# Yonge, *De Finibus Bonorum et Malorum* ("On the Chief Good and Evil") —
source verification

Charles Duke Yonge's English translation of Cicero's *De Finibus*,
extracted from Wikisource's human-proofread transcription into
book/chapter-keyed clean JSON. Phase 1 only: source acquisition + clean
extraction. **Not yet wired to any manifest or the site** — the
chapter->PHI-Latin-section concordance (phase 2, needed before this can be
attached to a `manifests/de-finibus.yaml`) and any build/site wiring
(phase 3) are out of scope here. John's ruling, 2026-07-24: "use Yonge for
now" — Rackham 1914 (see `sources/INVENTORY.md`'s existing, incomplete
Rackham *De Finibus* entry, marked DO NOT WIRE due to OCR-recovery gaps)
becomes slot-A later.

## Witness identity

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891) |
| Work | *The Academic Questions, Treatise De Finibus, and Tusculan Disputations* |
| Publisher | George Bell & Sons, London |
| Printing used | 1891 |
| US-PD rationale | Published 1891, translator d. 1891 — safely pre-1931, US public domain |
| Source | en.wikisource.org, "The Academic Questions, Treatise De Finibus, and Tusculan Disputations/De Finibus, a Treatise on the Chief Good and Evil", subpages `/Book 1` … `/Book 5`, transcluding `Index:The academic questions, treatise de finibus, and Tusculan disputations.djvu` |
| Page range | Book 1 = djvu 134–163, Book 2 = 164–217, Book 3 = 217–247, Book 4 = 248–281, Book 5 = 281–322 (djvu 217 shared by Books 2/3, djvu 281 shared by Books 4/5, disambiguated by inline `<section begin="dfN" />…<section end="dfN" />` tags — each of the five tags, `df1`..`df5`, verified to begin and end exactly once across the fetched range) |
| Proofreading status | **Every one of the 189 pages spanning the De Finibus books is ProofreadPage quality level 3 ("Proofread"), all by the single proofreader "Pasicles"** — verified directly against the live MediaWiki API, 2026-07-24 (not sampled: all 189 pages checked programmatically, see "Proofreading audit" below). No level 0/1/2 pages exist in this span. |

This is the *same* 1853-family Bohn/Yonge volume already used for the
Academica and Tusculans (see `docs/pd-english-gaps-latin.md`) — Wikisource
hosts the later (1891) George Bell reprint of the same translation, not
the 1853 Bohn first printing; no revision-era wording comparison against
the 1853 text was undertaken here (out of this phase's scope — the 1891
printing is independently, safely PD on its own terms: translator
Yonge died in 1891, decades before the 1931 US-PD cutoff).

## Proofreading audit

All 189 `Page:The academic questions, treatise de finibus, and Tusculan
disputations.djvu/<N>` subpages, N = 134–322, were fetched via
`action=query&prop=revisions&rvprop=ids|content` and their
`<pagequality level="N" user="...">` tag inspected programmatically:
**189/189 are level 3, all attributed to the single proofreader
"Pasicles"**. This is a stronger fidelity class than the De Fato/Rackham
archive.org OCR extractions in this corpus: the transcription itself is
already human-proofread against the scan, not raw OCR needing a defect-fix
table. `extract_yonge_finibus.py`'s `_check_page_quality` re-asserts this
gate at fetch time (fails loud if any pinned revision is ever not level 3).

## Extraction pipeline

`pipeline/tools/extract_yonge_finibus.py` (tests:
`pipeline/tests/test_extract_yonge_finibus.py`, 32 tests, offline/synthetic
— mirrors `extract_yonge_nd_wikisource.py`'s test structure). Deterministic
against the 189 pinned revision IDs in `_PAGE_REVISIONS` (captured
2026-07-24). Method (see the module docstring for full detail):

1. Fetch all 189 pinned page revisions, strip each page's own
   `<noinclude>` chrome (pagequality tag, running head), gate on
   `pagequality level="3"`.
2. Join pages: 10 page-boundary seams end on a bare soft-line-wrap hyphen
   (e.g. djvu 152 "...erro-" / djvu 153 "neous opinions..." ->
   "...erroneous opinions..."); each hand-verified against its own
   next-page continuation to be a genuine word split, never a real
   compound needing to keep its hyphen. This edition never uses a
   `{{hws}}`/`{{hwe}}` page-boundary hyphenation template pair (confirmed
   zero occurrences, unlike `extract_yonge_nd_wikisource.py`'s corpus).
   Every other seam joins with a plain newline (a paragraph break is real
   content, not eaten by the page join).
3. Slice the five book sections by their `<section begin="dfN" />` /
   `<section end="dfN" />` tags.
4. Per book: strip the book's own heading chrome (`{{c|{{larger|{{uc|...
   Book...}}}}}}`, optionally followed by `{{Custom rule|...}}` — present
   for Books 2–5, absent for Book 1, whose section starts directly on its
   first chapter marker), then split on roman-numeral chapter markers
   (`I.`, `II.`, … at a paragraph start).
5. **Book 2's chapter I carries no roman-numeral marker in the print**
   (confirmed by the proofread wikitext itself, not a transcription gap):
   after Book 1 ends mid-dialogue, Book 2's text opens directly with "On
   this, when both of them fixed their eyes on me..." — a direct
   continuation of the same conversation, evidently why Yonge/Bohn felt no
   chapter numeral was needed there. The extractor detects this (first
   found marker's value > 1) and synthesizes chapter 1 from the
   un-numbered leading span. Expected/found chapter counts, asserted
   strictly sequential from 1: Book 1 = 21, Book 2 = 35 (34 numbered + 1
   synthesized), Book 3 = 22, Book 4 = 28, Book 5 = 32 — **138 chapters
   total**.
6. Clean markup: footnotes (`<ref>...</ref>`, 38 occurrences) dropped
   wholesale, matching this corpus's house convention
   (Falconer/Miller/Yonge-ND/Yonge-De-Fato all drop footnotes whole). The
   one `<poem>...</poem>` verse quotation and 54 inline `<br/>` line
   breaks (mostly inside `{{center block|{{smaller block|...}}}}`-wrapped
   verse this edition does not wrap in `<poem>` tags) flatten into
   surrounding prose. Layout/font templates with no semantic content
   (`{{center block|...}}`, `{{smaller block|...}}`, `{{smaller|...}}`,
   `{{c|...}}`, `{{sc|...}}`) unwrap to their own content in a fixpoint
   loop. Pure-decoration templates (`{{gap}}`, `{{dhr}}`, `{{rule|...}}`,
   `{{Custom rule|...}}`) drop. `''italic''` unwraps to its content (mostly
   single Latin/Greek words). `&nbsp;` (1 occurrence) normalizes to a
   plain space.
7. Residual-markup gate: every cleaned chapter's final text is checked for
   any surviving `{{`, `}}`, `[[`, `]]`, or `<` — fails loud if the
   template catalogue is ever incomplete for a future pinned-revision
   bump. Ran clean on the full 138-chapter extraction.

## Declared normalization: Wikisource ellipsis template → ASCII `...`

Wikisource's own transcribers encode this edition's genuine editorial
elisions (quoted-verse lacunae — the same textual phenomenon as De Fato's
typeset `* * *` asterisks) with a dedicated template, `{{...}}` /
`{{...|N}}` (`N` a spacing/width parameter), rather than literal asterisks.
6 occurrences found in the raw wikitext; 1 sits inside a footnote `<ref>`
that is dropped wholesale (per step 6 above) before the ellipsis count, so
**5 replacements land in the shipped text** — all within quoted verse
(book 2 chapters 4, 22, 32; book 4 chapter 9). Normalized to the ASCII
`...` this corpus already uses for the identical phenomenon (see
`sources/yonge-fato/README.md` "Declared normalizations" — same
convention, applied here at extraction time since Wikisource's own markup
already isolates it as a distinct template rather than literal asterisks
needing a later normalization pass).

## Proofing pass (structural + programmatic; no archive-scan OCR check needed)

Because the source is an already-proofread Wikisource transcription (not a
raw OCR pass this corpus needs to defect-fix, unlike De Fato/Rackham), the
proofing burden here is (a) verifying the transcription's own proofread
status — done exhaustively, all 189 pages, see "Proofreading audit" above
— and (b) verifying the extractor's own parsing fidelity, which the
32-test suite plus the residual-markup fail-loud gate cover. A structural
spot check of 10 chapters (both books' openings and closings: 1.1, 1.21,
2.1, 2.35, 3.1, 3.22, 4.1, 4.28, 5.1, 5.32) confirms clean, coherent prose
at every book boundary (each book's final chapter ends the dialogue/walk,
the next book's opening either restates the setting or, for Book 2,
directly continues Book 1's conversation) and matches the known De Finibus
text (Book 1 opens "I was not ignorant, Brutus..."; Book 5's final
sentence — "we all went into the town to the house of Pomponius" — is the
work's own closing line).

**No OCR-defect classes found or expected**: a programmatic scan of the
full 138-chapter output for stray footnote-call digits glued to words
(`[a-zA-Z][0-9]\b`), double spaces, and any non-ASCII character outside the
expected inventory (Greek script — native Unicode, not garbled, since this
is a human transcription rather than an OCR pass — plus æ/œ/â/Æ/Œ loan
letters, em dash, curly quotes) found **zero anomalies**.

## Output

- `yonge.clean.json` — 138 records `{book: 1..5, chapter: 1..N, text}` (N =
  21/35/22/28/32 per book), SHA-256
  `39061f838b53711bedf26d29ed34370bfac45eeee5857d78e081a782db2d7d42`.
  80,228 words / 439,314 characters.
- `PATCHES.json` — empty (no print-level errata found; none expected given
  the transcription's own proofread status).

## Not yet done (out of this phase's scope)

- Chapter→PHI-Latin-section concordance (phase 2 — needed before this can
  be wired into a `manifests/de-finibus.yaml`).
- Any manifest/`shared/lib/works.ts`/site wiring (phase 3).
- A revision-era comparison against the 1853 Bohn first printing (this
  phase relied on the 1891 printing's own independent PD status; a
  letter-identity check between 1853 and 1891, analogous to De Fato's
  1853/1878 check, was not undertaken here since it isn't required to
  clear US-PD and is not blocking phase 1).
