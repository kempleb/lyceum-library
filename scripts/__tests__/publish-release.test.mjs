import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { performance } from 'node:perf_hooks';

import { SPAWN_OPTIONS, buildCheckCommand, buildCopyCommands, decide, isValidVersion, parseArgs, parseCombined } from '../publish-release.mjs';

test('uses a child-process buffer large enough for a full release check', () => {
  // A 2026-09-22 real release check failed with "spawnSync rclone ENOBUFS" at the 1 MiB default.
  assert.ok(SPAWN_OPTIONS.maxBuffer >= 64 * 1024 * 1024);
});

test('requires a bucket flag or environment value', () => {
  assert.throws(() => parseArgs([], {}), /--bucket is required/);
  assert.equal(parseArgs(['--bucket', 'flag-bucket'], { READER_R2_BUCKET: 'env-bucket' }).bucket, 'flag-bucket');
  assert.equal(parseArgs([], { READER_R2_BUCKET: 'env-bucket' }).bucket, 'env-bucket');
});

test('validates Worker-compatible corpus versions', () => {
  assert.equal(isValidVersion('2026.09.21-6151ee0'), true);
  assert.equal(isValidVersion('../x'), false);
  assert.equal(isValidVersion('a'.repeat(65)), false);
});

test('builds the exact rclone check command', () => {
  assert.deepEqual(buildCheckCommand({ dist: 'build/dist', remote: 'r2', bucket: 'data', version: 'v1' }), {
    command: 'rclone', args: ['check', 'build/dist', 'r2:data/releases/v1', '--combined', '-'],
  });
});

test('builds immutable copies with RELEASE.json last', () => {
  assert.deepEqual(buildCopyCommands({ dist: 'build/dist', remote: 'r2', bucket: 'data', version: 'v1' }), [
    { command: 'rclone', args: ['copy', 'build/dist', 'r2:data/releases/v1', '--checksum', '--immutable', '--exclude', 'RELEASE.json', '--transfers', '16'] },
    { command: 'rclone', args: ['copy', 'build/dist/RELEASE.json', 'r2:data/releases/v1', '--checksum', '--immutable'] },
  ]);
});

test('parses every rclone combined marker', () => {
  // rclone check --help says:
  // "= path" means path was found in source and destination and was identical
  // "- path" means path was missing on the source, so only in the destination
  // "+ path" means path was missing on the destination, so only in the source
  // "* path" means path was present in source and destination but different.
  // "! path" means there was an error reading or hashing the source or dest.
  assert.deepEqual(parseCombined('= identical.txt\n- only-destination.txt\n+ only-source.txt\n* different.txt\n! hash-error.txt\n'), {
    identical: ['identical.txt'], onlyLocal: ['only-source.txt'], onlyRemote: ['only-destination.txt'], differ: ['different.txt'], errors: ['hash-error.txt'],
  });
});

test('decides whether to refuse, skip, or resume', () => {
  assert.deepEqual(decide(parseCombined('= same\n')), { action: 'noop', paths: [] });
  assert.deepEqual(decide(parseCombined('= same\n+ local-only\n')), { action: 'upload', paths: ['local-only'] });
  assert.deepEqual(decide(parseCombined('- remote-only\n* changed\n')), { action: 'refuse', paths: ['remote-only', 'changed'] });
});

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const rcloneAvailable = spawnSync('rclone', ['version'], { encoding: 'utf8' }).status === 0;
function sha256(text) {
  return createHash('sha256').update(text).digest('hex');
}

function writeFakeDist(dir, extra = []) {
  const entries = [['alpha.txt', 'alpha\n'], ['nested/beta.txt', 'beta\n'], ...extra];
  for (let index = 0; index < 1500; index += 1) {
    const number = String(index).padStart(4, '0');
    entries.push([`texts/${number}/section-${number}/subdivision-${number}/fragment.txt`, `file ${number}\n`]);
  }
  for (const [path, content] of entries) {
    const absolute = join(dir, path);
    mkdirSync(dirname(absolute), { recursive: true });
    writeFileSync(absolute, content);
  }
  writeFileSync(join(dir, 'RELEASE.json'), `${JSON.stringify({
    corpus_version: '2026.09.22-test000', schema_version: '1.0',
    files: entries.map(([path, content]) => ({ path, size: Buffer.byteLength(content), sha256: sha256(content) })),
  }, null, 2)}\n`);
}

function runPublish({ dist, bucket, config, dryRun = false, env = {} }) {
  const args = [join(ROOT, 'scripts/publish-release.mjs'), '--dist', dist, '--remote', 'loc', '--bucket', bucket];
  if (dryRun) args.push('--dry-run');
  return spawnSync(process.execPath, args, { encoding: 'utf8', env: { ...process.env, RCLONE_CONFIG: config, ...env } });
}

test('publishes safely with the local rclone backend', { skip: !rcloneAvailable && 'rclone is not on PATH' }, async (t) => {
  const temp = mkdtempSync(join(tmpdir(), 'publish-release-'));
  try {
    const dist = join(temp, 'dist');
    const bucket = join(temp, 'bucket');
    const config = join(temp, 'rclone.conf');
    const release = join(bucket, 'releases', '2026.09.22-test000');
    mkdirSync(dist);
    writeFakeDist(dist);
    writeFileSync(config, '[loc]\ntype = local\n');

    await t.test('empty bucket publishes all files', () => {
      const started = performance.now();
      const fresh = runPublish({ dist, bucket, config });
      const elapsed = performance.now() - started;
      assert.equal(fresh.status, 0, fresh.stderr);
      assert.match(fresh.stdout, /^uploading \d+ file\(s\) to releases\//m);
      assert.doesNotMatch(fresh.stdout, /resuming/);
      assert.equal(readFileSync(join(release, 'alpha.txt'), 'utf8'), 'alpha\n');
      assert.equal(readFileSync(join(release, 'nested/beta.txt'), 'utf8'), 'beta\n');
      assert.ok(statSync(join(release, 'RELEASE.json')).isFile());
      t.diagnostic(`empty bucket publish time: ${elapsed.toFixed(0)} ms`);
    });

    const beforeRepeat = statSync(join(release, 'alpha.txt')).mtimeMs;
    await t.test('unchanged rerun is a no-op', () => {
      const unchanged = runPublish({ dist, bucket, config });
      assert.equal(unchanged.status, 0, unchanged.stderr);
      assert.match(unchanged.stdout, /already published/);
      assert.equal(statSync(join(release, 'alpha.txt')).mtimeMs, beforeRepeat);
    });

    const releaseMtime = statSync(join(release, 'RELEASE.json')).mtimeMs;
    unlinkSync(join(release, 'alpha.txt'));
    await t.test('missing remote data file is restored without touching RELEASE.json', () => {
      const resumed = runPublish({ dist, bucket, config });
      assert.equal(resumed.status, 0, resumed.stderr);
      assert.match(resumed.stdout, /^resuming: uploading 1 local-only file\(s\)/m);
      assert.equal(readFileSync(join(release, 'alpha.txt'), 'utf8'), 'alpha\n');
      assert.equal(statSync(join(release, 'RELEASE.json')).mtimeMs, releaseMtime);
    });

    writeFileSync(join(release, 'alpha.txt'), 'Alpha\n');
    await t.test('changed remote object refuses publication', () => {
      const changed = runPublish({ dist, bucket, config });
      assert.equal(changed.status, 4);
      assert.match(changed.stderr, /refusing/);
    });

    writeFileSync(join(release, 'alpha.txt'), 'alpha\n');
    writeFileSync(join(release, 'extra.txt'), 'extra\n');
    await t.test('extra remote object refuses publication', () => {
      const extra = runPublish({ dist, bucket, config });
      assert.equal(extra.status, 4);
      assert.match(extra.stderr, /refusing/);
    });

    await t.test('dry run leaves an empty bucket untouched and prints both copies', () => {
      const dryDist = join(temp, 'dry-dist');
      const dryBucket = join(temp, 'dry-bucket');
      mkdirSync(dryDist);
      writeFakeDist(dryDist);
      const result = runPublish({ dist: dryDist, bucket: dryBucket, config, dryRun: true });
      assert.equal(result.status, 0, result.stderr);
      assert.match(result.stdout, /rclone copy .*--exclude RELEASE\.json/);
      assert.match(result.stdout, /rclone copy .*RELEASE\.json/);
      assert.equal(statSync(dryBucket, { throwIfNoEntry: false }), undefined);
    });
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

// docs/todo/plato-mount.md, GPT-6 Sol code review item 1 (BLOCKER): a dist
// carrying a held corpus's work (Plato is held via corpora/plato/mount.yaml
// hold: true -- see scripts/lib/held-works.mjs) must never be published, not
// even with READER_INCLUDE_HELD=1 (that override is for a local held-on test
// BUILD only; publishing requires lifting the hold in mount.yaml itself).
// This refusal fires before the rclone check runs, so it needs no rclone
// binary and no bucket/config fixture.
test('refuses to publish a dist that carries a held corpus\'s work, even with READER_INCLUDE_HELD=1', () => {
  const temp = mkdtempSync(join(tmpdir(), 'publish-release-held-'));
  try {
    const dist = join(temp, 'dist');
    mkdirSync(dist);
    // 'Euthyphro' is a real corpora/plato/registry.yaml work id -- the same
    // directory name mount-corpus.mjs would copy it under in build/dist.
    writeFakeDist(dist, [['Euthyphro/manifest.json', '{}\n']]);

    const withoutOverride = runPublish({ dist, bucket: join(temp, 'bucket'), config: join(temp, 'rclone.conf') });
    assert.notEqual(withoutOverride.status, 0);
    assert.match(withoutOverride.stderr, /held/i);
    assert.match(withoutOverride.stderr, /plato/);

    const withOverride = runPublish({
      dist,
      bucket: join(temp, 'bucket'),
      config: join(temp, 'rclone.conf'),
      env: { READER_INCLUDE_HELD: '1' },
    });
    assert.notEqual(withOverride.status, 0, 'READER_INCLUDE_HELD=1 must not let publish-release.mjs bypass the hold');
    assert.match(withOverride.stderr, /held/i);
    assert.match(withOverride.stderr, /plato/);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});
