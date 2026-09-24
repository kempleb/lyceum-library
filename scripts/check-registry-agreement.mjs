#!/usr/bin/env node
// Lyceum P2 (docs/p2-plan.md §5, stage 3): assert that each per-work YAML
// manifest's duplicated registry block agrees with its pipeline fields.
// This is YAML-vs-YAML only: it does not load TypeScript, corpus data, or
// esbuild, so CI can run it before any corpus build.

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { loadYaml, REPO_ROOT as ROOT } from './lib/load-yaml.mjs';

const MANIFESTS = join(ROOT, 'manifests');
const hasOwn = (value, key) => value != null && Object.hasOwn(value, key);
const shown = (value) => value === undefined ? '<missing>' : JSON.stringify(value);

function translationEntries(english) {
  if (!english) return [];
  const entries = [];
  for (const [key, slot] of [
    ['primary', 'english'],
    ['secondary', 'secondary'],
    ['third', 'third'],
  ]) {
    if (english[key]?.id) entries.push({ id: english[key].id, slot, source: `english.${key}` });
  }
  for (const [index, overlay] of (english.overlays ?? []).entries()) {
    if (overlay?.id) entries.push({ id: overlay.id, slot: 'overlay', source: `english.overlays[${index}]` });
  }
  // Existing Gorgias data predates overlays[] but represents the same
  // display slot. Keep it in the two-way agreement check.
  if (english.summary_overlay?.id) {
    entries.push({ id: english.summary_overlay.id, slot: 'overlay', source: 'english.summary_overlay' });
  }
  return entries;
}

function checkManifest(doc, manifestFile) {
  const problems = [];
  const workId = doc?.work?.id ?? manifestFile.replace(/\.yaml$/, '');
  const registry = doc?.registry;
  const work = doc?.work;
  const fail = (message) => problems.push(`${workId}: ${message} (${manifestFile})`);
  const equal = (label, actual, expected) => {
    if (actual !== expected) fail(`${label} is ${shown(actual)}; expected ${shown(expected)}`);
  };

  if (!registry) {
    fail('missing registry block');
    return problems;
  }

  equal('registry.id', registry.id, work?.id);
  equal('registry.title', registry.title, work?.title);
  equal('registry.author', registry.author, work?.author);
  equal('registry.language', registry.language, work?.language);
  equal('registry.greekEdition', registry.greekEdition, work?.greek_edition || work?.latin_edition);

  if (hasOwn(registry, 'books') && hasOwn(doc, 'books')) {
    if (!Array.isArray(doc.books)) {
      fail(`books is ${shown(doc.books)}; expected an array before comparing registry.books`);
    } else {
      equal('registry.books', registry.books, doc.books.length);
    }
  }

  equal('registry.citation.scheme', registry.citation?.scheme, doc?.citation?.scheme);
  if (hasOwn(registry.citation, 'hideLineNumbers') && hasOwn(doc?.citation, 'hideLineNumbers')) {
    equal(
      'registry.citation.hideLineNumbers',
      registry.citation.hideLineNumbers,
      doc.citation.hideLineNumbers,
    );
  }

  const manifestTranslations = translationEntries(doc?.english);
  const registryTranslations = Array.isArray(registry.translations) ? registry.translations : [];
  if (!Array.isArray(registry.translations)) {
    fail(`registry.translations is ${shown(registry.translations)}; expected an array`);
  }

  const manifestById = new Map();
  for (const entry of manifestTranslations) {
    if (manifestById.has(entry.id)) {
      fail(`translation id ${shown(entry.id)} is declared more than once in english entries`);
    } else {
      manifestById.set(entry.id, entry);
    }
  }

  const registryById = new Map();
  const nonOverlaySlots = new Map();
  for (const entry of registryTranslations) {
    if (!entry?.id) {
      fail(`registry translation has no id: ${shown(entry)}`);
      continue;
    }
    if (registryById.has(entry.id)) {
      fail(`registry translation id ${shown(entry.id)} is declared more than once`);
    } else {
      registryById.set(entry.id, entry);
    }
    if (entry.slot !== 'overlay') {
      if (nonOverlaySlots.has(entry.slot)) {
        fail(
          `registry translation slot ${shown(entry.slot)} is used by both ` +
          `${shown(nonOverlaySlots.get(entry.slot))} and ${shown(entry.id)}`,
        );
      } else {
        nonOverlaySlots.set(entry.slot, entry.id);
      }
    }
  }

  for (const entry of manifestTranslations) {
    const match = registryById.get(entry.id);
    if (!match) {
      fail(`${entry.source} translation ${shown(entry.id)} has no registry translation`);
    } else if (match.slot !== entry.slot) {
      fail(
        `registry translation ${shown(entry.id)} has slot ${shown(match.slot)}; ` +
        `${entry.source} requires ${shown(entry.slot)}`,
      );
    }
  }

  for (const entry of registryTranslations) {
    if (!entry?.id) continue;
    const match = manifestById.get(entry.id);
    if (!match) {
      fail(`registry translation ${shown(entry.id)} has no matching english entry`);
    } else if (entry.slot !== match.slot) {
      fail(
        `registry translation ${shown(entry.id)} has slot ${shown(entry.slot)}; ` +
        `${match.source} requires ${shown(match.slot)}`,
      );
    }
  }

  return problems;
}

async function loadManifestDocuments() {
  const yaml = await loadYaml();
  return readdirSync(MANIFESTS)
    .filter((name) => name.endsWith('.yaml') && !name.endsWith('-public.yaml') && name !== 'authors.yaml')
    .sort((a, b) => a.localeCompare(b))
    .map((name) => ({
      name,
      doc: yaml.load(readFileSync(join(MANIFESTS, name), 'utf8')),
    }));
}

export async function checkRegistryAgreement() {
  const manifests = await loadManifestDocuments();
  const registryBlocks = manifests.filter(({ doc }) => doc?.registry).length;
  const results = manifests.map(({ name, doc }) => ({ name, problems: checkManifest(doc, name) }));
  const problems = results.flatMap(({ problems: manifestProblems }) => manifestProblems);

  if (manifests.length > 0 && registryBlocks === 0) {
    problems.unshift(
      `sanity floor: ${manifests.length} manifest(s) exist under manifests/ but zero registry blocks were found`,
    );
  }

  return {
    checked: manifests.length,
    agreed: results.filter(({ problems: manifestProblems }) => manifestProblems.length === 0).length,
    registryBlocks,
    problems,
  };
}

async function runSelfTest() {
  const manifests = await loadManifestDocuments();
  const source = manifests.find(({ doc }) => Array.isArray(doc?.registry?.translations) && doc.registry.translations.length >= 2);
  if (!source) throw new Error('self-test needs a loaded manifest with at least two registry translations');

  const cases = [
    {
      name: 'changed title',
      mutate(doc) { doc.registry.title = `${doc.registry.title} (corrupt)`; },
      caught(problems) { return problems.some((problem) => problem.includes('registry.title')); },
    },
    {
      name: 'dropped translation',
      mutate(doc) { doc.registry.translations.pop(); },
      caught(problems) { return problems.some((problem) => problem.includes('has no registry translation')); },
    },
    {
      name: 'duplicate slot',
      mutate(doc) { doc.registry.translations[1].slot = doc.registry.translations[0].slot; },
      caught(problems) {
        return problems.some((problem) => problem.includes('registry translation slot') && problem.includes('used by both'));
      },
    },
  ];

  const missed = [];
  for (const testCase of cases) {
    const corrupted = structuredClone(source.doc);
    testCase.mutate(corrupted);
    const problems = checkManifest(corrupted, source.name);
    if (!testCase.caught(problems)) missed.push(testCase.name);
  }

  if (missed.length) {
    console.error(`Registry agreement self-test failed to catch: ${missed.join(', ')}`);
    return false;
  }
  console.log('Registry agreement self-test: all corruptions caught.');
  return true;
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  if (process.argv.includes('--self-test')) {
    process.exit((await runSelfTest()) ? 0 : 1);
  }

  const result = await checkRegistryAgreement();
  console.log(`Registry agreement: ${result.agreed}/${result.checked} agree.`);
  for (const problem of result.problems) console.error(`  ${problem}`);
  process.exit(result.problems.length ? 1 : 0);
}
