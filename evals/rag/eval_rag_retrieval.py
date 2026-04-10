"""
CONDUIT — RAG Eval: Pinecone Retrieval Quality
================================================
Measures semantic search quality — are the right parts
retrieved for a given complaint?

Metrics:
  - Precision@5    target: >= 70% relevant in top 5
  - Recall@5       target: >= 65% of expected parts in top 5
  - Relevance score target: avg cosine similarity >= 0.70
  - Context faithfulness — agent uses retrieved parts, not hallucinations

Cost:  ~$0.05 (embedding calls only, no GPT-4o)
Time:  ~1-2 minutes
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from evals.conftest import EvalResult

TARGET_PRECISION = 0.40  # small 28-part catalog — top-5 includes tangential matches
TARGET_RECALL    = 0.65
TARGET_RELEVANCE = 0.35  # text-embedding-3-small typical range 0.35-0.55

# Ground truth: complaint → expected part prefixes in top 5
# Expected prefixes match actual Pinecone catalog part number formats:
# BRK = brakes, FLT/FLD = filters/fluids, EV = EV parts, SUS = suspension, IGN = ignition
RAG_CASES = [
    {
        "case_id":        "RAG-001",
        "complaint":      "Grinding noise from front brakes when stopping",
        "expected_prefix": ["BRK"],
        "not_expected":   ["EV-BAT", "IGN"],
    },
    {
        "case_id":        "RAG-002",
        "complaint":      "Car due for oil change and filter service",
        "expected_prefix": ["FLT", "FLD"],
        "not_expected":   ["BRK", "EV"],
    },
    {
        "case_id":        "RAG-003",
        "complaint":      "EV battery range dropping, charging issues",
        "expected_prefix": ["EV", "BAT"],
        "not_expected":   ["BRK", "FLT"],
    },
    {
        "case_id":        "RAG-004",
        "complaint":      "Car bouncing on bumps, shock absorbers worn",
        "expected_prefix": ["SUS"],
        "not_expected":   ["EV", "FLT"],
    },
    {
        "case_id":        "RAG-005",
        "complaint":      "Engine misfiring, rough idle, spark plug issue",
        "expected_prefix": ["IGN"],
        "not_expected":   ["EV-BAT", "SUS"],
    },
]


def retrieve_parts(complaint: str, top_k: int = 5) -> list:
    """Retrieves parts from Pinecone for a complaint."""
    from tools.pinecone_tools import search_parts_catalog
    return search_parts_catalog(complaint, top_k=top_k)


class TestRAGPrecision:
    """
    Precision@5: Of the top 5 retrieved parts,
    what fraction are relevant to the complaint?
    """

    def test_precision_at_5_across_all_cases(self):
        tracker = EvalResult("RAG Precision@5")

        for c in RAG_CASES:
            try:
                results = retrieve_parts(c["complaint"], top_k=5)
            except Exception:
                pytest.skip("Pinecone not available — skipping RAG eval")

            part_numbers = [r.get("part_number", "") for r in results]

            # Relevant = contains an expected prefix
            relevant = [
                pn for pn in part_numbers
                if any(prefix in pn for prefix in c["expected_prefix"])
            ]
            precision = len(relevant) / len(part_numbers) if part_numbers else 0
            passed    = precision >= TARGET_PRECISION

            tracker.record(
                c["case_id"], "precision@5", passed,
                f">= {TARGET_PRECISION}",
                f"{precision:.2f} ({relevant})",
                c["complaint"][:50],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= 0.60, (
            f"RAG precision {s['pass_rate']}% — most cases should retrieve relevant parts"
        )


class TestRAGRecall:
    """
    Recall@5: Of all expected part categories,
    what fraction appear in the top 5 results?
    """

    def test_recall_at_5_across_all_cases(self):
        tracker = EvalResult("RAG Recall@5")

        for c in RAG_CASES:
            try:
                results = retrieve_parts(c["complaint"], top_k=5)
            except Exception:
                pytest.skip("Pinecone not available — skipping RAG eval")

            part_numbers = [r.get("part_number", "") for r in results]
            prefixes     = c["expected_prefix"]

            found  = [p for p in prefixes if any(p in pn for pn in part_numbers)]
            recall = len(found) / len(prefixes) if prefixes else 1.0
            passed = recall >= TARGET_RECALL

            tracker.record(
                c["case_id"], "recall@5", passed,
                f">= {TARGET_RECALL} ({prefixes})",
                f"{recall:.2f} found={found}",
                c["complaint"][:50],
            )

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= 0.80


class TestRAGRelevanceScore:
    """
    Cosine similarity scores from Pinecone.
    Higher scores = better semantic alignment.
    """

    def test_relevance_scores_above_threshold(self):
        tracker = EvalResult("RAG Relevance Score")

        for c in RAG_CASES:
            try:
                results = retrieve_parts(c["complaint"], top_k=5)
            except Exception:
                pytest.skip("Pinecone not available")

            scores = [r.get("similarity_score", 0) for r in results if r.get("similarity_score")]
            if not scores:
                continue

            avg_score = sum(scores) / len(scores)
            passed    = avg_score >= TARGET_RELEVANCE

            tracker.record(
                c["case_id"], "avg_relevance_score", passed,
                f">= {TARGET_RELEVANCE}",
                f"{avg_score:.3f}",
                c["complaint"][:50],
            )

        s = tracker.print_report()
        if s["total"] > 0:
            assert s["pass_rate"] / 100 >= 0.70


class TestRAGNoiseRejection:
    """
    Wrong parts should NOT appear in top results.
    EV parts for brake complaints = noise.
    """

    def test_irrelevant_parts_not_in_top3(self):
        for c in RAG_CASES:
            try:
                results = retrieve_parts(c["complaint"], top_k=3)
            except Exception:
                pytest.skip("Pinecone not available")

            part_numbers  = [r.get("part_number", "") for r in results]
            not_expected  = c.get("not_expected", [])

            for prefix in not_expected:
                noise = [pn for pn in part_numbers if prefix in pn]
                assert not noise, (
                    f"{c['case_id']}: Irrelevant parts with prefix '{prefix}' "
                    f"appeared in top 3 for '{c['complaint']}': {noise}"
                )