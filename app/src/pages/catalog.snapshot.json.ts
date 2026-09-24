// GET /catalog.snapshot.json (docs/lyceum-shared-repo-plan.md §11.5): serves
// KV LIBRARY_CATALOG's catalog/current.json, falling back to the committed
// live snapshot when the binding is absent, the key is empty, the stored
// value is malformed, or the KV read itself errors -- same source and same
// fallback as library/index.astro, via src/lib/catalog-runtime.ts's
// loadLiveCatalog. Never 500s for a reader.
export const prerender = false;

import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { catalogSourceHeader, loadLiveCatalog, type KVLike, readerCacheOptions, readerCacheControl } from '../lib/catalog-runtime';

export const GET: APIRoute = async ({ cache }) => {
  const kv = (env as unknown as { LIBRARY_CATALOG?: KVLike }).LIBRARY_CATALOG;
  const { json, source, fallback } = await loadLiveCatalog(kv);

  // Astro 7 route caching (John, 2026-09-14): tag this response 'catalog' so
  // api/catalog/publish.ts can purge it by tag after a successful write.
  // routeRules already sets maxAge/swr for this route; this call is the
  // explicit per-request tag the plan's cache.invalidate({tags:['catalog']})
  // targets. In dev mode Astro.cache performs no caching -- harmless to call
  // unconditionally.
  cache.set(readerCacheOptions(fallback));

  // Every response names its source -- 'kv' for a genuinely stored catalog,
  // 'fixture-fallback' for a degraded read (stored value malformed, or the
  // KV read itself errored), 'fixture' for the ordinary case of nothing
  // published yet. Lets scripts/acceptance.mjs's publish-rejects probe (and
  // anyone else) tell those three cases apart without guessing from the body.
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    'cache-control': readerCacheControl(fallback),
    'x-catalog-source': catalogSourceHeader(source, fallback),
  };

  return new Response(JSON.stringify(json), { status: 200, headers });
};
