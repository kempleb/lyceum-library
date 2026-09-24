import { mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const PAGES_DIR = join(ROOT, 'app', 'src', 'pages');
const GENERATED_REGISTRY = join(ROOT, 'shared', 'lib', 'registry.generated.ts');
const OUT_PATH = join(ROOT, 'build', 'route-registry.json');

// Add a documented exception as { abbr, workIds }. The workIds must list the
// whole collision set, so a later third owner still fails the check.
//
// Rule (item 91c, John 2026-09-23, refined same day): short titles are
// distinguished by AUTHOR -- the uniqueness check below compares author
// PLUS abbreviation, so two different authors' works sharing an abbr (e.g.
// the coming Plato corpus's "Leg."/"Ep." against Cicero's De Legibus /
// Seneca's Epistulae) are not a collision. Two works by the SAME author
// sharing an abbr still are. An allowed entry here is likewise scoped to
// one author's collision set, since the check groups per author now.
export const ALLOWED_ABBR_COLLISIONS = [];

function folded(value) {
  return value.toLocaleLowerCase('en-US');
}

function groupedCollisions(values, keyOf) {
  const groups = new Map();
  for (const value of values) {
    const key = keyOf(value);
    const group = groups.get(key);
    if (group) group.push(value);
    else groups.set(key, [value]);
  }
  return [...groups.entries()].filter(([, group]) => group.length > 1);
}

export function workSlug(work) {
  return work.slug ?? work.id;
}

export function scanReservedSegments(pagesDir = PAGES_DIR) {
  const segments = new Set(['data']);
  for (const entry of readdirSync(pagesDir, { withFileTypes: true })) {
    let segment;
    if (entry.isDirectory()) segment = entry.name;
    else if (entry.isFile()) segment = entry.name.slice(0, -extname(entry.name).length);
    else continue;
    if (segment === '[author]' || segment === '404' || segment === 'index') continue;
    segments.add(segment);
  }
  return [...segments].sort((a, b) => a.localeCompare(b));
}

export function makeRoutes(works, authors, workCorpus) {
  const authorsById = new Map(authors.map((author) => [author.id, author]));
  return works.map((work) => {
    const author = authorsById.get(work.author);
    return {
      // `/<author>/<slug>` is an identity/dedupe key for this registry
      // (checkDuplicateRoutes below, pipeline/reader_pipeline/
      // validate_contracts.py) -- not a page address. The reader's real
      // addresses are workPath()/workLanding() in shared/lib/works.ts.
      route: `/${author?.id ?? work.author}/${workSlug(work)}`,
      corpus: workCorpus[work.id],
      work: work.id,
    };
  });
}

export function checkRegistryReferences(works, authors, workCorpus) {
  const problems = [];
  const authorIds = new Set(authors.map((author) => author.id));
  for (const work of works) {
    if (!authorIds.has(work.author)) {
      problems.push(`work '${work.id}' names unknown author '${work.author}'`);
    }
    if (typeof workCorpus[work.id] !== 'string' || !workCorpus[work.id]) {
      problems.push(`work '${work.id}' has no corpus in WORK_CORPUS_DATA`);
    }
  }
  return problems;
}

export function checkDuplicateRoutes(routes) {
  return groupedCollisions(routes, (entry) => entry.route).map(
    ([route, entries]) =>
      `duplicate route '${route}' for works: ${entries.map((entry) => entry.work).join(', ')}`,
  );
}

export function checkReservedSegments(authors, routes, reservedSegments) {
  const problems = [];
  const reserved = new Set(reservedSegments.map(folded));
  for (const author of authors) {
    if (reserved.has(folded(author.id))) {
      problems.push(`author id '${author.id}' uses reserved first segment '${author.id}'`);
    }
  }
  for (const entry of routes) {
    const firstSegment = entry.route.split('/').filter(Boolean)[0];
    if (firstSegment && reserved.has(folded(firstSegment))) {
      problems.push(`route '${entry.route}' uses reserved first segment '${firstSegment}'`);
    }
  }
  return problems;
}

export function checkCaseInsensitiveWorkIds(works) {
  return groupedCollisions(works, (work) => folded(work.id)).map(
    ([, group]) => `case-insensitive work-id collision: ${group.map((work) => `'${work.id}'`).join(', ')}`,
  );
}

export function checkSlugUniqueness(works) {
  return groupedCollisions(
    works,
    (work) => `${folded(work.author)}\u0000${folded(workSlug(work))}`,
  ).map(
    ([, group]) =>
      `slug collision within author '${group[0].author}': ` +
      `${group.map((work) => `'${workSlug(work)}' (${work.id})`).join(', ')}`,
  );
}

// Keyed on author + folded abbr (item 91c): a collision is only reported
// within one author's own works, so two different authors legitimately
// sharing a short title (Plato's "Leg." vs. Cicero's) never trips this.
function abbrKey(work) {
  return `${work.author}\u0000${folded(work.abbr)}`;
}

export function checkAbbrUniqueness(works, allowedCollisions = ALLOWED_ABBR_COLLISIONS) {
  const allowed = new Map(
    allowedCollisions.map(({ abbr, workIds }) => {
      const sortedIds = [...workIds].sort((a, b) => a.localeCompare(b));
      const author = works.find((work) => work.id === sortedIds[0])?.author;
      return [`${author}\u0000${folded(abbr)}`, sortedIds.join('\u0000')];
    }),
  );
  const problems = [];
  for (const [key, group] of groupedCollisions(works, abbrKey)) {
    const workIds = group.map((work) => work.id).sort((a, b) => a.localeCompare(b));
    if (allowed.get(key) === workIds.join('\u0000')) continue;
    problems.push(
      `abbreviation collision '${group[0].abbr}' for author '${group[0].author}': ${workIds.join(', ')}`,
    );
  }
  return problems;
}

export function checkRouteRegistry({ works, authors, workCorpus, reservedSegments }) {
  const routes = makeRoutes(works, authors, workCorpus);
  const problems = [
    ...checkRegistryReferences(works, authors, workCorpus),
    ...checkDuplicateRoutes(routes),
    ...checkReservedSegments(authors, routes, reservedSegments),
    ...checkCaseInsensitiveWorkIds(works),
    ...checkSlugUniqueness(works),
    ...checkAbbrUniqueness(works),
  ];
  return { routes, problems };
}

export async function main() {
  let registry;
  try {
    registry = await import(pathToFileURL(GENERATED_REGISTRY).href);
  } catch (error) {
    console.error(
      `build-route-registry: could not import ${GENERATED_REGISTRY}. ` +
        'Run node scripts/build-registry.mjs first.',
    );
    console.error(error instanceof Error ? error.message : String(error));
    return 1;
  }

  const reservedSegments = scanReservedSegments();
  const { routes, problems } = checkRouteRegistry({
    works: registry.CORPUS_WORKS,
    authors: registry.CORPUS_AUTHORS,
    workCorpus: registry.WORK_CORPUS_DATA,
    reservedSegments,
  });

  if (problems.length) {
    for (const problem of problems) console.error(`build-route-registry: ${problem}`);
  } else {
    mkdirSync(dirname(OUT_PATH), { recursive: true });
    writeFileSync(
      OUT_PATH,
      `${JSON.stringify({ schema_version: 'route-registry.v1', routes }, null, 2)}\n`,
    );
  }
  console.log(`${routes.length} route(s), ${problems.length} problem(s)`);
  return problems.length ? 1 : 0;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) process.exitCode = await main();
