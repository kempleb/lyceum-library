# Munro, *On the Nature of Things* (Lucretius, De Rerum Natura)

English prose translation by **H. A. J. Munro** (1819–1885), all six books,
extracted from Wikisource's human-proofread transcription into
`munro.clean.json` by `pipeline/tools/extract_munro_wikisource.py`.
Full source-verification detail lives in `sources/INVENTORY.md`; this file
is the short identity card.

## Edition identity

- Translation: H. A. J. Munro, first published 1864 (Cambridge: Deighton
  Bell); the transcribed scan is the **Routledge (London) 1907** reprint
  ("On the nature of things (De rerum natura) Translated with an analysis
  of the six books by H.A.J. Munro", OCLC 1050249224, per the Wikisource
  Index page's own metadata), which reprints Munro's unchanged **Fourth
  Edition (1886)** text — the scan's own prefatory note (J. D. Duff)
  certifies "The translation has undergone no change".
- US-PD basis: translation first published 1864, 4th ed. 1886, translator
  d. 1885 — safely pre-1931, US public domain.

## Pinning

- Wikisource mainspace: `On the Nature of Things (Munro)/Book 1` … `/Book 6`,
  each transcluding a Page: range from
  `Index:On the nature of things (De rerum natura) Translated with an
  analysis of the six books by H.A.J. Munro.djvu`
  (Book 1 = djvu 70–104, 2 = 105–142, 3 = 143–177, 4 = 178–218,
  5 = 219–265, 6 = 266–308; ProofreadPage quality 3 "Proofread").
- Every one of the 239 Page: subpages is fetched at a **pinned revision**
  (`action=parse&oldid=<revid>&prop=wikitext`); the full book → djvu page →
  revid table (captured 2026-07-17) is `_PAGE_REVISIONS` in
  `pipeline/tools/extract_munro_wikisource.py`. Re-running the extractor
  reproduces `munro.clean.json` byte-identically unless a table entry is
  deliberately bumped.

## Shape

`munro.clean.json` is an ordered array of records
`{book, range, start, end, [derived], text}` — one record per printed
SPREAD, keyed by the print's own running-header Latin line ranges (see the
extractor's module docstring for the spread model, the derived book-edge
ranges, seam/hyphenation handling, and the excluded apparatus).
`PATCHES.json` (absent = no patches) would hold exact-once text
corrections, same shape as `sources/miller-de-officiis/PATCHES.json`.
