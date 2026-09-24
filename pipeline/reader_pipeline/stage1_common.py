"""Shared Stage 1 helpers.

This module holds behavior-preserving mechanics used by multiple stage1 sources:
XML tag normalization, whitespace collapse, paragraph-token joining, standoff
chunk bookkeeping, and JSON emission. Source-specific parsing stays in the
individual stage1 modules.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from lxml import etree

WS = re.compile(r"\s+")


def local_name(el) -> str | None:
    if not isinstance(el.tag, str):
        return None
    return etree.QName(el).localname


def collapse_ws(text: str) -> str:
    return WS.sub(" ", text)


def text_excluding_subtrees(el, skip: tuple[str, ...] = ("note", "head")) -> str:
    """Plain text under `el`, dropping skipped child subtrees but keeping tails."""
    out: list[str] = []

    def walk(node, is_root=False):
        tag = local_name(node) or ""
        if tag in skip and not is_root:
            if node.tail:
                out.append(node.tail)
            return
        if node.text:
            out.append(node.text)
        for child in node:
            walk(child)
        if not is_root and node.tail:
            out.append(node.tail)

    walk(el, is_root=True)
    return collapse_ws("".join(out)).strip()


def join_paragraph_parts(items: list, split_words: bool = False) -> str:
    """Join text items and None paragraph sentinels into a prose string."""
    parts: list[str] = []
    cur: list[str] = []
    for item in items:
        if item is None:
            if cur:
                parts.append(" ".join(cur))
                parts.append("\n")
                cur = []
        elif split_words:
            cur.extend(item.split())
        else:
            cur.append(item)
    if cur:
        parts.append(" ".join(cur))
    return "".join(parts)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def load_english_source(path: Path, key_prefix: str | None = None,
                         key_drop: frozenset[str] | None = None) -> dict[str, str]:
    """A clean English source JSON as {"<column>": text}, the column-token-
    keyed shape stage1_flat_english/stage1_book_section_english's
    `_load_prose` and `validate_english_source` (below) both consume.

    `key_prefix` (optional): a store shared across several flat-scheme works
    keys each work's entries "<work-id>:<column>" rather than the bare
    column token a single work's spine expects (Epicurus' three Letters,
    all sliced from one hicks-epicurus-letters.clean.json store keyed
    "letter-to-herodotus:35" etc. -- see manifests/epicurus-letter-to-*.yaml's
    english.primary.key_prefix). When given, only keys starting with the
    prefix are kept, stripped of it, before the rest of this function's
    normal per-shape handling runs; a key with no matching prefix is simply
    not this work's own entry and is dropped (the same "extra key" error
    validate_english_source already raises for a genuinely mis-keyed source
    still fires downstream, since a prefix that matches nothing leaves an
    empty dict, which trivially fails the spine reconciliation).

    `key_drop` (optional): pre-column-token keys (after `key_prefix`
    stripping) to discard outright before this work's spine reconciliation
    runs -- for a source key demonstrably NOT this edition's text for the
    column it happens to be filed under (Vatican Sayings' Bailey store: a
    handful of keys carry content misplaced by the extraction's own known,
    disclosed OCR-anchor drift -- see manifests/epicurus-vatican-sayings.yaml's
    english.primary.key_drop comment for the verified evidence). This is a
    manifest-declared exclusion of specific keys already known to be wrong,
    not a general filter -- it must never be used to paper over an
    unreviewed mismatch.

    Accepts either of the two shapes this corpus's extractors produce:
      * the established dict shape ({"<chapter>": text} for a flat scheme,
        {"<book>.<chapter>": text} for book-section -- extract_miller_perseus.py,
        extract_oldfather_wikisource.py, etc.), returned as-is (keys coerced
        to str for uniformity);
      * a list-of-records shape ([{"section": n, "text": ...}] for a flat
        scheme, [{"book": n, "section": n, "text": ...}] for book-section --
        extract_falconer_perseus.py's convention), normalized to the same
        dotted/bare column-token keys the dict shape already uses.
    Both normalize to the identical column-token-keyed dict downstream code
    already expects, so no caller needs to know which shape its source file
    used.

    The dict shape is trusted as-is (no schema on it -- it IS the final
    key -> text mapping already, matching every existing dict-producing
    extractor's own discipline). The list-of-records shape gets schema
    validation the dict shape has no analogous need for, because it is
    normalized rather than passed straight through: `book`/`section`, when
    present on a record, must be a real int (bool excluded -- `bool` is an
    `int` subclass in Python, and a stray `True`/`False` must not silently
    become key `"1"`/`"0"`); `text` must be a non-empty string; two records
    that normalize to the SAME key raise (naming both record indices)
    rather than the second silently overwriting the first. Unknown extra
    record keys (e.g. extract_rackham_fin.py's `"chapter"`) are tolerated,
    same lenient posture as the dict shape: this loader only cares about
    the keys it actually consumes."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        items = {str(k): v for k, v in data.items()}
        if key_prefix is not None:
            items = {k[len(key_prefix):]: v for k, v in items.items()
                     if k.startswith(key_prefix)}
        if key_drop:
            items = {k: v for k, v in items.items() if k not in key_drop}
        return items
    out: dict[str, str] = {}
    first_index: dict[str, int] = {}
    for i, rec in enumerate(data):
        for field in ("book", "section"):
            if field not in rec:
                continue
            val = rec[field]
            if isinstance(val, bool) or not isinstance(val, int):
                raise ValueError(
                    f"{path}: record {i} has non-integer {field!r} ({val!r}); "
                    f"list-of-records shape requires int book/section values"
                )
        text = rec.get("text")
        if not isinstance(text, str) or not text:
            raise ValueError(
                f"{path}: record {i} has invalid 'text' ({text!r}); "
                f"must be a non-empty string"
            )
        key = f"{rec['book']}.{rec['section']}" if "book" in rec else str(rec["section"])
        if key in first_index:
            raise ValueError(
                f"{path}: records {first_index[key]} and {i} both normalize "
                f"to key {key!r} -- duplicate would silently overwrite"
            )
        first_index[key] = i
        out[key] = text
    return out


def validate_english_source(manifest, spine: dict, cfg: dict, slot: str,
                            sources_dir: Path) -> None:
    """Loud key-set reconciliation between a clean chapter-keyed English
    source JSON and the Greek spine, for the direct-lookup builders
    (stage1_book_section_english, stage1_flat_english) — Sol review round 3.

    Those builders iterate SPINE segments and look each column up in the
    source, so without this check an extra/mis-keyed source key is silently
    ignored and a missing SECONDARY key silently vanishes from
    ross_chunks.json (stage2's alignment check only covers the primary).
    Here the source's key set must equal the spine's column set exactly:

      * a source key matching no spine column is ALWAYS a hard error (it is
        either mis-keyed or the source doesn't match the declared work);
      * a spine column with no source key is a hard error unless the manifest
        declares it a genuine edition gap — primary gaps in the existing
        `alignment_allow_unmatched`, secondary gaps in the symmetric
        `alignment_allow_unmatched_secondary` (both keyed by segment id,
        "5:5.37", matching how meditations.yaml declares its Haines gaps).

    Works for both direct-lookup schemes without dispatch: a book-section
    source is keyed "<book>.<chapter>" — exactly its column token — and a
    flat source is keyed "<chapter>", exactly its column token too.

    `sources_dir` is passed by the CALLER from its own module-level
    SOURCES_DIR binding (not read from config here) so the caller's binding
    stays the single point of redirection, as everywhere else in stage1."""
    source_keys = set(load_english_source(
        sources_dir / cfg["file"], key_prefix=cfg.get("key_prefix"),
        key_drop=frozenset(cfg.get("key_drop", ()))))
    columns = {seg["column"] for seg in spine["segments"]}

    extra = sorted(source_keys - columns)
    if extra:
        raise ValueError(
            f"{manifest.work_id}: english.{slot} ({cfg['file']}) carries "
            f"{len(extra)} key(s) matching no spine column: "
            f"{', '.join(extra[:10])}{' …' if len(extra) > 10 else ''}"
        )

    allow_key = ("alignment_allow_unmatched" if slot == "primary"
                 else "alignment_allow_unmatched_secondary")
    # allowances resolve against exact spine segment ids ("book:column") —
    # a bare-column match would let a wrong-book entry mask a real gap
    segment_ids = {f"{seg['book']}:{seg['column']}" for seg in spine["segments"]}
    allowed_ids = set(manifest.data.get(allow_key, []))
    unknown_allow = sorted(allowed_ids - segment_ids)
    if unknown_allow:
        raise ValueError(
            f"{manifest.work_id}: {allow_key} names segment id(s) not in the "
            f"Greek spine: {', '.join(unknown_allow)}"
        )

    # The set of segments GENUINELY unmatched by the source (Sol review
    # blocker: this used to only be checked in the "missing" direction below
    # — an allowance entry for a segment that IS actually matched by the
    # source was silently tolerated, an unreviewable stale declaration that
    # masks information about the source's real coverage). Two-way exact,
    # mirroring stage1_greek's lettered_fragments/unmarked_columns
    # precedent: `allowed_ids` must equal `unmatched_ids` exactly.
    unmatched_ids = {
        f"{seg['book']}:{seg['column']}" for seg in spine["segments"]
        if seg["column"] not in source_keys
    }
    stale_allow = sorted(allowed_ids - unmatched_ids)
    if stale_allow:
        raise ValueError(
            f"{manifest.work_id}: {allow_key} names segment id(s) that ARE "
            f"matched by english.{slot} ({cfg['file']}) -- a stale "
            f"allowance declaration must be removed from the manifest, not "
            f"left to silently no-op: {', '.join(stale_allow[:10])}"
            f"{' …' if len(stale_allow) > 10 else ''}"
        )
    missing_ids = sorted(unmatched_ids - allowed_ids)
    if missing_ids:
        raise ValueError(
            f"{manifest.work_id}: english.{slot} ({cfg['file']}) is missing "
            f"{len(missing_ids)} chapter(s) the Greek spine carries: "
            f"{', '.join(missing_ids[:10])}{' …' if len(missing_ids) > 10 else ''} — "
            f"declare a genuine edition gap in the manifest's {allow_key}"
        )


class StandoffChunkMixin:
    """Chunk text plus standoff notes/markers for TEI walkers.

    The consuming walker supplies `book`, `column`, `chunks`, and `_by_key`.
    """

    def _chunk(self) -> dict:
        key = (self.book, self.column)
        chunk = self._by_key.get(key)
        if chunk is None:
            chunk = {
                "id": f"{self.book}:{self.column}",
                "book": self.book,
                "column": self.column,
                "text": "",
                "notes": [],
                "markers": [],
            }
            self._by_key[key] = chunk
            self.chunks.append(chunk)
        return chunk

    def add_text(self, raw: str | None):
        if not raw:
            return
        chunk = self._chunk()
        piece = collapse_ws(raw)
        if piece == " " and (
            not chunk["text"] or chunk["text"].endswith(" ") or chunk["text"].endswith("\n")
        ):
            return
        if (chunk["text"].endswith(" ") or chunk["text"].endswith("\n")) and piece.startswith(" "):
            piece = piece.lstrip(" ")
        if not chunk["text"]:
            piece = piece.lstrip(" ")
        chunk["text"] += piece

    def add_note(self, el):
        text = collapse_ws("".join(el.itertext())).strip()
        chunk = self._chunk()
        chunk["notes"].append({"offset": len(chunk["text"].rstrip()), "text": text})

    def add_marker(self, kind: str, n: str):
        chunk = self._chunk()
        chunk["markers"].append(
            {"kind": kind, "n": n, "offset": len(chunk["text"].rstrip())}
        )

    def add_paragraph(self):
        chunk = self._chunk()
        if chunk["text"]:
            offset = len(chunk["text"].rstrip())
            marker = {"kind": "paragraph", "n": "", "offset": offset}
            if not chunk["markers"] or chunk["markers"][-1] != marker:
                chunk["markers"].append(marker)
            if not chunk["text"].endswith((" ", "\n")):
                chunk["text"] = chunk["text"].rstrip() + " "
