// Appends a Sitemap: line to dist/client/robots.txt, but only when the build has a
// real canonical origin (PUBLIC_SITE_ORIGIN). Staging (*.pages.dev) builds
// must never bake in a sitemap URL — see astro.config.mjs.
import { appendFileSync, existsSync } from 'node:fs';

const origin = process.env.PUBLIC_SITE_ORIGIN;
if (origin) {
  const dist = 'dist/client/robots.txt';
  if (!existsSync(dist)) {
    console.error(`postbuild-robots: ${dist} not found`);
    process.exit(1);
  }
  const trimmedOrigin = origin.replace(/\/+$/, '');
  appendFileSync(dist, `\nSitemap: ${trimmedOrigin}/sitemap-index.xml\n`);
}
