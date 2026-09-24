// LemmaPage.astro's citation-pill formatting (app/src/lib/lemma-instance.ts),
// extracted so the scheme-dispatch + sentinel-line handling is testable
// without an Astro render pass. Covers the Sol-review regression: hand-
// concatenation baked in Bekker's no-separator convention for every scheme
// (DK verse's dot separator got dropped: "B834" instead of "B8.34"), and a
// dk verse fragment's negative sentinel `n` (role='context' lines,
// stage1_greek._parse_fragments) rendered a garbled "B1-1" citation instead
// of being treated as "no line".
import { describe, expect, it } from 'vitest';
import { instHref, instLabel } from '../lib/lemma-instance';

describe('lemma-instance citation pills', () => {
  it('Bekker (unregistered work id defaults to bekker, per schemeFor): concatenates column+line with no separator', () => {
    // instHref isn't exercised here: workPath() throws for an unregistered
    // work id (by design — it's a caller-bug guard), and no bekker-scheme
    // work is registered in THIS repo (Aristotle lives in the sister
    // aristotle-reader repo). formatCite/formatLocValue dispatch through
    // schemeFor, which defaults an unregistered id to bekker (documented in
    // citation.ts), so instLabel alone still exercises the real regression:
    // bekker's own concatenation convention, undisturbed by the fix below.
    expect(instLabel('unregistered-bekker-work', ['1097a', 15, 'ἀγαθόν'])).toBe('1097a15');
  });

  it('book-section (de-officiis): drops the line entirely (no user-facing line axis)', () => {
    expect(instLabel('de-officiis', ['1.101', 4, 'honestum'])).toBe('1.101');
    const href = instHref('/base', 'de-officiis', 1, ['1.101', 4, 'honestum']);
    expect(href).toContain('loc=1.101');
    expect(href).not.toContain(':4');
  });

  it('DK verse (parmenides-fragments, citation.lines: true): dot-joins column and line — NOT "B834"', () => {
    expect(instLabel('parmenides-fragments', ['B8', 34, 'ἐόν'])).toBe('B8.34');
    const href = instHref('/base', 'parmenides-fragments', 1, ['B8', 34, 'ἐόν']);
    expect(href).toContain('loc=B8:34');
  });

  it('DK verse sentinel line (-1, role=\'context\' block): renders the bare column, not "B1-1"', () => {
    expect(instLabel('parmenides-fragments', ['B1', -1, 'μῦθος'])).toBe('B1');
    const href = instHref('/base', 'parmenides-fragments', 1, ['B1', -1, 'μῦθος']);
    // Exact assertion on the `loc` query value itself, not a substring check:
    // the reader address now legitimately contains "book-1" (see
    // shared/lib/works.ts's divisionId), so a blanket "-1"/"B1-1" substring
    // check would misfire on that segment while still letting the malformed
    // `loc=B1:-1` (documented as the regression in lemma-instance.ts) slip
    // through as a false pass.
    const loc = new URL(href, 'https://example.test').searchParams.get('loc');
    expect(loc).toBe('B1');
  });

  it('line-less DK fragment (heraclitus-fragments, no citation.lines): line is ignored regardless of sign', () => {
    expect(instLabel('heraclitus-fragments', ['B30', 5, 'κόσμον'])).toBe('B30');
    expect(instLabel('heraclitus-fragments', ['B30', -1, 'κόσμον'])).toBe('B30');
    const href = instHref('/base', 'heraclitus-fragments', 1, ['B30', 5, 'κόσμον']);
    expect(href).toContain('loc=B30');
  });
});
