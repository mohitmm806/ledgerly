"""Document upload / retrieval.

Day-1 scope: get a file in, extract text + positioned word blocks, store it,
and read it back. Extraction into structured invoice fields is Day 2; this is
the ingestion floor everything else stands on.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..rendering import PageNotRenderable, render_page_png

from ..config import settings
from ..database import get_db
from ..deps import get_llm
from ..extraction.llm import LLM, LLMError
from ..extraction.service import run_extraction
from ..ingestion import UnsupportedDocument, ingest
from ..models import Document, LayoutBlock
from ..schemas import DocumentDetail, DocumentSummary, ExtractionOut

router = APIRouter(prefix="/documents", tags=["documents"])

# Guardrail so a huge upload can't exhaust memory. 20 MB covers real invoices.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("", response_model=DocumentDetail, status_code=201)
def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    # Persist the original bytes so grounding can render the source later.
    ext = Path(file.filename or "").suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = settings.storage_dir / stored_name
    storage_path.write_bytes(data)

    doc = Document(
        filename=file.filename or stored_name,
        content_type=file.content_type or "application/octet-stream",
        storage_path=str(storage_path),
        status="processing",
    )
    db.add(doc)
    db.flush()  # assign an id without committing yet

    try:
        result = ingest(data, doc.content_type, enable_ocr=settings.enable_ocr)
    except UnsupportedDocument as exc:
        # Not a server error: the user handed us something we can't read.
        # Record why on the document rather than throwing the upload away.
        doc.status = "failed"
        doc.error = str(exc)
        db.commit()
        db.refresh(doc)
        raise HTTPException(status_code=422, detail=str(exc))

    doc.raw_text = result.text
    doc.source_method = result.method
    doc.page_count = result.page_count
    doc.status = "extracted"
    doc.blocks = [
        LayoutBlock(
            page=w.page, text=w.text,
            x0=w.x0, top=w.top, x1=w.x1, bottom=w.bottom,
            page_width=w.page_width, page_height=w.page_height,
            unit=w.unit, ocr_confidence=w.ocr_confidence,
        )
        for w in result.words
    ]
    db.commit()
    db.refresh(doc)
    return doc


@router.get("", response_model=list[DocumentSummary])
def list_documents(db: Session = Depends(get_db)):
    stmt = select(Document).order_by(Document.uploaded_at.desc())
    return db.scalars(stmt).all()


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/page/{page}.png")
def get_page_image(document_id: int, page: int, db: Session = Depends(get_db)):
    """Render a document page to PNG so the UI can overlay grounding boxes."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        data = Path(doc.storage_path).read_bytes()
        png = render_page_png(data, doc.content_type, page)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Source file missing")
    except PageNotRenderable as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Cache: a rendered page never changes for a given document.
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.post("/{document_id}/extract", response_model=ExtractionOut)
def extract_document(
    document_id: int,
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
):
    """Run structured extraction (with the self-correcting loop) on a document.

    Idempotent: re-running replaces the previous extraction for this document.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.raw_text.strip():
        raise HTTPException(
            status_code=422, detail="Document has no extracted text to work from"
        )
    try:
        return run_extraction(db, doc, llm)
    except LLMError as exc:
        # Provider-side failure (billing/auth/rate limit): a clean 502 with a
        # readable message the UI surfaces, not a stack trace.
        raise HTTPException(status_code=502, detail=str(exc))
