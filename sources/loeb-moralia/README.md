# The Loeb *Moralia* — the chapters DK's Plutarch passages need

Vendored English from the Loeb Classical Library's *Plutarch's Moralia* for
the Plutarch passages in the DK works whose essay a usable Loeb volume
covers. It replaces Goodwin's 1874 English (`sources/goodwin-morals/`) for
those essays; Goodwin's store is unchanged and still serves the essays no
usable Loeb covers (*Adversus Colotem*, *Amatorius*, *De animae procreatione*,
*De communibus notitiis*, *Table Talk*, *Natural Questions*, *Platonic
Questions*). `stage1_context_english.py` reads this store as the source pairs
("Plutarch", <essay>) and ("pseudo-Plutarch", "Vitae Decem Oratorum"), with
the credit of the essay's translator and volume (draft, pending the owner's
approval): "Babbitt, 1927", "Babbitt, 1928", "Babbitt, 1931", "Babbitt, 1936",
"Helmbold, 1939", "De Lacy and Einarson, 1959", "Fowler, 1936",
"Cherniss, 1957", "Helmbold, 1957".

## Copyright

Licence string: `Public Domain`.

- Vols. I (1927) and II (1928): public domain in the US by publication date.
- Vols. III (1931), IV and V (1936), VI (1939), VII (1959), X (1936) and XII
  (1957): no copyright renewal found. The owner ruled on 2026-09-29 that
  these are usable ("yes, use the non-renewed Loebs"), on the same footing
  as Ostwald's *Nicomachean Ethics*; the basis (NYPL renewal data, Copyright
  Office records, Perseus and LacusCurtius hosting) is review item 118 in
  `REVIEW-CHECKLIST.md`, and CLAUDE.md records it as the fourth exception.
  Vols. VIII, IX, XI, XIII and XIV are not used (IX renewed 1989; the rest
  1965–76).

## Sources

| | |
|---|---|
| Edition | *Plutarch's Moralia*, with an English translation, Loeb Classical Library (Cambridge, Mass.: Harvard University Press; London: William Heinemann). Translators: Frank Cole Babbitt (vols. I–V), W. C. Helmbold (vol. VI; vol. XII except *De facie*), Phillip H. De Lacy and Benedict Einarson (vol. VII, jointly), Harold North Fowler (vol. X), Harold Cherniss (vol. XII, *De facie*; the volume's preface assigns the essays) |
| Transcription, 31 essays | Perseus Digital Library, `canonical-greekLit` (GitHub `PerseusDL/canonical-greekLit`, commit `bcc5df0602f3b3fe6fefe1e1d575602a25ab1db6`, the commit the Perrin and Goodwin stores use), the `perseus-eng3` TEI file of each essay (CC BY-SA 4.0 markup). Fetched 2026-09-29 through jsDelivr's mirror of that commit (`cdn.jsdelivr.net/gh/PerseusDL/canonical-greekLit@bcc5df0…`), because github.com did not answer from this machine. Each file's `teiHeader` names the Loeb translator and gives the first printing (1927, 1928, 1931, 1936, 1939, 1957; the vol. V *De Pythiae oraculis* and vol. XII *De sollertia* headers give none) |
| Transcription, *De exilio*, *De vitioso pudore* (vol. VII) | Perseus has no Loeb English for vol. VII. LacusCurtius (Bill Thayer), `penelope.uchicago.edu/Thayer/E/Roman/Texts/Plutarch/Moralia/De_exilio*.html` and `…/De_vitioso_pudore*.html`, "as published in Vol. VII of the Loeb Classical Library edition, 1959", proofread by Thayer; fetched 2026-09-29 (SHA-256 `bb6dadddf256d890520b7b63d647f1db18bd48c44bc1e4bca7c474de6cea916c`, `a820618b4224efb17fc825efbf5ecaa5a9c5a5375790328ad680da8641d5d9d8`) |
| Transcription, *De genio Socratis* (vol. VII) | Neither Perseus nor LacusCurtius has it. Chapter 13 transcribed by hand from archive.org's OCR of vol. VII (`moraliainfiftee07plut`, the 1959 volume), the OCR's footnote markers and running heads removed |
| Scans checked | archive.org's OCR (`_djvu.txt`) of every volume used, fetched 2026-09-29, the OCR's line-end hyphens joined. SHA-256: vol. I `plutarchs-moralia-vol.-1-loeb-197` `3bbe2202eb965a6134c7d96b73c0328cb7ed15565895358d3459faa2d4aca781`; II `moraliainfifteen02plutuoft` `72b4d570d2d726534fae061a9d265eb9b063af55d4bbe615477036ce023aba1b`; III `moraliainfifteen03plutuoft` `2038b6393f60b23f282a32337a8bd2eac043ca57e9f7bef8e006442a0d545537`; IV `moraliainfifteen04plutuoft` `21368d9c612c257093f66a28d31a2b5a8e65dd22865d05b171e423ddf5be02f2`; V `moraliainfiftee05plut` `a31233572f0416bbf87ec1428a05ce6fa325ecf711d070f60dc9649172136923`; VI `moraliainfifteen06plutuoft` `219f1fd9e12de5c1dd792ce78d4280c49c9e5f6deda9137638039510e968c7ba`; VII `moraliainfiftee07plut` `2dbf558fc53c8c8395fb1af237bc5f7ca12a1cd6e00ec54c5c79643bbaf32658`; X `moraliainfifteen10plutuoft` `fedf6e66b90dd860717a8b224cc3b2425b739a3466fc819447818039222c2d56`; XII `moraliainfifteen12plutuoft` `cb637aa564849ae2243da9e39b4aac0e65b75d1f8b0f5473c426946118ce40c3`. Most scans are later printings ("First printed 1931 … Reprinted 1949, 1961"; vol. V "Reprinted 1957, 1962 …"): the Loeb *Moralia* volumes were reprinted, not revised, and the reprints' text agrees with the Perseus transcriptions of the first printings word for word, apart from the slips listed below |
| Third witness | LacusCurtius's proofread Loeb pages, where Thayer has the essay (fetched 2026-09-29): *An seni*, *Animine an corporis*, *Coniugalia praecepta*, *De amore prolis*, *De recta ratione audiendi*, *De defectu oraculorum*, *De fortuna*, *De garrulitate*, *De gloria Atheniensium*, *De liberis educandis*, *De primo frigido*, *De superstitione*, *De tranquillitate animi*, *Praecepta gerendae reipublicae*, *De Iside*, *De esu carnium*, *De facie* (chapter 2) |

Neither the scans, the TEI files nor the LacusCurtius pages are vendored here.

| Essay (DK's title) | Loeb vol. | First printed | Credit | Source | Chapters (Stephanus) |
|---|---|---|---|---|---|
| An Seni Respublica Gerenda Sit | X | 1936 | Fowler, 1936 | `tlg117.perseus-eng3` | 7 (787c-788a) |
| Animine an Corporis Affectiones Sint Peiores | VI | 1939 | Helmbold, 1939 | `tlg100.perseus-eng3` | 2 (500c-501a) |
| Coniugalia Praecepta | II | 1928 | Babbitt, 1928 | `tlg078.perseus-eng3` | 43 (144b-144c) |
| Consolatio ad Apollonium | II | 1928 | Babbitt, 1928 | `tlg076.perseus-eng3` | 10 (106c-107a) |
| De Adulatore et Amico | I | 1927 | Babbitt, 1927 | `tlg070.perseus-eng3` | 23 (64b-65a) |
| De Amore Prolis | VI | 1939 | Helmbold, 1939 | `tlg098.perseus-eng3` | 3 (495b-496c) |
| De Cohibenda Ira | VI | 1939 | Helmbold, 1939 | `tlg095.perseus-eng3` | 16 (463b-464d) |
| De Curiositate | VI | 1939 | Helmbold, 1939 | `tlg102.perseus-eng3` | 1 (515b-515f), 11 (520d-521a), 12 (521a-521e) |
| De Defectu Oraculorum | V | 1936 | Babbitt, 1936 | `tlg092.perseus-eng3` | 11 (415c-415f), 15 (417e-418d) |
| De E apud Delphos | V | 1936 | Babbitt, 1936 | `tlg090.perseus-eng3` | 8 (387f-388e), 18 (392a-392e) |
| De Esu Carnium | XII | 1957 | Helmbold, 1957 | `tlg131.perseus-eng3`, `tlg132.perseus-eng3` | I.2 (993c-994b), II.4 (998a-998c) |
| De Exilio | VII | 1959 | De Lacy and Einarson, 1959 | LacusCurtius | 11 (603d-604b), 17 (607a-607f) |
| De Facie in Orbe Lunae | XII | 1957 | Cherniss, 1957 | `tlg126.perseus-eng3` | 2 (920c-920f), 5 (921f-922f), 12 (926c-927a), 16 (928d-929e), 28 (942f-943e) |
| De Fortuna | II | 1928 | Babbitt, 1928 | `tlg074.perseus-eng3` | 3 (98b-98f) |
| De Garrulitate | VI | 1939 | Helmbold, 1939 | `tlg101.perseus-eng3` | 17 (510e-511d) |
| De Genio Socratis | VII | 1959 | De Lacy and Einarson, 1959 | archive.org OCR | 13 (582c-583c) |
| De Gloria Atheniensium | IV | 1936 | Babbitt, 1936 | `tlg088.perseus-eng3` | 5 (348b-348d) |
| De Iside et Osiride | V | 1936 | Babbitt, 1936 | `tlg089.perseus-eng3` | 26 (360f-361d), 30 (362e-363b), 34 (364c-364e), 48 (370c-371a), 79 (383a-383d) |
| De Liberis Educandis | I | 1927 | Babbitt, 1927 | `tlg067.perseus-eng3` | 14 (9f-11c) |
| De Primo Frigido | XII | 1957 | Helmbold, 1957 | `tlg127.perseus-eng3` | 7 (947e-948a), 16 (951e-952c), 19 (953d-954b) |
| De Profectibus in Virtute | I | 1927 | Babbitt, 1927 | `tlg071.perseus-eng3` | 10 (80e-81f) |
| De Pythiae Oraculis | V | 1936 | Babbitt, 1936 | `tlg091.perseus-eng3` | 6 (396f-397b), 12 (399e-400d), 21 (404b-405a) |
| De Recta Ratione Audiendi | I | 1927 | Babbitt, 1927 | `tlg069.perseus-eng3` | 13 (44a-45d) |
| De Sollertia Animalium | XII | 1957 | Helmbold, 1957 | `tlg129.perseus-eng3` | 20 (974a-974d) |
| De Superstitione | II | 1928 | Babbitt, 1928 | `tlg080.perseus-eng3` | 3 (165c-166c) |
| De Tranquillitate Animi | VI | 1939 | Helmbold, 1939 | `tlg096.perseus-eng3` | 2 (465c-466a), 15 (473e-474c), 16 (474c-475b) |
| De Tuenda Sanitate Praecepta | II | 1928 | Babbitt, 1928 | `tlg077.perseus-eng3` | 8 (126b-126d), 14 (129a-129c), 24 (135b-136a) |
| De Virtute Morali | VI | 1939 | Helmbold, 1939 | `tlg094.perseus-eng3` | 7 (446c-448d) |
| De Vitioso Pudore | VII | 1959 | De Lacy and Einarson, 1959 | LacusCurtius | 5 (530e-531b) |
| Praecepta Gerendae Reipublicae | X | 1936 | Fowler, 1936 | `tlg118.perseus-eng3` | 28 (820f-821e) |
| Quomodo Adulescens Poetas Audire Debeat | I | 1927 | Babbitt, 1927 | `tlg068.perseus-eng3` | 2 (16a-17f) |
| Regum et Imperatorum Apophthegmata | III | 1931 | Babbitt, 1931 | `tlg081.perseus-eng3` | 20 (175b-175c) |
| Septem Sapientium Convivium | II | 1928 | Babbitt, 1928 | `tlg079.perseus-eng3` | 2 (146d-148b) |
| Vitae Decem Oratorum | X | 1936 | Fowler, 1936 | `tlg121.perseus-eng3` | 1 (832b-834b), 4 (836e-839d) |

## Shape

`loeb-moralia.clean.json` has the shape of Goodwin's store:
`{"<essay>": {"<chapter>": {"steph": "<first>-<last>", "text": "…"}}}`.

- `<essay>` is the Latin title DK's head expansion gives.
- `<chapter>` is the Loeb chapter number, which is the Perseus division of
  both translations ("I.2", "II.4" for the two tracts *De esu carnium*).
- `steph` is copied from the same chapter in Goodwin's store (the ranges come
  from the Perseus Greek; `sources/goodwin-morals/README.md`). Every placed
  passage was found in the chapter whose range holds its DK locus, and the
  LacusCurtius Stephanus markers of vol. VII agree.
- `text` is the chapter's English, paragraphs separated by a blank line; a
  verse set apart in the Loeb is its own paragraph, its lines joined by
  single spaces. No footnotes, no chapter or page numbers.

A span's `locus` is the Stephanus page and letter of DK's Greek (unchanged
from the Goodwin placements); the resolver returns every vendored chapter
whose range meets it, and the span's `trim` cuts that to DK's words.

34 essays, 57 chapters, 33,475 words — only the chapters the placed spans need.

## Text

1. Perseus TEI to plain text: notes, bibliographic references, headings and
   page breaks dropped; `<q>` and inline `<quote>` as curly double quotes,
   a quotation inside a quotation as single quotes; `<q rend="italics">`
   (verse the Loeb sets in italics within a sentence) without marks; a block
   quotation as its own paragraph; `<gap>` as the dots Perseus records.
   Perseus repeats a speaker's name ("ZEUXIPPUS.") at every paragraph of a
   continuing speech (`rend="merge"`); the print names the speaker only where
   the speech begins, so the repeats are dropped and the rest set in
   ordinary case ("Moschion."). Spaced dashes are closed up ("distention—this
   comes close to his own phrasing—is", as the print has them).
2. Cherniss marks the words he supplies in angle brackets; Perseus gives them
   as square brackets, which the store turns back into ⟨ ⟩ (archive.org's
   OCR of vol. XII reads them as round brackets, as it reads other angle
   brackets in that volume, never as square ones).
3. Every chapter was compared word by word with the archive.org OCR of its
   volume, and, where LacusCurtius has the essay, with Thayer's page. The
   OCR's misreadings, footnote markers and running heads were set aside;
   where the OCR drops a word both transcriptions have, the transcriptions
   were kept. Corrections to the transcription, all to the printed page:

| Essay, chapter | Transcription | Loeb |
|---|---|---|
| *De E* 8 | since twTo makes | since two makes |
| *De facie* 5, 12, 16 | the suns (three times); the moons reflection; Anaxagorass | the sun’s; the moon’s reflection; Anaxagoras’s |
| *De facie* 12 | flesh and wines and marrow | flesh and sinew and marrow |
| *De facie* 12 | soul in body; that is light.” (the speech goes on); the “natural” to the “better” | soul ⟨in⟩ body; that is light.; the ‘natural’ to the ‘better’ |
| *De facie* 16 | upon an other star; That is why there, is | upon ⟨an⟩other star; That is why there is |
| *De Iside* 30 | strugglingagainst | struggling against |
| *De Pythiae oraculis* 6, 12, 21 | unembellislied; wre believe; in all eases; diiferent; Heraeleitus; keep quietior | unembellished; we believe; in all cases; different; Heracleitus; keep quiet or |
| *De sollertia* 20 | wrhich | which |
| *De tranquillitate* 15 | painting,b; Heliope; Thoosa | painting,; Heliopê; Thoösa (LacusCurtius; the OCR reads "Heliopé", "Thoésa") |
| *De tuenda sanitate* 14 | “swine m their … bedding,”b as Democritusc put it | “swine in their … bedding,” as Democritus put it |
| *De tuenda sanitate* 24 | Demolitus | Democritus |
| *De tuenda sanitate* 8, 24 | "In well-gorged bodies Love resides," and "May run like weanling colt beside its dam." run into the prose | each set apart as verse |
| *De virtute morali* 7 | itself,but | itself, but |
| *Quomodo adulescens* 2 | the lynx,a why | the lynx, why |
| *Regum apophthegmata* 20 | Epieharmus | Epicharmus |
| *Septem sapientium convivium* 2 | which xv.2.p.351"/> had led | which had led (stray markup) |
| *Vitae decem oratorum* 4 | showred; tw o; the hill-he himself | showed; two; the hill—he himself |
| *De curiositate* 1, 12 | your own-to; this sort-kitchen | your own—to; this sort—kitchen |
| *De cohibenda ira* 16 | to search I out; whether In jest | to search out; whether in jest |
| *Animine an corporis* 2 | at me >within; than she” “Of fair variety; the souls diseases | at me within; than she Of fair variety; the soul’s diseases |
| *De amore prolis* 3 | upon the earth - | upon the earth— |
| *De liberis educandis* 14 | Homer’s’ Crimson Death.’” | Homer’s ‘Crimson Death.’” |
| *De superstitione* 3 | bestow on us. Our sleep | bestow on us, Our sleep |
| *De exilio* 17 (LacusCurtius) | birth a “journey, using | birth a “journey,” using |

## Not settled beyond doubt

- Perseus closes a quotation at the end of each paragraph of a continuing
  speech; the print leaves the paragraph open and reopens the next one. The
  store follows Perseus except where noted above (*De facie* 12); no placed
  span ends at such a paragraph end.
- Perseus's vol. VI files drop the circumflex the Loeb prints on proper
  names ("Aphrodite" for "Aphroditê"); only the two names inside a placed
  span were restored.
- Greek words and punctuation were compared only as far as the OCR allows.
- *De genio Socratis* 13 rests on one witness, the OCR, read by eye;
  "fluteplayer" is the OCR's reading.

## Checks

- Every trim anchor and bold phrase of every placed span occurs exactly once
  in the text its locus resolves to (the build enforces this).
- `SHA256SUMS` holds the SHA-256 of the clean JSON.
