import { describe, expect, it } from 'vitest';
import { CORPUS_WORKS } from '../lib/registry.generated';

/**
 * `citation.proseIndent` declares which `indent(N)` level an edition uses for
 * an ORDINARY PARAGRAPH OPENING; anything deeper is quoted verse, and gets
 * verse treatment (its own line, a rebased inset, a hanging indent, space
 * above and below the run).
 *
 * The value is not cosmetic and it is not uniform across editions. The Greek
 * exports start at level 1; every Cicero export starts at 2 and has no level 1
 * at all. A wrong value here restyles a thousand prose paragraphs as verse --
 * the regression John caught on Tusculans 1.12, where dialogue turns ("Quid
 * tandem?", "Utrisque.") were rendering with verse spacing and a hanging
 * indent.
 *
 * These expectations are measured from the built data (the minimum `indent`
 * level present across each work's books). They are pinned here so that a
 * re-export which shifts an edition's levels fails loudly.
 */
const EXPECTED_PROSE_INDENT: Record<string, number> = {
  // Latin: Diogenes 4.7.2 exports, levels 2,4[,5][,7] -- no level 1 exists.
  'de-divinatione': 2,
  'de-finibus': 2,
  'de-legibus': 2,
  'de-officiis': 2,
  'tusculan-disputations': 2,
};

describe('citation.proseIndent (verse-vs-paragraph threshold)', () => {
  it('declares 2 for every Latin work whose export has no indent(1)', () => {
    for (const [id, expected] of Object.entries(EXPECTED_PROSE_INDENT)) {
      const work = CORPUS_WORKS.find((w) => w.id === id);
      expect(work, `${id} missing from the registry`).toBeTruthy();
      expect(work!.citation?.proseIndent, `${id} proseIndent`).toBe(expected);
    }
  });

  it('leaves the Greek lined works on the default of 1', () => {
    // These editions DO use indent(1) for paragraph openings, so declaring a
    // value would be wrong -- level 2 is genuine quoted verse there (Lives'
    // epigrams, Discourses' verse quotations).
    for (const id of ['lives', 'discourses', 'enchiridion']) {
      const work = CORPUS_WORKS.find((w) => w.id === id);
      expect(work, `${id} missing from the registry`).toBeTruthy();
      expect(work!.citation?.proseIndent ?? 1, `${id} proseIndent`).toBe(1);
    }
  });
});
