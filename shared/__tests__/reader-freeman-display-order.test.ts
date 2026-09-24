import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for the Freeman Ancilla wave (design note
// docs/freeman-wave-design.md §3.7 — "consume display_order: reorder
// segment display per the declared permutation"). Citations/anchors/ids
// stay column-keyed (`id="col-{seg.column}"`) regardless of display
// position — only the RENDERED list order changes.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'DKFIX', title: 'Fixture DK Work', abbr: 'Fix. B', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'DK 99', dkChapter: 99, series: 'B' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte display_order test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'DKFIX' ? fixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      id === 'DKFIX' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function seg(column: string) {
  return {
    id: `seg-${column}`,
    column,
    greek: [{ n: 1, text: `Greek ${column}`, tokens: [] }],
    english: { text: `English ${column}`, notes: [], markers: [] },
  };
}

function bookWith(displayOrder?: string[]): BookData {
  return {
    book: 1,
    segments: [seg('B1'), seg('B2'), seg('B3')],
    ...(displayOrder ? { displayOrder } : {}),
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte display_order (Freeman Ancilla wave, design note §3.7)', () => {
  it('renders segments in spine order when displayOrder is absent', async () => {
    render(Reader, { props: { work: 'DKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const ids = Array.from(document.querySelectorAll('.segment')).map((el) => el.id);
    expect(ids).toEqual(['col-B1', 'col-B2', 'col-B3']);
  });

  it('reorders the rendered list per a declared displayOrder permutation, keeping ids column-keyed', async () => {
    render(Reader, { props: { work: 'DKFIX', bookNum: 1, bookData: bookWith(['B3', 'B1', 'B2']) } });
    await flush();
    const ids = Array.from(document.querySelectorAll('.segment')).map((el) => el.id);
    expect(ids).toEqual(['col-B3', 'col-B1', 'col-B2']);
  });
});
