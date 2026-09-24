"""Stage 1b (dk `freeman` model): Kathleen Freeman's *Ancilla to the
Pre-Socratic Philosophers* as a DK fragment work's primary English --
docs/freeman-wave-design.md §4. Same flat, bookless column keying as
`model: archive`'s stage1_flat_english (a dk column token IS the source
key, no dotted book prefix), but the clean-JSON VALUE is a richer
`{kind, text}` record (design note §1(b)'s per-column kind taxonomy) --
carried through as an explicit model of its own, not smuggled through
`archive`'s plain-string shape.

Also emits the group-header paratext sidecar (`paratext.json`, §1/§3.7):
Freeman's own subject/category labels with no DK number of their own
("Doubtful titles…", "'On Mathematics'"), positioned immediately before
the DK column they precede.

## Gates (all fatal, all re-derived from files already checked into
`sources/` -- no network, no re-running the wayback extractor at build
time), applied in this order

0. **`kind_overrides` resolution**: the extractor never auto-resolves a
   wholly-italic-parenthetical entry where Freeman's own markup disagrees
   with the live Greek spine (`extract_freeman_wayback.classify_kind`
   returns `conflict` for that case) -- it is resolved HERE, and ONLY
   here, from an explicit `citation.kind_overrides` manifest declaration
   (design note §1(b)'s "no heuristic tie-break" rule). Any column still
   `conflict` after overrides are applied is fatal: the build STOPS,
   nothing is written, and the error names every unresolved column.
   A conflicted column may also resolve to the special disposition
   `kind: "omit"` (John's ruling 2026-07-23: "where she has no greek, we
   leave out... don't ship known mistranslations don't ship things for
   which we have no greek") -- this requires a non-empty `reason` string
   in place of the ordinary `note`, ships NO Freeman English for that
   column (the Greek renders alone), and is not itself a legal
   `Segment.kind`. An override may also declare `text_from: "<column>"`
   to pull its emitted text from an ALREADY-PRESENT column in the same
   clean JSON (DK's own double-numbering of one maxim under two column
   tokens, e.g. Democritus B44/B225) rather than from its own (often a
   bare cross-reference stub) `text` field; the referenced column keeps
   carrying its own English unaffected. `text_from` is itself gated
   (phase-2 adversarial round, findings 1-3): the reference graph must be
   acyclic; a source column's own RESOLVED disposition must be neither
   `omit` nor an unresolved `conflict` (never port English a ruling
   withheld at the source); and the source's resolved kind must equal the
   target's declared kind (no cross-kind porting, no exception mechanism).
1. **`freeman_concordance` remap**: Diels-5/Kranz-6 numbering drift
   (design note §2) -- Freeman's own printed number does not always equal
   the DK column token. Applied BEFORE key-set reconciliation, so the
   reconciliation gate below sees the remapped (DK-token-keyed) set, not
   Freeman's raw numbering.
2. **Key-set reconciliation**: the (remapped) clean JSON's column-token
   key set must equal the Greek spine's column set EXACTLY (a stray/mis-
   keyed key, or a spine column with no Freeman entry and no declared
   `alignment_allow_unmatched` id, is fatal) -- same posture as
   `stage1_common.validate_english_source`, reimplemented here rather than
   reused because that helper assumes a plain-string value.
2b. **Key-SEQUENCE reconciliation**: matching column SETS is not enough --
   a transposed pair would still pass gate 2 while rendering misaligned
   English against the wrong Greek column. The (remapped) clean JSON's
   own key order, restricted to matched columns, must equal the Greek
   spine's own column order, unless the manifest declares `display_order`
   (Freeman's own printed sequence genuinely diverging from the spine),
   in which case it must equal `display_order` instead.
3. **`fragment_kinds` staleness**: the manifest's declared
   `citation.fragment_kinds` (design note §6: "the manifest DECLARES the
   kinds") must equal the (remapped, override-resolved) clean JSON's own
   `kind` per column, in both directions -- a manifest that drifts from a
   re-run of the extractor (hand-edited, or the source file regenerated)
   is fatal, not silently accepted. (The SEPARATE Greek-role consistency
   cross-check -- design note §1's "(ii)" -- is a DIST-level gate, run
   against the actually emitted data post-build:
   `preflight._validate_freeman_kinds`.)
4. **`group_headers` staleness**: `english.primary.group_headers_file` is
   REQUIRED for this model (absent is fatal, even for a work with no
   headers at all -- an explicit empty-list sidecar, not a silently
   defaulted one). The manifest's declared `group_headers` list
   (`{before_column, level, text, sha256_16}`) must equal, in order, the
   sidecar file's own list -- each declared `sha256_16` must equal the
   hash of its own declared `text` (a self-consistency check against
   manifest hand-edits, same hash-gated-paratext posture as
   `stage1_latin.py`'s title-drop gate); each declared `level` must be 1
   or 2; each declared `before_column` must name a real spine column.
5. **`summary_suppressed`/`summary_labels` disposition** (John's ruling
   2026-07-29, live review of Gorgias B4): a Freeman entry that is WHOLLY
   her own parenthetical précis of a source she is reporting (never a
   translation of the DK fragment's own words) is either declared
   `english.summary_suppressed` (this column ALSO carries a `status:
   "translated"` context-english span covering the same material -- the
   précis ships no Freeman English chunk at all, Greek + source passage
   only) or `english.summary_labels` (no such coverage -- the précis ships
   as before, but its chunk carries `summary: true`, see EnglishChunk.summary
   and Reader.svelte's engCreditFor/segTransToggle). Never both for the
   same column. Both halves of each declaration are re-verified at build
   time (the entry really is wholly parenthetical; the coverage condition
   really does/doesn't hold) -- a text edit or a context-english.json change
   that stops satisfying either is fatal, not silently accepted.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .stage1_common import load_english_source, validate_english_source, write_json
from .stage1_english import build_alignment


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_clean(cfg: dict) -> dict[str, dict]:
    return json.loads((SOURCES_DIR / cfg["file"]).read_text(encoding="utf-8"))


def _load_group_headers(manifest: Manifest, cfg: dict) -> list[dict]:
    path = cfg.get("group_headers_file")
    if not path:
        raise ValueError(
            f"{manifest.work_id}: english.primary.group_headers_file is "
            f"required for the freeman English model -- even a work with "
            f"NO Freeman group headers must point at an explicit sidecar "
            f"file containing an empty list ([]), not omit the key and "
            f"silently default to no headers"
        )
    return json.loads((SOURCES_DIR / path).read_text(encoding="utf-8"))


_LEGAL_KINDS = {"title", "verbatim", "embedded", "note"}
# `omit` is a resolution DISPOSITION for a kind_overrides entry -- "ship no
# Freeman English for this column" -- never a Segment.kind (build_english
# below emits no chunk at all for it), so it lives in this separate set
# rather than being folded into _LEGAL_KINDS.
_OMIT = "omit"


def _apply_freeman_concordance(manifest: Manifest, clean: dict) -> dict:
    """Remaps `freeman_concordance`-declared Freeman entry keys onto their
    real DK column tokens (design note §2's Diels-5/Kranz-6 drift case),
    BEFORE key-set reconciliation ever sees the clean JSON -- finding 5 of
    the phase-1 adversarial fix round. A no-op (returns `clean` unchanged)
    when the manifest declares no concordance, the overwhelming majority
    of works."""
    concordance = manifest.data.get("freeman_concordance")
    if not concordance:
        return clean
    if not isinstance(concordance, dict):
        raise ValueError(f"{manifest.work_id}: freeman_concordance must be an object")
    for freeman_key, dk_col in concordance.items():
        if freeman_key not in clean:
            raise ValueError(
                f"{manifest.work_id}: freeman_concordance names Freeman "
                f"entry {freeman_key!r}, which is not present in the "
                f"clean JSON -- stale declaration"
            )
        if dk_col in clean and dk_col != freeman_key:
            raise ValueError(
                f"{manifest.work_id}: freeman_concordance remaps "
                f"{freeman_key!r} onto DK column {dk_col!r}, but the "
                f"clean JSON already carries a separate entry keyed "
                f"{dk_col!r} -- refusing to silently overwrite it"
            )
    # Rebuild key-by-key (rather than pop+reassign) so a renamed key keeps
    # its ORIGINAL position in the sequence -- Freeman prints "16c" right
    # where DK's B15c belongs (finding 3: a dict pop+reassign would instead
    # silently relocate it to the end, since Python dicts append on
    # reinsertion, which the reader's spine-order rendering would then
    # misalign against).
    return {concordance.get(key, key): value for key, value in clean.items()}


_SECTION_MARKER_RE = re.compile(r"\((\d+)\)")


def _greek_section_count(spine: dict, column: str) -> int:
    """The count of distinct DK section markers -- "(1)", "(2)", ... --
    printed inline in the GREEK text of `column`. The ground truth an
    `english.column_sources` file's section records must match exactly
    (finding 3, Sol review): the manifest's own column_sources comment
    attests these numbers are byte-identical between the two languages
    ((1)-(21) for Helen, (1)-(37) for Palamedes), so counting them in the
    Greek spine is a real cross-check against the source file, not an
    assumption layered on top of it."""
    numbers: set[int] = set()
    for seg in spine["segments"]:
        if seg["column"] != column:
            continue
        for line in seg["lines"]:
            numbers.update(int(n) for n in _SECTION_MARKER_RE.findall(line["text"]))
    return len(numbers)


def _load_column_sources(manifest: Manifest, spine: dict, clean: dict) -> dict[str, dict]:
    """`english.column_sources` (John's ruling 2026-07-28): the English for
    a NAMED column comes from a different translation than
    `english.primary`, and carries its own per-passage credit.

    The first consumer is Gorgias B11/B11a -- Freeman's own Ancilla entries
    for the Encomium of Helen and the Defence of Palamedes are her
    SUMMARIES, not translations, so the two complete speeches ship the
    Parnassos Press translations instead (CC BY-NC-ND 4.0, credited per
    passage on the reading page and on /attribution).

    Shape (a list, one entry per column -- never a work-wide switch: a
    different translator, edition and licence is asserted for one passage
    at a time, by name):

        english:
          column_sources:
            - column: B11
              file: "parnassos-gorgias/gatt-helen.clean.json"
              heading: "Encomium of Helen"
              credit:
                translator: "Jurgen R. Gatt"
                source: "<edition, as it should be cited>"
                year: 2022
                licence:
                  name: "CC BY-NC-ND 4.0"
                  url: "https://creativecommons.org/licenses/by-nc-nd/4.0/"

    `heading` is optional: the column's standard English title, printed as
    the Greek div's own title line is (a leading, unmarked line ahead of the
    body -- see the "(N)" join below). Prepended to the joined text with a
    single space before "(1)", exactly the "(NN)"-marker join every other
    section boundary gets, so Reader.svelte's DK inline-marker split (an
    existing mechanism, not new here -- see contextSectionMarkerNumbers)
    naturally peels it off as its own leading paragraph, unmarked, matching
    the Greek div's own title line (also unmarked, for the same reason).

    The file is the same array-of-records shape the other vendored
    translations use, one record per printed section of the speech:
    `[{"section": 1, "text": "..."}, ...]`, contiguous from 1, each text
    non-empty. Sections join into one chunk with their own numbers inline
    as "(N)", exactly as DK prints them in the Greek this column carries --
    so the two columns read section for section with no new alignment
    machinery.

    Fatal, so an override can never ship silently or half-applied: a
    malformed entry; a repeated column; a column absent from the Greek
    spine; a column the primary translation does not cover (there would be
    no chunk to replace); a column whose resolved primary disposition is
    `omit` (the ruling that withheld English there must be lifted in the
    manifest, not routed around); a missing/malformed source file; a
    non-contiguous section sequence; an incomplete credit.
    """
    declared = (manifest.data.get("english") or {}).get("column_sources")
    if declared is None:
        return {}
    if not isinstance(declared, list):
        raise ValueError(
            f"{manifest.work_id}: english.column_sources must be a list of "
            f"per-column entries"
        )
    spine_columns = {seg["column"] for seg in spine["segments"]}
    out: dict[str, dict] = {}
    for i, entry in enumerate(declared):
        if not isinstance(entry, dict):
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] must be an object"
            )
        column = entry.get("column")
        if not isinstance(column, str) or not column.strip():
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] needs a "
                f"'column' naming the DK column it supplies English for"
            )
        if column in out:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources declares column "
                f"{column!r} more than once"
            )
        if column not in spine_columns:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] names "
                f"column {column!r}, which is not in this work's Greek spine"
            )
        if column not in clean:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] names "
                f"column {column!r}, which english.primary's clean JSON does "
                f"not cover -- a column source REPLACES the primary "
                f"translation's own text for that column, so there must be "
                f"one to replace"
            )
        if clean[column]["kind"] == _OMIT:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] names "
                f"column {column!r}, whose resolved kind is \"omit\" -- no "
                f"English chunk is emitted for an omitted column at all, so "
                f"the source would ship nothing; lift the omit ruling in "
                f"citation.kind_overrides first"
            )
        path = entry.get("file")
        if not isinstance(path, str) or not path.strip():
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] needs a "
                f"'file' path (relative to sources/)"
            )
        records = json.loads((SOURCES_DIR / path).read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] file "
                f"{path!r} must hold a non-empty list of "
                f"{{section, text}} records"
            )
        for j, rec in enumerate(records):
            if (not isinstance(rec, dict) or rec.get("section") != j + 1
                    or not isinstance(rec.get("text"), str)
                    or not rec["text"].strip()):
                raise ValueError(
                    f"{manifest.work_id}: english.column_sources[{i}] file "
                    f"{path!r} record {j} is malformed -- every record must "
                    f"be {{section, text}} with a non-empty text, and the "
                    f"section sequence must run contiguously from 1 (got "
                    f"{rec.get('section') if isinstance(rec, dict) else rec!r} "
                    f"at position {j})"
                )
        # Finding 3 (Sol review): a contiguous-from-1 sequence alone never
        # caught a source file missing its LAST section (or carrying an
        # extra one past the Greek's own last marker) -- either would still
        # pass the loop above and ship silently against the wrong text. The
        # section count must match the Greek spine's own printed markers
        # for this column exactly.
        greek_count = _greek_section_count(spine, column)
        if len(records) != greek_count:
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}] file "
                f"{path!r} for column {column!r} has {len(records)} "
                f"section(s), but the Greek spine for column {column!r} "
                f"prints {greek_count} DK section marker(s) -- the source "
                f"file's section count must match the Greek exactly, or "
                f"the English would silently ship against the wrong text"
            )
        heading = entry.get("heading")
        if heading is not None and (not isinstance(heading, str) or not heading.strip()):
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}].heading "
                f"must be a non-empty string when present"
            )
        # Finding 5 (Sol review): heading is joined straight onto "(1) ..."
        # with no marker of its own between them (see the `out[column]`
        # assignment below) -- a heading containing its own "(N)" would be
        # indistinguishable, to the Reader's inline-marker split, from a
        # genuine section marker sitting one word early. Fatal, same as
        # every other malformed-shape check here: the title must never
        # itself look like a DK section marker.
        if heading is not None and _SECTION_MARKER_RE.search(heading):
            raise ValueError(
                f"{manifest.work_id}: english.column_sources[{i}].heading "
                f"{heading!r} must not contain a parenthesized number like "
                f"\"(N)\" -- it would be indistinguishable from a genuine "
                f"DK section marker once joined onto the body text"
            )
        body = " ".join(
            f"({rec['section']}) {rec['text'].strip()}" for rec in records
        )
        out[column] = {
            "text": f"{heading.strip()} {body}" if heading else body,
            "credit": _validate_credit(manifest, i, entry.get("credit")),
        }
    return out


def _validate_credit(manifest: Manifest, i: int, credit) -> dict:
    """A column source's own translation credit (see EnglishChunk.credit in
    shared/lib/data.ts). Every field is required except `licence`, which is
    present only for a text used under a licence rather than a public-domain
    one -- and then both its name and the URL of its deed are required, since
    an attribution term cannot be honoured by a licence name alone."""
    where = f"{manifest.work_id}: english.column_sources[{i}].credit"
    if not isinstance(credit, dict):
        raise ValueError(
            f"{where} is required -- a column source's translator, edition "
            f"and year must be declared, or the passage would ship under "
            f"the work's own translation credit (a misattribution)"
        )
    for field in ("translator", "source"):
        if not isinstance(credit.get(field), str) or not credit[field].strip():
            raise ValueError(f"{where}.{field} must be a non-empty string")
    if not isinstance(credit.get("year"), int) or isinstance(credit["year"], bool):
        raise ValueError(f"{where}.year must be an integer")
    source = credit["source"].strip()
    # Fix round (Sol review, commit b69eae5, finding 2): Reader.svelte's
    # splitCreditSource italicizes only a source's TITLE, splitting on the
    # first ", ed." when present. A first-COMMA fallback used to stand in
    # for sources with no ", ed." at all, but that fallback can truncate a
    # genuine "Title, Subtitle" with no editors named. Enforced here
    # instead of guessed at render: a comma-bearing source must mark its
    # editors with ", ed." (so the reader can find the title boundary), or
    # it must carry no comma at all (so the whole string is unambiguously
    # the title). Anything else is a build-time authoring error, not a
    # render-time guess.
    if ',' in source and ', ed.' not in source:
        raise ValueError(
            f"{where}.source {source!r} has a comma but no ', ed.' -- a "
            f"comma-bearing source must mark its editors with ', ed.' so "
            f"the reader can set only the title in italics"
        )
    out = {
        "translator": credit["translator"].strip(),
        "source": source,
        "year": credit["year"],
    }
    licence = credit.get("licence")
    if licence is not None:
        if not isinstance(licence, dict):
            raise ValueError(f"{where}.licence must be an object")
        for field in ("name", "url"):
            if not isinstance(licence.get(field), str) or not licence[field].strip():
                raise ValueError(
                    f"{where}.licence.{field} must be a non-empty string"
                )
        out["licence"] = {
            "name": licence["name"].strip(), "url": licence["url"].strip()
        }
    unknown = sorted(set(credit) - {"translator", "source", "year", "licence"})
    if unknown:
        raise ValueError(f"{where} has unrecognized field(s) {unknown}")
    return out


def _resolve_kind_overrides(manifest: Manifest, clean: dict) -> dict:
    """Applies `citation.kind_overrides` onto a freshly-loaded clean JSON,
    returning a NEW dict (`clean` is never mutated in place) with each
    conflicted column's kind replaced by its declared override.

    Design note §1(b)'s fail-loud tie-break: the extractor never
    auto-resolves a wholly-italic-parenthetical entry where Freeman's own
    markup disagrees with the live Greek spine's role='text' presence
    (`extract_freeman_wayback.classify_kind` marks it `kind: "conflict"`,
    which is NOT a legal Segment.kind). Resolution happens ONLY here, from
    an explicit, human-authored manifest declaration -- never a heuristic
    (CLAUDE.md rule 9 / the Empedocles verse-heuristic ban). A column
    still `conflict` after overrides are applied stops the build: this is
    the phase-1 pilot's deliberately-currently-failing gate for Protagoras
    B5/B6/B6a, pending John's ruling."""
    overrides = (manifest.data.get("citation") or {}).get("kind_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError(f"{manifest.work_id}: citation.kind_overrides must be an object")
    conflicted = {col for col, rec in clean.items() if rec.get("kind") == "conflict"}
    unknown_targets = sorted(set(overrides) - conflicted)
    if unknown_targets:
        raise ValueError(
            f"{manifest.work_id}: citation.kind_overrides names column(s) "
            f"that are NOT conflicted in the clean JSON: {unknown_targets} "
            f"-- an override may only resolve a genuine extractor "
            f"tie-break (kind: \"conflict\"), never override a column the "
            f"extractor already classified outright"
        )
    resolved = dict(clean)
    text_from_map: dict[str, str] = {}
    for col, decl in overrides.items():
        if not isinstance(decl, dict) or "kind" not in decl:
            raise ValueError(
                f"{manifest.work_id}: citation.kind_overrides[{col!r}] "
                f"must be an object with 'kind' (plus 'note', or 'reason' "
                f"for kind: \"omit\") -- a human justification for the "
                f"ruling"
            )
        kind = decl["kind"]
        if kind == _OMIT:
            if not isinstance(decl.get("reason"), str) or not decl["reason"].strip():
                raise ValueError(
                    f"{manifest.work_id}: citation.kind_overrides[{col!r}] "
                    f"kind \"omit\" needs a non-empty 'reason' string "
                    f"justifying why no Freeman English ships for this "
                    f"column (John's ruling 2026-07-23)"
                )
        else:
            if kind not in _LEGAL_KINDS:
                raise ValueError(
                    f"{manifest.work_id}: citation.kind_overrides[{col!r}]."
                    f"kind {kind!r} is not a recognized kind -- expected "
                    f"one of {sorted(_LEGAL_KINDS | {_OMIT})}"
                )
            if not isinstance(decl.get("note"), str) or not decl["note"].strip():
                raise ValueError(
                    f"{manifest.work_id}: citation.kind_overrides[{col!r}] "
                    f"needs a non-empty 'note' string justifying the ruling"
                )
        resolved[col] = {**resolved[col], "kind": kind}
        if "text_from" in decl:
            src = decl["text_from"]
            if not isinstance(src, str) or src not in clean:
                raise ValueError(
                    f"{manifest.work_id}: citation.kind_overrides[{col!r}]."
                    f"text_from names column {src!r}, which is not present "
                    f"in the clean JSON"
                )
            text_from_map[col] = src
    # Every column's KIND disposition is resolved (the loop above) before
    # any text_from PORTING is validated or applied -- phase-2 adversarial
    # round finding 2: text_from must never read a source's disposition
    # ahead of that source's own override being applied.
    still_conflicted = sorted(c for c in conflicted if resolved[c]["kind"] == "conflict")
    if still_conflicted:
        raise ValueError(
            f"{manifest.work_id}: {len(still_conflicted)} column(s) "
            f"remain unresolved after citation.kind_overrides -- "
            f"Freeman's wholly-italic-parenthetical markup is ambiguous "
            f"between 'note' and 'embedded' for {still_conflicted}; a "
            f"human must rule (design note docs/freeman-wave-design.md "
            f"§1(b)) and declare a citation.kind_overrides entry (with a "
            f"note) for each before this work can build -- BUILD "
            f"STOPPED, no output written"
        )
    _validate_text_from_acyclic(manifest, text_from_map)
    _validate_text_from_sources(manifest, resolved, text_from_map)
    _apply_text_from(resolved, text_from_map)
    return resolved


def _validate_text_from_acyclic(manifest: Manifest, text_from_map: dict[str, str]) -> None:
    """Finding 1 (phase-2 adversarial round): a `text_from` reference graph
    must terminate. Undetected, a two-column cycle (A text_from B, B
    text_from A) would resolve each column from the OTHER's ORIGINAL clean
    text -- silently swapping the two columns' English rather than porting
    one shared value from a single source, and never raising at all. Every
    column carries at most one `text_from` declaration (one outgoing edge),
    so walking each chain and flagging a revisited node is sufficient."""
    for start in text_from_map:
        seen: list[str] = []
        node = start
        while node in text_from_map:
            if node in seen:
                cycle = seen[seen.index(node):] + [node]
                raise ValueError(
                    f"{manifest.work_id}: citation.kind_overrides text_from "
                    f"reference graph contains a cycle: "
                    f"{' -> '.join(cycle)} -- a text_from chain must "
                    f"terminate at a column with no text_from of its own"
                )
            seen.append(node)
            node = text_from_map[node]


def _validate_text_from_sources(
    manifest: Manifest, resolved: dict, text_from_map: dict[str, str]
) -> None:
    """Finding 2: a `text_from` source's own RESOLVED disposition must
    itself ship Freeman English -- a source resolving to `omit` (John's
    ruling withheld the English at THAT column) or, defensively, a still-
    unresolved `conflict`, must never have its text quietly ported onto
    another column; that would ship the very English the ruling withheld.
    Finding 3: the source's resolved kind must equal the target's declared
    kind -- cross-kind porting (e.g. a verbatim target pulling from a note
    or title source) is fatal, with no exception mechanism. (Sanity: an
    ordinary shipped column, e.g. Democritus B225 for B44, is untouched by
    either check and still ports cleanly.)"""
    for col, src in text_from_map.items():
        src_kind = resolved[src]["kind"]
        if src_kind in (_OMIT, "conflict"):
            raise ValueError(
                f"{manifest.work_id}: citation.kind_overrides[{col!r}]."
                f"text_from names column {src!r}, whose own resolved "
                f"disposition is {src_kind!r} -- a text_from source must "
                f"itself carry shipped Freeman English, never a column "
                f"whose ruling withheld it"
            )
        target_kind = resolved[col]["kind"]
        if src_kind != target_kind:
            raise ValueError(
                f"{manifest.work_id}: citation.kind_overrides[{col!r}]."
                f"text_from names column {src!r} (resolved kind "
                f"{src_kind!r}), but {col!r} is declared kind "
                f"{target_kind!r} -- text_from may only port text between "
                f"columns of the SAME kind"
            )


def _apply_text_from(resolved: dict, text_from_map: dict[str, str]) -> None:
    """Applies validated `text_from` porting, mutating `resolved` in place.
    Resolves via a memoized chain walk (rather than reading the source's
    ORIGINAL clean text directly) so a multi-hop chain -- not exercised by
    any live manifest today, but not forbidden either -- ports the
    source's own final text, not a stale pre-porting value."""
    memo: dict[str, str] = {}

    def resolve_text(col: str) -> str:
        if col not in memo:
            src = text_from_map.get(col)
            memo[col] = resolve_text(src) if src is not None else resolved[col]["text"]
        return memo[col]

    for col in text_from_map:
        resolved[col] = {**resolved[col], "text": resolve_text(col)}


def _validate_key_set(manifest: Manifest, spine: dict, clean: dict) -> None:
    columns = {seg["column"] for seg in spine["segments"]}
    source_keys = set(clean)
    extra = sorted(source_keys - columns)
    if extra:
        raise ValueError(
            f"{manifest.work_id}: english.primary (freeman model) carries "
            f"{len(extra)} key(s) matching no spine column: "
            f"{', '.join(extra[:10])}{' …' if len(extra) > 10 else ''} -- "
            f"an English orphan (a Freeman entry with no DK column) must "
            f"be dropped from the clean JSON before it is committed, not "
            f"left for this gate to catch at build time"
        )
    segment_ids = {f"{seg['book']}:{seg['column']}" for seg in spine["segments"]}
    allowed_ids = set(manifest.data.get("alignment_allow_unmatched", []))
    unknown_allow = sorted(allowed_ids - segment_ids)
    if unknown_allow:
        raise ValueError(
            f"{manifest.work_id}: alignment_allow_unmatched names segment "
            f"id(s) not in the Greek spine: {', '.join(unknown_allow)}"
        )
    unmatched_ids = {
        f"{seg['book']}:{seg['column']}" for seg in spine["segments"]
        if seg["column"] not in source_keys
    }
    stale_allow = sorted(allowed_ids - unmatched_ids)
    if stale_allow:
        raise ValueError(
            f"{manifest.work_id}: alignment_allow_unmatched names segment "
            f"id(s) that ARE matched by english.primary -- a stale "
            f"allowance declaration must be removed from the manifest: "
            f"{', '.join(stale_allow[:10])}"
        )
    missing_ids = sorted(unmatched_ids - allowed_ids)
    if missing_ids:
        raise ValueError(
            f"{manifest.work_id}: english.primary (freeman model) is "
            f"missing {len(missing_ids)} column(s) the Greek spine "
            f"carries: {', '.join(missing_ids[:10])}"
            f"{' …' if len(missing_ids) > 10 else ''} -- declare a "
            f"genuine edition gap in alignment_allow_unmatched"
        )


def _validate_key_sequence(manifest: Manifest, spine: dict, clean: dict) -> None:
    """`_validate_key_set` above only reconciles column SETS -- a
    transposed pair of Freeman entries (e.g. the clean JSON's B15c/B16
    swapped) would still pass it, even though the reader renders in Greek
    spine order and would silently show the wrong English text next to
    each Greek column. This compares the concordance-adjusted Freeman key
    SEQUENCE (the clean dict's own insertion order, restricted to columns
    matched in the spine) against the Greek spine's own column sequence,
    and fails loudly on any divergence -- UNLESS the manifest declares
    `display_order` (design note's Freeman-prints-a-different-order
    escape hatch, already validated as an exact spine permutation by
    preflight._validate_freeman_manifest_declarations), in which case the
    Freeman sequence must equal `display_order` instead."""
    matched = {seg["column"] for seg in spine["segments"]} & set(clean)
    spine_seq = [seg["column"] for seg in spine["segments"] if seg["column"] in matched]
    freeman_seq = [col for col in clean if col in matched]
    display_order = manifest.data.get("display_order")
    if display_order is None:
        if freeman_seq != spine_seq:
            raise ValueError(
                f"{manifest.work_id}: english.primary (freeman model) "
                f"column order does not match the Greek spine's order -- "
                f"Freeman sequence {freeman_seq}, spine sequence "
                f"{spine_seq}; the reader renders in spine order, so a "
                f"transposed pair here would silently misalign English "
                f"text against the wrong Greek column. If Freeman's own "
                f"printed sequence genuinely diverges from the spine, "
                f"declare it explicitly via a manifest `display_order`"
            )
        return
    if not isinstance(display_order, list):
        raise ValueError(f"{manifest.work_id}: display_order must be a list")
    expected = [col for col in display_order if col in matched]
    if freeman_seq != expected:
        raise ValueError(
            f"{manifest.work_id}: english.primary (freeman model) column "
            f"order does not match the declared display_order -- Freeman "
            f"sequence {freeman_seq}, expected (from display_order) "
            f"{expected}"
        )


def _validate_fragment_kinds(manifest: Manifest, clean: dict) -> None:
    citation = manifest.data.get("citation") or {}
    declared = citation.get("fragment_kinds")
    if not isinstance(declared, dict):
        raise ValueError(
            f"{manifest.work_id}: citation.fragment_kinds is required for "
            f"the freeman English model -- declare a {{column: kind}} "
            f"object for every column english.primary's clean JSON covers"
        )
    observed = {col: rec["kind"] for col, rec in clean.items()}
    if set(declared) != set(observed):
        missing = sorted(set(observed) - set(declared))
        extra = sorted(set(declared) - set(observed))
        raise ValueError(
            f"{manifest.work_id}: citation.fragment_kinds column set does "
            f"not match english.primary's clean JSON -- "
            f"{f'missing {missing} ' if missing else ''}"
            f"{f'extra (undeclared columns) {extra}' if extra else ''}".strip()
        )
    mismatched = sorted(
        col for col in declared if declared[col] != observed[col]
    )
    if mismatched:
        raise ValueError(
            f"{manifest.work_id}: citation.fragment_kinds is stale for "
            f"column(s) {mismatched} -- declared value does not match the "
            f"clean JSON's own kind; re-verify by hand and update the "
            f"manifest (never silently trust either side)"
        )
    bad = sorted(v for v in declared.values() if v not in _LEGAL_KINDS | {_OMIT})
    if bad:
        raise ValueError(
            f"{manifest.work_id}: citation.fragment_kinds contains "
            f"unrecognized kind value(s) {bad} -- expected one of "
            f"{sorted(_LEGAL_KINDS | {_OMIT})}"
        )


def _wholly_parenthetical(text: str) -> bool:
    """John's ruling 2026-07-29: true iff `text`'s FIRST '(' closes its
    matching ')' only at (or, allowing a single trailing '.', immediately
    before) the very end of the string -- i.e. the entry is ONE parenthetical
    span (Freeman's own précis convention, e.g. Gorgias B4's "(Plato in the
    'Meno', 76A sqq.: ...)."), not a parenthetical PREFIX followed by
    unrelated trailing prose that merely also happens to end in ')'
    (Democritus B14's "(Remains of Astronomical Calendar). 1. (Vitruvius). ..."
    is exactly such a case -- its first paren closes after 8 words, long
    before the entry ends, so this returns False for it). A naive
    `startswith('(') and endswith(')')` check would misclassify both that
    case and Democritus B10a's "(Title): '...' (?)" as wholly parenthetical;
    this depth-tracking walk catches both (verified by hand against the
    corpus-wide census, docs/freeman-wave-design.md)."""
    t = text.strip()
    if not t.startswith("("):
        return False
    body = t[:-1] if t.endswith(".") else t
    if not body.endswith(")"):
        return False
    depth = 0
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i == len(body) - 1
    return False


def _load_context_translated_columns(manifest: Manifest, spine: dict) -> set[str]:
    """Which of this work's columns carry >=1 `status: "translated"` span in
    `sources/<work>/context-english.json` -- the coverage half of John's
    2026-07-29 ruling that both `english.summary_suppressed` and
    `english.summary_labels` below gate on. Reads the RAW declaration file
    directly rather than importing stage1_context_english's resolvers: by
    the time this module runs, __main__._stage1 has already called
    stage1_context_english.run() earlier in the SAME stage1 pass (and any
    span there that fails to resolve is fatal, stopping the build before
    this code ever executes), so re-parsing the same already-validated file
    here for a coverage-presence check duplicates no resolution logic and
    can never itself drift from what was actually resolved."""
    path = SOURCES_DIR / manifest.work_id / "context-english.json"
    if not path.exists():
        return set()
    declared = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict):
        return set()
    seg_to_col = {seg["id"]: seg["column"] for seg in spine["segments"]}
    covered: set[str] = set()
    for seg_id, entry in declared.items():
        spans = (entry or {}).get("context_spans") or []
        if any(isinstance(s, dict) and s.get("status") == "translated" for s in spans):
            col = seg_to_col.get(seg_id)
            if col:
                covered.add(col)
    return covered


def _load_summary_dispositions(manifest: Manifest) -> tuple[list[str], list[str]]:
    english = manifest.data.get("english") or {}
    suppressed = english.get("summary_suppressed") or []
    labels = english.get("summary_labels") or []
    if not isinstance(suppressed, list):
        raise ValueError(f"{manifest.work_id}: english.summary_suppressed must be a list")
    if not isinstance(labels, list):
        raise ValueError(f"{manifest.work_id}: english.summary_labels must be a list")
    return suppressed, labels


def _validate_summary_dispositions(
    manifest: Manifest, resolved: dict, covered_columns: set[str],
    suppressed: list[str], labels: list[str],
) -> None:
    """John's ruling 2026-07-29 (live review of Gorgias B4): a Freeman entry
    that is WHOLLY her own parenthetical précis of a source she is reporting
    (never a translation of the DK fragment's own words) is (a) SUPPRESSED
    outright when this column ALSO carries a translated context-english
    source-passage span covering the same quoted material (the reader
    already gets real English for it, from the source), or (b) LABELED a
    summary when no such coverage exists (the précis is all the English
    there is). Both declarations are manifest-DECLARED, never inferred, and
    both conditions are re-verified here every build -- a text edit or a
    context-english.json change that stops satisfying either is fatal, not
    silently accepted."""
    overlap = sorted(set(suppressed) & set(labels))
    if overlap:
        raise ValueError(
            f"{manifest.work_id}: column(s) {overlap} are declared in BOTH "
            f"english.summary_suppressed and english.summary_labels -- a "
            f"column is either suppressed or labeled a summary, never both"
        )
    for col in suppressed:
        if col not in resolved:
            raise ValueError(
                f"{manifest.work_id}: english.summary_suppressed names "
                f"column {col!r}, which english.primary's clean JSON does "
                f"not cover"
            )
        rec = resolved[col]
        if rec["kind"] == _OMIT:
            raise ValueError(
                f"{manifest.work_id}: english.summary_suppressed names "
                f"column {col!r}, whose resolved kind is \"omit\" -- an "
                f"omitted column already ships no English at all; naming it "
                f"here too is redundant and almost certainly a stale "
                f"declaration"
            )
        if not _wholly_parenthetical(rec["text"]):
            raise ValueError(
                f"{manifest.work_id}: english.summary_suppressed names "
                f"column {col!r}, whose Freeman entry is NOT wholly "
                f"parenthetical -- John's ruling only ever suppresses a "
                f"parenthetical précis, never a genuine translation"
            )
        if col not in covered_columns:
            raise ValueError(
                f"{manifest.work_id}: english.summary_suppressed names "
                f"column {col!r}, which carries no `status: \"translated\"` "
                f"span in context-english.json -- suppressing it would "
                f"leave the column with NO English at all; either add "
                f"source-passage coverage first, or declare it in "
                f"english.summary_labels instead"
            )
    for col in labels:
        if col not in resolved:
            raise ValueError(
                f"{manifest.work_id}: english.summary_labels names column "
                f"{col!r}, which english.primary's clean JSON does not cover"
            )
        rec = resolved[col]
        if rec["kind"] == _OMIT:
            raise ValueError(
                f"{manifest.work_id}: english.summary_labels names column "
                f"{col!r}, whose resolved kind is \"omit\" -- no Freeman "
                f"English ships for this column at all, so there is nothing "
                f"to label a summary"
            )
        if not _wholly_parenthetical(rec["text"]):
            raise ValueError(
                f"{manifest.work_id}: english.summary_labels names column "
                f"{col!r}, whose Freeman entry is NOT wholly parenthetical "
                f"-- John's ruling only ever labels a parenthetical précis, "
                f"never a genuine translation"
            )
        if col in covered_columns:
            raise ValueError(
                f"{manifest.work_id}: english.summary_labels names column "
                f"{col!r}, which carries a `status: \"translated\"` span in "
                f"context-english.json -- John's ruling SUPPRESSES a "
                f"covered précis rather than merely labeling it; declare "
                f"it in english.summary_suppressed instead"
            )


def _validate_group_headers(manifest: Manifest, spine: dict, extracted: list[dict]) -> None:
    declared = manifest.data.get("group_headers")
    if declared is None:
        declared = []
    if not isinstance(declared, list):
        raise ValueError(f"{manifest.work_id}: group_headers must be a list")
    if len(declared) != len(extracted):
        raise ValueError(
            f"{manifest.work_id}: group_headers count mismatch -- "
            f"manifest declares {len(declared)}, the extractor's sidecar "
            f"carries {len(extracted)}"
        )
    known_columns = {seg["column"] for seg in spine["segments"]}
    for i, (d, e) in enumerate(zip(declared, extracted)):
        for key in ("before_column", "level", "text", "sha256_16"):
            if key not in d:
                raise ValueError(
                    f"{manifest.work_id}: group_headers[{i}] missing {key!r}"
                )
        if (d["before_column"], d["level"], d["text"]) != (
            e["before_column"], e["level"], e["text"]
        ):
            raise ValueError(
                f"{manifest.work_id}: group_headers[{i}] does not match "
                f"the extractor sidecar's entry at the same position -- "
                f"declared {d!r}, extracted {e!r}"
            )
        want_hash = _content_hash(d["text"])
        if d["sha256_16"] != want_hash:
            raise ValueError(
                f"{manifest.work_id}: group_headers[{i}].sha256_16 "
                f"{d['sha256_16']!r} does not match the hash of its own "
                f"declared text ({want_hash!r}) -- stale or hand-edited "
                f"declaration"
            )
        if d["level"] not in (1, 2):
            raise ValueError(
                f"{manifest.work_id}: group_headers[{i}].level "
                f"{d['level']!r} is not 1 or 2 (design note §1's two-level "
                f"taxonomy)"
            )
        if d["before_column"] not in known_columns:
            raise ValueError(
                f"{manifest.work_id}: group_headers[{i}].before_column "
                f"{d['before_column']!r} names no column in this work's "
                f"Greek spine"
            )


def build_english(manifest: Manifest, spine: dict, clean: dict,
                  column_sources: dict[str, dict] | None = None,
                  summary_suppressed: set[str] | None = None,
                  summary_labels: set[str] | None = None) -> dict:
    column_sources = column_sources or {}
    summary_suppressed = summary_suppressed or set()
    summary_labels = summary_labels or set()
    chunks = []
    for seg in spine["segments"]:
        rec = clean.get(seg["column"])
        if not rec:
            continue
        if rec["kind"] == _OMIT:
            # John's ruling 2026-07-23: no Greek support for this column
            # (or a known mistranslation) -- ship no Freeman English at
            # all; the Greek renders alone, same as any other column with
            # no aligned English chunk (build_alignment leaves `english:
            # None` for it).
            continue
        if seg["column"] in summary_suppressed:
            # John's ruling 2026-07-29: a wholly parenthetical Freeman
            # précis, ALREADY covered by a translated context-english
            # source-passage span for this same column, ships no Freeman
            # English chunk at all -- the Greek renders alone beside that
            # source passage, the same gap shape any other untranslated
            # column with a context-english span already has.
            continue
        # A declared `english.column_sources` column ships a DIFFERENT
        # translation's text, with its own per-passage credit -- the
        # primary translation's own text for that column is replaced
        # outright, never appended to or kept alongside.
        source = column_sources.get(seg["column"])
        chunk = {
            "id": seg["id"], "book": seg["book"], "column": seg["column"],
            "text": source["text"] if source else rec["text"],
            "notes": [], "markers": [],
            "kind": rec["kind"],
        }
        if source:
            chunk["credit"] = source["credit"]
            # `abridged` and `frames` both describe the PRIMARY translation's
            # own text for this column (a summary flag, and char offsets into
            # it) -- neither survives the replacement.
            chunks.append(chunk)
            continue
        if rec.get("abridged"):
            chunk["abridged"] = True
        # Source-citation frame ranges (design note §3's
        # `.eng-source-frame`) -- [start, end) char offsets into `text`,
        # emitted by the extractor for an `embedded` entry's parenthetic
        # citation lead-in. See EnglishChunk.frames (shared/lib/data.ts).
        if rec.get("frames"):
            chunk["frames"] = rec["frames"]
        if seg["column"] in summary_labels:
            # John's ruling 2026-07-29: a wholly parenthetical Freeman
            # précis with NO context-english coverage ships as-is, but
            # labeled a summary (see EnglishChunk.summary) -- the same
            # "(summary)" convention item 84's freeman-summary overlay
            # carries, applied per passage here.
            chunk["summary"] = True
        chunks.append(chunk)
    return {
        "work": manifest.work_id,
        "source": "freeman-ancilla",
        "translation": manifest.data["english"]["primary"]["name"],
        "chunks": chunks,
    }


def _load_summary_overlay_cfg(manifest: Manifest, spine: dict) -> tuple[str, list[str]] | None:
    """`english.summary_overlay` (item 84, John's ruling 2026-07-28): Freeman's
    own DISPLACED summary text for one or more `english.column_sources`
    columns, offered back as a sparse per-passage alternate translation --
    never the default, and clearly labelled a summary in shared/lib/works.ts.
    Returns `(id, columns)` or `None` when the manifest declares none.
    Fatal on a malformed declaration or a named column absent from the
    Greek spine (same discipline as `_load_column_sources` above)."""
    declared = (manifest.data.get("english") or {}).get("summary_overlay")
    if declared is None:
        return None
    if not isinstance(declared, dict):
        raise ValueError(
            f"{manifest.work_id}: english.summary_overlay must be an object"
        )
    overlay_id = declared.get("id")
    if not isinstance(overlay_id, str) or not overlay_id.strip():
        raise ValueError(
            f"{manifest.work_id}: english.summary_overlay needs a "
            f"non-empty 'id' (the translations[] id it registers)"
        )
    columns = declared.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(
            f"{manifest.work_id}: english.summary_overlay needs a "
            f"non-empty 'columns' list"
        )
    spine_columns = {seg["column"] for seg in spine["segments"]}
    unknown = sorted(set(columns) - spine_columns)
    if unknown:
        raise ValueError(
            f"{manifest.work_id}: english.summary_overlay.columns names "
            f"column(s) not in this work's Greek spine: {unknown}"
        )
    return overlay_id, columns


def build_summary_overlay(spine: dict, clean: dict, columns: list[str]) -> dict[str, list[dict]]:
    """Freeman's own (displaced) summary text for the named columns, in the
    reader's existing per-column overlay shape ({seg_id: [{chapter, text,
    cont, bekker}]}) -- item 84. `clean` is the ALREADY-LOADED primary
    clean JSON (post kind_overrides resolution, whose 'text' field for a
    column_sources column is still Freeman's ORIGINAL text -- kind_overrides
    only ever replaces 'kind', never 'text', so this is the exact text
    column_sources replaces, not a re-derived value). Emits an entry only
    for a column actually named in `columns` -- sparse by construction, not
    merely because a source file happens to be short."""
    out: dict[str, list[dict]] = {}
    for seg in spine["segments"]:
        if seg["column"] not in columns:
            continue
        rec = clean.get(seg["column"]) or {}
        text = (rec.get("text") or "").strip()
        if text:
            out[seg["id"]] = [{
                "chapter": seg["column"], "text": text,
                "cont": False, "bekker": [],
            }]
    return out


def build_secondary_overlay(spine: dict, cfg: dict) -> dict[str, list[dict]]:
    """Archive secondary keyed directly by DK column, emitted in the
    reader's existing `ross` overlay shape. Phase 1b's Xenophanes flip is
    the first DK work to exercise this path."""
    prose = load_english_source(SOURCES_DIR / cfg["file"])
    out: dict[str, list[dict]] = {}
    for seg in spine["segments"]:
        text = prose.get(seg["column"], "").strip()
        if text:
            out[seg["id"]] = [{
                "chapter": seg["column"], "text": text,
                "cont": False, "bekker": [],
            }]
    return out


def run(manifest: Manifest, spine: dict) -> tuple[Path, Path]:
    cfg = manifest.data["english"]["primary"]
    clean = _load_clean(cfg)
    clean = _apply_freeman_concordance(manifest, clean)
    clean = _resolve_kind_overrides(manifest, clean)
    _validate_key_set(manifest, spine, clean)
    _validate_key_sequence(manifest, spine, clean)
    _validate_fragment_kinds(manifest, clean)

    group_headers = _load_group_headers(manifest, cfg)
    _validate_group_headers(manifest, spine, group_headers)
    column_sources = _load_column_sources(manifest, spine, clean)

    summary_suppressed, summary_labels = _load_summary_dispositions(manifest)
    covered_columns = _load_context_translated_columns(manifest, spine)
    _validate_summary_dispositions(
        manifest, clean, covered_columns, summary_suppressed, summary_labels
    )

    english = build_english(
        manifest, spine, clean, column_sources,
        set(summary_suppressed), set(summary_labels),
    )
    out_dir = BUILD_DIR / "stage1"
    out_dir.mkdir(parents=True, exist_ok=True)
    eng_path = out_dir / "english_chunks.json"
    write_json(eng_path, english)
    align_path = out_dir / "alignment.json"
    write_json(align_path, build_alignment(spine, english))
    write_json(out_dir / "paratext.json", [
        {"beforeColumn": h["before_column"], "level": h["level"], "text": h["text"]}
        for h in group_headers
    ])
    secondary = manifest.data["english"].get("secondary")
    if secondary:
        validate_english_source(
            manifest, spine, secondary, "secondary", SOURCES_DIR
        )
        write_json(
            out_dir / "ross_chunks.json",
            build_secondary_overlay(spine, secondary),
        )
    # `english.summary_overlay` (item 84): Freeman's own displaced summary
    # for one or more column_sources columns, as a sparse further overlay
    # (translations[].slot 'overlay', seg.overlays[id]). ALWAYS (re)written,
    # empty {} when a work declares none, so a prior work's overlays.json
    # (build/stage1/ is one shared directory across works, not per-work)
    # can never leak through -- same discipline as stage1_archive.run_overlays.
    overlays: dict[str, dict] = {}
    summary_overlay_cfg = _load_summary_overlay_cfg(manifest, spine)
    if summary_overlay_cfg:
        overlay_id, columns = summary_overlay_cfg
        overlays[overlay_id] = build_summary_overlay(spine, clean, columns)
    write_json(out_dir / "overlays.json", overlays)
    return eng_path, align_path
