# Falconer, *De Divinatione* — source verification

W. A. Falconer's 1923 Loeb translation (Loeb Classical Library 154),
extracted from the Perseus Digital Library's `canonical-latinLit` TEI XML.
Target work: `de-divinatione` (book.section, Book I 1–132, Book II 1–150).

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
| Source | Perseus Digital Library / PerseusDL `canonical-latinLit` GitHub repo, `data/phi0474/phi053/phi0474.phi053.perseus-eng1.xml` |
| Pinned commit | `1066a551aa5445ab165e9b490a6bb06ce72828da` (same "phi0474 Cicero batch" header-fix commit as the Senectute/Amicitia pins) |
| File | `phi0474.phi053.perseus-eng1.xml` |
| SHA-256 | `c4edfe8598dc7ff504ab91d3f6ad4d40879056155c05f71ad18f4141d1891ce6` |
| Size | 349,510 bytes (6,521 lines) |

## Identity verification (triple witness)

- Perseus's own teiHeader: `<editor role="translator">William Armistead
  Falconer</editor>` (titleStmt and sourceDesc), imprint "Cambridge /
  Harvard University Press; Cambridge, Mass., London, England / 1923".
- archive.org `cicero-in-28-volumes.-vol.-20-loeb-154` (HathiTrust `uc1`
  scan): title page "WITH AN ENGLISH TRANSLATION BY WILLIAM ARMISTEAD
  FALCONER"; printing history "First printed 1923 / Reprinted 1927, 1930,
  1938, 1946, 1953, 1959, 1964, 1971".
- Incipit cross-check: Perseus's own opening ("There is an ancient belief,
  handed down to us...") verified verbatim identical against the
  archive.org scan's OCR text layer.

## Structure and extraction

Miller's EXACT shape: `<div subtype="book" n="1"|"2">` (correctly numbered
here — no Book-III-style `@n` mislabeling bug) containing `<p>` elements
with inline `<milestone unit="section" n="...">` markers. Extracted by
`pipeline/tools/extract_falconer_perseus.py`'s `_extract_book_milestone` /
`_extract_divinatione`, called once per book.

**Confirmed Perseus typo: `unit="seciton"` (Book II, n="128").** A single
occurrence of a misspelled `unit` attribute value ("seciton" for
"section") — verified by direct inspection to be the ONLY `n="128"`
milestone in Book II, and 128 the only number Book II's correctly-spelled
`unit="section"` sequence is missing. Treated as a real section boundary
identically to a correctly-spelled one (`milestone_units=("section",
"seciton")`); with this alias, Book II's milestones run a clean,
complete 1..150.

**Declared gap: Book I has no `n="25"` milestone at all (131 of 132).**
No duplicate anywhere in Book I — `n="25"` is simply absent, and the
sequence otherwise runs contiguous 1..132 around the hole. Cross-checked
against the built PHI Latin spine
(`app/dist/data/de-divinatione/book-01.json`: `1:1.24` = 141 words,
`1:1.25` = 60 words, both present and substantial) and against the English
word count spanning Perseus's own milestones 24→26 (256 words, closely
proportionate to the combined 201 Latin words for 24+25) — strong
circumstantial evidence that Falconer's English DOES contain section 25's
content, folded into a neighboring span with no separate milestone ever
inserted (the Grok content gate located the "misleads perhaps…" rendering
of Latin 25's opening at the START of English 26's span, so the fold is
into 26, not 24 as first inferred),
the same "content present, editorial/markup merge, no separate marker"
shape as Miller's 2:2.90 gap in De Officiis. UNLIKE Miller's case (a
single, obviously terminal short sentence with an unambiguous splice
point), section 25's ~60-Latin-word span has no self-evident
single-sentence boundary recoverable from the English text alone.
**Left DECLARED rather than guessed**: `1:25` is simply absent from
`falconer.clean.json` (281 records, not the full 282), matching Miller's
"declared gap, not a silent fix" discipline. This needs the corresponding
`alignment_allow_unmatched: ["1:1.25"]` manifest entry at the alignment
stage — **out of this extraction script's blast radius**; flagged here and
in `sources/INVENTORY.md` for that follow-up.

## Cleaning conventions

- `<note>` (289, all untyped) dropped whole.
- `<bibl>` (5, all siblings of a verse `<quote rend="blockquote">` inside
  `<cit>` — Pacuvius, Ennius quotations) dropped whole even though not
  wrapped in `<note>` — confirmed against the archive.org scan to print as
  numbered footnotes, not running prose (same pattern as the Senectute and
  Amicitia `<bibl>` cases).
- `<foreign xml:lang="greek">` (29; 20 inside dropped notes, 9 in running
  body text) — Beta-Code-like ASCII, decoded via a small hand-verified
  table (all 9 standard divination/logic technical terms: μαντική,
  δαιμόνιον, εἱμαρμένη, ψευδόμενον, ὁρίζοντες, λήμματα, πρόσληψις,
  συμπάθεια ×2) — an unrecognized string fails the build loudly, and every
  table entry is asserted actually-used (checked independently per book,
  since both books key sections by bare int and a naive dict-merge would
  silently under-report usage — caught during development, see the
  extractor's `_extract_divinatione` comment).
- `<quote>` without `blockquote` in `@rend` (91 in running body text)
  wrapped in curly quotes, alternating by nesting depth; `<quote
  rend="...blockquote...">` (verse: Ennius' *Annales*, Pacuvius, Homer,
  etc. — 328 `<l>` lines total) passes through with no marks added.
- `<hi rend="italics">` (84 in body), `<title>` — plain pass-through, no
  markup.
- `<l>` — plain pass-through, relies on source whitespace (verified: zero
  tight `</l><l>` adjacencies across all 328 occurrences).

## Output

`falconer.clean.json` — 281 records, `{"book": b, "section": n, "text":
"..."}`. Book 1: 131/132 (n = 1..132 minus the declared `25` gap). Book 2:
150/150 (n = 1..150, complete via the `seciton` alias). SHA-256
`fd3758a2ea8f9529e20c68fd04b5b8528bf3e40aab1a30963262f22a957dcc41`.

## Gates

Record count: **281 of the expected 282** — the single, cross-verified,
DECLARED `1:25` gap above, not an extraction defect (flagged prominently;
not silently absorbed into a passing "exact count" claim). Both books'
sequences strictly increasing with no OTHER gaps. No empty records. No
high-Latin-density records. No stray Beta-Code artifacts. Deterministic
double-run (byte-identical output).

## Spot-check vs. archive.org scan

5 sections (1:1, 1:66, 1:131, 2:1, 2:150) checked against the archive.org
OCR text layer via fuzzy word-overlap comparison. 1:1, 1:66, 2:1, 2:150
matched directly (similarity 0.94–0.99). 1:131 was initially flagged by
the automated anchor-matcher (low score) because its opening phrase
recurs elsewhere in the volume and the matcher locked onto the wrong
occurrence; manually re-verified by direct text search and confirmed to
match Falconer's print exactly (no discrepancy). `PATCHES.json` is
deliberately absent (same "mechanism wired in, unused" convention as
`sources/munro-drn/`) — the ONE confirmed content anomaly found (`1:25`)
is a missing-milestone gap, not a text transcription error, so it is not
patchable via the exact-once text-replace mechanism and is declared
instead (see above).
