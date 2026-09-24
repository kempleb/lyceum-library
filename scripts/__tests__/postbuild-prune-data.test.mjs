// Runs the real app/scripts/postbuild-prune-data.mjs against a scratch
// dist/client/data directory. The script reacts only to PUBLIC_DATA_ROOT --
// bucket mode (DATA_FROM_BUCKET=1) sets that var itself, to its own
// same-origin `/data/<version>` root, before invoking this script
// (scripts/build-public.mjs), so there is nothing bucket-specific for this
// script itself to know about.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'app', 'scripts', 'postbuild-prune-data.mjs');

function withScratchDist(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'postbuild-prune-data-test-'));
  try {
    mkdirSync(join(dir, 'dist', 'client', 'data'), { recursive: true });
    writeFileSync(join(dir, 'dist', 'client', 'data', 'work.json'), '{}', 'utf8');
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function runPrune(cwd, env) {
  execFileSync('node', [SCRIPT], { cwd, env: { ...process.env, ...env }, stdio: 'pipe' });
}

test('PUBLIC_DATA_ROOT set (off-origin URL or bucket mode\'s same-origin path) prunes dist/client/data', () => {
  withScratchDist((dir) => {
    runPrune(dir, { PUBLIC_DATA_ROOT: '/data/2026.09.21-6151ee0' });
    assert.equal(existsSync(join(dir, 'dist', 'client', 'data')), false);
  });
  withScratchDist((dir) => {
    runPrune(dir, { PUBLIC_DATA_ROOT: 'https://data.example.test' });
    assert.equal(existsSync(join(dir, 'dist', 'client', 'data')), false);
  });
});

test('PUBLIC_DATA_ROOT unset leaves dist/client/data in place', () => {
  withScratchDist((dir) => {
    runPrune(dir, { PUBLIC_DATA_ROOT: '' });
    assert.equal(existsSync(join(dir, 'dist', 'client', 'data')), true);
  });
});
