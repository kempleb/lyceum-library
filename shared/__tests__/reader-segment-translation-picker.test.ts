import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Item 84 (REVIEW-CHECKLIST): generalizes the per-passage translation picker
// (item 82's context-English toggle) to every ordinary fragment/testimonium
// segment where the WORK carries 2+ translations and 2+ of them have actual
// text for THAT segment -- John: "I like the trans picker so much that we
// should have this individually for every fragment and testimonium where we
// have several translations... means fewer fragments and testimonia will
// have the 'NO ENGLISH' displayed if looking at Burnet." The work-level
// <select> (.rc-trans-select) is unchanged and stays every segment's
// default; a per-passage click overrides display for that segment only,
// page-local, no persistence.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const twoTrans: Work = {
    id: 'SEGPICKFIX', title: 'Fixture Two-Translation Work', abbr: 'Fix. C', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. C', dkChapter: 1, series: 'B' },
    translations: [
      { id: 'freeman', name: 'Kathleen Freeman (1948)', short: 'Freeman', slot: 'english' as const },
      { id: 'burnet', name: 'John Burnet (1920)', short: 'Burnet', slot: 'secondary' as const },
    ],
    blurb: 'Fixture work for the Reader.svelte per-segment translation picker test.',
  };
  // Item 84's real-world shape (Gorgias B11/B11a, 2026-07-28): the primary
  // 'english' slot carries a CREDITED alternate translation (the Parnassos
  // swap), and a further 'overlay'-slot translation carries Freeman's own
  // displaced summary, labelled unambiguously as a summary. The registry's
  // primary-slot `short` deliberately stays "Freeman" here (the work's usual
  // translation name) even though the CREDITED chunk is someone else's --
  // this is exactly the mislabel John caught live: the toggle must derive
  // the primary option's label from the displayed chunk's own credit, never
  // from the slot's work-level short.
  const summaryOverlayWork: Work = {
    id: 'SEGPICKFIX2', title: 'Fixture Summary-Overlay Work', abbr: 'Fix. E', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. E', dkChapter: 1, series: 'B' },
    translations: [
      { id: 'freeman', name: 'Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Blackwell, 1948)', short: 'Freeman', slot: 'english' as const },
      // Fix round, finding 6 (Sol xhigh review): `kind: 'summary'` is what
      // Reader.svelte's engCreditFor reads to label a copy of this overlay's
      // text distinctly from a copy of an actual translation.
      // Fix round (Sol re-verify): production-shaped name (see
      // shared/lib/works.ts's real freeman-summary entry) -- the prior
      // fixture name ('Kathleen Freeman (1948) — summary') had no comma
      // and no title, so engCreditFor's `t.name.split(' (')[0]` masked
      // whether the split does anything real against production data.
      { id: 'freeman-summary', name: 'Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers', short: 'Freeman (summary)', slot: 'overlay' as const, kind: 'summary' as const },
    ],
    blurb: 'Fixture work for the item-84 summary-overlay picker test.',
  };
  const oneTrans: Work = {
    id: 'SEGPICKFIX1', title: 'Fixture One-Translation Work', abbr: 'Fix. D', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. D', dkChapter: 1, series: 'B' },
    translations: [
      { id: 'freeman', name: 'Kathleen Freeman (1948)', short: 'Freeman', slot: 'english' as const },
    ],
    blurb: 'Fixture work for the Reader.svelte single-translation regression.',
  };
  return {
    ...actual,
    getWork: (id: string) => {
      if (id === 'SEGPICKFIX') return twoTrans;
      if (id === 'SEGPICKFIX1') return oneTrans;
      if (id === 'SEGPICKFIX2') return summaryOverlayWork;
      return actual.getWork(id);
    },
    workPath: (id: string, book = 1) =>
      (id === 'SEGPICKFIX' || id === 'SEGPICKFIX1' || id === 'SEGPICKFIX2')
        ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(): BookData {
  return {
    book: 1,
    segments: [
      // Both translations carry text -- toggle renders, 2 buttons.
      {
        id: 'seg-both', column: 'B1',
        greek: [{ n: 1, text: 'Greek of B1', tokens: [], role: 'context' }],
        english: { text: 'Freeman text for B1.', notes: [], markers: [] },
        ross: [{ chapter: '', text: 'Burnet text for B1.', cont: true }],
      },
      // A second both-translations segment, to prove one segment's override
      // never leaks onto another.
      {
        id: 'seg-both2', column: 'B2',
        greek: [{ n: 1, text: 'Greek of B2', tokens: [], role: 'context' }],
        english: { text: 'Freeman text for B2.', notes: [], markers: [] },
        ross: [{ chapter: '', text: 'Burnet text for B2.', cont: true }],
      },
      // Only Freeman (the currently-selected work-level default) has text --
      // no toggle, even though the work carries 2 translations.
      {
        id: 'seg-freeman-only', column: 'B3',
        greek: [{ n: 1, text: 'Greek of B3', tokens: [], role: 'context' }],
        english: { text: 'Freeman-only text for B3.', notes: [], markers: [] },
      },
      // Only Burnet has text; Freeman (selected by default) has none -- the
      // existing "Not in X -- see Y" note still fires, no toggle (only one
      // translation carries text here).
      {
        id: 'seg-burnet-only', column: 'B4',
        greek: [{ n: 1, text: 'Greek of B4', tokens: [], role: 'context' }],
        english: null,
        ross: [{ chapter: '', text: 'Burnet-only text for B4.', cont: true }],
      },
      // A segment whose own primary English carries a per-passage credit
      // (EnglishChunk.credit) AND a Burnet alternate with text -- the credit
      // must follow the DISPLAYED chunk, not leak onto the alternate.
      {
        id: 'seg-credit', column: 'B5',
        greek: [{ n: 1, text: 'Greek of B5', tokens: [], role: 'context' }],
        english: {
          text: 'Freeman credited text for B5.', notes: [], markers: [],
          credit: { translator: 'Smith', source: 'Some Edition', year: 1900 },
        },
        ross: [{ chapter: '', text: 'Burnet text for B5.', cont: true }],
      },
    ],
  };
}

function bookSummaryOverlay(): BookData {
  return {
    book: 1,
    segments: [
      // Item 84's real shape: the primary chunk is a CREDITED alternate
      // (the Parnassos-style swap), the summary lives in overlays[id].
      {
        id: 'seg-b11', column: 'B11',
        greek: [{ n: 1, text: 'Greek of B11', tokens: [], role: 'context' }],
        english: {
          text: 'Gatt translation for B11.', notes: [], markers: [],
          credit: { translator: 'Jurgen R. Gatt', source: 'Fixture Press', year: 2022 },
        },
        overlays: { 'freeman-summary': [{ chapter: 'B11', text: "('Encomium on Helen': summary) Freeman's summary for B11.", cont: false, bekker: [] }] },
      },
    ],
  };
}

// Item 85 review (John's live-review layout ruling): the real Gorgias B11
// shape -- wholeColumnVerbatim + a per-passage credit -- PLUS a summary
// overlay whose own text carries the identical ascending "(N)" markers
// (attested for the real freeman-summary overlay by stage1_freeman_
// english.py's own section-count cross-check; see Reader.svelte's
// sectionRowsFor doc comment). Exercises the row split together with the
// per-passage toggle: switching translations must swap each ROW's English
// cell, not just the column as a whole.
function bookRowSplitOverlay(): BookData {
  return {
    book: 1,
    segments: [{
      id: 'seg-b11-rows', column: 'B11', wholeColumnVerbatim: true,
      greek: [
        { n: 1, text: 'ΤΙΤΛΕ', tokens: [], role: 'context' },
        { n: 2, text: '(1) Greek section one. (2) Greek section two.', tokens: [], role: 'context' },
      ],
      english: {
        text: 'Heading. (1) English section one. (2) English section two.',
        notes: [], markers: [],
        credit: { translator: 'Jurgen R. Gatt', source: 'Fixture Press', year: 2022 },
      },
      overlays: {
        'freeman-summary': [{
          chapter: 'B11',
          text: 'Summary heading. (1) Summary section one. (2) Summary section two.',
          cont: false, bekker: [],
        }],
      },
    }],
  };
}

function bookSingleTrans(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-only', column: 'C1',
        greek: [{ n: 1, text: 'Greek of C1', tokens: [], role: 'context' }],
        english: { text: 'Only translation for C1.', notes: [], markers: [] },
      },
    ],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
  // The "work-level translation switch" test below is the only one that
  // persists a choice (setTrans writes reader-trans-${work} to
  // localStorage) -- clear it so later tests see this file's fixture works
  // at their true first-load default (the primary 'english'-slot id),
  // rather than whatever a prior test left behind.
  localStorage.clear();
});

describe('Reader.svelte per-segment translation picker (item 84)', () => {
  it('renders the toggle with both short labels when 2+ translations carry text for the segment', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const toggle = document.querySelector('#col-B1 .seg-trans-toggle');
    expect(toggle).not.toBeNull();
    const labels = Array.from(toggle?.querySelectorAll('.seg-trans-btn') ?? [])
      .map((b) => b.textContent?.trim());
    expect(labels).toEqual(['Freeman', 'Burnet']);
    // The work-level default (Freeman, the primary slot) is active.
    expect(toggle?.querySelector('.seg-trans-btn.active')?.textContent?.trim()).toBe('Freeman');
  });

  it('clicking the alternate button swaps the displayed English to that translation\'s text', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B1') as HTMLElement;
    const col = seg.querySelector('.english-col') as HTMLElement;
    expect(col.textContent).toContain('Freeman text for B1.');
    // The toggle lives on the segment's .seg-ref line now (translator-picker
    // alignment fix), not inside .english-col -- look it up from the segment.
    const burnetBtn = Array.from(seg.querySelectorAll('.seg-trans-btn'))
      .find((b) => b.textContent?.trim() === 'Burnet') as HTMLElement;
    await fireEvent.click(burnetBtn);
    await flush();
    expect(col.textContent).toContain('Burnet text for B1.');
    expect(col.textContent).not.toContain('Freeman text for B1.');
    expect(burnetBtn.classList.contains('active')).toBe(true);
  });

  it('a per-segment override on one segment does not affect another segment', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg1 = document.querySelector('#col-B1') as HTMLElement;
    const burnetBtn1 = Array.from(seg1.querySelectorAll('.seg-trans-btn'))
      .find((b) => b.textContent?.trim() === 'Burnet') as HTMLElement;
    await fireEvent.click(burnetBtn1);
    await flush();
    const col2 = document.querySelector('#col-B2 .english-col') as HTMLElement;
    expect(col2.textContent).toContain('Freeman text for B2.');
    expect(document.querySelector('#col-B2 .seg-trans-btn.active')?.textContent?.trim()).toBe('Freeman');
  });

  it('a work-level translation switch repaints the non-overridden segment but leaves the overridden one alone', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    // Override seg-both (B1) to Burnet.
    const seg1 = document.querySelector('#col-B1') as HTMLElement;
    const col1 = seg1.querySelector('.english-col') as HTMLElement;
    const burnetBtn1 = Array.from(seg1.querySelectorAll('.seg-trans-btn'))
      .find((b) => b.textContent?.trim() === 'Burnet') as HTMLElement;
    await fireEvent.click(burnetBtn1);
    await flush();
    // Now flip the work-level picker to Burnet too.
    const select = document.querySelector('.rc-trans-select') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'burnet' } });
    await flush();
    // B1 (overridden) still shows Burnet -- unchanged by the work-level flip.
    expect(col1.textContent).toContain('Burnet text for B1.');
    // B2 (never overridden) now repaints to the new work-level selection.
    const col2 = document.querySelector('#col-B2 .english-col') as HTMLElement;
    expect(col2.textContent).toContain('Burnet text for B2.');
    expect(col2.textContent).not.toContain('Freeman text for B2.');
  });

  it('renders no toggle when only the currently-selected translation has text (work still carries 2)', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    // Scoped to the whole segment (not just .english-col, where the toggle
    // never lived even before it moved to .seg-ref) so this actually proves
    // absence rather than trivially passing.
    const seg = document.querySelector('#col-B3') as HTMLElement;
    expect(seg.querySelector('.seg-trans-toggle')).toBeNull();
    expect(seg.querySelector('.english-col')?.textContent).toContain('Freeman-only text for B3.');
  });

  it('shows the existing "not in X -- see Y" note with no toggle when only the OTHER translation has text', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B4') as HTMLElement;
    expect(seg.querySelector('.seg-trans-toggle')).toBeNull();
    const note = seg.querySelector('.trans-missing-note');
    expect(note?.textContent).toBe('Not in Freeman (1948) — see Burnet.');
  });

  it('credit follows the displayed chunk: showing Freeman keeps the credit and data-eng-credit', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const col = document.querySelector('#col-B5 .english-col') as HTMLElement;
    expect(col.querySelector('.translation-credit')?.textContent).toBe(
      'Translation: Smith, Some Edition, 1900.'
    );
    expect(col.getAttribute('data-eng-credit')).toBeTruthy();
  });

  it('credit follows the displayed chunk: switching to Burnet hides the Freeman credit and clears data-eng-credit', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B5') as HTMLElement;
    const col = seg.querySelector('.english-col') as HTMLElement;
    const burnetBtn = Array.from(seg.querySelectorAll('.seg-trans-btn'))
      .find((b) => b.textContent?.trim() === 'Burnet') as HTMLElement;
    await fireEvent.click(burnetBtn);
    await flush();
    expect(col.textContent).toContain('Burnet text for B5.');
    expect(col.querySelector('.translation-credit')).toBeNull();
    expect(col.hasAttribute('data-eng-credit')).toBe(false);
  });

  it('a single-translation work renders no toggle at all (byte-identical)', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX1', bookNum: 1, bookData: bookSingleTrans() } });
    await flush();
    expect(document.querySelector('.seg-trans-toggle')).toBeNull();
    expect(document.querySelector('#col-C1 .english-col')?.textContent).toContain('Only translation for C1.');
  });

  // Item 84 (REVIEW-CHECKLIST, 2026-07-28): Gorgias B11/B11a offer Freeman's
  // own DISPLACED summary back as a sparse 'overlay'-slot alternate beside
  // the credited Parnassos-style translation now shipped as the default.
  describe('summary-overlay alternate (item 84)', () => {
    it('the toggle offers "Freeman (summary)" alongside the default translation', async () => {
      render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookSummaryOverlay() } });
      await flush();
      const toggle = document.querySelector('#col-B11 .seg-trans-toggle');
      expect(toggle).not.toBeNull();
      const labels = Array.from(toggle?.querySelectorAll('.seg-trans-btn') ?? [])
        .map((b) => b.textContent?.trim());
      // The primary option reads "Gatt" -- the credited translator's own
      // surname -- never "Freeman", the registry short for this slot.
      expect(labels).toEqual(['Gatt', 'Freeman (summary)']);
      expect(labels).not.toContain('Freeman');
    });

    it('the label text includes "summary"', async () => {
      render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookSummaryOverlay() } });
      await flush();
      const btn = Array.from(document.querySelectorAll('#col-B11 .seg-trans-btn'))
        .find((b) => b.textContent?.trim().includes('summary')) as HTMLElement;
      expect(btn).toBeTruthy();
      expect(btn.textContent?.trim()).toBe('Freeman (summary)');
    });

    it('switching to the summary overlay swaps the displayed text, clears the Parnassos-style credit, and labels the copy a summary', async () => {
      render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookSummaryOverlay() } });
      await flush();
      const seg = document.querySelector('#col-B11') as HTMLElement;
      const col = seg.querySelector('.english-col') as HTMLElement;
      // Default (Gatt) shows its own credit.
      expect(col.textContent).toContain('Gatt translation for B11.');
      expect(col.querySelector('.translation-credit')?.textContent).toBe(
        'Translation: Jurgen R. Gatt, Fixture Press, 2022.'
      );
      expect(col.getAttribute('data-eng-credit')).toBeTruthy();

      const summaryBtn = Array.from(seg.querySelectorAll('.seg-trans-btn'))
        .find((b) => b.textContent?.trim() === 'Freeman (summary)') as HTMLElement;
      await fireEvent.click(summaryBtn);
      await flush();

      expect(col.textContent).toContain("Freeman's summary for B11.");
      expect(col.textContent).not.toContain('Gatt translation for B11.');
      // The Gatt-only credit must never leak onto the summary alternate --
      // neither rendered nor available to a copy-with-citation.
      expect(col.querySelector('.translation-credit')).toBeNull();
      // Fix round, finding 6 (Sol xhigh review): a copy of the summary must
      // still be distinguishable from a copy of an actual translation --
      // data-eng-credit now carries the registry's own name, marked
      // "(summary)", rather than being cleared outright. Full name, not a
      // truncated surname -- the fuller attribution is the better one
      // (Sol re-verify, ACCEPT production behavior).
      expect(col.getAttribute('data-eng-credit')).toBe(
        'Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (summary)'
      );
    });
  });

  // Item 85 review (John's live-review layout ruling): wholeColumnVerbatim
  // + credit routes through the row-aligned split (Reader.svelte's
  // sectionRowSplit/sectionRowsFor), not the single-.seg-row rendering the
  // rest of this file's tests exercise. The toggle must keep working
  // per-row: switching translations swaps every row's own English cell.
  describe('row-aligned split + per-passage toggle (item 85 review)', () => {
    it('renders one row per DK section, heading + 2, with the toggle in the heading row', async () => {
      const { container } = render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookRowSplitOverlay() } });
      await flush();

      const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
      expect(rows.length).toBe(3);
      // Translator-picker alignment fix: the toggle now lives once, on the
      // segment's .seg-ref line, rather than inside any row's English cell.
      expect(container.querySelector('#col-B11 .seg-ref .seg-trans-toggle')).toBeTruthy();
      expect(rows[0]!.querySelector('.seg-trans-toggle')).toBeNull();
      expect(rows[1]!.querySelector('.seg-trans-toggle')).toBeNull();
      expect(rows[2]!.querySelector('.seg-trans-toggle')).toBeNull();

      const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
      expect(engText(0)).toContain('Heading.');
      expect(engText(1)).toContain('(1) English section one.');
      expect(engText(2)).toContain('(2) English section two.');
    });

    // Fix round (Sol re-verify): `.frag-eng-card-bg`'s old `grid-row: 1 /
    // -1` (global.css) resolved against explicit grid rows, and this grid
    // declares none -- jsdom can't verify actual layout, so this pins the
    // explicit inline placement Reader.svelte now sets on every cell and
    // the bg instead: each row's own cells carry ascending `grid-row`
    // (1-indexed) with the Greek cell in column 1 and the English cell in
    // column 2, and the bg spans exactly `rows.length` rows in column 2.
    it('gives every row cell and the card background explicit, consistent grid placement', async () => {
      const { container } = render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookRowSplitOverlay() } });
      await flush();

      const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
      expect(rows.length).toBe(3);
      rows.forEach((row, i) => {
        const greek = row.querySelector('.greek-col') as HTMLElement;
        const eng = row.querySelector('.english-col') as HTMLElement;
        expect(greek.style.gridRow).toBe(String(i + 1));
        expect(greek.style.gridColumn).toBe('1');
        expect(eng.style.gridRow).toBe(String(i + 1));
        expect(eng.style.gridColumn).toBe('2');
      });

      const bg = container.querySelector('#col-B11 .frag-row-split .frag-eng-card-bg') as HTMLElement;
      expect(bg).toBeTruthy();
      expect(bg.style.gridRow).toBe(`1 / span ${rows.length}`);
      expect(bg.style.gridColumn).toBe('2');
    });

    it('switching to the summary overlay swaps EACH row\'s English cell to that overlay\'s own matching section', async () => {
      const { container } = render(Reader, { props: { work: 'SEGPICKFIX2', bookNum: 1, bookData: bookRowSplitOverlay() } });
      await flush();

      const summaryBtn = [...container.querySelectorAll('#col-B11 .seg-trans-btn')]
        .find((b) => b.textContent?.trim() === 'Freeman (summary)') as HTMLElement;
      expect(summaryBtn).toBeTruthy();
      await fireEvent.click(summaryBtn);
      await flush();

      const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
      expect(rows.length).toBe(3);
      const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
      expect(engText(0)).toContain('Summary heading.');
      expect(engText(0)).not.toContain('Heading.');
      expect(engText(1)).toContain('(1) Summary section one.');
      expect(engText(1)).not.toContain('English section one.');
      expect(engText(2)).toContain('(2) Summary section two.');
      expect(engText(2)).not.toContain('English section two.');
      // Fix round (Sol re-verify): the row-split branch sets its own
      // data-eng-credit per row (Reader.svelte ~3191), independent of the
      // single-.seg-row path this file's other summary-overlay test
      // already covers -- prove it carries the same "(summary)" label on
      // every row, not just the toggle row.
      const engCredit = (i: number) => rows[i]!.querySelector('.english-col')?.getAttribute('data-eng-credit');
      for (let i = 0; i < 3; i++) {
        expect(engCredit(i)).toBe('Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (summary)');
      }
    });
  });
});

// Stage 1 of the `ross` -> `secondary` slot rename. The pipeline still emits
// the second translation under `seg.ross`, so Reader.svelte's piecesFor reads
// `seg.secondary ?? seg.ross`. Every other fixture in this file feeds the
// legacy key, which covers the fallback arm; these two cover the new key and
// the precedence between them.
describe('Reader.svelte secondary-slot field name (ross -> secondary)', () => {
  function bookSecondaryKey(): BookData {
    return {
      book: 1,
      segments: [
        // New field name alone -- must render just like the legacy one.
        {
          id: 'seg-secondary', column: 'C1',
          greek: [{ n: 1, text: 'Greek of C1', tokens: [], role: 'context' }],
          english: { text: 'Freeman text for C1.', notes: [], markers: [] },
          secondary: [{ chapter: '', text: 'Burnet text for C1.', cont: true }],
        },
        // Both names present -- `secondary` wins, `ross` is never read.
        {
          id: 'seg-both-keys', column: 'C2',
          greek: [{ n: 1, text: 'Greek of C2', tokens: [], role: 'context' }],
          english: { text: 'Freeman text for C2.', notes: [], markers: [] },
          secondary: [{ chapter: '', text: 'Burnet from secondary.', cont: true }],
          ross: [{ chapter: '', text: 'Burnet from legacy ross.', cont: true }],
        },
      ],
    };
  }

  it('renders a secondary-slot translation emitted under `secondary`', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookSecondaryKey() } });
    await flush();
    const select = document.querySelector('.rc-trans-select') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'burnet' } });
    await flush();
    const col = document.querySelector('#col-C1 .english-col') as HTMLElement;
    expect(col.textContent).toContain('Burnet text for C1.');
  });

  it('prefers `secondary` over the legacy `ross` when a segment carries both', async () => {
    render(Reader, { props: { work: 'SEGPICKFIX', bookNum: 1, bookData: bookSecondaryKey() } });
    await flush();
    const select = document.querySelector('.rc-trans-select') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'burnet' } });
    await flush();
    const col = document.querySelector('#col-C2 .english-col') as HTMLElement;
    expect(col.textContent).toContain('Burnet from secondary.');
    expect(col.textContent).not.toContain('Burnet from legacy ross.');
  });
});
