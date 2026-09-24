// Unit tests for scripts/vendor-plato-registry.mjs's pure functions, against
// a literal fixture shaped like plato-reader's shared/lib/works.ts (36
// works, 9 tetralogies of 4, 10 dubious) -- see docs/todo/plato-mount.md
// step 1. Run with: node --test scripts/__tests__/vendor-plato-registry.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  deriveSlug,
  mapWork,
  parseTetralogyComments,
  deriveTetralogyGroups,
  assertRegistry,
  applyPostVendorCorrections,
  applyTetralogyIIIOrderCorrection,
} from '../vendor-plato-registry.mjs';

const DUBIOUS_IDS = new Set([
  'Alcibiades1', 'Alcibiades2', 'Hipparchus', 'Lovers', 'Theages',
  'HippiasMajor', 'Clitophon', 'Minos', 'Epinomis', 'Letters',
]);

// 9 tetralogies x 4 ids, in Thrasyllan order -- real plato-reader ids, but a
// minimal synthetic Work body (this fixture is deliberately NOT a copy of
// the real file; it only needs to be shaped like it).
const TETRALOGIES = [
  ['Euthyphro', 'Apology', 'Crito', 'Phaedo'],
  ['Cratylus', 'Theaetetus', 'Sophist', 'Statesman'],
  ['Symposium', 'Parmenides', 'Philebus', 'Phaedrus'],
  ['Alcibiades1', 'Alcibiades2', 'Hipparchus', 'Lovers'],
  ['Theages', 'Charmides', 'Laches', 'Lysis'],
  ['Euthydemus', 'Protagoras', 'Gorgias', 'Meno'],
  ['HippiasMajor', 'HippiasMinor', 'Ion', 'Menexenus'],
  ['Clitophon', 'Republic', 'Timaeus', 'Critias'],
  ['Minos', 'Laws', 'Epinomis', 'Letters'],
];

function fixtureWork(id) {
  return {
    id,
    title: id,
    abbr: id.slice(0, 4),
    author: 'Plato',
    books: id === 'Republic' ? 10 : 1,
    bookLabels: id === 'Republic' ? Array.from({ length: 10 }, (_, i) => String(i + 1)) : ['1'],
    greekEdition: 'Burnet, Platonis Opera (OCT)',
    greekSource: { short: 'Burnet (OCT)', full: 'J. Burnet, ed. Platonis opera. Oxford: Clarendon Press.' },
    translations:
      id === 'Republic'
        ? [{ id: 'shorey', name: 'Paul Shorey (Loeb, 1930–35)', short: 'Shorey', slot: 'english' }]
        : [{ id: 'fowler', name: 'H. N. Fowler (Loeb, 1914)', short: 'Fowler', slot: 'english' }],
    citation: { scheme: 'stephanus', hideLineNumbers: true },
    blurb: `${id} blurb.`,
    ...(DUBIOUS_IDS.has(id) ? { authenticity: 'dubious' } : {}),
  };
}

const FIXTURE_WORKS = TETRALOGIES.flat().map(fixtureWork);

function fixtureSourceText() {
  const numerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX'];
  let body = 'export const WORKS: Work[] = [\n';
  TETRALOGIES.forEach((ids, i) => {
    body += `  // ---- Tetralogy ${numerals[i]} ----\n`;
    for (const id of ids) body += `  { id: '${id}', title: '${id}' },\n`;
  });
  body += '];\n\nconst BY_ID = new Map(WORKS.map((w) => [w.id, w]));\n';
  return body;
}

test('deriveSlug: lowercases and hyphenates, matching titles like "Alcibiades I"', () => {
  assert.equal(deriveSlug('Republic'), 'republic');
  assert.equal(deriveSlug('Alcibiades I'), 'alcibiades-i');
  assert.equal(deriveSlug('Hippias Major'), 'hippias-major');
});

test('deriveSlug: throws on a title that produces an empty slug', () => {
  assert.throws(() => deriveSlug('...'), /empty slug/);
});

test('mapWork: maps 36-work-shaped fixture entries to registry entries (stephanus, workType, author id)', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  assert.equal(mapped.length, 36);
  for (const w of mapped) {
    assert.equal(w.author, 'plato');
    assert.equal(w.language, 'grc');
    assert.equal(w.citation.scheme, 'stephanus');
  }
  // Letters is the one 'letters'-workType work; every other work is
  // 'continuous' (the established value for a single dialogue, matching
  // manifests/epistulae-morales.yaml's own precedent for a letter collection).
  const byId = Object.fromEntries(mapped.map((w) => [w.id, w]));
  assert.equal(byId.Letters.workType, 'letters');
  assert.equal(byId.Euthyphro.workType, 'continuous');
  assert.equal(byId.Republic.workType, 'continuous');
});

test('mapWork: throws on an author other than Plato', () => {
  assert.throws(() => mapWork({ ...fixtureWork('X'), author: 'Someone Else' }), /expected author 'Plato'/);
});

test('mapWork: throws when citation.scheme is not stephanus', () => {
  assert.throws(
    () => mapWork({ ...fixtureWork('X'), citation: { scheme: 'bekker' } }),
    /expected citation\.scheme 'stephanus'/,
  );
});

test('mapWork: throws on an unmapped field (guards silent data loss)', () => {
  assert.throws(() => mapWork({ ...fixtureWork('X'), unknownField: 1 }), /unmapped field/);
});

test('assertRegistry: passes for the 36-work fixture with exactly 10 dubious works', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  assert.doesNotThrow(() => assertRegistry(mapped));
});

test('assertRegistry: throws when the work count is not 36', () => {
  const mapped = FIXTURE_WORKS.slice(0, 35).map(mapWork);
  assert.throws(() => assertRegistry(mapped), /expected 36 works, found 35/);
});

test('assertRegistry: throws when the dubious count is not 10', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  mapped[0] = { ...mapped[0], authenticity: 'dubious' }; // Euthyphro: 11th dubious
  assert.throws(() => assertRegistry(mapped), /expected 10 dubious works, found 11/);
});

test('parseTetralogyComments: recovers a workId -> tetralogy-numeral map from the raw source text', () => {
  const map = parseTetralogyComments(fixtureSourceText());
  assert.equal(map.get('Euthyphro'), 'I');
  assert.equal(map.get('Republic'), 'VIII');
  assert.equal(map.get('Letters'), 'IX');
  assert.equal(map.size, 36);
});

test('deriveTetralogyGroups: 9 groups of 4, in Thrasyllan order, agreeing with the source comments', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const commentMap = parseTetralogyComments(fixtureSourceText());
  const groups = deriveTetralogyGroups(mapped, commentMap);
  assert.equal(groups.length, 9);
  for (const g of groups) assert.equal(g.works.length, 4);
  assert.equal(groups[0].numeral, 'I');
  assert.equal(groups[0].title, 'Tetralogy I');
  assert.deepEqual(groups[0].works, ['Euthyphro', 'Apology', 'Crito', 'Phaedo']);
  assert.equal(groups[8].numeral, 'IX');
  assert.deepEqual(groups[8].works, ['Minos', 'Laws', 'Epinomis', 'Letters']);
});

test('deriveTetralogyGroups: FAILS LOUDLY when order-derived grouping disagrees with the source comment (P4 discipline: never silently trust one source)', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  // Swap Apology and Cratylus's *comment* tetralogy without touching WORKS
  // order -- simulates a sibling edit that reordered WORKS but not its own
  // comments (or vice versa).
  const commentMap = parseTetralogyComments(fixtureSourceText());
  commentMap.set('Apology', 'II');
  assert.throws(
    () => deriveTetralogyGroups(mapped, commentMap),
    /disagrees with its source comment/,
  );
});

test('deriveTetralogyGroups: throws when a work id has no source-comment tetralogy at all', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const commentMap = parseTetralogyComments(fixtureSourceText());
  commentMap.delete('Phaedo');
  assert.throws(() => deriveTetralogyGroups(mapped, commentMap), /has no source-comment tetralogy/);
});

test('applyPostVendorCorrections: writes the Shorey "unverified" licence, never public-domain-us (John\'s pre-1940 ruling)', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const registryDoc = { registry: Object.fromEntries(mapped.map((w) => [w.id, w])) };
  applyPostVendorCorrections(registryDoc);
  const shorey = registryDoc.registry.Republic.translations[0];
  assert.equal(shorey.id, 'shorey');
  assert.equal(shorey.license.status, 'unverified');
  assert.notEqual(shorey.license.status, 'public-domain-us');
});

test('applyPostVendorCorrections: throws if the sibling data has drifted out from under the correction', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  mapped.find((w) => w.id === 'Republic').translations[0] = { id: 'someone-else', name: 'X', short: 'X', slot: 'english' };
  const registryDoc = { registry: Object.fromEntries(mapped.map((w) => [w.id, w])) };
  assert.throws(() => applyPostVendorCorrections(registryDoc), /data has drifted/);
});

// Tetralogy III order correction (John's ruling, 2026-09-23: DL 3.58 gives
// Parmenides, Philebus, Symposium, Phaedrus; the fixture's source order
// above, like the real works.ts, has Symposium, Parmenides, Philebus,
// Phaedrus).
test('applyTetralogyIIIOrderCorrection: reorders Tetralogy III to Parmenides, Philebus, Symposium, Phaedrus (DL 3.58)', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const commentMap = parseTetralogyComments(fixtureSourceText());
  const reordered = applyTetralogyIIIOrderCorrection(mapped, commentMap);
  assert.equal(reordered.length, 36);
  assert.deepEqual(
    reordered.slice(8, 12).map((w) => w.id),
    ['Parmenides', 'Philebus', 'Symposium', 'Phaedrus'],
  );
  // Every other tetralogy is untouched, including its order.
  const groups = deriveTetralogyGroups(reordered, commentMap);
  assert.deepEqual(groups[0].works, ['Euthyphro', 'Apology', 'Crito', 'Phaedo']);
  assert.deepEqual(groups[1].works, ['Cratylus', 'Theaetetus', 'Sophist', 'Statesman']);
  assert.deepEqual(groups[2].works, ['Parmenides', 'Philebus', 'Symposium', 'Phaedrus']);
  assert.deepEqual(groups[3].works, ['Alcibiades1', 'Alcibiades2', 'Hipparchus', 'Lovers']);
  assert.deepEqual(groups[8].works, ['Minos', 'Laws', 'Epinomis', 'Letters']);
});

test('applyTetralogyIIIOrderCorrection: still passes the group-membership check against the source comments after reordering', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const commentMap = parseTetralogyComments(fixtureSourceText());
  const reordered = applyTetralogyIIIOrderCorrection(mapped, commentMap);
  assert.doesNotThrow(() => deriveTetralogyGroups(reordered, commentMap));
});

test('applyTetralogyIIIOrderCorrection: throws when Tetralogy III\'s source-declared membership is not exactly the expected four works', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  // Simulate a sibling edit that changed which works belong to Tetralogy III
  // (its source comment now claims Cratylus instead of Phaedrus).
  const commentMap = parseTetralogyComments(fixtureSourceText());
  commentMap.set('Phaedrus', 'II');
  commentMap.set('Cratylus', 'III');
  assert.throws(
    () => applyTetralogyIIIOrderCorrection(mapped, commentMap),
    /expected exactly the source's own comment-declared members/,
  );
});

test('applyTetralogyIIIOrderCorrection: throws when the four works are not contiguous in the source order', () => {
  const mapped = FIXTURE_WORKS.map(mapWork);
  const commentMap = parseTetralogyComments(fixtureSourceText());
  // Move Phaedrus out of its source position so the block is no longer
  // contiguous, without changing comment-declared membership.
  const phaedrusIndex = mapped.findIndex((w) => w.id === 'Phaedrus');
  const [phaedrus] = mapped.splice(phaedrusIndex, 1);
  mapped.push(phaedrus);
  assert.throws(
    () => applyTetralogyIIIOrderCorrection(mapped, commentMap),
    /expected a contiguous source-order block/,
  );
});

// John, 2026-09-23: the whole canon follows Diogenes Laertius 3.58-61 (only
// Tetralogy III differs from plato-reader's order). Checked against the
// committed corpora/plato files, so the three orders cannot drift apart.
test('corpora/plato: all nine tetralogies in DL 3.58-61 order, and the three files agree', async () => {
  const { readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  const { loadYaml, REPO_ROOT } = await import('../lib/load-yaml.mjs');
  const yaml = await loadYaml();
  const read = (f) => yaml.load(readFileSync(join(REPO_ROOT, 'corpora/plato', f), 'utf8'));
  const DL = [
    ['Euthyphro', 'Apology', 'Crito', 'Phaedo'],
    ['Cratylus', 'Theaetetus', 'Sophist', 'Statesman'],
    ['Parmenides', 'Philebus', 'Symposium', 'Phaedrus'],
    ['Alcibiades1', 'Alcibiades2', 'Hipparchus', 'Lovers'],
    ['Theages', 'Charmides', 'Laches', 'Lysis'],
    ['Euthydemus', 'Protagoras', 'Gorgias', 'Meno'],
    ['HippiasMajor', 'HippiasMinor', 'Ion', 'Menexenus'],
    ['Clitophon', 'Republic', 'Timaeus', 'Critias'],
    ['Minos', 'Laws', 'Epinomis', 'Letters'],
  ];
  const groups = read('groups.yaml').groups;
  assert.deepEqual(groups.map((g) => g.works), DL);
  const flat = DL.flat();
  const plato = read('authors.yaml').authors.find((a) => a.id === 'plato');
  assert.deepEqual(plato.works, flat);
  assert.deepEqual(Object.keys(read('registry.yaml').registry), flat);
});
