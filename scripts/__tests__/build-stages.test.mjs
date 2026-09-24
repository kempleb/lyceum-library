import { test } from 'node:test';
import assert from 'node:assert/strict';

import { planReleaseCopy, planStages, parseFromDistArg } from '../lib/build-stages.mjs';

function byName(stages) {
  return Object.fromEntries(stages.map((s) => [s.name, s]));
}

test('full build runs the pipeline, mount, and release-index stages', () => {
  const stages = byName(planStages({ fromDist: false }));
  assert.equal(stages['pipeline-per-work'].enabled, true);
  assert.equal(stages['turn-align'].enabled, true);
  assert.equal(stages['mount-corpora'].enabled, true);
  assert.equal(stages['clean-dist'].enabled, true);
  assert.equal(stages['copy-release'].enabled, false);
  assert.equal(stages['verify-release-copy'].enabled, false);
  assert.equal(stages['release-index'].enabled, true);
  assert.equal(stages['verify-release-final'].enabled, true);
  assert.equal(stages['lsj-topup'].mode, 'full');
});

test('from-dist build skips the pipeline, mount, and release-index stages', () => {
  const stages = byName(planStages({ fromDist: true }));
  assert.equal(stages['pipeline-per-work'].enabled, false);
  assert.equal(stages['turn-align'].enabled, false);
  assert.equal(stages['mount-corpora'].enabled, false);
  assert.equal(stages['clean-dist'].enabled, false);
  assert.equal(stages['copy-release'].enabled, true);
  assert.equal(stages['verify-release-copy'].enabled, true);
  assert.equal(stages['release-index'].enabled, false);
  assert.equal(stages['verify-release-final'].enabled, true);
  assert.equal(stages['lsj-topup'].mode, 'check-only');
});

test('stage names are unique', () => {
  const names = planStages({ fromDist: false }).map((s) => s.name);
  assert.equal(new Set(names).size, names.length);
});

test('stages unaffected by --from-dist stay enabled in both modes', () => {
  const always = [
    'npm-ci',
    'registry-agreement',
    'inventory-hashes',
    'clean-app-dist',
    'citation-index',
    'registries',
    'preflight',
    'validate-contracts',
    'emit-lyceum-manifest',
    'lsj-topup',
    'verify-shared-lsj',
    'astro-build',
    'verify-release-final',
    'check-links',
    'prune-and-verify-artifact',
  ];
  for (const fromDist of [false, true]) {
    const stages = byName(planStages({ fromDist }));
    for (const name of always) {
      assert.equal(stages[name].enabled, true, `${name} should be enabled when fromDist=${fromDist}`);
    }
  }
});

test('parseFromDistArg: --from-dist <dir> form', () => {
  assert.equal(parseFromDistArg(['--from-dist', '/tmp/release'], {}), '/tmp/release');
});

test('parseFromDistArg: --from-dist=<dir> form', () => {
  assert.equal(parseFromDistArg(['--from-dist=/tmp/release'], {}), '/tmp/release');
});

test('parseFromDistArg: READER_RELEASE_DIR env var used when no flag', () => {
  assert.equal(parseFromDistArg([], { READER_RELEASE_DIR: '/tmp/env-release' }), '/tmp/env-release');
});

test('parseFromDistArg: the flag overrides the env var', () => {
  assert.equal(
    parseFromDistArg(['--from-dist', '/tmp/flag'], { READER_RELEASE_DIR: '/tmp/env' }),
    '/tmp/flag',
  );
});

test('parseFromDistArg: neither given returns null', () => {
  assert.equal(parseFromDistArg([], {}), null);
});

test('parseFromDistArg rejects --from-dist without a value', () => {
  assert.throws(() => parseFromDistArg(['--from-dist'], {}), /requires a directory argument/);
});

test('parseFromDistArg rejects --from-dist followed by another option', () => {
  assert.throws(
    () => parseFromDistArg(['--from-dist', '--other-option'], {}),
    /requires a directory argument/,
  );
});

test('parseFromDistArg rejects an empty --from-dist= value', () => {
  assert.throws(() => parseFromDistArg(['--from-dist='], {}), /requires a directory argument/);
});

test('parseFromDistArg treats an empty READER_RELEASE_DIR as unset', () => {
  assert.equal(parseFromDistArg([], { READER_RELEASE_DIR: '' }), null);
});

test('planReleaseCopy returns noop for equal paths', () => {
  assert.equal(planReleaseCopy('/tmp/build/dist', '/tmp/build/dist'), 'noop');
});

test('planReleaseCopy returns copy for disjoint paths', () => {
  assert.equal(planReleaseCopy('/tmp/release', '/tmp/build/dist'), 'copy');
});

test('planReleaseCopy rejects a release inside build/dist', () => {
  assert.throws(
    () => planReleaseCopy('/tmp/build/dist/release', '/tmp/build/dist'),
    /outside build\/dist/,
  );
});

test('planReleaseCopy rejects a source containing build/dist', () => {
  assert.throws(() => planReleaseCopy('/tmp/build', '/tmp/build/dist'), /outside build\/dist/);
});
