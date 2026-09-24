"""One-off: extract W. A. Falconer's 1923 Loeb translation of Cicero's *De
Senectute*, *De Amicitia*, and *De Divinatione* (Loeb Classical Library 154)
from the Perseus Digital Library's `canonical-latinLit` TEI XML into clean
JSON -- same "download once, verify the hash, read locally" playbook as
`extract_miller_perseus.py` (see that script's docstring and
sources/INVENTORY.md's "De Officiis" entry for the precedent this mirrors).

## Sources, pinned

All three files were last touched by the SAME commit as Miller's De
Officiis pin -- `1066a551aa5445ab165e9b490a6bb06ce72828da` (2026-06-23,
"(review_work) phi0474 Cicero batch: ... fixes to author and editor in
headers", a header-metadata fix, not a translation-text edit; verified via
GitHub's commits-by-path API 2026-07-18, each file's most recent commit).

| Work | Perseus file | SHA-256 | Size |
|---|---|---|---|
| De Senectute | `data/phi0474/phi051/phi0474.phi051.perseus-eng1.xml` | `44ba1e6d5059cbbf774ee43b0feeb64d670511db972cd7be11192f12c24af348` | 95,817 bytes |
| De Amicitia | `data/phi0474/phi052/phi0474.phi052.perseus-eng2.xml` | `b0c39a70e78e3d7363cabdc1832e8ca9de878a31ac6e13a18742aeda1d919069` | 121,142 bytes |
| De Divinatione | `data/phi0474/phi053/phi0474.phi053.perseus-eng1.xml` | `c4edfe8598dc7ff504ab91d3f6ad4d40879056155c05f71ad18f4141d1891ce6` | 349,510 bytes |

De Amicitia has no Perseus `eng1` file -- only `eng2` exists for phi0474.phi052,
and its own teiHeader still names Falconer as translator (see below), so
`eng2` is simply that file's index within Perseus's own numbering, not a
second/alternate translation.

## Translator-identity verification (triple witness, Rouse/Smith-trap
discipline -- see the Miller precedent and `docs/wave2-latin-design.md` §5.2#3)

- **Each file's own teiHeader**: `<editor role="translator">William
  Armistead Falconer</editor>` in BOTH the titleStmt and the sourceDesc's
  biblStruct, with `<publisher>Harvard University Press; Cambridge, Mass.,
  London, England</publisher>` and `<date>1923</date>` (De Amicitia's
  sourceDesc additionally names the shared volume title "De Senectute De
  Amicitia De Divinatione, With An English Translation" and links directly
  to `https://archive.org/details/desenectutedeami0000cice`, a second,
  independent archive.org scan of the same volume).
- **archive.org `cicero-in-28-volumes.-vol.-20-loeb-154`** (fetched
  independently, not just followed as a link): its own title page reads "DE
  SENECTUTE, DE AMICITIA, DE DIVINATIONE / WITH AN ENGLISH TRANSLATION BY
  WILLIAM ARMISTEAD FALCONER", imprint "LONDON WILLIAM HEINEMANN LTD /
  CAMBRIDGE, MASSACHUSETTS HARVARD UNIVERSITY PRESS", and its own printing
  history states "First printed 1923 / Reprinted 1927, 1930, 1938, 1946,
  1953, 1959, 1964, 1971" (OCR misreads "1930" as "1980"; the underlying
  scan is a HathiTrust `uc1` capture, description field points to
  `https://hdl.handle.net/2027/uc1.32106005388308") -- unrevised reprints
  across nearly half a century, the same "no known later revision" shape as
  Miller's De Officiis.
- **Incipit cross-check, all three works**, Perseus's own opening words
  against the archive.org scan's OCR text layer, confirmed verbatim
  identical for each: De Senectute ("O Titus, should some aid of mine
  dispel..."), De Amicitia ("QUINTUS MUCIUS SCAEVOLA, the augur, used to
  relate..."), De Divinatione ("There is an ancient belief, handed down to
  us...").
- US-PD rationale: published 1923 (Loeb 154's first printing), translator
  Falconer d. 1927 -- safely pre-1931, US public domain by the 95-year
  term regardless of the archive.org record's copyright-status field
  (which for this item is unset, unlike Miller's De Officiis scan; the
  1923 publication date alone settles it under this project's US-PD rule).

## Structure: three DIFFERENT TEI shapes in the same Perseus corpus

Unlike Miller's De Officiis (one shape, milestone-cursor per book), these
three Falconer files use three genuinely different encodings -- each
work's extractor function matches its own file's shape:

1. **De Senectute** (`_extract_flat_milestone`): a single flat
   `<div type="translation">` (no book subdivision -- De Senectute is one
   book) with INLINE `<milestone unit="section" n="...">` markers, exactly
   Miller's per-book cursor shape but with only one "book" to walk.
2. **De Amicitia** (`_extract_section_divs`): each section is its OWN
   wrapping `<div type="textpart" subtype="section" n="...">` element
   (Hicks-shaped, like Diogenes Laertius) -- there is no `unit="section"`
   milestone in this file at all; only `unit="chapter"` milestones appear
   INSIDE section divs, and (like Miller's chapter milestones) carry no
   text and have no effect on section boundaries.
3. **De Divinatione** (`_extract_book_milestone`, x2 for Books I/II):
   Miller's exact shape -- `<div subtype="book" n="1"|"2">` (correctly
   numbered here, no Book-III-style `@n` bug) containing `<p>` elements
   with inline `unit="section"` milestones, PLUS one single confirmed
   Perseus data-entry typo: `<milestone unit="seciton" n="128"/>` (Book II)
   -- "seciton" for "section", verified by inspection (this is the ONLY
   `n="128"` milestone in Book II, and 128 is the only number Book II's
   `unit="section"` sequence alone is missing) -- treated as a real section
   boundary identically to a correctly-spelled one, but ONLY for that exact
   (book, n) pair: `_extract_book_milestone`'s Book II call passes
   `seciton_alias_n=128` (`_SECITON_ALIAS_N`); the Book I call passes none.
   A `unit="seciton"` milestone anywhere else -- Book I at all, or Book II
   with any `n` other than 128 -- raises `ValueError` unconditionally; it
   is never silently ignored the way a genuinely different, harmless unit
   (e.g. "chapter") is, since it is a known misspelling of a real section
   boundary rather than a different kind of milestone.

## De Senectute's duplicate-milestone bug: the SECOND `n="35"` is really `36`

The pinned XML's `unit="section"` milestones run 1..85 but contain a
DUPLICATE `n="35"` (two separate milestones, both `n="35"`) and are
missing `n="36"` entirely -- not a coincidence. Evidence, cross-checked
against the already-built PHI Latin spine
(`app/dist/data/cato-maior-de-senectute/book-01.json`, sections 34-37 all
present, lengths 104/93/100/48 words respectively -- so Latin section 36
genuinely exists and is substantial, not a Miller-2.90-style single-sentence
merge):
- The English content between the FIRST `n="35"` milestone and the SECOND
  falls at a clean topical unit ("old men...feeble...second luminary of
  the state...same fate?") -- normal single-section length.
- The SECOND `n="35"` milestone fires mid-sentence ("...to adopt a regimen
  of health; [MILESTONE] to practise moderate exercise...") -- a duplicate
  boundary marker mid-clause is exactly the shape of a transposed-digit
  typo (35 for 36), not a real re-opening of section 35.
- The very next milestone after the duplicate is `n="37"` -- confirming no
  OTHER milestone was ever meant to carry "36".
`_DUPLICATE_MILESTONE_FIX = {35: 36}` applies this single, hand-verified,
cited correction: the SECOND occurrence of a duplicate section number is
corrected per this table (looked up by the duplicated number, asserted to
fire exactly once). `_walk`'s `duplicate_fix` parameter is passed this
table ONLY by `_extract_flat_milestone` (De Senectute) -- both
`_extract_section_divs` (De Amicitia) and `_extract_book_milestone` (De
Divinatione, both books) leave it unset, so any duplicate milestone number
anywhere else in the corpus, in OR out of this table, still raises
`ValueError` exactly like Miller's unconditional duplicate check. This is
a narrow, cited exception scoped to the one file it was hand-verified
against, not a loosening of the invariant corpus-wide.

## De Divinatione's declared gap: Book I has no `n="25"` milestone

Book I's `unit="section"` milestones run 1..132 but skip `n="25"` entirely
(131 of 132 present, no duplicate). Cross-checked against the built Latin
spine (`app/dist/data/de-divinatione/book-01.json`, `1:1.24`=141 words,
`1:1.25`=60 words present in Latin) and the English word count spanning
milestones 24-26 (256 words, proportionate to the combined 201 Latin
words) -- Falconer's own English almost certainly DOES contain section
25's content, folded into 24's span with no separate milestone, the same
"content present, editorial merge, no separate marker" shape as Miller's
2:2.90 gap. UNLIKE Miller's case (a single terminal short sentence with an
obvious splice point), section 25's ~60-Latin-word span has no
self-evident single-sentence boundary recoverable from the English alone
-- rather than guess a split point and silently fabricate a section
boundary, this script leaves the gap DECLARED (`1:25` absent from output,
281 of the expected 282 records) exactly as Miller's script left 2:2.90
absent, for the same manifest-stage `alignment_allow_unmatched` treatment
(out of this script's blast radius; flagged in sources/INVENTORY.md and
falconer-div/README.md for that follow-up).

## Cleaning conventions (mirrors extract_miller_perseus.py)

- `<note>` (all three files: untyped only, no `type="marg"` split like
  Miller's De Officiis) -- dropped whole, no descent: editorial apparatus.
- `<bibl>` -- dropped whole EVEN WHEN NOT inside a `<note>` (De Senectute:
  2; De Amicitia: 1; De Divinatione: 5, all wrapped in a sibling `<cit>`
  alongside a `<quote rend="blockquote">` verse quotation) -- verified
  against the archive.org scan that these attributions print as numbered
  FOOTNOTES ("1 From Caecilius's comedy, Plocium."), not running prose,
  despite not being TEI-wrapped in `<note>` in this particular encoding.
  `<cit>` itself is a plain pass-through container (its `<quote>` child is
  handled by the normal quote rule below).
- `<foreign xml:lang="greek">` (Beta-Code-like ASCII, Miller's convention)
  -- De Senectute: all 8 occurrences sit inside dropped `<note>`s (none in
  running body text -- no decode table needed for this file). De
  Divinatione: 29 occurrences, 20 inside dropped notes, 9 in the running
  body text, decoded via a small hand-verified table (all 9 standard
  divination/logic technical terms: μαντική, δαιμόνιον, εἱμαρμένη,
  ψευδόμενον, ὁρίζοντες, λήμματα, πρόσληψις, συμπάθεια x2) -- an
  unrecognized string fails the build loudly, same as Miller.
- `<foreign xml:lang="grc">` (De Amicitia ONLY -- a different Perseus
  encoding convention: already-Unicode Greek, not Beta Code) -- all 7
  occurrences verified to sit inside dropped `<note>`s (none in running
  body text); passed through as-is (already Unicode) as a defensive
  fallback that this corpus never actually exercises, with a corpus-count
  assertion (`_assert_grc_all_in_notes`) that fails loud if a future
  re-fetch ever puts one in the body, so this silent-pass-through path
  cannot rot unnoticed.
- `<foreign xml:lang="lat">` (De Amicitia ONLY -- untranslated Latin words
  quoted inline in Falconer's English, e.g. "toga virilis," "amor",
  "amicitia", "obsequium") -- 54 occurrences, 50 inside dropped notes, 4 in
  running body text; passed through as plain text (no italics markup
  exists in this corpus's `clean.json` convention, matching `<hi>`).
- `<quote>` without "blockquote" in `@rend` (and, De Amicitia only, `<q>`
  of ANY `@type` -- "soCalled"/"emph"/"spoken"/"translation"/"written"/
  "mentioned"/"gloss" are all print-typography categories that resolve to
  the same plain quotation marks, confirmed against the archive.org scan
  for representative examples of each) -- wrapped in curly quotes,
  alternating double/single by nesting depth (Miller's convention; `<q>`
  and non-blockquote `<quote>` share one nesting-depth counter).
- `<quote rend="...blockquote...">` (verse/displayed quotations: Ennius,
  Pacuvius, Accius, Homer via Way, Terence, etc.) -- pass-through, no
  quote marks added, same as Miller. NOTE one De Amicitia edge case: a
  `<quote type="blockquote">` (attribute is `@type`, NOT `@rend`) wrapping
  a short Terence tag ("He says nay, and nay say I...") is verified against
  the archive.org scan to print WITH quotation marks, not as a displayed
  block -- Miller's `_is_verse_quote` check (`@rend` only) already gets
  this right by construction, unchanged here.
- `<hi rend="italics"|"italic">`, `<emph rend="italic">` (De Amicitia
  only), `<title>` (cross-references to Cicero's other works) -- all
  plain pass-through, no markup (matches Miller's `<hi>` convention; no
  markdown-emphasis convention exists in this corpus's `clean.json` files).
- `<l>`, `<sp>`/`<said>`/`<speaker>`/`<label>` (De Amicitia's dialogue
  markup only) -- plain pass-through containers, walked for text, no
  markup applied (matches Miller's treatment of `<speaker>`; a `<label>`
  like "FANNIUS." is kept as ordinary running text exactly as printed).
  Verified: every `<l>` sibling pair in all three files has real
  whitespace between `</l>` and the next `<l>` (zero tight `</l><l>`
  adjacencies), so the generic whitespace-collapse in `_clean` reproduces
  correct line-to-line spacing with no dedicated verse-line-join logic.
- `<milestone>` and `<pb>` -- no text of their own, pure structural
  markers (handled above).
- `<head>` -- never inside any per-section/per-book walk scope in a way
  that reaches an open section (De Senectute/De Divinatione: appears
  before each flat/book div's first milestone, `ctx.current` is still
  `None`, so `ctx.append` no-ops exactly as in Miller; De Amicitia: is a
  sibling of, and precedes, the first `subtype="section"` div, never
  visited at all since each section is walked as its own standalone unit).
- Whitespace: `re.sub(r"\\s+", " ", ...)`-collapsed and `.strip()`-ed, plus
  the same `_TIGHTEN` punctuation-adjacency pass as Miller.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import lxml.etree as ET

# --- paths -----------------------------------------------------------------

_SEN_DIR = Path("../sources/falconer-sen")
_AMIC_DIR = Path("../sources/falconer-amic")
_DIV_DIR = Path("../sources/falconer-div")

SRC_SEN = _SEN_DIR / "phi0474.phi051.perseus-eng1.xml"
SRC_AMIC = _AMIC_DIR / "phi0474.phi052.perseus-eng2.xml"
SRC_DIV = _DIV_DIR / "phi0474.phi053.perseus-eng1.xml"

OUT_SEN = _SEN_DIR / "falconer.clean.json"
OUT_AMIC = _AMIC_DIR / "falconer.clean.json"
OUT_DIV = _DIV_DIR / "falconer.clean.json"

PATCHES_SEN = _SEN_DIR / "PATCHES.json"
PATCHES_AMIC = _AMIC_DIR / "PATCHES.json"
PATCHES_DIV = _DIV_DIR / "PATCHES.json"

_EXPECTED_SHA256 = {
    SRC_SEN: "44ba1e6d5059cbbf774ee43b0feeb64d670511db972cd7be11192f12c24af348",
    SRC_AMIC: "b0c39a70e78e3d7363cabdc1832e8ca9de878a31ac6e13a18742aeda1d919069",
    SRC_DIV: "c4edfe8598dc7ff504ab91d3f6ad4d40879056155c05f71ad18f4141d1891ce6",
}

_PIN = "1066a551aa5445ab165e9b490a6bb06ce72828da"
_RAW_BASE = f"https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/{_PIN}/data/phi0474"

_TEI_NS = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI_NS}
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


# --- hand-verified Beta-Code -> Unicode Greek table (De Divinatione ONLY --
# see module docstring: De Senectute's and De Amicitia's body text carry no
# Beta-Code Greek at all, both verified by direct corpus count) -----------
_GREEK_TERMS = {
    "mantikh/": "μαντική",
    "daimo/nion,": "δαιμόνιον,",
    "ei(marme/nh,": "εἱμαρμένη,",
    "yeudo/menon;": "ψευδόμενον;",
    "o(ri/zontes,": "ὁρίζοντες,",
    "lh/mmata,": "λήμματα,",
    "pro/slhyis.": "πρόσληψις.",
    "sumpa/qeia": "συμπάθεια",
    "sumpa/qeia,": "συμπάθεια,",
}

# De Senectute's confirmed duplicate-milestone typo: the SECOND `n="35"`
# unit="section" milestone is really "36" (see module docstring). Keyed on
# the duplicated number; the walker consults this only when it is ABOUT to
# raise the duplicate-section ValueError, and only for a number present in
# this table -- any other duplicate still fails loud. Scoped to De
# Senectute ONLY: `_extract_flat_milestone` is the one caller that passes
# this table to `_walk` as `duplicate_fix`; every other walk (De Amicitia's
# per-div walk, De Divinatione's per-book walk) passes none, so a duplicate
# milestone anywhere else in the corpus is unconditionally fatal, not
# eligible for this narrow, hand-verified, De-Senectute-specific repair.
_DUPLICATE_MILESTONE_FIX = {35: 36}

# De Divinatione's ONE confirmed Perseus data-entry typo: `<milestone
# unit="seciton" n="128"/>` in Book II (see module docstring). Scoped to
# exactly that (book, n) pair -- `_extract_book_milestone`'s Book II call
# passes `seciton_alias_n=128`; the Book I call passes none. A "seciton"
# milestone anywhere else (Book I at all, or Book II with any n other than
# 128) is unconditionally fatal, not a general typo alias.
_SECITON_ALIAS_N = 128

_OPEN_QUOTE = ("“", "‘")  # curly double / single, by nesting depth
_CLOSE_QUOTE = ("”", "’")


def _is_verse_quote(el: ET._Element) -> bool:
    return _local(el.tag) == "quote" and "blockquote" in (el.get("rend") or "")


class _Ctx:
    """Threaded through one walk scope (a flat work, one section div, or one
    book div): `sections` accumulates a list of text fragments per open key;
    `current` is the key presently open (`None` before the first real
    section boundary, when only dropped front matter is in scope); `depth`
    is the current quote/`<q>` nesting depth, for alternating curly-quote
    style. `key_type` distinguishes int-keyed milestone walks from the
    single dummy string key a per-section-div walk uses (that walk has only
    one key, matching the whole div)."""

    def __init__(self) -> None:
        self.sections: dict[object, list[str]] = {}
        self.current: object | None = None
        self.depth = 0

    def append(self, text: str | None) -> None:
        if not text or self.current is None:
            return
        self.sections[self.current].append(text)


def _last_emitted_char(ctx: _Ctx) -> str | None:
    if ctx.current is None:
        return None
    parts = ctx.sections.get(ctx.current) or []
    for part in reversed(parts):
        if part:
            return part[-1]
    return None


def _append_after_dropped(ctx: _Ctx, tail: str | None) -> None:
    """Append a dropped element's (`<note>` or `<bibl>`) tail, inserting a
    single space when the lexical boundary would otherwise glue two
    alphanumeric runs into one word -- mirrors
    extract_miller_perseus.py's `_append_after_dropped_note` exactly, just
    generalized to the second dropped-element class this corpus has
    (`<bibl>`, see module docstring)."""
    if not tail or ctx.current is None:
        return
    prev = _last_emitted_char(ctx)
    if prev is not None and prev.isalnum() and tail[0].isalnum():
        ctx.append(" ")
    ctx.append(tail)


_DROPPED_WHOLE = {"note", "bibl"}


def _walk(
    el: ET._Element,
    ctx: _Ctx,
    *,
    milestone_units: tuple[str, ...] = (),
    duplicate_fix: dict[int, int] | None = None,
    seciton_alias_n: int | None = None,
) -> None:
    """Flatten `el`'s text into `ctx`. `milestone_units` names the
    `unit="..."` values that open a NEW section boundary (int(@n) becomes
    the new `ctx.current`); an empty tuple (De Amicitia's per-section-div
    walk) means milestones never change `ctx.current` at all -- the whole
    div is one already-delimited section.

    `duplicate_fix` is the hand-verified duplicate-milestone repair table
    (De Senectute's `_DUPLICATE_MILESTONE_FIX`) -- passed ONLY by the one
    caller it's verified for; every other caller leaves it `None`, so a
    duplicate milestone number anywhere else is unconditionally fatal.

    `seciton_alias_n` is the one `n` value (De Divinatione Book II's `128`)
    for which the misspelled `unit="seciton"` is accepted as a `"section"`
    typo -- passed ONLY by that book's call. A `"seciton"` milestone with
    any other `n`, or in a call that leaves this `None` entirely, is
    unconditionally fatal: it is never silently ignored like a genuinely
    unrecognized unit (e.g. "chapter") would be, because it is a known
    misspelling of a REAL section boundary, not a harmless different kind
    of milestone."""
    tag = _local(el.tag)

    if tag in _DROPPED_WHOLE:
        return  # tail appended by the parent loop via _append_after_dropped

    if tag == "milestone":
        unit = el.get("unit")
        if unit == "seciton":
            n_typo = int(el.get("n"))
            if seciton_alias_n is None or n_typo != seciton_alias_n:
                raise ValueError(
                    f"extract_falconer_perseus: misspelled milestone "
                    f"unit='seciton' n={n_typo} outside the one "
                    f"hand-verified alias (De Divinatione Book II, n=128) "
                    f"-- not silently accepted"
                )
            unit = "section"  # the one verified typo, now a normal boundary
        if unit in milestone_units:
            n = int(el.get("n"))
            if n in ctx.sections:
                fix = (duplicate_fix or {}).get(n)
                if fix is None or fix in ctx.sections:
                    raise ValueError(
                        f"extract_falconer_perseus: duplicate unit={unit!r} "
                        f"n={n} (no hand-verified fix applies here)"
                    )
                n = fix
            ctx.current = n
            ctx.sections[n] = []
        # Any other milestone unit (De Senectute/De Divinatione's "chapter")
        # carries no text and does not touch ctx.current -- see docstring.
        return

    if tag == "pb":
        return

    if tag == "foreign" and el.get(_XML_LANG) == "greek":
        raw = (el.text or "").strip()
        if raw not in _GREEK_TERMS:
            raise ValueError(
                f"extract_falconer_perseus: unexpected Beta-Code Greek "
                f"<foreign> string {raw!r} in running body text -- not in "
                f"the hand-verified _GREEK_TERMS table (section {ctx.current})"
            )
        ctx.append(_GREEK_TERMS[raw])
        return

    if tag == "foreign" and el.get(_XML_LANG) == "grc":
        # De Amicitia's alternate (already-Unicode) Greek convention --
        # verified corpus-wide to occur ONLY inside dropped <note>s (see
        # module docstring); this branch is therefore a defensive
        # pass-through never actually exercised by the pinned XML, guarded
        # by _assert_grc_all_in_notes() in main() so it cannot rot silently.
        ctx.append(el.text)
        return  # this corpus's <foreign> elements carry no children

    is_quote = (tag == "quote" and not _is_verse_quote(el)) or tag == "q"
    if is_quote:
        ctx.append(_OPEN_QUOTE[ctx.depth % 2])
        ctx.depth += 1

    ctx.append(el.text)
    for child in el:
        _walk(
            child, ctx, milestone_units=milestone_units,
            duplicate_fix=duplicate_fix, seciton_alias_n=seciton_alias_n,
        )
        if _local(child.tag) in _DROPPED_WHOLE:
            _append_after_dropped(ctx, child.tail)
        else:
            ctx.append(child.tail)

    if is_quote:
        ctx.depth -= 1
        ctx.append(_CLOSE_QUOTE[ctx.depth % 2])


_TIGHTEN = re.compile(r"\s+([,;:.!?’”])")


def _clean(parts: list[str]) -> str:
    text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return _TIGHTEN.sub(r"\1", text)


# --- patches (Miller-shape exact-once) --------------------------------------
def _load_patches(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_patches(records: list[dict], patches: list[dict], key_fn) -> list[dict]:
    by_key = {key_fn(r): r for r in records}
    for p in patches:
        key = p["key"]
        if key not in by_key:
            raise ValueError(f"PATCHES.json: key {key!r} not found in extraction output")
        text = by_key[key]["text"]
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: key {key} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        by_key[key]["text"] = text
    return records


def _verify_source(src: Path) -> None:
    if not src.exists():
        rel = src.relative_to(Path(".."))
        raise SystemExit(
            f"missing {src} -- fetch from {_RAW_BASE}/{rel.parts[1]}/"
            f"{rel.parts[1]}/{src.name} (or the corresponding phi05x dir) "
            f"and place it there before running."
        )
    actual = hashlib.sha256(src.read_bytes()).hexdigest()
    expected = _EXPECTED_SHA256[src]
    if actual != expected:
        raise SystemExit(
            f"SHA-256 mismatch for {src}: expected {expected}, got {actual} "
            "-- the pinned commit's file must not have changed; re-verify before proceeding."
        )


# --- De Senectute: flat, single-book milestone-cursor walk ------------------
def _extract_flat_milestone(root: ET._Element) -> dict[int, str]:
    ctx = _Ctx()
    _walk(root, ctx, milestone_units=("section",), duplicate_fix=_DUPLICATE_MILESTONE_FIX)
    nums = sorted(ctx.sections)
    assert nums == list(range(1, 86)), f"De Senectute: expected 1..85, got {nums}"
    return {n: _clean(ctx.sections[n]) for n in nums}


# --- De Amicitia: one already-delimited section per <div> -------------------
def _extract_section_divs(divs: list[ET._Element]) -> dict[int, str]:
    out: dict[int, str] = {}
    for expected_n, div in enumerate(divs, start=1):
        n = int(div.get("n"))
        assert n == expected_n, (
            f"De Amicitia: section divs out of document order -- expected "
            f"n={expected_n} at position {expected_n}, div's own @n is {n}"
        )
        ctx = _Ctx()
        ctx.current = n
        ctx.sections[n] = []
        for child in div:
            _walk(child, ctx, milestone_units=())
            if _local(child.tag) in _DROPPED_WHOLE:
                _append_after_dropped(ctx, child.tail)
            else:
                ctx.append(child.tail)
        out[n] = _clean(ctx.sections[n])
    assert sorted(out) == list(range(1, 105)), f"De Amicitia: expected 1..104, got {sorted(out)}"
    return out


# --- De Divinatione: Miller-shape per-book milestone-cursor walk, x2 --------
def _extract_book_milestone(
    book: ET._Element, expected_max: int, allow_missing: set[int],
    *, seciton_alias_n: int | None = None,
) -> dict[int, str]:
    ctx = _Ctx()
    _walk(book, ctx, milestone_units=("section",), seciton_alias_n=seciton_alias_n)
    nums = sorted(ctx.sections)
    expected = sorted(set(range(1, expected_max + 1)) - allow_missing)
    assert nums == expected, (
        f"De Divinatione book: expected {expected[0]}..{expected[-1]} minus "
        f"{sorted(allow_missing) or 'none'}, got {nums}"
    )
    return {n: _clean(ctx.sections[n]) for n in nums}


def _assert_grc_all_in_notes(src: Path) -> None:
    """De Amicitia's already-Unicode `xml:lang="grc"` <foreign> occurrences
    are all inside dropped <note>s in the pinned XML (corpus-verified 7/7,
    see module docstring) -- the pass-through branch in _walk is therefore
    dead code on this pinned source, kept only as a defensive fallback. This
    guards that fact: if a future re-fetch ever moves one into running body
    text, this fails loud instead of the change passing through unnoticed
    (the pass-through would still be CORRECT -- grc is already Unicode -- but
    the docstring's "0 needed" claim would be stale)."""
    tree = ET.parse(str(src))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    total = 0
    in_note = 0
    for el in body.iter():
        if _local(el.tag) != "foreign" or el.get(_XML_LANG) != "grc":
            continue
        total += 1
        if any(_local(a.tag) == "note" for a in el.iterancestors()):
            in_note += 1
    assert total == 7, f"expected 7 <foreign xml:lang=grc> in De Amicitia, found {total}"
    assert in_note == total, (
        f"De Amicitia: {total - in_note} <foreign xml:lang=grc> now sit OUTSIDE "
        f"<note> -- update the module docstring's element-handling claim"
    )


def _extract_senectute() -> None:
    _verify_source(SRC_SEN)
    tree = ET.parse(str(SRC_SEN))
    root = tree.getroot().find(
        './/t:text/t:body/t:div[@type="translation"]', _NS
    )
    assert root is not None, "De Senectute: translation div not found"
    sections = _extract_flat_milestone(root)

    seen_greek: set[str] = set()  # De Senectute uses no _GREEK_TERMS entries
    records = [{"section": n, "text": sections[n]} for n in sorted(sections)]
    for r in records:
        assert r["text"], f"De Senectute {r['section']}: empty record"

    patches = _load_patches(PATCHES_SEN)
    records = _apply_patches(records, patches, key_fn=lambda r: r["section"])

    OUT_SEN.write_text(
        json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"De Senectute: {len(records)} sections -> {OUT_SEN}")


def _extract_amicitia() -> None:
    _verify_source(SRC_AMIC)
    _assert_grc_all_in_notes(SRC_AMIC)
    tree = ET.parse(str(SRC_AMIC))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    divs = body.findall('.//t:div[@subtype="section"]', _NS)
    assert len(divs) == 104, f"expected 104 section divs, found {len(divs)}"
    sections = _extract_section_divs(divs)

    records = [{"section": n, "text": sections[n]} for n in sorted(sections)]
    for r in records:
        assert r["text"], f"De Amicitia {r['section']}: empty record"

    patches = _load_patches(PATCHES_AMIC)
    records = _apply_patches(records, patches, key_fn=lambda r: r["section"])

    OUT_AMIC.write_text(
        json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"De Amicitia: {len(records)} sections -> {OUT_AMIC}")


def _extract_divinatione() -> None:
    _verify_source(SRC_DIV)
    tree = ET.parse(str(SRC_DIV))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    books = body.findall('.//t:div[@subtype="book"]', _NS)
    assert len(books) == 2, f"expected 2 book divs, found {len(books)}"
    assert books[0].get("n") == "1" and books[1].get("n") == "2", (
        f"unexpected book @n values: {[b.get('n') for b in books]}"
    )

    # Book I: declared gap at n=25 (see module docstring -- content very
    # likely present, folded into 1:24's span, but with no recoverable
    # single-sentence splice point; left DECLARED, not silently patched).
    book1 = _extract_book_milestone(books[0], expected_max=132, allow_missing={25})
    # Book II: n=128 fires via the "seciton" typo alias -- scoped to this
    # ONE call (_SECITON_ALIAS_N); Book I gets no such alias at all, so a
    # "seciton" milestone there (or a mismatched n here) is fatal.
    book2 = _extract_book_milestone(
        books[1], expected_max=150, allow_missing=set(), seciton_alias_n=_SECITON_ALIAS_N,
    )

    seen_greek: set[str] = set()
    # NOTE: book1 and book2 both key by bare int section number (1.. and
    # 1..) -- merging the two dicts by key (`{**book1, **book2}`) would
    # silently collapse same-numbered sections from different books and
    # under-report usage, so both books' texts are checked independently.
    for book_dict in (book1, book2):
        for text in book_dict.values():
            for greek in _GREEK_TERMS.values():
                if greek in text:
                    seen_greek.add(greek)
    unused = set(_GREEK_TERMS.values()) - seen_greek
    if unused:
        raise AssertionError(f"_GREEK_TERMS entries never matched in output: {unused}")

    records = [{"book": 1, "section": n, "text": book1[n]} for n in sorted(book1)]
    records += [{"book": 2, "section": n, "text": book2[n]} for n in sorted(book2)]
    for r in records:
        assert r["text"], f"De Divinatione {r['book']}:{r['section']}: empty record"

    patches = _load_patches(PATCHES_DIV)
    records = _apply_patches(records, patches, key_fn=lambda r: f"{r['book']}:{r['section']}")

    OUT_DIV.write_text(
        json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"De Divinatione: {len(records)} sections "
        f"(book 1: {len(book1)}/132, book 2: {len(book2)}/150) -> {OUT_DIV}"
    )


def main() -> None:
    _extract_senectute()
    _extract_amicitia()
    _extract_divinatione()


if __name__ == "__main__":
    main()
