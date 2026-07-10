"""Map each extracted value back to where it sits on the page.

This is the signature feature. A bookkeeper won't trust an auto-extracted total
they can't verify, so every value should point at the spot it came from. The
hard part is that the model's value rarely matches the page verbatim: "$1,240.00"
on the page vs 1240.0 in the extraction, values split across OCR tokens, the same
number appearing twice.

We try progressively looser strategies and stop at the first that hits:

    exact       a single block equals the value verbatim
    normalized  a single block equals it after normalizing (numbers compared
                numerically, text stripped to lowercase alphanumerics)
    span        a run of consecutive blocks whose concatenation matches
                (handles values split across tokens)
    none        we couldn't place it, and we say so instead of guessing

The strategy that succeeds sets a match quality, which later feeds confidence:
a value we grounded exactly is more trustworthy than one we couldn't place.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A "block" here is any object with .text/.page/.x0/.top/.x1/.bottom plus page
# dimensions. Both the ORM LayoutBlock and the ingestion Word satisfy this, so
# grounding works on freshly-extracted words or on stored blocks.

_METHOD_QUALITY = {"exact": 1.0, "normalized": 0.9, "span": 0.75, "none": 0.0}


@dataclass
class Placement:
    matched: bool
    method: str
    quality: float
    page: int = 0
    x0: float = 0.0
    top: float = 0.0
    x1: float = 0.0
    bottom: float = 0.0
    page_width: float = 0.0
    page_height: float = 0.0


def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _as_number(s: str) -> float | None:
    """Parse a number out of messy text: '$1,240.00' -> 1240.0. None if not numeric."""
    cleaned = s.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _target_forms(value) -> tuple[str | None, float | None]:
    """Return (normalized_text, numeric_value) for a target value."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return None, round(float(value), 2)
    text = str(value)
    return _norm_text(text), _as_number(text)


def _block_matches(block, target_norm, target_num) -> bool:
    if target_num is not None:
        bnum = _as_number(block.text)
        if bnum is not None and abs(bnum - target_num) <= 0.01:
            return True
    if target_norm:
        return _norm_text(block.text) == target_norm
    return False


def _merge(blocks) -> Placement:
    x0 = min(b.x0 for b in blocks)
    top = min(b.top for b in blocks)
    x1 = max(b.x1 for b in blocks)
    bottom = max(b.bottom for b in blocks)
    first = blocks[0]
    return Placement(
        matched=True, method="", quality=0.0, page=first.page,
        x0=x0, top=top, x1=x1, bottom=bottom,
        page_width=first.page_width, page_height=first.page_height,
    )


def locate(value, blocks) -> Placement:
    """Find the best on-page placement for a single value."""
    target_norm, target_num = _target_forms(value)
    if target_norm is None and target_num is None:
        return Placement(matched=False, method="none", quality=0.0)

    # 1. exact: a single block equal verbatim (case-sensitive for text).
    if isinstance(value, str):
        for b in blocks:
            if b.text == value:
                p = _merge([b]); p.method = "exact"; p.quality = _METHOD_QUALITY["exact"]
                return p

    # 2. normalized: a single block equal after normalization / numerically.
    for b in blocks:
        if _block_matches(b, target_norm, target_num):
            p = _merge([b]); p.method = "normalized"; p.quality = _METHOD_QUALITY["normalized"]
            return p

    # 3. span: a run of consecutive blocks (reading order, same page) whose
    #    concatenation matches. Handles values split across tokens.
    span = _find_span(blocks, target_norm, target_num)
    if span:
        p = _merge(span); p.method = "span"; p.quality = _METHOD_QUALITY["span"]
        return p

    # 4. none.
    return Placement(matched=False, method="none", quality=0.0)


def _find_span(blocks, target_norm, target_num):
    """Look for consecutive blocks (per page, reading order) whose joined text
    matches the target. Bounded window so this stays cheap.
    """
    by_page: dict[int, list] = {}
    for b in blocks:
        by_page.setdefault(b.page, []).append(b)

    for page_blocks in by_page.values():
        ordered = sorted(page_blocks, key=lambda b: (round(b.top / 3), b.x0))
        n = len(ordered)
        for i in range(n):
            joined_norm = ""
            for j in range(i, min(i + 6, n)):  # window of up to 6 tokens
                joined_norm += _norm_text(ordered[j].text)
                run = ordered[i : j + 1]
                if target_num is not None:
                    joined_num = _as_number("".join(b.text for b in run))
                    if joined_num is not None and abs(joined_num - target_num) <= 0.01:
                        return run
                if target_norm and joined_norm == target_norm:
                    return run
    return None
