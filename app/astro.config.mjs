// @ts-check
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import { cacheCloudflare } from '@astrojs/cloudflare/cache';
import svelte from '@astrojs/svelte';

import sitemap from '@astrojs/sitemap';

// Deploys at the domain root (Cloudflare Pages) — no `base`. No real domain
// is registered yet, so `site` (the canonical origin, needed for
// @astrojs/sitemap's absolute URLs and for pages' Astro.site-derived
// canonical/og tags) is only set from PUBLIC_SITE_ORIGIN, and the sitemap
// integration is only included when it's set. This keeps any staging
// *.pages.dev origin out of the build entirely by default; pages already
// treat `Astro.site` as optional and omit the tags that need it.
// Trailing slash(es) stripped for consistency with data.ts and
// postbuild-robots.mjs's origin-concatenation idiom — an origin like
// "https://example.com/" would otherwise double up when Astro's sitemap
// integration (or a page) appends a path.
const siteOrigin = process.env.PUBLIC_SITE_ORIGIN?.replace(/\/+$/, '');

export default defineConfig({
  ...(siteOrigin ? { site: siteOrigin } : {}),
  // M2 probe (docs/lyceum-shared-repo-plan.md §11.2): on-request pages
  // (app/src/pages/library/index.astro, api/catalog/publish.ts,
  // catalog.snapshot.json.ts) need the Cloudflare adapter; every other page
  // keeps Astro's default static output (unaffected: no `output` override).
  // prerenderEnvironment: 'node' -- the adapter's default ('workerd') runs
  // static-page prerendering inside a sandboxed workerd fs that cannot see
  // app/public/data (a symlink to ../../build/dist, outside the project
  // root): a build under the default came back with "103 registered
  // work(s) have no data in this checkout" though the corpus is right
  // there. 'node' restores the plain Node fs prerendering every other page
  // already depends on (built-works.ts, lyceum-catalog.ts, etc.); only the
  // three new on-request routes run in workerd, which is what this probe is
  // actually testing.
  adapter: cloudflare({ prerenderEnvironment: 'node' }),
  // No sessions anywhere on this site -- keeps the Worker bundle small
  // (John, 2026-09-14).
  session: false,
  // Route caching (Astro 7 addition, John 2026-09-14): the Cloudflare
  // provider tags/purges through the Worker cache API. library/index.astro
  // and catalog.snapshot.json.ts both tag their response 'catalog';
  // api/catalog/publish.ts invalidates that tag after a successful write (or
  // a same-revision replay) so both routes purge together.
  cache: {
    provider: cacheCloudflare(),
  },
  routeRules: {
    '/library': { maxAge: 60, swr: 86400, tags: ['catalog'] },
    '/catalog.snapshot.json': { maxAge: 60, swr: 86400, tags: ['catalog'] },
  },
  integrations: [
    svelte(),
    ...(siteOrigin ? [sitemap()] : []),
  ],
  vite: {
    server: {
      fs: { allow: ['..'] },
    },
    resolve: {
      // The reader core (components, libs, global.css) lives in ../shared and
      // is consumed by both this site and the desktop app. See shared/README.md.
      alias: {
        '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
      },
    },
  },
});