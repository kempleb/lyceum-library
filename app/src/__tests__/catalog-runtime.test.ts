// Unit tests for the M2 probe's pure decision functions
// (src/lib/catalog-runtime.ts) -- written before the routes that call them,
// per the brief: token check, revision rule, cross-reference checks.
import { describe, expect, it } from 'vitest';
import {
  catalogSourceHeader,
  checkAuth,
  constantTimeEqual,
  crossReferenceErrors,
  decideRevision,
  readCatalogFromKV,
  type KVLike,
  readerCacheOptions,
  READER_CACHE_RULE,
  readerCacheControl,
} from '../lib/catalog-runtime';

describe('constantTimeEqual', () => {
  it('is true for identical strings', () => {
    expect(constantTimeEqual('test-token', 'test-token')).toBe(true);
  });

  it('is false for different strings of the same length', () => {
    expect(constantTimeEqual('test-token', 'test-tokeX')).toBe(false);
  });

  it('is false for strings of different lengths', () => {
    expect(constantTimeEqual('short', 'a-much-longer-token')).toBe(false);
    expect(constantTimeEqual('a-much-longer-token', 'short')).toBe(false);
  });

  it('is false against an empty string', () => {
    expect(constantTimeEqual('', 'test-token')).toBe(false);
    expect(constantTimeEqual('test-token', '')).toBe(false);
  });
});

describe('checkAuth', () => {
  it('accepts a matching Bearer token', () => {
    expect(checkAuth('Bearer test-token', 'test-token')).toBe(true);
  });

  it('rejects a mismatched token', () => {
    expect(checkAuth('Bearer wrong-token', 'test-token')).toBe(false);
  });

  it('rejects a missing Authorization header', () => {
    expect(checkAuth(null, 'test-token')).toBe(false);
  });

  it('rejects a header with no Bearer scheme', () => {
    expect(checkAuth('test-token', 'test-token')).toBe(false);
    expect(checkAuth('Basic dGVzdA==', 'test-token')).toBe(false);
  });

  it('fails closed when no token is configured, even with a header present', () => {
    expect(checkAuth('Bearer anything', undefined)).toBe(false);
  });

  it('fails closed when the configured secret is the empty string', () => {
    expect(checkAuth('Bearer anything', '')).toBe(false);
    expect(checkAuth('Bearer ', '')).toBe(false);
  });

  it('matches the Bearer scheme case-insensitively', () => {
    expect(checkAuth('bearer test-token', 'test-token')).toBe(true);
    expect(checkAuth('BEARER test-token', 'test-token')).toBe(true);
    expect(checkAuth('BeArEr test-token', 'test-token')).toBe(true);
  });

  it('tolerates extra whitespace between scheme and token, and trailing whitespace', () => {
    expect(checkAuth('Bearer  test-token', 'test-token')).toBe(true);
    expect(checkAuth('Bearer\ttest-token', 'test-token')).toBe(true);
    expect(checkAuth('Bearer test-token ', 'test-token')).toBe(true);
  });
});

describe('decideRevision', () => {
  it('accepts a first publish when nothing is stored yet', () => {
    expect(decideRevision(null, { revision: 1, digest: 'aaa' })).toEqual({ action: 'write', status: 200 });
  });

  it('is idempotent on a replay: same revision, same digest -> 200, no write', () => {
    const stored = { revision: 11, digest: 'aaa' };
    expect(decideRevision(stored, { revision: 11, digest: 'aaa' })).toEqual({ action: 'idempotent', status: 200 });
  });

  it('rejects same revision with a different digest -> 409', () => {
    const stored = { revision: 11, digest: 'aaa' };
    const result = decideRevision(stored, { revision: 11, digest: 'bbb' });
    expect(result.status).toBe(409);
    expect(result.action).toBe('reject');
  });

  it('rejects a lower revision -> 409', () => {
    const stored = { revision: 11, digest: 'aaa' };
    const result = decideRevision(stored, { revision: 10, digest: 'zzz' });
    expect(result.status).toBe(409);
    expect(result.action).toBe('reject');
  });

  it('accepts a higher revision -> 200, write', () => {
    const stored = { revision: 11, digest: 'aaa' };
    expect(decideRevision(stored, { revision: 12, digest: 'ccc' })).toEqual({ action: 'write', status: 200 });
  });
});

describe('crossReferenceErrors', () => {
  const baseCatalog = {
    collections: [{ id: 'greek' }, { id: 'stoics' }],
    presentation: { presets: { classic: {}, dark: {} } },
    works: [] as unknown[],
  };

  it('passes a work whose editorial fields all resolve', () => {
    const catalog = {
      ...baseCatalog,
      works: [
        {
          id: 'lyceum:epictetus.enchiridion',
          facts: { translations: [{ id: 'oldfather' }, { id: 'long' }] },
          editorial: { collection_ids: ['greek', 'stoics'], preset: 'classic', default_translation: 'oldfather' },
        },
      ],
    };
    expect(crossReferenceErrors(catalog)).toEqual([]);
  });

  it('passes empty editorial preset/default_translation (unset, not a dangling reference)', () => {
    const catalog = {
      ...baseCatalog,
      works: [
        { id: 'lyceum:epictetus.enchiridion', facts: {}, editorial: { collection_ids: [], preset: '', default_translation: '' } },
      ],
    };
    expect(crossReferenceErrors(catalog)).toEqual([]);
  });

  it('reports an unknown collection_ids entry', () => {
    const catalog = {
      ...baseCatalog,
      works: [{ id: 'lyceum:x.y', facts: {}, editorial: { collection_ids: ['no-such-collection'] } }],
    };
    const errors = crossReferenceErrors(catalog);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('no-such-collection');
    expect(errors[0]).toContain('lyceum:x.y');
  });

  it('reports an unknown preset', () => {
    const catalog = {
      ...baseCatalog,
      works: [{ id: 'lyceum:x.y', facts: {}, editorial: { preset: 'no-such-preset' } }],
    };
    const errors = crossReferenceErrors(catalog);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('no-such-preset');
  });

  it('reports a default_translation not present in the work\'s own facts.translations', () => {
    const catalog = {
      ...baseCatalog,
      works: [
        {
          id: 'lyceum:x.y',
          facts: { translations: [{ id: 'oldfather' }] },
          editorial: { default_translation: 'nonexistent' },
        },
      ],
    };
    const errors = crossReferenceErrors(catalog);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toContain('nonexistent');
  });

  it('reports multiple problems across multiple works', () => {
    const catalog = {
      ...baseCatalog,
      works: [
        { id: 'lyceum:a.b', facts: {}, editorial: { collection_ids: ['ghost'] } },
        { id: 'lyceum:c.d', facts: {}, editorial: { preset: 'ghost-preset' } },
      ],
    };
    expect(crossReferenceErrors(catalog)).toHaveLength(2);
  });
});

describe('readCatalogFromKV', () => {
  function fakeKV(behavior: { value?: unknown; throws?: Error }): KVLike {
    return {
      get: async () => {
        if (behavior.throws) throw behavior.throws;
        return behavior.value;
      },
      put: async () => {},
    };
  }

  it('is absent when no KV binding is configured', async () => {
    expect(await readCatalogFromKV(undefined)).toEqual({ kind: 'absent' });
  });

  it('is absent when the key is unset (get resolves null/undefined)', async () => {
    expect(await readCatalogFromKV(fakeKV({ value: null }))).toEqual({ kind: 'absent' });
    expect(await readCatalogFromKV(fakeKV({ value: undefined }))).toEqual({ kind: 'absent' });
  });

  it('is ok for a well-formed stored catalog', async () => {
    const stored = { revision: 11, integrity: { digest: 'aaa' }, works: [] };
    expect(await readCatalogFromKV(fakeKV({ value: stored }))).toEqual({ kind: 'ok', value: stored });
  });

  it('is malformed when the stored value is not a plain object', async () => {
    const result = await readCatalogFromKV(fakeKV({ value: 'not-an-object' }));
    expect(result.kind).toBe('malformed');
  });

  it('is malformed when revision or integrity.digest is missing or the wrong type', async () => {
    expect((await readCatalogFromKV(fakeKV({ value: { integrity: { digest: 'aaa' } } }))).kind).toBe('malformed');
    expect((await readCatalogFromKV(fakeKV({ value: { revision: 11 } }))).kind).toBe('malformed');
    expect((await readCatalogFromKV(fakeKV({ value: { revision: '11', integrity: { digest: 'aaa' } } }))).kind).toBe(
      'malformed',
    );
    expect((await readCatalogFromKV(fakeKV({ value: { revision: 11, integrity: { digest: '' } } }))).kind).toBe(
      'malformed',
    );
  });

  it('is error when the KV read throws', async () => {
    const result = await readCatalogFromKV(fakeKV({ throws: new Error('KV unavailable') }));
    expect(result).toEqual({ kind: 'error', reason: 'KV unavailable' });
  });
});

describe('readerCacheOptions', () => {
  it('caches a live or fixture-by-absence response under the catalog tag', () => {
    expect(readerCacheOptions(false)).toEqual(READER_CACHE_RULE);
    expect(READER_CACHE_RULE.tags).toEqual(['catalog']);
  });
  it('opts a fixture-fallback response out of the route cache', () => {
    expect(readerCacheOptions(true)).toBe(false);
  });
});

describe('readerCacheControl', () => {
  it('advertises the route cache window for a live or absent-store response', () => {
    expect(readerCacheControl(false)).toBe('public, max-age=60, stale-while-revalidate=86400');
  });
  it('forbids storing a fixture-fallback response', () => {
    expect(readerCacheControl(true)).toBe('no-store');
  });
});

describe('catalogSourceHeader', () => {
  it('is "kv" for a genuinely stored catalog', () => {
    expect(catalogSourceHeader('kv', false)).toBe('kv');
  });
  it('is "fixture-fallback" for a degraded read (malformed value or KV error)', () => {
    expect(catalogSourceHeader('fixture', true)).toBe('fixture-fallback');
  });
  it('is "fixture" for the ordinary case of nothing published yet', () => {
    expect(catalogSourceHeader('fixture', false)).toBe('fixture');
  });
});
