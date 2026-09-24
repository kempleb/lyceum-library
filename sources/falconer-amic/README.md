# Falconer, *Laelius de Amicitia* — source verification

W. A. Falconer's 1923 Loeb translation (Loeb Classical Library 154),
extracted from the Perseus Digital Library's `canonical-latinLit` TEI XML.
Target work: `laelius-de-amicitia` (flat, sections 1–104).

See `sources/INVENTORY.md`'s "Cicero, *De Senectute*, *De Amicitia*, *De
Divinatione*" entry for the full evidence chain; this file is the
short-form pointer.

## Source

| | |
|---|---|
| Translator | William Armistead Falconer (1869–1927) |
| Publisher | London: William Heinemann; Cambridge, Mass.: Harvard University Press |
| Publication year | 1923 (Loeb Classical Library 154), reprinted unrevised 1927–1971 |
| US-PD rationale | Published 1923 — safely pre-1931, US public domain |
| Source | Perseus Digital Library / PerseusDL `canonical-latinLit` GitHub repo, `data/phi0474/phi052/phi0474.phi052.perseus-eng2.xml` |
| Pinned commit | `1066a551aa5445ab165e9b490a6bb06ce72828da` (same "phi0474 Cicero batch" header-fix commit as the Senectute/Divinatione pins) |
| File | `phi0474.phi052.perseus-eng2.xml` |
| SHA-256 | `b0c39a70e78e3d7363cabdc1832e8ca9de878a31ac6e13a18742aeda1d919069` |
| Size | 121,142 bytes (323 lines) |

Note: phi0474.phi052 has no `eng1` file on Perseus — only `eng2` exists,
and its own teiHeader still names Falconer as translator (below); `eng2` is
simply this file's index within Perseus's own numbering, not a second or
alternate translation.

## Identity verification (triple witness)

- Perseus's own teiHeader: `<editor role="translator">William Armistead
  Falconer</editor>` (titleStmt and sourceDesc); sourceDesc additionally
  names the shared volume title "De Senectute De Amicitia De Divinatione,
  With An English Translation" and links to a SECOND, independent
  archive.org scan (`archive.org/details/desenectutedeami0000cice`).
- archive.org `cicero-in-28-volumes.-vol.-20-loeb-154` (HathiTrust `uc1`
  scan, cross-witnessed independently of the link above): title page "WITH
  AN ENGLISH TRANSLATION BY WILLIAM ARMISTEAD FALCONER"; printing history
  "First printed 1923 / Reprinted 1927, 1930, 1938, 1946, 1953, 1959,
  1964, 1971".
- Incipit cross-check: Perseus's own opening ("QUINTUS MUCIUS SCAEVOLA,
  the augur, used to relate...") verified verbatim identical against the
  archive.org scan's OCR text layer.

## Structure and extraction: Hicks-shaped, not milestone-shaped

Unlike the other two Falconer files (and unlike Miller's De Officiis),
De Amicitia has NO `unit="section"` milestone at all. Each section is its
OWN wrapping `<div type="textpart" subtype="section" n="1".."104">`
element (the Diogenes Laertius / Hicks shape) — confirmed 104 divs,
document-order `@n` exactly 1..104, no gaps or duplicates. Only
`unit="chapter"` milestones appear (27, INSIDE section divs), carrying no
text and never affecting section boundaries, exactly like Miller's chapter
milestones. Extracted by `pipeline/tools/extract_falconer_perseus.py`'s
`_extract_section_divs` / `_extract_amicitia` — one already-delimited
`_Ctx` walk per div, asserting document order matches `@n`.

## Cleaning conventions (the file with the richest element inventory)

- `<note>` (68, all untyped) and `<bibl>` (1, sibling of a verse `<quote
  rend="blockquote">` inside `<cit>`) dropped whole — same "prints as a
  footnote" verification as the Senectute/Divinatione `<bibl>` cases.
- `<foreign xml:lang="lat">` (54; 50 inside dropped notes, 4 in running
  body text: "toga virilis,", "amor", "amicitia", "obsequium") — untranslated
  Latin technical terms quoted inline in Falconer's own English; passed
  through as plain text (no italics markup exists in this corpus's
  convention).
- `<foreign xml:lang="grc">` (7) — De Amicitia's OWN, different encoding:
  already-Unicode Greek, not Beta Code (unlike the other two files' `greek`
  lang tag). ALL 7 sit inside dropped `<note>`s — corpus-verified via
  `_assert_grc_all_in_notes()`, which fails the build loud if a future
  re-fetch ever moves one into body text. The pass-through branch for this
  case exists but is never exercised on the pinned XML.
- `<quote>` (any `@rend` not containing "blockquote") AND `<q>` (ANY
  `@type` — `soCalled`/`emph`/`spoken`/`translation`/`written`/`mentioned`/
  `gloss`, 47 in running body text) both wrapped in curly quotes,
  alternating by nesting depth, sharing one depth counter — confirmed
  against the archive.org scan for representative examples of each `@type`
  that all print as plain quotation marks. One edge case: `<quote
  type="blockquote">` (attribute is `@type`, NOT `@rend` — a short Terence
  tag, no `<l>` children) is confirmed by the archive.org scan to print
  WITH quotation marks, i.e. as a REGULAR quote, not a displayed block;
  Miller's `_is_verse_quote` (which checks `@rend` only) already gets this
  right unchanged.
- `<emph rend="italic">` (2) — plain pass-through, same as `<hi>` elsewhere.
- `<said who="..." [rend="merge"]>`, `<label>` (De Amicitia's dialogue
  markup: Scaevola narrating Laelius/Fannius/Scaevola's conversation) —
  plain pass-through containers; a `<label>` (e.g. "FANNIUS.") is kept as
  ordinary running text exactly as printed, matching Miller's `<speaker>`
  treatment.
- `<title>` — plain pass-through (cross-references to Cicero's other
  works, e.g. "Cato the Elder").
- `<l>` (5, verse) — plain pass-through, relies on source whitespace.
- `<head>` ("Laelius on Friendship") is a SIBLING of, and precedes, the
  first section div — never visited at all, since each section is walked
  as its own standalone unit (not dropped via an open-section check like
  the other two files; simply out of scope).

## Output

`falconer.clean.json` — 104 records, `{"section": n, "text": "..."}`,
`n` = 1..104 contiguous. SHA-256
`031378d8823da088d655ba62783f508ede356bf3800a814a27cccbfb5a6d7fa5`.

## Gates

Record count 104/104 exact. Sequence strictly increasing, no gaps. No
empty records. No high-Latin-density records beyond the 4 confirmed
short embedded-Latin-term cases above (none flagged by the automated
sweep). No stray Beta-Code artifacts. Deterministic double-run
(byte-identical output).

## Spot-check vs. archive.org scan

5 sections (1, 25, 50, 75, 104) checked against the archive.org OCR text
layer via fuzzy word-overlap comparison. Sections 1, 25, 50 matched
directly (similarity 0.93–1.00). Sections 75 and 104 were initially
flagged by the automated anchor-matcher (low scores) because their
distinctive opening phrases ("This rule also may properly be prescribed",
"Why need I speak of...") recur elsewhere in the volume and the matcher
locked onto the wrong occurrence; both were manually re-verified by direct
text search and confirmed to match Falconer's print exactly (no
discrepancies). `PATCHES.json` is deliberately absent (same "mechanism
wired in, unused" convention as `sources/munro-drn/`).
