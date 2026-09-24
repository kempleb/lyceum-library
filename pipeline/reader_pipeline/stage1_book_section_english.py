"""Stage 1b (book-section variant): primary + secondary English translations
for a book-section scheme work (Marcus Aurelius' Meditations).

Unlike a Bekker/archive-scheme translation — which stage1_archive.build_chunks
must proportionally split across however many Greek columns a chapter spans —
book-section's translation-to-column mapping is exactly 1:1: every chapter
IS its own Greek spine segment (stage1_greek's _parse_flat_book_section
flattens a whole TEI chapter div, sections included, to one column). There is
no gutter to interpolate either (lines_user_facing is False for this scheme),
so this is a direct lookup, not a reduced case of the archive machinery: a
chapter-keyed prose dict straight onto its one matching segment.

Primary lands in the ordinary EnglishChunk shape (english_chunks.json) the
reader's main parallel column consumes; a secondary lands in the overlay
piece shape (ross_chunks.json) the 'ross' translation slot consumes. Both are
loaded from a clean {"<book>.<chapter>": "text"} JSON produced by
pipeline/tools/extract_haines.py / extract_long.py — see sources/INVENTORY.md
for how those were extracted and their known coverage gaps.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .stage1_common import load_english_source, validate_english_source, write_json
from .stage1_english import build_alignment


def _load_prose(cfg: dict) -> dict[tuple[int, int], str]:
    """{(book, chapter): text} from a clean per-chapter English source
    keyed "<book>.<chapter>" (english.primary/secondary's `file`) -- see
    load_english_source's docstring for the two source shapes this
    accepts."""
    data = load_english_source(SOURCES_DIR / cfg["file"])
    out: dict[tuple[int, int], str] = {}
    for key, text in data.items():
        book_s, chap_s = key.split(".", 1)
        out[(int(book_s), int(chap_s))] = text
    return out


def _chapter_of(column: str) -> int:
    """The chapter number from a book-section column token ("4.23" -> 23)."""
    return int(column.split(".", 1)[1])


def _load_titles_sidecar(rel: str) -> dict[str, str]:
    """{"<column>": "title"} from an english.primary.titles_sidecar path
    (relative to SOURCES_DIR) — a chapter's own descriptive heading (e.g.
    Oldfather's "Of freedom" for Discourses 4.1), produced by
    pipeline/tools/extract_oldfather_wikisource.py. Keyed by column token
    directly, same as `_load_verse_sidecar`."""
    return json.loads((SOURCES_DIR / rel).read_text(encoding="utf-8"))


def _load_paras_sidecar(rel: str) -> dict[str, list[dict]]:
    """{"<column>": [{"n", "o"}]} from an english.primary.paras_sidecar path
    — standoff paragraph-marker offsets over a column's clean (post-strip)
    English text (Discourses' Oldfather: every 5th TLG-numbered section, see
    extract_oldfather_wikisource.py's module docstring). Keyed by column
    token directly, same as `_load_verse_sidecar`."""
    return json.loads((SOURCES_DIR / rel).read_text(encoding="utf-8"))


# How far an English marker may sit from where its own Greek section starts,
# as a fraction of the chapter, before it is treated as naming the wrong
# section. Measured over all 481 Discourses markers: the worst SOUND marker
# is 0.067 out (3.8 n=5), while item 100's mislabelled 3.3 marker is 0.189
# out — this sits between them with room on both sides. Deliberately loose:
# an English sentence never tracks its Greek character-for-character, so the
# gate is a wrong-section detector, not an alignment measure.
#
# This number was measured on the Discourses only. A different work's
# translator could expand some sections of a chapter far more unevenly than
# Oldfather did, which would legitimately push a correctly labelled marker
# past this tolerance. Before this gate is relied on for a new work's own
# paragraph-marker sidecar, that work's own markers need to be measured the
# same way this one was, not assumed to fit.
_PARA_POSITION_TOLERANCE = 0.12


def _greek_section_starts(spine: dict) -> dict[str, dict[int, float]]:
    """{"<column>": {section number: fraction of the chapter's Greek that
    precedes that section's start}} for every segment whose Greek line
    carries a `sections` standoff channel (stage1_greek's `section_paragraphs`
    opt-in) OR a per-line `sec` field (stage1_greek's `lined_source` opt-in,
    docs/lined-source-plan.md Q6 — the one coupling that must survive
    Discourses' move to per-print-line emission: once Discourses stops
    emitting `sections`, this function's only remaining source for it is
    `sec`) — used by `_validated_paras` both to check that English's
    paragraph markers are a SUBSET of the Greek channel's kept section
    numbers for the same chapter (the keys) and to check that each marker
    sits roughly where its own section does (the fractions). A work opts
    into at most one of the two channels per chapter in practice, but both
    are read unconditionally here so this function never needs to know which
    one is live; the chapter's Greek is measured as its lines joined with
    single spaces, matching how stage1_greek flattens a chapter."""
    out: dict[str, dict[int, float]] = {}
    for seg in spine["segments"]:
        texts = [line["text"] for line in seg["lines"]]
        total = len(" ".join(texts))
        if not total:
            continue
        starts: dict[int, int] = {}
        run = 0
        for line, text in zip(seg["lines"], texts):
            for entry in line.get("sections") or ():
                starts.setdefault(entry["n"], run + entry["o"])
            sec = line.get("sec")
            if sec is not None:
                starts.setdefault(sec, run)
            run += len(text) + 1
        if starts:
            out[seg["column"]] = {n: o / total for n, o in starts.items()}
    return out


def _validated_paras(
    work: str, column: str, text: str, paras: list[dict],
    greek_starts: dict[int, float],
) -> list[dict]:
    """`paras` after validating strict ascending in-bounds offsets (a real
    structural bug — loud ValueError); checking each entry's `n` is a member
    of `greek_starts` (the Greek section channel's KEPT numbers for this same
    chapter); and checking each entry SITS where its own section does, within
    `_PARA_POSITION_TOLERANCE` of the chapter (another loud ValueError).

    That last gate is REVIEW-CHECKLIST item 100: Discourses 3.3's first
    Wikisource marker is labelled 10 but sits at the sentence translating
    Greek section 5, and membership alone passed it happily — 10 is one of
    that chapter's 22 Greek section numbers. A marker that names the wrong
    section is a false alignment claim, so it fails the build rather than
    being dropped: unlike an unknown number (below) there is nothing here to
    report to John case by case, only a data point to repair.

    Membership, by contrast, stays a warning. Since stage1_greek.
    _chapter_sections now SNAPS every section boundary rather than dropping
    any (a print-line hyphen wrap fusing mid-word moves the boundary back to
    the start of the straddling word instead of vanishing it — ground-truth
    adjudication 2026-07-16 found this is the only case that ever occurs),
    `greek_starts` normally holds every TLG section number the chapter's XML
    declares, so this mismatch path is not expected to fire in practice. It
    is kept as a defensive check (never a hard build failure) against a
    genuine, unrelated mismatch — e.g. an English sidecar marker keyed to a
    section number the Greek XML simply does not contain — which would still
    be a real, reportable oddity, not a build-breaking one: that ONE marker
    is dropped and reported (never silently absorbed) — see the pipeline
    run's printed WARNING and the janky-review-list report this feeds John's
    case-by-case call."""
    if not paras:
        return []
    kept: list[dict] = []
    prev_o = -1
    for p in paras:
        o, n = p["o"], p["n"]
        if not (0 <= o < len(text)):
            raise ValueError(
                f"{column}: English paragraph offset {o} out of bounds for "
                f"text of length {len(text)}"
            )
        if o <= prev_o:
            raise ValueError(
                f"{column}: English paragraph offsets not strictly "
                f"ascending at o={o}"
            )
        prev_o = o
        if n not in greek_starts:
            print(
                f"  stage1 WARNING: {column} English paragraph marker n={n} "
                f"is not among the Greek section channel's kept numbers "
                f"{sorted(greek_starts, key=str)} -- dropped, not rendered"
            )
            continue
        english_at = o / len(text)
        greek_at = greek_starts[n]
        if abs(english_at - greek_at) > _PARA_POSITION_TOLERANCE:
            book, _, chapter = column.partition(".")
            raise ValueError(
                f"{work} book {book}, chapter {chapter} (column {column}): "
                f"English paragraph marker n={n} sits {english_at:.1%} "
                f"through the chapter's English text, but Greek section {n} "
                f"starts {greek_at:.1%} through the chapter's Greek "
                f"(tolerance {_PARA_POSITION_TOLERANCE:.1%}) -- the marker's "
                f"number and its offset disagree; expected a marker here for "
                f"the section that begins near {english_at:.1%}. If the "
                f"marker is right and the translation is simply uneven "
                f"here, the tolerance (measured on the Discourses only) "
                f"needs re-measuring for this work."
            )
        kept.append(p)
    return kept


def _load_verse_sidecar(rel: str) -> dict[str, list[dict]]:
    """{"<column>": [{"start", "end", "breaks"}, ...]} from an
    english.primary.verse_sidecar path (relative to SOURCES_DIR) — standoff
    verse ranges over a column's clean (post-strip) English text, produced by
    a DL-shaped extractor as e.g. sources/hicks-dl/hicks-verse.json. Keyed
    directly by the book-section column token ("7.85"), matching
    seg["column"] — no book/chapter split needed, unlike `_load_prose`'s
    dotted-key dict (which IS split, since it is looked up by (book, chapter)
    tuple instead)."""
    return json.loads((SOURCES_DIR / rel).read_text(encoding="utf-8"))


def _validated_verse_ranges(column: str, text: str, ranges: list[dict]) -> list[dict]:
    """`ranges` after validating every entry loudly: each range must be
    in-bounds and non-empty (0 <= start < end <= len(text)), and every break
    must fall STRICTLY inside its range (start < break < end) — a break
    equal to a boundary would double-render or misrender the edge line (see
    the reader's Reader.svelte verse rendering).

    Also rejects any two ranges in the column that overlap or nest: sorted
    by start, a following range whose start is before the previous range's
    end (including an identical range, which trivially satisfies that) is a
    loud error. The reader's groupVerse (Reader.svelte) treats a second
    verseStart as unconditionally starting a fresh `lines` accumulator, so an
    overlapping/nested pair that slipped past validation would silently
    discard the first range's already-accumulated lines at render time
    instead of failing loud here. Ranges that merely abut — the next range's
    start equal to the previous range's end — are legitimate and pass;
    input order need not be pre-sorted by start."""
    out = []
    for r in ranges:
        start, end, breaks = r["start"], r["end"], r.get("breaks", [])
        if not (0 <= start < end <= len(text)):
            raise ValueError(
                f"{column}: verse range [{start}, {end}) is out of bounds or "
                f"empty for text of length {len(text)}"
            )
        for b in breaks:
            if not (start < b < end):
                raise ValueError(
                    f"{column}: verse break {b} is not strictly inside range "
                    f"[{start}, {end})"
                )
        out.append({"start": start, "end": end, "breaks": list(breaks)})
    ordered = sorted(out, key=lambda r: r["start"])
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt["start"] < prev["end"]:
            raise ValueError(
                f"{column}: verse ranges [{prev['start']}, {prev['end']}) and "
                f"[{nxt['start']}, {nxt['end']}) overlap or nest"
            )
    return out


def build_english(manifest: Manifest, spine: dict, cfg: dict) -> dict:
    """Primary English chunks (EnglishChunk shape): one whole-chapter chunk
    per spine segment. A segment whose chapter has no translation text (an
    unrecoverable OCR gap or a translator/edition section merge — see
    sources/INVENTORY.md) is simply omitted, same as stage1_archive drops an
    empty piece.

    `cfg["verse_sidecar"]` (optional) names a standoff-verse sidecar file (see
    _load_verse_sidecar); a chunk whose column has ranges gets a validated
    `verse` field attached. Absent for every other chunk (the overwhelming
    majority, and every work with no verse_sidecar at all) — never an empty
    array, matching stage7_emit's conditional-spread convention.

    `cfg["titles_sidecar"]`/`cfg["paras_sidecar"]` (optional, Discourses
    only) attach a per-chapter `title` and validated `paras` the same
    conditional-spread way — see `_load_titles_sidecar`/`_load_paras_sidecar`
    /`_validated_paras`."""
    prose = _load_prose(cfg)
    verse_sidecar = _load_verse_sidecar(cfg["verse_sidecar"]) if cfg.get("verse_sidecar") else {}
    titles_sidecar = _load_titles_sidecar(cfg["titles_sidecar"]) if cfg.get("titles_sidecar") else {}
    paras_sidecar = _load_paras_sidecar(cfg["paras_sidecar"]) if cfg.get("paras_sidecar") else {}
    greek_starts = _greek_section_starts(spine) if paras_sidecar else {}
    chunks = []
    for seg in spine["segments"]:
        text = prose.get((seg["book"], _chapter_of(seg["column"])), "").strip()
        if not text:
            continue
        chunk = {
            "id": seg["id"], "book": seg["book"], "column": seg["column"],
            "text": text, "notes": [], "markers": [],
        }
        ranges = verse_sidecar.get(seg["column"])
        if ranges:
            chunk["verse"] = _validated_verse_ranges(seg["column"], text, ranges)
        title = titles_sidecar.get(seg["column"])
        if title:
            chunk["title"] = title
        raw_paras = paras_sidecar.get(seg["column"])
        if raw_paras:
            validated = _validated_paras(
                manifest.work_id, seg["column"], text, raw_paras,
                greek_starts.get(seg["column"], {}),
            )
            if validated:
                chunk["paras"] = validated
        chunks.append(chunk)
    return {
        "work": manifest.work_id,
        "source": cfg.get("file", ""),
        "translation": cfg["name"],
        "chunks": chunks,
    }


def build_overlay(spine: dict, cfg: dict) -> dict[str, list[dict]]:
    """A secondary translation as chapter-anchored overlay pieces
    ({seg_id: [{chapter, text, cont, bekker}]}) — the shape the reader's
    'ross' slot consumes. `cont` is always False (a piece is never a
    continuation of an earlier column — no column ever straddles a chapter)
    and `bekker` always empty (book-section carries no user-facing line
    gutter to tick)."""
    prose = _load_prose(cfg)
    out: dict[str, list[dict]] = {}
    for seg in spine["segments"]:
        chapter = _chapter_of(seg["column"])
        text = prose.get((seg["book"], chapter), "").strip()
        if text:
            out[seg["id"]] = [{"chapter": str(chapter), "text": text,
                               "cont": False, "bekker": []}]
    return out


def run(manifest: Manifest, spine: dict) -> tuple[Path, Path]:
    eng_cfg = manifest.data["english"]
    # Loud key-set reconciliation for BOTH slots before anything is built —
    # see validate_english_source's docstring (an undeclared gap or a
    # mis-keyed source must never silently drop translation text). Genuine
    # edition gaps are declared per slot: alignment_allow_unmatched for the
    # primary (as meditations.yaml's Haines 5.37/12.15 already are),
    # alignment_allow_unmatched_secondary for the secondary.
    validate_english_source(manifest, spine, eng_cfg["primary"], "primary",
                            SOURCES_DIR)
    sec = eng_cfg.get("secondary")
    if sec:
        validate_english_source(manifest, spine, sec, "secondary", SOURCES_DIR)
    english = build_english(manifest, spine, eng_cfg["primary"])
    out_dir = BUILD_DIR / "stage1"
    out_dir.mkdir(parents=True, exist_ok=True)
    eng_path = out_dir / "english_chunks.json"
    write_json(eng_path, english)
    align_path = out_dir / "alignment.json"
    write_json(align_path, build_alignment(spine, english))
    # Secondary translation (Long) fills the same 'ross' overlay slot every
    # other work's secondary does. __main__._stage1 already clears
    # ross_chunks.json/third_chunks.json/overlays.json before dispatching
    # here, so a work with no secondary simply leaves it cleared.
    if sec:
        write_json(out_dir / "ross_chunks.json", build_overlay(spine, sec))
    return eng_path, align_path
