#!/usr/bin/env node
// Downloads one dated release (build/dist + RELEASE.json, published with
// `rclone copy build/dist r2:<bucket>/releases/<version>/ --checksum` per
// docs/release-from-dist.md) to a local directory, then verifies it against
// its own RELEASE.json before it's trusted as input to
// `build-public.mjs --from-dist`.
//
// Two transports:
//   - rclone (default): requires rclone configured for an `r2:` remote; not
//     run in this task or in CI.
//   - `--from-url <base>`: HTTPS GETs (HTTP allowed only to localhost/
//     127.0.0.1, for tests) against a static file server that serves
//     `<base>/<version>/RELEASE.json` and `<base>/<version>/<path>` for
//     every path RELEASE.json lists (e.g. the read-only
//     /data/<version>/<path> route on a deployed Worker). Node stdlib only
//     (global fetch). The destination directory must be a fresh folder --
//     empty or not yet existing -- that no other process writes to for the
//     duration of the fetch; a non-empty destination, or a symlink at or
//     under it, is refused outright. Every listed path, size, and sha256 is
//     validated before any download starts; each file's temp file is opened
//     with an exclusive create (refusing an existing file or symlink there)
//     and streams to a size cap, then verifies and moves into place; any
//     redirect, a 4xx, or a size/sha256 mismatch is refused outright (no
//     retry). Network errors and 5xx get a bounded, timed-out,
//     exponentially-backed-off retry; the first fatal failure stops the
//     queue from taking new work and waits for in-flight downloads to settle
//     before rejecting.
//
// Run: node scripts/fetch-release.mjs <version> [dest]
//      node scripts/fetch-release.mjs <version> [dest] --from-url <base>
import { spawnSync } from 'node:child_process';
import { closeSync, createWriteStream, lstatSync, openSync, readdirSync, realpathSync } from 'node:fs';
import { mkdir, rename, rm, writeFile } from 'node:fs/promises';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';
import { isValidVersion } from './lib/data-source-mode.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

// docs/cloudflare-setup.md: "Bucket | `classical-philosophy-reader-data`".
const DEFAULT_BUCKET = 'classical-philosophy-reader-data';

const DEFAULT_CONCURRENCY = 16;
// "Max 3 attempts" per request (the Sol review's wording): 1 initial try plus
// this many retries.
const DEFAULT_RETRIES = 2;
const DEFAULT_RETRY_DELAY_MS = 100;
const DEFAULT_TIMEOUT_MS = 60_000;

/**
 * Pure argument construction, unit-tested without ever invoking rclone.
 *
 * @param {string} version
 * @param {string | undefined} dest
 * @param {{ bucket?: string }} [opts]
 */
function buildFetchCommand(version, dest, opts = {}) {
  if (!version) throw new Error('fetch-release: version is required');
  const bucket = opts.bucket ?? process.env.READER_R2_BUCKET ?? DEFAULT_BUCKET;
  const destDir = dest ?? join('build', 'dist');
  return {
    command: 'rclone',
    args: ['copy', `r2:${bucket}/releases/${version}`, destDir, '--checksum'],
    bucket,
    destDir,
  };
}

function delay(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

// Only https: is allowed, except http: to localhost/127.0.0.1 -- the local
// server the test suite spins up, or a hand-run rehearsal against one.
function assertAllowedUrl(urlStr, context) {
  let u;
  try {
    u = new URL(urlStr);
  } catch (err) {
    throw new Error(`fetch-release: ${context} is not a valid URL: ${JSON.stringify(urlStr)} (${err.message})`);
  }
  const isLocalHttp = u.protocol === 'http:' && (u.hostname === 'localhost' || u.hostname === '127.0.0.1');
  if (u.protocol !== 'https:' && !isLocalHttp) {
    throw new Error(
      `fetch-release: ${context} must use https: (http: only to localhost/127.0.0.1, for tests), got ${JSON.stringify(urlStr)}`,
    );
  }
  return u;
}

// A safe relative POSIX path: no leading `/`, no `..` or `.` segment, no
// backslash, no empty segment, no NUL. RELEASE.json is data received over
// the network -- every path it lists is validated against this before any
// download starts, so a malicious or corrupted index can never write outside
// destDir. (`\` is rejected outright rather than treated as a separator: on
// POSIX it's just a normal filename character, and treating it as one here
// would only invite the Windows-path-semantics confusion that caused zip-
// slip-style bugs elsewhere.)
function assertSafeRelativePath(relPath) {
  if (typeof relPath !== 'string' || relPath.length === 0) {
    throw new Error(`fetch-release: RELEASE.json lists an unsafe path: ${JSON.stringify(relPath)}`);
  }
  if (relPath.includes('\0')) {
    throw new Error(`fetch-release: RELEASE.json lists a path containing NUL: ${JSON.stringify(relPath)}`);
  }
  if (relPath.includes('\\')) {
    throw new Error(`fetch-release: RELEASE.json lists a path containing a backslash: ${JSON.stringify(relPath)}`);
  }
  if (relPath.startsWith('/')) {
    throw new Error(`fetch-release: RELEASE.json lists an absolute path: ${JSON.stringify(relPath)}`);
  }
  for (const seg of relPath.split('/')) {
    if (seg === '' || seg === '.' || seg === '..') {
      throw new Error(
        `fetch-release: RELEASE.json lists an unsafe path segment ${JSON.stringify(seg)} in ${JSON.stringify(relPath)}`,
      );
    }
  }
}

// RELEASE.json is data received over the network -- every entry's size and
// sha256 are validated up front too, not just its path, before any download
// starts. Without this, a malformed or corrupted index could smuggle a
// negative, non-numeric, or absurd size past downloadFileWithRetry's size
// cap (which trusts expectedSize), or a bogus sha256 past verify-release.mjs's
// comparison.
function assertValidReleaseEntry(entry) {
  assertSafeRelativePath(entry.path);
  if (!Number.isSafeInteger(entry.size) || entry.size < 0) {
    throw new Error(
      `fetch-release: RELEASE.json entry ${JSON.stringify(entry.path)} has an invalid size: ${JSON.stringify(entry.size)}`,
    );
  }
  if (typeof entry.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(entry.sha256)) {
    throw new Error(
      `fetch-release: RELEASE.json entry ${JSON.stringify(entry.path)} has an invalid sha256: ${JSON.stringify(entry.sha256)}`,
    );
  }
}

// Refuses a destination directory that already has content. fetch-release
// assumes single-writer use (docs/release-from-dist.md): the destination
// must be a fresh folder -- empty or not yet existing -- that nothing else
// writes to for the duration of the fetch. A symlink among its top-level
// entries is reported with its own message (checked first, so it isn't
// reported as merely "not empty"); anything else present is refused
// generically.
function assertDestDirEmptyOrAbsent(destDir) {
  let entries;
  try {
    entries = readdirSync(destDir, { withFileTypes: true });
  } catch (err) {
    if (err.code === 'ENOENT') return;
    throw err;
  }
  for (const entry of entries) {
    if (entry.isSymbolicLink()) {
      throw new Error(`fetch-release: refusing a symlink inside the destination directory: ${join(destDir, entry.name)}`);
    }
  }
  if (entries.length > 0) {
    throw new Error(
      `fetch-release: destination directory is not empty: ${destDir} (fetch-release needs a fresh or empty destination)`,
    );
  }
}

// Refuses if `path` already exists and is a symlink -- a symlink there
// (planted by a previous run, or by anything else with write access to
// destDir) must never be silently followed. Non-existent paths pass, since
// there's nothing to refuse yet (and lstatSync -- unlike existsSync -- also
// catches a broken symlink, which existsSync would report as "doesn't
// exist").
function assertNotSymlink(path, context) {
  let st;
  try {
    st = lstatSync(path);
  } catch {
    return;
  }
  if (st.isSymbolicLink()) {
    throw new Error(`fetch-release: refusing to use a symlink as ${context}: ${path}`);
  }
}

// Walks every path component between destDirReal and dirname(destPath) that
// already exists, refusing if any of them is a symlink. destPath itself is
// always built from destDirReal plus already-validated (no ".."/absolute)
// segments, so it can never be lexically outside destDirReal -- this is the
// separate check for a symlink *inside* destDirReal that would make a
// filesystem write land somewhere else despite that.
function assertNoSymlinkInAncestry(destDirReal, destPath) {
  const rel = relative(destDirReal, dirname(destPath));
  if (rel === '' || rel.startsWith('..')) return;
  let current = destDirReal;
  for (const seg of rel.split(sep)) {
    current = join(current, seg);
    assertNotSymlink(current, `an intermediate directory (${current})`);
  }
}

// Final defense-in-depth: the resolved destPath must stay inside
// realpath(destDir). Given assertSafeRelativePath and the fact that destPath
// is always built by joining onto destDirReal, this can't actually fire --
// it's here because the Sol review named it as an explicit, separate check.
function assertInsideDestDir(destDirReal, destPath) {
  const resolved = resolve(destPath);
  if (resolved !== destDirReal && !resolved.startsWith(destDirReal + sep)) {
    throw new Error(`fetch-release: refusing to write outside destination: ${resolved}`);
  }
}

function isFatal(err) {
  return Boolean(err) && err.fatal === true;
}

// Retries `attempt` on non-fatal failure with exponential backoff, up to
// `retries` retries (so retries+1 attempts total). A fatal error (a 4xx, a
// cross-origin redirect, or a declared-size overrun -- anything that means
// "no" rather than "try again") is rethrown immediately, unretried.
async function withRetry(attempt, { retries, retryDelayMs, label }) {
  let n = 0;
  for (;;) {
    try {
      return await attempt();
    } catch (err) {
      if (isFatal(err)) throw err;
      if (n >= retries) {
        throw new Error(`fetch-release: ${label} failed after ${n + 1} attempt(s): ${err.message}`);
      }
      await delay(retryDelayMs * 2 ** n);
      n += 1;
    }
  }
}

// One GET with a request timeout, refusing a 4xx or ANY redirect outright
// (fatal, no retry) and a 5xx or network error non-fatally (the caller
// retries). Release paths are immutable and never legitimately redirect
// (docs/release-from-dist.md), so even a same-origin redirect is refused,
// not only a cross-origin one. `redirect: 'manual'` means the redirect is
// never followed, so no request reaches the redirect's target; where it
// pointed is not needed to refuse it.
async function fetchOnce(url, { fetchImpl, timeoutMs }) {
  let res;
  try {
    res = await fetchImpl(url, { redirect: 'manual', signal: AbortSignal.timeout(timeoutMs) });
  } catch (err) {
    throw new Error(`fetch-release: network error fetching ${url}: ${err.message}`);
  }
  if (res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400) || res.redirected) {
    const err = new Error(`fetch-release: refusing a redirect (release paths are immutable and never redirect): ${url}`);
    err.fatal = true;
    throw err;
  }
  if (res.status >= 500 && res.status < 600) {
    throw new Error(`fetch-release: ${url} returned ${res.status}`);
  }
  if (!res.ok) {
    const err = new Error(`fetch-release: ${url} returned ${res.status}`);
    err.fatal = true;
    throw err;
  }
  return res;
}

// GETs `url` into memory, retrying on network errors and 5xx responses.
// Used only for RELEASE.json itself, which has no declared size to stream
// against.
async function fetchBufferWithRetry(
  url,
  { retries = DEFAULT_RETRIES, retryDelayMs = DEFAULT_RETRY_DELAY_MS, timeoutMs = DEFAULT_TIMEOUT_MS, fetchImpl = fetch } = {},
) {
  return withRetry(
    async () => {
      const res = await fetchOnce(url, { fetchImpl, timeoutMs });
      try {
        return Buffer.from(await res.arrayBuffer());
      } catch (err) {
        throw new Error(`fetch-release: error reading body of ${url}: ${err.message}`);
      }
    },
    { retries, retryDelayMs, label: url },
  );
}

// Streams `url` to `${destPath}.part`, refusing (fatally, no retry) if more
// bytes arrive than `expectedSize` declares, then renames the temp file into
// place. verifyRelease still checks the final sha256/size once every file is
// down; this cap exists so a server that lies about a file's size can't run
// destDir out of disk or memory first.
async function downloadFileWithRetry(
  url,
  destPath,
  expectedSize,
  { retries = DEFAULT_RETRIES, retryDelayMs = DEFAULT_RETRY_DELAY_MS, timeoutMs = DEFAULT_TIMEOUT_MS, fetchImpl = fetch } = {},
) {
  const partPath = `${destPath}.part`;
  // Exclusive-create check, once, before any network activity or retry: an
  // existing file *or* symlink at partPath (planted by a previous run, or by
  // anything else with write access to destDir) is refused rather than
  // opened through. Having passed this once, every write attempt below
  // reuses that same, now-known-ours, temp file with a plain open -- a retry
  // after a transient failure must be able to reopen and overwrite its own
  // partial file, not fail with EEXIST against itself.
  try {
    closeSync(openSync(partPath, 'wx'));
  } catch (err) {
    if (err.code === 'EEXIST') {
      throw new Error(`fetch-release: refusing to use an existing file (possibly a symlink) as a download temp file: ${partPath}`);
    }
    throw err;
  }
  try {
    await withRetry(
      async () => {
        const res = await fetchOnce(url, { fetchImpl, timeoutMs });
        if (!res.body) {
          throw new Error(`fetch-release: ${url} returned no body`);
        }
        let seen = 0;
        try {
          await pipeline(
            Readable.fromWeb(res.body),
            // eslint-disable-next-line func-names -- pipeline calls this with the source stream
            async function* capSize(source) {
              for await (const chunk of source) {
                seen += chunk.length;
                if (seen > expectedSize) {
                  const overrun = new Error(`fetch-release: ${url} exceeded its declared size (${expectedSize} bytes)`);
                  overrun.fatal = true;
                  throw overrun;
                }
                yield chunk;
              }
            },
            createWriteStream(partPath),
          );
        } catch (err) {
          if (isFatal(err)) throw err;
          throw new Error(`fetch-release: error downloading ${url}: ${err.message}`);
        }
      },
      { retries, retryDelayMs, label: url },
    );
    // Inside the same cleanup scope as the download itself: a failed rename
    // (e.g. destPath already exists as a non-empty directory) must remove
    // the .part temp file too, not just a failed download.
    await rename(partPath, destPath);
  } catch (err) {
    await rm(partPath, { force: true }).catch(() => {});
    throw err;
  }
}

/**
 * Fetches a release over HTTPS GETs: `<baseUrl>/<version>/RELEASE.json`
 * first, then every file it lists, with bounded concurrency, into `destDir`.
 * Verifies the result against RELEASE.json (verify-release.mjs) before
 * resolving -- a size/sha256 mismatch or a missing file throws, same as a
 * refused 4xx during download.
 *
 * @param {{ version: string, destDir: string, baseUrl: string, concurrency?: number, retries?: number, retryDelayMs?: number, timeoutMs?: number, fetchImpl?: typeof fetch }} opts
 */
async function fetchReleaseFromUrl({
  version,
  destDir,
  baseUrl,
  concurrency = DEFAULT_CONCURRENCY,
  retries = DEFAULT_RETRIES,
  retryDelayMs = DEFAULT_RETRY_DELAY_MS,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  fetchImpl = fetch,
}) {
  if (!version) throw new Error('fetch-release: version is required');
  if (!isValidVersion(version)) {
    throw new Error(`fetch-release: version ${JSON.stringify(version)} is not a valid release version`);
  }
  if (!baseUrl) throw new Error('fetch-release: --from-url requires a base URL');
  if (!destDir) throw new Error('fetch-release: dest is required');

  const base = baseUrl.replace(/\/+$/, '');
  assertAllowedUrl(base, '--from-url base URL');

  assertNotSymlink(destDir, 'the destination directory');
  assertDestDirEmptyOrAbsent(destDir);
  await mkdir(destDir, { recursive: true });
  // Everything after this point is built from the *real* path, not the
  // caller's possibly-symlinked-ancestor string -- see assertInsideDestDir.
  const destDirReal = realpathSync(destDir);

  const retryOpts = { retries, retryDelayMs, timeoutMs, fetchImpl };
  const releaseUrl = `${base}/${encodeURIComponent(version)}/RELEASE.json`;
  const releaseBuf = await fetchBufferWithRetry(releaseUrl, retryOpts);
  // Exclusive create: the dest-dir check above means nothing should already
  // be there, but this is the same defense-in-depth as downloadFileWithRetry's
  // temp files -- refuse rather than follow a symlink or overwrite a file.
  await writeFile(join(destDirReal, 'RELEASE.json'), releaseBuf, { flag: 'wx' });

  let index;
  try {
    index = JSON.parse(releaseBuf.toString('utf8'));
  } catch (err) {
    throw new Error(`fetch-release: RELEASE.json at ${releaseUrl} is not valid JSON: ${err.message}`);
  }

  const files = index.files ?? [];
  // Validate every listed path, size, and sha256 before downloading anything.
  for (const entry of files) {
    assertValidReleaseEntry(entry);
  }

  const queue = files.slice();
  const state = { fatalError: null };
  let totalBytes = 0;

  async function worker() {
    for (;;) {
      if (state.fatalError) return;
      const entry = queue.shift();
      if (!entry) return;
      const segments = entry.path.split('/');
      const destPath = join(destDirReal, ...segments);
      try {
        assertNoSymlinkInAncestry(destDirReal, destPath);
        assertInsideDestDir(destDirReal, destPath);
        await mkdir(dirname(destPath), { recursive: true });
        const fileUrl = `${base}/${encodeURIComponent(version)}/${segments.map(encodeURIComponent).join('/')}`;
        await downloadFileWithRetry(fileUrl, destPath, entry.size, retryOpts);
        totalBytes += entry.size;
      } catch (err) {
        if (!state.fatalError) state.fatalError = err;
        return;
      }
    }
  }

  const workerCount = Math.max(1, Math.min(concurrency, files.length || 1));
  // Every worker settles (each returns on its own fatalError check, never
  // interrupted mid-download) before we look at state.fatalError -- so no
  // write happens after this function decides to reject.
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  if (state.fatalError) throw state.fatalError;

  console.log(`fetch-release: downloaded ${files.length} files (${totalBytes} bytes) from ${base}/${version}`);
  console.log('fetch-release: verifying downloaded release');
  const { verifyRelease } = await import('./verify-release.mjs');
  const { ok, problems } = verifyRelease(destDirReal);
  if (!ok) {
    for (const p of problems.slice(0, 20)) console.error(`  FAIL: ${p}`);
    throw new Error(`fetch-release: downloaded release at ${destDirReal} failed verification`);
  }
  console.log(`fetch-release: OK -- ${destDirReal} matches RELEASE.json`);
  return { ok: true, fileCount: files.length, totalBytes };
}

function usage(message) {
  if (message) console.error(message);
  console.error('Usage: node scripts/fetch-release.mjs <version> [dest]');
  console.error('       node scripts/fetch-release.mjs <version> [dest] --from-url <base>');
  process.exit(2);
}

// Splits argv into positionals (version, dest) and the --from-url value,
// tolerating the flag in any position.
function parseArgs(argv) {
  const positionals = [];
  let fromUrl;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--from-url') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) throw new Error('--from-url requires a base URL argument');
      fromUrl = value;
      i += 1;
    } else if (arg.startsWith('--from-url=')) {
      fromUrl = arg.slice('--from-url='.length);
      if (!fromUrl) throw new Error('--from-url requires a base URL argument');
    } else {
      positionals.push(arg);
    }
  }
  const [version, dest] = positionals;
  return { version, dest, fromUrl };
}

async function main() {
  let version, dest, fromUrl;
  try {
    ({ version, dest, fromUrl } = parseArgs(process.argv.slice(2)));
  } catch (err) {
    usage(err.message);
    return;
  }
  if (!version) usage('Missing <version>.');
  const destDir = dest ?? join('build', 'dist');

  if (fromUrl) {
    const resolvedDest = resolve(destDir);
    console.log(`fetch-release: GET ${fromUrl}/${version}/RELEASE.json (and every file it lists) -> ${resolvedDest}`);
    await fetchReleaseFromUrl({ version, destDir: resolvedDest, baseUrl: fromUrl });
    return;
  }

  const { command, args, destDir: rcloneDest } = buildFetchCommand(version, dest);

  console.log(`fetch-release: ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with status ${result.status}`);
  }

  console.log('\nfetch-release: verifying downloaded release');
  const { verifyRelease } = await import('./verify-release.mjs');
  const resolvedDest = resolve(rcloneDest);
  const { ok, problems } = verifyRelease(resolvedDest);
  if (!ok) {
    for (const p of problems.slice(0, 20)) console.error(`  FAIL: ${p}`);
    throw new Error(`fetch-release: downloaded release at ${resolvedDest} failed verification`);
  }
  console.log(`fetch-release: OK -- ${resolvedDest} matches RELEASE.json`);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}

export { assertSafeRelativePath, buildFetchCommand, DEFAULT_BUCKET, downloadFileWithRetry, fetchReleaseFromUrl };
