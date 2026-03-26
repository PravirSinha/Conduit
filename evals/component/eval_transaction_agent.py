"""
CONDUIT — Component Eval: Transaction Agent
=============================================
Tests HITL trigger logic — when to pause for human approval.

IMPORTANT: should_pause_for_human() returns False when
TRANSACTION_HITL_ENABLED=false (portfolio/CV mode). Tests are written
to respect this — we test the LOGIC by temporarily enabling
HITL, not by assuming the env var is set.

Cost: $0.00 — deterministic logic, no LLM calls.
"""
import sys, os
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.transaction_agent import should_pause_for_human
from evals.conftest import EvalResult


BASE_STATE = {
    "is_ev_job":             False,
    "quote":                 {"total_amount": 15000.0},
    "intake_confidence":     0.90,
    "recall_action_required": False,
    "fault_classification":  "BRAKE_SYSTEM",
}

# All HITL tests patch TRANSACTION_HITL_ENABLED=True so we test the logic,
# not the env var value. The env var behaviour is tested separately.


class TestHITLTriggerLogic:
    """
    Tests the HITL trigger CONDITIONS — patching TRANSACTION_HITL_ENABLED=True
    so we evaluate the logic regardless of .env setting.
    """

    def test_ev_job_always_pauses(self):
        state = {**BASE_STATE, "is_ev_job": True}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_high_value_pauses(self):
        state = {**BASE_STATE, "quote": {"total_amount": 75000.0}}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_low_confidence_pauses(self):
        state = {**BASE_STATE, "intake_confidence": 0.50}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_recall_job_pauses(self):
        state = {**BASE_STATE, "recall_action_required": True}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_routine_job_auto_approved(self):
        state = {
            **BASE_STATE,
            "is_ev_job":              False,
            "quote":                  {"total_amount": 5000.0},
            "intake_confidence":      0.92,
            "recall_action_required": False,
        }
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is False

    def test_ev_job_pauses_regardless_of_low_value(self):
        """EV always pauses — even for cheap jobs."""
        state = {**BASE_STATE, "is_ev_job": True, "quote": {"total_amount": 500.0}}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_high_value_ev_pauses(self):
        """EV + high value — double trigger, still True."""
        state = {**BASE_STATE, "is_ev_job": True, "quote": {"total_amount": 200000.0}}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_confidence_at_boundary_69pct_pauses(self):
        """Below 70% confidence threshold — must pause."""
        state = {**BASE_STATE, "intake_confidence": 0.69}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_confidence_at_boundary_70pct_passes(self):
        """At exactly 70% — should NOT pause."""
        state = {**BASE_STATE, "intake_confidence": 0.70}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is False


class TestHITLTriggerCombinations:

    def test_ev_plus_recall_pauses(self):
        state = {**BASE_STATE, "is_ev_job": True, "recall_action_required": True}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_low_confidence_plus_high_value_pauses(self):
        state = {**BASE_STATE, "intake_confidence": 0.40, "quote": {"total_amount": 80000.0}}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is True

    def test_all_triggers_clear_auto_approves(self):
        from config import AUTO_APPROVE_THRESHOLD
        state = {
            "is_ev_job":              False,
            "quote":                  {"total_amount": AUTO_APPROVE_THRESHOLD - 1},
            "intake_confidence":      0.95,
            "recall_action_required": False,
            "fault_classification":   "ROUTINE_SERVICE",
        }
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", True):
            assert should_pause_for_human(state) is False


class TestHITLDisabledBehaviour:
    """
    When TRANSACTION_HITL_ENABLED=false (portfolio mode),
    should_pause_for_human() must ALWAYS return False
    regardless of job type — this enables the instant pipeline.
    """

    def test_hitl_disabled_ev_job_returns_false(self):
        state = {**BASE_STATE, "is_ev_job": True}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", False):
            assert should_pause_for_human(state) is False

    def test_hitl_disabled_high_value_returns_false(self):
        state = {**BASE_STATE, "quote": {"total_amount": 999999.0}}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", False):
            assert should_pause_for_human(state) is False

    def test_hitl_disabled_recall_returns_false(self):
        state = {**BASE_STATE, "recall_action_required": True}
        with patch("agents.transaction_agent.TRANSACTION_HITL_ENABLED", False):
            assert should_pause_for_human(state) is False