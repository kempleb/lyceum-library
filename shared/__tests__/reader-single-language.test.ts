import { render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Reader, { paragraphAliasColumn } from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// A work whose ONLY language is English (`language: 'en'`): one column, no
// translation controls, no dictionary links, no claim of a parallel text.
// Every branch is keyed on `work.language === 'en'`, never on "has no
// translation" (26 Greek/Latin works have none; reader-view-toggle.test.ts
// pins their wording). ENOTRANS below is the control for that.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const common = {
    author: 'Test',
    workType: 'continuous' as const,
    books: 1,
    bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'book-section' as const },
    blurb: 'Fixture work for the single-language Reader test.',
  };
  const trans = [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }];
  const fixtures: Record<string, Work> = {
    ENONLY: {
      id: 'ENONLY', title: 'Fixture English-Only Work', abbr: 'ENONLY', ...common,
      language: 'en', translations: [],
    },
    ENESSAY: {
      id: 'ENESSAY', title: 'Fixture English Essay Work', abbr: 'ENESSAY', ...common,
      language: 'en', translations: [], divisionNoun: 'essay',
    },
    ENOTRANS: {
      id: 'ENOTRANS', title: 'Fixture Greek No-English Work', abbr: 'ENOTRANS', ...common,
      language: 'grc', translations: trans,
    },
    NOTRANS: {
      id: 'NOTRANS', title: 'Fixture Latin No-Translation Work', abbr: 'NOTRANS', ...common,
      language: 'lat', translations: [],
    },
    PLAIN: {
      id: 'PLAIN', title: 'Fixture Plain Book-Section Work', abbr: 'PLAIN', ...common,
      language: 'grc', translations: trans,
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function book(column = '1', text = 'The whole of virtue is discussed here.', tokens: { t: string; o: number; k: string }[] = []): BookData {
  return {
    book: 1,
    segments: [{ id: `seg-${column}`, column, greek: [{ n: 1, text, tokens }], english: null }],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

beforeEach(() => {
  (Element.prototype.scrollIntoView as unknown as { mockClear: () => void }).mockClear();
});

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte for a work whose only language is English', () => {
  it('shows one English column and no translation or view controls', async () => {
    render(Reader, { props: { work: 'ENONLY', bookNum: 1, bookData: book() } });
    await flush();

    const text = document.querySelector('.line-text') as HTMLElement;
    expect(text).toBeTruthy();
    expect(text.getAttribute('lang')).toBe('en');
    expect(text.textContent).toContain('The whole of virtue');
    expect(document.querySelector('.greek-col')?.getAttribute('lang')).toBe('en');

    expect(document.querySelector('.view-toggle')).toBeFalsy();
    expect(document.querySelector('.rc-no-english')).toBeFalsy();
    expect(document.body.textContent).not.toContain('No English translation wired yet.');
    expect(document.body.textContent).not.toContain('or English');
    expect(document.body.textContent).toContain('Applies to any selection');
  });

  it('control: a Greek work with no English still shows the source-language toggle and lang="grc"', async () => {
    render(Reader, { props: { work: 'ENOTRANS', bookNum: 1, bookData: book('1', 'λόγος ἀρετή', [{ t: 'λόγος', o: 0, k: 'logos' }]) } });
    await flush();

    const buttons = Array.from((document.querySelector('.view-toggle') as HTMLElement).querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Greek']);
    expect(document.querySelector('.rc-no-english')?.textContent?.trim()).toBe('No English translation wired yet.');
    expect(document.querySelector('.line-text')?.getAttribute('lang')).toBe('grc');
    expect(document.querySelector('.tok')).toBeTruthy();
    expect(document.body.textContent).toContain('Applies to any selection, Greek or English');
  });
});

// Review item 128, option (a): a Greek or Latin work the registry lists no
// translation for leaves out the line that promises one; it keeps its
// source-language column and controls. Keyed on `translations.length === 0`.
describe('Reader.svelte for a work with no translation (item 128)', () => {
  it('drops the "wired yet" line and keeps the source-language view', async () => {
    render(Reader, { props: { work: 'NOTRANS', bookNum: 1, bookData: book('1', 'lorem ipsum') } });
    await flush();

    expect(document.querySelector('.rc-no-english')).toBeFalsy();
    expect(document.body.textContent).not.toContain('No English translation wired yet.');
    const buttons = Array.from((document.querySelector('.view-toggle') as HTMLElement).querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Latin']);
    expect(document.querySelector('.line-text')?.getAttribute('lang')).toBe('la');
    // The copy-settings hint names no English for a work that has none.
    expect(document.body.textContent).toContain('Applies to any selection');
    expect(document.body.textContent).not.toContain('Latin or English');
  });

  it('control: a work with a translation but no English in this book still shows the note', async () => {
    render(Reader, { props: { work: 'ENOTRANS', bookNum: 1, bookData: book() } });
    await flush();
    expect(document.querySelector('.rc-no-english')?.textContent?.trim()).toBe('No English translation wired yet.');
  });
});

describe('paragraphAliasColumn', () => {
  const essay = { divisionNoun: 'essay', citation: { scheme: 'book-section' } } as Pick<Work, 'divisionNoun' | 'citation'>;
  const plain = { citation: { scheme: 'book-section' } } as Pick<Work, 'divisionNoun' | 'citation'>;
  const essayBekker = { divisionNoun: 'essay', citation: { scheme: 'bekker' } } as Pick<Work, 'divisionNoun' | 'citation'>;

  it('maps #paragraph-N to book.N for an essay work cited by book-section', () => {
    expect(paragraphAliasColumn('paragraph-3', 1, essay)).toBe('1.3');
    expect(paragraphAliasColumn('paragraph-12', 4, essay)).toBe('4.12');
  });
  it('returns null for every other case', () => {
    expect(paragraphAliasColumn('paragraph-3', 1, plain)).toBeNull();
    expect(paragraphAliasColumn('paragraph-3', 1, essayBekker)).toBeNull();
    expect(paragraphAliasColumn('paragraph-0', 1, essay)).toBeNull();
    expect(paragraphAliasColumn('paragraph-03', 1, essay)).toBeNull();
    expect(paragraphAliasColumn('Paragraph-3', 1, essay)).toBeNull();
    expect(paragraphAliasColumn('paragraph-3x', 1, essay)).toBeNull();
    expect(paragraphAliasColumn('4.23', 1, essay)).toBeNull();
    expect(paragraphAliasColumn('paragraph-3', 1, undefined)).toBeNull();
  });
});

describe('Reader.svelte #paragraph-N hash', () => {
  it('scrolls to col-1.3 on an essay work', async () => {
    window.history.replaceState(null, '', '/ENESSAY/book/1#paragraph-3');
    render(Reader, { props: { work: 'ENESSAY', bookNum: 1, bookData: book('1.3') } });
    await flush();

    const target = document.getElementById('col-1.3');
    expect(target).toBeTruthy();
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);
  });

  it('targets nothing on a plain book-section work', async () => {
    window.history.replaceState(null, '', '/PLAIN/book/1#paragraph-3');
    render(Reader, { props: { work: 'PLAIN', bookNum: 1, bookData: book('1.3') } });
    await flush();

    expect(document.getElementById('col-1.3')).toBeTruthy();
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
  });
});
