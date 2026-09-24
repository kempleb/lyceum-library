"""One-off: fetch C. R. Haines' 1916 Loeb Meditations translation from
Wikisource's human-proofread transcription (en.wikisource.org, "Marcus
Aurelius (Haines 1916)", ProofreadPage quality 3 = "Proofread" -- one pass
short of "Validated") and produce a clean {book}.{chapter}: text JSON map,
keyed exactly like the OCR-based extract_haines.py's output and the Greek
book-section spine's dotted column tokens.

Supersedes the OCR-derived haines.clean.json as the file the pipeline reads
(manifests/meditations.yaml's english.primary.file). The OCR chain
(extract_haines.py, thecommuningswit00marcuoft_djvu.txt, PATCHES.json, the
two extra archive.org scan witnesses) is left in place, untouched, as a
verification witness -- see sources/INVENTORY.md's Wikisource-sourcing note.

Fetch mechanics. Each of the 12 "Book N" subpages is fetched via the
MediaWiki API's action=parse at a PINNED revision (oldid=) -- see
_BOOK_REVISIONS below, captured 2026-07-16. A Book page's own wikitext is
just a ProofreadPage `<pages index=... />` transclusion tag, not literal
text (Wikisource keeps the real proofread text in the Page: namespace, one
page per scanned leaf, assembled at render time); action=parse&prop=text
returns the already-assembled HTML, which is what this script parses,
rather than re-implementing `<pages>` transclusion over raw wikitext.

HTML structure (see a fetched sample, archived nowhere else -- re-fetch at
the pinned oldid to reproduce): the body lives inside one
`<div class="prp-pages-output" lang="en">` that runs up to an
"==Footnotes==" section heading; each chapter opens a `<p>` whose flattened
text begins "N. " (smallcaps spans already carry correctly-cased plain
text -- Wikisource proofreaders typed real case, not OCR-derived shouting
caps, so no case-repair is needed here); a chapter can continue across
several further, unnumbered `<p>` paragraphs before the next numbered `<p>`
opens the next chapter. Footnote markers are `<sup class="reference">`
elements (dropped whole, no textual residue); mid-page scan-boundary
markers are `<span class="pagenum ws-pagenum">` (dropped whole -- they
carry only a zero-width-space placeholder and data attributes, no prose).

Known coverage gaps (see manifests/meditations.yaml, sources/INVENTORY.md):
Haines' translation has no chapter 5.37 (his edition merges it into 5.36 --
Wikisource's Book 5 page simply ends its numbering at "36.", confirmed by
this script's max-chapter check, not a skipped-number gap) and is missing
11.31, 11.34, 12.15 (true skipped-number gaps in an otherwise-continuous
sequence -- Wikisource's own text jumps "30." -> "32.", "33." -> "35.",
"14." -> "16." exactly as the manifest already documents for the OCR
extraction). `_ALLOWED_GAPS` enumerates these; any OTHER numbering
discontinuity is a schema-assumption violation and fails loud rather than
being silently absorbed.
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

OUT = Path("../sources/haines-meditations/haines.clean.json")
PATCHES = Path("../sources/haines-meditations/WIKISOURCE-PATCHES.json")

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# Captured 2026-07-16 via action=query&prop=revisions on each
# "Marcus Aurelius (Haines 1916)/Book N" subpage -- see
# sources/INVENTORY.md for the full per-book fetch log (URL, revid,
# timestamp). Pinning these (rather than fetching "latest") makes a re-run
# of this script reproduce byte-identical HTML unless Wikisource's page is
# deliberately re-pointed at a new revision here.
_BOOK_REVISIONS = {
    1: 14039740,
    2: 14041829,
    3: 14062858,
    4: 14085030,
    5: 14148813,
    6: 14149965,
    7: 14149990,
    8: 14007301,
    9: 14013645,
    10: 14019457,
    11: 14031354,
    12: 14037608,
}

# True skipped-number gaps within an otherwise-continuous chapter sequence
# (see module docstring). 5.37 is NOT here: Haines' numbering simply ends at
# 36 for book 5, which the max-chapter check below verifies directly rather
# than needing a gap allowance.
_ALLOWED_GAPS = {(11, 31), (11, 34), (12, 15)}

_CHAPTER_HEAD = re.compile(r"^(\d{1,3})\.\s*(.*)$", re.DOTALL)
_FOOTNOTES_MARKER = '<div class="mw-heading mw-heading2"><h2 id="Footnotes">'
_BODY_MARKER = '<div class="prp-pages-output" lang="en">'


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


def _isolate_body(html: str, book: int) -> str:
    body_start = html.find(_BODY_MARKER)
    if body_start == -1:
        raise ValueError(f"Book {book}: could not find body marker {_BODY_MARKER!r} in fetched HTML")
    footnotes_start = html.find(_FOOTNOTES_MARKER, body_start)
    if footnotes_start == -1:
        raise ValueError(f"Book {book}: could not find Footnotes heading marker in fetched HTML")
    return html[body_start:footnotes_start]


# Elements that contribute no body prose and are dropped wholesale before
# any <p> is read: footnote-reference superscripts, the scan-boundary
# page-number markers ProofreadPage inserts at each transcluded leaf, and
# inline <style>/<link> TemplateStyles elements. The latter matter more than
# they look: a <style> MediaWiki injects INSIDE a <p> (to scope a one-off
# span class, e.g. "nowrap" on a spaced-ellipsis lacuna marker in 11.31) is
# invisible when rendered but lxml's text_content() does not know that and
# would otherwise splice its raw CSS text straight into the chapter body
# (caught by inspecting 11.31's first extraction attempt, which opened with
# ".mw-parser-output .nowrap...{white-space:nowrap}" before this was added).
_DROP_XPATH = './/sup[contains(concat(" ", normalize-space(@class), " "), " reference ")]' \
              ' | .//span[contains(concat(" ", normalize-space(@class), " "), " pagenum ")]' \
              ' | .//style | .//link'


# A chapter's prose is not always carried in <p> tags alone: a set-off verse
# quotation (Marcus quoting Homer/Euripides/etc., e.g. 7.51, 11.6) is typeset
# as a plain indented <div> with <i>/<br/> children and NO <p> of its own --
# caught only by diffing against the OCR witness, which had this content
# (7.51 collapsed from a real ~200-char chapter to the single word "Again:"
# before this was added). Selecting "every <p>, plus every <div> that is a
# content LEAF (no nested <p> or <div> of its own)" in document order (XPath
# `|` unions preserve document order) picks up both without double-counting
# a structural wrapper div's own nested <p> (e.g. the "wst-center" divs used
# for the book-title block and the closing "Written among the ..." colophon,
# both of which already have their own <p>).
_BLOCK_XPATH = ".//p | .//div[not(.//p) and not(.//div)]"


def _parse_book(book: int, html: str) -> dict[str, str]:
    body_html = _isolate_body(html, book)
    tree = lxml.html.fromstring(body_html)
    for el in tree.xpath(_DROP_XPATH):
        el.drop_tree()
    # lxml's text_content() concatenates across element boundaries with NO
    # whitespace, so a rendered line/space break that carries no literal
    # whitespace text glues its neighbours together ("things,For" in 7.38;
    # likewise 7.40/7.41/7.44 -- a verse line break inside one <p>, typeset
    # as <br/> plus an EMPTY inline-block "wst-gap" spacer span). Prefix a
    # space onto each such element's tail; the existing whitespace collapse
    # in flush()/the paragraph loop dedupes any doubling.
    for el in tree.iter("br"):
        el.tail = " " + (el.tail or "")
    for el in tree.xpath('.//span[contains(concat(" ", normalize-space(@class), " "), " wst-gap ")]'):
        if not el.text_content().strip():
            el.tail = " " + (el.tail or "")

    out: dict[str, str] = {}
    current = 0
    buf: list[str] = []

    def flush():
        if current and buf:
            text = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if text:
                out[f"{book}.{current}"] = text

    for p in tree.xpath(_BLOCK_XPATH):
        raw = p.text_content()
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            continue
        m = _CHAPTER_HEAD.match(text)
        if m:
            want = current + 1
            n = int(m.group(1))
            if n == want:
                flush()
                current, buf = n, [m.group(2)]
                continue
            if n > want:
                gap_ok = all((book, c) in _ALLOWED_GAPS for c in range(want, n))
                if gap_ok:
                    flush()
                    current, buf = n, [m.group(2)]
                    continue
            raise ValueError(
                f"Book {book}: chapter numbering discontinuity -- expected {want}, "
                f"got {n} (paragraph: {text[:80]!r}). Not in the documented allowed-gap "
                f"set {_ALLOWED_GAPS}; stopping rather than improvising."
            )
        if current:
            buf.append(text)
        # else: front-matter paragraph (e.g. the "BOOK I" title block) before
        # chapter 1 opens -- not body prose, dropped.
    flush()
    return out


# --- hand-verified transcription-slip patches ---------------------------------
# The pinned Wikisource revisions carry a couple of unambiguous transcription
# typos contradicted by the print (verified against the OCR scan witnesses in
# sources/haines-meditations/ -- each entry's `note`/`witness_lines` records
# the exact witness evidence). Same fail-loud philosophy as the OCR chain's
# PATCHES.json: a patch is a claim that its exact `old` string occurs EXACTLY
# ONCE in the named chapter; if the extraction output changes (e.g. the pinned
# revision is bumped and Wikisource fixed the typo upstream), the stale patch
# fails the build loudly rather than silently no-op'ing.
def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_patches(out: dict[str, str], patches: list[dict]) -> dict[str, str]:
    for p in patches:
        chapter = p["chapter"]
        if chapter not in out:
            raise ValueError(f"WIKISOURCE-PATCHES.json: chapter {chapter!r} not found in extraction output")
        text = out[chapter]
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"WIKISOURCE-PATCHES.json: chapter {chapter} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        out[chapter] = text
    return out


def main() -> None:
    all_chapters: dict[str, str] = {}
    for book in range(1, 13):
        revid = _BOOK_REVISIONS[book]
        print(f"fetching Book {book} (oldid={revid})...")
        html = _fetch_html(revid)
        chapters = _parse_book(book, html)
        nums = sorted(int(k.split(".")[1]) for k in chapters)
        print(f"  Book {book}: {len(chapters)} chapters, {nums[0]}..{nums[-1]}")
        all_chapters.update(chapters)
        time.sleep(1)  # be polite to the API between the 12 fetches

    patches = _load_patches()
    all_chapters = _apply_patches(all_chapters, patches)
    OUT.write_text(
        json.dumps(all_chapters, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} -- {len(all_chapters)} chapters"
          + (f" ({len(patches)} hand-verified patch(es) applied)" if patches else ""))


if __name__ == "__main__":
    main()
