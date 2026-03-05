"""
CONDUIT — Unit Tests: Inventory Tools
======================================
Tests for check_compatibility() — pure logic, no DB calls.
This is where the case-sensitivity bug was caught in production.
"""

import pytest
from tools.inventory_tools import check_compatibility


class TestCheckCompatibility:

    # ── HAPPY PATH ────────────────────────────────────────────────────────

    def test_exact_match_compatible(self, oem_brake_part, honda_city_vehicle):
        """Exact make/model/year/fuel match → compatible."""
        is_compat, reason = check_compatibility(oem_brake_part, honda_city_vehicle)
        assert is_compat is True

    def test_universal_part_always_compatible(self, universal_part, honda_city_vehicle):
        """Parts with 'All' in compatible_models work on any vehicle."""
        is_compat, reason = check_compatibility(universal_part, honda_city_vehicle)
        assert is_compat is True

    def test_universal_part_compatible_with_ev(self, universal_part, ev_vehicle):
        """Universal part works on EV too."""
        is_compat, _ = check_compatibility(universal_part, ev_vehicle)
        assert is_compat is True

    # ── MAKE CHECKS ───────────────────────────────────────────────────────

    def test_wrong_make_incompatible(self, oem_brake_part):
        """Part for Honda should not fit a Tata."""
        tata_vehicle = {
            "make": "Tata", "model": "Nexon",
            "year": 2022, "fuel_type": "Petrol"
        }
        is_compat, reason = check_compatibility(oem_brake_part, tata_vehicle)
        assert is_compat is False
        assert "Tata" in reason

    def test_make_check_case_insensitive(self, oem_brake_part):
        """Make comparison must be case-insensitive — this was a real bug."""
        vehicle_lowercase = {
            "make": "honda",      # lowercase
            "model": "City",
            "year": 2022,
            "fuel_type": "Petrol",
        }
        is_compat, _ = check_compatibility(oem_brake_part, vehicle_lowercase)
        assert is_compat is True

    # ── MODEL CHECKS ──────────────────────────────────────────────────────

    def test_wrong_model_incompatible(self, oem_brake_part):
        """Part for City should not fit a Jazz."""
        jazz_vehicle = {
            "make": "Honda", "model": "Jazz",
            "year": 2022, "fuel_type": "Petrol"
        }
        is_compat, reason = check_compatibility(oem_brake_part, jazz_vehicle)
        assert is_compat is False
        assert "Jazz" in reason

    def test_model_check_case_insensitive(self, oem_brake_part):
        """Model comparison must be case-insensitive."""
        vehicle_lower = {
            "make": "Honda", "model": "city",   # lowercase model
            "year": 2022, "fuel_type": "Petrol"
        }
        is_compat, _ = check_compatibility(oem_brake_part, vehicle_lower)
        assert is_compat is True

    # ── YEAR CHECKS ───────────────────────────────────────────────────────

    def test_year_within_range_compatible(self, oem_brake_part):
        """Year 2021 is within 2019-2023 range → compatible."""
        vehicle = {
            "make": "Honda", "model": "City",
            "year": 2021, "fuel_type": "Petrol"
        }
        is_compat, _ = check_compatibility(oem_brake_part, vehicle)
        assert is_compat is True

    def test_year_out_of_range_incompatible(self, oem_brake_part):
        """Year 2018 is before 2019 range start → incompatible."""
        old_vehicle = {
            "make": "Honda", "model": "City",
            "year": 2018, "fuel_type": "Petrol"
        }
        is_compat, reason = check_compatibility(oem_brake_part, old_vehicle)
        assert is_compat is False
        assert "2018" in reason

    def test_boundary_year_first_year_compatible(self, oem_brake_part):
        """First year of range (2019) → compatible."""
        vehicle = {
            "make": "Honda", "model": "City",
            "year": 2019, "fuel_type": "Petrol"
        }
        is_compat, _ = check_compatibility(oem_brake_part, vehicle)
        assert is_compat is True

    def test_boundary_year_last_year_compatible(self, oem_brake_part):
        """Last year of range (2023) → compatible."""
        vehicle = {
            "make": "Honda", "model": "City",
            "year": 2023, "fuel_type": "Petrol"
        }
        is_compat, _ = check_compatibility(oem_brake_part, vehicle)
        assert is_compat is True

    # ── FUEL TYPE CHECKS ──────────────────────────────────────────────────

    def test_wrong_fuel_type_incompatible(self, oem_brake_part):
        """Petrol part should not fit a diesel vehicle."""
        petrol_only_part = dict(oem_brake_part)
        petrol_only_part["compatible_fuel_types"] = ["Petrol"]

        diesel_vehicle = {
            "make": "Honda", "model": "City",
            "year": 2022, "fuel_type": "Diesel"
        }
        is_compat, reason = check_compatibility(petrol_only_part, diesel_vehicle)
        assert is_compat is False
        assert "Diesel" in reason

    def test_fuel_type_case_insensitive(self, oem_brake_part):
        """Fuel type comparison must be case-insensitive — was a real bug."""
        vehicle_lowercase_fuel = {
            "make": "Honda", "model": "City",
            "year": 2022, "fuel_type": "diesel",  # lowercase from DB
        }
        # Part has "Diesel" in compatible list
        is_compat, _ = check_compatibility(oem_brake_part, vehicle_lowercase_fuel)
        assert is_compat is True

    def test_electric_part_incompatible_with_petrol(self):
        """EV-specific part should not fit petrol vehicle."""
        ev_part = {
            "part_number":           "EV-BAT-01",
            "compatible_makes":      ["Tata"],
            "compatible_models":     ["Nexon EV"],
            "compatible_years":      [2022, 2023],
            "compatible_fuel_types": ["Electric"],
        }
        petrol_vehicle = {
            "make": "Tata", "model": "Nexon EV",
            "year": 2022, "fuel_type": "Petrol"
        }
        is_compat, reason = check_compatibility(ev_part, petrol_vehicle)
        assert is_compat is False

    # ── EDGE CASES ────────────────────────────────────────────────────────

    def test_empty_compatibility_lists_always_compatible(self):
        """Part with no restrictions set → compatible with everything."""
        unrestricted_part = {
            "compatible_makes":       [],
            "compatible_models":      [],
            "compatible_years":       [],
            "compatible_fuel_types":  [],
        }
        any_vehicle = {
            "make": "Toyota", "model": "Corolla",
            "year": 2015, "fuel_type": "Diesel"
        }
        is_compat, _ = check_compatibility(unrestricted_part, any_vehicle)
        assert is_compat is True

    def test_returns_tuple_of_bool_and_string(self, oem_brake_part, honda_city_vehicle):
        """Return type is always (bool, str)."""
        result = check_compatibility(oem_brake_part, honda_city_vehicle)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_incompatible_reason_is_informative(self, oem_brake_part):
        """Reason string should explain WHY it's incompatible."""
        wrong_make = {
            "make": "BMW", "model": "City",
            "year": 2022, "fuel_type": "Petrol"
        }
        _, reason = check_compatibility(oem_brake_part, wrong_make)
        assert len(reason) > 10   # not an empty or trivial string
        assert "BMW" in reason    # mentions the actual vehicle value