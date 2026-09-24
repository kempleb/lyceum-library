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
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  findHeldWorksInDist,
  formatHeldWorksFindings,
  listHeldCorpora,
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

test('listHeldCorpora: the real repo lists plato (held) and not aristotle (unheld)', async () => {
  const held = await listHeldCorpora(REPO_ROOT);
  const names = held.map((h) => h.corpus);
  assert.ok(names.includes('plato'), `expected plato among held corpora, got ${names.join(', ')}`);
  assert.ok(!names.includes('aristotle'), 'aristotle has no hold flag and must not be reported as held');
  const plato = held.find((h) => h.corpus === 'plato');
  assert.ok(plato.workIds.includes('Euthyphro'), 'plato registry.yaml declares Euthyphro');
  assert.ok(plato.workIds.length >= 36, `expected at least 36 Plato works, got ${plato.workIds.length}`);
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

test('findHeldWorksInDist: against the real repo, a dist with a Plato work directory is caught', async () => {
  await withTmpDir(async (root) => {
    const dist = join(root, 'dist');
    mkdirSync(join(dist, 'Euthyphro'), { recursive: true });
    const findings = await findHeldWorksInDist(dist, { root: REPO_ROOT });
    const euthyphro = findings.find((f) => f.workId === 'Euthyphro');
    assert.ok(euthyphro, 'expected the real plato registry to catch a mounted Euthyphro directory');
    assert.equal(euthyphro.corpus, 'plato');
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
