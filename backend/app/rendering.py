"""Render a document page to a PNG for the review UI to draw boxes on.

Grounding stores each box in page-space (the same width/height units as the
page it lives on), so the frontend can scale boxes to whatever size it displays
the image at. That means the exact render resolution here doesn't matter for
alignment; we pick something readable.
"""

from __future__ import annotations

import io

RENDER_DPI = 150


class PageNotRenderable(Exception):
    pass


def render_page_png(data: bytes, content_type: str, page: int) -> bytes:
    is_pdf = content_type == "application/pdf" or data[:5] == b"%PDF-"
    if is_pdf:
        return _render_pdf_page(data, page)
    if content_type.startswith("image/"):
        if page != 1:
            raise PageNotRenderable("Images have a single page")
        return _reencode_image(data)
    raise PageNotRenderable(f"Cannot render content type {content_type!r}")


def _render_pdf_page(data: bytes, page: int) -> bytes:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if page < 1 or page > len(pdf.pages):
            raise PageNotRenderable(f"Page {page} out of range")
        pil = pdf.pages[page - 1].to_image(resolution=RENDER_DPI).original
        return _to_png_bytes(pil)


def _reencode_image(data: bytes) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(data))
    img.load()
    return _to_png_bytes(img)


def _to_png_bytes(img) -> bytes:
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
