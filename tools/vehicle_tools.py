"""
CONDUIT — Vehicle Tools
VIN decode and vehicle catalog lookup utilities for the Intake Agent.
"""

import os
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()


def decode_vin(vin: str) -> Optional[Dict]:
    """
    Looks up vehicle details from the vehicles table by VIN.
    Returns full vehicle record or None if not found.

    In production this would also call an external VIN decode API
    for vehicles not yet in the system. For portfolio — DB lookup only.
    """
    from database.connection import get_session
    from database.models import Vehicle

    with get_session() as db:
        vehicle = db.query(Vehicle).filter(
            Vehicle.vin == vin.upper().strip()
        ).first()

        if not vehicle:
            return None

        return {
            "vin":                  vehicle.vin,
            "make":                 vehicle.make,
            "model":                vehicle.model,
            "year":                 vehicle.year,
            "trim":                 vehicle.trim,
            "fuel_type":            vehicle.fuel_type,
            "engine_code":          vehicle.engine_code,
            "transmission":         vehicle.transmission,
            "category":             vehicle.category,
            "color":                vehicle.color,
            "odometer_km":          vehicle.odometer_km,
            "registration_number":  vehicle.registration_number,
            "warranty_expired":     vehicle.warranty_expired,
            "battery_capacity_kwh": vehicle.battery_capacity_kwh,
            "is_ev":                vehicle.is_ev,
        }


def get_customer_by_vin(vin: str) -> Optional[Dict]:
    """
    Finds the customer who owns a given VIN.
    Used by Intake Agent to pull loyalty tier and discount rate.
    """
    from database.connection import get_session
    from database.models import Customer

    with get_session() as db:
        from sqlalchemy import cast, String
        # Use PostgreSQL JSON contains operator to avoid full table scan
        vin_upper = vin.upper()
        customer = (
            db.query(Customer)
            .filter(
                cast(Customer.vehicle_vins, String).contains(vin_upper)
            )
            .first()
        )

        if customer:
            return {
                "customer_id":       customer.customer_id,
                "full_name":         customer.full_name,
                "phone":             customer.phone,
                "loyalty_tier":      customer.loyalty_tier,
                "loyalty_tier_name": customer.loyalty_tier_name,
                "discount_rate":     customer.discount_rate,
                "total_visits":      customer.total_visits,
                "preferred_contact": customer.preferred_contact,
            }

        return None


def check_recall(vin: str, make: str, model: str, year: int) -> list:
    """
    Checks for active recalls on a vehicle.

    In production: calls OEM recall API (Honda, Hyundai etc.)
    For portfolio: returns mock recall data for specific known cases
    to demonstrate the feature without needing real API keys.
    """

    # Mock recall database — realistic examples for demo
    mock_recalls = [
        {
            "recall_id":     "RECALL-2023-HON-001",
            "make":          "Honda",
            "models":        ["City", "Amaze"],
            "years":         [2020, 2021, 2022],
            "description":   "Fuel pump may fail causing engine stall",
            "remedy":        "Replace fuel pump assembly at no charge",
            "parts_covered": ["Fuel Pump Assembly"],
            "severity":      "HIGH",
        },
        {
            "recall_id":     "RECALL-2022-HYN-001",
            "make":          "Hyundai",
            "models":        ["Creta"],
            "years":         [2020, 2021],
            "description":   "ABS module software error may increase stopping distance",
            "remedy":        "ABS module software update",
            "parts_covered": ["ABS Module"],
            "severity":      "HIGH",
        },
        {
            "recall_id":     "RECALL-2023-TAT-EV-001",
            "make":          "Tata",
            "models":        ["Nexon EV"],
            "years":         [2020, 2021],
            "description":   "Battery management system may cause unexpected power cutoff",
            "remedy":        "BMS software update and inspection",
            "parts_covered": ["Battery Management System"],
            "severity":      "CRITICAL",
        },
    ]

    active_recalls = []

    for recall in mock_recalls:
        if (
            recall["make"] == make
            and model in recall["models"]
            and year in recall["years"]
        ):
            active_recalls.append(recall)

    return active_recalls