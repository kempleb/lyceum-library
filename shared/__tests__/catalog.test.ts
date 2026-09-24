import { describe, expect, it } from 'vitest';
import {
  buildCatalog, countVisibleWorks, matchesCatalogFacets,
  type CatalogAuthorInput, type CatalogSectionInput,
} from '../lib/contents';

// The catalog model behind the Lyceum Catalog page and the homepage's ledger
// previews (docs/design-spec.md §5.3.3, §6): the per-collection counts, the
// period grouping, the filter-bar options, and what a chosen facet means.

const work = (over: Partial<CatalogAuthorInput['works'][number]> = {}) => ({
  id: 'w', title: 'Fragments', href: '/a/fragments', extent: 'B1–B139',
  language: 'Greek', form: 'Fragments & testimonia', ...over,
});

const author = (over: Partial<CatalogAuthorInput> = {}): CatalogAuthorInput => ({
  id: 'heraclitus', name: 'Heraclitus', period: 'presocratic',
  periodLabel: 'Presocratics', range: 'DK 22',
  works: [work({ id: 'heraclitus-fragments' })],
  ...over,
});

const philosophers = (...authors: CatalogAuthorInput[]): CatalogSectionInput => ({
  id: 'philosophers', name: 'The Philosophers', authors,
});

describe('buildCatalog', () => {
  it('counts the authors and works of each collection, and of the library', () => {
    const model = buildCatalog([
      philosophers(
        author({ works: [work({ id: 'heraclitus-fragments' }), work({ id: 'heraclitus-testimonia', title: 'Testimonia' })] }),
        author({ id: 'cicero', name: 'Cicero', period: 'roman', periodLabel: 'Roman', range: 'Latin · 2 works',
          works: [work({ id: 'de-officiis', language: 'Latin', form: 'Prose' }), work({ id: 'de-fato', language: 'Latin', form: 'Prose' })] }),
      ),
      { id: 'aristotle', name: 'Aristotle', authors: [author({ id: 'aristotle', name: 'Aristotle', period: 'classical', periodLabel: 'Classical', range: 'Bekker', works: [work({ id: 'EN', form: 'Prose' })] })] },
    ]);

    expect(model.sections.map((s) => [s.id, s.authorCount, s.workCount]))
      .toEqual([['philosophers', 2, 4], ['aristotle', 1, 1]]);
    expect(model.authorCount).toBe(3);
    expect(model.workCount).toBe(5);
    expect(model.meta).toBe('3 authors · 5 works');
  });

  it('names the languages a collection holds in its count line', () => {
    const model = buildCatalog([
      philosophers(
        author(),
        author({ id: 'cicero', name: 'Cicero', period: 'roman', periodLabel: 'Roman', range: 'Latin · 1 work',
          works: [work({ id: 'de-fato', language: 'Latin', form: 'Prose' })] }),
      ),
    ]);
    expect(model.sections[0].meta).toBe('GREEK & LATIN · 2 AUTHORS · 2 WORKS');
  });

  it('groups by period only where a collection spans more than one', () => {
    const many = buildCatalog([
      philosophers(
        author(),
        author({ id: 'gorgias', name: 'Gorgias', period: 'sophists', periodLabel: 'Sophists' }),
      ),
    ]);
    expect(many.sections[0].groups.map((g) => g.label)).toEqual(['Presocratics', 'Sophists']);

    const one = buildCatalog([philosophers(author(), author({ id: 'thales', name: 'Thales' }))]);
    expect(one.sections[0].groups).toHaveLength(1);
    expect(one.sections[0].groups[0].label).toBeNull();
    expect(one.sections[0].groups[0].authors).toHaveLength(2);
  });

  it('offers every facet axis its own options, authors alphabetically', () => {
    const model = buildCatalog([
      philosophers(
        author({ id: 'zeno', name: 'Zeno of Elea' }),
        author({ id: 'anaxagoras', name: 'Anaxagoras' }),
        author({ id: 'lucretius', name: 'Lucretius', period: 'roman', periodLabel: 'Roman',
          works: [work({ id: 'de-rerum-natura', language: 'Latin', form: 'Verse' })] }),
      ),
    ]);
    expect(model.options.author.map((o) => o.label)).toEqual(['Anaxagoras', 'Lucretius', 'Zeno of Elea']);
    expect(model.options.collection).toEqual([{ value: 'philosophers', label: 'The Philosophers' }]);
    expect(model.options.period.map((o) => o.value)).toEqual(['presocratic', 'roman']);
    expect(model.options.language.map((o) => o.value)).toEqual(['Greek', 'Latin']);
    expect(model.options.form.map((o) => o.value)).toEqual(['Fragments & testimonia', 'Verse']);
  });

  it('tags every work with the facets its row is filtered on', () => {
    const model = buildCatalog([philosophers(author())]);
    expect(model.sections[0].groups[0].authors[0].works[0].facets).toEqual({
      author: 'heraclitus', collection: 'philosophers', period: 'presocratic',
      language: 'Greek', form: 'Fragments & testimonia',
    });
  });

  it('keeps a collection with no works of its own, with its note', () => {
    const model = buildCatalog([
      { id: 'roman', name: 'Roman Thought', accent: 'roman', note: 'Joining later.', authors: [] },
    ]);
    expect(model.sections[0].workCount).toBe(0);
    expect(model.sections[0].note).toBe('Joining later.');
    expect(model.sections[0].accent).toBe('roman');
    expect(model.sections[0].meta).toBe('');
    expect(model.workCount).toBe(0);
    expect(model.sections[0].empty).toBe(true);
  });

  it('counts a work in two collections once, not twice, in the library-wide totals', () => {
    // The same author and the same work, listed under two collections --
    // a work's total membership must not double the library's own count.
    const model = buildCatalog([
      { id: 'philosophy', name: 'Philosophy', authors: [author()] },
      { id: 'presocratics', name: 'Presocratics', authors: [author()] },
    ]);
    expect(model.authorCount).toBe(1);
    expect(model.workCount).toBe(1);
    expect(model.meta).toBe('1 author · 1 work');
    // Each section's own count still reflects its own membership.
    expect(model.sections.map((s) => [s.id, s.authorCount, s.workCount]))
      .toEqual([['philosophy', 1, 1], ['presocratics', 1, 1]]);
  });

  it('carries a child collection\'s parentId through, null for a root collection', () => {
    const model = buildCatalog([
      { id: 'greek', name: 'Greek', authors: [] },
      { id: 'greek-verse', name: 'Greek Verse', parentId: 'greek', authors: [author()] },
    ]);
    expect(model.sections[0].parentId).toBeNull();
    expect(model.sections[1].parentId).toBe('greek');
  });
});

describe('matchesCatalogFacets', () => {
  const tokens = {
    author: 'heraclitus', collection: 'philosophers', period: 'presocratic',
    language: 'Greek', form: 'Fragments & testimonia',
  };

  it('keeps everything when nothing is chosen', () => {
    expect(matchesCatalogFacets(tokens, {})).toBe(true);
    expect(matchesCatalogFacets(tokens, { author: '', language: '' })).toBe(true);
  });

  it('narrows on one axis', () => {
    expect(matchesCatalogFacets(tokens, { language: 'Greek' })).toBe(true);
    expect(matchesCatalogFacets(tokens, { language: 'Latin' })).toBe(false);
    expect(matchesCatalogFacets(tokens, { period: 'roman' })).toBe(false);
  });

  it('ANDs the axes together', () => {
    expect(matchesCatalogFacets(tokens, { collection: 'philosophers', form: 'Fragments & testimonia' })).toBe(true);
    expect(matchesCatalogFacets(tokens, { collection: 'philosophers', form: 'Verse' })).toBe(false);
  });

  it('filters a whole model down to the rows a reader would still see', () => {
    const model = buildCatalog([
      philosophers(
        author(),
        author({ id: 'lucretius', name: 'Lucretius', period: 'roman', periodLabel: 'Roman',
          works: [work({ id: 'de-rerum-natura', language: 'Latin', form: 'Verse' })] }),
      ),
    ]);
    const rows = model.sections
      .flatMap((s) => s.groups.flatMap((g) => g.authors.flatMap((a) => a.works)))
      .filter((w) => matchesCatalogFacets(w.facets, { language: 'Latin' }));
    expect(rows.map((w) => w.id)).toEqual(['de-rerum-natura']);
  });
});

describe('countVisibleWorks', () => {
  it('counts distinct visible work ids, not rows', () => {
    // A work can carry a row in both a parent and a child collection; the
    // shown count must still be the work count, never the row count.
    const rows = [
      { workId: 'republic', visible: true },
      { workId: 'republic', visible: true },
      { workId: 'timaeus', visible: true },
    ];
    expect(countVisibleWorks(rows)).toBe(2);
  });

  it('ignores hidden rows', () => {
    const rows = [
      { workId: 'republic', visible: true },
      { workId: 'timaeus', visible: false },
    ];
    expect(countVisibleWorks(rows)).toBe(1);
  });

  it('is zero for no rows', () => {
    expect(countVisibleWorks([])).toBe(0);
  });
});
