// Citation-pill formatting for LemmaPage.astro's per-work occurrence lists.
// Extracted into a plain module (rather than inline arrow functions in the
// .astro frontmatter) so this scheme-dispatch logic is unit-testable without
// an Astro render pass — see app/src/__tests__/lemma-instance.test.ts.
//
// Bug this replaces (Sol review): the old inline instLabel/instHref
// HAND-CONCATENATED column+line ("${col}${line}"), which bakes in Bekker's
// no-separator convention for every scheme. A DK verse work (Parmenides)
// uses a DOT separator ("B8.34" — schemeFor(...).formatCitation) — the
// hand-concat produced "B834" instead of "B8.34". Fix: dispatch through the
// citation module's own formatCitation/formatLocValue (via formatCite/
// formatLocValue), which already know each scheme's separator.
//
// Second bug: a dk verse fragment's role='context' line carries a NEGATIVE
// synthetic line number (stage1_greek._parse_fragments; see stage7_emit.py's
// column_line_ranges doc) — non-citable by construction, never a real
// citation target. The old code passed it straight through, rendering
// "B1-1" / "?loc=B1:-1". Any negative line is now treated as "no line"
// (the module's own `ParsedLocation.line: number | null` convention) before
// it reaches the formatters, so a context-block occurrence renders its bare
// column citation instead of a garbled one.
import { formatCite, formatLocValue } from '@shared/lib/citation';
import { workPath } from '@shared/lib/works';

export type Instance = [col: string, line: number, surface: string];

// stage1's non-citable sentinel for a dk verse fragment's role='context'
// line is a negative synthetic `n`; everywhere else `line` is a real
// citable line (>= 0). Line-less schemes (book-section, lineless dk) ignore
// whatever they're handed regardless, so this guard only ever changes
// behavior for the sentinel case.
function citableLine(line: number): number | null {
  return line >= 0 ? line : null;
}

// The citation pill's visible label: "1097a15" (bekker), "4.23"
// (book-section — no user-facing line axis, so the line is dropped),
// "B8.34" (dk verse), "B30" (dk, lineless), "B1" (dk verse context block —
// sentinel line dropped, not "B1-1").
export function instLabel(work: string, [col, line]: Instance): string {
  return formatCite(work, col, citableLine(line));
}

// Deep-link an instance back into the reader: scroll to the cited line (when
// the scheme and this instance both have one) and highlight the word.
export function instHref(
  base: string,
  work: string,
  book: number,
  [col, line, surface]: Instance,
): string {
  const loc = formatLocValue(work, col, citableLine(line));
  return `${base}${workPath(work, book)}?hlg=${encodeURIComponent(surface)}&loc=${loc}`;
}
