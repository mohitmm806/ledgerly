"""Query stored invoices, either with an explicit filter or plain English.

The English path translates to the same structured filter the explicit path
uses, and the response echoes the applied filter so the user can see how their
question was interpreted.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_llm
from ..extraction.llm import LLM, LLMError
from ..query.filters import QueryFilter, build_query
from ..query.nl import translate
from ..schemas import QueryRequest, QueryResponse, QueryResultItem

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def run_query(req: QueryRequest, db: Session = Depends(get_db)):
    """Structured query. Builds the filter directly from the request fields."""
    f = QueryFilter(
        vendor=req.vendor,
        invoice_number=req.invoice_number,
        min_total=req.min_total,
        max_total=req.max_total,
        date_from=req.date_from,
        date_to=req.date_to,
    )
    return _execute(db, f, interpreted_from=None)


@router.post("/nl", response_model=QueryResponse)
def run_nl_query(
    req: QueryRequest, db: Session = Depends(get_db), llm: LLM = Depends(get_llm)
):
    """Natural-language query. Translates to a filter, then runs it.

    The LLM dependency means this returns an honest 503 when no model is
    configured, and tests can inject a deterministic translation.
    """
    question = req.q or ""
    try:
        f = translate(question, llm, today=date.today().isoformat())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return _execute(db, f, interpreted_from=question)


def _execute(db: Session, f: QueryFilter, *, interpreted_from: str | None) -> QueryResponse:
    rows = db.execute(build_query(f)).all()
    results = [
        QueryResultItem(
            document_id=doc.id,
            filename=doc.filename,
            vendor=ext.vendor,
            invoice_number=ext.invoice_number,
            invoice_date=ext.invoice_date,
            currency=ext.currency,
            total=ext.total,
        )
        for ext, doc in rows
    ]
    return QueryResponse(
        applied_filter={k: v for k, v in f.model_dump().items() if v is not None},
        interpreted_from=interpreted_from,
        count=len(results),
        results=results,
    )
