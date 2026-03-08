"""
CONDUIT — Component Eval: Inventory Agent
==========================================
Tests part compatibility checks against ground truth dataset.
Cost: $0.00 — no LLM calls (compatibility is deterministic).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from evals.conftest import load_dataset, EvalResult
from tools.inventory_tools import check_compatibility


class TestCompatibilityAccuracy:

    def test_all_inventory_cases(self):
        cases   = load_dataset("inventory_eval_cases.json")
        tracker = EvalResult("Parts Compatibility Accuracy")

        for c in cases:
            is_compat, reason = check_compatibility(c["part"], c["vehicle"])
            expected          = c["expected"]["compatible"]
            passed            = is_compat == expected

            tracker.record(
                c["case_id"], "compatibility", passed,
                str(expected), str(is_compat), c["description"]
            )

            # If expected reason keyword, verify it appears
            if not expected and c["expected"].get("reason_contains"):
                keyword = c["expected"]["reason_contains"]
                assert keyword in reason, (
                    f"{c['case_id']}: expected '{keyword}' in reason, got: '{reason}'"
                )

        s = tracker.print_report()
        assert s["pass_rate"] == 100.0, (
            f"Compatibility accuracy {s['pass_rate']}% — must be 100%"
        )


class TestCompatibilityEdgeCases:

    def test_case_insensitive_make_check(self):
        """'honda' vs 'Honda' must both work."""
        part = {
            "part_number":           "BRK-PAD-HON-F-01",
            "compatible_makes":      ["Honda"],
            "compatible_models":     ["City"],
            "compatible_years":      [2022],
            "compatible_fuel_types": ["Petrol"],
        }
        vehicle = {"make": "honda", "model": "city", "year": 2022, "fuel_type": "petrol"}
        is_compat, _ = check_compatibility(part, vehicle)
        assert is_compat is True, "Case insensitive check failed for make/model"

    def test_universal_part_any_vehicle(self):
        part = {
            "part_number":           "FLT-OIL-UNI-01",
            "compatible_makes":      [],
            "compatible_models":     ["All"],
            "compatible_years":      [],
            "compatible_fuel_types": [],
        }
        vehicle = {"make": "Toyota", "model": "Innova", "year": 2019, "fuel_type": "Diesel"}
        is_compat, _ = check_compatibility(part, vehicle)
        assert is_compat is True

    def test_boundary_year_first(self):
        """First year in range must be compatible."""
        part = {
            "part_number":           "BRK-PAD-HON-F-01",
            "compatible_makes":      ["Honda"],
            "compatible_models":     ["City"],
            "compatible_years":      [2019, 2020, 2021, 2022, 2023],
            "compatible_fuel_types": ["Petrol"],
        }
        vehicle = {"make": "Honda", "model": "City", "year": 2019, "fuel_type": "Petrol"}
        is_compat, _ = check_compatibility(part, vehicle)
        assert is_compat is True

    def test_boundary_year_last(self):
        """Last year in range must be compatible."""
        part = {
            "part_number":           "BRK-PAD-HON-F-01",
            "compatible_makes":      ["Honda"],
            "compatible_models":     ["City"],
            "compatible_years":      [2019, 2020, 2021, 2022, 2023],
            "compatible_fuel_types": ["Petrol"],
        }
        vehicle = {"make": "Honda", "model": "City", "year": 2023, "fuel_type": "Petrol"}
        is_compat, _ = check_compatibility(part, vehicle)
        assert is_compat is True

    def test_one_year_outside_range_fails(self):
        part = {
            "part_number":           "BRK-PAD-HON-F-01",
            "compatible_makes":      ["Honda"],
            "compatible_models":     ["City"],
            "compatible_years":      [2019, 2020, 2021, 2022, 2023],
            "compatible_fuel_types": ["Petrol"],
        }
        vehicle = {"make": "Honda", "model": "City", "year": 2024, "fuel_type": "Petrol"}
        is_compat, _ = check_compatibility(part, vehicle)
        assert is_compat is False