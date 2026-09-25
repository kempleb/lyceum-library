import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// The Parnassos Press translations of Gorgias' two complete speeches (B11
// Encomium of Helen, B11a Defense of Palamedes) are the only non-public-
// domain text this site carries: they ship under CC BY-NC-ND 4.0, whose
// attribution term binds. The credit shows per passage on the reading page
// (see shared/__tests__/reader-translation-credit.test.ts); it must ALSO
// appear on /attribution, with the licence named and linked.
//
// The attribution page is hand-written prose, not generated from the
// registry (no work-level licence field exists, and the credit lives in the
// per-chunk data the page never loads), so this test is what keeps the page
// from drifting away from the source of truth: sources/parnassos-gorgias/
// README.md's own required attribution string, and the manifest's declared
// licence URL. There is no precedent in this repo for rendering an .astro
// file under vitest (see toc-group-label.test.ts's note), so the assertions
// are made against the page source itself.
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
// Whitespace-normalized: the page's prose is line-wrapped, so a citation
// string spans several source lines.
const PAGE = readFileSync(join(REPO_ROOT, 'app/src/pages/attribution.astro'), 'utf8')
  .replace(/\s+/g, ' ');
const README = readFileSync(
  join(REPO_ROOT, 'sources/parnassos-gorgias/README.md'), 'utf8'
);
const MANIFEST = readFileSync(
  join(REPO_ROOT, 'manifests/gorgias-fragments.yaml'), 'utf8'
);

const LICENCE_URL = 'https://creativecommons.org/licenses/by-nc-nd/4.0/';

describe('/attribution carries the Parnassos Gorgias credit and licence', () => {
  it('names both translators, the volume, its editors, publisher and year', () => {
    for (const part of [
      'Jurgen R. Gatt',
      'George Alexander Gazis',
      'Stamatia Dova',
      'Phillip Mitsis',
      'Heather Reid',
      'Gorgias/Gorgias: The Sicilian Orator and the Platonic Dialogue',
      'S. Montgomery Ewegen',
      'Coleen P. Zoller',
      'Parnassos Press',
      '2022',
    ]) {
      expect(PAGE).toContain(part);
    }
  });

  it('names the licence and links its deed', () => {
    expect(PAGE).toContain('CC BY-NC-ND 4.0');
    expect(PAGE).toContain(LICENCE_URL);
  });

  it('uses the licence URL the vendored source and the manifest declare', () => {
    expect(README).toContain(LICENCE_URL);
    expect(MANIFEST).toContain(LICENCE_URL);
  });

  it('says the two speeches are not public domain, so the badge is not read as covering them', () => {
    expect(PAGE).toContain('Encomium of');
    expect(PAGE).toContain('Defense of Palamedes');
    // John's 2026-09-23 ruling dropped the section-wide "every translation
    // is public domain, with one exception" framing (a blanket claim), but
    // the speeches' own CC status must still be stated plainly -- in the
    // citation itself (John, 2026-09-25: no explanatory paragraph).
    expect(PAGE).toMatch(/Defense of Palamedes.{0,400}Licensed under CC BY-NC-ND 4\.0/);
    expect(PAGE).not.toContain('is United States public domain, with one exception');
  });
});

describe('/attribution carries the Bury Sextus credit for Gorgias B3', () => {
  it('names Bury, the Sextus passage and 1935, and does not call that credit public domain', () => {
    expect(PAGE).toContain('trans. R.&nbsp;G. Bury');
    expect(PAGE).toContain('Against the Logicians</em> I 65–87');
    expect(PAGE).toContain('1935');
    // The next paragraph credits Bury's pre-1931 Plato Loebs as United
    // States public domain, so the same regex on the whole PAGE matches
    // that sentence. This check is the Sextus credit alone.
    const start = PAGE.indexOf('Sextus Empiricus, <em>Against the Logicians</em>');
    const end = PAGE.indexOf('Where a testimonium quotes Plato');
    expect(PAGE.slice(start, end)).not.toMatch(/Bury.{0,300}public domain/i);
  });
});
