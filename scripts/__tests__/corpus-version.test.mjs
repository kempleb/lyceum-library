// Pins the "one stamp" fix (brief-one-stamp.md, 2026-09-22): in full bucket
// mode, build-public.mjs derives the bucket-mode data root from the SAME
// release-version string that ends up in build/dist/manifests/index.json
// and build/dist/RELEASE.json -- scripts/emit-lyceum-manifest.mjs's
// reorderCorpusVersion() applied to the raw <sha>-YYYY-MM-DD stamp every
// reader_pipeline / mount-corpus.mjs run is given as CORPUS_VERSION -- never
// the raw stamp itself. build-public.mjs is an imperative top-level script
// (spawns git, runs the pipeline) and isn't itself unit-testable, so this
// pins the pure pieces it now composes the same way it does.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { reorderCorpusVersion } from '../emit-lyceum-manifest.mjs';
import { resolveDataSourceMode, isValidVersion } from '../lib/data-source-mode.mjs';

// The exact shape build-public.mjs's full-mode branch computes:
// `${git rev-parse --short HEAD}-${new Date().toISOString().slice(0, 10)}`.
const RAW_PIPELINE_STAMP = '25a4036-2026-09-22';
const RELEASE_VERSION = '2026.09.22-25a4036';

test('reorderCorpusVersion turns the raw pipeline stamp into the release version', () => {
  assert.equal(reorderCorpusVersion(RAW_PIPELINE_STAMP), RELEASE_VERSION);
});

test('the release version differs from the raw stamp (the bug this fix closes: they must not be used interchangeably)', () => {
  assert.notEqual(RELEASE_VERSION, RAW_PIPELINE_STAMP);
});

test('full bucket mode: the resolved data root uses the release version, not the raw pipeline stamp', () => {
  const dataSource = resolveDataSourceMode({ DATA_FROM_BUCKET: '1' });
  const corpusVersion = reorderCorpusVersion(RAW_PIPELINE_STAMP);
  assert.equal(dataSource.dataRootFor(corpusVersion), '/data/2026.09.22-25a4036');
  // The bug this fix closes, made concrete: computing the data root from the
  // raw stamp instead gives a DIFFERENT path than the release actually
  // carries -- this is what 404'd every text on 2026-09-22.
  assert.notEqual(dataSource.dataRootFor(RAW_PIPELINE_STAMP), dataSource.dataRootFor(corpusVersion));
});

test('the derived release version is itself a valid /data/<version> path segment', () => {
  assert.equal(isValidVersion(reorderCorpusVersion(RAW_PIPELINE_STAMP)), true);
});

test('reorderCorpusVersion is undefined behavior build-public.mjs guards against: malformed input returns null', () => {
  // build-public.mjs throws immediately if this happens rather than
  // silently building with CORPUS_VERSION = null.
  assert.equal(reorderCorpusVersion('not-a-stamp'), null);
  assert.equal(reorderCorpusVersion(RELEASE_VERSION), null); // already reordered: not idempotent
});
