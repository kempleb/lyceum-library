#!/usr/bin/env node
// Builds John's review dashboard: REVIEW-CHECKLIST.md -> a self-contained
// HTML file he can open on his phone, tick items in, and export back into
// the checklist via scripts/ingest-review-export.mjs.
//
// This is the rendering half of the mechanism whose parsing half is
// scripts/lib/review-checklist.mjs and whose return leg is
// scripts/ingest-review-export.mjs. See docs/review-dashboard.md for the
// whole loop.
//
// WHY IDS ARE NEVER INVENTED HERE: John's ticked state lives in his
// browser's localStorage, keyed by item id. An id minted fresh at render
// time (rather than read from the checklist's pinned `<!--id:...-->`
// comment) would silently detach whatever he'd already ticked under the
// old id -- exactly the bug the id-pinning migration
// (scripts/migrate-checklist-ids.mjs) exists to prevent. So: every item
// MUST already carry a pinned id, or this script fails loudly rather than
// generating one.
//
// KIND/CAT DERIVATION: scripts/lib/review-checklist.mjs deliberately does
// not derive the live dashboard's richer taxonomy (kind: decision |
// spot-check, cat: authors | features | site | ticket) because it isn't
// present in REVIEW-CHECKLIST.md's text. This script assigns its own
// simple, honest stand-ins so the export payload has the fields
// ingest-review-export.mjs expects: `kind` is 'decision' when the item's
// text (title or body) contains a ⚖ mark anywhere -- REVIEW-CHECKLIST.md's
// own header (see line 12) declares that convention -- else 'spot-check';
// `cat` mirrors the item's section ('active' | 'completed' | 'retired').
// Neither field is read by ingest-review-export.mjs's matching logic
// except `kind === 'decision'`, so this is a reasonable, low-stakes
// default -- see docs/review-dashboard.md for the open reconciliation.

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { parseChecklist } from './lib/review-checklist.mjs';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const REPO_ROOT = dirname(ROOT.replace(/\/$/, ''));
const DEFAULT_CHECKLIST = join(REPO_ROOT, 'REVIEW-CHECKLIST.md');
const DEFAULT_SHELL = join(ROOT, 'review-dashboard-shell.html');
const DEFAULT_OUT = join(REPO_ROOT, 'build', 'review-dashboard.html');

const SECTION_LABELS = {
  active: 'Active review queue',
  completed: 'Completed',
  retired: 'Retired',
};

/**
 * Turn parsed checklist items into the itemsData array embedded in the
 * dashboard shell. Throws with the offending item's number and title if any
 * item lacks a pinned id -- see module header.
 */
export function buildItemsData(items) {
  return items.map((item) => {
    if (!item.id) {
      const where = item.num != null ? `active item #${item.num}` : `a ${item.section} item`;
      throw new Error(
        `build-review-dashboard: ${where} has no pinned <!--id:...--> marker `
          + `(title: ${JSON.stringify(item.title)}). Run scripts/migrate-checklist-ids.mjs `
          + `or pin an id by hand before regenerating the dashboard -- a generated id would `
          + `silently detach John's ticked state.`,
      );
    }
    const text = `${item.title} ${item.body}`;
    const kind = text.includes('⚖') ? 'decision' : 'spot-check';
    return {
      id: item.id,
      num: item.num,
      section: item.section,
      sectionLabel: SECTION_LABELS[item.section] ?? item.section,
      kind,
      cat: item.section,
      title: item.title,
      body: item.body,
      done: item.done,
    };
  });
}

/** Render the full dashboard HTML from checklist markdown + a shell template. */
export function renderDashboard(checklistMarkdown, shellHtml) {
  if (!shellHtml.includes('__ITEMS_DATA__')) {
    throw new Error('build-review-dashboard: shell template is missing the __ITEMS_DATA__ token');
  }
  const items = parseChecklist(checklistMarkdown);
  const itemsData = buildItemsData(items);
  const json = JSON.stringify(itemsData);
  return shellHtml.replace('__ITEMS_DATA__', () => json);
}

function parseArgs(argv) {
  const args = { checklist: DEFAULT_CHECKLIST, shell: DEFAULT_SHELL, out: DEFAULT_OUT };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--checklist') args.checklist = resolve(argv[++i]);
    else if (arg === '--shell') args.shell = resolve(argv[++i]);
    else if (arg === '--out') args.out = resolve(argv[++i]);
    else throw new Error(`Unexpected argument: ${arg}`);
  }
  return args;
}

function main() {
  const { checklist, shell, out } = parseArgs(process.argv.slice(2));
  const checklistMarkdown = readFileSync(checklist, 'utf8');
  const shellHtml = readFileSync(shell, 'utf8');
  const html = renderDashboard(checklistMarkdown, shellHtml);
  const outDir = dirname(out);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
  writeFileSync(out, html, 'utf8');
  console.log(`Wrote ${out}`);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  try {
    main();
  } catch (err) {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  }
}
