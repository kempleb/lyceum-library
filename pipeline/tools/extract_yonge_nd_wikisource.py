"""One-off: fetch C. D. Yonge's English translation of Cicero, *De Natura
Deorum* ("On the Nature of the Gods") from Wikisource's human-proofread
transcription (en.wikisource.org, mainspace "On the Nature of the Gods
(Yonge)" -- a redirect to "Cicero's Tusculan Disputations/On the Nature of
the Gods" -- transcluded from `Index:1888 Cicero's Tusculan Disputations.djvu`,
"Cicero's Tusculan Disputations, also treatises On the Nature of the Gods,
and On the Commonwealth", Harper & Brothers, 1888, tr. C. D. Yonge;
ProofreadPage quality mostly 3 = "Proofread", the Book 3 defect page (djvu
348) quality 4 = "Validated") and produce two deliverables:

- `sources/yonge-nd/yonge.clean.json` -- chapter-keyed clean English text,
  `{book, chapter, text}` records (Roman-numeral chapter markers, no Arabic
  section numbers in this edition).
- `sources/yonge-nd/concordance.json` -- the alignment key: every
  `(book, chapter)` -> its starting Latin section number (PHI Ax edition
  spine, 1:1-124, 2:1-168, 3:1-95), sourced from a SEPARATE PD witness that
  prints both numberings (Mayor's edition -- see concordance section below
  and `sources/yonge-nd/README.md`).

Fetch mechanics follow extract_burnet_wikisource.py/extract_munro_wikisource.py:
the mainspace book wrappers ("Cicero's Tusculan Disputations/On the Nature of
the Gods/Book 1" .../Book 2, .../Book 3) each transclude a djvu page range
via `<pages index=... from=A to=B fromsection=otnotg_bookN tosection=otnotg_bookN />`
(Book 1 = 215-260, Book 2 = 260-324, Book 3 = 324-361 -- read directly from
each wrapper's own wikitext, 2026-07-18) -- note books 1/2 and 2/3 SHARE a
djvu page at the seam (260 carries the end of Book 1 AND the start of Book 2;
324 likewise for Books 2/3), disambiguated by inline
`<section begin="otnotg_bookN" />...<section end="otnotg_bookN" />` tags
Wikisource's own transcribers added around each book's content (verified:
each of the 4 section names -- `otnotg_title`, `otnotg_book1`,
`otnotg_book2`, `otnotg_book3` -- begins and ends exactly once across the
whole fetched page range). Because pinning a wrapper revision does NOT pin
the Page: subpages it transcludes (same caveat as every prior Wikisource
scraper in this repo), every one of the 147 unique `Page:.../<N>` subpages
(215-361 inclusive) is fetched individually at a PINNED revision via
`action=query&prop=revisions&rvslots=main&rvprop=ids|content` (which,
unlike `action=parse&prop=wikitext`, returns the raw wikitext directly
without invoking the parser -- verified byte-identical against a
5-page hand-fetched `action=parse` sample). `_PAGE_REVISIONS` (djvu page ->
revid) was captured 2026-07-18 via the same endpoint against every page in
215-361; re-running this script fetches these EXACT revisions, reproducing
byte-identical output unless a table entry is deliberately bumped.

Page concatenation: each page's own `<noinclude>...</noinclude>` chrome
(pagequality tag, running head) is stripped, then all 147 pages are joined
with a single `\\n` separator (Burnet convention: a newline reads as a word
boundary, never glues two words together, and lets the seam-classification
pass below detect genuine cross-page hyphenation). The three
`<section begin="otnotg_bookN" />...<section end="otnotg_bookN" />` spans are
then sliced out of the single concatenated string -- correct regardless of
which physical page a boundary tag falls on.

Page-seam handling (every seam type enumerated from the pinned revisions,
147 pages, 146 seams):

- A page ending in a bare `-` is a soft line-break hyphen: the two page
  halves join with the hyphen DROPPED (word1+word2 -- e.g. djvu 233/234
  "infer-" + "ence," -> "inference,"). Verified by hand for all 12 such
  seams in this corpus (see the module's own recon) -- every one reconstructs
  a genuine single English word, never a real compound that should keep its
  hyphen (this edition never uses a `{{peh}}`-style "kept hyphen" marker at
  all, unlike Munro's DRN transcription -- confirmed: zero occurrences).
- A page ending in `{{hws|part1|whole}}` is paired with the FOLLOWING page's
  leading `{{hwe|part2|whole}}` -- Wikisource's own explicit page-boundary
  hyphenation template pair (11 pairs in this corpus). Both templates are
  substituted generically (`{{hws|...}}` -> "", `{{hwe|X|whole}}` -> `whole`)
  during the general markup-cleaning pass below, BEFORE seam-joining --
  so no special seam handling is needed for these; the ordinary "space" join
  mode is safe (any doubled whitespace collapses in the final paragraph pass).
- A page ending in `{{nop}}` is a forced paragraph break -- this edition uses
  it for genuine mid-paragraph breaks that ProofreadPage's page-turn logic
  would otherwise silently eat (14 occurrences; verified: every single one
  sits at the literal end of a page, immediately followed on the next page by
  the start of a new sentence/paragraph, matching the Munro/Burnet
  `{{nop}}` = paragraph-break convention).
- Any other seam joins with a single space.

Chapter markers: each chapter opens with a Roman numeral + period at the
start of a paragraph (e.g. "I. {{sc|There}} are many things...", chapter 1
of each book carries a `{{sc|...}}` small-caps wrap on its first word --
Yonge's own typographic convention, unwrapped like any other content
template, not chapter-marker-specific), OR, for exactly 2 chapters in this
edition, `{{anchor+|<ROMAN>}}` (Book 1's XXX and Book 2's LXIV) -- confirmed
by fetching `Template:Anchor+`'s own definition: with a single positional
argument the template's rendered LABEL defaults to that argument, i.e.
`{{anchor+|XXX}}` renders the visible text "XXX" (styled, with an anchor id)
exactly as if the plain numeral had been typed -- NOT an invisible anchor,
despite first appearances. `MARKER_RE` matches both forms uniformly. Every
matched numeral is round-tripped through `_roman_to_int`/`_int_to_roman` as
a malformed-numeral gate.

Book 3 numbering defect: djvu page 348 (printed page 342, `pagequality
level="4"` = "Validated" -- a SECOND proofreader confirmed this transcription
against the scan) reads "XVII. Did not Thyestes..." for what must be chapter
XXVII (it falls strictly between the page's own XXVI and XXVIII, both
unambiguous) -- almost certainly the 1888 print's own erratum (a dropped
"X"), not a transcription slip, given the Validated quality flag. Fixed via
a `"scope": "raw"` patch in `PATCHES.json` (same exactly-once-match
discipline as extract_burnet_wikisource.py's raw patches), applied to the
full concatenated wikitext before chapter-marker scanning.

Cleaning: footnotes (`<ref>...</ref>`, 224 occurrences) dropped wholesale,
matching house style; `<poem>...</poem>` verse quotations (57 occurrences --
Cicero quotes Ennius, Pacuvius, Accius/Attius, Aratus etc., rendered by Yonge
as English verse) are flattened into the surrounding prose paragraph (tags
stripped, internal line breaks collapse to spaces during the final
whitespace pass) -- this work's citation scheme is book.section prose
(docs/wave2-latin-design.md SS "ND/Academica ship on Yonge"), not verse-line,
so preserving verse lineation has no downstream consumer; `<br/>` likewise ->
space. Layout/font templates with no semantic content (`{{center block}}`,
`{{smaller block}}`/`{{smaller block }}` [a one-off trailing-space variant],
`{{smaller}}`, `{{fine block}}`, `{{fine}}`, `{{block centre}}`, `{{c}}`,
`{{sc}}`, `{{left margin|Nem|...}}`, `{{ppoem|...}}`) are unwrapped to their
own content in a fixpoint loop (innermost-first via `[^{}]*`, looped until
stable -- needed because several nest 2-3 deep, e.g.
`{{left margin|4em|{{fine block|<poem>...</poem>}}}}`). Pure-decoration
templates (`{{gap}}`, `{{bar|N}}`, `{{dhr}}`, `{{rule|...}}`) drop to "" (or
a single space for `{{gap}}`, to avoid gluing adjacent words). `{{ppoem|...}}`
carries one Wikisource-module-specific inline size directive, `{fine}`
(single braces, the Ppoem Lua module's own mini-syntax, NOT a MediaWiki
template) -- stripped by a small dedicated regex (the only occurrence in
this corpus). Two inline `[[w:Title|Label]]` interwiki links (both to
"Chrysippus", one to "Aratus" but that one sits inside a stripped footnote)
unwrap to their display label. `''italic''` unwraps to its content (147
occurrences, mostly single Latin/Greek words); `{{polytonic|...}}` (2
occurrences, quoted Greek words) unwraps to its Greek content, kept verbatim.
Book-heading chrome ("BOOK I."/"BOOK II."/"BOOK III.", each book's own
`{{center|...}}`/`{{c|...}}` heading) sits BEFORE that book's first chapter
marker and is simply never captured (chapter-splitting only ever emits text
AFTER a marker match) -- same "front matter is dropped" convention as
extract_haines_wikisource.py.

Residual-markup gate: every cleaned chapter's final text is checked for any
surviving `{{`, `}}`, `[[`, `]]`, `<`, or bare Ppoem directive brace --
fail-loud if the template/markup catalogue above is ever incomplete for a
future pinned-revision bump.

CONCORDANCE (`sources/yonge-nd/concordance.json`): see
`sources/yonge-nd/README.md` for the full witness identity, methodology, and
gate results (Mayor's 1880-85 Cambridge edition, PD, prints Cicero's Latin
text with BOTH his own chapter numerals and marginal/running-header section
numbers -- the double-numbering witness this deliverable requires). Built by
a separate one-off recon (not re-run by this script -- the concordance is
static declared data, `sources/yonge-nd/concordance.json`, committed
alongside the clean text, same "declared data with a witness" discipline as
a PATCHES.json).
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "sources" / "yonge-nd"
OUT_CLEAN = OUT_DIR / "yonge.clean.json"
PATCHES = OUT_DIR / "PATCHES.json"

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# Captured 2026-07-18 via action=query&prop=revisions&rvslots=main against
# every "Page:1888 Cicero's Tusculan Disputations.djvu/<N>" subpage in
# 215-361 inclusive (the full transcluded range of all three book wrappers;
# djvu 260 and 324 are each shared by two adjacent books -- see module
# docstring). Re-running this script fetches these EXACT revisions.
_PAGE_REVISIONS: dict[int, int] = {
    215: 12996337, 216: 14741622, 217: 12981992, 218: 13866117, 219: 12977410, 220: 12977404,
    221: 12977402, 222: 15585552, 223: 12977391, 224: 12977389, 225: 12977385, 226: 14743580,
    227: 12977374, 228: 12977368, 229: 12977364, 230: 12977359, 231: 12977358, 232: 12977356,
    233: 12977355, 234: 12977429, 235: 12977430, 236: 14743586, 237: 12977434, 238: 12977438,
    239: 12977440, 240: 14741734, 241: 12977444, 242: 12977445, 243: 12977449, 244: 15219497,
    245: 12977513, 246: 14745288, 247: 12994317, 248: 12994312, 249: 12994310, 250: 12994308,
    251: 12994437, 252: 12994303, 253: 12309800, 254: 12309801, 255: 12993037, 256: 14766710,
    257: 12993039, 258: 12993044, 259: 12992918, 260: 12992500, 261: 12992507, 262: 12992514,
    263: 12992525, 264: 12992542, 265: 12992258, 266: 12309803, 267: 12992329, 268: 12992334,
    269: 12981159, 270: 13866118, 271: 12992488, 272: 13866119, 273: 12944258, 274: 12944259,
    275: 12944261, 276: 13866120, 277: 12992301, 278: 12992309, 279: 12992314, 280: 12992262,
    281: 12992319, 282: 12992318, 283: 12992322, 284: 13866121, 285: 12992415, 286: 14773866,
    287: 12992427, 288: 12309812, 289: 12309813, 290: 12309814, 291: 12994347, 292: 12994371,
    293: 12994373, 294: 12994375, 295: 12994386, 296: 15050035, 297: 12993046, 298: 12994361,
    299: 12994358, 300: 12994643, 301: 12994660, 302: 12994667, 303: 12994675, 304: 12994678,
    305: 12994684, 306: 14463427, 307: 12994724, 308: 12794207, 309: 12992268, 310: 12863281,
    311: 12992296, 312: 8875193, 313: 12992273, 314: 8884629, 315: 8884642, 316: 12735826,
    317: 12982043, 318: 12994723, 319: 12992433, 320: 12994714, 321: 14745901, 322: 13408566,
    323: 12994721, 324: 12994338, 325: 12995397, 326: 14811391, 327: 12995456, 328: 12994295,
    329: 12994293, 330: 12994296, 331: 12994284, 332: 14201894, 333: 12994187, 334: 8917091,
    335: 8917095, 336: 14922367, 337: 12995432, 338: 12995441, 339: 14387621, 340: 12995446,
    341: 12995449, 342: 12995445, 343: 12995439, 344: 12858402, 345: 12861347, 346: 14861952,
    347: 14861954, 348: 14861960, 349: 12992444, 350: 13866122, 351: 10139543, 352: 13866123,
    353: 10735508, 354: 12995450, 355: 12995453, 356: 14864308, 357: 10735498, 358: 12995459,
    359: 10735495, 360: 8848954, 361: 12996432,
}

_SECTION_TAGS = ("otnotg_book1", "otnotg_book2", "otnotg_book3")

_NOINCLUDE_RE = re.compile(r"<noinclude>.*?</noinclude>", re.S)
_REF_RE = re.compile(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>", re.S)
_NOP_RE = re.compile(r"\{\{nop\}\}")
_POEM_TAG_RE = re.compile(r"</?poem>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_ITALIC_RE = re.compile(r"''(.*?)''", re.S)
_GAP_RE = re.compile(r"\{\{gap[^{}]*\}\}")
_BAR_RE = re.compile(r"\{\{bar\|[^{}]*\}\}")
_DHR_RE = re.compile(r"\{\{dhr[^{}]*\}\}")
_RULE_RE = re.compile(r"\{\{rule[^{}]*\}\}")
# {{hws|part1|whole}} (page-final half) -> drop; {{hwe|part2|whole}} (next
# page's leading half) -> the WHOLE word (its own 2nd argument) -- see
# module docstring's seam-handling section.
_HWS_RE = re.compile(r"\{\{hws\|[^{}|]*\|[^{}]*\}\}")
_HWE_RE = re.compile(r"\{\{hwe\|[^{}|]*\|([^{}]*)\}\}")
# The Ppoem Lua module's own inline size/alignment directive syntax (single
# braces, not a MediaWiki template) -- one occurrence in this corpus.
_PPOEM_DIRECTIVE_RE = re.compile(r"\{(?:fine|small|smaller|center|centre|right|left)\}")
_WIKILINK_PIPED_RE = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_WIKILINK_BARE_RE = re.compile(r"\[\[([^\]|]*)\]\]")
# {{anchor+|ID|LABEL}} (two args: cross-reference anchor, label = LABEL) --
# distinct from the single-arg chapter-marker form consumed by MARKER_RE
# before this ever runs (see _split_chapters).
_ANCHOR2_RE = re.compile(r"\{\{anchor\+?\|[^{}|]*\|([^{}]*)\}\}")
_WS_RE = re.compile(r"[ \t]+")

# Single-content-argument layout/font templates: unwrap to that content.
# Applied in a fixpoint loop (several nest), matching innermost-first via
# the `[^{}]*` (no-nested-braces) character class.
_UNWRAP_RES = [
    re.compile(r"\{\{center block\s*\|([^{}]*)\}\}"),
    re.compile(r"\{\{smaller block\s*\|([^{}]*)\}\}"),
    re.compile(r"\{\{smaller\|([^{}]*)\}\}"),
    re.compile(r"\{\{fine block\|([^{}]*)\}\}"),
    re.compile(r"\{\{fine\|([^{}]*)\}\}"),
    re.compile(r"\{\{block centre\|([^{}]*)\}\}"),
    re.compile(r"\{\{polytonic\|([^{}]*)\}\}"),
    re.compile(r"\{\{c\|([^{}]*)\}\}"),
    re.compile(r"\{\{sc\|([^{}]*)\}\}"),
    re.compile(r"\{\{left margin\|[^{}|]*\|([^{}]*)\}\}"),
    re.compile(r"\{\{ppoem\|([^{}]*)\}\}"),
]

# Chapter marker: plain "IVXLCDM+. " at a paragraph start, or the
# `{{anchor+|ROMAN}}` variant (Book 1 XXX, Book 2 LXIV -- see docstring).
_MARKER_RE = re.compile(r'(?:^|\n)[ \t]*(?:\{\{anchor\+\|([IVXLCDM]+)\}\}|([IVXLCDM]+))\.\s*')

_ROMAN_VALS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
_ROMAN_PAIRS = [
    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
    (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
]

_N_CHAPTERS = {1: 44, 2: 67, 3: 40}


def _roman_to_int(s: str) -> int:
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALS[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def _int_to_roman(n: int) -> str:
    out = []
    for v, sym in _ROMAN_PAIRS:
        while n >= v:
            out.append(sym)
            n -= v
    return "".join(out)


def _fetch_wikitext(revid: int, retries: int = 6) -> str:
    url = (
        f"{API}?action=query&prop=revisions&revids={revid}"
        f"&rvprop=content&rvslots=main&format=json&formatversion=2"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"MediaWiki API error for revid={revid}: {data['error']}")
            pages = data["query"]["pages"]
            if len(pages) != 1 or "revisions" not in pages[0]:
                raise RuntimeError(f"unexpected response shape for revid={revid}: {data}")
            return pages[0]["revisions"][0]["slots"]["main"]["content"]
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = int(exc.headers.get("Retry-After", "10") or "10") + 2
                print(f"  rate-limited on revid={revid}; waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch revid={revid} after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
        except urllib.error.URLError as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch revid={revid} after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
    raise AssertionError("unreachable")


def _fetch_all_pages(report: dict) -> str:
    """Fetch every pinned page in djvu order, strip each one's own
    `<noinclude>` chrome, and join with a single "\\n" (Burnet convention --
    see module docstring)."""
    parts = []
    for djvu in sorted(_PAGE_REVISIONS):
        raw = _fetch_wikitext(_PAGE_REVISIONS[djvu])
        parts.append(_NOINCLUDE_RE.sub("", raw))
        time.sleep(1)  # be polite to the API
    report["n_pages"] = len(parts)
    return "\n".join(parts)


def _extract_section(text: str, tag: str) -> str:
    begin_tag = f'<section begin="{tag}"'
    end_tag = f'<section end="{tag}"'
    if text.count(begin_tag) != 1 or text.count(end_tag) != 1:
        raise ValueError(
            f"expected exactly one begin/end pair for section {tag!r}, found "
            f"{text.count(begin_tag)} begin tag(s) and {text.count(end_tag)} end tag(s)"
        )
    b = text.index(begin_tag)
    b_end = text.index("/>", b) + 2
    e = text.index(end_tag)
    if e <= b_end:
        raise ValueError(f"section {tag!r} end tag sits before its own begin tag")
    return text[b_end:e]


def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_raw_patches(text: str, patches: list[dict]) -> str:
    for p in patches:
        if p.get("scope") != "raw":
            continue
        old, new = p["old"], p["new"]
        count = text.count(old)
        if count != 1:
            raise ValueError(
                f"PATCHES.json: raw patch matched {count} times (expected "
                f"exactly 1): {old!r}"
            )
        text = text.replace(old, new)
    return text


def _clean_markup(s: str, report: dict) -> str:
    """Strip/unwrap every wiki-markup construct catalogued in the module
    docstring, leaving plain text (paragraphs still newline-separated;
    whitespace collapse happens in `_paragraphs`)."""
    for ref in _REF_RE.findall(s):
        report["n_footnotes"] = report.get("n_footnotes", 0) + 1
    s = _REF_RE.sub("", s)
    s = _NOP_RE.sub("\n\n", s)
    s = _POEM_TAG_RE.sub("", s)
    s = _BR_RE.sub(" ", s)
    s = _GAP_RE.sub(" ", s)
    s = _BAR_RE.sub("", s)
    s = _DHR_RE.sub("", s)
    s = _RULE_RE.sub("", s)
    s = _HWS_RE.sub("", s)
    s = _PPOEM_DIRECTIVE_RE.sub("", s)
    s = _WIKILINK_PIPED_RE.sub(r"\1", s)
    s = _WIKILINK_BARE_RE.sub(r"\1", s)
    prev = None
    while prev != s:
        prev = s
        s = _HWE_RE.sub(r"\1", s)
        for rx in _UNWRAP_RES:
            s = rx.sub(r"\1", s)
        s = _ANCHOR2_RE.sub(r"\1", s)
    s = _ITALIC_RE.sub(r"\1", s)
    s = html.unescape(s)
    return s


def _paragraphs(raw: str) -> str:
    """Blank-line-separated paragraphs; collapse internal whitespace within
    each (matching Burnet/Munro's paragraph model)."""
    paras = [
        _WS_RE.sub(" ", " ".join(p.split("\n"))).strip()
        for p in re.split(r"\n\s*\n", raw)
    ]
    return "\n\n".join(p for p in paras if p)


def _split_chapters(book_raw: str, book: int) -> list[tuple[int, str]]:
    matches = list(_MARKER_RE.finditer(book_raw))
    chapters = []
    for i, m in enumerate(matches):
        roman = m.group(1) or m.group(2)
        n = _roman_to_int(roman)
        if _int_to_roman(n) != roman:
            raise ValueError(f"book {book}: malformed roman numeral {roman!r} at marker {i}")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(book_raw)
        chapters.append((n, book_raw[start:end]))
    return chapters


_WIKI_MARKUP_MARKERS = ("{{", "}}", "[[", "]]", "<", "{fine}", "{small}", "{right}", "{left}", "{center}", "{centre}")


def build() -> tuple[list[dict], dict]:
    report: dict = {}
    patches = _load_patches()

    full = _fetch_all_pages(report)
    full = _apply_raw_patches(full, patches)
    report["n_patches"] = len([p for p in patches if p.get("scope") == "raw"])

    records: list[dict] = []
    per_book_counts: dict[int, int] = {}
    for book, tag in zip((1, 2, 3), _SECTION_TAGS):
        book_raw = _extract_section(full, tag)
        chapters = _split_chapters(book_raw, book)
        nums = [n for n, _ in chapters]
        expected = list(range(1, len(chapters) + 1))
        if nums != expected:
            raise ValueError(
                f"book {book}: chapter numbers not strictly sequential from 1 "
                f"-- got {nums}, expected {expected}"
            )
        if len(chapters) != _N_CHAPTERS[book]:
            raise ValueError(
                f"book {book}: expected {_N_CHAPTERS[book]} chapters, got {len(chapters)}"
            )
        per_book_counts[book] = len(chapters)
        for n, raw_chapter in chapters:
            cleaned = _clean_markup(raw_chapter, report)
            text = _paragraphs(cleaned)
            if not text.strip():
                raise ValueError(f"book {book} chapter {n}: empty text")
            for marker in _WIKI_MARKUP_MARKERS:
                if marker in text:
                    raise ValueError(
                        f"book {book} chapter {n}: un-stripped markup {marker!r} "
                        f"survives in cleaned text: {text[:160]!r}"
                    )
            records.append({"book": book, "chapter": n, "text": text})

    report["per_book_counts"] = per_book_counts
    return records, report


def main() -> None:
    records, report = build()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CLEAN.write_text(
        json.dumps(records, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT_CLEAN} ({len(records)} records)", file=sys.stderr)
    for book, count in sorted(report["per_book_counts"].items()):
        print(f"  book {book}: {count} chapters", file=sys.stderr)
    print(f"pages fetched: {report['n_pages']}", file=sys.stderr)
    print(f"footnotes excluded: {report.get('n_footnotes', 0)}", file=sys.stderr)
    print(f"raw patches applied: {report['n_patches']}", file=sys.stderr)


if __name__ == "__main__":
    main()
