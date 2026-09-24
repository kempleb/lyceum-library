// Resolves and loads the real js-yaml module across whichever of the repo's
// three node_modules roots happens to carry it (app/, shared/, or the repo
// root) -- generalizes the path hack check-manifest-translations.mjs used to
// hardcode against app/node_modules alone (see its own loadYamlModule, now
// refactored onto this helper). js-yaml ships an ESM build at
// dist/js-yaml.mjs; importing it directly (rather than 'js-yaml' by package
// name) needs no resolution algorithm beyond a plain file path, which is why
// this works from a plain `node script.mjs` invocation with no bundler.
//
// Lyceum P2 (docs/p2-plan.md §2): js-yaml is a devDependency of BOTH
// app/package.json and shared/package.json (shared CI installs only
// shared/node_modules), so a script run from either checkout still finds it.

import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

// scripts/lib/load-yaml.mjs -> scripts/ -> repo root.
export const REPO_ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

const CANDIDATES = [
  join(REPO_ROOT, 'app', 'node_modules', 'js-yaml', 'dist', 'js-yaml.mjs'),
  join(REPO_ROOT, 'shared', 'node_modules', 'js-yaml', 'dist', 'js-yaml.mjs'),
  join(REPO_ROOT, 'node_modules', 'js-yaml', 'dist', 'js-yaml.mjs'),
];

let cached;

/** @returns {Promise<typeof import('js-yaml')>} */
export async function loadYaml() {
  if (cached) return cached;
  const path = CANDIDATES.find((p) => existsSync(p));
  if (!path) {
    throw new Error(
      `js-yaml not found in any of:\n  ${CANDIDATES.join('\n  ')}\n` +
        `Run \`npm install\` in app/ or shared/ (js-yaml is a devDependency of both).`,
    );
  }
  const mod = await import(pathToFileURL(path).href);
  cached = mod.default ?? mod;
  return cached;
}
