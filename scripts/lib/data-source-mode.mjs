// Pure resolution of how a build serves corpus data, split out of
// build-public.mjs so it can be unit-tested without running the real
// (multi-minute, corpus-dependent) build -- same reasoning as build-stages.mjs.
//
// Two build-only env vars each answer "where does corpus data come from,"
// and a build can only mean one:
//   - PUBLIC_DATA_ROOT: the browser fetches corpus data from this root
//     instead of same-origin `/data` -- an off-origin URL (e.g. the R2
//     r2.dev domain), OR a same-origin absolute path (bucket mode below
//     sets one itself).
//   - DATA_FROM_BUCKET=1: the deployed Worker serves corpus data itself,
//     same-origin, from an R2 bucket bound to it (env.CORPUS) --
//     app/src/pages/data/[...path].ts. Resolving this mode does NOT set
//     PUBLIC_DATA_ROOT itself -- the caller (build-public.mjs) does that,
//     once CORPUS_VERSION is known, by calling the returned `dataRootFor`.
// Setting both is an error. Setting neither is the default: same-origin
// static files (dist/client/data ships as-is, nothing pruned).
//
// The route serves `/data/<version>/<path>` from R2 key
// `releases/<version>/<path>` -- the version travels in the URL, never
// baked into the Worker (docs/cloudflare-setup.md's bucket-mode section).
// VERSION_SEGMENT_RE is kept byte-for-byte identical to
// app/src/lib/data-route.ts's copy of the same rule (a plain `node` script
// can't import that .ts file directly); this file's own test and
// app/src/__tests__/data-route.test.ts pin both copies to the same
// accept/reject example set.
const VERSION_SEGMENT_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

/** @param {string} version */
function isValidVersion(version) {
  return typeof version === 'string' && VERSION_SEGMENT_RE.test(version);
}

/**
 * @param {Record<string, string | undefined>} env
 * @returns {
 *   | { mode: 'same-origin' }
 *   | { mode: 'off-origin', dataRoot: string }
 *   | { mode: 'bucket', dataRootFor: (version: string) => string }
 * }
 */
function resolveDataSourceMode(env) {
  const dataRoot = env.PUBLIC_DATA_ROOT;
  const rawFromBucket = env.DATA_FROM_BUCKET;

  // Strict parsing: only the exact string "1" turns bucket mode on. Empty
  // or unset is off. Anything else is a caller mistake (a stray "true",
  // "0", trailing whitespace, ...) and fails loudly rather than silently
  // falling back to same-origin, which would ship a build the caller didn't
  // ask for.
  let fromBucket = false;
  if (rawFromBucket === '1') {
    fromBucket = true;
  } else if (rawFromBucket !== undefined && rawFromBucket !== '') {
    throw new Error(
      `DATA_FROM_BUCKET must be exactly "1" when set (or left unset/empty for off) -- got ${JSON.stringify(rawFromBucket)}`,
    );
  }

  if (dataRoot && fromBucket) {
    throw new Error(
      'PUBLIC_DATA_ROOT and DATA_FROM_BUCKET are mutually exclusive -- set only one. '
        + 'PUBLIC_DATA_ROOT points the browser at an off-origin data host; DATA_FROM_BUCKET '
        + 'has the deployed Worker serve data itself, same-origin, and computes its own root.',
    );
  }

  if (fromBucket) {
    return {
      mode: 'bucket',
      dataRootFor(version) {
        if (!isValidVersion(version)) {
          throw new Error(
            `DATA_FROM_BUCKET=1: computed CORPUS_VERSION ${JSON.stringify(version)} is not a valid `
              + `release-version path segment (must match ${VERSION_SEGMENT_RE}) -- the /data/<version>/ `
              + 'route could never serve it. Fix the version, not the route.',
          );
        }
        return `/data/${version}`;
      },
    };
  }
  if (dataRoot) return { mode: 'off-origin', dataRoot };
  return { mode: 'same-origin' };
}

/**
 * The PUBLIC_DATA_ROOT env every child process that reads it needs, resolved
 * once from a DATA_SOURCE (resolveDataSourceMode's return value) and the
 * build's CORPUS_VERSION -- pure, so it's unit-testable without spawning
 * anything. Empty in same-origin mode (nothing to pass); the off-origin URL
 * as-is; or bucket mode's own same-origin `/data/<version>` path, computed
 * via dataRootFor (which can throw if the version fails the route's rule --
 * see VERSION_SEGMENT_RE above). build-public.mjs spreads this into every
 * child's env instead of special-casing PUBLIC_DATA_ROOT at each run() call
 * site (a prior version of the build only passed it to some of them, which
 * left manifests/index.json's data_root null in bucket mode).
 *
 * @param {ReturnType<typeof resolveDataSourceMode>} dataSource
 * @param {string} corpusVersion
 * @returns {Record<string, string>}
 */
function childEnvFor(dataSource, corpusVersion) {
  if (dataSource.mode === 'off-origin') return { PUBLIC_DATA_ROOT: dataSource.dataRoot };
  if (dataSource.mode === 'bucket') return { PUBLIC_DATA_ROOT: dataSource.dataRootFor(corpusVersion) };
  return {};
}

export { resolveDataSourceMode, VERSION_SEGMENT_RE, isValidVersion, childEnvFor };
