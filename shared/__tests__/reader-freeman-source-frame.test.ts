import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for the Freeman Ancilla wave's `.eng-source-frame`
// mechanism (design note docs/freeman-wave-design.md §3, appendix note on
// EnglishChunk.frames): a chunk's declared [start, end) char range wraps
// the corresponding slice of the rendered English text in
// `<span class="eng-source-frame">`, leaving the rest of the text plain.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'DKFRAME', title: 'Fixture DK Frame Work', abbr: 'Fix. B', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'DK 98', dkChapter: 98, series: 'B' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte .eng-source-frame test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'DKFRAME' ? fixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      id === 'DKFRAME' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(): BookData {
  const text = "(Plato, Sophist 232D: 'a quoted view').";
  return {
    book: 1,
    segments: [
      {
        id: 'seg-B1',
        column: 'B1',
        kind: 'embedded',
        greek: [{ n: 1, text: 'Greek text', tokens: [] }],
        english: { text, notes: [], markers: [], frames: [[0, 22]] },
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

describe('Reader.svelte .eng-source-frame (Freeman Ancilla wave, design note §3)', () => {
  it('wraps the declared frame range in .eng-source-frame, leaving the quoted words plain', async () => {
    render(Reader, { props: { work: 'DKFRAME', bookNum: 1, bookData: bookWith() } });
    await flush();
    const frame = document.querySelector('.eng-source-frame');
    expect(frame).toBeTruthy();
    expect(frame?.textContent).toBe('(Plato, Sophist 232D: ');
    const prose = document.querySelector('.overlay-prose');
    expect(prose?.textContent).toContain('a quoted view');
  });
});
