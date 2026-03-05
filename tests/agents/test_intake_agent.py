"""
CONDUIT — Agent Tests: Intake Agent
=====================================
Tests validate_intake_output() — the guardrail function.
No LLM calls, no DB, fully deterministic.
"""

import pytest
from agents.intake_agent import validate_intake_output


# ── VALID OUTPUT ──────────────────────────────────────────────────────────────

VALID_BRAKE_OUTPUT = {
    "fault_classification": "BRAKE_SYSTEM",
    "required_parts":       ["BRK-PAD-HON-F-01"],
    "urgency":              "HIGH",
    "confidence":           0.92,
    "recall_flags":         [],
}

VALID_UNKNOWN_OUTPUT = {
    "fault_classification": "UNKNOWN",
    "required_parts":       [],
    "urgency":              "NEEDS_CLARIFICATION",
    "confidence":           0.30,
    "recall_flags":         [],
}


class TestValidateIntakeOutput:

    # ── HAPPY PATH ────────────────────────────────────────────────────────

    def test_valid_brake_output_passes(self):
        is_valid, reason = validate_intake_output(VALID_BRAKE_OUTPUT, "RO-001")
        assert is_valid is True
        assert reason == "OK"

    def test_valid_unknown_output_passes(self):
        """UNKNOWN fault with empty parts is a valid edge case."""
        is_valid, _ = validate_intake_output(VALID_UNKNOWN_OUTPUT, "RO-001")
        assert is_valid is True

    def test_all_fault_categories_accepted(self):
        """Every valid fault category should pass validation."""
        valid_faults = [
            "BRAKE_SYSTEM", "ROUTINE_SERVICE", "ELECTRICAL_SYSTEM",
            "SUSPENSION", "ENGINE", "EV_SYSTEM", "UNKNOWN"
        ]
        for fault in valid_faults:
            output = {**VALID_BRAKE_OUTPUT, "fault_classification": fault}
            # EV_SYSTEM and BRAKE_SYSTEM can't be LOW — use HIGH for those
            output["urgency"] = "MEDIUM"
            is_valid, reason = validate_intake_output(output, "RO-001")
            assert is_valid is True, f"Fault {fault} failed: {reason}"

    def test_all_urgency_levels_accepted(self):
        """Every valid urgency must be accepted."""
        for urgency in ["HIGH", "MEDIUM", "LOW", "NEEDS_CLARIFICATION"]:
            output = {
                **VALID_BRAKE_OUTPUT,
                "fault_classification": "ROUTINE_SERVICE",  # safe fault for LOW
                "urgency": urgency,
            }
            is_valid, _ = validate_intake_output(output, "RO-001")
            assert is_valid is True

    # ── MISSING FIELDS ────────────────────────────────────────────────────

    def test_missing_fault_classification_fails(self):
        bad = {k: v for k, v in VALID_BRAKE_OUTPUT.items()
               if k != "fault_classification"}
        is_valid, reason = validate_intake_output(bad, "RO-001")
        assert is_valid is False
        assert "fault_classification" in reason

    def test_missing_required_parts_fails(self):
        bad = {k: v for k, v in VALID_BRAKE_OUTPUT.items()
               if k != "required_parts"}
        is_valid, reason = validate_intake_output(bad, "RO-001")
        assert is_valid is False
        assert "required_parts" in reason

    def test_missing_urgency_fails(self):
        bad = {k: v for k, v in VALID_BRAKE_OUTPUT.items()
               if k != "urgency"}
        is_valid, reason = validate_intake_output(bad, "RO-001")
        assert is_valid is False
        assert "urgency" in reason

    def test_missing_confidence_fails(self):
        bad = {k: v for k, v in VALID_BRAKE_OUTPUT.items()
               if k != "confidence"}
        is_valid, reason = validate_intake_output(bad, "RO-001")
        assert is_valid is False
        assert "confidence" in reason

    # ── CONFIDENCE VALIDATION ─────────────────────────────────────────────

    def test_confidence_zero_passes(self):
        """0.0 confidence is valid — agent is very uncertain."""
        output = {**VALID_UNKNOWN_OUTPUT, "confidence": 0.0}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is True

    def test_confidence_one_passes(self):
        """1.0 confidence is valid — agent is certain."""
        output = {**VALID_BRAKE_OUTPUT, "confidence": 1.0}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is True

    def test_confidence_above_one_fails(self):
        output = {**VALID_BRAKE_OUTPUT, "confidence": 1.1}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "confidence" in reason.lower()

    def test_confidence_negative_fails(self):
        output = {**VALID_BRAKE_OUTPUT, "confidence": -0.1}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False

    def test_confidence_string_fails(self):
        """Confidence must be numeric, not string."""
        output = {**VALID_BRAKE_OUTPUT, "confidence": "high"}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is False

    # ── FAULT CATEGORY VALIDATION ─────────────────────────────────────────

    def test_invalid_fault_category_fails(self):
        output = {**VALID_BRAKE_OUTPUT, "fault_classification": "MADE_UP_FAULT"}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "MADE_UP_FAULT" in reason

    def test_lowercase_fault_fails(self):
        """Fault classification must be uppercase."""
        output = {**VALID_BRAKE_OUTPUT, "fault_classification": "brake_system"}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is False

    # ── URGENCY VALIDATION ────────────────────────────────────────────────

    def test_invalid_urgency_fails(self):
        output = {**VALID_BRAKE_OUTPUT, "urgency": "CRITICAL"}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "CRITICAL" in reason

    # ── SAFETY GUARDRAILS ─────────────────────────────────────────────────

    def test_brake_system_low_urgency_fails(self):
        """Safety rule: BRAKE_SYSTEM cannot be LOW urgency."""
        output = {**VALID_BRAKE_OUTPUT, "urgency": "LOW"}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "safety" in reason.lower() or "brake" in reason.lower()

    def test_ev_system_low_urgency_fails(self):
        """Safety rule: EV_SYSTEM cannot be LOW urgency."""
        output = {
            **VALID_BRAKE_OUTPUT,
            "fault_classification": "EV_SYSTEM",
            "urgency":              "LOW",
        }
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "EV" in reason or "safety" in reason.lower()

    def test_brake_system_high_urgency_passes(self):
        """BRAKE_SYSTEM with HIGH urgency is valid."""
        output = {**VALID_BRAKE_OUTPUT, "urgency": "HIGH"}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is True

    def test_engine_low_urgency_passes(self):
        """ENGINE fault can be LOW urgency — not a safety-critical override."""
        output = {
            **VALID_BRAKE_OUTPUT,
            "fault_classification": "ENGINE",
            "urgency":              "LOW",
        }
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is True

    # ── REQUIRED PARTS TYPE ───────────────────────────────────────────────

    def test_required_parts_must_be_list(self):
        output = {**VALID_BRAKE_OUTPUT, "required_parts": "BRK-PAD-HON-F-01"}
        is_valid, reason = validate_intake_output(output, "RO-001")
        assert is_valid is False
        assert "list" in reason.lower()

    def test_empty_parts_list_valid_for_unknown(self):
        """UNKNOWN fault with no parts is acceptable."""
        output = {**VALID_UNKNOWN_OUTPUT, "required_parts": []}
        is_valid, _ = validate_intake_output(output, "RO-001")
        assert is_valid is True