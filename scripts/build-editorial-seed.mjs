#!/usr/bin/env node
// Regenerates the `works` half of fixtures/editorial.seed.json (Lyceum P4,
// docs/lyceum-shared-repo-plan.md §11.6) -- OUR editorial records in the
// partner's version-2 catalog shape, seeded under (never overriding) the
// partner's own published catalog at build time (see
// shared/lib/lyceum-catalog-source.ts's parseCatalog).
//
// The `collections` half of the seed file is committed, hand-authored data
// and is preserved verbatim; this script only replaces `works`, derived
// from every built work's build/dist/<id>/manifest.lyceum.json (the partner
// manifest scripts/emit-lyceum-manifest.mjs already emits) plus the registry
// (shared/lib/registry.generated.ts, itself built from manifests/*.yaml and
// corpora/aristotle/*.yaml by scripts/build-registry.mjs -- run that first).
//
// Run: node scripts/build-editorial-seed.mjs

import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DIST = join(ROOT, 'build', 'dist');
const SEED_PATH = join(ROOT, 'fixtures', 'editorial.seed.json');
const GENERATED_REGISTRY = join(ROOT, 'shared', 'lib', 'registry.generated.ts');

// Collection membership, derived from registry data -- never a hand list
// (design ruling, docs/lyceum-shared-repo-plan.md §11.6). `manifest` is the
// work's own manifest.lyceum.json (its `language` is already partner-mapped:
// 'grc' stays 'grc', Latin is 'la' -- see scripts/emit-lyceum-manifest.mjs's
// mapLanguage), `author` is the matching shared/lib/registry.generated.ts
// CORPUS_AUTHORS entry (undefined for a work the registry doesn't carry).
function collectionIdsFor(manifest, author) {
  const ids = ['philosophy'];
  if (manifest.language === 'grc') ids.push('greek');
  if (author?.period === 'presocratic') ids.push('presocratics');
  if (author?.schools?.includes('stoic')) ids.push('stoics');
  if (author?.schools?.includes('epicurean')) ids.push('epicureans');
  if (author?.id === 'aristotle') ids.push('aristotle');
  return ids;
}

async function main() {
  if (!existsSync(SEED_PATH)) {
    throw new Error(`build-editorial-seed: ${SEED_PATH} is missing -- author its committed collections first.`);
  }
  const current = JSON.parse(readFileSync(SEED_PATH, 'utf8'));
  if (!Array.isArray(current.collections) || current.collections.length === 0) {
    throw new Error(`build-editorial-seed: ${SEED_PATH} has no collections to preserve.`);
  }
  if (!existsSync(GENERATED_REGISTRY)) {
    throw new Error('build-editorial-seed: shared/lib/registry.generated.ts is missing -- run scripts/build-registry.mjs first.');
  }
  if (!existsSync(DIST)) {
    throw new Error(`build-editorial-seed: ${DIST} is missing -- run the pipeline (build:public) first.`);
  }

  const registry = await import(pathToFileURL(GENERATED_REGISTRY).href);
  const authorsById = new Map(registry.CORPUS_AUTHORS.map((a) => [a.id, a]));
  const worksById = new Map(registry.CORPUS_WORKS.map((w) => [w.id, w]));

  const workDirs = readdirSync(DIST, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .filter((name) => existsSync(join(DIST, name, 'manifest.lyceum.json')))
    .sort();

  const works = workDirs.map((dirName) => {
    const manifest = JSON.parse(readFileSync(join(DIST, dirName, 'manifest.lyceum.json'), 'utf8'));
    // The partner manifest carries no `source_manifest`/`generator` fields of
    // its own use to us as editorial `facts` -- both name OUR pipeline
    // internals (manifest.json / this repo's emit script), not a fact about
    // the work itself.
    const { source_manifest: _sourceManifest, generator: _generator, ...facts } = manifest;
    const registryWork = worksById.get(dirName);
    const author = registryWork ? authorsById.get(registryWork.author) : undefined;
    const defaultTranslation = Array.isArray(manifest.translations) && manifest.translations.length > 0
      ? manifest.translations[0].id
      : '';
    return {
      id: manifest.work,
      facts,
      editorial: {
        description: registryWork?.blurb ?? '',
        approved_by: '',
        default_translation: defaultTranslation,
        collection_ids: collectionIdsFor(manifest, author),
        preset: '',
        featured: false,
        state: 'draft',
      },
    };
  });

  const out = { ...current, works };
  writeFileSync(SEED_PATH, `${JSON.stringify(out, null, 2)}\n`);
  console.log(`build-editorial-seed: wrote ${works.length} work(s), kept ${current.collections.length} collection(s).`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
