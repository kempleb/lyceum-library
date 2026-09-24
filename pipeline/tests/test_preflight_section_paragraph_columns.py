"""Regression tests for `citation.section_paragraph_columns` (item 85's
Melissus B7/B8 addendum) -- preflight._validate_section_paragraph_columns.

Unlike citation.whole_column_verbatim, this is not an anti-fabrication
attestation (it asserts nothing about which words are the author's own), so
it takes a bare list of column names, not a per-column justified object. The
gate only checks: the declaration's own shape, that a named column is
actually emitted, and that both its Greek and its English carry at least 2
markers forming one ascending "(N)" run -- otherwise the split has nothing
to key off and would silently no-op in the reader."""

from __future__ import annotations

from pathlib import Path

from reader_pipeline.preflight import WorkManifest, _validate_section_paragraph_columns


def _manifest(extra: dict | None = None) -> WorkManifest:
    data = {
        "work": {"id": "FIX", "author": "fixture"},
        "citation": {"scheme": "dk", "series": "B"},
        "books": [{"n": 1, "start": "B1", "end": "B8"}],
    }
    data.update(extra or {})
    return WorkManifest(work_id="FIX", path=Path("FIX.yaml"), data=data)


def _seg(column: str, greek_texts: list[str], english_text: str) -> dict:
    return {
        "column": column,
        "greek": [{"role": "context", "text": t} for t in greek_texts],
        "english": {"text": english_text},
    }


def _with_declared(declared) -> WorkManifest:
    return _manifest({"citation": {"scheme": "dk", "series": "B",
                                    "section_paragraph_columns": declared}})


def test_no_declaration_is_a_silent_no_op():
    loaded = {"book-01.json": {"segments": [_seg("B1", ["plain text"], "plain text")]}}
    problems: list = []
    _validate_section_paragraph_columns(_manifest(), loaded, problems)
    assert problems == []


def test_declared_column_with_two_ascending_markers_on_both_sides_passes():
    loaded = {"book-01.json": {"segments": [
        _seg("B7", ["Simplicius says. (1)", "Melissus speaking. (2) more."],
             "(1) Simplicius says. (2) Melissus speaking more."),
    ]}}
    problems: list = []
    _validate_section_paragraph_columns(_with_declared(["B7"]), loaded, problems)
    assert problems == []


def test_declaration_must_be_a_non_empty_list_of_strings():
    for bad in (True, "B7", {"B7": {}}, [], [1, 2]):
        loaded = {"book-01.json": {"segments": [_seg("B7", ["(1) a. (2) b."], "(1) a. (2) b.")]}}
        problems: list = []
        _validate_section_paragraph_columns(_with_declared(bad), loaded, problems)
        assert any("non-empty list" in p[2] for p in problems), bad


def test_naming_an_unemitted_column_is_fatal():
    loaded = {"book-01.json": {"segments": [_seg("B7", ["(1) a. (2) b."], "(1) a. (2) b.")]}}
    problems: list = []
    _validate_section_paragraph_columns(_with_declared(["B999"]), loaded, problems)
    assert any("B999" in p[2] and "does not carry" in p[2] for p in problems)


def test_greek_with_fewer_than_two_ascending_markers_is_fatal():
    loaded = {"book-01.json": {"segments": [
        _seg("B7", ["only one marker (1) here"], "(1) a. (2) b."),
    ]}}
    problems: list = []
    _validate_section_paragraph_columns(_with_declared(["B7"]), loaded, problems)
    assert any("B7" in p[2] and "Greek carries fewer than 2" in p[2] for p in problems)


def test_english_with_fewer_than_two_ascending_markers_is_fatal():
    loaded = {"book-01.json": {"segments": [
        _seg("B7", ["(1) a. (2) b."], "only one marker (1) here"),
    ]}}
    problems: list = []
    _validate_section_paragraph_columns(_with_declared(["B7"]), loaded, problems)
    assert any("B7" in p[2] and "English carries fewer than 2" in p[2] for p in problems)


def test_out_of_sequence_repeats_do_not_count_toward_the_ascending_run():
    # "(2) ... (2) ... " never ascends past 2 -- not 2 distinct ascending
    # markers, so this is fatal, same as only ever writing "(2)" once.
    loaded = {"book-01.json": {"segments": [
        _seg("B7", ["(2) a. (2) b."], "(1) a. (2) b."),
    ]}}
    problems: list = []
    _validate_section_paragraph_columns(_with_declared(["B7"]), loaded, problems)
    assert any("B7" in p[2] and "Greek carries fewer than 2" in p[2] for p in problems)
