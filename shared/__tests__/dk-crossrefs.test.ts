import { describe, expect, it, vi } from 'vitest';

// dk-crossrefs.ts's resolver leans on works.ts (workByDkCitation, workPath)
// only to compose an href -- mocked here with a tiny synthetic registry so
// the test stays independent of the real corpus (which chapter numbers
// land where can change), matching the mocking style citation.test.ts
// already uses for dk fixtures.
vi.mock('../lib/works', () => ({
  workByDkCitation: (dkChapter: number, series: 'A' | 'B') => {
    if (dkChapter === 22 && series === 'B') return { id: 'heraclitus-fragments' };
    if (dkChapter === 22 && series === 'A') return { id: 'heraclitus-testimonia' };
    if (dkChapter === 31 && series === 'B') return { id: 'empedocles-fragments' };
    if (dkChapter === 31 && series === 'A') return { id: 'empedocles-testimonia' };
    // 14 (Pythagoras) is deliberately absent: a noSeries chapter has no
    // (chapter, series) entry in the real DK_BY_CHAPTER_SERIES map either.
    return undefined;
  },
  workPath: (workId: string) => `/read/x/${workId}/text`,
}));

import { applyDkCrossRefs, dkCrossRefColumn, dkCrossRefWorkId, findDkCrossRefs, resolveDkCrossRef } from '../lib/dk-crossrefs';
import type { LineRenderPart } from '../lib/speakers';

describe('findDkCrossRefs — the ruling\'s own examples', () => {
  it('a bare series+number means this author\'s own chapter', () => {
    const refs = findDkCrossRefs('foo [B 10] bar');
    expect(refs).toEqual([{ start: 5, end: 9, chapter: undefined, kind: 'B', number: '10' }]);
    expect('foo [B 10] bar'.slice(refs[0]!.start, refs[0]!.end)).toBe('B 10');
  });

  it('a chapter number before the series letter names that chapter', () => {
    const refs = findDkCrossRefs('[31 B 17]');
    expect(refs).toEqual([{ start: 1, end: 8, chapter: 31, kind: 'B', number: '17' }]);
  });

  it('"vgl." chains two references, the second inheriting kind+chapter', () => {
    const refs = findDkCrossRefs('[vgl. B 91. 12]');
    expect(refs).toHaveLength(2);
    expect(refs[0]).toMatchObject({ chapter: undefined, kind: 'B', number: '91' });
    expect(refs[1]).toMatchObject({ chapter: undefined, kind: 'B', number: '12' });
    expect('[vgl. B 91. 12]'.slice(refs[0]!.start, refs[0]!.end)).toBe('B 91');
    expect('[vgl. B 91. 12]'.slice(refs[1]!.start, refs[1]!.end)).toBe('12');
  });

  it('a chained reference naming its own kind does not inherit the first\'s', () => {
    const refs = findDkCrossRefs('[31 A 69a. B 94]');
    expect(refs).toHaveLength(2);
    expect(refs[0]).toMatchObject({ chapter: 31, kind: 'A', number: '69a' });
    expect(refs[1]).toMatchObject({ chapter: 31, kind: 'B', number: '94' });
  });

  it('a chained reference with an explicit chapter carries a chapter that inherits', () => {
    const refs = findDkCrossRefs('[vgl. 22 B 13. 37]');
    expect(refs[0]).toMatchObject({ chapter: 22, kind: 'B', number: '13' });
    expect(refs[1]).toMatchObject({ chapter: 22, kind: 'B', number: '37' });
  });

  it('a chain step that is a whole fresh citation (new chapter AND kind) does not misread the chapter as the first ref\'s fragment number', () => {
    // Corpus case (protagoras-testimonia A26): "82 A 7" then a SEPARATE
    // "85 A 2" -- not chapter-82's own fragment "85".
    const text = '[s. 82 A 7. 85 A 2]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(2);
    expect(refs[0]).toMatchObject({ chapter: 82, kind: 'A', number: '7' });
    expect(refs[1]).toMatchObject({ chapter: 85, kind: 'A', number: '2' });
    expect(text.slice(refs[1]!.start, refs[1]!.end)).toBe('85 A 2');
  });

  it('a chain step\'s chapter/kind inherit from the PREVIOUS step, not always the first', () => {
    const refs = findDkCrossRefs('[vgl. 22 A 1. B 2. 3]');
    expect(refs).toHaveLength(3);
    expect(refs[0]).toMatchObject({ chapter: 22, kind: 'A', number: '1' });
    expect(refs[1]).toMatchObject({ chapter: 22, kind: 'B', number: '2' });
    expect(refs[2]).toMatchObject({ chapter: 22, kind: 'B', number: '3' });
  });

  it('a trailing locus number after a chain step\'s own number is not itself a further chapter', () => {
    // "33, 3 I 122, 26 ff." -- the comma means "33" is NOT followed by the
    // whitespace REF_RE's chapter-number grammar requires, so it is read as
    // a bare (inheriting) fragment number, and nothing past it chains.
    const text = '[vgl. A 32. 33, 3 I 122, 26 ff.]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(2);
    expect(refs[0]).toMatchObject({ chapter: undefined, kind: 'A', number: '32' });
    expect(refs[1]).toMatchObject({ chapter: undefined, kind: 'A', number: '33' });
    expect(text.slice(refs[1]!.start, refs[1]!.end)).toBe('33');
  });

  it('a stray lowercase volume numeral right after the number is never read as a suffix', () => {
    // Corpus case (empedocles-fragments B99): "A 86 i 302, 11ff" -- "i" is a
    // (mistranscribed lowercase) Roman volume numeral, page-locus text, not
    // a genuine DK suffix letter like "86a".
    const text = '[A 86 i 302, 11ff]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(refs[0]).toMatchObject({ chapter: undefined, kind: 'A', number: '86' });
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('A 86');
  });

  it('a bare series letter alone', () => {
    expect(findDkCrossRefs('[A 21]')[0]).toMatchObject({ chapter: undefined, kind: 'A', number: '21' });
  });

  it('a chapter number before A', () => {
    expect(findDkCrossRefs('[28 A 21]')[0]).toMatchObject({ chapter: 28, kind: 'A', number: '21' });
  });

  it('a trailing word after the reference is not part of the link', () => {
    const text = '[B 4 Ende]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 4');
  });

  it('a page/line locus after the reference is not part of the link', () => {
    const text = '[B 12 II 38, 8]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 12');
  });

  it('a stray leading space inside the bracket is not part of the link', () => {
    const text = '[ B 30]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 30');
  });

  it('the whole bracket is the reference, no separator needed', () => {
    expect(findDkCrossRefs('[B 1]')[0]).toMatchObject({ kind: 'B', number: '1' });
    expect(findDkCrossRefs('[B27]')[0]).toMatchObject({ kind: 'B', number: '27' });
  });
});

describe('findDkCrossRefs — connectors found in the corpus survey', () => {
  it('"s." (see)', () => {
    expect(findDkCrossRefs('[s. 82 A 30]')[0]).toMatchObject({ chapter: 82, kind: 'A', number: '30' });
  });
  it('"z." (zu/at)', () => {
    expect(findDkCrossRefs('[z. 28 A 5]')[0]).toMatchObject({ chapter: 28, kind: 'A', number: '5' });
  });
  it('"nach" (after)', () => {
    expect(findDkCrossRefs('[nach B 2]')[0]).toMatchObject({ chapter: undefined, kind: 'B', number: '2' });
  });
  it('"hinter" (behind)', () => {
    expect(findDkCrossRefs('[hinter 2 B 1]')[0]).toMatchObject({ chapter: 2, kind: 'B', number: '1' });
  });
  it('"folgt" (follows)', () => {
    expect(findDkCrossRefs('[folgt 1 A 12]')[0]).toMatchObject({ chapter: 1, kind: 'A', number: '12' });
  });
  it('"=" ', () => {
    expect(findDkCrossRefs('[= 21 A 46]')[0]).toMatchObject({ chapter: 21, kind: 'A', number: '46' });
  });
  it('a connector reached after unrelated leading prose links only what follows it', () => {
    const text = '[Emped., vgl. 31 A 6]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('31 A 6');
  });
  it('a clause after ";" (no connector needed) links', () => {
    const text = '[fr. 173 Us.; 68 A 9]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('68 A 9');
  });

  it('a named author gloss before an EXPLICIT chapter number links (corpus cases: empedocles-fragments B118, pythagoras-testimonia 8)', () => {
    const text1 = '[Heraklit, 22 B 20]';
    const refs1 = findDkCrossRefs(text1);
    expect(refs1).toHaveLength(1);
    expect(refs1[0]).toMatchObject({ chapter: 22, kind: 'B', number: '20' });
    expect(text1.slice(refs1[0]!.start, refs1[0]!.end)).toBe('22 B 20');

    const text2 = '[Pherekydes 7 A 1]';
    const refs2 = findDkCrossRefs(text2);
    expect(refs2).toHaveLength(1);
    expect(refs2[0]).toMatchObject({ chapter: 7, kind: 'A', number: '1' });
    expect(text2.slice(refs2[0]!.start, refs2[0]!.end)).toBe('7 A 1');
  });
});

describe('findDkCrossRefs — deliberately unmatched shapes (corpus survey)', () => {
  it('a bracket with no series letter at all is never a reference', () => {
    expect(findDkCrossRefs('[428]')).toEqual([]);
    expect(findDkCrossRefs('[500—497]')).toEqual([]);
    expect(findDkCrossRefs('[c. 76, 3]')).toEqual([]);
  });

  it('a Roman-numeral volume citation is not a chapter number', () => {
    expect(findDkCrossRefs('[XVII A 681 K.]')).toEqual([]);
  });

  it('a work title with no connector is not a cross-reference (Aristotle\'s own book-letter)', () => {
    expect(findDkCrossRefs('[de anima A 2. 405a 19]')).toEqual([]);
  });

  it('a bare name with no chapter number is still left unlinked -- the explicit chapter is what makes the corpus cases below different from "de anima A 2"', () => {
    expect(findDkCrossRefs('[Heraklit, B 20]')).toEqual([]);
    expect(findDkCrossRefs('[Pherekydes A 1]')).toEqual([]);
  });

  it('a Stephanus page+section (number before the letter, nothing after) is not a reference', () => {
    expect(findDkCrossRefs('[Soph. 237 A vgl. 258D]')).toEqual([]);
  });

  it('but a genuine "vgl." reference alongside such a citation still links', () => {
    const text = '[Soph. 237 A vgl. B 7]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 7');
  });

  it('a range names no single target and is entirely skipped', () => {
    expect(findDkCrossRefs('[B 78—81]')).toEqual([]);
    expect(findDkCrossRefs('[68 C 2—6]')).toEqual([]);
    expect(findDkCrossRefs('[68 B 298b—299h]')).toEqual([]);
    expect(findDkCrossRefs('[s. 60 A 1—5]')).toEqual([]);
  });

  it('a range does not suppress an unrelated reference elsewhere in the same bracket', () => {
    const text = '[540—537; Apollod. FGrHist. 244 F 68b II 1039. Vgl. B 8, 4]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 8');
  });

  it('a locus range after the reference\'s own number is just a trailing locus, not a range on the ref', () => {
    const text = '[B 17, 17—20]';
    const refs = findDkCrossRefs(text);
    expect(refs).toHaveLength(1);
    expect(text.slice(refs[0]!.start, refs[0]!.end)).toBe('B 17');
  });

  it('a number-before-letter Stephanus-style citation with nothing after is never matched', () => {
    expect(findDkCrossRefs('[127 B; vgl. A 11]').map((r) => `${r.kind}${r.number}`)).toEqual(['A11']);
  });
});

describe('dkCrossRefColumn / dkCrossRefWorkId', () => {
  it('composes the canonical DK column token', () => {
    expect(dkCrossRefColumn({ start: 0, end: 0, kind: 'B', number: '84a' })).toBe('B84a');
  });

  it('resolves a chapter-carrying reference regardless of the current work', () => {
    expect(dkCrossRefWorkId({ start: 0, end: 0, chapter: 31, kind: 'B', number: '17' }, undefined))
      .toBe('empedocles-fragments');
  });

  it('resolves a bare reference against the current chapter', () => {
    expect(dkCrossRefWorkId({ start: 0, end: 0, kind: 'A', number: '10' }, 22))
      .toBe('heraclitus-testimonia');
  });

  it('is undefined with no chapter available at all (bare reference, non-dk or unknown current work)', () => {
    expect(dkCrossRefWorkId({ start: 0, end: 0, kind: 'B', number: '10' }, undefined)).toBeUndefined();
  });

  it('is undefined for a \'C\' series (no C-series work in this library)', () => {
    expect(dkCrossRefWorkId({ start: 0, end: 0, chapter: 31, kind: 'C', number: '1' }, undefined)).toBeUndefined();
  });

  it('is undefined for a chapter with no (chapter, series) work at all', () => {
    expect(dkCrossRefWorkId({ start: 0, end: 0, chapter: 14, kind: 'A', number: '7' }, undefined)).toBeUndefined();
  });
});

describe('resolveDkCrossRef', () => {
  const ref = { start: 0, end: 0, chapter: 31, kind: 'B' as const, number: '17' };

  it('resolves to an href built from the segment\'s own DOM id (col-<column>), not the bare citation -- the same format scripts/emit-lyceum-manifest.mjs emits and scripts/check-links.mjs accepts, since a plain <a> has no runtime ?loc= fallback to lean on', () => {
    const hasColumn = (workId: string, column: string) => workId === 'empedocles-fragments' && column === 'B17';
    expect(resolveDkCrossRef(ref, undefined, hasColumn)).toEqual({
      workId: 'empedocles-fragments',
      column: 'B17',
      href: '/read/x/empedocles-fragments/text#col-B17',
    });
  });

  it('renders as plain text (null) when the column does not exist in that work', () => {
    const hasColumn = () => false;
    expect(resolveDkCrossRef(ref, undefined, hasColumn)).toBeNull();
  });

  it('renders as plain text (null) when the chapter/series names no work', () => {
    const unknownRef = { start: 0, end: 0, chapter: 999, kind: 'B' as const, number: '1' };
    expect(resolveDkCrossRef(unknownRef, undefined, () => true)).toBeNull();
  });

  it('resolves a bare reference against the current work\'s own chapter (self-link)', () => {
    const bare = { start: 0, end: 0, kind: 'B' as const, number: '6' };
    const hasColumn = (workId: string, column: string) => workId === 'heraclitus-fragments' && column === 'B6';
    expect(resolveDkCrossRef(bare, 22, hasColumn)?.workId).toBe('heraclitus-fragments');
  });
});

describe('applyDkCrossRefs', () => {
  it('leaves parts untouched when there are no spans', () => {
    const parts: LineRenderPart[] = [{ kind: 'text', text: 'plain' }];
    expect(applyDkCrossRefs('plain', parts, [])).toBe(parts);
  });

  it('wraps a resolved span inside a single text atom, keeping the rest as plain text', () => {
    const text = '[B 10] rest';
    const parts: LineRenderPart[] = [{ kind: 'text', text }];
    const out = applyDkCrossRefs(text, parts, [{ start: 1, end: 5, href: '/x#B10' }]);
    expect(out).toEqual([
      { kind: 'text', text: '[' },
      { kind: 'dklink', text: 'B 10', href: '/x#B10' },
      { kind: 'text', text: '] rest' },
    ]);
  });

  it('renders an unresolved span (href: null) as plain text', () => {
    const text = '[B 10]';
    const parts: LineRenderPart[] = [{ kind: 'text', text }];
    const out = applyDkCrossRefs(text, parts, [{ start: 1, end: 5, href: null }]);
    expect(out).toEqual([{ kind: 'text', text: '[' }, { kind: 'text', text: 'B 10' }, { kind: 'text', text: ']' }]);
  });

  it('a span straddling two adjacent atoms (a token boundary inside the reference) still links as one piece', () => {
    // "B" and "10" as separate non-lexical atoms either side of a literal
    // space -- lineRenderParts emits one atom per apparatus token/gap.
    const text = '[B 10]';
    const parts: LineRenderPart[] = [
      { kind: 'text', text: '[' },
      { kind: 'text', text: 'B' },
      { kind: 'text', text: ' ' },
      { kind: 'text', text: '10' },
      { kind: 'text', text: ']' },
    ];
    const out = applyDkCrossRefs(text, parts, [{ start: 1, end: 5, href: '/x#B10' }]);
    expect(out).toEqual([
      { kind: 'text', text: '[' },
      { kind: 'dklink', text: 'B 10', href: '/x#B10' },
      { kind: 'text', text: ']' },
    ]);
  });

  it('a token part (clickable Greek word) is never touched by a span', () => {
    const text = 'λόγος [B 1]';
    const tok = { t: 'λόγος', o: 0, k: 'lo/gos' };
    const parts: LineRenderPart[] = [
      { kind: 'token', text: 'λόγος', tok },
      { kind: 'text', text: ' [' },
      { kind: 'text', text: 'B 1' },
      { kind: 'text', text: ']' },
    ];
    const out = applyDkCrossRefs(text, parts, [{ start: 7, end: 10, href: '/x#B1' }]);
    expect(out[0]).toEqual({ kind: 'token', text: 'λόγος', tok });
    expect(out).toContainEqual({ kind: 'dklink', text: 'B 1', href: '/x#B1' });
  });

  it('a speaker lead-in part (zero-width) is passed through and does not shift the pointer', () => {
    const text = '[B 1]';
    const parts: LineRenderPart[] = [
      { kind: 'speaker', label: 'ΣΩ.', dash: false },
      { kind: 'text', text },
    ];
    const out = applyDkCrossRefs(text, parts, [{ start: 1, end: 4, href: '/x#B1' }]);
    expect(out[0]).toEqual({ kind: 'speaker', label: 'ΣΩ.', dash: false });
    expect(out.slice(1)).toEqual([
      { kind: 'text', text: '[' },
      { kind: 'dklink', text: 'B 1', href: '/x#B1' },
      { kind: 'text', text: ']' },
    ]);
  });

  it('two spans in the same line each link independently', () => {
    const text = '[B 1] and [B 2]';
    const parts: LineRenderPart[] = [{ kind: 'text', text }];
    const out = applyDkCrossRefs(text, parts, [
      { start: 1, end: 4, href: '/x#B1' },
      { start: 11, end: 14, href: '/x#B2' },
    ]);
    expect(out).toEqual([
      { kind: 'text', text: '[' },
      { kind: 'dklink', text: 'B 1', href: '/x#B1' },
      { kind: 'text', text: '] and [' },
      { kind: 'dklink', text: 'B 2', href: '/x#B2' },
      { kind: 'text', text: ']' },
    ]);
  });
});
