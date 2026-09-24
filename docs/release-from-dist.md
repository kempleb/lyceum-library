# Building from a release, not from the corpus

This is the seed of the OPERATOR-RUNBOOK Brian's brief asks for
(`docs/lyceum-build/handoff-2026-09-12/START-HERE.md`, "Hosting and
reproducibility"): a fresh checkout plus one approved release artifact must
build the deployable site with no TLG/PHI, no text-pipeline run, no sibling
repository, and nothing else from John's machine.

## What a release is

A release is a copy of a prior full build's `build/dist` directory, plus one
file it does not otherwise carry: `RELEASE.json`, written by
`scripts/release-index.mjs`. `RELEASE.json` lists every non-derived release
file (relative path, byte size, sha256), the corpus version and
producer commit that built it, and the schema versions in force
(`schema_version` for RELEASE.json's own shape, `manifest_schema_version` for
`manifest.json`, `catalog_schema_version` for the partner catalog view).
Anything under `build/dist/reports/` is diagnostics, not release content, and
is excluded from the index. The index also excludes files the checkout rebuilds
from release data and build-time settings: `citation-index.json` (written by
`scripts/build-citation-index.mjs`); `manifests/index.json` and each
`<work>/manifest.lyceum.json` (written by
`scripts/emit-lyceum-manifest.mjs`); and `lemmata.json`, `lemmata-lat.json`,
`lemmata/`, and `lemmata-lat/` (written by `app/scripts/build-lemmata.mjs`). These are
not release content. `RELEASE.json` records the text-pipeline output, while
verification ignores those derived files. A release must contain only regular
files and directories; any symlink or other special entry makes indexing and
verification fail.

## Publishing a release

A full build (`node scripts/build-public.mjs`, no `--from-dist`) writes
`build/dist/RELEASE.json` before the Astro build. After Astro generates the
derived lemma files, the build verifies the release again. This final check
ensures every indexed release file still matches and that no non-derived file
appeared after indexing. To publish it:

```
node scripts/publish-release.mjs --bucket <bucket>
```

Never overwrite an existing version's folder — each `releases/<version>/` is
immutable once published, matching `docs/lyceum-shared-repo-plan.md` §4's
"nothing overwrites a live folder." `publish-release.mjs` publishes a fresh
folder, resumes an incomplete one by adding only local files absent from R2,
and refuses a folder with changed or extra remote objects.

## Fetching and building from a release

```
node scripts/fetch-release.mjs <version> build/dist
node scripts/build-public.mjs --from-dist build/dist
```

`fetch-release.mjs` downloads `releases/<version>/` from R2 (bucket from
`READER_R2_BUCKET`, default `classical-philosophy-reader-data` per
`docs/cloudflare-setup.md`) and verifies the download against its own
`RELEASE.json` before handing it back. `verify-release.mjs <dir>` does the
same check standalone, callable by hand against any directory.

`--from-url` assumes single-writer use: its destination directory must be a
fresh folder -- empty or not yet existing -- that no other process writes to
for the duration of the fetch. It refuses outright if the destination
already has anything in it, and refuses rather than follows a symlink there
or inside it, including for the `RELEASE.json` and `.part` temp files it
writes, which it opens with an exclusive create. A second process (or a
second, concurrent fetch) renaming or replacing the destination directory
mid-fetch is a directory-swap race these checks do not defend against, and
is out of scope under that single-writer assumption.

An index written before commit 56d2c39 (2026-09-14) lists the derived files
and fails this check with `indexed a derived file`. No release was published
under that shape; if one turns up, re-index it with
`node scripts/release-index.mjs <dir>` before verifying.

`build-public.mjs --from-dist <dir>` (or the `READER_RELEASE_DIR` env var, if
no flag is given) copies `<dir>` into `build/dist` — unless `<dir>` already
*is* `build/dist` — verifies the copy against the release's own
`RELEASE.json`, and then runs only the stages that read `build/dist` and the
checked-out repository: the manifest/registry and inventory-hash checks, the
citation index, the route registry, preflight, contract validation, the
partner-catalog emission, an LSJ top-up **check** (below), the shared-LSJ
coverage gate, the Astro build, the link check, and (when `PUBLIC_DATA_ROOT`
is set) the data prune and pruned-artifact check. It skips the per-work text
pipeline, the translation turn-alignment pass, and the external-corpus mount
step entirely — those already ran when the release was built, and their
output is already inside it. It does not read `CORPUS_VERSION` from git in
this mode; it reads it directly from the copied-in `RELEASE.json`'s own
`corpus_version` (`fromDistCorpusVersion`, `scripts/release-index.mjs`,
commit `9ba7674`) — never via `manifests/index.json` or a work's
`manifest.json`, which may not exist yet on a release that was only
downloaded, not built, in this checkout.

`--from-dist` needs a non-empty directory argument. `--from-dist` with no
value, with another option in place of a value, or as `--from-dist=` fails
before the build touches the file system. An empty `READER_RELEASE_DIR` acts
as if it were unset. The source directory must be outside `build/dist`, unless
it is exactly `build/dist`; a source nested inside `build/dist`, or one that
contains `build/dist`, fails before the build removes or copies anything.

### Prerequisites for a fresh checkout

- Node 22 (`nvm use 22`).
- `npm ci` in `app/` and in `shared/`.
- `uv sync` in `pipeline/` — the Python venv is still needed for preflight,
  contract validation, the LSJ top-up check, and the shared-LSJ gate, but
  none of those need the corpus.
- No TLG/PHI corpus, no `~/Developer/aristotle-reader` (or any sibling
  corpus repository), and no local Diogenes install. None of the above are
  read in `--from-dist` mode.

### Env vars that matter

- `PUBLIC_DATA_ROOT` — if set, ships an off-origin (R2) data root: the Astro
  build's service worker points at it, and the build prunes `dist/client/data`
  and verifies the pruned deploy artifact. Unset ships the data alongside the
  site (same-origin).
- `PUBLIC_SITE_ORIGIN` — gates sitemap/canonical/robots-Sitemap emission.
  Unset means staging; never set it to a `*.pages.dev` address.
- `PUBLIC_LYCEUM_CHROME`, `PUBLIC_LYCEUM_DRAFTS` — the Lyceum-specific
  Astro flags; see `docs/lyceum-demo-handoff.md` for what each toggles.
- `READER_R2_BUCKET` — overrides the bucket `fetch-release.mjs` reads from.
- `READER_RELEASE_DIR` — the env-var form of `--from-dist <dir>`.

### What fails if the release was not fully topped up

The LSJ top-up (`reader_pipeline.lsj_topup`) fills in dictionary entries for
words referenced only by a mounted external corpus (never a classical work).
A full build runs it for real; `--from-dist` mode has no local Diogenes
install to regenerate from, so it instead runs
`reader_pipeline.lsj_topup --check-only`, which recomputes the same
mounted-only key set and checks each one for presence (not content) as an
entry in the release's own `build/dist/lsj/<letter>.json` shards. That set
can be empty (every word the mounted corpus uses already appears in a
classical work); then there is nothing to check and it exits zero. Otherwise
"fully topped up" means every key in the set is present in its shard. A shard
file whose top level is not a JSON object is reported as malformed, and every
key routed to it counts as missing. It exits non-zero (naming the count and
the first ten keys still missing from the shards) only if some key is
absent. `build-public.mjs` fails the build on that exit code
with a message that the release was not fully topped up — the fix is to
rebuild and republish the release with the mounted corpus present, not to
patch the downstream checkout.

## Proven without source access, 2026-09-23

Rehearsal for `docs/todo/rebuild-from-release.md`: can a fresh checkout plus
one published release build the site with no TLG/PHI and no sister repo
reachable at all, not just unused? Ran end to end in the scratchpad; nothing
here touched the main checkout's `build/` or `app/dist`.

**`fetch-release.mjs --from-url`.** Added a second transport alongside
rclone: HTTPS GETs (HTTP allowed only to localhost/127.0.0.1, for tests; a
redirect to a different origin is refused), Node stdlib only, bounded
concurrency (16) with a small retry on network errors and 5xx; a 4xx or a
size/sha256 mismatch is refused outright. Test-first: `scripts/__tests__/fetch-release.test.mjs`
against a local `node:http` server serving a synthetic release — seen
failing (`fetchReleaseFromUrl` not exported) before implementation, all 7
cases (existing rclone tests + the 3 new `--from-url` cases: good fetch,
sha256 mismatch refused, 404 refused) passing after. `node --test
scripts/__tests__/*.test.mjs`: 189 tests / 193 with subtests, 0 failed, 2
skipped (a symlink test the sandbox itself forbids).

**Fetch.** From the main checkout (read-only HTTPS GETs only):
```
node scripts/fetch-release.mjs 2026.09.22-25a4036 <scratch>/release \
  --from-url https://lyceum-library-staging.lyceum-institute.workers.dev/data
```
Landed 1,330 files, 388,188,298 bytes (~370 MiB) — RELEASE.json's own count,
smaller than a rough estimate going in. `verify-release` passed: every file
present at its recorded size and sha256, no extras.

**Fresh clone.** `git clone --no-local <main checkout> <scratch>/repo` (no
hardlinks back to the original). `npm ci` in `app/` and `shared/` (no root
lockfile), `uv sync` in `pipeline/` — all three clean.

**Sandbox control check.** `<scratch>/no-sources.sb`:
```
(version 1)
(allow default)
(deny file-read*
  (subpath "/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT")
  (subpath "/Users/johnboyer/Developer/aristotle-reader")
  (subpath "/Users/johnboyer/Developer/plato-reader")
  (subpath "/Users/johnboyer/Developer/classical-philosophy-reader"))
```
`sandbox-exec -f no-sources.sb /bin/cat` on a real TLG file, a file in
`aristotle-reader`, and a file in the original checkout all failed with
`Operation not permitted` (exit 1); `sandbox-exec -f no-sources.sb /bin/ls
<clone>` succeeded (exit 0).

**Build, inside the sandbox, in the clone, `TLG_DIR`/`PHI_DIR` unset.**
Bucket-mode `--from-dist`, the 2026-09-22 staging recipe minus the deploy
step:
```
DATA_FROM_BUCKET=1 CLOUDFLARE_ENV=staging PUBLIC_LYCEUM_CHROME=1 \
PUBLIC_LYCEUM_DRAFTS=1 PUBLIC_PARTNER_ORIGIN=https://library.lyceum.institute \
node scripts/build-public.mjs --from-dist <scratch>/release
```
run as `sandbox-exec -f no-sources.sb /bin/zsh <script>`, launched detached
and polled. 79 seconds (12:34:58–12:36:17). Stage plan matched
`--from-dist` exactly (pipeline-per-work, turn-align, mount-corpora,
clean-dist, release-index all `SKIP`). Registry agreement 62/62, inventory
hashes 51/51, preflight ok, contract validation ok (103 works), LSJ top-up
`--check-only` ok (5,452 regen keys, all present), shared-LSJ gate ok
(166,645 keys across 103 works), Astro build completed, check-links: 4,250
pages, 86,952 links, 12,403 anchors, **0 broken**. No `Operation not
permitted` anywhere in the build log — the sandbox was never the obstacle.

**Finding (not a sandbox block): bucket-mode `--from-dist` derives the wrong
data-root stamp on a genuinely fresh release copy.** The final gate,
`verify-pages-artifact.mjs`, failed:
```
FAIL: bucket data root "/data/25a4036-2026-09-22" does not match RELEASE.json
corpus_version "2026.09.22-25a4036" (expected data root
"/data/2026.09.22-25a4036")
```
Root cause: `build-public.mjs`'s `--from-dist` path computes `CORPUS_VERSION`
via `release-index.mjs`'s `readCorpusVersion(DIST_DIR)` immediately after
copying the release — before `emit-lyceum-manifest` (which runs much later
in the stage list) has written `manifests/index.json`. `readCorpusVersion`
prefers that file but it doesn't exist yet on a release that was only ever
downloaded, never built-from in this checkout, so it falls back to the first
top-level work's own `manifest.json`, which carries the *raw* pipeline stamp
(`<short commit>-YYYY-MM-DD`, e.g. `25a4036-2026-09-22`) rather than the
release's reformatted public stamp (`YYYY.MM.DD-<short commit>`,
`2026.09.22-25a4036`) — the exact drift the "one stamp, not two" fix
(2026-09-22, this same file) was written to close. It closed it for a full
build (which derives `CORPUS_VERSION` from `git rev-parse` +
`reorderCorpusVersion()`, never from `readCorpusVersion`) and for Brian's
existing recipe (`--from-dist build/dist`, source and dest the same
directory, so `manifests/index.json` from a prior local build is already
sitting there) — but not for this rehearsal's case: `--from-dist <a release
dir that was only ever fetched, never built>`. Every run reproduces it
identically, since `--from-dist` deletes and recopies `build/dist` from the
release on every invocation. Out of this task's edit scope
(`scripts/fetch-release.mjs` and this doc only); reported, not patched.

**Net result:** the no-source-access claim itself is proven — the build ran
the full stage list, including Astro and the link check, against a sandbox
that made TLG/PHI and every sister repo unreadable, and never once needed
them. The one gate that did fail (data-root stamp matching) is an unrelated,
pre-existing bug in the bucket-mode `--from-dist` combination, not a source
leak.

**Fix, same day.** `scripts/release-index.mjs` gained `fromDistCorpusVersion(distDir)`,
which reads a release's own `RELEASE.json` `corpus_version` directly — no
`manifests/index.json`-or-work-manifest fallback. `build-public.mjs`'s
`--from-dist` path now calls it for both the early source-version check and
`CORPUS_VERSION`, in place of `readCorpusVersion()`. `readCorpusVersion()`
itself and full-build mode are unchanged. Commit `9ba7674`; test-first
(`scripts/__tests__/from-dist-corpus-version.test.mjs`, seen failing before
the fix), full suite green (196 pass, 2 pre-existing skips).

**Second run, same rehearsal setup, after the fix.** Fresh clone pulled to
`9ba7674`; same command, same sandbox profile, same release copy. Completed
in about a minute (12:43:16–12:44:17). Same gates as before, now including
the one that failed the first time: registry agreement 62/62, inventory
hashes 51/51, preflight ok, contract validation ok (103 works), LSJ top-up
`--check-only` ok (5,452 regen keys), shared-LSJ gate ok (166,645 keys
across 103 works), Astro build completed, check-links 4,250 pages / 86,952
links / 12,403 anchors / 0 broken, and `verify-pages-artifact --release-json`
now passes: `OK -- data root matches RELEASE.json corpus_version=2026.09.22-25a4036`.
`corpus-version=2026.09.22-25a4036` in the build's own log line, `/data/2026.09.22-25a4036`
confirmed present in both `app/dist/client/sw.js` and `app/dist/client/index.html`.
No `Operation not permitted` anywhere in the log.
`docs/todo/rebuild-from-release.md`'s build-completion box is now ticked.

## Cross-family review hardening, 2026-09-23

GPT-6 Sol's review of `fetch-release.mjs --from-url` found four faults, fixed
test-first (`scripts/__tests__/fetch-release.test.mjs`): each new case was
written and run against the pre-fix code first; most failed outright, and a
couple of the defense-in-depth checks (e.g. the final inside-destDir
resolve) had no independent failure path to observe since nothing earlier in
the file could reach them incorrect. 18 total cases in the file passing
after; full repo suite 207 pass / 2 pre-existing skips.

- **Path safety (blocker).** Every path RELEASE.json lists is validated
  (`assertSafeRelativePath`) before any download starts: no leading `/`, no
  `..` or `.` segment, no backslash, no empty segment, no NUL. destDir and
  every already-existing directory inside it are refused if any is a
  symlink, checked before that path is written through; the final path is
  also asserted to resolve inside `realpath(destDir)`.
- **URL and version safety.** Each path segment is `encodeURIComponent`-
  encoded when building request URLs (spaces, `#`, `?`, non-ASCII all
  round-trip). `<version>` is validated with the same rule the `/data/
  <version>/` route itself uses (`isValidVersion`, `scripts/lib/data-source-
  mode.mjs`). The base URL must be `https:`, except `http:` to localhost/
  127.0.0.1 for tests; a redirect to a different origin is refused (checked
  via `response.redirected`/`response.url`, since Node's `redirect: 'manual'`
  makes a redirect response's status and Location header unreadable, the
  same as a browser's CORS-safe response).
- **Streaming, timeouts, backoff.** Each file streams to a size-capped
  `<path>.part` temp file (capped at RELEASE.json's own declared size for
  that file, refused if exceeded) and is renamed into place only on success;
  `verifyRelease` still checks the final sha256/size. Each request carries a
  timeout (`AbortSignal.timeout`, default 60s, overridable) and retries
  network errors, 5xx, and body-read errors with exponential backoff, up to
  3 attempts total. A 4xx, a cross-origin redirect, or a size overrun is
  refused immediately, unretried.
- **Queue stop.** The first fatal failure stops workers from taking new
  queue items; in-flight downloads are let to settle before the call
  rejects, so nothing is written after rejection.

Also fixed: this file's stale claim (just above) that `--from-dist` reads
`CORPUS_VERSION` from `manifests/index.json` or a work's `manifest.json` —
it has read it from the release's own `RELEASE.json` `corpus_version` since
commit `9ba7674`; and a stale comment in `scripts/release-index.mjs` that
still listed a `--from-dist` run against its own `build/dist` as a caller of
`readCorpusVersion()` — after `9ba7674`, `--from-dist` always uses
`fromDistCorpusVersion()` instead, regardless of source and destination.
