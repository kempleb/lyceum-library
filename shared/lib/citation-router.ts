// Citation router — Lyceum P3 stage 3 (docs/p3-plan.md, Settled decision 5;
// Stage sequence 3). A single entry point, `resolveCitation`, that turns a
// raw string a reader might type or paste ("1094a15", "EN 1094a15",
// "Nicomachean Ethics 1094a", "DK 22 B30", "1a5") into the work + citation
// it names, dispatching across EVERY scheme and EVERY work the registry
// carries — unlike shared/lib/citation.ts's `schemeFor(work).parseLocation`,
// which only ever knows how to parse a citation for a work you already have
// in hand. `shared/lib/citation.ts` stays untouched; this module is a new,
// separate layer built ON TOP of it (imports `schemeFor`/`parseDkFullCitation`,
// never reimplements their grammars).
//
// Pure with respect to the cross-corpus index: this module never fetches.
// The index (built by scripts/build-citation-index.mjs, fetched by
// shared/lib/data.ts's fetchCitationIndex) is injected by the caller via
// `opts.index`, so this module is fully unit-testable with a literal fixture
// and carries no runtime dependency on `fetch`/`import.meta.env` of its own
// (see data.ts's `resolveBekker`, reused below for book disambiguation,
// which is likewise fetch-free).
//
// Dispatch order (plan's Settled decision 5), each tried in turn only when
// the previous stage found NOTHING (a genuine no-match) — an AMBIGUOUS
// result at any stage is the final answer, never silently overridden by a
// weaker later stage:
//   1. work-qualified: "<abbr|slug|title> <locus>" — the named work's own
//      schemeFor(work).parseLocation parses the locus half. A comma between
//      qualifier and locus is tolerated ("Nicomachean Ethics, 1094a15").
//   2. `parseDkFullCitation` (citation.ts, unchanged) — "DK 22 B30" / "22 B30"
//      — GUARDED against a live homograph: a DK citation typed with a space
//      between chapter and series letter collapses, whitespace stripped, to
//      the exact string a Bekker/Busse page+line citation uses ("22 b30" ->
//      "22b30" == De Int 22b30; "28 b8" -> Parmenides B8 == APr 28b8; "31
//      b17" -> Empedocles B17 == APr 31b17 — all three verified live). When
//      the collapsed form is also a real column in the injected index, this
//      stage returns AmbiguousResolution (DK reading + index reading(s)),
//      never a silent DK pick. An UNSPACED input ("22b30") never reaches
//      this stage at all — DK_FULL_CITATION_RE requires the whitespace — so
//      it resolves via stage 3 alone: a scholar who omits the space is
//      understood to mean Bekker/Busse, not DK.
//   3. a bare column(+line) in the bekker/busse column grammar ("1094a",
//      "1094a15", busse "1a5") looked up in the injected cross-corpus index
//      (only bekker/busse works ever appear in that index). Line
//      containment narrows the candidate set only WITHIN one citation
//      scheme (e.g. two Bekker works sharing a split page) — across schemes
//      (Bekker vs Busse works that happen to print the same column string)
//      containment never narrows, since a line's presence in one scheme's
//      span says nothing about the other scheme.
//   4. `contextWorkId` fallback: `schemeFor(contextWorkId).parseLocation(raw)`
//      — byte-identical to BekkerJump.svelte's `go()` today (the reader's
//      in-page jump box), preserved here so a caller migrating onto this
//      router changes no user-visible behavior for that path.
//
// Ambiguity (never guess): when a stage's own candidates can't be narrowed
// to one work, this returns an AmbiguousResolution — NOT a genuine `null`.
// `null` means "not a citation at all, under any stage"; an
// AmbiguousResolution means "this IS a citation, and more than one work
// could equally be meant" (a bare column two different corpora's works both
// happen to use, e.g. two busse works that each start their own pagination
// at "1a"). A caller distinguishes the two with `isAmbiguous`.

import { resolveBekker, type CitationIndex } from './data';
import { schemeFor, parseDkFullCitation } from './citation';
import { WORKS, workSlug, type Work } from './works';

export type { CitationIndex, CitationIndexEntry } from './data';

export interface Resolution {
  workId: string;
  column: string;
  // Always populated (a number, or null for a lineless-scheme/bare-column
  // citation) — optional only so a caller pattern-matching on `Resolution |
  // AmbiguousResolution | null` doesn't have to destructure a candidate
  // shape that never carries it.
  line?: number | null;
  // The book that owns this column, when derivable — either directly from
  // the work's own scheme (a dotted column's book IS its prefix; see
  // citation.ts's `bookFromColumn`) or, for bekker/busse, from the injected
  // index's lo/hi span (the same distance-to-nearest-book logic
  // data.ts's `resolveBekker` already implements for a single work's own
  // columns.json — reused here rather than re-derived). Absent when neither
  // source can resolve it (no `opts.index` was given, or the column isn't
  // in it).
  bookN?: number;
}

// One work's claim on an otherwise-ambiguous citation, listed rather than
// silently chosen. Same shape as Resolution minus the "this is THE answer"
// implication.
export interface CitationCandidate {
  workId: string;
  column: string;
  line?: number | null;
  bookN?: number;
}

// The "null-ambiguous" shape: a citation this router recognizes as a real
// locus, but can't resolve to one work without guessing. Deliberately not
// `null` itself (see the module doc comment) — `isAmbiguous` below is the
// one place a caller should test for it.
export interface AmbiguousResolution {
  candidates: CitationCandidate[];
}

export function isAmbiguous(
  r: Resolution | AmbiguousResolution | null,
): r is AmbiguousResolution {
  return r != null && 'candidates' in r;
}

// Registry order (WORKS' own declaration order — not the home page's
// per-shelf WORK_ORDER in works.ts) is the ambiguity tie-break's stable sort
// key, per the plan: "filter candidates by line containment, then registry
// order". Registry order never PICKS a winner among distinct works by
// itself (that would be guessing) — it only gives the `candidates` array a
// deterministic, reviewable order once line containment has already failed
// to narrow the set to one.
const REGISTRY_ORDER = new Map(WORKS.map((w, i) => [w.id, i]));
function registryOrder(workId: string): number {
  return REGISTRY_ORDER.get(workId) ?? Number.MAX_SAFE_INTEGER;
}

// The book owning `column` for `workId`, reusing data.ts's resolveBekker
// (itself fetch-free) rather than re-implementing its line-distance
// disambiguation here. Tries the work's own scheme first (bookFromColumn is
// non-null for a dotted scheme — book-section, letter, verse-line — where
// the book is recoverable from the column string alone, no index needed);
// falls back to the injected index, scoped to this one work's own entries,
// when the scheme itself can't say (bekker/busse, whose column can be
// shared/split across two books).
function computeBookN(
  workId: string,
  column: string,
  line: number | null,
  index: CitationIndex | undefined,
): number | undefined {
  const direct = schemeFor(workId).bookFromColumn(column);
  if (direct != null) return direct;
  if (!index) return undefined;
  const entries = (index[column] ?? [])
    .filter((e) => e.work === workId)
    .map((e) => ({ book: e.book, lo: e.lo, hi: e.hi }));
  if (entries.length === 0) return undefined;
  return resolveBekker({ [column]: entries }, column, line) ?? undefined;
}

// ── Stage 1: work-qualified ("<abbr|slug|title> <locus>") ──────────────────

// Matches `qualifier` as a case-insensitive prefix of `raw`, requiring at
// least one whitespace character between it and whatever follows (a locus
// never starts with whitespace, so this is the one unambiguous boundary
// that works for every qualifier shape — a bare abbreviation ("EN"), a
// dotted/spaced one, or a full multi-word title). Returns the trimmed
// remainder past the qualifier, or null if `qualifier` isn't a prefix (or
// isn't followed by whitespace) — e.g. "ENDppp" never matches abbr "EN".
// Concatenated work-qualified citations ("EN1094a15", no separator) are out
// of scope for this stage — every accept-list example in the plan uses a
// space, and nothing in the corpus needs the tighter form.
function matchQualifier(raw: string, qualifier: string): string | null {
  if (!qualifier || raw.length <= qualifier.length) return null;
  if (raw.slice(0, qualifier.length).toLowerCase() !== qualifier.toLowerCase()) return null;
  let rest = raw.slice(qualifier.length);
  // A comma between qualifier and locus ("Nicomachean Ethics, 1094a15") is
  // tolerated as a stand-in for the plain-whitespace boundary — a reader
  // typing a full title naturally reaches for the comma a citation style
  // guide would use. This is punctuation around the SAME qualifier string,
  // not a different spelling of it, so it's not an alias table (a separate,
  // John-gated item — docs/p3-plan.md).
  if (rest.startsWith(',')) rest = rest.slice(1);
  if (!/^\s/.test(rest)) return null;
  return rest.trim();
}

interface QualifiedMatch { work: Work; qualifier: string; column: string; line: number | null; }

// Every work-qualified match across every work and every qualifier kind
// (abbr, slug, full title) — a work is tried under all three so "EN
// 1094a15", "nicomachean-ethics 1094a15", and "Nicomachean Ethics 1094a15"
// all resolve the same way. Case-insensitive throughout, matching the
// forgiving posture citation.ts's own jump-layer grammars (dk's lenient
// input regexes) already take for hand-typed input — the strict-canonical
// posture is reserved for spine data, never a reader's raw keystrokes.
function workQualifiedMatches(raw: string): QualifiedMatch[] {
  const matches: QualifiedMatch[] = [];
  for (const work of WORKS) {
    for (const qualifier of [work.abbr, workSlug(work), work.title]) {
      const remainder = matchQualifier(raw, qualifier);
      if (remainder == null) continue;
      const loc = schemeFor(work.id).parseLocation(remainder);
      if (loc) matches.push({ work, qualifier, column: loc.column, line: loc.line });
    }
  }
  return matches;
}

function stageWorkQualified(
  raw: string,
  index: CitationIndex | undefined,
): Resolution | AmbiguousResolution | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const matches = workQualifiedMatches(trimmed);
  if (matches.length === 0) return null;

  // A qualifier that is itself a prefix of a LONGER qualifier should never
  // let the shorter, less specific match compete with the longer, more
  // specific one naming the same locus. Keep only the longest-qualifier
  // match(es); dedupe by work so a single work matching under two qualifier
  // kinds of the same length counts once (abbr/slug/title are always
  // distinct lengths for one work, so that dedupe never collapses two
  // DIFFERENT works' matches into one).
  //
  // Distinct works sharing a qualifier is NOT rare: 19 works in the
  // registry are titled "Fragments" and 19 "Testimonia" (the DK
  // collections). "Fragments B1" reaches this stage with many same-length
  // matches from different works — a genuine ambiguity, not a bug. The
  // `longest.size === 1` check below is what catches it: it fails, and the
  // branch after it returns an AmbiguousResolution listing every claimant
  // in registry order, exactly like any other stage's ambiguity.
  const maxLen = Math.max(...matches.map((m) => m.qualifier.length));
  const longest = new Map(
    matches.filter((m) => m.qualifier.length === maxLen).map((m) => [m.work.id, m]),
  );

  if (longest.size === 1) {
    const m = [...longest.values()][0];
    return { workId: m.work.id, column: m.column, line: m.line, bookN: computeBookN(m.work.id, m.column, m.line, index) };
  }

  // Two different works' qualifiers tie at the same length and both parsed
  // a locus out of the same remainder — never guess which was meant.
  const sorted = [...longest.values()].sort((a, b) => registryOrder(a.work.id) - registryOrder(b.work.id));
  return {
    candidates: sorted.map((m) => ({
      workId: m.work.id,
      column: m.column,
      line: m.line,
      bookN: computeBookN(m.work.id, m.column, m.line, index),
    })),
  };
}

// ── Stage 2: parseDkFullCitation (citation.ts, unchanged) ──────────────────

// The DK/Bekker homograph guard (see module doc comment): a DK citation
// typed with a space between chapter and series letter collapses,
// whitespace stripped, to the exact string a Bekker/Busse bare column(+line)
// citation uses. When that collapsed form is ALSO a real column in the
// injected index, this stage can't silently prefer the DK reading — it
// returns both. `parseBareColumn`/`resolveFromIndex` are stage 3's own
// helpers (defined below); reused here rather than duplicated, since this
// IS a bare-column lookup once the input is collapsed.
function stageDkFull(
  raw: string,
  index: CitationIndex | undefined,
): Resolution | AmbiguousResolution | null {
  const full = parseDkFullCitation(raw);
  if (!full) return null;
  const dkResolution: Resolution = {
    workId: full.workId,
    column: full.column,
    line: full.line,
    bookN: computeBookN(full.workId, full.column, full.line, index),
  };

  if (index) {
    const collapsed = parseBareColumn(raw);
    if (collapsed) {
      const indexHit = resolveFromIndex(index, collapsed.column, collapsed.line);
      if (indexHit) {
        const indexCandidates: CitationCandidate[] = isAmbiguous(indexHit)
          ? indexHit.candidates
          : [indexHit];
        return { candidates: [dkResolution, ...indexCandidates] };
      }
    }
  }

  return dkResolution;
}

// ── Stage 3: bare column(+line) against the cross-corpus index ─────────────

// Mirrors citation.ts's private COLUMN_RE/REF_RE (the column/ref grammar
// bekker and busse both share — digits + a single a-e side letter,
// optionally followed by a run-together line number, e.g. "1094a",
// "1094a15", busse "1a5"). Duplicated here rather than exported from
// citation.ts because this router applies it ONLY to a bare, unqualified
// citation being looked up in the cross-corpus index — a context this
// module owns, not a per-work scheme concern citation.ts's own contract
// should grow a seam for.
const BARE_COLUMN_RE = /^(\d+)([a-e])$/;
const BARE_REF_RE = /^(\d+)([a-e])\.?(\d+)$/;

function parseBareColumn(raw: string): { column: string; line: number | null } | null {
  const norm = raw.trim().toLowerCase().replace(/\s+/g, '');
  if (!norm) return null;
  if (BARE_COLUMN_RE.test(norm)) return { column: norm, line: null };
  const m = BARE_REF_RE.exec(norm);
  if (!m) return null;
  return { column: m[1] + m[2], line: Number(m[3]) };
}

// Resolves a parsed bare column(+line) against the index's per-column entry
// list, which may name more than one work (the index carries every
// bekker/busse work's columns, and two different works CAN coincidentally
// use the same column string — most visibly two busse works each starting
// their own pagination at "1a"). Ambiguity policy (plan): filter by line
// containment (a line that falls inside exactly one candidate work's
// lo/hi span settles it even when the raw column string is shared), THEN
// registry order — but registry order here is a SORT for the reported
// candidates, never a silent pick: a residual tie across different works
// after containment filtering is returned as an AmbiguousResolution, not
// guessed at.
function resolveFromIndex(
  index: CitationIndex,
  column: string,
  line: number | null,
): Resolution | AmbiguousResolution | null {
  const entries = index[column];
  if (!entries || entries.length === 0) return null;

  const byWork = new Map<string, { book: number; lo: number; hi: number }[]>();
  for (const e of entries) {
    const list = byWork.get(e.work) ?? [];
    list.push({ book: e.book, lo: e.lo, hi: e.hi });
    byWork.set(e.work, list);
  }

  let workIds = [...byWork.keys()];

  // Line containment narrows the candidate set only WITHIN one citation
  // scheme. Across schemes (the live case: Categories' Bekker "1a" and
  // Isagoge's Busse "1a" are unrelated numbering systems that happen to
  // print the same column string), a line falling inside one work's span
  // and outside the other's says nothing about which scheme the reader
  // meant — narrowing there would be a guess dressed up as containment.
  // Same-scheme containment (two Bekker works sharing a split page, e.g.
  // Posterior Analytics ending 100a17 where Topics begins 100a18) stays a
  // real, valid narrowing signal.
  const schemesInvolved = new Set(workIds.map((w) => schemeFor(w).id));
  if (schemesInvolved.size === 1 && workIds.length > 1 && line != null) {
    const contained = workIds.filter((w) => byWork.get(w)!.some((e) => line >= e.lo && line <= e.hi));
    if (contained.length >= 1) workIds = contained;
  }

  if (workIds.length === 1) {
    const workId = workIds[0];
    return { workId, column, line, bookN: computeBookN(workId, column, line, index) };
  }

  const sorted = [...workIds].sort((a, b) => registryOrder(a) - registryOrder(b));
  return {
    candidates: sorted.map((workId) => ({
      workId,
      column,
      line,
      bookN: computeBookN(workId, column, line, index),
    })),
  };
}

function stageBareColumn(
  raw: string,
  index: CitationIndex | undefined,
): Resolution | AmbiguousResolution | null {
  if (!index) return null;
  const parsed = parseBareColumn(raw);
  if (!parsed) return null;
  return resolveFromIndex(index, parsed.column, parsed.line);
}

// ── Stage 4: contextWorkId fallback ─────────────────────────────────────────

// Byte-identical in behavior to BekkerJump.svelte's `go()`: parse `raw`
// against the SAME work's own scheme, with no cross-work resolution at all.
// (`schemeFor` already defaults an unregistered work id to bekker — see its
// own doc comment — so an unknown `contextWorkId` behaves exactly as it
// does in the reader jump box today, not as a new failure mode this router
// introduces.)
function stageContextFallback(
  raw: string,
  contextWorkId: string | undefined,
  index: CitationIndex | undefined,
): Resolution | null {
  if (!contextWorkId) return null;
  const loc = schemeFor(contextWorkId).parseLocation(raw);
  if (!loc) return null;
  return {
    workId: contextWorkId,
    column: loc.column,
    line: loc.line,
    bookN: computeBookN(contextWorkId, loc.column, loc.line, index),
  };
}

// ── Entry point ──────────────────────────────────────────────────────────

export function resolveCitation(
  raw: string,
  opts: { index?: CitationIndex; contextWorkId?: string } = {},
): Resolution | AmbiguousResolution | null {
  const { index, contextWorkId } = opts;

  const qualified = stageWorkQualified(raw, index);
  if (qualified) return qualified;

  const dk = stageDkFull(raw, index);
  if (dk) return dk;

  const bare = stageBareColumn(raw, index);
  if (bare) return bare;

  return stageContextFallback(raw, contextWorkId, index);
}
