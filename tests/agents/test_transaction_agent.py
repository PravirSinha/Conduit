"""
CONDUIT — Agent Tests: Transaction Agent
==========================================
Tests should_pause_for_human() and validate_transaction_output().
"""

import pytest
from unittest.mock import patch


class TestShouldPauseForHuman:
    """
    Tests the HITL trigger logic.
    We patch HITL_ENABLED=True to test the real branching logic.
    """

    def _run(self, state):
        from agents.transaction_agent import should_pause_for_human
        return should_pause_for_human(state)

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_ev_job_always_pauses(self):
        state = {"is_ev_job": True, "quote": {"total_amount": 1000.0},
                 "intake_confidence": 0.95, "recall_action_required": False}
        assert self._run(state) is True

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_high_value_quote_pauses(self):
        state = {"is_ev_job": False, "quote": {"total_amount": 99999.0},
                 "intake_confidence": 0.95, "recall_action_required": False}
        assert self._run(state) is True

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_low_confidence_pauses(self):
        state = {"is_ev_job": False, "quote": {"total_amount": 5000.0},
                 "intake_confidence": 0.55, "recall_action_required": False}
        assert self._run(state) is True

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_recall_job_pauses(self):
        state = {"is_ev_job": False, "quote": {"total_amount": 5000.0},
                 "intake_confidence": 0.95, "recall_action_required": True}
        assert self._run(state) is True

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_routine_job_auto_approved(self):
        """Normal job under threshold — no pause needed."""
        state = {"is_ev_job": False, "quote": {"total_amount": 10000.0},
                 "intake_confidence": 0.92, "recall_action_required": False}
        assert self._run(state) is False

    @patch("agents.transaction_agent.HITL_ENABLED", False)
    def test_hitl_disabled_never_pauses(self):
        """When HITL_ENABLED=False, nothing ever pauses."""
        state = {"is_ev_job": True, "quote": {"total_amount": 999999.0},
                 "intake_confidence": 0.10, "recall_action_required": True}
        assert self._run(state) is False

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_confidence_exactly_70_no_pause(self):
        """Confidence at exactly 0.70 is NOT below threshold."""
        state = {"is_ev_job": False, "quote": {"total_amount": 5000.0},
                 "intake_confidence": 0.70, "recall_action_required": False}
        assert self._run(state) is False

    @patch("agents.transaction_agent.HITL_ENABLED", True)
    def test_confidence_just_below_70_pauses(self):
        """Confidence at 0.69 IS below threshold — must pause."""
        state = {"is_ev_job": False, "quote": {"total_amount": 5000.0},
                 "intake_confidence": 0.69, "recall_action_required": False}
        assert self._run(state) is True


class TestValidateTransactionOutput:
    """
    validate_transaction_output checks PRE-CONDITIONS before processing:
      1. quote_id must exist
      2. reserved_parts must exist (unless ROUTINE_SERVICE)
      3. quote total must be > 0
    It does NOT validate transaction_status — that's set after processing.
    """

    def _run(self, state):
        from agents.transaction_agent import validate_transaction_output
        return validate_transaction_output(state)

    VALID_STATE = {
        "quote_id":             "QT-TEST-001",
        "reserved_parts":       [{"part_number": "BRK-PAD-01", "qty_reserved": 1}],
        "fault_classification": "BRAKE_SYSTEM",
        "quote":                {"total_amount": 15000.0},
    }

    def test_valid_state_passes(self):
        is_valid, reason = self._run(self.VALID_STATE)
        assert is_valid is True
        assert reason == "OK"

    def test_missing_quote_id_fails(self):
        state = {**self.VALID_STATE, "quote_id": None}
        is_valid, reason = self._run(state)
        assert is_valid is False
        assert "quote_id" in reason.lower()

    def test_no_reserved_parts_non_routine_fails(self):
        """Non-routine job with no reserved parts → invalid."""
        state = {
            **self.VALID_STATE,
            "reserved_parts":       [],
            "fault_classification": "BRAKE_SYSTEM",
        }
        is_valid, reason = self._run(state)
        assert is_valid is False
        assert "reserved" in reason.lower() or "parts" in reason.lower()

    def test_routine_service_no_parts_passes(self):
        """ROUTINE_SERVICE can have no reserved parts — labor only job."""
        state = {
            **self.VALID_STATE,
            "reserved_parts":       [],
            "fault_classification": "ROUTINE_SERVICE",
        }
        is_valid, _ = self._run(state)
        assert is_valid is True

    def test_zero_quote_total_fails(self):
        state = {**self.VALID_STATE, "quote": {"total_amount": 0}}
        is_valid, reason = self._run(state)
        assert is_valid is False
        assert "total" in reason.lower()

    def test_valid_state_returns_ok(self):
        is_valid, reason = self._run(self.VALID_STATE)
        assert reason == "OK"