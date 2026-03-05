"""
CONDUIT — Pricing Tools
Quote calculation utilities for the Quoting Agent.
Handles parts pricing, labor costs, discounts, and GST.
All calculations are deterministic — no LLM involved.
"""

import os
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

GST_RATE        = 0.18   # 18% GST on parts + labor in India
MAX_DISCOUNT    = 0.30   # hard cap — no discount above 30%
QUOTE_VALID_DAYS = 3     # quote expires after 3 days

# Auto-approve threshold — quotes above this need human approval
# Loaded from env so it can be configured per dealership
AUTO_APPROVE_THRESHOLD = float(
    os.getenv("AUTO_APPROVE_THRESHOLD", "50000")
)


# ── LABOR PRICING ─────────────────────────────────────────────────────────────

def get_labor_operations(operation_codes: List[str]) -> List[Dict]:
    """
    Fetches labor operation details from PostgreSQL.
    Returns list of operations with flat rate hours and cost.
    """
    from database.connection import get_session
    from database.models import LaborOperation

    if not operation_codes:
        return []

    with get_session() as db:
        operations = db.query(LaborOperation).filter(
            LaborOperation.operation_code.in_(operation_codes)
        ).all()

        return [
            {
                "operation_code":   op.operation_code,
                "description":      op.description,
                "flat_rate_hours":  float(op.flat_rate_hours),
                "skill_level":      op.skill_level,
                "rate_per_hour":    float(op.rate_per_hour),
                "labor_cost":       round(
                                        op.flat_rate_hours * op.rate_per_hour,
                                        2
                                    ),
            }
            for op in operations
        ]


def infer_labor_from_parts(reserved_parts: List[Dict]) -> List[Dict]:
    """
    Infers labor operations from reserved parts when no
    explicit labor codes are provided by Intake Agent.

    Maps part subcategory → labor operation code.
    Fallback for when recommended_labor_codes is empty.
    """
    from database.connection import get_session
    from database.models import LaborOperation

    # Subcategory → labor code mapping
    subcategory_to_labor = {
        "Brake Pads":       "BRK-001",
        "Brake Rotors":     "BRK-002",
        "Oil Filters":      "SVC-001",
        "Air Filters":      "SVC-002",
        "Spark Plugs":      "SVC-002",
        "Batteries":        "BAT-001",
        "Shock Absorbers":  "SUS-001",
        "Timing Belt":      "ENG-001",
        "EV Battery":       "EV-001",
    }

    inferred_codes = set()

    for part in reserved_parts:
        # part may have subcategory directly or need lookup
        subcategory = part.get("subcategory")

        if not subcategory:
            # Look up from DB
            from database.models import Inventory
            with get_session() as db:
                inv = db.query(Inventory).filter(
                    Inventory.part_number == part["part_number"]
                ).first()
                if inv:
                    subcategory = inv.subcategory

        if subcategory and subcategory in subcategory_to_labor:
            inferred_codes.add(subcategory_to_labor[subcategory])

    if not inferred_codes:
        return []

    return get_labor_operations(list(inferred_codes))


# ── DISCOUNT CALCULATION ──────────────────────────────────────────────────────

def calculate_discount(
    subtotal: float,
    customer_details: Optional[Dict],
    fault_classification: Optional[str],
    recall_action_required: bool,
) -> Tuple[float, str]:
    """
    Calculates applicable discount rate and reason.

    Priority order:
    1. Recall — always 100% covered (zero cost to customer)
    2. Warranty — parts covered, customer pays labor only
    3. Loyalty tier discount
    4. No discount

    Returns (discount_rate, discount_reason)
    """

    # Recall — fully covered by manufacturer
    if recall_action_required:
        return 1.0, "Manufacturer recall — fully covered at no charge"

    # Loyalty tier discount
    if customer_details:
        tier         = customer_details.get("loyalty_tier", 1)
        discount_rate = customer_details.get("discount_rate", 0.0)

        # Apply tier discount
        if discount_rate > 0:
            tier_name = customer_details.get("loyalty_tier_name", "Standard")
            reason    = f"{tier_name} member discount ({discount_rate*100:.0f}%)"
            # Never exceed max discount cap
            return min(discount_rate, MAX_DISCOUNT), reason

    return 0.0, "No discount applicable"


# ── QUOTE LINE ITEMS ──────────────────────────────────────────────────────────

def build_parts_line_items(
    reserved_parts: List[Dict],
    use_oem: bool = True,
) -> List[Dict]:
    """
    Builds line items for reserved parts.
    use_oem=True  → uses sell_price (OEM pricing)
    use_oem=False → uses discounted sell_price (aftermarket)
    """
    line_items = []

    for part in reserved_parts:
        sell_price = float(part.get("sell_price", 0))

        # Aftermarket is typically 25-35% cheaper than OEM
        if not use_oem:
            sell_price = round(sell_price * 0.72, 2)

        subtotal = round(sell_price * part.get("qty_reserved", 1), 2)

        line_items.append({
            "type":         "PART",
            "part_number":  part["part_number"],
            "description":  part["description"],
            "brand":        part.get("brand", ""),
            "qty":          part.get("qty_reserved", 1),
            "unit_price":   sell_price,
            "subtotal":     subtotal,
            "bin_location": part.get("bin_location", ""),
            "is_oem":       use_oem,
        })

    return line_items


def build_labor_line_items(labor_operations: List[Dict]) -> List[Dict]:
    """Builds line items for labor operations."""
    line_items = []

    for op in labor_operations:
        line_items.append({
            "type":             "LABOR",
            "operation_code":   op["operation_code"],
            "description":      op["description"],
            "flat_rate_hours":  op["flat_rate_hours"],
            "rate_per_hour":    op["rate_per_hour"],
            "subtotal":         op["labor_cost"],
            "skill_level":      op["skill_level"],
        })

    return line_items


# ── TOTALS CALCULATION ────────────────────────────────────────────────────────

def calculate_totals(
    line_items: List[Dict],
    discount_rate: float,
) -> Dict:
    """
    Calculates quote totals with discount and GST.

    Formula:
        subtotal       = sum of all line items
        discount       = subtotal * discount_rate
        post_discount  = subtotal - discount
        gst            = post_discount * GST_RATE
        total          = post_discount + gst
    """
    subtotal = round(
        sum(item["subtotal"] for item in line_items), 2
    )

    discount_amount = round(subtotal * discount_rate, 2)
    post_discount   = round(subtotal - discount_amount, 2)
    gst_amount      = round(post_discount * GST_RATE, 2)
    total_amount    = round(post_discount + gst_amount, 2)

    return {
        "subtotal":        subtotal,
        "discount_rate":   discount_rate,
        "discount_amount": discount_amount,
        "post_discount":   post_discount,
        "gst_rate":        GST_RATE,
        "gst_amount":      gst_amount,
        "total_amount":    total_amount,
    }


def requires_approval(total_amount: float, is_ev_job: bool) -> Tuple[bool, str]:
    """
    Determines if quote needs human approval before proceeding.

    Rules:
    - Above AUTO_APPROVE_THRESHOLD → needs approval
    - EV job → always needs approval (safety + cost)
    """
    if is_ev_job:
        return True, "EV job — always requires advisor approval"

    if total_amount > AUTO_APPROVE_THRESHOLD:
        return (
            True,
            f"Quote ₹{total_amount:,.0f} exceeds "
            f"auto-approve threshold ₹{AUTO_APPROVE_THRESHOLD:,.0f}"
        )

    return False, "Within auto-approve threshold"