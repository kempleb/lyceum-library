#!/usr/bin/env node
// Lyceum Plato mount (docs/todo/plato-mount.md; by analogy with
// scripts/vendor-aristotle-registry.mjs, P3 stage 1 -- that script is NOT
// refactored by this one; helpers used the same way are re-implemented
// locally rather than imported, since importing vendor-aristotle-registry.mjs
// would execute ITS top-level `await main()` as a side effect). Reads the
// sibling plato-reader repo's `shared/lib/works.ts` through a real esbuild
// bundle and writes the three committed YAML inputs this repo's
// build-registry.mjs and mount-corpus.mjs read: corpora/plato/registry.yaml,
// corpora/plato/authors.yaml, corpora/plato/groups.yaml. The sibling repo
// stays read-only. Also writes corpora/plato/mount.yaml (hold: true --
// John's ruling 2026-09-23) if it does not already exist; re-running this
// script never touches a hand-edited mount.yaml.

import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { loadYaml, REPO_ROOT as ROOT } from './lib/load-yaml.mjs';

// Resolved as process.env.PLATO_READER_DIR when set (a git worktree's ROOT
// is .claude/worktrees/<name>, not the real checkout, so `dirname(ROOT)` is
// the worktrees directory, not this repo's actual sibling-repo parent --
// this override lets the script run correctly from a worktree). Falls back
// to the normal sibling-of-ROOT path, and finally to this machine's known
// checkout location (docs/todo/plato-mount.md's brief: `~/Developer/plato-reader`).
const SIBLING_ROOT =
  process.env.PLATO_READER_DIR ??
  (existsSync(join(dirname(ROOT), 'plato-reader'))
    ? join(dirname(ROOT), 'plato-reader')
    : join(process.env.HOME ?? '', 'Developer', 'plato-reader'));
const SIBLING_WORKS = join(SIBLING_ROOT, 'shared', 'lib', 'works.ts');
const OUT_DIR = join(ROOT, 'corpora', 'plato');
const REGISTRY_PATH = join(OUT_DIR, 'registry.yaml');
const AUTHORS_PATH = join(OUT_DIR, 'authors.yaml');
const GROUPS_PATH = join(OUT_DIR, 'groups.yaml');
const MOUNT_PATH = join(OUT_DIR, 'mount.yaml');

const TETRALOGY_NUMERALS = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX'];

// The Work interface fields this script knows how to map. Mirrors
// vendor-aristotle-registry.mjs's HANDLED_SOURCE_FIELDS -- an unrecognized
// field throws rather than silently dropping data. plato-reader's Work type
// has no `language`/`workType` field (neither does aristotle-reader's);
// both are synthesized below, exactly as the aristotle script synthesizes
// them.
const HANDLED_SOURCE_FIELDS = new Set([
  'id',
  'title',
  'greekTitle',
  'abbr',
  'author',
  'books',
  'bookLabels',
  'missingBooks',
  'greekEdition',
  'greekSource',
  'translations',
  'defaultTranslation',
  'blurb',
  'citation',
  'authenticity',
  'related',
  'commentaries',
  'parts',
  'narrator',
  'period',
]);

function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

// Local re-implementation of vendor-aristotle-registry.mjs's DERIVE_SLUG
// (same algorithm) -- duplicated rather than imported, see the module
// docstring.
export function deriveSlug(title) {
  const slug = title
    .normalize('NFKD')
    .replace(/\p{Mark}/gu, '')
    .toLowerCase()
    .replace(/[’']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  if (!slug) {
    throw new Error(`vendor-plato-registry: title '${title}' produced an empty slug.`);
  }
  return slug;
}

async function bundleWorks() {
  const esbuildPath = join(ROOT, 'app', 'node_modules', 'esbuild', 'lib', 'main.js');
  const { default: esbuild } = await import(pathToFileURL(esbuildPath).href);
  const result = await esbuild.build({
    entryPoints: [SIBLING_WORKS],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
    define: {
      'import.meta.env.PUBLIC_SHOW_PRIVATE': 'undefined',
    },
  });
  const dir = mkdtempSync(join(tmpdir(), 'vendor-plato-registry-'));
  const outPath = join(dir, 'works.mjs');
  writeFileSync(outPath, result.outputFiles[0].text);
  return import(pathToFileURL(outPath).href);
}

function assertPlainData(value, path) {
  if (value === null || value === undefined) return;
  const type = typeof value;
  if (type === 'string' || type === 'number' || type === 'boolean') return;
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertPlainData(item, `${path}[${index}]`));
    return;
  }
  if (type === 'object' && value.constructor === Object) {
    for (const [key, item] of Object.entries(value)) {
      assertPlainData(item, `${path}.${key}`);
    }
    return;
  }
  throw new Error(
    `vendor-plato-registry: ${path} is not plain JSON-shaped data (${type}, ${value?.constructor?.name ?? 'unknown'}).`,
  );
}

// ---------------------------------------------------------------------------
// POST_VENDOR_CORRECTIONS -- same shape and purpose as the aristotle script's
// table: a divergence from the sibling's data, applied after mapping and
// before the YAML is written, keyed to the exact value it replaces so a
// stale entry can never misapply.
//
// Shorey's Republic translation (Loeb, 1930-35): translationLicense()'s
// year-cutoff rule (scripts/lib/corpus-adapter/manifest.mjs,
// ARISTOTLE_PD_CUTOFF_YEAR=1930) takes the EARLIEST 4-digit year in the
// name string -- "Paul Shorey (Loeb, 1930-35)" yields 1930, which is
// <= the cutoff and would auto-derive "public-domain-us". That is WRONG:
// John's ruling (CLAUDE.md, 2026-07-28) explicitly moved this one work to a
// "pre-1940" exception and requires it never be described as PD-by-date
// (see sources/perseus-plato/README.md's HARD LICENSING RULE). An explicit
// `license` here overrides the derived guess (manifest.mjs: `t.license ??
// translationLicense(t.name)`), mirroring the same override mechanism the
// aristotle registry uses for Smith/Fyfe (post-1930, left to the auto rule,
// which already answers "unverified" for them -- Shorey needs an EXPLICIT
// override only because its auto-derived answer would otherwise be wrong).
const POST_VENDOR_CORRECTIONS = Object.freeze([
  {
    path: 'Republic.translations.0.id',
    from: 'shorey',
    to: 'shorey',
    reason: "Guard: the next correction writes a licence onto translations[0]; this throws if a sibling reorder moves Shorey.",
  },
  {
    path: 'Republic.translations.0.license',
    from: undefined,
    to: {
      status: 'unverified',
      rationale:
        "Not claimed public domain by date -- John's pre-1940 exception ruling, 2026-07-28 " +
        '(vol. 2 is 1935; vol. 1 is digitized from a 1935-37 printing that may follow Shorey\'s ' +
        '1937 revision). See sources/perseus-plato/README.md.',
    },
    reason: "Shorey's Republic is never described as PD-by-date (John's ruling, 2026-07-28).",
  },
]);

function getAtPath(root, path) {
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), root);
}

function setAtPath(root, path, value) {
  const keys = path.split('.');
  const last = keys.pop();
  const target = keys.reduce((acc, key) => acc[key], root);
  target[last] = value;
}

export function applyPostVendorCorrections(registryDoc) {
  for (const correction of POST_VENDOR_CORRECTIONS) {
    const current = getAtPath(registryDoc.registry, correction.path);
    if (JSON.stringify(current) !== JSON.stringify(correction.from)) {
      throw new Error(
        `vendor-plato-registry: POST_VENDOR_CORRECTIONS[registry.${correction.path}] expected ` +
          `${JSON.stringify(correction.from)}, found ${JSON.stringify(current)} -- the sibling ` +
          'data has drifted; review this correction before rerunning.',
      );
    }
    setAtPath(registryDoc.registry, correction.path, correction.to);
    console.log(`CORRECTION: registry.${correction.path} -- ${correction.reason}`);
  }
}

// Maps one plato-reader Work -> a corpora/plato/registry.yaml work entry.
// Pure function -- no filesystem access -- so it is unit-testable against a
// literal fixture shaped like works.ts, not only the real bundled file.
export function mapWork(work) {
  const unknown = Object.keys(work).filter((key) => !HANDLED_SOURCE_FIELDS.has(key));
  if (unknown.length) {
    throw new Error(`vendor-plato-registry: ${work.id ?? '<unknown>'} has unmapped field(s): ${unknown.join(', ')}`);
  }
  if (work.author !== 'Plato') {
    throw new Error(`vendor-plato-registry: ${work.id}: expected author 'Plato', found '${work.author}'.`);
  }
  if (!work.citation || work.citation.scheme !== 'stephanus') {
    throw new Error(`vendor-plato-registry: ${work.id}: expected citation.scheme 'stephanus', found ${JSON.stringify(work.citation)}.`);
  }

  return {
    id: work.id,
    slug: deriveSlug(work.title),
    title: work.title,
    ...(hasOwn(work, 'greekTitle') ? { greekTitle: work.greekTitle } : {}),
    abbr: work.abbr,
    author: 'plato',
    language: 'grc',
    // Every work is a single continuous dialogue except the Letters, a
    // 13-letter epistolary collection -- the same 'letters' workType value
    // this repo's own Epicurus/Seneca letter manifests already use (e.g.
    // manifests/epistulae-morales.yaml), not invented for this mount.
    workType: work.id === 'Letters' ? 'letters' : 'continuous',
    books: work.books,
    bookLabels: work.bookLabels,
    ...(hasOwn(work, 'missingBooks') ? { missingBooks: work.missingBooks } : {}),
    greekEdition: work.greekEdition,
    greekSource: work.greekSource,
    translations: work.translations,
    ...(hasOwn(work, 'defaultTranslation') ? { defaultTranslation: work.defaultTranslation } : {}),
    citation: work.citation,
    ...(hasOwn(work, 'authenticity') ? { authenticity: work.authenticity } : {}),
    ...(hasOwn(work, 'related') ? { related: work.related } : {}),
    ...(hasOwn(work, 'commentaries') ? { commentaries: work.commentaries } : {}),
    ...(hasOwn(work, 'parts') ? { parts: work.parts } : {}),
    ...(hasOwn(work, 'narrator') ? { narrator: work.narrator } : {}),
    ...(hasOwn(work, 'period') ? { period: work.period } : {}),
    blurb: hasOwn(work, 'blurb') ? work.blurb : '',
  };
}

// Parses the RAW source text of works.ts (comments are stripped by esbuild,
// so this reads the file's text directly, not the bundled module) for its
// `// ---- Tetralogy <roman> ----` section headers and the work ids each
// section declares, in source order. Returns a Map<workId, roman numeral>.
export function parseTetralogyComments(sourceText) {
  const start = sourceText.indexOf('export const WORKS: Work[] = [');
  const end = sourceText.indexOf('\nconst BY_ID');
  if (start === -1 || end === -1 || end <= start) {
    throw new Error('vendor-plato-registry: could not locate the WORKS array bounds in works.ts source text.');
  }
  const body = sourceText.slice(start, end);

  const headerRe = /\/\/ ---- Tetralogy (\w+) ----/g;
  const headers = [...body.matchAll(headerRe)].map((m) => ({ numeral: m[1], index: m.index }));
  if (headers.length === 0) {
    throw new Error('vendor-plato-registry: no "// ---- Tetralogy <roman> ----" comments found in works.ts.');
  }

  const idRe = /id:\s*'([A-Za-z0-9]+)'/g;
  const map = new Map();
  for (let i = 0; i < headers.length; i += 1) {
    const sectionStart = headers[i].index;
    const sectionEnd = i + 1 < headers.length ? headers[i + 1].index : body.length;
    const section = body.slice(sectionStart, sectionEnd);
    idRe.lastIndex = 0;
    let match;
    while ((match = idRe.exec(section))) {
      map.set(match[1], headers[i].numeral);
    }
  }
  return map;
}

// Chunks `works` (in their WORKS array order) into 9 groups of 4, "Tetralogy
// I".."Tetralogy IX" -- the traditional Thrasyllan division -- and CHECKS
// the chunking against `commentMap` (parseTetralogyComments' output),
// throwing loudly on any disagreement rather than silently trusting either
// source alone.
export function deriveTetralogyGroups(works, commentMap) {
  if (works.length !== 36) {
    throw new Error(`vendor-plato-registry: expected 36 works to group into tetralogies, found ${works.length}.`);
  }
  const groups = [];
  for (let g = 0; g < 9; g += 1) {
    const numeral = TETRALOGY_NUMERALS[g];
    const chunk = works.slice(g * 4, g * 4 + 4);
    for (const work of chunk) {
      const commentNumeral = commentMap.get(work.id);
      if (commentNumeral == null) {
        throw new Error(`vendor-plato-registry: work '${work.id}' has no source-comment tetralogy (order says ${numeral}).`);
      }
      if (commentNumeral !== numeral) {
        throw new Error(
          `vendor-plato-registry: order-derived Tetralogy ${numeral} for '${work.id}' disagrees with its ` +
            `source comment (Tetralogy ${commentNumeral}).`,
        );
      }
    }
    groups.push({ numeral, title: `Tetralogy ${numeral}`, works: chunk.map((w) => w.id) });
  }
  return groups;
}

// ---------------------------------------------------------------------------
// Tetralogy III order correction -- Diogenes Laertius 3.58 gives Thrasyllus's
// third tetralogy as Parmenides, Philebus, Symposium, Phaedrus. The sibling
// plato-reader repo's shared/lib/works.ts (read-only; never edited from this
// repo) lists the same four works in a different order -- Symposium,
// Parmenides, Philebus, Phaedrus. John's ruling, 2026-09-23: emit the
// traditional DL 3.58 order on our side; every other tetralogy already
// matches DL 3.58-61 and is left untouched. This is declarative and keyed to
// the exact source order it replaces, mirroring POST_VENDOR_CORRECTIONS --
// it throws rather than silently reordering if the sibling's Tetralogy III
// membership (per its own `// ---- Tetralogy III ----` source comment) is
// not exactly these four works, or if they are not contiguous in the
// source's declared order.
const TETRALOGY_III_SOURCE_ORDER = ['Symposium', 'Parmenides', 'Philebus', 'Phaedrus'];
const TETRALOGY_III_CORRECTED_ORDER = ['Parmenides', 'Philebus', 'Symposium', 'Phaedrus'];

export function applyTetralogyIIIOrderCorrection(works, commentMap) {
  const iiiMembers = works.filter((w) => commentMap.get(w.id) === 'III').map((w) => w.id);
  const sourceSet = new Set(TETRALOGY_III_SOURCE_ORDER);
  const memberSet = new Set(iiiMembers);
  const sameMembership =
    iiiMembers.length === 4 &&
    memberSet.size === 4 &&
    [...sourceSet].every((id) => memberSet.has(id));
  if (!sameMembership) {
    throw new Error(
      `vendor-plato-registry: Tetralogy III order correction expected exactly the source's ` +
        `own comment-declared members [${TETRALOGY_III_SOURCE_ORDER.join(', ')}], found ` +
        `[${iiiMembers.join(', ')}] -- the sibling data has drifted; review this correction ` +
        'before rerunning.',
    );
  }

  const indices = TETRALOGY_III_SOURCE_ORDER.map((id) => works.findIndex((w) => w.id === id));
  const start = Math.min(...indices);
  const actualBlock = works.slice(start, start + 4).map((w) => w.id);
  if (JSON.stringify(actualBlock) !== JSON.stringify(TETRALOGY_III_SOURCE_ORDER)) {
    throw new Error(
      `vendor-plato-registry: Tetralogy III order correction expected a contiguous source-order ` +
        `block [${TETRALOGY_III_SOURCE_ORDER.join(', ')}] at index ${start}, found ` +
        `[${actualBlock.join(', ')}] -- the sibling data has drifted; review this correction ` +
        'before rerunning.',
    );
  }

  const byId = new Map(works.map((w) => [w.id, w]));
  const correctedBlock = TETRALOGY_III_CORRECTED_ORDER.map((id) => byId.get(id));
  const result = works.slice();
  result.splice(start, 4, ...correctedBlock);
  console.log(
    `CORRECTION: Tetralogy III order -- ${TETRALOGY_III_SOURCE_ORDER.join(', ')} -> ` +
      `${TETRALOGY_III_CORRECTED_ORDER.join(', ')} (DL 3.58; John's ruling, 2026-09-23).`,
  );
  return result;
}

export function assertRegistry(works) {
  if (works.length !== 36) {
    throw new Error(`vendor-plato-registry: expected 36 works, found ${works.length}.`);
  }
  const ids = new Set();
  const routes = new Set();
  for (const work of works) {
    if (!work.id || !work.title || !work.author || !work.language) {
      throw new Error(`vendor-plato-registry: ${work.id ?? '<unknown>'} lacks a required field.`);
    }
    if (work.citation?.scheme !== 'stephanus') {
      throw new Error(`vendor-plato-registry: ${work.id}: citation.scheme must be 'stephanus'.`);
    }
    if (ids.has(work.id)) {
      throw new Error(`vendor-plato-registry: duplicate work id '${work.id}'.`);
    }
    ids.add(work.id);
    const route = `${work.author}/${work.slug}`.toLocaleLowerCase('en-US');
    if (routes.has(route)) {
      throw new Error(`vendor-plato-registry: duplicate author/slug route '${route}'.`);
    }
    routes.add(route);
  }
  const dubious = works.filter((w) => w.authenticity === 'dubious').map((w) => w.id);
  if (dubious.length !== 10) {
    throw new Error(`vendor-plato-registry: expected 10 dubious works, found ${dubious.length}: ${dubious.join(', ')}.`);
  }
}

async function main() {
  if (!existsSync(SIBLING_WORKS)) {
    throw new Error(`vendor-plato-registry: sibling file not found: ${SIBLING_WORKS} (is ../plato-reader checked out?).`);
  }

  const yaml = await loadYaml();
  const sourceText = readFileSync(SIBLING_WORKS, 'utf8');

  const bundled = await bundleWorks();
  assertPlainData(bundled.WORKS, 'WORKS');
  if (!Array.isArray(bundled.WORKS)) {
    throw new Error('vendor-plato-registry: sibling WORKS is not an array.');
  }

  const works = bundled.WORKS.map(mapWork);
  assertRegistry(works);

  const commentMap = parseTetralogyComments(sourceText);
  const orderedWorks = applyTetralogyIIIOrderCorrection(works, commentMap);
  const groups = deriveTetralogyGroups(orderedWorks, commentMap);

  const workOrder = orderedWorks.map((w) => w.id);

  const registryDoc = { registry: Object.fromEntries(orderedWorks.map((w) => [w.id, w])) };
  applyPostVendorCorrections(registryDoc);

  const authorsDoc = {
    authors: [
      {
        id: 'plato',
        name: 'Plato',
        nativeName: 'Πλάτων',
        languages: ['grc'],
        period: 'classical',
        schools: [],
        floruit: 'c. 428/427–348/347 BC',
        blurb: '',
        works: workOrder,
        // The full 36-work Thrasyllan canon -- the traditional standard
        // collection this site carries against -- is present (works.ts's
        // own comment: "The full 36-work Thrasyllan canon is carried").
        holdings: 'complete',
      },
    ],
    work_order: workOrder,
  };

  const groupsDoc = { groups };

  mkdirSync(OUT_DIR, { recursive: true });
  const dumpOptions = { sortKeys: false, lineWidth: -1, noRefs: true };
  writeFileSync(REGISTRY_PATH, yaml.dump(registryDoc, dumpOptions));
  writeFileSync(AUTHORS_PATH, yaml.dump(authorsDoc, dumpOptions));
  writeFileSync(GROUPS_PATH, yaml.dump(groupsDoc, dumpOptions));

  if (!existsSync(MOUNT_PATH)) {
    const mountYaml = `# Lyceum Plato mount (docs/todo/plato-mount.md). Mount configuration for the
# plato corpus: where its built data lives on this machine, and what
# mount-corpus.mjs excludes when it flat-merges the corpus's work
# directories into build/dist alongside the classical and aristotle works.
#
# HOLD (John's ruling, 2026-09-23): Plato stays out of any release sent to
# the test copy until he lifts the hold. mount-corpus.mjs skips a held
# corpus (clean no-op, logged) unless READER_INCLUDE_HELD=1 is set in its
# environment.
hold: true

corpus: plato

# Resolved as: process.env[source_env] ?? source_default, relative to this
# repo's root. The sibling repo is read-only; nothing here is ever written
# back to it (see mount-corpus.mjs's realpath(dest)-inside-this-repo assert).
source_env: PLATO_DATA_DIR
source_default: ../plato-reader/build/dist

# Top-level entries under the source directory that are never copied into
# build/dist -- documentary, mirroring corpora/aristotle/mount.yaml's own
# list: the per-work copy loop only ever copies sourceDir/<workId>, so none
# of these are structurally reachable by mount-corpus.mjs's copy step
# either way. lsj-heads.json is listed explicitly (aristotle's own list
# omits it) because nothing in this repo reads a top-level lsj-heads.json
# for the aristotle mount either (grepped scripts/ and pipeline/ -- zero
# hits) -- it is dead weight for both corpora, excluded rather than carried
# on the "why ship what nothing reads" principle. lsj/ is deliberately
# absent from this list -- it is merged key-by-key via
# corpus-adapter/lsj-merge.mjs, not copied or excluded wholesale.
exclude:
  - lemmata
  - lemmata.json
  - lemma-map
  - ngrams
  - reports
  - lsj-heads.json

# Per-work search/ subdirectory entries that are never copied. Mirrors
# corpora/aristotle/mount.yaml -- no consumer in this repo's reader.
search_exclude:
  - offsets.json
  - grammar-dict.json
  - grammar-col.bin

citationRoutes: true
`;
    writeFileSync(MOUNT_PATH, mountYaml);
    console.log('Wrote corpora/plato/mount.yaml (hold: true).');
  } else {
    console.log('corpora/plato/mount.yaml already exists -- left untouched.');
  }

  console.log(
    `Wrote corpora/plato/{registry,authors,groups}.yaml: ${works.length} works, 1 author, ` +
      `${groups.length} tetralogy groups.`,
  );
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
