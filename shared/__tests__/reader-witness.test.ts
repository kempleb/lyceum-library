import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader from '../components/Reader.svelte';
import type { BookData, GreekLine } from '../lib/data';
import type { Work } from '../lib/works';

// Segment.witnesses (dk_witness.py's split_witnesses, wired via
// stage7_emit.py) acceptance: a column WITH witnesses renders them as
// separate .frag-witness rows instead of one undifferentiated context
// blob; a column WITHOUT witnesses, or one where substitution isn't
// structurally safe (prose-flow.ts's singlePureContextRun), renders exactly
// as it did before this field existed.

vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  const common = {
    author: 'Test',
    language: 'grc' as const,
    workType: 'fragments' as const,
    books: 1,
    bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture for witness-row Reader tests.',
  };
  const fixtures: Record<string, Work> = {
    DKPROSE: {
      id: 'DKPROSE', title: 'Fixture DK Prose', abbr: 'Fix. B', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 97', dkChapter: 97, series: 'B' },
    },
    DKVERSE: {
      id: 'DKVERSE', title: 'Fixture DK Verse', abbr: 'Fix. V', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 96', dkChapter: 96, series: 'B', lines: true },
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book: number) =>
      fixtures[id] ? `/read/test-author/${id}/book-${book}` : actual.workPath(id, book),
  };
});

function gl(n: number, role: GreekLine['role'], text: string, tokens: GreekLine['tokens'] = []): GreekLine {
  return { n, role, text, tokens };
}

async function flush(ms = 30) {
  await new Promise((r) => setTimeout(r, ms));
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('Reader.svelte DK witness rows (Segment.witnesses)', () => {
  it('pure-context prose column: renders one .frag-witness row per witness, label small-caps beside its text', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B14',
        column: 'B14',
        greek: [
          gl(1, 'context', 'ETYM. GEN. ἀλαπάξαι· ἐκπορθῆσαι. ANECD. BEKK. LEX. VI 374, 14 ἀμέλει.'),
        ],
        witnesses: [
          { source: 'ETYM. GEN.', text: 'ἀλαπάξαι· ἐκπορθῆσαι.' },
          { source: 'ANECD. BEKK. LEX. VI 374, 14', text: 'ἀμέλει.' },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const rows = container.querySelectorAll('.frag-witness');
    expect(rows.length).toBe(2);
    expect(rows[0]?.querySelector('.frag-witness-source')?.textContent).toBe('ETYM. GEN.');
    expect(rows[0]?.textContent).toContain('ἀλαπάξαι· ἐκπορθῆσαι.');
    expect(rows[1]?.querySelector('.frag-witness-source')?.textContent).toBe('ANECD. BEKK. LEX. VI 374, 14');
    // The raw undifferentiated blob no longer renders as one ordinary
    // (non-witness) flow paragraph — it was fully replaced by the two
    // witness rows (which are themselves .frag-flow, for the same flex
    // layout every other DK prose row uses).
    expect(container.querySelector('.frag-flow:not(.frag-witness)')).toBeNull();
    expect(container.querySelector('.frag-source-head')).toBeNull();
  });

  it('unlabelled witness (no `source`) renders as plain apparatus text, no small-caps label', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B300',
        column: 'B300',
        greek: [
          gl(1, 'context', 'a wholly-Latin witness with no separable label'),
        ],
        witnesses: [
          { text: 'a wholly-Latin witness with no separable label' },
          { source: 'GAL. de simpl.', text: 'παραπλήσια δὲ τῶι Ξενοκράτει.' },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const rows = container.querySelectorAll('.frag-witness');
    expect(rows.length).toBe(2);
    expect(rows[0]?.querySelector('.frag-witness-source')).toBeNull();
    expect(rows[0]?.textContent).toContain('a wholly-Latin witness with no separable label');
    expect(rows[1]?.querySelector('.frag-witness-source')?.textContent).toBe('GAL. de simpl.');
  });

  it('verse column: single pure context frame substitutes witness rows instead of the frame flow', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B17',
        column: 'B17',
        greek: [
          gl(-1, 'context', 'SIMPL. Phys. 157, 25 first witness. PLUT. Amat. 13 second witness.'),
          gl(1, 'text', 'ἵπποι ταί με φέρουσιν', [{ t: 'ἵπποι', o: 0, k: 'ippoi' }]),
        ],
        witnesses: [
          { source: 'SIMPL. Phys. 157, 25', text: 'first witness.' },
          { source: 'PLUT. Amat. 13', text: 'second witness.' },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKVERSE', bookNum: 1, bookData: book } });
    await flush();

    const rows = container.querySelectorAll('.frag-witness');
    expect(rows.length).toBe(2);
    expect(container.querySelector('.frag-source-head')).toBeNull();
    // The verse quote line itself is untouched.
    expect(container.querySelector('#LB17-1')).toBeTruthy();
  });

  it('column with no `witnesses` field renders exactly as before (no .frag-witness anywhere)', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B81',
        column: 'B81',
        greek: [
          gl(1, 'context', 'PHILODEM. Rhet. I. ἡ δὲ τῶν ῥητόρων'),
          gl(2, 'text', 'κοπίδων ἐστὶν ἀρχηγός', [{ t: 'κοπίδων', o: 0, k: 'kopidwn' }]),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-witness')).toBeNull();
    expect(container.querySelector('.frag-source-head')?.textContent).toContain('PHILODEM. Rhet. I.');
  });

  it('impure column (context interleaved with the philosopher\'s own quoted words) falls back to unsplit rendering, even though `witnesses` is present', async () => {
    // Mirrors the real corpus shape dk_witness.py's own docstring calls out
    // (Empedocles B7/B58/B92, kind: embedded): the Greek quotation sits
    // INSIDE the surrounding narrative, so a row-per-witness rendering
    // would misplace it. singlePureContextRun's own eligibility guard
    // means this segment renders unchanged, not row-substituted.
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-embedded',
        column: 'B7',
        greek: [
          gl(1, 'context', 'SIMPL. in Phys. quoting the phrase'),
          gl(2, 'text', 'the actual Empedoclean words', [{ t: 'words', o: 0, k: 'test' }]),
          gl(3, 'context', 'and PLUT. continuing the frame'),
        ],
        witnesses: [
          { source: 'SIMPL. in Phys.', text: 'quoting the phrase' },
          { source: 'PLUT.', text: 'continuing the frame' },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-witness')).toBeNull();
    // Old rendering still applies: one flowing paragraph mixing frag-txt/frag-ctx.
    expect(container.querySelectorAll('.frag-flow').length).toBeGreaterThan(0);
    expect(container.querySelector('.frag-flow')?.textContent).toContain('the actual Empedoclean words');
  });
});
