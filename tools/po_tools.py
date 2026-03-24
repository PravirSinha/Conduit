"""
CONDUIT — PO Tools
Purchase order creation and supplier selection utilities
for the Replenishment Agent.
"""

import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()


def get_best_supplier(
    part_number: str,
    category: str,
    is_ev_part: bool,
) -> Optional[Dict]:
    """
    Selects best supplier for a part based on composite scorecard.

    Scoring weights:
        On-time delivery rate  50%
        Fill rate              30%
        Lead time              20%

    EV parts → only EV-specialist or OEM suppliers considered.
    """
    from database.connection import get_session
    from database.models import Supplier

    with get_session() as db:
        suppliers = db.query(Supplier).all()

        candidates = []
        for s in suppliers:
            categories = s.categories_supplied or []

            # Filter by category capability
            if category not in categories:
                continue

            # EV parts must go to EV-capable suppliers
            if is_ev_part and s.reliability_tier not in ["Tier 1", "Tier 2"]:
                continue

            candidates.append({
                "supplier_id":          s.supplier_id,
                "name":                 s.name,
                "short_name":           s.short_name,
                "composite_score":      s.composite_score or 0,
                "current_on_time_rate": s.current_on_time_rate or 0,
                "current_fill_rate":    s.current_fill_rate or 0,
                "lead_time_days":       s.lead_time_days or 7,
                "min_order_value":      float(s.min_order_value or 0),
                "contact_email":        s.contact_email,
                "integration_type":     s.integration_type,
                "reliability_tier":     s.reliability_tier,
            })

        if not candidates:
            return None

        # Sort by composite score descending
        candidates.sort(
            key=lambda x: x["composite_score"],
            reverse=True
        )

        return candidates[0]


def get_reorder_details(part_number: str) -> Optional[Dict]:
    """
    Fetches part details needed to calculate reorder quantity and value.
    """
    from database.connection import get_session
    from database.models import Inventory

    with get_session() as db:
        part = db.query(Inventory).filter(
            Inventory.part_number == part_number
        ).first()

        if not part:
            return None

        return {
            "part_number":     part.part_number,
            "description":     part.description,
            "category":        part.category,
            "subcategory":     part.subcategory,
            "qty_on_hand":     part.qty_on_hand,
            "qty_reserved":    part.qty_reserved,
            "reorder_point":   part.reorder_point,
            "reorder_quantity": part.reorder_quantity,
            "unit_cost":       float(part.unit_cost or 0),
            "is_ev_part":      part.category == "EV Components",
        }


def create_purchase_order(
    supplier_id: str,
    parts: List[Dict],
    raised_by: str = "REPLENISHMENT_AGENT",
) -> Tuple[str, float]:
    """
    Creates a purchase order in PostgreSQL.
    Groups multiple parts into a single PO per supplier.
    Returns (po_id, total_value)
    """
    from database.connection import get_session
    from database.models import PurchaseOrder

    po_id       = f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    # Use demand-adjusted `order_quantity` calculated in Replenishment Agent.
    # Fall back to catalog `reorder_quantity` only if needed.
    total_value = sum(
        float(p.get("unit_cost", 0))
        * int(p.get("order_quantity", p.get("reorder_quantity", 0)))
        for p in parts
    )

    try:
        with get_session() as db:
            po = PurchaseOrder(
                po_id       = po_id,
                supplier_id = supplier_id,
                total_value = total_value,
                status      = "RAISED",
                raised_by   = raised_by,
                month       = datetime.utcnow().month,
                year        = datetime.utcnow().year,
            )
            db.add(po)
            db.commit()

        return po_id, total_value

    except Exception as e:
        raise Exception(f"Failed to create PO: {e}")


def get_demand_forecast(
    part_number: str,
    lookback_months: int = 3,
) -> Dict:
    """
    Calculates average monthly demand from historical RO data.
    Used to validate reorder quantity is appropriate.

    Simple average — production would use time-series forecasting.
    Portfolio version demonstrates awareness of demand-driven replenishment.
    """
    from database.connection import get_session
    from database.models import RepairOrder
    from sqlalchemy import text

    with get_session() as db:
        # Count ROs in last N months that used this part
        # Uses classification_payload JSONB field
        result = db.execute(text("""
            SELECT COUNT(*) as ro_count
            FROM repair_orders
            WHERE status = 'COMPLETE'
            AND created_at >= NOW() - INTERVAL ':months months'
            AND classification_payload::text LIKE :part_pattern
        """), {
            "months":       lookback_months,
            "part_pattern": f"%{part_number}%",
        })

        row      = result.fetchone()
        ro_count = row[0] if row else 0

        avg_monthly_demand = round(ro_count / max(lookback_months, 1), 1)

        return {
            "part_number":         part_number,
            "lookback_months":     lookback_months,
            "total_usage":         ro_count,
            "avg_monthly_demand":  avg_monthly_demand,
            "forecast_next_month": round(avg_monthly_demand * 1.1, 1),
        }