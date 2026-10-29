import { createHash } from 'node:crypto';
import { copyFileSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const read = (dir, file) => JSON.parse(readFileSync(join(dir, file), 'utf8'));
const write = (dir, file, value) => writeFileSync(join(dir, file), `${JSON.stringify(value, null, 2)}\n`);
const check = (ok, message) => { if (!ok) throw new Error(`lyceum-handoff: ${message}`); };

export function verifyHandoffChecksums(sourceDir) {
  const checksums = read(sourceDir, 'CHECKSUMS.json');
  for (const [file, expected] of Object.entries(checksums)) {
    const actual = createHash('sha256').update(readFileSync(join(sourceDir, file))).digest('hex');
    check(actual === expected, `checksum mismatch: ${file}`);
  }
}

function perseusSource(url) {
  const m = /\/data\/(phi\d+)\/(phi\d+)\/\1\.\2\.([a-z0-9-]+)\.xml$/.exec(url);
  check(m, `not a Perseus canonical-latinLit file: ${url}`);
  return { kind: 'perseus', author: m[1], work: `${m[2]}.${m[3]}` };
}

// Each result keeps Brian's passage and the PHI rows it owns in display order.
// `landings` maps each of Brian's line addresses to a PHI row number.
export function mapPassagesOntoLatin(book, rows) {
  const owner = new Map();
  for (const [index, passage] of book.scholarSegments.entries()) {
    for (const row of passage.latin) {
      check(!owner.has(row.n), `two passages own ${book.book}.${row.n}`);
      owner.set(row.n, index);
    }
  }
  const result = book.scholarSegments.map(passage => ({ passage, rows: [], landings: {} }));
  const seen = new Set();
  let previous = -1;
  for (const row of rows) {
    check(!seen.has(row.n), `duplicate PHI row ${book.book}.${row.n}`);
    seen.add(row.n);
    const index = owner.get(row.n);
    check(index !== undefined, `PHI row ${book.book}.${row.n} has no passage`);
    check(index >= previous, `passages out of sequence in book ${book.book}`);
    if (index === previous) check(result[index].rows.length > 0, `non-contiguous passage in book ${book.book}`);
    result[index].rows.push(row);
    previous = index;
  }
  for (const item of result) {
    check(item.rows.length, `passage ${item.passage.id} owns no PHI row`);
    const present = new Set(item.rows.map(row => row.n));
    let preceding = item.rows[0].n;
    for (const row of item.passage.latin) {
      if (present.has(row.n)) preceding = row.n;
      item.landings[row.n] = preceding;
    }
  }
  return result;
}

export function convertHandoff(sourceDir, destDir, work, corpusVersion, options = {}) {
  const recordsFile = read(sourceDir, 'source-records.json');
  const records = Object.fromEntries(recordsFile.records.map(record => [record.id, record]));
  const license = record => ({ status: 'unverified', rationale: record.rights });
  const books = [];
  const columns = {};
  const sections = {};
  const translations = (work.translations ?? []).map(t => ({
    id: t.id, name: t.name, slot: t.slot === 'english' ? 'primary' : t.slot,
    default: t.slot === 'english', license: license(records[t.id]),
  }));
  let overrides;

  if (work.id === 'federalist') {
    const bundle = read(sourceDir, 'federalist.bundle.json');
    check(bundle.works.length === 1 && bundle.works[0].manifest.work === 'lyceum:publius.federalist', 'wrong Federalist work');
    const { manifest, divisions } = bundle.works[0];
    check(divisions.length === 85, 'Federalist division count');
    for (const [i, division] of divisions.entries()) {
      const b = i + 1;
      check(division.id === `essay-${b}`, `Federalist division ${b}`);
      // The lines before the salutation are the essay's own publication and
      // author lines; the page shows the Library of Congress heading instead
      // (John 2026-10-09), so they are kept in the data but marked hidden.
      const salutation = division.passages.findIndex(p => p.texts[0].text.startsWith('To the People of the State of New York'));
      check(salutation >= 1 && salutation <= 2, `Federalist ${b}: no salutation in the first three paragraphs`);
      const segments = division.passages.map((passage, k) => {
        const n = k + 1, column = `${b}.${n}`;
        check(passage.id === `paragraph-${n}` && passage.reference === column, `Federalist passage ${column}`);
        check(passage.texts.length === 1 && passage.texts[0].language === 'en' && passage.texts[0].role === 'original', `Federalist text ${column}`);
        const segment = { id: `${b}:${column}`, column,
          greek: [{ n: 1, text: passage.texts[0].text, tokens: [] }], english: null,
          anchors: [`paragraph-${n}`], ...(k < salutation ? { hidden: true } : {}) };
        check(!columns[column], `duplicate column ${column}`);
        columns[column] = [{ book: b, lo: 1, hi: 1 }];
        (sections[b] ??= []).push({ column, page: n, letter: '', id: segment.id });
        return segment;
      });
      check(segments.length > 0, `empty essay ${b}`);
      write(destDir, `book-${String(b).padStart(2, '0')}.json`, { book: b, segments });
      books.push({ book: b, segments: segments.length, first_column: segments[0].column, last_column: segments.at(-1).column });
    }
    const { schema_version, corpus_version, corpus_id, ...rest } = manifest;
    overrides = rest;
  } else if (work.id === 'aeneid') {
    const latin = options.latin ?? 'perseus';
    check(['phi', 'perseus'].includes(latin), `unknown latin ${latin}`);
    const phi = latin === 'phi' ? JSON.parse(readFileSync(options.phiLatin, 'utf8')) : null;
    if (phi) check(phi.source.corpus === 'phi' && phi.source.author === options.phiAuthor && phi.source.work === options.phiWork, 'wrong PHI source');
    const source = read(sourceDir, 'aeneid.books.json');
    check(source.work === 'lyceum:vergil.aeneid' && source.books.length === 12, 'wrong Aeneid work');
    for (const [i, book] of source.books.entries()) {
      const b = i + 1;
      check(book.book === b, `Aeneid book ${b}`);
      const segments = [];
      const mappings = phi ? mapPassagesOntoLatin(book, phi.books[i]?.rows ?? [])
        : book.scholarSegments.map(passage => ({ passage, rows: passage.latin }));
      for (const { passage: scholar, rows, landings } of mappings) {
        check(scholar.book === b && scholar.latin.length > 0, `Aeneid segment ${scholar.id}`);
        for (const [j, row] of rows.entries()) {
          const column = `${b}.${row.n}`;
          check(!columns[column], `duplicate column ${column}`);
          const anchors = phi
            ? [ ...(j === 0 ? [scholar.id] : []), ...scholar.latin.filter(original => landings[original.n] === row.n).map(original => `line-${original.n}`) ]
            : j === 0 ? [scholar.id, `line-${row.n}`] : [`line-${row.n}`];
          const seg = { id: `${b}:${column}`, column,
            greek: [{ n: 1, text: row.text, tokens: [] }], ref: phi ? parseInt(row.n, 10) : row.ref,
            anchors,
            english: j === 0 ? { text: scholar.translations.williams.join('\n'), notes: [], markers: [] } : null };
          if (j === 0) {
            seg.secondary = [{ chapter: scholar.id, text: scholar.translations.dryden.join('\n'), cont: false }];
            seg.third = [{ chapter: scholar.id, text: scholar.translations.mackail.join('\n'), cont: false }];
          }
          columns[column] = [{ book: b, lo: 1, hi: 1 }];
          segments.push(seg);
        }
      }
      check(segments.length > 0, `empty Aeneid book ${b}`);
      write(destDir, `book-${String(b).padStart(2, '0')}.json`, { book: b, segments });
      books.push({ book: b, segments: segments.length, first_column: segments[0].column, last_column: segments.at(-1).column });
    }
    const routes = read(sourceDir, 'aeneid.routes.json');
    overrides = {
      ...(latin === 'perseus' ? { editions: [{ id: 'latin', source: records.latin.source, url: records.latin.source,
        license: records.latin.rights, verified: false, verification_status: recordsFile.verification }] } : {}),
      translations: ['williams-en', 'dryden-en', 'mackail-en'].map(id => ({
        id, label: work.translations.find(t => t.id === id).short,
        date: records[id].edition_year, rights: records[id].rights, default: id === 'williams-en',
      })),
      // No search index or word analyses are built for this work, so the
      // emitter's per-language search/lexicon claims would be false.
      apparatus: [],
      navigation: { loci: routes.navigation.loci },
    };
  } else throw new Error(`lyceum-handoff: unknown work ${work.id}`);

  const sourceRecord = records[work.id === 'federalist' ? 'federalist' : 'latin'];
  const manifest = {
    schema_version: 'manifest.v1', id: work.id, author: work.author, title: work.title,
    language: work.language, route: `/${work.author}/${work.slug}`,
    citation: { scheme: work.citation.scheme, books: books.map(b => ({ n: b.book, start: b.first_column, end: b.last_column })) },
    // Our schema requires a source for a Latin edition: PHI's author/work
    // under `latin: phi` (John's ruling), else the Perseus file named in
    // source-records.json (its CTS ids).
    editions: [{ language: work.language, edition: work.greekEdition,
      license: work.id === 'aeneid' && options.latin === 'phi' ? { status: 'unverified' } : license(sourceRecord),
      ...(work.language === 'lat' ? { source: options.latin === 'phi'
        ? { kind: 'phi', author: options.phiAuthor, work: options.phiWork }
        : perseusSource(sourceRecord.source) } : {}) }],
    translations, apparatus: { footnotes: false, sidenotes: false, paratext: false,
      figures: false, sections: work.id === 'federalist', philosophers: false },
    presentation: work, corpus_version: corpusVersion, books,
  };
  write(destDir, 'manifest.json', manifest);
  write(destDir, 'columns.json', columns);
  write(destDir, 'chapters.json', {});
  if (work.id === 'federalist') write(destDir, 'sections.json', sections);
  copyFileSync(join(sourceDir, 'source-records.json'), join(destDir, 'source-records.json'));
  // Per-division headings (the Federalist's title/author/publication/date from
  // the Library of Congress table, John 2026-10-09), keyed by book number.
  if (options.divisionHeads) {
    const heads = JSON.parse(readFileSync(options.divisionHeads, 'utf8'));
    check(heads.essays.length === books.length && heads.essays.every((e, i) => e.n === i + 1), 'division heads do not match the books');
    write(destDir, 'division-heads.json', Object.fromEntries(heads.essays.map(({ n, ...head }) => [String(n), { label: `No. ${n}`, ...head }])));
  }
  write(destDir, 'lyceum-overrides.json', overrides);
  return books.length + 4 + (work.id === 'federalist' ? 1 : 0);
}
