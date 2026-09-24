import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for task #33 (scroll-sync perf debt found in Grok's
// review, before Diogenes Laertius-scale books ship): updateChapterContext /
// updateActiveNav used to re-run querySelectorAll (plus a getElementById per
// nav anchor) and rewrite classList/aria-current on EVERY rAF-throttled
// scroll tick, with no change guard. At Diogenes scale (100-202
// sections/book) that's a per-tick cost that scales with book size. The fix
// caches the anchor/target lookups and only mutates the DOM when the
// highlighted entry actually changes — this test exercises that cache
// through repeated 'scroll' events and asserts the DOM lookups/mutations
// don't grow with the number of ticks once the highlighted entry settles.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixtures: Record<string, Work> = {
    SS: {
      id: 'SS', title: 'Fixture Scroll-Sync Work', abbr: 'SS', author: 'Test',
      language: 'grc', workType: 'continuous',
      books: 1, bookLabels: ['1'],
      greekEdition: 'Test edition',
      greekSource: { short: 'Test', full: 'Test edition, full citation.' },
      translations: [{ id: 'rackham', name: 'Test Translator (Test, 1900)', short: 'Rackham', slot: 'english' }],
      blurb: 'Fixture work for the Reader.svelte scroll-sync perf regression test.',
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

const fixtureBook: BookData = {
  book: 1,
  segments: [
    {
      id: 'seg1',
      column: '1094a',
      greek: [
        { n: 1, text: 'λόγος ἀρετή', tokens: [{ t: 'λόγος', o: 0, k: 'logos' }, { t: 'ἀρετή', o: 6, k: 'areth' }] },
      ],
      english: {
        text: 'Virtue is discussed here.',
        notes: [],
        markers: [],
        bekker: [{ n: 1, offset: 0, real: true }],
      },
      chapterStarts: [{ chapter: '1', beforeLine: 1, wordIndex: 0, engOffset: 0, bekker: '1094a' }],
    },
  ],
};

function rect(top: number): DOMRect {
  return { top, bottom: top + 20, left: 0, right: 0, width: 0, height: 20, x: 0, y: top, toJSON() {} } as DOMRect;
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  document.querySelectorAll('.chapter-nav, .toc-outline').forEach((el) => el.remove());
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte scroll-sync perf (task #33)', () => {
  it('caches nav/context DOM lookups and only mutates classList when the highlighted entry changes', async () => {
    window.history.replaceState(null, '', '/SS/book/1');
    render(Reader, { props: { work: 'SS', bookNum: 1, bookData: fixtureBook } });

    // Stand in for ReaderShell.astro's static contents surfaces, which live
    // outside this Svelte island in the real app.
    const nav = document.createElement('nav');
    nav.className = 'chapter-nav';
    nav.innerHTML = '<a data-ch="ch-1-1">Ch 1</a>';
    document.body.appendChild(nav);
    const toc = document.createElement('nav');
    toc.className = 'toc-outline';
    toc.innerHTML = '<a data-ch="ch-1-1">Ch 1</a>';
    document.body.appendChild(toc);

    // The chapter head renders synchronously with the initial template (it
    // doesn't wait on onMount) — stub its position below the detection
    // boundary before onMount's first updateChapterContext() call runs, so
    // the initial (nothing-highlighted-yet) state is deterministic too.
    const target = document.getElementById('ch-1-1');
    expect(target).toBeTruthy();
    target!.getBoundingClientRect = vi.fn(() => rect(500));

    // Let onMount's setTimeout(0) run: wires the scroll/resize listeners and
    // fires the initial updateChapterContext() call.
    await flush();
    expect(nav.querySelector('a')).not.toHaveClass('current');

    const qsaSpy = vi.spyOn(document, 'querySelectorAll');
    const classListProto = Object.getPrototypeOf(nav.querySelector('a')!.classList);
    const addSpy = vi.spyOn(classListProto, 'add');
    const removeSpy = vi.spyOn(classListProto, 'remove');

    // First scroll: still below the boundary (also arms the spy, which
    // rebuilds the caches once — that's expected and is not the thing under
    // test here).
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(nav.querySelector('a')).not.toHaveClass('current');

    // Scroll the chapter head above the detection boundary.
    target!.getBoundingClientRect = vi.fn(() => rect(0));
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(nav.querySelector('a')).toHaveClass('current');
    expect(nav.querySelector('a')).toHaveAttribute('aria-current', 'location');
    expect(toc.querySelector('a')).toHaveClass('current');

    const rcContext = document.querySelector('.rc-context');
    const liveChapterText = rcContext?.textContent;

    // Caches are warm and the highlighted entry has settled. From here,
    // repeated identical scroll ticks (the steady state during a long,
    // continuous scroll through a Diogenes-scale book) must not re-query the
    // DOM or re-touch classList/aria-current — that's the M1/M2 fix.
    const qsaCallsBaseline = qsaSpy.mock.calls.length;
    const addCallsBaseline = addSpy.mock.calls.length;
    for (let i = 0; i < 25; i++) {
      window.dispatchEvent(new Event('scroll'));
      await flush(5);
    }

    expect(qsaSpy.mock.calls.length).toBe(qsaCallsBaseline);
    expect(addSpy.mock.calls.length).toBe(addCallsBaseline);
    expect(removeSpy.mock.calls.length).toBe(0);
    // The sticky heading text is likewise unchanged, and (m2) the reactive
    // liveChapter assignment guard means it was never rewritten either.
    expect(document.querySelector('.rc-context')?.textContent).toBe(liveChapterText);

    // The entry still de-highlights correctly when it scrolls back below the
    // boundary — the change-guard suppresses redundant writes, not real ones.
    target!.getBoundingClientRect = vi.fn(() => rect(500));
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(nav.querySelector('a')).not.toHaveClass('current');
    expect(nav.querySelector('a')).not.toHaveAttribute('aria-current');
  });

  // Regression test for the M1 finding in the adversarial review of task #33
  // (328b801): setupScrollSpy() (view toggle / resize / re-arm) reset
  // navCurrent to `[null, null]` without touching the DOM. If the next tick
  // then computed "nothing under the boundary" (current === null), the
  // change-guard read null === null and skipped the DOM sweep entirely,
  // leaving the previous view's .current/aria-current frozen on an anchor
  // that no longer corresponds to anything on screen. This must fail against
  // 328b801 (navCurrent reset to [null, null]) and pass once setupScrollSpy
  // resets to a sentinel (`undefined`) that never equals a computed `current`
  // of null.
  it('clears a stale nav highlight after a view-toggle invalidation with nothing under the boundary', async () => {
    window.history.replaceState(null, '', '/SS/book/1');
    render(Reader, { props: { work: 'SS', bookNum: 1, bookData: fixtureBook } });

    const nav = document.createElement('nav');
    nav.className = 'chapter-nav';
    nav.innerHTML = '<a data-ch="ch-1-1">Ch 1</a>';
    document.body.appendChild(nav);
    const toc = document.createElement('nav');
    toc.className = 'toc-outline';
    toc.innerHTML = '<a data-ch="ch-1-1">Ch 1</a>';
    document.body.appendChild(toc);

    const target = document.getElementById('ch-1-1');
    expect(target).toBeTruthy();
    target!.getBoundingClientRect = vi.fn(() => rect(500));

    await flush();

    // Arm the spy and highlight the entry (mirrors the earlier test).
    target!.getBoundingClientRect = vi.fn(() => rect(0));
    window.dispatchEvent(new Event('scroll'));
    await flush();
    expect(nav.querySelector('a')).toHaveClass('current');
    expect(toc.querySelector('a')).toHaveClass('current');

    // Toggle the view (setView unconditionally re-runs setupScrollSpy once
    // the spy is armed, even to the already-active view — this is the
    // reviewer's live repro: highlight col-1.2, toggle view "Both").
    const bothBtn = Array.from(document.querySelectorAll<HTMLButtonElement>('.view-toggle button'))
      .find((b) => b.textContent === 'Both');
    expect(bothBtn).toBeTruthy();
    bothBtn!.click();
    await flush();

    // Scroll below the boundary: nothing should be highlighted now.
    target!.getBoundingClientRect = vi.fn(() => rect(500));
    window.dispatchEvent(new Event('scroll'));
    await flush();

    expect(nav.querySelector('a')).not.toHaveClass('current');
    expect(nav.querySelector('a')).not.toHaveAttribute('aria-current');
    expect(toc.querySelector('a')).not.toHaveClass('current');
    expect(toc.querySelector('a')).not.toHaveAttribute('aria-current');
  });
});
