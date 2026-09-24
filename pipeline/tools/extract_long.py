"""One-off: extract George Long's 1862 Meditations translation (Project
Gutenberg #15877, pre-cleaned to sources/long-meditations/pg15877.clean.txt —
see sources/INVENTORY.md) into a clean {book}.{chapter}: text JSON map,
keyed exactly like the Greek book-section spine's dotted column tokens.

Structure (see INVENTORY.md): each of the 12 books opens on its own line
holding only a Roman numeral + period ("I.", ... "XII."); within a book,
sections are numbered inline "N." at the start of the section (the first
section after the book head is unnumbered/implicit "1"). Long's own
footnotes are 4-space-indented blocks interleaved directly in the running
text (not page-bottom notes) — skipped entirely, along with each inline
"[A]"-style reference-letter marker in the kept prose.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SRC = Path("../sources/long-meditations/pg15877.clean.txt")
OUT = Path("../sources/long-meditations/long.clean.json")

_BOOK_HEAD = re.compile(r"^([IVXLC]+)\.\s*$")
_SECTION_HEAD = re.compile(r"^(\d{1,2})\.\s+(.*)$")
_REF_MARKER = re.compile(r"\[[A-Z0-9]+\]")

# A caption dropped straight into the running text by the Gutenberg scan
# ("[Illustration: THE FORUM]") — never Long's or Marcus' own words, always a
# standalone flush-left line; stripped wherever it appears (mid-chapter or
# between chapters).
_ILLUSTRATION = re.compile(r"^\[Illustration:")

# Long typesets a translated-verse inset (Homer/Hesiod/the tragedians, quoted
# inside a chapter's prose) with the SAME 4-space indent as his footnotes, so
# the indent alone can't tell them apart (see the module docstring's footnote
# description and INVENTORY.md). Two content signals resolve it:
#
# * `_FOOTNOTE_LETTER` — Long's footnote paragraphs always open "[A] ...",
#   "[B] ...": a bracket letter no genuine verse or body sentence ever opens
#   with. This is checked regardless of indentation, because one footnote
#   (under 7.45) lost its leading spaces somewhere between the 1862 print and
#   the Gutenberg transcription — its "[A]/[B]/[C] See ..."/"From the ..."
#   lines sit flush left, otherwise indistinguishable from body prose by
#   indentation.
# * `_FOOTNOTE_CITE` — a citation line that is NOT bracket-lettered: Long
#   sometimes sets a verse inset's source attribution on its own indented
#   line directly under the quotation ("HESIOD, _Works, etc_. v. 197.",
#   "_Odyssey_, ix. 413.") rather than folding it into a lettered footnote.
#   Shape: "See ...", "From [the] <Capitalized>...", or a bare
#   Name-comma-locator line ending in a classical citation number (roman
#   numeral + arabic, or a trailing bare number) — never how a translated
#   verse line itself reads (verse is a sentence/clause, not a citation).
#
# Once either fires, `extract`'s `footnote_mode` latches so a footnote's own
# indented continuation (its prose wrap, or a nested illustrative quotation
# such as 7.40's footnote translating Euripides into Latin) stays excluded
# even though those continuation lines don't themselves look like citations;
# the latch clears on the next UNINDENTED line (Long's footnotes are always
# all-indented paragraphs, so an unindented line always means the running
# text — sometimes the SAME chapter's own prose, resuming right after the
# footnote, e.g. 11.6) or the next chapter marker.
_FOOTNOTE_LETTER = re.compile(r"^\[[A-Z]\]\s")
_FOOTNOTE_CITE = re.compile(
    r"^See\s"
    r"|^From\s(?:the\s)?[A-Z]"
    r"|^_?[A-Z][A-Za-z.'’]*_?,.*\d[.,]?$"
)
# A page with only one footnote is sometimes marked with a bare "+" or "*"
# instead of "[A]", glued straight onto the end of the word it annotates
# (e.g. "agreeable\nway.+"); the lookbehind keeps this from ever touching a
# "+"/"*" that opens its own token.
_BARE_REF_MARKER = re.compile(r"(?<=[A-Za-z.,;:!?'’])[+*]")
_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _roman_to_int(s: str) -> int:
    total = prev = 0
    for ch in reversed(s):
        v = _ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


_TRAILING_REF_MARKER = re.compile(r"\s+[+*]$")


def _clean(line: str) -> str:
    text = _BARE_REF_MARKER.sub("", _REF_MARKER.sub("", line))
    return _TRAILING_REF_MARKER.sub("", text).strip()


def extract(text: str) -> dict[str, str]:
    lines = text.split("\n")
    # Locate the 12 book headers in sequence (guards against a stray Roman
    # numeral elsewhere, e.g. in the front-matter essays or back-matter index).
    book_starts: list[tuple[int, int]] = []  # (book_n, line_index)
    expected = 1
    for i, ln in enumerate(lines):
        m = _BOOK_HEAD.match(ln)
        if m and _roman_to_int(m.group(1)) == expected:
            book_starts.append((expected, i))
            expected += 1
        if expected > 12:
            break
    if len(book_starts) != 12:
        raise ValueError(f"found {len(book_starts)}/12 book headers: {book_starts}")

    # Book XII's text is followed by the volume's back matter — the indexes —
    # NOT by "THE END.", which closes the whole volume only after the indexes
    # (~660 lines further on). Bounding book XII at "THE END." therefore sweeps
    # the entire "INDEXES." / "INDEX OF TERMS." apparatus into 12.36 (18.5k
    # chars vs the real ~660). The Meditations proper ends where the first index
    # section ("INDEXES.") begins, so that heading is the true terminator.
    end_marker = next(i for i, ln in enumerate(lines)
                      if ln.strip() == "INDEXES." and i > book_starts[-1][1])
    bounds = [start for _, start in book_starts] + [end_marker]

    out: dict[str, str] = {}
    for (book_n, _), start, stop in zip(book_starts, bounds, bounds[1:]):
        chapter = 1
        buf: list[str] = []
        started = False
        footnote_mode = False  # inside a footnote/citation block? (see module docstring)
        for ln in lines[start + 1:stop]:
            stripped = ln.strip()
            if not stripped:
                continue  # a blank does not clear footnote_mode — see docstring
            if _ILLUSTRATION.match(stripped):
                continue  # scan caption, never body — see _ILLUSTRATION
            if _FOOTNOTE_LETTER.match(stripped):
                footnote_mode = True
                continue
            m = _SECTION_HEAD.match(stripped)
            if m and (int(m.group(1)) == chapter + 1 or (not started and int(m.group(1)) == 1)):
                if started:
                    out[f"{book_n}.{chapter}"] = " ".join(buf).strip()
                    chapter += 1
                buf = [_clean(m.group(2))]
                started = True
                footnote_mode = False
                continue
            if ln.startswith("    "):  # indented: verse inset, or footnote text
                if footnote_mode or _FOOTNOTE_CITE.search(stripped):
                    footnote_mode = True
                    continue
                buf.append(_clean(stripped))
                continue
            # Unindented body line: always exits any footnote block — Long's
            # footnotes are all-indented paragraphs (bar the bracket-lettered
            # ones caught above), so an unindented line is always the running
            # text, sometimes the SAME chapter resuming right after its own
            # footnote (e.g. 11.6).
            footnote_mode = False
            if not started:
                # Book's implicit first section: content before any "1." marker.
                started = True
            buf.append(_clean(stripped))
        if started and buf:
            out[f"{book_n}.{chapter}"] = " ".join(buf).strip()
    return out


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    out = extract(text)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {OUT} — {len(out)} chapters")


if __name__ == "__main__":
    main()
