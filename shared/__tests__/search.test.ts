import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { englishOccurrences, greekFold, latinFold, search } from '../lib/search';

// Latin-language test work ids (unregistered in the real WORKS registry, so
// getWork() would otherwise resolve them to 'grc' and mask the Blocker 2
// asymmetry this file guards against): stubbed to `language: 'lat'` here,
// everything else in '../lib/works' stays real.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  return {
    ...actual,
    getWork: (id: string) =>
      id.startsWith('TLat') ? { language: 'lat' } : actual.getWork(id),
  };
});

const meta = [
  { id: 's1', book: 1, column: '1094a', head: 'λόγος ἀρετή', tokens: 'logos areth', english_head: 'virtue is a habit of choice' },
  { id: 's2', book: 1, column: '1094b', head: 'ψυχή λόγος', tokens: 'yuxh logos', english_head: 'happiness and virtue together' },
  { id: 's3', book: 2, column: '1100a', head: 'τέχνη', tokens: 'texnh', english_head: 'craft concerns making' },
];

const greekIndex = {
  logos: [[0, 0], [1, 1]],
  areth: [[0, 1]],
  yuxh: [[1, 0]],
  texnh: [[2, 0]],
} satisfies Record<string, [number, number][]>;

const englishIndex = {
  virtue: [0, 1],
  habit: [0],
  choice: [0],
  happiness: [1],
  craft: [2],
  making: [2],
} satisfies Record<string, number[]>;

function json(data: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(data) } as Response);
}

describe('greekFold', () => {
  it.each([
    ['λόγος', 'logos'],
    ['lo/gos', 'logos'],
    ['*a)nqrwpos', 'anqrwpos'],
    ["ἀρετή'", "areth'"],
    ['ψυχή κόσμος', 'yuxhkosmos'],
  ])('folds %s', (input, expected) => {
    expect(greekFold(input)).toBe(expected);
  });

  // Ruling item 3 (2026-09-23): the pipeline's key fold normalizes every
  // elision/koronis apostrophe variant to ASCII "'" before stage6 ever folds
  // it (pipeline/reader_pipeline/beta.py's _APOSTROPHES set, exercised by
  // test_to_beta_key_normalizes_grave_and_elision_apostrophe in
  // test_beta.py) — so a printed form copied off the rendered page, which
  // can carry any of these four marks, must fold to the SAME index key as
  // typed Beta Code input. Before this fix, greekFold only recognized the
  // ASCII apostrophe and silently dropped the other three.
  it.each([
    ['κατ’', "kat'"], // U+2019 RIGHT SINGLE QUOTATION MARK (curly, from copy-paste)
    ['κατ᾽', "kat'"], // U+1FBD GREEK KORONIS
    ['κατʼ', "kat'"], // U+02BC MODIFIER LETTER APOSTROPHE
  ])('folds elision apostrophe variant %s the same as ASCII', (input, expected) => {
    expect(greekFold(input)).toBe(expected);
  });
});

describe('latinFold', () => {
  // Mirrors pipeline/reader_pipeline/latin.py's fold() test cases exactly
  // (test_latin.py) — the query-side and index-build-side fold functions
  // must agree.
  it.each([
    ['vita', 'uita'],
    ['uita', 'uita'],
    ['coniunx', 'coniunx'],
    ['conjunx', 'coniunx'],
    ['VIRTUS', 'uirtus'],
    ['Virtus!', 'uirtus'],
    ['mālus', 'malus'],   // macron-carrying vowel folds to its base letter
    ['mălus', 'malus'],   // breve-carrying vowel folds to its base letter
    ['cælum', 'caelum'],  // æ ligature expands before folding
    ['fœdus', 'foedus'],  // œ ligature expands before folding
  ])('folds %s to %s', (input, expected) => {
    expect(latinFold(input)).toBe(expected);
  });
});

describe('search', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(greekIndex);
      if (path.endsWith('/english.json')) return json(englishIndex);
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns no results for empty queries or no works', async () => {
    await expect(search('', ' ', 'all', 'all', 'and', ['TEmpty'])).resolves.toEqual([]);
    await expect(search('logos', '', 'all', 'all', 'and', [])).resolves.toEqual([]);
  });

  it('supports all, any, and phrase modes', async () => {
    expect(await search('logos areth', '', 'all', 'all', 'and', ['TAll'])).toHaveLength(1);
    expect(await search('yuxh areth', '', 'any', 'all', 'and', ['TAny'])).toHaveLength(2);
    expect(await search('logos areth', '', 'phrase', 'all', 'and', ['TPhraseMiss'])).toHaveLength(1);
    expect(await search('areth logos', '', 'phrase', 'all', 'and', ['TPhraseHit'])).toHaveLength(0);
  });

  it('supports wildcards for Greek and English terms', async () => {
    const greek = await search('tex*', '', 'all', 'all', 'and', ['TGreekWildcard']);
    const english = await search('', 'hap*', 'all', 'all', 'and', ['TEngWildcard']);
    expect(greek.map((r) => r.meta.id)).toEqual(['s3']);
    expect(english.map((r) => r.meta.id)).toEqual(['s2']);
  });

  it('combines Greek and English boxes with AND or OR', async () => {
    const andHits = await search('logos', 'happiness', 'all', 'all', 'and', ['TAnd']);
    const orHits = await search('texnh', 'happiness', 'all', 'all', 'or', ['TOr']);
    expect(andHits.map((r) => r.meta.id)).toEqual(['s2']);
    expect(orHits.map((r) => r.meta.id)).toEqual(['s2', 's3']);
  });

  it.each([
    ['whitespace only', '   ', '\t'],
    ['pure punctuation', '!!!', '...'],
    ['regex metacharacters', '.*+?^${}()|[]\\', '.*+?^${}()|[]\\'],
    ['Greek string', 'λόγος τέχνη', 'virtue'],
    ['very long string', `${'logos '.repeat(500)}texnh`, `${'virtue '.repeat(500)}craft`],
  ])('does not throw for adversarial input: %s', async (_label, grk, eng) => {
    await expect(search(grk, eng, 'any', 'any', 'or', [`TAdv-${_label}`])).resolves.toEqual(expect.any(Array));
  });
});

// Blocker: search() previously folded EVERY work's source-language box with
// greekFold, regardless of the work's actual language — a Latin work's
// query for "vita" would never match an index built with the fold("vita",
// "lat") == fold("uita", "lat") equivalence, because the query side used
// Greek's Beta-Code fold table instead. These tests use a work id
// ('TLat...') the top-of-file `vi.mock('../lib/works', ...)` resolves to
// `language: 'lat'`, with a synthetic index built the way stage6_search.py
// would build it for a Latin work (fold(key, 'lat') keys).
describe('search — Latin work language dispatch', () => {
  const latMeta = [
    { id: 'l1', book: 1, column: '1.1', head: 'vita', tokens: 'uita', english_head: 'life is short' },
    { id: 'l2', book: 1, column: '1.2', head: 'coniunx cara', tokens: 'coniunx cara', english_head: 'a dear spouse' },
  ];
  // Index built with the u/v, i/j-unified fold — "vita"/"uita" both fold to
  // "uita"; "coniunx"/"conjunx" both fold to "coniunx" (latin.py's fold()).
  const latIndex = {
    uita: [[0, 0]],
    coniunx: [[1, 0]],
    cara: [[1, 1]],
  } satisfies Record<string, [number, number][]>;

  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(latMeta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(latIndex);
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('matches "vita" and "uita" as the same query (exact)', async () => {
    const viaV = await search('vita', '', 'all', 'all', 'and', ['TLatExact']);
    const viaU = await search('uita', '', 'all', 'all', 'and', ['TLatExact']);
    expect(viaV.map((r) => r.meta.id)).toEqual(['l1']);
    expect(viaU.map((r) => r.meta.id)).toEqual(['l1']);
  });

  it('matches "coniunx" and "conjunx" as the same query (exact)', async () => {
    const viaI = await search('coniunx', '', 'all', 'all', 'and', ['TLatExact']);
    const viaJ = await search('conjunx', '', 'all', 'all', 'and', ['TLatExact']);
    expect(viaI.map((r) => r.meta.id)).toEqual(['l2']);
    expect(viaJ.map((r) => r.meta.id)).toEqual(['l2']);
  });

  it('supports a u/v-folded wildcard prefix query', async () => {
    // "con*" and "uit*" should prefix-match the folded ("uita"/"coniunx")
    // keys regardless of which u/v i/j spelling the user types.
    const hits = await search('con*', '', 'all', 'all', 'and', ['TLatWildcard']);
    expect(hits.map((r) => r.meta.id)).toEqual(['l2']);
  });

  it('matches a u/v-folded phrase query across the token sequence', async () => {
    // meta.tokens for l2 is the fold sequence "coniunx kara" -- a phrase
    // query spelled with the alternate convention ("conjunx cara") must
    // still hit it.
    const hits = await search('conjunx cara', '', 'phrase', 'all', 'and', ['TLatPhrase']);
    expect(hits.map((r) => r.meta.id)).toEqual(['l2']);
  });

  it('does not cross-match a Greek-work id\'s query against the Latin fold', async () => {
    // A work id NOT recognized as Latin by the mock (falls through to the
    // real registry, unregistered -> defaults to 'grc') must still use
    // greekFold, not latinFold -- "vita" under greekFold folds to a
    // different key than under latinFold (proving the two fold functions
    // are genuinely distinct, not just aliases), so it must not spuriously
    // hit an unrelated Greek-indexed work.
    expect(greekFold('vita')).not.toBe(latinFold('vita'));
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(greekIndex);
      if (path.endsWith('/english.json')) return json(englishIndex);
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
    const hits = await search('vita', '', 'all', 'all', 'and', ['TGreekUnaffected']);
    expect(hits).toEqual([]);
  });
});

// John, 2026-09-23 ruling: the search page's default Lemma mode must accept
// a word AS PRINTED (e.g. Πᾶσα / folded "pasa"), not just its headword
// (πᾶς / "pas") — lemma.json is keyed by folded headword only. These tests
// use SEPARATE lemma.json/form.json fixtures (unlike the describe('search')
// block above, which reuses one `greekIndex` for both — that reuse is what
// hid this bug: a lemma-mode lookup of a surface-only key against form.json
// would have "worked" there only because form.json and lemma.json were the
// same object).
describe('search — Lemma mode resolves a printed form via form_lemmata.json', () => {
  const meta = [
    { id: 'm1', book: 1, column: '1094a', head: 'Pasa texnh', tokens: 'pas texnh', english_head: 'every art' },
    { id: 'm2', book: 1, column: '2', head: 'ambig', tokens: 'foo', english_head: '' },
    { id: 'm3', book: 1, column: '3', head: 'ambig', tokens: 'bar', english_head: '' },
  ];
  // lemma.json: keyed by headword fold.
  const lemmaIdx = {
    pas: [[0, 0]],
    texnh: [[0, 1]],
    foo: [[1, 0]],
    bar: [[2, 0]],
  } satisfies Record<string, [number, number][]>;
  // form.json: keyed by surface fold — deliberately DIFFERENT from lemmaIdx,
  // so a test that accidentally hit the wrong file would fail loudly.
  const formIdx = {
    pasa: [[0, 0]],
    texnh: [[0, 1]],
    ambig: [[1, 0], [2, 0]],
  } satisfies Record<string, [number, number][]>;
  // form_lemmata.json: "pasa" differs from its headword "pas" (mapped);
  // "texnh" is omitted (surface == headword, per stage6_search.py's rule);
  // "ambig" is genuinely ambiguous and lists both headwords.
  const formLemmata = {
    pasa: ['pas'],
    ambig: ['foo', 'bar'],
  } satisfies Record<string, string[]>;

  function mockFetch() {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json')) return json(lemmaIdx);
      if (path.endsWith('/form.json')) return json(formIdx);
      if (path.endsWith('/form_lemmata.json')) return json(formLemmata);
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  }

  beforeEach(mockFetch);
  afterEach(() => vi.restoreAllMocks());

  it('Lemma mode: typing the printed form finds the headword\'s postings', async () => {
    const hits = await search('pasa', '', 'all', 'all', 'and', ['TLemForm'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
  });

  it('Lemma mode: typing the headword itself is unchanged', async () => {
    const hits = await search('pas', '', 'all', 'all', 'and', ['TLemHead'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
  });

  it('Lemma mode: an ambiguous printed form unions every headword it maps to', async () => {
    const hits = await search('ambig', '', 'all', 'all', 'and', ['TLemAmbig'], 'lemma');
    expect(hits.map((r) => r.meta.id).sort()).toEqual(['m2', 'm3']);
  });

  it('Exact/Form mode: typing the printed form is unchanged (direct form.json hit)', async () => {
    const hits = await search('pasa', '', 'all', 'all', 'and', ['TFormForm'], 'form');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
  });

  it('Exact/Form mode: typing the headword does NOT match the inflected form (map not consulted)', async () => {
    const hits = await search('pas', '', 'all', 'all', 'and', ['TFormHead'], 'form');
    expect(hits).toEqual([]);
  });

  it('wildcard queries are unaffected: a prefix that is not itself a lemma.json key still misses', async () => {
    // "pasa*" folds to prefix "pasa", which is not a KEY of lemma.json (only
    // "pas" is) — the map must not be consulted for a wildcard term, so this
    // must still miss exactly as it did before form_lemmata.json existed.
    const hits = await search('pasa*', '', 'all', 'all', 'and', ['TLemWildcardMiss'], 'lemma');
    expect(hits).toEqual([]);
  });

  it('wildcard queries still match by lemma.json key prefix as before', async () => {
    const hits = await search('pa*', '', 'all', 'all', 'and', ['TLemWildcardHit'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
  });

  // Ruling item 1 (2026-09-23): phrase mode must resolve each typed word
  // through the same headword rule before checking adjacency — m1's
  // meta.tokens is 'pas texnh' (headword folds), so a phrase typed with a
  // printed first word ("Pasa") has to resolve to "pas" before the adjacency
  // check runs, or it silently misses despite each term's posting lookup
  // succeeding on its own.
  it('Phrase mode: a phrase with a printed first word finds the passage', async () => {
    const hits = await search('Pasa texnh', '', 'phrase', 'all', 'and', ['TLemPhrasePrinted'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
    // m1's meta.tokens is 'pas texnh' -- the printed first word ("Pasa")
    // must resolve through form_lemmata.json to headword "pas" for the
    // HIGHLIGHT positions too, not just the hit/miss check: a token-position
    // regression (e.g. falling back to the raw typed fold) would still find
    // the segment via phraseMatches() but highlight the wrong tokens or none.
    expect(hits[0].grkPositions).toEqual([0, 1]);
  });

  it('Phrase mode: a headword phrase is unchanged', async () => {
    const hits = await search('pas texnh', '', 'phrase', 'all', 'and', ['TLemPhraseHead'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
    expect(hits[0].grkPositions).toEqual([0, 1]);
  });
});

// Ruling item 2 (2026-09-23): headword precedence. Mirrors the real
// Heraclitus case Sol flagged — "hmera" is itself a lemma.json headword key
// (day) AND is separately listed in form_lemmata.json as a printed SURFACE
// form of a different headword "hmeros" (tame/gentle). "Always union" (the
// pre-fix behavior) would add "hmeros"'s postings too; the ruling says a
// typed fold that is ALREADY a headword key must use exactly the old direct
// lookup and never consult the map.
describe('search — Lemma mode: headword precedence over form_lemmata.json', () => {
  const meta = [
    { id: 'd1', book: 1, column: '1', head: 'hmera', tokens: 'hmera', english_head: '' },
    { id: 'd2', book: 1, column: '2', head: 'hmeros', tokens: 'hmeros', english_head: '' },
  ];
  const lemmaIdx = {
    hmera: [[0, 0]],
    hmeros: [[1, 0]],
  } satisfies Record<string, [number, number][]>;
  // "hmera" differs from the OTHER headword "hmeros" it's listed under, so
  // stage6_search.py's omission rule (sf not in lemmata) keeps this entry —
  // it is not itself a self-mapping, just a coincidental key collision with
  // an unrelated headword.
  const formLemmata = { hmera: ['hmeros'] } satisfies Record<string, string[]>;

  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(lemmaIdx);
      if (path.endsWith('/form_lemmata.json')) return json(formLemmata);
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('a Lemma search for the headword returns exactly its own postings', async () => {
    const hits = await search('hmera', '', 'all', 'all', 'and', ['THeadwordPrecedence'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['d1']);
  });
});

// Ruling item 4 (2026-09-23): a work with no form_lemmata.json (mounted
// sibling corpus, or a build predating this file) 404s once, and that
// absence should be remembered — not re-fetched on every subsequent search
// of the same work. A transient failure (network error / 5xx) must still be
// retried, so only the 404 case is cached.
describe('search — form_lemmata.json fetch caching (ruling item 4)', () => {
  const meta = [
    { id: 'm1', book: 1, column: '1', head: 'texnh', tokens: 'texnh', english_head: '' },
  ];
  const lemmaIdx = { texnh: [[0, 0]] } satisfies Record<string, [number, number][]>;

  afterEach(() => vi.restoreAllMocks());

  it('a 404 is fetched once, not on every subsequent search of the same work', async () => {
    let mapCalls = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(lemmaIdx);
      if (path.endsWith('/form_lemmata.json')) {
        mapCalls++;
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
      }
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
    await search('texnh', '', 'all', 'all', 'and', ['T404Cache'], 'lemma');
    await search('texnh', '', 'all', 'all', 'and', ['T404Cache'], 'lemma');
    expect(mapCalls).toBe(1);
  });

  it('a transient failure (5xx) is retried on the next search', async () => {
    let mapCalls = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(lemmaIdx);
      if (path.endsWith('/form_lemmata.json')) {
        mapCalls++;
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) } as Response);
      }
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
    await search('texnh', '', 'all', 'all', 'and', ['T500Retry'], 'lemma');
    await search('texnh', '', 'all', 'all', 'and', ['T500Retry'], 'lemma');
    expect(mapCalls).toBe(2);
  });
});

// A work whose search index predates form_lemmata.json (or a mounted
// sibling corpus that doesn't emit it) must not have its Lemma-mode search
// break outright — the missing file should fall back to "no map" instead of
// failing the whole work.
describe('search — Lemma mode tolerates a missing form_lemmata.json', () => {
  const meta = [
    { id: 'm1', book: 1, column: '1094a', head: 'texnh', tokens: 'texnh', english_head: 'art' },
  ];
  const lemmaIdx = { texnh: [[0, 0]] } satisfies Record<string, [number, number][]>;

  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(lemmaIdx);
      if (path.endsWith('/form_lemmata.json')) {
        return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
      }
      if (path.endsWith('/english.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('a direct headword query still succeeds when form_lemmata.json 404s', async () => {
    const hits = await search('texnh', '', 'all', 'all', 'and', ['TMissingMap'], 'lemma');
    expect(hits.map((r) => r.meta.id)).toEqual(['m1']);
  });
});

describe('englishOccurrences', () => {
  it('returns one offset per matching token (repeats counted)', () => {
    // #11: "socrates" three times -> three offsets, not one.
    const text = 'Socrates asked; then Socrates replied, and Socrates smiled.';
    expect(englishOccurrences(text, ['socrates'], 'all')).toHaveLength(3);
  });

  it('finds a phrase whose occurrence is past the old 500-char cap', () => {
    // #5: the phrase sits well beyond character 500; token-based matching still finds it.
    const filler = 'word '.repeat(200);           // ~1000 chars
    const text = `${filler}you shall avail yourself of it`;
    const offs = englishOccurrences(text, ['shall', 'avail'], 'phrase');
    expect(offs).toHaveLength(1);
    expect(offs[0]).toBeGreaterThan(500);
  });

  it('matches whole tokens and prefix wildcards, not substrings', () => {
    const text = 'virtue and virtues and virtuous';
    expect(englishOccurrences(text, ['virtue'], 'all')).toHaveLength(1);   // not "virtues"/"virtuous"
    expect(englishOccurrences(text, ['virtu*'], 'all')).toHaveLength(3);   // prefix hits all three
  });
});

describe('search English occurrences (index integration)', () => {
  const longText = `${'filler word '.repeat(60)}the crux is that one shall avail nothing`;
  const engMeta = [
    { id: 's1', book: 1, column: '406a', head: '', tokens: '', english_head: longText },
  ];
  const engIndex = { shall: [0], avail: [0], filler: [0], word: [0], the: [0] };
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(engMeta);
      if (path.endsWith('/english.json')) return json(engIndex);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json({});
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it('phrase past char 500 is found (regression for the [:500] truncation)', async () => {
    const idx = longText.toLowerCase().indexOf('shall avail');
    expect(idx).toBeGreaterThan(500);
    const hits = await search('', 'shall avail', 'all', 'phrase', 'and', ['TEng500']);
    expect(hits).toHaveLength(1);
    expect(hits[0].engPositions).toEqual([idx]);
  });

  it('counts repeated English occurrences per segment', async () => {
    const hits = await search('', 'word', 'all', 'all', 'and', ['TEngCount']);
    expect(hits).toHaveLength(1);
    // "word" appears 60 times in the filler.
    expect(hits[0].engPositions).toHaveLength(60);
  });
});

// PUBLIC_DATA_ROOT mirrors data.ts's build-time root override (see
// data.test.ts's matching describe block) — search.ts derives its own
// DEFAULT_ROOT independently, so it needs its own coverage.
describe('PUBLIC_DATA_ROOT build-time root override', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.restoreAllMocks();
  });

  it('prefixes every index fetch with PUBLIC_DATA_ROOT when set', async () => {
    vi.stubEnv('PUBLIC_DATA_ROOT', 'https://data.example.com/v1/');
    vi.resetModules();
    const fresh = await import('../lib/search');
    const urls: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      urls.push(String(url));
      const path = String(url);
      if (path.endsWith('/meta.json')) return json(meta);
      if (path.endsWith('/lemma.json') || path.endsWith('/form.json')) return json(greekIndex);
      if (path.endsWith('/english.json')) return json(englishIndex);
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) } as Response);
    });
    await fresh.search('logos', '', 'all', 'all', 'and', ['TRoot']);
    expect(urls.length).toBeGreaterThan(0);
    expect(urls.every((u) => u.startsWith('https://data.example.com/v1/TRoot/search/'))).toBe(true);
  });
});
