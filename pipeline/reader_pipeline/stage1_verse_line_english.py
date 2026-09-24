"""Stage 1b (verse-line variant): Munro's English prose translation attached
to Lucretius' De Rerum Natura (Wave 2 Batch 2's English task).

verse-line's spine (stage1_latin._parse_spine_verse) is one segment PER
CITABLE LINE — ~7400 of them across the six books — but Munro's source
(sources/munro-drn/munro.clean.json) is 122 records, each a whole printed
spread's worth of prose keyed by its own Latin line RANGE ("23-90"). Neither
existing English builder fits: stage1_book_section_english's 1:1 chapter
lookup assumes one column per translation unit (verse-line's column IS a
single line, far too fine-grained); stage1_english's Bekker archive model
proportionally SPLITS one translation across the many columns it spans
(verse-line has no page/side axis to split across, and splitting one
paragraph across ~30 one-line segments would shred it into unreadable
fragments). The shape that DOES fit, adapted from stage1_book_section_english
one level up: each Munro record becomes ONE EnglishChunk, anchored to the
spine segment at the FIRST citation-order line of its range — Reader.svelte
already renders a chunk's `text` as a single block at its anchor segment's
row and (via the pre-existing `title` field, Discourses' descriptive-heading
mechanism) a subtitle above it; giving that field the record's own line-range
("1–23") reuses that rendering path unchanged as the block's citation label.
Every OTHER segment the record's range covers carries no chunk of its own —
sparse coverage is a normal, already-supported shape (stage7_emit.emit_books'
`english_by_id.get(seg["id"])` -> None, stage6_search's matching lookup) —
so a Latin line's row is simply Latin-only for the ~29 lines out of 30 that
aren't a record's own anchor, the same way the printed edition's translation
occupies its own paragraph, not a line-for-line rendering.

Because coverage is deliberately ~98% sparse BY DESIGN, the generic
segment-level alignment gate (stage1_english.build_alignment / stage2_validate's
"every unmatched segment must be a declared allowance") does not apply here —
it would demand declaring thousands of individually-expected gaps. The real
completeness gate for this scheme is `reconcile_book` below: every citation-
order Latin line 1..(the book's max) must fall inside EXACTLY ONE Munro
record's range, after reconciling the source's own two edition artifacts
(open-ended trailers at books 3 and 5; one-line straddled boundaries between
consecutive spreads), except a book's declared `english.gaps` entries (a real,
single print-layout gap: book 3 has no record covering line 126 at all —
Munro's own spread break lands on neither side). `build_alignment` here is
reduced to just the 122 anchor pairs (trivially all matched, since
`build_english` already fails loudly if any record couldn't be placed) —
informational only, not a second coverage gate.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import scheme as scheme_mod
from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .stage1_common import write_json

# A range-form lineref's two bounds, each with an optional (and, for a Munro
# attachment target, never actually observed) lowercase suffix letter --
# same grammar as scheme.py's private _VERSE_LINE_RANGE_RE, re-declared here
# because that module exposes classification (`verse_line_kind`) but not
# bound extraction, and this is the only stage1 module that needs the bounds
# themselves (every other caller only ever needs the range's START, for
# sorting -- see stage1_latin.py/stage7_emit.py's own `.split("-", 1)[0]`).
_RANGE_BOUNDS_RE = re.compile(r"^([0-9]+)[a-z]?-([0-9]+)[a-z]?$")

# A plain (non-range, non-suffixed) lineref -- the only lineref shape that
# contributes an integer->segment mapping of its own; see
# `_line_to_segment_map`'s doc comment for why a lettered-suffix line
# ("860a") does not.
_PLAIN_LINE_RE = re.compile(r"^[0-9]+$")


def _range_bounds(lineref: str) -> tuple[int, int]:
    m = _RANGE_BOUNDS_RE.match(lineref)
    if not m:
        raise ValueError(f"not a verse-line range lineref: {lineref!r}")
    return int(m.group(1)), int(m.group(2))


def _line_to_segment_map(spine: dict) -> dict[tuple[int, int], dict]:
    """(book, line-integer) -> spine segment, for every citation-order
    integer line the verse-line spine carries a citable division for.

    An ordinary line's own plain lineref ("101") maps its own integer. A
    lettered-suffix line ("860a") is a distinct EXTRA division inserted
    after line 860 (design memo §3.2) -- it contributes no mapping of its
    own; the plain "860" segment elsewhere in the same book's segment list
    already covers integer 860. A lacuna RANGE div ("1094-1101") replaces
    several integers with one citable unit -- every integer it spans maps to
    that one segment, since none of those integers has a plain division of
    its own."""
    out: dict[tuple[int, int], dict] = {}
    for seg in spine["segments"]:
        book = seg["book"]
        lineref = seg["column"].split(".", 1)[1]
        if scheme_mod.verse_line_kind(lineref) == "range":
            lo, hi = _range_bounds(lineref)
            for n in range(lo, hi + 1):
                out[(book, n)] = seg
        elif _PLAIN_LINE_RE.match(lineref):
            out[(book, int(lineref))] = seg
    return out


def reconcile_book(records: list[dict], book_max: int, declared_gaps: set[int]) -> list[dict]:
    """`records` (one book's Munro entries, any order) with each given an
    `eff_start` -- its reconciled first line, after:

      * closing AT MOST ONE open-ended trailer (`end: None`, books 3 and 5's
        print-edition artifact -- the source's last spread has no following
        recto header) to `book_max`;
      * resolving each straddled print-spread boundary (`records[i+1].start
        == records[i].end`, one Latin line printed on both spreads' running
        headers) by crediting the shared line to the EARLIER record --
        `records[i+1].eff_start = records[i].end + 1` -- while a plain abut
        (`records[i+1].start == records[i].end + 1`, no shared line) needs no
        adjustment.

    Every input record's own `start` must be <= its `end` (a backwards range
    is rejected up front, before any reconciliation runs). Then validates
    full coverage: every citation-order line 1..book_max must fall inside
    EXACTLY ONE record's [eff_start, end] span, except a line in
    `declared_gaps` (which must fall inside NONE -- a declared gap that turns
    out to be covered is a stale declaration, equally fatal). A record whose
    straddle-reconciled `eff_start` ends up past its own `end` (an exact
    shared-boundary CHAIN can squeeze a middle record's span to empty) is
    rejected too, rather than silently contributing zero coverage. Any other
    uncovered line, any overlap, or an edition shape this function doesn't
    recognize (more than one trailer, a first record not starting at line 1,
    a last record not ending at book_max, or two records overlapping by more
    than the one allowed straddling line) raises ValueError loudly rather
    than silently mis-attaching or dropping translation text."""
    recs = sorted((dict(r) for r in records), key=lambda r: r["start"])
    if not recs:
        raise ValueError("reconcile_book: no records given for this book")

    backwards = [r for r in recs if r["end"] is not None and r["start"] > r["end"]]
    if backwards:
        raise ValueError(
            f"record(s) with start > end (not a valid range): "
            f"{[r.get('range', (r['start'], r['end'])) for r in backwards]}"
        )

    open_ended = [r for r in recs if r["end"] is None]
    if len(open_ended) > 1:
        raise ValueError(
            f"more than one open-ended (trailer) record: "
            f"{[r.get('range', r['start']) for r in open_ended]}"
        )
    if open_ended:
        trailer = open_ended[0]
        if trailer is not recs[-1]:
            raise ValueError(
                f"open-ended record {trailer.get('range', trailer['start'])!r} "
                f"is not the book's last record by start line"
            )
        trailer["end"] = book_max

    if recs[0]["start"] != 1:
        raise ValueError(f"book's first Munro record starts at line {recs[0]['start']}, expected 1")
    recs[0]["eff_start"] = recs[0]["start"]

    for prev, cur in zip(recs, recs[1:]):
        if cur["start"] == prev["end"]:
            cur["eff_start"] = prev["end"] + 1  # straddle: shared line credited to the earlier record
        elif cur["start"] == prev["end"] + 1:
            cur["eff_start"] = cur["start"]  # plain abut, no shared line
        elif cur["start"] > prev["end"] + 1:
            cur["eff_start"] = cur["start"]  # a real gap -- checked against declared_gaps below
        else:
            raise ValueError(
                f"record {cur.get('range', cur['start'])!r} overlaps "
                f"{prev.get('range', prev['start'])!r} by more than the one "
                f"allowed straddling line"
            )

    if recs[-1]["end"] != book_max:
        raise ValueError(f"book's last record ends at {recs[-1]['end']}, expected the book max {book_max}")

    # An exact shared-boundary CHAIN (e.g. ranges 1-10, 10-10, 10-20) can
    # straddle-reconcile a record's eff_start past its own end -- the middle
    # 10-10 record above becomes eff_start=11, end=10, an empty span that
    # would silently contribute zero coverage below (Python's `range(11, 11)`
    # is simply empty) rather than failing loudly on the edition shape this
    # function doesn't recognize.
    empty_spans = [r for r in recs if r["eff_start"] > r["end"]]
    if empty_spans:
        raise ValueError(
            f"record(s) reduced to an empty effective span by straddle "
            f"reconciliation (eff_start > end): "
            f"{[(r.get('range', r['start']), r['eff_start'], r['end']) for r in empty_spans]}"
        )

    coverage = [0] * (book_max + 1)
    for r in recs:
        for n in range(r["eff_start"], r["end"] + 1):
            coverage[n] += 1

    overlaps = [n for n in range(1, book_max + 1) if coverage[n] > 1]
    if overlaps:
        raise ValueError(f"line(s) {overlaps} are covered by more than one Munro record after reconciliation")

    uncovered = {n for n in range(1, book_max + 1) if coverage[n] == 0}
    undeclared = sorted(uncovered - declared_gaps)
    if undeclared:
        raise ValueError(f"line(s) {undeclared} are covered by no Munro record and not declared in english.gaps")

    stale = sorted(declared_gaps - uncovered)
    if stale:
        raise ValueError(
            f"english.gaps declares line(s) {stale} but they ARE covered by a "
            f"Munro record after reconciliation (stale declaration)"
        )

    return recs


def _parse_gap_token(token: str) -> tuple[int, int]:
    book_s, line_s = token.split(":", 1)
    return int(book_s), int(line_s)


def build_english_chunks(
    manifest: Manifest, spine: dict, records: list[dict], primary: dict, gap_tokens: list[str],
) -> dict:
    """The EnglishChunk-shaped `english_chunks.json` dict, pure of any file
    I/O -- `records`/`primary`/`gap_tokens` are already-loaded manifest/source
    data, so this is directly unit-testable against synthetic fixtures (see
    `build_english`, the thin I/O wrapper `run` actually calls)."""
    declared_gaps: dict[int, set[int]] = defaultdict(set)
    for token in gap_tokens:
        book, line = _parse_gap_token(token)
        declared_gaps[book].add(line)

    by_book: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        by_book[r["book"]].append(r)

    book_max = {b["n"]: int(b["end"].split(".", 1)[1]) for b in manifest.books}
    unknown_books = sorted(set(by_book) - set(book_max))
    if unknown_books:
        raise ValueError(
            f"{manifest.work_id}: Munro records reference book(s) {unknown_books}, "
            f"not in the manifest's books list"
        )
    unknown_gap_books = sorted(set(declared_gaps) - set(by_book))
    if unknown_gap_books:
        raise ValueError(
            f"{manifest.work_id}: english.gaps declares book(s) {unknown_gap_books} "
            f"with no Munro records at all"
        )

    # `reconcile_book` below only ever runs for a book that HAS at least one
    # Munro record -- a spine/manifest book with NO records and no declared
    # gap (a whole book silently missing its translation) would otherwise
    # never be visited at all, since the loop below iterates `by_book`, not
    # `book_max`. Require the two book sets to match exactly before
    # reconciling anything, so a missing book fails loudly here instead of
    # being silently skipped.
    missing_books = sorted(set(book_max) - set(by_book))
    if missing_books:
        raise ValueError(
            f"{manifest.work_id}: manifest book(s) {missing_books} have no "
            f"Munro records at all and no declared english.gaps -- coverage "
            f"cannot be verified for a book that is never checked"
        )

    line_to_seg = _line_to_segment_map(spine)

    chunks = []
    seen_ids: set[str] = set()
    for book in sorted(by_book):
        reconciled = reconcile_book(by_book[book], book_max[book], declared_gaps.get(book, set()))
        for r in reconciled:
            seg = line_to_seg.get((book, r["eff_start"]))
            if seg is None:
                raise ValueError(
                    f"{manifest.work_id}: no citable Latin division at book {book} "
                    f"line {r['eff_start']} (Munro record {r.get('range', r['start'])!r}'s "
                    f"reconciled start) -- the spine and the translation source have drifted"
                )
            # Defensive backstop: two records anchoring at the same segment
            # would silently dedupe in downstream keyed consumers
            # (english_by_id.get(seg["id"]) etc.) -- reconcile_book's overlap
            # and empty-span checks should already prevent this, but a chunk
            # ID collision is cheap and cheap to catch here too.
            if seg["id"] in seen_ids:
                raise ValueError(
                    f"{manifest.work_id}: duplicate chunk anchor {seg['id']!r} "
                    f"at book {book} line {r['eff_start']} (Munro record "
                    f"{r.get('range', r['start'])!r}) -- another record already "
                    f"anchored a chunk here"
                )
            seen_ids.add(seg["id"])
            label = str(r["eff_start"]) if r["eff_start"] == r["end"] else f"{r['eff_start']}–{r['end']}"
            chunks.append({
                "id": seg["id"], "book": book, "column": seg["column"],
                "text": r["text"].strip(), "notes": [], "markers": [],
                "title": label,
            })

    return {
        "work": manifest.work_id,
        "source": primary.get("file", ""),
        "translation": primary["name"],
        "chunks": chunks,
    }


def build_english(manifest: Manifest, spine: dict) -> dict:
    eng_cfg = manifest.data["english"]
    primary = eng_cfg["primary"]
    records = json.loads((SOURCES_DIR / primary["file"]).read_text(encoding="utf-8"))
    return build_english_chunks(manifest, spine, records, primary, eng_cfg.get("gaps", []))


def build_alignment(english: dict) -> dict:
    """Standoff alignment scoped to just the anchor segments a chunk was
    actually placed at (see the module docstring's alignment paragraph) --
    every pair is matched by construction, since `build_english_chunks`
    already raised loudly on any record it couldn't place."""
    pairs = [{"segment": c["id"], "english": c["id"]} for c in english["chunks"]]
    return {"work": english["work"], "pairs": pairs, "english_only": []}


def run(manifest: Manifest, spine: dict) -> tuple[Path, Path]:
    english = build_english(manifest, spine)
    out_dir = BUILD_DIR / "stage1"
    out_dir.mkdir(parents=True, exist_ok=True)
    eng_path = out_dir / "english_chunks.json"
    write_json(eng_path, english)
    align_path = out_dir / "alignment.json"
    write_json(align_path, build_alignment(english))
    return eng_path, align_path
