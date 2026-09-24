"""One-off: fetch Richard M. Gummere's Loeb translation of Seneca's *Ad
Lucilium Epistulae Morales* (all 124 letters) from Wikisource's mainspace
transcription (en.wikisource.org, "Moral letters to Lucilius/Letter 1" ..
"/Letter 124") and produce a clean, letter.section-keyed JSON --
`sources/gummere-epistulae/gummere.clean.json`. Target work: `epistulae-
morales` (the `letter` citation scheme -- letter = page axis, section =
column, dotted grammar identical to book-section, see
manifests/epistulae-morales.yaml). See `sources/gummere-epistulae/README.md`
and `sources/INVENTORY.md` for the full provenance/verification writeup;
this docstring covers extraction mechanics only.

## Route: rendered HTML, not raw wikitext

Each mainspace Letter page's own wikitext is just a `{{header}}` template
plus a single `<pages index=... include=A,B fromsection="i" tosection="i"
/>` ProofreadPage transclusion tag -- the real prose lives in the
`Page:Ad Lucilium epistulae morales, volume N.djvu/<M>` subpages that tag
pulls in. Unlike extract_munro_wikisource.py / extract_yonge_nd_wikisource.py
(which fetch each Page: subpage's raw wikitext individually and hand-roll
the page-seam joins), this script fetches `action=parse&prop=text` -- the
SERVER-RENDERED HTML -- which lets MediaWiki's own ProofreadPage extension
resolve the `<pages>` transclusion (word-joins across page boundaries,
hyphenation, running-head/pagenum chrome) instead of reimplementing that
logic here. Verified against the underlying Page: subpages actually used
(778 quality-3 "Proofread" + 2 quality-4 "Validated" pages across all 124
letters, zero below quality 3 -- extracted from each render's own
`data-page-quality` attributes) -- despite the Letter-page Index itself
being only formally/nominally unproofread as a wrapper concept, every
individual underlying page is proofread-or-better.

**Reproducibility tradeoff, stated plainly**: `_LETTER_REVISIONS` pins each
mainspace Letter page's own revision id (captured 2026-07-21 via this
script's own `action=parse&prop=revid` responses), which protects against a
future edit to the wrapper's own `<pages include=.../>` parameters. It does
NOT pin the underlying Page: namespace revisions the way the Munro/Yonge
ND scripts' `_PAGE_REVISIONS` tables do -- `action=parse&oldid=<revid>`
resolves `<pages>` transclusions using the THEN-CURRENT Page: content, not
a historically pinned one (the same caveat those scripts' docstrings note
about wrapper pins never reaching into Page: pins). This is a deliberate
simplification given the underlying pages' proofread-or-better quality and
the independent archive.org spot-check below (not a claim of Munro/Yonge-
grade byte-for-byte reproducibility); a future re-run could pick up a
Wikisource proofreading correction made after 2026-07-21, which would only
ever improve, not degrade, fidelity to the print.

## Structure

Each rendered letter page is `<div class="ws-header">...</div>` (nav
chrome, never visited -- this script only reads the sibling
`<div class="prp-pages-output">`) followed by the assembled prose. Within
that div:

- `<span class="pagenum ws-pagenum">` -- zero-width per-page markers (a
  zero-width-space `data-page-quality`-bearing span the ProofreadPage
  extension inserts at each underlying page boundary); dropped whole, no
  text lost (the actual page-seam prose join was already performed by
  MediaWiki's own rendering, unlike the raw-wikitext scripts' hand-rolled
  seam classifier).
- `<div class="wst-center tiInherit">` -- centered front-matter lines
  before the letter's own content starts: the running head ("THE EPISTLES
  OF SENECA", present only on the 3 volume-opening letters 1/66/93) and
  the letter's own title ("I. ON SAVING TIME") -- both dropped, matching
  every prior extractor's "front matter before the first citable marker is
  never captured" convention. See "Letter 1's salutation" below for the
  ONE exception.
- `<span class="wst-verse wst-verse-default" id="N.">` (wrapping
  `<sup><b>N.</b></sup>`) -- the section-number marker itself (dropped;
  its OWN "N." glyph is never emitted as prose) opening a new section --
  matches this scheme's dotted "letter.section" column exactly (see
  manifests/epistulae-morales.yaml's own `citation.scheme: letter` note).
- `<sup class="reference">...</sup>` (a footnote reference mark, 1,067
  occurrences across 122 of 124 letters) -- dropped whole, matching house
  style (`<ref>`/footnote-drop convention shared by every prior extractor);
  the footnote TEXT itself lives in a `<div class="reflist">` that is a
  SIBLING of, not a descendant of, `prp-pages-output` -- never visited at
  all by construction, so it needs no separate exclusion step.
- `<span class="wst-lang wst-lang-grc">` -- already-Unicode Greek quoted
  inline in Gummere's English (9 occurrences, letters 58/82/89: οὐσία, ὄν,
  ἀδιάφορα, σοφία) -- plain pass-through, matching Falconer's `xml:lang=
  "grc"` convention (De Amicitia) for already-Unicode Greek.
- `<div class="wst-block-center">` wrapping `<div class="wst-size-block
  wst-fine wst-fine-block">` -- centered verse quotations (Gummere's own
  translations of Latin poets quoted mid-letter) with internal `<br/>`
  line breaks (144 occurrences corpus-wide, ALL verified to sit inside
  this wrapper -- zero stray `<br/>` in ordinary running prose) --
  flattened into the surrounding paragraph exactly like
  extract_yonge_nd_wikisource.py's `<poem>` handling (this scheme is
  section-level prose, not verse-line -- no downstream consumer for verse
  lineation); each `<br/>` becomes a single space.
- `<i>`, `<span class="smallcaps">` -- plain pass-through, no markup
  (matches every prior extractor's italic/small-caps convention).
- `<div class="wst-dhr">` (decorative hidden-rule spacer) and
  `<div class="__nop wst-nop">` (forced-paragraph-break marker) -- both
  drop to nothing; this corpus's `clean.json` convention (matching
  extract_falconer_perseus.py's own `_clean`) collapses ALL whitespace to
  single spaces with no paragraph structure preserved, so a forced-
  paragraph-break marker carries no information this format can represent
  anyway.

## Letter 1's salutation (the brief's own "do not invent a section" note)

The Latin PHI export's `citation.salutation_role` folds each letter's own
`<section n="sa">` (the conventional Latin epistolary greeting formula --
never quoted here; this script never handles Latin text at all) onto that
letter's own section 1 as a leading, non-citable line (see manifests/
epistulae-morales.yaml's own header comment). Checked directly against ALL 124
letters' rendered HTML (every front `wst-center` div before the first
section marker, corpus-wide): only Letter 1 carries an ADDITIONAL third
front div reading "Greetings from Seneca to his friend Lucilius." -- every
other letter (including the other two volume-openers, 66 and 93) goes
straight from the title div into its own numbered "1." marker with no
separate greeting sentence at all (Gummere evidently rendered the
salutation as English prose only once, introducing the whole work, not
letter-by-letter). This script therefore prepends that one sentence onto
Letter 1's own section-1 text (never a separate section/record) and
FAILS LOUD if it is missing, duplicated, or found (verbatim or by the
substring "Greetings from Seneca") anywhere else in the corpus --
`_SALUTATION` / `_Ctx.salutation` below.

## Two declared per-letter numbering exceptions (both cross-checked against
## the real PHI Latin spine's own per-letter word counts, not guessed)

Every one of the other 122 letters' section-marker COUNT matches the
Latin spine's own count for that letter exactly (see
manifests/epistulae-morales.yaml's `books:` list), and a corpus-wide
per-section English-word-count / Latin-word-count ratio sweep (2,093
one-to-one section pairs; median ratio 1.76, i.e. Gummere's English runs
~1.8x the Latin word count, a stable expansion factor for Loeb prose
translation) turned up ZERO outliers outside that -- strong evidence the
1:1 marker correspondence holds letter-by-letter, not just in aggregate
count. Two letters are the sole exceptions, and both are genuine edition-
level section-boundary differences between Gummere's source text (Hense's
1898 Teubner) and this project's Latin spine (Reynolds' 1965 OCT), not
extraction bugs:

- **Letter 41: Gummere's English has 9 numbered markers where the Latin
  spine has only 8** (41.1-41.8). English markers 8 and 9 are both
  substantial (63 and 75 words) where the Latin's own final section 41.8
  is 74 words -- combined, 138 English words for 74 Latin words gives a
  ratio of 1.86, squarely inside this letter's own established range
  (41.5-41.7 run 2.2/1.8/1.7); English 8 ALONE against Latin 8 would be an
  outlying 0.85. Hense's edition evidently subdivides what Reynolds' OCT
  keeps as one section. `_MERGE_TAIL = {41: 9}`: marker "9." does not open
  a new section -- its content folds onto the still-open section 8,
  matching extract_falconer_perseus.py's `_DUPLICATE_MILESTONE_FIX`
  precedent (a narrow, hand-verified, cited exception scoped to this one
  letter; any other letter's marker sequence must still be perfectly
  contiguous from 1 or the build fails loud).
- **Letter 108: Gummere's English has only 38 numbered markers where the
  Latin spine has 39** (108.1-108.39). English's own final marker (38, 120
  words, ending "...Farewell.") is the true end of the letter -- there is
  no missing content, just one fewer boundary than Reynolds' OCT draws:
  Latin 108.38+108.39 (34+33 = 67 words) against English 38 alone (120
  words) gives ratio 1.79, matching this letter's own established range,
  where English-38-alone against Latin-38-alone would be an outlying 3.5.
  Left DECLARED, exactly like Falconer's De Divinatione 1:25 gap: this
  script emits Letter 108 with sections 1..38 only (no fabricated 39th
  key); manifests/epistulae-morales.yaml declares `alignment_allow_
  unmatched: ["108:108.39"]` to match (out of this script's blast radius).

## Cleaning / self-check gates

Whitespace collapse + punctuation-tighten exactly matches
extract_falconer_perseus.py's `_clean`. Fail-loud gates: all 124 letters
present; every letter's section numbers contiguous from 1 (post `_MERGE_
TAIL` folding) with no duplicates or gaps; every letter's max section
number matches `_EXPECTED_SECTIONS` (the real Latin spine's own per-letter
count, with Letter 108 overridden to 38 per the declared gap above); no
empty section text; no residual HTML/entity markup (`<`, `>`, `&#`,
`cite-bracket`) survives cleaning; Letter 1's salutation found exactly
once and nowhere else; deterministic across two runs (byte-identical
output, verified via the pinned `_LETTER_REVISIONS` + the local fetch
cache below).

## Cache integrity (post-adversarial-review hardening)

A GPT-5.6-Sol adversarial review proved that a truncated cached Letter 2
(`.html`) -- section 2.6 silently shortened from 560 to 64 chars -- still
passed every gate above, because the cache was trusted purely on the
basis of file-existence, with no validation of completeness. Fixed with
three layers, all fail-loud:

1. **Atomic cache writes** (`_atomic_write`): every cache file is written
   to a sibling `.tmp-<pid>` path and `os.replace`d into place, so a
   process killed mid-write never leaves a half-written `.html` file that
   a later run would silently trust.
2. **Envelope/completeness validation** (`_validate_rendered_html`),
   applied to BOTH a freshly-fetched API response body and an
   already-cached file before either is handed to the HTML parser: reject
   empty text; reject text missing its expected trailing MediaWiki
   `action=parse` terminal anchor (the "Saved in parser cache" comment
   `action=parse&prop=text` always appends as the very last thing in the
   rendered body -- verified present, byte-identical position, at the
   tail of all 124 real pinned responses; a truncation drops this even
   when the cut point falls mid-prose and would NOT otherwise look like
   broken HTML to lxml's lenient parser); reject text that does not
   contain exactly one `prp-pages-output` div. A freshly-fetched response
   additionally has its JSON envelope shape checked (`parse.text` and
   `parse.revid` present, `parse.revid` matching the requested `oldid`)
   before its `text` field is trusted at all.
3. **Per-letter content-hash + per-page-quality declarations**
   (`sources/gummere-epistulae/gummere.integrity.json`, `_validate_
   integrity` / `_write_integrity_baseline`): since this extraction is now
   FROZEN (`gummere.clean.json` is the committed artifact), each letter's
   rendered-HTML sha256 and each underlying page's `data-page-quality`
   are declared once (written by running this script with
   `--bootstrap-integrity` against the verified-good cache) and checked
   bidirectionally on every subsequent run -- a declared-but-unobserved
   OR observed-but-undeclared letter/page is fatal, and any hash/quality
   MISMATCH is fatal. This is deliberately simpler than the Munro/Yonge ND
   scripts' `_PAGE_REVISIONS` per-page revision pinning: pinning the
   RENDERED content's own hash catches any drift in the underlying Page:
   namespace transclusions transitively (a changed Page: revision changes
   the rendered HTML, which changes its hash), without needing a second
   pinning table for content this script never re-fetches once frozen.
   BLOCKER fix (Sol re-verification, 2026-07-21): `--bootstrap-integrity`
   is CREATION-ONLY -- fatal if `gummere.integrity.json` already exists,
   never silently overwriting it (which could otherwise re-bootstrap
   straight around a genuine integrity mismatch a plain run just reported;
   delete the file deliberately first if a re-bootstrap is truly intended).
   Written atomically (temp+rename, via `_atomic_write`) so a process
   killed mid-write never leaves a half-written integrity manifest for a
   later run to trust -- the same hardening already applied to the fetch
   cache above.

Two further hardenings from the same review:

- **Exact-once merge assertion** (`_assert_merge_invariant`): Letter 41's
  declared `_MERGE_TAIL` fold is now asserted, not just performed --
  exactly one merge event for `(41, 9)`, folding into exactly section 8
  (Letter 41's own declared final section), with marker 9 verified as the
  FINAL raw marker in that letter's own encountered-marker sequence,
  immediately following marker 8. Silently removing marker 9 (zero
  merges) or duplicating it (two merges) each used to pass; both are now
  fatal.
- **Fail-loud element allowlist** inside `_walk`'s generic pass-through
  branch: only the exact (tag, class-set) combinations verified to occur
  in the real corpus (see `_ALLOWED_PASSTHROUGH`) are allowed to fall
  through as plain prose; anything else (e.g. an injected maintenance
  banner div, or any other unrecognized element Wikisource might render
  in the future) raises instead of silently being flattened into a
  section's text.

All corpus-wide final-text invariants (empty-text, residual-markup, the
salutation-exactly-once-at-letter-1-section-1 check) are re-run AFTER
`PATCHES.json` application, not only during per-letter parsing, and the
salutation check itself now scans every FINAL record's text corpus-wide
(not just the front `wst-center` divs `_walk` happens to visit) --
closing the gap where a salutation-like sentence surfacing in some other
letter's own body prose, rather than its front matter, would previously
have gone unchecked.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import lxml.html

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "sources" / "gummere-epistulae"
OUT_CLEAN = OUT_DIR / "gummere.clean.json"
PATCHES = OUT_DIR / "PATCHES.json"
# Declared per-letter rendered-HTML sha256 + per-page data-page-quality
# baseline, generated once (via --bootstrap-integrity) against the
# verified-good cache and checked bidirectionally on every rerun -- see
# the module docstring's "Cache integrity" section.
GUMMERE_INTEGRITY = OUT_DIR / "gummere.integrity.json"
# Local, untracked fetch cache (build/ is gitignored repo-wide) -- keyed by
# revid, so a rerun with the SAME _LETTER_REVISIONS table never re-fetches.
CACHE_DIR = REPO_ROOT / "build" / "gummere-wikisource-cache"

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

_N_LETTERS = 124

# Captured 2026-07-21 via this script's own action=parse&prop=revid response
# for each "Moral_letters_to_Lucilius/Letter_<N>" mainspace page (current
# revision at fetch time). Re-running this script fetches these EXACT
# wrapper revisions -- see the module docstring's "reproducibility
# tradeoff" section for what this does and does not pin.
_LETTER_REVISIONS: dict[int, int] = {
    1: 14843822, 2: 14843823, 3: 14843824, 4: 14843825, 5: 14843828, 6: 14843830, 7: 14843832, 8: 14843833,
    9: 14843835, 10: 14843836, 11: 14843837, 12: 14843840, 13: 14843841, 14: 14843842, 15: 14843844, 16: 14843846,
    17: 14843847, 18: 14843849, 19: 14843850, 20: 14843851, 21: 14843854, 22: 14843855, 23: 14843856, 24: 14843858,
    25: 14843859, 26: 14843860, 27: 14843861, 28: 14843862, 29: 14843864, 30: 14843865, 31: 14843866, 32: 14843867,
    33: 15153510, 34: 14843870, 35: 14843871, 36: 14843872, 37: 14843873, 38: 14843874, 39: 14843875, 40: 14843878,
    41: 14843881, 42: 14843882, 43: 14843883, 44: 14843884, 45: 14843885, 46: 14843886, 47: 14843887, 48: 14843891,
    49: 14844691, 50: 14844692, 51: 14844694, 52: 14844695, 53: 14843898, 54: 14843899, 55: 14843901, 56: 14886394,
    57: 14886397, 58: 14886399, 59: 14886403, 60: 14886408, 61: 14886410, 62: 14886412, 63: 14886427, 64: 14886430,
    65: 14886431, 66: 14886434, 67: 14886435, 68: 14886437, 69: 14886439, 70: 14843926, 71: 14843928, 72: 14843930,
    73: 14843932, 74: 14843936, 75: 14843938, 76: 14843939, 77: 14843941, 78: 14843943, 79: 14843944, 80: 14843947,
    81: 14843948, 82: 14843949, 83: 14843950, 84: 14843951, 85: 14843953, 86: 14843954, 87: 14843955, 88: 14843956,
    89: 14843957, 90: 14843960, 91: 14843962, 92: 14843964, 93: 14843965, 94: 14843966, 95: 14843969, 96: 14843970,
    97: 14843971, 98: 14843973, 99: 14843975, 100: 14843977, 101: 14843979, 102: 14843981, 103: 14843982, 104: 14843983,
    105: 14843985, 106: 14843987, 107: 14843989, 108: 14843991, 109: 14843992, 110: 14843997, 111: 14843998, 112: 14844001,
    113: 14844700, 114: 14844701, 115: 14844006, 116: 14844009, 117: 14844010, 118: 14844011, 119: 14844013, 120: 14844014,
    121: 14844015, 122: 14844018, 123: 14844019, 124: 14844022,
}

# The real PHI Latin spine's own per-letter section count (see
# manifests/epistulae-morales.yaml's `books:` list) -- EXCEPT letter 108,
# overridden to 38 for the declared gap (see module docstring). This is
# the EXPECTED ENGLISH count this script's own output must match, not a
# re-derivation of the Latin spine itself.
_EXPECTED_SECTIONS: dict[int, int] = {
    1: 5, 2: 6, 3: 6, 4: 11, 5: 9, 6: 7, 7: 12, 8: 10, 9: 22, 10: 5,
    11: 10, 12: 11, 13: 17, 14: 18, 15: 11, 16: 9, 17: 12, 18: 15, 19: 12, 20: 13,
    21: 11, 22: 17, 23: 11, 24: 26, 25: 7, 26: 10, 27: 9, 28: 10, 29: 12, 30: 18,
    31: 11, 32: 5, 33: 11, 34: 4, 35: 4, 36: 12, 37: 5, 38: 2, 39: 6, 40: 14,
    41: 8, 42: 10, 43: 5, 44: 7, 45: 13, 46: 3, 47: 21, 48: 12, 49: 12, 50: 9,
    51: 13, 52: 15, 53: 12, 54: 7, 55: 11, 56: 15, 57: 9, 58: 37, 59: 18, 60: 4,
    61: 4, 62: 3, 63: 16, 64: 10, 65: 24, 66: 53, 67: 16, 68: 14, 69: 6, 70: 28,
    71: 37, 72: 11, 73: 16, 74: 34, 75: 18, 76: 35, 77: 20, 78: 29, 79: 18, 80: 10,
    81: 32, 82: 24, 83: 27, 84: 13, 85: 41, 86: 21, 87: 41, 88: 46, 89: 23, 90: 46,
    91: 21, 92: 35, 93: 12, 94: 74, 95: 73, 96: 5, 97: 16, 98: 18, 99: 32, 100: 12,
    101: 15, 102: 30, 103: 5, 104: 34, 105: 8, 106: 12, 107: 12, 108: 38, 109: 18, 110: 20,
    111: 5, 112: 4, 113: 32, 114: 27, 115: 18, 116: 8, 117: 33, 118: 17, 119: 16, 120: 22,
    121: 24, 122: 19, 123: 17, 124: 24,
}

# Letter 41's declared merge: marker "9." folds onto the still-open section
# 8 rather than opening a new one (see module docstring).
_MERGE_TAIL: dict[int, int] = {41: 9}

_SALUTATION = "Greetings from Seneca to his friend Lucilius."

# The exact (tag, class-set) combinations verified (by walking the real,
# pinned 124-letter corpus with an instrumented copy of _walk) to reach the
# generic pass-through branch below. Anything NOT in this set is fatal --
# an injected maintenance banner or any other unrecognized element must not
# silently flatten into a section's prose (see module docstring's "Cache
# integrity" section, MAJOR 2).
_ALLOWED_PASSTHROUGH: frozenset[tuple[str, frozenset[str]]] = frozenset({
    ("p", frozenset()),
    ("span", frozenset()),  # bare wrapper span (around a dropped pagenum
    # span, or around verse-line text inside a wst-block-center quotation)
    ("i", frozenset()),
    ("div", frozenset({"wst-block-center"})),  # centered verse quotation
    ("div", frozenset({"wst-fine", "wst-fine-block", "wst-size-block"})),  # ditto, inner block
    ("div", frozenset({"tiInherit", "wst-center"})),  # mid-letter centered
    # epigraph heading (ctx.current is already set here; the front-matter
    # case above only matches while ctx.current is None)
    ("span", frozenset({"smallcaps"})),
    ("span", frozenset({"wst-lang", "wst-lang-grc"})),  # already-Unicode Greek
    ("span", frozenset({"wst-tooltip", "wst-tooltip-dash"})),  # hover-gloss text
    ("span", frozenset({"__gap", "wst-gap"})),  # verse-line indentation spacer
    ("span", frozenset({"nowrap"})),  # e.g. ". . ." kept from wrapping
    ("span", frozenset({"wst-fqm"})),  # floating quotation mark (verse block)
})

_MARKER_ID_RE = re.compile(r"^(\d+)\.$")
_WS_RE = re.compile(r"\s+")
_TIGHTEN_RE = re.compile(r"\s+([,;:.!?’”])")


_TERMINAL_ANCHOR = "Saved in parser cache"


def _validate_rendered_html(letter_n: int, text: str, source: str) -> None:
    """Fail loud unless `text` is a COMPLETE rendered-HTML response body --
    guards against a truncated cache write or truncated HTTP read silently
    masquerading as valid content (a GPT-5.6-Sol adversarial review proved a
    truncated cached Letter 2 passed every downstream section-count/markup
    check while shortening section 2.6 from 560 to 64 chars). `source` is
    "cache" or "fetch", for the error message only."""
    if not text or not text.strip():
        raise ValueError(f"letter {letter_n}: {source} produced empty HTML")
    # action=parse&prop=text always appends this HTML comment as the LAST
    # thing in the rendered body (verified present, at the tail, in all 124
    # real pinned responses -- see module docstring). A truncation loses
    # this terminal anchor even when the cut point falls mid-prose, where it
    # would not otherwise look like broken HTML to lxml's lenient parser.
    if _TERMINAL_ANCHOR not in text[-2000:]:
        raise ValueError(
            f"letter {letter_n}: {source} HTML is missing its expected "
            f"trailing {_TERMINAL_ANCHOR!r} anchor -- truncated or malformed"
        )
    try:
        doc = lxml.html.fromstring(text)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is fatal here
        raise ValueError(f"letter {letter_n}: {source} HTML failed to parse: {exc}") from exc
    n_content = len(doc.xpath('//div[@class="prp-pages-output"]'))
    if n_content != 1:
        raise ValueError(
            f"letter {letter_n}: {source} HTML has {n_content} prp-pages-output "
            f"divs, expected exactly 1 -- truncated or malformed"
        )


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` via write-temp-then-rename, so a process
    killed mid-write never leaves a half-written file for a later run to
    trust (the cache is keyed by revid and never rewritten once complete,
    so an atomic write is all determinism requires)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)  # atomic on POSIX


def _fetch(letter_n: int, revid: int, retries: int = 6) -> str:
    """The rendered HTML (`parse.text`) for one pinned letter-page revision,
    served from the local untracked cache when present. Both the cached and
    the freshly-fetched path are validated as a COMPLETE response body
    before being trusted (see `_validate_rendered_html`)."""
    cache_path = CACHE_DIR / f"{revid}.html"
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
        _validate_rendered_html(letter_n, text, "cache")
        return text
    url = f"{API}?action=parse&oldid={revid}&prop=text&format=json&formatversion=2"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"letter {letter_n} oldid={revid}: API response is not valid JSON: {exc}"
                ) from exc
            if "error" in data:
                raise RuntimeError(f"MediaWiki API error for letter {letter_n} oldid={revid}: {data['error']}")
            parse = data.get("parse")
            if not isinstance(parse, dict) or "text" not in parse or "revid" not in parse:
                raise RuntimeError(
                    f"letter {letter_n} oldid={revid}: malformed API envelope -- "
                    f"missing parse.text/parse.revid"
                )
            if parse["revid"] != revid:
                raise RuntimeError(
                    f"letter {letter_n}: API returned revid {parse['revid']}, expected {revid}"
                )
            text = parse["text"]
            _validate_rendered_html(letter_n, text, "fetch")
            _atomic_write(cache_path, text)
            return text
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = int(exc.headers.get("Retry-After", "10") or "10") + 2
                print(f"  rate-limited on letter {letter_n}; waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch letter {letter_n} (oldid={revid}) after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
        except urllib.error.URLError as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch letter {letter_n} (oldid={revid}) after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
    raise AssertionError("unreachable")


class _Ctx:
    """Threaded through one letter's walk. `sections` accumulates text
    fragments per open section number; `current` is the presently-open
    section (`None` before the first "1." marker, when only dropped front
    matter is in scope); `salutation` holds Letter 1's own greeting
    sentence once found (prepended to section 1 at the end); `front_divs`
    is a diagnostic record of every dropped front `wst-center` div's text,
    for the caller's own reporting."""

    def __init__(self) -> None:
        self.sections: dict[int, list[str]] = {}
        self.current: int | None = None
        self.salutation: str | None = None
        self.front_divs: list[str] = []

    def append(self, text: str | None) -> None:
        if not text or self.current is None:
            return
        self.sections[self.current].append(text)


def _local_tag(el) -> str | None:
    return el.tag if isinstance(el.tag, str) else None


def _collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _walk(el, ctx: _Ctx, letter_n: int, report: dict) -> None:
    tag = _local_tag(el)
    classes = (el.get("class") or "").split()

    if tag in ("style", "link"):
        return  # no text of their own; caller appends .tail

    if tag == "span" and "pagenum" in classes:
        # Zero-width per-page marker; the page-seam prose join was already
        # performed by MediaWiki's own <pages> rendering. Capture its
        # data-page-quality/data-page-name for the declared per-page
        # integrity check (see _validate_integrity / module docstring) --
        # a page transcluded more than once (shared boundary page between
        # two letters) must report the SAME quality every time.
        page_name = el.get("data-page-name")
        quality = el.get("data-page-quality")
        if not page_name or quality is None:
            raise ValueError(
                f"letter {letter_n}: pagenum span missing data-page-name/"
                f"data-page-quality attributes"
            )
        page_quality: dict = report.setdefault("page_quality", {})
        prev = page_quality.get(page_name)
        if prev is not None and prev != quality:
            raise ValueError(
                f"letter {letter_n}: page {page_name!r} data-page-quality "
                f"changed across transclusions: {prev!r} vs {quality!r}"
            )
        page_quality[page_name] = quality
        page_occurrences: dict = report.setdefault("page_occurrences", {})
        page_occurrences[page_name] = page_occurrences.get(page_name, 0) + 1
        return

    if tag == "sup" and "reference" in classes:
        report["n_footnotes"] = report.get("n_footnotes", 0) + 1
        return  # footnote reference mark; the note text itself is a
        # sibling of prp-pages-output, never visited at all

    if tag == "div" and "wst-dhr" in classes:
        return  # decorative hidden-rule spacer

    if tag == "div" and "wst-nop" in classes:
        return  # forced-paragraph-break marker; no paragraph structure
        # is preserved in this corpus's clean.json convention anyway

    if tag == "div" and classes == ["wst-center", "tiInherit"] and ctx.current is None:
        # This class is reused for two unrelated purposes: front-matter
        # chrome (running head / letter title, always BEFORE section 1
        # opens) and centered verse quotations mid-letter (AFTER a section
        # has opened -- see e.g. letter 8's "What Chance has made yours..."
        # quotation). Only the front-matter case is special-cased here;
        # once ctx.current is set this falls through to the generic
        # pass-through branch below like any other centered content.
        text = _collapse_ws(el.text_content())
        if letter_n == 1 and text == _SALUTATION:
            if ctx.salutation is not None:
                raise ValueError("letter 1: salutation div matched more than once")
            ctx.salutation = text
        else:
            if "greetings from seneca" in text.lower():
                raise ValueError(
                    f"letter {letter_n}: unexpected greeting-like front div "
                    f"(salutation fold is scoped to letter 1 only): {text[:80]!r}"
                )
            ctx.front_divs.append(text)
        return

    if tag == "span" and classes == ["wst-verse", "wst-verse-default"]:
        id_attr = el.get("id") or ""
        m = _MARKER_ID_RE.fullmatch(id_attr)
        if not m:
            raise ValueError(f"letter {letter_n}: malformed section-marker id {id_attr!r}")
        n = int(m.group(1))
        # Raw marker-id sequence, recorded BEFORE the merge/regular split,
        # so _assert_merge_invariant can confirm a declared merge marker is
        # the FINAL raw marker in the letter and immediately follows the
        # section it declares folding into (see module docstring).
        report.setdefault("marker_sequence", {}).setdefault(letter_n, []).append(n)
        if _MERGE_TAIL.get(letter_n) == n:
            if ctx.current is None:
                raise ValueError(
                    f"letter {letter_n}: merge-tail marker {n} has no already-open section to fold into"
                )
            report.setdefault("merges", []).append((letter_n, n, ctx.current))
        else:
            expected_next = (max(ctx.sections) + 1) if ctx.sections else 1
            if n != expected_next:
                raise ValueError(
                    f"letter {letter_n}: section marker {n} out of sequence "
                    f"(expected {expected_next})"
                )
            ctx.current = n
            ctx.sections[n] = []
        return  # the marker's own "<sup><b>N.</b></sup>" glyph is never prose

    if tag == "br":
        ctx.append(" ")
        return

    # Generic pass-through: <p>, <i>, <span class="smallcaps">, <span
    # class="wst-lang wst-lang-grc"> (already-Unicode Greek), <div
    # class="wst-block-center">/<div class="wst-size-block wst-fine
    # wst-fine-block"> (centered verse quotations), and the other combos in
    # _ALLOWED_PASSTHROUGH -- keep text, descend into children (mirrors
    # extract_falconer_perseus.py's `_walk`). Anything NOT allowlisted is
    # fatal, not silently flattened into prose (MAJOR 2).
    combo = (tag, frozenset(classes))
    if combo not in _ALLOWED_PASSTHROUGH:
        raise ValueError(
            f"letter {letter_n}: unrecognized element <{tag} class={classes!r}> "
            f"inside prp-pages-output -- not in _ALLOWED_PASSTHROUGH "
            f"(text: {_collapse_ws(el.text_content())[:80]!r})"
        )
    ctx.append(el.text)
    for child in el:
        _walk(child, ctx, letter_n, report)
        ctx.append(child.tail)


def _clean(parts: list[str]) -> str:
    text = _WS_RE.sub(" ", "".join(parts)).strip()
    return _TIGHTEN_RE.sub(r"\1", text)


_RESIDUAL_MARKERS = ("<", ">", "&#", "cite-bracket")


def _parse_letter(letter_n: int, raw_html: str, report: dict) -> dict[int, str]:
    doc = lxml.html.fromstring(raw_html)
    content_divs = doc.xpath('//div[@class="prp-pages-output"]')
    if len(content_divs) != 1:
        raise ValueError(
            f"letter {letter_n}: expected exactly one prp-pages-output div, "
            f"found {len(content_divs)}"
        )
    content = content_divs[0]

    ctx = _Ctx()
    ctx.append(content.text)
    for child in content:
        _walk(child, ctx, letter_n, report)
        ctx.append(child.tail)

    nums = sorted(ctx.sections)
    expected = list(range(1, len(nums) + 1))
    if nums != expected:
        raise ValueError(
            f"letter {letter_n}: section numbers not strictly sequential "
            f"from 1 after merge-fixes -- got {nums}, expected {expected}"
        )
    expected_max = _EXPECTED_SECTIONS[letter_n]
    if len(nums) != expected_max:
        raise ValueError(
            f"letter {letter_n}: expected {expected_max} sections, got {len(nums)}"
        )

    if letter_n == 1:
        if ctx.salutation is None:
            raise ValueError("letter 1: expected salutation div not found")
        ctx.sections[1].insert(0, ctx.salutation + " ")
    elif ctx.salutation is not None:
        raise AssertionError("unreachable: salutation fold is scoped to letter 1 only")

    out: dict[int, str] = {}
    for n in nums:
        text = _clean(ctx.sections[n])
        if not text:
            raise ValueError(f"letter {letter_n} section {n}: empty text")
        for marker in _RESIDUAL_MARKERS:
            if marker in text:
                raise ValueError(
                    f"letter {letter_n} section {n}: un-stripped markup "
                    f"{marker!r} survives in cleaned text: {text[:160]!r}"
                )
        out[n] = text
    return out


def _assert_merge_invariant(report: dict) -> None:
    """Assert Letter 41's declared `_MERGE_TAIL` fold EXACTLY, not just
    performed: exactly one merge event per declared (letter, marker) pair,
    folding into that letter's own declared final section
    (`_EXPECTED_SECTIONS[letter]`), with the marker verified as the FINAL
    raw marker encountered in the letter, immediately following the section
    it folds into. Bidirectional: a declared pair observed zero or >1 times
    is fatal, and any OBSERVED merge with no matching declaration is fatal
    (MAJOR 1 -- previously, removing marker 9 entirely, or duplicating it,
    both silently passed)."""
    merges = report.get("merges", [])
    for letter, marker in _MERGE_TAIL.items():
        matches = [m for m in merges if m[0] == letter and m[1] == marker]
        if len(matches) != 1:
            raise ValueError(
                f"declared merge (letter {letter}, marker {marker}) observed "
                f"{len(matches)} time(s) (expected exactly 1): {matches}"
            )
        into = matches[0][2]
        expected_into = _EXPECTED_SECTIONS[letter]
        if into != expected_into:
            raise ValueError(
                f"declared merge (letter {letter}, marker {marker}) folded "
                f"into section {into}, expected section {expected_into} "
                f"(that letter's own declared final section)"
            )
        seq = report.get("marker_sequence", {}).get(letter, [])
        if len(seq) < 2 or seq[-2:] != [into, marker]:
            raise ValueError(
                f"declared merge (letter {letter}, marker {marker}): marker "
                f"{marker} must be the FINAL raw marker, immediately "
                f"following marker {into} -- got raw marker sequence tail "
                f"{seq[-2:] if len(seq) >= 2 else seq}"
            )

    observed_pairs = {(m[0], m[1]) for m in merges}
    declared_pairs = set(_MERGE_TAIL.items())
    undeclared = observed_pairs - declared_pairs
    if undeclared:
        raise ValueError(f"observed merge(s) with no matching _MERGE_TAIL declaration: {sorted(undeclared)}")


def _assert_salutation_invariant(records: list[dict]) -> None:
    """MINOR 1 fix: assert over ALL final records (not just the front
    `wst-center` divs `_walk` happens to visit) that the salutation occurs
    exactly once, corpus-wide, at the very start of Letter 1 section 1 --
    closing the gap where a salutation-like sentence surfacing in some
    OTHER letter's own body prose would previously have gone unchecked.

    MINOR (Sol re-verification, 2026-07-21): counts TOTAL OCCURRENCES
    (`str.count`, summed across every record), not the number of records
    CONTAINING the phrase -- a single record quoting the salutation twice
    used to still count as "found in 1 record" (`len(hits) == 1`) and pass
    this gate silently."""
    hits = [r for r in records if _SALUTATION in r["text"]]
    total_occurrences = sum(r["text"].count(_SALUTATION) for r in records)
    if total_occurrences != 1:
        raise ValueError(
            f"salutation must occur exactly once corpus-wide, found "
            f"{total_occurrences} occurrence(s) across records: "
            f"{[(r['book'], r['section']) for r in hits]}"
        )
    r = hits[0]
    if not (r["book"] == 1 and r["section"] == 1 and r["text"].startswith(_SALUTATION)):
        raise ValueError(
            f"salutation found at letter {r['book']} section {r['section']}, "
            f"not at the start of letter 1 section 1"
        )


def _assert_final_text_invariants(records: list[dict]) -> None:
    """MINOR 2 fix: rerun the empty-text / residual-markup / salutation
    invariants on the FINAL records, AFTER PATCHES.json application (a
    patch could otherwise introduce an empty string or reintroduce residual
    markup / a stray salutation-like sentence with no re-check)."""
    for r in records:
        text = r["text"]
        if not text.strip():
            raise ValueError(f"letter {r['book']} section {r['section']}: empty text after patches")
        for marker in _RESIDUAL_MARKERS:
            if marker in text:
                raise ValueError(
                    f"letter {r['book']} section {r['section']}: un-stripped "
                    f"markup {marker!r} survives after patches: {text[:160]!r}"
                )
    _assert_salutation_invariant(records)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_integrity() -> dict:
    if not GUMMERE_INTEGRITY.exists():
        raise ValueError(
            f"{GUMMERE_INTEGRITY} not found -- the per-letter/per-page "
            f"integrity manifest is required. Run this script with "
            f"--bootstrap-integrity once, against a verified-good cache, to "
            f"create it (see module docstring's 'Cache integrity' section)."
        )
    return json.loads(GUMMERE_INTEGRITY.read_text(encoding="utf-8"))


def _validate_integrity(html_sha256: dict[int, str], page_quality: dict[str, str]) -> None:
    """BLOCKER (c) + MAJOR 2: bidirectional check of observed per-letter
    rendered-HTML hashes and per-page data-page-quality values against the
    declared baseline -- missing declaration (declared file lacks an
    observed key) is fatal; an observed key absent from the declared file
    is fatal; any value MISMATCH is fatal."""
    declared = _load_integrity()
    declared_html: dict = declared.get("letter_html_sha256", {})
    declared_pages: dict = declared.get("page_quality", {})

    observed_letters = {str(n) for n in html_sha256}
    declared_letters = set(declared_html)
    missing = observed_letters - declared_letters
    if missing:
        raise ValueError(f"integrity manifest missing declared HTML hash for letter(s): {sorted(missing, key=int)}")
    extra = declared_letters - observed_letters
    if extra:
        raise ValueError(f"integrity manifest declares letter(s) never observed: {sorted(extra, key=int)}")
    for n, digest in html_sha256.items():
        want = declared_html[str(n)]
        if digest != want:
            raise ValueError(
                f"letter {n}: rendered-HTML sha256 {digest} does not match "
                f"declared {want} -- content has drifted from the frozen "
                f"extraction; re-verify before accepting"
            )

    observed_pages = set(page_quality)
    declared_pg_keys = set(declared_pages)
    missing_pg = sorted(observed_pages - declared_pg_keys)
    if missing_pg:
        raise ValueError(f"integrity manifest missing declared page-quality for {len(missing_pg)} page(s), e.g. {missing_pg[:3]}")
    extra_pg = sorted(declared_pg_keys - observed_pages)
    if extra_pg:
        raise ValueError(f"integrity manifest declares {len(extra_pg)} page(s) never transcluded, e.g. {extra_pg[:3]}")
    for page, quality in page_quality.items():
        want = declared_pages[page]
        if quality != want:
            raise ValueError(f"page {page!r}: observed data-page-quality={quality!r} does not match declared {want!r}")


def _write_integrity_baseline(html_sha256: dict[int, str], page_quality: dict[str, str]) -> None:
    """BLOCKER fix (Sol re-verification, 2026-07-21): creation-only -- fatal
    if a `gummere.integrity.json` baseline already exists, so
    `--bootstrap-integrity` can never silently re-bootstrap AROUND an
    integrity mismatch a plain (non-bootstrap) run just reported. Delete
    the file deliberately first if a genuine re-bootstrap is intended.
    Written atomically (temp+rename, via `_atomic_write`) so a process
    killed mid-write never leaves a half-written manifest for a later run
    to trust -- see the module docstring's 'Cache integrity' section."""
    if GUMMERE_INTEGRITY.exists():
        raise ValueError(
            f"{GUMMERE_INTEGRITY} already exists -- --bootstrap-integrity is "
            f"creation-only and refuses to overwrite an existing integrity "
            f"baseline (doing so could silently paper over a real integrity "
            f"mismatch). Delete it deliberately first if a re-bootstrap is "
            f"genuinely intended."
        )
    payload = json.dumps(
        {
            "letter_html_sha256": {str(n): html_sha256[n] for n in sorted(html_sha256)},
            "page_quality": dict(sorted(page_quality.items())),
        },
        indent=1,
    ) + "\n"
    _atomic_write(GUMMERE_INTEGRITY, payload)


def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_patches(records: list[dict], patches: list[dict]) -> list[dict]:
    by_key = {f"{r['book']}.{r['section']}": r for r in records}
    for p in patches:
        key = p["key"]
        if key not in by_key:
            raise ValueError(f"PATCHES.json: key {key!r} not found in extraction output")
        text = by_key[key]["text"]
        for old, new in p.get("replace", []):
            count = text.count(old)
            if count != 1:
                raise ValueError(
                    f"PATCHES.json: key {key} 'replace' text matched {count} "
                    f"times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        by_key[key]["text"] = text
    return records


def build(bootstrap_integrity: bool = False) -> tuple[list[dict], dict]:
    report: dict = {}
    if sorted(_LETTER_REVISIONS) != list(range(1, _N_LETTERS + 1)):
        raise ValueError(
            f"_LETTER_REVISIONS must cover exactly 1..{_N_LETTERS}, got "
            f"{sorted(_LETTER_REVISIONS)}"
        )

    all_sections: dict[int, dict[int, str]] = {}
    html_sha256: dict[int, str] = {}
    for n in range(1, _N_LETTERS + 1):
        raw_html = _fetch(n, _LETTER_REVISIONS[n])
        html_sha256[n] = _sha256_hex(raw_html)
        all_sections[n] = _parse_letter(n, raw_html, report)
        time.sleep(0.2)  # be polite to the API (only matters on a cold cache)

    _assert_merge_invariant(report)  # MAJOR 1

    records = [
        {"book": letter, "section": n, "text": all_sections[letter][n]}
        for letter in sorted(all_sections)
        for n in sorted(all_sections[letter])
    ]

    patches = _load_patches()
    records = _apply_patches(records, patches)
    report["n_patches"] = len(patches)
    report["n_records"] = len(records)
    report["n_letters"] = len(all_sections)

    _assert_final_text_invariants(records)  # MINOR 2: after patches

    page_quality = report.get("page_quality", {})
    page_occurrences = report.get("page_occurrences", {})
    report["n_distinct_pages"] = len(page_quality)
    report["n_page_transclusions"] = sum(page_occurrences.values())

    if bootstrap_integrity:
        _write_integrity_baseline(html_sha256, page_quality)
    else:
        _validate_integrity(html_sha256, page_quality)  # BLOCKER (c) + MAJOR 2

    return records, report


def main() -> None:
    bootstrap_integrity = "--bootstrap-integrity" in sys.argv[1:]
    records, report = build(bootstrap_integrity=bootstrap_integrity)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CLEAN.write_text(
        json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT_CLEAN} ({report['n_records']} records, {report['n_letters']} letters)", file=sys.stderr)
    print(f"footnotes excluded: {report.get('n_footnotes', 0)}", file=sys.stderr)
    print(f"patches applied: {report['n_patches']}", file=sys.stderr)
    for merge in report.get("merges", []):
        letter, marker, into = merge
        print(f"  declared merge: letter {letter} marker {marker} folded into section {into}", file=sys.stderr)
    print(
        f"page transclusions: {report['n_page_transclusions']} across "
        f"{report['n_distinct_pages']} distinct pages",
        file=sys.stderr,
    )
    if bootstrap_integrity:
        print(f"wrote integrity baseline: {GUMMERE_INTEGRITY}", file=sys.stderr)
    else:
        print(f"integrity manifest verified: {GUMMERE_INTEGRITY}", file=sys.stderr)


if __name__ == "__main__":
    main()
