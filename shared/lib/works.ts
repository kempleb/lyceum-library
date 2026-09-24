// The corpus registry — the single source of truth for which works the site
// carries. Adding a work is one entry here (plus its pipeline data under
// build/dist/<id>/). Everything else — routing, the home index, the reader's
// work switcher, unified search — is driven off this list.
//
// `id` is the URL slug AND the data directory name; it is a readable
// CamelCase slug matching the manifest filename (Euthyphro, Alcibiades1),
// established by the Euthyphro pilot rather than a Bekker-style abbreviation.
//
// `translations[].slot` says which emitted segment field the reader renders for
// that translation: 'english' is the primary parallel chunk, 'secondary' a
// second chapter-anchored overlay, 'third' an optional third overlay, and
// 'overlay' any further overlay (4th onward) read from seg.overlays[id] — so a
// work can carry any number of translations. The picker lists them in
// registry order.
//
// Companion registry: shared/lib/authors.ts holds the AUTHORS this file's
// `Work.author` refs resolve against (getAuthor(work.author)).

import { AUTHOR_PERIOD_ORDER, AUTHORS, PERIOD_LABEL, getAuthor } from './authors';
import {
  AUTHOR_WORK_GROUPS_DATA,
  CORPUS_WORKS,
  FIXTURE_WORKS,
  START_HERE_DATA,
  WORK_CORPUS_DATA,
} from './registry.generated';

export interface TranslationRef {
  id: string;
  name: string;     // full citation, for the picker + attribution
  short: string;    // chip label
  slot: 'english' | 'secondary' | 'third' | 'overlay';
  // Carries inline `[^N]` footnote markers + a footnotes.json popup map.
  // Independent of slot — the reader renders the markers for whichever
  // translation sets this.
  footnotes?: boolean;
  // Copyright-encumbered translations carried only in the local/full build.
  // The public deploy sets PUBLIC_HIDE_PRIVATE=1 to drop them from the registry
  // (and is built from the work's -public manifest, so their text is absent too).
  private?: boolean;
  // Marks a translation as a SUMMARY rather than a full translation (e.g.
  // Gorgias B11/B11a's freeman-summary overlay — Freeman's own displaced
  // Ancilla summary, offered back as a sparse alternate beside the
  // Parnassos-style credited swap). Fix round, finding 6 (Sol xhigh
  // review): Reader.svelte's per-passage picker reads this to label a
  // copy of the summary text distinctly from a copy of an actual
  // translation (`data-eng-credit` gets "<name> (summary)"), so the two
  // are never indistinguishable once copied out of the reader.
  kind?: 'summary';
  // Translator's full name, for catalog interchange (e.g. the Lyceum partner
  // manifest). Optional; not shown in the reader itself.
  translator?: string;
  // Recorded licence status for THIS translation, when the manifest/vendor
  // correction declares one (e.g. Ostwald's Nicomachean Ethics, public
  // domain by lapsed copyright — see POST_VENDOR_CORRECTIONS in
  // scripts/vendor-aristotle-registry.mjs). Absent means "unverified": no
  // public-domain or CC claim is made for it. attribution.astro reads
  // `status === 'cc'` to show a licence badge/link next to that translation;
  // every other status (or no license at all) renders nothing, per John's
  // 2026-09-23 ruling against blanket public-domain claims.
  license?: {
    status: 'public-domain-us' | 'cc' | 'unverified' | string;
    name?: string;   // display licence name, e.g. "CC BY-NC-ND 4.0"
    url?: string;    // licence deed link
    rationale?: string;
  };
}

// A gap in a work's book sequence worth annotating in the reader (e.g. the
// Aristotelian Eudemian Ethics' "common books", shared with the Nicomachean
// Ethics and not reprinted). Unused while WORKS is empty (Phase 0), but the
// field/type stay as generic multi-book infrastructure for later waves.
export interface MissingBooks {
  after: number;      // render the note after this (contiguous) book index
  label: string;      // the missing books' labels, e.g. 'IV–VI'
  note: string;       // one line explaining the gap
  linkWork: string;   // id of the work that carries the text (e.g. 'EN')
  linkBook: number;   // book to jump to in that work
  linkLabel: string;  // link text, e.g. 'Nicomachean Ethics V–VII'
}

export interface Work {
  id: string;       // data dir (and URL slug, unless `slug` overrides it below), e.g. 'Euthyphro'
  // URL segment within the author's namespace, when it must differ from
  // `id` — needed once two works share an id PREFIX under one author (DK's
  // `<author>-fragments`/`<author>-testimonia` id pattern: `id` stays
  // globally unique and IS the data directory, e.g. 'heraclitus-fragments'
  // publishing at the shorter, un-duplicated '/heraclitus/fragments').
  // Defaults to `id` when omitted (every pre-DK work). A registry test
  // asserts slug uniqueness WITHIN each author (workSlug never needs to be
  // globally unique — only `id` does).
  slug?: string;
  title: string;
  greekTitle?: string;  // polytonic Greek title, shown in the print masthead
  abbr: string;     // display abbreviation (may differ from id styling)
  // Slug ref into shared/lib/authors.ts's AUTHORS registry (e.g.
  // 'marcus-aurelius'), resolved via getAuthor(work.author). Formerly held
  // the author's bare display name ('Plato') back when this registry carried
  // a single author; every work now names its author by id, not by label.
  author: string;
  language: 'grc' | 'lat';
  workType: 'continuous' | 'fragments' | 'verse' | 'letters';
  books: number;
  bookLabels: string[];   // per-book display labels (Arabic for a bookless work)
  missingBooks?: MissingBooks;  // annotate a gap in the book sequence
  // The noun for one division of this work, when it isn't a "book" -- e.g.
  // Seneca's Epistulae Morales ('letter') or De Providentia/De Constantia
  // Sapientis ('chapter', single dialogues stored as PHI chapters, not real
  // books). Default (omitted) = 'book'. Drives both the reader's "Book"/
  // "Letter"/"Chapter" chrome (ReaderShell.astro) and the URL division id
  // (divisionId below) from the one field, so the two can't disagree.
  // Ruling: John, 2026-09-12.
  divisionNoun?: 'letter' | 'chapter';
  greekEdition: string;
  // The print edition the TLG text was digitised from, in two lengths: `short`
  // for the reader's bilingual strip, `full` for the Greek-only strip and the
  // Texts & Licences page (both driven off this one field so they can't drift).
  greekSource: { short: string; full: string };
  translations: TranslationRef[];
  // Which translation the reader shows by default (a translations[].id). When
  // omitted the reader falls back to the primary 'english'-slot translation.
  defaultTranslation?: string;
  // Fix round, finding 3 (Sol xhigh review): a brief prose note naming
  // translator(s) whose PER-CHUNK credit (EnglishChunk.credit — the DK
  // column_sources override) displaces the primary translation for
  // specific passages within this work (Gorgias B11/B11a's swap to the
  // Parnassos Press translators). Landing.astro's work-level "translated
  // by" line is built entirely from `translations` (visibleTranslations),
  // which never sees these per-segment overrides — its static build has no
  // access to segment data at all (only chapter/section OUTLINE counts).
  // Rather than duplicate the override translators' names as a literal
  // string in the astro template, they live here once and Landing appends
  // this note after the primary translator name(s). Absent for every work
  // with no such override (every work but Gorgias' fragments today).
  alsoCredits?: string;
  blurb: string;    // one line for the home index
  // Most works are cited by Bekker (column:line). Plato is cited by Stephanus
  // page + section only — no user-facing line numbers at all (see
  // shared/lib/citation.ts). Default (omitted) = bekker.
  citation?: {
    // Mirrors SchemeId in shared/lib/citation.ts (kept as a literal union
    // here because citation.ts imports this module — no circular import).
    // ennead is the only remaining registered-but-unimplemented stub; dk
    // (Diels-Kranz), verse-line (Lucretius' DRN), and letter (Seneca's
    // Epistulae Morales, Wave 2 Batch 3) are all implemented.
    scheme: 'bekker' | 'busse' | 'stephanus' | 'book-section' | 'section' | 'dk' | 'verse-line' | 'ennead' | 'letter';
    hideLineNumbers?: boolean;
    // PILOT (2026-08-28, John's "why not default the greek to verse mode
    // here like with aristotle" — Discourses): a `book-section` work's
    // Greek normally flows continuously with each Loeb section's number
    // floated into the gutter at its wrapped-text position (Reader.svelte's
    // `bookSectionFlow`) — fine for Meditations' longer sections, but
    // Epictetus' short dialogic sections can land two section numbers on
    // the same wrapped row, so their gutter numbers collide. `linedGreek:
    // true` opts a single book-section work OUT of that scheme-wide flow
    // default and into the same block-per-section lineated rendering
    // Enchiridion's `section` scheme already uses (splitGreekSections +
    // the ordinary lineate branch) — one Greek block per TLG/Loeb section,
    // its number alone in the gutter, never sharing a row with another
    // section's number. Citation scheme/grammar is untouched (still
    // book-section, citations still "1.2"); this only changes layout.
    linedGreek?: boolean;
    // The opt-OUT twin of `linedGreek`, for works whose scheme lineates by
    // default (`section`, and any non-book-section scheme). John's criterion
    // (2026-08-31, on Epicurus' Letter to Menoeceus): "if this is not cited
    // by line numbers, then this needs prose reflow." A work cited by
    // chapter or section has no line axis for a print line to serve, so its
    // print lines align nothing while forcing one rendered line per print
    // line -- which at 375px wraps 91% of Menoeceus' lines into stubs
    // (`με-`/`λέτα`, `ἀλλό-`/`τριον`). Setting this true routes the work to
    // the ordinary prose-flow branch instead; quoted VERSE inside it still
    // renders as real lines (Reader.svelte's `isVerseLine`).
    //
    // A book-section work needs no such flag: lineation is opt-IN there, so
    // it reflows by simply setting `linedGreek: false` (as Lives does).
    proseReflow?: boolean;
    // The `indent(N)` level that means "ordinary paragraph opening" in THIS
    // edition -- everything deeper is quoted verse. Editions disagree, and
    // the disagreement is not cosmetic: the Greek works' exports start at
    // level 1 (lives 1..16, discourses 1..3, enchiridion 1..2), while every
    // Cicero export starts at 2 and has no level 1 at all (tusculans 2,4,5,7;
    // de-officiis 2,4,7; de-divinatione 2,4). So a bare `indent >= 2` test
    // reads Cicero's ordinary paragraph openings -- including every dialogue
    // turn, "Quid tandem?", "Utrisque." -- as verse. Default 1; the Cicero
    // works set 2. Pinned against the data by a test, so a re-export that
    // shifts an edition's levels fails loudly instead of silently restyling
    // a thousand paragraphs.
    proseIndent?: number;
    // Print-lineation rollout wave 1 (docs/lined-rollout-plan.md, Stage 3):
    // this work's Greek lines carry the print-line channel (sec/wrap/indent)
    // and must be painted with hyphen splits and section marks. One meaning,
    // unlike `linedGreek` above (which keeps its own single existing
    // meaning — forcing `lineate` for a book-section work — and its
    // `cscheme.id === 'book-section'` guard). Set on Enchiridion, the five
    // Epicurus works, and Discourses (which carries both flags).
    linedSource?: boolean;
    // Continuous section flow (docs/section-flow-plan.md): a `book-section`
    // work that opts in drops each section's `.seg-ref` header, rule, and
    // inter-section gap, and shows the section number as a non-copying
    // gutter tick (≥681px) or inline tick (≤680px). Book-section only;
    // default off. The plan-of-record flag; no work sets it until stage 5.
    sectionFlow?: boolean;
    // Per-work Copy Citation prefix, e.g. 'M.Ant.' for Marcus Aurelius'
    // Meditations ("M.Ant. 4.23"). For a dk work this is "DK <dkChapter>"
    // (e.g. 'DK 22' for Heraclitus), composed with the column by
    // formatCopyCitation into "DK 22 B30" with no extra machinery.
    copyAbbr?: string;
    // dk (Diels-Kranz) only, below — see shared/lib/citation.ts's dk scheme
    // and pipeline/reader_pipeline/scheme.py's matching `for_manifest`
    // fields.
    //
    // A verse work's fragments carry real, per-fragment-restarting line
    // numbers cited "B8.34" (Parmenides); omitted/false (Heraclitus) keeps
    // the scheme lineless — a fragment is cited "B30" alone.
    lines?: boolean;
    // The DK series this work's spine carries: 'B' fragments (the
    // philosopher's own quoted words) or 'A' testimonia (ancient reports
    // about him). Every column in a dk work's spine carries this letter as
    // part of its own token (see citation.ts's dk module doc) — this field
    // is the cheap cross-check that the exported spine matches the work it
    // was meant for.
    series?: 'A' | 'B';
    // A DK chapter DK itself prints with NO series letter at all
    // (Pythagoras, DK 14 — cited "DK 14, 7", never "14 A7"): omit `series`
    // and set this true instead. See citation.ts's `makeDkScheme`/
    // `DK_NO_SERIES_COLUMN_RE` and scheme.py's matching `citation.no_series`.
    // Not composable with `lines` (unevidenced combination).
    noSeries?: boolean;
    // Diels–Kranz chapter number for this philosopher (e.g. 22 for
    // Heraclitus, 28 for Parmenides) — the numeral in "DK 22 B30" and the
    // key the ⌘K palette's dkChapter -> work map resolves the full
    // scholarly citation form against.
    dkChapter?: number;
    // DK prose-flow (docs/prose-flow-design.md §3): columns whose role='text'
    // runs are incipit reference stubs (opening + closing words around an
    // ellipsis), not the fragment's own words. Hash-gated over the joined
    // text-run text in the work manifest (`citation.incipit_columns`); the
    // reader only needs the column set. Absent ⇒ no column is an incipit.
    incipitColumns?: { column: string; sha256_16: string }[];
    // Per-work override for citation.ts's unitNounFor (e.g. Epicurus' Kuriai
    // Doxai -> {singular: 'doctrine', plural: 'doctrines'}, Vatican Sayings
    // -> {singular: 'saying', plural: 'sayings'}). Absent ⇒ the scheme's own
    // table default (see unitNounFor's doc comment) — set today only by the
    // five Epicurus works (the letters use it too, for "section").
    unitNoun?: { singular: string; plural: string };
  };
  // Cross-links to closely related works, shown on the landing page. Each
  // `id` must be a built work.
  related?: { id: string; label: string }[];
  // Ancient commentaries/introductions hosted on the site that comment on THIS
  // work (ids of built works), surfaced in a "Commentary" section on the
  // landing page.
  commentaries?: string[];
  /** Authorship status. Absent ⇒ genuine. Drives the homepage/landing badge. */
  authenticity?: 'genuine' | 'dubious' | 'spurious';
  // Traditional stylometric/dramatic dating (early/middle/late Plato), shown
  // as a single hedged line on the work's landing page. Omitted for the
  // disputed corpus (works without a settled place in the traditional
  // chronology) and the Letters — see docs/registry-draft.md and John's call
  // 2026-07-11. Not shown anywhere on the home page.
  period?: 'early' | 'middle' | 'late';
}

export const AUTHENTICITY_LABEL: Record<'dubious' | 'spurious', string> = {
  dubious: 'Dubious',
  spurious: 'Spurious',
};

// Copyright-encumbered translations are carried ONLY when a build explicitly
// opts in via PUBLIC_SHOW_PRIVATE=1 — the `npm run dev` script sets it, so they
// show locally. Every production build (plain `npm run build` AND the public
// deploy, which forces it off) leaves it unset, so private entries — and their
// citations — are dropped from the bundle. This is fail-SAFE: a forgotten flag
// hides private content rather than leaking text we can't host. The vendored
// aristotle registry (corpora/aristotle/registry.yaml) carries a handful of
// private:true translations; scripts/build-registry.mjs strips them from
// registry.generated.ts's CORPUS_WORKS before this module ever sees them
// unless PUBLIC_SHOW_PRIVATE=1, since that generated file is a plain literal
// with no Vite define-fold of its own. `visibleTranslations` below is the
// second, runtime guard — for any work, vendored or not — that hides a
// private entry this flag leaves unset.
const SHOW_PRIVATE = import.meta.env.PUBLIC_SHOW_PRIVATE === '1';

// A minimal work for exercising registry-driven routing/search/tests before
// any real content lands (see shared/lib/authors.ts's matching
// 'sample-author' fixture). Flag-gated the same way (see authors.ts's
// FIXTURES_ON doc comment). Cited book-section (Marcus-style "4.23") — the
// scheme the pilot author (Marcus Aurelius) will actually carry — so the
// PUBLIC_READER_FIXTURES=1 build exercises the book-section reader path (and
// its own author routing) end-to-end; committed data for it lives under
// fixtures/data/sample-work/ (see app/scripts/stage-fixtures.mjs).
const FIXTURES_ON = import.meta.env.PUBLIC_READER_FIXTURES === '1';

// P6 wing-standalone build mode (docs/p6-plan.md, Settled decision 4): when
// set, scopes WORKS to the entries belonging to one corpus (e.g.
// PUBLIC_WING=aristotle), via the work-id -> corpus map generated alongside
// the registry. Same module-scope import.meta.env read as SHOW_PRIVATE/
// FIXTURES_ON above, so an unset var dead-code-eliminates this filter to a
// no-op in any client bundle. Ruling: the fixture work rides along
// UNFILTERED regardless of PUBLIC_WING — WORK_CORPUS_DATA has no entry for
// 'sample-work' (fixtures aren't real corpus data), so filtering it by
// corpus would just drop it; simpler and safer to leave fixtures untouched
// by this flag, matching how FIXTURES_ON already composes independently of
// SHOW_PRIVATE.
const WING = import.meta.env.PUBLIC_WING;
const WORK_CORPUS = WORK_CORPUS_DATA as Record<string, string>;

const WING_CORPUS_WORKS: Work[] = WING
  ? (CORPUS_WORKS as Work[]).filter((w) => WORK_CORPUS[w.id] === WING)
  : (CORPUS_WORKS as Work[]);

export const WORKS: Work[] = [
  ...WING_CORPUS_WORKS,
  ...(FIXTURES_ON ? (FIXTURE_WORKS as Work[]) : []),
];

const BY_ID = new Map(WORKS.map((w) => [w.id, w]));

export function getWork(id: string): Work | undefined {
  return BY_ID.get(id);
}

// (dkChapter, series) -> the dk work carrying that spine, e.g. (22, 'B') ->
// heraclitus-fragments, (22, 'A') -> heraclitus-testimonia. Registry-derived
// (built once, off WORKS, at module load) rather than a separately hand-
// maintained map — a new dk work is automatically resolvable the moment its
// registry entry declares `citation.dkChapter`/`citation.series`, with no
// second place to keep in sync. Consumed by citation.ts's
// `parseDkFullCitation`, the ⌘K palette's site-wide "DK 22 B30" jump form
// (Wave 1b design memo §2) — the only reason `dkChapter` exists on `Work` at
// all.
// A `noSeries` work (Pythagoras DK 14) has no `series` letter and so is
// deliberately absent from this map — it has its own map, DK_BY_CHAPTER_NO_
// SERIES, immediately below (its lookup key is the chapter alone, with no
// series component to disambiguate on).
const DK_BY_CHAPTER_SERIES = new Map<string, string>();
for (const w of WORKS) {
  const c = w.citation;
  if (c?.scheme === 'dk' && c.dkChapter != null && c.series) {
    DK_BY_CHAPTER_SERIES.set(`${c.dkChapter}:${c.series}`, w.id);
  }
}

export function workByDkCitation(dkChapter: number, series: 'A' | 'B'): Work | undefined {
  const id = DK_BY_CHAPTER_SERIES.get(`${dkChapter}:${series}`);
  return id ? getWork(id) : undefined;
}

// dkChapter -> the no-series dk work carrying that spine, e.g. 14 ->
// pythagoras-testimonia (DK prints this chapter's testimonia with NO A/B
// series letter at all — see the `Work.citation.noSeries` field's own doc).
// Registry-derived off WORKS, same construction as DK_BY_CHAPTER_SERIES
// above, just keyed by chapter alone since there is no series letter to
// disambiguate on. Consumed by citation.ts's `parseDkFullCitation`'s
// no-series full-citation form ("DK 14, 7" / "DK 14 7").
const DK_BY_CHAPTER_NO_SERIES = new Map<number, string>();
for (const w of WORKS) {
  const c = w.citation;
  if (c?.scheme === 'dk' && c.dkChapter != null && c.noSeries) {
    DK_BY_CHAPTER_NO_SERIES.set(c.dkChapter, w.id);
  }
}

export function workByDkChapterNoSeries(dkChapter: number): Work | undefined {
  const id = DK_BY_CHAPTER_NO_SERIES.get(dkChapter);
  return id ? getWork(id) : undefined;
}

// The URL segment a work publishes at within its author's namespace:
// `slug` when declared, else `id` unchanged (every pre-DK work). NOT the
// same thing as `id` (the data directory) once a work declares a slug — see
// the field's doc comment.
export function workSlug(work: Work): string {
  return work.slug ?? work.id;
}

// Resolves a work by its (author, URL slug) pair — the inverse of
// workSlug, for a route whose URL param is the slug, not the id (see
// [author]/[work]/index.astro and .../book/[n].astro's getStaticPaths).
// Undefined for an unknown author or a slug that owns no work of theirs.
export function getWorkBySlug(authorId: string, slug: string): Work | undefined {
  const author = getAuthor(authorId);
  if (!author) return undefined;
  for (const id of author.works) {
    const w = getWork(id);
    if (w && workSlug(w) === slug) return w;
  }
  return undefined;
}

export function bookLabel(work: Work, n: number): string {
  return work.bookLabels[n - 1] ?? String(n);
}

// Human-readable name for a work's source language, derived from the
// registry's `language` field (never from the author or title) — 'grc' works
// are TLG-sourced Greek, 'lat' works are PHI-sourced Latin.
export const LANGUAGE_LABEL: Record<Work['language'], string> = {
  grc: 'Greek',
  lat: 'Latin',
};

export function languageLabel(work: Work): string {
  return LANGUAGE_LABEL[work.language];
}

// A single-book work is a single treatise with no book level, so it lives at
// /<work> with no /book/<n> subfolder, and the reader hides all book-level
// navigation.
export function isBookless(work: Work): boolean {
  return work.books === 1;
}

// Resolves the author slug that owns a work, for composing an author-scoped
// URL. Throws (rather than falling back to some default) when the work or its
// author can't be resolved — a broken link is a build-time bug to surface
// loudly, never a silently-emitted 404.
function resolveAuthorSlug(workId: string): string {
  const w = BY_ID.get(workId);
  if (!w) throw new Error(`resolveAuthorSlug: unknown work '${workId}'`);
  const author = getAuthor(w.author);
  if (!author) {
    throw new Error(`resolveAuthorSlug: work '${workId}' has unresolvable author '${w.author}'`);
  }
  return author.id;
}

// The division id for a work's book/letter/chapter number, e.g. book-1,
// letter-47, chapter-3 -- or 'text' for a bookless work (isBookless), which
// only ever has one division. One place so the per-work rule (John's ruling,
// 2026-09-12: divisionNoun + isBookless) changes this single function rather
// than every call site.
export function divisionId(workId: string, book: number): string {
  const w = BY_ID.get(workId);
  if (!w) throw new Error(`divisionId: unknown work '${workId}'`);
  return isBookless(w) ? 'text' : `${w.divisionNoun ?? 'book'}-${book}`;
}

// The base-relative path to a work's READER (caller prepends BASE_URL). Every
// work — bookless or not — reads at /read/<author>/<work>/<division-id>;
// bookless works only ever have book 1. The bare /texts/<author>/<work>/
// slug is the work's landing page (workLanding). The single source of truth
// for reader URLs — used by the home index, work switcher, Bekker/Stephanus
// jump, search jumps, and cross-book outline links.
export function workPath(workId: string, book = 1): string {
  const w = BY_ID.get(workId);
  if (!w) throw new Error(`workPath: unknown work '${workId}'`);
  // Clamp to the work's real book range so a stale/overflow value (e.g. a
  // remembered book number for a work that is now bookless) can't 404. Also
  // guards non-integer/non-finite input (NaN, 1.5, Infinity) — anything that
  // isn't a whole number falls back to 1 before clamping.
  const n = Number.isInteger(book) ? book : 1;
  const b = Math.min(Math.max(1, n), w.books);
  return `/read/${resolveAuthorSlug(workId)}/${workSlug(w)}/${divisionId(workId, b)}`;
}

// The base-relative path to a work's LANDING page (caller prepends BASE_URL):
// /texts/<author>/<work>/, an overview of the work that funnels into the
// reader.
export function workLanding(workId: string): string {
  const w = BY_ID.get(workId);
  if (!w) throw new Error(`workLanding: unknown work '${workId}'`);
  return `/texts/${resolveAuthorSlug(workId)}/${workSlug(w)}/`;
}

// The Lyceum partner catalog's own key for a work, 'lyceum:<author-segment>.
// <work-segment>' -- built off the SAME segments workLanding uses (resolve-
// AuthorSlug + workSlug), so it can never drift from scripts/emit-lyceum-
// manifest.mjs's own derivation (routeSegments/workKey there), which reads
// the manifest's `route` field this repo writes from those same segments.
export function lyceumWorkKey(workId: string): string {
  const w = BY_ID.get(workId);
  if (!w) throw new Error(`lyceumWorkKey: unknown work '${workId}'`);
  return `lyceum:${resolveAuthorSlug(workId).toLowerCase()}.${workSlug(w).toLowerCase()}`;
}

let lyceumKeyIndex: Map<string, string> | undefined;

// The inverse of lyceumWorkKey: our work id for a partner catalog key, or
// undefined when the key names no work of ours (a partner-only work in the
// shared catalog -- see app/src/lib/lyceum-catalog.ts's foreign-work
// handling). Built once, off WORKS, not just the built subset -- an
// unbuilt-but-registered work still round-trips.
export function workIdFromLyceumKey(key: string): string | undefined {
  if (!lyceumKeyIndex) {
    lyceumKeyIndex = new Map(WORKS.map((w) => [lyceumWorkKey(w.id), w.id]));
  }
  return lyceumKeyIndex.get(key);
}

// The base-relative path to an AUTHOR's landing page (caller prepends
// BASE_URL): the bare /<author> slug. Throws for an unknown author id, for
// the same reason workPath/workLanding throw on an unresolvable work.
export function authorPath(authorId: string): string {
  if (!getAuthor(authorId)) throw new Error(`authorPath: unknown author '${authorId}'`);
  return `/${authorId}`;
}

// Freeman Ancilla wave apparatus-credit line (design note §3.8): shown
// beside a Freeman-wired work's own edition citation. null for any work
// whose translations don't include the 'freeman' id (every non-Freeman
// work — the overwhelming majority — is unaffected). Two forms, selected
// by whether Burnet is ALSO wired (the slot-flip case, phase 1b onward) —
// Protagoras (phase 1, Freeman-only) always gets the second form.
export function freemanApparatusCredit(work: Work): string | null {
  if (!work.translations.some((t) => t.id === 'freeman')) return null;
  const burnet = work.translations.find((t) => t.id === 'burnet');
  if (burnet) {
    return `Groupings, title markings, and editorial apparatus follow Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Oxford: Blackwell, 1948), whose translation is shown by default; John Burnet's Early Greek Philosophy, 3rd ed. (1920) is available from the translation picker.`;
  }
  return `Groupings, title markings, and editorial apparatus follow Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Oxford: Blackwell, 1948); the translation is Freeman's.`;
}

// Translations visible in the current build. Private (copyright-encumbered)
// entries are already dropped from WORKS at compile time unless the build opted
// in (see SHOW_PRIVATE above); this filter is a runtime backstop.
// A non-Astro host (e.g. a future desktop app) can append runtime-registered
// translations — user imports, loaded from local files — via
// globalThis.__READER_EXTRA_TRANSLATIONS__ ({workId: TranslationRef[]});
// the site never sets it, so the static registry is unchanged there.
export function visibleTranslations(work: Work): TranslationRef[] {
  const extra = (globalThis as {
    __READER_EXTRA_TRANSLATIONS__?: Record<string, TranslationRef[]>;
  }).__READER_EXTRA_TRANSLATIONS__?.[work.id] ?? [];
  return work.translations.filter(t => !t.private || SHOW_PRIVATE).concat(extra);
}

// ---------------------------------------------------------------------------
// "In print" — copyright-encumbered modern translations and commentaries we
// can't host but want to point readers to, shown on each work's landing page.
// This is curated, additive metadata: a work with no entry simply omits the
// section. Each item is a citation plus an optional direct `url`; when `url` is
// absent the landing renders a Google Books search for the citation, so a link
// always resolves and we never fabricate a product page.
//
// Empty for this rollout — no modern Plato translations/commentaries have
// been curated yet (the Aristotle-specific catalogue this replaced is gone
// along with those works). Populate per-work as John curates them.

export interface FurtherReadingItem {
  // 'translation'/'commentary' = modern, copyright-protected works we can't host.
  // 'collection' = an in-print physical edition that CONTAINS the translation we
  // do host (e.g. a Loeb volume), for readers who want a paper copy of what
  // they're reading here.
  kind: 'translation' | 'commentary' | 'collection';
  cite: string;     // full citation, e.g. "Christopher Rowe (Penguin, 2005)"
  url?: string;     // optional direct purchase/publisher link; else Books search
}

// Citations may use <em>…</em> around the work's title (rendered as italics on
// the landing; stripped for the Google Books search link in inPrintHref).
const FURTHER_READING: Record<string, FurtherReadingItem[]> = {};

export function furtherReading(workId: string): FurtherReadingItem[] {
  return FURTHER_READING[workId] ?? [];
}

// A link that always resolves to where the cited edition can be found/bought.
// The cite may carry <em> title markup, so strip tags before building the query.
export function inPrintHref(item: FurtherReadingItem): string {
  const plain = item.cite.replace(/<[^>]+>/g, '');
  return item.url ?? `https://www.google.com/search?tbm=bks&q=${encodeURIComponent(plain)}`;
}

// ---------------------------------------------------------------------------
// "Resources" — external study aids relevant to a specific work, shown on the
// landing page. Curated, additive metadata like FURTHER_READING: a work with
// no entry simply omits the section. Empty for this rollout (the Aristotle
// logic-exercise catalogue this replaced doesn't apply to Plato).

export interface ResourceItem {
  label: string;         // resource name
  url: string;
  blurb: string;         // one line describing the resource
  authorName: string;
  authorUrl: string;
  exercises?: string;    // exercise set(s) within the resource keyed to this work
}

const RESOURCES: Record<string, ResourceItem[]> = {};

export function resourcesFor(workId: string): ResourceItem[] {
  return RESOURCES[workId] ?? [];
}

// ---------------------------------------------------------------------------
// Home-page taxonomy. Phase 0 replaces the old single-author Thrasyllan
// grouping (nine tetralogies of one author's dialogues) with period/school
// shelves, per BUILD-PROMPT.md's "Phase 0" plan: one shelf per historical
// period that has at least one author (shared/lib/authors.ts's
// AUTHOR_PERIOD_ORDER / PERIOD_LABEL), in chronological order — Presocratics
// through Late Antiquity. WITHIN a shelf, authors keep their AUTHORS registry
// order, and within an author, works keep that author's `works` order. A
// `ShelfWork` is either an existing work (`id`, resolved against WORKS) or a
// not-yet-added work shown as a "coming soon" placeholder (`title` only) —
// unused so far. Every WORKS entry appears in exactly one shelf — verified in
// shared/__tests__/works.test.ts.

export interface ShelfWork {
  id?: string;      // an existing work (in WORKS) — clickable
  title?: string;   // a planned work — greyed-out placeholder
}

export interface Shelf {
  numeral: string;  // a plain ordinal (position in AUTHOR_PERIOD_ORDER) — the shelf TITLE is what should read prominently
  title: string;    // the period's display name, e.g. 'Imperial'
  works: ShelfWork[];
}

export const SHELVES: Shelf[] = AUTHOR_PERIOD_ORDER
  .filter((period) => AUTHORS.some((a) => a.period === period))
  .map((period, i) => ({
    numeral: String(i + 1),
    title: PERIOD_LABEL[period],
    works: AUTHORS
      .filter((a) => a.period === period)
      .flatMap((a) => a.works.filter((id) => BY_ID.has(id)).map((id) => ({ id }))),
  }));

// "Start here" — a curated front-table strip of approachable works for
// newcomers, rendered as a featured band ABOVE the SHELVES on the home page.
// Empty in Phase 0 (no real works yet to curate); a later wave populates it.
// Every id here must resolve to a real WORKS entry — verified in
// shared/__tests__/works.test.ts.
export const START_HERE: string[] = START_HERE_DATA;

// A named group of works for the search "works to include" selector: one entry
// per home-page shelf, in home-page order, holding only the existing works
// (placeholders dropped).
export interface WorkGroup {
  ref: string;    // the shelf numeral (SHELVES[i].numeral)
  label: string;  // the shelf's title
  ids: string[];  // existing work ids in this group, in order
}

export const WORK_GROUPS: WorkGroup[] = (() => {
  const groups: WorkGroup[] = [];
  const ids = (ws: ShelfWork[]) => ws.filter(w => w.id && BY_ID.has(w.id)).map(w => w.id!);
  for (const shelf of SHELVES) {
    const g = ids(shelf.works);
    if (g.length) groups.push({ ref: shelf.numeral, label: shelf.title, ids: g });
  }
  return groups;
})();

// The vendored Aristotelian-corpus taxonomy (Lyceum P3) — the traditional
// numbered divisions of the corpus (I Logic, II Natural Philosophy with
// II.a/b/c subcategories, III Metaphysics, …) plus an unnumbered appendix of
// doubtful/spurious works, exactly as the sibling aristotle-reader's own
// works.ts CATEGORIES groups them (see scripts/vendor-aristotle-registry.mjs's
// extractGroups). Keyed by author id; currently populated for 'aristotle'
// only — Porphyry's Isagoge is deliberately outside the sibling's own
// CATEGORIES (surfaced as a Categories-page "Commentary" card there instead),
// so `workGroupsFor('porphyry')` returns `[]` and porphyry keeps the flat
// Works list. An author with no vendored groups also returns `[]`.
export interface AuthorWorkSubcategory {
  ref: string;    // e.g. 'II.a'
  label: string;  // e.g. 'Major Works on Nature'
  works: string[]; // work ids
}

export interface AuthorWorkGroup {
  numeral: string;  // 'I' — empty for the appendix (rendered without a numeral)
  title: string;
  works?: string[];                        // direct works (no sub-division)
  subcategories?: AuthorWorkSubcategory[];
  appendix?: boolean;
}

const AUTHOR_WORK_GROUPS = AUTHOR_WORK_GROUPS_DATA as Record<string, AuthorWorkGroup[]>;

export function workGroupsFor(authorId: string): AuthorWorkGroup[] {
  return AUTHOR_WORK_GROUPS[authorId] ?? [];
}

// Cross-work ordering for search results, matching the home page's SHELVES
// flatten order (which differs from the raw WORKS/corpus order). Any real work
// not referenced by SHELVES is appended in WORKS order so every searchable
// work has a defined index.
export const WORK_ORDER: Map<string, number> = (() => {
  const order: string[] = [];
  for (const g of WORK_GROUPS) for (const id of g.ids) order.push(id);
  for (const w of WORKS) if (!order.includes(w.id)) order.push(w.id);
  return new Map(order.map((id, i) => [id, i]));
})();
