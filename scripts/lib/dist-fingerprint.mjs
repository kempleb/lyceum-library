// Content fingerprint for a build output directory (e.g. app/dist,
// build/dist). Used by scripts/verify-byte-stability.mjs both as a
// byte-diff harness precondition (proving the shared corpus-input
// directory, build/dist, didn't change between the two builds under test)
// and as the basis for the path-set + per-file sha256 comparison of the
// two build outputs themselves.
//
// Per file: sha256(relativePath + '\0' + contents) -- the null byte keeps
// a path/content boundary unambiguous. Those per-file hashes are then
// folded, in sorted relative-path order, into one sha256 digest for the
// whole tree: a single accumulator hash is updated with each per-file
// hash in turn. Sorting first makes the digest independent of directory
// read order (readdir order is not guaranteed stable across platforms or
// filesystems).
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

function collectFiles(dir, out) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    // Follow symlinks (both files and directories) rather than skip them --
    // app/public/data itself is a symlink into build/dist, and a naive
    // lstat-based walk would silently fingerprint zero files there.
    const isSymlink = entry.isSymbolicLink();
    const stat = isSymlink ? statSync(full) : entry;
    if (stat.isDirectory()) {
      collectFiles(full, out);
    } else if (stat.isFile()) {
      out.push(full);
    }
    // Anything else (broken symlink, socket, etc.) is ignored.
  }
}

/**
 * Fingerprint every regular file under `dir`.
 *
 * @param {string} dir - absolute path to the directory tree to hash.
 * @param {{ includeFiles?: boolean }} [options] - pass includeFiles: true to
 *   also return a relativePath -> perFileHash map for diagnostics (e.g.
 *   reporting exactly which paths differ between two trees).
 * @returns {{ digest: string, fileCount: number, files?: Record<string, string> }}
 */
export function fingerprintDir(dir, options = {}) {
  const { includeFiles = false } = options;
  const absoluteFiles = [];
  collectFiles(dir, absoluteFiles);

  const relPaths = absoluteFiles
    .map((f) => relative(dir, f).split(sep).join('/'))
    .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

  const folded = createHash('sha256');
  const files = includeFiles ? {} : undefined;

  for (const relPath of relPaths) {
    const contents = readFileSync(join(dir, relPath));
    const perFileHash = createHash('sha256')
      .update(relPath, 'utf8')
      .update('\0')
      .update(contents)
      .digest('hex');
    folded.update(perFileHash);
    if (files) files[relPath] = perFileHash;
  }

  const result = { digest: folded.digest('hex'), fileCount: relPaths.length };
  if (files) result.files = files;
  return result;
}
