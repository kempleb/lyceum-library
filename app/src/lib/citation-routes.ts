// Build-time citation shim paths. Like built-works.ts, this reads cwd-relative
// files while Astro runs from app/: public/data is the build/dist symlink, and
// corpus mount files live one directory above the app package.
import { existsSync, readFileSync } from 'node:fs';
import { load } from 'js-yaml';
import { getAuthor } from '@shared/lib/authors';
import { WORK_CORPUS_DATA } from '@shared/lib/registry.generated';
import { workSlug } from '@shared/lib/works';
import { builtWorks } from './built-works';

interface CitationIndexEntry {
  work: string;
  book: number;
}

type CitationIndex = Record<string, CitationIndexEntry[]>;

interface MountConfig {
  corpus?: string;
  citationRoutes?: boolean;
}

export interface CitationRoute {
  author: string;
  work: string;
  cite: string;
  bookN: number;
}

const INDEX_PATH = 'public/data/citation-index.json';
const WORK_CORPUS = WORK_CORPUS_DATA as Record<string, string>;

function enabledCorpora(): Set<string> {
  const enabled = new Set<string>();
  for (const corpus of new Set(Object.values(WORK_CORPUS))) {
    const mountPath = `../corpora/${corpus}/mount.yaml`;
    if (!existsSync(mountPath)) continue;
    const config = load(readFileSync(mountPath, 'utf8')) as MountConfig | null;
    if (config?.corpus === corpus && config.citationRoutes === true) enabled.add(corpus);
  }
  return enabled;
}

function buildCitationRoutes(): CitationRoute[] {
  if (!existsSync(INDEX_PATH)) return [];

  const enabled = enabledCorpora();
  if (enabled.size === 0) return [];

  const eligibleWorks = new Map(
    builtWorks()
      .filter((work) => enabled.has(WORK_CORPUS[work.id]))
      .map((work) => [work.id, work]),
  );
  if (eligibleWorks.size === 0) return [];

  const index = JSON.parse(readFileSync(INDEX_PATH, 'utf8')) as CitationIndex;
  const routes: CitationRoute[] = [];

  for (const [cite, entries] of Object.entries(index)) {
    const seenWorks = new Set<string>();
    for (const entry of entries) {
      if (seenWorks.has(entry.work)) continue;
      seenWorks.add(entry.work);

      const work = eligibleWorks.get(entry.work);
      if (!work) continue;
      const author = getAuthor(work.author);
      if (!author) {
        throw new Error(
          `[citation-routes] work '${work.id}' has unresolvable author '${work.author}'`,
        );
      }
      routes.push({ author: author.id, work: workSlug(work), cite, bookN: entry.book });
    }
  }

  return routes;
}

export const citationRoutes: CitationRoute[] = buildCitationRoutes();
