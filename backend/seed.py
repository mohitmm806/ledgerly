"""Seed the database with sample invoices so a reviewer sees a working app
immediately, without having to upload anything first.

Ingests the labeled eval documents (clean PDFs, a scanned receipt, a messy
layout). If an LLM is configured it also runs extraction on them, so grounding
and the review UI have something to show on first load. Without a key it still
seeds the documents; extraction can be run from the UI once a key is set.

    python seed.py
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.extraction.service import run_extraction
from app.ingestion import ingest
from app.models import Document, LayoutBlock
from eval.dataset import build_dataset


def seed_if_empty() -> int:
    """Ingest sample documents only if there are none yet. Ingestion only (no
    LLM calls), so it's fast and free to run on every startup. Returns the
    number of documents seeded (0 if the DB already had data).
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Document).first() is not None:
            return 0
        seeded = 0
        for case in build_dataset():
            _ingest_case(db, case)
            db.commit()
            seeded += 1
        return seeded
    finally:
        db.close()


def _ingest_case(db, case) -> Document:
    data, content_type = case.render()
    ext = ".pdf" if content_type == "application/pdf" else ".png"
    stored = settings.storage_dir / f"{uuid.uuid4().hex}{ext}"
    stored.write_bytes(data)

    result = ingest(data, content_type, enable_ocr=settings.enable_ocr)
    doc = Document(
        filename=f"{case.case_id}{ext}",
        content_type=content_type,
        storage_path=str(stored),
        status="extracted",
        source_method=result.method,
        page_count=result.page_count,
        raw_text=result.text,
        blocks=[
            LayoutBlock(
                page=w.page, text=w.text, x0=w.x0, top=w.top, x1=w.x1, bottom=w.bottom,
                page_width=w.page_width, page_height=w.page_height,
                unit=w.unit, ocr_confidence=w.ocr_confidence,
            )
            for w in result.words
        ],
    )
    db.add(doc)
    db.flush()
    return doc


def main() -> None:
    Base.metadata.create_all(bind=engine)

    # Optional: run real extraction if a model is configured.
    llm = None
    try:
        from app.extraction.llm import default_llm

        llm = default_llm()
    except RuntimeError:
        print("No LLM_API_KEY set: seeding documents without extraction.")

    db = SessionLocal()
    try:
        seeded = 0
        for case in build_dataset():
            doc = _ingest_case(db, case)
            db.commit()
            if llm is not None:
                run_extraction(db, doc, llm)
            seeded += 1
        print(f"Seeded {seeded} documents" + (" with extractions." if llm else "."))
    finally:
        db.close()


if __name__ == "__main__":
    main()
