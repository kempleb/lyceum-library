"""One-off: extract H. Rackham's 1914 Loeb translation of Cicero's *De
Finibus Bonorum et Malorum* from the archive.org OCR scan/word-level XML
into a clean {book, section, chapter, text} JSON list, keyed at SECTION
granularity against the Latin spine (1:1-72, 2:1-119, 3:1-76, 4:1-80,
5:1-96 -- 443 sections total).

## Sources (see sources/rackham-fin/README.md for full identity/PD evidence)

Primary witness: archive.org item `CiceroRackhamDeFinibusBonorumEtMalorum`
("Cicero - Rackham - De_Finibus_Bonorum_Et_Malorum" -- title page reads
"WITH AN ENGLISH TRANSLATION BY H. RACKHAM, M.A. ... MCMXIV"). This script
reads the item's word-level `_djvu.xml` (WORD coords + text, grouped
PAGE/PAGECOLUMN/REGION/PARAGRAPH/LINE) rather than the flattened
`_djvu.txt`, because per-page boundaries and per-word geometry are the only
way to reliably separate this edition's THREE interleaved streams on every
English recto page: (1) the translated body text, (2) a Latin verso
"ghost" is NOT actually present here (Latin lives on its own separate
physical pages, cleanly excluded by the LATIN/ENGLISH page classifier
below), and (3) a genuine, book-specific defect -- every English page also
carries short marginal "argument" glosses (e.g. "Preface: choice of
subject defended;") typeset in a smaller face in the outer margin, which
this OCR pass merges into the SAME <LINE> as the body words at that
y-position with normal-looking inter-word spacing (verified against the
Loebolus L040 page image -- see README). No general geometric signal
(x-gap, glyph height) cleanly separates gloss tokens from body tokens in
this scan; `_GARBAGE_TOKEN` catches the majority of gloss fragments by
their OCR-corruption signature (stray '^'/'«', or an internal
lowercase-to-uppercase glyph transition no genuine body word has), and the
required proofing pass (README) hand-verifies/patches the sampled
sections against the second witness for whatever a purely lexical filter
cannot catch.

Second witness (proofing): Loebolus L040 PDF
(https://ryanfb.xyz/loebolus-data/L040.pdf), the PD-curated first-edition
scan of the same volume ("Digitized by Google" -- a different physical
scan than the archive.org item, confirmed by a stable +3 page offset
between the two: archive.org page N == Loebolus PDF page N+3 for every
Book-opening title page checked). Used for the proofing pass and for
visually resolving section-marker gaps this OCR pass cannot recover cleanly.

## Page classification

Each `<OBJECT>` in the XML is one physical page. Book boundaries are the
five Latin title pages ("LIBER PRIMUS".."LIBER QUINTUS", found once each);
INDEX_START is the page where the back-of-book Index begins. Within a
book's page range, each page is classified LATIN vs ENGLISH by a stopword
vote (`_ENG_STOP` vs `_LAT_STOP` word-frequency, ~10:1 margins in
practice) rather than by parsing the (heavily OCR-garbled: "CICBRO DB
FINIBUS", "BOOK H. XXXV", etc.) running head text directly -- head-text
regex matching was tried first and under-recovered roughly half the true
English pages before this fix.

## Section-marker recovery (the hard part)

The printed marginal Arabic section number is usually (not always) OCR'd
as the leading token of whichever raster line it sits beside, e.g. "2 of
my character and position." This scan's numeral OCR is itself unreliable
(digits split apart, "33"/"34" misread as "13"/"14", stray page-footer
numbers interleaved), so a naive "must equal previous+1" scan derails
permanently on the first miss (confirmed empirically: on the *_djvu.txt*
flat OCR, that naive approach recovers as few as 2 of 119 Book II
sections). Recovery here is a Longest Common Subsequence alignment
(`_lcs_align`) between the fixed target list [2..N] and the observed
candidate values in true reading order -- LCS is the right tool because it
finds the best achievable increasing correspondence for free, without
being derailed by out-of-order noise (footnote/footer digits) or by
individual misreads, and any target value with no viable candidate is
reported as an explicit, un-silenced gap rather than merged silently.

Known residual gaps (this OCR pass could not recover these markers at
all -- no candidate token anywhere carries the right value): see
`sources/rackham-fin/README.md`'s gap table. Per the brief, every gap is a
declared decision requiring second-witness reconciliation before the
record set can ship at 443 records; this script alone does NOT close them
(some, on inspection against the Loebolus page image, are not resolvable
from the image either -- see README).

## Cleanup

- `_strip_footnote_tail`: an English page's *trailing* paragraph is
  dropped if its first line is a single lowercase letter (Loeb's
  footnote-marker convention, "a", "b", ...) followed by a CAPITALIZED
  second word (a footnote always opens a fresh sentence; the indefinite
  article "a" beginning a genuine body line is followed by a lowercase
  word, e.g. "a well-read man" -- this distinction is what the naive
  "any line starting with a lowercase single letter" version got wrong).
- `_GARBAGE_TOKEN`: drops tokens carrying '^'/'«' or an internal
  lowercase-to-uppercase transition (this scan's marginal-gloss/OCR-noise
  signature -- see module docstring above).
- `_DEHYPH_OK`: standard line-wrap dehyphenation.
- `_ROMAN_CHAP`: captures the Loeb chapter numeral (I, II, III, ...) that
  opens some (not all) sections, carried forward as each record's
  `chapter` field until the next chapter numeral is seen.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

SRC_XML = Path("../../build/rackham-fin/CiceroRackhamDeFinibusBonorumEtMalorum_djvu.xml")
OUT = Path("../../sources/rackham-fin/rackham.clean.json")
PATCHES = Path("../../sources/rackham-fin/PATCHES.json")

BOOK_TITLE_PAGE = {1: 36, 2: 112, 3: 250, 4: 334, 5: 424}
INDEX_START = 539
TARGET = {1: 72, 2: 119, 3: 76, 4: 80, 5: 96}

_ENG_STOP = set(
    "the and of to in is was that he it his with as for be not this but are "
    "on at have from which by an or i we you they were had has will would "
    "should could may might not".split()
)
_LAT_STOP = set(
    "et in est non quod cum qui quae quam sed ut si esse ad ex atque enim "
    "autem nam ita hoc haec his eius eos ea id sunt tamen quia".split()
)

_FOOTNOTE_START = re.compile(r"^[a-e]$")
_LEAD_DIGIT = re.compile(r"^(\d{1,3})\b\.?\s*(.*)$")
_GARBAGE_TOKEN = re.compile(r"[\^«]|[a-z][A-Z]")
_DEHYPH_OK = re.compile(r"[A-Za-z]-$")
_ROMAN_CHAP = re.compile(r"^(I{1,3}|IV|V|VI{1,3}|IX|X)\.?$")


def _load_pages(xml_path: Path):
    tree = ET.parse(xml_path)
    return list(tree.getroot().iter("OBJECT"))


def _page_lines(obj):
    out = []
    for line in obj.iter("LINE"):
        words = [w.text for w in line.findall("WORD") if w.text]
        if words:
            out.append(words)
    return out


def _classify(obj) -> str:
    words = [w.lower() for line in _page_lines(obj) for w in line]
    e = sum(1 for w in words if w.strip(".,;:!?\"'()") in _ENG_STOP)
    l = sum(1 for w in words if w.strip(".,;:!?\"'()") in _LAT_STOP)
    return "ENGLISH" if e > l else "LATIN"


def _strip_footnote_tail(lines_of_words):
    for i, words in enumerate(lines_of_words):
        first = words[0]
        if _FOOTNOTE_START.match(first) and len(words) > 1 and words[1][:1].isupper():
            return lines_of_words[:i]
    return lines_of_words


def _gather_book_lines(objs, book_n: int):
    """Flat list of (page_idx, line_text) for book_n's English content,
    head-stripped and footnote-tail-stripped, in reading order."""
    start = BOOK_TITLE_PAGE[book_n] + 1
    end = (BOOK_TITLE_PAGE[book_n + 1] if book_n < 5 else INDEX_START) - 1
    out = []
    for pidx in range(start, end + 1):
        obj = objs[pidx]
        if _classify(obj) != "ENGLISH":
            continue
        lines = _page_lines(obj)
        if not lines:
            continue
        lines = lines[1:]  # drop the running-head line
        lines = _strip_footnote_tail(lines)
        for words in lines:
            out.append((pidx, " ".join(words)))
    return out


def _lcs_align(target: list[int], cand_vals: list[int]) -> dict[int, int]:
    """Longest common subsequence between the fixed target [2..N] and the
    observed candidate values (reading order). Returns {target_value:
    candidate_index} for the best achievable increasing correspondence."""
    n, m = len(target), len(cand_vals)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if target[i - 1] == cand_vals[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    i, j = n, m
    mapping: dict[int, int] = {}
    while i > 0 and j > 0:
        if target[i - 1] == cand_vals[j - 1] and dp[i][j] == dp[i - 1][j - 1] + 1:
            mapping[target[i - 1]] = j - 1
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return mapping


def build_book(objs, book_n: int):
    """Returns (records, gaps) where records is a list of
    {section, chapter, text} dicts (may be FEWER than TARGET[book_n] if
    gaps exist -- a gap's content stays merged into the preceding record)
    and gaps is the sorted list of target section values this OCR pass
    could not locate a marker for."""
    all_lines = _gather_book_lines(objs, book_n)
    N = TARGET[book_n]
    candidates = []  # (line_index, value)
    for idx, (_pidx, ln) in enumerate(all_lines):
        m = _LEAD_DIGIT.match(ln)
        if m:
            candidates.append((idx, int(m.group(1))))
    target = list(range(2, N + 1))
    cand_vals = [v for (_, v) in candidates]
    mapping = _lcs_align(target, cand_vals)
    gaps = sorted(v for v in target if v not in mapping)
    boundary_line_idx = {v: candidates[ci][0] for v, ci in mapping.items()}

    records = []
    chapter = None
    cur_section = 1
    cur_tokens: list[str] = []
    boundary_set = set(boundary_line_idx.values())

    for idx, (_pidx, ln) in enumerate(all_lines):
        rest = ln
        if idx in boundary_set:
            # close current record, start new section
            records.append({"section": cur_section, "chapter": chapter, "text": " ".join(cur_tokens)})
            cur_tokens = []
            cur_section = next(v for v, li in boundary_line_idx.items() if li == idx)
            m = _LEAD_DIGIT.match(ln)
            rest = m.group(2) if m else ln
        for tok in rest.split():
            if _GARBAGE_TOKEN.search(tok):
                continue
            rm = _ROMAN_CHAP.match(tok)
            if rm:
                chapter = rm.group(1)
                continue
            if cur_tokens and _DEHYPH_OK.search(cur_tokens[-1]):
                cur_tokens[-1] = cur_tokens[-1][:-1] + tok
            else:
                cur_tokens.append(tok)
    records.append({"section": cur_section, "chapter": chapter, "text": " ".join(cur_tokens)})
    return records, gaps


def _apply_patches(records_by_book, patches_path: Path):
    if not patches_path.exists():
        return
    patches = json.loads(patches_path.read_text(encoding="utf-8"))
    applied = set()
    for p in patches:
        book, section = p["book"], p["section"]
        key = (book, section)
        rec = next((r for r in records_by_book[book] if r["section"] == section), None)
        if rec is None:
            raise SystemExit(f"PATCHES.json: no record for book {book} section {section}")
        for old, new in p.get("replace", []):
            if old not in rec["text"]:
                raise SystemExit(f"PATCHES.json: exact-once match failed for book {book} section {section}: {old!r} not found")
            if rec["text"].count(old) != 1:
                raise SystemExit(f"PATCHES.json: exact-once match failed for book {book} section {section}: {old!r} not unique")
            rec["text"] = rec["text"].replace(old, new)
        applied.add(key)
    return applied


def main():
    objs = _load_pages(SRC_XML)
    all_records = []
    gap_report = {}
    for book_n in range(1, 6):
        records, gaps = build_book(objs, book_n)
        gap_report[book_n] = gaps
        records_by_section = {r["section"]: r for r in records}
        by_book = {book_n: records}
        _apply_patches(by_book, PATCHES)
        for r in records:
            all_records.append({"book": book_n, "section": r["section"], "chapter": r["chapter"], "text": r["text"]})

    total_gaps = sum(len(g) for g in gap_report.values())
    print(f"Total records: {len(all_records)} (target 443); total unresolved gaps: {total_gaps}")
    for b, g in gap_report.items():
        if g:
            print(f"  Book {b} gaps ({len(g)}): {g}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_records, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Wrote", OUT, "sha256", hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
