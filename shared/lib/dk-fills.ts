// Filled DK abbreviations (John, 2026-09-29 ruling).
//
// Inside a source passage DK often abbreviates a quotation of words it
// prints in full elsewhere as "FIRST ... LAST" -- a printing economy. The
// pipeline (pipeline/reader_pipeline/stage1_dk_fills.py) supplies the words
// between from DK's own full text and hangs them on the line as `fills`
// (GreekLine.fills); the line's `text` is never changed. The reader shows the
// supplied words in place of the "...", set lighter with a dotted underline,
// and a hover note: "DK prints only FIRST … LAST; the full verses are the
// fragment's own." ("the full text is" for prose).
//
// This module is pure: a locator (`locateDkFills`) that finds a line's fills
// in whatever slice of it a renderer shows, and a render-part splicer
// (`applyDkFills`). Reader.svelte is the only caller.

import type { DkFill } from './data';
import type { DkRenderPart } from './dk-crossrefs';

// A filled "...": `text` stays the printed "..." so the parts still
// reproduce the line (applyEditionNotes counts offsets by part text);
// `fill` is what the reader sees in its place.
export type DkFillPart = { kind: 'dkfill'; text: string; fill: string; title: string };

// One DK line that carries fills, as the column holds it.
export interface DkFillLine { line: string; fills: readonly DkFill[] }

// The hover note (John's approved wording).
export function dkFillTitle(fill: DkFill): string {
  const full = fill.kind === 'verse' ? 'the full verses are' : 'the full text is';
  // As approved: the quotation marks dropped and DK's "..." shown as "…".
  const shown = fill.abbrev.replace(/^[‘’'"]+|[‘’'"]+$/g, '').replace(/\s*(?:\.\.\.|…)\s*/, ' … ');
  return `DK prints only ${shown}; ${full} the fragment’s own.`;
}

// How much of the line around a "..." must agree before a fill is placed in
// a text that is not the whole line (a source heading peeled off the front,
// a witness row, a paragraph cut from the line, a healed print hyphen).
const CONTEXT = 40;
const MIN_CONTEXT = 12;

// The column's fills that fall inside `text`, in `text` coordinates, sorted.
// A renderer usually shows the whole line (an exact match); otherwise each
// fill is placed where its "..." occurs in `text` with the same surrounding
// characters as in its line -- up to CONTEXT on each side, cut at either
// string's edge, and at least MIN_CONTEXT in all -- so a slice of the line
// keeps its fills and nothing else can take them.
export function locateDkFills(text: string, lines: readonly DkFillLine[]): DkFill[] {
  const out: DkFill[] = [];
  for (const { line, fills } of lines) {
    if (line === text) {
      out.push(...fills);
      continue;
    }
    for (const fill of fills) {
      const mark = line.slice(fill.start, fill.end);
      for (let p = text.indexOf(mark); p >= 0; p = text.indexOf(mark, p + 1)) {
        const a = Math.min(p, fill.start, CONTEXT);
        const b = Math.min(text.length - (p + mark.length), line.length - fill.end, CONTEXT);
        if (a + b < MIN_CONTEXT) continue;
        if (text.slice(p - a, p + mark.length + b) === line.slice(fill.start - a, fill.end + b)) {
          out.push({ ...fill, start: p, end: p + mark.length });
          break;
        }
      }
    }
  }
  out.sort((x, y) => x.start - y.start);
  return out.filter((f, i) => i === 0 || f.start >= out[i - 1]!.end);
}

// Replace each fill's "..." among a line's render parts with one 'dkfill'
// part. `parts` must reproduce `text` (every non-'speaker' part's text,
// concatenated, is `text` -- lineRenderParts' and applyDkCrossRefs' shared
// contract), and `fills` must be sorted and non-overlapping. The "..." is
// never inside a Greek word or a cross-reference link, so only plain 'text'
// parts are cut: a piece outside a fill stays plain text, and a "..." split
// across two parts becomes one 'dkfill' where it starts.
export function applyDkFills(
  text: string,
  parts: readonly DkRenderPart[],
  fills: readonly DkFill[],
): (DkRenderPart | DkFillPart)[] {
  if (!fills.length) return parts as DkRenderPart[];
  const out: (DkRenderPart | DkFillPart)[] = [];
  let ptr = 0;
  let fi = 0;
  for (const part of parts) {
    if (part.kind === 'speaker') { out.push(part); continue; }
    const start = ptr;
    const end = ptr + part.text.length;
    ptr = end;
    while (fi < fills.length && fills[fi]!.end <= start) fi += 1;
    if (part.kind !== 'text' || fi >= fills.length || fills[fi]!.start >= end) { out.push(part); continue; }
    let cursor = start;
    while (fi < fills.length && fills[fi]!.start < end) {
      const f = fills[fi]!;
      if (f.start > cursor) out.push({ kind: 'text', text: text.slice(cursor, f.start) });
      if (f.start >= start) out.push({ kind: 'dkfill', text: text.slice(f.start, f.end), fill: f.text, title: dkFillTitle(f) });
      cursor = Math.min(f.end, end);
      if (f.end > end) break; // the "..." runs on into the next part
      fi += 1;
    }
    if (cursor < end) out.push({ kind: 'text', text: text.slice(cursor, end) });
  }
  return out;
}
