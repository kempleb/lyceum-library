#!/usr/bin/env node
// Lyceum P3 stage 3 (docs/p3-plan.md, Settled decision 5; Stage sequence 3).
// Scans build/dist/<work>/{manifest.json,columns.json} for every BUILT work
// whose citation scheme is bekker or busse -- the only two schemes sharing
// the "digits + a-e column letter" grammar shared/lib/citation-router.ts's
// bare-column dispatch stage parses -- and emits build/dist/citation-
// index.json: column -> [{work, book, lo, hi}], the shape shared/lib/
// data.ts's fetchCitationIndex fetches at runtime (never bundled).
// aristotle-reader's build/dist/bekker.json is the shape precedent this
// generalizes to more than one mounted corpus and to busse alongside
// bekker.
//
// Usage: node scripts/build-citation-index.mjs
// Wired into build-public.mjs right after the multi-corpus mount step
// (before preflight/astro build), so a mounted work's manifest.json is
// already in its final adapted (v1) shape when this reads it.

import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DEFAULT_DIST = join(ROOT, 'build', 'dist');

// 'stephanus' added for the Plato mount (docs/todo/plato-mount.md, P4
// precondition recorded in docs/p3-plan.md's Settled decision 5): the
// bare-column grammar (digits + a single a-e side letter) matches a
// Stephanus page+column exactly like a Bekker/Busse one, so a Stephanus
// citation (e.g. "327a") must be resolvable through this same index --
// otherwise it would resolve as a confident, WRONG Bekker/Busse hit instead
// of, correctly, a genuine no-match or a reported ambiguity. resolveFromIndex
// (shared/lib/citation-router.ts) already scopes its line-containment
// narrowing to a single scheme and reports a cross-scheme collision as
// ambiguous, so adding a third scheme here needs no change there.
const INDEXED_SCHEMES = new Set(['bekker', 'busse', 'stephanus']);

// Builds the cross-corpus citation index by scanning `distDir` (defaults to
// build/dist). Returns { index, works } -- `works` is the ids of the works
// actually indexed, in scan order -- so a caller can report a summary
// without re-scanning the disk. A missing/empty dist dir returns an empty
// index rather than throwing (mirrors every other build-public.mjs step's
// "no corpus data present" tolerance for the zero-works CI build).
export function buildCitationIndex(distDir = DEFAULT_DIST) {
  const index = {};
  const works = [];
  if (!existsSync(distDir)) return { index, works };

  for (const name of readdirSync(distDir).sort()) {
    const workDir = join(distDir, name);
    if (!statSync(workDir).isDirectory()) continue;

    const manifestPath = join(workDir, 'manifest.json');
    if (!existsSync(manifestPath)) continue; // lsj/, ls/, reports/, etc. -- not a work dir
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
    if (!INDEXED_SCHEMES.has(manifest.citation?.scheme)) continue;

    const columnsPath = join(workDir, 'columns.json');
    if (!existsSync(columnsPath)) continue;
    const columns = JSON.parse(readFileSync(columnsPath, 'utf8'));

    const workId = manifest.id ?? name;
    works.push(workId);
    for (const [column, entries] of Object.entries(columns)) {
      const list = index[column] ?? (index[column] = []);
      for (const entry of entries) {
        list.push({ work: workId, book: entry.book, lo: entry.lo, hi: entry.hi });
      }
    }
  }

  return { index, works };
}

function main() {
  const { index, works } = buildCitationIndex();
  const outPath = join(DEFAULT_DIST, 'citation-index.json');
  writeFileSync(outPath, JSON.stringify(index));
  const columnCount = Object.keys(index).length;
  console.log(
    `citation-index: ${works.length} work(s) indexed (${works.join(', ') || 'none'}), ` +
    `${columnCount} column(s) -> ${outPath}`,
  );
}

// Guarded so buildCitationIndex can be imported for a unit test (e.g.
// scripts/__tests__/build-citation-index.test.mjs) without running main() --
// and its build/dist write -- as an import-time side effect.
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  main();
}
