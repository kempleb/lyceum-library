"""One-off: fetch George Long's 1877 (this scan: 1890 Bell reprint) translation
of Epictetus' Discourses + Encheiridion from Wikisource's human-proofread
transcription and produce clean {book}.{chapter}: text / {chapter}: text JSON
maps -- see sources/INVENTORY.md for full source-verification detail and
sources/long-epictetus/raw/ for the archive.org OCR scan this scrape
supersedes as the pipeline's input (the OCR scan remains in place as a
verification witness only).

Fetch mechanics -- same approach as extract_oldfather_wikisource.py (see that
module's docstring for the shared rationale: subpage wikitext is just a
ProofreadPage `<pages index=... />` transclusion tag, so this script fetches
the already-assembled render via action=parse&prop=text at a PINNED revision).
Each Discourses chapter lives on its own subpage ("The Discourses of
Epictetus; with the Encheiridion and Fragments/Book N/Chapter M"), and the
Encheiridion lives on a single page (".../The Encheiridion or Manual") with
all 53 chapters run together. `_DISCOURSES_REVISIONS`/`_MANUAL_REVISION` were
captured 2026-07-16 via action=query&prop=revisions against every subpage.

HTML structure differs from Oldfather's in two ways (see
sources/INVENTORY.md's Wikisource-provenance section for a captured sample):

* Chapter markers are plain text, not `id`-bearing anchor spans: a Discourses
  chapter opens `<div class="wst-center tiInherit"><p><span
  style="font-size:120%;">CHAPTER <ROMAN>.</span></p></div>` (preceded, for a
  book's first chapter, by a "BOOK <ROMAN>." div at font-size 144%), and each
  of the Encheiridion's 53 sections opens the SAME div/font-size-120% shape
  but with a bare roman numeral ("I.", "II.", ...) instead of "CHAPTER
  <ROMAN>." -- the Encheiridion's own title ("THE ENCHEIRIDION, OR MANUAL.")
  is set at font-size 144%, so it never collides with the per-chapter 120%
  heading pattern used to split chapters.
* Long's chapter subtitle line (e.g. "of the things which are in our power,
  and not in our power.") is typeset in Wikisource as a smallcaps SPAN whose
  underlying characters are literally lowercase (a common transcription
  convention for an all-small-caps printed heading: the visual capitals are
  pure CSS, not real characters) -- `_capitalize_first` repairs the resulting
  chapter text's leading letter so it reads as a normal sentence, matching
  what `extract_long.py` (the OCR-based Meditations sibling) does not need to
  do only because ITS source, a proofread plain-text transcription, already
  encodes the heading's real capitalization.

As with Oldfather, footnote-ref superscripts (`<sup class="reference">`),
scan-boundary page markers (`<span class="pagenum...">`), and inline
TemplateStyles CSS (`<style>`/`<link>`) are dropped before any text is read,
and the body is bounded to the `<div class="prp-pages-output">` that runs up
to the (separate, later) "==Footnotes==" section. Fragments (a separate
Wikisource subpage, never fetched here) are out of scope per the brief.

Encheiridion numbering repair (John's ruling, 2026-07-16 -- see
sources/INVENTORY.md's coverage-anomaly section). Long's printed edition has
only 52 sections: his "L." merges what the modern/Schenkl numbering (which
Oldfather follows, and which the Greek spine uses) counts as separate
SS 50-51, and the merge cascades (his 51 = modern 52, his 52 = modern 53).
The ruling is to key this file to the MODERN numbering -- split, don't gap:
`_renumber_manual` splits Long's merged section 50 into modern 50 and 51 at
the exact sentence opening his rendering of modern S 51
(`_MODERN_51_OPENING`, "How long will you then still defer thinking yourself
worthy of the best things..." -- Oldfather's modern-numbered S 51 opens "How
long will you still wait to think yourself worthy of the best things...",
same subject matter, confirming the boundary), then shifts his 51 -> 52 and
52 -> 53. The split marker must match exactly once and the input must have
exactly Long's 52 printed sections, else the run fails loud -- a numbering
repair that silently misfires is worse than none.
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

OUT_DISCOURSES = Path("../sources/long-epictetus/long-discourses.clean.json")
OUT_ENCHIRIDION = Path("../sources/long-epictetus/long-enchiridion.clean.json")

API = "https://en.wikisource.org/w/api.php"
USER_AGENT = (
    "classical-philosophy-reader/1.0 "
    "(research tool for a public-domain-translation reader; "
    "contact: jhboyer@loyno.edu)"
)

# Captured 2026-07-16 via action=query&prop=revisions on every
# "The Discourses of Epictetus; with the Encheiridion and Fragments/Book
# N/Chapter M" subpage (chapter counts 30/26/26/13, matching the Greek
# spine's 95-chapter Discourses total) and on ".../The Encheiridion or
# Manual". Indexed [book][chapter - 1]. See sources/INVENTORY.md for the
# fetch log.
_DISCOURSES_REVISIONS: dict[int, list[int]] = {
    1: [14267196, 14266538, 14266543, 14266549, 14266553, 14266563, 14266566, 14266574, 14266577, 14266583, 14267048, 14267054, 14267060, 14267063, 14267066, 14267069, 14267073, 14267096, 14267108, 14267114, 14267417, 14267419, 14267426, 14267433, 14267435, 14267441, 14267445, 14267446, 14267447, 14267455],
    2: [14267464, 14267783, 14267781, 14267785, 14267789, 14267796, 14267798, 14267802, 14267807, 14268146, 14268144, 14268152, 14268157, 14268164, 14268170, 14268174, 14268177, 14268184, 14268189, 14268191, 14268925, 14268929, 14268934, 14268937, 14268938, 14268941],
    3: [14268945, 14268947, 14268948, 14268952, 14268954, 14268955, 14268956, 14268957, 14269305, 14270249, 14270357, 14271240, 14271498, 14271676, 14271721, 14273943, 14274100, 14274102, 14274153, 14274158, 14268974, 14268976, 14268977, 14268978, 14268985, 14268989],
    4: [14268997, 14268998, 14272162, 14273825, 14274653, 14275447, 14275827, 14275869, 14275896, 14275899, 14269009, 14269013, 14269019],
}
_MANUAL_REVISION = 14269067

# The proofread body lives in exactly one such div; bounding extraction to
# ITS OWN subtree (via XPath on the parsed DOM, not a string search for a
# following "==Footnotes==" heading) is what correctly excludes footnote
# text even on the chapters that have none at all (the ==Footnotes== heading
# is only emitted when `<references/>` has something to render).
_BODY_XPATH = '//div[@class="prp-pages-output"]'

# Besides the noise elements shared with the Oldfather scraper (footnote-ref
# superscripts, page markers, TemplateStyles), this translation's pages
# render the FOOTNOTE LIST ITSELF (`<div class="reflist"><ol
# class="references">`, the translator's notes with their "^" backlinks)
# INSIDE the prp-pages-output body div -- unlike Oldfather's pages, which
# render it outside, under the separate "==Footnotes==" heading. Without
# dropping it wholesale, every chapter with footnotes swallows all its
# translator-note text at the end of the chapter body (caught by the
# Oldfather-vs-Long length-ratio screen: 92/95 Discourses chapters and
# Enchiridion 53 carried the contamination before this rule).
_DROP_XPATH = './/sup[contains(concat(" ", normalize-space(@class), " "), " reference ")]' \
              ' | .//span[contains(concat(" ", normalize-space(@class), " "), " pagenum ")]' \
              ' | .//div[contains(concat(" ", normalize-space(@class), " "), " reflist ")]' \
              ' | .//ol[contains(concat(" ", normalize-space(@class), " "), " references ")]' \
              ' | .//style | .//link'

# A Discourses chapter page opens "BOOK <ROMAN>." (only the book's first
# chapter) then always "CHAPTER <ROMAN>." -- both redundant with this
# script's own "book.chapter" JSON key, stripped from the leading edge.
_LEAD_HEADING = re.compile(r"^\s*(?:BOOK\s+[IVXLCDM]+\.\s*)?CHAPTER\s+[IVXLCDM]+\.\s*")

# The font-size:120% heading div used for both a Discourses "CHAPTER N."
# marker (never seen here -- that page's own single heading is stripped by
# _LEAD_HEADING instead) and, on the Manual page, EVERY chapter's bare roman
# numeral ("I.", "II.", ... "LIII."). The Manual's own title
# ("THE ENCHEIRIDION, OR MANUAL.") is set at font-size:144%, so it never
# matches this pattern.
_MANUAL_CHAPTER_HEADING = re.compile(
    r'<div class="wst-center tiInherit">\s*'
    r'<p><span style="font-size:120%;">([IVXLCDM]+)\.</span>\s*</p>\s*'
    r'</div>\s*'
)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_to_int(s: str) -> int:
    total = prev = 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


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
    the cleaned fragments concatenated (in document order) as one string --
    see extract_oldfather_wikisource.py's `_clean_body` docstring: the Manual
    page transcludes in more than one `<pages index=...>` block (front
    matter, then the chapters proper), each becoming its own
    `prp-pages-output` div, so all matches must be kept, not just the first."""
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


def _extract_chapter(html: str) -> str:
    cleaned = _clean_body(html)
    text = _flatten(cleaned)
    text = _LEAD_HEADING.sub("", text)
    return _capitalize_first(text.strip())


def _extract_manual(html: str) -> dict[str, str]:
    cleaned = _clean_body(html)
    delimited = _MANUAL_CHAPTER_HEADING.sub(
        lambda m: f"\x00{_roman_to_int(m.group(1))}\x00", cleaned
    )
    flat = _flatten(delimited)
    parts = flat.split("\x00")
    out: dict[str, str] = {}
    i = 1
    while i + 1 < len(parts):
        chapter, text = parts[i].strip(), parts[i + 1]
        out[chapter] = _capitalize_first(text.strip())
        i += 2
    return _renumber_manual(out)


# The exact sentence opening Long's rendering of modern S 51, inside his
# merged printed section "L." -- the deterministic split point (see module
# docstring). Long's OWN sentence, quoted verbatim from the pinned revision's
# text, not composed: everything before it is modern S 50, it and everything
# after is modern S 51.
_MODERN_51_OPENING = "How long will you then still defer thinking yourself worthy"


def _renumber_manual(out: dict[str, str]) -> dict[str, str]:
    """Re-key Long's printed Encheiridion numbering (1-52) to the modern
    1-53 numbering the Greek spine and Oldfather use (see module docstring):
    split his merged printed 50 into modern 50 + 51 at `_MODERN_51_OPENING`,
    shift his 51 -> 52 and 52 -> 53. Fails loud on any shape surprise."""
    if sorted(int(k) for k in out) != list(range(1, 53)):
        raise ValueError(
            f"Encheiridion renumbering expects exactly Long's printed sections "
            f"1-52, got {len(out)} keys: {sorted(int(k) for k in out)}"
        )
    merged = out["50"]
    if merged.count(_MODERN_51_OPENING) != 1:
        raise ValueError(
            f"split marker matched {merged.count(_MODERN_51_OPENING)} times in "
            f"Long's printed section 50 (expected exactly 1): {_MODERN_51_OPENING!r}"
        )
    cut = merged.index(_MODERN_51_OPENING)
    renumbered = {k: v for k, v in out.items() if int(k) < 50}
    renumbered["50"] = merged[:cut].strip()
    renumbered["51"] = merged[cut:].strip()
    renumbered["52"] = out["51"]
    renumbered["53"] = out["52"]
    return renumbered


def main() -> None:
    discourses: dict[str, str] = {}
    for book, revids in _DISCOURSES_REVISIONS.items():
        print(f"Book {book}: fetching {len(revids)} chapters...")
        for chapter, revid in enumerate(revids, start=1):
            html = _fetch_html(revid)
            discourses[f"{book}.{chapter}"] = _extract_chapter(html)
            time.sleep(1)
        print(f"  Book {book}: {len(revids)} chapters done")

    OUT_DISCOURSES.write_text(
        json.dumps(discourses, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_DISCOURSES} -- {len(discourses)} chapters")

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
