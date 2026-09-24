import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { ingest, loadExport, shortDate } from '../ingest-review-export.mjs';

const SCRIPT = fileURLToPath(new URL('../ingest-review-export.mjs', import.meta.url));
const REAL_EXPORT = '/Users/johnboyer/.claude/uploads/e75f1215-a942-4d5a-9b15-2f34a4b4ca46/b79807aa-reviewexport2.json';

async function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'ingest-review-export-test-'));
  try {
    return await fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function writeChecklist(dir, content) {
  const path = join(dir, 'REVIEW-CHECKLIST.md');
  writeFileSync(path, content, 'utf8');
  return path;
}

function writeExport(dir, data) {
  const path = join(dir, 'review-export.json');
  writeFileSync(path, JSON.stringify(data), 'utf8');
  return path;
}

const BASE_CHECKLIST = [
  '# checklist fixture',
  '',
  '1. [ ] **Some spot-check item** — looks fine? <!--id:spot-check-one-->',
  '2. [ ] **A decision item** — pick an option. <!--id:decision-one-->',
  '3. [ ] **Another decision, no ruling yet** — pick an option. <!--id:decision-two-->',
  '',
].join('\n');

test('ok on a non-decision item ticks the checkbox', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T00:00:00.000Z',
      items: [{ id: 'spot-check-one', title: 'Some spot-check item', section: 'x', kind: 'spot-check', cat: 'x', state: 'ok', note: '' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.unmatched.length, 0);
    assert.equal(result.matched.length, 1);
    assert.match(result.newText, /1\. \[x\] \*\*Some spot-check item\*\*/);
    assert.equal(result.canonRows.length, 0);
  });
});

test('issue on a non-decision item leaves it unticked and attaches a flag matching the JOHN convention', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      // 18:00Z is 13:00 in America/Chicago (CDT, UTC-5) — safely the same
      // calendar day there too, so this test isn't about the tz conversion.
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'spot-check-one', title: 'Some spot-check item', section: 'x', kind: 'spot-check', cat: 'x', state: 'issue', note: 'This is wrong, fix it.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.match(result.newText, /1\. \[ \] /);
    assert.match(result.newText, /\*\*⚑ JOHN 2026-07-28 \(dashboard\): "This is wrong, fix it\."\*\*/);
  });
});

test('a decision with a note is RULED, ticked when ok, and produces a proposed CANON row', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'decision-one', title: 'A decision item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Go with option B.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.match(result.newText, /2\. \[x\] \*\*✅ RULED 2026-07-28 — A decision item\*\* \(John: "Go with option B\."\)\. Original item: \*\*A decision item\*\*/);
    assert.equal(result.canonRows.length, 1);
    assert.match(result.canonRows[0], /\| A decision item \| Go with option B\. \| decided by John 2026-07-28 \|/);
  });
});

test('a decision left unruled (state null, no note) is left alone', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T00:00:00.000Z',
      items: [{ id: 'decision-two', title: 'Another decision, no ruling yet', section: 'x', kind: 'decision', cat: 'x', state: null, note: '' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.matched[0].changed, false);
    assert.equal(result.newText, BASE_CHECKLIST);
  });
});

test('an id with no matching checklist item is reported loudly, not dropped', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T00:00:00.000Z',
      items: [{ id: 'no-such-item', title: 'Ghost item', section: 'x', kind: 'spot-check', cat: 'x', state: 'ok', note: '' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.unmatched.length, 1);
    assert.equal(result.unmatched[0].id, 'no-such-item');
    assert.equal(result.matched.length, 0);
    // Nothing in the checklist changes for an unmatched id.
    assert.equal(result.newText, BASE_CHECKLIST);
  });
});

test('running the same export twice is a no-op the second time (idempotent)', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T00:00:00.000Z',
      items: [
        { id: 'decision-one', title: 'A decision item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Go with option B.' },
        { id: 'spot-check-one', title: 'Some spot-check item', section: 'x', kind: 'spot-check', cat: 'x', state: 'issue', note: 'Fix this.' },
      ],
      tickets: [],
    });
    const first = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(first.anyChange, true);
    writeFileSync(checklistPath, first.newText, 'utf8');

    const second = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(second.anyChange, false);
    assert.equal(second.newText, first.newText);
    for (const m of second.matched) assert.equal(m.changed, false);
  });
});

test('--dry-run prints without writing the file', async () => {
  await withTmpDir((dir) => {
    const checklistPath = writeChecklist(dir, BASE_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T00:00:00.000Z',
      items: [{ id: 'decision-one', title: 'A decision item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Go with option B.' }],
      tickets: [],
    });
    const before = readFileSync(checklistPath, 'utf8');
    const run = spawnSync(process.execPath, [SCRIPT, exportPath, '--dry-run', '--checklist', checklistPath], { encoding: 'utf8' });
    assert.equal(run.status, 0, run.stderr);
    assert.match(run.stdout, /would write the following changes/);
    const after = readFileSync(checklistPath, 'utf8');
    assert.equal(after, before);
  });
});

// REAL_EXPORT is a session upload outside the repo; it is gone once that
// session's uploads are cleaned up, so these two run only while it exists.
const NO_REAL_EXPORT = existsSync(REAL_EXPORT) ? false : `real export not on this machine: ${REAL_EXPORT}`;

test('the real export file loads and matches the contract (exported, items[], tickets[])', { skip: NO_REAL_EXPORT }, () => {
  const data = loadExport(REAL_EXPORT);
  assert.equal(typeof data.exported, 'string');
  assert.ok(Array.isArray(data.items) && data.items.length > 0);
  assert.deepEqual(data.tickets, []);
  for (const item of data.items) {
    assert.equal(typeof item.id, 'string');
    assert.equal(typeof item.title, 'string');
    assert.ok(item.state === 'ok' || item.state === 'issue' || item.state === null);
  }
});

test('the real export ingests end-to-end against a fixture checklist built from its ids', { skip: NO_REAL_EXPORT }, async () => {
  await withTmpDir(async (dir) => {
    const data = loadExport(REAL_EXPORT);
    const lines = ['# checklist fixture (real export ids)', ''];
    data.items.forEach((item, i) => {
      lines.push(`${i + 1}. [ ] **${item.title.replace(/\*\*/g, '')}** — original text goes here. <!--id:${item.id}-->`);
    });
    const checklistPath = writeChecklist(dir, lines.join('\n'));
    const exportPath = REAL_EXPORT;

    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.unmatched.length, 0, JSON.stringify(result.unmatched));
    assert.equal(result.matched.length, data.items.length);
    // Every item in the real export is kind:decision with a note (verified
    // against the file), so every match should produce a RULED annotation
    // and a proposed CANON row.
    for (const item of data.items) {
      assert.equal(item.kind, 'decision');
      assert.ok(item.note && item.note.trim().length > 0);
    }
    assert.equal(result.canonRows.length, data.items.length);
    // The export's exported timestamp (2026-07-28T03:19:38.746Z) is still
    // the evening of the 27th in John's timezone (America/Chicago).
    assert.match(result.newText, /RULED 2026-07-27/);

    // Re-running is a no-op.
    writeFileSync(checklistPath, result.newText, 'utf8');
    const second = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(second.anyChange, false);
  });
});

// ---------------------------------------------------------------------------
// Regression: the pinned id marker must stay immediately after the
// checkbox on rewrite, not drift into the body (DEFECT 1).
// ---------------------------------------------------------------------------

const CANONICAL_ID_CHECKLIST = [
  '# checklist fixture (canonical id-after-checkbox position)',
  '',
  '1. [ ] <!--id:tick-me--> **A spot-check item** — some body text.',
  '2. [ ] <!--id:flag-me--> **Another spot-check item** — some body text.',
  '3. [ ] <!--id:rule-me--> **A decision item** — some body text.',
  '',
].join('\n');

function idPositionOf(line) {
  // Everything between the checkbox "]" and the id marker must be only
  // whitespace for the marker to be "immediately after the checkbox".
  const m = line.match(/\]\s*(<!--\s*id\s*:[\w-]+\s*-->)/);
  return m ? m[1] : null;
}

test('a tick-only rewrite keeps the id marker immediately after the checkbox', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, CANONICAL_ID_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'tick-me', title: 'A spot-check item', section: 'x', kind: 'spot-check', cat: 'x', state: 'ok', note: '' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    const newLine = result.newText.split('\n').find((l) => l.includes('tick-me'));
    assert.ok(idPositionOf(newLine), `id marker drifted out of canonical position: ${newLine}`);
  });
});

test('a flag rewrite keeps the id marker immediately after the checkbox', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, CANONICAL_ID_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'flag-me', title: 'Another spot-check item', section: 'x', kind: 'spot-check', cat: 'x', state: 'issue', note: 'Fix this.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    const newLine = result.newText.split('\n').find((l) => l.includes('flag-me'));
    assert.ok(idPositionOf(newLine), `id marker drifted out of canonical position: ${newLine}`);
  });
});

test('a RULED-decision rewrite keeps the id marker immediately after the checkbox (not buried in "Original item:")', async () => {
  await withTmpDir(async (dir) => {
    const checklistPath = writeChecklist(dir, CANONICAL_ID_CHECKLIST);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'rule-me', title: 'A decision item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Go with option B.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    const newLine = result.newText.split('\n').find((l) => l.includes('rule-me'));
    assert.ok(idPositionOf(newLine), `id marker drifted out of canonical position: ${newLine}`);
    // And it must not appear a second time buried in the "Original item:" tail.
    assert.equal((newLine.match(/<!--\s*id\s*:rule-me\s*-->/g) ?? []).length, 1);
  });
});

// ---------------------------------------------------------------------------
// Regression: an already hand-recorded ruling must not be double-annotated
// (DEFECT 2), detected by John's verbatim note already being present in the
// body — independent of RULED wording, quoting style, or date.
// ---------------------------------------------------------------------------

test('a decision whose verbatim note is already recorded by hand is left un-re-annotated', async () => {
  await withTmpDir(async (dir) => {
    const checklist = [
      '# checklist fixture',
      '',
      '1. [x] <!--id:already-ruled--> **✅ RULED 2026-07-27 — kept as-is** (John: "Keep it as is."). Original item: some body text.',
      '',
    ].join('\n');
    const checklistPath = writeChecklist(dir, checklist);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'already-ruled', title: 'Some item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Keep it as is.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.matched[0].alreadyRecorded, true);
    // No second RULED stamp, no nested "Original item:" chain, no CANON row.
    assert.equal((result.newText.match(/RULED/g) ?? []).length, 1);
    assert.equal((result.newText.match(/Original item:/g) ?? []).length, 1);
    assert.equal(result.canonRows.length, 0);
  });
});

test('an already-recorded ruling still picks up a genuine tick correction', async () => {
  await withTmpDir(async (dir) => {
    const checklist = [
      '# checklist fixture',
      '',
      '1. [ ] <!--id:already-ruled--> **✅ RULED 2026-07-27 — kept as-is** (John: "Keep it as is."). Original item: some body text.',
      '',
    ].join('\n');
    const checklistPath = writeChecklist(dir, checklist);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'already-ruled', title: 'Some item', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'Keep it as is.' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.matched[0].alreadyRecorded, true);
    assert.equal(result.matched[0].changed, true);
    assert.match(result.newText, /1\. \[x\] <!--id:already-ruled-->/);
    assert.equal((result.newText.match(/RULED/g) ?? []).length, 1);
  });
});

test('a hand-recorded ruling using different quote glyphs around the same words is still recognized as already recorded', async () => {
  await withTmpDir(async (dir) => {
    // Hand-typed annotation uses single quotes around "Sophists"; the export
    // note uses double quotes — same words, different glyph, must still match.
    const checklist = [
      '# checklist fixture',
      '',
      "1. [ ] <!--id:sophists--> **⚑ RULED 2026-07-27 — the sophists get their own shelf** (John: \"How about a separate 'Sophists' shelf?\"). Original item: some body text.",
      '',
    ].join('\n');
    const checklistPath = writeChecklist(dir, checklist);
    const exportPath = writeExport(dir, {
      exported: '2026-07-28T18:00:00.000Z',
      items: [{ id: 'sophists', title: 'Sophists shelf', section: 'x', kind: 'decision', cat: 'x', state: 'ok', note: 'How about a separate "Sophists" shelf?' }],
      tickets: [],
    });
    const result = await ingest({ exportPath, checklistPath, dryRun: false });
    assert.equal(result.matched[0].alreadyRecorded, true);
    assert.equal((result.newText.match(/RULED/g) ?? []).length, 1);
  });
});

// ---------------------------------------------------------------------------
// Regression: ruling dates come from the export's `exported` timestamp
// converted to John's timezone (America/Chicago), not the UTC calendar day
// and not today's clock (DEFECT 3).
// ---------------------------------------------------------------------------

test('shortDate converts the export timestamp to America/Chicago, not UTC', () => {
  // 03:19 UTC is still 22:19 the previous day in America/Chicago (CDT, UTC-5).
  assert.equal(shortDate('2026-07-28T03:19:38.746Z'), '2026-07-27');
  // Comfortably inside the Chicago daytime: no shift.
  assert.equal(shortDate('2026-07-28T18:00:00.000Z'), '2026-07-28');
});
