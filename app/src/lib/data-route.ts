// Serves the reader's corpus data (GET/HEAD /data/<version>/<path>) straight
// out of an R2 bucket bound to the Worker, at the same origin -- no client
// change needed beyond a build-time PUBLIC_DATA_ROOT of `/data/<version>`
// (scripts/build-public.mjs), since shared/lib/data.ts and shared/lib/search.ts
// already build every fetch URL as a plain string join off that root. See
// docs/cloudflare-setup.md's bucket-mode section.
//
// Same pattern as src/lib/catalog-runtime.ts: handleData is PURE (no
// `cloudflare:workers`, no R2 binding of its own) so it runs under Vitest
// against a fake bucket exactly as it runs under workerd -- the route
// (pages/data/[...path].ts) is a thin wrapper that wires the real CORPUS
// binding into it.
//
// The release version travels in the URL, not baked into the Worker: object
// key = `releases/<version>/<path>`, where `<version>` is the request's own
// first path segment (validated against VERSION_SEGMENT_RE below) and
// `<path>` is everything after it, decoded exactly once. Because the URL
// carries the version, and a version's contents in the bucket never change
// once published, every 200 ships an immutable Cache-Control -- see below.

// Minimal shape of the R2 binding this file needs -- avoids adding
// @cloudflare/workers-types as a project dependency for a handful of
// methods (mirrors KVLike in catalog-runtime.ts). `get` never receives a
// second (`onlyIf`) argument from this module -- R2's onlyIf expects an
// UNQUOTED etag and throws on the quoted form this route works with
// (see etagMatches below) -- but the signature allows one so a test double
// can assert that a caller regression never re-introduces it.
export interface R2ObjectLike {
  httpEtag: string;
  body: ReadableStream;
}

export interface R2Like {
  get(key: string, options?: unknown): Promise<R2ObjectLike | null>;
}

export interface DataRouteDeps {
  bucket?: R2Like;
}

const MAX_PATH_LENGTH = 512;
// eslint-disable-next-line no-control-regex -- deliberately matching C0/DEL.
const CONTROL_CHARS = /[\x00-\x1f\x7f]/;

// A release-version path segment: build-public.mjs's CORPUS_VERSION, whose
// two real shapes are `<short-sha>-<date>` (a from-scratch build) and
// whatever a --from-dist release's RELEASE.json carries (including the
// pipeline's own "dev" fallback). Deliberately excludes '.' and '..' without
// a separate rule: both fail on their own, since neither starts with an
// alphanumeric character. Kept byte-for-byte identical to
// scripts/lib/data-source-mode.mjs's copy (a plain `node` script can't
// import this .ts file directly) -- scripts/__tests__/data-source-mode.test.mjs
// and this file's own test pin both copies to the same accept/reject set.
export const VERSION_SEGMENT_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

export function isValidVersion(version: string): boolean {
  return VERSION_SEGMENT_RE.test(version);
}

function contentTypeFor(path: string): string {
  if (path.endsWith('.json')) return 'application/json; charset=utf-8';
  // The one non-JSON file under build/dist today (reports/validation_report.md,
  // a pipeline report, not reader-referenced) -- handled rather than ignored,
  // per the brief's "check for any other extension" instruction.
  if (path.endsWith('.md')) return 'text/markdown; charset=utf-8';
  return 'application/octet-stream';
}

function plainText(status: number, message: string, extraHeaders: Record<string, string> = {}): Response {
  return new Response(message, {
    status,
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'x-content-type-options': 'nosniff',
      ...extraHeaders,
    },
  });
}

/**
 * Decodes the raw path segment (everything after `/data/<version>/`, still
 * exactly as it arrived in the URL -- percent-encoding untouched) exactly
 * once and validates it. A double-encoded input (`%252e%252e`) decodes here
 * to a single-encoded literal (`%2e%2e`), never to `..` (which would need a
 * SECOND decode) -- decodeURIComponent runs once, here, and nowhere else in
 * this module.
 *
 * Rejects: an empty path, any `.` or `..` segment, a backslash, a leading
 * slash, a control character (C0 or DEL) or NUL, and a length over 512
 * (checked both before and after decoding). Non-ASCII is otherwise allowed:
 * every file name actually under build/dist is plain ASCII today (checked
 * with `find build/dist -type f | LC_ALL=C grep -c '[^ -~]'` -> 0), so
 * there's nothing in the real corpus this would need to reject, and no
 * reason to add a rule the data doesn't exercise.
 */
// Exported for its own direct tests: a literal (or once-percent-encoded)
// "." / ".." segment can never actually reach this function through a real
// Request -- the WHATWG URL Standard's path parser already collapses both
// forms (case-insensitively, including "%2e") before `new URL(request.url)`
// ever returns a pathname, so `handleData` itself can't be used to exercise
// those two rules. They stay here as explicit defense-in-depth (the brief's
// rule, and cheap insurance against some other caller's URL implementation
// not normalizing the same way) and are tested directly instead.
export function decodeAndValidate(rawPath: string): { ok: true; path: string } | { ok: false; reason: string } {
  if (rawPath.length === 0) return { ok: false, reason: 'empty path' };
  if (rawPath.length > MAX_PATH_LENGTH) return { ok: false, reason: 'path too long' };

  let decoded: string;
  try {
    decoded = decodeURIComponent(rawPath);
  } catch {
    return { ok: false, reason: 'malformed percent-encoding' };
  }

  if (decoded.length === 0) return { ok: false, reason: 'empty path' };
  if (decoded.length > MAX_PATH_LENGTH) return { ok: false, reason: 'path too long' };
  if (decoded.startsWith('/')) return { ok: false, reason: 'leading slash' };
  if (decoded.includes('\\')) return { ok: false, reason: 'backslash' };
  if (CONTROL_CHARS.test(decoded)) return { ok: false, reason: 'control character' };

  for (const segment of decoded.split('/')) {
    if (segment === '') return { ok: false, reason: 'empty path segment' };
    if (segment === '.' || segment === '..') return { ok: false, reason: 'dot segment' };
  }

  return { ok: true, path: decoded };
}

// Strips an RFC 7232 weak-validator prefix so a weak and a strong tag with
// the same opaque part compare equal, same as the spec's weak comparison.
function stripWeakPrefix(tag: string): string {
  return tag.startsWith('W/') ? tag.slice(2) : tag;
}

// An RFC 7232 §3.2 entity-tag: an optional weak-validator prefix (exactly
// `W/`, uppercase -- a lowercase `w/` is not a valid prefix and so is never
// stripped, making the whole tag fail to parse) followed by a quoted opaque
// string. Matched at an exact position (see parseEntityTagList) rather than
// globally, so a scan never skips over stray characters between tags.
const ENTITY_TAG_AT = /^(?:W\/)?"[^"]*"/;

/**
 * Parses an If-None-Match header's list form (the `*` case is handled by the
 * caller) into its entity-tags, or returns null if the header is malformed.
 * `header.split(',')` -- the code this replaces -- breaks a tag that
 * contains a comma inside its quotes, and lets a malformed list (a stray
 * leading comma, junk between tags, ...) match by accident; this instead
 * walks the header left to right, requiring exactly one entity-tag, then
 * (only between tags) a single comma, with optional surrounding whitespace
 * everywhere else. Any deviation -- nothing where a tag was expected, junk
 * where a comma was expected, a trailing comma with nothing after it, an
 * empty or all-whitespace header -- returns null.
 */
function parseEntityTagList(header: string): string[] | null {
  const tags: string[] = [];
  let pos = 0;
  const len = header.length;
  const skipSpace = () => {
    while (pos < len && /\s/.test(header[pos])) pos += 1;
  };

  skipSpace();
  if (pos === len) return null; // empty (or all-whitespace) list

  for (;;) {
    const match = ENTITY_TAG_AT.exec(header.slice(pos));
    if (!match) return null; // no entity-tag where one was expected
    tags.push(match[0]);
    pos += match[0].length;
    skipSpace();
    if (pos === len) return tags; // clean end right after a tag
    if (header[pos] !== ',') return null; // junk between tags
    pos += 1; // consume the separator comma
    skipSpace();
    if (pos === len) return null; // trailing comma, nothing after it
  }
}

/**
 * RFC 7232 §3.2 If-None-Match, compared against the (quoted) httpEtag R2
 * handed back -- never delegated to R2's own `onlyIf` (tried first;
 * reverted -- see the R2Like doc comment above): R2's onlyIf.etagDoesNotMatch
 * expects an UNQUOTED etag and throws when handed the quoted header value.
 *
 * `*` matches any existing object (the header alone, not inside a list --
 * the one caller-observable case that matters here). Otherwise the header
 * must be a well-formed list of entity-tags (parseEntityTagList); each is
 * compared, weak prefix stripped, to the (similarly stripped) stored etag.
 * A malformed header simply never matches -- a 200, not an error -- rather
 * than needing its own rejection branch.
 */
function etagMatches(ifNoneMatch: string | null, objectEtag: string): boolean {
  if (ifNoneMatch === null) return false;
  const header = ifNoneMatch.trim();
  if (header === '*') return true;
  const tags = parseEntityTagList(header);
  if (tags === null) return false;
  const target = stripWeakPrefix(objectEtag);
  return tags.some((tag) => stripWeakPrefix(tag) === target);
}

export async function handleData(request: Request, deps: DataRouteDeps): Promise<Response> {
  const method = request.method;
  if (method !== 'GET' && method !== 'HEAD') {
    return plainText(405, 'Method Not Allowed', { Allow: 'GET, HEAD' });
  }

  const url = new URL(request.url);
  const rawAfterData = url.pathname.replace(/^\/data\/?/, '');
  const slashIndex = rawAfterData.indexOf('/');
  if (slashIndex === -1) {
    return plainText(400, 'Bad path: missing version segment or path');
  }
  const rawVersion = rawAfterData.slice(0, slashIndex);
  const rawPath = rawAfterData.slice(slashIndex + 1);

  if (!isValidVersion(rawVersion)) {
    return plainText(400, `Bad path: invalid version segment "${rawVersion}"`);
  }

  const validated = decodeAndValidate(rawPath);
  if (!validated.ok) {
    return plainText(400, `Bad path: ${validated.reason}`);
  }

  if (!deps.bucket) {
    return plainText(503, 'Data bucket is not configured');
  }

  const key = `releases/${rawVersion}/${validated.path}`;

  const object = await deps.bucket.get(key);
  if (object === null) {
    return plainText(404, 'Not Found');
  }

  // `immutable` is safe here only under a PUBLICATION rule, not a technical
  // guarantee this route enforces itself: a release folder, once uploaded to
  // the bucket, is never overwritten (the version string alone -- commit
  // plus date -- does not guarantee unique contents; a same-day rebuild
  // could differ). That invariant belongs to scripts/publish-release.mjs --
  // see docs/cloudflare-setup.md's bucket-mode section for the rule and why
  // old releases must stay in the bucket for this header to stay honest.
  const headers: Record<string, string> = {
    'content-type': contentTypeFor(validated.path),
    etag: object.httpEtag,
    'cache-control': 'public, max-age=31536000, immutable',
    'x-content-type-options': 'nosniff',
  };

  if (etagMatches(request.headers.get('if-none-match'), object.httpEtag)) {
    await object.body.cancel().catch(() => {});
    return new Response(null, { status: 304, headers });
  }

  if (method === 'HEAD') {
    await object.body.cancel().catch(() => {});
    return new Response(null, { status: 200, headers });
  }

  return new Response(object.body, { status: 200, headers });
}
