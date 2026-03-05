"""
CONDUIT — Unit Tests: Pricing Tools
=====================================
Tests for calculate_totals(), calculate_discount(),
requires_approval(), build_parts_line_items().

All fully deterministic — no DB, no LLM, no Pinecone.
"""

import pytest
from tools.pricing_tools import (
    calculate_totals,
    calculate_discount,
    requires_approval,
    build_parts_line_items,
    build_labor_line_items,
    GST_RATE,
    MAX_DISCOUNT,
    AUTO_APPROVE_THRESHOLD,
)


# ── calculate_totals ──────────────────────────────────────────────────────────

class TestCalculateTotals:

    def test_basic_totals_no_discount(self, sample_line_items):
        """Subtotal sums correctly, GST at 18%, no discount."""
        result = calculate_totals(sample_line_items, discount_rate=0.0)

        assert result["subtotal"]        == 12800.0
        assert result["discount_amount"] == 0.0
        assert result["gst_amount"]      == round(12800.0 * GST_RATE, 2)
        assert result["total_amount"]    == round(12800.0 * (1 + GST_RATE), 2)

    def test_totals_with_10_percent_discount(self, sample_line_items):
        """10% discount applied before GST."""
        result = calculate_totals(sample_line_items, discount_rate=0.10)

        assert result["discount_amount"] == round(12800.0 * 0.10, 2)
        post_discount = 12800.0 - result["discount_amount"]
        assert result["gst_amount"]   == round(post_discount * GST_RATE, 2)
        assert result["total_amount"] == round(post_discount * (1 + GST_RATE), 2)

    def test_totals_with_recall_full_discount(self, sample_line_items):
        """Recall = 100% discount → customer pays zero."""
        result = calculate_totals(sample_line_items, discount_rate=1.0)

        assert result["discount_amount"] == 12800.0
        assert result["post_discount"]   == 0.0
        assert result["gst_amount"]      == 0.0
        assert result["total_amount"]    == 0.0

    def test_totals_with_max_discount_cap(self, sample_line_items):
        """MAX_DISCOUNT is 30% — totals should reflect that."""
        result = calculate_totals(sample_line_items, discount_rate=MAX_DISCOUNT)

        assert result["discount_rate"]   == MAX_DISCOUNT
        assert result["discount_amount"] == round(12800.0 * MAX_DISCOUNT, 2)

    def test_single_line_item(self):
        """Works correctly with a single line item."""
        items  = [{"subtotal": 5000.0}]
        result = calculate_totals(items, discount_rate=0.0)

        assert result["subtotal"]     == 5000.0
        assert result["gst_amount"]   == round(5000.0 * GST_RATE, 2)
        assert result["total_amount"] == round(5000.0 * 1.18, 2)

    def test_empty_line_items(self):
        """Empty line items returns all zeros."""
        result = calculate_totals([], discount_rate=0.0)

        assert result["subtotal"]     == 0.0
        assert result["total_amount"] == 0.0

    def test_gst_rate_is_18_percent(self, sample_line_items):
        """GST rate must always be 18% — regulatory requirement."""
        result = calculate_totals(sample_line_items, discount_rate=0.0)
        assert result["gst_rate"] == 0.18

    def test_totals_are_rounded_to_2dp(self, sample_line_items):
        """All money values should be rounded to 2 decimal places."""
        result = calculate_totals(sample_line_items, discount_rate=0.07)

        for key in ["subtotal", "discount_amount", "gst_amount", "total_amount"]:
            val = result[key]
            assert round(val, 2) == val, f"{key} not rounded to 2dp: {val}"


# ── calculate_discount ────────────────────────────────────────────────────────

class TestCalculateDiscount:

    def test_recall_always_full_discount(self, loyalty_customer):
        """Recall overrides everything — even gold tier customer."""
        rate, reason = calculate_discount(
            subtotal               = 10000.0,
            customer_details       = loyalty_customer,
            fault_classification   = "BRAKE_SYSTEM",
            recall_action_required = True,
        )
        assert rate   == 1.0
        assert "recall" in reason.lower()

    def test_gold_tier_gets_10_percent(self, loyalty_customer):
        """Gold loyalty customer gets 10% discount."""
        rate, reason = calculate_discount(
            subtotal               = 10000.0,
            customer_details       = loyalty_customer,
            fault_classification   = "BRAKE_SYSTEM",
            recall_action_required = False,
        )
        assert rate == 0.10
        assert "Gold" in reason

    def test_new_customer_no_discount(self, new_customer):
        """New customer with no loyalty gets 0% discount."""
        rate, reason = calculate_discount(
            subtotal               = 10000.0,
            customer_details       = new_customer,
            fault_classification   = "BRAKE_SYSTEM",
            recall_action_required = False,
        )
        assert rate == 0.0

    def test_no_customer_no_discount(self):
        """None customer_details returns 0% discount."""
        rate, reason = calculate_discount(
            subtotal               = 10000.0,
            customer_details       = None,
            fault_classification   = "ENGINE",
            recall_action_required = False,
        )
        assert rate == 0.0

    def test_discount_never_exceeds_max_cap(self):
        """Discount cannot exceed MAX_DISCOUNT (30%) regardless of tier."""
        high_discount_customer = {
            "loyalty_tier":      5,
            "loyalty_tier_name": "Platinum",
            "discount_rate":     0.50,  # 50% — but cap is 30%
        }
        rate, _ = calculate_discount(
            subtotal               = 50000.0,
            customer_details       = high_discount_customer,
            fault_classification   = "ENGINE",
            recall_action_required = False,
        )
        assert rate <= MAX_DISCOUNT

    def test_recall_takes_priority_over_loyalty(self, loyalty_customer):
        """Recall discount (100%) beats loyalty discount (10%)."""
        rate, _ = calculate_discount(
            subtotal               = 5000.0,
            customer_details       = loyalty_customer,
            fault_classification   = "ENGINE",
            recall_action_required = True,
        )
        assert rate == 1.0


# ── requires_approval ─────────────────────────────────────────────────────────

class TestRequiresApproval:

    def test_small_quote_auto_approved(self):
        """Quote under threshold, non-EV → auto approved."""
        needs, reason = requires_approval(
            total_amount = 10000.0,
            is_ev_job    = False,
        )
        assert needs is False

    def test_large_quote_needs_approval(self):
        """Quote above AUTO_APPROVE_THRESHOLD needs human approval."""
        needs, reason = requires_approval(
            total_amount = AUTO_APPROVE_THRESHOLD + 1,
            is_ev_job    = False,
        )
        assert needs is True
        assert "threshold" in reason.lower()

    def test_ev_job_always_needs_approval(self):
        """EV jobs always require approval regardless of amount."""
        needs, reason = requires_approval(
            total_amount = 100.0,     # tiny amount
            is_ev_job    = True,
        )
        assert needs is True
        assert "EV" in reason

    def test_ev_job_above_threshold_needs_approval(self):
        """EV job above threshold — still needs approval (EV flag dominant)."""
        needs, reason = requires_approval(
            total_amount = AUTO_APPROVE_THRESHOLD + 10000,
            is_ev_job    = True,
        )
        assert needs is True

    def test_exact_threshold_auto_approved(self):
        """Quote exactly at threshold is auto-approved (> not >=)."""
        needs, _ = requires_approval(
            total_amount = AUTO_APPROVE_THRESHOLD,
            is_ev_job    = False,
        )
        assert needs is False

    def test_one_rupee_above_threshold_needs_approval(self):
        """One rupee above threshold triggers approval."""
        needs, _ = requires_approval(
            total_amount = AUTO_APPROVE_THRESHOLD + 0.01,
            is_ev_job    = False,
        )
        assert needs is True


# ── build_parts_line_items ────────────────────────────────────────────────────

class TestBuildPartsLineItems:

    def test_oem_line_item_uses_full_price(self, oem_brake_part):
        """OEM line item uses sell_price directly."""
        items = build_parts_line_items([oem_brake_part], use_oem=True)

        assert len(items)              == 1
        assert items[0]["unit_price"]  == 4500.0
        assert items[0]["is_oem"]      is True
        assert items[0]["part_number"] == "BRK-PAD-HON-F-01"

    def test_aftermarket_line_item_is_discounted(self, oem_brake_part):
        """Aftermarket uses 72% of sell_price (28% cheaper)."""
        items = build_parts_line_items([oem_brake_part], use_oem=False)

        expected_price = round(4500.0 * 0.72, 2)
        assert items[0]["unit_price"] == expected_price
        assert items[0]["is_oem"]     is False

    def test_aftermarket_cheaper_than_oem(self, oem_brake_part):
        """Aftermarket must always be cheaper than OEM."""
        # Ensure qty_reserved is set explicitly — don't rely on fixture default
        part = {**oem_brake_part, "qty_reserved": 1}
        oem_items = build_parts_line_items([part], use_oem=True)
        am_items  = build_parts_line_items([part], use_oem=False)

        assert am_items[0]["subtotal"] < oem_items[0]["subtotal"]

    def test_empty_parts_returns_empty_list(self):
        """No reserved parts → empty line items."""
        items = build_parts_line_items([], use_oem=True)
        assert items == []

    def test_subtotal_is_unit_price_times_qty(self, oem_brake_part):
        """subtotal = unit_price × qty_reserved."""
        part = {**oem_brake_part, "qty_reserved": 2}   # copy — never mutate fixture
        items = build_parts_line_items([part], use_oem=True)

        assert items[0]["subtotal"] == items[0]["unit_price"] * 2