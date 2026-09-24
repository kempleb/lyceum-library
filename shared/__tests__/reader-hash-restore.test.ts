import { render } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for the Sol blocker (Wave 1b Parmenides round): the
// Reader.svelte:1318 hash-restore branch was swapped from `parseBekker`
// (bekker-grammar-only) to the scheme-aware `parseLocation` so a non-bekker
// work's line-bearing hash (Parmenides' dot-joined "#B8.34") round-trips on
// reload/share, the same way a Bekker hash always has. The existing tests
// only covered `parseLocation` itself in isolation (citation.test.ts) — a
// revert of the Reader's own branch back to `parseBekker` left every test
// green, because nothing exercised the mounted Reader's onMount hash-restore
// code path at all. These do, for all four citation-scheme shapes the site
// carries: bekker (line-bearing), dk verse (line-bearing, dot-joined — the
// actual regression case), book-section and flat section (both lineless, so
// they fall through to the bare-id/segment fallback either way — pinned here
// for completeness, not because they're revert-sensitive).
//
// Must-fail proof (verified by hand): temporarily revert the branch at
// Reader.svelte:~1318 to `const ref = parseBekker(hash);` — the bekker and
// lineless (book-section/section) cases here still pass (parseBekker returns
// null for a lineless hash exactly like parseLocation does, so both take the
// same fallback path), but the dk-verse case fails on both assertions: no
// element with id "LB8-34" ever receives scrollIntoView (parseBekker can't
// parse "B8.34" at all, and neither "B8.34" nor "col-B8.34" exist as element
// ids, so the fallback finds nothing either), and the lastCite check fails
// because lastCite is never set, so the scroll-spy's change-guard doesn't
// suppress a redundant `history.replaceState` the way it should once the
// hash has already been restored.
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
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte hash-restore regression test.',
  };
  const fixtures: Record<string, Work> = {
    HRB: { id: 'HRB', title: 'Fixture Bekker Work', abbr: 'HRB', ...common },
    HRD: {
      id: 'HRD', title: 'Fixture DK Verse Work', abbr: 'HRD', ...common,
      citation: { scheme: 'dk', lines: true, series: 'B' },
    },
    HRS: {
      id: 'HRS', title: 'Fixture Book-Section Work', abbr: 'HRS', ...common,
      citation: { scheme: 'book-section' },
    },
    HRF: {
      id: 'HRF', title: 'Fixture Flat-Section Work', abbr: 'HRF', ...common,
      citation: { scheme: 'section' },
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(column: string, n: number, role?: 'text' | 'context'): BookData {
  return {
    book: 1,
    segments: [
      {
        id: `seg-${column}`,
        column,
        greek: [
          { n, text: 'λόγος ἀρετή', tokens: [{ t: 'λόγος', o: 0, k: 'logos' }, { t: 'ἀρετή', o: 6, k: 'areth' }],
            ...(role ? { role } : {}) },
        ],
        english: { text: 'Virtue is discussed here.', notes: [], markers: [] },
      },
    ],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

beforeEach(() => {
  (Element.prototype.scrollIntoView as unknown as { mockClear: () => void }).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte hash restoration across citation schemes (Sol blocker 2)', () => {
  it('restores a bekker line hash (#1097a15) to the Greek line, tinted, with lastCite in bekker form', async () => {
    window.history.replaceState(null, '', '/HRB/book/1#1097a15');
    let ioCallback: IntersectionObserverCallback | undefined;
    class CapturingIO {
      constructor(cb: IntersectionObserverCallback) { ioCallback = cb; }
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() { return []; }
    }
    vi.stubGlobal('IntersectionObserver', CapturingIO);

    render(Reader, { props: { work: 'HRB', bookNum: 1, bookData: bookWith('1097a', 15) } });
    await flush();

    const target = document.getElementById('L1097a-15');
    expect(target).toBeTruthy();
    expect(target).toHaveClass('target');
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);

    // Arm the scroll-spy and replay the SAME element as the intersecting one
    // — citeOf(target) recomputes "1097a15", which must already equal the
    // lastCite the restore branch set, so updateHash's change-guard must
    // suppress a redundant history.replaceState. The initial restore sets a
    // 1500ms suppression window (onScrollArm ignores our own programmatic
    // jump's scroll); clear it before dispatching the "genuine" scroll.
    await flush(1600);
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(ioCallback).toBeTruthy();
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    ioCallback!(
      [{ target, isIntersecting: true, boundingClientRect: { top: 5 } } as unknown as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
    expect(replaceStateSpy).not.toHaveBeenCalled();
  });

  it('restores a dk verse dot-joined hash (#B8.34) to the Greek line, tinted, with lastCite in dot form', async () => {
    window.history.replaceState(null, '', '/HRD/book/1#B8.34');
    let ioCallback: IntersectionObserverCallback | undefined;
    class CapturingIO {
      constructor(cb: IntersectionObserverCallback) { ioCallback = cb; }
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() { return []; }
    }
    vi.stubGlobal('IntersectionObserver', CapturingIO);

    render(Reader, { props: { work: 'HRD', bookNum: 1, bookData: bookWith('B8', 34, 'text') } });
    await flush();

    const target = document.getElementById('LB8-34');
    expect(target).toBeTruthy();
    expect(target).toHaveClass('target');
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);

    // Same change-guard check as the bekker case above, but this is the
    // actual revert-sensitive assertion: under `parseBekker`, "B8.34" never
    // parses, lastCite is never set, and this call WOULD fire.
    await flush(1600);
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(ioCallback).toBeTruthy();
    const replaceStateSpy = vi.spyOn(window.history, 'replaceState');
    ioCallback!(
      [{ target, isIntersecting: true, boundingClientRect: { top: 5 } } as unknown as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
    expect(replaceStateSpy).not.toHaveBeenCalled();
  });

  it('restores a book-section dotted hash (#4.23) to the owning segment (lineless — no line-level target)', async () => {
    window.history.replaceState(null, '', '/HRS/book/1#4.23');
    render(Reader, { props: { work: 'HRS', bookNum: 1, bookData: bookWith('4.23', 1) } });
    await flush();

    const target = document.getElementById('col-4.23');
    expect(target).toBeTruthy();
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);
  });

  it('restores a flat-section hash (#5) to the owning segment (lineless — no line-level target)', async () => {
    window.history.replaceState(null, '', '/HRF/book/1#5');
    render(Reader, { props: { work: 'HRF', bookNum: 1, bookData: bookWith('5', 1) } });
    await flush();

    const target = document.getElementById('col-5');
    expect(target).toBeTruthy();
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);
  });

  // Lyceum partner manifest fix (John and Opus, 2026-09-12): navigation.loci
  // hrefs lowercase only the URL fragment (the partner schema's fragment
  // pattern is lowercase-only), so a mixed-case column like "B30" produces
  // "#col-b30" while the reader's own element id stays "col-B30". Neither of
  // the exact-case lookups (document.getElementById(hash) or
  // `col-${hash}`) matches; the case-insensitive fallback must.
  it('restores a lowercased col- hash (#col-b30) to the mixed-case element (col-B30)', async () => {
    window.history.replaceState(null, '', '/HRS/book/1#col-b30');
    render(Reader, { props: { work: 'HRS', bookNum: 1, bookData: bookWith('B30', 1) } });
    await flush();

    const target = document.getElementById('col-B30');
    expect(target).toBeTruthy();
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect((Element.prototype.scrollIntoView as ReturnType<typeof vi.fn>).mock.instances).toContain(target);
  });
});
