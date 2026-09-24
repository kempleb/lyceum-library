import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for repo task #4: a work with NO English wired at all
// (every segment's `english` field null, e.g. thales-fragments/testimonia)
// still offered the "Greek | Both | English" view toggle, and English-only
// view rendered every fragment as an empty row. Design pin: suppress the
// Both/English toggle buttons for a zero-English book, show a quiet inline
// note ("No English translation wired yet."), and fall back any stored/URL
// preference of 'english'/'both' to source-only without error.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const common = {
    author: 'Test',
    language: 'grc' as const,
    workType: 'continuous' as const,
    books: 1,
    bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'book-section' as const },
    blurb: 'Fixture work for the Reader.svelte view-toggle suppression test.',
  };
  const fixtures: Record<string, Work> = {
    NOENG: {
      id: 'NOENG', title: 'Fixture No-English Work', abbr: 'NOENG', ...common,
      translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    },
    HASENG: {
      id: 'HASENG', title: 'Fixture English-Bearing Work', abbr: 'HASENG', ...common,
      translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(english: boolean): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-1',
        column: '1',
        greek: [
          { n: 1, text: 'λόγος ἀρετή', tokens: [{ t: 'λόγος', o: 0, k: 'logos' }, { t: 'ἀρετή', o: 6, k: 'areth' }] },
        ],
        english: english ? { text: 'Virtue is discussed here.', notes: [], markers: [] } : null,
      },
    ],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte view toggle suppression for a zero-English book (task #4)', () => {
  it('shows only the source-language button, plus the exact note, and no Both/English buttons', async () => {
    render(Reader, { props: { work: 'NOENG', bookNum: 1, bookData: bookWith(false) } });
    await flush();

    const toggle = document.querySelector('.view-toggle') as HTMLElement;
    const buttons = Array.from(toggle.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Greek']);

    const note = document.querySelector('.rc-no-english');
    expect(note).toBeTruthy();
    expect(note?.textContent?.trim()).toBe('No English translation wired yet.');
  });

  it('falls back a stored english/both view preference to source-only without error', async () => {
    localStorage.setItem('reader-view', 'both');
    render(Reader, { props: { work: 'NOENG', bookNum: 1, bookData: bookWith(false) } });
    await flush();

    const toggle = document.querySelector('.view-toggle') as HTMLElement;
    const activeBtn = toggle.querySelector('button.active');
    expect(activeBtn?.textContent?.trim()).toBe('Greek');
    localStorage.removeItem('reader-view');
  });
});

describe('Reader.svelte view toggle for an English-bearing book (unaffected by task #4)', () => {
  it('shows all three view buttons and no "no English" note', async () => {
    render(Reader, { props: { work: 'HASENG', bookNum: 1, bookData: bookWith(true) } });
    await flush();

    const toggle = document.querySelector('.view-toggle') as HTMLElement;
    const buttons = Array.from(toggle.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Greek', 'Both', 'English']);

    expect(document.querySelector('.rc-no-english')).toBeFalsy();
  });
});
