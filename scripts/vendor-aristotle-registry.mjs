#!/usr/bin/env node
// Lyceum P3 stage 1 (docs/p3-plan.md, Stage sequence 1) -- one-time,
// committed vendor script. It reads the sibling aristotle-reader registry
// through a real esbuild bundle and writes the two committed YAML inputs used
// by scripts/build-registry.mjs. The sibling repo stays read-only.

import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { loadYaml, REPO_ROOT as ROOT } from './lib/load-yaml.mjs';

const SIBLING_WORKS = join(dirname(ROOT), 'aristotle-reader', 'shared', 'lib', 'works.ts');
const OUT_DIR = join(ROOT, 'corpora', 'aristotle');
const REGISTRY_PATH = join(OUT_DIR, 'registry.yaml');
const AUTHORS_PATH = join(OUT_DIR, 'authors.yaml');
const GROUPS_PATH = join(OUT_DIR, 'groups.yaml');

// Add a title here only when the normal derivation cannot yield the wanted
// route (for example, a title made only of Greek text or one whose parentheses
// must affect the route). Every override is reported when the script runs.
const OVERRIDES = Object.freeze({});

const HANDLED_SOURCE_FIELDS = new Set([
  'id',
  'title',
  'greekTitle',
  'abbr',
  'author',
  'language',
  'workType',
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
  // Sibling reader feature flag (curated quotation citations for the
  // Metaphysics, added 2026-09; the sibling fetches quotations.json when
  // set). Not rendered by this reader, so it is recognised and dropped.
  'quotations',
]);

function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

export function DERIVE_SLUG(title) {
  if (hasOwn(OVERRIDES, title)) return OVERRIDES[title];
  const slug = title
    .normalize('NFKD')
    .replace(/\p{Mark}/gu, '')
    .toLowerCase()
    .replace(/[’']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  if (!slug) {
    throw new Error(
      `vendor-aristotle-registry: title '${title}' needs an explicit OVERRIDES entry.`,
    );
  }
  return slug;
}

async function bundleWorks(publicShowPrivate) {
  const esbuildPath = join(ROOT, 'app', 'node_modules', 'esbuild', 'lib', 'main.js');
  const { default: esbuild } = await import(pathToFileURL(esbuildPath).href);
  const result = await esbuild.build({
    entryPoints: [SIBLING_WORKS],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
    define: {
      'import.meta.env.PUBLIC_SHOW_PRIVATE': publicShowPrivate,
    },
  });
  const dir = mkdtempSync(join(tmpdir(), 'vendor-aristotle-registry-'));
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
    `vendor-aristotle-registry: ${path} is not plain JSON-shaped data ` +
      `(${type}, ${value?.constructor?.name ?? 'unknown'}).`,
  );
}

function assertPrivateBundleOnlyAddsPrivateTranslations(publicWorks, fullWorks) {
  const withoutPrivate = fullWorks.map((work) => ({
    ...work,
    translations: work.translations.filter((translation) => !translation.private),
  }));
  if (JSON.stringify(publicWorks) !== JSON.stringify(withoutPrivate)) {
    throw new Error(
      'vendor-aristotle-registry: PUBLIC_SHOW_PRIVATE=1 changed data other than ' +
        'adding translations marked private:true.',
    );
  }
}

// ---------------------------------------------------------------------------
// POST_VENDOR_CORRECTIONS
//
// The sibling registry is a straight extraction of their works.ts and is not
// always philologically correct (a wrong edition label, a year that drifted
// between fields, a period/school classification this repo's house style
// disagrees with). Hand-editing the generated YAML would be silently undone
// by the next vendor run, so every such divergence lives here instead, keyed
// to the exact value it replaces. `applyPostVendorCorrections` runs after
// mapping and before the YAML is written, and throws if the current value
// does not match `from` -- either the sibling's data moved out from under us,
// or the correction already landed -- so a stale entry can never misapply.
//
// `doc` selects which document `path` is read from: 'registry' (dotted path
// into registryDoc.registry, work id first) or 'authors' (dotted path
// addressed by author id, into the authorsDoc.authors array). A numeric
// path segment (e.g. `EN.translations.2.license`) addresses an array
// element -- plain bracket access on a JS array already accepts a numeric
// string key, so getAtPath/setAtPath need no special-casing for it.
// `from: undefined` means "the key must currently be absent": JSON.stringify
// of an absent/undefined value is the JS value `undefined` on both sides of
// the comparison below, so the check passes only when nothing is there yet,
// and throws (data drift, or the correction already landed) otherwise.
const POST_VENDOR_CORRECTIONS = Object.freeze([
  {
    doc: 'registry',
    path: 'Meta.greekEdition',
    from: 'Ross, Aristotle’s Metaphysics (OCT, 1924)',
    to: 'Ross, Aristotle’s Metaphysics (Oxford, 1924)',
    reason:
      "Ross 1924 is the Clarendon revised text with commentary, not an Oxford " +
      'Classical Text (OCT Metaphysica = Jaeger 1957); year aligned across fields.',
  },
  {
    doc: 'registry',
    path: 'Meta.greekSource.short',
    from: 'Ross (OCT, 1953)',
    to: 'Ross (1924)',
    reason:
      "Ross 1924 is the Clarendon revised text with commentary, not an Oxford " +
      'Classical Text (OCT Metaphysica = Jaeger 1957); year aligned across fields.',
  },
  {
    doc: 'registry',
    path: 'Meta.greekSource.full',
    from: 'W. D. Ross, ed. Aristotle’s Metaphysics. 2 vols. Oxford: Clarendon Press, 1953.',
    to: 'W. D. Ross, ed. Aristotle’s Metaphysics. 2 vols. Oxford: Clarendon Press, 1924 (corr. repr. 1953).',
    reason:
      "Ross 1924 is the Clarendon revised text with commentary, not an Oxford " +
      'Classical Text (OCT Metaphysica = Jaeger 1957); year aligned across fields ' +
      '(the OCT label is dropped; the 1953 reprint detail the sibling carried is kept).',
  },
  {
    doc: 'registry',
    path: 'Poet.greekSource.short',
    from: 'Kassel (OCT, 1966)',
    to: 'Kassel (OCT, 1965)',
    reason: 'greekEdition already reads 1965 and the OCT label is correct here; only the year drifted.',
  },
  {
    doc: 'authors',
    path: 'porphyry.period',
    from: 'imperial',
    to: 'late-antique',
    reason:
      'Porphyry is the paradigm late-antique Neoplatonist; the registry’s own Isagoge ' +
      'description already calls him late-antique. (John may veto this call.)',
  },
  {
    doc: 'authors',
    path: 'porphyry.floruit',
    from: 'c. 234–305 AD',
    to: 'c. AD 234–305',
    reason: 'house style puts the era marker before the year range.',
  },
  {
    doc: 'authors',
    path: 'porphyry.schools',
    from: [],
    to: ['neoplatonist'],
    reason: 'sibling leaves schools empty; Porphyry is classed as a Neoplatonist.',
  },
  {
    doc: 'authors',
    path: 'aristotle.schools',
    from: [],
    to: ['peripatetic'],
    reason: 'sibling leaves schools empty; Aristotle founded the Peripatetic school.',
  },
  {
    doc: 'registry',
    path: 'EN.translations.2.id',
    from: 'ostwald',
    to: 'ostwald',
    reason:
      'Guard: the next correction writes a licence onto translations[2]; this throws if a ' +
      'sibling reorder moves Ostwald.',
  },
  {
    doc: 'registry',
    path: 'EN.translations.2.license',
    from: undefined,
    to: {
      status: 'public-domain-us',
      rationale: "Copyright not renewed; public domain by lapse (John's research, ruling 2026-09-22)",
    },
    reason:
      "Ostwald's ethics translation is public domain based on research--lapsed copyright due to " +
      'non-renewal.',
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

function applyPostVendorCorrections(registryDoc, authorsDoc) {
  const authorsById = Object.fromEntries(authorsDoc.authors.map((author) => [author.id, author]));
  for (const correction of POST_VENDOR_CORRECTIONS) {
    const root = correction.doc === 'registry' ? registryDoc.registry : authorsById;
    const current = getAtPath(root, correction.path);
    if (JSON.stringify(current) !== JSON.stringify(correction.from)) {
      throw new Error(
        `vendor-aristotle-registry: POST_VENDOR_CORRECTIONS[${correction.doc}.${correction.path}] ` +
          `expected ${JSON.stringify(correction.from)}, found ${JSON.stringify(current)} -- ` +
          'the sibling data has drifted; review this correction before rerunning.',
      );
    }
    setAtPath(root, correction.path, correction.to);
    console.log(`CORRECTION: ${correction.doc}.${correction.path} -- ${correction.reason}`);
  }
}

function mapAuthor(author) {
  if (author === 'Aristotle') return 'aristotle';
  if (author === 'Porphyry') return 'porphyry';
  throw new Error(`vendor-aristotle-registry: no author mapping for '${author}'.`);
}

function mapWork(work) {
  const unknown = Object.keys(work).filter((key) => !HANDLED_SOURCE_FIELDS.has(key));
  if (unknown.length) {
    throw new Error(
      `vendor-aristotle-registry: ${work.id ?? '<unknown>'} has unmapped field(s): ` +
        unknown.join(', '),
    );
  }

  return {
    id: work.id,
    slug: DERIVE_SLUG(work.title),
    title: work.title,
    ...(hasOwn(work, 'greekTitle') ? { greekTitle: work.greekTitle } : {}),
    abbr: work.abbr,
    author: mapAuthor(work.author),
    language: 'grc',
    workType: work.workType ?? 'continuous',
    books: work.books,
    bookLabels: work.bookLabels,
    ...(hasOwn(work, 'missingBooks') ? { missingBooks: work.missingBooks } : {}),
    greekEdition: work.greekEdition,
    greekSource: work.greekSource,
    translations: work.translations,
    ...(hasOwn(work, 'defaultTranslation')
      ? { defaultTranslation: work.defaultTranslation }
      : {}),
    citation: work.citation ?? { scheme: 'bekker' },
    ...(hasOwn(work, 'authenticity') ? { authenticity: work.authenticity } : {}),
    ...(hasOwn(work, 'related') ? { related: work.related } : {}),
    ...(hasOwn(work, 'commentaries') ? { commentaries: work.commentaries } : {}),
    blurb: hasOwn(work, 'blurb') ? work.blurb : '',
  };
}

// ---------------------------------------------------------------------------
// CATEGORIES extraction (Lyceum P3, [author]/index.astro grouped-Works
// rendering). The sibling's home-page taxonomy (works.ts's CATEGORIES,
// ~line 1220) is the traditional Aristotelian corpus structure -- numbered
// divisions (I Logic, II Natural Philosophy with II.a/b/c subcategories,
// III Metaphysics, IV Moral and Political Philosophy, V Rhetoric and
// Poetics), plus an unnumbered appendix of doubtful/spurious works. This
// reduces it to work ids only (a CATEGORIES "placeholder" entry -- `title`
// with no `id`, a not-yet-added sibling work -- has nothing to vendor and is
// dropped). Porphyry's Isagoge is deliberately absent from CATEGORIES (the
// sibling's own trailing comment: it's surfaced as a Categories-page
// "Commentary" card instead), so groups.yaml is aristotle-only -- never
// asserted for porphyry.
function extractGroups(categories, aristotleWorkIds) {
  const idSet = new Set(aristotleWorkIds);
  const seen = new Map(); // work id -> the group/subcategory label that already claimed it
  const groups = [];

  const claim = (id, where) => {
    if (!idSet.has(id)) {
      throw new Error(`vendor-aristotle-registry: CATEGORIES references unknown work id '${id}' (in ${where}).`);
    }
    if (seen.has(id)) {
      throw new Error(
        `vendor-aristotle-registry: work '${id}' appears in more than one CATEGORIES group ` +
          `(${seen.get(id)} and ${where}).`,
      );
    }
    seen.set(id, where);
  };

  for (const cat of categories) {
    const group = { numeral: cat.numeral, title: cat.title };
    if (cat.appendix) group.appendix = true;
    if (Array.isArray(cat.works)) {
      const ids = cat.works.filter((w) => hasOwn(w, 'id')).map((w) => w.id);
      ids.forEach((id) => claim(id, cat.title));
      group.works = ids;
    }
    if (Array.isArray(cat.subcategories)) {
      group.subcategories = cat.subcategories.map((sub) => {
        const ids = sub.works.filter((w) => hasOwn(w, 'id')).map((w) => w.id);
        ids.forEach((id) => claim(id, `${cat.title} / ${sub.label}`));
        return { ref: sub.ref, label: sub.label, works: ids };
      });
    }
    groups.push(group);
  }

  const orphans = aristotleWorkIds.filter((id) => !seen.has(id));
  if (orphans.length) {
    throw new Error(`vendor-aristotle-registry: CATEGORIES has no group for: ${orphans.join(', ')}.`);
  }
  return groups;
}

function assertRegistry(works) {
  if (works.length !== 41) {
    throw new Error(`vendor-aristotle-registry: expected 41 works, found ${works.length}.`);
  }
  const ids = new Set();
  const routes = new Set();
  for (const work of works) {
    if (!work.id || !work.title || !work.author || !work.language) {
      throw new Error(`vendor-aristotle-registry: ${work.id ?? '<unknown>'} lacks a required field.`);
    }
    if (ids.has(work.id)) {
      throw new Error(`vendor-aristotle-registry: duplicate work id '${work.id}'.`);
    }
    ids.add(work.id);
    const route = `${work.author}/${work.slug}`.toLocaleLowerCase('en-US');
    if (routes.has(route)) {
      throw new Error(`vendor-aristotle-registry: duplicate author/slug route '${route}'.`);
    }
    routes.add(route);
  }
}

async function main() {
  const yaml = await loadYaml();

  // The baseline uses the same undefined import.meta.env define as the P2
  // extractor. A second bundle enables only PUBLIC_SHOW_PRIVATE so the
  // committed source keeps the private:true entries that public builds hide.
  const publicModule = await bundleWorks('undefined');
  const fullModule = await bundleWorks("'1'");
  assertPlainData(publicModule.WORKS, 'public.WORKS');
  assertPlainData(fullModule.WORKS, 'full.WORKS');
  assertPrivateBundleOnlyAddsPrivateTranslations(publicModule.WORKS, fullModule.WORKS);

  assertPlainData(fullModule.CATEGORIES, 'full.CATEGORIES');
  if (JSON.stringify(publicModule.CATEGORIES) !== JSON.stringify(fullModule.CATEGORIES)) {
    throw new Error(
      'vendor-aristotle-registry: CATEGORIES differs between the public and PUBLIC_SHOW_PRIVATE ' +
        'bundles -- it should carry no private-translation data at all.',
    );
  }

  const works = fullModule.WORKS.map(mapWork);
  assertRegistry(works);

  const workOrder = works.map((work) => work.id);
  const aristotleWorks = works
    .filter((work) => work.author === 'aristotle')
    .map((work) => work.id);
  const porphyryWorks = works
    .filter((work) => work.author === 'porphyry')
    .map((work) => work.id);

  const registryDoc = {
    registry: Object.fromEntries(works.map((work) => [work.id, work])),
  };
  const authorsDoc = {
    authors: [
      {
        id: 'aristotle',
        name: 'Aristotle',
        nativeName: 'Ἀριστοτέλης',
        languages: ['grc'],
        period: 'classical',
        schools: [],
        floruit: '384–322 BC',
        blurb: '',
        works: aristotleWorks,
        holdings: 'partial',
      },
      {
        id: 'porphyry',
        name: 'Porphyry',
        nativeName: 'Πορφύριος',
        languages: ['grc'],
        period: 'imperial',
        schools: [],
        floruit: 'c. 234–305 AD',
        blurb: '',
        works: porphyryWorks,
        holdings: 'partial',
      },
    ],
    work_order: workOrder,
  };

  applyPostVendorCorrections(registryDoc, authorsDoc);

  const groups = extractGroups(fullModule.CATEGORIES, aristotleWorks);
  const groupsDoc = { groups };

  mkdirSync(OUT_DIR, { recursive: true });
  const dumpOptions = { sortKeys: false, lineWidth: -1, noRefs: true };
  writeFileSync(REGISTRY_PATH, yaml.dump(registryDoc, dumpOptions));
  writeFileSync(AUTHORS_PATH, yaml.dump(authorsDoc, dumpOptions));
  writeFileSync(GROUPS_PATH, yaml.dump(groupsDoc, dumpOptions));

  console.warn(
    'WARNING: sibling Work has no workType field; wrote workType: continuous for all 41 works.',
  );
  const missingBlurbs = fullModule.WORKS.filter((work) => !hasOwn(work, 'blurb'));
  if (missingBlurbs.length) {
    console.warn(
      `WARNING: wrote empty blurbs for: ${missingBlurbs.map((work) => work.id).join(', ')}.`,
    );
  }
  for (const [title, slug] of Object.entries(OVERRIDES)) {
    console.log(`OVERRIDE: ${title} -> ${slug}`);
  }
  console.log(
    `Wrote corpora/aristotle/{registry,authors,groups}.yaml: ${works.length} works, 2 authors, ` +
      `${groups.length} CATEGORIES groups.`,
  );
}

await main();
