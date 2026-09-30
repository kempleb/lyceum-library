import { describe, expect, it } from 'vitest';
import { applyEditionNotes, classifyDkBracket, findEditionNotes, numberEditionNotes } from '../lib/dk-edition-notes';
import type { LineRenderPart } from '../lib/speakers';

// DK edition references as numbered notes (John, 2026-09-28). Every shape
// below is taken from the 39-work survey (see the module doc).
const cases: Record<string, string[]> = {
  note: [
    // The ruling's own examples.
    'FHG III 42 fr. 28', 'FGrHist. 84 F 25 II 197', 'fr. 173 Us.', 'II 253, 28', 'fr 50 Fowler', 'Nauck FGT p. 792',
    // Edition fragment/page numbers and sigla.
    'F GrHist. 244 F 30 II 1028', 'FGHist. 244 F 28 II 1028', 'fr. 12 FHG III 39', 'fr: 7 FHG II 273', 'II 40, 2 St.',
    'I 673 K.', 'XVII A 681 K.', 'XVII A p. 1002 K', 'DOX. 276', 'D. 358', 'fr. 6a. D. 483, 2', 'O. A. II 156b 6 Sauppe',
    'p. 15, 12 Us.', 'p 218', 'c. 41, 7', '§ 137', ' § 58', 'Zeller IIIa 6302', 'fr. 71,', 'ebd. 3 F 167',
    // Ancient loci: Stephanus pages, Homer books, other authors.
    '309D', '316 A', 'Protag. 343A', 'Theaet. 171A', 'Hom. B 273', 'de anima A 2. 405a 19', 'Σ 107', 'γ 301. δ 80. 90',
    'zu Φ 252', 'H 99', 'S 470', 'VII 35', 'V. 10', 'Stob. III 5, 23', 'DIODOR. XIII 83', 'Anth. Pal. VII 84',
    // No digit, but an edition siglum.
    'fehlt FHG', 'IG XIV', 'Cr. An. Ox. III', 'a. O.',
    // A reference with Greek in it.
    'Eudemos Γεωμετρικὴ ἱστορία fr. 84 Speng.', 'fr. 577 aus d. Πολιτεία Σαμίων', 'πλῆρες Simpl. 44, 16',
    // Mixed with a DK cross-reference: a note whose pop-up keeps the link.
    'fr. 173 Us.; 68 A 9', 'Soph. 237 A vgl. B 7', '127 B; vgl. A 11', 'fr. 94 Speng. Vgl. 11 A 5 I 74, 20',
    'STOB. III 1, 27; s. B 187', 'II 445, 16 St.; s. A 14 I 284, 18', 'vgl. B 6. Spengel Συν. τεχν. p. 26ff.',
    // Numbers only (verse or DK page), no DK item: notes (reported ambiguous).
    '1. 2', '17. 18.', '74, 1', 'AI 279, 1ff.', 's. II 254, 8', 'vgl. 166, 15', '58 A', '68 A', '68 B IX 4',
  ],
  crossref: [
    'B 10', ' B 30', 'B27', '31 B 17', 'vgl. B 91. 12', '31 A 69a. B 94', 's. 82 A 7. 85 A 2', 'Heraklit, 22 B 20',
    'Pherekydes 7 A 1', 'Emped., vgl. 31 A 6', '11 A 1 Thales', '?, vgl. B 1', '= B 43?', 'folgt 1 A 12', 'hinter 2 B 1',
    'nach B 8, 59', 'z. 28 A 5', 'C 1', 'vgl. C 5', 'A 1 a', 'B 6 b', 'B. 9', 'vgl. A. 1 II 82, 14',
    // Ranges.
    'B 78—81', '68 C 2—6', 's. 60 A 1—5', '68 B 298b—299h', 'B 44a—71',
    // With DK's own locus: line, volume page, "Ende", "Mitte", "§", "V.", "ff.".
    'B 17, 32', '31 B 17, 21', 'B 12 II 38, 8', 'A 86 I 302, 22', 'A 86 i 302, 11ff', 'A 2; II 85, 2', 'vgl. A 1, I 247, 14',
    'nach B 1 I 227, 39. 228, 12', 'vgl. A 32. 33, 3 I 122, 26 ff.', 'B 17, 7. 8', '28 B 8, 43—45', 'B 4 Ende',
    '31 A 66 Mitte', '28 A 1 § 23', 's. A 3a V. 132', 'A 13ff.', 'B 33 ?', 'vgl. A 22 B 56',
    // DK's Greek Α/Β for the series letter.
    'Β 1, 14', 'Β 8, 30; 10, 6', 'Α 92 I 307, 3',
    // Greek word plus a cross-reference.
    'τὴν μεσότητα vgl. 47 B 2', 'τῶν πέντε s. B 11', 'n. σελήνην, vgl. 28 B 21.',
  ],
  date: [
    '504—501', '428', '442/1', '504—1', '460ʼ', '± 380—370', '431 ?', 'Ol. 79, 3 =462/1', 'ol. 78, 3 = 466',
    'Ol. 94, 1. 404', 'aufgeführt 410—8', '438 ausgeführt', '28. Sept.', 'Mai 403', 'richtig Arm. 60,1 = 540',
  ],
  mark: ['?', '!', 'so', '5 Zeilen fehlen'],
  greek: [
    'φύσεως', 'sc. ῥήτορες', 'scil. πῦρ', 'καὶ', 'δ̇', 'ο>υχ <ο> μολογηθεν ⸏τα', 'ΑΡΙΣΤΟΤΕΛΟΥΣ', 'Etymologie v. ὑπερίων',
    'sollte heissen: διπλ. ἀπέχειν τὸν ἥλιον ἀπὸ τῆς γῆς ἤπερ τὴν σελήνην',
  ],
  gloss: [
    'sc. zodiaci', 'Isokrates', 'ARISTOT.', 'PLUT.', 'Anaxag.', 'd. i. Xenophanes', 'Thales, Anaximander, Anaximenes',
    'Bücherzahl fehlt', 'Bücherzahl?', 'animam esse dixerunt', 'aus Hesych', 'Scholion',
  ],
};

describe('classifyDkBracket — every survey shape', () => {
  for (const [cls, shapes] of Object.entries(cases)) {
    it.each(shapes)(`[%s] -> ${cls}`, (inner) => {
      expect(classifyDkBracket(inner)).toBe(cls);
    });
  }
});

describe('findEditionNotes', () => {
  it('finds only the edition references, brackets included', () => {
    const text = 'Ἀρίσταρχος [Ἀριστοτέλης Preller, fr. 190 Rose] καὶ [B 10] [sc. ῥήτορες] [504—501] Θεόπομπος [F GrHist. 115 F 72 II 550].';
    const notes = findEditionNotes(text);
    expect(notes.map((n) => n.text)).toEqual(['[Ἀριστοτέλης Preller, fr. 190 Rose]', '[F GrHist. 115 F 72 II 550]']);
    for (const n of notes) expect(text.slice(n.start, n.end)).toBe(n.text);
  });
  it('leaves a bracket that opens on one line and closes on the next in the text', () => {
    expect(findEditionNotes('καὶ [fr. 12 FHG')).toEqual([]);
    expect(findEditionNotes('II 272] καὶ')).toEqual([]);
  });
});

// A bracket that is its line's only content -- surrounding whitespace and
// one trailing "." or "," aside -- is the fragment's own source reference,
// not an interruption of running Greek, however the classifier reads its
// content (John, 2026-09-28). Real lines from the corpus (democritus-
// fragments): B39/B61's "[Stob. III 37, 25]." and B224's "[233 H.]".
describe('findEditionNotes — a bracket that is its whole line stays (John, 2026-09-28 ruling)', () => {
  it('leaves the bracket alone when nothing but it (and a trailing "." or ",") is on the line', () => {
    expect(findEditionNotes('[Stob. III 37, 25].')).toEqual([]);
    expect(findEditionNotes('[233 H.]')).toEqual([]);
    expect(findEditionNotes('[Stob. III 1, 95]')).toEqual([]);
    expect(findEditionNotes('[STOB. III 1, 27; s. B 187].')).toEqual([]);
    expect(findEditionNotes('[fr. 1 Us.],')).toEqual([]);
  });
  it('ignores surrounding whitespace', () => {
    expect(findEditionNotes('  [Stob. III 37, 25].  ')).toEqual([]);
    expect(findEditionNotes('\t[233 H.]')).toEqual([]);
  });
  it('still becomes a note once the line carries anything else', () => {
    expect(findEditionNotes('λόγος [Stob. III 37, 25].').map((n) => n.text)).toEqual(['[Stob. III 37, 25]']);
    expect(findEditionNotes('[Stob. III 37, 25]. καὶ').map((n) => n.text)).toEqual(['[Stob. III 37, 25]']);
    // Two trailing marks (not just one) no longer count as "nothing else".
    expect(findEditionNotes('[233 H.]..').map((n) => n.text)).toEqual(['[233 H.]']);
  });
  it('does not exempt a bracket classified crossref, date, mark, greek, or gloss -- they already stay regardless', () => {
    expect(findEditionNotes('[B 4].')).toEqual([]); // crossref, not via the exception
    expect(classifyDkBracket('B 4')).toBe('crossref');
  });
});

describe('numberEditionNotes', () => {
  const line1 = 'α [fr. 1 Us.] β [B 2] γ [II 3, 4]';
  const line2 = 'δ [p. 5 M.]';
  it('numbers one column from 1 in reading order, across its lines', () => {
    const notes = numberEditionNotes([line1, line2]);
    expect(notes).toEqual([
      { n: 1, text: '[fr. 1 Us.]', line: line1, start: line1.indexOf('[fr. 1 Us.]') },
      { n: 2, text: '[II 3, 4]', line: line1, start: line1.indexOf('[II 3, 4]') },
      { n: 3, text: '[p. 5 M.]', line: line2, start: line2.indexOf('[p. 5 M.]') },
    ]);
  });
  it('restarts at 1 for the next column', () => {
    // "α [fr. 9 Us.]", not the bracket alone -- a bracket that is its
    // line's whole content is exempted below and never numbered.
    expect(numberEditionNotes(['α [fr. 9 Us.]'])[0]!.n).toBe(1);
  });
  // GPT-6-Sol review, 2026-09-28: Empedocles testimonia A1 prints
  // "[fr. 27 FHG III 42]" twice, on two different lines -- these are two
  // notes, told apart by their (line, offset) identity, each with its own
  // number and its own print entry, not one number shown twice.
  it('gives the identical bracket printed twice in one column two separate numbers', () => {
    const dupLine1 = 'α [fr. 1 Us.] β [fr. 2 Us.]';
    const dupLine2 = 'γ [fr. 1 Us.]';
    const notes = numberEditionNotes([dupLine1, dupLine2]);
    expect(notes.map((n) => n.n)).toEqual([1, 2, 3]);
    expect(notes.map((n) => n.text)).toEqual(['[fr. 1 Us.]', '[fr. 2 Us.]', '[fr. 1 Us.]']);
    // The two same-text notes are distinguished by which line they sit on.
    expect(notes[0]!.line).toBe(dupLine1);
    expect(notes[2]!.line).toBe(dupLine2);
  });
  it('gives two identical brackets on the SAME line two separate numbers too', () => {
    const dup = 'α [fr. 1 Us.] β [fr. 1 Us.]';
    const notes = numberEditionNotes([dup]);
    expect(notes.map((n) => n.n)).toEqual([1, 2]);
    expect(notes[0]!.start).not.toBe(notes[1]!.start);
  });
});

describe('applyEditionNotes', () => {
  const text = 'Ἀρίσταρχος [fr. 1 Us.] καὶ λόγος';
  const tok = (t: string, k: string) => ({ kind: 'token' as const, text: t, tok: { t, o: text.indexOf(t), k } });
  // lineRenderParts' shape: tokens for Greek words, text atoms for the rest.
  const parts: LineRenderPart[] = [
    tok('Ἀρίσταρχος', 'a'), { kind: 'text', text: ' [fr' }, { kind: 'text', text: '. 1 Us.] ' },
    tok('καὶ', 'b'), { kind: 'text', text: ' ' }, tok('λόγος', 'c'),
  ];
  const numberFor = (span: { text: string }) => (span.text === '[fr. 1 Us.]' ? 1 : undefined);

  it('replaces the bracket, and the space before it, with one note part; every word stays a token', () => {
    const out = applyEditionNotes(text, parts, findEditionNotes(text), numberFor);
    // The word right before the bracket (parts[0], "Ἀρίσταρχος") is pulled
    // onto the note part's own `lead` rather than left as a separate
    // sibling -- Reader.svelte wraps `lead` + the marker in one
    // `white-space: nowrap` span so they can never split across a line.
    expect(out).toEqual([
      { kind: 'dknote', n: 1, text: '[fr. 1 Us.]', lead: parts[0] }, { kind: 'text', text: ' ' },
      parts[3], parts[4], parts[5],
    ]);
  });
  it('glues the note to the token right before it', () => {
    const out = applyEditionNotes(text, parts, findEditionNotes(text), numberFor);
    const note = out[0] as { kind: 'dknote'; lead?: unknown };
    expect(note.kind).toBe('dknote');
    expect(note.lead).toEqual(parts[0]);
  });
  it('carries no lead when nothing glueable precedes the note (line starts with it)', () => {
    const t = '[fr. 1 Us.] καὶ';
    const p: LineRenderPart[] = [
      { kind: 'text', text: '[fr. 1 Us.] ' },
      { kind: 'token', text: 'καὶ', tok: { t: 'καὶ', o: t.indexOf('καὶ'), k: 'b' } },
    ];
    const out = applyEditionNotes(t, p, findEditionNotes(t), () => 1);
    expect((out[0] as { kind: 'dknote'; lead?: unknown }).lead).toBeUndefined();
  });
  it('does not glue a speaker part as a lead (zero-width: no text of its own)', () => {
    const t = '[fr. 1 Us.] καὶ';
    const p: LineRenderPart[] = [
      { kind: 'speaker', label: 'X', dash: true },
      { kind: 'text', text: '[fr. 1 Us.] ' },
      { kind: 'token', text: 'καὶ', tok: { t: 'καὶ', o: t.indexOf('καὶ'), k: 'b' } },
    ];
    const out = applyEditionNotes(t, p, findEditionNotes(t), () => 1);
    expect(out[0]).toEqual(p[0]); // the speaker part passes through, untouched
    expect((out[1] as { kind: 'dknote'; lead?: unknown }).lead).toBeUndefined();
  });
  it('leaves the parts alone when there is no note or it cannot be numbered', () => {
    expect(applyEditionNotes(text, parts, [], numberFor)).toBe(parts);
    expect(applyEditionNotes(text, parts, findEditionNotes(text), () => undefined)).toBe(parts);
  });
  it('drops a Greek word inside the bracket from the line (the pop-up prints it), and glues the word before the bracket', () => {
    const t2 = 'α [fr. 577 aus d. Πολιτεία] β';
    const p2: LineRenderPart[] = [
      { kind: 'text', text: 'α [fr. 577 aus d. ' }, { kind: 'token', text: 'Πολιτεία', tok: { t: 'Πολιτεία', o: 18, k: 'x' } },
      { kind: 'text', text: '] β' },
    ];
    const out = applyEditionNotes(t2, p2, findEditionNotes(t2), () => 1);
    expect(out).toEqual([
      { kind: 'dknote', n: 1, text: '[fr. 577 aus d. Πολιτεία]', lead: { kind: 'text', text: 'α' } },
      { kind: 'text', text: ' β' },
    ]);
  });
  it('keeps a speaker part outside the note, but glues the link right before it', () => {
    const t3 = 'B 1 [p. 2 M.]';
    const p3 = [
      { kind: 'speaker' as const, label: 'X', dash: false },
      { kind: 'dklink' as const, text: 'B 1', href: '#col-B1' }, { kind: 'text' as const, text: ' [p. 2 M.]' },
    ];
    expect(applyEditionNotes(t3, p3, findEditionNotes(t3), () => 4)).toEqual([
      p3[0], { kind: 'dknote', n: 4, text: '[p. 2 M.]', lead: p3[1] },
    ]);
  });
  // GPT-6-Sol review, 2026-09-28: `numberFor` gets the span itself (start
  // included), not just its text -- so a caller can tell two identical
  // brackets apart by where they sit, as Reader.svelte's dkAnnotate does by
  // matching (line, start) against numberEditionNotes' recorded identity.
  it('numbers two identical-text spans on the same line differently when numberFor keys off span.start', () => {
    const t4 = 'α [fr. 1 Us.] β [fr. 1 Us.] γ';
    const p4: LineRenderPart[] = [{ kind: 'text', text: t4 }];
    const spans = findEditionNotes(t4);
    expect(spans).toHaveLength(2);
    const firstStart = spans[0]!.start;
    const numberFor = (span: { start: number; text: string }) => (span.start === firstStart ? 1 : 2);
    const out = applyEditionNotes(t4, p4, spans, numberFor);
    const notes = out.filter((p) => p.kind === 'dknote') as { n: number }[];
    expect(notes.map((n) => n.n)).toEqual([1, 2]);
  });
});
