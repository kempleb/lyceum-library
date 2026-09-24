#!/usr/bin/env node
// Standalone / library counterpart to release-index.mjs: verifies that a
// directory (typically a copied-down or downloaded release) matches its own
// RELEASE.json byte-for-byte -- every listed file present with the recorded
// size and sha256, and no extra non-derived files. Used by
// `build-public.mjs --from-dist` before it
// trusts a copied release, and by `fetch-release.mjs` after a download; also
// callable by hand. See docs/release-from-dist.md.
//
// Run: node scripts/verify-release.mjs <dir>
import { existsSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDerivedPath, listReleaseFiles, sha256File } from './release-index.mjs';

function verifyRelease(distDir) {
  if (!existsSync(distDir) || !statSync(distDir).isDirectory()) {
    return { ok: false, problems: [`release directory does not exist: ${distDir}`] };
  }

  const releasePath = join(distDir, 'RELEASE.json');
  if (!existsSync(releasePath)) {
    return { ok: false, problems: [`RELEASE.json not found in ${distDir}`] };
  }

  let index;
  try {
    index = JSON.parse(readFileSync(releasePath, 'utf8'));
  } catch (err) {
    return { ok: false, problems: [`RELEASE.json is not valid JSON: ${err.message}`] };
  }

  const problems = [];
  const listed = new Set();
  for (const entry of index.files ?? []) {
    listed.add(entry.path);
    if (isDerivedPath(entry.path)) {
      problems.push(`indexed a derived file: ${entry.path}`);
      continue;
    }
    const abs = join(distDir, entry.path);
    if (!existsSync(abs)) {
      problems.push(`missing file listed in RELEASE.json: ${entry.path}`);
      continue;
    }
    const stat = statSync(abs);
    if (stat.size !== entry.size) {
      problems.push(`size mismatch for ${entry.path}: expected ${entry.size}, got ${stat.size}`);
      continue;
    }
    const actualSha = sha256File(abs);
    if (actualSha !== entry.sha256) {
      problems.push(`sha256 mismatch for ${entry.path}: expected ${entry.sha256}, got ${actualSha}`);
    }
  }

  let actualFiles;
  try {
    actualFiles = listReleaseFiles(distDir);
  } catch (err) {
    return { ok: false, problems: [...problems, err.message] };
  }
  for (const rel of actualFiles) {
    if (!listed.has(rel)) {
      problems.push(`extra file not in RELEASE.json: ${rel}`);
    }
  }

  return { ok: problems.length === 0, problems };
}

function usage(message) {
  if (message) console.error(message);
  console.error('Usage: node scripts/verify-release.mjs <dir>');
  process.exit(2);
}

async function main() {
  const dir = process.argv[2];
  if (!dir) usage('Missing <dir>.');
  const distDir = resolve(dir);
  const { ok, problems } = verifyRelease(distDir);
  console.log(`verify-release: ${distDir}`);
  if (ok) {
    console.log('  OK -- matches RELEASE.json (files, sizes, sha256), no extra non-derived files');
  } else {
    for (const p of problems.slice(0, 20)) console.error(`  FAIL: ${p}`);
    if (problems.length > 20) console.error(`  ... and ${problems.length - 20} more`);
  }
  process.exitCode = ok ? 0 : 1;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  main().catch((err) => {
    console.error(err.stack ?? String(err));
    process.exitCode = 1;
  });
}

export { verifyRelease };
