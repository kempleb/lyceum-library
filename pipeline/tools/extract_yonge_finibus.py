"""One-off: fetch C. D. Yonge's English translation of Cicero's *De Finibus
Bonorum et Malorum* ("On the Chief Good and Evil") from Wikisource's
human-proofread transcription (en.wikisource.org, "The Academic Questions,
Treatise De Finibus, and Tusculan Disputations" -- George Bell & Sons, 1891,
tr. Charles Duke Yonge -- transcluded from `Index:The academic questions,
treatise de finibus, and Tusculan disputations.djvu`; every one of the 189
pages spanning the five De Finibus books, djvu 134-322, is ProofreadPage
quality level 3 = "Proofread", all by the single proofreader "Pasicles" --
see `sources/yonge-finibus/README.md` for the full witness identity and the
per-page quality audit) and produce:

- `sources/yonge-finibus/yonge.clean.json` -- chapter-keyed clean English
  text, `{book, chapter, text}` records (Roman-numeral chapter markers, same
  shape as `sources/yonge-nd/yonge.clean.json`).

John's standing ruling, 2026-07-24: "use Yonge for now" for this work's
website English (Rackham 1914 -- see `sources/INVENTORY.md`'s existing,
incomplete Rackham *De Finibus* entry -- becomes slot-A later; out of scope
here). NOT in this script's scope: the chapter->PHI-Latin-section
concordance (phase 2) and any manifest/site wiring (phase 3).

## Fetch mechanics (follows extract_yonge_nd_wikisource.py)

The five book wrappers ("De Finibus, a Treatise on the Chief Good and
Evil/Book 1" .../Book 5) each transclude a djvu page range via
`<pages index=... from=A to=B fromsection=dfN tosection=dfN />` (read
directly from each wrapper's own wikitext, 2026-07-24): Book 1 = 134-163,
Book 2 = 164-217, Book 3 = 217-247, Book 4 = 248-281, Book 5 = 281-322 --
books 1/2, 2/3, and 4/5 each SHARE a djvu page at the seam (163/164 do NOT
overlap; 217 is shared by Books 2/3, 281 by Books 4/5), disambiguated the
same way as the ND extractor: Wikisource's own
`<section begin="dfN" />...<section end="dfN" />` tags, each of the five
(`df1`..`df5`) verified to begin and end exactly once across the whole
fetched page range.

Because pinning a wrapper revision does NOT pin the Page: subpages it
transcludes (same caveat as every prior Wikisource scraper in this repo),
every one of the 189 unique `Page:.../<N>` subpages (134-322 inclusive) is
fetched individually at a PINNED revision via
`action=query&prop=revisions&rvslots=main&rvprop=ids|content`.
`_PAGE_REVISIONS` (djvu page -> revid) was captured 2026-07-24 via that
endpoint against every page in 134-322; re-running this script fetches
these EXACT revisions, reproducing byte-identical output unless a table
entry is deliberately bumped. Every one of the 189 pinned revisions carries
`<pagequality level="3" user="Pasicles" />` -- a single proofreader,
already-proofread transcription (never level 1 "not proofread" or level 2
"problematic"); see the README for the full per-page audit.

Page concatenation: each page's own `<noinclude>...</noinclude>` chrome
(pagequality tag, running head) is stripped, then all 189 pages are joined
page by page. Ten page-boundary seams end a page on a bare soft-line-wrap
hyphen (e.g. djvu 152 "...erro-" / djvu 153 "neous opinions..." ->
"...erroneous opinions..."); each was hand-verified (2026-07-24) against
its own next-page continuation to be a genuine single English word split
across the page turn, never a real compound that should keep its hyphen
(this edition, like the ND transcription, never uses a `{{hws}}`/`{{hwe}}`
page-boundary hyphenation template pair here -- confirmed zero
occurrences). Every other seam joins with a single space (a paragraph
newline inside the wikitext is preserved as content, not eaten by the page
join).

## Book-heading chrome and Book 2's unmarked chapter I

Each book's own heading ("{{c|{{larger|{{uc|Second Book Of The Treatise On
The Chief Good And Evil.}}}}}}", optionally followed by
"{{Custom rule|...}}") sits at the very start of that book's `dfN` section
and is stripped by `_HEADING_RE` before chapter-marker scanning (same
"front matter is dropped" convention as extract_yonge_nd_wikisource.py) --
this is a no-op for Books 1, 3, and 5 (whose sections open directly on a
roman-numeral marker, no heading block present at that position) and drops
real heading chrome for Books 2 and 4.

Book 2 is the one book whose first chapter carries NO roman-numeral marker
in the print (confirmed by the pinned, level-3-proofread wikitext, not an
OCR/transcription gap): after its heading is stripped, the section's own
text begins directly with prose ("On this, when both of them fixed their
eyes on me...") and the first marker found is "II." -- Book 1 ends
mid-dialogue and Book 2's opening paragraph is a direct continuation of
that same conversation, evidently why Yonge/Bohn felt no chapter numeral
was needed there. `_split_chapters` detects this (first found marker's
value > 1) and synthesizes chapter 1 from the un-numbered leading span;
every other book's first marker is "I." and needs no synthesis. Expected
chapter counts per book (`_N_CHAPTERS`): Book 1 = 21, Book 2 = 35 (34
numbered + 1 synthesized), Book 3 = 22, Book 4 = 28, Book 5 = 32 -- 138
chapters total.

## Cleaning

Footnotes (`<ref>...</ref>`, 38 occurrences) dropped wholesale, matching
this corpus's house style (Falconer/Miller/Yonge-ND/Yonge-De-Fato all drop
footnotes whole). The one `<poem>...</poem>` verse quotation (Ennius'
"Albucius" lines, quoted with an embedded Greek phrase) is flattened into
surrounding prose exactly like extract_yonge_nd_wikisource.py: the tag is
stripped and internal `<br/>` line breaks (54 occurrences total, mostly
inside `{{center block|{{smaller block|...<br/>...}}}}`-wrapped verse
quotations that this edition does NOT wrap in `<poem>` tags) collapse to a
single space during the final whitespace pass -- this work's citation
scheme is book.chapter prose, not verse-line, so no downstream consumer
needs lineation preserved. Layout/font templates with no semantic content
(`{{center block|...}}`, `{{smaller block|...}}`, `{{smaller|...}}`,
`{{c|...}}`, `{{sc|...}}`) unwrap to their own content in a fixpoint loop
(innermost-first, several nest 2-3 deep). Pure-decoration templates
(`{{gap}}`, `{{dhr}}`, `{{rule|...}}`) drop (`{{gap}}` -> a single space,
to avoid gluing adjacent words; the rest -> ""). Wikisource's own ellipsis
template, `{{...}}` / `{{...|N}}` (6 occurrences, all inside quoted verse
marking a genuine editorial elision, the same textual phenomenon as De
Fato's typeset `* * *` asterisks) normalizes to the ASCII `...` this
corpus already uses for that phenomenon (see `sources/yonge-fato/README.md`
"Declared normalizations" -- same convention, applied here at extraction
time rather than as a later normalization pass, since Wikisource's own
transcribers already encode it as a distinct template rather than literal
asterisks). `''italic''` unwraps to its content (60 occurrences, mostly
single Latin/Greek words or short phrases) -- the Greek itself is native
Unicode in this transcription (not OCR-garbled, unlike the De Fato archive
scan), so no Greek-restoration table is needed here. `&nbsp;` (1
occurrence) normalizes to a plain space via `html.unescape` plus an
explicit `\xa0` -> " " pass.

Residual-markup gate: every cleaned chapter's final text is checked for any
surviving `{{`, `}}`, `[[`, `]]`, or `<` -- fail-loud if the template
catalogue above is ever incomplete for a future pinned-revision bump.
"""
from __future__ import annotations

import html
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import re

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "sources" / "yonge-finibus"
OUT_CLEAN = OUT_DIR / "yonge.clean.json"
PATCHES = OUT_DIR / "PATCHES.json"

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# Captured 2026-07-24 via action=query&prop=revisions&rvslots=main against
# every "Page:The academic questions, treatise de finibus, and Tusculan
# disputations.djvu/<N>" subpage in 134-322 inclusive (the full transcluded
# range of all five book wrappers). Re-running this script fetches these
# EXACT revisions. Every one of these carries `pagequality level="3"`.
_PAGE_REVISIONS: dict[int, int] = {
    134: 13277867, 135: 13001901, 136: 13004431, 137: 13004433, 138: 13004434, 139: 13004435,
    140: 13005749, 141: 13005751, 142: 13005752, 143: 13005754, 144: 13005759, 145: 13005763,
    146: 13005766, 147: 13005767, 148: 13005769, 149: 13005771, 150: 13005773, 151: 13005780,
    152: 13005785, 153: 13005787, 154: 13005788, 155: 13005790, 156: 13005791, 157: 13005794,
    158: 13005797, 159: 13005798, 160: 13005801, 161: 13005803, 162: 13005805, 163: 13277859,
    164: 13277860, 165: 13027016, 166: 13027017, 167: 13027020, 168: 13027022, 169: 13027027,
    170: 13114260, 171: 13114264, 172: 13114272, 173: 13114274, 174: 13114276, 175: 13265304,
    176: 13265305, 177: 13265306, 178: 13265307, 179: 13265308, 180: 13265312, 181: 13265313,
    182: 13281028, 183: 13281027, 184: 13265316, 185: 13266123, 186: 13266127, 187: 13266135,
    188: 13274362, 189: 13274366, 190: 13274370, 191: 13274371, 192: 13274374, 193: 13274375,
    194: 13274378, 195: 13274381, 196: 13274385, 197: 13274386, 198: 13274387, 199: 13274388,
    200: 13274392, 201: 13274393, 202: 13274397, 203: 13274400, 204: 13274401, 205: 13277804,
    206: 13277805, 207: 13277810, 208: 13277811, 209: 13277814, 210: 13277840, 211: 13277831,
    212: 13277833, 213: 13277837, 214: 13277842, 215: 13277846, 216: 13277852, 217: 13277862,
    218: 13280969, 219: 13280971, 220: 13280972, 221: 13280974, 222: 13280978, 223: 13280981,
    224: 13280982, 225: 13280985, 226: 13280988, 227: 13280990, 228: 13280992, 229: 13280993,
    230: 13280995, 231: 13280997, 232: 13280998, 233: 13280999, 234: 13281000, 235: 13281002,
    236: 13281003, 237: 13281004, 238: 13281005, 239: 13281007, 240: 13281008, 241: 13281009,
    242: 13281011, 243: 13281013, 244: 13281014, 245: 13281015, 246: 13281016, 247: 13281018,
    248: 13285324, 249: 13309649, 250: 13309653, 251: 13309656, 252: 13309657, 253: 13309659,
    254: 13309662, 255: 13309668, 256: 13309677, 257: 13309686, 258: 13309695, 259: 13309704,
    260: 13309712, 261: 13309719, 262: 13309724, 263: 13309728, 264: 13309737, 265: 13310942,
    266: 13310943, 267: 13310945, 268: 13310946, 269: 13310947, 270: 13310950, 271: 13310951,
    272: 13310952, 273: 13310954, 274: 13310957, 275: 13310959, 276: 13310962, 277: 13310963,
    278: 13310964, 279: 13310966, 280: 13310967, 281: 13310974, 282: 13311236, 283: 13311238,
    284: 13311240, 285: 13311241, 286: 13311243, 287: 13311245, 288: 13311246, 289: 13311247,
    290: 13311250, 291: 13311252, 292: 13311254, 293: 13311256, 294: 13311258, 295: 13311259,
    296: 13311262, 297: 13311263, 298: 13311265, 299: 13311266, 300: 13311267, 301: 13311269,
    302: 13311272, 303: 13311274, 304: 13311276, 305: 13311278, 306: 13311279, 307: 13311283,
    308: 13311287, 309: 13311289, 310: 13311293, 311: 13311294, 312: 13311296, 313: 13311298,
    314: 13311303, 315: 13311304, 316: 13311305, 317: 13311306, 318: 13311307, 319: 13311308,
    320: 13311310, 321: 13311312, 322: 13311313,
}

_SECTION_TAGS = ("df1", "df2", "df3", "df4", "df5")
_N_CHAPTERS = {1: 21, 2: 35, 3: 22, 4: 28, 5: 32}

_NOINCLUDE_RE = re.compile(r"<noinclude>.*?</noinclude>", re.S)
_REF_RE = re.compile(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>", re.S)
_NOP_RE = re.compile(r"\{\{nop\}\}")
_POEM_TAG_RE = re.compile(r"</?poem>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_ITALIC_RE = re.compile(r"''(.*?)''", re.S)
_GAP_RE = re.compile(r"\{\{gap[^{}]*\}\}")
_DHR_RE = re.compile(r"\{\{dhr[^{}]*\}\}")
_RULE_RE = re.compile(r"\{\{rule[^{}]*\}\}")
_CUSTOM_RULE_RE = re.compile(r"\{\{Custom rule[^{}]*\}\}")
_ELLIPSIS_RE = re.compile(r"\{\{\.\.\.(?:\|[^{}]*)?\}\}")
_WS_RE = re.compile(r"[ \t]+")

# Book-heading chrome sitting before the first chapter marker in a `dfN`
# section (Books 2 and 4 have both parts; Books 3 and 5 have only the
# {{c|{{larger|{{uc|...}}}}}} part; Book 1 has neither -- see docstring).
_HEADING_RE = re.compile(
    r"^(?:\{\{c\|\{\{larger\|\{\{uc\|[^{}]*\}\}\}\}\}\}\s*)?"
    r"(?:\{\{Custom rule\|[^{}]*\}\}\s*)?"
)

# Single-content-argument layout/font templates: unwrap to that content.
# Applied in a fixpoint loop (several nest).
_UNWRAP_RES = [
    re.compile(r"\{\{center block\s*\|([^{}]*)\}\}"),
    re.compile(r"\{\{smaller block\s*\|([^{}]*)\}\}"),
    re.compile(r"\{\{smaller\|([^{}]*)\}\}"),
    re.compile(r"\{\{c\|([^{}]*)\}\}"),
    re.compile(r"\{\{sc\|([^{}]*)\}\}"),
]

# Chapter marker: roman numeral + period at the start of a paragraph.
_MARKER_RE = re.compile(r'(?:^|\n)[ \t]*([IVXLCDM]+)\.\s*')

_ROMAN_VALS = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
_ROMAN_PAIRS = [
    (1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
    (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
]


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


def _check_page_quality(raw: str, djvu: int) -> None:
    m = re.search(r'<pagequality level="(\d)"', raw)
    if not m or m.group(1) != "3":
        level = m.group(1) if m else "MISSING"
        raise ValueError(f"djvu page {djvu}: expected pagequality level 3, found {level!r}")


def _join_pages(parts: list[str]) -> str:
    """Join stripped page bodies. A page ending on a bare soft-line-wrap
    hyphen (word-char immediately before it, not a real "--" dash) joins
    directly to the next page's leading fragment with the hyphen DROPPED
    (10 such seams in this corpus, each hand-verified -- see docstring).
    Every other seam joins with a single newline (preserves in-page
    paragraph breaks as real content)."""
    if not parts:
        return ""
    out = parts[0]
    for nxt in parts[1:]:
        stripped = out.rstrip()
        if (
            stripped.endswith("-")
            and len(stripped) >= 2
            and stripped[-2].isalpha()
            and not stripped.endswith("--")
        ):
            out = stripped[:-1] + nxt.lstrip()
        else:
            out = out + "\n" + nxt
    return out


def _fetch_all_pages(report: dict) -> str:
    parts = []
    for djvu in sorted(_PAGE_REVISIONS):
        raw = _fetch_wikitext(_PAGE_REVISIONS[djvu])
        _check_page_quality(raw, djvu)
        parts.append(_NOINCLUDE_RE.sub("", raw))
        time.sleep(0.3)
    report["n_pages"] = len(parts)
    return _join_pages(parts)


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
    for _ in _REF_RE.findall(s):
        report["n_footnotes"] = report.get("n_footnotes", 0) + 1
    s = _REF_RE.sub("", s)
    s = _NOP_RE.sub("\n\n", s)
    s = _POEM_TAG_RE.sub("", s)
    s = _BR_RE.sub(" ", s)
    s = _GAP_RE.sub(" ", s)
    s = _DHR_RE.sub("", s)
    s = _RULE_RE.sub("", s)
    s = _CUSTOM_RULE_RE.sub("", s)
    for _ in _ELLIPSIS_RE.findall(s):
        report["n_ellipsis"] = report.get("n_ellipsis", 0) + 1
    s = _ELLIPSIS_RE.sub("...", s)
    prev = None
    while prev != s:
        prev = s
        for rx in _UNWRAP_RES:
            s = rx.sub(r"\1", s)
    s = _ITALIC_RE.sub(r"\1", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ")
    return s


def _paragraphs(raw: str) -> str:
    """Blank-line-separated paragraphs; collapse internal whitespace within
    each (matching the ND/De-Fato paragraph model)."""
    paras = [
        _WS_RE.sub(" ", " ".join(p.split("\n"))).strip()
        for p in re.split(r"\n\s*\n", raw)
    ]
    return "\n\n".join(p for p in paras if p)


def _split_chapters(book_raw: str, book: int) -> list[tuple[int, str]]:
    """Strip this book's own heading chrome, then split on roman-numeral
    chapter markers. If the first marker found is not "I." (Book 2's own
    print convention -- its chapter I carries no numeral, see docstring),
    the un-numbered leading span becomes chapter 1."""
    body = _HEADING_RE.sub("", book_raw, count=1)
    matches = list(_MARKER_RE.finditer(body))
    chapters: list[tuple[int, str]] = []
    if matches and _roman_to_int(matches[0].group(1)) > 1:
        chapters.append((1, body[: matches[0].start()]))
    for i, m in enumerate(matches):
        roman = m.group(1)
        n = _roman_to_int(roman)
        if _int_to_roman(n) != roman:
            raise ValueError(f"book {book}: malformed roman numeral {roman!r} at marker {i}")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        chapters.append((n, body[start:end]))
    return chapters


_WIKI_MARKUP_MARKERS = ("{{", "}}", "[[", "]]", "<")


def build() -> tuple[list[dict], dict]:
    report: dict = {}
    patches = _load_patches()

    full = _fetch_all_pages(report)
    full = _apply_raw_patches(full, patches)
    report["n_patches"] = len([p for p in patches if p.get("scope") == "raw"])

    records: list[dict] = []
    per_book_counts: dict[int, int] = {}
    for book, tag in zip((1, 2, 3, 4, 5), _SECTION_TAGS):
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
    print(f"ellipsis templates normalized: {report.get('n_ellipsis', 0)}", file=sys.stderr)
    print(f"raw patches applied: {report['n_patches']}", file=sys.stderr)


if __name__ == "__main__":
    main()
