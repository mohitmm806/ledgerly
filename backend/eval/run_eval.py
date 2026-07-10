"""Run extraction over the labeled set and report how good it is.

Usage:
    LLM_API_KEY=... python -m eval.run_eval

Reports field-level accuracy, line-item precision/recall, grounding accuracy,
and the self-correction recovery rate, then an error breakdown of where and why
it missed. The error breakdown matters as much as the headline number: it's the
honest account of where the system is weak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.extraction.confidence import score_fields
from app.extraction.extractor import extract_invoice
from app.extraction.llm import LLM
from app.ingestion import ingest

from .dataset import Case, build_dataset
from .metrics import PRReport, compare_line_items, compare_scalar_fields


@dataclass
class CaseResult:
    case_id: str
    kind: str
    n_fields: int
    n_fields_correct: int
    wrong_fields: list[str]
    pr: PRReport
    grounded: int
    grounded_total: int
    attempts: int
    passed: bool


def evaluate_case(case: Case, llm: LLM) -> CaseResult:
    data, content_type = case.render()
    ing = ingest(data, content_type)
    result = extract_invoice(ing.text, llm)
    inv = result.invoice

    fields = compare_scalar_fields(inv, case.truth)
    pr = compare_line_items(inv, case.truth.get("line_items", []))

    # Grounding accuracy: of the fields we got right, how many did we also locate
    # on the page? (No point grounding a wrong value.)
    scores = {s.field_key: s for s in score_fields(inv, result.issues, ing.words)}
    grounded = grounded_total = 0
    for f, ok in fields.correct.items():
        if ok and getattr(inv, f) is not None:
            grounded_total += 1
            s = scores.get(f)
            if s and s.matched:
                grounded += 1

    return CaseResult(
        case_id=case.case_id, kind=case.kind,
        n_fields=fields.n_total, n_fields_correct=fields.n_correct,
        wrong_fields=[f for f, ok in fields.correct.items() if not ok],
        pr=pr, grounded=grounded, grounded_total=grounded_total,
        attempts=result.attempts, passed=result.passed,
    )


@dataclass
class Aggregate:
    results: list[CaseResult] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def report(self) -> str:
        n_fields = sum(r.n_fields for r in self.results)
        n_correct = sum(r.n_fields_correct for r in self.results)
        li_matched = sum(r.pr.matched for r in self.results)
        li_pred = sum(r.pr.predicted for r in self.results)
        li_exp = sum(r.pr.expected for r in self.results)
        g = sum(r.grounded for r in self.results)
        g_total = sum(r.grounded_total for r in self.results)

        first_pass = sum(1 for r in self.results if r.attempts == 1 and r.passed)
        recovered = sum(1 for r in self.results if r.attempts > 1 and r.passed)
        n = len(self.results)

        def pct(a, b):
            return f"{100 * a / b:.1f}%" if b else "n/a"

        lines = [
            "=" * 60,
            f"Ledgerly eval  ({n} documents)",
            "=" * 60,
            f"Field-level accuracy      {pct(n_correct, n_fields)}  ({n_correct}/{n_fields})",
            f"Line-item precision       {pct(li_matched, li_pred)}",
            f"Line-item recall          {pct(li_matched, li_exp)}",
            f"Grounding accuracy        {pct(g, g_total)}  (correct fields located on page)",
            f"First-pass clean          {pct(first_pass, n)}",
            f"Recovered by correction   {pct(recovered, n)}",
            "",
            "Per-document:",
        ]
        for r in self.results:
            status = "ok " if not r.wrong_fields else "MISS"
            note = "" if not r.wrong_fields else f"  wrong: {', '.join(r.wrong_fields)}"
            lines.append(
                f"  [{status}] {r.case_id:<16} {r.kind:<13} "
                f"fields {r.n_fields_correct}/{r.n_fields}  "
                f"attempts {r.attempts}{note}"
            )

        if self.skipped:
            lines += ["", "Skipped (could not run, e.g. OCR needs tesseract):"]
            for case_id, reason in self.skipped:
                lines.append(f"  {case_id}: {reason}")

        lines += ["", "Error analysis:"]
        weak = [r for r in self.results if r.wrong_fields]
        if not weak:
            lines.append("  No field misses on this set.")
        else:
            by_kind: dict[str, int] = {}
            for r in weak:
                by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
            for kind, cnt in sorted(by_kind.items(), key=lambda x: -x[1]):
                lines.append(f"  {cnt} document(s) with misses were '{kind}' inputs")
        return "\n".join(lines)


def run_eval(llm: LLM, cases: list[Case] | None = None) -> Aggregate:
    cases = cases or build_dataset()
    agg = Aggregate()
    for case in cases:
        # One bad case (OCR without tesseract, a transient model error) shouldn't
        # sink the whole run; record it as skipped and keep going.
        try:
            agg.results.append(evaluate_case(case, llm))
        except Exception as exc:  # noqa: BLE001 - report any per-case failure
            agg.skipped.append((case.case_id, f"{type(exc).__name__}: {exc}"))
    return agg


def main() -> None:
    from app.extraction.llm import default_llm

    try:
        llm = default_llm()
    except RuntimeError as exc:
        raise SystemExit(f"{exc}\nSet LLM_API_KEY to run the eval.")
    print(run_eval(llm).report())


if __name__ == "__main__":
    main()
