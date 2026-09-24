// Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 3, 8).
//
// adaptManifest() wraps one mounted corpus's LEGACY manifest.json (the
// aristotle-reader shape: {work: {...}, books: [...], analyses: {...}, ...})
// into schema/manifest.v1.json's shape, using the vendored registry work
// entry (corpora/aristotle/registry.yaml) for everything the legacy manifest
// doesn't carry. The failure list this closes is docs/p3-probe.md's
// validate_contracts run: 11 missing required v1 properties (schema_version,
// id, author, title, language, route, citation, editions, translations,
// apparatus, corpus_version).
//
// The legacy `work` and `books` root keys are preserved VERBATIM as extra
// root properties -- manifest.v1.json's own docstring allows this ("Legacy
// pipeline statistics may remain as extra root properties"), and classical's
// own emitted manifests already do the same (their `work`/`books` keys are
// the stage7_emit.py Manifest.data passthrough). verify_shared_lsj.py reads
// `manifest.work.language` (falling back to 'grc' when absent) -- the
// legacy `work` block never carries a `language` key, so that fallback is
// exactly what resolves it correctly for a grc-only corpus.
//
// Pure function: no filesystem access. The caller probes which apparatus
// files exist under the mounted work directory and passes the resulting
// booleans in (`apparatus`) -- keeps this module trivially unit-testable
// and keeps the adaptManifest/mount-corpus.mjs boundary at "data in, data
// out".

const REQUIRED_LEGACY_WORK_FIELDS = [
  'id',
  'title',
  'author',
  'tlg_author',
  'tlg_work',
  'greek_edition',
];

// Mirrors stage7_emit.py's own apparatus derivation exactly
// (`(out_dir / f"{name}.json").exists()` for these six names) -- callers
// pass the resulting booleans as `apparatus`.
export const APPARATUS_FILES = [
  'footnotes',
  'sidenotes',
  'paratext',
  'figures',
  'sections',
  'philosophers',
];

// Legacy registry.yaml translation `slot` values -> manifest.v1.json's
// translation.slot enum. Only "english" renames (to "primary"); every other
// legacy slot name ("secondary", "third", "overlay", "column") is already
// the v1 vocabulary word for word -- confirmed by reading a live classical
// manifest (build/dist/meditations/manifest.json's `translations[].slot`:
// "english"/"secondary" in `presentation`, "primary"/"secondary" at the top
// level -- and build/dist/gorgias-fragments/manifest.json for "overlay").
const SLOT_RENAME = { english: 'primary' };

function renamedSlot(slot) {
  return SLOT_RENAME[slot] ?? slot;
}

// John's standing rule (as of 2026, restated 2026-09-22): a translation is
// public domain in the US when its publication year is 1930 or earlier
// (pre-1931). Bump this by hand each January -- never compute it from the
// clock, since "pre-1931 as of 2026" is a fixed calendar fact, not a rolling
// window.
export const ARISTOTLE_PD_CUTOFF_YEAR = 1930;

// Registry translation `name` strings embed the publication year, e.g.
// "E. M. Edghill (Oxford, 1928)". Take the EARLIEST 4-digit number in the
// string -- first publication is what US copyright turns on, so a name like
// "William Ellis (1776; rev. 1912)" is public domain by 1776, not 1912 --
// no match -> null, so a translation without a parseable year comes out
// unverified rather than silently guessed. A revised edition whose revision
// postdates 1930 must carry an explicit `license` on the registry entry:
// that wins over this rule (see the `t.license ?? translationLicense(t.name)`
// line below).
export function translationYear(name) {
  if (typeof name !== 'string') return null;
  const matches = name.match(/\d{4}/g);
  if (!matches || matches.length === 0) return null;
  return Number(matches[0]);
}

function translationLicense(name) {
  const year = translationYear(name);
  if (year == null) {
    return { status: 'unverified', rationale: `${name}: no publication year found` };
  }
  if (year <= ARISTOTLE_PD_CUTOFF_YEAR) {
    return { status: 'public-domain-us' };
  }
  return { status: 'unverified', rationale: `${name}: published after ${ARISTOTLE_PD_CUTOFF_YEAR}` };
}

/**
 * @param {object} legacy - parsed legacy manifest.json ({work, books, ...}).
 * @param {object} registryWork - one corpora/aristotle/registry.yaml work
 *   entry (id, slug, title, author, language, books, bookLabels,
 *   greekEdition, translations[], citation, blurb, ...).
 * @param {{corpusVersion: string, apparatus?: Record<string, boolean>}} options
 * @returns {object} a schema/manifest.v1.json-shaped manifest, with the
 *   legacy `work`/`books` keys preserved as extra root properties.
 */
export function adaptManifest(legacy, registryWork, { corpusVersion, apparatus } = {}) {
  if (!legacy || typeof legacy !== 'object') {
    throw new Error('adaptManifest: legacy manifest must be an object');
  }
  if (!registryWork || typeof registryWork !== 'object') {
    throw new Error('adaptManifest: registryWork must be an object');
  }
  if (!corpusVersion) {
    throw new Error('adaptManifest: corpusVersion is required');
  }

  const work = legacy.work;
  if (!work || typeof work !== 'object') {
    throw new Error('adaptManifest: legacy manifest has no work block');
  }
  for (const field of REQUIRED_LEGACY_WORK_FIELDS) {
    if (!work[field]) {
      throw new Error(`adaptManifest: legacy manifest.work.${field} is missing`);
    }
  }
  if (!Array.isArray(legacy.books) || legacy.books.length === 0) {
    throw new Error('adaptManifest: legacy manifest.books must be a non-empty array');
  }

  const language = registryWork.language;
  if (language !== 'grc' && language !== 'lat') {
    throw new Error(
      `adaptManifest: registryWork.language must be grc|lat, got ${JSON.stringify(language)}`,
    );
  }
  if (!registryWork.id || !registryWork.slug || !registryWork.author || !registryWork.title) {
    throw new Error('adaptManifest: registryWork is missing id/slug/author/title');
  }

  const citationBooks = legacy.books.map((b) => {
    if (b.book == null || !b.first_column || !b.last_column) {
      throw new Error(
        `adaptManifest: legacy books entry missing book/first_column/last_column: ${JSON.stringify(b)}`,
      );
    }
    return { n: b.book, start: b.first_column, end: b.last_column };
  });

  const registryCitation = registryWork.citation;
  if (!registryCitation || !registryCitation.scheme) {
    throw new Error('adaptManifest: registryWork.citation.scheme is required');
  }

  const translations = (registryWork.translations ?? []).map((t) => {
    if (!t.id || !t.name || !t.slot) {
      throw new Error(
        `adaptManifest: registryWork translation missing id/name/slot: ${JSON.stringify(t)}`,
      );
    }
    const slot = renamedSlot(t.slot);
    return {
      id: t.id,
      name: t.name,
      slot,
      // manifest.v1.json's translation schema forces default:true iff
      // slot==="primary" and default:false otherwise (its own allOf/if/then
      // constraint) -- so "default" is fully determined by the renamed
      // slot, not a separate registry field. registryWork.defaultTranslation
      // (present on a handful of works, e.g. EN: 'ostwald') is a distinct,
      // UI-only hint that stays available via the verbatim `presentation`
      // block below; using it to pick which translation is "primary" here
      // would violate the schema whenever it names a non-"english"-slot
      // translation (EN's own defaultTranslation does exactly that).
      default: slot === 'primary',
      // A registry translation entry may carry an explicit `license` (a
      // vendor correction, e.g. Ostwald's -- corpora/aristotle/registry.yaml
      // via scripts/vendor-aristotle-registry.mjs's POST_VENDOR_CORRECTIONS).
      // That is a researched, human ruling and wins over the derived
      // year-cutoff guess.
      license: t.license ?? translationLicense(t.name),
    };
  });
  if (!translations.some((t) => t.slot === 'primary')) {
    throw new Error(
      `adaptManifest: ${registryWork.id}: no registry translation has slot "english" (-> primary)`,
    );
  }

  const resolvedApparatus = {};
  for (const name of APPARATUS_FILES) {
    resolvedApparatus[name] = Boolean(apparatus?.[name]);
  }

  // presentation: the registry work block verbatim, minus `route` (route
  // ownership lives only in the cross-corpus route registry -- P2 stage 5
  // precedent, schemas/manifest.v1.json's own `presentation` docstring).
  // The vendored aristotle registry never declares a `route` key today; the
  // strip is defensive, mirroring stage7_emit.py's own comment on the same
  // point.
  const { route: _route, ...presentation } = registryWork;

  return {
    schema_version: 'manifest.v1',
    id: registryWork.id,
    author: registryWork.author,
    title: registryWork.title,
    language,
    // `/<author>/<slug>` is the same bare identity form every manifest.json
    // carries (stage7_emit.py's own `route` field) -- an input that
    // scripts/emit-lyceum-manifest.mjs's routeSegments()/toLyceumManifest()
    // prefixes into the real /texts/... and /read/... page addresses. It is
    // never served as a URL on its own.
    route: `/${registryWork.author}/${registryWork.slug}`,
    citation: {
      scheme: registryCitation.scheme,
      books: citationBooks,
    },
    editions: [
      {
        language,
        edition: work.greek_edition,
        source: {
          kind: 'tlg',
          author: work.tlg_author,
          work: work.tlg_work,
        },
        license: { status: 'unverified' },
      },
    ],
    translations,
    presentation,
    apparatus: resolvedApparatus,
    corpus_version: corpusVersion,
    // Legacy pipeline stats, preserved verbatim (see module docstring).
    work: legacy.work,
    books: legacy.books,
  };
}
