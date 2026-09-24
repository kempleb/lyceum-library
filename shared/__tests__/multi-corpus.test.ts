import { describe, expect, it } from 'vitest';
import { AUTHORS, SCHOOL_LABEL, getAuthor } from '../lib/authors';
import { WORKS, getWork, workSlug } from '../lib/works';
import { WORK_CORPUS_DATA } from '../lib/registry.generated';
// @ts-expect-error The production generator is a plain .mjs module.
import * as routeRegistry from '../../scripts/build-route-registry.mjs';

const { checkAbbrUniqueness } = routeRegistry;

// WORK_CORPUS_DATA is generated with an exact-key literal type (one key per
// registered work id), so indexing it with a plain `string` (rather than one
// of its literal keys) needs an index-signature view of the same object.
const workCorpus: Record<string, string> = WORK_CORPUS_DATA;
const aristotleWorks = WORKS.filter((work) => workCorpus[work.id] === 'aristotle');
const platoWorks = WORKS.filter((work) => workCorpus[work.id] === 'plato');

describe('multi-corpus registry', () => {
  it('registers all three committed corpora and resolves every mounted-source author', () => {
    // 103 -> 139 works, 29 -> 30 authors: the Plato mount (docs/todo/plato-mount.md)
    // adds 36 Thrasyllan works + 1 author, registered unconditionally exactly
    // like the aristotle mount (mount.yaml's `hold` flag gates only the mount
    // step's text-data copy, not the registry entries).
    expect(WORKS).toHaveLength(139);
    expect(AUTHORS).toHaveLength(30);
    expect(aristotleWorks).toHaveLength(41);
    expect(platoWorks).toHaveLength(36);
    for (const work of aristotleWorks) expect(getAuthor(work.author), work.id).toBeDefined();
    for (const work of platoWorks) expect(getAuthor(work.author), work.id).toBeDefined();
  });

  it('keeps work ids unique without regard to case', () => {
    const folded = WORKS.map((work) => work.id.toLocaleLowerCase('en-US'));
    expect(new Set(folded).size).toBe(WORKS.length);
  });

  it('keeps slugs unique within each author', () => {
    const routes = WORKS.map(
      (work) => `${work.author}/${workSlug(work)}`.toLocaleLowerCase('en-US'),
    );
    expect(new Set(routes).size).toBe(WORKS.length);
  });

  // Review item 91c (John, 2026-09-23): a short title need only be unique
  // within its author; the build's own gate is the one checked here.
  it('keeps abbreviations unique within each author', () => {
    expect(checkAbbrUniqueness(WORKS)).toEqual([]);
  });

  it('maps every work id to exactly one corpus', () => {
    const workIds = WORKS.map((work) => work.id).sort();
    const mappedIds = Object.keys(WORK_CORPUS_DATA).sort();
    expect(mappedIds).toEqual(workIds);
    expect(mappedIds).toHaveLength(139);
    expect(new Set(Object.values(WORK_CORPUS_DATA))).toEqual(
      new Set(['classical', 'aristotle', 'plato']),
    );
  });

  it('keeps the Isagoge under Porphyry with Busse citations', () => {
    const isa = getWork('Isa');
    expect(isa?.author).toBe('porphyry');
    expect(isa?.citation).toEqual({ scheme: 'busse', hideLineNumbers: true });
  });

  it('links the Eudemian common books to the Nicomachean Ethics', () => {
    expect(getWork('EE')?.missingBooks?.linkWork).toBe('EN');
  });

  it('keeps all fourteen Metaphysics book labels, including distinct alphas', () => {
    expect(getWork('Meta')?.bookLabels).toEqual([
      'Α',
      'α',
      'Β',
      'Γ',
      'Δ',
      'Ε',
      'Ζ',
      'Η',
      'Θ',
      'Ι',
      'Κ',
      'Λ',
      'Μ',
      'Ν',
    ]);
  });

  // build-registry.mjs strips private:true translations from the vendored
  // aristotle registry before they ever reach WORKS unless PUBLIC_SHOW_PRIVATE
  // is set -- the generated module is a plain literal with no Vite
  // define-fold of its own, so this test process (env unset) must never see
  // one survive.
  it('carries no private translation in the default (public) build', () => {
    for (const work of WORKS) {
      for (const translation of work.translations) {
        expect(translation.private, `${work.id}/${translation.id}`).not.toBe(true);
      }
    }
  });

  it('classes Porphyry as late-antique and Neoplatonist, and Aristotle as Peripatetic', () => {
    const porphyry = getAuthor('porphyry');
    expect(porphyry?.period).toBe('late-antique');
    expect(porphyry?.schools).toEqual(['neoplatonist']);
    expect(SCHOOL_LABEL[porphyry!.schools[0]]).toBe('Neoplatonist');

    const aristotle = getAuthor('aristotle');
    expect(aristotle?.schools).toEqual(['peripatetic']);
    expect(SCHOOL_LABEL[aristotle!.schools[0]]).toBe('Peripatetic');
  });
});
