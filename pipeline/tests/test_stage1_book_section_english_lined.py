"""Stage 2 of docs/lined-source-plan.md (Q6): once Discourses stops emitting
the Greek `sections` standoff channel in favour of a per-line `sec` field
(stage1_greek's `citation.lined_source`), `_greek_section_starts` must union
`line["sec"]` into its per-column mapping as well -- otherwise the mapping
goes empty and `_validated_paras` silently drops every Oldfather
every-5th-section English marker with a WARNING (a real, visible English
regression the plan calls out by name)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage1_book_section_english import _greek_section_starts


def _numbers(spine: dict) -> dict[str, set[int]]:
    """Just the section NUMBERS `_greek_section_starts` collected per column --
    this file's claim is about which numbers are found, not where in the
    chapter each one starts (see test_paras_marker_position.py for that)."""
    return {col: set(starts) for col, starts in _greek_section_starts(spine).items()}


def test_unions_sec_field_alongside_the_sections_channel():
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"n": 1, "text": "a", "sec": 1},
                {"n": 2, "text": "b", "sec": 1},
                {"n": 3, "text": "c", "sec": 2},
            ]},
        ],
    }
    assert _numbers(spine) == {"1.1": {1, 2}}


def test_sections_channel_still_works_unchanged_for_enchiridion_shaped_input():
    spine = {
        "segments": [
            {"column": "5", "lines": [
                {"n": 1, "text": "whole chapter", "sections": [
                    {"n": 1, "o": 0}, {"n": 2, "o": 6},
                ]},
            ]},
        ],
    }
    assert _numbers(spine) == {"5": {1, 2}}


def test_both_channels_union_into_the_same_set_when_somehow_both_present():
    # Not a real corpus shape (I5 forbids a line carrying both), but the
    # function itself must not assume mutual exclusivity -- it simply unions
    # whatever it finds, per its own docstring.
    spine = {
        "segments": [
            {"column": "1.1", "lines": [
                {"n": 1, "text": "a", "sec": 3, "sections": [{"n": 1, "o": 0}]},
            ]},
        ],
    }
    assert _numbers(spine) == {"1.1": {1, 3}}


def test_a_line_with_neither_channel_contributes_nothing():
    spine = {
        "segments": [
            {"column": "1.1", "lines": [{"n": 1, "text": "a"}]},
        ],
    }
    assert _numbers(spine) == {}


def test_sec_zero_is_never_produced_by_stage1_but_would_still_be_recorded():
    # Defensive: the function itself has no opinion on sec's positive-int
    # invariant (that is stage1_greek's / preflight's job) -- it just unions
    # whatever key is present, including a hypothetically-falsy 0, via an
    # explicit `is not None` check rather than a truthiness check.
    spine = {
        "segments": [
            {"column": "1.1", "lines": [{"n": 1, "text": "a", "sec": 0}]},
        ],
    }
    assert _numbers(spine) == {"1.1": {0}}


def test_real_discourses_manifest_declares_lined_source_not_section_paragraphs():
    # Regression pin for manifests/discourses.yaml's own edit (plan Q4): the
    # pipeline citation block drops `section_paragraphs` in favour of
    # `lined_source` for this one work, so a stale re-add of the old key
    # would silently resurrect the `sections` channel this test file exists
    # to make sure is no longer the only source `_greek_section_numbers`
    # reads.
    import yaml

    data = yaml.safe_load((ROOT / "manifests" / "discourses.yaml").read_text(encoding="utf-8"))
    citation = data["citation"]
    assert citation.get("lined_source") is True
    assert "section_paragraphs" not in citation
