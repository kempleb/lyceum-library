import { describe, expect, it } from 'vitest';
// @ts-expect-error The production generator is a plain .mjs module.
import * as routeRegistry from '../../scripts/build-route-registry.mjs';
import {
  CORPUS_AUTHORS,
  CORPUS_WORKS,
  WORK_CORPUS_DATA,
} from '../lib/registry.generated';

const {
  checkAbbrUniqueness,
  checkCaseInsensitiveWorkIds,
  checkDuplicateRoutes,
  checkReservedSegments,
  checkRouteRegistry,
  scanReservedSegments,
} = routeRegistry;

describe('route registry collision gates', () => {
  it('reports an injected duplicate route', () => {
    const problems = checkDuplicateRoutes([
      { route: '/author/work', corpus: 'one', work: 'first' },
      { route: '/author/work', corpus: 'two', work: 'second' },
    ]);

    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain("duplicate route '/author/work'");
  });

  it("reports a reserved author id of 'search'", () => {
    const problems = checkReservedSegments([{ id: 'search' }], [], ['search']);

    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain("author id 'search'");
  });

  it("reports a case-insensitive work-id collision for 'en' and 'EN'", () => {
    const problems = checkCaseInsensitiveWorkIds([{ id: 'en' }, { id: 'EN' }]);

    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain("'en', 'EN'");
  });

  // Item 91c (John, 2026-09-23, refined same day): short titles are
  // distinguished by author -- the duplicate check compares author PLUS
  // title/abbr, so "Leg." from two different authors (a coming Plato work
  // vs. Cicero's De Legibus) is no longer a collision; "Leg." twice under
  // the SAME author still is.
  describe('checkAbbrUniqueness (item 91c: keyed on author + abbr)', () => {
    it('reports NO collision for the same abbr under two DIFFERENT authors', () => {
      const problems = checkAbbrUniqueness([
        { id: 'plato-laws', abbr: 'Leg.', author: 'plato' },
        { id: 'de-legibus', abbr: 'Leg.', author: 'cicero' },
      ]);

      expect(problems).toEqual([]);
    });

    it('reports a collision for the same abbr (case-insensitively) under the SAME author', () => {
      const problems = checkAbbrUniqueness([
        { id: 'work-a', abbr: 'Leg.', author: 'cicero' },
        { id: 'work-b', abbr: 'leg.', author: 'cicero' },
      ]);

      expect(problems).toHaveLength(1);
      expect(problems[0]).toContain("'Leg.'");
      expect(problems[0]).toContain('cicero');
      expect(problems[0]).toContain('work-a');
      expect(problems[0]).toContain('work-b');
    });

    it('still honors an ALLOWED_ABBR_COLLISIONS exception for a same-author pair', () => {
      const works = [
        { id: 'work-a', abbr: 'Leg.', author: 'cicero' },
        { id: 'work-b', abbr: 'leg.', author: 'cicero' },
      ];

      const problems = checkAbbrUniqueness(works, [
        { abbr: 'Leg.', workIds: ['work-a', 'work-b'] },
      ]);

      expect(problems).toEqual([]);
    });
  });

  it('accepts all 139 real routes', () => {
    const result = checkRouteRegistry({
      works: CORPUS_WORKS,
      authors: CORPUS_AUTHORS,
      workCorpus: WORK_CORPUS_DATA,
      reservedSegments: scanReservedSegments(),
    });

    expect(result.routes).toHaveLength(139);
    expect(result.problems).toEqual([]);
  });
});
