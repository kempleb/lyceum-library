# R. G. Bury — Sextus Empiricus, *Against the Logicians* I 65–87 (Gorgias, DK 82 B3)

Vendored English for Gorgias' *On Not-Being* as Sextus reports it
(*Adversus Mathematicos* VII 65–87 = *Against the Logicians* I 65–87), which
DK prints as 82 B3. For use against work `gorgias-fragments`, column B3, in
place of Kathleen Freeman's outline of the argument (review item 85). See
`sources/INVENTORY.md`'s "Gorgias B3" entry.

**Not public domain.** Published 1935, after the US cut-off. It is used under
the owner's ruling below, the same treatment as J. A. Smith's *De Anima*
(1931) and W. H. Fyfe's *Poetics* (1932) (see CLAUDE.md, hard rules).

## Ruling (John, 2026-09-24)

John chose Bury's Loeb translation for B3 and accepted its grey-area status:

> If we're fine with grey area for other works that are almost pd, I'm fine
> with that for gorgias b3

Licence string: **`unverified`**. No public-domain claim is made, in this
file, the manifest, or on the site.

## Attribution string

> R. G. Bury, trans., Sextus Empiricus, vol. II: Against the Logicians (Loeb
> Classical Library; London: Heinemann; Cambridge, MA: Harvard University
> Press, 1935)

## Source

| | |
|---|---|
| Translator | Rev. Robert Gregg Bury (1869–1951) |
| Edition | *Sextus Empiricus*, with an English translation by R. G. Bury, vol. II: *Against the Logicians* (Loeb Classical Library) |
| Publisher | London: William Heinemann Ltd; Cambridge, MA: Harvard University Press |
| Printing | First printing, 1935: the scan's title page reads MCMXXXV, with no reprint or revision line |
| Passage | *Against the Logicians* I 65–87 (= *Adv. Math.* VII 65–87), print pp. 35–45 (English on the odd pages) |
| Working text | John's cleaned OCR, `~/Downloads/Sextus Empiricus Vol II Against the Logicians.txt` (7,784 lines; SHA-256 `cee00858a527cd15f405822cc4dc85ca08a2825528707824155dcc5a36b3b829`), lines 609–777 |
| Check witness (scan) | archive.org `in.ernet.dli.2015.183448`, local copy `~/Documents/lyceum-sources/bury-sextus-logicians/bury-logicians.pdf` (SHA-256 `fe2dd9627cf74dbbd1fffbbbb76a144c271ce0dd72ecacacb728eb19b2a4c30e`) |
| Check witness (raw OCR) | the same item's `_djvu.txt`, local copy `bury-logicians_djvu.txt` in that folder (SHA-256 `7f0d435d3fb4ffaaf7b0d17d8dd43dc0677d969ab123e89ff5a46bc854f8dc3c`), lines 1672–2277 |

Neither the working text nor the scan is vendored here. Bury's Greek (the
facing pages) is never used or shipped: our Greek for B3 is DK's.

## Shape

`bury-b3.clean.json`: one flat JSON array, `[{"section": n, "text": "..."}]`,
the same shape as `sources/parnassos-gorgias/*.clean.json`, except that
`section` is the Sextus section number, 65–87 (23 records, contiguous), not a
count from 1. Text only: plain Unicode, no markup, no notes.

| | |
|---|---|
| Sections | 65–87, 23 records, none empty |
| Words | 1,769 in all; per section 45 (§82, §87) to 132 (§73) |
| Characters | 237 to 700 per section, mean 428 |
| Reads | continuously from "Gorgias of Leontini belonged…" to "…explained to another person." |

## Extraction

A short script over John's cleaned file, lines 609–777 (kept outside the repo;
the steps are all here):

1. Dropped page furniture: page numbers, `---` rules, the running heads
   ("AGAINST THE LOGICIANS, I. 67-71" and so on, "SEXTUS EMPIRICUS"), and every
   line holding Greek (the facing Greek pages and their critical notes).
2. Dropped footnote lines and footnote markers (`$^a$`).
3. Joined what was left with single spaces. Bury's own paragraph breaks fall
   inside sections, so they are not kept; each section is one string, as in
   the Parnassos files.
4. Removed Bury's margin section numbers, bare ("as 65 those") and bold
   ("**68**").
5. Mended three words the print breaks with a hyphen at a margin number:
   "any- 77 thing" → "anything", "Further- 80 more" → "Furthermore",
   "incom- 83 municable" → "incommunicable".
6. Stripped Markdown emphasis to plain text (*Concerning the Non-existent*,
   *Concerning Nature*, *vice versa*).
7. Made quotation marks and apostrophes the print's curly forms. John's file
   mixes straight and curly (`one's` but `one another’s`; straight quotes
   around "to be thought", curly around the syllogism in §78).
8. Split into sections at the opening words listed below.

## Corrections to John's text

One, found by the machine check for a hyphen followed by a space:

- **§75**, "For if the non- existent exists" → "For if the non-existent
  exists". The print hyphenates the word across the page turn (p. 39 ends
  "For if the non-", p. 41 begins "existent exists"); John's file keeps the
  two halves on different pages, and joining them left a space.

Every other word agrees with the scan. A word-by-word comparison with the
archive.org OCR (difflib, hyphens and punctuation ignored) leaves 19
differing spans, each a fault in the raw OCR where John's reading is the
print's: "1t"/"it" (twice), "lime"/"time", "ahd"/"and", "properly"/"property",
"Yor"/"For", "begining"/"beginning", "infinte"/"infinite", "1s"/"is" (three
times), "diserete"/"discrete", "Tor"/"For", "existsit"/"exists it"; three runs
of Greek-page noise the OCR read as letters; and two words ("Further-more",
"incom-municable") the OCR could not rejoin because a margin number stands
after the hyphen.

## Section boundaries

Bury prints his section numbers in the margin, level with the printed line
in which a section starts, not at the word; on the Greek pages the number
often stands beside a line that opens with the end of the previous section
(e.g. 70 beside "ὥστε οὐκ ἔστι που τὸ ἄπειρον. καὶ μὴν οὐδ'…"). Each
boundary below is set where the section opens in DK's Greek, which is our
Greek for B3 (the inline "(66)"…"(87)" in
`build/dist/gorgias-fragments/book-01.json`, column `1:B3`), and checked
against the numbers on Bury's facing Greek pages. Where the Greek section
opens mid-sentence, so does the English.

| § | Opens (Bury) | DK's Greek opens | Note |
|---|---|---|---|
| 65 | Gorgias of Leontini belonged… | Γ. δὲ ὁ Λεοντῖνος… | DK prints no "(65)"; §65 is the unmarked start of the column |
| 66 | Now that nothing exists, he argues… | ὅτι μὲν οὖν οὐδὲν ἔστιν | |
| 67 | Now the non-existent does not exist. | καὶ δὴ τὸ μὲν μὴ ὂν | |
| 68 | Furthermore, the existent does not exist either. | καὶ μὴν οὐδὲ τὸ ὂν ἔστιν | |
| 69 | for everything created has some beginning… | τὸ γὰρ γινόμενον πᾶν | mid-sentence, after "it has no beginning;" |
| 70 | Nor, again, is it encompassed by itself. | καὶ μὴν οὐδ' ἐν αὑτῶι | |
| 71 | Nor, again, can the existent be created. | καὶ μὴν οὐδὲ γενητὸν | |
| 72 | In the same way, it is not both together… | κατὰ τὰ αὐτὰ δὲ | |
| 73 | Moreover, if it exists, it is either one or many… | καὶ ἄλλως, εἰ ἔστιν | |
| 74 | Yet neither is it many. | καὶ μὴν οὐδὲ πολλά | |
| 75 | and that they do not both exist… | ὅτι δὲ οὐδὲ ἀμφότερα | mid-sentence, after "…nor the non-existent exist;" |
| 76 | And what is more, if the existent is identical… | οὐ μὴν ἀλλ' εἴπερ | |
| 77 | In the next place it must be shown… | ὅτι δὲ κἂν ἦι τι | |
| 78 | Consequently, this is a sound and consistent syllogism… | διόπερ ὑγιὲς | |
| 79 | for if the things thought are existent, all the things thought exist… | εἰ γὰρ τὰ φρονούμενά | mid-sentence, after "…is plain;" |
| 80 | Furthermore, if the things thought are existent… | πρὸς τούτοις | |
| 81 | And just as the things seen… | ὥσπερ τε | |
| 82 | If, then, a man thinks… | εἰ οὖν φρονεῖ | |
| 83 | And even if it should be apprehended… | καὶ εἰ καταλαμβάνοιτο | |
| 84 | For the means by which we indicate is speech… | ὧι γὰρ μηνύομεν | |
| 85 | and not being speech it will not be made clear… | μὴ ὢν δὲ λόγος | mid-sentence, after "…it will not become our speech;" |
| 86 | Moreover, it is not possible to assert… | καὶ μὴν οὐδὲ ἔνεστι λέγειν | |
| 87 | Such, then, being the difficulties raised by Gorgias… | τοιούτων οὖν | |

## Notes and Greek-text differences

Excluded, per the text-only rule. Those bearing on the wording:

- **§73**, footnote on "discrete quantity": "i.e. a quantity, or number,
  which is divisible." Bury's gloss on his rendering of ποσόν.
- **§77**, footnote on "the existent is not thought": "Cf. P.H. ii. 64."
  A cross-reference only.
- **§67**, a Greek-page critical note (οὐδὲ 〈τοίνυν〉: 〈τοίνυν〉 οὐδὲ cj.
  Bekk., Mutsch.). About the Greek only; no bearing on the English.

Bury translates his own Greek (Bekker's text with the Teubner editor's
corrections, per his prefatory note), not DK's. The two differ in small
points: DK adds 〈μὴν〉 in §78 and omits Bury's bracketed [ὂν] in §69. Both
bracket εἰ δέ ἐστι, φαῦλον in §79, and Bury's English leaves it untranslated.
None of these moves a section boundary.

## Verification

- 23 records, `section` 65–87 in order, no gaps or repeats, no empty text.
- The joined text starts "Gorgias of Leontini" and ends "explained to
  another person."
- Zero Greek-block code points (U+0370–03FF, U+1F00–1FFF), zero digits, zero
  running-head words (AGAINST, LOGICIANS, SEXTUS, EMPIRICUS), zero Markdown
  or footnote characters (`* _ $ ^ [ ] < >`), zero straight quotes, no double
  spaces, no hyphen followed by a space.

- Checked word by word against the scan, print pp. 35–45, by Grok
  (2026-09-25): no differences. Grok raised two doubtful readings, and
  both were settled at 600 dpi in favour of this file: §76 "nothing
  exists ; for" is a semicolon in the print, and §67's "and" carries an ink
  speck, nothing more.

## Wiring

Wired into `manifests/gorgias-fragments.yaml` as the B3 entry of
`english.column_sources` (commit 84741cf) with `unmarked_lead: true`: §65
is printed with no "(65)", as DK prints none, and the "(66)"–"(87)"
markers must equal the Greek's markers as a set. `citation.section_paragraph_columns`
breaks both columns at those markers. Freeman's outline stays reachable as
the "Freeman (summary)" alternate. Credit line (John, 2026-09-25):
translator "R. G. Bury", source "Sextus Empiricus II: Against the
Logicians (Loeb Classical Library)", year 1935, no licence.
