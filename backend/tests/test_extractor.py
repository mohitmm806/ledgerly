"""The self-correction loop is the depth of Day 2, so these tests prove the
behavior that matters: a bad first pass gets *recovered*, not just retried, and
the attempt count reflects reality.
"""

import json

from app.extraction.extractor import extract_invoice
from app.extraction.llm import FakeLLM

CLEAN = json.dumps({
    "vendor": "Acme", "invoice_number": "INV-1", "invoice_date": "2026-03-14",
    "currency": "USD", "subtotal": 140.0, "tax": 14.0, "total": 154.0,
    "line_items": [
        {"description": "A", "quantity": 2, "unit_price": 50, "amount": 100},
        {"description": "B", "quantity": 1, "unit_price": 40, "amount": 40},
    ],
})

# Same invoice but the total is wrong: subtotal 140 + tax 14 = 154, not 200.
BAD_TOTAL = json.dumps({
    "vendor": "Acme", "invoice_number": "INV-1", "invoice_date": "2026-03-14",
    "currency": "USD", "subtotal": 140.0, "tax": 14.0, "total": 200.0,
    "line_items": [
        {"description": "A", "quantity": 2, "unit_price": 50, "amount": 100},
        {"description": "B", "quantity": 1, "unit_price": 40, "amount": 40},
    ],
})


def test_clean_first_pass_needs_one_attempt():
    llm = FakeLLM([CLEAN])
    result = extract_invoice("irrelevant text", llm)
    assert result.passed is True
    assert result.attempts == 1
    assert result.issues == []
    assert result.invoice.total == 154.0


def test_bad_first_pass_is_recovered_by_self_correction():
    # First reply is wrong, second is correct. The loop should recover.
    llm = FakeLLM([BAD_TOTAL, CLEAN])
    result = extract_invoice("irrelevant text", llm)

    assert result.passed is True
    assert result.attempts == 2
    assert result.issues == []
    # And the correction was actually driven by the specific problem: the second
    # prompt must mention the total discrepancy we detected.
    assert "total" in llm.calls[1].lower()
    assert "200" in llm.calls[1]


def test_persistent_failure_returns_best_effort_flagged_not_clean():
    # Model never fixes it. We should get the invoice back, marked not passed,
    # with the issue retained rather than crashing or looping forever.
    llm = FakeLLM([BAD_TOTAL])
    result = extract_invoice("irrelevant text", llm, max_attempts=3)

    assert result.passed is False
    assert result.attempts == 3
    assert any(i.code == "total_mismatch" for i in result.issues)


def test_garbage_then_valid_json_recovers():
    llm = FakeLLM(["not json at all", CLEAN])
    result = extract_invoice("irrelevant text", llm)
    assert result.passed is True
    assert result.invoice.vendor == "Acme"


def test_json_wrapped_in_code_fence_is_parsed():
    llm = FakeLLM(["```json\n" + CLEAN + "\n```"])
    result = extract_invoice("irrelevant text", llm)
    assert result.passed is True
    assert result.invoice.total == 154.0
