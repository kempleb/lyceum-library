"""DK (Diels-Kranz) non-Greek-script run classification — Wave 1b design memo
§4.3 "German-commentary stripping (required regardless of the copyright
gate)".

The problem: a DK fragment/testimonium div's `role: 'context'` blocks (and,
rarely, a `role: 'text'` block for an all-Latin fragment like Heraclitus B4)
mix THREE things in the same Latin-alphabet typography, with no `xml:lang`
to tell them apart:

  * bibliographic/citation apparatus (author abbreviations, volume/page
    refs, DK's own bracketed cross-reference notation like "[vgl. B 13]") —
    KEEP, unmodified;
  * genuine ancient Latin text (a Latin-source fragment's own words, e.g.
    B4's Albertus Magnus quotation) — KEEP, unmodified;
  * Diels/Kranz's own German editorial commentary (explanatory glosses,
    cross-references in prose) — STRIP; German apparatus in the reading
    text is noise for this site's readers regardless of how the DK6
    copyright gate (CANON.md §3, pending) resolves.

Decision discipline (heuristic-proposes, declaration-decides, preflight-
gates — the established manual-patch fail-loud pattern this codebase uses
elsewhere): `classify_run` below is a PROPOSAL heuristic only, used to seed
`propose_decisions` / regenerate a work's `dk-context-lang.json` proposal
file for human review. Stage1 (`stage1_greek.apply_context_language`) never
calls the heuristic — it only ever trusts the COMMITTED decision file
(`sources/<work>/dk-context-lang.json`), keyed by a HASH of each run's own
normalized text (not by div — the same citation-apparatus string recurs
verbatim across many divs, and a fingerprint keyed to its content, not its
location, survives a div-numbering-neutral re-export). A run with no
decision-file entry is a hard build error, never a silent pass-through.

Key format (repo hard rule: corpus source text is never committed — TLG is
licensed Greek, PHI is licensed Latin, and Kranz's own German apparatus is
editorial content this repo has no license to redistribute verbatim): a
decision file's JSON keys are `decision_key(normalize_run(run))` — the
first 16 hex characters of the run's own sha256 digest — never the run's
literal text. Each value is `{"decision": ..., "note": "<short,
NON-VERBATIM human label>"}`; `note` exists purely so a reviewer skimming
the committed file can tell entries apart without the (uncommitted) source
text in hand — it must never quote the run itself. `apply_context_language`
below hashes each run it encounters AT RUNTIME (reading from the
never-committed source XML) to perform the lookup, and error messages are
free to print the runtime-derived run text (never committed, so reviewable
without becoming a copyright problem) — see its own doc for exactly where.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

# ── Run extraction ──────────────────────────────────────────────────────────


def is_greek_letter(ch: str) -> bool:
    """True when ch is a Greek LETTER of any accentuation (mirrors the
    identically-named helper in stage1_greek.py / stage3_tokenize.py —
    duplicated rather than imported, same reasoning as those modules'
    matching docstrings: no other coupling between the modules)."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK") and unicodedata.category(ch).startswith("L")


_HAS_LATIN_LETTER = re.compile(r"[A-Za-zÀ-ſ]")


def _iter_non_greek_spans(text: str) -> list[tuple[int, int, str]]:
    """Every maximal non-Greek-script substring of `text` as `(start, end,
    raw)` character spans (`end` exclusive, `raw == text[start:end]`),
    UNTRIMMED — split at Greek-letter boundaries exactly like
    `find_non_greek_runs` (below), which is a thin wrapper over this that
    trims and filters. Kept separate so `apply_context_language`'s strip
    step can recover the exact punctuation trimmed off each run's edges
    (needed to find punctuation a strip orphans — see its own doc) without
    re-deriving span boundaries by a second, possibly-divergent scan."""
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    for i, ch in enumerate(text):
        if is_greek_letter(ch):
            if start is not None:
                spans.append((start, i, text[start:i]))
                start = None
        elif start is None:
            start = i
    if start is not None:
        spans.append((start, len(text), text[start:]))
    return spans


def find_non_greek_runs(text: str) -> list[str]:
    """Every maximal non-Greek-script substring of `text`, split at Greek-
    letter boundaries (whitespace-collapsed source text is assumed — see
    stage1_greek's `_line_text`), trimmed of leading/trailing whitespace and
    a narrow set of pure-connective punctuation, and filtered to runs that
    contain at least one Latin letter (a bare digit/punctuation run like a
    lone "12" or "·" carries no language signal to classify and is not a
    "run" in this module's sense — it passes through unclassified, same as
    ordinary apparatus punctuation elsewhere in this pipeline)."""
    out = []
    for _start, _end, raw in _iter_non_greek_spans(text):
        r = raw.strip(" ,.;:")
        if len(r) < 2 or not _HAS_LATIN_LETTER.search(r):
            continue
        out.append(r)
    return out


def normalize_run(run: str) -> str:
    """A run's canonical text: outer-trimmed, internal whitespace collapsed
    to a single space. Two runs that differ only in incidental line-wrap
    whitespace must resolve to the same decision. This is NOT itself the
    decision-file key (see `decision_key` below) — it is the string that
    gets hashed to produce one."""
    return re.sub(r"\s+", " ", run).strip()


_HASH_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


def decision_key(normalized: str) -> str:
    """The dk-context-lang.json lookup key for a run's own normalized text:
    the first 16 hex characters of its sha256 digest (UTF-8 encoded). A
    hash — not the literal text — is what gets committed, so a decision
    file can declare "this exact run is reviewed and decided X" without
    itself carrying the corpus source text the decision is ABOUT (see the
    module doc's key-format note for the full rationale). 64 bits of digest
    is unshakeable collision margin for the low hundreds of distinct runs
    any one work's decision file holds; `load_decisions` validates every
    committed key against `_HASH_KEY_RE` so a literal-text key (a stale
    pre-migration file, or an authoring slip) is rejected loudly rather
    than silently never matching anything."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


# ── Heuristic proposal (review aid only — never consulted at build time) ────

# German function words/abbreviations a DK editorial aside is built from.
# "vgl."/"s."/"nach"/"S." are also common as bare bibliographic shorthand
# (comparable to English "cf."/"see"/"p.") — classify_run's citation-shape
# check (below) fires FIRST and catches the overwhelmingly common case where
# one of these sits alone in an otherwise apparatus-shaped bracket; they are
# listed here too so a run that is genuine German PROSE built around one of
# them (not bare apparatus) still scores toward strip-german.
_GERMAN_WORDS = {
    "der", "die", "das", "und", "oder", "nach", "aus", "über", "auch",
    "ist", "sind", "nämlich", "näml", "vielmehr", "mit", "für", "vgl",
    "zum", "zur", "vom", "dem", "den", "des", "ein", "eine", "einer",
    "wie", "wird", "werden", "sein", "seine", "ihre", "noch", "schon",
    "nur", "hier", "dort", "diese", "dieser", "dieses", "bei", "man",
}
# Latin function words a genuine ancient-source Latin quotation is built
# from (Albertus Magnus, Censorinus, Columella, Chalcidius, Numenius, the
# Gnomologium — the long Latin fragments this corpus actually carries).
_LATIN_WORDS = {
    "et", "est", "qui", "quae", "quod", "sed", "enim", "autem", "cum",
    "ut", "ad", "de", "in", "ex", "non", "esse", "sunt", "hic", "haec",
    "hoc", "sic", "sive", "vel", "atque", "quia", "quam", "cui", "eius",
    "suis", "tamen", "igitur", "modo", "dixit", "fecit", "ait", "vero",
    "idem", "eadem", "eo", "ab", "per", "quibus", "qua", "si", "ipse",
}
_WORD_RE = re.compile(r"[A-Za-zÀ-ſ]+")

Decision = str  # 'citation' | 'keep-latin' | 'strip-german'
DECISIONS = {"citation", "keep-latin", "strip-german"}


def classify_run(run: str) -> Decision:
    """Heuristic PROPOSAL for one non-Greek run — never authoritative (see
    module doc). Two-step: (1) a citation-apparatus SHAPE check (mostly
    caps/digits/punctuation, at most one lowercase word of length > 2, and
    no more than one German-apparatus-shorthand hit) fires first, since the
    overwhelming majority of DK's non-Greek runs are exactly this —author
    abbreviations, volume/page references, DK's own bracketed
    cross-reference notation; (2) otherwise, a German-vs-Latin function-word
    score decides between strip-german and keep-latin, defaulting to
    'citation' when neither language signal fires (a bare proper name or
    editor surname, say)."""
    orig_words = _WORD_RE.findall(run)
    lowered_words = [w.lower() for w in orig_words]
    # Case checked against the ORIGINAL word, not the lowered copy: an
    # all-caps citation abbreviation ("ARIST.", "AËT.") must not count as a
    # "lowercase prose word" just because it was folded to lowercase for the
    # dictionary lookup below — that folding would erase exactly the
    # citation-abbreviation signal this shape check exists to catch.
    lowercase_words = [w for w in orig_words if len(w) > 2 and w[0].islower()]
    german_hits = sum(1 for w in lowered_words if w in _GERMAN_WORDS)
    latin_hits = sum(1 for w in lowered_words if w in _LATIN_WORDS)
    if len(lowercase_words) <= 1 and german_hits <= 1:
        return "citation"
    if german_hits > latin_hits:
        return "strip-german"
    if latin_hits > 0:
        return "keep-latin"
    return "citation"


def propose_decisions(runs: list[str]) -> dict[str, Decision]:
    """A proposal-file body: every distinct normalized run in `runs`, each
    heuristically classified. For human review before being committed as a
    work's `dk-context-lang.json` decision file."""
    proposal: dict[str, Decision] = {}
    for run in runs:
        key = normalize_run(run)
        if key not in proposal:
            proposal[key] = classify_run(run)
    return proposal


# ── Decision-file loading + application (the only part stage1 calls) ───────


def load_decisions(path: Path) -> dict[str, dict[str, str]]:
    """A work's committed dk-context-lang.json: `{hash: {"decision": ...,
    "note": ...}}` (see `decision_key`'s doc for the hash and the module
    doc for the value shape). Every key must be a well-formed hash and
    every value a `{"decision", "note"}` object with a recognized decision
    and a non-empty note — malformed content (including a stale
    pre-migration file whose keys are literal run text) fails loudly here,
    at load time, rather than surfacing as a confusing "undecided run"
    error downstream."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: dk-context-lang.json root must be an object")
    bad_keys = [k for k in data if not _HASH_KEY_RE.match(k)]
    if bad_keys:
        raise ValueError(
            f"{path}: {len(bad_keys)} key(s) are not a 16-hex-char decision "
            f"hash (see dk_lang.decision_key) -- a stale pre-migration file "
            f"keyed by literal run text?: {bad_keys[:5]}"
        )
    bad = {
        k: v for k, v in data.items()
        if not isinstance(v, dict)
        or v.get("decision") not in DECISIONS
        or not isinstance(v.get("note"), str)
        or not v.get("note", "").strip()
    }
    if bad:
        raise ValueError(
            f"{path}: {len(bad)} entr(y/ies) must be an object "
            f"{{'decision': one of {sorted(DECISIONS)}, 'note': a non-empty "
            f"non-verbatim label}}: {list(bad.items())[:5]}"
        )
    return data


_ORPHANABLE_INTRO_PUNCT = {":", ","}


# Both delimiter pairs a strip-german run can orphan one half of (Grok
# review defect G4 extends the mechanism from square brackets, its original
# scope, to parentheses -- real shape: Xenophanes B41 "κανών (über σιρός)":
# the run extraction splits "(über ... )" into two non-Greek runs because
# the Greek headword "σιρός" sits inside the parens, exactly the "[näml.
# ... ]" shape below but with "("/")" instead of "["/"]"). Tracked
# independently per pair -- a block can be ambiguous in one delimiter type
# and perfectly balanced in the other, and the two never interact.
_BRACKET_PAIRS: tuple[tuple[str, str], ...] = (("[", "]"), ("(", ")"))


def _block_delims_ambiguous(text: str, open_ch: str, close_ch: str) -> bool:
    """True when `text`'s `open_ch`/`close_ch` are NOT a single, fully-
    paired, properly-nested run -- an unmatched opener anywhere, or a
    closer with no opener before it, anywhere in the block. A running depth
    counter (rather than a position-tracking stack) is the correct, well-
    known equivalent check for a SINGLE delimiter-pair type: the block is
    properly nested and balanced iff the counter never goes negative and
    ends at zero -- exactly what a stack-based pairing pass over `text`
    would also conclude, without the bookkeeping overhead of recording
    every pair's positions.

    Computed ONCE per block, per delimiter pair, BEFORE any deletion, by
    `apply_context_language` below: for a genuinely balanced block,
    forward/backward counting from a stripped run's own edge (see that
    function) is a provably correct stand-in for full stack-based pair
    matching over the whole block -- there is exactly one way to pair a
    balanced, single-type delimiter sequence. When the block is NOT
    balanced, that equivalence breaks down and there is no principled way
    to tell which delimiter belongs to which; the prior code searched
    forward/backward from the stripped run's edge regardless and assumed
    whatever it found first was that run's partner, which is false exactly
    when the block's own delimiter structure is already unbalanced going in
    -- Sol's counterexample: "ἀρχή [λέξις [oder vielmehr μέση] τέλος" strips
    "oder vielmehr" (with its riding-along "[") and, absent this guard,
    deletes the trailing "]" even though it is at least as plausibly the
    ANCIENT source's own "[λέξις ... ]" closing bracket as it is the
    stripped run's -- the block has two "["s and only one "]", so it is
    unbalanced and genuinely ambiguous, not a case to guess at."""
    depth = 0
    for ch in text:
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def apply_context_language(
    text: str, decisions: dict[str, dict[str, str]], *, where: str,
    used: set[str] | None = None,
) -> str:
    """Strip every `strip-german` run out of `text` (collapsing the
    whitespace it leaves behind), leaving `citation`/`keep-latin` runs
    untouched. Every non-Greek run in `text` MUST have a decision-file
    entry — an undecided run is a hard build error (`where` names the
    fragment/div for the message), never a silent pass-through.

    A stripped run can leave adjoining punctuation stranded, because the
    run string used for matching is itself TRIMMED (see
    `_iter_non_greek_spans`/`find_non_greek_runs`) while the removal below
    operates by exact character position, not literal substring search —
    two provable shapes, both handled here, deliberately nothing else:

      * a bracket split across embedded Greek — e.g. DK's own
        "[näml. <Greek gloss>]" cross-reference notation: the run
        extraction breaks this into two runs on either side of the Greek,
        and the opening "[" (not in the " ,.;:" trim charset, so it rides
        along inside the run string itself) is removed with the German
        word, stranding the closing "]" with no partner. Detected as a
        single unmatched bracket INSIDE the trimmed run being removed;
        fixed by a bracket-balance scan from the run's edge to find that
        run's own exact partner — never any other bracket, so a bracket
        pair that is NOT split by this specific strip (both members
        survive, as in a self-contained "[vgl. B 12]" citation run) is
        never touched.
      * an introducing colon/comma immediately adjacent to the run with
        only whitespace between — e.g. "oder vielmehr: <Greek>": ":" IS in
        the trim charset, so it is trimmed off the run string before
        matching and survives the literal-run removal untouched, orphaned
        once the run it introduced (or was introduced by) is gone.

    `used`, when passed, accumulates the decision HASH (see `decision_key`)
    of every run this call actually consulted a decision for — the caller
    (stage1_greek's `_parse_fragments`) threads ONE set across a whole
    work's divs and, once every div is processed, compares it against the
    full decision file: a decision-file entry that was NEVER consulted is a
    stale declaration (mirrors this module's own undecided-run check, and
    the unmarked_columns/lettered_fragments two-way-exact precedent
    elsewhere in this pipeline) — a real re-export change or a
    manifest-authoring slip that leaves a dead entry the reviewer can no
    longer see is exercised."""
    run_specs: list[tuple[int, int, str, str]] = []
    for start, end, raw in _iter_non_greek_spans(text):
        trimmed = raw.strip(" ,.;:")
        if len(trimmed) < 2 or not _HAS_LATIN_LETTER.search(trimmed):
            continue
        run_specs.append((start, end, raw, trimmed))

    # hash -> the first-seen normalized text that produced it, kept ONLY for
    # this call's own error message below (never persisted, never written
    # anywhere) -- the committed decision file itself carries no run text at
    # all (see decision_key's doc), so this is the one place left able to
    # name an undecided run in a way a reviewer can actually act on.
    seen_text_by_hash: dict[str, str] = {}
    for *_, trimmed in run_specs:
        normalized = normalize_run(trimmed)
        seen_text_by_hash.setdefault(decision_key(normalized), normalized)

    undecided = sorted(h for h in seen_text_by_hash if h not in decisions)
    if undecided:
        undecided_texts = [seen_text_by_hash[h] for h in undecided]
        raise ValueError(
            f"{where}: {len(undecided)} non-Greek run(s) have no "
            f"dk-context-lang.json decision: {undecided_texts[:5]}"
            + (" ..." if len(undecided) > 5 else "")
        )
    if used is not None:
        used.update(seen_text_by_hash)

    delete = bytearray(len(text))  # 1 = character dropped entirely

    def mark(lo: int, hi: int) -> None:
        for i in range(lo, hi):
            delete[i] = 1

    # Computed ONCE per block, per delimiter pair, over the WHOLE text,
    # BEFORE any deletion below (see `_block_delims_ambiguous`'s doc for the
    # full rationale and Sol's counterexample). Only when a delimiter
    # pair's own structure is unambiguous is forward/backward counting from
    # a stripped run's own edge (below) a correct stand-in for stack-based
    # pair matching over the whole block.
    block_ambiguous = {
        pair: _block_delims_ambiguous(text, *pair) for pair in _BRACKET_PAIRS
    }

    for start, end, raw, trimmed in run_specs:
        if decisions[decision_key(normalize_run(trimmed))]["decision"] != "strip-german":
            continue
        trim_off = raw.index(trimmed)
        trim_start = start + trim_off
        trim_end = trim_start + len(trimmed)
        mark(trim_start, trim_end)

        # Delimiter half whose pair sits inside the deleted run: exactly
        # one unmatched opener or closer left inside `trimmed` (never more
        # — a run with a multi-delimiter imbalance is left alone,
        # conservatively, as too tangled to guess at). Conservatism guard
        # (Sol review blocker, extended to parens by Grok review defect
        # G4): when the block's own delimiter structure is unbalanced or
        # ambiguous BEFORE this strip, there is no principled partner to
        # delete — warn loudly (naming the column) and delete nothing
        # beyond the trimmed run itself, rather than guess. Square brackets
        # and parens are independent delimiter TYPES, checked separately —
        # a run can orphan at most one type at a time in practice, but
        # nothing here assumes that.
        for open_ch, close_ch in _BRACKET_PAIRS:
            net = trimmed.count(open_ch) - trimmed.count(close_ch)
            if net not in (1, -1):
                continue
            if block_ambiguous[(open_ch, close_ch)]:
                print(
                    f"  dk_lang WARNING: {where}: strip-german run {trimmed!r} leaves "
                    f"an unmatched {open_ch!r}/{close_ch!r}, but this block's own "
                    f"{open_ch!r}/{close_ch!r} structure is unbalanced or ambiguous "
                    f"before the strip -- deleting nothing beyond the run itself; "
                    f"review via the decision file if a leftover delimiter is wrong"
                )
            elif net == 1:
                bal = 1
                i = trim_end
                while i < len(text):
                    if text[i] == open_ch:
                        bal += 1
                    elif text[i] == close_ch:
                        bal -= 1
                        if bal == 0:
                            mark(i, i + 1)
                            break
                    i += 1
            else:  # net == -1
                bal = 1
                i = trim_start - 1
                while i >= 0:
                    if text[i] == close_ch:
                        bal += 1
                    elif text[i] == open_ch:
                        bal -= 1
                        if bal == 0:
                            mark(i, i + 1)
                            break
                    i -= 1

        # Introducing colon/comma immediately adjacent to the run (only
        # whitespace between) — trimmed off `trimmed` itself by
        # `.strip(" ,.;:")`, so it survives the position-exact deletion
        # above untouched unless marked here too. Skipped when the run is
        # itself a SELF-CONTAINED bracketed/parenthesized aside (opens and
        # closes with a matching delimiter, e.g. a real committed decision
        # "(wie Diogenes 64 A 20)" strip-german run in this corpus): the
        # comma/colon that happens to follow such a complete aside is the
        # OUTER sentence's own punctuation, not something the run
        # introduced — verified against Heraclitus A15, where naively
        # removing that trailing comma broke the surrounding Greek clause.
        self_delimited = (
            len(trimmed) >= 2
            and trimmed[0] in "(["
            and trimmed[-1] in ")]"
        )
        leading = "" if self_delimited else raw[:trim_off].rstrip(" ")
        if leading and leading[-1] in _ORPHANABLE_INTRO_PUNCT:
            pos = start + len(leading) - 1
            mark(pos, pos + 1)
        trailing = "" if self_delimited else raw[trim_off + len(trimmed):].lstrip(" ")
        if trailing and trailing[0] in _ORPHANABLE_INTRO_PUNCT:
            pos = end - len(trailing)
            mark(pos, pos + 1)

    out = "".join(ch for i, ch in enumerate(text) if not delete[i])
    return re.sub(r"\s+", " ", out).strip()
