import { cpSync, existsSync, lstatSync, readFileSync, readdirSync, realpathSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

import { parseFromDistArg, planReleaseCopy, planStages } from './lib/build-stages.mjs';
import { childEnvFor, resolveDataSourceMode } from './lib/data-source-mode.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const MANIFESTS = join(ROOT, 'manifests');
const DIST_DIR = join(ROOT, 'build', 'dist');

// PUBLIC_DATA_ROOT and DATA_FROM_BUCKET are mutually exclusive -- fail fast,
// before any real work starts, rather than partway through a multi-minute
// build. See scripts/lib/data-source-mode.mjs and docs/cloudflare-setup.md's
// bucket-mode section.
let DATA_SOURCE;
try {
  DATA_SOURCE = resolveDataSourceMode(process.env);
} catch (err) {
  console.error(err.message);
  process.exit(1);
}

// --from-dist <dir> (or env READER_RELEASE_DIR): build the site from one
// prior full build's build/dist -- a "release" -- instead of running the
// text pipeline. See docs/release-from-dist.md and
// docs/lyceum-shared-repo-plan.md §4/§6 (Brian's brief requires this: a
// fresh checkout plus one approved release artifact must build with no
// TLG/PHI, no pipeline run, and no sibling repo).
let FROM_DIST_ARG;
try {
  FROM_DIST_ARG = parseFromDistArg(process.argv.slice(2), process.env);
} catch (err) {
  console.error(err.message);
  process.exit(1);
}
const FROM_DIST = FROM_DIST_ARG ? resolve(FROM_DIST_ARG) : null;
const STAGES = Object.fromEntries(planStages({ fromDist: !!FROM_DIST }).map((s) => [s.name, s]));

let CORPUS_VERSION;
// Full mode only: the raw <short commit>-YYYY-MM-DD stamp handed to every
// reader_pipeline / mount-corpus.mjs run as CORPUS_VERSION (stage7_emit.py's
// os.environ.get("CORPUS_VERSION", "dev") -- unchanged by this fix). This is
// NOT the release's public identity; scripts/emit-lyceum-manifest.mjs's
// reorderCorpusVersion() reformats it, per work, into the build version
// docs/lyceum-shared-repo-plan.md §6 documents (`YYYY.MM.DD-<short commit>`)
// -- the one that ends up in manifests/index.json and (via
// release-index.mjs's readCorpusVersion, which prefers that file) in
// RELEASE.json. CORPUS_VERSION below is derived with that same reorder
// function, from this same seed, right here -- before the pipeline runs --
// so the bucket data root agrees with RELEASE.json by construction instead
// of by the two independently landing on the same string. See the "one
// stamp" note in docs/cloudflare-setup.md's bucket-mode section (added with
// this fix, 2026-09-22).
let PIPELINE_CORPUS_VERSION;
// Bucket mode's data root, resolved once CORPUS_VERSION is known below --
// `/data/<CORPUS_VERSION>`, or undefined for same-origin/off-origin modes
// (off-origin already has its root in DATA_SOURCE.dataRoot). Validated and
// computed here, right after CORPUS_VERSION exists and before any expensive
// pipeline stage runs, so a computed version that can't be a valid URL path
// segment fails the build immediately with a clear message rather than
// partway through a multi-minute run.
let BUCKET_DATA_ROOT;
if (FROM_DIST) {
  // Read the version straight from the SOURCE release's own RELEASE.json,
  // and -- in bucket mode -- validate it against the /data/<version>/
  // route's rule, BEFORE touching build/dist at all. Validating only after
  // the copy meant a version that could never be served still cost a full
  // delete-and-replace of build/dist first.
  const { fromDistCorpusVersion } = await import('./release-index.mjs');
  let sourceVersion;
  try {
    sourceVersion = fromDistCorpusVersion(FROM_DIST);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  if (DATA_SOURCE.mode === 'bucket') {
    try {
      DATA_SOURCE.dataRootFor(sourceVersion);
    } catch (err) {
      console.error(err.message);
      process.exit(1);
    }
  }

  // Copy the release into place (removing any existing build/dist -- an old
  // LOCAL build, safe to discard -- before the copy, never after). A no-op
  // when the caller already points --from-dist at build/dist itself.
  // Compare real paths: a case variant (macOS) or a symlink alias of
  // build/dist must not slip past the overlap guard and get deleted below.
  const realFrom = existsSync(FROM_DIST) ? realpathSync.native(FROM_DIST) : FROM_DIST;
  const realDist = existsSync(DIST_DIR) ? realpathSync.native(DIST_DIR) : DIST_DIR;
  const copyPlan = planReleaseCopy(realFrom, realDist);
  if (copyPlan === 'copy') {
    console.log(`\nCopying release from ${FROM_DIST} to build/dist`);
    rmSync(DIST_DIR, { recursive: true, force: true });
    cpSync(FROM_DIST, DIST_DIR, { recursive: true });
  }

  // Verify the copy against its own RELEASE.json before doing anything else.
  const { verifyRelease } = await import('./verify-release.mjs');
  const releaseCheck = verifyRelease(DIST_DIR);
  if (!releaseCheck.ok) {
    console.error(`release verification failed for build/dist (copied from ${FROM_DIST}):`);
    for (const p of releaseCheck.problems.slice(0, 3)) console.error(`  FAIL: ${p}`);
    process.exit(1);
  }

  // Held-corpus guard (docs/todo/plato-mount.md, GPT-6 Sol code review item 1
  // -- BLOCKER): a corpus on hold (mount.yaml hold: true, e.g. Plato) must
  // not resurface through a --from-dist rebuild of a release that carries it
  // -- the same READER_INCLUDE_HELD=1 override mount-corpus.mjs's own
  // shouldSkipForHold honors is required here too, so a local held-on test
  // build still works end to end; without it, this refuses.
  const { findHeldWorksInDist, formatHeldWorksFindings, shouldRefuseForHeld } = await import('./lib/held-works.mjs');
  const heldFindings = await findHeldWorksInDist(DIST_DIR, { root: ROOT });
  if (shouldRefuseForHeld(heldFindings, process.env)) {
    console.error(`build-public: refusing --from-dist: ${heldFindings.length} held work(s) present in build/dist:`);
    console.error(formatHeldWorksFindings(heldFindings));
    console.error('set READER_INCLUDE_HELD=1 to build with them anyway (a local test build only).');
    process.exit(1);
  }

  // corpus_version: read from the release's own RELEASE.json directly
  // (fromDistCorpusVersion, not readCorpusVersion's manifests/index.json-or-
  // work-manifest fallback -- see that function's comment in
  // release-index.mjs), never from git (stage 0 no longer calls git in
  // --from-dist mode). Same value as sourceVersion above; DIST_DIR is FROM_DIST's
  // copy at this point, so re-reading it here (rather than reusing
  // sourceVersion) keeps this line correct even if FROM_DIST and DIST_DIR
  // ever diverge before this point.
  CORPUS_VERSION = fromDistCorpusVersion(DIST_DIR);

  // producer_commit for the banner comes from RELEASE.json (the release
  // index written by release-index.mjs, item 2 of the task brief).
  const releaseMeta = JSON.parse(readFileSync(join(DIST_DIR, 'RELEASE.json'), 'utf8'));
  console.log(
    `\nbuild-public: mode=from-dist release-dir=${FROM_DIST} ` +
      `corpus-version=${CORPUS_VERSION} producer-commit=${releaseMeta.producer_commit}`,
  );
} else {
  const gitVersion = spawnSync('git', ['rev-parse', '--short', 'HEAD'], {
    cwd: ROOT,
    encoding: 'utf8',
  });
  if (gitVersion.error) throw gitVersion.error;
  if (gitVersion.status !== 0 || !gitVersion.stdout.trim()) {
    throw new Error('git rev-parse --short HEAD failed while setting CORPUS_VERSION');
  }
  PIPELINE_CORPUS_VERSION = `${gitVersion.stdout.trim()}-${new Date().toISOString().slice(0, 10)}`;
  const { reorderCorpusVersion } = await import('./emit-lyceum-manifest.mjs');
  CORPUS_VERSION = reorderCorpusVersion(PIPELINE_CORPUS_VERSION);
  if (!CORPUS_VERSION) {
    throw new Error(
      `could not derive a release corpus_version from pipeline stamp ${JSON.stringify(PIPELINE_CORPUS_VERSION)}`,
    );
  }
  console.log(
    `\nbuild-public: mode=full corpus-version=${CORPUS_VERSION} (pipeline stamp ${PIPELINE_CORPUS_VERSION})`,
  );
}

if (DATA_SOURCE.mode === 'bucket') {
  try {
    BUCKET_DATA_ROOT = DATA_SOURCE.dataRootFor(CORPUS_VERSION);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  console.log(`  bucket mode: data root will be ${BUCKET_DATA_ROOT} (R2 key prefix releases/${CORPUS_VERSION}/)`);
}

// The PUBLIC_DATA_ROOT env every child process that reads it needs, resolved
// once here (scripts/lib/data-source-mode.mjs's childEnvFor) and spread into
// each relevant child's env below, rather than special-casing call sites --
// empty in same-origin mode, the off-origin URL as-is, or bucket mode's own
// /data/<CORPUS_VERSION> path.
const DATA_ROOT_ENV = childEnvFor(DATA_SOURCE, CORPUS_VERSION);

console.log('Stage plan:');
for (const stage of Object.values(STAGES)) {
  const mode = stage.mode ? ` (${stage.mode})` : '';
  console.log(`  ${stage.enabled ? 'RUN    ' : 'SKIP   '} ${stage.name}${mode}`);
}

// uv is not installed on this machine (post-wipe); the pipeline runs from its
// checked-out venv. Override with READER_PY if the interpreter lives elsewhere.
const PY = process.env.READER_PY ?? join(dirname(fileURLToPath(import.meta.url)), '..', 'pipeline', '.venv', 'bin', 'python');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? ROOT,
    env: { ...process.env, ...(options.env ?? {}) },
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} failed with status ${result.status}`);
  }
}

function dataDirProblem(path) {
  try {
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) {
      return existsSync(path) ? null : 'data not built yet: build/dist is a dangling symlink';
    }
    if (!stat.isDirectory()) {
      return 'data not built yet: build/dist exists but is not a directory';
    }
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return 'data not built yet: build/dist does not exist';
    }
    throw error;
  }
  return null;
}

const works = readdirSync(MANIFESTS)
  // authors.yaml is the corpus author roster (P2), not a work manifest.
  .filter((name) => name.endsWith('.yaml') && !name.endsWith('-public.yaml') && name !== 'authors.yaml')
  .map((name) => name.slice(0, -'.yaml'.length))
  .sort((a, b) => a.localeCompare(b));

const publicWorks = new Set(
  readdirSync(MANIFESTS)
    .filter((name) => name.endsWith('-public.yaml'))
    .map((name) => name.slice(0, -'-public.yaml'.length)),
);

// Moved ahead of its original spot (just before the Astro build) so the
// translation-seam gate below — which borrows app/'s esbuild + js-yaml —
// has them available even on a from-scratch checkout with no app/node_modules
// yet; a no-op on every other run (the directory already exists).
if (!existsSync(join(ROOT, 'app', 'node_modules'))) {
  console.log('Installing app dependencies');
  run('npm', ['ci'], { cwd: join(ROOT, 'app') });
}

// Hard gate: each manifest's duplicated registry block must agree with its
// pipeline fields. This reads YAML only, so it runs before the corpus build.
console.log('\nChecking manifest <-> registry agreement');
const { checkRegistryAgreement } = await import('./check-registry-agreement.mjs');
const { checked, agreed, problems } = await checkRegistryAgreement();
console.log(`  ${agreed}/${checked} work(s) agree, ${problems.length} problem(s)`);
if (problems.length) {
  for (const p of problems) console.error(`  ${p}`);
  process.exit(1);
}

console.log('\nVerifying sources/INVENTORY.md SHA-256 declarations');
const { verifyInventoryHashes } = await import('./verify-inventory-hashes.mjs');
const inv = verifyInventoryHashes();
for (const w of inv.warnings) console.warn(`  warning: ${w}`);
console.log(`  ${inv.verified} hash(es) verified, ${inv.problems.length} problem(s)`);
if (inv.problems.length) {
  for (const p of inv.problems) console.error(`  ${p}`);
  process.exit(1);
}
if (inv.verified <= 20) {
  console.error(`  FAIL: verified count ${inv.verified} is not > 20`);
  process.exit(1);
}

console.log('\nCleaning generated public build output');
if (STAGES['clean-dist'].enabled) {
  rmSync(DIST_DIR, { recursive: true, force: true });
}
rmSync(join(ROOT, 'app', 'dist'), { recursive: true, force: true });

if (STAGES['pipeline-per-work'].enabled) {
  for (const work of works) {
    const manifest = publicWorks.has(work) ? `${work}-public.yaml` : `${work}.yaml`;
    console.log(`\nBuilding ${work} from manifests/${manifest}`);
    run(PY, ['-m', 'reader_pipeline', 'all', '--work', work, '--public'], {
      cwd: join(ROOT, 'pipeline'),
      // The raw pipeline stamp, not the release identity -- stage7_emit.py
      // writes this verbatim into manifest.json, and emit-lyceum-manifest.mjs's
      // reorderCorpusVersion() (which produced CORPUS_VERSION above) expects
      // to find it in exactly this <sha>-YYYY-MM-DD shape when it re-derives
      // the release version from each work's manifest.json later.
      env: { CORPUS_VERSION: PIPELINE_CORPUS_VERSION },
    });
  }
}

const dataDir = DIST_DIR;
const dataProblem = dataDirProblem(dataDir);
if (dataProblem) {
  console.error(dataProblem);
  process.exit(1);
}

// Turn-align each alternate public-domain translation onto its work's reference
// turnFlow, injecting alt[<id>] into the emitted book JSON (build/dist is what
// the app reads). Runs after every work is built so the reference exists. Each
// alternate translation declares itself with a sources/<dir>/align.json config.
const SOURCES = join(ROOT, 'sources');
const alignConfigs =
  STAGES['turn-align'].enabled && existsSync(SOURCES)
    ? readdirSync(SOURCES)
        .map((dir) => join(SOURCES, dir, 'align.json'))
        .filter((p) => existsSync(p))
        .sort((a, b) => a.localeCompare(b))
    : [];
if (alignConfigs.length) {
  console.log('\nTurn-aligning alternate translations');
  for (const cfg of alignConfigs) {
    run(PY, ['-m', 'reader_pipeline.align_turns', '--config', cfg], {
      cwd: join(ROOT, 'pipeline'),
    });
  }
}

// Multi-corpus mount (Lyceum P3 stage 2, docs/p3-plan.md): flat-merges every
// registered external corpus's own built work directories into build/dist
// alongside the classical works, running the corpus-adapter transforms
// (manifest/search/private) and merging its LSJ shards. Runs after every
// classical work is built (so the shared root exists to merge into) and
// before preflight/validate_contracts (which must see the mounted
// manifests too). A corpus.mjs no-ops cleanly when its source directory
// isn't present on this machine (e.g. CI, or a checkout without the
// sibling repo) -- see mount-corpus.mjs's own no-op log line.
const CORPORA_DIR = join(ROOT, 'corpora');
const mountedCorpora =
  STAGES['mount-corpora'].enabled && existsSync(CORPORA_DIR)
    ? readdirSync(CORPORA_DIR).filter((name) => existsSync(join(CORPORA_DIR, name, 'mount.yaml')))
    : [];
if (mountedCorpora.length) {
  console.log('\nMounting external corpora');
  for (const corpus of mountedCorpora) {
    run('node', [join(ROOT, 'scripts', 'mount-corpus.mjs'), corpus], {
      // Same raw pipeline stamp as the classical per-work loop above -- every
      // work's manifest.json (classical and mounted alike) must carry the
      // identical string, or emit-lyceum-manifest.mjs's buildIndex() throws
      // "mixed corpus_version values".
      env: { CORPUS_VERSION: PIPELINE_CORPUS_VERSION },
    });
  }
}

// Cross-corpus citation index (Lyceum P3 stage 3, docs/p3-plan.md Settled
// decision 5): scans build/dist for every BUILT bekker/busse-scheme work
// (classical and any mounted corpus alike) and emits build/dist/citation-
// index.json, fetched by shared/lib/data.ts's fetchCitationIndex. Runs
// after the mount step (so a mounted corpus's works are already merged in)
// and before preflight -- preflight's own dist walk reads manifests/*.yaml,
// not dist files, so an extra file here doesn't perturb it.
console.log('\nBuilding cross-corpus citation index');
run('node', [join(ROOT, 'scripts', 'build-citation-index.mjs')]);

// Cross-corpus route ownership (Lyceum P3 stage 5, docs/p3-plan.md Settled
// decision 7): generated only from the committed registry, so it can catch
// route and name collisions even when no external corpus data is mounted.
console.log('\nBuilding cross-corpus route registry');
run('node', [join(ROOT, 'scripts', 'build-registry.mjs')]);
run('node', [join(ROOT, 'scripts', 'build-route-registry.mjs')]);

console.log('\nRunning corpus preflight validation');
run(PY, ['-m', 'reader_pipeline.preflight', dataDir, MANIFESTS], {
  cwd: join(ROOT, 'pipeline'),
});

console.log('\nValidating versioned data contracts');
run(PY, [
  '-m', 'reader_pipeline.validate_contracts',
  '--schemas', join(ROOT, 'schemas'),
  '--dist', dataDir,
  '--snapshot', join(ROOT, 'fixtures', 'taxonomy.json'),
  '--registry', join(ROOT, 'build', 'route-registry.json'),
], {
  cwd: join(ROOT, 'pipeline'),
});

// Partner (Lyceum Reader Manager) manifest view: derived from each work's own
// manifest.json, written into the same build/dist/<work>/ directory. Must run
// before the Astro build below -- app/public/data is a symlink to build/dist,
// so Astro only ships files that exist here by the time it walks the tree.
// Same failure contract as every other step: a non-zero exit fails the build.
console.log('\nEmitting partner-catalog (Lyceum) manifests');
run('node', [join(ROOT, 'scripts', 'emit-lyceum-manifest.mjs')], { env: DATA_ROOT_ENV });

// LSJ top-up (Lyceum P3 stage 2, docs/p3-plan.md Settled decision 4): fills
// in dictionary entries for keys referenced only by a mounted corpus's
// works (never a classical one), regenerated from grc.lsj.xml with this
// repo's current renderer -- runs after validate_contracts (which needs
// the mounted manifests already adapted) and before verify_shared_lsj (the
// gate this closes). A no-op when no corpus is mounted.
//
// --from-dist mode has no Diogenes install (machine-local) and did not just
// run the topup itself, so it only CHECKS that the release it was handed was
// already fully topped up (--check-only) and fails loudly if not, rather
// than silently shipping a release with missing mounted-only LSJ entries.
if (STAGES['lsj-topup'].mode === 'check-only') {
  console.log('\nChecking the release was fully topped up (LSJ top-up, --check-only)');
  const checkOnly = spawnSync(PY, ['-m', 'reader_pipeline.lsj_topup', '--check-only'], {
    cwd: join(ROOT, 'pipeline'),
    env: process.env,
    stdio: 'inherit',
  });
  if (checkOnly.error) throw checkOnly.error;
  if (checkOnly.status !== 0) {
    throw new Error(
      'lsj_topup --check-only failed: this release was not fully topped up before publish ' +
        '(see the keys listed above) -- rebuild the release with the mounted corpus present.',
    );
  }
} else {
  console.log('\nTopping up the shared LSJ dictionary for mounted corpora');
  run(PY, ['-m', 'reader_pipeline.lsj_topup'], {
    cwd: join(ROOT, 'pipeline'),
  });
}

// Safety gate for the shared (de-duplicated) LSJ dictionary: fail the build if
// any LSJ key referenced by any work's analyses.json is missing from the shared
// build/dist/lsj shards (which would make a word popup silently show no entry).
console.log('\nVerifying shared LSJ dictionary covers every referenced key');
run(PY, ['-m', 'reader_pipeline.verify_shared_lsj'], {
  cwd: join(ROOT, 'pipeline'),
});

// (app dependencies are ensured present earlier, ahead of the translation-seam gate)

// Release index (docs/release-from-dist.md): write it before the Astro build
// so any future non-derived build output fails the final verification gate.
// Not written in --from-dist mode -- the release being built FROM
// already carries its own RELEASE.json, verified above; writing a new one
// here would just re-describe someone else's build/dist under this
// checkout's commit, which is not what "producer_commit" is for.
if (STAGES['release-index'].enabled) {
  console.log('\nWriting release index (build/dist/RELEASE.json)');
  const { writeReleaseIndex } = await import('./release-index.mjs');
  const releaseIndex = writeReleaseIndex(dataDir);
  console.log(
    `  ${releaseIndex.files.length} file(s), ${releaseIndex.works} work(s), ` +
      `corpus_version=${releaseIndex.corpus_version}`,
  );
}

// Private (copyright-encumbered) translations are hidden by default; a
// production build only carries them if PUBLIC_SHOW_PRIVATE=1. Force it off here
// so the public deploy can never leak them — even if the caller's shell happens
// to have that var set. (See SHOW_PRIVATE in app/src/lib/works.ts.)
console.log('\nBuilding Astro app (private translations hidden)');
// DATA_ROOT_ENV carries PUBLIC_DATA_ROOT (off-origin URL or bucket mode's
// own path) when either mode is active -- this one env object is also what
// the "npm run build" chain hands to postbuild-sw.mjs afterward
// (app/package.json's build script runs astro build then postbuild-sw.mjs
// in one process tree), so a value set only in THIS process's env, not the
// parent shell's, still reaches both steps.
const astroBuildEnv = { PUBLIC_SHOW_PRIVATE: '0', ...DATA_ROOT_ENV };
run('npm', ['run', 'build'], {
  cwd: join(ROOT, 'app'),
  env: astroBuildEnv,
});

console.log('\nVerifying final release data');
const { verifyRelease: verifyFinalRelease } = await import('./verify-release.mjs');
const finalReleaseCheck = verifyFinalRelease(DIST_DIR);
if (!finalReleaseCheck.ok) {
  console.error('final release verification failed for build/dist:');
  for (const p of finalReleaseCheck.problems.slice(0, 10)) console.error(`  FAIL: ${p}`);
  throw new Error(`final release verification found ${finalReleaseCheck.problems.length} problem(s)`);
}

// Deploy gate: every internal href, fragment anchor, Bekker deep link, and
// lemma page in the emitted site must resolve. CI can't run this (the corpus
// is machine-local), so the pre-deploy build is where it has to hold the line.
//
// Runs BEFORE the data prune below, on purpose: check-links's lemma
// cross-check reads dist/data/lemmata*/_index.json (and dist/data/lemmata*/
// <slug>.json) straight off disk to verify the lexicon index and its data
// files agree. Pruning first wouldn't fail that check loudly -- it would
// silently SKIP it (check-links.mjs treats a missing index as "nothing to
// check" so a from-scratch/fixture build isn't penalized), which would let a
// real index/data mismatch ship undetected. check-links must see the
// pre-prune, full-data dist to be a meaningful gate at all.
console.log('\nChecking link integrity of the built site');
run('node', [join(ROOT, 'scripts', 'check-links.mjs'), join(ROOT, 'app', 'dist', 'client')]);

// Address-stability gate (scripts/check-addresses.mjs): readers bookmark and
// cite our pages, so a page address that existed in the last public release
// must never quietly disappear from this one. New addresses are fine. Runs
// right after check-links, before the data prune, for the same reason
// check-links does: this is the pre-deploy build, the one point where the
// gate can hold the line (CI builds no real corpus data to check against).
console.log('\nChecking published addresses against the baseline');
run('node', [join(ROOT, 'scripts', 'check-addresses.mjs'), join(ROOT, 'app', 'dist', 'client')]);

// Deploy-artifact hygiene (Lyceum P6 plan, Settled decision 3 / docs/p6-plan.md
// Stage 1): once check-links has validated the full-data dist above, prune
// dist/client/data whenever this build shipped a PUBLIC_DATA_ROOT (either an
// off-origin R2 host or bucket mode's own same-origin `/data/<version>`
// path) and assert the pruned artifact is what the Worker's static assets
// should ship. A same-origin build (neither mode) does neither step --
// dist/client/data ships as it always has. (@astrojs/cloudflare emits
// dist/client (static assets, what deploys) + dist/server (the Worker
// entry); the assertions below are about dist/client only.)
//
// Both modes reduce to the exact same check here: postbuild-prune-data.mjs
// and verify-pages-artifact.mjs only ever look at PUBLIC_DATA_ROOT (a plain
// string -- an absolute URL for off-origin, an absolute path for bucket
// mode, and verify-pages-artifact.mjs's sw.js literal check doesn't care
// which), so there is no separate bucket-mode branch or verification mode
// to maintain.
const dataRootForPrune = DATA_ROOT_ENV.PUBLIC_DATA_ROOT ?? null;
if (dataRootForPrune) {
  console.log(`\nPruning dist/client/data (${DATA_SOURCE.mode} build, data root ${dataRootForPrune})`);
  run('node', [join(ROOT, 'app', 'scripts', 'postbuild-prune-data.mjs')], {
    cwd: join(ROOT, 'app'),
    env: DATA_ROOT_ENV,
  });

  console.log('\nVerifying pruned deploy artifact');
  const verifyArgs = [
    join(ROOT, 'scripts', 'verify-pages-artifact.mjs'),
    join(ROOT, 'app', 'dist', 'client'),
    '--expect-data-root', dataRootForPrune,
  ];
  // Bucket mode only: independently re-check the "one stamp" invariant this
  // fix establishes -- that the /data/<version> root baked into the deploy
  // artifact and build/dist/RELEASE.json's own corpus_version name the same
  // version. Reads RELEASE.json fresh off disk rather than trusting the
  // in-memory CORPUS_VERSION above, so it still catches drift if some future
  // change breaks the invariant this fix relies on. Off-origin mode's data
  // root is an arbitrary URL with no relationship to corpus_version, so the
  // check does not apply there.
  if (DATA_SOURCE.mode === 'bucket') {
    verifyArgs.push('--release-json', join(DIST_DIR, 'RELEASE.json'));
  }
  run('node', verifyArgs);
}
