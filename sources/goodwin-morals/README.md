# W. W. Goodwin (ed.) — Plutarch, *Moralia*, the chapters DK's Plutarch passages need

Vendored English for the Plutarch passages in the DK works that an audit of
Goodwin's text against DK's Greek classed as matching (the owner's rule for
the Aëtius work, applied here: English goes beside DK's Greek only where the
translation renders the same Greek DK prints; where Goodwin's English differs,
nothing is placed and the case is listed for the owner). `stage1_context_english.py`
reads this store as the source pairs ("Plutarch", <essay>) and, for the
*Lives of the Ten Orators*, ("pseudo-Plutarch", "Vitae Decem Oratorum"),
credit "Goodwin, 1874" (draft, pending the owner's approval).

**Since 2026-09-29 the Loeb English replaces Goodwin's** wherever a usable
Loeb volume covers the essay (owner ruling, review item 118; see
`sources/loeb-moralia/README.md`). This store is unchanged, but the resolver
now reads it only for *Adversus Colotem*, *Amatorius*, *De animae
procreatione in Timaeo*, *De communibus notitiis*, *Quaestiones convivales*,
*Quaestiones naturales* and *Quaestiones Platonicae*; its chapters of the
other essays are no longer read.

**Public domain in the US by publication date.** All five volumes of the
set used were printed in 1874 (title pages); copyright was entered in 1870.
Both dates are before the 1931 cut-off. Licence string: `Public Domain`.

## Source

| | |
|---|---|
| Translation | "Translated from the Greek by several hands" (the late-17th-century English Morals), "corrected and revised by William W. Goodwin, Ph. D., Professor of Greek Literature in Harvard University" |
| Edition | *Plutarch's Morals*, 5 vols, with an introduction by Ralph Waldo Emerson |
| Publisher | Boston: Little, Brown, and Company (Cambridge: Press of John Wilson and Son) |
| Printing | 1874, every volume (title pages); "Entered according to Act of Congress, in the year 1870" |
| Scans | archive.org `plutarchsmoralst01plutuoft` … `plutarchsmoralst05plutuoft` (University of Toronto copies), fetched 2026-09-27 |
| Transcription | Perseus Digital Library, `canonical-greekLit` (GitHub `PerseusDL/canonical-greekLit`, commit `bcc5df0602f3b3fe6fefe1e1d575602a25ab1db6`), the Goodwin TEI file of each essay (Perseus's OCR of the same 1874 volumes, corrected; the TEI files carry a CC BY-SA 4.0 licence) |
| Files read | the TEI files named below; archive.org's OCR of the five volumes, `_djvu.txt` (SHA-256: vol. I `3ffd5ca27650f5c26a2805a372024b6172e4e2e1e7c9193d07052b47ead049ea`, II `c6fdb25174a7403549b5dc7e77e1ce891b889ef1c938c0d260f37ed538cafefc`, III `13438008b241f87bfc58d26c7aa2cd532c824db2768403238bd1bbac1c8c1327`, IV `36dc1e5453fcb6fa7cbc00c9d6da0a53295e2e050b62bda8ace074a1a79f179c`, V `d7aa0bdbca7b1310eda3ce450e9f9054970744c4b1b6665a0f206b1777af23c7`); page images where noted |

Neither the scans nor the TEI files are vendored here.

## Shape

`goodwin-morals.clean.json`: `{"<essay>": {"<chapter>": {"steph": "<first>-<last>", "text": "…"}}}`.

- `<essay>` is the Latin title DK's head expansion gives (the source pair's
  work title).
- `<chapter>` is the Perseus division of Goodwin's text (the Loeb chapter
  numbers; "book.question.section" for the *Symposiacs*, "question.section"
  for the *Platonic Questions*; `I.`/`II.` for the two tracts *Of Eating of
  Flesh*). Goodwin's print numbers paragraphs, not chapters; these numbers
  are an addressing aid.
- `steph` is the Stephanus range the chapter covers, first and last page
  and letter ("683d-683e"). It comes from the Stephanus milestones in the
  Perseus Greek of the same chapter; where the Perseus Greek has none
  (*De liberis educandis*) it comes from aligning that Greek with the TLG
  text, which is divided by Stephanus page and letter. Two Perseus faults
  were corrected: *De esu carnium* II 1 carries "966d, 966e" for 996d, 996e;
  *De animae procreatione* 20 carries the editors' transposed 1027f–1028a,
  which Goodwin's chapter does not have (range set to 1022c–1022e).
- `text` is Goodwin's English for the chapter, his paragraphs separated by a
  blank line; a verse quotation is its own paragraph, its lines joined by
  single spaces. No footnotes, no question titles or running heads, no
  paragraph numbers.

A span's `locus` is a Stephanus page and letter ("929b") or a range
("683d-683f"): the place of DK's Greek in the TLG. The resolver returns every
chapter of the essay whose range meets the locus, and the span's `trim`
cuts that to DK's words.

41 essays, 123 chapters, 63,137 words — only the chapters the placed spans need:

| Essay (DK's title) | Goodwin's title | Vol. | Perseus file | Chapters (Stephanus) |
|---|---|---|---|---|
| Adversus Colotem | Against Colotes, the Disciple and Favorite of Epicurus | V | `tlg140.perseus-eng2` | 3 (1108d-1108f), 4 (1108f-1109c), 12 (1113b-1113e), 13 (1113e-1114f), 15 (1115c-1116c), 20 (1118b-1118f), 28 (1123a-1124b), 32 (1126a-1126e), 33 (1126e-1127c) |
| Amatorius | Of Love | IV | `tlg113.perseus-eng2` | 13 (756a-757c) |
| An Seni Respublica Gerenda Sit | Whether an Aged Man Ought to Meddle in State Affairs | V | `tlg117.perseus-eng4` | 6 (786d-787c), 7 (787c-788a) |
| Animine an Corporis Affectiones Sint Peiores | Whether the passions of the soul or diseases of the body are worse | IV | `tlg100.perseus-eng4` | 2 (500c-501a) |
| Coniugalia Praecepta | Conjugal Precepts | II | `tlg078.perseus-eng4` | 42 (144a-144b), 43 (144b-144c), 44 (144c-144d) |
| Consolatio ad Apollonium | Consolation to Apollonius | I | `tlg076.perseus-eng4` | 10 (106c-107a) |
| De Adulatore et Amico | How to Know a Flatterer from a Friend | II | `tlg070.perseus-eng4` | 23 (64b-65a) |
| De Amore Prolis | Of Natural Affection Towards One's Offspring | IV | `tlg098.perseus-eng4` | 3 (495b-496c) |
| De Animae Procreatione in Timaeo | Concerning the procreation of the soul as discoursed in Timaeus | II | `tlg134.perseus-eng2` | 27 (1026a-1026e) |
| De Cohibenda Ira | Concerning the cure of anger: a dialogue | I | `tlg095.perseus-eng4` | 16 (463b-464d) |
| De Communibus Notitiis adversus Stoicos | Of common conceptions, against the Stoics | IV | `tlg138.perseus-eng2` | 39 (1079d-1080d), 46 (1084d-1084e) |
| De Curiositate | Of Curiosity, or an Over-Busy Inquisitiveness into Things Impertinent | II | `tlg102.perseus-eng4` | 1 (515b-515f), 11 (520d-521a), 12 (521a-521e) |
| De Defectu Oraculorum | Why the Oracles Cease to Give Answers | IV | `tlg092.perseus-eng4` | 11 (415c-415f), 15 (417e-418d) |
| De E apud Delphos | Of the word ΕΙ engraven over the gate of Apollo's temple at Delphi | IV | `tlg090.perseus-eng4` | 8 (387f-388e), 9 (388e-389c), 18 (392a-392e) |
| De Esu Carnium | Of eating of flesh: Tract I / Of eating of flesh: Tract II | V | `tlg131.perseus-eng4, tlg132.perseus-eng4` | I.1 (993a-993c), I.2 (993c-994b), II.4 (998a-998c), II.5 (998c-998f) |
| De Exilio | Of Banishment, or Flying One's Country | III | `tlg110.perseus-eng2` | 11 (603d-604b), 17 (607a-607f) |
| De Facie in Orbe Lunae | Of the Face Appearing Within the Orb Of the Moon | V | `tlg126.perseus-eng4` | 1 (920b-920c), 2 (920c-920f), 5 (921f-922f), 12 (926c-927a), 16 (928d-929e), 17 (929e-930e), 28 (942f-943e), 29 (943e-944c) |
| De Fortuna | Of Fortune | II | `tlg074.perseus-eng4` | 3 (98b-98f) |
| De Garrulitate | Of Garrulity, or Talkativeness | IV | `tlg101.perseus-eng4` | 17 (510e-511d) |
| De Genio Socratis | A Discourse Concerning Socrates's Daemon | II | `tlg109.perseus-eng2` | 13 (582c-583c) |
| De Gloria Atheniensium | Whether the Athenians Were More Renowned For Their Warlike Achievements or For Their Learning | V | `tlg088.perseus-eng4` | 5 (348b-348d) |
| De Iside et Osiride | Of Isis and Osiris, or of the Ancient Religion and Philosophy of Egypt | IV | `tlg089.perseus-eng4` | 26 (360f-361d), 30 (362e-363b), 33 (364a-364c), 34 (364c-364e), 48 (370c-371a), 79 (383a-383d) |
| De Liberis Educandis | A Discourse Touching the Training of Children | I | `tlg067.perseus-eng4` | 13 (9b-9f), 14 (9f-11c) |
| De Primo Frigido | Concerning the First Principles of Cold | V | `tlg127.perseus-eng4` | 7 (947e-948a), 8 (948a-948c), 16 (951e-952c), 19 (953d-954b) |
| De Profectibus in Virtute | How a Man May Be Sensible of His Progress in Virtue | II | `tlg071.perseus-eng4` | 10 (80e-81f) |
| De Pythiae Oraculis | Wherefore the Pythian Priestess Now Ceases to Deliver her Oracles in Verse | III | `tlg091.perseus-eng4` | 6 (396f-397b), 12 (399e-400d), 21 (404b-405a) |
| De Recta Ratione Audiendi | Of Hearing | I | `tlg069.perseus-eng4` | 13 (44a-45d) |
| De Sollertia Animalium | Which are the most crafty, water-animals or those creatures that breed upon the land? | V | `tlg129.perseus-eng4` | 19 (972f-974a), 20 (974a-974d) |
| De Superstitione | Of Superstition, or Indiscreet Devotion | I | `tlg080.perseus-eng4` | 3 (165c-166c), 4 (166c-167a) |
| De Tranquillitate Animi | Of the Tranquillity of the Mind | I | `tlg096.perseus-eng4` | 1 (464e-465c), 2 (465c-466a), 15 (473e-474c), 16 (474c-475b) |
| De Tuenda Sanitate Praecepta | Plutarch's Rules for the Preservation of Health | I | `tlg077.perseus-eng4` | 8 (126b-126d), 9 (126d-127b), 13 (128e-129a), 14 (129a-129c), 24 (135b-136a) |
| De Virtute Morali | Of Moral Virtue | III | `tlg094.perseus-eng4` | 7 (446c-448d) |
| De Vitioso Pudore | Of Bashfulness | I | `tlg104.perseus-eng2` | 5 (530e-531b) |
| Praecepta Gerendae Reipublicae | Political Precepts | V | `tlg118.perseus-eng4` | 27 (819f-820f), 28 (820f-821e) |
| Quaestiones Convivales | Symposiacs | III | `tlg112.perseus-eng2` | 1.2.5 (617f-618c), 1.10.2 (628b-628d), 2.7.1 (641b-641c), 2.10.1 (642f-643e), 2.10.2 (643e-644d), 3.0.1 (644f-645c), 4.2.3 (665a-665e), 4.2.4 (665e-666d), 5.4.1 (677c-677e), 5.7.5 (682c-682f), 5.7.6 (682f-683b), 5.8.2 (683d-683e), 5.8.3 (683e-684b), 5.10.4 (685c-685f), 6.2.2 (687e-689a), 7.10.2 (715b-716c), 8.3.1 (720c-720f), 8.10.1 (734d-734f), 8.10.2 (734f-735c), 9.14.4 (744f-745c), 9.14.5 (745c-745d), 9.14.6 (745d-746b), 9.14.7 (746b-747a) |
| Quaestiones Naturales | Plutarch's Natural Questions | III | `tlg125.perseus-eng2` | 1 (911d-911f), 2 (911f-912d), 19 (916b-916f), 20 (916f-917b), 22 (917d-917e), 23 (917e-917f), 39 (919d-919d) |
| Quaestiones Platonicae | Plutarch's Platonic questions | V | `tlg133.perseus-eng2` | 8.2 (1006d-1006e), 8.3 (1006e-1006f), 8.4 (1006f-1007e), 9.1 (1007e-1008e) |
| Quomodo Adulescens Poetas Audire Debeat | How a Young Man Ought to Hear Poems | II | `tlg068.perseus-eng4` | 2 (16a-17f) |
| Regum et Imperatorum Apophthegmata | The Apopthegms or Remarkable Sayings of Kings and Great Commanders | I | `tlg081.perseus-eng4` | 20 (175b-175c), 21 (175c-176c) |
| Septem Sapientium Convivium | The Banquet of the Seven Wise Men | II | `tlg079.perseus-eng4` | 2 (146d-148b) |
| Vitae Decem Oratorum | Lives of the Ten Orators | V | `tlg121.perseus-eng4` | 1 (832b-834b), 4 (836e-839d) |

## Text: the Perseus transcription, checked against the 1874 print

1. Each chapter's text is the Perseus TEI, converted to plain text: notes,
   bibliographic references and headings dropped; `<q>` as curly double
   quotes; Goodwin's Greek words kept as Perseus has them.
2. Every chapter was compared word by word with archive.org's OCR of the 1874
   volume (the OCR's line-end hyphens joined). The OCR's own misreadings
   ("tliis", "Ileraclitus", running heads) were set aside; every other
   difference was checked against the page image where the OCR could not
   settle it. Typography was normalised, never the words: em-dashes closed
   up, no space inside quotation marks or brackets or before punctuation, the
   small capitals of a chapter's first word set in ordinary case ("WHETHER
   the dogs" → "Whether the dogs").
3. Corrections to the Perseus text, all to the printed page:

| Essay, chapter | Perseus | 1874 print |
|---|---|---|
| *De tuenda sanitate praecepta* 8, 9, 13, 14, 24 | "ZEUXIPPUS." at paragraph openings (6 times) | no speaker names; the print numbers the paragraphs ("14. It is absurd …", page image checked) |
| *De communibus notitiis* 39, 46 | "DIADUMENUS." | none (paragraph numbers) |
| *Amatorius* 13 | "AUTOB." (11 times) | none |
| *De cohibenda ira* 16 | "FUNDANUS." | none (paragraph number) |
| *De profectibus in virtute* 10 | "within him. and that" | "within him, and that" |
| *De garrulitate* 17 | "highly applauded Thus"; "came don again"; "whether lie could"; "with case;" | "highly applauded? Thus"; "came down again"; "whether he could"; "with ease;" |
| *De exilio* 11 | "live at case." | "live at ease." |
| *De primo frigido* 16 | "Posidouius" | "Posidonius" |
| *Symposiacs* 6.2.2 | "but front the evacuation" | "but from the evacuation" |
| *De virtute morali* 7 | "stalk blind" | "stark blind" |
| *Symposiacs* 5.8.2 | "And apples bear a lovely show;" (Perseus moved the Greek into a note) | "And apples bear a lovely show (ὑπέρφλοια);" (page image) |
| *Symposiacs* 5.4.1 | "ἀκρατα" | "ἄκρατα" (page image) |

*Quaestiones naturales* 39 opens with Goodwin's question title ("How cometh it
that water …?" as the print words it, set in sentence case), added 2026-09-29 from the 1874
volume's OCR (vol. III, p. 518), because DK's Latin text opens with that
question. Every other chapter still carries no title.

Goodwin is American: his spellings ("favorable", "honor") are the print's.

### Checked against page images

"Thoösa" (*De tranquillitate animi* 15), the comma before a verse quotation
("saying," in *De facie* 2, where the OCR reads a full stop), and every
Greek word inside a placed span (τὸ δέν, τὸ μηδέν, δέν, μηδέν in *Adversus
Colotem* 4; ἄκρατα, ζωρά, ζωρόν, εὔκρατον in *Symposiacs* 5.4.1; ὑπέρφλοια,
φλοίειν, ὑπέρφλοιον in 5.8.2–3) agree with the 1874 page.

### Not settled beyond doubt

- Greek words outside the placed spans were not checked against the page
  images (the OCR cannot read Greek).
- One misprint Perseus corrected is left corrected, outside every placed
  span: *De recta ratione audiendi* 13, "Not to be too prone to commend"
  (the print: "Not to he").
- Punctuation was compared with the OCR, which often reads a comma as a full
  stop; only the cases listed above were settled from the page images.

## Checks

- Every trim anchor and bold phrase of every placed span occurs exactly once
  in the text its locus resolves to (the build enforces this).
- `SHA256SUMS` holds the SHA-256 of the clean JSON.
