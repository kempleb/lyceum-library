"""Regression tests for tools/extract_yonge_nd_wikisource.py's wikitext
parsing -- markup cleaning (footnotes, poem/verse flattening, layout
template unwrapping, page-boundary hyphenation, the Ppoem inline directive,
interwiki links), the chapter-marker scan (plain and `{{anchor+|ROMAN}}`
forms, malformed-numeral rejection), section-tag book slicing, and the raw
patch mechanism. No network: these exercise the module's functions directly
on minimal synthetic wikitext replicating the exact structures found in the
pinned Wikisource revisions (captured 2026-07-18, see the module docstring).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_yonge_nd_wikisource", _TOOLS / "extract_yonge_nd_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_yonge_nd_wikisource"] = _mod
_spec.loader.exec_module(_mod)


# --- roman numeral round-trip ------------------------------------------------

@pytest.mark.parametrize("roman,value", [
    ("I", 1), ("IV", 4), ("XXIX", 29), ("XXX", 30), ("XLIV", 44),
    ("LXVII", 67), ("XCIX", 99), ("CXXIV", 124),
])
def test_roman_round_trip(roman, value):
    assert _mod._roman_to_int(roman) == value
    assert _mod._int_to_roman(value) == roman


def test_malformed_roman_numeral_does_not_round_trip():
    # "IIII" is not canonical (should be "IV") -- the gate in _split_chapters
    # relies on this round-trip mismatch to fail loud.
    n = _mod._roman_to_int("IIII")
    assert _mod._int_to_roman(n) != "IIII"


# --- chapter-marker scanning -------------------------------------------------

def test_split_chapters_plain_markers():
    raw = "I. First chapter text.\n\nII. Second chapter text.\n\nIII. Third."
    chapters = _mod._split_chapters(raw, book=1)
    assert [n for n, _ in chapters] == [1, 2, 3]
    assert chapters[0][1].strip() == "First chapter text."
    assert chapters[1][1].strip() == "Second chapter text."


def test_split_chapters_anchor_marker_form():
    # Book 1's real XXX / Book 2's real LXIV shape.
    raw = "XXIX. Text of 29.\n\n{{anchor+|XXX}}. Text of 30.\n\nXXXI. Text of 31."
    chapters = _mod._split_chapters(raw, book=1)
    assert [n for n, _ in chapters] == [29, 30, 31]
    assert chapters[1][1].strip() == "Text of 30."
    assert "XXX" not in chapters[1][1]


def test_split_chapters_marker_at_string_start():
    raw = "I. Opens right at the start.\n\nII. Continues."
    chapters = _mod._split_chapters(raw, book=1)
    assert chapters[0][0] == 1
    assert chapters[0][1].strip().startswith("Opens right")


def test_split_chapters_rejects_malformed_numeral():
    raw = "I. Fine.\n\nIIII. Malformed, should be IV."
    with pytest.raises(ValueError, match="malformed roman numeral"):
        _mod._split_chapters(raw, book=1)


# --- section-tag extraction (book slicing) -----------------------------------

def test_extract_section_slices_between_tags():
    text = (
        'front matter<section begin="otnotg_book1" />BOOK ONE CONTENT'
        '<section end="otnotg_book1" />trailing chrome'
    )
    body = _mod._extract_section(text, "otnotg_book1")
    assert body == "BOOK ONE CONTENT"


def test_extract_section_fails_loud_on_duplicate_tag():
    text = (
        '<section begin="otnotg_book1" />A<section end="otnotg_book1" />'
        '<section begin="otnotg_book1" />B<section end="otnotg_book1" />'
    )
    with pytest.raises(ValueError, match="exactly one begin/end pair"):
        _mod._extract_section(text, "otnotg_book1")


def test_extract_section_fails_loud_when_missing():
    with pytest.raises(ValueError):
        _mod._extract_section("no section tags here", "otnotg_book1")


# --- markup cleaning ----------------------------------------------------------

def test_clean_markup_strips_footnotes_and_counts_them():
    report = {}
    text = _mod._clean_markup("word one<ref>a note</ref> word two.", report)
    assert text == "word one word two."
    assert report["n_footnotes"] == 1


def test_clean_markup_flattens_poem_tags():
    raw = "before\n{{center block|{{smaller block|<poem>line one\nline two\n</poem>}}}}\nafter"
    text = _mod._clean_markup(raw, {})
    assert "<poem>" not in text and "</poem>" not in text
    assert "{{" not in text and "}}" not in text
    assert "line one" in text and "line two" in text


def test_clean_markup_unwraps_nested_layout_templates():
    raw = "start {{left margin|4em|{{fine block|<poem>a verse line</poem>}}}} end"
    text = _mod._clean_markup(raw, {})
    assert text.strip() == "start a verse line end"


def test_clean_markup_hws_hwe_page_seam_pair():
    # Book 1 djvu 217/218 real shape: hws holds the page-final half (dropped),
    # hwe holds the next page's leading half, resolved to the WHOLE word.
    raw = "I have {{hws|ap|applied}}\n{{hwe|plied|applied}} myself to them"
    text = _mod._clean_markup(raw, {})
    assert text == "I have \napplied myself to them"
    # the paragraph pass (which the real pipeline always runs next) collapses
    # this internal newline to a single space, correctly rejoining the word.
    assert _mod._paragraphs(text) == "I have applied myself to them"


def test_clean_markup_ppoem_directive_stripped():
    raw = "before {{ppoem|{fine}\nThe Iron Age began\n}} after"
    text = _mod._clean_markup(raw, {})
    assert "{fine}" not in text
    assert "The Iron Age began" in text


def test_clean_markup_piped_wikilink_uses_label():
    raw = "whose life, [[w:Chrysippus|Chrysippus]] says, was given it"
    text = _mod._clean_markup(raw, {})
    assert text == "whose life, Chrysippus says, was given it"

    text_bare = _mod._clean_markup("see [[Some Page]] here", {})
    assert text_bare == "see Some Page here"


def test_clean_markup_two_arg_anchor_uses_label():
    raw = "call your {{anchor+|SomeId|just proportion}}, said he"
    text = _mod._clean_markup(raw, {})
    assert text == "call your just proportion, said he"


def test_clean_markup_polytonic_and_italic_kept():
    raw = "the Greeks call {{polytonic|ποιότης}}, no ''sense''?"
    text = _mod._clean_markup(raw, {})
    assert "ποιότης" in text
    assert "sense" in text and "''" not in text


def test_clean_markup_nop_forces_paragraph_break():
    raw = "end of one paragraph.\n{{nop}}\nStart of the next."
    cleaned = _mod._clean_markup(raw, {})
    text = _mod._paragraphs(cleaned)
    assert text == "end of one paragraph.\n\nStart of the next."


def test_clean_markup_decorative_templates_drop_silently():
    raw = "before{{dhr}}{{rule|12em}}{{bar|2}}mid{{gap|1.5em}}after"
    text = _mod._clean_markup(raw, {})
    assert "{{" not in text and "}}" not in text
    assert "before" in text and "mid" in text and "after" in text


# --- paragraph joining --------------------------------------------------------

def test_paragraphs_splits_on_blank_lines_and_collapses_whitespace():
    raw = "line one\nline   two\n\n\nsecond   paragraph"
    assert _mod._paragraphs(raw) == "line one line two\n\nsecond paragraph"


# --- raw patch mechanism -------------------------------------------------------

def test_apply_raw_patches_exact_once():
    patches = [{"scope": "raw", "old": "XVII. Did not", "new": "XXVII. Did not"}]
    text = _mod._apply_raw_patches("before XVII. Did not Thyestes after", patches)
    assert "XXVII. Did not Thyestes" in text


def test_apply_raw_patches_fails_loud_on_zero_matches():
    patches = [{"scope": "raw", "old": "NOT PRESENT ANYWHERE", "new": "x"}]
    with pytest.raises(ValueError, match="matched 0 times"):
        _mod._apply_raw_patches("some text", patches)


def test_apply_raw_patches_fails_loud_on_multiple_matches():
    patches = [{"scope": "raw", "old": "dup", "new": "x"}]
    with pytest.raises(ValueError, match="matched 2 times"):
        _mod._apply_raw_patches("dup and dup again", patches)
