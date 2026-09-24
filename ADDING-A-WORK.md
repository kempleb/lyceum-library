> Adapted from aristotle-reader — copied as-is during the plato-reader bootstrap
> (2026-07-11), then generalized for the multi-author corpus (WP6). The core
> recipe (vendor sources, write a manifest, run the pipeline, register the
> work, build) holds for any author; where a step is genuinely scheme- or
> author-specific (Bekker-page vs. Stephanus citation, in particular) it is
> marked as such below rather than invented. The worked example below is
> still *De Anima* (Bekker-scheme, Aristotle); for a Stephanus-scheme (Plato)
> manifest's shape, see `docs/examples/Apology.yaml`.

# Adding a work to the corpus

The reader is a registry-driven complete-works site. Adding a work is a
configuration exercise — **no frontend code changes**. These are the steps,
using *De Anima* (slug `DA`, Bekker-scheme) as the worked example.

## 1. Vendor the sources (`sources/`)

*(Bekker-scheme specifics below — a Stephanus-scheme work's Greek export and
translation vendoring differ; see `manifests/Euthyphro.yaml`'s scheme-contract
commentary in a sister repo, or `docs/examples/Apology.yaml` here, for the
shape rather than inventing the recipe here.)*

- **Greek**: nothing to fetch if the TLG author export is already cached — the
  Diogenes verse-mode export emits one file per work (`tlg0086<work>.xml`) for the
  whole author. Confirm the work's file has `type="Bekker-page"` divs with numeric
  `<l n="…">` lines (the spine relies on this).
- **Chapter structure** (only if the work has no Bekker-milestoned English TEI):
  vendor the First1KGreek Greek TEI, e.g.
  `sources/tlg0086.tlg002.1st1K-grc1.xml`. Its `subtype="chapter"` divs are
  text-aligned onto the spine to recover each chapter's Bekker (column, line).
- **English** (chapter-anchored archive translation): one HTML file per book in
  `sources/<slug>-<translator>/book-0N.html`, e.g. `sources/da-smith/book-01.html`
  from the MIT Internet Classics Archive (the `TheMITTech/classics` GitHub mirror
  is the reliable source). Chapter markers are bare numbers (`1`) or `Part N`.

## 2. Write the manifest (`manifests/<SLUG>.yaml`)

Every manifest, regardless of author or citation scheme, carries these two
`work` fields (enforced by `pipeline/reader_pipeline/preflight.py`):

- `work.author` — the author **slug**, lowercase (e.g. `aristotle`, `plato`),
  used to group works by author across the corpus. Required.
- `work.language` — `grc` or `lat`, defaults to `grc` if omitted. It selects
  the source corpus and the lexicon: `grc` reads the TLG export and
  `greek-analyses.txt` + LSJ; `lat` reads the PHI export (`stage1_latin.py`,
  `latin.py`) and `latin-analyses.txt` + Lewis & Short. Latin is live: fourteen
  PHI works ship (Cicero, Seneca, Lucretius). A Latin manifest names the work by
  `phi_author`/`phi_work`, `latin_edition`, and `expected_sourcedesc` (checked
  verbatim against the PHI export, a fatal gate); copy `manifests/de-officiis.yaml`
  for a prose (book-section) work or `manifests/de-rerum-natura.yaml` for verse.
  Design notes: `docs/wave2-latin-design.md`. (Corrected 2026-09-09; this
  paragraph had said Latin was unsupported since before Wave 2.)

The rest of the manifest is scheme-specific. For a **Bekker-scheme** work
(Aristotle), copy `manifests/DA.yaml` and set:

- `work.id` = the slug (= URL + data dir), `tlg_work`, Bekker range, editions.
- `chapters.source: grc_tei` + the grc TEI filename (or omit for the Perseus-TEI
  path that EN uses).
- `english.primary` (and optional `secondary`): `model: archive`, the `dir`,
  `books` count, and `chapter_marker` (`number` or `part`).
- `books`: each book's Bekker `start`/`end`. Run `stage1`/`stage2` once and let
  the validator tell you the exact boundary lines (mid-column book starts and any
  edition line-number quirks go in `mid_column_book_starts` / `expected_line_gaps`).
- `proper_names` (optional): a cross-language spot-check list, or omit to skip it.

For a **Stephanus-scheme** work (Plato), the shape differs (`citation.scheme:
stephanus`, `english.primary` instead of `work.english_translation`, a
`section_spine` fingerprint, books bounded by section tokens instead of full
Bekker refs) — see `docs/examples/Apology.yaml` for the field-by-field shape;
that recipe is owned by the sister repo that built it out (see this repo's
`CLAUDE.md`) and is not duplicated here.

### (optional) Hand-keyed Bekker anchors

The archive English gutter is interpolated. To pin specific Bekker lines to the
true place in the translation, add `english.primary.anchors:
"<slug>-<translator>/anchors.yaml"` — a YAML list of
`{ bekker: "412a10", at: "a verbatim phrase from the translation" }`. Each
resolved anchor becomes a real gutter tick; interpolation only fills the gaps
between anchors. Zero anchors = all estimates; full anchors = Rackham-grade.

## 3. Run the pipeline

```bash
cd pipeline && uv run python -m reader_pipeline all --work <SLUG>
```

Emits `build/dist/<SLUG>/` (books, chapters, columns, analyses, search) and
merges this work's LSJ entries into the shared corpus-wide `build/dist/lsj/`
(one dictionary, not per-work). For the complete shared dictionary run a full
`npm run build:public` (it clears `build/dist` once, then every work accumulates
into `build/dist/lsj/`; `verify_shared_lsj` then checks every referenced key
resolves). Spot-check chapter placement against a couple of canonical Bekker anchors.

## 4. Register the work (`app/src/lib/works.ts`)

Add one `Work` entry to `WORKS`: `id` (= slug), `title`, `abbr`, `books`,
`bookLabels`, `greekEdition`, `translations` (each with a display `name`/`short`
and `slot`: `english` = primary parallel chunk, `ross` = secondary overlay), and
a one-line `blurb`. The home index, routing, reader work-switcher, and unified
search pick it up automatically.

## 5. Build

```bash
cd app && npm run build      # Node 22; getStaticPaths enumerates the new work
```

That's it — the new work appears on the home page, gets its reader route, and
joins unified search. No component code is touched.

## Variations (added for the Organon works — Categories, De Interpretatione)

All manifest-driven; no component changes needed unless noted.

- **Explicit chapters** — instead of a grc TEI, declare chapter starts as Bekker
  references in the manifest: `chapters: { source: explicit, list: [{n: 1,
  bekker: "1a1"}, …] }`. Use when the divisions are known exactly (e.g. keyed
  from a Bekker-stamped translation).
- **Two or three translations, each Bekker-keyed** — `english.primary` +
  `english.secondary` + optional `english.third`, each `model: archive` with its
  own `anchors:` file (a YAML list of `{bekker, at: "verbatim phrase"}`). Dense
  anchors give every overlay translation a real per-segment Bekker gutter. The
  `third` slot needs a `slot: 'third'` entry in works.ts.
- **Copyright gating** — for a work with a copyrighted translation: keep `<Work>.yaml`
  (all translations, local) AND `<Work>-public.yaml` (PD only). Flag the
  copyrighted registry entry `private: true` (it's dropped at compile time when
  the app is built with `PUBLIC_HIDE_PRIVATE=1`). Deploy = rebuild data with
  `--work <Work>-public` + build the app with `PUBLIC_HIDE_PRIVATE=1`, so the
  copyrighted text never enters the published data, search index, or bundle.
- **Single-book (bookless) works** — set `books: 1`. The work routes at `/<slug>`
  (no `/book/1`), with no book-level navigation (`isBookless`/`workPath` in
  works.ts handle this automatically).
- **Inline tables** — Greek lines with the `⎪` (U+23AA) divider render as 2-col
  tables automatically (stage7 `_greek_cells`). A translation's diagrams render
  as grids if you provide `sources/<dir>/tables.json` (a list of
  `{bekker, rows: [[cells]]}`), attached by Bekker line.
