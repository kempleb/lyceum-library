"""Regression tests for tools/extract_munro_wikisource.py's wikitext
parsing -- the {{rvh}} running-header range scan, the page-seam
classification ({{nop}} paragraph breaks, {{peh}} kept hyphens, bare soft
hyphens), and the record-boundary word-rejoin. No network: these exercise
the module's functions directly on minimal synthetic wikitext replicating
the exact structures found in the pinned Wikisource revisions (captured
2026-07-17, see the module docstring).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_munro_wikisource", _TOOLS / "extract_munro_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_munro_wikisource"] = _mod
_spec.loader.exec_module(_mod)


# --- running-header parsing -------------------------------------------------

def test_parse_header_recto_range():
    # Real recto shape (djvu 76): range after the "Lines" small-caps label.
    raw = ('<noinclude><pagequality level="3" user="X" />'
           '{{rvh|7|ON THE NATURE OF THINGS|ON THE NATURE OF THINGS|'
           '{{sc|Lines}}] 154-215|[{{sc|Book}} I}}</noinclude>body text')
    printed, rng = _mod._parse_header(raw)
    assert printed == 7
    assert rng == ("154-215", 154, 215)


def test_parse_header_range_bracket_variant():
    # djvu 90 variant: the ] sits after the range, not before it.
    raw = ('<noinclude><pagequality level="3" user="X" />'
           '{{rvh|21|T|T|{{sc|Lines}} 614-679]|[{{sc|Book}} I}}</noinclude>x')
    printed, rng = _mod._parse_header(raw)
    assert printed == 21
    assert rng == ("614-679", 614, 679)


def test_parse_header_verso_placeholder_yields_no_range():
    raw = ('<noinclude><pagequality level="3" user="X" />'
           '{{rvh|8|T|T|{{sc|Lines}}] #-# |[{{sc|Book}} I}}</noinclude>x')
    printed, rng = _mod._parse_header(raw)
    assert printed == 8
    assert rng is None


def test_parse_header_opener_has_neither():
    raw = '<noinclude><pagequality level="3" user="X" /></noinclude>{{c|BOOK II}}\n\ntext'
    printed, rng = _mod._parse_header(raw)
    assert printed is None
    assert rng is None


# --- seam classification ----------------------------------------------------

def test_seam_nop_is_paragraph_break():
    body, mode = _mod._classify_seam("...length of days.\n{{nop}}")
    assert mode == "para"
    assert body.endswith("length of days.")


def test_seam_peh_is_kept_hyphen():
    body, mode = _mod._classify_seam("...embellished in smooth{{peh}}")
    assert mode == "hard_hyphen"
    assert body.endswith("smooth")


def test_seam_bare_hyphen_is_soft():
    body, mode = _mod._classify_seam("...air rivers earth and things pro-")
    assert mode == "soft_hyphen"
    assert body.endswith("pro")


def test_seam_plain_text_joins_with_space():
    body, mode = _mod._classify_seam("...ministering ")
    assert mode == "space"
    assert body.endswith("ministering")


def test_join_modes():
    assert _mod._join("pro", "duced from earth", "soft_hyphen") == "produced from earth"
    assert _mod._join("smooth", "polished verses", "hard_hyphen") == "smooth-polished verses"
    assert _mod._join("days.", "New paragraph.", "para") == "days.\n\nNew paragraph."
    assert _mod._join("sorrowful", "priests hiding", "space") == "sorrowful priests hiding"


def test_split_leading_word():
    assert _mod._split_leading_word("duced from earth, and") == ("duced", "from earth, and")
    assert _mod._split_leading_word("word") == ("word", "")
    assert _mod._split_leading_word("") == ("", "")


# --- page cleaning gates ----------------------------------------------------

def test_clean_page_strips_footnote_and_reports():
    raw = ('<noinclude><pagequality level="3" user="X" />'
           '{{rvh|11|T|T|{{sc|Lines}}] 1-5|[{{sc|Book}} I}}</noinclude>'
           'named presteres,<ref>See note on p. 239.</ref> come down from above.')
    report = {}
    text, seam = _mod._clean_page(raw, 1, 80, report)
    assert "See note" not in text
    assert "presteres, come down" in text
    assert report["excluded_refs"][0][2] == "<ref>See note on p. 239.</ref>"


def test_clean_page_rejects_argument_leakage():
    raw = ('<noinclude></noinclude>329-369: but there is void as well as body in things')
    with pytest.raises(ValueError, match="Argument-style"):
        _mod._clean_page(raw, 1, 80, {})


def test_clean_page_rejects_surviving_markup():
    raw = '<noinclude></noinclude>text with a {{mystery|template}} inside'
    with pytest.raises(ValueError, match="un-stripped wiki markup"):
        _mod._clean_page(raw, 1, 80, {})


def test_clean_page_opener_requires_book_heading():
    # djvu 105 is book 2's opener: heading chrome must contain BOOK.
    good = '<noinclude></noinclude>{{c|BOOK II}}\n\n{{sc|It}} is sweet, when on the great sea...'
    text, _ = _mod._clean_page(good, 2, 105, {})
    assert text.startswith("It is sweet")
    bad = '<noinclude></noinclude>{{c|SOMETHING ELSE}}\n\nIt is sweet...'
    with pytest.raises(ValueError, match="no BOOK heading"):
        _mod._clean_page(bad, 2, 105, {})


def test_clean_page_lacuna_stars_kept_as_own_paragraph():
    raw = ('<noinclude></noinclude>...to the general weal. \n\n{{***|1}}\n\n'
           'for what remains to tell...')
    text, _ = _mod._clean_page(raw, 1, 71, {})
    assert "\n\n* * *\n\n" in text


# --- range validation -------------------------------------------------------

def _rec(book, start, end, derived=False):
    r = {"book": book, "range": f"{start}-{end if end is not None else ''}",
         "start": start, "end": end, "text": "x"}
    if derived:
        r["derived"] = True
    return r


def test_validate_accepts_shared_boundary_and_abutting():
    recs = {1: [_rec(1, 1, 23, derived=True), _rec(1, 23, 90), _rec(1, 91, 153)]}
    findings = _mod.validate(recs)
    assert any("DERIVED" in f for f in findings)
    assert not any("gap" in f for f in findings)


def test_validate_reports_gap_as_finding():
    # Real case: Book 3's print jumps 60-125 -> 127-189 (line 126 skipped).
    recs = {3: [_rec(3, 60, 125), _rec(3, 127, 189)]}
    findings = _mod.validate(recs)
    assert any("gap" in f and "126" in f for f in findings)


def test_validate_rejects_true_overlap():
    recs = {1: [_rec(1, 1, 90), _rec(1, 88, 153)]}
    with pytest.raises(ValueError, match="overlap"):
        _mod.validate(recs)


def test_validate_rejects_empty_text():
    recs = {1: [{"book": 1, "range": "1-23", "start": 1, "end": 23, "text": "  "}]}
    with pytest.raises(ValueError, match="empty text"):
        _mod.validate(recs)
