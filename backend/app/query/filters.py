"""A small, explicit query filter over extracted invoices.

Deliberately a fixed structured shape rather than free-form SQL. Two reasons:
the natural-language layer (see nl.py) targets this shape, which is safer than
letting a model emit SQL we execute blindly; and showing the user the parsed
filter is only meaningful if the filter is something legible.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import Select, select

from ..models import Document, Extraction


class QueryFilter(BaseModel):
    vendor: str | None = Field(default=None, description="Vendor name contains")
    invoice_number: str | None = Field(default=None, description="Invoice number contains")
    min_total: float | None = None
    max_total: float | None = None
    # ISO dates (YYYY-MM-DD). Lexical comparison works because the format sorts.
    date_from: str | None = None
    date_to: str | None = None

    def is_empty(self) -> bool:
        return not any(
            v is not None for v in self.model_dump().values()
        )


def build_query(f: QueryFilter) -> Select:
    """Turn a filter into a SQLAlchemy select over extractions + their document."""
    stmt = select(Extraction, Document).join(Document, Extraction.document_id == Document.id)

    if f.vendor:
        stmt = stmt.where(Extraction.vendor.ilike(f"%{f.vendor}%"))
    if f.invoice_number:
        stmt = stmt.where(Extraction.invoice_number.ilike(f"%{f.invoice_number}%"))
    if f.min_total is not None:
        stmt = stmt.where(Extraction.total >= f.min_total)
    if f.max_total is not None:
        stmt = stmt.where(Extraction.total <= f.max_total)
    if f.date_from:
        stmt = stmt.where(Extraction.invoice_date >= f.date_from)
    if f.date_to:
        stmt = stmt.where(Extraction.invoice_date <= f.date_to)

    return stmt.order_by(Extraction.invoice_date.desc())
