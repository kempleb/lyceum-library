#!/usr/bin/env node
// The Lyceum Library acceptance script (docs/lyceum-shared-repo-plan.md
// §11.7). Given a running site (origin) and the place its data lives
// (data-origin), checks every Active catalog work in a headless browser and
// prints one line per work: PASS/FAIL/SKIP. Lives here until the
// `lyceum-contracts` repository the plan describes exists.
//
// Playwright is resolved the way app/scripts/shoot.mjs does -- not a project
// dependency (require('playwright'), then the npx cache). See
// resolvePlaywright below.
//
// Run: node scripts/acceptance.mjs --origin <url> --data-origin <url>
//        [--works a,b,c] [--fixture <path>]
// See docs/acceptance-script.md.

import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadLyceumSchema, validateAgainstSchema } from './emit-lyceum-manifest.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DEFAULT_FIXTURE = join(ROOT, 'fixtures', 'acceptance', 'expected-passages.json');
// The two committed editorial sources the running site itself merges at
// build/request time (shared/lib/lyceum-catalog-source.ts's parseCatalog).
// There is no network endpoint that exposes the merged, description-and-
// collections view for a locally-built (seed-only) work, so checks that need
// it read these files directly, the way app/src/lib/lyceum-catalog.ts does.
const DEFAULT_LIVE_CATALOG = join(ROOT, 'fixtures', 'catalog.snapshot.v2.live-2026-09-08.json');
const DEFAULT_SEED_CATALOG = join(ROOT, 'fixtures', 'editorial.seed.json');

// ── Playwright resolution (copied from app/scripts/shoot.mjs; kept local so
//    this script has no dependency on that file) ───────────────────────────
function resolvePlaywright() {
  const require = createRequire(import.meta.url);
  try {
    return require('playwright');
  } catch { /* fall through to the npx cache */ }
  const npxRoot = join(homedir(), '.npm', '_npx');
  if (existsSync(npxRoot)) {
    for (const hash of readdirSync(npxRoot)) {
      const p = join(npxRoot, hash, 'node_modules', 'playwright');
      if (existsSync(p)) return require(p);
    }
  }
  throw new Error(
    'Playwright not found. Install it (npm i -D playwright) or run `npx playwright --version` once to populate the cache.',
  );
}

function ensureBrowsersPath() {
  if (!process.env.PLAYWRIGHT_BROWSERS_PATH) {
    const cache = join(homedir(), 'Library', 'Caches', 'ms-playwright');
    if (existsSync(cache)) process.env.PLAYWRIGHT_BROWSERS_PATH = cache;
  }
}

// ── Timeouts (Sol review, P2 finding 15) ────────────────────────────────
// Every network fetch and every Playwright navigation/action gets a bounded
// deadline, so a hung server or a stalled browser subprocess fails this
// script instead of hanging it forever.
const FETCH_TIMEOUT_MS = 10_000;
const NAV_TIMEOUT_MS = 15_000;

async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

// ── CLI ──────────────────────────────────────────────────────────────────

const HELP = `Usage: node scripts/acceptance.mjs --origin <url> --data-origin <url> [options]

Checks every Active work in the running Lyceum site (docs/lyceum-shared-repo-plan.md
section 11.7) and prints one PASS/FAIL/SKIP line per work, then a summary.
Exits 1 if any check failed, 0 otherwise.

Required:
  --origin <url>        the site under test, e.g. http://localhost:8787
  --data-origin <url>   where the manifests and /data/ live (same as --origin
                         for a local run with PUBLIC_DATA_ROOT unset)

Options:
  --works a,b,c          restrict to these work ids (our registry ids, e.g. EN);
                          default is every Active work in the catalog file
  --fixture <path>        expected-passages fixture (default: fixtures/acceptance/expected-passages.json)
  --live-catalog <path>   committed live catalog file (default: fixtures/catalog.snapshot.v2.live-2026-09-08.json)
  --seed-catalog <path>   committed editorial seed file (default: fixtures/editorial.seed.json)
  --drafts                the build under test includes draft works (PUBLIC_LYCEUM_DRAFTS=1) --
                          negative:inactive-no-landing then picks a non-active, non-draft work
                          instead, since a draft work's landing page returns 200, not 404
  --help                  print this message and exit 0

Env:
  LYCEUM_PUBLISH_TOKEN    exercises the authenticated publish-endpoint checks
                          and is scanned for as a credential leak
`;

export function parseArgs(argv) {
  const out = { origin: null, dataOrigin: null, works: null, fixture: DEFAULT_FIXTURE,
    liveCatalog: DEFAULT_LIVE_CATALOG, seedCatalog: DEFAULT_SEED_CATALOG, drafts: false, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    switch (arg) {
      case '--help':
      case '-h':
        out.help = true;
        break;
      case '--origin':
        out.origin = argv[++i] ?? null;
        break;
      case '--data-origin':
        out.dataOrigin = argv[++i] ?? null;
        break;
      case '--works':
        out.works = (argv[++i] ?? '').split(',').map((s) => s.trim()).filter(Boolean);
        break;
      case '--fixture':
        out.fixture = argv[++i] ?? out.fixture;
        break;
      case '--live-catalog':
        out.liveCatalog = argv[++i] ?? out.liveCatalog;
        break;
      case '--seed-catalog':
        out.seedCatalog = argv[++i] ?? out.seedCatalog;
        break;
      case '--drafts':
        out.drafts = true;
        break;
      default:
        throw new Error(`unknown argument: ${arg}`);
    }
  }
  return out;
}

// ── Fixture ─────────────────────────────────────────────────────────────

/** Validates the expected-passages fixture shape. Returns {ok, errors}. */
export function validateFixtureShape(json) {
  const errors = [];
  if (json === null || typeof json !== 'object' || Array.isArray(json)) {
    return { ok: false, errors: ['fixture must be a JSON object'] };
  }
  if (json.schema_version !== 1) errors.push('fixture.schema_version must be 1');
  if (json.works === null || typeof json.works !== 'object' || Array.isArray(json.works)) {
    errors.push('fixture.works must be an object keyed by work id');
    return { ok: errors.length === 0, errors };
  }
  for (const [workId, entry] of Object.entries(json.works)) {
    const at = (msg) => errors.push(`works.${workId}: ${msg}`);
    if (entry === null || typeof entry !== 'object') { at('must be an object'); continue; }
    if (typeof entry.edition !== 'string' || !entry.edition) at('edition must be a non-empty string');
    if (entry.reviewed_by !== null && typeof entry.reviewed_by !== 'string') {
      at('reviewed_by must be null or a string');
    }
    if (!Array.isArray(entry.passages) || entry.passages.length === 0) {
      at('passages must be a non-empty array');
      continue;
    }
    entry.passages.forEach((p, i) => {
      const pat = (msg) => errors.push(`works.${workId}.passages[${i}]: ${msg}`);
      if (!['first', 'middle', 'last'].includes(p?.position)) pat('position must be first, middle, or last');
      if (typeof p?.address !== 'string' || !p.address.startsWith('/')) pat('address must be a root-relative string');
      if (!['grc', 'lat', 'en'].includes(p?.language)) pat('language must be grc, lat, or en');
      if (typeof p?.opening !== 'string' || !p.opening.trim()) pat('opening must be a non-empty string');
      // John, 2026-09-23: search-finds must search for a phrase set per
      // sample passage, not the first three words of `opening` -- an
      // opening can start with a source citation or title rather than the
      // passage's own words. `search` is optional (searchPhraseFor falls
      // back to the old first-three-words behaviour when absent) but must
      // be a non-empty string when present.
      if (p && typeof p === 'object' && 'search' in p && (typeof p.search !== 'string' || !p.search.trim())) {
        pat('search must be a non-empty string when present');
      }
    });
    // Sol review, finding 4: a one-passage or duplicate-position fixture
    // (e.g. three "first"s) used to pass as "three passages" -- the checks
    // above only required a nonempty array. Require exactly one of each.
    for (const position of ['first', 'middle', 'last']) {
      const count = entry.passages.filter((p) => p?.position === position).length;
      if (count !== 1) at(`must have exactly one '${position}' passage, found ${count}`);
    }
  }
  return { ok: errors.length === 0, errors };
}

export function loadFixture(path) {
  let json;
  try {
    json = JSON.parse(readFileSync(path, 'utf8'));
  } catch (err) {
    console.error(`acceptance: could not read/parse fixture ${path}: ${err.message}`);
    process.exit(2);
  }
  const { ok, errors } = validateFixtureShape(json);
  if (!ok) {
    console.error(`acceptance: fixture ${path} is malformed:`);
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(2);
  }
  return json;
}

// ── Catalog merge (mirrors shared/lib/lyceum-catalog-source.ts's parseCatalog
//    just enough for this script's own checks: which id wins between live and
//    seed, each work's editorial fields, and collection names) ────────────

function isPlainObject(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** Live-wins merge of the live catalog + our editorial seed, pure. Returns
 *  { works: Map<id, {description, collectionIds, defaultTranslation, preset, state}>,
 *    allWorks: Map<id, (same shape, every state, unfiltered)>,
 *    collections: Map<id, name>, defaultPreset }.
 *  `opts.includeDrafts` (default false, set by the script's own --drafts
 *  flag): both `works` and `collections` filter to `active` state only,
 *  unless includeDrafts keeps `draft` too -- mirrors
 *  shared/lib/lyceum-catalog-source.ts's parseCatalog (mergeById + keep),
 *  so a work (or a work linked to a draft collection) is expected here
 *  exactly as it will (or won't) render on the page. `allWorks` keeps every
 *  work regardless of state -- callers that need to know a dropped work's
 *  own state (selectWorkIds' SKIP reason, selectInactiveWork's negative
 *  check) read that map, never `works`. */
export function mergeCatalog(liveJson, seedJson, opts = {}) {
  const includeDrafts = opts.includeDrafts === true;
  const rawWorks = new Map();
  const rawCollections = new Map();
  // Sol review, finding 2: parseCatalog (shared/lib/lyceum-catalog-source.ts,
  // toWork) drops an editorial.preset name absent from the live catalog's own
  // presentation.presets -- this merge used to keep any string verbatim.
  // Mirrored here (and applied to defaultPreset too, which parseCatalog also
  // validates against the same set).
  const presentation = isPlainObject(liveJson) && isPlainObject(liveJson.presentation) ? liveJson.presentation : {};
  const presetIds = new Set(isPlainObject(presentation.presets) ? Object.keys(presentation.presets) : []);
  const addWorks = (list) => {
    for (const raw of Array.isArray(list) ? list : []) {
      if (!isPlainObject(raw) || typeof raw.id !== 'string') continue;
      const editorial = isPlainObject(raw.editorial) ? raw.editorial : {};
      const rawPreset = typeof editorial.preset === 'string' ? editorial.preset : '';
      rawWorks.set(raw.id, {
        description: typeof editorial.description === 'string' ? editorial.description : '',
        collectionIds: Array.isArray(editorial.collection_ids)
          ? editorial.collection_ids.filter((v) => typeof v === 'string') : [],
        defaultTranslation: typeof editorial.default_translation === 'string' ? editorial.default_translation : '',
        preset: presetIds.has(rawPreset) ? rawPreset : '',
        state: typeof editorial.state === 'string' ? editorial.state : 'draft',
        facts: isPlainObject(raw.facts) ? raw.facts : {},
      });
    }
  };
  const addCollections = (list) => {
    for (const raw of Array.isArray(list) ? list : []) {
      if (!isPlainObject(raw) || typeof raw.id !== 'string') continue;
      rawCollections.set(raw.id, {
        name: typeof raw.name === 'string' ? raw.name : raw.id,
        state: typeof raw.state === 'string' ? raw.state : 'draft',
      });
    }
  };
  addCollections(isPlainObject(seedJson) ? seedJson.collections : undefined);
  addCollections(isPlainObject(liveJson) ? liveJson.collections : undefined);
  addWorks(isPlainObject(seedJson) ? seedJson.works : undefined);
  addWorks(isPlainObject(liveJson) ? liveJson.works : undefined);
  const theme = isPlainObject(presentation.theme) ? presentation.theme : {};
  const rawDefaultPreset = typeof theme.preset === 'string' ? theme.preset : '';
  const defaultPreset = presetIds.has(rawDefaultPreset) ? rawDefaultPreset : '';
  // Same keep() rule as parseCatalog: active is always kept, draft only
  // when includeDrafts -- a draft collection a work names is otherwise
  // absent from this map entirely, so checkLanding's expectedCollections
  // (below) drops it the same way the rendered page will.
  const collections = new Map();
  for (const [id, c] of rawCollections) {
    if (c.state === 'active' || (includeDrafts && c.state === 'draft')) {
      collections.set(id, c.name);
    }
  }
  // Same keep() rule applied to works themselves (Codex Sol re-verification
  // of 8131f40, item 1): mergeCatalog used to hand back a work of ANY state,
  // so a dropped (non-active, non-kept-draft) work would still be checked as
  // if the catalog served it. `works` now matches what parseCatalog would
  // actually render; `allWorks` keeps the unfiltered view for callers that
  // need to explain *why* a work was dropped.
  const works = new Map();
  for (const [id, w] of rawWorks) {
    if (w.state === 'active' || (includeDrafts && w.state === 'draft')) {
      works.set(id, w);
    }
  }
  return { works, allWorks: rawWorks, collections, defaultPreset };
}

// ── Work selection ──────────────────────────────────────────────────────

/**
 * Builds the manifest-index lookups: shortId (the manifest's own directory
 * segment, e.g. 'EN') <-> lyceum key (e.g. 'lyceum:aristotle.en'), derived
 * from each entry's own `path` ('/EN/manifest.lyceum.json') -- never
 * reconstructed by guessing at route segments.
 */
export function indexLookups(manifestIndexJson) {
  const shortIdToEntry = new Map();
  const lyceumKeyToShortId = new Map();
  for (const entry of manifestIndexJson?.manifests ?? []) {
    const match = /^\/([^/]+)\//.exec(entry.path ?? '');
    if (!match) continue;
    shortIdToEntry.set(match[1], entry);
    lyceumKeyToShortId.set(entry.work, match[1]);
  }
  return { shortIdToEntry, lyceumKeyToShortId };
}

/**
 * The work set to check, pure. `explicitWorks`: the --works list of short
 * ids, or null for "every Active work". `mergedWorks`: the kept (`works`)
 * Map from mergeCatalog. `allWorks`: mergeCatalog's unfiltered map, read
 * only to explain a `--works` id that names a real catalog work mergeCatalog
 * itself dropped (Codex Sol re-verification of 8131f40, item 1) -- a work
 * present in the catalog but not active (or draft without --drafts) is
 * skipped, not silently checked as if the live page served it.
 * `lyceumKeyToShortId`/`shortIdToEntry`: from indexLookups.
 * Returns an array of { displayId, lyceumKey, shortId, manifestEntry } |
 * { displayId, skip: reason }.
 */
export function selectWorkIds({ explicitWorks, mergedWorks, allWorks, lyceumKeyToShortId, shortIdToEntry }) {
  const out = [];
  if (explicitWorks && explicitWorks.length > 0) {
    for (const shortId of explicitWorks) {
      const entry = shortIdToEntry.get(shortId);
      if (!entry) {
        out.push({ displayId: shortId, skip: 'not built in this release' });
        continue;
      }
      if (!mergedWorks.has(entry.work)) {
        const raw = allWorks?.get(entry.work);
        if (raw) {
          out.push({ displayId: shortId, skip: `not active in the catalog (state ${raw.state})` });
          continue;
        }
      }
      out.push({ displayId: shortId, lyceumKey: entry.work, shortId, manifestEntry: entry });
    }
    return out;
  }
  for (const [lyceumKey, work] of mergedWorks) {
    if (work.state !== 'active') continue;
    const shortId = lyceumKeyToShortId.get(lyceumKey);
    if (!shortId) {
      out.push({ displayId: lyceumKey, skip: 'not built in this release' });
      continue;
    }
    out.push({ displayId: shortId, lyceumKey, shortId, manifestEntry: shortIdToEntry.get(shortId) });
  }
  return out;
}

// ── Pure check helpers (network/DOM-free; exercised directly in tests) ───

/** Any URL whose host is neither `originHost` nor `dataOriginHost` --
 *  used by the no-foreign-requests check. */
export function foreignRequests(urls, originHost, dataOriginHost) {
  const offenders = [];
  for (const raw of urls) {
    let host;
    try { host = new URL(raw).host; } catch { continue; }
    if (host !== originHost && host !== dataOriginHost) offenders.push(raw);
  }
  return offenders;
}

/** Credential strings that must never appear in reader-facing HTML/JS. */
export function scanForCredentials(text, token) {
  const hits = [];
  if (token && text.includes(token)) hits.push('LYCEUM_PUBLISH_TOKEN value');
  if (text.includes('LYCEUM_PUBLISH_TOKEN=')) hits.push('LYCEUM_PUBLISH_TOKEN=');
  if (text.includes('Authorization: Bearer')) hits.push('Authorization: Bearer');
  return hits;
}

const WS_RE = /\s+/g;
export function normalizeWhitespace(s) {
  return s.replace(WS_RE, ' ').trim();
}

/** True when `renderedText` (whitespace-normalised) starts with `opening`
 *  (also normalised). */
export function startsWithOpening(renderedText, opening) {
  return normalizeWhitespace(renderedText).startsWith(normalizeWhitespace(opening));
}

/** The phrase `search-finds` types into the search box for a passage.
 *  John, 2026-09-23: a sample passage's `opening` can start with a source
 *  citation or title rather than the passage's own words (Heraclitus B1's
 *  "SEXT. adv. math. VII 132 ...", Seneca Letter 1.1's "AD LVCILIVM
 *  EPISTVLAE ..."), so a passage may set its own `search` string. Falls
 *  back to the first three words of `opening` -- today's behaviour -- when
 *  `search` is absent, so an unfilled fixture entry is unchanged. */
export function searchPhraseFor(passage) {
  if (typeof passage?.search === 'string' && passage.search.trim()) return passage.search;
  return passage.opening.split(/\s+/).slice(0, 3).join(' ');
}

// ── Result lines ────────────────────────────────────────────────────────

export function passLine(work, note) {
  return `PASS ${work}${note ? ` (${note})` : ''}`;
}
export function failLine(work, check, detail) {
  return `FAIL ${work}: ${check}${detail ? ` (${detail})` : ''}`;
}
export function skipLine(work, reason) {
  return `SKIP ${work}: ${reason}`;
}

export function summarize(lines) {
  let pass = 0; let fail = 0; let skip = 0;
  for (const line of lines) {
    if (line.startsWith('PASS ')) pass += 1;
    else if (line.startsWith('FAIL ')) fail += 1;
    else if (line.startsWith('SKIP ')) skip += 1;
  }
  return { pass, fail, skip, exitCode: fail > 0 ? 1 : 0 };
}

// ── Network helpers ─────────────────────────────────────────────────────

async function fetchText(url) {
  const res = await fetchWithTimeout(url);
  const text = await res.text();
  return { ok: res.ok, status: res.status, text, headers: res.headers };
}

/** Fetches the manifest index, trying `${dataOrigin}/manifests/index.json`
 *  first (the plan's own address, matching a real R2 data-origin) and
 *  falling back to `${dataOrigin}/data/manifests/index.json` (how a local
 *  build with PUBLIC_DATA_ROOT unset actually serves it -- see
 *  docs/acceptance-script.md). Returns { json, indexUrl }. `indexUrl` is
 *  `res.url` (the address actually served, following any redirect), not the
 *  candidate URL requested -- Sol review finding 1: resolveManifestUrl below
 *  resolves each entry's path against wherever the index truly lives, so a
 *  redirected index (e.g. a trailing-slash or host normalisation) must not
 *  resolve entries against the pre-redirect URL. A 200 response whose body
 *  is not valid JSON (finding 13) is treated as a failed candidate and the
 *  loop continues to the next one, rather than throwing out of the function
 *  and skipping the fallback entirely. */
export async function fetchManifestIndex(dataOrigin) {
  for (const path of ['/manifests/index.json', '/data/manifests/index.json']) {
    const url = `${dataOrigin}${path}`;
    let res;
    try {
      res = await fetchWithTimeout(url);
    } catch {
      continue;
    }
    if (!res.ok) continue;
    let json;
    try {
      json = await res.json();
    } catch {
      continue;
    }
    return { json, indexUrl: res.url };
  }
  throw new Error(`no manifest index found at ${dataOrigin}/manifests/index.json or ${dataOrigin}/data/manifests/index.json`);
}

/**
 * Resolves a manifest entry's address. The index's own `url`/`data_root`
 * fields point at wherever the build that emitted them expected to publish
 * (a real R2 domain even for a local dev build), which is not reachable from
 * a local run -- so this resolves `entry.path` against the URL the index
 * was itself fetched from, matching the plan's own fallback rule ("no data
 * root: resolves against the index's own origin") generalised to "the
 * index's own location". See docs/acceptance-script.md.
 */
export function resolveManifestUrl(entry, indexUrl) {
  // The index lives at '<data root>/manifests/index.json' (both locally and
  // on a real deploy); 'entry.path' is root-relative to that SAME data root,
  // not to the 'manifests/' directory the index itself sits in. '..' climbs
  // out of 'manifests/' back to the data root before joining the path.
  const dataRoot = new URL('..', indexUrl);
  return new URL(entry.path.replace(/^\//, ''), dataRoot).toString();
}

function sha256Hex(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

// ── Per-work checks ─────────────────────────────────────────────────────

async function checkManifest(entry, indexUrl, displayId) {
  const manifestUrl = resolveManifestUrl(entry, indexUrl);
  let res;
  try {
    res = await fetchWithTimeout(manifestUrl);
  } catch (err) {
    return { fail: failLine(displayId, 'manifest-fetch', `${manifestUrl}: ${err.message}`) };
  }
  if (!res.ok) {
    return { fail: failLine(displayId, 'manifest-fetch', `${manifestUrl} -> ${res.status}`) };
  }
  const buf = new Uint8Array(await res.arrayBuffer());
  const actualSha = sha256Hex(buf);
  if (actualSha !== entry.sha256) {
    return { fail: failLine(displayId, 'manifest-hash', `expected ${entry.sha256}, got ${actualSha}`) };
  }
  let manifestJson;
  try {
    manifestJson = JSON.parse(Buffer.from(buf).toString('utf8'));
  } catch (err) {
    return { fail: failLine(displayId, 'manifest-schema', `not valid JSON: ${err.message}`) };
  }
  const schemaErrors = validateAgainstSchema(manifestJson, loadLyceumSchema());
  if (schemaErrors.length > 0) {
    const first = schemaErrors[0];
    return { fail: failLine(displayId, 'manifest-schema', `${first.path} ${first.message}`) };
  }
  return { manifestJson, manifestUrl };
}

async function checkCatalogEntry(origin, lyceumKey, indexCorpusVersion, displayId) {
  let catalog;
  try {
    const { ok, status, text } = await fetchText(`${origin}/catalog.snapshot.json`);
    if (!ok) return failLine(displayId, 'catalog-entry', `${origin}/catalog.snapshot.json -> ${status}`);
    catalog = JSON.parse(text);
  } catch (err) {
    return failLine(displayId, 'catalog-entry', `fetching ${origin}/catalog.snapshot.json: ${err.message}`);
  }
  const work = (Array.isArray(catalog.works) ? catalog.works : []).find((w) => w?.id === lyceumKey);
  if (!work) {
    return failLine(displayId, 'catalog-entry', `work not present in ${origin}/catalog.snapshot.json`);
  }
  const facts = isPlainObject(work.facts) ? work.facts : {};
  // Sol review, finding 3: the catalog work was found by its top-level `id`,
  // but `facts.work` is a separate, independently-declared field (see e.g.
  // fixtures/catalog.snapshot.v2.live-2026-09-08.json's caesar.civil-war
  // entry) that should name the very same lyceum key -- catching drift
  // between the catalog's own id and what the work's facts declare about
  // itself, which the id match alone cannot catch.
  if (facts.work !== lyceumKey) {
    return failLine(displayId, 'catalog-entry', `catalog entry facts.work '${facts.work}' != expected '${lyceumKey}'`);
  }
  if (typeof facts.corpus_version !== 'string' || !facts.corpus_version) {
    return failLine(displayId, 'catalog-entry', 'catalog entry carries no facts.corpus_version');
  }
  if (facts.corpus_version !== indexCorpusVersion) {
    return failLine(displayId, 'catalog-entry',
      `catalog facts.corpus_version ${facts.corpus_version} != manifest index corpus_version ${indexCorpusVersion}`);
  }
  return null;
}

/** Finds the element whose id matches `fragment` case-insensitively (the
 *  manifest lowercases loci fragments; the reader resolves the same way --
 *  see docs/lyceum-shared-repo-plan.md §11.7 and shared/lib/data.ts). */
async function findAnchorText(page, fragment) {
  return page.evaluate((frag) => {
    const target = frag.toLowerCase();
    for (const el of document.querySelectorAll('[id]')) {
      if (el.id.toLowerCase() === target) return el.innerText || el.textContent || '';
    }
    return null;
  }, fragment);
}

/** Strips the anchor's own `col-` id prefix, case-insensitively, leaving the
 *  bare column token (`'col-1094A'` -> `'1094a'`, `'B30'` -> `'b30'`)
 *  pulled out as a pure, unit-testable step -- see findColumnText below. */
export function stripColPrefix(fragment) {
  return fragment.toLowerCase().replace(/^col-/, '');
}

/**
 * The `#col-<fragment>` element (found above) also wraps the chapter head
 * and the per-passage translation-picker buttons -- chrome that will never
 * start with the passage's own opening words. Confirmed against
 * shared/components/Reader.svelte: the source-language subtree is the
 * descendant carrying `data-column`, whose value is the BARE column token
 * with no 'col-' prefix (`data-column={seg.column}`) -- unlike the anchor's
 * own id (`id="col-{seg.column}"`) and the address fragment passed in here
 * (which keeps the 'col-' prefix, e.g. '#col-1094a'). Comparing the raw
 * fragment against `data-column` therefore never matched (Sol review,
 * finding 5) -- fixed by stripping the prefix before comparing. The English
 * subtree carries no `data-column` at all, only an `.english-col` class
 * (also confirmed against Reader.svelte), so an English request selects
 * that class directly rather than falling through the (always-empty)
 * `[data-column]` search. Returns '' -- not the whole anchor's chrome-
 * inclusive text -- when the expected language subtree isn't found, so a
 * caller's opening-words check fails loudly instead of a chrome string
 * passing by accident; returns null only when the anchor itself isn't
 * found.
 *
 * The matched subtree also carries its own `.line-num` gutter labels
 * (shared/components/Reader.svelte, both `.greek-col` and `.english-col`) --
 * marked `user-select: none` there specifically so a person's own
 * select-and-copy never picks them up. Found by the acceptance rehearsal,
 * 2026-09-23: a person's read of Rackham's opening line is "Πᾶσα τέχνη...",
 * but the unstripped element's own innerText read "1 Πᾶσα τέχνη..." (the
 * line-1 gutter label), so an opening-words check against the former always
 * failed on any passage starting a fresh numbered line -- reliably the
 * `first` position of every fixture entry. Stripped here the same way the
 * person's own selection already excludes it, before the opening-words
 * comparison ever sees the text.
 */
/** Nodes to strip from a matched column's clone before reading its opening
 *  words for comparison, on top of the `.line-num` gutter above:
 *  `.bk-num`, the Bekker-number gutter rendered inside the same column
 *  (shared/components/Reader.svelte:3026-3031, 3071-3076), and any node
 *  marked `aria-hidden="true"` -- decorative markup Reader also renders
 *  inside a text column, none of it real reading text: section-tick marks,
 *  the missing-translation em dash, and, the one that actually misled a
 *  comparison (acceptance rehearsal, 2026-09-23), the hidden chapter-title
 *  spacer that keeps the Greek and English columns the same height
 *  (Reader.svelte:3744: `<div class="overlay-chapter-title
 *  overlay-chapter-title-spacer" aria-hidden="true">{spacerTitle}</div>`).
 *  Pulled out as exported data, not left inline in the page.evaluate
 *  string below, so its membership is unit-testable without a DOM
 *  (scripts/__tests__/acceptance.test.mjs) even though the removal itself
 *  has to run in-browser against the live clone. */
export const READABLE_TEXT_STRIP_SELECTORS = ['.line-num', '.bk-num', '[aria-hidden="true"]'];

async function findColumnText(page, fragment, language) {
  const target = fragment.toLowerCase();
  const columnToken = stripColPrefix(fragment);
  const wantEnglish = language === 'en';
  return page.evaluate(({ target, columnToken, wantEnglish, stripSelectors }) => {
    const readableText = (el) => {
      const clone = el.cloneNode(true);
      stripSelectors.forEach((sel) => clone.querySelectorAll(sel).forEach((n) => n.remove()));
      return clone.textContent || '';
    };
    let anchor = null;
    for (const el of document.querySelectorAll('[id]')) {
      if (el.id.toLowerCase() === target) { anchor = el; break; }
    }
    if (!anchor) return null;
    if (wantEnglish) {
      const eng = anchor.querySelector('.english-col');
      return eng ? readableText(eng) : '';
    }
    const match = [...anchor.querySelectorAll('[data-column]')]
      .find((el) => (el.getAttribute('data-column') || '').toLowerCase() === columnToken);
    return match ? readableText(match) : '';
  }, { target, columnToken, wantEnglish, stripSelectors: READABLE_TEXT_STRIP_SELECTORS });
}

export function splitAddress(address) {
  const hashIndex = address.indexOf('#');
  return hashIndex === -1
    ? { path: address, fragment: null }
    : { path: address.slice(0, hashIndex), fragment: address.slice(hashIndex + 1) };
}

/**
 * True when a rendered `.inst-ref` anchor's `href` (Search.svelte's own
 * `jumpFor`: `<root><workPath>?...&loc=<column>[:<line>]`, no '#' fragment)
 * points at the same passage as a fixture `address`
 * (`<path>#col-<column>[...]`, the reader's own #-anchor scheme). Compares
 * the path prefix, then the `loc=` value's column segment (before any ':')
 * against the address fragment with its 'col-' prefix stripped -- the same
 * stripping findColumnText/stripColPrefix does, since it is the identical
 * mismatch (an address fragment keeps 'col-', a rendered column marker does
 * not). Pure -- exercised directly in tests (Sol review finding 16).
 */
/** True when `href` names exactly `path` as its own route, not merely a
 *  route that happens to start with the same characters (Grok review
 *  finding B: `href.startsWith(path)` let `/read/x/y/letter-1` match a hit
 *  at `/read/x/y/letter-10?loc=...`, since 'letter-10' starts with
 *  'letter-1'). The character right after `path` in `href` must end that
 *  path segment: '?', '#', or nothing (href === path exactly). */
function hrefPathMatches(href, path) {
  if (!href.startsWith(path)) return false;
  const next = href.charAt(path.length);
  return next === '' || next === '?' || next === '#';
}

export function instRefMatchesAddress(href, address) {
  const { path, fragment } = splitAddress(address);
  if (!hrefPathMatches(href, path)) return false;
  if (!fragment) return true;
  const column = stripColPrefix(fragment);
  const locMatch = /[?&]loc=([^&]+)/.exec(href);
  if (!locMatch) return false;
  const locColumn = decodeURIComponent(locMatch[1]).toLowerCase().split(':')[0];
  return locColumn === column;
}

async function gotoAndSettle(page, url) {
  const res = await page.goto(url, { waitUntil: 'load', timeout: NAV_TIMEOUT_MS });
  return res;
}

/**
 * Pure companion to checkLanding's `main.lp-body` extraction: `null` means
 * the element itself was missing (a real rendering failure), as opposed to
 * an empty string (an empty-but-present element). Extracted so the
 * null-means-FAIL decision is testable without a browser.
 */
export function landingBodyTextFailReason(mainInnerText) {
  return mainInnerText == null ? 'no main.lp-body' : null;
}

/**
 * Pure: compares the collections actually rendered on the landing page
 * (read from `[data-collections] [data-collection-id]`, each `{id, name}`,
 * in DOM order) against the work's own merged-catalog collections, in the
 * order editorial.collection_ids itself promises. A duplicate id anywhere in
 * `rendered` is always a failure. `opts.hasContainer` (defaults to
 * `rendered.length > 0` when omitted, for callers that never had a
 * container to check) tells apart "no `[data-collections]` element at all"
 * (the correct rendering of a work with no kept collections) from "the
 * element is there but empty" (a real defect, its own failure reason). A
 * duplicate id in `expected` is caught before any length comparison and
 * reported by name -- that is the catalog's own editorial.collection_ids
 * naming the same collection twice, not a page defect (Codex Sol
 * re-verification of 8131f40, item 2: unequal lengths with a duplicated
 * expected id used to find neither a missing nor an extra entry and
 * dereference undefined).
 * Returns a failure reason, or null when they agree.
 */
export function collectionMismatchReason(rendered, expected, opts = {}) {
  const hasContainer = opts.hasContainer === undefined ? rendered.length > 0 : opts.hasContainer;

  const seen = new Set();
  for (const r of rendered) {
    if (seen.has(r.id)) return `page renders collection '${r.id}' more than once`;
    seen.add(r.id);
  }

  const expectedSeen = new Set();
  for (const e of expected) {
    if (expectedSeen.has(e.id)) return `catalog names collection '${e.id}' more than once for this work`;
    expectedSeen.add(e.id);
  }

  if (expected.length === 0) {
    if (hasContainer) return 'page renders an empty [data-collections] element; expected none at all';
    return null;
  }

  if (!hasContainer) {
    return `page is missing collection '${expected[0].id}' (${expected[0].name})`;
  }

  if (rendered.length !== expected.length) {
    const renderedIds = new Set(rendered.map((r) => r.id));
    const missing = expected.find((e) => !renderedIds.has(e.id));
    if (missing) return `page is missing collection '${missing.id}' (${missing.name})`;
    const expectedIds = new Set(expected.map((e) => e.id));
    const extra = rendered.find((r) => !expectedIds.has(r.id));
    if (extra) return `page renders unexpected collection '${extra.id}' (${extra.name})`;
    return `collection count mismatch: expected ${expected.length}, page rendered ${rendered.length}`;
  }

  for (let i = 0; i < expected.length; i += 1) {
    if (rendered[i].id !== expected[i].id) {
      return `collection order mismatch at position ${i}: expected '${expected[i].id}', got '${rendered[i].id}'`;
    }
    if (rendered[i].name !== expected[i].name) {
      return `collection '${expected[i].id}' rendered as '${rendered[i].name}', expected '${expected[i].name}'`;
    }
  }
  return null;
}

async function checkLanding(page, origin, work, displayId) {
  const url = `${origin}${work.facts.route ?? ''}`;
  if (!work.facts.route) return failLine(displayId, 'landing-renders', 'no route in manifest facts');
  let res;
  try {
    res = await gotoAndSettle(page, url);
  } catch (err) {
    return failLine(displayId, 'landing-renders', `${url}: ${err.message}`);
  }
  // Sol review, finding 6: Playwright's Response.ok() is true for any 2xx,
  // not just 200 -- a landing page served as e.g. a 204 or a soft-redirect
  // 3xx-turned-2xx would have passed this check. The site never intends
  // anything but a plain 200 for a rendered landing page.
  if (!res || res.status() !== 200) return failLine(displayId, 'landing-renders', `${url} -> ${res ? res.status() : 'no response'}`);
  // Grok review finding D: `document.body.innerText.includes(...)` let ANY
  // string anywhere on the page satisfy this check. Concretely, on
  // app/src/components/Landing.astro the sitewide Breadcrumb dropdowns
  // (`authorOptions`/`workOptions`, built from EVERY built author/work in
  // the site -- see Landing.astro's own `builtAuthors()`/`builtWorksOf()`
  // calls) render as a sibling of `<main>`, so they alone would satisfy a
  // match against most collection/author names regardless of whether this
  // particular work belongs to that collection. Scoped to
  // `<main class="lp-body">` -- Landing.astro's own content region -- which
  // excludes that nav chrome (and the header/breadcrumb/search links above
  // it) entirely.
  //
  // Follow-up Grok review of commit 43e8323: falling back to
  // `document.body.innerText` when `main.lp-body` is missing reopened the
  // exact whole-page false PASS finding D fixed -- a landing page that
  // failed to render its content region could still match the nav chrome
  // and PASS. The DOM query has to happen inside page.evaluate, but the
  // null-means-FAIL decision doesn't need a browser, so it's pulled out
  // into `landingBodyTextFailReason` (pure, tested directly) instead of
  // falling back to the whole page.
  // Landing.astro's own description element (`.lp-lede`, the work's blurb --
  // seeded from the same catalog editorial.description text) and its
  // collection list (`[data-collections] [data-collection-id]`, added
  // specifically for this check) -- read by dedicated selector rather than
  // scanning `main`'s whole text, so a coincidental text match elsewhere in
  // the page can't satisfy either half.
  const pageData = await page.evaluate(() => {
    const main = document.querySelector('main.lp-body');
    if (!main) return null;
    const descEl = main.querySelector('.lp-lede');
    const container = main.querySelector('[data-collections]');
    const collectionEls = container ? Array.from(container.querySelectorAll('[data-collection-id]')) : [];
    return {
      description: descEl ? (descEl.textContent || '').trim() : '',
      hasCollectionsContainer: container !== null,
      collections: collectionEls.map((el) => ({
        id: el.getAttribute('data-collection-id') || '',
        name: (el.textContent || '').trim(),
      })),
    };
  });
  const failReason = landingBodyTextFailReason(pageData);
  if (failReason) return failLine(displayId, 'landing-renders', failReason);
  const merged = work.merged;
  if (merged.description && pageData.description !== merged.description) {
    return failLine(displayId, 'landing-renders', `page description does not match catalog description`);
  }
  const expectedCollections = merged.collectionIds
    .map((cid) => ({ id: cid, name: work.collections.get(cid) }))
    .filter((c) => typeof c.name === 'string');
  const collectionsFail = collectionMismatchReason(
    pageData.collections, expectedCollections, { hasContainer: pageData.hasCollectionsContainer },
  );
  if (collectionsFail) return failLine(displayId, 'landing-renders', collectionsFail);
  return null;
}

async function checkReading(page, origin, address, displayId, checkName) {
  const { path, fragment } = splitAddress(address);
  let res;
  try {
    res = await gotoAndSettle(page, `${origin}${path}`);
  } catch (err) {
    return { fail: failLine(displayId, checkName, `${path}: ${err.message}`) };
  }
  if (!res || !res.ok()) return { fail: failLine(displayId, checkName, `${path} -> ${res ? res.status() : 'no response'}`) };
  let text;
  if (fragment) {
    text = await findAnchorText(page, fragment);
    if (text == null) return { fail: failLine(displayId, checkName, `no element with id (case-insensitive) '${fragment}'`) };
  } else {
    text = await page.evaluate(() => document.body.innerText || '');
  }
  if (!text || !text.trim()) return { fail: failLine(displayId, checkName, `${address} rendered no passage text`) };
  return { text };
}

async function checkPreset(page, origin, work, displayId) {
  const url = `${origin}${work.facts.route ?? ''}`;
  try {
    await gotoAndSettle(page, url);
  } catch (err) {
    return failLine(displayId, 'preset-marked', `${url}: ${err.message}`);
  }
  const preset = await page.evaluate(() => document.body.getAttribute('data-preset'));
  const expected = work.merged.preset || work.defaultPreset;
  if (!expected) return null; // nothing to assert against
  if (preset !== expected) {
    return failLine(displayId, 'preset-marked', `body[data-preset]='${preset}', expected '${expected}'`);
  }
  return null;
}

/** Runs the three fixture passages. Returns {status: 'skip'|'fail'|'pass',
 *  reason?, fail?, note?} -- 'skip' when the work has no fixture entry (does
 *  not fail the run; the caller keeps checking other things). */
async function checkFixturePassages(page, origin, displayId, fixtureEntry) {
  if (!fixtureEntry) return { status: 'skip', reason: 'no fixture' };
  for (const passage of fixtureEntry.passages) {
    const { path, fragment } = splitAddress(passage.address);
    let res;
    try {
      res = await gotoAndSettle(page, `${origin}${path}`);
    } catch (err) {
      return { status: 'fail', fail: failLine(displayId, 'fixture-passages', `${path}: ${err.message}`) };
    }
    if (!res || !res.ok()) {
      return { status: 'fail', fail: failLine(displayId, 'fixture-passages', `${path} -> ${res ? res.status() : 'no response'}`) };
    }
    const text = fragment ? await findColumnText(page, fragment, passage.language) : await page.evaluate(() => document.body.innerText || '');
    if (text == null) {
      return { status: 'fail', fail: failLine(displayId, 'fixture-passages', `no element with id (case-insensitive) '${fragment}'`) };
    }
    if (!startsWithOpening(text, passage.opening)) {
      return {
        status: 'fail',
        fail: failLine(displayId, 'fixture-passages',
          `${passage.position} passage at ${passage.address} did not start with the expected opening words`),
      };
    }
  }
  return { status: 'pass', note: fixtureEntry.reviewed_by === null ? 'fixture unreviewed' : undefined };
}

async function checkNoForeignRequests(context, origin, path, displayId, originHost, dataOriginHost) {
  const urls = [];
  const page = await context.newPage();
  page.on('request', (req) => urls.push(req.url()));
  try {
    // Sol review, finding 7: `waitUntil: 'load'` (inside gotoAndSettle) fires
    // once the page's own load event settles -- any redirect chain is
    // already followed by then, so it IS the final forwarded page -- but a
    // request the page's own script issues just after load (a lazy fetch, a
    // deferred asset) fired after the old code closed the page and dropped
    // the listener, so it was never seen. A bounded network-idle wait keeps
    // the listener attached long enough to catch that class of request,
    // without hanging forever on a page that polls.
    await gotoAndSettle(page, `${origin}${path}`);
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
  } catch (err) {
    await page.close();
    return failLine(displayId, 'no-foreign-requests', `${path}: ${err.message}`);
  }
  await page.close();
  const offenders = foreignRequests(urls, originHost, dataOriginHost);
  if (offenders.length > 0) {
    return failLine(displayId, 'no-foreign-requests', offenders[0]);
  }
  return null;
}

async function checkNoCredentials(context, origin, paths, displayId, token) {
  const page = await context.newPage();
  const scriptTexts = [];
  // Sol review, finding 8: each response's body read is async and was fired
  // off with no way to know when it finished -- `page.close()` could (and,
  // under load, would) run before a script's `res.text()` resolved, silently
  // dropping that script from the scan. Every handler's promise is now
  // tracked in `pending` and awaited before the page closes.
  const pending = [];
  page.on('response', (res) => {
    const type = res.request().resourceType();
    if (type !== 'script') return;
    pending.push((async () => {
      try {
        const url = res.url();
        if (new URL(url).origin !== origin) return; // same-origin scripts only
        scriptTexts.push(await res.text());
      } catch { /* ignore unreadable responses */ }
    })());
  });
  // Finding 8 also: only the LAST page's HTML was scanned (`page.content()`
  // called once, after the loop, over whichever path the loop visited last)
  // -- the landing page's HTML, visited first, was never scanned at all.
  // Each path's HTML is now captured right after its own navigation.
  const htmls = [];
  for (const path of paths) {
    try {
      await gotoAndSettle(page, `${origin}${path}`);
    } catch (err) {
      await Promise.allSettled(pending);
      await page.close();
      return failLine(displayId, 'no-credentials', `${path}: ${err.message}`);
    }
    htmls.push(await page.content());
  }
  await Promise.allSettled(pending);
  await page.close();
  const hits = new Set([
    ...htmls.flatMap((html) => scanForCredentials(html, token)),
    ...scriptTexts.flatMap((t) => scanForCredentials(t, token)),
  ]);
  if (hits.size > 0) return failLine(displayId, 'no-credentials', [...hits].join(', '));
  return null;
}

/**
 * Returns {status: 'skip'|'fail'|'pass', reason?, fail?}. Sol review,
 * finding 9: `.inst-ref` anchors only render inside an EXPANDED result
 * group (shared/components/Search.svelte only auto-expands a group with a
 * single instance) -- the old check merely asked "does any inst-ref href
 * mention the work's URL segment", which a completely unrelated hit in the
 * same work would also satisfy, and which a collapsed group's un-rendered
 * hit would never reach either way. This expands every collapsed group
 * first, then requires an inst-ref whose href actually names the expected
 * passage (instRefMatchesAddress), not merely the work.
 */
async function checkSearch(page, origin, displayId, fixtureEntry) {
  if (!fixtureEntry) return { status: 'skip', reason: 'no fixture' };
  const first = fixtureEntry.passages.find((p) => p.position === 'first') ?? fixtureEntry.passages[0];
  const inputSelector = first.language === 'en' ? '#eng-input' : '#grk-input';
  try {
    await gotoAndSettle(page, `${origin}/search`);
    await page.fill(inputSelector, searchPhraseFor(first), { timeout: NAV_TIMEOUT_MS });
    await page.click('.search-btn', { timeout: NAV_TIMEOUT_MS });
    await page.waitForSelector('.chapter-group, .search-note', { timeout: 10000 }).catch(() => {});
    // Expand every collapsed result group so its instances (and their
    // .inst-ref anchors) actually render. Bounded iteration count as a
    // safety net against an unexpected infinite render loop.
    for (let i = 0; i < 500; i += 1) {
      const opened = await page.evaluate(() => {
        const btn = document.querySelector('.group-head[aria-expanded="false"]');
        if (!btn) return false;
        btn.click();
        return true;
      });
      if (!opened) break;
      await page.waitForTimeout(20);
    }
  } catch (err) {
    return { status: 'fail', fail: failLine(displayId, 'search-finds', `${err.message}`) };
  }
  const hrefs = await page.evaluate(() => [...document.querySelectorAll('a.inst-ref')].map((a) => a.getAttribute('href') || ''));
  const hasResult = hrefs.some((href) => instRefMatchesAddress(href, first.address));
  if (!hasResult) return { status: 'fail', fail: failLine(displayId, 'search-finds', `no result link found for ${first.address}`) };
  return { status: 'pass' };
}

// ── Negative checks ─────────────────────────────────────────────────────

/**
 * Picks the catalog work `negative:inactive-no-landing` checks, pure.
 * Without `drafts`, any non-active work. With `drafts` (the build under
 * test was built with PUBLIC_LYCEUM_DRAFTS=1, so draft works ARE served --
 * their landing pages return 200, not 404), a draft work would fail the
 * check for the wrong reason, so drafts are skipped in favour of a work
 * whose state is neither 'active' nor 'draft'. Returns [lyceumKey, work] or
 * null when no eligible work exists.
 */
export function selectInactiveWork(mergedWorks, drafts) {
  for (const [lyceumKey, work] of mergedWorks) {
    if (work.state === 'active') continue;
    if (drafts && work.state === 'draft') continue;
    return [lyceumKey, work];
  }
  return null;
}

async function negativeInactiveNoLanding(origin, mergedWorks, lyceumKeyToShortId, drafts) {
  const inactive = selectInactiveWork(mergedWorks, drafts);
  if (!inactive) {
    return skipLine('negative:inactive-no-landing', drafts
      ? 'build includes drafts and every non-active work is a draft'
      : 'every catalog work is active');
  }
  const [lyceumKey, work] = inactive;
  const route = work.facts.route;
  if (!route) return skipLine('negative:inactive-no-landing', `work '${lyceumKey}' has no route to check`);
  const res = await fetchWithTimeout(`${origin}${route}`).catch((err) => ({ ok: false, status: `error: ${err.message}` }));
  if (res.status === 404) return passLine('negative:inactive-no-landing');
  return failLine('negative:inactive-no-landing', 'landing page', `${origin}${route} -> ${res.status}, expected 404`);
}

/** Which of the built-and-manifest-fetched entries negative:unknown-
 *  translation-reported should check, pure: every one whose merged catalog
 *  record names a default_translation, cross-referenced against the
 *  manifest's own translations list. Separated from the async wrapper below
 *  so the "empty input set" rule (finding 10) is unit-testable without a
 *  fetch. */
export function unknownTranslationProblems(entries, mergedWorks, manifestFetchByShortId) {
  const problems = [];
  for (const { lyceumKey, shortId } of entries) {
    const merged = mergedWorks.get(lyceumKey);
    if (!merged?.defaultTranslation) continue;
    const manifestJson = manifestFetchByShortId.get(shortId);
    if (!manifestJson) continue;
    const ids = (manifestJson.translations ?? []).map((t) => t.id);
    if (!ids.includes(merged.defaultTranslation)) {
      problems.push(`${shortId}: default_translation '${merged.defaultTranslation}' not in manifest translations [${ids.join(', ')}]`);
    }
  }
  return problems;
}

/**
 * Sol review, finding 10: this used to take only the works that reached the
 * very end of the per-work loop (every one of the 11 checks either passed
 * or skipped) -- a run where every active work FAILs an earlier check (e.g.
 * catalog-entry) fed this an empty list and printed a bare PASS, having
 * checked nothing. `checkedEntries` is now every active work whose manifest
 * was actually fetched (main() below populates it right after the
 * manifest-fetch/-hash/-schema checks succeed, before catalog-entry can
 * fail it out of the old list) -- and an empty set prints SKIP, never a
 * silent PASS.
 */
export async function negativeUnknownTranslation(checkedEntries, mergedWorks, manifestFetchByShortId) {
  if (checkedEntries.length === 0) {
    return skipLine('negative:unknown-translation-reported', 'no active work had its manifest fetched to check');
  }
  const problems = unknownTranslationProblems(checkedEntries, mergedWorks, manifestFetchByShortId);
  if (problems.length > 0) return failLine('negative:unknown-translation-reported', problems.join('; '));
  return passLine('negative:unknown-translation-reported');
}

/**
 * Grok review finding A, tightened by a follow-up Grok review of commit
 * 43e8323: whether it is safe to run the stale-revision half of
 * negative:publish-rejects, decided from the served catalog.snapshot.json
 * response's own `x-catalog-source` header. This used to be a denylist --
 * proceed for anything except an explicit 'fixture-fallback' -- but the
 * only value that positively confirms the served body came from a stored
 * catalog is 'kv'. The route now sends this header on EVERY response, not
 * just a degraded one (catalog-runtime.ts's `catalogSourceHeader`, called
 * from app/src/pages/catalog.snapshot.json.ts's GET): 'kv' for a genuinely
 * stored catalog, 'fixture-fallback' for a degraded read (stored value
 * malformed, or the KV read itself errored), 'fixture' for the ordinary
 * case of nothing published yet. A denylist would proceed on a header
 * value this route never actually sends, on the strength of it merely not
 * being the one string checked for. This is now an allowlist: only 'kv'
 * proceeds. Every other value SKIPs -- the conservative direction, since
 * the one thing this probe must never do is write to the site under test
 * (POSTing a decremented copy of a first-publish fixture body risks
 * `handlePublish`/`decideRevision` treating it as a first publish and
 * WRITING it, not rejecting it with 409). The absent-header branch below is
 * now purely defensive (the route always sends the header) -- kept so an
 * older or misbehaving deployment still SKIPs rather than guesses. Returns
 * a skip reason, or null to proceed.
 */
export function staleProbeSkipReason(catalogSourceHeader) {
  if (!catalogSourceHeader) {
    return 'x-catalog-source absent; cannot tell a stored catalog from the fixture, so the stale-revision probe is skipped';
  }
  if (catalogSourceHeader === 'fixture-fallback' || catalogSourceHeader === 'fixture') {
    return 'catalog store empty or unreadable; stale-revision probe would publish';
  }
  if (catalogSourceHeader !== 'kv') {
    return `x-catalog-source=${catalogSourceHeader} is not the stored-catalog value`;
  }
  return null;
}

/**
 * Sol review, finding 11: the malformed-body case accepted 400 OR 422, but
 * app/src/lib/catalog-runtime.ts's handlePublish (see its JSON.parse catch)
 * always returns 422 for invalid JSON -- 400 was never a real code this
 * endpoint sends, just a guess. There was also no stale/conflicting-revision
 * case at all, though handlePublish's decideRevision (§11.5) is the whole
 * point of the endpoint. With no LYCEUM_PUBLISH_TOKEN, the authenticated
 * cases (malformed body, stale revision) cannot be exercised and are
 * reported as SKIP rather than silently passing; the unauthenticated 401
 * cases still run either way.
 */
async function negativePublishRejects(origin, token) {
  const bodyUrl = `${origin}/api/catalog/publish`;
  // Content-Type: application/json is required on every one of these POSTs:
  // Astro's own cross-site-POST guard 403s a request lacking it (or lacking
  // an Origin header) before the route handler -- and so before the token
  // check -- ever runs. Confirmed by hand: the identical POST with no
  // content-type header gets 403 "Cross-site POST form submissions are
  // forbidden"; with the header, 401 "unauthorized". See docs/acceptance-script.md.
  const jsonHeaders = (extra) => ({ 'content-type': 'application/json', ...extra });
  const noToken = await fetchWithTimeout(bodyUrl, { method: 'POST', headers: jsonHeaders(), body: '{}' });
  if (noToken.status !== 401) {
    return failLine('negative:publish-rejects', 'no token', `expected 401, got ${noToken.status}`);
  }
  const wrongToken = await fetchWithTimeout(bodyUrl, {
    method: 'POST',
    headers: jsonHeaders({ authorization: 'Bearer wrong-token-value' }),
    body: '{}',
  });
  if (wrongToken.status !== 401) {
    return failLine('negative:publish-rejects', 'wrong token', `expected 401, got ${wrongToken.status}`);
  }
  if (!token) {
    return skipLine('negative:publish-rejects',
      'no token: unauthenticated cases (401) passed; malformed-body and stale-revision cases need LYCEUM_PUBLISH_TOKEN');
  }
  const malformed = await fetchWithTimeout(bodyUrl, {
    method: 'POST',
    headers: jsonHeaders({ authorization: `Bearer ${token}` }),
    body: 'not json',
  });
  if (malformed.status !== 422) {
    return failLine('negative:publish-rejects', 'malformed body with right token', `expected 422, got ${malformed.status}`);
  }
  // Stale revision: replay the currently served catalog with its revision
  // decremented by one. decideRevision (catalog-runtime.ts) rejects any
  // incoming revision lower than the stored one with 409, regardless of
  // digest -- so no separate digest tampering is needed to trigger it.
  // Grok review finding A: this used to build and POST that decremented
  // body unconditionally -- on a fresh origin (KV store empty, nothing
  // published yet) the served catalog is the bundled fixture, and POSTing
  // it back publishes it for real (handlePublish treats an empty store as a
  // first publish, not a conflict), so the probe FAILed "expected 409, got
  // 200" having just written to the site under test. staleProbeSkipReason
  // reads the response's own x-catalog-source header (see its doc comment
  // for why "absent" must be treated the same as an explicit
  // fixture-fallback) and SKIPs rather than risk that write.
  const served = await fetchWithTimeout(`${origin}/catalog.snapshot.json`);
  const skipReason = staleProbeSkipReason(served.headers.get('x-catalog-source'));
  if (skipReason) {
    return skipLine('negative:publish-rejects', `malformed-body case passed; ${skipReason}`);
  }
  let staleBody;
  try {
    const catalog = JSON.parse(await served.text());
    if (typeof catalog.revision === 'number' && catalog.revision > 1) {
      staleBody = JSON.stringify({ ...catalog, revision: catalog.revision - 1 });
    }
  } catch { /* served catalog unreadable -- fall through to SKIP below */ }
  if (!staleBody) {
    return skipLine('negative:publish-rejects',
      'malformed-body case passed; served catalog.snapshot.json has no revision > 1 to make stale');
  }
  const stale = await fetchWithTimeout(bodyUrl, {
    method: 'POST',
    headers: jsonHeaders({ authorization: `Bearer ${token}` }),
    body: staleBody,
  });
  if (stale.status !== 409) {
    return failLine('negative:publish-rejects', 'stale revision with right token', `expected 409, got ${stale.status}`);
  }
  return passLine('negative:publish-rejects');
}

/**
 * Sol review, finding 12: this used to accept ANY nonblank text from the
 * whole `#col-<fragment>` anchor -- which also wraps the chapter head and
 * translation-picker chrome -- as proof the passage rendered, and never
 * checked the navigation's own response status at all (a 404/500 error
 * page with nonblank body text would have passed). Fixed the same way as
 * fixture-passages: require a successful final response, and read the same
 * language-column subtree via findColumnText rather than the whole anchor.
 */
async function negativeReadingWithoutEndpoint(browser, origin, address, language) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.route('**/api/*', (route) => route.abort());
  await page.route('**/catalog.snapshot.json', (route) => route.abort());
  const { path, fragment } = splitAddress(address);
  let text = null;
  try {
    const res = await gotoAndSettle(page, `${origin}${path}`);
    if (!res || !res.ok()) {
      await context.close();
      return failLine('negative:reading-without-endpoint', 'navigation', `${path} -> ${res ? res.status() : 'no response'}`);
    }
    text = fragment ? await findColumnText(page, fragment, language) : await page.evaluate(() => document.body.innerText || '');
  } catch (err) {
    await context.close();
    return failLine('negative:reading-without-endpoint', 'navigation', err.message);
  }
  await context.close();
  if (!text || !text.trim()) {
    return failLine('negative:reading-without-endpoint', 'passage text', `${address} rendered no text with /api/* and catalog.snapshot.json blocked`);
  }
  return passLine('negative:reading-without-endpoint');
}

/**
 * Grok review finding C: an abort or network error thrown inside a negative
 * check (e.g. a fetch racing past FETCH_TIMEOUT_MS) escaped `main`'s own
 * try/finally undhandled, so no result lines or summary ever printed --
 * silent exit rather than a readable failure. Mirrors the per-work
 * try/catch shape already in the loop below (`failLine(item.displayId,
 * 'unexpected-error', ...)`): every negative check's own errors become one
 * FAIL line instead of aborting the run.
 */
async function guardNegativeCheck(name, fn) {
  try {
    return await fn();
  } catch (err) {
    return failLine(name, 'unexpected-error', err instanceof Error ? err.message : String(err));
  }
}

// ── Main ────────────────────────────────────────────────────────────────

export async function main(argv = process.argv.slice(2)) {
  let args;
  try {
    args = parseArgs(argv);
  } catch (err) {
    console.error(err.message);
    console.error(HELP);
    process.exitCode = 2;
    return;
  }
  if (args.help) {
    console.log(HELP);
    return;
  }
  if (!args.origin || !args.dataOrigin) {
    console.error('acceptance: --origin and --data-origin are required.');
    console.error(HELP);
    process.exitCode = 2;
    return;
  }
  const origin = args.origin.replace(/\/$/, '');
  const dataOrigin = args.dataOrigin.replace(/\/$/, '');
  const originHost = new URL(origin).host;
  const dataOriginHost = new URL(dataOrigin).host;
  const token = process.env.LYCEUM_PUBLISH_TOKEN;

  const fixture = loadFixture(args.fixture);
  let liveJson; let seedJson;
  try {
    liveJson = JSON.parse(readFileSync(args.liveCatalog, 'utf8'));
  } catch (err) {
    console.error(`acceptance: could not read live catalog ${args.liveCatalog}: ${err.message}`);
    process.exitCode = 2;
    return;
  }
  try {
    seedJson = JSON.parse(readFileSync(args.seedCatalog, 'utf8'));
  } catch (err) {
    console.error(`acceptance: could not read editorial seed ${args.seedCatalog}: ${err.message}`);
    process.exitCode = 2;
    return;
  }
  const { works: mergedWorks, allWorks, collections, defaultPreset } = mergeCatalog(liveJson, seedJson, { includeDrafts: args.drafts });

  let index; let indexUrl;
  try {
    ({ json: index, indexUrl } = await fetchManifestIndex(dataOrigin));
  } catch (err) {
    console.error(`acceptance: ${err.message}`);
    process.exitCode = 2;
    return;
  }
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(index);

  const selection = selectWorkIds({
    explicitWorks: args.works, mergedWorks, allWorks, lyceumKeyToShortId, shortIdToEntry,
  });

  ensureBrowsersPath();
  const { chromium } = resolvePlaywright();
  let browser;
  try {
    browser = await chromium.launch();
  } catch {
    browser = await chromium.launch({ channel: 'chrome' });
  }

  const lines = [];
  // Sol review, finding 14: one work throwing an error the per-work checks
  // didn't anticipate used to abort the whole run, and `browser.close()`
  // sat after that code rather than in a `finally`, so the crash also
  // leaked the browser process. Everything from here on is wrapped so a
  // single work's unexpected error becomes one FAIL line, and the browser
  // always closes.
  try {
    const context = await browser.newContext();
    const page = await context.newPage();

    // Sol review, finding 10: negative:unknown-translation-reported used to
    // take only works that reached the very end of the loop below (every
    // check passed or skipped) -- so a run where every active work FAILs an
    // earlier check checked nothing and still printed PASS. This list is
    // every active work whose manifest was actually fetched, populated
    // right after the manifest checks succeed (see inside the loop).
    const activeManifestWorks = [];
    const manifestFetchByShortId = new Map();

    // Each work collapses its 11 checks into ONE output line: the first FAIL
    // stops the sequence and names itself; a SKIP (a check that could not run,
    // e.g. no fixture entry) does not stop the run but is remembered as the
    // work's outcome unless a later check fails outright; otherwise PASS.
    for (const item of selection) {
      if (item.skip) {
        lines.push(skipLine(item.displayId, item.skip));
        continue;
      }
      const { displayId, lyceumKey, shortId, manifestEntry } = item;
      try {
        const merged = mergedWorks.get(lyceumKey) ?? {
          description: '', collectionIds: [], defaultTranslation: '', preset: '', state: 'draft', facts: {},
        };
        let skipReason;
        let note;

        // 1-3: manifest-fetch, manifest-hash, manifest-schema.
        const manifestResult = await checkManifest(manifestEntry, indexUrl, displayId);
        if (manifestResult.fail) { lines.push(manifestResult.fail); continue; }
        const { manifestJson } = manifestResult;
        manifestFetchByShortId.set(shortId, manifestJson);
        if (merged.state === 'active') activeManifestWorks.push({ lyceumKey, shortId });

        // 4: catalog-entry.
        const catalogFail = await checkCatalogEntry(origin, lyceumKey, index.corpus_version, displayId);
        if (catalogFail) { lines.push(catalogFail); continue; }

        // 5: landing-renders.
        const work = { facts: manifestJson, merged, collections, defaultPreset };
        const landingFail = await checkLanding(page, origin, work, displayId);
        if (landingFail) { lines.push(landingFail); continue; }

        // 6: reading-renders (first reading address from navigation.default_locus).
        const nav = manifestJson.navigation ?? {};
        const firstAddress = nav.loci?.[nav.default_locus];
        if (!firstAddress) { lines.push(failLine(displayId, 'reading-renders', 'manifest has no navigation.default_locus/loci')); continue; }
        const readingResult = await checkReading(page, origin, firstAddress, displayId, 'reading-renders');
        if (readingResult.fail) { lines.push(readingResult.fail); continue; }

        // 7: fixture-passages.
        const fixtureEntry = fixture.works[shortId];
        const fixtureResult = await checkFixturePassages(page, origin, displayId, fixtureEntry);
        if (fixtureResult.status === 'fail') { lines.push(fixtureResult.fail); continue; }
        if (fixtureResult.status === 'skip') skipReason = fixtureResult.reason;
        else if (fixtureResult.note) note = fixtureResult.note;

        // 8: no-foreign-requests (on the reading page).
        const { path: readingPath } = splitAddress(firstAddress);
        const foreignFail = await checkNoForeignRequests(context, origin, readingPath, displayId, originHost, dataOriginHost);
        if (foreignFail) { lines.push(foreignFail); continue; }

        // 9: no-credentials (landing + reading pages).
        const landingPath = manifestJson.route ?? '';
        const credFail = await checkNoCredentials(context, origin, [landingPath, readingPath], displayId, token);
        if (credFail) { lines.push(credFail); continue; }

        // 10: preset-marked.
        const presetFail = await checkPreset(page, origin, work, displayId);
        if (presetFail) { lines.push(presetFail); continue; }

        // 11: search-finds.
        const searchResult = await checkSearch(page, origin, displayId, fixtureEntry);
        if (searchResult.status === 'fail') { lines.push(searchResult.fail); continue; }
        if (searchResult.status === 'skip' && !skipReason) skipReason = searchResult.reason;

        if (skipReason) lines.push(skipLine(displayId, skipReason));
        else lines.push(passLine(displayId, note));
      } catch (err) {
        lines.push(failLine(item.displayId, 'unexpected-error', err instanceof Error ? err.message : String(err)));
      }
    }

    // Negative checks. Each is wrapped so its own unexpected error becomes
    // one FAIL line (finding C) rather than aborting the run before the
    // summary prints.
    // allWorks, not the filtered mergedWorks: selectInactiveWork needs to see
    // a work's real state to pick a non-active one, and mergeCatalog's own
    // keep rule (item 1 above) now drops non-active/non-kept-draft works
    // from mergedWorks entirely.
    lines.push(await guardNegativeCheck('negative:inactive-no-landing',
      () => negativeInactiveNoLanding(origin, allWorks, lyceumKeyToShortId, args.drafts)));
    lines.push(await guardNegativeCheck('negative:unknown-translation-reported',
      () => negativeUnknownTranslation(activeManifestWorks, mergedWorks, manifestFetchByShortId)));
    lines.push(await guardNegativeCheck('negative:publish-rejects',
      () => negativePublishRejects(origin, token)));
    lines.push(await guardNegativeCheck('negative:reading-without-endpoint', async () => {
      const anyAddress = selection.find((s) => !s.skip);
      if (!anyAddress) return skipLine('negative:reading-without-endpoint', 'no built work available to check');
      const entry = manifestFetchByShortId.get(anyAddress.shortId);
      const nav = entry?.navigation ?? {};
      const address = nav.loci?.[nav.default_locus];
      if (!address) return skipLine('negative:reading-without-endpoint', 'no built work with a reading address to check');
      // The original-language column, not English -- see findColumnText:
      // any value other than 'en' selects the [data-column] subtree,
      // which is language-agnostic (Greek or Latin both carry it).
      return negativeReadingWithoutEndpoint(browser, origin, address, 'grc');
    }));
  } finally {
    await browser.close();
  }

  for (const line of lines) console.log(line);
  const { pass, fail, skip, exitCode } = summarize(lines);
  console.log(`\n${pass} passed, ${fail} failed, ${skip} skipped`);
  process.exitCode = exitCode;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}
