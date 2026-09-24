import { render, fireEvent } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Reader, {
  greekLineIdForScrollCite,
  greekLineIdToCite,
} from '../components/Reader.svelte';
import type { BookData, GreekLine } from '../lib/data';
import type { Work } from '../lib/works';

// Reader-layer acceptance for docs/prose-flow-design.md: prose columns flow
// as one paragraph; verse columns keep lineation; incipit stubs mute text;
// scroll-spy still finds .greek-line[id] per prose column.

vi.mock('../lib/works', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/works')>();
  // Inline fixture base — vi.mock is hoisted; outer consts are not yet init.
  const common = {
    author: 'Test',
    language: 'grc' as const,
    workType: 'fragments' as const,
    books: 1,
    bookLabels: ['1'],
    greekEdition: 'Test edition',
    greekSource: { short: 'Test', full: 'Test edition, full citation.' },
    translations: [{ id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const }],
    blurb: 'Fixture for prose-flow Reader tests.',
  };
  const fixtures: Record<string, Work> = {
    // Lineless DK prose (Heraclitus-shaped).
    DKPROSE: {
      id: 'DKPROSE', title: 'Fixture DK Prose', abbr: 'Fix. B', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 97', dkChapter: 97, series: 'B' },
    },
    // Verse DK (Parmenides-shaped).
    DKVERSE: {
      id: 'DKVERSE', title: 'Fixture DK Verse', abbr: 'Fix. V', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 96', dkChapter: 96, series: 'B', lines: true },
    },
    // Lineless DK with one declared incipit column.
    DKINCIP: {
      id: 'DKINCIP', title: 'Fixture DK Incipit', abbr: 'Fix. I', ...common,
      citation: {
        scheme: 'dk', copyAbbr: 'DK 95', dkChapter: 95, series: 'B',
        incipitColumns: [{ column: 'B9', sha256_16: '0123456789abcdef' }],
      },
    },
    // Freeman pilot shape: title kind + chip.
    DKFREEM: {
      id: 'DKFREEM', title: 'Fixture Freeman Prose', abbr: 'Fix. F', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 94', dkChapter: 94, series: 'B' },
    },
    // verse-line (Lucretius' DRN-shaped): one segment per verse line, cited
    // book.line ("1.1", "1.2"…), no user-facing line axis of its own.
    VERSELINE: {
      id: 'VERSELINE', title: 'Fixture Verse-Line', abbr: 'Fix. VL', ...common,
      language: 'lat', workType: 'verse' as const,
      citation: { scheme: 'verse-line', copyAbbr: 'Fix.' },
    },
    // verse-line WITH a second (compare-mode) translation — finding 5's own
    // fixture; kept separate from VERSELINE so existing single-translation
    // verse-line tests are untouched.
    VERSELINE2: {
      id: 'VERSELINE2', title: 'Fixture Verse-Line Compare', abbr: 'Fix. VL2', ...common,
      language: 'lat', workType: 'verse' as const,
      citation: { scheme: 'verse-line', copyAbbr: 'Fix.' },
      translations: [
        { id: 'test', name: 'Test Translator (Test, 1900)', short: 'Test', slot: 'english' as const },
        { id: 'alt', name: 'Alt Translator (Alt, 1950)', short: 'Alt', slot: 'secondary' as const },
      ],
    },
    // Mixed work: verse columns (positive text n) + prose columns (negative n).
    DKMIX: {
      id: 'DKMIX', title: 'Fixture DK Mixed', abbr: 'Fix. M', ...common,
      citation: { scheme: 'dk', copyAbbr: 'DK 88', dkChapter: 88, series: 'B', lines: true },
    },
    // item 23: book-section chapter-level work (Discourses/Marcus/DL/Cicero-
    // shaped) — no user-facing line axis (hideLineNumbers), no dk role tags.
    BOOKSEC: {
      id: 'BOOKSEC', title: 'Fixture Book-Section Work', abbr: 'Fix. BS', ...common,
      citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. BS' },
    },
    // linedGreek pilot (Discourses) + its extension to Lives/de-finibus/etc.
    // (2026-08-28) — a book-section work opted OUT of bookSectionFlow's
    // chapter-wide flow, into the ordinary lineate (block-per-line) branch.
    // Kept separate from BOOKSEC so every existing bookSectionFlow test above
    // stays untouched.
    // Carries BOTH `linedGreek` (its own book-section-only job: force the
    // ordinary lineate branch) and `linedSource` (the print-line painting
    // gate, docs/lined-rollout-plan.md Stage 3) -- mirroring the real
    // Discourses registry block, which sets both.
    BOOKSECLINED: {
      id: 'BOOKSECLINED', title: 'Fixture Lined Book-Section Work', abbr: 'Fix. BSL', ...common,
      citation: { scheme: 'book-section', hideLineNumbers: true, copyAbbr: 'Fix. BSL', linedGreek: true, linedSource: true },
    },
    // Print-lineation rollout wave 1 (docs/lined-rollout-plan.md Stage 3):
    // a `section`-scheme work opted into the print-line paint -- Enchiridion/
    // Epicurus-shaped. Kept separate from FLATSEC (below), which stays the
    // pre-wave-1 regression control and must render byte-identical.
    FLATSECLINED: {
      id: 'FLATSECLINED', title: 'Fixture Lined Flat-Section Work', abbr: 'Fix. FSL', ...common,
      citation: { scheme: 'section', hideLineNumbers: true, copyAbbr: 'Fix. Ench.', linedSource: true },
    },
    // Regression control: 'letter' scheme (Seneca Epistulae-shaped) — NOT in
    // item 23's scope; must render byte-identical to before this change.
    LETTER: {
      id: 'LETTER', title: 'Fixture Letter Work', abbr: 'Fix. L', ...common,
      language: 'lat' as const,
      citation: { scheme: 'letter', copyAbbr: 'Fix. Ep.' },
    },
    // Regression control: flat 'section' scheme (Enchiridion-shaped) — NOT
    // in item 23's scope; must render byte-identical to before this change.
    FLATSEC: {
      id: 'FLATSEC', title: 'Fixture Flat-Section Work', abbr: 'Fix. FS', ...common,
      citation: { scheme: 'section', hideLineNumbers: true, copyAbbr: 'Fix. Ench.' },
    },
  };
  return {
    ...actual,
    getWork: (id: string) => fixtures[id] ?? actual.getWork(id),
    workPath: (id: string, book = 1) =>
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

describe('Reader.svelte DK prose-flow (docs/prose-flow-design.md)', () => {
  it('B81-shaped prose: mixed head peels; one .frag-flow body, punctuation hugged, Πυθαγόραν inline', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B81',
        column: 'B81',
        greek: [
          gl(1, 'context', 'PHILODEM. Rhet. I. ἡ δὲ τῶν ῥητόρων'),
          gl(2, 'text', 'κοπίδων ἐστὶν ἀρχηγός', [{ t: 'κοπίδων', o: 0, k: 'kopidwn' }]),
          gl(3, 'context', '. SCHOL. in Eur. ὥστε μὴ τὸν'),
          gl(4, 'text', 'Πυθαγόραν', [{ t: 'Πυθαγόραν', o: 0, k: 'puqagoran' }]),
          gl(5, 'context', 'εὑρετὴν ὄντα τῶν ἀληθινῶν'),
          gl(6, 'text', 'κοπίδων', [{ t: 'κοπίδων', o: 0, k: 'kopidwn' }]),
          gl(7, 'context', "μηδὲ τὸν Ἡράκλειτον."),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const head = container.querySelector('.frag-source-head');
    expect(head?.textContent).toContain('PHILODEM. Rhet. I.');
    const flows = container.querySelectorAll('.frag-flow');
    expect(flows.length).toBe(1);
    // Body is one flow paragraph (plus optional source-head sibling, not a .greek-line stack).
    const greekLines = container.querySelectorAll('.segment .greek-col > .greek-line');
    expect(greekLines.length).toBe(1);
    expect(greekLines[0]?.classList.contains('frag-flow')).toBe(true);

    const text = flows[0]?.textContent ?? '';
    expect(text).toContain('ἡ δὲ τῶν ῥητόρων');
    expect(text).toContain('Πυθαγόραν');
    expect(text).toContain('ἀρχηγός. SCHOL.');
    expect(text).toContain('τὸν Πυθαγόραν εὑρετὴν');
    // Tokens stay clickable.
    expect(container.querySelectorAll('.frag-flow .tok').length).toBeGreaterThanOrEqual(3);
    // Role spans present (leading Greek frame is frag-ctx; 3 text + 4 ctx body runs).
    expect(container.querySelectorAll('.frag-txt').length).toBe(3);
    expect(container.querySelectorAll('.frag-flow .frag-ctx').length).toBe(4);
    // Scroll-spy anchor: one .greek-line[id] at column granularity (column
    // token only — never run n; FIX B).
    const anchored = container.querySelectorAll('.greek-line[id]');
    expect(anchored.length).toBe(1);
    expect(anchored[0]?.id).toBe('LB81');
  });

  it('B1-shaped: pure source head on its own line; trailing period in flow as frag-ctx', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B1',
        column: 'B1',
        greek: [
          gl(1, 'context', 'SEXT. adv. math. VII 132 (Vgl. A 4. 16. B 51)'),
          gl(2, 'text', "τοῦ δὲ λόγου", [{ t: 'τοῦ', o: 0, k: 'tou' }, { t: 'δὲ', o: 4, k: 'de' }, { t: 'λόγου', o: 7, k: 'logou' }]),
          gl(3, 'context', '.'),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const head = container.querySelector('.frag-source-head');
    expect(head?.textContent).toContain('SEXT. adv. math.');
    const flow = container.querySelector('.frag-flow');
    expect(flow?.textContent?.replace(/\s+/g, ' ').trim()).toMatch(/λόγου\s*\./);
    // Period keeps context colour (frag-ctx), not reassigned to text.
    const ctxs = flow?.querySelectorAll('.frag-ctx') ?? [];
    expect([...ctxs].some((el) => el.textContent === '.')).toBe(true);
  });

  it('verse work column (Parmenides-shaped): pure Latin head + lineation; no frame flow', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B1',
        column: 'B1',
        greek: [
          gl(-1, 'context', 'SEXT. VII 111'),
          gl(1, 'text', 'ἵπποι ταί με φέρουσιν', [{ t: 'ἵπποι', o: 0, k: 'ippoi' }]),
          gl(2, 'text', 'ὅσον τ\' ἐπὶ θυμὸς', [{ t: 'ὅσον', o: 0, k: 'oson' }]),
          gl(3, 'text', 'ἱκάνοι,', [{ t: 'ἱκάνοι', o: 0, k: 'ikanoi' }]),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKVERSE', bookNum: 1, bookData: book } });
    await flush();

    // Sole pure-Latin frame peels to source-head; no leftover frame paragraph.
    expect(container.querySelector('.frag-source-head')?.textContent).toContain('SEXT. VII 111');
    expect(container.querySelector('.frag-flow')).toBeNull();
    // Verse text lines keep individual block .greek-line ids.
    expect(container.querySelector('#LB1-1')).toBeTruthy();
    expect(container.querySelector('#LB1-2')).toBeTruthy();
    expect(container.querySelector('#LB1-3')).toBeTruthy();
    // Line numbers shown for 1 (every 5th or 1).
    const nums = [...container.querySelectorAll('.greek-line .line-num')]
      .map((el) => el.textContent?.trim())
      .filter(Boolean);
    expect(nums).toContain('1');
  });

  it('B12-shaped verse: source head own line; leading/trailing frame flow; verse lineated; hyphens healed', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B12',
        column: 'B12',
        greek: [
          gl(-1, 'context', 'SEXT. adv. math. I 289 Ὅμηρος δὲ καὶ Ἡσίοδος κατὰ τὸν Κολοφώνιον'),
          gl(-1, 'context', 'Ξενοφάνη'),
          gl(1, 'text', 'ὡς πλεῖστ(α) ἐφθέγξαντο θεῶν ἀθεμίστια ἔργα,', [
            { t: 'ὡς', o: 0, k: 'ws' },
            { t: 'πλεῖστ(α', o: 3, k: 'pleista' },
          ]),
          gl(2, 'text', 'κλέπτειν μοιχεύειν τε καὶ ἀλλήλους ἀπατεύειν.', [
            { t: 'κλέπτειν', o: 0, k: 'kleptein' },
          ]),
          gl(
            -2,
            'context',
            "Κρόνος μὲν γὰρ ἐφ' οὗ τὸν πατέρα ἠνδρο- τόμησε καὶ τῆς ἡγε- μονίας κτλ.",
          ),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKVERSE', bookNum: 1, bookData: book } });
    await flush();

    const head = container.querySelector('.frag-source-head');
    expect(head?.textContent?.trim()).toBe('SEXT. adv. math. I 289');

    const flows = container.querySelectorAll('.frag-flow');
    expect(flows.length).toBe(2);

    // Leading frame: one flowing paragraph (no .greek-line.context block children).
    const lead = flows[0]!;
    expect(lead.querySelectorAll('.frag-ctx').length).toBeGreaterThanOrEqual(1);
    expect(lead.querySelector('.frag-txt')).toBeNull();
    const leadText = lead.textContent?.replace(/\s+/g, ' ').trim() ?? '';
    expect(leadText).toContain('Ὅμηρος δὲ καὶ Ἡσίοδος');
    expect(leadText).toContain('Ξενοφάνη');
    // No hanging-indent block context lines for the frame.
    expect(container.querySelectorAll('.greek-line.context').length).toBe(0);
    // Leading flow is a single .frag-flow, not nested per-print-line children.
    expect(lead.querySelectorAll('.greek-line').length).toBe(0);

    // Verse quote intact + line numbers / ids.
    expect(container.querySelector('#LB12-1')).toBeTruthy();
    expect(container.querySelector('#LB12-2')).toBeTruthy();
    expect(container.querySelector('#LB12-1')?.textContent).toContain('ἐφθέγξαντο');
    expect(container.querySelector('#LB12-2')?.textContent).toContain('κλέπτειν');

    // Trailing frame: healed hyphens, frag-ctx only.
    const trail = flows[1]!;
    const trailText = trail.textContent ?? '';
    expect(trailText).toContain('ἠνδροτόμησε');
    expect(trailText).toContain('ἡγεμονίας');
    expect(trailText).not.toMatch(/ἠνδρο-\s/);
    expect(trailText).not.toMatch(/ἡγε-\s/);
    expect(trail.querySelector('.frag-txt')).toBeNull();

    // Frame flows do not steal the column-only id (verse lines own anchors).
    expect(lead.id).toBe('');
    expect(trail.id).toBe('');
    const ids = [...container.querySelectorAll('.greek-line[id]')].map((el) => el.id);
    expect(ids).toEqual(expect.arrayContaining(['LB12-1', 'LB12-2']));
    expect(ids).not.toContain('LB12');
  });

  it('incipit column: text-runs muted (frag-ctx + frag-incipit), data-incipit on the flow', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B9',
        column: 'B9',
        greek: [
          gl(1, 'context', 'Arist. EN'),
          gl(2, 'text', "’ἵπποι ... ἀληθής’", [{ t: 'ἵπποι', o: 1, k: 'ippoi' }]),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKINCIP', bookNum: 1, bookData: book } });
    await flush();

    const flow = container.querySelector('.frag-flow');
    expect(flow).toBeTruthy();
    expect(flow?.hasAttribute('data-incipit')).toBe(true);
    // Text-run is apparatus treatment, not frag-txt.
    expect(flow?.querySelector('.frag-txt')).toBeNull();
    expect(flow?.querySelector('.frag-incipit')).toBeTruthy();
    expect(flow?.querySelector('.frag-ctx .frag-incipit')?.textContent).toContain('ἵπποι');
  });

  it('Freeman title chip still renders beside a flowing prose column', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B1',
        column: 'B1',
        kind: 'title',
        greek: [
          gl(1, 'context', 'Δημοκρίτου'),
        ],
        english: { text: 'Of Democritus', notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKFREEM', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-title-chip')?.textContent).toBe('title');
    // Context-only title column still flows as apparatus (one flow or source-head).
    expect(container.querySelector('.segment[data-kind="title"]')).toBeTruthy();
  });

  it('note-kind segment gets an "editorial note" chit', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B2',
        column: 'B2',
        kind: 'note',
        greek: [gl(1, 'context', 'σχόλιον')],
        english: { text: 'A scholarly note.', notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKFREEM', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-title-chip')?.textContent).toBe('editorial note');
  });

  it('embedded-kind segment gets an "embedded quotation" chit', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B3',
        column: 'B3',
        kind: 'embedded',
        greek: [
          gl(1, 'context', 'Πορφύριος'),
          gl(2, 'text', 'ὀλίγα τῶν συγγραμμάτων'),
        ],
        english: { text: "(Porphyry: 'Few of the writings...')", notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKFREEM', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-title-chip')?.textContent).toBe('embedded quotation');
  });

  it('verbatim-kind segment gets no chit', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B4',
        column: 'B4',
        kind: 'verbatim',
        greek: [gl(1, 'text', 'πάντα ῥεῖ')],
        english: { text: 'All things flow.', notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKFREEM', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-title-chip')).toBeNull();
  });

  it('kindless segment gets no chit', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B5',
        column: 'B5',
        greek: [gl(1, 'text', 'πάντα ῥεῖ')],
        english: { text: 'All things flow.', notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKFREEM', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-title-chip')).toBeNull();
  });

  // FIX A (Reader layer): context-only Latin column keeps a body flow + scroll-
  // spy anchor; no empty .frag-source-head-only column.
  it('context-only all-Latin: no .frag-source-head; .frag-flow body has column anchor', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B79',
        column: 'B79',
        greek: [
          // Pure Latin (no Greek letters) — would peel if multi-run, must not
          // when it is the sole run.
          gl(-1, 'context', 'ARISTOT. eth. Eud. Gamma 1. 1229 a 40.'),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-source-head')).toBeNull();
    const flow = container.querySelector('.frag-flow');
    expect(flow).toBeTruthy();
    expect(flow?.classList.contains('frag-ctx') || flow?.querySelector('.frag-ctx')).toBeTruthy();
    expect(flow?.id).toBe('LB79');
    expect(container.querySelector('.greek-line[id="LB79"]')).toBeTruthy();
  });

  // FIX B: prose-flow DOM id is column-only; negative / zero n never produces
  // "LB4--1" / "LB4-0"; scroll-spy citeOf serializes bare column citation.
  it('prose flow with n=-1: id is LB4 (not LB4--1); hash citation is bare B4', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B4',
        column: 'B4',
        greek: [
          gl(-1, 'context', 'Clem. Strom. V 109 (II 400, 12 St.).'),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const flow = container.querySelector('.frag-flow');
    expect(flow?.id).toBe('LB4');
    expect(container.querySelector('#LB4--1')).toBeNull();
    const anchored = container.querySelector('.greek-line[id]') as HTMLElement;
    expect(anchored?.id).toBe('LB4');
    // Scroll-spy citeOf / idToCite: column-only prose id → bare column citation.
    const { formatCite } = await import('../lib/citation');
    const { parseLocation } = await import('../lib/data');
    const id = anchored.id;
    expect(greekLineIdToCite(id)).toEqual({ column: 'B4', line: null });
    const scroll = greekLineIdForScrollCite(id);
    expect(scroll).toEqual({ column: 'B4' });
    const cite = formatCite('DKPROSE', scroll!.column, scroll!.line);
    expect(cite).toBe('B4');
    expect(parseLocation('DKPROSE', cite)).toEqual({ column: 'B4', line: null });
  });

  // Column-only fallback must not swallow verse continuation ids L{col}-{n}-c{k}
  // (Discourses section-split cont pieces) into a malformed column like
  // "1.2-3-c5". citeOf (scroll-spy) still declines to resolve one — see the
  // next test — but idToCite (copy-citation) no longer returns null for one:
  // defect fix round (adversarial review, 2026-08-28) found that a selection
  // confined to a continuation piece used to drop its citation entirely,
  // because citeForGreekLine's own no-id fallback only runs for an element
  // WITHOUT an id, and a continuation piece always has one. See
  // greekLineIdToCite's own doc comment for why resolving it to {column,
  // line: n} (its chapter's own citation) is safe rather than a grammar change.
  describe('greek-line id parse: continuation vs prose-flow vs numbered', () => {
    it('idToCite: continuation L1.2-3-c5 resolves to its chapter\'s own column+line (defect fix, was null)', () => {
      expect(greekLineIdToCite('L1.2-3-c5')).toEqual({ column: '1.2', line: 3 });
      expect(greekLineIdToCite('L4.23-1-c2')).toEqual({ column: '4.23', line: 1 });
    });

    it('citeOf/scroll: continuation ids never yield a column token with -c{k}', () => {
      expect(greekLineIdForScrollCite('L1.2-3-c5')).toBeNull();
      expect(greekLineIdForScrollCite('L4.23-1-c2')).toBeNull();
      // Bare -c mid-line tail (no paraN digits) also non-digit-terminal for citeOf.
      expect(greekLineIdForScrollCite('L1094a-3-c')).toBeNull();
      for (const id of ['L1.2-3-c5', 'L4.23-1-c2', 'L1094a-3-c'] as const) {
        const g = greekLineIdForScrollCite(id);
        expect(g?.column ?? '').not.toMatch(/-c\d*$/);
      }
    });

    it('column-only prose LB4 / LB81 still resolve; numbered LB1-1 still resolves', () => {
      expect(greekLineIdToCite('LB4')).toEqual({ column: 'B4', line: null });
      expect(greekLineIdToCite('LB81')).toEqual({ column: 'B81', line: null });
      expect(greekLineIdToCite('LB1-1')).toEqual({ column: 'B1', line: 1 });
      expect(greekLineIdForScrollCite('LB4')).toEqual({ column: 'B4' });
      expect(greekLineIdForScrollCite('LB81')).toEqual({ column: 'B81' });
      expect(greekLineIdForScrollCite('LB1-1')).toEqual({ column: 'B1', line: 1 });
    });

    it('idToCite: mid-line bare -c tail still yields column+line (L1094a-3-c)', () => {
      // Prior idToCite regex `/^L(.+?)-(\d+)(?:-c)?$/` accepted bare -c.
      expect(greekLineIdToCite('L1094a-3-c')).toEqual({ column: '1094a', line: 3 });
    });

    // Stage 4 acceptance #4 (docs/lined-source-plan.md Q5): a lined-source
    // (Discourses-shaped) print-line id is the SAME `L{column}-{n}` shape
    // every other lineate scheme already produces — no new id grammar. `n`
    // here is the per-column print-line ordinal (Q1.1), not a TLG `<l>` @n.
    it('lined-source id: L1.1-24 resolves to {column: "1.1", line: 24}', () => {
      expect(greekLineIdToCite('L1.1-24')).toEqual({ column: '1.1', line: 24 });
    });

    // Print-lineation rollout wave 1 (docs/lined-rollout-plan.md Stage 3):
    // the same id shape for a flat `section`-scheme column — no book/chapter
    // prefix, just the bare citable-column token (Ruling 1b), e.g.
    // Enchiridion chapter 5's print line 12.
    it('lined-source id (flat section scheme): L5-12 resolves to {column: "5", line: 12}', () => {
      expect(greekLineIdToCite('L5-12')).toEqual({ column: '5', line: 12 });
    });
  });

  it('prose flow with n=0: id is still column-only LB5, not LB5-0', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B5',
        column: 'B5',
        greek: [
          gl(0, 'context', 'Some Latin apparatus only.'),
          gl(0, 'text', 'λόγος', [{ t: 'λόγος', o: 0, k: 'logos' }]),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-flow')?.id).toBe('LB5');
    expect(container.querySelector('#LB5-0')).toBeNull();
  });

  it('mixed work: verse line ids coexist with column-only prose ids (no collision)', async () => {
    const book: BookData = {
      book: 1,
      segments: [
        {
          id: 'seg-B1',
          column: 'B1',
          greek: [
            gl(-1, 'context', 'SEXT. VII 111'),
            gl(1, 'text', 'ἵπποι ταί με φέρουσιν', [{ t: 'ἵπποι', o: 0, k: 'ippoi' }]),
            gl(2, 'text', 'ὅσον τ\' ἐπὶ θυμὸς', [{ t: 'ὅσον', o: 0, k: 'oson' }]),
          ],
          english: null,
        },
        {
          id: 'seg-B31',
          column: 'B31',
          greek: [
            gl(-1, 'context', 'source apparatus Latin only.'),
            gl(-2, 'text', '’ὁμολογοῦνται…', [{ t: 'ὁμολογοῦνται', o: 1, k: 'omologountai' }]),
          ],
          english: null,
        },
      ],
    };
    const { container } = render(Reader, { props: { work: 'DKMIX', bookNum: 1, bookData: book } });
    await flush();

    // Verse column lineates: per-line ids.
    expect(container.querySelector('#LB1-1')).toBeTruthy();
    expect(container.querySelector('#LB1-2')).toBeTruthy();
    // Prose column flows: single column-only id.
    expect(container.querySelector('.frag-flow')?.id).toBe('LB31');
    expect(container.querySelector('#LB31')).toBeTruthy();
    expect(container.querySelector('#LB31--1')).toBeNull();
    // No id collision: every .greek-line[id] is unique.
    const ids = [...container.querySelectorAll('.greek-line[id]')].map((el) => el.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual(expect.arrayContaining(['LB1-1', 'LB1-2', 'LB31']));
  });

  // item 65 (REVIEW-CHECKLIST, John's ruling 2026-07-28): a whole-column
  // verbatim column (Gorgias B11/B11a-shaped — a continuous speech with no
  // DK letter-spacing, so every line is role='context') renders every run
  // at full text weight (frag-txt), not the muted apparatus weight
  // (frag-ctx) role='context' would otherwise carry.
  it('wholeColumnVerbatim segment: every run renders frag-txt, never frag-ctx', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B11',
        column: 'B11',
        wholeColumnVerbatim: true,
        greek: [
          gl(1, 'context', 'ἦν πόλει καὶ γένει'),
          gl(2, 'context', 'ἐπιφανεστάτη γενομένη'),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const flow = container.querySelector('.frag-flow');
    expect(flow).toBeTruthy();
    expect(flow?.querySelectorAll('.frag-ctx').length).toBe(0);
    expect(flow?.querySelectorAll('.frag-txt').length).toBeGreaterThan(0);
    expect(flow?.textContent?.replace(/\s+/g, ' ').trim()).toBe('ἦν πόλει καὶ γένει ἐπιφανεστάτη γενομένη');
  });

  // Regression control: an otherwise-identical column with NO
  // wholeColumnVerbatim flag keeps its ordinary muted context rendering —
  // byte-identical to every existing prose-flow test above.
  it('regression: the same B11-shaped lines WITHOUT the flag stay frag-ctx (muted)', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B11a',
        column: 'B11a',
        greek: [
          gl(1, 'context', 'ἦν πόλει καὶ γένει'),
          gl(2, 'context', 'ἐπιφανεστάτη γενομένη'),
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const flow = container.querySelector('.frag-flow');
    expect(flow).toBeTruthy();
    expect(flow?.querySelectorAll('.frag-txt').length).toBe(0);
    expect(flow?.querySelectorAll('.frag-ctx').length).toBeGreaterThan(0);
  });
});

// John's dashboard note on thales/testimonia A1: the DK context block quoting
// Diogenes Laertius 1.22–40 carries DK's own inline "(NN)" section markers,
// but rendered as one unbroken Greek paragraph while the English below it
// (Hicks, per-section) was already split into one paragraph per section.
// This suite pins the fix at the Reader layer: one .frag-flow per marker,
// a .greek-context-section-marker label per paragraph (mirroring the
// source-passage English's own .context-english-section-marker), a single
// column-anchor id (no DOM id collisions), and byte-identical rendering for
// a column with no such markers.
describe('Reader.svelte DK inline "(NN)" section-marker split (thales/testimonia A1)', () => {
  it('A1-shaped: one .frag-flow + one marker label per DK section, parallel to the English paragraph count', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-A1',
        column: 'A1',
        greek: [
          gl(1, 'context', 'DIOGENES LAERTIUS I 22—44. (22) Ἦν τοίνυν ὁ Θαλῆς πατρὸς μὲν Ἐξαμύου.'),
          gl(2, 'context', '(23) μετὰ δὲ τὰ πολιτικὰ τῆς φυσικῆς ἐγένετο θεωρίας.'),
          gl(3, 'context', '(24) ἔνιοι δὲ καὶ αὐτὸν πρῶτον εἰπεῖν φασιν ἀθανάτους τὰς ψυχάς.'),
        ],
        english: null,
        contextEnglish: [{
          sourceAuthor: 'Diogenes Laertius',
          sourceWork: 'Lives of Eminent Philosophers',
          locus: '1.22-24',
          status: 'translated',
          translationCredit: 'Hicks, 1925',
          text: 'Section 22 text.\n\nSection 23 text.\n\nSection 24 text.',
          sectionLoci: ['1.22', '1.23', '1.24'],
        }],
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const head = container.querySelector('.frag-source-head');
    expect(head?.textContent).toContain('DIOGENES LAERTIUS I 22—44.');

    // Greek: three flowing paragraphs, one per DK section — parallel to the
    // English's three .context-english-text paragraphs below.
    const greekFlows = container.querySelectorAll('.frag-flow');
    expect(greekFlows.length).toBe(3);
    const englishParas = container.querySelectorAll('.context-english-text');
    expect(englishParas.length).toBe(3);
    expect(greekFlows.length).toBe(englishParas.length);

    // Each paragraph carries its own marker label; the literal "(NN)" is
    // gone from the flowing Greek text itself.
    const markers = [...container.querySelectorAll('.greek-context-section-marker')].map((m) => m.textContent);
    expect(markers).toEqual(['(22)', '(23)', '(24)']);
    for (const f of greekFlows) expect(f.textContent).not.toMatch(/\(\d+\)/);

    // Only ONE column-anchor id exists (no DOM id collision across the three
    // paragraphs) and scroll-spy still finds it at column granularity.
    const anchored = container.querySelectorAll('.greek-line[id]');
    expect(anchored.length).toBe(1);
    expect(anchored[0]?.id).toBe('LA1');
  });

  it('a column with no "(NN)" markers renders exactly as before: one .frag-flow, no marker label', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B97',
        column: 'B97',
        greek: [gl(1, 'context', 'ἀρχὴν δὲ τῶν πάντων ὕδωρ ὑπεστήσατο.')],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.frag-flow').length).toBe(1);
    expect(container.querySelectorAll('.greek-context-section-marker').length).toBe(0);
    const flow = container.querySelector('.frag-flow');
    expect(flow?.textContent?.trim()).toBe('ἀρχὴν δὲ τῶν πάντων ὕδωρ ὑπεστήσατο.');
    expect(flow?.id).toBe('LB97');
  });

  // Fix round, finding 1 (Sol review): Gorgias A10's bibliographic year
  // "[Neue Jahrb. Suppl. 14 (1848) ed. A. Jahn]" used to false-positive as
  // a marker + paragraph break. A segment with NO contextEnglish declared
  // must render byte-identical: one flow, no marker label, "(1848)" intact.
  it('Gorgias A10 shape: bibliographic year with no contextEnglish declared renders byte-identical', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-A10',
        column: 'A10',
        greek: [gl(1, 'context', '[Neue Jahrb. Suppl. 14 (1848) ed. A. Jahn]')],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.frag-flow').length).toBe(1);
    expect(container.querySelectorAll('.greek-context-section-marker').length).toBe(0);
    const flow = container.querySelector('.frag-flow');
    expect(flow?.textContent?.trim()).toBe('[Neue Jahrb. Suppl. 14 (1848) ed. A. Jahn]');
    expect(flow?.id).toBe('LA10');
  });

  // Fix round, finding 2 (Sol review): only the FIRST marker paragraph
  // carries the column-anchor id; a selection inside a LATER paragraph must
  // still resolve to the same column's citation, not drop it.
  it('finding 2: a selection inside a second marker-split paragraph still resolves the owning column\'s citation', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-A1',
        column: 'A1',
        greek: [
          gl(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς πατρὸς μὲν Ἐξαμύου.'),
          gl(2, 'context', '(23) μετὰ δὲ τὰ πολιτικὰ τῆς φυσικῆς ἐγένετο θεωρίας.'),
        ],
        english: null,
        contextEnglish: [{
          sourceAuthor: 'Diogenes Laertius',
          sourceWork: 'Lives of Eminent Philosophers',
          locus: '1.22-23',
          status: 'translated',
          translationCredit: 'Hicks, 1925',
          text: 'Section 22 text.\n\nSection 23 text.',
          sectionLoci: ['1.22', '1.23'],
        }],
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const flows = container.querySelectorAll('.frag-flow');
    expect(flows.length).toBe(2);
    const first = flows[0] as HTMLElement;
    const second = flows[1] as HTMLElement;
    expect(first.id).toBe('LA1');
    expect(second.id).toBe(''); // the bug surface: no id of its own

    const range = document.createRange();
    range.selectNodeContents(second);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);

    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);

    expect(captured).toBeTruthy();
    expect(captured).toContain('(DK 97 A1)');
  });
});

// item 85 review (2026-07-28): Gorgias B11/B11a (Encomium of Helen, Defence
// of Palamedes) are whole-column-verbatim columns whose English ships a
// per-passage credit (english.column_sources) -- the SAME "(N)" convention
// both languages already carry inline. This suite pins the Reader-layer
// per-section paragraph split for that specific shape: Greek splits via the
// existing DK inline-marker mechanism (no new field -- scanned straight off
// the English chunk's own text, see contextSectionMarkerNumbers), English
// splits via a bare (unlabeled) paragraph break before each marker not at
// the very start of the text, and a declared `heading` (the speech's own
// English title) leads the English chunk as an unmarked line, landing in
// the same leading, unlabeled paragraph slot the Greek div's own title line
// already occupies once the split fires.
describe('Reader.svelte whole-column-verbatim per-section split (Gorgias B11/B11a, item 85)', () => {
  function b11Book(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-B11', column: 'B11', wholeColumnVerbatim: true,
        greek: [
          gl(1, 'context', 'ΓΟΡΓΙΟΥ ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ'),
          gl(2, 'context', '(1) Κόσμος πόλει μὲν εὐανδρία. (2) ὅτι μὲν οὖν φύσει.'),
        ],
        english: {
          text: 'Encomium of Helen (1) Good order, for a city. (2) It is the same task.',
          notes: [], markers: [],
          credit: {
            translator: 'Jurgen R. Gatt',
            source: 'Gorgias/Gorgias, ed. Ewegen and Zoller (Parnassos Press)',
            year: 2022,
          },
        },
      }],
    };
  }

  it('Greek: title line and each DK section become their own .frag-flow paragraph, section markers labelled', async () => {
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: b11Book() } });
    await flush();

    const flows = container.querySelectorAll('.frag-flow');
    // Title paragraph + section 1 + section 2 = 3 flows.
    expect(flows.length).toBe(3);
    expect(flows[0]?.textContent?.trim()).toBe('ΓΟΡΓΙΟΥ ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ');
    const markers = [...container.querySelectorAll('.greek-context-section-marker')]
      .map((m) => m.textContent);
    expect(markers).toEqual(['(1)', '(2)']);
    for (const f of flows) expect(f.textContent).not.toMatch(/\(\d+\)/);
  });

  it('English: heading and each DK section become their own ROW, level with the matching Greek row (item 85 review, John\'s row-alignment ruling)', async () => {
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: b11Book() } });
    await flush();

    // Row-aligned rendering (John, 2026-07-28): the two columns no longer
    // flow independently -- each numbered section (plus the heading) is its
    // own `.frag-row` (Greek cell + English cell), reusing .seg-row's own
    // 2-column grid so both cells of a row stretch to the taller one and
    // start level. Heading row + section (1) + section (2) = 3 rows, same
    // count as the Greek's 3 .frag-flow paragraphs above.
    const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
    expect(rows.length).toBe(3);
    const cellText = (i: number, cls: string) =>
      rows[i]!.querySelector(cls)?.textContent?.replace(/\s+/g, ' ').trim();
    // The number itself stays visible inline (never stripped, unlike the
    // Greek's own relabelled marker) -- no duplicate label is rendered.
    expect(rows[0]!.querySelectorAll('.para-n').length).toBe(0);
    expect(cellText(0, '.english-col')).toBe('Encomium of Helen');
    expect(cellText(1, '.english-col')).toBe('(1) Good order, for a city.');
    expect(cellText(2, '.english-col')).toContain('(2) It is the same task.');
    // Each row's Greek cell holds the paragraph the English row is level
    // with (the marker label itself lives in the Greek's own
    // .greek-context-section-marker, a sibling of the paragraph).
    expect(cellText(0, '.greek-col')).toBe('ΓΟΡΓΙΟΥ ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ');
    expect(cellText(1, '.greek-col')).toContain('Κόσμος πόλει μὲν εὐανδρία.');
    expect(cellText(2, '.greek-col')).toContain('ὅτι μὲν οὖν φύσει.');
    expect(rows[1]!.querySelector('.greek-context-section-marker')?.textContent).toBe('(1)');
    expect(rows[2]!.querySelector('.greek-context-section-marker')?.textContent).toBe('(2)');
  });

  it('regression: a wholeColumnVerbatim segment with no column_sources credit renders one unsplit flow, as before', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B11a', column: 'B11a', wholeColumnVerbatim: true,
        greek: [gl(1, 'context', '(1) ἦν πόλει καὶ γένει. (2) ἐπιφανεστάτη γενομένη.')],
        english: { text: '(1) Was of city and race. (2) Most eminent by birth.', notes: [], markers: [] },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.frag-flow').length).toBe(1);
    expect(container.querySelectorAll('.greek-context-section-marker').length).toBe(0);
    const prose = container.querySelector('#col-B11a .english-col .overlay-prose');
    expect(prose!.querySelectorAll('br.para-br').length).toBe(0);
  });
});

// Fix round (Sol adversarial review on commit 7287b10, finding 1): the
// English-side split used to fire on EVERY "(N)" with no validation at all
// — a stray mid-text citation sharing no relation to the declared section
// run split a paragraph the Greek never did. Both trigger paths
// (wholeColumnVerbatim+credit and sectionParagraphSplit) must reject an
// out-of-sequence "(N)" while still splitting the real ascending run.
describe('Reader.svelte English-side marker split: stray "(N)" rejected (item 85 fix round, finding 1)', () => {
  it('wholeColumnVerbatim+credit: a stray out-of-sequence "(12)" does not split; the real ascending run still does', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B11', column: 'B11', wholeColumnVerbatim: true,
        greek: [
          gl(1, 'context', 'ΓΟΡΓΙΟΥ ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ'),
          gl(2, 'context', '(1) Κόσμος πόλει μὲν εὐανδρία. (2) ὅτι μὲν οὖν φύσει.'),
        ],
        english: {
          text: 'Encomium of Helen (1) Good order, for a city. (12) See note. (2) It is the same task.',
          notes: [], markers: [],
          credit: {
            translator: 'Jurgen R. Gatt',
            source: 'Gorgias/Gorgias, ed. Ewegen and Zoller (Parnassos Press)',
            year: 2022,
          },
        },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    // Same row count as the stray-free baseline above: heading + section (1)
    // + section (2) — the interposed stray "(12)" is rejected outright and
    // opens no row of its own; it stays literal text inside section (1)'s
    // English cell.
    const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
    expect(rows.length).toBe(3);
    const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
    expect(engText(0)).toBe('Encomium of Helen');
    expect(engText(1)).toBe('(1) Good order, for a city. (12) See note.');
    expect(engText(2)).toContain('(2) It is the same task.');
  });

  it('sectionParagraphSplit: a stray out-of-sequence "(12)" does not split; the real ascending run still does', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B7', column: 'B7', sectionParagraphSplit: true,
        greek: [
          gl(1, 'context', 'λέγει δ᾽ οὖν οὕτως ἐπάγων. (1)'),
          gl(2, 'text', 'οὕτως οὖν ἀίδιόν ἐστι. (2) καὶ οὔτ᾽ ἂν ἀπόλοιτο. (3) οὐδὲ ἀλγεῖ.'),
          gl(3, 'context', '.'),
        ],
        english: {
          text: '(1) It is eternal. (12) See cross-reference. (2) And it could not perish. (3) Nor does it feel pain.',
          notes: [], markers: [],
        },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    // Rows before "(2)" and "(3)" only -- the stray "(12)" after "(1)"
    // never opens a row of its own (it stays literal text inside section
    // (1)'s English cell), and "(1)" itself opens the heading-following row
    // (the citation-frame heading row itself carries no English here).
    const rows = [...container.querySelectorAll('#col-B7 .frag-row-split .frag-row')];
    expect(rows.length).toBe(4);
    const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
    expect(engText(0)).toBe('');
    expect(engText(1)).toBe('(1) It is eternal. (12) See cross-reference.');
    expect(engText(2)).toBe('(2) And it could not perish.');
    expect(engText(3)).toBe('(3) Nor does it feel pain.');
  });
});

describe('Reader.svelte English-side marker split: stray value equal to the expected marker is skipped for a boundary occurrence (Sol review, commit b69eae5, finding 1)', () => {
  it('wholeColumnVerbatim+credit: a fused, non-boundary stray "(5)" does not split; the later boundary-adjacent real "(5)" does', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B11', column: 'B11', wholeColumnVerbatim: true,
        greek: [
          gl(1, 'context', 'ΓΟΡΓΙΟΥ ΕΛΕΝΗΣ ΕΓΚΩΜΙΟΝ'),
          gl(2, 'context', '(5) Κόσμος πόλει μὲν εὐανδρία.'),
        ],
        english: {
          text:
            'Heading runs stray(5) noise mid-sentence. Section four ends here. (5) True section five begins.',
          notes: [], markers: [],
          credit: {
            translator: 'Jurgen R. Gatt',
            source: 'Gorgias/Gorgias, ed. Ewegen and Zoller (Parnassos Press)',
            year: 2022,
          },
        },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    // One row-split only, before the real "(5)" — the fused stray occurrence
    // earlier in the text never opens a row of its own.
    const rows = [...container.querySelectorAll('#col-B11 .frag-row-split .frag-row')];
    expect(rows.length).toBe(2);
    const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
    expect(engText(0)).toBe('Heading runs stray(5) noise mid-sentence. Section four ends here.');
    expect(engText(1)).toContain('(5) True section five begins.');
  });

  it('sectionParagraphSplit: a fused, non-boundary stray "(5)" does not split; the later boundary-adjacent real "(5)" does', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B7', column: 'B7', sectionParagraphSplit: true,
        greek: [
          gl(1, 'context', 'λέγει δ᾽ οὖν οὕτως ἐπάγων. (5)'),
          gl(2, 'text', 'οὕτως οὖν ἀίδιόν ἐστι.'),
        ],
        english: {
          text:
            'Heading runs stray(5) noise mid-sentence. Section four ends here. (5) True section five begins.',
          notes: [], markers: [],
        },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    const rows = [...container.querySelectorAll('#col-B7 .frag-row-split .frag-row')];
    expect(rows.length).toBe(2);
    const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
    expect(engText(0)).toBe('Heading runs stray(5) noise mid-sentence. Section four ends here.');
    expect(engText(1)).toContain('(5) True section five begins.');
  });
});

describe('Reader.svelte section-paragraph split (Melissus B7/B8, item 85 addendum)', () => {
  // Melissus-shaped: a real quoting frame (role='context') around the
  // quotation itself (role='text'), the ascending "(N)" markers baked into
  // the quotation, no per-column english.credit override -- unlike Gorgias
  // B11/B11a, this segment carries no wholeColumnVerbatim flag at all.
  function b7Book(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-B7', column: 'B7', sectionParagraphSplit: true,
        greek: [
          gl(1, 'context', 'λέγει δ᾽ οὖν οὕτως ἐπάγων. (1)'),
          gl(2, 'text', 'οὕτως οὖν ἀίδιόν ἐστι. (2) καὶ οὔτ᾽ ἂν ἀπόλοιτο. (3) οὐδὲ ἀλγεῖ.'),
          gl(3, 'context', '.'),
        ],
        english: {
          text: '(1) It is eternal. (2) And it could not perish. (3) Nor does it feel pain.',
          notes: [], markers: [],
        },
      }],
    };
  }

  it('Greek: the citation frame and each ascending marker become their own .frag-flow paragraph', async () => {
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: b7Book() } });
    await flush();

    const flows = container.querySelectorAll('.frag-flow');
    // Citation-frame paragraph + section (1) + section (2) + section (3) = 4.
    expect(flows.length).toBe(4);
    const markers = [...container.querySelectorAll('.greek-context-section-marker')]
      .map((m) => m.textContent);
    expect(markers).toEqual(['(1)', '(2)', '(3)']);
    for (const f of flows) expect(f.textContent).not.toMatch(/\(\d+\)/);
    // The quotation's role='text' run still renders at full text weight
    // (frag-txt) -- this flag never forces every run to frag-txt the way
    // wholeColumnVerbatim does, since the frame really is a quoting source,
    // not the philosopher speaking entire.
    expect(container.querySelectorAll('.frag-txt').length).toBeGreaterThan(0);
    expect(container.querySelectorAll('.frag-ctx').length).toBeGreaterThan(0);
  });

  it('English: aligned rows, no english.credit required (item 85 review, row-alignment ruling)', async () => {
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: b7Book() } });
    await flush();

    // Citation-frame heading row + section (1) + section (2) + section (3)
    // = 4 rows, same count as the Greek's 4 .frag-flow paragraphs above; the
    // heading row's English cell is empty (the citation frame has no English
    // of its own here) -- the shorter side's own gap, never faked.
    const rows = [...container.querySelectorAll('#col-B7 .frag-row-split .frag-row')];
    expect(rows.length).toBe(4);
    const engText = (i: number) => rows[i]!.querySelector('.english-col')?.textContent?.replace(/\s+/g, ' ').trim();
    expect(engText(0)).toBe('');
    expect(engText(1)).toBe('(1) It is eternal.');
    expect(engText(2)).toBe('(2) And it could not perish.');
    expect(engText(3)).toBe('(3) Nor does it feel pain.');
  });

  it('regression: an unflagged Melissus-shaped segment renders one unsplit flow, as before', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-B9', column: 'B9',
        greek: [
          gl(1, 'context', 'λέγει δ᾽ οὖν οὕτως ἐπάγων. (1)'),
          gl(2, 'text', 'οὕτως οὖν ἀίδιόν ἐστι. (2) καὶ οὔτ᾽ ἂν ἀπόλοιτο. (3) οὐδὲ ἀλγεῖ.'),
          gl(3, 'context', '.'),
        ],
        english: {
          text: '(1) It is eternal. (2) And it could not perish. (3) Nor does it feel pain.',
          notes: [], markers: [],
        },
      }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.frag-flow').length).toBe(1);
    expect(container.querySelectorAll('.greek-context-section-marker').length).toBe(0);
    const prose = container.querySelector('#col-B9 .english-col .overlay-prose');
    expect(prose!.querySelectorAll('br.para-br').length).toBe(0);
  });
});

// John's flag (2026-07-24): /lucretius/de-rerum-natura rendered each verse
// line as its own bordered section (one .segment + bold .seg-ref chip per
// line — build/dist/de-rerum-natura/book-01.json has one segment per line,
// only Munro's ~60-line spreads carry English). This suite pins the
// verse-line Reader mode: no per-segment chip, a quiet 5th-line gutter
// number, unchanged per-line anchors, English rendered exactly once per
// carrying segment (never an empty cell), and lacuna/seamNote still
// breaking the flow at their positions — plus a non-verse-line regression
// check (DKPROSE) proving the new branches never fire for another scheme.
describe('Reader.svelte verse-line mode (Lucretius\' DRN — John\'s flag 2026-07-24)', () => {
  function vgl(n: number, text: string, extra: Partial<GreekLine> = {}): GreekLine {
    return { n, text, tokens: [], ...extra };
  }

  function verseBook(): BookData {
    return {
      book: 1,
      segments: [
        { id: 'seg-1.1', column: '1.1', greek: [vgl(1, 'Aeneadum genetrix, hominum divomque voluptas,')],
          english: { text: 'Mother of the Aeneadae.', notes: [], markers: [], title: '1–5' } },
        { id: 'seg-1.2', column: '1.2', greek: [vgl(1, 'alma Venus, caeli subter labentia signa')], english: null },
        { id: 'seg-1.3', column: '1.3', greek: [vgl(1, 'quae mare navigerum, quae terras frugiferentis')], english: null },
        { id: 'seg-1.4', column: '1.4', greek: [vgl(1, 'concelebras, per te quoniam genus omne animantum')], english: null },
        { id: 'seg-1.5', column: '1.5', greek: [vgl(1, 'concipitur visitque exortum lumina solis:')], english: null },
        { id: 'seg-1.6', column: '1.6', greek: [vgl(1, '', { role: 'lacuna' })], english: null },
        { id: 'seg-1.7', column: '1.7', greek: [vgl(1, 'te, dea, te fugiunt venti, te nubila caeli', { seamNote: 'Line 7 transmitted elsewhere in the manuscript.' })], english: null },
        { id: 'seg-1.8', column: '1.8', greek: [vgl(1, 'te tibi suavis daedala tellus')], english: null },
        { id: 'seg-1.9', column: '1.9', greek: [vgl(1, 'submittit flores')], english: null },
        { id: 'seg-1.10', column: '1.10', greek: [vgl(1, 'tibi rident aequora ponti')], english: null },
      ],
    };
  }

  it('renders without per-segment chips, with a quiet 5th-line/post-lacuna gutter number', async () => {
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: verseBook() } });
    await flush();

    // No bold per-line citation chip.
    expect(container.querySelectorAll('.seg-ref').length).toBe(0);

    const gutters = [...container.querySelectorAll('.greek-col .greek-line .line-num')].map((el) => el.textContent);
    // 1.1 (first line) · 1.5 (5th) · 1.7 (line right after the 1.6 lacuna) · 1.10 (10th).
    expect(gutters).toEqual(['1', '', '', '', '5', '', '7', '', '', '10']);
  });

  it('keeps every per-line anchor id exactly as today', async () => {
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: verseBook() } });
    await flush();

    for (const col of ['1.1', '1.2', '1.5', '1.7', '1.10']) {
      expect(container.querySelector(`[id="L${col}-1"]`)).toBeTruthy();
    }
  });

  it('renders English exactly once, only for the segment that carries it — never an empty cell', async () => {
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: verseBook() } });
    await flush();

    const englishCols = container.querySelectorAll('.english-col');
    expect(englishCols.length).toBe(1);
    expect(englishCols[0]?.textContent).toContain('Mother of the Aeneadae.');
    // Its declared Munro range label is kept.
    expect(container.querySelector('.eng-chapter-title')?.textContent).toBe('1–5');
  });

  it('still renders a lacuna gap and a transposition seam note at their positions', async () => {
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: verseBook() } });
    await flush();

    expect(container.querySelectorAll('.lacuna-gap').length).toBe(1);
    const seamNote = container.querySelector('.seam-note');
    expect(seamNote?.textContent).toBe('Line 7 transmitted elsewhere in the manuscript.');
  });

  it('regression: a non-verse-line work (DKPROSE) still gets its .seg-ref chip and an english-col even with null English', async () => {
    const book: BookData = {
      book: 1,
      segments: [{ id: 'seg-B1', column: 'B1', greek: [gl(1, 'text', 'ἀρχή')], english: null }],
    };
    const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.seg-ref').length).toBe(1);
    expect(container.querySelector('.seg-ref')?.textContent?.trim()).toBe('B1');
    expect(container.querySelectorAll('.english-col').length).toBe(1);
  });

  // Fix round, finding 4 (Sol review): a suffixed column ("1.860a") must
  // never carry its own gutter number (it duplicated the real "860" under
  // the old unanchored regex), and a post-lacuna forced number must not
  // repeat the number the previous rendered gutter already showed.
  it('finding 4: verseGutterNum — 860 / 860a / 861 sequence', async () => {
    const book: BookData = {
      book: 1,
      segments: [
        { id: 'seg-1.860', column: '1.860', greek: [vgl(1, 'line eight sixty')], english: null },
        // A suffixed variant reading marked as an editorial gap.
        { id: 'seg-1.860a', column: '1.860a', greek: [vgl(1, '', { role: 'lacuna' })], english: null },
        { id: 'seg-1.861', column: '1.861', greek: [vgl(1, 'line eight sixty-one')], english: null },
      ],
    };
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: book } });
    await flush();

    const gutters = [...container.querySelectorAll('.greek-col .greek-line .line-num')].map((el) => el.textContent);
    expect(gutters).toEqual(['860', '', '861']);
  });

  // Fix round, finding 5 (Sol review): compare mode's .overlay-col branch must
  // get the same non-null-English guard as .english-col — a verse-line
  // segment with no English renders NEITHER English track, never a
  // 3-track grid with one empty compare column.
  it('finding 5: compare mode renders no .overlay-col for a verse-line segment with no English', async () => {
    const book: BookData = {
      book: 1,
      segments: [
        { id: 'seg-1.1', column: '1.1', greek: [vgl(1, 'Aeneadum genetrix, hominum divomque voluptas,')],
          english: { text: 'Mother of the Aeneadae.', notes: [], markers: [] } },
        { id: 'seg-1.2', column: '1.2', greek: [vgl(1, 'alma Venus, caeli subter labentia signa')], english: null },
      ],
    };
    const { container } = render(Reader, { props: { work: 'VERSELINE2', bookNum: 1, bookData: book } });
    await flush();

    const compareRadio = container.querySelectorAll('input[name="trans-mode"]')[1] as HTMLInputElement;
    expect(compareRadio).toBeTruthy();
    await fireEvent.click(compareRadio);
    await fireEvent.change(compareRadio);
    await flush();

    expect(container.querySelectorAll('.overlay-col').length).toBe(1);
    expect(container.querySelectorAll('.english-col').length).toBe(1);
  });

  // Fix round, finding 6 (Sol review): the blanket verse-line `.segment`
  // rule removes ALL separation; a lacuna gap / transposition seam note
  // must carry a structural marker the CSS can hang a separating margin on.
  it('finding 6: lacuna and seam segments carry a data-discontinuity marker', async () => {
    const book: BookData = {
      book: 1,
      segments: [
        { id: 'seg-1.1', column: '1.1', greek: [vgl(1, 'concipitur visitque exortum lumina solis:')], english: null },
        { id: 'seg-1.2', column: '1.2', greek: [vgl(1, '', { role: 'lacuna' })], english: null },
        { id: 'seg-1.3', column: '1.3', greek: [vgl(1, 'te, dea, te fugiunt venti, te nubila caeli', { seamNote: 'Line 3 transmitted elsewhere in the manuscript.' })], english: null },
        { id: 'seg-1.4', column: '1.4', greek: [vgl(1, 'te tibi suavis daedala tellus')], english: null },
      ],
    };
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: book } });
    await flush();

    const segments = [...container.querySelectorAll('.segment')];
    expect(segments[0]?.hasAttribute('data-discontinuity')).toBe(false);
    expect(segments[1]?.getAttribute('data-discontinuity')).toBe('lacuna');
    expect(segments[2]?.getAttribute('data-discontinuity')).toBe('seam');
    expect(segments[3]?.hasAttribute('data-discontinuity')).toBe(false);
  });

  // Re-review finding 3: an untranslated verse-line row renders no
  // english-col at all, but used to keep whatever grid-template-columns the
  // active view/compare mode set (2 tracks in "both", 3 in compare+both) —
  // the sole greek-col sat in the first track with one or two empty tracks
  // beside it. `.verse-untranslated` on the seg-row is the structural signal
  // CSS hangs a single-track override on; assert the class, not child counts.
  it('finding 3 (re-review): a no-English verse-line row carries .verse-untranslated; a row with English does not', async () => {
    const { container } = render(Reader, { props: { work: 'VERSELINE', bookNum: 1, bookData: verseBook() } });
    await flush();

    const rows = [...container.querySelectorAll('.seg-row')];
    // seg-1.1 carries English (verseBook()'s first segment); every other
    // segment in the fixture has none.
    expect(rows[0]?.classList.contains('verse-untranslated')).toBe(false);
    expect(rows.slice(1).every((r) => r.classList.contains('verse-untranslated'))).toBe(true);
  });

  it('finding 3 (re-review): the same signal is present in compare mode, where the untranslated row would otherwise keep a 3-track grid', async () => {
    const book: BookData = {
      book: 1,
      segments: [
        { id: 'seg-1.1', column: '1.1', greek: [vgl(1, 'Aeneadum genetrix, hominum divomque voluptas,')],
          english: { text: 'Mother of the Aeneadae.', notes: [], markers: [] } },
        { id: 'seg-1.2', column: '1.2', greek: [vgl(1, 'alma Venus, caeli subter labentia signa')], english: null },
      ],
    };
    const { container } = render(Reader, { props: { work: 'VERSELINE2', bookNum: 1, bookData: book } });
    await flush();

    const compareRadio = container.querySelectorAll('input[name="trans-mode"]')[1] as HTMLInputElement;
    expect(compareRadio).toBeTruthy();
    await fireEvent.click(compareRadio);
    await fireEvent.change(compareRadio);
    await flush();

    const rows = [...container.querySelectorAll('.seg-row')];
    expect(rows[0]?.classList.contains('verse-untranslated')).toBe(false);
    expect(rows[1]?.classList.contains('verse-untranslated')).toBe(true);
  });
});

// item 23 (REVIEW-CHECKLIST): chapter-level book-section works (Discourses is
// the reference — Marcus Aurelius/Diogenes Laertius/Cicero's book-section
// works share the scheme, so they get the same fix) flow continuously within
// a segment instead of forcing one block per underlying print-line/Schenkl-
// subsection. Scope decision: gated on `cscheme.id === 'book-section'` alone
// (not a further "many single-block segments" heuristic) — the root cause
// (Reader.svelte's old lineate formula forced block-per-line for every
// non-dk scheme regardless of content) is scheme-wide, and flowing a
// single-line segment renders the same text either way, so gating on scheme
// covers every book-section work uniformly without a fragile content sniff.
describe('Reader.svelte book-section chapter-flow (item 23 unification)', () => {
  it('Discourses-shaped: a Schenkl `sections`-split line joins its neighbours into one flowing paragraph with gutter markers, no per-subsection blocks', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, text: 'τῶν ὄντων τὰ μέν ἐστιν', tokens: [{ t: 'τῶν', o: 0, k: 'twn' }] },
          {
            n: 2,
            text: 'δοκιμαστικὴν ἢ ἀποδοκιμαστικήν ἐστιν',
            tokens: [{ t: 'δοκιμαστικὴν', o: 0, k: 'x' }, { t: 'ἀποδοκιμαστικήν', o: 15, k: 'y' }],
            sections: [{ n: 2, o: 0 }, { n: 3, o: 15 }],
          },
          { n: 3, text: 'καὶ τέλος ἔχει', tokens: [{ t: 'καὶ', o: 0, k: 'kai' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 1, bookData: book } });
    await flush();

    // Exactly one segment, one flowing paragraph — no per-subsection blocks.
    expect(container.querySelectorAll('.segment').length).toBe(1);
    const flows = container.querySelectorAll('.frag-flow');
    expect(flows.length).toBe(1);
    expect(container.querySelectorAll('.segment .greek-col > .greek-line').length).toBe(1);

    // Continuous text: the mid-clause split reads as one unbroken sentence.
    const text = flows[0]!.textContent!.replace(/\s+/g, ' ').trim();
    expect(text).toContain('τῶν ὄντων τὰ μέν ἐστιν δοκιμαστικὴν ἢ ἀποδοκιμαστικήν ἐστιν καὶ τέλος ἔχει');

    // Marker "2" (the paragraph's first) has nothing before it to collide
    // with, so it stays a gutter marker. Marker "3" fires only 15
    // characters after it (the whole of the "δοκιμαστικὴν ἢ " run) — well
    // under the collision-mitigation threshold (fix round, finding 3: Sol
    // review flagged two gutter markers landing on the SAME rendered line,
    // real case Discourses 2.9.1's 38-char run) — so it falls back to the
    // plain inline ".para-n" treatment instead of a second gutter marker.
    const gutterMarkers = [...container.querySelectorAll('.greek-para-n-flow')];
    expect(gutterMarkers.map((m) => m.getAttribute('data-n'))).toEqual(['2']);
    const inlineMarkers = [...container.querySelectorAll('.frag-flow .para-n:not(.greek-para-n-flow)')];
    expect(inlineMarkers.map((m) => m.getAttribute('data-n'))).toEqual(['3']);
    // No stray text node leak (John's Sol-review precedent on .para-n): the
    // digits live only in data-n, painted by ::before — true of both the
    // gutter and inline-fallback markers.
    expect([...gutterMarkers, ...inlineMarkers].every((m) => m.textContent === '')).toBe(true);
    // Old block-above-paragraph marker treatment is NOT used here.
    expect(container.querySelectorAll('.greek-para-n').length).toBe(0);

    // Anchors preserved exactly as the pre-flow per-line rendering gave them
    // (copy-citation / scroll-spy rely on these ids existing verbatim).
    expect(container.querySelector('[id="L1.1-1"]')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-2"]')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-2-c3"]')).toBeTruthy();
    // Scroll-spy still finds exactly one observable anchor for this segment
    // (column granularity — book-section's own citation grain).
    const spyEls = [...container.querySelectorAll('.greek-line[id]')];
    expect(spyEls.length).toBe(1);
    expect(spyEls[0]?.id).toBe('L1.1-1');
  });

  it('Marcus/DL-shaped: an ordinary multi-line segment with no `sections` channel flows too, but shows no gutter markers', async () => {
    const book: BookData = {
      book: 4,
      segments: [{
        id: 'seg-4.23',
        column: '4.23',
        greek: [
          { n: 1, text: 'ἡ τῶν ὅλων φύσις', tokens: [{ t: 'ἡ', o: 0, k: 'h' }] },
          { n: 2, text: 'ταῦτα ἐποίησεν', tokens: [{ t: 'ταῦτα', o: 0, k: 'tauta' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 4, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.frag-flow').length).toBe(1);
    expect(container.querySelectorAll('.segment .greek-col > .greek-line').length).toBe(1);
    const text = container.querySelector('.frag-flow')!.textContent!.replace(/\s+/g, ' ').trim();
    expect(text).toContain('ἡ τῶν ὅλων φύσις ταῦτα ἐποίησεν');
    expect(container.querySelectorAll('.greek-para-n-flow').length).toBe(0);
    expect(container.querySelector('[id="L4.23-1"]')).toBeTruthy();
    expect(container.querySelector('[id="L4.23-2"]')).toBeTruthy();
  });

  // Fix round, finding 1 (Sol review): buildProseFlow's run.cls ('frag-txt')
  // carries DK's own role-distinction font-weight:500 — book-section has no
  // such role distinction (never role='context') and must render its
  // source text at the same weight the pre-flow per-line block rendering
  // used (no class at all — normal weight). global.css neutralizes
  // frag-txt's weight, but ONLY inside .bs-flow; pin the DOM structure that
  // makes that scoping correct, since a computed-style read isn't available
  // in this test environment (no stylesheet is loaded).
  it('finding 1: book-section flow text runs sit inside .bs-flow, so frag-txt\'s DK weight is neutralized', async () => {
    const book: BookData = {
      book: 4,
      segments: [{
        id: 'seg-4.23',
        column: '4.23',
        greek: [{ n: 1, text: 'ἡ τῶν ὅλων φύσις', tokens: [{ t: 'ἡ', o: 0, k: 'h' }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 4, bookData: book } });
    await flush();

    const p = container.querySelector('.frag-flow');
    expect(p?.classList.contains('bs-flow')).toBe(true);
    const run = p!.querySelector('.frag-txt');
    expect(run).toBeTruthy();
    // The weight-neutralizing rule is `.greek-line.bs-flow .frag-txt` — the
    // run must actually be a DESCENDANT of the .bs-flow-carrying element.
    expect(run!.closest('.bs-flow')).toBe(p);
  });

  // Fix round, finding 3 (Sol review): the flip side of the collision
  // mitigation above — two markers separated by a genuinely long run (at or
  // above the threshold) must NOT be needlessly demoted to inline; the
  // mitigation only fires on an actual short-run collision risk.
  it('finding 3: two markers separated by a long run both stay gutter markers (no false-positive collision)', async () => {
    const longRun = 'x'.repeat(65) + ' short tail';
    const book: BookData = {
      book: 2,
      segments: [{
        id: 'seg-2.9',
        column: '2.9',
        greek: [{
          n: 1,
          text: longRun,
          tokens: [],
          sections: [{ n: 1, o: 0 }, { n: 2, o: 65 }],
        }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 2, bookData: book } });
    await flush();

    const gutterMarkers = [...container.querySelectorAll('.greek-para-n-flow')];
    expect(gutterMarkers.map((m) => m.getAttribute('data-n'))).toEqual(['1', '2']);
    expect(container.querySelectorAll('.frag-flow .para-n:not(.greek-para-n-flow)').length).toBe(0);
  });

  // Fix round, finding 5 (Sol review): the existing tests only ever
  // selected the FIRST run of a flowed paragraph. Pin the real acceptance
  // criterion — a selection whose anchor AND focus sit inside a LATER run
  // (including a mid-line `-c{paraN}` continuation piece) still produces
  // the correct copy-citation OUTPUT. book-section's own citation scheme
  // drops the line axis entirely (hasUserFacingLines: false), so every run
  // in a segment cites the same bare column regardless of which run
  // resolved it — this is the mechanism's actual, honest behavior (see
  // flowRunId's doc comment in Reader.svelte), not per-run resolution.
  it('finding 5: a selection inside a later run (including a -c{paraN} continuation) still copies the correct column citation', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, text: 'τῶν ὄντων τὰ μέν ἐστιν', tokens: [{ t: 'τῶν', o: 0, k: 'twn' }] },
          {
            n: 2,
            text: 'δοκιμαστικὴν ἢ ἀποδοκιμαστικήν ἐστιν',
            tokens: [{ t: 'δοκιμαστικὴν', o: 0, k: 'x' }, { t: 'ἀποδοκιμαστικήν', o: 15, k: 'y' }],
            sections: [{ n: 2, o: 0 }, { n: 3, o: 15 }],
          },
          { n: 3, text: 'καὶ τέλος ἔχει', tokens: [{ t: 'καὶ', o: 0, k: 'kai' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 1, bookData: book } });
    await flush();

    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');

    function copyFrom(el: Element): string | undefined {
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
      let captured: string | undefined;
      const event = new Event('copy', { bubbles: true, cancelable: true });
      Object.defineProperty(event, 'clipboardData', {
        value: { setData: (_type: string, value: string) => { captured = value; } },
      });
      target!.dispatchEvent(event);
      return captured;
    }

    // Second run (id L1.1-2, not a continuation).
    const run2 = container.querySelector('[id="L1.1-2"]');
    expect(run2).toBeTruthy();
    expect(copyFrom(run2!)).toContain('(Fix. BS 1.1)');

    // Continuation piece past the mid-line section split (id L1.1-2-c3).
    const cont = container.querySelector('[id="L1.1-2-c3"]');
    expect(cont).toBeTruthy();
    expect(copyFrom(cont!)).toContain('(Fix. BS 1.1)');

    // Final line, no id of its own past the first (in-paragraph run).
    const last = container.querySelector('.frag-flow .frag-txt:last-of-type');
    expect(last).toBeTruthy();
    expect(copyFrom(last!)).toContain('(Fix. BS 1.1)');
  });

  it('regression: letter scheme (Seneca-shaped) is untouched — a salutation line still lineates as its own block, no flow', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, text: 'Seneca Lucilio suo salutem', tokens: [{ t: 'Seneca', o: 0, k: 'seneca' }], role: 'salutation' },
          { n: 2, text: 'Ita fac, mi Lucili', tokens: [{ t: 'Ita', o: 0, k: 'ita' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'LETTER', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-flow')).toBeNull();
    expect(container.querySelector('.greek-line.salutation')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-1"]')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-2"]')).toBeTruthy();
  });

  it('flat section scheme (Enchiridion-shaped) joins the gutter presentation — a `sections`-split line shows its section numbers in the .line-num cells, with no block-above marker (John no-gaps ruling, 2026-08-28 evening)', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1',
        column: '1',
        greek: [{
          n: 1,
          text: 'τῶν ὄντων τὰ μέν ἐστιν ἐφ᾽ ἡμῖν',
          tokens: [{ t: 'τῶν', o: 0, k: 'twn' }],
          sections: [{ n: 1, o: 0 }, { n: 2, o: 22 }],
        }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'FLATSEC', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('.frag-flow')).toBeNull();
    expect(container.querySelectorAll('.greek-para-n-flow').length).toBe(0);
    expect(container.querySelectorAll('.greek-para-n').length).toBe(0);
    const gutters = [...container.querySelectorAll('.greek-line .line-num')].map((g) => g.textContent?.trim());
    expect(gutters).toEqual(['1', '2']);
    // Both pieces carry sec-piece (kills the .cont continuation indent —
    // a section start is not a mid-line continuation).
    expect(container.querySelectorAll('.greek-line.sec-piece').length).toBe(2);
  });

  // Fix round, finding 6 (Sol review): the new
  // `.greek-line.frag-flow .line-text { position: relative }` rule was
  // unscoped and hit DK's own prose-flow rendering, and `bookSectionFlow`
  // is gated purely on `cscheme.id === 'book-section'` — every OTHER
  // scheme's render branch (the `{:else}` in Reader.svelte's greek-items
  // block, and the per-line block rendering below it) is untouched code,
  // so its output must be byte-identical to before this diff. Pin that
  // with a FULL rendered-HTML comparison (not a handful of node picks) for
  // one DK fixture, one letter fixture, and one flat-section fixture.
  describe('finding 6: full-HTML byte-identity for every non-book-section branch', () => {
    it('DK prose fixture: .greek-col renders byte-identical to the pre-item-23 branch', async () => {
      const book: BookData = {
        book: 1,
        segments: [{
          id: 'seg-B97',
          column: 'B97',
          greek: [gl(1, 'context', 'ἀρχὴν δὲ τῶν πάντων ὕδωρ ὑπεστήσατο.')],
          english: null,
        }],
      };
      const { container } = render(Reader, { props: { work: 'DKPROSE', bookNum: 1, bookData: book } });
      await flush();
      expect(container.querySelector('.greek-col')!.innerHTML).toBe(
        '<!----> <!----><!----><!----><!----> <p class="greek-line frag-flow" id="LB97"><span class="line-num"></span> <span class="line-text" lang="grc"><!----><!----><span class="frag-ctx"><!----><!---->ἀρχὴν δὲ τῶν πάντων ὕδωρ ὑπεστήσατο.<!----></span></span></p><!---->',
      );
    });

    it('letter-scheme fixture: .greek-col renders byte-identical to the pre-item-23 branch', async () => {
      const book: BookData = {
        book: 1,
        segments: [{
          id: 'seg-1.1',
          column: '1.1',
          greek: [
            { n: 1, text: 'Seneca Lucilio suo salutem', tokens: [{ t: 'Seneca', o: 0, k: 'seneca' }], role: 'salutation' },
            { n: 2, text: 'Ita fac, mi Lucili', tokens: [{ t: 'Ita', o: 0, k: 'ita' }] },
          ],
          english: null,
        }],
      };
      const { container } = render(Reader, { props: { work: 'LETTER', bookNum: 1, bookData: book } });
      await flush();
      // Re-pinned 2026-08-28 evening (gutter-number change): the ONLY
      // delta from the prior pin is one fewer Svelte anchor comment per
      // line (the removed block-above `.greek-para-n` {#if}); the visible
      // DOM — every element, attribute, and text node — is unchanged.
      expect(container.querySelector('.greek-col')!.innerHTML).toBe(
        '<!----> <!----><!----><!----> <div class="greek-line salutation" id="L1.1-1"><span class="line-num"></span> <span class="line-text" lang="la"><!----><!----><span role="button" tabindex="0" aria-haspopup="dialog" class="tok" aria-label="Analyse Seneca">Seneca</span><!----> Lucilio suo salutem<!----></span><!----></div><!----><!----><!----> <div class="greek-line" id="L1.1-2"><span class="line-num"></span> <span class="line-text" lang="la"><!----><!----><span role="button" tabindex="-1" aria-haspopup="dialog" class="tok" aria-label="Analyse Ita">Ita</span><!----> fac, mi Lucili<!----></span><!----></div><!---->',
      );
    });

    it('flat-section fixture: .greek-col renders byte-identical to the pre-item-23 branch', async () => {
      const book: BookData = {
        book: 1,
        segments: [{
          id: 'seg-1',
          column: '1',
          greek: [{
            n: 1,
            text: 'τῶν ὄντων τὰ μέν ἐστιν ἐφ᾽ ἡμῖν',
            tokens: [{ t: 'τῶν', o: 0, k: 'twn' }],
            sections: [{ n: 1, o: 0 }, { n: 2, o: 22 }],
          }],
          english: null,
        }],
      };
      const { container } = render(Reader, { props: { work: 'FLATSEC', bookNum: 1, bookData: book } });
      await flush();
      // Re-pinned 2026-08-28 evening (John's no-gaps ruling): the section
      // numbers moved from block-above `.greek-para-n` spacers into the
      // pieces' own `.line-num` gutter cells, and pieces carry `sec-piece`
      // (neutralizes the .cont continuation indent). This branch is
      // deliberately NOT byte-identical to the pre-ruling pin.
      expect(container.querySelector('.greek-col')!.innerHTML).toBe(
        '<!----> <!----><!----><!----> <div class="greek-line sec-piece" id="L1-1"><span class="line-num">1</span> <span class="line-text" lang="grc"><!----><!----><span role="button" tabindex="0" aria-haspopup="dialog" class="tok" aria-label="Analyse τῶν">τῶν</span><!----> ὄντων τὰ μέν ἐστιν<!----></span><!----></div><!----><!----><!----> <div class="greek-line cont sec-piece" id="L1-1-c2"><span class="line-num">2</span> <span class="line-text" lang="grc"><!----><!----> ἐφ᾽ ἡμῖν<!----></span><!----></div><!---->',
      );
    });
  });
});

// linedGreek's extension to Lives/de-finibus/de-divinatione/de-legibus/
// de-officiis/tusculan-disputations/de-constantia-sapientis/de-providentia
// (2026-08-28) — those 8 works store one Greek line per SEGMENT already (no
// `sections` channel), so the section number is never missing on their
// pages: it's the segment's own `.seg-ref` header ("1.29"), not a gutter
// marker. `linedGreek` changes ONLY their wrapper markup (a per-line
// `.greek-line` div — the ordinary lineate branch — instead of one
// `.frag-flow bs-flow` paragraph); it must add no number of its own. The one
// real defect here: a handful of Lives segments (2.125, 7.160, 7.166, 8.83,
// 8.84, 10.120) carry two or three physical Greek lines that ALL repeat
// `n: 1` (a pipeline quirk, not a citation-scheme feature), which used to
// collide into duplicate `L{column}-1` ids — silently dropping every line
// past the first from the DOM.
describe('Reader.svelte linedGreek book-section: extension-work hardening (2026-08-28)', () => {
  it('single physical line per segment (the common case): one block, id unchanged, no numbering added anywhere', async () => {
    const book: BookData = {
      book: 2,
      segments: [{
        id: 'seg-2.1',
        column: '2.1',
        greek: [{ n: 1, text: 'Ἀναξίμανδρος Πραξιάδου Μιλήσιος.', tokens: [{ t: 'Ἀναξίμανδρος', o: 0, k: 'x' }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 2, bookData: book } });
    await flush();

    expect(container.querySelectorAll('.segment .greek-col > .greek-line').length).toBe(1);
    expect(container.querySelector('[id="L2.1-1"]')).toBeTruthy();
    // No section-number badge anywhere — the number lives in .seg-ref, not
    // the gutter, for these one-line-per-segment works.
    expect(container.querySelectorAll('.para-n').length).toBe(0);
    expect(container.querySelectorAll('.greek-para-n').length).toBe(0);
  });

  it('Lives 2.125-shaped: two physical lines both stamped n:1 get unique, stable, sequential ids — still no numbering', async () => {
    const book: BookData = {
      book: 2,
      segments: [{
        id: 'seg-2.125',
        column: '2.125',
        greek: [
          { n: 1, text: 'Κέβης ὁ Θηβαῖος.', tokens: [{ t: 'Κέβης', o: 0, k: 'x' }] },
          { n: 1, text: 'Μενέδημος Οὗτος τῶν ἀπὸ Φαίδωνος.', tokens: [{ t: 'Μενέδημος', o: 0, k: 'y' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 2, bookData: book } });
    await flush();

    const lines = [...container.querySelectorAll('.segment .greek-col > .greek-line')];
    expect(lines.length).toBe(2);
    const ids = lines.map((l) => l.id);
    expect(ids).toEqual(['L2.125-1', 'L2.125-2']);
    expect(new Set(ids).size).toBe(2);
    // Neither line carries a number — no para-n badge anywhere, for either
    // the first or a renumbered continuation line.
    expect(container.querySelectorAll('.para-n').length).toBe(0);
    // Both lines' text survives the id fix (nothing dropped or merged).
    expect(lines[0]?.textContent).toContain('Κέβης');
    expect(lines[1]?.textContent).toContain('Μενέδημος');
  });

  it('Lives 7.160-shaped: three physical lines sharing n:1 get three distinct ids', async () => {
    const book: BookData = {
      book: 7,
      segments: [{
        id: 'seg-7.160',
        column: '7.160',
        greek: [
          { n: 1, text: 'πρῶτον.', tokens: [{ t: 'πρῶτον', o: 0, k: 'a' }] },
          { n: 1, text: 'δεύτερον.', tokens: [{ t: 'δεύτερον', o: 0, k: 'b' }] },
          { n: 1, text: 'τρίτον.', tokens: [{ t: 'τρίτον', o: 0, k: 'c' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 7, bookData: book } });
    await flush();

    const ids = [...container.querySelectorAll('.segment .greek-col > .greek-line')].map((l) => l.id);
    expect(ids).toEqual(['L7.160-1', 'L7.160-2', 'L7.160-3']);
  });

  it('duplicate followed by a REAL later n ([1, 1, 2]): the bump skips past the real value instead of stealing its anchor', async () => {
    // No current work ships this shape (the six Lives cases are all [1,1] or
    // [1,1,1]) — this pins the adversarial-review finding that a naive
    // next-unused bump would hand the duplicate the real line 2's id,
    // moving the collision instead of removing it.
    const book: BookData = {
      book: 3,
      segments: [{
        id: 'seg-3.1',
        column: '3.1',
        greek: [
          { n: 1, text: 'ἕν.', tokens: [{ t: 'ἕν', o: 0, k: 'a' }] },
          { n: 1, text: 'ἕν πάλιν.', tokens: [{ t: 'ἕν', o: 0, k: 'b' }] },
          { n: 2, text: 'δύο.', tokens: [{ t: 'δύο', o: 0, k: 'c' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 3, bookData: book } });
    await flush();

    const ids = [...container.querySelectorAll('.segment .greek-col > .greek-line')].map((l) => l.id);
    expect(ids).toEqual(['L3.1-1', 'L3.1-3', 'L3.1-2']);
    expect(new Set(ids).size).toBe(3);
  });

  it('Discourses-shaped `sections` channel is untouched: split pieces keep their own paraN/cont ids, unaffected by the dedup path', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, text: 'τῶν ὄντων τὰ μέν ἐστιν', tokens: [{ t: 'τῶν', o: 0, k: 'twn' }] },
          {
            n: 2,
            text: 'δοκιμαστικὴν ἢ ἀποδοκιμαστικήν ἐστιν',
            tokens: [{ t: 'δοκιμαστικὴν', o: 0, k: 'x' }, { t: 'ἀποδοκιμαστικήν', o: 15, k: 'y' }],
            sections: [{ n: 2, o: 0 }, { n: 3, o: 15 }],
          },
          { n: 3, text: 'καὶ τέλος ἔχει', tokens: [{ t: 'καὶ', o: 0, k: 'kai' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    expect(container.querySelector('[id="L1.1-1"]')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-2"]')).toBeTruthy();
    expect(container.querySelector('[id="L1.1-2-c3"]')).toBeTruthy();
    // Gutter presentation (John's no-gaps ruling, 2026-08-28 evening): a
    // split piece's section number renders inside its own .line-num cell —
    // no block-above .greek-para-n spacer exists anywhere any more.
    expect(container.querySelectorAll('.greek-para-n').length).toBe(0);
    const gutters = [...container.querySelectorAll('.greek-line .line-num')].map((g) => g.textContent?.trim());
    expect(gutters).toContain('2');
    expect(gutters).toContain('3');
  });
});

// Defect fix round (adversarial review, 2026-08-28): with append-citation
// enabled, a selection confined SOLELY to a Discourses section-split
// continuation piece (§2+ of a chapter) used to drop its citation entirely —
// the piece's `L1.1-2-c3`-style id resolved to null (greekLineIdToCite), and
// citeForGreekLine's no-id fallback never runs for an element that DOES have
// an id. See greekLineIdToCite's own doc comment for why resolving it to its
// chapter's own {column, line} is safe: book-section's formatCitation drops
// `line` entirely, so the copied citation is byte-identical to the chapter's
// first piece either way.
describe('Reader.svelte copy-citation: section-split continuation piece (defect fix, 2026-08-28)', () => {
  it('a selection confined to a continuation piece still copies a citation (was silently dropped)', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, text: 'τῶν ὄντων τὰ μέν ἐστιν', tokens: [{ t: 'τῶν', o: 0, k: 'twn' }] },
          {
            n: 2,
            text: 'δοκιμαστικὴν ἢ ἀποδοκιμαστικήν ἐστιν',
            tokens: [{ t: 'δοκιμαστικὴν', o: 0, k: 'x' }, { t: 'ἀποδοκιμαστικήν', o: 15, k: 'y' }],
            sections: [{ n: 2, o: 0 }, { n: 3, o: 15 }],
          },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const cont = container.querySelector('.greek-line.cont') as HTMLElement;
    expect(cont).toBeTruthy();
    expect(cont.id).toBe('L1.1-2-c3');

    const range = document.createRange();
    range.selectNodeContents(cont);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);

    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);

    expect(captured).toBeTruthy();
    expect(captured).toContain('(Fix. BSL 1.1)');
  });
});

// Stage 4 (docs/lined-source-plan.md §4): the lined-source Reader-side paint
// for Discourses' print lines -- gutter section marks (Q3) and the hyphen
// re-split (Q2). The 3-line fixture below reproduces the plan's own §1.2/Q2
// worked example verbatim (Schenkl 1.1 §1-§2 opening): line 1's "αὐτὴν αὑτῆς"
// wraps "αὑ-"/"τῆς" INTRA-section; line 2's "...ἀποδοκιμαστικήν" wraps
// "ἀποδο-"/"κιμαστικήν" section-STRADDLING (Q1.3: the joined word stays
// owned by section 1, the line it starts on, even though the gutter mark for
// section 2 lands on the very next line -- Q3.2). No `sections` channel is
// present on any line here (Q4: retired for Discourses in favour of `sec`).
describe('Reader.svelte lined-source (Discourses) print-line paint (Stage 4, docs/lined-source-plan.md)', () => {
  function linedFixture(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          {
            n: 1, sec: 1, joined: true, wrap: 2, wrapO: 43,
            text: 'Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑτῆς',
            tokens: [
              { t: 'Τῶν', o: 0, k: 'k1' },
              { t: 'ἄλλων', o: 4, k: 'k2' },
              { t: 'δυνάμεων', o: 10, k: 'k3' },
              { t: 'οὐδεμίαν', o: 19, k: 'k4' },
              { t: 'εὑρήσετε', o: 28, k: 'k5' },
              { t: 'αὐτὴν', o: 37, k: 'k6' },
              { t: 'αὑτῆς', o: 43, k: 'k7' },
            ],
          },
          // Section 1's OWN second line: absorbs the section-straddling word
          // whole (Q1.3) -- "ἀποδοκιμαστικήν" starts here, so it (and this
          // line's `sec`) stay 1, even though the word's remainder prints on
          // section 2's own first line. `text` already has the PREVIOUS
          // line's carried word ("τῆς") removed from its head, per §3's spec.
          // The trailing "." mirrors the REAL emitted shape (I3's 2026-08-29
          // amendment, docs/lined-source-plan.md §3, verified against
          // build/dist/discourses/book-01.json seg 1:1.1 greek[1]: text len
          // 58, last token ends at 57, tail "."): a section-straddling wrap
          // absorbs the continuation word's SENTENCE-FINAL punctuation too
          // (sections begin after sentences end), but the last token's own
          // `t` is the bare word -- the period is a letterless tail in
          // `text` after the token's [o, o+len(t)) span, not part of `t`.
          {
            n: 2, sec: 1, joined: true, wrap: 5, wrapO: 42,
            text: 'θεωρητικήν, οὐ τοίνυν οὐδὲ δοκιμαστικὴν ἢ ἀποδοκιμαστικήν.',
            tokens: [
              { t: 'θεωρητικήν', o: 0, k: 'k8' },
              { t: 'οὐ', o: 12, k: 'k9' },
              { t: 'τοίνυν', o: 15, k: 'k10' },
              { t: 'οὐδὲ', o: 22, k: 'k11' },
              { t: 'δοκιμαστικὴν', o: 27, k: 'k12' },
              { t: 'ἢ', o: 40, k: 'k13' },
              { t: 'ἀποδοκιμαστικήν', o: 42, k: 'k14' },
            ],
          },
          // Section 2's own first line: its head ("κιμαστικήν") was already
          // absorbed onto the PREVIOUS line above, so `text` starts directly
          // with its own next word -- the "κιμαστικήν." the reader shows
          // here (word remainder PLUS the previous line's tail period) is a
          // PAINTED fragment (item.leadFragment), never in this line's own
          // `text`/`tokens`. No wrap of its own, to keep the fixture to
          // three lines.
          {
            n: 3, sec: 2,
            text: 'ἡ γραμματικὴ μέχρι τίνος κέκτηται τὸ θεωρητικόν',
            tokens: [
              { t: 'ἡ', o: 0, k: 'k15' },
              { t: 'γραμματικὴ', o: 2, k: 'k16' },
              { t: 'μέχρι', o: 13, k: 'k17' },
              { t: 'τίνος', o: 19, k: 'k18' },
              { t: 'κέκτηται', o: 25, k: 'k19' },
              { t: 'τὸ', o: 34, k: 'k20' },
              { t: 'θεωρητικόν', o: 37, k: 'k21' },
            ],
          },
        ],
        english: null,
      }],
    };
  }

  // Acceptance #1: gutter numbers appear on exactly the section-start lines
  // -- including the MID-LINE section start (Q3.2) -- and nowhere else.
  it('gutter: section number on line 1 (segment start) and line 3 (mid-line section start), empty on line 2 (continuation)', async () => {
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: linedFixture() } });
    await flush();

    const line1 = container.querySelector('[id="L1.1-1"]');
    const line2 = container.querySelector('[id="L1.1-2"]');
    const line3 = container.querySelector('[id="L1.1-3"]');
    expect(line1).toBeTruthy();
    expect(line2).toBeTruthy();
    expect(line3).toBeTruthy();

    expect(line1!.querySelector('.line-num')?.textContent?.trim()).toBe('1');
    // Line 2 stays inside section 1 -- no gutter mark, even though it carries
    // `sec` (Q3.1: a mark appears only where a section OPENS).
    expect(line2!.querySelector('.line-num')?.textContent?.trim()).toBe('');
    // Line 3 opens section 2 -- the mark lands here, on the line whose own
    // text begins the new section (Q3.2), not on the line that owns the
    // straddling word (line 2, per Q1.3).
    expect(line3!.querySelector('.line-num')?.textContent?.trim()).toBe('2');
  });

  // Acceptance #2: a wrap split paints "…αὑ-" at line 1's end and "τῆς" at
  // line 2's head, both bound to the SAME token -- clicking either opens the
  // same popup. Observable via Reader's own `class:active={popup?.token ===
  // part.tok}`: clicking one painted piece must mark BOTH pieces active,
  // since a `===` reference check can only pass for both if they share one
  // token object.
  it('wrap split: line-end head and next-line-head tail both paint from the same token (click either → both go active)', async () => {
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: linedFixture() } });
    await flush();

    const line1Toks = [...container.querySelectorAll('[id="L1.1-1"] .tok')];
    const line2Toks = [...container.querySelectorAll('[id="L1.1-2"] .tok')];
    const line3Toks = [...container.querySelectorAll('[id="L1.1-3"] .tok')];

    // Line 1's LAST token is the painted head "αὑ-"; line 2's FIRST token is
    // the painted tail "τῆς" (leadFragment), then its own first real token
    // "θεωρητικήν" — three .tok spans on line 2, not two, since its own text
    // is untouched.
    const tail1 = line1Toks[line1Toks.length - 1] as HTMLElement;
    const head2 = line2Toks[0] as HTMLElement;
    expect(tail1.textContent).toBe('αὑ-');
    expect(head2.textContent).toBe('τῆς');
    expect(line2Toks.length).toBe(8); // 1 carried fragment + 7 of line 2's own tokens

    // Symmetric pair for the SECTION-STRADDLING wrap: line 2's own last
    // token paints "ἀποδο-"; line 3's first token paints "κιμαστικήν" --
    // the tail period line 2's `text` carried after the token (I3's
    // 2026-08-29 amendment) rides along in `carried` as its OWN plain-text
    // render part (splitWrapLine's parts-list generalization), a sibling of
    // the `.tok` span rather than glued into its textContent -- so it never
    // lands on the wrap line itself (see the two assertions just below),
    // and the FULL line text (checked below) still reads "κιμαστικήν.".
    const tail2 = line2Toks[line2Toks.length - 1] as HTMLElement;
    const head3 = line3Toks[0] as HTMLElement;
    expect(tail2.textContent).toBe('ἀποδο-');
    expect(head3.textContent).toBe('κιμαστικήν');

    // (i) The wrap line's own rendered text ends with the print hyphen and
    // never contains the punctuation tail that belongs on the next line --
    // asserted as the EXACT string (leading carried fragment "τῆς", a
    // literal space rejoining it to line 2's own content, per this line
    // being one whitespace-separated print line before the pipeline split
    // it), not just a substring check.
    const line2Text = container.querySelector('[id="L1.1-2"] .line-text')?.textContent ?? '';
    expect(line2Text).toBe('τῆς θεωρητικήν, οὐ τοίνυν οὐδὲ δοκιμαστικὴν ἢ ἀποδο-');
    expect(line2Text.endsWith('-')).toBe(true);
    expect(line2Text).not.toContain('.');
    // (ii) line 3's head fragment renders the word remainder PLUS the tail
    // period, rejoined to its own content by the same literal space.
    const line3Text = container.querySelector('[id="L1.1-3"] .line-text')?.textContent ?? '';
    expect(line3Text).toBe('κιμαστικήν. ἡ γραμματικὴ μέχρι τίνος κέκτηται τὸ θεωρητικόν');

    expect(tail1.classList.contains('active')).toBe(false);
    expect(head2.classList.contains('active')).toBe(false);
    await fireEvent.click(tail1);
    await flush(5);
    expect(tail1.classList.contains('active')).toBe(true);
    expect(head2.classList.contains('active')).toBe(true);
    // The OTHER wrap pair (line2/line3) must be unaffected -- a different
    // token object, so it stays inactive.
    expect(tail2.classList.contains('active')).toBe(false);
    expect(head3.classList.contains('active')).toBe(false);

    // Clicking the TAIL half (head3) opens the same popup as its own head
    // (tail2) would -- symmetric in the other direction too.
    await fireEvent.click(head3);
    await flush(5);
    expect(tail2.classList.contains('active')).toBe(true);
    expect(head3.classList.contains('active')).toBe(true);
    // The first pair is no longer active -- only one popup token at a time.
    expect(tail1.classList.contains('active')).toBe(false);
  });

  // Acceptance #3: a selection spanning the split yields the word once.
  //
  // DECISION (documented per Stage 4's brief, measured against the real
  // rendered DOM rather than assumed): the reader issues no special
  // copy-path normalisation for a wrap split -- `handleCopy` reads
  // `window.getSelection().toString()` verbatim (Reader.svelte's own
  // `handleCopy`, unchanged by this stage). The two painted pieces sit in
  // SEPARATE `.greek-line` blocks, and the reader's existing per-line
  // markup (unrelated to this stage -- the same shape every `linedGreek`
  // line has always had) puts TWO whitespace text nodes between any two
  // consecutive lines' clickable content: one from the `{#each}` block's own
  // item-boundary gap, one from the literal space between a line's
  // `.line-num` and `.line-text` spans. A cross-line selection therefore
  // always carries this two-space seam in this harness, split-word or not --
  // it is a pre-existing multi-line-selection artifact, not something this
  // stage introduces. The captured text is "αὑ-  τῆς" (verified against the
  // actual rendered markup, not inferred): the word appears exactly ONCE,
  // whole, with the Schenkl print hyphen attached (never duplicated, which
  // is the actual failure this criterion guards against -- see Q2's rejected
  // alternative (ii)) -- the extra whitespace is a cosmetic side effect of
  // copying across a block boundary, present for ANY two-line selection in
  // this reader, and is out of this stage's scope to change. A real browser
  // renders a line break here instead of these two spaces (CSS block-layout
  // behaviour happy-dom does not model), which reads at least as sensibly to
  // a human reader as this harness's two spaces do.
  it('copy: a selection spanning the wrap split yields the word once, as "αὑ-  τῆς"', async () => {
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: linedFixture() } });
    await flush();

    const tail1 = container.querySelector('[id="L1.1-1"] .tok:last-of-type') as HTMLElement;
    const head2 = container.querySelector('[id="L1.1-2"] .tok:first-of-type') as HTMLElement;
    expect(tail1.textContent).toBe('αὑ-');
    expect(head2.textContent).toBe('τῆς');

    const range = document.createRange();
    range.setStartBefore(tail1);
    range.setEndAfter(head2);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);

    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);

    expect(captured).toBeTruthy();
    // First line of the clipboard payload is the copied text itself (the
    // citation, if any, is appended after a newline) -- assert it exactly,
    // per this stage's acceptance ("state the EXACT expected string"). The
    // key claim: the word is whole and appears once, never duplicated.
    const copiedText = captured!.split('\n')[0];
    expect(copiedText).toBe('αὑ-  τῆς');
    expect(copiedText.replace(/\s+/g, '')).toBe('αὑ-τῆς');
    expect(copiedText.match(/τῆς/g)?.length).toBe(1);
  });

  // Em-dash glob (the real defect this report fixes, epicurus-letter-to-
  // herodotus §53/§69 -- the only two corpus sites, caught by preflight on
  // the first wave-1 full build): the source glues an em dash straight onto
  // the next word with NO space ("σθαι—πολλὴν"), so whole-whitespace-token
  // absorption (I4) pulls "πολλὴν" onto the wrapped line too -- it is the
  // line's LAST token, not the wrapped one. `wrapO` names the wrapped token
  // ("σχηματίζεσθαι") explicitly, so the Reader locates and repaints IT
  // (not "πολλὴν") and carries EVERYTHING after it -- the word's own
  // remainder, the glued em dash, and "πολλὴν" as its OWN separately
  // clickable token -- to the next line's head.
  it('em-dash glob: line A ends "σχηματίζε-", line B head renders "σθαι—πολλὴν" with "πολλὴν" independently clickable, copy across yields each word once', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-53',
        column: '53',
        greek: [
          {
            n: 1, sec: 53, joined: true, wrap: 9, wrapO: 17,
            text: 'καὶ τῶν ὁμογενῶν σχηματίζεσθαι—πολλὴν',
            tokens: [
              { t: 'καὶ', o: 0, k: 'k1' },
              { t: 'τῶν', o: 4, k: 'k2' },
              { t: 'ὁμογενῶν', o: 8, k: 'k3' },
              { t: 'σχηματίζεσθαι', o: 17, k: 'k4' },
              { t: 'πολλὴν', o: 31, k: 'k5' },
            ],
          },
          {
            n: 2, sec: 53,
            text: 'γὰρ ῥεῖ.',
            tokens: [
              { t: 'γὰρ', o: 0, k: 'k6' },
              { t: 'ῥεῖ', o: 4, k: 'k7' },
            ],
          },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const line1Toks = [...container.querySelectorAll('[id="L53-1"] .tok')];
    const line2Toks = [...container.querySelectorAll('[id="L53-2"] .tok')];

    // Line A's rendered text ends with the repainted wrapped token, hyphen
    // included -- "πολλὴν" never appears on line A at all.
    const line1Text = container.querySelector('[id="L53-1"] .line-text')?.textContent ?? '';
    expect(line1Text.endsWith('σχηματίζε-')).toBe(true);
    expect(line1Text).not.toContain('πολλὴν');
    const wrapTail = line1Toks[line1Toks.length - 1] as HTMLElement;
    expect(wrapTail.textContent).toBe('σχηματίζε-');

    // Line B's head renders the carried block, word remainder immediately
    // followed by the glued em dash then "πολλὴν" -- no space inserted
    // within the carried block (they were contiguous in the source text).
    const line2Text = container.querySelector('[id="L53-2"] .line-text')?.textContent ?? '';
    expect(line2Text).toBe('σθαι—πολλὴν γὰρ ῥεῖ.');

    // "πολλὴν" is its OWN separately clickable token -- not merged into the
    // wrapped word's remainder as plain text.
    const carriedRemainder = line2Toks[0] as HTMLElement;
    const carriedGlued = line2Toks[1] as HTMLElement;
    expect(carriedRemainder.textContent).toBe('σθαι');
    expect(carriedGlued.textContent).toBe('πολλὴν');

    // Clicking either half of the WRAPPED word ("σχηματίζε-" / "σθαι")
    // activates both -- same token object -- but never "πολλὴν", a
    // genuinely different token.
    expect(wrapTail.classList.contains('active')).toBe(false);
    expect(carriedRemainder.classList.contains('active')).toBe(false);
    expect(carriedGlued.classList.contains('active')).toBe(false);
    await fireEvent.click(wrapTail);
    await flush(5);
    expect(wrapTail.classList.contains('active')).toBe(true);
    expect(carriedRemainder.classList.contains('active')).toBe(true);
    expect(carriedGlued.classList.contains('active')).toBe(false);

    // "πολλὴν" is independently clickable, opening its OWN popup (a
    // different token's identity than the wrapped word's).
    await fireEvent.click(carriedGlued);
    await flush(5);
    expect(carriedGlued.classList.contains('active')).toBe(true);
    expect(wrapTail.classList.contains('active')).toBe(false);
    expect(carriedRemainder.classList.contains('active')).toBe(false);

    // Copy across the split: each word appears exactly once, whole -- the
    // wrapped word reconstitutes as "σχηματίζε-  σθαι" (this harness's own
    // two-space cross-line seam, per the acceptance above) and "πολλὴν"
    // is never duplicated.
    const range = document.createRange();
    range.setStartBefore(wrapTail);
    range.setEndAfter(carriedGlued);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);
    const copiedText = captured!.split('\n')[0];
    expect(copiedText.replace(/\s+/g, '')).toBe('σχηματίζε-σθαι—πολλὴν');
    expect(copiedText.match(/πολλὴν/g)?.length).toBe(1);
    expect(copiedText.match(/σχηματίζε/g)?.length).toBe(1);
  });

  // Pipeline-lane addendum (real-corpus fact, landed 2026-08-29): 18 real
  // Discourses lines are hyphen continuations absorbed WHOLE -- the entire
  // physical print line is a single word that got rejoined onto the
  // PREVIOUS line. The pipeline still emits such a line as its own entry
  // (its `n` keeps the ordinary positional contract) with `text: ""` and no
  // tokens, plus its own `sec`. This line's rendered content is therefore
  // ENTIRELY the carried fragment from the previous line's `wrap` -- nothing
  // of its own. No Reader-side code change was needed for this: `lineParts`
  // already builds `base` from `lineRenderParts('', [])` (empty array, see
  // speakers.test.ts's own no-op-adjacent coverage) and prepends
  // `leadFragment` unconditionally, so an empty-text line's rendered parts
  // collapse to exactly the one carried fragment. `pendingWrapTail` is
  // correctly cleared after this line too (it carries no `wrap` of its own),
  // so the line AFTER it does not also inherit a fragment.
  //
  // Line 1's own text also carries a punctuation TAIL after its wrap token
  // (I3's 2026-08-29 amendment, docs/lined-source-plan.md §3) -- the
  // absorbed fragment's carried remainder ("ορεῖ") the empty line 2 renders
  // must include that tail too ("ορεῖ."), never dropping it.
  it('fully-absorbed line (empty text, whole content is the carried fragment): renders exactly the fragment (with its tail), keeps its own id, next line unaffected', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          {
            n: 1, sec: 1, joined: true, wrap: 5, wrapO: 20,
            text: 'τῶν ἄλλων πραγμάτων κατηγορεῖ.',
            tokens: [
              { t: 'τῶν', o: 0, k: 'k1' },
              { t: 'ἄλλων', o: 4, k: 'k2' },
              { t: 'πραγμάτων', o: 10, k: 'k3' },
              { t: 'κατηγορεῖ', o: 20, k: 'k4' },
            ],
          },
          // The whole line IS the tail of line 1's last token -- no text,
          // no tokens of its own.
          { n: 2, sec: 1, text: '', tokens: [] },
          {
            n: 3, sec: 2,
            text: 'δεύτερος λόγος οὗτος',
            tokens: [
              { t: 'δεύτερος', o: 0, k: 'k5' },
              { t: 'λόγος', o: 9, k: 'k6' },
              { t: 'οὗτος', o: 15, k: 'k7' },
            ],
          },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const line1 = container.querySelector('[id="L1.1-1"]') as HTMLElement;
    const line2 = container.querySelector('[id="L1.1-2"]') as HTMLElement;
    const line3 = container.querySelector('[id="L1.1-3"]') as HTMLElement;
    expect(line1).toBeTruthy();
    // The empty-text line keeps its ordinary id -- not folded into line 1,
    // not given a `-c{k}` continuation suffix (that's a DIFFERENT mechanism,
    // Enchiridion's `cont`/`paraN`, which this line never sets).
    expect(line2).toBeTruthy();
    expect(line2.id).toBe('L1.1-2');
    expect(line3).toBeTruthy();

    // Line 2 renders EXACTLY one clickable piece: the carried word
    // remainder ("ορεῖ", the .tok's own text) -- line 1's tail period rides
    // along as its own plain-text carried part (splitWrapLine's parts-list
    // generalization), a sibling of the .tok rather than glued into its
    // textContent, so the FULL line text (checked below) still reads
    // "ορεῖ." with nothing dropped.
    const line2Toks = [...line2.querySelectorAll('.tok')];
    expect(line2Toks.length).toBe(1);
    expect(line2Toks[0].textContent).toBe('ορεῖ');
    // The period is present in the line's full text, not lost.
    expect(line2.querySelector('.line-text')?.textContent).toBe('ορεῖ.');

    // Line 1's own painted tail and line 2's fragment are the SAME token
    // (the split is still clickable as one logical token, hyphen included).
    const tail1 = [...line1.querySelectorAll('.tok')].at(-1) as HTMLElement;
    expect(tail1.textContent).toBe('κατηγ-');
    expect(tail1.classList.contains('active')).toBe(false);
    await fireEvent.click(tail1);
    await flush(5);
    expect(tail1.classList.contains('active')).toBe(true);
    expect(line2Toks[0].classList.contains('active')).toBe(true);

    // Gutter: line 2 stays inside section 1 (no mark); line 3 opens section
    // 2 (mark lands there) -- the empty line's `sec` participates in the
    // same section-start bookkeeping as any other line.
    expect(line2.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line3.querySelector('.line-num')?.textContent?.trim()).toBe('2');

    // Line 3 renders normally -- it does NOT inherit a leadFragment (line 2
    // carried no `wrap` of its own, so `pendingWrapTail` was cleared).
    const line3Toks = [...line3.querySelectorAll('.tok')].map((t) => t.textContent);
    expect(line3Toks).toEqual(['δεύτερος', 'λόγος', 'οὗτος']);
  });

  // Regression (blast-radius contract, §6.4): the eight other `linedGreek`
  // works (Lives et al.) carry no `sec`/`wrap` at all -- their lines must
  // render byte-identical to before this stage. Folds into the existing
  // "extension-work hardening" suite's own single-physical-line case above
  // by re-asserting it here with an explicit no-`sec` fixture and checking
  // the gutter cell is empty (unchanged: these works show their section
  // number in `.seg-ref`, never the gutter) and no leadFragment/paintWrapHead
  // artifact (no extra `.tok` spans, no bare hyphen) appears anywhere.
  it('regression: a linedGreek line with no `sec`/`wrap` (Lives-shaped) renders exactly as before -- no gutter number, no painted fragments', async () => {
    const book: BookData = {
      book: 2,
      segments: [{
        id: 'seg-2.1',
        column: '2.1',
        greek: [{ n: 1, text: 'Ἀναξίμανδρος Πραξιάδου Μιλήσιος.', tokens: [{ t: 'Ἀναξίμανδρος', o: 0, k: 'x' }] }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 2, bookData: book } });
    await flush();

    const line = container.querySelector('[id="L2.1-1"]') as HTMLElement;
    expect(line).toBeTruthy();
    expect(line.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect([...line.querySelectorAll('.tok')].map((t) => t.textContent)).toEqual(['Ἀναξίμανδρος']);
    expect(line.textContent).not.toContain('-');
  });

  // Lined-source first-line inset: `line.indent` drives a capped formula on
  // `.line-text` -- a visual inset
  // on that line's own rendered content, gutter cell (`.line-num`) untouched.
  // Fragment interaction (Stage brief's explicit question, resolved here):
  // when an indented line is ALSO the RECEIVER of the previous line's
  // carried wrap fragment (`item.leadFragment`), the fragment is painted
  // inside the SAME single `.line-text` span as the rest of that line's own
  // content -- there is no separate un-indented wrapper around it -- so the
  // inset necessarily shifts the whole painted line, fragment included, per
  // the reasoning: the fragment is part of THIS line's own text flow, not a
  // trailing addendum to the PREVIOUS line's.
  it('indent style stays on the line text, leaves the gutter untouched, and covers a carried wrap fragment', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          // Paragraph-opening line (section 1's own first line): indent 1,
          // plain -- no wrap of its own.
          {
            n: 1, sec: 1, indent: 1,
            text: 'ἄλφα βῆτα.',
            tokens: [{ t: 'ἄλφα', o: 0, k: 'k1' }, { t: 'βῆτα', o: 5, k: 'k2' }],
          },
          // A wrap line (still section 1): its last token splits across the
          // print-line boundary, same shape as the "fully-absorbed" fixture
          // above (κατηγορεῖ / ορεῖ.). No indent of its own.
          {
            n: 2, sec: 1, joined: true, wrap: 5, wrapO: 20,
            text: 'τῶν ἄλλων πραγμάτων κατηγορεῖ.',
            tokens: [
              { t: 'τῶν', o: 0, k: 'k3' },
              { t: 'ἄλλων', o: 4, k: 'k4' },
              { t: 'πραγμάτων', o: 10, k: 'k5' },
              { t: 'κατηγορεῖ', o: 20, k: 'k6' },
            ],
          },
          // The fully-absorbed continuation of line 2's wrap -- its ENTIRE
          // rendered content is the carried fragment. ALSO carries `indent:
          // 3` (deepest level, quoted/inset matter) -- the case the brief
          // asks to be covered explicitly.
          { n: 3, sec: 1, indent: 3, text: '', tokens: [] },
          // An ordinary, unindented line -- must carry none of the three
          // classes.
          {
            n: 4, sec: 2,
            text: 'δεύτερος λόγος.',
            tokens: [{ t: 'δεύτερος', o: 0, k: 'k7' }, { t: 'λόγος', o: 9, k: 'k8' }],
          },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const line1 = container.querySelector('[id="L1.1-1"]') as HTMLElement;
    const line2 = container.querySelector('[id="L1.1-2"]') as HTMLElement;
    const line3 = container.querySelector('[id="L1.1-3"]') as HTMLElement;
    const line4 = container.querySelector('[id="L1.1-4"]') as HTMLElement;
    expect(line1).toBeTruthy();
    expect(line2).toBeTruthy();
    expect(line3).toBeTruthy();
    expect(line4).toBeTruthy();

    expect((line1.querySelector('.line-text') as HTMLElement).style.textIndent)
      .toBe('1.25em');
    expect((line2.querySelector('.line-text') as HTMLElement).style.textIndent).toBe('');
    // Line 3 is a verse run of ONE (lines 2 and 4 carry no indent), so it
    // sits at its run's own base -- 2.5em -- not at the 3.75em its raw
    // level 3 used to map to. See rebaseVerseRuns: the edition's indent(N)
    // is page geometry, and a run is rebased to its own shallowest line.
    // It rides --v-inset (the hanging-indent rule's input), not text-indent.
    expect((line3.querySelector('.line-text') as HTMLElement)
      .style.getPropertyValue('--v-inset')).toBe('2.5em');
    expect((line3.querySelector('.line-text') as HTMLElement).style.textIndent).toBe('');
    expect((line4.querySelector('.line-text') as HTMLElement).style.textIndent).toBe('');

    // The gutter cell is unaffected by indent: line 1 (section-start) still
    // shows '1', line 4 (opens section 2) still shows '2', lines 2-3 (still
    // inside section 1) stay empty -- the exact same values as if `indent`
    // were absent altogether.
    expect(line1.querySelector('.line-num')?.textContent?.trim()).toBe('1');
    expect(line2.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line3.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line4.querySelector('.line-num')?.textContent?.trim()).toBe('2');

    // Fragment-plus-indent interaction: line 3's WHOLE content is the
    // carried fragment from line 2's wrap, and it renders inside the same
    // single `.line-text` span that carries the indent style itself, never
    // leaving the fragment in an un-indented sibling.
    const line3Text = line3.querySelector('.line-text') as HTMLElement;
    expect(line3Text).toBeTruthy();
    expect(line3Text.textContent).toBe('ορεῖ.');
    expect(line3Text.parentElement).toBe(line3);
    expect(line3.querySelectorAll('.line-text').length).toBe(1);
    const line3Toks = [...line3Text.querySelectorAll('.tok')];
    expect(line3Toks.length).toBe(1);
    // The carried tail period is its own plain-text part (splitWrapLine's
    // parts-list generalization), a sibling of the .tok -- not glued into
    // its own textContent (the FULL line text above already confirms it's
    // present, indented and all).
    expect(line3Toks[0].textContent).toBe('ορεῖ');

    // The fragment is still bound to the SAME token as line 2's own painted
    // head -- indent changes only presentation, never the click/popup
    // wiring.
    const tail2 = [...line2.querySelectorAll('.tok')].at(-1) as HTMLElement;
    expect(tail2.textContent).toBe('κατηγ-');
    await fireEvent.click(tail2);
    await flush(5);
    expect(tail2.classList.contains('active')).toBe(true);
    expect(line3Toks[0].classList.contains('active')).toBe(true);
  });

  it('rebases a verse run to its own base, so equal shapes at different print depths render alike', async () => {
    // The defect this replaces (John, 2026-08-31, dashboard item 96a): the
    // old rule mapped the edition's literal indent(N) to the inset, capped
    // at 4 steps. Lives' two elegiac epigrams are the same shape recorded at
    // different print depths -- 1.4 at (4,5), 1.5 at (2,3) -- because the
    // printer set the shorter couplet further right. Under the old rule they
    // rendered THREE different ways: 1.4 flattened to 5em/5em (the cap ate
    // its real hexameter/pentameter step) while 1.5 stepped 2.5em/3.75em.
    // Rebasing per run fixes both halves at once.
    const couplets: Array<[number, number]> = [[4, 5], [2, 3]];
    const levels = couplets.flat();
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: levels.map((indent, index) => ({
          n: index + 1,
          indent,
          text: `line ${indent}`,
          tokens: [],
        })),
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    // A verse line's inset now rides the `--v-inset` custom property, which
    // the hanging-indent rule turns into padding + a negative first-line
    // text-indent (a wrapped verse line must hang, not return to the margin).
    const insets = levels.map((_, index) =>
      (container.querySelector(`[id="L1.1-${index + 1}"] .line-text`) as HTMLElement)
        .style.getPropertyValue('--v-inset'),
    );
    // All four lines are ONE consecutive run (base 2), so every line deeper
    // than the base steps in exactly once -- 4, 5 and 3 all being > 2.
    expect(insets).toEqual(['3.75em', '3.75em', '2.5em', '3.75em']);
  });

  it('rebases each verse run independently, so prose between two epigrams resets the base', async () => {
    // The real Lives shape: prose, epigram, prose, epigram. Each epigram is
    // its own run, so both render identically despite 1.4's print depths
    // being two steps deeper than 1.5's.
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [
          { n: 1, indent: 1, text: 'prose opening', tokens: [] },
          { n: 2, indent: 4, text: 'hexameter A', tokens: [] },
          { n: 3, indent: 5, text: 'pentameter A', tokens: [] },
          { n: 4, text: 'prose between', tokens: [] },
          { n: 5, indent: 2, text: 'hexameter B', tokens: [] },
          { n: 6, indent: 3, text: 'pentameter B', tokens: [] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();
    const at = (n: number) =>
      (container.querySelector(`[id="L1.1-${n}"] .line-text`) as HTMLElement).style.textIndent;
    const inset = (n: number) =>
      (container.querySelector(`[id="L1.1-${n}"] .line-text`) as HTMLElement)
        .style.getPropertyValue('--v-inset');

    // Level 1 is an ordinary paragraph opening, not a verse run: unchanged.
    expect(at(1)).toBe('1.25em');
    expect(at(4)).toBe('');
    // The two couplets render IDENTICALLY -- the point of the ruling.
    expect([inset(2), inset(3)]).toEqual(['2.5em', '3.75em']);
    expect([inset(5), inset(6)]).toEqual(['2.5em', '3.75em']);
    // A verse line carries no inline text-indent: the hanging-indent rule
    // owns both axes, off --v-inset.
    expect(at(2)).toBe('');

    // Each run is marked at its ends so the block can breathe.
    const cls = (n: number) => (container.querySelector(`[id="L1.1-${n}"]`) as HTMLElement).className;
    expect(cls(2)).toContain('verse-run-first');
    expect(cls(3)).toContain('verse-run-last');
    expect(cls(5)).toContain('verse-run-first');
    expect(cls(6)).toContain('verse-run-last');
    expect(cls(1)).not.toContain('verse-run');
  });

  it('a segment-final joined-only line paints full text with no hyphen or carried fragment', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [{
          n: 1,
          joined: true,
          text: 'columnis finis',
          tokens: [
            { t: 'columnis', o: 0, k: 'columnis' },
            { t: 'finis', o: 9, k: 'finis' },
          ],
        }],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const lineText = container.querySelector('[id="L1.1-1"] .line-text') as HTMLElement;
    expect(lineText.textContent).toBe('columnis finis');
    expect([...lineText.querySelectorAll('.tok')].map((token) => token.textContent))
      .toEqual(['columnis', 'finis']);
    expect(lineText.textContent).not.toContain('-');
  });
});

// Print-lineation rollout wave 1 (docs/lined-rollout-plan.md Stage 3): the
// SAME lined-source paint (gutter section marks, hyphen re-split) extended
// to the `section` scheme (Enchiridion/Epicurus-shaped), gated on the new
// `linedSource` flag instead of `linedGreek` (which stays book-section-only).
// FLATSECLINED carries `linedSource: true` with no `linedGreek` at all --
// `section` already lineates unconditionally (Ruling 2.3), so this fixture
// isolates the painting-gate change from the lineate decision.
describe('Reader.svelte lined-source (section scheme) print-line paint (docs/lined-rollout-plan.md Stage 3)', () => {
  // Ruling 6.2/6.3: a multi-section column (Enchiridion-shaped) shows the
  // gutter mark on exactly the line that OPENS each section.
  it('Enchiridion-shaped multi-section column: gutter numbers on exactly the section-start lines', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-5',
        column: '5',
        greek: [
          { n: 1, sec: 1, text: 'ἄλφα βῆτα.', tokens: [{ t: 'ἄλφα', o: 0, k: 'k1' }, { t: 'βῆτα', o: 5, k: 'k2' }] },
          { n: 2, sec: 1, text: 'γάμμα δέλτα.', tokens: [{ t: 'γάμμα', o: 0, k: 'k3' }, { t: 'δέλτα', o: 6, k: 'k4' }] },
          { n: 3, sec: 2, text: 'ἔψιλον ζῆτα.', tokens: [{ t: 'ἔψιλον', o: 0, k: 'k5' }, { t: 'ζῆτα', o: 7, k: 'k6' }] },
          { n: 4, sec: 2, text: 'ἦτα θῆτα.', tokens: [{ t: 'ἦτα', o: 0, k: 'k7' }, { t: 'θῆτα', o: 4, k: 'k8' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const line1 = container.querySelector('[id="L5-1"]');
    const line2 = container.querySelector('[id="L5-2"]');
    const line3 = container.querySelector('[id="L5-3"]');
    const line4 = container.querySelector('[id="L5-4"]');
    expect(line1).toBeTruthy();
    expect(line2).toBeTruthy();
    expect(line3).toBeTruthy();
    expect(line4).toBeTruthy();
    expect(line1!.querySelector('.line-num')?.textContent?.trim()).toBe('1');
    expect(line2!.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line3!.querySelector('.line-num')?.textContent?.trim()).toBe('2');
    expect(line4!.querySelector('.line-num')?.textContent?.trim()).toBe('');
  });

  // Ruling 6.3: a segment whose lines carry only ONE distinct `sec` value
  // (37 of Enchiridion's 53 real chapters) shows NO gutter mark at all --
  // not even on line 1, which would otherwise read as "opening" section 1.
  it('Enchiridion-shaped single-section column: no gutter number at all', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-12',
        column: '12',
        greek: [
          { n: 1, sec: 1, text: 'ἄλφα.', tokens: [{ t: 'ἄλφα', o: 0, k: 'k1' }] },
          { n: 2, sec: 1, text: 'βῆτα.', tokens: [{ t: 'βῆτα', o: 0, k: 'k2' }] },
        ],
        english: null,
      }],
    };
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: book } });
    await flush();

    const line1 = container.querySelector('[id="L12-1"]');
    const line2 = container.querySelector('[id="L12-2"]');
    expect(line1).toBeTruthy();
    expect(line2).toBeTruthy();
    expect(line1!.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line2!.querySelector('.line-num')?.textContent?.trim()).toBe('');
  });

  // Ruling 1c: the five Epicurus works never carry `sec` at all (their
  // column div IS the leaf -- no `lined_section_div`). Fixture below has no
  // `sec` field on either line, mirroring the real shape.
  function epicurusFixture(): BookData {
    return {
      book: 1,
      segments: [{
        id: 'seg-84',
        column: '84',
        greek: [
          {
            n: 1, joined: true, wrap: 3, wrapO: 12,
            text: 'πρῶτον περὶ ἀγαθόν',
            tokens: [
              { t: 'πρῶτον', o: 0, k: 'e1' },
              { t: 'περὶ', o: 7, k: 'e2' },
              { t: 'ἀγαθόν', o: 12, k: 'e3' },
            ],
          },
          {
            n: 2,
            text: 'κλέος αἰώνιον μένει',
            tokens: [
              { t: 'κλέος', o: 0, k: 'e4' },
              { t: 'αἰώνιον', o: 6, k: 'e5' },
              { t: 'μένει', o: 14, k: 'e6' },
            ],
          },
        ],
        english: null,
      }],
    };
  }

  it('Epicurus-shaped column (no `sec` on any line): no gutter numbers at all', async () => {
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: epicurusFixture() } });
    await flush();

    const line1 = container.querySelector('[id="L84-1"]');
    const line2 = container.querySelector('[id="L84-2"]');
    expect(line1).toBeTruthy();
    expect(line2).toBeTruthy();
    expect(line1!.querySelector('.line-num')?.textContent?.trim()).toBe('');
    expect(line2!.querySelector('.line-num')?.textContent?.trim()).toBe('');
  });

  it('Epicurus-shaped column: clicking either half of a split word yields the same token (both go active)', async () => {
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: epicurusFixture() } });
    await flush();

    const line1Toks = [...container.querySelectorAll('[id="L84-1"] .tok')];
    const line2Toks = [...container.querySelectorAll('[id="L84-2"] .tok')];
    const tail1 = line1Toks[line1Toks.length - 1] as HTMLElement;
    const head2 = line2Toks[0] as HTMLElement;
    expect(tail1.textContent).toBe('ἀγα-');
    expect(head2.textContent).toBe('θόν');

    expect(tail1.classList.contains('active')).toBe(false);
    expect(head2.classList.contains('active')).toBe(false);
    await fireEvent.click(tail1);
    await flush(5);
    expect(tail1.classList.contains('active')).toBe(true);
    expect(head2.classList.contains('active')).toBe(true);

    await fireEvent.click(head2);
    await flush(5);
    expect(tail1.classList.contains('active')).toBe(true);
    expect(head2.classList.contains('active')).toBe(true);
  });

  it('Epicurus-shaped column: copy across the split yields the whole word once, as "ἀγα-  θόν"', async () => {
    const { container } = render(Reader, { props: { work: 'FLATSECLINED', bookNum: 1, bookData: epicurusFixture() } });
    await flush();

    const tail1 = container.querySelector('[id="L84-1"] .tok:last-of-type') as HTMLElement;
    const head2 = container.querySelector('[id="L84-2"] .tok:first-of-type') as HTMLElement;
    expect(tail1.textContent).toBe('ἀγα-');
    expect(head2.textContent).toBe('θόν');

    const range = document.createRange();
    range.setStartBefore(tail1);
    range.setEndAfter(head2);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);

    const target = container.querySelector('.reader-body');
    if (!target) throw new Error('no .reader-body rendered');
    let captured: string | undefined;
    const event = new Event('copy', { bubbles: true, cancelable: true });
    Object.defineProperty(event, 'clipboardData', {
      value: { setData: (_type: string, value: string) => { captured = value; } },
    });
    target.dispatchEvent(event);

    expect(captured).toBeTruthy();
    const copiedText = captured!.split('\n')[0];
    // Same two-space cross-block seam as the Discourses copy test above
    // (pre-existing multi-line-selection artifact, not introduced here) --
    // the word itself is whole and appears exactly once.
    expect(copiedText).toBe('ἀγα-  θόν');
    expect(copiedText.replace(/\s+/g, '')).toBe('ἀγα-θόν');
    expect(copiedText.match(/θόν/g)?.length).toBe(1);
  });
});

// John's ruling (2026-08-28, live Epictetus example at /epictetus/discourses/
// book/1, section 1.1): a chunk's EnglishChunk.title ("Of the things which
// are under our control...") was rendering TWICE — once in the segment's own
// `.seg-ref` header (`.seg-ref-title`, always shown for a book-section/busse
// scheme when `seg.english?.title` is set — see the `!busse && !verseLine`
// guard on `.seg-ref` itself) and again as a `.eng-chapter-title` inside the
// English column. "keep the header, lose it in the english." The English-
// column render sites now additionally require `(busse || verseLine)` —
// exactly the case where NO `.seg-ref` header exists to have shown it
// already (verse-line works, e.g. Lucretius' DRN — see the 'renders English
// exactly once...' test above, which pins that the title is KEPT there).
// Discourses and Cicero's De Finibus (both book-section, chapter-concordance
// or Oldfather-sidecar sourced) are the two live works this fix touches.
describe('Reader.svelte English-column chapter title de-duplication (John\'s ruling 2026-08-28)', () => {
  it('book-section scheme (Discourses/De Finibus-shaped): the header shows the title, the English column does not repeat it', async () => {
    const book: BookData = {
      book: 1,
      segments: [{
        id: 'seg-1.1',
        column: '1.1',
        greek: [{ n: 1, text: 'τῶν ὄντων τὰ μέν ἐστιν ἐφ᾽ ἡμῖν', tokens: [{ t: 'τῶν', o: 0, k: 'twn' }] }],
        english: { text: 'Of the things which are under our control.', notes: [], markers: [], title: 'Of the things which are under our control' },
      }],
    };
    const { container } = render(Reader, { props: { work: 'BOOKSEC', bookNum: 1, bookData: book } });
    await flush();

    // The header still carries the title, once.
    const headerTitle = container.querySelector('.seg-ref-title');
    expect(headerTitle?.textContent).toBe('· Of the things which are under our control');
    // The English column no longer repeats it.
    expect(container.querySelector('.eng-chapter-title')).toBeNull();
    // The English translation text itself is unaffected.
    expect(container.querySelector('.english-col')?.textContent).toContain('Of the things which are under our control.');
  });
});
