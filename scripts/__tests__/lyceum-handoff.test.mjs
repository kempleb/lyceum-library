import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { convertHandoff, mapPassagesOntoLatin, verifyHandoffChecksums } from '../lib/corpus-adapter/lyceum-handoff.mjs';
import { applyLyceumOverrides } from '../emit-lyceum-manifest.mjs';
import { shouldIncludeHandoff } from '../build-registry.mjs';
const dir = () => mkdtempSync(join(tmpdir(), 'handoff-test-'));
const put = (d, n, x) => writeFileSync(join(d, n), JSON.stringify(x));
const get = (d, n) => JSON.parse(readFileSync(join(d, n)));
const record = id => ({ id, rights: `rights ${id}`, source: id === 'latin' ? 'https://github.com/PerseusDL/canonical-latinLit/blob/master/data/phi0690/phi003/phi0690.phi003.perseus-lat2.xml' : `https://example.com/${id}`, edition_year: 1900 });
function fixture() {
  const src = dir(), dst = dir();
  put(src, 'source-records.json', { verification: 'checked', records: ['federalist', 'latin', 'williams-en', 'dryden-en', 'mackail-en'].map(record) });
  put(src, 'federalist.bundle.json', { works: [{ manifest: { work: 'lyceum:publius.federalist', schema_version: '1.0', corpus_version: 'old', corpus_id: 'american', navigation: { loci: {} } }, divisions: Array.from({ length: 85 }, (_, i) => ({ id: `essay-${i + 1}`, passages: ['For the Paper. Date', 'AUTHOR', 'To the People of the State of New York:', `text ${i + 1}`].map((text, k) => ({ id: `paragraph-${k + 1}`, reference: `${i + 1}.${k + 1}`, texts: [{ language: 'en', role: 'original', text }] })) })) }] });
  const books = Array.from({ length: 12 }, (_, i) => { const b = i + 1; return { book: b, scholarSegments: [{ id: `aeneid-${b}-1-3`, book: b, latin: b === 10 ? [{ n: '62', ref: 62, text: 'a' }, { n: '62b', ref: 62, text: 'b' }, { n: '4', ref: 4, text: 'c' }, { n: '3', ref: 3, text: 'd' }] : [{ n: '1', ref: 1, text: 'a' }], translations: { williams: ['one', 'two '], dryden: ['three '], mackail: ['four '] } }] }; });
  put(src, 'aeneid.books.json', { work: 'lyceum:vergil.aeneid', books });
  put(src, 'aeneid.routes.json', { navigation: { loci: {} } });
  const checksums = Object.fromEntries(['source-records.json', 'federalist.bundle.json', 'aeneid.books.json', 'aeneid.routes.json'].map(n => [n, createHash('sha256').update(readFileSync(join(src, n))).digest('hex')]));
  put(src, 'CHECKSUMS.json', checksums);
  return { src, dst };
}
test('converter keeps source order, letter suffixes, and trailing spaces', () => {
  const { src, dst } = fixture(); verifyHandoffChecksums(src);
  convertHandoff(src, dst, { id: 'aeneid', author: 'vergil', slug: 'aeneid', title: 'Aeneid', language: 'lat', greekEdition: 'edition', citation: { scheme: 'verse-line' }, translations: [{ id: 'williams-en', name: 'Williams', slot: 'english' }, { id: 'dryden-en', name: 'Dryden', slot: 'secondary' }, { id: 'mackail-en', name: 'Mackail', slot: 'third' }] }, 'v');
  const rows = get(dst, 'book-10.json').segments;
  assert.deepEqual(rows.map(x => x.column), ['10.62', '10.62b', '10.4', '10.3']);
  assert.equal(rows[1].ref, 62);
  assert.equal(rows[0].english.text, 'one\ntwo ');
  assert.equal(rows[0].secondary[0].text, 'three ');
  assert.equal(rows[0].third[0].text, 'four ');
  assert.deepEqual(get(dst, 'manifest.json').editions[0].source, { kind: 'perseus', author: 'phi0690', work: 'phi003.perseus-lat2' });
});
test('Federalist mapping and checksum mismatch', () => {
  const { src, dst } = fixture();
  convertHandoff(src, dst, { id: 'federalist', author: 'publius', slug: 'federalist', title: 'The Federalist', language: 'en', greekEdition: 'edition', citation: { scheme: 'book-section' }, translations: [] }, 'v');
  const segs = get(dst, 'book-01.json').segments;
  assert.equal(segs[3].greek[0].text, 'text 1');
  assert.deepEqual(segs[0].anchors, ['paragraph-1']);
  // The lines before the salutation are kept but hidden; the rest are shown.
  assert.deepEqual(segs.map(s => s.hidden === true), [true, true, false, false]);
  writeFileSync(join(src, 'aeneid.routes.json'), 'bad');
  assert.throws(() => verifyHandoffChecksums(src), /checksum mismatch/);
});
test('overrides merge and forbidden keys fail; absent file keeps identity', () => {
  const dst = dir(), original = { work: 'x', navigation: { loci: { a: 'old' }, divisions: [] } };
  assert.equal(applyLyceumOverrides(original, join(dst, 'missing.json')), original);
  put(dst, 'overrides.json', { title: 'new', navigation: { loci: { a: 'new' } } });
  assert.deepEqual(applyLyceumOverrides(original, join(dst, 'overrides.json')).navigation, { loci: { a: 'new' }, divisions: [] });
  put(dst, 'overrides.json', { generator: 'bad' });
  assert.throws(() => applyLyceumOverrides(original, join(dst, 'overrides.json')), /forbidden/);
});
test('held adapter skips a missing source directory without a mount', () => {
  const result = spawnSync(process.execPath, ['scripts/mount-corpus.mjs', 'american'], {
    cwd: new URL('../..', import.meta.url).pathname,
    env: { ...process.env, READER_INCLUDE_HELD: '1', LYCEUM_HANDOFF_DIR: join(dir(), 'missing') },
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /no-op/);
});
test('registry admits held sources only with the flag', () => {
  assert.equal(shouldIncludeHandoff({ hold: true }, {}), false);
  assert.equal(shouldIncludeHandoff({ hold: true }, { READER_INCLUDE_HELD: '1' }), true);
  assert.equal(shouldIncludeHandoff({ hold: false }, {}), true);
});
test('PHI maps a dropped address and a transposition within one passage', () => {
  const book = { book: 1, scholarSegments: [
    { id: 'first', latin: [{ n: '1' }, { n: '2' }, { n: '3' }] },
    { id: 'second', latin: [{ n: '4' }, { n: '5' }] },
  ] };
  const mapped = mapPassagesOntoLatin(book, [{ n: '1' }, { n: '3' }, { n: '5' }, { n: '4' }]);
  assert.deepEqual(mapped[0].landings, { 1: '1', 2: '1', 3: '3' });
  assert.deepEqual(mapped[1].rows.map(row => row.n), ['5', '4']);
  assert.throws(() => mapPassagesOntoLatin(book, [{ n: '1' }, { n: '5' }, { n: '3' }, { n: '4' }]), /out of sequence/);
  assert.throws(() => mapPassagesOntoLatin(book, [{ n: '1' }, { n: '3' }, { n: '6' }, { n: '4' }]), /no passage/);
  assert.throws(() => mapPassagesOntoLatin(book, [{ n: '1' }, { n: '3' }]), /owns no PHI row/);
  assert.throws(() => mapPassagesOntoLatin({ book: 1, scholarSegments: [
    { id: 'one', latin: [{ n: '1' }] }, { id: 'two', latin: [{ n: '1' }] },
  ] }, [{ n: '1' }]), /two passages own/);
});
test('PHI mount names the extractor when its JSON is missing', () => {
  const { src } = fixture();
  const result = spawnSync(process.execPath, ['scripts/mount-corpus.mjs', 'vergil'], {
    cwd: new URL('../..', import.meta.url).pathname,
    env: { ...process.env, READER_INCLUDE_HELD: '1', LYCEUM_HANDOFF_DIR: src,
      LYCEUM_PHI_LATIN: join(dir(), 'missing.json') }, encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /python -m reader_pipeline\.handoff_phi_latin --phi-author 0690/);
});
test('PHI converter uses PHI text and keeps Brian translations and addresses', () => {
  const { src, dst } = fixture();
  const phiPath = join(dir(), 'phi.json');
  const books = get(src, 'aeneid.books.json').books.map(book => ({ book: book.book,
    rows: book.book === 10 ? [{ n: '62', text: 'PHI first' }, { n: '3', text: 'PHI third' }, { n: '4', text: 'PHI fourth' }]
      : [{ n: '1', text: 'PHI line' }] }));
  writeFileSync(phiPath, JSON.stringify({ source: { corpus: 'phi', author: '0690', work: '003' }, books }));
  const work = { id: 'aeneid', author: 'vergil', slug: 'aeneid', title: 'Aeneid', language: 'lat',
    greekEdition: 'Mynors', citation: { scheme: 'verse-line' }, translations: [
      { id: 'williams-en', short: 'Williams', slot: 'english' },
      { id: 'dryden-en', short: 'Dryden', slot: 'secondary' },
      { id: 'mackail-en', short: 'Mackail', slot: 'third' }] };
  convertHandoff(src, dst, work, 'v', { latin: 'phi', phiLatin: phiPath, phiAuthor: '0690', phiWork: '003' });
  const rows = get(dst, 'book-10.json').segments;
  assert.deepEqual(rows.map(row => row.column), ['10.62', '10.3', '10.4']);
  assert.equal(rows[0].greek[0].text, 'PHI first');
  assert.deepEqual(rows[0].anchors, ['aeneid-10-1-3', 'line-62', 'line-62b']);
  assert.equal(rows[0].english.text, 'one\ntwo ');
  assert.equal(get(dst, 'manifest.json').editions[0].source.kind, 'phi');
  assert.equal(Object.hasOwn(get(dst, 'lyceum-overrides.json'), 'editions'), false);
});
