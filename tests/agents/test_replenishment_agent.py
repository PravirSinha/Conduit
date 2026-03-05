"""
CONDUIT — Agent Tests: Replenishment Agent
============================================
Tests calculate_reorder_quantity() and validate_replenishment_output().
No DB, no external calls — pure logic.
"""

import pytest
from agents.replenishment_agent import (
    calculate_reorder_quantity,
    validate_replenishment_output,
)


class TestCalculateReorderQuantity:

    def test_uses_base_quantity_when_no_forecast(self):
        """No forecast data → use base reorder_quantity."""
        part     = {"reorder_quantity": 10, "is_ev_part": False}
        forecast = {"forecast_next_month": 0}
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 10

    def test_demand_driven_quantity_when_forecast_higher(self):
        """High demand forecast → order more than base."""
        part     = {"reorder_quantity": 10, "is_ev_part": False}
        forecast = {"forecast_next_month": 12}  # 12 * 2 = 24 > 10
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 24

    def test_base_quantity_wins_when_demand_lower(self):
        """Low forecast → base quantity is the floor."""
        part     = {"reorder_quantity": 20, "is_ev_part": False}
        forecast = {"forecast_next_month": 3}   # 3 * 2 = 6 < 20
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 20

    def test_ev_parts_always_use_base_quantity(self):
        """EV parts always use base — expensive, slow-moving."""
        part     = {"reorder_quantity": 5, "is_ev_part": True}
        forecast = {"forecast_next_month": 100}  # high demand ignored for EV
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 5

    def test_ev_part_ignores_high_forecast(self):
        """Even extreme forecast doesn't override EV base quantity."""
        part     = {"reorder_quantity": 2, "is_ev_part": True}
        forecast = {"forecast_next_month": 999}
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 2

    def test_missing_reorder_quantity_defaults_to_10(self):
        """Default reorder_quantity is 10 when not specified."""
        part     = {"is_ev_part": False}
        forecast = {"forecast_next_month": 0}
        qty = calculate_reorder_quantity(part, forecast)
        assert qty == 10

    def test_quantity_always_positive(self):
        """Reorder quantity must always be > 0."""
        part     = {"reorder_quantity": 5, "is_ev_part": False}
        forecast = {"forecast_next_month": 0}
        qty = calculate_reorder_quantity(part, forecast)
        assert qty > 0


class TestValidateReplenishmentOutput:

    VALID_PO = {
        "po_id":       "PO-20260304-TEST01",
        "supplier_id": "SUP-0001",
        "total_value": 92400.0,
        "parts_count": 10,
    }

    def test_valid_pos_passes(self):
        is_valid, reason = validate_replenishment_output([self.VALID_PO])
        assert is_valid is True
        assert reason == "OK"

    def test_empty_pos_passes(self):
        """No POs needed is a valid outcome."""
        is_valid, _ = validate_replenishment_output([])
        assert is_valid is True

    def test_multiple_pos_passes(self):
        po2 = {**self.VALID_PO, "po_id": "PO-20260304-TEST02", "supplier_id": "SUP-0002"}
        is_valid, _ = validate_replenishment_output([self.VALID_PO, po2])
        assert is_valid is True

    def test_missing_po_id_fails(self):
        bad_po = {k: v for k, v in self.VALID_PO.items() if k != "po_id"}
        is_valid, reason = validate_replenishment_output([bad_po])
        assert is_valid is False
        assert "po_id" in reason

    def test_missing_supplier_id_fails(self):
        bad_po = {k: v for k, v in self.VALID_PO.items() if k != "supplier_id"}
        is_valid, reason = validate_replenishment_output([bad_po])
        assert is_valid is False
        assert "supplier_id" in reason

    def test_missing_total_value_fails(self):
        bad_po = {k: v for k, v in self.VALID_PO.items() if k != "total_value"}
        is_valid, reason = validate_replenishment_output([bad_po])
        assert is_valid is False
        assert "total_value" in reason

    def test_zero_total_value_fails(self):
        bad_po = {**self.VALID_PO, "total_value": 0}
        is_valid, reason = validate_replenishment_output([bad_po])
        assert is_valid is False
        assert "value" in reason.lower()

    def test_negative_total_value_fails(self):
        bad_po = {**self.VALID_PO, "total_value": -100.0}
        is_valid, reason = validate_replenishment_output([bad_po])
        assert is_valid is False