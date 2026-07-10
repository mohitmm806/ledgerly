"""Translate a plain-English question into a structured QueryFilter.

The model only ever produces a filter in our fixed shape, never SQL, and the
caller shows that parsed filter back to the user. So a misread question is
visible ("last quarter" became the wrong dates) instead of silently returning
the wrong rows.
"""

from __future__ import annotations

import json

from ..extraction.llm import LLM
from .filters import QueryFilter


def translate(question: str, llm: LLM, *, today: str | None = None) -> QueryFilter:
    prompt = _build_prompt(question, today)
    raw = llm.complete(prompt)
    data = _parse(raw)
    return QueryFilter.model_validate(data)


def _build_prompt(question: str, today: str | None) -> str:
    date_note = f"Today's date is {today}. " if today else ""
    return (
        "Convert this question about stored invoices into a JSON filter. "
        "Return ONLY the JSON object, with these optional keys (omit or null "
        "any that don't apply):\n"
        "{\n"
        '  "vendor": string|null,\n'
        '  "invoice_number": string|null,\n'
        '  "min_total": number|null,\n'
        '  "max_total": number|null,\n'
        '  "date_from": "YYYY-MM-DD"|null,\n'
        '  "date_to": "YYYY-MM-DD"|null\n'
        "}\n"
        f"{date_note}Resolve relative dates (like 'last quarter') to explicit "
        "date_from/date_to.\n\n"
        f"Question: {question}"
    )


def _parse(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    if not cleaned.startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object in model output")
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)
