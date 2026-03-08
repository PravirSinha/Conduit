"""
CONDUIT — Component Eval: Quoting Agent
=========================================
Tests pricing accuracy, GST calculations, and discount logic
against known ground truth cases.
Cost: $0.00 — quoting logic is deterministic.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from evals.conftest import load_dataset, EvalResult

GST_RATE     = 0.18
MAX_DISCOUNT = 0.30
TOLERANCE    = 1.0    # ₹1 rounding tolerance


class TestGSTAccuracy:
    """GST must be exactly 18% of post-discount amount. Zero tolerance."""

    def test_gst_correct_for_all_amounts(self):
        from tools.pricing_tools import calculate_totals

        amounts  = [1000.0, 4500.0, 11000.0, 28500.0, 185000.0]
        tracker  = EvalResult("GST Calculation Accuracy")

        for amount in amounts:
            items  = [{"subtotal": amount}]
            result = calculate_totals(items, discount_rate=0.0)

            expected_gst = round(amount * GST_RATE, 2)
            actual_gst   = result.get("gst_amount", 0)
            passed       = abs(actual_gst - expected_gst) <= TOLERANCE

            tracker.record(
                f"AMT-{int(amount)}", "gst_amount", passed,
                expected_gst, actual_gst
            )

        s = tracker.print_report()
        assert s["pass_rate"] == 100.0, "GST must be 100% accurate — regulatory"

    def test_gst_applied_after_discount(self):
        """GST on post-discount, not pre-discount subtotal."""
        from tools.pricing_tools import calculate_totals

        items  = [{"subtotal": 10000.0}]
        result = calculate_totals(items, discount_rate=0.10)

        expected_gst = round(9000.0 * GST_RATE, 2)   # 18% of 9000, not 10000
        actual_gst   = result.get("gst_amount", 0)
        assert abs(actual_gst - expected_gst) <= TOLERANCE, (
            f"GST {actual_gst} calculated on pre-discount amount — should be {expected_gst}"
        )


class TestDiscountAccuracy:

    def test_discount_rates_applied_correctly(self):
        from tools.pricing_tools import calculate_totals

        cases = [
            (10000.0, 0.05,  9500.0),
            (10000.0, 0.10, 9000.0),
            (10000.0, 0.20, 8000.0),
            (10000.0, 0.30, 7000.0),   # max discount
        ]
        for subtotal, rate, expected_post in cases:
            items  = [{"subtotal": subtotal}]
            result = calculate_totals(items, discount_rate=rate)
            actual = result.get("post_discount", 0)
            assert abs(actual - expected_post) <= TOLERANCE, (
                f"Discount {rate:.0%}: expected post={expected_post}, got {actual}"
            )

    def test_discount_cap_enforced(self):
        """No discount above 30% — customer loyalty cannot override."""
        from tools.pricing_tools import calculate_discount, MAX_DISCOUNT

        extreme = {"loyalty_tier_name": "Platinum", "discount_rate": 0.99}
        rate, _ = calculate_discount(
            subtotal               = 50000.0,
            customer_details       = extreme,
            fault_classification   = "ENGINE",
            recall_action_required = False,
        )
        assert rate <= MAX_DISCOUNT, (
            f"Discount {rate:.0%} exceeded MAX_DISCOUNT {MAX_DISCOUNT:.0%}"
        )

    def test_recall_overrides_loyalty_discount(self):
        """Recall jobs get 100% discount regardless of loyalty tier."""
        from tools.pricing_tools import calculate_discount

        customer = {"loyalty_tier_name": "Gold", "discount_rate": 0.10}
        rate, _ = calculate_discount(
            subtotal               = 10000.0,
            customer_details       = customer,
            fault_classification   = "BRAKE_SYSTEM",
            recall_action_required = True,
        )
        assert rate == 1.0, f"Recall job discount was {rate:.0%}, expected 100%"


class TestOEMvsAftemarketPricing:

    def test_aftermarket_always_cheaper_than_oem(self):
        from tools.pricing_tools import build_parts_line_items

        parts = [
            {"part_number": "BRK-PAD-HON-F-01", "description": "Brake pads",
             "sell_price": 4500.0, "qty_reserved": 1},
            {"part_number": "SHK-ABS-HON-F-01", "description": "Shock absorber",
             "sell_price": 12000.0, "qty_reserved": 2},
        ]
        for part in parts:
            oem = build_parts_line_items([part], use_oem=True)[0]["unit_price"]
            am  = build_parts_line_items([part], use_oem=False)[0]["unit_price"]
            assert am < oem, (
                f"Aftermarket {am} >= OEM {oem} for {part['part_number']}"
            )

    def test_aftermarket_is_72pct_of_oem(self):
        from tools.pricing_tools import build_parts_line_items

        part = {"part_number": "BRK-PAD-HON-F-01", "description": "Brake pads",
                "sell_price": 4500.0, "qty_reserved": 1}
        oem = build_parts_line_items([part], use_oem=True)[0]["unit_price"]
        am  = build_parts_line_items([part], use_oem=False)[0]["unit_price"]
        ratio = am / oem
        assert abs(ratio - 0.72) <= 0.01, (
            f"Aftermarket ratio {ratio:.2f} ≠ expected 0.72"
        )


class TestQuotingDatasetCases:
    """Run all ground truth quoting cases from dataset."""

    def test_all_quoting_cases(self):
        from tools.pricing_tools import calculate_totals, calculate_discount

        cases   = load_dataset("quoting_eval_cases.json")
        tracker = EvalResult("Quoting Dataset Accuracy")

        for c in cases:
            exp = c["expected"]

            # Build subtotal from reserved parts
            subtotal = sum(
                p["sell_price"] * p.get("qty_reserved", 1)
                for p in c["reserved_parts"]
            )

            # Get discount
            rate, _ = calculate_discount(
                subtotal               = subtotal,
                customer_details       = c.get("customer"),
                fault_classification   = "BRAKE_SYSTEM",
                recall_action_required = c.get("recall", False),
            )

            # Calculate totals
            items  = [{"subtotal": subtotal}]
            result = calculate_totals(items, discount_rate=rate)

            # Check expected fields
            if "gst_amount" in exp:
                passed = abs(result["gst_amount"] - exp["gst_amount"]) <= TOLERANCE
                tracker.record(c["case_id"], "gst_amount", passed,
                               exp["gst_amount"], result["gst_amount"])

            if "total_amount" in exp:
                passed = abs(result["total_amount"] - exp["total_amount"]) <= TOLERANCE
                tracker.record(c["case_id"], "total_amount", passed,
                               exp["total_amount"], result["total_amount"])

        s = tracker.print_report()
        assert s["pass_rate"] / 100 >= 0.90