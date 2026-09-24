#!/usr/bin/env node
// Hard gate for an R2-backed (off-origin data) Cloudflare Pages artifact
// (Lyceum P6 plan, Settled decision 3 / docs/p6-plan.md, Stage 1).
//
// Only meaningful for a build made with PUBLIC_DATA_ROOT set: it asserts the
// dist directory is the LEAN artifact that build should produce (no local
// data copy, file count safely under Cloudflare Pages' 20,000-file cap, a
// service worker that actually points at the off-origin data root, and at
// least one real reader page — not just an empty shell). The caller passes
// --expect-data-root with the exact value it built with; this script does not
// read env vars itself, so it can be pointed at any prior build's dist and
// still make a meaningful assertion.
//
// A same-origin build (PUBLIC_DATA_ROOT unset) is out of scope: it legitimately
// ships dist/data, so running this script against one is expected to fail the
// "no dist/data" check -- that failure is correct, not a bug in the gate.
import { existsSync, readFileSync, statSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(import.meta.url), '..', '..');
const FILE_COUNT_LIMIT = 18000;

function countFiles(dir) {
  let count = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const child = join(dir, entry.name);
    if (entry.isDirectory()) count += countFiles(child);
    else if (entry.isFile()) count += 1;
  }
  return count;
}

// A reader page is one of the emitted /read/<author>/<work>/<division>/
// pages (app/src/pages/read/[author]/[work]/[division].astro) -- distinct
// from the front-door, authors, search, and lemma routes, which exist even
// in an empty-corpus build. The division segment is book-N for most works,
// but text/letter-N/chapter-N for others (shared/lib/works.ts's divisionId,
// John's ruling 2026-09-12), so this no longer greps for a "book-" prefix --
// any directory under read/ whose index.html is not a forwarder qualifies.
// The old /[author]/[work]/book/[n]/ shape is now only a forwarder
// (app/src/pages/[author]/[work]/book/[n].astro), and the section-N alias
// (app/src/pages/read/[author]/[work]/section-[n].astro) is a forwarder too
// -- both are meta-refresh pages, so the "not a forwarder" check already
// excludes them without needing a path-shape check as well.
function hasReaderPage(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const child = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (hasReaderPage(child)) return true;
    } else if (entry.isFile() && entry.name === 'index.html') {
      const segments = child.split('/');
      const newShape = segments.includes('read');
      if (newShape && !readFileSync(child, 'utf8').includes('http-equiv="refresh"')) return true;
    }
  }
  return false;
}

// Every `.js` file under `dir`, recursively, except the one at `excludePath`
// (sw.js: checked separately, by its own literal form, above) -- used to
// confirm the CLIENT bundle actually carries the data root too, not just
// the service worker. sw.js alone carrying it would ship a build where the
// reader's own code still requests the wrong path once dist/client/data is
// pruned (checked against a real build: the root shows up as a plain
// backtick-string literal in the client's data.js/search.js chunks under
// dist/client/_astro/, so a substring search is enough -- no need to parse
// or unescape anything).
function listJsFiles(dir, excludePath) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const child = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...listJsFiles(child, excludePath));
    } else if (entry.isFile() && entry.name.endsWith('.js') && child !== excludePath) {
      files.push(child);
    }
  }
  return files;
}

// Bucket mode's own data root is always `/data/<corpus_version>`
// (scripts/lib/data-source-mode.mjs's dataRootFor) -- pure, so the "does the
// baked-in root name the same version RELEASE.json does" comparison below is
// unit-testable without touching a filesystem.
function bucketRootFor(corpusVersion) {
  return `/data/${corpusVersion}`;
}

// The "one stamp" gate (brief-one-stamp.md, 2026-09-22): the /data/<version>
// root baked into sw.js and the client bundle (checked above via
// --expect-data-root) and the release's own corpus_version -- the identity
// RELEASE.json carries and publish-release.mjs uploads the release under
// (releases/<corpus_version>/) -- must name the exact same version. Before
// this gate, build-public.mjs could compute one string for the bucket data
// root and a DIFFERENT string ended up in RELEASE.json (see build-public.mjs
// for how the fix keeps them in agreement); a build that regresses that
// agreement now fails here instead of shipping a Worker that 404s every
// text. Pure: takes both values as strings, does no I/O, so this is what the
// unit test pins -- the caller reads RELEASE.json.
function checkReleaseDataRoot({ expectDataRoot, releaseCorpusVersion }) {
  const expected = bucketRootFor(releaseCorpusVersion);
  if (expectDataRoot === expected) return null;
  return (
    `bucket data root "${expectDataRoot}" does not match RELEASE.json corpus_version ` +
    `"${releaseCorpusVersion}" (expected data root "${expected}") -- the deployed site ` +
    'would request data from a version the release folder does not carry. One release, one stamp.'
  );
}

// `limit` defaults to the real tripwire and is only overridable so tests can
// exercise the boundary without writing 18,000 real files to a tmp dir.
// `releaseCorpusVersion`, when given, also runs the bucket-mode "one stamp"
// check above (bucket mode only -- see build-public.mjs's call site).
function verifyArtifact({ distDir, expectDataRoot, limit = FILE_COUNT_LIMIT, releaseCorpusVersion }) {
  const problems = [];

  if (!existsSync(distDir) || !statSync(distDir).isDirectory()) {
    return { ok: false, count: null, problems: [`dist directory does not exist: ${distDir}`] };
  }

  const dataDir = join(distDir, 'data');
  if (existsSync(dataDir)) {
    problems.push(`${dataDir} is present -- expected pruned for an off-origin (PUBLIC_DATA_ROOT) build`);
  }

  const count = countFiles(distDir);
  if (count >= limit) {
    problems.push(`file count ${count} >= tripwire ${limit} (docs/p6-plan.md Settled decision 1)`);
  }

  const swPath = join(distDir, 'sw.js');
  if (!existsSync(swPath)) {
    problems.push(`${swPath} not found`);
  } else {
    const sw = readFileSync(swPath, 'utf8');
    // Mirrors app/scripts/postbuild-sw.mjs's own substitution exactly.
    const expected = `const DATA_ROOT = ${JSON.stringify(expectDataRoot)};`;
    if (!sw.includes(expected)) {
      problems.push(`${swPath} does not contain "${expected}" -- postbuild-sw substitution did not run or used a different root`);
    }
  }

  // sw.js carrying the root is not enough on its own -- the reader's own
  // client bundle must have it baked in too (Vite inlines import.meta.env.
  // PUBLIC_DATA_ROOT as a plain string literal at build time). Search every
  // other .js file under distDir; a build where only sw.js carries it would
  // silently ship a client that still requests the pruned same-origin path.
  const bundleFiles = listJsFiles(distDir, swPath);
  const bundleCarriers = bundleFiles.filter((path) => readFileSync(path, 'utf8').includes(expectDataRoot));
  if (bundleCarriers.length === 0) {
    problems.push(
      `no .js file under ${distDir} other than sw.js contains the expected data root "${expectDataRoot}" -- ` +
        'the client bundle does not carry it (sw.js may, but that is not enough)',
    );
  }

  if (releaseCorpusVersion != null) {
    const releaseProblem = checkReleaseDataRoot({ expectDataRoot, releaseCorpusVersion });
    if (releaseProblem) problems.push(releaseProblem);
  }

  if (!hasReaderPage(distDir)) {
    problems.push('no reader page (.../read/<author>/<work>/<division>/index.html) found under dist -- looks like an empty or failed build');
  }

  return { ok: problems.length === 0, count, problems };
}

function usage(message) {
  if (message) console.error(message);
  console.error(
    'Usage: node scripts/verify-pages-artifact.mjs [DIST_DIR] --expect-data-root <url> [--release-json <RELEASE.json path>]',
  );
  process.exit(2);
}

async function main() {
  const args = process.argv.slice(2);
  let distDir;
  let expectDataRoot;
  let releaseJsonPath;
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--expect-data-root') {
      i += 1;
      expectDataRoot = args[i];
    } else if (arg.startsWith('--expect-data-root=')) {
      expectDataRoot = arg.slice('--expect-data-root='.length);
    } else if (arg === '--release-json') {
      i += 1;
      releaseJsonPath = args[i];
    } else if (arg.startsWith('--release-json=')) {
      releaseJsonPath = arg.slice('--release-json='.length);
    } else if (arg.startsWith('-')) {
      usage(`Unknown option: ${arg}`);
    } else if (!distDir) {
      distDir = arg;
    } else {
      usage('Specify the dist directory only once.');
    }
  }
  if (!expectDataRoot) usage('--expect-data-root <url> is required.');
  distDir = resolve(distDir || join(ROOT, 'app', 'dist', 'client'));

  // Optional bucket-mode "one stamp" check (brief-one-stamp.md): re-reads
  // RELEASE.json fresh off disk rather than trusting anything the caller
  // already computed, so it still catches drift on its own.
  let releaseCorpusVersion;
  if (releaseJsonPath) {
    const resolvedReleaseJson = resolve(releaseJsonPath);
    if (!existsSync(resolvedReleaseJson)) {
      usage(`--release-json file not found: ${resolvedReleaseJson}`);
    }
    let release;
    try {
      release = JSON.parse(readFileSync(resolvedReleaseJson, 'utf8'));
    } catch (error) {
      usage(`--release-json file is not valid JSON: ${resolvedReleaseJson} (${error.message})`);
    }
    releaseCorpusVersion = release.corpus_version;
    if (!releaseCorpusVersion) {
      usage(`--release-json file has no corpus_version: ${resolvedReleaseJson}`);
    }
  }

  const { ok, count, problems } = verifyArtifact({ distDir, expectDataRoot, releaseCorpusVersion });
  console.log(`verify-pages-artifact: ${distDir}`);
  console.log(`  file count: ${count === null ? 'n/a' : count} (limit ${FILE_COUNT_LIMIT})`);
  if (ok) {
    console.log(`  OK -- no dist/data, sw.js and the client bundle both carry PUBLIC_DATA_ROOT=${expectDataRoot}, reader pages present`);
    if (releaseCorpusVersion) console.log(`  OK -- data root matches RELEASE.json corpus_version=${releaseCorpusVersion}`);
  } else {
    for (const p of problems) console.error(`  FAIL: ${p}`);
  }
  process.exitCode = ok ? 0 : 1;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}

export { verifyArtifact, countFiles, hasReaderPage, checkReleaseDataRoot, bucketRootFor, FILE_COUNT_LIMIT };
