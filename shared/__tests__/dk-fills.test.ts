import { describe, expect, it } from 'vitest';
import type { DkFill } from '../lib/data';
import { applyDkFills, dkFillTitle, locateDkFills } from '../lib/dk-fills';
import { applyEditionNotes, findEditionNotes } from '../lib/dk-edition-notes';
import type { LineRenderPart } from '../lib/speakers';

// Filled DK abbreviations (John, 2026-09-29). The Greek is invented (letter
// names), never corpus text.
const LINE = 'ΠΗΓΗ 1, 2 ὡς λέγει ὁ ποιητής ‘ἄλφα ... ζῆτα’ καὶ τὰ λοιπά.';
const AT = LINE.indexOf('...');
const FILL: DkFill = { start: AT, end: AT + 3, text: 'βῆτα, γάμμα / δέλτα', kind: 'verse', abbrev: 'ἄλφα ... ζῆτα' };

// Render parts as lineRenderParts builds them: a token per Greek word, the
// rest plain text.
function parts(text: string): LineRenderPart[] {
  const out: LineRenderPart[] = [];
  let ptr = 0;
  for (const m of text.matchAll(/[\p{Script=Greek}]+/gu)) {
    if (m.index! > ptr) out.push({ kind: 'text', text: text.slice(ptr, m.index!) });
    out.push({ kind: 'token', text: m[0], tok: { t: m[0], o: m.index!, k: m[0] } });
    ptr = m.index! + m[0].length;
  }
  if (ptr < text.length) out.push({ kind: 'text', text: text.slice(ptr) });
  return out;
}
const shown = (ps: ReturnType<typeof applyDkFills>) => ps.map((p) => (p.kind === 'dkfill' ? `[${p.fill}]` : p.kind === 'speaker' ? '' : p.text)).join('');

describe('dkFillTitle', () => {
  it('uses John\'s wording, verses or text by kind', () => {
    expect(dkFillTitle(FILL)).toBe('DK prints only ἄλφα … ζῆτα; the full verses are the fragment’s own.');
    expect(dkFillTitle({ ...FILL, kind: 'prose' })).toBe('DK prints only ἄλφα … ζῆτα; the full text is the fragment’s own.');
    expect(dkFillTitle({ ...FILL, abbrev: '‘ἄλφα ... ζῆτα’' })).toBe('DK prints only ἄλφα … ζῆτα; the full verses are the fragment’s own.');
  });
});

describe('locateDkFills', () => {
  it('takes the fills of the line shown whole', () => {
    expect(locateDkFills(LINE, [{ line: LINE, fills: [FILL] }])).toEqual([FILL]);
  });

  it('finds a fill in a slice of its line by the characters around the "..."', () => {
    const cut = LINE.indexOf('ὡς');
    const slice = LINE.slice(cut);
    const [f] = locateDkFills(slice, [{ line: LINE, fills: [FILL] }]);
    expect(f).toEqual({ ...FILL, start: AT - cut, end: AT - cut + 3 });
    expect(slice.slice(f!.start, f!.end)).toBe('...');
  });

  it('places nothing where the "..." has other surroundings or too little of them', () => {
    expect(locateDkFills('ἄλλο τι ‘ἄλφα ... ἦτα’ καὶ τὰ λοιπά.', [{ line: LINE, fills: [FILL] }])).toEqual([]);
    expect(locateDkFills('α ... ζ', [{ line: LINE, fills: [FILL] }])).toEqual([]);
    expect(locateDkFills(LINE, [])).toEqual([]);
  });
});

describe('applyDkFills', () => {
  it('replaces the "..." with a fill part and keeps every other part', () => {
    const out = applyDkFills(LINE, parts(LINE), [FILL]);
    expect(shown(out)).toBe(LINE.replace('...', '[βῆτα, γάμμα / δέλτα]'));
    const fill = out.find((p) => p.kind === 'dkfill');
    expect(fill).toEqual({ kind: 'dkfill', text: '...', fill: FILL.text, title: dkFillTitle(FILL) });
    // Tokens pass through untouched, and the parts still spell the line.
    expect(out.filter((p) => p.kind === 'token')).toEqual(parts(LINE).filter((p) => p.kind === 'token'));
    expect(out.map((p) => (p.kind === 'speaker' ? '' : p.text)).join('')).toBe(LINE);
  });

  it('handles a "..." split across two text parts', () => {
    const split: LineRenderPart[] = parts(LINE).flatMap((p) =>
      p.kind === 'text' && p.text.includes('...') ? [{ kind: 'text', text: p.text.slice(0, 3) }, { kind: 'text', text: p.text.slice(3) }] : [p]);
    const out = applyDkFills(LINE, split, [FILL]);
    expect(shown(out)).toBe(LINE.replace('...', '[βῆτα, γάμμα / δέλτα]'));
    expect(out.filter((p) => p.kind === 'dkfill')).toHaveLength(1);
  });

  it('returns the parts unchanged with no fills', () => {
    const ps = parts(LINE);
    expect(applyDkFills(LINE, ps, [])).toBe(ps);
  });

  it('lets edition notes run after it on the same line', () => {
    const text = 'ὡς ‘ἄλφα ... ζῆτα’ [fr. 12 Us.] λέγει.';
    const at = text.indexOf('...');
    const fill = { ...FILL, start: at, end: at + 3 };
    const filled = applyDkFills(text, parts(text), [fill]);
    const out = applyEditionNotes(text, filled, findEditionNotes(text), () => 1);
    expect(out.filter((p) => p.kind === 'dkfill')).toHaveLength(1);
    expect(out.filter((p) => p.kind === 'dknote').map((p) => p.text)).toEqual(['[fr. 12 Us.]']);
  });
});
