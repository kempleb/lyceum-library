import { describe, expect, it } from 'vitest';
import { buildDkSourceRows, contextSectionMarkerNumbers, headTextFaults } from '../lib/dk-layout';
import type { CitationHead, Segment } from '../lib/data';

const expansion = (author: string, title: string) => [{ verbatim: '', resolution: 'direct' as const,
  authorDisplay: author, work: { title, italic: true }, flags: [] }];
function fixture(): Segment {
  const text = 'ARIST. Metaph. A 3. SIMPL. Phys. 23 λόγος. AËT. I 3 (D. 283) λόγος.';
  const heads = ['ARIST. Metaph. A 3.', 'SIMPL. Phys. 23', 'AËT. I 3 (D. 283)'];
  const sources = [['Aristotle', 'Metaphysica'], ['Simplicius', 'in Physica'], ['Aëtius', 'Placita']];
  return { id: '1:A5', column: 'A5', greek: [{ n: -1, text, role: 'context', tokens: [] }],
    english: { text: 'Fragment translation.', notes: [], markers: [] },
    citationHeads: heads.map((head, i): CitationHead => ({ text: head, lineIndex: 0, line: -1,
      start: text.indexOf(head), end: text.indexOf(head) + head.length,
      expanded: expansion(sources[i]![0]!, sources[i]![1]!),
    })),
    contextEnglish: [
      { sourceAuthor: 'Aëtius', sourceWork: 'Placita', locus: 'I 3', status: 'translated', text: 'Aëtius text.' },
      { sourceAuthor: 'Aristotle', sourceWork: 'Metaphysics', locus: 'A 3', status: 'translated', text: 'Aristotle text.' },
    ],
  };
}

describe('pipeline-located DK source rows', () => {
  it('keeps pointer-only heads alone and aligns expansions and source English by author/work', () => {
    const seg = fixture(); const rows = buildDkSourceRows(seg);
    expect(rows).toHaveLength(3);
    expect(rows[0]!.items.map(i => i.kind)).toEqual(['source-head']);
    expect(rows[1]!.items.map(i => i.kind)).toEqual(['source-head', 'flow']);
    expect(rows.map(r => r.contextIndexes)).toEqual([[1], [], [0]]);
    expect(rows.map(r => r.ownsEnglish)).toEqual([false, true, false]);
    rows.forEach((r, i) => expect(r.head?.expanded).toBe(seg.citationHeads![i]!.expanded));
  });

  it('never peels editorial prose, Roman numbers, or bracket references', () => {
    const seg = fixture(); seg.citationHeads = []; seg.contextEnglish = [];
    seg.greek = [{ n: 1, role: 'context', text: 'XIV p. 645 EBENDA I 2 [B 40].', tokens: [] }];
    const rows = buildDkSourceRows(seg);
    expect(rows[0]!.items.map(i => i.kind)).toEqual(['flow']);
  });

  it('rejects stale locations and disambiguates repeated n with lineIndex', () => {
    const seg = fixture(); seg.citationHeads![1]!.start++;
    expect(() => buildDkSourceRows(seg)).toThrow('stale citation location');
    const sameN = fixture(); sameN.contextEnglish = [];
    sameN.greek.push({ n: -1, text: 'DIOG. II 22 λόγος.', role: 'context', tokens: [] });
    sameN.citationHeads!.push({ lineIndex: 1, line: -1, start: 0, end: 11, text: 'DIOG. II 22', expanded: expansion('Diogenes Laertius', 'Vitae Philosophorum') });
    expect(buildDkSourceRows(sameN)).toHaveLength(4);
  });

  it('rebases clickable tokens and anchors only the first prose paragraph', () => {
    const seg = fixture();
    seg.greek[0]!.tokens = [...seg.greek[0]!.text.matchAll(/λόγος/g)].map(m => ({ t: 'λόγος', k: 'logos', o: m.index }));
    const flows = buildDkSourceRows(seg).flatMap(r => r.items.filter(i => i.kind === 'flow'));
    expect(flows.map(i => i.anchor)).toEqual([true, false]);
    for (const f of flows) for (const l of f.prose.lines) for (const t of l.tokens) expect(l.text.slice(t.o, t.o + t.t.length)).toBe(t.t);
  });

  it('keeps verse lines and assigns fragment English to the source with the text run', () => {
    const seg = fixture(); seg.greek.push({ n: 1, role: 'text', text: 'λόγος', tokens: [] });
    const rows = buildDkSourceRows(seg, true);
    expect(rows[2]!.items.at(-1)?.kind).toBe('line');
    expect(rows.map(r => r.ownsEnglish)).toEqual([false, false, true]);
    expect(rows.flatMap(r => r.items).filter(i => i.kind === 'flow').every(i => !i.anchor)).toBe(true);
  });

  it('keeps unmatched context in an independent row for the C5 gate', () => {
    const seg = fixture(); seg.contextEnglish!.push({ sourceAuthor: 'Plato', sourceWork: 'Meno', locus: '1', status: 'desert' });
    const row = buildDkSourceRows(seg).at(-1)!;
    expect(row.head).toBeUndefined(); expect(row.contextIndexes).toEqual([2]); expect(row.items).toEqual([]);
  });

  it('breaks repeated-author ties in document order', () => {
    const seg = fixture(); seg.citationHeads![2]!.expanded = seg.citationHeads![0]!.expanded;
    seg.contextEnglish = [1, 2].map(i => ({ sourceAuthor: 'Aristotle', sourceWork: 'Metaphysics', locus: String(i), status: 'desert' }));
    expect(buildDkSourceRows(seg).map(r => r.contextIndexes)).toEqual([[0], [], [1]]);
  });

  // Heraclitus A12's shape: six Aëtius headings, English for the 2nd-5th only.
  function a12(): Segment {
    const heads = ['—II 20, 16 (D. 351)', '—22, 2 (D. 352)', '—24, 3 (D. 354)', '—27, 2 (D. 358)', '—28, 6 (D. 359)', '—29, 3'];
    const text = heads.map(h => `${h} λόγος.`).join(' ');
    let at = 0;
    const citationHeads = heads.map((h): CitationHead => {
      const start = text.indexOf(h, at); at = start + h.length;
      return { text: h, lineIndex: 0, line: -1, start, end: start + h.length, expanded: expansion('Aëtius', 'Placita') };
    });
    const span = (head: string, locus: string) => ({ sourceAuthor: 'Aëtius', sourceWork: 'Placita', locus, status: 'translated' as const, headText: head, text: locus });
    return { id: '1:A12', column: 'A12', greek: [{ n: -1, text, role: 'context', tokens: [] }],
      english: null, citationHeads,
      contextEnglish: [span(heads[1]!, '2.22'), span(heads[2]!, '2.24'), span(heads[3]!, '2.27'), span(heads[4]!, '2.28')] };
  }

  it('binds a span that names its heading to that heading, not to the first of its source', () => {
    const seg = a12(); const rows = buildDkSourceRows(seg);
    expect(rows.map(r => r.contextIndexes)).toEqual([[], [0], [1], [2], [3], []]);
    expect(headTextFaults(seg, rows)).toEqual([]);
    // Without headText the document-order rule would shift every span up one.
    for (const span of seg.contextEnglish!) delete span.headText;
    expect(buildDkSourceRows(seg).map(r => r.contextIndexes)).toEqual([[0], [1], [2], [3], [], []]);
  });

  it('gives spans without headText only the headings no named span took', () => {
    const seg = a12(); delete seg.contextEnglish![1]!.headText;
    const rows = buildDkSourceRows(seg);
    // The unnamed span takes the first free Aëtius heading (II 20, 16).
    expect(rows.map(r => r.contextIndexes)).toEqual([[1], [0], [], [2], [3], []]);
  });

  it('fails C10 on a headText no heading prints, and on two spans naming one heading', () => {
    const missing = a12(); missing.contextEnglish![0]!.headText = '—23, 1 (D. 352)';
    const missingRows = buildDkSourceRows(missing);
    expect(missingRows.at(-1)!.head).toBeUndefined();
    expect(headTextFaults(missing, missingRows)).toEqual(['contextEnglish[0] names heading "—23, 1 (D. 352)", which no heading in the column prints']);
    const twice = a12(); twice.contextEnglish![1]!.headText = twice.contextEnglish![0]!.headText;
    expect(headTextFaults(twice, buildDkSourceRows(twice))).toEqual([
      'contextEnglish[0] shares heading "—22, 2 (D. 352)" with another source passage',
      'contextEnglish[1] shares heading "—22, 2 (D. 352)" with another source passage',
    ]);
  });

  it.each(['wholeColumnVerbatim', 'sectionParagraphSplit'] as const)('retains %s section splits including Greek question marks', (flag) => {
    const seg = fixture(); seg.citationHeads = []; seg.contextEnglish = [];
    seg[flag] = true;
    seg.english = { text: '(1) One. (2) Two.', credit: { translator: 'Test', source: 'Test', year: 1900, license: 'Public domain' }, notes: [], markers: [] } as Segment['english'];
    seg.greek = [{ n: 1, role: flag === 'sectionParagraphSplit' ? 'text' : 'context', text: '(1) λόγος; (2) λόγος.', tokens: [] }];
    expect([...contextSectionMarkerNumbers(seg)!]).toEqual([1, 2]);
    expect(buildDkSourceRows(seg).flatMap(r => r.items.flatMap(i => i.kind === 'flow' ? [i.prose.sectionMarker] : []))).toEqual(['1', '2']);
  });
});
