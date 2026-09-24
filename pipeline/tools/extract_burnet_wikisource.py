"""One-off: fetch John Burnet's *Early Greek Philosophy* (3rd ed., 1920)
translations of Herakleitos (Ch. III), Parmenides (Ch. IV), and Xenophanes
(the second half of Ch. II, "Science and Religion") from
Wikisource's human-proofread transcription (en.wikisource.org,
`Index:Early Greek philosophy by John Burnet, 3rd edition, 1920.djvu`,
ProofreadPage quality 3 = "Proofread" -- one pass short of "Validated") and
produce clean DK-column-keyed JSON maps -- see sources/INVENTORY.md for full
source-verification detail (edition equivalence, witness-diff results,
SHA-256s) and the Haines/Oldfather Wikisource scrapers for the house
playbook this follows.

Fetch mechanics -- deliberately DIFFERENT from Haines/Oldfather's
`action=parse&prop=text` (rendered HTML) approach. Burnet's mainspace
chapter pages ("Early Greek Philosophy/Herakleitos of Ephesos", ".../
Parmenides of Elea") DO exist and DO transclude their Page: range cleanly
(`<pages index=... from=144 to=182 />` / `from=183 to=210` -- verified by
direct fetch, 2026-07-16), but pinning a revision of that WRAPPER page does
not pin the Page: namespace subpages it transcludes (ProofreadPage's
`<pages>` extension tag resolves transclusion live, against whatever the
Page: subpages currently say, regardless of the wrapper's own oldid) --
so, matching the per-subpage revision-pinning already proven necessary by
Haines/Oldfather, this script fetches each of the 39 (Ch. III) + 28 (Ch. IV)
individual `Page:.../<N>` subpages directly, at a PINNED revision, via
`action=parse&oldid=<revid>&prop=wikitext` -- the RAW wikitext of that
specific revision (not rendered HTML; verified byte-identical against a
5-page hand-fetched sample, 2026-07-16). `_HERAKLEITOS_PAGE_REVISIONS` /
`_PARMENIDES_PAGE_REVISIONS` (djvu page number -> revid) were captured
2026-07-16 via `action=query&prop=revisions` against every Page: subpage in
each chapter's range; re-running this script reproduces byte-identical
wikitext unless Wikisource is deliberately re-pointed at a new revision
here. Chapter <-> djvu-page-range correspondence (Ch. III = 144-182,
printed pp. 130-168; Ch. IV = 183-210, printed pp. 169-196) comes from the
book's own Contents page (Page:.../11) cross-checked against both chapter
wrapper pages' own `from=`/`to=` values.

Each Page: subpage's own `<noinclude>...</noinclude>` header/footer chrome
(the `pagequality` tag, `{{Sidenotes begin/end}}`, the running head
`{{rh|...}}`, the printed page number, `{{smallrefs}}`) is stripped before
concatenation; pages are joined with a newline (not the empty string) so
that a fragment whose translation genuinely spans a page break (real case:
DK121/B121, see `_RAW_HERAKLEITOS_DEFECT` below) gets a natural word
boundary rather than two words gluing together across the seam.

Herakleitos (Ch. III): individual fragments are wrapped in
`<section begin="DKn" />...<section end="DKn" />` tags -- added by
Wikisource contributors, keyed to the real Diels-Kranz numbers, NOT by
Burnet himself (his own printed parenthetical numerals, e.g. "(1)", follow
Bywater's 1877 subject-based arrangement, not Diels' -- confirmed directly:
the tags are wildly out of numeric order relative to Burnet's own printed
sequence). `_extract_dk_spans` scans for these tags directly (ignoring the
enclosing `<section begin="HeraFrag">...end="HeraFrag">` wrapper that
brackets the WHOLE fragment listing, itself not DK-prefixed and so simply
never matched). Two systematic irregularities, both real content in the
primary source, not extraction bugs:

- `DK110111` is one Wikisource tag wrapping ONE Burnet translation that
  covers what DK numbers separately as B110 and B111 -- `_MERGED_DK_COLUMNS`
  duplicates its cleaned text under both column keys (same handling as
  Parmenides' combined headings below).
- Letter-suffixed tags are inconsistently cased on Wikisource's side
  (`DK31A`/`DK31B`, `DK5A`/`DK5B`, `DK84A`/`DK84B` alongside lowercase
  `DK49a`/`DK101a`) -- `_normalize_dk_column` lowercases the suffix
  uniformly, per the dk citation scheme's own case-insensitive-input/
  canonical-lowercase contract (docs/wave1b-presocratics-design.md SS2.1).
  B5a/b and B31a/b are NOT in that design memo's own catalogue of the TLG
  spine's lettered columns (only 1a 3a 3b 14a 49a 67a 84a 84b 101a 125a 126a
  126b are listed there) -- both ARE well-attested genuine Diels-Kranz
  sub-fragment splits (B31's fire/sea/earth transformation, quoted by
  Clement in two adjacent excerpts; B5's purification fragment, quoted by
  Origen in two parts), so this script ships them as B5a/B5b/B31a/B31b
  rather than guessing they're extraction noise -- but this is a real
  open question for the Greek-spine side to reconcile (flagged in
  sources/INVENTORY.md and the delivery report): if the TLG spine keeps
  B5/B31 as single undivided columns, `validate_english_source` will
  loudly reject these as keys matching no spine column, exactly the
  "tag errors... fail only at key-set reconciliation" risk the design memo
  itself anticipated (SS Open risk 4).

`DKxx` is Wikisource's own explicit placeholder for "Burnet/Bywater
includes this, but it has no genuine Diels-Kranz B-number" -- the
meticulousness of the surrounding tagging (which correctly assigns every
lettered sub-fragment) makes "Wikisource just hasn't gotten to it yet" an
implausible reading; far more likely these are exactly the
Bywater-arrangement items Diels excluded as spurious/inauthentic that
SS0 of the design memo predicts. FOUR such items were found in Ch. III
(Bywater ordinals 14, 43, 57, 87-89) -- collected in `EXCLUDED_DKXX` for
the caller to report, never emitted as a clean.json key (there is no DK
column to attach them to).

Burnet's own cross-reference notes ("(56) Same as 45.") are NOT wrapped in
any `<section>` tag at all (verified: only one such note exists in Ch. III,
and it carries no DK tag) -- since this scraper only ever captures TAGGED
content, an untagged cross-reference is simply never extracted, which is
the correct behaviour: it duplicates a fragment (DK51/B51, "(45)") that
already has its own real translation elsewhere, so there is no separate DK
column for the note to fill. If a future Wikisource edit ever DOES wrap a
cross-reference inside a real `<section begin="DKn">` tag, the general
mechanism captures it verbatim like any other tagged content -- no special
casing is needed or present (see test_extract_burnet_wikisource.py).

Parmenides (Ch. IV): Wikisource has NOT added per-fragment DK tags here --
only one overall `<section begin="ParmFrag">...end="ParmFrag">` wrapper
brackets the whole fragment listing. Burnet states explicitly, in his own
printed text, "I follow the arrangement of Diels", so `_extract_parmenides_
fragments` locates fragment boundaries by scanning for Burnet's own
centered numeral headings (`{{c|{{fine|(N[, M...])}}}}`) rather than
relying on section tags -- but "the arrangement of Diels" turns out NOT to
mean the DK6 (Diels-Kranz 6th ed., 1951) numbering the TLG spine uses:
Burnet's numerals genuinely ARE the real DK numbers for fr. 1 and 6-19
(verified by content -- e.g. his (6) "It needs must be..." matches DK6
B6's Greek exactly), but for fr. 2-5 they follow Diels' EARLIER
an earlier 1897 edition's numbering instead, which DK6 later
reshuffled. `_PARMENIDES_HEADING_REMAP` (below `_extract_parmenides_
fragments`) corrects exactly this block -- see its own comment for the
full content-match + Burnet-footnote evidence, and sources/INVENTORY.md's
Parmenides coverage note for the concordance table. A heading naming two
numbers ("(4, 5)", "(10, 11)") means Burnet gives ONE continuous
translation covering both DK numbers -- duplicated under both keys (the
REMAPPED keys for "(4, 5)"), same rationale/same open risk as DK110111
above. Fr. 18 is deliberately absent: Burnet's own footnote to fr. 17
explains Diels' fr. 18 is "a retranslation of the Latin hexameters of
Caelius Aurelianus" -- not an original Greek quotation, so Burnet does not
translate it (a genuine edition gap, not a scrape defect).

Boundary-finding is deliberately NOT brace-matching: one heading in the
pinned revisions (fr. 6, Page:.../188) has a transposed-brace transcription
typo (`{{c|{{fine|(6}})}}}}` instead of `{{c|{{fine|(6)}}}}`) that defeats
any reluctant-regex or balanced-brace approach. Since every heading's
literal OPENING text is always exactly `{{c|{{fine|` regardless of how its
closing braces are mangled, and no heading is ever more than a few words
long, `_extract_parmenides_fragments` finds a fragment's content start by
searching for the FIRST `{{fine|` occurring strictly after the heading's
own 11-character opening literal (skipping past the heading's own embedded
`{{fine|` token without needing to know where the heading "ends") -- robust
to the typo by construction, not by patching it.

English side of verse: Burnet's Parmenides translation is CONTINUOUS PROSE
with sparse (every-5th-Diels-line) marginal cross-reference markers
(`{{left sidenote|N}}` / `{{right sidenote|N}}`), not hard-line-broken
verse -- verified directly (a marker sits mid-sentence, between two words
of one flowing clause, with no line break of any kind on either side).
This contradicts docs/wave1b-presocratics-design.md SS3's assumption that
"Burnet prints his Parmenides lineated" and that the DL-epigram verse
STANDOFF machinery (`english.verse`, `{start,end,breaks}` ranges over hard
line boundaries) would be "reused as-is" -- it would not fit what the
primary source actually looks like. What Burnet's markup actually matches
is Oldfather's Discourses `paras` sidecar (also a Loeb-style every-5th
marginal reference number embedded in continuous prose,
oldfather-discourses-paras.json) -- so `_clean_parmenides_fragment` reuses
THAT shape: `burnet-parmenides-paras.json` is `{"<column>": [{"n", "o"},
...]}`, `n` the Diels line number and `o` the character offset into the
column's own clean text where that line's marker used to sit (the marker
digit itself is removed from the running prose, same technique as
Oldfather's `_extract_chapter`). Flagged for the stage1 dk-scheme owner:
whatever renders Parmenides' English side should consume this the way
stage1_book_section_english consumes paras_sidecar, not verse_sidecar.

Fail-loud patch mechanism: sources/burnet-egp/WIKISOURCE-PATCHES.json is a
list of patch objects, `"scope": "raw"` (applied to a whole chapter's
concatenated, noinclude-stripped wikitext BEFORE any span/heading parsing
-- for markup-level defects that would otherwise corrupt section
boundaries) or `"scope": "chunk"` (applied to one already-cleaned column's
final text -- for hand-verified transcription typos, same
exactly-once-match philosophy as Haines'/Oldfather's `_apply_patches`).
Every patch's `old` string must match its target EXACTLY ONCE; a stale
patch (e.g. because a pinned revision bump picked up Wikisource's own fix)
fails the build loudly rather than silently no-op'ing. The one currently
shipped raw patch fixes a genuine Wikisource tagging defect: B121's
`<section end="DK121" />` closes prematurely mid-sentence on Page:.../154,
with a second (correctly-placed) `<section end="DK121" />` on Page:.../155
after the fragment's real continuation -- removing the premature first
close lets the general scan capture the whole two-page fragment up to the
genuine closing tag. See the patch's own `note` for full detail.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT_DIR = Path("../sources/burnet-egp")
OUT_HERAKLEITOS = OUT_DIR / "burnet-heraclitus.clean.json"
OUT_PARMENIDES = OUT_DIR / "burnet-parmenides.clean.json"
OUT_PARMENIDES_PARAS = OUT_DIR / "burnet-parmenides-paras.json"
OUT_XENOPHANES = OUT_DIR / "burnet-xenophanes.clean.json"
OUT_EMPEDOCLES = OUT_DIR / "burnet-empedocles.clean.json"
OUT_EMPEDOCLES_PARAS = OUT_DIR / "burnet-empedocles-paras.json"
# Task #48 (the Burnet English alignment wave): the six untagged works.
OUT_ZENO = OUT_DIR / "burnet-zeno.clean.json"
OUT_MELISSUS = OUT_DIR / "burnet-melissus.clean.json"
OUT_ANAXAGORAS = OUT_DIR / "burnet-anaxagoras.clean.json"
OUT_ANAXIMANDER = OUT_DIR / "burnet-anaximander.clean.json"
OUT_ANAXIMENES = OUT_DIR / "burnet-anaximenes.clean.json"
OUT_LEUCIPPUS = OUT_DIR / "burnet-leucippus.clean.json"
PATCHES = OUT_DIR / "WIKISOURCE-PATCHES.json"

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# Captured 2026-07-16 via action=query&prop=revisions against every
# "Page:Early Greek philosophy by John Burnet, 3rd edition, 1920.djvu/<N>"
# subpage in each chapter's djvu-page range (Ch. III = printed pp. 130-168;
# Ch. IV = printed pp. 169-196 -- see the Index's Contents page,
# Page:.../11, and both chapter wrapper pages' own `from=`/`to=` values).
# Re-running this script fetches these EXACT revisions (raw wikitext via
# action=parse&oldid=<revid>&prop=wikitext), reproducing byte-identical
# output unless a table entry is deliberately bumped.
_HERAKLEITOS_PAGE_REVISIONS: dict[int, int] = {
    144: 8938585, 145: 8931915, 146: 8938459, 147: 8938520, 148: 8939023, 149: 8938873,
    150: 8938874, 151: 8938667, 152: 8939434, 153: 8938831, 154: 8943991, 155: 8968046,
    156: 8928681, 157: 8931954, 158: 8931959, 159: 8931968, 160: 8931972, 161: 8932100,
    162: 8932104, 163: 8932107, 164: 8932113, 165: 8932122, 166: 8932132, 167: 8932141,
    168: 8932142, 169: 8968079, 170: 8932148, 171: 8932152, 172: 8932156, 173: 8932158,
    174: 8932183, 175: 8932178, 176: 8932179, 177: 8932180, 178: 8932189, 179: 8932195,
    180: 8932197, 181: 10233338, 182: 8932200,
}

_PARMENIDES_PAGE_REVISIONS: dict[int, int] = {
    183: 8932949, 184: 8932221, 185: 8937566, 186: 8937641, 187: 9192426, 188: 8937645,
    189: 8937651, 190: 8937656, 191: 8937659, 192: 8937582, 193: 8932233, 194: 8932234,
    195: 8932237, 196: 10684777, 197: 10233361, 198: 8932246, 199: 8932251, 200: 8932253,
    201: 8932306, 202: 10684779, 203: 8932320, 204: 8932328, 205: 8932336, 206: 8932341,
    207: 8932353, 208: 8932354, 209: 8932361, 210: 8932367,
}

# Captured 2026-07-17 the same way, over Chapter II "Science and Religion"'s
# FULL djvu range (94-143 -- the chapter wrapper page's own `<pages from=94
# to=143 />`; printed pp. 80-129). Xenophanes is NOT his own chapter in
# Burnet's arrangement -- Chapter II covers Pythagoras (§§37-54) THEN
# "II. Xenophanes of Kolophon" (§§55-62, printed pp. 112-121) as its second
# half; the Wave 1b task brief's "Ch. II region" pointer, confirmed by
# fetching the Index's own Contents page. Only the Xenophanes portion is
# extracted below (`_XENO_SECTION_HEADING` bounds the scan) -- the
# Pythagoras portion is out of scope for this work and never parsed.
_XENOPHANES_PAGE_REVISIONS: dict[int, int] = {
    94: 8942800, 95: 8928625, 96: 8931789, 97: 8931791, 98: 8931792, 99: 8936188,
    100: 8936191, 101: 11274163, 102: 8936918, 103: 8936921, 104: 8942243, 105: 8942244,
    106: 8942245, 107: 8942246, 108: 8942249, 109: 8942252, 110: 10936184, 111: 8942521,
    112: 8942523, 113: 8942530, 114: 8942536, 115: 8943127, 116: 13360359, 117: 8944234,
    118: 8942680, 119: 8942689, 120: 8942693, 121: 8942695, 122: 8942779, 123: 8942780,
    124: 8937294, 125: 8937295, 126: 8937297, 127: 8943136, 128: 8937690, 129: 8937313,
    130: 8937681, 131: 8937317, 132: 8937683, 133: 8937324, 134: 8937330, 135: 8937685,
    136: 8937344, 137: 8942782, 138: 15517012, 139: 8942787, 140: 8942789, 141: 8942793,
    142: 8942795, 143: 8942797,
}

# Captured 2026-07-17 via action=query&prop=revisions against every Page:
# subpage in Chapter V's FULL djvu range (211-264, per the Index's own
# Contents page: printed pp. 197-250, and the chapter wrapper page's own
# `<pages from=211 to=264 />`) -- Empedokles of Akragas is its OWN chapter
# (unlike Xenophanes' shared half-chapter), matching the Heraclitus/
# Parmenides precedent of one full chapter per author.
_EMPEDOCLES_PAGE_REVISIONS: dict[int, int] = {
    211: 9022998, 212: 8932989, 213: 8932992, 214: 8932993, 215: 8932995, 216: 8933002,
    217: 8937468, 218: 8987119, 219: 8969796, 220: 8937746, 221: 8937505, 222: 8937506,
    223: 8937508, 224: 8937509, 225: 8937757, 226: 8937514, 227: 8937756, 228: 8937515,
    229: 8937517, 230: 8937754, 231: 8937518, 232: 8933026, 233: 8937519, 234: 8937520,
    235: 8937522, 236: 8937524, 237: 8937755, 238: 12834445, 239: 8933039, 240: 8937531,
    241: 8933046, 242: 8933050, 243: 8933057, 244: 8933069, 245: 8933076, 246: 8933082,
    247: 8933091, 248: 8933099, 249: 8933111, 250: 8933114, 251: 8933119, 252: 8933121,
    253: 8933123, 254: 8933127, 255: 8933655, 256: 8933660, 257: 8933698, 258: 8933699,
    259: 8933702, 260: 8933704, 261: 8933708, 262: 8933712, 263: 8933720, 264: 8933722,
}

# Captured 2026-07-17 via action=query&prop=revisions against every Page:
# subpage in Chapter VIII's FULL djvu range (324-343 -- the Index's own
# Contents page gives printed pp. 310-329; the chapter wrapper page's own
# `<pages index=... from=324 to=343 />` confirms it directly, both fetched
# and verified 2026-07-17). "The Younger Eleatics" -- Zeno of Elea (I) and
# Melissos of Samos (II) share this one chapter. Task #48 (the Burnet
# English alignment wave).
_ELEATICS_PAGE_REVISIONS: dict[int, int] = {
    324: 8949380, 325: 8935972, 326: 8928430, 327: 8935976, 328: 8948575, 329: 8935982,
    330: 8944212, 331: 8935987, 332: 8949389, 333: 8944598, 334: 8936000, 335: 8949398,
    336: 8936010, 337: 8936012, 338: 8937546, 339: 8936020, 340: 8936029, 341: 8936049,
    342: 8936065, 343: 8936070,
}

# Captured 2026-07-17 the same way, over Chapter VI's FULL djvu range
# (265-289 -- printed pp. 251-275 per the Index's Contents page; the
# chapter wrapper page's own `<pages from=265 to=289 />` confirms it
# directly). "Anaxagoras of Klazomenai" is its own chapter, matching the
# Heraclitus/Parmenides/Empedokles precedent. Task #48.
_ANAXAGORAS_PAGE_REVISIONS: dict[int, int] = {
    265: 8933728, 266: 8933731, 267: 9023008, 268: 8933735, 269: 8933736, 270: 8933738,
    271: 8933740, 272: 11447081, 273: 11447394, 274: 11444403, 275: 8937448, 276: 8928304,
    277: 8933764, 278: 8933773, 279: 8933776, 280: 8933782, 281: 8933796, 282: 8935928,
    283: 8935931, 284: 8935941, 285: 8935948, 286: 8935952, 287: 8935959, 288: 8949448,
    289: 8935966,
}

# Task #48's micro-pass: hand-curated, exact-anchor extraction (no general
# parser) of three isolated quotations, each pinned individually via
# action=query&prop=revisions on 2026-07-17 -- one djvu page per fragment,
# not a whole chapter's table. Ch. I = "The Milesian School" (djvu 53-93,
# printed 39-79); Ch. IX = "Leukippos of Miletos" (djvu 344-363, printed
# 330-349) -- both cross-checked against the Index's own Contents page and
# each chapter wrapper's own `<pages from=/to=/>` the same way as the two
# chapter-scale tables above. Value is `(djvu_page, revid)`.
_MICRO_PASS_PAGE_REVISIONS: dict[str, tuple[int, int]] = {
    "anaximander_b1": (66, 9923142),
    "anaximenes_b2": (87, 8937159),
    "leucippus_b2": (354, 8949375),
}

_NOINCLUDE_RE = re.compile(r"<noinclude>.*?</noinclude>", re.S)
_ELLIPSIS_RE = re.compile(r"\{\{\.\.\.\}\}")
_NOP_RE = re.compile(r"\{\{nop\}\}")
_SEPARATOR_RE = re.compile(r"\{\{separator[^}]*\}\}")
_REF_RE = re.compile(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>", re.S)
_ITALIC_RE = re.compile(r"''(.*?)''", re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ORDINAL_PREFIX_RE = re.compile(r"^\(\s*\d+[a-z]?(?:\s*[-–,]\s*\d+[a-z]?)*\s*\)\s*")
_SIDENOTE_RE = re.compile(r"\{\{(?:left|right) sidenote\|(\d+)\}\}")
_FINE_SPLIT_RE = re.compile(r"\{\{fine\|(.*?)\}\}", re.S)


def _fetch_wikitext(revid: int, retries: int = 5) -> str:
    url = f"{API}?action=parse&oldid={revid}&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"MediaWiki API error for oldid={revid}: {data['error']}")
            return data["parse"]["wikitext"]["*"]
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch oldid={revid} after {retries} tries: {exc}") from exc
            wait = 2 ** attempt * 2
            print(f"  fetch oldid={revid} failed ({exc}); retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _fetch_chapter_wikitext(page_revisions: dict[int, int]) -> str:
    """Fetch every pinned Page: subpage in djvu-page order, strip each one's
    own `<noinclude>` header/footer chrome, and concatenate with a newline
    separator between pages (NOT the empty string -- see module docstring:
    a fragment whose translation genuinely spans a page break needs that
    seam to read as a word boundary, not glue two words together)."""
    parts = []
    for page_num in sorted(page_revisions):
        revid = page_revisions[page_num]
        wikitext = _fetch_wikitext(revid)
        parts.append(_NOINCLUDE_RE.sub("", wikitext))
        time.sleep(1)  # be polite to the API
    return "\n".join(parts)


def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_raw_patches(text: str, chapter: str, patches: list[dict]) -> str:
    for p in patches:
        if p.get("scope") != "raw" or p.get("chapter") != chapter:
            continue
        old, new = p["old"], p["new"]
        # A patch may never double-apply. Some patches' `new` value contains
        # its own `old` value as a substring (e.g. B22: wrapping a span in
        # section tags leaves the original text intact inside the tags) --
        # for those, re-running the patch would still find exactly one match
        # of `old` (nested inside the already-applied `new`) and silently
        # apply a SECOND time, nesting the tags. Guard exactly that hazard:
        # when `old` is itself contained in `new` (the wrapping shape), a
        # `new` already present in the text is proof the patch already ran.
        # (Patches where `new` merely truncates `old`, e.g. DK121, don't
        # have this hazard -- there `old` is never a substring of `new`, and
        # a genuine first-time `new in text` hit there is just `new` being a
        # prefix of the still-unpatched `old`, not a double-apply signal.)
        if old in new and new in text:
            raise ValueError(
                f"WIKISOURCE-PATCHES.json: raw patch for {chapter!r} already "
                f"applied -- its 'new' text is already present in the source "
                f"(patch must not be double-applied): {new!r}"
            )
        count = text.count(old)
        if count != 1:
            raise ValueError(
                f"WIKISOURCE-PATCHES.json: raw patch for {chapter!r} matched "
                f"{count} times (expected exactly 1): {old!r}"
            )
        text = text.replace(old, new)
    return text


def _apply_chunk_patches(chunks: dict[str, str], chapter: str, patches: list[dict]) -> dict[str, str]:
    for p in patches:
        if p.get("scope") != "chunk" or p.get("chapter") != chapter:
            continue
        column = p["column"]
        if column not in chunks:
            raise ValueError(
                f"WIKISOURCE-PATCHES.json: chunk patch names column {column!r}, "
                f"not present in {chapter} output"
            )
        text = chunks[column]
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"WIKISOURCE-PATCHES.json: {chapter} {column} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        chunks[column] = text
    return chunks


def _strip_common_markup(span: str) -> str:
    """Shared first pass for both chapters: expand the spaced-lacuna
    ellipsis template to its rendered text (verified against fetched HTML:
    `{{...}}` renders as ". . ." -- Burnet's own typographic convention for
    a lacuna), drop the page-layout `{{nop}}`/`{{separator|N}}` templates
    (no textual content), and drop footnotes (`<ref>...</ref>` and
    self-closing `<ref .../>`) wholesale -- same house style as
    extract_haines_wikisource.py/extract_oldfather_wikisource.py, which
    drop Wikisource's footnote apparatus entirely rather than capturing
    it."""
    span = _ELLIPSIS_RE.sub(" . . . ", span)
    span = _NOP_RE.sub("", span)
    span = _SEPARATOR_RE.sub("", span)
    span = _REF_RE.sub("", span)
    return span


def _join_fine_blocks(span: str) -> str:
    """A tagged span can carry more than one `{{fine|...}}` block (Burnet
    sometimes runs two of his own numbered items under one DK tag, e.g.
    Ch. III's "(124)"/"(125)" pair under DK14). `{{...}}` has already been
    expanded (see `_strip_common_markup`) so no nested `{{` survives inside
    a `{{fine|...}}` block, making a reluctant, non-recursive split safe.
    `re.split` with a capturing pattern interleaves the delimiter's own
    captured group with the surrounding non-matching text in document
    order; joining ALL of it (not just the captured groups) preserves
    whatever sits BETWEEN fine blocks too, which matters for Parmenides'
    sidenote sentinels (see `_clean_parmenides_fragment`) -- for
    Herakleitos, the between-block gap is always just whitespace."""
    return "".join(_FINE_SPLIT_RE.split(span))


def _finish_plain_text(text: str) -> str:
    text = _ITALIC_RE.sub(r"\1", text)
    text = _TAG_RE.sub(" ", text)
    import html as _html
    text = _html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


# --- Herakleitos (Ch. III): DK-tag driven -----------------------------------

_DK_BEGIN_RE = re.compile(r'<section begin="(DK[^"]*)"\s*/>')
_DK_COLUMN_RE = re.compile(r"^DK(\d+)([A-Za-z]?)$")

# One Wikisource tag wraps a Burnet translation covering two DK numbers --
# see module docstring.
_MERGED_DK_COLUMNS: dict[str, tuple[str, ...]] = {"DK110111": ("B110", "B111")}

# Two Wikisource tag PAIRS wrap Burnet translations of what DK6 (the TLG
# export's edition, per the Wave 1b design memo) prints as a SINGLE
# undivided column -- resolved by the Wave 1b Heraclitus integration pass
# (2026-07-16) after cross-checking against the Greek spine
# (build/stage1/greek_spine.json): B5's sole role='text' block is the
# word-for-word concatenation of Burnet's DK5A+DK5B translations (Origen's
# two-part purification quotation); B31's TWO role='text' blocks (separated
# by Clement's own paraphrase, itself role='context') match Burnet's
# DK31A/DK31B in order (Clement's two-part fire/sea/earth transformation
# quotation). Diels' 6th edition merged what an earlier edition -- the one
# Wikisource's tagging and Burnet's own 3rd ed. (1920) follow -- numbered as
# split sub-fragments (5a/5b, 31a/31b); these letters are NOT in the design
# memo's catalogue of the TLG spine's genuine lettered columns (49a, 67a,
# 84a/84b, 101a, 125a, 126a/126b), confirming they are a pre-DK6 split, not
# a spine gap. Concatenated with a single space (each half reads as
# continuous quotation in the Greek); each half's own "R. P. NN" locator
# survives verbatim -- no citation invented or dropped.
_CONCAT_MERGE_COLUMNS: dict[str, tuple[str, ...]] = {
    "B5": ("DK5A", "DK5B"),
    "B31": ("DK31A", "DK31B"),
}


def _extract_dk_spans(text: str) -> list[tuple[str, str]]:
    """`[(tag_name, raw_content), ...]` for every `<section begin="DKn">
    ...<section end="DKn">` pair, in document order. Each begin tag is
    paired with the NEAREST following end tag of the exact same name (a
    plain `re.search` from the begin match's end position) -- correct even
    for a name repeated several times in one chapter (`DKxx`, used 4 times
    for 4 unrelated excluded items -- see module docstring), since each
    occurrence's begin/end pair sits together with no interleaving same-name
    tag between them. The chapter-wide `HeraFrag` wrapper is never matched
    (this pattern requires the `DK` prefix)."""
    spans = []
    for m in _DK_BEGIN_RE.finditer(text):
        name = m.group(1)
        start = m.end()
        end_re = re.compile(r'<section end="' + re.escape(name) + r'"\s*/>')
        end_m = end_re.search(text, start)
        if not end_m:
            raise ValueError(f"no matching <section end=\"{name}\" /> found after its begin tag")
        spans.append((name, text[start:end_m.start()]))
    return spans


def _normalize_dk_column(tag_name: str) -> str:
    m = _DK_COLUMN_RE.match(tag_name)
    if not m:
        raise ValueError(f"DK tag {tag_name!r} does not match the expected DK<number><letter?> shape")
    number, suffix = m.group(1), m.group(2).lower()
    return f"B{number}{suffix}"


def _clean_heraclitus_fragment(raw: str) -> str:
    span = _strip_common_markup(raw)
    joined = _join_fine_blocks(span)
    text = _finish_plain_text(joined)
    # Strip Burnet's own leading Bywater-ordinal locator ("(1) ", "(41, 42) ",
    # "(87-89) ") -- purely structural, redundant with the DK column key that
    # is now this fragment's real citation identity (same rationale as
    # Haines/Oldfather dropping their own leading chapter/section numerals).
    return _ORDINAL_PREFIX_RE.sub("", text)


def build_heraclitus(patches: list[dict]) -> tuple[dict[str, str], list[str]]:
    """Returns `(clean_columns, excluded_dkxx_texts)`."""
    raw_text = _fetch_chapter_wikitext(_HERAKLEITOS_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "heraclitus", patches)

    # Reverse index for _CONCAT_MERGE_COLUMNS: source tag name -> target
    # column. A tag landing here is held back from ordinary emission and
    # concatenated with its sibling(s) below instead.
    concat_source_target = {
        tag: target for target, tags in _CONCAT_MERGE_COLUMNS.items() for tag in tags
    }
    concat_parts: dict[str, dict[str, str]] = {t: {} for t in _CONCAT_MERGE_COLUMNS}

    columns: dict[str, str] = {}
    excluded: list[str] = []
    for tag_name, raw_span in _extract_dk_spans(raw_text):
        cleaned = _clean_heraclitus_fragment(raw_span)
        if tag_name == "DKxx":
            excluded.append(cleaned)
            continue
        if tag_name in concat_source_target:
            target = concat_source_target[tag_name]
            if tag_name in concat_parts[target]:
                raise ValueError(
                    f"duplicate Herakleitos tag {tag_name!r} (a "
                    f"_CONCAT_MERGE_COLUMNS source for column {target!r}) -- "
                    f"a second occurrence would silently overwrite the first "
                    f"half already captured"
                )
            concat_parts[target][tag_name] = cleaned
            continue
        keys = _MERGED_DK_COLUMNS.get(tag_name) or (_normalize_dk_column(tag_name),)
        for key in keys:
            if key in columns:
                raise ValueError(f"duplicate Herakleitos column {key!r} (from tag {tag_name!r})")
            columns[key] = cleaned

    for target, source_tags in _CONCAT_MERGE_COLUMNS.items():
        parts = concat_parts[target]
        if not parts:
            continue  # neither half present -- this document/fixture doesn't touch this pair
        missing = [t for t in source_tags if t not in parts]
        if missing:
            raise ValueError(
                f"_CONCAT_MERGE_COLUMNS[{target!r}] expected tag(s) {missing} "
                f"not found in this revision's tagging -- Wikisource's tagging "
                f"may have changed; re-verify before updating the merge table"
            )
        if target in columns:
            raise ValueError(f"duplicate Herakleitos column {target!r} (from concat-merge)")
        columns[target] = " ".join(parts[t] for t in source_tags)

    columns = _apply_chunk_patches(columns, "heraclitus", patches)
    return columns, excluded


# --- Parmenides (Ch. IV): heading-number driven -----------------------------

_PARM_WRAPPER_BEGIN = '<section begin="ParmFrag" />'
_PARM_WRAPPER_END = '<section end="ParmFrag" />'
_PARM_HEADING_OPEN = "{{c|{{fine|("
_PARM_BOUNDARY_RE = re.compile(r"\{\{c\|\{\{")
_PARM_NUMERAL_RE = re.compile(r"\{\{c\|\{\{fine\|\(\s*([0-9][0-9,\s–-]*)")
_PARM_FINE_OPEN_RE = re.compile(r"\{\{fine\|")

# Burnet's own printed numerals for fr. 2, 3, and the combined "(4, 5)"
# heading do NOT identify with the DK6 (Diels-Kranz 6th ed., 1951) numbers
# the TLG spine uses, DESPITE his stated "I follow the arrangement of
# Diels" (see module docstring) -- that statement refers to Diels' EARLIER
# an earlier 1897 edition, which renumbered exactly this one block
# before the later Diels-Kranz 6th edition renumbered it again. Verified
# 2026-07-17, two independent ways:
#   (1) CONTENT match against DK6's Greek (build/export/.../tlg1562002.xml):
#       Burnet's (2) "Look steadfastly with thy mind at things though afar
#       as if they were at hand..." is a translation of DK6 B4's Greek
#       the opening of B4, not B2's; his (3)
#       "It is all one to me where I begin; for I shall come back again
#       there." matches DK6 B5, not B3's; his (4, 5) "Come now, I will tell thee...the
#       only two ways of search...it is the same thing that can be thought
#       and that can be" matches DK6 B2 with B3 embedded as its closing sentence.
#   (2) Burnet's OWN footnote to the "(4, 5)" heading (Wikisource
#       Page:.../187, pinned revid 9192426) cross-references "fr. 4" for
#       that closing sentence (Burnet says it cannot be separated from
#       fragment 4) -- self-
#       consistently confirming his OWN numeral 4 as the old-numbering
#       identity of the "two ways" fragment he is translating right there,
#       not DK6's B4 (the separate "Look steadfastly" fragment two headings
#       earlier).
# Fragments 1, 6-17, 19 (and the genuine 10/11 combined heading) are NOT
# affected -- e.g. Burnet's own (6) "It needs must be that what can be
# spoken and thought is..." matches DK6 B6 exactly, confirming his numeral IS the
# DK6 number from fr. 6 onward. Keyed by the RAW column-key tuple
# `_extract_parmenides_fragments` would otherwise emit (the identity
# reading of Burnet's own printed numeral) -> the CORRECT DK6 column-key
# tuple `build_parmenides` emits instead. See sources/INVENTORY.md's
# Parmenides coverage note for the full concordance table.
_PARMENIDES_HEADING_REMAP: dict[tuple[str, ...], tuple[str, ...]] = {
    ("B2",): ("B4",),
    ("B3",): ("B5",),
    ("B4", "B5"): ("B2", "B3"),
}


def _extract_parmenides_fragments(text: str) -> list[tuple[tuple[str, ...], str]]:
    """`[(column_keys, raw_content), ...]` for each of Burnet's own numbered
    fragments inside the `ParmFrag` wrapper (see module docstring for why
    this parses Burnet's printed numeral headings rather than DK tags, and
    for why boundary-finding does not attempt to locate a heading's own
    closing braces)."""
    begin = text.find(_PARM_WRAPPER_BEGIN)
    end = text.find(_PARM_WRAPPER_END)
    if begin == -1 or end == -1:
        raise ValueError('could not find the "ParmFrag" section wrapper')
    body = text[begin + len(_PARM_WRAPPER_BEGIN):end]

    boundaries = [m.start() for m in _PARM_BOUNDARY_RE.finditer(body)]
    fragments = []
    for i, pos in enumerate(boundaries):
        m = _PARM_NUMERAL_RE.match(body, pos)
        if not m:
            continue  # a non-numeral heading (e.g. "The Way of Truth") -- not a fragment start
        keys = tuple(f"B{n}" for n in re.findall(r"\d+", m.group(1)))
        content_search_from = pos + len(_PARM_HEADING_OPEN)
        fine_m = _PARM_FINE_OPEN_RE.search(body, content_search_from)
        if not fine_m:
            raise ValueError(f"no fragment content found after heading at offset {pos}")
        content_start = fine_m.start()
        content_end = boundaries[i + 1] if i + 1 < len(boundaries) else len(body)
        fragments.append((keys, body[content_start:content_end]))
    return fragments


def _clean_parmenides_fragment(raw: str) -> tuple[str, list[dict]]:
    """Returns `(text, paras)` -- `paras` is `[{"n", "o"}]` over the
    returned text, one entry per `{{left|right sidenote|N}}` marginal
    Diels-line marker (see module docstring: Burnet's Parmenides is
    continuous prose, not hard-lineated verse). Sentinel technique matches
    extract_oldfather_wikisource.py's `_extract_chapter`/`_extract_manual`:
    replace each marker with a null-byte-delimited number BEFORE the final
    whitespace collapse (done once, over the whole string, so the space
    that sat on either side of a marker in the source correctly survives
    on whichever side it was really on), then split on the sentinel and
    record each marker's offset as the length of the text accumulated so
    far (i.e. exactly where its digit used to sit) before dropping it."""
    span = _strip_common_markup(raw)
    span = _SIDENOTE_RE.sub(lambda m: f"\x00{m.group(1)}\x00", span)
    joined = _join_fine_blocks(span)
    joined = _ITALIC_RE.sub(r"\1", joined)
    joined = _TAG_RE.sub(" ", joined)
    import html as _html
    joined = _html.unescape(joined)
    joined = _WS_RE.sub(" ", joined)  # collapse whitespace globally; \x00 bytes untouched

    pieces = joined.split("\x00")
    text_acc = pieces[0]
    paras: list[dict] = []
    for i in range(1, len(pieces), 2):
        paras.append({"n": int(pieces[i]), "o": len(text_acc)})
        if i + 1 < len(pieces):
            text_acc += pieces[i + 1]

    lstripped = text_acc.lstrip()
    trim = len(text_acc) - len(lstripped)
    text_acc = lstripped.rstrip()
    for p in paras:
        p["o"] = max(0, p["o"] - trim)
    return text_acc, paras


def build_parmenides(patches: list[dict]) -> tuple[dict[str, str], dict[str, list[dict]]]:
    raw_text = _fetch_chapter_wikitext(_PARMENIDES_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "parmenides", patches)

    columns: dict[str, str] = {}
    paras_by_column: dict[str, list[dict]] = {}
    remapped_seen: set[tuple[str, ...]] = set()
    for raw_keys, raw_span in _extract_parmenides_fragments(raw_text):
        keys = _PARMENIDES_HEADING_REMAP.get(raw_keys, raw_keys)
        if raw_keys in _PARMENIDES_HEADING_REMAP:
            remapped_seen.add(raw_keys)
        text, paras = _clean_parmenides_fragment(raw_span)
        for key in keys:
            if key in columns:
                raise ValueError(f"duplicate Parmenides column {key!r}")
            columns[key] = text
            if paras:
                paras_by_column[key] = paras

    missing = set(_PARMENIDES_HEADING_REMAP) - remapped_seen
    if missing:
        raise ValueError(
            f"_PARMENIDES_HEADING_REMAP expected Burnet heading(s) "
            f"{sorted(missing)} not found in this revision's printed "
            f"numerals -- Wikisource's heading numbering may have changed; "
            f"re-verify the 2-5 concordance before updating the remap table"
        )

    columns = _apply_chunk_patches(columns, "parmenides", patches)
    return columns, paras_by_column


# --- Xenophanes (Ch. II, second half): heading-number driven ---------------
#
# Same "I give the fragments according to the text and arrangement of
# Diels" heading-numbered listing shape as Parmenides (verified: Burnet's
# own preface sentence, verbatim, immediately before "(1)") -- NOT
# DK-tag-driven like Herakleitos (Wikisource never added per-fragment
# `<section begin="DKn">` tags here; the three `<section begin="XenoFragA/
# B/C">` wrappers found in this chapter are Wikisource's own arbitrary
# editing-section names, not DK identifiers -- confirmed: "XenoFragA"/"C"
# together bracket the whole numbered listing (split across the two, at an
# unrelated internal page-editing boundary), and "XenoFragB" separately
# wraps ONE fragment (see below) quoted early, inside the biographical
# narrative, before the listing even starts).
_XENO_SECTION_HEADING = "Xenophanes of Kolophon"
_XENO_FRAG8_BEGIN = '<section begin="XenoFragB" />'
_XENO_FRAG8_END = '<section end="XenoFragB" />'

# DK6 B22 (Grok review defect G2): Burnet DOES translate it -- "This is the
# sort of thing we should say by the fireside in the winter-time..."
# (content-verified against the source passage) -- introduced two paragraphs
# after B8's own quotation, in the
# SAME biographical-narrative shape ("another poem (fr. 22 = 17 Karst.; R.
# P. 95 a):" immediately before the `{{fine|...}}` block). UNLIKE B8,
# Wikisource never wrapped this quotation in a `<section>` tag of its own
# -- so, to apply the identical content-verified re-attachment discipline,
# a `raw` scope patch in WIKISOURCE-PATCHES.json inserts this module's OWN
# "XenoFragB22" begin/end pair around the exact (content-pinned, matched-
# exactly-once) span before extraction ever runs.
_XENO_FRAG22_BEGIN = '<section begin="XenoFragB22" />'
_XENO_FRAG22_END = '<section end="XenoFragB22" />'

# Any raw, un-stripped MediaWiki template/link markup surviving into a
# CLEANED value is a strong invariant violation -- exactly the shape of the
# real B38 contamination this module's cleaning passes exist to prevent
# ("58.{{right sidenote|The heavenly bodies.}}..." bleeding past an intended
# fragment boundary, Grok review defect G1). Checked both locally (the
# XenoFragB re-attachment below, Sol review blocker S4) and globally (the
# test suite's extractor-wide invariant sweep of every emitted clean.json).
_WIKI_MARKUP_MARKERS = ("{{", "}}", "[[", "]]", "sidenote")


def _contains_wiki_markup(text: str) -> bool:
    return any(marker in text for marker in _WIKI_MARKUP_MARKERS)


# The TRUE end of the numbered fragment listing (Grok review defect G1):
# "XenoFragA"/"C" together bracket the whole listing (module doc above), so
# the LAST heading's content -- which has no following heading to bound it
# against -- must stop at THIS tag, not run to the end of the fetched
# chapter text. Without it, Burnet's own §§58-62 running commentary (which
# follows the listing immediately, still inside the same fetched page
# range, and still starts with raw un-stripped wiki markup like
# "58.{{right sidenote|...}}") silently bled into the last heading's column
# (verified: (38) = B38) as ~11k characters of contamination.
_XENO_LISTING_END = '<section end="XenoFragC" />'

# Numbering check (Wave 1b task brief: "verify per-fragment that Burnet's
# tags/numerals align with the DK6 spine BY CONTENT before identity-keying"
# -- the Parmenides lesson). Verified 2026-07-17 by content match against
# every one of Burnet's 31 headings (build/dist/xenophanes-fragments/
# book-01.json): 29 of 31 identify directly (his (1)-(3), (7), (9)-(38)
# minus gaps ARE the DK6 numbers). Exactly TWO do not, both content-verified
# against the Greek:
#   - Burnet's (4) "Nor would a man mix wine in a cup by pouring out the
#     wine first, but water first and wine on the top of it" translates
#     DK6 B5, not B4's (DK6 B4 -- Pollux's
#     coinage doxography citing "the Lydians, as Xenophanes says" -- carries
#     no macroscopically quotable verse at all, see the fragments
#     manifest's citation.unmarked_columns; Burnet, translating only real
#     verse, has nothing to give it a heading for).
#   - Burnet's (5) "Thou didst send the thigh-bone of a kid and get for it
#     the fat leg of a fatted bull..." translates DK6 B6, not B5's.
# No Burnet heading "(6)" exists at all (the listing jumps (5) -> (7)) --
# his edition's numbering (pre-dating DK6 by three decades, like Diels'
# the 1897 edition Burnet follows for that chapter) evidently
# never assigned a number to the DK6 B4 testimony either, so the shift is
# local to (4)/(5) only: by (7) -- content-verified against DK6 B7 (the
# "dog fragment") directly -- and every heading after it, Burnet's own
# numeral IS the DK6 number again, unshifted. CANON-log-worthy: a second,
# independent instance of the "Burnet's numeral predates DK6" defect class
# the Parmenides pilot first found, confirming it is not a one-off.
_XENOPHANES_NUMERAL_REMAP: dict[tuple[str, ...], tuple[str, ...]] = {
    ("B4",): ("B5",),
    ("B5",): ("B6",),
}

# Burnet's own heading "(8)" is a CROSS-REFERENCE, not a fresh translation
# -- its content is the two words "See p. 114." (verified: Page:.../113,
# revid 8942536), pointing back to the SEPARATE "threescore years and
# seven" quotation he gives earlier, inline in the biographical narrative
# (S:S 55, "He says himself (fr. 8 = 24 Karst.; R. P. 97):"), which IS
# DK6 B8's real text (content-verified against the source passage) -- exactly
# the Herakleitos "(56) Same as
# 45" cross-reference shape (module docstring), except THIS cross-reference
# happens to sit inside a numbered heading in the main listing rather than
# floating free, so it must be explicitly excluded from the heading scan
# (never emitted as B8's content) rather than simply never matching a tag.
# The real translation is separately, reliably bounded by Wikisource's own
# `XenoFragB` tag (`_XENO_FRAG8_BEGIN`/`_END`).
_XENO_CROSSREF_SKIP: frozenset[tuple[str, ...]] = frozenset({("B8",)})


def _extract_xenophanes_fragments(text: str) -> list[tuple[tuple[str, ...], str]]:
    """`[(column_keys, raw_content), ...]` for each of Burnet's own numbered
    fragments in the Xenophanes portion of Chapter II (see module doc for
    why this parses printed numeral headings like Parmenides, not DK tags,
    and why boundary-finding does not attempt to locate a heading's own
    closing braces -- same reasoning, same regexes, reused verbatim).

    The LAST heading in the listing has no FOLLOWING heading to bound its
    content against -- it is bounded instead against `_XENO_LISTING_END`
    (Grok review defect G1: falling back to `len(body)` here let Burnet's
    own post-listing §§58-62 commentary, raw wiki markup included, bleed
    into that column; see that constant's own doc)."""
    start = text.find(_XENO_SECTION_HEADING)
    if start == -1:
        raise ValueError(f"could not find {_XENO_SECTION_HEADING!r} in Chapter II")
    body = text[start:]

    listing_end = body.find(_XENO_LISTING_END)
    if listing_end == -1:
        raise ValueError(
            f"could not find {_XENO_LISTING_END!r} -- the numbered fragment "
            f"listing's own end boundary -- in Chapter II; without it the "
            f"last heading's content cannot be bounded against Burnet's "
            f"own following commentary"
        )

    boundaries = [m.start() for m in _PARM_BOUNDARY_RE.finditer(body)]
    fragments = []
    for i, pos in enumerate(boundaries):
        m = _PARM_NUMERAL_RE.match(body, pos)
        if not m:
            continue  # a non-numeral heading (e.g. "Elegies"/"Satires") -- not a fragment start
        keys = tuple(f"B{n}" for n in re.findall(r"\d+", m.group(1)))
        if keys in _XENO_CROSSREF_SKIP:
            continue  # "(8) See p. 114." -- a cross-reference, not a translation
        content_search_from = pos + len(_PARM_HEADING_OPEN)
        fine_m = _PARM_FINE_OPEN_RE.search(body, content_search_from)
        if not fine_m:
            raise ValueError(f"no fragment content found after heading at offset {pos}")
        content_start = fine_m.start()
        if i + 1 < len(boundaries):
            content_end = boundaries[i + 1]
        else:
            if listing_end < content_start:
                raise ValueError(
                    f"{_XENO_LISTING_END!r} sits BEFORE the last heading's "
                    f"own content start (offset {content_start}) -- the "
                    f"listing's own end tag may have moved; re-verify "
                    f"before trusting this boundary"
                )
            content_end = listing_end
        fragments.append((keys, body[content_start:content_end]))
    return fragments


def _clean_xenophanes_fragment(raw: str) -> str:
    span = _strip_common_markup(raw)
    joined = _join_fine_blocks(span)
    return _finish_plain_text(joined)


def _xeno_reattach_tagged_fragment(raw_text: str, begin_tag: str, end_tag: str, label: str) -> str:
    """Locate, extract, and clean a single `<section begin=.../end=...>`-
    wrapped cross-reference quotation (Sol review blocker S4's hardening,
    shared between DK B8 and B22 -- Grok review defect G2): `.find()` alone
    silently matches only the FIRST occurrence of each tag, so a re-tagging
    slip that duplicated either tag (or a pinned-revision bump that
    introduced a second copy) would otherwise go completely unnoticed and
    re-attach against whichever copy happened to come first. Exactly one
    begin AND exactly one end, begin strictly before end, and the cleaned
    content must be non-empty and free of raw wiki markup -- FATAL
    otherwise, mirroring the Herakleitos DK5A/DK5B duplicate-tag hardening
    above."""
    begin_count = raw_text.count(begin_tag)
    end_count = raw_text.count(end_tag)
    if begin_count != 1 or end_count != 1:
        raise ValueError(
            f"expected exactly one {label} begin/end pair, found "
            f"{begin_count} begin tag(s) and {end_count} end tag(s) -- a "
            f"duplicated or re-tagged span must be reviewed, not silently "
            f"matched against its first occurrence"
        )
    begin_pos = raw_text.find(begin_tag)
    end_pos = raw_text.find(end_tag)
    if end_pos <= begin_pos:
        raise ValueError(f"{label} end tag sits before its own begin tag")
    raw_span = raw_text[begin_pos + len(begin_tag):end_pos]
    text = _clean_xenophanes_fragment(raw_span)
    if not text:
        raise ValueError(f"{label} span cleaned to empty text -- captured content must be non-empty")
    if _contains_wiki_markup(text):
        raise ValueError(f"{label} span still carries un-stripped wiki markup after cleaning: {text[:120]!r}")
    return text


def build_xenophanes(patches: list[dict]) -> dict[str, str]:
    raw_text = _fetch_chapter_wikitext(_XENOPHANES_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "xenophanes", patches)

    columns: dict[str, str] = {}
    remapped_seen: set[tuple[str, ...]] = set()
    for raw_keys, raw_span in _extract_xenophanes_fragments(raw_text):
        keys = _XENOPHANES_NUMERAL_REMAP.get(raw_keys, raw_keys)
        if raw_keys in _XENOPHANES_NUMERAL_REMAP:
            remapped_seen.add(raw_keys)
        text = _clean_xenophanes_fragment(raw_span)
        for key in keys:
            if key in columns:
                raise ValueError(f"duplicate Xenophanes column {key!r}")
            columns[key] = text

    missing = set(_XENOPHANES_NUMERAL_REMAP) - remapped_seen
    if missing:
        raise ValueError(
            f"_XENOPHANES_NUMERAL_REMAP expected Burnet heading(s) "
            f"{sorted(missing)} not found in this revision's printed "
            f"numerals -- Wikisource's heading numbering may have changed; "
            f"re-verify the 4/5 concordance before updating the remap table"
        )

    # Sol review blocker S4 / Grok review defect G2: re-attach both
    # cross-reference quotations (DK B8 via Wikisource's own "XenoFragB"
    # tag, DK B22 via this module's OWN "XenoFragB22" tag -- see that
    # constant's doc) through the SAME hardened, content-verified
    # discipline -- see `_xeno_reattach_tagged_fragment`.
    for column, begin_tag, end_tag, label in (
        ("B8", _XENO_FRAG8_BEGIN, _XENO_FRAG8_END, '"XenoFragB" (DK B8)'),
        ("B22", _XENO_FRAG22_BEGIN, _XENO_FRAG22_END, '"XenoFragB22" (DK B22)'),
    ):
        if column in columns:
            raise ValueError(f"duplicate Xenophanes column {column!r} (heading scan + {label} tag)")
        columns[column] = _xeno_reattach_tagged_fragment(raw_text, begin_tag, end_tag, label)

    columns = _apply_chunk_patches(columns, "xenophanes", patches)
    return columns


# --- Empedokles (Ch. V, its own chapter): heading-number driven, verse ----
#
# Same "I give the remains as they are arranged by Diels" heading-numbered
# listing shape as Parmenides/Xenophanes (Burnet's own preface sentence,
# verbatim, immediately before "(1)") -- one overall
# `<section begin="EmpedFrag" />...end="EmpedFrag" />` wrapper, no
# per-fragment DK tags. Empedokles is its OWN chapter (pp. 197-250, djvu
# 211-264), unlike Xenophanes' shared half-chapter -- matching the
# Heraclitus/Parmenides precedent. Also verse-with-marginal-markers like
# Parmenides (`{{left|right sidenote|N}}` every 5th Diels line, continuous
# prose otherwise, NOT hard-lineated) -- `_clean_empedocles_fragment` reuses
# Parmenides' `paras` sidecar shape unchanged.
#
# NUMBERING (Wave 1b Empedocles task brief: verify per-heading against the
# DK6 spine BY CONTENT before keying -- the Parmenides lesson, now proven a
# THIRD time). Exhaustively content-verified against ~45 of Burnet's 141
# headings, spanning the full range (1)-(148), cross-checked against this
# work's own hand-reviewed Greek verse_text_lines declarations
# (manifests/empedocles-fragments.yaml): from (6) onward, EVERY checked
# heading's numeral IS the DK6 number directly, unshifted -- including
# famous long fragments (17)=B17, (84)=B84, (100)=B100, (112)=B112,
# (115)=B115, (128)=B128, confirming Burnet's own translated OPENING WORDS
# match the Greek exactly. The drift is confined to (3)-(5), the same
# "Burnet's numeral predates DK6" defect class the Parmenides pilot first
# found (its own frr. 2-5) and the Xenophanes pilot confirmed independently
# (its own (4)/(5)) -- a THIRD occurrence, now clearly a systematic
# consequence of Burnet's edition (1920) predating DK6 (1951) by three
# decades, localized to the philosopher's opening lines every time:
#   - Burnet's (4) "But, O ye gods, turn aside from my tongue the madness
#     of those men. Hallow my lips..." translates DK6 B3 --
#     "white-armed Virgin Muse" matches Sextus' B3 witness exactly.
#   - Burnet's (5) "But it is all too much the way of low minds to
#     disbelieve their betters..." translates DK6 B4 exactly.
#   - Burnet's (3) "{{...}} to keep within thy dumb heart" translates only
#     the TAIL clause of that SAME B4 passage -- Clement's
#     own div (TLG n="4") carries an elided PREVIEW quote of this same tail
#     (an abbreviated source-language citation) ahead of the full quotation, which the
#     pre-DK6 numbering Burnet follows apparently numbered separately from
#     the fuller (5); DK6 consolidated both witnesses into ONE column B4.
#     Since (5) already gives the complete, correctly-ordered translation,
#     (3) is a redundant partial duplicate -- DROPPED (never emitted as its
#     own column; no DK column is "(3)" under either numbering, so nothing
#     is lost), rather than fabricating a fictitious extra key for it.
#   - No Burnet heading "(3)" survives under this treatment; DK6 B5 (Plutarch's
#     short fish/silence fragment) has no
#     Burnet heading of its own at all -- content-verified as genuinely
#     un-translated (his listing jumps straight from the (4)/(5) pair to
#     (6), which IS DK6 B6 directly, matching "shining Zeus, life-bringing
#     Hera, Aidoneus and Nestis" against the source passage exactly).
# CANON-log-worthy: a THIRD, independent instance of the "Burnet's numeral
# predates DK6" defect class, confirming it as a recurring, predictable
# shape of this edition (always confined to the opening handful of
# fragments) rather than a one-off.
#
# Combined headings ("(11, 12)", "(30, 31)", "(35, 36)", "(45, 46)",
# "(77–78)", "(103, 104)", "(122, 123)", "(146, 147)") mean Burnet gives ONE
# continuous translation covering multiple DK numbers -- duplicated under
# every key, the DK110111/Parmenides "(4, 5)" precedent -- EXCEPT
# "(77–78)": B78 is not an independently-existing spine column at all (the
# TLG export's own "77,78" div composes ONLY "B77" via this work's
# `citation.compound_n_map` -- see the manifest's own comment), so that
# heading's translation is filed under B77 alone, never duplicated onto a
# nonexistent "B78" key. "(27a)" is an ordinary lettered heading (Burnet's
# own numeral grammar already accommodates a trailing letter, unlike
# Parmenides/Xenophanes' all-numeric headings) -- `_EMPED_NUMERAL_RE`
# extends the shared boundary/heading-open regexes with an optional
# trailing `[a-z]?` per number.
_EMPED_WRAPPER_BEGIN = '<section begin="EmpedFrag" />'
_EMPED_WRAPPER_END = '<section end="EmpedFrag" />'
_EMPED_NUMERAL_RE = re.compile(
    r"\{\{c\|\{\{fine\|\(\s*([0-9]+[a-z]?(?:\s*[,–-]\s*[0-9]+[a-z]?)*)\s*\)"
)
_EMPED_SPLIT_RE = re.compile(r"\s*[,–-]\s*")

# Burnet's own book-part title, inserted as a bare (non-`{{fine|...}}`)
# centered heading between fr. 111 and 112 -- "POEM ON NATURE" ends and
# "PURIFICATIONS" begins exactly there (confirming the TLG export's own
# title-div boundary, "tit,1-111"/"tit,112-153a" -- see the fragments
# manifest's module comment). `_EMPED_NUMERAL_RE`'s boundary scan does not
# recognize it as a fragment start (no `{{fine|(N)}}` numeral), so without
# this strip it rides along as trailing contamination on B111's own content
# (the B38 wiki-markup-bleed defect class the design memo flags).
_EMPED_PART_TITLE_RE = re.compile(r"\{\{c\|PURIFICATIONS\}\}")

_EMPEDOCLES_HEADING_REMAP: dict[tuple[str, ...], tuple[str, ...]] = {
    ("B4",): ("B3",),
    ("B5",): ("B4",),
    ("B77", "B78"): ("B77",),  # B78 has no column of its own -- compound_n_map
}
# Burnet's own heading "(3)" -- see the module comment above: a redundant
# partial duplicate of DK6 B4, superseded by (5)'s complete translation of
# the same passage. Dropped, never emitted as any column's content.
_EMPEDOCLES_DROP: frozenset[tuple[str, ...]] = frozenset({("B3",)})


def _extract_empedocles_fragments(text: str) -> list[tuple[tuple[str, ...], str]]:
    """`[(column_keys, raw_content), ...]` for each of Burnet's own numbered
    fragments inside the `EmpedFrag` wrapper -- same heading-numeral scan as
    `_extract_parmenides_fragments` (identical boundary/heading-open/fine-open
    regexes, reused verbatim), except keyed by `_EMPED_NUMERAL_RE` (accepts a
    trailing letter per number, e.g. "27a") rather than `_PARM_NUMERAL_RE`."""
    begin = text.find(_EMPED_WRAPPER_BEGIN)
    end = text.find(_EMPED_WRAPPER_END)
    if begin == -1 or end == -1:
        raise ValueError('could not find the "EmpedFrag" section wrapper')
    body = text[begin + len(_EMPED_WRAPPER_BEGIN):end]

    boundaries = [m.start() for m in _PARM_BOUNDARY_RE.finditer(body)]
    fragments = []
    for i, pos in enumerate(boundaries):
        m = _EMPED_NUMERAL_RE.match(body, pos)
        if not m:
            continue  # a non-numeral heading -- not a fragment start
        keys = tuple(f"B{piece}" for piece in _EMPED_SPLIT_RE.split(m.group(1)))
        content_search_from = pos + len(_PARM_HEADING_OPEN)
        fine_m = _PARM_FINE_OPEN_RE.search(body, content_search_from)
        if not fine_m:
            raise ValueError(f"no fragment content found after heading at offset {pos}")
        content_start = fine_m.start()
        content_end = boundaries[i + 1] if i + 1 < len(boundaries) else len(body)
        fragments.append((keys, body[content_start:content_end]))
    return fragments


def _clean_empedocles_fragment(raw: str) -> tuple[str, list[dict]]:
    """Returns `(text, paras)` -- identical shape and technique to
    `_clean_parmenides_fragment` (Empedokles' Burnet translation is also
    continuous prose with sparse every-5th-Diels-line marginal sidenotes,
    not hard-lineated verse; verified directly against the fetched
    wikitext, e.g. fr. (2)'s "{{left sidenote|5}}" sits mid-sentence)."""
    span = _strip_common_markup(raw)
    span = _EMPED_PART_TITLE_RE.sub("", span)
    span = _SIDENOTE_RE.sub(lambda m: f"\x00{m.group(1)}\x00", span)
    joined = _join_fine_blocks(span)
    joined = _ITALIC_RE.sub(r"\1", joined)
    joined = _TAG_RE.sub(" ", joined)
    import html as _html
    joined = _html.unescape(joined)
    joined = _WS_RE.sub(" ", joined)

    pieces = joined.split("\x00")
    text_acc = pieces[0]
    paras: list[dict] = []
    for i in range(1, len(pieces), 2):
        paras.append({"n": int(pieces[i]), "o": len(text_acc)})
        if i + 1 < len(pieces):
            text_acc += pieces[i + 1]

    lstripped = text_acc.lstrip()
    trim = len(text_acc) - len(lstripped)
    text_acc = lstripped.rstrip()
    for p in paras:
        p["o"] = max(0, p["o"] - trim)
    return text_acc, paras


def build_empedocles(patches: list[dict]) -> tuple[dict[str, str], dict[str, list[dict]]]:
    raw_text = _fetch_chapter_wikitext(_EMPEDOCLES_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "empedocles", patches)

    columns: dict[str, str] = {}
    paras_by_column: dict[str, list[dict]] = {}
    remapped_seen: set[tuple[str, ...]] = set()
    dropped_seen: set[tuple[str, ...]] = set()
    for raw_keys, raw_span in _extract_empedocles_fragments(raw_text):
        if raw_keys in _EMPEDOCLES_DROP:
            dropped_seen.add(raw_keys)
            continue
        keys = _EMPEDOCLES_HEADING_REMAP.get(raw_keys, raw_keys)
        if raw_keys in _EMPEDOCLES_HEADING_REMAP:
            remapped_seen.add(raw_keys)
        text, paras = _clean_empedocles_fragment(raw_span)
        for key in keys:
            if key in columns:
                raise ValueError(f"duplicate Empedocles column {key!r}")
            columns[key] = text
            if paras:
                paras_by_column[key] = paras

    missing = set(_EMPEDOCLES_HEADING_REMAP) - remapped_seen
    if missing:
        raise ValueError(
            f"_EMPEDOCLES_HEADING_REMAP expected Burnet heading(s) "
            f"{sorted(missing)} not found in this revision's printed "
            f"numerals -- Wikisource's heading numbering may have changed; "
            f"re-verify the 3/4/5 concordance before updating the remap table"
        )
    missing_drop = _EMPEDOCLES_DROP - dropped_seen
    if missing_drop:
        raise ValueError(
            f"_EMPEDOCLES_DROP expected Burnet heading(s) {sorted(missing_drop)} "
            f"not found in this revision's printed numerals -- re-verify "
            f"before trusting the drop"
        )

    columns = _apply_chunk_patches(columns, "empedocles", patches)
    return columns, paras_by_column


# --- The Younger Eleatics (Ch. VIII): Zeno heading-driven, Melissos ordinal-fine ----
#
# Task #48 (the Burnet English alignment wave). Zeno of Elea (I, printed
# S:S154-163) and Melissos of Samos (II, S:S164-170) share this chapter.
# Verified directly against the pinned wikitext, 2026-07-17:
#
# Zeno S:S160 ("The fragments of Zeno himself also show that this was his
# line of argument. I give them according to the arrangement of Diels.")
# introduces THREE fragments as separate `{{c|{{fine|(N)}}}}` headings
# followed by their own `{{fine|...}}` content -- the SAME shape as
# Parmenides/Xenophanes/Empedokles, just with no chapter-wide `<section>`
# wrapper of its own (Wikisource never tagged Zeno's fragments at all).
# Content-verified against the built Greek spine
# (build/dist/zeno-fragments/book-01.json): (1)="If what is had no
# magnitude..." matches B1 directly; (2) matches B2; and (3) matches B3
# -- all three identify 1:1, no numeral-drift here. B4 (Diogenes Laertius
# ix. 72's separate, independent one-sentence aphorism about motion is a GENUINE Burnet
# coverage gap: it is not the content of any of Burnet's four numbered
# S:S163 arguments (see below), and Burnet never quotes it -- declared via
# this work's own `alignment_allow_unmatched`, not an extraction defect.
#
# DANGER, hard-bounded by construction: S:S163 ("Zeno's arguments on the
# subject of motion have been preserved by Aristotle himself... They are as
# follows") introduces Burnet's OWN four-item PARAPHRASE of Aristotle's
# motion testimonia (stadium, Achilles, arrow, moving rows) -- each item is
# an INLINE `{{fine|(N) ...}}` block with NO separate `{{c|{{fine|(N)}}}}`
# heading of its own (verified: "{{fine|(1) You cannot cross a
# race-course...}}", not "{{c|{{fine|(1)}}}}" + a following block). Content
# check: the arrow argument, S:S163's (3), reads close to B4's Greek in
# theme (both deny motion) but B4's actual source is Diogenes Laertius, not
# Aristotle's ''Physics'' -- confirmed NOT the same quotation (B4 is a
# short independent maxim; S:S163's (3) is Burnet's own multi-sentence
# paraphrase of Aristotle Z 9's arrow discussion). `_extract_zeno_fragments`
# scans ONLY the literal span between the S:S160 marker and the S:S161
# marker (the very next numbered paragraph) for `{{c|{{fine|` headings --
# S:S163's own inline `{{fine|(N)...}}` shape has no such heading at all, so
# even an unbounded scan would not match it; the explicit S:S160/S:S161
# bound is defense in depth (and the mechanism the required must-fail test
# exercises), not the only thing stopping it.
_ZENO_SECTION_START = "160.{{right sidenote|The Fragments}}"
_ZENO_SECTION_END = "161.{{left sidenote|The unit.}}"


def _extract_zeno_fragments(text: str) -> list[tuple[tuple[str, ...], str]]:
    """`[(column_keys, raw_content), ...]` for Zeno's three S:S160 fragments,
    hard-bounded to the span between the S:S160 and S:S161 paragraph markers
    (see module doc: this keeps S:S163's differently-shaped paraphrase list
    permanently out of reach of this scan, not merely absent from a wider
    one) -- otherwise identical heading-numeral scan to
    `_extract_parmenides_fragments`/`_extract_empedocles_fragments` (same
    boundary/heading-open/fine-open regexes, reused verbatim)."""
    start = text.find(_ZENO_SECTION_START)
    if start == -1:
        raise ValueError(f"could not find {_ZENO_SECTION_START!r}")
    end = text.find(_ZENO_SECTION_END, start)
    if end == -1:
        raise ValueError(f"could not find {_ZENO_SECTION_END!r} after S:S160")
    body = text[start:end]

    boundaries = [m.start() for m in _PARM_BOUNDARY_RE.finditer(body)]
    fragments = []
    for i, pos in enumerate(boundaries):
        m = _PARM_NUMERAL_RE.match(body, pos)
        if not m:
            continue  # a non-numeral heading -- not a fragment start
        keys = tuple(f"B{n}" for n in re.findall(r"\d+", m.group(1)))
        content_search_from = pos + len(_PARM_HEADING_OPEN)
        fine_m = _PARM_FINE_OPEN_RE.search(body, content_search_from)
        if not fine_m:
            raise ValueError(f"no fragment content found after Zeno heading at offset {pos}")
        content_start = fine_m.start()
        content_end = boundaries[i + 1] if i + 1 < len(boundaries) else len(body)
        fragments.append((keys, body[content_start:content_end]))
    return fragments


def _extract_tag_bounded_span(text: str, begin_tag: str, end_tag: str, label: str) -> str:
    """Exactly-one-begin/exactly-one-end whole-listing span extraction (Sol
    review blocker S4's hardening, reused verbatim from
    `_xeno_reattach_tagged_fragment` -- here for a whole fragment-listing
    wrapper, e.g. Melissos' "MelisFrag" or Anaxagoras' "AnaxFrag", rather
    than a single cross-reference quotation)."""
    begin_count = text.count(begin_tag)
    end_count = text.count(end_tag)
    if begin_count != 1 or end_count != 1:
        raise ValueError(
            f"expected exactly one {label} begin/end pair, found "
            f"{begin_count} begin tag(s) and {end_count} end tag(s) -- a "
            f"duplicated or re-tagged span must be reviewed, not silently "
            f"matched against its first occurrence"
        )
    begin_pos = text.find(begin_tag)
    end_pos = text.find(end_tag)
    if end_pos <= begin_pos:
        raise ValueError(f"{label} end tag sits before its own begin tag")
    return text[begin_pos + len(begin_tag):end_pos]


_ORDINAL_FINE_START_RE = re.compile(r"\{\{fine\|\(\s*(\d+[a-z]?)\s*\)")


def _extract_ordinal_fine_fragments(span: str) -> list[tuple[str, str]]:
    """`[(ordinal, raw_content), ...]` for a section-tag-bounded span whose
    fragments are each introduced INLINE as `{{fine|(N) ...}}` (Melissos'
    MelisFrag / Anaxagoras' AnaxFrag span shape -- unlike Parmenides/
    Xenophanes/Empedokles's separate `{{c|{{fine|(N)}}}}` heading blocks,
    there is no standalone heading template here at all: the ordinal sits
    inside the SAME `{{fine|...}}` block as the fragment's own first
    words). A fragment may continue across more than one `{{fine|...}}`
    block (e.g. Anaxagoras (4), (12), (17) each span two or three) --
    content between one ordinal-prefixed start and the next belongs to the
    SAME fragment, exactly like Herakleitos' multi-`{{fine|}}` DK spans.
    Melissos' own "(1''a'')" wiki-italicizes its letter suffix (unlike its
    own plain "(6a)" two fragments later) -- italics are stripped from the
    whole span BEFORE this scan runs so both spellings normalize to the
    same "1a" ordinal string."""
    normalized = _ITALIC_RE.sub(r"\1", span)
    starts = [(m.start(), m.group(1)) for m in _ORDINAL_FINE_START_RE.finditer(normalized)]
    if not starts:
        raise ValueError("no ordinal-prefixed {{fine|(N)...}} blocks found in span")
    fragments = []
    for i, (pos, ordinal) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(normalized)
        fragments.append((ordinal, normalized[pos:end]))
    return fragments


def _clean_ordinal_fine_fragment(raw: str) -> str:
    cleaned = _finish_plain_text(_join_fine_blocks(_strip_common_markup(raw)))
    return _ORDINAL_PREFIX_RE.sub("", cleaned)


_MELISSUS_TAG_BEGIN = '<section begin="MelisFrag" />'
_MELISSUS_TAG_END = '<section end="MelisFrag" />'

# Burnet's own two declared insertions -- both explicit in his own
# footnotes, verified against the pinned Ch. VIII wikitext. Neither has a
# DK column to attach to (melissus-fragments.yaml's spine is an unbroken
# B1-B11) -- declared exclusions, never emitted:
#   - (1a): Burnet's OWN restoration of a passage Diels excised entirely
#     ("It is no longer necessary to discuss the passages which used to
#     appear as frs. 1-5 of Melissos, as it has been proved by A. Pabst
#     that they are merely a paraphrase of the genuine fragments... I still
#     believe, however, that the fragment which I have numbered 1a is
#     genuine.").
#   - (6a): Burnet's OWN interpolation with no Greek original at all ("I
#     have ventured to insert this, though the actual words are nowhere
#     quoted, and it is not in Diels.").
_MELISSUS_EXCLUDED_ORDINALS = frozenset({"1a", "6a"})


def build_eleatics_ch8(patches: list[dict]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Returns `(zeno_columns, melissus_columns, melissus_excluded_texts)`."""
    raw_text = _fetch_chapter_wikitext(_ELEATICS_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "eleatics", patches)

    zeno_columns: dict[str, str] = {}
    for keys, raw_span in _extract_zeno_fragments(raw_text):
        text = _clean_xenophanes_fragment(raw_span)  # shared plain-prose cleaner
        for key in keys:
            if key in zeno_columns:
                raise ValueError(f"duplicate Zeno column {key!r}")
            zeno_columns[key] = text
    zeno_columns = _apply_chunk_patches(zeno_columns, "zeno", patches)

    melissus_span = _extract_tag_bounded_span(
        raw_text, _MELISSUS_TAG_BEGIN, _MELISSUS_TAG_END, '"MelisFrag"'
    )
    melissus_columns: dict[str, str] = {}
    melissus_excluded: list[str] = []
    for ordinal, raw_span in _extract_ordinal_fine_fragments(melissus_span):
        cleaned = _clean_ordinal_fine_fragment(raw_span)
        if ordinal in _MELISSUS_EXCLUDED_ORDINALS:
            melissus_excluded.append(cleaned)
            continue
        key = f"B{ordinal}"
        if key in melissus_columns:
            raise ValueError(f"duplicate Melissus column {key!r}")
        melissus_columns[key] = cleaned

    missing_excl = _MELISSUS_EXCLUDED_ORDINALS - {
        o for o, _ in _extract_ordinal_fine_fragments(melissus_span)
    }
    if missing_excl:
        raise ValueError(
            f"_MELISSUS_EXCLUDED_ORDINALS expected ordinal(s) {sorted(missing_excl)} "
            f"not found in this revision's tagging -- re-verify before trusting the exclusion"
        )
    melissus_columns = _apply_chunk_patches(melissus_columns, "melissus", patches)

    return zeno_columns, melissus_columns, melissus_excluded


# --- Anaxagoras of Klazomenai (Ch. VI, its own chapter): ordinal-fine, tag-bounded --
#
# Task #48. S:S126 ("I give the fragments according to the text and
# arrangement of Diels") introduces the whole listing inside ONE
# `<section begin="AnaxFrag">...end="AnaxFrag">` wrapper -- same
# inline-ordinal `{{fine|(N) ...}}` shape as Melissos above (shared
# `_extract_ordinal_fine_fragments`/`_clean_ordinal_fine_fragment`), not the
# separate-heading shape of Parmenides/Xenophanes/Empedokles.
#
# Content-verified against the built Greek spine
# (build/dist/anaxagoras-fragments/book-01.json, 23 columns: B1-B19, B21,
# B21a, B21b, B22 -- B20 a declared gap, per anaxagoras-fragments.yaml's own
# comment) for EVERY one of Burnet's 24 numbered items: (1)-(19) identify
# directly with B1-B19 (including (1) and (14); Burnet's OWN footnote to
# (14) independently confirms the latter identification).
# (21)/(21a)/(21b)/(22) likewise identify directly with B21/B21a/B21b/B22
# (e.g. (21a) "What appears is a vision of the unseen." matches B21a).
# Burnet's own (20) ("With the
# rise of the Dogstar (?) men begin the harvest...") is the ONE exception:
# it has NO corresponding DK6 column at all -- B20 is Diels' own numbering
# gap, confirmed both by the manifest's comment and by the built spine
# carrying no B20 segment. Given every OTHER numeral in this listing
# identifies 1:1 with its DK column, (20)'s absence is best read as a
# genuine casualty of Burnet's edition (1920) predating DK6 (1951) by three
# decades -- the same defect class already established for Parmenides'/
# Xenophanes'/Empedokles' OPENING fragments, here landing mid-listing
# instead -- not an extraction bug. There is no DK column to attach it to;
# emitting a "B20" key would also fail stage1's validate_english_source
# key-set check outright. Declared exclusion, never emitted.
_ANAXAGORAS_TAG_BEGIN = '<section begin="AnaxFrag" />'
_ANAXAGORAS_TAG_END = '<section end="AnaxFrag" />'
_ANAXAGORAS_EXCLUDED_ORDINALS = frozenset({"20"})


def build_anaxagoras(patches: list[dict]) -> tuple[dict[str, str], list[str]]:
    """Returns `(columns, excluded_texts)`."""
    raw_text = _fetch_chapter_wikitext(_ANAXAGORAS_PAGE_REVISIONS)
    raw_text = _apply_raw_patches(raw_text, "anaxagoras", patches)

    span = _extract_tag_bounded_span(
        raw_text, _ANAXAGORAS_TAG_BEGIN, _ANAXAGORAS_TAG_END, '"AnaxFrag"'
    )
    all_fragments = _extract_ordinal_fine_fragments(span)
    columns: dict[str, str] = {}
    excluded: list[str] = []
    for ordinal, raw_span in all_fragments:
        cleaned = _clean_ordinal_fine_fragment(raw_span)
        if ordinal in _ANAXAGORAS_EXCLUDED_ORDINALS:
            excluded.append(cleaned)
            continue
        key = f"B{ordinal}"
        if key in columns:
            raise ValueError(f"duplicate Anaxagoras column {key!r}")
        columns[key] = cleaned

    missing_excl = _ANAXAGORAS_EXCLUDED_ORDINALS - {o for o, _ in all_fragments}
    if missing_excl:
        raise ValueError(
            f"_ANAXAGORAS_EXCLUDED_ORDINALS expected ordinal(s) {sorted(missing_excl)} "
            f"not found in this revision's tagging -- re-verify before trusting the exclusion"
        )
    columns = _apply_chunk_patches(columns, "anaxagoras", patches)
    return columns, excluded


# --- Micro-pass (task #48): hand-curated exact-anchor extraction, no parser ---
#
# Three isolated quotations from three different untagged chapters (Ch. I
# "The Milesian School", Ch. IX "Leukippos of Miletos"), each pinned to its
# own single djvu page (see `_MICRO_PASS_PAGE_REVISIONS`). No general
# heading/tag scan applies to any of these (they sit alone in running
# biographical/doxographical prose, not inside a fragment listing) -- each
# is extracted by locating a short, literal, English start-phrase anchor
# and asserting it matches EXACTLY ONCE, the same fail-loud discipline as
# WIKISOURCE-PATCHES.json's patches, rather than a hand-transcribed exact
# string (avoids a silent transcription mismatch on this module's own long
# footnotes/em-dashes/curly punctuation).


def _fetch_micro_page(page_num: int, revid: int) -> str:
    return _NOINCLUDE_RE.sub("", _fetch_wikitext(revid))


def _extract_micro_fine_block(page_text: str, start_phrase: str, label: str) -> str:
    """Exact-anchor extraction of a single `{{fine|...}}` block's inner
    content: every `{{fine|...}}` block on the page is located first (safe
    to scan non-greedily -- `_strip_common_markup` runs BEFORE the block
    scan, so any `<ref>...</ref>` or `{{...}}` lacuna template nested
    inside a block is already gone, the same precondition
    `_join_fine_blocks` documents), then filtered to the one block
    CONTAINING `start_phrase` as a substring (not necessarily at its very
    start -- Anaximenes B2's block opens with Burnet's own leading quotation
    mark before the anchor phrase). Fails loudly unless exactly one block
    matches."""
    stripped_page = _strip_common_markup(page_text)
    blocks = re.findall(r"\{\{fine\|(.*?)\}\}", stripped_page, re.S)
    matches = [b for b in blocks if start_phrase in b]
    if len(matches) != 1:
        raise ValueError(
            f"{label}: start-phrase anchor {start_phrase!r} matched "
            f"{len(matches)} fine-block(s) out of {len(blocks)} on this "
            f"page (expected exactly 1) -- re-verify the pinned revision "
            f"before trusting this extraction"
        )
    return matches[0]


def _extract_micro_quoted_span(page_text: str, start_phrase: str, end_phrase: str,
                               label: str) -> str:
    """Exact-anchor extraction of a plain-running-prose quotation (no
    `{{fine|...}}` wrapper -- Leukippos B2's shape), bounded by a literal
    start phrase and end phrase, asserted to match exactly once."""
    stripped_page = _strip_common_markup(page_text)
    pattern = re.compile(re.escape(start_phrase) + r".*?" + re.escape(end_phrase), re.S)
    matches = pattern.findall(stripped_page)
    if len(matches) != 1:
        raise ValueError(
            f"{label}: quoted-span anchor {start_phrase!r}...{end_phrase!r} matched "
            f"{len(matches)} span(s) (expected exactly 1) -- re-verify the "
            f"pinned revision before trusting this extraction"
        )
    return matches[0]


# PHILOLOGICAL FLAG for task #48's Opus pass (not resolved by this script):
# DK6's own marked Greek span for B1
# (build/dist/anaximander-fragments/book-01.json) includes the preceding
# preceding origin-and-destruction clause as part of the SAME quotation that
# ends in the
# "reparation" sentence. Burnet's OWN quotation marks in his printed
# English open only at "as is meet" -- the reparation clause alone --
# treating the preceding clause as his own connective paraphrase, not
# quoted Anaximander; his own footnote makes the disagreement explicit:
# Diels begins the actual quotation earlier, while Burnet says the customary
# blending of quotations with surrounding prose argues against that boundary.
# Extracted here verbatim AS BURNET PRINTS THE WHOLE
# SENTENCE (his own lead-in prose together with his quotation-marked
# clause) -- matching how the general-parser extractors above always
# capture a `{{fine|...}}` span whole rather than sub-selecting inside it.
# The quotation-start boundary itself is a live philological call, left
# for the Opus pass, not resolved here.
_ANAXIMANDER_B1_START = "And into that from which things take their rise"


def build_anaximander_micro(patches: list[dict]) -> dict[str, str]:
    page_num, revid = _MICRO_PASS_PAGE_REVISIONS["anaximander_b1"]
    page_text = _fetch_micro_page(page_num, revid)
    raw = _extract_micro_fine_block(page_text, _ANAXIMANDER_B1_START, "Anaximander B1")
    cleaned = _finish_plain_text(raw)
    return _apply_chunk_patches({"B1": cleaned}, "anaximander", patches)


# The formal `{{fine|...}}`-wrapped quotation (used here) appears once, at
# S:S27's doxographical citation ("Aet. i. 3, 4 (R. P. 24)"); Burnet also
# restates the SAME quotation, slightly reworded and without the "he said"
# interruption, in his own S:S28 running commentary immediately afterward
# ("This argument brings us to an important point in the theory, which is
# attested by the single fragment that has come down to us... 'Just as our
# soul, being air, holds us together, so do breath and air encompass the
# whole world.'") -- the `{{fine|...}}`-wrapped version is used as the
# canonical extracted text, matching the shape of every other
# Burnet-extracted fragment in this module (always a `{{fine|...}}` span).
_ANAXIMENES_B2_START = 'Just as," he said, "our soul'


def build_anaximenes_micro(patches: list[dict]) -> dict[str, str]:
    page_num, revid = _MICRO_PASS_PAGE_REVISIONS["anaximenes_b2"]
    page_text = _fetch_micro_page(page_num, revid)
    raw = _extract_micro_fine_block(page_text, _ANAXIMENES_B2_START, "Anaximenes B2")
    cleaned = _finish_plain_text(raw)
    return _apply_chunk_patches({"B2": cleaned}, "anaximenes", patches)


# Confirmed sitting in Burnet's own MAIN running text at S:S178 ("The only
# fragment of Leukippos which has survived is an express denial of chance.
# 'Naught happens for nothing,' he said, 'but everything from a ground and
# of necessity.'"), not inside a `<ref>...</ref>` footnote (the footnote
# that follows carries only the Greek citation, Aet. i. 25, 4).
_LEUCIPPUS_B2_START = '"Naught happens for nothing,"'
_LEUCIPPUS_B2_END = 'of necessity."'


def build_leucippus_micro(patches: list[dict]) -> dict[str, str]:
    page_num, revid = _MICRO_PASS_PAGE_REVISIONS["leucippus_b2"]
    page_text = _fetch_micro_page(page_num, revid)
    raw = _extract_micro_quoted_span(
        page_text, _LEUCIPPUS_B2_START, _LEUCIPPUS_B2_END, "Leucippus B2"
    )
    cleaned = _finish_plain_text(raw)
    return _apply_chunk_patches({"B2": cleaned}, "leucippus", patches)


def main() -> None:
    patches = _load_patches()

    print("Herakleitos: fetching Ch. III (39 pages)...")
    heraclitus, excluded = build_heraclitus(patches)
    print(f"  {len(heraclitus)} DK columns, {len(excluded)} Burnet/Bywater item(s) with no DK number:")
    for text in excluded:
        print(f"    - {text[:70]!r}")
    OUT_HERAKLEITOS.write_text(
        json.dumps(heraclitus, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_HERAKLEITOS}")

    print("Parmenides: fetching Ch. IV (28 pages)...")
    parmenides, paras = build_parmenides(patches)
    print(f"  {len(parmenides)} DK columns, {len(paras)} with verse-line markers")
    OUT_PARMENIDES.write_text(
        json.dumps(parmenides, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_PARMENIDES}")
    OUT_PARMENIDES_PARAS.write_text(
        json.dumps(paras, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_PARMENIDES_PARAS}")

    print("Xenophanes: fetching Ch. II, second half (50 pages)...")
    xenophanes = build_xenophanes(patches)
    print(f"  {len(xenophanes)} DK columns")
    OUT_XENOPHANES.write_text(
        json.dumps(xenophanes, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_XENOPHANES}")

    print("Empedokles: fetching Ch. V (54 pages)...")
    empedocles, emp_paras = build_empedocles(patches)
    print(f"  {len(empedocles)} DK columns, {len(emp_paras)} with verse-line markers")
    OUT_EMPEDOCLES.write_text(
        json.dumps(empedocles, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_EMPEDOCLES}")
    OUT_EMPEDOCLES_PARAS.write_text(
        json.dumps(emp_paras, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_EMPEDOCLES_PARAS}")

    print("The Younger Eleatics: fetching Ch. VIII (20 pages)...")
    zeno, melissus, melissus_excluded = build_eleatics_ch8(patches)
    print(f"  Zeno: {len(zeno)} DK columns")
    print(f"  Melissus: {len(melissus)} DK columns, {len(melissus_excluded)} "
          f"Burnet insertion(s) with no DK number:")
    for text in melissus_excluded:
        print(f"    - {text[:70]!r}")
    OUT_ZENO.write_text(
        json.dumps(zeno, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_ZENO}")
    OUT_MELISSUS.write_text(
        json.dumps(melissus, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_MELISSUS}")

    print("Anaxagoras: fetching Ch. VI (25 pages)...")
    anaxagoras, anax_excluded = build_anaxagoras(patches)
    print(f"  {len(anaxagoras)} DK columns, {len(anax_excluded)} Burnet item(s) with no DK number:")
    for text in anax_excluded:
        print(f"    - {text[:70]!r}")
    OUT_ANAXAGORAS.write_text(
        json.dumps(anaxagoras, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_ANAXAGORAS}")

    print("Micro-pass: Anaximander B1, Anaximenes B2, Leucippus B2...")
    anaximander = build_anaximander_micro(patches)
    OUT_ANAXIMANDER.write_text(
        json.dumps(anaximander, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_ANAXIMANDER}")
    anaximenes = build_anaximenes_micro(patches)
    OUT_ANAXIMENES.write_text(
        json.dumps(anaximenes, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_ANAXIMENES}")
    leucippus = build_leucippus_micro(patches)
    OUT_LEUCIPPUS.write_text(
        json.dumps(leucippus, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_LEUCIPPUS}")


if __name__ == "__main__":
    main()
