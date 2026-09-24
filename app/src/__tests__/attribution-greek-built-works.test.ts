// attribution.astro's "Greek Text" list ran over the FULL WORKS registry, so
// every mounted corpus's works (Aristotle's 41 since P3, Plato's 36 while
// held) showed up there whether or not this build carries their data. The
// fix filters that list to built works only, via isBuilt()
// (app/src/lib/built-works.ts), the same predicate every other listing page
// in this repo uses. Sibling of attribution-built-works.test.ts, which covers
// the "English Translations" list on the same page.
//
// No render harness exists for .astro pages here (see
// parnassos-attribution.test.ts's note), so this asserts against the page's
// own source text, whitespace-normalized. The fix is a code-only predicate
// change -- John is deciding the rights wording separately -- so the test also
// pins the section's prose, which must not move.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const PAGE = readFileSync(join(REPO_ROOT, 'app/src/pages/attribution.astro'), 'utf8')
  .replace(/\s+/g, ' ');

describe('/attribution Greek Text section lists only built works', () => {
  it('imports isBuilt from built-works.ts', () => {
    expect(PAGE).toMatch(/import\s*\{[^}]*\bisBuilt\b[^}]*\}\s*from\s*['"]\.\.\/lib\/built-works['"]/);
  });

  it('the Greek edition list is filtered by isBuilt(w.id)', () => {
    expect(PAGE).toMatch(
      /WORKS\.filter\(\(w\) => isBuilt\(w\.id\)\)\.map\(\(w\) => \( <li><strong>\{w\.title\}<\/strong> — \{w\.greekSource\.full\}<\/li>/,
    );
  });

  it('no unfiltered WORKS.map remains on the page', () => {
    expect(PAGE).not.toMatch(/\bWORKS\.map\(/);
  });

  it('leaves the section prose unchanged', () => {
    expect(PAGE).toContain(
      "<h2>Greek Text</h2> <p> The Greek text of the Meditations follows A. S. L. Farquharson's edition; " +
        "the Discourses and Enchiridion follow Heinrich Schenkl's Teubner edition; the <em>Lives of Eminent " +
        "Philosophers</em> follows H. S. Long's Oxford Classical Text, all listed below. </p>",
    );
  });
});
