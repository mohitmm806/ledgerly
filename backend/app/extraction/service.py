"""Glue between the extractor and the database.

Runs extraction for a document, replaces any prior extraction, and persists the
structured result plus the how-it-went metadata (attempts, whether it passed,
remaining issues).
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import Document, ExtractedLineItem, Extraction, FieldProvenance
from .confidence import score_fields
from .extractor import ExtractionResult, extract_invoice
from .llm import LLM


def run_extraction(db: Session, doc: Document, llm: LLM) -> Extraction:
    result: ExtractionResult = extract_invoice(doc.raw_text, llm)
    inv = result.invoice

    # Ground each value against the stored layout blocks and score confidence.
    field_scores = score_fields(inv, result.issues, doc.blocks)

    # One extraction per document: replace any earlier attempt.
    if doc.extraction is not None:
        db.delete(doc.extraction)
        db.flush()

    extraction = Extraction(
        document_id=doc.id,
        vendor=inv.vendor,
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date,
        currency=inv.currency,
        subtotal=inv.subtotal,
        tax=inv.tax,
        discount=inv.discount,
        total=inv.total,
        attempts=result.attempts,
        validation_passed=result.passed,
        issues_json=json.dumps(
            [{"code": i.code, "message": i.message} for i in result.issues]
        ),
        model_name=result.model_name,
        line_items=[
            ExtractedLineItem(
                position=idx,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                amount=li.amount,
            )
            for idx, li in enumerate(inv.line_items)
        ],
        provenance=[
            FieldProvenance(
                field_key=s.field_key,
                value_text=s.value_text,
                matched=s.matched,
                match_method=s.method,
                confidence=s.confidence,
                page=s.page,
                x0=s.x0, top=s.top, x1=s.x1, bottom=s.bottom,
                page_width=s.page_width, page_height=s.page_height,
            )
            for s in field_scores
        ],
    )
    db.add(extraction)
    db.commit()
    db.refresh(extraction)
    return extraction
