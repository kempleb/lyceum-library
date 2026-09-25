#!/usr/bin/env node
// Publishes one verified release to R2 without ever replacing an object in an
// existing release folder. See docs/cloudflare-setup.md.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyRelease } from './verify-release.mjs';
import { findHeldWorksInDist, formatHeldWorksFindings } from './lib/held-works.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
export const SPAWN_OPTIONS = Object.freeze({ encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });

// app/src/lib/data-route.ts:54
const VERSION_SEGMENT_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

function parseArgs(argv, env = process.env) {
  const options = { dist: 'build/dist', remote: 'r2', dryRun: false, help: false };
  let bucketFromFlag;

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help') {
      options.help = true;
    } else if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--bucket' || arg === '--dist' || arg === '--remote') {
      const value = argv[++index];
      if (!value || value.startsWith('--')) throw new Error(`publish-release: ${arg} requires a value`);
      if (arg === '--bucket') bucketFromFlag = value;
      if (arg === '--dist') options.dist = value;
      if (arg === '--remote') options.remote = value;
    } else {
      throw new Error(`publish-release: unknown option ${arg}`);
    }
  }

  if (options.help) return options;
  options.bucket = bucketFromFlag ?? env.READER_R2_BUCKET;
  if (!options.bucket) throw new Error('publish-release: --bucket is required (or set READER_R2_BUCKET)');
  return options;
}

function isValidVersion(version) {
  return typeof version === 'string' && VERSION_SEGMENT_RE.test(version);
}

function remoteRelease(remote, bucket, version) {
  return `${remote}:${bucket}/releases/${version}`;
}

function buildCheckCommand({ dist, remote, bucket, version }) {
  return {
    command: 'rclone',
    args: ['check', dist, remoteRelease(remote, bucket, version), '--combined', '-'],
  };
}

function buildCopyCommands({ dist, remote, bucket, version }) {
  const destination = remoteRelease(remote, bucket, version);
  return [
    {
      command: 'rclone',
      args: ['copy', dist, destination, '--checksum', '--immutable', '--exclude', 'RELEASE.json', '--transfers', '16'],
    },
    {
      command: 'rclone',
      args: ['copy', join(dist, 'RELEASE.json'), destination, '--checksum', '--immutable'],
    },
  ];
}

function parseCombined(text) {
  const parsed = { identical: [], onlyLocal: [], onlyRemote: [], differ: [], errors: [] };
  const destination = { '=': 'identical', '+': 'onlyLocal', '-': 'onlyRemote', '*': 'differ', '!': 'errors' };
  for (const line of text.split(/\r?\n/)) {
    const match = /^([=+*!-])\s+(.+)$/.exec(line);
    if (match) parsed[destination[match[1]]].push(match[2]);
  }
  return parsed;
}

function decide(parsed) {
  const conflicts = [...parsed.onlyRemote, ...parsed.differ, ...parsed.errors];
  if (conflicts.length) return { action: 'refuse', paths: conflicts };
  if (parsed.onlyLocal.length) return { action: 'upload', paths: parsed.onlyLocal };
  return { action: 'noop', paths: [] };
}

function printCommand({ command, args }) {
  console.log(`${command} ${args.join(' ')}`);
}

function runCheck(command) {
  printCommand(command);
  const result = spawnSync(command.command, command.args, SPAWN_OPTIONS);
  if (result.error) throw Object.assign(result.error, { exitCode: 3 });
  if (result.stdout) process.stdout.write(result.stdout);

  const combined = result.stdout ?? '';
  const hasCombinedLines = /^([=+*!-])\s+.+$/m.test(combined);
  if (result.status !== 0 && (result.status !== 1 || !hasCombinedLines)) {
    const stderrLines = (result.stderr ?? '').trim().split(/\r?\n/).filter(Boolean).slice(-20);
    const detail = stderrLines.length ? `\n${stderrLines.join('\n')}` : '';
    throw Object.assign(new Error(`rclone check failed with status ${result.status}${detail}`), { exitCode: 3 });
  }
  return parseCombined(combined);
}

function summary(parsed) {
  return `identical=${parsed.identical.length}, onlyLocal=${parsed.onlyLocal.length}, onlyRemote=${parsed.onlyRemote.length}, differ=${parsed.differ.length}, errors=${parsed.errors.length}`;
}

function usage() {
  console.log('Usage: node scripts/publish-release.mjs --bucket <name> [--dist <dir>] [--remote <name>] [--dry-run]');
}

async function main() {
  let options;
  try {
    options = parseArgs(process.argv.slice(2));
  } catch (err) {
    console.error(err.message);
    usage();
    process.exitCode = 2;
    return;
  }
  if (options.help) {
    usage();
    return;
  }

  const dist = resolve(ROOT, options.dist);
  const releasePath = join(dist, 'RELEASE.json');
  let release;
  try {
    if (!existsSync(releasePath)) throw new Error(`RELEASE.json not found: ${releasePath}`);
    release = JSON.parse(readFileSync(releasePath, 'utf8'));
    if (!release.corpus_version) throw new Error(`RELEASE.json is missing corpus_version: ${releasePath}`);
    if (!isValidVersion(release.corpus_version)) {
      throw new Error(`RELEASE.json has invalid corpus_version: ${release.corpus_version}`);
    }
    const verified = verifyRelease(dist);
    if (!verified.ok) throw new Error(`release verification failed:\n${verified.problems.map((p) => `  ${p}`).join('\n')}`);
  } catch (err) {
    console.error(`publish-release: ${err.message}`);
    process.exitCode = 2;
    return;
  }

  // Held-corpus guard (docs/todo/plato-mount.md, GPT-6 Sol code review item 1
  // -- BLOCKER): a corpus on hold (mount.yaml hold: true, e.g. Plato) must
  // never leave this checkout via a published release -- not even a dist
  // built locally with mount-corpus.mjs's own READER_INCLUDE_HELD=1 override.
  // That override exists so a held corpus can still be smoke-tested in a
  // local build; publishing it is a different, owner-only decision (lifting
  // the hold in mount.yaml), so it is refused unconditionally here, with no
  // env var able to bypass it.
  const heldFindings = await findHeldWorksInDist(dist, { root: ROOT });
  if (heldFindings.length) {
    console.error(`publish-release: refusing to publish: ${heldFindings.length} held work(s) present in ${dist}:`);
    console.error(formatHeldWorksFindings(heldFindings));
    console.error(
      'publishing a held corpus requires lifting its hold in corpora/<name>/mount.yaml (owner\'s call) -- ' +
        'READER_INCLUDE_HELD=1 only permits a local held-on test BUILD, never a publish.',
    );
    process.exitCode = 7;
    return;
  }

  const values = { dist, remote: options.remote, bucket: options.bucket, version: release.corpus_version };
  let checked;
  try {
    checked = runCheck(buildCheckCommand(values));
  } catch (err) {
    console.error(`publish-release: ${err.message}`);
    process.exitCode = err.exitCode ?? 3;
    return;
  }

  const firstDecision = decide(checked);
  const releaseFolder = `releases/${values.version}/`;
  if (firstDecision.action === 'refuse') {
    for (const path of firstDecision.paths.slice(0, 50)) console.error(`  ${path}`);
    console.error(`refusing: ${releaseFolder} already exists in ${values.bucket} and differs from ${dist}; a release folder is never overwritten (docs/cloudflare-setup.md). Bump the version or fix the local build.`);
    process.exitCode = 4;
    return;
  }
  if (firstDecision.action === 'noop') {
    console.log(`already published: ${releaseFolder} in ${values.bucket} is identical (${checked.identical.length} files)`);
    return;
  }

  if (checked.identical.length) {
    console.log(`resuming: uploading ${firstDecision.paths.length} local-only file(s); existing bytes will not change`);
  } else {
    console.log(`uploading ${firstDecision.paths.length} file(s) to ${releaseFolder} in ${values.bucket}`);
  }
  const copies = buildCopyCommands(values);
  if (options.dryRun) {
    for (const command of copies) printCommand(command);
    return;
  }
  for (const command of copies) {
    printCommand(command);
    const result = spawnSync(command.command, command.args, { ...SPAWN_OPTIONS, stdio: 'inherit' });
    if (result.error) {
      console.error(`publish-release: ${result.error.code ?? result.error.message}: ${result.error.message}`);
      process.exitCode = 3;
      return;
    }
    if (result.status !== 0) {
      console.error(`publish-release: copy failed: ${command.command} ${command.args.join(' ')}`);
      process.exitCode = 5;
      return;
    }
  }

  let after;
  try {
    after = runCheck(buildCheckCommand(values));
  } catch (err) {
    console.error(`publish-release: ${err.message}`);
    process.exitCode = 6;
    return;
  }
  if (decide(after).action !== 'noop') {
    console.error(`publish-release: post-upload check failed: ${summary(after)}`);
    process.exitCode = 6;
    return;
  }
  console.log(`published: ${releaseFolder} to ${values.bucket} (${after.identical.length} files)`);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) main();

export { parseArgs, isValidVersion, buildCheckCommand, buildCopyCommands, parseCombined, decide };
