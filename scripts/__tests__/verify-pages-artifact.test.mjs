import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { verifyArtifact, FILE_COUNT_LIMIT, checkReleaseDataRoot, bucketRootFor } from '../verify-pages-artifact.mjs';

const EXPECT_ROOT = 'https://staging-data.invalid/data';

function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'verify-pages-artifact-test-'));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// Builds a minimal-but-valid artifact: index.html at root, one reader page
// under read/[author]/[work]/book-[n]/index.html, an sw.js already
// substituted with EXPECT_ROOT (mirrors what postbuild-sw.mjs emits), and a
// client bundle chunk under _astro/ that carries the root the way a real
// Vite build does -- a plain backtick-string literal (checked against a real
// zero-works build: `` `${EXPECT_ROOT}`.replace(...) `` in dist/client/_astro/
// data.*.js and search.*.js).
function writeValidArtifact(dir) {
  writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
  const bookDir = join(dir, 'read', 'plato', 'republic', 'book-1');
  mkdirSync(bookDir, { recursive: true });
  writeFileSync(join(bookDir, 'index.html'), '<html></html>', 'utf8');
  writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(EXPECT_ROOT)};\n`, 'utf8');
  const astroDir = join(dir, '_astro');
  mkdirSync(astroDir, { recursive: true });
  writeFileSync(join(astroDir, 'data.abc123.js'), `var m=\`${EXPECT_ROOT}\`.replace(/\\/+$/,\`\`);\n`, 'utf8');
}

test('passes on a clean, pruned artifact (sw.js and the client bundle both carry the root)', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir);
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, true);
    assert.equal(result.problems.length, 0);
    assert.equal(result.count, 4); // index.html, sw.js, book/1/index.html, _astro/data.abc123.js
  });
});

test('fails when dist/data is present', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir);
    const dataDir = join(dir, 'data');
    mkdirSync(dataDir, { recursive: true });
    writeFileSync(join(dataDir, 'corpus.json'), '{}', 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('data') && p.includes('present')));
  });
});

test('default limit matches the plan tripwire', () => {
  assert.equal(FILE_COUNT_LIMIT, 18000);
});

test('fails when file count meets the tripwire', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir); // 4 files: index.html, sw.js, book/1/index.html, _astro bundle
    // `limit` is injectable so this test can hit the boundary exactly
    // without writing 18,000 real files -- production callers never pass it
    // and get the real FILE_COUNT_LIMIT.
    const atLimit = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT, limit: 4 });
    assert.equal(atLimit.ok, false);
    assert.ok(atLimit.problems.some((p) => p.includes('tripwire')));

    const underLimit = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT, limit: 5 });
    assert.equal(underLimit.ok, true);
  });
});

test('fails when only sw.js carries the data root and no client bundle does', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir);
    // Overwrite the bundle chunk with unrelated content -- sw.js still
    // carries EXPECT_ROOT, the client bundle no longer does.
    writeFileSync(join(dir, '_astro', 'data.abc123.js'), 'var m=`/data/some-other-root`;\n', 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(
      result.problems.some((p) => p.includes('.js') && p.includes(EXPECT_ROOT) && p.includes('client bundle')),
    );
  });
});

test('fails when no client bundle file exists at all (only sw.js)', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    const bookDir = join(dir, 'read', 'plato', 'republic', 'book-1');
    mkdirSync(bookDir, { recursive: true });
    writeFileSync(join(bookDir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(EXPECT_ROOT)};\n`, 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('client bundle')));
  });
});

test('fails when sw.js does not carry the expected DATA_ROOT literal', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir);
    writeFileSync(join(dir, 'sw.js'), "const DATA_ROOT = '';\n", 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('sw.js') && p.includes('DATA_ROOT')));
  });
});

test('fails when sw.js is missing entirely', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    const bookDir = join(dir, 'plato', 'republic', 'book', '1');
    mkdirSync(bookDir, { recursive: true });
    writeFileSync(join(bookDir, 'index.html'), '<html></html>', 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('sw.js not found')));
  });
});

test('fails when no reader page exists', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(EXPECT_ROOT)};\n`, 'utf8');
    const authorsDir = join(dir, 'authors');
    mkdirSync(authorsDir, { recursive: true });
    writeFileSync(join(authorsDir, 'index.html'), '<html></html>', 'utf8');
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('no reader page')));
  });
});

test('fails when the dist only has old-shape forwarder pages, no real read/ reader page', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(EXPECT_ROOT)};\n`, 'utf8');
    const oldBookDir = join(dir, 'plato', 'republic', 'book', '1');
    mkdirSync(oldBookDir, { recursive: true });
    writeFileSync(
      join(oldBookDir, 'index.html'),
      '<html><head><meta http-equiv="refresh" content="0;url=/read/plato/republic/book-1" /></head></html>',
      'utf8',
    );
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('no reader page')));
  });
});

test('fails when the read/.../book-N/ page itself is a meta-refresh forwarder', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(EXPECT_ROOT)};\n`, 'utf8');
    const bookDir = join(dir, 'read', 'plato', 'republic', 'book-1');
    mkdirSync(bookDir, { recursive: true });
    writeFileSync(
      join(bookDir, 'index.html'),
      '<html><head><meta http-equiv="refresh" content="0;url=/somewhere-else" /></head></html>',
      'utf8',
    );
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('no reader page')));
  });
});

test('fails when dist directory does not exist', () => {
  withTmpDir((dir) => {
    const missing = join(dir, 'does-not-exist');
    const result = verifyArtifact({ distDir: missing, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, false);
    assert.equal(result.count, null);
    assert.ok(result.problems.some((p) => p.includes('does not exist')));
  });
});

// --- the "one stamp" gate (brief-one-stamp.md, 2026-09-22) -----------------
// bucketRootFor/checkReleaseDataRoot are pure -- no filesystem -- so the
// comparison itself is pinned directly, then again through verifyArtifact's
// optional `releaseCorpusVersion` param, the way build-public.mjs's
// --release-json flag feeds it.

test('bucketRootFor: the bucket route is always /data/<version>', () => {
  assert.equal(bucketRootFor('2026.09.22-25a4036'), '/data/2026.09.22-25a4036');
});

test('checkReleaseDataRoot: passes when the baked-in root names the release version', () => {
  const problem = checkReleaseDataRoot({
    expectDataRoot: '/data/2026.09.22-25a4036',
    releaseCorpusVersion: '2026.09.22-25a4036',
  });
  assert.equal(problem, null);
});

test('checkReleaseDataRoot: fails and names both values when they disagree', () => {
  // The exact shape of 2026-09-22's incident: the client bundle/sw.js asked
  // for the raw pipeline stamp's path while RELEASE.json (and the bucket
  // folder publish-release.mjs uploads to) carried the reordered version.
  const problem = checkReleaseDataRoot({
    expectDataRoot: '/data/25a4036-2026-09-22',
    releaseCorpusVersion: '2026.09.22-25a4036',
  });
  assert.match(problem, /bucket data root "\/data\/25a4036-2026-09-22"/);
  assert.match(problem, /does not match RELEASE\.json corpus_version "2026\.09\.22-25a4036"/);
  assert.match(problem, /expected data root "\/data\/2026\.09\.22-25a4036"/);
});

test('verifyArtifact: passes an otherwise-clean bucket-mode artifact when releaseCorpusVersion matches', () => {
  const root = '/data/2026.09.22-25a4036';
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    const bookDir = join(dir, 'read', 'plato', 'republic', 'book-1');
    mkdirSync(bookDir, { recursive: true });
    writeFileSync(join(bookDir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(root)};\n`, 'utf8');
    const astroDir = join(dir, '_astro');
    mkdirSync(astroDir, { recursive: true });
    writeFileSync(join(astroDir, 'data.abc123.js'), `var m=\`${root}\`.replace(/\\/+$/,\`\`);\n`, 'utf8');

    const result = verifyArtifact({ distDir: dir, expectDataRoot: root, releaseCorpusVersion: '2026.09.22-25a4036' });
    assert.equal(result.ok, true);
    assert.equal(result.problems.length, 0);
  });
});

test('verifyArtifact: fails an otherwise-clean bucket-mode artifact when releaseCorpusVersion disagrees with the baked-in root', () => {
  const root = '/data/25a4036-2026-09-22';
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'index.html'), '<html></html>', 'utf8');
    const bookDir = join(dir, 'read', 'plato', 'republic', 'book-1');
    mkdirSync(bookDir, { recursive: true });
    writeFileSync(join(bookDir, 'index.html'), '<html></html>', 'utf8');
    writeFileSync(join(dir, 'sw.js'), `const DATA_ROOT = ${JSON.stringify(root)};\n`, 'utf8');
    const astroDir = join(dir, '_astro');
    mkdirSync(astroDir, { recursive: true });
    writeFileSync(join(astroDir, 'data.abc123.js'), `var m=\`${root}\`.replace(/\\/+$/,\`\`);\n`, 'utf8');

    const result = verifyArtifact({ distDir: dir, expectDataRoot: root, releaseCorpusVersion: '2026.09.22-25a4036' });
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('does not match RELEASE.json corpus_version')));
  });
});

test('verifyArtifact: omitting releaseCorpusVersion skips the check entirely (off-origin mode)', () => {
  withTmpDir((dir) => {
    writeValidArtifact(dir);
    const result = verifyArtifact({ distDir: dir, expectDataRoot: EXPECT_ROOT });
    assert.equal(result.ok, true);
  });
});
