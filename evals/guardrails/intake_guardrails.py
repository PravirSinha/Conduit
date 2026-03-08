"""
CONDUIT — Guardrail Evals: Intake Agent
=========================================
Zero-tolerance tests on validate_intake_output().
Every invalid agent output must be blocked before DB write.
Cost: $0.00 — no LLM calls.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.intake_agent import validate_intake_output

VALID = {
    "fault_classification": "BRAKE_SYSTEM",
    "required_parts":       ["BRK-PAD-HON-F-01"],
    "urgency":              "HIGH",
    "confidence":           0.92,
}

ALLOWED_FAULTS   = ["BRAKE_SYSTEM","ROUTINE_SERVICE","ELECTRICAL_SYSTEM","SUSPENSION","ENGINE","EV_SYSTEM","UNKNOWN"]
ALLOWED_URGENCY  = ["HIGH","MEDIUM","LOW","NEEDS_CLARIFICATION"]


class TestIntakeGuardrailFieldValidation:
    """Every missing or malformed field must be caught."""

    def test_missing_fault_classification(self):
        out = {k: v for k, v in VALID.items() if k != "fault_classification"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False
        assert "fault_classification" in reason

    def test_missing_urgency(self):
        out = {k: v for k, v in VALID.items() if k != "urgency"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False
        assert "urgency" in reason

    def test_missing_confidence(self):
        out = {k: v for k, v in VALID.items() if k != "confidence"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False

    def test_missing_required_parts(self):
        out = {k: v for k, v in VALID.items() if k != "required_parts"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False
        assert "required_parts" in reason

    def test_invalid_fault_category_rejected(self):
        for bad in ["TRANSMISSION", "COOLING", "brake_system", "", None, 999]:
            out = {**VALID, "fault_classification": bad}
            ok, _ = validate_intake_output(out, "EVAL-001")
            assert ok is False, f"Invalid fault '{bad}' was not rejected"

    def test_all_valid_fault_categories_pass(self):
        for fault in ALLOWED_FAULTS:
            urgency = "HIGH" if fault in ["BRAKE_SYSTEM","EV_SYSTEM"] else "MEDIUM"
            out = {**VALID, "fault_classification": fault, "urgency": urgency}
            ok, reason = validate_intake_output(out, "EVAL-001")
            assert ok is True, f"Valid fault '{fault}' was rejected: {reason}"

    def test_confidence_above_1_rejected(self):
        for bad in [1.1, 2.0, 10, 99]:
            out = {**VALID, "confidence": bad}
            ok, _ = validate_intake_output(out, "EVAL-001")
            assert ok is False, f"Confidence {bad} was not rejected"

    def test_confidence_below_0_rejected(self):
        for bad in [-0.1, -1, -99]:
            out = {**VALID, "confidence": bad}
            ok, _ = validate_intake_output(out, "EVAL-001")
            assert ok is False, f"Confidence {bad} was not rejected"

    def test_confidence_string_rejected(self):
        out = {**VALID, "confidence": "high"}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is False

    def test_confidence_boundary_0_passes(self):
        out = {**VALID, "fault_classification": "UNKNOWN", "urgency": "NEEDS_CLARIFICATION", "confidence": 0.0}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True

    def test_confidence_boundary_1_passes(self):
        out = {**VALID, "confidence": 1.0}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True


class TestIntakeSafetyGuardrails:
    """Zero tolerance — safety overrides must block 100% of violations."""

    def test_brake_system_low_urgency_blocked(self):
        out = {**VALID, "fault_classification": "BRAKE_SYSTEM", "urgency": "LOW"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False
        assert any(w in reason.lower() for w in ["safety","brake","urgency"])

    def test_ev_system_low_urgency_blocked(self):
        out = {**VALID, "fault_classification": "EV_SYSTEM", "urgency": "LOW"}
        ok, reason = validate_intake_output(out, "EVAL-001")
        assert ok is False

    def test_brake_system_high_urgency_passes(self):
        out = {**VALID, "fault_classification": "BRAKE_SYSTEM", "urgency": "HIGH"}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True

    def test_brake_system_medium_urgency_passes(self):
        out = {**VALID, "fault_classification": "BRAKE_SYSTEM", "urgency": "MEDIUM"}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True

    def test_ev_system_high_urgency_passes(self):
        out = {**VALID, "fault_classification": "EV_SYSTEM", "urgency": "HIGH"}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True

    def test_non_safety_fault_low_urgency_passes(self):
        """ROUTINE_SERVICE can legitimately be LOW urgency."""
        out = {**VALID, "fault_classification": "ROUTINE_SERVICE", "urgency": "LOW"}
        ok, _ = validate_intake_output(out, "EVAL-001")
        assert ok is True

    def test_valid_intake_output_passes(self):
        ok, reason = validate_intake_output(VALID, "EVAL-001")
        assert ok is True, f"Valid output was rejected: {reason}"