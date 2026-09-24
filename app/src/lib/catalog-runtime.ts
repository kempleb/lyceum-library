// The M2 probe's request-time catalog plumbing (docs/lyceum-shared-repo-plan.md
// §11.2, §11.5, §11.6): the KV read (with the committed live snapshot as
// fallback), the publish endpoint's decision logic, and the revision rule.
//
// Every function that decides something (token check, revision rule,
// cross-reference checks, the read-result classification) is PURE -- no KV,
// no Request/Response -- so it can be unit-tested without a Workers runtime.
// handlePublish is the one exception: it orchestrates KV + cache for the
// publish route, but takes both as injected `deps` (see PublishDeps) so it
// can be exercised with fakes instead of a real Workers runtime too.
import { parseCatalog } from '@shared/lib/lyceum-catalog-source';
import fixtureCatalog from '../../../fixtures/catalog.snapshot.v2.live-2026-09-08.json';
import editorialSeed from '../../../fixtures/editorial.seed.json';

// Minimal shape of the Workers KV binding this file needs -- avoids adding
// @cloudflare/workers-types as a dependency for a handful of methods.
export interface KVLike {
  get(key: string, type: 'json'): Promise<unknown>;
  put(key: string, value: string): Promise<void>;
}

/** Minimal shape of Astro's request-scoped cache object this file needs
 *  (astro/dist/core/cache/runtime/cache.js's CacheLike) -- just the one
 *  method the publish route calls after a successful write. */
export interface CacheLike {
  invalidate(options: { tags?: string[] }): Promise<void>;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function json(status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

// ── Auth ─────────────────────────────────────────────────────────────────

/** Constant-time byte comparison -- standard library only (no node:crypto,
 *  so it works identically under Vitest/Node and under workerd). Length is
 *  folded into the running diff instead of short-circuiting, so a mismatched
 *  length takes the same number of steps as a match of the longer input. */
export function constantTimeEqual(a: string, b: string): boolean {
  const aBytes = new TextEncoder().encode(a);
  const bBytes = new TextEncoder().encode(b);
  const len = Math.max(aBytes.length, bBytes.length, 1);
  let diff = aBytes.length ^ bBytes.length;
  for (let i = 0; i < len; i += 1) {
    diff |= (aBytes[i] ?? 0) ^ (bBytes[i] ?? 0);
  }
  return diff === 0;
}

/** True when `authHeader` is a `Bearer` token, scheme matched case-
 *  insensitively (`bearer`, `Bearer`, `BEARER`, ...) with any run of
 *  whitespace between the scheme and the token and optional trailing
 *  whitespace. `expectedToken` undefined OR the empty string (the secret
 *  isn't configured) always fails closed -- never treated as "no auth
 *  required". */
export function checkAuth(authHeader: string | null, expectedToken: string | undefined): boolean {
  if (!expectedToken) return false;
  if (!authHeader) return false;
  const match = /^bearer\s+(\S+)\s*$/i.exec(authHeader);
  if (!match) return false;
  return constantTimeEqual(match[1], expectedToken);
}

// ── Revision rule (§11.5) ────────────────────────────────────────────────

export interface StoredRevision {
  revision: number;
  digest: string;
}

export type RevisionDecision =
  | { action: 'write'; status: 200 }
  | { action: 'idempotent'; status: 200 }
  | { action: 'reject'; status: 409; reason: string };

/**
 * The plugin is the authority: same revision + same digest as stored is an
 * idempotent 200 (no write); same revision with a different digest is 409;
 * a lower revision is 409; a higher revision (or no stored revision at all --
 * first publish) is accepted and written. Pure: takes and returns plain data,
 * no KV.
 */
export function decideRevision(stored: StoredRevision | null, incoming: StoredRevision): RevisionDecision {
  if (!stored) return { action: 'write', status: 200 };
  if (incoming.revision < stored.revision) {
    return {
      action: 'reject',
      status: 409,
      reason: `incoming revision ${incoming.revision} is lower than the stored revision ${stored.revision}`,
    };
  }
  if (incoming.revision === stored.revision) {
    if (incoming.digest === stored.digest) return { action: 'idempotent', status: 200 };
    return {
      action: 'reject',
      status: 409,
      reason: `revision ${incoming.revision} is already stored with a different integrity.digest`,
    };
  }
  return { action: 'write', status: 200 };
}

// ── Cross-reference checks (§11.5) ──────────────────────────────────────

/**
 * Structural + cross-reference validation of an incoming publish body, over
 * and above shared/lib/lyceum-catalog-source.ts's validateLive (reused via
 * parseCatalog, never duplicated here): every work's editorial.collection_ids
 * entries name a collection that exists, editorial.preset names a
 * presentation.presets entry or is '', and editorial.default_translation
 * names one of the work's own facts.translations or is ''. Returns one
 * message per problem found; empty means the body passes.
 */
export function crossReferenceErrors(catalog: Record<string, unknown>): string[] {
  const errors: string[] = [];

  const collections = Array.isArray(catalog.collections) ? catalog.collections : [];
  const collectionIds = new Set(
    collections
      .map((c) => (isPlainObject(c) ? c.id : undefined))
      .filter((id): id is string => typeof id === 'string'),
  );

  const presentation = isPlainObject(catalog.presentation) ? catalog.presentation : {};
  const presets = isPlainObject(presentation.presets) ? presentation.presets : {};
  const presetIds = new Set(Object.keys(presets));

  const works = Array.isArray(catalog.works) ? catalog.works : [];
  for (const raw of works) {
    if (!isPlainObject(raw)) continue;
    const workId = typeof raw.id === 'string' ? raw.id : '(work with no id)';
    const editorial = isPlainObject(raw.editorial) ? raw.editorial : {};

    const collectionRefs = Array.isArray(editorial.collection_ids) ? editorial.collection_ids : [];
    for (const ref of collectionRefs) {
      if (typeof ref !== 'string' || !collectionIds.has(ref)) {
        errors.push(`work '${workId}' names unknown collection '${String(ref)}' in editorial.collection_ids`);
      }
    }

    const preset = editorial.preset;
    if (typeof preset === 'string' && preset !== '' && !presetIds.has(preset)) {
      errors.push(`work '${workId}' names unknown preset '${preset}' in editorial.preset`);
    }

    const defaultTranslation = editorial.default_translation;
    if (typeof defaultTranslation === 'string' && defaultTranslation !== '') {
      const facts = isPlainObject(raw.facts) ? raw.facts : {};
      const translations = Array.isArray(facts.translations) ? facts.translations : [];
      const translationIds = new Set(
        translations
          .map((t) => (isPlainObject(t) ? t.id : undefined))
          .filter((id): id is string => typeof id === 'string'),
      );
      if (!translationIds.has(defaultTranslation)) {
        errors.push(
          `work '${workId}' names unknown default_translation '${defaultTranslation}' (not in its own facts.translations)`,
        );
      }
    }
  }

  return errors;
}

// ── KV read/write (not pure -- exercised via fakes, see catalog-runtime.test.ts and catalog-publish-route.test.ts) ──

export const CATALOG_CURRENT_KEY = 'catalog/current.json';
export const catalogRevisionKey = (digest: string): string => `catalog/revisions/${digest}.json`;

/** The committed live snapshot (fixtures/catalog.snapshot.v2.live-2026-09-08.json,
 *  revision 11), bundled at build time -- the fallback used whenever the KV
 *  binding is absent (local `astro dev`/build with no `--kv`) or the
 *  `catalog/current.json` key is empty. */
export function fallbackCatalog(): unknown {
  return fixtureCatalog;
}

/** Our own editorial seed (fixtures/editorial.seed.json) -- the same file
 *  app/src/lib/lyceum-catalog.ts reads at build time, bundled here so the
 *  request-time route (library/index.astro) can pass it to the same
 *  parseCatalog(live, seed, opts) as the prebuilt homepage. */
export function seedCatalog(): unknown {
  return editorialSeed;
}

/** The result of reading and classifying `catalog/current.json` from KV.
 *  `absent`: no binding configured, or the key isn't set yet (nothing
 *  published). `ok`: parsed JSON is a plain object with a valid integer
 *  `revision` and a non-empty string `integrity.digest`. `malformed`: JSON
 *  parsed but doesn't match that shape -- a stored value we should not trust
 *  and must not silently overwrite. `error`: the KV read itself threw. */
export type CatalogReadResult =
  | { kind: 'absent' }
  | { kind: 'ok'; value: Record<string, unknown> & { revision: number; integrity: { digest: string } } }
  | { kind: 'malformed'; reason: string }
  | { kind: 'error'; reason: string };

/** Reads and classifies `catalog/current.json`. Never throws -- callers
 *  (readers vs. the publish route) decide how each non-`ok` case degrades. */
export async function readCatalogFromKV(kv: KVLike | undefined): Promise<CatalogReadResult> {
  if (!kv) return { kind: 'absent' };
  let stored: unknown;
  try {
    stored = await kv.get(CATALOG_CURRENT_KEY, 'json');
  } catch (err) {
    return { kind: 'error', reason: err instanceof Error ? err.message : String(err) };
  }
  if (stored === null || stored === undefined) return { kind: 'absent' };
  if (!isPlainObject(stored)) {
    return { kind: 'malformed', reason: 'stored catalog/current.json is not a JSON object' };
  }
  const integrity = isPlainObject(stored.integrity) ? stored.integrity : {};
  if (
    typeof stored.revision !== 'number'
    || !Number.isInteger(stored.revision)
    || typeof integrity.digest !== 'string'
    || !integrity.digest
  ) {
    return {
      kind: 'malformed',
      reason: 'stored catalog/current.json is missing a valid "revision" or "integrity.digest"',
    };
  }
  return { kind: 'ok', value: stored as Record<string, unknown> & { revision: number; integrity: { digest: string } } };
}

export interface LoadCatalogResult {
  json: unknown;
  source: 'kv' | 'fixture';
  /** True when the fixture was served because the stored value was
   *  malformed or the KV read errored -- as opposed to nothing having been
   *  published yet. Readers surface this as `x-catalog-source:
   *  fixture-fallback` so a degraded read is visible without ever 500ing. */
  fallback: boolean;
}

/** Reads `catalog/current.json` from KV, falling back to the committed
 *  snapshot whenever the binding is absent, the key is empty, the stored
 *  value is malformed, or the KV read itself errors -- a reader never 500s. */
export async function loadLiveCatalog(kv: KVLike | undefined): Promise<LoadCatalogResult> {
  const result = await readCatalogFromKV(kv);
  if (result.kind === 'ok') return { json: result.value, source: 'kv', fallback: false };
  return {
    json: fallbackCatalog(),
    source: 'fixture',
    fallback: result.kind === 'malformed' || result.kind === 'error',
  };
}

/** Writes the revision snapshot, then current.json -- that order, per §11.5
 *  ("Write snapshot:rev:<revision> first, then snapshot:current"). */
export async function writeCatalog(kv: KVLike, digest: string, body: string): Promise<void> {
  await kv.put(catalogRevisionKey(digest), body);
  await kv.put(CATALOG_CURRENT_KEY, body);
}

// ── Publish route (POST /api/catalog/publish, §11.5) ───────────────────

const MAX_BODY_BYTES = 8 * 1024 * 1024;

/** Reads `request`'s body up to `maxBytes`, counting bytes actually read off
 *  the stream (never trusting Content-Length, which a caller can lie about).
 *  Aborts and cancels the stream the moment the running total exceeds the
 *  cap, returning `too-large` rather than buffering the rest. */
async function readBodyCapped(
  request: Request,
  maxBytes: number,
): Promise<{ kind: 'ok'; text: string } | { kind: 'too-large' }> {
  if (!request.body) {
    const text = await request.text();
    if (new TextEncoder().encode(text).length > maxBytes) return { kind: 'too-large' };
    return { kind: 'ok', text };
  }
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value && value.byteLength > 0) {
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel().catch(() => {});
        return { kind: 'too-large' };
      }
      chunks.push(value);
    }
  }
  const combined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { kind: 'ok', text: new TextDecoder().decode(combined) };
}

export interface PublishDeps {
  kv: KVLike | undefined;
  secret: string | undefined;
  cache: CacheLike;
}

/**
 * The publish route's full decision logic, injected with `deps` instead of
 * reading `cloudflare:workers`'s `env` directly, so it can run under Vitest
 * against fakes (see catalog-publish-route.test.ts) exactly as it runs under
 * workerd. publish.ts is a thin wrapper that wires the real KV binding, the
 * real secret, and Astro's request-scoped `cache` into this.
 */
/**
 * Route-cache options for the two reader routes (/library and
 * /catalog.snapshot.json). A response built from the bundled fixture because
 * the KV store failed or held a malformed catalog must NOT be cached: a
 * 60 s fresh window plus stale-while-revalidate would pin the fixture at the
 * edge long after the store recovered. `false` opts the response out of
 * Astro's route cache (overriding the matching routeRules entry).
 */
export interface ReaderCacheRule { tags: string[]; maxAge: number; swr: number }
export const READER_CACHE_RULE: ReaderCacheRule = { tags: ['catalog'], maxAge: 60, swr: 86400 };
export function readerCacheOptions(fallback: boolean): false | ReaderCacheRule {
  return fallback ? false : READER_CACHE_RULE;
}

/** HTTP Cache-Control for the reader routes: the same fresh/stale window as
 *  the route cache, or `no-store` for a fixture-fallback response so no
 *  browser or intermediary keeps the fixture after the store recovers. */
export function readerCacheControl(fallback: boolean): string {
  return fallback ? 'no-store' : `public, max-age=${READER_CACHE_RULE.maxAge}, stale-while-revalidate=${READER_CACHE_RULE.swr}`;
}

/** The `x-catalog-source` value a reader route should send for a
 *  `loadLiveCatalog` result, on EVERY response (not just a degraded one):
 *  `kv` for a genuinely stored catalog, `fixture-fallback` for a degraded
 *  read (store held a malformed value, or the read itself errored), and
 *  `fixture` for the ordinary case of nothing published yet. Lets a caller
 *  (the acceptance script's publish-rejects probe) tell "nothing published"
 *  apart from "the store is broken" apart from "read succeeded" without
 *  guessing from the response body. */
export function catalogSourceHeader(source: LoadCatalogResult['source'], fallback: boolean): string {
  if (source === 'kv') return 'kv';
  return fallback ? 'fixture-fallback' : 'fixture';
}

export async function handlePublish(request: Request, deps: PublishDeps): Promise<Response> {
  // Auth first, and never logged: don't read/echo the header or the token.
  if (!checkAuth(request.headers.get('authorization'), deps.secret)) {
    return json(401, { ok: false, error: 'unauthorized' });
  }

  // Fast path: a Content-Length that already declares itself over the cap
  // needn't be read at all. Any other value (including a lying one) falls
  // through to the byte-counted read below, which is the real enforcement.
  const contentLength = request.headers.get('content-length');
  if (contentLength && Number(contentLength) > MAX_BODY_BYTES) {
    return json(413, { ok: false, error: 'body too large' });
  }
  const bodyResult = await readBodyCapped(request, MAX_BODY_BYTES);
  if (bodyResult.kind === 'too-large') {
    return json(413, { ok: false, error: 'body too large' });
  }
  const rawBody = bodyResult.text;

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawBody);
  } catch {
    return json(422, { ok: false, error: 'body is not valid JSON' });
  }

  // Structural validation: the same validateLive() path parseCatalog runs
  // internally, reused rather than duplicated. An empty seed is enough --
  // only the live half is under test here.
  try {
    parseCatalog(parsed, { collections: [], works: [] }, { includeDrafts: true });
  } catch (err) {
    return json(422, { ok: false, error: err instanceof Error ? err.message : String(err) });
  }

  const catalog = parsed as Record<string, unknown>;
  const crossRefErrors = crossReferenceErrors(catalog);
  if (crossRefErrors.length > 0) {
    return json(422, { ok: false, error: crossRefErrors.join('; ') });
  }

  const integrity = isPlainObject(catalog.integrity) ? catalog.integrity : {};
  const revision = catalog.revision;
  const digest = integrity.digest;
  if (
    typeof revision !== 'number'
    || !Number.isInteger(revision)
    || revision < 1
    || typeof digest !== 'string'
    || !digest
  ) {
    return json(422, { ok: false, error: 'catalog is missing a valid "revision" or "integrity.digest"' });
  }

  // The stored revision comes ONLY from KV -- never from the bundled
  // fixture. The fixture is a reader fallback for when nothing has been
  // published; the publish route must never treat "nothing in KV" as "the
  // fixture's revision 11 is stored", or a first publish at revision 11
  // would be wrongly rejected as a replay/conflict.
  const readResult = await readCatalogFromKV(deps.kv);
  if (readResult.kind === 'error') {
    return json(503, { ok: false, error: 'catalog store unavailable' });
  }
  if (readResult.kind === 'malformed') {
    return json(409, { ok: false, error: 'stored catalog unreadable; repair catalog/current.json' });
  }
  const stored: StoredRevision | null = readResult.kind === 'ok'
    ? { revision: readResult.value.revision, digest: readResult.value.integrity.digest }
    : null;

  const decision = decideRevision(stored, { revision, digest });
  if (decision.action === 'reject') {
    return json(decision.status, { ok: false, error: decision.reason });
  }
  if (decision.action === 'write') {
    if (!deps.kv) return json(503, { ok: false, error: 'LIBRARY_CATALOG KV binding is not configured' });
    await writeCatalog(deps.kv, digest, rawBody);
  }

  // Astro 7 route caching (John, 2026-09-14): purge library/index.astro's
  // and catalog.snapshot.json's cached responses now that the catalog they
  // read has changed. Runs on both `write` and `idempotent` (a retry after a
  // previously-failed purge should still get a fresh page). KV is already
  // committed by this point (on the `write` branch) -- a purge failure must
  // not fail the request, just leave stale pages until the next publish or
  // their natural swr expiry; report it via `cache_purged` instead.
  let cachePurged = false;
  try {
    await deps.cache.invalidate({ tags: ['catalog'] });
    cachePurged = true;
  } catch {
    cachePurged = false;
  }

  return json(200, { ok: true, revision, published_at: new Date().toISOString(), cache_purged: cachePurged });
}
