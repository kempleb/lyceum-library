import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// John's ruling, 2026-09-23: the site must not load fonts from Google.
// Cardo, EB Garamond, Public Sans, Bodoni Moda and DM Mono are now
// self-hosted (shared/styles/fonts.css + shared/styles/fonts/*.woff2) --
// nothing under app/src, shared/ (source, not tests) or app/public should
// still point at Google's font-serving hosts. A regression here would be
// exactly the no-foreign-requests failure the 2026-09-23 acceptance
// rehearsal hit (docs/acceptance-script.md's "Rehearsal, 2026-09-23").

// app/src/__tests__/no-google-fonts.test.ts -> repo root is three levels up.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../../');

const FORBIDDEN = [/fonts\.googleapis\.com/, /fonts\.gstatic\.com/];

// Directories to scan, each relative to the repo root. shared/__tests__ and
// app/src/__tests__ are excluded -- tests may legitimately reference the
// hostnames (e.g. sw.test.ts exercising the service worker's cache-first
// path against an arbitrary cross-origin asset). app/scripts is included --
// Sol review, 2026-09-23: build-design-snapshot.mjs there emits a standalone
// HTML preview and had its own Google Fonts <link>, which this scan would
// have caught had it covered dev-tooling scripts, not just the site itself.
const SCAN_ROOTS = ['app/src', 'shared', 'app/public', 'app/scripts'];
const EXCLUDE_DIRS = new Set(['node_modules', '__tests__', 'dist', 'data']);

// Only text source files can plausibly contain a literal URL; skip binaries
// (woff2 font files in particular) and anything not source-shaped.
const TEXT_EXTENSIONS = new Set([
  '.ts', '.tsx', '.js', '.mjs', '.cjs', '.astro', '.svelte',
  '.css', '.json', '.html', '.md', '.txt',
]);

function walk(dir: string, files: string[]): void {
  for (const entry of readdirSync(dir)) {
    if (EXCLUDE_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      walk(full, files);
    } else {
      files.push(full);
    }
  }
}

describe('no Google Fonts references in source', () => {
  it('never points app/src, shared/, or app/public at fonts.googleapis.com or fonts.gstatic.com', () => {
    const files: string[] = [];
    for (const root of SCAN_ROOTS) {
      walk(join(repoRoot, root), files);
    }

    const offenders: string[] = [];
    for (const file of files) {
      const dot = file.lastIndexOf('.');
      const ext = dot === -1 ? '' : file.slice(dot);
      if (!TEXT_EXTENSIONS.has(ext)) continue;

      const content = readFileSync(file, 'utf8');
      if (FORBIDDEN.some((re) => re.test(content))) {
        offenders.push(relative(repoRoot, file));
      }
    }

    expect(offenders).toEqual([]);
  });
});
