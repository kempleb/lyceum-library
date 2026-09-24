# Lyceum Library
> DRAFT — awaiting John Boyer's approval.

The Lyceum Library shows Greek and Latin philosophical texts beside English
translations. Readers can look up words, search the texts, and follow citations.
Astro builds the site in `app/`. A shared TypeScript and Svelte library lives
in `shared/`. Python prepares text data in `pipeline/`. The site runs as a
Cloudflare Worker with static assets. An R2 bucket serves the texts.

## Folders

- `app/` — Astro pages, Worker routes, public assets, and app tests.
- `shared/` — reader components, styles, data helpers, and tests.
- `pipeline/` — Python text tools, tests, and package settings.
- `scripts/` — build, release, check, and catalog scripts.
- `manifests/` — YAML work and author records used to generate the site list.
- `corpora/` — Aristotle and Plato mount settings.
- `schemas/` — JSON rules for manifests, routes, and catalog files.
- `fixtures/` — sample data and files used by checks.
- `sources/` — source notes and English translation files.
- `docs/` — plans, build notes, release steps, and check guides.

## Data kept out of git

Greek source text comes from the TLG; Latin source text comes from the PHI.
Both are licensed. Never commit that source text. Git also ignores generated
build output in build/; app/public/data points to that output. A fresh
checkout has no built texts.

## Build the site

Use Node 22 (`nvm use 22`). The release build also needs the Python tools
described in `docs/release-from-dist.md`.

From licensed source text on John's machine, run from the repo root:

```sh
npm run build:public
```

Anyone can build from a published data release without the licensed source.
Read `docs/release-from-dist.md` and `scripts/fetch-release.mjs` first. From
the repo root, use a published version in place of `<version>`:

```sh
node scripts/fetch-release.mjs <version> build/dist --from-url https://lyceum-library-staging.lyceum-institute.workers.dev/data
npm run build:public -- --from-dist build/dist
```

The fetch checks each downloaded file against the release record. For a fresh
checkout, the release guide also calls for `npm ci` in `app/` and `shared/`,
and `uv sync` in `pipeline/`.

## Test and check

Use Node 22 (`nvm use 22`) before the Node commands. Run these from the
named folder:

```sh
cd shared && npx vitest run
cd ../app && npx vitest run
cd ../pipeline && uv run --with pytest pytest
cd ../app && npm run build
```

The last command must build with no texts present. CI also builds with the
sample text, then checks links and the sample pages. From the repo root:

```sh
rm -rf app/dist build/dist
cd app && PUBLIC_READER_FIXTURES=1 PUBLIC_SITE_ORIGIN=https://ci-staging.example/ npm run build
cd .. && node scripts/check-links.mjs app/dist/client
node scripts/verify-fixture-build.mjs app/dist/client
```

See `.github/workflows/ci.yml` for the other CI checks.

## Release and deploy

A data release lives in a versioned folder in the bucket. Its contents do
not change after publication. `scripts/publish-release.mjs` refuses to replace
a version whose files differ. John runs the upload and the deploy. The current
staging steps are in `docs/cloudflare-setup.md`, “Update 2026-09-22”:

1. John checks the upload with `node scripts/publish-release.mjs --remote lyceum --bucket lyceum-library-data --dry-run`, then publishes with the same command without `--dry-run`.
2. Build from that release with `DATA_FROM_BUCKET=1 CLOUDFLARE_ENV=staging PUBLIC_LYCEUM_CHROME=1 PUBLIC_LYCEUM_DRAFTS=1 PUBLIC_PARTNER_ORIGIN=https://library.lyceum.institute npm run build:public -- --from-dist build/dist`.
3. Check the generated Worker settings for the staging name, account, and `CORPUS` R2 binding.
4. John runs `npx wrangler@latest deploy` from `app/`, then checks a known text, a repeat request, and an unknown version.

The test copy is https://lyceum-library-staging.lyceum-institute.workers.dev.
It serves texts at /data/{version}/{path}. The catalog publish route is
/api/catalog/publish. It needs a token named `LYCEUM_PUBLISH_TOKEN`.

## Acceptance check

`scripts/acceptance.mjs` checks a running site's text records, pages, word
lookups, search, citations, and publish safeguards; see
`docs/acceptance-script.md`. Run it against a site address like this:

```sh
node scripts/acceptance.mjs --origin https://lyceum-library-staging.lyceum-institute.workers.dev --data-origin https://lyceum-library-staging.lyceum-institute.workers.dev
```

## Rules and decisions

- `CANON.md` says what belongs in the collection and why.
- `AGENTS.md` gives coding assistants the repo rules.
