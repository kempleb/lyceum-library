// DK cross-reference links (John, 2026-09-27 ruling): Diels-Kranz's own
// Greek apparatus is full of bracketed cross-references to OTHER fragments/
// testimonia — "[B 10]" (this author's own fragment B10), "[31 B 17]"
// (chapter 31 = Empedocles, fragment B17), "[vgl. B 91. 12]" ("compare"
// B91 AND B12), "[ B 30]" (a stray leading space DK itself prints). The
// ruling: keep every bracket exactly as DK prints it, but make each
// fragment/testimonium reference INSIDE it a link to that item's place in
// the reader. Nothing is removed or reworded, and no new visible text is
// added — only an `<a>` wraps the reference's own printed characters.
//
// This module is a pure parser (`findDkCrossRefs`) plus a pure resolver
// (`resolveDkCrossRef`) and a pure LineRenderPart splicer
// (`applyDkCrossRefs`) that turns a resolved reference into a link without
// disturbing the Greek word click-lookup machinery in shared/lib/speakers.ts
// (lineRenderParts) — see Reader.svelte's `greekToks` snippet, the only
// call site.
//
// ── Corpus survey (all 39 DK works' Greek text, 2026-09-27) ────────────────
// Every bracket in the corpus was scanned for a series-letter+number shape.
// The genuine DK cross-references found all take one of these forms:
//   - the WHOLE bracket is the reference: "[B 10]", "[A 21]", "[C 1]",
//     "[ B 30]" (stray leading space), "[B27]" (no space before the number).
//   - a chapter number precedes the series letter: "[31 B 17]", "[28 A 21]".
//   - a "compare/see" connector precedes it: "vgl."/"Vgl." ("compare"),
//     "s." ("see"), "z." ("zu", "at"), "nach"/"hinter"/"folgt" ("after"/
//     "behind"/"follows"), or "=" — wherever one of these appears, whatever
//     immediately follows it is a reference, regardless of what precedes
//     the connector itself: "[Emped., vgl. 31 A 6]", "[fr. 65; vgl. A 19]".
//   - a second (or third) reference chained onto the first with ". ": "[vgl.
//     B 91. 12]" -> B91 and B12 (the second inherits the first's chapter AND
//     series letter unless it names its own, e.g. "[31 A 69a. B 94]" ->
//     31A69a and 31B94).
//   - a reference immediately after a ";" inside the bracket (a second,
//     unconnected citation DK adds after a semicolon): "[fr. 173 Us.; 68 A
//     9]" -> only 68A9 links; "fr. 173 Us." is Usener's own numbering, not a
//     DK item.
//   - a bare name (no title, no locus, nothing else) at the very start of
//     the bracket, naming another author, immediately before an EXPLICIT
//     chapter number: "[Heraklit, 22 B 20]", "[Pherekydes 7 A 1]" -- a
//     genuine DK annotation naming the author the reference belongs to.
//     The explicit chapter number is what tells this apart from the "de
//     anima A 2" false positive below, which never has a chapter number at
//     all -- see isValidStart's own doc for the guard.
//
// Deliberately NOT linked (reported, not treated as a parser bug):
//   - a bare letter+number preceded by anything else -- a work title, or a
//     citation with no recognized connector AND no chapter number of its
//     own: "[de anima A 2. 405a 19]" (Aristotle's own book-A chapter-2, not
//     a DK reference — 5 occurrences), "[XVII A 681 K.]" (a Kühn-edition
//     volume/page), "[Hom. B 273]" (a Homer book-B line), "[Soph. 237 A
//     vgl. 258D]" (Plato's Stephanus page 237, section A -- note "vgl. B 7"
//     appearing elsewhere in a SIBLING bracket to the same passage DOES
//     link, since "vgl." directly precedes it there).
//   - a page/line locus or trailing word after a reference's own number:
//     "[B 12 II 38, 8]", "[B 4 Ende]", "[31 B 17, 32]" -- only the
//     reference's own letter+number is linked; the rest renders unchanged.
//   - a RANGE ("[B 78—81]", "[68 C 2—6]", "[68 B 298b—299h]", "[s. 60 A
//     1—5]"): there is no single citable target for a range, so none of it
//     links (9 occurrences corpus-wide).
//   - a bare number with no series letter at all ("[428]", "[500—497]"): DK
//     prints these for dates/page numbers; only a lettered reference is
//     ever a DK item.
//   - a 'C' series reference ("[vgl. C 5]", "[31 C 1]"): parsed like any
//     other reference, but no work in this library carries a 'C' series (DK
//     itself uses it rarely, for "Nachahmung"/imitation texts this corpus
//     doesn't carry as separate works), so it always resolves to no work
//     and renders as plain text — not a parser gap.

import type { LineRenderPart } from './speakers';
import { workByDkCitation, workPath } from './works';

export type DkRefKind = 'A' | 'B' | 'C';

// One cross-reference found inside a DK Greek line's raw text. `start`/`end`
// are character offsets into that same text (never into a bracket's own
// inner substring), spanning exactly the reference's own printed
// characters (e.g. "B 10", "31 B 17") -- never the surrounding "[" "]" or
// connector word, and never a trailing locus/word.
export interface DkCrossRef {
  start: number;
  end: number;
  /** Absent means "this author's own chapter" -- see the module doc. */
  chapter?: number;
  kind: DkRefKind;
  /** e.g. "10", "84a" -- DK's own lowercase suffix-letter convention. */
  number: string;
}

// A DK bracket, matched exactly as `check-dk-structure.mjs` and the source-
// citation expansion pipeline already do: no nesting occurs in this corpus.
const BRACKET_RE = /\[([^[\]]*)\]/g;

// A single reference's own grammar: an optional chapter number (Arabic
// digits only -- a Roman numeral like "XVII" never matches, which is what
// keeps a Kühn-edition volume citation like "[XVII A 681 K.]" from being
// mistaken for a chapter prefix), then a series letter, then its number
// with DK's optional single lowercase suffix letter. A space may separate
// each part ("A 21", "B 6 b") or not ("B27", "B5b") -- DK prints both.
// The suffix must not be followed by a(nother) digit: "[A 86 i 302, 11ff]"
// is the number 86 followed by a stray lowercase volume numeral "i" (DK
// elsewhere prints this "I 302, 22", uppercase -- this one instance is a
// transcription slip) and " 302" is its page, never a real fragment suffix
// "86i" -- a genuine suffix ("89a", "115a") is never itself followed by a
// number.
const SUFFIX = /(?:\s?([a-z])(?![a-z])(?!\s?[0-9]))?/.source;
const REF_RE = new RegExp(`(?:(\\d{1,3})\\s+)?([ABC])\\s?(\\d{1,4})${SUFFIX}`, 'g');

// A chained reference immediately after ". " -- mirrors REF_RE's own
// grammar (an optional new chapter number, an optional series letter, then
// the number+suffix), so a chain step can be a WHOLE fresh citation, not
// just a bare continuation number: "s. 82 A 7. 85 A 2" chains 85A2 (a new
// chapter AND kind, not chapter-82's own fragment "85"), "31 A 69a. B 94"
// chains 31B94 (a new kind, chapter inherited), "vgl. B 91. 12" chains B12
// (chapter AND kind both inherited from whichever ref precedes it in the
// chain). A chapter number is only ever read here when followed by
// whitespace (matching REF_RE) -- "33, 3" (a trailing locus, not a new
// chapter) never satisfies that, so it falls through to the bare-number
// form instead.
const CHAIN_RE = new RegExp(`^\\.\\s*(?:(\\d{1,3})\\s+)?(?:([ABC])\\s?)?(\\d{1,4})${SUFFIX}`);

// The "compare/see" connectors DK's apparatus uses before a reference that
// has no chapter/bracket-start context of its own -- see the module doc's
// corpus survey. Checked as a literal suffix of the text preceding the
// candidate match, so case matters (both "vgl." and "Vgl." occur; "S."
// capitalized never does in this corpus).
const CONNECTORS = ['vgl.', 'Vgl.', 's.', 'z.', 'nach', 'hinter', 'folgt', '='];

// True at a range's start position: the era's OWN dash convention is an
// em-dash directly against the number, with no space ("B 78—81" — never
// "B 78 —81"). A range names no single citable item, so the whole
// candidate is skipped entirely (see the module doc's "deliberately not
// linked" list) -- it is not merely a trailing locus (that's handled by
// simply not extending the match past the reference's own number).
function isRangeAt(text: string, pos: number): boolean {
  return text[pos] === '—' && /[0-9]/.test(text[pos + 1] ?? '');
}

// A bare name (one or more space-separated words of letters only, no
// digits or punctuation) filling the WHOLE of `text` -- used only to
// recognize "Heraklit, 22 B 20" / "Pherekydes 7 A 1"'s own shape: a named
// author gloss with nothing else before it in the bracket.
const NAME_RE = /^\p{L}+(?:\s\p{L}+)*$/u;

// True when `pos` (the start of a candidate reference match) is a
// legitimate place for a reference to begin: the very start of the
// bracket's own content, immediately after a ";" (DK's own clause
// separator inside a bracket), immediately after one of CONNECTORS
// (wherever it occurs -- what precedes the connector itself is never
// checked, so "Emped., vgl. 31 A 6" links "31 A 6" regardless of "Emped.,"),
// or -- only when the candidate carries its OWN explicit chapter number
// (`hasChapter`) -- immediately after a bare name, with an optional comma,
// at the very start of the bracket ("[Heraklit, 22 B 20]", "[Pherekydes 7
// A 1]": genuine DK annotations naming another author before the chapter).
// The `hasChapter` guard is what keeps this from also admitting a false
// positive like "[de anima A 2. 405a 19]" or "[Hom. B 273]": neither
// captures a chapter number to begin with (no digit run precedes the
// series letter there), so the name-prefix branch never runs for them --
// see the module doc's corpus survey. Otherwise, only whitespace is
// skipped when looking back; anything else (a work title, a citation with
// no chapter number) fails this check -- see the module doc's
// "deliberately not linked" list for why that's a feature, not a gap.
function isValidStart(text: string, pos: number, hasChapter: boolean): boolean {
  let j = pos;
  while (j > 0 && text[j - 1] === ' ') j -= 1;
  if (j === 0) return true;
  if (text[j - 1] === ';') return true;
  const before = text.slice(0, j);
  if (CONNECTORS.some((c) => before.endsWith(c))) return true;
  if (!hasChapter) return false;
  let k = j;
  if (text[k - 1] === ',') k -= 1;
  while (k > 0 && text[k - 1] === ' ') k -= 1;
  return k > 0 && NAME_RE.test(text.slice(0, k));
}

// Find every DK cross-reference in a Greek line's raw text (the full line,
// not a single bracket's inner text -- offsets are into `text` itself, so a
// caller composing render parts from the same `text` string needs no
// translation). Pure: no work lookups, no rendering. See the module doc's
// corpus survey for the grammar this covers, and its "deliberately not
// linked" list for what it doesn't.
export function findDkCrossRefs(text: string): DkCrossRef[] {
  const refs: DkCrossRef[] = [];
  let bm: RegExpExecArray | null;
  BRACKET_RE.lastIndex = 0;
  while ((bm = BRACKET_RE.exec(text))) {
    const inner = bm[1];
    const base = bm.index + 1; // offset of `inner`'s char 0 within `text`
    REF_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = REF_RE.exec(inner))) {
      const start = m.index;
      if (!isValidStart(inner, start, Boolean(m[1]))) continue;
      const chapter = m[1] ? Number(m[1]) : undefined;
      const kind = m[2] as DkRefKind;
      let end = m.index + m[0].length;
      if (isRangeAt(inner, end)) continue; // whole candidate is a range -- skip, no chain either
      const number = m[3] + (m[4] ?? '');
      refs.push({ start: base + start, end: base + end, chapter, kind, number });
      // Chain continuations ("B 91. 12", "31 A 69a. B 94", "s. 82 A 7. 85 A
      // 2"): each inherits the chapter/kind of the chain's own PREVIOUS
      // step (not always the first reference) unless it names its own.
      let curChapter = chapter;
      let curKind = kind;
      let pos = end;
      for (;;) {
        const cm = CHAIN_RE.exec(inner.slice(pos));
        if (!cm) break;
        const cend = pos + cm[0].length;
        if (isRangeAt(inner, cend)) break;
        if (cm[1]) curChapter = Number(cm[1]);
        if (cm[2]) curKind = cm[2] as DkRefKind;
        // cm[0] is the WHOLE chain match, including the leading ". " (and,
        // when present, a new chapter number and/or renamed kind letter)
        // -- the link itself starts at the first digit-or-series-letter,
        // never at the separator.
        const refStartRel = cm[0].search(/[ABC0-9]/);
        refs.push({ start: base + pos + refStartRel, end: base + cend, chapter: curChapter, kind: curKind, number: cm[3] + (cm[4] ?? '') });
        pos = cend;
        // REF_RE's own lastIndex must not re-match characters this chain
        // just consumed.
        REF_RE.lastIndex = pos;
      }
      if (pos > end) REF_RE.lastIndex = pos;
    }
  }
  return refs;
}

// The DK column token a reference names, e.g. "B10", "A84a" -- matches this
// codebase's canonical DK_COLUMN_RE (citation.ts) exactly: series upper,
// suffix lower, no leading-zero normalization.
export function dkCrossRefColumn(ref: DkCrossRef): string {
  return `${ref.kind}${ref.number}`;
}

// The work a reference names, or undefined when it doesn't resolve --
// either because it's chapter-less and the CURRENT work isn't itself a
// (known-chapter) DK work, its kind is 'C' (no 'C'-series work exists in
// this library -- see the module doc), or the (chapter, kind) pair simply
// names no registered work. `currentChapter` is the CURRENT work's own
// `citation.dkChapter` (undefined for a non-dk work, which correctly makes
// every chapter-less reference unresolvable too).
export function dkCrossRefWorkId(ref: DkCrossRef, currentChapter: number | undefined): string | undefined {
  const chapter = ref.chapter ?? currentChapter;
  if (chapter == null || ref.kind === 'C') return undefined;
  return workByDkCitation(chapter, ref.kind)?.id;
}

export interface DkCrossRefTarget {
  workId: string;
  column: string;
  href: string;
}

// Resolve a reference to a concrete link target, or null when it should
// render as plain text: an unknown chapter/series (dkCrossRefWorkId
// returns undefined), or a column that doesn't exist in the resolved work
// (`hasColumn` -- backed by that work's own columns.json; the caller
// decides how/when to have it loaded, this stays a pure decision function).
//
// The href's fragment is `col-<column>` -- the segment's own DOM id
// (Reader.svelte's `id="col-{seg.column}"`), NOT the bare citation
// (formatCite's "B10") a jump CONTROL puts in `?loc=`. Bekker/dk jump
// controls (BekkerJump.svelte, CommandPalette.svelte) always route through
// `?loc=`, which Reader.svelte parses at mount and only THEN falls back to
// a bare-hash-matches-a-`col-`-id lookup client-side; a plain `<a href>`
// like this one has no such runtime fallback to lean on for a STATIC
// checker, and scripts/check-links.mjs's own `fragmentResolves` only
// accepts an exact id or (case-insensitively) a `col-`-prefixed one --
// the same format scripts/emit-lyceum-manifest.mjs already emits for the
// Lyceum partner catalog's `navigation.loci` hrefs. Using it here means
// build:public's check-links gate passes on this link with no special
// case, and the link still resolves correctly at runtime (a `col-B10`
// hash matches `document.getElementById(hash)` on Reader.svelte's very
// first lookup, same-page or cross-page).
export function resolveDkCrossRef(
  ref: DkCrossRef,
  currentChapter: number | undefined,
  hasColumn: (workId: string, column: string) => boolean,
): DkCrossRefTarget | null {
  const workId = dkCrossRefWorkId(ref, currentChapter);
  if (!workId) return null;
  const column = dkCrossRefColumn(ref);
  if (!hasColumn(workId, column)) return null;
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return { workId, column, href: `${base}${workPath(workId)}#col-${column}` };
}

// A resolved (or deliberately unresolved) span to splice into a line's
// render parts -- `href: null` means "leave this span as plain text" (an
// unresolved reference is not an error; see resolveDkCrossRef's doc).
export interface DkCrossRefSpan {
  start: number;
  end: number;
  href: string | null;
}

// A render part for a linked reference -- alongside speakers.ts's ordinary
// 'text'/'token'/'speaker' parts. Additive: Reader.svelte's `greekToks`
// snippet is the only renderer that needs to know about it, and every
// other LineRenderPart consumer (splitWrapLine, other works' rendering)
// never sees one, since `applyDkCrossRefs` is only ever called for a
// dk-scheme work's own lines.
export type DkLinkPart = { kind: 'dklink'; text: string; href: string };
export type DkRenderPart = LineRenderPart | DkLinkPart;

// Splice resolved reference spans into a line's already-built render parts
// (lineRenderParts' output) without disturbing anything else: a 'token'
// part (a clickable Greek word) never overlaps a reference span (DK's
// cross-references are pure apparatus, never inside a Greek word) and is
// passed through unchanged; a 'speaker' part is zero-width (no text of its
// own) and passed through unchanged; a 'text' part -- the only kind a
// reference can fall inside -- is trimmed/split around each span it
// contains, in place of the whole part's original text. `spans` must be
// sorted by `start` and given in the SAME coordinate space as `text` (the
// same string `parts` was built from) -- e.g. findDkCrossRefs's own output,
// resolved. A span with `href: null` still consumes its characters (so
// they aren't duplicated) but renders as an ordinary 'text' part.
//
// A span may straddle more than one adjacent 'text' atom (lineRenderParts
// emits one atom per non-lexical token/gap, so "B" and "10" can be
// separate atoms either side of a literal space) -- handled by tracking a
// running char pointer across the WHOLE parts array (reconstructed from
// `text`, since concatenating every non-'speaker' part's own text
// reproduces `text` exactly, by lineRenderParts' own contract) rather than
// processing each part in isolation.
export function applyDkCrossRefs(
  text: string,
  parts: readonly LineRenderPart[],
  spans: readonly DkCrossRefSpan[],
): DkRenderPart[] {
  if (!spans.length) return parts as DkRenderPart[];
  const out: DkRenderPart[] = [];
  // A resolved span that straddles two adjacent 'text' atoms (e.g. "B" and
  // "10" either side of a literal space, both non-lexical apparatus atoms —
  // see lineRenderParts) would otherwise emit two separate 'dklink' pieces
  // with the same href; merged into one so the printed reference is a
  // single link, not several abutting ones.
  const pushLink = (linkText: string, href: string) => {
    const last = out[out.length - 1];
    if (last && last.kind === 'dklink' && last.href === href) last.text += linkText;
    else out.push({ kind: 'dklink', text: linkText, href });
  };
  let ptr = 0;
  let si = 0;
  for (const part of parts) {
    if (part.kind !== 'text') {
      // 'token' (never overlaps a span) and 'speaker' (zero-width) both
      // pass through unchanged; only a 'token' advances the pointer.
      if (part.kind === 'token') ptr += part.text.length;
      out.push(part);
      continue;
    }
    const start = ptr;
    const end = ptr + part.text.length;
    ptr = end;
    let cursor = start;
    while (si < spans.length && spans[si]!.start < end) {
      const span = spans[si]!;
      const rs = Math.max(span.start, start);
      const re = Math.min(span.end, end);
      if (rs > cursor) out.push({ kind: 'text', text: text.slice(cursor, rs) });
      if (span.href) pushLink(text.slice(rs, re), span.href);
      else out.push({ kind: 'text', text: text.slice(rs, re) });
      cursor = re;
      if (span.end <= end) si += 1;
      else break; // this span continues into the next 'text' part
    }
    if (cursor < end) out.push({ kind: 'text', text: text.slice(cursor, end) });
  }
  return out;
}
