"""One-off: extract R. D. Hicks's 1925 Loeb translation of Diogenes Laertius,
*Lives of Eminent Philosophers*, from the Perseus Digital Library's
`canonical-greekLit` TEI XML into a clean {book}.{section}: text JSON map, a
verse-range sidecar, and a chapter-name outline -- see sources/INVENTORY.md
("Diogenes Laertius" section) for full source-verification detail.

Source: PerseusDL/canonical-greekLit, data/tlg0004/tlg001/
tlg0004.tlg001.perseus-eng2.xml, PINNED at commit 299a8af2 (2026-07-16 fetch).
Rather than a live re-fetch per run (the Wikisource scrapers' pattern, needed
there because ProofreadPage assembly isn't reproducible from a bare wikitext
GET), this script reads the pinned file straight from the repo at
sources/hicks-dl/tlg0004.tlg001.perseus-eng2.xml -- the same "download once,
verify the hash, read locally" shape as extract_long.py's PG text -- and
verifies its SHA-256 against `_EXPECTED_SHA256` before parsing, so a
corrupted or silently-updated local copy fails loud rather than producing
drifted output.

## Structure (see INVENTORY.md for the full TEI shape)

`<div type="textpart" subtype="book" n="1".."10">` > (`subtype="chapter"`,
one per philosopher's Life, `<head>` gives the display name) >
`subtype="section" n="<Bekker-style number>"`. Section content is one or
more `<p>`; footnotes are `<note resp="editor">` inline (dropped entirely --
editorial apparatus, not translated text); verse epigrams are
`<quote rend="...blockquote...">` with empty `<l/>` line-break markers
scattered through their running text (see `_is_verse_quote`). A handful of
book-title *lists* (bibliographies of a philosopher's works) also use `<l>`,
but as a normal container with real text content, inside a plain `<p
rend="align(indent)">` -- NOT inside a `<quote>` -- so the verse-vs-list
distinction is exactly "is this the closest `<quote rend=~blockquote>`
ancestor", not "does it contain `<l>`" (spot-checked: 55 such p/l title-list
paragraphs exist and are correctly excluded from the verse sidecar by this
rule). A few verse `<quote>`s carry `rend="blockquote; merge"` -- Perseus's
own signal that the epigram continues from/into an *adjacent section's*
quote (a poem interrupted by a section boundary); this script does not
attempt cross-section verse reconstruction (out of the per-section sidecar's
scope) and just records each `<quote>` as its own self-contained range
within whatever section contains it.

## The five doubled Greek section numbers (2.125, 7.160, 7.166, 8.83, 8.84)

The Greek spine (H. S. Long's TLG/OCT text, exported locally via Diogenes --
see docs/tlg-phi-export.md) numbers five sections twice each (a chapter
boundary falling mid-Bekker-section: the closing lines of one philosopher's
Life and the opening lines of the next share one section number). Hicks's
own TEI section `n` attributes ALREADY mirror this directly -- Perseus
encodes the doubled (and, at 2.124, even TRIPLED -- see below) Greek content
as multiple consecutive `<div subtype="section">` elements carrying the
IDENTICAL `n` value, not as distinctly-incremented numbers. This directly
contradicts this script's original brief, which assumed Hicks numbers
post-double sections distinctly and would need a derived per-book numeric
offset map -- empirical inspection of the actual TEI shows otherwise (see
the reconciliation note returned to the orchestrator). The fix is simply:
merge every run of consecutive same-`n` section divs within a book into one
key, concatenating their text in document order. This was verified
book-by-book against the Greek spine's own merged (duplicate-collapsed)
section-number sets: books 1-9 match EXACTLY, element for element, with no
offset needed at all. Book 2's `n="124"` is a genuine oddity worth flagging
explicitly: it appears THREE times in Hicks/Perseus (Simon-the-physician
coda, Glaucon, Simmias) even though the Greek's own `2.124` is a SINGLE,
non-doubled section -- i.e. Hicks/Perseus split one Greek section into three
XML divs for editorial (paragraph-per-biographee) convenience. The uniform
merge-by-n rule handles this identically to the genuine doubles (any run of
2+ same-n divs collapses to one key) and was content-verified against the
Greek (proper-name correspondence: Simon/Glaucon/Simmias all fall within
the Greek's single 2.124 div).

## Book 10's two "gaps" (10.120, 10.121)

The Greek spine's Long OCT text marks a well-known manuscript leaf
transposition in the Epicurus doxographical epitome with FOUR lettered
sections in manuscript order -- 120a, 121b, 120b, 121a -- instead of plain
120/121. Hicks's own numbering is plain and contiguous (120, 121), already
resolved into the standard scholarly reading order: content-verified
directly (Hicks 120 opens "He will leave written words behind him..." =
Greek 120a's "καὶ ... συγγράμματα καταλείψειν"; Hicks 121 opens "Two sorts
of happiness can be conceived..." = Greek 121a's "Τὴν εὐδαιμονίαν διχῆ
νοεῖσθαι" and Hicks 121 ends at the Letter to Menoeceus's salutation, same
as Greek 121a). Since the Greek spine's plain-numeric column set has no
bare "120" or "121" entry for book 10 (only the lettered fragments), these
two Hicks keys are recorded as allowances with no direct Greek spine
counterpart -- not a defect, just a numbering-scheme mismatch at a known
textual crux. No special-casing needed in this script: Hicks's own section
numbers are used as-is, and this gap is purely a fact about the *Greek*
spine's key set, documented for the manifest-allowance list.

## Verse-offset sidecar

`hicks-verse.json` maps each "book.section" key (only where verse is
present) to a list of `{start, end, breaks}` char-offset ranges over that
key's EXACT final flattened text in `hicks-lives.clean.json`. Offsets are
computed by an incremental whitespace-collapsing buffer (see `_Builder`)
rather than collapsing-then-searching, so they are correct by construction
against the actual emitted string -- no separate offset-remapping pass is
needed, and `main()` asserts every range's invariants (non-empty slice,
breaks strictly inside the range) before writing.
"""
from __future__ import annotations

import hashlib
import json
import re
from itertools import groupby
from pathlib import Path

import lxml.etree as ET

SRC = Path("../sources/hicks-dl/tlg0004.tlg001.perseus-eng2.xml")
OUT_LIVES = Path("../sources/hicks-dl/hicks-lives.clean.json")
OUT_VERSE = Path("../sources/hicks-dl/hicks-verse.json")
OUT_NAMES = Path("../sources/hicks-dl/lives-names.json")

_EXPECTED_SHA256 = "f53a4d376bb8bcc02547ecc46f9865855ed434ccc1b991baeb1254ce0d6086a3"

_TEI_NS = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI_NS}


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _is_verse_quote(el: ET._Element) -> bool:
    return _local(el.tag) == "quote" and "blockquote" in (el.get("rend") or "")


def _is_inline_quotation(el: ET._Element) -> bool:
    """`<q>` (1,596 uses) and the small minority of `<quote>` NOT flagged
    verse (10 uses -- e.g. a prose doctrinal excerpt) both mark direct
    quotation rendered inline within running prose. Perseus's own
    `<quotation marks="none"/>` editorial declaration means NO literal
    quote-mark character appears anywhere in the corpus text -- confirmed
    by a direct sweep (zero straight OR curly quote characters in the
    body's `itertext()`, only U+2019 apostrophes) -- so without adding
    marks here, direct speech and quoted doctrine would read as
    unpunctuated run-on prose. `_walk` wraps these in curly quotes,
    alternating double/single by nesting depth (42 of the 1,596 `<q>`s
    nest one level deep) to match ordinary English quotation typography."""
    tag = _local(el.tag)
    return tag == "q" or (tag == "quote" and not _is_verse_quote(el))


def _is_empty_line_break(el: ET._Element) -> bool:
    """An `<l/>` used as an in-line verse line-break marker: no text, no
    children. (Contrast the book-title-list `<l>PLAY TITLE.</l>` usage,
    which always has text content and is walked as ordinary prose.)"""
    return _local(el.tag) == "l" and not (el.text and el.text.strip()) and len(el) == 0


# Never legitimately preceded by a space in English typography, so a
# pending separator space gets DROPPED (not materialized) right before one
# of these -- rather than emitted -- regardless of why it was pending.
# Covers two real corpus artifacts, both spot-checked to ground-truth
# during development: (1) a lone stray XML whitespace character sitting
# between a dropped `<pb/>` page-break marker and the comma that follows it
# ("book 3.62"'s "...Horse-breeder , the Eryxias..." -> "...Horse-breeder,
# the Eryxias..."); (2) FAR more commonly, this script's OWN inserted
# closing quote marks (U+2019/U+201D -- see `_OPEN_QUOTE`/`_CLOSE_QUOTE`)
# landing after a pending space left by the quoted text's own trailing
# whitespace, which would otherwise print as "...the will. ”" instead of
# the correct "...the will.”". Deliberately does NOT include "." -- Hicks
# uses genuine SPACED ellipsis dots (". . .") to mark manuscript lacunae,
# which must be preserved as-is.
_NO_LEADING_SPACE = frozenset(",;:’”")


class _Builder:
    """Incrementally collapses whitespace while building flattened text, so
    every offset recorded during the walk is already a valid index into the
    FINAL string -- no post-hoc remap needed. A run of whitespace becomes a
    single pending space, materialized only once a following non-space
    character actually arrives (never at the very start, and never at all
    if nothing more follows) -- so leading and trailing whitespace are
    dropped for free, and never right before `_NO_LEADING_SPACE` punctuation.

    A pending space can span MULTIPLE separate `append()` calls (e.g. a
    dropped `<note>`'s tail whitespace, immediately followed by a verse
    `<quote>`'s own leading whitespace before its first real child) and
    must still collapse to exactly one character -- so `pos()` (the true
    committed length) is NOT what a verse range's "start" should record.
    `next_pos()` instead reports where the NEXT real character would land
    -- `pos()` plus one if a space is still owed -- without committing
    anything, so two still-pending whitespace runs correctly collapse into
    the single separator space that eventually materializes, rather than
    each contributing its own character (which an earlier, eager
    "materialize now" implementation got wrong: see the git history of
    this file for the double-space bug that caught)."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._length = 0
        self._pending_space = False

    def pos(self) -> int:
        return self._length

    def next_pos(self) -> int:
        return self._length + (1 if self._pending_space else 0)

    def drop_trailing(self, ch: str) -> None:
        """Remove the single most-recently-committed character if it
        equals `ch`, regardless of any pending (not-yet-materialized)
        separator space queued after it. Used for the stray literal ">"
        Perseus's data entry left immediately before two verse quotes (a
        leftover printer's-mark artifact, not real prose -- see `_walk`)."""
        if not self._parts:
            return
        last = self._parts[-1]
        if last.endswith(ch):
            trimmed = last[:-1]
            self._length -= 1
            if trimmed:
                self._parts[-1] = trimmed
            else:
                self._parts.pop()

    def append(self, raw: str | None) -> None:
        if not raw:
            return
        out = []
        pending = self._pending_space
        for ch in raw:
            if ch.isspace():
                if self._length > 0 or out:
                    pending = True
            else:
                if pending and ch not in _NO_LEADING_SPACE:
                    out.append(" ")
                pending = False
                out.append(ch)
        if out:
            s = "".join(out)
            self._parts.append(s)
            self._length += len(s)
        self._pending_space = pending

    def text(self) -> str:
        return "".join(self._parts)


_OPEN_QUOTE = ("“", "‘")  # double at even nesting depth, single at odd
_CLOSE_QUOTE = ("”", "’")


def _walk(
    el: ET._Element,
    buf: _Builder,
    verse_ranges: list[dict],
    verse_stack: list[dict],
    quote_depth: list[int],
) -> None:
    tag = _local(el.tag)
    if tag == "note":
        return  # editorial apparatus only -- never appears in translated prose
    if _is_empty_line_break(el):
        if verse_stack:
            # A handful of epigrams open with an `<l/>` marker before any
            # text (e.g. "1.30"'s Myson couplet), which would otherwise
            # record a break at the exact same offset as the range's own
            # start; filtered out below once "end" is known (a break must
            # be strictly inside (start, end), same rule for a trailing one).
            verse_stack[-1]["breaks"].append(buf.pos())
        return

    entry: dict | None = None
    is_inline_quote = _is_inline_quotation(el)
    if _is_verse_quote(el):
        buf.drop_trailing(">")  # stray Perseus data-entry artifact -- see _Builder.drop_trailing
        entry = {"start": buf.next_pos(), "breaks": []}
        verse_stack.append(entry)
    elif is_inline_quote:
        buf.append(_OPEN_QUOTE[quote_depth[0] % 2])
        quote_depth[0] += 1

    buf.append(el.text)
    for child in el:
        _walk(child, buf, verse_ranges, verse_stack, quote_depth)
        buf.append(child.tail)

    if entry is not None:
        entry["end"] = buf.pos()
        entry["breaks"] = [b for b in entry["breaks"] if entry["start"] < b < entry["end"]]
        verse_stack.pop()
        verse_ranges.append(entry)
    elif is_inline_quote:
        quote_depth[0] -= 1
        buf.append(_CLOSE_QUOTE[quote_depth[0] % 2])


def _flatten(divs: list[ET._Element]) -> tuple[str, list[dict]]:
    """Flatten one or more section divs (a merge-group of same-`n` divs, or
    a single `<head>`) into one continuous string, with an inter-div space
    separator so merged divs don't run words together."""
    buf = _Builder()
    verse_ranges: list[dict] = []
    verse_stack: list[dict] = []
    quote_depth = [0]
    for i, div in enumerate(divs):
        if i > 0:
            buf.append(" ")
        _walk(div, buf, verse_ranges, verse_stack, quote_depth)
    text = buf.text()
    assert text == text.strip(), "flattened text has leading/trailing whitespace"
    return _capitalize_first(text), verse_ranges


def _capitalize_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch.isalpha():
            return text[:i] + ch.upper() + text[i + 1:]
        if not ch.isspace():
            break
    return text


_CHAPTER_PREFIX = re.compile(r"^(?:Chapter\s+\d+\.?\s*)?(.+)$", re.DOTALL)


def _chapter_name(head_text: str) -> str:
    body = _CHAPTER_PREFIX.match(head_text).group(1)
    return re.split(r"[\(\[]", body, maxsplit=1)[0].strip()


def _verify_source() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"missing {SRC} -- fetch from "
            "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/"
            "299a8af276c31f407e7f0f75dde516bdd4376d7a/data/tlg0004/tlg001/"
            "tlg0004.tlg001.perseus-eng2.xml and place it there before running."
        )
    actual = hashlib.sha256(SRC.read_bytes()).hexdigest()
    if actual != _EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch for {SRC}: expected {_EXPECTED_SHA256}, got {actual} "
            "-- the pinned commit's file must not have changed; re-verify before proceeding."
        )


# Emendations of transcription defects inherited from the Perseus digitization.
# Each entry: key -> (defective substring, corrected substring); the defect must
# occur exactly once in that key's flattened text. Corrected keys must carry no
# verse ranges (offsets are computed on the uncorrected text).
_TEXT_CORRECTIONS = {
    # Perseus's own transcription carries the identical "Anbaxagoras" in the
    # identical sentence; Wikisource and the 35 other occurrences in this
    # volume read "Anaxagoras". OCR artifact, not the 1925 print.
    "9.35": ("Anbaxagoras", "Anaxagoras"),
}


def main() -> None:
    _verify_source()
    tree = ET.parse(str(SRC))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    books = body.findall('.//t:div[@subtype="book"]', _NS)
    assert len(books) == 10, f"expected 10 books, found {len(books)}"

    lives: dict[str, str] = {}
    verse: dict[str, list[dict]] = {}
    names: list[dict] = []

    for book in books:
        book_n = int(book.get("n"))

        for chapter in book.findall('t:div[@subtype="chapter"]', _NS):
            head = chapter.find("t:head", _NS)
            head_text, _ = _flatten([head]) if head is not None else ("", [])
            secs = chapter.findall('.//t:div[@subtype="section"]', _NS)
            start_section = int(secs[0].get("n"))
            names.append({
                "book": book_n,
                "start_section": start_section,
                "name": _chapter_name(head_text) if head_text else "",
            })

        section_divs = book.findall('.//t:div[@subtype="section"]', _NS)
        for n, group in groupby(section_divs, key=lambda d: d.get("n")):
            group_divs = list(group)
            key = f"{book_n}.{n}"
            text, ranges = _flatten(group_divs)
            if key in _TEXT_CORRECTIONS:
                bad, good = _TEXT_CORRECTIONS[key]
                assert text.count(bad) == 1, f"{key}: expected exactly one {bad!r}"
                assert not ranges, f"{key}: corrections forbidden on verse-bearing keys"
                text = text.replace(bad, good)
            lives[key] = text
            if ranges:
                verse[key] = ranges

    # -- Validate verse sidecar invariants against the actual emitted text --
    for key, ranges in verse.items():
        full_text = lives[key]
        for r in ranges:
            assert 0 <= r["start"] < r["end"] <= len(full_text), (key, r)
            assert full_text[r["start"]:r["end"]].strip(), f"{key}: empty verse range {r}"
            for b in r["breaks"]:
                assert r["start"] < b < r["end"], f"{key}: break {b} not strictly inside {r}"

    OUT_LIVES.write_text(
        json.dumps(lives, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    OUT_VERSE.write_text(
        json.dumps(verse, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    OUT_NAMES.write_text(
        json.dumps(names, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

    total_ranges = sum(len(r) for r in verse.values())
    print(f"wrote {OUT_LIVES} -- {len(lives)} sections")
    print(f"wrote {OUT_VERSE} -- {len(verse)} keys, {total_ranges} verse ranges")
    print(f"wrote {OUT_NAMES} -- {len(names)} chapters")


if __name__ == "__main__":
    main()
