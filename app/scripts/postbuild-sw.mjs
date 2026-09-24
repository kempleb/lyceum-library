// Substitutes the build's PUBLIC_DATA_ROOT into dist/client/sw.js.
//
// The service worker is a static file copied verbatim out of public/, so it
// cannot read import.meta.env the way shared/lib/data.ts and shared/lib/search.ts
// do. Without this step a build whose data lives off-origin ships a worker that
// ignores every corpus fetch — word lookup, search, footnotes and lemma pages
// all stop working offline, silently (docs/cloudflare-setup.md §3a).
//
// No PUBLIC_DATA_ROOT means same-origin data, which the worker already handles:
// nothing to do. When it IS set, a missed substitution is exactly the silent
// failure this script exists to prevent, so every problem is fatal.
import { readFileSync, existsSync, writeFileSync } from 'node:fs';

const PLACEHOLDER = /^const DATA_ROOT = '';$/m;
const SW = 'dist/client/sw.js';

const root = process.env.PUBLIC_DATA_ROOT;
if (root) {
  try {
    new URL(root, 'https://example.invalid/');
  } catch {
    console.error(`postbuild-sw: PUBLIC_DATA_ROOT is not a usable URL: ${root}`);
    process.exit(1);
  }
  if (!existsSync(SW)) {
    console.error(`postbuild-sw: ${SW} not found`);
    process.exit(1);
  }
  const source = readFileSync(SW, 'utf8');
  if (!PLACEHOLDER.test(source)) {
    console.error(`postbuild-sw: no DATA_ROOT placeholder in ${SW} — public/sw.js has drifted`);
    process.exit(1);
  }
  writeFileSync(SW, source.replace(PLACEHOLDER, `const DATA_ROOT = ${JSON.stringify(root)};`));
}
