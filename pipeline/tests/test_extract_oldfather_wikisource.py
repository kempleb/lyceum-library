"""Regression tests for tools/extract_oldfather_wikisource.py's Discourses
chapter parsing (`_extract_chapter`).

No network: these exercise `_extract_chapter` on minimal synthetic HTML
replicating the exact structures Wikisource's rendered ProofreadPage output
uses for a Discourses chapter page (captured 2026-07-16, see the module
docstring): a leading "[BOOK <ROMAN> ]CHAPTER <ROMAN>" `wst-center` div, the
chapter's own italic subtitle in a second `wst-center` div, then running
prose carrying `wst-verse` markers at every 5th TLG section.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_oldfather_wikisource", _TOOLS / "extract_oldfather_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_oldfather_wikisource"] = _mod
_spec.loader.exec_module(_mod)


def _page(heading: str, subtitle: str, body: str) -> str:
    """Minimal fetched-HTML shape: the prp-pages-output body div carrying a
    chapter heading, an italic subtitle, and the running prose."""
    return (
        '<div class="mw-parser-output">'
        '<div class="prp-pages-output" lang="en">'
        f'<div class="wst-center tiInherit"><p><span style="font-size:120%;">{heading}</span></p></div>'
        f'<div class="wst-center tiInherit"><p><i>{subtitle}</i></p></div>'
        f'{body}'
        '</div>'
        '<div class="mw-heading mw-heading2"><h2 id="Footnotes">Footnotes</h2></div>'
        '</div>'
    )


def test_title_extracted_and_excluded_from_body_text():
    html = _page(
        "CHAPTER I", "Of freedom",
        '<p><span class="smallcaps" style="font-variant:small-caps;">He</span>'
        ' is free who lives as he wills.</p>',
    )
    title, text, paras = _mod._extract_chapter(html)
    assert title == "Of freedom"
    assert not text.startswith("Of freedom")
    assert text == "He is free who lives as he wills."
    assert paras == []


def test_book_opening_chapter_heading_stripped_too():
    html = _page(
        "BOOK IV CHAPTER I", "Of freedom",
        '<p>He is free.</p>',
    )
    title, text, _ = _mod._extract_chapter(html)
    assert title == "Of freedom"
    assert text == "He is free."


def test_wst_verse_marker_removed_and_recorded_as_para_offset():
    # Replicates the real 4.1 "—110For what purpose" shape: the marker sits
    # directly against the surrounding punctuation/words with no real
    # whitespace in the source.
    html = _page(
        "CHAPTER I", "Of freedom",
        '<p>the very freedom for which we are now seeking.—'
        '<span class="wst-verse wst-verse-default" id="110"><sup>110</sup></span>'
        'For what purpose, then, did I receive these gifts?</p>',
    )
    title, text, paras = _mod._extract_chapter(html)
    assert "110" not in text
    assert text == (
        "The very freedom for which we are now seeking.—"
        "For what purpose, then, did I receive these gifts?"
    )
    assert paras == [{"n": 110, "o": text.index("For what purpose")}]


def test_multiple_wst_verse_markers_in_document_order():
    html = _page(
        "CHAPTER I", "Of freedom",
        '<p>First bit.'
        '<span class="wst-verse wst-verse-default" id="5"><sup>5</sup></span>'
        'Second bit.'
        '<span class="wst-verse wst-verse-default" id="10"><sup>10</sup></span>'
        'Third bit.</p>',
    )
    title, text, paras = _mod._extract_chapter(html)
    assert text == "First bit.Second bit.Third bit."
    assert [p["n"] for p in paras] == [5, 10]
    assert text[paras[0]["o"]:paras[0]["o"] + 6] == "Second"
    assert text[paras[1]["o"]:paras[1]["o"] + 5] == "Third"


def test_stray_space_before_punctuation_from_tag_boundary_is_collapsed():
    # The real Discourses 2.2 finding: the pinned source HTML has NO space
    # between </span> and the comma -- _flatten's blind tag-to-space
    # substitution introduced one ("Consider , you"). Must not regress.
    html = _page(
        "CHAPTER II", "On tranquillity",
        '<p><span class="smallcaps" style="font-variant:small-caps;">Consider</span>'
        ', you who are going to court.</p>',
    )
    _, text, _ = _mod._extract_chapter(html)
    assert text == "Consider, you who are going to court."
    assert " ," not in text


def test_genuine_spaces_around_inline_tags_are_preserved():
    # Sanity: the punctuation-space fix must not eat legitimate word-boundary
    # spaces that happen to sit next to a tag (e.g. "He</span> is free").
    html = _page(
        "CHAPTER I", "Of freedom",
        '<p><span class="smallcaps" style="font-variant:small-caps;">He</span>'
        ' is free who lives as he wills.</p>',
    )
    _, text, _ = _mod._extract_chapter(html)
    assert text == "He is free who lives as he wills."


def test_missing_subtitle_fails_loudly():
    html = (
        '<div class="mw-parser-output">'
        '<div class="prp-pages-output" lang="en">'
        '<div class="wst-center tiInherit"><p><span style="font-size:120%;">CHAPTER I</span></p></div>'
        '<p>No subtitle div follows.</p>'
        '</div>'
        '<div class="mw-heading mw-heading2"><h2 id="Footnotes">Footnotes</h2></div>'
        '</div>'
    )
    with pytest.raises(ValueError, match="no chapter subtitle"):
        _mod._extract_chapter(html)


def test_third_wst_center_div_is_kept_as_body_text():
    # Real corpus shape (1.12, 1.24): a centered inline quoted verse shares
    # the same wst-center class as the heading/subtitle. It is neither the
    # heading nor the subtitle -- it must flow into the body text unchanged.
    html = (
        '<div class="mw-parser-output">'
        '<div class="prp-pages-output" lang="en">'
        '<div class="wst-center tiInherit"><p><span style="font-size:120%;">CHAPTER I</span></p></div>'
        '<div class="wst-center tiInherit"><p><i>Of freedom</i></p></div>'
        '<p>Before the quote.</p>'
        '<div class="wst-center tiInherit"><p><i>Nor when I move am I concealed from thee.</i></p></div>'
        '<p>After the quote.</p>'
        '</div>'
        '<div class="mw-heading mw-heading2"><h2 id="Footnotes">Footnotes</h2></div>'
        '</div>'
    )
    title, text, _ = _mod._extract_chapter(html)
    assert title == "Of freedom"
    assert text == "Before the quote. Nor when I move am I concealed from thee. After the quote."


def test_heading_with_trailing_period_is_recognized():
    # Real corpus shape (1.27): "CHAPTER XXVII." carries a trailing period
    # some chapter pages have and others (e.g. "CHAPTER I") don't.
    html = _page("CHAPTER XXVII.", "A real subtitle", '<p>Body.</p>')
    title, text, _ = _mod._extract_chapter(html)
    assert title == "A real subtitle"
    assert text == "Body."


def test_marker_landing_mid_word_fails_loudly():
    # Synthetic pathological case: a wst-verse marker glued directly inside
    # a run of letters on both sides (never seen in the real corpus, but the
    # extraction must refuse to silently emit a mid-word paragraph offset).
    html = _page(
        "CHAPTER I", "Of freedom",
        '<p>wor<span class="wst-verse wst-verse-default" id="5"><sup>5</sup></span>d</p>',
    )
    with pytest.raises(ValueError, match="lands mid-word"):
        _mod._extract_chapter(html)
