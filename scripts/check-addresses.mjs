#!/usr/bin/env node
// Address-stability gate for the emitted Astro site (Node 22+, standard
// library only). Readers bookmark and cite our pages, so a page address that
// existed in the last public release must never quietly disappear from a new
// one. This compares the live page addresses in a built dist directory
// against a committed baseline (scripts/address-baseline.txt) and fails when
// any baseline address is missing. New addresses are fine.
//
// "Address" here uses the same file<->URL convention scripts/check-links.mjs
// relies on when it resolves an href to a candidate file: a directory's
// index.html serves the directory address ("foo/index.html" -> "/foo/"), and
// any other file serves its own name minus ".html" ("404.html" -> "/404").
// Keeping that convention here (rather than inventing a second one) is what
// keeps this script and check-links.mjs in agreement about what a "page" is.
import { promises as fs } from 'node:fs';
import path from 'node:path';

const MAX_REPORTS = 200;
const BASELINE_FILE = path.resolve(import.meta.dirname, 'address-baseline.txt');

function usage(message) {
  if (message) console.error(message);
  console.error('Usage: node scripts/check-addresses.mjs [DIST_DIR | --dist=DIST_DIR] [--update]');
  process.exit(2);
}

function parseArgs(argv) {
  let dist;
  let update = false;
  for (const arg of argv) {
    if (arg === '--update') {
      update = true;
    } else if (arg.startsWith('--dist=')) {
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
  return {
    dist: path.resolve(dist || path.resolve(import.meta.dirname, '..', 'app', 'dist', 'client')),
    update,
  };
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

// Inverse of check-links.mjs's resolve() candidates (candidate,
// candidate/index.html, candidate.html): given a dist-relative file, produce
// the site address that would resolve back to it.
function addressFor(dist, file) {
  const relative = path.relative(dist, file).split(path.sep).join('/');
  if (path.basename(relative) === 'index.html') {
    const dir = relative.slice(0, -'index.html'.length);
    return `/${dir}`;
  }
  return `/${relative.slice(0, -'.html'.length)}`;
}

async function collectAddresses(dist) {
  const addresses = new Set();
  for await (const file of htmlFiles(dist)) {
    addresses.add(addressFor(dist, file));
  }
  return addresses;
}

async function readBaseline(file) {
  let text;
  try {
    text = await fs.readFile(file, 'utf8');
  } catch (error) {
    if (error?.code === 'ENOENT') {
      usage(`Baseline file does not exist: ${file} (run with --update to create it from a verified real build).`);
    }
    throw error;
  }
  return new Set(text.split('\n').map((line) => line.trim()).filter(Boolean));
}

function sorted(set) {
  return [...set].sort();
}

async function writeBaseline(file, addresses) {
  const lines = sorted(addresses);
  await fs.writeFile(file, lines.length ? `${lines.join('\n')}\n` : '');
  return lines;
}

async function main() {
  const { dist, update } = parseArgs(process.argv.slice(2));

  let stat;
  try { stat = await fs.stat(dist); } catch { usage(`Dist directory does not exist: ${dist}`); }
  if (!stat.isDirectory()) usage(`Dist path is not a directory: ${dist}`);

  const current = await collectAddresses(dist);
  if (current.size === 0) usage(`No HTML pages found under ${dist} -- not a built site.`);

  if (update) {
    const lines = await writeBaseline(BASELINE_FILE, current);
    console.log(`Wrote ${lines.length} address(es) to ${path.relative(process.cwd(), BASELINE_FILE)}`);
    process.exitCode = 0;
    return;
  }

  const baseline = await readBaseline(BASELINE_FILE);
  const missing = sorted(new Set([...baseline].filter((address) => !current.has(address))));
  const added = sorted(new Set([...current].filter((address) => !baseline.has(address))));

  if (missing.length) {
    console.error(`${missing.length} address(es) from the baseline (${baseline.size}) are missing from the build (${current.size}):`);
    for (const address of missing.slice(0, MAX_REPORTS)) console.error(`  ${address}`);
    if (missing.length > MAX_REPORTS) console.error(`  +${missing.length - MAX_REPORTS} more`);
    console.error('Dropping a published address needs John\'s approval. Once approved, run with --update to record the new list.');
    process.exitCode = 1;
    return;
  }

  console.log(`Addresses checked: ${current.size}; baseline: ${baseline.size}; missing: 0`);
  if (added.length) {
    console.log(`${added.length} new addresses not in the baseline; run with --update to record them`);
  }
  process.exitCode = 0;
}

main().catch((error) => {
  console.error(`Address checker failed: ${error.stack || error}`);
  process.exit(2);
});
