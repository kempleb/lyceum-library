"""One-off: fetch W. A. Oldfather's Loeb translation of Epictetus (Discourses
Books 1-4, vol. I 1925 / vol. II 1928; the Manual/Encheiridion, vol. II 1928)
from Wikisource's human-proofread transcription and produce clean
{book}.{chapter}: text / {chapter}: text JSON maps -- see sources/INVENTORY.md
for full source-verification detail and sources/oldfather-epictetus/raw/ for
the archive.org OCR scans this scrape supersedes as the pipeline's input (the
OCR scans remain in place as verification witnesses only).

Fetch mechanics -- same approach as the sibling extract_haines_wikisource.py:
each Discourses chapter lives on its own Wikisource subpage
("Epictetus, the Discourses as reported by Arrian, the Manual, and
Fragments/Book N/Chapter M"), and the Manual lives on a single page
(".../Manual") with all 53 chapters run together, chapter boundaries marked
by `<span class="wst-anchor" id="N">`. A subpage's own wikitext is just a
ProofreadPage `<pages index=... />` transclusion tag, not literal text --
Wikisource keeps the real proofread text in the Page: namespace, one page per
scanned leaf, assembled at render time -- so this script fetches the
already-assembled render via action=parse&prop=text at a PINNED revision
(oldid=), rather than re-implementing `<pages>` transclusion over raw
wikitext. `_DISCOURSES_REVISIONS`/`_MANUAL_REVISION` were captured 2026-07-16
via action=query&prop=revisions against every "Book N/Chapter M" and
"/Manual" subpage; re-running this script reproduces byte-identical HTML
unless Wikisource is deliberately re-pointed at a new revision here.

HTML structure (see sources/INVENTORY.md's Wikisource-provenance section for
a captured sample). Both page shapes share one body container,
`<div class="prp-pages-output" lang="en">`, running up to an
"==Footnotes==" heading (outside this div, so bounding extraction to the div
already excludes footnote text -- no separate marker search needed). Noise
dropped before any text is read: `<sup class="reference">` (footnote-ref
superscripts), `<span class="pagenum...">` (scan-boundary page markers, a
zero-width-space placeholder plus data attributes, no prose), and
`<style>`/`<link>` (inline TemplateStyles CSS MediaWiki injects mid-paragraph
for one-off span classes -- invisible when rendered, but lxml's
text_content() does not know that and would splice raw CSS text into the
chapter body if left in).

Discourses chapter pages additionally open with a `<div class="wst-center
tiInherit">` "CHAPTER <ROMAN>" heading (font-size 120%; the book-opening
chapter is preceded by a second such div, "BOOK <ROMAN>", font-size 144%) --
both are redundant with this script's own "book.chapter" JSON key and are
dropped. Oldfather's own italic chapter subtitle ("Of the things which are
under our control...") that FOLLOWS, in its own `wst-center tiInherit` div,
is genuine translated content (his own descriptive heading for each
Discourse) -- extracted as a separate `title` (oldfather-discourses-
titles.json), no longer swallowed as the chapter text's opening clause.

Each chapter page also carries small marginal Loeb reference numbers, every
5th TLG-numbered section (`<span class="wst-verse wst-verse-default"
id="N"><sup>N</sup></span>` -- named "verse" by the Wikisource template that
renders them, but here marking Loeb SECTION numbers, not verse lines;
confirmed by their spacing tracking each chapter's own total TLG-section
count, e.g. chapter 4.1's markers run 5..175 for a chapter of 177 sections,
and chapter 1.1's run 5..30 for 32 sections -- an unrelated line-position
axis would not track section count that way). These are captured as
`paras: [{"n", "o"}]` (oldfather-discourses-paras.json) -- offsets into the
CLEANED text where each digit used to sit -- and the bare digits removed
from the running prose (previously spliced in raw, e.g. "—110For what
purpose"). Being only every 5th section, `paras` is always a SUBSET of the
Greek `sections` channel's numbers for the same chapter (stage1_greek.py) --
never a 1:1 match, and stage1_book_section_english.py validates exactly
that.

Extraction bug fixed alongside this (found via the 2.2 "Consider , you" stray
space, verified against the pinned source HTML -- the source has NO space
before the comma; `_flatten`'s blind tag-to-space substitution inserted one
because the closing `</span>` around Oldfather's small-caps drop-cap sits
directly against the following punctuation with no real whitespace in the
source): `_extract_chapter` now collapses a space that formed directly
before terminal punctuation, but ONLY within this Discourses path -- the
Manual extraction below is untouched (no comparable audit was done there;
per the brief, its text handling stays exactly as before).

The Manual has no such subtitle: each of the 53 chapters opens directly with
`<span class="wst-anchor" id="N">N</span>. ` inline within the running prose
(chapters do not reliably align to `<p>` boundaries -- a short chapter can
share a `<p>` with its neighbour via `<br/>`), so extraction here works by
regex-replacing each anchor span (plus its trailing "N. " numbering, which is
redundant with the JSON key) with a null-byte delimiter token on the
noise-stripped HTML, then splitting the fully tag-stripped, entity-unescaped
text on those tokens. Content before the first delimiter (the page's own
title block and the AuxTOC chapter-link table) is discarded as front matter.

Exclusions per the brief: Fragments (a separate Wikisource subpage, never
fetched by this script) and the "DOUBTFUL AND SPURIOUS FRAGMENTS" subsection
noted in INVENTORY.md for the archive.org witness scan are both out of scope
-- the registry covers Discourses + Enchiridion only.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import lxml.html

OUT_DISCOURSES = Path("../sources/oldfather-epictetus/oldfather-discourses.clean.json")
OUT_DISCOURSES_TITLES = Path("../sources/oldfather-epictetus/oldfather-discourses-titles.json")
OUT_DISCOURSES_PARAS = Path("../sources/oldfather-epictetus/oldfather-discourses-paras.json")
OUT_ENCHIRIDION = Path("../sources/oldfather-epictetus/oldfather-enchiridion.clean.json")

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

_PAGE_TITLE = "Epictetus, the Discourses as reported by Arrian, the Manual, and Fragments"

# Captured 2026-07-16 via action=query&prop=revisions on every
# "<title>/Book N/Chapter M" subpage (chapter counts 30/26/26/13, matching
# the Greek spine's 95-chapter Discourses total) and on "<title>/Manual".
# Indexed [book][chapter - 1]. See sources/INVENTORY.md for the fetch log.
_DISCOURSES_REVISIONS: dict[int, list[int]] = {
    1: [11538152, 11538165, 11538177, 11538180, 11538181, 11538182, 11538184, 11538188, 11538189, 11538153, 11538154, 11538155, 11538156, 11538157, 11538158, 11538159, 11538161, 11538162, 11538164, 11538166, 11538167, 11538168, 11538169, 11538170, 11538171, 11538172, 11538173, 11538174, 11538176, 13256335],
    2: [13256338, 11538213, 11538233, 11538235, 11538237, 11538240, 11538242, 11538246, 11538250, 11538191, 11538192, 11538193, 11538196, 11538199, 11538201, 11538204, 11538207, 11538209, 11538211, 11538215, 11538218, 11538220, 11538223, 11538226, 11538228, 13256340],
    3: [13256342, 11538295, 11538321, 11538323, 11538325, 11538328, 11538331, 11538333, 11538338, 11538257, 11538259, 11538264, 11538268, 11538271, 11538275, 11538280, 11538283, 11538289, 11538292, 11538298, 11538300, 11538305, 11538309, 11538312, 11538315, 13256343],
    4: [13256344, 11538353, 11538357, 11538361, 11538364, 11538367, 11538371, 11538375, 11538378, 11538345, 11538347, 11538349, 11538351],
}
_MANUAL_REVISION = 13301500

# The proofread body lives in exactly one such div; bounding extraction to
# ITS OWN subtree (via XPath on the parsed DOM, not a string search for a
# following "==Footnotes==" heading) is what correctly excludes footnote
# text even on the chapters that have none at all (the ==Footnotes== heading
# is only emitted when `<references/>` has something to render, so a
# footnote-less chapter page has no such marker to search for).
_BODY_XPATH = '//div[@class="prp-pages-output"]'

# Footnote-ref superscripts, scan-boundary page markers, and inline
# TemplateStyles CSS -- see module docstring. The reflist/references drop is
# defensive on THIS translation's pages (their footnote list renders outside
# the prp-pages-output div, under the ==Footnotes== heading, so it is never
# captured anyway -- verified byte-identical output with and without the
# rule) but load-bearing on the sibling Long scraper's pages, which render
# the footnote list INSIDE the body div; kept identical in both scrapers so
# neither silently regresses if Wikisource restyles.
_DROP_XPATH = './/sup[contains(concat(" ", normalize-space(@class), " "), " reference ")]' \
              ' | .//span[contains(concat(" ", normalize-space(@class), " "), " pagenum ")]' \
              ' | .//div[contains(concat(" ", normalize-space(@class), " "), " reflist ")]' \
              ' | .//ol[contains(concat(" ", normalize-space(@class), " "), " references ")]' \
              ' | .//style | .//link'

# A Discourses chapter page's `wst-center tiInherit` divs: the FIRST is
# always "[BOOK <ROMAN>[.] ]CHAPTER <ROMAN>[.]" (redundant with this script's
# own "book.chapter" JSON key) -- the trailing period after the roman
# numeral is present on SOME chapter pages and absent on others (verified:
# e.g. 1.27 "CHAPTER XXVII." vs 1.1 "CHAPTER I", both real), so it is
# optional on both numerals. The chapter's italic subtitle is the NEXT such
# div, whose text does NOT match this shape.
_HEADING_TEXT = re.compile(r"^\s*(?:BOOK\s+[IVXLCDM]+\.?\s*)?CHAPTER\s+[IVXLCDM]+\.?\s*$")
_WST_CENTER = re.compile(r'<div class="wst-center tiInherit">(.*?)</div>', re.S)

# Every-5th-TLG-section Loeb reference marker -- see module docstring.
_DISCOURSES_VERSE = re.compile(
    r'<span class="wst-verse wst-verse-default" id="(\d+)"><sup>\1</sup></span>'
)
# A space directly before terminal punctuation is always an artifact of
# `_flatten`'s tag-to-space substitution firing on a closing tag that sits
# against punctuation with no real whitespace in the source (the 2.2
# "Consider , you" finding -- see module docstring); English prose never
# legitimately has one. Scoped to _extract_chapter only.
_SPACE_BEFORE_PUNCT = re.compile(r" +([,.;:!?)])")

_WST_ANCHOR = re.compile(
    r'<span id="(\d{1,2})" title="Anchor:\1" class="wst-anchor">\1</span>\.\s*'
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _fetch_html(revid: int, retries: int = 5) -> str:
    url = f"{API}?action=parse&oldid={revid}&prop=text&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(f"MediaWiki API error for oldid={revid}: {data['error']}")
            return data["parse"]["text"]["*"]
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"failed to fetch oldid={revid} after {retries} tries: {exc}") from exc
            wait = 2 ** attempt * 2
            print(f"  fetch oldid={revid} failed ({exc}); retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _clean_body(html: str) -> str:
    """Parse the full page HTML, isolate the `prp-pages-output` body div(s) by
    their own subtree (see `_BODY_XPATH`), strip noise elements, and return
    the cleaned fragments concatenated (in document order) as one string. The
    Manual page transcludes its source in TWO separate `<pages index=...>`
    blocks (title/AuxTOC front matter, pages 489-491; then the 53 chapters
    proper, pages 493-547) -- each becomes its own `prp-pages-output` div, so
    taking only the first would silently drop all 53 chapters. A Discourses
    chapter page has exactly one such div; concatenating a single-element
    list is a no-op there."""
    tree = lxml.html.fromstring(html)
    bodies = tree.xpath(_BODY_XPATH)
    if not bodies:
        raise ValueError("could not find prp-pages-output body div in fetched HTML")
    parts = []
    for body in bodies:
        for el in body.xpath(_DROP_XPATH):
            el.drop_tree()
        parts.append(lxml.html.tostring(body, encoding="unicode"))
    return "".join(parts)


def _flatten(html_fragment: str) -> str:
    """Strip all remaining tags, unescape entities, collapse whitespace."""
    import html as _html
    text = _TAG.sub(" ", html_fragment)
    text = _html.unescape(text)
    return _WS.sub(" ", text).strip()


def _capitalize_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
        if not ch.isspace():
            break
    return text


def _extract_chapter(html: str) -> tuple[str, str, list[dict]]:
    """Returns `(title, text, paras)` for one Discourses chapter page -- see
    the module docstring for the `wst-center` (chapter title) and
    `wst-verse` (Loeb every-5th-section marker) HTML shapes parsed here.

    `title` is Oldfather's own italic chapter subtitle (e.g. "Of freedom"):
    the FIRST `wst-center tiInherit` div is always the redundant "[BOOK
    <ROMAN> ]CHAPTER <ROMAN>" heading (dropped, matching the old
    `_LEAD_HEADING` strip); the NEXT one (the first that doesn't match the
    heading shape) is the subtitle -- removed from the HTML entirely (not
    merely skipped at flatten time) so it can't leak into `text`'s offsets.
    A FURTHER `wst-center` div (chapters 1.12, 1.24: a centered inline
    quoted verse sharing the same CSS class) is ordinary body content, not
    another title -- kept verbatim, flowing into `text` at flatten time like
    any other prose.

    `paras` is `[{"n", "o"}]` over the returned `text`: the char offset
    where each wst-verse marker's own digit used to sit (removed from the
    running prose), keyed by the Loeb section number it marks."""
    cleaned = _clean_body(html)
    title_parts: list[str] = []

    def _take_center(m: re.Match) -> str:
        inner = _flatten(m.group(1))
        if _HEADING_TEXT.match(inner):
            return ""
        if not title_parts:
            title_parts.append(inner)
            return ""
        return m.group(0)

    cleaned = _WST_CENTER.sub(_take_center, cleaned)
    if not title_parts:
        raise ValueError("no chapter subtitle (wst-center tiInherit) found")

    # Replace each Loeb marker with a null-byte delimiter before stripping
    # the remaining tags, so its digit's flattened offset can be recovered
    # afterward (same sentinel technique as _extract_manual's wst-anchor
    # handling below). The stray-space-before-punctuation fix (see
    # _SPACE_BEFORE_PUNCT) runs on the WHOLE flattened string, before
    # splitting on the sentinels, so paragraph offsets are computed against
    # the already-cleaned text.
    delimited = _DISCOURSES_VERSE.sub(lambda m: f"\x00{m.group(1)}\x00", cleaned)
    flat = _SPACE_BEFORE_PUNCT.sub(r"\1", _flatten(delimited))
    parts = flat.split("\x00")
    text_acc = parts[0]
    paras: list[dict] = []
    for i in range(1, len(parts), 2):
        n = int(parts[i])
        o = len(text_acc)
        prev_ch = text_acc[-1] if text_acc else ""
        next_ch = parts[i + 1][0] if i + 1 < len(parts) and parts[i + 1] else ""
        if prev_ch.isalpha() and next_ch.isalpha():
            raise ValueError(
                f"wst-verse marker {n} lands mid-word at offset {o} "
                f"(between {prev_ch!r} and {next_ch!r})"
            )
        paras.append({"n": n, "o": o})
        if i + 1 < len(parts):
            text_acc += parts[i + 1]
    return title_parts[0], _capitalize_first(text_acc), paras


def _extract_manual(html: str) -> dict[str, str]:
    cleaned = _clean_body(html)
    # Replace each chapter's opening anchor span (plus its "N. " numbering)
    # with a null-byte delimiter before stripping the remaining tags, so the
    # split survives regardless of <p>/<br/> boundaries (see module docstring).
    delimited = _WST_ANCHOR.sub(lambda m: f"\x00{m.group(1)}\x00", cleaned)
    flat = _flatten(delimited)
    parts = flat.split("\x00")
    out: dict[str, str] = {}
    # parts alternates: [front-matter, "1", text1, "2", text2, ...]
    i = 1
    while i + 1 < len(parts):
        chapter, text = parts[i].strip(), parts[i + 1]
        out[chapter] = _capitalize_first(text.strip())
        i += 2
    return out


def main() -> None:
    discourses: dict[str, str] = {}
    titles: dict[str, str] = {}
    paras: dict[str, list[dict]] = {}
    for book, revids in _DISCOURSES_REVISIONS.items():
        print(f"Book {book}: fetching {len(revids)} chapters...")
        for chapter, revid in enumerate(revids, start=1):
            html = _fetch_html(revid)
            key = f"{book}.{chapter}"
            title, text, chapter_paras = _extract_chapter(html)
            discourses[key] = text
            titles[key] = title
            if chapter_paras:
                paras[key] = chapter_paras
            time.sleep(1)
        print(f"  Book {book}: {len(revids)} chapters done")

    OUT_DISCOURSES.write_text(
        json.dumps(discourses, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_DISCOURSES} -- {len(discourses)} chapters")

    OUT_DISCOURSES_TITLES.write_text(
        json.dumps(titles, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_DISCOURSES_TITLES} -- {len(titles)} titles")

    OUT_DISCOURSES_PARAS.write_text(
        json.dumps(paras, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_DISCOURSES_PARAS} -- {len(paras)} chapters with markers")

    print("Manual: fetching...")
    manual_html = _fetch_html(_MANUAL_REVISION)
    enchiridion = _extract_manual(manual_html)
    OUT_ENCHIRIDION.write_text(
        json.dumps(enchiridion, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_ENCHIRIDION} -- {len(enchiridion)} chapters")


if __name__ == "__main__":
    main()
