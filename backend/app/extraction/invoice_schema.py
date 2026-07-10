"""The structured shape we want out of an invoice.

This is the contract the LLM must fill. Keeping it a Pydantic model (rather than
a free-form dict) means malformed model output is rejected at the boundary
instead of leaking downstream, and it doubles as the JSON schema we hand to the
model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class InvoiceLineItem(BaseModel):
    description: str = Field(description="What the line is for")
    quantity: float | None = Field(default=None, description="Units billed")
    unit_price: float | None = Field(default=None, description="Price per unit")
    amount: float | None = Field(default=None, description="Line total")


class Invoice(BaseModel):
    vendor: str | None = Field(default=None, description="Who issued the invoice")
    invoice_number: str | None = None
    invoice_date: str | None = Field(
        default=None, description="ISO date if determinable (YYYY-MM-DD)"
    )
    currency: str | None = Field(default=None, description="ISO 4217 code, e.g. USD")
    subtotal: float | None = None
    tax: float | None = None
    discount: float | None = Field(
        default=None, description="Total discount amount subtracted, if any"
    )
    total: float | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)

    @staticmethod
    def json_schema_hint() -> str:
        """A compact schema description to embed in the extraction prompt."""
        return (
            "{\n"
            '  "vendor": string|null,\n'
            '  "invoice_number": string|null,\n'
            '  "invoice_date": string|null (YYYY-MM-DD),\n'
            '  "currency": string|null (ISO 4217),\n'
            '  "subtotal": number|null,\n'
            '  "tax": number|null,\n'
            '  "discount": number|null (total amount discounted, if any),\n'
            '  "total": number|null,\n'
            '  "line_items": [\n'
            '    {"description": string, "quantity": number|null,\n'
            '     "unit_price": number|null, "amount": number|null}\n'
            "  ]\n"
            "}"
        )
