import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData, GreekLine, Segment } from '../lib/data';
import type { Work } from '../lib/works';

// Filled DK abbreviations in the reader (John, 2026-09-29). Pins: the "..."
// of a line carrying `fills` shows the supplied words in a .dk-fill span
// with the hover note as its title, in the Both and Greek views; the words
// around it stay lookup tokens; a line without fills is untouched. The Greek
// is invented (letter names), never corpus text.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'DKFILLFIX', title: 'Fixture DK Fill Work', abbr: 'Fix. B', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. B', dkChapter: 1, series: 'B' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the DK fill test.',
  };
  return { ...actual, getWork: (id: string) => (id === 'DKFILLFIX' ? fixture : actual.getWork(id)) };
});

const TEXT = 'ὡς λέγει ὁ ποιητής ‘ἄλφα ... ζῆτα’ καὶ τὰ λοιπά.';
const AT = TEXT.indexOf('...');

function line(text: string, fills?: GreekLine['fills']): GreekLine {
  const tokens = [...text.matchAll(/[\p{Script=Greek}]+/gu)].map((m) => ({ t: m[0], o: m.index!, k: m[0] }));
  return { n: 1, role: 'text', text, tokens, ...(fills ? { fills } : {}) };
}
function seg(column: string, l: GreekLine, english: boolean): Segment {
  return {
    id: `seg-${column}`, column,
    english: english ? { text: `English ${column}.`, notes: [], markers: [] } : null,
    greek: [l],
  };
}
const book = (english: boolean): BookData => ({ book: 1, segments: [
  seg('B1', line(TEXT, [{ start: AT, end: AT + 3, text: 'βῆτα, γάμμα / δέλτα', kind: 'verse', abbrev: 'ἄλφα ... ζῆτα' }]), english),
  seg('B2', line(TEXT), english),
] });
const flush = (ms = 20) => new Promise((r) => setTimeout(r, ms));

afterEach(() => {
  window.history.replaceState(null, '', '/');
  try { localStorage.clear(); } catch {}
});

describe('Reader.svelte filled DK abbreviations', () => {
  for (const [view, english] of [['Both', true], ['Greek', false]] as const) {
    it(`${view} view: the "..." shows DK's words, lighter, with the note`, async () => {
      const { container: c } = render(Reader, { props: { work: 'DKFILLFIX', bookNum: 1, bookData: book(english) } });
      await flush();
      expect(c.querySelector(`.reader-body.view-${view.toLowerCase()}`)).toBeTruthy();
      const fills = [...c.querySelectorAll<HTMLElement>('#col-B1 .greek-col .dk-fill')];
      expect(fills).toHaveLength(1);
      expect(fills[0]!.textContent).toBe('βῆτα, γάμμα / δέλτα');
      expect(fills[0]!.title).toBe('DK prints only ἄλφα … ζῆτα; the full verses are the fragment’s own.');
      expect(c.querySelector('#col-B1 .greek-col .line-text')!.textContent).toBe(TEXT.replace('...', 'βῆτα, γάμμα / δέλτα'));
      const toks = [...c.querySelectorAll('#col-B1 .greek-col .tok')].map((t) => t.textContent);
      expect(toks).toEqual(['ὡς', 'λέγει', 'ὁ', 'ποιητής', 'ἄλφα', 'ζῆτα', 'καὶ', 'τὰ', 'λοιπά']);
      // A line without fills keeps its "...".
      expect(c.querySelector('#col-B2 .dk-fill')).toBeNull();
      expect(c.querySelector('#col-B2 .greek-col .line-text')!.textContent).toBe(TEXT);
    });
  }
});
