// The service worker follows the data root off-origin.
//
// public/sw.js is static, so the build substitutes PUBLIC_DATA_ROOT into it
// (app/scripts/postbuild-sw.mjs). These tests run that real build step over the
// real public/sw.js and then execute the emitted worker against stubbed
// caches/fetch — a worker that ignored off-origin corpus fetches, or one whose
// DATA_ROOT placeholder had drifted out of the source, would fail here rather
// than silently break offline reading (docs/cloudflare-setup.md §3a).
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SW_SOURCE = join(APP, 'public', 'sw.js');
const POSTBUILD = join(APP, 'scripts', 'postbuild-sw.mjs');
const ORIGIN = 'https://reader.example';
const R2 = 'https://pub-4ed50262412e44deb78c78b952f07f03.r2.dev';

/** Runs the real postbuild step over a dist copy of sw.js; returns the result. */
function build(dataRoot = '', source = readFileSync(SW_SOURCE, 'utf8')): string {
  const dir = mkdtempSync(join(tmpdir(), 'sw-'));
  mkdirSync(join(dir, 'dist', 'client'), { recursive: true });
  writeFileSync(join(dir, 'dist', 'client', 'sw.js'), source);
  execFileSync('node', [POSTBUILD], {
    cwd: dir,
    env: { ...process.env, PUBLIC_DATA_ROOT: dataRoot },
    stdio: 'pipe',
  });
  return readFileSync(join(dir, 'dist', 'client', 'sw.js'), 'utf8');
}

const keyOf = (req: { url: string } | string) => (typeof req === 'string' ? req : req.url);

function makeResponse(body: string, init: { ok?: boolean; type?: string } = {}) {
  const res: Record<string, unknown> = { ok: init.ok ?? true, type: init.type ?? 'cors', body };
  res.clone = () => ({ ...res, clone: res.clone });
  return res;
}

/** Let every queued microtask and timer callback run. */
const flush = () => new Promise((r) => setTimeout(r, 0));

/** Does this promise still have nothing to say once the queue has drained? */
async function pending(p: Promise<unknown>): Promise<boolean> {
  let settled = false;
  p.then(() => { settled = true; }, () => { settled = true; });
  await flush();
  return !settled;
}

/**
 * Executes a worker source with stubbed globals and returns a driver for it.
 * `scope` defaults to the whole origin (root); pass a narrower one (e.g.
 * `${ORIGIN}/app/`) to prove a request is claimed by a SPECIFIC branch of
 * the fetch handler rather than by the general same-origin/in-scope branch,
 * which would otherwise also claim anything under the default root scope.
 */
function start(
  source: string,
  scope = `${ORIGIN}/`,
  opts: { waitUntilThrows?: boolean; lazyPut?: boolean } = {},
) {
  const handlers: Record<string, (event: unknown) => void> = {};
  const store = new Map<string, unknown>();
  const net = { offline: false, calls: [] as string[] };
  // cache.put's own write (the store.set below) happens synchronously, exactly
  // as the old unconditional `async () => { store.set(...) }` did — only the
  // PROMISE it returns is left pending, so a test can control when the write
  // "settles" (as event.waitUntil sees it) without changing what a later
  // cache.match() reads. With `opts.lazyPut`, the store.set itself is also
  // deferred to `resolvePut` — needed when a test must tell apart a fresh
  // network response from a cached one that hasn't landed yet.
  const pendingPuts: { key: string; resolve: () => void }[] = [];
  let nextResponseInit: { ok?: boolean; type?: string } | undefined;

  const cache = {
    match: async (req: unknown) => store.get(keyOf(req as { url: string })),
    put: (req: unknown, res: unknown) => {
      const key = keyOf(req as { url: string });
      if (!opts.lazyPut) store.set(key, res);
      return new Promise<void>((resolve) => {
        pendingPuts.push({
          key,
          resolve: () => {
            if (opts.lazyPut) store.set(key, res);
            resolve();
          },
        });
      });
    },
    addAll: async () => {},
  };
  const caches = { open: async () => cache, keys: async () => [], delete: async () => true };
  const fetchStub = async (req: unknown) => {
    const key = keyOf(req as { url: string });
    net.calls.push(key);
    if (net.offline) throw new TypeError('offline');
    const init = nextResponseInit;
    nextResponseInit = undefined;
    return makeResponse(`fresh:${key}`, init);
  };
  const self = {
    registration: { scope },
    addEventListener: (type: string, fn: (event: unknown) => void) => { handlers[type] = fn; },
    skipWaiting: () => {},
    clients: { claim: () => {} },
  };

  // eslint-disable-next-line no-new-func
  new Function('self', 'caches', 'location', 'fetch', source)(
    self, caches, new URL(`${ORIGIN}/sw.js`), fetchStub,
  );

  return {
    net,
    /** Puts an already-settled response straight into the cache store. */
    seed(url: string, body: string) {
      store.set(url, makeResponse(body));
    },
    /** Resolves the oldest still-pending cache.put for this URL by hand. */
    resolvePut(url: string) {
      const i = pendingPuts.findIndex((p) => p.key === url);
      if (i === -1) throw new Error(`no pending cache.put for ${url}`);
      pendingPuts[i].resolve();
      pendingPuts.splice(i, 1);
    },
    async get(url: string, mode = 'cors', responseInit?: { ok?: boolean; type?: string }) {
      nextResponseInit = responseInit;
      const request = { method: 'GET', url, mode };
      let promise: Promise<unknown> | undefined;
      const waits: Promise<unknown>[] = [];
      handlers.fetch({
        request,
        respondWith: (p: Promise<unknown>) => { promise = p; },
        waitUntil: (p: Promise<unknown>) => {
          if (opts.waitUntilThrows) {
            // Real browsers throw InvalidStateError synchronously when the
            // event has already timed out -- the promise itself is never
            // seen, so it must not be pushed to `waits`.
            throw new DOMException('The event handler is finished', 'InvalidStateError');
          }
          waits.push(p);
        },
      });
      if (promise === undefined) return { handled: false, body: null, waits };
      return { handled: true, body: ((await promise) as { body: string }).body, waits };
    },
  };
}

describe('service worker with an off-origin data root', () => {
  it('caches corpus data from the data root and serves it when offline', async () => {
    const sw = start(build(R2));
    const url = `${R2}/plato-republic/analyses.json`;

    const online = await sw.get(url);
    expect(online.handled).toBe(true);
    expect(online.body).toBe(`fresh:${url}`);

    sw.net.offline = true;
    const offline = await sw.get(url);
    expect(offline.handled).toBe(true);
    expect(offline.body).toBe(`fresh:${url}`);
    // Network-first, not cache-first: the second read tried the network first
    // and only fell back to cache because it failed.
    expect(sw.net.calls).toEqual([url, url]);
  });

  it('claims only the data root, not the whole bucket origin', async () => {
    const sw = start(build(`${R2}/corpus/`));

    expect((await sw.get(`${R2}/corpus/plato-republic/book-1.json`)).handled).toBe(true);
    expect((await sw.get(`${R2}/elsewhere.json`)).handled).toBe(false);
  });
});

describe('service worker with a same-origin PATH data root (bucket mode: PUBLIC_DATA_ROOT=/data/<version>)', () => {
  // Bucket mode (docs/cloudflare-setup.md's bucket-mode section) sets
  // PUBLIC_DATA_ROOT to an absolute PATH, not a URL -- `/data/<version>`.
  // DATA_BASE's `new URL(DATA_ROOT, location.href)` construction resolves a
  // path-only root against the worker's own origin exactly the same way it
  // resolves an absolute off-origin URL, so this needs no branch of its own
  // in sw.js -- this test proves that rather than assuming it.
  const PATH_ROOT = '/data/2026.09.21-6151ee0';

  // A narrower registration scope than the default root (`/`): SCOPE_PATH
  // becomes `/app/`, which does not contain PATH_ROOT. Under the default
  // root scope, the general same-origin branch (`url.pathname.startsWith(
  // SCOPE_PATH)`) would ALSO claim a `/data/<version>/...` request on its
  // own, so asserting `handled === true` there proves nothing about
  // isDataRequest() specifically -- a worker with isDataRequest hard-coded
  // to `false` would still pass. With this narrower scope, only the
  // isDataRequest() branch can claim the request, so these tests actually
  // exercise it.
  const APP_SCOPE = `${ORIGIN}/app/`;

  it('claims a request under the versioned path root via isDataRequest(), even outside the registration scope, and caches it for offline', async () => {
    const sw = start(build(PATH_ROOT), APP_SCOPE);
    const url = `${ORIGIN}${PATH_ROOT}/plato-republic/analyses.json`;

    const online = await sw.get(url);
    expect(online.handled).toBe(true);
    expect(online.body).toBe(`fresh:${url}`);

    sw.net.offline = true;
    const offline = await sw.get(url);
    expect(offline.handled).toBe(true);
    expect(offline.body).toBe(`fresh:${url}`);
    // Network-first, not cache-first: the second read tried the network
    // first and only fell back to cache because it failed.
    expect(sw.net.calls).toEqual([url, url]);
  });

  it('does not handle a same-origin request outside both the registration scope and the data root', async () => {
    const sw = start(build(PATH_ROOT), APP_SCOPE);
    expect((await sw.get(`${ORIGIN}/elsewhere/x.json`)).handled).toBe(false);
  });
});

describe('service worker with same-origin data (no PUBLIC_DATA_ROOT)', () => {
  it('leaves the shipped worker byte-identical', () => {
    expect(build()).toBe(readFileSync(SW_SOURCE, 'utf8'));
  });

  it('keeps network-first data, cache-first assets, and ignores other origins', async () => {
    const sw = start(build());

    expect((await sw.get(`${ORIGIN}/data/plato-republic/analyses.json`)).handled).toBe(true);
    expect(sw.net.calls).toHaveLength(1);

    await sw.get(`${ORIGIN}/_astro/app.js`);
    await sw.get(`${ORIGIN}/_astro/app.js`);
    expect(sw.net.calls).toHaveLength(2); // asset fetched once, then cache-first

    expect((await sw.get('https://example.com/tracker.json')).handled).toBe(false);
  });
});

describe('cache writes are tied to the fetch event, not abandoned mid-flight', () => {
  // The browser is free to kill the worker once a response is delivered, so a
  // cache.put started but not tied to event.waitUntil() can be dropped before
  // it lands. Each case: the response resolves at network speed while a
  // waitUntil promise stays pending until the write settles.
  it('networkFirst: a navigation (page) request', async () => {
    const sw = start(build());
    const url = `${ORIGIN}/plato-republic/book-1/`;

    const result = await sw.get(url, 'navigate');
    expect(result.handled).toBe(true);
    expect(result.body).toBe(`fresh:${url}`);

    expect(result.waits).toHaveLength(1);
    expect(await pending(result.waits[0])).toBe(true);

    sw.resolvePut(url);
    expect(await pending(result.waits[0])).toBe(false);
  });

  it('networkFirst: the data-root branch (isDataRequest)', async () => {
    const sw = start(build(R2));
    const url = `${R2}/plato-republic/analyses.json`;

    const result = await sw.get(url);
    expect(result.handled).toBe(true);
    expect(result.body).toBe(`fresh:${url}`);

    expect(result.waits).toHaveLength(1);
    expect(await pending(result.waits[0])).toBe(true);

    sw.resolvePut(url);
    expect(await pending(result.waits[0])).toBe(false);
  });

  it('cacheFirst: an /_astro/ hashed asset', async () => {
    const sw = start(build());
    const url = `${ORIGIN}/_astro/app.abc123.js`;

    const result = await sw.get(url);
    expect(result.handled).toBe(true);
    expect(result.body).toBe(`fresh:${url}`);

    expect(result.waits).toHaveLength(1);
    expect(await pending(result.waits[0])).toBe(true);

    sw.resolvePut(url);
    expect(await pending(result.waits[0])).toBe(false);
  });

  // The cross-origin Google Fonts branch this test exercised is gone (John's
  // ruling, 2026-09-23: fonts are self-hosted, see shared/styles/fonts.css) --
  // sw.js no longer has any no-cors cross-origin fetch, so cacheFirst's
  // `fresh.type === 'opaque'` arm has no remaining caller in this worker (the
  // only other cacheFirst caller, the /_astro/ branch, is same-origin and
  // never opaque). Not replaced with an equivalent case: there is no longer a
  // real request path that produces an opaque response to cover.
});

describe('a timed-out event.waitUntil() never costs the reader the fresh response (Sol finding, nit)', () => {
  // The browser may have already decided the fetch event is finished (e.g. it
  // ran long) by the time the handler calls event.waitUntil() to register the
  // cache write -- that call then throws InvalidStateError synchronously.
  // Before the fix this landed uncaught (cacheFirst has no try/catch of its
  // own) or was swallowed by the existing try/catch and diverted the response
  // (networkFirst); either way the reader must still get the response that
  // was already fetched.
  it('networkFirst: a navigation still resolves to the fresh network response, not a stale cached one', async () => {
    // lazyPut so the write this fetch triggers does NOT land in the store
    // before the assertion below -- otherwise a pre-fix worker whose catch
    // branch serves `cache.match(request)` would read back the identical
    // copy `cache.put` had just written synchronously, and the test
    // couldn't tell old and new code apart. Seeding an older body makes the
    // two diverge: the fixed worker must return the fresh response, not
    // this stale one.
    const sw = start(build(), `${ORIGIN}/`, { waitUntilThrows: true, lazyPut: true });
    const url = `${ORIGIN}/plato-republic/book-1/`;
    sw.seed(url, 'stale');

    const result = await sw.get(url, 'navigate');
    expect(result.handled).toBe(true);
    expect(result.body).toBe(`fresh:${url}`);
  });

  it('cacheFirst: an /_astro/ hashed asset still resolves to the fresh network response', async () => {
    const sw = start(build(), `${ORIGIN}/`, { waitUntilThrows: true });
    const url = `${ORIGIN}/_astro/app.abc123.js`;
    const result = await sw.get(url);
    expect(result.handled).toBe(true);
    expect(result.body).toBe(`fresh:${url}`);
  });
});

describe('postbuild-sw', () => {
  it('fails the build if the DATA_ROOT placeholder drifts out of sw.js', () => {
    const drifted = readFileSync(SW_SOURCE, 'utf8').replace("const DATA_ROOT = '';", 'const DATA_ROOT = self.x;');
    expect(() => build(R2, drifted)).toThrow();
  });
});
