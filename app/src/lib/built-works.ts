// Build-time gate: the works registry may list works whose pipeline data
// isn't present in this checkout (build/dist is gitignored; a fresh clone has
// nothing under public/data). The site serves what's built — page emission and
// listings only include works with public/data/<workId>/manifest.json on disk
// at build time. Path style matches ReaderShell.astro / speaker-roster.ts
// (cwd-relative public/data/… from the app package root).
import { existsSync } from 'node:fs';
import { WORKS, getWork, type Work } from '@shared/lib/works';
import { AUTHORS, getAuthor, type Author } from '@shared/lib/authors';

const cache = new Map<string, boolean>();
let warned = false;

function check(workId: string): boolean {
  const hit = cache.get(workId);
  if (hit !== undefined) return hit;
  const built = existsSync(`public/data/${workId}/manifest.json`);
  cache.set(workId, built);
  return built;
}

// One-time console.warn listing every registered-but-unbuilt work id so a
// partial build is loud, never silent. Memoized with the fs checks so
// getStaticPaths can call isBuilt/builtWorks repeatedly.
function warnOnce(): void {
  if (warned) return;
  warned = true;
  const missing = WORKS.filter((w) => !check(w.id)).map((w) => w.id);
  if (missing.length === 0) return;
  console.warn(
    `[built-works] ${missing.length} registered work(s) have no data in this checkout` +
      ` and will not emit pages: ${missing.join(', ')}`,
  );
}

/** True iff public/data/<workId>/manifest.json exists at build time. */
export function isBuilt(workId: string): boolean {
  warnOnce();
  return check(workId);
}

/** Registry works that have pipeline data on disk in this checkout. */
export function builtWorks(): Work[] {
  warnOnce();
  return WORKS.filter((w) => check(w.id));
}

/**
 * Registry authors with at least one built work, in registry order — the
 * breadcrumb's AUTHOR dropdown option list (see components/Breadcrumb.svelte).
 * Mirrors [author]/index.astro's own getStaticPaths filter.
 */
export function builtAuthors(): Author[] {
  warnOnce();
  return AUTHORS.filter((a) => a.works.some((id) => check(id)));
}

/**
 * A given author's built works, in the author's own curated order (not WORKS
 * registry order — see [author]/index.astro's matching `works` computation).
 * The breadcrumb's WORK dropdown option list. Unknown author id -> empty.
 */
export function builtWorksOf(authorId: string): Work[] {
  warnOnce();
  const author = getAuthor(authorId);
  if (!author) return [];
  return author.works.map((id) => getWork(id)).filter((w): w is Work => w !== undefined && check(w.id));
}
