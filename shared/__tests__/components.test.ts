import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CommandPalette from '../components/CommandPalette.svelte';
import Reader from '../components/Reader.svelte';
import Search from '../components/Search.svelte';
import type { BookData, EnglishChunk } from '../lib/data';
import type { Work } from '../lib/works';

// These Reader tests need a real Work shape (translations, citation scheme)
// for the 'EN'/'Isa' fixture ids they render — a bekker-scheme work with a
// Rackham-style primary translation, and a busse-scheme work with lineless
// citations. Neither id is in the real registry (Plato-only now), so fixture
// metas stand in rather than depending on a real registry entry. 'Marcus' is
// CommandPalette's book-section fixture (see the 'CommandPalette.svelte'
// describe block below) — workPath is overridden alongside getWork since it
// otherwise resolves through the real (Plato-only) registry and throws for
// an id that isn't really registered.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixtures: Record<string, Work> = {
    EN: {
      id: 'EN', title: 'Fixture Bekker Work', abbr: 'EN', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [{ id: 'rackham', name: 'Test Translator (Test, 1900)', short: 'Rackham', slot: 'english' }],
      blurb: 'Fixture work for Reader.svelte tests (bekker scheme, the default).',
    },
    Isa: {
      id: 'Isa', title: 'Fixture Busse Work', abbr: 'Isa', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [{ id: 'owen', name: 'Test Translator (Test, 1900)', short: 'Owen', slot: 'english', footnotes: true }],
      citation: { scheme: 'busse', hideLineNumbers: true },
      blurb: 'Fixture work for Reader.svelte tests (busse scheme, lineless).',
    },
    Marcus: {
      id: 'Marcus', title: 'Fixture Book-Section Work', abbr: 'Med.', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 12, bookLabels: Array.from({ length: 12 }, (_, i) => String(i + 1)),
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      // abbr ('Med.') deliberately differs from citation.copyAbbr ('M.Ant.')
      // -- the Reader.svelte copy-citation tests below rely on this gap to
      // prove copy output uses copyAbbr, not the short UI abbr.
      citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'M.Ant.' },
      blurb: 'Fixture work for CommandPalette tests (book-section scheme, dotted columns).',
    },
    // dk-lettered (Heraclitus-shaped): abbr is the short UI label ('Her. B'),
    // copyAbbr is the scholarly DK-chapter prefix ('DK 22') -- Reader.svelte
    // copy-citation tests below assert the copy path uses copyAbbr.
    DkLet: {
      id: 'DkLet', title: 'Fixture DK Lettered Work', abbr: 'Her. B', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      citation: { scheme: 'dk', copyAbbr: 'DK 22', series: 'B', dkChapter: 22 },
      blurb: 'Fixture work for Reader.svelte copy-citation tests (dk lettered scheme).',
    },
    // dk no-series (Pythagoras-shaped, DK 14): copyAbbr carries its own
    // trailing comma so the copy join comes out "DK 14, 7" verbatim.
    DkNo: {
      id: 'DkNo', title: 'Fixture DK No-Series Work', abbr: 'Pyth.', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      citation: { scheme: 'dk', copyAbbr: 'DK 14,', noSeries: true, dkChapter: 14 },
      blurb: 'Fixture work for Reader.svelte copy-citation tests (dk no-series scheme).',
    },
    // A two-translation work (primary 'english' slot + 'secondary' slot)
    // for the Reader.svelte "missing translation chunk" fallback test below —
    // mirrors the real Meditations registry entry (Haines primary, Long
    // secondary), where Haines legitimately skips some sections.
    TwoTrans: {
      id: 'TwoTrans', title: 'Fixture Two-Translation Work', abbr: 'TT', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [
        { id: 'primary', name: 'Test Primary (Test, 1900)', short: 'Primo', slot: 'english' },
        { id: 'secondary', name: 'Test Secondary (Test, 1950)', short: 'Sec', slot: 'secondary' },
      ],
      blurb: 'Fixture work for Reader.svelte tests (a translation missing a chunk).',
    },
    // verse-line (Lucretius DRN-shaped) — the CommandPalette lacuna-range
    // tests below (mirroring BekkerJump.svelte's own regression coverage):
    // a dotted verse-line RANGE ("1.1-2") must resolve via the same
    // columns.json membership check BekkerJump.svelte's go() performs, not
    // straight through bookFromColumn's syntax-only book derivation.
    Verse: {
      id: 'Verse', title: 'Fixture Verse-Line Work', abbr: 'Verse', author: 'Test',
      language: 'lat', workType: 'verse',
      books: 6, bookLabels: Array.from({ length: 6 }, (_, i) => String(i + 1)),
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      citation: { scheme: 'verse-line' },
      blurb: 'Fixture work for CommandPalette tests (verse-line scheme, lacuna ranges).',
    },
    // Two same-titled fixture works under different (real) authors — the
    // Search.svelte regression fixture below: two "Fragments" result groups
    // must be told apart by author, not just by title (John's screenshot
    // report, 2026-07-24: "Fragments — Book 1" appeared twice with no way
    // to tell Heraclitus from Empedocles).
    FragA: {
      id: 'FragA', title: 'Fragments', abbr: 'FragA', author: 'heraclitus',
      language: 'grc', workType: 'fragments',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      blurb: 'Fixture work for Search.svelte author-disambiguation tests.',
    },
    FragB: {
      id: 'FragB', title: 'Fragments', abbr: 'FragB', author: 'empedocles',
      language: 'grc', workType: 'fragments',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      blurb: 'Fixture work for Search.svelte author-disambiguation tests.',
    },
    // dk (Diels-Kranz) fragments work — Search.svelte result-group label
    // regression fixture (John's screenshot report, 2026-07-24: a DK result
    // group rendered "Chapter B1" beside the actual hit "B10"/"B81").
    DkFrag: {
      id: 'DkFrag', title: 'Fragments', abbr: 'DkFrag', author: 'heraclitus',
      language: 'grc', workType: 'fragments',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      citation: { scheme: 'dk', copyAbbr: 'DK 22', series: 'B', dkChapter: 22 },
      blurb: 'Fixture work for Search.svelte dk group-label tests.',
    },
    // letter-scheme (Seneca Epistulae Morales-shaped) — Search.svelte's
    // result group heading regression fixture (finding 2, Sol review: a
    // letter work's result-group header hardcoded "Book N", so Epistle 47
    // showed "Book 47").
    SenLetter: {
      id: 'SenLetter', title: 'Epistles', abbr: 'Ep.', author: 'seneca',
      language: 'lat', workType: 'continuous',
      books: 124, bookLabels: Array.from({ length: 124 }, (_, i) => String(i + 1)),
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      citation: { scheme: 'letter', copyAbbr: 'Sen. Ep.' },
      blurb: 'Fixture work for Search.svelte letter-scheme group-heading tests.',
    },
    // Search.svelte per-passage credit fixture (finding 1, Sol review): a
    // column_sources passage's translator/licence must travel with a
    // search hit — this work stands in for Gorgias B11/B11a.
    CredWork: {
      id: 'CredWork', title: 'Credited Fixture', abbr: 'CredWork', author: 'Test',
      language: 'grc', workType: 'fragments',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [],
      blurb: 'Fixture work for Search.svelte per-passage credit tests (finding 1).',
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

const { fixtureBook } = vi.hoisted(() => ({
  fixtureBook: {
    book: 1,
    segments: [
      {
        id: 'seg1',
        column: '1094a',
        greek: [
          { n: 1, text: 'λόγος ἀρετή', tokens: [{ t: 'λόγος', o: 0, k: 'logos' }, { t: 'ἀρετή', o: 6, k: 'areth' }] },
        ],
        english: {
          text: 'Virtue (test) and κόσμος are discussed here.',
          notes: [],
          markers: [],
          bekker: [{ n: 1, offset: 0, real: true }],
        },
        chapterStarts: [{ chapter: '1', beforeLine: 1, wordIndex: 0, engOffset: 0, bekker: '1094a' }],
        third: [
          {
            chapter: '1',
            cont: false,
            text: 'Ostwald says virtue (test) beside κόσμος.',
            bekker: [{ n: 1, offset: 0, real: true }],
          },
        ],
      },
    ],
  } satisfies BookData,
}));

vi.mock('../lib/search', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/search')>();
  return {
    ...actual,
    search: vi.fn(async () => [
      {
        work: 'EN',
        meta: { id: 'seg1', book: 1, column: '1094a', head: 'λόγος', tokens: 'logos', english_head: 'Virtue (test) and κόσμος' },
        grkMatch: true,
        engMatch: true,
        grkPositions: [0],
        engPositions: [0],
      },
    ]),
  };
});

vi.mock('../lib/data', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/data')>();
  return {
    ...actual,
    fetchBook: vi.fn(async () => fixtureBook),
    fetchChapters: vi.fn(async () => ({
      '1': [{ chapter: '1', column: '1094a', line: '1', bekker: '1094a' }],
    })),
    // Spied (not just wrapped) so the CommandPalette book-section test below
    // can assert it's never called — a dotted-scheme citation must resolve
    // its book via bookFromColumn, not a columns.json fetch. 'Verse' returns
    // canned columns.json data instead of falling through to the real
    // fetchColumns (which would hit the network in a test environment) —
    // only the declared-lacuna column exists, mirroring the real corpus, so
    // a syntactically valid but undeclared range ("1.1-2") is absent here.
    fetchColumns: vi.fn((work: string) =>
      work === 'Verse'
        ? Promise.resolve({ '1.1094-1101': [{ book: 1, lo: 1094, hi: 1101 }] })
        : actual.fetchColumns(work),
    ),
    // Section-scheme outline (dk, stephanus, book-section, letter). Defaults
    // to empty; the Search.svelte group-label tests below override per work
    // with mockResolvedValueOnce.
    fetchSections: vi.fn(async () => ({})),
  };
});

afterEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, '', '/');
});

describe('Search.svelte', () => {
  // Smoke test: mounts, accepts Greek + English queries (including a
  // parenthesis metacharacter and a Unicode Greek term), and runs a search
  // without throwing. Asserting exact result-card markup would couple this to
  // the grouping internals; the value here is that mount + input + submit +
  // the (mocked) search call all wire together and nothing crashes.
  it('mounts and runs a search with metacharacter + Unicode input without throwing', async () => {
    const { search } = await import('../lib/search');
    render(Search);

    await fireEvent.input(screen.getByLabelText('Greek'), { target: { value: 'λόγ*' } });
    await fireEvent.input(screen.getByLabelText('English'), { target: { value: 'virtue (test) κόσμος' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    // The wired search path was invoked with the typed queries.
    expect(search).toHaveBeenCalled();
    // The form is still mounted (no crash / unhandled render error): the Greek
    // searchbox persists after the search runs.
    expect(screen.getByLabelText('Greek')).toBeInTheDocument();
  });

  // Regression test: two works sharing a title ("Fragments") under different
  // authors used to render identical, indistinguishable group headers
  // ("Fragments — Book 1" twice). Each header must now name its author too.
  it('labels each result group with its author, disambiguating two same-titled works', async () => {
    const { search } = await import('../lib/search');
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'FragA',
        meta: { id: 'seg1', book: 1, column: 'B1', head: 'πάντα', tokens: 'panta', english_head: 'All things' },
        grkMatch: true, engMatch: false, grkPositions: [0], engPositions: [],
      },
      {
        work: 'FragB',
        meta: { id: 'seg1', book: 1, column: 'B1', head: 'πάντα', tokens: 'panta', english_head: 'All things' },
        grkMatch: true, engMatch: false, grkPositions: [0], engPositions: [],
      },
    ]);

    render(Search);
    await fireEvent.input(screen.getByLabelText('Greek'), { target: { value: 'panta' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('Heraclitus — Fragments')).toBeInTheDocument();
    expect(screen.getByText('Empedocles — Fragments')).toBeInTheDocument();
  });

  // Regression test for John's screenshot report (2026-07-24): a dk
  // (Diels-Kranz) result group rendered "Chapter B1" as its bold label next
  // to the actual hit, "B10" — wrong vocabulary ("Chapter" is not a valid
  // label for a DK fragment/testimonium) AND a truncation bug (the page-label
  // derivation blindly sliced the last character off the anchor column,
  // assuming a Stephanus-style trailing letter; for dk's un-suffixed "B10"
  // that stripped the trailing digit instead, yielding "B1"). The row must
  // now read as the bare fragment citation, with no "Chapter" prefix and no
  // truncated second token.
  it('labels a dk fragment work\'s result group with the bare column, no "Chapter" prefix or truncated pairing', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook, fetchSections } = await import('../lib/data');

    (fetchSections as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      '1': [
        { column: 'B10', page: 10, id: 'seg-b10' },
        { column: 'B81', page: 81, id: 'seg-b81' },
      ],
    });
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      book: 1,
      segments: [
        {
          id: 'seg-b10', column: 'B10',
          greek: [{ n: 1, text: 'πάντα ῥεῖ', tokens: [{ t: 'πάντα', o: 0 }, { t: 'ῥεῖ', o: 6 }] }],
          english: null,
        },
        {
          id: 'seg-b81', column: 'B81',
          greek: [{ n: 1, text: 'ἥλιος νέος', tokens: [{ t: 'ἥλιος', o: 0 }, { t: 'νέος', o: 6 }] }],
          english: null,
        },
      ],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'DkFrag',
        meta: { id: 'seg-b10', book: 1, column: 'B10', head: 'πάντα', tokens: 'panta', english_head: '' },
        grkMatch: true, engMatch: false, grkPositions: [0], engPositions: [],
      },
    ]);

    const { container } = render(Search);
    await fireEvent.input(screen.getByLabelText('Greek'), { target: { value: 'panta' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(container.querySelector('.group-label')).toBeTruthy());
    expect(container.querySelector('.group-label')!.textContent).toBe('B10');
    expect(container.textContent).not.toContain('Chapter');
    expect(container.textContent).not.toContain('B1 ');
  });

  // Counterpart: a book-section work's result group is labeled "Section N"
  // (REVIEW-CHECKLIST item 34 — book.section's unit noun is "section", not
  // "chapter"; this used to say "Chapter 1.1" for Cicero's De Officiis, which
  // is actually book 1 section 1), with the truncation bug also fixed for
  // its own dotted column ("4.23" no longer clipped to "4.2").
  it('labels a book-section work\'s result group "Section", with its full untruncated column', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook, fetchSections } = await import('../lib/data');

    (fetchSections as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      '4': [{ column: '4.23', page: 4, letter: 23, id: 'seg-4.23' }],
    });
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      book: 4,
      segments: [{
        id: 'seg-4.23', column: '4.23',
        greek: [{ n: 1, text: 'ἡ τῶν ὅλων', tokens: [{ t: 'ἡ', o: 0 }, { t: 'τῶν', o: 2 }, { t: 'ὅλων', o: 6 }] }],
        english: null,
      }],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'Marcus',
        meta: { id: 'seg-4.23', book: 4, column: '4.23', head: 'ὅλων', tokens: 'holon', english_head: '' },
        grkMatch: true, engMatch: false, grkPositions: [2], engPositions: [],
      },
    ]);

    const { container } = render(Search);
    await fireEvent.input(screen.getByLabelText('Greek'), { target: { value: 'holon' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(container.querySelector('.group-label')).toBeTruthy());
    expect(container.querySelector('.group-label')!.textContent).toBe('Section 4.23');
  });

  // Regression test (finding 2, Sol review): a letter-scheme work's result
  // group heading hardcoded "Book" — Seneca's Epistle 47 showed "Book 47"
  // instead of "Letter 47".
  it('labels a letter-scheme work\'s result group heading "Letter", not "Book"', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook, fetchSections } = await import('../lib/data');

    (fetchSections as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      '47': [{ column: '47.1', page: 47, letter: 1, id: 'seg-47.1' }],
    });
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      book: 47,
      segments: [{
        id: 'seg-47.1', column: '47.1',
        greek: [{ n: 1, text: 'placeholder', tokens: [{ t: 'placeholder', o: 0 }] }],
        english: null,
      }],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'SenLetter',
        meta: { id: 'seg-47.1', book: 47, column: '47.1', head: 'placeholder', tokens: 'placeholder', english_head: '' },
        grkMatch: true, engMatch: false, grkPositions: [0], engPositions: [],
      },
    ]);

    const { container } = render(Search);
    await fireEvent.input(screen.getByLabelText('Greek'), { target: { value: 'placeholder' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(container.querySelector('.book-name')).toBeTruthy());
    expect(container.querySelector('.book-name')!.textContent).toBe('Letter 47');
    expect(container.querySelector('.book-name')!.textContent).not.toContain('Book');
  });
});

// Finding 1 (Sol review): the search surface indexed and rendered a
// segment's English with no attribution metadata at all, so a hit inside a
// column_sources passage (e.g. Gorgias B11/B11a's CC BY-NC-ND Parnassos
// translations) showed and exported the licensed English uncredited — a
// breach of the licence's attribution term wherever the text appears, not
// just on the reading page. Search.svelte already fetches the FULL segment
// (fetchBook) to build each hit's snippet, so the fix reads the same
// seg.english.credit the reading page renders — no search-index reshaping.
describe('Search.svelte — per-passage credit on English hits (finding 1)', () => {
  const creditedSeg = {
    id: 'seg-cred', column: 'B11',
    greek: [{ n: 1, text: 'πάντα', tokens: [{ t: 'πάντα', o: 0 }] }],
    english: {
      text: 'Good order for a city is courage.',
      notes: [], markers: [],
      credit: {
        translator: 'Jurgen R. Gatt',
        source: 'Gorgias/Gorgias (Parnassos Press)',
        year: 2022,
        licence: { name: 'CC BY-NC-ND 4.0', url: 'https://creativecommons.org/licenses/by-nc-nd/4.0/' },
      },
    },
  };
  const plainSeg = {
    id: 'seg-plain', column: 'B12',
    greek: [{ n: 1, text: 'x', tokens: [{ t: 'x', o: 0 }] }],
    english: { text: 'Plain translation, no credit.', notes: [], markers: [] },
  };

  it('shows the translator and licence beside a credited English hit', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook } = await import('../lib/data');
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      book: 1, segments: [creditedSeg],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'CredWork',
        meta: { id: 'seg-cred', book: 1, column: 'B11', head: 'πάντα', tokens: 'panta', english_head: creditedSeg.english.text },
        grkMatch: false, engMatch: true, grkPositions: [], engPositions: [11],
      },
    ]);

    const { container } = render(Search);
    await fireEvent.input(screen.getByLabelText('English'), { target: { value: 'courage' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(container.querySelector('.inst-credit')).toBeTruthy());
    expect(container.querySelector('.inst-credit')!.textContent)
      .toBe('Tr. Jurgen R. Gatt (2022) — CC BY-NC-ND 4.0.');
  });

  // The regression that matters: a hit with no column_sources credit at
  // all renders exactly as it did before this fix.
  it('shows nothing beside an uncredited English hit', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook } = await import('../lib/data');
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      book: 1, segments: [plainSeg],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'CredWork',
        meta: { id: 'seg-plain', book: 1, column: 'B12', head: 'x', tokens: 'x', english_head: plainSeg.english.text },
        grkMatch: false, engMatch: true, grkPositions: [], engPositions: [6],
      },
    ]);

    const { container } = render(Search);
    await fireEvent.input(screen.getByLabelText('English'), { target: { value: 'translation' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(container.querySelector('.inst-snippet')).toBeTruthy());
    expect(container.querySelector('.inst-credit')).toBeNull();
  });

  it('CSV export carries an Attribution column, filled only for the credited row', async () => {
    const { search } = await import('../lib/search');
    const { fetchBook } = await import('../lib/data');
    // mockResolvedValue (not -Once): exportCsv rebuilds groups over the FULL
    // result set with its own fetchBook call, separate from the one the
    // initial on-screen render already consumed.
    (fetchBook as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      book: 1, segments: [creditedSeg, plainSeg],
    });
    (search as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        work: 'CredWork',
        meta: { id: 'seg-cred', book: 1, column: 'B11', head: 'πάντα', tokens: 'panta', english_head: creditedSeg.english.text },
        grkMatch: false, engMatch: true, grkPositions: [], engPositions: [11],
      },
      {
        work: 'CredWork',
        meta: { id: 'seg-plain', book: 1, column: 'B12', head: 'x', tokens: 'x', english_head: plainSeg.english.text },
        grkMatch: false, engMatch: true, grkPositions: [], engPositions: [6],
      },
    ]);

    render(Search);
    await fireEvent.input(screen.getByLabelText('English'), { target: { value: 'translation' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await screen.findByRole('button', { name: 'Export results as CSV' });

    let capturedBlob: Blob | undefined;
    const createObjectURL = vi.spyOn(URL, 'createObjectURL')
      .mockImplementation((b: Blob | MediaSource) => { capturedBlob = b as Blob; return 'blob:mock'; });
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    await fireEvent.click(screen.getByRole('button', { name: 'Export results as CSV' }));
    await waitFor(() => expect(capturedBlob).toBeTruthy());

    const csv = (await capturedBlob!.text()).replace(/^﻿/, '');
    const rows = csv.trim().split('\r\n').map((r) => r.split(','));
    expect(rows[0]).toContain('Attribution');
    const attrCol = rows[0].indexOf('Attribution');
    const byRef = new Map(rows.slice(1).map((r) => [r[3], r]));
    expect(byRef.get('B11')?.[attrCol]).toBe('Tr. Jurgen R. Gatt (2022) — CC BY-NC-ND 4.0.');
    expect(byRef.get('B12')?.[attrCol]).toBe('');

    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
  });
});

describe('CommandPalette.svelte — citation jump', () => {
  // Regression test for the deferred adversarial-review finding: a
  // book-section work's citation ("4.23") used to resolve its book only via
  // fetchColumns + resolveBekker (a columns.json/Bekker path), so the "Go
  // to" item was silently omitted when that lookup came up empty. It now
  // dispatches on the scheme's bookFromColumn first (see citation.ts) and
  // never needs columns.json for a dotted-scheme work.
  it('offers a "Go to" item for a book-section citation, routed to its own book, without fetching columns.json', async () => {
    const { fetchColumns } = await import('../lib/data');
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '4.23' } });

    const item = await screen.findByText('Go to 4.23');
    expect(fetchColumns).not.toHaveBeenCalled();

    await fireEvent.click(item.closest('button')!);
    // 4.23's book (4) is derived straight from the dotted column, not from a
    // columns.json/resolveBekker lookup — see the fetchColumns assertion above.
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/test-author/Marcus/book-4?loc=4.23'),
    );
  });

  // Regression test for the adversarial-review finding: bookFromColumn only
  // validates a dotted column's SYNTAX ("99.99" parses fine), not corpus
  // membership. "Marcus" has 12 books, so book 99 is out of range — the
  // palette must not offer a dead jump that workPath would silently clamp to
  // book 12 with an unresolvable ?loc=99.99.
  it('offers no "Go to" item for a book-section citation whose book is out of range', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '99.99' } });

    // The corpus-search fallback item always appears, so wait for the list to
    // settle on it rather than asserting an empty list.
    await screen.findByText('Search the corpus for “99.99”');
    expect(screen.queryByText('Go to 99.99')).not.toBeInTheDocument();
  });

  // A citation in the last real book (12 of 12) still offers a jump — the
  // out-of-range guard must not reject an in-range book at the boundary.
  it('still offers a "Go to" item for a book-section citation in the last real book', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '12.36' } });

    const item = await screen.findByText('Go to 12.36');
    await fireEvent.click(item.closest('button')!);
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/test-author/Marcus/book-12?loc=12.36'),
    );
  });

  // Blocker-3 end-to-end coverage: the site-wide dk full-citation jump is
  // wired through parseDkFullCitation (citation.ts) and resolves against the
  // REAL works registry (the vi.mock above does not stub workByDkCitation /
  // workByDkChapterNoSeries, so these exercise the palette's genuine
  // cross-work resolution path all the way to the href).
  it('resolves the no-series full citation "DK 14, 7" to Pythagoras testimonia end to end', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: 'DK 14, 7' } });

    const item = await screen.findByText('Go to 7');
    await fireEvent.click(item.closest('button')!);
    // pythagoras/testimonia is bookless (dk scheme, books === 1), so its
    // division id is 'text', not 'book-1' (shared/lib/works.ts's divisionId).
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/pythagoras/testimonia/text?loc=7'),
    );
  });

  it('still resolves the lettered full citation "DK 22 B30" to Heraclitus fragments end to end', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: 'DK 22 B30' } });

    const item = await screen.findByText('Go to B30');
    await fireEvent.click(item.closest('button')!);
    // heraclitus/fragments is bookless (dk scheme, books === 1), so its
    // division id is 'text', not 'book-1' (shared/lib/works.ts's divisionId).
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/heraclitus/fragments/text?loc=B30'),
    );
  });

  it('never resolves a no-series chapter followed by a series letter ("DK 14 A7")', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Marcus', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: 'DK 14 A7' } });

    // The corpus-search fallback item always appears; the jump item must not.
    await screen.findByText('Search the corpus for “DK 14 A7”');
    expect(screen.queryByText(/^Go to /)).not.toBeInTheDocument();
  });

  // Adversarial-review finding: the palette independently parsed citations
  // and routed any dotted verse-line RANGE ("1.1-2") straight through
  // bookFromColumn, bypassing the columns.json membership check
  // BekkerJump.svelte's go() already applies (see citation.ts's `isRange`
  // and that component's own "rejects a verse-line range..." test). A range
  // is valid jump input only when it exactly matches a declared lacuna — a
  // real column in the corpus — never merely well-formed range syntax.
  it('offers no "Go to" item for a verse-line range that does not match a declared lacuna', async () => {
    const { fetchColumns } = await import('../lib/data');
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Verse', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '1.1-2' } });

    // The corpus-search fallback item always appears, so wait for the list
    // to settle on it rather than asserting an empty list.
    await screen.findByText('Search the corpus for “1.1-2”');
    expect(screen.queryByText('Go to 1.1-2')).not.toBeInTheDocument();
    expect(fetchColumns).toHaveBeenCalledWith('Verse');
  });

  // The counterpart: a range that IS a declared lacuna (present in
  // columns.json, the corpus's own record of real columns) still offers a jump.
  it('offers a "Go to" item for a verse-line range that matches a declared lacuna', async () => {
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Verse', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '1.1094-1101' } });

    const item = await screen.findByText('Go to 1.1094-1101');
    await fireEvent.click(item.closest('button')!);
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/test-author/Verse/book-1?loc=1.1094-1101'),
    );
  });

  // A non-range verse-line citation never triggers the new lacuna check — it
  // still resolves straight from the dotted column's own book prefix, with
  // no columns.json fetch involved (same fast path as book-section above).
  it('leaves a non-range verse-line citation unaffected, without fetching columns.json', async () => {
    const { fetchColumns } = await import('../lib/data');
    const onNavigate = vi.fn();
    render(CommandPalette, { props: { work: 'Verse', onNavigate } });

    await fireEvent.keyDown(window, { key: 'k', metaKey: true });
    const input = screen.getByRole('combobox');
    await fireEvent.input(input, { target: { value: '1.101' } });

    const item = await screen.findByText('Go to 1.101');
    expect(fetchColumns).not.toHaveBeenCalled();

    await fireEvent.click(item.closest('button')!);
    expect(onNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/read/test-author/Verse/book-1?loc=1.101'),
    );
  });
});

describe('Reader.svelte', () => {
  it('labels the source-only view from the work language without changing its internal view value', () => {
    const greekReader = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: fixtureBook } });
    expect(screen.getAllByRole('button', { name: 'Greek' }).length).toBeGreaterThan(0);
    greekReader.unmount();

    render(Reader, { props: { work: 'Verse', bookNum: 1, bookData: { book: 1, segments: [] } } });
    expect(screen.getAllByRole('button', { name: 'Latin' }).length).toBeGreaterThan(0);
  });

  // Smoke test: mounts with fixture book data plus highlight URL params
  // (Greek wildcard + English phrase containing a metacharacter) and renders
  // the fixture prose without throwing in the highlight code paths.
  it('renders fixture book data with highlight params applied', async () => {
    window.history.replaceState(null, '', '/EN/book/1?hlg=λόγ*&hle=virtue%20(test)%20κόσμος&loc=1094a:1');

    render(Reader, { props: { work: 'EN', bookNum: 1, bookData: fixtureBook } });

    // Bekker column from the fixture renders.
    expect(await screen.findByText('1094a')).toBeInTheDocument();
    // Greek token from the fixture renders as a token span.
    expect(screen.getByText('λόγος')).toHaveClass('tok');
    // The English column renders the fixture prose (the highlight code path ran
    // over a phrase containing a parenthesis metacharacter without throwing).
    const main = screen.getByRole('main');
    expect(within(main).getAllByText(/virtue/i).length).toBeGreaterThan(0);
  });

  it('renders sidecar English paragraph markers as paragraph breaks', async () => {
    window.history.replaceState(null, '', '/EN/book/1?trans=rackham');
    const book: BookData = structuredClone(fixtureBook);
    book.segments[0].english = {
      text: 'First paragraph. Second paragraph.',
      notes: [],
      markers: [{ kind: 'paragraph', n: '', offset: 'First paragraph.'.length }],
      bekker: [{ n: 1, offset: 0, real: true }],
    };

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });

    expect(await screen.findByText('First paragraph.')).toBeInTheDocument();
    expect(container.querySelectorAll('.english-col .para-br')).toHaveLength(1);
    expect(screen.getByText(/Second paragraph/)).toBeInTheDocument();
  });

  it('keeps English prose without paragraph markers on the existing flat path', async () => {
    window.history.replaceState(null, '', '/EN/book/1?trans=rackham');
    const book: BookData = structuredClone(fixtureBook);
    book.segments[0].english = {
      text: 'First paragraph. Second paragraph.',
      notes: [],
      markers: [],
      bekker: [{ n: 1, offset: 0, real: true }],
    };

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });

    expect(await screen.findByText(/First paragraph\. Second paragraph\./)).toBeInTheDocument();
    expect(container.querySelectorAll('.english-col .para-br')).toHaveLength(0);
  });

  it('keeps existing sidenote and figure inline markers out of rendered prose', async () => {
    window.history.replaceState(null, '', '/Isa/book/1');
    const book: BookData = structuredClone(fixtureBook);
    book.segments[0].english = {
      text: 'Alpha [[s1]] beta [[fig2]] gamma.',
      notes: [],
      markers: [],
      bekker: [{ n: 1, offset: 0, real: true }],
    };

    const { container } = render(Reader, { props: { work: 'Isa', bookNum: 1, bookData: book } });

    expect(await screen.findByText(/Alpha/)).toBeInTheDocument();
    expect(container.textContent).toContain('Alpha beta gamma.');
    expect(container.textContent).not.toContain('[[s1]]');
    expect(container.textContent).not.toContain('[[fig2]]');
  });

  // Regression test for the adversarial-review finding: a work whose manifest
  // legitimately allows a translation to skip a section (e.g. Haines has no
  // Meditations 11.31/11.34/12.15) used to render a completely blank English
  // gutter for that block. It now names the gap and points at whichever other
  // translation does carry it — 'TwoTrans' fixture has an empty primary
  // ('primary'/Primo, the default-selected translation) and a populated
  // secondary ('secondary'/Sec, the 'secondary' overlay slot) for the one segment.
  it('shows a muted fallback note when the selected translation lacks a chunk another translation has', async () => {
    window.history.replaceState(null, '', '/TwoTrans/book/1');
    const book: BookData = {
      book: 1,
      segments: [
        {
          id: 'seg1',
          column: '1a',
          greek: [],
          english: null,
          ross: [{ chapter: '1', text: 'Long has this passage.', cont: true, bekker: [] }],
        },
      ],
    };

    render(Reader, { props: { work: 'TwoTrans', bookNum: 1, bookData: book } });

    expect(await screen.findByText('Not in Primo (1900) — see Sec.')).toBeInTheDocument();
  });
});

// Blocker-2 regression coverage: Reader.svelte's copy-with-citation path
// (handleCopy, bound to the reader body's native 'copy' event — see
// shared/lib/citation.ts's formatCopyCitationRange) used to build its
// citation prefix from workMeta.abbr directly, so every dk work's copied
// citation carried its short UI abbreviation ("Pyth. 7") instead of its
// scholarly DK-chapter one ("DK 14, 7"). These tests drive the REAL 'copy'
// event Reader.svelte listens for (not just the citation.ts helper in
// isolation) with a genuine DOM Selection/Range over rendered `.greek-line`
// elements, so they exercise the exact code path a user's copy triggers.
describe('Reader.svelte — copy-with-citation (Blocker 2)', () => {
  function selectGreekLines(container: HTMLElement, startId: string, endId?: string): void {
    const startEl = container.querySelector<HTMLElement>(`[id="${startId}"]`);
    if (!startEl) throw new Error(`no element with id ${startId}`);
    const endEl = endId ? container.querySelector<HTMLElement>(`[id="${endId}"]`) : startEl;
    if (!endEl) throw new Error(`no element with id ${endId}`);
    const range = document.createRange();
    range.selectNodeContents(startEl);
    range.setEnd(endEl, endEl.childNodes.length);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }

  function fireCopy(container: HTMLElement): string | undefined {
    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);
    return captured;
  }

  it('dk-lettered: single-column selection copies "(DK 22 B30)", not the short UI abbr', async () => {
    window.history.replaceState(null, '', '/DkLet/book/1');
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg1', column: 'B30',
        greek: [{ n: 1, text: 'πάντα ῥεῖ', tokens: [{ t: 'πάντα', o: 0 }, { t: 'ῥεῖ', o: 6 }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DkLet', bookNum: 1, bookData: book } });
    await waitFor(() => expect(container.querySelector('[id="LB30-1"]')).toBeTruthy());

    selectGreekLines(container, 'LB30-1');
    const copied = fireCopy(container);

    expect(copied).toContain('(DK 22 B30)');
    expect(copied).not.toContain('Her. B');
  });

  it('dk-lettered: multi-column range selection copies "(DK 22 B30–B31)"', async () => {
    window.history.replaceState(null, '', '/DkLet/book/1');
    const book: BookData = {
      book: 1,
      segments: [
        {
          id: 'seg1', column: 'B30',
          greek: [{ n: 1, text: 'πάντα ῥεῖ', tokens: [{ t: 'πάντα', o: 0 }, { t: 'ῥεῖ', o: 6 }] }],
          english: null,
        },
        {
          id: 'seg2', column: 'B31',
          greek: [{ n: 1, text: 'ἥλιος νέος', tokens: [{ t: 'ἥλιος', o: 0 }, { t: 'νέος', o: 6 }] }],
          english: null,
        },
      ],
    };
    const { container } = render(Reader, { props: { work: 'DkLet', bookNum: 1, bookData: book } });
    await waitFor(() => expect(container.querySelector('[id="LB31-1"]')).toBeTruthy());

    selectGreekLines(container, 'LB30-1', 'LB31-1');
    const copied = fireCopy(container);

    expect(copied).toContain('(DK 22 B30–B31)');
  });

  it('dk no-series: single-column selection copies "(DK 14, 7)" (Pythagoras-shaped)', async () => {
    window.history.replaceState(null, '', '/DkNo/book/1');
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg1', column: '7',
        greek: [{ n: 1, text: 'ἀριθμὸς πάντα', tokens: [{ t: 'ἀριθμὸς', o: 0 }, { t: 'πάντα', o: 8 }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DkNo', bookNum: 1, bookData: book } });
    await waitFor(() => expect(container.querySelector('[id="L7-1"]')).toBeTruthy());

    selectGreekLines(container, 'L7-1');
    const copied = fireCopy(container);

    expect(copied).toContain('(DK 14, 7)');
    expect(copied).not.toContain('Pyth.');
  });

  it('book-section: single-column selection copies "(M.Ant. 4.23)", not the short UI abbr', async () => {
    window.history.replaceState(null, '', '/Marcus/book/4');
    const book: BookData = {
      book: 4,
      segments: [{
        id: 'seg1', column: '4.23',
        greek: [{ n: 1, text: 'ἡ τῶν ὅλων', tokens: [{ t: 'ἡ', o: 0 }, { t: 'τῶν', o: 2 }, { t: 'ὅλων', o: 6 }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'Marcus', bookNum: 4, bookData: book } });
    await waitFor(() => expect(container.querySelector('[id="L4.23-1"]')).toBeTruthy());

    selectGreekLines(container, 'L4.23-1');
    const copied = fireCopy(container);

    expect(copied).toContain('(M.Ant. 4.23)');
    expect(copied).not.toContain('Med.');
  });
});

describe('Reader.svelte — verse rendering (EnglishChunk.verse standoff)', () => {
  // "AAA BBB CCC DDD EEE." — index map:
  //   0123456789012345678 9
  //   AAA BBB CCC DDD EEE.
  // A verse range [4, 15) covers "BBB CCC DDD" (indices 4..14); a break at 8
  // (the start of "CCC") splits it into two verse-lines: "BBB " and "CCC DDD".
  const VERSE_TEXT = 'AAA BBB CCC DDD EEE.';

  function verseBook(verse: { start: number; end: number; breaks: number[] }[], extra?: Partial<EnglishChunk>): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg1',
          column: '1094a',
          greek: [],
          english: { text: VERSE_TEXT, notes: [], markers: [], bekker: [], verse, ...extra },
        },
      ],
    };
  }

  it('renders a verse range as a .verse block split into .verse-line spans at each break', async () => {
    window.history.replaceState(null, '', '/EN/book/1');
    const book = verseBook([{ start: 4, end: 15, breaks: [8] }]);

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });
    await screen.findByText(/AAA/);

    const verseEls = container.querySelectorAll('.verse');
    expect(verseEls).toHaveLength(1);
    const lines = verseEls[0].querySelectorAll('.verse-line');
    expect(lines).toHaveLength(2);
    expect(lines[0].textContent).toBe('BBB ');
    expect(lines[1].textContent).toBe('CCC DDD');
    // Text outside the range renders as ordinary prose, untouched.
    expect(container.textContent).toContain('AAA');
    expect(container.textContent).toContain('EEE.');
  });

  // CRITICAL regression (the memo's flagged riskiest seam): a Bekker tick AND
  // a paragraph marker both falling STRICTLY INSIDE a verse range must each
  // render EXACTLY ONCE, and must not corrupt the verse-line split — the tick
  // attaches to the text run where it falls, the paragraph marker renders its
  // one <br>, and no character of the range is dropped or duplicated.
  it('does not double-render or mis-split when a tick and a paragraph marker fall inside a verse range', async () => {
    window.history.replaceState(null, '', '/EN/book/1');
    // Range [4, 15) = "BBB CCC DDD", broken at 8 into "BBB " / "CCC DDD".
    // Tick at 7 (the space right after "BBB", still in the first line, before
    // the break) and the paragraph marker at 11 (the space right after "CCC",
    // in the second line, after the break) — both strictly inside the range,
    // neither on a range/break boundary.
    const book = verseBook(
      [{ start: 4, end: 15, breaks: [8] }],
      {
        bekker: [{ n: 42, offset: 7, real: true }],
        markers: [{ kind: 'paragraph', n: '', offset: 11 }],
      },
    );

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });
    await screen.findByText(/AAA/);

    const verseEl = container.querySelector('.verse')!;
    expect(verseEl).toBeTruthy();
    const lines = verseEl.querySelectorAll('.verse-line');
    expect(lines).toHaveLength(2);
    // The tick number renders exactly once, inside the verse block's first
    // line (and nowhere else in the document) — attached to the text run it
    // marks, per the pre-existing attachTicks convention.
    expect(lines[0].querySelectorAll('.bk-num')).toHaveLength(1);
    expect(lines[0].querySelector('.bk-num')!.textContent).toBe('42');
    const ticksAnywhere = Array.from(container.querySelectorAll('.bk-num')).filter(el => el.textContent === '42');
    expect(ticksAnywhere).toHaveLength(1);
    // The paragraph break renders exactly once, inside the second line.
    expect(lines[1].querySelectorAll('.para-br')).toHaveLength(1);
    expect(container.querySelectorAll('.para-br')).toHaveLength(1);
    // No text lost or duplicated: each Greek-letter run appears once, in
    // order — the tick's own digits ("42") are expected inline (real Bekker
    // ticks render as inline text too), but no word is split, dropped, or
    // repeated.
    expect(lines[0].textContent).toBe('BBB42 ');
    expect(lines[1].textContent).toBe('CCC DDD');
  });

  it('places an event exactly on a range boundary outside the verse block (exclusive end)', async () => {
    window.history.replaceState(null, '', '/EN/book/1');
    // A tick sitting exactly at the range's exclusive end (15, the start of
    // "EEE.") must land OUTSIDE .verse, not inside it.
    const book = verseBook(
      [{ start: 4, end: 15, breaks: [] }],
      { bekker: [{ n: 7, offset: 15, real: true }] },
    );

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });
    await screen.findByText(/AAA/);

    const verseEl = container.querySelector('.verse')!;
    const tickEl = Array.from(container.querySelectorAll('.bk-num')).find(el => el.textContent === '7');
    expect(tickEl).toBeTruthy();
    expect(verseEl.contains(tickEl!)).toBe(false);
  });

  it('renders ordinary prose with no .verse block for a chunk with no verse field', async () => {
    window.history.replaceState(null, '', '/EN/book/1');
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg1', column: '1094a', greek: [],
        english: { text: VERSE_TEXT, notes: [], markers: [], bekker: [] },
      }],
    };

    const { container } = render(Reader, { props: { work: 'EN', bookNum: 1, bookData: book } });
    await screen.findByText(/AAA/);

    expect(container.querySelectorAll('.verse')).toHaveLength(0);
    expect(container.textContent).toContain(VERSE_TEXT);
  });
});
