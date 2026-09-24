// Pins the fix for the bug the 2026-09-23 no-source-access rehearsal found
// (docs/release-from-dist.md's "Proven without source access" section):
// build-public.mjs's --from-dist mode used to read corpus_version via
// release-index.mjs's readCorpusVersion(), which prefers
// manifests/index.json and otherwise falls back to a work's manifest.json.
// A release that was only ever copied or downloaded, never built-from in
// this checkout, has no manifests/index.json yet at this point in the stage
// list (emit-lyceum-manifest runs much later) -- so it fell back to a work's
// RAW pipeline stamp (`<short commit>-YYYY-MM-DD`) instead of the release's
// own public stamp (`YYYY.MM.DD-<short commit>`) recorded in RELEASE.json --
// the exact drift the "one stamp" fix (2026-09-22, 40b9bbc) closed for full
// mode but not this one. fromDistCorpusVersion() reads RELEASE.json's own
// corpus_version directly, skipping that fallback chain entirely.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { fromDistCorpusVersion } from '../release-index.mjs';

function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'from-dist-corpus-version-test-'));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const RELEASE_VERSION = '2026.09.22-25a4036';
const RAW_PIPELINE_STAMP = '25a4036-2026-09-22';

test('reads the release form from RELEASE.json, not a work manifest\'s raw stamp, when manifests/index.json is absent', () => {
  withTmpDir((dir) => {
    // A release as actually stored: manifests/** excluded (derived), but the
    // work manifest's RAW stamp still sits in its own manifest.json.
    mkdirSync(join(dir, 'work1'), { recursive: true });
    writeFileSync(join(dir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: RAW_PIPELINE_STAMP }), 'utf8');
    writeFileSync(join(dir, 'RELEASE.json'), JSON.stringify({ corpus_version: RELEASE_VERSION }), 'utf8');

    assert.equal(fromDistCorpusVersion(dir), RELEASE_VERSION);
  });
});

test('throws a clear error when RELEASE.json is missing', () => {
  withTmpDir((dir) => {
    mkdirSync(join(dir, 'work1'), { recursive: true });
    writeFileSync(join(dir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: RAW_PIPELINE_STAMP }), 'utf8');

    assert.throws(() => fromDistCorpusVersion(dir), /RELEASE\.json not found/);
  });
});

test('throws a clear error when RELEASE.json has no corpus_version', () => {
  withTmpDir((dir) => {
    writeFileSync(join(dir, 'RELEASE.json'), JSON.stringify({ producer_commit: '25a4036' }), 'utf8');

    assert.throws(() => fromDistCorpusVersion(dir), /no corpus_version/);
  });
});
