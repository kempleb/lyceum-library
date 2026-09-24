import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

import { buildItemsData, renderDashboard } from '../build-review-dashboard.mjs';
import { parseChecklist } from '../lib/review-checklist.mjs';
import { loadExport } from '../ingest-review-export.mjs';

const SHELL_PATH = fileURLToPath(new URL('../review-dashboard-shell.html', import.meta.url));
const SHELL_HTML = readFileSync(SHELL_PATH, 'utf8');

const FIXTURE = [
  '## Active review queue (1-2)',
  '',
  '1. [ ] <!--id:fixture-one--> **⚖ First item** — needs a ruling.',
  '',
  '2. [x] <!--id:fixture-two--> **Second item** — already checked.',
  '',
  '## Completed',
  '',
  '- [x] <!--id:fixture-three--> **Third item** — done.',
  '',
  '## Retired — superseded and cut from the queue',
  '',
  '- <!--id:fixture-four--> **Fourth item** — retired.',
  '',
].join('\n');

const FIXTURE_MISSING_ID = [
  '## Active review queue (1-1)',
  '',
  '1. [ ] **Unpinned item** — no id comment here.',
  '',
  '## Completed',
  '',
  '## Retired',
  '',
].join('\n');

function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'build-review-dashboard-test-'));
  try {
    return fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('renderer output contains every item id', () => {
  const html = renderDashboard(FIXTURE, SHELL_HTML);
  for (const id of ['fixture-one', 'fixture-two', 'fixture-three', 'fixture-four']) {
    assert.ok(html.includes(id), `expected output to contain id "${id}"`);
  }
});

test('a checklist item without a pinned id fails the build, naming the item', () => {
  assert.throws(
    () => buildItemsData(parseChecklist(FIXTURE_MISSING_ID)),
    (err) => {
      assert.match(err.message, /#1/);
      assert.match(err.message, /Unpinned item/);
      return true;
    },
  );
});

test('idempotent output for unchanged input', () => {
  const first = renderDashboard(FIXTURE, SHELL_HTML);
  const second = renderDashboard(FIXTURE, SHELL_HTML);
  assert.equal(first, second);
});

test('kind is "decision" when the item text carries a ⚖ mark, "spot-check" otherwise', () => {
  const itemsData = buildItemsData(parseChecklist(FIXTURE));
  const byId = Object.fromEntries(itemsData.map((item) => [item.id, item]));
  assert.equal(byId['fixture-one'].kind, 'decision');
  assert.equal(byId['fixture-two'].kind, 'spot-check');
});

// --- Export-shape test: run the shell's actual inline behavior script
// (extracted verbatim from the built HTML, not a hand copy of its logic) in
// a minimal sandbox, drive it exactly as John's browser would (crafted
// localStorage state, then a synthetic click on "Send to Claude"), and feed
// the JSON it hands to navigator.clipboard.writeText straight through
// ingest-review-export.mjs's own loadExport() -- the real contract, not an
// assertion re-describing it.
//
// The live shell's script is an IIFE exposing nothing globally and reading
// state as { [id]: { s: 'ok'|'issue'|null, note } } (not the old synthetic
// shell's { checked, note }), so the sandbox below mimics the DOM surface it
// actually touches: getElementById for its known ids, querySelectorAll for
// the toolbar (stubbed empty -- this test doesn't exercise tab-switching),
// and document.createElement returning fully-stubbed nodes so render()'s
// card-building can run over the fixture items without throwing.

function makeElementStub(initialText = '') {
  const stub = {
    _innerHTML: '',
    _textContent: initialText,
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = v; },
    get textContent() { return this._textContent; },
    set textContent(v) { this._textContent = v; },
    style: {},
    dataset: {},
    hidden: false,
    value: '',
    addEventListener(type, handler) {
      stub._listeners = stub._listeners || {};
      stub._listeners[type] = handler;
    },
    appendChild() {},
    removeChild() {},
    setAttribute() {},
    getAttribute() { return null; },
    classList: { contains: () => false, add: () => {}, remove: () => {}, toggle: () => {} },
  };
  return stub;
}

function extractBehaviorScript(html) {
  // The shell has two <script> blocks: the itemsData JSON payload (which
  // carries its own type="application/json" attribute) and the bare
  // behavior <script>. Grab the bare one.
  const matches = [...html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)];
  const bare = matches.find((m) => !m[0].startsWith('<script id="itemsData"'));
  assert.ok(bare, 'expected the shell to contain a bare <script> logic block');
  return bare[1];
}

function runShellScript(html, itemsDataJsonText, storageSeed = {}) {
  const storage = { ...storageSeed };
  const knownIds = [
    'itemsData', 'groups', 'stTodo', 'stOk', 'stIssue', 'stDec', 'meterFill',
    'q', 'sendBtn', 'newTicketBtn', 'ticketForm', 'tkTitle', 'tkBody', 'tkCat',
    'tkSave', 'tkCancel', 'toast',
  ];
  const elements = Object.fromEntries(knownIds.map((id) => [id, makeElementStub()]));
  elements.itemsData.textContent = itemsDataJsonText;

  let clipboardText = null;
  const sandbox = {
    document: {
      getElementById: (id) => elements[id],
      createElement: () => makeElementStub(),
      querySelectorAll: () => [],
      body: { appendChild() {}, removeChild() {} },
    },
    localStorage: {
      getItem: (k) => (Object.prototype.hasOwnProperty.call(storage, k) ? storage[k] : null),
      setItem: (k, v) => { storage[k] = v; },
    },
    navigator: {
      clipboard: {
        writeText: (text) => { clipboardText = text; return Promise.resolve(); },
      },
    },
    console,
    setTimeout,
    clearTimeout,
  };
  sandbox.window = { localStorage: sandbox.localStorage };
  vm.createContext(sandbox);
  const script = extractBehaviorScript(html);
  new vm.Script(script, { filename: 'review-dashboard-shell-inline.js' }).runInContext(sandbox);
  return { elements, getClipboardText: () => clipboardText };
}

test('the shell export payload matches the shape ingest-review-export.mjs consumes', async () => {
  const html = renderDashboard(FIXTURE, SHELL_HTML);
  const itemsData = buildItemsData(parseChecklist(FIXTURE));

  // Craft state in the real shell's own schema: item one ticked OK, item two
  // flagged with a note, item three (and the retired fourth) untouched.
  // Seeded into localStorage before the script runs, exactly as a returning
  // browser session would have it.
  const state = {
    'fixture-one': { s: 'ok', note: '' },
    'fixture-two': { s: 'issue', note: 'this looks wrong' },
  };
  const storageSeed = { 'apr-review-v1': JSON.stringify(state) };

  const { elements, getClipboardText } = runShellScript(html, JSON.stringify(itemsData), storageSeed);

  // Trigger "Send to Claude" exactly as a click would.
  elements.sendBtn._listeners.click();
  // Let the clipboard promise's .then() (which fires the toast) settle.
  await Promise.resolve();

  const payload = JSON.parse(getClipboardText());
  assert.equal(payload.items.length, 2);
  const byId = Object.fromEntries(payload.items.map((it) => [it.id, it]));
  assert.equal(byId['fixture-one'].state, 'ok');
  assert.equal(byId['fixture-two'].state, 'issue');
  assert.equal(byId['fixture-two'].note, 'this looks wrong');
  assert.deepEqual(payload.tickets, []);

  withTmpDir((dir) => {
    const exportPath = join(dir, 'review-export.json');
    writeFileSync(exportPath, JSON.stringify(payload), 'utf8');
    // The real contract: loadExport() must accept this without throwing.
    const loaded = loadExport(exportPath);
    assert.equal(loaded.items.length, 2);
    assert.deepEqual(loaded.tickets, []);
  });
});
