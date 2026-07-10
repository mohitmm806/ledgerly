# Decisions

The reasoning behind the calls I made, including a couple I'd redo. Grounded in
what's actually in the code.

## Invoices for a bookkeeper, not a general parser

Could've done resumes, contracts, papers. Invoices won because the schema is
obvious, there's a real person who feels the pain, and I can check my work
against ground truth. Vague problems get vague solutions, so step one was making
it concrete.

## "Queryable" is half the prompt, so query is a real feature

Easy to build extraction plus a `WHERE vendor =` and call it done. But the
prompt says searched *and* queried, and that's the half most tools phone in. So
there's a structured filter (`query/filters.py`) and a natural-language layer
(`query/nl.py`) that translates a question into that same filter. If I'd had to
cut something late, this would've been the last to go.

## The model translates to a filter, never to SQL

The NL query path produces a `QueryFilter` in a fixed shape, and the response
echoes the applied filter back to the UI. Two reasons: showing the parsed filter
makes a misread question visible ("last quarter" resolved to the wrong dates)
instead of silently returning wrong rows; and running a structured filter is
safer and more predictable than executing generated SQL.

## Extraction corrects itself instead of trusting one call

`extractor.py` is a loop, not a single call. It extracts, validates, and on
failure re-prompts with the *specific* discrepancy, up to three attempts. It
keeps the best attempt seen (fewest issues), so a document it never fully fixes
still returns the closest result, flagged as not clean, rather than the last
garbage attempt. Attempts and pass/fail are recorded, which is what the eval's
recovery rate is built from. This was the biggest single lever on quality.

## Confidence from hard signals, not the model's self-report

`confidence.py` scores each field from two trustworthy things: did it ground
cleanly, and is it implicated in a failed validation check. A model will report
high confidence on a total that doesn't add up; arithmetic won't. So a field
that fails a check is low-confidence no matter what the model says. That's what
makes "only review the flagged fields" safe.

## Grounding with a fallback hierarchy, and honest failure

`grounding.py` tries exact, then normalized (numbers compared numerically, text
reduced to alphanumerics), then a multi-token span, then reports "not found"
rather than guessing. The span step is what handles values OCR split across
tokens; the normalized step handles "$1,240.00" vs `1240.0`. Coordinates are
captured at ingest (`ingestion.py`) because they can't be rebuilt after the fact.
If a value can't be placed, the field still shows, just without a box and at
lower confidence. Graceful degradation beats an all-or-nothing feature.

## Coordinates live in page-space, so the UI scales freely

Every block and provenance box stores its page's width/height in the same units
as the box. The frontend converts to percentages, so the overlay lines up at any
display size and the server render resolution doesn't matter for alignment. That
kept the review UI simple.

## LLM behind a small interface, with a deterministic fake

Everything the pipeline needs from a model is "prompt in, text out"
(`llm.py`). Hiding that behind a Protocol means tests run with a `FakeLLM` that
can be scripted to return a bad answer then a good one, so the self-correction
loop is actually tested (it recovered on attempt two), with no network or key.
Swapping providers is a one-file change.

## SQLite by default, Postgres by env var

Defaults to a SQLite file so the project runs with zero setup; docker-compose
points it at Postgres via a single env var. Both go through SQLAlchemy, so it's
one line. Tables are created in a lifespan handler, not at import, so importing
the app (in tests) has no side effects.

## Tests and eval are different, and both exist

`make test` is regressions and runs offline. `make eval` measures accuracy and
needs a real model. The eval's scoring functions are pure and unit-tested; the
harness plumbing is tested with a fake. Collapsing them would hide whichever was
weaker.

## Modeling discounts (found by testing a real invoice)

Testing with an actual agency invoice surfaced a gap: it had a 30% package
discount, so line items summed to the subtotal but subtotal + tax did not equal
the total. The validation correctly flagged it and self-correction couldn't fix
it, because the real reason was a discount the schema didn't model. Rather than
loosen the check, I added a `discount` field and made the total reconcile as
`subtotal + tax - discount`. This is the human-in-the-loop loop doing its job: a
genuine "these numbers don't add up" that pointed at a missing concept, not a bad
extraction. Fees and shipping would deserve the same treatment next.

## Things I'd change

- The NL query is one-shot translation with no memory; a follow-up like "just
  the ones from March" won't refine the previous query. A small conversational
  state would fix it.
- Grounding matches per-value; when the same number appears twice (a line amount
  equal to the total) it takes the first. Disambiguating by expected label
  position would be more correct.
- No feedback loop yet: corrections in the review UI are stored but don't yet
  feed back as examples to improve future extractions. That's the obvious next win.
- Semantic search over the corpus is scoped but not built; the query is exact-ish
  filtering only. Whether it earns its complexity is an open question.
