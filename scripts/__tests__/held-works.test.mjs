// Tests scripts/lib/held-works.mjs (docs/todo/plato-mount.md, GPT-6 Sol code
// review item 1 -- BLOCKER): mount-corpus.mjs's own hold switch
// (shouldSkipForHold, see mount-corpus.test.mjs) only stops the MOUNT step
// from copying a held corpus into build/dist. Nothing downstream re-checked
// it before this fix -- a release built locally with READER_INCLUDE_HELD=1
// could still be published (publish-release.mjs) or rebuilt-from
// (build-public.mjs --from-dist) with the held corpus's data still inside.
// This suite covers the shared helper both call sites now use.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

import {
  findHeldWorksInDist,
  formatHeldWorksFindings,
  listHeldCorpora,
  markHeldBuildUndeployable,
  shouldRefuseForHeld,
} from '../lib/held-works.mjs';
import { REPO_ROOT } from '../lib/load-yaml.mjs';

async function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'held-works-test-'));
  try {
    return await fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeFixtureCorpus(root, name, { hold, workIds }) {
  const dir = join(root, 'corpora', name);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, 'mount.yaml'), `hold: ${hold}\ncorpus: ${name}\n`);
  const registryLines = ['registry:'];
  for (const id of workIds) {
    registryLines.push(`  ${id}:`, `    id: ${id}`, `    title: ${id}`);
  }
  writeFileSync(join(dir, 'registry.yaml'), `${registryLines.join('\n')}\n`);
}

// Real-repo claims. Plato was held from 2026-09-23 until John lifted the hold
// on 2026-09-30; neither mounted corpus is held now. The hold mechanism
// itself is covered by the temporary-corpus tests in this file.
test('listHeldCorpora: the real repo lists neither plato nor aristotle (both unheld)', async () => {
  const names = (await listHeldCorpora(REPO_ROOT)).map((h) => h.corpus);
  assert.ok(!names.includes('plato'), 'the plato hold was lifted 2026-09-30');
  assert.ok(!names.includes('aristotle'), 'aristotle has no hold flag and must not be reported as held');
});

test('listHeldCorpora: no corpora/ directory returns an empty list', async () => {
  await withTmpDir(async (root) => {
    assert.deepEqual(await listHeldCorpora(root), []);
  });
});

test('listHeldCorpora: only reports corpora with hold: true, using each one\'s own registry.yaml', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA', 'WorkB'] });
    writeFixtureCorpus(root, 'unheld-corpus', { hold: false, workIds: ['WorkC'] });
    const held = await listHeldCorpora(root);
    assert.deepEqual(held, [{ corpus: 'held-corpus', workIds: ['WorkA', 'WorkB'] }]);
  });
});

test('findHeldWorksInDist: an empty dist reports nothing', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dist = join(root, 'dist');
    mkdirSync(dist, { recursive: true });
    assert.deepEqual(await findHeldWorksInDist(dist, { root }), []);
  });
});

test('findHeldWorksInDist: a held work\'s own directory in dist is reported', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA', 'WorkB'] });
    const dist = join(root, 'dist');
    mkdirSync(join(dist, 'WorkA'), { recursive: true });
    const findings = await findHeldWorksInDist(dist, { root });
    assert.equal(findings.length, 1);
    assert.equal(findings[0].corpus, 'held-corpus');
    assert.equal(findings[0].workId, 'WorkA');
    assert.match(findings[0].evidence.join(', '), /work directory/);
  });
});

test('findHeldWorksInDist: a manifests/index.json entry under the held work is reported', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dist = join(root, 'dist');
    mkdirSync(join(dist, 'manifests'), { recursive: true });
    writeFileSync(
      join(dist, 'manifests', 'index.json'),
      JSON.stringify({ manifests: [{ work: 'Work A', path: '/WorkA/manifest.lyceum.json', sha256: 'x' }] }),
    );
    const findings = await findHeldWorksInDist(dist, { root });
    assert.equal(findings.length, 1);
    assert.equal(findings[0].workId, 'WorkA');
    assert.match(findings[0].evidence.join(', '), /manifests\/index\.json/);
  });
});

test('findHeldWorksInDist: a RELEASE.json file path under the held work is reported', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dist = join(root, 'dist');
    mkdirSync(dist, { recursive: true });
    writeFileSync(
      join(dist, 'RELEASE.json'),
      JSON.stringify({ corpus_version: 'v1', files: [{ path: 'WorkA/manifest.json', size: 1, sha256: 'x' }] }),
    );
    const findings = await findHeldWorksInDist(dist, { root });
    assert.equal(findings.length, 1);
    assert.equal(findings[0].workId, 'WorkA');
    assert.match(findings[0].evidence.join(', '), /RELEASE\.json/);
  });
});

test('findHeldWorksInDist: an unheld corpus\'s work present in dist is never reported', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    writeFixtureCorpus(root, 'unheld-corpus', { hold: false, workIds: ['WorkC'] });
    const dist = join(root, 'dist');
    mkdirSync(join(dist, 'WorkC'), { recursive: true });
    assert.deepEqual(await findHeldWorksInDist(dist, { root }), []);
  });
});

test('findHeldWorksInDist: against the real repo, a dist with a Plato work directory is not flagged', async () => {
  await withTmpDir(async (root) => {
    const dist = join(root, 'dist');
    mkdirSync(join(dist, 'Euthyphro'), { recursive: true });
    const findings = await findHeldWorksInDist(dist, { root: REPO_ROOT });
    assert.equal(findings.find((f) => f.workId === 'Euthyphro'), undefined, 'plato is no longer held');
  });
});

test('formatHeldWorksFindings: names the corpus and its hold, not just bare work ids', () => {
  const message = formatHeldWorksFindings([
    { corpus: 'plato', workId: 'Euthyphro', evidence: ['work directory Euthyphro/'] },
    { corpus: 'plato', workId: 'Apology', evidence: ['work directory Apology/'] },
  ]);
  assert.match(message, /plato/);
  assert.match(message, /hold: true/);
  assert.match(message, /Euthyphro/);
  assert.match(message, /Apology/);
});

test('shouldRefuseForHeld: no findings never refuses', () => {
  assert.equal(shouldRefuseForHeld([], {}), false);
  assert.equal(shouldRefuseForHeld([], { READER_INCLUDE_HELD: '1' }), false);
});

test('shouldRefuseForHeld: findings refuse unless READER_INCLUDE_HELD=1', () => {
  const findings = [{ corpus: 'plato', workId: 'Euthyphro', evidence: ['work directory Euthyphro/'] }];
  assert.equal(shouldRefuseForHeld(findings, {}), true);
  assert.equal(shouldRefuseForHeld(findings, { READER_INCLUDE_HELD: '0' }), true);
  assert.equal(shouldRefuseForHeld(findings, { READER_INCLUDE_HELD: 'true' }), true);
  assert.equal(shouldRefuseForHeld(findings, { READER_INCLUDE_HELD: '1' }), false);
});

// Deploy gate (2026-10-08): a held-on app build must not be deployable. The
// gate writes a failing build.command into the Worker config the build
// emitted, which `wrangler deploy` runs before uploading anything.
function writeWorkerConfig(serverDir) {
  mkdirSync(serverDir, { recursive: true });
  const configPath = join(serverDir, 'wrangler.json');
  writeFileSync(
    configPath,
    JSON.stringify({ name: 'gate-test', main: 'entry.mjs', compatibility_date: '2026-09-01' }),
  );
  writeFileSync(join(serverDir, 'entry.mjs'), "export default { fetch() { return new Response('ok'); } };\n");
  return configPath;
}

test('markHeldBuildUndeployable: with no held work in the data, the Worker config is left byte-identical', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    writeFixtureCorpus(root, 'open-corpus', { hold: false, workIds: ['WorkB'] });
    const dataDir = join(root, 'data');
    mkdirSync(join(dataDir, 'WorkB'), { recursive: true });
    const configPath = writeWorkerConfig(join(root, 'server'));
    const before = readFileSync(configPath);
    const findings = await markHeldBuildUndeployable({ dataDir, serverDir: join(root, 'server'), root });
    assert.deepEqual(findings, []);
    assert.deepEqual(readFileSync(configPath), before);
  });
});

test('markHeldBuildUndeployable: a held work in the data writes a failing build command naming the corpus', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dataDir = join(root, 'data');
    mkdirSync(join(dataDir, 'WorkA'), { recursive: true });
    const configPath = writeWorkerConfig(join(root, 'server'));
    const findings = await markHeldBuildUndeployable({ dataDir, serverDir: join(root, 'server'), root });
    assert.equal(findings.length, 1);
    const config = JSON.parse(readFileSync(configPath, 'utf8'));
    assert.equal(config.name, 'gate-test', 'the rest of the config is kept');
    assert.match(config.build.command, /refusing to deploy/);
    assert.match(config.build.command, /held-corpus/);
    assert.match(config.build.command, /exit 1$/);
  });
});

test('markHeldBuildUndeployable: a held work with no Worker config to mark is an error', async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dataDir = join(root, 'data');
    mkdirSync(join(dataDir, 'WorkA'), { recursive: true });
    await assert.rejects(
      markHeldBuildUndeployable({ dataDir, serverDir: join(root, 'server'), root }),
      /cannot be marked undeployable/,
    );
  });
});

// End to end against the real wrangler: `wrangler deploy --dry-run` from an
// app-shaped directory, through the same .wrangler/deploy/config.json
// redirect astro build writes, passes before the gate and fails after it.
// --dry-run never contacts Cloudflare.
const WRANGLER = join(REPO_ROOT, 'app', 'node_modules', '.bin', 'wrangler');

test('markHeldBuildUndeployable: `wrangler deploy` refuses a marked build', {
  skip: existsSync(WRANGLER) ? false : 'app/node_modules has no wrangler (run npm ci in app/)',
  timeout: 120_000,
}, async () => {
  await withTmpDir(async (root) => {
    writeFixtureCorpus(root, 'held-corpus', { hold: true, workIds: ['WorkA'] });
    const dataDir = join(root, 'data');
    mkdirSync(join(dataDir, 'WorkA'), { recursive: true });
    const appDir = join(root, 'app');
    const serverDir = join(appDir, 'dist', 'server');
    writeWorkerConfig(serverDir);
    mkdirSync(join(appDir, '.wrangler', 'deploy'), { recursive: true });
    writeFileSync(
      join(appDir, '.wrangler', 'deploy', 'config.json'),
      JSON.stringify({ configPath: '../../dist/server/wrangler.json', auxiliaryWorkers: [] }),
    );
    const deploy = () =>
      spawnSync(WRANGLER, ['deploy', '--dry-run'], {
        cwd: appDir,
        encoding: 'utf8',
        env: { ...process.env, WRANGLER_SEND_METRICS: 'false', CI: '1' },
      });

    const unmarked = deploy();
    assert.equal(unmarked.status, 0, `an unmarked build must dry-run cleanly:\n${unmarked.stdout}${unmarked.stderr}`);

    await markHeldBuildUndeployable({ dataDir, serverDir, root });
    const marked = deploy();
    assert.notEqual(marked.status, 0, 'wrangler deploy must refuse a build marked as carrying held works');
    assert.match(`${marked.stdout}${marked.stderr}`, /refusing to deploy/);
  });
});
