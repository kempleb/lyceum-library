import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SCRIPT = join(ROOT, 'scripts', 'check-addresses.mjs');

// Builds a tiny dist tree: a homepage, two "directory" pages served by their
// own index.html (the common case), and one bare "<name>.html" page (like
// 404.html/offline.html in the real build) -- covering both branches of
// check-addresses.mjs's addressFor(), which mirrors check-links.mjs's
// resolve() candidates in reverse.
function writeDist(dir, pages) {
  for (const page of pages) {
    const file = join(dir, page);
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, '<!doctype html><html><body>page</body></html>\n');
  }
}

function writeBaseline(dir, addresses) {
  writeFileSync(join(dir, 'address-baseline.txt'), addresses.length ? `${[...addresses].sort().join('\n')}\n` : '');
}

// check-addresses.mjs always reads/writes scripts/address-baseline.txt next
// to itself, so each test runs the script from a scratch copy of scripts/
// (just this script) with its own baseline file alongside it.
function setupScriptDir(temp) {
  const scriptsDir = join(temp, 'scripts');
  mkdirSync(scriptsDir, { recursive: true });
  writeFileSync(join(scriptsDir, 'check-addresses.mjs'), readFileSync(SCRIPT, 'utf8'));
  return scriptsDir;
}

function run(scriptsDir, args) {
  return spawnSync(process.execPath, [join(scriptsDir, 'check-addresses.mjs'), ...args], { encoding: 'utf8' });
}

test('passes when the build matches the baseline exactly', () => {
  const temp = mkdtempSync(join(tmpdir(), 'check-addresses-pass-'));
  try {
    const scriptsDir = setupScriptDir(temp);
    const dist = join(temp, 'dist');
    writeDist(dist, ['index.html', 'foo/index.html', 'bar/index.html', '404.html']);
    writeBaseline(scriptsDir, ['/', '/foo/', '/bar/', '/404']);

    const result = run(scriptsDir, [dist]);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Addresses checked: 4; baseline: 4; missing: 0/);
    assert.doesNotMatch(result.stdout, /new addresses/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test('fails and names the address when a baseline address is missing from the build', () => {
  const temp = mkdtempSync(join(tmpdir(), 'check-addresses-missing-'));
  try {
    const scriptsDir = setupScriptDir(temp);
    const dist = join(temp, 'dist');
    // The build no longer has /bar/ -- as if a published page were dropped.
    writeDist(dist, ['index.html', 'foo/index.html']);
    writeBaseline(scriptsDir, ['/', '/foo/', '/bar/']);

    const result = run(scriptsDir, [dist]);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /\/bar\//);
    assert.match(result.stderr, /1 address\(es\)/);
    assert.match(result.stderr, /John/);
    assert.match(result.stderr, /--update/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test('passes and notes new addresses not yet in the baseline', () => {
  const temp = mkdtempSync(join(tmpdir(), 'check-addresses-added-'));
  try {
    const scriptsDir = setupScriptDir(temp);
    const dist = join(temp, 'dist');
    // The build has a brand-new page, /baz/, that isn't in the baseline yet.
    writeDist(dist, ['index.html', 'foo/index.html', 'baz/index.html']);
    writeBaseline(scriptsDir, ['/', '/foo/']);

    const result = run(scriptsDir, [dist]);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Addresses checked: 3; baseline: 2; missing: 0/);
    assert.match(result.stdout, /1 new addresses not in the baseline; run with --update to record them/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test('--update rewrites the baseline from the dist directory', () => {
  const temp = mkdtempSync(join(tmpdir(), 'check-addresses-update-'));
  try {
    const scriptsDir = setupScriptDir(temp);
    const dist = join(temp, 'dist');
    writeDist(dist, ['index.html', 'foo/index.html', 'baz/index.html']);
    writeBaseline(scriptsDir, ['/', '/foo/', '/bar/']); // stale: has /bar/, lacks /baz/

    const result = run(scriptsDir, [dist, '--update']);
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Wrote 3 address\(es\)/);

    const baseline = readFileSync(join(scriptsDir, 'address-baseline.txt'), 'utf8');
    assert.equal(baseline, '/\n/baz/\n/foo/\n');

    // Running again against the freshly written baseline now passes clean.
    const recheck = run(scriptsDir, [dist]);
    assert.equal(recheck.status, 0, recheck.stderr);
    assert.match(recheck.stdout, /Addresses checked: 3; baseline: 3; missing: 0/);
    assert.doesNotMatch(recheck.stdout, /new addresses/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

test('accepts --dist= the same way check-links.mjs does', () => {
  const temp = mkdtempSync(join(tmpdir(), 'check-addresses-dist-flag-'));
  try {
    const scriptsDir = setupScriptDir(temp);
    const dist = join(temp, 'dist');
    writeDist(dist, ['index.html']);
    writeBaseline(scriptsDir, ['/']);

    const result = run(scriptsDir, [`--dist=${dist}`]);
    assert.equal(result.status, 0, result.stderr);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});
