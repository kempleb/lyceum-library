"""Offline unit tests for extract_rackham_fin.py's pure functions. No
corpus/network access required."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import extract_rackham_fin as m  # noqa: E402


def test_lcs_align_exact_sequence():
    target = [2, 3, 4, 5]
    cand_vals = [2, 3, 4, 5]
    mapping = m._lcs_align(target, cand_vals)
    assert mapping == {2: 0, 3: 1, 4: 2, 5: 3}


def test_lcs_align_skips_noise_candidates():
    # footer/footnote numbers interleaved should not derail the alignment
    target = [2, 3, 4]
    cand_vals = [99, 2, 401, 3, 4]
    mapping = m._lcs_align(target, cand_vals)
    assert mapping == {2: 1, 3: 3, 4: 4}


def test_lcs_align_recovers_after_missing_marker():
    # section 3's marker never appears (lost to OCR); 2 and 4 must still align
    target = [2, 3, 4, 5]
    cand_vals = [2, 4, 5]
    mapping = m._lcs_align(target, cand_vals)
    assert 3 not in mapping
    assert mapping[2] == 0
    assert mapping[4] == 1
    assert mapping[5] == 2


def test_lcs_align_uses_one_of_duplicate_candidates_consistently():
    # a repeated value (e.g. a stray duplicate digit) must still yield a
    # single, valid, increasing-order match -- not a crash or a mapping
    # that reuses an index for two different target values.
    target = [2, 3]
    cand_vals = [2, 3, 3]  # trailing stray duplicate "3"
    mapping = m._lcs_align(target, cand_vals)
    assert mapping[2] == 0
    assert cand_vals[mapping[3]] == 3
    assert mapping[2] != mapping[3]


def test_garbage_token_flags_caret_and_glued_case():
    assert m._GARBAGE_TOKEN.search("le^fo^")
    assert m._GARBAGE_TOKEN.search("pMorophyi^to")
    assert m._GARBAGE_TOKEN.search("sful^gof")
    assert not m._GARBAGE_TOKEN.search("Latin")
    assert not m._GARBAGE_TOKEN.search("philosophy")
    assert not m._GARBAGE_TOKEN.search("Brutus,")


def test_dehyph_ok_matches_line_final_hyphen():
    assert m._DEHYPH_OK.search("contemp-")
    assert m._DEHYPH_OK.search("arbi-")
    assert not m._DEHYPH_OK.search("Brutus,")
    assert not m._DEHYPH_OK.search("well-read")  # mid-token hyphen, not at line end context we care about


def test_lead_digit_captures_marker_and_rest():
    m1 = m._LEAD_DIGIT.match("2 of my character and position.")
    assert m1.group(1) == "2"
    assert m1.group(2) == "of my character and position."
    m2 = m._LEAD_DIGIT.match("24 \"Quid ? T. Torquatus\"")
    assert m2.group(1) == "24"


def test_lead_digit_rejects_non_leading_digit_lines():
    assert m._LEAD_DIGIT.match("no digit here") is None


def test_footnote_start_only_a_through_e():
    assert m._FOOTNOTE_START.match("a")
    assert m._FOOTNOTE_START.match("e")
    assert not m._FOOTNOTE_START.match("p")
    assert not m._FOOTNOTE_START.match("z")
    assert not m._FOOTNOTE_START.match("ab")


def test_strip_footnote_tail_drops_genuine_footnote_block():
    lines = [
        ["some", "body", "text."],
        ["a", "This", "book", "was", "called", "Hortensius."],
        ["and", "formed", "an", "introduction."],
    ]
    out = m._strip_footnote_tail(lines)
    assert out == [["some", "body", "text."]]


def test_strip_footnote_tail_keeps_article_a_body_line():
    lines = [
        ["some", "body", "text."],
        ["a", "well-read", "man", "who", "does", "not", "know."],
    ]
    out = m._strip_footnote_tail(lines)
    assert out == lines  # nothing stripped: "well-read" is lowercase, not a footnote


def test_roman_chap_matches_common_numerals():
    for tok in ["I", "II", "III.", "IV", "V.", "VI", "IX", "X."]:
        assert m._ROMAN_CHAP.match(tok), tok
    assert not m._ROMAN_CHAP.match("XV")  # out of the single-digit-chapter range this book uses
