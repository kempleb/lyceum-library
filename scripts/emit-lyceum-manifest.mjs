// Build-time view of each work's manifest.json for the partner WordPress
// plugin (Lyceum Reader Manager 0.7.0). Our manifest.json stays the
// authority; this file is derived and never hand-maintained.
//
// Validation approach mirrors pipeline/reader_pipeline/validate_contracts.py:
// walk <dist>/*/manifest.json, load a draft 2020-12 schema, fail the run on
// the first invalid instance. Node has no jsonschema package in this repo,
// so validateAgainstSchema implements the dialect features this schema uses.

import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const GENERATED_REGISTRY = join(ROOT, 'shared', 'lib', 'registry.generated.ts');
const SCHEMA_PATH = join(ROOT, 'schemas', 'lyceum-manifest.v1.json');
const DEFAULT_DIST = join(ROOT, 'build', 'dist');

const WORK_PATTERN = /^lyceum:[a-z0-9-]+\.[a-z0-9-]+$/;
const ROUTE_PATTERN = /^\/texts\/[a-z0-9-]+\/[a-z0-9-]+\/$/;


// John's licence-string ruling (2026-09-22): the partner sees a plain
// display string, never our internal status bucket -- "Public Domain" for
// every public-domain-us translation, the licence's own short abbreviation
// (its `name`, e.g. "CC BY-NC-ND 4.0") for a `cc` one, and "Licensed" for
// anything else under active licence. `unverified` (or a missing/unrecognized
// status) stays the literal string "unverified" so nothing silently claims a
// rights basis it doesn't have. This is `mapLicense`, used for translations'
// `rights` field. Editions use `editionLicenseString` instead (below) --
// their `license` string names the source's digitization channel ("TLG" /
// "PHI") or CC abbreviation, never a public-domain claim; `verified` stays
// false for every edition.

// Partner apparatus labels, in the order the template listed them.
const APPARATUS_LABELS = [
  ['sections', 'Section numbers'],
  ['footnotes', 'Footnotes'],
  ['sidenotes', 'Marginal notes'],
  ['paratext', 'Editorial headings'],
  ['figures', 'Figures'],
  ['philosophers', 'Philosopher index'],
];

export const LYCEUM_KEY_ORDER = [
  'work',
  'author',
  'title',
  'latin_title',
  'language',
  'date_label',
  'route',
  'reading_route',
  'citation',
  'editions',
  'translations',
  'apparatus',
  'navigation',
  'schema_version',
  'corpus_version',
  'source_manifest',
  'generator',
];

export function parseArgs(argv) {
  let dist = DEFAULT_DIST;
  let work = null;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dist') {
      const value = argv[++i];
      if (!value) throw new Error('--dist requires a directory');
      dist = resolve(value);
    } else if (arg === '--work') {
      const value = argv[++i];
      if (!value) throw new Error('--work requires a work id');
      work = value;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return { dist, work };
}

export function mapLanguage(language) {
  if (language === 'grc') return 'grc';
  if (language === 'lat') return 'la';
  return null;
}

export function mapLicense(license) {
  const status = license?.status;
  if (status === 'public-domain-us') return 'Public Domain';
  if (status === 'licensed') return 'Licensed';
  if (status === 'cc') {
    const name = license.name;
    if (typeof name !== 'string' || name.trim() === '') {
      throw new Error("cc license is missing its required 'name' (licence abbreviation)");
    }
    return name;
  }
  // unverified, missing, or any other status: never silently claim a
  // rights basis the manifest doesn't assert.
  return 'unverified';
}

// Stopgap: take a four-digit year from the translation `name` only when the
// string contains exactly one number in 1500–2030. Zero or two-or-more
// matches → null (the partner sees the gap rather than a guessed year).
export function yearFromName(name) {
  if (typeof name !== 'string') return null;
  const matches = name.match(/\d{4}/g) ?? [];
  const years = matches.map(Number).filter((year) => year >= 1500 && year <= 2030);
  return years.length === 1 ? years[0] : null;
}

export function reorderCorpusVersion(ours) {
  if (typeof ours !== 'string') return null;
  const match = /^(.*)-(\d{4})-(\d{2})-(\d{2})$/.exec(ours);
  if (!match) return null;
  return `${match[2]}.${match[3]}.${match[4]}-${match[1]}`;
}

export function buildIndex(entries, dataRoot) {
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new Error('buildIndex requires at least one entry');
  }
  const versions = [...new Set(entries.map((entry) => entry.corpus_version))];
  if (versions.length > 1) {
    const listed = [...versions].sort((a, b) => String(a).localeCompare(String(b))).join(', ');
    throw new Error(`mixed corpus_version values: ${listed}`);
  }
  const root =
    dataRoot == null ? null : String(dataRoot).replace(/\/+$/, '');
  const manifests = [...entries]
    .sort((a, b) => String(a.work).localeCompare(String(b.work)))
    .map((entry) => ({
      work: entry.work,
      path: entry.path,
      url: root == null ? entry.path : `${root}${entry.path}`,
      sha256: entry.sha256,
    }));
  return {
    schema_version: '1.0',
    corpus_version: versions[0],
    data_root: root,
    manifests,
  };
}

export function latinTitle(ourManifest, work) {
  if (typeof work?.greekTitle === 'string' && work.greekTitle.length > 0) {
    return work.greekTitle;
  }
  if (ourManifest?.language === 'lat' || work?.language === 'lat') {
    return ourManifest?.title ?? null;
  }
  return null;
}

export function countNullFields(value, counts = {}) {
  if (value === null) return counts;
  if (Array.isArray(value)) {
    for (const item of value) countNullFields(item, counts);
    return counts;
  }
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (child === null) {
        counts[key] = (counts[key] ?? 0) + 1;
      } else {
        countNullFields(child, counts);
      }
    }
  }
  return counts;
}

// Our own manifest.route is the route-ownership authority (never the id or
// author fields, which can diverge from it -- e.g. Aristotle's EN id routes
// at /aristotle/nicomachean-ethics). Segments come back lowercased only when
// they aren't already -- the route/reading_route fields below use the route
// string verbatim, so a non-lowercase route fails the partner's ROUTE_PATTERN
// check further down rather than being silently normalized here.
function routeSegments(ourManifest) {
  const route = ourManifest?.route;
  if (typeof route !== 'string') {
    throw new Error(`missing input: manifest route (got ${JSON.stringify(route)})`);
  }
  const match = /^\/([^/]+)\/([^/]+)$/.exec(route);
  if (!match) {
    throw new Error(`missing input: manifest route ${JSON.stringify(route)} is not in /<author>/<work> form`);
  }
  const lower = (value) => (value === value.toLowerCase() ? value : value.toLowerCase());
  return { authorSegment: lower(match[1]), workSegment: lower(match[2]) };
}

function citationBooks(ourManifest) {
  const books = ourManifest?.citation?.books;
  return Array.isArray(books) ? books : [];
}

function topLevelBooks(ourManifest) {
  const books = ourManifest?.books;
  return Array.isArray(books) ? books : [];
}

// Mirrors shared/lib/works.ts's divisionId (John's ruling, 2026-09-12): a
// bookless work reads at 'text'; every other work reads at
// '<divisionNoun>-<n>', divisionNoun defaulting to 'book'. Implemented
// directly here -- there is no clean .mjs import of the TypeScript
// shared/lib/works.ts -- and pinned against the real divisionId/workPath by
// the cross-check test in shared/__tests__/lyceum-manifest.test.ts.
// Bookless-ness is decided off the REGISTRY's own book count (work.books ===
// 1, same field isBookless reads in shared/lib/works.ts), not the manifest's
// citation-book count: a manifest that exports only its first citation book
// (a partial or in-progress export) would otherwise read as bookless even
// when the registry says the work has many -- e.g. an Epistulae Morales
// export carrying one citation book would emit 'text' instead of 'letter-1'.
// Fall back to the manifest's own book count only when the registry has no
// `books` count for this work at all (a hand-built fixture with no matching
// registry entry).
export function divisionIdFor(work, books) {
  const bookless = typeof work.books === 'number' ? work.books === 1 : books.length === 1;
  if (bookless) return 'text';
  return `${work.divisionNoun ?? 'book'}-${books[0].n}`;
}

// `book.start`/`book.end` already carry the book-dotted column ("1.1") for
// book-section works; a flat scheme's single book carries the bare column
// ("1"). Either way the range is the column pair verbatim -- prepending
// book.n again (the old behaviour) double-counted the book for book-section
// works, yielding "1.1.1-1.1.17" instead of "1.1-1.17".
function citationRanges(books) {
  return books.map((book) => `${book.start}-${book.end}`);
}

function citationExtent(books) {
  if (books.length === 0) return null;
  const counts = books.map((book) => book.segments);
  if (counts.some((count) => typeof count !== 'number')) return null;
  if (books.length === 1) return `${counts[0]} sections`;
  const total = counts.reduce((sum, count) => sum + count, 0);
  return `${books.length} books · ${total} sections`;
}

// John's edition-licence ruling (2026-09-22): the partner's `editions[].license`
// says which digitization channel the source text came from -- "TLG" or "PHI"
// -- unless the edition instead carries a Creative Commons licence (Perseus /
// First1kGreek; none in this build today), in which case it's that licence's
// abbreviation. `verified` stays false for every edition regardless: none of
// this is a public-domain claim, just metadata for Brian's plugin.
export function editionLicenseString(edition) {
  if (edition?.license?.status === 'cc') {
    const name = edition.license.name;
    if (typeof name !== 'string' || name.trim() === '') {
      throw new Error("cc license is missing its required 'name' (licence abbreviation)");
    }
    return name;
  }
  const kind = edition?.source?.kind;
  if (kind === 'tlg') return 'TLG';
  if (kind === 'phi') return 'PHI';
  return 'unverified';
}

function editionView(edition) {
  const source = edition?.source ?? {};
  const kind = source.kind;
  const author = source.author;
  const work = source.work;
  // The public edition id and source name the printed edition only. The
  // digitization channel stays in the pipeline manifest (source.kind), not
  // in anything served or handed to the partner (John, 2026-09-09).
  const id =
    kind && author && work ? `edition-${author}-${work}` : null;
  const sourceText = edition?.edition && author && work ? edition.edition : null;
  return {
    id,
    source: sourceText,
    license: editionLicenseString(edition),
    verified: false,
  };
}

// The partner template's `aligned` is the alignment GRAIN (a citation unit:
// "section", "line", ...), not our internal alignment strategy name
// (archive/freeman/chapter_concordance/...). Map scheme -> grain here; the
// strategy itself moves to the additive `alignment_method` field so it isn't
// lost, just relabeled to the right slot.
const ALIGNMENT_GRAIN_BY_SCHEME = {
  section: 'section',
  'book-section': 'section',
  'verse-line': 'line',
  bekker: 'column',
  stephanus: 'column',
  dk: 'fragment',
  letter: 'letter',
};

export function alignmentGrain(scheme) {
  return Object.hasOwn(ALIGNMENT_GRAIN_BY_SCHEME, scheme) ? ALIGNMENT_GRAIN_BY_SCHEME[scheme] : null;
}

function translationView(translation, work, scheme) {
  if (!translation?.id) {
    throw new Error('translation missing required id');
  }
  const refs = Array.isArray(work?.translations) ? work.translations : [];
  const ref = refs.find((entry) => entry?.id === translation.id) ?? {};
  const translator = Object.hasOwn(ref, 'translator') ? ref.translator : null;
  const hasAlignment = translation.alignment != null;
  return {
    id: translation.id,
    label: ref.short ?? null,
    translator,
    date: yearFromName(translation.name),
    rights: mapLicense(translation.license),
    aligned: hasAlignment ? alignmentGrain(scheme) : null,
    alignment_method: hasAlignment ? translation.alignment : null,
    default: typeof translation.default === 'boolean' ? translation.default : null,
  };
}

function apparatusView(ourManifest, language) {
  const flags = ourManifest?.apparatus && typeof ourManifest.apparatus === 'object'
    ? ourManifest.apparatus
    : {};
  const items = [];
  for (const [id, label] of APPARATUS_LABELS) {
    if (flags[id] === true) items.push({ id, label });
  }
  items.push({ id: 'search', label: 'Full-text search' });
  if (language === 'grc') {
    items.push({ id: 'lexicon', label: 'Greek dictionary lookup' });
  } else if (language === 'la') {
    items.push({ id: 'lexicon', label: 'Latin dictionary lookup' });
  }
  return items;
}

// The partner's real schema (schemas/lyceum-manifest.v1.json) declares no
// field with a null variant, so `null` is always a type violation, never
// "absent". Dropping the key is the schema's own remedy for an optional
// field; a required field that would have been null is dropped too and then
// fails the schema's `required` check, which is the failure we want. Applied
// recursively so nested objects/arrays (translations[], editions[], citation,
// apparatus[]) are covered from this one spot. `false`/`0`/`''`/`[]` are
// real values and stay.
function dropNulls(value) {
  if (Array.isArray(value)) {
    return value.map(dropNulls);
  }
  if (value !== null && typeof value === 'object') {
    const out = {};
    for (const [key, child] of Object.entries(value)) {
      if (child === null) continue;
      out[key] = dropNulls(child);
    }
    return out;
  }
  return value;
}

function ordered(object) {
  const out = {};
  for (const key of LYCEUM_KEY_ORDER) {
    if (Object.hasOwn(object, key) && object[key] !== undefined && object[key] !== null) {
      out[key] = dropNulls(object[key]);
    }
  }
  for (const [key, value] of Object.entries(object)) {
    if (!Object.hasOwn(out, key) && value !== undefined && value !== null) {
      out[key] = dropNulls(value);
    }
  }
  return out;
}

export function toLyceumManifest(ourManifest, work, author) {
  if (!ourManifest || typeof ourManifest !== 'object') {
    throw new Error('missing input: our manifest');
  }
  if (!work || typeof work !== 'object') {
    throw new Error(`missing input: registry work '${ourManifest.id ?? '<unknown>'}'`);
  }
  if (!author || typeof author !== 'object' || !author.name) {
    throw new Error(`unknown author '${ourManifest.author ?? '<missing>'}'`);
  }

  const { authorSegment, workSegment } = routeSegments(ourManifest);
  const workKey = `lyceum:${authorSegment}.${workSegment}`;
  const route = `/texts${ourManifest.route}/`;
  if (!WORK_PATTERN.test(workKey)) {
    throw new Error(`work ${JSON.stringify(workKey)} fails partner rules`);
  }
  if (!ROUTE_PATTERN.test(route)) {
    throw new Error(`route ${JSON.stringify(route)} fails partner rules`);
  }

  const language = mapLanguage(ourManifest.language);
  const books = citationBooks(ourManifest);
  const scheme = ourManifest.citation?.scheme ?? null;
  // reading_route always points at the real, always-built reader page
  // (app/src/pages/read/[author]/[work]/[division].astro), never at a
  // scheme-specific alias -- the section-N alias
  // (app/src/pages/read/_section-routes.ts) exists only for section-scheme
  // works and is itself a forwarder INTO this page.
  const readingRoute =
    books[0]?.n == null ? null : `/read/${authorSegment}/${workSegment}/${divisionIdFor(work, books)}`;

  const result = {
    work: workKey,
    author: author.name,
    title: ourManifest.title ?? null,
    latin_title: latinTitle(ourManifest, work),
    language,
    date_label: author.floruit ?? null,
    route,
    reading_route: readingRoute,
    citation: {
      scheme,
      ranges: citationRanges(books),
      extent: citationExtent(topLevelBooks(ourManifest)),
    },
    editions: Array.isArray(ourManifest.editions)
      ? ourManifest.editions.map(editionView)
      : [],
    translations: Array.isArray(ourManifest.translations)
      ? ourManifest.translations.map((entry) => translationView(entry, work, scheme))
      : [],
    apparatus: apparatusView(ourManifest, language),
    schema_version: '1.0',
    corpus_version: reorderCorpusVersion(ourManifest.corpus_version),
    source_manifest: 'manifest.json',
    generator: 'scripts/emit-lyceum-manifest.mjs',
  };

  return ordered(result);
}

// build/dist/<work>/book-NN.json -- the same padding shared/lib/data.ts's
// fetchBook uses (book-100.json, not book-0100.json).
function bookFileName(n) {
  return `book-${String(n).padStart(2, '0')}.json`;
}

function capitalize(word) {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

// Navigation for the partner's adaptive-reading contract (John and Opus,
// 2026-09-12; schemas/lyceum-manifest.v1.json's `navigation` and
// `$defs.navigationNode`). One division node per reading page
// (/read/<a>/<w>/<division-id>); one loci entry per COLUMN, never per line --
// line-level loci are resolved on the page by `?loc=`, so they are
// deliberately omitted here.
//
// A Bekker column split across a book boundary (68 of them, in 17 works --
// e.g. EN's "1103a") gets two loci entries: the bare column key on the LOWER
// book (the first occurrence) and, on the book where it recurs, a key built
// from that segment's own first Greek line (its `greek[0].n`, e.g.
// "1103a14") -- read from book-NN.json's segment order, never from
// columns.json's key order (integer-like keys hoist in JS; Pythagoras has
// "6a"/"8a" mixed with numeric ones).
//
// citation_aliases carries only the two per-scheme forms the contract can't
// express any other way: a DK work's "<dkChapter> <col>" / "DK <dkChapter>
// <col>" forms, and a letter work's bare letter number ("47") pointing at
// that letter's first section. Split Bekker columns need no alias -- the
// bare column is already the first occurrence's key.
export function buildNavigation(ourManifest, work, workDir) {
  const books = citationBooks(ourManifest);
  if (books.length === 0) {
    throw new Error('navigation requires at least one citation book');
  }
  const { authorSegment, workSegment } = routeSegments(ourManifest);
  const scheme = ourManifest.citation?.scheme ?? null;
  const divisionNoun = work.divisionNoun ?? 'book';
  const isText = books.length === 1;

  const columnsPath = join(workDir, 'columns.json');
  if (!existsSync(columnsPath)) {
    throw new Error(`missing input: ${columnsPath}`);
  }
  const columns = JSON.parse(readFileSync(columnsPath, 'utf8'));

  const loci = {};
  const divisions = [];
  const aliases = {};

  for (const book of books) {
    const divisionId = isText ? 'text' : `${divisionNoun}-${book.n}`;
    const route = `/read/${authorSegment}/${workSegment}/${divisionId}`;
    const bookPath = join(workDir, bookFileName(book.n));
    if (!existsSync(bookPath)) {
      throw new Error(`missing input: ${bookPath}`);
    }
    const bookData = JSON.parse(readFileSync(bookPath, 'utf8'));
    const segments = Array.isArray(bookData.segments) ? bookData.segments : [];
    if (segments.length === 0) {
      throw new Error(`division ${divisionId} (${bookPath}) has no segments`);
    }

    let firstLocus = null;
    let finalLocus = null;
    const seenFragments = new Map(); // lowercased fragment -> owning column, this division only

    for (const segment of segments) {
      const column = segment.column;
      if (typeof column !== 'string' || column.length === 0) {
        throw new Error(`${bookPath}: segment '${segment.id ?? '?'}' has no column`);
      }
      const fragment = column.toLowerCase();
      const priorColumn = seenFragments.get(fragment);
      if (priorColumn !== undefined && priorColumn !== column) {
        throw new Error(
          `case collision in division ${divisionId}: columns '${priorColumn}' and '${column}' both lowercase to '${fragment}'`,
        );
      }
      seenFragments.set(fragment, column);

      const occurrences = Array.isArray(columns[column]) ? columns[column] : null;
      const isSplit = !!occurrences && occurrences.length > 1;
      let refKey = column;
      if (isSplit) {
        const lowestBook = Math.min(...occurrences.map((occurrence) => occurrence.book));
        if (book.n !== lowestBook) {
          const firstLine = segment.greek?.[0]?.n;
          if (firstLine == null) {
            throw new Error(
              `${bookPath}: split column '${column}' has no greek[0].n to key its recurrence`,
            );
          }
          refKey = `${column}${firstLine}`;
        }
      }
      if (Object.hasOwn(loci, refKey)) {
        throw new Error(`duplicate loci key '${refKey}' (column '${column}', book ${book.n})`);
      }
      loci[refKey] = `${route}#col-${fragment}`;
      if (firstLocus == null) firstLocus = refKey;
      finalLocus = refKey;
    }

    divisions.push({
      id: divisionId,
      label: isText
        ? (ourManifest.title ?? divisionId)
        : `${capitalize(divisionNoun)} ${work.bookLabels?.[book.n - 1] ?? String(book.n)}`,
      route,
      first_locus: firstLocus,
      final_locus: finalLocus,
    });

    if (scheme === 'letter') {
      aliases[String(book.n)] = firstLocus;
    }
  }

  if (scheme === 'dk') {
    const dkChapter = work.citation?.dkChapter;
    if (dkChapter == null) {
      throw new Error(`dk work '${work.id ?? ourManifest.id}' is missing registry citation.dkChapter`);
    }
    for (const column of Object.keys(loci)) {
      aliases[`${dkChapter} ${column}`] = column;
      aliases[`DK ${dkChapter} ${column}`] = column;
    }
  }

  const translations = Array.isArray(ourManifest.translations) ? ourManifest.translations : [];

  return {
    default_locus: divisions[0].first_locus,
    first_locus: divisions[0].first_locus,
    final_locus: divisions.at(-1).final_locus,
    citation_aliases: aliases,
    language_modes: translations.length ? ['original', 'parallel', 'translation'] : ['original'],
    translation_ids: translations.map((translation) => translation.id),
    divisions,
    loci,
  };
}

// class-lrm-manifest-validator.php's route-with-optional-fragment pattern.
// Shared by node routes (validate_navigation_nodes, line 174) and loci
// hrefs (the loci block, line 82) — the PHP uses the identical regex both
// places.
const NAV_ROUTE_PATTERN = /^\/[a-z0-9][a-z0-9/_-]*(?:#[a-z0-9][a-z0-9._-]*)?$/;
const NAV_ID_PATTERN = /^[a-z0-9][a-z0-9._-]*$/;
const NAV_ALLOWED_MODES = ['original', 'parallel', 'translation'];

function isNonEmptyTrimmedString(value) {
  return typeof value === 'string' && value.trim() !== '';
}

// Mirrors validate_navigation_nodes (class-lrm-manifest-validator.php
// lines 164-183): recurses through children, tracking id/route uniqueness
// across the whole work tree (seenIds/seenRoutes are shared by reference
// through the recursion, exactly as the PHP's &$seen_ids/&$seen_routes are).
function validateNavigationNodes(nodes, path, errors, seenIds, seenRoutes) {
  nodes.forEach((node, index) => {
    const itemPath = `${path}[${index}]`;
    if (node === null || typeof node !== 'object' || Array.isArray(node)) {
      errors.push(`${itemPath} must be an object.`); // line 167
      return;
    }
    for (const field of ['id', 'label', 'route', 'first_locus', 'final_locus']) {
      if (!isNonEmptyTrimmedString(node[field])) {
        errors.push(`${itemPath}.${field} must be a non-empty string.`); // line 168
      }
    }
    if (typeof node.id === 'string') {
      // lines 169-172
      if (!NAV_ID_PATTERN.test(node.id)) {
        errors.push(`${itemPath}.id must be a stable lowercase identifier.`);
      } else if (seenIds.has(node.id)) {
        errors.push(`${itemPath}.id must be unique within the work navigation.`);
      } else {
        seenIds.add(node.id);
      }
    }
    if (typeof node.route === 'string') {
      // lines 173-176
      if (!NAV_ROUTE_PATTERN.test(node.route)) {
        errors.push(`${itemPath}.route must be a lowercase root-relative path with an optional stable fragment.`);
      } else if (seenRoutes.has(node.route)) {
        errors.push(`${itemPath}.route must be unique within the work navigation.`);
      } else {
        seenRoutes.add(node.route);
      }
    }
    if (node.children !== undefined) {
      // lines 177-179
      if (!Array.isArray(node.children)) {
        errors.push(`${itemPath}.children must be an array.`);
      } else {
        validateNavigationNodes(node.children, `${itemPath}.children`, errors, seenIds, seenRoutes);
      }
    }
  });
}

// Mirrors the PHP loci-block's $visit closure (class-lrm-manifest-validator.php
// line 79): collects every node's route, fragment stripped, recursively
// through children — not just top-level divisions.
function collectNodePaths(nodes, paths) {
  for (const node of nodes) {
    if (node === null || typeof node !== 'object' || Array.isArray(node)) continue;
    if (typeof node.route === 'string') paths.push(node.route.split('#')[0]);
    if (Array.isArray(node.children)) collectNodePaths(node.children, paths);
  }
}

// Mirrors the PHP plugin's validate_navigation (lines 127-162) and the
// loci block in validate() (lines 78-85), one check at a time and in the
// same order, so a manifest that would fail the partner's gate fails
// loudly here instead of shipping. Schema shape (types/patterns/minLength)
// is already covered by validateAgainstSchema; this adds the checks a
// $ref/pattern schema can't express — trimmed non-emptiness, cross-tree
// uniqueness, and cross-referential rules ("this string must be a key of
// that object").
export function validateNavigationSemantics(navigation, translations) {
  const errors = [];
  if (navigation === null || typeof navigation !== 'object' || Array.isArray(navigation)) {
    return ['navigation must be an object.'];
  }

  // lines 129-130: default_locus/first_locus/final_locus non-empty trimmed.
  for (const field of ['default_locus', 'first_locus', 'final_locus']) {
    if (!isNonEmptyTrimmedString(navigation[field])) {
      errors.push(`navigation.${field} must be a non-empty string.`);
    }
  }

  // lines 131-135: citation_aliases must be an object; every key and value
  // a non-empty trimmed string.
  const citationAliases = navigation.citation_aliases;
  const citationAliasesIsObject =
    citationAliases !== null && typeof citationAliases === 'object' && !Array.isArray(citationAliases);
  if (!citationAliasesIsObject) {
    errors.push('navigation.citation_aliases must be an object.');
  } else {
    for (const [alias, canonical] of Object.entries(citationAliases)) {
      if (!isNonEmptyTrimmedString(alias) || !isNonEmptyTrimmedString(canonical)) {
        errors.push('navigation.citation_aliases must map non-empty aliases to canonical loci.');
      }
    }
  }

  // lines 137-143: language_modes non-empty, each in the allowed set, no
  // duplicates, and no translation/parallel mode without a translation.
  const languageModes = navigation.language_modes;
  if (!Array.isArray(languageModes) || languageModes.length === 0) {
    errors.push('navigation.language_modes must contain at least one mode.');
  } else {
    languageModes.forEach((mode, index) => {
      if (typeof mode !== 'string' || !NAV_ALLOWED_MODES.includes(mode)) {
        errors.push(`navigation.language_modes[${index}] must be original, parallel, or translation.`);
      }
    });
    if (new Set(languageModes).size !== languageModes.length) {
      errors.push('navigation.language_modes must not contain duplicates.');
    }
    const hasTranslations = Array.isArray(translations) && translations.length > 0;
    if ((languageModes.includes('translation') || languageModes.includes('parallel')) && !hasTranslations) {
      errors.push('navigation cannot offer translation or parallel mode without a manifest translation.');
    }
  }

  // lines 144-150: translation_ids an array; each a non-empty string
  // matching a manifest translation id; no duplicates.
  const translationIds = navigation.translation_ids;
  if (!Array.isArray(translationIds)) {
    errors.push('navigation.translation_ids must be an array.');
  } else {
    const available = new Set(
      (Array.isArray(translations) ? translations : [])
        .filter((translation) => translation && typeof translation === 'object' && translation.id)
        .map((translation) => String(translation.id)),
    );
    translationIds.forEach((id, index) => {
      if (!isNonEmptyTrimmedString(id) || !available.has(id)) {
        errors.push(`navigation.translation_ids[${index}] (${JSON.stringify(id)}) must match a manifest translation id.`);
      }
    });
    if (new Set(translationIds).size !== translationIds.length) {
      errors.push('navigation.translation_ids must not contain duplicates.');
    }
  }

  // lines 151-158: divisions non-empty; nodes validated recursively.
  const divisions = navigation.divisions;
  const seenIds = new Set();
  const seenRoutes = new Set();
  if (!Array.isArray(divisions) || divisions.length === 0) {
    errors.push('navigation.divisions must contain at least one division.');
  } else {
    validateNavigationNodes(divisions, 'navigation.divisions', errors, seenIds, seenRoutes);
  }

  // lines 78-85: loci checks run ONLY when navigation.loci is present
  // (PHP's `isset( $manifest['navigation']['loci'] )` branch) — absent
  // loci skips the boundary/alias-against-loci checks entirely.
  const loci = navigation.loci;
  if (loci !== undefined) {
    if (loci === null || typeof loci !== 'object' || Array.isArray(loci)) {
      errors.push('navigation.loci must be an object.'); // line 85
    } else {
      const paths = [];
      collectNodePaths(Array.isArray(divisions) ? divisions : [], paths);
      for (const [ref, href] of Object.entries(loci)) {
        const hrefPath = typeof href === 'string' ? href.split('#')[0] : null;
        if (
          !isNonEmptyTrimmedString(ref) ||
          typeof href !== 'string' ||
          !NAV_ROUTE_PATTERN.test(href) ||
          !paths.includes(hrefPath)
        ) {
          errors.push(`locus '${ref}' (${JSON.stringify(href)}) does not address a declared division route`); // line 82
        }
      }
      for (const field of ['default_locus', 'first_locus', 'final_locus']) {
        const value = navigation[field];
        if (typeof value === 'string' && !Object.hasOwn(loci, value)) {
          errors.push(`navigation.${field} (${JSON.stringify(value)}) is not a loci key`); // line 83
        }
      }
      if (citationAliasesIsObject) {
        for (const [alias, ref] of Object.entries(citationAliases)) {
          if (typeof ref === 'string' && !Object.hasOwn(loci, ref)) {
            errors.push(`citation_aliases['${alias}'] -> '${ref}' is not a loci key`); // line 84
          }
        }
      }
    }
  }

  return errors;
}

function jsonType(value) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'number') return Number.isInteger(value) ? 'integer' : 'number';
  return typeof value;
}

function resolveRef(schema, root) {
  if (!schema || typeof schema !== 'object' || typeof schema.$ref !== 'string') {
    return schema;
  }
  const ref = schema.$ref;
  if (!ref.startsWith('#/')) {
    throw new Error(`unsupported $ref: ${ref}`);
  }
  let current = root;
  for (const part of ref.slice(2).split('/')) {
    current = current?.[part];
  }
  if (current == null) throw new Error(`unresolved $ref: ${ref}`);
  return current;
}

function pointer(path) {
  return path === '' ? '/' : path;
}

export function validateAgainstSchema(instance, schema, root = schema, path = '') {
  const resolved = resolveRef(schema, root);
  const errors = [];
  const fail = (message, at = path) => {
    errors.push({ path: pointer(at), message });
  };

  if (resolved.const !== undefined && instance !== resolved.const) {
    fail(`must be ${JSON.stringify(resolved.const)}`);
  }
  if (Array.isArray(resolved.enum) && !resolved.enum.includes(instance)) {
    fail(`must be one of ${resolved.enum.map((value) => JSON.stringify(value)).join(', ')}`);
  }
  if (
    Array.isArray(resolved.anyOf) &&
    !resolved.anyOf.some((option) => validateAgainstSchema(instance, option, root, path).length === 0)
  ) {
    fail('does not match any of the allowed schemas');
  }

  if (resolved.type !== undefined) {
    const types = Array.isArray(resolved.type) ? resolved.type : [resolved.type];
    const actual = jsonType(instance);
    const ok = types.some((type) => {
      if (type === 'number') return actual === 'number' || actual === 'integer';
      return actual === type;
    });
    if (!ok) fail(`must be type ${types.join('|')}, got ${actual}`);
  }

  if (typeof instance === 'string') {
    if (typeof resolved.minLength === 'number' && instance.length < resolved.minLength) {
      fail(`shorter than minLength ${resolved.minLength}`);
    }
    if (typeof resolved.pattern === 'string' && !new RegExp(resolved.pattern).test(instance)) {
      fail(`does not match pattern ${resolved.pattern}`);
    }
  }

  const isObject = instance !== null && typeof instance === 'object' && !Array.isArray(instance);
  if (isObject) {
    for (const key of resolved.required ?? []) {
      if (!Object.hasOwn(instance, key)) fail('is required', `${path}/${key}`);
    }
    const properties = resolved.properties ?? {};
    for (const [key, value] of Object.entries(instance)) {
      if (Object.hasOwn(properties, key)) {
        errors.push(...validateAgainstSchema(value, properties[key], root, `${path}/${key}`));
      } else if (resolved.additionalProperties === false) {
        fail('additional property not allowed', `${path}/${key}`);
      } else if (resolved.additionalProperties && typeof resolved.additionalProperties === 'object') {
        errors.push(
          ...validateAgainstSchema(value, resolved.additionalProperties, root, `${path}/${key}`),
        );
      }
    }
  }

  if (Array.isArray(instance)) {
    if (typeof resolved.minItems === 'number' && instance.length < resolved.minItems) {
      fail(`fewer than minItems ${resolved.minItems}`);
    }
    if (resolved.uniqueItems === true) {
      const seen = new Set();
      for (const item of instance) {
        const key = JSON.stringify(item);
        if (seen.has(key)) {
          fail('items must be unique');
          break;
        }
        seen.add(key);
      }
    }
    if (resolved.items) {
      instance.forEach((item, index) => {
        errors.push(...validateAgainstSchema(item, resolved.items, root, `${path}/${index}`));
      });
    }
  }

  return errors;
}

export function loadLyceumSchema(root = ROOT) {
  return JSON.parse(readFileSync(join(root, 'schemas', 'lyceum-manifest.v1.json'), 'utf8'));
}

export function formatNullCounts(counts) {
  const names = Object.keys(counts).sort((a, b) => a.localeCompare(b));
  if (names.length === 0) return 'null fields: (none)';
  return `null fields: ${names.map((name) => `${name}=${counts[name]}`).join(' ')}`;
}

async function loadRegistry() {
  try {
    return await import(pathToFileURL(GENERATED_REGISTRY).href);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `could not import ${GENERATED_REGISTRY}. Run node scripts/build-registry.mjs first. ${message}`,
    );
  }
}

function listManifests(dist, workId) {
  if (!existsSync(dist)) {
    throw new Error(`missing input: dist directory ${dist} does not exist`);
  }
  if (workId) {
    const path = join(dist, workId, 'manifest.json');
    if (!existsSync(path)) {
      throw new Error(`missing input: ${path}`);
    }
    return [path];
  }
  const found = readdirSync(dist, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => join(dist, entry.name, 'manifest.json'))
    .filter((path) => existsSync(path))
    .sort((a, b) => a.localeCompare(b));
  if (found.length === 0) {
    throw new Error(`missing input: ${dist} contains no */manifest.json`);
  }
  return found;
}

export async function main(argv = process.argv.slice(2)) {
  const { dist, work: workFilter } = parseArgs(argv);
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8'));
  const registry = await loadRegistry();
  const worksById = new Map(registry.CORPUS_WORKS.map((entry) => [entry.id, entry]));
  const authorsById = new Map(registry.CORPUS_AUTHORS.map((entry) => [entry.id, entry]));

  const paths = listManifests(dist, workFilter);
  const totals = {};
  const entries = [];
  let failed = false;

  for (const path of paths) {
    const workDir = dirname(path);
    const workId = workDir.slice(dist.length).replace(/^[/\\]/, '');
    let ourManifest;
    try {
      ourManifest = JSON.parse(readFileSync(path, 'utf8'));
    } catch (error) {
      console.error(`ERROR ${path}: missing input (${error instanceof Error ? error.message : error})`);
      failed = true;
      continue;
    }

    const id = ourManifest.id ?? workId;
    const author = authorsById.get(ourManifest.author);
    if (!author) {
      console.error(`ERROR ${id}: unknown author '${ourManifest.author}'`);
      failed = true;
      continue;
    }
    const work = worksById.get(ourManifest.id);
    if (!work) {
      console.error(`ERROR ${id}: missing input: registry work '${ourManifest.id}'`);
      failed = true;
      continue;
    }

    let lyceum;
    try {
      lyceum = toLyceumManifest(ourManifest, work, author);
      const navigation = buildNavigation(ourManifest, work, workDir);
      const semanticErrors = validateNavigationSemantics(navigation, ourManifest.translations ?? []);
      if (semanticErrors.length) {
        throw new Error(`navigation failed semantic validation:\n${semanticErrors.join('\n')}`);
      }
      lyceum = ordered({ ...lyceum, navigation });
    } catch (error) {
      console.error(`ERROR ${id}: ${error instanceof Error ? error.message : error}`);
      failed = true;
      continue;
    }

    const errors = validateAgainstSchema(lyceum, schema);
    if (errors.length) {
      for (const error of errors) {
        console.error(`ERROR ${id} ${error.path}: ${error.message}`);
      }
      failed = true;
      continue;
    }

    const outPath = join(workDir, 'manifest.lyceum.json');
    const body = `${JSON.stringify(lyceum, null, 2)}\n`;
    writeFileSync(outPath, body);
    const sha256 = createHash('sha256').update(body).digest('hex');
    entries.push({
      work: lyceum.work,
      path: '/' + workId.replaceAll('\\', '/') + '/manifest.lyceum.json',
      sha256,
      corpus_version: lyceum.corpus_version,
    });
    const nulls = countNullFields(lyceum);
    for (const [name, count] of Object.entries(nulls)) {
      totals[name] = (totals[name] ?? 0) + count;
    }
    const nullSummary = Object.keys(nulls).length
      ? ` ${formatNullCounts(nulls)}`
      : '';
    console.log(`${id} ${lyceum.work}${nullSummary}`);
  }

  console.log(formatNullCounts(totals));
  if (!workFilter && !failed) {
    mkdirSync(join(dist, 'manifests'), { recursive: true });
    const index = buildIndex(entries, process.env.PUBLIC_DATA_ROOT ?? null);
    writeFileSync(join(dist, 'manifests', 'index.json'), `${JSON.stringify(index, null, 2)}\n`);
    console.log(`manifests/index.json ${entries.length} manifests`);
  }
  return failed ? 1 : 0;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) process.exitCode = await main();
