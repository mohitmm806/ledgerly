"""Confidence must reflect the two hard signals: grounding quality and whether
a field failed validation. These tests lock that in.
"""

from dataclasses import dataclass

from app.extraction.confidence import score_fields
from app.extraction.invoice_schema import Invoice, InvoiceLineItem
from app.extraction.validation import validate


@dataclass
class B:
    text: str
    page: int = 1
    x0: float = 0.0
    top: float = 0.0
    x1: float = 40.0
    bottom: float = 10.0
    page_width: float = 600.0
    page_height: float = 800.0


def _blocks(pairs):
    out = []
    x = 0.0
    for t, top in pairs:
        out.append(B(text=t, top=top, x0=x, x1=x + 40))
        x += 45
    return out


def test_grounded_clean_field_is_high_confidence():
    inv = Invoice(vendor="Acme", total=154.0, subtotal=154.0)
    blocks = _blocks([("Acme", 10), ("154.00", 20)])
    scores = {s.field_key: s for s in score_fields(inv, validate(inv), blocks)}
    assert scores["total"].confidence >= 0.9
    assert scores["total"].matched


def test_field_in_failed_validation_is_penalized():
    # Total doesn't reconcile: subtotal 140 + tax 14 = 154, not 200.
    inv = Invoice(vendor="Acme", subtotal=140.0, tax=14.0, total=200.0)
    blocks = _blocks([("Acme", 10), ("200.00", 20), ("140.00", 30), ("14.00", 40)])
    issues = validate(inv)
    scores = {s.field_key: s for s in score_fields(inv, issues, blocks)}
    # Even though 200.00 is on the page (grounds fine), the failed check pulls
    # its confidence down.
    assert scores["total"].matched
    assert scores["total"].confidence < 0.6


def test_ungrounded_value_is_low_but_nonzero():
    inv = Invoice(vendor="Acme", total=999.0, subtotal=999.0)
    blocks = _blocks([("Acme", 10)])  # total isn't on the page
    scores = {s.field_key: s for s in score_fields(inv, [], blocks)}
    assert not scores["total"].matched
    assert 0.0 < scores["total"].confidence < 0.5


def test_line_item_amounts_are_grounded():
    inv = Invoice(
        vendor="Acme", total=100.0, subtotal=100.0,
        line_items=[InvoiceLineItem(description="Widget", amount=100.0)],
    )
    blocks = _blocks([("Acme", 10), ("Widget", 20), ("100.00", 20)])
    keys = {s.field_key for s in score_fields(inv, validate(inv), blocks)}
    assert "line_items[0].amount" in keys
