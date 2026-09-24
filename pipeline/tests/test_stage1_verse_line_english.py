from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.config import Manifest
from reader_pipeline.stage1_verse_line_english import (
    build_alignment,
    build_english_chunks,
    reconcile_book,
)


def _manifest(books: list[dict]) -> Manifest:
    data = {
        "work": {"id": "DRNFIX", "language": "lat"},
        "citation": {"scheme": "verse-line", "div_types": {"page": "book"}},
        "books": books,
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


_PRIMARY = {"id": "munro-fixture", "name": "Fixture Translator (test)",
            "model": "archive", "file": "fixture.json"}


# --- reconcile_book: the straddling-line rule -------------------------------


def test_reconcile_book_straddling_line_credited_to_earlier_record():
    records = [
        {"book": 1, "start": 1, "end": 23, "range": "1-23"},
        {"book": 1, "start": 23, "end": 50, "range": "23-50"},
    ]
    reconciled = reconcile_book(records, book_max=50, declared_gaps=set())
    assert reconciled[0]["eff_start"] == 1 and reconciled[0]["end"] == 23
    # The shared boundary line (23) is credited to the EARLIER record, so the
    # later record's effective start moves one past it.
    assert reconciled[1]["eff_start"] == 24 and reconciled[1]["end"] == 50


def test_reconcile_book_plain_abut_needs_no_adjustment():
    records = [
        {"book": 1, "start": 1, "end": 10, "range": "1-10"},
        {"book": 1, "start": 11, "end": 20, "range": "11-20"},
    ]
    reconciled = reconcile_book(records, book_max=20, declared_gaps=set())
    assert reconciled[1]["eff_start"] == 11


# --- reconcile_book: trailer closing ----------------------------------------


def test_reconcile_book_closes_open_trailer_to_book_max():
    records = [
        {"book": 3, "start": 1, "end": 40, "range": "1-40"},
        {"book": 3, "start": 40, "end": None, "range": "40-", "derived": True},
    ]
    reconciled = reconcile_book(records, book_max=50, declared_gaps=set())
    trailer = reconciled[-1]
    assert trailer["end"] == 50
    # The trailer's own start (40) still straddles the prior record's end.
    assert trailer["eff_start"] == 41


def test_reconcile_book_two_open_trailers_fails_loudly():
    records = [
        {"book": 1, "start": 1, "end": None, "range": "1-"},
        {"book": 1, "start": 20, "end": None, "range": "20-"},
    ]
    with pytest.raises(ValueError, match="more than one open-ended"):
        reconcile_book(records, book_max=50, declared_gaps=set())


# --- reconcile_book: declared-gap acceptance / undeclared-gap fatality -----


def test_reconcile_book_declared_gap_is_accepted():
    records = [
        {"book": 3, "start": 1, "end": 25, "range": "1-25"},
        {"book": 3, "start": 27, "end": 50, "range": "27-50"},
    ]
    reconciled = reconcile_book(records, book_max=50, declared_gaps={26})
    assert [r["eff_start"] for r in reconciled] == [1, 27]


def test_reconcile_book_undeclared_gap_fails_loudly():
    records = [
        {"book": 3, "start": 1, "end": 25, "range": "1-25"},
        {"book": 3, "start": 27, "end": 50, "range": "27-50"},
    ]
    with pytest.raises(ValueError, match=r"\[26\]"):
        reconcile_book(records, book_max=50, declared_gaps=set())


def test_reconcile_book_stale_declared_gap_fails_loudly():
    # A single record covers every line -- declaring a gap that turns out to
    # BE covered must fail just as loudly as an undeclared real one.
    records = [{"book": 1, "start": 1, "end": 50, "range": "1-50"}]
    with pytest.raises(ValueError, match="stale declaration"):
        reconcile_book(records, book_max=50, declared_gaps={30})


# --- reconcile_book: overlap fatality ---------------------------------------


def test_reconcile_book_backwards_range_fails_loudly():
    # MAJOR 2(a): a record whose own start > end is not a valid range at all
    # -- reject it up front, before any straddle reconciliation runs.
    records = [{"book": 1, "start": 10, "end": 5, "range": "10-5"}]
    with pytest.raises(ValueError, match="start > end"):
        reconcile_book(records, book_max=50, declared_gaps=set())


def test_reconcile_book_shared_boundary_chain_yields_empty_span_fails_loudly():
    # MAJOR 2(b): an exact shared-boundary CHAIN (1-10, 10-10, 10-20) credits
    # the middle 10-10 record's shared line to the earlier record on BOTH
    # sides, straddle-reconciling it to eff_start=11, end=10 -- an empty span
    # that must not silently contribute zero coverage.
    records = [
        {"book": 1, "start": 1, "end": 10, "range": "1-10"},
        {"book": 1, "start": 10, "end": 10, "range": "10-10"},
        {"book": 1, "start": 10, "end": 20, "range": "10-20"},
    ]
    with pytest.raises(ValueError, match="empty effective span"):
        reconcile_book(records, book_max=20, declared_gaps=set())


def test_reconcile_book_overlap_fails_loudly():
    records = [
        {"book": 1, "start": 1, "end": 30, "range": "1-30"},
        {"book": 1, "start": 20, "end": 50, "range": "20-50"},
    ]
    with pytest.raises(ValueError, match="overlaps"):
        reconcile_book(records, book_max=50, declared_gaps=set())


def test_reconcile_book_first_record_must_start_at_one():
    records = [{"book": 1, "start": 2, "end": 50, "range": "2-50"}]
    with pytest.raises(ValueError, match="expected 1"):
        reconcile_book(records, book_max=50, declared_gaps=set())


def test_reconcile_book_last_record_must_reach_book_max():
    records = [{"book": 1, "start": 1, "end": 40, "range": "1-40"}]
    with pytest.raises(ValueError, match="expected the book max"):
        reconcile_book(records, book_max=50, declared_gaps=set())


# --- build_english_chunks: attachment, including landing inside a lacuna ---
# range div (not just an ordinary plain line) -- "range attachment".


def _spine(segments: list[dict]) -> dict:
    return {"work": "DRNFIX", "edition": "Fixture", "segments": segments,
            "headings": [], "unassigned_lines": []}


def test_build_english_chunks_attaches_to_plain_line_and_into_a_lacuna_range():
    manifest = _manifest(books=[{"n": 1, "start": "1.1", "end": "1.10"}])
    spine = _spine([
        {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "Alfa unum."}]},
        # A lacuna range div collapsing lines 6-9 into one citable division
        # (mirrors stage1_latin._parse_spine_verse's shape for a declared
        # range lacuna) -- line 6, the second record's reconciled start,
        # falls INSIDE this div, not at a plain "1.6" segment of its own.
        {"id": "1:1.6-9", "book": 1, "column": "1.6-9", "lines": [{"n": 1, "text": "", "role": "lacuna"}]},
    ])
    records = [
        {"book": 1, "start": 1, "end": 5, "range": "1-5", "text": " Alpha translation. "},
        {"book": 1, "start": 5, "end": 10, "range": "5-10", "text": "Beta translation."},
    ]
    english = build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=[])
    chunks = {c["id"]: c for c in english["chunks"]}
    assert chunks["1:1.1"]["title"] == "1–5"
    assert chunks["1:1.1"]["text"] == "Alpha translation."  # stripped
    # The straddle credits line 5 to the first record, so the second's
    # effective start is 6 -- inside the lacuna range div, not "1.6".
    assert chunks["1:1.6-9"]["title"] == "6–10"
    assert chunks["1:1.6-9"]["text"] == "Beta translation."
    assert set(chunks) == {"1:1.1", "1:1.6-9"}


def test_build_english_chunks_no_citable_division_fails_loudly():
    manifest = _manifest(books=[{"n": 1, "start": "1.1", "end": "1.10"}])
    # No segment at all for line 1 -- an impossible-but-must-not-silently-
    # mis-attach spine/source drift.
    spine = _spine([])
    records = [{"book": 1, "start": 1, "end": 10, "range": "1-10", "text": "x"}]
    with pytest.raises(ValueError, match="no citable Latin division"):
        build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=[])


def test_build_english_chunks_unknown_book_fails_loudly():
    manifest = _manifest(books=[{"n": 1, "start": "1.1", "end": "1.10"}])
    spine = _spine([{"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "x"}]}])
    records = [{"book": 2, "start": 1, "end": 10, "range": "1-10", "text": "x"}]
    with pytest.raises(ValueError, match="not in the manifest's books list"):
        build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=[])


def test_build_english_chunks_gap_declared_for_a_book_with_no_records_fails_loudly():
    manifest = _manifest(books=[{"n": 1, "start": "1.1", "end": "1.10"}])
    spine = _spine([{"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "x"}]}])
    records = [{"book": 1, "start": 1, "end": 10, "range": "1-10", "text": "x"}]
    with pytest.raises(ValueError, match="no Munro records at all"):
        build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=["2:5"])


def test_build_english_chunks_undeclared_missing_book_fails_loudly():
    # MAJOR 1: a manifest/spine book with NO Munro records at all and no
    # declared english.gaps for it must fail loudly -- it must not be
    # silently skipped just because the coverage loop only ever iterates
    # `by_book` (the books records actually mention), never the manifest's
    # own book list. Book 2 here is a real manifest book but has neither
    # records nor a gap declaration.
    manifest = _manifest(books=[
        {"n": 1, "start": "1.1", "end": "1.5"},
        {"n": 2, "start": "2.1", "end": "2.5"},
    ])
    spine = _spine([
        {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "x"}]},
        {"id": "2:2.1", "book": 2, "column": "2.1", "lines": [{"n": 1, "text": "x"}]},
    ])
    records = [{"book": 1, "start": 1, "end": 5, "range": "1-5", "text": "x"}]
    with pytest.raises(ValueError, match=r"book\(s\) \[2\] have no Munro records"):
        build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=[])


def test_build_english_chunks_duplicate_anchor_segment_id_fails_loudly():
    # MAJOR 2(c): defensive backstop at chunk build -- two records anchoring
    # at the same spine segment id would silently dedupe in downstream keyed
    # consumers (english_by_id.get(seg["id"])). Constructed via a spine where
    # two DIFFERENT lines happen to carry the same segment id (a spine-side
    # bug reconcile_book's own overlap/empty-span checks cannot see, since
    # the two Munro records here don't overlap on the line axis at all).
    manifest = _manifest(books=[{"n": 1, "start": "1.1", "end": "1.10"}])
    spine = _spine([
        {"id": "1:DUP", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "x"}]},
        {"id": "1:DUP", "book": 1, "column": "1.6", "lines": [{"n": 1, "text": "x"}]},
    ])
    records = [
        {"book": 1, "start": 1, "end": 5, "range": "1-5", "text": "Alpha."},
        {"book": 1, "start": 6, "end": 10, "range": "6-10", "text": "Beta."},
    ]
    with pytest.raises(ValueError, match="duplicate chunk anchor"):
        build_english_chunks(manifest, spine, records, _PRIMARY, gap_tokens=[])


# --- build_alignment: scoped to anchor segments only ------------------------


def test_build_alignment_is_scoped_to_anchor_segments_only():
    english = {"work": "DRNFIX", "chunks": [
        {"id": "1:1.1", "book": 1, "column": "1.1", "text": "x", "notes": [], "markers": [], "title": "1–5"},
    ]}
    alignment = build_alignment(english)
    assert alignment == {
        "work": "DRNFIX",
        "pairs": [{"segment": "1:1.1", "english": "1:1.1"}],
        "english_only": [],
    }
