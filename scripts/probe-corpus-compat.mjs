#!/usr/bin/env node
// Lyceum P3 stage 0 (docs/p3-plan.md) -- compatibility probe, DIAGNOSTIC ONLY.
// Not part of the build. Reads the sibling aristotle-reader repo's build/dist
// READ-ONLY and this repo's build/dist. Produces two reports:
//
//   (a) normalized deep key-path diff of aristotle EN/Cat/Isa/Meta's
//       manifest/book/chapters/columns/analyses/search JSON against the same
//       file types across five classical works spanning citation schemes
//       (meditations, de-finibus, heraclitus-fragments, de-rerum-natura,
//       lives) -- object keys that look like a dictionary (many keys, same
//       shape across values) collapse to a single `*` so the diff reports
//       SCHEMA divergence, not per-entry noise.
//   (b) a required-file matrix over all 41 aristotle work dirs, plus a check
//       of book-NN.json file count against manifest.json's `books` array
//       length for each.
//
// Usage: node scripts/probe-corpus-compat.mjs

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const REPO_ROOT = new URL('..', import.meta.url).pathname.replace(/\/$/, '');
const ARISTOTLE_DIST = '/Users/johnboyer/Developer/aristotle-reader/build/dist';
const CLASSICAL_DIST = join(REPO_ROOT, 'build', 'dist');

if (!existsSync(ARISTOTLE_DIST)) {
  console.error(`ERROR: sibling dist not found at ${ARISTOTLE_DIST}`);
  process.exit(1);
}
if (!existsSync(CLASSICAL_DIST)) {
  console.error(`ERROR: this repo's dist not found at ${CLASSICAL_DIST}`);
  process.exit(1);
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

// ---------------------------------------------------------------------------
// (a) normalized deep key-path diff
// ---------------------------------------------------------------------------

function shapeOf(v) {
  if (Array.isArray(v)) return 'array';
  if (v === null) return 'null';
  return typeof v;
}

// Two values are "same shape" for map-detection purposes: same JS type, and
// if objects, the same set of top-level keys (order-independent).
function sameShape(a, b) {
  if (shapeOf(a) !== shapeOf(b)) return false;
  if (shapeOf(a) === 'object') {
    const ak = Object.keys(a).sort().join(',');
    const bk = Object.keys(b).sort().join(',');
    return ak === bk;
  }
  return true;
}

const SAMPLE_CAP = 25; // union up to this many entries of a map/array before collapsing

function collectPaths(value, path, out) {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      out.add(`${path}[]`);
      return;
    }
    const n = Math.min(value.length, SAMPLE_CAP);
    for (let i = 0; i < n; i++) collectPaths(value[i], `${path}[*]`, out);
    return;
  }
  if (value !== null && typeof value === 'object') {
    const keys = Object.keys(value);
    if (keys.length === 0) {
      out.add(`${path}{}`);
      return;
    }
    const values = keys.map((k) => value[k]);
    // Heuristic: >=4 keys all sharing the same shape as the first entry ==
    // a dictionary keyed by dynamic data (lemma form, column id, chapter #,
    // ...), not a fixed record. Collapse the key to `*`.
    const isMap = keys.length >= 4 && values.every((v) => sameShape(v, values[0]));
    if (isMap) {
      const n = Math.min(values.length, SAMPLE_CAP);
      for (let i = 0; i < n; i++) collectPaths(values[i], `${path}.*`, out);
    } else {
      for (const k of keys) collectPaths(value[k], `${path}.${k}`, out);
    }
    return;
  }
  out.add(`${path}:${shapeOf(value)}`);
}

function pathSet(jsonPath) {
  if (!existsSync(jsonPath)) return null;
  const out = new Set();
  collectPaths(readJson(jsonPath), '', out);
  return out;
}

// File "slots" to compare. `aristotle` and `classical` may name the file
// differently (the search rename gap is itself a probe-established fact).
const FILE_SLOTS = [
  { label: 'manifest.json', aristotle: 'manifest.json', classical: 'manifest.json' },
  { label: 'book-01.json', aristotle: 'book-01.json', classical: 'book-01.json' },
  { label: 'chapters.json', aristotle: 'chapters.json', classical: 'chapters.json' },
  { label: 'columns.json', aristotle: 'columns.json', classical: 'columns.json' },
  { label: 'analyses.json', aristotle: 'analyses.json', classical: 'analyses.json' },
  { label: 'search/meta.json', aristotle: 'search/meta.json', classical: 'search/meta.json' },
  { label: 'search/english.json', aristotle: 'search/english.json', classical: 'search/english.json' },
  { label: 'search/{greek_form,form}.json', aristotle: 'search/greek_form.json', classical: 'search/form.json' },
  { label: 'search/{greek_lemma,lemma}.json', aristotle: 'search/greek_lemma.json', classical: 'search/lemma.json' },
];

const ARISTOTLE_PROBE_WORKS = ['EN', 'Cat', 'Isa', 'Meta'];
const CLASSICAL_PROBE_WORKS = ['meditations', 'de-finibus', 'heraclitus-fragments', 'de-rerum-natura', 'lives'];

console.log('='.repeat(78));
console.log('(a) NORMALIZED DEEP KEY-PATH DIFF');
console.log('='.repeat(78));
console.log(`aristotle works: ${ARISTOTLE_PROBE_WORKS.join(', ')}`);
console.log(`classical works: ${CLASSICAL_PROBE_WORKS.join(', ')}`);
console.log();

const summaryRows = [];
const allAristotleOnly = new Map(); // path -> Set(work)
const allClassicalOnly = new Map(); // path -> Set(work)

for (const slot of FILE_SLOTS) {
  // Union path sets across all probe works on each side (different works
  // exercise different optional fields -- union catches the full schema).
  const aristotleUnion = new Set();
  const aristotleMissing = [];
  for (const w of ARISTOTLE_PROBE_WORKS) {
    const p = join(ARISTOTLE_DIST, w, slot.aristotle);
    const set = pathSet(p);
    if (set === null) {
      aristotleMissing.push(w);
      continue;
    }
    for (const path of set) aristotleUnion.add(path);
  }

  const classicalUnion = new Set();
  const classicalMissing = [];
  for (const w of CLASSICAL_PROBE_WORKS) {
    const p = join(CLASSICAL_DIST, w, slot.classical);
    const set = pathSet(p);
    if (set === null) {
      classicalMissing.push(w);
      continue;
    }
    for (const path of set) classicalUnion.add(path);
  }

  const aristotleOnly = [...aristotleUnion].filter((p) => !classicalUnion.has(p)).sort();
  const classicalOnly = [...classicalUnion].filter((p) => !aristotleUnion.has(p)).sort();
  const shared = [...aristotleUnion].filter((p) => classicalUnion.has(p)).length;

  for (const p of aristotleOnly) {
    if (!allAristotleOnly.has(p)) allAristotleOnly.set(p, new Set());
    allAristotleOnly.get(p).add(slot.label);
  }
  for (const p of classicalOnly) {
    if (!allClassicalOnly.has(p)) allClassicalOnly.set(p, new Set());
    allClassicalOnly.get(p).add(slot.label);
  }

  summaryRows.push({
    file: slot.label,
    aristotleTotal: aristotleUnion.size,
    classicalTotal: classicalUnion.size,
    shared,
    aristotleOnly: aristotleOnly.length,
    classicalOnly: classicalOnly.length,
    aristotleMissingIn: aristotleMissing.join(',') || '-',
    classicalMissingIn: classicalMissing.join(',') || '-',
  });
}

// Print summary table
const cols = [
  ['file', 20],
  ['aristotleTotal', 8],
  ['classicalTotal', 8],
  ['shared', 8],
  ['aristotleOnly', 8],
  ['classicalOnly', 8],
  ['aristotleMissingIn', 20],
  ['classicalMissingIn', 20],
];
console.log(cols.map(([h, w]) => h.padEnd(w)).join(' | '));
console.log(cols.map(([, w]) => '-'.repeat(w)).join('-|-'));
for (const row of summaryRows) {
  console.log(cols.map(([h, w]) => String(row[h]).padEnd(w)).join(' | '));
}
console.log();

console.log('--- aristotle-only paths (deduped, with which file slots) ---');
for (const [path, slots] of [...allAristotleOnly.entries()].sort()) {
  console.log(`  ${path}  [${[...slots].join(', ')}]`);
}
console.log();
console.log('--- classical-only paths (deduped, with which file slots) ---');
for (const [path, slots] of [...allClassicalOnly.entries()].sort()) {
  console.log(`  ${path}  [${[...slots].join(', ')}]`);
}
console.log();

// ---------------------------------------------------------------------------
// (b) required-file matrix over all 41 aristotle work dirs
// ---------------------------------------------------------------------------

console.log('='.repeat(78));
console.log('(b) REQUIRED-FILE MATRIX -- all aristotle work dirs');
console.log('='.repeat(78));

const REQUIRED_FILES = ['manifest.json', 'analyses.json', 'chapters.json', 'columns.json'];
const workDirs = readdirSync(ARISTOTLE_DIST)
  .filter((name) => {
    const p = join(ARISTOTLE_DIST, name);
    return statSync(p).isDirectory() && existsSync(join(p, 'manifest.json'));
  })
  .sort();

console.log(`Found ${workDirs.length} work dirs with a manifest.json.`);
console.log();

const fileMatrixHeader = ['work', ...REQUIRED_FILES, 'search/', 'book-files', 'manifest.books.len', 'match'];
console.log(fileMatrixHeader.join(' | '));
console.log(fileMatrixHeader.map(() => '---').join(' | '));

let mismatchCount = 0;
for (const work of workDirs) {
  const dir = join(ARISTOTLE_DIST, work);
  const files = readdirSync(dir);
  const presence = REQUIRED_FILES.map((f) => (files.includes(f) ? 'y' : 'MISSING'));
  const hasSearch = files.includes('search') && statSync(join(dir, 'search')).isDirectory() ? 'y' : 'MISSING';
  const bookFileCount = files.filter((f) => /^book-\d+\.json$/.test(f)).length;

  let manifestBooksLen = 'ERR';
  let match = 'ERR';
  try {
    const manifest = readJson(join(dir, 'manifest.json'));
    if (Array.isArray(manifest.books)) {
      manifestBooksLen = manifest.books.length;
      match = manifestBooksLen === bookFileCount ? 'y' : 'MISMATCH';
    } else {
      manifestBooksLen = `not-array(${typeof manifest.books})`;
      match = 'MISMATCH';
    }
  } catch (err) {
    manifestBooksLen = `parse-error: ${err.message}`;
  }
  if (match !== 'y') mismatchCount++;

  console.log([work, ...presence, hasSearch, bookFileCount, manifestBooksLen, match].join(' | '));
}
console.log();
console.log(`Total work dirs: ${workDirs.length}. book-file/manifest.books mismatches: ${mismatchCount}.`);

// Extra files present beyond the required set, per work (informational --
// third-titles.json, footnotes.json, chapter-titles.json, figures.json,
// sidenotes.json all show up here for specific works).
console.log();
console.log('--- extra files beyond the required set (informational) ---');
const KNOWN = new Set([...REQUIRED_FILES, 'search']);
for (const work of workDirs) {
  const dir = join(ARISTOTLE_DIST, work);
  const files = readdirSync(dir).filter((f) => !/^book-\d+\.json$/.test(f) && !KNOWN.has(f));
  if (files.length > 0) console.log(`  ${work}: ${files.join(', ')}`);
}
