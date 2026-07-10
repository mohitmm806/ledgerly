"""Turn an extracted invoice into grounded, confidence-scored fields.

Confidence here is deliberately not "how sure did the model say it was." It
combines two trustworthy signals:

  - grounding: could we find this value on the page, and how cleanly? A value
    grounded exactly is more believable than one we couldn't place at all.
  - validation: is this field implicated in a check that failed? A total that
    doesn't reconcile is untrustworthy no matter how cleanly it grounds.

The result is one record per field, carrying its on-page location and a score.
Low-confidence fields are what the review UI surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass

from .grounding import locate
from .invoice_schema import Invoice
from .validation import Issue

# A field implicated in a failed validation check gets this knocked off: a hard
# signal that something is wrong outweighs a clean grounding match.
_VALIDATION_PENALTY = 0.5
# We have a value but couldn't locate it on the page: usable but not verified.
_UNGROUNDED_BASE = 0.35


@dataclass
class FieldScore:
    field_key: str
    value_text: str
    matched: bool
    method: str
    confidence: float
    page: int = 0
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0
    page_width: float = 0.0
    page_height: float = 0.0


def _implicated(field_key: str, issues: list[Issue]) -> bool:
    for issue in issues:
        for f in issue.fields:
            if f == field_key:
                return True
            # "line_items" or "line_items[0]" should implicate
            # "line_items[0].amount".
            if field_key.startswith(f):
                return True
    return False


def _score_one(field_key: str, value, blocks, issues) -> FieldScore | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    placement = locate(value, blocks)
    base = placement.quality if placement.matched else _UNGROUNDED_BASE
    if _implicated(field_key, issues):
        base -= _VALIDATION_PENALTY
    confidence = round(max(0.05, min(1.0, base)), 2)

    return FieldScore(
        field_key=field_key,
        value_text=str(value),
        matched=placement.matched,
        method=placement.method,
        confidence=confidence,
        page=placement.page,
        x0=placement.x0, top=placement.top, x1=placement.x1, bottom=placement.bottom,
        page_width=placement.page_width, page_height=placement.page_height,
    )


def score_fields(inv: Invoice, issues: list[Issue], blocks) -> list[FieldScore]:
    """Ground and score every present field on the invoice."""
    scores: list[FieldScore] = []

    scalar_fields = [
        ("vendor", inv.vendor),
        ("invoice_number", inv.invoice_number),
        ("invoice_date", inv.invoice_date),
        ("subtotal", inv.subtotal),
        ("tax", inv.tax),
        ("discount", inv.discount),
        ("total", inv.total),
    ]
    for key, value in scalar_fields:
        s = _score_one(key, value, blocks, issues)
        if s is not None:
            scores.append(s)

    for i, li in enumerate(inv.line_items):
        s = _score_one(f"line_items[{i}].amount", li.amount, blocks, issues)
        if s is not None:
            scores.append(s)

    return scores
