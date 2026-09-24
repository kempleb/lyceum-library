import { readFileSync } from 'node:fs';

// Column-level CC licence notes (John's ruling, 2026-09-23: "Add the
// appropriate CC licence info next to translations or works that are CC.").
//
// A manifest's `english.column_sources` (e.g. Gorgias's Parnassos Press
// Encomium of Helen / Defence of Palamedes, manifests/gorgias-fragments.yaml)
// ships a CC-licensed translation as a COLUMN override that displaces the
// work's primary translation for specific passages -- it is never a
// registry `translations[]` entry, so visibleTranslations() (shared/lib/
// works.ts) never sees it and attribution.astro's per-translation CC badge
// never fires for it.
//
// stage7_emit.py already folds column_sources into the per-work
// manifest.json it emits (public/data/<id>/manifest.json -- the same
// build-time file Landing.astro and built-works.ts read) as slot:"column"
// translations carrying a license object (see that file's
// _manifest_v1_fields). This reads that back, grouped by licence
// (name+url), so two columns sharing one licence (Gorgias's B11/B11a) merge
// into a single note instead of repeating it.
export interface ColumnCcNote {
  columns: string[];
  name: string;
  url?: string;
}

interface ManifestTranslation {
  slot?: string;
  columns?: string[];
  license?: { status?: string; name?: string; url?: string };
}

/** CC-licensed column-source translations for a built work, grouped by licence. Returns [] when the work isn't built or declares none. */
export function columnCcLicenses(workId: string): ColumnCcNote[] {
  let translations: ManifestTranslation[];
  try {
    const manifest = JSON.parse(readFileSync(`public/data/${workId}/manifest.json`, 'utf-8'));
    translations = manifest.translations ?? [];
  } catch {
    return [];
  }
  const groups = new Map<string, ColumnCcNote>();
  for (const t of translations) {
    if (t.slot !== 'column' || t.license?.status !== 'cc' || !t.license.name) continue;
    const key = `${t.license.name}\u0000${t.license.url ?? ''}`;
    const existing = groups.get(key);
    if (existing) {
      existing.columns.push(...(t.columns ?? []));
    } else {
      groups.set(key, { columns: [...(t.columns ?? [])], name: t.license.name, url: t.license.url });
    }
  }
  return [...groups.values()];
}
