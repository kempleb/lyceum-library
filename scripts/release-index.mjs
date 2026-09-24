#!/usr/bin/env node
// Lyceum reproducibility gate (docs/lyceum-shared-repo-plan.md §4/§6; Brian's
// brief, docs/lyceum-build/handoff-2026-09-12/START-HERE.md, "Hosting and
// reproducibility"): a *release* is build/dist plus this file, RELEASE.json,
// naming every file it should contain with its size and sha256, plus the
// commit and corpus version that produced it. `verify-release.mjs` (and
// `build-public.mjs --from-dist`) check a copied-down release against this
// index before trusting it. See docs/release-from-dist.md.
//
// Run: node scripts/release-index.mjs [DIST_DIR]  (default build/dist)
import { createHash } from 'node:crypto';
import { closeSync, existsSync, openSync, readFileSync, readSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

// Fixed for now -- see the task brief. manifest_schema_version/
// catalog_schema_version describe the shapes of manifest.json and the
// partner catalog view, not RELEASE.json's own shape (schema_version).
const SCHEMA_VERSION = '1.0';
const MANIFEST_SCHEMA_VERSION = '1.0';
const CATALOG_SCHEMA_VERSION = '2.0';

// Derived files are rebuilt from release data plus this checkout and build-time
// environment. build-citation-index.mjs writes citation-index.json;
// emit-lyceum-manifest.mjs writes manifests/** and */manifest.lyceum.json;
// app/scripts/build-lemmata.mjs writes lemmata.json, lemmata-lat.json, and
// lemmata/** plus lemmata-lat/**.
function isDerivedPath(rel) {
  return (
    rel === 'RELEASE.json' ||
    rel === 'reports' ||
    rel.startsWith('reports/') ||
    rel === 'citation-index.json' ||
    rel === 'manifests' ||
    rel.startsWith('manifests/') ||
    /^[^/]+\/manifest\.lyceum\.json$/.test(rel) ||
    rel === 'lemmata.json' ||
    rel === 'lemmata-lat.json' ||
    rel === 'lemmata' ||
    rel.startsWith('lemmata/') ||
    rel === 'lemmata-lat' ||
    rel.startsWith('lemmata-lat/')
  );
}

function sha256File(path) {
  const hash = createHash('sha256');
  const fd = openSync(path, 'r');
  const buffer = Buffer.allocUnsafe(1024 * 1024);
  try {
    let bytesRead;
    do {
      bytesRead = readSync(fd, buffer, 0, buffer.length, null);
      if (bytesRead) hash.update(buffer.subarray(0, bytesRead));
    } while (bytesRead);
  } finally {
    closeSync(fd);
  }
  return hash.digest('hex');
}

// Every regular, non-derived file under distDir, relative-pathed with forward
// slashes. Releases must not contain symlinks or other special entries.
function listReleaseFiles(distDir) {
  const files = [];
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const abs = join(dir, entry.name);
      const rel = relative(distDir, abs).split(sep).join('/');
      if (entry.isSymbolicLink()) {
        throw new Error(`release must not contain symlinks: ${rel}`);
      }
      if (entry.isDirectory()) {
        walk(abs);
        continue;
      }
      if (!entry.isFile()) {
        throw new Error(`release must not contain non-file entries: ${rel}`);
      }
      if (!isDerivedPath(rel)) files.push(rel);
    }
  }
  walk(distDir);
  files.sort((a, b) => a.localeCompare(b));
  return files;
}

// A "work" is any top-level directory with its own manifest.json (the shape
// every classical and mounted work emits alike -- see manifest-contract
// tests). Two path segments: "<work>/manifest.json".
function countWorks(relFiles) {
  return relFiles.filter((p) => p.split('/').length === 2 && p.endsWith('/manifest.json')).length;
}

// corpus_version lives on every work's manifest.json (stage7_emit.py) and,
// once it exists, on build/dist/manifests/index.json (docs/lyceum-shared-
// repo-plan.md §6 step 1) -- prefer the index when present, otherwise fall
// back to the first (sorted) work's manifest.json. Used when release-
// index.mjs indexes a fresh full build, where emit-lyceum-manifest has
// already written manifests/index.json by the time this runs. --from-dist
// mode does NOT call this -- see fromDistCorpusVersion() below, and the
// comment on it, for why.
function readCorpusVersion(distDir) {
  const indexPath = join(distDir, 'manifests', 'index.json');
  if (existsSync(indexPath)) {
    const idx = JSON.parse(readFileSync(indexPath, 'utf8'));
    if (idx.corpus_version) return idx.corpus_version;
  }
  const topLevel = readdirSync(distDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort((a, b) => a.localeCompare(b));
  for (const name of topLevel) {
    const manifestPath = join(distDir, name, 'manifest.json');
    if (existsSync(manifestPath)) {
      const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
      if (manifest.corpus_version) return manifest.corpus_version;
    }
  }
  throw new Error(
    `release-index: no corpus_version found under ${distDir} (checked manifests/index.json and */manifest.json)`,
  );
}

// build-public.mjs's --from-dist mode: the corpus_version to use for the
// build in progress is the SOURCE release's own RELEASE.json corpus_version
// -- the release's public stamp (`YYYY.MM.DD-<short commit>`) -- read
// directly, never via readCorpusVersion()'s manifests/index.json-or-work-
// manifest fallback. --from-dist now always calls fromDistCorpusVersion(),
// regardless of whether its source directory is or isn't already
// build/dist; readCorpusVersion()'s only remaining caller is release-
// index.mjs indexing a fresh full build below, where emit-lyceum-manifest
// has already written manifests/index.json by the time release-index runs.
// Before this fix, a release that was only ever copied or downloaded, never
// built-from in this checkout, had no manifests/index.json yet at this point
// in --from-dist's stage list (emit-lyceum-manifest runs much later) and
// readCorpusVersion() fell back to a work's RAW pipeline stamp instead --
// the exact drift the "one stamp" fix (2026-09-22, 40b9bbc) closed for full
// mode but not this one. Found by the no-source-access rehearsal, 2026-09-23
// (docs/release-from-dist.md).
function fromDistCorpusVersion(distDir) {
  const releasePath = join(distDir, 'RELEASE.json');
  if (!existsSync(releasePath)) {
    throw new Error(`fromDistCorpusVersion: RELEASE.json not found in ${distDir}`);
  }
  let release;
  try {
    release = JSON.parse(readFileSync(releasePath, 'utf8'));
  } catch (err) {
    throw new Error(`fromDistCorpusVersion: RELEASE.json in ${distDir} is not valid JSON: ${err.message}`);
  }
  if (!release.corpus_version) {
    throw new Error(`fromDistCorpusVersion: RELEASE.json in ${distDir} has no corpus_version`);
  }
  return release.corpus_version;
}

function producerCommit() {
  const result = spawnSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: ROOT, encoding: 'utf8' });
  if (result.error) throw result.error;
  if (result.status !== 0 || !result.stdout.trim()) {
    throw new Error('release-index: git rev-parse --short HEAD failed');
  }
  return result.stdout.trim();
}

function buildReleaseIndex(distDir) {
  const relFiles = listReleaseFiles(distDir);
  const files = relFiles.map((rel) => {
    const abs = join(distDir, rel);
    const stat = statSync(abs);
    return { path: rel, size: stat.size, sha256: sha256File(abs) };
  });
  return {
    schema_version: SCHEMA_VERSION,
    corpus_version: readCorpusVersion(distDir),
    producer_commit: producerCommit(),
    generated_at: new Date().toISOString(),
    manifest_schema_version: MANIFEST_SCHEMA_VERSION,
    catalog_schema_version: CATALOG_SCHEMA_VERSION,
    works: countWorks(relFiles),
    files,
  };
}

function writeReleaseIndex(distDir) {
  const index = buildReleaseIndex(distDir);
  writeFileSync(join(distDir, 'RELEASE.json'), `${JSON.stringify(index, null, 2)}\n`, 'utf8');
  return index;
}

async function main() {
  const distDir = resolve(process.argv[2] || join(ROOT, 'build', 'dist'));
  console.log(`release-index: indexing ${distDir}`);
  const index = writeReleaseIndex(distDir);
  console.log(
    `  wrote RELEASE.json: ${index.files.length} file(s), ${index.works} work(s), ` +
      `corpus_version=${index.corpus_version}, producer_commit=${index.producer_commit}`,
  );
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}

export {
  buildReleaseIndex,
  writeReleaseIndex,
  readCorpusVersion,
  fromDistCorpusVersion,
  listReleaseFiles,
  isDerivedPath,
  sha256File,
};
