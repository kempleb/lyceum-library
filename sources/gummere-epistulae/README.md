# Gummere, *Ad Lucilium Epistulae Morales* — source verification

Richard M. Gummere's Loeb translation of Seneca's *Epistulae Morales ad
Lucilium* (Loeb Classical Library, 3 vols.: 75, 76, 77), extracted from
Wikisource's mainspace transcription. Target work: `epistulae-morales`
(the `letter` citation scheme — letter.section, 124 letters, dotted
grammar identical to book-section).

See `sources/INVENTORY.md`'s matching entry for the hash-verification
restatement; this file is the full provenance writeup.

## Source volumes

| Vol. | Letters | archive.org identifier | THIS SCAN's own title-page date | Printing-history wording (verbatim, verified directly against page images) |
|---|---|---|---|---|
| I | 1–65 | `adluciliumepistu01seneuoft` | **MCMXXV (1925)** — this exact scanned copy's own title page (leaf 9) carries the REPRINT date, not the original 1918 one | Verso (leaf 10, directly viewed via IIIF): *"First Printed* 1918. / *Reprinted* 1925." (two lines, italic; confirms this copy is the unrevised 1925 reprint of a work first printed 1918) |
| II | 66–92 | `adlucilium02sene` | MCMXX (1920) | **No printing-history statement at all in this specific scan** — see "Vol. II gate" below |
| III | 93–124 | `adluciliumepistu03seneuoft` | MCMXXV (1925) | No printing-history line found (first printing, per recon) |

**Vol. I correction (this task's own gate)**: an earlier draft of this
README stated Vol. I's title-page date as "MCMXVIII" and did not
distinguish it from the first-printing year — wrong on both counts.
Directly inspected via the IIIF endpoint
(`https://iiif.archive.org/iiif/adluciliumepistu01seneuoft$<leaf>/full/full/0/default.jpg`),
leaves 7–11: leaf 7 is the half-title, leaf 8 blank (ink bleed-through
only), leaf 9 is the full title page reading "SENECA / AD LUCILIUM
EPISTULAE MORALES / WITH AN ENGLISH TRANSLATION BY / RICHARD M. GUMMERE,
PH.D. / OF HAVERFORD COLLEGE / IN THREE VOLUMES / I / LONDON: WILLIAM
HEINEMANN / NEW YORK: G. P. PUTNAM'S SONS / **MCMXXV**" (1925, not 1918),
leaf 10 is that title page's own verso and carries the printing-history
line quoted above, leaf 11 opens "CONTENTS OF VOLUME I" confirming no page
was skipped. archive.org's own catalog `date` field for this identifier
reads `1917` — a cataloging artifact (this Toronto library copy's own
call-slip pencil marks likewise read "1917 v.1") that matches neither date
actually printed on the physical pages and is not relied on here.

Translator (credentials restated per volume from what is actually printed
on each volume's own title page, directly verified — an earlier draft's
blanket "Head Master... vols. I–II title pages" claim was wrong for Vol. I
and self-contradicted its own Vol. II transcription below):

| Vol. | Credential line on this scan's title page |
|---|---|
| I | "OF HAVERFORD COLLEGE" (his post at the time of the 1918 first printing; left unrevised even in this 1925 reprint) |
| II | "HEAD MASTER, WILLIAM PENN CHARTER SCHOOL, PHILADELPHIA" (per the Vol. II gate transcription below) |
| III | "HEAD MASTER, WILLIAM PENN CHARTER SCHOOL, PHILADELPHIA" (djvu OCR, front matter — clean, unambiguous) |

Richard Mott Gummere, **1883–1969** (not 1883–1965 — corrected; per the
Online Books Page / LC-NACO name-authority record "Gummere, Richard M.
(Richard Mott), 1883-1969", https://onlinebooks.library.upenn.edu/webbin/book/lookupname?key=Gummere,+Richard+M.+(Richard+Mott),+1883-1969).
Publisher: London, William Heinemann; New York, G. P. Putnam's Sons.

**US-PD rationale**: all three volumes first published 1918/1920/1925 (this
Vol. I scan itself being the unrevised 1925 reprint) — safely pre-1931, US
public domain by the 95-year rule regardless of archive.org's own
`possible-copyright-status` field (Vol. II's is `NOT_IN_COPYRIGHT`, which
per CLAUDE.md can be a Canada-only signal and is therefore not relied on
alone — the title-page dates and verified-absence of "revised" language
are the load-bearing evidence here).

### Vol. II gate (MANDATORY per this task's brief)

Vol. II's own copyright/title-page verso was inspected DIRECTLY as page
images (not just OCR), since the recon flagged a sibling copy
(`senecaadlucilium0002gumm`) showing "First printed 1920. Reprinted 1930,
1953" — reprint language that, if it appeared on the copy actually used
here, would need separate US-PD justification for the later reprint dates
(still safely pre-1931, but the brief required verifying which wording
this exact scan carries).

Fetched via archive.org's IIIF endpoint
(`https://iiif.archive.org/iiif/adlucilium02sene$<leaf>/full/full/0/default.jpg`),
leaves 6–12 of `adlucilium02sene`:

- Leaf 7 (recto): half-title — "THE LOEB CLASSICAL LIBRARY / EDITED BY /
  E. CAPPS... / SENECA / AD LUCILIUM EPISTULAE MORALES".
- Leaf 8: blank.
- Leaf 9 (recto): full title page — "SENECA / AD LUCILIUM EPISTULAE
  MORALES / WITH AN ENGLISH TRANSLATION BY / RICHARD M. GUMMERE, PH.D. /
  HEAD MASTER, WILLIAM PENN CHARTER SCHOOL, PHILADELPHIA / IN THREE
  VOLUMES / II / LONDON: WILLIAM HEINEMANN / NEW YORK: G. P. PUTNAM'S SONS
  / MCMXX".
- **Leaf 10 (the title page's own verso — where a printing-history line
  would normally sit): blank**, carrying only a faint mirror bleed-through
  of leaf 9's own ink (confirmed by direct visual inspection of the full
  page image) — no "First printed"/"Reprinted"/"revised" text of any kind.
- Leaf 11: "CONTENTS OF VOLUME II" (page v), confirming no page was
  skipped between the title verso and the contents.

Cross-checked against the full OCR text (`adlucilium02sene_djvu.txt`,
21,043 lines): `grep -i "first printed\|reprint\|revised\|copyright"`
returns **zero matches** anywhere in the volume.

**Verdict: this exact scanned copy of Vol. II carries NO printing-history
statement at all** — neither the sibling copy's "First printed 1920.
Reprinted 1930, 1953" nor any revision language. Combined with the title
page's own unambiguous "MCMXX" (1920) date, this is consistent with the
sibling copy's own "First printed 1920" clause (i.e., this copy is
plausibly an early, un-reprinted-yet impression, or simply omits the line)
— in either case, **no "revised" language of any kind appears**, so the
MANDATORY GATE is satisfied and extraction proceeded.

## Extraction route

**Wikisource mainspace pages**, not raw Perseus/archive.org OCR: "Moral
letters to Lucilius/Letter 1" .. "/Letter 124" (en.wikisource.org),
fetched via the MediaWiki API's `action=parse&prop=text` (server-rendered
HTML, which lets Wikisource's own ProofreadPage extension resolve the
`<pages>` transclusion — word-joins across djvu page boundaries,
hyphenation, running-head chrome — rather than this script re-implementing
that logic). Tool: `pipeline/tools/extract_gummere_wikisource.py` — see
its own module docstring for full extraction mechanics, cleaning
conventions, and the two declared per-letter numbering exceptions (below).

780 transclusion occurrences across 688 distinct `Page:Ad Lucilium
epistulae morales, volume N.djvu/<M>` subpages (an earlier draft of this
README said "780 underlying subpages", conflating occurrence count with
distinct-page count — corrected; the two-page-per-letter-boundary sharing
is why occurrences exceed distinct pages) are ProofreadPage quality 3
("Proofread", 778 occurrences / 687 distinct pages) or 4 ("Validated", 2
occurrences / 1 distinct page) — **zero** below quality 3 — despite the
Letter-page Index itself being only nominally/formally unproofread as a
wrapper concept. Every page's own `data-page-quality` value is captured
and declared in `gummere.integrity.json` (see below); any future rerun
where a page's quality changes is fatal.

Extracted 2026-07-21. Invocation: `cd pipeline && uv run python3
tools/extract_gummere_wikisource.py`. Fetch mechanics pin each mainspace
Letter page's own revision id (`_LETTER_REVISIONS` in the script, captured
at extraction time) and cache the rendered HTML under the untracked
`build/gummere-wikisource-cache/`, so a rerun with an unchanged table never
re-fetches. See the script's own docstring for the stated reproducibility
tradeoff (wrapper revisions are pinned; the underlying Page: namespace
revisions those wrappers transclude are not, unlike the Munro/Yonge ND
scripts' per-page pinning — drift in those transcluded revisions is instead
caught transitively by the per-letter content-hash declarations below,
since a changed Page: revision changes the rendered HTML this script hashes).

**Cache integrity (post-adversarial-review hardening)**: a GPT-5.6-Sol
review proved the untracked cache was trusted purely on file-existence,
with no validation of completeness — a truncated cached letter passed
every gate below while silently losing content. Fixed with atomic
write-temp-then-rename cache writes, envelope/completeness validation on
every cached-or-fetched response (rejecting anything missing its expected
trailing MediaWiki parser-cache comment or lacking exactly one
`prp-pages-output` div) before parsing, and a declared per-letter
rendered-HTML sha256 + per-page `data-page-quality` manifest,
`gummere.integrity.json` (generated once via `--bootstrap-integrity`
against this verified-good cache, checked bidirectionally — missing or
mismatched — on every subsequent run). SHA-256 of that manifest: see
`sources/INVENTORY.md`'s restated line. Full mechanics in the script's own
"Cache integrity" docstring section.

## Two declared per-letter numbering exceptions

Both are genuine section-boundary differences between Gummere's own
source text (Hense's 1898 Teubner edition) and this project's Latin spine
(Reynolds' 1965 Oxford Classical Text), cross-checked via a corpus-wide
per-section English/Latin word-count ratio sweep (2,093 one-to-one
section pairs, median ratio 1.76, zero outliers besides these two letters)
— not extraction bugs. Full analysis in the extractor's own module
docstring.

- **Letter 41**: Gummere's English carries 9 numbered markers where the
  Latin spine has 8. Marker "9" is folded onto the still-open section 8
  by the extractor itself (`_MERGE_TAIL`) — the shipped `gummere.clean.json`
  therefore has exactly 8 sections for letter 41, matching the Latin spine
  1:1, no manifest-level declaration needed. This fold is now asserted
  EXACTLY (`_assert_merge_invariant`): exactly one merge event, folding
  exactly into section 8, with marker 9 verified as the final raw marker
  in the letter, immediately following marker 8 — silently dropping or
  duplicating marker 9 is fatal.
- **Letter 108**: Gummere's English carries only 38 numbered markers where
  the Latin spine has 39 — English's own final marker (38) is the true
  end of the letter ("...Farewell."), with Latin's 108.39 folded into it
  with no separate marker. Left DECLARED (38 sections shipped, not 39):
  `manifests/epistulae-morales.yaml`'s `alignment_allow_unmatched: ["108:
  108.39"]`.

## Output

`gummere.clean.json` — 2,139 records, `{"book": letter, "section": n,
"text": "..."}` (letter.section list-of-records shape, matching
`extract_falconer_perseus.py`'s convention — `book` here is the LETTER
number). All 124 letters present. Section numbers strictly contiguous
from 1 within every letter. SHA-256: see `sources/INVENTORY.md`'s
restated line.

## Gates

Record count 2,139 (2,140 Latin spine columns minus the one declared
`108:108.39` gap). Zero empty records. Zero un-stripped HTML/entity
residue (`<`, `>`, `&#`, `cite-bracket`) in any cleaned text. Zero
duplicate or non-contiguous section-number sequences within any letter
(after the Letter 41 merge-fix, itself now asserted exact-once — see
above). Letter 1's salutation ("Greetings from Seneca to his friend
Lucilius.") found exactly once, corpus-wide across every FINAL record's
own text (not only the front `wst-center` divs the walker visits), at the
very start of letter 1 section 1. These empty-text/residual-markup/
salutation invariants are re-run a second time AFTER `PATCHES.json`
application, not only during per-letter parsing. Only the exact
tag/class-combination shapes verified present in the real corpus are
allowed to pass through as prose inside `prp-pages-output` — any other
element (e.g. an injected banner) is fatal, not silently flattened into
text. Every underlying page's own `data-page-quality` and every letter's
own rendered-HTML sha256 are checked against a declared, committed
manifest (`gummere.integrity.json`) bidirectionally on every run.
Deterministic double-run (byte-identical output, `sha256` unchanged across
two invocations against the warm local cache, itself now validated for
completeness before every parse — see "Cache integrity" above). 1,067
footnote reference marks excluded (house style — the note text itself
lives in each page's own `reflist`, a sibling of, never a descendant of,
the content this script walks). `PATCHES.json` is deliberately absent — no
genuine transcription defect was found during the spot-check below.

## Latin embedded in the English pages (orchestrator ruling, 2026-07-21)

Six verbatim Latin spans in `gummere.clean.json` (records for letters 58
and 114) happen to match this project's PHI Latin spine word-for-word.
This is NOT a corpus-source-text leak: Gummere himself prints these words
in Latin, inline, inside his own English pages — Letter 58 discusses the
missing Latin equivalent for Greek *ousia* and quotes an archaic four-word
Latin idiom for armed combat under discussion (span `d124697a2a0fe334` in
the table above; not quoted here per the hash-reference convention);
Letter 114 is Seneca's critique of
Sallust's compressed prose style and quotes several of Sallust's and
Arruntius' own Latin sentences verbatim as the illustrative examples being
criticized. Both letters are ABOUT Latin diction, so Gummere's English
translation necessarily reproduces the Latin words being discussed — the
same phenomenon as any English commentary quoting a foreign phrase it is
analyzing. These six spans reach this repo through an entirely
public-domain chain (the Wikisource transcription of Gummere's 1918/1925
Loeb English pages), merely coinciding with the separately-licensed PHI
Latin text at the same letter.section. Per the orchestrator's ruling
(2026-07-21, logged in `CANON.md`): the repo's no-corpus-text rule targets
PHI/TLG-*derived* data, not independently-PD-sourced translation content
that happens to quote the same words — these six spans are correctly kept
verbatim in `gummere.clean.json`, not redacted.

Identified by letter.section and the first 16 hex characters of the
sha256 digest of the whitespace-normalized span text (this project's
standard hash-reference convention — see `pipeline/reader_pipeline/
stage1_chapter_concordance_english.py`'s `_anchor_hash` for the same
convention elsewhere); the Latin itself is deliberately NOT quoted here:

| Letter.section | sha256-16 | Span length |
|---|---|---|
| 58.3 | `d124697a2a0fe334` | 4 words |
| 114.17 | `bb85f71b944f4008` | 5 words |
| 114.17 | `a082a04f5f0efc7f` | 6 words |
| 114.19 | `b0ec977f2188a1d3` | 4 words |
| 114.19 | `7d92382e7748beda` | 12 words |
| 114.19 | `7fc5b0f020d424f4` | 7 words |

## Spot-check vs. archive.org OCR

14 letters spread across all three volumes (6 from Vol. I, 4 from Vol. II,
4 from Vol. III), each checked by locating a distinctive phrase from the
Wikisource-extracted text in that volume's own `_djvu.txt` OCR:

| Letter | Volume | Verdict |
|---|---|---|
| 1 | I | Match — verified directly (OCR itself misreads "Continue" as "CoNTHrui"; Wikisource's human-proofread "Continue" is correct against the scan) |
| 10 | I | Match (direct substring hit) |
| 25 | I | Match (direct substring hit) |
| 40 | I | Match (direct substring hit) |
| 55 | I | Match (direct substring hit) |
| 65 | I | Match — verified directly ("...claimed for itself all the period before noon; in the..." found verbatim; the shorter automated probe phrase happened to straddle an OCR-garbled word) |
| 66 | II | Match — verified directly (OCR misreads "Claranus" as "Claraiius"; Wikisource's "Claranus" is correct against the scan) |
| 75 | II | Match (direct substring hit) |
| 80 | II | Match (direct substring hit) |
| 90 | II | Match (direct substring hit) |
| 93 | III | Match (direct substring hit) |
| 100 | III | Match (direct substring hit) |
| 110 | III | Match (direct substring hit) |
| 124 | III | Match (direct substring hit) |

14/14 confirmed matches (11 by direct normalized-substring search against
the OCR full text, 3 verified manually where the automated probe phrase
happened to straddle an OCR misreading — in every one of those 3 cases the
OCR is what's wrong, not the Wikisource transcription, confirmed by
reading the surrounding OCR context directly). No genuine content
discrepancies found; no patches needed.
