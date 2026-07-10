"""Query is half of the prompt ('searched and queried'), so it gets real tests:
the structured filtering itself, and that the NL layer targets the same filter.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.extraction.llm import FakeLLM
from app.models import Document, Extraction
from app.query.filters import QueryFilter, build_query
from app.query.nl import translate


@pytest.fixture
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path/'q.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    # Seed three invoices from two vendors across two dates.
    _seed(s, "Acme", "INV-1", "2026-01-15", 100.0)
    _seed(s, "Acme", "INV-2", "2026-03-20", 600.0)
    _seed(s, "Globex", "G-9", "2026-03-25", 250.0)
    s.commit()
    yield s
    s.close()


def _seed(s, vendor, number, d, total):
    doc = Document(filename=f"{number}.pdf", content_type="application/pdf",
                   storage_path="x", status="extracted")
    s.add(doc); s.flush()
    s.add(Extraction(document_id=doc.id, vendor=vendor, invoice_number=number,
                     invoice_date=d, total=total, currency="USD"))


def _run(s, f):
    return s.execute(build_query(f)).all()


def test_filter_by_vendor(db):
    rows = _run(db, QueryFilter(vendor="acme"))
    assert len(rows) == 2
    assert all(ext.vendor == "Acme" for ext, _ in rows)


def test_filter_by_min_total(db):
    rows = _run(db, QueryFilter(min_total=200))
    totals = sorted(ext.total for ext, _ in rows)
    assert totals == [250.0, 600.0]


def test_filter_by_date_range(db):
    rows = _run(db, QueryFilter(date_from="2026-03-01", date_to="2026-03-31"))
    assert len(rows) == 2
    assert all(ext.invoice_date.startswith("2026-03") for ext, _ in rows)


def test_combined_filter(db):
    rows = _run(db, QueryFilter(vendor="acme", min_total=200))
    assert len(rows) == 1
    assert rows[0][0].invoice_number == "INV-2"


def test_empty_filter_returns_everything(db):
    assert len(_run(db, QueryFilter())) == 3


def test_nl_translation_targets_the_structured_filter():
    # Model returns a filter; translate must parse it into QueryFilter.
    payload = json.dumps({"vendor": "Acme", "min_total": 500})
    f = translate("acme invoices over $500", FakeLLM([payload]))
    assert f.vendor == "Acme"
    assert f.min_total == 500
    assert f.max_total is None


def test_nl_translation_handles_code_fence():
    payload = "```json\n" + json.dumps({"max_total": 300}) + "\n```"
    f = translate("cheap invoices", FakeLLM([payload]))
    assert f.max_total == 300
