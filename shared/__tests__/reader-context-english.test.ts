import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for the source-passage English mechanism (docs/source-
// passage-english-scoping.md, Phase C + implementation section): a
// segment's declared `contextEnglish` spans render INSIDE the English
// column (the same parallel layout every translation uses), after that
// column's ordinary rows -- a `translated` span shows its resolved text
// plus a credit line; a `desert` span shows the honest no-PD-English
// notice instead. Absent entirely for a segment with no `contextEnglish`.
//
// Bug fix (John 2026-07-24, thales/testimonia A1): contextEnglish used to
// render as a full-width block below the Greek column, and a work with no
// primary translation but real contextEnglish content was still forced
// into Greek-only view (no toggle, "No English translation wired yet.").
// This suite also pins the fix: English-column placement, toggle presence
// and header-note absence for a contextEnglish-only work, and byte-
// identical regression for a work with neither.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'CTXFIX', title: 'Fixture Context-English Work', abbr: 'Fix. A', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. A', dkChapter: 1, series: 'A' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte contextEnglish test.',
  };
  // Control fixture for the fragment-translation card test (John's review,
  // 2026-07-28): a book-section work (Meditations/Cicero/Seneca-letters
  // shaped), NOT dk -- .frag-eng-card must never attach here.
  const bookSectionFixture: Work = {
    id: 'BOOKSECCTXFIX', title: 'Fixture Book-Section Work', abbr: 'Fix. BS', author: 'Test',
    language: 'lat', workType: 'continuous', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. BS' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture book-section work for the Reader.svelte frag-eng-card test.',
  };
  return {
    ...actual,
    getWork: (id: string) =>
      id === 'CTXFIX' ? fixture : id === 'BOOKSECCTXFIX' ? bookSectionFixture : actual.getWork(id),
    workPath: (id: string, book = 1) =>
      id === 'CTXFIX' || id === 'BOOKSECCTXFIX' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-A1', column: 'A1',
        greek: [{ n: 1, text: 'Greek context line', tokens: [], role: 'context' }],
        english: null,
        contextEnglish: [
          {
            sourceAuthor: 'Diogenes Laertius',
            sourceWork: 'Lives of Eminent Philosophers',
            locus: '1.22-40',
            status: 'translated',
            translationCredit: 'Hicks, 1925',
            text: 'First resolved paragraph.\n\nSecond resolved paragraph.',
          },
        ],
      },
      {
        id: 'seg-A1b', column: 'A1b',
        greek: [{ n: 1, text: 'A range context line', tokens: [], role: 'context' }],
        english: null,
        contextEnglish: [
          {
            sourceAuthor: 'Diogenes Laertius',
            sourceWork: 'Lives of Eminent Philosophers',
            locus: '1.22-24',
            status: 'translated',
            translationCredit: 'Hicks, 1925',
            text: 'Section 22 text.\n\nSection 23 text.\n\nSection 24 text.',
            sectionLoci: ['1.22', '1.23', '1.24'],
          },
        ],
      },
      {
        id: 'seg-A2', column: 'A2',
        greek: [{ n: 1, text: 'Another Greek context line', tokens: [], role: 'context' }],
        english: null,
        contextEnglish: [
          {
            sourceAuthor: 'Sextus Empiricus',
            sourceWork: 'Adversus Mathematicos',
            locus: 'VII 132',
            status: 'desert',
          },
        ],
      },
      {
        id: 'seg-A3', column: 'A3',
        greek: [{ n: 1, text: 'A plain column with no declaration', tokens: [] }],
        english: null,
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

describe('Reader.svelte source-passage English (docs/source-passage-english-scoping.md)', () => {
  it('renders a translated span\'s resolved paragraphs and credit line', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-A1');
    const blocks = seg?.querySelectorAll('.context-english');
    expect(blocks?.length).toBe(1);
    const paras = blocks?.[0].querySelectorAll('.context-english-text');
    expect(paras?.length).toBe(2);
    expect(paras?.[0].textContent).toBe('First resolved paragraph.');
    expect(paras?.[1].textContent).toBe('Second resolved paragraph.');
    const credit = blocks?.[0].querySelector('.context-english-credit');
    expect(credit?.textContent).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–40 (tr. Hicks, 1925).'
    );
    // No sectionLoci on this fixture span -- no per-paragraph markers.
    expect(blocks?.[0].querySelectorAll('.context-english-section-marker').length).toBe(0);
  });

  it('marks each paragraph of a multi-section range with its own DL section number', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-A1b');
    const block = seg?.querySelector('.context-english');
    const markers = block?.querySelectorAll('.context-english-section-marker');
    expect(Array.from(markers ?? []).map((m) => m.textContent)).toEqual([
      '1.22', '1.23', '1.24',
    ]);
    const paras = block?.querySelectorAll('.context-english-text');
    expect(paras?.length).toBe(3);
  });

  it('renders the desert notice for a status: "desert" span, with no credit', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-A2');
    const desert = seg?.querySelector('.context-english-desert');
    expect(desert?.textContent).toBe(
      'No public-domain English translation of this source passage exists yet. Only the Greek is shown.'
    );
    expect(seg?.querySelector('.context-english-credit')).toBeNull();
  });

  it('renders no block at all for a segment with no contextEnglish declared', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-A3');
    expect(seg?.querySelector('.context-english')).toBeNull();
  });

  it('places the context-english block in the English column, not the Greek column', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-A1');
    const englishCol = seg?.querySelector('.english-col');
    const greekCol = seg?.querySelector('.greek-col');
    expect(englishCol?.querySelector('.context-english')).toBeTruthy();
    expect(greekCol?.querySelector('.context-english')).toBeNull();
  });

  it('un-forces Greek-only view and hides the "no English" note for a contextEnglish-only work', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const toggle = document.querySelector('.view-toggle') as HTMLElement;
    const buttons = Array.from(toggle.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Greek', 'Both', 'English']);
    expect(document.querySelector('.rc-no-english')).toBeFalsy();
  });

  // Fix round, finding 5 (Sol xhigh review): data-eng-credit used to be set
  // ONLY for an alt-bearing span, so an alt-free span's own primary credit
  // (every translated span carries one) never made it onto the copy path --
  // a reader copying this text out of the reader got no attribution at all.
  // Now set whenever the span carries a credit to show, alts or not.
  it('renders no picker toggle for a span with no alts, but still carries data-eng-credit with its primary credit', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const block = document.querySelector('#col-A1 .context-english');
    expect(block?.querySelector('.context-english-alt-toggle')).toBeNull();
    expect(block?.getAttribute('data-eng-credit')).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–40 (tr. Hicks, 1925).'
    );
  });

  it('a span with no emphasis renders no <strong> (byte-identical)', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const block = document.querySelector('#col-A1 .context-english');
    expect(block?.querySelectorAll('.context-english-emphasis').length).toBe(0);
    expect(block?.querySelectorAll('strong').length).toBe(0);
  });
});

// Item 83 (REVIEW-CHECKLIST): source-passage excerpt emphasis. A
// ContextEnglishSpan's `emphasis` substrings (hand-authored, validated at
// build time to occur exactly once, non-overlapping, in text order) mark
// the English words that translate the Greek excerpt DK actually prints --
// rendered bold via .context-english-emphasis, surrounding context at
// normal weight. Applies only to the primary translation; a picked alt
// never carries emphasis.
describe('Reader.svelte source-passage excerpt emphasis (item 83)', () => {
  function bookWithEmphasis(): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg-E1', column: 'E1',
          greek: [{ n: 1, text: 'Greek context line', tokens: [], role: 'context' }],
          english: null,
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.22',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'All things flow and nothing stays fixed.',
              emphasis: ['flow'],
            },
          ],
        },
        {
          id: 'seg-E2', column: 'E2',
          greek: [{ n: 1, text: 'Greek context line', tokens: [], role: 'context' }],
          english: null,
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.22-23',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'First paragraph has fire in it.\n\nSecond paragraph has water in it.',
              sectionLoci: ['1.22', '1.23'],
              emphasis: ['fire', 'water'],
            },
          ],
        },
        {
          id: 'seg-E3', column: 'E3',
          greek: [{ n: 1, text: 'Greek context line', tokens: [], role: 'context' }],
          english: null,
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.30',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'Hicks primary text.',
              emphasis: ['primary'],
              alts: [
                {
                  id: 'yonge',
                  label: 'Yonge',
                  translationCredit: 'Yonge, 1853',
                  sections: [{ locus: '1.30', text: 'Yonge alt text.' }],
                },
              ],
            },
          ],
        },
      ],
    };
  }

  it('wraps a single emphasis substring in <strong>, leaving the rest plain', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithEmphasis() } });
    await flush();
    const para = document.querySelector('#col-E1 .context-english-text') as HTMLElement;
    const strongs = Array.from(para.querySelectorAll('strong.context-english-emphasis'));
    expect(strongs.length).toBe(1);
    expect(strongs[0].textContent).toBe('flow');
    expect(para.textContent).toBe('All things flow and nothing stays fixed.');
  });

  it('wraps multiple emphasis substrings across separate paragraphs', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithEmphasis() } });
    await flush();
    const paras = document.querySelectorAll('#col-E2 .context-english-text');
    expect(paras.length).toBe(2);
    const strong0 = paras[0].querySelectorAll('strong.context-english-emphasis');
    const strong1 = paras[1].querySelectorAll('strong.context-english-emphasis');
    expect(strong0.length).toBe(1);
    expect(strong0[0].textContent).toBe('fire');
    expect(strong1.length).toBe(1);
    expect(strong1[0].textContent).toBe('water');
    expect(paras[0].textContent).toBe('First paragraph has fire in it.');
    expect(paras[1].textContent).toBe('Second paragraph has water in it.');
  });

  it('shows no emphasis when the Jowett/alt translation is displayed', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithEmphasis() } });
    await flush();
    const block = document.querySelector('#col-E3 .context-english') as HTMLElement;
    // Primary shows the emphasis.
    expect(block.querySelectorAll('strong.context-english-emphasis').length).toBe(1);
    const yongeBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Yonge') as HTMLElement;
    await fireEvent.click(yongeBtn);
    await flush();
    expect(block.querySelectorAll('strong.context-english-emphasis').length).toBe(0);
    expect(block.querySelector('.context-english-text')?.textContent).toBe('Yonge alt text.');
  });

  it('textContent is unchanged by the emphasis markup', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithEmphasis() } });
    await flush();
    const para = document.querySelector('#col-E1 .context-english-text');
    expect(para?.textContent).toBe('All things flow and nothing stays fixed.');
  });
});

// Per-passage translation picker (item 82, REVIEW-CHECKLIST): a
// ContextEnglishSpan whose source passage has alternate PD translations
// (span.alts) gets a plain-text toggle beside its rendering -- primary
// label first, then each alt. Switching swaps the visible text/credit AND
// the `data-eng-credit` attribute the copy path reads (finding, Sol
// review: the nearest ancestor `.english-col` names the SEGMENT's own
// primary credit, never this source passage's alt).
describe('Reader.svelte per-passage translation picker (item 82)', () => {
  function bookWithAlts(): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg-P1', column: 'P1',
          greek: [{ n: 1, text: 'Greek context line', tokens: [], role: 'context' }],
          english: null,
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.22-23',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'Hicks section 22.\n\nHicks section 23.',
              sectionLoci: ['1.22', '1.23'],
              alts: [
                {
                  id: 'yonge',
                  label: 'Yonge',
                  translationCredit: 'Yonge, 1853',
                  sections: [
                    { locus: '1.22', text: 'Yonge section 22.' },
                    { locus: '1.23' },
                  ],
                },
              ],
            },
          ],
        },
        // Mixed-selection fixture (finding 1, Sol review): a segment whose
        // OWN primary English carries a credit (a passage translated by
        // someone other than the work's primary translator), immediately
        // followed by a context-english span with alts -- so a single
        // selection can span both a `.english-col`-level credit and a
        // `.context-english`-level credit, and the two differ.
        {
          id: 'seg-P2', column: 'P2',
          greek: [{ n: 1, text: 'Greek line with its own translator', tokens: [] }],
          english: {
            text: 'Primary passage text.',
            notes: [],
            markers: [],
            credit: { translator: 'Smith', source: 'Some Edition', year: 1900 },
          },
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.30-31',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'Hicks section 30.',
              alts: [
                {
                  id: 'yonge',
                  label: 'Yonge',
                  translationCredit: 'Yonge, 1853',
                  sections: [{ locus: '1.30', text: 'Yonge section 30.' }],
                },
              ],
            },
          ],
        },
      ],
    };
  }

  async function flush(ms = 20) {
    await new Promise((r) => setTimeout(r, ms));
  }

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

  function selectContextEnglishOf(column: string): void {
    const block = document.querySelector(`#col-${column} .context-english`);
    if (!block) throw new Error(`no context-english block rendered for column ${column}`);
    const range = document.createRange();
    range.selectNodeContents(block);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }

  // Finding 2 (Sol review): the original test selected the WHOLE
  // .context-english block, which visibly contains the rendered credit
  // line itself -- so `toContain(credit)` passed even if the copy path
  // appended nothing at all (the credit was already inside the selected
  // text). This selects ONLY the .context-english-text paragraph(s),
  // excluding the toggle and the visible .context-english-credit line, so
  // a passing assertion actually proves handleCopy appended the
  // data-eng-credit attribution.
  function selectContextEnglishTextOf(column: string): void {
    const block = document.querySelector(`#col-${column} .context-english`);
    if (!block) throw new Error(`no context-english block rendered for column ${column}`);
    const paras = block.querySelectorAll('.context-english-text');
    if (!paras.length) throw new Error(`no .context-english-text paragraphs for column ${column}`);
    const range = document.createRange();
    range.setStartBefore(paras[0]);
    range.setEndAfter(paras[paras.length - 1]);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }

  // Finding 1 (Sol review): a selection spanning a segment's own credited
  // primary English (`.english-col`'s own data-eng-credit) and a
  // differently-credited `.context-english` span used to keep only the
  // FIRST endpoint's credit (`??` short-circuit in englishCiteForRange),
  // silently dropping the other translator's attribution. Spans from
  // inside the primary `.overlay-prose` text to inside the context-english
  // paragraph text (excluding its own credit line), so both endpoints
  // resolve to genuinely different credits.
  function selectMixedEnglishOf(column: string): void {
    const col = document.querySelector(`#col-${column} .english-col`);
    if (!col) throw new Error(`no english-col rendered for column ${column}`);
    const prose = col.querySelector('.overlay-prose');
    const ctxPara = col.querySelector('.context-english .context-english-text');
    if (!prose || !ctxPara) throw new Error(`missing prose or context-english-text for column ${column}`);
    const range = document.createRange();
    range.setStartBefore(prose);
    range.setEndAfter(ctxPara);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  }

  it('renders the toggle with the primary label (translator surname) first, then each alt', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithAlts() } });
    await flush();
    const toggle = document.querySelector('#col-P1 .context-english-alt-toggle');
    const labels = Array.from(toggle?.querySelectorAll('.context-english-alt-btn') ?? [])
      .map((b) => b.textContent?.trim());
    expect(labels).toEqual(['Hicks', 'Yonge']);
    expect(toggle?.querySelector('.context-english-alt-btn.active')?.textContent?.trim()).toBe('Hicks');
  });

  it('clicking an alt swaps the visible text and credit, and a gap section renders the marker', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithAlts() } });
    await flush();
    const block = document.querySelector('#col-P1 .context-english') as HTMLElement;
    const yongeBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Yonge') as HTMLElement;
    await fireEvent.click(yongeBtn);
    await flush();
    const paras = Array.from(block.querySelectorAll('.context-english-text')).map((p) => p.textContent);
    expect(paras).toEqual(['Yonge section 22.', 'No Yonge translation for this section.']);
    expect(block.querySelector('.context-english-credit')?.textContent).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–23 (tr. Yonge, 1853).'
    );
    expect(yongeBtn.classList.contains('active')).toBe(true);
  });

  it('after switching to an alt, the data-eng-credit attribute (and copied text) reflects the alt\'s credit', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithAlts() } });
    await flush();
    const block = document.querySelector('#col-P1 .context-english') as HTMLElement;
    const yongeBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Yonge') as HTMLElement;
    await fireEvent.click(yongeBtn);
    await flush();
    expect(block.getAttribute('data-eng-credit')).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–23 (tr. Yonge, 1853).'
    );
    // Select ONLY the translation paragraphs (not the visible credit line
    // itself, and not the toggle) -- the selected text carries no credit
    // wording of its own, so asserting the copied string is exactly
    // "selection + newline + credit" proves the copy path APPENDED the
    // attribution, rather than merely including text that already had it
    // (the original test's weakness: it selected the whole block, credit
    // line included).
    selectContextEnglishTextOf('P1');
    const selectedText = window.getSelection()?.toString().trim() ?? '';
    expect(selectedText).not.toContain('Source passage:');
    const copied = fireCopy();
    const expectedCredit =
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–23 (tr. Yonge, 1853).';
    expect(copied).toBe(selectedText + '\n' + expectedCredit);
  });

  it('a selection spanning a credited primary translation and a differently-credited context-english span appends BOTH credits', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithAlts() } });
    await flush();
    // seg-P2's own primary English carries the 'Smith' credit; switch its
    // context-english span to Yonge so the two endpoints resolve to
    // genuinely different credits (Hicks -- the DEFAULT -- would also
    // differ from Smith, but Yonge exercises the alt-picker path too).
    const block = document.querySelector('#col-P2 .context-english') as HTMLElement;
    const yongeBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Yonge') as HTMLElement;
    await fireEvent.click(yongeBtn);
    await flush();
    selectMixedEnglishOf('P2');
    const copied = fireCopy();
    // Before the fix, englishCiteForRange used
    // `nearestEnglishCredit(start) ?? nearestEnglishCredit(end)`, which
    // resolves the START endpoint's credit and never looks at the end
    // when the start already resolved -- so only Smith's primary-English
    // credit would appear, and Yonge's source-passage credit would be
    // silently dropped.
    expect(copied).toContain('Translation: Smith, Some Edition, 1900.');
    expect(copied).toContain(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.30–31 (tr. Yonge, 1853).'
    );
    // Document order: the primary translation's credit precedes the
    // source-passage credit.
    const smithIdx = copied?.indexOf('Translation: Smith') ?? -1;
    const yongeIdx = copied?.indexOf('Source passage:') ?? -1;
    expect(smithIdx).toBeGreaterThanOrEqual(0);
    expect(yongeIdx).toBeGreaterThan(smithIdx);
  });

  it('switching back to the primary restores the original text, credit and data-eng-credit', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithAlts() } });
    await flush();
    const block = document.querySelector('#col-P1 .context-english') as HTMLElement;
    const hicksBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Hicks') as HTMLElement;
    const yongeBtn = Array.from(block.querySelectorAll('.context-english-alt-btn'))
      .find((b) => b.textContent?.trim() === 'Yonge') as HTMLElement;
    await fireEvent.click(yongeBtn);
    await flush();
    await fireEvent.click(hicksBtn);
    await flush();
    const paras = Array.from(block.querySelectorAll('.context-english-text')).map((p) => p.textContent);
    expect(paras).toEqual(['Hicks section 22.', 'Hicks section 23.']);
    expect(block.querySelector('.context-english-credit')?.textContent).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–23 (tr. Hicks, 1925).'
    );
    expect(block.getAttribute('data-eng-credit')).toBe(
      'Source passage: Diogenes Laertius, Lives of Eminent Philosophers 1.22–23 (tr. Hicks, 1925).'
    );
    expect(hicksBtn.classList.contains('active')).toBe(true);
  });
});

describe('Reader.svelte regression: a work with no contextEnglish and no primary translation', () => {
  function bookWithNoEnglishAtAll(): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg-B1', column: 'B1',
          greek: [{ n: 1, text: 'Plain Greek line, no context English anywhere', tokens: [] }],
          english: null,
        },
      ],
    };
  }

  it('stays forced Greek-only, with the "no English" note and no context-english block', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithNoEnglishAtAll() } });
    await flush();
    const toggle = document.querySelector('.view-toggle') as HTMLElement;
    const buttons = Array.from(toggle.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons).toEqual(['Greek']);
    expect(document.querySelector('.rc-no-english')?.textContent?.trim()).toBe('No English translation wired yet.');
    expect(document.querySelector('.context-english')).toBeNull();
  });
});

// John's review, 2026-07-28: the same teal accent-line + tinted-background
// card he liked on .context-english (visible live on e.g. gorgias/testimonia
// A2a) now also wraps a dk-scheme (fragment/testimonia) segment's OWN
// translation content, via `.frag-eng-card` in Reader.svelte -- same CSS
// tokens as .context-english (global.css). Scoped to dk-scheme works only
// (fragment/testimonia); book-section, turn-flow and verse-line works are
// untouched. A segment carrying BOTH its own translation and a
// contextEnglish span must never nest a card inside an identical card --
// .frag-eng-card wraps the translation content only, as a SIBLING of
// .context-english, not an ancestor.
describe('Reader.svelte fragment-translation card (John review, 2026-07-28)', () => {
  function bookWithTranslation(): BookData {
    return {
      book: 1,
      segments: [
        {
          id: 'seg-T1', column: 'B1',
          greek: [{ n: 1, text: 'Greek fragment line', tokens: [] }],
          english: { text: 'Primary fragment translation.', notes: [], markers: [] },
        },
        // Both surfaces on one segment: its own translation AND a
        // contextEnglish span for the quoted source passage.
        {
          id: 'seg-T2', column: 'B2',
          greek: [{ n: 1, text: 'Greek fragment line with a quoted source', tokens: [] }],
          english: { text: 'Primary fragment translation, second segment.', notes: [], markers: [] },
          contextEnglish: [
            {
              sourceAuthor: 'Diogenes Laertius',
              sourceWork: 'Lives of Eminent Philosophers',
              locus: '1.30',
              status: 'translated',
              translationCredit: 'Hicks, 1925',
              text: 'Quoted source passage text.',
            },
          ],
        },
      ],
    };
  }

  it('wraps a dk-scheme segment\'s own translation content in .frag-eng-card', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithTranslation() } });
    await flush();
    const col = document.querySelector('#col-B1 .english-col');
    const card = col?.querySelector('.frag-eng-card');
    expect(card).toBeTruthy();
    expect(card?.textContent).toContain('Primary fragment translation.');
  });

  it('does not attach .frag-eng-card on a book-section-scheme work (Meditations/Cicero/Seneca-letters shaped)', async () => {
    render(Reader, {
      props: {
        work: 'BOOKSECCTXFIX', bookNum: 1,
        bookData: {
          book: 1,
          segments: [
            {
              id: 'seg-BS1', column: '1.1',
              greek: [{ n: 1, text: 'Book-section Greek line', tokens: [] }],
              english: { text: 'Book-section translation.', notes: [], markers: [] },
            },
          ],
        },
      },
    });
    await flush();
    expect(document.querySelector('.frag-eng-card')).toBeNull();
  });

  it('does not nest a card inside a card: a segment with both its own translation and a contextEnglish span keeps .context-english as a SIBLING of .frag-eng-card, never a descendant', async () => {
    render(Reader, { props: { work: 'CTXFIX', bookNum: 1, bookData: bookWithTranslation() } });
    await flush();
    const col = document.querySelector('#col-B2 .english-col') as HTMLElement;
    const card = col.querySelector('.frag-eng-card') as HTMLElement;
    expect(card).toBeTruthy();
    expect(card.textContent).toContain('Primary fragment translation, second segment.');
    // The source-passage block exists, but NOT inside the card.
    expect(col.querySelector('.context-english')).toBeTruthy();
    expect(card.querySelector('.context-english')).toBeNull();
  });
});
