// GPT-6 Sol code review item 4 (docs/todo/plato-mount.md, MINOR): the
// whole-registry golden in registry-golden.test.ts pins ALL 139 works/30
// authors, so it necessarily changed the moment the Plato mount landed (103
// -> 139, etc.) — it cannot, by itself, prove that generalising
// build-registry.mjs's loader to handle more than one mountable corpus left
// the ALREADY-shipping Aristotle corpus's own data untouched. This is a
// second, narrower golden scoped to just Aristotle's 41-work corpus slice
// (WORK_CORPUS_DATA-tagged 'aristotle': Aristotle's own 40 works plus
// Porphyry's Isagoge, the one non-Aristotle-authored work the vendored
// corpus carries — see shared/lib/works.ts's workGroupsFor doc comment).
//
// The expected hash below was computed on main (commit dd9f213, before the
// Plato mount existed at all) with the exact same filter -- see the
// regeneration command -- and matches this branch's value byte for byte,
// proving the generalised loader is a pure refactor as far as Aristotle is
// concerned.
import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { AUTHORS } from '../lib/authors';
import { WORKS } from '../lib/works';
import { WORK_CORPUS_DATA } from '../lib/registry.generated';

describe('generated registry golden value -- Aristotle corpus slice only', () => {
  it('keeps the Aristotle corpus\'s own works/authors byte-identical to main (pre-Plato-mount)', () => {
    const aristotleIds = new Set(
      Object.entries(WORK_CORPUS_DATA as Record<string, string>)
        .filter(([, corpus]) => corpus === 'aristotle')
        .map(([id]) => id),
    );
    const works = WORKS.filter((w) => aristotleIds.has(w.id));
    const authorIds = new Set(works.map((w) => w.author));
    const authors = AUTHORS.filter((a) => authorIds.has(a.id));

    // Aristotle's 40 works + Porphyry's Isagoge = 41; the two authors those
    // 41 works name.
    expect(works).toHaveLength(41);
    expect(authors).toHaveLength(2);

    const hash = createHash('sha256')
      .update(JSON.stringify(works) + JSON.stringify(authors))
      .digest('hex');

    // After a deliberate change to the Aristotle corpus's own registry data
    // (never after a change to some OTHER corpus, e.g. Plato — this slice
    // must not move for that), regenerate with this exact command from
    // shared/:
    // node --experimental-strip-types --input-type=module -e "import{createHash}from'node:crypto';import{CORPUS_WORKS as WORKS,CORPUS_AUTHORS as AUTHORS,WORK_CORPUS_DATA}from'./lib/registry.generated.ts';const ids=new Set(Object.entries(WORK_CORPUS_DATA).filter(([,c])=>c==='aristotle').map(([id])=>id));const works=WORKS.filter(w=>ids.has(w.id));const authorIds=new Set(works.map(w=>w.author));const authors=AUTHORS.filter(a=>authorIds.has(a.id));console.log(createHash('sha256').update(JSON.stringify(works)+JSON.stringify(authors)).digest('hex'))"
    expect(hash).toBe('bf394f2c28b5493609b57d67cff9e767e01617acc2f86792b8aa8b7bbbc08617');
  });
});
