"""
CONDUIT — LLM-as-Judge Eval: Intake Response Quality
======================================================
Uses GPT-4o as an evaluator to assess the QUALITY of the
Intake Agent's free-text outputs — fault_description and notes.

Why LLM-as-judge here (not for classification):
  - fault_classification / urgency → exact match against ground truth is correct
  - fault_description / notes     → free text, needs semantic evaluation

Metrics:
  - Diagnosis Relevance     : is fault_description relevant to the complaint?
  - Hallucination Check     : does it mention parts/issues NOT in the complaint or catalog?
  - Technician Clarity      : would a technician understand what to do?

Cost:  ~$0.05 (10 judge calls, judge prompt is short)
Time:  ~1-2 minutes
"""
import sys, os, pytest, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from evals.conftest import load_dataset, EvalResult, MOCK_RETRIEVED_PARTS

TARGET_RELEVANCE    = 0.80
TARGET_NO_HALLUCIN  = 0.90
TARGET_CLARITY      = 0.80


def classify(complaint: str, vehicle: dict) -> dict:
    from agents.intake_agent import classify_fault_with_llm
    return classify_fault_with_llm(
        complaint_text  = complaint,
        vehicle         = vehicle,
        retrieved_parts = MOCK_RETRIEVED_PARTS,
        recall_flags    = [],
    )


def llm_judge(complaint: str, vehicle_str: str, fault_description: str, notes: str,
              retrieved_parts_context: str) -> dict:
    """
    Calls GPT-4o as a judge to evaluate the quality of the intake response.
    Returns scores for relevance, hallucination, clarity (each True/False).
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    judge_prompt = f"""You are an expert automotive quality evaluator.
A service advisor AI produced a diagnosis for a vehicle complaint.
Evaluate the quality of the AI's response on three criteria.

ORIGINAL COMPLAINT: "{complaint}"
VEHICLE: {vehicle_str}
AVAILABLE PARTS FROM CATALOG:
{retrieved_parts_context}

AI PRODUCED:
- Fault Description: "{fault_description}"
- Technician Notes: "{notes}"

Respond ONLY with valid JSON:
{{
    "relevance_pass": true/false,
    "relevance_reason": "one sentence",
    "hallucination_pass": true/false,
    "hallucination_reason": "one sentence",
    "clarity_pass": true/false,
    "clarity_reason": "one sentence"
}}

Criteria:
- relevance_pass: true if fault_description directly addresses the complaint
- hallucination_pass: true if response only mentions issues/parts consistent with complaint and catalog
- clarity_pass: true if a technician would clearly understand what to inspect/fix"""

    try:
        response = client.chat.completions.create(
            model           = os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
            messages        = [{"role": "user", "content": judge_prompt}],
            response_format = {"type": "json_object"},
            temperature     = 0.0,
            max_tokens      = 200,
            timeout         = 20,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "relevance_pass": False, "relevance_reason": str(e),
            "hallucination_pass": False, "hallucination_reason": str(e),
            "clarity_pass": False, "clarity_reason": str(e),
        }


class TestDiagnosisRelevance:
    """
    LLM-as-judge: Is the fault_description relevant to the original complaint?
    """

    def test_diagnosis_relevance(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("LLM Judge: Diagnosis Relevance")

        parts_ctx = "\n".join([f"- {p['part_number']}: {p['description']}" for p in MOCK_RETRIEVED_PARTS])

        for c in cases:
            result = classify(c["complaint"], c["vehicle"])
            fault_desc = result.get("fault_description", "")
            notes      = result.get("notes", "")

            if not fault_desc:
                tracker.record(c["case_id"], "relevance", False,
                               "non-empty fault_description", "empty", c["description"])
                continue

            vehicle_str = f"{c['vehicle']['make']} {c['vehicle']['model']} {c['vehicle']['year']}"
            judgment    = llm_judge(c["complaint"], vehicle_str, fault_desc, notes, parts_ctx)

            tracker.record(
                c["case_id"], "relevance",
                judgment.get("relevance_pass", False),
                "relevant to complaint",
                f"{fault_desc[:60]}... | {judgment.get('relevance_reason','')}",
                c["description"],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_RELEVANCE, (
            f"Diagnosis relevance {s['pass_rate']}% < target {TARGET_RELEVANCE*100}%"
        )


class TestHallucinationCheck:
    """
    LLM-as-judge: Does the response hallucinate parts or issues
    not grounded in the complaint or parts catalog?
    """

    def test_no_hallucination(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("LLM Judge: Hallucination Check")

        parts_ctx = "\n".join([f"- {p['part_number']}: {p['description']}" for p in MOCK_RETRIEVED_PARTS])

        for c in cases:
            result     = classify(c["complaint"], c["vehicle"])
            fault_desc = result.get("fault_description", "")
            notes      = result.get("notes", "")
            vehicle_str = f"{c['vehicle']['make']} {c['vehicle']['model']} {c['vehicle']['year']}"
            judgment    = llm_judge(c["complaint"], vehicle_str, fault_desc, notes, parts_ctx)

            tracker.record(
                c["case_id"], "hallucination_check",
                judgment.get("hallucination_pass", False),
                "no hallucinated content",
                judgment.get("hallucination_reason", ""),
                c["description"],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_NO_HALLUCIN, (
            f"Hallucination check {s['pass_rate']}% < target {TARGET_NO_HALLUCIN*100}%"
        )


class TestTechnicianClarity:
    """
    LLM-as-judge: Would a technician clearly understand what to inspect?
    """

    def test_technician_clarity(self):
        cases   = load_dataset("intake_eval_cases.json")
        tracker = EvalResult("LLM Judge: Technician Clarity")

        parts_ctx = "\n".join([f"- {p['part_number']}: {p['description']}" for p in MOCK_RETRIEVED_PARTS])

        for c in cases:
            result      = classify(c["complaint"], c["vehicle"])
            fault_desc  = result.get("fault_description", "")
            notes       = result.get("notes", "")
            vehicle_str = f"{c['vehicle']['make']} {c['vehicle']['model']} {c['vehicle']['year']}"
            judgment    = llm_judge(c["complaint"], vehicle_str, fault_desc, notes, parts_ctx)

            tracker.record(
                c["case_id"], "clarity",
                judgment.get("clarity_pass", False),
                "clear for technician",
                judgment.get("clarity_reason", ""),
                c["description"],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= TARGET_CLARITY, (
            f"Technician clarity {s['pass_rate']}% < target {TARGET_CLARITY*100}%"
        )
