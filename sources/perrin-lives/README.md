# Bernadotte Perrin — Plutarch, *Lives*, the chapters DK's Plutarch passages need

Vendored English for the passages of Plutarch's *Lives* in the DK works that
an audit of Perrin's text against DK's Greek classed as matching (English goes
beside DK's Greek only where the translation renders the same Greek DK
prints). `stage1_context_english.py` reads this store as the source pairs
("Plutarch", <Life>), with the credit of the Life's volume: "Perrin, 1914",
"Perrin, 1916" or "Perrin, 1920" (draft, pending the owner's approval).

**Public domain in the US by publication date** (first printed 1914, 1916
and 1920, all before the 1931 cut-off). Licence string: `Public Domain`.

## Source

| | |
|---|---|
| Translator | Bernadotte Perrin (1847–1920) |
| Edition | *Plutarch's Lives*, with an English translation by Bernadotte Perrin, Loeb Classical Library, 11 volumes |
| Publisher | London: William Heinemann (first printings) |
| Transcription | Perseus Digital Library, `canonical-greekLit` (GitHub `PerseusDL/canonical-greekLit`, commit `bcc5df0602f3b3fe6fefe1e1d575602a25ab1db6`), the `perseus-eng2` TEI file of each Life (the TEI files carry a CC BY-SA 4.0 licence) |
| Scans checked | archive.org `plutarchs-lives-in-11-volumes.-vol.-1-loeb-46`, `-vol.-2-loeb-47`, `-vol.-3-loeb-65`, `-vol.-4-loeb-80`, `-vol.-9-loeb-101` (later reprints: "First printed 1914 … Reprinted 1928, 1948, 1959, 1967" and so on), archive.org's OCR `_djvu.txt`, fetched 2026-09-27 (SHA-256: vol. I `1db7560c85ec47162ea781030d01d30fa5f4f709ae97a9f611b9c229fef7a693`, II `9ffeb5dafd0ae81b8de09e7ea82b561dcb894f7ad6934c26084ced6d3f3476bb`, III `45d9e358b1901d21bc1551b563f2d080a9439ecefe83922fd8b822f16b0c04f3`, IV `aa444fb9e76011c04ff59c3d7620e02c9879c27bc951c3d3ec2ce5e2143e9418`, IX `6b70b0b24fa6bfa12277d984f3de301a55340a80522ef25021a733f2de5b4969`) |

Neither the scans nor the TEI files are vendored here.

| Life (DK's title) | Loeb volume | First printed | Credit | Perseus file | Chapters |
|---|---|---|---|---|---|
| Lycurgus | I | 1914 | Perrin, 1914 | `tlg004.perseus-eng2` | 9, 23 |
| Numa | I | 1914 | Perrin, 1914 | `tlg005.perseus-eng2` | 1 |
| Solon | I | 1914 | Perrin, 1914 | `tlg007.perseus-eng2` | 2, 12 |
| Camillus | II | 1914 | Perrin, 1914 | `tlg011.perseus-eng2` | 19 |
| Cimon | II | 1914 | Perrin, 1914 | `tlg035.perseus-eng2` | 10, 16 |
| Pericles | III | 1916 | Perrin, 1916 | `tlg012.perseus-eng2` | 4, 5, 6, 16, 26, 27, 28, 32, 36 |
| Nicias | III | 1916 | Perrin, 1916 | `tlg038.perseus-eng2` | 23 |
| Alcibiades | IV | 1916 | Perrin, 1916 | `tlg015.perseus-eng2` | 33 |
| Coriolanus | IV | 1916 | Perrin, 1916 | `tlg016.perseus-eng2` | 22, 38 |
| Lysander | IV | 1916 | Perrin, 1916 | `tlg032.perseus-eng2` | 12 |
| Antonius (Antony) | IX | 1920 | Perrin, 1920 | `tlg058.perseus-eng2` | 28 |

## Shape

`perrin-lives.clean.json`: `{"<Life>": {"<chapter>": "…"}}`, the Life by the
Latin title DK's head expansion gives, the chapter by the Loeb chapter
number. A chapter's text is its sections run together as the Loeb prints
them; a verse set apart in the Loeb is its own paragraph (blank line). No
footnotes, no section numbers. 11 Lives, 23 chapters, 9,862 words — only the
chapters the placed spans need.

A span's `locus` is a chapter ("16") or a range of chapters ("26-28");
chapters are joined by a blank line, and the span's `trim` cuts the text to
DK's words.

## Text: the Perseus transcription, checked against the Loeb

1. Each chapter's text is the Perseus TEI, converted to plain text: notes
   (the Loeb's footnotes) and bibliographic references dropped; `<q>` and
   `<quote>` as curly double quotes, as the Loeb prints them (Perseus drops
   the quotation marks round quoted verse).
2. Every chapter was compared word by word with archive.org's OCR of the
   Loeb volume (the OCR's line-end hyphens joined; the facing Greek pages and
   the OCR's misreadings set aside).
3. Corrections to the Perseus text, all to the printed page. Perseus
   Americanised some of the Loeb's British spellings; the print's are
   restored:

| Life, chapter | Perseus | Loeb |
|---|---|---|
| Lysander 12, Pericles 26 | harbor | harbour |
| Pericles 4 | demeanor | demeanour |
| Pericles 28 | honorable | honourable |
| Nicias 23 | colors; splendor; "but what what it was" | colours; splendour; "but what it was" |
| Cimon 10 | honor (twice); "he might he honored" | honour; "he might be honoured" |
| Cimon 16, Solon 2 | honor | honour |
| Solon 12 | honors | honours |

### Printer's errors corrected (2026-09-29, owner's instruction)

The Loeb prints these slips, and the text corrects them:

- Cimon 10: "Georgias the Leontine" is now "Gorgias the Leontine".
- Coriolanus 38: "But most or the Deity's powers" is now "But most of the Deity's powers".

One misprint Perseus corrected is left corrected, outside every placed span:
Coriolanus 38, "in His works most of all" (the print: "must of all").

## Checks

- Every trim anchor and bold phrase of every placed span occurs exactly once
  in the text its locus resolves to (the build enforces this).
- `SHA256SUMS` holds the SHA-256 of the clean JSON.
