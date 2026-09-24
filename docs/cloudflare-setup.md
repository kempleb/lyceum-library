# Cloudflare hosting setup ("Option B")

Decided 2026-07-15 (`ancient-philosophy-reader-plan.md` §5); condition: stays free
or near-free, and anything that would cost money is surfaced to John *before*
doing it (CLAUDE.md hard rule). One-time dashboard checklist plus the data-deploy
recipe future agents use.

## 0. Current state (2026-08-14)

Live, verified by command output — not planned:

| Thing | State |
|---|---|
| Cloudflare account | John's account `6ff75c6d6c06d1092df2c7efd42077ba` |
| R2 | Activated (payment method on file; usage still $0 — §5) |
| `wrangler` auth | Logged in via OAuth, `~/Library/Preferences/.wrangler/` |
| Bucket | `classical-philosophy-reader-data`, Standard storage class |
| Public origin | `https://pub-4ed50262412e44deb78c78b952f07f03.r2.dev` — **staging only** (§4) |
| CORS | Applied and read back; proven to work on `r2.dev` (step 6, step 2) |
| Cache-Control | Per-object at upload, proven to round-trip (step 7) |
| Corpus uploaded | **Yes** — re-synced 2026-08-20 (LSJ sense hierarchy): 13,481 objects, `rclone check --checksum` clean |
| Cross-origin reads | **Proven in a browser**, app code path included (§3) |
| Service worker | **Fixed 2026-08-14** — follows the data root off-origin (§3a) |
| Worker | **Demo live 2026-09-16:** `lyceum-reader-demo` at `https://lyceum-reader-demo.johnhboyer.workers.dev`, own catalog store `lyceum-reader-demo-catalog`; the live-site Worker is not created (ruling 2026-09-15: Worker with static assets, not Pages — see §1) |
| Data domain | **Not registered** — deferred to launch (step 2) |
| `PUBLIC_DATA_ROOT` in a real build | **Bakes in** — proven on a works-free build; not yet at corpus scale (§3) |

Neither the account ID nor the `r2.dev` hostname is a credential; both appear in
ordinary request URLs. The R2 API keys are the secret, and they live only in
John's `~/.config/rclone/rclone.conf` (mode 0600) — see §3.

Next action: create the Worker (step 3), then deploy a staging build with
`PUBLIC_DATA_ROOT` set. The domain (step 2) stays deferred until launch; nothing
is blocked on it.

**Update 2026-09-02 (staging deploy, John's go 2026-09-01):** Pages project
`lyceum-reader-demo` created by direct upload (`npx wrangler@latest pages
deploy dist --project-name lyceum-reader-demo --branch main`); live at
`https://lyceum-reader-demo.pages.dev` — staging only, never announced. The
first `build:public` with `PUBLIC_DATA_ROOT` set over real data ran clean
(3,883 pages, artifact 3,932 files, no `dist/data`). R2 mirrored from
`build/dist` with `rclone sync … --checksum` (17,456 objects, 555 MB, incl.
the Aristotle mount). Bucket CORS gained the demo origin — preview URLs
(`<hash>.lyceum-reader-demo.pages.dev`) are NOT allowed and will fail to
fetch data; test on the production URL. Permission rules for the sync and
the deploy live in `.claude/settings.local.json`, so redeploys need no hand
step. Demo builds set `PUBLIC_LYCEUM_CHROME=1`.

**Update 2026-09-16 (demo moved to a Worker, John's go the same day):** the
demo now runs as the Worker `lyceum-reader-demo` in John's account, set up by
the `demo` section of `app/wrangler.jsonc`. Redeploy:

1. `PUBLIC_DATA_ROOT=https://pub-4ed50262412e44deb78c78b952f07f03.r2.dev PUBLIC_LYCEUM_CHROME=1 CLOUDFLARE_ENV=demo nohup npm run build:public > log 2>&1 &`
   (check `ps` first: one build owner at a time).
2. `rclone copy build/dist r2:classical-philosophy-reader-data --checksum --header-upload "Cache-Control: public, max-age=3600" --transfers 16`
   (`copy`, not `sync`: nothing is deleted).
3. From `app/`: `CLOUDFLARE_ACCOUNT_ID=6ff75c6d6c06d1092df2c7efd42077ba npx wrangler@latest deploy`.
   Wrangler should report about 4,300 files; a much larger count means `app/dist`
   is not the demo build. The account id is required since 2026-09-21: the
   wrangler login now also sees Brian's account (`Lyceum Institute`,
   `570b13129baea40d581ac89859a9c8aa`), and `app/wrangler.jsonc` names no account,
   so every wrangler command must say which one it means. **Brian's account holds
   a Worker named `lyceum-library`; never run a deploy against his account id
   without John's go.**

**Update 2026-09-21 (test copy in Brian's account, John's go and Brian's the same day):**
the Worker `lyceum-library-staging` runs in the Lyceum Institute account
(`570b13129baea40d581ac89859a9c8aa`) at
`https://lyceum-library-staging.lyceum-institute.workers.dev`, set up by the
`staging` section of `app/wrangler.jsonc`, with its own catalog store
`lyceum-library-staging-catalog` (`d3944cf9…`; the live store `lyceum-library-catalog`
is never bound). `lyceum.institute`'s DNS is at WordPress.com, so there is no custom
domain. This recipe reads the texts from John's bucket, off-origin — the bucket
in Brian's account came online 2026-09-22 (see the update below). Redeploy:

1. `PUBLIC_DATA_ROOT=https://pub-4ed50262412e44deb78c78b952f07f03.r2.dev PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 PUBLIC_PARTNER_ORIGIN=https://library.lyceum.institute CLOUDFLARE_ENV=staging nohup npm run build:public > log 2>&1 &`
2. Check `app/dist/server/wrangler.json` names `lyceum-library-staging` and Brian's account id.
3. `rclone copy build/dist r2:classical-philosophy-reader-data --checksum …` as above.
4. From `app/`: `npx wrangler@latest deploy`. **The app's permission check blocks this
   from an agent session as a production deploy; John runs it.** wrangler ≥4.136 reports
   "Read 8805 files": it counts folders too (4,290 files + 4,516 folders); the upload
   line says 4,288 assets. The upload's last 250 files took about 25 minutes.
5. Brian sets the secret `LYCEUM_PUBLISH_TOKEN` on the Worker himself.

Bucket CORS gained `https://lyceum-library-staging.lyceum-institute.workers.dev`
(2026-09-21). Earlier, it gained `https://lyceum-reader-demo.johnhboyer.workers.dev`. The
Pages demo `lyceum-reader-demo.pages.dev` was retired the same day (John): the Pages
project is deleted and its address is off the bucket CORS list.

**Update 2026-09-22 (staging now serves texts from its own bucket):** the
recipe above still works and still runs John's demo Worker, in his own
account — keep it for that. For the Lyceum staging Worker, the recipe is now
this instead:

1. Publish the release: `node scripts/publish-release.mjs --remote lyceum --bucket lyceum-library-data`
   from the repo root. **John runs the real upload; agent sessions are blocked
   from it** — a dry run is fine.
2. Build: `DATA_FROM_BUCKET=1 CLOUDFLARE_ENV=staging PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 PUBLIC_PARTNER_ORIGIN=https://library.lyceum.institute npm run build:public -- --from-dist build/dist`
   (about two minutes, in place; `--from-dist` keeps the build's version
   matching what is already in the bucket).
3. Check `app/dist/server/wrangler.json` names `lyceum-library-staging`,
   Brian's account, and an `r2_buckets` entry binding `CORPUS` to
   `lyceum-library-data`.
4. From `app/`: `npx wrangler@latest deploy` (about 512 changed assets, about
   a minute). **John runs this.**
5. Verify: a GET on a data path returns 200 with
   `Cache-Control: public, max-age=31536000, immutable` and an etag; the same
   request with `If-None-Match` returns 304; an unknown version returns 404.
   A `..` that stays inside the release (e.g. `/data/<v>/../<v>/RELEASE.json`)
   is resolved by Cloudflare's edge before the Worker sees it and returns the
   same file with the same etag (seen 2026-09-23); one that tries to leave
   `/data/<v>/` returns 404.

One known gap: a bucket-mode rebuild changes only `manifests/index.json` (its
data-root and URL fields), so `publish-release.mjs --dry-run` afterward flags
that one file — expected, and what address it should carry is still open.

**Update 2026-09-21 (bucket mode: the Worker can serve data itself, added but
not yet wired up):** a second way to serve corpus data, alongside the
off-origin `PUBLIC_DATA_ROOT` setup above. Instead of the browser fetching
data straight from R2, the deployed Worker fetches it and serves it itself,
at the same address as the rest of the site, under a versioned path:
`/data/<version>/...`. The reader's own code needed no change for this
beyond the build itself pointing at that path — `shared/lib/data.ts` and
`shared/lib/search.ts` already build every corpus-data URL as a plain string
join off whatever root they are given.

To build in this mode, set `DATA_FROM_BUCKET=1` instead of `PUBLIC_DATA_ROOT`.
The two must never both be set — the build stops with an error if they are.
`DATA_FROM_BUCKET` is parsed strictly: only the exact string `1` turns it on;
any other non-empty value is also an error (a stray `true` or `0` is a
caller mistake, not a silent no-op); empty or unset is off. Setting it does
not need a version supplied by hand — the build works out its own release
version (the build version below, or whatever a `--from-dist` release
already carries) and, from that, sets `PUBLIC_DATA_ROOT` to `/data/<version>`
itself, before building the Astro app and before running the post-build
steps that read that variable. From there it is a completely ordinary
`PUBLIC_DATA_ROOT` build: the same code paths that prune `dist/client/data`,
bake the root into the client bundle, template it into the service worker,
and verify the shipped artifact all run exactly as they do for an
off-origin build — nothing in any of them needed to change for this mode,
because the only difference is what string the root holds (a same-origin
path here, instead of an off-origin URL).

**One stamp, not two (fixed 2026-09-22):** the text pipeline stamps each
work's own `manifest.json` with a plain commit-and-date string
(`<short commit>-YYYY-MM-DD`) — that string is a producer id, never the
release's public identity. `scripts/emit-lyceum-manifest.mjs` reformats it
once into the build version `docs/lyceum-shared-repo-plan.md` §6 names
(`YYYY.MM.DD-<short commit>`), and that reformatted string is what
`manifests/index.json`, `RELEASE.json`, and the `releases/<version>/` bucket
folder all end up carrying. A full build derives `/data/<version>` from that
same reformatted string — computed the same way, before the pipeline even
runs — never from the raw commit-and-date form, so the two can no longer
drift apart the way they did on 2026-09-22 (the deployed site asking for one
version's path while the bucket only held a release folder under the other,
404ing every text). `scripts/verify-pages-artifact.mjs` checks this on every
bucket-mode build: it re-reads `RELEASE.json`'s `corpus_version` on its own
and fails the build if the root baked into `sw.js` names a different
version.

The route itself is `app/src/pages/data/[...path].ts`. A request for
`/data/<version>/<path>` reads the R2 bucket bound to the Worker under the
name `CORPUS`, at the object key `releases/<version>/<path>` — the version
comes from the request's own URL, not from anything baked into the Worker at
build time, so **nothing about a deploy needs to change to add a new
release**: a redeploy just starts writing pages that link to a new version's
path, and the Worker can still answer requests for every older version still
sitting in the bucket. Every successful response carries
`Cache-Control: public, max-age=31536000, immutable`, and a conditional
request (`If-None-Match`, including a list, a weak validator, or `*`) gets a
matching 304 with the same headers — this is safe only under a rule, not a
technical guarantee: **a release folder, once uploaded, is never
overwritten.** The version string alone (a short commit hash plus the date)
does not guarantee unique contents — a rebuild on the same commit and day, a
dirty working tree, a changed mounted corpus, or a `--from-dist` rebuild of
derived files can each produce different data under one version — so the
invariant is enforced at **publication**, not by the version string:
`scripts/publish-release.mjs` refuses a folder with changed or extra remote
objects, does nothing when the folder is identical, and resumes by adding
only local files missing from the remote folder. Run
`node scripts/publish-release.mjs --bucket lyceum-library-data --dry-run` to
check a release before publishing it. **John ruled (2026-09-22): keep the
two most recent release folders; older ones may be deleted by hand** — a
page refresh always asks for the new folder, so only a tab left open or the
site's offline copy in the browser can still ask for the previous one, and
that folder stays. The publish script itself never deletes anything; this
replaces the earlier "never delete" wording. A bucket for this mode needs the same
`build/dist` tree pushed under a `releases/<version>/` folder, rather than
at the bucket's root the way the existing `rclone` recipe above pushes it —
one folder per version, side by side, never overwritten.

The version in the URL is restricted to a single path segment matching
`^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (letters, digits, `.`, `_`, `-`, starting
with a letter or digit, up to 64 characters) — anything else in that
position, including `.` or `..`, is a 400, not a lookup. The build itself
checks its own computed `CORPUS_VERSION` against this same rule before doing
any real work — including in `--from-dist` mode, where the version is read
from the release being copied FROM and validated before that copy (or any
deletion of the existing `build/dist`) happens, not after.

**The `CORPUS` binding has been in `env.staging` of `app/wrangler.jsonc` since
commit 29015b4.** The Lyceum staging test copy has served texts from the
bucket this way since 2026-09-22. John's demo Worker, in his own account,
still uses the `r2.dev` root, not bucket mode.

## 1. Architecture recap

The **app** (this Astro site) deploys to a Cloudflare Worker with static assets
at a domain root (ruling, John, 2026-09-15 — superseding Cloudflare Pages;
`@astrojs/cloudflare` 14.x no longer emits a Pages Advanced Mode artifact, see
`app/wrangler.jsonc`). **Corpus data** (the JSON the reader
fetches per work/book) lives in a Cloudflare R2 bucket, served through a custom
"data domain." The app never hardcodes that domain: every data fetch goes through
the `ROOT()` helper in `shared/lib/data.ts:192-194`, which reads
`globalThis.__READER_DATA_ROOT__` (falling back to same-origin `${BASE_URL}/data`
when unset) — see `shared/lib/search.ts:14-19` for the same pattern applied to
search shards. Pointing the site at R2 instead of same-origin `/data` is meant to
be a config change, not a rebuild, per the plan (§5: "the data-root is config").
The public app URL will eventually be one CNAME (`reader.lyceum.institute` or
similar) added to the Lyceum's existing DNS, pointed at the deployed Worker. The
R2 data domain has to live on a domain **John controls directly in Cloudflare**
(R2 custom domains require a Cloudflare-managed zone), registered at cost — this
domain is invisible to users since it's only ever a background fetch address.

**Build-time switch (implemented, WP7)**: `shared/lib/data.ts` and
`shared/lib/search.ts` each compute their `DEFAULT_ROOT` from a `PUBLIC_DATA_ROOT`
build-time env var (a Vite static replacement — the same mechanism as
`PUBLIC_SITE_ORIGIN`, no inline script needed) when it's set, falling back to
same-origin `${BASE_URL}/data` when it isn't. `globalThis.__READER_DATA_ROOT__` —
still exercised today only by the desktop app (Tauri) — is read lazily at
fetch time and wins over both, so a Tauri window can still override at runtime.
Covered by `shared/__tests__/data.test.ts`/`search.test.ts`'s
"PUBLIC_DATA_ROOT build-time root override" suites. §3 documents the deploy-time
recipe for flipping this switch.

## 2. John's dashboard checklist

Do these once, in order. Deploys themselves stay John-gated per CLAUDE.md — none
of this authorizes an agent to actually deploy.

**Tooling note (2026-08-14):** the official Cloudflare plugin is installed
(`claude plugin install cloudflare@cloudflare`, per
`https://developers.cloudflare.com/agent-setup/prompt.md`) — 13 skills plus five
MCP servers (`cloudflare-api`, `-docs`, `-bindings`, `-builds`,
`-observability`). Once John has restarted Claude and completed the OAuth flow,
steps 4, 6 and 7 are doable through `cloudflare-api` rather than by hand in the
dashboard. Steps 1, 2 and 8 stay manual: they are the money gate, the domain
purchase, and a credential-issuing step no agent should drive.

1. **Cloudflare account.** Sign up / log in if not already done. *(Done — account
   exists as of 2026-08-14; nothing else in this list is built yet.)*

   **Cost gate before enabling R2:** activating R2 requires a payment method on
   file even for free-tier-only use — Cloudflare preauthorizes the card against
   usage-based billing. Our footprint bills $0 (§5), but per CLAUDE.md's hard rule
   the card requirement itself is John's to clear, not an agent's to walk past.

2. **Register the data domain** — a domain John controls in Cloudflare, ~$10/yr
   (at-cost registration). Needed because R2 custom domains require a
   Cloudflare-managed DNS zone; this domain is never user-facing.

   **Deferred (John, 2026-08-14): prove the path out on the free `r2.dev` URL
   first (step 5), buy the domain only at launch.** The staging pass exists to
   close §3's outstanding [verify] — a real cross-origin fetch — before spending
   anything.

   **Resolved 2026-08-14: a bucket CORS policy DOES apply to `r2.dev`.** Cloudflare
   documents CORS response headers for *custom domains* and says nothing about the
   dev URL, so this was a live risk to the whole staging plan. Measured against the
   real bucket: a request carrying `Origin: http://localhost:4321` comes back with
   `Access-Control-Allow-Origin: http://localhost:4321`, and a disallowed origin
   gets a 200 with **no** ACAO header — correct behaviour, since a simple GET has
   no preflight, so R2 serves the bytes and withholds the header, leaving the
   browser to refuse to expose the response. Nothing about the domain purchase is
   urgent on CORS grounds.
3. **Create the Worker** (`app/wrangler.jsonc`), either connecting this GitHub
   repo (Workers Builds, auto-builds on push) or via direct-upload CLI
   (`wrangler deploy`). Either way, the actual deploy trigger stays
   manual/John-gated — CI auto-deploy-on-push would violate "deploying is
   John's call," so if Workers Builds is used, its auto-deploy should be
   disabled or restricted to a preview-only branch. [verify] confirm Cloudflare
   Workers Builds' current settings support "build previews but never
   auto-publish to production."
4. **Create the R2 bucket** for corpus data. **Named `classical-philosophy-reader-data`
   (John, 2026-08-14).** The ruling is a convention, not a one-off: **one bucket per
   reader site, named after its repo** — `aristotle-reader-data`,
   `plato-reader-data`, `roman-reader-data` as those follow. Bucket names are never
   user-visible (the custom domain is the public face), so clarity beats brevity.

   Why per-site rather than one shared bucket with per-site prefixes:

   - **`rclone sync` deletes destination files absent from the source.** One
     forgotten prefix against a shared bucket's root wipes a sibling site's data.
     Separate buckets remove the foot-gun; they also let each API token be scoped
     to one bucket, so a leaked key cannot reach the others.
   - **Sharing would dedupe nothing today.** Each repo ships its own LSJ shards
     (measured 2026-08-14: 51 MB here, 48 MB aristotle-reader, 45 MB
     plato-reader) and they differ byte-for-byte — `lsj/a.json` is 7.6 MB here
     against 6.9 MB in aristotle-reader — because each shard set is the union of
     *that* corpus's lemmas (see `shared/lib/data.ts`'s `fetchLsjShard` note).
     Real dedup would mean building one full-LSJ shard set in the pipeline; that
     is separate work, and a bucket layout cannot substitute for it.
   - **Cost is identical either way** — the 10 GB free tier is per *account*, not
     per bucket. All three built corpora together are ~944 MB (377 + 316 + 251),
     about 9.4% of the tier.

   Custom domains work either way: one bucket each means one subdomain each
   (`data-classical.…`, `data-plato.…`), all free inside the single registered
   zone (step 2).
5. **Give the bucket a public origin.** Two paths, and we are on the first:

   *Staging (current).* Bucket → Settings → Public Development URL → Enable,
   confirming with "allow". Yields a free `https://pub-<hash>.r2.dev` origin, no
   domain required. Rate-limited and **staging only** — Cloudflare says
   explicitly it "should only be used for development purposes," and warns
   against CNAMEing to it (unsupported access path). This is the §4
   staging-discipline rule in force: never announce an `r2.dev` URL, never set
   `PUBLIC_SITE_ORIGIN` alongside it.

   *Launch (later).* **Attach the data domain to the bucket** as an R2 custom
   domain, making it reachable at e.g. `data.<johns-domain>.com` instead. Blocked
   on step 2's deferred registration.
6. **Set CORS rules on the bucket** so the app origin(s) can fetch it
   cross-origin. **Gotcha: the two tools want different JSON shapes.** The
   dashboard takes the S3-style array; `wrangler` rejects it outright ("must
   contain a 'rules' array as expected by the R2 API"). Applied via wrangler
   2026-08-14 and read back with `wrangler r2 bucket cors list`:

   ```json
   {
     "rules": [
       {
         "id": "reader-app-origins",
         "allowed": {
           "origins": [
             "http://localhost:4321",
             "https://lyceum-reader-demo.johnhboyer.workers.dev"
           ],
           "methods": ["GET"],
           "headers": ["*"]
         },
         "maxAgeSeconds": 3600
       }
     ]
   }
   ```

   ```sh
   npx -y wrangler@latest r2 bucket cors set classical-philosophy-reader-data \
     --file cors.json -y
   ```

   `http://localhost:4321` is the Astro dev/preview origin, needed for the §3
   verification pass. The `workers.dev` origin is the demo Worker; the rules
   shown are the bucket's as of 2026-09-16, when the retired Pages demo and
   the unused `classical-philosophy-reader.pages.dev` placeholder came off
   (John). Add the real reader subdomain (§4) once picked, and drop localhost
   when going public.
7. **Cache-control.** Corpus data paths are **stable, not content-addressed** —
   `build/dist/<work>/book-01.json`, `analyses.json`, `lsj/a.json` and the rest
   keep their names across pipeline runs, so a rebuild changes an object's
   *content* at the *same* path (verified 2026-08-14: no hashed filename anywhere
   under `build/dist`). An earlier draft of this step claimed the opposite and
   recommended `max-age=31536000, immutable` on that basis; that would pin every
   reader to stale corpus text for a year with no way to bust it. **Default to a
   modest TTL** — `Cache-Control: public, max-age=3600` — which is cheap here
   because R2 egress is free.

   To get immutable caching properly, version the *root* rather than the object:
   sync each build to its own prefix (`r2:<bucket>/v/<build-id>/`) and point
   `PUBLIC_DATA_ROOT` at that prefix, so a new build is a new URL space and the
   old one stays cacheable forever. The data-root is already a build-time config
   knob (§3), so this costs no code — only storage, ~377 MB per retained version
   against the 10 GB free tier. **John's call**, since it changes the deploy
   recipe; not adopted yet.

   Set the header **per-object at upload time** (rclone `--header-upload`, or
   wrangler's `--cache-control` for a single object). A zone-level Cache Rule is
   the other route, but it needs a real Cloudflare zone and so is unavailable on
   the `r2.dev` staging path (§4) — there, per-object is the only option.
   Verified 2026-08-14 against the live bucket: an object uploaded with
   `--cache-control "public, max-age=3600"` serves exactly that
   `Cache-Control` header back over the `r2.dev` URL.
8. **Create an R2 API token** scoped to just this bucket, for rclone to use as
   S3-compatible credentials. R2 tokens are **not** the same thing as the general
   Cloudflare API tokens under My Profile, and they are not reachable from the
   sidebar: go to **R2 Object Storage → Overview**, then in the **Account Details**
   panel select **Manage** next to **API Tokens**
   (`https://dash.cloudflare.com/<account-id>/r2/overview`). Choose **Create
   Account API token** (a User token dies with the user), permission **Object Read
   and Write**, scoped to `classical-philosophy-reader-data`.

   The confirmation screen shows the **Access Key ID** and **Secret Access Key** —
   sometimes labelled Client ID and Client Secret. Those two, not the "Token
   value" above them, are what an S3 client wants. The Secret is shown **once**;
   a lost one cannot be recovered, only replaced by a new token. Store both
   outside the repo (never committed — see §3).
9. **(Launch time, later) Request the Lyceum CNAME** — `reader.lyceum.institute`
   (or whatever subdomain is chosen) pointed at the deployed Worker's
   `workers.dev` hostname. Five-minute, zero-risk ask per the plan; do this
   only when John is ready to go public, not during Wave 1 development.

## 3. Data deploy recipe

Corpus data is pushed to R2 with `rclone`, treating R2 as an S3-compatible remote.

**rclone remote config** (`rclone config` interactively, or drop into
`~/.config/rclone/rclone.conf` — never commit this file):

```ini
[r2]
type = s3
provider = Cloudflare
access_key_id = <from the R2 API token, §2 step 8 — set via env, not pasted here>
secret_access_key = <same>
endpoint = https://<account-id>.r2.cloudflarestorage.com
acl = private
region = auto
no_check_bucket = true
```

A token for one bucket cannot list buckets or check that the bucket exists. A remote that uses one needs `no_check_bucket = true` and `region = auto`, as shown above. Otherwise `rclone lsd <remote>:` gets `AccessDenied` for `ListBuckets`, and the first upload gets `AccessDenied` for `CreateBucket`. Test an empty bucket with `rclone lsd <remote>:<bucket>`; it should print nothing and return no error.

Credentials should come from environment variables
(`RCLONE_CONFIG_R2_ACCESS_KEY_ID` / `RCLONE_CONFIG_R2_SECRET_ACCESS_KEY`) or a
local, gitignored conf file — never hardcoded into a script that gets committed.
**John fills the two secret values in himself**, in his own editor: agents do not
handle R2 keys, and nobody pastes them into a chat transcript. An agent can write
the conf skeleton with placeholders and can then run `rclone` against the named
remote without ever seeing the secrets.

**Sync** (incremental — only changed shards re-upload):

```sh
rclone sync build/dist r2:<bucket-name> --checksum
```

Run from the repo root after `npm run build:public` (or the pipeline step that
populates `build/dist`) has produced current output. `--checksum` compares
content hashes rather than mtimes, which matters because the pipeline can
regenerate a file with identical content but a new mtime.

Add the §2-step-7 cache header at upload time (the only option on the `r2.dev`
staging path, which has no zone and so no Cache Rules):

```sh
rclone sync build/dist r2:<bucket-name> --checksum \
  --header-upload "Cache-Control: public, max-age=3600"
```

**Current size (2026-08-14): 377 MB across 13,482 objects, 69 works.** The first
sync is therefore ~13.5k Class A writes against a 1,000,000/month free allowance,
and 3.7% of the 10 GB storage tier — both comfortably free (§5). Later syncs only
push changed objects. This is also the standing argument for R2 over bundling
data into the Worker deploy: the app itself is only 397 files, but app + data is
13,879 against the Worker free plan's 20,000-file cap, and every added work
costs roughly 200 more — the cap would be hit partway through the canon.

**Verified end-to-end 2026-08-14.** The corpus is on R2: `rclone check --checksum`
reports 13,482 matching files and **0 differences** against `build/dist`, 350 MiB.
A real browser at `http://localhost:4321`, served a copy of `app/dist` with
`data/` removed and `globalThis.__READER_DATA_ROOT__` set to the bucket, fetched
every data class cross-origin — `manifest.json`, `book-01.json`, `analyses.json`,
`lemmata-lat.json`, and a 6.25 MB `ls/a.json` shard — all 200, all carrying
`Cache-Control: public, max-age=3600`. Clicking the word *Quamquam* in De
Officiis I drove the app's own path (`lookupWord` → `fetchAnalyses` →
`fetchLsjShard`), which pulled `/ls/q.json` — the right shard — and rendered the
Lewis & Short entry in the popup.

What that does *not* cover: the harness exercised the **runtime** override, so
what is proven is the shared fetch path (`dataRoot()`), CORS, and the completeness
of the uploaded data.

The **build-time** `PUBLIC_DATA_ROOT` replacement has since been run (2026-08-14,
a zero-works `npm run build` in `app/` with the bucket's `r2.dev` host set). Both
replacements bake in: the host appears in the emitted `dist/_astro/data.*.js` and
`search.*.js` chunks (Vite), and `dist/sw.js` differs from `public/sw.js` in
exactly one line — its `DATA_ROOT` literal (§3a). Still unproven at corpus scale:
that was a works-free build, so `build:public` with the var set has not run.

**Pointing the app at it**: `PUBLIC_DATA_ROOT` (parallel to `PUBLIC_SITE_ORIGIN`,
`app/astro.config.mjs`) is read directly into `shared/lib/data.ts`/`search.ts`'s
`DEFAULT_ROOT` at build time — no inline script or runtime wiring needed (§1).
Unset, the build falls back to `DEFAULT_ROOT` = `${BASE_URL}/data` — same-origin,
expecting `/data` inside the deployed Worker's static assets itself. Flipping the
switch means: build with `PUBLIC_DATA_ROOT=https://<data-domain>` set (a
trailing slash is stripped automatically) and confirm CORS (§2 step 6) allows
the deployed app's origin. [verify] this against a real Worker + R2 deploy once
both exist — the env wiring itself is unit-tested, but an actual cross-origin
fetch against R2 is not.

## 3a. The service worker follows the data root off-origin

**Found 2026-08-14, fixed the same day.** What was wrong: `app/public/sw.js`
routed by origin —

```js
if (url.origin === location.origin) { /* _astro: cacheFirst; else networkFirst */ }
return;   // cross-origin falls through, uncached
```

— with only `fonts.googleapis.com` / `fonts.gstatic.com` handled cross-origin.
Point `PUBLIC_DATA_ROOT` at R2 and every corpus fetch becomes cross-origin, so
the service worker stopped caching it — silently. Nothing failed at build time,
and the site looked perfect online.

Scope of the regression, precisely: book text is server-rendered into the page
HTML, which the worker still caches as a navigation, so **reading an
already-visited page offline kept working**. What broke offline was everything
that fetches from the data root — word lookup (`analyses.json` + the LSJ/L&S
shards), the search index (`shared/lib/search.ts` uses the same override),
footnotes, sidenotes, figures and lemma pages. The worker's own header comment
promises "anything you have read is available offline"; after the flip that
promise would have been false for all of it.

**How the worker learns the data origin (John's ruling, 2026-08-14): template it
at build time.** The worker is a static file served from `public/`, so it cannot
read `import.meta.env`. The alternative — the app handing the origin over by
`postMessage` at registration — loses to service-worker lifetime: the browser
kills an idle worker and restarts it on the next fetch, with the variable empty
and no client having messaged it yet, so the origin would have to be persisted
and read back asynchronously, which a `fetch` handler cannot do before deciding
synchronously whether to call `respondWith()`. Templating also changes the
worker's bytes when the root changes, which is itself the browser's update
signal.

Shape of the fix:

- `app/public/sw.js` declares `const DATA_ROOT = '';` (empty = same-origin data,
  the existing scope branch) and matches requests against it by origin *and*
  path prefix, so a data root with a path claims only its own subtree.
- Matched requests get `networkFirst` — the same policy same-origin `/data/`
  already had, for the same schema-drift reason. Never cache-first. These
  cross-origin responses are CORS-enabled, not opaque, so they cache and read
  back normally.
- `app/scripts/postbuild-sw.mjs` (wired into `app/package.json`'s `build`, after
  `postbuild-robots.mjs`) substitutes `PUBLIC_DATA_ROOT` into `dist/sw.js`. No
  env var → no-op. Env var set but the placeholder missing, the file absent, or
  the value unparseable → **the build fails**, since a silent miss is exactly
  the failure this step exists to prevent.
- `app/src/__tests__/sw.test.ts` runs that real build step over the real
  `public/sw.js` and executes the emitted worker against stubbed
  caches/`fetch`: data-root requests cache online and serve offline, the fetch
  count proves network-first rather than cache-first, a data root with a path
  does not claim its whole bucket origin, same-origin behaviour is unchanged,
  and placeholder drift fails the build.

## 4. Staging discipline

`*.pages.dev` and R2 dev URLs (e.g. `pub-xxxx.r2.dev`) are **staging only**. The
build already enforces one half of this: `app/astro.config.mjs` only sets
`site` (and only includes the `@astrojs/sitemap` integration) when
`PUBLIC_SITE_ORIGIN` is set at build time, and `app/scripts/postbuild-robots.mjs`
only appends a `Sitemap:` line to `robots.txt` under the same condition — both
currently live in a worktree, not yet merged to `main` (a parallel work package),
but this is the intended, already-implemented contract: no `PUBLIC_SITE_ORIGIN` →
no sitemap, no canonical URLs baked in. Do not register Google Search Console, do
not announce a `*.pages.dev` URL as canonical, and do not set `PUBLIC_SITE_ORIGIN`
in any build until the real domain (§2 step 9) is attached.

## 5. Cost guardrails

- **R2**: free tier is 10 GB storage + free egress (no egress fees, unlike S3).
  Beyond 10 GB, storage is $0.015/GB-month (e.g. a 20 GB corpus ≈ $0.15/month).
- **Worker (free plan)**: static asset requests are free; Worker requests are
  capped at 100,000/day and a deployed version at 20,000 files (§3 above) —
  this project fits comfortably within both.
- **Domain registration**: ~$10/yr, at-cost, one-time-per-year (§2 step 2).
- Hard rule (CLAUDE.md): anything that would incur cost gets surfaced to John
  **before** doing it — this includes crossing the R2 10 GB threshold, not just
  new purchases.
