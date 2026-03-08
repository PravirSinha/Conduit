"""
CONDUIT — Component Eval: Replenishment Agent
===============================================
Tests reorder quantity logic and PO generation accuracy.

Function signature (actual):
    calculate_reorder_quantity(part: dict, forecast: dict) -> int

forecast dict has key: forecast_next_month (float)

Cost: $0.00 — deterministic logic, no LLM calls.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.replenishment_agent import calculate_reorder_quantity
from evals.conftest import EvalResult


BASE_PART = {
    "part_number":    "BRK-PAD-HON-F-01",
    "reorder_quantity": 10,
    "subcategory":    "Brake Pads",
    "is_ev_part":     False,
}

EV_PART = {
    "part_number":    "EV-BAT-TTA-NXN-01",
    "reorder_quantity": 2,
    "subcategory":    "EV Battery",
    "is_ev_part":     True,
}

NO_DEMAND   = {"forecast_next_month": 0}
LOW_DEMAND  = {"forecast_next_month": 0.1}
HIGH_DEMAND = {"forecast_next_month": 15.0}


class TestReorderQuantityAccuracy:

    def test_uses_base_when_no_forecast(self):
        qty = calculate_reorder_quantity(BASE_PART, NO_DEMAND)
        assert qty == BASE_PART["reorder_quantity"]

    def test_uses_demand_when_higher_than_base(self):
        qty = calculate_reorder_quantity(BASE_PART, HIGH_DEMAND)
        # demand_driven = max(10, int(15 * 2)) = max(10, 30) = 30
        assert qty > BASE_PART["reorder_quantity"]

    def test_uses_base_when_demand_lower(self):
        qty = calculate_reorder_quantity(BASE_PART, LOW_DEMAND)
        # demand_driven = max(10, int(0.1 * 2)) = max(10, 0) = 10
        assert qty == BASE_PART["reorder_quantity"]

    def test_ev_parts_always_use_base_quantity(self):
        """EV parts are expensive and slow-moving — never inflate quantity."""
        qty = calculate_reorder_quantity(EV_PART, HIGH_DEMAND)
        assert qty == EV_PART["reorder_quantity"], (
            f"EV part qty {qty} != base {EV_PART['reorder_quantity']} — "
            "high demand forecast should be ignored for EV parts"
        )

    def test_quantity_always_positive(self):
        qty = calculate_reorder_quantity(BASE_PART, NO_DEMAND)
        assert qty > 0

    def test_missing_reorder_quantity_defaults_to_10(self):
        part = {"part_number": "TEST-001", "subcategory": "General", "is_ev_part": False}
        qty  = calculate_reorder_quantity(part, NO_DEMAND)
        assert qty == 10

    def test_quantity_is_integer(self):
        qty = calculate_reorder_quantity(BASE_PART, {"forecast_next_month": 3.7})
        assert isinstance(qty, int), f"Reorder qty must be int, got {type(qty)}"

    def test_high_demand_doubles_forecast(self):
        """demand_driven = max(base, int(forecast_next_month * 2))"""
        forecast = {"forecast_next_month": 20.0}
        qty      = calculate_reorder_quantity(BASE_PART, forecast)
        # max(10, int(20 * 2)) = max(10, 40) = 40
        assert qty == 40


class TestReorderQuantityDataset:

    CASES = [
        # (part,      forecast_next_month, expected_min, expected_max, description)
        (BASE_PART,  0,    10, 10,  "no demand → base qty"),
        (BASE_PART,  0.1,  10, 10,  "low demand → base qty"),
        (BASE_PART,  15.0, 11, None,"high demand → above base"),
        (EV_PART,    20.0, 2,  2,   "EV part → always base qty, never inflated"),
    ]

    def test_all_reorder_cases(self):
        tracker = EvalResult("Reorder Quantity Accuracy")

        for i, (part, demand, exp_min, exp_max, desc) in enumerate(self.CASES):
            forecast = {"forecast_next_month": demand}
            qty      = calculate_reorder_quantity(part, forecast)
            passed   = qty >= exp_min
            if exp_max is not None:
                passed = passed and qty <= exp_max

            exp_str = f">= {exp_min}" + (f" <= {exp_max}" if exp_max else "")
            tracker.record(f"RQ-{i+1:03d}", "reorder_qty", passed,
                           exp_str, qty, desc)

        s = tracker.print_report()
        assert s["pass_rate"] == 100.0