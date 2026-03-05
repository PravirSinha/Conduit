"""
CONDUIT — Agent Tests: Inventory Agent
========================================
Tests validate_inventory_output() guardrail.
No DB calls — pure validation logic.
"""

import pytest
from agents.inventory_agent import validate_inventory_output


VALID_RESERVED_PART = {
    "part_number":  "BRK-PAD-HON-F-01",
    "description":  "Front brake pads",
    "qty_reserved": 1,
    "unit_cost":    3200.0,
    "sell_price":   4500.0,
}

VALID_INVENTORY_OUTPUT = {
    "reserved_parts":  [VALID_RESERVED_PART],
    "parts_available": True,
    "unavailable_parts": [],
    "reorder_needed":  [],
}


class TestValidateInventoryOutput:

    # ── HAPPY PATH ────────────────────────────────────────────────────────

    def test_valid_output_passes(self):
        is_valid, reason = validate_inventory_output(
            VALID_INVENTORY_OUTPUT, "RO-001"
        )
        assert is_valid is True
        assert reason == "OK"

    def test_empty_reserved_parts_passes(self):
        """No parts reserved is valid — agent handled unavailability."""
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [], "parts_available": False}
        is_valid, _ = validate_inventory_output(output, "RO-001")
        assert is_valid is True

    def test_multiple_parts_passes(self):
        part2 = {**VALID_RESERVED_PART, "part_number": "BRK-ROT-HON-F-01", "qty_reserved": 2}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [VALID_RESERVED_PART, part2]}
        is_valid, _ = validate_inventory_output(output, "RO-001")
        assert is_valid is True

    # ── parts_available ───────────────────────────────────────────────────

    def test_parts_available_must_be_boolean(self):
        output = {**VALID_INVENTORY_OUTPUT, "parts_available": "yes"}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "parts_available" in reason

    def test_parts_available_true_passes(self):
        output = {**VALID_INVENTORY_OUTPUT, "parts_available": True}
        is_valid, _ = validate_inventory_output(output, "RO-001")
        assert is_valid is True

    def test_parts_available_false_passes(self):
        output = {**VALID_INVENTORY_OUTPUT, "parts_available": False}
        is_valid, _ = validate_inventory_output(output, "RO-001")
        assert is_valid is True

    # ── RESERVED PARTS VALIDATION ─────────────────────────────────────────

    def test_reserved_parts_must_be_list(self):
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": "BRK-PAD-HON-F-01"}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "list" in reason.lower()

    def test_part_missing_part_number_fails(self):
        bad_part = {k: v for k, v in VALID_RESERVED_PART.items()
                    if k != "part_number"}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "part_number" in reason

    def test_part_missing_qty_reserved_fails(self):
        bad_part = {k: v for k, v in VALID_RESERVED_PART.items()
                    if k != "qty_reserved"}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "qty_reserved" in reason

    def test_part_missing_unit_cost_fails(self):
        bad_part = {k: v for k, v in VALID_RESERVED_PART.items()
                    if k != "unit_cost"}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "unit_cost" in reason

    def test_part_missing_sell_price_fails(self):
        bad_part = {k: v for k, v in VALID_RESERVED_PART.items()
                    if k != "sell_price"}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "sell_price" in reason

    def test_zero_quantity_fails(self):
        """qty_reserved of 0 is invalid — why reserve nothing?"""
        bad_part = {**VALID_RESERVED_PART, "qty_reserved": 0}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False
        assert "quantity" in reason.lower() or "qty" in reason.lower()

    def test_negative_quantity_fails(self):
        bad_part = {**VALID_RESERVED_PART, "qty_reserved": -1}
        output = {**VALID_INVENTORY_OUTPUT, "reserved_parts": [bad_part]}
        is_valid, reason = validate_inventory_output(output, "RO-001")
        assert is_valid is False