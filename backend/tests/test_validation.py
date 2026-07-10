"""The validation rules are the backbone of both correction and confidence,
so these tests pin down exactly what counts as a problem.
"""

from app.extraction.invoice_schema import Invoice, InvoiceLineItem
from app.extraction.validation import validate


def _codes(inv):
    return {i.code for i in validate(inv)}


def test_clean_invoice_has_no_issues():
    inv = Invoice(
        vendor="Acme",
        invoice_number="INV-1",
        invoice_date="2026-03-14",
        currency="USD",
        subtotal=140.0,
        tax=14.0,
        total=154.0,
        line_items=[
            InvoiceLineItem(description="A", quantity=2, unit_price=50, amount=100),
            InvoiceLineItem(description="B", quantity=1, unit_price=40, amount=40),
        ],
    )
    assert validate(inv) == []


def test_line_items_not_summing_to_subtotal_flagged():
    inv = Invoice(
        vendor="Acme", total=154.0, subtotal=140.0, tax=14.0,
        line_items=[InvoiceLineItem(description="A", amount=999)],
    )
    assert "line_items_sum_mismatch" in _codes(inv)


def test_subtotal_plus_tax_not_equal_total_flagged():
    inv = Invoice(vendor="Acme", subtotal=100.0, tax=10.0, total=200.0)
    assert "total_mismatch" in _codes(inv)


def test_discount_reconciles_the_total():
    # A real invoice: line items -> subtotal 1250, 30% discount 375, total 875.
    inv = Invoice(
        vendor="Avery Davis", invoice_number="1024",
        subtotal=1250.0, discount=375.0, total=875.0,
        line_items=[
            InvoiceLineItem(description="Content Plan", amount=200),
            InvoiceLineItem(description="Copy Writing", amount=100),
            InvoiceLineItem(description="Website Design", amount=250),
            InvoiceLineItem(description="Website Development", amount=500),
            InvoiceLineItem(description="SEO", amount=200),
        ],
    )
    # With the discount modeled, nothing should be flagged.
    assert validate(inv) == []


def test_discount_ignored_would_flag_total():
    # Same invoice but the model missed the discount: total no longer reconciles.
    inv = Invoice(vendor="Avery Davis", subtotal=1250.0, total=875.0)
    assert "total_mismatch" in _codes(inv)


def test_line_quantity_times_price_mismatch_flagged():
    inv = Invoice(
        vendor="Acme", total=100.0, subtotal=100.0,
        line_items=[InvoiceLineItem(description="A", quantity=2, unit_price=50, amount=100)],
    )
    # 2 * 50 == 100, so no line mismatch here; change amount to trip it.
    assert "line_amount_mismatch" not in _codes(inv)
    inv.line_items[0].amount = 90
    inv.subtotal = 90
    inv.total = 90
    assert "line_amount_mismatch" in _codes(inv)


def test_unparseable_date_flagged():
    inv = Invoice(vendor="Acme", total=10.0, subtotal=10.0, invoice_date="March 14th")
    assert "unparseable_date" in _codes(inv)


def test_missing_total_flagged():
    inv = Invoice(vendor="Acme", subtotal=10.0)
    assert "missing_total" in _codes(inv)


def test_missing_identity_flagged():
    inv = Invoice(total=10.0, subtotal=10.0)
    assert "missing_identity" in _codes(inv)


def test_rounding_within_a_cent_is_ok():
    inv = Invoice(
        vendor="Acme", subtotal=100.0, tax=0.0, total=100.005,
        line_items=[InvoiceLineItem(description="A", amount=100.0)],
    )
    assert validate(inv) == []
