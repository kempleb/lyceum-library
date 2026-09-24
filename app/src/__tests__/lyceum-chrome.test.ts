// PUBLIC_LYCEUM_CHROME=1 has to reach EVERY page, not just the reader, the
// homepage and the Catalog: under the flag the whole origin wears one band and
// one name. Two claims are checked here.
//
// 1. siteNameFor — the single decision of which name a page prints. Extracted
//    from the pages so it is testable without an Astro render pass (same
//    rationale as citation-copy.test.ts).
// 2. No page still shows the OLD chrome unconditionally. The old header is
//    `<header class="simple-header">`; every file that still contains one must
//    also read the flag and render LyceumBand instead when it is on. A new page
//    copied from an old one fails this the moment it is added.
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { LYCEUM_SITE_NAME, SITE_NAME, siteNameFor } from '../lib/site';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..');

function astroFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    if (e.isDirectory()) return astroFiles(p);
    return e.name.endsWith('.astro') ? [p] : [];
  });
}

describe('siteNameFor', () => {
  it('prints the library name under the flag', () => {
    expect(siteNameFor(true)).toBe(LYCEUM_SITE_NAME);
    expect(LYCEUM_SITE_NAME).toBe('The Lyceum Reader');
  });

  it('leaves the flag-off site on its own name', () => {
    expect(siteNameFor(false)).toBe(SITE_NAME);
  });
});

describe('the flag reaches every page that has old chrome', () => {
  const withOldHeader = astroFiles(SRC)
    .filter((p) => readFileSync(p, 'utf-8').includes('class="simple-header"'))
    .map((p) => [p.slice(SRC.length), readFileSync(p, 'utf-8')] as const);

  it('finds the pages that carry the old header at all', () => {
    // Guards the sweep itself: a broken glob would make every case below pass
    // vacuously.
    expect(withOldHeader.length).toBeGreaterThan(5);
  });

  it.each(withOldHeader.map(([rel]) => rel))('%s branches on the flag', (rel) => {
    const src = withOldHeader.find(([r]) => r === rel)![1];
    expect(src).toContain("import.meta.env.PUBLIC_LYCEUM_CHROME === '1'");
    expect(src).toContain('LyceumBand');
    // The band comes first, the old header only in the else-branch.
    expect(src.indexOf('<LyceumBand')).toBeLessThan(src.indexOf('class="simple-header"'));
  });

  it.each(withOldHeader.map(([rel]) => rel))('%s prints one name, never both', (rel) => {
    const src = withOldHeader.find(([r]) => r === rel)![1];
    // SITE_NAME is reached only through siteNameFor now; a page that still
    // interpolates it directly would print the old name under the flag.
    expect(src).not.toMatch(/\bSITE_NAME\b/);
  });
});
