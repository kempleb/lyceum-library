"""One-off: extract Walter Miller's 1913 Loeb translation of Cicero's
*De Officiis* from the Perseus Digital Library's `canonical-latinLit` TEI
XML into a clean {book}.{section}: text JSON map, keyed exactly like the
Latin (PHI/Atzert) book-section spine's dotted column tokens -- see
sources/INVENTORY.md ("De Officiis" section) for full source-verification
detail.

Source: PerseusDL/canonical-latinLit, data/phi0474/phi055/
phi0474.phi055.perseus-eng1.xml, PINNED at commit 1066a551 (2026-07-17
fetch; commit itself dated 2026-06-23, a header-only author/editor fix --
verified byte-identical to the `master` copy fetched the same day). Same
"download once, verify the hash, read locally" shape as
extract_hicks_dl_perseus.py: this script reads the pinned file straight
from sources/miller-de-officiis/ and verifies its SHA-256 against
`_EXPECTED_SHA256` before parsing, so a corrupted or silently-updated local
copy fails loud rather than producing drifted output.

## Edition identity (see INVENTORY.md for the full evidence chain)

The XML's own teiHeader records: author M. Tullius Cicero, translator
Walter Miller, imprint "William Heinemann; G.P. Putnam's Sons, London;
New York, 1913", series "Loeb Classical Library" -- and its own sourceDesc
links straight to `https://archive.org/details/deofficiiswithen00ciceuoft`,
the real 1913 Heinemann scan (catalog title "De officiis. With an English
translation by Walter Miller", `possible-copyright-status: NOT_IN_COPYRIGHT`
/ `copyright-region: US`). Cross-checked independently against Project
Gutenberg #47001 (same translator/publisher/year credited in its own
transcriber's note): its Book I opens "My dear son Marcus, you have now
been studying a full year..." -- verbatim identical to this file's own
1.1 text. No Rouse/Smith-style later-revision risk is known for this
translation (unlike Lucretius' Rouse); this is Miller's original,
unrevised 1913 text.

## Structure

`<div type="textpart" subtype="book" n="1".."3">` (BUT see the Book III `@n`
bug below) containing `<p>` elements with INLINE `<milestone unit="section"
n="...">` markers -- unlike Hicks' Diogenes Laertius (section-level `<div>`
wrappers), a De Officiis section is not its own element: it is the run of
text between one `unit="section"` milestone and the next, which may span
several `<p>` boundaries and does not align with them (e.g. 2.88/2.89 both
fall inside one `<p>`; 1.1's own milestone opens mid-`<p>`). The walk below
threads a single "current section" cursor through the whole book div in
document order, re-pointing it at every `unit="section"` milestone and
appending every other node's flattened text into whichever section is
currently open. Content before the book's first milestone (the `<head>`
title) has no open section and is dropped.

Two other milestone units appear and are BOTH deliberately ignored (no text
of their own; their tail text attaches, correctly, to whichever REAL
section is already open): `unit="chapter"` (Miller's literary chapter
divisions -- I, II, III... -- restart per book and do not match the
citable, continuously-numbered section scheme this script keys on) and
`unit="alternatesection"` (5 occurrences: 1.15, 2.27, 2.56, 2.55, 3.75 --
verified each one sits INSIDE the real, already-open same-numbered
`unit="section"` span, e.g. 1.15's alternatesection milestone falls between
the genuine `n="15"` and `n="16"` section milestones; some second reference
system Perseus's editors overlaid, never load-bearing for Miller's own
citation numbering).

## The Book III `@n="1"` data bug

Perseus's own XML mislabels Book III's div as `<div ... n="1" subtype="book">`
(the SAME `@n` as Book I) -- confirmed by direct inspection, not a
transcription error introduced here. This script does NOT trust `@n` for
book numbering; it assigns book number by DOCUMENT ORDER (1st, 2nd, 3rd
`subtype="book"` div encountered), asserting there are exactly 3.

## Section-count edition gap: Miller's Book II has no 2.90

Book II's milestone sequence is a clean, continuous 1..89 -- there is no
`unit="section" n="90"` anywhere in Book II. The Atzert/PHI Latin spine's
2.90 is the single short sentence "Reliqua deinceps persequemur." ("Let us
now pass on to the remaining problems.") -- and that EXACT sentence is
present in Miller's own English, just folded into the tail of his own 2.89
(no separate marker), as the closing sentence of the paragraph following
the Cato "Bene pascere" exchange. A genuine translator/edition numbering
merge (same shape as Haines' Meditations 5.37 -- see
manifests/meditations.yaml), not an extraction bug: declared in
manifests/de-officiis.yaml as `alignment_allow_unmatched: ["2:2.90"]`.
Every other book-section key (1.1-1.161, 2.1-2.89, 3.1-3.121 = 371 keys) is
present.

## Cleaning conventions applied (mirrors extract_hicks_dl_perseus.py)

- `<note>` (any @type, 392 occurrences: 306 `type="marg"` running-summary
  sidenotes + 86 untyped explanatory footnotes) -- dropped WHOLE, no
  descent: editorial apparatus, never part of the translated prose.
- `<foreign xml:lang="greek">` in the running BODY text (13 occurrences,
  11 distinct strings -- 8 further occurrences sit inside dropped `<note>`
  elements and are already excluded by the note drop above) -- Perseus
  stores these as Beta-Code-like ASCII transliterations (e.g.
  "kato/rqwma," for κατόρθωμα,), not Unicode Greek. Decoded via the small,
  closed, hand-verified `_GREEK_TERMS` table below (every term a standard
  Stoic/ethical technical term whose sense matches its surrounding English
  exactly -- e.g. "the ordinary duty they call καθῆκον" / "what the Greeks
  call εἴρων"). The exact observed string set is asserted against the
  table's keys -- an unexpected string fails loud rather than passing
  through undecoded ASCII.
- `<quote>` WITHOUT "blockquote" in @rend -- wrapped in curly quotes,
  alternating double/single by nesting depth (same convention as Hicks'
  `_OPEN_QUOTE`/`_CLOSE_QUOTE`, since Perseus's data entry, like Hicks',
  carries no literal quote-mark characters for these).
- `<quote rend="...blockquote...">` (24 occurrences -- Cicero quoting verse:
  Ennius, Accius, Terence, Euripides via A. S. Way) -- pass-through, no
  quote marks added (they are typographically set off in the print by
  indentation we have no channel for; content flattened into the running
  section text like everything else, since this is a plain prose
  book-section extraction with no verse-line sidecar). `<l>`, `<sp>`,
  `<speaker>`, `<hi>`, `<cit>`, `<bibl>` are all plain pass-through
  containers (walked for text, no markup applied) -- `<hi rend="italics">`
  loses its italics (no markdown-emphasis convention exists anywhere in
  this corpus's clean.json files; matches established practice) and a
  `<speaker>` name (e.g. "Thyestes.") is kept as ordinary running text
  exactly as printed.
- `<milestone>` and `<pb>` -- no text of their own; both are pure
  section-boundary/page-break markers (already handled above).
- Whitespace: all text is concatenated in document order, then
  `re.sub(r"\\s+", " ", ...)`-collapsed and `.strip()`-ed (Haines-extractor
  convention), plus a light punctuation-adjacency pass that strips any
  space introduced directly before a closing quote mark or terminal
  punctuation (`_TIGHTEN`) -- the source XML has no such stray whitespace
  in practice, but this is cheap insurance against the same class of
  defect Hicks' `_NO_LEADING_SPACE` guards.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import lxml.etree as ET

SRC = Path("../sources/miller-de-officiis/phi0474.phi055.perseus-eng1.xml")
OUT = Path("../sources/miller-de-officiis/miller.clean.json")
PATCHES = Path("../sources/miller-de-officiis/PATCHES.json")

_EXPECTED_SHA256 = "9eb13903d602c40a691954db79b2a0336f9baa0012f3cf3d3ef5374d90f99c86"

_TEI_NS = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI_NS}
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


# Hand-verified Beta-Code-like ASCII -> Unicode Greek decode table for every
# `<foreign xml:lang="greek">` string encountered in the running BODY text
# (i.e. NOT inside a dropped `<note>`) -- see the module docstring. Keyed on
# the exact raw (unstripped-of-punctuation) text, including trailing
# sentence punctuation, since that punctuation is real content to preserve.
_GREEK_TERMS = {
    "kato/rqwma,": "κατόρθωμα,",
    "kaqh=kon.": "καθῆκον.",
    "pre/pon.": "πρέπον.",
    "o(rmh/,": "ὁρμή,",
    "ei)/rwn": "εἴρων",
    "eu)taci/a": "εὐταξία",
    "eu)kairi/a,": "εὐκαιρία,",
    "sofi/a;": "σοφία;",
    "fro/nhsis,": "φρόνησις,",
    "pa/qh": "πάθη",
    "o(rmai/": "ὁρμαί",
}

_OPEN_QUOTE = ("“", "‘")  # curly double / single, by nesting depth
_CLOSE_QUOTE = ("”", "’")


def _is_verse_quote(el: ET._Element) -> bool:
    return _local(el.tag) == "quote" and "blockquote" in (el.get("rend") or "")


class _Ctx:
    """Threaded through one book div's walk: `sections` accumulates a list
    of text fragments per (int) section number; `current` is the section
    number presently open (None before the book's first milestone, when
    only the dropped `<head>` title is in scope); `depth` is the current
    `<quote>` (non-blockquote) nesting depth, for alternating curly-quote
    style."""

    def __init__(self) -> None:
        self.sections: dict[int, list[str]] = {}
        self.current: int | None = None
        self.depth = 0

    def append(self, text: str | None) -> None:
        if not text or self.current is None:
            return
        self.sections[self.current].append(text)


def _last_emitted_char(ctx: _Ctx) -> str | None:
    """Last character already buffered for the open section, or None."""
    if ctx.current is None:
        return None
    parts = ctx.sections.get(ctx.current) or []
    for part in reversed(parts):
        if part:
            return part[-1]
    return None


def _append_after_dropped_note(ctx: _Ctx, tail: str | None) -> None:
    """Append a dropped `<note>`'s tail, inserting a single space when the
    lexical boundary would otherwise glue two alphanumeric runs into one
    word (e.g. `word<note>x</note>word` → `word word`, not `wordword`).
    Later whitespace-collapse handles any double spaces this might create
    when the source already had spacing on one side. The pinned Perseus XML
    has zero such alnum/alnum boundaries (fail-safe hardening only)."""
    if not tail or ctx.current is None:
        return
    prev = _last_emitted_char(ctx)
    if prev is not None and prev.isalnum() and tail[0].isalnum():
        ctx.append(" ")
    ctx.append(tail)


def _walk(el: ET._Element, ctx: _Ctx) -> None:
    tag = _local(el.tag)

    if tag == "note":
        # Editorial apparatus only -- never appears in translated prose.
        # Tail is appended by the parent loop via _append_after_dropped_note.
        return

    if tag == "milestone":
        if el.get("unit") == "section":
            n = int(el.get("n"))
            if n in ctx.sections:
                raise ValueError(
                    f"extract_miller_perseus: duplicate unit=section n={n} "
                    f"within a book (section numbers must be unique per book; "
                    f"got a repeated n={n} while section {n} was already open)"
                )
            ctx.current = n
            ctx.sections[n] = []
        # "chapter" and "alternatesection" milestones: no text, and
        # deliberately do NOT touch ctx.current (see module docstring).
        return

    if tag == "pb":
        return  # page-break marker, no text

    if tag == "foreign" and el.get(_XML_LANG) == "greek":
        raw = (el.text or "").strip()
        if raw not in _GREEK_TERMS:
            raise ValueError(
                f"extract_miller_perseus: unexpected Greek <foreign> string "
                f"{raw!r} in the running body text -- not in the hand-verified "
                f"_GREEK_TERMS decode table; add and verify it before proceeding "
                f"(section {ctx.current})"
            )
        ctx.append(_GREEK_TERMS[raw])
        return  # this corpus's <foreign> elements carry no children

    is_quote = tag == "quote" and not _is_verse_quote(el)
    if is_quote:
        ctx.append(_OPEN_QUOTE[ctx.depth % 2])
        ctx.depth += 1

    ctx.append(el.text)
    for child in el:
        _walk(child, ctx)
        if _local(child.tag) == "note":
            _append_after_dropped_note(ctx, child.tail)
        else:
            ctx.append(child.tail)

    if is_quote:
        ctx.depth -= 1
        ctx.append(_CLOSE_QUOTE[ctx.depth % 2])


# Strips whitespace introduced directly before closing punctuation/quote
# marks after whitespace-collapse -- cheap insurance mirroring Hicks'
# _NO_LEADING_SPACE (this source has no such stray whitespace in practice,
# verified by the extraction's own output, but the rule costs nothing to
# keep general).
_TIGHTEN = re.compile(r"\s+([,;:.!?’”])")

# Miller's literary chapter roman numerals (I, II, XIII, …) sometimes bleed
# into the TEI body text immediately after a section milestone, e.g. 2.44
# opens "(XIII.) But, although…". Strip only a leading parenthesized roman
# label at section start; corpus-checked: exactly one section matches.
_CHAPTER_LABEL = re.compile(r"^\(\s*[IVXLC]+\.\s*\)\s*")


def _clean(parts: list[str]) -> str:
    text = re.sub(r"\s+", " ", "".join(parts)).strip()
    return _TIGHTEN.sub(r"\1", text)


def _strip_leading_chapter_label(text: str) -> tuple[str, bool]:
    """Strip a leading parenthesized roman chapter label, if present.

    Returns (cleaned_text, did_strip).
    """
    stripped = _CHAPTER_LABEL.sub("", text)
    return stripped, stripped != text


# --- hand-verified transcription-slip patches ---------------------------------
# Same fail-loud exact-once-match philosophy as Haines'/Burnet's
# `_apply_patches` / `_apply_raw_patches`: a patch is a claim that its exact
# `old` string occurs EXACTLY ONCE in the named section; if the upstream
# Perseus XML is fixed (or the extraction changes), a stale patch fails the
# build loudly rather than silently no-op'ing. Re-running extraction from
# the pinned source is idempotent (same clean.json every time).
def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_patches(out: dict[str, str], patches: list[dict]) -> dict[str, str]:
    for p in patches:
        chapter = p["chapter"]
        if chapter not in out:
            raise ValueError(
                f"PATCHES.json: chapter {chapter!r} not found in extraction output"
            )
        text = out[chapter]
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: chapter {chapter} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        out[chapter] = text
    return out


def _verify_source() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"missing {SRC} -- fetch from "
            "https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/"
            "1066a551aa5445ab165e9b490a6bb06ce72828da/data/phi0474/phi055/"
            "phi0474.phi055.perseus-eng1.xml and place it there before running."
        )
    actual = hashlib.sha256(SRC.read_bytes()).hexdigest()
    if actual != _EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch for {SRC}: expected {_EXPECTED_SHA256}, got {actual} "
            "-- the pinned commit's file must not have changed; re-verify before proceeding."
        )


def _extract_book(
    book: ET._Element, book_idx: int
) -> tuple[dict[str, str], int, list[str]]:
    """{"<book_idx>.<n>": text} for every section milestone found while
    walking `book` in document order, plus the book's last section number
    and the list of keys whose text had a leading roman chapter label
    stripped. `book_idx` is the CALLER's document-order index (1st/2nd/3rd
    book div encountered) -- never the div's own `@n`, which Book III's
    real data mislabels "1" (see module docstring). Asserts the section
    numbers form a contiguous 1..max run (a real structural invariant:
    Miller's own numbering never skips or restarts mid-book)."""
    ctx = _Ctx()
    _walk(book, ctx)
    nums = sorted(ctx.sections)
    assert nums == list(range(nums[0], nums[-1] + 1)), (
        f"Book {book_idx}: non-contiguous section numbers {nums}"
    )
    assert nums[0] == 1, f"Book {book_idx}: expected section 1 to open the book, got {nums[0]}"
    out: dict[str, str] = {}
    label_keys: list[str] = []
    for n in nums:
        key = f"{book_idx}.{n}"
        text, stripped = _strip_leading_chapter_label(_clean(ctx.sections[n]))
        out[key] = text
        if stripped:
            label_keys.append(key)
    return out, nums[-1], label_keys


def main() -> None:
    _verify_source()
    tree = ET.parse(str(SRC))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    # Document order, NEVER book.get("n") -- Book III's div is mislabeled n="1"
    # (see module docstring). enumerate(..., start=1) is the book index.
    books = body.findall('.//t:div[@subtype="book"]', _NS)
    assert len(books) == 3, f"expected 3 book divs, found {len(books)}"

    out: dict[str, str] = {}
    seen_greek_strings: set[str] = set()
    chapter_label_keys: list[str] = []
    for book_idx, book in enumerate(books, start=1):
        book_out, last, label_keys = _extract_book(book, book_idx)
        out.update(book_out)
        chapter_label_keys.extend(label_keys)
        print(f"  Book {book_idx}: {len(book_out)} sections, 1..{last}")

    # Sanity: every _GREEK_TERMS entry was actually consumed (an unused
    # table entry would mean the docstring's evidence no longer matches the
    # live extraction -- fail loud rather than let the table silently rot).
    for key, text in out.items():
        for greek in _GREEK_TERMS.values():
            if greek in text:
                seen_greek_strings.add(greek)
    unused = set(_GREEK_TERMS.values()) - seen_greek_strings
    if unused:
        raise AssertionError(f"_GREEK_TERMS entries never matched in output: {unused}")

    assert len(out) == 371, f"expected 371 sections (161+89+121), got {len(out)}"

    # Corpus-checked: exactly one section (2.44) carries a leading roman
    # chapter label in the TEI body; strip all matches and report each.
    print(
        f"  chapter-label strips: {len(chapter_label_keys)}"
        + (f" ({', '.join(chapter_label_keys)})" if chapter_label_keys else "")
    )
    if len(chapter_label_keys) != 1:
        raise AssertionError(
            f"expected exactly 1 leading chapter-label strip, got "
            f"{len(chapter_label_keys)}: {chapter_label_keys}"
        )

    patches = _load_patches()
    out = _apply_patches(out, patches)

    OUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {OUT} -- {len(out)} sections"
        + (f" ({len(patches)} hand-verified patch(es) applied)" if patches else "")
    )


if __name__ == "__main__":
    main()
