// Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 3).
//
// Adapts a mounted corpus's legacy search/ directory (aristotle-reader shape:
// greek_form.json, greek_lemma.json, meta.json with `greek_head` instead of
// `head`/`tokens`, english.json) into this repo's stage6_search.py shape
// (form.json, lemma.json, meta.json with {id, book, column, head, tokens,
// english_head}, english.json).
//
// form.json/lemma.json are position-indexed posting lists ([[seg_idx,
// token_pos], ...]) keyed on `fold(term)` -- the SAME fold, the SAME
// postings, just renamed files (docs/p3-probe.md's key-path diff: 0
// aristotle-only / 0 classical-only paths in both files). Only meta.json's
// SHAPE differs, so only meta.json is rebuilt -- and it must be rebuilt in
// the ORIGINAL array order, because lemma.json/form.json's postings are
// [seg_idx, token_pos] pairs indexing straight into meta.json's array
// position; reordering meta would silently misalign every posting.
//
// english.json's shape can ALSO differ and needs normalizing (unlike
// docs/p3-probe.md's original "0 aristotle-only / 0 classical-only paths"
// finding, recorded before aristotle-reader's stage6_search.py grew
// word-position tracking on 2026-09-07): this repo's contract is
// {word: [seg_idx, ...]}, but a newer-sibling english.json may carry
// {word: [[seg_idx, word_pos], ...]} instead -- see normalizeEnglishIndex().
//
// rebuildMeta() mirrors pipeline/reader_pipeline/stage6_search.py's own
// per-segment computation (run(), lines ~165-190) exactly:
//   head         <- " ".join of the first two lines' token surface forms
//   tokens       <- per-token fold(first lemma of analyses[key] ?? key),
//                   space-joined, in document order
//   english_head <- the segment's own english.text (full, not truncated)
//
// fold() is IMPORTED from shared/lib/search.ts (greekFold/latinFold), never
// reimplemented -- see loadFold() below. greekFold operating on a Beta Code
// key (not Unicode Greek) produces byte-identical output to stage6_search.py's
// fold_lemma() (both: lowercase, strip everything but [a-z']); verified
// directly against the Python implementation during stage 2 development.

import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));

let foldCache;

// Bundles shared/lib/search.ts through esbuild and caches greekFold/
// latinFold -- the same "run a real bundle of the .ts module" technique
// scripts/vendor-aristotle-registry.mjs and scripts/extract-registry.mjs
// already use for works.ts/authors.ts, applied here to search.ts's pure fold
// functions. The import.meta.env.* defines are dummy values: search.ts's
// module-level DEFAULT_ROOT computation references them, but nothing this
// module calls (greekFold/latinFold) ever reads DEFAULT_ROOT.
//
// Evaluated as a CommonJS bundle via `new Function`, NOT `import()` of a
// written-out file: a dynamic `import()` of a path vitest's module runner
// didn't itself resolve fails there ("Cannot find module") even for a
// trivial freshly-written file, unrelated to this module's own logic
// (confirmed with a minimal repro during stage-2 development) -- so this
// avoids the dynamic-import path entirely rather than working around a
// test-runner quirk inside the adapter itself.
async function loadFold() {
  if (foldCache) return foldCache;
  const esbuildPath = join(ROOT, 'app', 'node_modules', 'esbuild', 'lib', 'main.js');
  const { default: esbuild } = await import(pathToFileURL(esbuildPath).href);
  const result = await esbuild.build({
    entryPoints: [join(ROOT, 'shared', 'lib', 'search.ts')],
    bundle: true,
    format: 'cjs',
    platform: 'node',
    write: false,
    define: {
      'import.meta.env.PUBLIC_DATA_ROOT': 'undefined',
      'import.meta.env.BASE_URL': JSON.stringify('/'),
      'import.meta.env.PUBLIC_SHOW_PRIVATE': 'undefined',
      'import.meta.env.PUBLIC_READER_FIXTURES': 'undefined',
      'import.meta.env.PUBLIC_WING': 'undefined',
    },
  });
  const mod = { exports: {} };
  const evaluate = new Function('module', 'exports', result.outputFiles[0].text);
  evaluate(mod, mod.exports);
  foldCache = { greekFold: mod.exports.greekFold, latinFold: mod.exports.latinFold };
  return foldCache;
}

/** Per-language search-fold dispatch -- mirrors stage6_search.py's fold(). */
export async function fold(key, language) {
  const { greekFold, latinFold } = await loadFold();
  if (language === 'lat') return latinFold(key);
  if (language === 'grc') return greekFold(key);
  throw new Error(`corpus-adapter/search: unsupported language: ${JSON.stringify(language)}`);
}

/**
 * Rebuilds meta.json in the ORIGINAL (their) order.
 *
 * @param {Array<{id: string, book: number, column: string}>} theirMeta -
 *   the legacy meta.json, read only for its ordering + segment ids (book/
 *   column are carried through unchanged).
 * @param {Array<{book: number, segments: Array<object>}>} bookData - every
 *   book-NN.json for the work, parsed.
 * @param {Record<string, Array<{lemma: string}>>} analyses - the work's
 *   analyses.json.
 * @param {string} language - 'grc' | 'lat', for fold().
 * @returns {Promise<Array<object>>} the rebuilt meta.json array, in
 *   theirMeta's order, each entry {id, book, column, head, tokens,
 *   english_head} (this exact key order -- matches stage6_search.py's own
 *   dict literal, load-bearing for the differential byte-equality gate).
 */
export async function rebuildMeta(theirMeta, bookData, analyses, language) {
  const { greekFold, latinFold } = await loadFold();
  const foldFn = language === 'lat' ? latinFold : language === 'grc' ? greekFold : null;
  if (!foldFn) {
    throw new Error(`corpus-adapter/search: unsupported language: ${JSON.stringify(language)}`);
  }

  const segmentsById = new Map();
  for (const book of bookData) {
    for (const seg of book.segments ?? []) {
      segmentsById.set(seg.id, seg);
    }
  }

  return theirMeta.map((entry) => {
    const seg = segmentsById.get(entry.id);
    if (!seg) {
      throw new Error(`corpus-adapter/search: rebuildMeta: no segment found for meta id ${entry.id}`);
    }
    const lines = seg.greek ?? [];

    const head = lines
      .slice(0, 2)
      .map((line) => (line.tokens ?? []).map((t) => t.t).join(' '))
      .join(' ');

    const foldSeq = [];
    for (const line of lines) {
      for (const tok of line.tokens ?? []) {
        const key = tok.k;
        if (!key) continue;
        const groups = analyses[key];
        const lemma = groups?.find((g) => g.lemma)?.lemma;
        foldSeq.push(foldFn(lemma || key));
      }
    }

    const englishHead = seg.english?.text ?? '';

    return {
      id: entry.id,
      book: entry.book,
      column: entry.column,
      head,
      tokens: foldSeq.join(' '),
      english_head: englishHead,
    };
  });
}

/**
 * Normalizes one work's english.json posting-list shape to this repo's
 * contract -- {word: [seg_idx, ...]}, deduped and ascending (matches
 * pipeline/reader_pipeline/stage6_search.py lines ~155-163) -- tolerating
 * the sibling's newer {word: [[seg_idx, word_pos], ...]} shape (added to
 * aristotle-reader's stage6_search.py 2026-09-07, after docs/p3-probe.md's
 * "0 aristotle-only / 0 classical-only paths" finding was recorded; that
 * finding is now stale for english.json specifically).
 *
 * Root cause this fixes: shared/lib/search.ts's engPosting() does
 * `new Set(idx[word])` expecting bare seg_idx numbers. Given the paired
 * shape it instead builds a Set of [seg_idx, word_pos] ARRAYS, and a later
 * `meta[si]` lookup with an array key stringifies to e.g. "182,332" --
 * always undefined -- throwing `Cannot read properties of undefined
 * (reading 'english_head')` for every mounted work on any English search.
 *
 * Already-flat entries pass through unchanged and `changed` stays false,
 * so adaptSearchFiles() leaves a contract-shaped english.json unwritten.
 *
 * @param {Record<string, Array<number|[number, number]>>} englishIdx - the
 *   parsed english.json.
 * @returns {{ index: Record<string, number[]>, changed: boolean }}
 */
export function normalizeEnglishIndex(englishIdx) {
  const index = {};
  let changed = false;
  for (const [word, postings] of Object.entries(englishIdx)) {
    if (postings.length > 0 && Array.isArray(postings[0])) {
      const segIdxs = new Set(postings.map(([si]) => si));
      index[word] = [...segIdxs].sort((a, b) => a - b);
      changed = true;
    } else {
      index[word] = postings;
    }
  }
  return { index, changed };
}

/**
 * Builds one mounted work's form_lemmata.json straight from its OWN token
 * analyses -- the same source data rebuildMeta() already walks (this
 * work's book-NN.json + analyses.json) -- mirroring
 * pipeline/reader_pipeline/stage6_search.py's form_lemmata_idx computation
 * (module docstring there) exactly: for every token, fold its surface key
 * to `sf`, look up that key's analysis groups, and for each group's lemma
 * (or the key itself when a group has no lemma) fold it to `fl` and record
 * sf -> fl. An entry survives only when it has at least one fl and `sf`
 * differs from every fl it collected; an ambiguous surface (more than one
 * fl across its occurrences) keeps them all, sorted.
 *
 * Fixed 2026-09-23 (Sol re-review #1): the prior implementation restricted
 * a CORPUS-WIDE surface->headword map (merged across every mounted work)
 * to this work's own form.json/lemma.json KEYS. That is not the same
 * check as "this work's own tokens actually produced sf -> fl": if work W
 * has surface s analysed as headword A, ANOTHER work in the corpus also
 * maps s -> B, and W separately happens to have its own headword B (from
 * some unrelated surface), the intersection kept the false s -> B link for
 * W. Deriving directly from W's own token analyses -- as this function and
 * stage6_search.py both do -- cannot produce a link no token in W actually
 * has.
 *
 * @param {Array<{segments: Array<{greek?: Array<{tokens?: Array<{k?: string}>}>}>}>} bookData -
 *   every book-NN.json for the work, parsed (same shape rebuildMeta() reads).
 * @param {Record<string, Array<{lemma?: string}>>} analyses - the work's own
 *   analyses.json, parsed.
 * @param {(key: string) => string} foldFn - the language's fold function
 *   (greekFold or latinFold from loadFold()).
 * @returns {Record<string, string[]>} the per-work form_lemmata.json
 *   contents (possibly {}).
 */
export function buildFormLemmata(bookData, analyses, foldFn) {
  const formLemmata = new Map(); // sf -> Set<fl>
  for (const book of bookData) {
    for (const seg of book.segments ?? []) {
      for (const line of seg.greek ?? []) {
        for (const tok of line.tokens ?? []) {
          const key = tok.k;
          if (!key) continue;
          const sf = foldFn(key);
          if (!sf) continue;
          const groups = analyses[key];
          if (!groups) continue;
          for (const g of groups) {
            const fl = foldFn(g.lemma || key);
            if (!fl) continue;
            if (!formLemmata.has(sf)) formLemmata.set(sf, new Set());
            formLemmata.get(sf).add(fl);
          }
        }
      }
    }
  }

  const result = {};
  for (const [sf, flSet] of formLemmata) {
    if (flSet.has(sf)) continue;
    result[sf] = [...flSet].sort();
  }
  return result;
}

/**
 * In-place adaptation of one work's mounted search/ directory: renames
 * greek_form.json/greek_lemma.json to form.json/lemma.json, rewrites
 * meta.json via rebuildMeta(), normalizes english.json's posting-list
 * shape via normalizeEnglishIndex() (only rewritten when the sibling's
 * shape actually needs converting), and writes this work's own
 * form_lemmata.json via buildFormLemmata() -- unconditionally, same as
 * stage6_search.py does for native works, since it is derived from data
 * (bookData/analyses) this function already requires.
 *
 * @param {string} searchDir - the mounted work's search/ directory
 *   (build/dist/<id>/search), already populated by mount-corpus.mjs's plain
 *   copy step.
 * @param {Array<object>} bookData - every book-NN.json for the work, parsed.
 * @param {object} analyses - the work's analyses.json, parsed.
 * @param {string} language - 'grc' | 'lat'.
 */
export async function adaptSearchFiles(searchDir, bookData, analyses, language) {
  const greekFormPath = join(searchDir, 'greek_form.json');
  const greekLemmaPath = join(searchDir, 'greek_lemma.json');
  const metaPath = join(searchDir, 'meta.json');
  const englishPath = join(searchDir, 'english.json');

  if (!existsSync(greekFormPath)) {
    throw new Error(`corpus-adapter/search: missing ${greekFormPath}`);
  }
  if (!existsSync(greekLemmaPath)) {
    throw new Error(`corpus-adapter/search: missing ${greekLemmaPath}`);
  }
  if (!existsSync(metaPath)) {
    throw new Error(`corpus-adapter/search: missing ${metaPath}`);
  }
  if (!existsSync(englishPath)) {
    throw new Error(`corpus-adapter/search: missing ${englishPath}`);
  }

  const { greekFold, latinFold } = await loadFold();

  renameSync(greekFormPath, join(searchDir, 'form.json'));
  renameSync(greekLemmaPath, join(searchDir, 'lemma.json'));

  const theirMeta = JSON.parse(readFileSync(metaPath, 'utf8'));
  const rebuilt = await rebuildMeta(theirMeta, bookData, analyses, language);
  writeFileSync(metaPath, JSON.stringify(rebuilt, null, 1), 'utf8');

  const theirEnglish = JSON.parse(readFileSync(englishPath, 'utf8'));
  const { index: normalizedEnglish, changed } = normalizeEnglishIndex(theirEnglish);
  if (changed) {
    writeFileSync(englishPath, JSON.stringify(normalizedEnglish), 'utf8');
  }

  const foldFn = language === 'lat' ? latinFold : language === 'grc' ? greekFold : null;
  if (!foldFn) {
    throw new Error(`corpus-adapter/search: unsupported language: ${JSON.stringify(language)}`);
  }
  const formLemmata = buildFormLemmata(bookData, analyses, foldFn);
  writeFileSync(join(searchDir, 'form_lemmata.json'), JSON.stringify(formLemmata), 'utf8');
}
