#!/usr/bin/env node
// Dependency-free link checker for the emitted Astro site (Node 22+).
import { promises as fs } from 'node:fs';
import path from 'node:path';

const BASE = process.env.READER_BASE_PATH || '';
const MAX_ID_CACHE = 6000;
const MAX_REPORTS = 200;

function usage(message) {
  if (message) console.error(message);
  console.error('Usage: node scripts/check-links.mjs [DIST_DIR | --dist=DIST_DIR]');
  process.exit(2);
}

function getDist() {
  const args = process.argv.slice(2);
  let dist;
  for (const arg of args) {
    if (arg.startsWith('--dist=')) {
      if (dist) usage('Specify the dist directory only once.');
      dist = arg.slice(7);
    } else if (arg.startsWith('-')) {
      usage(`Unknown option: ${arg}`);
    } else if (!dist) {
      dist = arg;
    } else {
      usage('Specify the dist directory only once.');
    }
  }
  return path.resolve(dist || path.resolve(import.meta.dirname, '..', 'app', 'dist', 'client'));
}

function decodeEntities(value) {
  return value
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#(x[0-9a-f]+|\d+);/gi, (_, n) => String.fromCodePoint(n[0].toLowerCase() === 'x' ? parseInt(n.slice(1), 16) : parseInt(n, 10)));
}

function decodePath(value) {
  try { return decodeURIComponent(value); } catch { return value; }
}

function splitReference(reference) {
  const hash = reference.indexOf('#');
  const beforeHash = hash < 0 ? reference : reference.slice(0, hash);
  const fragment = hash < 0 ? null : decodePath(reference.slice(hash + 1));
  const question = beforeHash.indexOf('?');
  return {
    pathname: question < 0 ? beforeHash : beforeHash.slice(0, question),
    query: question < 0 ? '' : beforeHash.slice(question + 1),
    fragment,
  };
}

function isExternal(reference) {
  return /^(?:https?:|mailto:|tel:|\/\/)/i.test(reference);
}

function attributeValue(tag, attribute) {
  const match = new RegExp(
    "\\b" + attribute + "\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)'|([^\\s\"'=<>`]+))",
    'i',
  ).exec(tag);
  return match ? match[1] ?? match[2] ?? match[3] : null;
}

// A `col-<column>` fragment resolves case-insensitively: the Lyceum partner
// manifest's navigation.loci hrefs lowercase only the fragment (its schema is
// lowercase-only), e.g. "#col-b30", while the page's own element id keeps the
// column's real case, "col-B30" (see the matching Reader.svelte fallback).
function fragmentResolves(ids, fragment) {
  if (!ids) return false;
  if (ids.has(fragment)) return true;
  const lower = fragment.toLowerCase();
  if (!lower.startsWith('col-')) return false;
  for (const id of ids) {
    if (id.toLowerCase() === lower) return true;
  }
  return false;
}

async function existsFile(file) {
  try { return (await fs.stat(file)).isFile(); } catch { return false; }
}

async function* htmlFiles(dir) {
  let entries;
  try { entries = await fs.readdir(dir, { withFileTypes: true }); } catch { return; }
  for (const entry of entries) {
    const child = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(child);
    else if (entry.isFile() && entry.name.toLowerCase().endsWith('.html')) yield child;
  }
}

function virtualDirectory(dist, source) {
  const relative = path.relative(dist, source);
  return path.dirname(relative) === '.' ? '' : path.dirname(relative);
}

async function main() {
  const dist = getDist();
  let stat;
  try { stat = await fs.stat(dist); } catch { usage(`Dist directory does not exist: ${dist}`); }
  if (!stat.isDirectory()) usage(`Dist path is not a directory: ${dist}`);

  let pages = 0;
  let links = 0;
  let anchors = 0;
  const broken = [];
  const idCache = new Map();
  const report = (source, href, reason) => broken.push({ source: path.relative(dist, source), href, reason });

  async function idsFor(file) {
    if (idCache.has(file)) {
      const ids = idCache.get(file);
      idCache.delete(file);
      idCache.set(file, ids);
      return ids;
    }
    let html;
    try { html = await fs.readFile(file, 'utf8'); } catch { return null; }
    const ids = new Set();
    for (const match of html.matchAll(/\bid\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi)) {
      ids.add(decodeEntities(match[1] ?? match[2] ?? match[3]));
    }
    idCache.set(file, ids);
    if (idCache.size > MAX_ID_CACHE) idCache.delete(idCache.keys().next().value);
    return ids;
  }

  async function resolve(source, pathname) {
    let relative;
    if (!pathname) return source;
    if (pathname.startsWith('/')) {
      let rooted = decodePath(pathname);
      if (rooted === BASE || rooted === `${BASE}/`) rooted = '/';
      else if (rooted.startsWith(`${BASE}/`)) rooted = rooted.slice(BASE.length);
      relative = rooted.replace(/^\/+/, '');
    } else {
      relative = path.join(virtualDirectory(dist, source), decodePath(pathname));
    }
    relative = path.normalize(relative);
    if (relative === '.') relative = '';
    if (relative.startsWith('..') || path.isAbsolute(relative)) return null;
    const candidate = path.join(dist, relative);
    for (const file of [candidate, path.join(candidate, 'index.html'), `${candidate}.html`]) {
      if (await existsFile(file)) return file;
    }
    return null;
  }

  async function checkReference(source, raw, kind) {
    const href = decodeEntities(raw.trim());
    if (!href || href.startsWith('#')) {
      if (href.startsWith('#') && href.length > 1) {
        anchors++;
        const ids = await idsFor(source);
        if (!ids?.has(decodePath(href.slice(1)))) report(source, raw, 'fragment id not found');
      }
      return;
    }
    if (isExternal(href) || (kind !== 'a' && /^data:/i.test(href))) return;
    links++;
    const parts = splitReference(href);
    const target = await resolve(source, parts.pathname);
    if (!target) {
      report(source, raw, 'target does not exist');
      return;
    }
    if (parts.fragment) {
      anchors++;
      const ids = await idsFor(target);
      if (!fragmentResolves(ids, parts.fragment)) report(source, raw, 'fragment id not found');
    }
    const loc = parts.query.match(/(?:^|&)loc=([^&]*)/i);
    if (loc) {
      anchors++;
      const value = decodePath(loc[1]);
      // `loc={column}:{line}` — a Greek-line-level citation target (bekker/busse,
      // or the internal line-precise form of a stephanus deep link).
      const match = value.match(/^([^:]+):(\d+)$/);
      if (match) {
        const ids = await idsFor(target);
        if (!ids?.has(`L${match[1]}-${match[2]}`) && !ids?.has(`L${match[1]}-${match[2]}-c`)) {
          report(source, raw, `citation target L${match[1]}-${match[2]} not found`);
        }
      } else if (value && !value.includes(':')) {
        // `loc={column}` — a bare column with no line, e.g. a stephanus work's
        // section-token-only jump ("?loc=17a"). This targets the column-level
        // segment anchor (`col-{column}`), not a line-level `L{column}-{n}` id.
        const ids = await idsFor(target);
        if (!ids?.has(`col-${value}`)) {
          report(source, raw, `citation target col-${value} not found`);
        }
      }
    }
  }

  for await (const source of htmlFiles(dist)) {
    pages++;
    let html;
    try { html = await fs.readFile(source, 'utf8'); } catch { report(source, '', 'cannot read HTML'); continue; }
    const tags = html.matchAll(/<(a|img|link|script|meta)\b[^>]*>/gi);
    for (const tagMatch of tags) {
      const kind = tagMatch[1].toLowerCase();
      if (kind === 'meta') {
        if (attributeValue(tagMatch[0], 'http-equiv')?.toLowerCase() !== 'refresh') continue;
        const content = attributeValue(tagMatch[0], 'content');
        const refresh = content?.match(/^\s*\d+(?:\.\d+)?\s*;\s*url\s*=\s*(.+?)\s*$/i);
        if (refresh) await checkReference(source, refresh[1], kind);
        continue;
      }
      const attribute = (kind === 'img' || kind === 'script') ? 'src' : 'href';
      const reference = attributeValue(tagMatch[0], attribute);
      if (reference) await checkReference(source, reference, kind);
    }
  }

  // Lemma entries are CLIENT-RENDERED: one page per language at
  // /lemma/<lang>/entry/ resolves any word via ?w=<slug>, rather than a static
  // page per lemma. (Pre-rendering them put 12,587 files against Cloudflare
  // Pages' 20,000-file cap — a ceiling the corpus would have breached at the
  // Plato/Aristotle migration. John ruled 2026-08-04 that the lexicon is a
  // tool, not SEO surface, so static indexability was not a requirement.)
  //
  // The old bidirectional invariant (every index entry has a page, every page
  // is indexed) still holds — it just binds the index to the DATA the island
  // fetches. An orphan either way is still a broken lexicon link.
  for (const [lang, dir] of [['grc', 'lemmata'], ['lat', 'lemmata-lat']]) {
    const indexFile = path.join(dist, 'data', dir, '_index.json');
    try {
      const entries = JSON.parse(await fs.readFile(indexFile, 'utf8'));
      const indexed = new Set((Array.isArray(entries) ? entries : []).map(entry => typeof entry === 'string' ? entry : entry?.slug).filter(Boolean));
      // Every index entry must have the JSON the entry page fetches.
      for (const slug of indexed) {
        if (!await existsFile(path.join(dist, 'data', dir, `${slug}.json`))) report(indexFile, slug, 'lemma index entry has no data file');
      }
      // ...and every data file must be reachable from the index.
      for (const name of await fs.readdir(path.join(dist, 'data', dir))) {
        if (!name.endsWith('.json') || name === '_index.json') continue;
        const slug = name.slice(0, -5);
        if (!indexed.has(slug)) report(path.join(dist, 'data', dir), slug, 'lemma data file missing from index');
      }
      // The single route that renders all of them must exist, or every
      // lexicon link 404s while both checks above still pass.
      if (indexed.size && !await existsFile(path.join(dist, 'lemma', lang, 'entry', 'index.html'))) {
        report(indexFile, `${lang}/entry`, 'lemma entry route is missing');
      }
    } catch (error) {
      if (error?.code === 'ENOENT') console.log(`Note: data/${dir}/_index.json is absent; skipping ${lang} lemma cross-check.`);
      else report(indexFile, '', 'cannot read lemma index');
    }
  }

  // A dist with no pages (or no homepage) is a failed build, not a clean one —
  // this gate must never bless an empty directory.
  if (pages === 0) usage(`No HTML pages found under ${dist} — not a built site.`);
  if (!(await existsFile(path.join(dist, 'index.html')))) {
    usage(`No index.html at the root of ${dist} — not a complete site build.`);
  }

  console.log(`Pages crawled: ${pages}; links checked: ${links}; anchors checked: ${anchors}; broken: ${broken.length}`);
  for (const failure of broken.slice(0, MAX_REPORTS)) console.log(`${failure.source} -> ${failure.href} (${failure.reason})`);
  if (broken.length > MAX_REPORTS) console.log(`+${broken.length - MAX_REPORTS} more`);
  process.exitCode = broken.length ? 1 : 0;
}

main().catch(error => {
  console.error(`Link checker failed: ${error.stack || error}`);
  process.exit(2);
});
