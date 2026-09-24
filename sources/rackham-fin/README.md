# Rackham's De Finibus Bonorum et Malorum (Cicero) — English

**Status: INCOMPLETE / NOT READY TO WIRE INTO THE READER.** This directory
holds a partial, best-effort automated extraction. It is 368 of the
required 443 section records (83%), and a hand proofing pass against the
second witness found confirmed content defects (not just missing
sections) in several of the 368 "present" records too. See "Known
problems" below before using this data for anything beyond further repair
work. Nothing here has been wired into the app or committed to git by
this pass.

## Witness identity

**Primary**: archive.org item `CiceroRackhamDeFinibusBonorumEtMalorum`
("Cicero - Rackham - De_Finibus_Bonorum_Et_Malorum"). Title page: "THE
LOEB CLASSICAL LIBRARY ... CICERO DE FINIBUS BONORUM ET MALORUM WITH AN
ENGLISH TRANSLATION BY H. RACKHAM, M.A., FELLOW AND TUTOR OF CHRIST'S
COLLEGE, CAMBRIDGE ... LONDON: WILLIAM HEINEMANN NEW YORK: THE MACMILLAN
CO. MCMXIV" (1914). This is the Loeb *first* edition, not Perseus's 1931
second edition. This script reads the item's word-level `_djvu.xml` (not
the flattened `_djvu.txt`) for per-page and per-word geometry; raw files
(not committed — see `pipeline/tools/extract_rackham_fin.py`'s module
docstring) are staged at `build/rackham-fin/`:

| File | SHA-256 |
|---|---|
| `CiceroRackhamDeFinibusBonorumEtMalorum_djvu.xml` | `6095d38a06e5bf91daebe7160ca89ad13e1de06020cc60d89b347cc87c5e4285` |
| `CiceroRackhamDeFinibusBonorumEtMalorum_djvu.txt` (flat OCR, reference only, not used by the final extractor) | `3762d955c296c5f4b6ea69df30aacb8430cf85ab029642c6d98e56d55704ccd5` |

**Second witness (proofing)**: Loebolus L040 PDF
(`https://ryanfb.xyz/loebolus-data/L040.pdf`), the PD-curated first-edition
scan of the same volume (page footer "Digitized by Google" — a distinct
physical scan from the archive.org item; confirmed by a stable **archive
page N == Loebolus PDF page N+3** offset, checked at all five Book-opening
Latin title pages). SHA-256: `1b6573c13bb8d04546724e742d7c491ec6b462c57a8fd1e713c4b62ee8b206cc`. This PDF has no embedded text layer (image-only scan); proofing was done
by rendering specific pages to PNG (`pdftoppm -r 200`) and reading the
image directly, not by re-OCRing it (a second OCR pass would just add a
second layer of noise, defeating the point of a witness comparison).

## US public-domain basis

Published 1914 (per title page "MCMXIV" and archive.org catalog
metadata). Under US copyright law, works published before 1929 (and, per
this project's own pre-1931-as-of-2026 policy line, well before that) are
conclusively in the US public domain regardless of renewal status — 1914
is 96 years earlier than even the conservative cutoff. Not the 1931 second
edition (which some sites host under a Canada-only PD claim); confirmed
from the primary scan's own title page and confirmed independently via
the Loebolus second witness (Loebolus only mirrors first editions).

## Extraction pipeline

`pipeline/tools/extract_rackham_fin.py` (see its module docstring for the
full method — page classification, section-marker recovery via LCS
alignment, footnote/garbage-token cleanup, dehyphenation). Run:

```
cd pipeline/tools && python3 extract_rackham_fin.py
```

Requires `build/rackham-fin/CiceroRackhamDeFinibusBonorumEtMalorum_djvu.xml`
(download from archive.org; not committed, see hash table above).

Tests: `pipeline/tests/test_extract_rackham_fin.py` (offline, pure
functions only — `uv run --with pytest pytest tests/test_extract_rackham_fin.py`
from `pipeline/`). All pass.

## Known problems (why this is not ready to ship)

### 1. 75 of 443 section markers are not recoverable from this OCR pass

The Loeb marginal Arabic section number is usually OCR'd as the leading
token of whichever line it sits beside, but this scan's digit OCR is
unreliable: digits get merged with adjacent noise, split apart ("19" →
"1" + "9" on separate tokens), or misread in ways that collide with
*other* valid target values ("33"/"34" misread as "13"/"14", landing on
tokens that a naive scan would wrongly accept for the wrong section). A
Longest Common Subsequence alignment (see script docstring) against the
fixed target sequence [1..N] recovers the maximum achievable match and
reports the rest as **explicit, un-silenced gaps** — a gap's underlying
text currently stays merged into the *previous* record (i.e. the
records around a gap are NOT reliable either — see problem 3).

Gap counts, by book (missing section numbers):

| Book | Present | Missing | Missing sections |
|---|---|---|---|
| 1 | 62/72 | 10 | 10, 13, 14, 19, 21, 33, 34, 40, 41, 63 |
| 2 | 113/119 | 6 | 21, 38, 56, 83, 95, 96 |
| 3 | 70/76 | 6 | 3, 25, 58, 59, 64, 65 |
| 4 | 74/80 | 6 | 15, 23, 42, 43, 46, 72 |
| 5 | 49/96 | 47 | 22, 23, 28, 35–42, 47–52, 55, 57, 61, 63–72, 78–86, 89–96 |

Book 5's gap rate (49%) is qualitatively different from Books 1–4
(8–14%): manual inspection of several Book 5 candidate tokens confirms a
*systematic* tens-digit misread pattern in that stretch of the scan (e.g.
"35"→"85", "39"→"99", "42"→"12") rather than isolated misses — this reads
as a genuine scan/print-quality defect in that portion of the physical
copy, not a tunable bug in the extractor. Closing these will need either
a different/better scan of Book 5, or a substantially larger manual
transcription effort against the second witness than the "declared
per-gap reconstruction" the brief anticipated.

Gap 1.10 was specifically checked against the Loebolus image (pp. 9–11 of
the printed book): **no marginal "10" is visible in the print at all**
across the two English pages spanning that stretch — the gap may not be
purely an OCR artifact but a case where the target Latin-spine section
boundary doesn't align with a distinct marginal numeral in this English
edition's print layout. This needs philological judgment (do the Latin
and English editions' section 10 boundaries actually coincide here?) that
is out of scope for this pass — flagging for Opus-level review rather
than guessing.

### 2. Marginal-gloss contamination survives in the "present" 368 records

This edition prints short marginal "argument" glosses (e.g. "Preface:
choice of subject defended;") in the outer margin of every English page,
typeset smaller. This OCR pass merges gloss words into the same `<LINE>`
as the body text at that line's height, with ordinary-looking inter-word
spacing — no reliable per-word geometric signal (x-position, glyph
height) separates them in this scan (verified: glyph bounding-box height
is dominated by ascender/descender shape, not font size, so a height
threshold flags ordinary short body words like "to"/"a"/"not" as often as
real gloss fragments — see script docstring). `_GARBAGE_TOKEN` strips the
subset of gloss fragments that carry this scan's OCR-corruption signature
(a stray `^`/`«`, or an internal lowercase-to-uppercase glyph transition
no genuine body word has), which catches the badly-garbled majority but
not gloss fragments the OCR happened to read cleanly (e.g. "The
Philosophy" bled into 1.2's text; "his Ethical" and a garbled "contrary to
fact:" fragment bled into 1.23's text — confirmed against the Loebolus
image, see problem 3 below for the direct comparison).

### 3. Proofing pass: confirmed error rate exceeds the ~1/section bar

Per the brief's requirement, sampled sections were compared word-by-word
against rendered Loebolus page images (not a second OCR pass — see
witness note above). Five sections were rendered and read in full across
Books 1 and 4 (the full 25-section/all-5-books sample specified by the
brief was NOT completed — this pass stopped once a clear, reproducible
problem pattern was confirmed, per the brief's own "if the sampled error
rate exceeds ~1 error per section, STOP and report" clause):

| Section | Confirmed defects found |
|---|---|
| 1.1/1.2 | gloss bleed ("Preface: choice", "The Philosophy"); page-footer-number leak ("m 3") |
| 1.23 | gloss bleed ("his Ethical", a garbled "contrary to fact:" fragment); **dropped body text** — "lie at the root of every act of choice and of avoidance" collapses to a stray "He" |
| 4.4 | page-footer-number leak ("304"); OCR digit corruption "(3)"→"(8)" |
| 4.12 | page-footer-number leak ("818"→ shown as "813" in one read); a dropped word ("followed") producing "the Stoics the Peripatetics" instead of "the Stoics followed the Peripatetics"; "reason and and bound up" (a dropped "intellect,") |

That is 2+ confirmed defects in every one of the 5 sections actually
checked, i.e. well over the ~1/section bar the brief sets as the stop
condition — including at least one case (1.23) of real translated-text
loss, not just cosmetic noise. **Per the brief: STOP and report rather
than ship.** No PATCHES.json entries have been written for these, because
they are OCR/extraction defects in this pass, not print-level errata in
the original book (PATCHES.json's stated purpose) — fixing them belongs
in the extractor or in a re-proofed, corrected data pass, not as
exact-once patches papering over a systematic problem.

## Recommendation

Do not wire this into the reader or treat `rackham.clean.json` as
authoritative. Two paths forward, either of which is a larger effort than
this pass: (a) invest in a proper geometric/layout-aware re-OCR of the
archive.org scan (ideally recovering true column separation so gloss text
is excluded structurally, not lexically) and a full line-by-line
proofing pass against the second witness for all 443 sections, or (b)
locate a cleaner already-transcribed source. Perseus's `canonical-latinLit`
(used successfully for Miller's *De Officiis*, see
`extract_miller_perseus.py`) and en.wikisource.org were both checked and
do **not** have Rackham's *De Finibus* (Wikisource's Loeb Classical
Library index page links out to the Loebolus scan only, confirming no
transcription exists there either) — so archive.org OCR is the only
currently-available source, as the original brief assumed.
