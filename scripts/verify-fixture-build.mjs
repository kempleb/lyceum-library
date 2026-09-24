#!/usr/bin/env node
// Verifies a PUBLIC_READER_FIXTURES=1 build actually produced a working
// sample-author/sample-work site — the only way to prove the book-section
// citation scheme and author-scoped routing end to end, since CI carries no
// real corpus data (see app/scripts/stage-fixtures.mjs). Checked, empirically
// against a real build rather than assumed:
//   (a) the author/work/book pages exist;
//   (b) a book page's segments render their `col-{column}` anchors (how
//       Reader.svelte actually emits a section anchor — see
//       shared/components/Reader.svelte's `id="col-{seg.column}"` — NOT the
//       bare "1.1" the column token itself reads as);
//   (c) /authors/ lists sample-author;
//   (d) the fixture book page carries the HOME > AUTHOR > WORK breadcrumb as
//       real links (home, author landing, work landing) with the switcher
//       placeholders (see app/src/components/Breadcrumb.svelte).
// Exits nonzero with a clear message on any failure.
import { promises as fs } from 'node:fs';
import path from 'node:path';

function usage(message) {
  if (message) console.error(message);
  console.error('Usage: node scripts/verify-fixture-build.mjs [DIST_DIR]');
  process.exit(2);
}

function getDist() {
  const arg = process.argv[2];
  return path.resolve(arg || path.resolve(import.meta.dirname, '..', 'app', 'dist', 'client'));
}

async function readFile(dist, rel) {
  try {
    return await fs.readFile(path.join(dist, rel), 'utf8');
  } catch {
    return null;
  }
}

async function main() {
  const dist = getDist();
  let stat;
  try { stat = await fs.stat(dist); } catch { usage(`Dist directory does not exist: ${dist}`); }
  if (!stat.isDirectory()) usage(`Dist path is not a directory: ${dist}`);

  const failures = [];
  const check = (ok, message) => { if (!ok) failures.push(message); };

  // (a) The author, landing, and book pages exist. The work's landing page
  // now lives at texts/<author>/<work>/ (workLanding); the old
  // <author>/<work>/ address is kept only as a forwarder to it (see (a2)
  // below), so it must not be mistaken for the real page here.
  const pages = {
    authorIndex: 'sample-author/index.html',
    workLanding: 'texts/sample-author/sample-work/index.html',
    book1: 'read/sample-author/sample-work/book-1/index.html',
    book2: 'read/sample-author/sample-work/book-2/index.html',
  };
  const html = {};
  for (const [key, rel] of Object.entries(pages)) {
    html[key] = await readFile(dist, rel);
    check(html[key] !== null, `missing page: ${rel}`);
  }
  if (html.workLanding !== null) {
    check(
      !html.workLanding.includes('http-equiv="refresh"'),
      `${pages.workLanding}: is a meta-refresh forwarder, expected the real landing page`,
    );
  }

  // (a2) The old landing address is now a forwarder pointing at the new one.
  const oldLanding = await readFile(dist, 'sample-author/sample-work/index.html');
  check(oldLanding !== null, 'missing page: sample-author/sample-work/index.html (old landing forwarder)');
  if (oldLanding !== null) {
    check(
      oldLanding.includes('http-equiv="refresh"'),
      'sample-author/sample-work/index.html: expected a meta-refresh forwarder to the new landing page',
    );
    check(
      /url=[^"]*\/texts\/sample-author\/sample-work\/?/.test(oldLanding),
      'sample-author/sample-work/index.html: forwarder does not target /texts/sample-author/sample-work/',
    );
  }

  // (b) Each book page renders its sections' segment anchors — Reader.svelte
  // emits `id="col-{seg.column}"` per segment (see shared/components/Reader.svelte),
  // so a book-section work's book 1 carries id="col-1.1".."col-1.4" and book 2
  // carries id="col-2.1".."col-2.4" — matching fixtures/data/sample-work/.
  const expectAnchors = {
    book1: ['col-1.1', 'col-1.2', 'col-1.3', 'col-1.4'],
    book2: ['col-2.1', 'col-2.2', 'col-2.3', 'col-2.4'],
  };
  for (const [key, anchors] of Object.entries(expectAnchors)) {
    if (html[key] === null) continue; // already reported missing above
    for (const anchor of anchors) {
      check(html[key].includes(`id="${anchor}"`), `${pages[key]}: missing section anchor id="${anchor}"`);
    }
  }

  // (c) /authors/ lists sample-author as an actual link into its landing
  // page — not just the text "Sample Author" appearing somewhere on the
  // page, which plain-text matching would have let a broken/missing <a>
  // slip past.
  const authorsIndex = await readFile(dist, 'authors/index.html');
  check(authorsIndex !== null, 'missing page: authors/index.html');
  if (authorsIndex !== null) {
    check(
      /href="[^"]*\/sample-author\/?"/.test(authorsIndex),
      'authors/index.html has no href link to /sample-author/',
    );
  }

  // (d) The book page's breadcrumb: a real nav with real links — home ("/"),
  // the author's landing, the work's landing — plus the two switcher selects'
  // placeholder options. Checked inside the breadcrumb nav element itself so
  // an identical href elsewhere on the page can't mask a broken breadcrumb.
  if (html.book1 !== null) {
    const navMatch = html.book1.match(/<nav[^>]*aria-label="Breadcrumb"[\s\S]*?<\/nav>/);
    check(navMatch !== null, `${pages.book1}: missing <nav aria-label="Breadcrumb">`);
    if (navMatch) {
      const nav = navMatch[0];
      const wanted = [
        ['href="/"', 'home link'],
        ['href="/sample-author"', 'author landing link'],
        ['href="/texts/sample-author/sample-work/"', 'work landing link'],
        ['Switch author', 'author switcher placeholder'],
        ['Switch work', 'work switcher placeholder'],
      ];
      for (const [needle, label] of wanted) {
        check(nav.includes(needle), `${pages.book1}: breadcrumb missing ${label} (${needle})`);
      }
    }
  }

  if (failures.length) {
    console.error(`verify-fixture-build: ${failures.length} check(s) failed:`);
    for (const f of failures) console.error(`  - ${f}`);
    process.exit(1);
  }

  console.log(`verify-fixture-build: OK (${dist})`);
}

main().catch(error => {
  console.error(`verify-fixture-build failed: ${error.stack || error}`);
  process.exit(2);
});
