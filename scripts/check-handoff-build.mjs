#!/usr/bin/env node
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mapPassagesOntoLatin } from './lib/corpus-adapter/lyceum-handoff.mjs';
const require = createRequire(import.meta.url);
const { Window } = require('../app/node_modules/happy-dom');
const args = Object.fromEntries(process.argv.slice(2).reduce((out, x, i, a) => x.startsWith('--') ? [...out, [x.slice(2), a[i + 1]]] : out, []));
const handoff = resolve(args.handoff ?? ''), dist = resolve(args.dist ?? ''), html = resolve(args.html ?? '');
const read = (dir, file) => JSON.parse(readFileSync(join(dir, file), 'utf8'));
const check = (condition, message) => { if (!condition) throw new Error(message); };
const same = (a, b, message) => check(JSON.stringify(a) === JSON.stringify(b), message);
const norm = s => s.replace(/\s+/g, ' ').trim();
if (process.argv[2] === '--parse-page') {
  const checks = JSON.parse(readFileSync(0, 'utf8'));
  const window = new Window({ settings: { disableJavaScriptEvaluation: true,
    disableJavaScriptFileLoading: true, disableCSSFileLoading: true } });
  window.document.write(readFileSync(process.argv[3], 'utf8'));
  const ids = new Map([...window.document.querySelectorAll('[id]')].map(node => [node.id, node]));
  for (const { id, contains, compact, segment, order, group, groupCount, groupText, hidden } of checks) {
    if (hidden) {
      check(ids.get(hidden)?.classList.contains('segment-hidden'), `${hidden} should be hidden in ${process.argv[3]}`);
      continue;
    }
    if (groupCount !== undefined) {
      check(window.document.querySelectorAll('.verse-group').length === groupCount,
        `verse-group count differs in ${process.argv[3]}`);
      continue;
    }
    if (group) {
      const first = ids.get(group[0])?.closest('.verse-group');
      check(first && first.querySelectorAll('.english-col').length === 1,
        `passage ${group[0]} lacks one English column in ${process.argv[3]}`);
      for (const lineId of group) check(ids.get(lineId)?.closest('.verse-group') === first,
        `${lineId} lies outside its passage group in ${process.argv[3]}`);
      continue;
    }
    if (order) {
      const actual = [...window.document.querySelectorAll('.segment')].map(node => node.id);
      same(actual, order, `segment order differs from the handoff in ${process.argv[3]}`);
      continue;
    }
    const node = ids.get(id);
    check(node, `missing fragment ${id} in ${process.argv[3]}`);
    if (segment !== undefined) {
      check(node.closest('.segment')?.id === segment, `fragment ${id} is not inside #${segment} in ${process.argv[3]}`);
    }
    if (contains !== undefined) {
      const textNode = groupText ? node.closest('.verse-group') : node;
      check(textNode, `missing verse group for ${id} in ${process.argv[3]}`);
      const actual = compact ? textNode.textContent.replace(/\s+/g, '') : norm(textNode.textContent);
      check(actual.includes(contains), `HTML text mismatch ${id} in ${process.argv[3]}`);
    }
  }
  process.exit(0);
}
const htmlChecks = new Map();
function page(route, segment) {
  const [path, fragment] = route.split('#');
  const file = join(html, path, 'index.html');
  check(existsSync(file), `missing page ${file}`);
  if (!htmlChecks.has(file)) htmlChecks.set(file, []);
  if (fragment) htmlChecks.get(file).push({ id: fragment, segment });
  return file;
}
const pages = { divisions: 0, landings: 0 };
function textAt(route, id, text, compact = false, groupText = false) {
  const file = page(route);
  htmlChecks.get(file).push({ id, contains: compact ? text.replace(/\s+/g, '') : norm(text), compact, groupText });
}
function run() {
  const federalist = read(handoff, 'federalist.bundle.json').works[0];
  const aeneid = read(handoff, 'aeneid.books.json');
  const routes = read(handoff, 'aeneid.routes.json');
  const fedManifest = read(join(dist, 'federalist'), 'manifest.lyceum.json');
  const aenManifest = read(join(dist, 'aeneid'), 'manifest.lyceum.json');
  const pipelineManifest = read(join(dist, 'aeneid'), 'manifest.json');
  const isPhi = pipelineManifest.editions[0].source?.kind === 'phi';
  check(!isPhi || args['phi-latin'], '--phi-latin is required for a PHI Aeneid build');
  const phi = isPhi ? JSON.parse(readFileSync(resolve(args['phi-latin']), 'utf8')) : null;
  same(fedManifest.navigation.loci, federalist.manifest.navigation.loci, 'Federalist loci differ');
  same(aenManifest.navigation.loci, routes.navigation.loci, 'Aeneid loci differ');
  const counts = { federalist: 0, latin: 0, translations: 0, groups: 0, federalistLoci: 0, aeneidLoci: 0, moved: 0 };
  for (const [i, division] of federalist.divisions.entries()) {
    const b = i + 1, built = read(join(dist, 'federalist'), `book-${String(b).padStart(2, '0')}.json`).segments;
    check(built.length === division.passages.length, `essay ${b} length`);
    htmlChecks.get(page(`/read/publius/federalist/essay-${b}`)).push({ order: division.passages.map((_, k) => `col-${b}.${k + 1}`) });
    for (const [k, passage] of division.passages.entries()) {
      const column = `${b}.${k + 1}`, seg = built[k];
      check(seg.column === column && seg.greek[0].text === passage.texts[0].text, `Federalist ${column}`);
      textAt(fedManifest.navigation.loci[column], `col-${column}`, passage.texts[0].text);
      if (seg.hidden) { htmlChecks.get(page(fedManifest.navigation.loci[column])).push({ hidden: `col-${column}` }); counts.hiddenFederalist = (counts.hiddenFederalist ?? 0) + 1; }
      page(fedManifest.navigation.loci[column], `col-${column}`);
      counts.federalist++;
    }
  }
  for (const [i, book] of aeneid.books.entries()) {
    const b = i + 1, built = read(join(dist, 'aeneid'), `book-${String(b).padStart(2, '0')}.json`).segments;
    const rows = phi ? phi.books[i]?.rows : book.scholarSegments.flatMap(s => s.latin);
    check(rows && (!phi || phi.books[i].book === b), `PHI book ${b}`);
    const mappings = phi ? mapPassagesOntoLatin(book, rows)
      : book.scholarSegments.map(passage => ({ passage, rows: passage.latin,
        landings: Object.fromEntries(passage.latin.map(row => [row.n, row.n])) }));
    let index = 0;
    htmlChecks.get(page(`/read/vergil/aeneid/book-${b}`)).push({ order: rows.map(row => `col-${b}.${row.n}`) });
    htmlChecks.get(page(`/read/vergil/aeneid/book-${b}`)).push({ groupCount: mappings.length });
    for (const { passage: scholar, rows: passageRows, landings } of mappings) {
      page(`/read/vergil/aeneid/book-${b}#${scholar.id}`, `col-${b}.${passageRows[0].n}`);
      const first = built[index];
      same(first.english.text.split('\n'), scholar.translations.williams, `Williams ${scholar.id}`);
      same(first.secondary[0].text.split('\n'), scholar.translations.dryden, `Dryden ${scholar.id}`);
      same(first.third[0].text.split('\n'), scholar.translations.mackail, `Mackail ${scholar.id}`);
      counts.translations += 3;
      textAt(`/read/vergil/aeneid/book-${b}#${scholar.id}`, `col-${first.column}`, first.english.text, true, true);
      htmlChecks.get(page(`/read/vergil/aeneid/book-${b}`)).push({ group: passageRows.map(row => `col-${b}.${row.n}`) });
      counts.groups++;
      for (const row of passageRows) {
        const seg = built[index++], column = `${b}.${row.n}`;
        check(seg.column === column && seg.ref === (phi ? parseInt(row.n, 10) : row.ref) && seg.greek[0].text === row.text, `Latin ${column}`);
        textAt(`/read/vergil/aeneid/book-${b}#line-${row.n}`, `L${column}-1`, row.text);
        counts.latin++;
      }
      for (const row of scholar.latin) {
        const landing = landings[row.n];
        page(`/read/vergil/aeneid/book-${b}#line-${row.n}`, `col-${b}.${landing}`);
        if (landing !== row.n) counts.moved++;
      }
    }
    check(index === built.length, `extra Aeneid rows in book ${b}`);
  }
  for (const route of Object.values(federalist.manifest.navigation.loci)) { page(route); counts.federalistLoci++; }
  for (const route of Object.values(routes.navigation.loci)) { page(route); counts.aeneidLoci++; }
  for (const division of [...fedManifest.navigation.divisions, ...aenManifest.navigation.divisions]) { page(division.route); pages.divisions++; }
  for (const landing of ['/texts/publius/federalist/', '/texts/vergil/aeneid/']) { page(landing); pages.landings++; }
  let parsed = 0;
  for (const [file, checks] of htmlChecks) {
    const result = spawnSync(process.execPath, [process.argv[1], '--parse-page', file],
      { input: JSON.stringify(checks), encoding: 'utf8', maxBuffer: 1024 * 1024 });
    check(result.status === 0, result.stderr || result.error?.message || `HTML check failed: ${file}`);
    parsed++;
    if (parsed % 20 === 0) console.log(`Checked ${parsed} HTML pages`);
  }
  check(counts.federalist === 1625 && counts.latin === (phi ? 9888 : 9897) && counts.translations === 981 && counts.groups === 327 && counts.aeneidLoci === 10224 && counts.federalistLoci === 1625 && counts.moved === (phi ? 9 : 0), `unexpected counts ${JSON.stringify(counts)}`);
  console.log(`Federalist paragraphs: ${counts.federalist} (opening lines hidden under the essay heading: ${counts.hiddenFederalist ?? 0}); Latin rows: ${counts.latin}; verse groups: ${counts.groups}; moved Aeneid addresses: ${counts.moved}; translation arrays: ${counts.translations} (327 × 3); Aeneid loci: ${counts.aeneidLoci}; Federalist loci: ${counts.federalistLoci}; division routes: ${pages.divisions}; landing routes: ${pages.landings}; segment order checked on ${85 + 12} pages.`);
  console.log('Dryden and Mackail HTML switches are client-rendered; their exact text passed data-level checks.');
}
try { run(); } catch (error) { console.error(error.stack ?? String(error)); process.exitCode = 1; }
