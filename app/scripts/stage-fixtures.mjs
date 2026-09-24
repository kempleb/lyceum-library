// Fixture-data staging step for a PUBLIC_READER_FIXTURES=1 build.
//
// public/data is a symlink to build/dist (the pipeline's emitted-data
// output — see app/public/data and app/scripts/build-lemmata.mjs's doc
// comment). CI carries no corpus data at all (no TLG/PHI access — see this
// repo's CLAUDE.md), so the only way to build+verify the sample-author/
// sample-work fixture route end to end is to stage the committed fixture
// JSON (fixtures/data/sample-work/, matching the shape pipeline/reader_pipeline/
// stage7_emit.py writes per work) into build/dist/ before `astro build` runs,
// exactly where a real pipeline run would have left it.
//
// Gated on the same flag as the works.ts/authors.ts fixture registry entries
// — whenever PUBLIC_READER_FIXTURES isn't '1', a normal build never stages
// fixture data, and instead unstages it: any fixture directory names left
// behind in build/dist by a prior fixture-on build are removed by name (never
// anything else — build/dist otherwise holds real pipeline output). build/ is
// entirely gitignored (see .gitignore), so this never touches a git-tracked
// path.
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const SRC = resolve(import.meta.dirname, '..', '..', 'fixtures', 'data');
const DEST = resolve(import.meta.dirname, '..', '..', 'build', 'dist');

if (process.env.PUBLIC_READER_FIXTURES !== '1') {
  if (existsSync(SRC) && existsSync(DEST)) {
    for (const name of readdirSync(SRC, { withFileTypes: true })) {
      if (!name.isDirectory()) continue;
      rmSync(resolve(DEST, name.name), { recursive: true, force: true });
    }
  }
  process.exit(0);
}

if (!existsSync(SRC)) {
  console.error(`stage-fixtures: fixture source '${SRC}' not found`);
  process.exit(1);
}

mkdirSync(DEST, { recursive: true });
cpSync(SRC, DEST, { recursive: true });
console.log(`stage-fixtures: staged ${SRC} -> ${DEST}`);
