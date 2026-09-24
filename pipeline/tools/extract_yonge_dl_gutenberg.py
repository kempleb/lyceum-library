"""One-off: extract Charles Duke Yonge's 1853 (this printing: 1915 Bell
reprint) translation of Diogenes Laertius from Project Gutenberg #57342 into
a clean JSON map -- see sources/INVENTORY.md ("Diogenes Laertius" section)
for full source-verification detail.

## Why Life-level keying, not book.section (measured, not assumed)

The sibling Hicks extractor (extract_hicks_dl_perseus.py) keys "book.section"
directly off the Greek/Loeb Bekker-style section apparatus. Yonge's own
inline markers -- Roman numerals (I., II., III. ...) restarting at I for
each philosopher's "LIFE OF X." -- LOOK like the same kind of section
apparatus, and the original brief for this script assumed a Life-relative
cumulative-sum mapping onto Hicks's book.section keys (Yonge's Nth Roman
numeral within a Life = Hicks's chapter-start-section + N - 1) would work.

It does not. Measured directly: chapter-COUNT reconciles perfectly (83
"LIFE OF X."/"INTRODUCTION." headers, in the same order as Hicks's 83
chapters -- confirmed by both position and by comparing philosopher names),
but each Life's Roman-numeral COUNT is essentially uncorrelated with the
corresponding Hicks chapter's section count: 78 of 83 chapters have a
DIFFERENT count (e.g. Zeno: Hicks 159 sections vs Yonge 86 Roman numerals;
Epicurus: Hicks 154 vs Yonge 31; Thales: Hicks 23 vs Yonge 16). Yonge's
numbering is evidently the Bohn translator's own independent paragraph
enumeration, not tied to the Loeb/Bekker apparatus at all -- so a
cumulative-sum mapping would silently drift out of alignment within the
FIRST chapter of every book and produce systematically wrong keys. This
was reported to the orchestrator rather than shipped silently; the
resulting decision was to key at Life granularity instead: one chunk per
philosopher, at "<book>.<start_section>" using the SAME start_section
Hicks's chapter uses (i.e. matching the key that opens the corresponding
Hicks chapter) -- so Yonge remains fully addressable and alignable at the
work's natural navigation unit (which philosopher), just not at
Hicks/Greek section granularity within a Life. See this script's return to
the orchestrator for the chapter-count and per-Life length-correlation
evidence (Pearson r against Hicks's own per-chapter character counts).

## Structure (see INVENTORY.md)

Single-language plain text. Each book opens on its own flush-left
"BOOK <ROMAN>." line; each philosopher's Life opens on its own flush-left
"LIFE OF <NAME>." line (Book I's opening front-matter Life is
"INTRODUCTION." instead; two Cynic-school "MENEDEMUS" Lives are spelled
"THE LIFE OF MENEDEMUS." -- the "(?:THE )?" in `_HEADER` covers both).
Footnote references are bracketed digits ("[12]") inline in the body,
resolved in one big "FOOTNOTES" section after Book X (not interleaved
per-book) -- so this script just slices the body off before that heading
and strips the inline markers, no per-book footnote-vs-verse disambiguation
needed (contrast extract_long.py's Meditations problem, where Long's
footnotes and verse insets share one indent convention and must be told
apart by content). Verse epitaphs are set off only by indentation, no
tagging -- flattened into the surrounding prose like every other clean
JSON in this repo (verse-vs-prose rendering is a sidecar concern, and only
Hicks gets one, per the brief). Gutenberg's plain-text italics markup
(`_word_`) is stripped to bare words.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SRC = Path("../sources/yonge-dl/pg57342.txt")
HICKS_NAMES = Path("../sources/hicks-dl/lives-names.json")
OUT = Path("../sources/yonge-dl/yonge-lives.clean.json")

_EXPECTED_SHA256 = "0176dd702dfcc4a11d355475cab857f2a521a72dc316ecd8921ef12a0495c5a1"

_HEADER = re.compile(r"^(?:THE )?LIFE OF |^INTRODUCTION\.$")
_FOOTNOTE_MARKER = re.compile(r"\[\d+\]")
_SECTION_NUMERAL = re.compile(r"^[IVXLCDM]+\.\s+")
_ITALIC = re.compile(r"_([^_]+)_")
_WS = re.compile(r"\s+")


def _verify_source() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"missing {SRC} -- fetch from "
            "https://www.gutenberg.org/cache/epub/57342/pg57342.txt "
            "and place it there before running."
        )
    actual = hashlib.sha256(SRC.read_bytes()).hexdigest()
    if actual != _EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch for {SRC}: expected {_EXPECTED_SHA256}, got {actual} "
            "-- Project Gutenberg text can be silently updated; re-verify before proceeding."
        )


def _clean_chunk(lines: list[str]) -> str:
    """Drop the header line itself, strip footnote markers/section-numeral
    markers/italic underscores per line, then join with single spaces --
    same "verse flattened into prose" policy as every other clean JSON."""
    kept = []
    for line in lines[1:]:  # [0] is the "LIFE OF X."/"INTRODUCTION." header
        line = _SECTION_NUMERAL.sub("", line.strip())
        if line:
            kept.append(line)
    text = " ".join(kept)
    text = _FOOTNOTE_MARKER.sub("", text)
    text = _ITALIC.sub(r"\1", text)
    return _WS.sub(" ", text).strip()


def main() -> None:
    _verify_source()
    lines = SRC.read_text(encoding="utf-8").split("\n")

    book1_start = next(i for i, l in enumerate(lines) if l == "BOOK I.")
    footnotes_start = next(i for i, l in enumerate(lines) if l.strip() == "FOOTNOTES")
    body = lines[book1_start:footnotes_start]

    header_idx = [i for i, l in enumerate(body) if _HEADER.match(l.strip())]
    hicks_names = json.loads(HICKS_NAMES.read_text(encoding="utf-8"))
    assert len(header_idx) == len(hicks_names), (
        f"chapter-count mismatch: Yonge has {len(header_idx)} Life headers, "
        f"Hicks has {len(hicks_names)} chapters -- re-verify before keying"
    )

    # Three of Hicks's 83 chapter-start keys are shared by TWO consecutive
    # philosophers (2.124: Glaucon/Simmias; 2.125: Cebes/Menedemus; 8.84:
    # Hippasus/Philolaus) -- an unavoidable consequence of the Hicks
    # merge-by-duplicate-section-number rule (see extract_hicks_dl_perseus.py):
    # both Lives' OWN opening content happened to fall inside the same
    # merged Hicks/Greek column, since that column spans a chapter boundary.
    # A naive dict write would silently drop one Life's text; concatenate
    # instead so nothing is lost, and flag the collision below.
    lives: dict[str, str] = {}
    collisions: list[str] = []
    for i, idx in enumerate(header_idx):
        end = header_idx[i + 1] if i + 1 < len(header_idx) else len(body)
        chunk = body[idx:end]
        entry = hicks_names[i]
        key = f"{entry['book']}.{entry['start_section']}"
        text = _clean_chunk(chunk)
        if key in lives:
            collisions.append(f"{key} ({entry['name']})")
            lives[key] = lives[key] + " " + text
        else:
            lives[key] = text

    OUT.write_text(
        json.dumps(lives, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    total_chars = sum(len(v) for v in lives.values())
    print(f"wrote {OUT} -- {len(lives)} Lives, {total_chars} chars")
    if collisions:
        print(f"key collisions merged (see module docstring): {collisions}")


if __name__ == "__main__":
    main()
