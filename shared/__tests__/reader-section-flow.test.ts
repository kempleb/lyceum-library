import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader, { sectionFlowSpyLabel } from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Section-flow presentation (docs/section-flow-plan.md, stages 1–4): a
// book-section work that opts in drops per-section furniture for a
// non-copying gutter/inline tick. Flag default off; no corpus work sets it.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const common = {
    author: 'Test',
    language: 'lat' as const,
    workType: 'continuous' as const,
    books: 1,
    bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    blurb: 'Fixture work for the Reader.svelte section-flow test.',
  };
  const off: Work = {
    id: 'SECFLOWOFF', title: 'Fixture Section-Flow Off', abbr: 'Fix. SFO', ...common,
    citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. SFO' },
    translations: [{ id: 'king', name: 'King (1927)', short: 'King', slot: 'english' as const }],
  };
  const on: Work = {
    id: 'SECFLOWON', title: 'Fixture Section-Flow On', abbr: 'Fix. SFN', ...common,
    citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. SFN', sectionFlow: true },
    translations: [{ id: 'king', name: 'King (1927)', short: 'King', slot: 'english' as const }],
  };
  const two: Work = {
    id: 'SECFLOW2T', title: 'Fixture Section-Flow Two-Trans', abbr: 'Fix. SF2', ...common,
    citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. SF2', sectionFlow: true },
    translations: [
      { id: 'hicks', name: 'Hicks (1925)', short: 'Hicks', slot: 'english' as const },
      { id: 'yonge', name: 'Yonge (1853)', short: 'Yonge', slot: 'secondary' as const },
    ],
  };
  return {
    ...actual,
    getWork: (id: string) => {
      if (id === 'SECFLOWOFF') return off;
      if (id === 'SECFLOWON') return on;
      if (id === 'SECFLOW2T') return two;
      return actual.getWork(id);
    },
    workPath: (id: string, book = 1) =>
      (id === 'SECFLOWOFF' || id === 'SECFLOWON' || id === 'SECFLOW2T')
        ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookThree(opts?: { titled?: boolean; twoTrans?: boolean }): BookData {
  const titled = opts?.titled !== false;
  return {
    book: 1,
    segments: [
      {
        id: 'seg-1.1', column: '1.1',
        greek: [{ n: 1, text: 'Primum igitur', tokens: [{ t: 'Primum', o: 0, k: 'primum' }] }],
        english: { text: 'First, then.', notes: [], markers: [] },
        ...(opts?.twoTrans ? { ross: [{ chapter: '', text: 'First, Yonge.', cont: true }] } : {}),
      },
      {
        id: 'seg-1.2', column: '1.2',
        greek: [{ n: 1, text: 'Deinde', tokens: [{ t: 'Deinde', o: 0, k: 'deinde' }] }],
        english: {
          text: 'Next.', notes: [], markers: [],
          ...(titled ? { title: 'On the next point' } : {}),
        },
        ...(opts?.twoTrans ? { ross: [{ chapter: '', text: 'Next, Yonge.', cont: true }] } : {}),
      },
      {
        id: 'seg-1.3', column: '1.3',
        greek: [{ n: 1, text: 'Postremo', tokens: [{ t: 'Postremo', o: 0, k: 'postremo' }] }],
        english: { text: 'Lastly.', notes: [], markers: [] },
        ...(opts?.twoTrans ? { ross: [{ chapter: '', text: 'Lastly, Yonge.', cont: true }] } : {}),
      },
    ],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
});

describe('Reader.svelte section-flow (docs/section-flow-plan.md)', () => {
  it('flag off: every segment keeps .seg-ref > .seg-ref-label; no ticks; no section-flow class', async () => {
    const { container } = render(Reader, {
      props: { work: 'SECFLOWOFF', bookNum: 1, bookData: bookThree() },
    });
    await flush();

    const body = container.querySelector('.reader-body');
    expect(body?.classList.contains('section-flow')).toBe(false);

    const segs = [...container.querySelectorAll('.segment')];
    expect(segs).toHaveLength(3);
    for (const seg of segs) {
      expect(seg.querySelector('.seg-ref > .seg-ref-label')).not.toBeNull();
    }
    expect(container.querySelectorAll('.sect-tick')).toHaveLength(0);
    expect(container.querySelectorAll('.sect-tick-inline')).toHaveLength(0);
  });

  it('flag on: ordinary segments drop the label, emit one gutter tick and one source + one English inline tick; titled segment keeps .seg-ref; ids stay unique on .segment', async () => {
    const { container } = render(Reader, {
      props: { work: 'SECFLOWON', bookNum: 1, bookData: bookThree() },
    });
    await flush();

    const body = container.querySelector('.reader-body');
    expect(body?.classList.contains('section-flow')).toBe(true);

    const ordinary = ['1.1', '1.3'].map((col) => container.querySelector(`[id="col-${col}"]`) as HTMLElement);
    for (const seg of ordinary) {
      expect(seg).toBeTruthy();
      expect(seg.querySelector('.seg-ref-label')).toBeNull();
      const ticks = [...seg.querySelectorAll('.sect-tick')];
      expect(ticks).toHaveLength(1);
      expect(ticks[0]!.getAttribute('data-n')).toBe(seg.id.replace(/^col-/, ''));
      expect(ticks[0]!.textContent).toBe('');
      expect(ticks[0]!.getAttribute('aria-hidden')).toBe('true');
      expect(ticks[0]!.id).toBe('');

      const sourceInline = seg.querySelector('.greek-col .sect-tick-inline') as HTMLElement;
      const engInline = seg.querySelector('.english-col .sect-tick-inline') as HTMLElement;
      expect(sourceInline).toBeTruthy();
      expect(engInline).toBeTruthy();
      expect(sourceInline.getAttribute('data-n')).toBe(seg.id.replace(/^col-/, ''));
      expect(engInline.getAttribute('data-n')).toBe(seg.id.replace(/^col-/, ''));
      expect(sourceInline.textContent).toBe('');
      expect(engInline.textContent).toBe('');
      expect(sourceInline.getAttribute('aria-hidden')).toBe('true');
      expect(engInline.getAttribute('aria-hidden')).toBe('true');
    }

    const titled = container.querySelector('[id="col-1.2"]') as HTMLElement;
    expect(titled.querySelector('.seg-ref > .seg-ref-label')).not.toBeNull();
    expect(titled.querySelector('.seg-ref-title')?.textContent).toContain('On the next point');

    const segs = [...container.querySelectorAll('.segment')];
    expect(segs.map((s) => s.id)).toEqual(['col-1.1', 'col-1.2', 'col-1.3']);
    const colIds = [...container.querySelectorAll('[id^="col-"]')].map((el) => el.id);
    expect(new Set(colIds).size).toBe(colIds.length);
  });

  it('flag on with 2 translations: segTransToggle still renders inside .seg-ref--flow', async () => {
    const { container } = render(Reader, {
      props: { work: 'SECFLOW2T', bookNum: 1, bookData: bookThree({ titled: false, twoTrans: true }) },
    });
    await flush();

    const flowRef = container.querySelector('[id="col-1.1"] .seg-ref--flow');
    expect(flowRef).not.toBeNull();
    expect(flowRef?.querySelector('.seg-trans-toggle')).not.toBeNull();
    const labels = [...(flowRef?.querySelectorAll('.seg-trans-btn') ?? [])]
      .map((b) => b.textContent?.trim());
    expect(labels).toEqual(['Hicks', 'Yonge']);
  });

  it('sectionFlowSpyLabel strips the col- prefix', () => {
    expect(sectionFlowSpyLabel('col-1.1')).toBe('1.1');
    expect(sectionFlowSpyLabel('col-12.34')).toBe('12.34');
    expect(sectionFlowSpyLabel('1.1')).toBe('1.1');
  });
});
