"""
CONDUIT — Master Eval Runner
==============================
Runs all evals in order, prints consolidated report,
and saves JSON results to evals/reports/latest/.

Usage:
    python evals/run_evals.py                    # full suite (~$1.00)
    python evals/run_evals.py --free             # no LLM, $0.00
    python evals/run_evals.py --no-pipeline      # skip expensive pipeline evals
    python evals/run_evals.py --rag-only         # Pinecone only (~$0.05)
    python evals/run_evals.py --intake-only      # intake LLM only (~$0.20)

Cost summary:
    guardrails/     $0.00   deterministic
    component/      $0.20   intake LLM calls only
    rag/            $0.05   embeddings only
    pipeline/       $0.80   5 full pipeline runs
    ─────────────────────
    Total:          ~$1.05
"""

import os, sys, time, json, argparse, subprocess, hashlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EVALS_DIR   = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(EVALS_DIR, "reports", "latest")

ALL_MODULES = [
    # (rel_path,                                  label,                         cost)
    ("guardrails/intake_guardrails.py",    "Intake Guardrails",           "$0.00"),
    ("guardrails/quoting_guardrails.py",   "Quoting Guardrails",          "$0.00"),
    ("guardrails/output_validator.py",     "Output Validators",           "$0.00"),
    ("component/eval_inventory_agent.py",  "Inventory Agent",             "$0.00"),
    ("component/eval_quoting_agent.py",    "Quoting Agent",               "$0.00"),
    ("component/eval_transaction_agent.py","Transaction Agent",           "$0.00"),
    ("component/eval_replenishment_agent.py","Replenishment Agent",       "$0.00"),
    ("component/eval_intake_agent.py",     "Intake Agent (LLM)",          "~$0.20"),
    ("rag/eval_rag_retrieval.py",          "RAG Retrieval (Pinecone)",    "~$0.05"),
    ("component/eval_llm_judge.py",        "LLM-as-Judge (Diagnosis)",   "~$0.05"),
    ("pipeline/eval_full_pipeline.py",     "Full Pipeline (end-to-end)", "~$0.80"),
]


def _safe_env(key: str) -> str | None:
    val = os.getenv(key)
    return val if val else None


def _get_git_sha() -> str | None:
    """Best-effort git SHA resolution (works in CI; fails open in Docker images without .git)."""
    for k in ("GIT_SHA", "GITHUB_SHA", "VERCEL_GIT_COMMIT_SHA"):
        v = _safe_env(k)
        if v:
            return v

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        sha = (proc.stdout or "").strip()
        return sha or None
    except Exception:
        return None


def _hash_files(file_paths: list[str]) -> str | None:
    """SHA256 hash of (relative_path + content) for stable dataset/version fingerprints."""
    if not file_paths:
        return None
    h = hashlib.sha256()
    for rel_path in sorted(set(file_paths)):
        h.update(rel_path.replace("\\", "/").encode("utf-8"))
        h.update(b"\n")
        try:
            with open(rel_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
        except Exception:
            # Fail-open: include filename but skip unreadable content.
            continue
        h.update(b"\n")
    return h.hexdigest()


def _datasets_fingerprint() -> dict:
    datasets_dir = os.path.join(EVALS_DIR, "datasets")
    dataset_files: list[str] = []

    if os.path.isdir(datasets_dir):
        for root, _, files in os.walk(datasets_dir):
            for fn in files:
                if fn.lower().endswith(".json"):
                    dataset_files.append(os.path.join(root, fn))

    digest = _hash_files(dataset_files)
    return {
        "datasets_dir": "evals/datasets",
        "datasets_files": [os.path.relpath(p, EVALS_DIR).replace("\\", "/") for p in sorted(dataset_files)],
        "datasets_files_count": len(dataset_files),
        "datasets_hash_sha256": digest,
    }


def run_module(rel_path: str, label: str, cost: str) -> dict:
    full_path = os.path.join(EVALS_DIR, rel_path)
    print(f"\n{'─'*65}")
    print(f"Running: {label}  ({cost})")
    print(f"{'─'*65}")

    start  = time.time()
    proc   = subprocess.run(
        [sys.executable, "-m", "pytest", full_path,
         "-v", "-s", "--tb=short", "--no-header", "-q",
         f"--junitxml={REPORTS_DIR}/{rel_path.replace('/', '_').replace('.py', '.xml')}"],
        text=True,
    )
    elapsed = time.time() - start

    return {
        "label":      label,
        "module":     rel_path,
        "cost":       cost,
        "passed":     proc.returncode == 0,
        "elapsed_s":  round(elapsed, 1),
        "returncode": proc.returncode,
    }


def save_summary(results: list, total_elapsed: float):
    """
    Saves JSON summary to two locations:
      1. evals/reports/latest/summary.json  — gitignored, always fresh
      2. docs/eval_results.json             — git tracked, read by Streamlit dashboard

    Both are written on every run so the dashboard always reflects
    the latest results without any manual cp step.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Load any per-eval metric summaries (written by EvalResult).
    metrics = {}
    metrics_path = os.path.join(REPORTS_DIR, "metrics.json")
    try:
        if os.path.exists(metrics_path):
            with open(metrics_path, "r") as f:
                metrics = json.load(f) or {}
    except Exception:
        metrics = {}

    eval_metrics = (metrics or {}).get("evals", {})

    system_pass_rate = round(
        (sum(1 for r in results if r["passed"]) / len(results) * 100) if results else 0,
        0,
    )
    intake_accuracy = eval_metrics.get("Fault Classification Accuracy", {}).get("pass_rate")
    rag_recall_at_5 = eval_metrics.get("RAG Recall@5", {}).get("pass_rate")

    headline_metrics = [
        {
            "id": "system_pass_rate",
            "label": "System Pass Rate",
            "value": system_pass_rate,
            "unit": "%",
        },
        {
            "id": "intake_classification_accuracy",
            "label": "Intake Accuracy",
            "value": intake_accuracy,
            "unit": "%",
        },
        {
            "id": "rag_recall_at_5",
            "label": "RAG Recall@5",
            "value": rag_recall_at_5,
            "unit": "%",
        },
    ]

    git_sha = _get_git_sha()
    meta = {
        "git_sha": git_sha,
        "git_sha_short": (git_sha[:7] if git_sha else None),
        "openai_model": os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
        **_datasets_fingerprint(),
    }

    summary = {
        "run_at":        datetime.utcnow().isoformat() + "Z",
        "total_elapsed": round(total_elapsed, 1),
        "all_passed":    all(r["passed"] for r in results),
        "passed":        sum(1 for r in results if r["passed"]),
        "failed":        sum(1 for r in results if not r["passed"]),
        "total":         len(results),
        "meta":          meta,
        "headline_metrics": headline_metrics,
        "eval_metrics": eval_metrics,
        "modules":       results,
    }

    # ── Write 1: gitignored reports folder ────────────────────────────────
    summary_path = os.path.join(REPORTS_DIR, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nReport saved → evals/reports/latest/summary.json")

    # ── Write 2: docs/eval_results.json (git tracked) ─────────────────────
    # This is what the Streamlit dashboard reads on AWS.
    # Auto-copied here so you never need to run cp manually.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir     = os.path.join(project_root, "docs")
    docs_path    = os.path.join(docs_dir, "eval_results.json")

    try:
        os.makedirs(docs_dir, exist_ok=True)
        with open(docs_path, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Snapshot saved  → docs/eval_results.json  (commit this to update dashboard)")
    except Exception as e:
        print(f"Warning: could not write docs/eval_results.json — {e}")

    return summary


def print_report(results: list, total_elapsed: float) -> bool:
    print(f"\n{'='*65}")
    print("CONDUIT — EVAL SUITE REPORT")
    print(f"Run at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*65}")

    all_passed = all(r["passed"] for r in results)

    for r in results:
        icon   = "✓" if r["passed"] else "✗"
        status = "PASSED" if r["passed"] else "FAILED"
        print(f"  {icon}  {r['label']:<42} {r['cost']:<8} {r['elapsed_s']}s  {status}")

    print(f"{'─'*65}")
    passed = sum(1 for r in results if r["passed"])
    print(f"  {passed}/{len(results)} modules passed   Total time: {total_elapsed:.1f}s")

    if all_passed:
        print("\n  ✓ ALL EVALS PASSED — system is production ready")
    else:
        failed = [r["label"] for r in results if not r["passed"]]
        print(f"\n  ✗ FAILED: {', '.join(failed)}")
        print("  Fix all failures before deploying to production")

    print(f"{'='*65}\n")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="CONDUIT Eval Runner")
    parser.add_argument("--free",        action="store_true", help="$0.00 evals only")
    parser.add_argument("--no-pipeline", action="store_true", help="Skip pipeline evals")
    parser.add_argument("--rag-only",    action="store_true", help="RAG eval only")
    parser.add_argument("--intake-only", action="store_true", help="Intake eval only")
    args = parser.parse_args()

    if args.free:
        modules = [m for m in ALL_MODULES if m[2] == "$0.00"]
    elif args.no_pipeline:
        modules = [m for m in ALL_MODULES if "pipeline" not in m[0]]
    elif args.rag_only:
        modules = [m for m in ALL_MODULES if "rag" in m[0]]
    elif args.intake_only:
        modules = [m for m in ALL_MODULES if "intake" in m[0]]
    else:
        modules = ALL_MODULES

    est_cost = round(sum(
        float(m[2].replace("~$", "").replace("$", ""))
        for m in modules
    ), 2)

    print(f"\n{'='*65}")
    print("CONDUIT — EVAL SUITE")
    print(f"Modules: {len(modules)}   Estimated cost: ~${est_cost}")
    print(f"{'='*65}")

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Make per-eval metric summaries available to the master runner.
    metrics_path = os.path.join(REPORTS_DIR, "metrics.json")
    try:
        if os.path.exists(metrics_path):
            os.remove(metrics_path)
    except Exception:
        pass
    os.environ["EVALS_METRICS_OUT"] = metrics_path

    suite_start = time.time()
    results     = []

    for rel_path, label, cost in modules:
        r = run_module(rel_path, label, cost)
        results.append(r)

        # Stop on pipeline failure to save API costs
        if not r["passed"] and "pipeline" in rel_path:
            print("\n⚠  Pipeline eval failed — stopping to save API costs")
            break

    total_elapsed = time.time() - suite_start
    all_passed    = print_report(results, total_elapsed)
    save_summary(results, total_elapsed)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()