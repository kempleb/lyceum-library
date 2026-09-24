import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData } from '../lib/data';
import type { Work } from '../lib/works';

// Regression test for the DK source-citation expansion render layer (docs/
// citation-expansion-wiring-design.md §4): a segment's declared
// `expandedCitation` -- a LIST OF RUNS, one per distinct context run,
// document order (fix round finding 2) -- renders INSIDE the English
// column, after the segment's ordinary translation rows, as one line PER
// RUN -- a `direct` entry prints "Author, Work locus" with the work title
// italicized only when the entry's own `work.italic` says so; a `verbatim`
// entry (unresolved or a dash-continuation) prints the head exactly as DK
// printed it, with no invented author or title, and never italicized just
// for being verbatim (fix round finding 3); multiple SOURCES within one
// run join with "; ", but two DISTINCT runs render as two separate lines,
// never merged into one false attribution. Absent entirely for a segment
// with no `expandedCitation`.
vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const fixture: Work = {
    id: 'ECFIX', title: 'Fixture Expanded-Citation Work', abbr: 'Fix. B', author: 'Test',
    language: 'grc', workType: 'fragments', books: 1, bookLabels: ['1'],
    greekEdition: 'Test edition', greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    citation: { scheme: 'dk', copyAbbr: 'Fix. B', dkChapter: 1, series: 'B' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture work for the Reader.svelte expandedCitation test.',
  };
  return {
    ...actual,
    getWork: (id: string) => (id === 'ECFIX' ? fixture : actual.getWork(id)),
    workPath: (id: string, book = 1) =>
      id === 'ECFIX' ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function bookWith(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-B1', column: 'B1',
        greek: [{ n: 1, text: 'Direct-head Greek line', tokens: [], role: 'context' }],
        english: { text: 'Direct-head English line.', notes: [], markers: [] },
        // One run, one direct entry, WITH an apparatus ref (finding 1: the
        // apparatus field must round-trip and render, verbatim, unexpanded).
        expandedCitation: [[
          {
            verbatim: 'SIMPL. Phys. 155, 30 (D. 476)',
            resolution: 'direct',
            authorDisplay: 'Simplicius',
            work: { title: 'in Physica', italic: true },
            locus: '155, 30',
            apparatus: '(D. 476)',
            flags: [],
            dashInherited: false,
          },
        ]],
      },
      {
        // DEFECT 2 regression, real Heraclitus B37 run structure: the
        // column carries TWO separate context runs -- a Latin quote-intro
        // head ("COLUMELLA VIII 4...") that resolves directly, then the
        // Diels-attributed Greek fragment words themselves (role: 'text',
        // the actual quotation), then a second, unrelated context run
        // ("[vgl. B 13],", an editorial cross-reference) that does NOT
        // resolve. These must render as two SEPARATE `.expanded-citation`
        // lines, never merged into one semicolon-joined false attribution.
        id: 'seg-B37', column: 'B37',
        greek: [
          { n: 1, role: 'context', text: 'COLUMELLA VIII 4 si vero credimus Empedocli Agrigentino qui dixit', tokens: [] },
          { n: 2, role: 'text', text: 'λύκοι δὴ ὠρύονται', tokens: [{ t: 'λύκοι', o: 0, k: 'lukoi' }] },
          { n: 3, role: 'context', text: '[vgl. B 13],', tokens: [] },
        ],
        english: { text: 'Two-run English line.', notes: [], markers: [] },
        expandedCitation: [
          [
            {
              verbatim: 'COLUMELLA VIII 4',
              resolution: 'direct',
              authorDisplay: 'Columella',
              work: { title: 'De Re Rustica', italic: true },
              locus: 'VIII 4',
              flags: [],
              dashInherited: false,
            },
          ],
          [
            {
              verbatim: '[vgl. B 13],',
              resolution: 'verbatim',
              flags: ['unmappable'],
            },
          ],
        ],
      },
      {
        id: 'seg-B3', column: 'B3',
        greek: [{ n: 1, text: 'A plain column with no declaration', tokens: [] }],
        english: { text: 'Plain English line.', notes: [], markers: [] },
      },
      {
        id: 'seg-B4', column: 'B4',
        greek: [{ n: 1, text: 'Opaque-title Greek line', tokens: [], role: 'context' }],
        english: { text: 'Opaque-title English line.', notes: [], markers: [] },
        expandedCitation: [[
          {
            verbatim: 'PS.-GALEN hist. philos. 3',
            resolution: 'direct',
            authorDisplay: 'Pseudo-Galen',
            work: { title: '(commentary on Aristotle)', italic: false },
            locus: '3',
            flags: [],
            dashInherited: false,
          },
        ]],
      },
    ],
  };
}

// Sol adversarial-review regression fixture (finding 1, run-to-block
// misassignment): a single segment split into THREE blocks by chapterStarts,
// where context run A starts in block 0 and (as consecutive context lines)
// continues into block 1, run B starts fresh in block 1, and run C starts
// fresh in block 2. Every cut lands on a line boundary (wordIndex: 0) so no
// line is split mid-line -- isolates the run-to-block bug from lineSlice.
function bookWithSplitRun(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-SPLIT', column: 'SPLIT',
        greek: [
          { n: 1, text: 'RUN-A-HEAD-ONE', tokens: [], role: 'context' },
          { n: 2, text: 'RUN-A-HEAD-TWO', tokens: [], role: 'context' },
          { n: 3, text: 'logos', tokens: [{ t: 'logos', o: 0, k: 'logos' }], role: 'text' },
          { n: 4, text: 'RUN-B-HEAD', tokens: [], role: 'context' },
          { n: 5, text: 'allos', tokens: [{ t: 'allos', o: 0, k: 'allos' }], role: 'text' },
          { n: 6, text: 'RUN-C-HEAD', tokens: [], role: 'context' },
        ],
        english: { text: 'English A. English B. English C.', notes: [], markers: [] },
        chapterStarts: [
          { chapter: 'B', beforeLine: 2, wordIndex: 0, engOffset: 12, bekker: 'b' },
          { chapter: 'C', beforeLine: 5, wordIndex: 0, engOffset: 24, bekker: 'c' },
        ],
        expandedCitation: [
          [{ verbatim: 'RUN-A-HEAD-ONE', resolution: 'direct', authorDisplay: 'AuthorA', work: { title: 'Work A', italic: true }, locus: '1', flags: [], dashInherited: false }],
          [{ verbatim: 'RUN-B-HEAD', resolution: 'direct', authorDisplay: 'AuthorB', work: { title: 'Work B', italic: true }, locus: '4', flags: [], dashInherited: false }],
          [{ verbatim: 'RUN-C-HEAD', resolution: 'direct', authorDisplay: 'AuthorC', work: { title: 'Work C', italic: true }, locus: '6', flags: [], dashInherited: false }],
        ],
      },
    ],
  };
}

// Sol adversarial-review regression fixture (finding 2, empty run slots):
// stage1 emits an empty inner list to keep run positions aligned when the
// first context run's head text doesn't resolve (e.g. "Nach B 6 folgt"),
// followed by a second run that does resolve.
function bookWithEmptyRun(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-EMPTYRUN', column: 'EMPTYRUN',
        greek: [
          { n: 1, text: 'Nach B 6 folgt', tokens: [], role: 'context' },
          { n: 2, text: 'logos', tokens: [{ t: 'logos', o: 0, k: 'logos' }], role: 'text' },
          { n: 3, text: '[vgl. B 13],', tokens: [], role: 'context' },
        ],
        english: { text: 'Empty-run English line.', notes: [], markers: [] },
        expandedCitation: [
          [],
          [{ verbatim: '[vgl. B 13],', resolution: 'verbatim', flags: ['unmappable'] }],
        ],
      },
    ],
  };
}

// Rule E (John, 2026-09-24): a filled-in dash renders exactly like any other
// expanded citation. Two columns carry the same citation, one reached
// directly, one through a dash; their lines must be indistinguishable.
function bookWithDash(): BookData {
  const cite = { authorDisplay: 'Diogenes Laertius', work: { title: 'Vitae Philosophorum', italic: true }, locus: 'IX 2' };
  return {
    book: 1,
    segments: [
      {
        id: 'seg-D1', column: 'D1',
        greek: [{ n: 1, text: 'DIOG. IX 2', tokens: [], role: 'context' }],
        english: { text: 'Direct.', notes: [], markers: [] },
        expandedCitation: [[{ verbatim: 'DIOG. IX 2', resolution: 'direct', ...cite, flags: [], dashInherited: false }]],
      },
      {
        id: 'seg-D2', column: 'D2',
        greek: [{ n: 1, text: '— —2', tokens: [], role: 'context' }],
        english: { text: 'Dash.', notes: [], markers: [] },
        expandedCitation: [[{ verbatim: '— —2', resolution: 'dash', ...cite, flags: ['dash-e5'], dashInherited: true }]],
      },
    ],
  };
}

// A DK misprint printed corrected, with a note (John, 2026-09-24; real
// Antiphon B107, DK "V 441" for Pollux V 141). The note follows the
// citation in a quieter style; an entry with no note gets none.
function bookWithCorrection(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-C1', column: 'C1',
        greek: [{ n: 1, text: '—V 441', tokens: [], role: 'context' }],
        english: { text: 'Corrected.', notes: [], markers: [] },
        expandedCitation: [[{
          verbatim: '—V 441', resolution: 'dash', authorDisplay: 'Julius Pollux',
          work: { title: 'Onomasticon', italic: true }, locus: 'V 141',
          flags: ['corrected'], dashInherited: true, note: 'DK prints “V 441”.',
        }]],
      },
    ],
  };
}

// An edition with no author (John's ruling, 2026-09-24: Bekker's Anecdota
// Graeca, real Antiphon B85 "—p. 418, 6"): the pipeline omits
// `authorDisplay`, and the line opens with the work -- no stray comma.
function bookWithNoAuthor(): BookData {
  return {
    book: 1,
    segments: [
      {
        id: 'seg-N1', column: 'N1',
        greek: [{ n: 1, text: '—p. 418, 6', tokens: [], role: 'context' }],
        english: { text: 'No author.', notes: [], markers: [] },
        expandedCitation: [[{
          verbatim: '—p. 418, 6', resolution: 'dash',
          work: { title: 'Anecdota Graeca', italic: true }, locus: 'I, Lex. VI p. 418, 6',
          flags: ['dash-e5'], dashInherited: true,
        }]],
      },
    ],
  };
}

// A work with no locus of its own (Grok content review item 6, real
// Democritus B127-128): Herodian's De prosodia catholica, preserved "bei
// Theogn. p. 79 [I 355, 19 L.]" -- the note is apparatus and the locus is
// empty. The line never prints an empty separator: one space between title
// and apparatus, none after a title that stands alone.
function bookWithNoLocus(): BookData {
  const herodian = { resolution: 'direct' as const, authorDisplay: 'Herodian (grammarian)', flags: [], dashInherited: false };
  return {
    book: 1,
    segments: [
      {
        id: 'seg-H1', column: 'H1',
        greek: [{ n: 1, text: 'HERODIAN. π. καθολ. προσ. bei Theogn. p. 79 [I 355, 19 L.]', tokens: [], role: 'context' }],
        english: { text: 'No locus, apparatus.', notes: [], markers: [] },
        expandedCitation: [[{
          ...herodian, verbatim: 'HERODIAN. π. καθολ. προσ. bei Theogn. p. 79 [I 355, 19 L.]',
          work: { title: 'De Prosodia Catholica', italic: true }, locus: '', apparatus: 'bei Theogn. p. 79 [I 355, 19 L.]',
        }]],
      },
      {
        id: 'seg-H2', column: 'H2',
        greek: [{ n: 1, text: 'HERODIAN. π. μον. λέξ.', tokens: [], role: 'context' }],
        english: { text: 'No locus at all.', notes: [], markers: [] },
        expandedCitation: [[{
          ...herodian, verbatim: 'HERODIAN. π. μον. λέξ.',
          work: { title: 'Περὶ μονήρους λέξεως', italic: true }, locus: '',
        }]],
      },
    ],
  };
}

// The stage also reads a dash head from a line the spine marks as text
// (Heraclitus B42) and from a later line of a context run (Democritus B82
// "—*48."); the reader must count those lines as run starts too, or every
// later run lands under the wrong block.
function bookWithDashHeadLines(): BookData {
  const run = (a: string) => [{ verbatim: a, resolution: 'direct' as const, authorDisplay: a, work: { title: 'W', italic: true }, locus: '1', flags: [], dashInherited: false }];
  return {
    book: 1,
    segments: [
      {
        id: 'seg-DH', column: 'DH',
        greek: [
          { n: 1, text: 'DIOG. IX 1', tokens: [], role: 'context' },
          { n: 2, text: 'logos', tokens: [{ t: 'logos', o: 0, k: 'logos' }], role: 'text' },
          { n: 3, text: '— —ὅνπερ καὶ Μίδην', tokens: [], role: 'text' },
          { n: 4, text: 'ἔλεγεν', tokens: [], role: 'context' },
          { n: 5, text: '—47.', tokens: [], role: 'context' },
          { n: 6, text: '—*48. εὐδαίμων', tokens: [], role: 'context' },
        ],
        english: { text: 'English A. English B. English C.', notes: [], markers: [] },
        chapterStarts: [
          { chapter: 'B', beforeLine: 3, wordIndex: 0, engOffset: 12, bekker: 'b' },
          { chapter: 'C', beforeLine: 5, wordIndex: 0, engOffset: 24, bekker: 'c' },
        ],
        expandedCitation: [run('RUN-A'), run('RUN-B'), run('RUN-C'), run('RUN-D')],
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

describe('Reader.svelte DK source-citation expansion (docs/citation-expansion-wiring-design.md)', () => {
  it('renders a direct entry as "Author, italic-Work locus" with its apparatus ref, no italics on the whole line', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B1');
    const block = seg?.querySelector('.expanded-citation');
    expect(block).toBeTruthy();
    // Finding 1: apparatus rides along, verbatim, never expanded.
    expect(block?.textContent?.trim()).toBe('Simplicius, in Physica 155, 30 (D. 476)');
    const em = block?.querySelector('em');
    expect(em?.textContent).toBe('in Physica');
  });

  it('DEFECT 2 regression (real Heraclitus B37 run structure): two distinct context runs render as two separate lines, never merged into one attribution', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B37');
    const blocks = seg?.querySelectorAll('.expanded-citation');
    expect(blocks?.length).toBe(2);
    expect(blocks?.[0]?.textContent?.trim()).toBe('Columella, De Re Rustica VIII 4');
    expect(blocks?.[1]?.textContent?.trim()).toBe('[vgl. B 13],');
    // Neither run's text leaks into the other's line (the old bug: one
    // "; "-joined line inventing a single attribution DK never printed).
    expect(blocks?.[0]?.textContent).not.toContain('vgl');
    expect(blocks?.[1]?.textContent).not.toContain('Columella');
    // Finding 3: the verbatim run is not italicized just for being verbatim.
    const verbatimEntry = blocks?.[1]?.querySelector('.expanded-citation-verbatim');
    expect(verbatimEntry).toBeTruthy();
    expect(verbatimEntry && getComputedStyle(verbatimEntry).fontStyle).not.toBe('italic');
  });

  it('renders no block for a segment with no expandedCitation declared, alongside segments in the same render that do', async () => {
    // Non-vacuous: this only proves something if OTHER segments in this same
    // render DO show a block -- otherwise "renders nothing" would trivially
    // hold even with the whole feature unimplemented.
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    expect(document.querySelector('#col-B3')?.querySelector('.expanded-citation')).toBeNull();
    expect(document.querySelector('#col-B1')?.querySelector('.expanded-citation')).toBeTruthy();
    expect(document.querySelector('#col-B37')?.querySelectorAll('.expanded-citation').length).toBe(2);
  });

  it('never italicizes an opaque (DEFAULT) work title', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B4');
    const block = seg?.querySelector('.expanded-citation');
    expect(block?.textContent?.trim()).toBe('Pseudo-Galen, (commentary on Aristotle) 3');
    expect(block?.querySelector('em')).toBeNull();
  });

  it('places the expanded-citation block in the English column, not the Greek column', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWith() } });
    await flush();
    const seg = document.querySelector('#col-B1');
    const englishCol = seg?.querySelector('.english-col');
    const greekCol = seg?.querySelector('.greek-col');
    expect(englishCol?.querySelector('.expanded-citation')).toBeTruthy();
    expect(greekCol?.querySelector('.expanded-citation')).toBeNull();
  });

  it('Sol finding 1 regression: a run that starts before a chapterStarts cut and continues into the next block is not recounted as a new head in that block, so later runs land under the correct block', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithSplitRun() } });
    await flush();
    const seg = document.querySelector('#col-SPLIT');
    const englishCols = seg?.querySelectorAll('.english-col');
    expect(englishCols?.length).toBe(3);
    const citationsOf = (i: number) => englishCols?.[i]?.querySelectorAll('.expanded-citation');
    // Block 0: run A only.
    expect(citationsOf(0)?.length).toBe(1);
    expect(citationsOf(0)?.[0]?.textContent).toContain('AuthorA');
    // Block 1: run B only -- NOT also run C (the bug: block-local head
    // counting recounts run A's continuation as a new head in block 1,
    // over-consuming and pulling run C's citation in here too).
    expect(citationsOf(1)?.length).toBe(1);
    expect(citationsOf(1)?.[0]?.textContent).toContain('AuthorB');
    expect(citationsOf(1)?.[0]?.textContent).not.toContain('AuthorC');
    // Block 2: run C, not stranded empty.
    expect(citationsOf(2)?.length).toBe(1);
    expect(citationsOf(2)?.[0]?.textContent).toContain('AuthorC');
  });

  it('rule E: a filled-in dash renders exactly like a direct citation', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithDash() } });
    await flush();
    const direct = document.querySelector('#col-D1 .expanded-citation');
    const dash = document.querySelector('#col-D2 .expanded-citation');
    expect(dash?.textContent?.trim()).toBe('Diogenes Laertius, Vitae Philosophorum IX 2');
    expect(dash?.innerHTML).toBe(direct?.innerHTML);
    expect(dash?.querySelector('.expanded-citation-verbatim')).toBeNull();
  });

  it('a corrected misprint prints its note after the citation, in the muted credit style', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithCorrection() } });
    await flush();
    const block = document.querySelector('#col-C1 .expanded-citation');
    expect(block?.textContent?.trim()).toBe('Julius Pollux, Onomasticon V 141 DK prints “V 441”.');
    const note = block?.querySelector('.context-english-credit');
    expect(note?.textContent).toBe('DK prints “V 441”.');
    // The note sits after the citation, never inside it.
    expect(block?.querySelector('.expanded-citation-entry')?.textContent).toBe('Julius Pollux, Onomasticon V 141');
    // A citation with no note carries none (bookWithDash's direct entry).
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithDash() } });
    await flush();
    expect(document.querySelector('#col-D1 .expanded-citation .context-english-credit')).toBeNull();
  });

  it('an entry with no author opens with the italic work (Bekker, Anecdota Graeca)', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithNoAuthor() } });
    await flush();
    const entry = document.querySelector('#col-N1 .expanded-citation-entry');
    expect(entry?.textContent).toBe('Anecdota Graeca I, Lex. VI p. 418, 6');
    expect(entry?.querySelector('em')?.textContent).toBe('Anecdota Graeca');
  });

  it('an empty locus leaves no empty separator (Herodian, content review item 6)', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithNoLocus() } });
    await flush();
    const withApparatus = document.querySelector('#col-H1 .expanded-citation-entry');
    expect(withApparatus?.textContent).toBe('Herodian (grammarian), De Prosodia Catholica bei Theogn. p. 79 [I 355, 19 L.]');
    const alone = document.querySelector('#col-H2 .expanded-citation-entry');
    expect(alone?.textContent).toBe('Herodian (grammarian), Περὶ μονήρους λέξεως');
  });

  it('rule E: dash heads on a text line or later in a context run count as run starts', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithDashHeadLines() } });
    await flush();
    const englishCols = document.querySelectorAll('#col-DH .english-col');
    expect(englishCols.length).toBe(3);
    const texts = (i: number) => [...(englishCols[i]?.querySelectorAll('.expanded-citation') ?? [])].map((d) => d.textContent?.trim().split(',')[0]);
    expect(texts(0)).toEqual(['RUN-A']);
    expect(texts(1)).toEqual(['RUN-B']);
    expect(texts(2)).toEqual(['RUN-C', 'RUN-D']);
  });

  it('Sol finding 2 regression: an empty run slot (kept for positional alignment) renders no blank .expanded-citation line', async () => {
    render(Reader, { props: { work: 'ECFIX', bookNum: 1, bookData: bookWithEmptyRun() } });
    await flush();
    const seg = document.querySelector('#col-EMPTYRUN');
    const citations = seg?.querySelectorAll('.expanded-citation');
    // Only the resolving second run renders -- the empty first run produces
    // no div at all (the bug: an empty, blank-looking div renders for it).
    expect(citations?.length).toBe(1);
    expect(citations?.[0]?.textContent?.trim()).toBe('[vgl. B 13],');
  });
});
