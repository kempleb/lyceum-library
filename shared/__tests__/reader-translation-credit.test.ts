import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

const HERE = dirname(fileURLToPath(import.meta.url));
const GLOBAL_CSS = readFileSync(join(HERE, '../styles/global.css'), 'utf8');

// Per-passage translation credit (EnglishChunk.credit): a passage whose
// English comes from a different translation than the work's own primary
// one must name its translator, edition and licence on the reading page
// itself -- the control bar's work-level credit names the primary
// translator, so without this the passage would read as that translator's
// work (a misattribution, and for a CC BY-NC-ND text a breach of the
// licence's attribution term). The first consumer is Gorgias B11/B11a,
// whose Parnassos Press translations stand where Kathleen Freeman printed
// only her own summaries.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'CREDFIX', title: 'Fixture Credit Work', abbr: 'Fix. B', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. B', dkChapter: 1, series: 'B' },
    translations: [{ id: 'test', name: 'Primary Translator (Press, 1900)', short: 'Primary', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte per-passage credit test.',
  };
  // Fix round, findings 2 + 3 (Sol xhigh review): a two-translation work, so
  // compare mode is available (canCompare = translations.length >= 2) --
  // the primary slot carries a per-passage credit and a secondary
  // ('secondary'-slot) translation carries none, exercising the compare
  // column's data-eng-credit gating and col-label surname override.
  const compareFixture: Work = {
    id: 'CREDCMPFIX', title: 'Fixture Compare Credit Work', abbr: 'Fix. F', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. F', dkChapter: 1, series: 'B' },
    translations: [
      { id: 'primary', name: 'Primary Translator (Press, 1900)', short: 'Primary', slot: 'english' as const },
      { id: 'secondary', name: 'Secondary Translator (Press, 1910)', short: 'Secondary', slot: 'secondary' as const },
    ],
    blurb: 'Fixture work for the Reader.svelte compare-mode credit-gating test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'CREDFIX' ? fixture : id === 'CREDCMPFIX' ? compareFixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      (id === 'CREDFIX' || id === 'CREDCMPFIX') ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-B11', column: 'B11',
        greek: [{ n: 1, text: 'Greek of the whole speech', tokens: [], role: 'context' }],
        english: {
          text: '(1) The first section. (2) The second section.',
          notes: [], markers: [],
          credit: {
            translator: 'Jurgen R. Gatt',
            source: 'Gorgias/Gorgias, ed. Ewegen and Zoller (Parnassos Press — Fonte Aretusa)',
            year: 2022,
            licence: {
              name: 'CC BY-NC-ND 4.0',
              url: 'https://creativecommons.org/licenses/by-nc-nd/4.0/',
            },
          },
        },
      },
      {
        id: 'seg-B12', column: 'B12',
        greek: [{ n: 1, text: 'Another Greek column', tokens: [], role: 'context' }],
        english: { text: 'The primary translation, uncredited per passage.', notes: [], markers: [] },
      },
    ],
  };
}

async function flush(ms = 20) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
  // The compare-mode credit-gating tests below persist a compare pair via
  // localStorage (reader-cmpl-/reader-cmpr-/reader-trans-CREDCMPFIX) --
  // clear it so it never leaks into a later test.
  localStorage.clear();
});

describe('Reader.svelte per-passage translation credit', () => {
  it('names the translator, edition, year and licence under the passage', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const credit = document.querySelector('#col-B11 .translation-credit');
    expect(credit?.textContent).toBe(
      'Translation: Jurgen R. Gatt, Gorgias/Gorgias, ed. Ewegen and Zoller '
      + '(Parnassos Press — Fonte Aretusa), 2022. Licensed under CC BY-NC-ND 4.0.'
    );
    // The licence names its own deed, so the attribution term is satisfiable
    // by a reader following the link.
    const link = credit?.querySelector('a');
    expect(link?.getAttribute('href')).toBe(
      'https://creativecommons.org/licenses/by-nc-nd/4.0/'
    );
  });

  // item 85 review (2026-07-28): the credit line used to render entirely in
  // italics; only the book/edition title should be. The fixture's `source`
  // ("Gorgias/Gorgias, ed. Ewegen and Zoller (Parnassos Press — Fonte
  // Aretusa)") is the same ", ed." shape the real manifest strings for
  // B11/B11a use.
  it('italicizes only the book title in the credit line, not the whole line', async () => {
    // (global.css, which carries the actual `font-style` rules, is not
    // loaded under this component-only test harness -- see
    // reader-expanded-citation.test.ts's own getComputedStyle checks, which
    // only ever assert the trivial "not italic" default for the same
    // reason. This test instead pins the MARKUP the CSS keys off: only the
    // book title is wrapped in `.translation-credit-title`, so
    // `.translation-credit`'s own italic rule can be dropped in CSS without
    // the whole line going italic again by accident.)
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const credit = document.querySelector('#col-B11 .translation-credit') as HTMLElement;
    const title = credit.querySelector('.translation-credit-title');
    expect(title?.textContent).toBe('Gorgias/Gorgias');
    // Nothing else in the line is wrapped in the italic span.
    expect(credit.querySelectorAll('.translation-credit-title').length).toBe(1);
    expect(credit.textContent?.startsWith('Translation: Jurgen R. Gatt, ')).toBe(true);
    expect(credit.textContent?.includes(', ed. Ewegen and Zoller (Parnassos Press — Fonte Aretusa)')).toBe(true);
    // textContent (what a plain read/copy of the DOM sees) is unaffected by
    // the added <span> -- same full line as the first test above.
    expect(credit.textContent).toBe(
      'Translation: Jurgen R. Gatt, Gorgias/Gorgias, ed. Ewegen and Zoller '
      + '(Parnassos Press — Fonte Aretusa), 2022. Licensed under CC BY-NC-ND 4.0.'
    );
  });

  // Fix round (Sol adversarial review on commit 7287b10, finding 4): the
  // markup-split assertions above pin the DOM shape the CSS keys off, but
  // jsdom never loads global.css, so they can't catch a CSS rule that
  // regresses back to "the whole line is italic" even with the split markup
  // correct. Read the stylesheet source directly and assert the two rules
  // that actually implement "only the title is italic".
  it('global.css: .translation-credit is roman and only .translation-credit-title is italic', () => {
    expect(GLOBAL_CSS).toMatch(/\.translation-credit\s*\{[^}]*font-style:\s*normal;[^}]*\}/);
    expect(GLOBAL_CSS).toMatch(/\.translation-credit-title\s*\{[^}]*font-style:\s*italic;[^}]*\}/);
  });

  // Fix round (Sol adversarial review on commit 7287b10, finding 2): a
  // source with no ", ed." split point used to italicize the WHOLE string.
  // Falls back to the first comma instead -- only the text before it (the
  // title) is italic.
  it('with no ", ed." but a comma in the source, italicizes only up to the first comma', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B13', column: 'B13',
        greek: [{ n: 1, text: 'Greek of the passage', tokens: [], role: 'context' }],
        english: {
          text: 'A passage with a differently-shaped credit.',
          notes: [], markers: [],
          credit: {
            translator: 'Some Translator',
            source: 'Loeb Classical Library, Harvard University Press',
            year: 1925,
          },
        },
      }],
    };
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: book } });
    await flush();
    const credit = document.querySelector('#col-B13 .translation-credit') as HTMLElement;
    const title = credit.querySelector('.translation-credit-title');
    expect(title?.textContent).toBe('Loeb Classical Library');
    expect(credit.querySelectorAll('.translation-credit-title').length).toBe(1);
    expect(credit.textContent).toBe(
      'Translation: Some Translator, Loeb Classical Library, Harvard University Press, 1925.'
    );
  });

  // A bare source with no comma at all can only be a title on its own, so
  // it still italicizes whole (the pre-existing, un-regressed behaviour).
  it('with a bare source containing no comma at all, italicizes the whole source', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B14', column: 'B14',
        greek: [{ n: 1, text: 'Greek of the passage', tokens: [], role: 'context' }],
        english: {
          text: 'A passage with a bare-title credit.',
          notes: [], markers: [],
          credit: {
            translator: 'Some Translator',
            source: 'Some Bare Title',
            year: 1930,
          },
        },
      }],
    };
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: book } });
    await flush();
    const credit = document.querySelector('#col-B14 .translation-credit') as HTMLElement;
    const title = credit.querySelector('.translation-credit-title');
    expect(title?.textContent).toBe('Some Bare Title');
    expect(credit.querySelectorAll('.translation-credit-title').length).toBe(1);
    expect(credit.textContent).toBe(
      'Translation: Some Translator, Some Bare Title, 1930.'
    );
  });

  it('renders it in the English column, beside the Greek, not as a full-width block', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const credit = document.querySelector('.translation-credit');
    expect(credit?.closest('.english-col')).not.toBeNull();
  });

  it('shows nothing at all for a passage carrying the work\'s own translation', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    expect(document.querySelectorAll('#col-B12 .translation-credit').length).toBe(0);
    expect(document.querySelectorAll('.translation-credit').length).toBe(1);
  });
});

// John's ruling 2026-07-29: a Freeman précis with no other translation to
// switch to (EnglishChunk.summary, english.summary_labels) still needs its
// "(summary)" label visible on the card, on the copy path, and in
// data-eng-credit -- reusing the exact string derivation kind:'summary'
// already uses (engCreditFor), and the seg-trans-toggle picker markup item
// 84 already built, rather than a parallel mechanism.
describe('Reader.svelte: EnglishChunk.summary label (John\'s ruling 2026-07-29)', () => {
  function bookWithSummary(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-B15', column: 'B15',
        greek: [{ n: 1, text: 'Greek of the précis column', tokens: [], role: 'context' }],
        english: {
          text: "(Some reporting source: a précis, not a translation).",
          notes: [], markers: [], summary: true,
        },
      }],
    };
  }

  it('shows a single "<short> (summary)" chip on the card even with no other translation to switch to', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWithSummary() } });
    await flush();
    const toggle = document.querySelector('#col-B15 .seg-trans-toggle');
    expect(toggle).not.toBeNull();
    const btns = toggle?.querySelectorAll('.seg-trans-btn');
    expect(btns?.length).toBe(1);
    expect(btns?.[0]?.textContent).toBe('Primary (summary)');
  });

  it('carries the full "(summary)" label in data-eng-credit', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWithSummary() } });
    await flush();
    const col = document.querySelector('#col-B15 .english-col') as HTMLElement;
    expect(col.getAttribute('data-eng-credit')).toBe('Primary Translator (summary)');
  });

  it('copies the "(summary)" label alongside a copied selection', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWithSummary() } });
    await flush();
    const prose = document.querySelector('#col-B15 .english-col .overlay-prose');
    if (!prose) throw new Error('no English prose rendered for B15');
    const range = document.createRange();
    range.selectNodeContents(prose);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    const target = document.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);
    expect(captured).toContain('Primary Translator (summary)');
  });

  it('a passage with no summary flag at all shows no toggle (unchanged, one translation available)', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    expect(document.querySelector('#col-B12 .seg-trans-toggle')).toBeNull();
  });
});

// Finding 2 (Sol review): handleCopy/clickCopyBtn appended a citation only
// when the selection resolved to Greek, and fell through silently for an
// English-only selection — a reader could copy a CC BY-NC-ND passage's
// English out of the reader with no attribution at all, breaching the
// licence's attribution term. These drive the REAL 'copy' event
// Reader.svelte listens for (mirroring the Blocker-2 copy-with-citation
// tests in components.test.ts), with a genuine DOM Selection/Range confined
// to the English column — no Greek line is ever part of the selection.
describe('Reader.svelte — copy path attaches a credited passage\'s translation credit', () => {
  function fireCopy(): string | undefined {
    const target = document.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);
    return captured;
  }

  function selectEnglishOf(column: string): void {
    const prose = document.querySelector(`#col-${column} .english-col .overlay-prose`);
    if (!prose) throw new Error(`no English prose rendered for column ${column}`);
    const range = document.createRange();
    range.selectNodeContents(prose);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }

  it('English-only selection of a credited passage (B11) copies its translation credit', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    selectEnglishOf('B11');
    const copied = fireCopy();
    expect(copied).toContain(
      'Translation: Jurgen R. Gatt, Gorgias/Gorgias, ed. Ewegen and Zoller '
      + '(Parnassos Press — Fonte Aretusa), 2022. Licensed under CC BY-NC-ND 4.0.'
    );
  });

  // The regression that matters: a passage under the work's own primary
  // translation (no column_sources override at all) is unchanged — exactly
  // as before this fix, handleCopy never calls setData/preventDefault for an
  // English-only selection with no per-passage credit, leaving the
  // browser's own default copy (the plain selected text, untouched) to
  // happen instead.
  it('English-only selection of an uncredited passage (B12) leaves the default copy untouched', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    selectEnglishOf('B12');
    const copied = fireCopy();
    expect(copied).toBeUndefined();
  });

  // Fix round, finding 1 (Sol xhigh review): the prior handleCopy resolved
  // a Greek citation from the selection's start endpoint and, finding one,
  // returned immediately -- englishCiteForRange (and any credited English
  // the selection ALSO touched) was never even consulted. A selection
  // starting in Greek and running into B11's credited English used to copy
  // with the citation only, silently dropping the CC BY-NC-ND attribution.
  it('a selection starting in Greek and running into credited English appends BOTH the citation and the translation credit', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    // The fixture's Greek line is role: 'context' (a DK-style verbatim head),
    // so it carries no id of its own (citeForGreekLine's column-only
    // fallback via the ancestor [data-column] -- see that function's own
    // doc comment) -- select by class, not by id.
    const greekLine = document.querySelector('#col-B11 .greek-col .greek-line');
    const prose = document.querySelector('#col-B11 .english-col .overlay-prose');
    if (!greekLine || !prose) throw new Error('missing Greek line or English prose for B11');
    const range = document.createRange();
    range.selectNodeContents(greekLine);
    range.setEnd(prose, prose.childNodes.length);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);

    const copied = fireCopy();
    expect(copied).toContain('(Fix. B B11)');
    expect(copied).toContain(
      'Translation: Jurgen R. Gatt, Gorgias/Gorgias, ed. Ewegen and Zoller '
      + '(Parnassos Press — Fonte Aretusa), 2022. Licensed under CC BY-NC-ND 4.0.'
    );
    // Citation first, credit after (document order: Greek precedes English).
    const citeIdx = copied?.indexOf('(Fix. B B11)') ?? -1;
    const creditIdx = copied?.indexOf('Translation: Jurgen') ?? -1;
    expect(citeIdx).toBeGreaterThanOrEqual(0);
    expect(creditIdx).toBeGreaterThan(citeIdx);
  });
});

// Fix round, findings 2 + 3 (Sol xhigh review): compare mode's right column
// used to set `data-eng-credit` from `seg.english.credit` UNCONDITIONALLY,
// with no check that the credited primary chunk is actually what's shown in
// that column -- and both compare columns' `.col-label` named the slot's
// work-level `short` even when the DISPLAYED chunk (the primary, when that
// column shows it) carries a per-passage credit from a different
// translator. Both bugs only show up once a segment's primary carries a
// credit AND compare mode puts that credited chunk in a specific column --
// exercised here by switching which side shows the primary via the Compare
// pickers (pickCompareLeft/pickCompareRight's otherTrans swap).
describe('Reader.svelte compare mode: per-passage credit follows the DISPLAYED column (findings 2 + 3)', () => {
  function bookCompareCredit(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-F1', column: 'F1',
        greek: [{ n: 1, text: 'Greek of F1', tokens: [], role: 'context' }],
        english: {
          text: 'Credited primary text for F1.', notes: [], markers: [],
          credit: { translator: 'Jurgen R. Gatt', source: 'Fixture Press', year: 2022 },
        },
        ross: [{ chapter: '', text: 'Secondary text for F1.', cont: true }],
      }],
    };
  }

  async function enterCompareMode(): Promise<void> {
    const compareRadio = document.querySelectorAll('input[name="trans-mode"]')[1] as HTMLInputElement;
    if (!compareRadio) throw new Error('no compare-mode radio rendered');
    await fireEvent.click(compareRadio);
    await fireEvent.change(compareRadio);
    await flush();
  }

  it('by default (primary on the left), the left column alone carries the credit and its surname label', async () => {
    render(Reader, { props: { work: 'CREDCMPFIX', bookNum: 1, bookData: bookCompareCredit() } });
    await flush();
    await enterCompareMode();

    const left = document.querySelector('#col-F1 .english-col') as HTMLElement;
    const right = document.querySelector('#col-F1 .overlay-col') as HTMLElement;
    expect(left.getAttribute('data-eng-credit')).toBe(
      'Translation: Jurgen R. Gatt, Fixture Press, 2022.'
    );
    expect(left.querySelector('.col-label')?.textContent).toBe('Gatt');
    // Finding 2's actual bug: before the fix this was ALSO truthy (the
    // right/secondary column carried the primary's credit unconditionally).
    expect(right.hasAttribute('data-eng-credit')).toBe(false);
    expect(right.querySelector('.col-label')?.textContent).toBe('Secondary');
  });

  // The Compare pickers' own same-event self-correction
  // (pickCompareLeft/Right's otherTrans swap) makes driving this scenario
  // through simulated <select> DOM events fragile in this test harness --
  // seed the persisted compare pair directly instead (the same
  // reader-cmpl-/reader-cmpr-<work> localStorage keys the settings sidebar
  // itself writes via saveCompare, read back in onMount), which exercises
  // the exact same reactive `compareLeft`/`compareRight` state the fix
  // reads, deterministically.
  it('with the primary on the RIGHT (persisted pair), the credit and surname label sit there instead', async () => {
    localStorage.setItem('reader-trans-CREDCMPFIX', 'compare');
    localStorage.setItem('reader-cmpl-CREDCMPFIX', 'secondary');
    localStorage.setItem('reader-cmpr-CREDCMPFIX', 'primary');
    render(Reader, { props: { work: 'CREDCMPFIX', bookNum: 1, bookData: bookCompareCredit() } });
    await flush();

    const left = document.querySelector('#col-F1 .english-col') as HTMLElement;
    const right = document.querySelector('#col-F1 .overlay-col') as HTMLElement;
    // Left is now the secondary (no credit, plain short label).
    expect(left.hasAttribute('data-eng-credit')).toBe(false);
    expect(left.querySelector('.col-label')?.textContent).toBe('Secondary');
    // Right now shows the credited primary -- the credit and its surname
    // label follow it. Finding 2's bug would have shown the credit on
    // BOTH columns here (right unconditionally, left correctly); finding
    // 3's bug would have labeled the right column "Primary" (the slot's
    // work-level short) instead of the credited translator's surname.
    expect(right.getAttribute('data-eng-credit')).toBe(
      'Translation: Jurgen R. Gatt, Fixture Press, 2022.'
    );
    expect(right.querySelector('.col-label')?.textContent).toBe('Gatt');
  });

  function bookCompareSummary(): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg-F2', column: 'F2',
          greek: [{ n: 1, text: 'Greek of F2', tokens: [], role: 'context' }],
          english: {
            text: 'Primary précis for F2.', notes: [], markers: [], summary: true,
          },
          ross: [{ chapter: '', text: 'Secondary text for F2.', cont: true }],
        },
        {
          id: 'seg-F3', column: 'F3',
          greek: [{ n: 1, text: 'Greek of F3', tokens: [], role: 'context' }],
          english: {
            text: 'Ordinary primary translation for F3.', notes: [], markers: [],
          },
          ross: [{ chapter: '', text: 'Secondary text for F3.', cont: true }],
        },
      ],
    };
  }

  it.each([
    { side: 'left', selector: '.english-col' },
    { side: 'right', selector: '.overlay-col' },
  ])('labels and copies a summary primary in the $side compare column without affecting ordinary columns', async ({ side, selector }) => {
    localStorage.setItem('reader-trans-CREDCMPFIX', 'compare');
    localStorage.setItem('reader-cmpl-CREDCMPFIX', side === 'left' ? 'primary' : 'secondary');
    localStorage.setItem('reader-cmpr-CREDCMPFIX', side === 'left' ? 'secondary' : 'primary');
    render(Reader, { props: { work: 'CREDCMPFIX', bookNum: 1, bookData: bookCompareSummary() } });
    await flush();

    const summaryCol = document.querySelector(`#col-F2 ${selector}`) as HTMLElement;
    expect(summaryCol.querySelector('.col-label')?.textContent).toBe('Primary (summary)');
    expect(summaryCol.getAttribute('data-eng-credit')).toBe('Primary Translator (summary)');

    const ordinaryCol = document.querySelector(`#col-F3 ${selector}`) as HTMLElement;
    expect(ordinaryCol.querySelector('.col-label')?.textContent).toBe('Primary');
    expect(ordinaryCol.hasAttribute('data-eng-credit')).toBe(false);

    const prose = summaryCol.querySelector('.overlay-prose');
    if (!prose) throw new Error(`no summary prose rendered in the ${side} compare column`);
    const range = document.createRange();
    range.selectNodeContents(prose);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    const target = document.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);
    expect(captured).toContain('Primary Translator (summary)');
  });
});

// Fix round, finding 4 (Sol xhigh review; John's ruling: behavior stays,
// wording only): the setting appends a citation AND a translator credit for
// ANY selection, not just a Greek one -- the old label ("Append citation on
// copy" / "Greek selections only") claimed a Greek-only scope the code
// never actually had.
describe('Reader.svelte settings: the "Append citation" label describes its real scope (finding 4, label only)', () => {
  it('names both citation and translator credit, and drops the "Greek selections only" claim', async () => {
    render(Reader, { props: { work: 'CREDFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const row = Array.from(document.querySelectorAll('.settings-check-row'))
      .find((r) => r.querySelector('.settings-check-name')?.textContent?.includes('Append citation')) as HTMLElement;
    expect(row).toBeTruthy();
    expect(row.querySelector('.settings-check-name')?.childNodes[0]?.textContent?.trim()).toBe(
      'Append citation and translator credit on copy'
    );
    expect(row.textContent).not.toContain('Greek selections only');
  });
});
