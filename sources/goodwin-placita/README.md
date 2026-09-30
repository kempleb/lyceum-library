# W. W. Goodwin (ed.) — pseudo-Plutarch, *Placita philosophorum*, the chapters DK's Aëtius passages need

Vendored English for the Aëtius passages in the DK works that an audit of
Goodwin's text against DK's Greek classed as matching (owner's ruling, John,
2026-09-27: "Only the 132 matches"). Aëtius's *Placita* survives mainly as
pseudo-Plutarch's epitome, *Of Those Sentiments concerning Nature with which
Philosophers were Delighted*; Goodwin prints that epitome in English.

Read by `pipeline/reader_pipeline/stage1_context_english.py` as the source
pair ("Aëtius", "Placita"), credit "Goodwin, 1874" (draft, pending the
owner's approval).

**Public domain in the US by publication date** (printed 1874; copyright
entered 1870; both before the 1931 cut-off). Licence string: `Public Domain`.

## Source

| | |
|---|---|
| Translation | "Translated from the Greek by several hands" (the late-17th-century Morals), "corrected and revised by William W. Goodwin, Ph. D., Professor of Greek Literature in Harvard University" |
| Edition | *Plutarch's Morals*, vol. III, with an introduction by Ralph Waldo Emerson |
| Publisher | Boston: Little, Brown, and Company |
| Printing | 1874 (title page reads 1874; verso: "Entered according to Act of Congress, in the year 1870"; Cambridge: Press of John Wilson and Son) |
| Scan | archive.org `plutarchsmoralst03plutuoft` (University of Toronto copy), fetched 2026-09-27 |
| Pages used | printed pp. 104–193 (the whole treatise), scan PDF pages 122–211; the chapters kept here fall on printed pp. 106–191 |
| Files read | `plutarchsmoralst03plutuoft.pdf` (SHA-256 `f25244c5bccc7e7bc1bc755f7107994b9ec9ce9e33416e6a6ee57060238b923b`; its page images and its text layer) and `plutarchsmoralst03plutuoft_djvu.txt` (SHA-256 `13438008b241f87bfc58d26c7aa2cd532c824db2768403238bd1bbac1c8c1327`, the same OCR as the PDF's text layer) |

The scan files are not vendored here. The date: an earlier note called this
text "1878"; the scan's title page reads 1874, so this README and the credit
say 1874.

## Shape

`goodwin-placita.clean.json`: one flat JSON object keyed `"<book>.<chapter>"`
in **Goodwin's own chapter numbers**. Each value is one chapter of Goodwin's
English (the chapter title left out), his paragraphs separated by a blank line
(`\n\n`). Plain Unicode text: no markup, no footnotes, no page numbers.

77 chapters, 15,873 words — only the chapters the matched passages need:

| Book | Chapters |
|---|---|
| I | 3, 5, 6, 7, 16, 17, 18, 23, 25, 26, 27 |
| II | 1, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 20, 21, 22, 23, 24, 25, 26, 27, 28, 31 |
| III | 1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 15, 16 |
| IV | 1, 2, 3, 4, 5, 7, 10, 16, 17, 19, 22 |
| V | 1, 2, 4, 5, 7, 8, 10, 11, 12, 14, 16, 18, 19, 20, 21, 23, 24, 26, 27 |

**Numbering.** Goodwin's book and chapter numbers are Diels's (the numbers
DK's heads cite), except in Book V, where Goodwin prints Diels's chapters 23
and 24 in the reverse order: Goodwin's V 23 ("What are the causes of sleep and
death?") is Diels V 24, and Goodwin's V 24 ("When and from whence the
perfection of a man commences") is Diels V 23. A span's locus is always
Diels's; the resolver maps 5.23 ↔ 5.24 and nothing else. Chapter order and
titles were checked against the 1909 Crowell reprint of the same translation:
all five books have the same chapter count (30, 32, 18, 23, 30).

## Text: three witnesses, then the page images

No transcription of the 1874 printing exists, so the text was built from the
scan:

1. **Our OCR.** Each page image (PDF pages 122–211, rendered at 300 dpi) was
   read with Tesseract, keeping each line's position. The position gives the
   structure: running heads, page signatures ("VOL. III."), chapter heads and
   titles, verse (set in from the margin), paragraph starts (a first-line
   indent), and footnotes (smaller type at the page foot, starting with a
   mark), which are dropped along with their marks in the text. Line-end
   hyphens were joined.
2. **archive.org's OCR** of the same scan (the PDF text layer), joined the
   same way.
3. **The Crowell reprint** (New York, 1909; hellenicaworld.com), a later
   printing of the same translation that differs from 1874 in wording in many
   places. It was used only to spot OCR misreadings, never as the text.

Each word was taken where our OCR and archive.org's agreed (15,629 of 15,960
words in these chapters). Where they disagreed, the reading two witnesses
shared was taken, with Crowell only breaking a tie between two OCR readings
of the 1874 page (256 words). Every remaining disagreement, and every word
outside the dictionary that the witnesses did not all share, was checked
against a crop of the 1874 page image: 156 checks, of which 69 kept the OCR
reading, 55 removed specks, footnote marks and stray line-end fragments the
OCR had read as words, and 32 set the word the page shows (small-capital
names such as THALES, words split at a line end whose hyphen the scan lost,
and Goodwin's Greek words). Where 1874 and Crowell differ in wording (for
example 1874 "reflection" where Crowell has "refraction", "Heraclides" where
Crowell has "Heraclitus", "Xenophanes" where Crowell has "Zenophanes"), 1874
was kept.

Typography was normalised, never the words: no space before `; : ? !` or a
closing bracket (the 1874 printer spaced them), em-dashes closed up,
curly quotes and apostrophes, and the small capitals of a chapter's first
word set in ordinary case ("THE disciples" → "The disciples"). A verse
quotation is its own paragraph, its lines joined by single spaces.

Goodwin's Greek words, typed from the page images (the OCR cannot read
Greek): κόσμος (II 1), θέοντες, θεωρεῖν, θεούς (I 6), ἐντελέχεια (IV 2),
φωνή, φωτίζει (IV 19). They are Goodwin's text, not DK's.

### Words not settled beyond doubt

- V 1: "and so likewise they explain interpretation by dreams" — the scan
  shows a damaged "sc"/"so"; "so" is taken (sense, and Crowell).
- The accents of the Greek words above are at the limit of the scan's
  resolution; standard forms were typed.
- Paragraph breaks come from first-line indents in the scan; a few may differ
  from the print where a page's first line is indented by a speck.

## Checks

- Every chapter title and the chapter counts per book agree with Crowell.
- No digits, footnote marks, running heads, straight quotes or double spaces
  remain in any chapter.
- Every trim anchor of every placed span occurs exactly once in its chapter
  (the build enforces this).

`SHA256SUMS` holds the SHA-256 of the clean JSON.
