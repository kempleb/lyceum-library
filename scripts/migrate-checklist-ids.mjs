#!/usr/bin/env node
// One-time migration: pin a stable `<!--id:...-->` comment onto every item in
// REVIEW-CHECKLIST.md that doesn't already have one, right after its
// checkbox (or its leading "- " for the unchecked Retired appendix).
//
// WHY THIS MATTERS -- READ BEFORE TOUCHING PINNED IDS:
// John's review dashboard is a claude.ai artifact; his ticked checkboxes
// live in the BROWSER's localStorage, keyed by each item's id. Ids are
// currently derived from item titles on every regeneration, so editing a
// title (which happens constantly -- items get "RULED"/"RESOLVED" prefixes
// stapled onto them) silently detaches his ticked state. Pinning the id in
// the markdown itself, once, fixes that: the id no longer moves just
// because the surrounding prose does.
//
// CONSEQUENCE: an id, once pinned, is LOAD-BEARING. Never regenerate or
// reslugify an id that is already present in the file -- that would repeat
// the exact bug this migration exists to fix, just one level down. This
// script is idempotent for that reason: it only ever ADDS an id comment
// where none exists; it never touches an existing one.
//
// CORRECTING AN ID BY HAND: ids are plain text in an HTML comment
// (`<!--id:some-slug-->`), immediately after the item's checkbox. To
// rename one, just edit that string directly in REVIEW-CHECKLIST.md --
// there is no derivation step to rerun, and nothing else in the file
// needs to change. (If the id is also referenced by an already-published
// dashboard export, reconcile that copy separately -- this script does not
// know about the live page.)
//
// SLUG RULE AND ITS EVIDENCE: ids are derived by slugifying the item's
// title (see scripts/lib/review-checklist.mjs `slugify`/`extractTitleAndMarker`)
// -- lowercase, non-alphanumerics collapsed to hyphens, trimmed. This is a
// *reconstruction*, not a read, of how the live dashboard derives ids: the
// live page needs authentication and can't be fetched from here. The one
// piece of real evidence available is a genuine export from the live
// dashboard (five items, see scripts/__tests__/review-checklist.test.ts),
// and this slug rule reproduces 3 of those 5 ids exactly when applied to
// the export's own title strings. The other 2 don't match -- their ids
// look like they were pinned from EARLIER, shorter/differently-worded
// titles than the ones in that export, i.e. exactly the drift this whole
// mechanism exists to stop. Once ids are pinned here, whatever the live
// page's real ids turn out to be, reconciling the two files is a manual,
// one-line-per-item edit -- see "CORRECTING AN ID BY HAND" above.
//
// Usage: node scripts/migrate-checklist-ids.mjs [path-to-REVIEW-CHECKLIST.md]

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  ACTIVE_ITEM_START_RE,
  BULLET_ITEM_START_RE,
  PLAIN_BULLET_START_RE,
  ID_COMMENT_RE,
  extractTitleAndMarker,
  slugify,
} from './lib/review-checklist.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url)).replace(/\/scripts$/, '');
const DEFAULT_PATH = join(ROOT, 'REVIEW-CHECKLIST.md');

function sectionBounds(markdown, headingRe, nextHeadingRe) {
  const startMatch = markdown.match(headingRe);
  if (!startMatch) return null;
  const start = startMatch.index + startMatch[0].length;
  let end = markdown.length;
  if (nextHeadingRe) {
    const rest = markdown.slice(start);
    const endMatch = rest.match(nextHeadingRe);
    if (endMatch) end = start + endMatch.index;
  }
  return { start, end };
}

/** Find every list-item start within [start, end), returning
 * {matchIndex, matchEnd, contentEnd} triples in file order. */
function itemStarts(markdown, start, end, startRe) {
  const all = [...markdown.matchAll(startRe)].filter(
    (m) => m.index >= start && m.index < end,
  );
  return all.map((m, i) => ({
    matchIndex: m.index,
    matchEnd: m.index + m[0].length,
    contentEnd: i + 1 < all.length ? all[i + 1].index : end,
  }));
}

/** Plan id insertions for one section; returns a list of {at, id} splice
 * points (in original-document coordinates) for items lacking an id. */
function planSection(markdown, start, end, startRe, usedSlugs) {
  const insertions = [];
  for (const { matchEnd, contentEnd } of itemStarts(markdown, start, end, startRe)) {
    const tail = markdown.slice(matchEnd, contentEnd);
    if (ID_COMMENT_RE.test(tail)) continue; // already pinned -- never touch it
    const { title } = extractTitleAndMarker(tail);
    const base = slugify(title) || 'item';
    let slug = base;
    let n = 2;
    while (usedSlugs.has(slug)) {
      slug = `${base}-${n}`;
      n += 1;
    }
    usedSlugs.add(slug);
    insertions.push({ at: matchEnd, id: slug });
  }
  return insertions;
}

export function migrate(markdown) {
  const usedSlugs = new Set(
    [...markdown.matchAll(new RegExp(ID_COMMENT_RE, 'g'))].map((m) => m[1]),
  );

  const active = sectionBounds(
    markdown,
    /^##\s+Active review queue.*$/m,
    /^##\s+Completed\s*$/m,
  );
  const completed = sectionBounds(
    markdown,
    /^##\s+Completed\s*$/m,
    /^##\s+Retired.*$/m,
  );
  const retired = sectionBounds(markdown, /^##\s+Retired.*$/m, null);

  let insertions = [];
  if (active) insertions.push(...planSection(markdown, active.start, active.end, ACTIVE_ITEM_START_RE, usedSlugs));
  if (completed) insertions.push(...planSection(markdown, completed.start, completed.end, BULLET_ITEM_START_RE, usedSlugs));
  if (retired) insertions.push(...planSection(markdown, retired.start, retired.end, PLAIN_BULLET_START_RE, usedSlugs));

  // Apply back-to-front so earlier splice points stay valid.
  insertions.sort((a, b) => b.at - a.at);
  let result = markdown;
  for (const { at, id } of insertions) {
    result = result.slice(0, at) + `<!--id:${id}--> ` + result.slice(at);
  }
  return { markdown: result, added: insertions.length };
}

function main() {
  const path = process.argv[2] || DEFAULT_PATH;
  const original = readFileSync(path, 'utf8');
  const { markdown, added } = migrate(original);
  if (added === 0) {
    console.log('No items needed an id -- file already fully pinned. Nothing written.');
    return;
  }
  writeFileSync(path, markdown);
  console.log(`Pinned ${added} new id(s) in ${path}.`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
