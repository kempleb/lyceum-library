#!/usr/bin/env node
// P2 Stage 0 byte-diff harness (docs/p2-plan.md §4-5), v2. Whitelists nothing.
//
// Unit under test: `cd app && npm run build` at a fixed build/dist (the
// corpus data directory app/public/data symlinks to) -- NOT build:public,
// which is the full pipeline and is unchanged across P2 stages 0-4.
//
// v1 bug (found by --self-check): comparing a worktree-built "baseline"
// against an in-place-built "current" is confounded -- esbuild/Vite's
// minifier allocates identifier names partly from the absolute build path,
// so building the SAME commit from two different absolute paths (a /tmp
// worktree vs the repo's own path) permutes minified identifiers in the
// largest shared chunks and cascades into every HTML file that references
// them. That is a harness artifact, not a build-determinism finding.
//
// v2 fix: BOTH sides are commit-ish refs, and BOTH are materialized into a
// git worktree at the SAME fixed absolute path (WORKTREE_PATH below),
// SEQUENTIALLY -- side A is checked out, built, copied out, and the
// worktree is torn down; only then is side B checked out at the identical
// path, built, and copied out. Neither side is ever built in place in the
// real repo. The fixed path (not a fresh tmpdir per run) is deliberate: it
// keeps the path-dependent parts of the build (if any remain) constant
// across stages, so a byte-stability gate from Stage 1 is comparable to one
// from Stage 3.
//
// Two builds are compared:
//   - "baseline": --ref (required), checked out into the scratch worktree.
//   - "current":  --ref2 if given, else `git stash create` (captures
//     tracked modifications AND staged new files without touching history
//     or the working tree); if the tree is clean (`git stash create`
//     prints nothing), falls back to HEAD.
//     IMPORTANT: `git stash create` does NOT see untracked new files unless
//     they are staged (`git add`) first -- an uncommitted new file that
//     hasn't been `git add`ed is invisible to this harness's default
//     "current" side. Stage new files before running without --ref2.
// --self-check pins baseline == current == HEAD (both --ref and --ref2, if
// passed, must resolve to HEAD) and runs the identical materialize-build
// cycle twice at the identical path, proving the whole instrument --
// worktree materialization included -- is byte-reproducible before any P2
// code change is trusted against it.
//
// Procedure (binding, see docs/p2-plan.md §4):
//   1. Fingerprint the corpus-input directory (build/dist, in the real
//      repo -- never touched by worktree add/remove) before each side's
//      build; require equality across the whole run -- a diagnostic
//      precondition, never a whitelist. If it fails, something wrote to
//      build/dist mid-run; that is a false diff, not a build-determinism
//      finding.
//   2. Each side via `git worktree add --detach WORKTREE_PATH <sha>`, with
//      two mandatory symlinks: <WORKTREE_PATH>/build -> repo build/,
//      <WORKTREE_PATH>/app/node_modules -> repo app/node_modules. Never
//      `npm ci` in the worktree -- a fresh install would itself change the
//      bundler output. The worktree is removed (`git worktree remove
//      --force`) before the next side is added, and defensively before add,
//      in case a prior crashed run left it registered.
//   3. Assert <WORKTREE_PATH>/app/public/data/meditations/manifest.json
//      exists before building each side -- a broken symlink chain here
//      produces a silent false "0 diffs" (zero corpus data on both sides).
//   4. Pinned env both sides: PUBLIC_SHOW_PRIVATE / PUBLIC_READER_FIXTURES /
//      PUBLIC_SITE_ORIGIN unset, TZ=UTC, LC_ALL=C.
//   5. Compare path sets + per-file sha256 (scripts/lib/dist-fingerprint.mjs).
//      Report every differing path; unified diff for the first 3 differing
//      HTML files; byte-length delta + first differing offset for
//      differing _astro/*.js chunks.
//   6. Exit non-zero on any diff. Clean up the worktree even on failure.
import { existsSync, mkdirSync, symlinkSync, cpSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { fingerprintDir } from './lib/dist-fingerprint.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

// Fixed constant path, reused every run and every side -- see header. Not a
// fresh tmpdir: the whole point is that both sides (and every stage's run)
// build from the identical absolute path.
const WORKTREE_PATH = '/private/tmp/p2-bytestab-tree';

function parseArgs(argv) {
  const args = { ref: null, ref2: null, selfCheck: false, out: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--ref') args.ref = argv[++i];
    else if (a === '--ref2') args.ref2 = argv[++i];
    else if (a === '--self-check') args.selfCheck = true;
    else if (a === '--out') args.out = argv[++i];
    else throw new Error(`Unknown argument: ${a}`);
  }
  return args;
}

function run(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, {
    cwd: options.cwd ?? ROOT,
    env: options.env ?? process.env,
    stdio: options.stdio ?? 'inherit',
    encoding: 'utf8',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(
      `${cmd} ${args.join(' ')} failed with status ${result.status}${options.cwd ? ` (cwd ${options.cwd})` : ''}`,
    );
  }
  return result;
}

function capture(cmd, args, options = {}) {
  const result = run(cmd, args, { ...options, stdio: ['ignore', 'pipe', 'pipe'] });
  return result.stdout.trim();
}

function resolveSha(ref) {
  return capture('git', ['rev-parse', ref], { cwd: ROOT });
}

// `git stash create` builds a stash commit from tracked modifications AND
// staged new files, WITHOUT touching the index, the working tree, or the
// stash ref-list -- it is side-effect-free, unlike `git stash push`. Prints
// nothing (empty stdout) when the tree has nothing to stash.
function stashCreateSha() {
  const result = spawnSync('git', ['stash', 'create'], {
    cwd: ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`git stash create failed with status ${result.status}: ${result.stderr}`);
  }
  return result.stdout.trim(); // '' when the tree is clean
}

// PUBLIC_SHOW_PRIVATE / PUBLIC_READER_FIXTURES / PUBLIC_SITE_ORIGIN / PUBLIC_WING
// / PUBLIC_LYCEUM_CHROME must be genuinely UNSET, not empty string:
// astro.config.mjs and works.ts branch on presence, not truthiness.
// PUBLIC_WING (P6 wing-standalone mode) scopes WORKS/AUTHORS to one corpus,
// so a stray value left in the shell environment would silently narrow this
// script's baseline build too. PUBLIC_LYCEUM_CHROME (ReaderShell.astro's
// Lyceum reader chrome toggle) changes rendered HTML the same way -- a stray
// value would silently alter chrome markup on only one side of the diff.
function pinnedEnv() {
  const env = { ...process.env };
  delete env.PUBLIC_SHOW_PRIVATE;
  delete env.PUBLIC_READER_FIXTURES;
  delete env.PUBLIC_SITE_ORIGIN;
  delete env.PUBLIC_WING;
  delete env.PUBLIC_LYCEUM_CHROME;
  env.TZ = 'UTC';
  env.LC_ALL = 'C';
  return env;
}

function buildDist(appDir, label) {
  console.log(`\n[verify-byte-stability] building ${label} (cd ${appDir} && npm run build)...`);
  run('npm', ['run', 'build'], { cwd: appDir, env: pinnedEnv() });
  const dist = join(appDir, 'dist');
  if (!existsSync(dist)) throw new Error(`${label} build did not produce ${dist}`);
  return dist;
}

function corpusFingerprint() {
  const dataDir = join(ROOT, 'build', 'dist');
  if (!existsSync(dataDir)) {
    throw new Error(`Corpus data missing: ${dataDir} does not exist. Build it (build:public) first.`);
  }
  return fingerprintDir(dataDir);
}

function assertCorpusDataInWorktree(appDir) {
  const marker = join(appDir, 'public', 'data', 'meditations', 'manifest.json');
  if (!existsSync(marker)) {
    throw new Error(
      `Worktree corpus data missing: ${marker} does not exist. This means the ` +
        `<worktree>/build or app/public/data symlink chain is broken -- left unchecked this ` +
        `produces a silent false "0 diffs" (both builds would see zero corpus data).`,
    );
  }
}

function unifiedDiff(pathA, pathB) {
  const result = spawnSync('diff', ['-u', pathA, pathB], { encoding: 'utf8' });
  return result.stdout || '(diff produced no textual output -- binary or identical after all)';
}

function firstDifferingOffset(bufA, bufB) {
  const len = Math.min(bufA.length, bufB.length);
  for (let i = 0; i < len; i++) {
    if (bufA[i] !== bufB[i]) return i;
  }
  return len; // one buffer is a strict prefix of the other
}

function isAstroChunk(relPath) {
  return relPath.endsWith('.js') && relPath.includes('_astro/');
}

// Best-effort teardown of any worktree registration/directory left at
// WORKTREE_PATH by a prior crashed run. Safe to call when nothing is there.
function forceCleanWorktreePath() {
  spawnSync('git', ['worktree', 'remove', '--force', WORKTREE_PATH], { cwd: ROOT, stdio: 'ignore' });
  spawnSync('git', ['worktree', 'prune'], { cwd: ROOT, stdio: 'ignore' });
  if (existsSync(WORKTREE_PATH)) {
    rmSync(WORKTREE_PATH, { recursive: true, force: true });
  }
}

// Materialize `sha` at the fixed WORKTREE_PATH, build it, copy the dist out
// to <outDir>/<label>-dist, and tear the worktree down again -- always,
// even on failure, so the fixed path is free for the next side.
function materializeAndBuild(sha, label, outDir) {
  console.log(`\n[verify-byte-stability] materializing ${label} (${sha}) at ${WORKTREE_PATH}...`);
  forceCleanWorktreePath();
  run('git', ['worktree', 'add', '--detach', WORKTREE_PATH, sha], { cwd: ROOT });
  try {
    symlinkSync(join(ROOT, 'build'), join(WORKTREE_PATH, 'build'), 'dir');
    symlinkSync(join(ROOT, 'app', 'node_modules'), join(WORKTREE_PATH, 'app', 'node_modules'), 'dir');
    assertCorpusDataInWorktree(join(WORKTREE_PATH, 'app'));

    const dist = buildDist(join(WORKTREE_PATH, 'app'), label);
    const distOut = join(outDir, `${label}-dist`);
    cpSync(dist, distOut, { recursive: true, dereference: true });
    return distOut;
  } finally {
    const removed = spawnSync('git', ['worktree', 'remove', '--force', WORKTREE_PATH], {
      cwd: ROOT,
      stdio: 'inherit',
    });
    if (removed.status !== 0) {
      console.error(
        `[verify-byte-stability] WARNING: git worktree remove --force failed for ${WORKTREE_PATH}; cleaning up manually.`,
      );
      try {
        rmSync(WORKTREE_PATH, { recursive: true, force: true });
      } catch {
        // best-effort
      }
      spawnSync('git', ['worktree', 'prune'], { cwd: ROOT, stdio: 'inherit' });
    }
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));

  const head = resolveSha('HEAD');

  let refA; // baseline
  let refB; // current
  if (args.selfCheck) {
    refA = args.ref ? resolveSha(args.ref) : head;
    if (refA !== head) {
      throw new Error(
        `--self-check requires the baseline ref to equal current HEAD ` +
          `(--ref resolved to ${refA}, HEAD is ${head}).`,
      );
    }
    refB = args.ref2 ? resolveSha(args.ref2) : head;
    if (refB !== head) {
      throw new Error(
        `--self-check requires the second ref to equal current HEAD ` +
          `(--ref2 resolved to ${refB}, HEAD is ${head}).`,
      );
    }
  } else {
    if (!args.ref) throw new Error('--ref <git-ref> is required unless --self-check is passed.');
    refA = resolveSha(args.ref);
    if (args.ref2) {
      refB = resolveSha(args.ref2);
    } else {
      const stashSha = stashCreateSha();
      refB = stashSha || head;
      console.log(
        stashSha
          ? `[verify-byte-stability] --ref2 not given: using git stash create -> ${refB}`
          : `[verify-byte-stability] --ref2 not given, tree is clean (git stash create was empty): using HEAD -> ${refB}`,
      );
    }
  }

  const outDir = args.out ? resolve(args.out) : join(tmpdir(), `byte-stability-${Date.now()}`);
  mkdirSync(outDir, { recursive: true });

  console.log(`[verify-byte-stability] mode: ${args.selfCheck ? 'self-check' : 'ref-diff'}`);
  console.log(`[verify-byte-stability] baseline ref: ${refA}`);
  console.log(`[verify-byte-stability] current ref:  ${refB}`);
  console.log(`[verify-byte-stability] worktree path: ${WORKTREE_PATH} (fixed, reused sequentially)`);
  console.log(`[verify-byte-stability] out dir: ${outDir}`);

  try {
    // --- Corpus-input fingerprint precondition (before side A build) ------
    const corpusFpBefore = corpusFingerprint();

    // --- Side A: baseline, sequentially materialized + built + torn down --
    const baselineDistOut = materializeAndBuild(refA, 'baseline', outDir);

    // --- Corpus-input fingerprint precondition (before side B build) ------
    const corpusFpAfter = corpusFingerprint();
    if (corpusFpBefore.digest !== corpusFpAfter.digest) {
      throw new Error(
        `Corpus input (build/dist) changed between the two builds -- this is a build/dist ` +
          `mutation mid-run (another pipeline/build process?), not a build-determinism finding. ` +
          `Before: ${corpusFpBefore.digest} (${corpusFpBefore.fileCount} files); ` +
          `after: ${corpusFpAfter.digest} (${corpusFpAfter.fileCount} files).`,
      );
    }

    // --- Side B: current, materialized at the SAME fixed path -------------
    const currentDistOut = materializeAndBuild(refB, 'current', outDir);

    // --- Compare ------------------------------------------------------------
    const baselineFp = fingerprintDir(baselineDistOut, { includeFiles: true });
    const currentFp = fingerprintDir(currentDistOut, { includeFiles: true });

    const baselinePaths = new Set(Object.keys(baselineFp.files));
    const currentPaths = new Set(Object.keys(currentFp.files));

    const onlyInBaseline = [...baselinePaths].filter((p) => !currentPaths.has(p)).sort();
    const onlyInCurrent = [...currentPaths].filter((p) => !baselinePaths.has(p)).sort();
    const differing = [...baselinePaths]
      .filter((p) => currentPaths.has(p) && baselineFp.files[p] !== currentFp.files[p])
      .sort();

    const totalFiles = currentPaths.size;
    const problems = onlyInBaseline.length + onlyInCurrent.length + differing.length;

    if (problems === 0) {
      console.log(`\n[verify-byte-stability] RESULT: 0 differing files of ${totalFiles}`);
      console.log(`[verify-byte-stability] baseline tree digest: ${baselineFp.digest}`);
      console.log(`[verify-byte-stability] current tree digest:  ${currentFp.digest}`);
      return 0;
    }

    console.log(`\n[verify-byte-stability] RESULT: ${problems} differing files of ${totalFiles}`);
    if (onlyInBaseline.length) {
      console.log(`\nPaths only in baseline (${onlyInBaseline.length}):`);
      for (const p of onlyInBaseline) console.log(`  - ${p}`);
    }
    if (onlyInCurrent.length) {
      console.log(`\nPaths only in current (${onlyInCurrent.length}):`);
      for (const p of onlyInCurrent) console.log(`  + ${p}`);
    }
    if (differing.length) {
      console.log(`\nPaths with differing content (${differing.length}):`);
      for (const p of differing) console.log(`  * ${p}`);

      let htmlShown = 0;
      for (const p of differing) {
        const a = join(baselineDistOut, p);
        const b = join(currentDistOut, p);
        if (p.endsWith('.html') && htmlShown < 3) {
          htmlShown++;
          console.log(`\n--- unified diff: ${p} ---`);
          console.log(unifiedDiff(a, b));
        } else if (isAstroChunk(p)) {
          const bufA = readFileSync(a);
          const bufB = readFileSync(b);
          const offset = firstDifferingOffset(bufA, bufB);
          console.log(
            `\n--- ${p}: length ${bufA.length} -> ${bufB.length} ` +
              `(delta ${bufB.length - bufA.length}), first differing byte offset ${offset} ---`,
          );
        }
      }
    }
    return 1;
  } finally {
    // Defensive: materializeAndBuild already tears its own worktree down in
    // its own finally, but if something throws between calls (e.g. the
    // corpus-fingerprint check) before a second materialize even starts,
    // make sure nothing is left registered at the fixed path.
    forceCleanWorktreePath();
  }
}

process.exit(main());
