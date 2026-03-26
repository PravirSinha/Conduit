"""
CONDUIT — Evals Shared conftest
=================================
Shared fixtures, result tracker, and dataset loader
used across all eval modules.
"""

import os
import sys
import json
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def load_dataset(filename: str) -> list:
    path = os.path.join(os.path.dirname(__file__), "datasets", filename)
    with open(path) as f:
        return json.load(f)


MOCK_RETRIEVED_PARTS = [
    {"part_number": "BRK-PAD-HON-F-01", "description": "Front disc brake pads Honda City",    "qty_on_hand": 5,  "stock_status": "healthy",  "sell_price": 4500},
    {"part_number": "BRK-ROT-HON-F-01", "description": "Front brake rotor Honda City",        "qty_on_hand": 3,  "stock_status": "healthy",  "sell_price": 6500},
    {"part_number": "FLT-OIL-UNI-01",   "description": "Universal engine oil filter",         "qty_on_hand": 20, "stock_status": "healthy",  "sell_price": 350},
    {"part_number": "BAT-12V-HON-01",   "description": "12V lead acid battery Honda",         "qty_on_hand": 3,  "stock_status": "low",       "sell_price": 8500},
    {"part_number": "SHK-ABS-HON-F-01", "description": "Front shock absorber Honda City",     "qty_on_hand": 4,  "stock_status": "healthy",  "sell_price": 12000},
    {"part_number": "SPK-PLG-HON-01",   "description": "Iridium spark plug Honda",            "qty_on_hand": 12, "stock_status": "healthy",  "sell_price": 850},
    {"part_number": "EV-BAT-TTA-NXN-01","description": "Tata Nexon EV high voltage battery", "qty_on_hand": 1,  "stock_status": "critical", "sell_price": 185000},
]


class EvalResult:
    def __init__(self, eval_name: str):
        self.eval_name = eval_name
        self.results   = []

    def _write_summary_metric(self, summary: dict) -> None:
        """Optionally persists summary metrics for the master runner.

        When `EVALS_METRICS_OUT` is set, each EvalResult will upsert its
        summary into that JSON file under the key `eval_name`.
        """
        metrics_path = os.getenv("EVALS_METRICS_OUT")
        if not metrics_path:
            return

        try:
            os.makedirs(os.path.dirname(metrics_path), exist_ok=True)

            existing = {}
            if os.path.exists(metrics_path):
                with open(metrics_path, "r") as f:
                    existing = json.load(f) or {}

            # Metadata can help debug stale snapshots.
            existing.setdefault("_meta", {})
            existing["_meta"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

            existing.setdefault("evals", {})
            existing["evals"][self.eval_name] = summary

            with open(metrics_path, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            # Never fail an eval due to metrics export.
            return

    def record(self, case_id, metric, passed, expected, actual, notes=""):
        self.results.append({
            "case_id": case_id, "metric": metric, "passed": passed,
            "expected": str(expected), "actual": str(actual), "notes": notes,
        })

    def summary(self) -> dict:
        total  = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        return {
            "eval": self.eval_name, "total": total, "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
        }

    def print_report(self) -> dict:
        s = self.summary()
        print(f"\n{'='*65}")
        print(f"EVAL: {s['eval']}")
        print(f"{'='*65}")
        print(f"{'Case':<12} {'Metric':<30} {'Result':<8} Notes")
        print(f"{'-'*65}")
        for r in self.results:
            status = "✓ PASS" if r["passed"] else "✗ FAIL"
            notes  = f"expected={r['expected']} got={r['actual']}" if not r["passed"] else r["notes"]
            print(f"{r['case_id']:<12} {r['metric']:<30} {status:<8} {notes}")
        print(f"{'-'*65}")
        print(f"RESULT: {s['passed']}/{s['total']} ({s['pass_rate']}%)")
        print(f"{'='*65}\n")

        self._write_summary_metric(s)
        return s


@pytest.fixture(scope="session")
def intake_cases():    return load_dataset("intake_eval_cases.json")

@pytest.fixture(scope="session")
def quoting_cases():   return load_dataset("quoting_eval_cases.json")

@pytest.fixture(scope="session")
def inventory_cases(): return load_dataset("inventory_eval_cases.json")

@pytest.fixture(scope="session")
def pipeline_cases():  return load_dataset("pipeline_eval_cases.json")

@pytest.fixture(scope="session")
def mock_parts():      return MOCK_RETRIEVED_PARTS