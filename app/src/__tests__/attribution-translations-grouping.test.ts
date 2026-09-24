import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// John's ruling (2026-09-23) for the "English Translations" section of
// /attribution: group by author, only list BUILT works, show CC licence
// info next to a CC-licensed translation, and drop every blanket
// "all translations are US public domain" claim (the page previously
// claimed that for every listed translation except Gorgias B11/B11a, but
// also lists Smith's De Anima (1931) and Fyfe's Poetics (1932), whose
// licence string is "unverified" — not a public-domain claim).
//
// There's no precedent in this repo for rendering an .astro file under
// vitest (see parnassos-attribution.test.ts's note), so — like that test —
// these assertions read the page source directly: the raw source for
// structural/code checks (imports, which helpers drive the list), and a
// whitespace-normalized copy for prose checks (the source is line-wrapped).
const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const RAW = readFileSync(join(REPO_ROOT, 'app/src/pages/attribution.astro'), 'utf8');
const PAGE = RAW.replace(/\s+/g, ' ');

describe('/attribution English Translations: no blanket public-domain claim', () => {
  it('drops the section-wide "every translation is public domain" sentence', () => {
    expect(PAGE).not.toContain('is United States public domain, with one exception');
    expect(PAGE).not.toMatch(/Every translation listed above is/);
  });

  it('drops the stale Meditations-only lead paragraph and its blanket pre-1931 claim', () => {
    // The old lead paragraph named only the Meditations (stale — six works
    // now carry translations) and asserted a blanket "published well before
    // 1931" claim; other paragraphs in this section make narrower,
    // per-translation claims like this and are untouched, so match the
    // specific retired clause rather than the general phrase.
    expect(PAGE).not.toContain('published well before 1931');
    expect(PAGE).not.toMatch(/The <em>Meditations<\/em> carries two English translations/);
  });

  it('drops the "Public Domain (US)" badge from the English Translations h2', () => {
    // Scope to the English Translations heading, not the whole page (the
    // Greek Lexicon / Morphological Data headings keep their own badges).
    const h2Match = RAW.match(/<h2>\s*English Translations[\s\S]*?<\/h2>/);
    expect(h2Match).not.toBeNull();
    expect(h2Match![0]).not.toContain('Public Domain (US)');
  });
});

describe('/attribution English Translations: grouped by author, built works only', () => {
  it('drives the list off builtAuthors/builtWorksOf, not a flat WORKS.filter', () => {
    expect(RAW).toMatch(/import\s*\{[^}]*builtAuthors[^}]*\}\s*from\s*['"]\.\.\/lib\/built-works['"]/);
    expect(RAW).toContain('builtWorksOf');
    // The old flat listing iterated WORKS directly with no built-work gate —
    // that pattern must be gone now that unbuilt works must not appear.
    expect(RAW).not.toMatch(/\{WORKS\.filter\(\(w\)\s*=>\s*visibleTranslations\(w\)\.length > 0\)\.map/);
  });

  it('renders the author display name as the grouping heading', () => {
    expect(RAW).toMatch(/\.author\.name/);
  });
});

describe('/attribution English Translations: CC licence shown per translation', () => {
  it("renders a licence badge for a translation whose recorded license.status is 'cc'", () => {
    expect(RAW).toMatch(/license\?\.status === ['"]cc['"]/);
  });

  it('still names and links the one recorded CC translation (Gorgias B11/B11a, Parnassos Press)', () => {
    expect(PAGE).toContain('CC BY-NC-ND 4.0');
    expect(PAGE).toContain('https://creativecommons.org/licenses/by-nc-nd/4.0/');
  });
});

describe('/attribution English Translations: column-source CC note (Gorgias Fragments), h2 badge removed', () => {
  it('the section h2 carries no licence badge (the per-entry note replaces it)', () => {
    const h2Match = RAW.match(/<h2>\s*English Translations[\s\S]*?<\/h2>/);
    expect(h2Match).not.toBeNull();
    expect(h2Match![0]).not.toContain('licence-badge');
  });

  it('derives a per-work CC note from columnCcLicenses, not a hard-coded Gorgias string', () => {
    expect(RAW).toMatch(/import\s*\{\s*columnCcLicenses\s*\}\s*from\s*['"]\.\.\/lib\/column-cc-licenses['"]/);
    expect(RAW).toMatch(/columnCcLicenses\(w\.id\)/);
  });
});
