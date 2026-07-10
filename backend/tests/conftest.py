import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture
def sample_invoice_pdf() -> bytes:
    """A tiny but real text-layer PDF resembling an invoice."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "Acme Corp")
    c.drawString(72, 700, "Invoice #INV-1001")
    c.drawString(72, 680, "Date: 2026-03-14")
    c.drawString(72, 640, "Widget A    2    50.00    100.00")
    c.drawString(72, 620, "Widget B    1    40.00     40.00")
    c.drawString(72, 580, "Subtotal: 140.00")
    c.drawString(72, 560, "Tax: 14.00")
    c.drawString(72, 540, "Total: 154.00")
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture
def blank_image_png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, format="PNG")
    return buf.getvalue()
