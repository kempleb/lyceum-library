import { readFileSync, readdirSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const requireShared = createRequire(join(root, 'shared/package.json'));
const { createServer } = await import(requireShared.resolve('vite'));
const yaml = requireShared('js-yaml');
const dist = resolve(process.argv[2] ?? join(root, 'build/dist'));
const exceptions = JSON.parse(readFileSync(join(root, 'scripts/dk-structure-allowlist.json'), 'utf8'));
const allowlist = exceptions.sectionGaps;
const contextAllowlist = exceptions.contextGaps;
// C6 exceptions: { work, column, head, reason }, on the exact heading text;
// C7 exceptions: { work, column, reason } (no source text in this file).
const bracketAllowlist = exceptions.headBrackets ?? [];
const vglAllowlist = exceptions.vglEnds ?? [];
const excepted = (list, work, column, head) => {
  const entry = list.find(a => a.work === work && a.column === column && a.head === head && a.reason?.trim());
  if (entry) entry.used = true;
  return !!entry;
};
// An opening parenthesis, bracket or angle bracket with no closer after it.
const unclosed = text => {
  const open = [];
  for (const ch of text) {
    if ('([<'.includes(ch)) open.push(ch);
    else if (')]>'.includes(ch) && open.length) open.pop();
  }
  return open.length > 0;
};
// A paragraph that ends in DK's "vgl." (compare) has lost what it compares.
const danglingVgl = text => /(?:^|[^\p{L}])vgl\.[\s\p{P}]*$/iu.test(text);
// A place in the source above by numbers and a Diels page, "4, 3 (D. 331)",
// left in a paragraph instead of heading its own passage.
const dielsPlace = /(?:^|[.·;:\])]\s+)(?:[IVX]+,?\s*\d+[a-z]?(?:,\s*\d+[a-z]?)?|\d+[a-z]?,\s*\d+[a-z]?)(?:\.\s*\d+[a-z]?)*\s*\(D\.\s*\d+/u;
const server = await createServer({ root, configFile: false, optimizeDeps: { noDiscovery: true, include: [] }, server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' });
const failures = [];
const report = { dataRoot: dist, works: [], midlineSplits: [], sectionMismatches: [], contextMismatches: [], unresolvedExpansions: [], unclosedHeads: [], vglEnds: [], failures };
try {
  const { buildDkSourceRows, contextSectionMarkerNumbers, headTextFaults, sourceMatches } = await server.ssrLoadModule('/shared/lib/dk-layout.ts');
  const segments = [], paragraphs = [], expansions = [], records = [];
  for (const file of readdirSync(join(root, 'manifests')).filter(f => f.endsWith('.yaml')).sort()) {
    const manifest = yaml.load(readFileSync(join(root, 'manifests', file), 'utf8'));
    if (manifest?.citation?.scheme !== 'dk' || !manifest.citation.expand_citations) continue;
    const work = manifest.work.id;
    const dir = join(dist, work);
    const summary = { work, segments: 0, citations: 0, midlineSplits: 0 };
    report.works.push(summary);
    if (!existsSync(dir)) { failures.push(`${work}: missing data directory`); continue; }
    const books = readdirSync(dir).filter(f => /^book-\d+\.json$/.test(f)).sort();
    if (!books.length) failures.push(`${work}: no books`);
    for (const book of books) for (const seg of JSON.parse(readFileSync(join(dir, book), 'utf8')).segments) {
      summary.segments++;
      const label = `${work}/${seg.column}`;
      const record = { work, seg, label, summary, rows: null };
      records.push(record);
      segments.push({ work, seg });
      if (!Array.isArray(seg.citationHeads)) { failures.push(`${label}: missing citationHeads; regenerate data`); continue; }
      summary.citations += seg.citationHeads.length;
      try {
        const rows = buildDkSourceRows(seg, !!manifest.citation.lines,
          (manifest.citation.incipit_columns ?? []).some(c => c.column === seg.column));
        record.rows = rows;
        const actualHeads = rows.flatMap(row => row.items.filter(i => i.kind === 'source-head'));
        if (actualHeads.length !== seg.citationHeads.length) failures.push(`${label}: C2 heading count`);
        seg.citationHeads.forEach((head, i) => {
          const row = rows.find(r => r.head === head);
          if (actualHeads[i]?.line.text !== head.text || !row || row.items[0]?.kind !== 'source-head'
            || row.head.expanded !== head.expanded) failures.push(`${label}: C2 heading/expansion order at ${i}`);
          if (unclosed(head.text)) {
            report.unclosedHeads.push({ work, column: seg.column, head: head.text });
            if (!excepted(bracketAllowlist, work, seg.column, head.text)) failures.push(`${label}: C6 heading opens a bracket it does not close at ${i}`);
          }
          const line = seg.greek[head.lineIndex];
          if (line.text.slice(0, head.start).trim()) {
            summary.midlineSplits++;
            report.midlineSplits.push({ work, column: seg.column, head: head.text,
              before: Array.from(line.text.slice(0, head.start)).slice(-30).join('') });
          }
          for (const entry of head.expanded) {
            // The English side prints an unresolved citation as printed:
            // never with DK's dash (John, 2026-09-27).
            if (entry.resolution === 'verbatim' && /^[—–]/.test(entry.verbatim)) failures.push(`${label}: C8 citation printed with a dash at ${i}`);
            expansions.push({ label, text: entry.verbatim });
            if (entry.resolution === 'verbatim') report.unresolvedExpansions.push({ work, column: seg.column, head: head.text, flags: entry.flags });
          }
        });
        const columnParagraphs = [];
        for (const row of rows) for (const item of row.items) {
          if (item.kind === 'flow') {
            // Scan the rendered paragraph, including role-run seams.
            columnParagraphs.push({ label, text: item.prose.runs.map(r => (r.space ? ' ' : '') + r.line.text).join('') });
          } else if (item.kind === 'line') columnParagraphs.push({ label, text: item.line.text });
          else if (item.kind === 'table') for (const line of item.rows) columnParagraphs.push({ label, text: line.text });
        }
        paragraphs.push(...columnParagraphs);
        for (const { text } of columnParagraphs) if (dielsPlace.test(text)) failures.push(`${label}: C9 Diels-page citation left in paragraph`);
        for (const { text } of columnParagraphs) if (danglingVgl(text.trimEnd())) {
          report.vglEnds.push({ work, column: seg.column, tail: Array.from(text.trimEnd()).slice(-30).join('') });
          if (!excepted(vglAllowlist, work, seg.column, undefined)) failures.push(`${label}: C7 paragraph ends in "vgl."`);
        }
        const expected = [...(contextSectionMarkerNumbers(seg) ?? [])].sort((a, b) => a - b);
        const actual = rows.flatMap(r => r.items.flatMap(i => i.kind === 'flow' && i.prose.sectionMarker !== undefined ? [Number(i.prose.sectionMarker)] : []));
        if (expected.length && JSON.stringify(expected) !== JSON.stringify(actual)) {
          const gap = { work, column: seg.column, expected, actual };
          report.sectionMismatches.push(gap);
          const allowed = allowlist.find(a => a.work === work && a.column === seg.column
            && a.reason?.trim() && JSON.stringify(a.expected) === JSON.stringify(expected) && JSON.stringify(a.actual) === JSON.stringify(actual));
          if (allowed) allowed.used = true;
          else failures.push(`${label}: C4 sections expected ${expected}; found ${actual}`);
        }
        for (const [i, span] of (seg.contextEnglish ?? []).entries()) {
          const owners = rows.filter(r => r.contextIndexes.includes(i));
          if (owners.length !== 1 || !owners[0].head || !sourceMatches(owners[0].head, span)) {
            const gap = { work, column: seg.column, index: i, sourceAuthor: span.sourceAuthor, sourceWork: span.sourceWork, locus: span.locus };
            report.contextMismatches.push(gap);
            const allowed = contextAllowlist.find(a => Object.entries(gap).every(([k, v]) => a[k] === v) && a.reason?.trim());
            // Exceptions permit only a separate, unassigned English row.
            // A span placed under a wrong source is always a failure.
            if (allowed && owners.length === 1 && !owners[0].head && !owners[0].items.length) allowed.used = true;
            else failures.push(`${label}: C5 contextEnglish[${i}] ${span.sourceAuthor}, ${span.sourceWork}`);
          }
        }
        for (const fault of headTextFaults(seg, rows)) failures.push(`${label}: C10 ${fault}`);
      } catch (error) { failures.push(`${label}: ${error.message}`); }
    }
  }
  if (!records.length) failures.push('No DK segments found');
  const checked = spawnSync(process.env.DK_PYTHON ?? 'python3', [join(root, 'scripts/dk-citation-locations.py')], {
    input: JSON.stringify({ segments, paragraphs: paragraphs.map(p => p.text), expansions: expansions.map(e => e.text) }),
    encoding: 'utf8', maxBuffer: 128 * 1024 * 1024,
  });
  if (checked.status !== 0) throw new Error(`Citation matcher failed: ${checked.error?.message ?? checked.stderr}`);
  const oracle = JSON.parse(checked.stdout);
  records.forEach(({ seg, label }, i) => {
    const locations = (seg.citationHeads ?? []).map(({ expanded, ...location }) => location);
    if (JSON.stringify(locations) !== JSON.stringify(oracle.heads[i])) failures.push(`${label}: C2 emitted locations differ from source matcher`);
  });
  oracle.paragraphHits.forEach((hits, i) => { if (hits.length) failures.push(`${paragraphs[i].label}: C1 source citation left in paragraph at ${hits.join(',')}`); });
  oracle.crossReferences.forEach((bad, i) => { if (bad) failures.push(`${expansions[i].label}: C3 pure DK cross-reference expansion`); });
  for (const entry of [...allowlist, ...contextAllowlist]) if (!entry.used) failures.push(`${entry.work}/${entry.column}: unused section-gap exception`);
  for (const entry of [...bracketAllowlist, ...vglAllowlist]) if (!entry.used) failures.push(`${entry.work}/${entry.column}: unused heading or "vgl." exception`);
} catch (error) {
  failures.push(error.message);
} finally {
  await server.close();
}
for (const w of report.works) console.log(`${w.work}: ${w.segments} columns, ${w.citations} citations, ${w.midlineSplits} mid-line splits`);
mkdirSync(join(root, 'build'), { recursive: true });
writeFileSync(join(root, 'build/dk-structure-report.json'), JSON.stringify(report, null, 2) + '\n');
for (const failure of failures) console.error(failure);
console.log(`DK structure: ${report.works.length} works; ${failures.length} failures. Report: build/dk-structure-report.json`);
process.exitCode = failures.length ? 1 : 0;
