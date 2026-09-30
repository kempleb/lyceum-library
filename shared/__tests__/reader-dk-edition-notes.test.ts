import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData, GreekLine, Segment } from '../lib/data';
import type { Work } from '../lib/works';

// DK edition references as numbered notes in the reader (John, 2026-09-28).
// Pins: the bracket leaves the Greek line for a superscript number button
// ("Note N"), numbered from 1 in each DK column; the button opens a pop-up
// with the bracket as printed (a DK cross-reference in it still links) and
// Escape / a second click / a click outside closes it; cross-references,
// Greek words and dates stay in the line; the Greek words around a note stay
// clickable; print gets each column's notes as a numbered list.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'DKNOTEFIX', title: 'Fixture DK Note Work', abbr: 'Fix. A', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. A', dkChapter: 1, series: 'A' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the DK edition-note test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'DKNOTEFIX' ? fixture : actual.getWork(id)),
    workByDkCitation: (chapter: number, series: 'A' | 'B') =>
      (chapter === 1 && series === 'A' ? fixture : actual.workByDkCitation(chapter, series)),
    workPath: (id: string, book = 1) =>
      id === 'DKNOTEFIX' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

// A Greek line with a token for each Greek word, as the pipeline emits it.
function line(text: string): GreekLine {
  const tokens = [...text.matchAll(/[\p{Script=Greek}]+/gu)].map((m) => ({ t: m[0], o: m.index!, k: m[0] }));
  return { n: 1, role: 'text', text, tokens };
}
function seg(column: string, lines: string[], english = true): Segment {
  return {
    id: `seg-${column}`, column,
    english: english ? { text: `English ${column}.`, notes: [], markers: [] } : null,
    greek: lines.map(line), citationHeads: [],
  };
}
const A1 = 'Ἀρίσταρχος [fr. 173 Us.; A 2] καὶ [B 10] λόγος [sc. ῥήτορες] [504—501] ἔφη [II 253, 28].';
// Democritus B39/B61's real last-line shape: the bracket is the whole line
// (a trailing "." aside) -- it stays, not a note (John, 2026-09-28).
const A3 = '[Stob. III 37, 25].';
// Empedocles testimonia A1's real shape (GPT-6-Sol review, 2026-09-28): the
// identical bracket printed twice in one column, on two different lines --
// two separate notes, not one number shown twice.
const A4a = 'πρῶτον [fr. 27 FHG III 42] δεύτερον';
const A4b = 'τρίτον [fr. 27 FHG III 42] τέταρτον';
const book = (english = true): BookData => ({ book: 1, segments: [
  seg('A1', [A1], english),
  seg('A2', ['ἄλλος [p. 5 M.] ἔτι'], english),
  seg('A3', [A3], english),
  seg('A4', [A4a, A4b], english),
] });
const flush = (ms = 20) => new Promise((r) => setTimeout(r, ms));

afterEach(() => {
  window.history.replaceState(null, '', '/');
  // The view-change test below sets localStorage['reader-view'] via
  // setView -- clear it so a later test's mount() doesn't inherit a
  // non-default view (onMount restores it, which would hide the print
  // list behind `view !== 'english'`).
  try { localStorage.clear(); } catch {}
});

async function mount(english = true) {
  const r = render(Reader, { props: { work: 'DKNOTEFIX', bookNum: 1, bookData: book(english) } });
  await flush();
  return r.container;
}
const marks = (c: Element, col: string) => [...c.querySelectorAll<HTMLButtonElement>(`#col-${col} .greek-col .dk-note-mark`)];

describe('Reader.svelte DK edition notes', () => {
  for (const [view, english] of [['Both', true], ['Greek', false]] as const) {
    it(`${view} view: each reference becomes a numbered button, restarting per column; the rest stays in the line`, async () => {
      const c = await mount(english);
      expect(c.querySelector(`.reader-body.view-${view.toLowerCase()}`)).toBeTruthy();
      const a1 = marks(c, 'A1');
      expect(a1.map((b) => b.textContent)).toEqual(['1', '2']);
      expect(a1.map((b) => b.getAttribute('aria-label'))).toEqual(['Note 1', 'Note 2']);
      expect(a1.every((b) => b.type === 'button' && b.closest('sup.dk-note'))).toBe(true);
      expect(marks(c, 'A2').map((b) => b.getAttribute('aria-label'))).toEqual(['Note 1']);

      const lineText = c.querySelector('#col-A1 .greek-col .line-text')!.textContent!;
      expect(lineText).toBe('Ἀρίσταρχος1 καὶ [B 10] λόγος [sc. ῥήτορες] [504—501] ἔφη2.');
      // Every Greek word, including those beside a note, is still a lookup token.
      const toks = [...c.querySelectorAll('#col-A1 .greek-col .tok')].map((t) => t.textContent);
      expect(toks).toEqual(['Ἀρίσταρχος', 'καὶ', 'λόγος', 'ῥήτορες', 'ἔφη']);
    });
  }

  // The marker must never wrap away from the word before it (dk-edition-
  // notes.ts's applyEditionNotes glues the preceding render part onto the
  // note as `lead`); Reader.svelte wraps `lead` + the marker together in a
  // `white-space: nowrap` span, on the .fn-anchor/.fn-marker pattern.
  it('wraps the marker with the word right before it in one nowrap span, and the word stays a live lookup token', async () => {
    const c = await mount();
    const anchors = [...c.querySelectorAll<HTMLElement>('#col-A1 .greek-col .dk-note-anchor')];
    expect(anchors).toHaveLength(2);
    expect(anchors.map((a) => a.querySelector('.tok')?.textContent)).toEqual(['Ἀρίσταρχος', 'ἔφη']);
    expect(anchors.map((a) => a.querySelector('.dk-note-mark')?.textContent)).toEqual(['1', '2']);
    // Each anchor holds exactly its glued word and its own marker -- no
    // other Greek is pulled in with it.
    for (const a of anchors) expect(a.querySelectorAll('.tok')).toHaveLength(1);
    // The glued word is still the ordinary clickable lookup token: clicking
    // it activates it like any other.
    const [tok] = anchors[0].querySelectorAll<HTMLElement>('.tok');
    await fireEvent.click(tok!);
    await flush();
    expect(tok!.classList.contains('active')).toBe(true);
  });

  it('opens the note on click, shows the bracket as printed with its DK link, and closes on a second click', async () => {
    const c = await mount();
    const [first] = marks(c, 'A1');
    expect(first!.getAttribute('aria-expanded')).toBe('false');
    await fireEvent.click(first!);
    await flush();
    const pop = document.querySelector('.dk-note-pop')!;
    expect(pop).toBeTruthy();
    expect(pop.getAttribute('role')).toBe('dialog');
    expect(pop.getAttribute('aria-label')).toBe('Note 1');
    expect(pop.textContent).toBe('[fr. 173 Us.; A 2]');
    const link = pop.querySelector<HTMLAnchorElement>('a.dk-crossref')!;
    expect(link.textContent).toBe('A 2');
    expect(link.getAttribute('href')).toMatch(/\/read\/test-author\/DKNOTEFIX\/book-1#col-A2$/);
    expect(first!.getAttribute('aria-expanded')).toBe('true');
    expect(document.activeElement).toBe(pop);
    // Tab reaches the link; Tab past it closes the note.
    await fireEvent.keyDown(pop, { key: 'Tab' });
    expect(document.querySelector('.dk-note-pop')).toBeTruthy();
    link.focus();
    await fireEvent.keyDown(link, { key: 'Tab' });
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
    expect(document.activeElement).toBe(first);
    await fireEvent.click(first!);
    await flush();

    await fireEvent.click(first!);
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
    expect(first!.getAttribute('aria-expanded')).toBe('false');
  });

  it('closes on Escape (focus back on the marker) and on a click outside', async () => {
    const c = await mount();
    const [, second] = marks(c, 'A1');
    await fireEvent.click(second!);
    await flush();
    expect(document.querySelector('.dk-note-pop')?.textContent).toBe('[II 253, 28]');
    await fireEvent.keyDown(document.querySelector('.dk-note-pop')!, { key: 'Escape' });
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
    expect(document.activeElement).toBe(second);

    // Tab from a note with no link leaves it, back to the marker.
    await fireEvent.click(second!);
    await flush();
    await fireEvent.keyDown(document.querySelector('.dk-note-pop')!, { key: 'Tab' });
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
    expect(document.activeElement).toBe(second);

    await fireEvent.click(second!);
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeTruthy();
    await fireEvent.pointerDown(c.querySelector('#col-A1 .tok')!);
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
  });

  it('lists each column\'s notes by number for print', async () => {
    const c = await mount();
    const list = (col: string) => [...c.querySelectorAll(`#col-${col} > ol.dk-note-list > li`)]
      .map((li) => [li.getAttribute('value'), li.textContent]);
    expect(list('A1')).toEqual([['1', '[fr. 173 Us.; A 2]'], ['2', '[II 253, 28]']]);
    expect(list('A2')).toEqual([['1', '[p. 5 M.]']]);
  });

  it('leaves a bracket that is its whole line alone -- no note, no print list (Democritus B39/B61 shape)', async () => {
    const c = await mount();
    expect(marks(c, 'A3')).toHaveLength(0);
    expect(c.querySelector('#col-A3 .greek-col .line-text')!.textContent).toBe(A3);
    expect(c.querySelector('#col-A3 > ol.dk-note-list')).toBeNull();
  });

  it('leaves the English untouched', async () => {
    const c = await mount();
    expect(c.querySelectorAll('.english-col .dk-note-mark')).toHaveLength(0);
  });

  // GPT-6-Sol review, 2026-09-28, fault 1: open a note, then switch to
  // English -- the Greek marker's column hides (view-english's CSS), but
  // the pop-up used to stay open and keep focus on a now-invisible marker.
  it('closes an open note when the view changes away from the marker\'s column', async () => {
    const c = await mount();
    const [first] = marks(c, 'A1');
    await fireEvent.click(first!);
    await flush();
    expect(document.querySelector('.dk-note-pop')).toBeTruthy();
    const englishBtn = [...c.querySelectorAll('button')].find((b) => b.textContent === 'English')!;
    await fireEvent.click(englishBtn);
    await flush();
    expect(c.querySelector('.reader-body.view-english')).toBeTruthy();
    expect(document.querySelector('.dk-note-pop')).toBeNull();
    expect(first!.getAttribute('aria-expanded')).toBe('false');
  });

  // GPT-6-Sol review, 2026-09-28, fault 2: Empedocles testimonia A1 prints
  // "[fr. 27 FHG III 42]" twice (lines 16 and 33) -- the old `seen`-by-text
  // numbering gave both occurrences the same number and one print entry,
  // and opening either marker set aria-expanded on both.
  describe('the identical bracket printed twice in one column', () => {
    it('numbers each occurrence separately, and print lists both', async () => {
      const c = await mount();
      const a4 = marks(c, 'A4');
      expect(a4.map((b) => b.textContent)).toEqual(['1', '2']);
      expect(a4.map((b) => b.getAttribute('aria-label'))).toEqual(['Note 1', 'Note 2']);
      const list = [...c.querySelectorAll('#col-A4 > ol.dk-note-list > li')]
        .map((li) => [li.getAttribute('value'), li.textContent]);
      expect(list).toEqual([['1', '[fr. 27 FHG III 42]'], ['2', '[fr. 27 FHG III 42]']]);
    });

    it('opens only the clicked marker -- the other, same-text marker stays collapsed', async () => {
      const c = await mount();
      const [first, second] = marks(c, 'A4');
      await fireEvent.click(first!);
      await flush();
      expect(first!.getAttribute('aria-expanded')).toBe('true');
      expect(second!.getAttribute('aria-expanded')).toBe('false');
      await fireEvent.click(first!); // close before opening the other
      await flush();
      await fireEvent.click(second!);
      await flush();
      expect(first!.getAttribute('aria-expanded')).toBe('false');
      expect(second!.getAttribute('aria-expanded')).toBe('true');
    });
  });
});
