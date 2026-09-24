// Build-time route list for /read/<author>/<work>/section-<n>/ — one alias
// page per section of every *flat section-scheme* work (Enchiridion, the
// Epicurus minor works, several Cicero works — any work whose registry
// citation.scheme is 'section'; see shared/lib/citation.ts's makeFlatScheme).
// Underscore-prefixed so Astro's router ignores it (it is not a page).
//
// Section numbers come from each built work's public/data/<id>/columns.json
// (same per-work column index the reader itself, BekkerJump/CommandPalette
// and scripts/build-citation-index.mjs read — see shared/lib/citation.ts),
// keyed by the exact citation token that has a real `col-<n>` anchor in the
// built book page — NOT the manifest's citation.books[0] start..end range.
// Several of these works cite a gapped ancient numbering (e.g. Epicurus'
// Vatican Sayings has no section 5, 6, 8, 10 — verified against
// app/public/data/epicurus-vatican-sayings/columns.json, 2026-09-01): a
// contiguous start..end would emit `?loc=` links scripts/check-links.mjs
// flags as "citation target col-<n> not found".
import { existsSync, readFileSync } from 'node:fs';
import { getAuthor } from '@shared/lib/authors';
import { workSlug } from '@shared/lib/works';
import { builtWorks } from '../../lib/built-works';

export interface SectionRoute {
  author: string;
  work: string;
  n: string;
  bookN: number;
}

interface ColumnEntry {
  book: number;
}

function columnsFor(workId: string): Record<string, ColumnEntry[]> | null {
  const file = `public/data/${workId}/columns.json`;
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, 'utf8')) as Record<string, ColumnEntry[]>;
}

export function sectionRoutes(): SectionRoute[] {
  const routes: SectionRoute[] = [];
  for (const work of builtWorks()) {
    if (work.citation?.scheme !== 'section') continue;
    const author = getAuthor(work.author);
    if (!author) {
      throw new Error(`[section-routes] work '${work.id}' has unresolvable author '${work.author}'`);
    }
    const columns = columnsFor(work.id);
    if (!columns) continue;
    const slug = workSlug(work);
    for (const [n, entries] of Object.entries(columns)) {
      const bookN = entries[0]?.book ?? 1;
      routes.push({ author: author.id, work: slug, n, bookN });
    }
  }
  return routes;
}
