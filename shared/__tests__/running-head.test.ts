import { render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import RunningHead from '../components/RunningHead.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';
import {
  buildContents, buildLibrary, citeDisplay, filterContents, filterLibrary,
  headingAt, looksLikeCitation, runningHeadText, titleCaseName,
  type ContentsInput, type LibraryInput,
} from '../lib/contents';

// The Lyceum reader chrome (PUBLIC_LYCEUM_CHROME): the running head is the
// navigation. These cover the pure model behind it — the contents of a work,
// the library listing and its filter, and the head's own label — plus a guard
// that Reader.svelte's existing controls strip is untouched by the one
// additive hook the chrome needed from it.

const emptyContents = (over: Partial<ContentsInput> = {}): ContentsInput => ({
  workTitle: 'Test Work',
  groupNoun: 'Book',
  bookLabels: ['I', 'II', 'III'],
  books: 3,
  currentBook: 1,
  bookless: false,
  unit: { singular: 'section', plural: 'sections' },
  manifestBooks: [],
  chapters: {},
  sections: {},
  philosophers: {},
  chapterTitles: {},
  bookHref: (n) => `/read/w/book-${n}`,
  ...over,
});

describe('contents model', () => {
  it('expands only the current book, and collapses the others to one line', () => {
    const model = buildContents(emptyContents({
      currentBook: 2,
      manifestBooks: [
        { n: 1, start: '1.1', end: '1.20' },
        { n: 2, start: '2.1', end: '2.30' },
        { n: 3, start: '3.1', end: '3.10' },
      ],
      sections: { '2': Array.from({ length: 30 }, (_, i) => ({ column: `2.${i + 1}` })) },
    }));
    expect(model.books.map((b) => b.entries.length)).toEqual([0, 3, 0]);
    expect(model.books[1].current).toBe(true);
    expect(model.books[0].extent).toBe('§§1–20 · 20 sections');
    expect(model.books[0].href).toBe('/read/w/book-1');
  });

  it('uses the work’s own headings when the built data carries them', () => {
    const model = buildContents(emptyContents({
      workTitle: 'Lives of Eminent Philosophers',
      manifestBooks: [{ n: 1, start: '1.1', end: '1.122' }],
      books: 1,
      sections: { '1': Array.from({ length: 122 }, (_, i) => ({ column: `1.${i + 1}` })) },
      philosophers: {
        '1': [
          { startSection: 22, endSection: 44, name: 'THALES', id: '1:1.22' },
          { startSection: 45, endSection: 67, name: 'SOLON', id: '1:1.45' },
        ],
      },
    }));
    expect(model.books[0].entries.map((e) => e.name)).toEqual(['Thales', 'Solon']);
    expect(model.books[0].entries[0].extent).toBe('§§22–44');
    expect(model.books[0].entries[0].hash).toBe('#col-1.22');
    expect(model.books[0].extent).toContain('2 lives');
    expect(model.note).toBeNull();
  });

  it('titles chapters from chapter-titles data, and keeps the citation range', () => {
    const model = buildContents(emptyContents({
      books: 1,
      unit: { singular: 'chapter', plural: 'chapters' },
      manifestBooks: [{ n: 1, start: '1094a', end: '1103a' }],
      chapters: { '1': [
        { chapter: '1', bekker: '1094a1–17' },
        { chapter: '2', bekker: '1094a18–1094b10' },
      ] },
      chapterTitles: { '1': { '1': 'The good as the aim of action' } },
    }));
    expect(model.books[0].entries[0].name).toBe('1. The good as the aim of action');
    expect(model.books[0].entries[0].extent).toBe('1094a1–17');
    expect(model.books[0].entries[1].name).toBe('Chapter 2');
    expect(model.books[0].extent).toBe('1094a–1103a · 2 chapters');
    expect(model.books[0].entries[0].head).toBe('The good as the aim of action');
    expect(model.books[0].entries[1].head).toBeNull();
  });

  it('falls back to section ranges — never a grid of numerals', () => {
    const model = buildContents(emptyContents({
      workTitle: 'Enchiridion',
      groupNoun: 'Book',
      books: 1,
      bookless: true,
      bookLabels: ['1'],
      manifestBooks: [{ n: 1, start: '1', end: '53' }],
      sections: { '1': Array.from({ length: 53 }, (_, i) => ({ column: String(i + 1) })) },
    }));
    const entries = model.books[0].entries;
    expect(entries).toHaveLength(6);            // 53 sections, ten to a line
    expect(entries[0].name).toBe('§§1–10');
    expect(entries[5].name).toBe('§§51–53');
    expect(entries[5].extent).toBe('3 sections');
    expect(entries[0].hash).toBe('#col-1');
    expect(entries[0].head).toBeNull();   // a range names no heading
    expect(model.meta).toContain('53 sections');
  });

  it('says so when a book has no headings at all', () => {
    const model = buildContents(emptyContents({ books: 1, manifestBooks: [{ n: 1, start: '1.1', end: '1.5' }] }));
    expect(model.books[0].entries).toEqual([]);
    expect(model.note).toMatch(/no headings of its own/);
  });

  it('filters books and entries together', () => {
    const model = buildContents(emptyContents({
      books: 2,
      currentBook: 1,
      philosophers: { '1': [
        { startSection: 22, endSection: 44, name: 'THALES', id: '1:1.22' },
        { startSection: 45, endSection: 67, name: 'SOLON', id: '1:1.45' },
      ] },
    }));
    const hit = filterContents(model.books, 'solon');
    expect(hit).toHaveLength(1);
    expect(hit[0].entries.map((e) => e.name)).toEqual(['Solon']);
    expect(filterContents(model.books, 'book ii')).toHaveLength(1);
  });
});

describe('running-head label', () => {
  it('composes author · work · book · section heading', () => {
    expect(runningHeadText({
      author: 'Diogenes Laertius', work: 'Lives of Eminent Philosophers',
      book: 'Book I', section: '§45', heading: 'Solon',
    })).toBe('Diogenes Laertius · Lives of Eminent Philosophers · Book I · §45 Solon');
  });

  it('drops the parts a work does not have', () => {
    expect(runningHeadText({
      author: 'Epictetus', work: 'Enchiridion', book: null, section: '§3', heading: null,
    })).toBe('Epictetus · Enchiridion · §3');
  });

  it('renders a column in the scheme’s own terms', () => {
    expect(citeDisplay('1.45')).toBe('§45');       // book-section
    expect(citeDisplay('53')).toBe('§53');         // flat section
    expect(citeDisplay('B30')).toBe('B30');        // Diels–Kranz
    expect(citeDisplay('17a')).toBe('17a');        // Stephanus
    expect(citeDisplay('3', 'Chapter')).toBe('Chapter 3');
    expect(citeDisplay('1.234', 'Line')).toBe('Line 234');
    expect(citeDisplay('')).toBe('');
  });

  it('reads the heading covering the live position', () => {
    const model = buildContents(emptyContents({
      books: 1,
      philosophers: { '1': [
        { startSection: 22, endSection: 44, name: 'THALES', id: '1:1.22' },
        { startSection: 45, endSection: 67, name: 'SOLON', id: '1:1.45' },
      ] },
    }));
    const book = model.books[0];
    expect(headingAt(book, '1.30')).toBe('Thales');
    expect(headingAt(book, '1.45')).toBe('Solon');
    expect(headingAt(book, '1.60')).toBe('Solon');
    expect(headingAt(book, '1.5')).toBeNull();     // before the first life
    expect(headingAt(undefined, '1.5')).toBeNull();
  });

  it('normalises an all-capitals source heading', () => {
    expect(titleCaseName('THALES')).toBe('Thales');
    expect(titleCaseName('Solon')).toBe('Solon');
  });
});

const library: LibraryInput = {
  shelves: [
    {
      id: 'presocratic',
      name: 'Presocratics',
      authors: [{
        id: 'heraclitus', name: 'Heraclitus', floruit: 'fl. c. 500 BC', current: false,
        groups: [{ label: null, works: [
          { id: 'heraclitus-fragments', title: 'Fragments', href: '/h/fragments', extent: 'B1–B139', current: false },
        ] }],
      }],
    },
    {
      id: 'classical',
      name: 'Classical',
      authors: [{
        id: 'aristotle', name: 'Aristotle', floruit: '384–322 BC', current: true,
        groups: [
          { label: 'Logic (Organon)', works: [
            { id: 'Cat', title: 'Categories', href: '/a/cat', extent: '1a–15b', current: false },
          ] },
          { label: 'Moral and Political Philosophy', works: [
            { id: 'EN', title: 'Nicomachean Ethics', href: '/a/en', extent: '10 books · 1094a–1181b', current: true },
          ] },
        ],
      }],
    },
  ],
};

describe('library sheet', () => {
  it('counts authors and works across the shelves', () => {
    const model = buildLibrary(library);
    expect(model.meta).toBe('2 authors · 3 works');
    expect(model.shelves[1].meta).toBe('1 author · 2 works');
    expect(model.shelves[1].authors[0].meta).toBe('384–322 BC · 2 works');
  });

  it('narrows to one work when a work title is typed', () => {
    const hit = filterLibrary(buildLibrary(library), 'nicomachean');
    expect(hit.meta).toBe('1 author · 1 work');
    expect(hit.shelves.map((s) => s.id)).toEqual(['classical']);
    expect(hit.shelves[0].authors[0].groups[0].works[0].title).toBe('Nicomachean Ethics');
  });

  it('keeps all of an author’s works when the author matches', () => {
    const hit = filterLibrary(buildLibrary(library), 'aristotle');
    expect(hit.meta).toBe('1 author · 2 works');
  });

  it('drops everything when nothing matches', () => {
    expect(filterLibrary(buildLibrary(library), 'zzz').shelves).toEqual([]);
  });

  it('recognises citation-shaped input, and only that', () => {
    for (const q of ['1.4', '1094a15', 'B30', 'DK 22 B30', 'Tusc 1.4', '17a']) {
      expect(looksLikeCitation(q), q).toBe(true);
    }
    for (const q of ['', 'Aristotle', 'nicomachean ethics', 'the good']) {
      expect(looksLikeCitation(q), q).toBe(false);
    }
  });
});

// ── Reader.svelte: the one additive hook, and nothing else ────────────────
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'RHFIX', title: 'Running Head Fixture', abbr: 'RHFIX', author: 'Test',
    language: 'grc', workType: 'continuous', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'book-section' },
    blurb: 'Fixture work for the Lyceum running-head tests.',
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' }],
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'RHFIX' ? fixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      id === 'RHFIX' ? `/read/test-author/RHFIX/book-${book}` : actual.workPath(id, book),
  };
});

const bookData: BookData = {
  book: 1,
  segments: [{
    id: 'seg-1',
    column: '1.1',
    greek: [{ n: 1, text: 'λόγος ἀρετή', tokens: [{ t: 'λόγος', o: 0, k: 'logos' }] }],
    english: { text: 'Reason and virtue.', notes: [], markers: [] },
  }],
};

// ── RunningHead.svelte: hasEnglish's initial (pre-hydration-reconcile) state
// ────────────────────────────────────────────────────────────────────────
// readReaderState() (run in onMount) only overwrites hasEnglish once Reader's
// own .rc-desktop-controls view-toggle exists in the document; here that
// element is absent, so what renders is exactly the seeded value — the thing
// under test. A zero-translation work (Heraclitus' Testimonia, the
// Tusculans) must never show Both/English, even for the one frame before
// that reconcile would have run.
describe('RunningHead.svelte: hasEnglish seeded from translations', () => {
  const contents = buildContents(emptyContents());
  const library = buildLibrary({ shelves: [] });
  const baseProps = { author: 'Author', workTitle: 'Work', workId: 'RHFIX', library, contents };

  it('renders only the source-language button with zero translations', () => {
    const { container } = render(RunningHead, { props: { ...baseProps, translations: [] } });
    const viewButtons = container.querySelectorAll('.views .rhp.v');
    expect(viewButtons).toHaveLength(1);
    expect(viewButtons[0].textContent).toBe('Greek');
  });

  it('renders the full Greek · Both · English toggle with one translation', () => {
    const { container } = render(RunningHead, {
      props: { ...baseProps, translations: [{ id: 't', short: 'Test', name: 'Test Translator' }] },
    });
    const viewButtons = container.querySelectorAll('.views .rhp.v');
    expect(Array.from(viewButtons).map((b) => b.textContent)).toEqual(['Greek', 'Both', 'English']);
  });
});

describe('Reader.svelte with the chrome off', () => {
  it('still renders its own controls strip, view toggle and print control', () => {
    const { container } = render(Reader, { props: { work: 'RHFIX', bookNum: 1, bookData } });
    expect(container.querySelector('.reader-controls')).not.toBeNull();
    expect(container.querySelector('.rc-desktop-controls .view-toggle')).not.toBeNull();
    expect(container.querySelector('.rc-desktop-controls .print-btn')).not.toBeNull();
    expect(container.querySelector('.reader-body')).not.toBeNull();
  });

  it('publishes no position until the scroll-spy reports one', () => {
    const seen: CustomEvent[] = [];
    const listener = (e: Event) => seen.push(e as CustomEvent);
    document.addEventListener('reader-position', listener);
    render(Reader, { props: { work: 'RHFIX', bookNum: 1, bookData } });
    document.removeEventListener('reader-position', listener);
    expect(seen).toEqual([]);
  });
});
