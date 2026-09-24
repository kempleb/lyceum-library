// Tests scripts/build-citation-index.mjs's INDEXED_SCHEMES (docs/todo/
// plato-mount.md step 5, P4 precondition recorded in docs/p3-plan.md's
// Settled decision 5): a stephanus-scheme work's columns must be scanned
// into the cross-corpus citation index exactly like a bekker/busse work's --
// never silently skipped, which would make a bare Stephanus citation
// ("327a") resolve today as a confident, WRONG Bekker/Busse hit instead of
// (correctly) a genuine miss or a reported ambiguity.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { buildCitationIndex } from '../build-citation-index.mjs';

function withScratchDist(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'build-citation-index-test-'));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeWork(distDir, id, scheme, columns) {
  const workDir = join(distDir, id);
  mkdirSync(workDir, { recursive: true });
  writeFileSync(join(workDir, 'manifest.json'), JSON.stringify({ id, citation: { scheme } }));
  writeFileSync(join(workDir, 'columns.json'), JSON.stringify(columns));
}

test('a stephanus work\'s columns ARE scanned into the index (not silently absent)', () => {
  withScratchDist((dist) => {
    writeWork(dist, 'Republic', 'stephanus', {
      '327a': [{ book: 1, lo: 1, hi: 5 }],
    });
    const { index, works } = buildCitationIndex(dist);
    assert.deepEqual(works, ['Republic']);
    assert.deepEqual(index['327a'], [{ work: 'Republic', book: 1, lo: 1, hi: 5 }]);
  });
});

test('a stephanus work and a bekker work are both indexed side by side', () => {
  withScratchDist((dist) => {
    writeWork(dist, 'Republic', 'stephanus', { '327a': [{ book: 1, lo: 1, hi: 5 }] });
    writeWork(dist, 'EN', 'bekker', { '1094a': [{ book: 1, lo: 1, hi: 28 }] });
    const { index, works } = buildCitationIndex(dist);
    assert.deepEqual(works.sort(), ['EN', 'Republic']);
    assert.ok(index['327a']);
    assert.ok(index['1094a']);
  });
});

test('a scheme not in INDEXED_SCHEMES (e.g. book-section) is still excluded', () => {
  withScratchDist((dist) => {
    writeWork(dist, 'SomeFragments', 'book-section', { '1.1': [{ book: 1, lo: 1, hi: 1 }] });
    const { index, works } = buildCitationIndex(dist);
    assert.deepEqual(works, []);
    assert.deepEqual(index, {});
  });
});

test('two different-scheme works sharing a bare column string both land in the index under that column (cross-scheme collision, left for the router to disambiguate)', () => {
  withScratchDist((dist) => {
    // Categories (bekker) and a hypothetical stephanus work both start
    // pagination at "1a" -- the exact P4 precondition scenario.
    writeWork(dist, 'Cat', 'bekker', { '1a': [{ book: 1, lo: 1, hi: 29 }] });
    writeWork(dist, 'Republic', 'stephanus', { '1a': [{ book: 1, lo: 1, hi: 10 }] });
    const { index } = buildCitationIndex(dist);
    const workIds = index['1a'].map((e) => e.work).sort();
    assert.deepEqual(workIds, ['Cat', 'Republic']);
  });
});
