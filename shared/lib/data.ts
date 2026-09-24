// Data-fetch helpers. All paths relative to /data (public symlink to
// build/dist/ne). Shards are cached in module-level Maps so a single
// click won't re-fetch the same shard twice in a session.
import { linkifyGlossaryRefs } from './glossary';
import { scheme, schemeFor } from './citation';
import { getWork } from './works';

export interface Token {
  t: string;   // surface form (Unicode Greek)
  o: number;   // char offset in the line
  // Beta Code key — absent (not empty) for a NON-LEXICAL token (inline
  // Latin-script apparatus, editor names, bare numerals: no Greek letters
  // at all, so no lexicon entry could ever exist). Present and non-empty
  // for every lexical (Greek) token.
  k?: string;
}

// DK prose-flow (docs/prose-flow-design.md §3): a declared incipit-stub
// column. Reader-read via Work.citation.incipitColumns (works.ts); the
// sha256_16 is for the pipeline preflight hash gate, not presentation.
export interface IncipitColumn {
  column: string;
  sha256_16: string;
}

// One ancient witness in a DK apparatus block, split out by
// pipeline/reader_pipeline/dk_witness.py's split_witnesses. `source` is the
// witness's own citation label (e.g. "SIMPL. Phys. 157, 25"); absent for a
// lead-in run before the first citation, or for a witness whose label
// could not be safely separated from a wholly-Latin or Latin-prose-heavy
// body (see that module's own doc for both fail-closed-per-witness cases).
export interface Witness {
  source?: string;
  text: string;
  // The witness's own clickable tokens, offsets rebased to `text` — cut from
  // the apparatus by offset in stage7_emit.py (split_witnesses partitions the
  // apparatus without rewriting it, so the cut is exact). Present on every
  // emitted witness; `?? []` at the call site only guards data built before
  // this field existed.
  tokens?: Token[];
  // Offsets of `text` within the column's joined apparatus. Emitted for
  // auditability — the reader renders from `text`/`tokens` and never needs
  // these.
  start?: number;
  end?: number;
}

export interface GreekLine {
  n: number;
  text: string;
  // Lined-source only. With `wrap`/`wrapO`, marks an in-column wrap that the
  // reader repaints. Alone, allowed only on a segment's final line, marks a
  // cross-column rejoin that the reader does not repaint.
  joined?: boolean;
  tokens: Token[];
  // Table row: present when the Greek line is part of an inline table (the TLG
  // ⎪ column divider, e.g. the De Int 22a modal square). Each cell carries its
  // own text + clickable tokens (offsets rebased to the cell).
  cells?: { text: string; tokens: Token[] }[];
  // Standoff TLG-section paragraph offsets over this line's `text` (Discourses
  // only — John's ruling 2026-07-16: Schenkl's section divisions are the
  // default paragraphing. See pipeline/reader_pipeline/stage1_greek.py's
  // _chapter_sections). `o` is a char offset landing on an inter-word
  // boundary (never inside a token); first entry always o=0; strictly
  // ascending. Absent for every line whose chapter didn't opt in or kept
  // fewer than 2 boundaries — never an empty array.
  sections?: { n: number; o: number }[];
  // Lined-source only (Discourses, docs/lined-source-plan.md §3): the TLG
  // section number this print line belongs to. REQUIRED on every line of a
  // lined-source work (never a standoff channel like `sections` above — the
  // two never coexist on one line, see the plan's I5); absent on every other
  // work's lines. A line starts a new section iff it is the segment's first
  // line or its `sec` differs from the previous line's — derived, never
  // stored separately, so the two can never disagree.
  sec?: number;
  // Lined-source only, present iff `wrapO` is present: count of characters of
  // the WRAPPED token's surface `t` (the token at offset `wrapO`, below)
  // that Schenkl printed on THIS line before the print hyphen; the
  // remainder (`t.slice(wrap)`) was printed at the head of the next line.
  // 0 < wrap < len(t). The reader repaints the split as
  // `t.slice(0, wrap) + '-'` here and `t.slice(wrap)` as the start of a
  // leading carried block on the next line — both pieces bound to this same
  // token, so `joined`'s token stays whole in the data (tokenisation,
  // morphology, LSJ and search are unaffected; see the plan's Q2).
  wrap?: number;
  // Lined-source only, present iff `wrap` is present (2026-08-29 deviation,
  // docs/lined-source-plan.md §3): the char offset in THIS line's `text`
  // where the wrapped word (the token `wrap` slices) starts — i.e. the
  // token whose `o` equals `wrapO`. Named explicitly rather than inferred
  // as "the last token" because `joined` absorbs the WHOLE whitespace-
  // delimited continuation fragment (I4), which can glue MORE than the
  // wrapped word onto this line when the source glues an em dash straight
  // onto the next word with no space (epicurus-letter-to-herodotus §53/§69:
  // "…σχηματίζε-" / "σθαι—πολλὴν…" absorbs "σθαι—πολλὴν" whole, so
  // "πολλὴν" becomes this line's LAST token, not the wrapped one). The
  // reader locates the wrapped token by `wrapO`, not by array position, and
  // carries EVERYTHING after it (the word's own remainder plus any
  // subsequent render parts) to the next line's head.
  wrapO?: number;
  // Lined-source only, present on a paragraph-opening print line (John's
  // ruling 2026-08-29): the edition's own first-line indent level,
  // 1..`citation.lined_indent_max`, from
  // the TLG export's `<l rend="indent(N)">` (level 1 an ordinary paragraph
  // open, deeper levels quoted/inset matter). A visual inset only — never
  // changes `text`, `tokens`, `sec`, or the wrap/join channel. Absent on
  // every other line (every other work's lines, and most lined lines too).
  indent?: number;
  // dk (Diels-Kranz) role tag: 'text' is the words Diels attributed to the
  // philosopher (letter-spaced in DK); 'context' is the quoting source's own
  // narrative and any surviving editorial commentary (small/italic in DK,
  // after German-commentary stripping). 'lacuna' (verse-line only —
  // Lucretius' DRN, Wave 2 Batch 2, design memo §3.2) marks an
  // editor-marked textual gap ("* * *" in the print edition): `text` is
  // always empty and `tokens` always [] for a lacuna line — see
  // pipeline/reader_pipeline/stage1_latin.py's `_parse_verse`. 'salutation'
  // (the `letter` scheme only — Seneca's Epistulae Morales, Wave 2 Seneca,
  // design note docs/wave2-seneca-design.md §B) is a real letter's opening
  // address ("Seneca to his Lucilius, greetings"), folded as the leading line of
  // that letter's own section 1 — text/tokens present and clickable like an
  // ordinary line, just visually set off; see
  // pipeline/reader_pipeline/stage1_latin.py's `_parse_letters`. Present
  // only for a dk fragment scheme's, a verse-line scheme's, or a letter
  // scheme's segments -- see stage1_greek._parse_fragments/
  // stage1_latin._parse_verse/_parse_letters and stage7_emit.py's
  // line-shape comment. Absent (not a fourth state) for every other
  // scheme's lines.
  // 'heading' (the `letter` scheme only — Seneca's Epistulae Morales,
  // REVIEW-CHECKLIST item 5, John's ruling 2026-08-03) is a structural
  // paratext marker (a manuscript book-division title, e.g. "LIBER
  // SECVNDVS"), folded as a leading line of that letter's own section 1,
  // ahead of any role='salutation' line — never independently citable
  // (unlike 'salutation', it carries no citation anchor). Distinct from
  // both 'context' (a quoting source's own narrative) and 'salutation'
  // (Seneca's own words to Lucilius): a heading is neither — see
  // pipeline/reader_pipeline/stage1_latin.py's `_parse_letters`.
  role?: 'text' | 'context' | 'lacuna' | 'salutation' | 'heading';
  // verse-line only (Lucretius' DRN, design memo §3.3): an auto-generated
  // note at a transposed block's citation-order seam ("Line 14 transmitted
  // after line 15 in this edition") — present only on the citation-order-
  // first line of a transposed block; see
  // pipeline/reader_pipeline/stage1_latin._transposition_seam_note. Absent
  // for every other line.
  seamNote?: string;
}

// A per-passage translation credit: the translator, edition and (where the
// text is used under a licence rather than being public domain) that
// licence and its URL. Carried by an EnglishChunk whose English comes from
// a DIFFERENT translation than the work's own primary one — the work-level
// credit in the reader's control bar names the primary translation, so a
// passage translated by someone else must name its own translator on the
// page, and its licence with it. Absent everywhere else: every work whose
// English is entirely its primary translation carries no `credit` key at
// all (byte-identical by construction).
export interface TranslationCredit {
  translator: string;
  // Edition/volume the translation is printed in, as it should be cited.
  source: string;
  year: number;
  // Present only for a licensed (non-public-domain) text; the licence's
  // short name and the URL of its deed.
  licence?: { name: string; url: string };
}

export interface EnglishChunk {
  text: string;
  notes: { offset: number; text: string }[];
  markers: { kind: string; n: string; offset: number }[];
  // Bekker line ticks for the English gutter; `real` = a true TEI milestone
  // (column start / ~line 20), otherwise a proportional estimate.
  bekker?: { n: number; offset: number; real: boolean }[];
  // Speaker turns starting in this chunk (Stephanus dialogues): the label
  // lead-in is stripped from `text` and rendered separately (like the Greek
  // sigla). `offset` is where the turn's text begins; `speaker` is the canonical
  // name (null = the unattributed dash turn); `display` is the printed lead-in
  // (null when the said carried none). Absent for non-dialogue chunks.
  turns?: EnglishTurn[];
  // Standoff verse ranges over this chunk's `text` (book-section works whose
  // translation quotes verse inline, e.g. Diogenes Laertius' embedded
  // epigrams — see stage1_book_section_english.py's verse-sidecar support).
  // `start`/`end` are char offsets into `text`; `breaks` are line-break
  // offsets strictly inside (start, end). Absent for every chunk with no
  // quoted verse (the overwhelming majority) — never an empty array.
  verse?: { start: number; end: number; breaks: number[] }[];
  // A chapter's own descriptive heading (Discourses only — Oldfather's
  // italic subtitle, e.g. "Of freedom"). Absent for every other work's
  // chunk. See pipeline/tools/extract_oldfather_wikisource.py.
  title?: string;
  // Standoff paragraph-marker offsets over this chunk's `text` (Discourses
  // only — Oldfather's every-5th-TLG-section Loeb reference markers, a
  // SUBSET of the Greek line's `sections` channel numbers for the same
  // chapter — see stage1_book_section_english.py's paras-sidecar support).
  // `o` is a char offset landing on an inter-word boundary; strictly
  // ascending. Absent for every chunk with no markers — never an empty array.
  paras?: { n: number; o: number }[];
  // Source-citation frame ranges (Freeman Ancilla wave, design note
  // docs/freeman-wave-design.md §3's `.eng-source-frame`): [start, end)
  // char offsets into `text` marking Freeman's own parenthetic citation
  // lead-in for an `embedded`-kind DK fragment (e.g. "(Porphyry: " in
  // "(Porphyry: 'Few of the writings…')"), as distinct from the quoted
  // words that follow. Emitted by extract_freeman_wayback.py; the design
  // note does not specify an exact range format, so this is the
  // implementation's own choice — plain char offsets into the chunk's own
  // `text`, non-nesting. Absent for every non-freeman-model chunk and for
  // a freeman chunk with no detected citation lead-in.
  frames?: [number, number][];
  // Per-passage translation credit — present only when this chunk's English
  // comes from a different translation than the work's primary one (see
  // TranslationCredit, and english.column_sources in the work manifest).
  credit?: TranslationCredit;
  // John's ruling 2026-07-29: true only for a Freeman-primary column whose
  // whole entry is Kathleen Freeman's own parenthetical précis of a source
  // she is reporting, rather than a translation of the DK fragment's own
  // words — declared per-work in `english.summary_labels`
  // (pipeline/reader_pipeline/stage1_freeman_english.py), gated on the
  // entry being wholly parenthetical AND this column carrying NO translated
  // context-english source-passage span (a précis that IS covered by one is
  // instead suppressed outright via `english.summary_suppressed` — never
  // both). Reuses the exact "(summary)" convention item 84's freeman-summary
  // overlay (TranslationRef.kind === 'summary') already carries for the
  // whole-translation case, applied here per PASSAGE instead — see
  // Reader.svelte's engCreditFor and the segTransToggle snippet's `label`.
  // Absent for every other chunk (byte-identical for every work built
  // before this ruling).
  summary?: true;
}

// Paratext ribbon before a segment (Freeman Ancilla wave, design note
// docs/freeman-wave-design.md §1/§3.7): Freeman's own subject/category
// group headers carry no DK number of their own ("Doubtful titles…",
// "'On Mathematics'"). `level` 1 = whole-paragraph small-caps (echoes the
// work masthead); 2 = a quieter wholly-italic short label. `beforeColumn`
// names the DK column the header immediately precedes, in DISPLAY order
// (segment.kind's own §3.7 display-order note). Rendered in every view,
// including Greek-only (John's ruling, design note's post-draft
// rulings §1) — it is editorial structure, not a translation.
export interface Paratext {
  beforeColumn: string;
  level: 1 | 2;
  text: string;
}

export interface EnglishTurn {
  offset: number;
  speaker: string | null;
  display: string | null;
}

// One entry of a dialogue book's global turn flow (see TurnFlow): `g` is the
// Greek start ref (Stephanus column token, line n, char offset) — null for an
// English-only residual; `e` is the turn's English slice text — null for a
// Greek-only residual; `s`/`d` are the canonical speaker and the printed
// English lead-in; `p` marks a paired (level-locked) turn.
export interface FlowTurn {
  s: string | null;
  d: string | null;
  g: { c: string; n: number; o: number } | null;
  e: string | null;
  p: boolean;
  // ── Optional flow extensions. The pipeline emits an explicit JSON `null`
  // when a field is absent (not an omitted key), so each is `T[] | null` as
  // well as optional; old dialogue JSON (keys absent) still typechecks.
  //
  // `ep`: paragraph-break offsets within this turn's stripped English slice
  // (exclusive of 0 and the slice end) — the reader renders each as a break.
  // Emitted for para-flow rows AND for dialogue turns with internal paragraphs
  // (Timaeus/Phaedo long speeches).
  ep?: number[] | null;
  // `et`: embedded english.turns for a para-flow row — intra-row speech blocks
  // with lead-ins (dialogue nested inside a narrated paragraph row). `o` is the
  // char offset in the row's English slice where the embedded speech begins.
  et?: { o: number; s: string | null; d: string | null }[] | null;
  // `sub`: stacked one-sided English speeches folded under this row (pipeline
  // B4's column-grouped residual rows — dialogue flows like Lysis/Parmenides,
  // and the para-flow contract). Usually the row's `e` is null and the stack
  // is its whole English cell; when the row also carries English (a narration
  // lead, e.g. Lysis 203a) the stack follows it. Each speech has its own
  // lead-in, English text, and optional paragraph breaks.
  sub?: { s: string | null; d: string | null; e: string; ep?: number[] | null }[] | null;
  // `alt`: this turn's text in ALTERNATE translations, keyed by translation id
  // (see shared/lib/works.ts TranslationRef.id). Populated by the post-stage7
  // turn aligner (pipeline/reader_pipeline/align_turns.py), which pairs each
  // alternate translation's speaker turns to this reference turnFlow so the
  // alternate inherits Stephanus anchoring. The reader's turn-by-turn compare
  // renders `alt[id].e` in the second column on this same row; `e` is null for
  // a reference turn the alternate has no match for (rendered as an em-dash).
  alt?: Record<string, { e: string | null; ep?: number[] | null }> | null;
}

// A dialogue book's turn flow: the globally-paired, ordered turn list the
// reader renders as Greek-beside-English rows (each speaker's statement level
// with its translation; Stephanus sections become gutter ticks). Present only
// for books with Greek turn events; narrated books keep section-row rendering.
// `leadE` is English prose preceding the first English turn.
//
// `kind: 'para'` marks a paragraph-anchored flow for a NARRATED work: rows are
// paragraphs (s/d null, p false), the English cut at paragraph boundaries and
// the Greek ref snapped to the nearest Stephanus section boundary. Absent (or
// omitted) for ordinary speaker-turn dialogue flows.
export interface TurnFlow {
  kind?: 'para';
  leadE: string | null;
  turns: FlowTurn[];
}

export interface ChapterStart {
  chapter: string;
  beforeLine: number;  // insert the heading before the Greek line with this n
  wordIndex: number;   // word index within that line where the chapter begins
                       // (>0 means the chapter starts mid-line → split the line)
  engOffset: number;   // char offset in the English chunk where the chapter begins
  bekker: string;      // Bekker span, e.g. "1097a–1098b" (single column if equal)
}

// A slice of an overlay translation paired to a chapter block in this column.
// `cont` = the tail of a chapter that began in an earlier column. An overlay is
// chapter-anchored (no per-line Bekker gutter), distributed across columns.
export interface OverlayPiece {
  chapter: string;
  text: string;
  cont: boolean;
  // Interpolated Bekker-line ticks down this slice (all estimates — an overlay
  // has no milestones of its own). Same shape as EnglishChunk.bekker.
  bekker?: { n: number; offset: number; real: boolean }[];
  // Structured diagram tables (e.g. Ackrill's squares of opposition), each
  // anchored to the Bekker line `n` of the segment it belongs to; rendered as a
  // grid after that segment's row.
  tables?: { n: number; rows: string[][] }[];
}

// A speaker-turn event in a Stephanus dialogue (Plato): the interlocutor whose
// speech begins at `offset` (char position in line `line`'s rejoined text). The
// `label` siglum ("ΕΥΘ.") or dialectic dash ("—") is EXCLUDED from the line text
// and rendered as a separate inline lead-in, so token char-offsets never shift.
// See shared/lib/speakers.ts for the render model. Absent for non-dialogue works.
export interface SpeakerTurn {
  line: number;
  offset: number;
  label: string;
}

// Source-passage English (docs/source-passage-english-scoping.md): the
// quoting source author's own English for a DK context run this column
// carries, resolved by locus pointer at build time against an already-
// vendored translation store (never a pasted duplicate — see
// pipeline/reader_pipeline/stage1_context_english.py). `status: "desert"`
// is a first-class, renderable state — no PD English exists for that
// passage — and carries no `text`/`translationCredit`.
export interface ContextEnglishSpan {
  sourceAuthor: string;
  sourceWork: string;
  locus: string;
  status: 'translated' | 'desert';
  translationCredit?: string;
  text?: string;
  // One source-section locus per paragraph in `text` (in order), present
  // only when `locus` is a multi-section range — lets the reader mark each
  // paragraph with its own section number (same "book.section" convention
  // as the source work's own segment ref — see Reader.svelte's `.seg-ref`).
  // Absent for a single-section locus (the span's own `locus` already
  // names it).
  sectionLoci?: string[];
  // Per-passage translation picker (item 82): alternate PD English
  // translations of this same source passage, for a page-local toggle
  // beside the primary rendering above. Absent or empty -- the common
  // case -- changes nothing (no toggle, byte-identical rendering).
  alts?: ContextEnglishAlt[];
  // Item 83 (REVIEW-CHECKLIST): hand-authored exact substrings of the
  // PRIMARY `text` above, marking the English words that translate the
  // Greek excerpt DK actually prints -- rendered bold, surrounding context
  // at normal weight. Validated at build time: each substring occurs
  // exactly once in `text`, the substrings are non-overlapping, and they
  // appear in this array in the same order they occur in `text`. Never
  // crosses a paragraph join ("\n\n") -- each substring lives entirely
  // inside one resolved paragraph. Applies only to the primary rendering;
  // a picked `alts` entry (Jowett or otherwise) never carries emphasis.
  // Absent or empty -- the common case -- changes nothing (no `<strong>`,
  // byte-identical rendering).
  emphasis?: string[];
}

// One alternate translation of a ContextEnglishSpan's source passage
// (item 82). `sections` carries one entry per locus of the span's own
// range, in the same order as the span's sectionLoci (or the single
// `locus` for a one-section span) -- so switching the picker never has to
// re-resolve which paragraph belongs to which source section.
export interface ContextEnglishAltSection {
  locus: string;
  // Absent -- this translation has no text for this section -- renders a
  // gap marker rather than an empty paragraph.
  text?: string;
}
export interface ContextEnglishAlt {
  id: string;
  label: string;
  translationCredit: string;
  sections: ContextEnglishAltSection[];
}

// DK source-citation expansion (docs/citation-expansion-wiring-design.md):
// one entry per apparatus citation head the pipeline resolved for this
// column's context run(s). `resolution: "direct"` carries a full lookup
// (`authorDisplay`/`work`/`locus`); `resolution: "verbatim"` is the honest
// unresolved case — only `verbatim` + `flags` are populated, never an
// invented author or title. `work.italic: false` marks a DEFAULT/opaque
// work title (e.g. "(commentary on Aristotle)") that must never render as
// a real title dressed up in italics. `apparatus` carries a Doxographi/
// editor-bracket ref DK printed alongside the locus (e.g. "(D. 476)") —
// kept verbatim, never expanded into the lookup, absent when the head
// carried none (memo §2, "Apparatus is never expanded").
export interface ExpandedCitationEntry {
  verbatim: string;
  resolution: 'direct' | 'verbatim';
  authorDisplay?: string;
  work?: { title: string; italic: boolean };
  locus?: string;
  apparatus?: string;
  flags: string[];
  dashInherited?: boolean;
}

export interface Segment {
  id: string;
  column: string;
  greek: GreekLine[];
  // DK apparatus witness split (dk_witness.py, wired in stage7_emit.py) --
  // present only when the column's role='context' content actually split
  // into 2+ witnesses; absent everywhere else (byte-identical for every
  // other column, and for every non-dk scheme). The underlying role=
  // 'context' `greek` lines are never removed or altered by this field's
  // presence -- Reader.svelte falls back to rendering them normally
  // whenever using this list isn't safe (see prose-flow.ts's
  // singlePureContextRun).
  witnesses?: Witness[];
  english: EnglishChunk | null;
  chapterStarts?: ChapterStart[];
  // Source-passage English spans for this column's context run(s) — present
  // only for a segment named in the work's sources/<work>/context-
  // english.json declaration; absent everywhere else (byte-identical for
  // every work with no declaration file, and for every work built before
  // this mechanism existed).
  contextEnglish?: ContextEnglishSpan[];
  // Expanded English form of this column's DK apparatus citation head(s) —
  // present only for a work that opted into `citation.expand_citations` and
  // a segment carrying >=1 head; absent everywhere else (byte-identical for
  // every other work). One inner list per DISTINCT context run in document
  // order (DK's own printed unit) -- a run's own multi-source entries (a
  // head naming several witnesses) join with "; " inside that run's list,
  // but two separate runs are never merged into one attribution (fix round:
  // Heraclitus B37 has two runs -- "COLUMELLA VIII 4..." and a later,
  // unrelated "[vgl. B 13],") -- each renders as its own line.
  expandedCitation?: ExpandedCitationEntry[][];
  // Speaker-turn events for a Stephanus dialogue segment (see SpeakerTurn).
  speakers?: SpeakerTurn[];
  // The work's second translation, chapter-anchored. Emitted under `ross` by
  // today's pipeline; `secondary` is the name the reader prefers, and the
  // pipeline will emit it in stage 2 of the rename.
  secondary?: OverlayPiece[];
  /** @deprecated Legacy name for `secondary` — the slot was called `ross` when
   *  W. D. Ross was its only occupant. Still emitted by the pipeline, so the
   *  reader reads `secondary ?? ross`. Drop once stage 2 lands. */
  ross?: OverlayPiece[];
  // Optional third translation (same overlay shape as secondary), e.g.
  // Categories' Ackrill beside Edghill + Taylor. Absent in works with fewer
  // translations.
  third?: OverlayPiece[];
  // Any further overlay translations (the 4th onward), keyed by translation id.
  // Same overlay shape as secondary/third. Lets a work carry an unbounded
  // number of chapter-anchored translations beyond the fixed secondary/third
  // slots.
  overlays?: Record<string, OverlayPiece[]>;
  // Freeman Ancilla wave (design note §1(b)): the DK column's per-column
  // entry-type classification -- proposed by the extractor from Freeman's
  // own English markup, declared in the manifest, and cross-checked at
  // build time against this segment's own Greek `role` profile (a `title`/
  // `note` column carries no role='text' line; `verbatim` carries at least
  // one; `embedded` carries a role='context' frame). Present only for a
  // Freeman-covered column; absent everywhere else (byte-identical for
  // every other work, and for a non-Freeman dk work).
  kind?: 'title' | 'verbatim' | 'embedded' | 'note';
  // Freeman's own admission that a longer extract is a summary, not a full
  // translation (Gorgias only — design note §2/§3's `abridged_columns`).
  // Absent everywhere else.
  abridged?: boolean;
  // A continuous verbatim work with no DK letter-spacing at all — every
  // line's `role` is 'context' because there is no quoting frame to
  // contrast against, but the column IS the philosopher's own text (item 65:
  // Gorgias' Helen and Palamedes speeches, DK B11/B11a). Present only for a
  // column named in the work's manifest `citation.whole_column_verbatim`
  // attestation (see pipeline/reader_pipeline/preflight.py's
  // `_whole_column_verbatim_columns`, stage7_emit.py); absent everywhere
  // else. Reader.svelte's DK prose-flow renders such a column's runs at
  // full text weight (`frag-txt`) instead of the muted apparatus weight
  // (`frag-ctx`) role='context' would otherwise carry.
  wholeColumnVerbatim?: true;
  // A column that keeps its ordinary mixed role='context'/'text' profile (a
  // real quoting frame around a quotation) but whose Greek AND English both
  // carry the source's own inline ascending "(N)" listing baked into the
  // text (item 85's Melissus B7/B8 addendum: Simplicius quoting Melissus's
  // book entire, the ordinal numbers part of the quotation itself). Present
  // only for a column named in the work's manifest
  // `citation.section_paragraph_columns` (see pipeline/reader_pipeline/
  // preflight.py's `_validate_section_paragraph_columns`, stage7_emit.py);
  // absent everywhere else. Unlike wholeColumnVerbatim, this never forces
  // full text weight on a role='context' run and needs no per-column
  // `english.credit` override -- it only drives Reader.svelte's marker
  // paragraph split on both sides, keying off the work's ordinary primary
  // English.
  sectionParagraphSplit?: true;
}

export interface ChapterRef {
  chapter: string;
  column: string;
  line: string;
  bekker: string;
}

export interface BookData {
  book: number;
  segments: Segment[];
  // Global turn flow for a dialogue book (see TurnFlow). Absent for narrated
  // books and non-stephanus works, which render the segment array as before.
  turnFlow?: TurnFlow;
  // Freeman Ancilla wave (design note §3.7): the manifest's declared
  // display permutation of `segments`' own column tokens, present only
  // when Freeman's own printed sequence diverges from the spine's
  // document order. Citations/anchors/ids stay column-keyed regardless —
  // the reader reorders the RENDERED segment list only (Lucretius
  // citation-order-display precedent, at column granularity). Absent for
  // the overwhelming majority of works (spine order = display order).
  displayOrder?: string[];
}

export interface Analysis {
  lemma: string;   // Beta Code (Greek) or plain Latin (Wave 2 — never Beta Code for a 'lat' work)
  gloss: string;
  parse: string;
  lsj: string[];   // dictionary key(s): LSJ (Greek) or Lewis & Short (Latin)
  foldedAccent?: boolean; // all-caps Greek fallback: accentuation is ambiguous
}

export interface LsjEntry {
  key: string;
  head: string;    // Unicode Greek (LSJ) or plain Latin (Lewis & Short)
  html: string;
}

// Honour Astro's base path so data fetches work under a project Pages site as
// well as at the root. BASE_URL may or may not carry a trailing slash, so strip
// it and join explicitly. Each work's data lives under /data/<work>/.
//
// A deploy can point the whole data layer at a different origin — e.g. the
// Cloudflare R2 data domain (docs/cloudflare-setup.md §3) instead of
// same-origin `/data` — by setting `PUBLIC_DATA_ROOT` at BUILD time (a Vite
// static replacement, same mechanism as `PUBLIC_SITE_ORIGIN`); it takes
// precedence over the BASE_URL-derived default. A non-Astro host (the
// desktop app) can additionally override at RUNTIME — e.g. a Tauri asset://
// URL for an on-disk corpus directory — by setting
// globalThis.__READER_DATA_ROOT__ before any fetch helper runs; that always
// wins over both, and is read lazily so the override applies regardless of
// module-import order.
const DEFAULT_ROOT = import.meta.env.PUBLIC_DATA_ROOT
  ? import.meta.env.PUBLIC_DATA_ROOT.replace(/\/+$/, '')
  : `${import.meta.env.BASE_URL.replace(/\/$/, '')}/data`;
export const dataRoot = () =>
  (globalThis as { __READER_DATA_ROOT__?: string }).__READER_DATA_ROOT__ ?? DEFAULT_ROOT;
const ROOT = dataRoot;

// Response.json() is `any` under the DOM lib but `json<T>(): Promise<T>` under
// the Cloudflare Worker types the app also loads (app/worker-configuration.d.ts),
// where a bare call infers `unknown`. Callers name the shape they expect; the
// call itself is unchanged.
const json = <T>(r: Response): Promise<T> => r.json() as Promise<T>;
const workBase = (work: string) => `${ROOT()}/${work}`;

// All caches are keyed by work so two works loaded in one session (e.g. unified
// search) never collide.
const _analysesCache = new Map<string, Promise<Record<string, Analysis[]>>>();
const _lsjCache = new Map<string, Record<string, LsjEntry>>();
const _bookCache = new Map<string, Promise<BookData>>();
const _chaptersCache = new Map<string, Promise<Record<string, ChapterRef[]>>>();
const _columnsCache = new Map<string, Promise<Record<string, ColumnRef[]>>>();
const _footnotesCache = new Map<string, Promise<Record<string, string>>>();

export function fetchBook(work: string, n: number): Promise<BookData> {
  const key = `${work}:${n}`;
  const cached = _bookCache.get(key);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/book-${String(n).padStart(2, '0')}.json`).then(r => {
    if (!r.ok) throw new Error(`${work} book ${n}: ${r.status}`);
    return json<BookData>(r);
  }).then((d: BookData) => {
    // A non-Astro host (the desktop app) can overlay runtime content — e.g.
    // user-imported translations merged into seg.overlays — via this hook.
    // The site never sets it; the fetched data passes through untouched.
    const hook = (globalThis as {
      __READER_BOOK_HOOK__?: (work: string, n: number, data: BookData) => BookData;
    }).__READER_BOOK_HOOK__;
    return hook ? hook(work, n, d) : d;
  });
  // Evict a rejected fetch so it can be retried (don't cache the failure).
  p.catch(() => { if (_bookCache.get(key) === p) _bookCache.delete(key); });
  _bookCache.set(key, p);
  return p;
}

/**
 * Drop cached book data so the next fetchBook re-fetches and re-runs
 * __READER_BOOK_HOOK__. The desktop app calls this after a translation
 * import (imports.ts's overlays are merged into the fetched BookData by the
 * hook, which only runs at fetch time — a book already loaded before the
 * import keeps its pre-import segments until its cached promise is dropped).
 * Pass a book number to evict one book, or omit to evict every book of the
 * work. Inert on the site build, which never imports it.
 */
export function invalidateBookCache(work: string, n?: number): void {
  if (n !== undefined) {
    _bookCache.delete(`${work}:${n}`);
    return;
  }
  for (const key of [..._bookCache.keys()]) {
    if (key.startsWith(`${work}:`)) _bookCache.delete(key);
  }
}

export function fetchChapters(work: string): Promise<Record<string, ChapterRef[]>> {
  const cached = _chaptersCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/chapters.json`).then(r => {
    if (!r.ok) throw new Error(`${work} chapters: ${r.status}`);
    return json<Record<string, ChapterRef[]>>(r);
  });
  // Evict a rejected fetch so it can be retried (don't cache the failure).
  p.catch(() => { if (_chaptersCache.get(work) === p) _chaptersCache.delete(work); });
  _chaptersCache.set(work, p);
  return p;
}

// One entry of a Stephanus work's section outline: a page+letter column
// ("17a"), the page number and letter split out, and the stable segment anchor
// id (`book:column`) the reader emits as `col-{column}`. Emitted per book by the
// pipeline's stage7 emit_sections (a section scheme replaces chapters.json with
// sections.json as the outline-nav source — Plato is cited by page+section, not
// by chapter). Ordered in reading order (2a, 2b, … 17e, 18a). `letter` is
// ABSENT for a flat (`section`-scheme) work, whose bare-integer columns have
// no section axis — emit_sections omits the key rather than writing null.
export interface SectionRef { column: string; page: number; letter?: string; id: string; }

const _sectionsCache = new Map<string, Promise<Record<string, SectionRef[]>>>();

// Per-book Stephanus section outline: { book -> ordered SectionRef[] }. Present
// only for section-scheme (stephanus) works; the outline nav groups these by
// page. Cached per work, failure evicted so it can be retried.
export function fetchSections(work: string): Promise<Record<string, SectionRef[]>> {
  const cached = _sectionsCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/sections.json`).then(r => {
    if (!r.ok) throw new Error(`${work} sections: ${r.status}`);
    return json<Record<string, SectionRef[]>>(r);
  });
  p.catch(() => { if (_sectionsCache.get(work) === p) _sectionsCache.delete(work); });
  _sectionsCache.set(work, p);
  return p;
}

// Group a book's ordered sections into Stephanus pages for the outline nav:
// [{ page, column }] where `column` is the first section column on that page —
// the anchor (`col-{column}`) the page's outline entry links to. Reading order
// is preserved (sections are already ordered), so pages come out ascending and
// each page appears once, keyed to where it first starts.
export interface SectionPage { page: number; column: string; }
export function sectionPages(sections: SectionRef[]): SectionPage[] {
  const pages: SectionPage[] = [];
  let last: number | null = null;
  for (const s of sections) {
    if (s.page !== last) { pages.push({ page: s.page, column: s.column }); last = s.page; }
  }
  return pages;
}

// Freeman Ancilla group-header paratext (see Paratext) for a work, in
// display order. Present only for a work whose english.primary is the
// freeman model; absent (empty array, never a fetch error) for every
// other work, mirroring fetchFootnotes'/fetchSidenotes' optional-file
// convention -- a 404 resolves to [] rather than throwing, since most
// works simply have no paratext.json at all.
const _paratextCache = new Map<string, Promise<Paratext[]>>();
export function fetchParatext(work: string): Promise<Paratext[]> {
  const cached = _paratextCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/paratext.json`).then(r => (r.ok ? json<Paratext[]>(r) : []));
  p.catch(() => { if (_paratextCache.get(work) === p) _paratextCache.delete(work); });
  _paratextCache.set(work, p);
  return p;
}

// Translator footnotes for a work: { footnote number -> pre-rendered HTML }.
// Present only for works whose translation carries notes (NE Ostwald). Loaded
// lazily the first time a `[^N]` marker is clicked, then cached for the session.
export function fetchFootnotes(work: string): Promise<Record<string, string>> {
  const cached = _footnotesCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/footnotes.json`).then(r => {
    if (!r.ok) throw new Error(`${work} footnotes: ${r.status}`);
    return json<Record<string, string>>(r);
  }).then((map: Record<string, string>) =>
    // The NE (Ostwald) footnotes reference glossary entries ("see Glossary,
    // <term>"); turn those into links to the standalone glossary page.
    work === 'EN'
      ? Object.fromEntries(Object.entries(map).map(([k, v]) => [k, linkifyGlossaryRefs(v)]))
      : map
  );
  // Evict a rejected fetch so it can be retried (don't cache the failure).
  p.catch(() => { if (_footnotesCache.get(work) === p) _footnotesCache.delete(work); });
  _footnotesCache.set(work, p);
  return p;
}

// Analytical sidenotes for a work: { sidenote number -> text }. Present only for
// works whose translation carries marginal notes (the Isagoge's Owen). Loaded
// lazily and cached for the session.
const _sidenotesCache = new Map<string, Promise<Record<string, string>>>();
export function fetchSidenotes(work: string): Promise<Record<string, string>> {
  const cached = _sidenotesCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/sidenotes.json`).then(r => {
    if (!r.ok) throw new Error(`${work} sidenotes: ${r.status}`);
    return json<Record<string, string>>(r);
  });
  p.catch(() => { if (_sidenotesCache.get(work) === p) _sidenotesCache.delete(work); });
  _sidenotesCache.set(work, p);
  return p;
}

// Diagrams for a work: { figure number -> pre-rendered HTML <figure> }. Present
// only for works that carry [[figN]] markers (the Isagoge's Tree of Porphyry).
const _figuresCache = new Map<string, Promise<Record<string, string>>>();
export function fetchFigures(work: string): Promise<Record<string, string>> {
  const cached = _figuresCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/figures.json`).then(r => {
    if (!r.ok) throw new Error(`${work} figures: ${r.status}`);
    return json<Record<string, string>>(r);
  });
  p.catch(() => { if (_figuresCache.get(work) === p) _figuresCache.delete(work); });
  _figuresCache.set(work, p);
  return p;
}

// Bekker column -> owning book(s) with each book's line span in that column.
export interface ColumnRef { book: number; lo: number; hi: number; }

export function fetchColumns(work: string): Promise<Record<string, ColumnRef[]>> {
  const cached = _columnsCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/columns.json`).then(r => {
    if (!r.ok) throw new Error(`${work} columns: ${r.status}`);
    return json<Record<string, ColumnRef[]>>(r);
  });
  p.catch(() => { if (_columnsCache.get(work) === p) _columnsCache.delete(work); });
  _columnsCache.set(work, p);
  return p;
}

// Parse a raw Bekker citation (e.g. "1097a15", "1097a 15", "1097a.15") into
// its column ("1097a") and line (15). Returns null if it isn't a citation.
// Delegates to the bekker citation scheme so the letter grammar stays in sync
// with the shared contract (a-e, per pipeline/reader_pipeline/scheme.py's
// shared column regex) instead of hand-rolling an [ab]-only pattern here;
// real column membership is still enforced downstream by resolveBekker
// against columns.json, so the wider letter grammar doesn't admit anything
// that wasn't already going to be rejected as "not in the text".
export function parseBekker(raw: string): { column: string; line: number } | null {
  const parsed = scheme('bekker').parseLocation(raw);
  return parsed && parsed.line != null ? { column: parsed.column, line: parsed.line } : null;
}

// Parse a `?loc=` value (or a hand-typed citation) against the citation scheme
// a work actually uses — bare column ("17a"), column:line ("1097a:15"), or the
// legacy concatenated Bekker form ("1097a15"). See shared/lib/citation.ts for
// the grammar and why a lineless scheme (stephanus) rejects a line component
// instead of silently dropping it.
export function parseLocation(work: string, raw: string): { column: string; line: number | null } | null {
  return schemeFor(work).parseLocation(raw);
}

// Resolve a parsed citation to the book that owns it. For a column shared by
// two books (a book that starts mid-column) the line picks the right one,
// snapping to the nearer book if the line falls in the gap between them. A
// null line (a lineless-scheme citation, or a bekker/busse jump to a bare
// column) can't disambiguate a shared column, so it just takes the first
// (lowest-numbered) owning book.
export function resolveBekker(
  columns: Record<string, ColumnRef[]>,
  column: string,
  line: number | null,
): number | null {
  const entries = columns[column];
  if (!entries || entries.length === 0) return null;
  if (entries.length === 1 || line == null) return entries[0].book;
  let best = entries[0];
  let bestDist = Infinity;
  for (const e of entries) {
    const d = line < e.lo ? e.lo - line : line > e.hi ? line - e.hi : 0;
    if (d < bestDist) { bestDist = d; best = e; }
  }
  return best.book;
}

export function fetchAnalyses(work: string): Promise<Record<string, Analysis[]>> {
  const cached = _analysesCache.get(work);
  if (cached) return cached;
  const p = fetch(`${workBase(work)}/analyses.json`).then(r => {
    if (!r.ok) throw new Error(`${work} analyses: ${r.status}`);
    return json<Record<string, Analysis[]>>(r);
  });
  p.catch(() => { if (_analysesCache.get(work) === p) _analysesCache.delete(work); });
  _analysesCache.set(work, p);
  return p;
}

// The lemma-page manifest: dictionary key -> { slug, head, count } for every
// lemma that has a /lemma/<lang>/entry/?w=<slug> reference page (produced by
// scripts/build-lemmata.mjs). `lemmata.json` is Greek (the default,
// unchanged path/name); `lemmata-lat.json` is Latin's sibling manifest
// (Wave 2 Batch 1b). The word popup loads one of these once per language to
// decide whether to offer a "see all N occurrences" link, and only for
// lemmata that actually have a page.
export interface LemmaRef { slug: string; head: string; count: number; }

// The ONE definition of a lemma entry's URL. Lemma entries are client-
// rendered from a single page per language (`/lemma/<lang>/entry/`), which
// reads the word from `?w=`; there is no page per lemma. Every caller must
// come through here: the href was hand-written at five sites when the route
// changed on 2026-08-04, one was missed (the ⌘K palette), and `check-links`
// could not catch it because that href only exists in client JS — it is
// never in the built HTML the gate crawls. A single definition plus the
// unit test on it is the only thing standing in for the link gate here.
export function lemmaEntryHref(base: string, lang: 'grc' | 'lat', slug: string): string {
  return `${base}/lemma/${lang}/entry/?w=${encodeURIComponent(slug)}`;
}
const _lemmataCache = new Map<string, Promise<Record<string, LemmaRef>>>();
export function fetchLemmata(lang: 'grc' | 'lat' = 'grc'): Promise<Record<string, LemmaRef>> {
  const cached = _lemmataCache.get(lang);
  if (cached) return cached;
  const file = lang === 'lat' ? 'lemmata-lat.json' : 'lemmata.json';
  const p = fetch(`${ROOT()}/${file}`).then(r => (r.ok ? r.json() : {}));
  // A missing/failed manifest just means no lemma links — don't cache the failure.
  p.catch(() => { if (_lemmataCache.get(lang) === p) _lemmataCache.delete(lang); });
  _lemmataCache.set(lang, p);
  return p;
}

// Cross-corpus citation index (Lyceum P3 stage 3, docs/p3-plan.md Settled
// decision 5): column -> the bekker/busse work(s)/book(s) that string could
// name, generated by scripts/build-citation-index.mjs from every BUILT
// bekker/busse-scheme work's own columns.json (aristotle-reader's
// build/dist/bekker.json is the shape precedent this generalizes). Consumed
// by shared/lib/citation-router.ts's bare-column dispatch stage — that
// module stays pure (never fetches), so this is the one place the index is
// actually loaded.
export interface CitationIndexEntry { work: string; book: number; lo: number; hi: number; }
export type CitationIndex = Record<string, CitationIndexEntry[]>;

let _citationIndexCache: Promise<CitationIndex> | null = null;

// A missing/failed index (no citation-index.json built yet, or a 404)
// degrades to {} rather than throwing, same as fetchLemmata's
// manifest-optional convention — a router with an empty index simply skips
// its bare-column stage rather than the whole page failing.
export function fetchCitationIndex(): Promise<CitationIndex> {
  if (_citationIndexCache) return _citationIndexCache;
  const p = fetch(`${ROOT()}/citation-index.json`).then(r => (r.ok ? r.json() : {}));
  // Evict a rejected fetch so it can be retried (don't cache the failure).
  p.catch(() => { if (_citationIndexCache === p) _citationIndexCache = null; });
  _citationIndexCache = p;
  return p;
}

export function lsjShard(key: string): string {
  for (const ch of key) {
    if (ch === '*') continue;
    if (/[a-z]/.test(ch)) return ch;
  }
  return '_';
}

// Each work's dictionary is shared across the whole corpus — one copy at
// /data/<dir>/<letter>.json (the union of every work's lemmas of that
// dictionary), not a per-work subset — so entries aren't duplicated ~30×
// across works. `dir` is 'lsj' for Greek (LSJ, the default) or 'ls' for
// Latin (Lewis & Short, Wave 2 Batch 1b — see pipeline's stage5_lsj
// .SHARD_DIR, the source of this convention: the two dictionaries are kept
// in SEPARATE directories because their key spaces can collide (LSJ's Beta
// Code vs L&S's plain-Latin-plus-macron-marks)). Keys are global headwords,
// identical across works of the same language, so the same lookup resolves
// against the shared shard. Cached by `dir:letter` (work-independent).
export async function fetchLsjShard(letter: string, dir: string = 'lsj'): Promise<Record<string, LsjEntry>> {
  const cacheKey = `${dir}:${letter}`;
  if (_lsjCache.has(cacheKey)) return _lsjCache.get(cacheKey)!;
  const r = await fetch(`${ROOT()}/${dir}/${letter}.json`);
  if (!r.ok) return {};
  const shard = await json<Record<string, LsjEntry>>(r);
  _lsjCache.set(cacheKey, shard);
  return shard;
}

export async function lookupWord(
  work: string,
  key: string
): Promise<{ analyses: Analysis[]; lsj: LsjEntry[] }> {
  const allAnalyses = await fetchAnalyses(work);
  const entries = allAnalyses[key] ?? [];
  const dir = getWork(work)?.language === 'lat' ? 'ls' : 'lsj';
  const lsjEntries: LsjEntry[] = [];
  const seen = new Set<string>();
  for (const a of entries) {
    for (const lsjKey of a.lsj) {
      if (seen.has(lsjKey)) continue;
      seen.add(lsjKey);
      const letter = lsjShard(lsjKey);
      const shard = await fetchLsjShard(letter, dir);
      if (shard[lsjKey]) lsjEntries.push(shard[lsjKey]);
    }
  }
  return { analyses: entries, lsj: lsjEntries };
}
