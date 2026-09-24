"""Structural gate for `sources/yonge-finibus/concordance.json` (Wave --
De Finibus English phase 2: the Yonge-chapter -> PHI-Latin-section
concordance, book-section scheme, De Fato chapter-concordance shape at
5-book scale -- see that file's own header and
`stage1_chapter_concordance_english.py`'s module docstring for the shared
mechanism this data feeds). This is a data-only gate: it validates the
concordance file's own internal invariants (every section of every book
covered exactly once, chapter counts matching phase 1, strictly
increasing anchors, valid hash format) without needing the licensed PHI
Latin export or the multi-book manifest wiring, neither of which exist
yet (phase 3, out of scope here). No corpus text is read or asserted
against -- `anchor_lat_sha256_16` stays a hash throughout, exactly as
`sources/yonge-fato/concordance.json`'s own convention requires."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONCORDANCE_PATH = ROOT / "sources" / "yonge-finibus" / "concordance.json"

# Phase 1 chapter counts (Yonge's chapter divisions per book) and the live
# PHI section counts per book (`manifests/de-finibus.yaml`'s own declared
# `section_spine`: 72/119/76/80/96, total 443).
BOOK_CHAPTERS = {1: 21, 2: 35, 3: 22, 4: 28, 5: 32}
BOOK_SECTIONS = {1: 72, 2: 119, 3: 76, 4: 80, 5: 96}

_ALLOWED_SECTION_POSITIONS = {"start", "mid", "end"}
_HASH_RE = re.compile(r"[0-9a-f]{16}")


def _load_records():
    data = json.loads(CONCORDANCE_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and isinstance(data.get("records"), list)
    return data["records"]


def _by_book(records):
    out = {}
    for r in records:
        out.setdefault(r["book"], []).append(r)
    for book in out:
        out[book].sort(key=lambda r: r["chapter"])
    return out


def test_total_record_count():
    records = _load_records()
    assert len(records) == sum(BOOK_CHAPTERS.values()) == 138


def test_record_schema():
    records = _load_records()
    for r in records:
        assert set(r) == {
            "book", "chapter", "start_section", "exact",
            "section_position", "anchor_lat_sha256_16", "anchor_lat_note",
            "anchor_en",
        }
        assert r["book"] in BOOK_CHAPTERS
        assert isinstance(r["chapter"], int) and not isinstance(r["chapter"], bool)
        assert isinstance(r["start_section"], int) and not isinstance(r["start_section"], bool)
        assert r["exact"] is True
        assert r["section_position"] in _ALLOWED_SECTION_POSITIONS
        assert _HASH_RE.fullmatch(r["anchor_lat_sha256_16"])
        assert isinstance(r["anchor_lat_note"], str) and r["anchor_lat_note"]
        assert isinstance(r["anchor_en"], str) and r["anchor_en"].strip()


def test_chapter_counts_match_phase_1():
    by_book = _by_book(_load_records())
    for book, n in BOOK_CHAPTERS.items():
        chapters = [r["chapter"] for r in by_book[book]]
        assert chapters == list(range(1, n + 1)), (book, chapters)


def test_no_duplicate_chapter_across_book():
    records = _load_records()
    keys = [(r["book"], r["chapter"]) for r in records]
    assert len(keys) == len(set(keys))


def test_start_sections_strictly_increasing_per_book():
    by_book = _by_book(_load_records())
    for book, recs in by_book.items():
        starts = [r["start_section"] for r in recs]
        assert all(starts[i] < starts[i + 1] for i in range(len(starts) - 1)), (book, starts)


def test_first_chapter_starts_at_book_minimum_section():
    by_book = _by_book(_load_records())
    for book, recs in by_book.items():
        assert recs[0]["start_section"] == 1, (book, recs[0])


def test_no_start_section_beyond_book_max():
    by_book = _by_book(_load_records())
    for book, recs in by_book.items():
        assert recs[-1]["start_section"] <= BOOK_SECTIONS[book], (book, recs[-1])
        for r in recs:
            assert 1 <= r["start_section"] <= BOOK_SECTIONS[book]


def test_every_section_covered_exactly_once_per_book():
    """The coverage gate: constructing each chapter's span the same way
    `stage1_chapter_concordance_english.build_spans` does (end_section =
    next chapter's start_section - 1, or book_max for the last chapter)
    must walk every section 1..book_max in each book exactly once -- no
    gap, no overlap."""
    by_book = _by_book(_load_records())
    total = 0
    for book, recs in by_book.items():
        book_max = BOOK_SECTIONS[book]
        covered = []
        for i, r in enumerate(recs):
            start = r["start_section"]
            end = recs[i + 1]["start_section"] - 1 if i + 1 < len(recs) else book_max
            assert start <= end, (book, r["chapter"], start, end)
            covered.extend(range(start, end + 1))
        assert covered == list(range(1, book_max + 1)), book
        total += len(covered)
    assert total == sum(BOOK_SECTIONS.values()) == 443


def test_anchor_en_is_non_trivial_prefix_of_its_own_chapter():
    """Loose sanity check mirroring the builder's own Blocker-1 concern
    (English-side drift): `anchor_en` must be a real, multi-word snippet
    -- not a placeholder -- so a later manifest-wiring pass has something
    for `_anchor_en_opens_chapter`-style verification to check against the
    real `yonge-finibus/yonge.clean.json` chapter text."""
    for r in _load_records():
        words = r["anchor_en"].split()
        assert len(words) >= 5, r
