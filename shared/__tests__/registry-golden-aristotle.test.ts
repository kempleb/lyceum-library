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
// The hash pins this corpus slice after each deliberate Aristotle data change.
// Other corpora can change without changing this value.
import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { AUTHORS } from '../lib/authors';
import { WORKS } from '../lib/works';
import { WORK_CORPUS_DATA } from '../lib/registry.generated';

describe('generated registry golden value -- Aristotle corpus slice only', () => {
  it('pins the Aristotle corpus works and authors', () => {
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
    expect(works.find((w) => w.id === 'Meta')?.translations[0].name)
      .toBe('W. D. Ross (Oxford, 1928)');
    expect(works.find((w) => w.id === 'GC')?.greekEdition)
      .toBe('Mugler, Aristote. De la génération et de la corruption (Les Belles Lettres, 1966)');

    const hash = createHash('sha256')
      .update(JSON.stringify(works) + JSON.stringify(authors))
      .digest('hex');

    // After a deliberate change to the Aristotle corpus's own registry data
    // (never after a change to some OTHER corpus, e.g. Plato — this slice
    // must not move for that), regenerate with this exact command from
    // shared/:
    // node --experimental-strip-types --input-type=module -e "import{createHash}from'node:crypto';import{CORPUS_WORKS as WORKS,CORPUS_AUTHORS as AUTHORS,WORK_CORPUS_DATA}from'./lib/registry.generated.ts';const ids=new Set(Object.entries(WORK_CORPUS_DATA).filter(([,c])=>c==='aristotle').map(([id])=>id));const works=WORKS.filter(w=>ids.has(w.id));const authorIds=new Set(works.map(w=>w.author));const authors=AUTHORS.filter(a=>authorIds.has(a.id));console.log(createHash('sha256').update(JSON.stringify(works)+JSON.stringify(authors)).digest('hex'))"
    expect(hash).toBe('3956ad23f0a6b1e89e5b618bd3b2ba4aa6f80ff40a3125c1128bba95c8ef4fe3');
  });
});
