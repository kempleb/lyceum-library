#!/usr/bin/env node
// Lyceum P2 stage 1 (docs/p2-plan.md §3) -- registry <-> baseline round-trip
// gate. Bundles shared/lib/works.ts/authors.ts AS THEY EXISTED at a pinned
// baseline commit (`git show`, written to temp files -- never a checkout,
// never touches the working tree), runs scripts/build-registry.mjs against
// the CURRENT working tree's YAML data, and asserts
// JSON.stringify(BEFORE.WORKS) === JSON.stringify(AFTER.CORPUS_WORKS) (and
// the AUTHORS equivalent) -- order-sensitive, so it catches value drift,
// undefined-vs-omitted, and any reordering in one string equality, plus an
// explicit codepoint check on typography (’ — …) and polytonic Greek in
// greekTitle/nativeName/blurb.
//
// Pinned to the stage-1 baseline sha during P2; retired from CI in the
// closing commit (plan §3) in favor of the stage-4 golden-hash test.
//
// Usage: node scripts/verify-registry-roundtrip.mjs --baseline <sha>

import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

function parseArgs(argv) {
  const args = { baseline: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--baseline') args.baseline = argv[++i];
    else throw new Error(`Unknown argument: ${a}`);
  }
  if (!args.baseline) throw new Error('Usage: verify-registry-roundtrip.mjs --baseline <sha>');
  return args;
}

function run(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, {
    cwd: options.cwd ?? ROOT,
    env: options.env ?? process.env,
    stdio: options.stdio ?? 'inherit',
    encoding: 'utf8',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed with status ${result.status}`);
  }
  return result;
}

// Raw stdout, byte-for-byte -- used for `git show`'ing file contents, where
// trimming would corrupt a source file that legitimately ends without (or
// with extra) trailing whitespace.
function captureRaw(cmd, args, options = {}) {
  const result = spawnSync(cmd, args, {
    cwd: options.cwd ?? ROOT,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} failed with status ${result.status}: ${result.stderr}`);
  }
  return result.stdout;
}

function captureTrimmed(cmd, args, options = {}) {
  return captureRaw(cmd, args, options).trim();
}

async function bundleFile(entryPath, define) {
  const esbuildPath = join(ROOT, 'app', 'node_modules', 'esbuild', 'lib', 'main.js');
  const { default: esbuild } = await import(pathToFileURL(esbuildPath).href);
  const result = await esbuild.build({
    entryPoints: [entryPath],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
    define,
  });
  const dir = mkdtempSync(join(tmpdir(), 'verify-registry-roundtrip-out-'));
  const outPath = join(dir, 'mod.mjs');
  writeFileSync(outPath, result.outputFiles[0].text);
  return import(pathToFileURL(outPath).href);
}

// Baseline WORKS/AUTHORS with fixtures OFF -- matches the real corpus
// (CORPUS_WORKS/CORPUS_AUTHORS never carry the sample-work/sample-author
// fixture; that's a separate FIXTURE_* pair, checked in build-registry.mjs's
// own loadFixtureSource, not here).
async function loadBaseline(sha) {
  const dir = mkdtempSync(join(tmpdir(), 'verify-registry-roundtrip-baseline-'));
  writeFileSync(join(dir, 'works.ts'), captureRaw('git', ['show', `${sha}:shared/lib/works.ts`]));
  writeFileSync(join(dir, 'authors.ts'), captureRaw('git', ['show', `${sha}:shared/lib/authors.ts`]));

  const define = {
    'import.meta.env.PUBLIC_SHOW_PRIVATE': 'undefined',
    'import.meta.env.PUBLIC_READER_FIXTURES': 'undefined',
  };
  const worksMod = await bundleFile(join(dir, 'works.ts'), define);
  const authorsMod = await bundleFile(join(dir, 'authors.ts'), define);
  return { WORKS: worksMod.WORKS, AUTHORS: authorsMod.AUTHORS };
}

async function loadGenerated() {
  run('node', ['scripts/build-registry.mjs'], { cwd: ROOT });
  const genPath = join(ROOT, 'shared', 'lib', 'registry.generated.ts');
  const mod = await bundleFile(genPath, {});
  return { CORPUS_WORKS: mod.CORPUS_WORKS, CORPUS_AUTHORS: mod.CORPUS_AUTHORS };
}

function charDiff(a, b) {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i++) {
    if (a[i] !== b[i]) {
      const start = Math.max(0, i - 60);
      return (
        `first differing character at offset ${i}:\n` +
        `  before: ...${JSON.stringify(a.slice(start, i + 60))}\n` +
        `  after:  ...${JSON.stringify(b.slice(start, i + 60))}`
      );
    }
  }
  return '(strings differ only in trailing length)';
}

function firstDifferingIndex(before, after) {
  const len = Math.max(before.length, after.length);
  for (let i = 0; i < len; i++) {
    if (JSON.stringify(before[i]) !== JSON.stringify(after[i])) return i;
  }
  return -1;
}

function compareArrays(label, before, after, idKey) {
  const beforeJson = JSON.stringify(before);
  const afterJson = JSON.stringify(after);
  if (beforeJson === afterJson) {
    return { ok: true, beforeCount: before.length, afterCount: after.length };
  }
  const idx = firstDifferingIndex(before, after);
  const beforeItem = before[idx];
  const afterItem = after[idx];
  const id = beforeItem?.[idKey] ?? afterItem?.[idKey] ?? `(index ${idx})`;
  console.error(`\n[verify-registry-roundtrip] ${label} MISMATCH -- first differing ${idKey}: '${id}' (index ${idx})`);
  console.error(charDiff(JSON.stringify(beforeItem ?? null, null, 2), JSON.stringify(afterItem ?? null, null, 2)));
  return { ok: false, beforeCount: before.length, afterCount: after.length };
}

// Explicit codepoint-level check on typography (’ — …) and polytonic Greek
// fields, on top of (redundant with, but independently asserted per plan §3)
// the full JSON.stringify equality above.
function assertCodepoints(before, after, idKey, field, label) {
  const afterById = new Map(after.map((x) => [x[idKey], x]));
  let checked = 0;
  for (const b of before) {
    const value = b[field];
    if (value === undefined) continue;
    const a = afterById.get(b[idKey]);
    const avalue = a?.[field];
    const bcp = Array.from(value).map((c) => c.codePointAt(0));
    const acp = Array.from(avalue ?? '').map((c) => c.codePointAt(0));
    if (bcp.length !== acp.length || bcp.some((cp, i) => cp !== acp[i])) {
      throw new Error(
        `verify-registry-roundtrip: codepoint mismatch in ${label} '${b[idKey]}'.${field}\n` +
          `  before codepoints: ${JSON.stringify(bcp)}\n  after codepoints:  ${JSON.stringify(acp)}`,
      );
    }
    checked++;
  }
  return checked;
}

async function main() {
  const { baseline } = parseArgs(process.argv.slice(2));
  const sha = captureTrimmed('git', ['rev-parse', baseline]);
  console.log(`[verify-registry-roundtrip] baseline ${baseline} -> ${sha}`);

  const before = await loadBaseline(sha);
  const after = await loadGenerated();

  const worksResult = compareArrays('WORKS vs CORPUS_WORKS', before.WORKS, after.CORPUS_WORKS, 'id');
  const authorsResult = compareArrays('AUTHORS vs CORPUS_AUTHORS', before.AUTHORS, after.CORPUS_AUTHORS, 'id');

  if (!worksResult.ok || !authorsResult.ok) {
    process.exitCode = 1;
    return;
  }

  const greekChecked = assertCodepoints(before.WORKS, after.CORPUS_WORKS, 'id', 'greekTitle', 'work');
  const blurbChecked = assertCodepoints(before.WORKS, after.CORPUS_WORKS, 'id', 'blurb', 'work');
  const nameChecked = assertCodepoints(before.AUTHORS, after.CORPUS_AUTHORS, 'id', 'nativeName', 'author');
  console.log(
    `[verify-registry-roundtrip] codepoint checks: ${greekChecked} greekTitle, ${blurbChecked} blurb, ` +
      `${nameChecked} nativeName fields -- all codepoint-identical.`,
  );

  console.log(
    `${worksResult.beforeCount}/${worksResult.afterCount} works, ` +
      `${authorsResult.beforeCount}/${authorsResult.afterCount} authors JSON-identical including key order`,
  );
}

await main();
