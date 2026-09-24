#!/usr/bin/env node
// Lyceum P2 stage 1 (docs/p2-plan.md §3) -- ONE-TIME extractor. Turns the
// literal data currently living in shared/lib/works.ts / authors.ts into
// committed YAML, so scripts/build-registry.mjs (the generator that runs on
// every future build) has real repo data to read instead of TypeScript
// source. Run once, then never again against the same manifests -- rerunning
// refuses to double-append (see assertNoExistingBlock below). Kept committed
// for audit; not wired into any build.
//
// Loads works.ts/authors.ts for REAL via an esbuild bundle -- never a regex
// scrape of the source, which would drift the moment the TypeScript's shape
// changes (see check-manifest-translations.mjs's own note on why, and its
// matching esbuild technique, generalized here). Two `import.meta.env` reads
// need a build-time `define`: PUBLIC_SHOW_PRIVATE (left undefined --
// unrelated to registry SHAPE, only to which translations render) and
// PUBLIC_READER_FIXTURES, deliberately turned ON here (unlike
// check-manifest-translations.mjs) so this single bundle also yields the
// synthetic sample-work/sample-author fixture entries this script needs to
// write out to fixtures/manifests/.
//
// Writes:
//   - manifests/<id>.yaml: a verbatim `registry:` block appended to each of
//     the 62 corpus works' existing pipeline manifest (APPEND ONLY -- every
//     existing line stays byte-identical; the pipeline-keys diff is empty).
//   - manifests/authors.yaml (new file): the 28 corpus AUTHORS, SCHOOL_GROUP_ORDER,
//     and an explicit `work_order` list. work_order is NOT in the plan's
//     literal "authors + school_groups" phrasing -- documented deviation: the
//     real shared/lib/works.ts WORKS array order does NOT reduce to "authors
//     in AUTHORS order, each author's works in its own order" (Lucretius'
//     lone work, de-rerum-natura, is interleaved into the middle of Cicero's
//     ten), so build-registry.mjs needs an explicit, order-preserving list to
//     reconstruct CORPUS_WORKS byte-for-byte (JSON.stringify order-sensitive
//     round-trip, plan §3) -- there is no other lossless way to recover it.
//   - fixtures/manifests/sample-work.yaml, fixtures/manifests/authors.yaml
//     (new files, new directory): the FIXTURES_ON synthetic work+author, in
//     the SAME `registry:`-block / `authors:`+`school_groups:` shape as the
//     corpus files, so build-registry.mjs's yamlManifestSource reads fixtures
//     as "just another manifest source" with no special-casing.
//   - fixtures/taxonomy.json (new file): `taxonomy`
//     (AUTHOR_PERIOD_ORDER/PERIOD_LABEL/SCHOOL_LABEL) and `start_here`
//     (works.ts's START_HERE, currently []) -- schemas/snapshot.v1.json validates it.

import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { loadYaml, REPO_ROOT as ROOT } from './lib/load-yaml.mjs';

const MANIFESTS = join(ROOT, 'manifests');
const FIXTURE_MANIFESTS = join(ROOT, 'fixtures', 'manifests');
const TAXONOMY_PATH = join(ROOT, 'fixtures', 'taxonomy.json');

async function bundleModule(relPath, define) {
  const esbuildPath = join(ROOT, 'app', 'node_modules', 'esbuild', 'lib', 'main.js');
  const { default: esbuild } = await import(pathToFileURL(esbuildPath).href);
  const result = await esbuild.build({
    entryPoints: [join(ROOT, relPath)],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
    define,
  });
  const dir = mkdtempSync(join(tmpdir(), 'extract-registry-'));
  const outPath = join(dir, 'mod.mjs');
  writeFileSync(outPath, result.outputFiles[0].text);
  return import(pathToFileURL(outPath).href);
}

async function loadRegistrySources() {
  // FIXTURES ON for this extraction bundle only, so WORKS/AUTHORS carry the
  // synthetic sample-work/sample-author entries too (appended last -- see
  // works.ts/authors.ts's own `...FIXTURE_WORKS`/`...FIXTURE_AUTHORS` spread
  // at the end of each array).
  const define = {
    'import.meta.env.PUBLIC_SHOW_PRIVATE': 'undefined',
    'import.meta.env.PUBLIC_READER_FIXTURES': "'1'",
  };
  const worksMod = await bundleModule('shared/lib/works.ts', define);
  const authorsMod = await bundleModule('shared/lib/authors.ts', define);
  return { worksMod, authorsMod };
}

// A JS/Work-field value the extractor doesn't recognize how to serialize
// losslessly (a function, a Map, a class instance, a Symbol...) -- none
// exist in works.ts/authors.ts today (both are plain JSON-shaped data), but
// per the task brief this is a STOP, not an improvised serialization.
function assertPlainData(value, path) {
  if (value === null || value === undefined) return;
  const t = typeof value;
  if (t === 'string' || t === 'number' || t === 'boolean') return;
  if (Array.isArray(value)) {
    value.forEach((v, i) => assertPlainData(v, `${path}[${i}]`));
    return;
  }
  if (t === 'object' && value.constructor === Object) {
    for (const [k, v] of Object.entries(value)) assertPlainData(v, `${path}.${k}`);
    return;
  }
  throw new Error(
    `extract-registry: field ${path} is a ${t} (${value?.constructor?.name ?? 'unknown'}), ` +
      `not plain JSON-shaped data -- stopping rather than improvising a serialization ` +
      `(see the task brief's stop condition).`,
  );
}

function indent(text, spaces) {
  const pad = ' '.repeat(spaces);
  return text
    .replace(/\n$/, '')
    .split('\n')
    .map((l) => (l.length ? pad + l : l))
    .join('\n');
}

function assertNoExistingBlock(filePath, text, key) {
  const re = new RegExp(`^${key}:\\s*$`, 'm');
  if (re.test(text)) {
    throw new Error(
      `extract-registry: ${filePath} already has a top-level \`${key}:\` block -- ` +
        `refusing to double-append (this script is one-time; delete the block to rerun).`,
    );
  }
}

function appendYamlBlock(filePath, key, value, yaml) {
  const original = readFileSync(filePath, 'utf8');
  assertNoExistingBlock(filePath, original, key);
  const dumped = yaml.dump(value, { sortKeys: false, lineWidth: -1, noRefs: true });
  const block = `${key}:\n${indent(dumped, 2)}\n`;
  const trimmed = original.replace(/\s+$/, '');
  writeFileSync(filePath, `${trimmed}\n\n${block}`);
}

function writeYamlDoc(filePath, doc, yaml) {
  if (existsSync(filePath)) {
    throw new Error(`extract-registry: ${filePath} already exists -- refusing to overwrite.`);
  }
  const dumped = yaml.dump(doc, { sortKeys: false, lineWidth: -1, noRefs: true });
  writeFileSync(filePath, dumped);
}

async function main() {
  const yaml = await loadYaml();
  const { worksMod, authorsMod } = await loadRegistrySources();

  const allWorks = worksMod.WORKS;
  const allAuthors = authorsMod.AUTHORS;
  assertPlainData(allWorks, 'WORKS');
  assertPlainData(allAuthors, 'AUTHORS');

  const fixtureWork = allWorks.find((w) => w.id === 'sample-work');
  const corpusWorks = allWorks.filter((w) => w.id !== 'sample-work');
  const fixtureAuthor = allAuthors.find((a) => a.id === 'sample-author');
  const corpusAuthors = allAuthors.filter((a) => a.id !== 'sample-author');

  if (!fixtureWork) throw new Error('extract-registry: no sample-work fixture found in WORKS (FIXTURES_ON define did not take).');
  if (!fixtureAuthor) throw new Error('extract-registry: no sample-author fixture found in AUTHORS (FIXTURES_ON define did not take).');

  console.log(`Extracting ${corpusWorks.length} corpus works, ${corpusAuthors.length} corpus authors, 1 fixture work, 1 fixture author.`);

  // 1. Append `registry:` to each corpus work's existing manifests/<id>.yaml.
  for (const work of corpusWorks) {
    const manifestPath = join(MANIFESTS, `${work.id}.yaml`);
    if (!existsSync(manifestPath)) {
      throw new Error(`extract-registry: no manifests/${work.id}.yaml for WORKS entry '${work.id}'.`);
    }
    appendYamlBlock(manifestPath, 'registry', work, yaml);
  }
  console.log(`Appended registry: blocks to ${corpusWorks.length} manifests/*.yaml files.`);

  // 2. manifests/authors.yaml -- corpus authors + SCHOOL_GROUP_ORDER + the
  // explicit work order (see header doc comment for why this third key
  // exists).
  const authorsDoc = {
    authors: corpusAuthors,
    school_groups: authorsMod.SCHOOL_GROUP_ORDER,
    work_order: corpusWorks.map((w) => w.id),
  };
  writeYamlDoc(join(MANIFESTS, 'authors.yaml'), authorsDoc, yaml);
  console.log('Wrote manifests/authors.yaml.');

  // 3. fixtures/manifests/{sample-work,authors}.yaml.
  mkdirSync(FIXTURE_MANIFESTS, { recursive: true });
  writeYamlDoc(join(FIXTURE_MANIFESTS, 'sample-work.yaml'), { registry: fixtureWork }, yaml);
  writeYamlDoc(
    join(FIXTURE_MANIFESTS, 'authors.yaml'),
    { authors: [fixtureAuthor], school_groups: {}, work_order: [fixtureWork.id] },
    yaml,
  );
  console.log('Wrote fixtures/manifests/sample-work.yaml and fixtures/manifests/authors.yaml.');

  // 4. fixtures/taxonomy.json: taxonomy, start_here.
  if (existsSync(TAXONOMY_PATH)) {
    throw new Error(`extract-registry: ${TAXONOMY_PATH} already exists -- refusing to overwrite.`);
  }
  assertPlainData(authorsMod.AUTHOR_PERIOD_ORDER, 'AUTHOR_PERIOD_ORDER');
  assertPlainData(authorsMod.PERIOD_LABEL, 'PERIOD_LABEL');
  assertPlainData(authorsMod.SCHOOL_LABEL, 'SCHOOL_LABEL');
  assertPlainData(worksMod.START_HERE, 'START_HERE');
  const taxonomyFile = {
    schema_version: 'taxonomy.v1',
    taxonomy: {
      author_period_order: authorsMod.AUTHOR_PERIOD_ORDER,
      period_label: authorsMod.PERIOD_LABEL,
      school_label: authorsMod.SCHOOL_LABEL,
    },
    start_here: worksMod.START_HERE,
  };
  writeFileSync(TAXONOMY_PATH, `${JSON.stringify(taxonomyFile, null, 2)}\n`);
  console.log('Wrote fixtures/taxonomy.json with taxonomy + start_here.');
}

await main();
