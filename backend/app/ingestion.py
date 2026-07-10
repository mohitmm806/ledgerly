"""Turn an uploaded file into text plus positioned word blocks.

Two paths:
  - Digital PDFs with a real text layer -> pdfplumber, which gives exact word
    coordinates in PDF points. Fast and accurate.
  - Scans / photos / image-only PDFs -> rasterize and OCR with Tesseract, which
    returns a bounding box per word in pixels.

Both paths return the same shape so everything downstream (storage, grounding)
is agnostic to how the text was obtained. We always keep coordinates: they are
the raw material for source-grounding later.
"""

from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass
class Word:
    text: str
    page: int
    x0: float
    top: float
    x1: float
    bottom: float
    page_width: float
    page_height: float
    unit: str  # "point" for PDF, "pixel" for OCR
    ocr_confidence: float = -1.0


@dataclass
class IngestResult:
    method: str  # "pdf_text" or "ocr"
    page_count: int
    words: list[Word]

    @property
    def text(self) -> str:
        """Reconstruct readable text, grouping words into lines per page."""
        lines: list[str] = []
        for page in sorted({w.page for w in self.words}):
            page_words = [w for w in self.words if w.page == page]
            # Cluster by vertical position so words on the same line stay together.
            page_words.sort(key=lambda w: (round(w.top / 3), w.x0))
            current_top = None
            line: list[str] = []
            for w in page_words:
                bucket = round(w.top / 3)
                if current_top is None or bucket == current_top:
                    line.append(w.text)
                else:
                    lines.append(" ".join(line))
                    line = [w.text]
                current_top = bucket
            if line:
                lines.append(" ".join(line))
        return "\n".join(lines).strip()


class UnsupportedDocument(Exception):
    """Raised when a file can't be read as a PDF or image."""


def ingest(data: bytes, content_type: str, *, enable_ocr: bool = True) -> IngestResult:
    """Ingest raw bytes. Chooses PDF or image path from content type / contents.

    A PDF with no extractable text layer (a scanned PDF) falls back to OCR.
    """
    is_pdf = content_type == "application/pdf" or data[:5] == b"%PDF-"
    if is_pdf:
        result = _ingest_pdf(data)
        if result.words:
            return result
        # No text layer: it's a scanned PDF. Fall back to OCR if available.
        if enable_ocr:
            return _ingest_pdf_via_ocr(data)
        return result  # empty, but honest about it

    if content_type.startswith("image/"):
        if not enable_ocr:
            raise UnsupportedDocument("OCR is disabled; cannot read image input")
        return _ingest_image(data)

    raise UnsupportedDocument(f"Unsupported content type: {content_type!r}")


def _ingest_pdf(data: bytes) -> IngestResult:
    import pdfplumber

    words: list[Word] = []
    page_count = 0
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                pw, ph = float(page.width), float(page.height)
                for w in page.extract_words(use_text_flow=True):
                    words.append(
                        Word(
                            text=w["text"],
                            page=i,
                            x0=float(w["x0"]),
                            top=float(w["top"]),
                            x1=float(w["x1"]),
                            bottom=float(w["bottom"]),
                            page_width=pw,
                            page_height=ph,
                            unit="point",
                        )
                    )
    except Exception as exc:  # pdfplumber raises a variety of parse errors
        raise UnsupportedDocument(f"Could not read PDF: {exc}") from exc

    return IngestResult(method="pdf_text", page_count=page_count, words=words)


def _ingest_pdf_via_ocr(data: bytes) -> IngestResult:
    """Rasterize each PDF page and OCR it. Used for scanned PDFs."""
    import pdfplumber

    words: list[Word] = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, start=1):
            pil_image = page.to_image(resolution=200).original
            words.extend(_ocr_image(pil_image, page=i))
    return IngestResult(method="ocr", page_count=page_count, words=words)


def _ingest_image(data: bytes) -> IngestResult:
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise UnsupportedDocument(f"Could not read image: {exc}") from exc
    words = _ocr_image(image, page=1)
    return IngestResult(method="ocr", page_count=1, words=words)


def _ocr_image(image, *, page: int) -> list[Word]:
    import pytesseract
    from pytesseract import Output

    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    data = pytesseract.image_to_data(image, output_type=Output.DICT)

    words: list[Word] = []
    for text, left, top, w, h, conf in zip(
        data["text"], data["left"], data["top"],
        data["width"], data["height"], data["conf"],
    ):
        if not text.strip():
            continue
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = -1.0
        words.append(
            Word(
                text=text,
                page=page,
                x0=float(left),
                top=float(top),
                x1=float(left + w),
                bottom=float(top + h),
                page_width=float(width),
                page_height=float(height),
                unit="pixel",
                ocr_confidence=confidence,
            )
        )
    return words
