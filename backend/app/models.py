from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(Base):
    """An uploaded invoice/receipt and the raw text we pulled out of it.

    Layout blocks (word positions) are captured at ingest time because they are
    what later makes source-grounding possible: mapping an extracted value back
    to the exact spot on the page it came from. If we don't store coordinates
    now, we can't rebuild them after extraction.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128))
    storage_path: Mapped[str] = mapped_column(String(1024))

    # uploaded -> processing -> extracted -> failed
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    # How text was obtained: "pdf_text", "ocr", or "" if not yet processed.
    source_method: Mapped[str] = mapped_column(String(32), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")

    raw_text: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    blocks: Mapped[list["LayoutBlock"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="LayoutBlock.page, LayoutBlock.top, LayoutBlock.x0",
    )
    extraction: Mapped["Extraction | None"] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
    )


class LayoutBlock(Base):
    """One positioned token of text on a page.

    Coordinates are stored in a top-left origin, in the units the extractor
    reports (PDF points for pdfplumber, pixels for OCR). `unit` records which,
    so downstream grounding can normalize against the rendered page size.
    """

    __tablename__ = "layout_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)

    x0: Mapped[float] = mapped_column(Float)
    top: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    bottom: Mapped[float] = mapped_column(Float)

    # Width/height of the page this block lives on, same units, so a consumer
    # can convert to fractional coordinates for rendering at any scale.
    page_width: Mapped[float] = mapped_column(Float, default=0.0)
    page_height: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(16), default="point")

    # OCR gives a 0-100 confidence per word; -1 when not applicable.
    ocr_confidence: Mapped[float] = mapped_column(Float, default=-1.0)

    document: Mapped["Document"] = relationship(back_populates="blocks")


class Extraction(Base):
    """The structured invoice pulled from a document.

    Records not just the values but how we got them: how many model passes were
    needed and whether validation ultimately passed. Those two fields are what
    let the eval report a self-correction recovery rate, and they're honest
    signal about how messy a given document was.
    """

    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )

    vendor: Mapped[str | None] = mapped_column(String(512), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # How the extraction went.
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    validation_passed: Mapped[bool] = mapped_column(default=False)
    # JSON-encoded list of remaining validation issues (empty if clean).
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    model_name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    document: Mapped["Document"] = relationship(back_populates="extraction")
    line_items: Mapped[list["ExtractedLineItem"]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="ExtractedLineItem.position",
    )
    provenance: Mapped[list["FieldProvenance"]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
    )


class ExtractedLineItem(Base):
    __tablename__ = "extracted_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    extraction_id: Mapped[int] = mapped_column(
        ForeignKey("extractions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    extraction: Mapped["Extraction"] = relationship(back_populates="line_items")


class FieldProvenance(Base):
    """Where an extracted value came from on the page, plus how confident we are.

    `field_key` names the field ("total", "vendor", "line_items[0].amount").
    The bbox is the merged region of the matching word block(s); `match_method`
    records how we found it (exact / normalized / span / none), which both
    explains the result and feeds the confidence score.
    """

    __tablename__ = "field_provenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    extraction_id: Mapped[int] = mapped_column(
        ForeignKey("extractions.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(64))
    value_text: Mapped[str] = mapped_column(Text, default="")

    matched: Mapped[bool] = mapped_column(default=False)
    match_method: Mapped[str] = mapped_column(String(16), default="none")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    page: Mapped[int] = mapped_column(Integer, default=0)
    x0: Mapped[float] = mapped_column(Float, default=0.0)
    top: Mapped[float] = mapped_column(Float, default=0.0)
    x1: Mapped[float] = mapped_column(Float, default=0.0)
    bottom: Mapped[float] = mapped_column(Float, default=0.0)
    page_width: Mapped[float] = mapped_column(Float, default=0.0)
    page_height: Mapped[float] = mapped_column(Float, default=0.0)

    extraction: Mapped["Extraction"] = relationship(back_populates="provenance")
