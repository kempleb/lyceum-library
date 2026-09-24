import { describe, expect, it } from 'vitest';
import {
  needsFlowSpace,
  columnLineates,
  isCitableTextLine,
  isPureSourceHeadText,
  isSourceHeadOnlyText,
  healGreekPrintHyphens,
  peelSourceHeadPrefix,
  buildProseFlow,
  scanSectionMarkers,
  singlePureContextRun,
} from '../lib/prose-flow';
import type { GreekLine } from '../lib/data';

const line = (
  n: number,
  role: GreekLine['role'],
  text: string,
): GreekLine => ({ n, role, text, tokens: [] });

describe('needsFlowSpace — prose-flow design §4', () => {
  it('joins with a space at a normal word seam', () => {
    expect(needsFlowSpace('κοπίδων', 'ἐστὶν')).toBe(true);
    expect(needsFlowSpace('τῶν ἀληθινῶν', 'κοπίδων')).toBe(true);
  });

  it('no space when run B starts with CLOSE punctuation (B81 `.`, B9 `·`, B1 `.`)', () => {
    expect(needsFlowSpace('ἀρχηγός', '. SCHOL.')).toBe(false);
    expect(needsFlowSpace('χρυσόν', '· ἥδιον')).toBe(false);
    expect(needsFlowSpace('χρυσόν', '· ἥδιον')).toBe(false); // Greek ano teleia
    expect(needsFlowSpace('ἐπιλανθάνονται', '.')).toBe(false);
    expect(needsFlowSpace('word', ', next')).toBe(false);
    expect(needsFlowSpace('word', '; next')).toBe(false);
    expect(needsFlowSpace('word', ': next')).toBe(false);
    expect(needsFlowSpace('word', '!')).toBe(false);
    expect(needsFlowSpace('word', '?')).toBe(false);
    expect(needsFlowSpace('word', ') more')).toBe(false);
    expect(needsFlowSpace('word', '] more')).toBe(false);
    expect(needsFlowSpace('word', '} more')).toBe(false);
    expect(needsFlowSpace('word', '…')).toBe(false);
    expect(needsFlowSpace('word', '’')).toBe(false);
    expect(needsFlowSpace('word', '”')).toBe(false);
    expect(needsFlowSpace('word', '»')).toBe(false);
  });

  it('no space when run A ends with OPEN punctuation', () => {
    expect(needsFlowSpace('says (', 'word')).toBe(false);
    expect(needsFlowSpace('says [', 'word')).toBe(false);
    expect(needsFlowSpace('says {', 'word')).toBe(false);
    expect(needsFlowSpace('says «', 'word')).toBe(false);
    expect(needsFlowSpace('says ‘', 'word')).toBe(false);
    expect(needsFlowSpace('says “', 'word')).toBe(false);
  });

  it('never double-spaces: trailing/leading whitespace on the inputs is ignored for the seam decision', () => {
    expect(needsFlowSpace('word ', ' next')).toBe(true);
    expect(needsFlowSpace('word ', '.')).toBe(false);
  });
});

describe('columnLineates — prose-flow design §2 (declaration only)', () => {
  it('lineless DK (hasUserFacingLines false): never lineates, even with positive n', () => {
    const lines = [
      line(1, 'context', 'SEXT. adv. math.'),
      line(2, 'text', 'τοῦ δὲ λόγου'),
    ];
    expect(columnLineates(lines, false)).toBe(false);
  });

  it('verse DK (hasUserFacingLines true + positive text n): lineates', () => {
    const lines = [
      line(-1, 'context', 'SEXT. VII 111'),
      line(1, 'text', 'ἵπποι ταί με φέρουσιν'),
      line(2, 'text', 'ὅσον τ\' ἐπὶ θυμὸς'),
    ];
    expect(columnLineates(lines, true)).toBe(true);
    expect(isCitableTextLine(lines[1]!, true)).toBe(true);
  });

  it('mixed-work prose column (positive-n scheme, negative sentinel text n): flows', () => {
    // Critias B31-area: citation.prose_columns → cite_n=None → n is negative.
    const lines = [
      line(-1, 'context', 'source'),
      line(-2, 'text', '’ὁμολογοῦνται…'),
    ];
    expect(columnLineates(lines, true)).toBe(false);
    expect(isCitableTextLine(lines[1]!, true)).toBe(false);
  });

  it('never treats content shape as verse (hexameter mid-prose stays flow)', () => {
    // B9-style: a metrical text-run under lineless dk still flows.
    const lines = [
      line(1, 'context', 'Arist. EN'),
      line(2, 'text', "ὄνους σύρματ' ἂν ἑλέσθαι μᾶλλον ἢ χρυσόν"),
      line(3, 'context', '· ἥδιον γὰρ'),
    ];
    expect(columnLineates(lines, false)).toBe(false);
  });
});

describe('singlePureContextRun — DK witness-row substitution eligibility (Segment.witnesses)', () => {
  it('lineless, context-only column: single pure buffer, eligible', () => {
    const lines = [line(1, 'context', 'ETYM. GEN. word. ANECD. word.')];
    expect(singlePureContextRun(lines, false)).toBe(true);
  });

  it('verse column: leading context frame before the verse quote, eligible', () => {
    const lines = [
      line(-1, 'context', 'SIMPL. Phys. 157, 25 witness.'),
      line(1, 'text', 'ἵπποι ταί με φέρουσιν'),
    ];
    expect(singlePureContextRun(lines, true)).toBe(true);
  });

  it('prose column with the quotation embedded inline (Empedocles B7/B58/B92 shape): ineligible', () => {
    const lines = [
      line(1, 'context', 'SIMPL. in Phys. quoting the phrase'),
      line(2, 'text', 'the actual Empedoclean words'),
      line(3, 'context', 'and PLUT. continuing the frame'),
    ];
    expect(singlePureContextRun(lines, false)).toBe(false);
  });

  it('verse column with two SEPARATE context frames (leading + trailing, Critias B16/B18 shape): ineligible', () => {
    const lines = [
      line(-1, 'context', 'leading frame'),
      line(1, 'text', 'ἵπποι ταί με φέρουσιν'),
      line(-2, 'context', 'trailing scholion'),
    ];
    expect(singlePureContextRun(lines, true)).toBe(false);
  });

  it('a table-cell line never joins a context buffer', () => {
    const withCells: GreekLine = { n: 1, role: 'context', text: '', tokens: [], cells: [{ text: 'x', tokens: [] }] };
    const lines = [line(1, 'context', 'ETYM. GEN. word.'), withCells, line(2, 'context', 'more.')];
    // Two separate context buffers on either side of the table row.
    expect(singlePureContextRun(lines, false)).toBe(false);
  });

  it('no context lines at all: ineligible (nothing to substitute)', () => {
    const lines = [line(1, 'text', 'plain verse')];
    expect(singlePureContextRun(lines, false)).toBe(false);
  });
});

describe('healGreekPrintHyphens', () => {
  it('heals Greek letter - whitespace - Greek letter (DK print-line breaks)', () => {
    expect(healGreekPrintHyphens('ἠνδρο- τόμησε')).toBe('ἠνδροτόμησε');
    expect(healGreekPrintHyphens('ἡγε- μονίας')).toBe('ἡγεμονίας');
    expect(healGreekPrintHyphens('Δη- μοδίκη')).toBe('Δημοδίκη');
    expect(healGreekPrintHyphens('τῆς ἡγε- μονίας κτλ.')).toBe('τῆς ἡγεμονίας κτλ.');
  });

  it('leaves Latin citations and non-Greek hyphens untouched', () => {
    expect(healGreekPrintHyphens('SEXT. adv. math. I 289')).toBe('SEXT. adv. math. I 289');
    expect(healGreekPrintHyphens('well- known')).toBe('well- known');
    expect(healGreekPrintHyphens('F GrHist. 81 F 66')).toBe('F GrHist. 81 F 66');
    // Hyphen without following whitespace stays (not a print wrap).
    expect(healGreekPrintHyphens('προ-')).toBe('προ-');
  });
});

describe('peelSourceHeadPrefix', () => {
  it('peels Latin citation before first lowercase-Greek token', () => {
    const p = peelSourceHeadPrefix('SEXT. adv. math. I 289 Ὅμηρος δὲ καὶ');
    expect(p).toEqual({
      head: 'SEXT. adv. math. I 289',
      rest: 'Ὅμηρος δὲ καὶ',
      restOffset: 'SEXT. adv. math. I 289 '.length,
    });
  });

  it('B31-shaped: Greek title + Latin citation peels; body starts at lowercase Greek', () => {
    const p = peelSourceHeadPrefix(
      'ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F ’ὁμολογοῦνται δ\' οἱ',
    );
    expect(p).not.toBeNull();
    expect(p!.head).toBe('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F');
    expect(p!.rest.startsWith('’ὁμολογοῦνται')).toBe(true);
    // Quote at the seam stays on the body side.
    expect(p!.rest[0]).toBe('’');
  });

  it('fused head+body without space: peels at numeral; quote on body; no digit-letter fuse', () => {
    // John's screenshot shape when head and body lack an intervening space.
    const p = peelSourceHeadPrefix("ATHEN. XIV 662F’ὁμολογοῦνται δ' οἱ");
    expect(p).not.toBeNull();
    expect(p!.head).toBe('ATHEN. XIV 662F');
    expect(p!.rest).toBe("’ὁμολογοῦνται δ' οἱ");
    // Display joins head and body with a space (separate .frag-source-head +
    // flow items); quote stays on the body side of the seam.
    expect(p!.head.endsWith('662F')).toBe(true);
    expect(p!.rest.startsWith('’')).toBe(true);
    expect(`${p!.head} ${p!.rest}`).toBe("ATHEN. XIV 662F ’ὁμολογοῦνται δ' οἱ");
    expect(`${p!.head} ${p!.rest}`).toMatch(/662F\s+’ὁμολογ/);
  });

  it('bare all-caps Greek with no Latin/numeral citation does not peel', () => {
    expect(peelSourceHeadPrefix('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ὁμολογοῦνται')).toBeNull();
    expect(peelSourceHeadPrefix('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ')).toBeNull();
  });

  it('returns null when pure head-only, pure Greek body, or empty', () => {
    expect(peelSourceHeadPrefix('SEXT. adv. math. I 289')).toBeNull();
    expect(peelSourceHeadPrefix('Ὅμηρος δὲ')).toBeNull();
    expect(peelSourceHeadPrefix('')).toBeNull();
  });
});

describe('isSourceHeadOnlyText', () => {
  it('accepts pure Latin and Greek-initial title + Latin citation', () => {
    expect(isSourceHeadOnlyText('SEXT. adv. math. VII 132')).toBe(true);
    expect(isSourceHeadOnlyText('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F')).toBe(true);
  });

  it('rejects bare all-caps Greek, narrative Greek, and empty', () => {
    expect(isSourceHeadOnlyText('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ')).toBe(false);
    expect(isSourceHeadOnlyText('’ὁμολογοῦνται δ\' οἱ')).toBe(false);
    expect(isSourceHeadOnlyText('PHILODEM. Rhet. I. ἡ δὲ τῶν')).toBe(false);
    expect(isSourceHeadOnlyText('')).toBe(false);
  });
});

describe('buildProseFlow — §1 + §3 + post-draft source head', () => {
  it('B81-shaped: mixed Latin head peels; body flows, punctuation hugged, no stranded text-run', () => {
    const lines = [
      line(1, 'context', 'PHILODEM. Rhet. I. ἡ δὲ τῶν ῥητόρων'),
      line(2, 'text', 'κοπίδων ἐστὶν ἀρχηγός'),
      line(3, 'context', '. SCHOL. in Eur. ὥστε μὴ τὸν'),
      line(4, 'text', 'Πυθαγόραν'),
      line(5, 'context', 'εὑρετὴν ὄντα τῶν ἀληθινῶν'),
      line(6, 'text', 'κοπίδων'),
      line(7, 'context', "μηδὲ τὸν Ἡράκλειτον."),
    ];
    const items = buildProseFlow(lines);
    // Mixed leading context: Latin citation peels; Greek narrative stays in flow.
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    if (items[0]!.kind === 'source-head') {
      expect(items[0]!.line.text).toBe('PHILODEM. Rhet. I.');
    }
    expect(items[1]!.kind).toBe('flow');
    if (items[1]!.kind !== 'flow') return;
    const flow = items[1]!;
    expect(flow.runs).toHaveLength(7);
    expect(flow.runs[0]!.cls).toBe('frag-ctx');
    expect(flow.runs[0]!.line.text).toBe('ἡ δὲ τῶν ῥητόρων');
    expect(flow.runs[1]!.cls).toBe('frag-txt');
    expect(flow.runs[3]!.line.text).toBe('Πυθαγόραν');
    // Seam before ". SCHOL..." — no space (CLOSE).
    expect(flow.runs[2]!.space).toBe(false);
    // Normal word seams — space.
    expect(flow.runs[4]!.space).toBe(true);
    expect(flow.runs[5]!.space).toBe(true);
    // Joined text has no orphan block-start period and keeps Πυθαγόραν inline.
    const joined = flow.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    expect(joined).toContain('ἀρχηγός. SCHOL.');
    expect(joined).toContain('τὸν Πυθαγόραν εὑρετὴν');
    expect(joined).not.toMatch(/\n/);
  });

  it('B1-shaped: pure Latin source head peels off; trailing period hugs fragment', () => {
    const lines = [
      line(1, 'context', 'SEXT. adv. math. VII 132 (Vgl. A 4. 16. B 51)'),
      line(2, 'text', "τοῦ δὲ λόγου τοῦδ' ἐόντος"),
      line(3, 'context', '.'),
    ];
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    expect(items[1]!.kind).toBe('flow');
    if (items[1]!.kind !== 'flow') return;
    expect(items[1]!.runs).toHaveLength(2);
    expect(items[1]!.runs[1]!.space).toBe(false); // period hugs
    expect(items[1]!.runs[0]!.cls).toBe('frag-txt');
    expect(items[1]!.runs[1]!.cls).toBe('frag-ctx');
  });

  it('incipit column: text-runs render as frag-ctx + incipit flag; data-incipit via flag', () => {
    const lines = [
      line(1, 'context', 'SIMPLIC. de caelo'),
      line(2, 'text', "’ἵπποι ... ἀληθής’"),
    ];
    const items = buildProseFlow(lines, { incipit: true });
    // Source head? "SIMPLIC..." may have no Greek - pure head peel.
    const flow = items.find((i) => i.kind === 'flow');
    expect(flow).toBeTruthy();
    if (!flow || flow.kind !== 'flow') return;
    expect(flow.incipit).toBe(true);
    const textRun = flow.runs.find((r) => r.line.role === 'text');
    expect(textRun?.cls).toBe('frag-ctx');
    expect(textRun?.incipit).toBe(true);
  });

  it('isPureSourceHeadText: Latin apparatus yes, Greek narrative no', () => {
    expect(isPureSourceHeadText('SEXT. adv. math. VII 132')).toBe(true);
    expect(isPureSourceHeadText('PHILODEM. Rhet. I. ἡ δὲ τῶν')).toBe(false);
    expect(isPureSourceHeadText('')).toBe(false);
  });

  // FIX A: never peel when the peel would leave zero body runs (Antiphon
  // B79–B81 / Anaxagoras A31 — entirely Latin context columns).
  it('context-only all-Latin column: no source-head peel; whole column is one flow', () => {
    // Pure ASCII/Latin apparatus — isPureSourceHeadText true, but sole run
    // so peeling would leave an empty body (must not peel).
    const lines = [
      line(-1, 'context', 'ARISTOT. eth. Eud. Gamma 1. 1229 a 40.'),
    ];
    const items = buildProseFlow(lines);
    expect(isPureSourceHeadText(lines[0]!.text)).toBe(true); // would peel if multi-run
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    if (items[0]!.kind !== 'flow') return;
    expect(items[0]!.runs).toHaveLength(1);
    expect(items[0]!.runs[0]!.cls).toBe('frag-ctx');
    expect(items.some((i) => i.kind === 'source-head')).toBe(false);
  });

  it('Latin head + Greek body: pure source head still peels (B1 unchanged)', () => {
    const lines = [
      line(1, 'context', 'SEXT. adv. math. VII 132 (Vgl. A 4. 16. B 51)'),
      line(2, 'text', "τοῦ δὲ λόγου τοῦδ' ἐόντος"),
      line(3, 'context', '.'),
    ];
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    expect(items[1]!.kind).toBe('flow');
  });

  it('peelSoleSourceHead: sole pure-Latin context peels (verse-frame streak)', () => {
    const lines = [line(-1, 'context', 'SEXT. VII 111')];
    const noPeel = buildProseFlow(lines);
    expect(noPeel).toHaveLength(1);
    expect(noPeel[0]!.kind).toBe('flow');

    const peeled = buildProseFlow(lines, { peelSoleSourceHead: true });
    expect(peeled).toHaveLength(1);
    expect(peeled[0]).toMatchObject({ kind: 'source-head' });
    if (peeled[0]!.kind === 'source-head') {
      expect(peeled[0]!.line.text).toBe('SEXT. VII 111');
    }
  });

  it('B12-shaped frame: mixed head peels; leading/trailing context flows; hyphens healed', () => {
    // Shape John ruled on (2026-07-24): citation head + leading Greek frame +
    // (verse handled by Reader lineation) + trailing frame with print hyphens.
    // Here we exercise the context streaks the verse branch feeds to buildProseFlow.
    const leading = [
      line(-1, 'context', 'SEXT. adv. math. I 289 Ὅμηρος δὲ καὶ Ἡσίοδος κατὰ τὸν Κολοφώνιον'),
      line(-1, 'context', 'Ξενοφάνη'),
    ];
    const leadItems = buildProseFlow(leading, { peelSoleSourceHead: true });
    expect(leadItems).toHaveLength(2);
    expect(leadItems[0]).toMatchObject({ kind: 'source-head' });
    if (leadItems[0]!.kind === 'source-head') {
      expect(leadItems[0]!.line.text).toBe('SEXT. adv. math. I 289');
    }
    expect(leadItems[1]!.kind).toBe('flow');
    if (leadItems[1]!.kind !== 'flow') return;
    // Single flowing leading-frame paragraph: two context lines → two frag-ctx
    // runs in ONE flow (not block children); no per-print-line structure beyond runs.
    expect(leadItems[1]!.runs).toHaveLength(2);
    expect(leadItems[1]!.runs.every((r) => r.cls === 'frag-ctx')).toBe(true);
    const leadJoined = leadItems[1]!.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    expect(leadJoined).toContain('Ὅμηρος δὲ καὶ Ἡσίοδος');
    expect(leadJoined).toContain('Ξενοφάνη');
    expect(leadJoined).not.toMatch(/\n/);

    const trailing = [
      line(
        -2,
        'context',
        "Κρόνος μὲν γὰρ ἐφ' οὗ τὸν εὐδαίμονα βίον γεγονέναι λέγουσι τὸν πατέρα ἠνδρο- τόμησε καὶ τὰ τέκνα κατέπιεν Ζεύς τε ὁ τούτου παῖς ἀφελόμενος αὐτὸν τῆς ἡγε- μονίας κτλ.",
      ),
    ];
    const trailItems = buildProseFlow(trailing, { peelSoleSourceHead: true });
    expect(trailItems).toHaveLength(1);
    expect(trailItems[0]!.kind).toBe('flow');
    if (trailItems[0]!.kind !== 'flow') return;
    expect(trailItems[0]!.runs).toHaveLength(1);
    expect(trailItems[0]!.runs[0]!.cls).toBe('frag-ctx');
    const t = trailItems[0]!.runs[0]!.line.text;
    expect(t).toContain('ἠνδροτόμησε');
    expect(t).toContain('ἡγεμονίας');
    expect(t).not.toMatch(/ἠνδρο-\s/);
    expect(t).not.toMatch(/ἡγε-\s/);
  });

  // John 2026-07-24 Critias B31: Greek-initial citation heads peel.
  it('B31-shaped: Greek title + Latin citation peels onto source-head; body flows', () => {
    const lines = [
      line(-1, 'context', 'ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F'),
      line(
        -2,
        'text',
        "’ὁμολογοῦνται δ' οἱ Θετταλοὶ πολυτελέστατοι τῶν Ἑλλήνων γεγενῆσθαι",
      ),
    ];
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    if (items[0]!.kind === 'source-head') {
      expect(items[0]!.line.text).toBe('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F');
    }
    expect(items[1]!.kind).toBe('flow');
    if (items[1]!.kind !== 'flow') return;
    expect(items[1]!.runs).toHaveLength(1);
    expect(items[1]!.runs[0]!.cls).toBe('frag-txt');
    expect(items[1]!.runs[0]!.line.text.startsWith('’ὁμολογοῦνται')).toBe(true);
    // Head and body are separate items; display form puts a space between them.
    const headText = items[0]!.kind === 'source-head' ? items[0]!.line.text : '';
    const bodyText = items[1]!.runs[0]!.line.text;
    expect(headText.endsWith('662F')).toBe(true);
    expect(`${headText} ${bodyText}`).toMatch(/662F\s+’ὁμολογ/);
  });

  it('bare all-caps Greek context is not a source-head (no Latin/numeral citation)', () => {
    const lines = [
      line(-1, 'context', 'ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ'),
      line(-2, 'text', 'ὁμολογοῦνται δ\' οἱ'),
    ];
    const items = buildProseFlow(lines);
    expect(items.some((i) => i.kind === 'source-head')).toBe(false);
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    if (items[0]!.kind !== 'flow') return;
    expect(items[0]!.runs[0]!.line.text).toBe('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ');
  });

  it('sole Greek-initial head-only run: only-run guard holds (no peel)', () => {
    const lines = [line(-1, 'context', 'ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F')];
    expect(isSourceHeadOnlyText(lines[0]!.text)).toBe(true);
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    expect(items.some((i) => i.kind === 'source-head')).toBe(false);
  });

  it('missing-space fused citation+body: peels with quote on body; display space between', () => {
    const lines = [
      line(-1, 'context', "ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F’ὁμολογοῦνται δ' οἱ"),
    ];
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    if (items[0]!.kind === 'source-head') {
      expect(items[0]!.line.text).toBe('ΠΟΛΙΤΕΙΑ ΘΕΤΤΑΛΩΝ ATHEN. XIV 662F');
    }
    expect(items[1]!.kind).toBe('flow');
    if (items[1]!.kind !== 'flow') return;
    const body = items[1]!.runs[0]!.line.text;
    expect(body.startsWith('’ὁμολογοῦνται')).toBe(true);
    // Separate source-head + flow items: joining with a space is the display form.
    const head = items[0]!.kind === 'source-head' ? items[0]!.line.text : '';
    expect(head.endsWith('662F')).toBe(true);
    expect(`${head} ${body}`).toContain('662F ’ὁμολογοῦνται');
    expect(`${head} ${body}`).toMatch(/662F\s+’ὁμολογ/);
  });
});

// John's dashboard note on thales/testimonia A1: the English below the Greek
// is Hicks's per-section translation (section markers "(22)", "(23)" …); the
// Greek carries the SAME DK convention as literal inline "(NN)" markers, but
// used to render as one unbroken paragraph. buildProseFlow now splits a
// context run into one flow paragraph per marker, mirroring the English.
describe('buildProseFlow — DK inline "(NN)" section-marker split (thales/testimonia A1)', () => {
  it('splits a context run into one paragraph per "(NN)" marker; marker moves to sectionMarker, not left in the text', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς πατρὸς μὲν Ἐξαμύου.'),
      line(2, 'context', '(23) μετὰ δὲ τὰ πολιτικὰ τῆς φυσικῆς ἐγένετο θεωρίας.'),
      line(3, 'context', '(24) ἔνιοι δὲ καὶ αὐτὸν πρῶτον εἰπεῖν φασιν ἀθανάτους τὰς ψυχάς.'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23, 24]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(3);
    expect(flows.map((f) => (f.kind === 'flow' ? f.sectionMarker : undefined))).toEqual([
      '22', '23', '24',
    ]);
    for (const f of flows) {
      if (f.kind !== 'flow') continue;
      for (const r of f.runs) expect(r.line.text).not.toMatch(/\(\d+\)/);
    }
    const joined = (f: (typeof flows)[number]) =>
      f.kind === 'flow' ? f.runs.map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text).join('') : '';
    expect(joined(flows[0]!)).toBe('Ἦν τοίνυν ὁ Θαλῆς πατρὸς μὲν Ἐξαμύου.');
    expect(joined(flows[1]!)).toBe('μετὰ δὲ τὰ πολιτικὰ τῆς φυσικῆς ἐγένετο θεωρίας.');
    expect(joined(flows[2]!)).toBe('ἔνιοι δὲ καὶ αὐτὸν πρῶτον εἰπεῖν φασιν ἀθανάτους τὰς ψυχάς.');
  });

  it('a marker mid-line splits that line: pre-marker text joins the running paragraph, post-marker text opens the next', () => {
    // Sentence-final "." before "(23)" (re-review finding 1's positional
    // gate — DK's own print shape, "λαμπροῦ. (23) μετὰ") — a comma would
    // not qualify as a valid marker boundary.
    const lines = [
      line(1, 'context', 'DIOGENES LAERTIUS I 22—44. (22) Ἦν τοίνυν ὁ Θαλῆς. (23) μετὰ δὲ τὰ πολιτικά.'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23]) });
    // Source-head "DIOGENES LAERTIUS I 22—44." still peels first (unchanged).
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(2);
    expect(flows.map((f) => (f.kind === 'flow' ? f.sectionMarker : undefined))).toEqual([
      '22', '23',
    ]);
    if (flows[0]!.kind === 'flow') {
      expect(flows[0]!.runs.map((r) => r.line.text).join(' ')).toContain('Ἦν τοίνυν ὁ Θαλῆς.');
    }
    if (flows[1]!.kind === 'flow') {
      expect(flows[1]!.runs.map((r) => r.line.text).join(' ')).toContain('μετὰ δὲ τὰ πολιτικά.');
    }
  });

  it('a marker-opened paragraph continues across subsequent marker-less lines (real A1 shape)', () => {
    const lines = [
      line(1, 'context', '(28) ἀρχὴν δὲ τῶν πάντων ὕδωρ ὑπεστήσατο.'),
      line(2, 'context', 'καὶ τὸν κόσμον ἔμψυχον.'),
      line(3, 'context', '(29) ὅθεν αὐτὸν καὶ Ξενοφάνης θαυμάζει.'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([28, 29]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(2);
    if (flows[0]!.kind !== 'flow' || flows[1]!.kind !== 'flow') throw new Error('unreachable');
    expect(flows[0]!.sectionMarker).toBe('28');
    expect(flows[0]!.runs).toHaveLength(2); // both marker-less continuation lines join paragraph 28
    expect(flows[1]!.sectionMarker).toBe('29');
  });

  it('role=text lines never split at "(NN)" — only context-role text carries the DK section convention, even when gated in', () => {
    const lines = [line(1, 'text', "(22) ’ - a quoted verse fragment, not DK apparatus")];
    // sectionMarkerNumbers gated in (22 declared) — still must not split a
    // role='text' line; the guard is on role, not just on gating.
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22]) });
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    if (items[0]!.kind !== 'flow') return;
    expect(items[0]!.sectionMarker).toBeUndefined();
    expect(items[0]!.runs[0]!.line.text).toContain('(22)');
  });

  it('no markers at all: single flow, sectionMarker undefined, byte-identical to pre-split behaviour', () => {
    const lines = [
      line(1, 'context', 'PHILODEM. Rhet. I. ἡ δὲ τῶν ῥητόρων'),
      line(2, 'text', 'κοπίδων ἐστὶν ἀρχηγός'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22]) });
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ kind: 'source-head' });
    expect(items[1]!.kind).toBe('flow');
    if (items[1]!.kind !== 'flow') return;
    expect(items[1]!.sectionMarker).toBeUndefined();
    expect(items[1]!.runs).toHaveLength(2);
  });
});

// Fix round (Sol review): findings 1, 3, 7 — the marker split is GATED on
// declared parallel English sections (sectionMarkerNumbers), not a bare
// regex scan, so a parenthesized integer with no declared section number
// can never be mistaken for the DK convention.
describe('buildProseFlow — marker-split gating (fix round finding 1) and empty-group reabsorption (finding 3)', () => {
  // Finding 1 regression: Gorgias A10's bibliographic year false-positived
  // as a marker + paragraph break under the old unconditional regex.
  it('Gorgias A10 shape: bibliographic year "(1848)" with NO contextEnglish declared renders byte-identical (no split, no marker, text untouched)', () => {
    const lines = [
      line(
        1,
        'context',
        '[Neue Jahrb. Suppl. 14 (1848) ed. A. Jahn]',
      ),
    ];
    // No sectionMarkerNumbers opt at all — the common case (no declared
    // contextEnglish for this segment).
    const items = buildProseFlow(lines);
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    if (items[0]!.kind !== 'flow') return;
    expect(items[0]!.sectionMarker).toBeUndefined();
    // Pin the FULL rendered text, not just a count (finding 7): "(1848)" is
    // still present, verbatim, never stripped or promoted to a marker.
    const joined = items[0]!.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    expect(joined).toBe('[Neue Jahrb. Suppl. 14 (1848) ed. A. Jahn]');
    expect(items[0]!.runs).toHaveLength(1);
  });

  it('a declared section set that does not include the parenthesized number leaves it as literal text too (no partial-match false positive)', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς. Cf. (1848) for the edition.'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(1);
    if (flows[0]!.kind !== 'flow') return;
    expect(flows[0]!.sectionMarker).toBe('22');
    const joined = flows[0]!.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    // "(22)" is stripped to the marker; "(1848)" (not in the declared set)
    // stays put, verbatim, in the flowing text.
    expect(joined).toBe('Ἦν τοίνυν ὁ Θαλῆς. Cf. (1848) for the edition.');
  });

  // Finding 3 regression: Empedocles A31 ends "… προσδοκῶντες. (2)" — the
  // terminal marker has no following text at all; the empty group it would
  // create must be reabsorbed as literal text, never silently dropped.
  it('Empedocles A31 shape: a terminal marker with nothing following is kept as literal text, not stripped', () => {
    const lines = [
      line(1, 'context', 'πάντα γὰρ ἴσθι φρόνησιν ἔχειν καὶ νώματος αἶσαν προσδοκῶντες. (2)'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([2]) });
    expect(items).toHaveLength(1);
    expect(items[0]!.kind).toBe('flow');
    if (items[0]!.kind !== 'flow') return;
    // No second (empty) paragraph was created.
    expect(items.filter((i) => i.kind === 'flow')).toHaveLength(1);
    expect(items[0]!.sectionMarker).toBeUndefined();
    const joined = items[0]!.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    expect(joined).toBe('πάντα γὰρ ἴσθι φρόνησιν ἔχειν καὶ νώματος αἶσαν προσδοκῶντες. (2)');
  });

  it('a terminal marker mid-run (more markers before it) still reabsorbs only its own empty tail, earlier paragraphs unaffected', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς.'),
      line(2, 'context', '(23)'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(1);
    if (flows[0]!.kind !== 'flow') return;
    expect(flows[0]!.sectionMarker).toBe('22');
    const joined = flows[0]!.runs
      .map((r, i) => (i > 0 && r.space ? ' ' : '') + r.line.text)
      .join('');
    // "(23)"'s own group was empty (nothing follows it) — reabsorbed onto
    // the running paragraph as literal text rather than lost.
    expect(joined).toBe('Ἦν τοίνυν ὁ Θαλῆς. (23)');
  });
});

// Re-review, finding 1: set membership alone still false-positived on an
// ordinary cross-reference sharing a declared section number. Two further
// gates: (a) ascending sequence — a set member out of order is not a
// marker; (b) position — a marker must sit at a line start or after
// sentence-final punctuation, not fused mid-sentence onto a word.
describe('buildProseFlow — marker sequence + position validation (re-review finding 1)', () => {
  it('a cross-reference "(23)" mid-sentence in section 22 does not split; the genuine "(23)" later (after sentence-final punctuation) does', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς, ὡς ἐν (23) ἄλλῳ τόπῳ λέγεται, σοφός.'),
      line(2, 'context', 'τέλος δὲ τῆς φυσικῆς ἐγένετο. (23) μετὰ δὲ ταῦτα.'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(2);
    if (flows[0]!.kind !== 'flow' || flows[1]!.kind !== 'flow') throw new Error('unreachable');
    expect(flows[0]!.sectionMarker).toBe('22');
    expect(flows[1]!.sectionMarker).toBe('23');
    const text22 = flows[0]!.runs.map((r) => r.line.text).join(' ');
    // The cross-reference stays put, literal, mid-paragraph — it never
    // opens its own section.
    expect(text22).toContain('(23)');
    expect(text22).toContain('ἐγένετο.');
    const text23 = flows[1]!.runs.map((r) => r.line.text).join(' ');
    expect(text23).toContain('μετὰ δὲ ταῦτα.');
    expect(text23).not.toContain('(23)');
  });

  it('an out-of-sequence "(30)" while 24 is still expected does not split; the same number later, in order, does', () => {
    const lines = [
      line(
        1,
        'context',
        '(22) Ἦν τοίνυν. (23) μετὰ δὲ. (30) ἔπειτα δὲ πρῶτον. (24) εἶτα δὲ. (30) τέλος δὲ.',
      ),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23, 24, 30]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows.map((f) => (f.kind === 'flow' ? f.sectionMarker : undefined))).toEqual([
      '22', '23', '24', '30',
    ]);
    if (flows[1]!.kind !== 'flow' || flows[3]!.kind !== 'flow') throw new Error('unreachable');
    const text23 = flows[1]!.runs.map((r) => r.line.text).join(' ');
    // The out-of-sequence "(30)" (24 was still expected) stays literal
    // inside section 23's paragraph rather than opening its own section.
    expect(text23).toContain('(30)');
    expect(text23).toContain('ἔπειτα δὲ πρῶτον.');
    const text30 = flows[3]!.runs.map((r) => r.line.text).join(' ');
    expect(text30).toContain('τέλος δὲ.');
    // The genuine, in-sequence "(30)" is stripped to the marker, not left
    // as literal text.
    expect(text30).not.toContain('(30)');
  });
});

// Re-review, finding 2: reabsorbEmptyMarkerGroups only treated a group with
// zero lines as empty — a terminal marker followed by a whitespace-only
// line kept a nonzero line count and rendered as a marker-labelled blank
// paragraph. Groups whose lines are ALL whitespace-only must reabsorb the
// same way, with the whitespace line itself kept, in place, not dropped.
describe('buildProseFlow — whitespace-only marker groups reabsorb too (re-review finding 2)', () => {
  it('a terminal marker followed by a whitespace-only line is reabsorbed; the whitespace line is kept', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς.'),
      line(2, 'context', '(23)'),
      line(3, 'context', '   '),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(1);
    if (flows[0]!.kind !== 'flow') throw new Error('unreachable');
    expect(flows[0]!.sectionMarker).toBe('22');
    expect(flows[0]!.runs).toHaveLength(2);
    expect(flows[0]!.runs[0]!.line.text).toBe('Ἦν τοίνυν ὁ Θαλῆς. (23)');
    // The whitespace line is not dropped — it stays, in place, as its own run.
    expect(flows[0]!.runs[1]!.line.text).toBe('   ');
  });

  it('two terminal markers separated only by a whitespace-only line both reabsorb; the whitespace line is kept', () => {
    const lines = [
      line(1, 'context', '(22) Ἦν τοίνυν ὁ Θαλῆς.'),
      line(2, 'context', '(23)'),
      line(3, 'context', '   '),
      line(4, 'context', '(24)'),
    ];
    const items = buildProseFlow(lines, { sectionMarkerNumbers: new Set([22, 23, 24]) });
    const flows = items.filter((i) => i.kind === 'flow');
    expect(flows).toHaveLength(1);
    if (flows[0]!.kind !== 'flow') throw new Error('unreachable');
    expect(flows[0]!.sectionMarker).toBe('22');
    expect(flows[0]!.runs).toHaveLength(2);
    expect(flows[0]!.runs[0]!.line.text).toBe('Ἦν τοίνυν ὁ Θαλῆς. (23) (24)');
    expect(flows[0]!.runs[1]!.line.text).toBe('   ');
  });
});

// Sol review, commit b69eae5, finding 1: `scanSectionMarkers` used to accept
// the FIRST occurrence matching the currently-expected value, even when a
// stray citation sharing that value sat earlier in the text with the real,
// boundary-adjacent marker following it — the stray won and the real one was
// rejected as out-of-sequence. Fixed to consider every occurrence of the
// expected value and prefer one at `isMarkerPosition`'s boundary, falling
// back to the first occurrence only when none qualifies.
describe('scanSectionMarkers — stray-equals-expected marker prefers the boundary occurrence (Sol review, commit b69eae5, finding 1)', () => {
  it('a stray "(5)" fused mid-word before the real, boundary-adjacent "(5)": the real one is chosen', () => {
    const text = 'Heading runs stray(5) noise. Section four ends here. (5) True section five begins.';
    const result = scanSectionMarkers(text, new Set([5]));
    expect(result).toHaveLength(1);
    expect(result[0]!.value).toBe(5);
    // The chosen match is the SECOND "(5)" (after ". "), not the first,
    // fused stray one.
    expect(result[0]!.index).toBe(text.indexOf('(5)', text.indexOf('(5)') + 1));
    expect(text.slice(result[0]!.index, result[0]!.index + result[0]!.length)).toBe('(5)');
  });

  it('a stray "(5)" at a boundary too, before the real "(5)": the FIRST boundary occurrence still wins (no way to distinguish, first-at-boundary rule holds)', () => {
    const text = 'Intro. (5) Actually a stray cross-reference. More text. (5) True section five begins.';
    const result = scanSectionMarkers(text, new Set([5]));
    expect(result).toHaveLength(1);
    // Both occurrences sit at a sentence boundary; the rule picks the first
    // boundary occurrence in the text, same as always-first-wins when both
    // qualify equally.
    expect(result[0]!.index).toBe(text.indexOf('(5)'));
  });

  it('heading runs straight into "(1)" with no sentence boundary at all: still splits at the sole occurrence (fallback preserved)', () => {
    const text = 'Encomium of Helen (1) Good order, for a city, is founded on wisdom.';
    const result = scanSectionMarkers(text, new Set([1]));
    expect(result).toHaveLength(1);
    expect(result[0]!.value).toBe(1);
    expect(result[0]!.index).toBe(text.indexOf('(1)'));
  });

  it('ascending run with a stray-equals-expected value at section 2: section 1 splits normally, the real "(2)" (not the earlier stray) opens section 2', () => {
    const text =
      '(1) First section text runs on. Some stray(2) reference fused in. Section one ends here. (2) Second section begins.';
    const result = scanSectionMarkers(text, new Set([1, 2]));
    expect(result.map((r) => r.value)).toEqual([1, 2]);
    expect(result[1]!.index).toBe(text.indexOf('(2)', text.indexOf('(2)') + 1));
  });
});

// Sol review, commit 6355e73, finding 2: a greedily chosen late boundary
// occurrence must never strand a later expected value when an earlier,
// non-boundary occurrence would keep the chain alive.
describe('scanSectionMarkers — a late boundary occurrence never strands a later expected value (Sol review, commit 6355e73, finding 2)', () => {
  it('with "(5)" mid-sentence early and at a boundary AFTER the only "(6)": the early "(5)" is chosen and "(6)" survives', () => {
    const text =
      'Intro runs into (5) alpha beta gamma continues (6) delta ends here. Cross-reference follows. (5) epsilon.';
    const result = scanSectionMarkers(text, new Set([5, 6]));
    expect(result).toHaveLength(2);
    expect(result[0]!.value).toBe(5);
    expect(result[0]!.index).toBe(text.indexOf('(5)'));
    expect(result[1]!.value).toBe(6);
    expect(result[1]!.index).toBe(text.indexOf('(6)'));
  });

  it('when the tail is unsatisfiable regardless, the boundary preference still applies (prior behavior preserved)', () => {
    const text = 'No six anywhere. Stray first (5) mid. Real follows. (5) tail.';
    const result = scanSectionMarkers(text, new Set([5, 6]));
    expect(result).toHaveLength(1);
    expect(result[0]!.value).toBe(5);
    expect(result[0]!.index).toBe(text.indexOf('(5)', text.indexOf('(5)') + 1));
  });
});
