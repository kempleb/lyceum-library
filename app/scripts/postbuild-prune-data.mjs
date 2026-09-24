// Removes dist/client/data when the build shipped an off-origin PUBLIC_DATA_ROOT.
//
// astro build always copies public/data into dist/client/data (the static
// assets directory -- @astrojs/cloudflare's adapter splits output into
// dist/client (static) + dist/server (Worker entry)) -- that copy is the
// full corpus (~555 MB, thousands of files today, growing with every wing).
// When PUBLIC_DATA_ROOT is set the app fetches corpus data from that origin
// (R2) instead, so the local copy is pure dead weight in the deploy artifact:
// it is what pushes the deploy toward the Worker free plan's 20,000-file cap
// (Lyceum P6 plan, Settled decision 3 / docs/p6-plan.md).
//
// NOT run as part of app's own `npm run build` chain: scripts/build-public.mjs
// runs check-links.mjs against this same dist BEFORE pruning (link checking,
// including the lemma index cross-check, needs the data files on disk), so
// build-public.mjs invokes this script itself, after check-links passes. A
// plain `npm run build` (same-origin, PUBLIC_DATA_ROOT unset, e.g. the
// zero-works/fixture builds) never needs pruning and this script no-ops.
//
// dist/client itself missing is fatal, not a silent no-op: that would mean
// astro build didn't run (or ran somewhere else), and a silent no-op here
// would let a build with the full local corpus still under dist/client (if
// it exists, just unpruned) or an entirely different, unpruned artifact ship
// to the deploy undetected.
import { existsSync, rmSync } from 'node:fs';

const root = process.env.PUBLIC_DATA_ROOT;
const CLIENT_DIR = 'dist/client';
const DATA_DIR = `${CLIENT_DIR}/data`;

if (root) {
  if (!existsSync(CLIENT_DIR)) {
    console.error(`postbuild-prune-data: ${CLIENT_DIR} not found -- astro build did not run (or ran elsewhere); refusing to no-op`);
    process.exit(1);
  }
  if (existsSync(DATA_DIR)) {
    rmSync(DATA_DIR, { recursive: true, force: true });
    console.log(`postbuild-prune-data: removed ${DATA_DIR} (PUBLIC_DATA_ROOT=${root})`);
  } else {
    console.log(`postbuild-prune-data: ${DATA_DIR} already absent (PUBLIC_DATA_ROOT=${root})`);
  }
} else {
  console.log('postbuild-prune-data: PUBLIC_DATA_ROOT unset, leaving dist/client/data in place');
}
