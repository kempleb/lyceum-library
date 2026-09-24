# Plato — vendored Perseus English (`plato-stephanus.clean.json`)

Flat `"<slug>:<page><letter>"` -> text store, built by
`pipeline/tools/extract_plato_perseus.py` from Perseus canonical-greekLit TEI
files vendored (not re-fetched) from the sibling `plato-reader` repo's
already-verified, already-patched local copies at
`~/Developer/plato-reader/sources/perseus-eng/` (read-only there). Per-file
SHA-256: `SHA256SUMS` in this directory.

**HARD LICENSING RULE (CLAUDE.md, overrides everything): every entry below
must be US public domain by publication date — pre-1931 as of 2026.** No
1931-or-later text is ever vendored into this store, regardless of any
claimed exception, **except Shorey's Republic (both Loeb volumes)**: vol. 2
(Books 6-10, 1935) is not PD by date, and vol. 1 (Books 1-5, first
published 1930) is digitized from a 1935-37 printing that may follow
Shorey's 1937 revision, so it is not claimed PD by date either. The
project owner explicitly ruled both in on 2026-07-28 — moving the line to
pre-1940 for this one vendoring. See the Republic entries below for the
exact basis; neither volume is ever described as PD by date.

## Original 18 (Phase 1-3, docs/plato-locus-resolver-design.md)

Apology, Charmides, Cratylus, Euthydemus, Gorgias, Hippias Major, Hippias
Minor, Laches, Lysis, Meno, Phaedo, Phaedrus, Philebus, Protagoras, Sophist,
Symposium, Theaetetus, Timaeus — translators Fowler (1914-1926), Lamb
(1924-1927), Bury (1929), all pre-1931. See `sources/INVENTORY.md`'s "Plato"
section for the full census and per-dialogue detail.

## Six more (vendored 2026-07-28, for wired-column candidates + Jowett
turn-alignment coverage)

| Dialogue | Slug | Translator | Year | PD basis | Coverage in this store |
|---|---|---|---|---|---|
| Crito | `crito` | H. N. Fowler | 1914 | Pre-1931 US public domain by publication date | Full (all Stephanus loci, 43a-54c) |
| Euthyphro | `euthyphro` | H. N. Fowler | 1914 | Pre-1931 US public domain by publication date | Full (2a-16a) |
| Ion | `ion` | W. R. M. Lamb | 1925 | Pre-1931 US public domain by publication date | Full (530a-542b) |
| Laws | `laws` | R. G. Bury | 1926 | Pre-1931 US public domain by publication date | Full (624a-969d) |
| Parmenides | `parmenides` | H. N. Fowler | 1926 | Pre-1931 US public domain by publication date | Full (126a-166c) |
| Republic vol. 1 (Books 1-5) | `republic` | Paul Shorey | 1930; TEI printing 1935-37 | **Not claimed PD-by-date** — covered by the owner's pre-1940 ruling, 2026-07-28 (see below) | Full (327a-480a) |
| Republic vol. 2 (Books 6-10) | `republic` | Paul Shorey | 1935 | **NOT public domain by date** — included per project owner's ruling, 2026-07-28 (pre-1940 line) | Full (484a-621d) |

**Republic, extended to full coverage 2026-07-28.** Perseus hosts Shorey's
complete two-volume Loeb translation as a single TEI document whose own
metadata dates the printing 1935-37 (Loeb Plato vols. 5-6). Vol. 1 (Books
1-5, Stephanus pages 327-480) was first published 1930, but Shorey revised
it in 1937 and the TEI's printing date means the digitized text may follow
the revision — so this store does **not** claim vol. 1 as PD-by-date
(adversarial review catch, 2026-07-28); it rests on the same pre-1940
ruling as vol. 2. Vol. 2 (Books 6-10, pages 484-621) was published 1935
and is **not** public domain by date — it is included in this store solely because the
project owner explicitly ruled, verbatim, "No. Pre 1940. Do it." on
2026-07-28, moving this project's licensing line to pre-1940 for this
vendoring. `extract_plato_perseus.py` no longer filters the Republic file by
page; both volumes are extracted in full, in the same pass as every other
dialogue. Nothing published 1940 or later is ever vendored under this
ruling.

**No Jowett-aligned turn coverage for Laws, Republic, or Parmenides.**
`plato-reader`'s own build defers these three to a later paragraph-level
aligner (narrated/monologue works and Statesman/Laws' granularity mismatch —
see that repo's `sources/INVENTORY.md`), so `extract_jowett_stephanus.py`
finds no `alt.jowett` data for them and they simply don't appear in
`sources/jowett-plato/jowett-stephanus.clean.json`. Crito, Euthyphro, and Ion
DO have Jowett-aligned turns in `plato-reader`'s build and are included.

## Extending further

Vendoring a 19th (or 25th) dialogue is: (1) copy its
`tlg0059.tlg<NNN>.perseus-eng2.xml` from `plato-reader`'s
`sources/perseus-eng/`, verifying its SHA-256 against that repo's own
`SHA256SUMS`; (2) add a `_DIALOGUES` entry in
`pipeline/tools/extract_plato_perseus.py`; (3) add a `_PLATO_DIALOGUES` entry
in `pipeline/reader_pipeline/stage1_context_english.py`; (4) re-run the
extractor; (5) if `plato-reader` has Jowett turns aligned for it, add it to
`extract_jowett_stephanus.py`'s own `_PLATO_DIALOGUES` and re-run that too.
Never skip the PD-by-date check in step (2) — see the HARD LICENSING RULE
above. If a Loeb volume crosses the PD line partway through (like Republic),
that is a call for the project owner, not a default filter — see Republic's
entry above for how the one existing exception was ruled and recorded.
