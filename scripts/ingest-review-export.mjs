#!/usr/bin/env node
// Ingests John's review-export.json (downloaded from the review dashboard's
// "Send to Claude" button) into REVIEW-CHECKLIST.md, and prints proposed
// CANON.md rows for any decisions found.
//
// Contract of review-export.json, verified against a real export
// (2026-07-28, uploads/.../reviewexport2.json):
//   {
//     exported: "<ISO timestamp>",
//     items: [{ id, title, section, kind, cat, state, note }, ...],
//     tickets: [...]
//   }
// - state is "ok" | "issue" | null.
// - kind includes at least "decision"; other kinds (e.g. spot-checks) get
//   plain tick/flag treatment, no RULED annotation, no CANON row.
// - ASSUMPTION (tickets): the real export's tickets array was empty, so its
//   shape is unverified. We treat it conservatively: any non-empty tickets
//   array is reported (each ticket dumped to stderr) but never auto-applied
//   to REVIEW-CHECKLIST.md or CANON.md — creating new checklist items is a
//   judgment call, not a mechanical ingest. Extend ticket handling only once
//   a real populated example exists.
//
// Matching (step 1 of the brief): by id, against the checklist's pinned
// `<!--id:...-->` markers. Another agent owns scripts/lib/review-checklist.mjs
// and is adding those markers; this script prefers that parser when present
// and falls back to a small local one otherwise. All matching logic is
// isolated in loadChecklistItems() so it is a one-function swap once the
// shared parser lands.
//
// Idempotency: every applied annotation is paired with a hidden
// `<!--ingested:<id>:<hash>-->` marker (hash of the export item's
// state+note+kind). Re-running with the same export sees the same hash
// already present and makes no change to that line.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const DEFAULT_CHECKLIST = join(ROOT, 'REVIEW-CHECKLIST.md');

const ID_MARKER_RE = /<!--\s*id\s*:\s*([\w-]+)\s*-->/i;
const CHECKBOX_LINE_RE = /^(\s*)(\d+\.|-)(\s*)\[( |x|X)\](\s*)(.*)$/;
const RULING_TZ = 'America/Chicago';

// ---------------------------------------------------------------------------
// Checklist loading — the one function to swap once
// scripts/lib/review-checklist.mjs exists.
// ---------------------------------------------------------------------------

/**
 * Returns an array of { id, lineIndex, checked, content, raw } for every
 * checklist line that carries a pinned id marker.
 */
async function loadChecklistItems(checklistPath) {
  const libPath = join(ROOT, 'scripts', 'lib', 'review-checklist.mjs');
  if (existsSync(libPath)) {
    const mod = await import(libPath);
    if (typeof mod.parseChecklist === 'function') {
      const content = readFileSync(checklistPath, 'utf8');
      const parsed = mod.parseChecklist(content);
      // Expected shape (best guess, adjust if the real parser differs):
      // { items: [{ id, lineIndex, checked, content }] }
      if (Array.isArray(parsed?.items)) return parsed.items;
    }
  }
  return parseChecklistFallback(readFileSync(checklistPath, 'utf8'));
}

function parseChecklistFallback(text) {
  const lines = text.split('\n');
  const items = [];
  lines.forEach((line, lineIndex) => {
    const idMatch = line.match(ID_MARKER_RE);
    if (!idMatch) return;
    const checkboxMatch = line.match(CHECKBOX_LINE_RE);
    if (!checkboxMatch) return;
    const checked = checkboxMatch[4].toLowerCase() === 'x';
    items.push({ id: idMatch[1], lineIndex, checked, content: line });
  });
  return items;
}

// ---------------------------------------------------------------------------
// Export loading + validation
// ---------------------------------------------------------------------------

function loadExport(exportPath) {
  const raw = readFileSync(exportPath, 'utf8');
  const data = JSON.parse(raw);
  if (!data || typeof data !== 'object') {
    throw new Error(`${exportPath}: not a JSON object`);
  }
  if (!Array.isArray(data.items)) {
    throw new Error(`${exportPath}: missing "items" array`);
  }
  for (const item of data.items) {
    if (!item || typeof item.id !== 'string' || !item.id) {
      throw new Error(`${exportPath}: item missing string "id": ${JSON.stringify(item)}`);
    }
    if (item.state !== 'ok' && item.state !== 'issue' && item.state !== null && item.state !== undefined) {
      throw new Error(`${exportPath}: item ${item.id} has unexpected state ${JSON.stringify(item.state)}`);
    }
  }
  return {
    exported: data.exported ?? null,
    items: data.items,
    tickets: Array.isArray(data.tickets) ? data.tickets : [],
  };
}

// John's ruling date is the export timestamp read in his own timezone, not
// the UTC calendar date and not today's clock — an export taken shortly
// after midnight UTC is still "yesterday evening" for him, and that's the
// date that belongs in CANON.md.
function shortDate(isoOrNull) {
  const iso = isoOrNull ?? new Date().toISOString();
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: RULING_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(d);
  const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${map.year}-${map.month}-${map.day}`;
}

// Quote glyphs are cosmetic — a hand-typed annotation may render John's
// verbatim note with straight or curly, single or double quotes depending on
// who typed it. Strip them out before comparing so "'Sophists'" and
// "\"Sophists\"" are recognized as the same words.
function normalizeForCompare(s) {
  return (s ?? '')
    .replace(/[‘’‚‛'`´]/g, '')
    .replace(/[“”„‟"]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// Splits a checklist line's post-checkbox text into the pinned id marker and
// the surrounding body, remembering whether the marker sat at the very front
// (the canonical migrated position) so a rewrite can put it back there
// instead of letting it drift into the middle of the text.
function extractIdMarker(rest) {
  const match = rest.match(ID_MARKER_RE);
  if (!match) return { idText: null, atStart: false, body: rest };
  const idText = match[0];
  const before = rest.slice(0, match.index);
  const after = rest.slice(match.index + idText.length);
  const atStart = before.trim().length === 0;
  const body = `${before}${after}`.replace(/\s{2,}/g, ' ').trim();
  return { idText, atStart, body };
}

function itemHash(item) {
  const h = createHash('sha1');
  h.update(JSON.stringify({ id: item.id, kind: item.kind, state: item.state ?? null, note: item.note ?? '' }));
  return h.digest('hex').slice(0, 8);
}

function cleanTitle(title) {
  return (title ?? '').replace(/\*\*/g, '').trim();
}

// ---------------------------------------------------------------------------
// Applying one export item to one checklist line
// ---------------------------------------------------------------------------

/**
 * Returns { newLine, changed, canonRow|null } for applying `exportItem` to
 * `checklistItem.content` (the full raw checklist line, id marker included).
 */
function applyItemToLine(checklistItem, exportItem, dateStr) {
  const hash = itemHash(exportItem);
  const ingestedRe = new RegExp(`<!--ingested:${exportItem.id}:([a-f0-9]{8})-->`);
  const existingIngested = checklistItem.content.match(ingestedRe);
  if (existingIngested && existingIngested[1] === hash) {
    return { newLine: checklistItem.content, changed: false, canonRow: null };
  }

  const checkboxMatch = checklistItem.content.match(CHECKBOX_LINE_RE);
  if (!checkboxMatch) {
    throw new Error(`checklist line for id ${exportItem.id} is not a checkbox line: ${checklistItem.content}`);
  }
  const [, indent, marker, gapAfterMarker, , gapAfterBox, rest] = checkboxMatch;
  const { idText, atStart, body } = extractIdMarker(rest);

  const state = exportItem.state ?? null;
  const note = (exportItem.note ?? '').trim();
  const isDecision = exportItem.kind === 'decision' && note.length > 0;

  // A ruling is "already recorded" if John's verbatim note already appears
  // somewhere in the item body — regardless of whether a human or this
  // script put it there, and regardless of RULED-text wording or date, both
  // of which can legitimately differ from a hand-written annotation.
  const alreadyRecorded = isDecision && normalizeForCompare(body).includes(normalizeForCompare(note));

  // Tick determination: ok -> ticked, issue -> unticked, null -> unchanged.
  let tick = checkboxMatch[4].toLowerCase() === 'x' ? 'x' : ' ';
  if (state === 'ok') tick = 'x';
  else if (state === 'issue') tick = ' ';

  let newBody = body;
  let annotated = false;
  if (isDecision && !alreadyRecorded) {
    const icon = state === 'ok' ? '✅' : '⚑';
    const title = cleanTitle(exportItem.title);
    newBody = `**${icon} RULED ${dateStr} — ${title}** (John: "${note}"). Original item: ${body}`;
    annotated = true;
  } else if (!isDecision && state === 'issue' && note.length > 0) {
    newBody = `${body} **⚑ JOHN ${dateStr} (dashboard): "${note}"**`;
    annotated = true;
  }
  // isDecision && alreadyRecorded, state === 'ok' non-decision, or
  // state === null: body is untouched.

  const originalTick = checkboxMatch[4].toLowerCase() === 'x' ? 'x' : ' ';
  const tickChanged = tick !== originalTick;

  let canonRow = null;
  if (isDecision && !alreadyRecorded) {
    const title = cleanTitle(exportItem.title);
    canonRow = `| ${title} | ${note} | decided by John ${dateStr} |`;
  }

  // Nothing to apply: no tick change, no visible annotation. Leave the line
  // byte-for-byte alone rather than stamping an invisible marker on a
  // genuine no-op (e.g. a decision export shows up before John has ruled,
  // or the ruling is already recorded and the tick already matches).
  if (!tickChanged && !annotated) {
    return { newLine: checklistItem.content, changed: false, canonRow: null, alreadyRecorded };
  }

  // Reinsert the pinned id marker at the same relative position it held
  // before the rewrite — immediately in front if that's canonically where
  // the migration put it, otherwise trailing — so it never drifts into the
  // middle of the annotated text.
  let newRest = idText ? (atStart ? `${idText} ${newBody}` : `${newBody} ${idText}`) : newBody;

  // Strip any stale ingested marker for this id (a prior, different export
  // state for the same item), then append the fresh one.
  newRest = newRest.replace(new RegExp(`\\s*<!--ingested:${exportItem.id}:[a-f0-9]{8}-->`), '');
  newRest = `${newRest} <!--ingested:${exportItem.id}:${hash}-->`;

  const newLine = `${indent}${marker}${gapAfterMarker}[${tick}]${gapAfterBox}${newRest}`;

  return { newLine, changed: newLine !== checklistItem.content, canonRow, alreadyRecorded };
}

// ---------------------------------------------------------------------------
// Top-level ingest
// ---------------------------------------------------------------------------

async function ingest({ exportPath, checklistPath, dryRun }) {
  const exportData = loadExport(exportPath);
  const checklistText = readFileSync(checklistPath, 'utf8');
  const lines = checklistText.split('\n');
  const checklistItems = await loadChecklistItems(checklistPath);
  const byId = new Map(checklistItems.map((it) => [it.id, it]));

  const dateStr = shortDate(exportData.exported);
  const matched = [];
  const unmatched = [];
  const canonRows = [];
  let anyChange = false;

  for (const exportItem of exportData.items) {
    const checklistItem = byId.get(exportItem.id);
    if (!checklistItem) {
      unmatched.push(exportItem);
      continue;
    }
    const { newLine, changed, canonRow, alreadyRecorded } = applyItemToLine(checklistItem, exportItem, dateStr);
    if (changed) {
      lines[checklistItem.lineIndex] = newLine;
      anyChange = true;
    }
    if (canonRow) canonRows.push(canonRow);
    matched.push({ exportItem, checklistItem, changed, alreadyRecorded });
  }

  const newText = lines.join('\n');

  return {
    exportData,
    matched,
    unmatched,
    canonRows,
    anyChange,
    originalText: checklistText,
    newText,
    tickets: exportData.tickets,
  };
}

function printReport(result, { checklistPath, dryRun }) {
  const { matched, unmatched, canonRows, anyChange, tickets } = result;
  const changedCount = matched.filter((m) => m.changed).length;
  const noopCount = matched.length - changedCount;

  const alreadyRecorded = matched.filter((m) => m.alreadyRecorded);

  console.log(`Checklist: ${checklistPath}`);
  console.log(`Matched: ${matched.length} (applied: ${changedCount}, already up to date: ${noopCount})`);

  if (alreadyRecorded.length > 0) {
    console.log(`\nAlready recorded (John's verbatim note already present — ruling not re-applied):`);
    for (const m of alreadyRecorded) {
      console.log(`  - ${m.exportItem.id}${m.changed ? ' (tick updated)' : ''}`);
    }
  }

  if (unmatched.length > 0) {
    console.error(`\nUNMATCHED IDS — no checklist item found (feedback NOT applied):`);
    for (const item of unmatched) {
      console.error(`  - ${item.id}  (title: ${JSON.stringify(item.title)})`);
    }
  }

  if (tickets.length > 0) {
    console.error(`\nTICKETS present (${tickets.length}) — not auto-applied, review manually:`);
    for (const ticket of tickets) {
      console.error(`  - ${JSON.stringify(ticket)}`);
    }
  }

  if (canonRows.length > 0) {
    console.log(`\nProposed CANON.md rows (place manually in the judgment-call table):`);
    for (const row of canonRows) {
      console.log(`  ${row}`);
    }
  }

  if (dryRun) {
    console.log(anyChange ? '\n--dry-run: would write the following changes to REVIEW-CHECKLIST.md--' : '\n--dry-run: no changes needed--');
    if (anyChange) {
      for (const m of matched) {
        if (!m.changed) continue;
        console.log(`\n[${m.exportItem.id}]`);
        console.log(`- ${result.originalText.split('\n')[m.checklistItem.lineIndex]}`);
        console.log(`+ ${result.newText.split('\n')[m.checklistItem.lineIndex]}`);
      }
    }
  } else if (anyChange) {
    console.log('\nWrote changes to REVIEW-CHECKLIST.md.');
  } else {
    console.log('\nNo changes needed (already up to date).');
  }

  return unmatched.length > 0 ? 1 : 0;
}

async function main() {
  const args = process.argv.slice(2);
  let exportPath = null;
  let checklistPath = DEFAULT_CHECKLIST;
  let dryRun = false;

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--dry-run') dryRun = true;
    else if (arg === '--checklist') {
      i += 1;
      checklistPath = resolve(args[i]);
    } else if (!exportPath) {
      exportPath = resolve(arg);
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
  }

  if (!exportPath) {
    console.error('Usage: node scripts/ingest-review-export.mjs <review-export.json> [--dry-run] [--checklist <path>]');
    process.exitCode = 1;
    return;
  }

  const result = await ingest({ exportPath, checklistPath, dryRun });
  const exitCode = printReport(result, { checklistPath, dryRun });

  if (!dryRun && result.anyChange) {
    writeFileSync(checklistPath, result.newText, 'utf8');
  }

  process.exitCode = exitCode;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}

export { ingest, loadChecklistItems, applyItemToLine, loadExport, itemHash, shortDate, cleanTitle };
