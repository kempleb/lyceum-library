import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';
import { getAuthor } from '../lib/authors';
import { getWork, workPath } from '../lib/works';

// The emitter is a plain .mjs module with no declaration file; the
// directive must sit on the line the checker flags (the specifier).
import {
  toLyceumManifest,
  validateAgainstSchema,
  yearFromName,
  alignmentGrain,
  buildIndex,
  buildNavigation,
  validateNavigationSemantics,
  // @ts-expect-error untyped .mjs module
} from '../../scripts/emit-lyceum-manifest.mjs';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SCHEMA = JSON.parse(
  readFileSync(join(REPO_ROOT, 'schemas', 'lyceum-manifest.v1.json'), 'utf8'),
);

function expectValid(doc: unknown) {
  const errors = validateAgainstSchema(doc, SCHEMA);
  expect(errors).toEqual([]);
}

// Shaped on app/public/data/enchiridion/manifest.json (section, one book).
// Tests below both add a `name` to and `delete` this field on the first
// edition/translation, so the fixture's inferred literal type (name absent,
// property required) must be widened at the point of use.
type ManifestLicense = { status: string; name?: string } | undefined;

const ENCHIRIDION_MANIFEST = {
  schema_version: 'manifest.v1',
  id: 'enchiridion',
  author: 'epictetus',
  title: 'Enchiridion',
  language: 'grc',
  route: '/epictetus/enchiridion',
  citation: {
    scheme: 'section',
    books: [{ n: 1, start: '1', end: '53' }],
  },
  editions: [
    {
      language: 'grc',
      edition:
        'Schenkl, H. (ed.), Epicteti dissertationes ab Arriano digestae (Leipzig: Teubner, 1916, repr. 1965)',
      source: { kind: 'tlg', author: '0557', work: '002' },
      license: { status: 'unverified' } as ManifestLicense,
    },
  ],
  translations: [
    {
      id: 'oldfather',
      name: 'W. A. Oldfather (Loeb Classical Library, vol. II, 1928)',
      slot: 'primary',
      default: true,
      alignment: 'archive',
      license: { status: 'unverified' } as ManifestLicense,
    },
    {
      id: 'long',
      name: 'George Long (1877; Bell & Sons, 1890)',
      slot: 'secondary',
      default: false,
      alignment: 'archive',
      license: { status: 'unverified' },
    },
  ],
  apparatus: {
    footnotes: false,
    sidenotes: false,
    paratext: false,
    figures: false,
    sections: true,
    philosophers: false,
  },
  corpus_version: 'c5b8ecf-2026-09-01',
  books: [{ book: 1, segments: 53, first_column: '1', last_column: '53' }],
};

const ENCHIRIDION_WORK = {
  id: 'enchiridion',
  title: 'Enchiridion',
  greekTitle: 'Ἐγχειρίδιον',
  abbr: 'Ench.',
  author: 'epictetus',
  language: 'grc',
  translations: [
    {
      id: 'oldfather',
      name: 'W. A. Oldfather (Loeb Classical Library, vol. II, 1928)',
      short: 'Oldfather',
      slot: 'english',
    },
    {
      id: 'long',
      name: 'George Long (1877; Bell & Sons, 1890)',
      short: 'Long',
      slot: 'secondary',
    },
  ],
};

const EPICTETUS = {
  id: 'epictetus',
  name: 'Epictetus',
  nativeName: 'Ἐπίκτητος',
  floruit: 'c. AD 55–135',
};

// Shaped on app/public/data/meditations/manifest.json (book-section, 12 books).
const MEDITATIONS_MANIFEST = {
  schema_version: 'manifest.v1',
  id: 'meditations',
  author: 'marcus-aurelius',
  title: 'Meditations',
  language: 'grc',
  route: '/marcus-aurelius/meditations',
  citation: {
    scheme: 'book-section',
    books: [
      { n: 1, start: '1.1', end: '1.17' },
      { n: 2, start: '2.1', end: '2.17' },
      { n: 3, start: '3.1', end: '3.16' },
      { n: 4, start: '4.1', end: '4.51' },
      { n: 5, start: '5.1', end: '5.37' },
      { n: 6, start: '6.1', end: '6.59' },
      { n: 7, start: '7.1', end: '7.75' },
      { n: 8, start: '8.1', end: '8.61' },
      { n: 9, start: '9.1', end: '9.42' },
      { n: 10, start: '10.1', end: '10.38' },
      { n: 11, start: '11.1', end: '11.39' },
      { n: 12, start: '12.1', end: '12.36' },
    ],
  },
  editions: [
    {
      language: 'grc',
      edition:
        'Farquharson, A. S. L. (ed.), The Meditations of the Emperor Marcus Aurelius, vol. 1 (Oxford: Clarendon Press, 1944, repr. 1968)',
      source: { kind: 'tlg', author: '0562', work: '001' },
      license: { status: 'unverified' },
    },
  ],
  translations: [
    {
      id: 'haines',
      name: 'C. R. Haines (Loeb Classical Library, 1916)',
      slot: 'primary',
      default: true,
      alignment: 'archive',
      license: { status: 'public-domain-us' },
    },
    {
      id: 'long',
      name: 'George Long (1862)',
      slot: 'secondary',
      default: false,
      alignment: 'archive',
      license: { status: 'unverified' },
    },
  ],
  apparatus: {
    footnotes: false,
    sidenotes: false,
    paratext: false,
    figures: false,
    sections: true,
    philosophers: false,
  },
  corpus_version: 'c5b8ecf-2026-09-01',
  books: [
    { book: 1, segments: 17, first_column: '1.1', last_column: '1.17' },
    { book: 2, segments: 17, first_column: '2.1', last_column: '2.17' },
    { book: 3, segments: 16, first_column: '3.1', last_column: '3.16' },
    { book: 4, segments: 51, first_column: '4.1', last_column: '4.51' },
    { book: 5, segments: 37, first_column: '5.1', last_column: '5.37' },
    { book: 6, segments: 59, first_column: '6.1', last_column: '6.59' },
    { book: 7, segments: 75, first_column: '7.1', last_column: '7.75' },
    { book: 8, segments: 61, first_column: '8.1', last_column: '8.61' },
    { book: 9, segments: 42, first_column: '9.1', last_column: '9.42' },
    { book: 10, segments: 38, first_column: '10.1', last_column: '10.38' },
    { book: 11, segments: 39, first_column: '11.1', last_column: '11.39' },
    { book: 12, segments: 36, first_column: '12.1', last_column: '12.36' },
  ],
};

const MEDITATIONS_WORK = {
  id: 'meditations',
  title: 'Meditations',
  greekTitle: 'Τὰ εἰς ἑαυτόν',
  abbr: 'Med.',
  author: 'marcus-aurelius',
  language: 'grc',
  translations: [
    {
      id: 'haines',
      name: 'C. R. Haines (Loeb Classical Library, 1916)',
      short: 'Haines',
      slot: 'english',
    },
    {
      id: 'long',
      name: 'George Long (1862)',
      short: 'Long',
      slot: 'secondary',
    },
  ],
};

const MARCUS = {
  id: 'marcus-aurelius',
  name: 'Marcus Aurelius',
  nativeName: 'Μᾶρκος Αὐρήλιος',
  floruit: 'AD 121–180',
};

const DE_OFFICIIS_MANIFEST = {
  schema_version: 'manifest.v1',
  id: 'de-officiis',
  author: 'cicero',
  title: 'De Officiis',
  language: 'lat',
  route: '/cicero/de-officiis',
  citation: {
    scheme: 'book-section',
    books: [
      { n: 1, start: '1.1', end: '1.161' },
      { n: 2, start: '2.1', end: '2.90' },
      { n: 3, start: '3.1', end: '3.121' },
    ],
  },
  editions: [
    {
      language: 'lat',
      edition:
        'Atzert, C. (ed.), M. Tulli Ciceronis Scripta Quae Manserunt Omnia, Fasc. 48 (Leipzig: Teubner, 1932)',
      source: { kind: 'phi', author: '0474', work: '055' },
      license: { status: 'unverified' },
    },
  ],
  translations: [
    {
      id: 'miller',
      name: 'Walter Miller (Loeb Classical Library, 1913)',
      slot: 'primary',
      default: true,
      alignment: 'archive',
      license: { status: 'public-domain-us' },
    },
  ],
  apparatus: {
    footnotes: false,
    sidenotes: false,
    paratext: false,
    figures: false,
    sections: true,
    philosophers: false,
  },
  corpus_version: 'c5b8ecf-2026-09-01',
  books: [
    { book: 1, segments: 161, first_column: '1.1', last_column: '1.161' },
    { book: 2, segments: 90, first_column: '2.1', last_column: '2.90' },
    { book: 3, segments: 121, first_column: '3.1', last_column: '3.121' },
  ],
};

const DE_OFFICIIS_WORK = {
  id: 'de-officiis',
  title: 'De Officiis',
  abbr: 'Off.',
  author: 'cicero',
  language: 'lat',
  translations: [
    { id: 'miller', name: 'Walter Miller (Loeb Classical Library, 1913)', short: 'Miller', slot: 'english' },
  ],
};

const CICERO = {
  id: 'cicero',
  name: 'Cicero',
  nativeName: 'Marcus Tullius Cicero',
  floruit: '106–43 BC',
};

describe('toLyceumManifest', () => {
  it('maps the enchiridion (section, one book) fixture', () => {
    const out = toLyceumManifest(ENCHIRIDION_MANIFEST, ENCHIRIDION_WORK, EPICTETUS);

    expect(out.work).toBe('lyceum:epictetus.enchiridion');
    expect(out.author).toBe('Epictetus');
    expect(out.title).toBe('Enchiridion');
    expect(out.latin_title).toBe('Ἐγχειρίδιον');
    expect(out.language).toBe('grc');
    expect(out.date_label).toBe('c. AD 55–135');
    expect(out.route).toBe('/texts/epictetus/enchiridion/');
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/text');
    expect(out.citation).toEqual({
      scheme: 'section',
      ranges: ['1-53'],
      extent: '53 sections',
    });
    expect(out.editions).toEqual([
      {
        id: 'edition-0557-002',
        source:
          'Schenkl, H. (ed.), Epicteti dissertationes ab Arriano digestae (Leipzig: Teubner, 1916, repr. 1965)',
        license: 'TLG',
        verified: false,
      },
    ]);
    expect(out.translations).toEqual([
      {
        id: 'oldfather',
        label: 'Oldfather',
        date: 1928,
        rights: 'unverified',
        aligned: 'section',
        alignment_method: 'archive',
        default: true,
      },
      {
        id: 'long',
        label: 'Long',
        rights: 'unverified',
        aligned: 'section',
        alignment_method: 'archive',
        default: false,
      },
    ]);
    expect(out.apparatus).toEqual([
      { id: 'sections', label: 'Section numbers' },
      { id: 'search', label: 'Full-text search' },
      { id: 'lexicon', label: 'Greek dictionary lookup' },
    ]);
    expect(out.schema_version).toBe('1.0');
    expect(out.corpus_version).toBe('2026.09.01-c5b8ecf');
    expect(out.source_manifest).toBe('manifest.json');
    expect(out.generator).toBe('scripts/emit-lyceum-manifest.mjs');
    expect(Object.keys(out)).toEqual([
      'work',
      'author',
      'title',
      'latin_title',
      'language',
      'date_label',
      'route',
      'reading_route',
      'citation',
      'editions',
      'translations',
      'apparatus',
      'schema_version',
      'corpus_version',
      'source_manifest',
      'generator',
    ]);
    expectValid(out);
  });

  it('maps the meditations (book-section, multi-book) fixture', () => {
    const out = toLyceumManifest(MEDITATIONS_MANIFEST, MEDITATIONS_WORK, MARCUS);

    expect(out.work).toBe('lyceum:marcus-aurelius.meditations');
    expect(out.author).toBe('Marcus Aurelius');
    expect(out.latin_title).toBe('Τὰ εἰς ἑαυτόν');
    expect(out.language).toBe('grc');
    expect(out.date_label).toBe('AD 121–180');
    expect(out.route).toBe('/texts/marcus-aurelius/meditations/');
    expect(out.reading_route).toBe('/read/marcus-aurelius/meditations/book-1');
    expect(out.citation.scheme).toBe('book-section');
    expect(out.citation.ranges).toEqual([
      '1.1-1.17',
      '2.1-2.17',
      '3.1-3.16',
      '4.1-4.51',
      '5.1-5.37',
      '6.1-6.59',
      '7.1-7.75',
      '8.1-8.61',
      '9.1-9.42',
      '10.1-10.38',
      '11.1-11.39',
      '12.1-12.36',
    ]);
    expect(out.citation.extent).toBe('12 books · 488 sections');
    expect(out.editions[0]).toEqual({
      id: 'edition-0562-001',
      source:
        'Farquharson, A. S. L. (ed.), The Meditations of the Emperor Marcus Aurelius, vol. 1 (Oxford: Clarendon Press, 1944, repr. 1968)',
      license: 'TLG',
      verified: false,
    });
    expect(out.translations[0]).toEqual({
      id: 'haines',
      label: 'Haines',
      date: 1916,
      rights: 'Public Domain',
      aligned: 'section',
      alignment_method: 'archive',
      default: true,
    });
    expect(out.translations[1].date).toBe(1862);
    expect(out.translations[1].rights).toBe('unverified');
    expect(out.corpus_version).toBe('2026.09.01-c5b8ecf');
    expectValid(out);
  });

  it('maps lat → la, uses the Latin title, and labels the Latin lexicon', () => {
    const out = toLyceumManifest(DE_OFFICIIS_MANIFEST, DE_OFFICIIS_WORK, CICERO);

    expect(out.language).toBe('la');
    expect(out.latin_title).toBe('De Officiis');
    expect(out.work).toBe('lyceum:cicero.de-officiis');
    expect(out.route).toBe('/texts/cicero/de-officiis/');
    expect(out.editions[0].id).toBe('edition-0474-055');
    expect(out.editions[0].source).not.toMatch(/\b(TLG|PHI)\b/);
    expect(out.translations[0].rights).toBe('Public Domain');
    expect(out.editions[0].license).toBe('PHI');
    expect(out.translations[0].date).toBe(1913);
    expect(out.apparatus.at(-1)).toEqual({
      id: 'lexicon',
      label: 'Latin dictionary lookup',
    });
    expect(out.citation.extent).toBe('3 books · 372 sections');
    expectValid(out);
  });

  it('year heuristic: one 1500–2030 match → year; zero or two → null', () => {
    expect(yearFromName('W. A. Oldfather (Loeb Classical Library, vol. II, 1928)')).toBe(1928);
    expect(yearFromName('C. R. Haines (Loeb Classical Library, 1916)')).toBe(1916);
    expect(yearFromName('George Long (1862)')).toBe(1862);
    expect(yearFromName('George Long (1877; Bell & Sons, 1890)')).toBe(null);
    expect(yearFromName('Anonymous')).toBe(null);
    expect(yearFromName('Revised 1499 then 1910')).toBe(1910);
    expect(yearFromName('1910 and 1920 reprints')).toBe(null);

    const noYear = structuredClone(ENCHIRIDION_MANIFEST);
    noYear.translations = [
      {
        id: 'oldfather',
        name: 'W. A. Oldfather',
        slot: 'primary',
        default: true,
        alignment: 'archive',
        license: { status: 'unverified' },
      },
    ];
    const out = toLyceumManifest(noYear, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.translations[0].date).toBeUndefined();
    expectValid(out);
  });

  // John's edition-licence ruling (2026-09-22): editions[].license names the
  // digitization channel ("TLG"/"PHI") unless the edition carries a CC
  // licence instead; `verified` stays false for every edition regardless --
  // none of this is a public-domain claim.
  it('maps a tlg-source edition to "TLG", verified false', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.editions[0].source.kind = 'tlg';
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.editions[0].license).toBe('TLG');
    expect(out.editions[0].verified).toBe(false);
  });

  it('maps a phi-source edition to "PHI", verified false', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.editions[0].source.kind = 'phi';
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.editions[0].license).toBe('PHI');
    expect(out.editions[0].verified).toBe(false);
  });

  it('maps a cc-status license to its licence name regardless of source.kind, and requires that name', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.editions[0].license = { status: 'cc', name: 'CC BY-NC-ND 4.0' };
    const cc = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(cc.editions[0].license).toBe('CC BY-NC-ND 4.0');
    expect(cc.editions[0].verified).toBe(false);

    manifest.editions[0].license = { status: 'cc' };
    expect(() => toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS)).toThrow(/name/);
  });

  it('an edition license.status of public-domain-us does not change the TLG channel label or verified', () => {
    // John's edition-licence ruling (2026-09-22): editions[].license names
    // the digitization channel, never a public-domain claim -- so a
    // license.status of 'public-domain-us' on the edition is not read at
    // all; source.kind still drives the label, and verified stays false.
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.editions[0].source.kind = 'tlg';
    manifest.editions[0].license = { status: 'public-domain-us' };
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.editions[0].license).toBe('TLG');
    expect(out.editions[0].verified).toBe(false);
  });

  it('treats an unknown source.kind (or a missing one) as unverified, verified false, not a crash', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    delete manifest.editions[0].license;
    delete manifest.translations[0].license;
    manifest.editions[0].source.kind = 'whatever';
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.editions[0].license).toBe('unverified');
    expect(out.editions[0].verified).toBe(false);
    expect(out.translations[0].rights).toBe('unverified');
    expectValid(out);
  });

  it('derives work/route/reading_route from our manifest route, not from id or author casing (Aristotle EN)', () => {
    // Shaped on build/dist/EN/manifest.json: id 'EN' routes at
    // /aristotle/nicomachean-ethics (the registry `slug`, not the id
    // lowercased) -- the old id-lowercasing logic produced the dead address
    // /texts/aristotle/en/.
    const manifest = {
      ...ENCHIRIDION_MANIFEST,
      id: 'EN',
      author: 'aristotle',
      title: 'Nicomachean Ethics',
      route: '/aristotle/nicomachean-ethics',
    };
    const work = { ...ENCHIRIDION_WORK, id: 'EN', slug: 'nicomachean-ethics', author: 'aristotle' };
    const author = { id: 'aristotle', name: 'Aristotle', floruit: '384–322 BC' };
    const out = toLyceumManifest(manifest, work, author);
    expect(out.work).toBe('lyceum:aristotle.nicomachean-ethics');
    expect(out.route).toBe('/texts/aristotle/nicomachean-ethics/');
    expect(out.reading_route).toBe('/read/aristotle/nicomachean-ethics/text');
    expectValid(out);
  });

  it('throws when our manifest has no route or an unroutable shape', () => {
    const noRoute = { ...ENCHIRIDION_MANIFEST, route: undefined };
    expect(() => toLyceumManifest(noRoute, ENCHIRIDION_WORK, EPICTETUS)).toThrow(
      /missing input: manifest route/,
    );
    const badRoute = { ...ENCHIRIDION_MANIFEST, route: '/epictetus/enchiridion/extra' };
    expect(() => toLyceumManifest(badRoute, ENCHIRIDION_WORK, EPICTETUS)).toThrow(
      /not in \/<author>\/<work> form/,
    );
  });

  it('reads translator from the matching registry translation, defaulting to absent', () => {
    const workWithTranslator = {
      ...ENCHIRIDION_WORK,
      translations: [
        { ...ENCHIRIDION_WORK.translations[0], translator: 'W. A. Oldfather' },
        ENCHIRIDION_WORK.translations[1],
      ],
    };
    const out = toLyceumManifest(ENCHIRIDION_MANIFEST, workWithTranslator, EPICTETUS);
    expect(out.translations[0].translator).toBe('W. A. Oldfather');
    expect(out.translations[1].translator).toBeUndefined();
    expectValid(out);
  });

  it('throws on an unknown author and on a translation without id', () => {
    expect(() => toLyceumManifest(ENCHIRIDION_MANIFEST, ENCHIRIDION_WORK, null)).toThrow(
      /unknown author/,
    );
    const missingId = structuredClone(ENCHIRIDION_MANIFEST);
    delete (missingId.translations[0] as { id?: string }).id;
    expect(() => toLyceumManifest(missingId, ENCHIRIDION_WORK, EPICTETUS)).toThrow(
      /translation missing required id/,
    );
  });

  it('rejects a generated document that fails the partner schema', () => {
    const out = toLyceumManifest(ENCHIRIDION_MANIFEST, ENCHIRIDION_WORK, EPICTETUS);
    const broken = { ...out, route: '/Texts/Epictetus/Enchiridion' };
    const errors = validateAgainstSchema(broken, SCHEMA);
    expect(errors.some((error: { path: string }) => error.path === '/route')).toBe(true);
  });

  it('rejects an unsafe reading_route and a null corpus_version', () => {
    const out = toLyceumManifest(ENCHIRIDION_MANIFEST, ENCHIRIDION_WORK, EPICTETUS);

    const badRoute = { ...out, reading_route: 'javascript:alert(1)' };
    const routeErrors = validateAgainstSchema(badRoute, SCHEMA);
    expect(routeErrors.some((error: { path: string }) => error.path === '/reading_route')).toBe(true);

    const nullCorpusVersion = { ...out, corpus_version: null };
    const corpusErrors = validateAgainstSchema(nullCorpusVersion, SCHEMA);
    expect(corpusErrors.some((error: { path: string }) => error.path === '/corpus_version')).toBe(true);
  });
});

// reading_route always points at the real, always-built reader page
// (app/src/pages/read/[author]/[work]/[division].astro) -- the section-N
// alias (app/src/pages/read/_section-routes.ts) exists only for
// section-scheme works and is itself a forwarder INTO this page. The
// division segment depends only on the work's SHAPE (one book, i.e.
// bookless, vs. several) and its registry divisionNoun -- never on the
// citation scheme (John's ruling, 2026-09-12).
describe('reading_route grammar by work shape (division id)', () => {
  const bookishSchemes = ['section', 'book-section', 'bekker', 'stephanus', 'dk', 'verse-line', 'letter'];

  it.each(bookishSchemes)('a bookless work (one book) reads at /text regardless of scheme (%s)', (scheme) => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = { scheme, books: [{ n: 1, start: '1', end: '53' }] };
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/text');
    expectValid(out);
  });

  it('a multi-book work with no divisionNoun reads at /book-<n>', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = {
      scheme: 'book-section',
      books: [{ n: 1, start: '1.1', end: '1.9' }, { n: 2, start: '2.1', end: '2.9' }],
    };
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/book-1');
    expectValid(out);
  });

  it('a multi-book work with divisionNoun "letter" reads at /letter-<n> (Seneca Epistulae Morales shape)', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = {
      scheme: 'letter',
      books: [{ n: 1, start: '1.1', end: '1.9' }, { n: 2, start: '2.1', end: '2.9' }],
    };
    const work = { ...ENCHIRIDION_WORK, divisionNoun: 'letter' };
    const out = toLyceumManifest(manifest, work, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/letter-1');
    expectValid(out);
  });

  it('a multi-book work with divisionNoun "chapter" reads at /chapter-<n> (Seneca De Providentia shape)', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = {
      scheme: 'book-section',
      books: [{ n: 1, start: '1.1', end: '1.9' }, { n: 2, start: '2.1', end: '2.9' }],
    };
    const work = { ...ENCHIRIDION_WORK, divisionNoun: 'chapter' };
    const out = toLyceumManifest(manifest, work, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/chapter-1');
    expectValid(out);
  });

  // Bookless-ness is a REGISTRY fact (work.books === 1, same field
  // isBookless reads in shared/lib/works.ts), never the manifest's own
  // citation-book count -- a manifest that exports only its first citation
  // book (a partial/in-progress export) must not be misread as a one-book
  // work when the registry says otherwise. Un-guarded on build/dist: this
  // is a synthetic-manifest unit test, not a real-build cross-check.
  it('a manifest carrying only one citation book still reads at /letter-<n> when the registry says the work has many (partial Epistulae Morales export)', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = { scheme: 'letter', books: [{ n: 1, start: '1.1', end: '1.5' }] };
    const work = { ...ENCHIRIDION_WORK, divisionNoun: 'letter', books: 124 };
    const out = toLyceumManifest(manifest, work, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/letter-1');
    expectValid(out);
  });

  it('a manifest carrying two citation books still reads at /text when the registry says the work has exactly one book', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    manifest.citation = {
      scheme: 'section',
      books: [{ n: 1, start: '1', end: '30' }, { n: 2, start: '31', end: '53' }],
    };
    const work = { ...ENCHIRIDION_WORK, books: 1 };
    const out = toLyceumManifest(manifest, work, EPICTETUS);
    expect(out.reading_route).toBe('/read/epictetus/enchiridion/text');
    expectValid(out);
  });
});

describe('alignmentGrain', () => {
  it('maps citation schemes to the partner alignment-grain vocabulary', () => {
    expect(alignmentGrain('section')).toBe('section');
    expect(alignmentGrain('book-section')).toBe('section');
    expect(alignmentGrain('verse-line')).toBe('line');
    expect(alignmentGrain('bekker')).toBe('column');
    expect(alignmentGrain('stephanus')).toBe('column');
    expect(alignmentGrain('dk')).toBe('fragment');
    expect(alignmentGrain('letter')).toBe('letter');
    expect(alignmentGrain('unknown-scheme')).toBeNull();
    expect(alignmentGrain(null)).toBeNull();
  });
});

describe('translation aligned/alignment_method', () => {
  it('omits both keys when the translation carries no alignment value', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    delete (manifest.translations[0] as { alignment?: string }).alignment;
    const out = toLyceumManifest(manifest, ENCHIRIDION_WORK, EPICTETUS);
    expect(out.translations[0].aligned).toBeUndefined();
    expect(out.translations[0].alignment_method).toBeUndefined();
    expectValid(out);
  });
});

// The partner's real schema (schemas/lyceum-manifest.v1.json) types these
// fields as plain string/integer with no null variant -- null is a type
// violation there, not "absent". latin_title, translator, aligned and date
// are optional in that schema; alignment_method is an undeclared additive
// field it permits. In every case the fix is to omit the key rather than
// emit null (CONTRACT-GAP-REPORT.md).
describe('null fields are omitted, not emitted as null', () => {
  it('drops latin_title/translator/aligned/alignment_method/date when they would be null, and keeps default: false', () => {
    const manifest = structuredClone(ENCHIRIDION_MANIFEST);
    // 'long' already has no matching translator in the work registry and a
    // name that yields no single year (two 4-digit numbers) -- both already
    // null inputs; strip its alignment too so aligned/alignment_method join them.
    delete (manifest.translations[1] as { alignment?: string }).alignment;
    const work = { ...ENCHIRIDION_WORK };
    delete (work as { greekTitle?: string }).greekTitle;

    const out = toLyceumManifest(manifest, work, EPICTETUS);

    expect(Object.hasOwn(out, 'latin_title')).toBe(false);
    const long = out.translations[1];
    expect(Object.hasOwn(long, 'translator')).toBe(false);
    expect(Object.hasOwn(long, 'aligned')).toBe(false);
    expect(Object.hasOwn(long, 'alignment_method')).toBe(false);
    expect(Object.hasOwn(long, 'date')).toBe(false);
    expect(long.default).toBe(false);
    expectValid(out);
  });
});

const INDEX_ENTRY_A = {
  work: 'lyceum:b.beta',
  path: '/beta/manifest.lyceum.json',
  sha256: 'b'.repeat(64),
  corpus_version: '2026.09.01-c5b8ecf',
};

const INDEX_ENTRY_B = {
  work: 'lyceum:a.alpha',
  path: '/alpha/manifest.lyceum.json',
  sha256: 'a'.repeat(64),
  corpus_version: '2026.09.01-c5b8ecf',
};

describe('buildIndex', () => {
  it('sorts by work, strips trailing slashes from data_root, builds url, and keeps key order', () => {
    const index = buildIndex([INDEX_ENTRY_A, INDEX_ENTRY_B], 'https://data.example.com/root///');
    expect(Object.keys(index)).toEqual(['schema_version', 'corpus_version', 'data_root', 'manifests']);
    expect(index.schema_version).toBe('1.0');
    expect(index.corpus_version).toBe('2026.09.01-c5b8ecf');
    expect(index.data_root).toBe('https://data.example.com/root');
    expect(index.manifests.map((entry: { work: string }) => entry.work)).toEqual([
      'lyceum:a.alpha',
      'lyceum:b.beta',
    ]);
    expect(index.manifests[0]).toEqual({
      work: 'lyceum:a.alpha',
      path: '/alpha/manifest.lyceum.json',
      url: 'https://data.example.com/root/alpha/manifest.lyceum.json',
      sha256: 'a'.repeat(64),
    });
    expect(Object.keys(index.manifests[0])).toEqual(['work', 'path', 'url', 'sha256']);
  });

  it('sets url equal to path when data_root is null', () => {
    const index = buildIndex([INDEX_ENTRY_B], null);
    expect(index.data_root).toBeNull();
    expect(index.manifests[0].url).toBe(index.manifests[0].path);
    expect(index.manifests[0].url).toBe('/alpha/manifest.lyceum.json');
  });

  it('throws when entries have more than one distinct corpus_version', () => {
    expect(() =>
      buildIndex(
        [
          INDEX_ENTRY_B,
          { ...INDEX_ENTRY_A, corpus_version: '2026.09.02-deadbeef' },
        ],
        null,
      ),
    ).toThrow(/2026\.09\.01-c5b8ecf.*2026\.09\.02-deadbeef|2026\.09\.02-deadbeef.*2026\.09\.01-c5b8ecf/);
  });

  it('throws when entries is empty', () => {
    expect(() => buildIndex([], null)).toThrow();
  });
});

// Cross-check, item 3 of the division-id rollout: the emitter's own
// divisionIdFor (a plain-JS re-implementation, since there is no clean .mjs
// import of the TypeScript shared/lib/works.ts) must never drift from the
// real divisionId/workPath it mirrors. Runs against every work actually
// built in this checkout (build/dist/*/manifest.json) -- skipped entirely
// when that directory is absent (a clean checkout with no corpus data),
// same guard shape as app/src/__tests__/alias-routes.test.ts's real-data
// tests.
const DIST_DIR = join(REPO_ROOT, 'build', 'dist');

describe.skipIf(!existsSync(DIST_DIR))('reading_route cross-check against shared/lib/works.ts', () => {
  it('agrees with workPath(workId, firstBook) for every built work', () => {
    const dirs = readdirSync(DIST_DIR, { withFileTypes: true }).filter((d) => d.isDirectory());
    let checked = 0;
    for (const dir of dirs) {
      const manifestPath = join(DIST_DIR, dir.name, 'manifest.json');
      if (!existsSync(manifestPath)) continue;
      const ourManifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
      const work = getWork(ourManifest.id);
      if (!work) continue; // non-work dirs under build/dist (e.g. 'Top')
      const author = getAuthor(work.author);
      if (!author) continue;
      const lyceum = toLyceumManifest(ourManifest, work, author);
      const firstBook = ourManifest.citation?.books?.[0]?.n ?? 1;
      expect(lyceum.reading_route, `${ourManifest.id} reading_route`).toBe(workPath(work.id, firstBook));
      checked += 1;
    }
    expect(checked).toBeGreaterThan(0);
  });
});

// --- navigation (Lyceum partner "adaptive reading" contract, John and Opus,
// 2026-09-12) -----------------------------------------------------------
//
// buildNavigation reads columns.json + book-NN.json off a real work
// directory, so these fixtures write a small synthetic one per test (shaped
// on the real files -- see build/dist/EN/{columns,book-01}.json et al.) and
// clean it up afterwards, the same synthetic-but-realistic-shape approach as
// ENCHIRIDION_MANIFEST/MEDITATIONS_MANIFEST above.
const navFixtureDirs: string[] = [];

afterEach(() => {
  while (navFixtureDirs.length) {
    rmSync(navFixtureDirs.pop()!, { recursive: true, force: true });
  }
});

function makeNavFixture(
  columns: Record<string, Array<{ book: number; lo: number; hi: number }>>,
  books: Record<number, Array<{ column: string; n: number }>>,
): string {
  const dir = mkdtempSync(join(tmpdir(), 'lyceum-nav-'));
  navFixtureDirs.push(dir);
  writeFileSync(join(dir, 'columns.json'), JSON.stringify(columns));
  for (const [bookNum, segs] of Object.entries(books)) {
    const bookData = {
      book: Number(bookNum),
      segments: segs.map((seg, i) => ({
        id: `${bookNum}:${seg.column}:${i}`,
        column: seg.column,
        greek: [{ n: seg.n, text: 'placeholder', tokens: [] }],
      })),
    };
    writeFileSync(
      join(dir, `book-${String(bookNum).padStart(2, '0')}.json`),
      JSON.stringify(bookData),
    );
  }
  return dir;
}

describe('buildNavigation', () => {
  it('a split Bekker column: bare key on the first (lower) book, line-referenced key on its recurrence, both hrefs lowercase, both paths declared', () => {
    const dir = makeNavFixture(
      {
        '100a': [{ book: 1, lo: 1, hi: 10 }],
        '100b': [{ book: 1, lo: 1, hi: 10 }],
        '101A': [{ book: 1, lo: 1, hi: 5 }, { book: 2, lo: 6, hi: 20 }],
        '101b': [{ book: 2, lo: 1, hi: 10 }],
      },
      {
        1: [{ column: '100a', n: 1 }, { column: '100b', n: 1 }, { column: '101A', n: 1 }],
        2: [{ column: '101A', n: 6 }, { column: '101b', n: 1 }],
      },
    );
    const manifest = {
      citation: {
        scheme: 'bekker',
        books: [
          { n: 1, start: '100a', end: '101A' },
          { n: 2, start: '101A', end: '101b' },
        ],
      },
      route: '/test-author/test-work',
      title: 'Test Work',
      translations: [],
    };
    const work = { id: 'test-work', bookLabels: ['I', 'II'] };

    const nav = buildNavigation(manifest, work, dir);

    expect(nav.divisions).toEqual([
      {
        id: 'book-1',
        label: 'Book I',
        route: '/read/test-author/test-work/book-1',
        first_locus: '100a',
        final_locus: '101A',
      },
      {
        id: 'book-2',
        label: 'Book II',
        route: '/read/test-author/test-work/book-2',
        first_locus: '101A6',
        final_locus: '101b',
      },
    ]);
    // The first (lower-book) occurrence owns the bare column as its key;
    // the recurrence is keyed by its own first Greek line (101A's book-2
    // segment has greek[0].n === 6).
    expect(nav.loci['101A']).toBe('/read/test-author/test-work/book-1#col-101a');
    expect(nav.loci['101A6']).toBe('/read/test-author/test-work/book-2#col-101a');
    // Only the fragment is lowercased; the loci KEY keeps the column's real case.
    expect(Object.keys(nav.loci)).toContain('101A');
    expect(Object.keys(nav.loci)).toContain('101A6');
    for (const href of Object.values(nav.loci) as string[]) {
      expect(href.split('#')[1]).toMatch(/^[a-z0-9._-]+$/);
    }
    // Every locus path is a declared division route.
    const routes = new Set(nav.divisions.map((node: { route: string }) => node.route));
    for (const href of Object.values(nav.loci) as string[]) {
      expect(routes.has(href.split('#')[0])).toBe(true);
    }
    expect(nav.citation_aliases).toEqual({});
    expect(nav.default_locus).toBe('100a');
    expect(nav.final_locus).toBe('101b');
    expect(validateNavigationSemantics(nav, manifest.translations)).toEqual([]);
  });

  it('a DK work: "<dkChapter> <col>" and "DK <dkChapter> <col>" aliases, loci fragment lowercased, key keeps case', () => {
    const dir = makeNavFixture(
      { B30: [{ book: 1, lo: 1, hi: 3 }], B31: [{ book: 1, lo: 1, hi: 2 }] },
      { 1: [{ column: 'B30', n: 1 }, { column: 'B31', n: 1 }] },
    );
    const manifest = {
      citation: { scheme: 'dk', books: [{ n: 1, start: 'B30', end: 'B31' }] },
      route: '/heraclitus/fragments',
      title: 'Fragments',
      translations: [{ id: 'freeman' }],
    };
    const work = { id: 'heraclitus-fragments', citation: { dkChapter: 22 } };

    const nav = buildNavigation(manifest, work, dir);

    expect(nav.divisions).toEqual([
      {
        id: 'text',
        label: 'Fragments',
        route: '/read/heraclitus/fragments/text',
        first_locus: 'B30',
        final_locus: 'B31',
      },
    ]);
    expect(nav.loci).toEqual({
      B30: '/read/heraclitus/fragments/text#col-b30',
      B31: '/read/heraclitus/fragments/text#col-b31',
    });
    expect(nav.citation_aliases).toEqual({
      '22 B30': 'B30',
      'DK 22 B30': 'B30',
      '22 B31': 'B31',
      'DK 22 B31': 'B31',
    });
    expect(validateNavigationSemantics(nav, manifest.translations)).toEqual([]);
  });

  it('a letter work: bare letter number alias resolves to the first section of that letter', () => {
    const dir = makeNavFixture(
      {
        '46.1': [{ book: 46, lo: 1, hi: 1 }],
        '46.2': [{ book: 46, lo: 2, hi: 2 }],
        '47.1': [{ book: 47, lo: 1, hi: 1 }],
        '47.2': [{ book: 47, lo: 2, hi: 2 }],
      },
      {
        46: [{ column: '46.1', n: 1 }, { column: '46.2', n: 1 }],
        47: [{ column: '47.1', n: 1 }, { column: '47.2', n: 1 }],
      },
    );
    const manifest = {
      citation: {
        scheme: 'letter',
        books: [
          { n: 46, start: '46.1', end: '46.2' },
          { n: 47, start: '47.1', end: '47.2' },
        ],
      },
      route: '/seneca/epistulae-morales',
      title: 'Epistulae Morales',
      translations: [],
    };
    const work = { id: 'epistulae-morales', divisionNoun: 'letter' };

    const nav = buildNavigation(manifest, work, dir);

    expect(nav.divisions[1]).toEqual({
      id: 'letter-47',
      label: 'Letter 47',
      route: '/read/seneca/epistulae-morales/letter-47',
      first_locus: '47.1',
      final_locus: '47.2',
    });
    expect(nav.citation_aliases).toEqual({ '46': '46.1', '47': '47.1' });
    expect(validateNavigationSemantics(nav, manifest.translations)).toEqual([]);
  });

  it('a bookless work reads as a single "text" division labeled with the work title', () => {
    const dir = makeNavFixture(
      { '1': [{ book: 1, lo: 1, hi: 1 }], '2': [{ book: 1, lo: 1, hi: 1 }] },
      { 1: [{ column: '1', n: 1 }, { column: '2', n: 1 }] },
    );
    const manifest = {
      citation: { scheme: 'section', books: [{ n: 1, start: '1', end: '2' }] },
      route: '/epictetus/enchiridion',
      title: 'Enchiridion',
      translations: [],
    };
    const work = { id: 'enchiridion' };

    const nav = buildNavigation(manifest, work, dir);

    expect(nav.divisions).toEqual([
      {
        id: 'text',
        label: 'Enchiridion',
        route: '/read/epictetus/enchiridion/text',
        first_locus: '1',
        final_locus: '2',
      },
    ]);
    expect(nav.default_locus).toBe('1');
    expect(nav.first_locus).toBe('1');
    expect(nav.final_locus).toBe('2');
    expect(validateNavigationSemantics(nav, manifest.translations)).toEqual([]);
  });

  it('language_modes offers original+parallel+translation with ids when translations exist, else original only', () => {
    const dir = makeNavFixture({ '1': [{ book: 1, lo: 1, hi: 1 }] }, { 1: [{ column: '1', n: 1 }] });
    const base = {
      citation: { scheme: 'section', books: [{ n: 1, start: '1', end: '1' }] },
      route: '/x/y',
      title: 'X',
    };
    const work = { id: 'x' };

    const withTranslations = buildNavigation(
      { ...base, translations: [{ id: 'a' }, { id: 'b' }] },
      work,
      dir,
    );
    expect(withTranslations.language_modes).toEqual(['original', 'parallel', 'translation']);
    expect(withTranslations.translation_ids).toEqual(['a', 'b']);

    const withoutTranslations = buildNavigation({ ...base, translations: [] }, work, dir);
    expect(withoutTranslations.language_modes).toEqual(['original']);
    expect(withoutTranslations.translation_ids).toEqual([]);
  });
});

// Mirrors the PHP plugin's validate_navigation + loci cross-checks
// (class-lrm-manifest-validator.php lines 78-85) so the emitter fails loudly
// on a block the plugin would reject, rather than shipping it.
describe('validateNavigationSemantics', () => {
  const baseNavigation = {
    default_locus: 'a',
    first_locus: 'a',
    final_locus: 'a',
    citation_aliases: {},
    language_modes: ['original'],
    translation_ids: [],
    divisions: [{ id: 'text', label: 'X', route: '/read/x/y/text', first_locus: 'a', final_locus: 'a' }],
    loci: { a: '/read/x/y/text#col-a' },
  };

  it('accepts a well-formed navigation block', () => {
    expect(validateNavigationSemantics(baseNavigation, [])).toEqual([]);
  });

  it('rejects a locus whose path is not a declared division route', () => {
    const navigation = { ...baseNavigation, loci: { a: '/read/x/y/wrong-route#col-a' } };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('does not address a declared division route'))).toBe(true);
  });

  it('rejects boundaries and alias values that are not loci keys, and a translation_id absent from the manifest', () => {
    const navigation = {
      ...baseNavigation,
      default_locus: 'missing',
      citation_aliases: { alias1: 'also-missing' },
      translation_ids: ['ghost'],
    };
    const errors = validateNavigationSemantics(navigation, [{ id: 'real' }]);
    expect(errors.some((e: string) => e.includes('default_locus'))).toBe(true);
    expect(errors.some((e: string) => e.includes('alias1'))).toBe(true);
    expect(errors.some((e: string) => e.includes('ghost'))).toBe(true);
  });

  it('rejects duplicate division node ids', () => {
    const navigation = {
      ...baseNavigation,
      divisions: [
        { id: 'dup', label: 'A', route: '/read/x/y/a', first_locus: 'a', final_locus: 'a' },
        { id: 'dup', label: 'B', route: '/read/x/y/b', first_locus: 'a', final_locus: 'a' },
      ],
    };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('.id must be unique'))).toBe(true);
  });

  it('rejects duplicate division node routes', () => {
    const navigation = {
      ...baseNavigation,
      divisions: [
        { id: 'a', label: 'A', route: '/read/x/y/text', first_locus: 'a', final_locus: 'a' },
        { id: 'b', label: 'B', route: '/read/x/y/text', first_locus: 'a', final_locus: 'a' },
      ],
    };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('.route must be unique'))).toBe(true);
  });

  it('rejects translation/parallel language_modes offered without any manifest translation', () => {
    const navigation = { ...baseNavigation, language_modes: ['original', 'translation'] };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('without a manifest translation'))).toBe(true);
  });

  it('rejects a blank or whitespace-only citation alias key', () => {
    const navigation = { ...baseNavigation, citation_aliases: { '   ': 'a' } };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('citation_aliases must map non-empty aliases'))).toBe(true);
  });

  it('rejects a whitespace-only node label', () => {
    const navigation = {
      ...baseNavigation,
      divisions: [{ id: 'text', label: '   ', route: '/read/x/y/text', first_locus: 'a', final_locus: 'a' }],
    };
    const errors = validateNavigationSemantics(navigation, []);
    expect(errors.some((e: string) => e.includes('.label must be a non-empty string'))).toBe(true);
  });

  it('accepts a locus whose path matches a child node\'s route, where the parent node route carries a fragment', () => {
    // Finding 2 repro: PHP strips the fragment from every node's route (not
    // just top-level) and collects nodes recursively, so a locus addressing
    // a child route must be accepted even when its parent's own route has a
    // #fragment.
    const navigation = {
      ...baseNavigation,
      divisions: [
        {
          id: 'parent',
          label: 'Parent',
          route: '/read/x/y/parent#frag',
          first_locus: 'a',
          final_locus: 'b',
          children: [
            { id: 'child', label: 'Child', route: '/read/x/y/child', first_locus: 'b', final_locus: 'b' },
          ],
        },
      ],
      loci: { a: '/read/x/y/parent#col-a', b: '/read/x/y/child#col-b' },
    };
    expect(validateNavigationSemantics(navigation, [])).toEqual([]);
  });
});

describe.skipIf(!existsSync(DIST_DIR))('navigation cross-check against real build data', () => {
  it(
    'every loci key, division boundary, and DK alias traces correctly to the underlying book/columns data, for every built work',
    { timeout: 60_000 },
    () => {
      const dirs = readdirSync(DIST_DIR, { withFileTypes: true }).filter((d) => d.isDirectory());
      let checked = 0;
      for (const dir of dirs) {
        const workDir = join(DIST_DIR, dir.name);
        const manifestPath = join(workDir, 'manifest.json');
        const columnsPath = join(workDir, 'columns.json');
        if (!existsSync(manifestPath) || !existsSync(columnsPath)) continue;
        const ourManifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
        const work = getWork(ourManifest.id);
        if (!work) continue; // non-work dirs under build/dist (e.g. 'Top')
        const nav = buildNavigation(ourManifest, work, workDir);
        const columns = JSON.parse(readFileSync(columnsPath, 'utf8'));
        const books = ourManifest.citation?.books ?? [];
        expect(books.length, `${ourManifest.id} divisions vs citation books`).toBe(nav.divisions.length);

        let workFirstKey: string | null = null;
        let workLastKey: string | null = null;

        books.forEach((book: { n: number }, bookIndex: number) => {
          const division = nav.divisions[bookIndex];
          expect(division.id, `${ourManifest.id} book ${book.n} division`).toBeTruthy();
          const bookPath = join(workDir, `book-${String(book.n).padStart(2, '0')}.json`);
          if (!existsSync(bookPath)) return;
          const bookData = JSON.parse(readFileSync(bookPath, 'utf8'));
          const segments = bookData.segments ?? [];
          expect(segments.length, `${ourManifest.id} book ${book.n} has segments`).toBeGreaterThan(0);

          let divisionFirstKey: string | null = null;
          let divisionLastKey: string | null = null;

          for (const segment of segments) {
            const column: string = segment.column;
            const fragment = column.toLowerCase();

            // Recompute, from columns.json + this segment's own line data
            // (not by trusting buildNavigation's internal bookkeeping),
            // which loci key this segment ought to have produced: the bare
            // column, or -- for a split column's recurrence -- the column
            // plus its own first source line number.
            const occurrences = Array.isArray(columns[column]) ? columns[column] : null;
            const isSplit = !!occurrences && occurrences.length > 1;
            let expectedKey = column;
            if (isSplit) {
              const lowestBook = Math.min(...occurrences.map((o: { book: number }) => o.book));
              if (book.n !== lowestBook) {
                const firstLine = segment.greek?.[0]?.n ?? segment.latin?.[0]?.n;
                expectedKey = `${column}${firstLine}`;
              }
            }

            // (a) exactly one locus key traces to this segment column.
            expect(
              Object.hasOwn(nav.loci, expectedKey),
              `${ourManifest.id} book ${book.n} column '${column}' -> loci key '${expectedKey}'`,
            ).toBe(true);
            const href: string = nav.loci[expectedKey];

            // (b) that key's href path is the division route for THIS book,
            // not merely some division in the work.
            expect(href.split('#')[0], `${ourManifest.id} locus '${expectedKey}' route`).toBe(division.route);

            // (c) the fragment is 'col-' + the column lowercased.
            expect(href.split('#')[1], `${ourManifest.id} locus '${expectedKey}' fragment`).toBe(`col-${fragment}`);

            if (divisionFirstKey == null) divisionFirstKey = expectedKey;
            divisionLastKey = expectedKey;
          }

          // (e) this division's boundaries equal its own first/last segment keys.
          expect(division.first_locus, `${ourManifest.id} division ${division.id} first_locus`).toBe(
            divisionFirstKey,
          );
          expect(division.final_locus, `${ourManifest.id} division ${division.id} final_locus`).toBe(
            divisionLastKey,
          );

          if (bookIndex === 0) workFirstKey = divisionFirstKey;
          workLastKey = divisionLastKey;
        });

        // (d) work-level boundaries: first_locus/default_locus is book 1's
        // first segment key, final_locus is the last book's last segment key.
        expect(nav.first_locus, `${ourManifest.id} first_locus`).toBe(workFirstKey);
        expect(nav.default_locus, `${ourManifest.id} default_locus`).toBe(workFirstKey);
        expect(nav.final_locus, `${ourManifest.id} final_locus`).toBe(workLastKey);

        // (f) DK works: every column carries both alias forms, and both
        // resolve to the bare column.
        if (ourManifest.citation?.scheme === 'dk') {
          const dkChapter = work.citation?.dkChapter;
          for (const column of Object.keys(nav.loci)) {
            expect(
              nav.citation_aliases[`${dkChapter} ${column}`],
              `${ourManifest.id} alias '${dkChapter} ${column}'`,
            ).toBe(column);
            expect(
              nav.citation_aliases[`DK ${dkChapter} ${column}`],
              `${ourManifest.id} alias 'DK ${dkChapter} ${column}'`,
            ).toBe(column);
          }
        }

        expect(validateNavigationSemantics(nav, ourManifest.translations ?? [])).toEqual([]);
        checked += 1;
      }
      expect(checked).toBeGreaterThan(0);
    },
  );
});
