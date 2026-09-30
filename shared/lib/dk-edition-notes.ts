// DK edition references as numbered notes (John, 2026-09-28 ruling).
//
// Diels-Kranz's Greek carries bracketed references to OTHER editions --
// "[FHG III 42 fr. 28]", "[FGrHist. 84 F 25 II 197]", "[fr. 173 Us.]",
// "[II 253, 28]", "[fr 50 Fowler]", "[Nauck FGT p. 792]" -- which interrupt
// the Greek. The ruling: each such bracket leaves the line and becomes a
// superscript note number (1, 2, 3 ... restarting in each DK column) whose
// pop-up shows the bracket exactly as printed. Everything else in brackets
// stays in the text: DK cross-references ("[B 10]", "[31 B 17]", "[vgl. B
// 91. 12]", linked by dk-crossrefs.ts), Greek words DK adds or explains
// ("[φύσεως]", "[sc. ῥήτορες]"), and Latin/German glosses ("[sc. zodiaci]",
// "[Isokrates]"). One exception: a bracket that IS its line -- surrounding
// whitespace and one trailing "." or "," aside -- stays too, whatever it
// classifies as; Democritus's B36-B111 last lines ("[Stob. III 37, 25].")
// and B224 ("[233 H.]") print nothing else, so the bracket is the
// fragment's own source reference, not an interruption (see `isWholeLine`).
//
// This module is pure: a classifier (`classifyDkBracket`), a finder
// (`findEditionNotes`), a per-column numberer (`numberEditionNotes`) and a
// render-part splicer (`applyEditionNotes`). Reader.svelte is the only
// caller.
//
// ── The rule (survey of all 39 DK works, 2026-09-28) ────────────────────────
// 1478 closed brackets in the Greek lines. Each bracket's content is read in
// this order; the first match decides:
//   1. DK cross-reference (stays). The bracket names at least one DK item --
//      an optional chapter, a series letter A/B/C (DK's own Greek Α/Β too,
//      "[Β 1, 14]"; a stray period too, "[B. 9]"), a number, an optional
//      suffix letter or range ("B 78—81") -- at a place a reference can
//      begin (the bracket's start, after ";", after "vgl."/"s."/"z."/"nach"/
//      "hinter"/"folgt"/"="/"u.", or after a bare name when a chapter
//      follows: "[Heraklit, 22 B 20]"). Each item may carry its own locus:
//      a line (", 32"), a DK volume page ("II 38, 8", "; II 85, 2"), a
//      chained number (". 12"), a range end, "Ende", "Mitte", "§ 23", "V.
//      132", "ff.", "?", or a second item ("A 22 B 56"). If what is left
//      once those are removed holds no digit and no edition siglum, the
//      bracket is a cross-reference: "[11 A 1 Thales]", "[τὴν μεσότητα vgl.
//      47 B 2]", "[A 2; II 85, 2]".
//   2. Date (stays). DK's year for an olympiad or archon: "[504—501]",
//      "[428]", "[442/1]", "[± 380—370]", "[431 ?]", "[Ol. 79, 3 =462/1]",
//      "[aufgeführt 410—8]", "[28. Sept.]", "[Mai 403]", "[richtig Arm. 60,1
//      = 540]". A date names no edition.
//   3. Editorial mark (stays): "[?]", "[!]", "[so]", "[5 Zeilen fehlen]".
//   4. Edition reference (becomes a note): anything else with a digit
//      ("[fr. 173 Us.]", "[II 253, 28]", "[Σ 107]", "[309D]", "[c. 41, 7]"),
//      or an edition siglum with no digit ("[fehlt FHG]", "[IG XIV]", "[Cr.
//      An. Ox. III]", "[a. O.]"). A bracket mixing a reference with a DK
//      cross-reference ("[fr. 173 Us.; 68 A 9]", "[Soph. 237 A vgl. B 7]")
//      is a note; its pop-up keeps the cross-reference as a link.
//   5. Greek word (stays): any Greek letter left ("[φύσεως]", "[sc. ῥήτορες]",
//      "[Etymologie v. ὑπερίων]").
//   6. Gloss (stays): the rest -- Latin/German words and names ("[sc.
//      zodiaci]", "[Isokrates]", "[ARISTOT.]", DK's mark for a spurious
//      attribution, "[Bücherzahl fehlt]").
// Only a bracket closed on the same line is read; one that opens on one line
// and closes on the next stays in the text untouched (18 lines).

import type { DkRenderPart } from './dk-crossrefs';
import type { DkFillPart } from './dk-fills';

export type DkBracketClass = 'crossref' | 'date' | 'mark' | 'note' | 'greek' | 'gloss';

// A DK-style bracket, as dk-crossrefs.ts and check-dk-structure.mjs match it:
// no nesting occurs in this corpus.
const BRACKET_RE = /\[([^[\]]*)\]/g;

// One DK item: optional chapter, series letter (Latin or DK's Greek Α/Β),
// optional stray period, number, optional suffix letter (never followed by
// another letter or a digit -- "B 6 b" yes, "B 4 Ende" no), optional range.
const DK_ITEM = /(?:(\d{1,3})\s+)?[ABCΑΒ]\.?\s?\d{1,4}(?:\s?[a-z](?![a-z])(?!\s?\d))?(?:\s?—\s?(?:[ABC]\s?)?\d{1,4}[a-z]?)?/y;

// What may follow a DK item and still belong to it -- see rule 1 above.
// Tried in order at the position right after the item (sticky).
const DK_LOCI = [
  /\s*[,;]?\s*(?:[IV]{1,3}|i)\s+\d+(?:,\s*\d+)?(?:\s*ff?\.?)?/y, // DK volume page line
  /\s*[.;,]?\s*(?:\d{1,3}\s+)?[ABCΑΒ]\.?\s?\d{1,4}[a-z]?(?:\s?—\s?\d{1,4}[a-z]?)?/y, // another item
  /\s*[.,;]\s*\d{1,4}[a-z]?(?:\s*,\s*\d+)?(?:\s*ff?\.?)?/y, // line / chained number
  /\s*—\s*\d{1,4}[a-z]?/y, // range end
  /\s*(?:Ende|Mitte|ff?\.?|\?|§\s*\d+|V\.\s*\d+)/y,
];

// Words after which a DK item may begin (dk-crossrefs.ts's CONNECTORS plus
// "u.", "and": "[vgl. II 6, 3 u. B 55]").
const CONNECTORS = ['vgl.', 'Vgl.', 's.', 'z.', 'nach', 'hinter', 'folgt', '=', 'u.'];
const NAME_RE = /^\p{L}+(?:\s\p{L}+)*$/u;

function isItemStart(c: string, pos: number, hasChapter: boolean): boolean {
  let j = pos;
  while (j > 0 && c[j - 1] === ' ') j -= 1;
  if (j === 0) return true;
  if (c[j - 1] === ';') return true;
  const before = c.slice(0, j);
  if (CONNECTORS.some((w) => before.endsWith(w))) return true;
  if (!hasChapter) return false;
  let k = j;
  if (c[k - 1] === ',') k -= 1;
  while (k > 0 && c[k - 1] === ' ') k -= 1;
  return k > 0 && NAME_RE.test(c.slice(0, k));
}

// The bracket content with every DK item and its loci removed, plus how many
// items were found. Pure scan, left to right.
function stripDkItems(c: string): { residue: string; items: number } {
  let residue = '';
  let items = 0;
  let i = 0;
  while (i < c.length) {
    const prev = c[i - 1];
    // An item never starts inside a word or number.
    if (i === 0 || !/[\p{L}\p{N}]/u.test(prev ?? '')) {
      DK_ITEM.lastIndex = i;
      const m = DK_ITEM.exec(c);
      if (m && isItemStart(c, i, Boolean(m[1]))) {
        items += 1;
        let pos = i + m[0].length;
        for (let progressed = true; progressed;) {
          progressed = false;
          for (const re of DK_LOCI) {
            re.lastIndex = pos;
            const lm = re.exec(c);
            if (lm && lm[0].length) { pos += lm[0].length; progressed = true; break; }
          }
        }
        i = pos;
        continue;
      }
    }
    residue += c[i];
    i += 1;
  }
  return { residue, items };
}

const YEAR = String.raw`\d{3}ʼ?(?:\s*[—/]\s*\d{1,3})?`;
const DATE_RES = [
  new RegExp(String.raw`^(?:±\s*)?(?:richtig\s+)?(?:(?:Arm\.|[Oo]l\.)\s*\d+,\s*\d+\s*[=.]\s*)?(?:aufgeführt\s+)?${YEAR}(?:\s*\?)?(?:\s+ausgeführt)?$`),
  /^\d{1,2}\.\s*Sept\.$/,
  /^Mai\s+\d{3}$/,
];
const MARK_RE = /^(?:\?|!|so|\d+ Zeilen fehlen)$/;
// Edition sigla that make a bracket a reference even with no digit.
const SIGLUM_RE = /\b(?:FHG|FGrHist|IG)\b|Cr\. An\. Ox\.|(?:^|\s)a\. O\./;
const GREEK_RE = /[Ͱ-Ͽἀ-῿]/;

// Classify one bracket by its content (the text between "[" and "]").
export function classifyDkBracket(inner: string): DkBracketClass {
  const c = inner.trim();
  const { residue, items } = stripDkItems(c);
  if (items && !/\d/.test(residue) && !SIGLUM_RE.test(residue)) return 'crossref';
  if (DATE_RES.some((re) => re.test(c))) return 'date';
  if (MARK_RE.test(c)) return 'mark';
  if (/\d/.test(c) || SIGLUM_RE.test(c)) return 'note';
  if (GREEK_RE.test(c)) return 'greek';
  return 'gloss';
}

// One edition-reference bracket in a line: `start`/`end` are offsets into
// the line's text and include the brackets; `text` is the bracket as printed.
export interface EditionNoteSpan {
  start: number;
  end: number;
  text: string;
}

export function findEditionNotes(text: string): EditionNoteSpan[] {
  const out: EditionNoteSpan[] = [];
  BRACKET_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = BRACKET_RE.exec(text))) {
    const end = m.index + m[0].length;
    if (classifyDkBracket(m[1]!) === 'note' && !isWholeLine(text, m.index, end)) {
      out.push({ start: m.index, end, text: m[0] });
    }
  }
  return out;
}

// True when the bracket at [start, end) is its line's only content --
// surrounding whitespace and one trailing "." or "," aside. Democritus's
// B36-B111 last lines ("[Stob. III 37, 25]."), B224 ("[233 H.]"), and their
// siblings print no other Greek at all: the bracket IS the fragment's
// source reference, not an interruption of running text, however the
// classifier above reads its content -- it stays in the line (John,
// 2026-09-28).
function isWholeLine(text: string, start: number, end: number): boolean {
  if (text.slice(0, start).trim() !== '') return false;
  const after = text.slice(end).trim();
  return after === '' || after === '.' || after === ',';
}

export interface NumberedEditionNote {
  n: number;
  text: string;
  // The exact line this occurrence was found on, and its offset within it --
  // this occurrence's identity, so two brackets with the SAME text (e.g.
  // Empedocles testimonia A1's "[fr. 27 FHG III 42]" on both line 16 and
  // line 33) are told apart by where they sit, never by their text alone
  // (John, 2026-09-28, GPT-6-Sol review finding). See `numberFor` in
  // Reader.svelte's `dkAnnotate`, the only reader of these two fields.
  line: string;
  start: number;
}

// Number one DK column's notes in reading order (the column's Greek lines in
// order, left to right), from 1. Every occurrence gets its own number and
// its own print entry -- even the SAME bracket text printed twice, as
// Empedocles testimonia A1 does, is two notes, because it is two distinct
// places in the apparatus a reader might follow up separately. Every
// renderer of the column's Greek -- a source heading, a paragraph, a
// witness row cut from the same lines -- shows a slice of these lines, so
// an occurrence is found again by its (line, offset) identity, falling
// back to its printed text only for a renderer that reproduces a MODIFIED
// line (a source-citation head's `headText` override, a witness row's
// excerpt) where no exact line match exists.
export function numberEditionNotes(lines: readonly string[]): NumberedEditionNote[] {
  const notes: NumberedEditionNote[] = [];
  for (const line of lines) {
    for (const span of findEditionNotes(line)) {
      notes.push({ n: notes.length + 1, text: span.text, line, start: span.start });
    }
  }
  return notes;
}

// A note marker among a line's render parts. `lead` -- when present -- is
// the render part immediately before the marker, pulled out of the normal
// part stream so Reader.svelte can wrap it together with the marker in one
// `white-space: nowrap` span (the .fn-marker/.fn-anchor pattern): an atomic
// inline box like the marker <button> can still take a line-break
// opportunity at its own edge even with no space there (WKWebView
// especially), which would orphan the number onto the next line, away from
// the word it marks.
export type DkNotePart = { kind: 'dknote'; n: number; text: string; lead?: DkRenderPart };
export type DkNoteRenderPart = DkRenderPart | DkFillPart | DkNotePart;

// Replace each note span in a line's render parts with one 'dknote' part.
// `parts` must reproduce `text` (lineRenderParts' contract: every
// non-'speaker' part's text, concatenated, is `text`), and `spans` must be
// sorted and non-overlapping. A part wholly inside a span is dropped (the
// pop-up prints the bracket from `span.text`); a part straddling a span edge
// is cut, its outside piece kept as plain text. `numberFor` gives an
// occurrence's number (matched by its own (line, offset) identity, from
// numberEditionNotes -- see that function's doc comment on why identity,
// not text, is what distinguishes two occurrences of the same bracket); a
// span it cannot number stays as text. It is called once per span, on the
// span exactly as `findEditionNotes` found it (before the leading-space
// glue below), so its offset matches what numberEditionNotes recorded.
// The one space DK prints before a bracket goes with it, so the number sits
// against the word it follows ("Ἀρίσταρχος¹ καὶ"), as a note mark does --
// and that preceding part (never a 'speaker', which carries no text of its
// own) is pulled off `out` onto the 'dknote' part's own `lead`, so the two
// render as one glued unit.
export function applyEditionNotes(
  text: string,
  parts: readonly (DkRenderPart | DkFillPart)[],
  spans: readonly EditionNoteSpan[],
  numberFor: (span: EditionNoteSpan) => number | undefined,
): DkNoteRenderPart[] {
  const live = spans
    .map((s) => ({ ...s, n: numberFor(s) }))
    .filter((s): s is EditionNoteSpan & { n: number } => s.n !== undefined)
    .map((s) => (s.start > 0 && text[s.start - 1] === ' ' ? { ...s, start: s.start - 1 } : s));
  if (!live.length) return parts as DkNoteRenderPart[];
  const out: DkNoteRenderPart[] = [];
  let ptr = 0;
  let si = 0;
  const pushText = (t: string) => { if (t) out.push({ kind: 'text', text: t }); };
  for (const part of parts) {
    if (part.kind === 'speaker') { out.push(part); continue; }
    const start = ptr;
    const end = ptr + part.text.length;
    ptr = end;
    // Spans that ended before this part are done.
    while (si < live.length && live[si]!.end <= start) si += 1;
    const span = live[si];
    if (!span || span.start >= end) { out.push(part); continue; }
    // This part meets one or more spans.
    let cursor = start;
    let k = si;
    while (k < live.length && live[k]!.start < end) {
      const s = live[k]!;
      if (s.start > cursor) pushText(text.slice(cursor, s.start));
      if (s.start >= start) {
        const prev = out[out.length - 1];
        const gluesTo = prev?.kind === 'token' || prev?.kind === 'text' || prev?.kind === 'dklink';
        const lead = gluesTo ? (out.pop() as DkRenderPart) : undefined;
        out.push({ kind: 'dknote', n: s.n, text: s.text, lead });
      }
      cursor = Math.min(s.end, end);
      if (s.end > end) break;
      k += 1;
    }
    // What is left of a part a span cut into is plain text.
    if (cursor < end) pushText(text.slice(cursor, end));
  }
  return out;
}
