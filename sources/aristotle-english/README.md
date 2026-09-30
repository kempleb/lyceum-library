# Aristotle — vendored column English (`aristotle-english.clean.json`)

Bekker-column English for source-passage spans. One flat
`"<Abbr>:<book>:<column>"` map. Each value is `{"lines": [<int>, ...], "text":
"..."}`: `lines` is the Greek line-number list in document order (no Greek),
kept so a column split across a book boundary can be picked by line.
Nineteen works, in the order below. See
`docs/aristotle-context-english-design.md`.

Source for every row: sibling `aristotle-reader` commit
`691d2e0c752367812c97fe727d2f881f048ed706`, `build/dist/<Abbr>/book-NN.json`
(read-only; not this repo's `build/dist` mount). The public manifest is
`manifests/<Abbr>-public.yaml` when that file exists (Metaphysics, Politics),
otherwise `manifests/<Abbr>.yaml`. None of these manifests carries a
machine-readable licence field. Rhetoric and the Nicomachean Ethics set no
`english.primary`; their ids are the sibling registry's slot-`english`
translations (`freese`, `rackham`), and the built `english_translation`
matches those names.

| Work | Abbr | Keys | Translation | Id | Licence |
|---|---|---:|---|---|---|
| Metaphysics | `Meta` | 239 | W. D. Ross (Oxford, 1924) | `ross` | `public-domain-us` |
| Physics | `Phys` | 175 | R. P. Hardie and R. K. Gaye (Oxford, 1930) | `hardie` | `public-domain-us` |
| On Generation and Corruption | `GC` | 51 | H. H. Joachim (Oxford, 1922) | `joachim` | `public-domain-us` |
| On the Heavens | `Cael` | 95 | J. L. Stocks (Oxford, 1922) | `stocks` | `public-domain-us` |
| Meteorology | `Mete` | 108 | E. W. Webster (Oxford, 1923) | `webster` | `public-domain-us` |
| Rhetoric | `Rhet` | 135 | J. H. Freese (Loeb, 1926) | `freese` | `public-domain-us` |
| Generation of Animals | `GA` | 154 | Arthur Platt (Oxford, 1910) | `platt` | `public-domain-us` |
| Parts of Animals | `PA` | 121 | William Ogle (Oxford, 1912) | `ogle` | `public-domain-us` |
| Sense and Sensibilia | `Sens` | 28 | J. I. Beare (Oxford, 1908) | `beare` | `public-domain-us` |
| Nicomachean Ethics | `EN` | 183 | H. Rackham (Loeb, 1926) | `rackham` | `public-domain-us` |
| On Youth, Old Age, Life and Death, and Respiration | `Juv` | 27 | G. R. T. Ross (Oxford, 1908) | `ross` | `public-domain-us` |
| Sophistical Refutations | `SE` | 42 | W. A. Pickard-Cambridge (Oxford, 1928) | `pickard` | `public-domain-us` |
| History of Animals | `HA` | 304 | D'Arcy Wentworth Thompson (Oxford, 1910) | `thompson` | `public-domain-us` |
| Topics | `Top` | 135 | W. A. Pickard-Cambridge (Oxford, 1928) | `pickard` | `public-domain-us` |
| Politics | `Pol` | 189 | Benjamin Jowett (Oxford, 1885) | `jowett` | `public-domain-us` |
| De Mirabilibus Auscultationibus | `Mirab` | 36 | L. D. Dowdall (Oxford, 1909) | `dowdall` | `public-domain-us` |
| De Lineis Insecabilibus | `Lin` | 10 | H. H. Joachim (Oxford, 1908) | `joachim` | `public-domain-us` |
| De Anima | `DA` | 69 | J. A. Smith (Oxford, 1931) | `smith` | `unverified` |
| Poetics | `Poet` | 32 | W. H. Fyfe (Loeb, 1932) | `fyfe` | `unverified` |

2,133 keys in all. File `sources/aristotle-english/aristotle-english.clean.json`.
SHA-256 `2c7386caca87793f39277f0b15e2460cd0e6a2aa1bf4ae5c9ea2c225e38f8ef7`.

## Alternates (`alternates.json`)

Whole passages from another public-domain translation, for a span whose
DK Greek holds words the store's translation leaves out. A span picks one
with `"translation": "<id>"`; its `translation_credit` must equal the
entry's `credit`. Shape: `{"<id>": {"work", "credit", "passages":
{"<Bekker range>": "<text>"}}}`. Transcribed by hand, each checked against
the page scans.

| Id | Work | Translation | Passage | Source | Used for |
|---|---|---|---|---|---|
| `mmahon` | Metaphysics | John H. M'Mahon (Bohn's Classical Library, London, 1857), pp. 23–24 | 986a22–986b2 | archive.org `metaphysicsaris02arisgoog`, page images n127–n128 | Pythagoras 7: Ross omits the Alcmaeon dating clause (986a29–30), which DK prints |
| `owen` | Sophistical Refutations | Octavius Freire Owen, The Organon, vol. 2 (Bohn's Classical Library, London, 1853), p. 560 | 170b19–170b25 | the sibling's built `SE` book 1, column 170b (Owen's text, stored under the id `ross`); matched against archive.org `organonorlogica04porpgoog`, page image n214 | Zeno A14: Pickard-Cambridge follows a text without Zeno's name (Ross's OCT brackets it); DK prints Ζήνων and Owen renders it "(Zeno)" |
| `taylor` | On the Heavens | Thomas Taylor, A Dissertation on the Philosophy of Aristotle (London, 1812), Book I ch. 4, pp. 22–23, where Taylor quotes his own translation of De Caelo III.7 | 305b1–305b19 | archive.org `adissertationon00taylgoog`, page images n54–n55 | Democritus A46a: Stocks renders "the followers of Empedocles" and drops Democritus, whom every Greek text names |

Taylor's spellings "seperated" and "extention" are kept as printed; a stray mark after "they" at a line end on p. 22 and the printer's space before ";" are left out.

The M'Mahon table of opposites is printed as two blocks of five pairs; the
text keeps that order (the scan's OCR interleaves the blocks). Marginal
summaries and the footnote on p. 23 are left out.

SHA-256 (`alternates.json`)
`82fba07fb547c5ac7b45ed2c6d2ba7e33559971a4731f84fae76b638489efab0`.

## Corrections

`corrections.json` (this directory) is the list of edits the extractor
applies after each work's columns are built and before it writes the store.
Each object has `key`, `find`, `replace`, and `source`. `find` must occur
exactly once in that key's text. A replacement that would insert a blank
line is refused. Each entry was checked against a scan of the printed
translation; `source` names the scan.

| Work | Corrections |
|---|---:|
| De Lineis Insecabilibus | 53 |
| Physics | 3 |
| Metaphysics | 1 |
| Meteorology | 1 |
| On the Heavens | 2 |
| On Generation and Corruption | 1 |
| De Anima | 1 |
| Sophistical Refutations | 1 |
| Parts of Animals | 2 |
| Sense and Sensibilia | 1 |

66 in all.

The Metaphysics text follows W. D. Ross's 1928 second edition, checked
against both printings, so the resolver credit is "Ross, 1928". 1924 is
the year of Ross's Greek edition and commentary, which his 1928 preface
names as the basis of the revision. The sibling manifest still labels the
translation "W. D. Ross (Oxford, 1924)". The store follows the 1928 printing.

De Anima (Smith) and Poetics (Fyfe) are not claimed public domain; in use by
the owner's ruling of 2026-09-22 (and 2026-09-25 for vendoring here).

Parts of Animals: `manifests/PA.yaml` `english.primary.name` says "William
Ogle (Oxford, 1882)"; `work.english_translation` and the built manifest say
"William Ogle (Oxford, 1912)". The id is `ogle` on both. The store is the
built columns. Credit in the resolver table is "Ogle, 1912".

Four columns are stored with empty text, as in the sibling build: Rhetoric
`Rhet:1:1378a` and `Rhet:2:1404a`, Politics `Pol:5:1316a` and `Pol:5:1316b`.

**Regenerate** (sibling checkout must be the commit above, with its public
build already in `build/dist`; this script does not build it):

```
cd pipeline && uv run python tools/extract_aristotle_english.py
```

`$ARISTOTLE_DATA_DIR`, when set, replaces `../aristotle-reader/build/dist`.
The extractor refuses a missing data dir, a primary translation id other
than the table's, a declared licence other than the table's, and any
`private` flag. It does not read this repo's `build/dist`.
