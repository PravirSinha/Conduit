"""
CONDUIT — Full Pipeline Eval
==============================
End-to-end pipeline quality:
  - Success rate          target: >= 80%
  - State completeness    target: all required fields present
  - Financial accuracy    target: 100% GST correct
  - Latency               target: < 60 seconds
  - HITL trigger accuracy target: correct for EV and routine jobs

Cost:  ~$0.80 (5 full pipeline runs)
Time:  ~5-10 minutes
"""
import sys, os, time, uuid, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from evals.conftest import load_dataset, EvalResult

TARGET_SUCCESS_RATE  = 0.80
TARGET_MAX_LATENCY_S = 60
GST_RATE             = 0.18
GST_TOLERANCE        = 1.0


def run_pipeline_case(case: dict):
    """
    Creates a temporary RO in DB, runs pipeline, returns (state, elapsed_s).
    Cleans up RO after eval.
    """
    from database.connection import get_session
    from database.models import RepairOrder, Vehicle
    from orchestrator import run_pipeline

    ro_id = f"EVAL-{str(uuid.uuid4())[:8].upper()}"

    with get_session() as db:
        vehicle = db.query(Vehicle).filter(Vehicle.vin == case["vin"]).first()
        if not vehicle:
            return None, 0

        ro = RepairOrder(
            ro_id          = ro_id,
            vin            = case["vin"],
            complaint_text = case["complaint"],
            status         = "PENDING_INSPECTION",
        )
        db.add(ro)
        db.commit()

    start  = time.time()
    result = run_pipeline(
        ro_id          = ro_id,
        vin            = case["vin"],
        complaint_text = case["complaint"],
        customer_id    = case.get("customer_id"),
    )
    elapsed = time.time() - start

    # Clean up eval RO
    with get_session() as db:
        ro = db.query(RepairOrder).filter(RepairOrder.ro_id == ro_id).first()
        if ro:
            ro.status = "CANCELLED"
            db.commit()

    return result, elapsed


class TestPipelineSuccessRate:

    def test_success_rate_across_all_cases(self):
        cases   = load_dataset("pipeline_eval_cases.json")
        tracker = EvalResult("Pipeline Success Rate")

        for c in cases:
            result, elapsed = run_pipeline_case(c)

            if result is None:
                tracker.record(c["case_id"], "pipeline_success", False,
                               "completed", "VIN not in DB", c["description"])
                continue

            error  = result.get("error")
            passed = (error is None) if not c["expect_error"] else (error is not None)

            tracker.record(
                c["case_id"], "pipeline_success", passed,
                "no error" if not c["expect_error"] else "error expected",
                f"error={error}" if error else f"ok in {elapsed:.1f}s",
                c["description"],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_SUCCESS_RATE


class TestStateCompleteness:

    REQUIRED_FIELDS = [
        "ro_id", "vin", "complaint_text",
        "fault_classification", "urgency", "intake_confidence",
        "required_parts", "reserved_parts", "current_agent",
    ]

    def test_successful_run_has_complete_state(self):
        cases  = load_dataset("pipeline_eval_cases.json")
        case   = cases[0]   # PIPE-001 — simplest, most likely to succeed
        result, _ = run_pipeline_case(case)

        if result is None or result.get("error"):
            pytest.skip("Pipeline failed — skipping state completeness check")

        missing = [f for f in self.REQUIRED_FIELDS if result.get(f) is None]
        assert not missing, f"Pipeline state missing: {missing}"


class TestFinancialAccuracy:

    def test_gst_is_18_percent_in_final_quote(self):
        cases   = load_dataset("pipeline_eval_cases.json")
        tracker = EvalResult("Pipeline GST Accuracy")

        for c in cases[:3]:   # first 3 — enough coverage, saves cost
            result, _ = run_pipeline_case(c)
            if not result or result.get("error"):
                continue

            quote = result.get("quote", {})
            if not quote or not quote.get("total_amount"):
                continue

            post_disc = quote.get("post_discount", 0)
            stated    = quote.get("gst_amount", 0)
            expected  = round(post_disc * GST_RATE, 2)
            passed    = abs(stated - expected) <= GST_TOLERANCE

            tracker.record(
                c["case_id"], "gst_accuracy", passed,
                f"18% of {post_disc} = {expected}", stated, c["description"]
            )

        s = tracker.print_report()
        if s["total"] > 0:
            assert s["pass_rate"] == 100.0, "GST must be 100% accurate"

    def test_quote_arithmetic_correct(self):
        cases  = load_dataset("pipeline_eval_cases.json")
        case   = cases[0]
        result, _ = run_pipeline_case(case)

        if not result or result.get("error"):
            pytest.skip("Pipeline failed")

        quote = result.get("quote", {})
        if not quote or not quote.get("total_amount"):
            pytest.skip("No quote generated")

        post_disc = quote.get("post_discount", 0)
        gst       = quote.get("gst_amount", 0)
        total     = quote.get("total_amount", 0)
        expected  = round(post_disc + gst, 2)

        assert abs(total - expected) <= GST_TOLERANCE, (
            f"Quote arithmetic wrong: {post_disc} + {gst} = {expected}, "
            f"but total_amount = {total}"
        )


class TestPipelineLatency:

    def test_pipeline_under_60_seconds(self):
        cases   = load_dataset("pipeline_eval_cases.json")
        result, elapsed = run_pipeline_case(cases[0])

        print(f"\nPipeline latency: {elapsed:.2f}s (target < {TARGET_MAX_LATENCY_S}s)")

        if result and not result.get("error"):
            assert elapsed <= TARGET_MAX_LATENCY_S, (
                f"Pipeline took {elapsed:.1f}s — exceeds {TARGET_MAX_LATENCY_S}s target"
            )

    def test_record_baseline_latency_per_case(self):
        """Records latency for each case — printed as baseline, not hard assert."""
        cases   = load_dataset("pipeline_eval_cases.json")
        tracker = EvalResult("Pipeline Latency Baseline")

        for c in cases:
            result, elapsed = run_pipeline_case(c)
            passed = elapsed <= TARGET_MAX_LATENCY_S if result else False

            tracker.record(
                c["case_id"], "latency_seconds", passed,
                f"< {TARGET_MAX_LATENCY_S}s", f"{elapsed:.1f}s", c["description"]
            )

        tracker.print_report()
        # No assertion — this is a baseline record for LangSmith comparison


class TestHITLTriggerAccuracy:

    def test_ev_job_triggers_hitl_when_enabled(self):
        from config import HITL_ENABLED
        if not HITL_ENABLED:
            pytest.skip("HITL_ENABLED=false")

        cases    = load_dataset("pipeline_eval_cases.json")
        ev_case  = next((c for c in cases if c.get("expected_fault") == "EV_SYSTEM"), None)
        if not ev_case:
            pytest.skip("No EV case in dataset")

        result, _ = run_pipeline_case(ev_case)
        if result is None:
            pytest.skip("EV VIN not in DB")

        assert result.get("hitl_triggered") is True, (
            "EV job did not trigger HITL — all EV jobs require human approval"
        )

    def test_routine_job_does_not_trigger_hitl(self):
        from config import HITL_ENABLED, AUTO_APPROVE_THRESHOLD
        if not HITL_ENABLED:
            pytest.skip("HITL_ENABLED=false")

        cases        = load_dataset("pipeline_eval_cases.json")
        routine_case = next((c for c in cases if not c.get("expect_hitl")), None)
        if not routine_case:
            pytest.skip("No routine case in dataset")

        result, _ = run_pipeline_case(routine_case)
        if not result or result.get("error"):
            pytest.skip("Pipeline failed")

        total = result.get("quote", {}).get("total_amount", 0)
        if total <= AUTO_APPROVE_THRESHOLD:
            assert result.get("hitl_triggered") is False, (
                f"Routine job (₹{total:,.0f}) triggered HITL unnecessarily"
            )