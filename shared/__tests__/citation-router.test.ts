import { describe, expect, it } from 'vitest';

import { resolveCitation, isAmbiguous, type CitationIndex } from '../lib/citation-router';
import { schemeFor } from '../lib/citation';
import { WORKS } from '../lib/works';

// A literal fixture index modeling the REAL collision classes an Opus review
// (2026-08-28) found live in build/dist/citation-index.json — never the real
// generated file itself, but every span below is copied verbatim from it, so
// the fixture can't drift from what the corpus actually contains the way the
// old single-fake-collision ('5a') fixture did.
//
//   (a) Cross-scheme Bekker/Busse homograph: Aristotle's Categories (bekker)
//       and Porphyry's Isagoge (busse) both start their own pagination at
//       "1a" — two unrelated numbering systems that happen to print the same
//       column string. Also De Interpretatione (bekker) vs Isagoge (busse)
//       at "17a".
//   (b) Same-scheme split page: Posterior Analytics (bekker) ends 100a17,
//       Topics (bekker) begins 100a18 — both bekker, so line containment IS
//       a valid narrowing signal here, unlike (a).
//   (c) DK/Bekker homographs (the stage-2 guard): a DK citation typed with a
//       space between chapter and series letter ("22 b30") collapses,
//       whitespace stripped, to the exact string a Bekker bare column+line
//       citation uses. Real collisions: De Interpretatione 22b30 vs
//       Heraclitus DK 22 B30; Prior Analytics 28b8 vs Parmenides DK 28 B8;
//       Prior Analytics 31b17 vs Empedocles DK 31 B17.
const INDEX: CitationIndex = {
  '1094a': [{ work: 'EN', book: 1, lo: 1, hi: 28 }],
  '1a': [
    { work: 'Cat', book: 1, lo: 1, hi: 29 },
    { work: 'Isa', book: 1, lo: 3, hi: 23 },
  ],
  '17a': [
    { work: 'Int', book: 1, lo: 1, hi: 40 },
    { work: 'Isa', book: 1, lo: 1, hi: 26 },
  ],
  '100a': [
    { work: 'APo', book: 2, lo: 1, hi: 17 },
    { work: 'Top', book: 1, lo: 18, hi: 30 },
  ],
  '22b': [{ work: 'Int', book: 1, lo: 1, hi: 39 }],
  '28b': [{ work: 'APr', book: 1, lo: 1, hi: 39 }],
  '31b': [{ work: 'APr', book: 1, lo: 1, hi: 41 }],
};

describe('resolveCitation — accept list (docs/p3-plan.md Settled decision 5)', () => {
  it('resolves a bare Bekker column against the injected index', () => {
    expect(resolveCitation('1094a', { index: INDEX })).toEqual({
      workId: 'EN',
      column: '1094a',
      line: null,
      bookN: 1,
    });
  });

  it('resolves a bare Bekker column + line against the injected index', () => {
    expect(resolveCitation('1094a15', { index: INDEX })).toEqual({
      workId: 'EN',
      column: '1094a',
      line: 15,
      bookN: 1,
    });
  });

  it('resolves a work-qualified citation by abbreviation ("EN 1094a15")', () => {
    expect(resolveCitation('EN 1094a15', { index: INDEX })).toEqual({
      workId: 'EN',
      column: '1094a',
      line: 15,
      bookN: 1,
    });
  });

  it('resolves a work-qualified citation by full title ("Nicomachean Ethics 1094a")', () => {
    expect(resolveCitation('Nicomachean Ethics 1094a', { index: INDEX })).toEqual({
      workId: 'EN',
      column: '1094a',
      line: null,
      bookN: 1,
    });
  });

  it('tolerates an optional comma between a work qualifier and its locus ("Nicomachean Ethics, 1094a15")', () => {
    // Cheap coverage, not an alias table (queued separately, John-gated —
    // docs/p3-plan.md): this is punctuation around the SAME qualifier
    // string ("Nicomachean Ethics"), not a different spelling of it.
    expect(resolveCitation('Nicomachean Ethics, 1094a15', { index: INDEX })).toEqual({
      workId: 'EN',
      column: '1094a',
      line: 15,
      bookN: 1,
    });
  });

  it('resolves a DK full citation via the unchanged parseDkFullCitation path ("DK 22 B30")', () => {
    // The explicit "DK" prefix keeps the whitespace-collapsed form
    // ("dk22b30") from ever matching a bare bekker/busse column, so the
    // homograph guard below never fires here — this citation is
    // unambiguous by construction, exactly as it was before the guard.
    expect(resolveCitation('DK 22 B30', { index: INDEX })).toEqual({
      workId: 'heraclitus-fragments',
      column: 'B30',
      line: null,
      bookN: undefined,
    });
  });

  it('returns null for a string that is not a citation under any dispatch stage', () => {
    expect(resolveCitation('this is not a citation at all', { index: INDEX })).toBeNull();
  });

  it('contextWorkId fallback returns exactly what schemeFor(work).parseLocation returns today (BekkerJump parity)', () => {
    // 'lives' (Diogenes Laertius) is book-section-scheme, so "7.85" is
    // recognized only via the contextWorkId fallback — it matches no
    // work-qualifier prefix, no DK full-citation form, and no bare
    // bekker/busse column shape (no letter component), so stages 1-3 all
    // genuinely miss and this exercises stage 4 alone.
    const raw = '7.85';
    const direct = schemeFor('lives').parseLocation(raw);
    expect(direct).not.toBeNull();

    const result = resolveCitation(raw, { contextWorkId: 'lives', index: INDEX });
    expect(result).not.toBeNull();
    expect(isAmbiguous(result)).toBe(false);
    if (!result || isAmbiguous(result)) throw new Error('unreachable');

    expect(result.workId).toBe('lives');
    expect(result.column).toBe(direct!.column);
    expect(result.line).toBe(direct!.line);
  });

  it('stage 1/2 (work-qualified, DK) resolve without an injected index', () => {
    // The index is only ever consulted by stage 3 (bare column), by the
    // stage-2 homograph guard, and for bookN enrichment — a caller with no
    // index yet (e.g. before fetchCitationIndex resolves) still gets a
    // correct workId/column/line from the other three stages.
    const result = resolveCitation('EN 1094a15', {});
    expect(result).not.toBeNull();
    expect(isAmbiguous(result)).toBe(false);
    if (!result || isAmbiguous(result)) throw new Error('unreachable');
    expect(result.workId).toBe('EN');
    expect(result.column).toBe('1094a');
    expect(result.line).toBe(15);
    expect(result.bookN).toBeUndefined();
  });

  it('stage 2 (DK) resolves cleanly with no injected index — the homograph guard never fires without one', () => {
    const result = resolveCitation('22 b30', {});
    expect(result).not.toBeNull();
    expect(isAmbiguous(result)).toBe(false);
    if (!result || isAmbiguous(result)) throw new Error('unreachable');
    expect(result.workId).toBe('heraclitus-fragments');
    expect(result.column).toBe('B30');
  });

  it('stage 1 ambiguity is reachable when two different works share a qualifier (19 works are titled "Fragments")', () => {
    // Regression for the false comment this router shipped with ("no two
    // works in the registry share an abbr/slug/title today") — 19 works
    // are titled "Fragments" and 19 "Testimonia" (the DK collections), so
    // this IS reachable, and the longest-qualifier-tie branch already
    // handles it correctly.
    const result = resolveCitation('Fragments B1', {});
    expect(result).not.toBeNull();
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');

    const ids = result.candidates.map((c) => c.workId);
    expect(ids).toContain('heraclitus-fragments');
    expect(ids).toContain('parmenides-fragments');
    expect(result.candidates.every((c) => c.column === 'B1')).toBe(true);
  });

  it('a two-work "Leg." collision from DIFFERENT authors still resolves as an AmbiguousResolution naming both (item 91c: the registry gate now allows this cross-author collision, so the citation box must keep disambiguating it correctly rather than silently picking one) -- pinning test, this already passes: the router matches on qualifier text alone and has never looked at author', () => {
    // Two real works ('meditations'/marcus-aurelius, 'discourses'/epictetus)
    // both use the book-section scheme, so "3.2" parses for either. Their
    // abbrs are borrowed for the duration of this test only, and restored
    // in the finally block -- this module has no seam to inject a fixture
    // works list (WORKS is a hard top-level import, not an opts param). The
    // real registry already carries one live "Leg." (Cicero's De Legibus,
    // real abbr today, also book-section) -- it's moved out of the way for
    // the duration of the test too, so the collision under test stays a
    // clean two-work case instead of an (still-valid, but less legible)
    // three-way one.
    const med = WORKS.find((w) => w.id === 'meditations');
    const disc = WORKS.find((w) => w.id === 'discourses');
    const cicero = WORKS.find((w) => w.id === 'de-legibus');
    if (!med || !disc || !cicero) throw new Error('fixture works missing from the registry');
    const savedMedAbbr = med.abbr;
    const savedDiscAbbr = disc.abbr;
    const savedCiceroAbbr = cicero.abbr;
    med.abbr = 'Leg.';
    disc.abbr = 'Leg.';
    cicero.abbr = savedCiceroAbbr + '-moved-out-of-the-way';
    try {
      const result = resolveCitation('Leg. 3.2', {});
      expect(result).not.toBeNull();
      expect(isAmbiguous(result)).toBe(true);
      if (!isAmbiguous(result)) throw new Error('unreachable');

      const ids = result.candidates.map((c) => c.workId).sort();
      expect(ids).toEqual(['discourses', 'meditations']);
      expect(result.candidates.every((c) => c.column === '3.2')).toBe(true);
    } finally {
      med.abbr = savedMedAbbr;
      disc.abbr = savedDiscAbbr;
      cicero.abbr = savedCiceroAbbr;
    }
  });
});

describe('resolveCitation — DK/Bekker homograph guard (stage 2, Opus-review BLOCKER)', () => {
  it('"22 b30" is ambiguous: Heraclitus DK 22 B30 vs De Interpretatione 22b30', () => {
    const result = resolveCitation('22 b30', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates).toEqual([
      { workId: 'heraclitus-fragments', column: 'B30', line: null, bookN: undefined },
      { workId: 'Int', column: '22b', line: 30, bookN: 1 },
    ]);
  });

  it('"28 b8" is ambiguous: Parmenides DK 28 B8 vs Prior Analytics 28b8', () => {
    const result = resolveCitation('28 b8', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates).toEqual([
      { workId: 'parmenides-fragments', column: 'B8', line: null, bookN: undefined },
      { workId: 'APr', column: '28b', line: 8, bookN: 1 },
    ]);
  });

  it('"31 b17" is ambiguous: Empedocles DK 31 B17 vs Prior Analytics 31b17', () => {
    const result = resolveCitation('31 b17', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates).toEqual([
      { workId: 'empedocles-fragments', column: 'B17', line: null, bookN: undefined },
      { workId: 'APr', column: '31b', line: 17, bookN: 1 },
    ]);
  });

  it('an UNSPACED form ("22b30") never reaches the DK stage — it resolves as Bekker via the bare-column stage, unambiguously', () => {
    // A scholar who omits the space between chapter and series letter is
    // understood to mean Bekker page+line, not DK — DK_FULL_CITATION_RE
    // requires the whitespace, so parseDkFullCitation genuinely misses and
    // stage 3 (bare column) resolves this alone, same as any other bare
    // Bekker citation.
    const result = resolveCitation('22b30', { index: INDEX });
    expect(isAmbiguous(result)).toBe(false);
    expect(result).toEqual({ workId: 'Int', column: '22b', line: 30, bookN: 1 });
  });
});

describe('resolveCitation — rebuilt index fixture (Opus-review BLOCKER: real collision classes)', () => {
  it('re-ruled: bare "1a5" is AMBIGUOUS [Cat, Isa] — the old fixture omitted Categories and locked in a claim false live', () => {
    const result = resolveCitation('1a5', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');

    expect(result.candidates.map((c) => c.workId).sort()).toEqual(['Cat', 'Isa']);
    expect(result.candidates.every((c) => c.column === '1a' && c.line === 5)).toBe(true);

    // Candidates are sorted by registry order (the plan's tie-break for
    // PRESENTATION, never for silently picking a winner) — derive the
    // expected order from the real WORKS array rather than hardcoding it.
    const catOrder = WORKS.findIndex((w) => w.id === 'Cat');
    const isaOrder = WORKS.findIndex((w) => w.id === 'Isa');
    const expectedFirst = catOrder < isaOrder ? 'Cat' : 'Isa';
    expect(result.candidates[0].workId).toBe(expectedFirst);
  });

  it('same-scheme containment stays valid: "100a10" resolves to Posterior Analytics', () => {
    expect(resolveCitation('100a10', { index: INDEX })).toEqual({
      workId: 'APo',
      column: '100a',
      line: 10,
      bookN: 2,
    });
  });

  it('same-scheme containment stays valid: "100a20" resolves to Topics', () => {
    expect(resolveCitation('100a20', { index: INDEX })).toEqual({
      workId: 'Top',
      column: '100a',
      line: 20,
      bookN: 1,
    });
  });
});

describe('resolveCitation — cross-scheme containment ban (stage 3, Opus-review SHOULD-FIX)', () => {
  it('"1a25" stays ambiguous [Cat, Isa] even though the line falls inside Cat\'s span and outside Isa\'s export span', () => {
    // Line 25 is inside Categories' bekker span (1-29) but outside
    // Isagoge's busse export span (3-23) — a same-scheme containment check
    // would wrongly narrow this to Cat alone. Different schemes: no
    // narrowing, stays ambiguous.
    const result = resolveCitation('1a25', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates.map((c) => c.workId).sort()).toEqual(['Cat', 'Isa']);
  });

  it('"17a30" stays ambiguous [Int, Isa] across the bekker/busse scheme boundary', () => {
    // Line 30 is inside De Interpretatione's bekker span (1-40) but
    // outside Isagoge's busse export span (1-26).
    const result = resolveCitation('17a30', { index: INDEX });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates.map((c) => c.workId).sort()).toEqual(['Int', 'Isa']);
  });
});

describe('resolveCitation — Stephanus scheme (Plato mount, docs/p3-plan.md Settled decision 5 P4 precondition)', () => {
  // The bare-column grammar (digits + a single a-e side letter) matches a
  // Stephanus page+column exactly like a Bekker/Busse one — the precondition
  // recorded in docs/p3-plan.md for whoever mounts the first stephanus
  // corpus was that a Stephanus citation must never silently resolve as a
  // confident, WRONG Bekker/Busse hit. resolveFromIndex is scheme-generic
  // (it groups candidates by schemeFor(w).id, whatever that id is), so no
  // change to citation-router.ts itself was needed once the index actually
  // carries stephanus columns (scripts/build-citation-index.mjs's
  // INDEXED_SCHEMES) — this proves the dispatch as a whole.
  const STEPHANUS_INDEX: CitationIndex = {
    ...INDEX,
    '327a': [{ work: 'Republic', book: 1, lo: 1, hi: 10 }],
  };

  it('resolves a bare Stephanus column ("327a", the Republic\'s opening line) unambiguously', () => {
    expect(resolveCitation('327a', { index: STEPHANUS_INDEX })).toEqual({
      workId: 'Republic',
      column: '327a',
      line: null,
      bookN: 1,
    });
  });

  it('resolves a bare Stephanus column + line ("327a5")', () => {
    expect(resolveCitation('327a5', { index: STEPHANUS_INDEX })).toEqual({
      workId: 'Republic',
      column: '327a',
      line: 5,
      bookN: 1,
    });
  });

  it('resolves a work-qualified Stephanus citation by abbreviation ("Rep. 327a")', () => {
    expect(resolveCitation('Rep. 327a', { index: STEPHANUS_INDEX })).toEqual({
      workId: 'Republic',
      column: '327a',
      line: null,
      bookN: 1,
    });
  });

  it('a Stephanus column shared with a Bekker/Busse work\'s column is reported ambiguous, never a silent Bekker/Busse pick (the P4 failure mode)', () => {
    // "1a" is already a real Bekker/Busse collision in INDEX (Cat/Isa,
    // above) — adding a stephanus work at the same bare column must join
    // that ambiguity, not silently resolve to one of the other two.
    const index: CitationIndex = {
      ...INDEX,
      '1a': [...INDEX['1a'], { work: 'Republic', book: 1, lo: 1, hi: 5 }],
    };
    const result = resolveCitation('1a', { index });
    expect(isAmbiguous(result)).toBe(true);
    if (!isAmbiguous(result)) throw new Error('unreachable');
    expect(result.candidates.map((c) => c.workId).sort()).toEqual(['Cat', 'Isa', 'Republic']);
  });

  it('a Stephanus citation absent from the index is a genuine null, never a guess', () => {
    expect(resolveCitation('999e', { index: STEPHANUS_INDEX })).toBeNull();
  });
});
