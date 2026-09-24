// Shared held-corpus guard (docs/todo/plato-mount.md, GPT-6 Sol code review
// item 1 -- BLOCKER). mount-corpus.mjs's own hold switch
// (shouldSkipForHold, mount-corpus.mjs) only stops the MOUNT step from
// copying a held corpus's files into build/dist -- nothing downstream
// re-checked it. A release built locally with READER_INCLUDE_HELD=1 (to
// smoke-test a held corpus, e.g. Plato) left build/dist holding the
// corpus's work directories, and both publish-release.mjs (uploads
// build/dist to R2) and build-public.mjs --from-dist (rebuilds the site
// from a prior build/dist) carried it straight through with no gate at all.
//
// findHeldWorksInDist(distDir, { root }) is the one place that answers "is a
// held corpus's data actually present in this dist directory" -- both call
// sites report through it rather than re-deriving the hold list or the
// work-id -> dist-dir-name mapping themselves.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { loadYaml, REPO_ROOT } from './load-yaml.mjs';

/**
 * Every corpus (by its corpora/<name>/ directory name) whose mount.yaml
 * declares `hold: true`, with the work ids its own registry.yaml declares.
 * These work ids are exactly the directory names mount-corpus.mjs copies
 * each work under in build/dist (see mount-corpus.mjs's per-work loop:
 * `join(sourceDir, id)` -> `join(distDir, id)`, `id` being a registry.yaml
 * key), so no separate id-mapping step is needed here.
 * @param {string} [root] repo root (default: this file's own repo)
 * @returns {Promise<{ corpus: string, workIds: string[] }[]>}
 */
export async function listHeldCorpora(root = REPO_ROOT) {
  const corporaDir = join(root, 'corpora');
  if (!existsSync(corporaDir)) return [];
  const yaml = await loadYaml();
  const held = [];
  for (const name of readdirSync(corporaDir).sort()) {
    const mountPath = join(corporaDir, name, 'mount.yaml');
    if (!existsSync(mountPath)) continue;
    const mountConfig = yaml.load(readFileSync(mountPath, 'utf8'));
    if (!mountConfig?.hold) continue;
    const registryPath = join(corporaDir, name, 'registry.yaml');
    if (!existsSync(registryPath)) continue;
    const registryYaml = yaml.load(readFileSync(registryPath, 'utf8'));
    const workIds = Object.keys(registryYaml?.registry ?? {});
    held.push({ corpus: mountConfig.corpus ?? name, workIds });
  }
  return held;
}

/**
 * Which held works are actually present in `distDir`, as
 * [{ corpus, workId, evidence: string[] }, ...] (empty when nothing held is
 * there). A work counts as present if ANY of: its own work directory exists
 * under distDir (the mount-time copy target), manifests/index.json lists a
 * manifest path under it (emit-lyceum-manifest.mjs's derived index), or
 * RELEASE.json's file list names a path under it (release-index.mjs's own
 * inventory) -- any one is enough to prove the corpus's data shipped, and a
 * dist at different pipeline stages may not have all three yet.
 * @param {string} distDir
 * @param {{ root?: string }} [opts]
 * @returns {Promise<{ corpus: string, workId: string, evidence: string[] }[]>}
 */
export async function findHeldWorksInDist(distDir, { root = REPO_ROOT } = {}) {
  const heldCorpora = await listHeldCorpora(root);
  if (heldCorpora.length === 0) return [];

  let manifestPaths = [];
  const indexPath = join(distDir, 'manifests', 'index.json');
  if (existsSync(indexPath)) {
    try {
      const index = JSON.parse(readFileSync(indexPath, 'utf8'));
      manifestPaths = Array.isArray(index?.manifests)
        ? index.manifests.map((m) => m.path).filter((p) => typeof p === 'string')
        : [];
    } catch {
      manifestPaths = [];
    }
  }

  let releaseFilePaths = [];
  const releasePath = join(distDir, 'RELEASE.json');
  if (existsSync(releasePath)) {
    try {
      const release = JSON.parse(readFileSync(releasePath, 'utf8'));
      releaseFilePaths = Array.isArray(release?.files)
        ? release.files.map((f) => f.path).filter((p) => typeof p === 'string')
        : [];
    } catch {
      releaseFilePaths = [];
    }
  }

  const findings = [];
  for (const { corpus, workIds } of heldCorpora) {
    for (const workId of workIds) {
      const evidence = [];
      if (existsSync(join(distDir, workId))) {
        evidence.push(`work directory ${workId}/`);
      }
      if (manifestPaths.includes(`/${workId}/manifest.lyceum.json`)) {
        evidence.push('manifests/index.json entry');
      }
      if (releaseFilePaths.some((p) => p === workId || p.startsWith(`${workId}/`))) {
        evidence.push('RELEASE.json file list');
      }
      if (evidence.length) findings.push({ corpus, workId, evidence });
    }
  }
  return findings;
}

/** One human-readable line per held corpus, grouping its findings together
 * so the message names the corpus and its hold plainly -- never just a bare
 * list of work ids. */
export function formatHeldWorksFindings(findings) {
  const byCorpus = new Map();
  for (const f of findings) {
    const list = byCorpus.get(f.corpus) ?? [];
    list.push(f);
    byCorpus.set(f.corpus, list);
  }
  const lines = [];
  for (const [corpus, list] of byCorpus) {
    lines.push(
      `  corpus '${corpus}' is held (corpora/${corpus}/mount.yaml hold: true) but ${list.length} of its ` +
        `work(s) are present: ${list.map((f) => f.workId).join(', ')}`,
    );
  }
  return lines.join('\n');
}

/**
 * Whether a caller should refuse given these findings -- true whenever any
 * held work is present, UNLESS the caller opts in with READER_INCLUDE_HELD=1
 * (the same override mount-corpus.mjs's own shouldSkipForHold honors, so a
 * local held-on test build still works end to end). Exported as a pure
 * function so the gate is unit-testable without touching the filesystem;
 * publish-release.mjs does NOT use this -- it refuses on any finding
 * regardless of the override, since publishing a held corpus requires
 * lifting the hold in mount.yaml, not a build-time env var.
 */
export function shouldRefuseForHeld(findings, env) {
  return findings.length > 0 && env.READER_INCLUDE_HELD !== '1';
}
