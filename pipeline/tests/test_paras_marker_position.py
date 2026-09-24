"""REVIEW-CHECKLIST item 100: an English section marker must sit WHERE its
number says, not merely carry a number the chapter's Greek happens to
contain.

Discourses 3.3's first Wikisource marker is labelled 10 but sits at the
sentence translating Greek section 5 ("That is why the good is preferred
above every form of kinship" = Διὰ τοῦτο πάσης οἰκειότητος προκρίνεται τὸ
ἀγαθόν), about a thousand characters before section 10's English. The old
`_validated_paras` passed it: 10 IS one of the chapter's 22 Greek section
numbers. Nothing was visibly wrong once the markers left the display, but
the bad data point stayed in the source file, waiting for the day the
markers are revived for Greek-English alignment.

The tests below use the REAL English chapter text and the REAL markers from
sources/oldfather-epictetus/. The Greek side is supplied as a plain uniform
model (22 equal sections, so section n starts at (n-1)/22 of the chapter) --
no corpus text or corpus-derived measurement is committed here, and the
model is blunt enough that the three sound markers clear it with room to
spare while the mislabelled one misses by 21 points of the chapter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage1_book_section_english import (
    _PARA_POSITION_TOLERANCE,
    _greek_section_starts,
    _validated_paras,
)

SOURCES = ROOT / "sources" / "oldfather-epictetus"


def _real_paras() -> dict[str, list[dict]]:
    return json.loads(
        (SOURCES / "oldfather-discourses-paras.json").read_text(encoding="utf-8"))


def _real_chapter_text(column: str) -> str:
    data = json.loads(
        (SOURCES / "oldfather-discourses.clean.json").read_text(encoding="utf-8"))
    return data[column].strip()


def _uniform_greek_starts(sections: int) -> dict[int, float]:
    """{section number: fraction of the chapter's Greek that precedes it} for
    a chapter modelled as `sections` equal-length sections."""
    return {n: (n - 1) / sections for n in range(1, sections + 1)}


def test_the_3_3_marker_at_greek_section_5_is_labelled_5():
    # The data point itself (item 100). Offset 1096 is the start of "That is
    # why the good is preferred above every form of kinship" -- Greek 3.3.5.
    first = _real_paras()["3.3"][0]
    assert first == {"n": 5, "o": 1096}


def test_the_mislabelled_3_3_marker_would_fail_loud():
    # The file's pre-fix content, replayed against the real chapter text: a
    # marker labelled 10 at the offset where section 5 begins. (Measured
    # against the real Greek the gap is 19 points of the chapter; against the
    # uniform model here it is 21.)
    text = _real_chapter_text("3.3")
    paras = [{"n": 10, "o": 1096}, {"n": 15, "o": 3364}, {"n": 20, "o": 4957}]
    with pytest.raises(ValueError) as excinfo:
        _validated_paras("EPICT-DISC", "3.3", text, paras,
                         _uniform_greek_starts(22))
    message = str(excinfo.value)
    assert "EPICT-DISC" in message
    assert "book 3" in message and "chapter 3" in message
    assert "n=10" in message


def test_the_repaired_3_3_markers_pass():
    text = _real_chapter_text("3.3")
    paras = _real_paras()["3.3"]
    assert _validated_paras("EPICT-DISC", "3.3", text, paras,
                            _uniform_greek_starts(22)) == paras


def test_a_marker_drifting_less_than_the_tolerance_is_kept():
    # Translation is not a character-for-character map, so a marker is never
    # expected to land exactly on its section's Greek fraction -- the gate
    # only catches a marker that names the wrong section, not ordinary drift.
    text = "x" * 1000
    drift = int(1000 * (0.5 + _PARA_POSITION_TOLERANCE / 2))
    assert _validated_paras("W", "1.1", text, [{"n": 2, "o": drift}],
                            {1: 0.0, 2: 0.5}) == [{"n": 2, "o": drift}]


# ---------------------------------------------------------------------------
# _greek_section_starts itself: exact fractions from a synthetic spine, so a
# bug in the join/offset/denominator arithmetic would fail these even though
# every test above either discards the real fractions or injects its own.
# Synthetic ASCII text only -- never corpus text.
# ---------------------------------------------------------------------------

def test_a_section_spanning_several_lines_counts_the_join():
    # seg["lines"] joined the way stage1_greek flattens a chapter: with a
    # single space between each line's text. Section 1 starts at the very
    # first character of line 0 (offset 0). Section 2's own `o` is relative
    # to line 1's text, so its position in the JOINED text is line 0's
    # length (3) + 1 for the join space + its own o (1) = 4.
    #   joined = "abc" + " " + "de" = "abc de"  (len 6)
    #   section 1: run(0) + o(0) = 0            -> 0/6 = 0.0
    #   section 2: run(4) + o(1) = 5            -> 5/6 = 0.833333...
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "abc", "sections": [{"n": 1, "o": 0}]},
                {"text": "de", "sections": [{"n": 2, "o": 1}]},
            ]},
        ],
    }
    starts = _greek_section_starts(spine)["1.1"]
    assert starts[1] == pytest.approx(0 / 6, abs=1e-9)
    assert starts[2] == pytest.approx(5 / 6, abs=1e-9)


def test_a_section_number_repeated_on_a_later_line_keeps_the_first_start():
    # Section 1 is (re-)declared on line 1 too; its start must stay the line
    # 0 offset, not move to line 1's.
    #   joined = "aaa" + " " + "bbb" = "aaa bbb"  (len 7)
    #   section 1: first seen at run(0) + o(0) = 0      -> 0/7
    #   section 2: run(4) + o(1) = 5                    -> 5/7
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "aaa", "sections": [{"n": 1, "o": 0}]},
                {"text": "bbb", "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 1}]},
            ]},
        ],
    }
    starts = _greek_section_starts(spine)["1.1"]
    assert starts[1] == pytest.approx(0 / 7, abs=1e-9)
    assert starts[2] == pytest.approx(5 / 7, abs=1e-9)


def test_an_empty_line_inside_a_column_contributes_only_the_join_space():
    # An empty line's own text is "", so it adds nothing but the join
    # separator on either side of it.
    #   joined = "ab" + " " + "" + " " + "cd" = "ab  cd"  (len 6)
    #   section 1: run(0) + o(0) = 0                     -> 0/6
    #   section 2: run(2+1 + 0+1) + o(0) = 4 + 0 = 4      -> 4/6
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "ab", "sections": [{"n": 1, "o": 0}]},
                {"text": "", "sections": []},
                {"text": "cd", "sections": [{"n": 2, "o": 0}]},
            ]},
        ],
    }
    starts = _greek_section_starts(spine)["1.1"]
    assert starts[1] == pytest.approx(0 / 6, abs=1e-9)
    assert starts[2] == pytest.approx(4 / 6, abs=1e-9)


def test_leading_and_trailing_whitespace_in_a_lines_text_is_not_stripped():
    # The helper applies no normalisation of its own: a line's text is used
    # exactly as given, so whitespace inside it counts as ordinary
    # characters in both the join and the offset arithmetic.
    #   joined = "ab " + " " + " cd" = "ab   cd"  (len 7)
    #   section 1: run(0) + o(0) = 0                    -> 0/7
    #   section 2: run(3+1) + o(1) = 4 + 1 = 5           -> 5/7
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "ab ", "sections": [{"n": 1, "o": 0}]},
                {"text": " cd", "sections": [{"n": 2, "o": 1}]},
            ]},
        ],
    }
    starts = _greek_section_starts(spine)["1.1"]
    assert starts[1] == pytest.approx(0 / 7, abs=1e-9)
    assert starts[2] == pytest.approx(5 / 7, abs=1e-9)


def test_the_last_section_of_a_column_starts_before_the_end():
    #   joined = "aaaa" + " " + "bb" = "aaaa bb"  (len 7)
    #   section 2 (last): run(5) + o(0) = 5              -> 5/7 < 1.0
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "aaaa", "sections": [{"n": 1, "o": 0}]},
                {"text": "bb", "sections": [{"n": 2, "o": 0}]},
            ]},
        ],
    }
    starts = _greek_section_starts(spine)["1.1"]
    assert starts[2] == pytest.approx(5 / 7, abs=1e-9)
    assert starts[2] < 1.0


def test_a_column_with_exactly_one_section_starts_at_zero():
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"text": "hello", "sections": [{"n": 1, "o": 0}]},
            ]},
        ],
    }
    assert _greek_section_starts(spine)["1.1"] == {1: pytest.approx(0.0)}


def test_a_column_with_empty_greek_text_is_skipped_entirely():
    spine = {
        "segments": [
            {"column": "1.1", "lines": [{"text": "", "sections": []}]},
        ],
    }
    assert _greek_section_starts(spine) == {}


# ---------------------------------------------------------------------------
# One end-to-end test: synthetic spine + synthetic English text + markers,
# through _validated_paras with NO injected fractions -- _greek_section_starts
# runs for real.
# ---------------------------------------------------------------------------

def _synthetic_spine() -> dict:
    # joined Greek = "a"*9 + " " + "b"*10  (len 20)
    # section 1: run(0) + o(0) = 0    -> 0/20 = 0.0
    # section 2: run(10) + o(0) = 10  -> 10/20 = 0.5
    return {
        "segments": [
            {"column": "9.9", "lines": [
                {"text": "a" * 9, "sections": [{"n": 1, "o": 0}]},
                {"text": "b" * 10, "sections": [{"n": 2, "o": 0}]},
            ]},
        ],
    }


def test_end_to_end_a_correctly_placed_marker_passes_with_real_fractions():
    greek_starts = _greek_section_starts(_synthetic_spine())["9.9"]
    text = "x" * 100
    paras = [{"n": 2, "o": 50}]  # 50/100 = 0.5, matching Greek section 2's 0.5
    assert _validated_paras("W", "9.9", text, paras, greek_starts) == paras


def test_end_to_end_a_mislabelled_marker_raises_with_real_fractions():
    greek_starts = _greek_section_starts(_synthetic_spine())["9.9"]
    text = "x" * 100
    # 90/100 = 0.9, 0.4 away from Greek section 2's 0.5 -- well past tolerance
    paras = [{"n": 2, "o": 90}]
    with pytest.raises(ValueError):
        _validated_paras("W", "9.9", text, paras, greek_starts)


# ---------------------------------------------------------------------------
# Mixed int/str section labels must not crash the membership-warning path.
# ---------------------------------------------------------------------------

def test_mixed_type_greek_start_keys_warn_and_drop_instead_of_raising(capsys):
    greek_starts = {1: 0.0, "5a": 0.5}
    text = "x" * 100
    paras = [{"n": "missing", "o": 10}]
    result = _validated_paras("W", "1.1", text, paras, greek_starts)
    assert result == []
    assert "WARNING" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The error message: one decimal place of precision, and the tolerance's
# provenance/re-measurement sentence.
# ---------------------------------------------------------------------------

def test_error_message_uses_one_decimal_place_of_precision():
    text = "x" * 3
    paras = [{"n": 1, "o": 2}]  # 2/3 = 66.666...% english_at
    greek_starts = {1: 0.0}
    with pytest.raises(ValueError) as excinfo:
        _validated_paras("W", "1.1", text, paras, greek_starts)
    message = str(excinfo.value)
    assert "66.7%" in message
    assert "0.0%" in message
    assert "12.0%" in message


def test_error_message_explains_the_tolerance_is_discourses_measured_only():
    text = "x" * 3
    paras = [{"n": 1, "o": 2}]
    greek_starts = {1: 0.0}
    with pytest.raises(ValueError) as excinfo:
        _validated_paras("W", "1.1", text, paras, greek_starts)
    assert (
        "If the marker is right and the translation is simply uneven here, "
        "the tolerance (measured on the Discourses only) needs "
        "re-measuring for this work."
    ) in str(excinfo.value)
