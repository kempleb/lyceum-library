"""Stage 7: emit the frontend data set under build/dist/ne/.

Per the approved formats:
  - book-{n}.json     spine segments per Bekker column (split per book),
                      Greek lines with token arrays carrying Beta Code
                      analysis keys, paired English chunk with standoff
                      notes/markers.
  - analyses.json     token key -> analyses (lemma, gloss, parse) with the
                      LSJ keys for each lemma merged in.
  - lsj|ls/{letter}.json letter-sharded dictionary entries (LSJ or Lewis &
                      Short, per work.language), corpus lemmata only.
  - manifest.json     work metadata and per-book stats.
Reports (validation, unmatched tokens, sigla, missing lemmata) are copied
to build/dist/reports/ for the Milestone 2 review.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import dk_witness
from . import scheme as scheme_mod
from . import stage5_lsj
from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .parse_filter import filter_parses
from .refs import column_key
from .stage3_tokenize import _SPINE_FILENAMES


def _load(rel: str):
    return json.loads((BUILD_DIR / rel).read_text(encoding="utf-8"))


def _manifest_v1_fields(manifest: Manifest, out_dir: Path) -> dict:
    """Build the versioned contract fields added to the legacy manifest."""
    work = manifest.data["work"]
    language = manifest.language
    source_prefix = "tlg" if language == "grc" else "phi"
    source_license = work.get("source_license") or {"status": "unverified"}

    english = manifest.data.get("english") or {}
    translations = []
    for slot in ("primary", "secondary", "third"):
        entry = english.get(slot)
        if not entry:
            continue
        translations.append({
            "id": entry["id"],
            "name": entry["name"],
            "slot": slot,
            "default": slot == "primary",
            **({"alignment": entry["model"]} if entry.get("model") else {}),
            "license": entry.get("license") or {"status": "unverified"},
        })
    for entry in english.get("overlays") or []:
        translations.append({
            "id": entry["id"],
            "name": entry["name"],
            "slot": "overlay",
            "default": False,
            **({"alignment": entry["model"]} if entry.get("model") else {}),
            "license": entry.get("license") or {"status": "unverified"},
        })
    # Freeman-style summary overlay (Sol review finding 4, folded into P2
    # stage 5): a manifest's `english.summary_overlay` ({id, columns}) is a
    # per-column alternate view of the SAME primary translation's own
    # source -- Kathleen Freeman's short précis alongside her full
    # rendering (manifests/gorgias-fragments.yaml) -- so it is emitted as
    # an "overlay"-slot translation, `kind: "summary"`, scoped to its
    # declared columns. Neither name nor license exists on
    # `summary_overlay` in the YAML; the name is derived from the primary
    # translation's own name, matching the human-authored
    # `registry.translations` precedent for this exact entry in
    # gorgias-fragments.yaml ("... — summary"), and the license falls back
    # to unverified like every other translation slot when the manifest
    # declares none.
    summary_overlay = english.get("summary_overlay")
    if summary_overlay and summary_overlay.get("id"):
        primary_name = (english.get("primary") or {}).get("name")
        translations.append({
            "id": summary_overlay["id"],
            "name": f"{primary_name} — summary" if primary_name else summary_overlay["id"],
            "slot": "overlay",
            "kind": "summary",
            "default": False,
            "columns": list(summary_overlay.get("columns") or []),
            "license": summary_overlay.get("license") or {"status": "unverified"},
        })
    # Column-level English sources (Sol review finding 4): a manifest's
    # `english.column_sources` swaps in a different translator's rendering
    # as the DEFAULT English for one specific column (e.g.
    # gorgias-fragments.yaml's Gatt/Gazis Encomium/Apology translations,
    # displacing Freeman's own summary for B11/B11a) -- a real,
    # separately-licensed translation, not a slot a reader picks from a
    # menu, so it gets its own "column" slot (schemas/manifest.v1.json's
    # translation.slot enum) scoped to exactly the one column it covers.
    # No stable id exists in the YAML for a column source (unlike
    # primary/secondary/third/overlays, which always declare one) --
    # derived deterministically from its data file's basename (minimal,
    # readable, stable across re-emits: "gatt-helen.clean.json" ->
    # "gatt-helen"). `credit` (translator/source/year/licence) is the
    # per-entry rights record; folded into the standard license shape rather
    # than a bespoke credit object: `status: cc` (with its `name`, the CC
    # abbreviation, and `url`) passes through as {status "cc", name, url,
    # rationale}; any other explicit status passes through; a named licence
    # with no status becomes {status "licensed", rationale, source_url}; no
    # licence at all is the usual "unverified" fallback.
    for entry in english.get("column_sources") or []:
        if not entry.get("column") or not entry.get("file"):
            continue
        source_id = Path(entry["file"]).name.split(".")[0]
        credit = entry.get("credit") or {}
        licence = credit.get("licence") or {}
        licence_status = licence.get("status")
        name_bits = [b for b in (credit.get("translator"),) if b]
        if credit.get("source"):
            name_bits.append(f"in {credit['source']}")
        name = ", ".join(name_bits) if name_bits else source_id
        # John's ruling (2026-09-22): a Creative Commons translation must
        # show its CC abbreviation, not the generic "Licensed" bucket -- so
        # an explicit `licence.status: cc` gets its own license shape
        # (status "cc" plus the required CC name) instead of being folded
        # into the synthesised "licensed" status below.
        # scripts/emit-lyceum-manifest.mjs's mapLicense() is the consumer.
        if licence_status == "cc":
            if not licence.get("name"):
                raise ValueError(
                    f"{entry['column']}: licence.status is \"cc\" but has no "
                    f"'name' (the CC abbreviation, e.g. \"CC BY-NC-ND 4.0\") "
                    f"-- required to display a cc licence"
                )
            rationale_bits = []
            if credit.get("translator"):
                rationale_bits.append(f"{credit['translator']}, tr.")
            if credit.get("source"):
                rationale_bits.append(credit["source"])
            if credit.get("year"):
                rationale_bits.append(str(credit["year"]))
            license_obj = {
                "status": "cc",
                "name": licence["name"],
                **({"url": licence["url"]} if licence.get("url") else {}),
                **({"rationale": ", ".join(rationale_bits)} if rationale_bits else {}),
            }
        elif licence.get("name"):
            rationale_bits = []
            if credit.get("translator"):
                rationale_bits.append(f"{credit['translator']}, tr.")
            if credit.get("source"):
                rationale_bits.append(credit["source"])
            if credit.get("year"):
                rationale_bits.append(str(credit["year"]))
            rationale = ", ".join(rationale_bits) or licence["name"]
            license_obj = {
                # No explicit `licence.status` (the common case today):
                # synthesise "licensed" exactly as before. Any OTHER
                # explicit status (neither absent nor "cc") passes through
                # unchanged instead of being overwritten.
                "status": licence_status or "licensed",
                "rationale": f"{rationale} ({licence['name']})" if rationale_bits else rationale,
                **({"source_url": licence["url"]} if licence.get("url") else {}),
            }
        else:
            license_obj = {"status": "unverified"}
        translations.append({
            "id": source_id,
            "name": name,
            "slot": "column",
            "default": False,
            "columns": [entry["column"]],
            **({"heading": entry["heading"]} if entry.get("heading") else {}),
            "license": license_obj,
        })

    # Presentation block (P2 stage 5, docs/p2-plan.md §5): the manifest
    # YAML's `registry:` block verbatim -- it is already the presentation
    # contract (greekTitle, abbr, workType, bookLabels, blurb, slug,
    # citation extras, translations display metadata, etc.), so stage7
    # copies it through rather than re-deriving any of it. Omitted entirely
    # for a work whose manifest declares no registry block (most fixture/
    # test manifests). `route` is stripped defensively if present -- route
    # ownership lives only in the cross-corpus route registry (P1 rule; see
    # this function's own `route` field above), never in a per-work
    # registry block, so the key should never exist here in practice.
    registry_block = manifest.data.get("registry")
    presentation = None
    if isinstance(registry_block, dict):
        presentation = copy.deepcopy(registry_block)
        presentation.pop("route", None)

    citation = {
        "scheme": manifest.data["citation"]["scheme"],
        "books": [
            {"n": book["n"], "start": book["start"], "end": book["end"]}
            for book in manifest.books
        ],
    }
    if manifest.data.get("bekker_range"):
        span = manifest.data["bekker_range"]
        citation["bekker_range"] = {
            "first_column": span["first_column"],
            "last_column": span["last_column"],
        }

    return {
        "schema_version": "manifest.v1",
        "id": manifest.work_id,
        "author": manifest.author,
        "title": work["title"],
        "language": language,
        # Slug precedence: the registry block (where the app's 44 shortened
        # slugs actually live), then a top-level work.slug, then the work id.
        "route": (
            f"/{manifest.author}/"
            f"{(manifest.data.get('registry') or {}).get('slug') or work.get('slug') or manifest.work_id}"
        ),
        "citation": citation,
        "editions": [{
            "language": language,
            "edition": work[f"{'greek' if language == 'grc' else 'latin'}_edition"],
            "source": {
                "kind": source_prefix,
                "author": work[f"{source_prefix}_author"],
                "work": work[f"{source_prefix}_work"],
            },
            "license": source_license,
        }],
        "translations": translations,
        **({"presentation": presentation} if presentation is not None else {}),
        "apparatus": {
            name: (out_dir / f"{name}.json").exists()
            for name in (
                "footnotes",
                "sidenotes",
                "paratext",
                "figures",
                "sections",
                "philosophers",
            )
        },
        "corpus_version": os.environ.get("CORPUS_VERSION", "dev"),
    }


_COLSEP = "⎪"  # U+23AA — the TLG column divider inside Aristotle's inline tables


def _normalized_gloss(value: str) -> str:
    normalized = " ".join(value.lower().split())
    while normalized and (
        normalized[-1].isspace()
        or unicodedata.category(normalized[-1]).startswith("P")
    ):
        normalized = normalized[:-1]
    return normalized


def merge_short_def(
    gloss: str, lemma: str, candidate_keys: list[str], short_defs: dict[str, str]
) -> str:
    """Conservatively extend a truncated Morpheus gloss from an LSJ definition."""
    normalized_gloss = _normalized_gloss(gloss)
    if not normalized_gloss:
        return gloss

    candidates = sorted(candidate_keys, key=lambda key: key != lemma)
    for key in candidates:
        derived = short_defs.get(key)
        if not derived:
            continue
        normalized_derived = _normalized_gloss(derived)
        if (
            len(normalized_derived) > len(normalized_gloss)
            and re.match(rf"^{re.escape(normalized_gloss)}\b", normalized_derived)
        ):
            return derived
    return gloss


def resolve_parses(parses: list[dict], short_defs: dict[str, str]) -> list[dict]:
    """Drop spurious readings, then extend the survivors' truncated glosses.

    The order matters: filter_parses recognizes a spurious reading by its gloss
    exactly duplicating a resolved sibling's, and those are Morpheus glosses.
    Extending them first would make the duplicate stop looking like one, so the
    junk reading would survive — and can then become the token's primary
    analysis, which shifts the lemma bucket a lexicon page is built from.
    """
    # A folded all-capitals group is intentionally exhaustive: the
    # unaccented surface cannot justify narrowing the full-source match
    # set, even with the conservative ordinary-reading filter.
    kept = (
        parses
        if any(p.get("foldedAccent") for p in parses)
        else filter_parses(parses)
    )
    for parse in kept:
        parse["gloss"] = merge_short_def(
            parse["gloss"], parse["lemma"], parse["lsj"], short_defs
        )
    return kept


def _greek_cells(text: str, tokens: list[dict]):
    """If a Greek line is a table row (contains the ⎪ column divider), split it
    into cells, partitioning the clickable tokens by their char offset and
    rebasing each cell's token offsets to the cell text. Returns a list of
    {text, tokens} cells, or None for an ordinary (non-table) line."""
    if _COLSEP not in text:
        return None
    cells, start = [], 0
    for end in [m for m, ch in enumerate(text) if ch == _COLSEP] + [len(text)]:
        cell_text = text[start:end]
        lead = len(cell_text) - len(cell_text.lstrip())
        cell_toks = [
            {**t, "o": t["o"] - start - lead}
            for t in tokens if start <= t["o"] < end
        ]
        cells.append({"text": cell_text.strip(), "tokens": cell_toks})
        start = end + 1
    return cells


def _chapter_starts(seg_column, line_ns, eng, chapters_in_col, range_map) -> list[dict]:
    """For each chapter starting in this Bekker column, where to break the
    reader. The Greek heading goes before the chapter's ACTUAL Bekker line
    (ch['line'] — exact for grc-aligned chapters); the reader matches the first
    Greek line >= beforeLine, so an exact line lands exactly. The English column
    heading uses the section marker's char offset. (This replaced an earlier
    proportional offset->line estimate that drifted within a column.)"""
    section_offset = {}
    if eng:
        for m in eng["markers"]:
            if m["kind"] == "section":
                section_offset.setdefault(m["n"], m["offset"])
    first_line = line_ns[0] if line_ns else 1
    starts = []
    for ch in chapters_in_col:
        off = section_offset.get(ch["chapter"], 0)
        before = int(ch["line"]) if str(ch.get("line", "")).lstrip("-").isdigit() else first_line
        starts.append(
            {
                "chapter": ch["chapter"],
                "beforeLine": before,
                "wordIndex": int(ch.get("wordIndex", 0) or 0),
                "engOffset": off,
                "bekker": range_map[(ch["book"], ch["chapter"])],
            }
        )
    starts.sort(key=lambda s: (s["beforeLine"], s["wordIndex"]))
    return starts


def chapter_ranges(spine, chapters) -> dict[tuple, str]:
    """(book, chapter) -> Bekker line span, e.g. '1094a1–17' (same column) or
    '1097a15–1098b8' (crossing pages). End = one Bekker line before the next
    chapter begins; the book's last line for the final chapter of a book."""
    book_cols: dict[int, list[str]] = defaultdict(list)
    col_min: dict[tuple, int] = {}
    col_max: dict[tuple, int] = {}
    for seg in spine["segments"]:
        b, c = seg["book"], seg["column"]
        if c not in book_cols[b]:
            book_cols[b].append(c)
        ns = [l["n"] for l in seg["lines"]]
        col_min[(b, c)], col_max[(b, c)] = min(ns), max(ns)

    def step_back(book, col, line):
        """The Bekker position one line before (col, line) within this book."""
        if line > col_min[(book, col)]:
            return col, line - 1
        cols = book_cols[book]
        i = cols.index(col)
        if i > 0:
            pcol = cols[i - 1]
            return pcol, col_max[(book, pcol)]
        return col, line

    by_book: dict[int, list[dict]] = defaultdict(list)
    for ch in chapters:
        by_book[ch["book"]].append(ch)
    ranges: dict[tuple, str] = {}
    for book, chs in by_book.items():
        for i, ch in enumerate(chs):
            scol, sline = ch["column"], int(ch["line"])
            if i + 1 < len(chs):
                ecol, eline = step_back(book, chs[i + 1]["column"], int(chs[i + 1]["line"]))
            else:
                ecol = book_cols[book][-1]
                eline = col_max[(book, ecol)]
            ranges[(book, ch["chapter"])] = (
                f"{scol}{sline}–{eline}" if scol == ecol
                else f"{scol}{sline}–{ecol}{eline}"
            )
    return ranges


def column_line_ranges(spine) -> dict[str, list[dict]]:
    """Bekker (or other scheme's) column -> owning book(s), with each book's
    LINE SPAN in that column -- the columns.json contract `resolveBekker`
    (shared/lib/data.ts) reads to disambiguate a citation whose column is
    shared/split across two books (a book starting mid-column).

    A dk verse fragment's role='context' lines carry a non-citable NEGATIVE
    synthetic n (stage1_greek._parse_fragments) -- excluded here so a
    context-only block never widens a column's citable line-number range (a
    citation jump / nearest-line snap must never be able to land on one; see
    the verse-line-gate check in preflight.py, which enforces the same
    invariant on the OTHER side of this contract: a role='context' line's n
    must always be negative).

    A genuinely all-context column (citation.unmarked_columns) or a
    prose_columns testimonium sets cite_n=None on every one of its blocks
    (stage1_greek._parse_fragments), so ALL of its lines carry that negative
    synthetic n and the filter above leaves nothing -- but the column is
    still real, citable content (a bare citation to it, e.g. "Critias B31"
    or "Parmenides B22", has no line to resolve but must still resolve to
    its book). Dropping the column from the index entirely made it
    unresolvable even though its text renders (found by the navigation-block
    cross-check, 2026-09-12) -- so when the citable filter leaves nothing,
    fall back to the segment's full, unfiltered line set so the column still
    gets an entry. `resolveBekker` never uses lo/hi to pick a book when a
    column has a single entry (bookless dk is always book=1, one entry), so
    this fallback range is presence-only bookkeeping, not a claim about
    citable lines."""
    col_ranges: dict[str, dict[int, list]] = defaultdict(dict)
    for seg in spine["segments"]:
        ns = [line["n"] for line in seg["lines"] if line["n"] >= 0]
        if not ns:
            ns = [line["n"] for line in seg["lines"]]
        if ns:
            col_ranges[seg["column"]][seg["book"]] = [min(ns), max(ns)]
    return {
        col: [
            {"book": b, "lo": rng[0], "hi": rng[1]}
            for b, rng in sorted(books.items())
        ]
        for col, books in col_ranges.items()
    }


def _verse_line_column_sort_key(column: str) -> tuple:
    """Citation-order sort key for a verse-line column ('1.101', '3.47a',
    '1.1094-1101') — design memo §3.3's emit-time citation-order sort:
    stage1 records document order (transposed blocks included, per the
    manuscript's own transmitted position); this is the ONE place that
    order is abandoned in favor of citation (numeric) order for
    presentation. A range (lacuna) token sorts at its start line — the
    range is always encountered, in citation order, exactly where its
    first line would sit, and no other token shares that start position."""
    book_s, lineref = column.split(".", 1)
    num, suffix = scheme_mod.verse_line_order_key(
        lineref.split("-", 1)[0] if scheme_mod.verse_line_kind(lineref) == "range" else lineref
    )
    return (int(book_s), num, suffix)


def emit_books(spine, tokens_doc, english, range_map, out_dir: Path, ross=None,
               third=None, overlays=None, turn_flows=None, scheme=None,
               is_freeman: bool = False, display_order: list[str] | None = None,
               context_english=None, citation_expansion=None,
               whole_column_verbatim=None, section_paragraph_columns=None,
               fragment_kinds=None) -> list[dict]:
    turn_flows = turn_flows or {}
    tokens_by_id = {s["id"]: s for s in tokens_doc["segments"]}
    english_by_id = {c["id"]: c for c in english["chunks"]}
    ross = ross or {}
    third = third or {}
    overlays = overlays or {}
    context_english = context_english or {}
    citation_expansion = citation_expansion or {}
    whole_column_verbatim = whole_column_verbatim or {}
    section_paragraph_columns = section_paragraph_columns or set()
    fragment_kinds = fragment_kinds or {}
    chapters_by_col: dict[tuple, list[dict]] = defaultdict(list)
    seg_keys = {(seg["book"], seg["column"]) for seg in spine["segments"]}
    for ch in english.get("chapters", []):
        if (ch["book"], ch["column"]) not in seg_keys:
            # No spine segment carries this (book, column), so the reader would
            # never render the ch-{book}-{chapter} heading anchor. stage1 clamps
            # book-start chapters onto the spine's book cut; anything arriving
            # here is a real data bug — say so instead of dropping it silently.
            print(f"  stage7 WARNING: chapter {ch['book']}.{ch['chapter']} at "
                  f"{ch['column']}{ch['line']} matches no spine segment — "
                  f"heading not emitted")
        chapters_by_col[(ch["book"], ch["column"])].append(ch)
    by_book: dict[int, list[dict]] = defaultdict(list)
    for seg in spine["segments"]:
        tok_seg = tokens_by_id[seg["id"]]
        # Pair each spine line with its tokenized counterpart POSITIONALLY,
        # not by an `n`-keyed dict: stage3_tokenize.py emits exactly one
        # `lines` entry per spine line, in the same order, so index-for-index
        # correspondence is guaranteed even when two lines share the same
        # `n` (a "doubled section" merge -- e.g. Lives 8.83/7.160, where two
        # source sections both flatten to a synthetic n=1 line). An n-keyed
        # dict silently collapses that duplicate to whichever line wrote
        # last, so every OTHER same-n line then renders with the wrong
        # line's tokens entirely (CLAUDE.md defect B doubled-merge finding:
        # measured on 8.83/7.160/2.125/8.84/7.166/10.120, ~440 of the 527
        # Lives token-walk failures).
        tok_seg_lines = tok_seg["lines"]
        if len(tok_seg_lines) != len(seg["lines"]):
            raise ValueError(
                f"{seg['id']}: spine has {len(seg['lines'])} Greek line(s) "
                f"but the tokenized segment has {len(tok_seg_lines)} -- "
                f"stage3_tokenize.py must emit exactly one lines[] entry per "
                f"spine line for the positional pairing below to be safe"
            )
        eng = english_by_id.get(seg["id"])
        line_ns = [line["n"] for line in seg["lines"]]
        chapter_starts = _chapter_starts(
            seg["column"], line_ns, eng,
            chapters_by_col.get((seg["book"], seg["column"]), []),
            range_map,
        )
        # DK witness split (dk_witness.py, owner-verified against the whole
        # corpus): a fragment_scheme column's role='context' blocks, joined
        # in order, are its whole apparatus -- feed that to split_witnesses
        # and attach the result ONLY when it actually splits (2+ witnesses).
        # None (fail closed, the overwhelming majority) means "emit this
        # column exactly as today" -- no witnesses key at all, same as any
        # other scheme's segment. Scoped to scheme.fragment_scheme because
        # `role` only exists on a dk column's lines in the first place.
        witnesses = None
        if scheme is not None and scheme.fragment_scheme:
            context_idx = [
                i for i, ln in enumerate(seg["lines"]) if ln.get("role") == "context"
            ]
            if context_idx:
                witnesses = dk_witness.split_witnesses(
                    " ".join(seg["lines"][i]["text"] for i in context_idx)
                )
            if witnesses:
                # Carry the clickable tokens onto each witness. The apparatus
                # is one continuous string and split_witnesses partitions it
                # by OFFSET (never rewriting it), so a witness's tokens are
                # exactly those whose rebased offset falls in its span, with
                # offsets moved relative to the witness's own text. Without
                # this the lexicon popup dies on every word of every split
                # column -- 27,161 clickable Greek words.
                #
                # Tokens come from tok_seg_lines, NOT seg["lines"] (the spine
                # carries no tokens), paired positionally -- the same
                # index-not-`n` pairing the greek[] emit below relies on, and
                # for the same doubled-merge reason documented there.
                flat: list[dict] = []
                base = 0
                for i in context_idx:
                    flat.extend(
                        {**t, "o": t["o"] + base} for t in tok_seg_lines[i]["tokens"]
                    )
                    base += len(seg["lines"][i]["text"]) + 1  # the " " join inserts
                for w in witnesses:
                    w["tokens"] = [
                        {**t, "o": t["o"] - w["start"]}
                        for t in flat
                        if w["start"] <= t["o"] < w["end"]
                    ]
        by_book[seg["book"]].append(
            {
                "id": seg["id"],
                "column": seg["column"],
                **({"chapterStarts": chapter_starts} if chapter_starts else {}),
                # Freeman Ancilla (docs/freeman-wave-design.md §1(b)): the
                # per-column entry-type classification -- it classifies the
                # whole DK column, not just its English rendering, so it is
                # sourced from the manifest's own `citation.fragment_kinds`
                # declaration (John's ruling 2026-07-29) rather than the
                # English chunk: a column named in `english.summary_suppressed`
                # carries no chunk at all, but still has a `kind`.
                # fragment_kinds is kept in exact sync with the resolved
                # clean JSON by stage1_freeman_english's own gate 3, so this
                # is never a second, independently-drifting source. Present
                # ONLY for a freeman-MODEL work's covered column (`is_freeman`,
                # finding 12 of the phase-1 adversarial fix round) -- gated
                # explicitly on the manifest's own model choice, so a future
                # English model can never accidentally leak this field onto
                # a non-Freeman work. Every other segment carries no "kind"/
                # "abridged" key at all, byte-identical for the other 18
                # fragment works and every non-dk work.
                # "omit" is fragment_kinds' resolution DISPOSITION for a
                # column shipping no Freeman English at all (John's ruling
                # 2026-07-23), never a legal Segment.kind -- excluded here,
                # same as the old eng-sourced lookup excluded it implicitly
                # (an omit column never had an `eng` chunk to read from).
                **({"kind": k} if is_freeman
                   and (k := fragment_kinds.get(seg["column"])) and k != "omit"
                   else {}),
                **({"abridged": True} if is_freeman and eng and eng.get("abridged") else {}),
                # Whole-column verbatim override (REVIEW-CHECKLIST item 65,
                # John's ruling 2026-07-28): a column carrying a validated
                # `citation.whole_column_verbatim` attestation (see
                # preflight._whole_column_verbatim_columns) is the author
                # speaking entire, with no quoting narrative for DK's
                # contrastive typography to mark -- so no role='text' line
                # can exist to drive the reader's normal full-weight-text
                # styling. This flag lets the segment classify itself as
                # full text anyway, straight from the manifest's own
                # attestation (preflight is the validation gate; stage7
                # trusts a declared column by name). One flag per chunk
                # covers both its Greek and its English, since both sides
                # of this segment are the same continuous speech. Present
                # only for a column named in the attestation; every other
                # segment carries no "wholeColumnVerbatim" key at all
                # (byte-identical by construction).
                **({"wholeColumnVerbatim": True} if seg["column"] in whole_column_verbatim else {}),
                # Section-paragraph split flag (item 85's Melissus B7/B8
                # addendum) -- see the doc comment above this function's own
                # call site. Present only for a column named in
                # `citation.section_paragraph_columns`; every other segment
                # carries no "sectionParagraphSplit" key at all
                # (byte-identical by construction).
                **({"sectionParagraphSplit": True} if seg["column"] in section_paragraph_columns else {}),
                "greek": [
                    {
                        "n": line["n"],
                        "text": line["text"],
                        **({"joined": True} if line.get("joined") else {}),
                        # Lined-source print-line fields (Discourses only —
                        # docs/lined-source-plan.md §3): "sec" unconditional
                        # whenever the spine line carries it (every line of a
                        # lined chapter always does); "wrap" and "wrapO"
                        # conditional, present iff "joined" is (I3). "wrapO"
                        # (2026-08-29 deviation, §3) is the char offset in
                        # THIS line's `text` where the wrapped word starts —
                        # named explicitly because whole-whitespace-token
                        # absorption can glue more than the wrapped word onto
                        # this line (the em-dash glob), which makes "wrapped
                        # token = last token" false. Every other work's line
                        # carries none of these keys at all (byte-identical by
                        # construction).
                        **({"sec": sec} if (sec := line.get("sec")) is not None else {}),
                        **({"wrap": wrap} if (wrap := line.get("wrap")) is not None else {}),
                        **({"wrapO": wrapO} if (wrapO := line.get("wrapO")) is not None else {}),
                        # Paragraph-opening print-line inset (Discourses only
                        # — John's ruling 2026-08-29, docs/lined-source-
                        # plan.md addendum): the source's own rend=
                        # "indent(N)" level, 1..lined_indent_max. Present only on a line
                        # that carried it; every other work's line carries
                        # no "indent" key at all (byte-identical by
                        # construction).
                        **({"indent": indent} if (indent := line.get("indent")) is not None else {}),
                        "tokens": (tokens := tok_seg_lines[idx]["tokens"]),
                        **({"cells": cells} if (cells := _greek_cells(line["text"], tokens)) else {}),
                        # Standoff TLG-section paragraph offsets (Discourses
                        # only — see stage1_greek._chapter_sections). Present
                        # only for a line whose chapter opted in AND kept at
                        # least 2 boundaries; every other work's line carries
                        # no "sections" key at all (byte-identical by
                        # construction).
                        **({"sections": secs} if (secs := line.get("sections")) else {}),
                        # dk (Diels-Kranz) role tag — 'text' (the
                        # philosopher's own quoted words) or 'context' (the
                        # ancient source's narrative / surviving apparatus
                        # after German stripping). Present only for a dk
                        # work's blocks; every other scheme's line carries
                        # no "role" key at all (byte-identical by
                        # construction — see stage1_greek._parse_fragments).
                        **({"role": role} if (role := line.get("role")) else {}),
                        # verse-line transposition seam note (design memo
                        # §3.3 — Lucretius' DRN, Wave 2 Batch 2): present
                        # only on the citation-order-first line of a
                        # transposed block; every other scheme's/line's
                        # emitted JSON carries no "seamNote" key at all
                        # (byte-identical by construction — see
                        # stage1_latin._transposition_seam_note).
                        **({"seamNote": note} if (note := line.get("seam_note")) else {}),
                    }
                    for idx, line in enumerate(seg["lines"])
                ],
                # DK apparatus witness split (dk_witness.py) -- an ordered
                # [{source?, text}] list for the reader to render as
                # separate rows instead of one undifferentiated context
                # blob. Present only when the column's apparatus actually
                # split into 2+ witnesses; every other column (every other
                # scheme, and the great majority of dk columns too) carries
                # no "witnesses" key at all (byte-identical by construction
                # — the existing "greek" role='context' block is untouched
                # either way, so rendering can always fall back to it).
                **({"witnesses": witnesses} if witnesses else {}),
                "english": (
                    {
                        "text": eng["text"],
                        "notes": eng["notes"],
                        "markers": eng["markers"],
                        "bekker": eng.get("bekker", []),
                        # English speaker turns starting in this chunk (stephanus
                        # dialogues): [{offset, speaker, display}] — the label
                        # lead-in is stripped from `text` and rendered separately,
                        # like the Greek sigla. Present only for dialogue works.
                        **({"turns": eng["turns"]} if eng.get("turns") else {}),
                        # Standoff verse ranges (book-section works quoting verse
                        # inline — see stage1_book_section_english.py). Present
                        # only for a chunk whose column has ranges attached; a
                        # no-verse work's emitted JSON carries no "verse" key at
                        # all (byte-identical by construction).
                        **({"verse": eng["verse"]} if eng.get("verse") else {}),
                        # A chapter's own descriptive heading (Discourses'
                        # Oldfather subtitle) and standoff paragraph-marker
                        # offsets over `text` (Discourses' every-5th-TLG-
                        # section Loeb markers) — see
                        # stage1_book_section_english.py. Absent for every
                        # other work.
                        **({"title": eng["title"]} if eng.get("title") else {}),
                        **({"paras": eng["paras"]} if eng.get("paras") else {}),
                        # Source-citation frame ranges (design note §3's
                        # `.eng-source-frame`) -- see EnglishChunk.frames.
                        # Present only for a freeman-model chunk whose
                        # extractor detected a citation lead-in.
                        **({"frames": eng["frames"]} if is_freeman and eng.get("frames") else {}),
                        # Per-passage Freeman précis label -- stage1 emits
                        # this only for a column declared in
                        # `english.summary_labels`. Absent everywhere else.
                        **({"summary": True} if eng.get("summary") else {}),
                        # Per-passage translation credit -- present only for
                        # a chunk whose English comes from a different
                        # translation than the work's primary one (a
                        # manifest `english.column_sources` column). Every
                        # other chunk carries no "credit" key at all
                        # (byte-identical by construction).
                        **({"credit": eng["credit"]} if eng.get("credit") else {}),
                    }
                    if eng
                    else None
                ),
                # Speaker turn events (stephanus dialogues): [{line, offset,
                # label}] carried straight from the spine so the reader can render
                # the interlocutor at the char offset where each turn begins.
                **({"speakers": seg["speakers"]} if seg.get("speakers") else {}),
                # Second translation (Ross), chapter-anchored: per chapter-block
                # slices the reader pairs to its blocks (cont = continuation of a
                # chapter begun in an earlier column).
                **({"ross": ross[seg["id"]]} if ross.get(seg["id"]) else {}),
                # Optional third translation (same overlay shape as ross).
                **({"third": third[seg["id"]]} if third.get(seg["id"]) else {}),
                # Any further overlays (4th translation onward), keyed by
                # translation id: { <id>: [pieces] }. Same overlay shape as ross.
                **(
                    {"overlays": ov}
                    if (ov := {
                        tid: chunks[seg["id"]]
                        for tid, chunks in overlays.items()
                        if chunks.get(seg["id"])
                    })
                    else {}
                ),
                # Source-passage English (docs/source-passage-english-
                # scoping.md): the quoting source author's own English, by
                # locus pointer, for a DK context run this work declared in
                # sources/<work>/context-english.json. Present only for a
                # segment named in that sidecar; every other segment (and
                # every work with no sidecar at all) carries no
                # "contextEnglish" key, byte-identical to before this
                # mechanism existed.
                **(
                    {"contextEnglish": ce}
                    if (ce := context_english.get(seg["id"]))
                    else {}
                ),
                # DK source-citation expansion (docs/citation-expansion-
                # wiring-design.md): the Hackett-style expanded English
                # citation(s) for this column's DK apparatus head(s). Present
                # only for a segment carrying >=1 resolved-or-verbatim head in
                # a work that declared `citation.expand_citations: true`; every
                # other segment (and every work that did not opt in) carries no
                # "expandedCitation" key, byte-identical to before this
                # mechanism existed.
                **(
                    {"expandedCitation": ec}
                    if (ec := citation_expansion.get(seg["id"]))
                    else {}
                ),
            }
        )
    stats = []
    for book, segments in sorted(by_book.items()):
        # verse-line ONLY (design memo §3.3): re-sort this book's segments
        # from stage1's recorded DOCUMENT order into CITATION (numeric)
        # order for presentation — "a user who lands on 1.101 expects line
        # 101 to sit between 100 and 102". Safe post-hoc: every lookup above
        # (tokens_by_id, english_by_id, chapters_by_col) is keyed by segment
        # id, never by list position, so reordering the list here cannot
        # desync anything already built. Every other scheme's segments are
        # already in citation order from stage1 and are left untouched.
        if scheme is not None and scheme.verse_line_scheme:
            segments = sorted(segments, key=lambda s: _verse_line_column_sort_key(s["column"]))
        # Turn flow (stephanus dialogues): the book's globally-paired turn list
        # (see turns.build_turn_flow). Present only for a book with Greek turn
        # events; the reader then renders the continuous turn flow with section
        # gutter ticks instead of section-row segments.
        flow = turn_flows.get(book)
        (out_dir / f"book-{book:02d}.json").write_text(
            json.dumps(
                {"book": book, "segments": segments,
                 **({"turnFlow": flow} if flow else {}),
                 # Freeman Ancilla (design note §3.7): the manifest's
                 # declared display permutation, when Freeman's own
                 # sequence diverges from the spine's document order --
                 # citations/anchors/ids stay column-keyed regardless (the
                 # reader reorders the RENDERED list only, client-side).
                 # Absent (the overwhelming majority of dk works, and
                 # every non-dk work) -> no key at all, byte-identical.
                 **({"displayOrder": display_order} if display_order else {})},
                ensure_ascii=False),
            encoding="utf-8",
        )
        stats.append(
            {
                "book": book,
                "segments": len(segments),
                "first_column": segments[0]["column"],
                "last_column": segments[-1]["column"],
            }
        )
    return stats


def _dk_page_letter(col: str, scheme) -> tuple[int, str | None]:
    """dk's column_key 3-tuple (series, number, suffix), unpacked into the
    (page, letter) shape emit_sections' entries share across every scheme —
    see that function's doc comment."""
    _series, number, suffix = column_key(col, scheme)
    return number, (suffix or None)


def emit_sections(spine, out_dir: Path, scheme=None) -> dict:
    """Per-book ordered section outline for a section scheme, written to
    sections.json. Replaces chapters.json as the outline-nav source: a section
    work is cited by page+section, not by chapter, so the navigator lists the
    section columns in reading order — Stephanus (2a, 2b, ... 17e, 18a),
    book-section (4.1, 4.2, ... 4.23), or letter (47.1, 47.2, ... 47.21 —
    Seneca's Epistulae Morales, Wave 2 Batch 3). Each entry carries its
    column token, its page/book number and section letter/number, and the
    stable segment anchor id (`book:column`) the reader scrolls to. Segments
    are already in document order, so first-seen order is reading order.

    `page`/`letter` are named for the Stephanus case; for a numeric-section
    scheme (book-section, and letter — which reuses book-section's dotted
    column grammar and `numeric_section` derivation byte-for-byte, see
    scheme.py's `letter_scheme` doc comment) `page` is the book/letter number
    and `letter` is the integer section number — CONSTANT across a whole
    book/letter (never incrementing), which is exactly the shape
    shared/lib/citation.ts's `navChipsNeedFullSectionList` exists to work
    around on the reader-nav side for both schemes (task #35). A flat-numeric
    scheme (`section`) has no section axis at
    all — its column_key second component is None — so the `letter` key is
    OMITTED for its entries rather than emitted as null (SectionRef.letter in
    shared/lib/data.ts types it as a string; no consumer reads it for a flat
    work). A dk (Diels-Kranz) scheme's column_key is the 3-tuple (series,
    number, suffix) — bookless, like `section`, but with a genuine two-part
    ordering axis (unlike `section`'s bare integer): `page` is the DK number
    and `letter` is the lowercase suffix (omitted, same convention, when
    there isn't one — "B30" vs "B84a") — the same page/letter SHAPE every
    other section scheme already emits, so no reader-side type change is
    needed for this scheme either; `_dk_page_letter` below is dk's own
    unpacking of that 3-tuple."""
    by_book: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    for seg in spine["segments"]:
        col, book = seg["column"], str(seg["book"])
        if col in seen[book]:
            continue
        seen[book].add(col)
        if scheme is not None and scheme.fragment_scheme:
            page, letter = _dk_page_letter(col, scheme)
        else:
            page, letter = column_key(col, scheme)
        by_book[book].append(
            {"column": col, "page": page,
             **({"letter": letter} if letter is not None else {}),
             "id": seg["id"]}
        )
    out = dict(by_book)
    (out_dir / "sections.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out


def emit_philosophers(spine: dict, manifest: Manifest, out_dir: Path) -> dict | None:
    """Per-book ordered philosopher group headings, written to
    philosophers.json — a presentation-only overlay on top of the section
    outline (never a citation level; the ⌘K/citation machinery is untouched).

    Sourced from `spine["philosopher_headers"]` (Diogenes Laertius' Greek
    "tSTART-END" stub divs — see stage1_greek._parse_flat_book_section),
    which is the boundary/greek-name authority. Present ONLY for a work whose
    spine actually carries headers; every other book-section work
    (Meditations) has no `philosopher_headers` key at all, so this returns
    None and writes nothing — zero new files for them (see stage7_emit's
    emit whitelist pattern).

    English names are optional, from a manifest-referenced ordered names file
    (`philosophers.names_file`, relative to SOURCES_DIR — a JSON list of
    `{book, start_section, name}`). Names are matched to the Greek-derived
    headers BY start_section EQUALITY within each book (Grok M1/M2 review
    round, 2026-07-16 — positional matching silently shifted every label by
    one wherever the names file carries an entry the header list doesn't,
    e.g. book 1's leading "Prologue" name with no header at 1.1), not by list
    position: a name and a header at the same start_section are a match;
    duplicate start_sections (book 2's Cebes/Menedemus, both at 2.125) match
    in document order among themselves. A per-book count mismatch is still
    logged loudly (unchanged), and both the individual failure modes are
    logged loudly too — a name with no header at its start_section is unused
    (e.g. book 1's Prologue, book 2's Glaucon/Simmias, which have no TEI
    header of their own); a header with no matching name falls back to its
    Greek display name.

    Both sides of the per-book count comparison are asymmetric failure
    modes, so both are logged loudly whenever a names_file is given at all:
    a book with headers but a names-file entry of zero names for it (as
    opposed to no names_file being configured, the ordinary
    no-English-names case, which logs nothing) falls back for every header;
    a book with names but no Greek-derived headers at all is never visited
    by the emission loop below (headers are the boundary authority — no
    header, no output row — so those names are simply unused), and would
    otherwise go silently unwarned."""
    headers = spine.get("philosopher_headers") or []
    names_file = (manifest.data.get("philosophers") or {}).get("names_file")
    if not headers:
        # a configured names file with no Greek headers at all must still
        # warn — otherwise the whole file is silently unused
        if names_file:
            print(f"  philosophers WARNING: names_file {names_file!r} is "
                  f"configured but the spine has no philosopher headers — "
                  f"the entire file is unused, nothing emitted")
        return None

    names_by_book: dict[int, list[dict]] = defaultdict(list)
    if names_file:
        raw = json.loads((SOURCES_DIR / names_file).read_text(encoding="utf-8"))
        for entry in raw:
            names_by_book[int(entry["book"])].append(
                {"start_section": int(entry["start_section"]), "name": entry["name"]}
            )

    headers_by_book: dict[int, list[dict]] = defaultdict(list)
    for h in headers:
        headers_by_book[h["book"]].append(h)

    if names_file:
        for book in sorted(set(headers_by_book) | set(names_by_book)):
            header_count = len(headers_by_book.get(book, []))
            name_count = len(names_by_book.get(book, []))
            if header_count and name_count == 0:
                print(f"  philosophers WARNING: book {book} has {header_count} "
                      f"Greek-derived header(s) but 0 name(s) in the names "
                      f"file — every header falls back to its Greek name")
            elif name_count and header_count == 0:
                print(f"  philosophers WARNING: book {book} has {name_count} "
                      f"name(s) in the names file but no Greek-derived "
                      f"header(s) — headers are authoritative, so these "
                      f"names are never used")
            elif header_count != name_count:
                print(f"  philosophers WARNING: book {book} has {header_count} "
                      f"Greek-derived header(s) but {name_count} name(s) in the "
                      f"names file — matched by start_section; unmatched "
                      f"headers fall back to their Greek name and unmatched "
                      f"names are unused")

    by_book: dict[str, list[dict]] = defaultdict(list)
    for book, book_headers in sorted(headers_by_book.items()):
        # Group this book's names by start_section, preserving document
        # order within each start_section (for the duplicate-start_section
        # case, e.g. book 2's Cebes/Menedemus both at 2.125) — an exact-match
        # FIFO queue per start_section, not a single by-position list.
        names_queue: dict[int, list[str]] = defaultdict(list)
        for entry in names_by_book.get(book, []):
            names_queue[entry["start_section"]].append(entry["name"])
        for h in book_headers:
            queue = names_queue.get(h["start_section"])
            name = queue.pop(0) if queue else None
            by_book[str(book)].append({
                "startSection": h["start_section"],
                "endSection": h["end_section"],
                "greekName": h["greek_name"],
                "name": name or h["greek_name"],
                "id": f"{book}:{book}.{h['start_section']}",
            })
        for start_section, leftover in names_queue.items():
            for name in leftover:
                print(f"  philosophers WARNING: book {book} name {name!r} at "
                      f"start_section {start_section} has no matching "
                      f"Greek-derived header — unused")

    out = dict(by_book)
    (out_dir / "philosophers.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out


def emit_analyses(out_dir: Path) -> dict:
    analyses = _load("stage4/analyses.json")
    key_map = _load("stage4/key_map.json")
    lemma_map = _load("stage5/lemma_map.json")
    # Absent when stage7 is re-run alone over a build predating short defs;
    # the glosses then stay as Morpheus shipped them.
    short_defs_path = BUILD_DIR / "stage5" / "short_defs.json"
    short_defs = _load("stage5/short_defs.json") if short_defs_path.exists() else {}
    merged: dict[str, list[dict]] = {}
    dropped = 0
    for token_key, stored_key in key_map.items():
        parses = []
        for g in analyses[stored_key]:
            parse = {
                "lemma": g["lemma"],
                "gloss": g["gloss"].strip(),
                "parse": g["parse"],
                "lsj": lemma_map.get(g["lemma"], []),
            }
            if g.get("foldedAccent"):
                parse["foldedAccent"] = True
            parses.append(parse)
        kept = resolve_parses(parses, short_defs)
        dropped += len(parses) - len(kept)
        merged[token_key] = kept
    (out_dir / "analyses.json").write_text(
        json.dumps(merged, ensure_ascii=False), encoding="utf-8"
    )
    return {"token_keys": len(merged), "parses_dropped": dropped}


def _merge_shared_lsj(language: str) -> None:
    """Merge this work's dictionary shards into the corpus-wide shared
    dictionary at build/dist/<shard_dir>/<letter>.json (union by key).
    <shard_dir> is 'lsj' for Greek, 'ls' for Latin (stage5_lsj.SHARD_DIR) --
    the two dictionaries are kept in separate directories (different key
    spaces; see stage5_lsj.SHARD_DIR's docstring).

    The reader fetches /data/<shard_dir>/<letter>.json regardless of which
    work is open, so dictionary entries are stored ONCE instead of
    duplicated across per-work subsets. Entry bodies are identical across
    works of the same language (one master dictionary file), so a
    key-keyed dict merge dedups them: the result is the union of every
    work's needed entries. build/dist persists across the works in one
    build run (it is cleared once at the start), so each work accumulates
    into the shared dir; a single-work rebuild just refreshes its own keys.
    """
    shard_dir_name = stage5_lsj.SHARD_DIR[language]
    shared = BUILD_DIR / "dist" / shard_dir_name
    shared.mkdir(parents=True, exist_ok=True)
    for shard in sorted((BUILD_DIR / "stage5" / shard_dir_name).glob("*.json")):
        src = json.loads(shard.read_text(encoding="utf-8"))
        dest = shared / shard.name
        if dest.exists():
            merged = json.loads(dest.read_text(encoding="utf-8"))
            merged.update(src)
        else:
            merged = src
        # sort_keys: see stage5_lsj.run's shard writer — dist shard bytes
        # must depend on content only, not on which work merged a key first.
        dest.write_text(
            json.dumps(merged, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )


def run(manifest: Manifest) -> Path:
    # Per-language spine filename (shared with stage2/stage3 via the same
    # mapping — see stage3_tokenize._SPINE_FILENAMES's doc).
    spine = _load(f"stage1/{_SPINE_FILENAMES[manifest.language]}")
    tokens_doc = _load("stage3/tokens.json")
    # A genuinely Greek-only work (dk's A-testimonia, or a B-fragments work
    # with no English source wired in yet — see manifests/heraclitus-*.yaml)
    # has no english_chunks.json at all: stage1 never writes one when the
    # manifest declares no `english` block. Mirrors stage2_validate.run's
    # identical fallback for the same reason (a has_sections work whose
    # English walker runs as a separate, sometimes-absent pass).
    english_path = BUILD_DIR / "stage1" / "english_chunks.json"
    english = (json.loads(english_path.read_text(encoding="utf-8"))
               if english_path.exists() else {"chunks": []})
    ross_path = BUILD_DIR / "stage1" / "ross_chunks.json"
    ross = json.loads(ross_path.read_text(encoding="utf-8")) if ross_path.exists() else {}
    third_path = BUILD_DIR / "stage1" / "third_chunks.json"
    third = json.loads(third_path.read_text(encoding="utf-8")) if third_path.exists() else {}
    overlays_path = BUILD_DIR / "stage1" / "overlays.json"
    overlays = json.loads(overlays_path.read_text(encoding="utf-8")) if overlays_path.exists() else {}
    # Source-passage English (docs/source-passage-english-scoping.md):
    # present only for a work that declared sources/<work>/context-
    # english.json (stage1_context_english.run) -- every other work has no
    # build/stage1/context_english.json (cleared per-work by __main__.py's
    # `_stage1`, same posture as ross_chunks.json etc.) and emits nothing.
    context_english_path = BUILD_DIR / "stage1" / "context_english.json"
    context_english = (
        json.loads(context_english_path.read_text(encoding="utf-8"))
        if context_english_path.exists() else {}
    )
    # DK source-citation expansion (docs/citation-expansion-wiring-design.md):
    # present only for a work that declared `citation.expand_citations: true`
    # (stage1_citation_expansion.run) -- every other work has no
    # build/stage1/citation_expansion.json (cleared per-work by __main__.py's
    # `_stage1`, same posture as context_english.json) and emits nothing.
    citation_expansion_path = BUILD_DIR / "stage1" / "citation_expansion.json"
    citation_expansion = (
        json.loads(citation_expansion_path.read_text(encoding="utf-8"))
        if citation_expansion_path.exists() else {}
    )
    # Turn pairing (stephanus dialogues): global per-book pairing of the Greek
    # turn sequence against the English one (turns.build_turn_flow — section
    # boundaries never break a pairing), yielding each dialogue book's turnFlow
    # for emit_books plus the per-work reconciliation metric. Narrated books
    # (no Greek events) get no flow and keep section-row rendering.
    turn_report = None
    prose_report = None
    turn_flows: dict[int, dict] = {}
    sch = scheme_mod.for_manifest(manifest)
    if sch.has_sections:
        from . import turns as turns_mod

        sigla = ((manifest.data.get("speakers") or {}).get("sigla")) or {}
        segs_by_book: dict[int, list[dict]] = defaultdict(list)
        for seg in spine["segments"]:
            segs_by_book[seg["book"]].append(seg)
        chunks_by_book: dict[int, list[dict]] = defaultdict(list)
        for c in english["chunks"]:
            chunks_by_book[c["book"]].append(c)
        books_stats: dict[str, dict] = {}
        prose_stats: dict[str, dict] = {}
        tot = {"g_turns": 0, "e_turns": 0, "paired": 0,
               "g_residual": 0, "e_residual": 0,
               "e_dropped_empty": 0, "g_folded": 0,
               "e_folded": 0, "residual_rows": 0}
        unmapped_all: dict[str, int] = {}
        # Work-level speaker → printed-display map (Laws: Athenian→"Ath."), so
        # a head row labeled from the Greek side borrows the display the
        # translation uses for that speaker anywhere in the WORK, not just in
        # its own book.
        displays = turns_mod.speaker_displays(english["chunks"])
        for book in sorted(segs_by_book):
            flow, stats = turns_mod.build_turn_flow(
                segs_by_book[book], chunks_by_book.get(book, []), sigla,
                displays=displays)
            if flow:
                turn_flows[book] = flow
            else:
                # Narrated book (no Greek turn events): reflow the English at
                # its paragraph breaks, anchored to Stephanus columns, and emit
                # it under the same turnFlow key (kind:"para").
                para_flow, pstats = turns_mod.build_para_flow(
                    segs_by_book[book], chunks_by_book.get(book, []), sch)
                if para_flow:
                    turn_flows[book] = para_flow
                prose_stats[str(book)] = pstats
            books_stats[str(book)] = {k: v for k, v in stats.items() if k != "unmapped"}
            for k in tot:
                tot[k] += stats[k]
            for s, n in stats["unmapped"].items():
                unmapped_all[s] = unmapped_all.get(s, 0) + n
        turn_report = {"books": books_stats, **tot}
        if prose_stats:
            prose_report = {"books": prose_stats}
        d = tot["g_turns"]
        rate = f"{tot['paired']}/{d}" + (f" ({tot['paired'] / d * 100:.1f}%)" if d else "")
        print(f"  turn_reconciliation (global): paired/greek_turns={rate} "
              f"e_turns={tot['e_turns']} residual g={tot['g_residual']} "
              f"e={tot['e_residual']}")
        if unmapped_all:
            # Roster gate (P8): any unmapped non-dash siglum aborts the emit
            # before the destination directory is touched.
            segment_sigla = {
                seg["id"]: sorted({
                    turns_mod.base_siglum(ev["label"])
                    for ev in seg.get("speakers", [])
                    if turns_mod.base_siglum(ev["label"]) in unmapped_all
                })
                for seg in spine["segments"]
            }
            segment_sigla = {sid: sg for sid, sg in segment_sigla.items() if sg}
            details = ", ".join(
                f"{sid}=[{', '.join(sg)}]" for sid, sg in segment_sigla.items()
            )
            raise RuntimeError(
                f"{manifest.work_id}: unmapped non-dash speaker sigla in segments: {details}"
            )

    # Do not touch the destination until turn reconciliation has passed: an
    # incomplete speaker roster must leave any previous emitted work intact.
    out_dir = BUILD_DIR / "dist" / manifest.work_id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Translation footnotes and related ancillary files are emitted only after
    # the hard-failure checks above.
    # Freeman Ancilla group-header paratext (docs/freeman-wave-design.md
    # §1/§3.7) -- present only for a work whose english.primary is the
    # freeman model; every other work has no build/stage1/paratext.json
    # (cleared per-work by __main__.py's `_stage1`) and emits nothing.
    paratext_path = BUILD_DIR / "stage1" / "paratext.json"
    if paratext_path.exists():
        shutil.copy(paratext_path, out_dir / "paratext.json")

    footnotes_path = BUILD_DIR / "stage1" / "third_footnotes.json"
    if footnotes_path.exists():
        shutil.copy(footnotes_path, out_dir / "footnotes.json")
    else:
        prim = (manifest.data.get("english") or {}).get("primary") or {}
        if prim.get("dir"):
            src = SOURCES_DIR / prim["dir"] / "footnotes.json"
            if src.exists():
                shutil.copy(src, out_dir / "footnotes.json")
    prim = (manifest.data.get("english") or {}).get("primary") or {}
    if prim.get("dir"):
        for source_name, output_name in (
            ("sidenotes.json", "sidenotes.json"),
            ("figures.json", "figures.json"),
        ):
            src = SOURCES_DIR / prim["dir"] / source_name
            if src.exists():
                shutil.copy(src, out_dir / output_name)

    range_map = chapter_ranges(spine, english.get("chapters", []))
    is_freeman = prim.get("model") == "freeman"
    display_order = manifest.data.get("display_order")
    display_order = display_order if isinstance(display_order, list) else None
    # Whole-column verbatim override (item 65): the manifest's own
    # `citation.whole_column_verbatim` attestation, by column name --
    # preflight (`_whole_column_verbatim_columns`) is the validation gate
    # for this declaration (non-empty justification, a column this work
    # actually emits, no pre-existing role='text' line); stage7 only
    # propagates a declared column into the emitted chunk.
    whole_column_verbatim = (manifest.data.get("citation") or {}).get("whole_column_verbatim")
    whole_column_verbatim = whole_column_verbatim if isinstance(whole_column_verbatim, dict) else {}
    # Section-paragraph split override (item 85's Melissus B7/B8 addendum):
    # the manifest's own `citation.section_paragraph_columns` list, by
    # column name -- preflight (`_validate_section_paragraph_columns`) is
    # the validation gate (a column this work actually emits, both its
    # Greek and English carrying >=2 ascending "(N)" markers); stage7 only
    # propagates a declared column into the emitted chunk. Unlike
    # whole_column_verbatim, this never forces full-text styling on a
    # column's role='context' runs -- these columns keep their ordinary
    # mixed role profile (a real quoting frame around the quotation), so no
    # anti-fabrication attestation is being made here.
    section_paragraph_columns = set(
        c for c in ((manifest.data.get("citation") or {}).get("section_paragraph_columns") or [])
        if isinstance(c, str)
    )
    # Freeman per-column `kind` (John's ruling 2026-07-29): sourced from the
    # manifest's own `citation.fragment_kinds` declaration rather than the
    # English chunk (as before) -- `kind` classifies the whole DK column,
    # not its English rendering, so a column named in
    # `english.summary_suppressed` (no English chunk at all) must still
    # carry its `kind` on the Segment. stage1_freeman_english.py's gate 3
    # already keeps fragment_kinds in exact sync with the resolved clean
    # JSON's own per-column kind, so this is never a second, independently-
    # drifting source of truth.
    fragment_kinds = (manifest.data.get("citation") or {}).get("fragment_kinds")
    fragment_kinds = fragment_kinds if isinstance(fragment_kinds, dict) else {}
    book_stats = emit_books(spine, tokens_doc, english, range_map, out_dir, ross,
                            third, overlays, turn_flows, sch, is_freeman, display_order,
                            context_english, citation_expansion, whole_column_verbatim,
                            section_paragraph_columns, fragment_kinds)
    analyses_stats = emit_analyses(out_dir)

    # Per-book ordered chapter list for navigation (Work → Book → Chapter).
    chapters_by_book: dict[str, list[dict]] = defaultdict(list)
    for ch in english.get("chapters", []):
        chapters_by_book[str(ch["book"])].append(
            {
                "chapter": ch["chapter"],
                "column": ch["column"],
                "line": ch["line"],
                "bekker": range_map[(ch["book"], ch["chapter"])],
            }
        )
    (out_dir / "chapters.json").write_text(
        json.dumps(chapters_by_book, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    # Section schemes (stephanus) are cited by page+section, not by chapter: the
    # chapters.json above is emitted empty for reader compatibility, and the
    # outline navigator reads sections.json instead.
    if scheme_mod.for_manifest(manifest).has_sections:
        emit_sections(spine, out_dir, scheme_mod.for_manifest(manifest))

    # Philosopher group headings (Diogenes Laertius): a no-op — no file
    # written — for every work whose spine carries no philosopher_headers.
    emit_philosophers(spine, manifest, out_dir)

    # Optional per-chapter section titles ({book: {chapter: title}}), emitted
    # when the manifest chapters carry a `title` (e.g. the Isagoge's "Of Genus
    # and Species"). The reader's outline and chapter headings show these in
    # place of a bare "Chapter N"; absent → the file is simply not written.
    titles_by_book: dict[str, dict[str, str]] = defaultdict(dict)
    for ch in english.get("chapters", []):
        if ch.get("title"):
            titles_by_book[str(ch["book"])][str(ch["chapter"])] = ch["title"]
    # Book-section works (Discourses): a chapter's title lives on its own
    # chunk, not a separate chapters[] list — chunks map 1:1 to chapters
    # (see stage1_book_section_english.py's module docstring). Threaded the
    # same way so the SAME chapter-titles.json / Reader heading / TOC
    # machinery the Isagoge's titles use picks these up for free. The key
    # mirrors shared/lib/citation.ts's `dottedSectionChapter` exactly (the
    # TOC's own reader of this same file): a dotted book-section column
    # ("4.1") contributes its chapter component ("1"); a flat `section`
    # scheme's bare column ("48", De Fato's chapter-concordance chunks) has
    # no dot to split on and IS its own chapter unit, used as-is — the
    # pre-flat-scheme version of this loop assumed every titled chunk's
    # column was dotted and crashed (IndexError) on a bare one.
    for chunk in english.get("chunks", []):
        if chunk.get("title"):
            parts = chunk["column"].split(".", 1)
            chapter = parts[1] if len(parts) > 1 else parts[0]
            titles_by_book[str(chunk["book"])][chapter] = chunk["title"]
    if titles_by_book:
        (out_dir / "chapter-titles.json").write_text(
            json.dumps(titles_by_book, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    columns_out = column_line_ranges(spine)
    (out_dir / "columns.json").write_text(
        json.dumps(columns_out, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    _merge_shared_lsj(manifest.language)

    (out_dir / "search").mkdir(exist_ok=True)
    for f in ["lemma.json", "form.json", "english.json", "meta.json", "form_lemmata.json"]:
        shutil.copy(BUILD_DIR / "stage6" / f, out_dir / "search" / f)

    work = manifest.data["work"]
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                **_manifest_v1_fields(manifest, out_dir),
                "work": work,
                "books": book_stats,
                "analyses": analyses_stats,
                "lsj": _load("stage5/summary.json"),
                **({"turn_reconciliation": turn_report} if turn_report else {}),
                **({"prose_flow": prose_report} if prose_report else {}),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    reports = BUILD_DIR / "dist" / "reports"
    reports.mkdir(exist_ok=True)
    for rel in [
        "stage2/validation_report.md",
        "stage2/validation_report.json",
        "stage3/sigla_log.json",
        "stage4/unmatched.json",
        "stage4/summary.json",
        "stage5/missing_lemmata.json",
    ]:
        shutil.copy(BUILD_DIR / rel, reports / Path(rel).name)
    return out_dir
