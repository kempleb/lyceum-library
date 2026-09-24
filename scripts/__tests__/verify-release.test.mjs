import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { createHash, randomBytes } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { verifyRelease } from '../verify-release.mjs';
import { buildReleaseIndex, sha256File } from '../release-index.mjs';

function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'verify-release-test-'));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// A tiny but valid release: one work with a manifest.json (so
// release-index.mjs can read corpus_version) and one data file, plus a
// reports/ file that must stay outside the index.
function writeSyntheticRelease(dir) {
  mkdirSync(join(dir, 'work1'), { recursive: true });
  writeFileSync(join(dir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: 'test-1' }), 'utf8');
  writeFileSync(join(dir, 'work1', 'text.json'), JSON.stringify({ hello: 'world' }), 'utf8');
  mkdirSync(join(dir, 'reports'), { recursive: true });
  writeFileSync(join(dir, 'reports', 'diagnostics.txt'), 'not part of the release', 'utf8');
}

function writeIndex(dir) {
  const index = buildReleaseIndex(dir);
  writeFileSync(join(dir, 'RELEASE.json'), JSON.stringify(index, null, 2), 'utf8');
  return index;
}

test('passes on a tiny synthetic release', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    const result = verifyRelease(dir);
    assert.equal(result.ok, true);
    assert.equal(result.problems.length, 0);
  });
});

test('fails on a changed byte', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    writeFileSync(join(dir, 'work1', 'text.json'), JSON.stringify({ hello: 'WORLD' }), 'utf8');
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('sha256 mismatch') && p.includes('text.json')));
  });
});

test('fails on a missing file', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    rmSync(join(dir, 'work1', 'text.json'));
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('missing file') && p.includes('text.json')));
  });
});

test('fails on an extra file', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    writeFileSync(join(dir, 'work1', 'extra.json'), '{}', 'utf8');
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('extra file') && p.includes('extra.json')));
  });
});

test('reports/ contents are excluded from verification', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    writeFileSync(join(dir, 'reports', 'new-report.txt'), 'anything', 'utf8');
    const result = verifyRelease(dir);
    assert.equal(result.ok, true);
  });
});

test('derived files are excluded from the index and verification', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    mkdirSync(join(dir, 'lemmata'), { recursive: true });
    mkdirSync(join(dir, 'manifests'), { recursive: true });
    writeFileSync(join(dir, 'lemmata', 'x.json'), '{}', 'utf8');
    writeFileSync(join(dir, 'manifests', 'index.json'), '{}', 'utf8');
    writeFileSync(join(dir, 'work1', 'manifest.lyceum.json'), '{}', 'utf8');
    writeFileSync(join(dir, 'citation-index.json'), '{}', 'utf8');
    const index = writeIndex(dir);
    const paths = index.files.map((file) => file.path);
    for (const path of [
      'lemmata/x.json',
      'manifests/index.json',
      'work1/manifest.lyceum.json',
      'citation-index.json',
    ]) {
      assert.ok(!paths.includes(path), `${path} should be excluded`);
    }
    assert.equal(verifyRelease(dir).ok, true);
  });
});

test('fails when a release contains a symlink', (t) => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    writeIndex(dir);
    try {
      symlinkSync(join(dir, 'work1', 'text.json'), join(dir, 'work1', 'linked.json'));
    } catch (err) {
      if (err.code === 'EPERM' || err.code === 'EACCES') {
        t.skip(`sandbox forbids symlinks: ${err.code}`);
        return;
      }
      throw err;
    }
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('must not contain symlinks') && p.includes('linked.json')));
  });
});

test('fails when RELEASE.json indexes a derived file', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    mkdirSync(join(dir, 'lemmata'), { recursive: true });
    writeFileSync(join(dir, 'lemmata', 'x.json'), '{}', 'utf8');
    const index = writeIndex(dir);
    index.files.push({ path: 'lemmata/x.json', size: 2, sha256: sha256File(join(dir, 'lemmata', 'x.json')) });
    writeFileSync(join(dir, 'RELEASE.json'), JSON.stringify(index), 'utf8');
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.includes('indexed a derived file: lemmata/x.json'));
  });
});

test('sha256File streams files larger than one MiB', () => {
  withTmpDir((dir) => {
    const path = join(dir, 'large.bin');
    writeFileSync(path, randomBytes(Math.floor(2.5 * 1024 * 1024)));
    const expected = createHash('sha256').update(readFileSync(path)).digest('hex');
    assert.equal(sha256File(path), expected);
  });
});

test('fails when RELEASE.json is missing', () => {
  withTmpDir((dir) => {
    writeSyntheticRelease(dir);
    const result = verifyRelease(dir);
    assert.equal(result.ok, false);
    assert.ok(result.problems.some((p) => p.includes('RELEASE.json not found')));
  });
});
