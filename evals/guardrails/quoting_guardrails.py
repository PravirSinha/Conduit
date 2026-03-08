"""
CONDUIT — Guardrail Evals: Quoting Agent
==========================================
Tests validate_quote_output() — financial accuracy guardrails.
GST must be 18%, totals must add up, discounts must be capped.
Cost: $0.00 — no LLM calls.
"""
import sys, os, pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.quoting_agent import validate_quote_output

GST_RATE    = 0.18
MAX_DISCOUNT = 0.30

def make_quote(subtotal=12800.0, discount_rate=0.0, **overrides):
    discount_amount = round(subtotal * discount_rate, 2)
    post_discount   = round(subtotal - discount_amount, 2)
    gst_amount      = round(post_discount * GST_RATE, 2)
    total_amount    = round(post_discount + gst_amount, 2)
    q = {
        "subtotal":        subtotal,
        "discount_rate":   discount_rate,
        "discount_amount": discount_amount,
        "post_discount":   post_discount,
        "gst_rate":        GST_RATE,
        "gst_amount":      gst_amount,
        "total_amount":    total_amount,
        "recall_action_required": False,
        "line_items": [
            {"type": "PART",  "description": "Brake pads",  "subtotal": 4500.0},
            {"type": "PART",  "description": "Brake rotor", "subtotal": 6500.0},
            {"type": "LABOR", "description": "Labor",       "subtotal": 1800.0},
        ],
    }
    q.update(overrides)
    return q


class TestQuoteValidGuardrail:

    def test_correct_quote_passes(self):
        ok, reason = validate_quote_output(make_quote(), "EVAL-001")
        assert ok is True, f"Valid quote rejected: {reason}"

    def test_quote_with_loyalty_discount_passes(self):
        ok, reason = validate_quote_output(make_quote(discount_rate=0.10), "EVAL-001")
        assert ok is True, f"Valid discounted quote rejected: {reason}"

    def test_quote_at_max_discount_passes(self):
        ok, reason = validate_quote_output(make_quote(discount_rate=0.30), "EVAL-001")
        assert ok is True, f"Quote at max discount rejected: {reason}"


class TestGSTGuardrail:
    """GST must be exactly 18% of post-discount — regulatory requirement."""

    def test_gst_wrong_rate_rejected(self):
        q = make_quote()
        q["gst_amount"] = 1000.0     # wrong — should be 2304.0
        ok, reason = validate_quote_output(q, "EVAL-001")
        assert ok is False
        assert "gst" in reason.lower() or "GST" in reason

    def test_gst_zero_rejected(self):
        q = make_quote()
        q["gst_amount"] = 0.0
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False

    def test_gst_on_post_discount_not_pre(self):
        """GST must be on post-discount amount — not original subtotal."""
        q = make_quote(discount_rate=0.10)
        # Apply GST incorrectly on pre-discount subtotal
        q["gst_amount"] = round(12800.0 * GST_RATE, 2)
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False


class TestDiscountGuardrail:

    def test_discount_above_30pct_rejected(self):
        q = make_quote(discount_rate=0.40)
        ok, reason = validate_quote_output(q, "EVAL-001")
        assert ok is False
        assert "discount" in reason.lower() or "30" in reason

    def test_discount_50pct_rejected(self):
        q = make_quote(discount_rate=0.50)
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False


class TestArithmeticGuardrail:

    def test_subtotal_mismatch_rejected(self):
        q = make_quote()
        q["subtotal"] = 99999.0    # doesn't match line items
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False

    def test_zero_total_rejected(self):
        q = make_quote(total_amount=0.0)
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False

    def test_negative_total_rejected(self):
        q = make_quote(total_amount=-100.0)
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False

    def test_empty_line_items_rejected(self):
        q = make_quote(line_items=[])
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False

    def test_line_item_missing_subtotal_rejected(self):
        q = make_quote()
        q["line_items"][0] = {"type": "PART", "description": "Brake pads"}
        ok, _ = validate_quote_output(q, "EVAL-001")
        assert ok is False