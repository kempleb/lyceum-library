// Tests scripts/mount-corpus.mjs's hold switch (docs/todo/plato-mount.md,
// John's ruling 2026-09-23: Plato stays out of any release sent to the test
// copy until he lifts the hold). Two layers:
//   1. shouldSkipForHold -- the pure gating function -- unit tested directly.
//   2. An end-to-end run of the real script against a scratch fixture corpus
//      placed under this worktree's own corpora/ (mount-corpus.mjs resolves
//      its repo root from import.meta.url, so it cannot be pointed at an
//      external scratch directory) and a source directory outside the repo
//      (via the mount.yaml's source_env absolute-path override), proving the
//      real script -- not just the helper -- skips when held and mounts when
//      READER_INCLUDE_HELD=1. Cleans up both the fixture corpus dir and
//      whatever it wrote under build/dist/.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { shouldSkipForHold } from '../mount-corpus.mjs';

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SCRIPT = join(ROOT, 'scripts', 'mount-corpus.mjs');
const buildDistDir = join(ROOT, 'build', 'dist');
const buildDir = join(ROOT, 'build');

// mount-corpus.mjs always creates build/dist (and build/dist/.mounts/) as a
// side effect, even for a fixture corpus -- other tests (e.g.
// shared/__tests__/lyceum-manifest.test.ts) tell "no corpus data built yet"
// apart from "a real, empty build/dist" and skip differently for each, so
// this suite must not leave build/dist behind if it did not exist before it
// ran. Snapshotted once, at import time, before any test creates it.
const buildDistPreexisted = existsSync(buildDistDir);
const buildPreexisted = existsSync(buildDir);

test('shouldSkipForHold: skips a held corpus when READER_INCLUDE_HELD is unset', () => {
  assert.equal(shouldSkipForHold({ hold: true }, {}), true);
});

test('shouldSkipForHold: skips a held corpus when READER_INCLUDE_HELD is set to anything but "1"', () => {
  assert.equal(shouldSkipForHold({ hold: true }, { READER_INCLUDE_HELD: '0' }), true);
  assert.equal(shouldSkipForHold({ hold: true }, { READER_INCLUDE_HELD: 'true' }), true);
});

test('shouldSkipForHold: mounts a held corpus when READER_INCLUDE_HELD=1', () => {
  assert.equal(shouldSkipForHold({ hold: true }, { READER_INCLUDE_HELD: '1' }), false);
});

test('shouldSkipForHold: never skips a corpus with no hold flag (aristotle today)', () => {
  assert.equal(shouldSkipForHold({}, {}), false);
  assert.equal(shouldSkipForHold({ hold: false }, {}), false);
  assert.equal(shouldSkipForHold({}, { READER_INCLUDE_HELD: '1' }), false);
});

const FIXTURE_CORPUS = 'mounttestfixture';
const FIXTURE_ENV_VAR = 'MOUNTTESTFIXTURE_DATA_DIR';
const corpusDir = join(ROOT, 'corpora', FIXTURE_CORPUS);
const destWorkDir = join(ROOT, 'build', 'dist', 'FixtureWork');
const mountsFile = join(ROOT, 'build', 'dist', '.mounts', `${FIXTURE_CORPUS}.json`);

function writeFixtureCorpus({ hold }) {
  mkdirSync(corpusDir, { recursive: true });
  writeFileSync(
    join(corpusDir, 'mount.yaml'),
    `hold: ${hold}\ncorpus: ${FIXTURE_CORPUS}\nsource_env: ${FIXTURE_ENV_VAR}\nsource_default: /nonexistent\n`,
  );
  writeFileSync(
    join(corpusDir, 'registry.yaml'),
    [
      'registry:',
      '  FixtureWork:',
      '    id: FixtureWork',
      '    slug: fixture-work',
      '    title: Fixture Work',
      '    abbr: FW.',
      '    author: fixtureauthor',
      '    language: grc',
      '    workType: continuous',
      '    books: 1',
      "    bookLabels: ['1']",
      '    greekEdition: Test',
      '    greekSource: { short: Test, full: Test }',
      '    translations:',
      '      - { id: t, name: Test (1900), short: T, slot: english }',
      '    citation: { scheme: stephanus, hideLineNumbers: true }',
      '    blurb: Test.',
    ].join('\n'),
  );
}

function writeFixtureSource(sourceDir) {
  const workDir = join(sourceDir, 'FixtureWork');
  mkdirSync(workDir, { recursive: true });
  writeFileSync(
    join(workDir, 'manifest.json'),
    JSON.stringify({
      work: {
        id: 'FixtureWork',
        title: 'Fixture Work',
        author: 'Fixture Author',
        tlg_author: 'tlg9999',
        tlg_work: 'tlg001',
        greek_edition: 'Test',
      },
      books: [{ book: 1, first_column: '1a', last_column: '9e' }],
    }),
  );
  writeFileSync(
    join(workDir, 'book-01.json'),
    JSON.stringify({ book: 1, segments: [] }),
  );
}

function cleanup() {
  rmSync(corpusDir, { recursive: true, force: true });
  rmSync(destWorkDir, { recursive: true, force: true });
  rmSync(mountsFile, { force: true });
  // Restore the pre-test state exactly: if build/dist (or build/) did not
  // exist before this suite ran, remove whatever mount-corpus.mjs created,
  // rather than leaving an empty-but-present directory behind.
  if (!buildDistPreexisted) rmSync(buildDistDir, { recursive: true, force: true });
  if (!buildPreexisted) rmSync(buildDir, { recursive: true, force: true });
}

test('mount-corpus.mjs: a held corpus is a clean no-op without READER_INCLUDE_HELD', (t) => {
  t.after(cleanup);
  cleanup();
  const sourceDir = mkdtempSync(join(tmpdir(), 'mount-corpus-held-'));
  t.after(() => rmSync(sourceDir, { recursive: true, force: true }));
  writeFixtureCorpus({ hold: true });
  writeFixtureSource(sourceDir);

  const result = execFileSync('node', [SCRIPT, FIXTURE_CORPUS], {
    env: { ...process.env, [FIXTURE_ENV_VAR]: sourceDir },
    encoding: 'utf8',
  });

  assert.match(result, /is held \(mount\.yaml hold: true\) -- skipping/);
  assert.equal(existsSync(destWorkDir), false, 'held corpus must not write into build/dist');
});

test('mount-corpus.mjs: READER_INCLUDE_HELD=1 mounts a held corpus for real', (t) => {
  t.after(cleanup);
  cleanup();
  const sourceDir = mkdtempSync(join(tmpdir(), 'mount-corpus-included-'));
  t.after(() => rmSync(sourceDir, { recursive: true, force: true }));
  writeFixtureCorpus({ hold: true });
  writeFixtureSource(sourceDir);

  const result = execFileSync('node', [SCRIPT, FIXTURE_CORPUS], {
    env: { ...process.env, [FIXTURE_ENV_VAR]: sourceDir, READER_INCLUDE_HELD: '1' },
    encoding: 'utf8',
  });

  assert.match(result, /1 work\(s\) mounted/);
  assert.equal(existsSync(destWorkDir), true, 'READER_INCLUDE_HELD=1 must mount the held corpus');
  assert.equal(existsSync(join(destWorkDir, 'manifest.json')), true);
});

test('mount-corpus.mjs: a corpus with no hold flag mounts normally (unaffected by the hold switch)', (t) => {
  t.after(cleanup);
  cleanup();
  const sourceDir = mkdtempSync(join(tmpdir(), 'mount-corpus-unheld-'));
  t.after(() => rmSync(sourceDir, { recursive: true, force: true }));
  writeFixtureCorpus({ hold: false });
  writeFixtureSource(sourceDir);

  const result = execFileSync('node', [SCRIPT, FIXTURE_CORPUS], {
    env: { ...process.env, [FIXTURE_ENV_VAR]: sourceDir },
    encoding: 'utf8',
  });

  assert.match(result, /1 work\(s\) mounted/);
  assert.equal(existsSync(destWorkDir), true);
});
