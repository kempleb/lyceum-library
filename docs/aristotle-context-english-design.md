# Aristotle source-passage English — design

**Status:** design only. Nothing implemented. Written 2026-09-25. This is the
third round of the source-passage initiative, after
`docs/source-passage-english-scoping.md` (Diogenes Laertius) and
`docs/plato-locus-resolver-design.md` (Plato), and follows their conventions.
John approved Aristotle as the next source; his standing policy (2026-07-27) is
to use all good public-domain English we can find, plus what the sister readers
already carry.

**Blast radius when built:** one new extractor
(`pipeline/tools/extract_aristotle_english.py`), one new vendored source dir
(`sources/aristotle-english/`), one local-only proposal tool
(`pipeline/tools/propose_aristotle_loci.py`), about 80 lines added to
`pipeline/reader_pipeline/stage1_context_english.py`, new cases in
`pipeline/tests/test_stage1_context_english.py`, per-work
`sources/<work>/context-english.json` sidecar entries, and a
`sources/INVENTORY.md` entry. **No UI change, no schema change, no new
dependency.** The one visible change is an ellipsis where the English is
trimmed (section B), which is reader-facing and waits for John.

**How the numbers were made.** Every count below comes from two scratch
scripts (not committed) run on 2026-09-25 against `build/dist` at release
`2026.09.25-f13948b`, with the Aristotle corpus mounted from the sibling at
commit `691d2e0c75`. Method is in the appendix. No Greek text appears in this
document; the corpus rule forbids committing it.

---

## 0. Headline

- The testimonia works hold **914 columns; 96 carry source-passage English**
  today (Diogenes Laertius and Plato).
- **133 columns name Aristotle as their first cited source, plus 8 that name
  pseudo-Aristotle (141). None has English yet.** 132 of the 141 contain at
  least one Aristotle quotation that can be found, line by line, in the
  mounted Aristotle Greek: **161 quotations ("runs") in 132 columns.**
- **25 more columns cite Aristotle after another source.** 20 of them hold 24
  locatable Aristotle runs.
- The mounted English is aligned to the Greek **only by Bekker column**
  (about 2,600 characters per column). Line-level markers exist but are
  machine-placed, and for the Metaphysics and On the Heavens they are
  estimates. So the design locates the Greek extent by machine, has an Opus
  reader bold the exact English words, and trims the English to the bold
  sentences plus one sentence either side.
- The English must be **vendored into `sources/`**, not read from the mount:
  `build:public` deletes `build/dist` and runs the DK pipeline **before** it
  mounts Aristotle, so the mounted data does not exist when source-passage
  English is resolved.

---

## A. Census

"First cited source" means the first `authorDisplay`, in document order, in
the column's `expandedCitation`. DK's expanded citation covers only a
column's opening citation head(s), so later Aristotle citations were found by
splitting each column's Greek context lines into citation runs at every
citation head (see appendix, method).

### A.1 Columns whose first cited source is Aristotle

| Class | Aristotle | pseudo-Aristotle | Total |
|---|---:|---:|---:|
| Resolvable: at least one run found in the mounted Greek | 129 | 3 | **132** |
| Work not mounted (all *Problemata*) | 0 | 4 | 4 |
| Pointer only: DK names Aristotle, then quotes another author (Heraclitus A5 quotes Simplicius; Democritus A91 quotes Alexander) | 2 | 0 | 2 |
| Locus unparseable: cited by chapter only (*De Melisso Xenophane Gorgia*: Melissus A5, Xenophanes A28) | 1 | 1 | 2 |
| DK names no work (Xenophanes A13: "ARIST. B 26. 1400b 5"; 1400b falls in the *Rhetoric*) | 1 | 0 | 1 |
| **Total** | **133** | **8** | **141** |

- None of the 141 has `contextEnglish` today.
- Runs per column: 107 columns hold one Aristotle run, 23 hold two, 2 hold
  four, 9 hold none that can be located. **161 located runs** in all.
- **Every parsed locus names a column and a line that exist in the mounted
  Greek.** No "column missing" or "line missing" case occurred.
- Located runs by work: Metaphysics 25, Physics 23, On Generation and
  Corruption 22, De Anima 17, On the Heavens 16, Rhetoric 11, Meteorology 10,
  Generation of Animals 10, Parts of Animals 6, Sense and Sensibilia 5,
  Nicomachean Ethics 3, Respiration (in the mounted "Juv" work) 3,
  Sophistical Refutations 3, Poetics 2, and one each in History of Animals,
  Topics, Politics, *De Mirabilibus Auscultationibus*, *De Lineis
  Insecabilibus*. **19 works**, all mounted.
- 22 runs cross one column boundary; 1 crosses two (Democritus A60, *On the
  Heavens* 309a1 on into 310a).

A first pass that read only the expanded citation's own locus counted 130
Aristotle columns resolvable and 2 unparseable; the run-splitting pass
reclassified Anaxagoras A84 as resolvable (DK prints "Β 9 (…) 369b 14") and
Heraclitus A5 and Democritus A91 as pointer-only. The table above uses the
run-splitting pass.

### A.2 Columns that cite Aristotle, but not first

25 columns. 20 hold at least one locatable Aristotle run (24 runs):

- **14 columns (16 runs) have no English at all** — the first source is
  Aëtius, Simplicius, Xenophon, Cicero, Aelian, a scholiast, or a head the
  parser did not name.
- **6 columns (8 runs) already carry Plato or Diogenes Laertius English**
  (Anaxagoras A47, A55; Gorgias A19; Heraclitus A10; Protagoras A19;
  Pythagoras 5). An Aristotle span would be a second span, in DK's printed
  order — the Pythagoras 10 precedent.
- The other 5 are pointer-only (3), chapter-only (1), or cite an unmounted
  work (*De plantis*, 1).

### A.3 How reliable the location is

For each located run, a local alignment matched DK's quoted words against the
mounted Greek (appendix). "Coverage" is the share of DK's words found, in
order.

| Coverage | Runs (of 161) |
|---|---:|
| ≥ 0.80 | 143 |
| 0.50–0.79 | 11 |
| < 0.50 | 7 |

The match started **at the cited line in 137 runs, one line off in 22**, and
in a different column in 2. In 114 of the 132 resolvable columns, every run
reaches 0.80. Low coverage does not mean the passage is missing: the usual
causes are DK's name abbreviations, DK's own omissions, and the run splitter
running two sources together. Those 18 runs get a slower read.

The full per-run table is in the appendix.

---

## B. Extent: how much English to show

### B.1 What the mounted English offers

Each mounted segment (`build/dist/<Abbr>/book-NN.json`) carries the Greek line
by line (`greek[].n` is the Bekker line) and **one English text for the whole
column**. That text also carries `english.bekker`: a five-line tick list
(`{n, offset, real}`) placing Bekker lines 1, 5, 10 … inside the English.

- `real: true` ticks were placed by the sibling's gloss aligner (Sonnet
  gloss, Opus verify). The sibling's `docs/alignment-status.md` says plainly
  that **no human verdict survives for any work** except eight pins in
  *Poetics*/Fyfe. `real: false` ticks are proportional estimates.
- Real ticks dominate in Physics, On Generation and Corruption, Meteorology,
  De Anima, Sense and Sensibilia, Respiration, History of Animals, Politics,
  Sophistical Refutations, Poetics. **The Metaphysics has 3 real ticks out of
  1,510 (not counting each column's line-1 tick); On the Heavens has none.**
  Generation of Animals, Parts of Animals, Topics, *Mirab.* and *Lin.* are all
  or nearly all estimates; the Rhetoric (130 real of 891) and the Nicomachean
  Ethics (177 real of 1,151) are mostly estimates.
- Of the 177 located runs in columns with no English yet (161 first + 16
  later), **95 sit in columns whose ticks are mostly real, 82 in columns whose
  ticks are estimates.**
- For the public Metaphysics the column English is itself an estimate: the
  sibling's `manifests/Meta-public.yaml` builds Ross "chapter-anchored
  (interpolated gutter), no per-line Bekker" — each chapter's English is
  shared out across its columns by proportion. So the English for a line near
  a column edge can sit in the neighbouring column's slice. (One edge checked
  by hand, 983b/984a, falls cleanly.)
- **Finer alignment elsewhere in the sibling:**
  `alignment-results/ross/Meta_ross_gloss_map.json` holds 1,485 five-line and
  219 column ticks for Ross's Metaphysics marked confirmed by the Opus
  verifier. It was made for the sibling's local full build, where Ross is the
  secondary beside Tredennick, and it is **not used by the public build**. Its
  offsets are relative to chapters, not columns. `pipeline/tools/
  sentence_spike.py` is a read-only feasibility spike for Greek-sentence to
  English-sentence alignment, not production. **No word- or sentence-level
  Greek–English alignment exists in production anywhere in the sibling.**

A column averages **2,644 characters** of English (152 distinct columns the
located runs touch, 402,000 characters). The median DK quotation runs **5
Bekker lines**; the longest within one column runs 28.

### B.2 Matching DK's Greek to Aristotle's Greek

Both sides are Greek and both come from TLG (the mounted Aristotle spine is
built from the TLG export; DK is TLG's DK). They differ only where DK
abridges, supplies, or abbreviates. The census script shows the match is
mechanical and reliable:

1. Normalise both texts: strip accents and breathings, lower-case, fold final
   sigma, drop DK's bracketed editorial insertions (`[sc. …]`, `[B 1]`).
2. Treat DK's one-letter name abbreviations (Θ., Δ., Π. for the philosopher
   being quoted) as matching any word with that initial.
3. Local alignment of DK's words against the mounted Greek, in a window from
   three lines before the cited line through the next two columns: +2 for a
   match, −1 for a DK word not found, −0.15 for a skipped store word (so DK's
   "…" omissions cost little).
4. Read off the store's first and last matched line: that is the Greek
   extent, e.g. `983b6-983b33`, with a coverage score.

This becomes `pipeline/tools/propose_aristotle_loci.py`: **local only**
(it reads DK and Aristotle Greek derived from TLG, so it never runs in CI),
and its output is loci and scores only, never Greek. It proposes; a reader
decides.

### B.3 Options for the English

| Option | What it shows | Verdict |
|---|---|---|
| **(a) Whole columns, bold inside** (the Plato pattern) | Every column the locus touches, the DK words in bold | Zero new mechanism, but ~2,600 characters per column for a median 5-line quotation; a two-column range shows ~5,300. Plato's sections are one Stephanus letter, far shorter. |
| **(b) Cut by five-line ticks** | English between the ticks bracketing the Greek extent, snapped to sentences | Rejected. 82 of 177 runs sit on estimated ticks, and even real ticks are machine-checked only. The text shown would move whenever the sibling re-aligns. |
| **(c) Bold, then trim to the bold sentences** | The sentences holding the bold, plus one sentence before and after, with "…" where cut | **Recommended.** Deterministic, derived from the hand-checked bold, no dependence on tick estimates. |
| (d) Hand-authored English start and end anchors | Whatever the author brackets | Same outcome as (c) with two more authored strings per span and more gates. |

### B.4 The recommended approach, in full

1. **Greek extent (locus).** The proposal tool suggests start and end lines.
   An Opus reader (Greek judgment goes to Opus under this repo's rules)
   confirms or corrects them against DK's printed Greek. The locus records
   the extent DK actually quotes, never DK's open-ended "ff." — the Plato rule.
2. **English window (resolver).** The resolver returns the Bekker columns the
   locus touches **plus one neighbouring column on each side**, one paragraph
   per column, labelled by column (`sectionLoci`). The neighbours cover the
   estimated column edges in the Metaphysics and elsewhere; they cost nothing
   on screen because step 4 trims them away unless the bold falls there.
3. **Bold (emphasis).** The same Opus reader marks the exact English words
   that translate DK's Greek as the span's `emphasis` list, sliced byte-exact
   from the resolved text — the shipped item-83 rule (each substring occurs
   exactly once, in order, no overlap, never across a paragraph join; split a
   bold run at a column boundary, as Gorgias A19's Meno span already does).
   For Aristotle spans **emphasis is mandatory**, since it defines the
   window. In real-tick works the tick offsets are a hint for where to look;
   they are never the answer.
4. **Trim (build time).** After emphasis passes its gates, `_resolve_span`
   keeps the sentence holding the first bold run through the sentence holding
   the last bold run — no extra sentence on either side (John, 2026-09-25:
   "depends on how much DK includes") — and writes "…" at each cut. Paragraphs left empty drop out with their `sectionLoci` entry. The
   emitted text still derives wholly from the vendored store, so it cannot
   drift from it.
5. **Sentence rule.** A sentence ends at `.`, `?` or `!` (plus any closing
   quote or bracket) followed by whitespace and a capital or opening quote,
   except after a short fixed list (`e.g.`, `i.e.`, `cf.`, `viz.`, a single
   capital initial). Semicolons do not end sentences; Ross's long sentences
   stay whole.

**Cost.** About 80 lines in stage 1 (resolver, table, trim, sentence rule),
the extractor, the proposal tool, tests. The real work is reading: 161 runs
(plus 24 later ones), each needing DK's Greek compared with the English, with
the 18 low-coverage runs read slowest. It parallelises by DK work, as the
Plato and emphasis waves did.

**Verification.**

- Build-time fatal gates (section F) prove every bold string exists exactly
  once in the store's text and that every locus resolves.
- A cross-family content gate — Grok, which holds this repo's standing place
  for content and extraction gates — reads a sample of spans (all of phase 1;
  at least 30 across works later) and checks the bold against DK's Greek, as
  it did for item 83.
- `propose_aristotle_loci.py --check` (local, advisory, not CI) re-runs the
  Greek match for every declared span and flags a locus whose start differs
  from the match by more than one line or whose run covers under 0.80. For
  real-tick works it also flags a bold run that starts more than five Bekker
  lines from where the ticks put the Greek start.
- John's spot-check list goes into `REVIEW-CHECKLIST.md`.

---

## C. Store: vendor into `sources/`

**Recommendation: vendor a Bekker-keyed English store into
`sources/aristotle-english/`, built from the sibling's public build by an
extractor, exactly as Plato was vendored.** Reading the mounted data at build
time does not work, for five reasons:

1. **Order of the build.** `scripts/build-public.mjs` deletes `build/dist`
   (`clean-dist`), then runs `reader_pipeline all` for every classical work
   (which is when `stage1_context_english` runs), and only then runs
   `mount-corpus.mjs`. The mounted Aristotle data does not exist when the
   resolver would need it. Reordering the build to fix that couples every DK
   work to the mount.
2. **The sibling may be absent.** Mounting no-ops when the sibling is missing
   (CI, a fresh checkout). A resolver reading the sibling directly would then
   have to fail the build or drop a declared span in silence; the module's
   own rule forbids the second, and the first breaks every checkout without
   the sibling.
3. **CI has no corpus.** The shared public repository's CI runs the pipeline
   tests with no corpus. Tests that pin real sidecars against the store (the
   Thales pattern) need the store committed. English translations may be
   committed; only TLG/PHI Greek may not.
4. **Pinning the right translation.** The sibling's `manifests/Meta.yaml`
   (its local full build) makes Hugh Tredennick's Loeb (1933) the primary —
   the sibling's own note says it is in US copyright until 2029. Only
   `Meta-public.yaml` builds Ross alone. An extractor with a per-work
   expected-translation table refuses anything else, so a sibling rebuilt from
   the wrong manifest can never leak Tredennick into this repo.
5. **Frozen text.** A vendored store means authored bold ranges never break
   because the sibling re-slices its columns. A drift report (below) says
   when the two copies part.

**Shape.** One flat JSON map, the `plato-stephanus.clean.json` idea with one
more level, in document order (the order the resolver expands by):

```json
{
  "Meta:1:983b": {"lines": [1, 2, 3, "…", 33], "text": "…column English…"},
  "Meta:1:984a": {"lines": [1, "…", 34], "text": "…"}
}
```

Key `<Abbr>:<book>:<column>` — the book is needed because 61 columns in 13
of the 19 cited works are split across a book boundary (the Metaphysics has
11, e.g. 993a). Generation of Animals 763b is one: lines 1–16 close book 3,
lines 20–34 open book 4, and Anaxagoras A107 cites 763b30. `lines` is the ordered Greek line-number list, kept
so the resolver can pick the right half of a split column and handle the
Metaphysics' line gaps (993a has no line 28; 1029b runs 3–12, 1, 2, 13 …).
Numbers only, no Greek.

**Extractor** (`pipeline/tools/extract_aristotle_english.py`): reads
`$ARISTOTLE_DATA_DIR` or `../aristotle-reader/build/dist` (read-only); for
each work in its table, checks the manifest's primary translation id and
licence against the table (fatal on mismatch or on any `private` flag);
writes the store; asserts every key matches `^[A-Za-z]+:\d+:\d+[ab]$`, no
text contains a blank line (`\n\n` would break paragraph↔label pairing), and
no text in a cited column is empty (the mounted Politics has empty English
at 5:1316a and 5:1316b, the Rhetoric at 1:1378a and 2:1404a — none cited);
prints SHA-256. Records the sibling commit and each work's
translation in `sources/aristotle-english/README.md` and
`sources/INVENTORY.md` (which `build:public`'s hash gate then checks).

**Scope.** Whole works for each work a phase needs, following Plato's
"whole cited dialogues" rule: the Metaphysics alone is about 0.6 million
characters; all 19 cited works about 5.4 million (Plato's store is 3.8 MB).

**Drift report** (`--check` mode of the extractor, local, advisory): compares
the vendored text with the mounted text column by column and lists
differences. It never fails a build.

**The cost of vendoring.** The same English then exists twice, once in the
mounted Aristotle pages and once in `sources/`. The reader's Aristotle page
and the source-passage block may briefly show different slices after a
sibling rebuild; the drift report is the guard. And `sources/` ships to the
public mirror (`public-export.exclude` does not exclude it), which matters
for the two works whose translations are not public domain by date (E, H).

---

## D. Locus syntax and resolver contract

### D.1 Locus

```
_ARISTOTLE_LOCUS_RE = r"^(\d{1,4}[ab])(\d{1,2})(?:-(\d{1,4}[ab])(\d{1,2}))?$"
```

- Single line `1056b28`, or a range naming both ends in full,
  `983b6-983b33`, `984b32-985a10`. No abbreviated end (`983b6-33`), no
  spaces, no `ff.`, no bare column. (`\d{1,4}` because the *Categories* starts
  at column 1a; lines reach 40 in the cited data, e.g. 168b40.)
- The work lives in `source_work`, never in the locus — the Plato rule.
- The reader already prints `span.locus.replace('-', '–')`, so the credit
  reads "983b6–983b33". Shortening that to "983b6–33" would be a reader change
  and is not proposed.

### D.2 Resolver

`_resolve_aristotle(abbr)` returns a closure `resolver(locus) -> (text,
section_loci)`, the same contract as `_resolve_plato`:

1. Full-match the regex, else fatal.
2. Load the store; take this work's keys in store order.
3. Find the **start segment**: the segment whose column is the start column
   and whose `lines` contain the start line. Same for the end. Either missing
   is fatal ("column not in store" or "line not in column").
4. Range order is **store order, then position in `lines`**, never
   arithmetic on Bekker numbers — book-split columns and the 1029b
   transposition make arithmetic wrong. End before start is fatal.
5. A range spanning more than 3 segments is fatal (the census maximum is 3;
   this catches a typed `993a` for `983a`).
6. Add one neighbouring segment on each side, in store order and within the
   same work, skipping a neighbour whose English is empty. An empty segment
   inside the range itself is fatal.
7. Return the segments' texts joined by a blank line, and `section_loci` =
   each segment's **column token** (`"983b"`), one per paragraph.

**`sectionLoci` must stay column tokens, never line loci.** The reader's
`contextSectionMarkerNumbers` (`shared/components/Reader.svelte`, ~line 1494)
reads a trailing number off each `sectionLoci` entry (`/(\d+)\s*$/`) to decide
where to split DK's inline "(N)" section markers. A label like `983b6` would
feed "6" into that split; `983b` ends in a letter and is ignored, like Plato's
`315c`. A book-split column included whole on both sides labels both
paragraphs with the same token; that is rare and harmless.

After the trim (B.4 step 4), a span whose remaining text is one paragraph
emits no `sectionLoci`, matching DL and Plato.

### D.3 Registry

```python
_ARISTOTLE_WORKS = {           # site title -> (store abbr, credit)
    "Metaphysics": ("Meta", "Ross, 1924"),   # credit year: see E
    "Physics": ("Phys", "Hardie and Gaye, 1930"),
    ...
}
_RESOLVERS.update({("Aristotle", t): _resolve_aristotle(a)
                   for t, (a, _c) in _ARISTOTLE_WORKS.items()})
_TRIM_TO_EMPHASIS = {("Aristotle", t) for t in _ARISTOTLE_WORKS}
```

- Pair-keyed, as before: `("Aristotle", "Problemata")` has no entry and is
  fatal if declared "translated".
- `source_work` uses the site's own English title for the work (the one its
  Aristotle page shows), as Plato uses "Protagoras" rather than DK's
  "Protag.".
- The trim runs only for pairs in `_TRIM_TO_EMPHASIS`, so DL and Plato output
  stays byte-identical.
- The pseudo-Aristotelian works need one ruling (H3) on which author key they
  sit under.

### D.4 Worked shapes (invented loci)

| Locus | Resolver returns (before trim) |
|---|---|
| `983b6` | 983a, 983b, 984a |
| `983b6-983b33` | 983a, 983b, 984a |
| `984b32-985a10` | 984a, 984b, 985a, 985b |
| `763b30` in a work where 763b is split across books 3 and 4 | the book-4 half (it holds line 30) with its neighbours |

---

## E. Credit

The approved template needs no change: *"Source passage: {author}, {work}
{locus} (tr. {credit})."* It makes no licence claim, so it serves the two
grey-area works as-is. Credit strings follow the Plato form ("Lamb, 1925").
**All strings below are DRAFT until John approves them.**

| Work (site title) | Translator, edition (as the mounted manifest names it) | Licence status in the manifest | Proposed credit | Runs |
|---|---|---|---|---:|
| Metaphysics | W. D. Ross (Oxford, 1924) | public-domain-us | Ross, 1924 — *year to check, below* | 25 |
| Physics | R. P. Hardie and R. K. Gaye (Oxford, 1930) | public-domain-us | Hardie and Gaye, 1930 | 23 |
| On Generation and Corruption | H. H. Joachim (Oxford, 1922) | public-domain-us | Joachim, 1922 | 22 |
| De Anima | J. A. Smith (Oxford, 1931) | **unverified** (John's ruling 2026-09-22) | Smith, 1931 | 17 |
| On the Heavens | J. L. Stocks (Oxford, 1922) | public-domain-us | Stocks, 1922 | 16 |
| Rhetoric | J. H. Freese (Loeb, 1926) | public-domain-us | Freese, 1926 | 11 |
| Meteorology | E. W. Webster (Oxford, 1923) | public-domain-us | Webster, 1923 | 10 |
| Generation of Animals | Arthur Platt (Oxford, 1910) | public-domain-us | Platt, 1910 | 10 |
| Parts of Animals | William Ogle (Oxford, 1912) | public-domain-us | Ogle, 1912 | 6 |
| Sense and Sensibilia | J. I. Beare (Oxford, 1908) | public-domain-us | Beare, 1908 | 5 |
| Nicomachean Ethics | H. Rackham (Loeb, 1926) | public-domain-us | Rackham, 1926 | 3 |
| On Youth, Old Age, Life and Death, and Respiration | G. R. T. Ross (Oxford, 1908) | public-domain-us | G. R. T. Ross, 1908 | 3 |
| Sophistical Refutations | W. A. Pickard-Cambridge (Oxford, 1928) | public-domain-us | Pickard-Cambridge, 1928 | 3 |
| Poetics | W. H. Fyfe (Loeb, 1932) | **unverified** (John's ruling 2026-09-22) | Fyfe, 1932 | 2 |
| History of Animals | D'Arcy Wentworth Thompson (Oxford, 1910) | public-domain-us | Thompson, 1910 | 1 |
| Topics | W. A. Pickard-Cambridge (Oxford, 1928) | public-domain-us | Pickard-Cambridge, 1928 | 1 |
| Politics | Benjamin Jowett (Oxford, 1885) | public-domain-us | Jowett, 1885 | 1 |
| De Mirabilibus Auscultationibus | L. D. Dowdall (Oxford, 1909) | public-domain-us | Dowdall, 1909 | 1 |
| De Lineis Insecabilibus | H. H. Joachim (Oxford, 1908) | public-domain-us | Joachim, 1908 | 1 |

(Runs counted over the 161 first-Aristotle runs.)

- **Grey-area works.** Smith's De Anima and Fyfe's Poetics are used by
  John's 2026-09-22 ruling (freely hosted by MIT Classics and Perseus). The
  credit carries no licence words; the store README and `INVENTORY.md` record
  "not claimed public domain; in use by the owner's ruling of 2026-09-22", in
  the form the Republic entry in `sources/perseus-plato/README.md` already
  uses. The extractor's per-work table records each translation's licence
  status; a test asserts De Anima and Poetics are never marked
  public-domain-us there.
- **Two readings of "Ross".** The Respiration credit needs the initials (G.
  R. T. Ross) so it is not confused with W. D. Ross.
- **Metaphysics year to check.** The mounted label says "Oxford, 1924". Ross's
  Oxford translation of the Metaphysics appeared in 1908, with a second
  edition in 1928; 1924 is the year of his Greek edition and commentary, and
  `docs/source-passage-english-scoping.md` gave yet another year. All
  candidates are before 1931, so public-domain status does not turn on it, but
  the credit should name the printing the text follows. Not verified here; the
  sibling's `sources/meta-ross` is the MIT Classics transcription.
- **Alternates** already on the mounted pages (Wallace's De Anima, 1882;
  Butcher's Poetics, 1895; Roberts' Rhetoric, 1924; W. D. Ross's Ethics, 1908;
  Owen's Topics and Sophistical Refutations, 1853; Ellis's Politics) could
  later be offered through the reader's translation picker, as Jowett is for
  Plato. Not in this design (H6).

---

## F. Gates and tests

### F.1 Fatal gates (build time, in `stage1_context_english`)

All existing gates still apply (non-empty file, known column, required
fields, status, credit present, pair registered, locus resolves, emphasis
exact-once/ordered/non-overlapping). New:

1. Aristotle locus does not full-match `_ARISTOTLE_LOCUS_RE`.
2. Start or end column not in the store for that work; start or end line not
   in that column's `lines`.
3. End before start in store order.
4. Range spans more than 3 segments.
5. An empty-English segment inside the range.
6. A "translated" Aristotle span with no `emphasis` (it defines the window).
7. An emphasis substring that contains a blank line (crosses a paragraph).
   This one is general — the reader already assumes it for every span — and
   the existing sidecars should pass it; check before adding.

### F.2 Store gates (extractor, and one test over the committed file)

Key format; non-empty text; no blank line inside a text; `lines` non-empty
and all integers; every work in `_ARISTOTLE_WORKS` present in the store;
translation id per work matches the extractor's table; SHA-256 matches
`INVENTORY.md` (the existing hash gate).

### F.3 Tests (`pipeline/tests/test_stage1_context_english.py`)

The existing file's posture holds: an autouse fixture points `SOURCES_DIR` at
`tmp_path`, and each test writes an **invented** store and sidecar. No real
Greek anywhere; real English only in the integration tests, from the
committed public-domain store.

Unit cases, invented text (e.g. columns `"10a"`, `"10b"`, `"11a"` holding
"Alpha one. Beta two. Gamma three."):

- single-line locus resolves to the column plus neighbours;
- same-column range; cross-column range; the 3-segment limit;
- book-split column: the line picks the right half;
- a transposed line list: a range ordered by position, and the reverse fatal;
- missing column, missing line, reversed range, empty segment inside the
  range, empty neighbour skipped;
- bad syntax: `10a`, `10 a 5`, `10a5ff`, `10a5-6`, `10a5-`;
- `("Aristotle", "Problemata")` declared "translated": fatal;
- missing emphasis on an Aristotle span: fatal;
- trim: keeps one sentence either side, writes "…" at each cut, drops an
  emptied paragraph and its `sectionLoci` entry, drops `sectionLoci` when one
  paragraph is left;
- sentence rule: does not split after `e.g.`, `cf.`, or a capital initial;
  does split before an opening quote;
- `sectionLoci` entries never end in a digit;
- DL and Plato spans are not trimmed (byte-identical to today).

Integration cases, committed store: the phase-1 sidecar entries resolve;
one pinned span's emitted text starts and ends where hand-checked (the
Thales A1 pattern); De Anima and Poetics are never marked public-domain-us
in the extractor's table.

### F.4 What stays outside CI

The proposal/check tool and the drift report need TLG-derived Greek or the
sibling, so they run locally only, before a commit. `build:public` stays the
gate before anything ships.

---

## G. Phasing

| Phase | Scope | Runs | Columns |
|---|---|---:|---:|
| **1** | Extractor, store (Metaphysics only), resolver, trim, tests, INVENTORY entry; sidecars for every first-Aristotle run in **Metaphysics A** | 14 | 14 |
| **2** | Vendor the other public-domain works; every remaining first-Aristotle run outside De Anima and Poetics | 128 | 108 |
| **3** | De Anima and Poetics, after John's ruling (H2) | 19 | 14 |
| **4** | Aristotle runs in columns where another source comes first | 24 | 20 |
| later | *Problemata* (4 first + 1 later column; new sourcing); *De plantis* and *De spiritu* runs in 3 later columns (not mounted); chapter-only citations (the 2 *De Melisso* columns, Empedocles A44); Xenophanes A13 (DK names no work) | — | — |
| refused | Pointer-only columns (2 first + 3 later), as in the Plato round | — | — |

**Phase 1 is Metaphysics A** — Thales A12, Anaximenes A4, Empedocles A6, A28,
A37, A39, Anaxagoras A43, A58, Leucippus A6, Melissus A7, Parmenides A6,
A24, Pythagoras 7, Xenophanes A30. It is worth shipping alone: it is the
classic doxography, one translation (Ross, public domain), and the hardest
alignment case (estimated column edges), so it proves the neighbour rule and
the trim where they matter most. Pythagoras 7 (coverage 0.22) exercises the
slow-read path. Three phase-1 columns hold a second Aristotle run: Parmenides
A24's second run is also in the Metaphysics and ships in phase 1; Anaxagoras
A43's (On the Heavens) and Melissus A7's (Physics) wait for phase 2 — the
span list is additive and nothing is claimed for the missing run. Heraclitus
A5 (Metaphysics A, pointer only) is refused.

One column falls in both phases 2 and 3: Empedocles A57.

Per phase: Opus reads and authors; Grok gates the content; `build:public`
completes; `REVIEW-CHECKLIST.md` gets the spot-check list and the dashboard
is republished; commit on green.

---

## H. Rulings (John, 2026-09-25)

1. **Extent: as much as DK includes.** The English shown is the sentences
   that hold DK's quoted words, nothing more; "…" where cut (B.4 step 4).
2. **Smith's De Anima and Fyfe's Poetics: include them**, vendored into
   `sources/` and so into the public mirror, with no public-domain claim.
3. **Doubtful works: credit as "pseudo-Aristotle".**

Still open, not blocking phase 1:

4. **Ross's Metaphysics credit year** (site says 1924; printings are 1908 and
   1928). To be checked before phase 1 ships; credits stay DRAFT until John
   approves them.
5. **The Problemata**: separate sourcing task after phase 3.
6. **Alternate translations in the picker**: a later wave.

Added 2026-09-27 (John): "trim to what DK quotes", for every source, and no
Stephanus or Bekker division ("just have the part translating the DK
greek"). A span may carry `trim` (`start`, `end`, `omit`) and `alt_trims`;
the cuts sit on top of the sentence-keep above. Field rules are in the
module docstring of `pipeline/reader_pipeline/stage1_context_english.py`.

Later the same day (John): cut a long sentence to the clause DK quotes,
with "…" at each cut; extend English that stops short of DK's words, from
the same translation, widening the locus by the least needed; keep a whole
English verse where DK elides part of it. Jowett's store is aligned by
speaker turn, so a Plato span may carry `alt_loci` (`{"jowett": "<locus>"}`)
to draw his rendering from the neighbouring Stephanus key instead of
dropping him. Galen's *On the Natural Faculties* (Brock, Loeb 1916) is a
new source, vendored in `sources/brock-galen/`.

---

## Held spans

Leucippus A18 (Metaphysics 1071b31-1071b34): restored on 2026-09-25 after the store correction. Held out earlier that day because the stored Ross text read "they do say" where the Greek means "they do not say"; the span waited on the store correction, and its bold was re-cut to the corrected text.

```json
{
  "source_author": "Aristotle",
  "source_work": "Metaphysics",
  "locus": "1071b31-1071b34",
  "status": "translated",
  "translation_credit": "Ross, 1924",
  "emphasis": [
    "This is why some suppose eternal actuality-e.g. Leucippus and Plato; for they say there is always movement. But why and what this movement is they do say, nor, if the world moves in this way or that, do they tell us the cause of its doing so."
  ]
}
```

Heraclitus A4 (Rhetoric 1407b11-1407b18): held out 2026-09-25 on John's word ("let me check later for another"). DK's Greek has words that reverse one clause about connecting particles; Freese translates a text without them.

```json
{
  "source_author": "Aristotle",
  "source_work": "Rhetoric",
  "locus": "1407b11-1407b18",
  "status": "translated",
  "translation_credit": "Freese, 1926",
  "emphasis": [
    "Generally speaking, that which is written should be easy to read or easy to utter, which is the same thing. Now, this is not the case when there is a number of connecting particles, or when the punctuation is hard, as in the writings of Heraclitus. For it is hard, since it is uncertain to which word another belongs, whether to that which follows or that which precedes; for instance, at the beginning of his composition he says: Of this reason which exists always men are ignorant, where it is uncertain whether always should go with which exists or with are ignorant."
  ]
}
```

Also awaiting John (2026-09-25): the strict bold-gap rule ("I have to see later").

Resolved 2026-09-26:

- Heraclitus A4: authored in Freese by John's ruling ("show Freese, bold only the rest"). DK's <ἔχουσιν, οἱ δ' ὀλίγοι> is an editor's addition no pre-1931 translation renders (Freese, Roberts, Jebb, Welldon, Buckley, Taylor, Gillies checked); the clause built on it, "Now, this is not the case when there is a number of connecting particles,", stays unbolded. **Revised the same day (John): the whole passage is bolded. Ross's Greek text of the Rhetoric (Oxford Classical Texts, 1959) does not have the addition, so the bold follows that text, not DK's supplement.**
- Zeno A14: Owen's translation (Bohn, 1853), which renders DK's Ζήνων as "(Zeno)"; Pickard-Cambridge follows a text without the name (Ross's OCT brackets it). `"translation": "owen"`.
- Democritus A46a: Thomas Taylor's translation, quoted in full in his Dissertation on the Philosophy of Aristotle (London, 1812); Stocks drops Democritus, whom every Greek text names. `"translation": "taylor"`; credit "Taylor, 1812" (John's ruling).

Held 2026-09-26 (phase 4; for John):

- Democritus A38 (On Generation and Corruption 327a16-327a20): DK prints μεταβαλὸν; Joachim translates the other reading (μεταταχθὲν), so his English does not render it. **Ruled 2026-09-26 (John): authored; bold "but we see … to the solid state", the "grouping or position" clause unbolded.**
- Democritus A57 (Metaphysics 1069b22-1069b23): Ross's English makes "all things were together potentially" Aristotle's correction of Democritus; DK prints it as Democritus's own claim. Bolding it would contradict DK's attribution. **Ruled 2026-09-26 (John): authored; bold "and the account given by Democritus" and the quoted formula, since Ross's quotation marks show it is not Aristotle's own words.**

Pythagoras 7 ("look for alt trans"): authored 2026-09-26 in M'Mahon's translation (Bohn, 1857), which renders the Alcmaeon dating clause Ross omits; the span names `"translation": "mmahon"` and takes its text from `sources/aristotle-english/alternates.json`. Grok checked the bold and the passage against the Greek (all pass). The credit "M'Mahon, 1857" is DRAFT until John approves it.

## Appendix — method and full census

### Method

- **Census input:** every `build/dist/*-testimonia/book-*.json` segment.
  First cited source = first `authorDisplay` in `expandedCitation`, in
  document order (nested lists flattened).
- **Run splitting:** the column's `role: "context"` Greek lines, joined, are
  cut at every citation head — a stretch with no Greek letters that holds a
  Latin letter and a digit (Greek capital book numerals in heads are masked
  first). A head starts a new run only if it carries a Bekker locus or an
  author abbreviation in capitals; bracketed cross-references inside a quote
  (`[B 1]`, `c. 2.`) do not. A head naming Aristotle (`ARISTOT.`, `ARIST.`,
  `AR.`, `[ARISTOT.]`), or a dash/work-only head right after an Aristotle
  run, is an Aristotle run; a head naming Aristotle and another author is
  "pointer only". The work comes from the head's Latin abbreviation, else
  from the previous run, else from the expanded citation's title.
- **Locating:** the alignment in B.2. Window: three lines before the cited
  line through two more columns, in the mounted `build/dist/<Abbr>` Greek.
- **Known limits:** the splitter is heuristic. Some low-coverage rows are
  two sources run together, not a bad locus. Extents are proposals for the
  Opus reader, not findings about DK.

### A.1 detail — columns whose first cited source is Aristotle (one row per Aristotle run)

| # | DK work | Col | First author | Aristotle run: work | DK locus | Greek extent found in store | Coverage | Note |
|---:|---|---|---|---|---|---|---:|---|
| 1 | anaxagoras | A28 | Aristotle | Metaphysics | 1009b25 | 1009b26–1009b27 | 1.00 |  |
| 2 | anaxagoras | A30 | Aristotle | Nic. Ethics | 1141b3 | 1141b3–1141b8 | 1.00 |  |
| 3 | anaxagoras | A30 | Aristotle | Nic. Ethics | 1179a13 | 1179a13–1179a15 | 1.00 |  |
| 4 | anaxagoras | A43 | Aristotle | Metaphysics | 984a11 | 984a11–984a16 | 0.98 |  |
| 5 | anaxagoras | A43 | Aristotle | On the Heavens | 302a28 | 302a28–302b5 | 0.97 |  |
| 6 | anaxagoras | A45 | Aristotle | Physics | 203a19 | 203a19–203a24 | 0.91 |  |
| 7 | anaxagoras | A46 | Aristotle | Gen. and Corr. | 314a18 | 314a18–314a21 | 0.12 (low) |  |
| 8 | anaxagoras | A50 | Aristotle | Physics | 205b1 | 205b1–205b4 | 0.91 |  |
| 9 | anaxagoras | A52 | Aristotle | Physics | 187a26 | 187a26–187a30 | 0.94 |  |
| 10 | anaxagoras | A52 | Aristotle | Gen. and Corr. | 314a11 | 314a11–314a15 | 0.56 (low) |  |
| 11 | anaxagoras | A56 | Aristotle | Physics | 256b24 | 256b24–256b27 | 0.93 |  |
| 12 | anaxagoras | A58 | Aristotle | Metaphysics | 984b15 | 984b15–984b20 | 0.93 |  |
| 13 | anaxagoras | A60 | Aristotle | Metaphysics | 1056b28 | 1056b28–1056b32 | 1.00 |  |
| 14 | anaxagoras | A68 | Aristotle | On the Heavens | 309a19 | 309a19–309a20 | 1.00 |  |
| 15 | anaxagoras | A68 | Aristotle | Physics | 213a22 | 213a22–213a27 | 0.98 |  |
| 16 | anaxagoras | A69 | [Aristotle] | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| 17 | anaxagoras | A74 | [Aristotle] | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| 18 | anaxagoras | A80 | Aristotle | Meteorology | 345a25 | 345a25–345a31 | 0.70 (low) |  |
| 19 | anaxagoras | A81 | Aristotle | Meteorology | 342b25 | 342b25–342b31 | 0.74 (low) |  |
| 20 | anaxagoras | A84 | Aristotle | Meteorology | — | — |  | no Bekker locus (chapter only) |
| 21 | anaxagoras | A84 | Aristotle | Meteorology | 369b14 | 369b14–369b19 | 0.45 (low) |  |
| 22 | anaxagoras | A88 | Aristotle | On the Heavens | 295a9 | 295a9–295a14 | 0.95 |  |
| 23 | anaxagoras | A89 | Aristotle | Meteorology | 365a14 | 365a14–365a34 | 0.79 (low) |  |
| 24 | anaxagoras | A94 | Aristotle | Nic. Ethics | 1154b7 | 1154b7–1154b8 | 0.83 |  |
| 25 | anaxagoras | A99 | Aristotle | De Anima | 404a25 | 404a25–404a27 | 1.00 |  |
| 26 | anaxagoras | A100 | Aristotle | De Anima | 404b1 | 404b1–404b6 | 0.91 |  |
| 27 | anaxagoras | A100 | Aristotle | De Anima | 405a13 | 405a13–405a19 | 0.91 |  |
| 28 | anaxagoras | A100 | Aristotle | De Anima | 405b19 | 405b20–405b21 | 1.00 |  |
| 29 | anaxagoras | A100 | Aristotle | De Anima | 429a18 | 429a18–429a19 | 1.00 |  |
| 30 | anaxagoras | A102 | Aristotle | Parts of Animals | 687a7 | 687a8–687a12 | 0.95 |  |
| 31 | anaxagoras | A105 | Aristotle | Parts of Animals | 677a5 | 677a5–677a9 | 1.00 |  |
| 32 | anaxagoras | A107 | Aristotle | Gen. of Animals | 763b30 | 763b30–764a1 | 0.98 |  |
| 33 | anaxagoras | A114 | Aristotle | Gen. of Animals | 756b13 | 756b14–756b18 | 0.97 |  |
| 34 | anaxagoras | A115 | Aristotle | Respiration (Juv) | 470b30 | 470b31–471a2 | 0.98 |  |
| 35 | anaximander | A15 | Aristotle | Physics | 203b6 | 203b6–203b26 | 0.96 |  |
| 36 | anaximander | A26 | Aristotle | On the Heavens | 295b10 | 295b11–295b16 | 0.98 |  |
| 37 | anaximander | A27 | Aristotle | Meteorology | 353b6 | 353b6–353b11 | 0.98 |  |
| 38 | anaximenes | A4 | Aristotle | Metaphysics | 984a5 | 984a5–984a6 | 1.00 |  |
| 39 | anaximenes | A21 | Aristotle | Meteorology | 365b6 | 365b6–365b12 | 0.96 |  |
| 40 | critias | A8 | Aristotle | Rhetoric | 1375b32 | 1375b31–1375b34 | 1.00 |  |
| 41 | critias | A14 | Aristotle | Rhetoric | 1416b26 | 1416b27–1416b29 | 1.00 |  |
| 42 | critias | A23 | Aristotle | De Anima | 405b5 | 405b5–405b7 | 1.00 |  |
| 43 | democritus | A7 | Aristotle | Meteorology | 365a17 | 365a17–365a19 | 1.00 |  |
| 44 | democritus | A35 | Aristotle | Gen. and Corr. | 315a34 | 315a34–315b1 | 0.96 |  |
| 45 | democritus | A36 | Aristotle | Parts of Animals | 642a24 | 642a24–642a30 | 0.98 |  |
| 46 | democritus | A36 | Aristotle | Metaphysics | 1078b19 | 1078b19–1078b21 | 1.00 |  |
| 47 | democritus | A41 | Aristotle | Physics | 203a33 | 203a33–203b2 | 0.96 |  |
| 48 | democritus | A42 | Aristotle | Metaphysics | 1039a9 | 1039a9–1039a11 | 1.00 |  |
| 49 | democritus | A42 | Aristotle | Gen. and Corr. | 318b6 | 318b6–318b7 | 1.00 |  |
| 50 | democritus | A45 | Aristotle | Physics | 188a22 | 188a22–188a26 | 0.94 |  |
| 51 | democritus | A46a | Aristotle | On the Heavens | 305b1 | 305b1–305b19 | 0.98 |  |
| 52 | democritus | A48b | Aristotle | Gen. and Corr. | 316a13 | 316a13–316b16 | 0.97 |  |
| 53 | democritus | A58 | Aristotle | Physics | 265b24 | 265b24–265b25 | 1.00 |  |
| 54 | democritus | A60 | Aristotle | Gen. and Corr. | 326a9 | 326a9–326a10 | 1.00 |  |
| 55 | democritus | A60 | Aristotle | On the Heavens | 309a1 | 309a1–310a11 | 0.99 |  |
| 56 | democritus | A60a | Aristotle | On the Heavens | 303a25 | 303a25–303a29 | 1.00 |  |
| 57 | democritus | A62 | Aristotle | On the Heavens | 313a21 | 313a21–313b5 | 0.94 |  |
| 58 | democritus | A63 | Aristotle | Gen. and Corr. | 323b10 | 323b10–323b15 | 0.96 |  |
| 59 | democritus | A65 | Aristotle | Physics | 252a32 | 252a32–252b1 | 0.90 |  |
| 60 | democritus | A68 | Aristotle | Physics | 195b36 | 195b36–196a3 | 0.90 |  |
| 61 | democritus | A71 | Aristotle | Physics | 251b16 | 251b15–251b17 | 1.00 |  |
| 62 | democritus | A91 | Aristotle | Meteorology | — | — |  | pointer only: DK quotes another author |
| 63 | democritus | A97 | Aristotle | Meteorology | 365a1 | 365b1–365b6 | 0.96 |  |
| 64 | democritus | A100 | Aristotle | Meteorology | 356b4 | 356b4–356b21 | 0.99 |  |
| 65 | democritus | A101 | Aristotle | De Anima | 404a27 | 404a27–404a31 | 0.93 |  |
| 66 | democritus | A101 | Aristotle | De Anima | 405a5 | 405a5–405a13 | 0.99 |  |
| 67 | democritus | A104 | Aristotle | De Anima | 406b15 | 406b15–406b22 | 0.95 |  |
| 68 | democritus | A104a | Aristotle | De Anima | 409a32 | 409b1–409b4 | 0.87 |  |
| 69 | democritus | A106 | Aristotle | Respiration (Juv) | 471b30 | 471b30–472a18 | 0.96 |  |
| 70 | democritus | A112 | Aristotle | Metaphysics | 1009b7 | 1009b7–1009b15 | 0.92 |  |
| 71 | democritus | A119 | Aristotle | Sense and Sensibilia | 442a29 | 442a29–442b3 | 0.94 |  |
| 72 | democritus | A121 | Aristotle | Sense and Sensibilia | 438a5 | 438a5–438a12 | 0.96 |  |
| 73 | democritus | A122 | Aristotle | De Anima | 419a15 | 419a15–419a17 | 0.95 |  |
| 74 | democritus | A123 | Aristotle | Gen. and Corr. | 316a1 | 316a2 | 0.86 |  |
| 75 | democritus | A126 | Aristotle | Sense and Sensibilia | 442b11 | 442b11–442b12 | 1.00 |  |
| 76 | democritus | A143 | Aristotle | Gen. of Animals | 764a6 | 764a7–764a11 | 0.92 |  |
| 77 | democritus | A144 | Aristotle | Gen. of Animals | 740a33 | 740a33–740a37 | 0.97 |  |
| 78 | democritus | A144 | Aristotle | Gen. of Animals | 746a19 | 746a19–746a21 | 0.36 (low) |  |
| 79 | democritus | A148 | Aristotle | Parts of Animals | 665a30 | 665a30–665a33 | 0.92 |  |
| 80 | democritus | A149 | Aristotle | Gen. of Animals | 747a29 | 747a29–747a31 | 0.91 |  |
| 81 | democritus | A150 | [Aristotle] | Hist. of Animals | 623a30 | 623a30–623a33 | 1.00 |  |
| 82 | empedocles | A4 | Aristotle | De Anima | 405b1 | 405b1–405b5 | 1.00 |  |
| 83 | empedocles | A6 | Aristotle | Metaphysics | 984a11 | 984a11–984a13 | 0.95 |  |
| 84 | empedocles | A17 | [Aristotle] | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| 85 | empedocles | A22 | Aristotle | Poetics | 1447b17 | 1447b17–1447b19 | 1.00 |  |
| 86 | empedocles | A28 | Aristotle | Metaphysics | 984a8 | 984a8–984a11 | 0.97 |  |
| 87 | empedocles | A36 | Aristotle | Gen. and Corr. | 330b19 | 330b19–330b21 | 0.95 |  |
| 88 | empedocles | A37 | Aristotle | Metaphysics | 985a21 | 985a21–985b3 | 0.96 |  |
| 89 | empedocles | A38 | Aristotle | Physics | 252a7 | 252a7–252a9 | 1.00 |  |
| 90 | empedocles | A39 | Aristotle | Metaphysics | 984b32 | 984b32–985a10 | 0.99 |  |
| 91 | empedocles | A40 | Aristotle | Gen. and Corr. | 333b19 | 333b19–333b22 | 1.00 |  |
| 92 | empedocles | A42 | Aristotle | On the Heavens | 301a14 | 301a14–301a20 | 1.00 |  |
| 93 | empedocles | A42 | Aristotle | Gen. and Corr. | 334a5 | 334a5–334a7 | 1.00 |  |
| 94 | empedocles | A43 | Aristotle | Gen. and Corr. | 334a26 | 334a26–334a31 | 0.55 (low) |  |
| 95 | empedocles | A43a | Aristotle | On the Heavens | 305a1 | 305a1–305a4 | 0.96 |  |
| 96 | empedocles | A46 | Aristotle | Physics | 187a20 | 187a20–187a26 | 0.97 |  |
| 97 | empedocles | A57 | Aristotle | De Anima | 418b20 | 418b20–418b26 | 1.00 |  |
| 98 | empedocles | A57 | Aristotle | Sense and Sensibilia | 446a26 | 446a26–446a28 | 1.00 |  |
| 99 | empedocles | A63 | Aristotle | Meteorology | 369b12 | 369b12–369b14 | 0.42 (low) |  |
| 100 | empedocles | A67 | Aristotle | On the Heavens | 295a13 | 295a13–295a21 | 0.99 |  |
| 101 | empedocles | A69 | [Aristotle] | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| 102 | empedocles | A73 | Aristotle | Respiration (Juv) | 477a32 | 477a32–477b2 | 0.92 |  |
| 103 | empedocles | A81 | Aristotle | Gen. of Animals | 764a1 | 764a1–764a15 | 0.95 |  |
| 104 | empedocles | A81 | Aristotle | Gen. of Animals | 765a8 | 765a9–765a12 | 0.14 (low) |  |
| 105 | empedocles | A82 | Aristotle | Gen. of Animals | 747a24 | 747a24–747a30 | 0.57 (low) |  |
| 106 | empedocles | A87 | Aristotle | Gen. and Corr. | 324b26 | 324b26–324b35 | 0.99 |  |
| 107 | empedocles | A91 | Aristotle | Sense and Sensibilia | 437b9 | 437b9–437b14 | 0.91 |  |
| 108 | empedocles | A91 | Aristotle | Gen. of Animals | 779b15 | 779b15–779b20 | 0.98 |  |
| 109 | gorgias | A23 | Aristotle | Rhetoric | 1406b14 | 1406b15–1406b19 | 1.00 |  |
| 110 | gorgias | A29 | Aristotle | Rhetoric | 1404a24 | 1404a24–1404a28 | 0.97 |  |
| 111 | heraclitus | A4 | Aristotle | Rhetoric | 1407b11 | 1407b11–1407b18 | 0.84 |  |
| 112 | heraclitus | A5 | Aristotle | Metaphysics | — | — |  | pointer only: DK quotes another author |
| 113 | heraclitus | A7 | Aristotle | Metaphysics | 1005b23 | 1005b23–1005b25 | 1.00 |  |
| 114 | heraclitus | A9 | Aristotle | Parts of Animals | 645a17 | 645a17–645a23 | 0.92 |  |
| 115 | heraclitus | A15 | Aristotle | De Anima | 405a24 | 405a25–405a26 | 1.00 |  |
| 116 | leucippus | A6 | Aristotle | Metaphysics | 985b4 | 985b4–985b20 | 0.95 |  |
| 117 | leucippus | A7 | Aristotle | Gen. and Corr. | 324b35 | 324b35 | 0.80 |  |
| 118 | leucippus | A7 | Aristotle | Gen. and Corr. | 325a1 | 325a1–325a5 | 0.98 |  |
| 119 | leucippus | A7 | Aristotle | Gen. and Corr. | 325a23 | 325a23–325b11 | 0.98 |  |
| 120 | leucippus | A7 | Aristotle | Gen. and Corr. | 325b24 | 325b24–325b33 | 0.95 |  |
| 121 | leucippus | A9 | Aristotle | Gen. and Corr. | 314a21 | 314a21–314a24 | 1.00 |  |
| 122 | leucippus | A9 | Aristotle | Gen. and Corr. | 315b6 | 315b6–315b15 | 0.91 |  |
| 123 | leucippus | A16 | Aristotle | On the Heavens | 300b8 | 300b8–300b11 | 0.89 |  |
| 124 | leucippus | A18 | Aristotle | Metaphysics | 1071b31 | 1071b32–1071b34 | 0.96 |  |
| 125 | leucippus | A19 | Aristotle | On the Heavens | 275b29 | 275b29–276a1 | 0.93 |  |
| 126 | leucippus | A19 | Aristotle | Physics | 213a27 | 213a27–213b22 | 0.96 |  |
| 127 | leucippus | A28 | Aristotle | De Anima | 404a1 | 404a1–404a17 | 0.90 |  |
| 128 | melissus | A5 | Aristotle | MXG | — | — |  | no Bekker locus (chapter only) |
| 129 | melissus | A7 | Aristotle | Metaphysics | 986b25 | 986b25–986b28 | 0.93 |  |
| 130 | melissus | A7 | Aristotle | Physics | 186a6 | 186a6–186a10 | 1.00 |  |
| 131 | melissus | A10 | Aristotle | Soph. Refutations | 167b13 | 167b13–167b18 | 1.00 |  |
| 132 | melissus | A10 | Aristotle | Soph. Refutations | 168b35 | 168b35–168b40 | 0.94 |  |
| 133 | melissus | A11 | Aristotle | Physics | 185a32 | 185a32–185b3 | 0.81 |  |
| 134 | parmenides | A6 | Aristotle | Metaphysics | 986b22 | 986b22 | 1.00 |  |
| 135 | parmenides | A24 | Aristotle | Metaphysics | 986b18 | 986b19–987a2 | 0.97 |  |
| 136 | parmenides | A24 | Aristotle | Metaphysics | 1010a1 | 1010a1–1010a3 | 1.00 |  |
| 137 | parmenides | A25 | Aristotle | On the Heavens | 298b14 | 298b14–298b24 | 0.99 |  |
| 138 | parmenides | A25 | Aristotle | Gen. and Corr. | 325a13 | 325a13–325a19 | 0.73 (low) |  |
| 139 | parmenides | A27 | Aristotle | Physics | 207a9 | 207a9–207a16 | 0.96 |  |
| 140 | parmenides | A35 | Aristotle | Gen. and Corr. | 330b13 | 330b13–330b15 | 0.95 |  |
| 141 | parmenides | A35 | Aristotle | Gen. and Corr. | 336a3 | 336a3–336a6 | 0.97 |  |
| 142 | parmenides | A52 | Aristotle | Parts of Animals | 648a25 | 648a25–648a31 | 1.00 |  |
| 143 | prodicus | A12 | Aristotle | Rhetoric | 1415b12 | 1415b12–1415b17 | 0.93 |  |
| 144 | prodicus | A19 | Aristotle | Topics | 112b22 | 112b21–112b24 | 0.93 |  |
| 145 | protagoras | A17 | Aristotle | Metaphysics | 1046b29 | 1046b29–1047a8 | 0.98 |  |
| 146 | protagoras | A21 | Aristotle | Rhetoric | 1402a23 | 1402a24–1402a29 | 0.63 (low) |  |
| 147 | protagoras | A27 | Aristotle | Rhetoric | 1407b6 | 1407b6–1407b7 | 0.88 |  |
| 148 | protagoras | A29 | Aristotle | Poetics | 1456b15 | 1456b15–1456b18 | 0.96 |  |
| 149 | pythagoras | 7 | Aristotle | Metaphysics | 986a29 | 986a29 | 0.22 (low) |  |
| 150 | thales | A10 | Aristotle | Politics | 1259a6 | 1259a5–1259a18 | 0.96 |  |
| 151 | thales | A12 | Aristotle | Metaphysics | 983b6 | 983b6–983b33 | 0.94 |  |
| 152 | thales | A14 | Aristotle | On the Heavens | 294a28 | 294a28–294a33 | 1.00 |  |
| 153 | thales | A22 | Aristotle | De Anima | 411a7 | 411a7–411a8 | 0.72 (low) |  |
| 154 | thales | A22 | Aristotle | De Anima | 405a19 | 405a19–405a21 | 0.95 |  |
| 155 | xenophanes | A12 | Aristotle | Rhetoric | 1399b5 | 1399b5–1399b9 | 0.97 |  |
| 156 | xenophanes | A13 | Aristotle | (no work named) | — | — |  | DK names no work |
| 157 | xenophanes | A14 | Aristotle | Rhetoric | 1377a19 | 1377a19–1377a21 | 0.96 |  |
| 158 | xenophanes | A15 | Aristotle | Metaphysics | 1010a4 | 1010a5–1010a6 | 1.00 |  |
| 159 | xenophanes | A28 | [Aristotle] | MXG | — | — |  | no Bekker locus (chapter only) |
| 160 | xenophanes | A30 | Aristotle | Metaphysics | 986b18 | 986b19–986b27 | 0.98 |  |
| 161 | xenophanes | A47 | Aristotle | On the Heavens | 294a21 | 294a21–294a25 | 0.36 (low) |  |
| 162 | xenophanes | A48 | [Aristotle] | Mirab. | 833a15 | 833a15–833a17 | 0.82 |  |
| 163 | zeno | A5 | Aristotle | Rhetoric | 1372b3 | 1372b3–1372b5 | 1.00 |  |
| 164 | zeno | A14 | Aristotle | Soph. Refutations | 170b19 | 170b20–170b25 | 0.93 |  |
| 165 | zeno | A21 | Aristotle | Metaphysics | 1001b7 | 1001b7–1001b13 | 1.00 |  |
| 166 | zeno | A22 | [Aristotle] | Lin. Insec. | 968a18 | 968a18–968a23 | 0.97 |  |
| 167 | zeno | A22 | [Aristotle] | Physics | 187a1 | 187a1–187a3 | 0.89 |  |
| 168 | zeno | A24 | Aristotle | Physics | 210b22 | 210b22–210b25 | 0.79 (low) |  |
| 169 | zeno | A24 | Aristotle | Physics | 209a23 | 209a23–209a25 | 0.92 |  |
| 170 | zeno | A28 | Aristotle | Physics | 239b33 | 239b33–240a18 | 0.69 (low) |  |
| 171 | zeno | A29 | Aristotle | Physics | 250a19 | 250a19–250a22 | 1.00 |  |

### A.2 detail — columns that cite Aristotle after another source (one row per Aristotle run)

| DK work | Col | First author | Has English | Aristotle run: work | DK locus | Greek extent found | Coverage | Note |
|---|---|---|---|---|---|---|---:|---|
| anaxagoras | A47 | Plato | yes | Metaphysics | 985a18 | 985a18–985a21 | 0.94 |  |
| anaxagoras | A55 | Plato | yes | De Anima | 405a15 | 405a15–405a19 | 0.92 |  |
| anaxagoras | A73 | Xenophon | no | On the Heavens | 270b24 | 270b24–270b25 | 0.83 |  |
| anaxagoras | A85 | Aëtius | no | Meteorology | 348b13 | 348b13–348b15 | 1.00 |  |
| anaxagoras | A85 | Aëtius | no | Meteorology | 348a14 | 348a14–348a20 | 0.97 |  |
| anaxagoras | A117 | Theophrastus | no | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| anaximander | A9 | Simplicius | no | Physics | 187a20 | 187a20–187a23 | 0.97 |  |
| anaximenes | A14 | (none parsed) | no | Meteorology | 354a28 | 354a29–354a32 | 0.52 |  |
| anaximenes | A20 | Aëtius | no | On the Heavens | 294b13 | 294b13–294b24 | 0.92 |  |
| democritus | A38 | Simplicius | no | Gen. and Corr. | 327a16 | 327a16–327a20 | 0.97 |  |
| democritus | A57 | Scholia in Basilium | no | Metaphysics | 1069b22 | 1069b22–1069b23 | 1.00 |  |
| democritus | A66 | Cicero | no | Gen. of Animals | 789b2 | 789b3–789b5 | 0.56 |  |
| democritus | A151 | Aelian | no | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| democritus | A151 | Aelian | no | Gen. of Animals | 747a29 | 747a29–747a31 | 0.91 |  |
| empedocles | A19 | Sextus Empiricus | no | Rhetoric | — | — |  | pointer only: DK quotes another author |
| empedocles | A25 | Scholia | no | Rhetoric | — | — |  | pointer only: DK quotes another author |
| empedocles | A44 | Aëtius | no | On the Heavens | — | — |  | no Bekker locus (chapter only) |
| empedocles | A52 | Aëtius | no | Metaphysics | 1000b18 | 1000b18–1000b20 | 0.88 |  |
| empedocles | A70 | Aëtius | no | De Anima | 415b28 | 415b28–416a2 | 0.97 |  |
| empedocles | A70 | Aëtius | no | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| empedocles | A78 | (none parsed) | no | Parts of Animals | 642a17 | 642a17–642a22 | 0.98 |  |
| empedocles | A78 | (none parsed) | no | De Anima | 408a13 | 408a13–408a23 | 0.97 |  |
| empedocles | A78 | (none parsed) | no | (Problemata, De plantis or De spiritu) | — | — |  | work not mounted |
| empedocles | A94 | Aëtius | no | Sense and Sensibilia | 441a3 | 441a3–441a6 | 0.94 |  |
| gorgias | A19 | Plato | yes | Politics | 1275b26 | 1275b26–1275b30 | 1.00 |  |
| heraclitus | A10 | Plato | yes | On the Heavens | 279b12 | 279b12–279b17 | 0.87 |  |
| heraclitus | A10 | Plato | yes | Physics | 205a3 | 205a3–205a4 | 0.86 |  |
| leucippus | A15 | Aëtius | no | On the Heavens | 303a4 | 303a3–303a16 | 0.98 |  |
| philolaus | A23 | Macrobius | no | De Anima | — | — |  | pointer only: DK quotes another author |
| protagoras | A19 | Plato | yes | Metaphysics | 1007b18 | 1007b18–1007b25 | 0.97 |  |
| protagoras | A19 | Plato | yes | Metaphysics | 1062b13 | 1062b13–1062b19 | 1.00 |  |
| pythagoras | 5 | Diogenes Laertius | yes | Rhetoric | 1398b9 | 1398b11–1398b17 | 1.00 |  |
