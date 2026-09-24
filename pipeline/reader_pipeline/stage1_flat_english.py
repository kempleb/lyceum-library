"""Stage 1b (flat `section` variant): primary + secondary English translations
for the flat, bookless `section` scheme (Epictetus' Enchiridion).

Mirrors stage1_book_section_english.py's 1:1 chapter-to-column mapping
exactly — every column IS its own Greek spine segment (stage1_greek's
_parse_flat_chapter flattens a whole TEI chapter div to one column), no
gutter to interpolate (lines_user_facing is False for this scheme too) — the
only difference is the column token itself: a flat scheme's column is a bare
chapter integer ("53"), not a dotted book.chapter token ("4.23"), so the
source JSON is keyed "<chapter>" rather than "<book>.<chapter>" and there is
no book component to split off. Every segment belongs to the work's single
declared book (spine assigns book=1 to every flat column; see
stage1_greek._parse_flat_chapter).

Primary lands in the ordinary EnglishChunk shape (english_chunks.json); a
secondary lands in the overlay piece shape (ross_chunks.json) — both loaded
from a clean {"<chapter>": "text"} JSON produced by
pipeline/tools/extract_oldfather_wikisource.py /
extract_long_epictetus_wikisource.py (see sources/INVENTORY.md for how those
were extracted and Long's modern-numbering re-key)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .stage1_common import load_english_source, validate_english_source, write_json
from .stage1_english import build_alignment


def _load_prose(cfg: dict) -> dict[str, str]:
    """{"<chapter>": text} from a clean bare-chapter-keyed English source
    (english.primary/secondary's `file`) -- see load_english_source's
    docstring for the two source shapes this accepts. `cfg["key_prefix"]`
    (optional) slices one work's own entries out of a store shared across
    several flat-scheme works (Epicurus' three Letters, one
    hicks-epicurus-letters.clean.json store -- see that docstring).
    `cfg["key_drop"]` (optional) excludes specific keys already known to be
    wrong for this edition (Vatican Sayings' Bailey store -- see that
    docstring)."""
    return load_english_source(
        SOURCES_DIR / cfg["file"], key_prefix=cfg.get("key_prefix"),
        key_drop=frozenset(cfg.get("key_drop", ())))


def _load_paras_sidecar(rel: str) -> dict[str, list[dict]]:
    """{"<column>": [{"n", "o"}]} from an english.primary.paras_sidecar path
    -- standoff marginal-line-number offsets over a column's clean English
    text (Parmenides' Burnet extractor: every 5th Diels verse-line number,
    see pipeline/tools/extract_burnet_wikisource.py's module doc). Same
    sidecar SHAPE as stage1_book_section_english.py's Discourses paras (an
    `{n, o}` standoff list), but this scheme's `n` is a DK line number with
    no Greek-side channel to cross-check it against (unlike Discourses'
    TLG-section paras) -- see `_validated_paras` below for why this scheme
    only validates the offsets, not `n` membership."""
    return json.loads((SOURCES_DIR / rel).read_text(encoding="utf-8"))


def _validated_paras(column: str, text: str, paras: list[dict]) -> list[dict]:
    """`paras` after validating strict ascending in-bounds offsets (a real
    structural bug -- loud ValueError). Unlike stage1_book_section_english's
    `_validated_paras`, there is no Greek-side `sections` channel for a dk
    verse work to cross-check `n` against (a dk fragment's Greek line
    channel IS the citable line numbering itself, already validated by
    preflight's verse line gate) -- every entry that passes the bounds
    check is kept as-is; `n` is a pure display label (Burnet's own marginal
    Diels line number), not cross-validated against anything on the Greek
    side."""
    if not paras:
        return []
    prev_o = -1
    for p in paras:
        o = p["o"]
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
    return list(paras)


def build_english(manifest: Manifest, spine: dict, cfg: dict) -> dict:
    """Primary English chunks (EnglishChunk shape): one whole-chapter chunk
    per spine segment. A segment whose chapter has no translation text is
    simply omitted, same as the book-section builder does.

    `cfg["paras_sidecar"]` (optional, Parmenides' Burnet Fragmenta only)
    attaches a validated `paras` field the same conditional-spread way
    stage1_book_section_english.py's Discourses builder does -- see
    `_load_paras_sidecar`/`_validated_paras`."""
    prose = _load_prose(cfg)
    paras_sidecar = _load_paras_sidecar(cfg["paras_sidecar"]) if cfg.get("paras_sidecar") else {}
    chunks = []
    for seg in spine["segments"]:
        text = prose.get(seg["column"], "").strip()
        if not text:
            continue
        chunk = {
            "id": seg["id"], "book": seg["book"], "column": seg["column"],
            "text": text, "notes": [], "markers": [],
        }
        raw_paras = paras_sidecar.get(seg["column"])
        if raw_paras:
            validated = _validated_paras(seg["column"], text, raw_paras)
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
    ({seg_id: [{chapter, text, cont, bekker}]}), the shape the reader's
    'ross' slot consumes — `cont` always False, `bekker` always empty (no
    user-facing line gutter for this scheme either)."""
    prose = _load_prose(cfg)
    out: dict[str, list[dict]] = {}
    for seg in spine["segments"]:
        chapter = seg["column"]
        text = prose.get(chapter, "").strip()
        if text:
            out[seg["id"]] = [{"chapter": chapter, "text": text,
                               "cont": False, "bekker": []}]
    return out


def run(manifest: Manifest, spine: dict) -> tuple[Path, Path]:
    eng_cfg = manifest.data["english"]
    # Loud key-set reconciliation for BOTH slots before anything is built —
    # see validate_english_source's docstring (an undeclared gap or a
    # mis-keyed source must never silently drop translation text).
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
    # __main__._stage1 already clears ross_chunks.json/third_chunks.json/
    # overlays.json before dispatching here, so a work with no secondary
    # simply leaves it cleared.
    if sec:
        write_json(out_dir / "ross_chunks.json", build_overlay(spine, sec))
    return eng_path, align_path
