// GET/HEAD /data/<version>/<path...> -- serves the reader's corpus data
// straight out of an R2 bucket bound to the Worker (env.CORPUS), for a build
// made with DATA_FROM_BUCKET=1 (docs/cloudflare-setup.md's bucket-mode
// section). No client change: that build sets PUBLIC_DATA_ROOT to
// `/data/<version>` itself, so shared/lib/data.ts and shared/lib/search.ts
// already fetch same-origin `/data/<version>/...` -- this route is what
// answers those requests once dist/client/data is pruned.
//
// Same pattern as api/catalog/publish.ts: all the decision logic lives in
// lib/data-route.ts's handleData, injected with `deps` instead of reading
// `cloudflare:workers`'s `env` directly, so it runs under Vitest against a
// fake bucket exactly as it runs under workerd. This file only wires the
// real CORPUS binding into it -- nothing is baked into the Worker at build
// time; the release version comes from the request path itself, so a
// deployed Worker can serve every release still in the bucket.
//
// `ALL` (not `GET`/`HEAD`) so a request with any other method still reaches
// handleData and gets its own 405 + Allow header, rather than Astro's
// generic 404 for an unhandled method. Astro's endpoint renderer already
// nulls the body of whatever this returns for a HEAD request, on top of
// handleData's own HEAD handling.
export const prerender = false;

import type { APIRoute } from 'astro';
import { env } from 'cloudflare:workers';
import { handleData, type R2Like } from '../../lib/data-route';

export const ALL: APIRoute = async ({ request }) => {
  const bindings = env as unknown as { CORPUS?: R2Like };
  return handleData(request, { bucket: bindings.CORPUS });
};
