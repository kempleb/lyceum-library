from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.refs import (
    column_key,
    column_prefix_key,
    column_range,
    line_key,
    ref_key,
)

BOOK_SECTION = scheme_mod.get("book-section")
SECTION = scheme_mod.get("section")


def test_column_and_ref_keys_round_trip_to_normalized_strings():
    page, side = column_key("1094a")
    assert f"{page}{side}" == "1094a"

    page, side, line = ref_key("1094a1")
    assert f"{page}{side}{line}" == "1094a1"

    assert line_key("1094a", 1) == ref_key("1094a1")


def test_bekker_sort_order_places_columns_before_lines_before_next_side():
    refs = ["1094b", "1094a1", "1094a", "1095a1", "1094b1"]

    assert sorted(refs, key=lambda r: (*column_key(r), -1) if r[-1] in "ab" else ref_key(r)) == [
        "1094a",
        "1094a1",
        "1094b",
        "1094b1",
        "1095a1",
    ]


def test_column_range_includes_both_sides_and_honors_boundaries():
    assert column_range("1094b", "1096a") == ["1094b", "1095a", "1095b", "1096a"]


# --- Stephanus a-e support (page+section letter) -----------------------------

def test_stephanus_columns_and_refs_parse_across_a_to_e():
    for letter in "abcde":
        page, sec = column_key(f"17{letter}")
        assert (page, sec) == (17, letter)
        p, s, line = ref_key(f"17{letter}3")
        assert (p, s, line) == (17, letter, 3)


def test_letter_ordering_places_17e_before_18a():
    # A section-letter boundary must order before the next page's first section.
    assert column_key("17e") < column_key("18a")
    assert ref_key("17e10") < ref_key("18a1")


def test_mid_letter_span_orders_within_a_page():
    refs = ["5e2", "5c1", "5a4", "5c9"]
    assert sorted(refs, key=ref_key) == ["5a4", "5c1", "5c9", "5e2"]


@pytest.mark.parametrize("value", ["1094", "1094f", "1094a1", "a1094"])
def test_column_key_rejects_malformed_columns(value):
    with pytest.raises(ValueError, match="not a column token"):
        column_key(value)


@pytest.mark.parametrize("value", ["1094a", "1094", "1094f1", "1094aX"])
def test_ref_key_rejects_malformed_refs(value):
    with pytest.raises(ValueError, match="not a ref"):
        ref_key(value)


# --- book-section dotted tokens (Marcus "4.23", Diogenes Laertius "7.85") ----

def test_book_section_column_parses_book_and_section_as_ints():
    assert column_key("4.23", BOOK_SECTION) == (4, 23)
    assert column_key("7.85", BOOK_SECTION) == (7, 85)
    # ref grammar is the same dotted token (no user-facing line component).
    assert ref_key("4.23", BOOK_SECTION) == (4, 23)
    assert column_prefix_key("4.23", BOOK_SECTION) == (4, 23)
    assert line_key("4.23", 5, BOOK_SECTION) == (4, 23, 5)


def test_book_section_section_sorts_numerically_not_lexicographically():
    # The lexicographic trap: as strings "4.10" < "4.9"; numerically 9 < 10.
    assert column_key("4.9", BOOK_SECTION) < column_key("4.10", BOOK_SECTION)
    cols = ["4.10", "4.2", "4.9", "3.1", "4.1", "10.1"]
    assert sorted(cols, key=lambda c: column_key(c, BOOK_SECTION)) == [
        "3.1",
        "4.1",
        "4.2",
        "4.9",
        "4.10",
        "10.1",
    ]


@pytest.mark.parametrize("value", ["4a", "4", "4.", ".23", "4.23.5", "17e"])
def test_book_section_rejects_non_dotted_tokens(value):
    with pytest.raises(ValueError, match="not a column token"):
        column_key(value, BOOK_SECTION)



# --- section flat bookless chapter grammar (Epictetus' Enchiridion "5") -----

def test_section_column_parses_a_bare_chapter_integer():
    assert column_key("5", SECTION) == (5, None)
    assert column_key("10", SECTION) == (10, None)
    # ref grammar is the same bare-integer token (no user-facing line).
    assert ref_key("5", SECTION) == (5, None)


def test_section_chapters_sort_numerically_not_lexicographically():
    # The lexicographic trap: as strings "10" < "2"; numerically 2 < 10.
    assert column_key("2", SECTION) < column_key("10", SECTION)
    cols = ["10", "2", "1", "9"]
    assert sorted(cols, key=lambda c: column_key(c, SECTION)) == ["1", "2", "9", "10"]


@pytest.mark.parametrize("value", ["1.5", "5a", "5.", "", "a5"])
def test_section_rejects_non_flat_tokens(value):
    with pytest.raises(ValueError, match="not a column token"):
        column_key(value, SECTION)


# TS/Python parity: the SAME case list as citation.test.ts's "flat grammar
# parity" block. Both registries must agree exactly: ASCII digits only, outer
# whitespace trimmed, internal whitespace rejected (never collapsed into a
# different number), and no Unicode digits (Python \d would match "٥"; JS \d
# would not — the flat regex pins [0-9]).
@pytest.mark.parametrize("value,expected", [
    ("5", (5, None)),      # bare chapter
    (" 5 ", (5, None)),    # outer whitespace trimmed
    ("5 0", None),         # internal whitespace REJECTED, not collapsed to 50
    ("٥", None),           # Unicode (Arabic-Indic) digit rejected
    ("05", (5, None)),     # leading zero accepted (same int)
    ("", None),
])
def test_section_grammar_parity_with_citation_ts(value, expected):
    if expected is None:
        with pytest.raises(ValueError):
            column_key(value, SECTION)
    else:
        assert column_key(value, SECTION) == expected


def test_default_grammar_unchanged_when_no_scheme_passed():
    # Passing no scheme keeps the shared a-e grammar (bekker/busse/stephanus).
    assert column_key("17e") == (17, "e")
    assert ref_key("1094a15") == (1094, "a", 15)
    assert column_prefix_key("357a1") == (357, "a")


# --- dk (Diels-Kranz fragment/testimonium) grammar --------------------------

DK = scheme_mod.get("dk")
DK_VERSE = scheme_mod.for_manifest({"citation": {"scheme": "dk", "lines": True}})


def test_dk_column_parses_series_number_suffix():
    assert column_key("B30", DK) == ("B", 30, "")
    assert column_key("B84a", DK) == ("B", 84, "a")
    assert column_key("A1a", DK) == ("A", 1, "a")
    # lineless: ref grammar IS the column grammar
    assert ref_key("B30", DK) == ("B", 30, "")


def test_dk_columns_sort_numerically_with_suffix_after_bare():
    # B1 < B2 < ... < B9 < B10 (numeric, never lexicographic); B84 < B84a <
    # B84b; B126 < B126a < B126b — matches DK's own ordering.
    cols = ["B10", "B2", "B1", "B84b", "B84", "B84a", "B9"]
    assert sorted(cols, key=lambda c: column_key(c, DK)) == [
        "B1", "B2", "B9", "B10", "B84", "B84a", "B84b",
    ]


def test_dk_column_prefix_key_bare_column_is_the_whole_token():
    # dk is bookless (like `section`) — a bare column IS the whole prefix key.
    assert column_prefix_key("B30", DK) == column_key("B30", DK)


@pytest.mark.parametrize("value", ["C1", "b1", "B", "B1A", "30", "B1.5", ""])
def test_dk_rejects_malformed_columns(value):
    with pytest.raises(ValueError, match="not a column token"):
        column_key(value, DK)


def test_dk_verse_ref_grammar_parses_column_dot_line():
    assert ref_key("B8.34", DK_VERSE) == ("B", 8, "", 34)
    assert ref_key("B15a.2", DK_VERSE) == ("B", 15, "a", 2)
    # the bare column grammar itself is unchanged by the override
    assert column_key("B8", DK_VERSE) == ("B", 8, "")


def test_dk_verse_column_prefix_key_strips_the_line_component():
    assert column_prefix_key("B8.34", DK_VERSE) == column_key("B8", DK_VERSE)


def test_dk_column_range_never_enumerated():
    # dk's validation_mode is "observed" — real gaps (B84/B109) make a
    # rectangular range meaningless; callers must never call column_range for
    # it (see refs.py's module docstring). Not a runtime guard (column_range
    # is Bekker-shaped and would simply produce nonsense on a dk token), so
    # this test documents the contract via validation_mode instead.
    assert DK.validation_mode == "observed"


# --- dk no_series (Pythagoras, DK 14 — no series letter at all) -------------

DK_NO_SERIES = scheme_mod.for_manifest({"citation": {"scheme": "dk", "no_series": True}})


def test_dk_no_series_column_parses_number_suffix_with_empty_series():
    # Same 3-tuple shape as a series-bearing dk column (see column_key's doc
    # comment) -- the empty leading group keeps every existing consumer
    # (stage1_greek's f"{series}{n}" composition, this function) unchanged.
    assert column_key("7", DK_NO_SERIES) == ("", 7, "")
    assert column_key("6a", DK_NO_SERIES) == ("", 6, "a")
    assert ref_key("7", DK_NO_SERIES) == ("", 7, "")  # lineless: ref IS column


def test_dk_no_series_columns_sort_numerically():
    cols = ["10", "2", "1", "6a", "6", "9"]
    assert sorted(cols, key=lambda c: column_key(c, DK_NO_SERIES)) == [
        "1", "2", "6", "6a", "9", "10",
    ]


@pytest.mark.parametrize("value", ["B7", "A7", "7A", "b7", ""])
def test_dk_no_series_rejects_series_letter_forms(value):
    with pytest.raises(ValueError, match="not a column token"):
        column_key(value, DK_NO_SERIES)
