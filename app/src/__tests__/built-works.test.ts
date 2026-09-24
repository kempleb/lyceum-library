// builtAuthors()/builtWorksOf() — the breadcrumb's option lists must be gated
// on data actually built into this checkout (public/data/<id>/manifest.json),
// keep the author's own curated work order, and count fixture registrations
// only when PUBLIC_READER_FIXTURES=1. built-works.ts checks cwd-relative
// paths with the real fs, so each test chdirs into a temp dir seeded with
// exactly the manifests it wants "built"; modules are re-imported per test
// because built-works.ts memoizes its fs checks (and authors.ts/works.ts read
// the fixture env flag at module load).
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const realCwd = process.cwd();

// Seed a fresh fake app root whose public/data carries manifests for exactly
// `workIds`, and make it the cwd built-works.ts resolves against.
function builtOnly(...workIds: string[]) {
  const dir = mkdtempSync(path.join(tmpdir(), 'built-works-'));
  for (const id of workIds) {
    mkdirSync(path.join(dir, 'public', 'data', id), { recursive: true });
    writeFileSync(path.join(dir, 'public', 'data', id, 'manifest.json'), '{}');
  }
  process.chdir(dir);
}

async function load() {
  vi.resetModules();
  return await import('../lib/built-works');
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => {}); // silence warnOnce
});

afterEach(() => {
  process.chdir(realCwd);
  vi.unstubAllEnvs();
});

describe('builtAuthors', () => {
  it('is empty when no work data is on disk', async () => {
    builtOnly();
    const { builtAuthors } = await load();
    expect(builtAuthors()).toEqual([]);
  });

  it('includes only authors with at least one built work', async () => {
    builtOnly('meditations');
    const { builtAuthors } = await load();
    expect(builtAuthors().map((a) => a.id)).toEqual(['marcus-aurelius']);
  });

  it('counts fixture works only when PUBLIC_READER_FIXTURES=1', async () => {
    vi.stubEnv('PUBLIC_READER_FIXTURES', '1');
    builtOnly('sample-work');
    const withFlag = await load();
    expect(withFlag.builtAuthors().map((a) => a.id)).toEqual(['sample-author']);

    vi.unstubAllEnvs();
    builtOnly('sample-work');
    const withoutFlag = await load();
    expect(withoutFlag.builtAuthors()).toEqual([]);
  });
});

describe('builtWorksOf', () => {
  it('returns only the built works of the given author', async () => {
    builtOnly('meditations');
    const { builtWorksOf } = await load();
    expect(builtWorksOf('marcus-aurelius').map((w) => w.id)).toEqual(['meditations']);
  });

  it('is empty for an unbuilt or unknown author', async () => {
    builtOnly();
    const { builtWorksOf } = await load();
    expect(builtWorksOf('marcus-aurelius')).toEqual([]);
    expect(builtWorksOf('no-such-author')).toEqual([]);
  });

  it('keeps each author.works curated order when everything is built', async () => {
    vi.stubEnv('PUBLIC_READER_FIXTURES', '1');
    builtOnly('meditations', 'sample-work');
    const { builtAuthors, builtWorksOf } = await load();
    const authors = builtAuthors();
    expect(authors.map((a) => a.id)).toEqual(['marcus-aurelius', 'sample-author']);
    for (const a of authors) {
      const ids = builtWorksOf(a.id).map((w) => w.id);
      // Curated order: the returned ids are exactly author.works filtered to
      // the built set, order preserved.
      expect(ids).toEqual(a.works.filter((id) => ids.includes(id)));
      expect(ids.length).toBeGreaterThan(0);
    }
  });
});
