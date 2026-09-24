// lyceumCatalog()/weekPassage()/readingPaths() — the build-time assembly
// behind the Lyceum homepage and Catalog page. Like built-works.test.ts, this
// chdirs into a temp app root seeded with exactly the manifests it wants
// "built", plus a sibling fixtures/ directory carrying a tiny live catalog +
// editorial seed, so the assertions bind the assembly rather than whatever
// this checkout happens to have on disk. Modules are re-imported per test
// (lyceum-catalog.ts, built-works.ts and works.ts all memoize).
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { lyceumWorkKey } from '@shared/lib/works';

const realCwd = process.cwd();

const LIVE_BASE = {
  schema_version: '2.0',
  library_id: 'lyceum-library',
  revision: 1,
  generated_at: '2026-01-01T00:00:00Z',
  redirects: [],
  integrity: { algorithm: 'sha256', digest: 'x' },
};

function liveCollection(overrides: Record<string, unknown> = {}) {
  return {
    id: 'greek', slug: 'greek', name: 'Greek (live)', description: '', approved_by: '',
    parent_id: '', state: 'active', sort_order: 5, featured: false,
    presentation: { accent: '', label: '', layout: 'grid' },
    ...overrides,
  };
}

function seedCollection(overrides: Record<string, unknown> = {}) {
  return {
    id: 'greek', slug: 'greek', name: 'Greek (seed)', description: '', approved_by: '',
    parent_id: '', state: 'draft', sort_order: 1, featured: false,
    _draft: true, presentation: { accent: '', label: '', layout: 'grid' },
    ...overrides,
  };
}

// 'heraclitus-fragments' is a real registry work (author 'heraclitus', slug
// 'fragments') so its lyceum key round-trips to a real work id without any
// registry stubbing.
function catalogWork(id: string, overrides: Record<string, unknown> = {}) {
  const facts = {
    author: 'Heraclitus', title: 'Fragments', language: 'grc',
    route: '/heraclitus/fragments/', citation: { extent: '139 sections' },
    translations: [{ id: 'freeman', label: 'Freeman' }],
    ...((overrides.facts as Record<string, unknown>) ?? {}),
  };
  const editorial = {
    description: 'A description.', approved_by: '', default_translation: 'freeman',
    collection_ids: ['greek'], preset: '', featured: false, state: 'active',
    ...((overrides.editorial as Record<string, unknown>) ?? {}),
  };
  return { id, facts, editorial };
}

function writeCatalogFixtures(
  parent: string,
  opts: {
    liveCollections?: unknown[]; liveWorks?: unknown[];
    seedCollections?: unknown[]; seedWorks?: unknown[];
    content?: Record<string, string>; visibility?: Record<string, boolean>;
    presets?: Record<string, unknown>; defaultPreset?: string;
    liveOverride?: unknown; // when set, written verbatim (malformed-input tests)
  } = {},
): { catalogPath: string } {
  const fixturesDir = path.join(parent, 'fixtures');
  mkdirSync(fixturesDir, { recursive: true });
  const live = opts.liveOverride ?? {
    ...LIVE_BASE,
    presentation: {
      content: opts.content ?? {}, visibility: opts.visibility ?? {},
      presets: opts.presets ?? {}, theme: { preset: opts.defaultPreset ?? '' },
    },
    collections: opts.liveCollections ?? [],
    works: opts.liveWorks ?? [],
  };
  const catalogPath = path.join(fixturesDir, 'catalog.snapshot.v2.live-2026-09-08.json');
  writeFileSync(catalogPath, JSON.stringify(live));
  const seed = { schema_version: '2.0', collections: opts.seedCollections ?? [], works: opts.seedWorks ?? [] };
  writeFileSync(path.join(fixturesDir, 'editorial.seed.json'), JSON.stringify(seed));
  return { catalogPath };
}

const dkManifest = (start: string, end: string) => ({ citation: { books: [{ n: 1, start, end }] } });

function seedApp(works: Record<string, unknown> = {}): string {
  const parent = mkdtempSync(path.join(tmpdir(), 'lyceum-catalog-'));
  const appDir = path.join(parent, 'app');
  for (const [id, manifest] of Object.entries(works)) {
    mkdirSync(path.join(appDir, 'public', 'data', id), { recursive: true });
    writeFileSync(path.join(appDir, 'public', 'data', id, 'manifest.json'), JSON.stringify(manifest));
  }
  mkdirSync(appDir, { recursive: true });
  process.chdir(appDir);
  return parent;
}

async function load() {
  vi.resetModules();
  return await import('../lib/lyceum-catalog');
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => {}); // silence built-works' warnOnce
});

afterEach(() => {
  process.chdir(realCwd);
  vi.unstubAllEnvs();
});

describe('lyceumCatalog', () => {
  it('returns a work preset or the catalog default', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { preset: 'legal' } })],
      presets: { legal: { label: 'Legal' }, modern: { label: 'Modern' } },
      defaultPreset: 'modern',
    });
    const { workPreset } = await load();
    expect(workPreset('heraclitus-fragments')).toBe('legal');
    expect(workPreset('no-such-work')).toBe('modern');
  });

  it('keeps a work preset when the work sits in no collection, and falls back for a work with none', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139'), 'parmenides-fragments': dkManifest('B1', 'B19') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [
        catalogWork('lyceum:heraclitus.fragments', { editorial: { preset: 'legal', collection_ids: [] } }),
        catalogWork('lyceum:parmenides.fragments', { editorial: { preset: '' } }),
      ],
      presets: { legal: { label: 'Legal' }, modern: { label: 'Modern' } },
      defaultPreset: 'modern',
    });
    const { workPreset } = await load();
    expect(workPreset('heraclitus-fragments')).toBe('legal');
    expect(workPreset('parmenides-fragments')).toBe('modern');
  });

  it('lists a live catalog work under its resolved registry work, with the right extent', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments')],
    });
    const { lyceumCatalog } = await load();
    const model = lyceumCatalog();

    const section = model.sections.find((s) => s.id === 'greek')!;
    expect(section).toBeDefined();
    expect(section.name).toBe('Greek (live)'); // live wins over any same-id seed
    const work = section.groups.flatMap((g) => g.authors).flatMap((a) => a.works)[0];
    expect(work.id).toBe('heraclitus-fragments');
    expect(work.extent).toBe('B1–B139');
  });

  it('live wins entirely over a seed record with the same id -- whole record, not per field', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection({ name: 'Greek (live)' })],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { description: 'Live description.' } })],
      // The seed record carries an extra field (a seed-only accent) and its
      // own description; neither may survive the merge once live wins.
      seedCollections: [seedCollection({
        name: 'Greek (seed)', description: 'Seed collection description.',
        presentation: { accent: 'seed-only-accent', label: '', layout: 'grid' },
      })],
      // A registry-matched work's editorial fields (description, featured,
      // default_translation, ...) never reach this app-level model at all --
      // catalogSectionFor takes id/title/extent from OUR registry, not the
      // catalog record -- so whole-vs-field-by-field replacement of a
      // work's editorial data is proven at the source layer instead
      // (shared/__tests__/lyceum-catalog-source.test.ts).
      seedWorks: [catalogWork('lyceum:heraclitus.fragments', {
        editorial: { description: 'Seed description.' },
      })],
    });
    const { lyceumCatalog } = await load();
    const model = lyceumCatalog();
    const sections = model.sections.filter((s) => s.id === 'greek');
    expect(sections).toHaveLength(1); // merged into one record, not two
    expect(sections[0].name).toBe('Greek (live)');
    // Whole-record replacement: the seed-only accent never leaks through.
    expect(sections[0].accent).not.toBe('seed-only-accent');
    expect(sections[0].accent).toBeNull(); // the live collection sets no accent
  });

  it('adds a seed-only collection and work under their own state', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [],
      liveWorks: [],
      seedCollections: [seedCollection({ state: 'active' })],
      seedWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { state: 'active' } })],
    });
    const { lyceumCatalog } = await load();
    const model = lyceumCatalog();
    expect(model.sections.map((s) => s.id)).toContain('greek');
  });

  it('drops a draft collection/work by default, and keeps it when PUBLIC_LYCEUM_DRAFTS=1', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection({ state: 'draft' })],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { state: 'draft' } })],
    });

    { // default: drafts filtered out
      const { lyceumCatalog } = await load();
      expect(lyceumCatalog().sections.map((s) => s.id)).not.toContain('greek');
    }

    { // PUBLIC_LYCEUM_DRAFTS=1: drafts kept
      vi.stubEnv('PUBLIC_LYCEUM_DRAFTS', '1');
      const { lyceumCatalog } = await load();
      expect(lyceumCatalog().sections.map((s) => s.id)).toContain('greek');
    }
  });

  it('orders collections by sort_order, not declaration order', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [
        liveCollection({ id: 'second', slug: 'second', name: 'Second', sort_order: 2 }),
        liveCollection({ id: 'first', slug: 'first', name: 'First', sort_order: 1 }),
      ],
      liveWorks: [
        catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: ['first', 'second'] } }),
      ],
    });
    const { lyceumCatalog } = await load();
    const ids = lyceumCatalog().sections.map((s) => s.id);
    expect(ids).toEqual(['first', 'second']);
  });

  it('links a foreign (unresolvable) work to the partner origin only when PUBLIC_PARTNER_ORIGIN is set', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:caesar.civil-war', {
        facts: { author: 'Julius Caesar', title: 'The Civil War', language: 'la', route: '/caesar/civil-war/' },
      })],
    });

    { // unset: the work is omitted, but the collection itself still shows
      // (ruling 2026-09-13: an empty collection is shown, not dropped)
      const { lyceumCatalog } = await load();
      const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
      expect(section).toBeDefined();
      expect(section.workCount).toBe(0);
      expect(section.empty).toBe(true);
    }

    { // set: linked out, with a visible hostname marker (data, not copy)
      vi.stubEnv('PUBLIC_PARTNER_ORIGIN', 'https://library.lyceum.institute');
      const { lyceumCatalog } = await load();
      const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
      expect(section).toBeDefined();
      const work = section.groups.flatMap((g) => g.authors).flatMap((a) => a.works)[0];
      expect(work.href).toBe('https://library.lyceum.institute/caesar/civil-war/');
      expect((work as { external?: string }).external).toBe('library.lyceum.institute');
    }
  });

  it('sorts a foreign author\'s Testimonia before its Fragments, not alphabetically (John, 2026-07-23 ruling, Sol finding 2)', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [
        catalogWork('lyceum:foreignauthor.fragments', {
          facts: { author: 'Foreign Author', title: 'Fragments', language: 'grc', route: '/foreign-author/fragments/' },
        }),
        catalogWork('lyceum:foreignauthor.testimonia', {
          facts: { author: 'Foreign Author', title: 'Testimonia', language: 'grc', route: '/foreign-author/testimonia/' },
        }),
      ],
    });
    vi.stubEnv('PUBLIC_PARTNER_ORIGIN', 'https://library.lyceum.institute');
    const { lyceumCatalog } = await load();
    const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
    const author = section.groups.flatMap((g) => g.authors).find((a) => a.name === 'Foreign Author')!;
    expect(author).toBeDefined();
    expect(author.works.map((w) => w.title)).toEqual(['Testimonia', 'Fragments']);
  });

  it('throws a clear error for a malformed live catalog', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, { liveOverride: { schema_version: '1.0', collections: [], works: [] } });
    const { lyceumCatalog } = await load();
    expect(() => lyceumCatalog()).toThrow(/schema_version/);
  });

  it('links a work that is registered but not built in this checkout to the partner origin, same as any foreign work', async () => {
    // 'heraclitus-fragments' resolves via workIdFromLyceumKey (it's a real
    // registry work), but seedApp({}) below builds nothing -- the staging
    // case for a partial data set (§11.6 rule 5).
    const parent = seedApp({});
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments')],
    });

    { // unset: omitted, never a link into our own (unbuilt) page
      const { lyceumCatalog } = await load();
      const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
      expect(section.workCount).toBe(0);
    }

    { // set: linked to the partner origin, exactly like a work of Brian's
      vi.stubEnv('PUBLIC_PARTNER_ORIGIN', 'https://library.lyceum.institute');
      const { lyceumCatalog } = await load();
      const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
      const work = section.groups.flatMap((g) => g.authors).flatMap((a) => a.works)[0];
      expect(work.href).toBe('https://library.lyceum.institute/heraclitus/fragments/');
      expect((work as { external?: string }).external).toBe('library.lyceum.institute');
    }
  });

  it('nests a child collection under its parent, one level, flattened in order right after it', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [
        liveCollection({ id: 'greek', slug: 'greek', name: 'Greek', sort_order: 1 }),
        liveCollection({ id: 'greek-fragments', slug: 'greek-fragments', name: 'Fragments & Testimonia', parent_id: 'greek', sort_order: 1 }),
      ],
      // Only the child collection has a work -- the parent has none of its own.
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: ['greek-fragments'] } })],
    });
    const { lyceumCatalog } = await load();
    const model = lyceumCatalog();
    const ids = model.sections.map((s) => s.id);
    expect(ids.indexOf('greek')).toBe(0);
    expect(ids.indexOf('greek-fragments')).toBe(1); // right after its parent

    const parentSection = model.sections.find((s) => s.id === 'greek')!;
    const childSection = model.sections.find((s) => s.id === 'greek-fragments')!;
    expect(parentSection.parentId).toBeNull();
    expect(parentSection.workCount).toBe(0);
    expect(childSection.parentId).toBe('greek');
    expect(childSection.workCount).toBe(1);
  });

  it('shows an empty active collection rather than dropping it, with the partner\'s own empty-collection note', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [],
      content: { 'collection.empty': 'No published texts are assigned to this collection.' },
    });
    const { lyceumCatalog } = await load();
    const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
    expect(section).toBeDefined();
    expect(section.empty).toBe(true);
    expect(section.note).toBe('No published texts are assigned to this collection.');
  });

  it('omits the empty-collection note when the partner has not published that key', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, { liveCollections: [liveCollection()], liveWorks: [] });
    const { lyceumCatalog } = await load();
    const section = lyceumCatalog().sections.find((s) => s.id === 'greek')!;
    expect(section.empty).toBe(true);
    expect(section.note).toBeNull();
  });

  it('reads a work with no manifest ranges without inventing an extent', async () => {
    const parent = seedApp({ 'heraclitus-fragments': {} });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments')],
    });
    const { lyceumCatalog } = await load();
    const work = lyceumCatalog().sections[0].groups.flatMap((g) => g.authors).flatMap((a) => a.works)[0];
    expect(work.extent).toBe('');
  });

  it('gives each author their own citation-scheme range summary (DK, Bekker)', async () => {
    const parent = seedApp({
      'heraclitus-fragments': dkManifest('B1', 'B139'),
      EN: { citation: { books: [{ n: 1, start: '1094a', end: '1181b' }] } },
    });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [
        catalogWork('lyceum:heraclitus.fragments'),
        catalogWork(lyceumWorkKey('EN'), {
          facts: { author: 'Aristotle', title: 'Nicomachean Ethics', language: 'grc', route: '/aristotle/nicomachean-ethics/' },
          editorial: { collection_ids: ['greek'], default_translation: 'freeman' },
        }),
      ],
    });
    const { lyceumCatalog } = await load();
    const authors = lyceumCatalog().sections[0].groups.flatMap((g) => g.authors);
    const heraclitus = authors.find((a) => a.name === 'Heraclitus')!;
    const aristotle = authors.find((a) => a.name === 'Aristotle')!;
    expect(heraclitus.range).toBe('DK 22');
    expect(aristotle.range).toBe('Bekker');
    expect(aristotle.works[0].extent).toBe('10 books · 1094a–1181b');
  });
});

// P3 finding (Codex Sol): workCollections had no dedicated coverage of its
// own -- only exercised indirectly through lyceumCatalog(). Mirrors
// workPreset's own seedApp/writeCatalogFixtures setup above.
describe('workCollections', () => {
  it('flattens a child collection one level, same as a top-level one', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [
        liveCollection({ id: 'greek', slug: 'greek', name: 'Greek', sort_order: 1 }),
        liveCollection({
          id: 'greek-fragments', slug: 'greek-fragments', name: 'Fragments & Testimonia',
          parent_id: 'greek', sort_order: 1,
        }),
      ],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: ['greek-fragments'] } })],
    });
    const { workCollections } = await load();
    expect(workCollections('heraclitus-fragments')).toEqual([{ id: 'greek-fragments', name: 'Fragments & Testimonia' }]);
  });

  it('drops a draft collection unless PUBLIC_LYCEUM_DRAFTS=1', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection({ state: 'draft' })],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: ['greek'] } })],
    });

    { // default: the draft collection is filtered out, same as the page
      const { workCollections } = await load();
      expect(workCollections('heraclitus-fragments')).toEqual([]);
    }

    { // PUBLIC_LYCEUM_DRAFTS=1: kept
      vi.stubEnv('PUBLIC_LYCEUM_DRAFTS', '1');
      const { workCollections } = await load();
      expect(workCollections('heraclitus-fragments')).toEqual([{ id: 'greek', name: 'Greek (live)' }]);
    }
  });

  it('drops a collection_ids entry naming a collection that never existed', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: ['no-such-collection'] } })],
    });
    const { workCollections } = await load();
    expect(workCollections('heraclitus-fragments')).toEqual([]);
  });

  it('returns empty for a kept work that names no collection', async () => {
    const parent = seedApp({ 'heraclitus-fragments': dkManifest('B1', 'B139') });
    writeCatalogFixtures(parent, {
      liveCollections: [liveCollection()],
      liveWorks: [catalogWork('lyceum:heraclitus.fragments', { editorial: { collection_ids: [] } })],
    });
    const { workCollections } = await load();
    expect(workCollections('heraclitus-fragments')).toEqual([]);
  });

  it('returns empty for a work id the catalog names nothing for', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, { liveCollections: [liveCollection()], liveWorks: [] });
    const { workCollections } = await load();
    expect(workCollections('no-such-work')).toEqual([]);
  });
});

describe('lyceumContent / lyceumVisible', () => {
  it('prefers the live catalog\'s content string, falling back when a key is missing', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, { content: { 'home.title': 'From the live catalog' } });
    const { lyceumContent } = await load();
    expect(lyceumContent('home.title', 'Fallback title')).toBe('From the live catalog');
    expect(lyceumContent('nav.library', 'Fallback library')).toBe('Fallback library');
  });

  it('respects a visibility flag, defaulting to shown when absent', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, { visibility: { 'home.featured': false } });
    const { lyceumVisible } = await load();
    expect(lyceumVisible('home.featured')).toBe(false);
    expect(lyceumVisible('home.collections')).toBe(true);
  });
});

describe('weekPassage', () => {
  it('pairs the opening of the source with the same sentences of its English', async () => {
    const parent = seedApp({
      enchiridion: { citation: { books: [{ n: 1, start: '1', end: '53' }] } },
    });
    writeCatalogFixtures(parent, {});
    mkdirSync(path.join(parent, 'app', 'public', 'data', 'enchiridion'), { recursive: true });
    writeFileSync(
      path.join(parent, 'app', 'public', 'data', 'enchiridion', 'book-01.json'),
      JSON.stringify({
        book: 1,
        segments: [{
          column: '1',
          greek: [{ text: 'Τῶν ὄντων τὰ μέν ἐστιν ἐφ᾽' }, { text: `ἡμῖν. δεύτερον μὲν λόγον λέγω περὶ τῶν ἐφ᾽ ἡμῖν καὶ τῶν οὐκ ἐφ᾽ ἡμῖν ὅσα τε ἡμέτερα ἔργα ἐστὶ καὶ ὅσα οὐχ ἡμέτερα. τρίτον.` }],
          english: { text: 'Some things are up to us. The second sentence runs long enough to fill the column beside its Greek. Third sentence.' },
        }],
      }),
    );
    const { weekPassage } = await load();
    const passage = weekPassage()!;

    // One Greek sentence is short, so the second is taken — and the English
    // follows sentence for sentence, never half a sentence.
    expect(passage.source).toBe(`Τῶν ὄντων τὰ μέν ἐστιν ἐφ᾽ ἡμῖν. δεύτερον μὲν λόγον λέγω περὶ τῶν ἐφ᾽ ἡμῖν καὶ τῶν οὐκ ἐφ᾽ ἡμῖν ὅσα τε ἡμέτερα ἔργα ἐστὶ καὶ ὅσα οὐχ ἡμέτερα.`);
    expect(passage.english).toBe('Some things are up to us. The second sentence runs long enough to fill the column beside its Greek.');
    expect(passage.sourceRef).toBe('Ench. 1');
    // Enchiridion is bookless (isBookless: books === 1), so its division id
    // is 'text', not 'book-1' (shared/lib/works.ts's divisionId).
    expect(passage.href).toBe('/read/epictetus/enchiridion/text');
    expect(passage.label).toBe('Passage of the week · Epictetus, Enchiridion');
  });

  it('is null when nothing it could quote is built', async () => {
    const parent = seedApp({});
    writeCatalogFixtures(parent, {});
    const { weekPassage } = await load();
    expect(weekPassage()).toBeNull();
  });
});

// Cross-check (design point 4): every emitted Lyceum partner manifest's own
// `work` key must equal lyceumWorkKey() of the work id that produced it.
// scripts/emit-lyceum-manifest.mjs itself stays untouched -- this only reads
// its output. Guarded: a no-op when this checkout has no build/dist (a fresh
// clone, or CI before the pipeline runs).
describe('lyceumWorkKey matches every emitted partner manifest (guarded)', () => {
  it('agrees with scripts/emit-lyceum-manifest.mjs\'s own work key for every emitted manifest', async () => {
    process.chdir(realCwd);
    const distDir = path.join(realCwd, '..', 'build', 'dist');
    if (!existsSync(distDir)) return; // nothing built in this checkout
    const indexPath = path.join(distDir, 'manifests', 'index.json');
    if (!existsSync(indexPath)) return; // pipeline ran but didn't emit the manifest index
    const index = JSON.parse(readFileSync(indexPath, 'utf8')) as { manifests: { work: string }[] };

    const dirs = readdirSync(distDir, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
      .filter((name) => existsSync(path.join(distDir, name, 'manifest.lyceum.json')));
    expect(dirs.length).toBeGreaterThan(0);
    // No swallowed failures: every dist directory carrying a partner
    // manifest must round-trip through lyceumWorkKey, and the number this
    // test actually compares must equal the number the pipeline emitted --
    // never a silent undercount.
    let compared = 0;
    for (const workId of dirs) {
      const key = lyceumWorkKey(workId);
      const manifest = JSON.parse(readFileSync(path.join(distDir, workId, 'manifest.lyceum.json'), 'utf8'));
      expect(manifest.work).toBe(key);
      compared += 1;
    }
    expect(compared).toBe(index.manifests.length);
  });
});
