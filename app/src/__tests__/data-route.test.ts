// GET/HEAD /data/<version>/<path> serves the reader's corpus data out of an
// R2 bucket bound to the Worker (docs/cloudflare-setup.md's bucket-mode
// section). All the decision logic lives in lib/data-route.ts's handleData,
// exercised here against a fake R2 bucket instead of a Workers runtime --
// see pages/data/[...path].ts, which just wires the real CORPUS binding
// into the same function (nothing about the version is baked into the
// Worker; it comes from the request path).
import { describe, expect, it, vi } from 'vitest';
import {
  decodeAndValidate,
  handleData,
  isValidVersion,
  VERSION_SEGMENT_RE,
  type R2Like,
  type R2ObjectLike,
} from '../lib/data-route';

function streamOf(text: string): { stream: ReadableStream; cancel: ReturnType<typeof vi.fn> } {
  const cancel = vi.fn(async () => {});
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
    // The Streams Standard invokes this underlying-source callback exactly
    // once per `stream.cancel()` call, and never on ordinary read-to-completion
    // -- exactly the distinction finding E asks the tests to prove.
    cancel,
  });
  return { stream, cancel };
}

async function readAll(stream: ReadableStream | null): Promise<string> {
  if (!stream) return '';
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (value) chunks.push(value);
  }
  const total = chunks.reduce((n, c) => n + c.byteLength, 0);
  const combined = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    combined.set(c, offset);
    offset += c.byteLength;
  }
  return new TextDecoder().decode(combined);
}

/** Records every get() call (the key requested) so tests can assert on
 *  exactly what key was requested. httpEtag is quoted, as real R2 objects'
 *  is -- see data-route.ts's If-None-Match comment for why comparison
 *  happens against this quoted form rather than via R2's `onlyIf`.
 *
 *  get() THROWS if ever passed a second (`onlyIf`) argument: R2's onlyIf
 *  expects an unquoted etag and throws on the quoted form this route uses,
 *  so a regression that starts passing onlyIf again must fail this suite,
 *  not silently pass it (finding E). */
class FakeBucket implements R2Like {
  objects = new Map<string, { httpEtag: string; body: string }>();
  calls: string[] = [];
  private lastCancel = new Map<string, ReturnType<typeof vi.fn>>();

  set(key: string, body: string, httpEtag = `"etag-${key}"`): void {
    this.objects.set(key, { httpEtag, body });
  }

  async get(key: string, options?: unknown): Promise<R2ObjectLike | null> {
    if (options !== undefined) {
      throw new Error(`FakeBucket.get() received an onlyIf/options argument (${JSON.stringify(options)}) -- handleData must never pass one (R2's onlyIf throws on a quoted etag)`);
    }
    this.calls.push(key);
    const stored = this.objects.get(key);
    if (!stored) return null;
    // A fresh, single-use stream per get() -- matching R2's real body
    // semantics -- so each call gets its own cancel() spy to assert on.
    const { stream, cancel } = streamOf(stored.body);
    this.lastCancel.set(key, cancel);
    return { httpEtag: stored.httpEtag, body: stream };
  }

  /** The cancel() spy for the stream handed back by the most recent get() of `key`. */
  cancelSpyFor(key: string): ReturnType<typeof vi.fn> {
    const cancel = this.lastCancel.get(key);
    if (!cancel) throw new Error(`no get(${JSON.stringify(key)}) recorded yet`);
    return cancel;
  }
}

function req(path: string, init: RequestInit = {}): Request {
  return new Request(`https://reader.example${path}`, init);
}

const V = '2026.09.21-6151ee0';

describe('handleData -- happy path', () => {
  it('200s with body, content-type, etag, and an immutable cache-control', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/plato-republic/analyses.json`, '{"ok":true}');

    const res = await handleData(req(`/data/${V}/plato-republic/analyses.json`), { bucket });

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('application/json; charset=utf-8');
    expect(res.headers.get('etag')).toBe(`"etag-releases/${V}/plato-republic/analyses.json"`);
    expect(res.headers.get('cache-control')).toBe('public, max-age=31536000, immutable');
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
    expect(await readAll(res.body)).toBe('{"ok":true}');
  });

  it('serves a non-.json file with a sensible content-type (e.g. .md)', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/reports/validation_report.md`, '# report');

    const res = await handleData(req(`/data/${V}/reports/validation_report.md`), { bucket });

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('text/markdown; charset=utf-8');
  });

  it('falls back to application/octet-stream for an unrecognized extension', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/foo.bin`, 'raw');

    const res = await handleData(req(`/data/${V}/foo.bin`), { bucket });

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('application/octet-stream');
  });

  it('404s when the object is absent', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/missing.json`), { bucket });
    expect(res.status).toBe(404);
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
  });
});

describe('handleData -- key construction (version travels in the URL, not baked in)', () => {
  it('builds the key as "releases/<version>/<path>"', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/plato-republic/book-1.json`, '{}');
    await handleData(req(`/data/${V}/plato-republic/book-1.json`), { bucket });
    expect(bucket.calls).toEqual([`releases/${V}/plato-republic/book-1.json`]);
  });

  it('a different version in the URL requests a different key', async () => {
    const bucket = new FakeBucket();
    bucket.set('releases/other-version/x.json', '{}');
    const res = await handleData(req('/data/other-version/x.json'), { bucket });
    expect(res.status).toBe(200);
    expect(bucket.calls).toEqual(['releases/other-version/x.json']);
  });
});

describe('handleData -- method handling', () => {
  it('405s with an Allow header for a non-GET/HEAD method', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/a.json`, { method: 'POST' }), { bucket });
    expect(res.status).toBe(405);
    expect(res.headers.get('Allow')).toBe('GET, HEAD');
    expect(bucket.calls).toEqual([]); // never reached the bucket
  });
});

describe('handleData -- missing bucket', () => {
  it('503s when no bucket is configured, without ever validating the path further', async () => {
    const res = await handleData(req(`/data/${V}/a.json`), { bucket: undefined });
    expect(res.status).toBe(503);
  });
});

describe('handleData -- version segment', () => {
  it('400s for a version with a disallowed character (space, once decoded)', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req('/data/bad%20version/x.json'), { bucket });
    expect(res.status).toBe(400);
    expect(bucket.calls).toEqual([]); // never reached the bucket
  });

  it('400s for a version starting with a dash', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req('/data/-bad/x.json'), { bucket });
    expect(res.status).toBe(400);
    expect(bucket.calls).toEqual([]);
  });

  it('400s when there is a version but no path after it', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}`), { bucket });
    expect(res.status).toBe(400);
  });

  it('400s when there is a version, a trailing slash, but an empty path', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/`), { bucket });
    expect(res.status).toBe(400);
  });

  it('404s (not 400) for a well-formed but unknown version -- the object simply is not there', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req('/data/9999.01.01-unknown/plato-republic/book-1.json'), { bucket });
    expect(res.status).toBe(404);
    expect(bucket.calls).toEqual(['releases/9999.01.01-unknown/plato-republic/book-1.json']);
  });
});

describe('handleData -- If-None-Match (RFC 7232 §3.2)', () => {
  it('304s on a single quoted matching tag', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
    expect(res.headers.get('etag')).toBe('"same-etag"');
    expect(res.headers.get('cache-control')).toBe('public, max-age=31536000, immutable');
    expect(await readAll(res.body)).toBe('');
  });

  it('304s when the tag appears inside a list', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"a", "same-etag", "b"' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
  });

  it('304s on a weak validator matching the (stripped) stored etag', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': 'W/"same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
  });

  it('304s on a bare "*"', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '*' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
  });

  it('200s on a non-matching tag', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"current"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"stale"' } }),
      { bucket },
    );
    expect(res.status).toBe(200);
    expect(await readAll(res.body)).toBe('{"x":1}');
  });

  it('200s on a malformed header (treated as no match, not an error)', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"current"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': 'not-quoted-and-, ,weird' } }),
      { bucket },
    );
    expect(res.status).toBe(200);
  });

  it('304s on a tag whose quoted content itself contains a comma', async () => {
    // header.split(',') (the code this replaces) would have split this into
    // two pieces and never matched -- the comma belongs to the quoted tag,
    // not to the list syntax.
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"a,b"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"a,b"' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
  });

  it('200s on a malformed header with a leading comma, even when a real tag inside it matches', async () => {
    // header.split(',') would have produced an empty piece and '"same-etag"'
    // and matched on the second -- the old bug this guards against.
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': ', "same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(200);
  });

  it('200s on junk between two otherwise-valid tags', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"a" junk "same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(200);
  });

  it('200s on a lowercase "w/" prefix (only uppercase "W/" is a valid weak prefix)', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': 'w/"same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(200);
  });

  it('never delegates to R2 onlyIf (FakeBucket.get throws if ever passed one)', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/a.json`, '{"x":1}', '"same-etag"');
    // If handleData regressed to passing { onlyIf: ... } as a second get()
    // argument, FakeBucket.get would throw and this call would reject.
    await expect(
      handleData(req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"same-etag"' } }), { bucket }),
    ).resolves.toBeInstanceOf(Response);
  });
});

describe('handleData -- R2 body stream lifecycle (finding E)', () => {
  const KEY = `releases/${V}/a.json`;

  it('HEAD cancels the body stream exactly once', async () => {
    const bucket = new FakeBucket();
    bucket.set(KEY, '{"x":1}');
    const res = await handleData(req(`/data/${V}/a.json`, { method: 'HEAD' }), { bucket });
    expect(res.status).toBe(200);
    expect(await readAll(res.body)).toBe('');
    expect(bucket.cancelSpyFor(KEY)).toHaveBeenCalledTimes(1);
  });

  it('a 304 cancels the body stream exactly once', async () => {
    const bucket = new FakeBucket();
    bucket.set(KEY, '{"x":1}', '"same-etag"');
    const res = await handleData(
      req(`/data/${V}/a.json`, { headers: { 'if-none-match': '"same-etag"' } }),
      { bucket },
    );
    expect(res.status).toBe(304);
    expect(bucket.cancelSpyFor(KEY)).toHaveBeenCalledTimes(1);
  });

  it('a GET 200 never cancels the body stream', async () => {
    const bucket = new FakeBucket();
    bucket.set(KEY, '{"x":1}');
    const res = await handleData(req(`/data/${V}/a.json`), { bucket });
    expect(res.status).toBe(200);
    await readAll(res.body);
    expect(bucket.cancelSpyFor(KEY)).not.toHaveBeenCalled();
  });
});

// A literal or once-percent-encoded "." / ".." segment can never reach
// handleData through a real Request: WHATWG URL path parsing already
// collapses both forms (case-insensitively, including "%2e") before
// `new URL(request.url)` returns a pathname -- proven by the handleData
// tests below (a request built with "/foo/../bar.json" or "/foo/%2e%2e/"
// simply never has that segment in its pathname). decodeAndValidate's own
// "." / ".." rule is tested directly instead, as the defense-in-depth
// the brief asks for.
describe('decodeAndValidate -- dot segments (unreachable via a real Request; see comment)', () => {
  it('rejects a ".." segment', () => {
    expect(decodeAndValidate('foo/../bar.json')).toEqual({ ok: false, reason: 'dot segment' });
  });

  it('rejects a "." segment', () => {
    expect(decodeAndValidate('foo/./bar.json')).toEqual({ ok: false, reason: 'dot segment' });
  });

  it('rejects a bare ".."', () => {
    expect(decodeAndValidate('..')).toEqual({ ok: false, reason: 'dot segment' });
  });
});

describe('handleData -- URL parsing already strips literal/single-encoded dot segments', () => {
  it('normalizes "/data/<version>/foo/../bar.json" before handleData ever sees a dot segment', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/bar.json`, '{}');
    const res = await handleData(req(`/data/${V}/foo/../bar.json`), { bucket });
    expect(res.status).toBe(200); // reached "bar.json", not rejected as unsafe
    expect(bucket.calls).toEqual([`releases/${V}/bar.json`]);
  });

  it('normalizes "/data/<version>/foo/%2e%2e/bar.json" (single-encoded) the same way', async () => {
    const bucket = new FakeBucket();
    bucket.set(`releases/${V}/bar.json`, '{}');
    const res = await handleData(req(`/data/${V}/foo/%2e%2e/bar.json`), { bucket });
    expect(res.status).toBe(200);
    expect(bucket.calls).toEqual([`releases/${V}/bar.json`]);
  });
});

describe('handleData -- path safety', () => {
  it('rejects a backslash', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/foo%5Cbar.json`), { bucket });
    expect(res.status).toBe(400);
  });

  it('rejects a leading slash after the version (double slash in the URL)', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}//etc/passwd`), { bucket });
    expect(res.status).toBe(400);
  });

  it('rejects a control character', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/foo%01bar.json`), { bucket });
    expect(res.status).toBe(400);
  });

  it('rejects a NUL byte', async () => {
    const bucket = new FakeBucket();
    const res = await handleData(req(`/data/${V}/foo%00bar.json`), { bucket });
    expect(res.status).toBe(400);
  });

  it('rejects a path over 512 characters', async () => {
    const bucket = new FakeBucket();
    const longPath = 'a/'.repeat(300) + 'x.json';
    expect(longPath.length).toBeGreaterThan(512);
    const res = await handleData(req(`/data/${V}/${longPath}`), { bucket });
    expect(res.status).toBe(400);
  });

  it('decodes a percent-encoded path exactly once: a double-encoded ".." never becomes "..", and is not treated as an existing key either', async () => {
    const bucket = new FakeBucket();
    // %252e%252e decodes ONCE to the literal string "%2e%2e" -- not ".."
    // (which would need a SECOND decode). That literal is a valid single
    // path segment, so this must reach the bucket with that exact key
    // rather than being rejected as a dot-segment.
    bucket.set(`releases/${V}/%2e%2e/x.json`, '{}');
    const res = await handleData(req(`/data/${V}/%252e%252e/x.json`), { bucket });
    expect(res.status).toBe(200);
    expect(bucket.calls).toEqual([`releases/${V}/%2e%2e/x.json`]);
  });
});

// --- VERSION_SEGMENT_RE ----------------------------------------------------
// Pins this copy of the rule to the same accept/reject set as
// scripts/lib/data-source-mode.mjs's VERSION_SEGMENT_RE (that file's own
// test runs the identical two arrays below) -- the two can't share one
// import (this is TypeScript, that's a plain `node` script), so this is how
// the pair is kept from drifting apart.

const VALID_VERSIONS = [
  '2026.09.21-6151ee0', // build-public.mjs's real from-scratch shape: <sha>-<date>
  '6151ee0-2026-09-21',
  'dev', // pipeline's os.environ.get("CORPUS_VERSION", "dev") fallback
  '0',
  'a',
  'A9',
  'abc_def.1-2',
  'a' + 'b'.repeat(63), // exactly 64 chars: the maximum the rule allows
];

const INVALID_VERSIONS = [
  '',
  '.',
  '..',
  '-abc', // leading char must be alphanumeric
  '.abc',
  'a/b', // no path separators
  'a b', // no whitespace
  'a%2e', // no percent-encoding
  'a\\b', // no backslash
  'ünïcode', // ASCII only
  'a' + 'b'.repeat(64), // 65 chars: one past the maximum
];

describe('VERSION_SEGMENT_RE / isValidVersion', () => {
  it('accepts every valid example', () => {
    for (const v of VALID_VERSIONS) {
      expect(VERSION_SEGMENT_RE.test(v), `expected ${JSON.stringify(v)} to be valid`).toBe(true);
      expect(isValidVersion(v), `expected ${JSON.stringify(v)} to be valid`).toBe(true);
    }
  });

  it('rejects every invalid example', () => {
    for (const v of INVALID_VERSIONS) {
      expect(VERSION_SEGMENT_RE.test(v), `expected ${JSON.stringify(v)} to be invalid`).toBe(false);
      expect(isValidVersion(v), `expected ${JSON.stringify(v)} to be invalid`).toBe(false);
    }
  });
});
