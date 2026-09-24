# Parnassos Press — Gorgias, *Encomium of Helen* and *Defense of Palamedes*

Vendored English translations of Gorgias of Leontinoi's two surviving
complete speeches (DK 82 B11 and B11a), for use against work
`gorgias-fragments`. See `sources/INVENTORY.md`'s "Gorgias" entries and
`docs/gorgias-english-sources.md` for the full comparison against the other
candidate English sources (Van Hook, Donovan) that were considered and
rejected (partial coverage / non-CC licence, respectively).

**This is the only non-public-domain vendored source in this repo.** Every
other entry in `sources/` is US public domain; this one is used under an
explicit CC licence per John's ruling below. Do not treat it as a
precedent for skipping the public-domain-first policy in CLAUDE.md without
a matching ruling.

## Licence ruling (John, 2026-07-28, `CANON.md` judgment-call log)

The Parnassos Press volume is licensed **CC BY-NC-ND 4.0**
(Attribution–NonCommercial–NoDerivatives). John's ruling: exercising the
rights the licence grants "in any format or medium" is expressly carved out
of the definition of "Adapted Material" under the CC BY-NC-ND 4.0 legal
code and the CC FAQ — so reformatting the text into this site's own
per-section layout is not an adaptation, and ND is not engaged. BY
(attribution) and NC (non-commercial) still bind fully.

Exact licence statement, quoted from the book's copyright page (JSTOR
chapter PDF, p. [i]/1 of the "Introduction to the Translations" excerpt):

> This book is licensed under a Creative Commons Attribution-NonCommercial-
> NoDerivatives 4.0 International License (CC BY-NC-ND 4.0). To view a copy
> of this license, visit https://creativecommons.org/licenses/by-nc-nd/4.0/.

Licence URL: https://creativecommons.org/licenses/by-nc-nd/4.0/

## Attribution string (display wherever this text appears on-site)

> Gorgias of Leontinoi, *Encomium of Helen*, trans. Jurgen R. Gatt, and
> *Defense of Palamedes*, trans. George Alexander Gazis (rev. R. J. Barnes,
> Stamatia Dova, Jurgen Gatt, Phillip Mitsis, and Heather Reid), in
> *Gorgias/Gorgias: The Sicilian Orator and the Platonic Dialogue*, ed.
> S. Montgomery Ewegen and Coleen P. Zoller (Parnassos Press — Fonte
> Aretusa, 2022). Licensed under CC BY-NC-ND 4.0
> (https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Source

| | |
|---|---|
| Chapter | "Introduction to the Translations," by Jurgen R. Gatt |
| Book | *Gorgias/Gorgias: The Sicilian Orator and the Platonic Dialogue*, with new translations of the Helen, Palamedes, and On Not Being |
| Editors | S. Montgomery Ewegen, Coleen P. Zoller |
| Publisher | Parnassos Press — Fonte Aretusa (2022) |
| Hosted on | JSTOR, stable URL `https://www.jstor.org/stable/j.ctv36cj70n.6` |
| Translator, *Helen* | Jurgen R. Gatt |
| Translator, *Palamedes* | Drafted by George Alexander Gazis, "then revised by a group that included R.J. Barnes, Stamatia Dova, Jurgen Gatt, Phillip Mitsis, and Heather Reid" (translator's note, p. 27 of the chapter PDF) |
| Greek text followed | Laks–Most Loeb, *Early Greek Philosophy*, Vol. VIII: *Sophists, Part 1* (Cambridge, MA: Harvard UP, 2016), "with slight modifications" |
| Local copy of the source PDF | `/Users/johnboyer/.claude/uploads/e75f1215-a942-4d5a-9b15-2f34a4b4ca46/8c1b1492-GattIntroductionTranslations2022.pdf` (45-page chapter excerpt; not itself vendored into this directory — a licensed JSTOR chapter download, not redistributable in raw PDF form) |

## Shape

Two flat JSON arrays, one per speech, `[{"section": n, "text": "..."}, ...]` —
same array-of-records shape as `sources/falconer-sen/falconer.clean.json`.
`section` is the translation's own printed section number, which is
identical to the Loeb/DK numbering embedded as inline `(N)` markers in the
Greek `gorgias-fragments` build (confirmed directly against
`build/dist/gorgias-fragments/book-01.json`'s `1:B11` and `1:B11a` records:
Helen's Greek carries inline markers `(1)`–`(21)`, Palamedes' `(1)`–`(37)`).
Alignment to the DK columns is therefore 1:1 by section number, no
proportional interpolation needed.

| File | Speech | Sections | DK column |
|---|---|---|---|
| `gatt-helen.clean.json` | *Encomium of Helen* | 1–21, contiguous, no gaps | B11 |
| `gazis-palamedes.clean.json` | *Defense of Palamedes* | 1–37, contiguous, no gaps | B11a |

Only the translated speech text is included — the chapter's introduction
(pp. 11–15), footnotes/translator's notes, and the Greek facing text are
all excluded, per the licence's own text-only extraction and this task's
brief. The volume's third translation, *On Not Being*, is not part of
work `gorgias-fragments`' B11/B11a scope and was not extracted.

## Extraction and fidelity

Extracted by direct transcription from the JSTOR chapter PDF's own text
layer (a born-digital typeset PDF, not a scan — no OCR involved). Swept
explicitly for the defect classes that plague PDF extraction, all clear:

- **Ligatures** — none dropped; common ligature-bearing words (e.g.
  "difficult," "sufficient," "office") render correctly.
- **Long dashes** — em dashes (e.g. "honor and dishonor—whether to die
  justly") render as single correct characters, not glued or split.
- **Inline Greek/transliterated terms** — a few terms are quoted in
  transliteration within the English prose (*eikos*, *logos*, *sophia*,
  *mania*, *anaxios*); none are raw Greek Unicode bleeding into the
  translation, and none needed decoding.
- **Footnote markers glued to words** — found and fixed ONE case: Helen
  §12 in the source PDF carries a translator's footnote asterisk directly
  after "...it possesses the same power.]" (footnote text: "The meaning of
  the broken sentence is impossible to recover with confidence. I have
  given a literal translation of the shards which remain."). The asterisk
  was stripped from the shipped text; the footnote's content itself
  (translator's own editorial comment, not part of the speech) is excluded
  entirely, per the "no notes/apparatus" scope. The `Helen*`/`Defense of
  Palamedes*` section-title footnotes (crediting the translators) are also
  excluded — they sit in headings we don't carry, not in body text.
- **Hyphenation across line breaks** — none found; the source PDF's text
  layer already reflows correctly (checked by scanning for `<letter>-
  <space>` and `-<newline>` patterns — zero hits in either file).
- **Page-turn paragraph artifacts (found and fixed, item 85 review, 2026-07-28)**
  — the chapter is laid out as facing Greek/English columns; a page turn
  falling mid-sentence in the English column left the transcription with a
  spurious blank line at the exact point where the running text jumped from
  the bottom of one right-hand page to the top of the next (with the
  intervening Greek continuation and a translator-credit footnote sitting
  between them in the PDF, invisible to the English reading order). Three
  sections carried this artifact, confirmed directly against the PDF's own
  `pdftotext -layout` output (page numbers below are the chapter's own
  printed folios): Helen §5 ("…it does not bring any pleasure." / p.17 ends
  → p.19 resumes "So, skipping now…" — no new sentence subject, a plain
  continuation), Helen §9 ("…on account of words." / p.19 ends → p.20
  resumes "Come now, let me move…", still under "9." not a new numbered
  section), and Palamedes §5 ("…has not occurred." / p.27 ends → p.28
  resumes "If, then, the prosecutor…"). None of the three is a real
  authorial paragraph break — the print's own sentence flows continuously
  across the page turn in all three cases. The stray blank line has been
  removed from the shipped JSON (joined with a single space, like every
  other sentence seam); no section boundary or wording changed.
- **Page headers/footers interleaved into body text** — none found (JSTOR's
  running headers, e.g. "ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ" / "Defense of Palamedes", and its
  "This content downloaded from ... / All use subject to ..." footer, both
  sit outside the extracted running-text column and were excluded at
  extraction time, not stripped after the fact).
- **Double spaces / stray control characters** — swept, zero hits.

## Verification

Both JSON files parse as valid JSON; every record's `section` sequence is
contiguous 1..N with no gaps or duplicates; every `text` field is
non-empty. Size sanity: Helen sections range 236–716 characters (mean
480), Palamedes 222–872 characters (mean 518) — no anomalously short or
long outliers relative to the surrounding sections, consistent with
plausible section lengths for this genre.

## Not yet done (next task)

Wiring these translations into `manifests/gorgias-fragments.yaml` (setting
`kind: verbatim` or equivalent for B11/B11a, replacing the current `omit`
parked pending this exact ruling) and into the site build/registry is
explicitly out of scope here — see the manifest's own `PARKED PENDING
JOHN'S RULING` comment block for B11/B11a, and the preflight kind/role
contract work another agent is doing concurrently with this extraction.
