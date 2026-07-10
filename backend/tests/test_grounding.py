"""Grounding is the feature people will skip, so these tests pin the behavior
that makes it trustworthy: the fallback hierarchy, format-mismatch handling, and
honest failure when a value simply isn't on the page.
"""

from dataclasses import dataclass

from app.extraction.grounding import locate


@dataclass
class B:
    """Minimal block standing in for a LayoutBlock / ingestion Word."""
    text: str
    page: int = 1
    x0: float = 0.0
    top: float = 0.0
    x1: float = 10.0
    bottom: float = 10.0
    page_width: float = 600.0
    page_height: float = 800.0


def _row(texts, top):
    # Lay words left-to-right on one line at a given vertical position.
    out = []
    x = 0.0
    for t in texts:
        out.append(B(text=t, top=top, x0=x, x1=x + 40))
        x += 45
    return out


def test_exact_text_match():
    blocks = _row(["Acme", "Corp"], top=100)
    p = locate("Acme", blocks)
    assert p.matched and p.method == "exact"
    assert p.quality == 1.0


def test_number_format_mismatch_grounds_numerically():
    # Page shows "1,240.00"; extracted value is the float 1240.0.
    blocks = _row(["Total:", "1,240.00"], top=200)
    p = locate(1240.0, blocks)
    assert p.matched
    assert p.method == "normalized"
    # The box is the "1,240.00" token, to the right of "Total:".
    assert p.x0 > 0


def test_value_split_across_tokens_uses_span():
    # OCR split the total into three tokens: "1" "," "240.00" won't parse alone.
    blocks = _row(["1", ",", "240.00"], top=300)
    p = locate(1240.0, blocks)
    assert p.matched
    assert p.method == "span"
    # Merged box spans all three tokens.
    assert p.x1 > p.x0


def test_multitoken_text_span():
    blocks = _row(["Acme", "Corp", "Ltd"], top=100)
    p = locate("AcmeCorp", blocks)  # normalized target with no separators
    assert p.matched
    assert p.method == "span"


def test_unfindable_value_reports_none_not_a_guess():
    blocks = _row(["Acme", "Corp"], top=100)
    p = locate(9999.99, blocks)
    assert not p.matched
    assert p.method == "none"
    assert p.quality == 0.0


def test_none_value_is_not_grounded():
    p = locate(None, _row(["Acme"], top=100))
    assert not p.matched
