import type { CitationHead, ContextEnglishSpan, GreekLine, Segment } from './data';
import { buildProseFlow, columnLineates, sliceLineRange, type ProseFlowItem } from './prose-flow';

export type DkItem =
  | { kind: 'source-head'; line: GreekLine }
  | { kind: 'flow'; prose: Extract<ProseFlowItem, { kind: 'flow' }>; anchor: boolean }
  | { kind: 'line'; line: GreekLine }
  | { kind: 'table'; rows: GreekLine[] };

export interface DkSourceRow {
  head?: CitationHead;
  lines: GreekLine[];
  items: DkItem[];
  contextIndexes: number[];
  ownsEnglish: boolean;
}

// Source-passage records use translated titles; the dictionary uses edition
// titles. These are exact aliases, never fuzzy author-only matches.
const workAliases: Record<string, string> = {
  'Lives of Eminent Philosophers': 'Vitae Philosophorum',
  Metaphysics: 'Metaphysica', Physics: 'Physica',
  'On Generation and Corruption': 'De Generatione et Corruptione',
  'On the Heavens': 'De Caelo', Meteorology: 'Meteorologica', Rhetoric: 'Rhetorica',
  'Generation of Animals': 'De Generatione Animalium',
  'Parts of Animals': 'De Partibus Animalium', 'Sense and Sensibilia': 'De Sensu',
  'On Youth, Old Age, Life and Death, and Respiration': 'De Respiratione',
  'Sophistical Refutations': 'De Sophisticis Elenchis',
  'Nicomachean Ethics': 'Ethica Nicomachea', Politics: 'Politica', Poetics: 'Poetica',
  'History of Animals': 'Historia Animalium', Topics: 'Topica',
  'Hippias Major': 'Hippias Maior', Apology: 'Apologia', Sophist: 'Sophista',
  Republic: 'Respublica', Laws: 'Leges',
  'On the Natural Faculties': 'De Naturalibus Facultatibus',
};
const canonical = (s: string) => (workAliases[s] ?? s).normalize('NFC').toLocaleLowerCase();
export function sourceMatches(head: CitationHead, span: ContextEnglishSpan): boolean {
  return head.expanded.some(e => canonical(e.authorDisplay ?? '') === canonical(span.sourceAuthor)
    && canonical(e.work?.title ?? '') === canonical(span.sourceWork));
}

export function contextSectionMarkerNumbers(seg: Segment): Set<number> | undefined {
  const nums = new Set<number>();
  for (const span of seg.contextEnglish ?? []) {
    for (const locus of span.sectionLoci ?? []) {
      const m = /(\d+)\s*$/.exec(locus);
      if (m) nums.add(Number(m[1]));
    }
  }
  if ((seg.wholeColumnVerbatim && seg.english?.credit) || seg.sectionParagraphSplit) {
    for (const m of (seg.english?.text ?? '').matchAll(/\((\d+)\)/g)) nums.add(Number(m[1]));
  }
  return nums.size ? nums : undefined;
}

/** Build gate C10: a span that names its heading (headText) must sit under
 * a heading printed with that text, and alone. */
export function headTextFaults(seg: Segment, rows: DkSourceRow[]): string[] {
  const faults: string[] = [];
  (seg.contextEnglish ?? []).forEach((span, i) => {
    if (span.headText === undefined) return;
    const owner = rows.find(r => r.contextIndexes.includes(i));
    if (owner?.head?.text !== span.headText) faults.push(`contextEnglish[${i}] names heading "${span.headText}", which no heading in the column prints`);
    else if (owner.contextIndexes.length > 1) faults.push(`contextEnglish[${i}] shares heading "${span.headText}" with another source passage`);
  });
  return faults;
}

/** The reader and build gate both consume these exact items and source rows.
 * Locations are authoritative; no reader-side source-head detection occurs.
 */
export function buildDkSourceRows(seg: Segment, hasUserFacingLines = false, incipit = false): DkSourceRow[] {
  if (seg.citationHeads === undefined) throw new Error(`${seg.id}: missing citationHeads; regenerate DK data`);
  const rows: DkSourceRow[] = [];
  let row: DkSourceRow = { lines: [], items: [], contextIndexes: [], ownsEnglish: false };
  const flush = () => { if (row.head || row.lines.length) rows.push(row); };
  let hi = 0;
  for (let li = 0; li < seg.greek.length; li++) {
    const line = seg.greek[li]!;
    let cursor = 0;
    while (hi < seg.citationHeads.length && seg.citationHeads[hi]!.lineIndex === li) {
      const head = seg.citationHeads[hi++]!;
      if (head.line !== line.n || head.start < cursor || head.end <= head.start
        || head.end > line.text.length || line.text.slice(head.start, head.end) !== head.text) {
        throw new Error(`${seg.id}: stale citation location ${li}:${head.start}`);
      }
      if (line.text.slice(cursor, head.start).trim()) row.lines.push(sliceLineRange(line, cursor, head.start));
      flush();
      row = { head, lines: [], items: [{ kind: 'source-head', line: sliceLineRange(line, head.start, head.end) }], contextIndexes: [], ownsEnglish: false };
      cursor = head.end;
    }
    if (line.text.slice(cursor).trim() || (!line.text && !cursor)) row.lines.push(sliceLineRange(line, cursor, line.text.length));
  }
  flush();
  if (hi !== seg.citationHeads.length) throw new Error(`${seg.id}: unordered or missing citation lines`);
  if (!rows.length) rows.push(row);

  // A span naming its heading (headText) binds to the first unbound heading
  // printed with that text; if every such heading is bound it doubles up on
  // the last, and the gate fails. Other spans consume the remaining headings
  // of their source in document order; extra spans for a single source stay
  // on its last remaining heading; unmatched spans fail the gate.
  const spans = seg.contextEnglish ?? [];
  const byText = new Set<DkSourceRow>();
  const owners: (DkSourceRow | undefined)[] = spans.map(span => {
    if (span.headText === undefined) return undefined;
    const named = rows.filter(r => r.head?.text === span.headText);
    const owner = named.find(r => !byText.has(r)) ?? named.at(-1);
    if (owner) byText.add(owner);
    return owner;
  });
  const used = new Map<string, number>();
  for (const [si, span] of spans.entries()) {
    if (span.headText !== undefined) continue;
    const matches = rows.filter(r => r.head && !byText.has(r) && sourceMatches(r.head, span));
    const key = `${canonical(span.sourceAuthor)}|${canonical(span.sourceWork)}`;
    const index = used.get(key) ?? 0;
    owners[si] = matches[Math.min(index, matches.length - 1)];
    if (owners[si]) used.set(key, index + 1);
  }
  for (const [si, owner] of owners.entries()) {
    if (owner) owner.contextIndexes.push(si);
    else rows.push({ lines: [], items: [], contextIndexes: [si], ownsEnglish: false });
  }
  // Freeman's fragment English has no per-source offsets. Its quoted text
  // belongs to the first source containing a text run, otherwise the first
  // source with a passage (testimonia and whole-column translations).
  const owner = rows.find(r => r.lines.some(l => l.role === 'text'))
    ?? rows.find(r => r.lines.some(l => l.text.trim())) ?? rows[0]!;
  owner.ownsEnglish = true;
  const lineate = columnLineates(seg.greek, hasUserFacingLines);
  let anchored = false;
  for (const r of rows) {
    const local = { ...seg, contextEnglish: r.contextIndexes.map(i => seg.contextEnglish![i]!),
      english: r.ownsEnglish ? seg.english : null };
    const markers = contextSectionMarkerNumbers(local)
      ?? (rows.some(row => !row.head && row.contextIndexes.length) ? contextSectionMarkerNumbers(seg) : undefined);
    let buffer: GreekLine[] = [];
    const flushBody = () => {
      for (const item of buildProseFlow(buffer, { incipit, sourceHeadsProvided: true,
        sectionMarkerNumbers: markers, markerScanIncludesText: seg.sectionParagraphSplit })) {
        if (item.kind !== 'flow') throw new Error('Declared body produced a source head');
        r.items.push({ kind: 'flow', prose: item, anchor: !lineate && !anchored });
        anchored = true;
      }
      buffer = [];
    };
    for (const l of r.lines) {
      if (l.cells?.length) { flushBody(); r.items.push({ kind: 'table', rows: [l] }); }
      else if ((lineate && l.role !== 'context') || ['lacuna', 'heading', 'salutation'].includes(l.role ?? '') || l.seamNote) {
        flushBody(); r.items.push({ kind: 'line', line: l });
      } else buffer.push(l);
    }
    flushBody();
  }
  return rows;
}
