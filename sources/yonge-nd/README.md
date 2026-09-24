# Yonge, *De Natura Deorum* ("On the Nature of the Gods")

English translation by **C. D. Yonge**, all three books, extracted from
Wikisource's human-proofread transcription into `yonge.clean.json` by
`pipeline/tools/extract_yonge_nd_wikisource.py`, plus `concordance.json` --
the chapter -> Latin-section alignment key this work needs (Yonge's edition
carries only Roman-numeral chapter markers, no Arabic section numbers).
Full source-verification detail belongs in `sources/INVENTORY.md`; this file
is the short identity card plus the concordance methodology.

## Translation witness

- Translator: Charles Duke Yonge (1812-1891).
- Source: Wikisource, `On the Nature of the Gods (Yonge)` (a redirect to
  `Cicero's Tusculan Disputations/On the Nature of the Gods`), transcluded
  from `Index:1888 Cicero's Tusculan Disputations.djvu` -- "Cicero's
  Tusculan Disputations, also treatises On the Nature of the Gods, and On
  the Commonwealth" (New York: Harper & Brothers, 1888), ProofreadPage
  quality mostly 3 ("Proofread"); djvu page 348 (Book 3's numbering-defect
  page, see below) is quality 4 ("Validated").
- Source URL: <https://en.wikisource.org/wiki/On_the_Nature_of_the_Gods_(Yonge)>
- US-PD basis: published 1888, translator d. 1891 -- safely pre-1931, US
  public domain.
- Fetched: 2026-07-18, via MediaWiki `action=query&prop=revisions` (pinned
  revisions, not "latest" -- see `_PAGE_REVISIONS` in the extractor).

## Pinning

- Wikisource mainspace: `.../On the Nature of the Gods/Book 1`, `/Book 2`,
  `/Book 3`, each transcluding a djvu page range from the 1888 Index (Book 1
  = 215-260, Book 2 = 260-324, Book 3 = 324-361 -- djvu 260 and 324 are each
  shared by two adjacent books, disambiguated by Wikisource's own inline
  `<section begin="otnotg_bookN" />...<section end="otnotg_bookN" />` tags).
- Every one of the 147 unique `Page:.../<N>` subpages (215-361 inclusive) is
  fetched at a **pinned revision** (`action=query&prop=revisions&rvslots=main`,
  raw wikitext); the full djvu page -> revid table (captured 2026-07-18) is
  `_PAGE_REVISIONS` in `pipeline/tools/extract_yonge_nd_wikisource.py`.
  Re-running the extractor reproduces `yonge.clean.json` byte-identically
  unless a table entry is deliberately bumped (verified: two consecutive
  runs are byte-identical).

## Shape

`yonge.clean.json` is an ordered array of 151 records `{book, chapter,
text}` -- one record per chapter (Book 1: 44 chapters, Book 2: 67, Book 3:
40; strictly sequential from 1 within each book). See the extractor's
module docstring for the full markup-cleaning catalogue (footnote/verse/
layout-template handling, page-seam hyphenation, the two `{{anchor+|ROMAN}}`
chapter markers, the interwiki-link and Ppoem-directive handling).

`PATCHES.json` holds one hand-verified, exactly-once-matched raw patch:
Book 3's djvu page 348 (printed page 342, Validated quality) reads "XVII."
where content context requires "XXVII." (it sits strictly between the
page's own unambiguous "XXVI." and "XXVIII.") -- almost certainly the 1888
print's own erratum, not a transcription slip, given the Validated flag.
See the patch's own `note` for the full evidence.

## Concordance witness (`concordance.json`)

The alignment key this work needs: every `(book, chapter)` -> the Latin
**section** number (PHI Ax edition spine: book 1 = sections 1-124, book 2 =
1-168, book 3 = 1-95) at which that chapter begins. Yonge's edition (like
the underlying 1888 print) carries no section numbers at all, so this
mapping must come from a **separate** PD witness that prints Cicero's Latin
text with both a chapter (capitula) numbering AND a section numbering.

**Witness: Joseph B. Mayor** (with a collation by J. H. Swainson), *M.
Tulli Ciceronis De Natura Deorum Libri Tres*, 3 vols. (Cambridge: University
Press, 1880-1885) -- the standard 19th-century scholarly edition with Latin
text, critical apparatus, and English commentary. Public domain (published
1880-1885, safely pre-1931; vol. 1 and vol. 3 both carry archive.org
`possible-copyright-status: NOT_IN_COPYRIGHT` / `copyright-region: US`).

| Volume | Book | archive.org identifier | URL |
|---|---|---|---|
| 1 | I | `denaturadeorum01ciceuoft` | <https://archive.org/details/denaturadeorum01ciceuoft> |
| 2 | II | `denaturadeorumli02cice` | <https://archive.org/details/denaturadeorumli02cice> |
| 3 | III | `denaturatres03ciceuoft` | <https://archive.org/details/denaturatres03ciceuoft> |

Mayor's Latin text prints Cicero's own chapter numerals inline (e.g. "XLII.
Mihi quidem etiam Democritus...") AND, in the margin/interleaved with the
running text, the traditional continuous **section** numbers (e.g. "120",
"121", ...) -- the double numbering this concordance requires. Each page
also carries a running header of the form `LIB. I CAP. XL—XLII §§
118—119.` (chapter range / section range covered by that page).

### Method

The OCR'd djvu text (`*_djvu.txt` derivative, fetched 2026-07-18) is noisy
(critical-apparatus line-numbers, which reset every page, are easily
confused with the true continuous section numbers unless filtered), so the
concordance was built from the **running headers only**, using
"touching-boundary" evidence: when one page's header ends at chapter X /
section S and the very next page's header begins at chapter X / section S
(the same chapter and section, confirming a genuine page-turn mid-chapter),
S is recorded as a directly witnessed ("exact": true) anchor for chapter X.
Chapter 1 of every book is a definitional anchor (section 1, per the gate
below). Chapters with no directly witnessed anchor are **linearly
interpolated** between the nearest surrounding anchors (or, past a book's
last witnessed anchor, **extrapolated** using that book's average
sections-per-chapter rate) and marked `"exact": false`. This is a coarser
witness than a hypothetical chapter-by-chapter concordance, but it is
honestly sourced, reproducible from the cited archive.org identifiers, and
sufficient for the book.section alignment stage's needs.

### Sample mappings

| Book | Chapter | start_section | exact |
|---|---|---|---|
| 1 | 1 | 1 | true (definitional) |
| 1 | 4 | 7 | true (Mayor header touching-boundary) |
| 1 | 42 | 119 | true (Mayor header touching-boundary) |
| 2 | 1 | 1 | true (definitional) |
| 2 | 37 | 95 | true (Mayor header touching-boundary) |
| 3 | 1 | 1 | true (definitional) |
| 3 | 27 | 69 | true (Mayor header touching-boundary) |

### Gate results

- Chapter 1 -> section 1 in every book: holds by construction (definitional
  anchor).
- Section starts strictly increasing within each book: holds by
  construction (interpolation/extrapolation is nudged by +1 wherever a
  raw linear estimate would otherwise tie or invert against a neighbouring
  anchor -- affects a small number of interpolated, i.e. `"exact": false`,
  chapters; no witnessed ("exact": true) anchor was ever adjusted).
- Final chapter's implied start vs. the book's known Ax maximum (the
  extrapolated/interpolated value is compared, NOT force-fit to the
  maximum):
  - Book 1: chapter 44 -> section 125 vs. Ax max 124 (+1).
  - Book 2: chapter 67 -> section 166 vs. Ax max 168 (-2).
  - Book 3: chapter 40 -> section 101 vs. Ax max 95 (+6, the largest
    deviation -- Book 3's Mayor headers were noisier/sparser in the OCR
    source, with several pages excluded as corrupted; see the recon notes
    in the delivery report). These are exactly the "small mismatches vs the
    Ax edition" the concordance is expected to carry, since the witness is
    a different 19th-century edition, not Ax itself -- reported here rather
    than silently smoothed away.
