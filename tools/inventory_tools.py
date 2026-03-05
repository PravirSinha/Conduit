"""
CONDUIT — Inventory Tools
Stock check, parts reservation, and compatibility validation
utilities for the Inventory Agent.
"""

import os
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()


def get_part_details(part_number: str) -> Optional[Dict]:
    """
    Fetches full part details from inventory table.
    Returns None if part not found.
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
            "part_number":           part.part_number,
            "description":           part.description,
            "category":              part.category,
            "subcategory":           part.subcategory,
            "brand":                 part.brand,
            "unit_cost":             float(part.unit_cost or 0),
            "sell_price":            float(part.sell_price or 0),
            "bin_location":          part.bin_location,
            "qty_on_hand":           part.qty_on_hand,
            "qty_reserved":          part.qty_reserved,
            "qty_available":         part.qty_on_hand - part.qty_reserved,
            "reorder_point":         part.reorder_point,
            "reorder_quantity":      part.reorder_quantity,
            "stock_status":          part.stock_status,
            "compatible_makes":      part.compatible_makes or [],
            "compatible_models":     part.compatible_models or [],
            "compatible_years":      part.compatible_years or [],
            "compatible_fuel_types": part.compatible_fuel_types or [],
            "oem_part_number":       part.oem_part_number,
        }


def check_compatibility(
    part: Dict,
    vehicle: Dict,
) -> Tuple[bool, str]:
    """
    Validates that a part is compatible with a specific vehicle.
    Returns (is_compatible, reason)

    This prevents the classic dealership mistake of reserving
    a part that doesn't actually fit the customer's vehicle.
    """
    compatible_makes  = part.get("compatible_makes", [])
    compatible_models = part.get("compatible_models", [])
    compatible_years  = part.get("compatible_years", [])
    fuel_types        = part.get("compatible_fuel_types", [])

    vehicle_make      = vehicle.get("make", "")
    vehicle_model     = vehicle.get("model", "")
    vehicle_year      = vehicle.get("year", 0)
    vehicle_fuel      = vehicle.get("fuel_type", "")

    # Universal parts — compatible with everything
    if "All" in compatible_models:
        return True, "Universal part — compatible with all vehicles"

    # Check make
    if compatible_makes and vehicle_make.lower() not in [m.lower() for m in compatible_makes]:
        return False, (
            f"Part not compatible with {vehicle_make}. "
            f"Compatible makes: {compatible_makes}"
        )

    # Check model
    if compatible_models and vehicle_model.lower() not in [m.lower() for m in compatible_models]:
        return False, (
            f"Part not compatible with {vehicle_model}. "
            f"Compatible models: {compatible_models}"
        )

    # Check year
    if compatible_years and vehicle_year not in compatible_years:
        return False, (
            f"Part not compatible with {vehicle_year}. "
            f"Compatible years: {compatible_years}"
        )

    # Check fuel type
    if fuel_types:
        # Case-insensitive comparison
        vehicle_fuel_lower = vehicle_fuel.lower()
        fuel_types_lower   = [f.lower() for f in fuel_types]
        if vehicle_fuel_lower not in fuel_types_lower:
            return False, (
                f"Part not compatible with {vehicle_fuel} engine. "
                f"Compatible fuel types: {fuel_types}"
            )

    return True, "Compatible"


def check_stock(part_number: str) -> Dict:
    """
    Returns current stock levels for a part.
    qty_available = qty_on_hand - qty_reserved
    """
    from database.connection import get_session
    from database.models import Inventory

    with get_session() as db:
        part = db.query(Inventory).filter(
            Inventory.part_number == part_number
        ).first()

        if not part:
            return {
                "part_number":   part_number,
                "found":         False,
                "qty_on_hand":   0,
                "qty_reserved":  0,
                "qty_available": 0,
                "stock_status":  "not_found",
            }

        return {
            "part_number":   part.part_number,
            "found":         True,
            "qty_on_hand":   part.qty_on_hand,
            "qty_reserved":  part.qty_reserved,
            "qty_available": part.qty_on_hand - part.qty_reserved,
            "stock_status":  part.stock_status,
            "reorder_point": part.reorder_point,
            "below_reorder": part.qty_on_hand <= part.reorder_point,
        }


def reserve_parts(
    part_number: str,
    quantity: int,
    ro_id: str,
) -> Tuple[bool, str]:
    """
    Atomically reserves parts for a repair order.

    Uses a database transaction to prevent race conditions —
    two advisors cannot reserve the same last unit simultaneously.

    Returns (success, message)
    """
    from database.connection import get_session
    from database.models import Inventory
    from sqlalchemy import text

    try:
        with get_session() as db:

            # Lock the row during this transaction
            # Prevents concurrent reservations of same stock
            part = db.query(Inventory).filter(
                Inventory.part_number == part_number
            ).with_for_update().first()

            if not part:
                return False, f"Part {part_number} not found"

            available = part.qty_on_hand - part.qty_reserved

            if available < quantity:
                return False, (
                    f"Insufficient stock for {part_number}. "
                    f"Requested: {quantity}, "
                    f"Available: {available}"
                )

            # Atomically increment reserved quantity
            part.qty_reserved += quantity

            # Update stock status if falling below reorder point
            remaining_available = available - quantity
            if remaining_available <= 0:
                part.stock_status = "critical"
            elif remaining_available <= part.reorder_point:
                part.stock_status = "low"

            db.commit()

            return True, (
                f"Reserved {quantity} unit(s) of {part_number} "
                f"for RO {ro_id}"
            )

    except Exception as e:
        return False, f"Reservation failed: {str(e)}"


def release_reservation(
    part_number: str,
    quantity: int,
    ro_id: str,
) -> bool:
    """
    Releases a reservation when RO is cancelled or quantity adjusted.
    Called by Transaction Agent on RO cancellation.
    """
    from database.connection import get_session
    from database.models import Inventory

    try:
        with get_session() as db:
            part = db.query(Inventory).filter(
                Inventory.part_number == part_number
            ).with_for_update().first()

            if not part:
                return False

            # Never go below zero
            part.qty_reserved = max(
                0,
                part.qty_reserved - quantity
            )

            # Recalculate stock status
            available = part.qty_on_hand - part.qty_reserved
            if available > part.reorder_point:
                part.stock_status = "healthy"
            elif available > 0:
                part.stock_status = "low"
            else:
                part.stock_status = "critical"

            db.commit()
            return True

    except Exception:
        return False


def check_reorder_needed(part_number: str) -> bool:
    """
    Returns True if part needs to be reordered.
    Used by Replenishment Agent to trigger PO creation.
    """
    stock = check_stock(part_number)
    return stock.get("below_reorder", False)