// Search engine — operates on the prebuilt inverted indexes from Stage 6.
//
// Greek search: input is Unicode Greek OR TLG Beta Code (with optional * wildcards).
//   Converted to fold form (base Beta Code letters only) to match the index.
//   Beta Code letters already ARE the fold form (θ→q, φ→f, χ→x, ψ→y, ξ→c,
//   η→h, ω→w, …), so Latin input passes straight through; accents/breathings
//   (the ) ( / \ = | + markers) are stripped, matching the index's fold form.
// English search: whitespace-tokenized, lowercase.
// Phrase search: after intersection, verify token adjacency in segment data.
// Cross-language: AND (intersection) or OR (union) the two result sets.

import { getWork } from './works';

// Honour Astro's base path. BASE_URL may lack a trailing slash, so strip + join.
// Same root precedence as data.ts (see its longer doc comment): a build-time
// `PUBLIC_DATA_ROOT` (e.g. the Cloudflare R2 data domain) overrides the
// BASE_URL-derived default, and the desktop app's runtime
// globalThis.__READER_DATA_ROOT__ override — read lazily so module-import
// order doesn't matter — wins over both.
const DEFAULT_ROOT = import.meta.env.PUBLIC_DATA_ROOT
  ? import.meta.env.PUBLIC_DATA_ROOT.replace(/\/+$/, '')
  : `${import.meta.env.BASE_URL.replace(/\/$/, '')}/data`;
const ROOT = () =>
  (globalThis as { __READER_DATA_ROOT__?: string }).__READER_DATA_ROOT__ ?? DEFAULT_ROOT;
const searchBase = (work: string) => `${ROOT()}/${work}/search`;

// -- Data types -----------------------------------------------------------

export interface SegMeta {
  id: string;
  book: number;
  column: string;
  head: string;
  tokens: string;  // space-joined fold token sequence
  english_head: string;
}

type GrkIndex = Record<string, [number, number][]>; // fold → [[seg_idx, pos], ...]
type EngIndex = Record<string, number[]>;            // word → [seg_idx, ...]
// fold(surface) → [fold(headword), ...] — stage6_search.py's form_lemmata.json
// (John, 2026-09-23 ruling: Lemma mode must resolve a typed PRINTED FORM to
// its headword(s), not just the headword itself). Absent for a work whose
// index predates this file (e.g. a mounted sibling corpus) — see loadFormMap.
type FormLemmaIndex = Record<string, string[]>;

// Greek search can match by dictionary headword ('lemma', every inflected form)
// or by the exact surface form as written ('form').
export type MatchMode = 'lemma' | 'form';

// -- Per-work index loading (cached, lazy per file) -----------------------
//
// Each index file is fetched and cached on its own, and only when a query
// actually needs it (a Greek-only query never loads english.json, and only the
// lemma OR form index per its match mode). This keeps the request burst small:
// a Greek search over all works loads ~2 files/work, not 4 — which matters on
// Safari/WebKit, where a large simultaneous fetch burst can drop a request with
// "TypeError: Load failed" and (via Promise.all) sink the whole search.

const _fileCache = new Map<string, Promise<unknown>>();

function loadIndex<T>(work: string, file: string): Promise<T> {
  const key = `${work}/${file}`;
  const cached = _fileCache.get(key);
  if (cached) return cached as Promise<T>;
  const p = fetch(`${searchBase(work)}/${file}`).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status} for ${key}`);
    return r.json();
  });
  // Evict on failure so a transient drop can be retried — a rejected promise
  // must NOT stay cached (that would poison every later search in the tab).
  p.catch(() => { if (_fileCache.get(key) === p) _fileCache.delete(key); });
  _fileCache.set(key, p);
  return p as Promise<T>;
}

// form_lemmata.json is OPTIONAL per work: a mounted sibling corpus's own
// pipeline doesn't emit it yet (docs/p3-plan.md's aristotle mount), and this
// repo's own older builds predate it. A missing/failed fetch must fall back
// to "no map" (today's lemma.json-only behavior) for just THAT file — not
// propagate and fail the whole work the way an unexpected loadIndex()
// rejection does via the per-work catch in search() below.
//
// Deliberately NOT routed through loadIndex/_fileCache's generic
// evict-on-any-failure policy (John, 2026-09-23 ruling item 4): a 404 here
// means "this work has no map," a STABLE fact, so it resolves to {} and is
// cached forever — evicting it would re-fetch on every single search of the
// same work for no reason. A network error or non-404 status is still
// transient, so it rejects and rides the same evict-then-retry path
// loadIndex's other callers use (via the .catch below).
function loadFormMap(work: string): Promise<FormLemmaIndex> {
  const key = `${work}/form_lemmata.json`;
  const cached = _fileCache.get(key);
  if (cached) return cached as Promise<FormLemmaIndex>;
  const p = fetch(`${searchBase(work)}/form_lemmata.json`).then(r => {
    if (r.status === 404) return {} as FormLemmaIndex; // remembered absence — never evicted
    if (!r.ok) throw new Error(`HTTP ${r.status} for ${key}`);
    return r.json() as Promise<FormLemmaIndex>;
  });
  p.catch(() => { if (_fileCache.get(key) === p) _fileCache.delete(key); });
  _fileCache.set(key, p);
  return p as Promise<FormLemmaIndex>;
}

// Run `fn` over `items` with at most `limit` in flight at once (bounds the
// concurrent-fetch burst). Rejections propagate; callers that want per-item
// tolerance pass an `fn` that catches.
async function pool<T, R>(items: T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i]);
    }
  });
  await Promise.all(workers);
  return out;
}

// -- Unicode Greek → Beta Code fold form ----------------------------------

const GREEK_BETA: Record<string, string> = {
  α:'a',β:'b',γ:'g',δ:'d',ε:'e',ζ:'z',η:'h',θ:'q',ι:'i',κ:'k',
  λ:'l',μ:'m',ν:'n',ξ:'c',ο:'o',π:'p',ρ:'r',σ:'s',ς:'s',τ:'t',
  υ:'u',φ:'f',χ:'x',ψ:'y',ω:'w',ϝ:'v',
};

// Elision/koronis apostrophe variants, unified to ASCII "'" so the query
// side agrees with the index side. The index key comes from
// pipeline/reader_pipeline/beta.py's to_beta_key, whose _APOSTROPHES set
// ("'’᾽ʼ") normalizes straight, curly, koronis, and modifier-letter
// apostrophes all to ASCII before stage6 ever folds it (see
// test_to_beta_key_normalizes_grave_and_elision_apostrophe in
// pipeline/tests/test_beta.py) — so a printed elided form copied off the
// rendered page, which can carry any of these four marks (all four appear in
// real corpus text), must fold identically (John, 2026-09-23 ruling item 3).
const APOSTROPHES = new Set(["'", '’', '᾽', 'ʼ']);

export function greekFold(input: string): string {
  const out: string[] = [];
  for (const ch of input.normalize('NFD')) {
    const lower = ch.toLowerCase();
    const b = GREEK_BETA[lower];
    if (b) out.push(b);                          // Unicode Greek → fold letter
    else if (lower >= 'a' && lower <= 'z') out.push(lower); // Beta Code Latin input
    else if (APOSTROPHES.has(ch)) out.push("'");
    // skip combining marks, punctuation, Beta Code diacritics ) ( / \ = | +,
    // asterisk (handled by caller), and sigma-variant digits
  }
  return out.join('');
}

// -- Latin search fold -----------------------------------------------------
//
// Mirrors pipeline/reader_pipeline/latin.py's fold() exactly (memo §4.1):
// lowercase, u/v and i/j unified, NFD-decomposed BEFORE stripping non-base
// letters (so a macron/breve-carrying vowel folds to its base letter, not to
// nothing), with the æ/œ ligatures expanded first since Unicode NFD does not
// decompose them. Query-side counterpart to stage6_search.py's fold(key,
// 'lat') on the index-build side — both sides must agree or a Latin search
// silently misses everything.

const LATIN_LIGATURES: Record<string, string> = { æ: 'ae', œ: 'oe' };
const LATIN_FOLD_STRIP = /[^a-z']/g;

export function latinFold(input: string): string {
  let folded = input.toLowerCase();
  for (const [ligature, expansion] of Object.entries(LATIN_LIGATURES)) {
    folded = folded.split(ligature).join(expansion);
  }
  folded = folded.normalize('NFD').replace(/v/g, 'u').replace(/j/g, 'i');
  return folded.replace(LATIN_FOLD_STRIP, '');
}

// Per-language search-fold dispatch — the query-side analogue of
// stage6_search.py's fold(key, language). greekFold stays the default so
// grc (and any work whose language can't be resolved) is byte-identical to
// pre-Wave-2 behavior.
export type SourceLanguage = 'grc' | 'lat';

function sourceFold(input: string, lang: SourceLanguage): string {
  return lang === 'lat' ? latinFold(input) : greekFold(input);
}

// -- Posting-list helpers -------------------------------------------------

// Lemma mode only: resolves a typed term's fold to the GRK index key(s) to
// look up. HEADWORD PRECEDENCE (John, 2026-09-23 ruling item 2): if `fold`
// is already a key of the work's lemma index, the typed word IS a headword
// and the plain direct lookup wins outright — form_lemmata.json is never
// consulted, even when `fold` also happens to be listed there as the mapped
// SURFACE of some other, unrelated word (e.g. Heraclitus "hmera" is both its
// own headword and a printed form of "hmeros" — typing "hmera" must return
// only "hmera"'s own postings, not "hmeros"'s too; stage6_search.py's
// omission rule already keeps a surface entry out of the map only when it
// equals one of ITS OWN headwords, so this coincidental-collision case still
// needs handling here). Only when `fold` is NOT itself a headword key does a
// printed-form mapping (if any) supply the headword(s) to look up instead —
// possibly more than one, for a genuinely ambiguous surface form. Returns
// `[fold]` (the pre-existing direct-lookup behavior) for Form mode, a
// missing form map, or an unmapped fold. Never called for a wildcard term.
function resolveFold(
  idx: GrkIndex, formMap: FormLemmaIndex | null, matchMode: MatchMode, fold: string,
): string[] {
  if (matchMode !== 'lemma' || !formMap) return [fold];
  if (idx[fold]) return [fold];
  const mapped = formMap[fold];
  return mapped && mapped.length ? mapped : [fold];
}

function grkPosting(
  idx: GrkIndex, term: string, lang: SourceLanguage, matchMode: MatchMode, formMap: FormLemmaIndex | null,
): Set<number> {
  const wildcard = term.indexOf('*');
  if (wildcard === -1) {
    const fold = sourceFold(term, lang);
    const result = new Set<number>();
    for (const key of resolveFold(idx, formMap, matchMode, fold)) {
      for (const [si] of idx[key] ?? []) result.add(si);
    }
    return result;
  }
  // Prefix wildcard: fold the part before *, match all keys with that prefix
  const prefix = sourceFold(term.slice(0, wildcard), lang);
  const result = new Set<number>();
  for (const key of Object.keys(idx)) {
    if (key.startsWith(prefix)) {
      for (const [si] of idx[key]) result.add(si);
    }
  }
  return result;
}

function engPosting(idx: EngIndex, term: string): Set<number> {
  const word = term.toLowerCase().replace(/[^a-z'*]/g, '');
  if (!word || word === '*') return new Set(Object.values(idx).flat());
  if (word.endsWith('*')) {
    const prefix = word.slice(0, -1);
    const result = new Set<number>();
    for (const key of Object.keys(idx)) {
      if (key.startsWith(prefix)) for (const si of idx[key]) result.add(si);
    }
    return result;
  }
  return new Set(idx[word] ?? []);
}

function intersect(a: Set<number>, b: Set<number>): Set<number> {
  return new Set([...a].filter(x => b.has(x)));
}

function union(a: Set<number>, b: Set<number>): Set<number> {
  return new Set([...a, ...b]);
}

// Phrase check: does each position's resolved candidate fold(s) appear
// adjacent, in order, in the segment's headword-fold token sequence?
// `candidatesPerTerm[j]` is the list of keys a typed term at position j could
// mean (resolveFold — usually one key, more than one only for a genuinely
// ambiguous printed form), so adjacency is checked position-by-position
// rather than by string-inclusion of one joined pattern (John, 2026-09-23
// ruling item 1: meta.tokens is always stored as HEADWORD folds — see
// stage6_search.py's fold_seq_by_id — so a phrase typed with a printed form,
// e.g. "Πᾶσα τέχνη", must resolve "Πᾶσα" to its headword "πᾶς" before this
// check runs, or it silently misses despite each term's posting lookup
// succeeding on its own).
function phraseMatches(foldTokenSeq: string, candidatesPerTerm: string[][]): boolean {
  if (candidatesPerTerm.length === 0) return true;
  const toks = foldTokenSeq.split(' ');
  for (let i = 0; i + candidatesPerTerm.length <= toks.length; i++) {
    let ok = true;
    for (let j = 0; j < candidatesPerTerm.length; j++) {
      if (!candidatesPerTerm[j].includes(toks[i + j])) { ok = false; break; }
    }
    if (ok) return true;
  }
  return false;
}

// Char offsets of every English match in a segment's full text, tokenising
// exactly as the index does ([a-z']+ over the lowercased text) so a term hits
// whole tokens (and prefix* hits token starts). 'phrase' returns each phrase's
// start offset; 'all'/'any' return every matching token. One offset = one
// rendered occurrence, so repeats past the old 500-char cap now count and show.
function engMatchTerm(word: string, term: string): boolean {
  const c = term.toLowerCase().replace(/[^a-z'*]/g, '');
  if (!c || c === '*') return false;
  return c.endsWith('*') ? word.startsWith(c.slice(0, -1)) : word === c;
}
export function englishOccurrences(text: string, terms: string[], mode: SearchMode): number[] {
  const low = text.toLowerCase();
  const re = /[a-z']+/g;
  const toks: { w: string; i: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(low)) !== null) toks.push({ w: m[0], i: m.index });
  if (mode === 'phrase' && terms.length > 1) {
    const out: number[] = [];
    for (let i = 0; i + terms.length <= toks.length; i++) {
      let ok = true;
      for (let j = 0; j < terms.length; j++) {
        if (!engMatchTerm(toks[i + j].w, terms[j])) { ok = false; break; }
      }
      if (ok) out.push(toks[i].i);
    }
    return out;
  }
  return toks.filter(t => terms.some(term => engMatchTerm(t.w, term))).map(t => t.i);
}

// -- Public search API ----------------------------------------------------

export type SearchMode = 'all' | 'any' | 'phrase';
export type LangOp = 'and' | 'or';

export interface SearchResult {
  work: string;           // which work this hit belongs to
  meta: SegMeta;
  grkMatch: boolean;
  engMatch: boolean;
  grkPositions: number[]; // token positions in the segment where a Greek term matched
  engPositions: number[]; // char offsets in the segment's English where a term matched
}

// Positions of a single term across segments: seg_idx → [token positions].
function termPositions(
  idx: GrkIndex, term: string, lang: SourceLanguage, matchMode: MatchMode, formMap: FormLemmaIndex | null,
): Map<number, number[]> {
  const m = new Map<number, number[]>();
  const add = (posts: [number, number][]) => {
    for (const [si, pos] of posts) {
      const arr = m.get(si);
      if (arr) arr.push(pos);
      else m.set(si, [pos]);
    }
  };
  const wildcard = term.indexOf('*');
  if (wildcard === -1) {
    const fold = sourceFold(term, lang);
    for (const key of resolveFold(idx, formMap, matchMode, fold)) add(idx[key] ?? []);
  } else {
    const prefix = sourceFold(term.slice(0, wildcard), lang);
    for (const key of Object.keys(idx)) if (key.startsWith(prefix)) add(idx[key]);
  }
  return m;
}

// For each segment in `hits`, the token positions to highlight in a KWIC snippet.
function greekPositions(
  idx: GrkIndex,
  meta: SegMeta[],
  terms: string[],
  mode: SearchMode,
  hits: Set<number>,
  lang: SourceLanguage,
  matchMode: MatchMode,
  formMap: FormLemmaIndex | null,
): Map<number, number[]> {
  const out = new Map<number, number[]>();
  if (mode === 'phrase' && terms.length > 1) {
    // Same headword-resolution rule as phraseMatches (ruling item 1) — a
    // printed form's candidate positions must be found via its resolved
    // headword(s), not the raw typed fold.
    const candidatesPerTerm = terms.map(t => resolveFold(idx, formMap, matchMode, sourceFold(t.replace('*', ''), lang)));
    for (const si of hits) {
      const toks = meta[si].tokens.split(' ');
      const ps: number[] = [];
      for (let i = 0; i + candidatesPerTerm.length <= toks.length; i++) {
        let ok = true;
        for (let j = 0; j < candidatesPerTerm.length; j++) {
          if (!candidatesPerTerm[j].includes(toks[i + j])) { ok = false; break; }
        }
        if (ok) for (let j = 0; j < candidatesPerTerm.length; j++) ps.push(i + j);
      }
      out.set(si, ps);
    }
  } else {
    for (const t of terms) {
      for (const [si, ps] of termPositions(idx, t, lang, matchMode, formMap)) {
        if (!hits.has(si)) continue;
        const arr = out.get(si);
        if (arr) arr.push(...ps);
        else out.set(si, [...ps]);
      }
    }
  }
  for (const [si, ps] of out) out.set(si, [...new Set(ps)].sort((a, b) => a - b));
  return out;
}

// Search one work, returning hits tagged with that work. `lang` is the
// WORK's source language (Work.language from the registry, resolved by the
// caller) — it picks the fold function for the Greek/Latin query box, not
// to be confused with `matchMode` (lemma vs form) or `langOp` (AND/OR
// against the English box).
async function searchWork(
  work: string,
  grkTerms: string[],
  engTerms: string[],
  grkMode: SearchMode,
  engMode: SearchMode,
  langOp: LangOp,
  matchMode: MatchMode,
  lang: SourceLanguage,
): Promise<SearchResult[]> {
  // Fetch only what this query needs: meta always; the lemma OR form Greek
  // index iff there are Greek terms; the English index iff there are English
  // terms; form_lemmata.json iff Lemma mode (Form mode and wildcards never
  // consult it). Kick them off together, then await.
  const metaP = loadIndex<SegMeta[]>(work, 'meta.json');
  const grkP: Promise<GrkIndex | null> = grkTerms.length
    ? loadIndex<GrkIndex>(work, matchMode === 'form' ? 'form.json' : 'lemma.json')
    : Promise.resolve(null);
  const engP: Promise<EngIndex | null> = engTerms.length
    ? loadIndex<EngIndex>(work, 'english.json')
    : Promise.resolve(null);
  // A rejected loadFormMap (transient network/5xx — a 404 already resolves
  // to {} inside loadFormMap, never rejects) must fall back to "no map" for
  // just THIS call, same as before ruling item 4's caching fix — it must not
  // fail the whole work the way an unguarded rejection would via the
  // per-work catch in search() below. The underlying cache entry still gets
  // evicted by loadFormMap's own .catch, so the next search retries.
  const formMapP: Promise<FormLemmaIndex | null> = grkTerms.length && matchMode === 'lemma'
    ? loadFormMap(work).catch(() => null)
    : Promise.resolve(null);
  const meta = await metaP;
  const grkIdx = await grkP;
  const engIdx = await engP;
  const formMap = await formMapP;

  let grkHits: Set<number> | null = null;
  let engHits: Set<number> | null = null;

  if (grkTerms.length > 0 && grkIdx) {
    const postings = grkTerms.map(t => grkPosting(grkIdx, t, lang, matchMode, formMap));
    if (grkMode === 'any') {
      grkHits = postings.reduce(union);
    } else {
      grkHits = postings.reduce(intersect);
      if (grkMode === 'phrase' && grkTerms.length > 1) {
        // Resolve each typed word through the headword rule (ruling item 1)
        // before checking adjacency — a printed form's own fold is not what
        // meta.tokens stores.
        const candidatesPerTerm = grkTerms.map(t => resolveFold(grkIdx, formMap, matchMode, sourceFold(t.replace('*', ''), lang)));
        grkHits = new Set([...grkHits].filter(si =>
          phraseMatches(meta[si].tokens, candidatesPerTerm)
        ));
      }
    }
  }

  if (engTerms.length > 0 && engIdx) {
    const postings = engTerms.map(t => engPosting(engIdx, t));
    if (engMode === 'any') {
      engHits = postings.reduce(union);
    } else {
      engHits = postings.reduce(intersect);
      if (engMode === 'phrase' && engTerms.length > 1) {
        // Token-based phrase check on the FULL text (same routine that counts
        // occurrences), so a segment is a phrase hit iff it will render one.
        engHits = new Set([...engHits].filter(si =>
          englishOccurrences(meta[si].english_head, engTerms, 'phrase').length > 0
        ));
      }
    }
  }

  let combined: Set<number>;
  if (grkHits !== null && engHits !== null) {
    combined = langOp === 'and' ? intersect(grkHits, engHits) : union(grkHits, engHits);
  } else {
    combined = grkHits ?? engHits ?? new Set();
  }

  const grkPos = grkHits && grkIdx
    ? greekPositions(grkIdx, meta, grkTerms, grkMode, grkHits, lang, matchMode, formMap)
    : new Map<number, number[]>();

  return [...combined]
    .sort((a, b) => a - b)
    .map(si => ({
      work,
      meta: meta[si],
      grkMatch: grkHits?.has(si) ?? false,
      engMatch: engHits?.has(si) ?? false,
      grkPositions: grkPos.get(si) ?? [],
      // Occurrence offsets in the FULL English text — one rendered instance
      // each. Empty when this segment matched only on the Greek side.
      engPositions: engHits?.has(si)
        ? englishOccurrences(meta[si].english_head, engTerms, engMode)
        : [],
    }));
}

// Unified search across one or more works. `matchMode` chooses the Greek index
// (lemma = all forms of a headword, form = the exact inflected token).
export async function search(
  grkQuery: string,
  engQuery: string,
  grkMode: SearchMode,
  engMode: SearchMode,
  langOp: LangOp,
  works: string[],
  matchMode: MatchMode = 'lemma',
): Promise<SearchResult[]> {
  if (!grkQuery.trim() && !engQuery.trim()) return [];
  if (!works.length) return [];

  // Strip a leading '*' (Beta Code capital marker, e.g. *a)nqrwpos); the fold
  // form is caseless, and a leading wildcard would match everything anyway.
  const grkTerms = grkQuery.trim().split(/\s+/).filter(Boolean).map(t => t.replace(/^\*+/, ''));
  const engTerms = engQuery.trim().split(/\s+/).filter(Boolean);

  // Bound how many works load at once, and let a single work's failed index
  // load drop just that work (logged) instead of rejecting the whole search.
  let failures = 0;
  const perWork = await pool(works, 8, async w => {
    try {
      // Work language drives which fold function the query side uses
      // (Blocker: previously every work's Greek/Latin box was folded with
      // greekFold regardless of the work's actual language, so a Latin
      // work's search silently never matched u/v or i/j variants). Default
      // to 'grc' for an unregistered work id (matches greekFold's prior
      // unconditional behavior, so existing Greek-only callers/tests are
      // unaffected).
      const lang: SourceLanguage = getWork(w)?.language ?? 'grc';
      return await searchWork(w, grkTerms, engTerms, grkMode, engMode, langOp, matchMode, lang);
    } catch (err) {
      console.warn(`search: skipping ${w} —`, err);
      failures++;
      return [] as SearchResult[];
    }
  });
  // If EVERY work failed to load (e.g. offline, or a transient window mid-deploy
  // when the index JSONs are briefly unavailable), surface it as an error to
  // retry — not as an empty result that reads as a misleading "No passages
  // found." A partial failure still returns what loaded.
  if (failures === works.length) {
    throw new Error('Could not load the search index — check your connection and try again.');
  }
  return perWork.flat();
}
