"""One-off: fetch H. A. J. Munro's English prose translation of Lucretius,
*De Rerum Natura* (all six books) from Wikisource's human-proofread
transcription (en.wikisource.org, mainspace "On the Nature of Things
(Munro)", djvu index "On the nature of things (De rerum natura) Translated
with an analysis of the six books by H.A.J. Munro.djvu", ProofreadPage
quality 3 = "Proofread") and produce a clean, line-range-keyed JSON --
`sources/munro-drn/munro.clean.json`. See `sources/munro-drn/README.md`
and sources/INVENTORY.md for edition identity (the scan is the 1907
Routledge (London) reprint -- per the Wikisource Index page's own
metadata, OCLC 1050249224 -- of Munro's unchanged Fourth Edition text,
1886; the scan's prefatory note (J. D. Duff) certifies "The translation
has undergone no change") and the US-PD basis (Munro d. 1885; translation
first published 1864, 4th ed. 1886 -- safely pre-1931).

Fetch mechanics follow extract_burnet_wikisource.py exactly: the mainspace
book wrappers ("On the Nature of Things (Munro)/Book 1" ... "/Book 6") each
transclude a Page: range via `<pages index=... from=A to=B />` (Book 1 =
djvu 70-104, Book 2 = 105-142, Book 3 = 143-177, Book 4 = 178-218, Book 5 =
219-265, Book 6 = 266-308 -- read directly from each wrapper's own
wikitext, 2026-07-17), but pinning a wrapper revision does NOT pin the
Page: subpages it transcludes -- so every one of the 239 Page: subpages is
fetched individually at a PINNED revision via
`action=parse&oldid=<revid>&prop=wikitext` (raw wikitext of that exact
revision). `_PAGE_REVISIONS` (book -> djvu page -> revid) was captured
2026-07-17 via `action=query&prop=revisions` against every subpage in each
book's range; re-running this script reproduces byte-identical output
unless a table entry is deliberately bumped.

Layout of the print (verified against the fetched wikitext of all 239
pages, not assumed):

- The line-range keys are the print's own RUNNING HEADERS: every RECTO
  (odd printed page) carries `{{rvh|<printed page>|...|<start>-<end>|...}}`
  inside its `<noinclude>` chrome, giving the range of Lucretius' Latin
  lines rendered on the open SPREAD (the preceding verso + that recto).
  Versos carry only unfilled `#-#`/`# ` placeholders (checked: no verso in
  any book carries a real range). Printed page number == djvu page - 69
  throughout (gated below). Content-verified for Book 1's first spread:
  the verso djvu 71 begins mid-clause at Latin line 1.23 (a lowercase,
  non-sentence-initial continuation, confirming no paragraph break falls
  there), matching its recto's "23-90".
- One record is emitted per spread: {book, range (as printed), start, end,
  text}. Consecutive spread ranges either abut (…-153 / 154-…) or share
  one straddling boundary line (…-90 / 90-…) -- both accepted by the
  contiguity gate; anything else is reported (real case: Book 3's print
  jumps 60-125 -> 127-189, line 126 falling in neither header).
- Books 1, 4 and 6 OPEN on a recto (printed 1, 109, 197) with no running
  header (book-opening pages carry heading chrome instead) -- that page
  forms a leading singleton record with a DERIVED range 1..(first
  header's start), `"derived": true` (the boundary line straddles into the
  first headered spread, same convention as the print's own shared
  boundary lines). Books 2, 3 and 5 open on a verso, which simply joins
  its recto's first spread. Books 3 and 5 END on a verso (printed 108,
  196) with no following recto header -- a trailing singleton record with
  a DERIVED open-ended range (start = last header's end, end = null).
- "THE ARGUMENT" (Munro's own range-keyed analysis/paraphrase of all six
  books) is front matter, djvu pages 10-68, transcluded by the separate
  mainspace subpage ".../Argument" -- structurally outside every book's
  page range, so it is excluded by construction (never fetched). Gates
  verify the assumption: every book-opening page must carry its
  `{{c|BOOK <numeral>}}` heading, and no included page may contain the
  Argument's running head ("THE ARGUMENT") or its `NNN-NNN:` colon-keyed
  paragraph shape.

Page-seam handling (all seams enumerated from the pinned revisions):

- A page ending in a bare `-` is a soft line-break hyphen: ProofreadPage's
  transclusion convention (and the transcriber's practice here) is that
  the hyphen vanishes and the word halves join directly. 11 such seams.
- A page ending in `{{peh}}` is the transcriber's explicit KEPT hyphen
  (genuine compound split across the page break): join with the hyphen
  restored. 2 such seams ("smooth-polished", "close-packed").
- A page ending in `{{nop}}` marks a paragraph break falling exactly at
  the page boundary: join as a paragraph break. 9 occurrences (several at
  book-final pages, where they are simply trailing chrome).
- Any other seam joins with a single space (sentences flow across pages).
- When a hyphenated word straddles a RECORD boundary (the recto->verso
  seam between two spreads), the completed word is attached to the EARLIER
  record and the remainder of the later page starts the later record --
  same convention as the print's own straddling boundary lines. Every such
  transfer is reported.

Apparatus excluded (each reported at run time): one Wikisource-transcribed
print footnote on djvu 280 (printed 211: `<ref>See note on p. 239.</ref>`);
Munro's own endnote block + the printer's imprint at the tail of djvu 308
(printed 239: "Note to p. 211.--Presteres..." + "PLYMOUTH / WILLIAM
BRENDON AND SON, LTD., PRINTERS"), truncated at a fail-loud anchor.
`{{***|1}}` (Book 1, djvu 71: Munro's own asterisk line marking the
transmitted lacuna after 1.43) is kept as a paragraph of its own, "* * *".

Fail-loud patch mechanism: `sources/munro-drn/PATCHES.json`, same
exact-once shape as sources/miller-de-officiis/PATCHES.json (a list of
{"record": "<book>.<range>", "replace": [[old, new], ...], "note": ...}),
applied to a record's final cleaned text; absent file = no patches. A
stale patch fails the build loudly rather than silently no-op'ing.
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

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "sources" / "munro-drn"
OUT_CLEAN = OUT_DIR / "munro.clean.json"
PATCHES = OUT_DIR / "PATCHES.json"

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# djvu page number == printed page number + this offset, verified against
# every page's own {{rvh|<printed>|...}} first parameter (gated below).
_DJVU_PRINTED_OFFSET = 69

# Captured 2026-07-17 via action=query&prop=revisions against every
# "Page:On the nature of things (De rerum natura) Translated with an
# analysis of the six books by H.A.J. Munro.djvu/<N>" subpage in each
# book's transclusion range (read from each mainspace book wrapper's own
# `<pages from=/to= />`). Re-running fetches these EXACT revisions.
_PAGE_REVISIONS: dict[int, dict[int, int]] = {
    1: {
        70: 15596257, 71: 15596262, 72: 15596264, 73: 15596267, 74: 15596272, 75: 15596273,
        76: 15596278, 77: 15596279, 78: 15596280, 79: 15596282, 80: 15596577, 81: 15596578,
        82: 15596580, 83: 15596581, 84: 15596585, 85: 15596587, 86: 15596589, 87: 15596590,
        88: 15596594, 89: 15596595, 90: 15604393, 91: 15596597, 92: 15596938, 93: 15596939,
        94: 15604391, 95: 15596944, 96: 15604390, 97: 15597006, 98: 15604388, 99: 15597014,
        100: 15597015, 101: 15597018, 102: 15602851, 103: 15597034, 104: 15602850,
    },
    2: {
        105: 15597040, 106: 15597682, 107: 15597044, 108: 15597683, 109: 15597136, 110: 15597684,
        111: 15597139, 112: 15597540, 113: 15597541, 114: 15597543, 115: 15597544, 116: 15597669,
        117: 15597670, 118: 15597671, 119: 15597673, 120: 15597675, 121: 15597676, 122: 15597677,
        123: 15597679, 124: 15597680, 125: 15597681, 126: 15598223, 127: 15598224, 128: 15599462,
        129: 15599464, 130: 15599468, 131: 15599471, 132: 15599473, 133: 15599474, 134: 15599476,
        135: 15599478, 136: 15599479, 137: 15599480, 138: 15599482, 139: 15599484, 140: 15599486,
        141: 15599487, 142: 15599488,
    },
    3: {
        143: 15599494, 144: 15599838, 145: 15599840, 146: 15599842, 147: 15599844, 148: 15601019,
        149: 15601020, 150: 15601021, 151: 15601022, 152: 15601083, 153: 15601084, 154: 15601087,
        155: 15601088, 156: 15601093, 157: 15601094, 158: 15601095, 159: 15601096, 160: 15601141,
        161: 15601145, 162: 15601216, 163: 15601219, 164: 15601220, 165: 15601222, 166: 15601223,
        167: 15601224, 168: 15601226, 169: 15601228, 170: 15601229, 171: 15601231, 172: 15601233,
        173: 15601234, 174: 15601235, 175: 15601236, 176: 15601237, 177: 15601239,
    },
    4: {
        178: 15601240, 179: 15601242, 180: 15601417, 181: 15601420, 182: 15601423, 183: 15601425,
        184: 15601428, 185: 15601431, 186: 15601438, 187: 15601444, 188: 15601447, 189: 15601450,
        190: 15601453, 191: 15601455, 192: 15601458, 193: 15601461, 194: 15601797, 195: 15601799,
        196: 15601800, 197: 15601805, 198: 15601808, 199: 15601810, 200: 15601812, 201: 15601814,
        202: 15601816, 203: 15601818, 204: 15601820, 205: 15601822, 206: 15601823, 207: 15601825,
        208: 15601930, 209: 15601933, 210: 15601934, 211: 15601935, 212: 15601939, 213: 15607882,
        214: 15601945, 215: 15601947, 216: 15601950, 217: 15601952, 218: 15601956,
    },
    5: {
        219: 15601960, 220: 15602804, 221: 15602805, 222: 15602806, 223: 15602808, 224: 15602826,
        225: 15602827, 226: 15602828, 227: 15602829, 228: 15602830, 229: 15602831, 230: 15602835,
        231: 15602836, 232: 15602837, 233: 15602838, 234: 15602839, 235: 15602840, 236: 15602852,
        237: 15602853, 238: 15602854, 239: 15602855, 240: 15604367, 241: 15604368, 242: 15604370,
        243: 15604371, 244: 15604372, 245: 15604373, 246: 15604377, 247: 15604378, 248: 15604380,
        249: 15604381, 250: 15604444, 251: 15604446, 252: 15604447, 253: 15604449, 254: 15604450,
        255: 15604452, 256: 15604454, 257: 15604456, 258: 15604458, 259: 15604459, 260: 15604460,
        261: 15604462, 262: 15604463, 263: 15604466, 264: 15604470, 265: 15604472,
    },
    6: {
        266: 15602833, 267: 15602847, 268: 15602843, 269: 15602848, 270: 15602845, 271: 15602849,
        272: 15604374, 273: 15604375, 274: 15604399, 275: 15604400, 276: 15604512, 277: 15604513,
        278: 15604514, 279: 15604516, 280: 15604518, 281: 15604520, 282: 15604526, 283: 15604531,
        284: 15604532, 285: 15604534, 286: 15604536, 287: 15604538, 288: 15604541, 289: 15604544,
        290: 15604545, 291: 15604547, 292: 15604654, 293: 15604655, 294: 15604656, 295: 15604657,
        296: 15604659, 297: 15604661, 298: 15604663, 299: 15604664, 300: 15604665, 301: 15604666,
        302: 15604667, 303: 15604669, 304: 15604672, 305: 15604673, 306: 15604674, 307: 15604675,
        308: 15604678,
    },
}

# Book-opening djvu pages (no running header; heading chrome instead).
_BOOK_OPENERS = {1: 70, 2: 105, 3: 143, 4: 178, 5: 219, 6: 266}

# Munro's endnote + the printer's imprint trail the translation on the
# work's very last page (djvu 308, printed 239). Truncated at this anchor
# -- fail-loud if the pinned revision no longer contains it exactly once.
_ENDNOTE_PAGE = (6, 308)
_ENDNOTE_ANCHOR = "{{dhr|3}}\n{{fine|Note to p. 211."

_NOINCLUDE_RE = re.compile(r"<noinclude>.*?</noinclude>", re.S)
_REF_RE = re.compile(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref>", re.S)
_RVH_RE = re.compile(r"\{\{rvh\|(\d+)\|")
_RANGE_RE = re.compile(r"(\d+)\s*[-–]\s*(\d+)")
_HEADING_LINE_RE = re.compile(r"^(?:\{\{c\|.*\}\}|\{\{dhr[^}]*\}\})\s*$")
_NOP_RE = re.compile(r"\{\{nop\}\}\s*$")
_PEH_RE = re.compile(r"\{\{peh\}\}\s*$")
_STARS_RE = re.compile(r"\{\{\*\*\*\|?\d*\}\}")
_SC_RE = re.compile(r"\{\{sc\|(.*?)\}\}", re.S)
_ITALIC_RE = re.compile(r"''(.*?)''", re.S)
_BR_RE = re.compile(r"<br\s*/?>", re.I)
_SPACE_RE = re.compile(r"[ \t]+")
_ARGUMENT_KEY_RE = re.compile(r"^\d+\s*[-–]\s*\d+\s*:", re.M)
_WIKI_MARKUP_MARKERS = ("{{", "}}", "[[", "]]", "<", ">")


def _fetch_wikitext(revid: int, retries: int = 6) -> str:
    url = f"{API}?action=parse&oldid={revid}&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"MediaWiki API error for oldid={revid}: {data['error']}")
            return data["parse"]["wikitext"]["*"]
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = int(exc.headers.get("Retry-After", "10") or "10") + 2
                print(f"  rate-limited on oldid={revid}; waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch oldid={revid} after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
        except urllib.error.URLError as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch oldid={revid} after {retries} tries: {exc}") from exc
            time.sleep(2 ** attempt * 2)
    raise AssertionError("unreachable")


def _parse_header(raw_page: str) -> tuple[int | None, tuple[str, int, int] | None]:
    """(printed page number, (range-as-printed, start, end)) from the page's
    own `<noinclude>` running-header chrome. Both None for book-opening
    pages (which carry no {{rvh}}). A verso's placeholder (`#-#`/`# `)
    yields (printed, None)."""
    noinc = _NOINCLUDE_RE.findall(raw_page)
    chrome = "".join(noinc)
    rvh = _RVH_RE.search(chrome)
    if not rvh:
        return None, None
    printed = int(rvh.group(1))
    rng = _RANGE_RE.search(chrome, rvh.end())
    if not rng:
        return printed, None
    range_str = rng.group(0).replace(" ", "").replace("–", "-")
    return printed, (range_str, int(rng.group(1)), int(rng.group(2)))


def _classify_seam(body: str) -> tuple[str, str]:
    """(body with the seam marker stripped, join mode for the NEXT page):
    'para' ({{nop}}), 'hard_hyphen' ({{peh}}), 'soft_hyphen' (bare -),
    or 'space'."""
    stripped = body.rstrip()
    if _NOP_RE.search(stripped):
        return _NOP_RE.sub("", stripped).rstrip(), "para"
    if _PEH_RE.search(stripped):
        return _PEH_RE.sub("", stripped).rstrip(), "hard_hyphen"
    if stripped.endswith("-"):
        return stripped[:-1], "soft_hyphen"
    return stripped, "space"


def _clean_page(raw_page: str, book: int, djvu: int, report: dict) -> tuple[str, str]:
    """Cleaned page text (paragraphs separated by \\n\\n) + seam join mode.
    Fails loud on any surviving wiki markup."""
    body = _NOINCLUDE_RE.sub("", raw_page)

    if (book, djvu) == _ENDNOTE_PAGE:
        count = body.count(_ENDNOTE_ANCHOR)
        if count != 1:
            raise ValueError(
                f"endnote anchor matched {count} times on djvu {djvu} "
                f"(expected exactly 1) -- the pinned revision's tail layout "
                f"changed; re-verify the endnote/imprint boundary"
            )
        cut = body.index(_ENDNOTE_ANCHOR)
        report["excluded_endnote"] = body[cut:].strip()[:120] + "..."
        body = body[:cut]

    if djvu == _BOOK_OPENERS.get(book):
        # Book-opening heading chrome: leading lines that are wholly
        # {{c|...}} / {{dhr}}. The BOOK heading MUST be among them.
        lines = body.lstrip("\n").split("\n")
        n_chrome = 0
        while n_chrome < len(lines) and (
            not lines[n_chrome].strip() or _HEADING_LINE_RE.match(lines[n_chrome].strip())
        ):
            n_chrome += 1
        chrome = "\n".join(lines[:n_chrome])
        if "BOOK" not in chrome:
            raise ValueError(
                f"book {book} opener (djvu {djvu}) carries no BOOK heading in "
                f"its leading chrome -- page layout changed; re-verify"
            )
        body = "\n".join(lines[n_chrome:])

    for ref in _REF_RE.findall(body):
        report.setdefault("excluded_refs", []).append((book, djvu, ref))
    body = _REF_RE.sub("", body)

    body, seam = _classify_seam(body)

    body = _STARS_RE.sub("\n\n* * *\n\n", body)
    body = _SC_RE.sub(r"\1", body)
    body = _ITALIC_RE.sub(r"\1", body)
    body = _BR_RE.sub(" ", body)
    body = html.unescape(body)

    # Paragraphs: blank-line separated; collapse internal whitespace.
    paragraphs = [
        _SPACE_RE.sub(" ", " ".join(p.split("\n"))).strip()
        for p in re.split(r"\n\s*\n", body)
    ]
    text = "\n\n".join(p for p in paragraphs if p)

    for marker in _WIKI_MARKUP_MARKERS:
        if marker in text:
            raise ValueError(
                f"un-stripped wiki markup {marker!r} survives on cleaned "
                f"djvu {djvu} (book {book}): {text[:160]!r}"
            )
    if "THE ARGUMENT" in text:
        raise ValueError(
            f"'THE ARGUMENT' running head found in included body of djvu "
            f"{djvu} (book {book}) -- Argument material must never enter "
            f"the translation channel"
        )
    if _ARGUMENT_KEY_RE.search(text):
        raise ValueError(
            f"Argument-style 'NNN-NNN:' paragraph key found in included "
            f"body of djvu {djvu} (book {book}) -- Argument material must "
            f"never enter the translation channel"
        )
    return text, seam


def _join(prev: str, nxt: str, mode: str) -> str:
    if mode == "para":
        return prev + "\n\n" + nxt
    if mode == "hard_hyphen":
        return prev + "-" + nxt
    if mode == "soft_hyphen":
        return prev + nxt
    return prev + " " + nxt


def _split_leading_word(text: str) -> tuple[str, str]:
    parts = text.split(None, 1)
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def build_book(book: int, report: dict) -> list[dict]:
    """Ordered records for one book: fetch each pinned page, group pages
    into printed spreads (verso + range-bearing recto), and emit one record
    per spread (plus derived leading/trailing singletons -- see module
    docstring)."""
    pages = _PAGE_REVISIONS[book]
    opener = _BOOK_OPENERS[book]

    # (djvu, cleaned text, seam mode, printed page, range or None)
    cleaned: list[tuple[int, str, str, int, tuple[str, int, int] | None]] = []
    for djvu in sorted(pages):
        raw = _fetch_wikitext(pages[djvu])
        printed_claim, rng = _parse_header(raw)
        printed = djvu - _DJVU_PRINTED_OFFSET
        if printed_claim is not None and printed_claim != printed:
            raise ValueError(
                f"djvu {djvu} claims printed page {printed_claim}, expected "
                f"{printed} (djvu - {_DJVU_PRINTED_OFFSET}) -- the "
                f"djvu/printed correspondence this script relies on broke"
            )
        if djvu == opener and printed_claim is not None:
            raise ValueError(f"book {book} opener djvu {djvu} unexpectedly carries a running header")
        if printed % 2 == 1 and djvu != opener and rng is None:
            raise ValueError(
                f"recto djvu {djvu} (printed {printed}, book {book}) carries "
                f"no parseable line range -- every non-opener recto must"
            )
        if printed % 2 == 0 and rng is not None:
            raise ValueError(
                f"verso djvu {djvu} (printed {printed}, book {book}) carries "
                f"a real line range {rng[0]!r} -- violates the recto-only "
                f"model this script's spread grouping relies on"
            )
        text, seam = _clean_page(raw, book, djvu, report)
        if not text:
            raise ValueError(f"djvu {djvu} (book {book}) cleaned to empty text")
        cleaned.append((djvu, text, seam, printed, rng))
        time.sleep(1)  # be polite to the API

    # Group into records. A record closes after each range-bearing recto.
    records: list[dict] = []
    cur_text: str | None = None
    cur_seam = "space"

    def close(rng: tuple[str, int, int] | None, derived: bool) -> None:
        nonlocal cur_text
        assert cur_text is not None
        rec: dict = {"book": book}
        if rng is not None:
            rec.update({"range": rng[0], "start": rng[1], "end": rng[2]})
        if derived:
            rec["derived"] = True
        rec["text"] = cur_text
        records.append(rec)
        cur_text = None

    for djvu, text, seam, printed, rng in cleaned:
        if cur_text is None:
            cur_text, cur_seam = text, seam
        else:
            cur_text, cur_seam = _join(cur_text, text, cur_seam), seam
        if djvu == opener and printed % 2 == 1:
            # Leading recto singleton (books 1, 4, 6): close now; range
            # derived once the next recto's header is known.
            close(None, derived=True)
        elif rng is not None:
            close(rng, derived=False)
        # else: a verso -- keep accumulating into the current record.

        if cur_text is None and cur_seam in ("soft_hyphen", "hard_hyphen"):
            # The just-closed record's last page ends mid-word: complete
            # the word in the EARLIER record; the remainder of the next
            # page will start the next record (handled by patching the
            # next iteration's text -- done here by deferring: mark it).
            records[-1]["_dangling_seam"] = cur_seam

    # Trailing verso singleton (books 3, 5): text still open after loop.
    if cur_text is not None:
        close(None, derived=True)

    # Resolve dangling cross-record hyphens: move the following record's
    # leading word-fragment into the earlier record.
    for i, rec in enumerate(records):
        seam = rec.pop("_dangling_seam", None)
        if seam is None:
            continue
        if i + 1 >= len(records):
            raise ValueError(
                f"book {book}: final record ends mid-word (seam {seam}) "
                f"with no following record to complete it"
            )
        frag, rest = _split_leading_word(records[i + 1]["text"])
        if not frag or not rest:
            raise ValueError(
                f"book {book}: cannot resolve cross-record hyphen after "
                f"record {i} -- following record's text does not start "
                f"with a word fragment + remainder"
            )
        joiner = "-" if seam == "hard_hyphen" else ""
        rec["text"] = rec["text"] + joiner + frag
        records[i + 1]["text"] = rest
        report.setdefault("cross_record_rejoins", []).append(
            (book, rec.get("range", "derived"), rec["text"].rsplit(None, 1)[-1])
        )

    # Fill derived ranges from their neighbours.
    for i, rec in enumerate(records):
        if "range" in rec:
            continue
        if i == 0:
            nxt = records[1]
            rec.update({"range": f"1-{nxt['start']}", "start": 1, "end": nxt["start"]})
        elif i == len(records) - 1:
            prev = records[i - 1]
            rec.update({"range": f"{prev['end']}-", "start": prev["end"], "end": None})
        else:
            raise ValueError(f"book {book}: record {i} has no printed range but is not a book-edge singleton")

    return records


def _apply_patches(records_by_key: dict[str, dict]) -> int:
    if not PATCHES.exists():
        return 0
    patches = json.loads(PATCHES.read_text(encoding="utf-8"))
    for p in patches:
        key = p["record"]
        if key not in records_by_key:
            raise ValueError(f"PATCHES.json names record {key!r}, not present in output")
        rec = records_by_key[key]
        for old, new in p["replace"]:
            count = rec["text"].count(old)
            if count != 1:
                raise ValueError(
                    f"PATCHES.json: record {key} 'replace' text matched "
                    f"{count} times (expected exactly 1): {old!r}"
                )
            rec["text"] = rec["text"].replace(old, new)
    return len(patches)


def validate(all_records: dict[int, list[dict]]) -> list[str]:
    """Fail-loud invariants + a findings list (gaps/overlaps/derived
    ranges) for the caller to report rather than paper over."""
    findings: list[str] = []
    for book, records in all_records.items():
        if not records:
            raise ValueError(f"book {book}: no records")
        for rec in records:
            if not rec["text"].strip():
                raise ValueError(f"book {book} {rec['range']}: empty text")
            if rec.get("derived"):
                findings.append(f"book {book} {rec['range']}: DERIVED range (not printed; see extractor doc)")
        for a, b in zip(records, records[1:]):
            if a["end"] is None:
                raise ValueError(f"book {book}: open-ended record {a['range']} is not last")
            if b["start"] < a["start"]:
                raise ValueError(f"book {book}: ranges out of order at {a['range']} -> {b['range']}")
            if b["start"] < a["end"]:
                # More than a shared boundary line: a parse bug, not print reality.
                raise ValueError(f"book {book}: range overlap {a['range']} -> {b['range']}")
            if b["start"] == a["end"]:
                pass  # shared straddling boundary line -- the print's own convention
            elif b["start"] == a["end"] + 1:
                pass  # cleanly abutting
            else:
                findings.append(
                    f"book {book}: gap between {a['range']} and {b['range']} "
                    f"(lines {a['end'] + 1}-{b['start'] - 1} in neither header)"
                )
    return findings


def coverage_summary(all_records: dict[int, list[dict]]) -> list[str]:
    lines = []
    for book, records in sorted(all_records.items()):
        starts = [r["start"] for r in records]
        ends = [r["end"] for r in records if r["end"] is not None]
        lines.append(
            f"book {book}: {len(records)} records, lines {min(starts)}-{max(ends)}"
            + (" (final record open-ended)" if records[-1]["end"] is None else "")
        )
    return lines


def main() -> None:
    report: dict = {}
    all_records: dict[int, list[dict]] = {}
    for book in sorted(_PAGE_REVISIONS):
        print(f"fetching book {book} ({len(_PAGE_REVISIONS[book])} pages)...", file=sys.stderr)
        all_records[book] = build_book(book, report)

    records_by_key = {f"{r['book']}.{r['range']}": r for rs in all_records.values() for r in rs}
    n_patches = _apply_patches(records_by_key)

    findings = validate(all_records)

    # Normalize field order for a stable, readable dump.
    flat = [
        {
            "book": r["book"], "range": r["range"], "start": r["start"], "end": r["end"],
            **({"derived": True} if r.get("derived") else {}),
            "text": r["text"],
        }
        for rs in all_records.values() for r in rs
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_CLEAN.write_text(
        json.dumps(flat, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT_CLEAN} ({len(flat)} records)", file=sys.stderr)
    for line in coverage_summary(all_records):
        print("  " + line, file=sys.stderr)
    print(f"patches applied: {n_patches}", file=sys.stderr)
    for ref in report.get("excluded_refs", []):
        print(f"  excluded footnote (book {ref[0]}, djvu {ref[1]}): {ref[2]!r}", file=sys.stderr)
    if "excluded_endnote" in report:
        print(f"  excluded endnote/imprint tail: {report['excluded_endnote']!r}", file=sys.stderr)
    for rejoin in report.get("cross_record_rejoins", []):
        print(f"  cross-record hyphen rejoin: book {rejoin[0]} record {rejoin[1]} keeps {rejoin[2]!r}", file=sys.stderr)
    print("findings:", file=sys.stderr)
    for f in findings:
        print("  " + f, file=sys.stderr)


if __name__ == "__main__":
    main()
