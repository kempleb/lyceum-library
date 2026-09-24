# Yonge, *De Fato* ("On Fate") — source verification

Charles Duke Yonge's English translation of Cicero's *De Fato*, extracted
from the archive.org OCR of Bohn's *The Treatises of M. T. Cicero* into
chapter-keyed clean JSON, then split into a true per-section attachment.
Target work: `de-fato` (flat Latin spine, sections 1–48).

**Current build attachment**: `yonge-sections.clean.json` — 48
section-keyed records ("1".."48"), `english.primary.model: archive` in
`manifests/de-fato.yaml`, the same direct-lookup path
cato-maior-de-senectute/laelius-de-amicitia/de-divinatione's Falconer
English use. See "Per-section split" below. `yonge.clean.json` (20
chapter-keyed records) and `concordance.json` (the chapter→section
concordance) are kept for provenance/audit trail only — superseded, no
longer read by any manifest.

Rackham's Loeb *De Fato* (1942) is still in US copyright (post-1930);
Yonge's Bohn translation (1853/1878 printings, translator d. 1891) is the
only public-domain English option, per this project's US-PD rule.

## Witness identity

| | |
|---|---|
| Translator | Charles Duke Yonge (1812–1891), "Literally translated, chiefly by the editor" |
| Publisher | H. G. Bohn, London |
| First printing | 1853 — *The Treatises of M. T. Cicero* (Bohn's Classical Library) |
| Working-OCR printing | 1878 — G. Bell (successor to Bohn's list), same volume, same setting |
| US-PD rationale | Published 1853/1878, translator d. 1891 — safely pre-1931, US public domain regardless of any archive.org copyright-status field |

**Primary/working source**: archive.org item `treatisesofcicer00ciceuoft`
(1878 G. Bell reprint; archive.org's own `possible-copyright-status:
NOT_IN_COPYRIGHT`, `copyright-region: US`). This script reads the item's
own `_djvu.txt` flat OCR:

| File | SHA-256 | Size |
|---|---|---|
| `treatisesofcicer00ciceuoft_djvu.txt` | `c269f19a3bad6d15e8f9b707e522b756a0237f6026b619afc6940683c7af8284` | 1,457,332 bytes (27,302 lines) |

Staged (not committed — raw scan text is never committed) at
`build/yonge-fato/treatisesofcicer00ciceuoft_djvu.txt`:

```
curl -sSL -o build/yonge-fato/treatisesofcicer00ciceuoft_djvu.txt \
  https://archive.org/download/treatisesofcicer00ciceuoft/treatisesofcicer00ciceuoft_djvu.txt
```

**Second witness (proofing)**: archive.org item `treatisescicero00ciceuoft`
(the 1853 H. G. Bohn *first* printing — publisher "H.G. Bohn", date
"1853"). This item has no OCR text layer good enough to diff
mechanically at scale, so proofing was done by rendering and directly
reading its own page IMAGES (not a second OCR pass, which would just add
a second layer of noise) via
`https://ia902800.us.archive.org/BookReader/BookReaderImages.php?...&file=treatisescicero00ciceuoft_jp2/treatisescicero00ciceuoft_{leaf:04d}.jp2&scale=4`,
leaf = printed page + 10 (verified: printed p. 264 ↔ leaf 274 via the
item's own back-of-book index entry "Hirtius Pansa, 264,"; printed p. 282
↔ leaf 292, confirmed independently via the unique word "declinations").

## 1853/1878 letter-identity check

The brief asked for a 3-chapter spot check; this pass went further and
read **all 19 printed pages (264–282, all 20 chapters)** of the 1853
scan's own page images directly, word by word, against the 1878-sourced
OCR text used for extraction. Every substantive wording match — chapters
I, X, and XX (first, middle, last, the three explicitly requested) show
byte-for-byte identical prose modulo this OCR pass's own defects (see
below); the same holds for the other 17 chapters checked incidentally
during the full proofing pass. **Result: same plates, no revision-era
wording drift between the 1853 first printing and the 1878 reprint** —
the two are typographically identical text, differing only in which scan
happens to have cleaner OCR.

## Extraction pipeline

`pipeline/tools/extract_yonge_fato.py` (tests:
`pipeline/tests/test_extract_yonge_fato.py`, 15 tests, offline/synthetic).
Deterministic against the pinned SHA-256 above. Method (see the module
docstring for full detail):

1. Locate the *On Fate* span by three corpus-unique literal anchor
   strings (verified via direct search before being hardcoded): the
   preface heading (excluded), `[The commencement of this treatise is
   lost.]` (kept — start of chapter I), `[The rest of this treatise is
   lost.]` (kept — end of chapter XX). The translator's preface
   ("PREFACE BY THE ORIGINAL TRANSLATOR.") is dropped structurally, never
   shipped. Both in-body asterisk lacuna markers (chapter I's opening,
   chapter III's opening) are genuine typeset `* * *` in the 1853 scan;
   the clean store normalizes them to `...` (John, 2026-07-24 — see
   "Declared normalizations" below).
2. Strip 20 page-apparatus lines (18 running headers, several OCR-garbled
   — "OX FATE. Z6y" for "ON FATE. 269" — plus 2 printer's signature marks,
   "DE NAT. ETC. T" and "T 2") and 2 per-page footnotes (dropped whole,
   matching this corpus's house convention — see "Footnotes" below).
3. Segment into the 20 roman-numeral chapters (I–XX), asserting the exact
   strict sequence.
4. Apply the OCR-proofing fix table (below) — every entry a literal,
   corpus-unique substring substitution, each asserted to match exactly
   once; an unmatched or duplicated key raises loudly.

## OCR proofing pass (mandatory, per brief)

**Full-page-image comparison, not a sample**: all 19 printed pages
(264–282) of the 1853 scan were fetched as page images and read directly,
covering all 20 chapters in full (not just first/last sentence + 5
chapters — every word of every chapter was checked against the image).

**Error rate**: 127 confirmed OCR-layer defects (126 found in the original
proofing pass + 1 found post-commit by the Grok content gate, 2026-07-21 —
see the "O Chrysippus" row in the defect table below) across 7,792 words
(≈1 per 61 words, ≈6.7 per page). **Zero print-level errata** — every defect
is an artifact of this particular OCR pass, not an error in the 1853/1878
printed text itself (confirmed by the 1853 image always showing correct,
readable print at every defect location); `PATCHES.json` is accordingly
empty. **No text was ever lost or unrecoverable** — every defect is a
single-token letter/digit/punctuation substitution or a dropped line-wrap
hyphen, never a dropped sentence, contaminating marginal text, or an
unrecoverable gap (the categorical difference from the Rackham *De
Finibus* "STOP, do not ship" precedent, which had gloss-bleed
contamination and genuine translated-text loss). All 20 chapters are
complete and structurally intact. Judged against the brief's "generally
clean" bar and its STOP condition: **not stopped** — the defect count is
higher than the recon's plain-prose expectation, but every single
instance is a mechanical, image-verified, single-token OCR slip with the
underlying correct text directly legible in the scan, not a
quality-of-translation or completeness problem.

Defect categories (see the extractor's `_DEFECT_FIXES`,
`_HYPHEN_REJOINS`, `_DROPPED_HYPHEN_REJOINS`, `_QUESTION_MARK_FIXES` for
the full cited table, one entry per defect, each keyed to its printed
page):

| Category | Count | Example |
|---|---|---|
| Line-wrap hyphen rejoins (explicit "-" in OCR) | 10 | `Pos'do-\nnius` → `Posidonius` |
| Line-wrap hyphen rejoins (hyphen glyph dropped entirely by this OCR pass) | 65 | `sub\nmitted` → `submitted`; `every\nthing` → `everything` |
| Letter/word/punctuation substitutions | 32 | `veiy` → `very`; `Mara` → `Mars`; `thut` → `that` |
| "?" misread as bare digit "1" (systematic scan defect) | 15 | `why is it so 1 It` → `why is it so? It` |
| Vocative "O" misread as digit "0" (found post-commit by Grok content gate, 2026-07-21) | 1 | ch. 7 `0 Chrysippus` → `O Chrysippus` |
| Greek restorations | 4 | see below |

The 65-item dropped-hyphen category was found by a systematic
dictionary-backed sweep (every line-final short fragment in the span,
cross-checked against `/usr/share/dict/words` plus common-suffix
stripping for inflected forms the dictionary lacks) rather than by eye —
this OCR pass loses the hyphen glyph at a real line-wrap more often than
it keeps it. Several dictionary-flagged candidates were **rejected** as
genuine two-word text after context review, not joined: "many ways",
"For how", "he. In", "be known", "over all", "hero in", "am a", "set
Her" (the last two inside Ennius quotations, where the line break is a
verse-line break, not a hyphenation split).

## Greek restorations

Four mangled Greek runs, each hand-verified against the 1853 page image
AND cross-checked against the PHI Latin spine's own Greek-in-Latin runs
(`build/dist/de-fato/book-01.json`, which carries the identical Greek
terms embedded in Cicero's Latin — a double witness, not a guess):

| OCR (1878 scan) | Restored | Latin-spine cross-check | Page |
|---|---|---|---|
| `a^ico/mra` | ἀξιώματα | section 1: the spine's own embedded ἀξιώματα (in a "what the Greeks call…" frame) | 264 |
| `^ecDpf/jMara` | θεωρήματα | section 11: the spine's own embedded θεωρήματα (same naming frame) | 268 |
| `eAc^ta-ros` | ἐλάχιστος | section 22: the spine's embedded ἐλάχιστον (cognate form of the same term) | 273 |
| `apyos Aoyos` | ἀργὸς λόγος | section 28: the spine's own embedded ἀργὸς λόγος | 275 |

(The Latin context around each Greek term is deliberately not quoted here —
only the Greek terms themselves, which the spine embeds and which are the
objects of the restoration, appear; the surrounding Latin frames are described
structurally per the no-corpus-text rule.)

No unrecognized Greek-looking garble remains — every non-ASCII-suspect
run in the span was accounted for by one of these four table entries.

## Footnotes

Two per-page footnotes exist in the span, both dropped whole (matching
this corpus's house convention — Falconer/Miller/Yonge-ND all drop
footnotes wholesale): footnote to "ethics" on p. 264 ("From ἦθος"), and a
textual note on p. 266 ("A good deal of the original is lost here" —
anchored to "so begin.¹" at the end of chapter II / start of chapter
III's own in-text lacuna marker, not a separate loss). Neither
carries translated Ciceronian prose; both are the Bohn editor's own
apparatus.

## Output

- `yonge.clean.json` — 20 records `{chapter: 1..20, text}`, SHA-256
  `ae74b5e9f254c9f1101f86b41ddf2a55b06dfda3ab70fd27e0c1cfa00d3491b2`
  (post John 2026-07-24 asterisk→ellipsis normalization — see "Declared
  normalizations" below; this supersedes
  `2095df7ba88e2bad4be3b16c9b857c7b4cda7d769d4356e0e333349bc6ac662f`,
  itself post "O Chrysippus" 2026-07-21). Superseded for build purposes by
  `yonge-sections.clean.json` below; kept for provenance.
- `concordance.json` — 20 records `{chapter, start_section, exact,
  section_position, anchor_lat_sha256_16, anchor_lat_note, anchor_en}`,
  SHA-256 `db47c00c5cec2f724f816771638db5ba95abb4ee553e4f54c0efa39d740f59a7`.
  Superseded for build purposes by the per-section split below; kept for
  provenance (it is the audit trail the split was checked against, not a
  live build input — no manifest declares it any more).
- `sections.proposed.json` — the pre-promotion working file (48 records
  under a `sections` key plus a `_comment` marking it "NOT wired to the
  manifest — pending content verification"). Kept as the audit trail;
  `yonge-sections.clean.json` below is its promoted, manifest-wired form
  (the same 48 section texts, re-keyed to a plain `{"1".."48": text}`
  dict with no wrapper/comment key, since `stage1_common.load_english_
  source`'s dict shape is consumed as-is and `validate_english_source`
  would otherwise reject a stray `_comment` key as an unmatched source
  key).
- `PATCHES.json` — empty (no print-level errata found).

## Per-section split (current build attachment)

`yonge-sections.clean.json` — 48 records keyed `"1".."48"`, one per PHI
Latin section, SHA-256 `f4650658c4029c81000dbb50e75beeb064c52af197d1d30128299da53875b26e`
(post John 2026-07-24 declared normalizations — asterisk→ellipsis and
one orphaned trailing section-break dash; this supersedes
`9f944cc97979c1daf440c32c2b096241fb925426d46b7fb1623509af7ccfd774`).
Wired via `english.primary.model: archive` +
`english.primary.file: yonge-fato/yonge-sections.clean.json` in
`manifests/de-fato.yaml` — the direct 1:1 column-keyed lookup
`pipeline/reader_pipeline/stage1_flat_english.py` already uses for every
other flat-scheme work (no dedicated builder needed, unlike the
chapter-concordance attachment this supersedes).

**Derivation**: `sections.proposed.json`, produced by content-anchored
sentence-boundary splitting of the 20 chapter-keyed records in
`yonge.clean.json` against the 48-section Latin spine — every one of
Yonge's 20 chapters was cut at the sentence boundary nearest the Latin
section break the chapter→section concordance above already located, so
a chapter's prose that straddles more than one Latin section (the
"mid"/"end" `section_position` rows in the concordance table) is
distributed sentence-by-sentence across the sections it actually spans,
rather than riding a single "sections N–M" span label the way the
superseded chapter-concordance attachment did.

**Straddle rule**: at each cut point, a sentence is assigned wholly to
the Latin section its content corresponds to (never split mid-sentence);
where a single English sentence answers to Cicero's own argument spanning
a section break, it is kept with the section its main clause opens in.

**Verification**: Grok content-audit pass over all 48 boundary cuts found
2 boundary defects (a sentence assigned to the wrong side of its
neighboring section break), both fixed and machine-reverified. The
split itself is **byte-complete** against the pre-normalization chapter
text (no drops or duplicates at cut time). After the John 2026-07-24
declared normalizations below, the live section store diverges from
`yonge.clean.json` by the one orphaned trailing section-break dash
removed only from section ends (asterisk→ellipsis is applied in both
stores).

## Declared normalizations (John, 2026-07-24)

Post-extraction text normalizations on the Yonge English (same
superseded-hash pattern as the 2026-07-21 ch. 7 "O Chrysippus" OCR fix).
Not OCR defects — deliberate presentation choices after the per-section
split. Cited rulings:

1. **Asterisk elision → ellipsis.** Yonge typesets lacuna/elision as
   `* * *` (confirmed genuine typeset asterisks, not OCR). John:
   "Yonge uses *** where we would use ... so let's replace the *** for
   elision with a proper ellipsis." Form: ASCII `...`, matching this
   work's existing elision at section 45 and the Falconer/Miller Cicero
   English stores (Unicode `…` is used in some other Yonge works; this
   file already used `...`).

   | Site | Location | Before → after (snippet) |
   |---|---|---|
   | 1 | ch. 1 / sec. 1 | `[The commencement of this treatise is lost.] * * * THAT branch…` → `…lost.] ... THAT branch…` |
   | 2 | ch. 3 / sec. 5 | `Let us consider here * * * in some of which…` → `…here ... in some of which…` |

   Count: **2** replacements (all occurrences in the De Fato English).

2. **Orphaned trailing section-break dashes.** Yonge's em-dashes that
   marked section breaks (used when splitting chapter prose into the
   48-section store) were left at the end of the preceding section after
   the cut. John: remove only a dash at the very end of a section's
   English; do not touch mid-text em-dashes (legitimate sentence-internal
   Yonge usage). Applied only to `yonge-sections.clean.json` /
   `sections.proposed.json` (the chapter store keeps the mid-prose dash
   between what became sec. 1 and sec. 2).

   | Site | Location | Trailing snippet removed |
   |---|---|---|
   | 1 | sec. 1 | `…for the following reason. —` → `…for the following reason.` |

   Count: **1** removal (the only section-end match; every other em-dash
   in the English is mid-text).

## Concordance methodology

Built by direct philological comparison — **not** consulting Rackham's
English at any point — of each chapter's opening English sentence against
the PHI flat Latin spine's 48 sections (`build/dist/de-fato/book-01.json`,
Mueller 1890 Teubner text). Every one of the 20 chapters was matched
against a literal, hand-located Latin phrase in its declared section —
**PHI Latin is licensed corpus text and is never committed**, including
here: `concordance.json` stores only `anchor_lat_sha256_16` (the first 16
hex characters of the whitespace-normalized Latin phrase's sha256 digest —
`dk_lang.decision_key`'s own convention, reused independently) and
`anchor_lat_note` (a short, non-verbatim structural label: word count,
whether the phrase ends at a full stop/question mark/mid-clause, whether
it carries an embedded Greek term). The literal Latin phrases themselves
exist only in the hand-verification notes that produced this table, never
in any committed file. `anchor_en` stays verbatim — Yonge's translation is
the sanctioned public-domain text this pipeline exists to ship. The
extractor's `_self_check_concordance` re-verifies every anchor's HASH
still matches some word-bounded substring of its declared section
whenever the Latin-spine build artifact is present (it's gitignored, so
this is a live bonus check, not the basis of the table — the table itself
is the declared, cited result of the original comparison); the check
hashes candidate substrings read live from that local build artifact and
never stores or prints the literal Latin.

`start_section` is the Latin section ACTIVE (already begun, not
necessarily just-begun) at the point the English chapter opens — Yonge's
20 chapter breaks don't land on Cicero's 48 section breaks one-for-one.
`section_position` records whether the matched anchor sits at the
`start`, `mid`, or `end` of its section:

Latin anchors are never quoted here (PHI is licensed, never-committed
corpus text) — each row gives the anchor's `anchor_lat_sha256_16` /
`anchor_lat_note` pair from `concordance.json` plus the (sanctioned,
verbatim) English anchor it was matched against:

| Chapter | Start section | Position | Latin anchor hash | Note | English anchor (short) |
|---|---|---|---|---|---|
| I | 1 | start | `511e2cad50c26f79` | 8w, incl.-Greek-term, mid-clause | THAT branch of philosophy which... the Greeks usually term ethics |
| II | 3 | start | `fa7fb458d0b7b749` | 13w, mid-clause | Since you have not, as I hope, abandoned your oratorical studies |
| III | 5 | start | `a70714829a1ea426` | 7w, mid-clause | in some of which, as in the case of Antipater the poet |
| IV | 7 | start | `4e71549bf86d5e22` | 13w, mid-clause | let us... dismiss Posidonius... turn our attention to the sophisms of Chrysippus |
| V | 9 | start | `e40f71e4b1f655c7` | 13w, mid-clause | he shows that he does not understand the true question, nor its principal difficulties |
| VI | 11 | mid | `859fdf37f9341363` | 9w, ends-'?' | If you insist on the reality of divination... from what perceptions of art does it proceed? |
| VII | 13 | start | `799470589a67eed7` | 14w, mid-clause | this consequence... is by no means agreeable to you, O Chrysippus... your main dispute with Diodorus |
| VIII | 15 | start | `6970dfbb7288e0ba` | 9w, mid-clause | On this topic Chrysippus exerts all his ingenuity. He pretends that the Chaldeans are deceived |
| IX | 17 | start | `0d82867eb35b4db8` | 10w, incl.-Greek-term, mid-clause | let us return to the question concerning possibility, so warmly contested by Diodorus |
| X | 20 | mid | `0c00b7b7e7a66f8b` | 5w, ends-'.' | This is all that we need say concerning possibility. Let us pass on to other matters. |
| XI | 23 | mid | `270917744d9b60bc` | 13w, mid-clause | Carneades argued more acutely when he taught that the Epicureans might defend their cause without this imaginary declination of atoms |
| XII | 26 | end | `d64e799ad2661c6d` | 16w, mid-clause | The dispute then is at an end... grant either that all things happen by fate, or that some effects may exist without external causes |
| XIII | 29 | mid | `bd5f9d0774d0a61f` | 9w, mid-clause | Very properly, therefore, is this argument called inactive |
| XIV | 31 | start | `486cf4eaa4767d0d` | 13w, mid-clause | Carneades, however, absolutely rejects this method of reasoning... adopted too hastily |
| XV | 33 | end | `e2f9df6491f057d9` | 19w, mid-clause | Wherefore if the Stoics, who maintain that everything happens by fate... admit the truth of oracles of this kind |
| XVI | 36 | start | `514cc8ab35f6d432` | 23w, mid-clause | there is a difference, say they, between a cause without which an effect cannot happen, and a cause which necessarily produces an effect |
| XVII | 39 | start | `57bf162d6dfdb910` | 10w, mid-clause | It appears, indeed, to me, since the ancient philosophers are divided into two parties on the doctrine of fate |
| XVIII | 41 | start | `5c71714e4df73be2` | 16w, mid-clause | Chrysippus, rejecting necessity... distinguishes causes into two kinds |
| XIX | 43 | start | `ccfb6a9cebe5d0d6` | 11w, mid-clause | a man who pushes a cylinder gives it a principle of motion, but not immediately that of |
| XX | 46 | start | `a35676a0f20da3a8` | 16w, mid-clause | It is according to these principles that we should examine the question concerning fate... rush with Epicurus to a fortuitous concourse of atoms |

**Gates**: chapter 1 → section 1 (holds by construction/definition —
also independently confirmed as the literal opening sentence of both
texts). Strictly increasing (1, 3, 5, 7, 9, 11, 13, 15, 17, 20, 23, 26,
29, 31, 33, 36, 39, 41, 43, 46). Chapter XX starts at section 46 and its
English content runs through the rest of section 48 (confirmed
independently: both the English and the Latin text end with the SAME
trailing-lacuna convention — English `[The rest of this treatise is
lost.]`, Latin section 48's own text ending in ". . . ." — matching
`build/dist/de-fato/manifest.json`'s `segments: 48`). **All 20 mappings
are content-anchored** (a literal matching phrase was hand-located in
both languages; the Latin side is stored only as a hash + non-verbatim
note, per PHI's licensing — see "Concordance methodology" above); none
are interpolated — the brief's "aim for all-20 content-anchored given the
small size" was met in full.
