"""
CONDUIT — Component Eval: Intake Agent
========================================
Measures LLM classification quality against ground truth.

Metrics:
  - Fault classification accuracy     target: >= 80%
  - Urgency accuracy                  target: >= 90%
  - Confidence calibration            target: >= 75%
  - Parts prefix recall               target: >= 70%
  - Safety guardrails                 target: 100%
  - Vague complaint handling          target: 100%

Cost:  ~$0.20 (10 LLM calls)
Time:  ~2-3 minutes
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from evals.conftest import load_dataset, EvalResult, MOCK_RETRIEVED_PARTS

TARGET_CLASSIFICATION = 0.80
TARGET_URGENCY        = 0.90
TARGET_CONFIDENCE     = 0.75
TARGET_PARTS_RECALL   = 0.70


def classify(complaint: str, vehicle: dict) -> dict:
    """Calls classify_fault_with_llm with mock parts — no Pinecone needed."""
    from agents.intake_agent import classify_fault_with_llm
    return classify_fault_with_llm(
        complaint_text  = complaint,
        vehicle         = vehicle,
        retrieved_parts = MOCK_RETRIEVED_PARTS,
        recall_flags    = [],
    )


class TestFaultClassificationAccuracy:

    def test_accuracy_across_all_cases(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("Fault Classification Accuracy")

        for c in cases:
            exp = c["expected"]
            if "fault_classification" not in exp:
                continue
            result   = classify(c["complaint"], c["vehicle"])
            actual   = result.get("fault_classification", "ERROR")
            expected = exp["fault_classification"]
            tracker.record(c["case_id"], "fault_classification",
                           actual == expected, expected, actual, c["description"])

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_CLASSIFICATION, (
            f"Classification {s['pass_rate']}% < target {TARGET_CLASSIFICATION*100}%"
        )


class TestUrgencyAccuracy:

    def test_urgency_across_all_cases(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("Urgency Accuracy")

        for c in cases:
            exp            = c["expected"]
            expected_urg   = exp.get("urgency")
            urgency_not    = exp.get("urgency_not")
            if not expected_urg and not urgency_not:
                continue

            result = classify(c["complaint"], c["vehicle"])
            actual = result.get("urgency", "ERROR")

            if expected_urg:
                passed   = actual == expected_urg
                exp_str  = expected_urg
            else:
                passed   = actual != urgency_not
                exp_str  = f"not {urgency_not}"

            tracker.record(c["case_id"], "urgency", passed, exp_str, actual, c["description"])

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_URGENCY, (
            f"Urgency {s['pass_rate']}% < target {TARGET_URGENCY*100}%"
        )


class TestConfidenceCalibration:

    def test_clear_complaints_high_confidence(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("Confidence — Clear Complaints")

        for c in [x for x in cases if x["expected"].get("confidence_min")]:
            result   = classify(c["complaint"], c["vehicle"])
            actual   = result.get("confidence", 0)
            expected = c["expected"]["confidence_min"]
            tracker.record(c["case_id"], "confidence_min",
                           actual >= expected, f">= {expected}", round(actual, 2))

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_CONFIDENCE

    def test_vague_complaints_low_confidence(self):
        cases = load_dataset("intake_eval_cases.json")
        for c in [x for x in cases if x["expected"].get("confidence_max")]:
            result = classify(c["complaint"], c["vehicle"])
            actual = result.get("confidence", 1.0)
            limit  = c["expected"]["confidence_max"]
            assert actual <= limit, (
                f"{c['case_id']}: vague complaint confidence {actual} > max {limit}"
            )


class TestPartsIdentificationRecall:

    def test_parts_prefix_recall(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("Parts Prefix Recall")

        for c in [x for x in cases if x["expected"].get("parts_prefix")]:
            result   = classify(c["complaint"], c["vehicle"])
            found    = result.get("required_parts", [])
            prefixes = c["expected"]["parts_prefix"]

            hits   = [p for p in prefixes if any(p in part for part in found)]
            recall = len(hits) / len(prefixes) if prefixes else 1.0
            passed = recall >= TARGET_PARTS_RECALL

            tracker.record(c["case_id"], "parts_recall", passed,
                           f">= {TARGET_PARTS_RECALL} {prefixes}",
                           f"{recall:.2f} found={hits}", c["description"])

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= 0.70


class TestSafetyGuardrails:
    """Zero tolerance — must be 100%."""

    def test_ev_complaints_never_low_urgency(self):
        cases    = load_dataset("intake_eval_cases.json")
        ev_cases = [c for c in cases if c["vehicle"]["is_ev"]]
        for c in ev_cases:
            result  = classify(c["complaint"], c["vehicle"])
            urgency = result.get("urgency", "")
            assert urgency != "LOW", (
                f"{c['case_id']}: EV complaint got LOW urgency — safety violation"
            )

    def test_brake_complaints_never_low_urgency(self):
        cases = load_dataset("intake_eval_cases.json")
        brake = [c for c in cases if c["expected"].get("fault_classification") == "BRAKE_SYSTEM"]
        for c in brake:
            result = classify(c["complaint"], c["vehicle"])
            if result.get("fault_classification") == "BRAKE_SYSTEM":
                assert result.get("urgency") != "LOW", (
                    f"{c['case_id']}: Brake complaint got LOW urgency"
                )

    def test_ev_safety_protocol_set(self):
        cases = load_dataset("intake_eval_cases.json")
        ev    = [c for c in cases if c["expected"].get("ev_safety_protocol") is True]
        for c in ev:
            result = classify(c["complaint"], c["vehicle"])
            assert result.get("ev_safety_protocol") is True, (
                f"{c['case_id']}: EV job missing ev_safety_protocol=true"
            )


class TestVagueComplaintHandling:

    def test_vague_complaint_routes_to_unknown(self):
        cases = load_dataset("intake_eval_cases.json")
        vague = [c for c in cases if c["expected"].get("fault_classification") == "UNKNOWN"]
        for c in vague:
            result  = classify(c["complaint"], c["vehicle"])
            fault   = result.get("fault_classification")
            urgency = result.get("urgency")
            assert fault == "UNKNOWN" or urgency == "NEEDS_CLARIFICATION", (
                f"{c['case_id']}: '{c['complaint']}' classified as {fault}/{urgency}"
            )

    def test_vague_complaint_does_not_hallucinate_parts(self):
        cases = load_dataset("intake_eval_cases.json")
        vague = [c for c in cases if c["expected"].get("fault_classification") == "UNKNOWN"]
        for c in vague:
            result = classify(c["complaint"], c["vehicle"])
            parts  = result.get("required_parts", [])
            assert len(parts) <= 2, (
                f"{c['case_id']}: vague complaint hallucinated {len(parts)} parts: {parts}"
            )