import { describe, expect, it } from 'vitest';
import { lineRenderParts, buildFlowRows, buildEnglishTurnBlocks, labelSuppression, splitGreekSections, splitWrapLine, type SpeakerEvent, type FlowRow } from '../lib/speakers';
import type { Token, GreekLine, Segment, TurnFlow, EnglishTurn } from '../lib/data';

// A token as the pipeline emits it: surface form, char offset, Beta Code key.
// The key's exact value doesn't matter to these tests, only that it's
// present (lineRenderParts renders `kind: 'token'` for a keyed token, and
// `kind: 'text'` — non-clickable — for a non-lexical token with no `k`;
// see the dedicated "non-lexical tokens" describe block below).
const tok = (t: string, o: number): Token => ({ t, o, k: 'x' });

// Compact projections so assertions read clearly.
const kinds = (parts: ReturnType<typeof lineRenderParts>) => parts.map((p) => p.kind);
const texts = (parts: ReturnType<typeof lineRenderParts>) =>
  parts.map((p) => (p.kind === 'speaker' ? `«${p.label}»` : p.text));

describe('lineRenderParts — token/gap split (no speakers)', () => {
  it('splits a line into clickable tokens and verbatim gaps', () => {
    const text = 'ὦ φίλε.';
    const tokens = [tok('ὦ', 0), tok('φίλε', 2)];
    const parts = lineRenderParts(text, tokens);
    expect(kinds(parts)).toEqual(['token', 'text', 'token', 'text']);
    expect(texts(parts)).toEqual(['ὦ', ' ', 'φίλε', '.']);
    // The token parts carry the original Token object for the popup lookup.
    expect(parts[0]).toMatchObject({ kind: 'token', text: 'ὦ', tok: tokens[0] });
  });

  it('is byte-identical whether events is omitted or an empty array', () => {
    const text = 'α β γ';
    const tokens = [tok('α', 0), tok('β', 2), tok('γ', 4)];
    expect(lineRenderParts(text, tokens)).toEqual(lineRenderParts(text, tokens, []));
  });

  it('emits nothing for a genuinely unlocatable token, rather than a phantom that prints it twice', () => {
    // A token whose surface isn't in `text` at all (shouldn't happen) is
    // dropped: the verbatim text already prints whatever is there, so a
    // zero-width atom would print the word a SECOND time. The word only loses
    // its click target.
    const parts = lineRenderParts('βγ', [tok('α', 0)]);
    expect(kinds(parts)).toEqual(['text']);
    expect(texts(parts)).toEqual(['βγ']);
  });

  // Editorial sigla printed INSIDE a word: the token surface is the bare word,
  // so a plain indexOf misses it. Before locateToken the documented fallback
  // pushed a zero-width phantom and the word rendered TWICE. No line in this
  // repo's corpus does this today (0 of 21,216 lines with tokens) — the guard
  // is here because the same shared machinery serves plato-reader (20 lines)
  // and aristotle-reader (23).
  it('prints a word once when a supplement is set inside it, keeping it clickable', () => {
    const text = 'ἔπει<τα> δέ.';
    const tokens = [tok('ἔπειτα', 0), tok('δέ', 9)];
    const parts = lineRenderParts(text, tokens);
    expect(kinds(parts)).toEqual(['token', 'text', 'token', 'text']);
    // The rendered part carries the VERBATIM slice, brackets and all, so the
    // line stays byte-identical to the source...
    expect(texts(parts)).toEqual(['ἔπει<τα>', ' ', 'δέ', '.']);
    expect(parts.map((p) => (p.kind === 'speaker' ? '' : p.text)).join('')).toBe(text);
    // ...while the Token still carries the bare word for the popup lookup.
    expect(parts[0]).toMatchObject({ kind: 'token', tok: tokens[0] });
  });

  it('does not swallow a phrase-level closer into a word that already closed its own bracket', () => {
    // A bracket opened AND closed inside the word ("ἀ<μφι>γνοεῖν") leaves
    // nothing owing, so a closer following the word belongs to the phrase, not
    // to the word. Counting only openers left the tally positive at the word's
    // end and the trailing-consumption loop reached past the word and pulled
    // the phrase's "]" into the clickable span.
    const text = '[ἀ<μφι>γνοεῖν] δὲ';
    const tokens = [tok('ἀμφιγνοεῖν', 1), tok('δὲ', 15)];
    const parts = lineRenderParts(text, tokens);
    expect(texts(parts)).toEqual(['[', 'ἀ<μφι>γνοεῖν', '] ', 'δὲ']);
    expect(parts.map((p) => (p.kind === 'speaker' ? '' : p.text)).join('')).toBe(text);
  });

  it('still pulls in a closer for a bracket left open at the word end', () => {
    // "ἔπει<τα>" — the "<" is still open when the word's letters run out, so
    // its ">" belongs to the word and must be pulled in.
    const parts = lineRenderParts('ἔπει<τα> δέ.', [tok('ἔπειτα', 0), tok('δέ', 9)]);
    expect(texts(parts)).toEqual(['ἔπει<τα>', ' ', 'δέ', '.']);
  });

  it('prints a word once when a deletion is set inside it', () => {
    const text = '[προς]θῶμεν νῦν.';
    const tokens = [tok('προςθῶμεν', 0), tok('νῦν', 11)];
    const parts = lineRenderParts(text, tokens);
    // The span starts at the word's first LETTER, so a bracket opened before
    // the word (rather than inside it) stays a verbatim gap ahead of the click
    // target. What matters is that the word prints exactly once and the line
    // reproduces the source byte for byte.
    expect(texts(parts)).toEqual(['[', 'προς]θῶμεν', ' ', 'νῦν', '.']);
    expect(parts.map((p) => (p.kind === 'speaker' ? '' : p.text)).join('')).toBe(text);
    expect(parts.filter((p) => p.kind === 'token')).toHaveLength(2);
  });
});

describe('lineRenderParts — non-lexical tokens (no `k`)', () => {
  // The pipeline omits `k` entirely for a non-lexical token (inline
  // Latin-script apparatus, editor names, bare numerals — no Greek letters
  // at all, so no lexicon entry could ever exist). Such a token must render
  // as plain, non-clickable text: no popup, no dead lexicon link.
  const noKey = (t: string, o: number): Token => ({ t, o });

  it('renders a token with no `k` as text, not a clickable token', () => {
    const text = 'λόγος FGrH 765';
    const tokens = [tok('λόγος', 0), noKey('FGrH', 6), noKey('765', 11)];
    const parts = lineRenderParts(text, tokens);
    expect(kinds(parts)).toEqual(['token', 'text', 'text', 'text', 'text']);
    expect(texts(parts)).toEqual(['λόγος', ' ', 'FGrH', ' ', '765']);
  });

  it('drops an unlocatable no-`k` token too, rather than printing it twice', () => {
    const parts = lineRenderParts('βγ', [noKey('α', 0)]);
    expect(kinds(parts)).toEqual(['text']);
    expect(texts(parts)).toEqual(['βγ']);
  });

  it('does not move char offsets: a mid-line no-`k` token still lets a later speaker offset land correctly', () => {
    const events: SpeakerEvent[] = [{ line: 1, offset: 11, label: 'ΣΩ.' }];
    const text = 'λόγος FGrH καλῶς';
    const tokens = [tok('λόγος', 0), noKey('FGrH', 6), tok('καλῶς', 11)];
    const parts = lineRenderParts(text, tokens, events);
    expect(kinds(parts)).toEqual(['token', 'text', 'text', 'text', 'speaker', 'token']);
    expect(texts(parts)).toEqual(['λόγος', ' ', 'FGrH', ' ', '«ΣΩ.»', 'καλῶς']);
  });
});

describe('lineRenderParts — speaker lead-ins', () => {
  const text = 'ὦ φίλε.';
  const tokens = [tok('ὦ', 0), tok('φίλε', 2)];

  it('offset 0 leads the whole line with the siglum', () => {
    const events: SpeakerEvent[] = [{ line: 1, offset: 0, label: 'ΣΩ.' }];
    const parts = lineRenderParts(text, tokens, events);
    expect(kinds(parts)).toEqual(['speaker', 'token', 'text', 'token', 'text']);
    expect(parts[0]).toEqual({ kind: 'speaker', label: 'ΣΩ.', dash: false });
  });

  it('a mid-line offset at a token boundary sits immediately before that token', () => {
    const events: SpeakerEvent[] = [{ line: 1, offset: 2, label: 'ΕΥΘ.' }];
    const parts = lineRenderParts(text, tokens, events);
    expect(kinds(parts)).toEqual(['token', 'text', 'speaker', 'token', 'text']);
    expect(texts(parts)).toEqual(['ὦ', ' ', '«ΕΥΘ.»', 'φίλε', '.']);
  });

  it('an offset strictly inside a verbatim gap splits the gap around the label', () => {
    // Two-space gap [1,3); the turn begins at offset 2, mid-gap.
    const t2 = 'α  β';
    const tk2 = [tok('α', 0), tok('β', 3)];
    const parts = lineRenderParts(t2, tk2, [{ line: 1, offset: 2, label: 'ΣΩ.' }]);
    expect(kinds(parts)).toEqual(['token', 'text', 'speaker', 'text', 'token']);
    expect(texts(parts)).toEqual(['α', ' ', '«ΣΩ.»', ' ', 'β']);
  });

  it('renders multiple turns on one line in order', () => {
    const t2 = 'α β';
    const tk2 = [tok('α', 0), tok('β', 2)];
    const events: SpeakerEvent[] = [
      { line: 1, offset: 0, label: 'ΣΩ.' },
      { line: 1, offset: 2, label: 'ΕΥΘ.' },
    ];
    const parts = lineRenderParts(t2, tk2, events);
    expect(kinds(parts)).toEqual(['speaker', 'token', 'text', 'speaker', 'token']);
    expect(texts(parts)).toEqual(['«ΣΩ.»', 'α', ' ', '«ΕΥΘ.»', 'β']);
  });

  it('flags the dialectic dash so it renders as an em-dash, not a small-caps siglum', () => {
    const parts = lineRenderParts(text, tokens, [{ line: 1, offset: 0, label: '—' }]);
    expect(parts[0]).toEqual({ kind: 'speaker', label: '—', dash: true });
  });

  it('sorts unordered events and appends a turn at/after the line end', () => {
    const t2 = 'α β';
    const tk2 = [tok('α', 0), tok('β', 2)];
    const events: SpeakerEvent[] = [
      { line: 1, offset: 99, label: 'END' }, // past the text end → trailing
      { line: 1, offset: 0, label: 'ΣΩ.' },
    ];
    const parts = lineRenderParts(t2, tk2, events);
    expect(kinds(parts)).toEqual(['speaker', 'token', 'text', 'token', 'speaker']);
    expect(texts(parts)).toEqual(['«ΣΩ.»', 'α', ' ', 'β', '«END»']);
  });

  it('does not shift the surviving token offsets (labels are outside the token stream)', () => {
    const parts = lineRenderParts(text, tokens, [{ line: 1, offset: 2, label: 'ΕΥΘ.' }]);
    const toks = parts.filter((p) => p.kind === 'token');
    expect(toks.map((p) => (p as { tok: Token }).tok.o)).toEqual([0, 2]);
  });
});

describe('buildFlowRows — whole-book turn flow', () => {
  const line = (n: number, text: string, ts: [string, number][]): GreekLine => ({
    n, text, tokens: ts.map(([t, o]) => tok(t, o)),
  });
  const seg = (column: string, greek: GreekLine[], speakers: SpeakerEvent[] = []): Segment =>
    ({ id: `1:${column}`, column, greek, english: null, speakers });
  // Compact Greek projection: [col, n, cont, tick, [part texts]].
  const grk = (row: { greek: { col: string; n: number; cont: boolean; tick: string | null; parts: ReturnType<typeof lineRenderParts> }[] }) =>
    row.greek.map((l) => [l.col, l.n, l.cont, l.tick, texts(l.parts)]);

  const segments = [
    seg('2a',
      [line(1, 'α β.', [['α', 0], ['β', 2]]), line(2, 'γ δ.', [['γ', 0], ['δ', 2]])],
      [{ line: 1, offset: 0, label: 'ΣΩ.' }, { line: 2, offset: 0, label: 'ΕΥΘ.' }]),
    seg('2b',
      [line(1, 'ε ζ.', [['ε', 0], ['ζ', 2]])],
      [{ line: 1, offset: 2, label: 'ΣΩ.' }]),
  ];

  it('renders one row per turn across section boundaries, ticks on section-first lines', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'One.', p: true },
        { s: 'Euthyphro', d: 'Euth.', g: { c: '2a', n: 2, o: 0 }, e: 'Two.', p: true },
        { s: 'Socrates', d: 'Soc.', g: { c: '2b', n: 1, o: 2 }, e: 'Three.', p: true },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows.map((r) => [r.lead, r.paired, r.display, r.english])).toEqual([
      [false, true, 'Soc.', 'One.'],
      [false, true, 'Euth.', 'Two.'],
      [false, true, 'Soc.', 'Three.'],
    ]);
    // Row 1: 2a line 1 (section-first -> tick "2a").
    expect(grk(rows[0])).toEqual([['2a', 1, false, '2a', ['«ΣΩ.»', 'α', ' ', 'β', '.']]]);
    // Row 2 spans the 2a/2b section boundary: 2a line 2 + the head of 2b line 1
    // (which is 2b's first line -> tick "2b" rides it).
    expect(grk(rows[1])).toEqual([
      ['2a', 2, false, null, ['«ΕΥΘ.»', 'γ', ' ', 'δ', '.']],
      ['2b', 1, false, '2b', ['ε', ' ']],
    ]);
    expect(rows[1].ticks).toEqual(['2b']);
    // Row 3: the tail of 2b line 1 is a continuation slice (no id repeat, no tick).
    expect(grk(rows[2])).toEqual([['2b', 1, true, null, ['«ΣΩ.»', 'ζ', '.']]]);
  });

  it('never doubles a bracketed word when a row anchor cuts inside its sigla', () => {
    // Row anchors carry mid-line offsets, and they move on every rebuild — so a
    // cut can land INSIDE a bracketed token's verbatim span ("ἔπει|<τα>"). The
    // token is then filtered into the first slice while its text straddles the
    // boundary. It must not print twice: the word loses its click target on
    // that row, and the Greek still reads verbatim across the two slices.
    const brk = [
      seg('3a', [line(1, 'ἔπει<τα> καὶ', [['ἔπειτα', 0], ['καὶ', 9]])]),
    ];
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '3a', n: 1, o: 0 }, e: 'One.', p: true },
        // Cut at offset 5 — between "ἔπει" and "<τα>", inside the token span.
        { s: 'Euthyphro', d: 'Euth.', g: { c: '3a', n: 1, o: 5 }, e: 'Two.', p: true },
      ],
    };
    const rows = buildFlowRows(brk, flow);
    // The two slices concatenate to the source line, unaltered.
    const rendered = rows.flatMap((r) => r.greek).flatMap((l) => l.parts)
      .filter((p) => p.kind !== 'speaker').map((p) => p.text).join('');
    expect(rendered).toBe('ἔπει<τα> καὶ');
    // The straddled word appears exactly once, and as plain text (no phantom
    // token part duplicating it before the verbatim run).
    expect(grk(rows[0])).toEqual([['3a', 1, false, '3a', ['ἔπει<']]]);
    expect(rows[0].greek[0].parts.filter((p) => p.kind === 'token')).toHaveLength(0);
    expect(grk(rows[1])).toEqual([['3a', 1, true, null, ['τα> ', 'καὶ']]]);
  });

  it('merges a Greek-bearing same-speaker residual (section split mid-speech) into the previous row', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'One.', p: true },
        // Section 2b opens mid-speech: no top-level English, the continuation is
        // a same-speaker folded sub. It must merge into row 0, not make its own.
        { s: null, d: null, g: { c: '2b', n: 1, o: 0 }, e: null, p: false,
          sub: [{ s: 'Socrates', d: 'Soc.', e: 'Still Socrates.' }] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows.length).toBe(1);
    expect([rows[0].display, rows[0].english]).toEqual(['Soc.', 'One.']);
    // The sub folds in as a continuation paragraph (no repeated label)...
    expect(rows[0].englishCont).toEqual([{ text: 'Still Socrates.', ep: undefined }]);
    // ...and the section-2b Greek + its tick merge into the same row.
    expect(rows[0].ticks).toEqual(['2a', '2b']);
    expect(grk(rows[0]).some((l) => l[0] === '2b')).toBe(true);
  });

  it('does NOT merge a residual whose folded speaker differs (never mis-attribute)', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'One.', p: true },
        { s: null, d: null, g: { c: '2b', n: 1, o: 0 }, e: null, p: false,
          sub: [{ s: 'Euthyphro', d: 'Euth.', e: 'Different speaker.' }] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows.length).toBe(2);        // kept as its own one-sided row
    expect(rows[1].sub?.[0]?.d).toBe('Euth.');
  });

  it('does NOT merge a same-speaker residual whose folded display is a real heading', () => {
    // A narrated frame's section rubric ("The Speech of Pausanias") whose
    // canonical speaker is the narrator is a heading, not a redundant label —
    // it must keep its own row so the heading survives.
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Apollodorus', d: 'Ap.', g: { c: '2a', n: 1, o: 0 }, e: 'Frame.', p: true },
        { s: null, d: null, g: { c: '2b', n: 1, o: 0 }, e: null, p: false,
          sub: [{ s: 'Apollodorus', d: 'The Speech of Pausanias', e: 'A speech.' }] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows.length).toBe(2);
    expect(rows[1].sub?.[0]?.d).toBe('The Speech of Pausanias');
  });

  it('emits a leading continuation row for pre-turn Greek and leadE', () => {
    const flow: TurnFlow = {
      leadE: 'tail of speech.',
      turns: [{ s: 'Euthyphro', d: 'Euth.', g: { c: '2a', n: 2, o: 0 }, e: 'New.', p: true }],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows[0].lead).toBe(true);
    expect(rows[0].english).toBe('tail of speech.');
    // The line-1 siglum event still splices in (the Greek column always shows
    // its sigla, lead row or not).
    expect(grk(rows[0])).toEqual([['2a', 1, false, '2a', ['«ΣΩ.»', 'α', ' ', 'β', '.']]]);
    expect(rows[0].ticks).toEqual(['2a']);
    expect(rows[1].english).toBe('New.');
  });

  it('renders one-sided residual rows in place', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'One.', p: true },
        { s: 'Euthyphro', d: 'Euth.', g: null, e: 'Loose English.', p: false },
        { s: null, d: null, g: { c: '2a', n: 2, o: 0 }, e: null, p: false },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    // Paired row's Greek runs to the NEXT Greek-bearing turn (the residual
    // English turn between them does not cut the Greek).
    expect(grk(rows[0])).toEqual([['2a', 1, false, '2a', ['«ΣΩ.»', 'α', ' ', 'β', '.']]]);
    expect(rows[1].greek).toEqual([]);
    expect(rows[1].english).toBe('Loose English.');
    expect(rows[1].paired).toBe(false);
    // Greek-only residual: its Greek runs to the book end, no English cell.
    expect(rows[2].english).toBeNull();
    expect(grk(rows[2])[0][1]).toBe(2);
  });

  it('token identity survives slicing (popup lookups keep the original Token)', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [{ s: 'Socrates', d: 'Soc.', g: { c: '2b', n: 1, o: 2 }, e: 'X.', p: true }],
    };
    const rows = buildFlowRows(segments, flow);
    const lastRow = rows[rows.length - 1];
    const tokPart = lastRow.greek[0].parts.find((pt) => pt.kind === 'token');
    expect((tokPart as { tok: Token }).tok).toBe(segments[1].greek[0].tokens[1]);
  });

  it('merges a same-speaker English residual into the previous row as a continuation', () => {
    // Euthyphro 2d-3a: Fowler splits Socrates' speech into two <said> where
    // the OCT has ONE ΣΩ. turn — the second half flows under the same row.
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'First half.', p: true },
        { s: 'Socrates', d: 'Soc.', g: null, e: 'And so Meletus, perhaps.', p: false },
        { s: 'Euthyphro', d: 'Euth.', g: { c: '2a', n: 2, o: 0 }, e: 'Reply.', p: true },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(2);
    expect(rows[0].english).toBe('First half.');
    expect(rows[0].englishCont).toEqual([{ text: 'And so Meletus, perhaps.', ep: undefined }]);
    expect(rows[1].english).toBe('Reply.');
  });

  it('merges an unattributed (null-speaker) English residual into the previous row', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Speech.', p: true },
        { s: null, d: null, g: null, e: 'Unattributed continuation.', p: false },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(1);
    expect(rows[0].englishCont).toEqual([{ text: 'Unattributed continuation.', ep: undefined }]);
  });

  it('keeps a different-speaker English residual as its own one-sided row', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Mine.', p: true },
        { s: 'Euthyphro', d: 'Euth.', g: null, e: 'Not his.', p: false },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(2);
    expect(rows[0].englishCont).toEqual([]);
    expect(rows[1].english).toBe('Not his.');
    expect(rows[1].greek).toEqual([]);
    expect(rows[1].paired).toBe(false);
  });

  it('returns no rows for an empty flow', () => {
    expect(buildFlowRows(segments, { leadE: null, turns: [] })).toEqual([]);
  });

  it('leaves ep/et/sub undefined for ordinary dialogue rows (no para leakage)', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [{ s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Hi.', p: true }],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows[0].ep).toBeUndefined();
    expect(rows[0].et).toBeUndefined();
    expect(rows[0].sub).toBeUndefined();
  });

  it('never merges a sub-bearing English residual into the previous row (sub would drop)', () => {
    // Pipeline B4 (Lysis's opening): a g:null residual whose speaker matches
    // the previous row but which carries folded sub-speeches — merging its `e`
    // into prev.englishCont would silently lose the stack.
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Speech.', p: true },
        { s: 'Socrates', d: null, g: null, e: 'Narration lead.', p: false,
          sub: [{ s: 'Hippothales', d: null, e: 'Whither away?', ep: null }] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(2);
    expect(rows[0].englishCont).toEqual([]);
    expect(rows[1].english).toBe('Narration lead.');
    expect(rows[1].sub).toEqual([{ s: 'Hippothales', d: null, e: 'Whither away?', ep: null }]);
  });

  it('a null/empty sub does not block the same-speaker residual merge (old behavior)', () => {
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Speech.', p: true },
        { s: 'Socrates', d: null, g: null, e: 'Continuation.', p: false, sub: null },
        { s: null, d: null, g: null, e: 'More.', p: false, sub: [] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(1);
    expect(rows[0].englishCont).toEqual([{ text: 'Continuation.', ep: undefined }, { text: 'More.', ep: undefined }]);
  });

  it('preserves ep paragraph breaks through the same-speaker residual merge (Timaeus)', () => {
    // B2: a long residual speech carries internal paragraph breaks. Merged as a
    // continuation it must keep them ({text, ep}); merged as the row's main
    // English (previous row had none) they become the row's own ep.
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Critias', d: 'Crit.', g: { c: '2a', n: 1, o: 0 }, e: 'Lead speech.', p: true },
        { s: 'Critias', d: null, g: null, e: 'Long tale. New paragraph here.', p: false, ep: [10] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(1);
    expect(rows[0].englishCont).toEqual([{ text: 'Long tale. New paragraph here.', ep: [10] }]);
    // Main-English variant: the residual merges into a row whose english was
    // null (a Greek-only residual), so its ep rides the row itself.
    const flow2: TurnFlow = {
      leadE: null,
      turns: [
        { s: null, d: null, g: { c: '2a', n: 1, o: 0 }, e: null, p: false },
        { s: null, d: null, g: null, e: 'Tail. Break follows here.', p: false, ep: [5] },
      ],
    };
    const rows2 = buildFlowRows(segments, flow2);
    expect(rows2).toHaveLength(1);
    expect(rows2[0].english).toBe('Tail. Break follows here.');
    expect(rows2[0].ep).toEqual([5]);
  });

  it('passes sub:null and sub:[] through on e:null rows without merging or crashing', () => {
    // Codex review finding 1's data shapes: a Greek-anchored row with e:null
    // and a null (the pipeline's explicit null) or empty sub must come out as
    // its own row — english null, sub passed through — never folded or dropped.
    const flow: TurnFlow = {
      leadE: null,
      turns: [
        { s: 'Socrates', d: 'Soc.', g: { c: '2a', n: 1, o: 0 }, e: 'Speech.', p: true },
        { s: null, d: null, g: { c: '2a', n: 2, o: 0 }, e: null, p: false, sub: null },
        { s: null, d: null, g: { c: '2b', n: 1, o: 0 }, e: null, p: false, sub: [] },
      ],
    };
    const rows = buildFlowRows(segments, flow);
    expect(rows).toHaveLength(3);
    expect(rows[1].english).toBeNull();
    expect(rows[1].sub).toBeNull();
    expect(rows[1].greek.length).toBeGreaterThan(0);
    expect(rows[2].english).toBeNull();
    expect(rows[2].sub).toEqual([]);
    expect(rows[2].greek.length).toBeGreaterThan(0);
  });

  describe('paragraph flow (narrated works, kind:"para")', () => {
    it('carries ep/et/sub through and still slices Greek for s:null rows', () => {
      const flow: TurnFlow = {
        kind: 'para',
        leadE: null,
        turns: [
          // Ordinary paragraph row: no speaker, an internal paragraph break (ep).
          { s: null, d: null, g: { c: '2a', n: 1, o: 0 }, e: 'Para one. Para two.', p: false, ep: [10] },
          // Embedded-dialogue row: a narrated paragraph carrying english.turns.
          { s: null, d: null, g: { c: '2a', n: 2, o: 0 }, e: 'Reported speech.', p: false,
            et: [{ o: 0, s: 'Socrates', d: 'Soc.' }] },
          // Section-anchored one-sided row: English cell null, sub-speeches stacked.
          { s: null, d: null, g: { c: '2b', n: 1, o: 0 }, e: null, p: false,
            sub: [{ s: 'Cephalus', d: 'Ceph.', e: 'A one-sided speech.', ep: [4] }] },
        ],
      };
      const rows = buildFlowRows(segments, flow);
      expect(rows).toHaveLength(3);
      // Row 0: passthrough ep; speaker/display null; Greek still sliced (s:null
      // rows are handled by the speaker-agnostic slicer unchanged).
      expect(rows[0].ep).toEqual([10]);
      expect(rows[0].english).toBe('Para one. Para two.');
      expect(rows[0].speaker).toBeNull();
      expect(rows[0].display).toBeNull();
      expect(rows[0].greek.length).toBeGreaterThan(0);
      // Row 1: passthrough et.
      expect(rows[1].et).toEqual([{ o: 0, s: 'Socrates', d: 'Soc.' }]);
      expect(rows[1].english).toBe('Reported speech.');
      // Row 2: e:null does NOT trigger the same-speaker English merge (that path
      // needs t.e truthy) — it lands as its own row with sub carried through.
      expect(rows[2].english).toBeNull();
      expect(rows[2].sub).toEqual([{ s: 'Cephalus', d: 'Ceph.', e: 'A one-sided speech.', ep: [4] }]);
      expect(rows[2].greek.length).toBeGreaterThan(0);
    });

    it('does not fold consecutive s:null para rows into one (each paragraph is its own row)', () => {
      // Both rows carry Greek (g resolves), so the English-residual merge (which
      // only fires when greek is empty) never runs — s:null must not collapse
      // adjacent paragraphs the way it would a null-speaker English residual.
      const flow: TurnFlow = {
        kind: 'para',
        leadE: null,
        turns: [
          { s: null, d: null, g: { c: '2a', n: 1, o: 0 }, e: 'First paragraph.', p: false },
          { s: null, d: null, g: { c: '2a', n: 2, o: 0 }, e: 'Second paragraph.', p: false },
        ],
      };
      const rows = buildFlowRows(segments, flow);
      expect(rows).toHaveLength(2);
      expect(rows[0].english).toBe('First paragraph.');
      expect(rows[1].english).toBe('Second paragraph.');
      expect(rows[0].englishCont).toEqual([]);
    });
  });
});

describe('buildEnglishTurnBlocks — fallback English turn stack', () => {
  const turn = (offset: number, speaker: string | null, display: string | null): EnglishTurn =>
    ({ offset, speaker, display });

  it('slices the prose into one block per turn, labels never inline', () => {
    // "as I have. Our Athenians…" — the two turns must come out as SEPARATE
    // blocks (the glued "…as I have.SOCRATES. Our…" defect this guards against).
    const text = 'What is new? Nothing, as I have. Our Athenians differ.';
    const turns = [turn(0, 'Euthyphro', 'Euthyphro.'), turn(33, 'Socrates', 'Socrates.')];
    const blocks = buildEnglishTurnBlocks(text, turns);
    expect(blocks).toEqual([
      { lead: false, display: 'Euthyphro.', text: 'What is new? Nothing, as I have.' },
      { lead: false, display: 'Socrates.', text: 'Our Athenians differ.' },
    ]);
  });

  it('puts pre-turn continuation text in an unlabeled leading block', () => {
    const text = 'tail of an earlier speech. A new turn.';
    const turns = [turn(27, 'Socrates', 'Soc.')];
    const blocks = buildEnglishTurnBlocks(text, turns);
    expect(blocks).toEqual([
      { lead: true, display: null, text: 'tail of an earlier speech.' },
      { lead: false, display: 'Soc.', text: 'A new turn.' },
    ]);
  });

  it('omits an empty leading block when the first turn opens the chunk', () => {
    const blocks = buildEnglishTurnBlocks('Speech.', [turn(0, 'Socrates', 'Soc.')]);
    expect(blocks).toEqual([{ lead: false, display: 'Soc.', text: 'Speech.' }]);
  });

  it('an unattributed turn keeps a null display (renders as an em-dash block)', () => {
    const blocks = buildEnglishTurnBlocks('Yes. No.', [turn(0, null, null), turn(5, null, null)]);
    expect(blocks.map((b) => [b.lead, b.display, b.text])).toEqual([
      [false, null, 'Yes.'],
      [false, null, 'No.'],
    ]);
  });


  it('drops an empty unlabeled slice (no bare em-dash paragraph) but keeps an empty labeled one', () => {
    // Adjacent boundaries with nothing between: the dash block vanishes; a
    // labeled turn keeps its attribution block even with no text.
    const blocks = buildEnglishTurnBlocks('Speech.', [
      turn(0, null, null),
      turn(0, 'Socrates', 'Soc.'),
    ]);
    expect(blocks).toEqual([{ lead: false, display: 'Soc.', text: 'Speech.' }]);
  });

  it('a chunk with no turns is a single unlabeled block (plain prose)', () => {
    expect(buildEnglishTurnBlocks('Just prose.', [])).toEqual([
      { lead: true, display: null, text: 'Just prose.' },
    ]);
  });
});

describe('labelSuppression', () => {
  // Minimal FlowRow factory — only the fields labelSuppression reads.
  const row = (p: Partial<FlowRow>): FlowRow => ({
    lead: false, paired: true, display: null, speaker: null,
    greek: [], english: 'x', englishCont: [], ticks: [], sub: null, ...p,
  });

  it('suppresses a lead-in that repeats the same speaker + display', () => {
    const meta = labelSuppression([
      row({ speaker: 'Socrates', display: 'Soc.' }),
      row({ speaker: 'Socrates', display: 'Soc.' }),
    ]);
    expect(meta.map((m) => m.hideLead)).toEqual([false, true]);
  });

  it('keeps labels through a genuine alternation', () => {
    const meta = labelSuppression([
      row({ speaker: 'Meno', display: 'Men.' }),
      row({ speaker: 'Socrates', display: 'Soc.' }),
      row({ speaker: 'Meno', display: 'Men.' }),
    ]);
    expect(meta.map((m) => m.hideLead)).toEqual([false, false, false]);
  });

  it('keeps a folded sub whose display is a real heading (not a redundant label)', () => {
    // Codex #1: same canonical speaker (the narrator) but a rubric display.
    const meta = labelSuppression([
      row({ speaker: 'Apollodorus', display: 'Ap.' }),
      row({ speaker: null, display: null, english: null,
        sub: [{ s: 'Apollodorus', d: 'The Speech of Pausanias', e: 'A speech.' }] }),
    ]);
    expect(meta[1].hideSub).toEqual([false]); // heading kept
  });

  it('still suppresses a folded sub that repeats the same label', () => {
    const meta = labelSuppression([
      row({ speaker: 'Socrates', display: 'Soc.' }),
      row({ speaker: null, display: null, english: null,
        sub: [{ s: 'Socrates', d: 'Soc.', e: 'More.' }] }),
    ]);
    expect(meta[1].hideSub).toEqual([true]);
  });

  it('resets the floor after an em-dash turn (Codex #2)', () => {
    // Soc. → unattributed dash → Soc. again: the second Soc. must keep its label.
    const meta = labelSuppression([
      row({ speaker: 'Socrates', display: 'Soc.' }),
      row({ speaker: null, display: null }),          // em-dash turn (has English)
      row({ speaker: 'Socrates', display: 'Soc.' }),
    ]);
    expect(meta.map((m) => m.hideLead)).toEqual([false, false, false]);
  });
});

// --- splitGreekSections — Discourses' `sections` channel split -------------
//
// A GPT-5.6-Sol-High adversarial review found the ORIGINAL implementation
// (word-index based: converting a `sections[i].o` char offset to a token
// index via an exact-match search, then slicing by token index) silently
// DROPPED a section whenever its boundary fell in an inter-token gap rather
// than exactly on a token start — e.g. a section opening with punctuation
// (an opening quote). Discourses 1.1 sec 18 hits this shape in the real
// corpus (43/2,633 Discourses + 1/68 Enchiridion boundaries): the whole
// section silently vanished from the page. These tests pin the fixed,
// char-offset-direct split down: every piece must cover exactly
// [o_i, o_next) of the line's text, and concatenating every piece's text
// must reproduce the line's text byte-exactly.
describe('splitGreekSections — section-paragraph split (Discourses)', () => {
  const line = (text: string, tokens: Token[], sections?: { n: number; o: number }[]): GreekLine =>
    ({ n: 1, text, tokens, ...(sections ? { sections } : {}) });

  it('passes a line through UNCHANGED (same object) when it has no `sections`', () => {
    const l = line('λόγος ἀρετή', [tok('λόγος', 0), tok('ἀρετή', 6)]);
    const [out] = splitGreekSections([l]);
    expect(out).toBe(l);
  });

  it('passes a line through UNCHANGED when `sections` has fewer than 2 entries', () => {
    const l = line('λόγος ἀρετή', [tok('λόγος', 0), tok('ἀρετή', 6)], [{ n: 1, o: 0 }]);
    const [out] = splitGreekSections([l]);
    expect(out).toBe(l);
  });

  it('reproduces the 1.1 sec 18 shape — a boundary in an inter-token gap — without dropping the section', () => {
    // "εἶπεν. 'Ἐμὲ δεῖ." — section 2 opens with an opening curly quote that
    // sits in the gap between the first token's end and the second token's
    // start (token starts are 0 and 8; the boundary offset 7 matches
    // neither), exactly the shape that made the old word-index detour
    // return `tokens.length` (its "not found" fallback) and produce an
    // empty, dropped final piece.
    const text = "εἶπεν. ‘Ἐμὲ δεῖ.";
    const tokens = [tok('εἶπεν', 0), tok('Ἐμὲ', 8), tok('δεῖ', 12)];
    const boundaryOffset = text.indexOf('‘');
    expect(tokens.some((t) => t.o === boundaryOffset)).toBe(false); // confirms: not a token start
    const l = line(text, tokens, [{ n: 1, o: 0 }, { n: 2, o: boundaryOffset }]);

    const pieces = splitGreekSections([l]);

    expect(pieces).toHaveLength(2);
    // Full coverage: concatenating every piece's text reproduces the whole
    // line's text byte-exactly — nothing dropped, nothing duplicated.
    expect(pieces.map((p) => p.text).join('')).toBe(text);
    // Non-empty piece: section 2 must actually render, not vanish.
    expect(pieces[1].text.length).toBeGreaterThan(0);
    expect(pieces[1].text.startsWith('‘')).toBe(true);
    expect(pieces[1].tokens.length).toBeGreaterThan(0);
    expect(pieces[1].paraN).toBe(2);
    expect(pieces[1].cont).toBe(true);
    expect(pieces[0].cont).toBeFalsy();
  });

  it('covers a synthetic multi-boundary line byte-exactly, mixing token-start and gap boundaries', () => {
    const text = "one two. 'three four! 'five six.";
    const tokens = [
      tok('one', 0), tok('two', 4), tok('three', 10), tok('four', 16), tok('five', 23), tok('six', 28),
    ];
    // Boundary 2 (offset 9) and boundary 3 (offset 22) both sit on the
    // apostrophe immediately before "three"/"five" — inter-token gaps, not
    // token starts (10 and 23 are the nearest token starts).
    const boundaries = [{ n: 1, o: 0 }, { n: 2, o: 9 }, { n: 3, o: 22 }];
    const l = line(text, tokens, boundaries);

    const pieces = splitGreekSections([l]);

    expect(pieces).toHaveLength(3);
    // Byte-exact total coverage.
    expect(pieces.map((p) => p.text).join('')).toBe(text);
    // No piece is empty.
    for (const p of pieces) expect(p.text.length).toBeGreaterThan(0);
    expect(pieces.map((p) => p.paraN)).toEqual([1, 2, 3]);
    expect(pieces.map((p) => p.cont)).toEqual([false, true, true]);
    expect(pieces[0].text).toBe('one two. ');
    expect(pieces[1].text).toBe("'three four! ");
    expect(pieces[2].text).toBe("'five six.");
    // Every token is assigned to exactly the piece whose text span contains
    // its start — the token/gap contract lineRenderParts depends on within
    // each piece, not the whole original line.
    expect(pieces[0].tokens.map((t) => t.t)).toEqual(['one', 'two']);
    expect(pieces[1].tokens.map((t) => t.t)).toEqual(['three', 'four']);
    expect(pieces[2].tokens.map((t) => t.t)).toEqual(['five', 'six']);
  });

  it('keeps the token-walk contract intact WITHIN each piece (lineRenderParts reconstructs the piece text exactly)', () => {
    // Watch-interaction from the fix: token offsets handed to lineRenderParts
    // are re-derived per piece from that piece's own text/tokens (never the
    // original line's global offsets) — this must stay true after the split.
    const text = "εἶπεν. ‘Ἐμὲ δεῖ.";
    const tokens = [tok('εἶπεν', 0), tok('Ἐμὲ', 8), tok('δεῖ', 12)];
    const l = line(text, tokens, [{ n: 1, o: 0 }, { n: 2, o: text.indexOf('‘') }]);

    const pieces = splitGreekSections([l]);
    for (const p of pieces) {
      const parts = lineRenderParts(p.text, p.tokens);
      expect(parts.map((part) => (part.kind === 'speaker' ? '' : part.text)).join('')).toBe(p.text);
    }
  });
});

// splitWrapLine (docs/lined-source-plan.md Q2; wrapO deviation 2026-08-29,
// §3): splits a wrapped line's already-built render parts at the WRAPPED
// token (located by `tok.o === wrapO`) into `head` (kept on this line, the
// token repainted with only the chars printed here plus the hyphen) and
// `carried` (everything that moves to the next line's leading edge: the
// wrapped word's own remainder plus every render part after it) — the SAME
// token object as before for the wrapped word's own two halves, so a caller
// (Reader.svelte's `greekItems`/`lineParts`) can paint the remainder on the
// next line bound to that identical token, and clicking/hovering either
// piece opens the same popup.
describe('splitWrapLine — lined-source hyphen-split repaint (Discourses)', () => {
  it("1.1's own worked example (plan §1.2/Q2): 'αὐτὴν αὑτῆς', wrap 2 → 'αὑ-' painted, same token kept", () => {
    const text = 'Τῶν ἄλλων αὐτὴν αὑτῆς';
    const last = tok('αὑτῆς', 16);
    const tokens = [tok('Τῶν', 0), tok('ἄλλων', 4), tok('αὐτὴν', 10), last];
    const parts = lineRenderParts(text, tokens);
    const { head, carried } = splitWrapLine(parts, 16, 2);

    // Every part but the last is untouched (same array contents).
    expect(head.slice(0, -1)).toEqual(parts.slice(0, -1));
    const headPart = head[head.length - 1];
    expect(headPart).toEqual({ kind: 'token', text: 'αὑ-', tok: last });
    // The SAME token object — not a copy — so `popup?.token === part.tok`
    // (Reader.svelte's own identity check) still matches it.
    expect(headPart.kind === 'token' && headPart.tok).toBe(last);
    // The word's own surface (`tok.t`) is untouched — only the PAINTED
    // `text` is truncated; morphology/LSJ/search still see the whole word.
    expect(last.t).toBe('αὑτῆς');
    // Nothing follows the wrapped token here, so `carried` is exactly its
    // own remainder, still bound to the same token object.
    expect(carried).toEqual([{ kind: 'token', text: 'τῆς', tok: last }]);
    expect(carried[0].kind === 'token' && carried[0].tok).toBe(last);
  });

  it('reconstitutes the whole word exactly once when the painted head is joined with the carried remainder', () => {
    // Mirrors Reader.svelte's own contract: `t.slice(0, wrap) + '-'` on this
    // line, `t.slice(wrap)` as the next line's leading carried block. The
    // two slices are disjoint and exhaustive, so concatenating them (hyphen
    // included) reproduces exactly `t`, plus one inserted print hyphen —
    // never a duplicate or a dropped character.
    const wrap = 2;
    const last = tok('αὑτῆς', 0);
    const parts = lineRenderParts('αὑτῆς', [last]);
    const { head, carried } = splitWrapLine(parts, 0, wrap);
    const headText = (head[head.length - 1] as { text: string }).text;
    const tailText = (carried[0] as { text: string }).text;
    expect(headText).toBe('αὑ-');
    expect(tailText).toBe('τῆς');
    expect(headText.slice(0, -1) + tailText).toBe(last.t);
  });

  it("drops a trailing punctuation tail from `head` and carries it forward bound to the wrapped token (I3's 2026-08-29 amendment, docs/lined-source-plan.md §3)", () => {
    // Real Discourses data: most section-straddling wraps absorb the
    // continuation word's sentence-final punctuation too (sections begin
    // after sentences end), so the line's last render PART is often a
    // letterless `text` tail (the "." atom `lineRenderParts` pushes after
    // the token), not the token part itself. `splitWrapLine` must locate
    // the TOKEN by `wrapO` (not the last part), repaint it into `head`, and
    // move that tail into `carried` — never stranded after the hyphen.
    const last = tok('λόγος', 0);
    const parts = lineRenderParts('λόγος.', [last]);
    expect(parts.map((p) => p.kind)).toEqual(['token', 'text']); // word, then the "." tail
    const { head, carried } = splitWrapLine(parts, 0, 2);

    expect(head).toEqual([{ kind: 'token', text: 'λό-', tok: last }]);
    // The tail is gone from THIS line's `head`, not merely unpainted.
    expect(head.some((p) => p.kind === 'text')).toBe(false);
    // ...and rides along in `carried`, after the wrapped word's remainder.
    expect(carried).toEqual([
      { kind: 'token', text: 'γος', tok: last },
      { kind: 'text', text: '.' },
    ]);
  });

  it('em-dash glob (the real defect, epicurus-letter-to-herodotus §53/§69): a token AFTER the wrapped one — not part of it — rides along in `carried`, independently clickable', () => {
    // Whole-whitespace-token absorption (I4) can glue MORE than the wrapped
    // word onto a joined line when the source glues an em dash straight
    // onto the next word with no space: "…σχηματίζε-" / "σθαι—πολλὴν
    // γὰρ…" absorbs "σθαι—πολλὴν" whole, so the line's LAST token
    // ("πολλὴν") is NOT the wrapped one ("σχηματίζεσθαι"). `wrapO` names
    // the wrapped token explicitly, so `splitWrapLine` finds it by offset,
    // not array position.
    const wrapped = tok('σχηματίζεσθαι', 13);
    const glued = tok('πολλὴν', 27);
    const text = 'τῶν ὁμογενῶν σχηματίζεσθαι—πολλὴν';
    const tokens = [tok('τῶν', 0), tok('ὁμογενῶν', 4), wrapped, glued];
    const parts = lineRenderParts(text, tokens);
    expect(parts.map((p) => p.kind)).toEqual(['token', 'text', 'token', 'text', 'token', 'text', 'token']);

    const { head, carried } = splitWrapLine(parts, 13, 9);

    // `head` ends with the wrapped token truncated to what THIS line
    // printed, plus the hyphen -- "πολλὴν" (and the glued em dash before
    // it) never appear in `head` at all.
    expect(head[head.length - 1]).toEqual({ kind: 'token', text: 'σχηματίζε-', tok: wrapped });
    expect(head.some((p) => p.kind === 'token' && p.tok === glued)).toBe(false);

    // `carried` opens with the wrapped word's OWN remainder (still bound to
    // `wrapped`), then the glued em dash as a plain text part, then
    // "πολλὴν" as its OWN separately-clickable token part -- not merged
    // into one text blob.
    expect(carried).toEqual([
      { kind: 'token', text: 'σθαι', tok: wrapped },
      { kind: 'text', text: '—' },
      { kind: 'token', text: 'πολλὴν', tok: glued },
    ]);
    expect(carried[2].kind === 'token' && carried[2].tok).toBe(glued);
  });

  it('is a genuine no-op (head unchanged, carried empty) when no part matches `wrapO`', () => {
    // A defensive fail-safe only, for a shape that should never occur on
    // real `wrap`-carrying data (I3 requires `wrapO` to name a real token):
    // if `wrap`/`wrapO` are somehow set on a line whose parts are pure
    // verbatim text (no clickable token anywhere), splitWrapLine must not
    // guess which atom to split, or invent a click target that doesn't
    // correspond to a real token.
    const parts = lineRenderParts('. . .', []);
    expect(parts.every((p) => p.kind === 'text')).toBe(true);
    const { head, carried } = splitWrapLine(parts, 0, 2);
    expect(head).toEqual(parts);
    expect(head).not.toBe(parts); // still a fresh array, per the doc comment
    expect(carried).toEqual([]);
  });

  it('handles wrap === 1 and wrap === len(t) - 1 (the boundary values the data invariant I3 allows)', () => {
    const shortTok = tok('ab', 0);
    const parts = lineRenderParts('ab', [shortTok]);
    // wrap: 1 char printed on this line, 1 char carried.
    const { head, carried } = splitWrapLine(parts, 0, 1);
    expect((head[0] as { text: string }).text).toBe('a-');
    expect((carried[0] as { text: string }).text).toBe('b');
  });

  it('sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29): a trailing σ in the painted head is folded to ς before the hyphen, reproducing Schenkl\'s "προς-"', () => {
    // Real corpus locus: enchiridion ch.31 §5. The stored token surface
    // carries the CORRECT medial σ (stage1_greek.py's rejoin already folded
    // ς->σ there), but Schenkl's page prints the line-final ς immediately
    // before the wrap hyphen -- the reader must undo the fold for display,
    // never for the stored data (`tok.t` stays "προσήκει" throughout).
    const last = tok('προσήκει', 0);
    const parts = lineRenderParts('προσήκει', [last]);
    const { head, carried } = splitWrapLine(parts, 0, 4);

    expect(head).toEqual([{ kind: 'token', text: 'προς-', tok: last }]);
    expect(carried).toEqual([{ kind: 'token', text: 'ήκει', tok: last }]);
    // The word's own surface is untouched -- only the painted `text` on the
    // head fragment differs from a plain slice.
    expect(last.t).toBe('προσήκει');
  });

  it('folds a trailing σ through a closing siglum when repainting wrap metadata', () => {
    const last = tok('προ<σ>θέσει', 0);
    const parts = lineRenderParts('προ<σ>θέσει', [last]);
    const { head, carried } = splitWrapLine(parts, 0, 6);

    expect(head).toEqual([{ kind: 'token', text: 'προ<ς>-', tok: last }]);
    expect(carried).toEqual([{ kind: 'token', text: 'θέσει', tok: last }]);
    expect(last.t).toBe('προ<σ>θέσει');
  });

  it('sigma-fold leaves a head NOT ending in σ unchanged (only a trailing σ is ever folded)', () => {
    const last = tok('αὑτῆς', 0);
    const parts = lineRenderParts('αὑτῆς', [last]);
    const { head } = splitWrapLine(parts, 0, 2);
    expect((head[0] as { text: string }).text).toBe('αὑ-');
  });
});
