// citeDescriptorFor (app/src/lib/citation-copy.ts) drives Landing.astro's and
// ReaderShell.astro's "…and exact {citeWord} citation." sentence. Extracted
// so this scheme-dispatch logic is testable without an Astro render pass —
// see lemma-instance.test.ts's doc comment for the same rationale.
//
// Bug this replaces (REVIEW-CHECKLIST item 34): both call sites had their own
// stephanus/busse/section-only map that silently fell back to 'Bekker' for
// every scheme it didn't recognize — every dk work, every letter work, and
// Lucretius printed "…and exact Bekker citation."
import { describe, expect, it, vi } from 'vitest';
import { citeDescriptorFor, verseLineBookLineCount, verseLineTotalLines } from '../lib/citation-copy';

// Plotinus (ennead scheme) isn't in the real registry yet (planned addition
// — finding 5, Sol review) — schemeFor is mocked for this one case only, so
// citeDescriptorFor's ennead branch is exercised ahead of that work landing,
// same rationale as citation.test.ts's EnneadWork fixture.
vi.mock('@shared/lib/citation', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@shared/lib/citation')>();
  return {
    ...actual,
    schemeFor: (work: string) => (work === 'plotinus-enneads' ? { id: 'ennead' } : actual.schemeFor(work)),
  };
});

describe('citeDescriptorFor', () => {
  it('bekker (no bekker work registered yet — Aristotle lands later; schemeFor defaults an unregistered work to bekker)', () => {
    expect(citeDescriptorFor('unregistered-bekker-work')).toBe('Bekker');
  });

  it('flat section scheme (Epictetus Enchiridion): "chapter" (was already correct; guards against a regression)', () => {
    expect(citeDescriptorFor('enchiridion')).toBe('chapter');
  });

  it('dk (Heraclitus B-fragments): "Diels–Kranz", never the old "Bekker" fallback', () => {
    expect(citeDescriptorFor('heraclitus-fragments')).toBe('Diels–Kranz');
    expect(citeDescriptorFor('heraclitus-fragments')).not.toBe('Bekker');
  });

  it('dk (Heraclitus A-testimonia): also "Diels–Kranz" — the descriptor names the scheme, not the series', () => {
    expect(citeDescriptorFor('heraclitus-testimonia')).toBe('Diels–Kranz');
  });

  it('letter (Seneca Epistulae Morales): "letter", never "Bekker"', () => {
    expect(citeDescriptorFor('epistulae-morales')).toBe('letter');
    expect(citeDescriptorFor('epistulae-morales')).not.toBe('Bekker');
  });

  it('verse-line (Lucretius De Rerum Natura): "line", never "Bekker"', () => {
    expect(citeDescriptorFor('de-rerum-natura')).toBe('line');
    expect(citeDescriptorFor('de-rerum-natura')).not.toBe('Bekker');
  });

  it('book-section (Marcus Aurelius Meditations): "book and section", no dotted internal id', () => {
    expect(citeDescriptorFor('meditations')).toBe('book and section');
    expect(citeDescriptorFor('meditations')).not.toMatch(/\./);
  });

  it('ennead (Plotinus, planned): "Ennead", never falls through to the bare scheme id', () => {
    expect(citeDescriptorFor('plotinus-enneads')).toBe('Ennead');
    expect(citeDescriptorFor('plotinus-enneads')).not.toBe('ennead');
  });
});

// verseLineBookLineCount / verseLineTotalLines (Lucretius De Rerum Natura,
// verse-line scheme). Bug this replaces (commit 1798729): Landing.astro's
// credit sentence and ReaderShell.astro's TOC drawer both sourced their
// count from chapters.json/sections.json, which verse-line never populates
// (continuous verse has no chapter or section axis) — so both printed a
// false "0 chapters"/"0 lines" for every book instead of the real
// manifest.json-derived count.
describe('verseLineBookLineCount', () => {
  const manifestBooks = [
    { book: 1, segments: 1111 },
    { book: 2, segments: 1178 },
  ];

  it('returns the real per-book segment count from manifest.json, not zero', () => {
    // Pre-fix reproduction: the old call sites used chapters.json (always
    // empty for verse-line) and got `[].length === 0` — "0 lines" for a
    // book with 1111 real verse lines. This function must not repeat that.
    expect(verseLineBookLineCount(manifestBooks, 1)).toBe(1111);
    expect(verseLineBookLineCount(manifestBooks, 1)).not.toBe(0);
    expect(verseLineBookLineCount(manifestBooks, 2)).toBe(1178);
  });

  it('returns null (not 0) for a book missing from the manifest, so the caller can drop the count', () => {
    expect(verseLineBookLineCount(manifestBooks, 3)).toBeNull();
    expect(verseLineBookLineCount([], 1)).toBeNull();
  });
});

describe('verseLineTotalLines', () => {
  it('sums every book — the real total for Landing\'s "N books, N lines." sentence', () => {
    const manifestBooks = [
      { book: 1, segments: 1111 },
      { book: 2, segments: 1178 },
      { book: 3, segments: 1097 },
      { book: 4, segments: 1290 },
      { book: 5, segments: 1458 },
      { book: 6, segments: 1292 },
    ];
    expect(verseLineTotalLines(manifestBooks)).toBe(7426);
  });

  it('returns null (not 0) when the manifest is empty/missing, so the caller drops the count', () => {
    expect(verseLineTotalLines([])).toBeNull();
  });
});
