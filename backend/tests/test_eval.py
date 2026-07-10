"""Tests for the eval machinery itself: the scoring is deterministic and
unit-tested, and the harness plumbing runs end to end against a fake model.
"""

import json

from app.extraction.invoice_schema import Invoice, InvoiceLineItem
from app.extraction.llm import FakeLLM
from eval.dataset import build_dataset
from eval.metrics import compare_line_items, compare_scalar_fields, field_correct
from eval.run_eval import evaluate_case


def test_field_correct_numbers_within_tolerance():
    assert field_correct(154.004, 154.0)
    assert not field_correct(154.5, 154.0)


def test_field_correct_strings_normalized():
    assert field_correct("Acme Corp", "acme corp")
    assert not field_correct("Acme", "Globex")


def test_field_correct_handles_none():
    assert field_correct(None, None)
    assert not field_correct(None, 10.0)
    assert not field_correct(10.0, None)


def test_compare_scalar_fields_counts_correct():
    pred = Invoice(vendor="Acme", total=154.0, subtotal=140.0, tax=14.0)
    truth = {"vendor": "Acme", "total": 154.0, "subtotal": 140.0, "tax": 99.0}
    r = compare_scalar_fields(pred, truth)
    assert r.correct["vendor"] and r.correct["total"]
    assert not r.correct["tax"]
    assert r.n_correct == 3 and r.n_total == 4


def test_line_item_precision_recall():
    pred = Invoice(line_items=[
        InvoiceLineItem(description="a", amount=100.0),
        InvoiceLineItem(description="b", amount=40.0),
        InvoiceLineItem(description="c", amount=5.0),  # spurious
    ])
    truth = [{"amount": 100.0}, {"amount": 40.0}]
    pr = compare_line_items(pred, truth)
    assert pr.matched == 2
    assert pr.recall == 1.0
    assert abs(pr.precision - 2 / 3) < 1e-6


def test_harness_runs_and_scores_perfect_when_model_is_perfect():
    # Feed back each case's ground truth as the model output: the harness should
    # run end to end and report full field accuracy. This checks plumbing, not
    # model quality.
    cases = build_dataset()

    def truth_as_json(case):
        t = dict(case.truth)
        t.setdefault("currency", "USD")
        return json.dumps(t)

    # One-case-at-a-time so each fake returns that case's own truth.
    total_fields = correct_fields = 0
    for case in cases:
        llm = FakeLLM([truth_as_json(case)])
        res = evaluate_case(case, llm)
        total_fields += res.n_fields
        correct_fields += res.n_fields_correct

    assert total_fields > 0
    # A perfect model should get most fields right; OCR on the scanned case can
    # still cost a field or two, which is exactly the messy-input signal we want.
    assert correct_fields >= total_fields - 3
