<script lang="ts" module>
  // Pure greek-line DOM-id → citation parts. Exported for unit tests.
  // Shapes:
  //   L{col}-{n}      → { column, line: n }  (numbered verse/prose line)
  //   L{col}-{n}-c    → { column, line: n }  (mid-line chapter-split tail, no paraN)
  //   L{col}-{n}-c{k} → { column, line: n }  (section-split continuation — see below)
  //   L{col}          → { column, line: null } (DK prose-flow column anchor)
  //
  // Defect fix round (adversarial review, 2026-08-28): a selection confined
  // to a Discourses/Enchiridion section-split CONTINUATION piece (paraN
  // set, `cont: true` — see splitGreekSections) used to resolve to null
  // here, and citeForGreekLine's no-id fallback only runs for an element
  // WITHOUT an id — a continuation piece always has one (`L1.1-1-c2`), so
  // the fallback never fired and the copy dropped its citation entirely.
  // Every citation scheme that reaches this id shape (book-section via
  // `linedGreek`, and Enchiridion's `section` scheme, which splits the same
  // way) has `hasUserFacingLines: false`, so `formatCitation`
  // drops `line` and renders the bare column regardless of its value — a
  // continuation piece citing {column, line: n} therefore reads byte-
  // identical to its chapter's own first (non-continuation) piece. Resolving
  // it that way (instead of null) is a pure bugfix, not a citation-grammar
  // change: nothing downstream can tell the difference from a real numbered
  // line's citation.
  export function greekLineIdToCite(id: string): { column: string; line?: number | null } | null {
    const m = id.match(/^L(.+?)-(\d+)(?:-c\d*)?$/);
    if (m) return { column: m[1], line: Number(m[2]) };
    const p = id.match(/^L(.+)$/);
    return p ? { column: p[1], line: null } : null;
  }

  // Scroll-spy citeOf path for ids starting with L. Returns formatCite args, or
  // null when the id is not a citation target (continuations, unknown shapes).
  export function greekLineIdForScrollCite(id: string): { column: string; line?: number } | null {
    const lm = id.match(/^L(.+)-(\d+)$/);
    if (lm) return { column: lm[1], line: Number(lm[2]) };
    // Prose-flow column-only: L{col} — not L{col}-{n}-c{k} continuations.
    if (/^L.+-\d+-c\d*$/.test(id)) return null;
    const pm = id.match(/^L(.+)$/);
    if (pm) return { column: pm[1] };
    return null;
  }

  // Scroll-spy fallback label for section-flow works: the segment's column
  // token from its `id="col-{column}"` (the `.seg-ref-label` is not rendered).
  export function sectionFlowSpyLabel(id: string): string {
    return id.replace(/^col-/, '');
  }

  // A NON-verse line's first-line inset: `level` is the line's own literal
  // `indent(N)`. Level 1 is an ordinary paragraph opening. Verse lines do not
  // come through here -- they use verseInset + the hanging-indent CSS below,
  // because a verse line that turns over needs its continuation indented,
  // not returned to the margin.
  function linedIndent(level: number | undefined): string | undefined {
    return level != null && level >= 1 ? `${1.25 * Math.min(level, 4)}em` : undefined;
  }

  // A verse line's block inset, from the rebased step set by rebaseVerseRuns
  // (1 = the run's own base, 2 = one step in from it). Fed to CSS as
  // `--v-inset`; `.greek-line.verse .line-text` turns it into a HANGING
  // indent -- the line starts at the inset, and anything that wraps hangs
  // one further step in (John, 2026-08-31: "having the wrapped part of the
  // line be all the way at the left margin makes them not look like verse").
  // The hang is deliberately wider than the base->step gap, so a turned-over
  // hexameter can never be mistaken for the pentameter under it.
  function verseInset(step: number): string {
    return `${1.25 * (1 + step)}em`;
  }
</script>

<script lang="ts">
  import { onMount, onDestroy, afterUpdate, tick } from 'svelte';
  import { fade } from 'svelte/transition';
  import { fetchBook, parseLocation, fetchSidenotes, fetchFigures, fetchParatext, type Segment, type GreekLine, type Token, type BookData, type OverlayPiece, type Paratext, type ExpandedCitationEntry, type TranslationCredit, type ContextEnglishSpan, type Witness } from '../lib/data';
  import { schemeFor, formatCite, formatCopyCitationRange, unitNounFor } from '../lib/citation';
  import { lineRenderParts, buildFlowRows, buildEnglishTurnBlocks, labelSuppression, splitGreekSections, splitWrapLine, type SpeakerEvent, type LineRenderPart, type FlowRow, type EnglishTurnBlock } from '../lib/speakers';
  import { assignSpeakerSlots, collectDisplayOrder } from '../lib/speaker-colors';
  import { greekFold } from '../lib/search';
  import { highlightPrefixMatches } from '../lib/text';
  import { columnLineates, buildProseFlow, isSourceHeadOnlyText, peelSourceHeadPrefix, scanSectionMarkers, singlePureContextRun, type ProseFlowItem } from '../lib/prose-flow';
  import { getWork, visibleTranslations, bookLabel as workBookLabel, languageLabel, freemanApparatusCredit, type TranslationRef } from '../lib/works';
  import { getAuthor } from '../lib/authors';
  import { touchRecent } from '../lib/resume';
  import WordPopup from './WordPopup.svelte';
  import FootnotePopup from './FootnotePopup.svelte';

  export let work: string = 'EN';
  export let bookNum: number = 1;
  // The book's segments, read at build time and passed by ReaderShell.astro so
  // the reading text is server-rendered into the static HTML (crawlable, instant
  // paint) and the island hydrates over it. When absent (e.g. a future dynamic
  // mount), the reader falls back to fetching the JSON in onMount as before.
  export let bookData: BookData | null = null;
  // Optional per-chapter section titles {chapter: title} for this book, passed
  // by ReaderShell from chapter-titles.json. Shown in the chapter heading in
  // place of "Chapter N" (used by non-Bekker works like the Isagoge).
  export let chapterTitles: Record<string, string> = {};
  // The whole-work speaker-display roster (all books), passed by ReaderShell so
  // speaker-name colours are stable across books and match the landing cast
  // list. Null on hosts that mount a single book without it (desktop).
  export let speakerRoster: string[] | null = null;
  // PUBLIC_LYCEUM_CHROME=1 only (John, 2026-09-01): passed straight through
  // to WordPopup, which mounts the Grammata T8 lookup widget when true.
  // Default false so every other host's popup is unchanged.
  export let grammataLookup: boolean = false;

  const workMeta = getWork(work);
  // `workMeta.author` is an author-registry slug, not a display name — see
  // shared/lib/works.ts's doc comment on the field.
  const authorName = workMeta ? (getAuthor(workMeta.author)?.name ?? workMeta.author) : '';
  const sourceLanguageLabel = workMeta ? languageLabel(workMeta) : 'Greek';
  // `lang` attribute for the source-text column (Wave 2 Batch 1a: Cicero's
  // De Officiis is the first `lat` work) — matches Landing.astro's existing
  // sourceLangTag convention ('la', not 'lat') and drives global.css's
  // [lang="la"] --font-greek override (see that rule's own comment).
  const sourceLang = workMeta?.language === 'lat' ? 'la' : 'grc';
  // The citation scheme this work is cited by (bekker / busse / stephanus) — the
  // single dispatch point for every scheme-conditional below, in place of
  // scattered string tests. See shared/lib/citation.ts.
  const cscheme = schemeFor(work);
  // The chapter heading / print-menu unit noun ("Chapter") — this reader
  // path (chapterHead snippet, print-single-chapter menu) is only ever
  // exercised for a bekker/busse work (see chapterHead's/printSingleChapter's
  // own comments), whose unit noun IS "chapter" per REVIEW-CHECKLIST item 34
  // — sourced from unitNounFor rather than hardcoded so it stays correct if
  // that ever changes.
  const chapterUnitNoun = unitNounFor(work).capitalized;
  // item 23 unification (John's dashboard note, 7/23): book-section works
  // (Marcus Aurelius, Discourses, Diogenes Laertius, Cicero's book-section
  // works) have no user-facing line axis of their own (hasUserFacingLines:
  // false) and carry none of dk's role tags, so the old lineate/prose-flow
  // choice below forced block-per-line even where a segment's Greek arrives
  // as several separate print-line records (Discourses' Schenkl-subsection
  // split, GreekLine.sections/paraN) -- shredding one flowing sentence into
  // gapped blocks. Gated on the citation scheme alone (not re-derived from
  // content, matching the design's own rule for `columnLineates`): every
  // book-section column now flows continuously; every other scheme's
  // rendering is untouched (the gate is `false` for them, so the branch
  // below reduces to exactly its old expression).
  const bookSectionFlow = cscheme.id === 'book-section';
  // PILOT (2026-08-28, John's Discourses gutter-collision report): a
  // book-section work can opt into block-per-section Greek layout via
  // `citation.linedGreek` (see WorkMeta['citation'] doc comment) instead of
  // book-section's scheme-wide continuous flow — the same lineate path
  // Enchiridion's `section` scheme already exercises via splitGreekSections
  // (below, greekItems' `lineate`). Deliberately NOT folded into
  // `bookSectionFlow` itself: that constant also gates other book-section-
  // wide DOM/CSS choices that must stay untouched — this flag only ever
  // reaches greekItems' `lineate` computation, so it changes the Greek
  // column alone. (It used to gate the English column's gutter-vs-inline
  // paraN treatment too; those marks were retired 2026-08-31 — see the
  // retired `.para-n.gutter` rule in global.css for why.)
  const linedGreek = cscheme.id === 'book-section' && workMeta?.citation?.linedGreek === true;
  // Continuous section flow (docs/section-flow-plan.md): book-section only.
  // Opt-in; default off. Drops per-section furniture for a gutter/inline tick.
  const sectionFlow = cscheme.id === 'book-section' && workMeta?.citation?.sectionFlow === true;
  // Print-lineation rollout wave 1 (docs/lined-rollout-plan.md, Ruling 6 /
  // Stage 3): whether this work's Greek lines carry the print-line channel
  // (sec/wrap/indent) and must be painted with hyphen splits and section
  // marks. True for Discourses (alongside `linedGreek`, which still does its
  // own separate job of forcing `lineate` for that book-section work) and,
  // as of wave 1, for Enchiridion and the five Epicurus works — none of
  // which are book-section, so `linedGreek` itself stays false for them.
  // Gates the painting branch below (was `linedGreek`-only pre-wave-1) and
  // the `rawLineNs` dedupe seeding, unlike `linedGreek`'s `lineate` override,
  // which is unchanged.
  const linedSource = workMeta?.citation?.linedSource === true;
  // Opt-out of a scheme's default lineation -- see the type's doc comment.
  const proseReflow = workMeta?.citation?.proseReflow === true;
  // This edition's ordinary-paragraph indent level; deeper means verse.
  // See WorkMeta['citation'].proseIndent -- Cicero starts at 2, Greek at 1.
  const proseIndent = workMeta?.citation?.proseIndent ?? 1;
  // Non-Bekker works (e.g. Porphyry's Isagoge) are cited by Busse page, not a
  // Bekker column:line. For them the reader relabels the column reference (p. N),
  // hides the per-line Greek numbers and the interpolated English gutter, and
  // titles each section from chapterTitles instead of "Chapter N".
  const busse = cscheme.id === 'busse';
  // Stephanus works (Plato) are cited by page+letter only (17a); there are no
  // user-facing Greek line numbers, and each segment shows its section token in
  // the gutter. Speaker turns are rendered as inline lead-ins (see speakers.ts).
  const stephanus = cscheme.id === 'stephanus';
  // A verse dk work (Parmenides' Fragmenta): real per-fragment line numbers
  // (citation.lines: true) laid out as genuine hexameter verse, not dk's
  // usual lineless prose fragments (Heraclitus) — used only to scope the
  // hanging-indent wrap CSS below (Wave 1b Parmenides pilot, design memo
  // §3's "minor Greek-side verse CSS").
  const dkVerse = cscheme.id === 'dk' && cscheme.hasUserFacingLines;
  // verse-line (Lucretius' DRN): the spine's citable unit is one Latin verse
  // line per segment (John's flag, 2026-07-24 — each line was rendering as
  // its own bordered .segment with a bold column-ref chip and a mostly-empty
  // English cell). This mode keeps every segment's existing per-line anchor
  // (jump-to-line/copy-citation/#-target all untouched) but drops the
  // per-line .seg-ref chip and (via CSS) the per-segment border/margin, so
  // consecutive lines read as one continuous verse block; a quiet gutter
  // number stands in for the chip (verseGutterNum below), and the English
  // column is only rendered for a segment that actually carries English
  // (Munro's declared multi-line spreads), never as an empty cell.
  const verseLine = cscheme.id === 'verse-line';
  // DK prose-flow (docs/prose-flow-design.md §3): declared incipit-stub columns
  // — text-runs render as apparatus, not fragment-prominent.
  const incipitColumnSet = new Set(
    (workMeta?.citation?.incipitColumns ?? []).map((c) => c.column),
  );
  // Suppress the per-line Greek numerals whenever the scheme has no user-facing
  // lines (stephanus), or a busse work that opts in via hideLineNumbers.
  const hideLineNums = !cscheme.hasUserFacingLines
    || (busse && workMeta?.citation?.hideLineNumbers === true);
  // Analytical sidenotes ({N: text}) for a busse work, floated into a right rail.
  let sidenotesData: Record<string, string> = {};
  if (busse) fetchSidenotes(work).then(d => { sidenotesData = d; }).catch(() => {});
  // Diagrams ({N: html}) rendered inline at [[figN]] markers (Tree of Porphyry).
  let figuresData: Record<string, string> = {};
  if (busse) fetchFigures(work).then(d => { figuresData = d; }).catch(() => {});
  // Freeman Ancilla group-header paratext (design note §1/§3.7) — resolves
  // to [] for every non-Freeman work (fetchParatext's own 404-is-empty
  // convention), so this fetch is unconditional rather than gated on a
  // scheme check.
  let paratextData: Paratext[] = [];
  fetchParatext(work).then(d => { paratextData = d; }).catch(() => {});
  $: paratextByColumn = paratextData.reduce<Record<string, Paratext[]>>((acc, h) => {
    (acc[h.beforeColumn] ??= []).push(h);
    return acc;
  }, {});
  const translations = workMeta ? visibleTranslations(workMeta) : [];
  // The reader can render any number of translations. The primary parallel
  // chunk is the 'english' slot; every other translation is a chapter-anchored
  // overlay read from its segment field (secondary / third / overlays[id]).
  // `secondaries` is the ordered list of non-primary translations.
  const engSlot = translations.find(t => t.slot === 'english');
  const thirdSlot = translations.find(t => t.slot === 'third');  // bears footnotes/tables
  // The translation(s) whose prose carries [^label] footnote markers
  // (Ostwald's third slot, a primary like the Isagoge's Owen, or — Phase 4B —
  // any imported overlay whose file carried a footnotes block, flagged via
  // the same TranslationRef.footnotes bit by desktop/src/lib/imports.ts's
  // installHooks). Every such id's column renders the markers and opens the
  // footnote popup. thirdSlot is ALWAYS included (not just as a fallback when
  // nothing is explicitly flagged) so an import gaining footnotes:true never
  // silently un-flags Ostwald — this generalizes the old single-id
  // `fnTransId` without changing behavior for any existing work (today,
  // across the whole corpus, this set never has more than one member: either
  // the one explicitly-flagged translation, or thirdSlot — never both, since
  // no work currently combines them).
  const fnTransIds = new Set([
    ...translations.filter(t => t.footnotes).map(t => t.id),
    ...(thirdSlot ? [thirdSlot.id] : []),
  ]);
  const secondaries = translations.filter(t => t.slot !== 'english');
  const canCompare = translations.length >= 2;
  // Overlay pieces for a translation in a segment, selected by its slot.
  const piecesFor = (seg: Segment, t: TranslationRef | undefined | null): OverlayPiece[] => {
    if (!t) return [];
    // `?? seg.ross` reads the legacy field name until the pipeline emits
    // `secondary` (stage 2 of the rename); drop the fallback then.
    if (t.slot === 'secondary') return seg.secondary ?? seg.ross ?? [];
    if (t.slot === 'third') return seg.third ?? [];
    if (t.slot === 'overlay') return seg.overlays?.[t.id] ?? [];
    return [];
  };
  const transById = (id: string | null | undefined): TranslationRef | null =>
    id ? (translations.find(t => t.id === id) ?? null) : null;

  // §Phase-4B-revised (John's call 2026-07-06): an imported translation's own
  // converter-derived chapter title is this edition's editorial paratext, not
  // work-level chrome — it renders as a small unaligned heading INSIDE that
  // import's own overlay column (see transFlow below), never merged into the
  // shared chapterTitles heading map above. Resolved through a window-level
  // hook installed by desktop/src/lib/imports.ts's installHooks(), the same
  // site-shared pattern __READER_IMPORT_FOOTNOTE_HOOK__ uses (see
  // FootnotePopup.svelte) — this component is SHARED with the static site
  // build, which never installs the hook, so the lazy read below is always
  // undefined there: inert, byte-identical rendering. Render-only: sourced
  // from ImportRecord.titles, never written into any offset-bearing text
  // stream, so no anchor ever shifts.
  function importChapterTitle(transId: string, chapter: string | null): string {
    if (!chapter) return '';
    const hook = (globalThis as {
      __READER_IMPORT_TITLE_HOOK__?: (work: string, id: string, book: number, chapter: string) => string | null;
    }).__READER_IMPORT_TITLE_HOOK__;
    return (hook ? hook(work, transId, bookNum, chapter) : null) ?? '';
  }

  // Compare mode shows two translations side by side; which two is chosen in the
  // settings sidebar. Defaults: primary + first secondary. Persisted per work.
  let compareLeft: string = engSlot?.id ?? translations[0]?.id ?? 'english';
  let compareRight: string = secondaries[0]?.id ?? translations[1]?.id ?? compareLeft;
  const CMPL_KEY = `reader-cmpl-${work}`;
  const CMPR_KEY = `reader-cmpr-${work}`;
  function saveCompare() {
    try { localStorage.setItem(CMPL_KEY, compareLeft); localStorage.setItem(CMPR_KEY, compareRight); } catch {}
  }
  // The two columns must differ — two identical translations is never useful.
  // Pick the first other translation to fill the freed side.
  function otherTrans(exclude: string): string {
    return translations.find(t => t.id !== exclude)?.id ?? exclude;
  }
  function pickCompareLeft() {
    if (compareLeft === compareRight) compareRight = otherTrans(compareLeft);
    saveCompare(); setTrans('compare');
  }
  function pickCompareRight() {
    if (compareRight === compareLeft) compareLeft = otherTrans(compareRight);
    saveCompare(); setTrans('compare');
  }

  // Seeded from the build-time prop so SSR renders the text; stays empty (and
  // `loading` true) only in the fetch-fallback path.
  let segments: Segment[] = bookData?.segments ?? [];
  // Global turn flow of a dialogue book (stephanus): drives the turn-row
  // rendering; null keeps the section-segment rendering.
  let turnFlow = bookData?.turnFlow ?? null;
  // Freeman Ancilla wave (design note §3.7): the manifest's declared
  // display permutation of `segments`' column tokens (present only when
  // Freeman's own sequence diverges from spine/document order). null for
  // the overwhelming majority of books.
  let displayOrder: string[] | null = bookData?.displayOrder ?? null;
  let loading = !bookData;
  let error = '';
  // OS "reduce motion" preference — gates the JS fade transitions below, which
  // the CSS @media (prefers-reduced-motion) query can't reach. Set in onMount.
  let reduceMotion = false;

  // Search jump-in: highlight query terms + scroll to a line (?hlg=&hle=&loc=).
  let hlGrkFolds: string[] = [];
  let hlEngTerms: string[] = [];
  let targetId: string | null = null;

  // Per-passage translation picker for a ContextEnglishSpan's alternates
  // (item 82, REVIEW-CHECKLIST): page-local only -- no localStorage, no URL
  // param -- keyed by `${seg.id}:${spanIndex}`. Absent/null = the span's
  // primary translation. Reassigned (never mutated in place) so Svelte's
  // classic reactivity picks up the change.
  let contextEnglishAlt: Record<string, string | null> = {};
  function selectContextEnglishAlt(key: string, altId: string | null) {
    contextEnglishAlt = { ...contextEnglishAlt, [key]: altId };
  }
  // Surname extraction shared by every per-passage picker label (item 82's
  // context-English toggle and item 84's per-segment toggle, below): strips
  // a trailing ", year" if present ("Hicks, 1925" -> "Hicks", the only shape
  // ContextEnglishSpan.translationCredit ever carries), then -- for a bare
  // full name with no comma, e.g. TranslationCredit.translator's "Jurgen R.
  // Gatt" -- takes the last whitespace-separated word as the surname.
  function surnameFromCredit(credit: string): string {
    const comma = credit.indexOf(',');
    const base = (comma === -1 ? credit : credit.slice(0, comma)).trim();
    if (!base) return '';
    const words = base.split(/\s+/);
    return words[words.length - 1];
  }
  // The primary option's own picker label: the translator surname, cheaply
  // read off the front of `translationCredit` ("Hicks, 1925" -> "Hicks") --
  // that string's own convention is "translator, year", same as every other
  // credit line on the page. Falls back to the literal word "Default" when
  // there's no credit to read a surname from (never invents one).
  function contextEnglishPrimaryLabel(span: ContextEnglishSpan): string {
    const credit = span.translationCredit;
    if (!credit) return 'Default';
    return surnameFromCredit(credit) || 'Default';
  }

  // Item 84 (REVIEW-CHECKLIST): generalizes the per-passage translation
  // picker (item 82's context-English toggle) to every ordinary fragment/
  // testimonium segment where the WORK carries 2+ translations AND 2+ of
  // them have actual text for THIS segment. Page-local only (no
  // localStorage, no URL param), keyed by seg.id. Absent = the work-level
  // `trans` selection stays that segment's default. Never consulted (or
  // rendered) in compare mode -- callers guard on `trans !== 'compare'`.
  let segTransOverride: Record<string, string> = {};
  function selectSegTrans(segId: string, transId: string) {
    segTransOverride = { ...segTransOverride, [segId]: transId };
  }
  // The active per-segment translation id (segTransOverride[seg.id] ?? trans)
  // is read directly in the markup, not through a helper function -- Svelte's
  // template dependency tracking only sees identifiers referenced directly
  // in a template expression, so hiding the read inside a plain function
  // would make a toggle click invisible to re-rendering.
  // Whether translation `t` carries real text for `seg` -- the primary slot
  // via seg.english.text, any other via its overlay piece (piecesFor, the
  // same slot lookup transApprox already uses). Fragment/testimonia works
  // never split a segment into more than one block (splitSegment's own
  // documented invariant), so this segment-level check is exactly the
  // question the sole block would ask.
  function hasTextFor(seg: Segment, t: TranslationRef): boolean {
    if (t.slot === 'english') return !!seg.english?.text?.trim();
    const pieces = piecesFor(seg, t);
    const p = pieces.find(pp => pp.cont) ?? pieces[0];
    return !!p?.text?.trim();
  }
  // Which of the work's translations carry text for this segment. 2+ gates
  // the per-passage toggle (design point 1); fewer than 2 (one or zero)
  // renders no toggle -- the existing "Not in X -- see Y" note (transFlow)
  // is the only guidance in that case, unchanged.
  function availableTranslationsFor(seg: Segment): TranslationRef[] {
    return translations.filter(t => hasTextFor(seg, t));
  }

  // Item 83 (REVIEW-CHECKLIST): locate a ContextEnglishSpan's `emphasis`
  // substrings against the FULL span text (not per-paragraph) -- each is
  // searched from where the previous one ended, matching the build-time
  // validation (occurs exactly once, non-overlapping, in text order). Doing
  // this against the full text rather than re-searching each paragraph
  // means a substring that happens to also appear verbatim in another
  // paragraph can never be mismatched to the wrong occurrence. Defensive
  // only: an unmatched entry (should not happen -- build validates this) is
  // silently skipped rather than throwing.
  function locateEmphasisRanges(fullText: string, emphasis: string[] | undefined): { start: number; end: number }[] {
    if (!emphasis?.length) return [];
    const ranges: { start: number; end: number }[] = [];
    let cursor = 0;
    for (const sub of emphasis) {
      if (!sub) continue;
      const idx = fullText.indexOf(sub, cursor);
      if (idx === -1) continue;
      ranges.push({ start: idx, end: idx + sub.length });
      cursor = idx + sub.length;
    }
    return ranges;
  }

  interface ContextEnglishParagraph {
    segments: { text: string; bold: boolean }[];
  }
  // Splits a span's primary `text` into paragraphs (on "\n\n", same join the
  // render path already used) and, within each paragraph, into plain/bold
  // segments per `locateEmphasisRanges` above -- since an authored substring
  // never crosses a paragraph join, each match's [start,end) range falls
  // entirely inside exactly one paragraph's offset window here, so mapping
  // ranges onto paragraphs by offset (rather than re-searching each
  // paragraph's own text) is exact. A span with no `emphasis` produces one
  // all-plain segment per paragraph, so the render path adds no `<strong>`
  // and stays byte-identical to before this feature.
  function contextEnglishParagraphs(fullText: string, emphasis: string[] | undefined): ContextEnglishParagraph[] {
    const ranges = locateEmphasisRanges(fullText, emphasis);
    const paras = fullText.split('\n\n');
    const out: ContextEnglishParagraph[] = [];
    let offset = 0;
    for (const para of paras) {
      const paraStart = offset;
      const paraEnd = offset + para.length;
      const segments: { text: string; bold: boolean }[] = [];
      let pos = paraStart;
      for (const r of ranges) {
        if (r.start >= paraEnd || r.end <= paraStart) continue;
        if (r.start > pos) segments.push({ text: fullText.slice(pos, r.start), bold: false });
        segments.push({ text: fullText.slice(Math.max(r.start, paraStart), Math.min(r.end, paraEnd)), bold: true });
        pos = Math.min(r.end, paraEnd);
      }
      if (pos < paraEnd) segments.push({ text: fullText.slice(pos, paraEnd), bold: false });
      if (!segments.length) segments.push({ text: '', bold: false });
      out.push({ segments });
      offset = paraEnd + 2; // '\n\n' separator
    }
    return out;
  }

  // Which translation fills the English column: a translation id from the
  // registry (its slot decides what renders) or 'compare' = both slots side by
  // side. Persisted per work (works carry different translations).
  // First-load translation: the work's preferred default if it names one (and
  // it's actually visible in this build), else the primary 'english' slot. A
  // saved choice or ?trans= query param overrides this in onMount.
  const defaultTrans = translations.find(t => t.id === workMeta?.defaultTranslation)?.id;
  let trans: string = defaultTrans ?? engSlot?.id ?? translations[0]?.id ?? 'english';
  // The translation ids currently on screen: the single selection, or the two
  // compare columns. Drives the gutter disclaimer and the citation strip.
  $: shownTransIds = trans === 'compare' ? [compareLeft, compareRight] : [trans];
  // Whether a translation carries any approximate (interpolated) Bekker ticks in
  // a segment — overlays whose gutter is fully anchored show none, so the note
  // is suppressed for them.
  const transApprox = (seg: Segment, id: string): boolean => {
    const t = transById(id);
    if (!t) return false;
    if (t.slot === 'english') return !!seg.english?.bekker?.some((x) => !x.real);
    return piecesFor(seg, t).some((p) => p.bekker?.some((x) => !x.real));
  };
  $: hasApproxTicks = view !== 'greek'
    && segments.some((seg) => shownTransIds.some((id) => transApprox(seg, id)));
  const TRANS_KEY = `reader-trans-${work}`;
  const CITE_KEY  = 'reader-cite-copy';
  // The "ℹ︎ Bekker numbers" popover (upright = fixed, italic = estimate).
  let bekkerInfoOpen = false;
  let citeCopy = true;
  function saveCiteCopy() { try { localStorage.setItem(CITE_KEY, String(citeCopy)); } catch {} }

  // ── Speaker-name colourisation ───────────────────────────────────────────
  // OFF by default. When on, each distinct speaker in the current dialogue gets
  // one of a small palette of complementary hues (--spk-* in global.css),
  // applied to the .speaker lead-in NAME only — never the speech text. Once the
  // slot is stamped on the span as data-spk, the whole effect is CSS, so the
  // toggle merely flips a container class (.spk-color) with no re-render.
  const SPK_KEY = 'reader-spkcolor';
  // On by default; a reader who turns it off has that choice remembered
  // (onMount reads SPK_KEY, which only exists once they've toggled it).
  let spkColor = true;
  function saveSpkColor() { try { localStorage.setItem(SPK_KEY, String(spkColor)); } catch {} }
  // display → palette slot for every NAMED speaker in this book's turn flow
  // (turns, embedded `et` speeches, folded `sub` speeches). Slot assignment is
  // shared with the landing-page cast list (shared/lib/speaker-colors) so a
  // speaker gets the same hue in both. Unattributed em-dash turns have no
  // display and are never coloured.
  // Prefer the whole-work roster (passed by ReaderShell.astro) so a speaker's
  // colour is stable across every book AND matches the landing cast list; fall
  // back to the current book alone when no roster is supplied (e.g. the desktop
  // shell, which mounts a single book).
  $: spkSlots = assignSpeakerSlots(
    speakerRoster && speakerRoster.length ? speakerRoster : collectDisplayOrder([turnFlow]),
  );
  // The last single-translation choice, remembered so leaving compare mode
  // returns to it (and so the picker has something to display in compare).
  let lastSingle: string = trans;
  function setTrans(t: string) {
    trans = t;
    if (t !== 'compare') lastSingle = t;
    try { localStorage.setItem(TRANS_KEY, t); } catch {}
  }
  // The dropdowns select WHICH translation; mode (single vs compare) is chosen
  // in the settings sidebar. Picking a translation always means "show me this
  // one" — including from compare mode, which it exits.
  $: pickValue = trans === 'compare' ? lastSingle : trans;
  function onPick(e: Event) {
    setTrans((e.currentTarget as HTMLSelectElement).value);
  }

  // ── Settings sidebar ──────────────────────────────────────────────────────
  let settingsOpen = false;
  const FS_KEY = `reader-fs-${work}`;
  const LH_KEY = `reader-lh-${work}`;
  const COLW_KEY = `reader-colw-${work}`;
  // Base CSS values from global.css; scale as multipliers (1.0 = default).
  const FS_GREEK_BASE = 1.05;
  const FS_ENG_BASE   = 1.08;
  const LH_GREEK_BASE = 1.7;
  const LH_ENG_BASE   = 1.72;
  let fsScale = 1.0;
  let lhScale = 1.0;
  // Column-width scale: multiplies the layout's width caps (reader measure,
  // mono-view column measure) via --colw-scale; 1.0 = the stock layout.
  let colScale = 1.0;
  $: fsGreek = (FS_GREEK_BASE * fsScale).toFixed(3);
  $: fsEng   = (FS_ENG_BASE   * fsScale).toFixed(3);
  $: lhGreek = (LH_GREEK_BASE * lhScale).toFixed(3);
  $: lhEng   = (LH_ENG_BASE   * lhScale).toFixed(3);

  // The settings drawer is `inert` when closed (see the <aside> below), so it's
  // out of the tab order there. When open it needs the modal dance: move focus
  // in, trap Tab, and restore focus to the opener on close.
  let settingsEl: HTMLElement | undefined;
  let settingsReturnFocus: HTMLElement | null = null;
  function settingsFocusables(): HTMLElement[] {
    return settingsEl
      ? Array.from(settingsEl.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )).filter((el) => el.offsetParent !== null)
      : [];
  }
  function onSettingsKey(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const f = settingsFocusables();
    if (!f.length) { e.preventDefault(); settingsEl?.focus(); return; }
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function closeSettings() {
    if (!settingsOpen) return;
    settingsOpen = false;
    window.dispatchEvent(new CustomEvent('settings-state', { detail: { open: false } }));
    // Restore focus to the header toggle that opened the drawer.
    (settingsReturnFocus ?? document.querySelector<HTMLElement>('.settings-toggle'))?.focus();
    settingsReturnFocus = null;
  }
  function openSettings() {
    if (settingsOpen) return;
    settingsReturnFocus = document.activeElement as HTMLElement | null;
    settingsOpen = true;
    window.dispatchEvent(new CustomEvent('settings-state', { detail: { open: true } }));
    // Wait for the drawer to un-inert, then focus its close button.
    tick().then(() => (settingsEl?.querySelector('.settings-close') as HTMLElement | null)?.focus());
  }
  function saveFs() { try { localStorage.setItem(FS_KEY, String(fsScale)); } catch {} }
  function saveLh() { try { localStorage.setItem(LH_KEY, String(lhScale)); } catch {} }
  function saveColw() { try { localStorage.setItem(COLW_KEY, String(colScale)); } catch {} }
  function resetSettings() {
    fsScale = 1.0; lhScale = 1.0; colScale = 1.0; citeCopy = true; spkColor = true;
    try {
      localStorage.removeItem(FS_KEY); localStorage.removeItem(LH_KEY);
      localStorage.removeItem(COLW_KEY); localStorage.removeItem(CITE_KEY);
      localStorage.removeItem(SPK_KEY);
    } catch {}
  }

  // ── Citation shown in the controls strip ─────────────────────────────────
  // The strip is filled with the bibliographic provenance so it reads as a
  // header, not a lone toggle. The Greek source comes from the registry; the
  // translation citation from the currently-selected translation. `short` forms
  // ("Ross (1908)") sit beside the controls in bilingual view; the full forms
  // fill the otherwise-empty bar in Greek-only / English-only.
  const greekSrc = workMeta?.greekSource;
  // Freeman Ancilla wave apparatus credit (design note §3.8): a quiet
  // credit line beside the edition citation, present only for a
  // Freeman-wired work. null for every other work.
  const freemanCredit = workMeta ? freemanApparatusCredit(workMeta) : null;
  $: selectedTrans = trans === 'compare'
    ? null
    : (translations.find(t => t.id === trans) ?? null);
  const yearOf = (s: string) => { const m = s.match(/(\d{4})/); return m ? m[1] : ''; };
  const citeShort = (t: { short: string; name: string } | null | undefined) => {
    if (!t) return '';
    const y = yearOf(t.name);
    return y ? `${t.short} (${y})` : t.short;
  };
  // Bilingual strip: short Greek source · short translation (omit either if absent).
  $: pairText = [greekSrc?.short, citeShort(selectedTrans)].filter(Boolean).join(' · ');

  type View = 'both' | 'greek' | 'english';
  let view: View = 'both';
  async function setView(v: View) {
    view = v;
    try { localStorage.setItem('reader-view', v); } catch {}
    // The tracked anchors differ by view (Greek lines vs. whole columns), so
    // rebuild the scroll-spy once the DOM reflects the new view.
    await tick();
    if (spyArmed) setupScrollSpy();
  }

  // Print / Save-as-PDF: hand the currently-rendered view to the browser's
  // native print engine. The @media print stylesheet (global.css) strips the
  // app chrome, sets page breaks, and reveals a print-only title. We print the
  // on-screen view as-is, so Both / Greek / English all work via existing CSS.
  function printReader() {
    if (typeof window === 'undefined') return;
    window.print();
  }

  // Print a single chapter by temporarily hiding all seg-rows and chapter heads
  // that don't belong to the selected chapter, then restoring after print.
  function printSingleChapter(ch: string) {
    if (typeof window === 'undefined') return;
    const toRestore: { el: HTMLElement; was: string }[] = [];
    const hide = (el: HTMLElement) => {
      toRestore.push({ el, was: el.style.display });
      el.style.display = 'none';
    };
    document.querySelectorAll<HTMLElement>('.seg-row[data-chapter]').forEach(el => {
      if (el.dataset.chapter !== ch) hide(el);
    });
    document.querySelectorAll<HTMLElement>('.chapter-head').forEach(el => {
      const m = el.id.match(/^ch-\d+-(.+)$/);
      if (!m || m[1] !== ch) hide(el);
    });
    // Hide segments where every row was hidden (so the lone seg-ref doesn't print).
    document.querySelectorAll<HTMLElement>('.segment').forEach(seg => {
      const rows = seg.querySelectorAll<HTMLElement>('.seg-row[data-chapter]');
      if (rows.length > 0 && Array.from(rows).every(r => r.style.display === 'none')) hide(seg);
    });
    window.addEventListener('afterprint', () => {
      toRestore.forEach(({ el, was }) => { el.style.display = was; });
    }, { once: true });
    window.print();
  }

  // Print-menu dropdown state (chapter selector shown when book has > 1 chapter).
  let printMenuOpen = false;
  function togglePrintMenu(e: MouseEvent) {
    e.stopPropagation();
    if (printMenuOpen) { printMenuOpen = false; return; }
    printMenuOpen = true;
    document.addEventListener('click', () => { printMenuOpen = false; }, { once: true });
  }

  // Book label for chapter headings, the live context strip, and print —
  // multi-book works only, using the work's own numbering (Roman for EN).
  $: bookLabel = workMeta && workMeta.books > 1 ? `Book ${workBookLabel(workMeta, bookNum)}` : '';
  $: bekRange = segments.length
    ? (segments.length > 1
        ? `${segments[0].column}–${segments[segments.length - 1].column}`
        : segments[0].column)
    : '';
  // Whether this book has ANY English wired at all (repo task #4): a work with
  // every segment's `english` field null (a translation not yet wired, not a
  // translation that doesn't exist) has nothing for the Both/English toggle
  // buttons to show — English-only view would render every row empty. Once
  // `loading` clears, `segments` holds the real (possibly SSR-seeded) data, so
  // this is decisive rather than a transient false-during-fetch reading.
  // A segment's declared `contextEnglish` (source-passage English, see
  // ContextEnglishSpan) counts too: a dk testimonia/fragments work with no
  // primary translation at all but at least one context-English span is not
  // "nothing to show" — it has real English content in the English column
  // (bug: John 2026-07-24, thales/testimonia A1 rendered Greek-only with the
  // span dumped below the Greek column instead).
  $: hasEnglish = segments.some((seg) => !!seg.english || !!seg.contextEnglish?.length || !!seg.expandedCitation?.length);
  // Suppress any view but source-only when there's nothing to show beside it —
  // covers the default 'both', a restored localStorage/query-param choice, and
  // the mobile/jump-in defaults set in onMount, all in one place, without any
  // of those call sites needing to know about hasEnglish themselves.
  $: if (!loading && !hasEnglish && view !== 'greek') view = 'greek';
  // Masthead pieces (critical-edition design): author eyebrow + work title;
  // the full source citation(s) adapted to the printed view live in the footer.
  // Fix round (Sol re-verify): the printed masthead names only
  // `selectedTrans` — the work's ONE primary translation — same as
  // Landing's `translatorNames` did before it grew `alsoCredits`
  // (per-passage translator override, e.g. Gorgias' Parnassos Press
  // speeches). Print renders every section as a single work-level line
  // rather than per-segment credits, so the narrowest honest fix is the
  // same one Landing already uses: append the alsoCredits sentence to
  // that one line, same wording/punctuation Landing quotes it with.
  $: translationLine = selectedTrans?.name
    ? `Translation: ${selectedTrans.name}${workMeta?.alsoCredits ? `; ${workMeta.alsoCredits}` : ''}`
    : '';
  $: printCite = view === 'greek'
    ? (greekSrc?.full ? `${sourceLanguageLabel} text: ${greekSrc.full}` : '')
    : view === 'english'
      ? translationLine
      : [greekSrc?.full ? `${sourceLanguageLabel} text: ${greekSrc.full}` : '',
         translationLine]
          .filter(Boolean).join('   ·   ');

  // Freeman Ancilla wave (design note §3.7): `segments` reordered per the
  // declared `displayOrder` permutation of column tokens — Freeman's own
  // printed sequence, when it diverges from the spine's document order
  // (the Lucretius citation-order-display precedent, at column
  // granularity). Citations/anchors/ids stay keyed to `seg.column`
  // everywhere else (`id="col-{seg.column}"` below), so reordering the
  // rendered LIST here is safe — nothing else looks up a segment by list
  // position. A column `displayOrder` doesn't name (unreachable once the
  // build gate's exact-permutation check has passed; defensive only for a
  // runtime that somehow sees stale/partial data) keeps its original
  // spine position, appended after every named column.
  $: orderedSegments = (() => {
    if (!displayOrder || !displayOrder.length) return segments;
    const byColumn = new Map(segments.map(s => [s.column, s]));
    const seen = new Set<string>();
    const out: Segment[] = [];
    for (const col of displayOrder) {
      const s = byColumn.get(col);
      if (s && !seen.has(col)) { out.push(s); seen.add(col); }
    }
    for (const s of segments) if (!seen.has(s.column)) out.push(s);
    return out;
  })();

  // Segments annotated with a running currentChapter so every block — including
  // continuation blocks that don't open a new chapter — knows which chapter it
  // belongs to. Used for per-chapter print filtering via data-chapter attributes.
  $: enrichedSegments = (() => {
    let runCh = '';
    return orderedSegments.map(seg => {
      const blocks = splitSegment(seg);
      return {
        seg,
        blocks: blocks.map(b => {
          if (b.chapter) runCh = b.chapter;
          return { ...b, currentChapter: runCh } as EnrichedBlock;
        }),
      };
    });
  })();

  // Ordered list of distinct chapter identifiers present in the loaded book.
  // Empty-string entries (no chapter assignment yet) are filtered out.
  $: chaptersInBook = [...new Set(
    enrichedSegments.flatMap(s => s.blocks.map(b => b.currentChapter)).filter(Boolean)
  )];

  // ── Live URL tracking (aquinas.cc style) ─────────────────────────────────
  // As the reader scrolls, rewrite the location hash to the Bekker citation at
  // the top of the reading area, so any position is a citable link. Line-level
  // when the Greek column is visible (our lineation is canonical Bekker);
  // column-level in English-only view (its line numbers are interpolated
  // estimates). history.replaceState keeps this out of back-history and avoids
  // jumping the scroll. We arm the spy only on the first user scroll so an
  // opened #citation link isn't overwritten before the reader actually moves.
  let spyObserver: IntersectionObserver | null = null;
  let spyState = new Map<Element, number | null>();
  let spyArmed = false;
  let lastCite = '';
  let suppressArmUntil = 0;   // ignore scroll-events from our own programmatic scrolls
  let resizeTimer: ReturnType<typeof setTimeout> | undefined;

  // ── Cached DOM refs for the per-tick sweeps below (task #33 perf fix) ─────
  // updateChapterContext/updateActiveNav used to re-run querySelectorAll (and,
  // for the nav lists, a getElementById per anchor) on EVERY rAF tick, which
  // is fine for a short Bekker chapter but not for a Diogenes-scale book
  // (100–202 sections). All three element sets are stable for the life of a
  // mounted reader: `.chapter-nav`/`.toc-outline` are plain Astro markup
  // (ReaderShell.astro, outside this island) whose links always navigate to a
  // fresh page — a book switch never mutates them in place — and
  // `.chapter-head`/`.segment` are keyed by chapter/seg.id so view/compare
  // toggles reuse the same DOM nodes rather than recreating them. Cheap to
  // rebuild anyway, so they're invalidated in setupScrollSpy() — the one
  // point that already re-runs on view change / re-arm — rather than assumed
  // permanent.
  let chapterLabelEls: HTMLElement[] | null = null;
  let segRefEls: HTMLElement[] | null = null;
  let navEntries: { a: HTMLAnchorElement; target: HTMLElement | null }[][] | null = null;
  // `undefined` is a third state distinct from "highlighted: none" (`null`):
  // it means "invalidated, DOM may still show a stale highlight, next tick
  // must do a full rewrite regardless of what it computes". setupScrollSpy()
  // resets to this sentinel rather than to `null` — if it used `null` and the
  // next computed `current` also came out `null` (nothing under the
  // boundary), the change-guard below (`current === navCurrent[i]`) would
  // read null === null, skip the DOM sweep, and leave the previous view's
  // .current/aria-current frozen on screen (task #33 follow-up regression).
  let navCurrent: (HTMLAnchorElement | null | undefined)[] = [undefined, undefined];

  function citeOf(el: Element): string | null {
    // Compose through the work's citation scheme so the hash reads as a real
    // citation: "1094a15" (bekker line), "17a" (stephanus — the line is dropped,
    // never "17a5"). formatCite is byte-identical to the old concatenation for
    // schemes with user-facing lines.
    // Line form first (L{col}-{n}); then DK prose-flow column-only (L{col}) —
    // never derived from run n, so negative n cannot yield "LB4--1" / "#B4-.1".
    // Continuation ids L{col}-{n}-c{k} are excluded (see greekLineIdForScrollCite).
    if (el.id.startsWith('L')) {
      const g = greekLineIdForScrollCite(el.id);
      if (g) return formatCite(work, g.column, g.line);
    }
    const cm = el.id.match(/^col-(.+)$/);       // segment/tick: col-{column} → {column}
    if (cm) return formatCite(work, cm[1]);
    // English-view row tick of the turn flow (no id — the Greek tick owns
    // col-{token}); the section token rides a data attribute instead.
    const dt = el.getAttribute('data-etick');
    return dt ? formatCite(work, dt) : null;
  }

  function updateHash(cite: string | null) {
    if (!cite || cite === lastCite) return;
    lastCite = cite;
    try { history.replaceState(history.state, '', `#${cite}`); } catch {}
    // Remember the last position per work so the work-switcher can resume here.
    try { localStorage.setItem(`reader-loc-${work}`, cite); } catch {}
  }

  // ── Live book/chapter context in the sticky controls strip ───────────────
  // Chapter heads scroll away with the text (they sit inside segments, so
  // CSS sticky can't carry them across segment boundaries); the strip shows
  // the label of the last chapter head above the reading line instead, so
  // the reader always knows where they are. Sampled on scroll, rAF-throttled.
  let liveChapter = '';
  let ctxRaf = 0;
  // The Lyceum chrome's running head shows the live position too (its line IS
  // the navigation there), and it is a separate island outside this one, so
  // each change is published on `document` as a `reader-position` event.
  // Additive: nothing in this component reads it back.
  let lastPosition = '';
  function updateChapterContext() {
    const strip = document.querySelector('.reader-controls');
    // +56 (3.5rem) matches .segment/.chapter-head's own scroll-margin-top
    // reserve (global.css), so a just-arrived deep link (scrollIntoView
    // honours that same reserve) is recognised as "here" immediately, not
    // one entry short.
    const boundary = (strip?.getBoundingClientRect().bottom ?? 100) + 56;
    if (!chapterLabelEls) {
      chapterLabelEls = Array.from(document.querySelectorAll<HTMLElement>('.chapter-head .chapter-label'));
    }
    let label = '';
    let posColumn = '';
    for (const h of chapterLabelEls) {
      if (h.getBoundingClientRect().top <= boundary) {
        label = h.textContent?.trim() ?? '';
        posColumn = h.closest('.chapter-head')?.id.replace(/^ch-\d+-/, '') ?? '';
      } else break;
    }
    // Section-scheme works (book-section, flat `section`, Stephanus) have no
    // chapter heads — `.seg-ref` (the column reference beside each segment,
    // e.g. "4.23" or "5") plays the same "where am I" role, so fall back to it.
    // Reads `.seg-ref-label` (not the whole `.seg-ref`) so a fragment work's
    // per-passage translation toggle, now a sibling inside `.seg-ref`, never
    // leaks its button text ("Freeman · Burnet") into this breadcrumb.
    if (!label) {
      if (sectionFlow) {
        if (!segRefEls) segRefEls = Array.from(document.querySelectorAll<HTMLElement>('.segment[id^="col-"]'));
        for (const r of segRefEls) {
          if (r.getBoundingClientRect().top <= boundary) { label = sectionFlowSpyLabel(r.id); posColumn = r.id.slice(4); }
          else break;
        }
      } else {
        if (!segRefEls) segRefEls = Array.from(document.querySelectorAll<HTMLElement>('.seg-ref'));
        for (const r of segRefEls) {
          if (r.getBoundingClientRect().top <= boundary) {
            label = r.querySelector('.seg-ref-label')?.textContent?.trim() ?? r.textContent?.trim() ?? '';
            posColumn = r.closest('[id^="col-"]')?.id.slice(4) ?? '';
          } else break;
        }
      }
    }
    // Change-guard: assigning liveChapter (even to its own value) marks it
    // dirty and schedules a Svelte update every tick — skip when unchanged.
    if (label !== liveChapter) liveChapter = label;
    const position = `${posColumn}|${label}`;
    if (posColumn && position !== lastPosition) {
      lastPosition = position;
      document.dispatchEvent(new CustomEvent('reader-position', {
        detail: { book: bookNum, column: posColumn, label },
      }));
    }
    updateActiveNav(boundary);
  }
  function onCtxScroll() {
    if (ctxRaf) return;
    ctxRaf = requestAnimationFrame(() => { ctxRaf = 0; updateChapterContext(); });
  }

  // ── Contents-picker scroll-sync ───────────────────────────────────────────
  // Highlights the entry for the chapter/section currently under the reading
  // line in both contents surfaces: the header's inline chip row
  // (`.chapter-nav`) and the full-work outline drawer (`.toc-outline`). Both
  // are plain Astro-rendered markup (ReaderShell.astro), not part of this
  // Svelte island, so — like the liveChapter sweep above — this reaches out
  // via direct DOM queries. Each entry's `data-ch` names the same chapter-head
  // / segment id the scroll-spy already resolves citations against
  // (`ch-{book}-{chapter}` or `col-{column}`); entries for a different book's
  // chapters (the full outline lists every book, only the current one's ids
  // exist on this page) resolve to no element and are left alone.
  function updateActiveNav(boundary: number) {
    if (!navEntries) {
      navEntries = [
        Array.from(document.querySelectorAll<HTMLAnchorElement>('.chapter-nav a[data-ch]')),
        Array.from(document.querySelectorAll<HTMLAnchorElement>('.toc-outline a[data-ch]')),
      ].map((anchors) => anchors.map((a) => ({ a, target: document.getElementById(a.dataset.ch!) })));
    }
    navEntries.forEach((entries, i) => {
      let current: HTMLAnchorElement | null = null;
      for (const { a, target } of entries) {
        if (!target) continue;
        if (target.getBoundingClientRect().top <= boundary) current = a;
        else break;
      }
      // Change-guard: only touch classList/aria-current when the highlighted
      // entry actually moved, instead of rewriting every anchor every tick.
      // navCurrent[i] === undefined (set by setupScrollSpy's invalidation)
      // never matches a `current` of null or an anchor, so the first tick
      // after invalidation always falls through and does one full sweep —
      // that's what clears a stale highlight left over from before.
      if (current === navCurrent[i]) return;
      navCurrent[i] = current;
      for (const { a } of entries) {
        if (a === current) {
          a.classList.add('current');
          a.setAttribute('aria-current', 'location');
        } else {
          a.classList.remove('current');
          a.removeAttribute('aria-current');
        }
      }
    });
  }

  function setupScrollSpy() {
    spyObserver?.disconnect();
    spyState = new Map();
    // Invalidate the chapter-context/nav caches too: this is the one point
    // that already re-runs on view change (Greek/English cells toggling can
    // shift which .chapter-head/.seg-ref/.segment nodes are on screen) and on
    // re-arm, so it's the natural place to force a fresh read.
    chapterLabelEls = null;
    segRefEls = null;
    navEntries = null;
    navCurrent = [undefined, undefined];
    const greekVisible = view === 'greek' || view === 'both';
    // English-only view has no Greek lines to observe: section segments carry
    // ids in the segment layout; in the turn flow the row-level English ticks
    // ([data-etick]) stand in for them.
    const els = Array.from(document.querySelectorAll(
      greekVisible ? '.greek-line[id]' : '.segment[id], [data-etick]'));
    if (!els.length) return;
    const headerH = Math.round(document.querySelector('.page-header')?.getBoundingClientRect().height ?? 60);
    // The reading area starts below the sticky header AND the sticky controls
    // strip pinned beneath it, so the detection band begins at the strip's bottom.
    const ctrlBottom = document.querySelector('.reader-controls')?.getBoundingClientRect().bottom ?? 0;
    const topInset = Math.max(headerH, Math.round(ctrlBottom));
    // Detection band: a strip just below the sticky chrome. The intersecting
    // anchor highest on screen is the line currently at the top of the reading area.
    spyObserver = new IntersectionObserver((entries) => {
      for (const e of entries) spyState.set(e.target, e.isIntersecting ? e.boundingClientRect.top : null);
      let best: Element | null = null;
      let bestTop = Infinity;
      for (const [el, top] of spyState) {
        if (top != null && top < bestTop) { bestTop = top; best = el; }
      }
      if (best) updateHash(citeOf(best));
    }, { rootMargin: `-${topInset + 8}px 0px -82% 0px`, threshold: 0 });
    els.forEach((el) => spyObserver!.observe(el));
  }

  // Arm on the first genuine user scroll. Scroll events from our own
  // programmatic jumps (citation/search) fall inside the suppression window and
  // are ignored, so an opened #citation stays put until the reader moves.
  function onScrollArm() {
    if (Date.now() < suppressArmUntil) return;
    window.removeEventListener('scroll', onScrollArm);
    spyArmed = true;
    setupScrollSpy();
  }

  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (spyArmed) setupScrollSpy(); }, 200);
  }

  // Open at a Bekker citation from the URL hash: the exact Greek line if it's
  // present and visible, otherwise the owning column. Instant (no animation) so
  // it doesn't stream scroll-events, and suppressed so it doesn't self-arm.
  function scrollToCitation(column: string, line: number | null) {
    suppressArmUntil = Date.now() + 800;
    // A null line (a lineless-scheme citation like "17a", or any column-only
    // reference) targets the whole segment; otherwise the exact Greek line if
    // it's present and visible, else its owning column.
    const lineEl = line != null ? document.getElementById(`L${column}-${line}`) : null;
    if (lineEl && (lineEl as HTMLElement).offsetParent !== null) {
      lineEl.scrollIntoView({ behavior: 'auto', block: 'center' });
    } else {
      // col-{column} is the section segment (segment layout) or the section's
      // Greek gutter tick (turn flow). A hidden tick (English-only view hides
      // the Greek cells) falls back to the row-level English tick.
      const colEl = document.getElementById(`col-${column}`);
      const target = colEl && (colEl as HTMLElement).offsetParent !== null
        ? colEl
        : document.querySelector(`[data-etick="${column}"]`) ?? colEl;
      target?.scrollIntoView({ behavior: 'auto', block: 'start' });
    }
  }

  // Case-insensitive fallback for a `col-<column>` hash (Lyceum partner
  // manifest navigation.loci fragments are lowercased by the partner's own
  // schema, e.g. "#col-b30", while the reader's own element ids keep the
  // column's real case, "col-B30"). Built once per mount, on first miss, so
  // a hash restore never scans the DOM on every call.
  let colIdIndex: Map<string, Element> | null = null;
  function findColElementCaseInsensitive(hash: string): Element | null {
    if (!colIdIndex) {
      colIdIndex = new Map();
      document.querySelectorAll('[id^="col-"]').forEach((node) => {
        colIdIndex!.set(node.id.toLowerCase(), node);
      });
    }
    return colIdIndex.get(hash.toLowerCase()) ?? null;
  }

  let _onToggleSettings: () => void;
  let _onCloseSettings: () => void;

  onDestroy(() => {
    spyObserver?.disconnect();
    if (typeof window !== 'undefined') {
      window.removeEventListener('scroll', onScrollArm);
      window.removeEventListener('scroll', onCtxScroll);
      window.removeEventListener('resize', onResize);
      if (_onToggleSettings) window.removeEventListener('toggle-settings', _onToggleSettings);
      if (_onCloseSettings)  window.removeEventListener('close-settings',  _onCloseSettings);
      document.removeEventListener('mouseup', checkCopyBtn);
      document.removeEventListener('selectionchange', onSelectionChange);
    }
  });

  function isHit(surface: string): boolean {
    if (!hlGrkFolds.length) return false;
    const f = greekFold(surface);
    return f.length > 0 && hlGrkFolds.some(q => f.startsWith(q));
  }
  function esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function highlightEng(text: string): string {
    // Sidenote [[sN]] and figure [[figN]] markers are rendered elsewhere (the
    // right rail / an inline figure), so strip them from the prose flow.
    text = text.replace(/\s*\[\[(?:s|fig)\d+\]\]\s*/g, ' ');
    if (!hlEngTerms.length) return esc(text);
    return highlightPrefixMatches(text, hlEngTerms);
  }
  // §Phase-3 B5: the printed number is stored as `display`; identity is the
  // (scope, number) pair encoded in the label — continuous scope's label IS
  // the display digits (label === display, zero-change case), while a scoped
  // label ("2.3.1") or a star/dagger glyph carries its display as the
  // trailing component. Pure function of the label alone, so both Reader
  // (button text) and FootnotePopup (popup header) can compute it locally
  // without threading an extra value through the marker string itself.
  function fnDisplay(label: string): string {
    if (label === '*' || label === '†') return label;
    const i = label.lastIndexOf('.');
    return i === -1 ? label : label.slice(i + 1);
  }
  // A footnote-bearing translation (Ostwald's third slot, the Isagoge's Owen,
  // or — Phase 4B — an imported overlay; see fnTransIds above) carries inline
  // `[^label]` footnote references; turn each into a clickable superscript.
  // §B4.2: the label is the full scope-qualified identity (continuous scope:
  // plain digits, unchanged from before); the button only ever displays the
  // printed number. `data-fn-trans` records which translation's footnote map
  // to resolve against (§B4.3/4.4) — needed once more than one translation on
  // the page can carry footnotes. A delegated click handler on the column
  // reads both data attributes and opens the footnote popup.
  function renderThird(text: string, transId: string): string {
    // The marker <button> is an atomic inline box, and engines may take a
    // line-break opportunity at its edge even with no space — WKWebView
    // orphans the superscript onto the next line ("pair, | ¹ one thing").
    // Glue it to the word it annotates with a nowrap wrapper. The capture
    // deliberately stops at whitespace, tag brackets, and entities so it can
    // never swallow a fragment of highlightEng's own markup; if a tag abuts
    // the marker the wrapper just holds the marker alone (no worse than
    // before).
    return highlightEng(text).replace(
      /([^\s<>&]*)\[\^([\w.*†]+)\]/g,
      (_m, lead: string, label: string) => {
        const display = fnDisplay(label);
        return `<span class="fn-anchor">${lead}<button type="button" class="fn-marker" data-fn="${label}" data-fn-trans="${transId}" aria-label="Footnote ${display}">${display}</button></span>`;
      },
    );
  }

  // A segment renders as one or more blocks split at chapter boundaries.
  // `chapter` is non-null on the block that begins a new chapter (heading shown).
  // Every English slot (primary / secondary / third) lays out as flowing prose with
  // its Bekker numbers floated into the margin at their exact offsets (see
  // flowParts). A GreekLine may be a partial slice of a real line (cont = its
  // tail half, after a mid-line chapter split): it suppresses the repeated id.
  // `paraN` (splitGreekSections output, shared/lib/speakers.ts): the TLG
  // section number this piece opens — set only on a line SPLIT from a
  // chapter's `sections` channel (Discourses); rendered as a small muted
  // label before the line.
  type RLine = GreekLine & { cont?: boolean; paraN?: number };
  interface Block { chapter: string | null; bekker: string; lines: RLine[]; flow: FlowPart[]; oflows: Record<string, FlowPart[]>; otables: Record<string, { n: number; rows: string[][] }[]>; sidenotes: number[]; figs: number[]; }
  // EnrichedBlock annotates each block with the chapter it belongs to (tracking
  // across segments so continuation blocks know their chapter too).
  interface EnrichedBlock extends Block { currentChapter: string; }
  // A flowing-prose part: either a text run (n null) or a Bekker margin marker
  // (text null) placed at an exact mid-sentence offset — no row break.
  // verseStart/verseEnd/verseBreak are zero-width standoff markers (from a
  // chunk's `verse` ranges — see EnglishChunk in shared/lib/data.ts) that
  // groupVerse (below) folds into <div class="verse"> / <span
  // class="verse-line"> wrappers at render time; flowParts (below) merges
  // them into the SAME offset-sorted event stream as ticks/paragraph breaks,
  // so a tick or paragraph marker that falls inside a verse range is neither
  // dropped nor double-rendered — it is just another event in one linear
  // pass (see flowParts' `priority` ordering for the exact tie-breaks at a
  // shared offset).
  interface FlowPart {
    text: string | null; n: number | null; real: boolean; para?: boolean;
    // The TLG/Loeb section number a paragraph break opens (Discourses'
    // `paras` channel — see EnglishChunk.paras); null for an unlabeled
    // paragraph break (every other work's `markers: [{kind:"paragraph"}]`).
    // Rendered as a small muted label — never affects layout otherwise.
    paraN?: number | null;
    verseStart?: boolean; verseEnd?: boolean; verseBreak?: boolean;
    // Freeman Ancilla wave (design note §3's `.eng-source-frame`): true on
    // a text run that falls (in full or in part — flowParts splits a run
    // at a frame boundary so this is always exact) inside a source-
    // citation frame range (EnglishChunk.frames). Never set on a tick/
    // para/verse marker part.
    frame?: boolean;
  }

  // The char position where token `w` begins in a line's text (0 at the start,
  // text.length at/after the end), so a cut preserves the verbatim
  // punctuation/sigla between words on the correct side.
  function tokenPos(line: GreekLine, w: number): number {
    if (w <= 0) return 0;
    if (w >= line.tokens.length) return line.text.length;
    let ptr = 0;
    for (let i = 0; i < w; i++) {
      const idx = line.text.indexOf(line.tokens[i].t, ptr);
      if (idx >= 0) ptr = idx + line.tokens[i].t.length;
    }
    const cut = line.text.indexOf(line.tokens[w].t, ptr);
    return cut >= 0 ? cut : ptr;
  }

  // The sub-line covering tokens [fromW, toW) — used to split a Greek line at a
  // chapter boundary that falls mid-line (most chapters start mid-line). A
  // partial tail (fromW>0) is marked `cont` so the line number/id isn't repeated.
  function lineSlice(line: GreekLine, fromW: number, toW: number): RLine {
    fromW = Math.max(0, fromW);
    toW = Math.min(line.tokens.length, toW);
    if (fromW === 0 && toW === line.tokens.length) return line;
    let text = line.text.slice(tokenPos(line, fromW), tokenPos(line, toW));
    if (fromW > 0) text = text.replace(/^\s+/, '');
    if (toW < line.tokens.length) text = text.replace(/\s+$/, '');
    return { n: line.n, text, tokens: line.tokens.slice(fromW, toW), cont: fromW > 0 };
  }

  // Flowing prose with Bekker numbers floated into the margin at their EXACT
  // offsets (no row break, no in-text number, no sentence-boundary snapping).
  // Used for precisely-placed translations like the gloss-aligned secondary.
  //
  // `verseRanges` (optional — see EnglishChunk.verse) are ALREADY-rebased
  // char ranges over `text`: {start, end, breaks}. Every boundary (a range's
  // start/end and each interior break) is folded into the SAME offset-sorted
  // event stream as `ticks`/`paraOffsets` — a single linear pass that adds
  // each character span exactly once (`cur` only ever advances) — rather
  // than a second independent pass over `text`. That is what makes a tick or
  // paragraph marker landing inside (or exactly at the edge of) a verse
  // range safe: it is just one more event at its offset, never processed
  // twice and never able to split a span the main loop already emitted. At a
  // shared offset, `priority` breaks the tie: a verse range's end closes
  // BEFORE anything else fires there (so an event sitting exactly on the
  // boundary lands OUTSIDE, matching the exclusive `end`), its start opens
  // BEFORE a tick/para at the same offset (so that event lands INSIDE), and
  // an interior break splits the verse line BEFORE a tick at that same
  // offset attaches (so the tick marks the start of the new line, not the
  // tail of the one just closed) — ticks then attach to paras, as before.
  // `paraOffsets` entries are either a bare offset (unlabeled paragraph
  // break — Stephanus dialogues' `markers: [{kind:"paragraph"}]`, turn-flow
  // `ep`) or `{off, n}` (Discourses' `paras` channel: the TLG/Loeb section
  // number the new paragraph opens, rendered as a small muted label — see
  // EnglishChunk.paras). Both shapes coexist so every EXISTING caller
  // passing bare numbers is untouched.
  // `frameRanges` (optional — see EnglishChunk.frames): ALREADY-rebased
  // [start, end) char ranges over `text` marking a Freeman source-citation
  // lead-in (design note §3's `.eng-source-frame`). Folded into the SAME
  // offset-sorted event stream as ticks/paras/verse — a `frameStart`/
  // `frameEnd` pair toggles a running `frameOn` flag that tags every text
  // run pushed while it's set, so a tick/para landing mid-frame splits the
  // frame cleanly instead of swallowing or losing it. Non-nesting (the
  // extractor never emits overlapping frames).
  function flowParts(
    text: string,
    ticks: { n: number; real: boolean; off: number }[],
    paraOffsets: (number | { off: number; n: number | null })[] = [],
    verseRanges: { start: number; end: number; breaks: number[] }[] = [],
    frameRanges: { start: number; end: number }[] = [],
  ): FlowPart[] {
    type Kind = 'verseEnd' | 'verseStart' | 'verseBreak' | 'frameEnd' | 'frameStart' | 'tick' | 'para';
    const priority: Record<Kind, number> =
      { verseEnd: 0, verseStart: 1, frameEnd: 2, frameStart: 3, verseBreak: 4, tick: 5, para: 6 };
    const evs: { off: number; kind: Kind; n: number; real: boolean; paraN: number | null }[] = [
      ...ticks.map(t => ({ off: t.off, kind: 'tick' as const, n: t.n, real: t.real, paraN: null })),
      ...paraOffsets.map(p => typeof p === 'number'
        ? { off: p, kind: 'para' as const, n: 0, real: false, paraN: null }
        : { off: p.off, kind: 'para' as const, n: 0, real: false, paraN: p.n }),
    ];
    for (const v of verseRanges) {
      evs.push({ off: v.start, kind: 'verseStart', n: 0, real: false, paraN: null });
      for (const b of v.breaks) evs.push({ off: b, kind: 'verseBreak', n: 0, real: false, paraN: null });
      evs.push({ off: v.end, kind: 'verseEnd', n: 0, real: false, paraN: null });
    }
    for (const f of frameRanges) {
      evs.push({ off: f.start, kind: 'frameStart', n: 0, real: false, paraN: null });
      evs.push({ off: f.end, kind: 'frameEnd', n: 0, real: false, paraN: null });
    }
    evs.sort((a, b) => a.off - b.off || priority[a.kind] - priority[b.kind]);
    const parts: FlowPart[] = [];
    let cur = 0;
    let frameOn = false;
    const addText = (s: string) => {
      const segs = s.split('\n');
      for (let i = 0; i < segs.length; i++) {
        if (i > 0) parts.push({ text: '\n', n: null, real: false });
        if (segs[i]) parts.push({ text: segs[i], n: null, real: false, ...(frameOn ? { frame: true } : {}) });
      }
    };
    for (const e of evs) {
      const off = Math.max(0, Math.min(e.off, text.length));
      if (off > cur) { addText(text.slice(cur, off)); cur = off; }
      if (e.kind === 'para') parts.push({ text: null, n: null, real: false, para: true, paraN: e.paraN });
      else if (e.kind === 'verseStart') parts.push({ text: null, n: null, real: false, verseStart: true });
      else if (e.kind === 'verseEnd') parts.push({ text: null, n: null, real: false, verseEnd: true });
      else if (e.kind === 'verseBreak') parts.push({ text: null, n: null, real: false, verseBreak: true });
      else if (e.kind === 'frameStart') frameOn = true;
      else if (e.kind === 'frameEnd') frameOn = false;
      else parts.push({ text: null, n: e.n, real: e.real });
    }
    if (cur < text.length) addText(text.slice(cur));
    return parts;
  }

  // Groups a flow's rendered parts (post attachTicks) into verse blocks: a
  // run between a verseStart and its verseEnd becomes one VerseGroup, its
  // parts split into `lines` at each verseBreak; every other part passes
  // through unchanged. A flow with no verse markers at all (the overwhelming
  // majority — verse only ever comes from a chunk's optional `verse` field)
  // never enters the verseStart branch, so groupVerse is a byte-identical
  // pass-through for it: `out` ends up holding the exact same part objects,
  // in the exact same order, as `parts` itself.
  interface VerseGroup { verse: true; lines: RenderPart[][]; }
  type FlowItem = RenderPart | VerseGroup;
  function groupVerse(parts: RenderPart[]): FlowItem[] {
    const out: FlowItem[] = [];
    let lines: RenderPart[][] | null = null;
    for (const part of parts) {
      if (part.verseStart) { lines = [[]]; continue; }
      if (part.verseBreak) { lines?.push([]); continue; }
      if (part.verseEnd) {
        if (lines) { out.push({ verse: true, lines }); lines = null; }
        continue;
      }
      if (lines) lines[lines.length - 1].push(part);
      else out.push(part);
    }
    if (lines) out.push({ verse: true, lines }); // unterminated range guard
    return out;
  }

  // A standalone tick span is absolutely positioned with no `top`, so its
  // static position decides which line it reads against — and a marker box
  // sitting BETWEEN two text runs attaches to the END of the previous
  // rendered line whenever the marked word starts a new one. The tick then
  // shows a full rendered line (visually a sentence) too early, at every
  // column width. Merging each tick into the FOLLOWING text run as its first
  // child pins its static position to the first line box of the text it
  // marks. (It also keeps `.para-br + .bk-seg` adjacency intact when a tick
  // lands exactly on a paragraph start.) Ticks with an attached table — or
  // with no following text run — keep the standalone rendering.
  type RenderPart = FlowPart & { tick?: { n: number; real: boolean } };
  function attachTicks(parts: FlowPart[], tableNs: Set<number> = new Set()): RenderPart[] {
    const isText = (p: FlowPart | undefined): p is FlowPart => !!p && p.text !== null && p.text !== '\n';
    const isBreak = (p: FlowPart | undefined): boolean => !!p && (p.text === '\n' || p.para === true);
    const out: RenderPart[] = [];
    for (let i = 0; i < parts.length; i += 1) {
      const part = parts[i];
      const isTick = part.text === null && part.n !== null && !part.para;
      if (isTick && part.n !== null && !tableNs.has(part.n)) {
        const next = parts[i + 1];
        if (isText(next)) {
          out.push({ ...next, tick: { n: part.n, real: part.real } });
          i += 1;
          continue;
        }
        // A tick coinciding with a paragraph boundary marks the paragraph's
        // OPENING word: emit the break first, then the opener carrying the
        // tick (leaving the tick standalone before the <br> re-creates the
        // previous-line attachment this helper exists to prevent).
        if (isBreak(next) && isText(parts[i + 2])) {
          out.push(next);
          out.push({ ...parts[i + 2], tick: { n: part.n, real: part.real } });
          i += 2;
          continue;
        }
      }
      out.push(part);
    }
    return out;
  }

  // Split a line into clickable words, the verbatim text between them, and (for
  // Stephanus dialogues) speaker lead-in labels spliced in at each turn offset.
  // The tokens hold bare words (for the popup lookup); the line `text` keeps the
  // original punctuation AND the OCT editorial sigla ( ) [ ] < > † " — so the
  // gaps render as plain, non-clickable text, preserving the critical edition.
  // The position math lives in shared/lib/speakers.ts (see lineRenderParts):
  // with no speaker events it is byte-identical to the old token/gap split.
  const speakerEvents = (seg: Segment, line: RLine): SpeakerEvent[] =>
    // Speaker offsets are char positions in the FULL line, so they only apply to
    // a whole (non-`cont`) line; stephanus never splits lines (no chapters), but
    // guard anyway so a sliced line can't attach an event at a shifted offset.
    line.cont ? [] : (seg.speakers ?? []).filter((s) => s.line === line.n);

  // Clickable parts for a table cell (same shape as a line: text + tokens;
  // tables carry no speaker turns).
  function cellParts(cell: { text: string; tokens: Token[] }): LineRenderPart[] {
    return lineRenderParts(cell.text, cell.tokens);
  }

  // Lined-source only (Discourses, docs/lined-source-plan.md §3/Q2; wrapO
  // deviation 2026-08-29, §3): the render parts for a `kind: 'line'`
  // GreekItem, folding in its hyphen-split state as ONE expression -- kept
  // out of the template as a function call rather than `{@const}` because a
  // `{@const}` inside this branch adds its own anchor comment to the
  // compiled output, breaking the byte-identity regression contract for
  // every other work's lines (Stage 4 acceptance, §6). `item.line.wrap`/
  // `item.line.wrapO` (this line absorbed a continuation) repaints the
  // WRAPPED token (located by `wrapO`, not by array position -- see
  // splitWrapLine's own doc comment) as the truncated head + hyphen;
  // `item.leadFragment` (the PREVIOUS line carried a wrap) is the PARTS LIST
  // that line's own splitWrapLine call carried forward -- the wrapped
  // word's remainder plus everything printed after it (text and token parts
  // alike, e.g. a glued em dash and a following whole word), each part
  // still bound to its own token object so it stays independently
  // clickable. Both are no-ops for every line without these fields, so this
  // returns exactly `lineRenderParts(...)`'s own result then.
  //
  // The carried block and this line's own content were ONE whitespace-
  // separated print line before the pipeline's rejoin split them (the
  // pipeline strips the fragment AND its trailing space from this line's
  // `text`, per I4's byte-identical round-trip) -- so a single literal space
  // is spliced back in between them here, or "κιμαστικήν." would glue
  // straight onto "ἡ" as "κιμαστικήν.ἡ". No space when this line's own text
  // is empty (the fully-absorbed case, docs/lined-source-plan.md §3): the
  // carried block IS the line's entire rendered content there, with nothing
  // to separate it from. No space is ever inserted WITHIN the carried
  // block's own parts -- they were contiguous in the source text.
  function lineParts(item: { line: RLine; leadFragment?: LineRenderPart[] }, seg: Segment): LineRenderPart[] {
    const base = lineRenderParts(item.line.text, item.line.tokens, speakerEvents(seg, item.line));
    const head = item.line.wrap != null && item.line.wrapO != null
      ? splitWrapLine(base, item.line.wrapO, item.line.wrap).head
      : base;
    if (!item.leadFragment || !item.leadFragment.length) return head;
    return item.line.text
      ? [...item.leadFragment, { kind: 'text', text: ' ' }, ...head]
      : [...item.leadFragment, ...head];
  }

  // Turn-flow rows for a dialogue book (the pipeline emitted turnFlow): the
  // whole book renders as one continuous flow of turn rows — each speaker's
  // statement level with its translation, Stephanus sections as gutter ticks
  // (see speakers.ts buildFlowRows). Null for narrated books / non-stephanus
  // works, which render the segment array exactly as before. Reactive because
  // a fetch-mounted reader receives segments + turnFlow after onMount.
  let flowRows: FlowRow[] | null = null;
  $: flowRows =
    stephanus && turnFlow?.turns?.length
      ? buildFlowRows(segments, turnFlow)
      : null;
  // A narrated work's paragraph-anchored flow (Republic, Apology, Charmides,
  // Letters, Lovers): the same flow renderer, but rows are paragraphs (no
  // speaker — the em-dash fallback lead-in is suppressed) with English
  // paragraph breaks (`ep`), optional embedded dialogue (`et`), and optional
  // one-sided sub-speeches (`sub`). See flowRowsView.
  $: paraFlow = turnFlow?.kind === 'para';

  // Redundant-label suppression. When a single speaker's speech is split into a
  // new row — a section-boundary split whose Greek runs on, or a folded
  // one-sided continuation (`sub`) — the pipeline re-emits the speaker name, so
  // the reader would print e.g. "Soc." twice in a row for an unbroken speech
  // (Meno 70b→c). Print convention drops the name when the same speaker
  // continues: walk the rows in render order tracking who holds the floor, and
  // flag a lead-in / sub label as redundant when it repeats the current
  // speaker's same printed label (see labelSuppression in shared/lib/speakers).
  // Dialogue flows only — narrated `et` blocks carry no canonical speaker.
  $: rowMeta = paraFlow || !flowRows ? [] : labelSuppression(flowRows);

  // English turn blocks for a narrated work's said-bearing chunk (no turnFlow):
  // each turn is its own paragraph block with its lead-in — how print editions
  // set unaligned speeches — never an inline splice, so a label can't glue to
  // the previous sentence (speakers.ts buildEnglishTurnBlocks, pure + tested).
  function englishTurnBlocks(seg: Segment): EnglishTurnBlock[] {
    return buildEnglishTurnBlocks(seg.english?.text ?? '', seg.english?.turns ?? []);
  }
  // Embedded-dialogue blocks for a paragraph-flow row carrying `et` (english.turns
  // nested inside a narrated paragraph). buildEnglishTurnBlocks gives the speaker
  // structure; we re-anchor each trimmed block inside the row's English (indexOf
  // from a moving pointer — trim only strips surrounding whitespace, so the block
  // is a genuine substring) so any paragraph breaks (`ep`) fall in the right block
  // as block-local offsets. Lets ep + et coexist without dropping either.
  type EtBlock = EnglishTurnBlock & { ep: number[] };
  function etBlocks(
    english: string,
    et: { o: number; s: string | null; d: string | null }[],
    ep: number[] | null | undefined,
  ): EtBlock[] {
    const blocks = buildEnglishTurnBlocks(
      english,
      et.map((e) => ({ offset: e.o, speaker: e.s, display: e.d })),
    );
    let ptr = 0;
    return blocks.map((b) => {
      const found = b.text ? english.indexOf(b.text, ptr) : -1;
      const rawStart = found < 0 ? ptr : found;
      ptr = rawStart + b.text.length;
      const bep = (ep ?? [])
        .map((o) => o - rawStart)
        .filter((o) => o > 0 && o < b.text.length);
      return { ...b, ep: bep };
    });
  }
  const isUnpairedDialogue = (seg: Segment): boolean =>
    stephanus && !!seg.english?.turns?.length;
  // Section-flow keeps the ordinary `.seg-ref` when the header carries
  // editorial meaning (a kind chip, or an English title).
  const keepSectionFlowHeader = (seg: Segment): boolean =>
    (!!seg.kind && (seg.kind as string) !== 'text') || !!seg.english?.title;
  // DK inline "(NN)" section-marker split gating (fix round, finding 1 — Sol
  // review): the marker split may only fire when this column actually
  // carries parallel per-section English. Derives the set of section
  // numbers named by the segment's own contextEnglish spans from their
  // `sectionLoci` ("1.22" → 22) — a span with no sectionLoci (single-section
  // locus) contributes nothing, same as no contextEnglish at all. Returns
  // undefined (never an empty Set) so buildProseFlow's own "no set at all"
  // fast path stays the single source of the gating decision.
  //
  // item 85 review (2026-07-28): a whole-column-verbatim column whose
  // English ships a per-passage `credit` (english.column_sources — Gorgias
  // B11/B11a's Parnassos Press speeches) carries the SAME "(N)" convention
  // inline in both languages, attested 1:1 by the manifest's own section-
  // count cross-check (stage1_freeman_english.py's _greek_section_count).
  // No new pipeline field is needed to tell the Greek side where to split:
  // the English chunk's own text already names every section number, so the
  // Greek scans it directly. Gated on BOTH flags (not wholeColumnVerbatim
  // alone) so a future whole-column-verbatim column with no column_sources
  // English stays untouched — narrower than the flag by itself.
  //
  // item 85 addendum (Melissus B7/B8, 2026-07-28): `sectionParagraphSplit`
  // (citation.section_paragraph_columns; see preflight's
  // `_validate_section_paragraph_columns` and stage7_emit.py) is a SEPARATE,
  // narrower flag for columns that carry the same inline "(N)" convention
  // but keep their ordinary mixed role='context'/'text' profile (Simplicius's
  // quoting frame around Melissus's own words) -- unlike wholeColumnVerbatim,
  // it never forces frag-txt on every run (see the `seg.wholeColumnVerbatim`
  // check beside `frag-txt`/`run.cls` below), and it needs no per-column
  // `english.credit` override: the work's ordinary primary English (Freeman)
  // already carries the same ascending markers, preflight-verified.
  function contextSectionMarkerNumbers(seg: Segment): Set<number> | undefined {
    const nums = new Set<number>();
    const spans = seg.contextEnglish;
    for (const span of spans ?? []) {
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
  // Group a block's Greek lines into render items: runs of table rows (lines
  // carrying `cells`, e.g. the De Int 22a modal square) become one table; other
  // lines render individually. DK prose columns (docs/prose-flow-design.md) are
  // gathered into one flow paragraph of inline role-runs instead of a block
  // stack — verse/table/lacuna/salutation stay block-per-line.
  type GreekItem =
    | {
        kind: 'line'; line: RLine;
        // Lined-source only (Discourses, docs/lined-source-plan.md Q3):
        // true iff this line opens a new TLG section -- the segment's
        // first line, or a line whose `sec` differs from the previous
        // line's. Derived once here (document order over the whole
        // column), not re-derived at render time, so the gutter and any
        // other consumer can never disagree with each other.
        secStart?: boolean;
        // Lined-source only (Q2; wrapO deviation 2026-08-29, §3): the
        // PARTS LIST carried forward from the PREVIOUS line's wrap split
        // (splitWrapLine's `carried`) -- the wrapped word's own remainder
        // plus every render part printed after it, painted before this
        // line's own first render part. The wrapped word's remainder stays
        // bound to that SAME token object (not this line's own tokens/
        // offsets, which describe `line.text` and never contained the
        // fragment), so hovering/clicking it opens the same popup as the
        // head half painted on the previous line; a carried FULL token
        // (the em-dash glob case) keeps its own separate token binding.
        leadFragment?: LineRenderPart[];
        // Verse-block display fields, set by rebaseVerseRuns (below) --
        // never read off the data, which keeps the edition's literal
        // `indent(N)` column measurement untouched.
        vIndent?: number;
        vFirst?: boolean;
        vLast?: boolean;
      }
    | { kind: 'table'; rows: RLine[] }
    | { kind: 'flow'; prose: Extract<ProseFlowItem, { kind: 'flow' }>; anchor: boolean }
    | { kind: 'source-head'; line: RLine }
    | { kind: 'witness'; witness: Witness };
  function greekItems(lines: RLine[], column: string, sectionMarkerNumbers?: Set<number>, markerScanIncludesText?: boolean, witnesses?: Witness[]): GreekItem[] {
    // First split into table runs vs non-table stretches (order-preserving).
    type Stretch =
      | { table: true; rows: RLine[] }
      | { table: false; lines: RLine[] };
    const stretches: Stretch[] = [];
    let tableRun: RLine[] = [];
    let plain: RLine[] = [];
    const flushTable = () => {
      if (tableRun.length) { stretches.push({ table: true, rows: tableRun }); tableRun = []; }
    };
    const flushPlain = () => {
      if (plain.length) { stretches.push({ table: false, lines: plain }); plain = []; }
    };
    for (const l of lines) {
      if (l.cells && l.cells.length) {
        flushPlain();
        tableRun.push(l);
      } else {
        flushTable();
        plain.push(l);
      }
    }
    flushTable();
    flushPlain();

    const items: GreekItem[] = [];
    // design §2: lineation iff a role='text' line with positive n under a
    // hasUserFacingLines scheme; never re-derived from Greek content.
    const columnHasRoles = lines.some((l) => l.role === 'text' || l.role === 'context');
    // item 23: book-section always flows (see bookSectionFlow's own doc
    // comment) -- short-circuits to false before the original expression,
    // which is untouched for every other scheme. PILOT: `linedGreek`
    // (see its own doc comment above) overrides that short-circuit for a
    // single opted-in book-section work, forcing the ordinary lineate
    // branch below (block-per-section, via splitGreekSections' pieces)
    // exactly as `!bookSectionFlow` already would for any other scheme.
    // `proseReflow` (see WorkMeta['citation'].proseReflow) is the opt-OUT for
    // works whose scheme lineates by default: it wins over every branch
    // below, routing the column to prose flow. Verse survives regardless --
    // `isVerseLine` lifts it back out of the prose buffer.
    const lineate =
      !proseReflow
      && (linedGreek
        || (!bookSectionFlow
          && (cscheme.id !== 'dk'
            || !columnHasRoles
            || columnLineates(lines, cscheme.hasUserFacingLines))));
    const isBlockRole = (l: RLine) =>
      l.role === 'lacuna' || l.role === 'salutation' || l.role === 'heading';
    // A quoted-VERSE line inside a reflowing prose column (John's ruling
    // 2026-08-31, "reflow prose, keep the verse", for Lives). Reasoning: the
    // print-line display exists to keep GUTTER apparatus aligned with the
    // line it annotates -- the Discourses collision `linedGreek` was added
    // for. Lives carries no gutter apparatus at all (13,853 lines, zero
    // `sec`/`paraN`), so its print lines align nothing while forcing one
    // rendered line per print line: at 375px, 94% of them CSS-wrap into the
    // ragged orphan words John reported. Its prose therefore reflows.
    //
    // Its VERSE does not. The print channel's `indent >= 2` is the edition's
    // own mark that these lines are set as verse rather than prose -- Long's
    // Oxford text sets Lives' 2,259 lines of epigram and poetic quotation
    // that way -- and a verse line IS a line. So a verse line breaks the
    // prose buffer and renders as its own real line, exactly as `lacuna` and
    // `salutation` already do; rebaseVerseRuns then gives the run its inset
    // and its space above and below.
    //
    // `wrap` is deliberately ignored on this path: a line-end hyphen is page
    // geometry, and the line's own `text` already holds the WHOLE word (1.1
    // line 4 stores `Σεμνοθέους,` and merely asks the lined painter to break
    // it after 5 chars), so reflowing rejoins it with no data change.
    //
    // No-op for every work as of this commit: every column carrying
    // `indent >= 2` today reaches the lineate branch instead, via
    // `linedGreek` or a non-book-section scheme. It activates per work, as
    // each is ruled (John, 2026-08-31: "then we go work by work and
    // determine whether to keep the line presentation or reflow").
    const isVerseLine = (l: RLine) => (l.indent ?? 0) > proseIndent;
    const incipit = incipitColumnSet.has(column);
    // DK witness rows (Segment.witnesses): only when it's unambiguous where
    // they go and nothing else shares their buffer — see singlePureContextRun's
    // own doc. Consumed (set undefined) at the one context buffer it applies
    // to; every other buffer in this column, if any, keeps rendering exactly
    // as it did before `witnesses` existed.
    let witnessesPending = witnesses?.length && singlePureContextRun(lines, lineate)
      ? witnesses
      : undefined;

    // Hardening (Lives 2.125/7.160/7.166/8.83/8.84/10.120 — a handful of
    // book-section segments whose pipeline output carries two or three
    // physical Greek lines that all repeat `n: 1`, rather than the one
    // physical line every other segment gets): a `linedGreek` work's raw
    // lines (no `sections` channel — paraN is unset; a Discourses/
    // Enchiridion split PIECE always carries paraN, even its first, so this
    // never touches those) each become their own `L{column}-{n}` id below.
    // Repeating `n` within one column would collide, silently dropping every
    // line past the first from the DOM (same id, same node) — bump a
    // duplicate `n` to the next unused value so every physical line gets a
    // distinct id. No number is displayed either way (book-section hides
    // line numbers; paraN stays unset) — this only disambiguates ids.
    // The bump must skip every raw `n` in this call — table rows included —
    // not just ids already emitted: for raw [1, 1, 2] a naive next-unused
    // bump would hand the duplicate the REAL later line's id (1, 2, 2) and
    // move the collision instead of removing it. Seeding lets the duplicate
    // land past all real values (1, 3, 2). Also seeded on `linedSource`
    // (wave 1, docs/lined-rollout-plan.md Stage 3) for the same reason, even
    // though invariant I1 rules out a wave-1 segment ever repeating `n` —
    // a true no-op there, kept for parity with the painting gate below.
    const rawLineNs = new Set<number>();
    if (linedGreek || linedSource) {
      for (const s of stretches) {
        for (const l of ('table' in s && s.table ? s.rows : s.lines)) rawLineNs.add(l.n);
      }
    }
    const usedLineNs = new Set<number>();
    const dedupeLineN = (n: number): number => {
      let candidate = n;
      while (usedLineNs.has(candidate) || (candidate !== n && rawLineNs.has(candidate))) candidate += 1;
      usedLineNs.add(candidate);
      return candidate;
    };

    // Lined-source (Discourses, docs/lined-source-plan.md §3/Q2/Q3; wave 1,
    // docs/lined-rollout-plan.md Stage 3) gutter and hyphen state, tracked
    // once here across the WHOLE column in document order rather than
    // re-derived at render time. `prevSec` lets each `sec`-carrying line know
    // whether it opens a new section (Q3.1); `pendingWrapTail` carries the
    // previous line's hyphen-split remainder to the very next line pushed,
    // bound to that SAME token object (Q2). Neither field is ever set outside
    // `linedSource && l.paraN == null` lines below (the only lines a
    // `sec`/`wrap` field can appear on), and lined-source lines carry no
    // `role`, so no other item kind (table, DK context flow) can ever land
    // between a wrapped line and its continuation — the resets below are
    // defensive, not load-bearing. This whole-column framing relies on
    // `greekItems` being called once per citable column: true for Discourses
    // by construction (its own chapter/section split), and true for a wave-1
    // `section`-scheme segment because its column IS the segment and stage1's
    // flat English builder never emits a `chapters` channel, so
    // `seg.chapterStarts` is always empty and `splitSegment` never divides it
    // into more than one block (see the `!starts.length` branch below).
    let prevSec: number | undefined;
    let pendingWrapTail: LineRenderPart[] | undefined;
    // Ruling 6.3: a segment whose lines carry only ONE distinct `sec` value
    // (e.g. 37 of Enchiridion's 53 chapters) shows no gutter mark at all —
    // the number would just repeat the block header's own citable-unit
    // number ("Chapter 5"). Counted once, over every line this call sees
    // (not per stretch/table run), so it reflects the whole column per the
    // confirmation above. Provably a no-op for Discourses, whose minimum is
    // 3 sections per chapter.
    const distinctSecCount = new Set(lines.map((l) => l.sec).filter((s): s is number => s != null)).size;

    for (const s of stretches) {
      if (s.table) {
        items.push({ kind: 'table', rows: s.rows });
        pendingWrapTail = undefined;
        continue;
      }
      if (lineate) {
        // Verse DK: quote lines stay lineated; surrounding frame (role=context)
        // uses the same prose-flow peel/heal/join as prose columns — citation
        // head on its own line, frame as continuous .frag-ctx (John 2026-07-24).
        // Frame flows get no column id (verse L{col}-{n} lines carry anchors).
        let ctxBuf: RLine[] = [];
        const flushCtx = () => {
          if (!ctxBuf.length) return;
          if (witnessesPending) {
            for (const w of witnessesPending) items.push({ kind: 'witness', witness: w });
            witnessesPending = undefined;
          } else {
            for (const p of buildProseFlow(ctxBuf, { incipit, peelSoleSourceHead: true, sectionMarkerNumbers })) {
              if (p.kind === 'source-head') items.push({ kind: 'source-head', line: p.line as RLine });
              else items.push({ kind: 'flow', prose: p, anchor: false });
            }
          }
          ctxBuf = [];
        };
        for (const l of s.lines) {
          if (l.role === 'context' && !l.seamNote) {
            ctxBuf.push(l);
          } else {
            flushCtx();
            if (linedSource && l.paraN == null) {
              const n = dedupeLineN(l.n);
              const line = n === l.n ? l : { ...l, n };
              const secStart = distinctSecCount >= 2 && line.sec != null && (prevSec === undefined || line.sec !== prevSec);
              if (line.sec != null) prevSec = line.sec;
              const leadFragment = pendingWrapTail;
              // wrapO deviation (2026-08-29, docs/lined-source-plan.md §3):
              // splitWrapLine locates the WRAPPED token by `wrapO`, not by
              // array position, and its `carried` result is already the
              // full parts list this line hands to the next -- the wrapped
              // word's own remainder (`t.slice(wrap)`) followed by every
              // render part printed after it (an absorbed tail like "." or,
              // in the em-dash glob case, a glued "—" plus a whole following
              // word "πολλὴν", each still bound to its own token). See
              // splitWrapLine's own doc comment (speakers.ts) for why the
              // wrapped token is not always the last one.
              if (line.wrap != null && line.wrapO != null) {
                const parts = lineRenderParts(line.text, line.tokens);
                const carried = splitWrapLine(parts, line.wrapO, line.wrap).carried;
                pendingWrapTail = carried.length ? carried : undefined;
              } else {
                pendingWrapTail = undefined;
              }
              items.push({ kind: 'line', line, secStart, leadFragment });
            } else {
              items.push({ kind: 'line', line: l });
              pendingWrapTail = undefined;
            }
          }
        }
        flushCtx();
        continue;
      }
      // Prose flow: consecutive text|context runs → one flow group; lacuna/
      // salutation break the group as block items. seamNote stays on its line
      // (still rendered above a block line if present).
      let proseBuf: RLine[] = [];
      const flushProse = () => {
        if (!proseBuf.length) return;
        if (witnessesPending && proseBuf.every((l) => l.role === 'context')) {
          for (const w of witnessesPending) items.push({ kind: 'witness', witness: w });
          witnessesPending = undefined;
          proseBuf = [];
          return;
        }
        // A DK inline "(NN)" section-marker context run (see splitContextMarkerGroups)
        // now returns one `flow` item per paragraph instead of always one —
        // only the FIRST carries the column anchor id (`L{column}`); later
        // paragraphs of the same run stay unanchored so the DOM never gets
        // duplicate ids (scroll-spy still lands on the column's first line).
        let firstFlow = true;
        for (const p of buildProseFlow(proseBuf, { incipit, sectionMarkerNumbers, markerScanIncludesText })) {
          if (p.kind === 'source-head') items.push({ kind: 'source-head', line: p.line as RLine });
          else {
            items.push({ kind: 'flow', prose: p, anchor: firstFlow });
            firstFlow = false;
          }
        }
        proseBuf = [];
      };
      for (const l of s.lines) {
        if (isBlockRole(l) || l.seamNote || isVerseLine(l)) {
          flushProse();
          items.push({ kind: 'line', line: l });
        } else {
          proseBuf.push(l);
        }
      }
      flushProse();
    }
    rebaseVerseRuns(items);
    return items;
  }

  // A verse block's inset is REBASED, not taken literally (John's ruling
  // 2026-08-31, dashboard item 96a). The export's `indent(N)` is a physical
  // column measurement off the printed page, not a semantic verse level: a
  // printer set a short couplet further right than a long one, so Lives'
  // Linus epigram (1.4) records indent 4/5 and the Orpheus epigram (1.5)
  // records 2/3 for the SAME elegiac shape. Rendering N literally made two
  // identical couplets sit at different depths, and the old min(N,4) cap
  // made it worse in the other direction -- it flattened 1.4's real
  // hexameter/pentameter step (4 and 5 both clamped to 4) while leaving the
  // arbitrary absolute offset intact.
  //
  // The rule: within each maximal run of consecutive indented lines, the
  // run's own shallowest level is the base, and every deeper line steps in
  // exactly once. That keeps what the print MEANS -- the elegiac couplet's
  // alternation, a quotation set off from the prose -- and discards only the
  // page-geometry accident. `vFirst`/`vLast` mark the run's ends so the
  // block can breathe (John, same ruling: "a space above and below").
  function rebaseVerseRuns(items: GreekItem[]): void {
    const indentOf = (it: GreekItem): number | undefined =>
      it.kind === 'line' && it.line.indent != null && it.line.indent > proseIndent
        ? it.line.indent
        : undefined;
    let i = 0;
    while (i < items.length) {
      if (indentOf(items[i]) === undefined) { i++; continue; }
      let j = i;
      while (j < items.length && indentOf(items[j]) !== undefined) j++;
      const run = items.slice(i, j) as Extract<GreekItem, { kind: 'line' }>[];
      const base = Math.min(...run.map((it) => it.line.indent as number));
      for (const it of run) {
        it.vIndent = (it.line.indent as number) > base ? 2 : 1;
      }
      run[0].vFirst = true;
      run[run.length - 1].vLast = true;
      i = j;
    }
  }

  // DK source-citation expansion (docs/citation-expansion-wiring-design.md,
  // stage1_citation_expansion.py's `_segment_heads`): the number of maximal
  // context runs in `lines`, in document order, whose FIRST line carries
  // extractable head material -- the exact rule the pipeline ports
  // (isSourceHeadOnlyText / peelSourceHeadPrefix), applied per run rather
  // than per prose-flow buffer. This is deliberately NOT `greekItems`'
  // 'source-head' item count: `buildProseFlow` only ever peels the head of
  // the FIRST context run in a flushed buffer (a later context run mid-
  // buffer, e.g. Heraclitus B37's "[vgl. B 13]," after the Greek-text run
  // that follows "COLUMELLA VIII 4...", renders as flowing body text, not
  // its own `.frag-source-head`) -- so that count would silently under-
  // count and drop trailing runs. Counting runs directly here keeps it
  // exactly in step with the pipeline's own run count regardless of how
  // the Greek column happens to render them.
  // The Greek line number (`.n`) each context run STARTS on, in document
  // order, computed once over the segment's UNSPLIT `seg.greek` -- so a run
  // that begins before a chapterStarts cut and continues past it is counted
  // exactly once, at its true start line, regardless of where blocks later
  // slice it. Parallel in order to `seg.expandedCitation`'s runs.
  // Same three rules as stage1_citation_expansion._segment_context: a head
  // opens a context run (a dash with nothing citable after it still counts),
  // or a dash opens a later context line with a head after it ("—*48."), or
  // a dash opens a line the spine marks as text ("— —τόν τε Ὅμηρον").
  function runStartLines(lines: RLine[]): number[] {
    const starts: number[] = [];
    let prevRole: string | undefined;
    for (const line of lines) {
      const dash = /^[—–]/.test(line.text.trim());
      const head = isSourceHeadOnlyText(line.text) || !!peelSourceHeadPrefix(line.text);
      if (line.role === 'context' && prevRole !== 'context') {
        if (head || dash) starts.push(line.n);
      } else if (line.role === 'context' ? dash && head : line.role === 'text' && dash) {
        starts.push(line.n);
      }
      prevRole = line.role;
    }
    return starts;
  }

  // Fix round finding 4 (and Sol adversarial-review finding 1): a run's
  // expanded citation renders in the BLOCK where its source head actually
  // sits. `seg.expandedCitation` is document-ordered runs (one per context
  // run, matching stage1's own `_segment_heads` order). Block-LOCAL head
  // counting (the prior approach) miscounts a run that starts before a
  // chapterStarts cut and continues into the next block: the continuation
  // recounts as a fresh head there, over-consuming and shifting every later
  // run's citation onto the wrong block. Instead, each run's start line is
  // resolved ONCE against the unsplit Greek (`runStartLines`), then mapped
  // to whichever block's lines contain that line number as its HEAD piece
  // (not a `cont` tail -- the piece that actually starts at word 0, where
  // every run start sits). No overflow fallback is needed: every run start
  // line exists in exactly one block's lines, by construction.
  function expandedCitationByBlock(seg: Segment, blocks: Block[]): ExpandedCitationEntry[][][] {
    const runs = seg.expandedCitation;
    if (!runs?.length) return blocks.map(() => []);
    const blockOfLine = new Map<number, number>();
    blocks.forEach((block, bi) => {
      for (const l of block.lines) {
        if (!l.cont && !blockOfLine.has(l.n)) blockOfLine.set(l.n, bi);
      }
    });
    const starts = runStartLines(seg.greek);
    const byBlock: ExpandedCitationEntry[][][] = blocks.map(() => []);
    runs.forEach((run, i) => {
      const n = starts[i];
      const bi = n !== undefined && blockOfLine.has(n) ? blockOfLine.get(n)! : blocks.length - 1;
      byBlock[bi]!.push(run);
    });
    return byBlock;
  }

  function splitSegment(seg: Segment): Block[] {
    const greek = seg.greek;
    const text = seg.english?.text ?? '';
    const allTicks = seg.english?.bekker ?? [];
    // Unlabeled paragraph breaks (Stephanus dialogues' turn-internal
    // paragraphs — see stage1_stephanus_english.py) and Discourses' labeled
    // `paras` channel (each entry's `n` is the TLG/Loeb section number the
    // break opens — see EnglishChunk.paras) merge into one offset-sorted
    // list; flowParts renders a bare break for `n: null`, a small muted
    // label for a real `n` — no other work ever has both at once, but
    // nothing stops it structurally.
    // item 85 review (2026-07-28): a whole-column-verbatim column's
    // column_sources English (Gorgias B11/B11a) carries DK's own "(N)"
    // markers inline, exactly as the Greek does (see
    // contextSectionMarkerNumbers above) -- one bare, unlabeled break
    // before each marker not already at the very start of the text turns
    // every numbered section into its own paragraph, aligned index-for-
    // index with the Greek's own marker-split paragraphs. The number
    // itself stays visible inline (never stripped, unlike the Greek's own
    // relabelled marker) so no label is added here -- a bare break, same
    // shape as the Stephanus/turn-flow breaks above.
    // item 85 addendum (Melissus B7/B8, 2026-07-28): `sectionParagraphSplit`
    // carries the same inline "(N)" convention without a per-column
    // `english.credit` override -- see contextSectionMarkerNumbers above.
    // Fix round (Sol adversarial review on commit 7287b10, finding 1): every
    // "(N)" here used to split, unvalidated — a stray mid-text citation like
    // "(12)" (not a declared section number, or out of ascending order) split
    // a paragraph the Greek side never did. `scanSectionMarkers` applies the
    // SAME membership/ascending/boundary discipline as the Greek context-scan
    // (prose-flow.ts's `splitContextMarkerGroups`), fed the same declared
    // marker set `contextSectionMarkerNumbers` already builds from this text.
    const wholeColumnSectionBreaks: { off: number; n: number | null }[] = [];
    if ((seg.wholeColumnVerbatim && seg.english?.credit) || seg.sectionParagraphSplit) {
      for (const marker of scanSectionMarkers(text, contextSectionMarkerNumbers(seg))) {
        if (marker.index) wholeColumnSectionBreaks.push({ off: marker.index, n: null });
      }
    }
    const allParas: { off: number; n: number | null }[] = [
      ...(seg.english?.markers ?? [])
        .filter(m => m.kind === 'paragraph')
        .map(m => ({ off: m.offset, n: null as number | null })),
      ...(seg.english?.paras ?? []).map(p => ({ off: p.o, n: p.n as number | null })),
      ...wholeColumnSectionBreaks,
    ];
    const allVerse = seg.english?.verse ?? [];
    const allFrames = seg.english?.frames ?? [];
    // The primary English slice [a, b) as flowing prose: its Bekker ticks
    // (rebased into the slice) are floated into the margin at their EXACT char
    // offsets — no sentence-snapping, no row break — so a mid-sentence Bekker
    // number renders where it actually falls instead of jumping to the next
    // sentence start (which the older snapped-row gutter did). The secondary
    // secondary slot uses the same flow model.
    const flowFor = (a: number, b: number): FlowPart[] => {
      const slice = text.slice(a, b);
      const ticks = allTicks
        .filter(t => t.offset >= a && t.offset < b)
        .map(t => ({ n: t.n, real: t.real, off: t.offset - a }))
        .sort((x, y) => x.off - y.off);
      const paras = allParas
        .filter(p => p.off > a && p.off < b)
        .map(p => ({ off: p.off - a, n: p.n }));
      // A verse range must lie ENTIRELY within this slice — book-section
      // works (the only source of `verse` today) never split a segment into
      // more than one block, so this is always true for them in practice;
      // a range straddling a block-splitting boundary (a future scheme) is
      // dropped rather than rendered as a mis-cut fragment.
      const verse = allVerse
        .filter(v => v.start >= a && v.end <= b)
        .map(v => ({ start: v.start - a, end: v.end - a, breaks: v.breaks.map(x => x - a) }));
      // A frame must lie ENTIRELY within this slice — Freeman fragment
      // works never split a segment into more than one block (dk has no
      // chapters), so this is always true in practice; a frame straddling
      // a future block-splitting boundary is dropped rather than rendered
      // mis-cut, same posture as `verse` above.
      const frames = allFrames
        .filter(([s, e]) => s >= a && e <= b)
        .map(([s, e]) => ({ start: s - a, end: e - a }));
      return flowParts(slice, ticks, paras, verse, frames);
    };
    // Sidenote numbers ([[sN]] markers) falling in the primary English slice
    // [a, b) — the reader floats these into the right rail (busse works).
    const sidesIn = (a: number, b: number): number[] =>
      [...text.slice(a, b).matchAll(/\[\[s(\d+)\]\]/g)].map(m => Number(m[1]));
    // Diagram numbers ([[figN]] markers) in the slice — rendered inline as figures.
    const figsIn = (a: number, b: number): number[] =>
      [...text.slice(a, b).matchAll(/\[\[fig(\d+)\]\]/g)].map(m => Number(m[1]));
    // Overlay slices for each secondary translation, paired to blocks: the
    // continuation slice (a chapter begun in an earlier column) and one per
    // chapter that starts here. Each lays out as flowing prose with its Bekker
    // numbers floated into the margin at exact offsets. Keyed by translation id
    // so any number of overlays render (the 'third'/footnote-bearing one also
    // carries diagram tables).
    const secPieces = secondaries.map((t) => ({ t, pieces: piecesFor(seg, t) }));
    const flowOf = (p: OverlayPiece | undefined): FlowPart[] =>
      (!p || !p.text) ? [] : flowParts(p.text, (p.bekker ?? []).map(t => ({ n: t.n, real: t.real, off: t.offset })));
    const pieceCont = (pieces: OverlayPiece[]) => pieces.find(p => p.cont) ?? pieces[0];
    const pieceFor = (pieces: OverlayPiece[], chapter: string | null) =>
      pieces.find(p => !p.cont && p.chapter === chapter);
    // {transId: flow} + {transId: tables} for a block, picking each overlay's
    // continuation slice or the slice for `chapter` (null → continuation).
    const overlaysFor = (chapter: string | null): { oflows: Record<string, FlowPart[]>; otables: Record<string, { n: number; rows: string[][] }[]> } => {
      const oflows: Record<string, FlowPart[]> = {};
      const otables: Record<string, { n: number; rows: string[][] }[]> = {};
      for (const { t, pieces } of secPieces) {
        const p = chapter === null ? pieceCont(pieces) : pieceFor(pieces, chapter);
        oflows[t.id] = flowOf(p);
        if (p?.tables?.length) otables[t.id] = p.tables;
      }
      return { oflows, otables };
    };

    const starts = (seg.chapterStarts ?? []).slice()
      .sort((a, b) => a.beforeLine - b.beforeLine || (a.wordIndex || 0) - (b.wordIndex || 0));
    // Book-section works never have chapterStarts (chapter = segment, 1:1),
    // so this is the ONLY branch splitGreekSections needs to run from — see
    // its doc comment.
    if (!starts.length) return [{ chapter: null, bekker: '', lines: splitGreekSections(greek), flow: flowFor(0, text.length), sidenotes: sidesIn(0, text.length), figs: figsIn(0, text.length), ...overlaysFor(null) }];

    const lineIdx = (beforeLine: number) => {
      const i = greek.findIndex(l => l.n >= beforeLine);
      return i === -1 ? greek.length : i;
    };
    // Each chapter boundary is a cut at (line index, word index within the line).
    const bounds = starts.map(s => ({
      chapter: s.chapter, bekker: s.bekker, engOffset: s.engOffset,
      idx: lineIdx(s.beforeLine), word: s.wordIndex || 0,
    }));

    // The Greek lines spanning a block from cut (idxA,wA) to cut (idxB,wB),
    // splitting the boundary lines mid-line where wA/wB > 0.
    const linesFor = (idxA: number, wA: number, idxB: number, wB: number): RLine[] => {
      if (idxA >= greek.length) return [];
      if (idxA === idxB) {                       // block lies within one line
        const sl = lineSlice(greek[idxA], wA, wB);
        return sl.tokens.length || sl.text.trim() ? [sl] : [];
      }
      const res: RLine[] = [];
      for (let i = idxA; i < idxB && i < greek.length; i++) {
        res.push(i === idxA && wA > 0 ? lineSlice(greek[i], wA, greek[i].tokens.length) : greek[i]);
      }
      if (wB > 0 && idxB < greek.length) res.push(lineSlice(greek[idxB], 0, wB));
      return res;
    };

    const blocks: Block[] = [];
    const first = bounds[0];
    // Lines/English before the first chapter start continue the previous chapter.
    if (first.idx > 0 || first.word > 0 || starts[0].engOffset > 0) {
      blocks.push({
        chapter: null, bekker: '',
        lines: linesFor(0, 0, first.idx, first.word),
        flow: flowFor(0, starts[0].engOffset), sidenotes: sidesIn(0, starts[0].engOffset), figs: figsIn(0, starts[0].engOffset), ...overlaysFor(null),
      });
    }
    for (let i = 0; i < bounds.length; i++) {
      const b = bounds[i];
      const next = bounds[i + 1];
      const engTo = next ? next.engOffset : text.length;
      blocks.push({
        chapter: b.chapter, bekker: b.bekker,
        lines: linesFor(b.idx, b.word, next ? next.idx : greek.length, next ? next.word : 0),
        flow: flowFor(b.engOffset, engTo), sidenotes: sidesIn(b.engOffset, engTo), figs: figsIn(b.engOffset, engTo), ...overlaysFor(b.chapter),
      });
    }
    return blocks;
  }

  // ── Row-aligned rendering (item 85, John's live-review layout ruling) ────
  // The two DK "(N)" section-marker trigger paths (wholeColumnVerbatim+credit
  // -- Gorgias B11/B11a -- and sectionParagraphSplit -- Melissus B7/B8) used
  // to flow the Greek and English columns independently: each column's own
  // paragraphs stacked with no relation to where the OTHER column's matching
  // section happened to land. John's ruling: the first line of each numbered
  // section's English must sit level with the first line of that section's
  // Greek (a shorter side's own trailing gap at the end is fine; never
  // faked into matching height). `sectionRowSplit` gates this alternate
  // rendering at the render site; every other segment — and these same two
  // segments' own English in COMPARE mode, out of scope here (a 3rd column
  // per row is a follow-up, not asked for) — renders exactly as before.
  function sectionRowSplit(seg: Segment): boolean {
    return !!((seg.wholeColumnVerbatim && seg.english?.credit) || seg.sectionParagraphSplit);
  }

  type SectionRow = {
    marker?: string;
    items: GreekItem[];
    flow: FlowPart[];
    oflows: Record<string, FlowPart[]>;
  };

  // Splits a segment's `greekItems()` output into row groups: everything up
  // to (not including) the first marker-carrying flow is the HEADING row
  // (row 0, never marker-labelled); each subsequent marker-carrying flow
  // opens a new row and absorbs every item after it up to the next marker.
  // Mirrors prose-flow.ts's own splitContextMarkerGroups grouping exactly,
  // since it consumes that function's own output (via buildProseFlow).
  function groupGreekRows(items: GreekItem[]): { marker?: string; items: GreekItem[] }[] {
    const rows: { marker?: string; items: GreekItem[] }[] = [{ items: [] }];
    for (const item of items) {
      if (item.kind === 'flow' && item.prose.sectionMarker !== undefined) {
        rows.push({ marker: item.prose.sectionMarker, items: [item] });
      } else {
        rows[rows.length - 1]!.items.push(item);
      }
    }
    return rows;
  }

  // Splits `text` into `rowCount` ranges at its own accepted "(N)" markers
  // (scanSectionMarkers — the same membership/ascending/boundary discipline
  // the Greek side, and splitSegment's own wholeColumnSectionBreaks, use).
  // Returns [] when the text's marker set doesn't fully cover every row
  // (an incomplete or absent split) — the caller's signal to fall back
  // rather than fabricate alignment for that text. rowCount === 1 (no
  // marker-carrying row at all) always yields the whole text as one range,
  // regardless of markerNumbers, matching the pre-split single-flow case.
  function rowRanges(
    text: string,
    markerNumbers: Set<number> | undefined,
    rowCount: number,
  ): { start: number; end: number }[] {
    if (rowCount <= 1) return [{ start: 0, end: text.length }];
    if (!markerNumbers?.size) return [];
    const marks = scanSectionMarkers(text, markerNumbers);
    if (marks.length !== rowCount - 1) return [];
    const bounds = [0, ...marks.map((m) => m.index), text.length];
    const ranges: { start: number; end: number }[] = [];
    for (let i = 0; i < bounds.length - 1; i++) ranges.push({ start: bounds[i]!, end: bounds[i + 1]! });
    return ranges;
  }

  // Row-sliced FlowParts for one text (primary or overlay), reusing
  // flowParts exactly as flowFor (above) does — ticks rebased into the
  // slice, no paragraph breaks passed (the row boundary IS the paragraph
  // break; nothing further to split within a row).
  function flowSlice(
    text: string,
    range: { start: number; end: number } | undefined,
    ticks: { n: number; real: boolean; offset: number }[],
  ): FlowPart[] {
    if (!range) return [];
    const slice = text.slice(range.start, range.end);
    const localTicks = ticks
      .filter((t) => t.offset >= range.start && t.offset < range.end)
      .map((t) => ({ n: t.n, real: t.real, off: t.offset - range.start }));
    return flowParts(slice, localTicks, []);
  }

  // Builds the row-aligned data for a sectionRowSplit segment's sole block
  // (these DK fragment/testimonia columns never carry chapterStarts, so
  // splitSegment always returns exactly one block for them — see its own
  // doc comment). Row 0 is the heading (Greek title/frame + English
  // lead-in, neither carrying a marker); rows 1..N pair each ascending "(N)"
  // section. The primary English (seg.english.text) is the very text
  // `contextSectionMarkerNumbers` reads its marker set from, so it always
  // fully splits. An overlay translation (Reader's `secondaries`, e.g.
  // Gorgias B11's freeman-summary) is independently checked: real data
  // shows Freeman's own summary overlay carries the identical ascending
  // "(N)" run (attested by stage1_freeman_english.py's own section-count
  // cross-check), so it splits the same way; an overlay whose own text
  // doesn't fully cover the declared markers keeps its whole text in row 0
  // and renders empty in every other row, rather than a fabricated
  // per-row alignment.
  function sectionRowsFor(seg: Segment, block: Block): SectionRow[] {
    const markerNumbers = contextSectionMarkerNumbers(seg);
    const items = greekItems(block.lines, seg.column, markerNumbers, seg.sectionParagraphSplit, seg.wholeColumnVerbatim ? undefined : seg.witnesses);
    const rows = groupGreekRows(items);

    const text = seg.english?.text ?? '';
    const ticks = seg.english?.bekker ?? [];
    const primaryRanges = rowRanges(text, markerNumbers, rows.length);
    const primaryFlows = rows.map((_, i) => flowSlice(text, primaryRanges[i], ticks));

    const oflowsByRow: Record<string, FlowPart[]>[] = rows.map(() => ({}));
    for (const t of secondaries) {
      const pieces = piecesFor(seg, t);
      const piece = pieces.find((p) => !p.cont) ?? pieces[0];
      const oText = piece?.text ?? '';
      if (!oText) continue;
      const oTicks = piece?.bekker ?? [];
      const ranges = rowRanges(oText, markerNumbers, rows.length);
      if (ranges.length === rows.length) {
        rows.forEach((_, i) => { oflowsByRow[i]![t.id] = flowSlice(oText, ranges[i], oTicks); });
      } else {
        oflowsByRow[0]![t.id] = flowSlice(oText, { start: 0, end: oText.length }, oTicks);
        for (let i = 1; i < rows.length; i++) oflowsByRow[i]![t.id] = [];
      }
    }

    return rows.map((r, i) => ({
      marker: r.marker,
      items: r.items,
      flow: primaryFlows[i]!,
      oflows: oflowsByRow[i]!,
    }));
  }

  // Active popup state
  let popup: { token: Token; anchor: { x: number; y: number } } | null = null;
  // Active footnote popup (footnote-bearing translations' `[^label]`
  // markers). Opens on hover, with a short close-delay so the cursor can
  // travel from the marker into the popup without it vanishing; click/Enter
  // also open it (touch + keyboard). §B4.3: carries `transId` (from the
  // marker's `data-fn-trans`) alongside the label, so FootnotePopup knows
  // WHICH translation's footnote map to resolve `n` against.
  let footnote: { n: string; transId: string; anchor: { x: number; y: number } } | null = null;
  // A click PINS the popup open (it stays until you dismiss it); hover opens it
  // transiently with a short close delay. Pinning makes click-to-read reliable.
  let fnPinned = false;
  let fnCloseTimer: ReturnType<typeof setTimeout> | null = null;
  function cancelFnClose() {
    if (fnCloseTimer) { clearTimeout(fnCloseTimer); fnCloseTimer = null; }
  }
  function scheduleFnClose() {
    if (fnPinned) return;            // a clicked (pinned) note ignores hover-out
    cancelFnClose();
    fnCloseTimer = setTimeout(() => { footnote = null; fnCloseTimer = null; }, 180);
  }
  function showFootnote(marker: Element, pin = false) {
    cancelFnClose();
    if (pin) fnPinned = true;
    const n = marker.getAttribute('data-fn') ?? '';
    const transId = marker.getAttribute('data-fn-trans') ?? '';
    if (footnote?.n === n && footnote?.transId === transId) return;
    const r = marker.getBoundingClientRect();
    footnote = { n, transId, anchor: { x: r.left, y: r.bottom } };
  }
  function onFootnoteOver(e: MouseEvent) {
    const marker = (e.target as HTMLElement | null)?.closest?.('.fn-marker');
    if (marker) showFootnote(marker);
  }
  function onFootnoteOut(e: MouseEvent) {
    if ((e.target as HTMLElement | null)?.closest?.('.fn-marker')) scheduleFnClose();
  }
  function onFootnoteFocus(e: FocusEvent) {
    const marker = (e.target as HTMLElement | null)?.closest?.('.fn-marker');
    if (marker) showFootnote(marker);
  }
  function onFootnoteBlur(e: FocusEvent) {
    if ((e.target as HTMLElement | null)?.closest?.('.fn-marker')) scheduleFnClose();
  }
  function onFootnoteClick(e: MouseEvent | KeyboardEvent) {
    const marker = (e.target as HTMLElement | null)?.closest?.('.fn-marker');
    if (!marker) return;
    if (e instanceof KeyboardEvent && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    showFootnote(marker, true);
  }
  function closeFootnote() { cancelFnClose(); fnPinned = false; footnote = null; }
  // Click anywhere outside the marker/popup dismisses a pinned note; same
  // for the Bekker-numbers info popover.
  function onDocPointerDown(e: MouseEvent) {
    const t = e.target as HTMLElement | null;
    if (bekkerInfoOpen && !t?.closest?.('.bekker-info')) bekkerInfoOpen = false;
    if (!fnPinned) return;
    if (t?.closest?.('.fn-marker') || t?.closest?.('.footnote-popup')) return;
    closeFootnote();
  }

  onMount(async () => {
    reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Remember which book of this work was last open, for the work switcher —
    // and stamp the work's recency so hosts can offer "continue reading".
    try { localStorage.setItem(`reader-book-${work}`, String(bookNum)); } catch {}
    touchRecent(work);

    // Restore font-size / line-height prefs.
    const savedFs = (() => { try { return localStorage.getItem(FS_KEY); } catch { return null; } })();
    if (savedFs) { const v = parseFloat(savedFs); if (!isNaN(v)) fsScale = v; }
    const savedLh = (() => { try { return localStorage.getItem(LH_KEY); } catch { return null; } })();
    if (savedLh) { const v = parseFloat(savedLh); if (!isNaN(v)) lhScale = v; }
    const savedColw = (() => { try { return localStorage.getItem(COLW_KEY); } catch { return null; } })();
    if (savedColw) { const v = parseFloat(savedColw); if (!isNaN(v)) colScale = v; }
    const savedCite = (() => { try { return localStorage.getItem(CITE_KEY); } catch { return null; } })();
    if (savedCite !== null) citeCopy = savedCite === 'true';
    const savedSpk = (() => { try { return localStorage.getItem(SPK_KEY); } catch { return null; } })();
    if (savedSpk !== null) spkColor = savedSpk === 'true';

    // Settings sidebar events (dispatched by ReaderShell.astro and Escape handler).
    _onToggleSettings = () => { settingsOpen ? closeSettings() : openSettings(); };
    _onCloseSettings  = () => { if (settingsOpen) closeSettings(); };
    window.addEventListener('toggle-settings', _onToggleSettings);
    window.addEventListener('close-settings',  _onCloseSettings);
    const params = new URLSearchParams(window.location.search);
    hlGrkFolds = (params.get('hlg') ?? '').trim().split(/\s+/).filter(Boolean)
      .map(t => greekFold(t.replace(/\*/g, ''))).filter(Boolean);
    hlEngTerms = (params.get('hle') ?? '').trim().split(/\s+/).filter(Boolean);
    const loc = params.get('loc');
    let locCol = '';
    let locLine: number | null = null;
    if (loc) {
      // Parse through the work's citation scheme, so a column-only value ("17a")
      // yields line === null and targets the segment — never the malformed
      // "L17a-undefined" the old unconditional split-on-':' produced.
      const parsed = parseLocation(work, loc);
      if (parsed) {
        locCol = parsed.column;
        locLine = parsed.line;
        targetId = locLine != null ? `L${locCol}-${locLine}` : `col-${locCol}`;
      }
    }
    // Restore saved view, but a jump-in (loc/highlight) forces bilingual so the
    // target Greek line is on screen.
    if (loc || hlGrkFolds.length) {
      view = 'both';
    } else {
      const saved = (() => { try { return localStorage.getItem('reader-view'); } catch { return null; } })();
      if (saved === 'greek' || saved === 'english' || saved === 'both') view = saved;
      // No saved choice: a phone defaults to English only (the bilingual columns
      // are cramped on a narrow screen); desktop stays bilingual. The toggle —
      // and any saved choice — overrides this on either.
      else if (window.matchMedia('(max-width: 680px)').matches) view = 'english';
    }
    const validTrans = new Set([...translations.map(t => t.id), ...(canCompare ? ['compare'] : [])]);
    const savedTrans = (() => { try { return localStorage.getItem(TRANS_KEY); } catch { return null; } })();
    if (savedTrans && validTrans.has(savedTrans)) trans = savedTrans;
    // A restored single choice is also the one "leave compare" returns to.
    if (trans !== 'compare') lastSingle = trans;
    // Restore the chosen compare pair (set in the settings sidebar).
    const transIds = new Set(translations.map(t => t.id));
    const savedL = (() => { try { return localStorage.getItem(CMPL_KEY); } catch { return null; } })();
    const savedR = (() => { try { return localStorage.getItem(CMPR_KEY); } catch { return null; } })();
    if (savedL && transIds.has(savedL)) compareLeft = savedL;
    if (savedR && transIds.has(savedR)) compareRight = savedR;
    // A stale/duplicate persisted pair (or a one-translation default colliding)
    // must not yield two identical columns.
    if (compareLeft === compareRight) compareRight = otherTrans(compareLeft);
    // The home index links can preselect a view/translation via query params.
    const qView = params.get('view');
    if (qView === 'greek' || qView === 'both' || qView === 'english') view = qView;
    const qTrans = params.get('trans');
    if (qTrans && validTrans.has(qTrans)) { trans = qTrans; if (view === 'greek') view = 'both'; }
    try {
      // Already seeded from the build-time prop in the normal (SSR) path; only
      // fetch when the reader was mounted without it.
      if (!bookData) {
        const data = await fetchBook(work, bookNum);
        segments = data.segments;
        turnFlow = data.turnFlow ?? null;
        displayOrder = data.displayOrder ?? null;
      }
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
      // After Svelte renders, scroll to the jumped-to line (loc), a Bekker
      // citation in the hash, or a plain element-id hash.
      const hash = window.location.hash.slice(1);
      setTimeout(() => {
        if (targetId) {
          let el = document.getElementById(targetId);
          // Snap to the nearest existing line in the column if the exact
          // citation line isn't a Greek line break (e.g. mid-line citations).
          // Queried by line-id prefix, not by segment nesting, so it works in
          // both the section-segment layout and the turn flow (where a
          // section's lines aren't nested under its col-{token} tick).
          if (!el && locCol && locLine != null) {
            let best: Element | null = null;
            let bestDist = Infinity;
            document.querySelectorAll(`.greek-line[id^="L${CSS.escape(locCol)}-"]`).forEach((node) => {
              const m = node.id.match(/-(\d+)$/);
              if (!m) return;
              const d = Math.abs(Number(m[1]) - locLine);
              if (d < bestDist) { bestDist = d; best = node; }
            });
            if (best) { el = best as HTMLElement; targetId = (best as HTMLElement).id; }
          }
          if (el) { suppressArmUntil = Date.now() + 1500; el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        } else if (hash) {
          // Scheme-aware, not Bekker-only: a line-bearing hash only ever
          // resolves for the WORK's own citation scheme (parseLocation),
          // so a verse dk work's dot-joined ref ("#B8.34") round-trips the
          // same way a Bekker ref ("#1097a15") always has — parseBekker
          // (bekker-grammar-only) would silently fail every other scheme's
          // line-bearing hash and fall through to the bare-id branch below.
          const parsedHash = parseLocation(work, hash);
          const ref = parsedHash && parsedHash.line != null ? (parsedHash as { column: string; line: number }) : null;
          if (ref) {
            scrollToCitation(ref.column, ref.line);
            // formatCite, not raw concatenation: a dk verse ref is dot-joined
            // ("B8.34"), never concatenated ("B834") — matches what
            // updateHash's own citeOf will compute for this same line, so
            // the change-guard doesn't misfire on a scheme whose formatted
            // ref isn't plain concatenation.
            lastCite = formatCite(work, ref.column, ref.line);
            // Tint the cited line so a shared link makes the passage obvious.
            targetId = `L${ref.column}-${ref.line}`;
          } else {
            // Column-level citations (the scroll-spy writes bare "#1107a" when
            // the Greek column is hidden) target the segment element col-<col>.
            // Instant, like scrollToCitation: a smooth animation started during
            // hydration gets canceled by layout churn and strands the reader at
            // the top.
            let el = document.getElementById(hash) ?? document.getElementById(`col-${hash}`)
              ?? findColElementCaseInsensitive(hash) ?? findColElementCaseInsensitive(`col-${hash}`);
            // A hidden target (the turn flow's Greek gutter tick in
            // English-only view) falls back to the row-level English tick.
            if (el && (el as HTMLElement).offsetParent === null) {
              el = (document.querySelector(`[data-etick="${CSS.escape(hash)}"]`) as HTMLElement) ?? el;
            }
            if (el) {
              suppressArmUntil = Date.now() + 1500;
              el.scrollIntoView({ behavior: 'auto', block: 'start' });
            }
          }
        }
        // Begin live URL tracking once the reader actually scrolls (programmatic
        // jumps above are suppressed), so an opened #citation isn't overwritten.
        window.addEventListener('scroll', onScrollArm, { passive: true });
        window.addEventListener('scroll', onCtxScroll, { passive: true });
        window.addEventListener('resize', onResize);
        document.addEventListener('mouseup', checkCopyBtn);
        document.addEventListener('selectionchange', onSelectionChange);
        updateChapterContext();
      }, 0);
    }
  });

  // Opening/closing the word sidebar changes the reader body's width (it gains
  // padding-right to clear the panel), which reflows the text and shifts every
  // line vertically — so the passage the reader was looking at jumps. Pin a
  // given element to its current screen position by compensating scroll on each
  // frame for the duration of the width transition. MUST be called BEFORE the
  // `popup` state change so startTop is captured in the pre-reflow layout.
  function pinAcrossReflow(el: HTMLElement | null) {
    if (!el || typeof window === 'undefined') return;
    const startTop = el.getBoundingClientRect().top;
    suppressArmUntil = Date.now() + 500;   // don't let our scrolls arm the spy
    const until = Date.now() + 360;        // padding-right transition is 0.22s
    const step = () => {
      const delta = el.getBoundingClientRect().top - startTop;
      if (Math.abs(delta) >= 0.5) window.scrollBy(0, delta);
      if (Date.now() < until) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // The line currently at the top of the reading area — the fallback anchor to
  // keep fixed when the sidebar closes after the clicked word has scrolled away.
  function topAnchor(): HTMLElement | null {
    const ctrlBottom = document.querySelector('.reader-controls')?.getBoundingClientRect().bottom ?? 0;
    const inset = ctrlBottom + 8;
    const greekVisible = view === 'greek' || view === 'both';
    const els = document.querySelectorAll<HTMLElement>(
      greekVisible ? '.greek-line[id]' : '.segment[id], .turn-flow .seg-row');
    let best: HTMLElement | null = null, bestDiff = Infinity;
    for (const el of els) {
      const diff = Math.abs(el.getBoundingClientRect().top - inset);
      if (diff < bestDiff) { bestDiff = diff; best = el; }
    }
    return best;
  }

  function inViewport(el: HTMLElement): boolean {
    const r = el.getBoundingClientRect();
    return r.bottom > 0 && r.top < window.innerHeight;
  }

  // The word whose click opened the sidebar — pinned again on close so the
  // passage lands back exactly where it opened (symmetric), unless the reader
  // scrolled it out of view, in which case we keep the current top line fixed.
  let pinnedTok: HTMLElement | null = null;

  function handleTokenClick(e: MouseEvent, token: Token | null) {
    if (!token) return;
    e.stopPropagation();
    const el = e.currentTarget as HTMLElement;
    const rect = el.getBoundingClientRect();
    // Only the first open reflows the body (adds .word-open); switching words
    // while the sidebar is already open changes nothing about the layout.
    if (!popup) { pinnedTok = el; pinAcrossReflow(el); }
    popup = { token, anchor: { x: rect.left, y: rect.bottom } };
  }

  function closePopup() {
    if (popup) pinAcrossReflow(pinnedTok && inViewport(pinnedTok) ? pinnedTok : topAnchor());
    popup = null;
    pinnedTok = null;
  }

  // ── Keyboard access to Greek tokens ──────────────────────────────────────
  // Analysable tokens are a huge set (thousands per book), so putting every one
  // in the tab order would be hostile to keyboard and screen-reader users.
  // Instead we use a roving tabindex: exactly one token is tabbable; arrow keys
  // move focus token-to-token; Enter/Space opens its analysis. The reader body
  // is the scope so navigation can't wander into chrome.
  let readerBodyEl: HTMLElement | undefined;
  function ensureRovingTab() {
    if (!readerBodyEl) return;
    if (readerBodyEl.querySelector('.tok[tabindex="0"]')) return;
    const first = readerBodyEl.querySelector<HTMLElement>('.tok');
    first?.setAttribute('tabindex', '0');
  }
  afterUpdate(ensureRovingTab);

  function onTokenKey(e: KeyboardEvent, token: Token) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();
      handleTokenClick(e as unknown as MouseEvent, token);
      return;
    }
    const step: Record<string, number | 'first' | 'last'> = {
      ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1, Home: 'first', End: 'last',
    };
    if (!(e.key in step)) return;
    e.preventDefault();
    const cur = e.currentTarget as HTMLElement;
    const toks = Array.from(readerBodyEl?.querySelectorAll<HTMLElement>('.tok') ?? []);
    const i = toks.indexOf(cur);
    if (i < 0) return;
    const move = step[e.key];
    const j = move === 'first' ? 0
      : move === 'last' ? toks.length - 1
      : Math.min(toks.length - 1, Math.max(0, i + move));
    if (j === i) return;
    cur.setAttribute('tabindex', '-1');
    toks[j].setAttribute('tabindex', '0');
    toks[j].focus();
  }

  // Show line number only for multiples of 5 (and line 1). Suppressed entirely
  // for non-Bekker works whose synthetic line numbers aren't meaningful.
  function showLineNum(n: number): string {
    if (hideLineNums) return '';
    if (n === 1 || n % 5 === 0) return String(n);
    return '';
  }

  // item 23 unification: a book-section chapter-flow run's DOM anchor id --
  // byte-identical formula to the pre-flow per-line block rendering below
  // (`item.line.cont ? L{col}-{n}-c{paraN} : L{col}-{n}`), so #-target
  // highlighting (matched per run, directly against `rid`) and scroll-spy
  // (column granularity, via the paragraph's own first-run id) keep
  // resolving the exact same ids; only the wrapper markup (inline span vs
  // block div) changed. Copy-citation does NOT resolve per run: it walks up
  // to the nearest `.greek-line`-classed ancestor (Reader's
  // `nearestGreekLine`), which for every run past the first is the whole
  // flow `<p>`, not the run's own span -- so a selection anywhere in the
  // paragraph cites the paragraph's own first-run id (see
  // `citeForGreekLine`'s doc comment). That is harmless for book-section:
  // the scheme's own `formatCite` always drops the line axis
  // (hasUserFacingLines: false), so every run in one segment cites the SAME
  // column regardless of which run resolved it (fix round, finding 5 —
  // Sol review; see reader-prose-flow.test.ts's book-section describe
  // block for the pinned selection-endpoint test). book-section lines
  // never carry dk's role='context', so the old rendering's role guard is
  // omitted here (never reachable for this scheme).
  function flowRunId(line: RLine, column: string): string {
    return line.cont ? `L${column}-${line.n}-c${line.paraN ?? ''}` : `L${column}-${line.n}`;
  }

  // Fix round, finding 3 (Sol review): two Schenkl-subsection gutter
  // markers can land on the SAME rendered visual line when the run between
  // them is short (real case: Discourses 2.9.1, a 38-character run) --
  // both would sit at the identical absolute vertical position (the
  // .greek-para-n-flow "no row break" technique, mirroring .bk-num) and
  // visually overlap. Real wrapped-line length depends on viewport/font-
  // size/column width, which is unknowable at render time, so the
  // mitigation is a deterministic character-count proxy, never a DOM
  // measurement: a marker whose preceding run (the text since the PREVIOUS
  // marker fired in this paragraph) is shorter than PARA_N_COLLISION_CHARS
  // falls back to the plain inline ".para-n" treatment (muted, sitting in
  // the running text -- the same class the flat 'section' scheme's
  // .greek-para-n already reuses) instead of the absolute-positioned
  // gutter marker. A paragraph's FIRST marker has nothing before it to
  // collide with, so it is always a gutter marker. The threshold is
  // deliberately conservative (roughly half a comfortable print line) --
  // trading occasional unnecessary inline fallbacks for certainty against
  // overlap. Pure function of run text lengths, so it is exact and unit-
  // testable without any DOM measurement.
  const PARA_N_COLLISION_CHARS = 60;
  function paraMarkerIsGutter(runs: readonly { paraN?: number; text: string }[]): boolean[] {
    const gutter: boolean[] = [];
    let sincePrev = 0;
    let seenMarker = false;
    for (const r of runs) {
      if (r.paraN != null) {
        gutter.push(!seenMarker || sincePrev >= PARA_N_COLLISION_CHARS);
        sincePrev = 0;
        seenMarker = true;
      } else {
        gutter.push(false); // unused: no marker fires on this run
      }
      sincePrev += r.text.length;
    }
    return gutter;
  }

  // verse-line's own gutter numbering: hasUserFacingLines is false for this
  // scheme (the line IS the column — citation.ts's module doc), so
  // showLineNum above (keyed off item.line.n, always 1 for a one-line-per-
  // segment scheme) never applies. Parses the absolute verse-line number out
  // of the segment's own column instead (book.line, e.g. "1.245"; citation.ts's
  // VERSE_LINE_COLUMN_RE) and shows it every 5th line (standard verse-edition
  // convention) plus line 1, the very first rendered segment, and the line
  // right after an editorial lacuna gap — the points where a reader
  // re-orients without one.
  // Fix round, finding 4 (Sol review): computed once as a forward pass
  // (not per-call) so "don't re-show the last number already shown" has
  // real running state to check against, instead of re-deriving it per
  // index. Two fixes over the old per-call version:
  // (a) only a PURE-INTEGER column ("1.860") is eligible at all — a
  //     suffixed variant ("1.860a") never carries a gutter number (the old
  //     unanchored `/\.(\d+)/` read "860" out of "860a" too, duplicating
  //     the real line's own number).
  // (b) a post-lacuna forced number is suppressed if it would repeat the
  //     number the previous rendered gutter already showed.
  $: verseGutterNums = (() => {
    const out: string[] = [];
    let lastShown: number | null = null;
    enrichedSegments.forEach(({ seg }, i) => {
      const m = /\.(\d+)$/.exec(seg.column);
      if (!m) { out.push(''); return; }
      const n = Number(m[1]);
      const prevLacuna = i > 0 && enrichedSegments[i - 1]!.seg.greek[0]?.role === 'lacuna';
      const eligible = i === 0 || n === 1 || n % 5 === 0 || prevLacuna;
      if (eligible && n !== lastShown) {
        out.push(String(n));
        lastShown = n;
      } else {
        out.push('');
      }
    });
    return out;
  })();

  function verseGutterNum(si: number): string {
    return verseGutterNums[si] ?? '';
  }

  // ── Copy-with-citation helpers ────────────────────────────────────────────
  function nearestGreekLine(node: Node): HTMLElement | null {
    let n: Node | null = node;
    while (n && n !== document.body) {
      if (n instanceof HTMLElement && n.classList.contains('greek-line')) return n;
      n = n.parentNode;
    }
    return null;
  }
  // A Greek-line id → its {column, line}: L1094a-3 / L1094a-3-c → column
  // "1094a", line 3; L17a-5 → column "17a", line 5 (stephanus — a lineless
  // scheme, so greekCiteForRange's formatCopyCitationRange call drops it).
  // DK prose-flow anchors are column-only (`LB4`) — line is null.
  // A section-split continuation L{col}-{n}-c{k} resolves to {column, line:
  // n} too (module helper's own doc comment: book-section's formatCitation
  // drops `line`, so this is byte-identical to its chapter's own citation).
  function idToCite(id: string): { column: string; line?: number | null } | null {
    return greekLineIdToCite(id);
  }

  // Fix round, finding 2 (Sol review): a marker-split flow paragraph after
  // the first carries no `id` (only the column's first flow anchors
  // `L{column}` — see greekItems' `firstFlow` bookkeeping, which never
  // gives the DOM two elements with the same id). A `.greek-line` with no
  // id still sits inside its `.greek-col`'s `data-column` (see that div's
  // own comment), so a selection landing there resolves to the SAME
  // column-only citation the first paragraph's own id would give — never a
  // dropped citation. A `.greek-line` that does carry an id (every other
  // shape: numbered verse lines, a column's sole/first flow) is untouched,
  // so single-flow columns stay byte-identical to before this fix.
  function citeForGreekLine(el: HTMLElement): { column: string; line?: number | null } | null {
    if (el.id) return idToCite(el.id);
    const col = el.closest<HTMLElement>('[data-column]');
    return col?.dataset.column ? { column: col.dataset.column, line: null } : null;
  }

  // The copy-with-citation string for a Greek-text selection, routed
  // through citation.ts's formatCopyCitationRange so the prefix is the
  // work's scholarly `citation.copyAbbr` (falling back to `abbr`) — see
  // that function's own doc for why this used to read `workMeta.abbr`
  // directly instead (every dk work's copied citation carried its short UI
  // abbreviation rather than its DK-chapter one).
  function greekCiteForRange(range: Range): string | null {
    const startLine = nearestGreekLine(range.startContainer);
    const endLine   = nearestGreekLine(range.endContainer);
    if (!startLine && !endLine) return null;
    const s = startLine ? citeForGreekLine(startLine) : null;
    const f = endLine   ? citeForGreekLine(endLine)   : null;
    return formatCopyCitationRange(work, s, f);
  }

  // Plain-text twin of the translationCredit snippet above (same wording as
  // its rendered textContent — see reader-translation-credit.test.ts), for
  // the copy path (finding 2, Sol review): a reader copying a credited
  // passage's English used to get no attribution at all if the selection
  // never touched the Greek, breaching the licence's attribution term.
  // Clipboard text carries no markup, so the licence link becomes a plain
  // name rather than an anchor.
  // item 85 review (2026-07-28): only the book/edition TITLE in a credit's
  // `source` should render in italics -- editors, publisher and other
  // bibliographic detail are roman, matching ordinary scholarly citation
  // style. `source` sometimes fuses the two ("Title, ed. Editors (Press)" --
  // Gorgias B11/B11a's manifest strings); split on the first ", ed." (the
  // shape both of those strings use) when present. A `source` with no such
  // split is entirely a title (every other credited passage today) and
  // stays entirely italic, unchanged from before this split existed.
  function splitCreditSource(source: string): { title: string; rest: string } {
    const i = source.indexOf(', ed.');
    if (i >= 0) return { title: source.slice(0, i), rest: source.slice(i) };
    // Fix round (Sol adversarial review on commit 7287b10, finding 2): a
    // source with no ", ed." split point used to italicize the WHOLE
    // string, publisher/editor detail and all. Fall back to the first
    // comma instead — only the text before it (the title) is italic; a
    // bare source with no comma at all can only be a title on its own, so
    // it italicizes whole, same as before.
    const c = source.indexOf(',');
    return c < 0 ? { title: source, rest: '' } : { title: source.slice(0, c), rest: source.slice(c) };
  }

  function formatCopyCredit(credit: TranslationCredit): string {
    let s = `Translation: ${credit.translator}, ${credit.source}, ${credit.year}.`;
    if (credit.licence) s += ` Licensed under ${credit.licence.name}.`;
    return s;
  }

  function summaryTranslationLabel(name: string): string {
    return `${name.split(' (')[0]} (summary)`;
  }

  // The per-passage picker's `data-eng-credit` for whichever translation is
  // DISPLAYED in this segment (segTransId): the primary slot's own
  // per-chunk credit when that's what's shown (as before), or — fix round,
  // finding 6 (Sol xhigh review) — a plain "<name> (summary)" label when
  // the displayed translation's registry entry is TranslationRef.kind ===
  // 'summary' (Gorgias B11/B11a's freeman-summary overlay). Before this, a
  // copy of the summary text carried no attribute at all (segTransId !==
  // engSlot?.id short-circuited it), making a copy of the summary
  // indistinguishable from a copy of the real translation. Every other
  // overlay (no `kind`, e.g. a secondary full translation like Burnet) is
  // untouched — undefined, exactly as before.
  function engCreditFor(transId: string, seg: Segment): string | undefined {
    if (transId === engSlot?.id && seg.english?.credit) return formatCopyCredit(seg.english.credit);
    const t = transById(transId);
    // `t.name.split(' (')[0]` drops a trailing parenthetical (an edition
    // detail like "(Blackwell, 1948)" or a translator's own year) some
    // registry names carry, so the label stays a plain
    // "<translator name> (summary)" -- not "<name> (<edition detail>) —
    // summary". A name with no " (" at all (most translator names) passes
    // through unchanged; the split is deliberately harmless in that case,
    // not dead code.
    if (t?.kind === 'summary') return summaryTranslationLabel(t.name);
    // John's ruling 2026-07-29: a PRIMARY-slot chunk whose Freeman entry is
    // wholly her own précis of a source she is reporting (EnglishChunk.summary,
    // english.summary_labels) carries the identical "(summary)" suffix --
    // same string derivation as the kind:'summary' branch above, applied
    // per PASSAGE here instead of to a whole registered translation.
    if (transId === engSlot?.id && seg.english?.summary && t) return summaryTranslationLabel(t.name);
    return undefined;
  }

  // Fix round, finding 1 (Sol xhigh review): the prior version resolved
  // only the two SELECTION ENDPOINTS' credits (`nearestEnglishCredit` on
  // start/end), so a credited English passage anywhere in the MIDDLE of a
  // range never surfaced — and handleCopy called this only when
  // greekCiteForRange came back null, so a selection with ONE endpoint in
  // Greek dropped every credited English the range touched, however far
  // into it. This instead walks every `[data-eng-credit]` element in the
  // document and keeps the ones the Range genuinely overlaps
  // (Range.intersectsNode — real DOM API, well supported), in document
  // order, deduplicated — so a selection carries every credit for licensed
  // English it touches ANYWHERE, regardless of where it starts or ends or
  // whether a Greek citation also applies.
  function collectEnglishCreditsForRange(range: Range): string[] {
    const credited = document.querySelectorAll<HTMLElement>('[data-eng-credit]');
    const matched: HTMLElement[] = [];
    for (const el of credited) {
      if (el.dataset.engCredit && range.intersectsNode(el)) matched.push(el);
    }
    // Fix round (Sol re-verify): a credited descendant (e.g. a
    // `.context-english` block with its own `data-eng-credit`) can sit
    // inside another credited ancestor (`.english-col`). When the
    // selection lies entirely within the descendant, the ancestor's
    // credit doesn't apply to anything the user actually selected — drop
    // the ancestor so only the descendant's credit is reported. The
    // ancestor stays if the range reaches outside the descendant into the
    // ancestor's own content (a genuine mixed selection).
    const wrappedByDescendant = (ancestor: HTMLElement) =>
      matched.some(
        (other) =>
          other !== ancestor &&
          ancestor.contains(other) &&
          other.contains(range.startContainer) &&
          other.contains(range.endContainer)
      );
    const credits: string[] = [];
    for (const el of matched) {
      if (wrappedByDescendant(el)) continue;
      const credit = el.dataset.engCredit;
      if (credit && !credits.includes(credit)) credits.push(credit);
    }
    return credits;
  }

  function englishCiteForRange(range: Range): string | null {
    const credits = collectEnglishCreditsForRange(range);
    return credits.length ? credits.join('\n') : null;
  }

  function handleCopy(e: ClipboardEvent) {
    if (!citeCopy) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;
    const text = sel.toString().trim();
    if (!text) return;
    const range = sel.getRangeAt(0);
    // Fix round, finding 1 (Sol xhigh review): a Greek citation and
    // credited English are no longer mutually exclusive — a mixed
    // selection (e.g. Greek at one end, licensed English elsewhere in the
    // range) appends BOTH, citation first, rather than returning as soon
    // as one is found.
    const greekCite = greekCiteForRange(range);
    const engCredit = englishCiteForRange(range);
    const parts = [greekCite, engCredit].filter((p): p is string => !!p);
    if (!parts.length) return;
    e.clipboardData?.setData('text/plain', [text, ...parts].join('\n'));
    e.preventDefault();
  }

  // ── Floating copy button (appears on Greek text selection) ────────────────
  let copyBtnPos: { x: number; y: number } | null = null;

  function checkCopyBtn() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) { copyBtnPos = null; return; }
    const range = sel.getRangeAt(0);
    if (!nearestGreekLine(range.startContainer) && !nearestGreekLine(range.endContainer)) {
      copyBtnPos = null; return;
    }
    const rect = range.getBoundingClientRect();
    if (!rect.width && !rect.height) { copyBtnPos = null; return; }
    copyBtnPos = { x: rect.right, y: rect.top };
  }

  function onSelectionChange() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) copyBtnPos = null;
  }

  function clickCopyBtn() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) { copyBtnPos = null; return; }
    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    // Same mixed-range fix as handleCopy (finding 1, Sol xhigh review): a
    // Greek citation and credited English are both appended when both
    // apply, not treated as mutually exclusive.
    const greekCite = greekCiteForRange(range);
    const engCredit = englishCiteForRange(range);
    const parts = [greekCite, engCredit].filter((p): p is string => !!p);
    const full = parts.length ? [text, ...parts].join('\n') : text;
    navigator.clipboard.writeText(full).catch(() => {});
    copyBtnPos = null;
  }
</script>

<!-- View toggle and Print control are rendered in the reader header on desktop
     and inside the ⚙ Settings sidebar on mobile (CSS scopes which is visible).
     Top-level snippets keep a single source of markup and one printMenuOpen. -->
{#snippet viewToggle()}
  <div class="view-toggle" role="group" aria-label="Reading view">
    <button class:active={view === 'greek'} aria-pressed={view === 'greek'} on:click={() => setView('greek')}>{sourceLanguageLabel}</button>
    {#if hasEnglish}
      <button class:active={view === 'both'} aria-pressed={view === 'both'} on:click={() => setView('both')}>Both</button>
      <button class:active={view === 'english'} aria-pressed={view === 'english'} on:click={() => setView('english')}>English</button>
    {/if}
  </div>
{/snippet}

{#snippet printControl()}
  {#if chaptersInBook.length > 1}
    <div class="print-menu">
      <button class="print-btn" on:click={togglePrintMenu} title="Print or save as PDF" aria-label="Print or save as PDF">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M6 9V2h12v7" />
          <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
          <rect x="6" y="14" width="12" height="8" />
        </svg>
        <span class="print-btn-label">Print</span>
        <svg class="print-chevron" viewBox="0 0 10 6" width="8" height="5" fill="currentColor" aria-hidden="true"><path d="M0 0l5 6 5-6z"/></svg>
      </button>
      {#if printMenuOpen}
        <div class="print-dropdown">
          <button class="print-dd-item" on:click={() => { printMenuOpen = false; printReader(); }}>Full book</button>
          <div class="print-dd-sep" role="separator"></div>
          {#each chaptersInBook as ch}
            <button class="print-dd-item" on:click={() => { printMenuOpen = false; printSingleChapter(ch); }}>
              {#if bookLabel}{bookLabel}, {/if}{chapterUnitNoun} {ch}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {:else}
    <button class="print-btn" on:click={printReader} title="Print or save as PDF" aria-label="Print or save as PDF">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M6 9V2h12v7" />
        <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
        <rect x="6" y="14" width="12" height="8" />
      </svg>
      <span class="print-btn-label">Print</span>
    </button>
  {/if}
{/snippet}

{#if loading}
  <p style="padding:2rem;font-family:system-ui;color:#888">Loading Book {bookNum}…</p>
{:else if error}
  <p style="padding:2rem;color:red">{error}</p>
{:else}
  {#snippet greekToks(parts: LineRenderPart[])}{#each parts as part}{#if part.kind === 'token'}<span
        class="tok"
        class:active={popup?.token === part.tok}
        class:hit={isHit(part.tok.t)}
        role="button"
        tabindex="-1"
        aria-label="Analyse {part.tok.t}"
        aria-haspopup="dialog"
        on:click={(e) => handleTokenClick(e, part.tok)}
        on:keydown={(e) => onTokenKey(e, part.tok)}
      >{part.text}</span>{:else if part.kind === 'speaker'}<span class="speaker" class:speaker-dash={part.dash} lang={sourceLang}>{part.label}</span>{:else}{part.text}{/if}{/each}{/snippet}
  {#snippet chapterHead(block: Block)}
    <div class="chapter-head" id="ch-{bookNum}-{block.chapter}">
      <span class="chapter-label">{#if bookLabel}<span class="chapter-book">{bookLabel},&nbsp;</span>{/if}{chapterUnitNoun} {block.chapter}{#if chapterTitles[block.chapter ?? '']}: {chapterTitles[block.chapter ?? '']}{/if}</span>
      {#if block.bekker && !busse}<span class="chapter-bekker">({block.bekker})</span>{/if}
    </div>
  {/snippet}

  <!-- Per-passage translation credit (EnglishChunk.credit): the translator,
       edition and — for a text used under a licence rather than a public-
       domain one — that licence, linked to its deed. Plain scholarly
       citation prose, in the same quiet treatment as the source-passage
       English's own credit line. The line itself is roman; only the book/
       edition title (splitCreditSource) is italic, ordinary citation style
       -- textContent is unchanged by the split (a <span> adds no text), so
       formatCopyCredit's plain-text twin stays byte-identical. -->
  {#snippet translationCredit(credit: TranslationCredit)}
    {@const src = splitCreditSource(credit.source)}
    <div class="translation-credit">Translation: {credit.translator}, <span class="translation-credit-title">{src.title}</span>{src.rest}, {credit.year}.{#if credit.licence}{' '}Licensed under <a href={credit.licence.url} rel="license noopener" target="_blank">{credit.licence.name}</a>.{/if}</div>
  {/snippet}

  <!-- Item 84 (REVIEW-CHECKLIST): per-passage translation picker, generalized
       from item 82's context-English toggle -- same plain-text button-group
       register (not a <select>; that pattern is reserved for the work-level
       picker). Renders on the segment's `.seg-ref` line, right-aligned
       against the column reference (translator-picker alignment fix --
       formerly above a segment's English column, which pushed the English
       column's first line below the Greek's first line), whenever 2+ of the
       work's translations carry actual text for THIS segment (see
       availableTranslationsFor). Page-local only (segTransOverride above) --
       the work-level `trans` selection stays every other segment's default,
       and a work-level switch still repaints any segment with no override.
       Rendered only when trans !== 'compare' (compare mode is out of scope).

       John's ruling 2026-07-29: also rendered (as a single, already-active
       chip) when the segment carries only the primary translation AND that
       chunk is EnglishChunk.summary -- a Freeman précis with no OTHER
       translation to switch to still needs its "Freeman (summary)" label
       visible on the card, reusing this same picker markup rather than a
       parallel one (see the `label` const below, and engCreditFor's twin
       "(summary)" derivation for the copy/data-eng-credit surfaces). -->
  {#snippet segTransToggle(seg: Segment)}
    {@const available = availableTranslationsFor(seg)}
    {#if available.length > 1 || seg.english?.summary}
      <!-- Read segTransOverride/trans directly here (not via the segTrans(seg)
           helper) -- Svelte's template dependency tracking only sees
           identifiers referenced directly in the template, so a click that
           reassigns segTransOverride would not re-render this snippet
           otherwise (item 82's contextEnglishAlt is indexed directly for the
           same reason). -->
      {@const active = segTransOverride[seg.id] ?? trans}
      <div class="seg-trans-toggle" role="group" aria-label="Translation for this passage">
        {#each available as t, i}
          {#if i > 0}<span class="seg-trans-sep">·</span>{/if}
          <!-- Item 84 mislabel fix (REVIEW-CHECKLIST, John live catch on
               Gorgias B11): the PRIMARY ('english') slot's registry `short`
               names the work's usual translation (e.g. "Freeman"), but a
               chunk's own per-chunk credit (EnglishChunk.credit, e.g. the
               Parnassos-style B11 swap to Jurgen R. Gatt) means the text
               actually displayed is someone else's -- the label must follow
               what's shown, not the slot's work-level name. Only the primary
               slot's chunk (seg.english) carries a credit today (OverlayPiece/
               overlay pieces have no `credit` field), so this check only
               needs to look there; a non-primary slot ever gaining a credit
               would take the same branch once it does. -->
          {@const label = t.slot === 'english' && seg.english?.credit
            ? surnameFromCredit(seg.english.credit.translator) || t.short
            : t.slot === 'english' && seg.english?.summary
              ? summaryTranslationLabel(t.short)
              : t.short}
          <button
            type="button"
            class="seg-trans-btn"
            class:active={active === t.id}
            aria-pressed={active === t.id}
            on:click={() => selectSegTrans(seg.id, t.id)}
          >{label}</button>
        {/each}
      </div>
    {/if}
  {/snippet}

  <!-- One English column for a translation: the primary's flow (block.flow) or
       an overlay's (block.oflows[id]), as flowing prose with margin-floated
       Bekker numbers. The footnote/table-bearing translation ('third' slot)
       uses renderThird + clickable `[^N]` markers + diagram tables; the rest
       use plain highlightEng. Works for any number of translations. -->
  {#snippet transFlow(block: Block, transId: string, segKind?: string, inlineTick?: string)}
    {@const flow = transId === engSlot?.id ? block.flow : (block.oflows[transId] ?? [])}
    {#if flow.length}
      {@const chTitle = importChapterTitle(transId, block.chapter)}
      <!-- An imported translation's chapter-opening title: a SIBLING before
           .overlay-prose, not its first child — (a) inside .overlay-prose it pushed
           the English prose one line below the Greek (John's review of
           631ff971); the Greek column gets a matching invisible spacer
           instead (see the .greek-col markup below), so Greek line 1 and
           English prose line 1 stay flush and the title takes its own space
           above; (b) the offset walkers (annotations.ts proseOffsetAt,
           emphasis-paint.ts proseText) root at col.querySelector('.overlay-prose')
           and exclude only .bk-num/.eng-table, so title text INSIDE
           .overlay-prose would leak into captured offsets — as a sibling they
           never see it, keeping the render-only/no-offset-shift guarantee
           structural. -->
      {#if chTitle}<div class="overlay-chapter-title">{chTitle}</div>{/if}
      {#if fnTransIds.has(transId)}
        {#snippet thirdPart(part: RenderPart)}
          {#if part.text === '\n'}
            <br class="para-br" />
          {:else if part.text !== null}
            <span class="bk-seg"
              >{#if part.tick}<span class="bk-num" class:approx={!part.tick.real}>{part.tick.n}</span
                >{/if}<!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html renderThird(part.text, transId)}</span>
          {:else if part.para}
            <br class="para-br" />
          {:else}
            <span class="bk-num" class:approx={!part.real}>{part.n}</span>
            {#each (block.otables[transId] ?? []).filter(t => t.n === part.n) as tbl}
              <table class="eng-table"><tbody>
                {#each tbl.rows as trow}
                  <tr>{#each trow as cell}<td>{cell}</td>{/each}</tr>
                {/each}
              </tbody></table>
            {/each}
          {/if}
        {/snippet}
        <div
          class="overlay-prose"
          on:mouseover={onFootnoteOver}
          on:mouseout={onFootnoteOut}
          on:focus={onFootnoteFocus}
          on:blur={onFootnoteBlur}
          on:focusin={onFootnoteFocus}
          on:focusout={onFootnoteBlur}
          on:click={onFootnoteClick}
          on:keydown={onFootnoteClick}
          role="presentation"
        >{#if inlineTick}<span class="sect-tick-inline" data-n={inlineTick} aria-hidden="true"></span>{/if}
          {#each groupVerse(attachTicks(flow, new Set((block.otables[transId] ?? []).map(t => t.n)))) as item}
            {#if 'verse' in item}
              <div class="verse">
                {#each item.lines as lineParts}
                  <span class="verse-line">{#each lineParts as part}{@render thirdPart(part)}{/each}</span>
                {/each}
              </div>
            {:else}
              {@render thirdPart(item)}
            {/if}
          {/each}
        </div>
      {:else}
        {#snippet plainPart(part: RenderPart)}
          {#if part.text === '\n'}
            <br class="para-br" />
          {:else if part.text !== null}
            <span class="bk-seg"
              >{#if part.tick}<span class="bk-num" class:approx={!part.tick.real}>{part.tick.n}</span
                >{/if}{#if part.frame}<span class="eng-source-frame"><!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html highlightEng(part.text)}</span>{:else}<!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html highlightEng(part.text)}{/if}</span>
          {:else if part.para}
            <br class="para-br" />
          {:else}
            <span class="bk-num" class:approx={!part.real}>{part.n}</span>
          {/if}
        {/snippet}
        <div class="overlay-prose" class:frag-title={segKind === 'title'}>{#if inlineTick}<span class="sect-tick-inline" data-n={inlineTick} aria-hidden="true"></span>{/if}
          {#each groupVerse(attachTicks(flow)) as item}
            {#if 'verse' in item}
              <div class="verse">
                {#each item.lines as lineParts}
                  <span class="verse-line">{#each lineParts as part}{@render plainPart(part)}{/each}</span>
                {/each}
              </div>
            {:else}
              {@render plainPart(item)}
            {/if}
          {/each}
        </div>
      {/if}
    {:else}
      <!-- The manifest legitimately allows a translation to skip a section
           (e.g. Haines has no Meditations 12.15) — a blank gutter
           reads as a bug, so name the gap and point at whichever OTHER
           translation does carry this block, rather than rendering nothing.
           Names come from the registry (citeShort/translations), never
           hardcoded, so this tracks any future work/translation. -->
      {@const other = translations.find(t => t.id !== transId && (t.id === engSlot?.id ? block.flow : (block.oflows[t.id] ?? [])).length)}
      {#if other}
        <p class="trans-missing-note">Not in {citeShort(transById(transId))} — see {other.short}.</p>
      {/if}
    {/if}
  {/snippet}

  <!-- The turn flow of a dialogue book: one row per speaker turn, the whole
       book long — each speaker's Greek statement level with its English
       translation (Tier-0 alignment). Stephanus sections are gutter TICKS, not
       layout containers: each section's first Greek line floats its token in
       the center gutter (Both view) / left gutter (Greek-only), and the tick
       element carries the col-{token} citation anchor (deep links, outline
       nav, scroll-spy, resume). In English-only view the Greek cells are
       hidden, so each row also carries no-id [data-etick] markers in the left
       gutter for the sections starting within it (row-level approximation —
       English tick precision is deferred Tier 1+). One-sided residual rows
       (unpaired turns) render in place with the other cell empty. -->
  <!-- Narrated paragraph prose: the row's English with `ep` paragraph breaks
       rendered as <br class="para-br"> (reusing flowParts/attachTicks — no
       Bekker ticks are passed here, so only the paragraph breaks and any hard
       newlines survive). flowParts clamps each break offset into the slice, so
       a break landing exactly on a turn/tick offset can't over-run the text. -->
  {#snippet paraProse(text: string, ep: number[] | null | undefined)}
    {#each attachTicks(flowParts(text, [], ep ?? [])) as part}
      {#if part.text === '\n'}
        <br class="para-br" />
      {:else if part.text !== null}
        <span class="bk-seg"><!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html highlightEng(part.text)}</span>
      {:else if part.para}
        <br class="para-br" />
      {/if}
    {/each}
  {/snippet}

  <!-- One row's PRIMARY-translation English cell body (et embed / dialogue turn
       + folded subs). Factored out of the turn-flow english column so it can
       render in EITHER compare column when that column shows the primary. -->
  {#snippet primaryEng(row: FlowRow, ri: number)}
    {#if paraFlow && row.et && row.et.length}
      <div class="overlay-prose turn-eng turn-stack">
        {#each etBlocks(row.english ?? '', row.et, row.ep) as b}
          <p class="turn-para">{#if !b.lead}{#if b.display}<span class="speaker" data-spk={spkSlots.get(b.display)}>{b.display}</span>{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{@render paraProse(b.text, b.ep)}</p>
        {/each}
      </div>
    {:else}
      {#if row.english}
        <div class="overlay-prose turn-eng">
          {#if !paraFlow && !row.lead}{#if row.display}{#if !rowMeta[ri]?.hideLead}<span class="speaker" data-spk={spkSlots.get(row.display)}>{row.display}</span>{/if}{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{@render paraProse(row.english, row.ep)}{#each row.englishCont as c}<p class="turn-cont">{@render paraProse(c.text, c.ep)}</p>{/each}</div>
      {/if}
      {#if row.sub && row.sub.length}
        <div class="overlay-prose turn-eng turn-stack">
          {#each row.sub as s, si}
            <p class="turn-para">{#if s.d}{#if !rowMeta[ri]?.hideSub[si]}<span class="speaker" data-spk={spkSlots.get(s.d)}>{s.d}</span>{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{@render paraProse(s.e, s.ep)}</p>
          {/each}
        </div>
      {:else if paraFlow && !row.english && !row.lead}
        <div class="overlay-prose turn-eng"><span class="eng-missing" aria-hidden="true">—</span></div>
      {/if}
    {/if}
  {/snippet}

  <!-- One row's ALTERNATE-translation cell (turn-by-turn compare). The turn
       aligner gives each alternate one per-turn slice (alt[id] = {e, ep}), so
       this is just the row's speaker lead-in + that slice, or an em-dash where
       the alternate has no matching turn. No et/sub structure — alternates
       carry plain per-turn prose. Label suppression mirrors the primary (same
       speaker sequence) so the two columns stay visually parallel. -->
  {#snippet altEng(row: FlowRow, ri: number, id: string)}
    {@const a = row.alt?.[id]}
    <div class="overlay-prose turn-eng">
      {#if !paraFlow && !row.lead}{#if row.display}{#if !rowMeta[ri]?.hideLead}<span class="speaker" data-spk={spkSlots.get(row.display)}>{row.display}</span>{/if}{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{#if a && a.e}{@render paraProse(a.e, a.ep)}{:else}<span class="eng-missing" title="No aligned passage in this translation"><span class="sr-only">No aligned passage in this translation.</span><span aria-hidden="true">—</span></span>{/if}</div>
  {/snippet}

  {#snippet flowRowsView(rows: FlowRow[])}
    <div class="turn-flow" class:para-flow={paraFlow} class:spk-color={spkColor}>
      {#each rows as row, ri}
        <!-- Which translation the (single / left) English column shows: the
             selected id, or the left compare id in compare mode. -->
        {@const leftId = trans === 'compare' ? compareLeft : trans}
        <div class="seg-row turn-row" class:turn-lead={row.lead} class:turn-residual={!row.lead && !row.paired}>
          <!-- Each turn row is a single speaker, so the Greek siglum (ΣΩ.) is
               coloured to match the row's English name via the column's data-spk
               (see .greek-col[data-spk] rules in global.css). -->
          <div class="greek-col" lang={sourceLang} data-spk={row.display ? spkSlots.get(row.display) : undefined}>
            {#each row.greek as gl}
              <!-- Only the line's opening slice carries its id: a line split by
                   several turns (Parmenides' dash runs) yields multiple cont
                   slices, and repeating an -c id per slice would duplicate
                   ids. Cont slices aren't citation targets, so they get none. -->
              <div class="greek-line" id={gl.cont ? undefined : `L${gl.col}-${gl.n}`} class:target={!gl.cont && targetId === `L${gl.col}-${gl.n}`} class:cont={gl.cont}>
                {#if gl.tick}<span class="sect-tick" id="col-{gl.tick}">{gl.tick}</span>{/if}
                <span class="line-num">{gl.cont ? '' : showLineNum(gl.n)}</span>
                <span class="line-text" lang={sourceLang}>{@render greekToks(gl.parts)}</span>
              </div>
            {/each}
          </div>
          <div class="english-col" data-trans={leftId}>
            {#if trans === 'compare'}<div class="col-label">{transById(compareLeft)?.short ?? 'English'}</div>{/if}
            {#each row.ticks as t}<span class="sect-tick eng-tick" data-etick={t} aria-hidden="true">{t}</span>{/each}
            <!-- The (single / left) column shows the primary translation inline
                 (its full et/dialogue/sub structure) or, for an alternate id,
                 the aligner's per-turn slice via altEng. -->
            {#if leftId !== engSlot?.id}{@render altEng(row, ri, leftId)}{:else if paraFlow && row.et && row.et.length}
              <!-- Narrated embedded-dialogue row (para flow, `et`): the row's
                   English is english.turns nested inside a narrated paragraph —
                   set as a .turn-stack of labelled blocks (em-dash when the
                   lead-in is null), any `ep` breaks rebased per block. -->
              <div class="overlay-prose turn-eng turn-stack">
                {#each etBlocks(row.english ?? '', row.et, row.ep) as b}
                  <p class="turn-para">{#if !b.lead}{#if b.display}<span class="speaker" data-spk={spkSlots.get(b.display)}>{b.display}</span>{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{@render paraProse(b.text, b.ep)}</p>
                {/each}
              </div>
            {:else}
              {#if row.english}
                <!-- The row's own English: dialogue rows keep their speaker
                     lead-in (em-dash for an unattributed turn); paragraph rows
                     (kind==='para') have no speaker, so the em-dash fallback is
                     suppressed. BOTH render `ep` paragraph breaks — pipeline B2
                     gives dialogue turns internal breaks too (Timaeus/Phaedo
                     long speeches), not just para flows. -->
                <div class="overlay-prose turn-eng">
                  {#if !paraFlow && !row.lead}{#if row.display}{#if !rowMeta[ri]?.hideLead}<span class="speaker" data-spk={spkSlots.get(row.display)}>{row.display}</span>{/if}{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}{@render paraProse(row.english, row.ep)}{#each row.englishCont as c}<p class="turn-cont">{@render paraProse(c.text, c.ep)}</p>{/each}</div>
              {/if}
              {#if row.sub && row.sub.length}
                <!-- One-sided English speeches folded under this row (pipeline
                     B4 residual redesign — dialogue flows AND para flows): a
                     stack of labelled blocks under the row's Greek. Usually the
                     row's `e` is null and this stack IS the English cell; when
                     the row also carries English (a narration lead, e.g. Lysis
                     203a) the stack follows it. Lead-in span when a printed
                     display exists; em-dash otherwise (genuine speaker turns —
                     Fowler's prose embeds the "he said" attributions). -->
                <div class="overlay-prose turn-eng turn-stack">
                  {#each row.sub as s, si}
                    <p class="turn-para">{#if s.d}{#if !rowMeta[ri]?.hideSub[si]}<span class="speaker" data-spk={spkSlots.get(s.d)}>{s.d}</span>{/if}{:else}<span class="speaker speaker-dash">—</span>{/if}{@render paraProse(s.e, s.ep)}</p>
                  {/each}
                </div>
              {:else if paraFlow && !row.english && !row.lead}
                <!-- Defensive: a para-flow row with Greek but NO English content
                     (e null, sub null/empty) is malformed pipeline output — the
                     contract says every para row carries e or sub. Render an
                     intentional untranslated marker instead of a silently blank
                     cell (the blank-cell defect this round eliminates). Dialogue
                     flows are exempt: a Greek-only residual with a blank English
                     cell is their normal pre-B4 shape. -->
                <div class="overlay-prose turn-eng"><span class="eng-missing" aria-hidden="true">—</span></div>
              {/if}
            {/if}
          </div>
          <!-- Right compare column: the second chosen translation, turn-by-turn
               beside the first (hidden in Greek-only). Either column may be the
               primary or an alternate — pick the renderer by id. -->
          {#if trans === 'compare' && view !== 'greek'}
            <div class="overlay-col" data-trans={compareRight}>
              <div class="col-label">{transById(compareRight)?.short ?? ''}</div>
              {#if compareRight === engSlot?.id}{@render primaryEng(row, ri)}{:else}{@render altEng(row, ri, compareRight)}{/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/snippet}

  <div class="reader-body view-{view} trans-{trans}" role="main"
    bind:this={readerBodyEl}
    class:busse={busse}
    class:stephanus={stephanus}
    class:dk-verse={dkVerse}
    class:verse-line={verseLine}
    class:section-flow={sectionFlow}
    class:word-open={!!popup}
    style="--fs-greek:{fsGreek}rem;--fs-english:{fsEng}rem;--lh-greek:{lhGreek};--lh-english:{lhEng};--colw-scale:{colScale};--fs-scale:{fsScale}"
    on:copy={handleCopy}>
    <div class="reader-controls">
      {#if liveChapter}
        <span class="rc-context">{liveChapter}</span>
      {/if}
      <div class="rc-cite">
        {#if view === 'greek'}
          {#if greekSrc}<span class="rc-greek">{greekSrc.full}</span>{/if}
        {:else if trans === 'compare'}
          {#if view === 'both'}<span class="rc-col-spacer" aria-hidden="true"></span>{/if}
          <span class="rc-col-name">{citeShort(transById(compareLeft))}</span>
          <span class="rc-col-name">{citeShort(transById(compareRight))}</span>
        {:else if view === 'both'}
          <span class="rc-pair">{pairText}</span>
        {:else if selectedTrans}
          <span class="rc-full">{selectedTrans.name}</span>
        {/if}
      </div>
      {#if freemanCredit}<div class="rc-freeman-credit">{freemanCredit}</div>{/if}
      <div class="rc-controls">
        {#if !hasEnglish}
          <!-- design pin (task #4): PD translations often exist but aren't
               wired yet — never imply none exists. -->
          <span class="rc-no-english">No English translation wired yet.</span>
        {/if}
        {#if view !== 'greek' && translations.length === 1}
          <span class="rc-trans-abbr">{citeShort(translations[0])}</span>
        {/if}
        {#if translations.length > 1}
          <!-- Desktop translation picker, beside the view toggle. On mobile this
               is hidden (see global.css) and the same control lives in the
               ⚙ Settings sidebar instead. -->
          <select class="rc-trans-select" value={pickValue} on:change={onPick} aria-label="English translation">
            {#each translations as t}
              <option value={t.id}>{t.name}</option>
            {/each}
          </select>
        {/if}
        <!-- Desktop only — on mobile these live in the ⚙ Settings sidebar. -->
        <div class="rc-desktop-controls">
          {@render viewToggle()}
          {@render printControl()}
        </div>
      </div>
    </div>
    <!-- Print-only masthead (hidden on screen): author eyebrow, work title with
         its Greek title alongside, and the source citation. -->
    <div class="print-head" aria-hidden="true">
      <div class="print-eyebrow">{authorName}</div>
      <div class="print-titleline">
        <span class="print-title">{workMeta?.title ?? ''}</span>
        {#if workMeta?.greekTitle}<span class="print-title-gk">{workMeta.greekTitle}</span>{/if}
      </div>
      {#if printCite}<div class="print-cite">{printCite}</div>{/if}
    </div>
    {#if hasApproxTicks && !busse}
      <!-- The estimate disclaimer stays one click away, not a paragraph of
           front matter: the honesty lives in the ticks themselves (upright vs
           italic grey); this explains the convention on demand. -->
      <div class="bekker-info">
        <button
          type="button"
          class="bekker-info-btn"
          aria-expanded={bekkerInfoOpen}
          on:click|stopPropagation={() => (bekkerInfoOpen = !bekkerInfoOpen)}
        >ℹ︎ Bekker numbers</button>
        {#if bekkerInfoOpen}
          <div class="bekker-info-pop" role="note" transition:fade={{ duration: reduceMotion ? 0 : 120 }}>
            {sourceLanguageLabel} line numbers are exact. The translations carry no Bekker
            numbers of their own, so those beside the English are aligned to
            the {sourceLanguageLabel}: <span class="bk-fixed">upright</span> = fixed (anchored
            to this point in the text), <span class="bk-approx">italic grey</span>
            = approximate (interpolated estimate).
          </div>
        {/if}
      </div>
    {/if}
    {#if flowRows}
      <!-- Dialogue book: the continuous turn flow replaces the per-section
           segment blocks; Stephanus tokens float as gutter ticks. -->
      {@render flowRowsView(flowRows)}
    {:else}
    {#each enrichedSegments as {seg, blocks}, si (seg.id)}
      {@const leadChapter = blocks[0]?.chapter ? blocks[0] : null}
      {@const citationByBlock = expandedCitationByBlock(seg, blocks)}
      <!-- Freeman Ancilla group-header paratext (design note §1/§3.7): a
           full-width ribbon before the segment it precedes, rendered in
           EVERY view including Greek-only (John's post-draft ruling —
           editorial structure, not a translation). -->
      {#each (paratextByColumn[seg.column] ?? []) as header}
        <div class="frag-group-header level-{header.level}">{header.text}</div>
      {/each}
      {@const verseDiscontinuity = verseLine && (seg.greek[0]?.role === 'lacuna' || !!seg.greek[0]?.seamNote) ? (seg.greek[0]?.role === 'lacuna' ? 'lacuna' : 'seam') : undefined}
      <!-- verse-line editorial discontinuities (fix round, finding 6, Sol
           review): the blanket `.reader-body.verse-line .segment` rule
           removes ALL separation between consecutive verse lines so they
           read as one continuous block — but a lacuna gap or a
           transposition seam note is a real discontinuity that must stay
           visually set off. data-discontinuity backs global.css's targeted
           margin exception; every ordinary verse-line segment is untouched. -->
      <div class="segment" id="col-{seg.column}" data-kind={seg.kind} data-discontinuity={verseDiscontinuity}>
        {#if sectionFlow}<span class="sect-tick" aria-hidden="true" data-n={seg.column}></span>{/if}
        <!-- A chapter that opens this column heads the segment, ABOVE the column
             reference (the column ref is a marker within the chapter, not a
             heading over it). Mid-column chapter starts render inline below. -->
        {#if leadChapter}{@render chapterHead(leadChapter)}{/if}
        {#if !busse && !verseLine}
          <!-- John's ask (translator-picker alignment): the per-passage
               toggle (segTransToggle, formerly floating above the English
               column -- see its two removed call sites below) now renders
               on THIS line, right-aligned against the column reference, so
               "B8" and "Freeman · Burnet" share a baseline and the English
               column's first line can start flush with the Greek's (the
               toggle no longer eats a line inside .english-col). The label
               is wrapped in its own span so the scroll-spy fallback below
               (segRefEls / textContent, ~line 786) keeps reading just the
               column reference, not the toggle's button text. -->
          {#if sectionFlow && !keepSectionFlowHeader(seg)}
            {#if trans !== 'compare'}<div class="seg-ref seg-ref--flow">{@render segTransToggle(seg)}</div>{/if}
          {:else}
          <div class="seg-ref">
            <span class="seg-ref-label">{seg.column}{#if seg.kind === 'note'}<span class="frag-title-chip">editorial note</span>{:else if seg.kind === 'embedded'}<span class="frag-title-chip">embedded quotation</span>{:else if seg.kind === 'title'}<span class="frag-title-chip">title</span>{/if}{#if seg.english?.title}<span class="seg-ref-title"> · {seg.english.title}</span>{/if}</span>
            {#if trans !== 'compare'}{@render segTransToggle(seg)}{/if}
          </div>
          {/if}
        {/if}
        {#if seg.abridged}<div class="frag-abridged">Summary — not a complete translation</div>{/if}

        {#each blocks as block, bi}
          <!-- If the on-screen primary translation (English cell of this row)
               opens this chapter with an imported title, the Greek column gets
               an invisible spacer of the same one-line height (see
               .overlay-chapter-title-spacer in global.css) so both columns are
               pushed down equally: title above, Greek line 1 flush with
               English prose line 1. Same gates as the visible title in
               transFlow (chapter start + that import's flow present here);
               skipped in greek-only view (no title shown → no gap). Compare
               mode aligns Greek to the LEFT column; the right column's own
               title still renders in its cell via transFlow. -->
          <!-- Item 84: the per-segment override, read directly here (not
               through the segTrans(seg) helper) so Svelte's template
               dependency tracking actually sees segTransOverride and
               re-renders this block when a toggle click reassigns it --
               dependency reads hidden inside a plain function call are
               invisible to that tracking (the reason contextEnglishAlt,
               item 82, is always indexed directly in the template too). -->
          {@const segTransId = segTransOverride[seg.id] ?? trans}
          {@const spacerTransId = trans === 'compare' ? compareLeft : segTransId}
          {@const spacerFlow = spacerTransId === engSlot?.id ? block.flow : (block.oflows[spacerTransId] ?? [])}
          {@const spacerTitle = view !== 'greek' && spacerFlow.length ? importChapterTitle(spacerTransId, block.chapter) : ''}
          {#if block.chapter && !(bi === 0 && leadChapter)}
            {@render chapterHead(block)}
          {/if}
          <!-- Item 85 row-alignment: the Greek-side per-item rendering,
               factored into a snippet so both the ordinary single-.seg-row
               path below AND the row-aligned `.frag-row-split` path (John's
               live-review layout ruling — sectionRowSplit) render each
               GreekItem identically. Byte-identical to the pre-extraction
               markup; only the `greekItems(...)` call itself moved to each
               caller (they pass different item arrays: the whole column vs
               one row's slice). -->
          {#snippet greekColumnItems(items: GreekItem[], seg: Segment, si: number)}
            {#each items as item}
              {#if item.kind === 'table'}
                <!-- Greek inline table (the TLG ⎪ column square, e.g. De Int 22a). -->
                <table class="greek-table"><tbody>
                  {#each item.rows as row}
                    <tr id={`L${seg.column}-${row.n}`} class:target={targetId === `L${seg.column}-${row.n}`}>
                      <td class="line-num">{showLineNum(row.n)}</td>
                      {#each (row.cells ?? []) as cell}
                        <td class="line-text" lang={sourceLang}>{@render greekToks(cellParts(cell))}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody></table>
              {:else if item.kind === 'source-head'}
                <!-- DK source-citation head (prose-flow post-draft ruling):
                     pure Latin/ASCII apparatus citation on its own hanging
                     small-caps line, muted — DK's own page grammar. -->
                <div class="frag-source-head" lang={sourceLang}>{@render greekToks(lineRenderParts(item.line.text, item.line.tokens, speakerEvents(seg, item.line)))}</div>
              {:else if item.kind === 'witness'}
                <!-- DK apparatus witness row (dk_witness.py's split_witnesses,
                     Segment.witnesses): one row per ancient source instead of
                     one undifferentiated context blob. No id (never a
                     citation target, same as any other context content).
                     Tokens are the witness's OWN slice of the apparatus, cut
                     by offset in stage7_emit and rebased to this text, so
                     click-to-parse works here exactly as it does on an
                     unsplit column — 27,161 clickable Greek words across the
                     split columns would otherwise go dead. -->
                <p class="greek-line frag-flow frag-witness">
                  <span class="line-num"></span>
                  <span class="line-text" lang={sourceLang}><span class="frag-ctx">{#if item.witness.source}<span class="frag-witness-source">{item.witness.source}</span>{' '}{/if}{@render greekToks(lineRenderParts(item.witness.text, item.witness.tokens ?? []))}</span></span>
                </p>
              {:else if item.kind === 'flow'}
                <!-- DK prose-flow (docs/prose-flow-design.md §1): one flowing
                     paragraph of inline role-runs. Prose columns keep
                     class="greek-line" + column-only id (`L{column}`, never
                     run n) so scroll-spy observes at column granularity.
                     Verse-frame flows (context around lineated quote) set
                     anchor=false — no id; quote lines carry L{col}-{n}. -->
                {#if bookSectionFlow}
                  <!-- item 23 unification: chapter-level book-section works
                       (Marcus Aurelius, Discourses, Diogenes Laertius,
                       Cicero's book-section works) flow every run of the
                       segment into ONE paragraph instead of DK's
                       (possibly marker-split) grouping -- sectionMarker
                       never fires here (no contextEnglish declared for
                       these works). Each run keeps the EXACT anchor id
                       the old per-line block rendering gave it
                       (flowRunId) -- see that function's own doc comment
                       for exactly which mechanisms (#-target, scroll-spy,
                       copy-citation) actually resolve per run vs per
                       paragraph. A run whose own line carries a Schenkl
                       `sections` subsection number (paraN) gets a small
                       gutter marker (.greek-para-n-flow, absolute-
                       positioned like the English's own .bk-num Bekker
                       ticks -- no row break) instead of the old block-
                       above-the-paragraph treatment, UNLESS it collides
                       with the marker before it (paraMarkerIsGutter, fix
                       round finding 3), in which case it falls back to a
                       plain inline ".para-n". A plain multi-line segment
                       with no such channel (ordinary Marcus/DL/Cicero
                       prose) shows no marker at all.
                       Fix round finding 1 (Sol review): run.cls
                       ('frag-txt') is DK's own role-distinction class and
                       carries DK's font-weight:500 -- book-section has no
                       role distinction of its own (never role='context'),
                       so its source text must render at the SAME weight
                       the pre-flow per-line block rendering used (no
                       class at all, i.e. normal weight). The scoping
                       class "bs-flow" (below, and on .greek-line.frag-flow
                       .line-text's position:relative in global.css --
                       finding 6) neutralizes frag-txt's weight for this
                       branch only; DK's own frag-flow paragraphs are
                       untouched. -->
                  {@const firstId = flowRunId(item.prose.runs[0]!.line as RLine, seg.column)}
                  {@const firstCont = !!(item.prose.runs[0]!.line as RLine).cont}
                  {@const gutterFlags = paraMarkerIsGutter(item.prose.runs.map((r) => ({ paraN: (r.line as RLine).paraN, text: r.line.text })))}
                  <p
                    class="greek-line frag-flow bs-flow"
                    id={item.anchor ? firstId : undefined}
                    class:target={item.anchor && !firstCont && targetId === firstId}
                  >
                    <span class="line-num"></span>
                    <span class="line-text" lang={sourceLang}>{#if sectionFlow}<span class="sect-tick-inline" data-n={seg.column} aria-hidden="true"></span>{/if}{#each item.prose.runs as run, ri}{@const rline = run.line as RLine}{@const rid = flowRunId(rline, seg.column)}{#if ri > 0 && run.space}{' '}{/if}{#if rline.paraN != null}<span class="para-n" class:greek-para-n-flow={gutterFlags[ri]} aria-hidden="true" data-n={rline.paraN}></span>{/if}<span id={ri > 0 ? rid : undefined} class:target={ri > 0 && !rline.cont && targetId === rid} class={run.cls}>{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}</span>{/each}</span>
                  </p>
                {:else}
                <!-- DK inline "(NN)" section marker (John's thales/testimonia
                     A1 note: the Greek context block should paragraph-break
                     in parallel with the English's own per-section split) --
                     same label treatment as the source-passage English's
                     .context-english-section-marker, so the two columns
                     read as visually parallel. Absent for a paragraph with
                     no leading marker (e.g. a work with no such markers at
                     all keeps the single unmarked paragraph it always had). -->
                {#if item.prose.sectionMarker}<div class="greek-context-section-marker">({item.prose.sectionMarker})</div>{/if}
                <p
                  class="greek-line frag-flow"
                  id={item.anchor ? `L${seg.column}` : undefined}
                  class:target={item.anchor && targetId === `L${seg.column}`}
                  data-incipit={item.prose.incipit ? '' : undefined}
                >
                  <span class="line-num"></span>
                  <!-- item 65: a whole-column-verbatim segment (Gorgias
                       B11/B11a — no letter-spacing, so every run is
                       role='context') renders every run at full text
                       weight (frag-txt) instead of run.cls's ordinary
                       role-driven muting (frag-ctx) — see
                       Segment.wholeColumnVerbatim's doc comment. -->
                  <span class="line-text" lang={sourceLang}>{#each item.prose.runs as run, ri}{#if ri > 0 && run.space}{' '}{/if}<span class={seg.wholeColumnVerbatim ? 'frag-txt' : run.cls}>{#if run.incipit}<span class="frag-incipit">{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}</span>{:else}{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}{/if}</span>{/each}</span>
                </p>
                {/if}
              {:else}
                <!-- A section-split piece (Discourses' `sections` channel —
                     see splitGreekSections): cont-pieces beyond the first
                     get a `paraN`-disambiguated id suffix so they stay
                     unique in the DOM (still non-digit-terminal, so
                     citeOf's `-(\d+)$` line-citation match still excludes
                     them, exactly like an ordinary mid-line chapter-split
                     cont-line). The section number renders in the
                     piece's own .line-num gutter cell (user-select: none, same
                     exclusion-from-copy contract as every verse/Bekker gutter). -->
                                <!-- verse-line transposition seam note (Lucretius' DRN —
                     design memo §3.3): an auto-generated note rendered
                     inline at the citation-order-first line of a
                     transposed block, recording that the block is
                     transmitted elsewhere in the manuscript. -->
                {#if item.line.seamNote}<div class="seam-note">{item.line.seamNote}</div>{/if}
                <!-- A dk fragment's role='context' line (a synthetic
                     NEGATIVE n -- stage1_greek._parse_fragments) is never
                     a citation target: no id at all, so it can't leak into
                     a DOM id ("LB8--1"), the scroll-spy's `.greek-line[id]`
                     observation set, or a nearest-line snap (Sol review
                     nit (a)). A `letter` scheme's role='salutation' line
                     (Seneca's Epistulae, design note §B) is NOT this case
                     -- it is section 1's own real leading line (positive
                     n, clickable tokens), so it keeps an ordinary id;
                     only its CSS treatment (a quiet opening address,
                     .context's own muted precedent) differs. A role='heading'
                     line (REVIEW-CHECKLIST item 5, John's ruling) IS treated
                     like role='context' here -- a restored manuscript
                     book-division title is structural paratext, never a
                     citation target, so it gets no id either (and would
                     otherwise collide with its letter's role='salutation'
                     line, which shares the same n). -->
                <!-- Lined-source first-line inset: `item.line.indent` keeps
                     the source level while display caps it at four 1.25em
                     steps. This is a visual inset on THIS line's first
                     (only) rendered line, gutter untouched. When this line
                     also carries a carried fragment from a wrap on the
                     PREVIOUS line (`item.leadFragment`), the fragment is
                     part of this line's own text flow (painted first inside
                     `.line-text`), so the inset shifts the whole painted
                     line -- fragment included -- exactly as Schenkl prints
                     it. -->
                <div class="greek-line" id={(item.line.role === 'context' || item.line.role === 'heading') ? undefined : item.line.cont ? `L${seg.column}-${item.line.n}-c${item.line.paraN ?? ''}` : `L${seg.column}-${item.line.n}`} class:target={!item.line.cont && item.line.role !== 'context' && item.line.role !== 'heading' && targetId === `L${seg.column}-${item.line.n}`} class:cont={item.line.cont} class:sec-piece={item.line.paraN != null} class:context={item.line.role === 'context'} class:lacuna={item.line.role === 'lacuna'} class:salutation={item.line.role === 'salutation'} class:heading={item.line.role === 'heading'} class:verse={item.vIndent != null} class:verse-run-first={item.vFirst} class:verse-run-last={item.vLast}>
                  <!-- Lined-source only (Discourses, docs/lined-source-plan.md
                       Q3): a `sec`-carrying line shows its section number
                       here iff `secStart` (computed once in greekItems, in
                       document order) -- the line where that section's own
                       text begins, even a mid-word continuation (Q3.2). Every
                       other work's lines carry no `sec`, so this branch never
                       fires for them. -->
                  <span class="line-num">{item.line.paraN != null ? item.line.paraN : item.line.sec != null ? (item.secStart ? item.line.sec : '') : item.line.cont ? '' : (verseLine ? verseGutterNum(si) : showLineNum(item.line.n))}</span>
                  {#if item.line.role === 'lacuna'}
                    <!-- Editorial gap (design memo §3.2): rendered as a
                         styled placeholder, never the literal "* * *" the
                         print edition carries -- the line's own `text`/
                         `tokens` are always empty (see GreekLine.role's
                         doc comment), so there is nothing to click. -->
                    <span class="line-text lacuna-gap" lang={sourceLang} aria-label="editorial gap in the text" style:text-indent={item.vIndent == null ? linedIndent(item.line.indent) : undefined} style:--v-inset={item.vIndent != null ? verseInset(item.vIndent) : undefined}>⁂ lacuna ⁂</span>
                  {:else}
                    <!-- Lined-source only (Q2; wrapO deviation 2026-08-29,
                         §3): `item.leadFragment` (set when the PREVIOUS line
                         carried a wrap) prepends the carried parts list --
                         the wrapped word's remainder plus everything printed
                         after it -- before this line's own first part, each
                         part still bound to its own token; `item.line.wrap`/
                         `wrapO` (this line's own) repaints the WRAPPED token
                         (located by `wrapO`) as the truncated head + hyphen
                         via splitWrapLine. Both no-ops (parts pass through
                         unchanged) for every line without these fields. -->
                    <span class="line-text" lang={sourceLang} style:text-indent={item.vIndent == null ? linedIndent(item.line.indent) : undefined} style:--v-inset={item.vIndent != null ? verseInset(item.vIndent) : undefined}>{@render greekToks(lineParts(item, seg))}</span>
                  {/if}
                </div>
              {/if}
            {/each}
          {/snippet}
          {#if sectionRowSplit(seg) && trans !== 'compare'}
            <!-- Item 85 (John's live-review layout ruling): each DK numbered
                 section renders as its own row (Greek cell + English cell)
                 instead of the two columns flowing independently -- ordinary
                 CSS Grid already stretches both cells of a row to the taller
                 one and starts both at the row's top edge, so the first
                 line of a section's English sits level with the first line
                 of that section's Greek by construction (a shorter side's
                 own trailing gap is fine; nothing fakes the taller side's
                 height). `.frag-row-split` is ONE grid (reusing .seg-row's
                 own 2-column grid-template) holding every row-pair in
                 document order (`.frag-row` is `display:contents`, so its
                 two children -- not the wrapper -- are the actual grid
                 items); the heading pair (Greek title/frame + English
                 lead-in, row 0, never marker-labelled) is first, one pair
                 per ascending "(N)" section follows. Compare mode is out of
                 scope (a 3rd column per row is a follow-up, not asked for
                 here) -- sectionRowSplit(seg) && trans !== 'compare' gates
                 this branch; every other segment renders in the `{:else}`
                 below, byte-identical to before this feature. -->
            {@const rows = sectionRowsFor(seg, block)}
            <div class="seg-row frag-row-split" data-chapter={block.currentChapter}>
              {#each rows as row, ri}
                <div class="frag-row">
                  <!-- Fix round (Sol re-verify): explicit `grid-row`/
                       `grid-column` on every cell. `.frag-eng-card-bg`
                       below spans `grid-row: 1 / span {rows.length}` --
                       CSS Grid's `-1` line only resolves against EXPLICIT
                       rows, and this grid declares none (rows are pure
                       auto-placement), so the old `grid-row: 1 / -1` (in
                       global.css) had no explicit end line to resolve
                       against and could land the bg in whatever cell
                       auto-placement handed it, potentially displacing a
                       real English cell. Pinning every cell's own row/
                       column removes the ambiguity for both the cells and
                       the bg. -->
                  <div
                    class="greek-col"
                    data-column={seg.column}
                    lang={sourceLang}
                    style="grid-row: {ri + 1}; grid-column: 1"
                  >
                    {@render greekColumnItems(row.items, seg, si)}
                  </div>
                  <!-- English cell for this row. The per-passage translation
                       toggle (item 84) now renders on the segment's `.seg-ref`
                       line above, not in this cell (translator-picker
                       alignment fix) -- frag-row-cell-first (row 0 only)
                       drops this cell's top padding so its first line still
                       starts flush with the Greek's, now that nothing else
                       occupies that space. This segment's own imported
                       chapter title (never present for a dk fragment/
                       testimonium, but kept for parity) still renders in the
                       HEADING row's cell (row 0). The visible translation
                       credit and the DK source-citation expansion render
                       once, in the LAST row, same "once per segment" posture
                       the pre-split rendering used (there `bi === blocks.length
                       - 1`; these segments always have exactly one block, so
                       "last row" is this branch's equivalent). data-eng-credit
                       stays on every row (not just the last) so the
                       copy-with-citation path resolves it from whichever row
                       the reader selected. -->
                  <div
                    class="english-col frag-row-cell"
                    class:frag-row-cell-first={ri === 0}
                    data-trans={segTransId}
                    data-eng-credit={engCreditFor(segTransId, seg)}
                    style="grid-row: {ri + 1}; grid-column: 2"
                  >
                    {#if ri === 0}
                      {#if seg.english?.title && segTransId === engSlot?.id && (busse || verseLine)}
                        <div class="overlay-chapter-title eng-chapter-title">{seg.english.title}</div>
                      {/if}
                    {/if}
                    {@render transFlow({ chapter: null, bekker: '', lines: [], flow: row.flow, oflows: row.oflows, otables: {}, sidenotes: [], figs: [] }, segTransId, seg.kind)}
                    {#if ri === rows.length - 1}
                      {#if seg.english?.credit && segTransId === engSlot?.id}
                        {@render translationCredit(seg.english.credit)}
                      {/if}
                      {#each citationByBlock[bi] ?? [] as run}
                        {#if run.length}
                        <div class="expanded-citation">
                          {#each run as entry, i}
                            {#if i > 0}<span class="expanded-citation-sep">; </span>{/if}
                            {#if entry.resolution === 'direct' || entry.resolution === 'dash'}
                              <span class="expanded-citation-entry">{#if entry.authorDisplay}{`${entry.authorDisplay}, `}{/if}{#if entry.work?.italic}<em>{entry.work.title}</em>{:else}{entry.work?.title}{/if}{entry.locus ? ` ${entry.locus}` : ''}{entry.apparatus ? ` ${entry.apparatus}` : ''}</span>{#if entry.note}{' '}<span class="context-english-credit">{entry.note}</span>{/if}
                            {:else}
                              <span class="expanded-citation-entry expanded-citation-verbatim">{entry.verbatim}</span>
                            {/if}
                          {/each}
                        </div>
                        {/if}
                      {/each}
                    {/if}
                  </div>
                </div>
              {/each}
              <div
                class="frag-eng-card-bg"
                aria-hidden="true"
                style="grid-row: 1 / span {rows.length}; grid-column: 2"
              ></div>
            </div>
          {:else}
          <!-- verse-line, no English (fix round, re-review finding 3): this
               segment renders no english-col at all (see the english-col
               `{#if !verseLine || seg.english}` guard below) — without this
               class the row still carries every other view/compare rule's
               grid-template-columns (2 or 3 tracks), leaving the sole
               greek-col squeezed into the first track with empty tracks
               beside it. verse-untranslated forces a single track. -->
          <div
            class="seg-row"
            class:verse-untranslated={verseLine && !seg.english}
            data-chapter={block.currentChapter}
          >
            <!-- Greek column. data-column backs the copy-with-citation
                 fallback (fix round, finding 2): a marker-split paragraph
                 after the first carries no id of its own (only the column's
                 FIRST flow anchors L{column}), so greekCiteForRange resolves
                 a selection there via the owning column instead. -->
            <div class="greek-col" data-column={seg.column} lang={sourceLang}>
              {#if spacerTitle}<div class="overlay-chapter-title overlay-chapter-title-spacer" aria-hidden="true">{spacerTitle}</div>{/if}
              {#each greekItems(block.lines, seg.column, contextSectionMarkerNumbers(seg), seg.sectionParagraphSplit, seg.wholeColumnVerbatim ? undefined : seg.witnesses) as item}
                {#if item.kind === 'table'}
                  <!-- Greek inline table (the TLG ⎪ column square, e.g. De Int 22a). -->
                  <table class="greek-table"><tbody>
                    {#each item.rows as row}
                      <tr id={`L${seg.column}-${row.n}`} class:target={targetId === `L${seg.column}-${row.n}`}>
                        <td class="line-num">{showLineNum(row.n)}</td>
                        {#each (row.cells ?? []) as cell}
                          <td class="line-text" lang={sourceLang}>{@render greekToks(cellParts(cell))}</td>
                        {/each}
                      </tr>
                    {/each}
                  </tbody></table>
                {:else if item.kind === 'source-head'}
                  <!-- DK source-citation head (prose-flow post-draft ruling):
                       pure Latin/ASCII apparatus citation on its own hanging
                       small-caps line, muted — DK's own page grammar. -->
                  <div class="frag-source-head" lang={sourceLang}>{@render greekToks(lineRenderParts(item.line.text, item.line.tokens, speakerEvents(seg, item.line)))}</div>
                {:else if item.kind === 'witness'}
                  <!-- DK apparatus witness row (dk_witness.py's split_witnesses,
                       Segment.witnesses): one row per ancient source instead of
                       one undifferentiated context blob. No id (never a
                       citation target, same as any other context content). The
                       witness's text carries no tokens — dk_witness.py returns
                       flattened text, not a token-offset mapping — so it
                       renders plain, through greekToks/lineRenderParts only for
                       byte-identical whitespace handling with every other row. -->
                  <p class="greek-line frag-flow frag-witness">
                    <span class="line-num"></span>
                    <span class="line-text" lang={sourceLang}><span class="frag-ctx">{#if item.witness.source}<span class="frag-witness-source">{item.witness.source}</span>{' '}{/if}{@render greekToks(lineRenderParts(item.witness.text, []))}</span></span>
                  </p>
                {:else if item.kind === 'flow'}
                  <!-- DK prose-flow (docs/prose-flow-design.md §1): one flowing
                       paragraph of inline role-runs. Prose columns keep
                       class="greek-line" + column-only id (`L{column}`, never
                       run n) so scroll-spy observes at column granularity.
                       Verse-frame flows (context around lineated quote) set
                       anchor=false — no id; quote lines carry L{col}-{n}. -->
                  {#if bookSectionFlow}
                    <!-- item 23 unification: chapter-level book-section works
                         (Marcus Aurelius, Discourses, Diogenes Laertius,
                         Cicero's book-section works) flow every run of the
                         segment into ONE paragraph instead of DK's
                         (possibly marker-split) grouping -- sectionMarker
                         never fires here (no contextEnglish declared for
                         these works). Each run keeps the EXACT anchor id
                         the old per-line block rendering gave it
                         (flowRunId) -- see that function's own doc comment
                         for exactly which mechanisms (#-target, scroll-spy,
                         copy-citation) actually resolve per run vs per
                         paragraph. A run whose own line carries a Schenkl
                         `sections` subsection number (paraN) gets a small
                         gutter marker (.greek-para-n-flow, absolute-
                         positioned like the English's own .bk-num Bekker
                         ticks -- no row break) instead of the old block-
                         above-the-paragraph treatment, UNLESS it collides
                         with the marker before it (paraMarkerIsGutter, fix
                         round finding 3), in which case it falls back to a
                         plain inline ".para-n". A plain multi-line segment
                         with no such channel (ordinary Marcus/DL/Cicero
                         prose) shows no marker at all.
                         Fix round finding 1 (Sol review): run.cls
                         ('frag-txt') is DK's own role-distinction class and
                         carries DK's font-weight:500 -- book-section has no
                         role distinction of its own (never role='context'),
                         so its source text must render at the SAME weight
                         the pre-flow per-line block rendering used (no
                         class at all, i.e. normal weight). The scoping
                         class "bs-flow" (below, and on .greek-line.frag-flow
                         .line-text's position:relative in global.css --
                         finding 6) neutralizes frag-txt's weight for this
                         branch only; DK's own frag-flow paragraphs are
                         untouched. -->
                    {@const firstId = flowRunId(item.prose.runs[0]!.line as RLine, seg.column)}
                    {@const firstCont = !!(item.prose.runs[0]!.line as RLine).cont}
                    {@const gutterFlags = paraMarkerIsGutter(item.prose.runs.map((r) => ({ paraN: (r.line as RLine).paraN, text: r.line.text })))}
                    <p
                      class="greek-line frag-flow bs-flow"
                      id={item.anchor ? firstId : undefined}
                      class:target={item.anchor && !firstCont && targetId === firstId}
                    >
                      <span class="line-num"></span>
                      <span class="line-text" lang={sourceLang}>{#if sectionFlow}<span class="sect-tick-inline" data-n={seg.column} aria-hidden="true"></span>{/if}{#each item.prose.runs as run, ri}{@const rline = run.line as RLine}{@const rid = flowRunId(rline, seg.column)}{#if ri > 0 && run.space}{' '}{/if}{#if rline.paraN != null}<span class="para-n" class:greek-para-n-flow={gutterFlags[ri]} aria-hidden="true" data-n={rline.paraN}></span>{/if}<span id={ri > 0 ? rid : undefined} class:target={ri > 0 && !rline.cont && targetId === rid} class={run.cls}>{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}</span>{/each}</span>
                    </p>
                  {:else}
                  <!-- DK inline "(NN)" section marker (John's thales/testimonia
                       A1 note: the Greek context block should paragraph-break
                       in parallel with the English's own per-section split) --
                       same label treatment as the source-passage English's
                       .context-english-section-marker, so the two columns
                       read as visually parallel. Absent for a paragraph with
                       no leading marker (e.g. a work with no such markers at
                       all keeps the single unmarked paragraph it always had). -->
                  {#if item.prose.sectionMarker}<div class="greek-context-section-marker">({item.prose.sectionMarker})</div>{/if}
                  <p
                    class="greek-line frag-flow"
                    id={item.anchor ? `L${seg.column}` : undefined}
                    class:target={item.anchor && targetId === `L${seg.column}`}
                    data-incipit={item.prose.incipit ? '' : undefined}
                  >
                    <span class="line-num"></span>
                    <!-- item 65: a whole-column-verbatim segment (Gorgias
                         B11/B11a — no letter-spacing, so every run is
                         role='context') renders every run at full text
                         weight (frag-txt) instead of run.cls's ordinary
                         role-driven muting (frag-ctx) — see
                         Segment.wholeColumnVerbatim's doc comment. -->
                    <span class="line-text" lang={sourceLang}>{#each item.prose.runs as run, ri}{#if ri > 0 && run.space}{' '}{/if}<span class={seg.wholeColumnVerbatim ? 'frag-txt' : run.cls}>{#if run.incipit}<span class="frag-incipit">{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}</span>{:else}{@render greekToks(lineRenderParts(run.line.text, run.line.tokens, speakerEvents(seg, run.line as RLine)))}{/if}</span>{/each}</span>
                  </p>
                  {/if}
                {:else}
                  <!-- A section-split piece (Discourses' `sections` channel —
                       see splitGreekSections): cont-pieces beyond the first
                       get a `paraN`-disambiguated id suffix so they stay
                       unique in the DOM (still non-digit-terminal, so
                       citeOf's `-(\d+)$` line-citation match still excludes
                       them, exactly like an ordinary mid-line chapter-split
                       cont-line). The section number renders in the
                       piece's own .line-num gutter cell (user-select: none, same
                       exclusion-from-copy contract as every verse/Bekker gutter). -->
                                    <!-- verse-line transposition seam note (Lucretius' DRN —
                       design memo §3.3): an auto-generated note rendered
                       inline at the citation-order-first line of a
                       transposed block, recording that the block is
                       transmitted elsewhere in the manuscript. -->
                  {#if item.line.seamNote}<div class="seam-note">{item.line.seamNote}</div>{/if}
                  <!-- A dk fragment's role='context' line (a synthetic
                       NEGATIVE n -- stage1_greek._parse_fragments) is never
                       a citation target: no id at all, so it can't leak into
                       a DOM id ("LB8--1"), the scroll-spy's `.greek-line[id]`
                       observation set, or a nearest-line snap (Sol review
                       nit (a)). A `letter` scheme's role='salutation' line
                       (Seneca's Epistulae, design note §B) is NOT this case
                       -- it is section 1's own real leading line (positive
                       n, clickable tokens), so it keeps an ordinary id;
                       only its CSS treatment (a quiet opening address,
                       .context's own muted precedent) differs. A
                       role='heading' line (REVIEW-CHECKLIST item 5, John's
                       ruling) IS treated like role='context' here -- a
                       restored manuscript book-division title is structural
                       paratext, never a citation target, so it gets no id
                       either (and would otherwise collide with its letter's
                       role='salutation' line, which shares the same n). -->
                  <div class="greek-line" id={(item.line.role === 'context' || item.line.role === 'heading') ? undefined : item.line.cont ? `L${seg.column}-${item.line.n}-c${item.line.paraN ?? ''}` : `L${seg.column}-${item.line.n}`} class:target={!item.line.cont && item.line.role !== 'context' && item.line.role !== 'heading' && targetId === `L${seg.column}-${item.line.n}`} class:cont={item.line.cont} class:sec-piece={item.line.paraN != null} class:context={item.line.role === 'context'} class:lacuna={item.line.role === 'lacuna'} class:salutation={item.line.role === 'salutation'} class:heading={item.line.role === 'heading'} class:verse={item.vIndent != null} class:verse-run-first={item.vFirst} class:verse-run-last={item.vLast}>
                    <!-- Lined-source only (Discourses, docs/lined-source-plan.md
                         Q3): a `sec`-carrying line shows its section number
                         here iff `secStart` (computed once in greekItems, in
                         document order) -- the line where that section's own
                         text begins, even a mid-word continuation (Q3.2).
                         Every other work's lines carry no `sec`, so this
                         branch never fires for them. -->
                    <span class="line-num">{item.line.paraN != null ? item.line.paraN : item.line.sec != null ? (item.secStart ? item.line.sec : '') : item.line.cont ? '' : (verseLine ? verseGutterNum(si) : showLineNum(item.line.n))}</span>
                    {#if item.line.role === 'lacuna'}
                      <!-- Editorial gap (design memo §3.2): rendered as a
                           styled placeholder, never the literal "* * *" the
                           print edition carries -- the line's own `text`/
                           `tokens` are always empty (see GreekLine.role's
                           doc comment), so there is nothing to click. -->
                      <span class="line-text lacuna-gap" lang={sourceLang} aria-label="editorial gap in the text" style:text-indent={item.vIndent == null ? linedIndent(item.line.indent) : undefined} style:--v-inset={item.vIndent != null ? verseInset(item.vIndent) : undefined}>⁂ lacuna ⁂</span>
                    {:else}
                      <!-- Lined-source only (Q2; wrapO deviation 2026-08-29,
                           §3): `item.leadFragment` (set when the PREVIOUS
                           line carried a wrap) prepends the carried parts
                           list -- the wrapped word's remainder plus
                           everything printed after it -- before this line's
                           own first part, each part still bound to its own
                           token; `item.line.wrap`/`wrapO` (this line's own)
                           repaints the WRAPPED token (located by `wrapO`) as
                           the truncated head + hyphen via splitWrapLine.
                           Both no-ops (parts pass through unchanged) for every line
                           without these fields. -->
                      <span class="line-text" lang={sourceLang} style:text-indent={item.vIndent == null ? linedIndent(item.line.indent) : undefined} style:--v-inset={item.vIndent != null ? verseInset(item.vIndent) : undefined}>{@render greekToks(lineParts(item, seg))}</span>
                    {/if}
                  </div>
                {/if}
              {/each}
            </div>

            <!-- English column: the selected translation (single view), or the
                 left compare column. Prose laid out beside its Bekker-line
                 gutter — real anchors full weight, estimates lighter/italic.
                 verse-line: only a segment that actually carries English
                 (Munro's declared multi-line spread) gets this column at
                 all — every other line-segment renders no english-col, so
                 the continuous verse block never carries an empty cell. -->
            {#if !verseLine || seg.english}
            <!-- data-eng-credit backs the copy-with-citation path's English
                 side (finding 2, Sol review): handleCopy/clickCopyBtn walk up
                 to this attribute for an English-only selection, same shape
                 as the Greek column's data-column fallback above. Absent
                 (undefined) for an uncredited passage — nothing to copy.
                 Item 84: gated on the DISPLAYED chunk being the primary slot
                 (segTransId, not the bare work-level `trans`) — after a
                 per-passage switch to an alternate, this segment's own
                 seg.english?.credit must never leak onto that alternate's
                 copy (overlay translations carry no per-chunk credit of
                 their own, so an alternate's copy simply carries none). -->
            <div class="english-col" data-trans={trans === 'compare' ? compareLeft : segTransId} data-eng-credit={engCreditFor(trans === 'compare' ? compareLeft : segTransId, seg)}>
              <!-- Fix round, finding 3 (Sol xhigh review): this label used
                   to read the compare slot's work-level `short` unconditionally,
                   so a segment whose primary chunk carries a per-passage
                   credit (the Parnassos-style swap) still labeled the column
                   with the WORK's usual translator ("Freeman") even though
                   the text on screen is someone else's — the same mislabel
                   item 84's segTransToggle already fixed for the non-compare
                   picker. Same rule here: when this column shows the
                   primary slot AND that chunk carries a credit, the label is
                   the credited translator's own surname. -->
              {#if trans === 'compare'}
                {@const leftLabel = compareLeft === engSlot?.id && seg.english?.credit
                  ? (surnameFromCredit(seg.english.credit.translator) || (transById(compareLeft)?.short ?? 'English'))
                  : compareLeft === engSlot?.id && seg.english?.summary
                    ? summaryTranslationLabel(transById(compareLeft)?.short ?? 'English')
                    : (transById(compareLeft)?.short ?? 'English')}
                <div class="col-label">{leftLabel}</div>
              {/if}
              <!-- John's review, 2026-07-28: the same teal accent-line +
                   tinted-background card he liked on the source-passage
                   English block (.context-english below) now wraps the
                   segment's OWN translation content too, for a dk-scheme
                   (fragment/testimonia) work only — book-section, turn-flow
                   and verse-line works are untouched (his ask named
                   fragment translations specifically). `.frag-eng-card`
                   reuses .context-english's exact tokens (same --accent-light
                   border, same tinted background, same padding rhythm) —
                   see the CSS comment beside .context-english in global.css.
                   Wraps only the translation content (chapter title through
                   the expanded-citation run below); the .context-english
                   block further down is a SIBLING, outside this div, so a
                   segment carrying both never gets a card nested inside an
                   identical card — .context-english keeps the exact look it
                   had before this change. Item 84's per-passage translation
                   picker used to render as this card's first child; it now
                   renders on the segment's `.seg-ref` line instead
                   (translator-picker alignment fix), so the card's own top
                   margin/padding is zeroed in global.css -- nothing occupies
                   that space here anymore. -->
              <div class:frag-eng-card={cscheme.id === 'dk'}>
              <!-- A chapter's own descriptive heading (Discourses' Oldfather
                   subtitle — see EnglishChunk.title). Chunk-level, not
                   chapterStarts-driven (book-section works have no
                   chapterStarts at all — chapter = segment, 1:1), and shown
                   only when the PRIMARY translation is the one on screen
                   here (Oldfather carries it; Long, the secondary, never
                   does). CSS hides the whole column in Greek-only view, so
                   no extra `view` check is needed. Suppressed here whenever
                   the segment's own `.seg-ref` header ALSO renders this
                   title (`!busse && !verseLine`, the header's own gate —
                   Discourses and de-finibus both hit this, John's ruling
                   2026-08-28: "keep the header, lose it in the english").
                   DRN (verseLine, no `.seg-ref` header at all) is the one
                   work where this is the ONLY place the title shows, so it
                   stays. -->
              {#if seg.english?.title && (trans === 'compare' ? compareLeft : segTransId) === engSlot?.id && (busse || verseLine)}
                <div class="overlay-chapter-title eng-chapter-title">{seg.english.title}</div>
              {/if}
              {#if isUnpairedDialogue(seg)}
                <!-- A dialogue segment whose turns did not reconcile (and a
                     narrated work's said-bearing chunk): the English renders as
                     a STACK of turn paragraphs — each speech its own block with
                     its small-caps lead-in (em-dash for an unattributed turn),
                     the leading pre-turn continuation an unlabeled block. Block
                     boundaries, not inline splices, so a label can never butt
                     against the previous sentence. -->
                <div class="overlay-prose turn-eng turn-stack">
                  {#each englishTurnBlocks(seg) as b}
                    <p class="turn-para">{#if !b.lead}{#if b.display}<span class="speaker">{b.display}</span>{:else}<span class="speaker speaker-dash">—</span>{/if}{/if}<!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html highlightEng(b.text)}</p>
                  {/each}
                </div>
              {:else}
              {@render transFlow(block, trans === 'compare' ? compareLeft : segTransId, seg.kind, sectionFlow ? seg.column : undefined)}
              {/if}
              <!-- Per-passage translation credit (see EnglishChunk.credit):
                   a passage whose English comes from a different translation
                   than the work's own primary one names its translator,
                   edition and licence here, on the reading page itself --
                   the control bar's work-level credit names the primary
                   translation, so without this the passage would read as
                   that translator's work. Same treatment as the source-
                   passage English's own credit line, so the page reads
                   consistently. Shown once per segment (last block only),
                   and only when the PRIMARY translation is the one on
                   screen in this column -- the credit belongs to that
                   chunk's text, not to an alternate translation's overlay
                   (item 84: segTransId, so a per-passage switch away from
                   the primary hides this too). -->
              {#if bi === blocks.length - 1 && seg.english?.credit && (trans === 'compare' ? compareLeft : segTransId) === engSlot?.id}
                {@render translationCredit(seg.english.credit)}
              {/if}
              <!-- DK source-citation expansion (docs/citation-expansion-
                   wiring-design.md): the Hackett-style English form of this
                   column's DK apparatus head(s) -- the English counterpart to
                   the small-caps Greek `.frag-source-head` line. Rendered in
                   the primary English column only, never the compare column.
                   One line per RUN (fix round finding 2/4): `citationByBlock`
                   groups entries by the distinct context run they came from
                   and places each run's line in the block where that run's
                   head actually sits (a multi-block/multi-run segment no
                   longer dumps every run onto the last block, and two
                   unrelated runs never merge into one false attribution). A
                   `direct` entry -- and a `dash` entry, identically (rule E,
                   John 2026-09-24) -- prints "Author, Work locus [apparatus]" with
                   the work title italic only when `work.italic` says so
                   (never baked markup) and any Doxographi/editor apparatus
                   ref kept verbatim, unexpanded; a `verbatim` entry --
                   unresolved or dash-continuation -- prints the head exactly
                   as DK printed it, honest, no invented author or title, and
                   never italicized just for being verbatim. Multiple SOURCES
                   within one run join with "; ", as DK's own semicolon-
                   separated heads do. -->
              {#each citationByBlock[bi] as run}
                {#if run.length}
                <div class="expanded-citation">
                  {#each run as entry, i}
                    {#if i > 0}<span class="expanded-citation-sep">; </span>{/if}
                    {#if entry.resolution === 'direct' || entry.resolution === 'dash'}
                      <span class="expanded-citation-entry">{#if entry.authorDisplay}{`${entry.authorDisplay}, `}{/if}{#if entry.work?.italic}<em>{entry.work.title}</em>{:else}{entry.work?.title}{/if}{entry.locus ? ` ${entry.locus}` : ''}{entry.apparatus ? ` ${entry.apparatus}` : ''}</span>{#if entry.note}{' '}<span class="context-english-credit">{entry.note}</span>{/if}
                    {:else}
                      <span class="expanded-citation-entry expanded-citation-verbatim">{entry.verbatim}</span>
                    {/if}
                  {/each}
                </div>
                {/if}
              {/each}
              </div>
              <!-- Source-passage English (docs/source-passage-english-scoping.md):
                   the quoting source author's own English for this column's
                   context run(s), by locus pointer -- present only for a
                   segment the work's sources/<work>/context-english.json
                   declares. Lives in the ENGLISH COLUMN itself, appended
                   after whichever translation is on screen here (same
                   posture regardless of which translation is picked --
                   design decision, task follow-up to the docs memo: the
                   source passage belongs with its testimonium context, not
                   any one translation choice) -- reuses the standard
                   Greek/English parallel layout rather than a separate
                   full-width block. Rendered once per segment (on the last
                   block only, so a chaptered segment doesn't repeat it),
                   after its column's ordinary rows. NOT duplicated into the
                   right compare column. Bug fix (John 2026-07-24): used to
                   render as a full-width block below the Greek column when
                   the work had no primary translation, because such a work
                   forced view='greek' and hid the English column outright;
                   `hasEnglish` now counts contextEnglish too, so view is no
                   longer force-greek and the standard column-hiding CSS
                   applies exactly as it does for any other translation. -->
              {#if bi === blocks.length - 1 && seg.contextEnglish?.length}
                {#each seg.contextEnglish as span, spanIdx}
                  {@const spanKey = `${seg.id}:${spanIdx}`}
                  {@const selectedAltId = span.alts?.length ? (contextEnglishAlt[spanKey] ?? null) : null}
                  {@const activeAlt = selectedAltId ? span.alts?.find((a) => a.id === selectedAltId) : undefined}
                  {@const activeCredit = activeAlt ? activeAlt.translationCredit : span.translationCredit}
                  <!-- Item 82 (REVIEW-CHECKLIST): data-eng-credit lives on this
                       wrapping div, closer than the ancestor .english-col's own
                       attribute (that one names the SEGMENT's own primary
                       translation credit, not this source passage's) -- so a
                       copy of context-english text always carries the credit
                       for whichever translation (primary or alt) is on screen
                       here, not the wrong ancestor's. Fix round, finding 5
                       (Sol xhigh review): this used to be set only for an
                       alt-BEARING span, so an alt-free span's own
                       translationCredit (every span carries one when
                       status==='translated', alts or not) never made it onto
                       the copy path — set whenever the span has a credit to
                       show, alts or not. -->
                  <div
                    class="context-english"
                    data-eng-credit={span.status === 'translated' && activeCredit
                      ? `Source passage: ${span.sourceAuthor}, ${span.sourceWork} ${span.locus.replace('-', '–')} (tr. ${activeCredit}).`
                      : undefined}
                  >
                    {#if span.status === 'translated'}
                      {#if span.alts?.length}
                        <!-- Plain-text toggle (not a <select> -- that pattern is
                             reserved for the work-level picker): primary label
                             first, then each alt, active one bold/underlined.
                             Page-local only -- see contextEnglishAlt above. -->
                        <div class="context-english-alt-toggle" role="group" aria-label="Translation">
                          <button
                            type="button"
                            class="context-english-alt-btn"
                            class:active={!selectedAltId}
                            aria-pressed={!selectedAltId}
                            on:click={() => selectContextEnglishAlt(spanKey, null)}
                          >{contextEnglishPrimaryLabel(span)}</button>
                          {#each span.alts as alt}
                            <span class="context-english-alt-sep">·</span>
                            <button
                              type="button"
                              class="context-english-alt-btn"
                              class:active={selectedAltId === alt.id}
                              aria-pressed={selectedAltId === alt.id}
                              on:click={() => selectContextEnglishAlt(spanKey, alt.id)}
                            >{alt.label}</button>
                          {/each}
                        </div>
                      {/if}
                      {#if activeAlt}
                        <!-- One entry per locus of the span's own range, in
                             span order (data contract) -- a gap section (no
                             `text`) gets the honest marker, never a blank
                             paragraph. -->
                        {#each activeAlt.sections as sec}
                          {#if activeAlt.sections.length > 1}
                            <div class="context-english-section-marker">{sec.locus}</div>
                          {/if}
                          {#if sec.text}
                            <p class="context-english-text">{sec.text}</p>
                          {:else}
                            <p class="context-english-text context-english-gap">No {activeAlt.label} translation for this section.</p>
                          {/if}
                        {/each}
                        <div class="context-english-credit">Source passage: {span.sourceAuthor}, {span.sourceWork} {span.locus.replace('-', '–')} (tr. {activeAlt.translationCredit}).</div>
                      {:else}
                        <!-- A multi-section range (span.sectionLoci) carries one
                             resolved paragraph per source section -- mark each with
                             its own locus, same treatment as the work's own .seg-ref
                             column reference, so a many-paragraph range (e.g. 19
                             sections) stays navigable instead of reading as one
                             undifferentiated block. A single-section span carries no
                             sectionLoci (its one paragraph is already named by the
                             credit line below). Item 83: span.emphasis (primary
                             translation only -- an activeAlt never carries it, see
                             the branch above) bolds the DK-excerpt words within each
                             paragraph; a span with no emphasis renders one plain
                             segment per paragraph, byte-identical to before. -->
                        {@const paragraphs = contextEnglishParagraphs(span.text ?? '', span.emphasis)}
                        {#each paragraphs as p, i}
                          {#if span.sectionLoci?.[i]}
                            <div class="context-english-section-marker">{span.sectionLoci[i]}</div>
                          {/if}
                          <p class="context-english-text">{#each p.segments as s}{#if s.bold}<strong class="context-english-emphasis">{s.text}</strong>{:else}{s.text}{/if}{/each}</p>
                        {/each}
                        <div class="context-english-credit">Source passage: {span.sourceAuthor}, {span.sourceWork} {span.locus.replace('-', '–')} (tr. {span.translationCredit}).</div>
                      {/if}
                    {:else}
                      <div class="context-english-desert">No public-domain English translation of this source passage exists yet. Only the Greek is shown.</div>
                    {/if}
                  </div>
                {/each}
              {/if}
              <!-- Inline diagrams ([[figN]] markers), e.g. the Tree of Porphyry. -->
              {#if busse && view !== 'greek' && block.figs.length}
                {#each block.figs as fig}
                  {#if figuresData[String(fig)]}<!-- eslint-disable-next-line svelte/no-at-html-tags -->{@html figuresData[String(fig)]}{/if}
                {/each}
              {/if}
            </div>
            {/if}

            <!-- Right compare column: the second chosen translation beside the
                 first (hidden in Greek-only). verse-line: same non-null
                 guard as the english-col above (finding 5, Sol review) — a
                 verse-line segment with no English never renders a compare
                 column either, so a 3-track grid (Greek + two empty English
                 tracks) never appears for a line with no English at all. -->
            {#if trans === 'compare' && view !== 'greek' && (!verseLine || seg.english)}
              <!-- Fix round, finding 3 (Sol xhigh review): same surname
                   override as the left column above — the credited
                   translator's own surname wins over the slot's
                   work-level `short` whenever this column shows the
                   credited primary chunk. -->
              {@const rightLabel = compareRight === engSlot?.id && seg.english?.credit
                  ? (surnameFromCredit(seg.english.credit.translator) || (transById(compareRight)?.short ?? ''))
                  : compareRight === engSlot?.id && seg.english?.summary
                    ? summaryTranslationLabel(transById(compareRight)?.short ?? '')
                    : (transById(compareRight)?.short ?? '')}
              <!-- Same data-eng-credit fallback as the primary english-col
                   above: the credited primary chunk's text travels into this
                   compare column too (see the translationCredit render just
                   below), so the copy path must find its credit here too.
                   Fix round, finding 2 (Sol xhigh review): this used to set
                   the attribute whenever `seg.english?.credit` existed, with
                   no check that the credited PRIMARY chunk is actually the
                   one shown in this column — so switching the right column
                   to an alternate translation left the primary's credit
                   attached to that alternate's (uncredited) text. Gated on
                   compareRight === engSlot?.id, the same condition the
                   visible credit below already uses. -->
              <div class="overlay-col" data-trans={compareRight} data-eng-credit={engCreditFor(compareRight, seg)}>
                <div class="col-label">{rightLabel}</div>
                {#if seg.english?.title && compareRight === engSlot?.id && (busse || verseLine)}
                  <div class="overlay-chapter-title eng-chapter-title">{seg.english.title}</div>
                {/if}
                {@render transFlow(block, compareRight, seg.kind)}
                <!-- The primary chunk's own per-passage credit travels with
                     its text into the right compare column too: a licensed
                     translation may never render uncredited, whichever
                     column the reader put it in. -->
                {#if bi === blocks.length - 1 && seg.english?.credit && compareRight === engSlot?.id}
                  {@render translationCredit(seg.english.credit)}
                {/if}
              </div>
            {/if}

            <!-- Analytical sidenotes (Owen's marginal notes), floated into a
                 right rail on desktop; on mobile they fall inline below the
                 English (hidden in Greek-only view). -->
            {#if busse && view !== 'greek' && block.sidenotes.length}
              <aside class="sidenote-rail">
                {#each block.sidenotes as sn}
                  {#if sidenotesData[String(sn)]}<p class="sidenote">{sidenotesData[String(sn)]}</p>{/if}
                {/each}
              </aside>
            {/if}
          </div>
          {/if}
        {/each}
      </div>
    {/each}
    {/if}
  </div>
{/if}

<aside class="settings-sidebar" class:open={settingsOpen} aria-label="Reader settings" aria-hidden={!settingsOpen} inert={!settingsOpen} bind:this={settingsEl} on:keydown={onSettingsKey}>
  <div class="settings-head">
    <span class="settings-title">Settings</span>
    <button type="button" class="settings-close" on:click={closeSettings} aria-label="Close settings">×</button>
  </div>
  <div class="settings-body">
    <!-- Mobile-only: on desktop the view toggle and print control live in the
         reader header (see .settings-mobile-only in global.css). -->
    <div class="settings-section settings-mobile-only">
      <div class="settings-section-label">View</div>
      {@render viewToggle()}
    </div>
    {#if translations.length > 1}
      <!-- Mobile-only: on desktop the picker sits beside the view toggle in the
           header (see .settings-trans in global.css). -->
      <div class="settings-section settings-trans">
        <div class="settings-section-label">Translation</div>
        <!-- svelte-ignore a11y-label-has-associated-control -->
        <label>
          <select class="settings-select" value={pickValue} on:change={onPick} aria-label="English translation">
            {#each translations as t}
              <option value={t.id}>{t.name}</option>
            {/each}
          </select>
        </label>
      </div>
    {/if}
    {#if canCompare}
      <!-- Mode lives HERE, not in the picker: the dropdowns choose WHICH
           translation, this chooses single vs side-by-side comparison. -->
      <div class="settings-section">
        <div class="settings-section-label">Translations</div>
        <label class="settings-mode-row">
          <input
            type="radio"
            name="trans-mode"
            checked={trans !== 'compare'}
            on:change={() => setTrans(lastSingle)}
          />
          <span>Single translation</span>
        </label>
        <label class="settings-mode-row">
          <input
            type="radio"
            name="trans-mode"
            checked={trans === 'compare'}
            on:change={() => setTrans('compare')}
          />
          <span>Compare two translations</span>
        </label>
      </div>
    {/if}
    {#if canCompare && trans === 'compare'}
      <!-- Compare pair: which two translations sit side by side. -->
      <div class="settings-section">
        <div class="settings-section-label">Compare</div>
        <!-- svelte-ignore a11y-label-has-associated-control -->
        <label class="settings-compare-row">
          <span class="settings-compare-side">Left</span>
          <select class="settings-select" bind:value={compareLeft} on:change={pickCompareLeft} aria-label="Compare left translation">
            {#each translations as t}
              <option value={t.id} disabled={t.id === compareRight}>{t.name}</option>
            {/each}
          </select>
        </label>
        <!-- svelte-ignore a11y-label-has-associated-control -->
        <label class="settings-compare-row">
          <span class="settings-compare-side">Right</span>
          <select class="settings-select" bind:value={compareRight} on:change={pickCompareRight} aria-label="Compare right translation">
            {#each translations as t}
              <option value={t.id} disabled={t.id === compareLeft}>{t.name}</option>
            {/each}
          </select>
        </label>
      </div>
    {/if}

    <div class="settings-section settings-mobile-only">
      <div class="settings-section-label">Print</div>
      {@render printControl()}
    </div>

    <div class="settings-section">
      <div class="settings-section-label">Text size</div>
      <label class="settings-slider">
        <div class="settings-slider-row">
          <span class="settings-slider-name">Size</span>
          <span class="settings-slider-val">{Math.round(fsScale * 100)}%</span>
        </div>
        <input type="range" min="0.75" max="1.4" step="0.05" bind:value={fsScale} on:change={saveFs} aria-label="Text size" />
      </label>
    </div>

    <div class="settings-section">
      <div class="settings-section-label">Line spacing</div>
      <label class="settings-slider">
        <div class="settings-slider-row">
          <span class="settings-slider-name">Spacing</span>
          <span class="settings-slider-val">{Math.round(lhScale * 100)}%</span>
        </div>
        <input type="range" min="0.8" max="1.4" step="0.05" bind:value={lhScale} on:change={saveLh} aria-label="Line spacing" />
      </label>
    </div>

    <div class="settings-section">
      <div class="settings-section-label">Column width</div>
      <label class="settings-slider">
        <div class="settings-slider-row">
          <span class="settings-slider-name">Width</span>
          <span class="settings-slider-val">{Math.round(colScale * 100)}%</span>
        </div>
        <input type="range" min="0.75" max="1.3" step="0.05" bind:value={colScale} on:change={saveColw} aria-label="Column width" />
      </label>
    </div>

    {#if spkSlots.size > 1}
    <div class="settings-section">
      <div class="settings-section-label">Speakers</div>
      <label class="settings-check-row">
        <span class="settings-check-name">
          Color speaker names
          <span class="settings-check-hint">A distinct hue per speaker</span>
        </span>
        <span class="settings-pill">
          <input type="checkbox" bind:checked={spkColor} on:change={saveSpkColor} aria-label="Color speaker names by speaker" />
          <span class="settings-pill-track"></span>
          <span class="settings-pill-thumb"></span>
        </span>
      </label>
    </div>
    {/if}

    <div class="settings-section">
      <div class="settings-section-label">Copying</div>
      <label class="settings-check-row">
        <span class="settings-check-name">
          Append citation and translator credit on copy
          <span class="settings-check-hint">Applies to any selection, {sourceLanguageLabel} or English</span>
        </span>
        <span class="settings-pill">
          <input type="checkbox" bind:checked={citeCopy} on:change={saveCiteCopy} aria-label="Append citation when copying text" />
          <span class="settings-pill-track"></span>
          <span class="settings-pill-thumb"></span>
        </span>
      </label>
    </div>

    <div class="settings-section">
      <button type="button" class="settings-reset" on:click={resetSettings}>Reset to defaults</button>
    </div>
  </div>
</aside>

{#if settingsOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="settings-backdrop" on:click={closeSettings} transition:fade={{ duration: reduceMotion ? 0 : 180 }}></div>
{/if}

{#if popup}
  <WordPopup
    {work}
    token={popup.token}
    anchor={popup.anchor}
    asSheet={trans === 'compare'}
    {grammataLookup}
    onClose={closePopup}
  />
{/if}

<svelte:window on:pointerdown={onDocPointerDown} />

{#if footnote}
  <FootnotePopup
    {work}
    n={footnote.n}
    transId={footnote.transId}
    anchor={footnote.anchor}
    onClose={closeFootnote}
    onHoverIn={cancelFnClose}
    onHoverOut={scheduleFnClose}
  />
{/if}

{#if copyBtnPos}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <button
    class="copy-cite-btn"
    style="left:{copyBtnPos.x}px;top:{copyBtnPos.y}px"
    on:mousedown|preventDefault
    on:click={clickCopyBtn}
    aria-label="Copy with citation"
    title="Copy with citation"
  >
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2z"/>
      <path d="M0 4a2 2 0 0 1 2-2v10a2 2 0 0 0 2 2h8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4z"/>
    </svg>
    Copy
  </button>
{/if}
