// DK prose-flow helpers — design of record: docs/prose-flow-design.md.
// Pure functions so join/grouping cannot drift per-work. Presentation only;
// line records and the Greek spine are unchanged.

import type { GreekLine, Token } from './data';

// §4: closing / sentence punctuation — run B hugs the preceding run (no space).
// Characters from the design's CLOSE set (deduped), plus Greek ano teleia
// (U+0387), which DK prose uses at the same seam shape as middle dot (·).
const CLOSE = new Set([
  '.', ',', ';', ':', '·', '·', '!', '?', ')', ']', '}', '…', '’', '”', '»', "'", '"',
]);

// §4: opening punctuation — run A hugs the following run (no space).
const OPEN = new Set(['(', '[', '{', '«', '‘', '“', '¡', '¿']);

/** True when the seam between two adjacent role-run strings needs a single space. */
export function needsFlowSpace(prev: string, next: string): boolean {
  const a = prev.replace(/\s+$/u, '');
  const b = next.replace(/^\s+/u, '');
  if (!a || !b) return false;
  const aLast = a[a.length - 1]!;
  const bFirst = b[0]!;
  if (CLOSE.has(bFirst)) return false;
  if (OPEN.has(aLast)) return false;
  return true;
}

/** A declared user-facing citable line: role='text' with positive n under a line-bearing scheme. */
export function isCitableTextLine(
  line: Pick<GreekLine, 'role' | 'n'>,
  hasUserFacingLines: boolean,
): boolean {
  return hasUserFacingLines && line.role === 'text' && line.n > 0;
}

/**
 * A column lineates (block-per-line, line numbers) iff it carries a declared
 * citable text line. Every other DK column flows. Never re-derived from content.
 */
export function columnLineates(
  lines: readonly Pick<GreekLine, 'role' | 'n'>[],
  hasUserFacingLines: boolean,
): boolean {
  return lines.some((l) => isCitableTextLine(l, hasUserFacingLines));
}

/**
 * DK witness-row substitution eligibility (Segment.witnesses, dk_witness.py's
 * split wired in stage7_emit.py): a segment's `witnesses` list is safe to
 * render as separate rows only when its role='context' content lives in
 * exactly ONE buffer that the render loop would flush as pure context --
 * no role='text' sharing that buffer (an "embedded" quotation interleaved
 * inline with its surrounding narrative, e.g. Empedocles B7/B58/B92's
 * `kind: embedded` — measured corpus-wide: ~72 of 233 split columns are
 * this shape) and no SECOND, separate context run elsewhere in the column
 * (a leading + trailing context pair, e.g. a div_map merge — 2 of 233,
 * both Critias) that substitution would either duplicate or silently drop.
 * Mirrors Reader.svelte's greekItems' own ctxBuf (lineate)/proseBuf (prose)
 * buffering rule exactly, since that is the render loop this gates -- a
 * table-cell line (`cells`) is its own item and never shares a buffer with
 * either. Everywhere this returns false, the segment renders exactly as it
 * did before `witnesses` existed.
 */
export function singlePureContextRun(
  lines: readonly Pick<GreekLine, 'role' | 'seamNote' | 'cells'>[],
  lineate: boolean,
): boolean {
  type L = (typeof lines)[number];
  const buffers: L[][] = [];
  let buf: L[] = [];
  const flush = () => { if (buf.length) { buffers.push(buf); buf = []; } };
  for (const l of lines) {
    if (l.cells?.length) { flush(); continue; }
    if (lineate) {
      if (l.role === 'context' && !l.seamNote) buf.push(l);
      else flush();
    } else if (l.role === 'lacuna' || l.role === 'salutation' || l.role === 'heading' || l.seamNote) {
      flush();
    } else {
      buf.push(l);
    }
  }
  flush();
  const ctxBuffers = buffers.filter((b) => b.some((l) => l.role === 'context'));
  return ctxBuffers.length === 1 && ctxBuffers[0]!.every((l) => l.role === 'context');
}

/** Greek letter present → not a pure source-citation head (post-draft ruling). */
const GREEK_LETTER = /[\u0370-\u03FF\u1F00-\u1FFF]/u;

/** Quotes / brackets at the head|body seam attach to the body side. */
const BODY_BOUNDARY_PUNCT = new Set([
  "'", '"', '’', '”', '‘', '“', '«', '»', '(', ')', '[', ']', '{', '}',
]);

export function isPureSourceHeadText(text: string): boolean {
  return text.trim().length > 0 && !GREEK_LETTER.test(text);
}

function isGreekChar(ch: string): boolean {
  return GREEK_LETTER.test(ch);
}

/** True for a lowercase Greek letter (case-fold differs from upper). */
function isLowercaseGreekChar(ch: string): boolean {
  return isGreekChar(ch) && ch !== ch.toUpperCase();
}

function hasLowercaseGreek(s: string): boolean {
  for (const ch of s) {
    if (isLowercaseGreekChar(ch)) return true;
  }
  return false;
}

function hasLatinOrNumeral(s: string): boolean {
  return /[A-Za-z0-9]/.test(s);
}

/**
 * Non-whitespace token is all-caps Greek (title material): has Greek letters,
 * none lowercase, no Latin letters. Punctuation/digits may cling.
 */
function isAllCapsGreekToken(token: string): boolean {
  let sawGreek = false;
  for (const ch of token) {
    if (isLowercaseGreekChar(ch)) return false;
    if (isGreekChar(ch)) {
      sawGreek = true;
      continue;
    }
    if (/[A-Za-z]/.test(ch)) return false;
  }
  return sawGreek;
}

/** Latin-script and/or numeral/section-marker token (no Greek letters). */
function isLatinOrNumeralToken(token: string): boolean {
  if (GREEK_LETTER.test(token)) return false;
  return hasLatinOrNumeral(token);
}

function isPurePunctToken(token: string): boolean {
  return !GREEK_LETTER.test(token) && !/[A-Za-z0-9]/.test(token);
}

/**
 * Head-shaped token: all-caps Greek title word, Latin/numeral citation piece,
 * or pure punctuation glue between those. Tokens with lowercase Greek are body.
 */
function isHeadMaterialToken(token: string): boolean {
  if (hasLowercaseGreek(token)) return false;
  if (isAllCapsGreekToken(token)) return true;
  if (isLatinOrNumeralToken(token)) return true;
  if (isPurePunctToken(token)) return true;
  return false;
}

/**
 * Whole string is a source-citation head (no body): every token is head
 * material, no lowercase Greek, and at least one Latin letter or numeral.
 * Covers pure Latin apparatus and Greek-initial titles + Latin citation
 * (Critias B31: ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F). Bare all-caps Greek
 * without a Latin/numeral citation is NOT a head (may be title-kind content).
 */
export function isSourceHeadOnlyText(text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (hasLowercaseGreek(t)) return false;
  const tokens = t.match(/\S+/gu);
  if (!tokens?.length) return false;
  let sawLatinOrNum = false;
  for (const tok of tokens) {
    if (!isHeadMaterialToken(tok)) return false;
    if (hasLatinOrNumeral(tok)) sawLatinOrNum = true;
  }
  return sawLatinOrNum;
}

/**
 * Within a token that mixes head material with lowercase Greek body (e.g.
 * fused `662F'ὁμολογοῦνται`), return the exclusive end offset of the head
 * prefix. Quotes/brackets immediately before the body attach to the body.
 * Returns 0 when the whole token is body (e.g. Ὅμηρος — capital + lowercase).
 * Only a Latin/numeral-bearing prefix counts (never peel a bare Greek capital).
 */
function headPrefixLenInMixedToken(token: string): number {
  let firstLower = -1;
  for (let i = 0; i < token.length; i++) {
    if (isLowercaseGreekChar(token[i]!)) {
      firstLower = i;
      break;
    }
  }
  if (firstLower < 0) return token.length;

  let bodyStart = firstLower;
  while (bodyStart > 0 && BODY_BOUNDARY_PUNCT.has(token[bodyStart - 1]!)) {
    bodyStart--;
  }
  if (bodyStart === 0) return 0;

  const prefix = token.slice(0, bodyStart);
  // Conservatism: require Latin/numeral in the in-token prefix so Ὅμηρος
  // does not peel its leading capital onto the head.
  if (!hasLatinOrNumeral(prefix)) return 0;
  if (hasLowercaseGreek(prefix)) return 0;
  return bodyStart;
}

/**
 * DK print-line hyphen artifact: a hyphen immediately followed by whitespace
 * BETWEEN two Greek letters is not a real compound marker — join the word
 * (ἠνδρο- τόμησε → ἠνδροτόμησε, ἡγε- μονίας → ἡγεμονίας).
 *
 * Conservative: only heals when the char before `-` and the first non-space
 * char after it are both Greek letters. Latin citations (`adv. math.`),
 * Latin hyphens, and digit/Latin contexts are never touched.
 */
export function healGreekPrintHyphens(text: string): string {
  return text.replace(
    /([\u0370-\u03FF\u1F00-\u1FFF])-\s+([\u0370-\u03FF\u1F00-\u1FFF])/gu,
    '$1$2',
  );
}

/**
 * Peel a source-citation prefix from a mixed context string.
 *
 * Boundary rule (John 2026-07-24, Critias B31): head material is (a) all-caps
 * Greek title words, (b) Latin-script tokens, (c) numerals / roman numerals /
 * section markers (662F, XIV, II, …) and punctuation between them. The head
 * ends at the first token that contains lowercase Greek (intra-token split
 * when Latin/numeral fuses to body without a space). The head must contain at
 * least one Latin letter or numeral — bare all-caps Greek is not a head.
 * Quote-marks and brackets at the seam attach to the body.
 *
 * Returns null when there is no peelable head (no body rest, no Latin/numeral
 * citation, or empty). Whole-line heads with no rest use isSourceHeadOnlyText
 * in buildProseFlow instead.
 */
export function peelSourceHeadPrefix(
  text: string,
): { head: string; rest: string; restOffset: number } | null {
  const tokenRe = /\S+/gu;
  const tokens: { t: string; start: number; end: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = tokenRe.exec(text)) !== null) {
    tokens.push({ t: m[0], start: m.index, end: m.index + m[0].length });
  }
  if (!tokens.length) return null;

  let sawLatinOrNum = false;
  let restOffset = -1;

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i]!;

    if (!hasLowercaseGreek(tok.t)) {
      if (!isHeadMaterialToken(tok.t)) {
        // Non-head, non-lowercase-Greek token → body starts here.
        restOffset = tok.start;
        break;
      }
      if (hasLatinOrNumeral(tok.t)) sawLatinOrNum = true;
      continue;
    }

    // Token contains lowercase Greek: whole token is body, unless a
    // Latin/numeral head prefix is fused without whitespace.
    const headLen = headPrefixLenInMixedToken(tok.t);
    if (headLen > 0) {
      const prefix = tok.t.slice(0, headLen);
      if (hasLatinOrNumeral(prefix)) sawLatinOrNum = true;
      restOffset = tok.start + headLen;
    } else {
      restOffset = tok.start;
    }
    break;
  }

  // Entire run is head-shaped (no lowercase Greek body) → no in-string peel.
  if (restOffset < 0) return null;

  const head = text.slice(0, restOffset).trim();
  if (!head || !sawLatinOrNum || !hasLatinOrNumeral(head)) return null;

  const rest = text.slice(restOffset);
  if (!rest.trim()) return null;

  // Head and rest render as separate items (source-head block + flow). When
  // the source fused them without whitespace (`662F'ὁμολογοῦνται`), rest keeps
  // body-side quotes; the block boundary supplies the visual separation.
  return { head, rest, restOffset };
}

function sliceLineFrom(line: GreekLine, text: string, fromOffset: number): GreekLine {
  const tokens: Token[] = (line.tokens ?? [])
    .filter((t) => t.o >= fromOffset)
    .map((t) => ({ ...t, o: t.o - fromOffset }));
  return { ...line, text, tokens };
}

/** Slice a line's text/tokens to the char range [start, end) — both ends bounded. */
function sliceLineRange(line: GreekLine, start: number, end: number): GreekLine {
  const text = line.text.slice(start, end);
  const tokens: Token[] = (line.tokens ?? [])
    .filter((t) => t.o >= start && t.o < end)
    .map((t) => ({ ...t, o: t.o - start }));
  return { ...line, text, tokens };
}

/**
 * DK's inline section-number convention: a context run (e.g. Diogenes
 * Laertius quoted whole in a testimonium's citation block) carries its own
 * paragraph divisions as literal "(NN)" markers in the Greek text — John's
 * dashboard note on thales/testimonia A1: the English below is already
 * split per-section (Hicks), so the Greek should mirror it, marker for
 * marker, for parallel alignment.
 *
 * Splits a body of lines into paragraph groups at each such marker (context-
 * role lines only — a role='text' quote line's own parenthetical is not this
 * convention and is never split). The marker text itself is removed from the
 * flowing prose and returned as the group's `marker` (rendered separately,
 * same idea as the source-passage English's per-paragraph section label).
 * A body with no markers returns a single group, byte-identical to the
 * pre-split behaviour.
 *
 * Gating (fix round, finding 1 — Sol review): a bare "(NN)" is common DK
 * apparatus for all sorts of things that are NOT this convention —
 * bibliographic years ("(1848)"), cross-references, page refs. Splitting on
 * the regex alone false-positived on Gorgias A10's "[Neue Jahrb. Suppl. 14
 * (1848) ed. A. Jahn]". `markerNumbers` is the set of section numbers
 * actually named by this segment's own contextEnglish spans (derived from
 * their `sectionLoci` by Reader.svelte — see buildProseFlowOpts doc); a
 * parenthesized integer only becomes a split point when BOTH a set is
 * supplied (parallel English exists) AND the integer is a member of it. No
 * set (or an empty one) — the overwhelmingly common case — skips the regex
 * scan entirely, so every column with no declared contextEnglish renders
 * byte-identical to pre-split behaviour by construction, not by regex luck.
 *
 * Fix round (re-review, finding 1): set membership alone still false-
 * positived on an ordinary cross-reference sharing a declared section
 * number (e.g. "(23)" cited in passing while section 22 is the running
 * paragraph). Two further gates, both required:
 *  (a) Sequence — accepted markers must consume the declared numbers in
 *      ascending order. The first accepted marker must equal the smallest
 *      number in the set; each subsequent one must equal the smallest
 *      remaining number greater than the last accepted marker. A set
 *      member seen out of that order is left as literal text.
 *  (b) Position — a marker must sit at the start of its line/run, or be
 *      immediately preceded (skipping intervening whitespace) by
 *      sentence-final punctuation, matching DK's own print convention
 *      ("λαμπροῦ. (23) μετὰ"). A parenthesized number fused onto a word
 *      with no sentence boundary is never a marker.
 */
const SECTION_MARKER_RE = /\((\d+)\)/g;

/** DK sentence-final punctuation that may precede a genuine "(NN)" marker. */
const MARKER_BOUNDARY_PUNCT = new Set(['.', '·', '·', ';', ']']);

/** True when `matchStart` sits at the line's start, or after sentence-final punctuation. */
export function isMarkerPosition(text: string, matchStart: number): boolean {
  let i = matchStart;
  while (i > 0 && /\s/.test(text[i - 1]!)) i--;
  if (i === 0) return true;
  return MARKER_BOUNDARY_PUNCT.has(text[i - 1]!);
}

/**
 * Fix round (Sol adversarial review on commit 7287b10, finding 1): the
 * English side of a whole-column-verbatim/section-paragraph-split column
 * used to split on EVERY "(N)" in its text, with none of the Greek side's
 * validation — a stray mid-text citation like "(12)" split a paragraph the
 * Greek never did. This is the sequence half of that validation (set
 * membership + ascending-by-1 consumption, exactly `splitContextMarkerGroups`'
 * rule above), factored out so both the Greek context-scan and the English
 * scan (Reader.svelte's `splitSegment`) accept the same marker under the
 * same rule rather than reimplementing it. Returns a stateful acceptor: call
 * it once per candidate match, in document order, only for matches that
 * already passed `isMarkerPosition` (the position half, checked by the
 * caller since it needs the caller's own text/matchStart).
 */
export function createMarkerSequenceAcceptor(
  markerNumbers: ReadonlySet<number>,
): (value: number) => boolean {
  const sortedMarkers = Array.from(markerNumbers).sort((a, b) => a - b);
  let lastAccepted: number | undefined;
  return (value: number): boolean => {
    if (!markerNumbers.has(value)) return false;
    const expected =
      lastAccepted === undefined ? sortedMarkers[0] : sortedMarkers.find((n) => n > lastAccepted!);
    if (expected === undefined || value !== expected) return false;
    lastAccepted = value;
    return true;
  };
}

/**
 * Scan `text` for "(N)" markers validated by membership + ascending-run
 * discipline — the English-side counterpart to `splitContextMarkerGroups`'s
 * Greek scan, sharing its sequence rule via `createMarkerSequenceAcceptor`
 * rather than duplicating it. Returns accepted matches in document order; a
 * stray out-of-sequence "(NN)" (a footnote or cross-reference sharing no
 * relation to the declared run) is simply absent from the result, left for
 * the caller to render as plain text.
 *
 * Never REQUIRES `isMarkerPosition`'s sentence-boundary check: unlike the
 * Greek side, which scans one context LINE at a time (so a marker opening
 * its own line trivially sits at that line's start), the English side
 * scans one CONTINUOUS string that often runs a heading straight into its
 * first marker with no sentence break at all ("Encomium of Helen (1) Good
 * order…", Gorgias B11) — a mandatory boundary there would silently drop
 * the legitimate first split. Membership + ascending sequence alone,
 * though, has a second failure mode (Sol review, commit b69eae5, finding
 * 1): a stray citation sharing the currently-EXPECTED value (a bare "(5)"
 * quoted in passing just before the real section (5)) used to win simply
 * by coming first in scan order, leaving the genuine "(5)" rejected as
 * out-of-sequence. So for each expected value, every one of ITS
 * occurrences in the remaining text is considered (not just the first):
 * one sitting at `isMarkerPosition`'s boundary is preferred when any does;
 * otherwise the first occurrence stands, preserving the heading-with-no-
 * boundary case above. A stray value that never matches what's currently
 * expected is untouched by this — it is never a candidate at all, exactly
 * as before.
 *
 * Preferring a boundary occurrence must never strand a LATER expected
 * value (Sol review, commit 6355e73, finding 2: a late boundary "(5)"
 * chosen greedily could sit past the only "(6)"). So candidates are
 * filtered to VIABLE ones first — those that still leave a viable
 * occurrence of every remaining expected value strictly after them,
 * computed by a backward pass — and the boundary preference applies
 * within the viable set only. Known, accepted limit (same review,
 * finding 1): two occurrences of the SAME expected value both at
 * sentence boundaries before the real one are indistinguishable from
 * local evidence; the first wins, as any local rule must pick one.
 */
export function scanSectionMarkers(
  text: string,
  markerNumbers: ReadonlySet<number> | undefined,
): { index: number; length: number; value: number }[] {
  if (!markerNumbers || markerNumbers.size === 0) return [];
  const sortedMarkers = Array.from(markerNumbers).sort((a, b) => a - b);
  const re = /\((\d+)\)/g;
  const occurrences: { index: number; length: number; value: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const value = Number(m[1]);
    if (markerNumbers.has(value)) occurrences.push({ index: m.index, length: m[0].length, value });
  }
  // Backward pass: maxViableStart[i] is the latest start an occurrence of
  // expected value i may have while a complete chain through every later
  // value still exists. An occurrence of value i is viable iff it ends at
  // or before maxViableStart[i+1] — the occurrence achieving that maximum
  // is itself viable and starts after it. NaN marks an unsatisfiable tail.
  const maxViableStart: number[] = new Array(sortedMarkers.length).fill(Number.NaN);
  for (let i = sortedMarkers.length - 1; i >= 0; i--) {
    const value = sortedMarkers[i]!;
    const laterLimit = i + 1 < sortedMarkers.length ? maxViableStart[i + 1]! : Number.POSITIVE_INFINITY;
    const viable = occurrences.filter(
      (o) => o.value === value && (Number.isNaN(laterLimit) || o.index + o.length <= laterLimit),
    );
    if (viable.length > 0) maxViableStart[i] = Math.max(...viable.map((o) => o.index));
  }
  const out: { index: number; length: number; value: number }[] = [];
  let searchFrom = 0;
  for (let i = 0; i < sortedMarkers.length; i++) {
    const expected = sortedMarkers[i]!;
    const all = occurrences.filter((o) => o.value === expected && o.index >= searchFrom);
    if (all.length === 0) break;
    // Prefer candidates that keep the rest of the chain reachable; if none
    // do (the tail is unsatisfiable regardless), fall back to all of them,
    // preserving the prior greedy behavior.
    const laterLimit = i + 1 < sortedMarkers.length ? maxViableStart[i + 1]! : Number.POSITIVE_INFINITY;
    const viable = Number.isNaN(laterLimit)
      ? all
      : all.filter((o) => o.index + o.length <= laterLimit);
    const pool = viable.length > 0 ? viable : all;
    const chosen = pool.find((o) => isMarkerPosition(text, o.index)) ?? pool[0]!;
    out.push(chosen);
    searchFrom = chosen.index + chosen.length;
  }
  return out;
}

function splitContextMarkerGroups(
  lines: readonly GreekLine[],
  markerNumbers: ReadonlySet<number> | undefined,
  scanTextLines = false,
): { lines: GreekLine[]; marker?: string }[] {
  const groups: { lines: GreekLine[]; marker?: string }[] = [{ lines: [] }];
  if (!markerNumbers || markerNumbers.size === 0) {
    // No parallel English section declared for this segment: the "(NN)"
    // convention never applies here — every line is body, untouched.
    for (const line of lines) groups[0]!.lines.push(line);
    return groups;
  }
  // Persists across every context line in this body: markers are consumed
  // in one ascending sequence over the whole run, not per-line.
  const acceptMarker = createMarkerSequenceAcceptor(markerNumbers);
  for (const line of lines) {
    // Ordinarily only a role='context' (quoting frame) line is scanned for
    // "(NN)" markers — a citable role='text' line is the quotation itself
    // and (for every pre-existing caller) never carries the convention.
    // `scanTextLines` (item 85's Melissus B7/B8 addendum:
    // Segment.sectionParagraphSplit) opts a column INTO scanning its
    // role='text' lines too — Simplicius's ascending "(N)" listing sits
    // inside the quotation itself there, not in the surrounding frame.
    // False for every other caller, byte-identical to before this option
    // existed.
    if (line.role !== 'context' && !(scanTextLines && line.role === 'text')) {
      groups[groups.length - 1]!.lines.push(line);
      continue;
    }
    const text = line.text;
    SECTION_MARKER_RE.lastIndex = 0;
    let cursor = 0;
    let any = false;
    let m: RegExpExecArray | null;
    while ((m = SECTION_MARKER_RE.exec(text)) !== null) {
      // Not one of the declared section numbers: an ordinary parenthesized
      // integer (bibliographic year, cross-ref, page number) — leave it as
      // literal text; cursor stays put so it's swept up by the next real
      // split's `pre` slice (or the final untouched push if none follows).
      const value = Number(m[1]);
      const matchStart = m.index;
      // Not at a valid boundary (line start / sentence-final punctuation) —
      // an ordinary cross-reference, not a genuine DK marker; leave as
      // literal text so a later, properly-positioned occurrence can match.
      if (!isMarkerPosition(text, matchStart)) continue;
      // Not one of the declared section numbers, or out of the ascending
      // sequence (not the next expected number) — a stray set-member
      // integer that is not this convention's marker; leave as literal text;
      // cursor stays put so it's swept up by the next real split's `pre`
      // slice (or the final untouched push if none follows).
      if (!acceptMarker(value)) continue;
      any = true;
      // A single space right after the marker (the universal print shape,
      // "(22) Ἦν …") is swallowed too, so the next paragraph's text never
      // opens with a stray leading space.
      let matchEnd = matchStart + m[0].length;
      if (text[matchEnd] === ' ') matchEnd += 1;
      if (matchStart > cursor) {
        const pre = sliceLineRange(line, cursor, matchStart);
        if (pre.text.trim() || pre.tokens.length) groups[groups.length - 1]!.lines.push(pre);
      }
      groups.push({ lines: [], marker: m[1] });
      cursor = matchEnd;
    }
    if (!any) {
      groups[groups.length - 1]!.lines.push(line);
      continue;
    }
    if (cursor < text.length) {
      const post = sliceLineRange(line, cursor, text.length);
      if (post.text.trim() || post.tokens.length) groups[groups.length - 1]!.lines.push(post);
    }
  }
  return reabsorbEmptyMarkerGroups(groups);
}

/**
 * Fix round, finding 3 — Sol review: a marker whose own group ends up with
 * NO body lines (Empedocles A31 ends "… προσδοκῶντες. (2)" — nothing
 * follows the last marker at all) used to just vanish: the "(2)" was
 * stripped from the text and pushFlow's `if (!bodyLines.length) return`
 * silently dropped the empty group, losing the marker text with nothing to
 * show for it. Under the new gating this shape must lose nothing: an empty
 * marker group is un-split — its literal "(NN)" is put back as ordinary
 * text at the tail of the previous group (never left to evaporate).
 *
 * Fix round (re-review, finding 2): a group is also "empty" when every one
 * of its lines is whitespace-only — a terminal marker immediately followed
 * by a blank separator line used to count as non-empty (lines.length > 0)
 * and render as a marker-labelled blank paragraph. The whitespace line
 * itself is never dropped: the marker is reabsorbed onto the last line with
 * real content, and the whitespace line(s) are kept, in place, after it.
 */
function reabsorbEmptyMarkerGroups(
  groups: { lines: GreekLine[]; marker?: string }[],
): { lines: GreekLine[]; marker?: string }[] {
  const out: { lines: GreekLine[]; marker?: string }[] = [];
  for (const g of groups) {
    const isEmpty = g.marker != null && g.lines.every((l) => !l.text.trim());
    if (isEmpty) {
      const literal = `(${g.marker})`;
      const prev = out[out.length - 1];
      // Attach to the last line with real content, never to a trailing
      // whitespace-only line already sitting in `prev` (that line stays
      // untouched, in place) — search backward rather than assume last.
      let contentIdx = -1;
      if (prev) {
        for (let i = prev.lines.length - 1; i >= 0; i--) {
          if (prev.lines[i]!.text.trim()) {
            contentIdx = i;
            break;
          }
        }
      }
      if (prev && contentIdx >= 0) {
        const last = prev.lines[contentIdx]!;
        const sep = last.text && !/\s$/.test(last.text) ? ' ' : '';
        prev.lines[contentIdx] = { ...last, text: last.text + sep + literal };
        prev.lines.push(...g.lines);
      } else if (prev) {
        prev.lines.push({ n: -1, role: 'context', text: literal, tokens: [] }, ...g.lines);
      } else {
        out.push({ lines: [{ n: -1, role: 'context', text: literal, tokens: [] }, ...g.lines] });
      }
      continue;
    }
    out.push(g);
  }
  return out;
}

function withHealedContextText(line: GreekLine): GreekLine {
  if (line.role !== 'context') return line;
  const healed = healGreekPrintHyphens(line.text);
  if (healed === line.text) return line;
  // Token strings stay; lineRenderParts finds them by indexOf in healed text
  // (hyphen+space gaps collapse so halves butt together).
  return { ...line, text: healed };
}

export type FlowRun = {
  line: GreekLine;
  /** Leading space before this run (false for the first run in a flow). */
  space: boolean;
  /** CSS role class: frag-txt | frag-ctx (incipit text-runs use frag-ctx). */
  cls: 'frag-txt' | 'frag-ctx';
  /** Extra wrapper class for declared incipit stubs. */
  incipit: boolean;
};

export type ProseFlowItem =
  | { kind: 'source-head'; line: GreekLine }
  | {
      kind: 'flow';
      lines: GreekLine[];
      runs: FlowRun[];
      incipit: boolean;
      /**
       * DK's inline "(NN)" section marker that opens this paragraph (see
       * splitContextMarkerGroups) — undefined for a body with no such
       * markers, or for a flow's first paragraph when nothing precedes the
       * first marker's own group.
       */
      sectionMarker?: string;
    };

export type BuildProseFlowOpts = {
  incipit?: boolean;
  /**
   * When true, a sole pure-Latin context run peels as source-head (verse-frame
   * streaks above lineated quote lines — those lines carry the column anchors).
   * Default false preserves the context-only column guard (never peel a flow's
   * only run — Antiphon B79–B81).
   */
  peelSoleSourceHead?: boolean;
  /**
   * DK inline "(NN)" section numbers this segment's own contextEnglish spans
   * declare (Reader.svelte derives this from each span's `sectionLoci` —
   * "1.22" → 22 — before calling buildProseFlow; see ContextEnglishSpan in
   * ./data). Gates splitContextMarkerGroups (fix round, finding 1): undefined
   * or empty means no parallel English section is declared for this segment,
   * so the "(NN)" convention never applies and the run renders exactly as it
   * did before the split existed.
   */
  sectionMarkerNumbers?: ReadonlySet<number>;
  /**
   * When true, splitContextMarkerGroups also scans role='text' lines for
   * "(NN)" markers, not only role='context' ones (item 85's Melissus B7/B8
   * addendum — Segment.sectionParagraphSplit: Simplicius's ascending listing
   * sits inside the quotation itself, not the surrounding frame). Default
   * false, byte-identical to before this option existed.
   */
  markerScanIncludesText?: boolean;
};

/**
 * Build presentation items for a prose (non-lineating) DK column, or for a
 * consecutive context streak in a lineating (verse) column.
 * Peels a leading source-citation head onto its own line when body runs
 * remain (or when peelSoleSourceHead and the sole run is head-only); mixed
 * citation+body leading context peels the head prefix (Latin-only or
 * Greek-initial title + Latin citation, ending at first lowercase Greek).
 * Remaining role-runs join into one flow paragraph with §4 seams; context
 * text is hyphen-healed.
 * Lacuna/salutation/table lines must be filtered out by the caller — this
 * only handles role text|context (and role-less lines as frag-txt).
 */
export function buildProseFlow(
  lines: readonly GreekLine[],
  opts: BuildProseFlowOpts = {},
): ProseFlowItem[] {
  const incipit = !!opts.incipit;
  const peelSole = !!opts.peelSoleSourceHead;
  if (!lines.length) return [];

  // DK inline "(NN)" section markers (John's thales/testimonia A1 note: the
  // Greek context block should paragraph-break in parallel with the
  // English's own per-section split) split the run into paragraph groups
  // FIRST, before any source-head peel — a marker sitting mid-line right
  // after a citation head (the common shape: "DIOGENES LAERTIUS I 22—44.
  // (22) Ἦν …") must not be mistaken by peelSourceHeadPrefix for a citation
  // numeral folded into the head. Only the group PRECEDING the first marker
  // (or the whole run, when there are no markers at all) can ever carry a
  // real source-citation head — every later group opens with body text.
  const rawGroups = splitContextMarkerGroups(lines, opts.sectionMarkerNumbers, opts.markerScanIncludesText);
  const items: ProseFlowItem[] = [];

  let start = 0;
  let bodyHead: GreekLine | null = null;
  const firstGroupLines = rawGroups[0]!.lines;

  // Post-draft: source-citation heads on their own hanging small-caps line.
  // (1) Whole-line head-only apparatus (pure Latin, or Greek-initial title +
  //     Latin/numeral citation) when body remains (or sole peel for verse
  //     frames).
  // (2) Mixed leading context: peel prefix through first lowercase Greek.
  // Never peel a context-only column's sole head run unless peelSoleSourceHead
  // (verse frames — quote lines supply anchors / lineation) — "body remains"
  // now also counts a later section-marker group, not just more lines in
  // this one.
  const hasBodyElsewhere = rawGroups.length > 1;
  const first = firstGroupLines[0];
  if (first && first.role === 'context') {
    if (isSourceHeadOnlyText(first.text)) {
      if (firstGroupLines.length > 1 || hasBodyElsewhere || peelSole) {
        items.push({ kind: 'source-head', line: first });
        start = 1;
      }
    } else {
      const peeled = peelSourceHeadPrefix(first.text);
      if (peeled) {
        items.push({
          kind: 'source-head',
          line: {
            ...first,
            text: peeled.head,
            tokens: (first.tokens ?? []).filter((t) => t.o < peeled.restOffset),
          },
        });
        // If the source fused head to body without whitespace, keep body text
        // as-is (quote stays on body); source-head and flow are separate
        // blocks so they never render as one fused run. Token offsets still
        // use restOffset against the original string.
        bodyHead = withHealedContextText(
          sliceLineFrom(first, peeled.rest, peeled.restOffset),
        );
        start = 1;
      }
    }
  }

  const firstBody: GreekLine[] = [];
  if (bodyHead) firstBody.push(bodyHead);
  for (let i = start; i < firstGroupLines.length; i++) {
    firstBody.push(withHealedContextText(firstGroupLines[i]!));
  }

  const pushFlow = (bodyLines: GreekLine[], marker: string | undefined) => {
    if (!bodyLines.length) return;
    const runs: FlowRun[] = [];
    for (let i = 0; i < bodyLines.length; i++) {
      const line = bodyLines[i]!;
      const isText = line.role !== 'context';
      // Incipit stubs: text-runs render as apparatus (frag-ctx) + frag-incipit.
      const asApparatus = !isText || incipit;
      runs.push({
        line,
        space: i > 0 && needsFlowSpace(bodyLines[i - 1]!.text, line.text),
        cls: asApparatus ? 'frag-ctx' : 'frag-txt',
        incipit: incipit && isText,
      });
    }
    // DOM anchor id is the segment column token only (Reader builds
    // `L{column}`); never first-run n — negative n produced broken ids
    // like "LB4--1".
    items.push({ kind: 'flow', lines: bodyLines, runs, incipit, sectionMarker: marker });
  };

  pushFlow(firstBody, undefined);
  for (let g = 1; g < rawGroups.length; g++) {
    const group = rawGroups[g]!;
    pushFlow(group.lines.map(withHealedContextText), group.marker);
  }

  return items;
}
