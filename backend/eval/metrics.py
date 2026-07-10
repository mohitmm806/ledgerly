"""Scoring functions for the eval harness.

Kept as pure functions, separate from the harness that runs the model, so the
comparison logic itself is unit-tested and deterministic. The harness measures
quality; these functions define what "correct" means.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.extraction.invoice_schema import Invoice

SCALAR_FIELDS = ["vendor", "invoice_number", "invoice_date", "subtotal", "tax", "total"]
MONEY_TOL = 0.01


def _norm_str(s) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def field_correct(pred, truth) -> bool:
    """Is a single predicted field value correct vs. ground truth?"""
    if truth is None:
        return pred is None
    if pred is None:
        return False
    if isinstance(truth, (int, float)):
        try:
            return abs(float(pred) - float(truth)) <= MONEY_TOL
        except (TypeError, ValueError):
            return False
    return _norm_str(pred) == _norm_str(truth)


@dataclass
class FieldReport:
    correct: dict[str, bool] = field(default_factory=dict)

    @property
    def n_correct(self) -> int:
        return sum(1 for v in self.correct.values() if v)

    @property
    def n_total(self) -> int:
        return len(self.correct)


def compare_scalar_fields(pred: Invoice, truth: dict) -> FieldReport:
    """Per-field correctness for the fields the ground truth specifies."""
    report = FieldReport()
    for f in SCALAR_FIELDS:
        if f not in truth:
            continue
        report.correct[f] = field_correct(getattr(pred, f), truth[f])
    return report


@dataclass
class PRReport:
    matched: int
    predicted: int
    expected: int

    @property
    def precision(self) -> float:
        return self.matched / self.predicted if self.predicted else 0.0

    @property
    def recall(self) -> float:
        return self.matched / self.expected if self.expected else 0.0


def compare_line_items(pred: Invoice, truth_items: list[dict]) -> PRReport:
    """Match predicted line items to expected ones by amount (greedy)."""
    expected_amounts = [li.get("amount") for li in truth_items if li.get("amount") is not None]
    pred_amounts = [li.amount for li in pred.line_items if li.amount is not None]

    remaining = list(expected_amounts)
    matched = 0
    for a in pred_amounts:
        for i, e in enumerate(remaining):
            if abs(a - e) <= MONEY_TOL:
                matched += 1
                remaining.pop(i)
                break
    return PRReport(matched=matched, predicted=len(pred_amounts), expected=len(expected_amounts))
