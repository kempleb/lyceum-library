// POST /api/catalog/publish (docs/lyceum-shared-repo-plan.md §11.5). Bearer
// token against env.LYCEUM_PUBLISH_TOKEN; body capped at 8 MiB (counted off
// the actual byte stream, never trusted from Content-Length); structural
// validation via the same validateLive path parseCatalog runs (reused, never
// duplicated -- see shared/lib/lyceum-catalog-source.ts); cross-references
// (collection_ids, preset, default_translation) via
// src/lib/catalog-runtime.ts's crossReferenceErrors; then the revision rule.
//
// All of the actual decision logic lives in catalog-runtime.ts's
// handlePublish, which takes KV/secret/cache as injected `deps` instead of
// reading `cloudflare:workers`'s `env` itself -- that's what lets it run
// under Vitest against fakes (app/src/__tests__/catalog-publish-route.test.ts)
// exactly as it runs under workerd. This file only wires the real bindings
// and Astro's request-scoped `cache` into that function.
//
// integrity.digest is NOT recomputed here -- Brian's canonicalisation
// document (exactly which bytes get hashed) is not yet in hand. TODO once
// that document exists: recompute sha256 over the canonical serialization
// and reject a mismatch as 422, rather than trusting the plugin's own digest.
export const prerender = false;

import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { handlePublish, type KVLike } from '../../../lib/catalog-runtime';

export const POST: APIRoute = async ({ request, cache }) => {
  const bindings = env as unknown as { LIBRARY_CATALOG?: KVLike; LYCEUM_PUBLISH_TOKEN?: string };
  return handlePublish(request, {
    kv: bindings.LIBRARY_CATALOG,
    secret: bindings.LYCEUM_PUBLISH_TOKEN,
    cache,
  });
};
