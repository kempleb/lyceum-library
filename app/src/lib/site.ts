// Single source of truth for the site's display name — used in page titles,
// og:site_name, and JSON-LD across every page. Working title, per README.md:
// "the product name is not final; pending John's decision before the first
// public deploy" — centralized here so that decision is a one-line change.
// app/public/manifest.webmanifest can't import this (it's static JSON, not
// JS) and duplicates SITE_NAME in its "name"/"short_name"/"description" —
// update it by hand whenever this changes.
export const SITE_NAME = 'The Classical Philosophy Reader';

// The name the whole site wears under PUBLIC_LYCEUM_CHROME=1 (John, 2026-09-01:
// "Cut classical philosophy reader from the ui. Lyceum reader") — the demo
// origin is the library, not this wing. One constant so the band lockup, every
// page title, og:site_name and the JSON-LD all say the same thing.
export const LYCEUM_SITE_NAME = 'The Lyceum Reader';

// Which of the two names a page shows. The flag itself is read in the page or
// component (`import.meta.env.PUBLIC_LYCEUM_CHROME === '1'`) and passed in, so
// this stays a plain function the test suite can call both ways.
export function siteNameFor(lyceumChrome: boolean): string {
  return lyceumChrome ? LYCEUM_SITE_NAME : SITE_NAME;
}
