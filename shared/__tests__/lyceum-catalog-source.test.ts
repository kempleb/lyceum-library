import { describe, expect, it } from 'vitest';
import { parseCatalog } from '../lib/lyceum-catalog-source';
import { compareWorkTitles } from '../lib/work-title-order';

// parseCatalog's own contract (docs/lyceum-shared-repo-plan.md §11.6): full
// validation of the partner's live snapshot against the required keys of
// schemas/snapshot.v2.schema.json (Codex review 2026-09-13, finding 4), and
// the merge/nesting rules a caller (app/src/lib/lyceum-catalog.ts) depends on
// (findings 5 and 6).

function validLive(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: '2.0',
    library_id: 'lyceum-library',
    revision: 1,
    generated_at: '2026-01-01T00:00:00Z',
    presentation: { content: {}, visibility: {} },
    collections: [],
    works: [],
    integrity: { algorithm: 'sha256', digest: 'x' },
    ...overrides,
  };
}

function omit(obj: Record<string, unknown>, key: string): Record<string, unknown> {
  const out = { ...obj };
  delete out[key];
  return out;
}

describe('parseCatalog: live snapshot validation (every required key)', () => {
  const requiredKeys = [
    'schema_version', 'library_id', 'revision', 'generated_at',
    'presentation', 'collections', 'works', 'integrity',
  ];

  it.each(requiredKeys)('throws naming "%s" when it is missing', (key) => {
    const live = omit(validLive(), key);
    expect(() => parseCatalog(live, undefined, { includeDrafts: false })).toThrow(new RegExp(key));
  });

  it('throws when "revision" is not an integer >= 1', () => {
    expect(() => parseCatalog(validLive({ revision: 0 }), undefined, { includeDrafts: false })).toThrow(/revision/);
    expect(() => parseCatalog(validLive({ revision: 1.5 }), undefined, { includeDrafts: false })).toThrow(/revision/);
    expect(() => parseCatalog(validLive({ revision: '1' }), undefined, { includeDrafts: false })).toThrow(/revision/);
  });

  it('throws when "generated_at" is not a string', () => {
    expect(() => parseCatalog(validLive({ generated_at: 12345 }), undefined, { includeDrafts: false })).toThrow(/generated_at/);
  });

  it('throws when "presentation" is null or not an object', () => {
    expect(() => parseCatalog(validLive({ presentation: null }), undefined, { includeDrafts: false })).toThrow(/presentation/);
    expect(() => parseCatalog(validLive({ presentation: [] }), undefined, { includeDrafts: false })).toThrow(/presentation/);
  });

  it('throws when "collections" or "works" is not an array', () => {
    expect(() => parseCatalog(validLive({ collections: {} }), undefined, { includeDrafts: false })).toThrow(/collections/);
    expect(() => parseCatalog(validLive({ works: {} }), undefined, { includeDrafts: false })).toThrow(/works/);
  });

  it('throws when "integrity" is missing algorithm or digest', () => {
    expect(() => parseCatalog(validLive({ integrity: { digest: 'x' } }), undefined, { includeDrafts: false })).toThrow(/integrity/);
    expect(() => parseCatalog(validLive({ integrity: { algorithm: 'sha256' } }), undefined, { includeDrafts: false })).toThrow(/integrity/);
    expect(() => parseCatalog(validLive({ integrity: null }), undefined, { includeDrafts: false })).toThrow(/integrity/);
  });

  it('accepts a snapshot with every required key present and valid', () => {
    expect(() => parseCatalog(validLive(), undefined, { includeDrafts: false })).not.toThrow();
  });
});

function rawCollection(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 'greek', name: 'Greek', description: '', state: 'active',
    sort_order: 1, featured: false, parent_id: '', presentation: { accent: '' },
    ...overrides,
  };
}

function rawWork(id: string, overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id, facts: { title: id },
    editorial: { collection_ids: ['greek'], state: 'active', description: 'A description.', ...((overrides.editorial as object) ?? {}) },
    ...omit(overrides, 'editorial'),
  };
}

const presets = {
  legal: {
    label: 'Legal', description: 'For legal texts.',
    color_ink: '#111111', color_paper: '#fefefe', color_surface: '#eeeeee',
    color_accent: '#222222', color_muted: '#333333', color_line: '#444444',
  },
};

describe('parseCatalog: presentation presets', () => {
  it('parses presets and resolves the library and work defaults', () => {
    const catalog = parseCatalog(validLive({
      presentation: { content: {}, visibility: {}, presets, theme: { preset: 'legal' } },
      collections: [rawCollection()],
      works: [rawWork('lyceum:x.legal', { editorial: { preset: 'legal' } })],
    }), undefined, { includeDrafts: false });

    expect(catalog.presets.legal).toEqual({
      id: 'legal', label: 'Legal', description: 'For legal texts.',
      colors: {
        ink: '#111111', paper: '#fefefe', surface: '#eeeeee', accent: '#222222',
        muted: '#333333', line: '#444444',
      },
    });
    expect(catalog.defaultPreset).toBe('legal');
    expect(catalog.collections[0].works[0].preset).toBe('legal');
  });

  it('clears an unknown work preset and seed-work presets', () => {
    const catalog = parseCatalog(validLive({
      presentation: { content: {}, visibility: {}, presets, theme: { preset: 'legal' } },
      collections: [rawCollection()],
      works: [rawWork('lyceum:x.unknown', { editorial: { preset: 'unknown' } })],
    }), {
      collections: [rawCollection({ id: 'seed' })],
      works: [rawWork('lyceum:x.seed', { editorial: { collection_ids: ['seed'] } })],
    }, { includeDrafts: false });

    expect(catalog.collections.flatMap((collection) => collection.works)
      .find((work) => work.id === 'lyceum:x.unknown')?.preset).toBe('');
    expect(catalog.collections.flatMap((collection) => collection.works)
      .find((work) => work.id === 'lyceum:x.seed')?.preset).toBe('');
  });

  it('lists every kept work flat, including one no kept collection carries', () => {
    const catalog = parseCatalog(validLive({
      presentation: { content: {}, visibility: {}, presets, theme: { preset: 'legal' } },
      collections: [rawCollection()],
      works: [
        rawWork('lyceum:x.loose', { editorial: { preset: 'legal', collection_ids: [] } }),
        rawWork('lyceum:x.drafted', { editorial: { preset: 'legal', collection_ids: ['no-such-collection'] } }),
      ],
    }), undefined, { includeDrafts: false });
    expect(catalog.collections.flatMap((c) => c.works).map((w) => w.id)).toEqual([]);
    expect(catalog.works.map((w) => [w.id, w.preset])).toEqual([
      ['lyceum:x.loose', 'legal'],
      ['lyceum:x.drafted', 'legal'],
    ]);
  });

  it('uses no presets or default when presentation.presets is missing', () => {
    const catalog = parseCatalog(validLive({ presentation: { content: {}, visibility: {}, theme: { preset: 'legal' } } }), undefined, { includeDrafts: false });
    expect(catalog.presets).toEqual({});
    expect(catalog.defaultPreset).toBe('');
  });
});

describe('parseCatalog: orphan children (finding 5)', () => {
  it('promotes a child whose parent_id names no collection at all, and marks it orphaned', () => {
    const live = validLive({
      collections: [rawCollection({ id: 'child', parent_id: 'no-such-parent' })],
    });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections.map((c) => c.id)).toEqual(['child']);
    expect(catalog.collections[0].orphaned).toBe(true);
  });

  it('promotes a child whose parent is itself filtered out (a draft parent, drafts off), and marks it orphaned', () => {
    const live = validLive({
      collections: [
        rawCollection({ id: 'parent', state: 'draft' }),
        rawCollection({ id: 'child', parent_id: 'parent' }),
      ],
    });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections.map((c) => c.id)).toEqual(['child']);
    expect(catalog.collections[0].orphaned).toBe(true);
  });

  it('nests a child normally (not orphaned) when its parent is kept', () => {
    const live = validLive({
      collections: [
        rawCollection({ id: 'parent' }),
        rawCollection({ id: 'child', parent_id: 'parent' }),
      ],
    });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections.map((c) => c.id)).toEqual(['parent']);
    expect(catalog.collections[0].orphaned).toBe(false);
    expect(catalog.collections[0].children.map((c) => c.id)).toEqual(['child']);
    expect(catalog.collections[0].children[0].orphaned).toBe(false);
  });
});

describe('parseCatalog: live wins entirely over seed (finding 6)', () => {
  it('replaces the whole collection record, not field by field', () => {
    // 'accent' and 'featured' are both real, normalized CatalogCollection
    // fields (toCollection reads presentation.accent and raw.featured) --
    // the seed sets each to a value the live record never uses, so a
    // field-by-field merge and a whole-record replacement would disagree.
    const live = validLive({
      collections: [rawCollection({
        description: 'Live description.', featured: false,
        presentation: { accent: '' },
      })],
    });
    const seed = {
      collections: [rawCollection({
        description: 'Seed description.', featured: true,
        presentation: { accent: '#123456' },
      })],
      works: [],
    };
    const catalog = parseCatalog(live, seed, { includeDrafts: false });
    expect(catalog.collections).toHaveLength(1);
    expect(catalog.collections[0].description).toBe('Live description.');
    expect(catalog.collections[0].accent).toBe('');
    expect(catalog.collections[0].featured).toBe(false);
  });

  it('replaces the whole work record (facts and editorial), not field by field', () => {
    // 'featured' and 'default_translation' are both real, normalized
    // CatalogWork fields (toWork reads editorial.featured and
    // editorial.default_translation) -- an unsupported key like
    // 'seed_only_field' would vanish under either merge strategy, so it
    // proves nothing about whole-record replacement on its own.
    const live = validLive({
      collections: [rawCollection()],
      works: [rawWork('lyceum:x.y', {
        facts: { title: 'Live Title', extra_live_fact: 'present' },
        editorial: { description: 'Live description.', featured: false },
      })],
    });
    const seed = {
      collections: [],
      works: [rawWork('lyceum:x.y', {
        facts: { title: 'Seed Title', seed_only_fact: 'should not survive' },
        editorial: {
          description: 'Seed description.', seed_only_field: 'should not survive',
          featured: true, default_translation: 'x-en',
        },
      })],
    };
    const catalog = parseCatalog(live, seed, { includeDrafts: false });
    const work = catalog.collections[0].works[0];
    expect(work.description).toBe('Live description.');
    expect(work.facts.title).toBe('Live Title');
    expect(work.facts.extra_live_fact).toBe('present');
    expect(work.facts.seed_only_fact).toBeUndefined();
    expect((work as unknown as Record<string, unknown>).seed_only_field).toBeUndefined();
    expect(work.featured).toBe(false);
    expect(work.defaultTranslation).toBe('');
  });
});

describe('parseCatalog: empty collection description (John, 2026-09-22 -- no collection copy)', () => {
  it('carries an empty description through as "", not a placeholder', () => {
    // library/index.astro renders a collection's description with a truthy
    // guard, `{c.description && <p class="note">{c.description}</p>}` --
    // this only omits the <p> when the field is really `''`, so this pins
    // the precondition that guard depends on.
    const live = validLive({ collections: [rawCollection({ description: '' })] });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections[0].description).toBe('');
  });
});

describe('parseCatalog: testimonia before fragments (John, 2026-07-23 ruling)', () => {
  it('orders an author\'s Testimonia work before its Fragments work within a collection', () => {
    // sortWorks sorts by author then title alphabetically -- "Fragments"
    // would otherwise sort before "Testimonia" -- so this needs the
    // dedicated tie-break, not plain localeCompare.
    const live = validLive({
      collections: [rawCollection()],
      works: [
        rawWork('heraclitus-fragments', { facts: { title: 'Fragments', author: 'Heraclitus' } }),
        rawWork('heraclitus-testimonia', { facts: { title: 'Testimonia', author: 'Heraclitus' } }),
      ],
    });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections[0].works.map((w) => w.facts.title)).toEqual(['Testimonia', 'Fragments']);
  });

  // Sol finding 4: the old titleRank tie-break moved BOTH "Testimonia" and
  // "Fragments" ahead of every other title, not just Testimonia into place
  // just before Fragments. A mixed-title catalog pins the difference.
  it('moves only Testimonia into place just before Fragments -- every other title keeps its alphabetical spot', () => {
    const live = validLive({
      collections: [rawCollection()],
      works: [
        rawWork('author-academica', { facts: { title: 'Academica', author: 'Cicero' } }),
        rawWork('author-fragments', { facts: { title: 'Fragments', author: 'Cicero' } }),
        rawWork('author-letters', { facts: { title: 'Letters', author: 'Cicero' } }),
        rawWork('author-testimonia', { facts: { title: 'Testimonia', author: 'Cicero' } }),
      ],
    });
    const catalog = parseCatalog(live, undefined, { includeDrafts: false });
    expect(catalog.collections[0].works.map((w) => w.facts.title)).toEqual([
      'Academica', 'Testimonia', 'Fragments', 'Letters',
    ]);
  });
});

describe('compareWorkTitles: only identical titles tie (Sol re-review)', () => {
  // localeCompare's job is collation, not byte identity -- it calls some
  // DISTINCT strings equal. Confirmed for this pair in this Node/ICU build:
  // 'Fragments'.localeCompare('Fragments\u0000') === 0. Before the fix, a
  // key tie fell through to `return 0` for every pair except
  // Testimonia/Fragments -- not a valid comparator, since two different
  // titles must never compare equal.
  it('never returns 0 for two different titles, even when localeCompare calls their keys equal', () => {
    expect(compareWorkTitles('Fragments', 'Fragments\u0000')).not.toBe(0);
  });

  it('is antisymmetric: sign(cmp(a,b)) === -sign(cmp(b,a)) for every pair', () => {
    const titles = ['Testimonia', 'Fragments', 'Fragments\u0000', 'Academica'];
    const sign = (n: number) => (n > 0 ? 1 : n < 0 ? -1 : 0);
    for (const a of titles) {
      for (const b of titles) {
        // sign(0) + sign(-0) === 0 too, so summing avoids a false failure
        // from +0/-0 not being `Object.is`-equal on the diagonal (a === b).
        expect(sign(compareWorkTitles(a, b)) + sign(compareWorkTitles(b, a))).toBe(0);
      }
    }
  });

  it('is transitive: Testimonia precedes every title that collates with Fragments', () => {
    const titles = ['Fragments\u0000', 'Academica', 'Fragments', 'Testimonia'];
    const sorted = [...titles].sort(compareWorkTitles);
    expect(sorted).toEqual(['Academica', 'Testimonia', 'Fragments', 'Fragments\u0000']);
    for (let i = 0; i < sorted.length; i++) {
      for (let j = i + 1; j < sorted.length; j++) {
        expect(compareWorkTitles(sorted[i], sorted[j])).toBeLessThan(0);
      }
    }
  });
});
