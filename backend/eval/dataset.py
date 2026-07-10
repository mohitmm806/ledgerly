"""The labeled eval set.

Each case is a ground-truth invoice plus a renderer that produces the *document*
a user would actually upload. Keeping the label as the source of truth and
rendering the document from it keeps the set honest and easy to grow: add a
dict, get a new labeled case.

The set deliberately mixes clean digital PDFs with harder inputs, a photographed
receipt (forces OCR), odd number formatting, and a two-column layout, so the
numbers reflect messy reality rather than only the happy path.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Callable


@dataclass
class Case:
    case_id: str
    kind: str          # "clean_pdf" | "scan" | "messy_layout"
    truth: dict
    render: Callable[[], tuple[bytes, str]]  # -> (bytes, content_type)


def _pdf(lines: list[tuple[float, float, str]]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica", 11)
    for x, y, text in lines:
        c.drawString(x, y, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _pdf_as_image(lines: list[tuple[float, float, str]]) -> bytes:
    """Render text to a PNG so extraction must go through OCR (a 'scan')."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (850, 1100), "white")
    draw = ImageDraw.Draw(img)
    for x, y, text in lines:
        # PDF origin is bottom-left; flip to top-left for the image.
        draw.text((x, 1100 - y), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _clean(case_id, vendor, number, d, items, tax_rate=0.10):
    subtotal = round(sum(q * p for _, q, p in items), 2)
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)
    lines = [(72, 740, vendor), (72, 720, f"Invoice {number}"), (72, 700, f"Date: {d}")]
    y = 660
    for desc, q, p in items:
        lines.append((72, y, f"{desc}   {q}   {p:.2f}   {q * p:.2f}"))
        y -= 20
    lines += [(72, y - 20, f"Subtotal: {subtotal:.2f}"),
              (72, y - 40, f"Tax: {tax:.2f}"),
              (72, y - 60, f"Total: {total:.2f}")]
    truth = {
        "vendor": vendor, "invoice_number": number, "invoice_date": d,
        "subtotal": subtotal, "tax": tax, "total": total,
        "line_items": [{"description": desc, "amount": round(q * p, 2)} for desc, q, p in items],
    }
    return Case(case_id, "clean_pdf", truth, lambda: (_pdf(lines), "application/pdf"))


def build_dataset() -> list[Case]:
    cases: list[Case] = []

    # Clean digital PDFs.
    cases.append(_clean("acme-1", "Acme Corp", "INV-1001", "2026-03-14",
                        [("Widget A", 2, 50.0), ("Widget B", 1, 40.0)]))
    cases.append(_clean("globex-1", "Globex LLC", "G-2044", "2026-02-01",
                        [("Consulting", 10, 120.0)]))
    cases.append(_clean("initech-1", "Initech", "2026-88", "2026-05-09",
                        [("License", 3, 300.0), ("Support", 1, 150.0), ("Setup", 1, 75.0)]))

    # A photographed receipt: same content, but as an image, so OCR is exercised.
    scan_lines = [(60, 740, "Umbrella Cafe"), (60, 715, "Receipt R-5567"),
                  (60, 690, "Date: 2026-04-02"),
                  (60, 650, "Coffee   3   4.50   13.50"),
                  (60, 630, "Pastry   2   3.25   6.50"),
                  (60, 600, "Subtotal: 20.00"), (60, 580, "Tax: 2.00"),
                  (60, 560, "Total: 22.00")]
    cases.append(Case(
        "umbrella-scan", "scan",
        {"vendor": "Umbrella Cafe", "invoice_number": "R-5567", "invoice_date": "2026-04-02",
         "subtotal": 20.00, "tax": 2.00, "total": 22.00,
         "line_items": [{"description": "Coffee", "amount": 13.50},
                        {"description": "Pastry", "amount": 6.50}]},
        lambda: (_pdf_as_image(scan_lines), "image/png"),
    ))

    # Odd number formatting: thousands separators, currency symbol.
    messy_lines = [(72, 740, "Massive Dynamic"), (72, 720, "Invoice MD-7"),
                   (72, 700, "Date: 2026-01-20"),
                   (72, 660, "Servers   4   1,250.00   5,000.00"),
                   (72, 640, "Subtotal: $5,000.00"), (72, 620, "Tax: $500.00"),
                   (72, 600, "Total: $5,500.00")]
    cases.append(Case(
        "massive-messy", "messy_layout",
        {"vendor": "Massive Dynamic", "invoice_number": "MD-7", "invoice_date": "2026-01-20",
         "subtotal": 5000.00, "tax": 500.00, "total": 5500.00,
         "line_items": [{"description": "Servers", "amount": 5000.00}]},
        lambda: (_pdf(messy_lines), "application/pdf"),
    ))

    return cases
