# Address test: a Pages front that forwards to the test copy

This is a test. It answers one question: can a Cloudflare Pages project keep
its public address while its content becomes "send every request to a
different Worker"? The partner's live site is a Pages project with a custom
domain. If this works, the new site could take over that address without the
partner moving DNS.

It runs in the Lyceum Institute Cloudflare account (id
`570b13129baea40d581ac89859a9c8aa`), in front of the test copy
(`lyceum-library-staging`): John's choice, 30 September, because that is the
arrangement a real takeover would use. It creates one new Pages project,
`lyceum-proxy-test`, at `https://lyceum-proxy-test.pages.dev`. It changes
nothing on the test copy, on Brian's live `lyceum-library` project, or in any
setting; it only calls the test copy. Delete it when the checks are done.

What is here:

- `public/_worker.js` — the whole front, about 15 lines. It passes each
  request (method, path, query, headers, body) to the test copy and returns
  the answer unchanged. Redirects go to the browser, not followed.
- `wrangler.jsonc` — project name, the `public` folder, and the `LIBRARY`
  link to `lyceum-library-staging`.
- `_worker.test.mjs` — five tests with a fake `LIBRARY`. Run
  `nvm use 22 && node --test _worker.test.mjs`.
- `../../docs/address-takeover-test.md` — the results sheet to fill in.

## Deploy (you run this; agent sessions cannot)

From this folder, logged in to your account (`npx wrangler login` first if
needed):

```sh
cd tools/address-proxy
CLOUDFLARE_ACCOUNT_ID=570b13129baea40d581ac89859a9c8aa ../../app/node_modules/.bin/wrangler pages deploy --project-name lyceum-proxy-test
```

Wrangler does not accept `account_id` in a Pages configuration file, so the
account is given on the command line.

`pages_build_output_dir` in `wrangler.jsonc` tells Wrangler to upload
`./public`. The docs say the first deploy of a new name prompts you to create
the project and choose a production branch (answer `main`). If Wrangler
instead says the project does not exist, create it first:

```sh
npx wrangler pages project create lyceum-proxy-test --production-branch main
```

then run the deploy again. If Wrangler complains about `account_id`, see the
comment in `wrangler.jsonc`.

Then work through the table in `docs/address-takeover-test.md`.

## Delete afterwards

```sh
npx wrangler pages project delete lyceum-proxy-test
```

Or in the dashboard: Workers & Pages, open `lyceum-proxy-test`, Settings,
Delete project. The test copy stays as it was.

## What the Cloudflare docs say

Checked 2026-09-30 in Cloudflare's current docs. Page titles and addresses
follow.

- **(a) `_worker.js` placement and shape.** "Advanced mode" page
  (developers.cloudflare.com/pages/functions/advanced-mode/): put `_worker.js`
  in the project's build output directory (here `public/`). It is a module
  Worker with `export default { async fetch(request, env) { … } }`. With
  advanced mode the `/functions` folder is ignored. CONFIRMED.
- **(b) Service binding in a Pages config file.** "Configuration" page under
  Pages Functions (…/pages/functions/wrangler-configuration/): a Wrangler file
  with `pages_build_output_dir` is supported, and `services` is listed as a
  non-inheritable key. The "Bindings" page (…/pages/functions/bindings/) says
  the binding can be set in the Wrangler file or in the dashboard (Settings,
  Bindings, Add, Service binding, then redeploy). When the file is used it is
  the source of truth and its fields cannot be edited in the dashboard.
  CONFIRMED. `account_id` in that file: NOT LISTED on the Pages configuration
  page. UNVERIFIED.
- **(c) Deploy command and first deploy.** "Wrangler commands" page for Pages
  (…/workers/wrangler/commands/pages/): `npx wrangler pages deploy
  [DIRECTORY]` with `--project-name` and `--branch`. The "Direct Upload" page
  (…/pages/get-started/direct-upload/) says the project is created with
  `wrangler pages project create` (prompts for name and production branch),
  and that running the deploy command first also creates it with the same
  prompts. The exact prompt text is UNVERIFIED. Whether `name` in the config
  file is used as the project name is not stated, so the command above passes
  `--project-name`.
- **(d) Function invocations and the free limit.** "Pricing" page under Pages
  Functions (…/pages/functions/pricing/): Function requests bill as Workers
  requests; on the Free plan the daily limit is 100,000, shared with Workers
  requests, resetting at midnight UTC. Static asset requests are free and
  unlimited, but a request counts as static only when it does not invoke a
  Function. In advanced mode `_worker.js` handles every request, so each
  proxied request is one invocation. The "Routing" page (…/pages/functions/
  routing/) says `_routes.json` can exclude paths from Functions, but this
  test does not use one. CONFIRMED. The "Pricing" page for Workers
  (…/workers/platform/pricing/) says a call through a service binding adds no
  request fee: it bills one request (the front) plus CPU time of both. It
  words this for the Standard (paid) model; the Free-plan wording is
  UNVERIFIED, so treat the origin call as possibly counting too.
- **(e) `env.ASSETS`.** Advanced mode page: `env.ASSETS.fetch()` exists as a
  default binding and is how a `_worker.js` serves the project's static files.
  This front serves none (`public/` holds only `_worker.js`, which Pages does
  not serve as a file), so it does not use it. CONFIRMED.

The advanced-mode, Pages commands, Direct Upload and configuration pages were
read through a page summariser, not the raw text. One summary gave the wrong
delete command; the Workers "Migrate from Pages" page gives
`npx wrangler pages project delete`, used above.
