"""Unit tests for stage1_chapter_concordance_english.py (De Fato / Yonge's
chapter-level concordance attachment), plus targeted regression tests for
the adjacent preflight.py / __main__.py dispatch fixes from the same
adversarial-review round (Sol). SYNTHETIC FIXTURES ONLY, per this repo's
zero-tolerance rule: every Latin-looking token below is an invented
placeholder (never real TLG/PHI corpus text), and every English sentence is
invented too (never a verbatim Yonge sentence). Anchor hashes are computed
locally with the documented convention (sha256 of the whitespace-normalized
phrase, first 16 hex chars) over these synthetic phrases only."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.config import Manifest
from reader_pipeline.preflight import WorkManifest, _validate_manifest_schema
from reader_pipeline.stage1_chapter_concordance_english import (
    build_alignment,
    build_english_chunks,
    build_spans,
    load_chapters,
    load_concordance,
    verify_anchor,
)


def _hash(phrase: str) -> str:
    norm = re.sub(r"\s+", " ", phrase).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _manifest(books: list[dict], exclude_sections: list[str] | None = None) -> Manifest:
    data = {
        "work": {"id": "FATOFIX", "language": "lat"},
        "citation": {"scheme": "section", "div_types": {"page": "section"},
                     **({"exclude_sections": exclude_sections} if exclude_sections else {})},
        "books": books,
    }
    return Manifest(data, ROOT / "manifests" / "fake-fato.yaml")


def _spine(section_texts: dict[int, str]) -> dict:
    """A synthetic flat-scheme Latin spine: one segment per section, each
    carrying invented placeholder text (never real PHI corpus text)."""
    return {
        "segments": [
            {"id": f"1:{n}", "book": 1, "column": str(n),
             "lines": [{"n": 1, "text": text}]}
            for n, text in sorted(section_texts.items())
        ],
    }


_PRIMARY = {"id": "fixture-fato", "name": "Fixture Translator (test)",
            "model": "chapter_concordance", "file": "fixture.json",
            "concordance": "fixture-concordance.json"}

# Invented, non-verbatim placeholder "Latin" text per synthetic section.
_SECTION_TEXT = {
    1: "wordalfa wordbeta wordgamma worddelta wordepsilon",
    2: "wordzeta wordeta wordtheta wordiota",
    3: "wordkappa wordlambda wordmu wordnu wordxi wordomicron",
}


def _default_anchor_en(chapter: int) -> str:
    return f"invented placeholder English opening for chapter {chapter}"


def _chapter_text(chapter: int) -> str:
    """Synthetic English chapter text whose opening literally IS
    `_default_anchor_en(chapter)` -- keeps every fixture below satisfying the
    Blocker-1 anchor_en-opens-chapter check by construction, without every
    test having to hand-craft matching prose. Never a verbatim Yonge
    sentence."""
    return f"{_default_anchor_en(chapter)} -- invented placeholder prose continues here."


def _concordance_record(
    chapter: int, section: int, anchor_words: str,
    anchor_en: str | None = None, section_position: str = "start", book: int = 1,
) -> dict:
    return {
        "book": book,
        "chapter": chapter,
        "start_section": section,
        "exact": True,
        "section_position": section_position,
        "anchor_lat_sha256_16": _hash(anchor_words),
        "anchor_lat_note": "synthetic fixture anchor, non-verbatim",
        "anchor_en": anchor_en if anchor_en is not None else _default_anchor_en(chapter),
    }


def _multi_book_spine(book_section_texts: dict[int, dict[int, str]]) -> dict:
    """A synthetic book-section-scheme Latin spine (De Finibus' real
    shape): one segment per (book, section), column a dotted "book.section"
    token -- mirrors stage1_latin's own `compose_column(book, n)` output for
    this scheme. Each text is an invented, non-verbatim placeholder."""
    segments = []
    for book, section_texts in sorted(book_section_texts.items()):
        for n, text in sorted(section_texts.items()):
            segments.append({
                "id": f"{book}:{book}.{n}", "book": book, "column": f"{book}.{n}",
                "lines": [{"n": 1, "text": text}],
            })
    return {"segments": segments}


# --- load_chapters ------------------------------------------------------


def test_load_chapters_happy_path(tmp_path):
    """No `book` key at all (De Fato's real source shape) -- every record
    defaults to book 1."""
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"chapter": 1, "text": "Invented placeholder chapter one."}, '
        '{"chapter": 2, "text": "Invented placeholder chapter two."}]',
        encoding="utf-8",
    )
    chapters = load_chapters(path)
    assert chapters == {
        (1, 1): "Invented placeholder chapter one.",
        (1, 2): "Invented placeholder chapter two.",
    }


def test_load_chapters_multi_book_happy_path(tmp_path):
    """`book` present on every record (De Finibus' real source shape) --
    chapter numbering resets per book."""
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"book": 1, "chapter": 1, "text": "book one chapter one"}, '
        '{"book": 1, "chapter": 2, "text": "book one chapter two"}, '
        '{"book": 2, "chapter": 1, "text": "book two chapter one"}]',
        encoding="utf-8",
    )
    chapters = load_chapters(path)
    assert chapters == {
        (1, 1): "book one chapter one",
        (1, 2): "book one chapter two",
        (2, 1): "book two chapter one",
    }


def test_load_chapters_rejects_gap(tmp_path):
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"chapter": 1, "text": "x"}, {"chapter": 3, "text": "y"}]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="contiguous set"):
        load_chapters(path)


def test_load_chapters_rejects_gap_in_one_book_only(tmp_path):
    """Book 1 is contiguous; book 2 skips chapter 2 -- must still fail,
    scoped to book 2, even though book 1 alone is fine."""
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"book": 1, "chapter": 1, "text": "a"}, '
        '{"book": 2, "chapter": 1, "text": "b"}, '
        '{"book": 2, "chapter": 3, "text": "c"}]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="book 2 chapters must form the contiguous set"):
        load_chapters(path)


def test_load_chapters_rejects_duplicate(tmp_path):
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"chapter": 1, "text": "x"}, {"chapter": 1, "text": "y"}]',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate chapter"):
        load_chapters(path)


def test_load_chapters_same_chapter_number_different_books_is_fine(tmp_path):
    """Chapter 1 recurring in book 1 and book 2 is NOT a duplicate --
    chapter numbering resets per book."""
    path = tmp_path / "chapters.json"
    path.write_text(
        '[{"book": 1, "chapter": 1, "text": "a"}, {"book": 2, "chapter": 1, "text": "b"}]',
        encoding="utf-8",
    )
    chapters = load_chapters(path)
    assert chapters == {(1, 1): "a", (2, 1): "b"}


def test_load_chapters_rejects_empty_text(tmp_path):
    path = tmp_path / "chapters.json"
    path.write_text('[{"chapter": 1, "text": "   "}]', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid 'text'"):
        load_chapters(path)


# --- load_concordance -----------------------------------------------------


def test_load_concordance_happy_path_sorts_by_chapter(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": ['
        '{"chapter": 2, "start_section": 3, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "b"}, '
        '{"chapter": 1, "start_section": 1, "exact": true, "section_position": "mid", '
        '"anchor_lat_sha256_16": "fedcba9876543210", "anchor_en": "a"}'
        ']}',
        encoding="utf-8",
    )
    records = load_concordance(path)
    assert [r["chapter"] for r in records] == [1, 2]
    assert records[0]["anchor_en"] == "a"
    assert records[0]["section_position"] == "mid"
    # No "book" key in either record (De Fato's real shape) -- defaults to 1.
    assert [r["book"] for r in records] == [1, 1]


def test_load_concordance_multi_book_sorts_by_book_then_chapter(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": ['
        '{"book": 2, "chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "b2c1"}, '
        '{"book": 1, "chapter": 2, "start_section": 3, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "b1c2"}, '
        '{"book": 1, "chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "fedcba9876543210", "anchor_en": "b1c1"}'
        ']}',
        encoding="utf-8",
    )
    records = load_concordance(path)
    assert [(r["book"], r["chapter"]) for r in records] == [(1, 1), (1, 2), (2, 1)]


def test_load_concordance_same_chapter_different_book_is_fine(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": ['
        '{"book": 1, "chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}, '
        '{"book": 2, "chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "fedcba9876543210", "anchor_en": "b"}'
        ']}',
        encoding="utf-8",
    )
    records = load_concordance(path)
    assert [(r["book"], r["chapter"]) for r in records] == [(1, 1), (2, 1)]


def test_load_concordance_rejects_non_exact(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": [{"chapter": 1, "start_section": 1, "exact": false, '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exact=False"):
        load_concordance(path)


def test_load_concordance_rejects_malformed_hash(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": [{"chapter": 1, "start_section": 1, "exact": true, '
        '"anchor_lat_sha256_16": "not-hex!", "anchor_en": "a"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid anchor_lat_sha256_16"):
        load_concordance(path)


def test_load_concordance_rejects_duplicate_chapter(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": ['
        '{"chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}, '
        '{"chapter": 1, "start_section": 2, "exact": true, '
        '"anchor_lat_sha256_16": "fedcba9876543210", "anchor_en": "b"}'
        ']}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate concordance record"):
        load_concordance(path)


def test_load_concordance_rejects_duplicate_book_chapter_pair(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": ['
        '{"book": 2, "chapter": 1, "start_section": 1, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}, '
        '{"book": 2, "chapter": 1, "start_section": 2, "exact": true, "section_position": "start", '
        '"anchor_lat_sha256_16": "fedcba9876543210", "anchor_en": "b"}'
        ']}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate concordance record for book 2 chapter 1"):
        load_concordance(path)


# --- load_concordance: section_position (Major 1) --------------------------


def test_load_concordance_rejects_missing_section_position(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": [{"chapter": 1, "start_section": 1, "exact": true, '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="section_position"):
        load_concordance(path)


def test_load_concordance_rejects_unknown_section_position(tmp_path):
    path = tmp_path / "concordance.json"
    path.write_text(
        '{"records": [{"chapter": 1, "start_section": 1, "exact": true, '
        '"section_position": "overlap", '
        '"anchor_lat_sha256_16": "0123456789abcdef", "anchor_en": "a"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="partial-section boundaries"):
        load_concordance(path)


def test_load_concordance_accepts_start_mid_end():
    for pos in ("start", "mid", "end"):
        rec = _concordance_record(1, 1, "a", section_position=pos)
        assert rec["section_position"] == pos


# --- build_spans: ordering / duplicate / exclusion gates -------------------


def test_build_spans_happy_path_contiguous_spans():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2), 3: _chapter_text(3)}
    concordance = [
        _concordance_record(1, 1, "a"),
        _concordance_record(2, 3, "b"),
        _concordance_record(3, 5, "c"),
    ]
    spans = build_spans(concordance, chapters, book_min=1, book_max=6, exclude_sections=set())
    assert [(s["chapter"], s["start_section"], s["end_section"]) for s in spans] == [
        (1, 1, 2), (2, 3, 4), (3, 5, 6),
    ]


def test_build_spans_missing_concordance_record_is_fatal():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2)}
    concordance = [_concordance_record(1, 1, "a")]
    with pytest.raises(ValueError, match=r"chapter\(s\) \[2\]"):
        build_spans(concordance, chapters, book_min=1, book_max=5, exclude_sections=set())


def test_build_spans_concordance_chapter_with_no_source_text_is_fatal():
    chapters = {1: _chapter_text(1)}
    concordance = [_concordance_record(1, 1, "a"), _concordance_record(2, 3, "b")]
    with pytest.raises(ValueError, match=r"chapter\(s\) \[2\]"):
        build_spans(concordance, chapters, book_min=1, book_max=5, exclude_sections=set())


def test_build_spans_duplicate_anchor_section_is_fatal():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2)}
    concordance = [_concordance_record(1, 1, "a"), _concordance_record(2, 1, "b")]
    with pytest.raises(ValueError, match="duplicate anchor start_section"):
        build_spans(concordance, chapters, book_min=1, book_max=5, exclude_sections=set())


def test_build_spans_chapters_out_of_order_is_fatal():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2)}
    concordance = [_concordance_record(1, 3, "a"), _concordance_record(2, 1, "b")]
    with pytest.raises(ValueError, match="chapters out of order"):
        build_spans(concordance, chapters, book_min=3, book_max=5, exclude_sections=set())


def test_build_spans_span_touching_excluded_section_is_fatal():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2)}
    concordance = [_concordance_record(1, 1, "a"), _concordance_record(2, 3, "b")]
    # Chapter 1's span is sections 1-2; section "2" is declared excluded.
    with pytest.raises(ValueError, match="excluded section token"):
        build_spans(concordance, chapters, book_min=1, book_max=4, exclude_sections={"2"})


def test_build_spans_start_section_out_of_range_is_fatal():
    chapters = {1: _chapter_text(1)}
    concordance = [_concordance_record(1, 10, "a")]
    with pytest.raises(ValueError, match="outside the work's section range"):
        build_spans(concordance, chapters, book_min=10, book_max=5, exclude_sections=set())


def test_build_spans_rejects_non_string_exclude_sections():
    # Major 3 defensive backstop: this module is reachable from `astro
    # build`/`reader_pipeline all` runs that bypass preflight's schema gate.
    chapters = {1: _chapter_text(1)}
    concordance = [_concordance_record(1, 1, "a")]
    with pytest.raises(ValueError, match="non-empty strings"):
        build_spans(concordance, chapters, book_min=1, book_max=5, exclude_sections={2, "fr1"})


# --- build_spans: English-anchor-drift (Blocker 1) --------------------------


def test_build_spans_anchor_en_drift_is_fatal():
    chapters = {1: _chapter_text(1)}
    # anchor_en recorded for chapter 1 does NOT actually open this chapter's
    # live text -- simulates a reordered/misnumbered/corrupted English
    # chapter attaching to an otherwise-valid Latin anchor.
    drifted = _concordance_record(1, 1, "a", anchor_en="this phrase never appears in the chapter at all")
    with pytest.raises(ValueError, match="anchor_en does not open"):
        build_spans([drifted], chapters, book_min=1, book_max=5, exclude_sections=set())


def test_build_spans_anchor_en_tolerates_short_preamble_and_case():
    # Mirrors the real concordance's own observed cases: a short narrative
    # preamble before the anchor phrase, and a capitalization difference
    # between the recorded anchor and the chapter's own sentence-initial
    # capital (both non-verbatim, invented placeholders here).
    chapters = {1: "But invented narrative connective, THE Real Opening Phrase continues on."}
    rec = _concordance_record(1, 1, "a", anchor_en="the real opening phrase")
    spans = build_spans([rec], chapters, book_min=1, book_max=1, exclude_sections=set())
    assert spans[0]["text"] == chapters[1]


# --- build_spans: uncovered prefix (Blocker 2) ------------------------------


def test_build_spans_uncovered_prefix_is_fatal():
    chapters = {1: _chapter_text(1), 2: _chapter_text(2)}
    concordance = [_concordance_record(1, 3, "a"), _concordance_record(2, 5, "b")]
    # The live spine's first citable section is 1, but chapter 1's
    # concordance record starts at section 3 -- sections 1-2 would be
    # silently English-less.
    with pytest.raises(ValueError, match="silently English-less"):
        build_spans(concordance, chapters, book_min=1, book_max=6, exclude_sections=set())


def test_build_spans_first_chapter_matching_book_min_is_fine():
    chapters = {1: _chapter_text(1)}
    concordance = [_concordance_record(1, 1, "a")]
    spans = build_spans(concordance, chapters, book_min=1, book_max=3, exclude_sections=set())
    assert spans[0]["start_section"] == 1


# --- verify_anchor: hash re-verification against live spine text -----------


def test_verify_anchor_matches_a_word_bounded_substring():
    words = "wordalfa wordbeta wordgamma worddelta".split()
    target_hash = _hash("wordbeta wordgamma")
    assert verify_anchor(words, target_hash) is True


def test_verify_anchor_tolerates_trimmed_edge_punctuation():
    words = ["wordalfa", "wordbeta,", "wordgamma"]
    # The anchor was recorded WITHOUT the trailing comma the live text
    # happens to carry on "wordbeta,".
    target_hash = _hash("wordalfa wordbeta")
    assert verify_anchor(words, target_hash) is True


def test_verify_anchor_returns_false_for_unmatched_hash():
    words = "wordalfa wordbeta wordgamma".split()
    assert verify_anchor(words, "0000000000000000") is False


# --- build_english_chunks: end-to-end fixture builds ------------------------


def test_build_english_chunks_happy_path_anchors_and_labels():
    manifest = _manifest([{"n": 1, "start": "1", "end": "3"}])
    spine = _spine(_SECTION_TEXT)
    chapters = {(1, 1): _chapter_text(1), (1, 2): _chapter_text(2)}
    concordance = [
        _concordance_record(1, 1, "wordalfa wordbeta"),
        _concordance_record(2, 3, "wordkappa wordlambda"),
    ]
    english = build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)
    assert [c["id"] for c in english["chunks"]] == ["1:1", "1:3"]
    assert english["chunks"][0]["title"] == "sections 1–2"
    assert english["chunks"][1]["title"] == "section 3"
    assert english["chunks"][0]["text"] == chapters[(1, 1)]
    assert english["translation"] == _PRIMARY["name"]

    alignment = build_alignment(english)
    assert alignment["pairs"] == [
        {"segment": "1:1", "english": "1:1"},
        {"segment": "1:3", "english": "1:3"},
    ]
    assert alignment["english_only"] == []


def test_build_english_chunks_hash_mismatch_is_fatal():
    manifest = _manifest([{"n": 1, "start": "1", "end": "3"}])
    spine = _spine(_SECTION_TEXT)
    chapters = {(1, 1): _chapter_text(1)}
    # Anchor hash computed from words that do NOT actually appear in
    # section 1's live text -- simulates a re-exported Latin spine that
    # drifted out from under a stale concordance.
    stale = _concordance_record(1, 1, "wordalfa wordNOTPRESENT")
    with pytest.raises(ValueError, match="Latin export changed and the concordance is stale"):
        build_english_chunks(manifest, spine, chapters, [stale], set(), _PRIMARY)


def test_build_english_chunks_missing_spine_segment_is_fatal():
    # book_min (1) agrees with the live spine's own minimum, so this test
    # exercises a MID-spine chapter (2) whose declared anchor section (9)
    # has no live segment at all -- distinct from the book_min-mismatch
    # tests below.
    manifest = _manifest([{"n": 1, "start": "1", "end": "9"}])
    spine = _spine(_SECTION_TEXT)  # only sections 1-3 exist
    chapters = {(1, 1): _chapter_text(1), (1, 2): _chapter_text(2)}
    concordance = [
        _concordance_record(1, 1, "wordalfa wordbeta"),
        _concordance_record(2, 9, "wordalfa"),
    ]
    with pytest.raises(ValueError, match="no citable Latin division"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


# --- build_english_chunks: book_min derived from the live spine (MAJOR fix) --


def test_build_english_chunks_book_min_mismatch_against_manifest_is_fatal():
    """MAJOR fix (Sol re-verification, 2026-07-21): book_min is now derived
    from the LIVE spine, not trusted from the manifest -- a manifest whose
    declared start disagrees with the live spine's own minimum citable
    section must fail loudly, even when the concordance's first chapter
    agrees with the (wrong) declared value (previously this combination
    passed silently, leaving live section(s) below the true minimum with
    no English and no error)."""
    manifest = _manifest([{"n": 1, "start": "2", "end": "3"}])
    spine = _spine(_SECTION_TEXT)  # live spine's own min is section 1
    chapters = {(1, 1): _chapter_text(1)}
    concordance = [_concordance_record(1, 2, "wordzeta wordeta")]
    with pytest.raises(ValueError, match="does not equal the live spine's own minimum"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


def test_build_english_chunks_no_live_segments_for_book_is_fatal():
    manifest = _manifest([{"n": 1, "start": "1", "end": "3"}])
    spine = {"segments": []}
    chapters = {(1, 1): _chapter_text(1)}
    concordance = [_concordance_record(1, 1, "wordalfa")]
    with pytest.raises(ValueError, match="no live spine segments found"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


# --- build_english_chunks: multi-book walk (De Finibus phase 3) ------------


def test_build_english_chunks_multi_book_happy_path():
    """Two books, each with its own chapter numbering starting at 1 and its
    own Latin section range -- exercises the per-book slicing, per-book
    book_min derivation, and a MID-section-position record (chapter 2's
    concordance record straddles the book's own section boundary; the
    whole-section span/label mechanism is unaffected by section_position,
    same as the single-book case)."""
    manifest = _manifest([
        {"n": 1, "start": "1", "end": "3"},
        {"n": 2, "start": "1", "end": "2"},
    ])
    spine = _multi_book_spine({
        1: _SECTION_TEXT,
        2: {1: "wordpi wordrho wordsigma", 2: "wordtau wordupsilon wordphi"},
    })
    chapters = {
        (1, 1): _chapter_text(1), (1, 2): _chapter_text(2),
        (2, 1): _chapter_text(1),
    }
    concordance = [
        _concordance_record(1, 1, "wordalfa wordbeta", book=1),
        _concordance_record(2, 3, "wordkappa wordlambda", book=1, section_position="mid"),
        _concordance_record(1, 1, "wordpi wordrho", book=2),
    ]
    english = build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)
    assert [c["id"] for c in english["chunks"]] == ["1:1.1", "1:1.3", "2:2.1"]
    assert [c["book"] for c in english["chunks"]] == [1, 1, 2]
    assert english["chunks"][0]["title"] == "sections 1–2"
    assert english["chunks"][1]["title"] == "section 3"
    assert english["chunks"][2]["title"] == "sections 1–2"
    assert english["chunks"][2]["text"] == chapters[(2, 1)]

    alignment = build_alignment(english)
    assert [p["segment"] for p in alignment["pairs"]] == ["1:1.1", "1:1.3", "2:2.1"]


def test_build_english_chunks_multi_book_hash_mismatch_in_second_book_is_fatal():
    """The bad-hash gate applies per book, at multi-book scale -- book 1 is
    entirely valid; book 2's one chapter has a stale anchor hash."""
    manifest = _manifest([
        {"n": 1, "start": "1", "end": "3"},
        {"n": 2, "start": "1", "end": "2"},
    ])
    spine = _multi_book_spine({
        1: _SECTION_TEXT,
        2: {1: "wordpi wordrho wordsigma", 2: "wordtau wordupsilon wordphi"},
    })
    chapters = {
        (1, 1): _chapter_text(1),
        (2, 1): _chapter_text(1),
    }
    concordance = [
        _concordance_record(1, 1, "wordalfa wordbeta", book=1),
        # Anchor hash computed from words that do NOT appear in book 2's
        # section 1 live text -- simulates a re-exported Latin spine that
        # drifted out from under a stale concordance, in the SECOND book.
        _concordance_record(1, 1, "wordpi wordNOTPRESENT", book=2),
    ]
    with pytest.raises(ValueError, match="book 2 chapter 1: anchor hash"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


def test_build_english_chunks_book_set_mismatch_chapters_vs_manifest_is_fatal():
    """The manifest declares books 1 and 2, but the chapter source only has
    text for book 1 -- must fail loudly, not silently ship book 2 with no
    English (or crash on an empty-list IndexError deep inside build_spans)."""
    manifest = _manifest([
        {"n": 1, "start": "1", "end": "3"},
        {"n": 2, "start": "1", "end": "2"},
    ])
    spine = _multi_book_spine({
        1: _SECTION_TEXT,
        2: {1: "wordpi wordrho wordsigma", 2: "wordtau wordupsilon wordphi"},
    })
    chapters = {(1, 1): _chapter_text(1)}
    concordance = [
        _concordance_record(1, 1, "wordalfa wordbeta", book=1),
        _concordance_record(1, 1, "wordpi wordrho", book=2),
    ]
    with pytest.raises(ValueError, match="chapter source declares book"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


def test_build_english_chunks_book_set_mismatch_concordance_vs_manifest_is_fatal():
    manifest = _manifest([{"n": 1, "start": "1", "end": "3"}])
    spine = _spine(_SECTION_TEXT)
    chapters = {(1, 1): _chapter_text(1)}
    # Concordance declares book 2, which the manifest never declared.
    concordance = [_concordance_record(1, 1, "wordalfa wordbeta", book=2)]
    with pytest.raises(ValueError, match="concordance declares book"):
        build_english_chunks(manifest, spine, chapters, concordance, set(), _PRIMARY)


# --- preflight: citation.exclude_sections type gate (Major 3) --------------


def test_preflight_rejects_non_string_exclude_sections():
    data = {"citation": {"exclude_sections": [2, "fr1"]}}
    manifest = WorkManifest(work_id="FATOFIX", path=Path("fatofix.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("exclude_sections" in m and "strings" in m for m in messages), messages


def test_preflight_rejects_duplicate_exclude_sections():
    data = {"citation": {"exclude_sections": ["fr1", "fr1"]}}
    manifest = WorkManifest(work_id="FATOFIX", path=Path("fatofix.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("duplicate" in m for m in messages), messages


def test_preflight_accepts_valid_exclude_sections():
    data = {"citation": {"exclude_sections": ["fr", "fr1"]}}
    manifest = WorkManifest(work_id="FATOFIX", path=Path("fatofix.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert not any("exclude_sections" in m for m in messages), messages


# --- preflight: english.primary.model enum (Major 2) ------------------------


def test_preflight_rejects_unrecognized_english_model():
    data = {
        "work": {"id": "FATOFIX", "title": "Fixture", "author": "cicero", "language": "lat",
                 "phi_author": "0000", "phi_work": "000", "latin_edition": "Fixture Edition"},
        "citation": {"scheme": "section", "div_types": {"page": "section"}},
        "english": {"primary": {"id": "fx", "name": "Fixture", "model": "chapter_concordence",
                                 "file": "fx.json"}},
        "section_spine": {"count": 3, "sha256": "0" * 64},
        "sources": {},
        "books": [{"n": 1, "start": "1", "end": "3"}],
    }
    manifest = WorkManifest(work_id="FATOFIX", path=Path("fatofix.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("not a recognized model" in m for m in messages), messages


# --- __main__ dispatch: model gate and builder selection (Major 2) ---------


def test_stage1_dispatch_raises_on_unknown_model(tmp_path, monkeypatch):
    from reader_pipeline import __main__ as main_mod
    from reader_pipeline import stage1_greek

    spine_path = tmp_path / "spine.json"
    spine_path.write_text('{"segments": [], "unassigned_lines": []}', encoding="utf-8")
    monkeypatch.setattr(stage1_greek, "run", lambda manifest: spine_path)

    data = {
        "work": {"id": "FATOFIX", "language": "grc"},
        "citation": {"scheme": "section"},
        "english": {"primary": {"id": "fx", "name": "Fixture", "model": "chapter_concordence",
                                 "file": "fx.json"}},
        "books": [{"n": 1, "start": "1", "end": "3"}],
    }
    manifest = Manifest(data, ROOT / "manifests" / "fake-fato.yaml")
    with pytest.raises(ValueError, match="unsupported english.primary.model"):
        main_mod._stage1(manifest)


def test_stage1_dispatch_chapter_concordance_selects_dedicated_builder(tmp_path, monkeypatch):
    from reader_pipeline import __main__ as main_mod
    from reader_pipeline import stage1_chapter_concordance_english, stage1_flat_english, stage1_greek

    spine_path = tmp_path / "spine.json"
    spine_path.write_text('{"segments": [], "unassigned_lines": []}', encoding="utf-8")
    monkeypatch.setattr(stage1_greek, "run", lambda manifest: spine_path)

    calls: list[str] = []

    def fake_concordance_run(manifest, spine):
        calls.append("chapter_concordance")
        eng_path = tmp_path / "english_chunks.json"
        align_path = tmp_path / "alignment.json"
        eng_path.write_text('{"chunks": [], "translation": "Fixture"}', encoding="utf-8")
        align_path.write_text('{"pairs": [], "english_only": []}', encoding="utf-8")
        return eng_path, align_path

    def fake_flat_english_run(manifest, spine):
        calls.append("flat_english")
        raise AssertionError("stage1_flat_english must not run for model chapter_concordance")

    monkeypatch.setattr(stage1_chapter_concordance_english, "run", fake_concordance_run)
    monkeypatch.setattr(stage1_flat_english, "run", fake_flat_english_run)

    data = {
        "work": {"id": "FATOFIX", "language": "grc"},
        "citation": {"scheme": "section"},
        "english": {"primary": {"id": "fx", "name": "Fixture", "model": "chapter_concordance",
                                 "file": "fx.json", "concordance": "fx-conc.json"}},
        "books": [{"n": 1, "start": "1", "end": "3"}],
    }
    manifest = Manifest(data, ROOT / "manifests" / "fake-fato.yaml")
    main_mod._stage1(manifest)
    assert calls == ["chapter_concordance"]
