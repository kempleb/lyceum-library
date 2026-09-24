// Pure description of scripts/build-public.mjs's stage list and its
// `--from-dist <dir>` argument resolution, split out so both can be unit-
// tested without running the real (multi-minute, corpus-dependent) build.
// build-public.mjs imports planStages() and gates its own execution on the
// `enabled`/`mode` fields returned here -- this is the single source of
// truth for "what --from-dist skips or changes," not a parallel description
// that could drift from the real script.
//
// See docs/release-from-dist.md for what a "release" is and how --from-dist
// uses one; docs/lyceum-shared-repo-plan.md §4/§6 for why this exists
// (Brian's brief requires a fresh checkout + one dated release to build the
// site with no TLG/PHI, no pipeline run, and no sibling repo).
import { isAbsolute, relative } from 'node:path';

/**
 * @param {{ fromDist: boolean }} opts
 * @returns {{ name: string, enabled: boolean, mode?: string, note?: string }[]}
 */
function planStages({ fromDist }) {
  const full = !fromDist;
  return [
    { name: 'npm-ci', enabled: true, note: 'installs app/ deps if missing' },
    { name: 'registry-agreement', enabled: true },
    { name: 'inventory-hashes', enabled: true },
    { name: 'copy-release', enabled: !full, note: 'cp <release dir> to build/dist' },
    { name: 'verify-release-copy', enabled: !full, note: 'RELEASE.json files/size/sha256, no extras' },
    { name: 'clean-dist', enabled: full, note: 'rm build/dist (from-dist replaces it via the copy instead)' },
    { name: 'clean-app-dist', enabled: true, note: 'rm app/dist' },
    { name: 'pipeline-per-work', enabled: full, note: 'runs reader_pipeline; needs TLG/PHI' },
    { name: 'turn-align', enabled: full, note: 'runs reader_pipeline.align_turns' },
    { name: 'mount-corpora', enabled: full, note: 'mount-corpus.mjs; needs the sibling repo' },
    { name: 'citation-index', enabled: true },
    { name: 'registries', enabled: true },
    { name: 'preflight', enabled: true },
    { name: 'validate-contracts', enabled: true },
    { name: 'emit-lyceum-manifest', enabled: true },
    { name: 'lsj-topup', enabled: true, mode: full ? 'full' : 'check-only' },
    { name: 'verify-shared-lsj', enabled: true },
    { name: 'release-index', enabled: full, note: 'writes build/dist/RELEASE.json' },
    { name: 'astro-build', enabled: true },
    { name: 'verify-release-final', enabled: true, note: 'checks release after Astro build' },
    { name: 'check-links', enabled: true },
    { name: 'prune-and-verify-artifact', enabled: true, note: 'still gated on PUBLIC_DATA_ROOT at runtime' },
  ];
}

/**
 * Resolves the --from-dist target: an explicit `--from-dist <dir>` /
 * `--from-dist=<dir>` argument wins over the READER_RELEASE_DIR env var;
 * neither given returns null (ordinary full-build mode). An empty
 * READER_RELEASE_DIR is treated as unset.
 *
 * @param {string[]} argv - e.g. process.argv.slice(2)
 * @param {Record<string, string | undefined>} env - e.g. process.env
 * @returns {string | null}
 */
function parseFromDistArg(argv, env = {}) {
  let fromDist = env.READER_RELEASE_DIR || null;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--from-dist') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        throw new Error('--from-dist requires a directory argument');
      }
      i += 1;
      fromDist = value;
    } else if (arg.startsWith('--from-dist=')) {
      fromDist = arg.slice('--from-dist='.length);
      if (!fromDist) throw new Error('--from-dist requires a directory argument');
    }
  }
  return fromDist;
}

function planReleaseCopy(fromDistAbs, distDirAbs) {
  if (fromDistAbs === distDirAbs) return 'noop';
  const fromInsideDist = relative(distDirAbs, fromDistAbs);
  const distInsideFrom = relative(fromDistAbs, distDirAbs);
  const isInside = (path) => path === '' || (!path.startsWith('..') && !isAbsolute(path));
  if (isInside(fromInsideDist) || isInside(distInsideFrom)) {
    throw new Error(
      `--from-dist paths overlap (${fromDistAbs}, ${distDirAbs}); point --from-dist at a directory outside build/dist`,
    );
  }
  return 'copy';
}

export { planStages, parseFromDistArg, planReleaseCopy };
