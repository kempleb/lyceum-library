// Citation-scheme contract — the frontend twin of the pipeline's
// pipeline/reader_pipeline/scheme.py. A *citation scheme* is the reference
// system a work is cited by: Bekker pages for Aristotle ("1094a15"), Busse/CAG
// pages for Porphyry's Isagoge ("1a5" — synthetic single-side pages), or
// Stephanus pages for Plato ("17a"). Every scheme-conditional in the reader
// should dispatch on the `CitationScheme` returned by `schemeFor(work)`
// instead of scattering `=== 'busse'` / `=== 'stephanus'` string tests.
//
// Two distinct grammars matter, and this module deliberately keeps them
// separate:
//
//   * a CITATION string — the form a scholar writes/copies: column and line
//     run together with no separator ("1097a15"), or just the column when the
//     scheme has no user-facing lines ("17a"). `formatCitation` produces this;
//     it's what the scroll-spy hash, copy-citation, and resume storage show.
//   * a LOCATION string — the `?loc=` query grammar: a column, optionally
//     followed by `:` and a line ("1097a:15" or "17a:12"). This is a routing
//     detail, not something a reader is meant to read as a citation, so it
//     keeps the line internally (DOM anchors still need it to scroll to an
//     exact Greek line) even for a lineless scheme. `parseLocation` reads
//     this grammar; nothing in this module composes it with a line for a
//     lineless scheme, because nothing upstream can ever hand one a line for
//     one (see `hasUserFacingLines` below).
//
// The known reader bug this replaces: splitting `?loc=` on ':' unconditionally
// produced `L17a-undefined` for a column-only value. `parseLocation` always
// returns a `line` of `null` rather than `NaN`/`undefined` when none is given,
// so a caller can branch on `line == null` to target the column-level anchor
// instead of a garbled line-level one.

import { getWork, workByDkChapterNoSeries, workByDkCitation } from './works';

export type SchemeId =
  | 'bekker'
  | 'busse'
  | 'stephanus'
  | 'book-section'
  // Flat, bookless chapter-integer grammar ("5") — Epictetus' Enchiridion.
  | 'section'
  | 'dk'
  // Book.line dotted grammar for continuous verse with a book axis
  // (Lucretius' DRN) — see makeVerseLineScheme below.
  | 'verse-line'
  // Letter.section dotted grammar (Seneca's Epistulae Morales) — see
  // makeDottedScheme's `letter` entry in SCHEMES below.
  | 'letter'
  // Registered but not yet implemented (see makeStubScheme below): using
  // this is a loud runtime error, never silent bekker behavior.
  | 'ennead';

export interface ParsedLocation {
  column: string;
  line: number | null;
  // True when `column`'s lineref half is the range form ("1094-1101") — a
  // spine-internal token reserved for a declared editorial lacuna
  // (verse-line only, design memo docs/wave2-latin-design.md §3.2). Absent/
  // undefined for every other scheme and for a verse-line non-range column.
  // Whether an *input* range is actually accepted (matches a manifest-
  // declared lacuna) is a later gate, out of scope here — this field only
  // classifies the shape.
  isRange?: boolean;
}

export interface CitationScheme {
  readonly id: SchemeId;
  // Bare-column token grammar shared by every scheme (mirrors scheme.py's
  // `_COLUMN_RE` — Bekker's real sides are a/b and Busse's is a-only, but the
  // grammar itself accepts a-e for all three so one regex serves them all;
  // real membership is enforced by the columns.json lookup, not this regex).
  readonly columnRegex: RegExp;
  // Whether individual line numbers within a column are meaningful,
  // user-facing citation targets. False only for stephanus — Plato is cited
  // page+letter only; lines exist in the underlying TEI but are editorial.
  readonly hasUserFacingLines: boolean;
  // Whether a work in this scheme nests a section div inside its page div
  // (mirrors scheme.py's `Scheme.has_sections`): true for stephanus (page +
  // a-e section letter) and book-section (book + numbered section) — both
  // replace chapters.json with sections.json as the reader's outline-nav
  // source, since these works have no chapter division. False for bekker,
  // busse, and the unimplemented stub schemes. The reader dispatches on this
  // instead of an `=== 'stephanus'` string test wherever the behavior is
  // really "this scheme has sections", not "this scheme is Stephanus" —
  // see ReaderShell.astro/Landing.astro's `hasSectionOutline`.
  readonly hasSections: boolean;
  // Placeholder text for a citation-jump input box.
  readonly jumpPlaceholder: string;
  // Human label for the jump box / error copy ("Bekker citation", "Stephanus page").
  readonly label: string;
  // Parse + normalize a bare column token ("34b", "1097A" -> "1097a"). Returns
  // null if it doesn't match this scheme's column grammar.
  parseColumnToken(raw: string): string | null;
  // Parse a `?loc=` value: a bare column, or column + line joined by ':' or
  // (for backward compatibility with hand-typed Bekker citations) run
  // together with an optional space/dot separator ("1097a15", "1097a.15").
  // A line component on a scheme with no user-facing lines is invalid input
  // (there is no such thing as "line 12 of Stephanus page 34b"), not a value
  // to silently drop — this rejects rather than truncates it.
  parseLocation(raw: string): ParsedLocation | null;
  // Render the citation string a reader sees: "1097a15" (line given, scheme
  // has lines), "1097a" (no line, or a lineless scheme where `line` is
  // ignored regardless of what's passed).
  formatCitation(column: string, line?: number | null): string;
  // The book that owns a column, when it's recoverable from the column
  // string alone — true only for a dotted scheme (book-section: "4.23"'s
  // book IS its dotted prefix, "12.34" -> 12). Null for every other scheme
  // (bekker, busse, stephanus), whose column can be shared/split across two
  // books (a book that starts mid-column) and so can only be resolved
  // against columns.json — see data.ts's resolveBekker. A citation-jump
  // caller (CommandPalette, BekkerJump) checks this first and only falls
  // back to a fetchColumns/resolveBekker lookup when it returns null, so a
  // dotted-scheme work's jump never depends on columns.json being fetched.
  bookFromColumn(column: string): number | null;
}

// Shared column/ref grammar (mirrors scheme.py's `_COLUMN_RE` / `_REF_RE`):
// digits + a single letter a-e, optionally followed by a line number.
const COLUMN_RE = /^(\d+)([a-e])$/;
const REF_RE = /^(\d+)([a-e])\.?(\d+)$/;

// book-section's dotted grammar (mirrors scheme.py's `_DOTTED_COLUMN_RE`):
// book.section, e.g. Marcus Aurelius "4.23", Diogenes Laertius "7.85". No
// [a-e] letter axis at all, and (per `hasUserFacingLines: false` below) no
// legacy concatenated ref form either — "4.23" already fully identifies the
// column, so there's nothing unambiguous to concatenate a line onto.
const DOTTED_COLUMN_RE = /^(\d+)\.(\d+)$/;

// verse-line's grammar (Lucretius' DRN, continuous verse with a book axis —
// design memo docs/wave2-latin-design.md §3.1-3.2): the citable unit is
// book.line; book is the page axis (book-section's book level, reused), and
// the line — the "column-token grammar within a book" — is a bare number
// with an optional single lowercase suffix letter (the observed "47a"
// insertions), no leading-zero normalization (same rationale as dk's
// DK_COLUMN_RE below: PHI has none, so a literal digit run is preserved
// rather than defensively stripped — see the "047" case in citation.test.ts
// and this module's parity with scheme.py's identical _VERSE_LINE_RE).
const VERSE_LINE_RE = /^([0-9]+)([a-z]?)$/;
// A lacuna range token (§3.2): valid ONLY as a spine-internal token for an
// editor-marked gap div (n="1094-1101"), never general citation input a
// reader types — the acceptance-against-a-declared-lacuna policy is a LATER
// gate (preflight), out of scope for this scheme-grammar layer, which only
// parses and classifies it (see ParsedLocation.isRange and
// isVerseLineRange below).
const VERSE_LINE_RANGE_RE = /^([0-9]+)([a-z]?)-([0-9]+)([a-z]?)$/;
// The full dotted column: book '.' lineref, where lineref is either form
// above — mirrors DOTTED_COLUMN_RE's shape but with a richer second
// component. Lineless (hasUserFacingLines: false — the line IS the column,
// §3.1/§3.4), so the same regex serves as both the column and the (unused)
// ref grammar, same as book-section.
const VERSE_LINE_COLUMN_RE = /^([0-9]+)\.([0-9]+[a-z]?(?:-[0-9]+[a-z]?)?)$/;

// dk's grammar (mirrors scheme.py's `_DK_COLUMN_RE`): a series letter (A
// testimonia / B fragments, canonical uppercase), a number (no leading-zero
// normalization), and an optional single lowercase suffix letter — "B30",
// "B84a", "A1a". The series letter lives IN the column token (see the
// module's dk section below for why): the citation a scholar writes IS
// "B30", so the scroll-spy hash/resume/copy-citation come out right for
// free, and preflight can assert spine-column-series == the work's declared
// series as a cheap wrong-file-exported gate.
const DK_COLUMN_RE = /^([AB])([0-9]+)([a-z]?)$/;
// A verse dk work's ref grammar (Parmenides): column + dot + line — the
// scholarly convention for fragment.line ("B8.34"), never concatenation
// ("B834" is ambiguous and does not exist in this grammar) and never
// book-section's colon (the dot IS the scholarly convention here).
const DK_VERSE_REF_RE = /^([AB])([0-9]+)([a-z]?)\.([0-9]+)$/;
// A no-series dk work's column grammar (mirrors scheme.py's
// `_DK_NO_SERIES_COLUMN_RE`): DK prints some chapters with NO A/B series
// letter at all (Pythagoras, DK 14 — cited "DK 14, 7", never "14 A7"). See
// `citation?.noSeries` in `schemeFor` below — the ONLY other per-work dk
// override seam besides `citation.lines`, and not composable with it (no
// chapter needing both has been observed). 2 capture groups (number,
// suffix) — deliberately NOT 3 like scheme.py's `_DK_NO_SERIES_COLUMN_RE`
// (which keeps an always-empty leading group to match `_DK_COLUMN_RE`'s
// (series, number, suffix) shape for its own refs.py/stage1_greek
// consumers): this side's only consumer, `canonicalNoSeriesColumn` below,
// never unpacks a 3-tuple, so there is nothing to keep a placeholder group
// in sync with. The "case-parity contract" scheme.py's own comment
// mentions is about canonicalization strictness ONLY, never capture-group
// count — see that comment's own clarification and citation.test.ts's
// capture-shape note test.
const DK_NO_SERIES_COLUMN_RE = /^([0-9]+)([a-z]?)$/;
const DK_NO_SERIES_INPUT_COLUMN_RE = /^([0-9]+)([A-Za-z]?)$/;

// `section`'s flat grammar (mirrors scheme.py's `_FLAT_COLUMN_RE`): a bare
// chapter integer, e.g. Epictetus' Enchiridion "5". No letter axis and no
// book prefix at all — the work is bookless (a single declared book), so
// there is nothing here for `bookFromColumn` to recover. The optional
// `-\d+` tail (Epicurus' Vatican Sayings) accepts the one compound "56-57"
// column the Arrighetti/TLG export carries — see scheme.py's matching
// comment for why it's one atomic token, not a range.
const FLAT_COLUMN_RE = /^(\d+)(?:-\d+)?$/;

function normalize(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, '');
}

function makeScheme(
  id: SchemeId,
  hasUserFacingLines: boolean,
  jumpPlaceholder: string,
  label: string,
): CitationScheme {
  function parseColumnToken(raw: string): string | null {
    const norm = normalize(raw);
    return COLUMN_RE.test(norm) ? norm : null;
  }

  function parseLocation(raw: string): ParsedLocation | null {
    const norm = normalize(raw);
    if (!norm) return null;

    // Bare column, e.g. "17a" or "1097a" — valid for every scheme.
    if (COLUMN_RE.test(norm)) return { column: norm, line: null };

    // "{column}:{line}" — the `?loc=` query grammar.
    const colon = norm.indexOf(':');
    if (colon !== -1) {
      const colPart = norm.slice(0, colon);
      const linePart = norm.slice(colon + 1);
      if (!COLUMN_RE.test(colPart) || !/^\d+$/.test(linePart)) return null;
      if (!hasUserFacingLines) return null; // no such thing as a lineless-scheme line
      return { column: colPart, line: Number(linePart) };
    }

    // Legacy concatenated citation form, e.g. "1097a15" / "1097a.15" — only
    // meaningful for a scheme with user-facing lines. For a lineless scheme
    // this is exactly the malformed "34b12" input that must be rejected, not
    // reinterpreted.
    if (!hasUserFacingLines) return null;
    const m = REF_RE.exec(norm);
    if (!m) return null;
    return { column: m[1] + m[2], line: Number(m[3]) };
  }

  function formatCitation(column: string, line?: number | null): string {
    if (hasUserFacingLines && line != null) return `${column}${line}`;
    return column;
  }

  // Not derivable here: a bekker/busse/stephanus column can be shared by two
  // books, so only a columns.json lookup (resolveBekker) can resolve it.
  function bookFromColumn(): number | null {
    return null;
  }

  return { id, columnRegex: COLUMN_RE, hasUserFacingLines, hasSections: false, jumpPlaceholder, label, parseColumnToken, parseLocation, formatCitation, bookFromColumn };
}

// A dotted-grammar scheme (book.section — currently only book-section; see
// DOTTED_COLUMN_RE). Kept as its own factory rather than contorting
// makeScheme: the two grammars don't share a column regex, and bekker/busse's
// legacy concatenated-ref form ("1097a15") relies on an unambiguous
// letter/digit boundary that a dotted token doesn't have (would "4.23" + line
// "5" be "4.235" or line 5 of section 23?), so that form simply doesn't exist
// here rather than being reinterpreted.
function makeDottedScheme(
  id: SchemeId,
  hasUserFacingLines: boolean,
  jumpPlaceholder: string,
  label: string,
): CitationScheme {
  function parseColumnToken(raw: string): string | null {
    const norm = normalize(raw);
    return DOTTED_COLUMN_RE.test(norm) ? norm : null;
  }

  function parseLocation(raw: string): ParsedLocation | null {
    const norm = normalize(raw);
    if (!norm) return null;

    // Bare column, e.g. "4.23" — valid for every dotted scheme, and (for
    // book-section, whose grammar bakes the book number into the column's
    // dotted prefix) all a caller needs to route to the right book page;
    // unlike stephanus there's no columns.json-style lookup step, just
    // `Number(column.split('.')[0])`.
    if (DOTTED_COLUMN_RE.test(norm)) return { column: norm, line: null };

    // "{column}:{line}" — the `?loc=` query grammar. No dotted scheme
    // currently has user-facing lines, so this always rejects today; kept
    // for parity with makeScheme's grammar against a future dotted scheme
    // that does.
    const colon = norm.indexOf(':');
    if (colon !== -1) {
      const colPart = norm.slice(0, colon);
      const linePart = norm.slice(colon + 1);
      if (!DOTTED_COLUMN_RE.test(colPart) || !/^\d+$/.test(linePart)) return null;
      if (!hasUserFacingLines) return null;
      return { column: colPart, line: Number(linePart) };
    }

    return null;
  }

  function formatCitation(column: string, line?: number | null): string {
    // A colon (not concatenation) separates a hypothetical line from a
    // dotted column, for the same ambiguity reason parseLocation has no
    // concatenated form.
    if (hasUserFacingLines && line != null) return `${column}:${line}`;
    return column;
  }

  // book-section's whole point: the book number IS the column's dotted
  // prefix (see the module doc comment and scheme.py's compose_column), so
  // no columns.json lookup is needed to recover it.
  function bookFromColumn(column: string): number | null {
    const m = DOTTED_COLUMN_RE.exec(normalize(column));
    return m ? Number(m[1]) : null;
  }

  return { id, columnRegex: DOTTED_COLUMN_RE, hasUserFacingLines, hasSections: false, jumpPlaceholder, label, parseColumnToken, parseLocation, formatCitation, bookFromColumn };
}

// Classifies a verse-line lineref (the part after the book dot, or a bare
// lineref/range token before a book is prefixed) as a declared-lacuna range
// or an ordinary line — design memo §3.2. Exported so a later manifest-
// declaration gate (out of scope here) can dispatch on it without
// re-deriving the grammar; mirrors scheme.py's `verse_line_kind`.
export function isVerseLineRange(lineref: string): boolean {
  return VERSE_LINE_RANGE_RE.test(lineref);
}

// The sort key for a SINGLE (non-range) verse-line lineref within a book:
// (int(number), suffix), so 47 < 47a < 48 and 99 < 100 (numeric, never
// lexicographic) — reuses dk's proven '' < 'a' < 'b' ordering (design memo
// §3.1). Exported for the later emit-time citation-order sort (§3.3);
// mirrors scheme.py's `verse_line_order_key` exactly. Throws for a range
// token (no single sort position — see isVerseLineRange) or a malformed one.
export function verseLineOrderKey(lineref: string): readonly [number, string] {
  const m = VERSE_LINE_RE.exec(lineref);
  if (!m) throw new Error(`not a verse-line token: ${lineref}`);
  return [Number(m[1]), m[2] ?? ''] as const;
}

// verse-line (Lucretius' DRN, Wave 2 Batch 2 — design memo
// docs/wave2-latin-design.md §3.1-3.4). Its own factory rather than reusing
// makeDottedScheme: book-section's dotted second component is a plain
// integer, but verse-line's lineref carries its own richer grammar (an
// optional single-letter suffix, and a range form reserved for declared
// lacunae — VERSE_LINE_RE/VERSE_LINE_RANGE_RE above), and (unlike every
// other scheme) its `?loc=` colon form is a genuine book/lineref split
// rather than a rejected-by-default line component, since verse-line has no
// separate line axis at all (hasUserFacingLines: false — the line IS the
// column).
function makeVerseLineScheme(): CitationScheme {
  function parseColumnToken(raw: string): string | null {
    const norm = normalize(raw);
    return VERSE_LINE_COLUMN_RE.test(norm) ? norm : null;
  }

  function parseLocation(raw: string): ParsedLocation | null {
    const norm = normalize(raw);
    if (!norm) return null;

    // Full dotted citation, e.g. "1.101" / "3.47a" / (lacuna) "1.1094-1101".
    const dotted = VERSE_LINE_COLUMN_RE.exec(norm);
    if (dotted) {
      return { column: norm, line: null, isRange: isVerseLineRange(dotted[2]) };
    }

    // "{book}:{lineref}" — the `?loc=` routing grammar's separator,
    // repurposed here: since there is no separate line axis, this composes
    // the colon form into the same dotted citation string rather than
    // returning a genuine `line` — `line` stays null on every return, per
    // this module's "no such thing as a line on a lineless scheme"
    // convention (see the module doc comment).
    const colon = norm.indexOf(':');
    if (colon !== -1) {
      const book = norm.slice(0, colon);
      const lineref = norm.slice(colon + 1);
      if (!/^[0-9]+$/.test(book)) return null;
      const isRange = isVerseLineRange(lineref);
      if (!isRange && !VERSE_LINE_RE.test(lineref)) return null;
      return { column: `${book}.${lineref}`, line: null, isRange };
    }

    // Bare lineref within the reader's current book, e.g. "101" (scrolling
    // book 3, jumping to "47a"). Unlike book-section's bookFromColumn,
    // there is no columns.json-style lookup that can recover a book from a
    // bare lineref — the caller supplies the ambient current book (the
    // reader page it is already rendering for a specific book) and composes
    // the full "book.lineref" column before treating this as a citation;
    // this function has no such context to resolve it itself.
    const isRange = isVerseLineRange(norm);
    if (isRange || VERSE_LINE_RE.test(norm)) {
      return { column: norm, line: null, isRange };
    }

    return null;
  }

  function formatCitation(column: string): string {
    // hasUserFacingLines is false — the line IS the column (§3.1/§3.4);
    // `line` is always ignored, matching book-section's formatCitation.
    return column;
  }

  // Like book-section, the book IS the column's dotted prefix — no
  // columns.json-style lookup needed.
  function bookFromColumn(column: string): number | null {
    const m = VERSE_LINE_COLUMN_RE.exec(normalize(column));
    return m ? Number(m[1]) : null;
  }

  return {
    id: 'verse-line',
    columnRegex: VERSE_LINE_COLUMN_RE,
    hasUserFacingLines: false,
    // A verse-line book runs to ~1000+ lines; unlike book-section's
    // tens-of-chapters-per-book outline, a per-line sections.json outline
    // nav would be unusable — no sections.json-style outline for this
    // scheme, mirroring bekker/busse rather than book-section/stephanus.
    hasSections: false,
    jumpPlaceholder: 'e.g. 1.101',
    label: 'line',
    parseColumnToken,
    parseLocation,
    formatCitation,
    bookFromColumn,
  };
}

// A flat-numeric scheme (bare chapter integer — currently only `section`,
// Epictetus' Enchiridion). Its own factory rather than reusing makeScheme or
// makeDottedScheme: the grammar has no letter axis and no dotted book prefix
// at all, so neither the legacy concatenated-ref form (needs an unambiguous
// letter/digit boundary) nor a `:line` suffix (this scheme has no
// user-facing lines) has anything to parse.
function makeFlatScheme(
  id: SchemeId,
  jumpPlaceholder: string,
  label: string,
): CitationScheme {
  // NOT the shared normalize(): that collapses INTERNAL whitespace, which for
  // a bare-integer grammar would silently rewrite "5 0" into the different
  // chapter "50". Outer whitespace is trimmed; anything internal rejects via
  // the regex. Mirrors scheme.py's flat handling exactly (JS \d is already
  // ASCII-only; the Python side pins [0-9] for the same reason) — see the
  // "flat grammar parity" tests on both sides.
  function flatToken(raw: string): string | null {
    const t = raw.trim();
    return FLAT_COLUMN_RE.test(t) ? t : null;
  }

  function parseColumnToken(raw: string): string | null {
    return flatToken(raw);
  }

  function parseLocation(raw: string): ParsedLocation | null {
    // Bare column, e.g. "5" — the only valid citation shape for a bookless,
    // lineless flat scheme; there is no columns.json-style lookup step
    // (bookFromColumn is always null below) and no `:line`/concatenated
    // form to parse, so anything else (including a dotted "1.5") rejects.
    const t = flatToken(raw);
    return t === null ? null : { column: t, line: null };
  }

  function formatCitation(column: string): string {
    return column;
  }

  // Bookless: the work declares a single book, so there is no book prefix
  // to recover from the column token — mirrors makeScheme's bekker/busse
  // bookFromColumn (always null), not makeDottedScheme's dotted-prefix one.
  function bookFromColumn(): number | null {
    return null;
  }

  return {
    id,
    columnRegex: FLAT_COLUMN_RE,
    hasUserFacingLines: false,
    hasSections: false,
    jumpPlaceholder,
    label,
    parseColumnToken,
    parseLocation,
    formatCitation,
    bookFromColumn,
  };
}

// dk (Diels-Kranz — the Presocratics, Wave 1b). Its own factory rather than
// reusing makeScheme: the column grammar has a THREE-part shape (series,
// number, suffix) with mixed-case canonicalization (series upper, suffix
// lower) that none of the other factories' single normalize() handles, and
// its book-boundary/formatCitation behavior (bookless; a dot-joined ref for
// a verse work, never colon or concatenation) doesn't match any of them
// either. `hasUserFacingLines` defaults false (Heraclitus: cited "B30", no
// line); a verse work (Parmenides) is composed with it true via the same
// per-work override seam scheme.py's `citation.lines` uses — see
// `schemeFor`'s composition below.
// Case-parity contract with scheme.py's `_DK_COLUMN_RE`/`_DK_VERSE_REF_RE`
// (both `^([AB])([0-9]+)([a-z]?)...$` — strict: uppercase series, lowercase
// suffix, no other case accepted): that strict grammar is `DK_COLUMN_RE`
// above (this module's `columnRegex` field), and BOTH registries hold data
// to it exactly — a manifest/emitted spine column is already canonical, on
// both sides, always. `DK_INPUT_COLUMN_RE`/`DK_INPUT_REF_RE` below are
// DELIBERATELY wider: they exist ONLY at the citation-JUMP layer (parseLocation,
// consumed by CommandPalette/BekkerJump — never anything that touches spine
// data), where a reader may hand-type "b30"/"B84A" and expects it silently
// canonicalized to "B84a", not rejected. scheme.py has no equivalent lenient
// regex and never needs one — the jump grammar's case-insensitive input
// handling is a TypeScript/UI-only concern, not a parity gap. See
// citation.test.ts's "grammar parity with scheme.py" cases, which assert
// the STRICT regex only; the lenient jump-layer forms are asserted
// separately, right below them.
const DK_INPUT_COLUMN_RE = /^([ABab])([0-9]+)([A-Za-z]?)$/;
const DK_INPUT_REF_RE = /^([ABab])([0-9]+)([A-Za-z]?)\.([0-9]+)$/;
// A bare number, optionally with dk's single-letter suffix ("30", "84a") —
// no series letter at all. Only ever meaningful WITHIN a specific dk work's
// context, where the work's own declared `citation.series` supplies the
// missing letter (Wave 1b design memo §2, ⌘K jump grammar: "bare `30`...
// resolved to the current work's declared series"). The module-level
// singleton `scheme('dk')` carries no series and so still rejects a bare
// number (see citation.test.ts's grammar-parity case `['30', null]`); only a
// per-work instance composed via `schemeFor` (which knows the work's series)
// accepts one — see `series` below.
const DK_BARE_NUMBER_RE = /^([0-9]+)([A-Za-z]?)$/;

function makeDkScheme(
  hasUserFacingLines: boolean,
  series?: 'A' | 'B',
  noSeries?: boolean,
): CitationScheme {
  // Outer whitespace only — mirrors makeFlatScheme's normalize (NOT the
  // shared normalize(), which collapses/lowercases indiscriminately and
  // would corrupt dk's series-upper/suffix-lower canonical form). Internal
  // whitespace ("B 30") is rejected by the regex below, never collapsed.
  function trimmed(raw: string): string {
    return raw.trim();
  }

  function canonicalColumn(seriesLetter: string, number: string, suffix: string): string {
    return `${seriesLetter.toUpperCase()}${number}${suffix.toLowerCase()}`;
  }

  // A no-series work's column IS just number+suffix — no letter to
  // canonicalize (see DK_NO_SERIES_COLUMN_RE's doc comment above).
  function canonicalNoSeriesColumn(number: string, suffix: string): string {
    return `${number}${suffix.toLowerCase()}`;
  }

  function parseColumnToken(raw: string): string | null {
    const t = trimmed(raw);
    if (noSeries) {
      const m = DK_NO_SERIES_INPUT_COLUMN_RE.exec(t);
      return m ? canonicalNoSeriesColumn(m[1], m[2] ?? '') : null;
    }
    const m = DK_INPUT_COLUMN_RE.exec(t);
    if (m) return canonicalColumn(m[1], m[2], m[3] ?? '');
    if (series) {
      const bm = DK_BARE_NUMBER_RE.exec(t);
      if (bm) return canonicalColumn(series, bm[1], bm[2] ?? '');
    }
    return null;
  }

  function parseLocation(raw: string): ParsedLocation | null {
    const t = trimmed(raw);
    if (!t) return null;

    // Bare column, e.g. "B30" or "b30" — valid for every dk work.
    const bare = parseColumnToken(t);
    if (bare) return { column: bare, line: null };

    // "{column}:{line}" — the `?loc=` query grammar.
    const colon = t.indexOf(':');
    if (colon !== -1) {
      const colPart = parseColumnToken(t.slice(0, colon));
      const linePart = t.slice(colon + 1);
      if (!colPart || !/^[0-9]+$/.test(linePart)) return null;
      if (!hasUserFacingLines) return null; // no such thing as a lineless-scheme line
      return { column: colPart, line: Number(linePart) };
    }

    // The dotted scholarly ref form, e.g. "B8.34" — only meaningful for a
    // verse work; unambiguous because a line is all-digits and a suffix is
    // a single letter ("B84a" can only ever be the bare column B84a, never
    // column B84 + line "a"). Not reachable for a no-series work (rejected
    // above via the `citation.no_series`+`citation.lines` combination
    // guard mirrored from scheme.py's `for_manifest`).
    if (!hasUserFacingLines || noSeries) return null;
    const m = DK_INPUT_REF_RE.exec(t);
    if (!m) return null;
    return { column: canonicalColumn(m[1], m[2], m[3] ?? ''), line: Number(m[4]) };
  }

  function formatCitation(column: string, line?: number | null): string {
    // The dot IS the scholarly convention for fragment.line ("DK 28 B8.34")
    // — never book-section's colon or bekker's concatenation (ambiguous
    // here: "B834" cannot tell column B834 from B8 line 34).
    if (hasUserFacingLines && line != null) return `${column}.${line}`;
    return column;
  }

  // dk is bookless (a single declared book covers the whole spine, like
  // `section`) — there is no book prefix to recover from the column token.
  function bookFromColumn(): number | null {
    return null;
  }

  return {
    id: 'dk',
    columnRegex: noSeries ? DK_NO_SERIES_COLUMN_RE : DK_COLUMN_RE,
    hasUserFacingLines,
    hasSections: true, // the ordered fragment list IS the outline nav — mirrors `section`
    jumpPlaceholder: noSeries ? 'e.g. 7' : 'e.g. B30',
    label: 'Diels–Kranz citation',
    parseColumnToken,
    parseLocation,
    formatCitation,
    bookFromColumn,
  };
}

// A registered-but-unimplemented scheme (ennead).
// `scheme(id)` returns this object rather than falling back to bekker — the
// id is recognized and distinguishable (`.id` reports its real name) — but
// every method throws, so using one is a loud, immediate error rather than
// mis-citing a work under the wrong grammar.
function makeStubScheme(id: SchemeId): CitationScheme {
  const fail = (): never => {
    throw new Error(`citation scheme '${id}' is registered but not implemented`);
  };
  return {
    id,
    columnRegex: /(?!)/, // never matches
    hasUserFacingLines: false,
    hasSections: false,
    jumpPlaceholder: '',
    label: `${id} (not yet implemented)`,
    parseColumnToken: fail,
    parseLocation: fail,
    formatCitation: fail,
    bookFromColumn: fail,
  };
}

const SCHEMES: Record<SchemeId, CitationScheme> = {
  bekker: makeScheme('bekker', true, 'e.g. 1097a15', 'Bekker citation'),
  busse: makeScheme('busse', true, 'e.g. 1a5', 'CAG citation'),
  // Both nest a section div inside their page div — see hasSections' doc
  // comment — so both override the factories' default `hasSections: false`.
  stephanus: { ...makeScheme('stephanus', false, 'e.g. 34b', 'Stephanus page'), hasSections: true },
  'book-section': { ...makeDottedScheme('book-section', false, 'e.g. 4.23', 'book and section'), hasSections: true },
  // Bookless flat chapter grammar; still wants the per-chapter outline (see
  // hasSections' doc comment), so overrides the factory's default false —
  // same override shape as stephanus/book-section above.
  section: { ...makeFlatScheme('section', 'e.g. 5', 'Chapter citation'), hasSections: true },
  dk: makeDkScheme(false),
  'verse-line': makeVerseLineScheme(),
  ennead: makeStubScheme('ennead'),
  // Letter.section dotted grammar (Seneca's Epistulae Morales, Wave 2 Batch 3
  // — design memo docs/wave2-seneca-design.md §A): byte-identical to
  // book-section's makeDottedScheme (letter = page axis, section = column;
  // "47.3"), reused wholesale rather than a new factory — the only
  // difference is labels/hasSections, mirroring book-section's own override
  // above.
  letter: { ...makeDottedScheme('letter', false, 'e.g. 47.3', 'letter'), hasSections: true },
};

// The scheme for a scheme id; omitted/empty (null/undefined/'') defaults to
// bekker, matching scheme.py's `get(name)`: `SCHEMES[name or "bekker"]`. An
// unknown *non-empty* name is a data bug (a manifest/work citation.scheme
// typo, say), and Python's dict-subscript raises KeyError for it rather than
// silently falling back — this throws a clear Error for parity, instead of
// masking the typo as bekker.
export function scheme(id: SchemeId | string | null | undefined): CitationScheme {
  if (!id) return SCHEMES.bekker;
  if (id in SCHEMES) return SCHEMES[id as SchemeId];
  throw new Error(`unknown citation scheme '${id}'`);
}

// The scheme a work is cited by — reads works.ts's `citation?.scheme`
// (default bekker), the same default the pipeline's `for_manifest` applies.
// `citation.lines: true` (dk only — a verse work like Parmenides) composes
// `{...scheme, hasUserFacingLines: true}` with the dk verse ref grammar,
// mirroring scheme.py's `for_manifest` `citation.lines` override exactly
// (same per-work-override seam as book-section/DL's `div_types`, see that
// module's doc comment). `citation.noSeries: true` (dk only — a chapter DK
// prints with no series letter, Pythagoras DK 14) composes the no-series
// column grammar the same way, mirroring scheme.py's `citation.no_series`.
// An unknown/mistyped work still falls back to bekker via `scheme()` above;
// the override only ever applies once a real dk work is resolved.
//
// A dk work is ALWAYS recomposed with its own `citation.series` (never the
// module-level `SCHEMES.dk` singleton, which carries no series) so that
// `parseLocation`'s bare-number jump form ("30" -> "B30") resolves against
// the right letter — see makeDkScheme's `series` param doc comment.
export function schemeFor(work: string): CitationScheme {
  const citation = getWork(work)?.citation;
  const base = scheme(citation?.scheme);
  if (base.id === 'dk') {
    return makeDkScheme(!!citation?.lines, citation?.series, !!citation?.noSeries);
  }
  return base;
}

// The noun for one citable unit of a work, in the three forms every caller
// needs (a bare lowercase noun, its regular plural, and a capitalized form
// for headings). Ruling (REVIEW-CHECKLIST item 34): each citation scheme
// names its own unit —
//   stephanus -> page, book-section -> section, flat section -> chapter,
//   letter -> letter, verse-line -> line, bekker/busse -> chapter,
//   dk -> "fragment" (B-series) or "testimonium" (A-series).
// The dk A/B split lives on the WORK record (`citation.series`), not on the
// scheme or the passage — see works.ts's doc comment on `series` — so this
// takes a work id, not just a scheme id, and resolves the work internally.
export interface UnitNoun {
  readonly singular: string;
  readonly plural: string;
  readonly capitalized: string;
}

const UNIT_NOUN_SINGULAR: Record<Exclude<SchemeId, 'dk'>, string> = {
  bekker: 'chapter',
  busse: 'chapter',
  stephanus: 'page',
  'book-section': 'section',
  section: 'chapter',
  'verse-line': 'line',
  letter: 'letter',
  // An Ennead is divided into tractates; citation is by ennead.tractate.chapter
  // (Plotinus, planned — REVIEW-CHECKLIST item 34's ruling covers planned
  // schemes too, same posture as bekker/busse before their works landed).
  ennead: 'tractate',
};

// Finding 1 (Sol review, 2026-07-24): the dk A/B split does NOT collapse to
// "not A means B" — a dk work with no series letter at all (Pythagoras, DK
// 14) is testimonia (ancient reports ABOUT the philosopher), not fragments
// (his own surviving words), and defaulting it to "fragment" asserted a
// false scholarly claim. Classify from an explicit work-level signal — the
// work's own `title` ('Fragments' / 'Testimonia', true for every DK work in
// the corpus today) backed by `citation.series` as a second signal — and if
// neither classifies the work, fall back to a neutral noun that asserts
// nothing rather than defaulting to "fragment".
function dkNoun(work: string): { singular: 'testimonium' | 'fragment' | 'passage'; plural: string } {
  const w = getWork(work);
  const series = w?.citation?.series;
  const title = w?.title;
  if (series === 'A' || title === 'Testimonia') return { singular: 'testimonium', plural: 'testimonia' };
  if (series === 'B' || title === 'Fragments') return { singular: 'fragment', plural: 'fragments' };
  return { singular: 'passage', plural: 'passages' };
}

export function unitNounFor(work: string): UnitNoun {
  const s = schemeFor(work);
  let singular: string;
  let plural: string;
  // Per-work override (`citation.unitNoun`, e.g. Epicurus' Kuriai Doxai ->
  // "doctrine", Vatican Sayings -> "saying"): the flat `section` scheme's
  // table default ("chapter") is a scholarly convention for a continuous
  // prose work like Epictetus' Enchiridion, not an evidentiary claim about
  // every flat-scheme work — a collection of discrete maxims calls its own
  // units something else. Checked before the scheme-level table so an
  // override always wins; set today only by the five Epicurus works.
  const override = getWork(work)?.citation?.unitNoun;
  if (override) {
    singular = override.singular;
    plural = override.plural;
  } else if (s.id === 'dk') {
    ({ singular, plural } = dkNoun(work));
  } else {
    singular = UNIT_NOUN_SINGULAR[s.id as keyof typeof UNIT_NOUN_SINGULAR] ?? 'chapter';
    plural = `${singular}s`;
  }
  return { singular, plural, capitalized: singular.charAt(0).toUpperCase() + singular.slice(1) };
}

// unitNounFor's singular or plural, chosen by `count` — e.g. ReaderShell.astro's
// TOC drawer count ("1 section" vs "51 sections"). Every "N <noun>" count
// display should route through this rather than hardcoding the plural form
// (finding 4, Sol review: a single-chapter book rendered "1 chapters").
export function nounForCount(work: string, count: number): string {
  const n = unitNounFor(work);
  return count === 1 ? n.singular : n.plural;
}

// The noun a result-group header uses for one grouping unit of a work — e.g.
// Search.svelte's per-group label ("Section 17" for a book-section work,
// "B10" for a Diels-Kranz fragment/testimonium). A DK column ("B10", "B84a")
// already reads as the citation itself — scholarly usage never prefixes it
// with a unit word, and the site's copy rule bars internal jargon standing
// in for it either — so dk gets no noun at all here; the caller renders the
// bare column. Every other scheme uses unitNounFor's capitalized noun.
// Exported so any future caller (the reader nav, say) can reuse the same
// mapping instead of re-deriving it.
export function groupUnitNoun(work: string): string {
  if (schemeFor(work).id === 'dk') return '';
  return unitNounFor(work).capitalized;
}

// ── Reader nav "Pages" picker chip source (ReaderShell.astro) ──────────────
// Every hasSections scheme's per-book outline pipeline output (sections.json)
// assigns `page` correctly EXCEPT the two numeric-section schemes,
// book-section and letter (Seneca's Epistulae Morales, Wave 2 Batch 3 —
// docs/wave2-seneca-design.md §A; `letter` reuses book-section's dotted
// column grammar byte-for-byte — see scheme.py's `letter_scheme` doc
// comment), where `page` is constant at the book number (book-section) or
// the letter number (letter) rather than incrementing per section (a
// pipeline artifact, task #35) — so a naive dedup-by-`page` collapses a
// whole book/letter (e.g. Epistula 47's 21 sections) to a single nav row
// ("Pages 47–47" + one chip). Callers building the nav's chip list key
// their choice of source array on this instead of a bare
// `=== 'book-section'` test, so the workaround has one definition next to
// the rest of the scheme dispatch (same convention as `hasSections` — see
// its doc comment above).
export function navChipsNeedFullSectionList(schemeId: SchemeId | string): boolean {
  return schemeId === 'book-section' || schemeId === 'letter';
}

// The book's "pages" for outline/count display (ReaderShell.astro's TOC
// drawer, Landing.astro's per-book row): the first section at each distinct
// `page` value, in reading order — EXCEPT for a navChipsNeedFullSectionList
// scheme (book-section/letter), where `page` is constant across the whole
// book (see the doc comment above), so deduping by it collapses every
// section in the book to a single entry ("1 section" for a 51-section book —
// finding 3, Sol review). For those schemes, every section is its own
// citable unit, so the full un-deduped list is returned instead. Both
// ReaderShell.astro and Landing.astro previously duplicated (and diverged
// on) this dedup, one of them missing the workaround entirely — consolidated
// here so there is one definition, and it's unit-testable without an Astro
// render pass.
export function pageEntriesFor<T extends { page: number; column: string }>(
  schemeId: SchemeId | string,
  sections: readonly T[],
): { page: number; column: string }[] {
  if (navChipsNeedFullSectionList(schemeId)) {
    return sections.map((s) => ({ page: s.page, column: s.column }));
  }
  const out: { page: number; column: string }[] = [];
  let last: number | null = null;
  for (const s of sections) {
    if (s.page !== last) { out.push({ page: s.page, column: s.column }); last = s.page; }
  }
  return out;
}

// A dotted book-section column's bare chapter component ("4.23" -> "23",
// "12.34" -> "34") — shared by the nav row's dotted section chips and the
// TOC sidebar's chapterTitles lookup, both keyed the same as bekker-scheme
// works' chapters.json entries. A non-dotted column (any other scheme) is
// returned unchanged, so a caller can apply this unconditionally without
// checking the scheme first.
export function dottedSectionChapter(column: string): string {
  return column.split('.', 2)[1] ?? column;
}

// ── Site-wide dk full-citation-form jump (⌘K palette only) ─────────────────
// "DK 22 B30" / "22 B30" — the full scholarly form a reader pastes from
// secondary literature (Wave 1b design memo §2, ⌘K jump grammar). Unlike
// every other parse path in this module, this one does NOT take a `work`:
// it resolves WHICH work from the cited dk chapter + series itself, via
// works.ts's registry-driven `workByDkCitation` (no separately-maintained
// map to go stale). Deliberately not part of the per-scheme `parseLocation`
// contract — it isn't a per-work grammar, it's a cross-work lookup — so it
// lives here as its own function the palette calls directly.
export interface DkFullCitation {
  workId: string;
  column: string;
  line: number | null;
}

const DK_FULL_CITATION_RE = /^(?:dk\s+)?([0-9]+)\s+([ab])([0-9]+)([a-z]?)(?:[.:]([0-9]+))?$/i;

// A no-series dk chapter's full-citation form ("DK 14, 7" / "DK 14,7" /
// "DK 14 7" — comma optional, mirroring how DK's own apparatus prints a
// no-series chapter, "DK 14, 7", never "14 A7"; Pythagoras, DK 14). No
// series letter, so no line component either (`citation.no_series` is not
// composable with `citation.lines` — see scheme.py's `for_manifest` and
// makeDkScheme's `noSeries` doc above). Structurally disjoint from
// DK_FULL_CITATION_RE above by construction: that regex requires an A/B
// series letter immediately after the chapter number; this one requires a
// bare digit run there instead (`[,\s]+` is never a letter), so a genuine
// lettered citation never matches here, and this regex never matches a
// lettered one — `parseDkFullCitation` tries both and only one can ever
// fire for a given input. A no-series chapter followed by a LETTER (e.g.
// "DK 14 A7") matches NEITHER form usefully: DK_FULL_CITATION_RE would
// parse it as chapter 14 series A, but `workByDkCitation(14, 'A')` finds
// nothing (Pythagoras has no `series` — see works.ts's DK_BY_CHAPTER_SERIES
// exclusion), so it correctly fails to resolve; this regex requires a
// digit right after the separator, which "A7" isn't, so it doesn't match
// at all. Either way, "DK 14 A7" never resolves.
const DK_NO_SERIES_FULL_CITATION_RE = /^(?:dk\s+)?([0-9]+)[,\s]+([0-9]+)([a-z]?)$/i;

export function parseDkFullCitation(raw: string): DkFullCitation | null {
  const t = raw.trim();
  const m = DK_FULL_CITATION_RE.exec(t);
  if (m) {
    const dkChapter = Number(m[1]);
    const seriesLetter = m[2].toUpperCase() as 'A' | 'B';
    const work = workByDkCitation(dkChapter, seriesLetter);
    if (!work) return null;
    const column = `${seriesLetter}${m[3]}${(m[4] ?? '').toLowerCase()}`;
    if (m[5] == null) return { workId: work.id, column, line: null };
    // A line component only ever means something for a verse dk work
    // (citation.lines: true) — reject rather than silently drop it, per
    // this module's lineless-scheme convention everywhere else.
    if (!schemeFor(work.id).hasUserFacingLines) return null;
    return { workId: work.id, column, line: Number(m[5]) };
  }
  const nm = DK_NO_SERIES_FULL_CITATION_RE.exec(t);
  if (!nm) return null;
  const dkChapter = Number(nm[1]);
  const work = workByDkChapterNoSeries(dkChapter);
  if (!work) return null;
  const column = `${nm[2]}${(nm[3] ?? '').toLowerCase()}`;
  return { workId: work.id, column, line: null };
}

// ── Convenience composers ──────────────────────────────────────────────────
// These aren't part of the per-scheme contract itself, but wrap it for the
// call sites that compose a citation/location string for a specific work
// (the scroll-spy hash, resume storage, copy-citation, and Search jump URLs).
// Reader.svelte and Search.svelte don't call these yet (that wiring is a
// later task) — they're here, exported and tested, for that task to use.

// The scroll-spy/resume/copy-citation string for a work's column (+ line):
// "1097a15" (bekker), "17a" (stephanus — line, if given, is dropped).
export function formatCite(work: string, column: string, line?: number | null): string {
  return schemeFor(work).formatCitation(column, line);
}

// The `#`-prefixed hash for `history.replaceState` / a shareable link.
export function formatHash(work: string, column: string, line?: number | null): string {
  return `#${formatCite(work, column, line)}`;
}

// The `loc=` query VALUE (not URL-encoded) for a jump-in link: "1097a:15" when
// the scheme has user-facing lines and a line is given, otherwise the bare
// column — so a stephanus Search-result link reads as a clean "?loc=17a"
// rather than a line-level citation a Plato reader never sees elsewhere.
export function formatLocValue(work: string, column: string, line?: number | null): string {
  const s = schemeFor(work);
  return s.hasUserFacingLines && line != null ? `${column}:${line}` : column;
}

// The "Copy Citation" scholarly-abbreviation prefix for a work: `abbr`
// stays the short UI label everywhere else in the reader (nav chips, the
// translation gutter's siglum, etc.); this is the ONLY place `copyAbbr`
// (when a work declares one) overrides it — the prefix a reader actually
// pastes into scholarship, e.g. "DK 22" for Heraclitus (not the UI's own
// short "Her. B"), or "DK 14," for Pythagoras (see formatCopyCitation's
// doc for why the trailing comma). Unlike schemeFor (which defaults an
// unknown work to the bekker scheme — see its doc comment), an unknown
// work here is a caller bug: with no registry entry there's no
// `abbr`/`copyAbbr` to prefix, so this would otherwise emit a
// plausible-looking citation for a typo'd work id.
function copyAbbrFor(workId: string): string {
  const work = getWork(workId);
  if (!work) throw new Error(`copy citation: unknown work '${workId}'`);
  return work.citation?.copyAbbr ?? work.abbr;
}

// The per-work "Copy Citation" string: `copyAbbrFor`'s prefix followed by
// the scheme-formatted citation — "M.Ant. 4.23" (book-section), "EN
// 1097a15" (bekker), "DK 22 B30" (dk lettered), "DK 14, 7" (dk no-series —
// Pythagoras' `citation.copyAbbr` carries its own trailing comma, so this
// plain `${prefix} ${column}` join needs no extra machinery to come out
// "DK 14, 7" rather than "DK 14 7").
export function formatCopyCitation(workId: string, column: string, line?: number): string {
  return `${copyAbbrFor(workId)} ${formatCite(workId, column, line)}`;
}

// The copy-with-citation RANGE string Reader.svelte's selection-copy
// handlers (handleCopy / clickCopyBtn) wrap a copied Greek passage in:
// "(DK 22 B30)" for a single-line/column selection, "(DK 22 B30–B31)" for
// a genuine range whose start and end resolve to different citations —
// `start`/`end` are `null` only when the corresponding end of the
// selection never resolved to a Greek line (idToCite came back null), and
// the whole result is `null` when NEITHER end resolved (nothing to cite).
// Shares `copyAbbrFor`'s prefix resolution with `formatCopyCitation` above
// so a work's copy output is coherent regardless of which of the two a
// caller uses — this used to be built inline in Reader.svelte from the
// work's plain `abbr` instead of this shared prefix, so every dk work's
// copied citation carried its short UI abbreviation ("Pyth. 7") rather
// than its scholarly DK-chapter one ("DK 14, 7").
export function formatCopyCitationRange(
  workId: string,
  start: { column: string; line?: number | null } | null,
  end: { column: string; line?: number | null } | null,
): string | null {
  if (!start && !end) return null;
  const prefix = copyAbbrFor(workId);
  const s = start ? formatCite(workId, start.column, start.line) : null;
  const f = end ? formatCite(workId, end.column, end.line) : null;
  return (s && f && s !== f) ? `(${prefix} ${s}–${f})` : `(${prefix} ${s ?? f})`;
}
