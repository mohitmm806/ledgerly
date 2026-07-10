"""Ingestion is the foundation for grounding, so the thing these tests really
guard is: do we get text back, AND do we get real coordinates for it?
"""

import pytest

from app.ingestion import UnsupportedDocument, ingest


def test_pdf_text_extraction_returns_words_with_coordinates(sample_invoice_pdf):
    result = ingest(sample_invoice_pdf, "application/pdf")

    assert result.method == "pdf_text"
    assert result.page_count == 1
    assert result.words, "expected extracted words"

    # The content made it through.
    assert "Acme" in result.text
    assert "154.00" in result.text

    # Every word carries a usable bounding box. This is the property grounding
    # depends on; if it regresses, grounding silently breaks.
    for w in result.words:
        assert w.x1 > w.x0
        assert w.bottom > w.top
        assert w.page_width > 0 and w.page_height > 0
        assert w.unit == "point"


def test_totals_are_locatable_for_grounding(sample_invoice_pdf):
    result = ingest(sample_invoice_pdf, "application/pdf")
    # The value "154.00" should exist as a positioned token we can point at.
    hits = [w for w in result.words if "154.00" in w.text]
    assert hits, "the total should be a locatable block"


def test_unsupported_content_type_raises():
    with pytest.raises(UnsupportedDocument):
        ingest(b"just some bytes", "text/plain")


def test_corrupt_pdf_raises_unsupported():
    # Looks like a PDF by header but isn't valid.
    with pytest.raises(UnsupportedDocument):
        ingest(b"%PDF-1.4 broken garbage", "application/pdf")


def test_image_ocr_path_runs(blank_image_png):
    # A blank image yields no words but must not error, and must be marked ocr.
    result = ingest(blank_image_png, "image/png")
    assert result.method == "ocr"
    assert result.page_count == 1
    assert result.words == []
