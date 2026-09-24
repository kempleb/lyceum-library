"""Regression tests for tools/extract_yonge_finibus.py's wikitext parsing --
markup cleaning (footnotes, poem/br verse flattening, layout template
unwrapping, the Wikisource ellipsis template, page-boundary soft-hyphen
seams), the chapter-marker scan (Book 2's unmarked leading chapter),
section-tag book slicing, page-quality gating, and the raw patch mechanism.
No network: these exercise the module's functions directly on minimal
synthetic wikitext replicating the exact structures found in the pinned
Wikisource revisions (captured 2026-07-24, see the module docstring).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_yonge_finibus", _TOOLS / "extract_yonge_finibus.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_yonge_finibus"] = _mod
_spec.loader.exec_module(_mod)


# --- roman numeral round-trip ------------------------------------------------

@pytest.mark.parametrize("roman,value", [
    ("I", 1), ("IV", 4), ("XXI", 21), ("XXXV", 35), ("XXII", 22),
    ("XXVIII", 28), ("XXXII", 32),
])
def test_roman_round_trip(roman, value):
    assert _mod._roman_to_int(roman) == value
    assert _mod._int_to_roman(value) == roman


def test_malformed_roman_numeral_does_not_round_trip():
    n = _mod._roman_to_int("IIII")
    assert _mod._int_to_roman(n) != "IIII"


# --- chapter-marker scanning -------------------------------------------------

def test_split_chapters_plain_markers():
    raw = "I. First chapter text.\n\nII. Second chapter text.\n\nIII. Third."
    chapters = _mod._split_chapters(raw, book=1)
    assert [n for n, _ in chapters] == [1, 2, 3]
    assert chapters[0][1].strip() == "First chapter text."
    assert chapters[1][1].strip() == "Second chapter text."


def test_split_chapters_book2_unmarked_leading_chapter():
    # Book 2's real shape: heading chrome, then unmarked chapter I prose,
    # then "II." opens the first numbered marker.
    raw = (
        "{{c|{{larger|{{uc|Second Book Of The Treatise On The Chief Good "
        "And Evil.}}}}}}\n\n{{Custom rule|sp|40|d|8|sp|40}}\n\n"
        "{{sc|On}} this, when both of them fixed their eyes on me...\n\n"
        "II. Second chapter text."
    )
    chapters = _mod._split_chapters(raw, book=2)
    assert [n for n, _ in chapters] == [1, 2]
    assert "Second Book Of The Treatise" not in chapters[0][1]
    assert "Custom rule" not in chapters[0][1]
    assert chapters[0][1].strip().startswith("{{sc|On}} this")
    assert chapters[1][1].strip() == "Second chapter text."


def test_split_chapters_strips_heading_with_no_custom_rule():
    # Books 3 and 5's shape: {{c|{{larger|{{uc|...}}}}}} heading with no
    # Custom rule template, first chapter still numbered "I.".
    raw = (
        "{{c|{{larger|{{uc|Third Book Of The Treatise On The Chief Good "
        "And Evil.}}}}}}\n\nI. Opening sentence of book three."
    )
    chapters = _mod._split_chapters(raw, book=3)
    assert [n for n, _ in chapters] == [1]
    assert "Third Book" not in chapters[0][1]
    assert chapters[0][1].strip() == "Opening sentence of book three."


def test_split_chapters_rejects_malformed_numeral():
    raw = "I. Fine.\n\nIIII. Malformed, should be IV."
    with pytest.raises(ValueError, match="malformed roman numeral"):
        _mod._split_chapters(raw, book=1)


# --- section-tag extraction (book slicing) -----------------------------------

def test_extract_section_slices_between_tags():
    text = (
        'front matter<section begin="df1" />BOOK ONE CONTENT'
        '<section end="df1" />trailing chrome'
    )
    body = _mod._extract_section(text, "df1")
    assert body == "BOOK ONE CONTENT"


def test_extract_section_fails_loud_on_duplicate_tag():
    text = (
        '<section begin="df1" />A<section end="df1" />'
        '<section begin="df1" />B<section end="df1" />'
    )
    with pytest.raises(ValueError, match="exactly one begin/end pair"):
        _mod._extract_section(text, "df1")


def test_extract_section_fails_loud_when_missing():
    with pytest.raises(ValueError):
        _mod._extract_section("no section tags here", "df1")


# --- page quality gate --------------------------------------------------------

def test_check_page_quality_accepts_level_3():
    _mod._check_page_quality('<pagequality level="3" user="Pasicles" />text', 200)


def test_check_page_quality_rejects_level_1():
    with pytest.raises(ValueError, match="expected pagequality level 3"):
        _mod._check_page_quality('<pagequality level="1" user="Someone" />text', 200)


def test_check_page_quality_rejects_missing_tag():
    with pytest.raises(ValueError, match="MISSING"):
        _mod._check_page_quality("no pagequality tag here", 200)


# --- page-seam joining --------------------------------------------------------

def test_join_pages_drops_soft_line_wrap_hyphen():
    parts = ["...erro-", "neous opinions,..."]
    assert _mod._join_pages(parts) == "...erroneous opinions,..."


def test_join_pages_keeps_real_double_dash():
    parts = ["end of sentence--", "start of next"]
    assert _mod._join_pages(parts) == "end of sentence--\nstart of next"


def test_join_pages_default_newline_join():
    parts = ["first page ends normally.", "Second page starts."]
    assert _mod._join_pages(parts) == "first page ends normally.\nSecond page starts."


# --- markup cleaning ----------------------------------------------------------

def test_clean_markup_strips_footnotes_and_counts_them():
    report = {}
    text = _mod._clean_markup("word one<ref>a note</ref> word two.", report)
    assert text == "word one word two."
    assert report["n_footnotes"] == 1


def test_clean_markup_flattens_poem_and_br_verse():
    raw = "before\n{{center block|{{smaller block|<poem>line one<br/>\nline two</poem>}}}}\nafter"
    text = _mod._clean_markup(raw, {})
    assert "<poem>" not in text and "</poem>" not in text and "<br" not in text
    assert "{{" not in text and "}}" not in text
    assert "line one" in text and "line two" in text


def test_clean_markup_normalizes_ellipsis_template():
    report = {}
    text = _mod._clean_markup("Cease, Rome, to dread your foes {{...|4}} truly", report)
    assert text == "Cease, Rome, to dread your foes ... truly"
    assert report["n_ellipsis"] == 1

    text2 = _mod._clean_markup("my mind's on fire, {{...}} said he", {})
    assert text2 == "my mind's on fire, ... said he"


def test_clean_markup_unwraps_nested_layout_templates():
    raw = "start {{center block|{{smaller block|{{c|nested content}}}}}} end"
    text = _mod._clean_markup(raw, {})
    assert text.strip() == "start nested content end"


def test_clean_markup_italic_and_greek_kept():
    raw = "the Greeks call it μαλιτία, no ''sense''?"
    text = _mod._clean_markup(raw, {})
    assert "μαλιτία" in text
    assert "sense" in text and "''" not in text


def test_clean_markup_nbsp_normalizes_to_space():
    text = _mod._clean_markup("word one", {})
    assert text == "word one"


def test_clean_markup_decorative_templates_drop_silently():
    raw = "before{{dhr}}{{rule|12em}}mid{{gap|1.5em}}after{{Custom rule|sp|40|d|8}}"
    text = _mod._clean_markup(raw, {})
    assert "{{" not in text and "}}" not in text
    assert "before" in text and "mid" in text and "after" in text


# --- paragraph joining --------------------------------------------------------

def test_paragraphs_splits_on_blank_lines_and_collapses_whitespace():
    raw = "line one\nline   two\n\n\nsecond   paragraph"
    assert _mod._paragraphs(raw) == "line one line two\n\nsecond paragraph"


# --- raw patch mechanism -------------------------------------------------------

def test_apply_raw_patches_exact_once():
    patches = [{"scope": "raw", "old": "some old phrase", "new": "some new phrase"}]
    text = _mod._apply_raw_patches("before some old phrase after", patches)
    assert "some new phrase" in text


def test_apply_raw_patches_fails_loud_on_zero_matches():
    patches = [{"scope": "raw", "old": "NOT PRESENT ANYWHERE", "new": "x"}]
    with pytest.raises(ValueError, match="matched 0 times"):
        _mod._apply_raw_patches("some text", patches)


def test_apply_raw_patches_fails_loud_on_multiple_matches():
    patches = [{"scope": "raw", "old": "dup", "new": "x"}]
    with pytest.raises(ValueError, match="matched 2 times"):
        _mod._apply_raw_patches("dup and dup again", patches)
