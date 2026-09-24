# Freeman, *Ancilla to the Pre-Socratic Philosophers* — source verification

Kathleen Freeman's *Ancilla to the Pre-Socratic Philosophers: A Complete
Translation of the Fragments in Diels, Fragmente der Vorsokratiker*
(Blackwell, 1948). Extracted from sacred-texts.com's transcription
(`sacred-texts.com/cla/app/appNN.htm`) via a web.archive.org raw `id_`
snapshot — sacred-texts.com itself 403s a direct fetch (Cloudflare
challenge, not a UA block) — see `docs/ancilla-source-assessment.md` for
the fetch mechanics and full risk list, and `docs/freeman-wave-design.md`
for the data model/gates this wave wires up. Copyright status settled
separately (CANON.md, "Freeman Ancilla copyright ruling").

Extraction tool: `pipeline/tools/extract_freeman_wayback.py`.

This README covers **phase 1: Protagoras (DK 80), `app75.htm`**,
**phase 1b: Xenophanes (DK 21), `app18.htm`**, and **phase 2:
Democritus (DK 68), `app63.htm`**. Chapter identities were confirmed
against the source index, not inferred from approximate ranges. Later
phases append their own sections here rather than opening new files,
matching the Gummere/Yonge precedent of one README per source directory.

## Protagoras (DK 80) — `freeman-protagoras.clean.json` / `freeman-protagoras.group_headers.json`

**Fetch**: `https://archive.org/wayback/available?url=sacred-texts.com/cla/app/app75.htm`
resolved to snapshot `20250622215023`; raw page fetched at
`http://web.archive.org/web/20250622215023id_/https://sacred-texts.com/cla/app/app75.htm`.

**Witness cross-check**: the open archive.org OCR scan
(`ancilla-to-the-pre-socratics-freeman`, `..._djvu.txt`, pp. 125–127)
matches the sacred-texts transcription for the whole chapter, content
word-for-word, with one exception (below). The OCR scan's own inline page
numbers ("125", "126") land one position earlier than sacred-texts' own
`p. 126`/`p. 127` inline anchors for the same break points — a labeling-
convention offset between the two sources' own page-marker placement, not
a content discrepancy (every sentence on both sides of each break matches).

**Mechanical fix (1)**: sacred-texts' own transcription of the Porphyry
quotation inside B2 reads "otherwise Plato perhaps would have been
detected in further plagiarisms. **fit** any rate, in the place..." — a
transcription typo. The archive.org OCR scan (independently garbled in
its own ways elsewhere) reads "**At** any rate" at the identical position,
confirming the intended word. Corrected in `freeman-protagoras.clean.json`
to "At any rate"; the raw sacred-texts wording is preserved here as the
paper trail.

**Column mapping**: Freeman's own Arabic-number-plus-letter numbering
(`1.`, `1a.`, …) equals DK's B-numbers with NO drift for this chapter —
every Freeman entry 1–10 (plus 6a/6b/8a–8h) matches an existing DK80B
spine column by EXACT token (verified against
`manifests/protagoras-fragments.yaml`'s declared 20-column spine:
B1–B10, B6a, B6b, B8a–B8h). No `freeman_concordance` remap needed.

**English orphans (dropped)**: Freeman prints two further numbered
entries, **11** ("Education does not take root in the soul unless one
goes deep.") and **12** (the Graeco-Syrian Maxims saying), beyond the
DK80B spine's own last column (B10) — confirmed present in the
archive.org OCR witness too, so not a sacred-texts transcription
artifact. Neither has a corresponding DK B-column in the TLG-sourced
Greek export (the 20-column spine stops at B10); per the design note
§2's English-orphan rule (the Melissus 1a/6a precedent), both are dropped
— not fabricated onto the spine, not silently renumbered onto an
existing column.

**Display order**: Freeman's printed sequence (1, 2, 3, 4, 5, 6, 6a, 6b,
7, 8, 8a–8h, 9, 10) is IDENTICAL to the Greek spine's own document order
(confirmed directly against `build/dist/protagoras-fragments/book-01.json`'s
segment order). No `display_order` declared — the design note's default
(display = spine order) applies unmodified.

**Kind classification — philological judgment call flagged for review**:
three columns (B5, B6, B6a) are wholly-italic parenthetical entries in
Freeman's English with NO small-caps named source — matching, at the pure
markup level, the design note's `note` signature ("wholly-italic
parenthetical … no words survive"). But all three carry at least one
`role='text'` span in the live Greek spine (B5: "Ἀντιλογικοῖς", the title-
word itself, quoted twice inside a Diogenes Laertius testimonium; B6:
"Euathlus", the one surviving Latin word inside the Cicero/Diogenes
Euathlus-lawsuit testimonium — already this work's own declared
`latin_fragments` entry; B6a: "δύο λόγους περὶ παντὸς πράγματος
ἀντικειμένους ἀλλήλοις", quoted inside Diogenes IX 51) — i.e. words DO
survive, embedded in Freeman's own narration rather than block-quoted
with a named-source tag. Classified `embedded`, not `note`, on that
basis (`extract_freeman_wayback.py`'s `classify_kind` tie-break, see its
own docstring) — the Greek DK spine is treated as authoritative over the
English markup shape alone, per the design note's own stated arbitration
rule ("Where the two signals disagree… no heuristic tie-break" — resolved
here by consulting the Greek role, not by guessing). **Flagged explicitly
for John/Opus review before this ships**, as CLAUDE.md routes Greek/Latin
philological judgment calls to that tier; the alternative reading
(`note`) is defensible from the English markup alone and the cross-check
gate (`stage1_freeman_english.py` / preflight) would equally accept
`note` reclassified IF the declared `fragment_kinds` and the extractor's
own re-derivation were both changed together — it is not a case the
build machinery can adjudicate unaided.

**Kind tally**: verbatim 6 (B1, B3, B4, B6b, B9, B10), embedded 5 (B2,
B5, B6, B6a, B8), note 1 (B7), title 8 (B8a–B8h). Total 20, matching the
spine's own column count.

**Group headers**: 5, all level 2 (wholly italic, no small-caps content
anywhere in this chapter — level 1 does not occur in Protagoras; it is
exercised at the Democritus/phase-2 tetralogy stress case per the design
note). In reading order: "Doubtful titles (taken from Diogenes
Laertius)" (before B6), "'On Mathematics'" (before B7), "'On Wrestling
and the Other Arts'" (before B8), "(Titles)" (before B8a), "From
unspecified writings" (before B9).

## Xenophanes (DK 21) — `freeman-xenophanes.clean.json` / `freeman-xenophanes.group_headers.json`

**Source and extraction**: sacred-texts chapter `app18.htm`, "21.
Xenophanes of Colophôn", confirmed from the collection index and checked
against the live public transcription. The exact semantic body and markup
are retained as the offline regression fixture
`pipeline/tests/fixtures/freeman/app18.htm`; it was parsed with
`pipeline/tools/extract_freeman_wayback.py`'s `parse_chapter`, using the
live Xenophanes Greek spine's role=`text` column set. This constrained
environment could not perform the extractor's network fetch itself, so
the fixture body was recovered from a public GitHub mirror of the same
sacred-texts HTML and compared against the live sacred-texts rendering.
No content discrepancy was found.

**Column mapping and edition gaps**: Freeman prints B1–B41 plus B21a,
42 entries total. Every printed number matches its corresponding DK6
column exactly, so `freeman_concordance` is explicitly empty. DK6's B42
and B45 are absent from Freeman's fifth-edition chapter and remain
declared primary edition gaps; no column is fabricated. Freeman's
relative order matches the Greek spine, so no `display_order` is needed.

**Group headers**: two level-2 genre labels: "Elegiacs" before B1 and
"Hexameters" before B10. Xenophanes required one minimal extractor
extension beyond the Protagoras pilot: preserving a wholly-italic group
label that appears before the first numbered entry.

**Kind classification**: 33 `verbatim`, 5 `embedded`, and 4 `note`.
Nine entries initially classify `conflict`, all resolved only through
approved Protagoras precedents:

- B4, B13, B19, B40 → `note`, following B7: wholly-italic editorial
  report or gloss, with no Greek role=`text` line.
- B20, B21, B21a, B39, B41 → `embedded`, following B6a: a reported
  phrase, epithet, or lexical item survives inside the later source's
  sentence.

Xenophanes also required the extractor's markup/role disagreement rule
to cover roman `verbatim`-looking text with no live role=`text` line
(B21, B21a, B39, B41). Such cases now classify `conflict` rather than
being accepted from markup alone. No unresolved Xenophanes conflict
remains and no new philological ruling was introduced.

**Translation slots**: Freeman is primary. Burnet's existing 32-column
translation is retained as the secondary overlay; its 12 known edition
gaps moved to `alignment_allow_unmatched_secondary`. The Freeman primary
has only the two fifth-to-sixth-edition gaps B42/B45.

## Democritus (DK 68) — `freeman-democritus.clean.json` / `freeman-democritus.group_headers.json`

**Source and extraction**: sacred-texts chapter `app63.htm`, "68.
Dêmocritus of Abdêra", confirmed from the collection index. Its semantic
HTML is retained as
`pipeline/tests/fixtures/freeman/app63.htm`, recovered from the same
public sacred-texts mirror used for the Xenophanes fixture and checked
against the live sacred-texts rendering. The extractor now handles the
chapter's compound small-caps tetralogy headings, the indented
internally-numbered B14 calendar (including its tables), legacy
Windows-1252 punctuation bytes, and genuine inline numerals without
weakening the fatal footnote-anchor leak check.

Three exact sacred-texts numbering typos are corrected during extraction:
the first printed `308. 'Theogonia.'` is DK B301, `30S.` is B305, and
`13I.` (a capital I standing in for the digit 1) is B131. The later
printed B308 is the genuine B308 epigram notice and remains distinct. The
`13I.` correction is not a literal-signature match like the other two --
it is accepted generically (any I/l-for-1 typo in a leading Arabic-number
label) but ONLY when the corrected number is the exact expected successor
of the entry being accumulated, so a genuine roman numeral or a stray
letter is never misread as a new entry.

**Coverage and edition reconciliation**: Freeman prints 390 numbered
entries. Five have no column in the existing DK6 spine and are excluded
as English-only entries: B25a, B25b, B301, B303, and B305. Freeman B16c
maps to DK6 B15c. DK B131 was previously believed to be Freeman's sole
edition gap, but that was an artifact of the `13I.` scan typo merging its
text into B130 (fixed above): Freeman coverage is complete, 386 of the
work's 386 columns. The reconciled order equals the existing DK spine, so
no display-order declaration is needed. Democritus B36 is one of the
sixteen precedent-less conflicts resolved below (`omit` — its Freeman
text is a bare cross-reference, "= 187.", not a translation).

**Group headers**: 21 structural labels: eight level-1 subject/group
headings and thirteen level-2 labels. They include the Thrasyllan
tetralogies, the title lists before B5a/B11b/B11l/B14a/B26b/B28a/B299a,
the unclassified Causes, the genuine fragments and Gnomae sections, the
Doubtful/Spurious labels before B298a/B298b, and two labels recovered from
standalone margin-left divs the extractor previously glued onto the
preceding entry's text: the end-of-section marker "(End of the Gnomae)"
before B116, and the forward range label "128-141. (Unusual words quoted
by grammarians)" before B128.

**Kind classification**: extraction yields 52 conflicts after the five
English-only entries are removed. Thirty-seven use already-approved pilot
precedents and are declared in the manifest: 25 title presentations use
Protagoras B5, seven editorial reports/references use B7, and four
reported lexical survivals use B6a (B122a moved note→embedded on
adversarial review). Sixteen unprecedented disagreements initially
stopped the Freeman loader outright (B300's initial title override was
rejected on review — the merged dossier carries substantive role=`text`
witnesses, so it did not fit the B5 title precedent) until John's
2026-07-23 ruling (docs/freeman-wave-design.md's post-draft rulings §4:
"I'm not into translations that don't have greek supporting them. where
she has no greek, we leave out. ... don't ship known mistranslations
don't ship things for which we have no greek") resolved all sixteen via
`kind_overrides`, fourteen of them to the new `omit` disposition (ships
no Freeman English at all; the Greek renders alone):

- B15 — markup: quoted title followed by a small-caps source name and
  mixed roman/italic report; reading: title plus geographical report,
  while the Greek column has no role=`text` line. **Disposition: `omit`**
  (testimonium-only).
- B19 — markup: small-caps source name plus reported letter names;
  reading: reported lexical material, while the Greek column has no
  role=`text` line. **Disposition: `omit`** (testimonium-only).
- B23 — markup: small-caps source name plus a Homeric quotation and
  report; reading: reported interpretation, while the Greek column has
  no role=`text` line. **Disposition: `omit`** (testimonium-only).
- B25 — markup: small-caps source name plus a doxographical report;
  reading: reported cosmology, while the Greek column has no role=`text`
  line. **Disposition: `omit`** (testimonium-only).
- B27 — markup: small-caps source name plus an agricultural report;
  reading: reported advice, while the Greek column has no role=`text`
  line. **Disposition: `omit`** (source is Columella's Latin — no Greek
  at all).
- B27a — markup: small-caps source name plus an agricultural report;
  reading: reported advice, while the Greek column has no role=`text`
  line. **Disposition: `omit`** (source is Columella's Latin — no Greek
  at all).
- B36 — Freeman markup/text: `= 187.`; reading: cross-reference/incipit
  stub. **Disposition: `omit`** — `= 187.` is a cross-reference, not a
  translation; the Greek incipit stub stands alone.
- B44 — Freeman markup/text: `= 225.`; reading: cross-reference stub,
  but this is DK's own double-numbering of the identical maxim
  ἀληθόμυθον χρὴ εἶναι, οὐ πολύλογον under two column tokens (B44/B225).
  **Disposition: `verbatim`** — her B225 English (§225: "One should tell
  the truth, not speak at length") is ported onto B44 via the new
  `text_from` override key rather than re-typed; her B225 entry itself
  is untouched.
- B298 — markup: small-caps source name plus a reported word; reading:
  reported lexical material, while the Greek column has no role=`text`
  line. **Disposition: `omit`** (testimonium-only).
- B298a — Freeman markup/text: `Check carefully the passion accumulated
  in thy breast, and take care not to disturb thy soul, and do not allow
  all things always to the tongue.`; reading: verbatim-looking direct
  maxim. **Disposition: `embedded`** — the Greek maxim survives verbatim
  inside the Demetrius papyrus quotation (the embedded shape: a
  role=`text` witness inside a testimonium's own narration), so her
  English does translate Greek actually printed in this column.
- B300 — markup: merged tetralogy-title dossier whose column carries
  substantive role=`text` witnesses alongside the title list; reading:
  neither a pure title presentation (B5 rejected on review) nor covered
  by any other precedent. **Disposition: `omit`** — deferred pending
  finer-grained English attachment to the merged column's own role=`text`
  witnesses.
- B302a — markup: small-caps source name followed by a direct maxim;
  reading: verbatim-looking maxim, while the Greek column has no
  role=`text` line. **Disposition: `omit`** (source survives only in
  Seneca's Latin — no Greek).
- B304 — Freeman markup/text: `(ib., and Vatican Maxims) I alone know
  that I know nothing.`; reading: verbatim-looking direct maxim with an
  editorial source frame, but the Greek column has no role=`text` line.
  **Disposition: `omit`** — known mistranslation: her English renders
  ἓν μόνον οἶδα ("one thing alone I know"), not a Socratic "know nothing"
  formula.
- B306 — markup: small-caps source name inside a mixed roman/italic
  parenthetical; reading: editorial notice of a fourteen-title list,
  while the Greek column has no role=`text` line. **Disposition: `omit`**
  (testimonium-only).
- B307 — markup: small-caps source name inside a mixed roman/italic
  parenthetical; reading: editorial reference, while the Greek column
  has no role=`text` line. **Disposition: `omit`** (testimonium-only).
- B309 — markup: small-caps source name followed by an attributed
  quotation; reading: reported quotation, while the Greek column has no
  role=`text` line. **Disposition: `omit`** (testimonium-only).

Democritus stage1 build confirmation: 386 spine segments, 372 emitted
English chunks (386 − 14 omitted columns), B44 carrying B225's ported
text, B298a carrying her own.

**Retroactive application (John's 2026-07-23 ruling)**: the same rule was
applied mechanically to the two already-shipped phase-1 works. Five
`note`-kind columns already documented (at the time of their OWN
kind_overrides ruling) as carrying no role=`text` line at all were
unambiguous violations and are now flipped to `omit`: Protagoras B7, and
Xenophanes B4/B13/B19/B40. Every `embedded`-kind column in both works
(Protagoras B2/B5/B6a/B8; Xenophanes B20/B21/B21a/B39/B41) was left
unchanged — each carries a documented single-word-or-phrase role=`text`
survival, which counts as supporting Greek for an `embedded` presentation
even though it is not a full sentence. Protagoras B6 (`note`, but with a
bare-proper-name role=`text` survival, "Euathlus") was deliberately NOT
flipped — flagged for John as a genuinely arguable case, since Freeman's
own English narrates the whole lawsuit story rather than translating the
surviving name itself. Both works' stage1 rebuilt clean after the flip
(Protagoras: 20 segments, 19 chunks, 1 omitted; Xenophanes: 44 segments,
38 chunks, 6 unmatched — the pre-existing 2 edition-gap allowances plus
the 4 newly omitted columns).

**Translation slots**: Freeman is the sole English translation and the
default. Burnet has no Democritus fragment translation to retain in a
secondary slot.

## Burnet-flip batch 1: Anaximander, Anaximenes, Zeno, Melissus, Leucippus

**Chapter identity evidence**: each identity was confirmed from the
sacred-texts collection index before extraction, rather than inferred from
DK numbering. The index links read `12. Anaximander of Milêtus` →
`app14.htm`, `13. Anaximenes of Milêtus` → `app15.htm`, `29. Zênô of
Elea` → `app24.htm`, `30. Melissus of Samos` → `app25.htm`, and `67.
Leucippus of Abdêra` → `app62.htm`. The linked chapter headings repeat
those identities exactly. This confirms in particular that the `appNN`
suffix is the collection-file sequence, not the DK chapter number.

**Source recovery and extraction**: direct network access from the build
environment was unavailable. The five semantic chapter bodies, including
italics, small-caps spans, page markers, footnote anchors, and margin-left
divs, were recovered from the same public sacred-texts mirror used for
Xenophanes and Democritus (`jonnyg23/mahabrain`, commit
`b00aa504cf9a7fb368a040b97ebe9cafca950489`) and compared with the live
sacred-texts renderings. No content discrepancy was found. The reviewed
bodies are retained as `pipeline/tests/fixtures/freeman/app14.htm`,
`app15.htm`, `app24.htm`, `app25.htm`, and `app62.htm`; the checked-in
clean JSON and group-header sidecars were produced by
`pipeline/tools/extract_freeman_wayback.py` with each live Greek spine's
role=`text` column set.

**Anaximander (DK 12)**: Freeman prints B1–B5, all matching DK6 tokens and
all supported by Greek role=`text` runs. Extraction therefore retains five
entries, all `verbatim`, covering 5 of the six-column spine; there are no
group headers. DK6 B6 is absent from Freeman's fifth-edition chapter and is
the sole primary edition gap. Burnet's B1 remains the secondary
translation.

**Anaximenes (DK 13)**: Freeman prints B1, B2, B2a, and B3 in the same order
and numbering as DK6. All four carry Greek role=`text` runs and all four
extract as `verbatim`, giving complete 4/4 coverage. The one level-2 group
header is `(Spurious)` before B3. Burnet's B2 remains secondary.

**Zeno (DK 29)**: Freeman prints B1–B4 in exact DK6 order. All four carry
Greek role=`text` runs and extract as `verbatim`, giving complete 4/4
coverage with no group headers. Burnet's B1–B3 remain secondary.

**Melissus (DK 30)**: Freeman prints B1–B12. B1–B11 match the eleven-column
DK6 spine and are retained; B12 is a Graeco-Syrian English orphan with no
DK30B column and is excluded rather than fabricated onto the spine. All
eleven retained entries are `verbatim`, giving complete 11/11 coverage.
The one level-2 group header is `Spurious` before B11. Sacred-texts prints
the B5 label as `S.`; the extractor corrects this only under the exact
opening `S. If it were not One,`, preserving the same literal-signature
discipline as the Democritus corrections. Burnet's B1–B10 remain
secondary.

**Leucippus (DK 67)**: Freeman prints B1, B1a, and B2, matching all three
DK6 tokens. B1 is the surviving book title inside an attribution context and
is resolved as `title` under the approved Protagoras B5 precedent. B2 is
`verbatim`. B1a is a damaged-papyrus authorship report followed by an
editorial terminology list; the Greek column has no role=`text` run, so
John's standing rule resolves it as `omit`. The italic sentence introducing
that terminology list remains attached to the same omitted dossier rather
than becoming a dangling header before B2. Coverage is therefore 3/3 at
the declared-disposition level and two shipped Freeman entries; there are
no group headers. Burnet's B2 remains secondary.

No known mistranslation was found in the Freeman English retained for
these five works, and no unprecedented classification conflict remains.

## Burnet-flip batch 2: Heraclitus, Parmenides, Empedocles, Anaxagoras

**Chapter identity and source recovery**: the sacred-texts collection
index links `22. Hêracleitus of Ephesus` → `app19.htm`, `28. Parmenides
of Elea` → `app23.htm`, `31. Empedocles of Acragas` → `app26.htm`, and
`59. Anaxagoras of Clazomenae` → `app54.htm`; each linked chapter repeats
that identity in its heading. Thus the collection file number is not the
DK chapter number. The semantic HTML was recovered from the same public
mirror and pinned commit used for batch 1, retaining italics, small caps,
page markers, and footnote anchors in the four corresponding fixtures.

**Heraclitus (DK 22)**: Freeman prints 145 entries. B109 is her bare
`See 95.` cross-reference to a column deleted by DK6 and is excluded;
DK6 B67a is absent from her fifth edition. The retained clean source has
144 entries: 123 `verbatim`, 16 `embedded`, and 5 `omit`.
The omitted entries B4, B37, and B130 survive only in Latin. The
`embedded` rulings cover Greek maxims or reported phrases that survive
inside unmarked source passages; B138 and B139 are also omitted — both
are unmarked columns with no surviving Heraclitean text-role, and Freeman
ships only an editorial description of the late text, not a translation
of it. One level-2 header, `Doubtful and spurious fragments`, precedes
B126a. Exact source corrections restore `S.`→B5, `So.`→B50, the first
printed B83→B81, `I12.`→B112, and `12 7.`→B127; the later B83 remains
B83. Burnet remains secondary with its existing 32 declared gaps.

**Parmenides (DK 28)**: Freeman covers all 26 DK6 columns. Her combined
`7, 8.` heading is split at the next paragraph’s explicit opening of the
remaining Way, yielding B7 and B8 without duplicating text. Small-caps
logical forms such as `it is` are emphasis, not source names. The tally is
21 `verbatim`, 3 `embedded`, and 2 `omit`: B22–B24 translate reported
Greek preserved inside their sources; B18 is a Latin retranslation of
lost Greek and B25 is only a cross-reference to Empedocles B28. The two
level-2 headers are `Doubtful` before B20 and `Spurious` before B21.
Burnet remains secondary with its existing eight gaps.

**Empedocles (DK 31)**: Freeman prints 164 numbered entries. Her combined
`77, 78.` entry attaches to DK6’s compound B77. Her separate B148–B150
prose translations are concatenated, in printed order, onto DK6’s compound
B148. B154b has no DK6 column and is excluded. The reconciled source
therefore has 161 entries: 149 `verbatim`, 9 `embedded`, and 3 `omit`.
B94 is Latin-only and omitted. B156 and B157 are also omitted: Freeman
describes the surviving elegiac verses without translating them, and
Burnet gaps there too — a description is not a translation, so the Greek
ships alone. The other conflicts translate Greek phrases embedded in
later authors.
The level-2 headers are `Doubtful fragments` before B154 and `Spurious
fragments` before B155. Long hexameter runs remain prose paragraphs in
Freeman and attach to their numbered fragment exactly as in Xenophanes.
Burnet remains secondary with its existing fourteen gaps.

**Anaxagoras (DK 59)**: Freeman prints B1–B23, including B21a/B21b.
B20 and the spurious B23 are English-only entries with no DK59B column
and are excluded; the `Spurious` label applies only to excluded B23 and
is likewise absent from the sidecar. The retained 23 entries match the
Greek spine exactly and are all `verbatim`. Burnet remains a complete
secondary translation.

No unprecedented classification conflict remains. No retained Freeman
entry is a known mistranslation, and every shipped entry faces Greek
surviving either as role=`text` or within the cited source passage.

## Phase 3: Thales, Philolaus, Gorgias, Prodicus, Hippias, Antiphon the
## Sophist, Critias

Per the sourcing queue (`docs/phase3-sourcing-queue.md`, ruled by John
2026-07-27), the seven remaining Greek-only fragments works flip to
Freeman-primary English. Chapter identities confirmed from the sacred-texts
collection index: `11. Thales of Milêtus` → `app13.htm`, `44. Philolâus of
Tarentum` → `app39.htm`, `82. Gorgias of Leontîni` → `app77.htm`, `84.
Prodicus of Ceos` → `app79.htm`, `86. Hippias of Êlis` → `app81.htm`, `87.
Antiphôn the Sophist` → `app82.htm`, `88. Critias of Athens` → `app83.htm`.
Source recovery used the same public sacred-texts mirror and pinned commit
as the Burnet-flip batches; the reviewed bodies are retained as
`pipeline/tests/fixtures/freeman/app13.htm`, `app39.htm`, `app77.htm`,
`app79.htm`, `app81.htm`, `app82.htm`, and `app83.htm`.

**Thales (DK 11)**: Freeman prints B1-B4, all matching DK6 tokens. B1's
title-announcement ("(Title: 'Nautical Astronomy')") is letter-spaced Greek
(the disputed book-title token) and ships `title` under the Leucippus B1/
Gorgias B9 precedent. B3 is `verbatim`. B2 and B4 are the two unmarked
columns (later paraphrase, no letter-spacing at all) and ship no English
(`omit`) under John's 2026-07-23 no-greek-support ruling. Coverage: 2/4
columns.

**Philolaus (DK 44)**: Freeman prints all 24 spine columns. B5 was
originally mis-scanned by sacred-texts.com as an unnumbered continuation of
B4 (its leading "5." transcribed as "S."), the same scan-typo class already
corrected for Melissus B5; `_SOURCE_NUMBER_CORRECTIONS` restores it to its
own column (corrected 2026-07-27, Grok verification pass). B15 keeps a
role='text' survival despite wholly-parenthetical presentation (`embedded`,
Protagoras B6a precedent); B18 (the one declared unmarked column: Stobaeus
reports the quotation itself has fallen out) ships no English (`omit`).
Coverage: 23/24 columns.

**Gorgias (DK 82)**: Freeman prints all 34 real columns plus one
English-only orphan (B28, the Graeco-Syrian Maxims saying, matching the
declared `expected_gaps` hole in the spine) -- dropped. B9 is a genuine
unmarked title-only column (Protagoras B8a-h/Hippias B5 precedent), ships
`title`. B13 keeps a role='text' survival (`embedded`). The remaining
eleven conflicted columns (B1, B8a, B11, B11a, B14, B18, B19, B25, B29,
B30, B31) are ordinary unmarked testimonia or unsupported maxims and ship
no English (`omit`). **PARKED, REVIEW-CHECKLIST item 79 (2026-07-27):**
B11 and B11a -- the Encomium of Helen and Defence of Palamedes, Gorgias'
own complete surviving speeches -- were shipped as `verbatim` (this
work's own documented "unmarked but genuine" exception) but that is
invalid: preflight requires `verbatim` to carry at least one role='text'
line, and neither column has one. Freeman's own text also labels both as
summaries, not translations, and there is no `summary` kind. Reverted to
`omit` to keep the build green pending John's ruling; see the manifest's
`kind_overrides` for the same note. Coverage: 23/34 columns.

**Prodicus (DK 84)**: Freeman prints all 11 columns; every one of the
seven conflicted columns resolves `omit` -- six are unmarked testimonia/
maxims with no Prodicus Greek, and B3's title-announcement shape is
disqualified by the work's own `latin_fragments` declaration (its one
marked span is Latin, not Greek). Coverage: 4/11 columns.

**Hippias (DK 86)**: Freeman prints all 20 real columns plus one
English-only orphan (B7, matching the declared `expected_gaps` hole) --
dropped. B5 is a genuine unmarked title-only column (bare Greek title of
the lost Trojan Dialogue), ships `title`. B2, B3, B4, B9, B10, B12, and B17
keep a role='text' survival despite wholly-parenthetical presentation
(`embedded`). The remaining eleven conflicted columns are ordinary unmarked
testimonia and ship no English (`omit`). **Extraction fix**: sacred-texts
prints B16's entry across a page break, splitting it into two wholly-italic
paragraphs; the second half carries no number, no small caps, and no roman
prose, so it reads (correctly, per the extractor's own L2-header taxonomy)
as a bare group-header label rather than a continuation. Content-verified
against the fixture and corrected by hand: the two halves are merged into
one continuous B16 entry in `freeman-hippias.clean.json`, and the bogus
header entry is dropped from `freeman-hippias.group_headers.json`.
Coverage: 9/20 columns.

**Antiphon the Sophist (DK 87)**: Freeman's fifth-edition chapter covers
B1-B81a but has no entries at all for DK6's B82-B117 (36 columns), a
genuine primary-edition gap, before resuming at B118. Sixteen columns
(B4-B8, B12, B16-B24, B24a) are single-word or short-phrase lexical
glosses that each keep a role='text' survival despite wholly-parenthetical
presentation (`embedded`, Protagoras B6a precedent). The ten declared
unmarked columns (B13, B26, B27, B28, B62, B79, B80, B81, B81a, B118) are
ordinary doxographic reports or unmarked Latin narrative with no Antiphon
Greek and ship no English (`omit`). Coverage: 77/126 columns (thin content
matches this work's own "lexicographer desert" character, not a quality
problem).

**Critias (DK 88)**: Freeman prints 75 entries against the 73-column verse/
prose spine: three (B11, B24, B74) match the declared `expected_gaps`
holes, and two more (B12a "From Rhadamanthys", B15a "From Peirithous") are
further Oxyrhynchus-papyrus additions with no DK6 column -- all five
dropped, not fabricated. B30 and B43 are genuine unmarked title-only
columns (Hippias B5/Gorgias B9 precedent), ship `title`. B10, B35, B38, and
B41 keep a role='text' survival despite wholly-parenthetical presentation
(`embedded`). B3, B45, B50, and B52 are ordinary unmarked testimonia and
ship no English (`omit`). Freeman's chapter has no entries at all for B46
or B47 (genuine primary-edition gaps). B59 was originally mis-scanned by
sacred-texts.com as an unnumbered continuation of B58 (its leading "59."
transcribed as "S9."), the same scan-typo class already corrected for
Melissus B5/Philolaus B5; `_SOURCE_NUMBER_CORRECTIONS` restores it to its
own column (corrected 2026-07-27, Grok verification pass). Three
per-fragment paratext labels describing only the dropped Oxyrhynchus
orphans are withheld along with them; the "Doubtful"-style section labels
("Spurious or uncertain", originally before the dropped B74) are
reattached to the next real column (B75) instead, since they genuinely
introduce a run of real columns rather than describing the dropped entry
itself. Coverage: 67/73 columns.

No unprecedented classification conflict remains in any of the seven
works: every conflicted column resolves either via the Protagoras
B6a-embedded precedent, the Hippias B5/Gorgias B9 title-only precedent, the
Gorgias B11/B11a unmarked-but-genuine exception (this work's own
documented finding), or John's 2026-07-23 no-greek-support `omit` ruling.
