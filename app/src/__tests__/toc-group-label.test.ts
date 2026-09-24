// ReaderShell.astro's sidebar contents drawer (.toc-book-label /
// .toc-book-count) — John's item-34 unit-label ruling, decision E: he saw
// the drawer open on /read/seneca/epistulae-morales/book-47 listing "Book 39 …
// Book 47 … Book 54", each with a meaningless "1 pp." (a letter's `page`
// field is constant at the letter number, not incrementing per section —
// see navChipsNeedFullSectionList's doc comment in shared/lib/citation.ts).
// tocGroupNoun/tocGroupShowsCount (app/src/lib/citation-copy.ts) are the
// pure logic ReaderShell.astro's two toc-book-label/toc-book-count sites
// both call; extracted so this is testable without an Astro render pass —
// see citation-copy.test.ts's doc comment for the same rationale.
//
// Finding 6 (Sol review): the four tests below only assert these two helpers
// in isolation, so ReaderShell.astro's own template could regress to a
// literal "Book 47 · 1 pp." (wrong variable, swapped label/count, a stray
// hardcoded string) and every one of them would still pass — none touch the
// .astro file at all. The right fix would render ReaderShell.astro itself
// (Astro's experimental Container API, `astro/container`) and assert on the
// DOM it produces. There is NO existing precedent for that in this repo:
// grepping every app/src/__tests__/*.test.ts file, none imports an .astro
// component or drives vitest through Astro's Vite plugin — this project's
// vitest.config only runs plain TS/Svelte through the default Vite pipeline.
// A spike confirmed why: Container API needs the Astro compiler processing
// .astro imports, which requires wiring `getViteConfig()` from 'astro/config'
// into vitest's config — an infrastructure change to the shared test config
// (affecting every app test, not just this file), out of this finding's
// blast radius as a "fix a hardcoded string" task.
//
// Second-best, done instead: a composition test below that reproduces the
// EXACT sequence ReaderShell.astro's TOC drawer runs — schemeFor ->
// pageEntriesFor (or the chapters array) -> nounForCount, composed the same
// way the template composes them — against realistic per-book data (Seneca's
// Epistle 47: 21 real sections, all sharing letter 47's constant `page`).
// This still won't catch a pure JSX typo (e.g. swapping which variable goes
// in .toc-book-label vs .toc-book-count), but it DOES catch a regression in
// the shared logic those template expressions call, which is what finding 3
// and finding 4 actually broke.
import { describe, expect, it } from 'vitest';
import { pageEntriesFor, nounForCount } from '@shared/lib/citation';
import { tocGroupNoun, tocGroupShowsCount } from '../lib/citation-copy';

describe('tocGroupNoun', () => {
  it('letter (Seneca Epistulae Morales): "Letter", not "Book"', () => {
    expect(tocGroupNoun('epistulae-morales')).toBe('Letter');
  });

  it('verse-line, genuine multi-book work (Lucretius De Rerum Natura, 6 books): "Book"', () => {
    expect(tocGroupNoun('de-rerum-natura')).toBe('Book');
  });

  it('chapter (Seneca De Providentia, a dialogue stored as PHI chapters): "Chapter", not "Book"', () => {
    expect(tocGroupNoun('de-providentia')).toBe('Chapter');
  });
});

describe('tocGroupShowsCount', () => {
  it('letter (Seneca Epistulae Morales): drops the count — always "1 pp.", no information', () => {
    expect(tocGroupShowsCount('epistulae-morales')).toBe(false);
  });

  it('verse-line, genuine multi-book work (Lucretius De Rerum Natura): keeps the count — real information', () => {
    expect(tocGroupShowsCount('de-rerum-natura')).toBe(true);
  });
});

// Composition test — see the file doc comment above for why this exists
// instead of an Astro render pass. Reproduces ReaderShell.astro's TOC drawer
// pipeline for a book-section work end to end: pageEntriesFor's dedup
// workaround feeding nounForCount's singular/plural choice, against a
// realistic per-book section list (finding 3 + finding 4, Sol review).
describe('ReaderShell.astro TOC drawer composition (pageEntriesFor -> nounForCount)', () => {
  it('book-section, 51 real sections all sharing one constant `page`: count is 51, not 1', () => {
    // Marcus Aurelius Meditations IV-shaped: 51 sections, `page` constant at
    // the book number (4) — the exact pipeline artifact that collapsed the
    // real bug (task #35).
    const sections = Array.from({ length: 51 }, (_, i) => ({ page: 4, column: `4.${i + 1}` }));
    const count = pageEntriesFor('book-section', sections).length;
    expect(count).toBe(51);
    expect(nounForCount('meditations', count)).toBe('sections');
  });

  it('book-section, a single-section book: count is 1 and the noun is singular, not "1 sections"', () => {
    const sections = [{ page: 9, column: '9.1' }];
    const count = pageEntriesFor('book-section', sections).length;
    expect(count).toBe(1);
    expect(nounForCount('meditations', count)).toBe('section');
  });

  it('stephanus (Plato-shaped, several sections sharing one real page): dedup is legitimate here, unlike book-section', () => {
    const sections = [
      { page: 17, column: '17a' },
      { page: 17, column: '17b' },
      { page: 18, column: '18a' },
    ];
    expect(pageEntriesFor('stephanus', sections)).toHaveLength(2);
  });
});
