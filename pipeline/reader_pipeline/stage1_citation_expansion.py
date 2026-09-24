"""Stage 1d: DK source-citation expansion (docs/citation-expansion-wiring-
design.md phase 1 -- the PILOT slice: heads-only, DIRECT dictionary lookups,
no dash walk-back).

A DK fragment/testimonia work MAY opt in by declaring
`citation.expand_citations: true` in its manifest (pilot work:
heraclitus-fragments). For a declared work this module re-extracts each
column's source-citation head(s) from the spine's context runs, resolves the
explicit heads against sources/dk-citations/citation-dictionary.json, and emits
an `expandedCitation` LIST OF RUNS per segment -- one inner list per distinct
context run, document order, never flattened (fix round finding 2: two
separate runs, e.g. Heraclitus B37's "COLUMELLA VIII 4..." and its later,
unrelated "[vgl. B 13],", must never merge into one false attribution). A
work that does NOT declare the flag is completely unaffected -- `run` returns
None and stage7_emit attaches no `expandedCitation` key to any segment
(byte-identical output).

## Head-boundary rule (ported from shared/lib/prose-flow.ts)

The pipeline is Python; the head|body boundary lives in TypeScript. This module
ports the MINIMAL rule John ruled on (item 24, Critias B31, 2026-07-24) --
faithfully, from these prose-flow.ts sources:
  - isLowercaseGreekChar / hasLowercaseGreek : prose-flow.ts:60-74
  - isAllCapsGreekToken                      : prose-flow.ts:84-95
  - isLatinOrNumeralToken / isPurePunctToken : prose-flow.ts:97-105
  - isHeadMaterialToken                      : prose-flow.ts:111-117
  - isSourceHeadOnlyText                     : prose-flow.ts:126-138
  - headPrefixLenInMixedToken                : prose-flow.ts:147-169
  - peelSourceHeadPrefix                     : prose-flow.ts:202-255
Rule (verbatim from prose-flow.ts:190-200): head material is (a) all-caps Greek
title words, (b) Latin-script tokens, (c) numerals / roman numerals / section
markers and punctuation between them; the head ends at the first token that
contains lowercase Greek (intra-token split when a Latin/numeral piece fuses to
the body without a space); the head must contain at least one Latin letter or
numeral -- bare all-caps Greek is not a head; quote-marks/brackets at the seam
attach to the body.

## Resolution (PILOT: direct lookups only)

A head is split at each explicit author-variant token (the memo's
`multi_source_heads` convention), so one column can carry several sources; each
source is one `expandedCitation` list entry. For each source:
  - a leading author-variant match resolves author+work+locus directly
    (resolution "direct");
  - a leading dash ("--"/em dash), a dash-misparse token, or an unmappable
    apparatus artifact / bracketed non-author passes through verbatim
    (resolution "verbatim") -- honest "as printed", never a fabricated author.
    Dash WALK-BACK (R1-R4) is a LATER slice; every dash head is verbatim here.

## Fatal gate (this module IS the preflight for its sidecar)

A head whose leading token matches a dictionary author variant but whose work
cannot be resolved (no explicit work token matched AND the author has no
DEFAULT work) is FATAL -- the dictionary knows the author, so a silent drop
would hide a real coverage hole rather than fabricate or pass through. A head
whose leading token matches nothing (author, dash, misparse, unmappable,
bracket) is treated as "not a citation head" (e.g. a run whose first line is
editorial prose) and produces no entry -- counted and reported, never emitted.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest

# --- Ported head-boundary primitives (prose-flow.ts, cited above) ----------

_GREEK_LETTER = re.compile(r"[Ͱ-Ͽἀ-῿]")
# Quotes / brackets at the head|body seam attach to the body (prose-flow.ts:52-54).
_BODY_BOUNDARY_PUNCT = set("'\"’”‘“«»()[]{}")


def _is_greek(ch: str) -> bool:
    return bool(_GREEK_LETTER.match(ch))


def _is_lower_greek(ch: str) -> bool:  # prose-flow.ts:64-67
    return _is_greek(ch) and ch != ch.upper()


def _has_lower_greek(s: str) -> bool:  # prose-flow.ts:69-74
    return any(_is_lower_greek(ch) for ch in s)


def _has_latin_or_numeral(s: str) -> bool:  # prose-flow.ts:76-78
    return bool(re.search(r"[A-Za-z0-9]", s))


def _is_all_caps_greek_token(token: str) -> bool:  # prose-flow.ts:84-95
    saw_greek = False
    for ch in token:
        if _is_lower_greek(ch):
            return False
        if _is_greek(ch):
            saw_greek = True
            continue
        if re.match(r"[A-Za-z]", ch):
            return False
    return saw_greek


def _is_latin_or_numeral_token(token: str) -> bool:  # prose-flow.ts:98-101
    if _GREEK_LETTER.search(token):
        return False
    return _has_latin_or_numeral(token)


def _is_pure_punct_token(token: str) -> bool:  # prose-flow.ts:103-105
    return not _GREEK_LETTER.search(token) and not re.search(r"[A-Za-z0-9]", token)


def _is_head_material_token(token: str) -> bool:  # prose-flow.ts:111-117
    if _has_lower_greek(token):
        return False
    if _is_all_caps_greek_token(token):
        return True
    if _is_latin_or_numeral_token(token):
        return True
    if _is_pure_punct_token(token):
        return True
    return False


def _is_source_head_only_text(text: str) -> bool:  # prose-flow.ts:126-138
    t = text.strip()
    if not t:
        return False
    if _has_lower_greek(t):
        return False
    tokens = re.findall(r"\S+", t)
    if not tokens:
        return False
    saw_latin_or_num = False
    for tok in tokens:
        if not _is_head_material_token(tok):
            return False
        if _has_latin_or_numeral(tok):
            saw_latin_or_num = True
    return saw_latin_or_num


def _head_prefix_len_in_mixed_token(token: str) -> int:  # prose-flow.ts:147-169
    first_lower = -1
    for i, ch in enumerate(token):
        if _is_lower_greek(ch):
            first_lower = i
            break
    if first_lower < 0:
        return len(token)
    body_start = first_lower
    while body_start > 0 and token[body_start - 1] in _BODY_BOUNDARY_PUNCT:
        body_start -= 1
    if body_start == 0:
        return 0
    prefix = token[:body_start]
    if not _has_latin_or_numeral(prefix):
        return 0
    if _has_lower_greek(prefix):
        return 0
    return body_start


def _peel_source_head_prefix(text: str) -> str | None:  # prose-flow.ts:202-255
    """Return the source-citation head prefix of a mixed context string, or
    None when there is no peelable head. (This port needs only the head string,
    not the body rest that prose-flow's renderer also returns.)"""
    tokens = [(m.group(0), m.start()) for m in re.finditer(r"\S+", text)]
    if not tokens:
        return None
    saw_latin_or_num = False
    rest_offset = -1
    for tok, start in tokens:
        if not _has_lower_greek(tok):
            if not _is_head_material_token(tok):
                rest_offset = start
                break
            if _has_latin_or_numeral(tok):
                saw_latin_or_num = True
            continue
        head_len = _head_prefix_len_in_mixed_token(tok)
        if head_len > 0:
            prefix = tok[:head_len]
            if _has_latin_or_numeral(prefix):
                saw_latin_or_num = True
            rest_offset = start + head_len
        else:
            rest_offset = start
        break
    if rest_offset < 0:
        return None  # entire run is head-shaped -> caller uses head-only path
    head = text[:rest_offset].strip()
    if not head or not saw_latin_or_num or not _has_latin_or_numeral(head):
        return None
    if not text[rest_offset:].strip():
        return None
    return head


def _extract_head(line_text: str) -> str | None:
    """The source-citation head at the start of a context-run's first line: a
    peelable prefix (mixed head+Greek body), or the whole line when it is
    head-only (all citation, no Greek body -- prose-flow's isSourceHeadOnlyText
    branch, prose-flow.ts:559 / buildProseFlow)."""
    peeled = _peel_source_head_prefix(line_text)
    if peeled is not None:
        return peeled
    if _is_source_head_only_text(line_text):
        return line_text.strip()
    return None


# --- Dictionary lookup -----------------------------------------------------

_DASH_PREFIXES = ("—", "–")  # em dash / en dash (DK dash-continuation)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _casefold_tuple(s: str) -> tuple[str, ...]:
    return tuple(t.casefold() for t in _nfc(s).split())


class _Dictionary:
    """Direct-lookup index over citation-dictionary.json: author-variant and
    per-author work-abbrev token sequences (longest-match), plus the meta
    dash-misparse and unmappable-artifact token sets.

    Work-abbreviation matching is case-folded (Grok gate defect 4: 'c. CELS.'
    must match the dict's 'Cels.' forms) -- the stored work-key tuples and the
    query tokens are both casefolded for comparison; the surrounding pipeline
    always renders from the ORIGINAL-case tokens (verbatim / locus text), so
    casefolding here only affects whether a match fires, never the emitted
    text. Author-variant matching stays case-SENSITIVE: casefolding it turned
    up genuine ambiguity (a locus-internal reference like 'ap. Eus. P. E.'
    would casefold-match Eusebius's 'EUS.' variant and Calcidius's 'Chalcid.'/
    Plato's 'Plat.' would casefold-match mid-sentence in a Latin quotation),
    which the author position never needs -- the census's exact-case variant
    spellings already disambiguate it."""

    def __init__(self, raw: dict):
        self._authors = raw["authors"]
        meta = raw.get("meta", {})
        self._misparse = {_nfc(t) for t in meta.get("dash_misparse_tokens", [])}
        self._unmappable = {_nfc(t) for t in meta.get("unmappable_artifacts", [])}
        # variant token-tuple -> author key (longest first)
        self._variants: list[tuple[tuple[str, ...], str]] = []
        for key, entry in self._authors.items():
            for v in entry["variants"]:
                self._variants.append((tuple(_nfc(v).split()), key))
        self._variants.sort(key=lambda t: -len(t[0]))
        # per-author: work token-tuple -> work key (longest first, no DEFAULT)
        self._works: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        for key, entry in self._authors.items():
            ws = [
                (_casefold_tuple(wk), wk)
                for wk in entry["works"]
                if wk != "DEFAULT"
            ]
            ws.sort(key=lambda t: -len(t[0]))
            self._works[key] = ws

    def match_author(self, tokens: list[str], i: int) -> tuple[int, str] | None:
        """Longest author-variant match in `tokens` starting at index i;
        returns (token_span, author_key) or None."""
        for seq, key in self._variants:
            n = len(seq)
            if tuple(tokens[i:i + n]) == seq:
                return n, key
        return None

    def match_work(self, key: str, tokens: list[str], i: int) -> tuple[int, str] | None:
        for seq, wk in self._works[key]:
            n = len(seq)
            cand = tuple(t.casefold() for t in tokens[i:i + n])
            if cand == seq:
                # A work-abbreviation key ending in the printed "p." (page)
                # marker doesn't consume it: "p." belongs to the printed
                # locus that follows, not the work marker (Grok gate defect
                # 5, e.g. 'in Alc. I p.' / 'de decade p.') -- span the match
                # one token short so "p." remains the first locus token.
                span = n - 1 if seq and seq[-1] == "p." else n
                return span, wk
        return None

    def author_entry(self, key: str) -> dict:
        return self._authors[key]

    def is_misparse(self, token: str) -> bool:
        return _nfc(token) in self._misparse

    def is_unmappable(self, head: str, token: str) -> bool:
        return _nfc(head) in self._unmappable or _nfc(token) in self._unmappable


def _load_dictionary() -> _Dictionary:
    # SOURCES_DIR read at call time so tests can monkeypatch it (same posture
    # as every other stage1 module).
    path = SOURCES_DIR / "dk-citations" / "citation-dictionary.json"
    return _Dictionary(json.loads(path.read_text(encoding="utf-8")))


def _verbatim(text: str, flags: list[str]) -> dict:
    return {"verbatim": text.strip(), "resolution": "verbatim", "flags": flags}


# --- Locus boundary (Grok content-gate defects 6, 7, 8) --------------------
#
# A resolved source's `locus` is the printed apparatus text after author+work
# are peeled off. Two shapes leak non-locus text into it if left unchecked:
#   7. A bare capitalized Greek abbreviation (e.g. "Ἡ.", short for
#      Ἡράκλειτος) has no lowercase Greek of its own, so the ported
#      prose-flow head-boundary rule (which only watches for lowercase
#      Greek) treats it as head material and it slides into the locus.
#   8. An all-Latin apparatus head (a Latin author quoting/glossing
#      Heraclitus in Latin) has no Greek at all to signal the body
#      boundary, so the ENTIRE Latin sentence -- quote-intro and all --
#      reads as "head-only" text and the whole thing lands in the locus.
# _truncate_locus stops the locus at the first Greek-script token or the
# first genuine lowercase Latin prose word, while letting Roman numerals,
# Bekker page/column numbers (355a, 396b), short lowercase apparatus
# abbreviations (p., c., ap.), capitalized editor names, and bracketed /
# parenthesized apparatus groups (which may contain lowercase text, e.g. an
# editor's French annotation) all continue it unconditionally.
_SHORT_LOWER_ABBREV = re.compile(r"^[a-z]{1,3}\.$")  # p. / c. / ap.
_ROMAN_NUMERAL = re.compile(r"^[IVXLCDM]+$")
_BEKKER_NUMERAL = re.compile(r"^\d+[a-z]?[.,;]?$")  # 132 / 396b / 525,
_SINGLE_CAP_ABBREV = re.compile(r"^[A-Z]\.$")  # H. / P. / E. -- ambiguous alone
_LOWER_PROSE_WORD = re.compile(r"^[a-z]{2,}[.,;]?$")  # dixit / si / subministrat.

# The "(D. NNN)" / "(D. NNN, W. NN)" Diels-Doxographi-Graeci page ref (memo
# ruling 4), plus any bracket groups DK prints immediately after it -- real
# heads carry a trailing annotation marker there ("HIPPOLYT. Refut. I 13
# (D. 565, W. 16) (1)", "THEOPHRAST. de sensu 1ff. (D. 499ff.) (1)"), which
# is apparatus too and must not stay embedded in the locus. NOT end-anchored:
# anchoring it stranded the whole ref in the locus whenever anything followed.
# The match still starts only at the exact "(D." shape, so no other
# parenthetical _truncate_locus lets through (editor names, edition years, a
# "(Vgl. ...)" cross-reference) is ever pulled out; the run stops at the first
# thing that is not a bracket group.
_DOXOGRAPHI_APPARATUS = re.compile(
    r"\(D\.[^()]*\)(?:\s*(?:\([^()]*\)|\[[^\[\]]*\]))*"
)


def _is_locus_stop_word(token: str) -> bool:
    """A genuine lowercase running Latin word (item 8's body signal) -- never
    the 1-3 letter apparatus abbreviations ('p.', 'c.', 'ap.')."""
    return bool(_LOWER_PROSE_WORD.match(token)) and not _SHORT_LOWER_ABBREV.match(token)


def _truncate_locus(tokens: list[str]) -> list[str]:
    out: list[str] = []
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.startswith("(") or tok.startswith("["):
            close = ")" if tok.startswith("(") else "]"
            j = i
            while j < n and close not in tokens[j]:
                j += 1
            if j >= n:  # unclosed group -> keep the rest verbatim, stop
                out.extend(tokens[i:])
                break
            out.extend(tokens[i:j + 1])
            i = j + 1
            continue
        if _GREEK_LETTER.search(tok):
            break
        if _SHORT_LOWER_ABBREV.match(tok):
            out.append(tok); i += 1; continue
        core = tok.rstrip(".,;")
        if core and _ROMAN_NUMERAL.match(core):
            out.append(tok); i += 1; continue
        if _BEKKER_NUMERAL.match(tok):
            out.append(tok); i += 1; continue
        if _SINGLE_CAP_ABBREV.match(tok):
            # Ambiguous alone: a title-abbreviation letter ("P. E." =
            # Praeparatio Evangelica) vs. an author-name initial introducing
            # the Latin quotation ("H. dixit quod" = "Heraclitus said
            # that..."). One-token lookahead: it continues the locus unless
            # the very next token is itself prose.
            nxt = tokens[i + 1] if i + 1 < n else None
            if nxt is not None and _is_locus_stop_word(nxt):
                break
            out.append(tok); i += 1; continue
        if len(core) >= 2 and core[:1].isupper() and core.isalpha():
            out.append(tok); i += 1; continue  # capitalized editor name
        break
    return out


def _resolve_source(
    dictionary: _Dictionary,
    key: str,
    author_span: int,
    tokens: list[str],
    start: int,
    end: int,
    work_id: str,
    seg_id: str,
    is_last: bool,
) -> dict:
    """Resolve one source span tokens[start:end] whose author matched `key`
    over `author_span` tokens. Fatal when the author is known but no work
    resolves and the author has no DEFAULT (never fabricate)."""
    entry = dictionary.author_entry(key)
    work_start = start + author_span
    matched = dictionary.match_work(key, tokens, work_start)
    locus_includes_work = False
    if matched is not None:
        wspan, wk = matched
        work = entry["works"][wk]
        locus_includes_work = bool(work.get("locus_includes_work"))
        locus_tokens = tokens[work_start:end] if locus_includes_work else tokens[work_start + wspan:end]
    elif "DEFAULT" in entry["works"]:
        wk = "DEFAULT"
        work = entry["works"][wk]
        locus_tokens = tokens[work_start:end]
    else:
        raise ValueError(
            f"{work_id}: citation head in segment {seg_id!r} resolves to author "
            f"{entry['canonical_author']!r} (dictionary key {key}), but names no "
            f"work this author has -- tokens {tokens[work_start:end]!r} match no "
            f"work abbreviation and {key} has no DEFAULT work (never fabricate a "
            f"title; add the work to the dictionary or flag the head)"
        )
    if not locus_includes_work:
        locus_tokens = _truncate_locus(locus_tokens)
    locus = " ".join(locus_tokens)
    if not is_last and locus.endswith(","):
        # Multi-source split: the comma that separated this source from the
        # next in the printed head belongs to the head, not this source's
        # locus (Grok gate defect 6).
        locus = locus[:-1]
    apparatus = None
    m = _DOXOGRAPHI_APPARATUS.search(locus)
    if m:
        # "(D. NNN)" Doxographi Graeci page ref rides along the locus but is
        # never expanded (memo rulings 4/5, "Apparatus is never expanded") --
        # pull it into its own field so the renderer can print it, and drop
        # it from `locus`, per fix round finding 1.
        apparatus = m.group(0)
        locus = re.sub(r"\s+", " ", locus[:m.start()] + " " + locus[m.end():]).strip()
    result = {
        "verbatim": " ".join(tokens[start:end]),
        "resolution": "direct",
        "authorDisplay": entry["canonical_author"],
        "work": {"title": work["title"], "italic": bool(work["title_italic"])},
        "locus": locus,
        "flags": list(entry.get("flags", [])) + list(work.get("flags", [])),
        "dashInherited": False,
    }
    if apparatus:
        result["apparatus"] = apparatus
    return result


def _resolve_head(
    dictionary: _Dictionary, head: str, work_id: str, seg_id: str
) -> list[dict]:
    """Resolve one extracted head into >=1 expandedCitation entries. Returns []
    when the head is not a citation head (leading token matches nothing)."""
    h = _nfc(head).strip()
    tokens = re.findall(r"\S+", h)
    if not tokens:
        return []

    # Leading dash-continuation -> verbatim (walk-back is a later slice).
    if h.startswith(_DASH_PREFIXES) or tokens[0] in _DASH_PREFIXES:
        return [_verbatim(head, ["dash-continuation"])]

    first = dictionary.match_author(tokens, 0)
    if first is None:
        # Not a resolvable author at the head start: honest verbatim only for
        # heads the census would have flagged (misparse / unmappable / bracket);
        # anything else is "not a citation head" -> no entry.
        if dictionary.is_misparse(tokens[0]):
            return [_verbatim(head, ["dash-misparse"])]
        if dictionary.is_unmappable(h, tokens[0]):
            return [_verbatim(head, ["unmappable"])]
        if tokens[0].startswith("["):
            return [_verbatim(head, ["unmappable"])]
        return []

    # Multi-source: split at each subsequent explicit author-variant token
    # (the memo's multi_source_heads convention). Record author-start indices.
    starts: list[tuple[int, int, str]] = [(0, first[0], first[1])]
    i = first[0]
    while i < len(tokens):
        m = dictionary.match_author(tokens, i)
        if m is not None:
            starts.append((i, m[0], m[1]))
            i += m[0]
        else:
            i += 1

    entries: list[dict] = []
    for idx, (start, span, key) in enumerate(starts):
        is_last = idx + 1 >= len(starts)
        end = len(tokens) if is_last else starts[idx + 1][0]
        entries.append(
            _resolve_source(dictionary, key, span, tokens, start, end, work_id, seg_id, is_last)
        )
    return entries


def _segment_heads(seg: dict) -> list[str]:
    """The source-citation head at the start of each maximal context run in a
    segment, document order. (DK prints the apparatus citation at the head of a
    context run; a run whose first line carries no head yields nothing.)"""
    heads: list[str] = []
    prev_role = None
    for line in seg.get("lines", []):
        role = line.get("role")
        if role == "context" and prev_role != "context":
            head = _extract_head(line.get("text", ""))
            if head:
                heads.append(head)
        prev_role = role
    return heads


def run(manifest: Manifest, spine: dict) -> Path | None:
    if not manifest.data.get("citation", {}).get("expand_citations"):
        return None
    dictionary = _load_dictionary()
    # One list PER SEGMENT, each element being one context run's own entry
    # list (fix round finding 2) -- never flattened. Two distinct runs (e.g.
    # Heraclitus B37's "COLUMELLA VIII 4..." and its later, unrelated
    # "[vgl. B 13],") stay two separate lines; a run's own multi-source split
    # (one head naming several witnesses) still joins as one line, exactly as
    # DK printed it. A run whose head is not itself a resolvable citation
    # (not author / dash / misparse / bracket -- editorial prose head-only
    # text) contributes an EMPTY list in its run slot, never dropped from the
    # sequence: the reader's per-block placement counts runs positionally
    # against the same head-boundary rule the Greek column renders from, so
    # a dropped slot would misalign every later run in the segment.
    resolved: dict[str, list[list[dict]]] = {}
    n_direct = 0
    n_verbatim = 0
    n_skipped = 0
    for seg in spine["segments"]:
        seg_id = seg["id"]
        runs: list[list[dict]] = []
        any_entries = False
        for head in _segment_heads(seg):
            head_entries = _resolve_head(dictionary, head, manifest.work_id, seg_id)
            if not head_entries:
                n_skipped += 1
            else:
                any_entries = True
            runs.append(head_entries)
        if any_entries:
            resolved[seg_id] = runs
            entries = [e for run in runs for e in run]
            n_direct += sum(1 for e in entries if e["resolution"] == "direct")
            n_verbatim += sum(1 for e in entries if e["resolution"] == "verbatim")
    print(
        f"  citation_expansion: columns={len(resolved)} "
        f"direct={n_direct} verbatim={n_verbatim} non-head-runs={n_skipped}"
    )
    out_path = BUILD_DIR / "stage1" / "citation_expansion.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out_path
