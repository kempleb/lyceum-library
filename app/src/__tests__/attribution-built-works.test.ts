// GPT-6 Sol code review item 3 (docs/todo/plato-mount.md, MAJOR, mechanical
// part only): attribution.astro's "English Translations" list ran over the
// FULL WORKS registry, so a held mounted corpus's works (e.g. Plato's 36
// dialogues, none built) showed up there with no page for a reader to
// actually find them on. The fix filters that list -- and the `hasPrivate`
// flag that gates the adjoining "local only" explainer sentence, since it
// must agree with what the (now-filtered) list actually shows -- to built
// works only, via isBuilt() (app/src/lib/built-works.ts), the same
// predicate every other listing page in this repo already uses.
//
// attribution.astro is hand-written prose with no render harness in this
// repo -- parnassos-attribution.test.ts's own note says there is no
// precedent here for rendering an .astro file under vitest -- so this test
// follows that file's established approach: assert against the page's own
// source text (whitespace-normalized) rather than executing it. This still
// fails before the fix (isBuilt is absent from both expressions) and passes
// after, so it is a real regression test, not a tautology: John's
// "Do NOT change any wording" instruction is what makes source-matching
// appropriate here rather than a smell -- the fix is a code-only predicate
// change, and prose the test doesn't look at is exactly what must NOT move.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const PAGE = readFileSync(join(REPO_ROOT, 'app/src/pages/attribution.astro'), 'utf8')
  .replace(/\s+/g, ' ');

describe('/attribution lists only built works, not every registered one', () => {
  it('imports isBuilt from built-works.ts', () => {
    expect(PAGE).toMatch(/import\s*\{[^}]*\bisBuilt\b[^}]*\}\s*from\s*['"]\.\.\/lib\/built-works['"]/);
  });

  // Since the author-grouped rework (John, 2026-09-23) the list is built from
  // builtAuthors()/builtWorksOf(), which apply the same isBuilt predicate;
  // what must never come back is a list over the raw WORKS registry.
  it('the translations list is drawn from built works only, never the raw WORKS registry', () => {
    expect(PAGE).toMatch(/builtWorksOf\(author\.id\)\.filter\(\(w\) => visibleTranslations\(w\)\.length > 0\)/);
    expect(PAGE).not.toMatch(/WORKS\.filter\(\(w\) => visibleTranslations\(w\)\.length > 0\)\.map/);
  });

  it('hasPrivate is scoped to built works too, so the "local only" explainer never outruns the visible list', () => {
    expect(PAGE).toMatch(
      /const hasPrivate = WORKS\.some\(\(w\) => isBuilt\(w\.id\) && visibleTranslations\(w\)\.some\(\(t\) => t\.private\)\);/,
    );
  });
});
