"""End-to-end route tests against an isolated SQLite database."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.deps import get_llm
from app.extraction.llm import FakeLLM
from app.main import app

_CLEAN_INVOICE = json.dumps({
    "vendor": "Acme", "invoice_number": "INV-1001", "invoice_date": "2026-03-14",
    "currency": "USD", "subtotal": 140.0, "tax": 14.0, "total": 154.0,
    "line_items": [
        {"description": "Widget A", "quantity": 2, "unit_price": 50, "amount": 100},
        {"description": "Widget B", "quantity": 1, "unit_price": 40, "amount": 40},
    ],
})


@pytest.fixture
def client(tmp_path):
    # Fresh file-backed SQLite per test run, torn down with tmp_path.
    engine = create_engine(
        f"sqlite:///{tmp_path/'test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_extract_list_detail_roundtrip(client, sample_invoice_pdf):
    # Upload
    resp = client.post(
        "/documents",
        files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "extracted"
    assert doc["source_method"] == "pdf_text"
    assert "Acme" in doc["raw_text"]
    assert len(doc["blocks"]) > 0
    assert doc["blocks"][0]["x1"] > doc["blocks"][0]["x0"]

    doc_id = doc["id"]

    # List
    resp = client.get("/documents")
    assert resp.status_code == 200
    assert any(d["id"] == doc_id for d in resp.json())

    # Detail
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


def test_empty_upload_rejected(client):
    resp = client.post(
        "/documents", files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert resp.status_code == 400


def test_non_invoice_garbage_is_unprocessable(client):
    resp = client.post(
        "/documents",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422


def test_missing_document_returns_404(client):
    assert client.get("/documents/99999").status_code == 404


def test_extract_endpoint_persists_structured_invoice(client, sample_invoice_pdf):
    # Inject a deterministic model so the route has no network dependency.
    app.dependency_overrides[get_llm] = lambda: FakeLLM([_CLEAN_INVOICE])
    try:
        up = client.post(
            "/documents",
            files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
        )
        doc_id = up.json()["id"]

        resp = client.post(f"/documents/{doc_id}/extract")
        assert resp.status_code == 200, resp.text
        ext = resp.json()
        assert ext["vendor"] == "Acme"
        assert ext["total"] == 154.0
        assert ext["validation_passed"] is True
        assert ext["attempts"] == 1
        assert len(ext["line_items"]) == 2
        assert ext["issues"] == []

        # Extraction is now attached to the document detail.
        detail = client.get(f"/documents/{doc_id}").json()
        assert detail["extraction"]["total"] == 154.0
    finally:
        app.dependency_overrides.pop(get_llm, None)


def test_extract_grounds_fields_to_source(client, sample_invoice_pdf):
    app.dependency_overrides[get_llm] = lambda: FakeLLM([_CLEAN_INVOICE])
    try:
        up = client.post(
            "/documents",
            files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
        )
        doc_id = up.json()["id"]
        ext = client.post(f"/documents/{doc_id}/extract").json()

        prov = {p["field_key"]: p for p in ext["provenance"]}
        # The total (154.00) is on the page, so it should ground with a box.
        assert prov["total"]["matched"] is True
        assert prov["total"]["x1"] > prov["total"]["x0"]
        assert prov["total"]["confidence"] >= 0.9
    finally:
        app.dependency_overrides.pop(get_llm, None)


def test_page_render_returns_png(client, sample_invoice_pdf):
    up = client.post(
        "/documents",
        files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
    )
    doc_id = up.json()["id"]
    resp = client.get(f"/documents/{doc_id}/page/1.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


def test_extract_surfaces_llm_billing_error_cleanly(client, sample_invoice_pdf):
    # A provider error (e.g. no credit balance) must come back as a readable 502,
    # not a 500 stack trace.
    from app.extraction.llm import LLMError

    class BrokenLLM:
        name = "broken"

        def complete(self, prompt):
            raise LLMError("The Anthropic account has no credit balance.")

    app.dependency_overrides[get_llm] = lambda: BrokenLLM()
    try:
        up = client.post(
            "/documents",
            files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
        )
        doc_id = up.json()["id"]
        resp = client.post(f"/documents/{doc_id}/extract")
        assert resp.status_code == 502
        assert "credit balance" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_llm, None)


def test_extract_without_llm_configured_returns_503(client, sample_invoice_pdf):
    # No override here, and no LLM_API_KEY in the test env -> honest 503.
    up = client.post(
        "/documents",
        files={"file": ("invoice.pdf", sample_invoice_pdf, "application/pdf")},
    )
    doc_id = up.json()["id"]
    resp = client.post(f"/documents/{doc_id}/extract")
    assert resp.status_code == 503
