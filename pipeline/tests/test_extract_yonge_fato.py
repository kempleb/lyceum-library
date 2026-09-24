"""Offline unit tests for extract_yonge_fato.py's pure functions. No
corpus/network access required -- these exercise the module's helpers on
small synthetic fixtures replicating the exact structures found in the
pinned archive.org OCR (page headers, footnote lines, chapter markers,
hyphen line-wraps), not the real 27k-line source file."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import extract_yonge_fato as m  # noqa: E402


# --- _norm / _is_apparatus ---------------------------------------------------

def test_norm_collapses_whitespace():
    assert m._norm("a   b\tc") == "a b c"
    assert m._norm("  leading and trailing  ") == "leading and trailing"


def test_is_apparatus_flags_page_headers_and_signatures():
    assert m._is_apparatus("ON   FATE.")
    assert m._is_apparatus("266  ON    FATE.")
    assert m._is_apparatus("ON    FATE.  265")
    assert m._is_apparatus("OX    FATE.  Z6y")  # OCR-garbled header variant
    assert m._is_apparatus("277")  # bare page number
    assert m._is_apparatus("DE  NAT.  ETC.  T")  # printer's signature
    assert m._is_apparatus("T  2")  # printer's signature


def test_is_apparatus_does_not_flag_body_prose():
    assert not m._is_apparatus("THAT branch of philosophy which, because")
    assert not m._is_apparatus("[The commencement of this treatise is lost.]")
    assert not m._is_apparatus("")
    assert not m._is_apparatus("   ")


# --- residual-garble detector --------------------------------------------------

def test_looks_like_ocr_garble_flags_caret_and_slash_tokens():
    assert m._looks_like_ocr_garble("a^ico/mra")  # raw _GREEK_FIXES left-hand shape
    assert m._looks_like_ocr_garble("^ecDpf/jMara")
    assert m._looks_like_ocr_garble("term/thing")  # bare mid-word slash alone


def test_looks_like_ocr_garble_flags_internal_case_switch():
    assert m._looks_like_ocr_garble("eAc")  # raw _GREEK_FIXES left-hand shape
    assert m._looks_like_ocr_garble("wrH")


def test_looks_like_ocr_garble_does_not_flag_ordinary_english():
    assert not m._looks_like_ocr_garble("Chrysippus")
    assert not m._looks_like_ocr_garble("philosophy")
    assert not m._looks_like_ocr_garble("Œdipus")
    assert not m._looks_like_ocr_garble("dog-star")
    assert not m._looks_like_ocr_garble("ἀξιώματα")  # genuine restored Greek


def test_check_no_residual_garble_passes_clean_text():
    m._check_no_residual_garble("THAT branch of philosophy, ἀξιώματα, Œdipus said — truly.")


def test_check_no_residual_garble_raises_on_garble_token():
    with pytest.raises(ValueError, match="garble-shaped token"):
        m._check_no_residual_garble("the term axioms (a^ico/mra) remains")


def test_check_no_residual_garble_raises_on_unaccounted_nonascii():
    with pytest.raises(ValueError, match="non-ASCII"):
        m._check_no_residual_garble("a stray café accent")  # é is not Greek, not sanctioned


# --- _apply_fixes -------------------------------------------------------------

def test_apply_fixes_replaces_and_counts():
    text = "the veiy much thing"
    out, n = m._apply_fixes(text, [("veiy much", "very much")])
    assert out == "the very much thing"
    assert n == 1


def test_apply_fixes_skips_absent_keys_without_error():
    text = "nothing to see here"
    out, n = m._apply_fixes(text, [("absent key", "replacement")])
    assert out == text
    assert n == 0


def test_apply_fixes_raises_on_duplicate_match():
    text = "twice twice"
    import pytest
    with pytest.raises(ValueError):
        m._apply_fixes(text, [("twice", "once")])


# --- chapter marker regex ------------------------------------------------------

def test_chapter_marker_matches_all_20_romans_in_order():
    for roman in m._ROMAN_CHAPTERS:
        line = f"{roman}.  Some chapter text follows"
        found = m._CHAPTER_MARKER.match(line)
        assert found, roman
        assert found.group(1) == roman


def test_chapter_marker_does_not_false_match_prefix_numeral():
    # "II." must match "II", not stop at "I" -- alternation is longest-first.
    found = m._CHAPTER_MARKER.match("II.  And after some time")
    assert found.group(1) == "II"
    found = m._CHAPTER_MARKER.match("XIX.  As then, says he")
    assert found.group(1) == "XIX"


def test_chapter_marker_rejects_non_chapter_line():
    assert m._CHAPTER_MARKER.match("Vigorously stated the argument") is None


# --- span slicing / apparatus stripping / segmentation (synthetic fixture) ---

def _synthetic_lines():
    return [
        "ON   FATE.",
        "",
        "PREFACE   BY   THE   ORIGINAL   TRANSLATOR.",
        "",
        "OP  all  the  treatises  on  Fate  which  have  come  down  to  us,",
        "this  is  dropped  preface  body  text.",
        "",
        "[The  commencement  of  this  treatise  is  lost.]",
        "I.  *  *  *  THAT  branch  of  philosophy,",
        "which  continues  chapter  one.",
        "",
        "ON    FATE.  265",
        "",
        "II.  And  after  some  time,  he  said,",
        "1  A  good  deal  of  the  original  is  lo^t  here.",
        "chapter  two  continues  here.",
        "[The  rest  of  this  treatise  is  lost.]",
    ]


def test_slice_span_excludes_preface_keeps_brackets():
    lines = _synthetic_lines()
    span = m._slice_span(lines)
    assert span[0].strip() == "[The  commencement  of  this  treatise  is  lost.]".strip()
    assert span[-1].strip() == "[The  rest  of  this  treatise  is  lost.]".strip()
    assert not any("PREFACE" in l for l in span)
    assert not any("dropped preface body" in l for l in span)


def test_strip_apparatus_drops_header_and_footnote_lines():
    lines = _synthetic_lines()
    span = m._slice_span(lines)
    kept = m._strip_apparatus(span, expected_apparatus=1, expected_footnotes=1)
    assert not any(l.strip() == "ON    FATE.  265" for l in kept)
    assert not any("lo^t" in l for l in kept)
    # bracket lines and chapter body survive
    assert any("commencement" in l for l in kept)
    assert any("chapter  one" in l for l in kept)


def test_segment_chapters_two_chapter_fixture():
    lines = _synthetic_lines()
    span = m._slice_span(lines)
    kept = m._strip_apparatus(span, expected_apparatus=1, expected_footnotes=1)
    segments = m._segment_chapters(kept, expected_romans=["I", "II"])
    assert len(segments) == 2
    text0 = m._flatten(segments[0])
    text1 = m._flatten(segments[1])
    assert text0.startswith("[The commencement of this treatise is lost.] * * * THAT")
    assert "chapter one" in text0
    assert text1.startswith("And after some time")
    assert "chapter two continues here." in text1
    assert text1.rstrip().endswith("[The rest of this treatise is lost.]")


def test_segment_chapters_raises_on_wrong_count():
    import pytest
    lines = ["I.  Only one chapter here.", "[The  rest  of  this  treatise  is  lost.]"]
    with pytest.raises(ValueError):
        m._segment_chapters(lines)


# --- concordance gates ---------------------------------------------------------

def test_build_concordance_starts_at_one_and_increases():
    concordance = m.build_concordance()
    records = concordance["records"]
    assert len(records) == 20
    assert records[0]["chapter"] == 1
    assert records[0]["start_section"] == 1
    starts = [r["start_section"] for r in records]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)  # strictly increasing (no ties)
    assert starts[-1] < 48
    assert all(r["exact"] for r in records)


def test_build_concordance_chapter_sequence_is_1_to_20():
    concordance = m.build_concordance()
    chapters = [r["chapter"] for r in concordance["records"]]
    assert chapters == list(range(1, 21))
