import { test } from 'node:test';
import assert from 'node:assert/strict';

import { resolveDataSourceMode, VERSION_SEGMENT_RE, isValidVersion, childEnvFor } from '../lib/data-source-mode.mjs';

test('defaults to same-origin when neither var is set', () => {
  assert.deepEqual(resolveDataSourceMode({}), { mode: 'same-origin' });
});

test('PUBLIC_DATA_ROOT alone resolves to off-origin', () => {
  const env = { PUBLIC_DATA_ROOT: 'https://data.example.test' };
  assert.deepEqual(resolveDataSourceMode(env), { mode: 'off-origin', dataRoot: 'https://data.example.test' });
});

test('DATA_FROM_BUCKET=1 alone resolves to bucket mode, with dataRootFor deriving the root from the version', () => {
  const result = resolveDataSourceMode({ DATA_FROM_BUCKET: '1' });
  assert.equal(result.mode, 'bucket');
  assert.equal(result.dataRootFor('2026.09.21-6151ee0'), '/data/2026.09.21-6151ee0');
  assert.equal(result.dataRootFor('dev'), '/data/dev');
});

test('bucket mode\'s dataRootFor throws on a version that fails the route\'s rule', () => {
  const { dataRootFor } = resolveDataSourceMode({ DATA_FROM_BUCKET: '1' });
  assert.throws(() => dataRootFor('..'), /not a valid release-version/);
  assert.throws(() => dataRootFor(''), /not a valid release-version/);
  assert.throws(() => dataRootFor('has/slash'), /not a valid release-version/);
});

test('DATA_FROM_BUCKET="" (empty) is treated as unset', () => {
  assert.deepEqual(resolveDataSourceMode({ DATA_FROM_BUCKET: '' }), { mode: 'same-origin' });
});

test('an unrecognized DATA_FROM_BUCKET value (not exactly "1", not empty) is a hard error', () => {
  assert.throws(() => resolveDataSourceMode({ DATA_FROM_BUCKET: 'true' }), /DATA_FROM_BUCKET must be exactly "1"/);
  assert.throws(() => resolveDataSourceMode({ DATA_FROM_BUCKET: '0' }), /DATA_FROM_BUCKET must be exactly "1"/);
  assert.throws(() => resolveDataSourceMode({ DATA_FROM_BUCKET: ' 1' }), /DATA_FROM_BUCKET must be exactly "1"/);
});

test('setting both PUBLIC_DATA_ROOT and DATA_FROM_BUCKET=1 throws', () => {
  const env = { PUBLIC_DATA_ROOT: 'https://data.example.test', DATA_FROM_BUCKET: '1' };
  assert.throws(() => resolveDataSourceMode(env), /mutually exclusive/);
});

// --- childEnvFor -------------------------------------------------------
// The PUBLIC_DATA_ROOT env every build-public.mjs child process that reads
// it should receive -- see that script's F1 fix note. Exercised directly
// against resolveDataSourceMode's own output, since childEnvFor is pure.

test('childEnvFor: same-origin mode passes no env at all', () => {
  const dataSource = resolveDataSourceMode({});
  assert.deepEqual(childEnvFor(dataSource, '2026.09.21-6151ee0'), {});
});

test('childEnvFor: off-origin mode passes PUBLIC_DATA_ROOT as-is, ignoring the version', () => {
  const dataSource = resolveDataSourceMode({ PUBLIC_DATA_ROOT: 'https://data.example.test' });
  assert.deepEqual(childEnvFor(dataSource, '2026.09.21-6151ee0'), {
    PUBLIC_DATA_ROOT: 'https://data.example.test',
  });
});

test('childEnvFor: bucket mode derives PUBLIC_DATA_ROOT from the version', () => {
  const dataSource = resolveDataSourceMode({ DATA_FROM_BUCKET: '1' });
  assert.deepEqual(childEnvFor(dataSource, '2026.09.21-6151ee0'), {
    PUBLIC_DATA_ROOT: '/data/2026.09.21-6151ee0',
  });
});

test('childEnvFor: bucket mode propagates dataRootFor\'s error on an invalid version', () => {
  const dataSource = resolveDataSourceMode({ DATA_FROM_BUCKET: '1' });
  assert.throws(() => childEnvFor(dataSource, '..'), /not a valid release-version/);
});

// --- VERSION_SEGMENT_RE ----------------------------------------------------
// Pins this copy of the rule to the same accept/reject set as
// app/src/lib/data-route.ts's VERSION_SEGMENT_RE (app/src/__tests__/
// data-route.test.ts runs the identical two arrays below against that
// copy) -- the two can't share one import (a plain `node` script can't
// import a .ts file), so this is how the pair is kept from drifting apart.

const VALID_VERSIONS = [
  '2026.09.21-6151ee0', // build-public.mjs's real from-scratch shape: <sha>-<date>
  '6151ee0-2026-09-21',
  'dev', // pipeline's os.environ.get("CORPUS_VERSION", "dev") fallback
  '0',
  'a',
  'A9',
  'abc_def.1-2',
  'a' + 'b'.repeat(63), // exactly 64 chars: the maximum the rule allows
];

const INVALID_VERSIONS = [
  '',
  '.',
  '..',
  '-abc', // leading char must be alphanumeric
  '.abc',
  'a/b', // no path separators
  'a b', // no whitespace
  'a%2e', // no percent-encoding
  'a\\b', // no backslash
  'ünïcode', // ASCII only
  'a' + 'b'.repeat(64), // 65 chars: one past the maximum
];

test('VERSION_SEGMENT_RE accepts every valid example', () => {
  for (const v of VALID_VERSIONS) {
    assert.equal(VERSION_SEGMENT_RE.test(v), true, `expected ${JSON.stringify(v)} to be valid`);
    assert.equal(isValidVersion(v), true, `expected ${JSON.stringify(v)} to be valid`);
  }
});

test('VERSION_SEGMENT_RE rejects every invalid example', () => {
  for (const v of INVALID_VERSIONS) {
    assert.equal(VERSION_SEGMENT_RE.test(v), false, `expected ${JSON.stringify(v)} to be invalid`);
    assert.equal(isValidVersion(v), false, `expected ${JSON.stringify(v)} to be invalid`);
  }
});
