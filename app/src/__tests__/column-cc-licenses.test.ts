// columnCcLicenses (app/src/lib/column-cc-licenses.ts) — John's ruling
// (2026-09-23): the /attribution English Translations list must show CC
// licence info beside a work whose CC-licensed text is a column_sources
// override (Gorgias's Fragments B11/B11a, manifests/gorgias-fragments.yaml)
// rather than a registry `translations[]` entry.
//
// build/dist (and its app/public/data symlink target) is gitignored and
// absent in a fresh checkout / CI, so this seeds a fake public/data/<id>/
// manifest.json in a temp dir and chdirs into it, same pattern as
// built-works.test.ts. The seeded licence is read from the REAL manifest's
// own declared `english.column_sources[].credit.licence`, not hand-typed —
// so this test fails if that licence is ever changed, renamed, or dropped.
import { afterEach, describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { load } from 'js-yaml';

const realCwd = process.cwd();

afterEach(() => {
  process.chdir(realCwd);
});

function gorgiasColumnLicence(column: string) {
  const manifestPath = path.join(realCwd, '..', 'manifests', 'gorgias-fragments.yaml');
  const doc = load(readFileSync(manifestPath, 'utf8')) as {
    english: { column_sources: { column: string; credit: { licence: { status: string; name: string; url: string } } }[] };
  };
  const entry = doc.english.column_sources.find((c) => c.column === column);
  if (!entry) throw new Error(`no column_sources entry for ${column} in ${manifestPath}`);
  return entry.credit.licence;
}

function seedManifest(workId: string, translations: unknown[]) {
  const dir = mkdtempSync(path.join(tmpdir(), 'column-cc-'));
  mkdirSync(path.join(dir, 'public', 'data', workId), { recursive: true });
  writeFileSync(
    path.join(dir, 'public', 'data', workId, 'manifest.json'),
    JSON.stringify({ translations }),
  );
  process.chdir(dir);
}

describe('columnCcLicenses', () => {
  it('groups Gorgias B11 and B11a into one CC note, licence read from the real manifest', async () => {
    const b11 = gorgiasColumnLicence('B11');
    const b11a = gorgiasColumnLicence('B11a');
    expect(b11.status).toBe('cc');
    expect(b11a.status).toBe('cc');

    // Mirrors stage7_emit.py's _manifest_v1_fields shape for a
    // column_sources entry: slot "column", one license object per entry,
    // folded from credit.licence.
    seedManifest('gorgias-fragments', [
      { id: 'freeman', slot: 'primary', license: { status: 'public-domain-us' } },
      {
        id: 'gatt-helen', slot: 'column', columns: ['B11'],
        license: { status: b11.status, name: b11.name, url: b11.url },
      },
      {
        id: 'gazis-palamedes', slot: 'column', columns: ['B11a'],
        license: { status: b11a.status, name: b11a.name, url: b11a.url },
      },
    ]);

    const { columnCcLicenses } = await import('../lib/column-cc-licenses');
    expect(columnCcLicenses('gorgias-fragments')).toEqual([
      { columns: ['B11', 'B11a'], name: b11.name, url: b11.url },
    ]);
    // Pinned against today's known value so a silent shape change (e.g. the
    // manifest losing its url) is loud here, not just in the grouping logic.
    expect(columnCcLicenses('gorgias-fragments')).toEqual([
      {
        columns: ['B11', 'B11a'],
        name: 'CC BY-NC-ND 4.0',
        url: 'https://creativecommons.org/licenses/by-nc-nd/4.0/',
      },
    ]);
  });

  it('ignores non-cc and non-column translations', async () => {
    seedManifest('x', [
      { id: 'a', slot: 'primary', license: { status: 'public-domain-us' } },
      { id: 'b', slot: 'column', columns: ['B1'], license: { status: 'unverified' } },
      { id: 'c', slot: 'overlay', columns: ['B2'], license: { status: 'cc', name: 'CC BY 4.0' } },
    ]);
    const { columnCcLicenses } = await import('../lib/column-cc-licenses');
    expect(columnCcLicenses('x')).toEqual([]);
  });

  it('returns [] when the work has no built manifest', async () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'column-cc-empty-'));
    process.chdir(dir);
    const { columnCcLicenses } = await import('../lib/column-cc-licenses');
    expect(columnCcLicenses('nope')).toEqual([]);
  });
});
