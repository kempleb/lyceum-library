// Build-time assembly of the Lyceum catalog (docs/design-spec.md §5.3.3 and
// §6, docs/lyceum-shared-repo-plan.md §11.6): the collection -> author ->
// work ledger both the homepage previews and the Catalog page render, plus
// the passage of the week and the curated reading paths.
//
// Same role as built-works.ts and citation-routes.ts — fs + registry in,
// plain view model out — so the pure models (shared/lib/contents.ts's
// buildCatalog, shared/lib/lyceum-catalog-source.ts's parseCatalog) never
// learn about the filesystem or import.meta.env. Read cwd-relative from
// app/, the way built-works.ts and citation-routes.ts already do.
import { existsSync, readFileSync } from 'node:fs';
import { AUTHOR_PERIOD_ORDER, getAuthor, PERIOD_LABEL } from '@shared/lib/authors';
import { buildCatalog, type CatalogAuthorInput, type CatalogModel, type CatalogSectionInput, type CatalogWorkInput } from '@shared/lib/contents';
import { parseCatalog, type Catalog, type CatalogCollection, type CatalogWork as SourceCatalogWork } from '@shared/lib/lyceum-catalog-source';
import { compareWorkTitles } from '@shared/lib/work-title-order';
import {
  LANGUAGE_LABEL, START_HERE, getWork, visibleTranslations, workIdFromLyceumKey, workLanding, workPath,
  type Work,
} from '@shared/lib/works';
import { builtWorks, isBuilt } from './built-works';

// The partner's published catalog. Overridable so a fetched copy (or a
// test's tiny fixture) can stand in for the committed live snapshot without
// touching this file — see parseCatalog's own doc comment.
const CATALOG_PATH = process.env.LYCEUM_CATALOG_FILE ?? '../fixtures/catalog.snapshot.v2.live-2026-09-08.json';
// Our own editorial seed (fixtures/editorial.seed.json): local defaults the
// partner's live catalog overrides record-for-record. Never env-overridden —
// it is committed data, not a build input to swap.
const SEED_PATH = '../fixtures/editorial.seed.json';

// Display names for the two mounted corpora. DRAFT copy, taken verbatim from
// the approved Round-5 mockup; the corpus files carry no display name of
// their own. `id` is the section's anchor on the Catalog page and its
// collection facet token.

// The form facet: the registry's own workType, in reader's English. Never
// inferred from a title — a DK work's fragment/testimonium split is an
// evidentiary claim the registry already makes.
const FORM_LABEL: Record<Work['workType'], string> = {
  continuous: 'Prose',
  fragments: 'Fragments & testimonia',
  verse: 'Verse',
  letters: 'Letters',
};

function readJson(path: string): unknown {
  return existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : undefined;
}

let catalogSourceCache: Catalog | undefined;

/** The merged, filtered, ordered catalog (live snapshot + our editorial
 *  seed) — see shared/lib/lyceum-catalog-source.ts's parseCatalog. */
function catalogSource(): Catalog {
  if (catalogSourceCache) return catalogSourceCache;
  const liveJson = readJson(CATALOG_PATH);
  if (liveJson === undefined) {
    throw new Error(
      `lyceum-catalog: no catalog file at ${CATALOG_PATH} (set LYCEUM_CATALOG_FILE to point at one).`,
    );
  }
  const seedJson = readJson(SEED_PATH);
  const includeDrafts = import.meta.env.PUBLIC_LYCEUM_DRAFTS === '1';
  return (catalogSourceCache = parseCatalog(liveJson, seedJson, { includeDrafts }));
}

/** A presentation.content string from the live catalog, falling back to our
 *  own copy when the partner hasn't published that key yet. */
export function lyceumContent(key: string, fallback: string): string {
  return catalogSource().content[key] ?? fallback;
}

/** A presentation.visibility flag from the live catalog; defaults to shown. */
export function lyceumVisible(key: string, fallback = true): boolean {
  const v = catalogSource().visibility[key];
  return typeof v === 'boolean' ? v : fallback;
}

/** The catalog preset for a work, falling back to the library default. */
export function workPreset(workId: string): string {
  const source = catalogSource();
  const work = source.works.find((w) => workIdFromLyceumKey(w.id) === workId);
  return work?.preset || source.defaultPreset;
}

/** The kept collections (id + name) a work belongs to, in the catalog's own
 *  editorial.collection_ids order -- a collection_ids entry naming a
 *  collection that was filtered out (draft while drafts are off) or never
 *  existed is silently dropped, same as every other cross-reference in this
 *  file. Flattens one level of nesting (a child collection's id/name are
 *  looked up the same as a top-level one) since a work can belong to either. */
export function workCollections(workId: string): { id: string; name: string }[] {
  const source = catalogSource();
  const work = source.works.find((w) => workIdFromLyceumKey(w.id) === workId);
  if (!work) return [];
  const byId = new Map<string, string>();
  for (const c of source.collections) {
    byId.set(c.id, c.name);
    for (const child of c.children) byId.set(child.id, child.name);
  }
  return work.collectionIds
    .map((id) => ({ id, name: byId.get(id) }))
    .filter((c): c is { id: string; name: string } => typeof c.name === 'string');
}

// Per-work citation ranges, read once per build from each work's manifest —
// the same source ReaderShell.astro's library rows use.
const rangeCache = new Map<string, { start: string; end: string }[]>();

function citationRanges(id: string): { start: string; end: string }[] {
  const hit = rangeCache.get(id);
  if (hit) return hit;
  let ranges: { start: string; end: string }[] = [];
  try {
    const m = JSON.parse(readFileSync(`public/data/${id}/manifest.json`, 'utf-8'));
    ranges = (m.citation?.books ?? []).map((b: { start: string; end: string }) => ({
      start: String(b.start), end: String(b.end),
    }));
  } catch { /* not built in this checkout */ }
  rangeCache.set(id, ranges);
  return ranges;
}

/** '12 books · 1.1–12.36' — the work's extent and its citation range. */
export function workExtent(w: Work): string {
  const ranges = citationRanges(w.id);
  return [
    w.books > 1 ? `${w.books} books` : null,
    ranges.length ? `${ranges[0].start}–${ranges[ranges.length - 1].end}` : null,
  ].filter(Boolean).join(' · ');
}

/**
 * One author's citation summary — what the ledger's right-hand column shows
 * when the row stands for the author rather than for a single work ('DK 22',
 * 'Bekker', 'Latin · 10 works'). Never a page-count guess.
 */
function authorRange(works: Work[]): string {
  const schemes = new Set(works.map((w) => w.citation?.scheme ?? 'bekker'));
  if (schemes.size === 1) {
    const scheme = [...schemes][0];
    if (scheme === 'dk') {
      const chapters = new Set(works.map((w) => w.citation?.dkChapter).filter((n) => n != null));
      if (chapters.size === 1) return `DK ${[...chapters][0]}`;
    }
    if (scheme === 'bekker') return 'Bekker';
    if (scheme === 'stephanus') return 'Stephanus';
  }
  const languages = [...new Set(works.map((w) => LANGUAGE_LABEL[w.language]))].join(' & ');
  if (works.length === 1 && works[0].books > 1) return `${languages} · ${works[0].books} books`;
  return `${languages} · ${works.length} ${works.length === 1 ? 'work' : 'works'}`;
}

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'unknown';
}

/** The partner origin, base URL with no trailing slash — unset means "don't
 *  link out" (rule 5: a foreign work is omitted, not half-linked). */
function partnerOrigin(): string | undefined {
  const raw = import.meta.env.PUBLIC_PARTNER_ORIGIN as string | undefined;
  return raw ? raw.replace(/\/$/, '') : undefined;
}

function foreignHostname(origin: string): string {
  try {
    return new URL(origin).hostname;
  } catch {
    return origin;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/**
 * One catalog collection, resolved into the shape buildCatalog wants:
 * author -> work, with a work of ours linking into the reader (workLanding)
 * when it's built HERE; a work that's either registered but not built in
 * this checkout, or resolves to no registry entry of ours at all, links to
 * the partner origin instead (rule 5, §11.6) — or is dropped entirely when
 * PUBLIC_PARTNER_ORIGIN isn't set, silently, never a broken link.
 */
function catalogSectionFor(collection: CatalogCollection, base: string, emptyNote?: string): CatalogSectionInput {
  const registryByAuthor = new Map<string, Work[]>();
  const foreignByAuthor = new Map<string, CatalogWorkInput[]>();
  const origin = partnerOrigin();

  for (const work of collection.works as SourceCatalogWork[]) {
    const workId = workIdFromLyceumKey(work.id);
    const w = workId ? getWork(workId) : undefined;
    if (workId && w && isBuilt(workId)) {
      registryByAuthor.set(w.author, [...(registryByAuthor.get(w.author) ?? []), w]);
      continue;
    }
    // Either not in our registry at all, or registered but not built in this
    // checkout (the staging case for a partial data set): both link out to
    // the partner origin, like any foreign work.
    if (!origin) continue; // no partner origin configured: omitted silently
    const route = typeof work.facts.route === 'string' ? work.facts.route : null;
    if (!route) continue;
    const authorName = typeof work.facts.author === 'string' ? work.facts.author : work.id;
    const citation = isRecord(work.facts.citation) ? work.facts.citation : {};
    const item: CatalogWorkInput = {
      id: work.id,
      title: typeof work.facts.title === 'string' ? work.facts.title : work.id,
      href: `${origin}${route}`,
      extent: typeof citation.extent === 'string' ? citation.extent : '',
      language: work.facts.language === 'grc' ? 'Greek' : work.facts.language === 'la' ? 'Latin' : '',
      form: '',
      external: foreignHostname(origin),
    };
    foreignByAuthor.set(authorName, [...(foreignByAuthor.get(authorName) ?? []), item]);
  }

  const authors: CatalogAuthorInput[] = [];
  for (const [authorId, works] of registryByAuthor) {
    const author = getAuthor(authorId);
    if (!author) throw new Error(`lyceum-catalog: work names unknown author '${authorId}'`);
    // The author's own curated work order, not corpus order.
    const ordered = author.works
      .map((wid) => works.find((w) => w.id === wid))
      .filter((w): w is Work => Boolean(w));
    authors.push({
      id: author.id,
      name: author.name,
      period: author.period as string,
      periodLabel: PERIOD_LABEL[author.period],
      range: authorRange(ordered),
      works: ordered.map((w) => ({
        id: w.id,
        title: w.title,
        href: `${base}${workLanding(w.id)}`,
        extent: workExtent(w),
        language: LANGUAGE_LABEL[w.language],
        form: FORM_LABEL[w.workType],
      })),
    });
  }
  for (const [authorName, works] of foreignByAuthor) {
    authors.push({
      id: `foreign:${slugify(authorName)}`,
      name: authorName,
      period: '',
      periodLabel: '',
      range: `${works.length} ${works.length === 1 ? 'work' : 'works'}`,
      works: [...works].sort((a, b) => compareWorkTitles(a.title, b.title)),
    });
  }
  // Chronological by period for registry authors; foreign (period-less)
  // authors sort after every real period, alphabetically among themselves.
  authors.sort((a, b) => periodIndex(a.period) - periodIndex(b.period) || a.name.localeCompare(b.name));

  return {
    id: collection.id,
    name: collection.name,
    accent: collection.accent || null,
    // Ruling (John, 2026-09-13): an empty collection is shown, not dropped,
    // with the partner's own presentation.content['collection.empty']
    // string as its note -- never prose of ours.
    note: authors.length === 0 ? (emptyNote ?? null) : null,
    parentId: collection.parentId || null,
    authors,
  };
}

let catalogCache: CatalogModel | undefined;

/**
 * The whole library as one ledger, built from the merged partner + seed
 * catalog (catalogSource): collections in the catalog's own sort order,
 * authors within a collection in period order, works in the author's own
 * curated order. A collection with no work of ours or the partner's own to
 * show is still shown, not dropped (ruling 2026-09-13), with the partner's
 * own 'collection.empty' string as its note. One level of nesting: a child
 * collection is its own section, flattened in right after its parent's
 * (both consumers render sections flat today), carrying `parentId` so the
 * relationship isn't lost.
 */
export function lyceumCatalog(): CatalogModel {
  if (catalogCache) return catalogCache;
  const base = (import.meta.env.BASE_URL as string).replace(/\/$/, '');
  const emptyNote = catalogSource().content['collection.empty'];
  const sections: CatalogSectionInput[] = [];
  for (const c of catalogSource().collections) {
    sections.push(catalogSectionFor(c, base, emptyNote));
    for (const child of c.children) {
      sections.push(catalogSectionFor(child, base, emptyNote));
    }
  }
  return (catalogCache = buildCatalog(sections));
}

function periodIndex(period: string): number {
  const i = (AUTHOR_PERIOD_ORDER as string[]).indexOf(period);
  return i < 0 ? AUTHOR_PERIOD_ORDER.length : i;
}

// ── The passage of the week ───────────────────────────────────────────────

export interface WeekPassage {
  label: string;        // 'Passage of the week · Epictetus, Enchiridion'
  source: string;       // the Greek or Latin
  english: string;
  sourceRef: string;    // 'Ench. 1'
  englishRef: string;   // the translator's citation
  href: string;         // into the reader
  title: string;
}

/** Sentences of `text`, split on a full stop followed by space or end. */
function sentences(text: string): string[] {
  return text.split(/(?<=\.)\s+/).map((s) => s.trim()).filter(Boolean);
}

/** The opening sentences of both columns, taking the same COUNT of sentences
 *  from each so the two halves of the hero say the same thing: enough Greek
 *  or Latin to fill the column, and its English beside it. */
function opening(text: string, count: number): string {
  return sentences(text).slice(0, count).join(' ');
}

/**
 * A real passage from a built work: the "start here" pick when one is built,
 * else the Enchiridion's first section. Null when neither is built in this
 * checkout.
 */
export function weekPassage(): WeekPassage | null {
  const built = new Set(builtWorks().map((w) => w.id));
  const id = START_HERE.find((w) => built.has(w)) ?? (built.has('enchiridion') ? 'enchiridion' : null);
  if (!id) return null;
  const work = getWork(id);
  if (!work) return null;
  const author = getAuthor(work.author);
  let segment: { column?: string; greek?: { text: string }[]; english?: { text: string } } | null = null;
  try {
    const book = JSON.parse(readFileSync(`public/data/${id}/book-01.json`, 'utf-8'));
    segment = book.segments?.[0] ?? null;
  } catch { /* not built in this checkout */ }
  if (!segment?.greek?.length || !segment.english?.text) return null;

  const sourceText = segment.greek.map((line) => line.text).join(' ');
  // Take whole sentences, enough of them to fill the column.
  let count = 1;
  const all = sentences(sourceText);
  while (count < all.length && all.slice(0, count).join(' ').length < 120) count += 1;
  const base = (import.meta.env.BASE_URL as string).replace(/\/$/, '');
  return {
    label: `Passage of the week · ${author?.name ?? work.author}, ${work.title}`,
    source: opening(sourceText, count),
    english: opening(segment.english.text, count),
    sourceRef: `${work.abbr} ${segment.column ?? ''}`.trim(),
    englishRef: visibleTranslations(work)[0]?.name ?? '',
    href: `${base}${workPath(id)}`,
    title: work.title,
  };
}

// ── Reading paths ─────────────────────────────────────────────────────────

export interface ReadingPath {
  title: string;
  description: string;
  caption: string;
  href: string;
  /** DRAFT paths are agent-drafted copy awaiting John; curated paths are not. */
  draft: boolean;
}

interface CuratedPath {
  id: string;
  title: string;
  description: string;
  stops?: { work: string; locus?: string; note?: string }[];
}

interface ReadingPathsFile {
  paths?: CuratedPath[];
}

let readingPathsFileCache: ReadingPathsFile | null | undefined;

/** The hand-authored curated paths (fixtures/reading-paths.json), or null. */
function readingPathsFile(): ReadingPathsFile | null {
  if (readingPathsFileCache !== undefined) return readingPathsFileCache;
  readingPathsFileCache = existsSync('../fixtures/reading-paths.json')
    ? (JSON.parse(readFileSync('../fixtures/reading-paths.json', 'utf8')) as ReadingPathsFile)
    : null;
  return readingPathsFileCache;
}

/**
 * The curated paths of spec §5.3.2. The hand-authored ones first (real
 * curation, their own curator's words); the two below them are DRAFT copy
 * from the Round-5 mockup over real works, with their counts and start
 * points computed.
 */
export function readingPaths(): ReadingPath[] {
  const built = builtWorks();
  const base = (import.meta.env.BASE_URL as string).replace(/\/$/, '');
  const isBuilt = (id: string) => built.some((w) => w.id === id);
  const out: ReadingPath[] = [];

  for (const path of readingPathsFile()?.paths ?? []) {
    const stops = (path.stops ?? []).filter((s) => isBuilt(s.work));
    const first = stops[0] && getWork(stops[0].work);
    if (!first) continue;
    out.push({
      title: path.title,
      description: path.description,
      caption: `${stops.length} stops · begins with ${first.title}`,
      href: `${base}${workLanding(first.id)}`,
      draft: false,
    });
  }

  const presocraticWorks = built.filter((w) => getAuthor(w.author)?.period === 'presocratic');
  const presocratics = new Set(presocraticWorks.map((w) => w.author));
  // Thales opens the path where he is built, as the tradition tells it.
  const opener = presocraticWorks.find((w) => w.author === 'thales') ?? presocraticWorks[0];
  if (presocratics.size && opener) {
    out.push({
      title: 'First Principles',
      description: 'The Presocratics in their own words — fragments first, testimonia beside them.',
      caption: `${presocratics.size} authors · begins with ${getAuthor(opener.author)?.name ?? ''}`,
      href: `${base}${workLanding(opener.id)}`,
      draft: true,
    });
  }

  const stoic = built.filter((w) => ['epictetus', 'seneca', 'marcus-aurelius'].includes(w.author));
  if (stoic.length && isBuilt('enchiridion')) {
    out.push({
      title: 'The Stoic Course',
      description: 'Epictetus heard, Seneca read, Marcus practiced — the Stoa in the order the tradition taught it.',
      caption: `${stoic.length} works · begins with the Enchiridion`,
      href: `${base}${workLanding('enchiridion')}`,
      draft: true,
    });
  }

  return out.slice(0, 3);
}
