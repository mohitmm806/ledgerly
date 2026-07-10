# Eval

How good is the extraction, measured, not asserted.

## Run it

```bash
cd backend
LLM_API_KEY=... python -m eval.run_eval
```

## What it measures

The labeled set lives in `dataset.py`. Each case is a ground-truth invoice plus
a renderer that produces the actual document a user would upload. The label is
the source of truth and the document is rendered from it, so adding a case is
just adding a dict. The set mixes clean digital PDFs, a photographed receipt
(forces OCR), and a messy-layout invoice with currency symbols and thousands
separators, so the numbers reflect messy inputs, not just the happy path.

For each document it reports:

- **Field-level accuracy** across vendor, invoice number, date, subtotal, tax, total
- **Line-item precision / recall** (matched by amount)
- **Grounding accuracy**: of the fields we got right, how many did we also locate
  on the page
- **First-pass clean** vs **recovered by self-correction**: how often the model
  was right immediately vs. needed the validation-driven retry

Then an **error breakdown** grouping the misses by input kind, so it's clear
*where* it's weak, not just the headline number.

## Why this is separate from `make test`

`make test` asks "did I break something" and runs offline. This asks "how good
is it" and needs a real model. The scoring functions in `metrics.py` are pure
and unit-tested (see `tests/test_eval.py`); the harness plumbing is tested with
a fake model. Only the accuracy run itself needs a key.

## Note on the numbers

Real accuracy figures depend on the model you point it at. Run it against your
key and paste the headline numbers into the top-level README, including the
weak spot the error analysis surfaces. Don't ship placeholder numbers.
