// Marks a build that carries held works (corpora/<name>/mount.yaml hold:
// true, mounted only under READER_INCLUDE_HELD=1) so `wrangler deploy`
// refuses it. See markHeldBuildUndeployable in scripts/lib/held-works.mjs.
// public/data is the data this build read (a symlink to build/dist in a
// real build); with no held work there, nothing is written.
import { markHeldBuildUndeployable, formatHeldWorksFindings } from '../../scripts/lib/held-works.mjs';

try {
  const findings = await markHeldBuildUndeployable({ dataDir: 'public/data', serverDir: 'dist/server' });
  if (findings.length) {
    console.warn('postbuild-held: this build carries held works; `wrangler deploy` will refuse it:');
    console.warn(formatHeldWorksFindings(findings));
  }
} catch (err) {
  console.error(`postbuild-held: ${err.message}`);
  process.exit(1);
}
