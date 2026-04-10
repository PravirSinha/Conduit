"""
CONDUIT — Replenishment Agent (Agent 5)
=========================================
Final agent in the pipeline. Triggered after Transaction Agent
confirms or whenever reorder flags are raised by Inventory Agent.

Responsibilities:
    1. Check which parts fell below reorder point
    2. Calculate reorder quantity using demand forecast
    3. Score and select best supplier per part
    4. Group parts by supplier to minimise PO count
    5. Raise purchase orders in PostgreSQL
    6. Return PO summary for dashboard display

Key design decisions:
    - No LLM — pure deterministic supplier scoring
    - Supplier selected by composite scorecard (on-time + fill rate)
    - Parts grouped by supplier → one PO per supplier not per part
    - EV parts always go to Tier 1 or Tier 2 suppliers only
    - Demand forecast from historical RO data (3 month lookback)
"""

import os
import sys
import time
from typing import List, Dict, Optional
from collections import defaultdict

# ── PATH SETUP ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))

from dotenv import load_dotenv
load_dotenv()

from tools.po_tools import (
    get_best_supplier,
    get_reorder_details,
    create_purchase_order,
    get_demand_forecast,
)

from tools.inventory_tools import check_stock

from app_logging.agent_logger import (
    log_agent_start,
    log_agent_end,
    log_agent_error,
)


# ── REORDER QUANTITY LOGIC ────────────────────────────────────────────────────

def calculate_reorder_quantity(
    part: Dict,
    forecast: Dict,
) -> int:
    """
    Calculates how many units to order.

    Logic:
        Base quantity    = part.reorder_quantity (from catalog)
        Demand adjusted  = max(base, forecast_next_month * 2)
        EV parts         = always use base quantity (expensive, slow-moving)

    This ensures we don't over-order expensive EV parts
    but adequately stock high-velocity consumables.
    """
    base_quantity     = part.get("reorder_quantity", 10)
    is_ev_part        = part.get("is_ev_part", False)
    forecast_next     = forecast.get("forecast_next_month", 0)

    # EV parts — always order base quantity
    # Too expensive to over-order, too slow-moving to run out quickly
    if is_ev_part:
        return base_quantity

    # High demand parts — order more if forecast suggests it
    demand_driven = max(base_quantity, int(forecast_next * 2))

    return demand_driven


# ── GUARDRAILS ────────────────────────────────────────────────────────────────

def validate_replenishment_output(pos_raised: list) -> tuple:
    """Validates POs before returning final state."""

    for po in pos_raised:
        # Each PO must have required fields
        for field in ["po_id", "supplier_id", "total_value", "parts_count"]:
            if field not in po:
                return False, f"PO missing field: {field}"

        # Total value must be positive
        if po.get("total_value", 0) <= 0:
            return False, f"Invalid PO value: {po.get('total_value')}"

    return True, "OK"


# ── MAIN AGENT FUNCTION ───────────────────────────────────────────────────────

def run_replenishment_agent(state: dict) -> dict:
    """
    Main Replenishment Agent function.

    Can be triggered in two ways:
    1. End of pipeline — after Transaction Agent completes
    2. Standalone — called directly when inventory check flags reorder

    Both paths use the same logic — checks reorder_needed list from state.
    """
    start_time = time.time()
    ro_id      = state.get("ro_id", "UNKNOWN")

    reorder_needed = state.get("reorder_needed", [])

    log_agent_start(
        agent_name="replenishment_agent",
        ro_id=ro_id,
        input_summary={
            "parts_to_reorder": reorder_needed,
            "count":            len(reorder_needed),
        }
    )

    try:

        # Nothing to reorder — exit cleanly
        if not reorder_needed:
            latency_ms = int((time.time() - start_time) * 1000)
            log_agent_end(
                agent_name="replenishment_agent",
                ro_id=ro_id,
                output_summary={"note": "No reorder needed"},
                latency_ms=latency_ms,
            )
            return {
                **state,
                "pos_raised":        [],
                "reorder_summary":   "No parts require reordering",
                "current_agent":     "replenishment_agent",
                "error":             None,
            }

        # ── STEP 1: ENRICH EACH PART WITH DETAILS + FORECAST ──────────────
        parts_to_order = []

        for part_number in reorder_needed:

            # Get current stock details
            part = get_reorder_details(part_number)
            if not part:
                continue

            # Get demand forecast from historical ROs
            forecast = get_demand_forecast(
                part_number     = part_number,
                lookback_months = 3,
            )

            # Calculate how many to order
            order_qty = calculate_reorder_quantity(part, forecast)

            parts_to_order.append({
                **part,
                "order_quantity":      order_qty,
                "order_value":         round(order_qty * part["unit_cost"], 2),
                "forecast":            forecast,
                "avg_monthly_demand":  forecast.get("avg_monthly_demand", 0),
            })

        if not parts_to_order:
            return {
                **state,
                "pos_raised":      [],
                "reorder_summary": "Parts not found in catalog",
                "current_agent":   "replenishment_agent",
                "error":           None,
            }

        # ── STEP 2: SELECT BEST SUPPLIER PER PART ─────────────────────────
        parts_with_suppliers = []

        for part in parts_to_order:
            supplier = get_best_supplier(
                part_number = part["part_number"],
                category    = part.get("category", ""),
                is_ev_part  = part.get("is_ev_part", False),
            )

            if not supplier:
                # No supplier found — flag but don't fail pipeline
                parts_with_suppliers.append({
                    **part,
                    "supplier":         None,
                    "supplier_warning": f"No supplier found for {part['part_number']}"
                })
                continue

            parts_with_suppliers.append({
                **part,
                "supplier":         supplier,
                "supplier_warning": None,
            })

        # ── STEP 3: GROUP PARTS BY SUPPLIER ───────────────────────────────
        # One PO per supplier — reduces admin overhead
        supplier_groups = defaultdict(list)
        no_supplier_parts = []

        for part in parts_with_suppliers:
            if part.get("supplier"):
                supplier_id = part["supplier"]["supplier_id"]
                supplier_groups[supplier_id].append(part)
            else:
                no_supplier_parts.append(part)

        # ── STEP 4: RAISE ONE PO PER SUPPLIER ─────────────────────────────
        pos_raised = []

        for supplier_id, parts in supplier_groups.items():
            supplier_info = parts[0]["supplier"]

            try:
                po_id, total_value = create_purchase_order(
                    supplier_id = supplier_id,
                    parts       = parts,
                    raised_by   = "REPLENISHMENT_AGENT",
                )

                pos_raised.append({
                    "po_id":          po_id,
                    "supplier_id":    supplier_id,
                    "supplier_name":  supplier_info["short_name"],
                    "supplier_email": supplier_info["contact_email"],
                    "parts_count":    len(parts),
                    "parts":          [
                        {
                            "part_number":    p["part_number"],
                            "description":    p["description"],
                            "order_quantity": p["order_quantity"],
                            "unit_cost":      p["unit_cost"],
                            "order_value":    p["order_value"],
                        }
                        for p in parts
                    ],
                    "total_value":       round(total_value, 2),
                    "lead_time_days":    supplier_info["lead_time_days"],
                    "integration_type":  supplier_info["integration_type"],
                    "reliability_tier":  supplier_info["reliability_tier"],
                    "on_time_rate":      supplier_info["current_on_time_rate"],
                    "status":            "RAISED",
                })

            except Exception as e:
                # PO creation failed — log but don't crash pipeline
                pos_raised.append({
                    "po_id":         "FAILED",
                    "supplier_id":   supplier_id,
                    "supplier_name": supplier_info.get("short_name"),
                    "parts_count":   len(parts),
                    "total_value":   0,
                    "status":        "FAILED",
                    "error":         str(e),
                })

        # ── STEP 5: BUILD SUMMARY ──────────────────────────────────────────
        successful_pos = [p for p in pos_raised if p["status"] == "RAISED"]
        failed_pos     = [p for p in pos_raised if p["status"] == "FAILED"]

        total_po_value = sum(p["total_value"] for p in successful_pos)

        if successful_pos:
            reorder_summary = (
                f"{len(successful_pos)} PO(s) raised | "
                f"{len(reorder_needed)} parts | "
                f"Total value ₹{total_po_value:,.0f}"
            )
        else:
            reorder_summary = "No POs raised — supplier selection failed"

        # ── STEP 6: LOG AND RETURN ─────────────────────────────────────────
        latency_ms = int((time.time() - start_time) * 1000)

        log_agent_end(
            agent_name="replenishment_agent",
            ro_id=ro_id,
            output_summary={
                "pos_raised":      len(successful_pos),
                "pos_failed":      len(failed_pos),
                "total_po_value":  total_po_value,
                "no_supplier":     len(no_supplier_parts),
                "latency_ms":      latency_ms,
            },
            latency_ms=latency_ms,
        )

        # ── STEP 7: MARK RO AS COMPLETE ───────────────────────────────────
        # Pipeline is done — update RO status to COMPLETE and write final_total
        try:
            quote = state.get("quote") or {}
            final_total = float(quote.get("total_amount", 0))
            from database.connection import get_session
            from database.models import RepairOrder
            from datetime import datetime
            with get_session() as db:
                ro = db.query(RepairOrder).filter(
                    RepairOrder.ro_id == ro_id
                ).first()
                if ro and ro.status == "IN_PROGRESS":
                    ro.status      = "COMPLETE"
                    ro.final_total = final_total
                    ro.updated_at  = datetime.utcnow()
                    db.commit()
        except Exception as e:
            print(f"[REPLENISHMENT] Warning: could not mark RO complete: {e}", flush=True)

        return {
            **state,
            "pos_raised":      pos_raised,
            "reorder_summary": reorder_summary,
            "total_po_value":  total_po_value,
            "current_agent":   "replenishment_agent",
            "error":           None,
        }

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log_agent_error(
            agent_name="replenishment_agent",
            ro_id=ro_id,
            error=str(e),
            input_state={"reorder_needed": reorder_needed},
        )

        return {
            **state,
            "error":         str(e),
            "current_agent": "replenishment_agent",
        }


# ── STANDALONE TEST ───────────────────────────────────────────────────────────

if __name__ == "__main__":

    # First check which parts are actually low in your DB
    from database.connection import get_session
    from database.models import Inventory

    with get_session() as db:
        low_parts = db.query(Inventory).filter(
            Inventory.stock_status.in_(["low", "critical"])
        ).limit(3).all()

        low_part_numbers = [p.part_number for p in low_parts]

    if not low_part_numbers:
        print("No low stock parts found — using test parts directly")
        low_part_numbers = ["BRK-PAD-HON-F-01"]

    print("\nRunning Replenishment Agent test...")
    print(f"Parts flagged for reorder: {low_part_numbers}\n")

    test_state = {
        "ro_id":         "RO-TEST-005",
        "reorder_needed": low_part_numbers,
        "transaction_status": "APPROVED",
    }

    result = run_replenishment_agent(test_state)

    if result.get("error"):
        print(f"ERROR: {result['error']}")
    else:
        print(f"Reorder Summary: {result['reorder_summary']}")
        print("\nPOs Raised:")

        for po in result.get("pos_raised", []):
            if po["status"] == "RAISED":
                print(f"\n  PO ID:        {po['po_id']}")
                print(f"  Supplier:     {po['supplier_name']}")
                print(f"  Parts:        {po['parts_count']}")
                print(f"  Total Value:  ₹{po['total_value']:,.0f}")
                print(f"  Lead Time:    {po['lead_time_days']} days")
                print(f"  Integration:  {po['integration_type']}")
                print(f"  On-Time Rate: {po['on_time_rate']*100:.0f}%")
                print("  Parts Detail:")
                for p in po.get("parts", []):
                    print(
                        f"    {p['part_number']:<25} "
                        f"qty={p['order_quantity']:>3} "
                        f"₹{p['order_value']:>8,.0f}"
                    )
            else:
                print(f"\n  FAILED PO: {po.get('error')}")