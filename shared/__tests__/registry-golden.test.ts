import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { AUTHORS } from '../lib/authors';
import { WORKS } from '../lib/works';

describe('generated registry golden value', () => {
  it('keeps the default corpus registry stable', () => {
    const hash = createHash('sha256')
      .update(JSON.stringify(WORKS) + JSON.stringify(AUTHORS))
      .digest('hex');

    // 103 -> 139 works, 29 -> 30 authors: the Plato mount (docs/todo/plato-mount.md)
    // -- 36 Thrasyllan works + 1 author, registered unconditionally in
    // build-registry.mjs exactly like the aristotle mount (the corpus's
    // mount.yaml `hold` flag gates only whether its text data is copied into
    // build/dist, not whether it is a registered work/author).
    expect(WORKS).toHaveLength(139);
    expect(AUTHORS).toHaveLength(30);
    // After a deliberate registry change, regenerate with this exact command from shared/:
    // node --experimental-strip-types --input-type=module -e "import{createHash}from'node:crypto';import{CORPUS_WORKS as WORKS,CORPUS_AUTHORS as AUTHORS}from'./lib/registry.generated.ts';console.log(createHash('sha256').update(JSON.stringify(WORKS)+JSON.stringify(AUTHORS)).digest('hex'))"
    // 2026-09-26: owner-approved TLG Greek-edition labels for 11 Aristotle works.
    // WORKS/AUTHORS membership and order unchanged.
    expect(hash).toBe('90712aea0d7e4dd0de791a551a8e483760ee2019a7ebbe650eea8eff8ca988f3');
  });
});
