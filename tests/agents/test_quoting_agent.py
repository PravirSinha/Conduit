"""
CONDUIT — Agent Tests: Quoting Agent
======================================
Tests validate_quote_output() — financial accuracy guardrail.
This is critical: wrong quotes = revenue leakage or angry customers.
"""

import pytest
from agents.quoting_agent import validate_quote_output

GST_RATE = 0.18


def make_valid_quote(
    subtotal=12800.0,
    discount_rate=0.0,
    discount_amount=0.0,
    post_discount=None,
    gst_amount=None,
    total_amount=None,
    line_items=None,
):
    """Helper — builds a mathematically correct quote dict."""
    if post_discount is None:
        post_discount = subtotal - discount_amount
    if gst_amount is None:
        gst_amount = round(post_discount * GST_RATE, 2)
    if total_amount is None:
        total_amount = round(post_discount + gst_amount, 2)
    if line_items is None:
        line_items = [
            {"type": "PART",  "description": "Brake pads",  "subtotal": 4500.0},
            {"type": "PART",  "description": "Brake rotor", "subtotal": 6500.0},
            {"type": "LABOR", "description": "Labor",       "subtotal": 1800.0},
        ]
    return {
        "subtotal":        subtotal,
        "discount_rate":   discount_rate,
        "discount_amount": discount_amount,
        "post_discount":   post_discount,
        "gst_rate":        GST_RATE,
        "gst_amount":      gst_amount,
        "total_amount":    total_amount,
        "line_items":      line_items,
    }


class TestValidateQuoteOutput:

    # ── HAPPY PATH ────────────────────────────────────────────────────────

    def test_valid_quote_passes(self):
        quote = make_valid_quote()
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is True
        assert reason == "OK"

    def test_valid_quote_with_discount_passes(self):
        discount_amount = round(12800.0 * 0.10, 2)
        quote = make_valid_quote(
            discount_rate   = 0.10,
            discount_amount = discount_amount,
        )
        is_valid, _ = validate_quote_output(quote, "RO-001")
        assert is_valid is True

    def test_valid_quote_with_recall_discount_passes(self):
        """
        Recall discount makes parts free but the quote total itself
        is still validated as > 0 by the validator (labor charges remain).
        A fully zero quote is technically rejected by the total > 0 check —
        this is correct behaviour: recall covers parts, not labor.
        We test a recall quote with labor charges remaining.
        """
        labor_subtotal  = 1800.0
        post_discount   = labor_subtotal   # parts are free, labor remains
        gst_amount      = round(post_discount * GST_RATE, 2)
        total_amount    = round(post_discount + gst_amount, 2)

        quote = {
            "subtotal":        labor_subtotal,
            "discount_rate":   0.30,          # max non-recall cap — within rules
            "discount_amount": 0.0,
            "post_discount":   post_discount,
            "gst_rate":        GST_RATE,
            "gst_amount":      gst_amount,
            "total_amount":    total_amount,
            "recall_action_required": True,
            "line_items": [
                {"type": "LABOR", "description": "Brake job labor", "subtotal": labor_subtotal},
            ],
        }
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is True

    # ── TOTAL VALIDATION ──────────────────────────────────────────────────

    def test_zero_total_fails(self):
        """Zero total (without recall) is invalid — something went wrong."""
        quote = make_valid_quote(total_amount=0.0)
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "total" in reason.lower()

    def test_negative_total_fails(self):
        quote = make_valid_quote(total_amount=-100.0)
        is_valid, _ = validate_quote_output(quote, "RO-001")
        assert is_valid is False

    def test_string_total_fails(self):
        quote = make_valid_quote()
        quote["total_amount"] = "15104"
        is_valid, _ = validate_quote_output(quote, "RO-001")
        assert is_valid is False

    # ── LINE ITEMS VALIDATION ─────────────────────────────────────────────

    def test_empty_line_items_fails(self):
        """Quote with no line items is invalid."""
        quote = make_valid_quote(line_items=[])
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "line" in reason.lower()

    def test_line_item_missing_type_fails(self):
        bad_items = [{"description": "Brake pads", "subtotal": 4500.0}]
        quote = make_valid_quote(
            subtotal    = 4500.0,
            line_items  = bad_items,
            post_discount = 4500.0,
            gst_amount  = round(4500.0 * 0.18, 2),
            total_amount = round(4500.0 * 1.18, 2),
        )
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "type" in reason

    def test_line_item_missing_subtotal_fails(self):
        bad_items = [{"type": "PART", "description": "Brake pads"}]
        quote = make_valid_quote(line_items=bad_items, total_amount=5310.0)
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "subtotal" in reason

    # ── MATH VALIDATION ───────────────────────────────────────────────────

    def test_subtotal_mismatch_fails(self):
        """stated subtotal ≠ sum of line items → arithmetic error."""
        quote = make_valid_quote()
        quote["subtotal"] = 99999.0  # wrong
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "mismatch" in reason.lower() or "arithmetic" in reason.lower()

    def test_gst_mismatch_fails(self):
        """GST not 18% of post-discount → calculation error."""
        quote = make_valid_quote()
        quote["gst_amount"] = 999.0  # wrong GST
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "GST" in reason or "gst" in reason.lower()

    def test_correct_gst_calculation(self):
        """GST exactly 18% of post-discount passes."""
        post_discount = 12800.0
        quote = make_valid_quote(
            post_discount = post_discount,
            gst_amount    = round(post_discount * 0.18, 2),
            total_amount  = round(post_discount * 1.18, 2),
        )
        is_valid, _ = validate_quote_output(quote, "RO-001")
        assert is_valid is True

    # ── DISCOUNT VALIDATION ───────────────────────────────────────────────

    def test_discount_above_30_percent_fails(self):
        """Discount > 30% without recall is not allowed."""
        discount_amount = round(12800.0 * 0.35, 2)
        post_discount   = 12800.0 - discount_amount
        quote = make_valid_quote(
            discount_rate   = 0.35,
            discount_amount = discount_amount,
            post_discount   = post_discount,
            gst_amount      = round(post_discount * 0.18, 2),
            total_amount    = round(post_discount * 1.18, 2),
        )
        is_valid, reason = validate_quote_output(quote, "RO-001")
        assert is_valid is False
        assert "30%" in reason or "discount" in reason.lower()

    def test_30_percent_discount_passes(self):
        """Exactly 30% discount is the maximum allowed."""
        discount_amount = round(12800.0 * 0.30, 2)
        post_discount   = 12800.0 - discount_amount
        quote = make_valid_quote(
            discount_rate   = 0.30,
            discount_amount = discount_amount,
            post_discount   = post_discount,
            gst_amount      = round(post_discount * 0.18, 2),
            total_amount    = round(post_discount * 1.18, 2),
        )
        is_valid, _ = validate_quote_output(quote, "RO-001")
        assert is_valid is True