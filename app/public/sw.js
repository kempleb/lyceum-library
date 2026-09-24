// Service worker: offline reading, cache-as-you-read.
//
// The corpus is far too large to precache wholesale (~hundreds of MB), so the
// contract is honest and simple: anything you have read is available offline.
//
//  - Navigations (page HTML): network-first so deploys show up immediately,
//    falling back to the cached copy offline, then to the offline page.
//  - Hashed build assets (/_astro/): cache-first — content-addressed names
//    make them immutable, and a deploy's new HTML references new names.
//  - Corpus data (the data root — same-origin /data/ or an off-origin bucket,
//    see DATA_ROOT below) and other same-scope files: network-first, cache
//    fallback. Fresh HTML must never pair with a prior deploy's cached JSON
//    (schema drift), so data is only served from cache when actually offline
//    — where it pairs with equally-old cached HTML, which is consistent.
//  - Fonts: self-hosted, hashed under /_astro/ (John's ruling, 2026-09-23:
//    no Google font loads) — covered by the cache-first branch below, same
//    as any other hashed build asset. No separate cross-origin font branch.
//
// Versioned cache: bump VERSION to invalidate everything after a breaking
// deploy. In particular, bump it whenever the corpus-data or search-index
// SCHEMA changes: navigations/JS are network-first (a deploy's new HTML/JS
// arrive immediately online), but same-URL /data/ JSON is only refreshed
// online, so without a version bump an offline reader could pair fresh JS
// with a stale cached index. Old caches are dropped on activate.
//
// CACHE_PREFIX namespaces our caches so activate only ever deletes caches
// this app owns — Cache Storage is per-ORIGIN, and a shared hosting origin
// can carry other sites' caches too, which must not be collateral damage.
const CACHE_PREFIX = 'classical-reader-';
const VERSION = CACHE_PREFIX + 'v1';
const SCOPE_PATH = new URL(self.registration.scope).pathname; // e.g. / (root)
const OFFLINE_URL = SCOPE_PATH + 'offline.html';

// The corpus data root can live on ANOTHER ORIGIN — a Cloudflare R2 bucket,
// see docs/cloudflare-setup.md §3. This file is static, copied verbatim out of
// public/ into dist, so it cannot read import.meta.env the way
// shared/lib/data.ts does; app/scripts/postbuild-sw.mjs substitutes the build's
// PUBLIC_DATA_ROOT into the literal below (John's ruling, 2026-08-14: template
// at build time rather than postMessage from the page — an idle worker is
// killed and restarted on the next fetch, so it must already know the origin
// before any client could tell it). Empty = same-origin data under SCOPE_PATH,
// which the scope branch in the fetch handler already covers.
const DATA_ROOT = '';
const DATA_BASE = DATA_ROOT ? new URL(DATA_ROOT, location.href).href.replace(/\/+$/, '') : '';
const isDataRequest = (url) => DATA_BASE !== ''
  && (url.href === DATA_BASE || url.href.startsWith(DATA_BASE + '/'));

// event.waitUntil() throws InvalidStateError synchronously if the browser has
// already decided the fetch event is finished. The write itself (already
// kicked off by `write`) still runs regardless -- this only stops that throw
// from displacing the response the caller is about to return.
function keepAlive(event, write) {
  try {
    event.waitUntil(write);
  } catch {
    // event already finished; the write still runs.
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION).then((c) => c.addAll([OFFLINE_URL])).then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== VERSION).map((k) => caches.delete(k)),
      ))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(event, { offlineFallback = false } = {}) {
  const { request } = event;
  const cache = await caches.open(VERSION);
  try {
    const fresh = await fetch(request);
    // The write is handed to waitUntil, not awaited: the reader gets the
    // response at network speed, while the event stays alive until the copy
    // has actually landed in the cache.
    if (fresh.ok) keepAlive(event, cache.put(request, fresh.clone()));
    return fresh;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (offlineFallback) return cache.match(OFFLINE_URL);
    throw err;
  }
}

async function cacheFirst(event) {
  const { request } = event;
  const cache = await caches.open(VERSION);
  const cached = await cache.match(request);
  if (cached) return cached;
  const fresh = await fetch(request);
  if (fresh.ok) keepAlive(event, cache.put(request, fresh.clone()));
  return fresh;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(event, { offlineFallback: true }));
    return;
  }

  // Corpus data, wherever the data root points: exactly the policy the
  // same-origin /data/ branch below applies — network-first, cached copy
  // offline. Never cache-first: the schema-drift argument in the header
  // comment does not care which origin the JSON came from. These cross-origin
  // responses are CORS-enabled, not opaque, so they cache and read normally.
  if (isDataRequest(url)) {
    event.respondWith(networkFirst(event));
    return;
  }

  if (url.origin === location.origin) {
    if (url.pathname.includes('/_astro/')) {
      event.respondWith(cacheFirst(event));
    } else if (url.pathname.startsWith(SCOPE_PATH)) {
      // Corpus data, favicons, manifest — always fresh online (a new deploy's
      // HTML must never read an old deploy's JSON), cached copy offline.
      event.respondWith(networkFirst(event));
    }
    return;
  }
});
