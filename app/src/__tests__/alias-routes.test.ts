// Partner-catalog alias routes: /texts/<author>/<work>/ (one per built work,
// see src/pages/texts/[author]/[work]/index.astro) and
// /read/<author>/<work>/section-<n>/ (one per section of every flat
// section-scheme work, see src/pages/read/_section-routes.ts and
// src/pages/read/[author]/[work]/section-[n].astro). Runs against the real
// public/data on disk in this checkout (same cwd-relative convention as
// built-works.test.ts / citation-routes.ts), so these assertions only bind
// what's actually built. Guarded (same no-op-on-empty-checkout pattern as
// lyceum-catalog.test.ts's "lyceumWorkKey matches every emitted partner
// manifest" describe): a fresh clone or CI has no public/data, so
// builtWorks() is empty and these tests have nothing to assert.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { getAuthor } from '@shared/lib/authors';
import { workPath, workSlug } from '@shared/lib/works';
import { builtWorks } from '../lib/built-works';
import { sectionRoutes } from '../pages/read/_section-routes';

// app/src/__tests__ -> app/src -> app -> repo root.
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

describe('texts/[author]/[work] route set', () => {
  it('yields exactly one /texts/ path per built work, matching [author]/[work]/index.astro\'s own getStaticPaths mapping', () => {
    const works = builtWorks();
    if (works.length === 0) return; // nothing built in this checkout
    const paths = works.map((w) => {
      const author = getAuthor(w.author);
      expect(author, `work '${w.id}' must resolve to a known author`).toBeTruthy();
      return { author: author!.id, work: workSlug(w) };
    });
    expect(paths).toHaveLength(works.length);
    const keys = paths.map((p) => `${p.author}/${p.work}`);
    expect(new Set(keys).size).toBe(keys.length); // no two works collide on the same alias URL
  });
});

describe('read/[author]/[work]/section-[n] route set', () => {
  it('yields one section-N page for every section 1..53 of Enchiridion', () => {
    if (builtWorks().length === 0) return; // nothing built in this checkout
    const enchiridion = sectionRoutes().filter((r) => r.author === 'epictetus' && r.work === 'enchiridion');
    const ns = enchiridion.map((r) => Number(r.n)).sort((a, b) => a - b);
    expect(ns).toEqual(Array.from({ length: 53 }, (_, i) => i + 1));
    expect(enchiridion.every((r) => r.bookN === 1)).toBe(true);
  });

  it('emits no /read/ pages for a book-section-scheme work (Meditations)', () => {
    const meditations = sectionRoutes().filter((r) => r.work === 'meditations');
    expect(meditations).toHaveLength(0);
  });

  it('emits, per section-scheme work, exactly the section tokens present as keys in that work\'s columns.json (handles gapped numbering)', () => {
    // Regression guard for the Vatican Sayings-style gap: routes must come
    // from columns.json's real keys, never a contiguous manifest start..end
    // range that would point ?loc= at a non-existent col-<n> anchor. A
    // "nonempty" check would pass even if the route set diverged from
    // columns.json (e.g. included a stale or missing token); set equality is
    // the real assertion.
    const built = builtWorks();
    if (built.length === 0) return; // nothing built in this checkout
    const sectionWorks = built.filter((w) => w.citation?.scheme === 'section');
    expect(sectionWorks.length).toBeGreaterThan(0);
    const routes = sectionRoutes();
    for (const work of sectionWorks) {
      const author = getAuthor(work.author)!;
      const slug = workSlug(work);
      const columns = JSON.parse(readFileSync(`public/data/${work.id}/columns.json`, 'utf8')) as Record<
        string,
        unknown
      >;
      const expectedTokens = new Set(Object.keys(columns));
      const actualTokens = new Set(
        routes.filter((r) => r.author === author.id && r.work === slug).map((r) => r.n),
      );
      expect(actualTokens, `${author.id}/${slug} section token set`).toEqual(expectedTokens);
    }
  });
});

describe('lyceum manifest reading_route for a section-scheme work (Enchiridion)', () => {
  it('regenerates the Lyceum manifest and points reading_route at the real reader page, not the alias', () => {
    if (builtWorks().length === 0) return; // nothing built in this checkout
    const result = spawnSync(
      'node',
      ['scripts/emit-lyceum-manifest.mjs', '--work', 'enchiridion'],
      { cwd: REPO_ROOT, encoding: 'utf8' },
    );
    expect(result.status, result.stderr || result.stdout).toBe(0);

    const lyceum = JSON.parse(
      readFileSync(join(REPO_ROOT, 'build', 'dist', 'enchiridion', 'manifest.lyceum.json'), 'utf8'),
    );
    // Enchiridion is bookless (isBookless: books === 1), so its division id
    // is 'text', not 'book-1' -- shared/lib/works.ts's divisionId.
    expect(lyceum.reading_route).toBe('/read/epictetus/enchiridion/text');
    expect(Object.hasOwn(lyceum, 'reading_route_note')).toBe(false);

    // The section-N alias pages still exist (one per real section, from
    // columns.json) and forward INTO the real reader page via `?loc=N` --
    // see section-[n].astro's `workPath(work.id, bookN)}?loc=${n}` target,
    // which now resolves through /text rather than /book-1.
    const enchiridionRoutes = sectionRoutes().filter(
      (r) => r.author === 'epictetus' && r.work === 'enchiridion',
    );
    const first = enchiridionRoutes.find((r) => r.n === '1');
    expect(first).toBeTruthy();
    expect(workPath('enchiridion', first!.bookN)).toBe('/read/epictetus/enchiridion/text');
  });
});
