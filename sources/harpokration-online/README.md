# Harpokration On Line — Harpocration, *Lexicon in decem oratores*, the entries DK quotes

Vendored English for the Harpocration passages in the DK works that an audit
of the English against DK's Greek classed as matching: 32 passages, 31
entries (Antiphon B14 and B63 both quote *s.v.* διάθεσις).

Read by `pipeline/reader_pipeline/stage1_context_english.py` as the source
pair ("Harpocration", "Lexicon in Decem Oratores"), credit
"Harpokration On Line (CC BY 4.0)" (draft, pending the owner's approval; see
Attribution below).

**Licence: Creative Commons Attribution 4.0 International (CC BY 4.0).**
Licence string: `CC BY 4.0`. Not public domain: the translations date from
2015–2016.

## Source

| | |
|---|---|
| Project | Harpokration On Line (HOL), a collaborative translation of Harpocration's *Lexicon of the Ten Orators*, Duke Collaboratory for Classics Computing (DC3) |
| Site | https://dcthree.github.io/harpokration/ (fetched 2026-09-27; SHA-256 `8efd1435ddac3f7c384236e37e216b8288f91bbeaee4b149c516f4e7086e354f`) |
| Data | https://github.com/dcthree/harpokration-data, `Harpokration CITE Translation.csv` (fetched 2026-09-27; SHA-256 `478c7b5e5fb1e1275463412e946c535741ba0776ca0b689a750071c14b15eb41`) |
| Greek HOL translates | TLG 1389.001, Dindorf (Oxford, 1853); the site footer says "Greek text courtesy of TLG" |

Neither fetched file is vendored here. HOL's Greek is never used or shipped;
our Greek is DK's.

## Licence statements, verbatim

The site footer (https://dcthree.github.io/harpokration/):

> Greek text courtesy of TLG. By contributing a translation you agree to
> licensing your translation under a Creative Commons Attribution 4.0
> International License.

Each translation on the site carries a `rel="license"` link to
http://creativecommons.org/licenses/by/4.0/ with the CC BY 4.0 badge.

The data repository's README (https://github.com/dcthree/harpokration-data):

> Translations licensed under a Creative Commons Attribution 4.0
> International License.

(The MIT licence in https://github.com/dcthree/harpokration covers the site's
code, not the translations.)

Licence: https://creativecommons.org/licenses/by/4.0/ (legal code:
https://creativecommons.org/licenses/by/4.0/legalcode).

## Attribution

CC BY 4.0 §3(a) asks anyone sharing the material to keep: the name of each
creator, a copyright notice, a notice that refers to the licence, a notice
that refers to the disclaimer of warranties, a link to the material where
reasonably practicable, a note that the material was changed (and how), and
a link to the licence. It may be met "in any reasonable manner", including a
link to a page that holds the information.

Wording for the full attribution, where a page or colophon can carry it:

> English translation of Harpocration's *Lexicon of the Ten Orators* from
> Harpokration On Line (https://dcthree.github.io/harpokration/), by Joshua
> D. Sosin, John-Paul Smith-MacDonald, Mackenzie Zalin, Matthew Farmer and
> Stelios Chronopoulos, licensed under CC BY 4.0
> (https://creativecommons.org/licenses/by/4.0/). Shortened to the words DK
> quotes ("…" marks each cut); straight quotation marks made curly.

The translators of each entry are in the table below.

## Shape

`harpokration-online.clean.json`: one JSON object with two keys.

- `entries`: headword as HOL spells it (lower case, as in HOL's CTS URN
  `urn:cts:greekLit:tlg1389.tlg001.dc3:<headword>`, with HOL's `_` read as a
  space) → the English of one HOL translation, one paragraph.
- `dk_spellings`: DK's spelling of a headword where it differs from HOL's →
  HOL's headword (here only capitalised proper names).

A span's locus is `s.v. <headword>` in DK's spelling.

| Headword | HOL translation (`urn:cite:dc3:…`) | Translators | DK column |
|---|---|---|---|
| ἀναξαγόρας | harpocration.171.1 | Sosin, Smith-MacDonald, Zalin | anaxagoras-testimonia A2 |
| ἄοπτα | harpocration.216.1 | Sosin, Smith-MacDonald, Zalin | antiphon-sophist-fragments B4 |
| ἀπαθῆ | harpocration.218.1 | Sosin, Smith-MacDonald, Zalin | B5 |
| δεήσεις | harpocration.1184.1 | Sosin, Smith-MacDonald, Zalin | B11 |
| διάθεσις | harpocration.1359.1 | Farmer, Sosin, Smith-MacDonald, Zalin | B14, B63 |
| ἔμβιος | harpocration.557.1 | Sosin, Smith-MacDonald, Zalin | B15 |
| ἀναποδιζόμενα | harpocration.172.1 | Sosin, Smith-MacDonald, Zalin | B18 |
| ἀνήκει | harpocration.190.1 | Sosin, Smith-MacDonald, Zalin | B19 |
| ἐπαλλάξεις | harpocration.619.1 | Sosin, Smith-MacDonald, Zalin | B20 |
| ὀριγνηθῆναι | harpocration.930.1 | Sosin, Smith-MacDonald, Zalin | B21 |
| διάστασις | harpocration.1306.1 | Sosin, Smith-MacDonald, Zalin | B23 |
| ἀδιάστατον | harpokration.30.1 | Sosin, Smith-MacDonald, Zalin | B24 |
| πεφοριῶσθαι | harpocration.1384.1 | Farmer, Sosin, Smith-MacDonald, Zalin | B33 |
| ἄβιος | harpokration.2.2 | Chronopoulos (version 2 of Sosin, Smith-MacDonald, Zalin's harpokration.2.1) | B43 |
| σκιάποδες | harpocration.1239.1 | Sosin, Smith-MacDonald, Zalin | B45 |
| μακροκέφαλοι | harpocration.721.1 | Sosin, Smith-MacDonald, Zalin | B46 |
| ὑπὸ γῆν οἰκοῦντες | harpocration.1037.1 | Sosin, Smith-MacDonald, Zalin | B47 |
| ἀναθέσθαι | harpocration.1170.1 | Sosin, Smith-MacDonald, Zalin | B52 |
| ἀθεώρητος | harpokration.43.1 | Sosin, Smith-MacDonald, Zalin | B67 |
| ἀνδρεία | harpocration.182.1 | Sosin, Smith-MacDonald, Zalin | B67a |
| αὐλιζόμενοι | harpokration.340.1 | Sosin, Smith-MacDonald, Zalin | B68 |
| εὐηνιώτατα | harpocration.606.1 | Sosin, Smith-MacDonald, Zalin | B70 |
| φηλώματα | harpocration.1054.1 | Sosin, Smith-MacDonald, Zalin | B71 |
| εὐσύμβολος | harpocration.615.1 | Sosin, Smith-MacDonald, Zalin | B74 |
| ἡμιολιασμός | harpocration.651.1 | Sosin, Smith-MacDonald, Zalin | B75 |
| ἀκαρῆ | harpokration.58.1 | Sosin, Smith-MacDonald, Zalin | B87 |
| βάσανος | harpokration.357.1 | Sosin, Smith-MacDonald, Zalin | B88 |
| δυσάνιος | harpocration.536.1 | Sosin, Smith-MacDonald, Zalin | B89 |
| εἰσφρήσειν | harpocration.548.1 | Sosin, Smith-MacDonald, Zalin | B90 |
| λυκιουργεῖς | harpokration.453.1 | Sosin, Smith-MacDonald, Zalin | critias-fragments B35 |
| ἀφαρεύς | harpokration.347.1 | Sosin, Smith-MacDonald, Zalin | hippias-testimonia A3 |

Full names: Joshua D. Sosin, John-Paul Smith-MacDonald, Mackenzie Zalin,
Matthew Farmer, Stelios Chronopoulos.

Where HOL has more than one translation of an entry, the one used is the
Sosin, Smith-MacDonald and Zalin translation, unless it does not render DK's
Greek: for ἄβιος, version 1 inverts the Homer comparison ("as Homer calls a
woodless woods 'much wooded'"), so Chronopoulos's version 2 is used. Not
used: de Lisle's δεήσεις (harpokration.1151.1), σκιάποδες (1118.1) and
ἀναθέσθαι (1122.1, which reads "to live always regretting earlier life").

## Method

1. Listed every DK head whose expansion author is Harpocration (36 heads in
   36 columns: anaxagoras-testimonia A2, antiphon-sophist-fragments 32
   columns, critias-fragments B35, hippias-testimonia A3). Heads without a
   printed *s.v.* take the headword from the Greek after the head.
2. Found each headword in HOL (all but δίνωι, which HOL keys as Dindorf's
   δείνωι) and in the local TLG Dindorf text (tlg1389.001, exported with
   Diogenes as in `docs/tlg-phi-export.md`).
3. Read each HOL English against DK's Greek: 32 MATCH, 4 DIFFERS, none NOT
   FOUND. The DIFFERS passages (Antiphon B22, B25, B30, B69) are not
   vendored and get no English; the reasons are in the audit list kept with
   the work notes.
4. The site's text and the data repository's CSV agree, word for word, for
   every translation used.
5. Cleaning, the only changes to HOL's words: whitespace runs made single
   spaces; straight quotation marks and apostrophes made curly (an opening
   mark after a space or bracket, a closing one otherwise). No word changed.
   HOL's own punctuation is kept as printed, including a missing final stop
   (ἀθεώρητος) and colons and semicolons inside quotation marks.

## Checks

- Every trim anchor of every placed span occurs exactly once in its entry
  (the build enforces this).
- The reader's layout places every span under its own Harpocration heading
  (replayed over the current DK columns; no column has two Harpocration
  headings, so no span needs `head`).

`SHA256SUMS` holds the SHA-256 of the clean JSON.
