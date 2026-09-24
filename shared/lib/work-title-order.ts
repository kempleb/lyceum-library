// Shared work-title ordering rule (John's ruling, 2026-07-23: "one uniform
// rule -- testimonia first, fragments second, for every author"). Plain
// alphabetical order puts "Fragments" ahead of "Testimonia", so every site
// that sorts works by title (shared/lib/lyceum-catalog-source.ts's
// sortWorks, shared/lib/palette.ts's rankWorks, app/src/lib/lyceum-catalog.ts's
// foreign-author sort) needs this same tie-break instead of a bare
// localeCompare.
//
// Order: collation of a key in which "Testimonia" reads as "Fragments", then
// Testimonia first, then code units. That moves only Testimonia (to just
// before Fragments); every other title keeps its alphabetical place.
function sortKey(title: string): string {
  return title === 'Testimonia' ? 'Fragments' : title;
}

export function compareWorkTitles(a: string, b: string): number {
  const byKey = sortKey(a).localeCompare(sortKey(b));
  if (byKey !== 0) return byKey;
  // Keys collate equal: Testimonia goes before every such title, not just
  // "Fragments" -- localeCompare calls some distinct strings equal, and a
  // pairwise rule there would make a cycle.
  const aT = a === 'Testimonia';
  const bT = b === 'Testimonia';
  if (aT !== bT) return aT ? -1 : 1;
  // Code-unit order last, so only identical strings return 0.
  return a < b ? -1 : a > b ? 1 : 0;
}
