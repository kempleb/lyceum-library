# Source inventory — Ancient Philosophy Reader (English translations)

Public-domain English translations only, judged by **US** copyright rules
(pre-1931 publication, per CLAUDE.md). Corpus source text (TLG Greek / PHI
Latin) is never committed and does not appear here.

## Marcus Aurelius, *Meditations* (work W1a)

### PRIMARY — C. R. Haines, *The Communings with Himself of Marcus Aurelius
Antoninus* (Loeb Classical Library, 1916), sourced via Wikisource

**2026-07-16 re-sourcing: the shipped `haines.clean.json` is now built from
Wikisource's human-proofread transcription of the same 1916 Haines
translation, not from OCR.** The OCR chain described below (raw
`_djvu.txt` scans, `extract_haines.py`, `PATCHES.json`) is retained in
place, untouched, as a verification witness — see "Wikisource re-sourcing
and verification" further down this section for why, and for the full
diff-based comparison against it.

| | |
|---|---|
| Translator | Charles Reginald Haines |
| Source | Wikisource, `Marcus Aurelius (Haines 1916)` (en.wikisource.org), 12 `.../Book N` subpages |
| Source URL | https://en.wikisource.org/wiki/Marcus_Aurelius_(Haines_1916) |
| Underlying scan | Wikisource's own djvu scan of the same 1916 Loeb first printing (`Marcus Aurelius (Haines 1916).djvu`), proofread by Wikisource contributors against the page images (ProofreadPage quality 3 = "Proofread" — one pass short of "Validated") |
| Fetched | 2026-07-16, via MediaWiki `action=parse&oldid=<revid>&prop=text` (pinned revisions, not "latest" — see table below) |
| Extraction tool | `pipeline/tools/extract_haines_wikisource.py` |
| File | `haines-meditations/haines.clean.json` (486/488 chapters — see coverage gaps below) |
| SHA-256 (haines.clean.json) | `f473750dd75274a5d82c768234f07466cba3d3022df4097a83b29c01ced82207` |

**Per-book pinned revisions** (captured 2026-07-16 via `action=query&prop=revisions`):

| Book | Page | Revision ID | Timestamp |
|---|---|---|---|
| I | `.../Book 1` | 14039740 | 2024-04-10T11:10:34Z |
| II | `.../Book 2` | 14041829 | 2024-04-11T11:21:05Z |
| III | `.../Book 3` | 14062858 | 2024-04-16T15:57:40Z |
| IV | `.../Book 4` | 14085030 | 2024-04-18T13:30:48Z |
| V | `.../Book 5` | 14148813 | 2024-04-29T21:05:39Z |
| VI | `.../Book 6` | 14149965 | 2024-04-30T10:32:33Z |
| VII | `.../Book 7` | 14149990 | 2024-04-30T10:56:58Z |
| VIII | `.../Book 8` | 14007301 | 2024-04-01T08:56:22Z |
| IX | `.../Book 9` | 14013645 | 2024-04-03T13:36:38Z |
| X | `.../Book 10` | 14019457 | 2024-04-05T08:18:41Z |
| XI | `.../Book 11` | 14031354 | 2024-04-08T11:07:05Z |
| XII | `.../Book 12` | 14037608 | 2024-04-09T16:40:45Z |

**Edition verification.** The Wikisource page's own front matter (rendered
HTML) reads "THE LOEB CLASSICAL LIBRARY / EDITED BY / E. CAPPS ... T. E.
PAGE ... W. H. D. ROUSE" and "A REVISED TEXT AND A TRANSLATION INTO ENGLISH
BY C. R. HAINES" — the same 1916 first printing as the OCR witness below,
transcribed from Wikisource's own scan of it (not a different edition or a
1930s revision).

**Known residual defects in the Wikisource text itself** (it is
"Proofread", not yet "Validated" quality): five transcription slips were
found across the verification diff and the independent verification rounds —
8.25 "Antoņinus" (stray cedilla; same sentence's next word correctly reads
"Antoninus"), 11.1 "oceurs" for "occurs" (dictionary typo), 9.3 "them,.yet"
(a stripped footnote-ref scar: the print has a superscript mark after the
comma; its removal left a stray "." and ate the space), 8.31 "dearth"
for "death" (adjudicated against THREE witnesses: both OCR scans read
"death", and the corresponding source clause means "death"), and 8.31
"the man s ancestors" for "the man's ancestors"
(dropped apostrophe; both scans read "man's"). All five are corrected in
the shipped text by hand-verified, fail-loud patches in
`haines-meditations/WIKISOURCE-PATCHES.json` (applied by
`extract_haines_wikisource.py`'s `_apply_patches`, same exactly-once-match
philosophy as the OCR chain's PATCHES.json) — each entry records the print
reading with exact witness line numbers in both scans. If a future
pinned-revision bump picks up Wikisource's own fix of any of these, the
stale patch fails the build loudly rather than silently no-op'ing.

#### OCR chain (retained as verification witness, no longer the shipped source)

| | |
|---|---|
| Translator | Charles Reginald Haines |
| Publisher | London: W. Heinemann; New York: G. P. Putnam's Sons |
| Publication year | 1916 (preface dated "Godalming, 1915") |
| US-PD rationale | Published 1916, pre-1931 — safely US public domain |
| Source | archive.org, identifier `thecommuningswit00marcuoft` |
| Source URL | https://archive.org/details/thecommuningswit00marcuoft |
| Contributor/scan | Kelly Library, University of Toronto; scanned 2006 (Microsoft-funded) |
| Retrieved | 2026-07-15, via `<identifier>_djvu.txt` OCR-text derivative |
| File | `haines-meditations/thecommuningswit00marcuoft_djvu.txt` (raw OCR text, pristine — no cleanup applied) |
| SHA-256 | `856b7f1bdeb7a47eec27be8a2b8368d177c2b15be0a941f7b4217d4557f5f73d` |
| Extraction tool | `pipeline/tools/extract_haines.py` (OCR page-side/footnote-zone heuristics, `PATCHES.json` hand patches, and a deterministic `,!`/`,?` footnote-superscript-mark rule — see the script's module docstring) |

**Edition verification.** archive.org catalog metadata records `date: 1916`,
`creator: Haines, Charles Reginald`, `title: The communings with himself of
Marcus Aurelius Antoninus, emperor of Rome ... a revised text and a
translation into English by C.R. Haines`, `possible-copyright-status:
NOT_IN_COPYRIGHT`, `copyright-region: US`. The scanned preface is dated
"Godalming, 1915" and the OCR text's own front matter reads "THE LOEB
CLASSICAL LIBRARY / EDITED BY / E. CAPPS ... T. E. PAGE ... W. H. D. ROUSE" —
this is genuinely the first (1916) Loeb printing, matching the title-page
imprint, not a 1930s revised reprint.

Two further archive.org scans of the same 1916 edition were pulled in
2026-07-16 as EXTRA cross-checking witnesses (not the shipped source, not
`thecommuningswit00marcuoft`'s replacement — used only to verify specific
OCR-garbled proper names/words against an independently-OCR'd second and
third copy before this repo learned about the Wikisource transcription):

| | Toronto/PIMS scan | Google Books (Univ. of Michigan) scan |
|---|---|---|
| Identifier | `communingswithhi00marc` | `communingswithh00haingoog` |
| Source URL | https://archive.org/details/communingswithhi00marc | https://archive.org/details/communingswithh00haingoog |
| Scanned | 2011 (PIMS/Toronto) | ~2009 (Google Books; U. Michigan copy, "gift of Prof. Alexander Ziwet") |
| File | `haines-meditations/communingswithhi00marc_djvu.txt` | `haines-meditations/communingswithh00haingoog_djvu.txt` |
| SHA-256 | `d11906934b4bc1b2b36fcbba1e9de7c9000fabf6f0ef6f1bf038c9e3a111309c` | `9fbebabfa92f0f89f773cef8fc91ced98eb387d3034c2c23f3e7133c0a658e50` |

Both spot-checked and rejected as a raw *extraction* source (visibly worse
OCR than `thecommuningswit00marcuoft` — e.g. the Toronto scan renders "BOOK
an incorrect character for "BOOK II", "dajbreak" for "daybreak"; the Google scan has its own
independent scattering of misreads). Retained here purely as evidentiary
witnesses (now superseded in that role too by the Wikisource transcription,
which is what the shipped file is actually built from).

**Structure / section marking.** This is a bilingual Loeb edition (facing
Greek and English on opposite pages), so the OCR text interleaves Greek-page
and English-page content in page-scan order. Book divisions are marked by a
plain running header `BOOK I` … `BOOK XII` (repeated on most pages, both
Greek and English sides, since it's a page header — not a per-section
marker). Within each book, sections are **numbered inline with Arabic
numerals + period** at the start of each section's first line (e.g. `5. From
my Tutor,¹ not to side with...`), directly usable as `(book, section)`
anchors for stage1_archive once Greek-page content is filtered out. All 12
books (I–XII) are present, confirmed by header count (14, 7, 10, 15, 17, 16,
15, 16, 15, 16, 15, 11 occurrences respectively for I–XII — this is the
raw per-page header count, not section count). The *Meditations* proper runs
from the `BOOK I` heading to just before `THE SPEECHES OF MARCUS` (the
appendix of separately-transmitted speeches/sayings, included in the same
Loeb volume but not part of the twelve books) — this appendix is not part of
work W1a and should be excluded at stage-1 archive time.

**OCR quality assessment.** Spot-checked 2.1, 4.23, and 5.16 against the
well-known English of these passages — all three are clean and legible in
the English-page portions:
- 2.1: "Say to thyself at daybreak: I shall come across the busy-body, the
  thankless, the bully, the treacherous, the envious, the unneighbourly..."
- 4.23: "All that is in tune with thee, O Universe, is in tune with me..."
- 5.16: "...the character of thy frequent thoughts, for the soul takes its
  dye from the thoughts. Dye her then with a continuous succession of such
  thoughts as these..."

English-page body text is **usable as-is** for these passages — no gross OCR
catastrophe. However, because this is a facing-Greek bilingual edition, the
Greek pages are heavily present in the raw file and their OCR is garbage
(the OCR engine transliterated Greek into nonsense Latin-alphabet strings
rather than Greek Unicode — zero actual Greek-Unicode characters appear
anywhere in the file, confirmed by scan). A line-level heuristic count
(lines containing common English stopwords, over the Book I–XII span only)
found **~33% clearly-English lines, ~31% blank, ~36% non-English/garbled**
— i.e. roughly a third of the raw file by line count is Greek-page OCR noise
or apparatus that stage-1 cleanup will need to strip. Footnotes (critical
apparatus, citing Greek sources) also contain garbled Greek fragments mixed
into otherwise-legible English footnote text.
**Estimate: needs an OCR post-processing / Greek-page-stripping pass before
ingestion** — the English-page prose itself is high quality, but a naive
line-by-line ingest would pull in ~1/3 unusable content. The existing
`pipeline/reader_pipeline/... ocr_postprocess.py` tooling (used elsewhere in
this repo) is the likely fit for this pass; not run here — out of scope for
sourcing.

---

### SECONDARY — George Long, *Thoughts of Marcus Aurelius Antoninus* (1862;
this text = Bohn's revised edition as reprinted by Project Gutenberg)

| | |
|---|---|
| Translator | George Long (1800–1879) |
| Publication year | 1862 (first edition; PD rationale independent of PG's re-publication date) |
| US-PD rationale | Published 1862, far pre-1931 — safely US public domain |
| Source | Project Gutenberg eBook **#15877**, "Thoughts of Marcus Aurelius Antoninus" |
| Source URL | https://www.gutenberg.org/ebooks/15877 |
| Retrieved | 2026-07-15, via `https://www.gutenberg.org/ebooks/15877.txt.utf-8` |
| Files | `long-meditations/pg15877.txt` (raw, includes PG header/license/footer, pristine); `long-meditations/pg15877.clean.txt` (cleaned — see below) |
| SHA-256 (raw) | `6584df7e90d6035eece30d8028527290bf2508076963ee0376cb41db9cf88d5b` |
| SHA-256 (clean) | `ee832ed7ff32f1376e2616c3d15f006a034fc922d0bb21c14781de77be9c874f` |

**Translator verification — course correction from the brief.** The brief's
suggested identifier, Gutenberg **#2680** ("Meditations"), was fetched and
checked first, but is **not** George Long's translation: its own in-text
"NOTES" section states the text is "neither a critical edition of the text
nor an emended edition of **Casaubon's** translation" (Meric Casaubon,
1634) — confirmed by the archaic "doth"/"shalt thou" diction and Roman-
numeral section marks throughout, unlike Long's plainer prose. PG's own
metadata for #2680 also carries no `Translator` field at all, unlike proper
Long editions. Rejected as mislabeled for this purpose.

Two genuine George Long editions exist on Gutenberg, both with an explicit
`Translator: Long, George, 1800-1879` metadata field: **#6920** ("Thoughts
of Marcus Aurelius", 2004, older OCR-sourced transcription) and **#15877**
("Thoughts of Marcus Aurelius Antoninus", 2005/rev. 2020, PGDP-proofread).
PG's own catalog entry for #6920 flags "There is an improved edition of this
title, eBook #15877" — **#15877 was used** as the better-quality, more
recently updated text. Spot-checked 2.1 ("Begin the morning by saying to
thyself, I shall meet with the busybody..."), 4.23 ("Everything harmonizes
with me, which is harmonious to thee, O..."), and 5.16 ("Such as are thy
habitual thoughts, such also will be the character...") — all present and
match Long's known phrasing.

**Structure / section marking.** No literal word "BOOK" — each of the 12
books opens with its own line containing **only a Roman numeral + period**
(`I.`, `II.`, ... `XII.`), confirmed present for all twelve (line numbers in
the raw file: 2129, 2493, 2725, 2994, 3446, 3878, 4332, 4933, 5419, 5865,
6375, 6817). Within each book, sections are **numbered inline with Arabic
numerals + period** at the start of the section (the first section after
each Roman-numeral book head is unnumbered/implicit "1", subsequent
sections are numbered "2.", "3.", ... explicitly) — same
`(book, section)`-anchor-friendly shape as Haines, though the book head
token differs (bare Roman numeral vs. "BOOK <roman>").

**OCR quality.** Not an OCR text — this is a PGDP (Distributed
Proofreaders) hand-transcribed/proofread edition, effectively born-digital
quality. No OCR post-processing needed. The file also includes George
Long's own substantial "Biographical Sketch" and "Philosophy of Marcus
Aurelius Antoninus" essays before "THE THOUGHTS" proper begins, plus an
"Index of Terms" and "General Index" after Book XII — all out of scope for
work W1a (the Meditations text itself) and should be excluded/skipped at
stage-1 archive time, same as Haines' Speeches/Sayings appendix.

**Cleanup applied (`pg15877.clean.txt` vs. raw `pg15877.txt`).** Removed:
(1) Project Gutenberg's boilerplate legal header (everything before the
`*** START OF THE PROJECT GUTENBERG EBOOK ... ***` marker); (2) the PGDP
transcriber-credit block immediately following the marker; (3) Project
Gutenberg's boilerplate legal footer (everything from `*** END OF THE
PROJECT GUTENBERG EBOOK ... ***` onward, including the full License
section). The cleaned file starts directly at the book's own title page
("THE THOUGHTS / OF / THE EMPEROR / MARCUS AURELIUS ANTONINUS") and ends at
the book's own "THE END." — no Gutenberg license text is present in the
clean copy, so it is safe to feed into rendering/ingestion. The raw copy is
left untouched (license intact) as the pristine record of what was
downloaded.

---

### Stage-1 extraction (W1a-D): clean per-chapter JSON

Long is ingested via a deterministic extraction pass over its cleaned
Gutenberg text (`pipeline/tools/extract_long.py` — run from `pipeline/`,
e.g. `uv run python tools/extract_long.py`). Haines is now built by
**`pipeline/tools/extract_haines_wikisource.py`**, which fetches the pinned
Wikisource revisions (see the PRIMARY section above) over the network and
parses the rendered HTML directly — there is no separate "clean" input file
to point at (the fetch and the extraction are the same step). Both produce a
`{"<book>.<chapter>": "text"}` JSON map keyed exactly like the Greek
book-section spine's dotted column tokens; `stage1_book_section_english.py`
reads these directly (book-section's translation-to-column mapping is 1:1,
so no proportional interpolation is needed, unlike a Bekker archive
translation).

| | Haines (primary, Wikisource) | Long (secondary) |
|---|---|---|
| File | `haines-meditations/haines.clean.json` | `long-meditations/long.clean.json` |
| Chapters | 486 / 488 | 487 / 488 |
| SHA-256 | `f473750dd75274a5d82c768234f07466cba3d3022df4097a83b29c01ced82207` | `9b111ff4b8344b4700066f18da36bda34ec6829f9243692ea6f0aca740ee9ad7` |

**Known coverage gaps** (also recorded in `manifests/meditations.yaml`):

- **5.37** — missing from BOTH translations. Neither the 1916 Haines nor the
  1862 Long source edition marks a separate section here; both run it
  straight into 5.36 (cross-validated: the two independent translations
  agree on where their own text ends, and Haines' Wikisource transcription
  confirms the same numbering as the old OCR — chapter numbering simply
  stops at "36." for book 5, not a skipped-number gap). A genuine
  translator/edition numbering divergence from the Farquharson Greek text
  used for this build, not an extraction bug.
- **12.15** — Haines only, confirmed genuinely absent by BOTH the OCR scan
  and the independent Wikisource transcription (numbering jumps "14." ->
  "16." in Wikisource's own text too). Long (secondary) covers it (186
  chars in `long.clean.json`), so every chapter has a public-domain
  translation from at least one source.
- **11.31, 11.34 — RECOVERED.** The old OCR pipeline treated these as
  unrecoverable gaps (the 1916 scan's chapter-marker digits were corrupted
  beyond `extract_haines.py`'s deterministic recovery). Wikisource's
  human-proofread transcription has both, cleanly: 11.31 is a genuinely
  short/lacunose entry in the manuscript tradition ("﻿. . . . and within me
  my heart laughed."), and 11.34 is a full paragraph (the Epictetus
  child-kissing anecdote). `manifests/meditations.yaml`'s
  `alignment_allow_unmatched` no longer lists either.

#### OCR extraction chain (retained as verification witness)

`pipeline/tools/extract_haines.py` (page-side/footnote-zone/apparatus
heuristics + `PATCHES.json` hand patches + a deterministic `,!`/`,?`
footnote-superscript-mark rule) still runs against the raw OCR scans and
still produces a `haines.clean.json`-shaped output — just not the file the
pipeline reads anymore. It exists purely so the diff-based verification
below has a "before" state to compare the Wikisource text against, and so
a future re-diff (e.g. after a Wikisource page is edited) has a stable OCR
baseline. Extracted 484/488 chapters (11.31, 11.34, 12.15 unrecovered, plus
the 5.37 cross-translation gap above); 11 hand-verified `PATCHES.json`
splice corrections (page-bottom OCR noise, marker-less footnote/apparatus
fragments, and Haines' own bracketed source-attribution labels — see the
script's docstrings for specifics) plus the corpus-wide `,!`/`,?` rule
(added 2026-07-16, ~90 sites, cross-checked against the two extra scan
witnesses before trusting it — see the rule's own docstring in
`extract_haines.py`).

**Hand-verified patches.** After three rounds of extraction heuristics, a
residual set of chapters still carried a splice — a page-bottom OCR-noise
leak (2.12), a marker-less footnote/apparatus fragment (5.4, 6.16, 9.42,
10.32, 9.21, 5.33), a footnote block spliced mid-word across a page break
(11.15), or a bracketed source-attribution label Haines himself set off in
brackets (7.35, 7.36, 7.44 — excluded under the same attribution-apparatus
policy as the Long-pipeline HESIOD/_Odyssey_ source-citation exclusions) —
that matched no general structural or content signal without risking
regressions on chapters that already extract clean. Rather than add more
heuristic rules chasing single-occurrence defects, these are closed the
same way the sibling repos (see e.g. `plato-reader/sources/perseus-eng/
PATCHES.md`) close their own last-mile residuals: 11 hand-verified,
per-chapter, exact-string corrections in `haines-meditations/PATCHES.json`,
applied by `extract_haines.py`'s `_apply_patches` step as the last stage of
the build (after the comma-mark rule), each with a `note` recording what
the contamination was and the raw `_djvu.txt` line range it came from.
Every patch is verified against the raw scan to keep exactly Haines'
printed text (no composed or paraphrased wording) and to confirm no genuine
translation text is lost at the splice point. A patch whose exact-string
target no longer appears (extraction output changed, or the patch itself is
wrong) fails the build loudly rather than silently no-op'ing.

### Wikisource re-sourcing and verification (2026-07-16)

An earlier session in this repo diagnosed and began hand-patching a set of
OCR defects in the (then-primary) OCR-extracted Haines text: 14 Book-1
small-caps-driven proper-name garbles, ~90 corpus-wide `,!`/`,?`
footnote-superscript-mark sites, and 8 chapters of minor mid-body OCR
noise. Before that patching effort went further, a research pass found
that Wikisource carries a complete, "Proofread"-quality, scan-backed,
human-transcribed copy of the exact same 1916 Haines translation — so the
project switched from *patching OCR* to *re-sourcing from a proofread
transcription* (see the PRIMARY section above for the fetch mechanics).
The `,!`/`,?` rule that had already been added to `extract_haines.py`
before the pivot was kept (it measurably improves the OCR chain's value as
a comparison witness — see below) but the 14 Book-1/8 minor-noise hand
patches were **not** added to `PATCHES.json`, since they're moot once
Haines ships from Wikisource; that patching work was superseded, not lost
(the diagnosis itself is preserved in this note and in the OCR witness
chain above).

**Verification methodology.** The OCR-derived `haines.clean.json` (with the
`,!`/`,?` rule applied, no further hand patches) was diffed chapter-by-
chapter against the new Wikisource-derived one, both keyed identically:

| | Count |
|---|---|
| Chapters in OCR only | 0 |
| Chapters in Wikisource only | 2 (11.31, 11.34 — recovered, see above) |
| Chapters identical byte-for-byte | 94 |
| Chapters differing (of 484 common) | 390 |
| — trivial only (whitespace/quote-style/hyphenation, normalizes to identical) | 222 |
| — substantive (real word-level difference) | 168 |

Every one of the 168 substantive-diff chapters was inspected (an automated
first pass flagged 63 as needing a human look — where the changed word(s)
on BOTH sides were real dictionary words rather than an obvious OCR
garble-string on the OCR side; the other 105 were confirmed OCR garble by
inspection of the specific non-word tokens involved, e.g. 1.16's
`",,,.,,"`/`"aul Deg"` mid-body noise, 7.53/7.56's leaked footnote-citation
fragments, 8.15's `"ReNeT"` for "fever"). Of the 63 flagged for a human
look, **every single one resolved to an OCR misread now corrected by the
proofread text** — mostly classic OCR letter-confusions (`Hither`/`Either`,
`mill`/`will`, `mith`/`nith`/`with`, `Werld`/`World`, `Tue`/`The`,
`Witr`/`Wilt`, `refi`/`reft`), several cases of OCR-dropped content now
restored (2.17's "Written at Carnuntum." colophon, 7.7's opening clause,
7.44/7.35's Plato-citation openers), and the previously-documented 12.34
truncation ("...contemned ed" -> "...contemned it."). **No genuine
word-choice ambiguity — i.e. no case where the two sources plausibly
disagree about what Haines actually wrote — turned up anywhere in the 168.**
The residual discrepancies worth flagging by name are Wikisource's own
minor, unambiguous transcription slips (see "Known residual defects in the
Wikisource text itself" in the PRIMARY section above: `Antoņinus` in 8.25,
`oceurs` in 11.1, `them,.yet` in 9.3, `dearth` in 8.31, and `man s` in
8.31) — typos and ref-removal scars, not contested readings; all five are
corrected in the shipped text via the fail-loud `WIKISOURCE-PATCHES.json`
mechanism with the witness evidence recorded in each patch entry. A later verification round also caught a
same-class defect in the EXTRACTOR rather than the transcription: lxml
joins text across `<br/>`/empty `wst-gap` spacer spans with no whitespace,
which had glued four Book-7 verse joins ("things,For" 7.38, "corn,And"
7.40, "spurned,For" 7.41, "]:I might" 7.44); fixed as a general rule in
`extract_haines_wikisource.py` (space inserted at those element joins, with
a no-network regression test in
`pipeline/tests/test_extract_haines_wikisource.py`), and a corpus-wide
re-extract sweep confirmed exactly those four chapters changed.

**Cross-translation length-ratio correlation** (Pearson r between
per-chapter character counts of Haines and Long, common chapters, a
consistency check two independent translations of the same content should
pass): **r = 0.9954** on the Wikisource-sourced Haines (n=486 common
chapters), up from r = 0.9838 on the OCR-sourced Haines (n=484) — the
cleaner text measurably tightens the cross-translation length relationship,
consistent with OCR noise having been a source of chapter-length outliers.

## Summary

| Work | Translator | Year | id | Book marker | Section marker | OCR quality |
|---|---|---|---|---|---|---|
| Meditations (primary) | C. R. Haines (Loeb) | 1916 | Wikisource `Marcus Aurelius (Haines 1916)` (pinned revisions; OCR scan `thecommuningswit00marcuoft` retained as witness) | `<p>` per chapter, "BOOK N" title block | `N.` inline | Human-proofread transcription ("Proofread" ProofreadPage quality); no OCR noise — see "Wikisource re-sourcing and verification" |
| Meditations (secondary) | George Long | 1862 | PG #15877 | bare `<ROMAN>.` on its own line | `<n>.` inline | Proofread, effectively born-digital — no OCR issues |

## Epictetus, *Discourses* + *Enchiridion* (Wave 1a, per `CANON.md` row)

### PRIMARY — W. A. Oldfather, *Epictetus: The Discourses as Reported by
Arrian, the Manual, and Fragments* (Loeb Classical Library, vol. I 1925,
vol. II 1928)

**Volume I — Discourses, Books 1–2**

| | |
|---|---|
| Translator | William Abbott Oldfather (1880–1945) |
| Publisher | London: William Heinemann Ltd; Cambridge, Mass.: Harvard University Press |
| Publication year | 1925 |
| US-PD rationale | Published 1925, pre-1931 — safely US public domain |
| Source | archive.org, identifier `epictetusdiscour01epicuoft` |
| Source URL | https://archive.org/details/epictetusdiscour01epicuoft |
| Contributor/scan | Kelly Library, University of Toronto (uploaded by KatieLawson) |
| Retrieved | 2026-07-16, via `<identifier>_djvu.txt` OCR-text derivative |
| File | `oldfather-epictetus/raw/epictetusdiscour01epicuoft_djvu.txt` (raw OCR text, pristine) |
| SHA-256 | `f6ee7e3ac0f6c3a731c0add0c44eb8dd166deac8d1c23a81ed253de60b3caf18` |
| Size | 997,767 bytes |

**Publication-year evidence.** The scanned copyright page itself (not just
catalog metadata — archive.org's own catalog field actually shows a
misleading "1926") reads: **"First printed 1925 / Reprinted 1946, 1956"**,
immediately following the "WILLIAM HEINEMANN LTD" imprint line. This is
genuinely the first Loeb printing (1925), not one of the later reprints —
the front matter also lists the Loeb general editors as "T. E. PAGE ...
E. CAPPS ... W. H. D. ROUSE ... L. A. POST ... E. H. WARMINGTON", matching
the mid-1920s editorial board.

**Translator verification.** Title page: "EPICTETUS / THE DISCOURSES AS
REPORTED BY ARRIAN, THE MANUAL, AND FRAGMENTS / WITH AN ENGLISH TRANSLATION
BY / W. A. OLDFATHER / UNIVERSITY OF ILLINOIS". Matches Oldfather's known
authorship (LCL 131) and Harvard UP's own current catalog listing for the
same volume/ISBN.

**Volume II — Discourses, Books 3–4; the Manual (Enchiridion); Fragments**

| | |
|---|---|
| Translator | William Abbott Oldfather |
| Publisher | London: William Heinemann; New York: G. P. Putnam's Sons |
| Publication year | 1928 |
| US-PD rationale | Published 1928, pre-1931 — safely US public domain |
| Source | archive.org, identifier `in.ernet.dli.2015.185339` |
| Source URL | https://archive.org/details/in.ernet.dli.2015.185339 |
| Contributor/scan | Digital Library of India / IIIT Allahabad |
| Retrieved | 2026-07-16, via `<identifier>_djvu.txt` OCR-text derivative |
| File | `oldfather-epictetus/raw/in.ernet.dli.2015.185339_djvu.txt` (raw OCR text, pristine) |
| SHA-256 | `de8a7162adf3c00b11eacda957969233af88c55718e2d6871fb7b58ddb0061ba` |
| Size | 1,163,547 bytes |

**Publication-year evidence.** The scanned title page reads "IN TWO VOLUMES
/ VOL. II / DISCOURSES, BOOKS III AND IV, THE MANUAL, AND FRAGMENTS /
LONDON : WILLIAM HEINEMANN / NEW YORK : G. P. PUTNAM'S SONS / MOMXXVIII" —
the OCR mis-scans the Roman numeral (mistaking C for O), but MOMXXVIII
decodes as **MCMXXVIII = 1928**, matching the external, independently-
sourced citation "Epictetus. Vol. II. Text and translation by W. A.
Oldfather. Pp. 559. (Loeb Classical Library.) London: Heinemann; New York:
Putnam's, 1928" (Cambridge *Classical Review* contemporary notice). archive.org's
own catalog metadata for this item is marked `Out_of_copyright`. Item is
freely downloadable (no CDL/borrow restriction), unlike a duplicate
archive.org scan discussed below.

**Rejected alternative scan.** A second archive.org copy of vol. II,
identifier `epictetuswitheng0002epic` ("Epictetus. With an English
Translation By W. A. Oldfather. Vol. II...", catalog date oddly listed as
1952 — almost certainly a Harvard UP reprint's CDL metadata, not the 1928
first printing), is `access-restricted-item: true` (controlled digital
lending only, "No suitable files to display" for full-text download).
Rejected in favor of `in.ernet.dli.2015.185339`, which is freely
downloadable and whose own scanned title page carries the 1928 imprint.

**Translator verification.** Vol. II title page carries the identical
"WITH AN ENGLISH TRANSLATION BY / W. A. OLDFATHER / UNIVERSITY OF ILLINOIS"
attribution as vol. I.

**Structure / section marking.** Both volumes are bilingual Loeb editions
(facing Greek and English), and — unlike the Haines *Meditations* OCR,
which rendered zero actual Greek Unicode — this OCR **does** capture real
Greek-Unicode text on the Greek-facing pages (spot-checked: Greek
characters present). Page-side discrimination is
easier here than for Haines: the recto (English) pages carry a running
header giving a **locator range**, not just a bare book number — e.g.
`BOOK I..1 3-11` (book, chapter, section-range covered on that page) in
vol. I, `BOOK III. 1. 1~3` in vol. II — vs. the verso (Greek) pages, which
carry Greek-script headers instead.
125 English-page locator headers were found in vol. I alone; the pattern
recurs throughout vol. II (Book III alone produced dozens in a sample
grep). Chapter/section numbers are otherwise inline lowercase Roman
(chapter) + Arabic (section), matching the Loeb convention, e.g. "BOOK I.
1. 3–11" = Book I, chapter 1, sections 3–11.

Vol. I covers Discourses Books I–II only (confirmed: 58 `BOOK II` recto
headers found; no Enchiridion text present — the ~9 hits for "Encheiridion"
in vol. I are all forward-references in the introduction/footnotes, not
the text itself). Vol. II covers Discourses Books III–IV, then — in this
scan's actual page order — the **Fragments** (regular fragments, then a
separately-labeled **"DOUBTFUL AND SPURIOUS FRAGMENTS"** subsection), then
**"THE ENCHEIRIDION, OR MANUAL"** last. The doubtful/spurious fragments
subsection is a clearly-marked block or extraction should treat it as
excludable/flaggable, mirroring the brief's question about content to
possibly exclude — regular vs. doubtful-and-spurious fragments are
typographically distinct (the latter under its own all-caps subheading).

**OCR quality assessment.** Spot-checked Discourses 1.1 (English opening:
"...the only faculty... which examines itself... and examines all other
faculties...") and Enchiridion ch. 1–2 openings in vol. II — both clean,
legible, modern-English OCR with no gross garbling on the English pages.
Heuristic line counts: vol. I — 27,113 total lines, 8,743 blank, 6,512
Greek-character-containing, ~7,495 English-stopword lines; vol. II —
31,620 total, 9,398 blank, 7,764 Greek-containing, ~8,282 English-stopword
lines. As with Haines, roughly a third to two-fifths of each raw file by
line count is Greek-facing-page content that stage-1 cleanup will need to
strip — but here the Greek is real Unicode (filterable by script-detection)
rather than garbled Latin-alphabet noise, which should make the strip
*more* reliable than for Haines. No missing-book or catastrophic-truncation
anomalies found in either volume.

---

### SECONDARY — George Long, *The Discourses of Epictetus; Encheiridion
and Fragments* (Bohn's Classical Library; this scan: George Bell and Sons
reprint)

| | |
|---|---|
| Translator | George Long (1800–1879) |
| Publisher | London: George Bell and Sons, York Street, Covent Garden |
| Publication year | 1890 (per archive.org catalog metadata; the scanned title page's own date line is OCR-garbled to "1800", clearly a misread of "1890" — see below) |
| US-PD rationale | Published 1890 (a Bell reprint of Long's original 1877 Bohn translation) — far pre-1931, safely US public domain regardless of which reprint year is correct |
| Source | archive.org, identifier `discoursesofepic033057mbp` |
| Source URL | https://archive.org/details/discoursesofepic033057mbp |
| Contributor/scan | Osmania University Library / Digital Library of India (Universal Library collection), scanned via IIIT Hyderabad |
| Retrieved | 2026-07-16, via `<identifier>_djvu.txt` OCR-text derivative |
| File | `long-epictetus/raw/discoursesofepic033057mbp_djvu.txt` (raw OCR text, pristine) |
| SHA-256 | `b27590ceae2f4699e03ceb68aff6422cdf54ee603012c7f7f9f5203d16d4203b` |
| Size | 1,349,721 bytes |

**Publication-year evidence.** The scanned title page reads: "THE
DISCOURSES OF EPICTETUS; ENCHEIRIDION AND FRAGMENTS. TRANSLATED, WITH
NOTES, A LIFE OF EPICTETUS, AND A VIEW OF HIS PHILOSOPHY, BY GEORGE LONG. ...
LONDON: GEORGE BELL AND SONS, YORK STREET, COVENT GARDEN. [date]." The
OCR renders the date digits as "1800" — impossible on its face, since Long
was born in 1800 and did not publish this translation as an infant. This
is a digit-OCR misread (9→0 is a common old-typeface confusion), and
archive.org's own catalog metadata independently gives **1890** for the
same publisher/imprint/identifier, which is adopted here. A publisher's
catalog-insert print code at the very end of the scan ("50,000. S. & S.
11.04") is consistent with a late-19th/early-20th-century Bell printing,
corroborating a pre-1931 (indeed pre-1905) date regardless of the exact
reprint year.

**Translator verification.** The dedication page — "TO ESTHER LAWRENCE, A
DILIGENT READER OF EPICTETUS, TO WHOM THE TRANSLATOR OWES MANY USEFUL
REMARKS" — is Long's own known dedication from his original translation,
confirming this is genuinely Long's text and not a mislabeled/ghost-written
edition (the same class of check that caught the PG #2680/Casaubon
mislabeling for Meditations). Spot-checked Discourses 1.1 opening ("OF ALL
THE FACULTIES... you will find not one which is capable of contemplating
itself...") and Book II opening — phrasing matches Long's known plain,
unarchaic prose style (distinct from e.g. Elizabeth Carter's earlier,
more archaic 18th-century translation, which Long's own preface discusses
and distinguishes itself from).

**Rejected alternative — Project Gutenberg #10661.** PG #10661, "A
Selection from the Discourses of Epictetus with the Encheiridion,"
carries an explicit `Translator: Long, George` field and is genuinely
Long's own wording — but its own title page states it is a **selection**,
not the complete Discourses ("A SELECTION FROM THE DISCOURSES OF EPICTETUS
WITH THE ENCHEIRIDION"), and the front matter does not enumerate which
chapters are omitted. Per the brief's preference for a full Discourses +
Enchiridion text, PG #10661 was rejected in favor of the complete
archive.org scan; no genuine *complete* Long translation was found on
Project Gutenberg (PG's Long-attributed Meditations sibling editions
#6920/#15877 are Marcus Aurelius, not Epictetus, and are irrelevant here).

**Structure / section marking.** Single-language (English-only) edition —
no facing Greek, so no page-side discrimination is needed at all (simpler
than both Oldfather and Haines). Each of the 4 books opens with a bare
`BOOK  I.` / `BOOK  II.` / `BOOK  III.` / `BOOK  IV.` header (double-spaced
OCR artifact of the printer's letter-spacing), confirmed present for all
four (body-text occurrences at lines 1768, 6404, 11144, 15972). Within
each book, sections are marked `CHAPTER  I.` / `CHAPTER  II.` etc. (spelled
out, Roman numeral, own line) followed by an all-caps chapter title on the
next line(s), then the chapter prose — a heavier-weight marker than the
bare inline `<n>.` used by both Meditations translations, closer to a
2-line "CHAPTER <ROMAN>. / <TITLE>" block. The table of contents (lines
~76–370) gives full CHAP./PAGE listings for all four books, useful as a
cross-check for chapter-count completeness. The Encheiridion (labeled "THE
ENCHEIRIDION OR MANUAL" in the TOC, p. 379) and Fragments (TOC p. 405,
body header "FRAGMENTS OF EPICTETUS" ~line 21286) both follow Book IV, in
that order — same relative order as Oldfather vol. II (fragments-then-
manual vs. Oldfather's fragments-then-manual — actually the reverse of the
vol. II *title-page* wording "THE MANUAL, AND FRAGMENTS", so downstream
extraction should not assume title-page order matches body order for
either translation).

**OCR quality.** This is an OCR scan of an older (1890s) physical
volume via the Digital Library of India / Universal Library project, not
a proofread transcription (unlike PG #15877 for Meditations) — quality is
noticeably rougher than the Meditations secondary source: common defects
spot-checked include letter-substitution noise within otherwise-legible
words (e.g. "THB" for "THE", "IL" for "II", "chouse" for "choose",
"CHAPTEK" for "CHAPTER") and heavy double-spacing between words
throughout, both typical of this scan batch. No missing books or gross
truncation found — heuristic line count: 28,814 total lines, 5,799 blank;
Book I–IV headers, full TOC, Encheiridion section, and Fragments section
(including the "FRAGMENTS OF EPICTETUS" header and an editorial note citing
Schweighaeuser's edition) are all present. The scan also carries
Osmania University Library ownership-stamp OCR noise at the very start
(call-number/accession-number boilerplate) and several hundred lines of
George Bell and Sons' own back-of-book advertising catalog (other Bohn's
Library titles, a Webster's Dictionary ad) after the Epictetus text proper
ends — both out of scope for extraction, analogous to Gutenberg's
license boilerplate around the Long Meditations text.

## Epictetus summary

| Work | Translator | Year | id | Book marker | Section marker | OCR quality |
|---|---|---|---|---|---|---|
| Discourses/Enchiridion vol. I (primary) | W. A. Oldfather (Loeb) | 1925 | `epictetusdiscour01epicuoft` | English-page header `BOOK <ROMAN>. <chap>. <sec-range>`; Greek-page header in Greek script | `<chap>.<sec>` inline, Loeb convention | English-page prose clean; real Greek Unicode on facing pages (unlike Haines) — needs a script-based Greek-page-stripping pass |
| Discourses/Enchiridion vol. II (primary) | W. A. Oldfather (Loeb) | 1928 | `in.ernet.dli.2015.185339` | same as vol. I | same as vol. I; Fragments has a marked "DOUBTFUL AND SPURIOUS" subsection | Same as vol. I |
| Discourses/Enchiridion (secondary) | George Long | 1890 (Bell reprint of 1877 translation) | `discoursesofepic033057mbp` | bare `BOOK <ROMAN>.` on its own line | `CHAPTER <ROMAN>.` + title block | Rougher OCR than PG-sourced Long Meditations text — letter-substitution noise, double-spacing, but complete and legible; no facing Greek so no page-side stripping needed |

### Stage-1 extraction (Wave 1a-D): Wikisource, not the archive.org OCR

Per the same methodology the sibling `extract_haines_wikisource.py` piloted
for Meditations, both Epictetus translations are ingested from **Wikisource's
human-proofread transcriptions** (ProofreadPage quality 3/4 — "Proofread"/
"Validated"), not by OCR-extracting the archive.org scans above. The
archive.org scans remain in place, untouched, as verification witnesses only
(`sources/{oldfather,long}-epictetus/raw/`); nothing downstream reads them.

| | Oldfather (primary) | Long (secondary) |
|---|---|---|
| Wikisource page | [Epictetus, the Discourses as reported by Arrian, the Manual, and Fragments](https://en.wikisource.org/wiki/Epictetus,_the_Discourses_as_reported_by_Arrian,_the_Manual,_and_Fragments) | [The Discourses of Epictetus; with the Encheiridion and Fragments](https://en.wikisource.org/wiki/The_Discourses_of_Epictetus;_with_the_Encheiridion_and_Fragments) |
| Structure | Discourses: one subpage per chapter, `.../Book N/Chapter M` (95 subpages, chapters 30/26/26/13 — matches the Greek spine exactly). Manual: single subpage `.../Manual`, all 53 chapters run together, delimited by `<span class="wst-anchor" id="N">`. | Same shape: Discourses `.../Book N/Chapter M` (95 subpages, 30/26/26/13). Encheiridion: single subpage `.../The Encheiridion or Manual`, chapters delimited by a `font-size:120%` roman-numeral heading div. |
| Fetch mechanics | MediaWiki API, `action=parse&oldid=<pinned revid>&prop=text` per subpage (a subpage's own wikitext is just an unresolved ProofreadPage `<pages index=.../>` transclusion tag — `prop=text` returns the already-assembled render). Every revid pinned 2026-07-16; embedded literally in the scraper as `_DISCOURSES_REVISIONS`/`_MANUAL_REVISION`, so a re-run reproduces byte-identical HTML unless Wikisource is deliberately re-pointed here. | Same mechanics, same pin date. |
| Scraper | `pipeline/tools/extract_oldfather_wikisource.py` (SHA-256 `c1119da7fa0e5b03b25f453c8f726a9f65600a0fdd36aa43bd4e22d7f8178c2b`, refreshed after the d4911c3 Schenkl-paragraphing wave modified the scraper without an inventory update — drift caught by verify-inventory-hashes) | `pipeline/tools/extract_long_epictetus_wikisource.py` (SHA-256 `119935875fd573faeac90290af5fb1f92f20aa258938499b06dca180f458721f`) |
| Output: Discourses | `oldfather-epictetus/oldfather-discourses.clean.json` — 95/95 chapters — SHA-256 `8a840ebd35d37fdadf4b1cf858da37dd292729ad8a46717204de29fd339120da` (refreshed with the scraper, same d4911c3 drift) | `long-epictetus/long-discourses.clean.json` — 95/95 chapters — SHA-256 `80e894561f0b3e80751764d60301c6f7ab08ea93e6e98d6476c2cb48e538e5cf` |
| Output: Enchiridion | `oldfather-epictetus/oldfather-enchiridion.clean.json` — 53/53 chapters — SHA-256 `c7e26cd5d6f3ff6288baae5b796ec38ded0db0d7c4243ea714afe7ea13ca0265` | `long-epictetus/long-enchiridion.clean.json` — 53/53 chapters after the deterministic split repair (see resolved anomaly below) — SHA-256 `dc2de19707c9030b9d80a72a8317a52c3c73784c7c737e8f4ed88be260363884` |

Extraction mechanics common to both scrapers: the proofread body lives inside
`<div class="prp-pages-output">` (the Manual page has TWO such divs — front
matter/AuxTOC, then the chapters proper — both must be concatenated, or all
53 chapters are silently dropped); footnote-ref superscripts
(`<sup class="reference">`), scan-boundary page markers
(`<span class="pagenum...">`), and inline TemplateStyles CSS
(`<style>`/`<link>`) are dropped before any text is read; a Discourses
chapter's own redundant "BOOK <ROMAN>"/"CHAPTER <ROMAN>" heading is stripped
from the leading edge (Oldfather's italic chapter subtitle and Long's
smallcaps one are KEPT as the chapter text's opening clause — genuine
translated content, not apparatus). Fragments are never fetched (a separate
Wikisource subpage), satisfying the brief's exclusion with no filtering
needed. Full extraction-logic rationale is in each script's module docstring.

One translation-specific trap, caught by the length-ratio screen below and
fixed 2026-07-16: the **Long** pages render the translator-footnote list
itself (`<div class="reflist"><ol class="references">`, with its "↑"
backlinks) INSIDE the `prp-pages-output` body div — unlike the Oldfather
pages, which render it outside, under the separate "==Footnotes==" heading —
so before the reflist was added to both scrapers' drop-list, 92/95 Long
Discourses chapters and Long Enchiridion 53 carried their footnotes' full
text appended to the chapter tail. The fix was verified surgically: every
repaired Long chapter is a strict prefix of its contaminated predecessor and
every removed tail begins with a footnote backlink ("↑"), so only footnote
text was removed; both Oldfather outputs are byte-identical with and without
the (defensive, there) rule.

**Chapter-count reconciliation.** Discourses: both translations 95/95 against
the Greek spine's 30/26/26/13 — exact match, no gaps. Enchiridion: Oldfather
53/53 exact; Long 53/53 after the deterministic split repair of his printed
edition's 52-section numbering (see the resolved anomaly below).

**Oldfather-vs-Long length-ratio correlation** (final, after the
footnote-strip fix and the §50/51 split repair below — this screen is what
CAUGHT the footnote contamination: the pre-fix run's numbers, Discourses
r = 0.989 / mean ratio 1.25 "Long more verbose", were an artifact of Long's
appended footnote text, and the Enchiridion's pre-split r = 0.600 was the
merge anomaly).

- Discourses: **r = 0.999** (n=95), mean ratio (Long/Oldfather) 0.944. Top-5
  robust-z outliers (3.11, 3.25, 1.14, 2.21, 3.7 — all |z| ≤ 2.6, ratios
  0.85–1.03) hand-checked: matching chapter titles and opening sentences in
  both translations, ordinary translator-length variance on mid-length
  chapters. **Verdict: clean.**
- Enchiridion: **r = 0.999** (n=53), mean ratio 0.993. Top-5 outliers (28,
  3, 10, 50, 40 — all short chapters where small absolute differences
  inflate the ratio, max |z| 3.3 on §28 at 230-vs-289 chars) hand-checked:
  same content both sides. **Verdict: clean.**

**Spot-collation vs. archive.org OCR witnesses.** Oldfather 1.1, 2.8, 4.1,
Enchiridion 1 and 53 vs. `raw/epictetusdiscour01epicuoft_djvu.txt`
/`raw/in.ernet.dli.2015.185339_djvu.txt`; Long 2.8, 4.1, Enchiridion 1 and
53 vs. `raw/discoursesofepic033057mbp_djvu.txt`. All located and matched
verbatim (mod. OCR noise) against the Wikisource extraction — same
translation, no abridgment. (Long 2.8 required disambiguating against three
same-numbered "CHAPTER VIII" headings elsewhere in the scan — Book II's own
is the second occurrence, confirmed by content: "WHAT IS THE NATUEE ... OF
THE GOOD ... GOD is beneficial." Long Enchiridion 53 appears in the scan
under his printed "LII." heading — OCR'd "LIT." — "In every thing
(circumstance) we should hold these maxims ready to hand : Lead me, 0 Zeus,
and thou 0 Destiny...", with the Cleanthes-attribution footnote correctly
absent from the clean JSON.)

**Garble screens** (comma-glued `,!`/`,?` footnote marks; leftover HTML
tags/entities; internal-cap OCR-shouting artifacts; stray null bytes; double
spaces; footnote-backlink "↑" residue) — **zero hits across all four files,
all screens**, re-run after the footnote-strip fix. The character-level
screens alone had NOT caught the footnote contamination (translator notes
are clean English prose) — the length-ratio screen above is what did; the
"↑" screen was added afterward as a direct detector for that defect class.

**Coverage anomaly — Long's printed Encheiridion has only 52 sections, not
53 (RESOLVED — John's ruling, 2026-07-16: re-key to modern numbering; split,
don't gap).** Long's own printed edition merges what the modern/Schenkl
numbering (and Oldfather) count as separate §§50–51 into a single section
under his heading "L." (confirmed: Oldfather's §50 + §51 concatenated =
1,721 chars, matching Long's merged section at 1,686 chars within normal
translation-length variance). Because this merge happens mid-sequence rather
than at the end, it **cascades**: Long's printed §51 = modern §52 ("The
first and most necessary [division/place] in philosophy..."), and Long's
printed §52 = modern §53 (the Cleanthes/"Lead thou me on, O Zeus" verse +
the Crito quotation) — confirmed by direct content comparison. This is a
genuine 19th-century edition-numbering variant (the same class of fact as
the already-documented Meditations 5.37 Haines/Long merge), **not** a
scraper defect — the garble screens are clean and the merge point's
arithmetic checks out exactly.

**Resolution.** Per John's ruling, `long-enchiridion.clean.json` is keyed to
the **modern 1–53 numbering** the Greek spine and Oldfather use, so the
1:1 translation-to-column assumption of `stage1_book_section_english.py`
holds with no gaps. The repair is a deterministic, fail-loud rule in the
extractor itself (`_renumber_manual` in
`extract_long_epictetus_wikisource.py`), not a silent text edit: Long's
merged printed section 50 is split into modern 50 + 51 at the exact sentence
opening his rendering of modern §51 — `"How long will you then still defer
thinking yourself worthy"` (Long's own verbatim sentence, required to match
exactly once, cf. Oldfather's modern §51 opening "How long will you still
wait to think yourself worthy of the best things") — then his printed 51→52
and 52→53. The rule raises (rather than improvising) if the input does not
have exactly Long's 52 printed sections or the split marker does not match
exactly once. Verified after the re-run: keys are exactly 1–53; keys 1–49
byte-identical to the pre-split extraction; modern 50 + 51 exactly partition
Long's old merged text (concatenation equality across the boundary space, no
loss); modern 52 byte-identical to his printed 51; modern 53 identical to
his printed 52 except for the removal of its appended translator-footnote
text (the separate contamination fix above — strict-prefix verified, the
removed tail opens with the "↑" footnote backlink); and the split halves
match Oldfather's modern §§50–51 subject-for-subject (Long 50: "Whatever
things (rules) are proposed to you [for the conduct of life] abide by them,
as if they were laws..." ~ Oldfather 50: "Whatever principles are set before
you, stand fast by these like laws..."; Long 51: "How long will you then
still defer thinking yourself worthy of the best things..." ~ Oldfather 51:
"How long will you still wait to think yourself worthy of the best
things..."). No such issue exists for Long's Discourses (95/95, no merge) or
either Oldfather output (53/53 and 95/95, no merge).

## Diogenes Laertius, *Lives of Eminent Philosophers* (10 books, citation
scheme `book-section` per `CANON.md`, e.g. `7.85`)

**Scrape-first check result: neither translation should be sourced from
Wikisource, for opposite reasons** — see each subsection. This work is
large (see "Corpus size" at the end) — a search-shard sizing concern per
`CANON.md`'s own note on this row.

### PRIMARY — Robert Drew Hicks, *Diogenes Laertius: Lives of Eminent
Philosophers* (Loeb Classical Library, vol. I–II, 1925) — sourced from the
**Perseus Digital Library**, not Wikisource

| | |
|---|---|
| Translator | Robert Drew Hicks (1850–1929) |
| Publisher | Cambridge, MA: Harvard University Press; London: William Heinemann Ltd; New York: G. P. Putnam's Sons |
| Publication year | 1925 (both volumes) |
| US-PD rationale | Published 1925, pre-1931 — safely US public domain |
| Source | Perseus Digital Library / PerseusDL `canonical-greekLit` GitHub repo, file `data/tlg0004/tlg001/tlg0004.tlg001.perseus-eng2.xml` |
| Source URL | https://raw.githubusercontent.com/PerseusDL/canonical-greekLit/master/data/tlg0004/tlg001/tlg0004.tlg001.perseus-eng2.xml (also browsable via https://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.01.0258 and catalogued at https://catalog.perseus.org/catalog/urn:cts:greekLit:tlg0004.tlg001.opp-eng1) |
| CTS URN | `urn:cts:greekLit:tlg0004.tlg001.perseus-eng2` |
| Pinned commit (last touching this file, as of retrieval) | `299a8af276c31f407e7f0f75dde516bdd4376d7a` (2026-05-04, "schema_cleanup" — a whitespace/schema fix, not a content edit) |
| Retrieved | 2026-07-16, via GitHub raw at the pinned commit |
| SHA-256 (raw XML as retrieved) | `f53a4d376bb8bcc02547ecc46f9865855ed434ccc1b991baeb1254ce0d6086a3` |
| Size | 1,355,995 bytes (5,493 lines); ~176,500 words / ~1,022,000 characters of text content once tags are stripped |
| Markup license | Perseus's own TEI/EpiDoc encoding is CC BY-SA 4.0 (per the file's own `<availability>` block) — this covers Perseus's XML markup and editorial apparatus, not the underlying 1925 Hicks translation itself, which is independently US-PD by publication date |

**Why Perseus, not Wikisource.** `en.wikisource.org/wiki/Lives_of_the_Eminent_Philosophers`
(the candidate the brief specifically flagged for verification) is genuinely
the Hicks translation, all 10 books present — but its own `{{header}}`
template carries an explicit **`{{no scan}}`** flag (confirmed via
`action=raw` on the live wikitext), meaning it is **not** backed by
Wikisource's ProofreadPage scan-and-proofread workflow the way the Haines
*Meditations* and Oldfather *Discourses* Wikisource sources were — it is a
free-form wikitext page, not a set of proofread `Page:` transclusions
against page images. Page-history inspection (`action=query&prop=revisions`)
confirms it: the entire page and each Book subpage were created in a
**single edit** on 2010-07-10 by user `Singinglemon~enwikisource` via
"Created page with '...'" — i.e. bulk-pasted, not built up page-by-page from
a scan. Textual comparison confirms the source of that paste: Wikisource's
Book I §1 text is word-for-word identical to Perseus's `perseus-eng2.xml`
§1.prol.1 (down to paragraph breaks), and each Wikisource Book page cites
`archive.org/details/livesofeminentph01diog` as its "source" note rather
than a Wikisource-hosted scan. Perseus is therefore the actual primary
digitization; Wikisource is a downstream, unproofread copy of it with
Wikisource-flavor markup added. Using Perseus directly is both more
faithful (one fewer copy-and-reformat generation removed from the print)
and structurally superior for a future scraper (see below).

**Edition/translator verification (front matter, not just catalog
labels).** Perseus's own TEI header, independent of the catalog page,
records `<editor>R. D. Hicks</editor>` and a `sourceDesc/biblStruct` citing
"Cambridge, MA: Harvard University Press; London: William Heinemann Ltd.,
1925," with a direct `<ref>` to `archive.org/details/livesofeminentph01diog`
as its print source. Cross-checked against that archive.org scan's own
`_djvu.txt` directly: the title page reads "IN TWO VOLUMES / I / LONDON:
WILLIAM HEINEMANN / NEW YORK: G. P. PUTNAM'S SONS / MCMXXV" (1925), and
Hicks's preface is signed "ROBERT DREW HICKS." archive.org catalog metadata
for both volumes (`livesofeminentph01diog`, `livesofeminentph02dioguoft`)
independently confirms `date: 1925`, `creator` including "Hicks, Robert
Drew, 1850-1929," `publisher: London : Heinemann`.

**Completeness.** All 10 books present (confirmed by direct XML structure
inspection, not just a book-heading grep): `<div type="textpart"
subtype="book" n="1">` through `n="10"`, 1,211 `section`-level divs total,
83 `chapter`-level divs (each "chapter" = one philosopher's Life; Books III
and X, each devoted to a single philosopher — Plato and Epicurus
respectively — are structurally a single chapter with many numbered
sections rather than many chapters). **Book X (Epicurus) spot-checked
directly per the brief's instruction**: contains all three verbatim
letters in full ("Epicurus to Herodotus, greeting" at file line 145,
"Epicurus to Pythocles, greeting" at line 258, "Epicurus to Menoeceus,
greeting" at line 332 of the extracted plain text) and ends correctly at
*Kuriai Doxai* (Principal Doctrines) §40, matching the known structure of
the Loeb Book X. Per-book chapter/section counts: Bk I 12 ch./122 sec., II
17/147, III 1/109 (Plato), IV 10/67, V 6/94, VI 9/105, VII 7/204 (Stoics —
largest section count, mostly Zeno/Chrysippus doxography), VIII 8/93, IX
12/116, X 1/154 (Epicurus).

**Quality assessment.** Not a scan-backed proofread transcription in the
Wikisource/PGDP sense — Perseus's own `editorialDecl` records
`<correction status="low"><p>Data Entry</p></correction>` (standard Perseus
collection-wide boilerplate, "correction status low" describing the general
policy applied across many Perseus 19th/early-20th-c. translation
digitizations, not a per-text audit). Screened for corruption directly:
zero hits for lacuna/corrupt/illegible/`[sic]` markers outside Hicks's own
genuine scholarly apparatus (his footnotes legitimately discuss manuscript
lacunae — e.g. "Hence I have marked a lacuna" — this is editorial content,
not a transcription defect); a non-ASCII-character sweep found only
expected diacritics (French/German scholar names in footnotes — 2
`xml:lang="fre"` tags — and embedded Greek) with no mojibake pattern. Spot
read of Book I §1 and Book X's three Epicurus letters is fluent, idiomatic
Hicks prose with no garbling. **Verdict: usable as-is; no independent
witness-scan cross-check was performed against every chapter** (unlike the
byte-level Haines/Oldfather Wikisource-vs-OCR diff campaigns) — if the
orchestrator wants that level of assurance before ingestion, a future pass
could diff a sample of chapters against the `livesofeminentph01diog`/
`livesofeminentph02dioguoft` archive.org OCR scans, which remain on
archive.org and were not downloaded here (no raw download was needed since
a faithful transcription-source was found, per the brief's playbook).

**Structure / URL scheme for a future revision-pinned scraper.** Perseus's
TEI XML uses CTS-standard nested `<div type="textpart">` elements:
`subtype="book"` (`n="1"`–`"10"`), `subtype="chapter"` (`n` = a philosopher
slug or ordinal, irregular — read from the `<head>` sibling for the name),
`subtype="section"` (`n` = the Bekker-style section number, exactly the
`book-section` scheme `CANON.md` specifies, e.g. `n="1"` under book 1 =
citation `1.1`). Each section is one or more `<p>` elements; verse epigrams
(322 occurrences corpus-wide — see the anomaly note below) are marked
`<quote rend="blockquote">` with `<l/>` line breaks, distinctly tagged from
prose `<p>`, which a scraper can use to preserve or flag them. Footnotes are
`<note resp="editor">` inline. A scraper should pin to the specific GitHub
commit SHA recorded above (not `master` HEAD) for reproducibility, the same
discipline the Wikisource `oldid`-pinning scrapers use for the sibling
works.

---

### SECONDARY — Charles Duke Yonge, *The Lives and Opinions of Eminent
Philosophers* (Bohn's Classical Library, 1st ed. 1853; this source: G. Bell
and Sons' 1915 reprint, "from stereotype plates" — same unrevised text)

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891) |
| Publisher (1915 printing used) | London: G. Bell and Sons, Ltd. |
| Publication year | 1853 (first edition, translation itself); this text is the 1915 Bell reprint, printed "from stereotype plates" — i.e. unrevised, identical text to 1853, per its own title page |
| US-PD rationale | 1853 (or even the 1915 reprint) — far pre-1931, safely US public domain regardless of which date governs |
| Source | Project Gutenberg eBook **#57342**, "The Lives and Opinions of Eminent Philosophers" |
| Source URL | https://www.gutenberg.org/ebooks/57342 (text: https://www.gutenberg.org/cache/epub/57342/pg57342.txt) |
| Credits | Ted Garvin and the Online Distributed Proofreading Team (pgdp.net) — a scan-backed, page-by-page proofread transcription, per its own "Transcriber's Note" appendix, which lists dozens of specific OCR-correction entries keyed to print page numbers (e.g. "Page 204, 'Innesigenes' changed to 'Mnesigenes'") |
| Retrieved | 2026-07-16 |
| Release date / last updated | Released 2018-06-16, most recently updated 2023-10-04 (per PG's own metadata — later corrections are possible; the SHA-256 below pins the exact 2026-07-16 snapshot) |
| SHA-256 (raw .txt as retrieved) | `0176dd702dfcc4a11d355475cab857f2a521a72dc316ecd8921ef12a0495c5a1` |
| Size | 1,154,825 bytes (20,828 lines); body (between PG's START/END markers, including front matter, index, and Transcriber's Note) ~193,000 words / ~1,101,000 characters |
| Standard Ebooks alternative | Same translation, same PG #57342 source, re-issued as clean semantic XHTML/EPUB by Standard Ebooks (CC0 markup) at https://standardebooks.org/ebooks/diogenes-laertius/the-lives-and-opinions-of-eminent-philosophers/c-d-yonge — 179,129 words. Worth considering as the scrape target instead of raw PG text, since Standard Ebooks ships clean per-file XHTML rather than one monolithic `.txt` with inline `[N]` footnote markers and a run-on Transcriber's Note to strip. |

**Wikisource checked and rejected — not usable, no faithful transcription
exists there.** A Wikisource entry for this exact translation/printing
does exist — `Index:The lives and opinions of eminent philosophers -
Laërtius, tr. Yonge - 1915.djvu` (a genuine scan-backed Index page, scan
uploaded, `Translator=Charles Duke Yonge`, `Year=1915`, `Publisher=G. Bell`)
— but the transcription itself has barely begun: only **18 of 504** `Page:`
namespace entries exist for the scan (confirmed via
`generator=allpages&gapnamespace=104`), and the work's own content page,
`The Lives and Opinions of Eminent Philosophers (Yonge)`, **does not exist**
(`action=query` returns `"missing":""`) — the link to it from the
disambiguation page `Lives and Opinions of Eminent Philosophers` is a
redlink. This is the mirror-image problem to the Hicks page: here Wikisource
has genuine scan backing but essentially no completed proofreading (~3.5%
of pages even touched), so per the brief's playbook ("only if no faithful
transcription exists, fall back") the fallback is warranted — except a
better fallback than raw archive.org OCR was found: PG #57342 is *already*
a complete, scan-backed, PGDP-proofread transcription of this identical
1915 printing, so no OCR download/extraction was needed at all.

**Edition/translator verification (front matter).** The downloaded PG text
itself begins with the scanned title page transcribed verbatim: "THE LIVES
AND OPINIONS OF EMINENT PHILOSOPHERS / BY / DIOGENES LAËRTIUS. / LITERALLY
TRANSLATED / BY C. D. YONGE, M.A., / ... / LONDON / G. BELL AND SONS, LTD /
1915 / [Reprinted from Stereotype plates.]" — publisher line matches the
Wikisource Index page's independently-recorded `Publisher=G. Bell` /
`Year=1915` for the same scan, cross-confirming both sources describe the
identical printing.

**Completeness.** All 10 books present (`BOOK I.` through `BOOK X.`
confirmed at file lines 248, 2211, 4323, 5875, 6985, 8330, 9856, 12792,
14194, 16037). **Book X spot-checked**: contains "LIFE OF EPICURUS,"
Roman-numeral-numbered sections through "XL" (matching Hicks's 40-section
end point), and all three letters present verbatim ("EPICURUS TO
HERODOTUS, WISHING HE MAY DO WELL" line 16528, "...TO PYTHOCLES..." line
17215, "...TO MENŒCEUS, GREETING" line 17738). The edition also includes a
full back-of-book alphabetical Index (ending "ZOROASTER, his philosophy,
_note_, 5.") before the Bell/Clowes printer's colophon — i.e. this is a
complete reprint of the full 1853 apparatus, not an abridgment.

**Quality.** Genuine PGDP double-keyed/proofread transcription against
page scans (not raw OCR) — the "Transcriber's Note" section documents
specific, itemized OCR-misread corrections keyed to exact print page
numbers, the strongest completeness/fidelity signal available short of a
Wikisource "Validated" ProofreadPage rating. No further garble screening
was needed given this provenance.

**Structure / section marking.** Single-language (English-only), no facing
Greek. Each book opens with a bare `BOOK <ROMAN>.` header on its own line.
Within a book, each philosopher's Life opens with an ALL-CAPS name/subject
header (e.g. `INTRODUCTION.` for Book I's prologue, presumably
`THALES.`-style headers for each subsequent Life — not individually
enumerated here) followed by **Roman-numeral section markers** (`I.`,
`II.`, `III.`...) inline at the start of each section's first line — same
`book-section` addressability as Hicks, via the per-Life Roman-numeral
sequence.

### Stage-1 extraction (Diogenes Laertius): merge-by-duplicate-key, not an
offset map; Yonge falls back to Life-level keying

**Hicks** (`sources/hicks-dl/hicks-lives.clean.json`, sidecar
`hicks-verse.json`, outline `lives-names.json`) is built by
`pipeline/tools/extract_hicks_dl_perseus.py` (SHA-256
`d9ae5b770b477ebec4b9ec74752e9c877838706a753b6bbb48a4e72fd4cf7d40`), which
reads the pinned Perseus XML straight from
`sources/hicks-dl/tlg0004.tlg001.perseus-eng2.xml` (SHA-256
`f53a4d376bb8bcc02547ecc46f9865855ed434ccc1b991baeb1254ce0d6086a3`, verified
against the pinned-commit value in the PRIMARY section above before every
run) rather than re-fetching per run — same "download once, verify the
hash, read locally" shape as `extract_long.py`'s PG text, chosen over the
Wikisource scrapers' live-fetch pattern because there's no ProofreadPage
transclusion to reassemble here. The extractor applies one recorded
emendation (`_TEXT_CORRECTIONS`): "Anbaxagoras" → "Anaxagoras" at 9.35, an
OCR artifact Perseus's transcription shares (Wikisource and the 35 other
occurrences in the volume read "Anaxagoras"); the pinned XML stays
byte-faithful. **Yonge** (`sources/yonge-dl/yonge-lives.
clean.json`) is built by `pipeline/tools/extract_yonge_dl_gutenberg.py`
(SHA-256 `546688a7601e0bf7aa800092c02ecd39ba18029fef07d1e0c9360c8582f07924`)
from the pinned `sources/yonge-dl/pg57342.txt` (SHA-256
`0176dd702dfcc4a11d355475cab857f2a521a72dc316ecd8921ef12a0495c5a1`, matches
the PG snapshot pinned in the SECONDARY section above exactly). Outputs:
`hicks-lives.clean.json` 1,204 keys (SHA-256
`966668221158c280b61aeeb8542308976f28b9200a17bead6a7d7199f9ae9f92`),
`hicks-verse.json` 238 keys / 331 ranges (SHA-256
`805c7cc4958ec760e6c91f6517b4ba68f0c62d949ff3bbf380689f5f4e4a8af4`),
`lives-names.json` 83 chapters (SHA-256
`c3c280952d2ebf7c4cc78fd747750d4a2e3ff8e29c6680177f652ad8aea1f6ba`),
`yonge-lives.clean.json` 80 keys (SHA-256
`e402b5d7c2365d81adb3f5e0a1aa14485b0f7a95aa5fb82647731236305d8c3b`).

**The brief for this stage assumed Hicks would need a derived per-book
numeric offset map to reconcile his post-double sections onto the Greek
spine's merged columns. Direct inspection of the actual TEI shows this is
unnecessary** — Perseus already encodes the Greek's doubled/tripled Bekker
sections as multiple consecutive `<div subtype="section">` elements
carrying the IDENTICAL `n` value (not distinctly incremented numbers), so
the fix is simply: merge every run of same-`n` section divs within a book
into one key, concatenating their text in document order. This was
verified book-by-book against the Greek spine (H. S. Long's TLG/OCT text,
exported locally via `docs/tlg-phi-export.md` to
`build/export/Diogenes-Resources/xml/tlg/tlg0004001.xml` — not committed,
per the corpus-source-text rule) by comparing the exact SET of merged
section numbers per book, not just counts:

- **Books 1–9: exact match, element for element, zero offset needed.**
  Book 2's `n="124"` is a genuine oddity worth naming: it appears THREE
  times in Hicks/Perseus (Simon-the-physician coda, Glaucon, Simmias) even
  though the Greek's own `2.124` is a single, non-doubled section — Hicks/
  Perseus split one Greek section into three divs for editorial
  (paragraph-per-biographee) convenience. The uniform merge-by-n rule
  handles this identically to the genuine doubles and was content-verified
  against the Greek by proper-name correspondence (the two English names
  both fall within the Greek's single `2.124`). All five
  of the Greek's own doubled Bekker numbers were independently
  content-verified boundary-by-boundary: **2.125** (the two matching names),
  **7.160** (close of Zeno's chapter plus the next author's opening),
  **7.166** (close of Herillus plus the next author's opening),
  **8.83** (close of Archytas plus the next author's opening), **8.84**
  (the two matching names) — Hicks's merged English opens
  with the matching proper name in every case.
- **Book 10: 2 keys (`10.120`, `10.121`) with no Greek plain-numeric
  counterpart — recorded as allowances, not a defect.** The Greek spine
  marks a well-known manuscript leaf transposition in the Epicurus
  doxographical epitome with FOUR lettered sections in manuscript order
  (`120a`, `121b`, `120b`, `121a`) instead of plain `120`/`121`. Hicks's
  own numbering is plain and contiguous, already resolved into standard
  scholarly reading order — content-verified directly: Hicks `10.120`
  opens "He will leave written words behind him..." = Greek `120a`; Hicks
  `10.121` opens "Two sorts of happiness can be conceived..." = Greek
  `121a`, and both end at the Letter to Menoeceus's salutation, same as
  Greek `121a`. No fix needed in the extractor — Hicks's own section
  numbers are used as-is; this is purely a fact about the *Greek* spine's
  key set (1,202 plain-numeric columns; 120/121 are absent from that set,
  present only as the lettered fragments), flagged here for the manifest
  allowance list.

**Reconciliation ledger.** Hicks: 1,204 keys = 1,202 Greek-spine columns +
the 2 book-10 allowances above. Every Greek column has Hicks text; the only
Hicks keys without a Greek plain-numeric counterpart are the 2 allowances.
No other residuals in either direction.

**Verse sidecar.** `hicks-verse.json` covers 238 of the 1,204 keys, 331
ranges total (the brief's "~322" estimate was in the right range; the
extractor's exact rule is "`<quote>` whose `rend` contains `blockquote`",
matching 332 raw elements, one of which nests inside another and is folded
into the parent's range rather than double-counted). Anomaly for the
record: a handful (~10) of additional `<quote>` elements elsewhere in the
XML are ALSO verifiably verse by content and internal `<l/>` markers but
carry a different `rend` (`align(indent)`, empty, or `single`) — e.g. "In
summer-time a thick cloak he would wear..." (6.22) and the famous
Pythagoras/Euphorbus epigram (8.5) — deliberately left OUT of the sidecar
to keep the extractor's rule matching the interface exactly as specified
("`<quote rend="blockquote">`/`<l>` markup") rather than unilaterally
widening scope; flagged for the orchestrator if broader verse coverage is
wanted later. Every range's invariants (non-empty slice, breaks strictly
inside `(start, end)`) are asserted in `main()` against the actual emitted
text, not a separate recomputation — two real bugs were caught and fixed
this way during development (a degenerate leading `<l/>` at the very start
of an epigram producing `break == start`, filtered; and a `_Builder`
whitespace-collapse bug that let TWO separately-pending inter-element
spaces both materialize instead of collapsing to one, giving
"Captives:  A. Pray..." — fixed by projecting the verse range's `start`
through a still-pending space instead of eagerly committing it).

**Quote-mark rendering (new, not in the original brief, but load-bearing
for readability).** Perseus's TEI declares `<quotation marks="none"/>` and
the corpus sweep confirms it: zero literal quote-mark characters (straight
or curly) anywhere in the body text — ALL direct speech and quoted
doctrine is marked purely by `<q>`/plain `<quote>` tags (1,596 + 10 uses).
Left as-is, this would flatten to unpunctuated run-on prose ("the question
Who is a wiser man than I? before..."). The extractor wraps these in curly
quotes, alternating "…" / '…' by nesting depth (42 of 1,596 `<q>`s nest one
level). A second, narrower fix: two places in the raw XML carry a literal
stray `>` character immediately before a verse `<quote>` (a Perseus
data-entry leftover, not meaningful punctuation — e.g. "...the couplet of
Mimnermus:>\n\<quote>Would that..."); dropped by the extractor
(`_Builder.drop_trailing`), confirmed against the archive.org OCR scan
that the printed original has no such mark.

**Garble screens** (leftover tags, double spaces, unstripped whitespace,
space before `,;:` or a closing quote mark, empty values) — zero hits
across all 1,204 Hicks keys and all 80 Yonge keys after the fixes above.

**Spot-collation vs. archive.org OCR witnesses**
(`livesofeminentph01diog`/`livesofeminentph02dioguoft`, fetched directly
for this pass, not previously downloaded per the PRIMARY section's note
that no raw copy was needed for ingestion). Hicks 1.30 (the Myson/Chilon
oracle passage, including its verse couplet) and 3.62 (the
Horse-breeder/Eryxias title list, the stray-`>`-fix case) both match the
scan **verbatim**, modulo the scan's own OCR noise (e.g. the scan renders
"as follows?:" where both Perseus and the print actually read "as
follows:" — Perseus is, if anything, cleaner than raw OCR here, as
expected given INVENTORY's existing verdict that Perseus is the superior
source).

**Yonge: per-section keying measured and rejected; Life-level keying
verified instead.** The brief's first-choice approach — map Yonge's inline
Roman numerals (restarting at I per Life) onto continuous `book.section`
via cumulative summing against Hicks's chapter ranges — was attempted and
measured honestly rather than assumed to work:

- **Chapter-count reconciliation: exact.** 83 "LIFE OF X."/"THE LIFE OF
  X."/"INTRODUCTION." headers in Yonge, same count, same order, same names
  as Hicks's 83 `<head>` chapters (cross-checked by position AND by
  philosopher name).
- **Per-Life Roman-numeral COUNT vs. Hicks's per-chapter section COUNT:
  uncorrelated.** 78 of 83 chapters have a different count outright — not
  noisy, structurally different. Zeno: Hicks 159 sections vs. Yonge 86
  Roman numerals. Epicurus: Hicks 154 vs. Yonge 31. Thales: Hicks 23 vs.
  Yonge 16. Yonge's numbering is evidently the Bohn translator's own
  independent paragraph enumeration, unrelated to the Loeb/Bekker
  apparatus — a cumulative-sum mapping would drift out of alignment within
  the FIRST chapter of nearly every book and silently mis-key almost the
  entire work. **Verdict: per-section keying is not viable for Yonge, not
  "noisy but usable" — rejected on the evidence, not shipped.**
- **Per-Life LENGTH correlation (character count, Hicks chapter vs. Yonge
  Life): r = 0.9996 (n=80, excluding the 3 collision chapters below whose
  Hicks length is a boundary-attribution artifact — see next item),
  Yonge/Hicks mean ratio 1.11 (Yonge runs somewhat more verbose, expected
  for 1853 Bohn prose vs. the tighter 1925 Loeb).** This strongly supports
  the fallback actually shipped: Life-level keying is highly reliable even
  though sub-chapter section boundaries are not. Outliers beyond the
  merge-boundary cluster are mild and explicable: Archytas (8.79, ratio
  1.38, Hicks compresses a long technical passage more tightly), Pythagoras
  (8.1, ratio 1.21, by far the largest chapter, ordinary translator-length
  variance at scale). **Verdict: ship Life-level keying** (this is the
  decision item for the orchestrator to confirm, per the brief).
- **Fallback shipped:** one chunk per philosopher, keyed
  `"<book>.<start_section>"` using the SAME `start_section` Hicks's chapter
  uses — so Yonge stays addressable and alignable at the work's natural
  navigation unit (which philosopher) even though it can't offer
  Hicks/Greek section granularity within a Life. Three of Hicks's 83
  chapter-start keys are shared by two consecutive philosophers as a direct
  consequence of the merge-by-duplicate-section-number rule above (`2.124`:
  Glaucon/Simmias; `2.125`: Cebes/Menedemus; `8.84`: Hippasus/Philolaus,
  each pair's second Life opening inside the same merged Hicks/Greek
  column as the first Life's close) — the extractor concatenates rather
  than silently overwriting, logged at run time.
- Footnote handling: Yonge's footnotes are NOT interleaved per-book (unlike
  Long's Meditations, which needed content-based footnote-vs-verse
  disambiguation) — they're one collected "FOOTNOTES" section after Book X,
  so the extractor just slices the body off before that heading and strips
  the inline `[N]` reference markers; no verse/footnote ambiguity exists to
  resolve.

## Diogenes Laertius summary

| Work | Translator | Year | Source | Fidelity class | Book marker | Section marker |
|---|---|---|---|---|---|---|
| (primary) | R. D. Hicks (Loeb) | 1925 | Perseus `canonical-greekLit`, `tlg0004.tlg001.perseus-eng2.xml`, pinned commit `299a8af2` | Born-digital data entry, Perseus's own long-standing digitization (not Wikisource — see rejection above); spot-collated against the archive.org OCR scan (2 passages, verbatim match) as part of stage-1 extraction below | TEI `<div subtype="book" n="1..10">` | TEI `<div subtype="section" n="N">`, CTS URN per section |
| (secondary) | C. D. Yonge (Bohn, this printing 1915) | 1853 (text)/1915 (this printing) | Project Gutenberg #57342 (PGDP scan-backed proofread) | Scan-backed, page-by-page proofread (PGDP) — the strongest fidelity class found for this work | `BOOK <ROMAN>.` on own line | Roman numeral inline per Life (see stage-1 extraction below: not usable for per-section keying — Life-level keying shipped instead) |

**Corpus size** (flagging for the roadmap's "watch search-shard sizes" note
on this row): Hicks clean-JSON text 157,717 words / 892,865 characters
(1,204 keys); Yonge clean-JSON text 178,587 words / 998,468 characters (80
Life-level keys) — both smaller than the raw-file word-count estimates in
each PRIMARY/SECONDARY section above, as expected once footnotes, front
matter, and (for Yonge) the back-of-book index are excluded from the
translated text proper. **The two translations together still run to
roughly 1.9 million characters of clean English text** — by a wide margin
the largest single work sourced in this repo to date (compare Meditations'
combined Haines+Long at a small fraction of this size), confirming the
roadmap's caution.

**Anomalies for orchestrator judgment:**

1. **Verse epigrams — RESOLVED, see stage-1 extraction above.** Hicks gets
   a verse-range sidecar (`hicks-verse.json`, 238 keys / 331 ranges) built
   from `<quote rend="blockquote">`/`<l/>` markup; Yonge's verse (marked
   only by indentation, no tagging) is flattened into prose like every
   other clean JSON in this repo, consistent with the brief's "verse
   flattened to prose inside the string" convention. A handful of
   additional Hicks `<quote>`s are verse by content but outside the
   sidecar's literal `rend`-matching rule — see the sidecar note above.
2. **Book X's verbatim Epicurus material** (three letters + *Kuriai Doxai*)
   is present in full in both translations, as required for completeness —
   but per `CANON.md`'s existing dedup ruling (Bailey's standalone
   *Epicurus: The Extant Remains* is the canonical text for these letters;
   DL Book X should cross-link rather than duplicate), this is a rendering/
   dedup decision already made at the canon level, not a new one raised
   here — flagging only so whoever builds the DL extraction pipeline
   doesn't re-litigate it.
3. **Perseus fidelity class is genuinely different from the Wikisource
   Proofread/Validated bar** this repo has used for Haines and Oldfather —
   it's a good, clean, complete, structurally superior source, but "low
   correction / data entry" is a real notch below "proofread against page
   images by multiple Wikisource contributors." Stage-1 extraction above
   added a small, 2-passage sampled spot-collation against the archive.org
   OCR scans (option (b) below) — both matched verbatim — which raises
   confidence somewhat but is not the full per-chapter diff campaign this
   item originally called for. If the project wants Wikisource-grade
   assurance specifically, that would still require either (a) the
   orchestrator or a future contributor completing the moribund 18/504
   Wikisource Yonge transcription and a from-scratch Hicks Wikisource
   scan-backed effort (large undertaking, not attempted here), or (b) a
   fuller sampled diff against the archive.org OCR witnesses, of which this
   pass's 2 spot-checks are a first, small, and clean-verdict installment.

## Herakleitos and Parmenides (Wave 1b presocratic pilot, DK scheme)

### PRIMARY (both authors) — John Burnet, *Early Greek Philosophy*, 3rd ed.
(1920), sourced via Wikisource

| | |
|---|---|
| Translator | John Burnet |
| Source | Wikisource, `Index:Early Greek philosophy by John Burnet, 3rd edition, 1920.djvu` (en.wikisource.org) — per-page proofread transcription in the `Page:` namespace, ProofreadPage quality 3 ("Proofread", one pass short of "Validated") on every one of the 67 pages fetched |
| Index URL | https://en.wikisource.org/wiki/Index:Early_Greek_philosophy_by_John_Burnet,_3rd_edition,_1920.djvu |
| Herakleitos coverage | Ch. III "Herakleitos of Ephesos", printed pp. 130–168 = djvu pages 144–182 (39 pages) |
| Parmenides coverage | Ch. IV "Parmenides of Elea", printed pp. 169–196 = djvu pages 183–210 (28 pages) |
| Page↔print offset | djvu page − 14 = printed page, confirmed both from the Index's own `Pages=` pagelist (`15=1`, `377=363`) and both chapter mainspace wrapper pages' `from=`/`to=` values matching the Contents page's (`Page:.../11`) printed-page ranges exactly |
| Fetched | 2026-07-17, via MediaWiki `action=parse&oldid=<revid>&prop=wikitext` (raw wikitext of a PINNED revision, not "latest") |
| Extraction tool | `pipeline/tools/extract_burnet_wikisource.py` |
| Files | `burnet-egp/burnet-heraclitus.clean.json` (113 DK columns; B5a/B5b and B31a/B31b merged under B5/B31 per the spine adjudication), `burnet-egp/burnet-parmenides.clean.json` (18 DK columns), `burnet-egp/burnet-parmenides-paras.json` (verse-line-marker sidecar, 6 columns) |
| SHA-256 (burnet-heraclitus.clean.json) | `2c03709c6a7c9ff4760c18c6b9cf84e4c53dcea7df03f13e14f8a0b0b294c7c6` (post-merge regeneration; the pre-merge extraction was `9f8d5e30…c06ff6a`) |
| SHA-256 (burnet-parmenides.clean.json) | `3c22c3280431a8d689abb3129a54334cc7eac3eb7d3f92f7c60cf848dad84da3` (regenerated 2026-07-17 after the B2-B5 old-Diels-numbering remap fix below) |
| SHA-256 (burnet-parmenides-paras.json) | `e857f1c81458f571b9e5462b77dd17119f2e2efdadd4094e76894c4b7a89f3e7` |
| SHA-256 (WIKISOURCE-PATCHES.json) | `0c937284414a387568bd6afb9c004303a99902b00cc3b3b4277a6df148342d8d` (updated 2026-07-17: added the Xenophanes B22 raw patch — see the Xenophanes section below; further updated 2026-07-17, Grok content audit close-out: added three `"scope": "chunk"` patches — `anaximander`/B1, `anaximenes`/B2, `anaxagoras`/B10 — trimming trailing apparatus that survived past each fragment's translated content, see the Zeno/Melissus/Anaxagoras/micro-pass section below) |
| Reproducibility | Re-running the extractor is byte-identical: verified by running twice, diffing all three output files (2026-07-17) |

**Revision pinning.** Both chapter mainspace pages ("Early Greek Philosophy/
Herakleitos of Ephesos", ".../Parmenides of Elea") exist and DO transclude
their `Page:` range cleanly via `<pages index=... from=... to=... />` — but
pinning a revision of that WRAPPER page does not pin the `Page:` subpages it
transcludes (ProofreadPage's `<pages>` tag resolves transclusion against
whatever the `Page:` subpages currently say, live, regardless of the
wrapper's own `oldid`). So, matching the granularity Haines/Oldfather
already established as necessary, this script pins and fetches all 67
individual `Page:.../<N>` subpages directly (`_HERAKLEITOS_PAGE_REVISIONS`/
`_PARMENIDES_PAGE_REVISIONS` in the extractor, captured 2026-07-17 via
`action=query&prop=revisions`). It also fetches RAW WIKITEXT
(`prop=wikitext`), not rendered HTML like the Haines/Oldfather scrapers —
verified byte-identical against a hand-fetched 5-page sample — because
Burnet's `<section begin="DKn">` tags and Parmenides' numeral headings are
easiest to parse directly off the wikitext's own templates
(`{{fine|...}}`, `{{c|{{fine|(N)}}}}`) rather than their rendered-HTML
projection.

**Edition verification.** The 1930 4th edition (archive.org
`earlygreekphilosOOOOburn`, OCR'd, retained in `raw/
earlygreekphilosOOOOburn_djvu.txt` as a verification witness only) carries
its own "NOTE ON THE FOURTH EDITION": "The present is a reprint of the
third edition, but the opportunity has been taken to incorporate a couple
of additional references and one correction which the author had noted in
his own copy and to correct some misprints and trivial slips." (signed
W. L. Lorimer, St Andrews, March 1930.) US-PD rationale for the 3rd
edition (1920) and its text: pre-1931 publication, safely public domain
under US rules regardless of the Wikisource transcription's own licensing
badge.

**Witness diff (2026-07-17).** Every one of the 115 Herakleitos columns and
all 18 Parmenides columns was checked against the 1930 OCR witness (fuzzy
anchor search + `difflib` comparison, then manual side-by-side reading of
every flagged case and a broad sample of unflagged ones — around 70
fragments read in full). **Zero substantive divergences found** — no word
that changes meaning, no added/removed clause, nothing rising above OCR
noise, across either chapter. The apparent low `difflib` ratios on short
fragments were entirely an artifact of the comparison window bleeding into
the next fragment's OCR text, not real disagreement (re-verified with a
tightly-bounded window). Explained OCR-only noise spotted along the way
(not fixed — these are the WITNESS's damage, not the shipped Wikisource
text's): "Ml" for "all" (B7), a glued footnote-digit "world,3" for
"world," (B30), heavy scan-quality garble on two short fragments (B47,
B51, e.g. "d° n°,l kn°W h°W" for "do not know how"), Greek-letter
transliteration OCR noise in the marginal Greek gloss of B48. **This confirms
the publisher's "trivial... slips" characterization
directly** — not one body-text divergence between the 3rd and 4th editions
was found in either chapter. No `WIKISOURCE-PATCHES.json` "chunk"-scope
(hand-verified typo) entries were needed — Burnet's Wikisource
transcription, unlike Haines' (5 patches) and Oldfather's, showed zero
transcription-typo defects across the full witness-diff pass.

**One raw-scope patch was needed** (`WIKISOURCE-PATCHES.json`, `"scope":
"raw"`) — a genuine Wikisource TAGGING defect, not a text defect:
`Page:.../154`'s `<section end="DK121" />` closes prematurely, mid-sentence
("...for they have cast out Hermodoros, the best man among them,"),
immediately followed by `Page:.../155` opening with the sentence's real
continuation ("saying, 'We will have none who is best among us...'") and a
SECOND, correctly-placed `<section end="DK121" />`. The patch removes the
premature first close so the general scan captures the whole two-page
fragment; the reconstructed B121 text is a single continuous sentence,
matching both the OCR witness and the Greek.

**Extraction model differs by chapter — both documented in the extractor's
own module docstring in full:**

- **Herakleitos**: parsed from Wikisource's own `<section begin="DKn" />`
  tags — added by Wikisource contributors, keyed to genuine DK numbers, NOT
  by Burnet himself (his own printed numerals follow Bywater's 1877
  subject-based arrangement and are wildly out of DK order — e.g. the first
  five tagged fragments on one page are DK50, DK1, DK34, DK107, DK17).
  **This directly contradicts this project's own earlier groundwork survey
  claim that "his fragment numbers ARE Diels numbers"** — true only in the
  sense that the Wikisource TAGS are DK numbers; Burnet's own printed
  parenthetical numerals are Bywater's, not Diels'. Flagging because it's a
  correction to a "fact" the Wave 1b design memo (SS0) states as
  established.
- **Parmenides**: Wikisource has NOT added per-fragment DK tags here — only
  one wrapper (`ParmFrag`) brackets the whole listing. Burnet states
  explicitly, in his own printed text, "I follow the arrangement of
  Diels" — so the extractor parses his own printed numeral headings
  (`{{c|{{fine|(N)}}}}`) directly rather than relying on section tags. **This
  does NOT mean his numerals are the DK6 numbers, though** — corrected
  2026-07-17 (see "Parmenides B2-B5 concordance correction" below): "the
  arrangement of Diels" turns out to mean Diels' EARLIER "Parmenides
  1897 edition's numbering for fr. 2-5 specifically, which the later
  DK6 (Diels-Kranz 6th ed., 1951 — the TLG spine's own edition) renumbered.
  His numerals genuinely ARE the DK6 numbers for fr. 1 and 6-19 (and the
  real 10/11 combined heading). One heading (fr. 6, `Page:.../188`) has a
  transposed-brace transcription typo (`{{c|{{fine|(6}})}}}}`); the
  extractor's boundary-finding is designed to be robust to this by
  construction (it never needs to locate a heading's closing braces — see
  the module docstring) rather than patching the typo.

**Two systematic Herakleitos irregularities, both real Burnet/Wikisource
content, not extraction bugs:**

1. `DK110111` is one Wikisource tag wrapping ONE Burnet translation
   ("(104) It is not good for men to get all they wish to get...") that DK
   numbers separately as B110 and B111 — the extractor duplicates the text
   under both column keys. Parmenides has the parallel case at the heading
   level: "(4, 5)" and "(10, 11)" each duplicate one translation under two
   DK keys.
2. Letter-suffixed tags are inconsistently cased on Wikisource's side:
   `DK31A`/`DK31B`, `DK5A`/`DK5B`, `DK84A`/`DK84B` alongside lowercase
   `DK49a`/`DK101a`. The extractor lowercases every suffix uniformly (the dk
   citation scheme's own contract, docs/wave1b-presocratics-design.md
   SS2.1: canonical lowercase, case-insensitive input) — shipping `B31a`,
   `B31b`, `B5a`, `B5b`, `B84a`, `B84b`. **B5a/b and B31a/b are NOT in the
   Wave 1b design memo's own catalogue of the TLG Greek spine's lettered
   columns** (SS0 lists only `1a 3a 3b 14a 49a 67a 84a 84b 101a 125a 126a
   126b`) — both ARE well-attested genuine Diels-Kranz sub-fragment splits
   (B31's fire/sea/earth transformation, quoted by Clement in two adjacent
   excerpts; B5's purification fragment, quoted by Origen in two parts), so
   shipping them as split columns is very likely correct, but this is an
   **open cross-check for the Greek-spine/scheme owner**: if the TLG spine
   keeps B5/B31 as single undivided columns, `validate_english_source` will
   reject these two English keys as matching no spine column — exactly the
   "tag errors... fail only at key-set reconciliation" risk the design memo
   itself names (SS Open risk 4). → worth a CANON.md log entry once
   resolved either way.

**Wikisource's own explicit "no DK number" placeholder, `DKxx`** — used 4
times in Ch. III, at Bywater ordinals 14, 43, 57, and 87-89. Collected by
the extractor (`build_heraclitus` returns them separately) but NEVER
emitted as a clean.json key — there is no DK column to attach them to. The
surrounding tagging is meticulous (every lettered sub-fragment correctly
assigned), which makes "Wikisource just hasn't tagged these yet" an
implausible reading — far more likely these are exactly the
Bywater-arrangement items Diels excluded as spurious/inauthentic, which the
design memo's SS0 predicts ("gaps track Diels' own spurious/duplicate
exclusions"). The four excluded texts, verbatim, for the record:

- (14) ". . . bringing untrustworthy witnesses in support of disputed
  points."
- (43) "Homer was wrong in saying: 'Would that strife might perish from
  among gods and men!' He did not see that he was praying for the
  destruction of the universe; for, if his prayer were heard, all things
  would pass away. . . . R. P. 34 d."
- (57) "Good and ill are one. R. P. 47 c."
- (87-89) "A man may be a grandfather in thirty years."

**Burnet's cross-reference notes** (e.g. Bywater ordinal 56, "(56) Same as
45.") are NOT wrapped in any `<section>` tag on Wikisource — only one such
note exists in the whole of Ch. III, and it carries no DK tag at all
(confirmed: ordinal 45 is DK51, which already has its own full translation
elsewhere — the note is Bywater re-citing the same fragment a second time
under his own subject arrangement, not a distinct DK entry). Since the
extractor only ever captures TAGGED content, this untagged note is simply
never extracted, which is correct: there is no separate DK column it could
fill. The general extraction mechanism has no special-casing for
cross-reference TEXT — if Wikisource ever tags one inside a real
`<section begin="DKn">`, it is captured verbatim like any other content
(tested in `test_extract_burnet_wikisource.py`).

**Herakleitos coverage.** 115 DK columns shipped (114 distinct Wikisource
tags, `DK110111` duplicated into B110/B111). Absent plain B-numbers in the
1–139 range (32 of them): 3, 5, 31, 46, 56, 68, 69, 70, 71, 74, 81, 82, 84,
105, 109, 112, 115, 116, 122, 124, 127, 128, 130, 131, 132, 133, 134, 135,
136, 137, 138, 139 — but 5, 31, and 84 are NOT true gaps (present as
lettered `B5a`/`B5b`, `B31a`/`B31b`, `B84a`/`B84b`), and 109 is the expected
Diels-deletion gap the Wave 1b design memo already documents. That leaves
**28 genuine no-translation gaps**, concentrated in two groups: scattered
low numbers Bywater's 1877 arrangement simply didn't select (3, 46, 56, 68,
69, 70, 71, 74, 81, 82, 105, 112, 115, 116, 122, 124, 127, 128 — 18 of
them), and the entire 130–139 range (10 fragments) — the latter almost
certainly because Bywater's edition (1877) predates several fragments Diels
added to later editions from other sources (the traditional high-numbered
"dubia" range); not independently confirmed against Diels' critical
apparatus here, flagged for whoever builds the `alignment_allow_unmatched`
list against the real TLG spine. Plus the 4 `DKxx` exclusions above (not
real DK numbers at all, not spine gaps).

**Parmenides coverage.** 18 DK columns shipped from 16 of Burnet's own
numbered headings (B2/B3 and B10/B11 each one heading, duplicated).
Canonical range 1–19 minus **B18**, the one genuine, well-explained gap:
Burnet's own footnote to fr. 17 states "Diels's fr. 18 is a retranslation
of the Latin hexameters of Caelius Aurelianus quoted R. P. 127 a" — not an
original Greek quotation, so Burnet doesn't translate it. B15a (a genuine
DK number beyond Burnet's 1–19 coverage, per the design memo) is correctly
absent — no heading for it exists in Burnet's text at all.

**Parmenides B2–B5 concordance correction (ship-blocker, fixed 2026-07-17).**
A content-verification pass (Grok-4.5 gate, orchestrator-verified) found
that the extractor's original identity-keying of Burnet's printed numerals
2–5 to DK6 columns B2–B5 was WRONG for that one block — each emitted
English was the translation of a DIFFERENT fragment (e.g. Greek B2 carried
Burnet's "Look steadfastly...", which is actually his
rendering of DK6 B4). Root cause: Burnet's "I follow the arrangement of
Diels" refers to Diels' EARLIER 1897 numbering
for fr. 2–5 specifically, not the DK6 (Diels-Kranz 6th ed., 1951)
numbering the TLG spine uses — DK6 reshuffled exactly this block after
Burnet's 3rd edition (1920) was printed. Ground-truthed two independent
ways (2026-07-17, against the pinned Wikisource revisions and
`build/export/.../tlg1562002.xml`):

| Burnet's printed numeral | Burnet's English (opening) | Greek content match |
|---|---|---|
| (1) | "The car that bears me..." | DK6 B1 — identity holds |
| (2) | "Look steadfastly with thy mind..." | **DK6 B4** |
| (3) | "It is all one to me where I begin..." | **DK6 B5** |
| (4, 5) | "Come now, I will tell thee...the only two ways...it is the same thing that can be thought and that can be" | **DK6 B2** with **DK6 B3** embedded as the closing sentence |
| (6) | "It needs must be that what can be spoken and thought is..." | DK6 B6 — identity holds |

Corroborating footnote evidence: Burnet's own footnote to his "(4, 5)"
heading (Wikisource `Page:.../187`, pinned revid 9192426) reads "It is
impossible to separate this from **fr. 4**, 'can be thought.'" —
self-consistently confirming his own numeral 4 as the
old-numbering identity of the very fragment he is translating there (DK6's
B2, the "two ways" fragment), not DK6's separate B4 ("Look steadfastly").
Fixed by `_PARMENIDES_HEADING_REMAP` in the extractor (declared, fail-loud
if an expected raw heading is missing — same discipline as
`_CONCAT_MERGE_COLUMNS`), not a silent renumber; `burnet-parmenides.clean
.json` was regenerated from the same pinned revisions (SHA-256 updated
above). B6–B17 and B19 (and the real 10/11 combined heading) were
independently content-verified against the DK6 Greek and are unaffected —
identity holds.

**Parmenides is prose, not lineated verse — corrects a design-memo
assumption.** docs/wave1b-presocratics-design.md SS3 states "Burnet prints
his Parmenides lineated" and that the DL-epigram verse-standoff machinery
(`english.verse`, hard `{start,end,breaks}` ranges) would be "reused
as-is." Direct inspection of the pinned wikitext shows this is wrong:
Burnet's English is CONTINUOUS PROSE with sparse (every-5th-Diels-line)
marginal cross-reference markers (`{{left/right sidenote|N}}`) — verified
directly, a marker sits mid-sentence between two words of one flowing
clause with no line break of any kind on either side (e.g. B1: "...left
the" | marker "10" | "abode of Night." — one sentence, split only by the
marker). What this actually matches is Oldfather's Discourses `paras`
sidecar (`oldfather-discourses-paras.json`), not the DL verse-standoff
shape — so `burnet-parmenides-paras.json` reuses THAT shape:
`{"<column>": [{"n": <Diels line number>, "o": <char offset into the
column's clean text>}, ...]}`, 6 columns with markers (B1, B8, and others;
short fragments naturally have none — never an empty array, matching the
Oldfather convention). **Flagging for the stage1 dk-scheme owner**:
whatever renders Parmenides' English side should consume this the way
`stage1_book_section_english.py` consumes `paras_sidecar`, not
`verse_sidecar`.

**No footnotes captured**, matching house style: `<ref>...</ref>` (and
self-closing `<ref .../>`) dropped wholesale, same as
`extract_haines_wikisource.py`/`extract_oldfather_wikisource.py` — Burnet's
extensive philological apparatus is editorial commentary, not the
translation.

## Xenophanes (Wave 1b presocratic pilot, third dk author, DK scheme)

### PRIMARY — John Burnet, *Early Greek Philosophy*, 3rd ed. (1920),
sourced via Wikisource (same edition, same mechanism as Herakleitos/
Parmenides above)

| | |
|---|---|
| Translator | John Burnet |
| Source | Wikisource, `Index:Early Greek philosophy by John Burnet, 3rd edition, 1920.djvu` (en.wikisource.org) — per-page proofread transcription, ProofreadPage quality 3 ("Proofread") |
| Coverage | Ch. II "Science and Religion", second half (the Xenophanes portion, covered as the chapter's second topic after Pythagoras) — djvu pages 94–143 (50 pages) |
| Extraction tool | `pipeline/tools/extract_burnet_wikisource.py`, `build_xenophanes` |
| Files | `burnet-egp/burnet-xenophanes.clean.json` (32 DK columns) |
| SHA-256 (burnet-xenophanes.clean.json) | `8111e224f0f2bcd3d42a9be0024934bc06274d14f064f7736603922bc88d3572` (regenerated 2026-07-17 after the B38 boundary fix and B22 re-attachment below) |
| SHA-256 (WIKISOURCE-PATCHES.json) | see the shared table above (this file is shared across all three Burnet authors) |

**Witness diff.** No substantive 1920↔1930 (3rd↔4th ed.) divergence found
in the Xenophanes sections — same "trivial... slips" characterization as
Herakleitos/Parmenides above (witness-diff pass performed during the
consolidated Sol/Grok review fix round, 2026-07-17; no chunk-scope patch
was needed for Xenophanes either).

**Two defects found by review and fixed in this pass (2026-07-17,
consolidated Sol/Grok fix round):**

1. **B38 end-boundary contamination (Grok review defect G1, CRITICAL).**
   `_extract_xenophanes_fragments`'s last-heading fallback used
   `len(body)` as the content end when no FOLLOWING heading existed to
   bound it — for the listing's actual last heading, (38), this let
   Burnet's own §§58-62 running commentary (raw, un-stripped wiki markup
   included: `"58.{{right sidenote|The heavenly bodies.}}..."`) bleed in
   as ~11k characters of contamination after the genuine one-sentence
   fragment. Fixed by bounding the last heading against the listing's own
   `<section end="XenoFragC" />` tag (`_XENO_LISTING_END`) instead — see
   the extractor's module doc. B38 now ends cleanly at "...than they do."
2. **B22 never attached (Grok review defect G2).** Burnet DOES translate
   DK6 B22 ("This is the sort of thing we should say by the fireside in
   the winter-time...", content-verified against the source passage) —
   quoted in the biographical
   narrative two paragraphs after B8's own quotation, same shape, but
   (unlike B8) never wrapped in a Wikisource `<section>` tag of its own,
   so it fell through both the heading scan and the XenoFragB
   re-attachment with no column at all; `citation.alignment_allow_
   unmatched` carried "1:B22" as a supposed genuine edition gap. Fixed by
   a new `raw`-scope patch in `WIKISOURCE-PATCHES.json` that inserts this
   module's OWN `XenoFragB22` tag pair around the exact, content-pinned
   span (matched exactly once), re-attached through the same hardened
   discipline as B8 (`_xeno_reattach_tagged_fragment`, shared by both).
   "1:B22" removed from `manifests/xenophanes-fragments.yaml`'s
   `alignment_allow_unmatched`.

**Re-attachment hardening (Sol review blocker S4).** Both B8 and B22's
`<section>`-tag re-attachment now requires exactly one begin AND exactly
one end tag (a duplicated or re-tagged span fails loudly rather than
silently matching `.find()`'s first occurrence), begin strictly before
end, and non-empty cleaned content free of residual wiki template/link
markup — mirrors the Herakleitos DK5A/DK5B duplicate-tag hardening.
Verified by an extractor-wide invariant test (`test_extract_burnet_
wikisource.py::test_no_wiki_template_markup_survives_in_any_clean_json`)
sweeping every `sources/burnet-egp/*.clean.json` for raw `{{`/`}}`/`[[`/
`]]`/"sidenote" markup.

**Numeral remap** (`_XENOPHANES_NUMERAL_REMAP`, Burnet's (4)→DK6 B5,
(5)→DK6 B6) and the B8 cross-reference exclusion (heading "(8)" = "See p.
114.", a pointer to the separately-tagged XenoFragB quotation) both
content-verified against the Greek — same defect class and same
resolution discipline as Parmenides' B2-B5 remap above; unlike Parmenides
this one had zero dedicated tests before this pass (now covered, along
with the boundary/re-attachment fixes above, in `test_extract_burnet_
wikisource.py`).

## Zeno, Melissus, Anaxagoras, and the micro-pass (task #48, the Burnet
English alignment wave)

### PRIMARY — John Burnet, *Early Greek Philosophy*, 3rd ed. (1920), sourced
via Wikisource (same edition, same mechanism as the four works above)

| | |
|---|---|
| Translator | John Burnet |
| Source | Wikisource, `Index:Early Greek philosophy by John Burnet, 3rd edition, 1920.djvu` (en.wikisource.org) — per-page proofread transcription, ProofreadPage quality 3 ("Proofread") |
| Zeno + Melissus coverage | Ch. VIII "The Younger Eleatics" (Zeno of Elea, printed S:S154-163; Melissus of Samos, S:S164-170), djvu pages 324-343 (20 pages), printed pp. 310-329 |
| Anaxagoras coverage | Ch. VI "Anaxagoras of Klazomenai", its own chapter, djvu pages 265-289 (25 pages), printed pp. 251-275 |
| Micro-pass coverage | Anaximander B1: djvu page 66 (Ch. I "The Milesian School", djvu 53-93, printed 39-79); Anaximenes B2: djvu page 87 (same chapter); Leucippus B2: djvu page 354 (Ch. IX "Leukippos of Miletos", djvu 344-363, printed 330-349) |
| Fetched | 2026-07-17, via MediaWiki `action=parse&oldid=<revid>&prop=wikitext` (raw wikitext of a PINNED revision), each Page: subpage's revid individually captured via `action=query&prop=revisions` |
| Extraction tool | `pipeline/tools/extract_burnet_wikisource.py`, `build_eleatics_ch8` / `build_anaxagoras` / `build_anaximander_micro` / `build_anaximenes_micro` / `build_leucippus_micro` |
| Files | `burnet-egp/burnet-zeno.clean.json` (3 columns), `burnet-egp/burnet-melissus.clean.json` (10 columns), `burnet-egp/burnet-anaxagoras.clean.json` (23 columns), `burnet-egp/burnet-anaximander.clean.json` (1 column), `burnet-egp/burnet-anaximenes.clean.json` (1 column), `burnet-egp/burnet-leucippus.clean.json` (1 column) — no paras sidecars (all six are plain prose in this wave, unlike Parmenides/Empedocles: no marginal Diels-line sidenote markers appear inside any of these listings) |
| SHA-256 (burnet-zeno.clean.json) | `0b2aa3985d51329b5815cd8b6231ca3eaed441733cf4d8a50fa2142f4a79fe58` |
| SHA-256 (burnet-melissus.clean.json) | `1668302686ed9443304c659f1fc6a05e39267af5d2a37535aa99783eb179291f` |
| SHA-256 (burnet-anaxagoras.clean.json) | `014bbbb435821cb3ddb211192334b556a0c604c9075372ea37841260e3ab0e48` |
| SHA-256 (burnet-anaximander.clean.json) | `280d9eeb919556346206d5218fd5721093d98028cee20bd9e82a61ac51416b45` |
| SHA-256 (burnet-anaximenes.clean.json) | `ee146474a230c5b5ef49fe154fd5de96e35a0092587eaad49d4a62133504681f` |
| SHA-256 (burnet-leucippus.clean.json) | `ec777ec40aa3b249ce0c263429dbb4b91147cfa1fdb2982ad8253e40dc494068` |
| SHA-256 (WIKISOURCE-PATCHES.json) | see the shared table above (updated 2026-07-17, Grok content audit close-out: three `"scope": "chunk"` patches added — `anaximander`/B1, `anaximenes`/B2, `anaxagoras`/B10 — trimming trailing apparatus (Burnet's own connective frame, a doxographical source citation, and footnote-marker residue) that survived past each fragment's translated content; see the patch entries' own `note` fields). `burnet-anaxagoras.clean.json`, `burnet-anaximander.clean.json`, and `burnet-anaximenes.clean.json` were regenerated against the same pinned revids to apply the trim; `burnet-zeno.clean.json`, `burnet-melissus.clean.json`, and `burnet-leucippus.clean.json` are untouched by these three patches and unchanged from the hashes above |
| Reproducibility | Verified 2026-07-17 by re-running every `build_*` function directly against a fresh network fetch of the pinned revids (bypassing `main()`'s file writes) and diffing the result against the committed `sources/burnet-egp/*.clean.json` in-memory: byte-identical for `burnet-zeno.clean.json`, `burnet-melissus.clean.json`, and `burnet-leucippus.clean.json`; the other three (`burnet-anaxagoras.clean.json`, `burnet-anaximander.clean.json`, `burnet-anaximenes.clean.json`) reproduce deterministically once the three chunk patches above are applied, confirming the pinned revid tables plus WIKISOURCE-PATCHES.json together reproduce byte-identical output |

**Revision pinning.** Same per-`Page:`-subpage pinning discipline as
Herakleitos/Parmenides/Xenophanes/Empedokles above (`_ELEATICS_PAGE_
REVISIONS`, `_ANAXAGORAS_PAGE_REVISIONS`, `_MICRO_PASS_PAGE_REVISIONS` in
the extractor) — each chapter's `Page:` range independently confirmed
against the Index's own Contents page (printed-page ranges) and each
chapter wrapper page's own `<pages index=... from=... to=... />` values.

**Extraction model — three distinct shapes, none DK-tag-driven (Wikisource
never added per-fragment `<section begin="DKn">` tags to any of these four
chapters):**

- **Zeno** (S:S160, "I give them according to the arrangement of Diels"):
  Burnet's own numbered headings, `{{c|{{fine|(N)}}}}`, same heading-scan
  mechanism as Parmenides/Xenophanes/Empedokles (`_extract_zeno_fragments`
  reuses the shared boundary/heading-open/fine-open regexes verbatim) —
  but hard-bounded to the literal span between the S:S160 and S:S161
  paragraph markers, since Zeno's fragment listing carries no chapter-wide
  `<section>` wrapper of its own. This bound is the primary defense
  against S:S163 (see below); the heading-shape mismatch is a second,
  independent defense in depth.
- **Melissus** (S:S165) and **Anaxagoras** (S:S126, "I give the fragments
  according to the text and arrangement of Diels"): a different shape —
  Burnet's ordinal sits INLINE inside the fragment's own `{{fine|(N)
  ...}}` block, with no separate heading template at all
  (`_extract_ordinal_fine_fragments`/`_clean_ordinal_fine_fragment`,
  shared by both). Melissus' listing sits inside Wikisource's own
  `<section begin="MelisFrag">` wrapper; Anaxagoras' inside `<section
  begin="AnaxFrag">` — both located via `_extract_tag_bounded_span`
  (hardened exactly-one-begin/exactly-one-end discipline, the same
  re-attachment safety as Xenophanes' B8/B22).
- **Micro-pass** (Anaximander B1, Anaximenes B2, Leucippus B2): no general
  parser at all — each of the three source chapters (Ch. I "The Milesian
  School", Ch. IX "Leukippos of Miletos") is continuous biographical/
  doxographical prose with no DK tagging AND no numbered-fragment listing
  of any kind, so each quotation is located by a literal English
  start-phrase (or start/end-phrase) anchor asserted to match EXACTLY ONCE
  on its own pinned page (`_extract_micro_fine_block`/`_extract_micro_
  quoted_span`) — the same fail-loud, exactly-once-match discipline as
  `WIKISOURCE-PATCHES.json`'s own patches, chosen over hand-transcribing
  the quotation to avoid a silent transcription mismatch against this
  module's own footnotes/em-dashes/curly punctuation.

**S:S163 — Burnet's own paraphrase of Aristotle's motion arguments, never
extracted (by construction, not by exclusion list).** Immediately after
Zeno's three genuine fragments, S:S163 ("Zeno's arguments on the subject of
motion have been preserved by Aristotle himself... They are as follows")
introduces Burnet's OWN four-item PARAPHRASE of Aristotle's *Physics* Z 9
testimonia (the stadium, Achilles, arrow, and moving-rows arguments) — not
a translation of any DK fragment at all. Two independent structural facts
keep it out of the extraction, verified directly against the pinned
wikitext and covered by dedicated must-fail tests
(`test_zeno_section_163_paraphrase_excluded_by_the_160_161_bound`,
`test_zeno_section_163_inline_shape_cannot_produce_its_own_heading_match`):
S:S163 sits strictly AFTER the S:S161 marker that hard-bounds the heading
scan, and even if it did not, its own shape — an INLINE `{{fine|(N)
...}}` block with no separate `{{c|{{fine|(N)}}}}` heading of its own —
can never satisfy the heading-boundary regex the scan requires. B4 (Zeno's
one DK column absent from Burnet's own coverage — Diogenes Laertius ix.
72's independent one-sentence aphorism) is content-verified NOT to be the
arrow argument or any of S:S163's other three items (thematically close —
both deny motion — but S:S163's own text is Burnet's multi-sentence
paraphrase of Aristotle, not a quotation of Zeno).

**Melissus' two Burnet-own insertions, (1a) and (6a) — declared exclusions,
never emitted, verified against both fragments' own footnotes.** (1a):
Burnet restores a passage Diels' 6th edition dropped entirely ("It is no
longer necessary to discuss the passages which used to appear as frs. 1-5
of Melissos, as it has been proved by A. Pabst that they are merely a
paraphrase of the genuine fragments... I still believe, however, that the
fragment which I have numbered 1a is genuine"). (6a): Burnet's own
interpolation with no Greek original at all ("I have ventured to insert
this, though the actual words are nowhere quoted, and it is not in
Diels"). Both are collected by `build_eleatics_ch8` (returned as
`melissus_excluded`, printed by `main()`) but never keyed as "B1a"/"B6a" —
there is no DK column for either to attach to. Melissus' own printed
listing runs (1a), (1)-(10), (6a) — DK's B11 (a later Palaephatus
addendum, "Melissus and Lamiscus of Samos") sits entirely outside this
range and is a genuine coverage gap, not a third exclusion (see
`manifests/melissus-fragments.yaml`'s `alignment_allow_unmatched`).

**Anaxagoras' (20) — a Burnet item with no DK number at all, same
treatment.** "(20)" ("With the rise of the Dogstar (?) men begin the
harvest; with its setting they begin to till the fields. It is hidden for
forty days and nights") is collected (`anax_excluded`) but never emitted
as "B20" — confirmed as Diels' own numbering gap (no `B20` div exists in
this work's TLG export either; `manifests/anaxagoras-fragments.yaml`'s own
`citation.expected_gaps` already declares it). Every OTHER one of Burnet's
24 numbered items — (1)-(19), (21), (21a), (21b), (22) — identifies 1:1
with its DK column; Anaxagoras is this wave's only FULL-coverage work (see
the alignment table in the task #48 delivery report for the full
content-spot-check, one row per emitted fragment).

**Anaximander B1's quotation-start boundary — a live philological call,
flagged for the Opus pass, not resolved here.** DK6's own marked B1 Greek
span (`build/dist/anaximander-fragments/book-01.json`) includes the
preceding origin-and-destruction clause as part of the SAME quotation that
ends in the "reparation" sentence. Burnet's own printed quotation marks
open only at "as is meet" (the reparation clause alone) — his own footnote
makes the disagreement with Diels explicit: Diels begins the actual quotation
earlier, while Burnet says conventional blending of quotations with the text
argues against that boundary. Extracted here
VERBATIM AS BURNET PRINTS THE WHOLE SENTENCE (his own lead-in prose
together with his quotation-marked clause) — matching how the general
heading/ordinal-fine extractors above always capture a whole `{{fine|
...}}` span rather than sub-selecting inside it. Not resolved by this
extraction; the quotation-start boundary itself is a live philological
call for the Opus pass.

**No footnotes captured, no wiki markup survives** — same house style as
the four works above (`<ref>...</ref>` dropped wholesale; the
extractor-wide invariant test sweeps every `sources/burnet-egp/*.clean.
json`, including these six, for residual `{{`/`}}`/`[[`/`]]`/"sidenote"
markup — zero violations).

**Coverage summary.** Zeno: 3 of 4 DK columns (B4 a genuine gap, above).
Melissus: 10 of 11 (B11 a genuine gap, above). Anaxagoras: 23 of 23 — FULL
coverage, this wave's only complete work. Anaximander: 1 of 6 (B1 only,
micro-pass). Anaximenes: 1 of 4 (B2 only, micro-pass). Leucippus: 1 of 3
(B2 only, micro-pass; B1a is also this work's own declared
`unmarked_columns` entry, so it would be a coverage gap even under a full
Ch. IX parse). Thales, Pythagoras, Philolaus, and Democritus remain
Greek-only by this wave's own explicit scope (no english block; Burnet's
Ch. I biographical prose covers Thales alongside Anaximander/Anaximenes
with nothing further to extract mechanically, and Ch. IX covers Democritus
alongside Leucippus the same way — both future work, not this wave's
scope).

---

## Cicero, *De Officiis* (Wave 2 Batch 1a, first Latin+English work,
citation scheme `book-section`, e.g. `1.8`)

### PRIMARY — Walter Miller, *Cicero: De Officiis* (Loeb Classical Library
30, 1913) — sourced from the **Perseus Digital Library**

| | |
|---|---|
| Translator | Walter Miller (1864–1949) |
| Publisher | London: William Heinemann; New York: G. P. Putnam's Sons |
| Publication year | 1913 (Loeb Classical Library 30) |
| US-PD rationale | Published 1913, pre-1931 — safely US public domain |
| Source | Perseus Digital Library / PerseusDL `canonical-latinLit` GitHub repo, file `data/phi0474/phi055/phi0474.phi055.perseus-eng1.xml` |
| Source URL | https://raw.githubusercontent.com/PerseusDL/canonical-latinLit/master/data/phi0474/phi055/phi0474.phi055.perseus-eng1.xml (also browsable via https://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:2007.01.0048) |
| CTS identifier | Perseus id `2007.01.0048`, target `canonical-latinLit/data/phi0474/phi055/phi0474.phi055.perseus-eng1.xml` (per the file's own `.tracking.json` sidecar) |
| Pinned commit (last touching this file, as of retrieval) | `1066a551aa5445ab165e9b490a6bb06ce72828da` (2026-06-23, "(review_work) phi0474 Cicero batch: … fixes to author and editor in headers" — a header-metadata fix, not a translation-text edit; fetched 2026-07-17 from `master` and confirmed byte-identical to this pinned commit before pinning) |
| Retrieved | 2026-07-17, via GitHub raw at the pinned commit |
| File | `miller-de-officiis/phi0474.phi055.perseus-eng1.xml` (raw XML as retrieved, pristine) |
| SHA-256 | `9eb13903d602c40a691954db79b2a0336f9baa0012f3cf3d3ef5374d90f99c86` |
| Size | 409,418 bytes (7,593 lines) |
| Markup license | Perseus's own TEI/EpiDoc encoding; the underlying 1913 Miller translation is independently US-PD by publication date |

**Edition-identity verification (the Rouse/Smith-trap discipline, §5.2#3 of
`docs/wave2-latin-design.md`).** This is genuinely Miller's original,
unrevised 1913 translation — no later-revision risk of the kind that
affects Lucretius' Rouse (1924, revised post-1975 by Smith in later Loeb
reprints) is known for this text, and the evidence chain below rules it
out directly rather than by absence of a known revision:

- **Perseus's own teiHeader** records `<title>De Officiis</title>`,
  `<author>M. Tullius Cicero</author>`, `<editor role="translator">Walter
  Miller</editor>`, and a `sourceDesc/biblStruct/imprint` reading "London;
  New York / William Heinemann; G.P. Putham's Sons / 1913", series "Loeb
  Classical Library" — and its own `<ref>` in that same `biblStruct`
  points straight at `https://archive.org/details/deofficiiswithen00ciceuoft`
  as its print source, i.e. Perseus itself declares the same scan this
  verification independently found.
- **archive.org catalog metadata for `deofficiiswithen00ciceuoft`**
  (fetched independently, not just followed as a link): title "De
  officiis. With an English translation by Walter Miller", creator "Marcus
  Tullius Cicero (author); Walter Miller, 1864-1949 (translator)",
  publisher "London Heinemann", date **1913**,
  `possible-copyright-status: NOT_IN_COPYRIGHT`, `copyright-region: US` —
  matching Perseus's own imprint line exactly (Perseus additionally names
  the Putnam's Sons US co-publisher, standard for a Loeb of this period;
  archive.org's catalog record is UK-copy-only).
- **Independent cross-check against Project Gutenberg #47001** (a wholly
  separate transcription project, not Perseus-derived): its own
  transcriber's note credits "Walter Miller" as translator and "William
  Heinemann (London) and The Macmillan Co. (New York), MCMXIII [1913]" as
  publisher — Macmillan rather than Putnam's Sons as the US co-publisher
  named, a detail difference consistent with two different imprints of
  the same 1913 first edition rather than a shared error, and immaterial
  to the translation text itself. Book I's opening sentence in the
  Gutenberg transcription — "My dear son Marcus, you have now been
  studying a full year under Cratippus…" — is **verbatim identical** to
  this file's own `1.1` text (verified directly, not by memory), the
  strongest available signal that no revision-era wording drift exists
  between two independently-sourced copies of the same nominal edition.
- **No known revision of Miller's De Officiis exists** in the way Rouse's
  Lucretius was later revised by Smith — the Loeb series never issued a
  revised edition of this volume under Miller's name (unlike Lucretius 181
  or the ND/Academica Rackham volumes flagged elsewhere in
  `docs/wave2-latin-design.md` §8.1); this is Miller's plain original text.

**Structure.** `<div type="textpart" subtype="book" n="1"|"2"|"3">`
(**Book III's own `@n` is mislabeled `"1"`, the same value as Book I** — a
genuine Perseus data-entry bug, confirmed by direct inspection; handled by
`extract_miller_perseus.py` numbering books by DOCUMENT ORDER, never by
`@n` — see the script's module docstring) containing `<p>` elements with
INLINE `<milestone unit="section" n="…">` markers — a De Officiis section
is not its own wrapping element (unlike Hicks' Diogenes Laertius
`<div subtype="section">`), it is the run of text between one section
milestone and the next, which does not align with `<p>` boundaries (e.g.
2.88/2.89 both sit inside one `<p>`). Two other milestone units appear and
are both ignored (see the script's docstring for the full verification):
`unit="chapter"` (Miller's literary I/II/III… divisions, unrelated to the
citable section numbering) and `unit="alternatesection"` (5 occurrences,
each verified to sit inside an already-open, correctly-numbered `section`
span — some second reference system Perseus's editors overlaid, never
load-bearing here).

**Completeness.** Book I: sections 1–161 (161, contiguous, no gaps). Book
II: sections 1–89 (89, contiguous — **no separate `n="90"` marker exists
in Miller's own numbering**; see the coverage-gap note below). Book III:
sections 1–121 (121, contiguous). Total: **371 of the Atzert/PHI Latin
spine's 372 book-section columns** (161+90+121).

**Coverage gap — 2.90, a genuine translator/edition numbering merge, not
an extraction bug.** The Latin spine's `2.90` is the single short sentence
"Reliqua deinceps persequemur." Miller's own English for this exact
sentence — "Let us now pass on to the remaining problems." — is present,
but folded into the tail of his own `2.89` (the paragraph following the
Cato "Bene pascere" exchange), with no separate section milestone marking
it. Verified directly against the real Latin PHI spine (already built at
`app/dist/data/de-officiis/book-02.json`'s `2.90` segment, text exactly
"Reliqua deinceps persequemur.") — the same shape as Meditations' Haines
5.37 gap (`manifests/meditations.yaml`). Declared in
`manifests/de-officiis.yaml`'s `alignment_allow_unmatched: ["2:2.90"]`.

**Cleaning conventions.** `<note>` (both `type="marg"` running-summary
sidenotes, 306 occurrences, and untyped explanatory footnotes, 86
occurrences) dropped whole — editorial apparatus, never translated prose.
`<foreign xml:lang="greek">` in the running body text (13 occurrences, 11
distinct strings — 8 further occurrences sit inside dropped notes) —
Perseus stores these as Beta-Code-like ASCII transliterations rather than
Unicode Greek (e.g. `"kato/rqwma,"` for "κατόρθωμα,"); decoded via a
small, closed, hand-verified table in the extractor (every term a
standard Stoic/ethical technical term whose sense matches its surrounding
English exactly, e.g. "the ordinary duty they call καθῆκον" / "what the
Greeks call εἴρων" / "εὐταξία", "εὐκαιρία", "σοφία", "φρόνησις", "πάθη",
"ὁρμαί"/"ὁρμή" — all textbook Ciceronian Stoic-ethics vocabulary matching
context exactly); an unrecognized string fails the build loudly rather
than passing through undecoded ASCII.
`<quote>` (not verse) wrapped in curly quotes, alternating double/single by
nesting depth (Perseus's data entry carries no literal quote-mark
characters for these, same convention as the Hicks Diogenes Laertius
extraction below). `<quote rend="blockquote">` (24 occurrences — Cicero
quoting verse: Ennius, Accius, Terence, Euripides via A. S. Way's
translation) passes through with no added quote marks (flattened into the
running section prose; no verse-line sidecar for this plain book-section
prose extraction). `<hi rend="italics">` loses its italics (no
markdown-emphasis convention exists in this corpus's `clean.json` files).
No wiki markup, no residual Beta-Code artifacts (swept for stray `/`/`)`/`(`
patterns post-extraction — zero hits).

### Stage-1 extraction: milestone-cursor walk, not a section-`<div>` walk

Miller (`sources/miller-de-officiis/miller.clean.json`) is built by
`pipeline/tools/extract_miller_perseus.py` (SHA-256
`8d454c2693b1303d923a4230b2661a519b1e21ff87052d4b71e0c10fc9db0926`), which
reads the pinned Perseus XML straight from
`sources/miller-de-officiis/phi0474.phi055.perseus-eng1.xml` (SHA-256
above, verified before every run) rather than re-fetching per run — same
"download once, verify the hash, read locally" shape as
`extract_hicks_dl_perseus.py`'s Diogenes Laertius extraction. Unlike Hicks
(section-level `<div>` wrappers merged by duplicate `@n`), a De Officiis
section has no wrapping element at all: the extractor threads a single
"current section" cursor through each book div in document order,
re-pointing it at every `unit="section"` milestone and appending every
other node's flattened text to whichever section is currently open (see
the script's module docstring for the full walk semantics, the Greek-term
decode table, and the quote-nesting rules). Output:
`miller.clean.json`, 371 keys (SHA-256
`a95279f3dd28ce26c1b0307571dc57e76ee665defa7267cf0d08d122f88d9f0b`).

**Coverage summary.** 371 of 372 book-section columns (99.7%) — the single
gap is the declared `2:2.90` translator-merge above, not a defect.


---

## Lucretius, *De Rerum Natura* (Wave 2, Latin+English; line-range-keyed
translation channel, alignment adjudication deferred to manifest stage)

### PRIMARY — H. A. J. Munro, *On the Nature of Things* (4th ed. text,
1886) — sourced from **Wikisource** (human-proofread transcription)

| | |
|---|---|
| Translator | Hugh Andrew Johnstone Munro (1819–1885) |
| First published | 1864 (Cambridge: Deighton Bell); Fourth Edition 1886 |
| Scan transcribed | Routledge (London), 1907 reprint — "On the nature of things (De rerum natura) Translated with an analysis of the six books by H.A.J. Munro" (OCLC 1050249224, per the Wikisource Index page's own metadata) |
| Edition identity | The 1907 reprint carries Munro's unchanged Fourth Edition (1886) translation text — the scan's own prefatory note (J. D. Duff) certifies "The translation has undergone no change" |
| US-PD rationale | Translation 1864, 4th ed. 1886, translator d. 1885 — safely pre-1931, US public domain |
| Source | en.wikisource.org, mainspace "On the Nature of Things (Munro)", subpages `/Book 1` … `/Book 6`, transcluding `Index:On the nature of things (De rerum natura) Translated with an analysis of the six books by H.A.J. Munro.djvu` (Book 1 = djvu 70–104, 2 = 105–142, 3 = 143–177, 4 = 178–218, 5 = 219–265, 6 = 266–308) |
| Proofread status | ProofreadPage quality 3 ("Proofread") on every one of the 239 Page: subpages |
| Pinning | Every Page: subpage fetched at a pinned revision (`action=parse&oldid=<revid>&prop=wikitext`); full book → djvu page → revid table captured 2026-07-17, lives in `_PAGE_REVISIONS` in `pipeline/tools/extract_munro_wikisource.py` (mainspace wrapper revisions do NOT pin transcluded Page: content — same lesson as Burnet/Haines/Oldfather) |
| Retrieved | 2026-07-17 |
| File | `munro-drn/munro.clean.json` (ordered array of 122 records `{book, range, start, end, [derived], text}` — one per printed spread, keyed by the print's own running-header Latin line ranges) |
| SHA-256 (munro.clean.json) | `6c8b56f665fcc7fc3471bfe4cfefa10f9e305030345c616455492e23858c82ae` |
| Patches | none — `sources/munro-drn/PATCHES.json` deliberately absent (no transcription defect requiring correction was found; the mechanism, Miller-shape exact-once, is wired in the extractor for future use) |

**Structure and keying.** The line-range keys are the print's own running
headers: every recto carries `{{rvh|…|<start>-<end>|…}}` giving the
Lucretius line range rendered on the open spread (preceding verso + that
recto); versos carry only unfilled placeholders (verified across all 239
pages). One record per spread. Books 1/4/6 open on a recto with no header
→ leading singleton record with a **derived** range `1-<first header
start>`; books 3/5 end on a verso with no following header → trailing
singleton with a **derived open-ended** range (`1077-` / `1447-`, end
null). Content-verified anchor: Book 1's verso djvu 71 begins mid-clause
exactly at 1.23, matching its recto's printed "23-90". Known print quirk
(reported, not papered over): Book 3's headers jump 60-125 → 127-189,
line 126 falling in neither.

**Munro vs PHI (Martin 1969 Teubner) line-count reconciliation** (report
only; adjudication at manifest stage): books 1 (1117), 2 (1174), 4 (1287)
match PHI's last lines exactly. Books 3/5: last printed header ends
1077/1447 vs PHI 1094/1457 — the remaining lines sit in the derived
open-ended trailing records, not a divergence of substance. **Book 6
genuinely diverges: Munro's last header reads 1250-1286 vs PHI's last
line 1251** — a real lineation difference at the end of Book 6 (whose
transmitted ending is a well-known site of editorial transposition and
renumbering between Munro's text (Lachmann-era numbering) and Martin's
Teubner); flagged for the alignment/manifest stage.

**Excluded material.** "THE ARGUMENT" (Munro's own range-keyed analysis of
all six books — a paraphrase, not the translation) is front matter, djvu
10–68, transcluded only by the separate mainspace `/Argument` subpage —
structurally outside every book's page range, never fetched; gates in the
extractor additionally reject its running head and its `NNN-NNN:`
colon-keyed paragraph shape anywhere in included text. Also excluded (each
reported at run time): one print footnote (djvu 280, printed 211: "See
note on p. 239."), and Munro's endnote on *presteres* + the printer's
imprint trailing the translation on the final page (djvu 308), truncated
at a fail-loud anchor. Munro's own asterisk line marking the transmitted
lacuna after 1.43 is kept in-channel as a `* * *` paragraph.

**Extraction.** `pipeline/tools/extract_munro_wikisource.py` (tests:
`pipeline/tests/test_extract_munro_wikisource.py`, offline/synthetic).
Deterministic against the pinned revids — verified by two full independent
network runs producing byte-identical `munro.clean.json`. Page-seam
handling (soft hyphens rejoined dropping the hyphen; `{{peh}}` compounds
rejoined keeping it — "smooth-polished", "close-packed"; `{{nop}}` page-end
paragraph breaks; 10 words straddling a record boundary attached to the
earlier record) is documented exhaustively in the module docstring.

## Cicero, *De Natura Deorum* ("On the Nature of the Gods") — Wave 2 Batch
3; chapter-keyed translation channel + chapter→section concordance
(alignment key for the book.section Latin spine)

### PRIMARY — C. D. Yonge, *On the Nature of the Gods* (1888) — sourced
from **Wikisource** (human-proofread transcription)

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891) |
| Published | 1888, New York: Harper & Brothers — "Cicero's Tusculan Disputations, also treatises On the Nature of the Gods, and On the Commonwealth" |
| US-PD rationale | Published 1888, translator d. 1891 — safely pre-1931, US public domain (per `docs/wave2-latin-design.md`'s own gate: Rackham 1933 ✗, Yonge substitutes) |
| Source | en.wikisource.org, `On the Nature of the Gods (Yonge)` (redirects to `Cicero's Tusculan Disputations/On the Nature of the Gods`), subpages `/Book 1` … `/Book 3`, transcluding `Index:1888 Cicero's Tusculan Disputations.djvu` (Book 1 = djvu 215–260, Book 2 = 260–324, Book 3 = 324–361; djvu 260 and 324 each shared by two adjacent books, disambiguated by inline `<section begin="otnotg_bookN" />` tags) |
| Proofread status | ProofreadPage quality 3 ("Proofread") on all but one of the 147 Page: subpages; djvu 348 (the Book 3 numbering-defect page, see Patches below) is quality 4 ("Validated") |
| Pinning | Every Page: subpage fetched at a pinned revision (`action=query&prop=revisions&rvslots=main`, raw wikitext); full djvu page → revid table captured 2026-07-18, lives in `_PAGE_REVISIONS` in `pipeline/tools/extract_yonge_nd_wikisource.py` (mainspace wrapper revisions do NOT pin transcluded Page: content — same lesson as Burnet/Haines/Munro/Oldfather) |
| Retrieved | 2026-07-18 |
| File | `yonge-nd/yonge.clean.json` (ordered array of 151 records `{book, chapter, text}` — Book 1: 44 chapters, Book 2: 67, Book 3: 40, strictly sequential from 1 within each book) |
| SHA-256 (yonge.clean.json) | `9bf8f6d431cee527b6093080f721ab82e1d746b61cf4d50ab12ad985dc4c55f` |
| Patches | one raw, exactly-once-matched patch in `sources/yonge-nd/PATCHES.json` — Book 3 djvu 348 (Validated quality) reads "XVII." for what content context requires to be "XXVII." (it falls strictly between the same page's own unambiguous "XXVI." and "XXVIII."), almost certainly the 1888 print's own erratum rather than a transcription slip |

**Structure and keying.** Chapters are marked inline with Roman numerals at
paragraph starts (no Arabic section numbers in this edition) — either the
plain "IVXLCDM+. " form, or, for exactly two chapters (Book 1's XXX, Book 2's
LXIV), `{{anchor+|ROMAN}}` (confirmed by fetching `Template:Anchor+`'s own
definition: a single positional argument renders as that argument's visible
text, not an invisible anchor). Every matched numeral is round-tripped
through int↔roman conversion as a malformed-numeral gate. Extensive markup
cleaning (footnotes dropped wholesale — 224 occurrences; `<poem>` verse
quotations, mostly Cicero's quoted Latin poets in Yonge's English verse — 57
occurrences — flattened into surrounding prose, since this work's citation
scheme is book.section prose, not verse-line; nested layout/font templates
unwrapped in a fixpoint loop; page-boundary hyphenation via both a bare
trailing `-` convention and an explicit `{{hws}}`/`{{hwe}}` template pair;
two `[[w:Title|Label]]` interwiki links; one Ppoem-module inline size
directive) is documented exhaustively in the extractor's module docstring.

**Excluded material.** Footnotes (`<ref>...</ref>`, 224 occurrences) dropped
wholesale, matching house style — none carry translation text, only editorial
notes/textual variants. Book-heading chrome ("BOOK I."/"BOOK II."/"BOOK
III.") sits before each book's first chapter marker and is simply never
captured (front-matter-before-chapter-1 is dropped, same convention as
Haines).

**Extraction.** `pipeline/tools/extract_yonge_nd_wikisource.py` (tests:
`pipeline/tests/test_extract_yonge_nd_wikisource.py`, 30 tests,
offline/synthetic). Deterministic against the pinned revids — verified by
two full independent network runs producing byte-identical
`yonge.clean.json`.

### Concordance — `yonge-nd/concordance.json` (the book.section alignment
key)

Yonge's edition carries no section numbers, so the chapter→section mapping
required for alignment against the PHI Ax Latin spine (book 1 = sections
1–124, book 2 = 1–168, book 3 = 1–95) is sourced from a **separate** PD
witness that prints both numberings.

| | |
|---|---|
| Witness | Joseph B. Mayor (collation by J. H. Swainson), *M. Tulli Ciceronis De Natura Deorum Libri Tres*, 3 vols. (Cambridge: University Press, 1880–1885) |
| US-PD rationale | Published 1880–1885 — safely pre-1931; vol. 1 (`denaturadeorum01ciceuoft`) and vol. 3 (`denaturatres03ciceuoft`) both carry archive.org `possible-copyright-status: NOT_IN_COPYRIGHT` / `copyright-region: US` |
| Source | archive.org, `denaturadeorum01ciceuoft` (vol. 1/Book I), `denaturadeorumli02cice` (vol. 2/Book II), `denaturatres03ciceuoft` (vol. 3/Book III) — `*_djvu.txt` OCR derivative, fetched 2026-07-18 |
| File | `yonge-nd/concordance.json` (151 records `{book, chapter, start_section, exact}`) |
| SHA-256 (concordance.json) | `5b3b42b82805533642f0b053f75a7d6dcba02f908f5a79366fd4b71178ff6b` |

**Method.** Mayor prints Cicero's own chapter numerals inline in the Latin
text plus the traditional continuous section numbers, and every page's
running header states its own chapter-range/section-range coverage (e.g.
`LIB. I CAP. XL—XLII §§ 118—119.`). The concordance was built from
**touching-boundary** evidence only (when one page's header ends at chapter
X/section S and the immediately following page's header begins at the same
chapter X/section S, S is a directly witnessed anchor for chapter X) plus
the definitional chapter-1→section-1 anchor for every book; chapters
without a witnessed anchor are linearly interpolated (or, past a book's
last anchor, extrapolated at that book's average sections/chapter rate) and
marked `"exact": false`. Raw OCR critical-apparatus line numbers (which
reset every page) were deliberately excluded from evidence — they are
easily confused with the true continuous section numbers and produced
non-monotonic false positives when tried.

**Gate results.** Chapter 1 → section 1 holds by construction in every
book; section starts are strictly increasing within each book by
construction (only interpolated/extrapolated, i.e. `"exact": false`,
chapters were ever nudged to break a tie — no witnessed anchor was
adjusted). Final-chapter comparison against the book's known Ax maximum
(reported, not force-fit): Book 1 ch. 44 → section 125 vs. Ax max 124
(+1); Book 2 ch. 67 → section 166 vs. Ax max 168 (−2); Book 3 ch. 40 →
section 101 vs. Ax max 95 (+6 — Book 3's Mayor headers were the noisiest/
sparsest of the three, with several OCR-corrupted headers excluded from
evidence). See `sources/yonge-nd/README.md` for sample mappings and full
methodology detail.


---

## Cicero, *De Senectute* (Wave 2, `cato-maior-de-senectute`, flat 1–85),
*De Amicitia* (`laelius-de-amicitia`, flat 1–104), and *De Divinatione*
(`de-divinatione`, book.section 1:1–132 + 2:1–150) — one translator, three
works, three different Perseus TEI shapes

### PRIMARY — William Armistead Falconer, *Cicero: De Senectute, De
Amicitia, De Divinatione* (Loeb Classical Library 154, 1923) — sourced
from the **Perseus Digital Library**

| | |
|---|---|
| Translator | William Armistead Falconer (1869–1927) |
| Publisher | London: William Heinemann; Cambridge, Mass.: Harvard University Press |
| Publication year | 1923 (Loeb Classical Library 154); reprinted unrevised 1927, 1930, 1938, 1946, 1953, 1959, 1964, 1971 |
| US-PD rationale | Published 1923 — safely pre-1931, US public domain |
| Source | Perseus Digital Library / PerseusDL `canonical-latinLit` GitHub repo, `data/phi0474/phi051/` (De Senectute), `data/phi0474/phi052/` (De Amicitia), `data/phi0474/phi053/` (De Divinatione) |
| Pinned commit (all three files) | `1066a551aa5445ab165e9b490a6bb06ce72828da` (2026-06-23, "(review_work) phi0474 Cicero batch: … fixes to author and editor in headers" — the SAME header-metadata-only commit already pinned for Miller's De Officiis; independently confirmed 2026-07-18 via GitHub's commits-by-path API as each of these three files' own most recent touching commit) |
| Retrieved | 2026-07-18, via GitHub raw at the pinned commit |
| Files | `falconer-sen/phi0474.phi051.perseus-eng1.xml` (SHA-256 `44ba1e6d5059cbbf774ee43b0feeb64d670511db972cd7be11192f12c24af348`, 95,817 bytes) · `falconer-amic/phi0474.phi052.perseus-eng2.xml` (SHA-256 `b0c39a70e78e3d7363cabdc1832e8ca9de878a31ac6e13a18742aeda1d919069`, 121,142 bytes) · `falconer-div/phi0474.phi053.perseus-eng1.xml` (SHA-256 `c4edfe8598dc7ff504ab91d3f6ad4d40879056155c05f71ad18f4141d1891ce6`, 349,510 bytes) |
| Markup license | Perseus's own TEI/EpiDoc encoding; the underlying 1923 Falconer translation is independently US-PD by publication date |

**Edition-identity verification (triple witness, Rouse/Smith-trap
discipline, §5.2#3 of `docs/wave2-latin-design.md`).**

- **Each file's own teiHeader**: `<editor role="translator">William
  Armistead Falconer</editor>` in BOTH `titleStmt` and the sourceDesc's
  `biblStruct`, imprint "Cambridge / Harvard University Press; Cambridge,
  Mass., London, England / 1923", series "Loeb Classical Library". De
  Amicitia's sourceDesc additionally names the shared volume title "De
  Senectute De Amicitia De Divinatione, With An English Translation" and
  links to a SECOND, independent archive.org scan
  (`archive.org/details/desenectutedeami0000cice`).
- **archive.org `cicero-in-28-volumes.-vol.-20-loeb-154`** (fetched
  independently, a HathiTrust `uc1` capture — description field points to
  `https://hdl.handle.net/2027/uc1.32106005388308`): its own title page
  reads "DE SENECTUTE, DE AMICITIA, DE DIVINATIONE / WITH AN ENGLISH
  TRANSLATION BY WILLIAM ARMISTEAD FALCONER", imprint "LONDON WILLIAM
  HEINEMANN LTD / CAMBRIDGE, MASSACHUSETTS HARVARD UNIVERSITY PRESS", and
  its own printing-history statement: "First printed 1923 / Reprinted
  1927, 1930, 1938, 1946, 1953, 1959, 1964, 1971" (OCR misreads "1930" as
  "1980") — unrevised reprints across nearly half a century, the same "no
  known later revision" shape as Miller's De Officiis; this item's catalog
  metadata has no `possible-copyright-status` field set (unlike Miller's
  scan), but the 1923 publication date alone settles US-PD status under
  this project's pre-1931 rule regardless.
- **Incipit cross-check, all three works**: Perseus's own opening words
  verified verbatim identical against the archive.org scan's OCR text
  layer for each — De Senectute ("O Titus, should some aid of mine
  dispel..."), De Amicitia ("QUINTUS MUCIUS SCAEVOLA, the augur, used to
  relate..."), De Divinatione ("There is an ancient belief, handed down to
  us...").

**Three different TEI shapes in the same Perseus corpus.** Unlike Miller's
De Officiis (one shape, milestone-cursor per book), these three Falconer
files use three genuinely different encodings, each with its own extractor
function in `pipeline/tools/extract_falconer_perseus.py`:

1. **De Senectute** (`_extract_flat_milestone`) — a single flat
   `<div type="translation">` (no book subdivision) with inline
   `<milestone unit="section" n="...">` markers, Miller's per-book cursor
   shape with only one "book". **Confirmed data-entry bug**: the
   milestones run 1..85 but contain a DUPLICATE `n="35"` (fires twice)
   while `n="36"` never appears — cross-checked against the built PHI
   Latin spine (`app/dist/data/cato-maior-de-senectute/book-01.json`,
   sections 34–37 all present, 93–104 words each, so section 36 is
   genuinely substantial, not a short-sentence merge) and against the
   milestone content itself (the second `n="35"` fires mid-sentence;
   the next milestone after it is `n="37"`). Hand-verified single-entry
   fix table `_DUPLICATE_MILESTONE_FIX = {35: 36}` renumbers only that
   second occurrence; any other duplicate still raises `ValueError`.
2. **De Amicitia** (`_extract_section_divs`) — Hicks/Diogenes-shaped: each
   section is its OWN wrapping `<div type="textpart" subtype="section"
   n="1".."104">`, with NO `unit="section"` milestone anywhere in the
   file (only `unit="chapter"`, 27 occurrences, inside section divs,
   carrying no text). Confirmed 104 divs, document-order `@n` exactly
   1..104, no gaps or duplicates.
3. **De Divinatione** (`_extract_book_milestone`, called once per book) —
   Miller's exact shape: `<div subtype="book" n="1"|"2">` (correctly
   numbered, no Book-III-style `@n` bug this time) with inline
   `unit="section"` milestones. **Confirmed Perseus typo**:
   `<milestone unit="seciton" n="128"/>` (Book II) — "seciton" for
   "section", the ONLY `n="128"` milestone in Book II and the only number
   its correctly-spelled sequence is missing; treated as a real section
   boundary via a `milestone_units=("section", "seciton")` alias. **Declared
   gap**: Book I has NO `n="25"` milestone at all (131 of 132, no
   duplicate — `25` is simply absent from an otherwise-contiguous 1..132
   sequence). Cross-checked against the built PHI Latin spine
   (`app/dist/data/de-divinatione/book-01.json`: `1:1.24`=141 words,
   `1:1.25`=60 words, both present) and the English word count spanning
   Perseus's own milestones 24→26 (256 words, proportionate to the
   combined 201 Latin words) — strong evidence Falconer's English DOES
   contain section 25's content, folded into 24's span with no separate
   milestone, the same shape as Miller's 2:2.90 gap. UNLIKE that case,
   there is no self-evident single-sentence splice point recoverable from
   the English alone, so this gap is left DECLARED (`1:25` absent from
   output) rather than guessed at — **needs an
   `alignment_allow_unmatched: ["1:1.25"]` manifest entry at the alignment
   stage, out of this extraction script's blast radius; follow-up flagged
   here**.

**Cleaning conventions** (full detail, including every element class and
its handling, in the extractor's module docstring and each work's
`README.md`): `<note>` (all untyped, no `type="marg"` split like Miller's
De Officiis) dropped whole. `<bibl>` (De Senectute 2, De Amicitia 1, De
Divinatione 5 — all siblings of a verse `<quote rend="blockquote">` inside
a `<cit>` wrapper) ALSO dropped whole even when not wrapped in `<note>` —
verified against the archive.org scan that these attributions print as
numbered footnotes, not running prose. `<foreign xml:lang="greek">`
(Beta-Code-like ASCII): De Senectute needs no decode table at all (all 8
occurrences sit inside dropped notes); De Divinatione needs 9 hand-verified
entries (μαντική, δαιμόνιον, εἱμαρμένη, ψευδόμενον, ὁρίζοντες, λήμματα,
πρόσληψις, συμπάθεια ×2 — all standard divination/logic technical terms,
9 of 29 occurrences sit in running body text, the rest in dropped notes).
De Amicitia uses a DIFFERENT lang tag, `xml:lang="grc"` (already-Unicode
Greek, not Beta Code) — all 7 occurrences corpus-verified to sit inside
dropped notes, guarded by a dedicated assertion so this fact can't rot
silently. `<foreign xml:lang="lat">` (De Amicitia only, 4 body
occurrences: untranslated Latin terms like "toga virilis," quoted inline
in the English) passed through as plain text. `<quote>` (non-blockquote)
and, De Amicitia only, `<q>` of any `@type` wrapped in curly quotes by
nesting depth; `<quote rend="...blockquote...">` (verse) passes through
unmarked — including one De Amicitia edge case, `<quote type="blockquote">`
(attribute is `@type` not `@rend`), confirmed against the archive.org
scan to print WITH quotation marks (a regular quote), which Miller's
`@rend`-only verse check already handles correctly by construction.
`<hi>`, `<emph>`, `<title>`, `<l>`, `<said>`/`<label>` (De Amicitia's
dialogue markup) all plain pass-through, no markup added.

### Stage-1 extraction

All three works extracted by `pipeline/tools/extract_falconer_perseus.py`
(SHA-256 `462372d1592ba040496e363731560d41fe9ed76e544764e19abf35de8455996a`),
which reads all three pinned Perseus XML files straight from
`sources/falconer-{sen,amic,div}/` (hashes above, verified before every
run) — same "download once, verify the hash, read locally" shape as
`extract_miller_perseus.py`. Outputs (record shape `{"section": n,
"text": "..."}`, or `{"book": b, "section": n, "text": "..."}` for De
Divinatione):

| Work | File | Records | SHA-256 |
|---|---|---|---|
| De Senectute | `falconer-sen/falconer.clean.json` | 85/85 | `536f98e6a77cc2ddc249516857798cf5c47eff689ae66e89f218e5f7f5897d07` |
| De Amicitia | `falconer-amic/falconer.clean.json` | 104/104 | `031378d8823da088d655ba62783f508ede356bf3800a814a27cccbfb5a6d7fa5` |
| De Divinatione | `falconer-div/falconer.clean.json` | **281/282** (declared `1:25` gap, see above) | `fd3758a2ea8f9529e20c68fd04b5b8528bf3e40aab1a30963262f22a957dcc41` |

Restated unambiguously for the hash-verification gate: `sources/falconer-sen/falconer.clean.json` (SHA-256 `536f98e6a77cc2ddc249516857798cf5c47eff689ae66e89f218e5f7f5897d07`); `sources/falconer-amic/falconer.clean.json` (SHA-256 `031378d8823da088d655ba62783f508ede356bf3800a814a27cccbfb5a6d7fa5`); `sources/falconer-div/falconer.clean.json` (SHA-256 `fd3758a2ea8f9529e20c68fd04b5b8528bf3e40aab1a30963262f22a957dcc41`).

**Gate results.** Record counts exact for De Senectute and De Amicitia;
De Divinatione is 281 of the expected 282 (the single declared `1:25`
gap — not silently absorbed into a passing claim). All three: sequences
strictly increasing with no OTHER gaps or duplicates, zero empty records,
zero high-Latin-density records (automated sweep), zero stray Beta-Code
artifacts, deterministic double-run (byte-identical output across two
runs). 5-section-per-work spot-check against the archive.org OCR scan
(word-overlap fuzzy comparison) found no genuine content discrepancies —
two initial low-similarity flags (De Amicitia §75/§104, De Divinatione
1:131) were automated-matcher false positives (common opening phrases
recurring elsewhere in the volume caused the matcher to lock onto the
wrong occurrence), each manually re-verified correct by direct text
search. `PATCHES.json` is deliberately absent in all three source dirs —
no genuine transcription defect was found (the one confirmed anomaly,
De Divinatione's `1:25`, is a missing-milestone structural gap, not a
text error, and is therefore declared rather than patched); the
exact-once mechanism is wired in for future use, same convention as
`sources/munro-drn/`.

**Follow-up needed, out of this extraction's blast radius**: a
`manifests/de-divinatione.yaml` `alignment_allow_unmatched: ["1:25"]`
entry (Miller-2:2.90-shaped) to let the alignment stage accept the
declared gap.

## Cicero, *De Finibus Bonorum et Malorum* — INCOMPLETE, NOT WIRED IN

### SLOT-A (future) / SECONDARY (current) — H. Rackham, *Cicero: De Finibus Bonorum et Malorum* (Loeb
Classical Library, 1914), sourced via archive.org OCR (`_djvu.xml`
word-level); SECOND WITNESS — Loebolus L040 PDF (image scan, no text
layer)

| | |
|---|---|
| Translator | H. Rackham, M.A., Fellow and Tutor of Christ's College, Cambridge |
| Publisher | London: William Heinemann; New York: The Macmillan Co. |
| Publication year | 1914 ("MCMXIV" on title page) — first edition, NOT Perseus's 1931 second edition |
| US-PD rationale | Published 1914, decades pre-1931 — safely US public domain |
| Primary source | archive.org, identifier `CiceroRackhamDeFinibusBonorumEtMalorum` |
| Primary file used | `CiceroRackhamDeFinibusBonorumEtMalorum_djvu.xml` (word-level XML, not the flat `_djvu.txt`), SHA-256 `6095d38a06e5bf91daebe7160ca89ad13e1de06020cc60d89b347cc87c5e4285` — staged at `build/rackham-fin/` (untracked; raw scan text is not committed per this task's brief) |
| Second witness | Loebolus L040 PDF, `https://ryanfb.xyz/loebolus-data/L040.pdf`, SHA-256 `1b6573c13bb8d04546724e742d7c491ec6b462c57a8fd1e713c4b62ee8b206cc` (image-only scan, no embedded text — proofing done by rendering pages to PNG and reading the image, not by re-OCRing) |
| Extraction tool | `pipeline/tools/extract_rackham_fin.py` (page-side classification by English/Latin stopword vote, LCS-based section-marker recovery, footnote/marginal-gloss cleanup — see script docstring) |
| Output | `rackham-fin/rackham.clean.json` — **368 of the required 443 records (83%)** |
| Output SHA-256 | see restated line below |
| Tests | `pipeline/tests/test_extract_rackham_fin.py` (offline, pure functions) — all pass |

Restated unambiguously for the hash-verification gate:
`sources/rackham-fin/rackham.clean.json` (SHA-256 `658ce29375a600249a21ee9dcd21c7b8e3639ce63bf066ffd0b64be49ba04733`).
The primary-file and second-witness hashes in the table above are provenance
records for EXTERNAL/untracked inputs (archive.org djvu XML staged under
`build/`, Loebolus PDF) — the hash gate correctly skips them as having no
repo path; the two "ambiguous hash" warnings on those lines are expected.
| PATCHES.json | Present but empty — confirmed defects found during proofing are OCR/extraction-pass problems, not print-level errata in the original, so patching them here would paper over a systematic issue rather than record a genuine transcription fix |

**Status: DO NOT WIRE INTO THE READER.** Full detail, gap table, and the
proofing-pass findings (confirmed content defects including at least one
case of real translated-text loss, at a rate well above the ~1
error/section stop-condition) are in `rackham-fin/README.md`. Summary:
75 of 443 section markers are not recoverable from this OCR pass (10 in
Book 1, 6 each in Books 2–4, 47 in Book 5 — Book 5's gap rate reflects a
systematic tens-digit OCR misread pattern in that portion of the scan,
not a tunable extractor bug); this edition's marginal "argument" glosses
bleed into the body-text OCR stream with no reliable geometric separator
in this particular scan, and the lexical filter that catches the
worst-garbled gloss fragments does not catch all of them. Perseus's
`canonical-latinLit` and en.wikisource.org were both checked and do not
have this translation (Wikisource only links out to the Loebolus scan) —
archive.org OCR is the only currently available source. Recommend either
a layout-aware re-OCR pass with full 443-section proofing, or revisiting
with more time/a different tool, before this enters the build.

### CURRENT — C. D. Yonge, *De Finibus, a Treatise on the Chief Good and
Evil*, in *The Academic Questions, Treatise De Finibus, and Tusculan
Disputations* (George Bell & Sons, 1891), sourced from **Wikisource's
human-proofread transcription** — phase 1 (source acquisition + clean
extraction) only, 2026-07-24. John's ruling: "use Yonge for now" — Rackham
1914 above becomes slot-A later once its OCR-recovery gap is cleared;
until then this is the only usable English channel for this work.

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891) |
| Printing | George Bell & Sons, London, 1891 |
| US-PD rationale | Published 1891, translator d. 1891 — safely pre-1931, US public domain |
| Primary source | en.wikisource.org, transcluded from `Index:The academic questions, treatise de finibus, and Tusculan disputations.djvu`, subpages `/Book 1`…`/Book 5` (djvu pages 134–322, five `<section begin="dfN"/>`/`<section end="dfN"/>`-delimited books) |
| Proofreading status | **All 189 pages spanning the De Finibus books are ProofreadPage quality level 3 ("Proofread"), single proofreader "Pasicles"** — verified programmatically against every page, not sampled |
| Extraction tool | `pipeline/tools/extract_yonge_finibus.py` (pinned-revision Wikisource fetch, page-seam soft-hyphen joins, book-heading/chapter-marker segmentation, declared ellipsis-template normalization — see script docstring) |
| Output | `yonge-finibus/yonge.clean.json` — 138 of 138 chapter records (5 books: 21, 35, 22, 28, 32 chapters; Book 2's chapter I carries no roman-numeral marker in the print itself, synthesized from its un-numbered leading span — see README) |
| Output SHA-256 | `39061f838b53711bedf26d29ed34370bfac45eeee5857d78e081a782db2d7d42` |
| Tests | `pipeline/tests/test_extract_yonge_finibus.py` (offline, pure functions, 32 tests) — all pass |
| PATCHES.json | Present but empty — no print-level errata found, none expected given the transcription's own proofread status |

**Status: NOT WIRED IN (phase 1 only).** 80,228 words / 439,314 characters,
zero OCR-defect-class anomalies found in a full-output programmatic scan
(stray footnote-digit glue, double spaces, unexpected non-ASCII — none
found; Greek is native Unicode from the proofread transcription, not
OCR-garbled). Full detail in `yonge-finibus/README.md`. **Not in this
phase's scope**: the chapter→PHI-Latin-section concordance (phase 2,
required before this can be wired into a `manifests/de-finibus.yaml`) and
any site wiring (phase 3).

## Cicero, *De Fato* ("On Fate") — chapter-keyed translation channel +
chapter→section concordance (alignment key for the `de-fato` flat Latin
spine, sections 1–48). Wired into `manifests/de-fato.yaml`'s `english`
block (`model: chapter_concordance`) and `shared/lib/works.ts`'s
`translations` entry, 2026-07-21.

### PRIMARY — C. D. Yonge, *On Fate*, in *The Treatises of M. T. Cicero*
(H. G. Bohn, 1853; G. Bell reprint, 1878), sourced from **archive.org OCR**

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891) |
| First printing | H. G. Bohn, London, 1853 |
| Working-OCR printing | G. Bell, London, 1878 (same plates as 1853 — see letter-identity check below) |
| US-PD rationale | Published 1853/1878, translator d. 1891 — safely pre-1931, US public domain (Rackham's 1942 Loeb is the only other English *De Fato* and is still in US copyright — Yonge is the ONLY PD option) |
| Primary source | archive.org, identifier `treatisesofcicer00ciceuoft` (1878), `_djvu.txt` flat OCR |
| Primary file | `treatisesofcicer00ciceuoft_djvu.txt` — staged at `build/yonge-fato/` (untracked; raw scan text is not committed), 1,457,332 bytes, 27,302 lines, SHA-256 `c269f19a3bad6d15e8f9b707e522b756a0237f6026b619afc6940683c7af8284` |
| Second witness (proofing) | archive.org, identifier `treatisescicero00ciceuoft` (1853 first printing) — all 19 printed pages (264–282, all 20 chapters) fetched as page images and read directly, not re-OCR'd |
| Extraction tool | `pipeline/tools/extract_yonge_fato.py` (anchor-based span slicing, apparatus/footnote stripping, chapter segmentation, declared OCR-fix tables — see script docstring) |
| Output | `yonge-fato/yonge.clean.json` — 20 of 20 chapter records (complete, no gaps) |
| Output SHA-256 | see restated line below |
| Concordance | `yonge-fato/concordance.json` — 20 of 20 chapters content-anchored to the 1–48 Latin section grid (none interpolated) |
| Concordance SHA-256 | see restated line below |
| Tests | `pipeline/tests/test_extract_yonge_fato.py` (offline, pure functions) — all pass |
| PATCHES.json | Present but empty — no print-level errata found; all confirmed defects (127 across 7,792 words: 126 found in the original proofing pass + 1 found post-commit by the Grok content gate, 2026-07-21) are this OCR pass's own artifacts, hand-fixed via cited, image-verified substitution tables, never a case of lost/unrecoverable translated text |

Restated unambiguously for the hash-verification gate:
`sources/yonge-fato/yonge.clean.json` (SHA-256
`ae74b5e9f254c9f1101f86b41ddf2a55b06dfda3ab70fd27e0c1cfa00d3491b2`;
prior hash `2095df7ba88e2bad…` superseded 2026-07-24 by the declared
asterisk→ellipsis normalization — see `yonge-fato/README.md` "Declared
normalizations"; that hash itself superseded `d9f13e5f380ba8f9…` on
2026-07-21 for the one-character ch. 7 `0 Chrysippus` → `O Chrysippus`
emendation).
`sources/yonge-fato/yonge-sections.clean.json` (live build attachment;
SHA-256 `f4650658c4029c81000dbb50e75beeb064c52af197d1d30128299da53875b26e`;
prior `9f944cc97979c1da…` superseded 2026-07-24 by the same asterisk
normalization plus one orphaned trailing section-break dash removal —
see README).
`sources/yonge-fato/concordance.json` (SHA-256
`db47c00c5cec2f724f816771638db5ba95abb4ee553e4f54c0efa39d740f59a7`).
The primary-file hash in the table above is a provenance record for an
EXTERNAL/untracked input (archive.org djvu text staged under `build/`) —
the hash gate correctly skips it as having no repo path.

**1853/1878 letter-identity**: confirmed same plates — see
`yonge-fato/README.md`'s dedicated section (full 20-chapter check, not
just the requested 3).

**Proofing pass**: full-page-image comparison of all 19 pages / all 20
chapters (exceeding the brief's first/last-sentence-plus-5-chapters
minimum). 127 defects found and fixed (126 in the original proofing pass
+ 1 found post-commit by the Grok content gate, 2026-07-21; ≈1 per 61
words) — all single-token OCR-layer slips (dropped line-wrap hyphens being
the largest category, 75 of 127), zero print-level errata, zero
lost/unrecoverable text, zero marginal-content contamination. Judged
against the brief's stop condition
and NOT stopped: every defect was mechanically correctable against the
clean 1853 scan image, unlike the Rackham *De Finibus* precedent above
(gloss contamination + genuine translated-text loss). Full defect table
and category breakdown in `yonge-fato/README.md`.

**Greek restorations**: 4 terms (ἀξιώματα, θεωρήματα, ἐλάχιστος, ἀργὸς
λόγος), each hand-verified against the 1853 page image AND independently
cross-checked against the PHI Latin spine's own embedded Greek
(`build/dist/de-fato/book-01.json` carries the identical terms in
Cicero's Latin) — a double witness. No unrecognized Greek-looking garble
remains.

**Concordance methodology**: direct philological comparison of each
English chapter's opening sentence against the PHI flat Latin spine's 48
sections (Mueller 1890 Teubner text) — Rackham's English was never
consulted. All 20 mappings are content-anchored (a literal, quoted
matching sentence in both languages); none interpolated. Gates: chapter
1 → section 1; strictly increasing (1, 3, 5, 7, 9, 11, 13, 15, 17, 20,
23, 26, 29, 31, 33, 36, 39, 41, 43, 46); chapter XX (section 46) runs
through the end of section 48, confirmed by both languages independently
ending with the same trailing-lacuna convention. Full per-chapter anchor
table in `yonge-fato/README.md`.

## Seneca, *Ad Lucilium Epistulae Morales* (work `epistulae-morales`,
`letter` scheme, 124 letters) — English channel wired in

### PRIMARY — Richard M. Gummere, *Ad Lucilium Epistulae Morales* (Loeb
Classical Library, 3 vols.: I 1918/repr. 1925, II 1920, III 1925), sourced
via Wikisource

| | |
|---|---|
| Translator | Richard Mott Gummere (1883–1969) |
| Publisher | London: William Heinemann; New York: G. P. Putnam's Sons |
| Vol. I (Letters 1–65) | archive.org `adluciliumepistu01seneuoft` — THIS scan's own title page (leaf 9, directly viewed via IIIF) carries the REPRINT date MCMXXV (1925), not 1918; its own verso (leaf 10) reads "First Printed 1918. / Reprinted 1925." (no revision language) — the work was first printed 1918, this scanned copy is the unrevised 1925 reprint |
| Vol. II (Letters 66–92) | archive.org `adlucilium02sene` (UCLA/CDL scan) — title page MCMXX (1920); **title-page verso directly inspected as page images and confirmed BLANK — no printing-history statement of any kind in this specific scan** (a sibling copy, `senecaadlucilium0002gumm`, shows "First printed 1920. Reprinted 1930, 1953", but that wording does not appear on the pages actually used here); full-OCR grep for "first printed\|reprint\|revised\|copyright" returns zero matches |
| Vol. III (Letters 93–124) | archive.org `adluciliumepistu03seneuoft` — title page MCMXXV (1925); no printing-history line found in the OCR (first printing) |
| US-PD rationale | All three volumes first published 1918/1920/1925 — safely pre-1931, US public domain; archive.org's `NOT_IN_COPYRIGHT` field on Vol. II is not relied on alone per CLAUDE.md's Canada-only caveat — the verified absence of any revision language on the title-page verso is the load-bearing evidence |
| Source | Wikisource, "Moral letters to Lucilius/Letter 1" .. "/Letter 124" (en.wikisource.org), fetched via `action=parse&prop=text` (rendered HTML, letting ProofreadPage's own `<pages>` transclusion resolve page-seam joins) |
| Underlying scan quality | 780 transclusion occurrences across 688 distinct `Page:` subpages are ProofreadPage quality 3 "Proofread" (778 occurrences / 687 distinct) or 4 "Validated" (2 occurrences / 1 distinct) — zero below quality 3; every page's own `data-page-quality` is declared and checked in `gummere.integrity.json` (below) |
| Extraction tool | `pipeline/tools/extract_gummere_wikisource.py` |
| File | `gummere-epistulae/gummere.clean.json` (2,139/2,140 letter.section columns — one declared gap, see below) |
| Integrity manifest | `gummere-epistulae/gummere.integrity.json` — declared per-letter rendered-HTML sha256 + per-page `data-page-quality`, checked bidirectionally on every rerun (missing or mismatched is fatal) |
| Tests | `pipeline/tests/test_extract_gummere_wikisource.py` — offline unit tests of the walker/allowlist/merge-invariant/integrity-manifest logic on synthetic fixtures, plus one end-to-end byte-identical regression test against the real pinned cache (skipped when the untracked cache is absent) |
| PATCHES.json | Deliberately absent — no genuine transcription defect found during the 14-letter spot-check |

Restated unambiguously for the hash-verification gate:
`sources/gummere-epistulae/gummere.clean.json` (SHA-256
`38e05c34afd45041d79233031a0f0aec1f1025de0a0a57051d8428634e6b15aa`);
`sources/gummere-epistulae/gummere.integrity.json` (SHA-256
`623d8c99ace3ebbf7ebb15275758dc44d60969701db8bb334c4d5aacfe3b7126`).

**Gate results.** 2,139 of the expected 2,140 letter.section columns —
one declared gap (Letter 108's Latin section 39 has no separately-numbered
English counterpart; see `manifests/epistulae-morales.yaml`'s
`alignment_allow_unmatched` and the extractor's own module docstring for
the cross-checked word-count-proportionality justification). Every
letter's own section-number sequence strictly contiguous from 1 (after a
single declared merge-fix in Letter 41, folding an extra Hense-edition
marker onto the Latin spine's own final section, now asserted exact-once
— see below). Zero empty records, zero un-stripped HTML/entity residue,
zero duplicate section numbers (both re-checked a second time after
`PATCHES.json` application). Only the exact tag/class shapes verified
present in the real corpus may pass through as prose inside
`prp-pages-output`; anything else (e.g. an injected banner element) is
fatal. Deterministic double-run (byte-identical output against the warm
local fetch cache, itself now validated for completeness — atomic writes,
envelope/terminal-anchor checks — before every parse, per a GPT-5.6-Sol
adversarial-review finding that a truncated cache file previously passed
silently).

**Two declared per-letter numbering exceptions** (both genuine Hense-1898-
vs-Reynolds-1965 edition differences, cross-checked via a corpus-wide
per-section English/Latin word-count ratio sweep — 2,093 one-to-one
section pairs, median ratio 1.76, zero outliers besides these two
letters): Letter 41 (Gummere's English splits the Latin spine's single
final section into two markers — merged back to one by the extractor,
`_MERGE_TAIL`) and Letter 108 (Gummere's English merges the Latin spine's
final two sections into one — left as a declared manifest-level gap, not
fabricated). Full analysis in `pipeline/tools/extract_gummere_wikisource.py`'s
module docstring and `gummere-epistulae/README.md`.

**Spot-check vs. archive.org OCR**: 14 letters spread across all three
volumes (6/4/4), each verified by locating a distinctive phrase from the
extracted text in that volume's own OCR full text. 14/14 confirmed
matches — 11 by direct normalized-substring hit, 3 verified manually where
the automated probe phrase happened to straddle an OCR misreading (in
each of those 3 cases the OCR, not the Wikisource transcription, is what's
wrong — confirmed by reading the surrounding OCR context directly: OCR
"CoNTHrui" for Wikisource's correct "Continue" in Letter 1, and OCR
"Claraiius" for Wikisource's correct "Claranus" in Letter 66). No genuine
content discrepancies found. Full table in `gummere-epistulae/README.md`.

## Plato, source-passage English for DK testimonia/fragments columns
(`sources/perseus-plato/`, docs/plato-locus-resolver-design.md, Phases 1–2)

DK's testimonia/fragments spines for six presocratic/sophist works quote
Plato in free text inside the Greek context line (no structured locus
anywhere in our data) — 39 columns across `prodicus-testimonia`,
`gorgias-testimonia`, `hippias-testimonia`, `critias-testimonia`,
`protagoras-testimonia`, and `philolaus-testimonia`, citing 18 distinct
dialogues. Full census, citation-grammar table, and the reuse-not-fork
design rationale are in `docs/plato-locus-resolver-design.md`; this entry
records only the vendoring.

| | |
|---|---|
| Translators | Fowler (1914–1926), Lamb (1924–1927), Bury (1929) — all pre-1931, safely US public domain; see the design memo §2.2 for the per-dialogue table |
| Source | PerseusDL `canonical-greekLit`, `data/tlg0059/tlg<NNN>/tlg0059.tlg<NNN>.perseus-eng2.xml`, one file per dialogue |
| Vendoring path | Copied (not re-fetched) from the sibling `plato-reader` repo's already-verified, already-patched local copies at `~/Developer/plato-reader/sources/perseus-eng/` (read-only there — never edited from this repo) |
| Per-file SHA-256 | `sources/perseus-plato/SHA256SUMS`, verified against the identical hashes recorded in that sibling repo's own `sources/perseus-eng/SHA256SUMS` |
| Markup license | Perseus's own TEI/EpiDoc encoding is CC BY-SA 4.0 (per that repo's own `INVENTORY.md`) — same posture already accepted for `sources/hicks-dl/`; the underlying Loeb-era translations are independently US-PD by publication date |
| Dialogues vendored (18 of 36) | Apology, Charmides, Cratylus, Euthydemus, Gorgias, Hippias Major, Hippias Minor, Laches, Lysis, Meno, Phaedo, Phaedrus, Philebus, Protagoras, Sophist, Symposium, Theaetetus, Timaeus — exactly the dialogues the census found cited; **not** vendored: Republic, Laws, Letters (not cited by any column, and Republic's Shorey translation is the one Perseus Plato text this project would have had to argue about on copyright) |
| Extractor | `pipeline/tools/extract_plato_perseus.py` — flat per-page-div walk, `<milestone unit="section" n="...">` cursors keyed directly (the `n` token already IS `<page><letter>`, e.g. `"281a"`); `<note>`/`<bibl>` dropped whole, everything else passes through as running prose |
| Store | `sources/perseus-plato/plato-stephanus.clean.json` — one flat `"<slug>:<page><letter>"` → text map, all 18 dialogues together, 4,003 keys total |
| Resolver | `stage1_context_english.py`'s `_resolve_plato` / `_PLATO_DIALOGUES` / `_RESOLVERS` — reuses the Diogenes Laertius mechanism unchanged; see the design memo §5 for why reuse rather than fork |

**Two vendored-file key-count deltas from the design memo's own census
table, both explained, not extraction bugs**: Protagoras yields 265 keys
(memo cites 264) and Symposium yields 257 (memo cites 256). Both dialogues'
vendored XML already carries a hand-applied patch (see the sibling repo's
`sources/perseus-eng/PATCHES.md`) adding one previously-missing Stephanus
milestone each (Protagoras `332c`, Symposium `181b`) — the memo's counts
predate those patches even though the patched files were what got copied.
Confirmed directly: both `protagoras:332c` and `symposium:181b` are present
and non-empty in the built store. Theaetetus yields 343 keys against the
sibling's documented 344 section milestones — the expected -1, since one of
those 344 is the non-numeric `n="imbedded dialogue"` structural marker the
extractor correctly ignores as a boundary. Apology (125), Hippias Major
(119), Hippias Minor (67), Gorgias (404), and Timaeus (364) all match the
memo's cited counts exactly.

**Phase 1 sidecar authored**: `sources/hippias-testimonia/context-english.json`
declares three columns — `1:A4` (Apology 19e), `1:A6` (Hippias Major 281a),
`1:A8` (Hippias Minor 363c–364a). The remaining 36 cited columns across all
six works are Phase 3 (hand-authoring, dispatched separately — needs Greek
judgment per dialogue, not done here).

**One finding for the record, resolved by cross-reference, not guessed**:
`hippias-testimonia` `1:A8`'s DK Greek context line literally reads
"...νῦν δὲ τὴν Σωκράτους ἐρώτησιν φύγοιμι ... 346 A ἐξ οὗ γὰρ ἦργμαι
Ὀλυμπίασιν ἀγωνίζεσθαι..." — but Hippias Minor's own Stephanus range is
363–376; page 346 does not exist in this dialogue. The quoted Greek
("since I began competing at Olympia, I have never met a better man than
myself") was located verbatim in Perseus's Hippias Minor English at
**364a** ("Naturally, Socrates, I am in this state: for since I began to
contend at the Olympic games, I never yet met anyone better than myself in
anything"), immediately following where the 363c–d excerpt leaves off (no
intervening Hippias-minor content is skipped past 363d before 364a) —
strongly indicating "346" is a digit-transposed typo in DK for "364", not
a citation to a different work. The Phase 1 sidecar records this as the
single contiguous range `363c-364a` rather than inventing a second
context_span at a locus that would not resolve against any vendored
dialogue.

---

## Epicurus — Cyril Bailey, *Epicurus: The Extant Remains* (1926)

### PRIMARY — Cyril Bailey, *Epicurus: The Extant Remains* (Oxford: Clarendon
Press, 1926) — sourced from an archive.org OCR text layer (no clean
scan-backed transcription was found; see the OCR-quality note below)

| | |
|---|---|
| Translator | Cyril Bailey (1871–1957) |
| Publisher | Oxford: Clarendon Press |
| Publication year | 1926 |
| US-PD rationale | Published 1926, pre-1931 — safely US public domain |
| Witness | archive.org item `EpicurusTheExtantRemainsBaileyOxford1926_201309` |
| Witness URL | https://archive.org/details/EpicurusTheExtantRemainsBaileyOxford1926_201309 |
| File used | that item's tesseract OCR text layer (`_djvu.txt`), downloaded and vendored verbatim |
| Vendored copy | `sources/bailey-epicurus/bailey-extant-remains-1926.djvu.txt` |
| Retrieved | 2026-07-28 |
| SHA-256 | `50924207cdee3361c00aabd8d4fdfb443e022e912958e2f1f43ab2c4aebbd55f` |
| Size | 1,305,909 bytes (26,140 lines) |

**Why an OCR text layer, not a clean transcription.** Unlike Hicks/DL
(Perseus TEI) or Haines/Meditations (Wikisource ProofreadPage), no
scan-backed proofread digitization of this specific edition was located.
The archive.org tesseract text layer is the rawest possible source: a flat,
single-pass OCR of the physical page images, with no paragraph/column
awareness and no post-OCR cleanup.

**Bilingual facing-page layout, OCR'd flat.** Bailey's edition sets Greek
and English on facing pages (Greek verso, English recto — same convention as
the Haines Loeb Meditations, see `extract_haines.py`), each page also
carrying a critical apparatus and, on the English page, a narrow marginal
synopsis column. The OCR reads all of this in physical scan order with no
structural markers. Unlike Haines, though, this OCR pass preserved the Greek
in real Greek-script Unicode rather than transliterating it into Latin-
alphabet noise — surveyed at ~44% Greek-script lines in the Letter to
Herodotus's own line range, with corrupted running heads and no form feeds.

**Extraction**: `pipeline/tools/extract_bailey_epicurus.py`. Architecture
follows `extract_haines.py` (block-level script filtering, hand-verified
`PATCHES.json` for residual slips, anchor extraction on section numbers) —
see that tool's own module docstring for the full defect-by-defect account
(Greek-Unicode line filter, all-caps running-head filter, decimal anchors
for the three Letters' DL section numbers, roman-numeral anchors with
homoglyph repair for the Principal Doctrines and Vatican Collection,
cross-reference-only Vatican Collection sayings recorded as explicit
skips with raw-OCR evidence, never guessed text).

**Coverage, as actually extracted (2026-07-29 run against the SHA above, after
the Grok verification-gate fixes: isolated-Greek-garble tolerance, hyphen-break
and short-terminal-line continuation, bracketed/compound-range roman-numeral
anchors, a Greek-mixed crossref-numeral fallback, and a hard sentence-boundary
merge cap — see `extract_bailey_epicurus.py`)**:

| Part | Extracted | Expected | Note |
|---|---|---|---|
| Letter to Herodotus | 12 | 49 (DL §35–83) | see finding below |
| Letter to Pythocles | 8 | 33 (DL §84–116) | see finding below |
| Letter to Menoeceus | 2 | 14 (DL §122–135) | see finding below |
| Principal Doctrines | 38 | 40 (I–XL) | 2 gaps, OCR too corrupted to recover (see `meta.json`) |
| Vatican Collection | 68 (66 singly-keyed sayings + 1 compound key, "56-57", covering 2) | 81 (I–LXXXI) | 13 confirmed cross-reference-only (no independent English text — see below); 0 further gaps, every expected saying now accounted for |

**Finding, verified not assumed: Bailey's own edition does not print every
DL section number in the English translation column.** The brief's
expectation (≥45/49 Herodotus, ≥30/33 Pythocles, ≥13/14 Menoeceus) assumed
a Haines-style one-number-per-break convention. Direct line-by-line
verification of the Letter to Herodotus shows this is not how this edition
is set: DL sections 37–42 (six consecutive sections) carry **no digit
token anywhere in the English OCR text, on any line** — confirmed by
grepping the full Herodotus line range for `\b37\b` … `\b42\b`; every hit
is either on a Greek-script line, in the Latin critical apparatus, or a
bare page-bottom page number, never attached to English prose. The
matching Greek page prints all six numbers. This is the source's own
translation convention (several consecutive Usener/von der Muehll section
breaks fall inside one continuous English sentence or paragraph, and
Bailey's translation does not force a marker at each one) — not an OCR
failure and not a tool defect. The extractor therefore cannot recover a
number that was never printed; per the honesty rule the brief itself sets
("a missing/damaged section becomes an absent key plus a meta.json gap
entry, not a guess"), these are recorded as gaps, not fabricated. Text
between two found anchors is merged into the earlier one (there is no
evidence for where exactly, within that span, each individual unmarked
section would begin) up to a 6,000-character cap (`_MAX_MERGE_CHARS`) —
past that, attributing yet more text to an increasingly-stale number
would be actively misleading rather than merely incomplete, so the
excess is left out of the store entirely instead. The same sparse-
numbering pattern holds across all three Letters (Pythocles' own opening
section, §84, carries no digit at all; Menoeceus is similarly sparse). The
Principal Doctrines and Vatican Collection do not share this problem —
each doctrine/saying there IS its own numbered unit by design, which is
why their coverage is far higher.

**Vatican Collection cross-reference-only sayings** (no independent
English text: the manuscript itself cross-references a Principal Doctrine
instead, e.g. "VI. = Κύριαι Δόξαι XXXV."): confirmed items 1, 2, 3, 5, 6,
8, 12, 13, 20, 22, 49, 50, 72 — each recorded in `meta.json` with its raw
OCR line as evidence, found by a dedicated pre-Greek-filter scan
(`_scan_vs_crossrefs`) since the cross-reference line is itself Greek
script and would otherwise vanish silently under the same filter that
drops all other Greek text. Saying 72's own crossref line is damaged
badly enough (Greek-script numeral lookalikes and a merged-doubled-I
accent glyph in the same token) that a dedicated fallback matcher was
needed to recognise it at all — without it, Saying 73's own numeral got
fuzzily misread as a damaged reading of 72, misfiling 73's text under key
"72" (fixed 2026-07-29; see `_VS_CROSSREF_FALLBACK`).

**Vatican Collection compound saying 56-57**: printed by Bailey under a
single inline "LVI-LVII." anchor spanning two numbers at once (Arrighetti's
numbering agrees there is no independent saying at either 56 or 57);
recorded under its own store key, `"56-57"`, with `meta.json`'s
`vs.compound_sayings` recording `{"key": "56-57", "covers": [56, 57]}` so
downstream numbering can align it.

**Known, disclosed limitation — marginal synopsis contamination.** Bailey's
printed page carries a narrow marginal column of short topic labels
beside the main translation (e.g. "Introduction:", "Methods of
procedure,"). The flat OCR interleaves fragments of that column into the
same line as the main prose, mid-sentence (e.g. Herodotus §35: "...to work
in detail Zntroduction : through all that I have written..." — "Zntroduction
:" is the marginal label, OCR-glued in). There is no reliable per-line
signal in the bare OCR text to separate the two columns (both are ordinary
English word fragments, unlike the Greek/English split, which has a clean
script-based signal) — attempting to strip these algorithmically risks
deleting real translated words. The extractor makes no attempt to remove
them; the output is faithful to the OCR otherwise. Recorded verbatim in
`meta.json`'s `known_limitations`, not silently left unclean.

**Spot-checked passages** (byte-readable, content faithful to Bailey's
prose): Letter to Herodotus §35 ("For those who are unable, Herodotus, to
work in detail through all that I have written about nature...");
Principal Doctrine IV ("Pain does not last continuously in the flesh, but
the acutest pain is there for a very short time..."); Vatican Collection
saying 4 ("All bodily suffering is negligible: for that which causes acute
pain has short duration...").

**Determinism**: `extract_bailey_epicurus.py` is a pure function of the
vendored bytes (no network, no timestamps); verified by running it twice
and byte-comparing all four output files — see
`pipeline/tests/test_extract_bailey_epicurus.py::test_end_to_end_is_deterministic`.

**Second verification gate (2026-07-29, Grok), fixed via the tool's own
mechanisms — no extracted/expected counts changed, content only.** (1) The
Letter to Pythocles' own 107/108 section boundary fell literally inside one
word ("...a process most fre-" / "108 quent in the atmosphere..." — raw OCR
lines 3993/4010: Bailey's own page break, not an OCR artifact); resolved to
the nearest word edge (`_resolve_anchor_mid_word`), never left mid-word.
(2) A digit/letter homoglyph — "1" glued onto "s"/"n"/"t"/"f" with no space,
standing in for "is"/"in"/"it"/"if" — recurred 56 times across all three
stores; fixed by a conservative, word-boundary-gated general rule
(`_fix_digit_letter_homoglyphs`) rather than 56 individual patches (a full
re-sweep after the fix confirms zero remaining hits, with legitimate digits
— ordinals, years, section numerals — structurally unmatchable by the
rule). (3) `PATCHES.json` now holds 9 hand-verified entries (each with its
own raw-OCR-line evidence) for defects too varied to generalize safely:
stray page numbers and marginal-synopsis-column fragments glued onto real
words with no space, one isolated "3" misread as "i", two isolated "!"
misread as "l", and Principal Doctrine I's own opening "Tue" misread as
"The" — same `{"store", "key", "remove", "replace"}` contract as
`extract_haines.py`'s `PATCHES.json`, exact-match-required, applied last.
Determinism re-verified (two runs byte-identical); full spot-check set
(Herodotus §35, Principal Doctrine IV, Vatican Collection sayings 4 and 81,
compound saying 56-57) still holds.
