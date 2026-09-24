// End-to-end tests for POST /api/catalog/publish's decision logic
// (src/lib/catalog-runtime.ts's handlePublish), against a fake KV and a fake
// cache instead of a Workers runtime -- see publish.ts, which just wires the
// real bindings into the same function. Covers Grok's review findings on the
// probe's Worker routes (docs/lyceum-shared-repo-plan.md §11.5): the 8 MiB
// body cap enforced on actual bytes read (not trusted Content-Length), cache
// invalidation after a successful write AND an idempotent replay (never
// failing the request when the purge itself fails), KV read-error vs.
// -absent classification (malformed stored data is never silently
// overwritten; a KV error is a 503, not a 500 or a silent fixture fallback),
// and that the publish path never consults the bundled fixture for the
// stored revision.
import { beforeEach, describe, expect, it } from 'vitest';
import { handlePublish, type CacheLike, type KVLike } from '../lib/catalog-runtime';

const MAX_BODY_BYTES = 8 * 1024 * 1024;
const SECRET = 'test-publish-token';

function validCatalog(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schema_version: '2.0',
    library_id: 'lyceum-library',
    revision: 1,
    generated_at: '2026-09-15T00:00:00Z',
    presentation: { presets: {}, content: {}, visibility: {} },
    collections: [],
    works: [],
    integrity: { algorithm: 'sha256', digest: 'digest-a' },
    ...overrides,
  };
}

function request(body: string | Uint8Array, headers: Record<string, string> = {}): Request {
  return new Request('http://example.test/api/catalog/publish', {
    method: 'POST',
    headers: { authorization: `Bearer ${SECRET}`, ...headers },
    body: body as BodyInit,
  });
}

/** Records get()/put() calls (and their order) so tests can assert on write
 *  order and on "no put happened". `getBehavior` lets a test make get()
 *  return a stored value, resolve absent, or throw. */
class FakeKV implements KVLike {
  calls: string[] = [];
  putBodies = new Map<string, string>();
  getBehavior: { value?: unknown; throws?: Error } = { value: null };

  async get(_key: string, _type: 'json'): Promise<unknown> {
    this.calls.push('get');
    if (this.getBehavior.throws) throw this.getBehavior.throws;
    return this.getBehavior.value ?? null;
  }

  async put(key: string, value: string): Promise<void> {
    this.calls.push(`put:${key}`);
    this.putBodies.set(key, value);
  }
}

class FakeCache implements CacheLike {
  invocations: { tags?: string[] }[] = [];
  shouldThrow = false;

  async invalidate(options: { tags?: string[] }): Promise<void> {
    this.invocations.push(options);
    if (this.shouldThrow) throw new Error('purge failed');
  }
}

let kv: FakeKV;
let cache: FakeCache;

beforeEach(() => {
  kv = new FakeKV();
  cache = new FakeCache();
});

function deps() {
  return { kv, secret: SECRET, cache };
}

describe('handlePublish -- auth', () => {
  it('rejects a missing/wrong bearer token with 401 before reading the body', async () => {
    const res = await handlePublish(
      new Request('http://example.test/x', { method: 'POST', body: JSON.stringify(validCatalog()) }),
      deps(),
    );
    expect(res.status).toBe(401);
    expect(kv.calls).toEqual([]);
  });
});

describe('handlePublish -- body cap', () => {
  it('rejects a body over 8 MiB by actual bytes read, even with a lying (small) Content-Length', async () => {
    const oversized = new Uint8Array(MAX_BODY_BYTES + 1024).fill(97); // 'a'
    const res = await handlePublish(request(oversized, { 'content-length': '10' }), deps());
    expect(res.status).toBe(413);
    const body = (await res.json()) as Record<string, unknown>;
    expect(body).toEqual({ ok: false, error: 'body too large' });
    expect(kv.calls).toEqual([]);
  });

  // The early Content-Length fast path (decision 1's "keep it as a fast
  // path") isn't separately testable here: "Content-Length" is a forbidden
  // header name under the Fetch spec, and happy-dom (this suite's test
  // environment) enforces that -- a Request built with a spoofed
  // content-length header simply doesn't carry it, so there's no way to
  // construct "a Content-Length that lies large" distinctly from "an
  // actually-large body" in this environment. The byte-counted read is the
  // real enforcement and is what actually reaches production (workerd sets
  // Content-Length itself, from the real body, not from JS-settable
  // headers); the test above already exercises it end to end.
});

describe('handlePublish -- JSON and field validation', () => {
  it('rejects invalid JSON with 422', async () => {
    const res = await handlePublish(request('not json'), deps());
    expect(res.status).toBe(422);
  });

  it('rejects a missing revision with 422', async () => {
    const body = validCatalog();
    delete body.revision;
    const res = await handlePublish(request(JSON.stringify(body)), deps());
    expect(res.status).toBe(422);
  });

  it('rejects a non-integer revision with 422', async () => {
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1.5 }))), deps());
    expect(res.status).toBe(422);
  });
});

describe('handlePublish -- digest and binding', () => {
  it('rejects a missing integrity.digest with 422', async () => {
    const res = await handlePublish(request(JSON.stringify(validCatalog({ integrity: {} }))), deps());
    expect(res.status).toBe(422);
    expect(await res.json()).toMatchObject({ ok: false });
  });
  it('rejects an empty integrity.digest with 422', async () => {
    const res = await handlePublish(request(JSON.stringify(validCatalog({ integrity: { digest: '' } }))), deps());
    expect(res.status).toBe(422);
  });
  it('answers 503 when the KV binding is missing, and never falls back to the fixture', async () => {
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1 }))), { ...deps(), kv: undefined });
    expect(res.status).toBe(503);
    expect(await res.json()).toMatchObject({ ok: false });
  });
});

describe('handlePublish -- write order and revision rule', () => {
  it('writes the revisions key before the current key', async () => {
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1 }))), deps());
    expect(res.status).toBe(200);
    expect(kv.calls).toEqual(['get', 'put:catalog/revisions/digest-a.json', 'put:catalog/current.json']);
  });

  it('is idempotent (200, no write) on a same-revision same-digest replay, and still invalidates', async () => {
    kv.getBehavior = { value: { revision: 5, integrity: { digest: 'same-digest' } } };
    const res = await handlePublish(
      request(JSON.stringify(validCatalog({ revision: 5, integrity: { algorithm: 'sha256', digest: 'same-digest' } }))),
      deps(),
    );
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(200);
    expect(kv.calls).toEqual(['get']); // no put
    expect(cache.invocations).toEqual([{ tags: ['catalog'] }]);
    expect(body.cache_purged).toBe(true);
  });

  it('rejects same revision, different digest, with 409', async () => {
    kv.getBehavior = { value: { revision: 5, integrity: { digest: 'aaa' } } };
    const res = await handlePublish(
      request(JSON.stringify(validCatalog({ revision: 5, integrity: { algorithm: 'sha256', digest: 'bbb' } }))),
      deps(),
    );
    expect(res.status).toBe(409);
    expect(kv.calls).toEqual(['get']);
  });

  it('rejects a lower revision with 409', async () => {
    kv.getBehavior = { value: { revision: 5, integrity: { digest: 'aaa' } } };
    const res = await handlePublish(
      request(JSON.stringify(validCatalog({ revision: 4, integrity: { algorithm: 'sha256', digest: 'zzz' } }))),
      deps(),
    );
    expect(res.status).toBe(409);
    expect(kv.calls).toEqual(['get']);
  });

  it('accepts a higher revision: 200, write, cache_purged true', async () => {
    kv.getBehavior = { value: { revision: 5, integrity: { digest: 'aaa' } } };
    const res = await handlePublish(
      request(JSON.stringify(validCatalog({ revision: 6, integrity: { algorithm: 'sha256', digest: 'ccc' } }))),
      deps(),
    );
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(200);
    expect(kv.calls).toEqual(['get', 'put:catalog/revisions/ccc.json', 'put:catalog/current.json']);
    expect(body.cache_purged).toBe(true);
  });

  it('reports cache_purged: false when invalidate throws, but the KV write still persisted', async () => {
    cache.shouldThrow = true;
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1 }))), deps());
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(200);
    expect(body.cache_purged).toBe(false);
    // the write itself is unaffected by the purge failure
    expect(kv.putBodies.has('catalog/current.json')).toBe(true);
  });
});

describe('handlePublish -- KV read classification', () => {
  it('rejects a malformed stored catalog with 409 and never overwrites it', async () => {
    kv.getBehavior = { value: { not: 'a valid stored catalog' } };
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1 }))), deps());
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(409);
    expect(body).toEqual({ ok: false, error: 'stored catalog unreadable; repair catalog/current.json' });
    expect(kv.calls).toEqual(['get']); // no put
  });

  it('returns 503 when the KV read itself throws, and never writes', async () => {
    kv.getBehavior = { throws: new Error('KV unavailable') };
    const res = await handlePublish(request(JSON.stringify(validCatalog({ revision: 1 }))), deps());
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(503);
    expect(body).toEqual({ ok: false, error: 'catalog store unavailable' });
    expect(kv.calls).toEqual(['get']); // no put
  });

  it('never consults the bundled fixture for the stored revision: empty KV + incoming revision 11 is a first publish', async () => {
    // The bundled fixture (fixtures/catalog.snapshot.v2.live-2026-09-08.json)
    // is revision 11. If the publish path ever fell back to it when KV is
    // empty, an incoming revision 11 would collide (409) instead of being
    // treated as the very first publish. KV here is empty (getBehavior
    // defaults to `value: null` -> 'absent').
    const res = await handlePublish(
      request(JSON.stringify(validCatalog({ revision: 11, integrity: { algorithm: 'sha256', digest: 'any-digest' } }))),
      deps(),
    );
    const body = (await res.json()) as Record<string, unknown>;
    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(kv.calls).toEqual(['get', 'put:catalog/revisions/any-digest.json', 'put:catalog/current.json']);
  });
});

describe('handlePublish -- bearer parsing', () => {
  it('accepts case/space variants of the Bearer scheme', async () => {
    const body = JSON.stringify(validCatalog({ revision: 1 }));
    for (const header of ['bearer test-publish-token', 'BEARER test-publish-token', 'Bearer  test-publish-token']) {
      kv = new FakeKV();
      cache = new FakeCache();
      const res = await handlePublish(request(body, { authorization: header }), deps());
      expect(res.status).toBe(200);
    }
  });

  it('fails closed with an empty-string configured secret', async () => {
    const res = await handlePublish(
      new Request('http://example.test/x', {
        method: 'POST',
        headers: { authorization: 'Bearer anything' },
        body: JSON.stringify(validCatalog()),
      }),
      { kv, secret: '', cache },
    );
    expect(res.status).toBe(401);
    expect(kv.calls).toEqual([]);
  });
});
