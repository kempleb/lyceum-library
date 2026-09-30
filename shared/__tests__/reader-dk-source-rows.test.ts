import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader, { contextSectionGroups, sourceHeadDisplayText } from '../components/Reader.svelte';
import type { BookData, CitationHead, ContextEnglishSpan, Segment } from '../lib/data';
import type { Work } from '../lib/works';

// DK source rows in the Both view (John, 2026-09-27). Pins:
//  - the heading row: the English citation (and the source passage's picker)
//    beside the Greek source heading, outside the translation card;
//  - the passage row: the English translation beside the Greek passage;
//  - section rows where DK's printed "(N)" labels match the English sections,
//    with an unprinted label's sections kept beside the Greek section that
//    contains them (Heraclitus A1 prints no (13) or (14));
//  - the unsplit layout whenever the match is not clean;
//  - Greek-only view keeps the ordinary layout;
//  - DK's continuation dashes never open a Greek source heading.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'DKROWFIX', title: 'Fixture DK Source-Row Work', abbr: 'Fix. A', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. A', dkChapter: 1, series: 'A' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the DK source-row layout test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'DKROWFIX' ? fixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      id === 'DKROWFIX' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

const HEAD = 'DIOG. IX 1—4.';
const dlHead = (text: string, start: number, extra: Partial<CitationHead> = {}): CitationHead => ({
  lineIndex: 0, line: -1, start, end: start + text.length, text,
  expanded: [{ verbatim: text, resolution: 'direct', authorDisplay: 'Diogenes Laertius', work: { title: 'Vitae Philosophorum', italic: true }, locus: 'IX 1—4.', flags: [] }],
  ...extra,
});
const dlSpan = (loci: string[], text: string, extra: Partial<ContextEnglishSpan> = {}): ContextEnglishSpan => ({
  sourceAuthor: 'Diogenes Laertius', sourceWork: 'Lives of Eminent Philosophers', locus: '9.1-4',
  status: 'translated', translationCredit: 'Hicks, 1925', text, sectionLoci: loci, ...extra,
});

// DK prints (1), (2) and (4) but no (3): the English's 9.3 stays beside (2).
function sectionSegment(span: ContextEnglishSpan): Segment {
  const text = `${HEAD} (1) Alpha one. (2) Beta two. (4) Delta four.`;
  return {
    id: 'seg-A1', column: 'A1', english: null,
    greek: [{ n: -1, role: 'context', text, tokens: [] }],
    citationHeads: [dlHead(HEAD, 0)],
    contextEnglish: [span],
  };
}
const book = (...segments: Segment[]): BookData => ({ book: 1, segments });
const flush = (ms = 20) => new Promise((r) => setTimeout(r, ms));
const texts = (els: Iterable<Element>) => [...els].map((e) => e.textContent?.trim());

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('contextSectionGroups', () => {
  it('pairs each printed label with its English section', () => {
    expect(contextSectionGroups([1, 2, 3], ['9.1', '9.2', '9.3'])).toEqual([[], [0], [1], [2]]);
  });
  it('keeps sections whose label DK leaves unprinted beside the Greek section that holds them', () => {
    // Heraclitus A1: DK prints no (13) or (14).
    const loci = Array.from({ length: 17 }, (_, i) => `9.${i + 1}`);
    const groups = contextSectionGroups([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17], loci)!;
    expect(groups[12]).toEqual([11, 12, 13]);
    expect(groups[13]).toEqual([14]);
    expect(groups.flat()).toEqual(loci.map((_, i) => i));
  });
  it('puts English sections before the first printed label beside the Greek that precedes it', () => {
    // Leucippus A1: DK prints no (30); the passage opens before (31).
    expect(contextSectionGroups([31, 32, 33], ['9.30', '9.31', '9.32', '9.33'])).toEqual([[0], [1], [2], [3]]);
  });
  it('returns null unless the match is clean', () => {
    expect(contextSectionGroups([1, 5], ['9.1', '9.2'])).toBeNull(); // label with no English section
    expect(contextSectionGroups([2, 1], ['9.1', '9.2'])).toBeNull(); // labels out of order
    expect(contextSectionGroups([1, 2], ['9.2', '9.1'])).toBeNull(); // sections out of order
    expect(contextSectionGroups([1], ['97b', '97c'])).toBeNull(); // loci with no section number
    expect(contextSectionGroups([], ['9.1', '9.2'])).toBeNull();
  });
});

describe('sourceHeadDisplayText', () => {
  it("drops DK's leading continuation dashes and the space after them", () => {
    expect(sourceHeadDisplayText('—II 20, 16 (D. 351)')).toBe('II 20, 16 (D. 351)');
    expect(sourceHeadDisplayText('—22, 2 (D. 352)')).toBe('22, 2 (D. 352)');
    expect(sourceHeadDisplayText('— —94 (I 214, 9 St.)')).toBe('94 (I 214, 9 St.)');
    expect(sourceHeadDisplayText('– 5, 3')).toBe('5, 3');
  });
  it('leaves a heading with no leading dash, or with nothing after the dash, as printed', () => {
    expect(sourceHeadDisplayText('DIOG. IX 1—17.')).toBe('DIOG. IX 1—17.');
    expect(sourceHeadDisplayText('—')).toBe('—');
  });
  it("uses the pipeline's display string when it describes this heading", () => {
    const head = { text: '—II 20, 16 (D. 351)', display: 'AËT. II 20, 16 (D. 351)' };
    expect(sourceHeadDisplayText(head.text, head)).toBe('AËT. II 20, 16 (D. 351)');
    expect(sourceHeadDisplayText('—22, 2 (D. 352)', head)).toBe('22, 2 (D. 352)');
    expect(sourceHeadDisplayText(head.text, { text: head.text })).toBe('II 20, 16 (D. 351)');
  });
});

describe('Reader.svelte DK source rows (Both view)', () => {
  it('gives the heading, and each matched section, its own row', async () => {
    const { container } = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(sectionSegment(
      dlSpan(['9.1', '9.2', '9.3', '9.4'], 'E one.\n\nE two.\n\nE three.\n\nE four.'),
    )) } });
    await flush();
    const grid = container.querySelector('#col-A1 .seg-row.dk-source-grid')!;
    expect(grid).toBeTruthy();
    const rows = [...grid.querySelectorAll(':scope > .frag-row')];
    expect(rows).toHaveLength(4);

    // Heading row: Greek heading beside the citation, no card.
    expect(rows[0]!.classList.contains('dk-head-row')).toBe(true);
    expect(rows[0]!.querySelector('.greek-col .frag-source-head')?.textContent).toBe(HEAD);
    expect(rows[0]!.querySelector('.english-col .dk-head-line .expanded-citation')?.textContent?.trim()).toBe('Diogenes Laertius, Vitae Philosophorum IX 1—4.');
    expect(rows[0]!.querySelector('.frag-eng-card, .context-english')).toBeNull();

    // Section rows: (1) | 9.1, (2) | 9.2 + 9.3, (4) | 9.4.
    const greek = (r: Element) => texts(r.querySelectorAll('.greek-context-section-marker'));
    const eng = (r: Element) => texts(r.querySelectorAll('.context-english-section-marker'));
    expect(rows.slice(1).map(greek)).toEqual([['(1)'], ['(2)'], ['(4)']]);
    expect(rows.slice(1).map(eng)).toEqual([['9.1'], ['9.2', '9.3'], ['9.4']]);
    expect(texts(rows[2]!.querySelectorAll('.context-english-text'))).toEqual(['E two.', 'E three.']);

    // Every cell pins its own grid place; the card spans the passage rows only.
    const place = (el: Element | null) => [(el as HTMLElement).style.gridRow, (el as HTMLElement).style.gridColumn];
    rows.forEach((r, i) => {
      expect(place(r.querySelector('.greek-col'))).toEqual([`${i + 1}`, '1']);
      expect(place(r.querySelector('.english-col'))).toEqual([`${i + 1}`, '2']);
    });
    expect(place(grid.querySelector(':scope > .frag-eng-card-bg'))).toEqual(['2 / span 3', '2']);

    // Credit once, in the last row; the copy credit on every section's English.
    expect(rows.map((r) => r.querySelectorAll('.context-english-credit').length)).toEqual([0, 0, 0, 1]);
    for (const r of rows.slice(1)) {
      expect(r.querySelector('.context-english-row')?.getAttribute('data-eng-credit')).toBe('Source passage: Diogenes Laertius, Lives of Eminent Philosophers 9.1–4 (tr. Hicks, 1925).');
    }
  });

  it('keeps the section-marked passage in one row when the English sections do not line up', async () => {
    // Four loci, three paragraphs: no clean match.
    const { container } = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(sectionSegment(
      dlSpan(['9.1', '9.2', '9.3', '9.4'], 'E one.\n\nE two.\n\nE three.'),
    )) } });
    await flush();
    const rows = [...container.querySelectorAll('#col-A1 .dk-source-grid > .frag-row')];
    expect(rows).toHaveLength(2);
    expect(rows[0]!.classList.contains('dk-head-row')).toBe(true);
    expect(rows[1]!.classList.contains('dk-body-whole')).toBe(true);
    expect(texts(rows[1]!.querySelectorAll('.greek-context-section-marker'))).toEqual(['(1)', '(2)', '(4)']);
    expect(rows[1]!.querySelectorAll('.context-english').length).toBe(1);
    expect(rows[1]!.querySelector('.context-english-credit')).toBeTruthy();
    expect(container.querySelector('#col-A1 .frag-eng-card-bg')).toBeNull();
  });

  it('moves the source passage picker onto the citation line, and it still switches the English', async () => {
    const text = 'PLAT. Cratyl. p. 402 A λέγει που Ἡράκλειτος.';
    const head = 'PLAT. Cratyl. p. 402 A';
    const seg: Segment = {
      id: 'seg-A6', column: 'A6', english: null,
      greek: [{ n: -1, role: 'context', text, tokens: [] }],
      citationHeads: [{ lineIndex: 0, line: -1, start: 0, end: head.length, text: head,
        expanded: [{ verbatim: head, resolution: 'direct', authorDisplay: 'Plato', work: { title: 'Cratylus', italic: true }, locus: 'p. 402 A', flags: [] }] }],
      contextEnglish: [{
        sourceAuthor: 'Plato', sourceWork: 'Cratylus', locus: '402a', status: 'translated',
        translationCredit: 'Fowler, 1926', text: 'Fowler English.',
        alts: [{ id: 'jowett', label: 'Jowett', translationCredit: 'Jowett, 1892', sections: [{ locus: '402a', text: 'Jowett English.' }] }],
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(seg) } });
    await flush();
    const rows = [...container.querySelectorAll('#col-A6 .dk-source-grid > .frag-row')];
    const picker = rows[0]!.querySelector('.dk-head-line .context-english-alt-toggle')!;
    expect(picker).toBeTruthy();
    expect(picker.getAttribute('role')).toBe('group');
    expect(picker.getAttribute('aria-label')).toBe('Translation');
    expect(rows[1]!.querySelector('.context-english-alt-toggle')).toBeNull();
    expect(rows[1]!.querySelector('.context-english')?.classList.contains('context-english-row')).toBe(false);
    expect(rows[1]!.querySelector('.context-english-text')?.textContent).toBe('Fowler English.');
    const jowett = [...picker.querySelectorAll('button')].find((b) => b.textContent === 'Jowett')!;
    await fireEvent.click(jowett);
    await flush();
    expect(jowett.getAttribute('aria-pressed')).toBe('true');
    expect(rows[1]!.querySelector('.context-english-text')?.textContent).toBe('Jowett English.');
  });

  it('floats a LATER source-passage span\'s own picker at its first line instead of pushing its English down (prodicus-testimonia A17 shape: the FIRST span, 197b, has no alt; the SECOND, 197d, does — only one span per heading can move up to the citation line)', async () => {
    const text = '—Lach. 197 B ἀλλ᾽, οἶμαι, τὸ ἄφοβον καὶ τὸ ἀνδρεῖον. Vgl. 197 D μηδέ γε εἴπηις.';
    const head = '—Lach. 197 B';
    const seg: Segment = {
      id: 'seg-A17', column: 'A17', english: null,
      greek: [{ n: -1, role: 'context', text, tokens: [] }],
      citationHeads: [{ lineIndex: 0, line: -1, start: 0, end: head.length, text: head,
        expanded: [{ verbatim: head, resolution: 'dash', authorDisplay: 'Plato', work: { title: 'Laches', italic: true }, locus: '197 B', flags: [] }] }],
      contextEnglish: [
        { sourceAuthor: 'Plato', sourceWork: 'Laches', locus: '197b', status: 'translated', translationCredit: 'Lamb, 1924', text: 'First span English, no alt.' },
        { sourceAuthor: 'Plato', sourceWork: 'Laches', locus: '197d', status: 'translated', translationCredit: 'Lamb, 1924', text: 'Second span English.',
          alts: [{ id: 'jowett', label: 'Jowett', translationCredit: 'Jowett, 1892', sections: [{ locus: '197d', text: 'Second span Jowett English.' }] }] },
      ],
    };
    const { container } = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(seg) } });
    await flush();
    const rows = [...container.querySelectorAll('#col-A17 .dk-source-grid > .frag-row')];
    expect(rows).toHaveLength(2);
    // No picker moves to the heading line -- the first span (which would be
    // the one moved) has no alt to offer.
    expect(rows[0]!.querySelector('.dk-head-line .context-english-alt-toggle')).toBeNull();
    const bodySpans = [...rows[1]!.querySelectorAll('.context-english')];
    expect(bodySpans).toHaveLength(2);
    expect(bodySpans[0]!.querySelector('.context-english-alt-toggle')).toBeNull();
    // The second span's own picker renders in ITS OWN span, floated at the
    // right end of its first line -- never as a block-level line above the
    // paragraph (that was the defect: nothing pushes the Greek down to
    // match, so the English fell out of level with it).
    const picker = bodySpans[1]!.querySelector('.context-english-alt-toggle')!;
    expect(picker).toBeTruthy();
    expect(picker.classList.contains('context-english-alt-toggle-float')).toBe(true);
    expect(bodySpans[1]!.classList.contains('context-english-float-contain')).toBe(true);
    // It still switches only its OWN span's English.
    const jowett = [...picker.querySelectorAll('button')].find((b) => b.textContent === 'Jowett')!;
    await fireEvent.click(jowett);
    await flush();
    expect(bodySpans[1]!.querySelector('.context-english-text')?.textContent).toBe('Second span Jowett English.');
    expect(bodySpans[0]!.querySelector('.context-english-text')?.textContent).toBe('First span English, no alt.');
  });

  it("splits item 85's own section rows below the heading row, in Both and English-only views", async () => {
    const head = 'SIMPL. phys. 111, 18';
    const text = `${head} (1) Κόσμος πόλει. (2) ὅτι μὲν οὖν.`;
    const seg: Segment = {
      id: 'seg-B7', column: 'B7', sectionParagraphSplit: true,
      greek: [{ n: -1, role: 'context', text, tokens: [] }],
      english: { text: '(1) One English. (2) Two English.', notes: [], markers: [], credit: { translator: 'T. Translator', source: 'Test Source', year: 1900 } },
      citationHeads: [{ lineIndex: 0, line: -1, start: 0, end: head.length, text: head,
        expanded: [{ verbatim: head, resolution: 'direct', authorDisplay: 'Simplicius', work: { title: 'in Physica', italic: true }, locus: '111, 18', flags: [] }] }],
    };
    for (const view of ['both', 'english']) {
      window.history.replaceState(null, '', `/?view=${view}`);
      const r = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(seg) } });
      await flush();
      const rows = [...r.container.querySelectorAll('#col-B7 .dk-source-grid > .frag-row')];
      expect(rows.map((x) => x.classList.contains('dk-head-row'))).toEqual([true, false, false]);
      expect(rows[0]!.querySelector('.english-col .dk-head-line .expanded-citation')).toBeTruthy();
      expect(rows.slice(1).map((x) => x.querySelector('.greek-context-section-marker')?.textContent)).toEqual(['(1)', '(2)']);
      expect(rows.slice(1).map((x) => x.querySelector('.english-col')?.textContent?.includes(x === rows[1] ? 'One English' : 'Two English'))).toEqual([true, true]);
      expect(rows.map((x) => x.querySelectorAll('.translation-credit').length)).toEqual([0, 0, 1]);
      expect(rows.every((x) => x.querySelector('.english-col')?.hasAttribute('data-eng-credit'))).toBe(true);
      r.unmount();
    }
  });

  it('keeps the ordinary layout in Greek-only view, with the citation outside the card', async () => {
    window.history.replaceState(null, '', '/?view=greek');
    const { container } = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(sectionSegment(
      dlSpan(['9.1', '9.2', '9.3', '9.4'], 'E one.\n\nE two.\n\nE three.\n\nE four.'),
    )) } });
    await flush();
    expect(container.querySelector('#col-A1 .dk-source-grid')).toBeNull();
    const col = container.querySelector('#col-A1 .seg-row > .english-col')!;
    expect(col.querySelector(':scope > .expanded-citation')).toBeTruthy();
    expect(col.querySelector('.frag-eng-card .expanded-citation')).toBeNull();
  });

  it('prints a continuation heading without its dash, or as the pipeline spells it out', async () => {
    const line = '—II 20, 16 (D. 351) ἥλιον εἶναι. —22, 2 (D. 352) ΠΕΡΙ ΦΥΣΙΟΣ ἄλλο.';
    const h1 = '—II 20, 16 (D. 351)';
    const h2 = '—22, 2 (D. 352) ΠΕΡΙ ΦΥΣΙΟΣ';
    const aet = (text: string, start: number, display?: string): CitationHead => ({
      lineIndex: 0, line: -1, start, end: start + text.length, text, ...(display ? { display } : {}),
      expanded: [{ verbatim: text, resolution: 'dash', authorDisplay: 'Aëtius', work: { title: 'Placita', italic: true }, locus: text.slice(1), flags: [] }],
    } as CitationHead);
    const seg = (display?: string): Segment => ({
      id: 'seg-A12', column: 'A12', english: null,
      greek: [{ n: -1, role: 'context', text: line, tokens: [{ t: 'ΦΥΣΙΟΣ', o: line.indexOf('ΦΥΣΙΟΣ'), k: 'φύσις' }] }],
      citationHeads: [aet(h1, 0, display), aet(h2, line.indexOf(h2))],
    });
    const heads = (c: Element) => texts(c.querySelectorAll('#col-A12 .frag-source-head'));

    const plain = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(seg()) } });
    await flush();
    expect(heads(plain.container)).toEqual(['II 20, 16 (D. 351)', '22, 2 (D. 352) ΠΕΡΙ ΦΥΣΙΟΣ']);
    // The Greek word inside the heading keeps its lookup.
    expect(plain.container.querySelectorAll('#col-A12 .frag-source-head .tok')).toHaveLength(1);
    plain.unmount();

    const spelled = render(Reader, { props: { work: 'DKROWFIX', bookNum: 1, bookData: book(seg('AËT. II 20, 16 (D. 351)')) } });
    await flush();
    expect(heads(spelled.container)).toEqual(['AËT. II 20, 16 (D. 351)', '22, 2 (D. 352) ΠΕΡΙ ΦΥΣΙΟΣ']);
  });
});
