"""Validate an extracted invoice against hard, checkable rules.

The point of these checks is that they are *unarguable*. A model will happily
report a confident total that doesn't add up; arithmetic won't. So these issues
serve two jobs:
  1. They drive the self-correction loop: each issue becomes a specific
     instruction the model can act on ("line items sum to 140 but you reported
     subtotal 150").
  2. They feed confidence: a field involved in a failed check is not trustworthy
     regardless of how sure the model claims to be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .invoice_schema import Invoice

# Money comparisons need a tolerance for rounding. One cent.
MONEY_TOL = 0.01


@dataclass
class Issue:
    code: str
    message: str
    # Fields implicated by this issue, used later to lower their confidence.
    fields: list[str] = field(default_factory=list)


def validate(inv: Invoice) -> list[Issue]:
    issues: list[Issue] = []

    _check_line_items_sum(inv, issues)
    _check_subtotal_tax_total(inv, issues)
    _check_line_amounts(inv, issues)
    _check_date(inv, issues)
    _check_required(inv, issues)

    return issues


def _check_line_items_sum(inv: Invoice, issues: list[Issue]) -> None:
    amounts = [li.amount for li in inv.line_items if li.amount is not None]
    if inv.subtotal is None or not amounts:
        return
    summed = round(sum(amounts), 2)
    if abs(summed - inv.subtotal) > MONEY_TOL:
        issues.append(
            Issue(
                code="line_items_sum_mismatch",
                message=(
                    f"Line item amounts sum to {summed:.2f} but subtotal is "
                    f"{inv.subtotal:.2f}. Recheck the line items and subtotal."
                ),
                fields=["subtotal", "line_items"],
            )
        )


def _check_subtotal_tax_total(inv: Invoice, issues: list[Issue]) -> None:
    if inv.subtotal is None or inv.total is None:
        return
    tax = inv.tax or 0.0
    discount = inv.discount or 0.0
    expected = round(inv.subtotal + tax - discount, 2)
    if abs(expected - inv.total) > MONEY_TOL:
        issues.append(
            Issue(
                code="total_mismatch",
                message=(
                    f"Subtotal {inv.subtotal:.2f} + tax {tax:.2f} - discount "
                    f"{discount:.2f} = {expected:.2f}, but total is "
                    f"{inv.total:.2f}. If there's a discount, fee, or shipping "
                    "line, include it so the total reconciles."
                ),
                fields=["subtotal", "tax", "discount", "total"],
            )
        )


def _check_line_amounts(inv: Invoice, issues: list[Issue]) -> None:
    for i, li in enumerate(inv.line_items):
        if li.quantity is None or li.unit_price is None or li.amount is None:
            continue
        expected = round(li.quantity * li.unit_price, 2)
        if abs(expected - li.amount) > MONEY_TOL:
            issues.append(
                Issue(
                    code="line_amount_mismatch",
                    message=(
                        f"Line {i + 1} ({li.description!r}): quantity "
                        f"{li.quantity} x unit price {li.unit_price} = "
                        f"{expected:.2f}, but amount is {li.amount:.2f}."
                    ),
                    fields=[f"line_items[{i}]"],
                )
            )


def _check_date(inv: Invoice, issues: list[Issue]) -> None:
    if inv.invoice_date is None:
        return
    try:
        date.fromisoformat(inv.invoice_date)
    except ValueError:
        issues.append(
            Issue(
                code="unparseable_date",
                message=(
                    f"Invoice date {inv.invoice_date!r} is not a valid ISO date. "
                    "Return it as YYYY-MM-DD."
                ),
                fields=["invoice_date"],
            )
        )


def _check_required(inv: Invoice, issues: list[Issue]) -> None:
    # A usable invoice needs at least a total and something to identify it.
    if inv.total is None:
        issues.append(
            Issue(
                code="missing_total",
                message="No total was found. An invoice must have a total.",
                fields=["total"],
            )
        )
    if not inv.vendor and not inv.invoice_number:
        issues.append(
            Issue(
                code="missing_identity",
                message=(
                    "No vendor and no invoice number. At least one is needed to "
                    "identify the invoice."
                ),
                fields=["vendor", "invoice_number"],
            )
        )
