# The Lyceum Library acceptance script

`scripts/acceptance.mjs` checks a running Lyceum site the way a reader would
use it: it opens the site's own pages in a headless browser and reports what
actually rendered. It implements docs/lyceum-shared-repo-plan.md section
11.7. The plan says this script eventually lives in a `lyceum-contracts`
repository; that repository does not exist yet, so it lives here.

## What it checks

For every work under test, in order, stopping at the first failure:

1. **manifest-fetch** -- the work's manifest is reachable at the address the
   manifest index gives for it.
2. **manifest-hash** -- the manifest's bytes match the sha256 the index
   recorded for it.
3. **manifest-schema** -- the manifest validates against
   `schemas/lyceum-manifest.v1.json`.
4. **catalog-entry** -- `GET <origin>/catalog.snapshot.json` lists the work,
   the listed entry's own `facts.work` names the same lyceum key the work
   was found by, and its `facts.corpus_version` matches the manifest index's
   `corpus_version`.
5. **landing-renders** -- the work's landing page (`/texts/<author>/<work>/`)
   returns exactly 200 (not any 2xx), its description element (`.lp-lede`,
   inside `<main class="lp-body">`) matches the catalog description exactly,
   and the collections rendered at
   `[data-collections] [data-collection-id]` (also inside `<main>`) match
   the work's own merged-catalog collections exactly -- same ids, same
   names, **in the same order** `editorial.collection_ids` names them (a
   reversed or otherwise reordered rendering FAILs), and no id rendered
   twice. `mergeCatalog` applies the same draft-filtering rule as the page
   itself (shared/lib/lyceum-catalog-source.ts's `parseCatalog`): a
   collection in `draft` state is expected to be absent unless the run was
   given `--drafts`, matching `PUBLIC_LYCEUM_DRAFTS=1`. A work with no kept
   collections passes only when the page renders no `[data-collections]`
   element at all; a present-but-empty container is its own FAIL (the page
   should have omitted the element entirely). Scoped to `<main>` and to
   these specific elements,
   not a whole-page or whole-`<main>` text scan, because the sitewide
   Breadcrumb dropdowns on that page list every built author and work and
   render outside `<main>` -- a whole-page text scan would let that nav
   chrome alone satisfy the check regardless of this work's actual catalog
   membership, and a whole-`<main>` scan risked the same for any text that
   happened to contain a collection's name. If `<main class="lp-body">`
   itself is missing, the check FAILs outright (`FAIL ... landing-renders: no
   main.lp-body`) rather than falling back to scanning the whole page -- that
   fallback was the same whole-page false-PASS risk the `<main>` scoping was
   added to close.
6. **reading-renders** -- the work's first reading address (the manifest's
   `navigation.default_locus`) renders non-empty passage text.
7. **fixture-passages** -- the first, middle, and last passages named in the
   expected-passages fixture (below) render text starting with the words the
   fixture says they should. A work with no fixture entry does not fail this
   check; it is noted and checking continues.
8. **no-foreign-requests** -- while the reading page loads, no request goes
   to a host other than the site origin or the data origin (this is what
   would catch a stray WordPress asset).
9. **no-credentials** -- the landing and reading pages, and any same-origin
   script they load, contain no publish-token value, no literal
   `LYCEUM_PUBLISH_TOKEN=`, and no literal `Authorization: Bearer`.
10. **preset-marked** -- see "Preset colours" below.
11. **search-finds** -- the fixture's first passage is findable from the
    search page: every collapsed result group is expanded first (Search.svelte
    only renders `.inst-ref` anchors inside an expanded group), then the
    check requires an `.inst-ref` whose `href` names the expected passage
    itself (its work path and `loc=` column, matched on a full path segment --
    `letter-1` does not match a hit at `letter-10`), not merely the work. A
    work with no fixture entry does not fail this check.

A negative check whose own code throws an unexpected error (an abort, a
network error, anything not already turned into one of its own FAIL/SKIP
returns) does not escape the run either: it prints one
`FAIL negative:<name>: unexpected-error (<message>)` line, the same shape
the per-work loop already used, so every line and the summary still print.

Every fetch and browser navigation/action in this script carries a bounded
timeout (10s for a plain fetch, 15s for a Playwright navigation or action) --
a hung server or a stalled browser subprocess fails the run instead of
hanging it.

A single work whose checks throw an unanticipated error (not one of the
above's own FAIL/SKIP returns) does not abort the whole run: it prints one
`FAIL <work>: unexpected-error (<message>)` line and the run continues to
the next work. The browser process always closes, including on that path.

A work whose every check passes prints `PASS <work>`. The first failing
check prints `FAIL <work>: <check> (<detail>)` and stops that work's
checks. A check that could not run because a prerequisite is missing (no
manifest built, no fixture entry) prints `SKIP <work>: <reason>` instead,
and does not fail the run by itself.

Four checks run once per run, not once per work, printed as
`PASS negative:<name>` or `FAIL negative:<name>: <detail>`:

- **inactive-no-landing** -- a work that is not Active has no landing page
  (expects 404). Picks the first non-active catalog work found -- but when
  the build under test was built with `PUBLIC_LYCEUM_DRAFTS=1`, draft works
  ARE built and served (200, not 404), so a draft would fail this check for
  the wrong reason (confirmed against `posterior-analytics`, state `draft`).
  Pass `--drafts` for such a build: the check then skips drafts and picks a
  non-active, non-draft work instead, or prints `SKIP negative:inactive-no-landing:
  build includes drafts and every non-active work is a draft` if none exists.
- **unknown-translation-reported** -- every Active work whose manifest was
  actually fetched (regardless of whether its own per-work checks above
  passed, skipped, or failed later -- e.g. on catalog-entry) has its
  `editorial.default_translation` checked against the translations its
  manifest actually has. Prints `SKIP negative:unknown-translation-reported:
  no active work had its manifest fetched to check` rather than a bare PASS
  when no active work's manifest was fetched at all.
- **publish-rejects** -- `POST /api/catalog/publish` rejects a missing
  token and a wrong token with 401 (checked unconditionally). Without
  `LYCEUM_PUBLISH_TOKEN` set, the run stops there and prints
  `SKIP negative:publish-rejects: ...` -- the remaining cases need a real
  token to authenticate. With the token set: a malformed (non-JSON) body
  with the right token must get exactly 422 (matching
  `app/src/lib/catalog-runtime.ts`'s `handlePublish`, which always 422s
  invalid JSON -- never 400); then the script fetches
  `<origin>/catalog.snapshot.json` and checks its `x-catalog-source`
  response header before doing anything else with it. **The probe never
  writes to the site under test.** On a fresh origin (KV store empty,
  nothing published yet) that endpoint serves the bundled fixture, and
  `handlePublish` treats an empty store as a first publish, not a conflict
  -- replaying that fixture with its revision decremented would actually
  publish it and get 200, not the 409 this check wants. The route sends
  `x-catalog-source` on every response it serves, not only a degraded one
  (`app/src/pages/catalog.snapshot.json.ts`, via `catalog-runtime.ts`'s
  `catalogSourceHeader`): `kv` for a genuinely stored catalog,
  `fixture-fallback` for a degraded read (stored value malformed, or the
  KV read itself errored), `fixture` for the ordinary case of nothing
  published yet. The check is an allowlist on that header, not a denylist:
  only the exact value `kv` proceeds; the script SKIPs the stale half for
  anything else, with a reason that names what is actually known:
  - header absent -- `SKIP negative:publish-rejects: malformed-body case
    passed; x-catalog-source absent; cannot tell a stored catalog from the
    fixture, so the stale-revision probe is skipped`
  - header `fixture-fallback` or `fixture` -- `SKIP negative:publish-rejects:
    malformed-body case passed; catalog store empty or unreadable;
    stale-revision probe would publish`
  - any other value -- `SKIP negative:publish-rejects: malformed-body case
    passed; x-catalog-source=<value> is not the stored-catalog value`

  Only when the header is exactly `kv` does the script proceed -- replaying
  the served catalog verbatim with its `revision` decremented by one,
  expecting 409. If the served catalog has no `revision > 1` to make stale,
  that half is itself `SKIP`ped rather than failed.
- **reading-without-endpoint** -- with `/api/*` and `/catalog.snapshot.json`
  blocked, a reading page still returns a successful (2xx) final navigation
  response and its original-language passage-text subtree (the same
  `[data-column]` element `fixture-passages` reads, not the whole anchor
  including chapter-head/picker chrome) still renders (the page must not
  depend on either endpoint at request time).

Output ends with a summary line (`N passed, N failed, N skipped`) and the
process exits 1 if any work or negative check failed, 0 otherwise.

## Which works get checked

By default, every work whose editorial state is `active` in the merged
catalog (the committed live snapshot plus the local editorial seed, live
winning on a shared id -- the same merge
`shared/lib/lyceum-catalog-source.ts`'s `parseCatalog` does). A catalog work
with no entry in the data origin's manifest index prints
`SKIP <id>: not built in this release` rather than being silently dropped.

`--works a,b,c` restricts the run to exactly those work ids -- **our own
registry ids** (`EN`, `heraclitus-fragments`, `epistulae-morales`, matching
`shared/lib/registry.generated.ts` and the manifest index's own `path`
segment), not the partner's `lyceum:author.work` keys. An explicit id still
needs a manifest-built entry and a catalog state `mergeCatalog` keeps for
this run: `active` always, or `draft` when the run itself was given
`--drafts`. A named id that exists in the catalog but was dropped by that
rule prints `SKIP <id>: not active in the catalog (state <state>)` (Codex Sol
re-verification of 8131f40) rather than being checked against stand-in empty
catalog data -- pass `--drafts` alongside `--works` to exercise a work that
is still `draft` while it's being built out.

**As of this writing, none of the 103 locally-built works carry
`editorial.state: "active"`** (they're all draft, per `fixtures/editorial.seed.json`,
pending John's review) and none of the partner's 51 Active works are built in
this checkout. A default run therefore prints only `SKIP ... : not built in
this release` lines for every Active work plus the four negative checks --
correct, not a bug. Use `--works --drafts` to exercise the checks against
specific built draft works during development.

## Running it locally

```
nvm use 22   # system node is out of the >=22.12 <24 engines range

# Build with the demo chrome and drafts on (from app/):
cd app
PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 npm run build

# Serve the build as a Worker (from app/):
npx wrangler dev --config dist/server/wrangler.json --port 8787
```

Then, from the repo root:

```
node scripts/acceptance.mjs --origin http://localhost:8787 --data-origin http://localhost:8787 --drafts
node scripts/acceptance.mjs --origin http://localhost:8787 --data-origin http://localhost:8787 --drafts \
  --works EN,heraclitus-fragments,epistulae-morales
```

The build command above sets `PUBLIC_LYCEUM_DRAFTS=1`, so pass `--drafts` to
match -- see the **inactive-no-landing** entry above.

### wrangler dev gotchas hit while building this script

- **Spawning `workerd` needs the sandbox disabled.** Under this harness's
  default Bash sandbox, `wrangler dev` prints its binding table and then
  hangs forever -- `workerd` never gets spawned in a state that binds the
  port. Run the `wrangler dev` command (and any script, like this one, that
  launches a headless browser subprocess) with the sandbox disabled.
- **The full `dist/client` asset tree (≈21,700 files under `app/dist/client/data`,
  one directory per work) makes local `wrangler dev` hang indefinitely**, not
  just start slowly -- confirmed by reproducing instantly against a
  one-file assets directory, then against a trimmed copy of `dist/client`
  keeping only a few works' data (which starts in single-digit seconds,
  after printing a "assets directory watcher hit a platform limit" warning
  that the full tree apparently never gets far enough to print). This looks
  like a `wrangler`/`workerd` local-assets scaling limit against this many
  files and directories, not a bug in the site. Workaround used here: copy
  `dist/client`, keep only the works under test in `data/`, and point a copy
  of `dist/server/wrangler.json` (`assets.directory` changed, kept in
  `dist/server/` so the config's relative `main` still resolves) at the
  trimmed copy. This is a local dev-loop workaround only -- the real build,
  its data, and its deploy are untouched.
- **`kv_namespaces[].id: "<kv-id>"` is not a real problem locally** -- local
  `wrangler dev` simulates KV without validating the id against a real
  Cloudflare account, so the placeholder in `app/wrangler.jsonc` needs no
  workaround for local testing.

### The manifest index address

The plan (section 11.3) says the data origin serves `/manifests/index.json`
at its root. A local build with `PUBLIC_DATA_ROOT` unset instead serves data
same-origin under `/data/` (`app/scripts/postbuild-prune-data.mjs`,
`shared/lib/data.ts`), so the index sits at `/data/manifests/index.json`.
This script tries `/manifests/index.json` first and falls back to
`/data/manifests/index.json`.

Each index entry's own `url` field (`data_root` + `path`) is not used to
fetch the manifest: `data_root` is whatever the build that emitted the index
expected to publish to (a real R2 address, even for a local dev build), so
it is not reachable from a local run. Instead the script resolves
`entry.path` against wherever it fetched the index FROM -- climbing out of
the index's own `manifests/` directory back to the data root, the same
resolution the plan's own "no data root: resolve against the index's own
origin" rule describes, generalised to "resolve against the index's own
location" so it also works when the index sits under `/data/`. On a real
deploy, where the index is served from the data root itself, this produces
the exact same address as `data_root + path`.

"Wherever it fetched the index FROM" is `res.url` (the address actually
served, following any redirect the server issued), not the candidate URL
requested -- a redirected index must resolve entries against where it truly
lives. A 200 response whose body isn't valid JSON is treated as a failed
candidate, same as a non-2xx status or a network error: the script falls
through to the next candidate path rather than throwing.

## The expected-passages fixture

`--fixture <path>` (default `fixtures/acceptance/expected-passages.json`)
names three passages per work -- first, middle, and last -- with the reading
address and the opening words a human checked against the edition:

```json
{
  "schema_version": 1,
  "works": {
    "<workId>": {
      "edition": "<edition named in the work's source note>",
      "reviewed_by": null,
      "passages": [
        { "position": "first", "address": "/read/<author>/<work>/<division>#<anchor>", "language": "grc", "opening": "..." },
        { "position": "middle", "...": "..." },
        { "position": "last", "...": "..." }
      ]
    }
  }
}
```

`workId` is the same short id `--works` takes. `language` is `grc`, `lat`,
or `en` and picks which search box `search-finds` types into. `reviewed_by`
is `null` until a person has checked the opening words against the edition;
a work whose entry has `reviewed_by: null` still runs normally but its PASS
line reads `PASS <work> (fixture unreviewed)`.

A passage may also carry a `search` string -- the phrase `search-finds`
types into the search box. The check searches for the `first` passage only,
so only that passage's `search` is used. It's optional: without one, the check falls back
to the first three words of `opening`, which works fine when the passage's
own words open the entry but not when `opening` leads with a source
citation or title (Heraclitus B1's "SEXT. adv. math. VII 132 ...", Seneca
Letter 1.1's "AD LVCILIVM EPISTVLAE ..."). John sets or confirms `search`
as part of the same passage review that sets `reviewed_by` (item 102).

**The committed fixture is unreviewed.** Its three entries (`EN`, Bekker;
`heraclitus-fragments`, DK; `epistulae-morales`, Seneca's letters) were
seeded by this change from the built corpus data itself (the same
`segments[].greek`/`segments[].column` text the reader renders from), not
independently checked against the printed edition by a person -- the plan
requires the latter. **John needs to review the three `opening` strings
against the editions named and set `reviewed_by` to his name** before this
fixture is trustworthy as a contract check rather than a
render-matches-itself smoke test.

The script exits 2 with a list of problems if the fixture doesn't match this
shape (missing `schema_version`, a passage missing `position`/`address`/
`language`/`opening`, a work with only one passage or two passages sharing a
position instead of exactly one `first`, one `middle`, and one `last`, etc.)
-- a malformed fixture is a script bug or an editing mistake, never silently
ignored.

## Preset colours (provisional)

Presets and theme colours are read from the catalog but not yet applied to
the page (plan section 10, decision 12) -- no CSS reacts to `data-preset`
today. The **preset-marked** check is deliberately narrow until that
ruling lands: it only confirms `<body data-preset>` equals the work's own
`editorial.preset`, or the catalog's default preset when the work names
none. It will widen to check actual rendered colours once the colour
treatment is implemented and ruled on.

## Flags

```
--origin <url>          required: the site under test
--data-origin <url>     required: where manifests and /data/ live
--works a,b,c           restrict to these work ids; default is every Active work
--fixture <path>        expected-passages fixture (default: fixtures/acceptance/expected-passages.json)
--live-catalog <path>   committed live catalog file (default: fixtures/catalog.snapshot.v2.live-2026-09-08.json)
--seed-catalog <path>   committed editorial seed file (default: fixtures/editorial.seed.json)
--drafts                the build under test includes draft works (PUBLIC_LYCEUM_DRAFTS=1)
--help                  print usage and exit 0
```

Env: `LYCEUM_PUBLISH_TOKEN`, when set, is used for the authenticated half of
the `publish-rejects` negative check and is also scanned for in page/script
text by `no-credentials`.

## Tests

`scripts/__tests__/acceptance.test.mjs`, run with node's own test runner
(the same way `scripts/__tests__/verify-release.test.mjs` runs -- there is
no vitest config at the repo root):

```
nvm use 22
node --test scripts/__tests__/acceptance.test.mjs
```

The tests cover the pure parts only (argument parsing, fixture validation,
the live+seed catalog merge, work selection, the foreign-request and
credential scanners, opening-words matching, and result-line formatting) --
no browser, no network.

## Rehearsal, 2026-09-23

First end-to-end local run of the whole pipeline this document describes --
build, trimmed `wrangler dev`, a publish, then `scripts/acceptance.mjs`
itself -- against three real, built works (EN, heraclitus-fragments,
epistulae-morales), stopping short of any deploy. Plan:
`~/.claude/plans/plan-4-5-7-rehearsal-release-plato.md`, task 4; checklist:
`docs/todo/acceptance-rehearsal.md`. All commands ran from the repo root
unless noted; the site under test was built from today's `build/dist`
(`corpus_version 2026.09.23-41be670`).

### Commands

```
cd app
PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 npm run build

# Trim dist/client/data to the three works plus lsj, manifests, reports,
# .mounts, and the four root JSON files (lemmata.json, lemmata-lat.json,
# citation-index.json, RELEASE.json) into a scratchpad copy; copy dist/server
# whole (entry.mjs + chunks need to sit next to wrangler.json for its
# relative "main" to resolve) and repoint its wrangler.json assets.directory
# at the trimmed client copy.

npx wrangler dev --config <scratch>/dist-server/wrangler.json --port 8787 \
  --var LYCEUM_PUBLISH_TOKEN:<random local token>   # sandbox disabled for this one

# Rehearsal catalog: fixtures/catalog.snapshot.v2.live-2026-09-08.json merged
# with fixtures/editorial.seed.json via the same live-wins-by-id rule
# shared/lib/lyceum-catalog-source.ts's mergeById uses (neither that module
# nor scripts/acceptance.mjs's own mergeCatalog exports a function that hands
# back raw, unflattened records, so the rule was mirrored, not reinvented, in
# a small scratchpad script), the three works' editorial.state flipped to
# "active", revision bumped past the live snapshot's, integrity.digest a
# sha256 over a sorted-key canonical serialization (the server doesn't verify
# this yet -- any stable method is fine, see app/src/pages/api/catalog/
# publish.ts's own TODO).

curl -X POST http://localhost:8787/api/catalog/publish \
  -H "content-type: application/json" -H "Authorization: Bearer <random local token>" \
  --data-binary @<rehearsal-catalog.json>

LYCEUM_PUBLISH_TOKEN=<random local token> node scripts/acceptance.mjs \
  --origin http://localhost:8787 --data-origin http://localhost:8787 \
  --live-catalog <rehearsal-catalog.json> --drafts \
  --works EN,heraclitus-fragments,epistulae-morales
```

`--works` was passed explicitly: the rehearsal catalog also carries the
partner's 51 live-snapshot works, and every one of them is already
`editorial.state: "active"` in that committed file -- a default (no
`--works`) run would additionally print 51 `SKIP ... not built in this
release` lines (correct and explained, just noise) for works this checkout
never built. Restricting to the three rehearsal ids keeps the run to exactly
what this rehearsal is about.

The `--var` token: generated locally with `openssl rand -hex 24`, kept only
at a scratchpad path (`chmod 600`), passed to `wrangler dev` with `--var
LYCEUM_PUBLISH_TOKEN:<value>` and to `scripts/acceptance.mjs` via the
`LYCEUM_PUBLISH_TOKEN` env var. No `app/.dev.vars` or any other repo file was
written with it, and it is not reproduced above or anywhere else in this
document.

### Negative-probe results

| Probe | Expected | Got |
| --- | --- | --- |
| No `Authorization` header | 401 | 401 |
| Wrong token | 401 | 401 |
| Correct token, missing `content-type` | 403 | 403 |
| Correct token + `content-type`, malformed JSON body | 422 | 422 |
| Valid catalog, `revision` lower than stored | 409 | 409 |

Positive flow: POST the rehearsal catalog (revision 13) -> `200
{"ok":true,"revision":13,...}`; `/library/` and `/catalog.snapshot.json` then
both carry `x-catalog-source: kv`; re-POSTing the identical body -> `200`
again (idempotent, same revision + digest).

**`x-catalog-source` does not appear on `/`.** The rehearsal step list called
for checking it there; in fact only `/library/` and
`/catalog.snapshot.json.ts` set that header (`app/src/pages/library/
index.astro:51` and `app/src/pages/catalog.snapshot.json.ts:33`) --
`PUBLIC_LYCEUM_CHROME=1`'s site root renders `LyceumHome.astro`, which never
reads the live catalog and sets no such header. `/` was confirmed 200 as
asked; the `fixture`/`kv` transition was instead confirmed on `/library/`.

### Acceptance run

Two bugs surfaced on the first passes; both diagnosed and one fixed (see
below). The stable, final, twice-reproduced result:

```
FAIL EN: no-foreign-requests (https://fonts.googleapis.com/css2?family=Cardo:ital@0;1&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap)
FAIL heraclitus-fragments: no-foreign-requests (https://fonts.googleapis.com/css2?family=Cardo:ital@0;1&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap)
FAIL epistulae-morales: no-foreign-requests (https://fonts.googleapis.com/css2?family=Cardo:ital@0;1&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap)
SKIP negative:inactive-no-landing: build includes drafts and every non-active work is a draft
PASS negative:unknown-translation-reported
PASS negative:publish-rejects
PASS negative:reading-without-endpoint

3 passed, 3 failed, 1 skipped
```

This does **not** meet the rehearsal's own target (3 PASS, 0 FAIL) --
`docs/todo/acceptance-rehearsal.md`'s acceptance-run box is left unticked.
The remaining failure is real, not a rehearsal artifact:

- **`no-foreign-requests`: `fonts.googleapis.com` (real, not fixed here).**
  Every page built with `PUBLIC_LYCEUM_CHROME=1` -- the same flag every real
  demo/staging/production build in `docs/cloudflare-setup.md` uses -- loads
  the Cardo/EB Garamond stylesheet from Google Fonts. This is deliberate site
  design (the reader's own service-worker test suite,
  `app/src/__tests__/sw.test.ts`, explicitly exercises caching an opaque
  cross-origin Google Fonts response), and the check is deliberately strict
  about it: `scripts/__tests__/acceptance.test.mjs`'s own `foreignRequests`
  test asserts `fonts.googleapis.com` gets flagged, in the same test case as
  a literal WordPress-plugin-asset example. Both sides are working as
  designed; they simply haven't been reconciled. This looks like the first
  time the full check suite has run end-to-end against a `PUBLIC_LYCEUM_
  CHROME=1` build with a real active work, which is what this rehearsal was
  for. Fixing it means either self-hosting/vendoring the two typefaces (a
  real, sitewide change touching every page) or a deliberate, reviewed
  exception to the check -- a design call, not a rehearsal fix. Flagged for
  follow-up; not touched here.

Two other findings, both resolved:

- **`fixture-passages` false FAIL, fixed** (`scripts/acceptance.mjs`,
  `findColumnText`, ~line 594-611). The first run failed EN's `first` fixture
  passage: the fixture expects the rendered text to start "Πᾶσα τέχνη...",
  but the checked element's own `innerText` started "1 Πᾶσα τέχνη..." -- the
  Reader's own `.line-num` gutter label for line 1094a-1
  (`shared/components/Reader.svelte`, marked `user-select: none` there
  specifically so a person's own select-and-copy never picks it up) was
  being read as part of the passage text. Manually reproduced in a live
  browser against the rehearsal server before touching anything. Fixed by
  stripping `.line-num` descendants (on a detached clone, so the live DOM is
  untouched) before reading `textContent`, in both the source-language and
  `.english-col` branches of `findColumnText` -- the same "read what a
  person would actually read" boundary the function's own comments already
  describe for the chapter-head/translation-picker chrome it excludes by
  scoping to `[data-column]`/`.english-col` in the first place. No unit test
  added: `findColumnText` is browser-DOM-bound (`page.evaluate`) and has
  never had one -- this file's own `## Tests` section above says its
  coverage is "the pure parts only... no browser, no network," and the
  function's two prior fixes (Sol review findings 5 and B, both in its own
  comments) were verified the same way this one was: a live re-run, twice,
  both clean. `node --test scripts/__tests__/acceptance.test.mjs` still
  passes all 88 existing cases unchanged.
- **`catalog-entry` false FAIL, a rehearsal-setup issue, not a code
  fix.** The first rehearsal catalog reused `fixtures/editorial.seed.json`'s
  own `facts.corpus_version` for the three works verbatim
  (`2026.09.13-01e3d2f`), which no longer matches today's build's manifest
  index (`2026.09.23-41be670`) -- the committed seed was last regenerated
  2026-09-22, a day before today's corpus rebuild. Not a script or endpoint
  bug: the seed genuinely is one rebuild behind, which
  `scripts/build-editorial-seed.mjs` fixes by design (never hand-edited).
  Regenerating that committed file was out of this rehearsal's scope (it
  would touch all 103 local works, not just the three under test), so the
  scratchpad catalog-builder script instead reads the corpus_version the
  build under test is actually serving, live, from the wrangler dev origin's
  own manifest index, and stamps the three rehearsal works with that value.
  Worth a `build-editorial-seed.mjs` re-run before the next rehearsal or
  review that reads the seed file directly.
- **One unreproduced flake.** A single run saw `negative:publish-rejects`'s
  "wrong token" probe get `500` instead of `401`; the `wrangler dev` log
  showed `Error inside ProxyWorker ... Network connection lost` for that one
  request, under concurrent Playwright + fetch load. An immediate manual
  curl retry got `401`; the whole acceptance run was repeated twice more and
  got a clean `401` both times. Read as local `wrangler dev` flakiness under
  load, not a defect.

### What surprised

- **Local `wrangler dev` start time.** This document's own "wrangler dev
  gotchas" section above describes the trimmed-`dist/client` workaround
  starting "in single-digit seconds." This rehearsal's trimmed copy left the
  rest of `dist/client` (the full local build's own rendered HTML for all
  103 works, ~8,800 files) untouched -- only `data/` was trimmed, as
  instructed -- and `workerd` took roughly 2.5-3 minutes to bind port 8787,
  not single digits. Plausibly that earlier note's own trial build didn't
  carry every author's rendered pages outside `data/`. Still far short of
  the full untrimmed tree's "hangs indefinitely."
- Everything else matched the documented recipe: the top-level `wrangler`
  config (placeholder KV id, no R2 binding, no `env` selected) needed no
  changes; local KV simulated the publish/read cycle correctly; the
  guard-rail probes (401/401/403/422/409) all matched on the first try.

### Re-run, 2026-09-23 -- fonts self-hosted

John's ruling, same day: the site must not load fonts from Google. The
`no-foreign-requests` failure above (`fonts.googleapis.com`) is fixed by
self-hosting every Google-Fonts family the site loads, not only Cardo and EB
Garamond -- the reading page also pulls Public Sans (lyceum chrome UI) and,
on `media="print"`, Bodoni Moda + DM Mono (the print masthead), and a
same-origin-only guard test would still fail on any of those.

**What changed.** `shared/styles/fonts.css` (new) holds 32 `@font-face` rules
copied verbatim (family, style, weight, `unicode-range`, `font-display`) from
Google's own `css2` API response for the five families/weights/styles this
site already requested, fetched with a modern-browser user agent so the API
returned woff2 (`curl -A "<Chrome UA>" "https://fonts.googleapis.com/css2?family=Cardo:ital@0;1&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Public+Sans:wght@400;600&family=Bodoni+Moda:ital,wght@1,600&family=DM+Mono:wght@400&display=swap"`).
Kept only the subsets the site needs -- latin + latin-ext for every family,
plus greek + greek-ext for Cardo and EB Garamond, the two faces that render
Greek passage text (Public Sans/Bodoni Moda/DM Mono are UI chrome and the
print masthead, English-only). 22 distinct woff2 files came out of that (some
`@font-face` rules share a file -- e.g. EB Garamond's 400/500/600 normal
weights and Public Sans's 400/600 are the same variable-font file per subset,
just declared at different `font-weight` values), 588 KB total, well inside
the ~2 MB budget. `shared/styles/fonts/` holds the woff2 files plus each
family's `OFL-<family>.txt` (SIL Open Font License 1.1, fetched from
`github.com/google/fonts`). `shared/styles/global.css` `@import`s
`./fonts.css` at the top, so every page that already does
`import '@shared/styles/global.css'` gets the local `@font-face` rules for
free; the `<link rel="preconnect">`/`<link ... css2?...>` tags to Google were
removed from all 15 files that carried them (`app/src/components/{LyceumHome,
ClassicHome,ReaderShell,Landing}.astro`; `app/src/pages/{404,attribution,
authors,support,search,[author]/index,catalog/[...slug]}.astro`;
`app/src/pages/lemma/{grc,lat}/{entry,index}.astro`). `app/public/sw.js`'s
now-dead cross-origin `fonts.googleapis.com`/`fonts.gstatic.com` cache-first
branch was removed (self-hosted fonts are hashed under `/_astro/`, covered by
the existing same-origin cache-first branch); its `app/src/__tests__/sw.test.ts`
coverage (`cacheFirst: an opaque cross-origin Google Fonts response`) was
removed too, with a comment explaining that `cacheFirst`'s remaining caller
(the `/_astro/` branch) is same-origin and never opaque, so there is no
longer a real request path for that arm to cover.

A new guard test, `app/src/__tests__/no-google-fonts.test.ts`, walks
`app/src`, `shared/` (excluding `__tests__`) and `app/public` and fails if
any source file matches `fonts.googleapis.com` or `fonts.gstatic.com`.
Run against the pre-fix tree (`git stash` of just the font-related files) it
failed correctly, listing all 15 `.astro` offenders plus `app/public/sw.js`;
restored, `npx vitest run` is green in both `app/` (15 files, 207 tests) and
`shared/` (44 files, 1057 tests), `tsc --noEmit -p app` is 0 errors, and
`npm run build` (`app/`) is green with zero `googleapis`/`gstatic` references
anywhere under `dist/client` and all 22 fonts fingerprinted under `/_astro/`
(e.g. `_astro/cardo-italic-greek.CVrcLkMl.woff2`).

**`findColumnText`.** Still browser-DOM-bound (`page.evaluate`, `cloneNode`,
`querySelectorAll`) -- extracting its `.line-num`-stripping fix into a
Node-testable pure helper would need a DOM implementation `scripts/` doesn't
depend on today, which is exactly the "no browser, no network" boundary
`scripts/__tests__/acceptance.test.mjs` is designed to keep, and adding one
would be a new npm dependency for a single test. Left as documented above:
the already-pure part of this function (`stripColPrefix`) was extracted and
unit-tested before this rehearsal ever started, unchanged by the fix; the fix
itself is covered by the rehearsal run, same as its two prior fixes.

**Commands** (from `app` unless noted): `PUBLIC_LYCEUM_CHROME=1
PUBLIC_LYCEUM_DRAFTS=1 npm run build`; trimmed `dist/client` (kept the whole
tree, replaced `data/` with `lsj`, `manifests`, `reports`, `.mounts`,
`lemmata.json`, `lemmata-lat.json`, `citation-index.json`, `RELEASE.json`,
and `EN`/`heraclitus-fragments`/`epistulae-morales`) and a `dist/server`
copy repointed at it, same recipe as the first rehearsal; `wrangler dev`
back up on `:8787` with a fresh random `--var LYCEUM_PUBLISH_TOKEN` (sandbox
disabled); the scratchpad catalog builder re-run against the live manifest
index (`corpus_version` unchanged at `2026.09.23-41be670`, so the stamped
catalog needed no other change); publish; then `scripts/acceptance.mjs`
`--works EN,heraclitus-fragments,epistulae-morales --drafts --live-catalog
<rehearsal catalog>`.

**Negative probes**: 401/401/403/422 unchanged from the first rehearsal;
publish (revision 12) -> `200`; `/library/` and `/catalog.snapshot.json`
both `x-catalog-source: kv`; resend -> `200` idempotent.

**Acceptance run:**

```
FAIL EN: search-finds (no result link found for /read/aristotle/nicomachean-ethics/book-1#col-1094a)
FAIL heraclitus-fragments: search-finds (no result link found for /read/heraclitus/fragments/text#col-b1)
FAIL epistulae-morales: search-finds (no result link found for /read/seneca/epistulae-morales/letter-1#col-1.1)
SKIP negative:inactive-no-landing: build includes drafts and every non-active work is a draft
PASS negative:unknown-translation-reported
PASS negative:publish-rejects
PASS negative:reading-without-endpoint

3 passed, 3 failed, 1 skipped
```

**`no-foreign-requests` now passes on all three works** -- confirmed
separately in a live browser against the same rehearsal server: the reading
page's `getComputedStyle` resolves the Greek column to `Cardo, "Gentium
Plus", "Noto Serif", Georgia, serif` and the English column to `"EB
Garamond", Georgia, "Times New Roman", serif` (the source CSS is untouched,
so the family names and fallback chains are exactly what they were), and
`document.fonts` reports `Cardo`, `EB Garamond` and `Public Sans` all
`loaded`, with zero network requests to any `google`/`gstatic` host on that
page. This is the target this font change set out to meet, and it is met.

This run does **not** reach the rehearsal's overall target (3 PASS, 0 FAIL)
-- `docs/todo/acceptance-rehearsal.md`'s "Rehearsal re-run" box is left
unticked -- but for a different, unrelated reason than the first run.
`search-finds` (check 11) never ran in the first rehearsal: checks stop at a
work's first failure, and `no-foreign-requests` (check 8) already stopped
all three works before reaching it. With that failure fixed, `search-finds`
is now the first thing to fail, and it is a real, pre-existing defect, not a
font or rehearsal-environment artifact:

- **Not a data-trimming artifact.** The browser console shows the search
  page's own graceful-skip path (`search: skipping <work> -- HTTP 404 for
  <work>/meta.json`) for every one of the ~150 other registered works whose
  `data/` this rehearsal's trim omits -- expected, and not fatal to the
  works that matter here. `EN/search/{meta,lemma,form}.json` all load `200
  OK`.
- **Reproduced directly.** On the rehearsal server's `/search` page, typing
  the fixture's own opening words for EN (`Πᾶσα τέχνη καὶ`, "Lemma" match,
  the page's default) returns "No passages found." So does `Πᾶσα τέχνη`
  (dropping the function word, in case `καὶ` was the problem) and even
  `Πᾶσα` alone. Switching only the match mode from "Lemma" to "Exact form"
  finds `Πᾶσα` in 27 places, including Nicomachean Ethics I -- so the word
  and the index both have it; **lemma matching specifically fails to map
  the inflected form `Πᾶσα` to its lemma** (search alone, `τέχνη`, finds 50
  instances under Lemma mode without trouble, so this isn't every word --
  the site's own default reading-page search box uses Lemma mode). This
  looks like a genuine, previously-unverified defect in lemma-form
  matching for at least this one common adjective (πᾶς), not anything this
  rehearsal or the font change touched.

Flagged for follow-up, not fixed here: diagnosing lemma matching is a
different subsystem (`Search.svelte` / the lemma-search index build) than
what this rehearsal set out to change, and well outside a font-hosting
change's blast radius.

`wrangler dev` stopped (`kill`, confirmed with `lsof -iTCP:8787` -- nothing
listening); the scratchpad's trimmed `dist-client`/`dist-server` copies and
the rehearsal catalog stay in the scratchpad, not the repo.

### Final re-run, 2026-09-23

Since the fonts re-run above, John ruled Lemma mode must accept a word as
printed, not only its typed-headword form; that fix landed (`Search:
Lemma mode accepts a word as printed`) and each fixture passage was given
its own `search` phrase (`Πᾶσα τέχνη καὶ`, `τοῦ δὲ λόγου`, `Ita fac, mi`) so
`search-finds` no longer has to derive one from `opening`. This run repeats
the exact recipe above end to end against a fresh build (`corpus_version
2026.09.23-0fe2f95`): `PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 npm run
build`, the same `dist/client` trim (`data/` kept to `lsj`, `manifests`,
`reports`, `.mounts`, the four root JSON files, and `EN`/
`heraclitus-fragments`/`epistulae-morales`), `wrangler dev` on `:8787` with
a fresh random `--var LYCEUM_PUBLISH_TOKEN`, the scratchpad catalog builder
re-run against the live manifest index, and a fresh publish. Negative
probes unchanged: 401/401/403/422/409, publish (revision 12) -> `200`,
`/library/` and `/catalog.snapshot.json` both `x-catalog-source: kv`,
resend -> `200` idempotent.

```
PASS EN (fixture unreviewed)
PASS heraclitus-fragments (fixture unreviewed)
PASS epistulae-morales (fixture unreviewed)
SKIP negative:inactive-no-landing: build includes drafts and every non-active work is a draft
PASS negative:unknown-translation-reported
PASS negative:publish-rejects
PASS negative:reading-without-endpoint

6 passed, 0 failed, 1 skipped
```

Reproduced twice, identical both times. The rehearsal's target (3 PASS,
0 FAIL, negative checks pass, every SKIP explained) is met. `wrangler dev`
stopped and port 8787 confirmed free.
