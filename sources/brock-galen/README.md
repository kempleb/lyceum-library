# A. J. Brock — Galen, *On the Natural Faculties*, Book II chapters 8–9

Vendored English for two DK columns that quote Galen's *De Naturalibus
Facultatibus*:

- `anaxagoras-testimonia` A104 — GAL. de nat. fac. II 8 (II 107 Kühn,
  III 179, 12 Helmreich)
- `prodicus-fragments` B4 — GAL. II 9 (III 195 Helmreich)

Read by `pipeline/reader_pipeline/stage1_context_english.py` as the source
pair ("Galen", "On the Natural Faculties"), credit "Brock, 1916".

**Public domain in the US by publication date** (1916, before the 1931
cut-off). Licence string: `Public Domain`.

## Source

| | |
|---|---|
| Translator | Arthur John Brock, M.D. (1879–1947) |
| Edition | *Galen: On the Natural Faculties*, with an English translation by A. J. Brock (Loeb Classical Library) |
| Publisher | London: William Heinemann; New York: G. P. Putnam's Sons |
| Printing | 1916 (title page reads MCMXVI) |
| Working text | Project Gutenberg eBook #43383, `https://www.gutenberg.org/files/43383/43383-h/43383-h.htm`, fetched 2026-09-27 (SHA-256 `5995719c0ba2c269ccec823acc996077c0c2bd9e298c422061b468e8722ad008`) |

The Gutenberg file is not vendored here. Brock's Greek (the facing pages,
Helmreich's Teubner text) is never used or shipped; our Greek is DK's.

## Shape

`brock-natural-faculties.clean.json`: one flat JSON object keyed
`"<book>.<chapter>"`. Each value is one chapter of Brock's English, his
paragraphs separated by a blank line (`\n\n`). Plain Unicode text: no markup,
no footnotes, no page numbers.

| Key | Chapter | Paragraphs | Words | Opens | Ends |
|---|---|---|---|---|---|
| `2.8` | Book II, ch. VIII | 17 | 3,747 | "Now Erasistratus ought not to have been ignorant…" | "…the view of Hippocrates and Plato." |
| `2.9` | Book II, ch. IX | 14 | 3,324 | "For this reason the things that we have said…" | "…in the third book all that remains." |

Only these two chapters are vendored: they are the only ones DK cites.

## Extraction

A short script over the Gutenberg HTML (kept outside the repo; the steps are
all here):

1. Took the lines between the chapter heads `<a name="II_8">` and
   `<a name="II_9">` (chapter 8), and from `<a name="II_9">` to the first
   footnote block after it (chapter 9). Book II's footnotes follow chapter 9
   and are not included.
2. Dropped the page-number spans (`<span class="pagenum">…Pg 169…Greek
   text…</span>`, Loeb page numbers and links to the facing Greek).
3. Dropped footnote anchors and footnote reference numbers.
4. Took each `<p>` as one paragraph, stripped the remaining tags (`<em>`
   italics), decoded HTML entities, and collapsed runs of whitespace to one
   space.
5. Joined the paragraphs with a blank line.

No word of Brock's was changed. His square brackets ("[mucus]", "[the
spleen]"), which mark words he supplies, are kept. So is the one Greek word
he prints inside the English (II 9, "from the verb πεφλέχθαι"), which is
Brock's text, not ours.

## Checks

- No digits, no "Pg", no "Greek text", no `<` or `&`, no straight quotes,
  no double spaces in either chapter.
- Each passage used was read against DK's Greek:
  - A104 (II 8): DK's sentence (εἰ γὰρ δὴ … φασι;) is Brock's "For, if it
    was right to raise this problem … by those who postulate homœmeries?"
  - B4 (II 9): DK's passage (Π. δ' ἐν τῶι … εἴποι ἂν αὐτόν.) is Brock's
    paragraph "Prodicus also, when in his book 'On the Nature of Man' …
    anything else than cold and moist."
- Not yet checked word by word against a scan of the 1916 printing (archive.org
  holds several); the Gutenberg transcription is the only witness so far.

`SHA256SUMS` holds the SHA-256 of the clean JSON.
