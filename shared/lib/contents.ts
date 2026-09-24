// Data model for the Lyceum reader chrome (PUBLIC_LYCEUM_CHROME): the running
// head's label composition, the Contents sheet's per-work outline, and the
// Library sheet's shelf/author/work listing with its filter.
//
// PURE: no fs, no import.meta.env, no DOM. Every input is plain data read by
// the caller (ReaderShell.astro reads the registries and the built JSON; the
// Svelte sheets get the finished model as a prop), so this module can be unit
// tested on its own and is safe to bundle into a client island.

// ── Running head ──────────────────────────────────────────────────────────

export interface RunningHeadParts {
  author: string;
  work: string;
  book: string | null;    // 'Book I' — null for a bookless work
  section: string | null; // '§22' / '1094a' / 'B30'
  heading: string | null; // 'Thales' / 'The good as the aim of action'
}

/** The running head as one plain string — what a screen reader hears, and
 *  what the label-composition test asserts against. */
export function runningHeadText(p: RunningHeadParts): string {
  const cite = [p.section, p.heading].filter(Boolean).join(' ');
  return [p.author, p.work, p.book, cite || null].filter(Boolean).join(' · ');
}

/**
 * A segment column rendered as the running head's citation slot. A dotted
 * column carries its book as a literal prefix ("1.22"), which the head already
 * shows as "Book I", so only the section part is repeated; a bare numeral is a
 * section too. `noun` names the unit for a scheme whose divisions are not
 * sections ("Chapter 3", "Line 234"); without it a numeric column takes the
 * section mark, and any other column IS the citation already (Bekker "1094a",
 * Diels-Kranz "B30") and is shown whole.
 */
export function citeDisplay(column: string, noun?: string | null): string {
  if (!column) return '';
  const dotted = column.match(/^\d+\.(\d+[a-z]?)$/i);
  const tail = dotted ? dotted[1] : column;
  if (noun) return `${noun} ${tail}`;
  if (dotted || /^\d+$/.test(column)) return `§${tail}`;
  return column;
}

// ── Contents of one work ──────────────────────────────────────────────────

export interface ManifestBookRange { n: number; start: string; end: string }

export interface ContentsEntry {
  name: string;
  // The running head's heading for this entry — the bare title, without the
  // numeral the sheet's own line carries. null for a range entry, which names
  // no heading at all.
  head: string | null;
  extent: string;
  hash: string;       // '#col-1.22' or '#ch-1-3'
  column: string;     // the anchor's citation token, for heading lookup
  current: boolean;
  search: string;
}

export interface ContentsBook {
  n: number;
  heading: string;    // 'Book I'
  extent: string;     // '§§1–122 · 12 lives'
  href: string;       // page href, for a collapsed book line
  current: boolean;
  entries: ContentsEntry[];  // filled for the current book only
  search: string;
}

export interface ContentsModel {
  title: string;
  meta: string;
  placeholder: string;
  note: string | null;
  books: ContentsBook[];
}

export interface ContentsInput {
  workTitle: string;
  groupNoun: string;              // 'Book' | 'Letter'
  bookLabels: string[];           // display label per book, index 0 = book 1
  books: number;
  currentBook: number;
  bookless: boolean;
  unit: { singular: string; plural: string };
  manifestBooks: ManifestBookRange[];
  chapters: Record<string, { chapter: string; bekker: string }[]>;
  sections: Record<string, { column: string; letter?: number | string }[]>;
  philosophers: Record<string, { startSection: number; endSection: number; name: string; id: string }[]>;
  chapterTitles: Record<string, Record<string, string>>;
  bookHref: (n: number) => string;
}

const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const num = (n: number) => n.toLocaleString('en-US');

/** '§§1–10' for section-cited works, 'Chapters 1–10' for the rest. */
function rangeLabel(a: string | number, b: string | number, unit: { singular: string; plural: string }): string {
  if (unit.singular === 'section') return `§§${a}–${b}`;
  return `${cap(unit.plural)} ${a}–${b}`;
}

/** Data headings are set in capitals in the source ('THALES'); the sheet sets
 *  its own small caps, so normalise an all-caps name to title case. */
export function titleCaseName(raw: string): string {
  if (!raw || raw !== raw.toUpperCase()) return raw;
  return raw.toLowerCase().replace(/(^|[\s'’-])([a-z])/g, (_, lead, ch) => lead + ch.toUpperCase());
}

const dottedSection = (column: string): string => {
  const m = column.match(/^\d+\.(\d+[a-z]?)$/i);
  return m ? m[1] : column;
};

/**
 * How many units a book's citation range covers ('1.122' -> 122, '53' -> 53).
 * Only a purely numeric section token is a tally: a Bekker page ('1103a') and a
 * Diels-Kranz reference ('B139') number the edition, not the units.
 */
function countableRange(range: ManifestBookRange | undefined): number | null {
  if (!range) return null;
  const tail = dottedSection(range.end);
  if (!/^\d+$/.test(tail)) return null;
  const n = Number(tail);
  return n > 0 ? n : null;
}

/**
 * The contents of one work: the current book expanded into its real headings
 * where the built data has them, every other book collapsed to a single line
 * with its citation range. Never a grid of every numeral — a book with no
 * headings of its own expands into section RANGES instead.
 */
export function buildContents(input: ContentsInput): ContentsModel {
  const {
    workTitle, groupNoun, bookLabels, books, currentBook, bookless, unit,
    manifestBooks, chapters, sections, philosophers, chapterTitles, bookHref,
  } = input;
  const mBook = (n: number) => manifestBooks.find((b) => b.n === n);

  const bookRows: ContentsBook[] = [];
  for (let n = 1; n <= books; n++) {
    const current = n === currentBook;
    const label = bookLabels[n - 1] ?? String(n);
    const heading = bookless ? workTitle : `${groupNoun} ${label}`;
    const range = mBook(n);
    const secs = sections[String(n)] ?? [];
    const chaps = chapters[String(n)] ?? [];
    const phils = philosophers[String(n)] ?? [];
    const count = secs.length || chaps.length || countableRange(range);
    const parts: string[] = [];
    if (range) {
      parts.push(unit.singular === 'section'
        ? `§§${dottedSection(range.start)}–${dottedSection(range.end)}`
        : `${dottedSection(range.start)}–${dottedSection(range.end)}`);
    }
    if (phils.length) parts.push(`${phils.length} lives`);
    else if (count) parts.push(`${num(count)} ${count === 1 ? unit.singular : unit.plural}`);

    bookRows.push({
      n,
      heading,
      extent: parts.join(' · '),
      href: bookHref(n),
      current,
      search: `${heading} ${parts.join(' ')}`.toLowerCase(),
      entries: current ? bookEntries(n, input) : [],
    });
  }

  // Total units across the work: what the built outline actually holds, and
  // only for a scheme whose citation counts units (a Bekker range's "1103a"
  // is a page, not a tally, so it is never summed).
  let totals = 0;
  for (let n = 1; n <= books; n++) {
    const key = String(n);
    totals += (sections[key] ?? []).length || (chapters[key] ?? []).length
      || (countableRange(mBook(n)) ?? 0);
  }
  const first = manifestBooks[0];
  const last = manifestBooks[manifestBooks.length - 1];
  const meta = [
    bookless ? null : `${books} ${books === 1 ? groupNoun.toLowerCase() : `${groupNoun.toLowerCase()}s`}`,
    totals ? `${num(totals)} ${unit.plural}` : null,
    first && last ? `${first.start}–${last.end}` : null,
  ].filter(Boolean).join(' · ');

  const expanded = bookRows.find((b) => b.current);
  const note = expanded && expanded.entries.length === 0
    ? `This ${groupNoun.toLowerCase()} has no headings of its own, so the contents give its citation range.`
    : null;

  return {
    title: `${workTitle} · contents`,
    meta,
    placeholder: bookless
      ? `Find a ${unit.singular} or a citation`
      : `Find a ${groupNoun.toLowerCase()}, a heading, or a citation`,
    note,
    books: bookRows,
  };
}

/** The current book's entries: real headings where the data has them, section
 *  ranges where it does not. */
function bookEntries(n: number, input: ContentsInput): ContentsEntry[] {
  const { sections, chapters, philosophers, chapterTitles, unit } = input;
  const key = String(n);
  const phils = philosophers[key] ?? [];
  const secs = sections[key] ?? [];
  const chaps = chapters[key] ?? [];

  // 1. Named divisions carried by the source (Diogenes Laertius' lives).
  if (phils.length) {
    return phils.map((g) => {
      const column = g.id.includes(':') ? g.id.split(':')[1] : String(g.startSection);
      const name = titleCaseName(g.name);
      const extent = `§§${g.startSection}–${g.endSection}`;
      return { name, head: name, extent, hash: `#col-${column}`, column, current: false, search: `${name} ${extent}`.toLowerCase() };
    });
  }

  // 2. Chapters, with their curated titles where a work has them.
  if (chaps.length) {
    const titles = chapterTitles[key] ?? {};
    return chaps.map((c) => {
      const title = titles[c.chapter];
      const name = title ? `${c.chapter}. ${title}` : `${cap(unit.singular)} ${c.chapter}`;
      return {
        name, head: title ?? null, extent: c.bekker, hash: `#ch-${n}-${c.chapter}`,
        column: c.chapter, current: false, search: `${name} ${c.bekker}`.toLowerCase(),
      };
    });
  }

  // 3. No headings: section ranges, ten to a line.
  if (secs.length) {
    const out: ContentsEntry[] = [];
    for (let i = 0; i < secs.length; i += 10) {
      const chunk = secs.slice(i, i + 10);
      const a = dottedSection(chunk[0].column);
      const b = dottedSection(chunk[chunk.length - 1].column);
      const name = rangeLabel(a, b, unit);
      out.push({
        name, head: null,
        extent: `${chunk.length} ${chunk.length === 1 ? unit.singular : unit.plural}`,
        hash: `#col-${chunk[0].column}`, column: chunk[0].column,
        current: false, search: `${name}`.toLowerCase(),
      });
    }
    return out;
  }

  return [];
}

/** The heading covering `column` in the open book — the running head's third
 *  part. Entries are in reading order, so the last one at or before the
 *  column wins. */
export function headingAt(book: ContentsBook | undefined, column: string): string | null {
  if (!book || !column) return null;
  const want = orderKey(column);
  if (want == null) return null;
  let hit: string | null = null;
  for (const e of book.entries) {
    const at = orderKey(e.column);
    if (at == null || at > want) break;
    hit = e.head;
  }
  return hit;
}

function orderKey(column: string): number | null {
  const m = String(column).match(/(\d+)\s*$/) ?? String(column).match(/(\d+)/);
  return m ? Number(m[1]) : null;
}

// ── The library ───────────────────────────────────────────────────────────

export interface LibWorkEntry {
  id: string; title: string; href: string; extent: string; current: boolean; search: string;
}
export interface LibGroup { label: string | null; works: LibWorkEntry[] }
export interface LibAuthorEntry {
  id: string; name: string; meta: string; current: boolean; groups: LibGroup[]; search: string;
}
export interface LibShelf { id: string; name: string; meta: string; authors: LibAuthorEntry[] }
export interface LibraryModel { meta: string; shelves: LibShelf[] }

export interface LibraryInput {
  shelves: {
    id: string;
    name: string;
    authors: {
      id: string; name: string; floruit: string; current: boolean;
      groups: { label: string | null; works: { id: string; title: string; href: string; extent: string; current: boolean }[] }[];
    }[];
  }[];
}

/** Shelf → author → work, with the count lines and the searchable text each
 *  row is filtered on. */
export function buildLibrary(input: LibraryInput): LibraryModel {
  let authorCount = 0;
  let workCount = 0;
  const shelves: LibShelf[] = input.shelves.map((s) => {
    let shelfWorks = 0;
    const authors: LibAuthorEntry[] = s.authors.map((a) => {
      const groups: LibGroup[] = a.groups.map((g) => ({
        label: g.label,
        works: g.works.map((w) => ({
          ...w,
          search: `${a.name} ${w.title} ${w.extent}`.toLowerCase(),
        })),
      }));
      const n = groups.reduce((sum, g) => sum + g.works.length, 0);
      shelfWorks += n;
      authorCount += 1;
      return {
        id: a.id, name: a.name, current: a.current, groups,
        meta: [a.floruit, `${n} ${n === 1 ? 'work' : 'works'}`].filter(Boolean).join(' · '),
        search: `${a.name} ${a.floruit}`.toLowerCase(),
      };
    });
    workCount += shelfWorks;
    return {
      id: s.id, name: s.name, authors,
      meta: `${authors.length} ${authors.length === 1 ? 'author' : 'authors'} · ${shelfWorks} ${shelfWorks === 1 ? 'work' : 'works'}`,
    };
  });
  return {
    meta: `${authorCount} ${authorCount === 1 ? 'author' : 'authors'} · ${workCount} ${workCount === 1 ? 'work' : 'works'}`,
    shelves,
  };
}

/** Fold accents so "Diogenes" finds "Diogenes Laërtius". */
export function foldText(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

/**
 * Narrow the whole sheet as you type: an author whose own name matches keeps
 * all of their works; otherwise only the matching works survive, and an author
 * (or shelf) left with nothing drops out.
 */
export function filterLibrary(model: LibraryModel, query: string): LibraryModel {
  const q = foldText(query.trim());
  if (!q) return model;
  const shelves: LibShelf[] = [];
  for (const s of model.shelves) {
    const authors: LibAuthorEntry[] = [];
    for (const a of s.authors) {
      const authorHit = foldText(a.search).includes(q);
      const groups = a.groups
        .map((g) => ({ label: g.label, works: authorHit ? g.works : g.works.filter((w) => foldText(w.search).includes(q)) }))
        .filter((g) => g.works.length > 0);
      if (groups.length) authors.push({ ...a, groups });
    }
    if (authors.length) shelves.push({ ...s, authors });
  }
  const authorCount = shelves.reduce((n, s) => n + s.authors.length, 0);
  const workCount = shelves.reduce(
    (n, s) => n + s.authors.reduce((m, a) => m + a.groups.reduce((k, g) => k + g.works.length, 0), 0), 0);
  return {
    meta: `${authorCount} ${authorCount === 1 ? 'author' : 'authors'} · ${workCount} ${workCount === 1 ? 'work' : 'works'}`,
    shelves,
  };
}

/** Narrow a work's contents the same way. */
export function filterContents(books: ContentsBook[], query: string): ContentsBook[] {
  const q = foldText(query.trim());
  if (!q) return books;
  const out: ContentsBook[] = [];
  for (const b of books) {
    const bookHit = foldText(b.search).includes(q);
    const entries = bookHit ? b.entries : b.entries.filter((e) => foldText(e.search).includes(q));
    if (bookHit || entries.length) out.push({ ...b, entries });
  }
  return out;
}

/**
 * Does this look like a citation rather than a name? Decides whether the
 * filter field offers a "Go to …" line above the narrowed list; the real
 * parsing is done by the work's own citation scheme (shared/lib/citation.ts's
 * parseLocation / parseDkFullCitation), never here.
 */
export function looksLikeCitation(raw: string): boolean {
  const q = raw.trim();
  if (!q || !/\d/.test(q)) return false;
  return /^\d+(\.\d+)*[a-z]?\d*$/i.test(q)              // 1.4 · 1094a15 · 17a
    || /^[ab]\s?\d+[a-z]?$/i.test(q)                    // B30
    || /^dk\s*\d+\s*[ab]?\s*\d*$/i.test(q)              // DK 22 B30
    || /^[a-z][a-z.]{0,14}\.?\s+\d+(\.\d+)*[a-z]?\d*$/i.test(q);  // Tusc 1.4
}

// ── The catalog ───────────────────────────────────────────────────────────
//
// The one-page ledger of docs/design-spec.md §6, and the homepage's ledger
// previews (§5.3.3): collection -> period -> author -> work. Same discipline
// as buildLibrary above — the caller resolves the registries and the built
// manifests and hands plain strings in; this module only composes the count
// lines, the period grouping and the facet tokens the Catalog page's filter
// bar narrows on.

export interface CatalogWorkInput {
  id: string;
  title: string;
  href: string;
  /** The work's own extent and citation range: '12 books · 1.1–12.36'. */
  extent: string;
  language: string;   // display label: 'Greek' | 'Latin'
  form: string;       // display label: 'Fragments' | 'Prose' | 'Verse' | 'Letters'
  /** Set only for a partner-catalog work with no work of ours behind it: the
   *  partner origin's bare hostname, e.g. 'library.lyceum.institute' — DATA,
   *  never copy, rendered as the link's visible external marker. Absent for
   *  every work of our own. */
  external?: string;
}

export interface CatalogAuthorInput {
  id: string;
  name: string;
  period: string;        // period id, the facet token
  periodLabel: string;   // 'Presocratics'
  /** The author's citation summary — 'DK 22', 'Bekker', 'Latin · 10 works'. */
  range: string;
  works: CatalogWorkInput[];
}

export interface CatalogSectionInput {
  id: string;
  name: string;
  /** Wing accent class suffix, e.g. 'roman' for --brick. */
  accent?: string | null;
  enterHref?: string | null;
  enterLabel?: string;
  /** A collection with no works yet (the Roman and American wings). */
  note?: string | null;
  /** The id of this collection's parent, one level of nesting (partner
   *  schema's parent_id) -- null/absent for a root collection. A child is
   *  still its own section, listed right after its parent's (ruling
   *  2026-09-13: consumers don't render real nesting yet). */
  parentId?: string | null;
  authors: CatalogAuthorInput[];
}

/** The five facets of §6's filter row, as one work's tokens. */
export interface CatalogFacetTokens {
  author: string;
  collection: string;
  period: string;
  language: string;
  form: string;
}

/** A chosen facet value per axis; '' (or absent) means "any". */
export type CatalogSelection = Partial<CatalogFacetTokens>;

export interface CatalogWork extends CatalogWorkInput { facets: CatalogFacetTokens }
export interface CatalogAuthor extends Omit<CatalogAuthorInput, 'works'> { works: CatalogWork[] }
export interface CatalogGroup { label: string | null; authors: CatalogAuthor[] }
export interface CatalogSection {
  id: string;
  name: string;
  accent: string | null;
  enterHref: string | null;
  enterLabel: string;
  note: string | null;
  parentId: string | null;
  /** True when this collection has no visible works of its own (ruling
   *  2026-09-13: shown, not dropped). */
  empty: boolean;
  meta: string;
  authorCount: number;
  workCount: number;
  groups: CatalogGroup[];
}
export interface CatalogOption { value: string; label: string }
export interface CatalogModel {
  sections: CatalogSection[];
  authorCount: number;
  workCount: number;
  meta: string;
  /** The filter bar's options, each axis in the order the ledger reads. */
  options: Record<keyof CatalogFacetTokens, CatalogOption[]>;
}

function pushOption(into: Map<string, CatalogOption>, value: string, label: string): void {
  if (value && !into.has(value)) into.set(value, { value, label });
}

/**
 * The ledger. Sections keep the caller's order (the launch chunk order, not
 * alphabetical); within a section, authors are grouped under their period
 * label — but only where a section spans more than one period, since a
 * single-period collection has nothing to group (spec §6).
 */
export function buildCatalog(sections: CatalogSectionInput[]): CatalogModel {
  const opt: Record<keyof CatalogFacetTokens, Map<string, CatalogOption>> = {
    author: new Map(), collection: new Map(), period: new Map(),
    language: new Map(), form: new Map(),
  };
  // Distinct by id: the same author or work can belong to more than one
  // collection, and the library-wide totals count the person and the text
  // once each, not once per membership (a work in two collections must not
  // double the library's own work count).
  const seenAuthorIds = new Set<string>();
  const seenWorkIds = new Set<string>();
  let authorCount = 0;
  let workCount = 0;

  const out: CatalogSection[] = sections.map((s) => {
    pushOption(opt.collection, s.id, s.name);
    const languages: string[] = [];
    let sectionWorks = 0;
    const authors: CatalogAuthor[] = s.authors.map((a) => {
      pushOption(opt.author, a.id, a.name);
      pushOption(opt.period, a.period, a.periodLabel);
      sectionWorks += a.works.length;
      if (!seenAuthorIds.has(a.id)) {
        seenAuthorIds.add(a.id);
        authorCount += 1;
      }
      return {
        ...a,
        works: a.works.map((w) => {
          pushOption(opt.language, w.language, w.language);
          pushOption(opt.form, w.form, w.form);
          if (!languages.includes(w.language)) languages.push(w.language);
          if (!seenWorkIds.has(w.id)) {
            seenWorkIds.add(w.id);
            workCount += 1;
          }
          return {
            ...w,
            facets: {
              author: a.id, collection: s.id, period: a.period,
              language: w.language, form: w.form,
            },
          };
        }),
      };
    });

    const periods = new Set(authors.map((a) => a.period));
    const groups: CatalogGroup[] = [];
    for (const a of authors) {
      const label = periods.size > 1 ? a.periodLabel : null;
      const last = groups[groups.length - 1];
      if (last && last.label === label) last.authors.push(a);
      else groups.push({ label, authors: [a] });
    }

    const meta = [
      languages.join(' & '),
      `${authors.length} ${authors.length === 1 ? 'author' : 'authors'}`,
      `${sectionWorks} ${sectionWorks === 1 ? 'work' : 'works'}`,
    ].filter(Boolean).join(' · ').toUpperCase();

    return {
      id: s.id,
      name: s.name,
      accent: s.accent ?? null,
      enterHref: s.enterHref ?? null,
      enterLabel: s.enterLabel ?? 'enter →',
      note: s.note ?? null,
      parentId: s.parentId ?? null,
      empty: sectionWorks === 0,
      meta: sectionWorks ? meta : (s.note ? '' : meta),
      authorCount: authors.length,
      workCount: sectionWorks,
      groups,
    };
  });

  return {
    sections: out,
    authorCount,
    workCount,
    meta: `${authorCount} ${authorCount === 1 ? 'author' : 'authors'} · ${workCount} ${workCount === 1 ? 'work' : 'works'}`,
    options: {
      author: [...opt.author.values()].sort((a, b) => a.label.localeCompare(b.label)),
      collection: [...opt.collection.values()],
      period: [...opt.period.values()],
      language: [...opt.language.values()],
      form: [...opt.form.values()],
    },
  };
}

/** Does one work survive the chosen facets? Every axis is an AND. */
export function matchesCatalogFacets(tokens: CatalogFacetTokens, selection: CatalogSelection): boolean {
  for (const axis of ['author', 'collection', 'period', 'language', 'form'] as const) {
    const want = selection[axis];
    if (want && tokens[axis] !== want) return false;
  }
  return true;
}

/** One ledger row's work id and whether the current filter keeps it. */
export interface CatalogVisibilityRow {
  workId: string;
  visible: boolean;
}

/**
 * How many distinct works the filtered ledger shows. A work can carry a row
 * in more than one collection (a parent and a child section both list it),
 * so counting rows would let "shown" exceed the library's own work total —
 * this counts each work id at most once, no matter how many visible rows
 * name it.
 */
export function countVisibleWorks(rows: CatalogVisibilityRow[]): number {
  const seen = new Set<string>();
  for (const row of rows) {
    if (row.visible && row.workId) seen.add(row.workId);
  }
  return seen.size;
}
