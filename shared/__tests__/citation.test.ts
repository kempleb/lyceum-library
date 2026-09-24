import { describe, expect, it, vi } from 'vitest';

// schemeFor reads works.ts' citation.scheme; a busse-scheme work is no longer
// in the real registry (Plato-only now), so a fixture meta stands in for one
// rather than depending on a real registry entry.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  interface Meta {
    id: string;
    abbr: string;
    title?: string;
    citation?: {
      scheme: string;
      copyAbbr?: string;
      lines?: boolean;
      series?: 'A' | 'B';
      noSeries?: boolean;
      dkChapter?: number;
    };
  }
  const metas: Record<string, Meta> = {
    EN: { id: 'EN', abbr: 'EN' }, // no citation field -> default bekker
    BusseWork: { id: 'BusseWork', abbr: 'Busse', citation: { scheme: 'busse' } },
    Marcus: { id: 'Marcus', abbr: 'M.Ant.', citation: { scheme: 'book-section', copyAbbr: 'M.Ant.' } },
    NoAbbrWork: { id: 'NoAbbrWork', abbr: 'NAW', citation: { scheme: 'book-section' } }, // no copyAbbr -> falls back to abbr
    Epictetus: { id: 'Epictetus', abbr: 'Ench.', citation: { scheme: 'section', copyAbbr: 'Epict. Ench.' } },
    Heraclitus: {
      id: 'Heraclitus', abbr: 'Her.', title: 'Fragments',
      citation: { scheme: 'dk', copyAbbr: 'DK 22', series: 'B', dkChapter: 22 },
    },
    HeraclitusTestimonia: {
      id: 'HeraclitusTestimonia', abbr: 'Her. A', title: 'Testimonia',
      citation: { scheme: 'dk', copyAbbr: 'DK 22', series: 'A', dkChapter: 22 },
    },
    Parmenides: {
      id: 'Parmenides', abbr: 'Parm.', title: 'Fragments',
      citation: { scheme: 'dk', copyAbbr: 'DK 28', lines: true, series: 'B', dkChapter: 28 },
    },
    Pythagoras: {
      id: 'Pythagoras', abbr: 'Pyth.', title: 'Testimonia',
      // DK 14 is printed with NO series letter at all — copyAbbr carries its
      // own trailing comma so formatCopyCitation's `${prefix} ${column}` join
      // comes out "DK 14, 7" with zero extra machinery (see formatCopyCitation).
      // The real pythagoras-testimonia work: NO series letter AND it records
      // ancient reports ABOUT Pythagoras, not his own surviving words — the
      // title ('Testimonia') is the only signal that distinguishes it from a
      // fragments work once `series` is absent (finding 1, Sol review).
      citation: { scheme: 'dk', copyAbbr: 'DK 14,', noSeries: true, dkChapter: 14 },
    },
    PythagorasUnclassifiable: {
      id: 'PythagorasUnclassifiable', abbr: 'PU',
      // No title, no series at all — must NOT default to "fragment" (that
      // would assert a false scholarly claim); falls back to a neutral noun.
      citation: { scheme: 'dk', copyAbbr: 'DK 99', noSeries: true, dkChapter: 99 },
    },
    Lucretius: {
      id: 'Lucretius', abbr: 'Lucr.',
      citation: { scheme: 'verse-line', copyAbbr: 'Lucr.' },
    },
    Seneca: {
      id: 'Seneca', abbr: 'Ep.',
      citation: { scheme: 'letter', copyAbbr: 'Sen. Ep.' },
    },
    // No stephanus work is in the real registry yet either (Plato hasn't
    // landed) — a fixture stands in, same rationale as BusseWork above, so
    // unitNounFor/CitationScheme.label stay tested for the scheme Aristotle
    // and Plato will need when they arrive (REVIEW-CHECKLIST item 34).
    StephanusWork: {
      id: 'StephanusWork', abbr: 'Steph.',
      citation: { scheme: 'stephanus', copyAbbr: 'Steph.' },
    },
    // No ennead work is in the real registry yet (Plotinus is a planned
    // addition) — a fixture stands in, same rationale as BusseWork/
    // StephanusWork above, so unitNounFor already resolves the right noun
    // when Plotinus lands (finding 5, Sol review).
    EnneadWork: {
      id: 'EnneadWork', abbr: 'Enn.',
      citation: { scheme: 'ennead', copyAbbr: 'Enn.' },
    },
  };
  const byDkChapterSeries = new Map<string, Meta>();
  const byDkChapterNoSeries = new Map<number, Meta>();
  for (const m of Object.values(metas)) {
    if (m.citation?.scheme === 'dk' && m.citation.dkChapter != null && m.citation.series) {
      byDkChapterSeries.set(`${m.citation.dkChapter}:${m.citation.series}`, m);
    }
    if (m.citation?.scheme === 'dk' && m.citation.dkChapter != null && m.citation.noSeries) {
      byDkChapterNoSeries.set(m.citation.dkChapter, m);
    }
  }
  return {
    ...actual,
    getWork: (id: string) => metas[id] ?? (actual.getWork(id) as unknown),
    workByDkCitation: (dkChapter: number, series: 'A' | 'B') =>
      byDkChapterSeries.get(`${dkChapter}:${series}`) ?? actual.workByDkCitation(dkChapter, series),
    workByDkChapterNoSeries: (dkChapter: number) =>
      byDkChapterNoSeries.get(dkChapter) ?? actual.workByDkChapterNoSeries(dkChapter),
  };
});

import {
  dottedSectionChapter,
  formatCite,
  formatCopyCitation,
  formatHash,
  formatLocValue,
  groupUnitNoun,
  isVerseLineRange,
  navChipsNeedFullSectionList,
  nounForCount,
  pageEntriesFor,
  parseDkFullCitation,
  scheme,
  schemeFor,
  unitNounFor,
  verseLineOrderKey,
} from '../lib/citation';

describe('per-scheme contract', () => {
  it('exposes the three scheme ids with the right line policy', () => {
    expect(scheme('bekker').id).toBe('bekker');
    expect(scheme('bekker').hasUserFacingLines).toBe(true);
    expect(scheme('busse').id).toBe('busse');
    expect(scheme('busse').hasUserFacingLines).toBe(true);
    expect(scheme('stephanus').id).toBe('stephanus');
    expect(scheme('stephanus').hasUserFacingLines).toBe(false);
  });

  it('defaults an omitted/empty scheme id to bekker', () => {
    expect(scheme(undefined).id).toBe('bekker');
    expect(scheme(null).id).toBe('bekker');
    expect(scheme('').id).toBe('bekker');
  });

  it('throws a clear Error for an unknown non-empty scheme id, matching scheme.py\'s KeyError instead of silently falling back to bekker', () => {
    expect(() => scheme('not-a-scheme')).toThrow(/unknown citation scheme/);
  });

  it('hasSections is true for stephanus, book-section, letter, the flat section scheme, and dk — mirrors scheme.py\'s Scheme.has_sections', () => {
    expect(scheme('stephanus').hasSections).toBe(true);
    expect(scheme('book-section').hasSections).toBe(true);
    // letter (Seneca's Epistulae, Wave 2 Batch 3) is book-section-shaped —
    // has_sections derives true the same way.
    expect(scheme('letter').hasSections).toBe(true);
    expect(scheme('section').hasSections).toBe(true);
    expect(scheme('dk').hasSections).toBe(true);
    expect(scheme('bekker').hasSections).toBe(false);
    expect(scheme('busse').hasSections).toBe(false);
    // A verse-line book runs to ~1000+ lines — a per-line outline nav would
    // be unusable, so this scheme (implemented, not a stub) is also false.
    expect(scheme('verse-line').hasSections).toBe(false);
    // ennead is the one remaining stub scheme.
    expect(scheme('ennead').hasSections).toBe(false);
  });

  it('schemeFor reads works.ts citation.scheme and defaults to bekker', () => {
    expect(schemeFor('EN').id).toBe('bekker');       // no citation field -> default
    expect(schemeFor('BusseWork').id).toBe('busse');  // citation: { scheme: 'busse', ... }
    expect(schemeFor('NoSuchWork').id).toBe('bekker'); // unknown work -> default
  });
});

// ReaderShell.astro's "Pages"/"Sections" nav-row chip source (task #35's
// workaround — a numeric-section scheme's (book-section, letter) per-section
// `page` is constant at the book/letter number, so pagesOf's dedup collapses
// a whole book/letter to one row/chip; the nav instead lists sectionsOf(book)
// directly for these two schemes).
describe('navChipsNeedFullSectionList', () => {
  it('is true for book-section and letter — the two numeric-section schemes whose pagesOf output collapses', () => {
    expect(navChipsNeedFullSectionList('book-section')).toBe(true);
    expect(navChipsNeedFullSectionList('letter')).toBe(true);
  });

  it('is false for every other hasSections scheme, whose pagesOf output is already correct', () => {
    expect(navChipsNeedFullSectionList('stephanus')).toBe(false);
    expect(navChipsNeedFullSectionList('section')).toBe(false);
    expect(navChipsNeedFullSectionList('dk')).toBe(false);
  });

  it('is false for schemes with no section outline at all', () => {
    expect(navChipsNeedFullSectionList('bekker')).toBe(false);
    expect(navChipsNeedFullSectionList('busse')).toBe(false);
  });
});

// Finding 3 (Sol review): ReaderShell.astro's TOC drawer and Landing.astro's
// per-book row both counted a book-section work's sections by deduping on
// `page` — which is constant across the whole book for book-section/letter
// — so a 51-section book (Marcus Aurelius Meditations IV) rendered "1
// section" instead of "51 sections". Consolidates what used to be two
// independently-duplicated (and diverging) dedup implementations.
describe('pageEntriesFor', () => {
  const secs = [
    { page: 4, column: '4.1' },
    { page: 4, column: '4.2' },
    { page: 4, column: '4.3' },
  ];

  it('book-section: returns every section — page is constant across the book, so a naive dedup would collapse them', () => {
    expect(pageEntriesFor('book-section', secs)).toHaveLength(3);
    expect(pageEntriesFor('book-section', secs).map((s) => s.column)).toEqual(['4.1', '4.2', '4.3']);
  });

  it('letter: same full-list treatment as book-section', () => {
    expect(pageEntriesFor('letter', secs)).toHaveLength(3);
  });

  it('stephanus: dedups by page — several sections legitimately share one Stephanus page', () => {
    const stephSecs = [
      { page: 34, column: '34a' },
      { page: 34, column: '34b' },
      { page: 35, column: '35a' },
    ];
    expect(pageEntriesFor('stephanus', stephSecs)).toEqual([
      { page: 34, column: '34a' },
      { page: 35, column: '35a' },
    ]);
  });

  it('dk: dedups by page too — each fragment already has its own distinct page ordinal', () => {
    const dkSecs = [{ page: 1, column: 'B10' }, { page: 2, column: 'B81' }];
    expect(pageEntriesFor('dk', dkSecs)).toEqual(dkSecs);
  });
});

// Finding 4 (Sol review): ReaderShell.astro's TOC drawer always rendered
// unitNounFor's plural, even for a count of 1 ("1 chapters" for a
// single-chapter book).
describe('nounForCount', () => {
  it('a count of 1 uses the singular noun', () => {
    expect(nounForCount('EN', 1)).toBe('chapter');
    expect(nounForCount('Marcus', 1)).toBe('section');
  });

  it('any other count uses the plural noun', () => {
    expect(nounForCount('EN', 0)).toBe('chapters');
    expect(nounForCount('EN', 2)).toBe('chapters');
    expect(nounForCount('Marcus', 51)).toBe('sections');
  });
});

describe('dottedSectionChapter', () => {
  it('strips a book-section column down to its bare chapter component', () => {
    expect(dottedSectionChapter('4.23')).toBe('23');
    expect(dottedSectionChapter('12.34')).toBe('34'); // multi-digit book AND section
    expect(dottedSectionChapter('7.85')).toBe('85');  // Diogenes Laertius-shaped
  });

  it('returns a non-dotted column unchanged rather than guessing', () => {
    expect(dottedSectionChapter('34b')).toBe('34b');   // stephanus/bekker-style
    expect(dottedSectionChapter('B30')).toBe('B30');   // dk-style
    expect(dottedSectionChapter('5')).toBe('5');       // flat `section`-scheme
  });
});

describe('parseColumnToken', () => {
  it.each([
    ['1097a', '1097a'],
    ['1097A', '1097a'],
    [' 1097a ', '1097a'],
    ['1097f', null],   // outside a-e
    ['1097a15', null], // a column token, not a ref (has a trailing line)
    ['abc', null],
  ])('bekker parses %s -> %s', (raw, expected) => {
    expect(scheme('bekker').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['34b', '34b'],
    ['34B', '34b'],
    ['34c', '34c'], // stephanus letters run a-e
    ['34e', '34e'],
    ['34f', null],
  ])('stephanus parses %s -> %s', (raw, expected) => {
    expect(scheme('stephanus').parseColumnToken(raw)).toBe(expected);
  });
});

describe('parseLocation', () => {
  describe('a scheme with user-facing lines (bekker)', () => {
    const s = scheme('bekker');
    it.each([
      ['1097a', { column: '1097a', line: null }],       // bare column
      ['1097a:15', { column: '1097a', line: 15 }],       // location-query grammar
      ['1097a15', { column: '1097a', line: 15 }],        // legacy concatenated citation
      ['1097a 15', { column: '1097a', line: 15 }],
      ['1097A.15', { column: '1097a', line: 15 }],
      ['1097c15', { column: '1097c', line: 15 }],        // widened a-e grammar
      ['not a citation', null],
      ['1097f15', null],
      ['', null],
    ])('%s -> %o', (raw, expected) => {
      expect(s.parseLocation(raw)).toEqual(expected);
    });
  });

  describe('a scheme with no user-facing lines (stephanus)', () => {
    const s = scheme('stephanus');
    it.each([
      ['17a', { column: '17a', line: null }],  // bare column: the only valid citation shape
      ['34b', { column: '34b', line: null }],
      ['34b12', null],   // a fixed KNOWN DEFECT case: reject, don't silently truncate
      ['34b:12', null],  // same rejection via the query-grammar's colon form
      ['not a citation', null],
    ])('%s -> %o', (raw, expected) => {
      expect(s.parseLocation(raw)).toEqual(expected);
    });
  });

  it('never returns a line of undefined/NaN for a column-only value (the L{col}-undefined bug)', () => {
    for (const id of ['bekker', 'busse', 'stephanus'] as const) {
      const parsed = scheme(id).parseLocation('17a');
      expect(parsed).not.toBeNull();
      expect(parsed!.line).toBeNull();
    }
  });
});

describe('formatCitation', () => {
  it('bekker/busse render column+line concatenated, or bare column with no line', () => {
    expect(scheme('bekker').formatCitation('1097a', 15)).toBe('1097a15');
    expect(scheme('bekker').formatCitation('1097a', null)).toBe('1097a');
    expect(scheme('bekker').formatCitation('1097a')).toBe('1097a');
  });

  it('stephanus always renders the bare section token, even if a line is passed', () => {
    expect(scheme('stephanus').formatCitation('17a')).toBe('17a');
    expect(scheme('stephanus').formatCitation('17a', 12)).toBe('17a');
  });
});

describe('work-level convenience composers', () => {
  it('formatCite/formatHash follow the work\'s scheme', () => {
    expect(formatCite('EN', '1097a', 15)).toBe('1097a15');
    expect(formatHash('EN', '1097a', 15)).toBe('#1097a15');
    expect(formatCite('BusseWork', '1a', 5)).toBe('1a5');
  });

  it('formatLocValue emits the colon form when a scheme has lines, else the bare column', () => {
    expect(formatLocValue('EN', '1097a', 15)).toBe('1097a:15');
    expect(formatLocValue('EN', '1097a', null)).toBe('1097a');
    expect(formatLocValue('EN', '1097a')).toBe('1097a');
  });
});

describe('book-section scheme (dotted book.section grammar)', () => {
  it('exposes the id with no user-facing lines', () => {
    expect(scheme('book-section').id).toBe('book-section');
    expect(scheme('book-section').hasUserFacingLines).toBe(false);
  });

  it.each([
    ['4.23', '4.23'],   // Marcus Aurelius
    ['12.1', '12.1'],
    [' 4.23 ', '4.23'],
  ])('parseColumnToken round-trips %s -> %s', (raw, expected) => {
    expect(scheme('book-section').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['4.x', null],   // section must be digits
    ['4.', null],    // no section
    ['a.23', null],  // book must be digits
    ['4a', null],    // not dotted at all — bekker-style letter grammar
  ])('parseColumnToken rejects %s', (raw, expected) => {
    expect(scheme('book-section').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['4.23', { column: '4.23', line: null }],
    ['12.1', { column: '12.1', line: null }],
    ['4.x', null],
    ['4.', null],
    ['a.23', null],
    ['4a', null],
    ['4.23:5', null], // no user-facing lines -> a line component is rejected
    ['', null],
  ])('parseLocation %s -> %o', (raw, expected) => {
    expect(scheme('book-section').parseLocation(raw)).toEqual(expected);
  });

  it('formatCitation renders the bare dotted column, ignoring any line', () => {
    expect(scheme('book-section').formatCitation('4.23')).toBe('4.23');
    expect(scheme('book-section').formatCitation('4.23', 5)).toBe('4.23');
  });

  it('round-trips through parseColumnToken -> formatCitation unchanged', () => {
    for (const raw of ['4.23', '12.1']) {
      const col = scheme('book-section').parseColumnToken(raw)!;
      expect(scheme('book-section').formatCitation(col)).toBe(raw);
    }
  });

  it('formatHash/formatLocValue follow the dotted grammar for a book-section work', () => {
    expect(formatCite('Marcus', '4.23')).toBe('4.23');
    expect(formatHash('Marcus', '4.23')).toBe('#4.23');
    expect(formatLocValue('Marcus', '4.23')).toBe('4.23');
  });
});

// letter (Seneca's Epistulae Morales, Wave 2 Batch 3 — design memo
// docs/wave2-seneca-design.md §A): byte-identical dotted grammar to
// book-section (letter = page axis, section = column, "47.3"), reused
// wholesale via makeDottedScheme rather than a new factory.
describe('letter scheme (dotted letter.section grammar — Seneca Epistulae Morales)', () => {
  it('exposes the id with no user-facing lines and the section outline', () => {
    expect(scheme('letter').id).toBe('letter');
    expect(scheme('letter').hasUserFacingLines).toBe(false);
    expect(scheme('letter').hasSections).toBe(true);
  });

  it.each([
    ['47.3', '47.3'],
    ['124.1', '124.1'],   // the last real letter (fr appendix excluded, §D)
    [' 47.3 ', '47.3'],
  ])('parseColumnToken round-trips %s -> %s', (raw, expected) => {
    expect(scheme('letter').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['47.x', null],  // section must be digits
    ['47.', null],   // no section
    ['a.3', null],   // letter must be digits
    ['47a', null],   // not dotted at all — bekker-style letter grammar
    ['3', null],     // bare column — no letterless form (design memo §A.3)
  ])('parseColumnToken rejects %s', (raw, expected) => {
    expect(scheme('letter').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['47.3', { column: '47.3', line: null }],
    ['124.1', { column: '124.1', line: null }],
    ['47.x', null],
    ['47.', null],
    ['a.3', null],
    ['47a', null],
    ['47:3', null],   // no user-facing lines -> a colon/line form is rejected (design memo §A.3)
    ['3', null],
    ['', null],
  ])('parseLocation %s -> %o', (raw, expected) => {
    expect(scheme('letter').parseLocation(raw)).toEqual(expected);
  });

  it('formatCitation renders the bare dotted column, ignoring any line', () => {
    expect(scheme('letter').formatCitation('47.3')).toBe('47.3');
    expect(scheme('letter').formatCitation('47.3', 5)).toBe('47.3');
  });

  it('round-trips through parseColumnToken -> formatCitation unchanged', () => {
    for (const raw of ['47.3', '124.1']) {
      const col = scheme('letter').parseColumnToken(raw)!;
      expect(scheme('letter').formatCitation(col)).toBe(raw);
    }
  });

  it('bookFromColumn derives the letter directly from the dotted prefix, like book-section', () => {
    expect(scheme('letter').bookFromColumn('47.3')).toBe(47);
    expect(scheme('letter').bookFromColumn('124.1')).toBe(124);
    expect(scheme('letter').bookFromColumn('47a')).toBeNull();
    expect(scheme('letter').bookFromColumn('')).toBeNull();
  });

  it('formatHash/formatLocValue follow the dotted grammar for a letter work', () => {
    expect(formatCite('Seneca', '47.3')).toBe('47.3');
    expect(formatHash('Seneca', '47.3')).toBe('#47.3');
    expect(formatLocValue('Seneca', '47.3')).toBe('47.3');
  });

  it('formatCopyCitation composes "Sen. Ep. <letter>.<section>"', () => {
    expect(formatCopyCitation('Seneca', '47.3')).toBe('Sen. Ep. 47.3');
  });

  // TS/Python grammar parity: the SAME case list as test_scheme.py's
  // test_letter_grammar_parity_with_citation_ts_valid/_malformed.
  it.each(['47.3', '124.1', '1.1', '7.85'])(
    'grammar parity with scheme.py: %s is a valid letter column',
    (tok) => {
      expect(scheme('letter').parseColumnToken(tok)).toBe(tok);
    },
  );
  it.each(['47.3.5', '47.', '.3', '47a', '3', '', 'a.3'])(
    'grammar parity with scheme.py (malformed): %s is rejected',
    (tok) => {
      expect(scheme('letter').parseColumnToken(tok)).toBeNull();
    },
  );
});

describe('section scheme (flat, bookless chapter-integer grammar)', () => {
  it('exposes the id with no user-facing lines', () => {
    expect(scheme('section').id).toBe('section');
    expect(scheme('section').hasUserFacingLines).toBe(false);
  });

  it.each([
    ['5', '5'],
    ['1', '1'],
    ['10', '10'],
    [' 5 ', '5'],
  ])('parseColumnToken round-trips %s -> %s', (raw, expected) => {
    expect(scheme('section').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['1.5', null],   // dotted book-section grammar — rejected by this scheme
    ['5a', null],    // bekker-style letter grammar — rejected
    ['5.', null],
    ['', null],
    ['abc', null],
  ])('parseColumnToken rejects %s', (raw, expected) => {
    expect(scheme('section').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['5', { column: '5', line: null }],
    ['1', { column: '1', line: null }],
    ['1.5', null],    // dotted — REJECTED by this scheme's grammar
    ['5a', null],
    ['5:1', null],    // no user-facing lines -> a line component is rejected
    ['', null],
  ])('parseLocation %s -> %o', (raw, expected) => {
    expect(scheme('section').parseLocation(raw)).toEqual(expected);
  });

  it('formatCitation renders the bare chapter integer, ignoring any line', () => {
    expect(scheme('section').formatCitation('5')).toBe('5');
    expect(scheme('section').formatCitation('5', 12)).toBe('5');
  });

  it('bookFromColumn is always null — the work is bookless (a single declared book)', () => {
    expect(scheme('section').bookFromColumn('5')).toBeNull();
    expect(scheme('section').bookFromColumn('1')).toBeNull();
  });

  it('round-trips through parseColumnToken -> formatCitation unchanged, including a ⌘K-style bare jump', () => {
    for (const raw of ['5', '1', '10']) {
      const col = scheme('section').parseColumnToken(raw)!;
      expect(scheme('section').formatCitation(col)).toBe(raw);
      // parseLocation accepts the same bare token a jump box would submit.
      expect(scheme('section').parseLocation(raw)).toEqual({ column: raw, line: null });
    }
  });

  it('formatHash/formatLocValue follow the flat grammar for a section-scheme work', () => {
    expect(formatCite('Epictetus', '5')).toBe('5');
    expect(formatHash('Epictetus', '5')).toBe('#5');
    expect(formatLocValue('Epictetus', '5')).toBe('5');
  });

  // TS/Python flat grammar parity: the SAME case list as test_refs.py's
  // test_section_grammar_parity_with_citation_ts. ASCII digits only, outer
  // whitespace trimmed, internal whitespace REJECTED (never collapsed into a
  // different number — the shared normalize() would turn "5 0" into "50"),
  // Unicode digits rejected.
  it.each([
    ['5', '5'],       // bare chapter
    [' 5 ', '5'],     // outer whitespace trimmed
    ['5 0', null],    // internal whitespace REJECTED, not collapsed to "50"
    ['٥', null],      // Unicode (Arabic-Indic) digit rejected
    ['05', '05'],     // leading zero accepted
    ['', null],
  ])('flat grammar parity with scheme.py: %j -> %j', (raw, expected) => {
    expect(scheme('section').parseColumnToken(raw)).toBe(expected);
    expect(scheme('section').parseLocation(raw)).toEqual(
      expected === null ? null : { column: expected, line: null },
    );
  });

  // Epicurus' Vatican Sayings (TLG 0537:014) carries exactly one div whose
  // own @n is a compound "56-57" — one atomic saying spanning two
  // traditional numbers, not a range-gap marker (see
  // manifests/epicurus-vatican-sayings.yaml and scheme.py's matching
  // `_FLAT_COLUMN_RE` comment for why it's safe to sort on the leading
  // number alone).
  it.each([
    ['56-57', '56-57'],
    ['5-', null],
    ['-5', null],
    ['5-5-5', null],
  ])('accepts the one Epicurus compound token, rejects malformed hyphenation: %j -> %j', (raw, expected) => {
    expect(scheme('section').parseColumnToken(raw)).toBe(expected);
  });
});

describe('bookFromColumn — recovering a book without a columns.json lookup', () => {
  it('book-section derives the book directly from the dotted prefix, including multi-digit books', () => {
    expect(scheme('book-section').bookFromColumn('4.23')).toBe(4);
    expect(scheme('book-section').bookFromColumn('12.34')).toBe(12); // multi-digit book AND section
    expect(scheme('book-section').bookFromColumn('7.85')).toBe(7);   // Diogenes Laertius-shaped
  });

  it('book-section rejects a malformed/non-dotted column rather than guessing', () => {
    expect(scheme('book-section').bookFromColumn('4a')).toBeNull();   // bekker-style, not dotted
    expect(scheme('book-section').bookFromColumn('4.')).toBeNull();
    expect(scheme('book-section').bookFromColumn('a.23')).toBeNull();
    expect(scheme('book-section').bookFromColumn('')).toBeNull();
  });

  it('bekker/busse/stephanus return null — their column can span/be shared by two books, so only a columns.json lookup (resolveBekker) can resolve it', () => {
    expect(scheme('bekker').bookFromColumn('1097a')).toBeNull();
    expect(scheme('busse').bookFromColumn('1a')).toBeNull();
    expect(scheme('stephanus').bookFromColumn('17a')).toBeNull();
  });

  it('section returns null — the work is bookless, so there is no book prefix to recover', () => {
    expect(scheme('section').bookFromColumn('5')).toBeNull();
  });
});

describe('stub schemes (ennead)', () => {
  it.each(['ennead'] as const)(
    'scheme(%s) is distinguishable, not a silent bekker fallback',
    (id) => {
      expect(scheme(id).id).toBe(id);
    },
  );

  it.each(['ennead'] as const)(
    'using scheme(%s) fails loudly rather than behaving like bekker',
    (id) => {
      const s = scheme(id);
      expect(() => s.bookFromColumn('1')).toThrow();
      expect(() => s.parseColumnToken('1')).toThrow();
      expect(() => s.parseLocation('1')).toThrow();
      expect(() => s.formatCitation('1')).toThrow();
    },
  );
});

describe('dk scheme (Diels-Kranz fragment/testimonium grammar)', () => {
  it('exposes the id, lineless by default, with the fragment-list outline nav', () => {
    expect(scheme('dk').id).toBe('dk');
    expect(scheme('dk').hasUserFacingLines).toBe(false);
    expect(scheme('dk').hasSections).toBe(true);
    expect(scheme('dk').jumpPlaceholder).toBe('e.g. B30');
  });

  it.each([
    ['B30', 'B30'],
    ['b30', 'B30'],     // series canonicalized uppercase
    ['B84A', 'B84a'],   // suffix canonicalized lowercase
    [' B30 ', 'B30'],   // outer whitespace trimmed
    ['A1a', 'A1a'],
    ['B126b', 'B126b'],
    ['C1', null],       // series must be A or B
    ['B', null],        // number required
    ['B1A2', null],     // suffix is a single letter, not alphanumeric
    ['30', null],       // series letter required — bare numbers don't resolve here
    ['B 30', null],     // internal whitespace rejected, not collapsed
  ])('parseColumnToken %s -> %s', (raw, expected) => {
    expect(scheme('dk').parseColumnToken(raw)).toBe(expected);
  });

  describe('parseLocation — lineless (Heraclitus)', () => {
    const s = scheme('dk');
    it.each([
      ['B30', { column: 'B30', line: null }],
      ['b30', { column: 'B30', line: null }],
      ['B84a', { column: 'B84a', line: null }],
      ['B30:5', null],   // no user-facing lines -> a line component is rejected
      ['B8.34', null],   // dotted scholarly form is verse-only
      ['', null],
      ['not a citation', null],
    ])('%s -> %o', (raw, expected) => {
      expect(s.parseLocation(raw)).toEqual(expected);
    });
  });

  describe('parseLocation — verse (Parmenides, hasUserFacingLines composed via schemeFor)', () => {
    const s = schemeFor('Parmenides');
    it.each([
      ['B8', { column: 'B8', line: null }],
      ['B8:34', { column: 'B8', line: 34 }],   // the `?loc=` query grammar
      ['B8.34', { column: 'B8', line: 34 }],   // the dotted scholarly ref
      ['B15a.2', { column: 'B15a', line: 2 }],
      // "B834" is NOT column-B8-line-34 concatenated (that form does not
      // exist in this grammar — formatCitation never produces it); it bare-
      // parses as the ordinary column token B834 (fragment 834), exactly
      // like scheme.py's identical column_re would.
      ['B834', { column: 'B834', line: null }],
    ])('%s -> %o', (raw, expected) => {
      expect(s.parseLocation(raw)).toEqual(expected);
    });
  });

  it('formatCitation renders the bare column when lineless, ignoring any line', () => {
    expect(scheme('dk').formatCitation('B30')).toBe('B30');
    expect(scheme('dk').formatCitation('B30', 5)).toBe('B30');
  });

  it('formatCitation dot-joins column.line for a verse (schemeFor-composed) work', () => {
    const s = schemeFor('Parmenides');
    expect(s.formatCitation('B8', 34)).toBe('B8.34');
    expect(s.formatCitation('B8', null)).toBe('B8');
  });

  it('bookFromColumn is always null — dk is bookless (a single declared book)', () => {
    expect(scheme('dk').bookFromColumn('B30')).toBeNull();
  });

  it('schemeFor composes hasUserFacingLines from work.citation.lines, defaulting false', () => {
    expect(schemeFor('Heraclitus').hasUserFacingLines).toBe(false);
    expect(schemeFor('Parmenides').hasUserFacingLines).toBe(true);
    // the base (non-composed) registry scheme is unaffected by another
    // work's override
    expect(scheme('dk').hasUserFacingLines).toBe(false);
  });

  it('formatCopyCitation composes "DK <chapter> <column>" with zero new machinery', () => {
    expect(formatCopyCitation('Heraclitus', 'B30')).toBe('DK 22 B30');
    expect(formatCopyCitation('Parmenides', 'B8', 34)).toBe('DK 28 B8.34');
  });

  it('round-trips through parseColumnToken -> formatCitation unchanged', () => {
    for (const raw of ['B1', 'B30', 'B84a', 'B126b', 'A5', 'A1a']) {
      const col = scheme('dk').parseColumnToken(raw)!;
      expect(scheme('dk').formatCitation(col)).toBe(raw);
    }
  });

  // TS/Python grammar parity: the SAME case list as test_scheme.py's
  // test_dk_column_and_ref_regex_match_series_number_suffix.
  it.each(['B1', 'B30', 'B84a', 'B126b', 'A5', 'A1a', 'B15a'])(
    'grammar parity with scheme.py: %s is a valid dk column',
    (tok) => {
      expect(scheme('dk').parseColumnToken(tok)).toBe(tok);
    },
  );
  it.each(['C1', 'B', '30', 'B1.5'])(
    'grammar parity with scheme.py (malformed): %s is rejected',
    (tok) => {
      expect(scheme('dk').parseColumnToken(tok)).toBeNull();
    },
  );

  // Explicit case-parity CONTRACT statement (Sol review nit): scheme.py's
  // `_DK_COLUMN_RE`/`_DK_VERSE_REF_RE` are STRICT (uppercase series,
  // lowercase suffix) on both sides, always — the two parity blocks above
  // assert exactly that, with the SAME case list as test_scheme.py. Lowercase/
  // mixed-case input ("b30", "B84A") is accepted ONLY here, at the
  // citation-JUMP layer (parseColumnToken/parseLocation's own input
  // canonicalization) — a TypeScript/UI-only courtesy for a hand-typed
  // citation, with NO Python-side equivalent: scheme.py never sees
  // user-typed input, only already-canonical manifest/emitted data, so it
  // has no lenient regex and needs none. This is not a parity gap.
  it('lowercase/mixed-case input is a JUMP-LAYER-ONLY courtesy — data grammar (columnRegex) stays strict', () => {
    // The strict, scheme.py-matching regex still rejects lowercase input.
    expect(scheme('dk').columnRegex.test('b30')).toBe(false);
    expect(scheme('dk').columnRegex.test('B84A')).toBe(false);
    expect(scheme('dk').columnRegex.test('B84a')).toBe(true);
    // parseColumnToken/parseLocation canonicalize it instead of rejecting —
    // the jump-layer leniency this contract describes.
    expect(scheme('dk').parseColumnToken('b30')).toBe('B30');
    expect(scheme('dk').parseColumnToken('B84A')).toBe('B84a');
  });

  describe('bare-number jump form — series derived from the work, not hardcoded', () => {
    it('a fragments (B) work resolves a bare number to its own series', () => {
      const s = schemeFor('Heraclitus');
      expect(s.parseColumnToken('30')).toBe('B30');
      expect(s.parseColumnToken('84a')).toBe('B84a');
      expect(s.parseColumnToken('84A')).toBe('B84a'); // suffix still canonicalized lowercase
      expect(s.parseLocation('30')).toEqual({ column: 'B30', line: null });
    });

    it('a testimonia (A) work resolves a bare number to A, not a hardcoded B', () => {
      const s = schemeFor('HeraclitusTestimonia');
      expect(s.parseColumnToken('5')).toBe('A5');
      expect(s.parseLocation('5')).toEqual({ column: 'A5', line: null });
    });

    it('explicit series letter still works on a schemeFor-composed instance', () => {
      const s = schemeFor('Heraclitus');
      expect(s.parseLocation('B30')).toEqual({ column: 'B30', line: null });
      expect(s.parseLocation('b30')).toEqual({ column: 'B30', line: null });
    });

    it('the module-level singleton scheme(\'dk\') still rejects a bare number (no series known)', () => {
      expect(scheme('dk').parseColumnToken('30')).toBeNull();
      expect(scheme('dk').parseLocation('30')).toBeNull();
    });
  });

  describe('site-wide full-citation-form jump ("DK 22 B30" / "22 B30")', () => {
    it('resolves work + column for the "DK <chapter> <column>" form, case-insensitively', () => {
      expect(parseDkFullCitation('DK 22 B30')).toEqual({ workId: 'Heraclitus', column: 'B30', line: null });
      expect(parseDkFullCitation('dk 22 b30')).toEqual({ workId: 'Heraclitus', column: 'B30', line: null });
    });

    it('resolves the bare "<chapter> <column>" form with no "DK" prefix', () => {
      expect(parseDkFullCitation('22 B30')).toEqual({ workId: 'Heraclitus', column: 'B30', line: null });
    });

    it('disambiguates the A/B series to the right work sharing one dk chapter', () => {
      expect(parseDkFullCitation('DK 22 A5')).toEqual({ workId: 'HeraclitusTestimonia', column: 'A5', line: null });
      expect(parseDkFullCitation('DK 22 B5')).toEqual({ workId: 'Heraclitus', column: 'B5', line: null });
    });

    it('resolves a verse-work line form ("DK 28 B8.34")', () => {
      expect(parseDkFullCitation('DK 28 B8.34')).toEqual({ workId: 'Parmenides', column: 'B8', line: 34 });
      expect(parseDkFullCitation('DK 28 B8:34')).toEqual({ workId: 'Parmenides', column: 'B8', line: 34 });
    });

    it('rejects a line component on a lineless (non-verse) work rather than silently dropping it', () => {
      expect(parseDkFullCitation('DK 22 B30.5')).toBeNull();
    });

    it('returns null for an unknown dk chapter/series pairing, or non-matching input', () => {
      expect(parseDkFullCitation('DK 99 B1')).toBeNull();
      expect(parseDkFullCitation('DK 22 C1')).toBeNull(); // series must be A or B
      expect(parseDkFullCitation('not a citation')).toBeNull();
      expect(parseDkFullCitation('B30')).toBeNull(); // the per-work bare form, not this site-wide one
    });
  });

  describe('site-wide no-series full-citation-form jump ("DK 14, 7" — Pythagoras, DK 14)', () => {
    it('resolves "DK <chapter>, <column>" (comma + space)', () => {
      expect(parseDkFullCitation('DK 14, 7')).toEqual({ workId: 'Pythagoras', column: '7', line: null });
    });

    it('resolves "DK <chapter>,<column>" (comma, no space)', () => {
      expect(parseDkFullCitation('DK 14,7')).toEqual({ workId: 'Pythagoras', column: '7', line: null });
    });

    it('resolves "DK <chapter> <column>" (space, no comma)', () => {
      expect(parseDkFullCitation('DK 14 7')).toEqual({ workId: 'Pythagoras', column: '7', line: null });
    });

    it('resolves a lettered suffix ("DK 14, 6a")', () => {
      expect(parseDkFullCitation('DK 14, 6a')).toEqual({ workId: 'Pythagoras', column: '6a', line: null });
    });

    it('resolves the bare "<chapter>, <column>" form with no "DK" prefix', () => {
      expect(parseDkFullCitation('14, 7')).toEqual({ workId: 'Pythagoras', column: '7', line: null });
    });

    it('a no-series chapter followed by an A/B series letter never resolves', () => {
      // "DK 14 A7" reads, at a glance, like a lettered citation -- but
      // chapter 14 has no `series` (it's noSeries), so the lettered path's
      // workByDkCitation(14, 'A') lookup finds nothing, and this no-series
      // regex requires a bare digit run (never a letter) right after the
      // separator -- neither path resolves it.
      expect(parseDkFullCitation('DK 14 A7')).toBeNull();
      expect(parseDkFullCitation('DK 14 B7')).toBeNull();
    });

    it('a lettered work chapter is unaffected by the no-series form', () => {
      // Sanity: adding the no-series regex/lookup must not perturb the
      // existing lettered forms at all.
      expect(parseDkFullCitation('DK 22 B30')).toEqual({ workId: 'Heraclitus', column: 'B30', line: null });
    });
  });
});

describe('dk no_series (a DK chapter printed with no A/B letter — Pythagoras, DK 14)', () => {
  it('schemeFor composes the no-series column grammar', () => {
    const s = schemeFor('Pythagoras');
    expect(s.columnRegex.test('7')).toBe(true);
    expect(s.columnRegex.test('6a')).toBe(true);
    expect(s.columnRegex.test('B7')).toBe(false); // series-letter form now REJECTED
    expect(s.jumpPlaceholder).toBe('e.g. 7');
  });

  it('parseColumnToken accepts a bare number/suffix and rejects a series letter', () => {
    const s = schemeFor('Pythagoras');
    expect(s.parseColumnToken('7')).toBe('7');
    expect(s.parseColumnToken('6a')).toBe('6a');
    expect(s.parseColumnToken('B7')).toBeNull();
    expect(s.parseColumnToken('A7')).toBeNull();
  });

  it('parseLocation resolves the bare column and the ?loc= colon form', () => {
    const s = schemeFor('Pythagoras');
    expect(s.parseLocation('7')).toEqual({ column: '7', line: null });
    expect(s.parseLocation('6a')).toEqual({ column: '6a', line: null });
    // no user-facing lines (lineless, like every non-verse dk work)
    expect(s.parseLocation('7:1')).toBeNull();
  });

  it('formatCitation/formatCite round-trip the bare column unchanged', () => {
    const s = schemeFor('Pythagoras');
    expect(s.formatCitation('7')).toBe('7');
    expect(formatCite('Pythagoras', '7')).toBe('7');
  });

  it('formatCopyCitation composes "DK 14, 7" from a copyAbbr carrying its own comma', () => {
    expect(formatCopyCitation('Pythagoras', '7')).toBe('DK 14, 7');
    expect(formatCopyCitation('Pythagoras', '6a')).toBe('DK 14, 6a');
  });

  it('bookFromColumn is still null — no_series does not change the bookless contract', () => {
    expect(schemeFor('Pythagoras').bookFromColumn('7')).toBeNull();
  });

  it('capture-shape note: columnRegex is 2 groups here, deliberately 3 in scheme.py', () => {
    // Documents (rather than merely asserting parity of) a deliberate
    // Python/TS asymmetry -- see DK_NO_SERIES_COLUMN_RE's own comment and
    // scheme.py's `_DK_NO_SERIES_COLUMN_RE`'s matching one. This side has
    // no consumer that unpacks a (series, number, suffix) 3-tuple, so
    // there is no always-empty placeholder group to keep in sync with
    // scheme.py's own 3-group shape -- the "case-parity contract" the two
    // sides' comments cross-reference is about canonicalization
    // strictness only, never capture-group count.
    const m = schemeFor('Pythagoras').columnRegex.exec('7a');
    expect(m).not.toBeNull();
    expect(m?.slice(1)).toEqual(['7', 'a']);
  });
});

describe('verse-line scheme (book.line dotted grammar for continuous verse — Lucretius)', () => {
  it('exposes the id with no user-facing lines and no section outline', () => {
    expect(scheme('verse-line').id).toBe('verse-line');
    expect(scheme('verse-line').hasUserFacingLines).toBe(false);
    expect(scheme('verse-line').hasSections).toBe(false);
  });

  it.each([
    ['1.101', '1.101'],
    ['3.47a', '3.47a'],
    ['3.47A', '3.47a'],              // suffix canonicalized lowercase
    ['1.1094-1101', '1.1094-1101'],  // a declared-lacuna range token
    [' 1.101 ', '1.101'],            // outer whitespace trimmed
    ['12.1', '12.1'],
  ])('parseColumnToken round-trips %s -> %s', (raw, expected) => {
    expect(scheme('verse-line').parseColumnToken(raw)).toBe(expected);
  });

  it.each([
    ['47ab', null],   // two suffix letters
    ['1.a47', null],  // letter before number
    ['4.7.1', null],  // extra dotted component
    ['', null],
    ['4.', null],
    ['.23', null],
    ['4a', null],     // not dotted at all — bekker-style letter grammar
  ])('parseColumnToken rejects %s', (raw, expected) => {
    expect(scheme('verse-line').parseColumnToken(raw)).toBe(expected);
  });

  describe('parseLocation', () => {
    const s = scheme('verse-line');
    it.each([
      ['1.101', { column: '1.101', line: null, isRange: false }],
      ['3.47a', { column: '3.47a', line: null, isRange: false }],
      ['1.1094-1101', { column: '1.1094-1101', line: null, isRange: true }],
      ['1:101', { column: '1.101', line: null, isRange: false }],         // ?loc= colon form
      ['3:47a', { column: '3.47a', line: null, isRange: false }],
      ['1:1094-1101', { column: '1.1094-1101', line: null, isRange: true }],
      ['101', { column: '101', line: null, isRange: false }],            // bare line, current-book context
      ['47a', { column: '47a', line: null, isRange: false }],
      ['1094-1101', { column: '1094-1101', line: null, isRange: true }], // bare lacuna range
      ['not a citation', null],
      ['', null],
      ['1.47ab', null],  // malformed lineref
    ])('%s -> %o', (raw, expected) => {
      expect(s.parseLocation(raw)).toEqual(expected);
    });
  });

  it('formatCitation renders the bare dotted column, ignoring any line (the line IS the column)', () => {
    expect(scheme('verse-line').formatCitation('1.101')).toBe('1.101');
    expect(scheme('verse-line').formatCitation('1.101', 5)).toBe('1.101');
    expect(scheme('verse-line').formatCitation('3.47a')).toBe('3.47a');
    expect(scheme('verse-line').formatCitation('1.1094-1101')).toBe('1.1094-1101');
  });

  it('round-trips through parseColumnToken -> formatCitation unchanged', () => {
    for (const raw of ['1.101', '3.47a', '1.1094-1101', '12.1']) {
      const col = scheme('verse-line').parseColumnToken(raw)!;
      expect(scheme('verse-line').formatCitation(col)).toBe(raw);
    }
  });

  it('bookFromColumn derives the book directly from the dotted prefix, like book-section', () => {
    expect(scheme('verse-line').bookFromColumn('1.101')).toBe(1);
    expect(scheme('verse-line').bookFromColumn('3.47a')).toBe(3);
    expect(scheme('verse-line').bookFromColumn('12.1')).toBe(12);
    expect(scheme('verse-line').bookFromColumn('4a')).toBeNull();
    expect(scheme('verse-line').bookFromColumn('')).toBeNull();
  });

  it('formatHash/formatLocValue follow the dotted grammar for a verse-line work', () => {
    expect(formatCite('Lucretius', '1.101')).toBe('1.101');
    expect(formatHash('Lucretius', '1.101')).toBe('#1.101');
    expect(formatLocValue('Lucretius', '1.101')).toBe('1.101');
  });

  it('formatCopyCitation composes "Lucr. <book>.<lineref>"', () => {
    expect(formatCopyCitation('Lucretius', '1.101')).toBe('Lucr. 1.101');
    expect(formatCopyCitation('Lucretius', '3.47a')).toBe('Lucr. 3.47a');
    expect(formatCopyCitation('Lucretius', '1.1094-1101')).toBe('Lucr. 1.1094-1101');
  });

  describe('isVerseLineRange', () => {
    it('classifies a lineref as a declared-lacuna range or an ordinary line', () => {
      expect(isVerseLineRange('101')).toBe(false);
      expect(isVerseLineRange('47a')).toBe(false);
      expect(isVerseLineRange('1094-1101')).toBe(true);
      expect(isVerseLineRange('1094a-1101b')).toBe(true);
    });
  });

  describe('verseLineOrderKey', () => {
    it('sorts numerically with a suffix ordering after its bare number: 47 < 47a < 48', () => {
      const linerefs = ['48', '47a', '47', '100', '99'];
      const sorted = [...linerefs].sort((a, b) => {
        const [an, as_] = verseLineOrderKey(a);
        const [bn, bs] = verseLineOrderKey(b);
        return an - bn || as_.localeCompare(bs);
      });
      expect(sorted).toEqual(['47', '47a', '48', '99', '100']);
    });

    it('99 < 100 numerically, never lexicographically', () => {
      const [n99] = verseLineOrderKey('99');
      const [n100] = verseLineOrderKey('100');
      expect(n99).toBeLessThan(n100);
    });

    it('is stable across books — the key is derived from the lineref alone', () => {
      expect(verseLineOrderKey('47a')).toEqual(verseLineOrderKey('47a'));
    });

    it('throws for a range token, which has no single sort position', () => {
      expect(() => verseLineOrderKey('1094-1101')).toThrow(/not a verse-line token/);
    });
  });

  // Leading-zero DECISION (design memo §3.1: "no leading-zero
  // normalization; PHI has none") — mirrors dk's identical grammar note:
  // the regex never special-cases a leading zero (real PHI data is never
  // observed to carry one), so a "047"-shaped lineref structurally matches
  // and is preserved literally, never renormalized to "47". See
  // test_scheme.py's matching
  // `test_verse_line_leading_zero_is_accepted_and_preserved_literally_not_stripped`
  // for the Python-side assertion.
  it('leading zero is accepted and preserved literally, not stripped (decision: PHI precedent, not rejection)', () => {
    expect(scheme('verse-line').parseColumnToken('1.047')).toBe('1.047');
    expect(verseLineOrderKey('047')).toEqual([47, '']);
  });

  // TS/Python grammar parity: the SAME case list as test_scheme.py's
  // test_verse_line_grammar_parity_with_citation_ts_valid/_malformed.
  it.each(['1.101', '3.47a', '1.1094-1101', '12.1', '1.1094a-1101b'])(
    'grammar parity with scheme.py: %s is a valid verse-line column',
    (tok) => {
      expect(scheme('verse-line').parseColumnToken(tok)).toBe(tok);
    },
  );
  it.each(['47ab', 'a47', '4.7.1', '', '4a', '1.47-', '1.-47', '1.'])(
    'grammar parity with scheme.py (malformed): %s is rejected',
    (tok) => {
      expect(scheme('verse-line').parseColumnToken(tok)).toBeNull();
    },
  );
});

describe('formatCopyCitation', () => {
  it('uses citation.copyAbbr as the prefix when set', () => {
    expect(formatCopyCitation('Marcus', '4.23')).toBe('M.Ant. 4.23');
  });

  it('falls back to the work abbr when citation.copyAbbr is absent', () => {
    expect(formatCopyCitation('NoAbbrWork', '4.23')).toBe('NAW 4.23');
  });

  it('falls back to the work abbr for a bekker work with a line', () => {
    expect(formatCopyCitation('EN', '1097a', 15)).toBe('EN 1097a15');
  });

  it('works with a bare-integer column for a flat section-scheme work', () => {
    expect(formatCopyCitation('Epictetus', '5')).toBe('Epict. Ench. 5');
  });

  it('throws a clear Error for an unknown work rather than emitting a plausible-looking citation', () => {
    // Unlike schemeFor (which defaults an unknown work to bekker), there's no
    // abbr/copyAbbr to prefix for a work that isn't in the registry, so a
    // typo'd work id must fail loudly instead of silently formatting e.g.
    // "typo 4.23".
    expect(() => formatCopyCitation('NoSuchWork', '4.23')).toThrow(/unknown work/);
  });
});

// REVIEW-CHECKLIST item 34: every scheme's citable unit gets its own noun —
// including bekker/busse/stephanus, which have no live work yet (Aristotle
// and Plato land later) but must already resolve correctly (forward
// requirement — see the fixture registry's BusseWork/StephanusWork/EN above).
describe('unitNounFor', () => {
  it('bekker (default scheme, EN fixture) -> chapter', () => {
    expect(unitNounFor('EN')).toEqual({ singular: 'chapter', plural: 'chapters', capitalized: 'Chapter' });
  });

  it('busse -> chapter', () => {
    expect(unitNounFor('BusseWork')).toEqual({ singular: 'chapter', plural: 'chapters', capitalized: 'Chapter' });
  });

  it('stephanus -> page', () => {
    expect(unitNounFor('StephanusWork')).toEqual({ singular: 'page', plural: 'pages', capitalized: 'Page' });
  });

  it('book-section -> section', () => {
    expect(unitNounFor('Marcus')).toEqual({ singular: 'section', plural: 'sections', capitalized: 'Section' });
  });

  it('flat section scheme -> chapter', () => {
    expect(unitNounFor('Epictetus')).toEqual({ singular: 'chapter', plural: 'chapters', capitalized: 'Chapter' });
  });

  // Per-work override (`citation.unitNoun`, Epicurus Wave 3): the flat
  // `section` scheme's table default ("chapter") is a scholarly convention
  // for a continuous prose work (Enchiridion), not an evidentiary claim
  // about every flat-scheme work — resolved against the REAL registry
  // (works.ts), not a test fixture, since these are now real works.
  it('flat section scheme with a per-work unitNoun override (Epicurus letter) -> section', () => {
    expect(unitNounFor('epicurus-letter-to-herodotus')).toEqual({
      singular: 'section', plural: 'sections', capitalized: 'Section',
    });
  });

  it('flat section scheme with a per-work unitNoun override (Kuriai Doxai) -> doctrine', () => {
    expect(unitNounFor('epicurus-kuriai-doxai')).toEqual({
      singular: 'doctrine', plural: 'doctrines', capitalized: 'Doctrine',
    });
  });

  it('flat section scheme with a per-work unitNoun override (Vatican Sayings) -> saying', () => {
    expect(unitNounFor('epicurus-vatican-sayings')).toEqual({
      singular: 'saying', plural: 'sayings', capitalized: 'Saying',
    });
  });

  it('letter -> letter', () => {
    expect(unitNounFor('Seneca')).toEqual({ singular: 'letter', plural: 'letters', capitalized: 'Letter' });
  });

  it('verse-line -> line', () => {
    expect(unitNounFor('Lucretius')).toEqual({ singular: 'line', plural: 'lines', capitalized: 'Line' });
  });

  it('dk B-series (fragments) -> fragment, irregular plural fragments', () => {
    expect(unitNounFor('Heraclitus')).toEqual({ singular: 'fragment', plural: 'fragments', capitalized: 'Fragment' });
  });

  it('dk A-series (testimonia) -> testimonium, irregular plural testimonia', () => {
    expect(unitNounFor('HeraclitusTestimonia')).toEqual({
      singular: 'testimonium', plural: 'testimonia', capitalized: 'Testimonium',
    });
  });

  it('derives dk A/B from the WORK record, not the scheme id alone — same scheme, different series, different noun', () => {
    const b = unitNounFor('Heraclitus');
    const a = unitNounFor('HeraclitusTestimonia');
    expect(b.singular).not.toBe(a.singular);
  });

  // Finding 1 (Sol review): a dk work with no A/B series letter at all
  // (Pythagoras, DK 14) previously fell through the "not A -> fragment"
  // assumption and got called "fragment" — factually wrong, since it
  // records ancient REPORTS about Pythagoras, not his own words. It must
  // classify from an explicit work-level signal (title), not a not-A default.
  it('dk with no series letter but a Testimonia title -> testimonium, NOT fragment', () => {
    expect(unitNounFor('Pythagoras')).toEqual({
      singular: 'testimonium', plural: 'testimonia', capitalized: 'Testimonium',
    });
  });

  it('dk with no series letter and no classifying title -> neutral "passage", never asserts fragment', () => {
    expect(unitNounFor('PythagorasUnclassifiable')).toEqual({
      singular: 'passage', plural: 'passages', capitalized: 'Passage',
    });
  });

  // Finding 5 (Sol review): ennead is a registered-but-unimplemented scheme
  // (Plotinus, planned) that previously fell through to the generic
  // "chapter" default. An Ennead is divided into tractates; citation is by
  // ennead.tractate.chapter, so the unit the scheme numbers is the tractate.
  it('ennead -> tractate, not the generic chapter fallback', () => {
    expect(unitNounFor('EnneadWork')).toEqual({
      singular: 'tractate', plural: 'tractates', capitalized: 'Tractate',
    });
  });
});

describe('groupUnitNoun', () => {
  it('capitalizes unitNounFor for every non-dk scheme', () => {
    expect(groupUnitNoun('Marcus')).toBe('Section');
    expect(groupUnitNoun('Epictetus')).toBe('Chapter');
    expect(groupUnitNoun('StephanusWork')).toBe('Page');
    expect(groupUnitNoun('Seneca')).toBe('Letter');
  });

  it('is bare (no noun) for a dk work — the fragment/testimonium column already reads as the citation', () => {
    expect(groupUnitNoun('Heraclitus')).toBe('');
    expect(groupUnitNoun('HeraclitusTestimonia')).toBe('');
  });
});

describe('CitationScheme.label — jump-box vocabulary (kept separate from unitNounFor)', () => {
  it('never leaks a dotted internal scheme id (copy rule)', () => {
    for (const id of ['bekker', 'busse', 'stephanus', 'book-section', 'section', 'dk', 'letter', 'verse-line'] as const) {
      expect(scheme(id).label).not.toMatch(/\./);
    }
  });

  it('book-section reads as "book and section"', () => {
    expect(scheme('book-section').label).toBe('book and section');
  });

  it('letter reads as bare "letter"', () => {
    expect(scheme('letter').label).toBe('letter');
  });

  it('verse-line reads as bare "line"', () => {
    expect(scheme('verse-line').label).toBe('line');
  });

  it('stephanus and dk labels are unchanged (already correct)', () => {
    expect(scheme('stephanus').label).toBe('Stephanus page');
    expect(scheme('dk').label).toBe('Diels–Kranz citation');
  });
});
