// Lyceum partner-catalog assembly (P4, docs/lyceum-shared-repo-plan.md §11.6):
// merges the partner's published version-2 catalog snapshot with our own
// local editorial seed, filters by lifecycle state, and orders collections
// and works for the homepage/Catalog page to render.
//
// PURE: no fs, no import.meta.env — same discipline as contents.ts's
// buildCatalog. The caller (app/src/lib/lyceum-catalog.ts) reads both JSON
// files off disk (build time today; a later wave can hand it a FETCHED copy
// of the live catalog instead — this function doesn't care which) and
// resolves any env-derived flag (PUBLIC_LYCEUM_DRAFTS) to the plain
// `includeDrafts` boolean below.

import { compareWorkTitles } from './work-title-order';

export interface CatalogWork {
  /** The partner catalog's own key, 'lyceum:<author-segment>.<work-segment>'. */
  id: string;
  /** The work's facts, verbatim from whichever source (live or seed) won. */
  facts: Record<string, unknown>;
  description: string;
  defaultTranslation: string;
  preset: string;
  collectionIds: string[];
  /** editorial.historical_shelf_id: the one age this work sits in, or ''
   *  (a legacy catalog, or a seed-only work with no age). */
  historicalShelfId: string;
  featured: boolean;
  state: string;
}

/** One of the partner's historical shelves -- the ages (Brian, 2026-10-08).
 *  Names, ids, order and count all come from the catalog; nothing here fixes
 *  them (the names may change, John, 2026-10-08). Each kept work sits in
 *  exactly one; collections cut across them. */
export interface CatalogShelf {
  id: string;
  name: string;
  sortOrder: number;
  /** This age's kept works, ordered (author, then title); may be empty. */
  works: CatalogWork[];
}

export interface CatalogPreset {
  id: string;
  label: string;
  description: string;
  colors: {
    ink: string;
    paper: string;
    surface: string;
    accent: string;
    muted: string;
    line: string;
  };
}

export interface CatalogCollection {
  id: string;
  name: string;
  description: string;
  accent: string;
  featured: boolean;
  state: string;
  sortOrder: number;
  parentId: string;
  /** This collection's own member works, filtered and ordered (author, then
   *  title). A work with no registry match is still listed here — the
   *  caller (app/src/lib/lyceum-catalog.ts) decides whether it links out or
   *  is silently omitted. */
  works: CatalogWork[];
  /** One level of nesting (parent_id), per the partner schema; empty today. */
  children: CatalogCollection[];
  /** True when this collection named a parent_id that named no collection
   *  we kept (missing entirely, or filtered out -- a draft parent while
   *  drafts are off): promoted to a root collection rather than dropped. */
  orphaned: boolean;
}

export interface Catalog {
  collections: CatalogCollection[];
  /** The ages in sort_order, or null for a catalog that carries no
   *  historical_shelves (every catalog before plugin 0.8.0). */
  shelves: CatalogShelf[] | null;
  /** Kept works in no age, ordered (author, then title): only ever seed-only
   *  works (our editorial seed carries no ages, and the live catalog must give
   *  each of its own works one). Always empty when `shelves` is null. */
  unshelved: CatalogWork[];
  /** Every kept work, flat, whether or not a kept collection lists it. */
  works: CatalogWork[];
  presets: Record<string, CatalogPreset>;
  defaultPreset: string;
  /** presentation.content string table (home.title, nav.library, ...). */
  content: Record<string, string>;
  /** presentation.visibility flags (home.collections, home.featured, ...). */
  visibility: Record<string, boolean>;
}

interface RawWork {
  id?: unknown;
  facts?: unknown;
  editorial?: Record<string, unknown>;
}

interface RawCollection {
  id?: unknown;
  name?: unknown;
  description?: unknown;
  state?: unknown;
  sort_order?: unknown;
  featured?: unknown;
  parent_id?: unknown;
  presentation?: { accent?: unknown } | null;
}

function fail(message: string): never {
  throw new Error(`parseCatalog: ${message}`);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Validates the partner's live snapshot shape; throws naming the first
 * missing or invalid key, in the order schemas/snapshot.v2.schema.json's own
 * `required` list carries them: schema_version, library_id, revision,
 * generated_at, presentation, collections, works, integrity. Does not
 * validate the full JSON Schema (nested collection/work shapes) — just the
 * top-level facts the merge below actually depends on.
 */
function validateLive(json: unknown): Record<string, unknown> {
  if (!isPlainObject(json)) fail('the live catalog is not a JSON object');

  if (!('schema_version' in json)) fail('the live catalog is missing required key "schema_version"');
  if (json.schema_version !== '2.0') {
    fail(`the live catalog's schema_version must be "2.0", got ${JSON.stringify(json.schema_version)}`);
  }

  if (!('library_id' in json)) fail('the live catalog is missing required key "library_id"');
  if (json.library_id !== 'lyceum-library') {
    fail(`the live catalog's library_id must be "lyceum-library", got ${JSON.stringify(json.library_id)}`);
  }

  if (!('revision' in json)) fail('the live catalog is missing required key "revision"');
  if (!(typeof json.revision === 'number' && Number.isInteger(json.revision) && json.revision >= 1)) {
    fail(`the live catalog's "revision" must be an integer >= 1, got ${JSON.stringify(json.revision)}`);
  }

  if (!('generated_at' in json)) fail('the live catalog is missing required key "generated_at"');
  if (typeof json.generated_at !== 'string') {
    fail(`the live catalog's "generated_at" must be a string, got ${JSON.stringify(json.generated_at)}`);
  }

  if (!('presentation' in json)) fail('the live catalog is missing required key "presentation"');
  if (!isPlainObject(json.presentation)) {
    fail(`the live catalog's "presentation" must be an object, got ${JSON.stringify(json.presentation)}`);
  }

  if (!('collections' in json)) fail('the live catalog is missing required key "collections"');
  if (!Array.isArray(json.collections)) fail('the live catalog\'s "collections" must be an array');

  if (!('works' in json)) fail('the live catalog is missing required key "works"');
  if (!Array.isArray(json.works)) fail('the live catalog\'s "works" must be an array');

  if (!('integrity' in json)) fail('the live catalog is missing required key "integrity"');
  const integrity = json.integrity;
  if (!isPlainObject(integrity) || typeof integrity.algorithm !== 'string' || typeof integrity.digest !== 'string') {
    fail('the live catalog\'s "integrity" must be an object with "algorithm" and "digest" strings');
  }

  return json;
}

interface RawShelf { id: string; name: string; sortOrder: number }

/**
 * A shelf-aware catalog (one carrying top-level historical_shelves -- plugin
 * 0.8.0's additive field, Brian, to-claude/0010) must give EVERY work in its
 * `works` list exactly one editorial.historical_shelf_id naming a declared
 * shelf, as the partner's snapshot.v2 schema requires. Throws on the first
 * problem; returns null for a legacy catalog with no historical_shelves,
 * which then parses exactly as before (any stray historical_shelf_id is
 * ignored). The shelf ids are the catalog's own, not a list kept here.
 */
function validateShelves(live: Record<string, unknown>): RawShelf[] | null {
  if (!('historical_shelves' in live)) return null;
  if (!Array.isArray(live.historical_shelves)) fail('the live catalog\'s "historical_shelves" must be an array');
  const shelves: RawShelf[] = [];
  const ids = new Set<string>();
  for (const raw of live.historical_shelves) {
    if (!isPlainObject(raw) || typeof raw.id !== 'string' || !raw.id
      || typeof raw.name !== 'string' || typeof raw.sort_order !== 'number') {
      fail(`every "historical_shelves" entry needs a string "id" and "name" and a numeric "sort_order", got ${JSON.stringify(raw)}`);
    }
    if (ids.has(raw.id)) fail(`"historical_shelves" declares the age '${raw.id}' twice`);
    ids.add(raw.id);
    shelves.push({ id: raw.id, name: raw.name, sortOrder: raw.sort_order });
  }

  const seen = new Map<string, string>();
  for (const raw of live.works as unknown[]) {
    if (!isPlainObject(raw) || typeof raw.id !== 'string' || !raw.id) continue;
    const editorial = isPlainObject(raw.editorial) ? raw.editorial : {};
    const shelf = editorial.historical_shelf_id;
    if (shelf === undefined || shelf === '' || shelf === null) {
      fail(`work '${raw.id}' has no editorial.historical_shelf_id, but the catalog declares historical_shelves`);
    }
    if (Array.isArray(shelf)) {
      fail(`work '${raw.id}' names more than one age in editorial.historical_shelf_id (${JSON.stringify(shelf)}); a work sits in exactly one`);
    }
    if (typeof shelf !== 'string') {
      fail(`work '${raw.id}' must name one age id in editorial.historical_shelf_id, got ${JSON.stringify(shelf)}`);
    }
    if (!ids.has(shelf)) fail(`work '${raw.id}' names unknown age '${shelf}' in editorial.historical_shelf_id`);
    const earlier = seen.get(raw.id);
    if (earlier !== undefined && earlier !== shelf) {
      fail(`work '${raw.id}' is listed twice, in two ages ('${earlier}' and '${shelf}'); a work sits in exactly one`);
    }
    seen.set(raw.id, shelf);
  }
  return shelves;
}

/** The seed is our own generated file; validated loosely (never fatal to a
 *  build over our own data) and defaults to empty when absent. */
function normalizeSeed(json: unknown): { collections: RawCollection[]; works: RawWork[] } {
  if (!isPlainObject(json)) return { collections: [], works: [] };
  return {
    collections: Array.isArray(json.collections) ? (json.collections as RawCollection[]) : [],
    works: Array.isArray(json.works) ? (json.works as RawWork[]) : [],
  };
}

function toCollection(raw: RawCollection): CatalogCollection | null {
  if (typeof raw.id !== 'string' || !raw.id) return null;
  return {
    id: raw.id,
    name: typeof raw.name === 'string' ? raw.name : raw.id,
    description: typeof raw.description === 'string' ? raw.description : '',
    accent: isPlainObject(raw.presentation) && typeof raw.presentation.accent === 'string'
      ? raw.presentation.accent : '',
    featured: raw.featured === true,
    state: typeof raw.state === 'string' ? raw.state : 'draft',
    sortOrder: typeof raw.sort_order === 'number' ? raw.sort_order : 0,
    parentId: typeof raw.parent_id === 'string' ? raw.parent_id : '',
    works: [],
    children: [],
    orphaned: false,
  };
}

function toWork(raw: RawWork, presetIds: Set<string>): CatalogWork | null {
  if (typeof raw.id !== 'string' || !raw.id) return null;
  const editorial = isPlainObject(raw.editorial) ? raw.editorial : {};
  const collectionIds = Array.isArray(editorial.collection_ids)
    ? editorial.collection_ids.filter((v): v is string => typeof v === 'string')
    : [];
  return {
    id: raw.id,
    facts: isPlainObject(raw.facts) ? raw.facts : {},
    description: typeof editorial.description === 'string' ? editorial.description : '',
    defaultTranslation: typeof editorial.default_translation === 'string' ? editorial.default_translation : '',
    preset: typeof editorial.preset === 'string' && presetIds.has(editorial.preset) ? editorial.preset : '',
    collectionIds,
    historicalShelfId: typeof editorial.historical_shelf_id === 'string' ? editorial.historical_shelf_id : '',
    featured: editorial.featured === true,
    state: typeof editorial.state === 'string' ? editorial.state : 'draft',
  };
}

function parsePresets(presentation: Record<string, unknown>): Record<string, CatalogPreset> {
  if (!isPlainObject(presentation.presets)) return {};
  return Object.fromEntries(
    Object.entries(presentation.presets)
      .filter((entry): entry is [string, Record<string, unknown>] => isPlainObject(entry[1]))
      .map(([id, preset]) => [id, {
        id,
        label: typeof preset.label === 'string' ? preset.label : '',
        description: typeof preset.description === 'string' ? preset.description : '',
        colors: {
          ink: typeof preset.color_ink === 'string' ? preset.color_ink : '',
          paper: typeof preset.color_paper === 'string' ? preset.color_paper : '',
          surface: typeof preset.color_surface === 'string' ? preset.color_surface : '',
          accent: typeof preset.color_accent === 'string' ? preset.color_accent : '',
          muted: typeof preset.color_muted === 'string' ? preset.color_muted : '',
          line: typeof preset.color_line === 'string' ? preset.color_line : '',
        },
      }]),
  );
}

/** Live wins entirely over seed for a shared id; a seed-only record is added
 *  with its own state. */
function mergeById<T extends { id: string }>(live: T[], seed: T[]): T[] {
  const out = new Map<string, T>();
  for (const item of seed) out.set(item.id, item);
  for (const item of live) out.set(item.id, item);
  return [...out.values()];
}

function keep(state: string, includeDrafts: boolean): boolean {
  return state === 'active' || (includeDrafts && state === 'draft');
}

function authorOf(work: CatalogWork): string {
  const author = work.facts.author;
  return typeof author === 'string' ? author : '';
}

function titleOf(work: CatalogWork): string {
  const title = work.facts.title;
  return typeof title === 'string' ? title : work.id;
}

// John's ruling, 2026-07-23: "one uniform rule -- testimonia first, fragments
// second, for every author." Plain alphabetical order puts "Fragments" ahead
// of "Testimonia", so the shared compareWorkTitles tie-break runs instead.
function sortWorks(works: CatalogWork[]): CatalogWork[] {
  return [...works].sort((a, b) => {
    const byAuthor = authorOf(a).localeCompare(authorOf(b));
    return byAuthor !== 0 ? byAuthor : compareWorkTitles(titleOf(a), titleOf(b));
  });
}

function sortCollections(collections: CatalogCollection[]): CatalogCollection[] {
  return [...collections].sort((a, b) => (
    a.sortOrder - b.sortOrder || a.name.localeCompare(b.name)
  ));
}

/**
 * Merges the partner's live catalog with our local editorial seed, keeps
 * only `active` collections/works (plus `draft` ones when `includeDrafts` is
 * set — the demo/staging build), and returns them ordered and nested for
 * direct rendering.
 */
export function parseCatalog(liveJson: unknown, seedJson: unknown, opts: { includeDrafts: boolean }): Catalog {
  const live = validateLive(liveJson);
  const rawShelves = validateShelves(live);
  const seed = normalizeSeed(seedJson);
  const presentation = live.presentation as Record<string, unknown>;
  const presets = parsePresets(presentation);
  const presetIds = new Set(Object.keys(presets));
  const defaultPreset = isPlainObject(presentation.theme)
    && typeof presentation.theme.preset === 'string'
    && presetIds.has(presentation.theme.preset)
    ? presentation.theme.preset : '';

  const liveCollections = (live.collections as unknown[])
    .map((c) => toCollection(c as RawCollection)).filter((c): c is CatalogCollection => c !== null);
  const seedCollections = seed.collections
    .map((c) => toCollection(c)).filter((c): c is CatalogCollection => c !== null);
  const mergedCollections = mergeById(liveCollections, seedCollections)
    .filter((c) => keep(c.state, opts.includeDrafts));

  const liveWorks = (live.works as unknown[])
    .map((w) => toWork(w as RawWork, presetIds)).filter((w): w is CatalogWork => w !== null);
  const seedWorks = seed.works
    .map((w) => toWork(w, presetIds)).filter((w): w is CatalogWork => w !== null);
  const mergedWorks = mergeById(liveWorks, seedWorks)
    .filter((w) => keep(w.state, opts.includeDrafts));

  const byCollectionId = new Map(mergedCollections.map((c) => [c.id, c]));
  for (const work of mergedWorks) {
    for (const id of work.collectionIds) {
      byCollectionId.get(id)?.works.push(work);
    }
  }
  for (const c of mergedCollections) c.works = sortWorks(c.works);

  // The same CatalogWork objects as the collections above -- an age and a
  // collection list one work, never a copy. A seed-only work (our own
  // editorial seed carries no ages) sits in no age: it goes in `unshelved`,
  // and still appears in `works` and in its collections.
  const shelves = rawShelves === null ? null : [...rawShelves]
    .sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name))
    .map((shelf) => ({
      ...shelf,
      works: sortWorks(mergedWorks.filter((w) => w.historicalShelfId === shelf.id)),
    }));
  const shelfIds = new Set(rawShelves?.map((shelf) => shelf.id));
  const unshelved = rawShelves === null ? [] : sortWorks(mergedWorks.filter((w) => !shelfIds.has(w.historicalShelfId)));

  // A child whose parent_id names no collection we kept -- absent entirely,
  // or itself filtered out (a draft parent while drafts are off) -- is
  // promoted to a root collection rather than silently lost: it keeps its
  // own sort_order and is marked `orphaned` so a caller (or a test) can see
  // what happened.
  const topLevel: CatalogCollection[] = [];
  for (const c of mergedCollections) {
    if (!c.parentId) {
      topLevel.push(c);
      continue;
    }
    const parent = byCollectionId.get(c.parentId);
    if (parent) parent.children.push(c);
    else {
      c.orphaned = true;
      topLevel.push(c);
    }
  }
  for (const c of mergedCollections) c.children = sortCollections(c.children);

  const content = isPlainObject(presentation) && isPlainObject(presentation.content)
    ? Object.fromEntries(
      Object.entries(presentation.content).filter((entry): entry is [string, string] => typeof entry[1] === 'string'),
    )
    : {};
  const visibility = isPlainObject(presentation) && isPlainObject(presentation.visibility)
    ? Object.fromEntries(
      Object.entries(presentation.visibility).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean'),
    )
    : {};

  return { collections: sortCollections(topLevel), shelves, unshelved, works: mergedWorks, presets, defaultPreset, content, visibility };
}
