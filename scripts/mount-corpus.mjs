#!/usr/bin/env node
// Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 1-4, 8; Stage
// sequence 2). Mounts one external corpus's built work directories into
// this repo's build/dist, flat-merged alongside the classical works
// (Settled decision 2), running the three corpus-adapter transforms
// (manifest, search, private) on each and merging the corpus's own LSJ
// shards into the shared dictionary.
//
// Usage: node scripts/mount-corpus.mjs <corpus>
//   e.g. node scripts/mount-corpus.mjs aristotle
//
// Reads corpora/<corpus>/{mount.yaml,registry.yaml}. Resolves the source
// directory as process.env[mount.source_env] ?? mount.source_default
// (relative to this repo's root). If the source directory does not exist,
// this is a clean no-op (exit 0) -- CI and any machine without the sibling
// repo checked out never fails here (docs/p3-plan.md's Mode A byte-
// stability requirement: the mount no-ops absolutely).
//
// SAFETY: before any write, this asserts realpath(build/dist) is inside
// this repo's own tree (never through a symlink pointing outside it -- the
// sibling repo is read-only and must never be written into), and that each
// destination work directory it is about to replace is a real directory,
// never a symlink.

import {
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  realpathSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { loadYaml } from './lib/load-yaml.mjs';
import { adaptManifest, APPARATUS_FILES } from './lib/corpus-adapter/manifest.mjs';
import { adaptSearchFiles } from './lib/corpus-adapter/search.mjs';
import { assertNoPrivate } from './lib/corpus-adapter/private.mjs';
import { mergeShards } from './lib/corpus-adapter/lsj-merge.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

// A corpus's mount.yaml may declare `hold: true` (docs/todo/plato-mount.md --
// John's ruling, 2026-09-23: Plato stays out of any release sent to the test
// copy until he lifts the hold). A held corpus is skipped by default -- a
// clean no-op, exactly like a missing source directory -- unless
// READER_INCLUDE_HELD=1 is set in the environment. Exported as a pure
// function (mountConfig, env) -> boolean so the gate itself is unit-testable
// without touching the filesystem.
export function shouldSkipForHold(mountConfig, env) {
  return Boolean(mountConfig.hold) && env.READER_INCLUDE_HELD !== '1';
}

async function main() {
  const corpus = process.argv[2];
  if (!corpus) {
    console.error('usage: node scripts/mount-corpus.mjs <corpus>');
    process.exit(1);
  }

  const corpusDir = join(ROOT, 'corpora', corpus);
  const mountConfigPath = join(corpusDir, 'mount.yaml');
  const registryPath = join(corpusDir, 'registry.yaml');
  if (!existsSync(mountConfigPath)) {
    throw new Error(`mount-corpus: no mount.yaml for corpus ${JSON.stringify(corpus)} at ${mountConfigPath}`);
  }

  const yaml = await loadYaml();
  const mountConfig = yaml.load(readFileSync(mountConfigPath, 'utf8'));
  if (mountConfig.corpus !== corpus) {
    throw new Error(
      `mount-corpus: ${mountConfigPath} declares corpus ${JSON.stringify(mountConfig.corpus)}, expected ${JSON.stringify(corpus)}`,
    );
  }

  if (shouldSkipForHold(mountConfig, process.env)) {
    console.log(
      `mount-corpus: ${corpus} is held (mount.yaml hold: true) -- skipping (no-op). ` +
        'Set READER_INCLUDE_HELD=1 to mount it anyway.',
    );
    return;
  }

  const sourceEnvValue = mountConfig.source_env ? process.env[mountConfig.source_env] : undefined;
  const sourceDir = sourceEnvValue
    ? resolveMaybeAbsolute(ROOT, sourceEnvValue)
    : resolveMaybeAbsolute(ROOT, mountConfig.source_default);

  if (!existsSync(sourceDir)) {
    console.log(
      `mount-corpus: source directory for ${corpus} not found (${sourceDir}) -- no-op.`,
    );
    return;
  }
  if (!statSync(sourceDir).isDirectory()) {
    console.log(`mount-corpus: source path for ${corpus} is not a directory (${sourceDir}) -- no-op.`);
    return;
  }

  const registryYaml = yaml.load(readFileSync(registryPath, 'utf8'));
  const registry = registryYaml.registry ?? {};
  const workIds = Object.keys(registry);
  if (workIds.length === 0) {
    throw new Error(`mount-corpus: ${registryPath} declares no works under registry:`);
  }

  const distDir = join(ROOT, 'build', 'dist');
  mkdirSync(distDir, { recursive: true });
  assertDestInsideRepo(distDir);

  const corpusVersion = process.env.CORPUS_VERSION ?? 'dev';

  let mounted = 0;
  let skippedMissing = 0;
  const mountedIds = [];
  const fileCounts = {};

  for (const id of workIds) {
    const registryWork = registry[id];
    const srcWorkDir = join(sourceDir, id);
    if (!existsSync(srcWorkDir)) {
      console.warn(`  skip ${id}: no source directory at ${srcWorkDir}`);
      skippedMissing += 1;
      continue;
    }

    const destWorkDir = join(distDir, id);
    assertNotSymlink(destWorkDir);
    rmSync(destWorkDir, { recursive: true, force: true });
    mkdirSync(destWorkDir, { recursive: true });
    assertDestInsideRepo(destWorkDir);

    const searchExclude = new Set(mountConfig.search_exclude ?? []);
    const count = copyWorkDir(srcWorkDir, destWorkDir, searchExclude);
    fileCounts[id] = count;

    const legacyManifest = JSON.parse(readFileSync(join(destWorkDir, 'manifest.json'), 'utf8'));
    const apparatus = {};
    for (const name of APPARATUS_FILES) {
      apparatus[name] = existsSync(join(destWorkDir, `${name}.json`));
    }
    const adapted = adaptManifest(legacyManifest, registryWork, { corpusVersion, apparatus });
    writeFileSync(join(destWorkDir, 'manifest.json'), JSON.stringify(adapted, null, 1), 'utf8');

    const bookData = readdirSync(destWorkDir)
      .filter((f) => /^book-\d+\.json$/.test(f))
      .sort()
      .map((f) => JSON.parse(readFileSync(join(destWorkDir, f), 'utf8')));
    if (bookData.length === 0) {
      throw new Error(`mount-corpus: ${id}: no book-NN.json files found under ${destWorkDir}`);
    }

    assertNoPrivate(bookData, registryWork);

    const analysesPath = join(destWorkDir, 'analyses.json');
    const analyses = existsSync(analysesPath)
      ? JSON.parse(readFileSync(analysesPath, 'utf8'))
      : {};
    const searchDir = join(destWorkDir, 'search');
    if (existsSync(searchDir)) {
      await adaptSearchFiles(searchDir, bookData, analyses, registryWork.language);
    }

    mounted += 1;
    mountedIds.push(id);
  }

  const lsjResult = mergeShards(join(distDir, 'lsj'), join(sourceDir, 'lsj'));

  const mountsDir = join(distDir, '.mounts');
  mkdirSync(mountsDir, { recursive: true });
  const sourceMtime = statSync(sourceDir).mtime.toISOString();
  writeFileSync(
    join(mountsDir, `${corpus}.json`),
    JSON.stringify(
      {
        corpus,
        mountedAt: new Date().toISOString(),
        adapterVersion: 1,
        source: { path: sourceDir, mtime: sourceMtime },
        works: mountedIds,
        fileCounts,
        lsj: lsjResult,
      },
      null,
      1,
    ),
    'utf8',
  );

  console.log(
    `mount-corpus: ${corpus}: ${mounted} work(s) mounted` +
      (skippedMissing ? `, ${skippedMissing} skipped (no source dir)` : '') +
      `.`,
  );
  console.log(`mount-corpus: lsj merge: added ${lsjResult.added}, conflicts ${lsjResult.conflicts}.`);
  console.log(`mount-corpus: 0 private violations (assertNoPrivate passed for every mounted work).`);
}

function resolveMaybeAbsolute(root, value) {
  if (value.startsWith('/')) return value;
  return join(root, value);
}

function assertNotSymlink(path) {
  if (!existsSync(path)) return;
  const st = lstatSync(path);
  if (st.isSymbolicLink()) {
    throw new Error(`mount-corpus: refusing to replace a symlink at ${path}`);
  }
}

function assertDestInsideRepo(path) {
  const repoReal = realpathSync(ROOT);
  const pathReal = realpathSync(path);
  if (pathReal !== repoReal && !pathReal.startsWith(repoReal + sep)) {
    throw new Error(
      `mount-corpus: refusing to write outside this repo: ${pathReal} is not inside ${repoReal}`,
    );
  }
}

// Recursively copies srcDir into destDir, skipping any file inside a
// "search" subdirectory whose basename is in searchExclude. Returns the
// number of files copied.
function copyWorkDir(srcDir, destDir, searchExclude, inSearchDir = false) {
  let count = 0;
  mkdirSync(destDir, { recursive: true });
  for (const entry of readdirSync(srcDir, { withFileTypes: true })) {
    const srcPath = join(srcDir, entry.name);
    if (entry.isSymbolicLink()) {
      throw new Error(`mount-corpus: refusing to copy a symlink from source: ${srcPath}`);
    }
    if (entry.isDirectory()) {
      const nextInSearch = inSearchDir || entry.name === 'search';
      count += copyWorkDir(srcPath, join(destDir, entry.name), searchExclude, nextInSearch);
      continue;
    }
    if (inSearchDir && searchExclude.has(entry.name)) continue;
    copyFileSync(srcPath, join(destDir, entry.name));
    count += 1;
  }
  return count;
}

// Guarded so shouldSkipForHold can be imported for a unit test (e.g.
// scripts/__tests__/mount-corpus.test.mjs) without running main() as an
// import-time side effect.
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exit(1);
  });
}
