"""Stage 1b (chapter-concordance variant): an English translation attached as
CHAPTER-LEVEL SPANS anchored to the Latin spine via a hand-verified
concordance (Wave 2 -- Cicero's De Fato, Yonge's Bohn translation,
`sources/yonge-fato/`; De Finibus phase 3 -- Cicero's De Finibus, Yonge's
Wikisource translation, `sources/yonge-finibus/`).

MULTI-BOOK (De Finibus phase 3): De Fato's flat `section` scheme has exactly
one implicit book; De Finibus is a `book-section` work (5 real PHI books, a
dotted "book.section" column grammar). Both are supported by the same walk:
`load_chapters`/`load_concordance` key every record by an OPTIONAL `book`
field (defaulting to 1 when absent -- De Fato's source files carry no `book`
key at all, so they parse exactly as before), and `build_english_chunks`
loops `manifest.books`, slicing the loaded chapters/concordance to each
book's own records and re-running the (unchanged, single-book) `build_spans`
walk per book. `_section_num` reads the section component out of either
column-token shape (`"48"` -> 48, `"1.48"` -> 48) so book_min/book_max
derivation and the live-spine lookup work unmodified for both schemes. For a
single-book, no-`book`-key source (De Fato) this reduces to exactly the
original single-book code path -- verified byte-identical against a real
regenerated build (see the module's own test suite and the phase-3 delivery
notes).

Neither existing flat-scheme English builder fits this shape:
stage1_flat_english's 1:1 chapter->column mapping assumes one translation
record PER CITABLE SECTION (Epictetus' Enchiridion). Yonge's chapters
instead each cover a SPAN of several of the work's Latin sections
(`concordance.json`'s `start_section` per chapter -- the translator's
chapter breaks don't land on the Latin editor's own section breaks). The
shape that DOES fit, adapted from stage1_verse_line_english's Munro
spread-chunk precedent one level up: each English chapter becomes ONE
EnglishChunk, anchored to the spine segment at the FIRST Latin section of
its span, with a range label ("sections N-M") riding the chunk's `title`
field -- the exact mechanism Munro's line-range label ("1-23") already
exercises (Reader.svelte renders `title` as a subtitle above the chunk,
unchanged, no frontend change needed).

Anchor VERIFICATION is the piece this scheme adds that Munro's doesn't:
`concordance.json` never stores the literal Latin anchor phrase (PHI/TLG
corpus text is licensed and never committed) -- only
`anchor_lat_sha256_16`, the first 16 hex characters of the
whitespace-normalized anchor phrase's sha256 digest (`_anchor_hash` below,
the same convention `pipeline/tools/extract_yonge_fato.py`'s own
`_anchor_hash`/`_self_check_concordance` use, itself `dk_lang.decision_key`'s
convention reused independently). At BUILD TIME (this module, via
`verify_anchor`), every declared anchor hash is re-verified against the
actual, freshly-parsed Latin spine text for its declared `start_section` --
some word-bounded substring of that section's live text must hash to the
declared value, or the build fails loudly: the concordance and the current
Latin export have drifted (a re-export changed the text at that section)
and shipping would silently mis-anchor English against the wrong Latin.
`verify_anchor` only ever compares HASHES -- it never reconstructs, stores,
or prints the literal Latin phrase.

Every other structural invariant is checked in `build_spans` before that
verification runs: the clean chapter source and the concordance must
declare the exact same chapter set (no missing/extra chapter on either
side); `start_section` must be strictly increasing chapter-over-chapter
(the source's chapters occur in the Latin editor's own section order, so
"chapters out of order" and "duplicate anchor section" are really the same
monotonicity check); a chapter's span (by construction, contiguous with its
neighbors -- see `build_spans`' own doc) may not touch a
`citation.exclude_sections` token (apparatus/fragment tail, never real
translated text); the FIRST chapter's `start_section` must equal the live
spine's own minimum citable section (`book_min`, adversarial-review Blocker
2) -- otherwise every section before it would be silently English-less,
with nothing in the output to signal the gap.

English-side drift (adversarial-review Blocker 1): the Latin-side
`verify_anchor` check above only proves the LATIN half of an anchor pair
didn't drift -- on its own it says nothing about whether the ENGLISH half
(the `chapters` dict, keyed purely by chapter NUMBER) is the chapter the
concordance author actually looked at when they picked `start_section`. A
reordered or misnumbered English chapter would still attach cleanly to a
valid Latin anchor with `verify_anchor` alone. `build_spans` therefore also
requires each record's `anchor_en` (the verbatim public-domain English
phrase the concordance recorded) to open its own chapter's live text --
see `_anchor_en_opens_chapter` for the tolerance (a short editorial/
narrative preamble before the phrase, case-folded comparison) and why it's
bounded, not unbounded.

`section_position` (adversarial-review Major 1): the concordance also
records, per chapter, whether its `anchor_en`/`start_section` pair sits at
the `start`, `mid`, or `end` of that Latin section's own text (Yonge's
chapter breaks don't always land on Cicero's own section breaks -- see
`sources/yonge-fato/README.md`'s concordance-methodology table). This
builder's span/label mechanism assigns a chapter's span WHOLE sections
(`start_section`..`end_section`, no partial-section split) regardless of
where within `start_section` the chapter's own break actually falls --
correct as a NAV LABEL (the same "sections N-M" subtitle precedent as
Munro's line-range title, never a formal claim of an exact sub-section
boundary) for any of the three positions the real, hand-verified
concordance actually uses. Building genuine partial-section/overlapping-
range support is deliberately OUT of scope here (speculative -- no current
data needs finer granularity than whole sections); instead `section_position`
is validated against exactly that enum (`_ALLOWED_SECTION_POSITIONS`) and
retained, so a future value this mechanism was never verified against (a
new taxonomy entry, a typo, a null) fails loudly at load time instead of
silently reusing the whole-section label logic for a case nobody checked."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .stage1_common import write_json

# Edge punctuation/quote glyphs a hand-picked anchor phrase's outermost word
# sometimes omits relative to the flat spine text it was drawn from (a
# trailing comma the anchor dropped for readability, a dialogue-opening
# quote glyph glued to the first word) -- mirrors
# `extract_yonge_fato.py._self_check_concordance`'s own tolerance, which
# hashes both the raw and the edge-trimmed candidate.
_EDGE_PUNCT = " ,.;:?!'‘’“”"

# Major 1: the only `section_position` values the real, hand-verified
# concordance uses (`sources/yonge-fato/concordance.json`, cross-checked
# against `sources/yonge-fato/README.md`'s concordance-methodology table) --
# see this module's doc comment for why the whole-section span mechanism is
# correct as a nav-label for all three, and why any other value is rejected
# rather than silently reusing that same logic for a case never verified.
_ALLOWED_SECTION_POSITIONS = {"start", "mid", "end"}

# Blocker 1: generous upper bound (roughly double the real concordance's own
# worst case -- chapter I's bracketed "[The commencement of this
# treatise is lost.] ..." editorial lacuna note, per `yonge.clean.json`)
# on how many words of narrative/editorial preamble may precede a chapter's
# recorded `anchor_en` phrase and still count as "opening" that chapter --
# tight enough that a reordered/misnumbered/wholly different chapter's text
# containing the same phrase this close to its own start would be
# vanishingly unlikely by chance.
_ANCHOR_EN_PREFIX_WORD_BUDGET = 20


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _anchor_en_opens_chapter(chapter_text: str, anchor_en: str) -> bool:
    """True if `anchor_en` (whitespace-normalized, case-folded) appears as a
    word-bounded substring within the first `_ANCHOR_EN_PREFIX_WORD_BUDGET`
    words of `chapter_text` (also normalized/case-folded) -- i.e. `anchor_en`
    genuinely opens THIS chapter's live text, tolerating only a short
    preamble (the real concordance's own observed cases: a bracketed
    editorial lacuna note, or a narrative connective clause like "But " or
    "And after some time, he said, --"), never a chapter's unrelated
    interior or a different chapter's text entirely. Case-folded because a
    recorded anchor sometimes quotes a chapter's opening sentence with
    different capitalization than the live text's own sentence-initial
    capital (verified against the real concordance's chapter VII record --
    the sanctioned tolerance, not a loophole: this function still compares
    every letter of the phrase, just ignoring case). Also tolerates outer
    edge punctuation (`_EDGE_PUNCT`) the recorded anchor dropped for
    readability relative to the live text it was drawn from (verified
    against the real concordance's chapter I record, whose anchor omits the
    live text's own trailing comma) -- the exact same tolerance
    `verify_anchor` already applies on the Latin side, applied here to the
    joined candidate/anchor phrase rather than a single hash."""
    words = _norm(chapter_text).split(" ") if chapter_text.strip() else []
    anchor_words = _norm(anchor_en).split(" ") if anchor_en.strip() else []
    if not anchor_words or not words:
        return False
    anchor_folded = " ".join(w.casefold() for w in anchor_words)
    anchor_trimmed = anchor_folded.strip(_EDGE_PUNCT)
    n = len(anchor_words)
    limit = min(len(words), _ANCHOR_EN_PREFIX_WORD_BUDGET)
    for offset in range(0, limit + 1):
        candidate = words[offset:offset + n]
        if len(candidate) != n:
            break
        candidate_folded = " ".join(w.casefold() for w in candidate)
        if candidate_folded == anchor_folded:
            return True
        candidate_trimmed = candidate_folded.strip(_EDGE_PUNCT)
        if candidate_trimmed and candidate_trimmed == anchor_trimmed:
            return True
    return False


def _anchor_hash(phrase: str) -> str:
    """Identical convention to `pipeline/tools/extract_yonge_fato.py`'s own
    `_anchor_hash`: first 16 hex characters of the sha256 digest of the
    whitespace-normalized phrase. Never called on anything but a substring
    of the LIVE, locally-parsed Latin spine text or an already-committed
    hash -- the literal PHI/TLG phrase is never stored, printed, or
    returned by this module."""
    return hashlib.sha256(_norm(phrase).encode("utf-8")).hexdigest()[:16]


def load_chapters(path: Path) -> dict[tuple[int, int], str]:
    """{(book, chapter): text} from a clean `[{"book"?: b, "chapter": n,
    "text": ...}]` source (`extract_yonge_fato.py`/`extract_yonge_finibus.py`'s
    own output shape -- distinct from `stage1_common.load_english_source`'s
    book/section-keyed shapes, since this scheme's translated unit is a
    whole chapter, not a single spine column). `book` is OPTIONAL and
    defaults to 1 -- De Fato's source carries no `book` key at all (a single
    implicit book), while De Finibus' 5-book source declares it on every
    record. Validates: a non-empty list of objects, `book`/`chapter` each a
    non-bool int, `text` a non-empty string, no duplicate (book, chapter),
    and each book's own chapter set forming the exact contiguous range 1..N
    (a missing or skipped chapter fails loudly rather than silently shipping
    a hole) -- chapter numbering resets per book (De Finibus' own convention,
    see sources/yonge-finibus/README.md), so contiguity is checked BOOK BY
    BOOK, not across the whole file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path}: expected a non-empty list of chapter records")
    out: dict[tuple[int, int], str] = {}
    for i, rec in enumerate(data):
        if not isinstance(rec, dict):
            raise ValueError(f"{path}: record {i} is not an object")
        book = rec.get("book", 1)
        if isinstance(book, bool) or not isinstance(book, int):
            raise ValueError(f"{path}: record {i} has non-integer book {book!r}")
        chapter = rec.get("chapter")
        if isinstance(chapter, bool) or not isinstance(chapter, int):
            raise ValueError(f"{path}: record {i} has non-integer chapter {chapter!r}")
        text = rec.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"{path}: book {book} chapter {chapter} has invalid 'text' "
                f"(must be a non-empty string)"
            )
        key = (book, chapter)
        if key in out:
            raise ValueError(f"{path}: duplicate chapter {chapter} in book {book}")
        out[key] = text
    by_book: dict[int, list[int]] = {}
    for book, chapter in out:
        by_book.setdefault(book, []).append(chapter)
    for book, chs in by_book.items():
        expected = set(range(1, len(chs) + 1))
        if set(chs) != expected:
            raise ValueError(
                f"{path}: book {book} chapters must form the contiguous set "
                f"1..{len(chs)}, got {sorted(chs)}"
            )
    return out


def load_concordance(path: Path) -> list[dict]:
    """`concordance.json`'s `records` list, schema-validated field-by-field
    and returned SORTED by (book, chapter) (the source JSON's own record
    order is not contractually guaranteed; every downstream consumer here
    relies on chapter order within a book). `book` is OPTIONAL and defaults
    to 1, mirroring `load_chapters` -- De Fato's concordance carries no
    `book` key (a single implicit book), while De Finibus' 5-book
    concordance declares it on every record. Only `exact: true` records (a
    directly witnessed textual anchor, per `extract_yonge_fato.py`'s own
    convention) are supported -- an interpolated/extrapolated entry would
    have no literal anchor phrase for `verify_anchor` to re-verify against
    the live spine, so it is rejected here rather than silently skipping
    verification for just that one chapter."""
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path}: expected an object with a non-empty 'records' list")
    out = []
    seen: set[tuple[int, int]] = set()
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"{path}: record {i} is not an object")
        book = rec.get("book", 1)
        if isinstance(book, bool) or not isinstance(book, int):
            raise ValueError(f"{path}: record {i} has non-integer book {book!r}")
        chapter = rec.get("chapter")
        if isinstance(chapter, bool) or not isinstance(chapter, int):
            raise ValueError(f"{path}: record {i} has non-integer chapter {chapter!r}")
        key = (book, chapter)
        if key in seen:
            raise ValueError(f"{path}: duplicate concordance record for book {book} chapter {chapter}")
        seen.add(key)
        start_section = rec.get("start_section")
        if isinstance(start_section, bool) or not isinstance(start_section, int):
            raise ValueError(f"{path}: chapter {chapter} has non-integer start_section {start_section!r}")
        if rec.get("exact") is not True:
            raise ValueError(
                f"{path}: chapter {chapter} has exact={rec.get('exact')!r} -- only "
                f"exact=true (a directly witnessed anchor) is supported by this builder"
            )
        anchor_hash = rec.get("anchor_lat_sha256_16")
        if not isinstance(anchor_hash, str) or not re.fullmatch(r"[0-9a-f]{16}", anchor_hash):
            raise ValueError(f"{path}: chapter {chapter} has invalid anchor_lat_sha256_16 {anchor_hash!r}")
        anchor_en = rec.get("anchor_en")
        if not isinstance(anchor_en, str) or not anchor_en.strip():
            raise ValueError(f"{path}: chapter {chapter} has invalid anchor_en")
        # Major 1 fix (Sol adversarial review): `section_position` used to be
        # neither validated nor retained -- see this module's doc comment for
        # why the whole-section span mechanism is correct for exactly the
        # positions the real, hand-verified concordance uses, and why a value
        # outside that enum (a typo, a null, a future taxonomy entry this
        # mechanism was never checked against) is rejected rather than
        # silently reusing the same whole-section label logic for it.
        section_position = rec.get("section_position")
        if section_position not in _ALLOWED_SECTION_POSITIONS:
            raise ValueError(
                f"{path}: chapter {chapter} has section_position {section_position!r} -- "
                f"expected one of {sorted(_ALLOWED_SECTION_POSITIONS)}; partial-section "
                f"boundaries beyond this enum are not supported by this builder"
            )
        out.append({
            "book": book,
            "chapter": chapter,
            "start_section": start_section,
            "anchor_lat_sha256_16": anchor_hash,
            "anchor_en": anchor_en,
            "section_position": section_position,
        })
    out.sort(key=lambda r: (r["book"], r["chapter"]))
    return out


def build_spans(
    concordance: list[dict], chapters: dict[int, str], book_min: int, book_max: int,
    exclude_sections: set[str],
) -> list[dict]:
    """Concordance records (sorted by chapter, from `load_concordance`) plus
    `chapters` (from `load_chapters`) -> one span dict per chapter:
    `{chapter, start_section, end_section, anchor_lat_sha256_16, text}`.

    `end_section` for chapter N is chapter N+1's `start_section` minus one,
    or `book_max` for the last chapter -- by this construction consecutive
    spans can never gap or overlap, so what this function actually GUARDS
    is the precondition construction relies on: the two sources declaring
    exactly the same chapter set, and `start_section` strictly increasing
    chapter-over-chapter (a non-increasing step means the concordance's
    chapters are out of order, or two chapters share an anchor section --
    checked explicitly, with its own message, before the ordering check so
    a duplicate is never misreported as merely "out of order"); Blocker 2
    (Sol adversarial review): the FIRST chapter's `start_section` must equal
    `book_min` (the live spine's own minimum citable section, from the
    manifest's declared book range) exactly -- a concordance whose first
    chapter starts later than that would otherwise pass silently, leaving
    every section before it with no attached English at all and no error
    to say so. Blocker 1: each record's `anchor_en` must also open its own
    chapter's live text (`_anchor_en_opens_chapter`) -- English-side drift
    (a reordered/misnumbered/corrupted chapter) is invisible to the
    Latin-only `verify_anchor` hash check in `build_english_chunks` below,
    so it is checked here, before any chunk is emitted."""
    bad_exclude = [tok for tok in exclude_sections if not isinstance(tok, str) or not tok]
    if bad_exclude:
        # Major 3 defensive backstop: preflight's schema gate already
        # requires citation.exclude_sections to be a list of non-empty
        # strings, but this module is reachable from `astro build`/
        # `reader_pipeline all` runs that bypass preflight -- a stray
        # non-string token (a YAML integer) would otherwise never match the
        # stringified span numbers compared against it below and silently
        # fail to exclude anything.
        raise ValueError(f"exclude_sections must contain only non-empty strings, got {bad_exclude!r}")

    concordance_chapters = {r["chapter"] for r in concordance}
    source_chapters = set(chapters)
    missing_concordance = sorted(source_chapters - concordance_chapters)
    if missing_concordance:
        raise ValueError(f"chapter(s) {missing_concordance} have translated text but no concordance record")
    missing_source = sorted(concordance_chapters - source_chapters)
    if missing_source:
        raise ValueError(f"concordance record(s) for chapter(s) {missing_source} have no translated text")

    starts = [r["start_section"] for r in concordance]
    dupes = sorted({s for s in starts if starts.count(s) > 1})
    if dupes:
        raise ValueError(f"duplicate anchor start_section(s) shared across chapters: {dupes}")

    for prev, cur in zip(concordance, concordance[1:]):
        if cur["start_section"] <= prev["start_section"]:
            raise ValueError(
                f"chapters out of order: chapter {cur['chapter']} start_section "
                f"{cur['start_section']} does not exceed chapter {prev['chapter']}'s "
                f"start_section {prev['start_section']}"
            )

    if concordance[0]["start_section"] != book_min:
        raise ValueError(
            f"chapter {concordance[0]['chapter']}'s start_section "
            f"{concordance[0]['start_section']} does not equal the work's first "
            f"citable section {book_min} -- section(s) {book_min}.."
            f"{concordance[0]['start_section'] - 1} would be silently English-less"
        )

    spans = []
    for i, rec in enumerate(concordance):
        start = rec["start_section"]
        if not (book_min <= start <= book_max):
            raise ValueError(
                f"chapter {rec['chapter']}: start_section {start} is outside the "
                f"work's section range {book_min}..{book_max}"
            )
        if not _anchor_en_opens_chapter(chapters[rec["chapter"]], rec["anchor_en"]):
            raise ValueError(
                f"chapter {rec['chapter']}: anchor_en does not open the live English "
                f"chapter text -- the concordance and the English source have drifted "
                f"(a reordered, misnumbered, or corrupted chapter)"
            )
        end = concordance[i + 1]["start_section"] - 1 if i + 1 < len(concordance) else book_max
        touched = {str(n) for n in range(start, end + 1)} & exclude_sections
        if touched:
            raise ValueError(
                f"chapter {rec['chapter']}'s span (sections {start}-{end}) covers "
                f"excluded section token(s) {sorted(touched)} -- the concordance "
                f"references excluded apparatus, not translated text"
            )
        spans.append({
            "chapter": rec["chapter"],
            "start_section": start,
            "end_section": end,
            "anchor_lat_sha256_16": rec["anchor_lat_sha256_16"],
            "text": chapters[rec["chapter"]],
        })
    return spans


def verify_anchor(words: list[str], anchor_hash: str) -> bool:
    """True if some word-bounded substring of `words` (as-is, or with outer
    edge punctuation/quotes trimmed -- mirrors the pre-hash substring check
    `extract_yonge_fato.py._self_check_concordance` itself tolerates)
    hashes to `anchor_hash`. `words` must already be the LIVE, freshly
    -parsed spine text for one section, split on normalized whitespace.
    Never reconstructs, stores, or returns the matching phrase -- only a
    boolean, so PHI/TLG corpus text never flows back through this
    function's return value."""
    for i in range(len(words)):
        for j in range(i + 1, len(words) + 1):
            candidate = " ".join(words[i:j])
            if _anchor_hash(candidate) == anchor_hash:
                return True
            trimmed = candidate.strip(_EDGE_PUNCT)
            if trimmed and trimmed != candidate and _anchor_hash(trimmed) == anchor_hash:
                return True
    return False


def _section_num(token: str) -> int:
    """The section-number component of a column/boundary token: a
    book-section scheme's dotted `"1.48"` -> 48, or a flat scheme's bare
    `"48"` -> 48 (no book prefix to strip). Lets book_min/book_max
    derivation and the live-spine lookup below work unmodified for either
    scheme's column-token shape."""
    return int(token.split(".", 1)[1]) if "." in token else int(token)


def _segments_by_section(spine: dict, book_n: int) -> dict[int, dict]:
    """{section number: segment} for every live spine segment belonging to
    book `book_n` -- keyed by section NUMBER rather than the literal column
    token, so callers never need to know whether this work's column grammar
    is bare ("48") or dotted ("1.48")."""
    return {
        _section_num(seg["column"]): seg
        for seg in spine["segments"] if seg.get("book") == book_n
    }


def _segment_words(seg: dict) -> list[str]:
    text = _norm(" ".join(line["text"] for line in seg["lines"]))
    return text.split(" ") if text else []


def build_english_chunks(
    manifest: Manifest, spine: dict, chapters: dict[tuple[int, int], str],
    concordance: list[dict], exclude_sections: set[str], primary: dict,
) -> dict:
    """The EnglishChunk-shaped `english_chunks.json` dict, pure of file I/O
    given already-loaded chapters/concordance -- directly unit-testable
    against synthetic fixtures (see `build_english`, the thin I/O wrapper
    `run` actually calls).

    MULTI-BOOK (De Finibus phase 3): iterates `manifest.books` (one entry
    for De Fato's single implicit book, five for De Finibus), slicing the
    loaded `chapters`/`concordance` -- both keyed/tagged by an optional
    `book` field defaulting to 1, see `load_chapters`/`load_concordance` --
    to each book's own records and re-running the unchanged, single-book
    `build_spans` walk per book. A manifest declaring a book with no
    matching chapter/concordance records (or vice versa: chapters/
    concordance declaring a book the manifest doesn't) is a loud,
    upfront error -- silently slicing an empty per-book dict would
    otherwise reach `build_spans`' `concordance[0]` indexing with an empty
    list and raise a raw, unhelpful IndexError instead."""
    if not manifest.books:
        raise ValueError(f"{manifest.work_id}: no books declared for the chapter-concordance attachment")

    manifest_books = {b["n"] for b in manifest.books}
    chapter_books = {book for book, _chapter in chapters}
    concordance_books = {r["book"] for r in concordance}
    if chapter_books != manifest_books:
        raise ValueError(
            f"{manifest.work_id}: chapter source declares book(s) "
            f"{sorted(chapter_books)} but the manifest declares book(s) "
            f"{sorted(manifest_books)}"
        )
    if concordance_books != manifest_books:
        raise ValueError(
            f"{manifest.work_id}: concordance declares book(s) "
            f"{sorted(concordance_books)} but the manifest declares book(s) "
            f"{sorted(manifest_books)}"
        )

    chunks = []
    seen_ids: set[str] = set()
    for book_cfg in sorted(manifest.books, key=lambda b: b["n"]):
        book_n = book_cfg["n"]

        # MAJOR fix (Sol re-verification, 2026-07-21): `book_min` used to
        # come straight from the manifest's own declared `books[0].start` --
        # but the stage-1 coverage GUARANTEE `build_spans` makes (every
        # section from book_min onward gets English) is only as good as
        # book_min itself. A manifest whose declared start disagreed with
        # the LIVE spine (e.g. a stale hand-edit) could still pass every
        # check below if the concordance's first chapter happened to agree
        # with that same wrong value -- stage2 eventually catches a
        # manifest/live-spine mismatch, but only downstream of stage1's own
        # claim having already silently been wrong. `book_min` is therefore
        # derived HERE from the validated live spine columns actually
        # parsed for this book, and the manifest's own declared start is
        # separately required to equal it -- both fatal, per book.
        live_sections = sorted(
            _section_num(seg["column"]) for seg in spine["segments"] if seg.get("book") == book_n
        )
        if not live_sections:
            raise ValueError(
                f"{manifest.work_id}: no live spine segments found for book "
                f"{book_n} -- cannot derive book_min for the chapter-concordance "
                f"attachment"
            )
        book_min = live_sections[0]
        declared_book_min = _section_num(str(book_cfg["start"]))
        if declared_book_min != book_min:
            raise ValueError(
                f"{manifest.work_id}: book {book_n}'s manifest start "
                f"({book_cfg['start']!r}) does not equal the live spine's own "
                f"minimum citable section ({book_min}) -- a manifest and "
                f"concordance that agree on a WRONG start would otherwise "
                f"leave every live section below the true minimum silently "
                f"English-less at stage 1"
            )
        book_max = _section_num(str(book_cfg["end"]))

        book_chapters = {chapter: text for (book, chapter), text in chapters.items() if book == book_n}
        book_concordance = sorted(
            (r for r in concordance if r["book"] == book_n), key=lambda r: r["chapter"]
        )

        spans = build_spans(book_concordance, book_chapters, book_min, book_max, exclude_sections)
        by_section = _segments_by_section(spine, book_n)

        for span in spans:
            seg = by_section.get(span["start_section"])
            if seg is None:
                raise ValueError(
                    f"{manifest.work_id}: book {book_n} chapter {span['chapter']}: no "
                    f"citable Latin division at section {span['start_section']} -- the "
                    f"spine and the concordance have drifted"
                )
            if not verify_anchor(_segment_words(seg), span["anchor_lat_sha256_16"]):
                raise ValueError(
                    f"{manifest.work_id}: book {book_n} chapter {span['chapter']}: anchor "
                    f"hash {span['anchor_lat_sha256_16']!r} does not match any word-bounded "
                    f"substring of {seg['id']}'s live Latin text -- the Latin export "
                    f"changed and the concordance is stale"
                )
            # Defensive backstop: build_spans' duplicate-start_section check
            # should already prevent this per book, but a chunk ID collision
            # is cheap to catch here too (same posture as Munro's builder).
            if seg["id"] in seen_ids:
                raise ValueError(f"{manifest.work_id}: duplicate chunk anchor {seg['id']!r} across chapters")
            seen_ids.add(seg["id"])

            start, end = span["start_section"], span["end_section"]
            label = f"section {start}" if start == end else f"sections {start}–{end}"
            chunks.append({
                "id": seg["id"], "book": seg["book"], "column": seg["column"],
                "text": span["text"].strip(), "notes": [], "markers": [],
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
    chapters = load_chapters(SOURCES_DIR / primary["file"])
    concordance = load_concordance(SOURCES_DIR / primary["concordance"])
    exclude_sections = set((manifest.data.get("citation") or {}).get("exclude_sections") or [])
    return build_english_chunks(manifest, spine, chapters, concordance, exclude_sections, primary)


def build_alignment(english: dict) -> dict:
    """Standoff alignment scoped to just the anchor segments a chunk was
    actually placed at (mirrors stage1_verse_line_english.build_alignment)
    -- every pair is matched by construction, since `build_english_chunks`
    already raises loudly on any span it couldn't place or verify."""
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
