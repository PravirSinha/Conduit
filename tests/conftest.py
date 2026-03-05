"""
CONDUIT — pytest conftest.py
Shared fixtures available to all tests.
"""

import os
import sys
import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


# ── SAMPLE DATA FIXTURES ──────────────────────────────────────────────────────

@pytest.fixture
def honda_city_vehicle():
    """Standard Honda City vehicle dict — used across multiple tests."""
    return {
        "make":      "Honda",
        "model":     "City",
        "year":      2022,
        "fuel_type": "Petrol",
        "is_ev":     False,
    }


@pytest.fixture
def ev_vehicle():
    """Electric vehicle for EV-specific test cases."""
    return {
        "make":      "Tata",
        "model":     "Nexon EV",
        "year":      2023,
        "fuel_type": "Electric",
        "is_ev":     True,
    }


@pytest.fixture
def oem_brake_part():
    """OEM brake pad part dict with full compatibility metadata."""
    return {
        "part_number":            "BRK-PAD-HON-F-01",
        "description":            "Front disc brake pads Honda City 2019-2023",
        "brand":                  "Honda Genuine",
        "sell_price":             4500.0,
        "qty_on_hand":            5,
        "qty_reserved":           1,      # always explicit — never rely on default
        "qty_available":          5,
        "subcategory":            "Brake Pads",
        "compatible_makes":       ["Honda"],
        "compatible_models":      ["City", "Amaze"],
        "compatible_years":       list(range(2019, 2024)),
        "compatible_fuel_types":  ["Petrol", "Diesel"],
    }


@pytest.fixture
def universal_part():
    """Universal filter — compatible with all vehicles."""
    return {
        "part_number":           "FLT-OIL-UNI-01",
        "description":           "Universal oil filter",
        "brand":                 "Bosch",
        "sell_price":            350.0,
        "qty_on_hand":           20,
        "qty_reserved":          0,
        "qty_available":         20,
        "subcategory":           "Oil Filters",
        "compatible_makes":      [],
        "compatible_models":     ["All"],
        "compatible_years":      [],
        "compatible_fuel_types": [],
    }


@pytest.fixture
def loyalty_customer():
    """Gold tier loyalty customer with 10% discount."""
    return {
        "customer_id":       "CUST-001",
        "full_name":         "Arjun Sharma",
        "loyalty_tier":      3,
        "loyalty_tier_name": "Gold",
        "discount_rate":     0.10,
    }


@pytest.fixture
def new_customer():
    """New customer with no loyalty discount."""
    return {
        "customer_id":       "CUST-999",
        "full_name":         "New Customer",
        "loyalty_tier":      1,
        "loyalty_tier_name": "Standard",
        "discount_rate":     0.0,
    }


@pytest.fixture
def sample_line_items():
    """Sample line items for quote totals calculation."""
    return [
        {"type": "PART",  "description": "Brake pads",      "subtotal": 4500.0},
        {"type": "PART",  "description": "Brake rotor",     "subtotal": 6500.0},
        {"type": "LABOR", "description": "Brake pad change", "subtotal": 1800.0},
    ]