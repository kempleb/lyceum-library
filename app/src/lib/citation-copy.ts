// The scheme descriptor for "…and exact {citeWord} citation." (Landing.astro's
// summary blurb, ReaderShell.astro's meta description) — a short name for
// the citation SYSTEM itself, distinct from shared/lib/citation.ts's
// unitNounFor (the plain unit noun: "page"/"section"/"fragment"/…). A
// dk/letter/book-section/verse-line work has no 19th-century scholar's-name
// scheme the way Bekker/Stephanus/Busse do, so its descriptor is the
// scheme's own noun instead ("Diels–Kranz", "letter", "book and section",
// "line"). Extracted into a plain module (rather than inline consts
// duplicated in both .astro files) so this scheme-dispatch logic is
// unit-testable without an Astro render pass — see lemma-instance.ts's doc
// comment for the same rationale.
//
// Bug this replaces (REVIEW-CHECKLIST item 34): both call sites had their own
// stephanus/busse/section-only map that silently fell back to 'Bekker' for
// every other scheme — every dk work, every letter work, and Lucretius all
// printed "…and exact Bekker citation."
import { schemeFor } from '@shared/lib/citation';
import { getWork } from '@shared/lib/works';

const CITE_DESCRIPTOR: Record<string, string> = {
  bekker: 'Bekker',
  busse: 'CAG',
  stephanus: 'Stephanus',
  'book-section': 'book and section',
  section: 'chapter',
  dk: 'Diels–Kranz',
  letter: 'letter',
  'verse-line': 'line',
  // Plotinus (planned): cited ennead.tractate.chapter — see unitNounFor's
  // ennead doc comment in citation.ts (finding 5, Sol review).
  ennead: 'Ennead',
};

export function citeDescriptorFor(work: string): string {
  const id = schemeFor(work).id;
  return CITE_DESCRIPTOR[id] ?? id;
}

// ReaderShell.astro's sidebar contents drawer (.toc-book-label /
// .toc-book-count): the noun for the drawer's top-level grouping row —
// "Book" by default, or the work's own registry `divisionNoun` ("Letter" for
// Seneca's Epistulae Morales, "Chapter" for De Providentia/De Constantia
// Sapientis, John's ruling 2026-09-12). This is distinct from unitNounFor's
// per-citation-unit noun ("section" for book-section, "page" for stephanus)
// — the drawer groups by book/letter/chapter, not by the unit cited inside
// it. Mirrors ReaderShell.astro's own `bookNoun` (used for the book-window
// prev/next aria-labels) and shared/lib/works.ts's `divisionId` (the URL) —
// all three read the same field, so none of them can disagree.
export function tocGroupNoun(work: string): 'Letter' | 'Chapter' | 'Book' {
  const noun = getWork(work)?.divisionNoun ?? 'book';
  return (noun.charAt(0).toUpperCase() + noun.slice(1)) as 'Letter' | 'Chapter' | 'Book';
}

// The drawer's per-row unit count ("21 pp.") is meaningless for
// letter-scheme works: a letter's `page` field is constant at the letter
// number rather than incrementing per section (see
// navChipsNeedFullSectionList's doc comment in shared/lib/citation.ts), so
// the count is always 1 and carries no information (John's ruling,
// REVIEW-CHECKLIST item 34, decision E). Every other scheme's count is
// real and stays.
export function tocGroupShowsCount(work: string): boolean {
  return schemeFor(work).id !== 'letter';
}

// verse-line's (Lucretius' De Rerum Natura) per-book/total outline count.
// Unlike every other scheme, verse-line has no chapters.json entries
// (continuous verse has no chapter axis) and no sections.json either
// (hasSections: false) — so Landing.astro's "N books, N lines." credit
// sentence and ReaderShell.astro's TOC drawer's per-book count can't source
// a real count from either file. Bug this fixes: commit 1798729 routed both
// call sites through `pageEntriesFor`/`chapters.length`, which is always 0
// for verse-line, printing a false "0 chapters"/"0 lines" everywhere.
//
// The real per-book tally already exists in the pipeline's own
// manifest.json (`books[].segments`) — read by the caller (Astro I/O; these
// two functions stay pure and file-I/O-free so they're testable without an
// Astro render pass, same rationale as citeDescriptorFor above).
export interface ManifestBookCount {
  readonly book: number;
  readonly segments: number;
}

// A single book's count, or null when the manifest has no record for it —
// the caller drops the count entirely rather than print a false zero
// (mirrors tocGroupShowsCount's letter-scheme treatment above).
export function verseLineBookLineCount(
  manifestBooks: readonly ManifestBookCount[],
  book: number,
): number | null {
  return manifestBooks.find((b) => b.book === book)?.segments ?? null;
}

// The work-wide total, for Landing's credit sentence. Null when the
// manifest is missing or empty, so the caller can drop the whole count
// instead of showing 0.
export function verseLineTotalLines(manifestBooks: readonly ManifestBookCount[]): number | null {
  if (manifestBooks.length === 0) return null;
  return manifestBooks.reduce((sum, b) => sum + b.segments, 0);
}
