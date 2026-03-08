"""
CONDUIT — Guardrail Evals: All Agent Output Validators
========================================================
Tests validate_*_output() for inventory, transaction,
and replenishment agents.
Cost: $0.00 — no LLM calls.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.inventory_agent     import validate_inventory_output
from agents.transaction_agent   import validate_transaction_output
from agents.replenishment_agent import validate_replenishment_output


# ── INVENTORY ─────────────────────────────────────────────────────────────────

class TestInventoryOutputValidator:

    VALID_PART = {
        "part_number":  "BRK-PAD-HON-F-01",
        "qty_reserved": 1,
        "unit_cost":    3200.0,
        "sell_price":   4500.0,
    }
    VALID = {"parts_available": True, "reserved_parts": [VALID_PART]}

    def test_valid_output_passes(self):
        ok, reason = validate_inventory_output(self.VALID, "EVAL-001")
        assert ok is True, f"Valid inventory output rejected: {reason}"

    def test_empty_reserved_parts_passes(self):
        """Parts unavailable is valid — agent should still return cleanly."""
        ok, _ = validate_inventory_output({"parts_available": False, "reserved_parts": []}, "EVAL-001")
        assert ok is True

    def test_zero_qty_reserved_rejected(self):
        part = {**self.VALID_PART, "qty_reserved": 0}
        ok, _ = validate_inventory_output({"parts_available": True, "reserved_parts": [part]}, "EVAL-001")
        assert ok is False

    def test_negative_qty_reserved_rejected(self):
        part = {**self.VALID_PART, "qty_reserved": -1}
        ok, _ = validate_inventory_output({"parts_available": True, "reserved_parts": [part]}, "EVAL-001")
        assert ok is False

    def test_missing_sell_price_rejected(self):
        part = {k: v for k, v in self.VALID_PART.items() if k != "sell_price"}
        ok, _ = validate_inventory_output({"parts_available": True, "reserved_parts": [part]}, "EVAL-001")
        assert ok is False

    def test_missing_part_number_rejected(self):
        part = {k: v for k, v in self.VALID_PART.items() if k != "part_number"}
        ok, _ = validate_inventory_output({"parts_available": True, "reserved_parts": [part]}, "EVAL-001")
        assert ok is False


# ── TRANSACTION ───────────────────────────────────────────────────────────────

class TestTransactionOutputValidator:

    VALID = {
        "quote_id":             "QT-TEST-001",
        "reserved_parts":       [{"part_number": "BRK-PAD-HON-F-01", "qty_reserved": 1}],
        "fault_classification": "BRAKE_SYSTEM",
        "quote":                {"total_amount": 15000.0},
    }

    def test_valid_state_passes(self):
        ok, reason = validate_transaction_output(self.VALID)
        assert ok is True, f"Valid transaction state rejected: {reason}"

    def test_missing_quote_id_rejected(self):
        state = {**self.VALID, "quote_id": None}
        ok, reason = validate_transaction_output(state)
        assert ok is False
        assert "quote_id" in reason.lower()

    def test_no_reserved_parts_non_routine_rejected(self):
        state = {**self.VALID, "reserved_parts": [], "fault_classification": "BRAKE_SYSTEM"}
        ok, _ = validate_transaction_output(state)
        assert ok is False

    def test_routine_service_no_parts_passes(self):
        """Labor-only routine jobs can have no reserved parts."""
        state = {**self.VALID, "reserved_parts": [], "fault_classification": "ROUTINE_SERVICE"}
        ok, _ = validate_transaction_output(state)
        assert ok is True

    def test_zero_quote_total_rejected(self):
        state = {**self.VALID, "quote": {"total_amount": 0}}
        ok, _ = validate_transaction_output(state)
        assert ok is False

    def test_negative_quote_total_rejected(self):
        state = {**self.VALID, "quote": {"total_amount": -500}}
        ok, _ = validate_transaction_output(state)
        assert ok is False


# ── REPLENISHMENT ─────────────────────────────────────────────────────────────

class TestReplenishmentOutputValidator:

    VALID_PO = {
        "po_id":       "PO-TEST-001",
        "supplier_id": "SUP-001",
        "total_value": 15000.0,
        "parts_count": 2,          # required field
        "status":      "RAISED",
    }

    def test_valid_pos_passes(self):
        ok, reason = validate_replenishment_output([self.VALID_PO])
        assert ok is True, f"Valid replenishment output rejected: {reason}"

    def test_empty_pos_passes(self):
        """No reorder needed is a valid state."""
        ok, _ = validate_replenishment_output([])
        assert ok is True

    def test_missing_po_id_rejected(self):
        po = {k: v for k, v in self.VALID_PO.items() if k != "po_id"}
        ok, _ = validate_replenishment_output([po])
        assert ok is False

    def test_missing_supplier_id_rejected(self):
        po = {k: v for k, v in self.VALID_PO.items() if k != "supplier_id"}
        ok, _ = validate_replenishment_output([po])
        assert ok is False

    def test_zero_total_value_rejected(self):
        po = {**self.VALID_PO, "total_value": 0}
        ok, _ = validate_replenishment_output([po])
        assert ok is False

    def test_negative_total_value_rejected(self):
        po = {**self.VALID_PO, "total_value": -100}
        ok, _ = validate_replenishment_output([po])
        assert ok is False