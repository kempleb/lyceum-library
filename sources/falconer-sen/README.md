# Falconer, *Cato Maior de Senectute* — source verification

W. A. Falconer's 1923 Loeb translation (Loeb Classical Library 154),
extracted from the Perseus Digital Library's `canonical-latinLit` TEI XML.
Target work: `cato-maior-de-senectute` (flat, sections 1–85).

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
| Source | Perseus Digital Library / PerseusDL `canonical-latinLit` GitHub repo, `data/phi0474/phi051/phi0474.phi051.perseus-eng1.xml` |
| Pinned commit | `1066a551aa5445ab165e9b490a6bb06ce72828da` (2026-06-23, same "phi0474 Cicero batch" header-fix commit as Miller's De Officiis pin — verified as this file's own most recent touching commit, 2026-07-18) |
| File | `phi0474.phi051.perseus-eng1.xml` |
| SHA-256 | `44ba1e6d5059cbbf774ee43b0feeb64d670511db972cd7be11192f12c24af348` |
| Size | 95,817 bytes (1,918 lines) |

## Identity verification (triple witness)

- Perseus's own teiHeader: `<editor role="translator">William Armistead
  Falconer</editor>` (titleStmt and sourceDesc), imprint "Cambridge /
  Harvard University Press; Cambridge, Mass., London, England / 1923".
- archive.org `cicero-in-28-volumes.-vol.-20-loeb-154` (HathiTrust `uc1`
  scan): title page "WITH AN ENGLISH TRANSLATION BY WILLIAM ARMISTEAD
  FALCONER"; printing history "First printed 1923 / Reprinted 1927, 1930,
  1938, 1946, 1953, 1959, 1964, 1971" — unrevised across every reprint.
- Incipit cross-check: Perseus's own opening ("O Titus, should some aid of
  mine dispel...") verified verbatim identical against the archive.org
  scan's OCR text layer.

## Structure and extraction

Single flat `<div type="translation">` (De Senectute has no book
subdivision) with inline `<milestone unit="section" n="...">` markers —
the same per-book milestone-cursor shape `extract_miller_perseus.py` uses,
just with only one "book" to walk. Extracted by
`pipeline/tools/extract_falconer_perseus.py`'s `_extract_flat_milestone` /
`_extract_senectute`.

**Confirmed Perseus data-entry bug: duplicate `n="35"` / missing `n="36"`.**
The pinned XML's milestones run 1..85 but contain the SAME number twice
(`n="35"` fires twice) while `n="36"` never appears at all. Cross-checked
against the built PHI Latin spine
(`app/dist/data/cato-maior-de-senectute/book-01.json`, sections 34–37 all
present, ~93–104 words each — section 36 is a genuine, substantial Latin
section, not a Miller-2.90-style single-sentence merge) and against the
milestone content itself (the second `n="35"` fires mid-sentence; the very
next milestone after it is `n="37"`). The extractor's
`_DUPLICATE_MILESTONE_FIX = {35: 36}` renumbers the SECOND occurrence to
36 — a single, hand-verified, cited correction; any other duplicate number
not in this table still raises `ValueError` unconditionally, matching
Miller's invariant.

## Cleaning conventions

- `<note>` (60, all untyped) dropped whole — editorial apparatus.
- `<foreign xml:lang="greek">` (8 occurrences) — ALL sit inside dropped
  `<note>`s; none appear in running body text, so no Beta-Code decode table
  is needed for this file (verified by direct corpus count).
- `<quote>` without `blockquote` in `@rend` wrapped in curly quotes,
  alternating by nesting depth; `<quote rend="...blockquote...">` (verse:
  Ennius, Caecilius, etc.) passes through with no marks added.
- `<hi rend="italics">`, `<title>` — plain pass-through, no markup.
- `<bibl>` (2, both siblings of a verse `<quote rend="blockquote">` inside
  `<cit>`, e.g. "From Caecilius's comedy, Plocium.") dropped whole EVEN
  THOUGH not wrapped in `<note>` — confirmed against the archive.org scan
  to print as a numbered footnote, not running prose.
- `<l>` (27, verse lines) — plain pass-through, relies on the source's own
  inter-`<l>` whitespace (verified: zero tight `</l><l>` adjacencies).

## Output

`falconer.clean.json` — 85 records, `{"section": n, "text": "..."}`,
`n` = 1..85 contiguous. SHA-256
`536f98e6a77cc2ddc249516857798cf5c47eff689ae66e89f218e5f7f5897d07`.

## Gates

Record count 85/85 exact. Sequence strictly increasing, no gaps. No empty
records. No high-Latin-density records (no untranslated-Latin bleed swept
post-extraction). No stray Beta-Code artifacts. Deterministic double-run
(byte-identical output).

## Spot-check vs. archive.org scan

5 sections (1, 20, 45, 65, 85) checked against the archive.org OCR text
layer via incipit/fuzzy word-overlap comparison — all 5 confirmed matching
(similarity ratios 0.966–1.000 on a 60-word window; section 1's exact
incipit separately confirmed verbatim by direct inspection). No
discrepancies found; `PATCHES.json` is deliberately absent (same
"mechanism wired in, unused" convention as `sources/munro-drn/`).
