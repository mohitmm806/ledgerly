"""Extract a structured invoice from raw text, and correct itself.

This is the depth of Day 2. A single LLM call is the shallow version and it
fails quietly: the model returns a confident-looking invoice whose numbers don't
add up. Instead we run a loop:

    extract -> validate -> if issues, re-prompt with the *specific* problems ->
    extract again -> ...

up to a small number of attempts. We keep the best attempt seen (fewest issues),
so even if it never reaches zero issues we return the closest one rather than
the last one. The number of attempts and whether it ended clean are recorded;
those become the self-correction recovery rate in the eval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from .invoice_schema import Invoice
from .llm import LLM
from .validation import Issue, validate


@dataclass
class ExtractionResult:
    invoice: Invoice
    issues: list[Issue]
    attempts: int
    passed: bool
    model_name: str


MAX_ATTEMPTS = 3


def extract_invoice(text: str, llm: LLM, *, max_attempts: int = MAX_ATTEMPTS) -> ExtractionResult:
    best: Invoice | None = None
    best_issues: list[Issue] | None = None
    prior_issues: list[Issue] = []

    for attempt in range(1, max_attempts + 1):
        prompt = _build_prompt(text, prior_issues)
        raw = llm.complete(prompt)

        try:
            invoice = _parse(raw)
        except (ValidationError, ValueError):
            # Unparseable output. Treat as a correctable failure: tell the model
            # to return valid JSON and try again.
            prior_issues = [
                Issue(
                    code="invalid_json",
                    message="Your previous reply was not valid JSON matching the schema. Return only the JSON object.",
                )
            ]
            # If this was the last attempt and we never parsed anything, surface
            # an empty invoice with the issue rather than crashing.
            if best is None and attempt == max_attempts:
                best, best_issues = Invoice(), prior_issues
            continue

        issues = validate(invoice)

        # Keep the attempt with the fewest issues as our best-so-far.
        if best_issues is None or len(issues) < len(best_issues):
            best, best_issues = invoice, issues

        if not issues:
            return ExtractionResult(
                invoice=invoice, issues=[], attempts=attempt,
                passed=True, model_name=llm.name,
            )
        prior_issues = issues  # feed the specific problems into the next prompt

    # Ran out of attempts. Return the best we saw, honestly flagged as not clean.
    assert best is not None and best_issues is not None
    return ExtractionResult(
        invoice=best, issues=best_issues, attempts=max_attempts,
        passed=False, model_name=llm.name,
    )


def _build_prompt(text: str, prior_issues: list[Issue]) -> str:
    base = (
        "You extract structured data from invoices. Return ONLY a JSON object "
        "matching this schema, with no prose or code fences:\n\n"
        f"{Invoice.json_schema_hint()}\n\n"
        "Rules: numbers must be plain numbers (no currency symbols or commas). "
        "Use null for anything not present. Dates as YYYY-MM-DD. "
        "Use the full vendor/company name exactly as written, not a shortened "
        "form. If there's a discount, fee, or shipping amount, capture the "
        "discount so subtotal + tax - discount equals the total.\n\n"
        "Invoice text:\n"
        '"""\n'
        f"{text}\n"
        '"""'
    )
    if not prior_issues:
        return base

    # The correction step: name the exact discrepancies the last answer had.
    problems = "\n".join(f"- {i.message}" for i in prior_issues)
    return (
        base
        + "\n\nYour previous answer had these problems. Fix them and return the "
        "corrected JSON:\n"
        + problems
    )


def _parse(raw: str) -> Invoice:
    """Parse model text into an Invoice, tolerating stray fences/prose."""
    cleaned = raw.strip()

    # Strip a ```json ... ``` fence if the model added one.
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    # If there's surrounding prose, grab the outermost JSON object.
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found in model output")
        cleaned = cleaned[start : end + 1]

    data = json.loads(cleaned)
    return Invoice.model_validate(data)
