"""One-off: extract C. D. Yonge's English translation of Cicero's *De Fato*
("On Fate") from the archive.org OCR flat text of Bohn's *The Treatises of
M. T. Cicero* into chapter-keyed clean JSON, plus a hand-verified
chapter->Latin-section concordance against the PHI flat spine (sections
1-48, see `build/dist/de-fato/`).

## Source, pinned (see sources/yonge-fato/README.md for the full witness
## identity and PD basis)

Working OCR: archive.org item `treatisesofcicer00ciceuoft` (the 1878 G.
Bell stereotype reprint -- same plates as the 1853 H. G. Bohn first
printing, item `treatisescicero00ciceuoft`; see README for the
letter-identity spot check between the two scans). This script reads the
item's own `_djvu.txt` flat OCR, staged (not committed -- raw scan text is
never committed per this project's playbook) at
`build/yonge-fato/treatisesofcicer00ciceuoft_djvu.txt`:

    curl -sSL -o build/yonge-fato/treatisesofcicer00ciceuoft_djvu.txt \\
      https://archive.org/download/treatisesofcicer00ciceuoft/treatisesofcicer00ciceuoft_djvu.txt

Pinned SHA-256 (`_EXPECTED_SHA256` below): the script refuses to run
against any other byte content -- this is the "download once, verify the
hash, read locally" playbook used by `extract_miller_perseus.py` and
`extract_falconer_perseus.py`.

## Method

1. Locate the *On Fate* span by three literal, corpus-unique anchor
   strings (verified unique via `grep -c` against the pinned file before
   being hardcoded here): `_PREFACE_ANCHOR` (excludes the translator's
   preface, which is dropped structurally per the brief -- never
   shipped), `_START_ANCHOR` ("[The commencement of this treatise is
   lost.]", KEPT -- this is Yonge/Bohn's own editorial apparatus marking a
   real manuscript lacuna, not OCR noise) through `_END_ANCHOR` ("[The
   rest of this treatise is lost.]", KEPT, same reasoning). The two
   in-body "* * *" lacuna markers (chapter I's opening, chapter III's
   opening) are genuine typeset asterisks in the 1853 scan (not OCR
   artifact). Extraction preserves them; the clean JSON store then
   normalizes them to "..." per John 2026-07-24 (see
   sources/yonge-fato/README.md "Declared normalizations").
2. Strip page-apparatus lines (18 running headers + 2 printer's signature
   marks, "DE NAT. ETC. T" and "T 2") via `_is_apparatus`: a short,
   almost-entirely-uppercase/digit line never occurs in this book's actual
   prose (verified: exactly 20 such lines exist in the sliced span, all of
   them confirmed apparatus by direct inspection -- no false positives).
   Drop the two per-page footnotes verbatim (`_FOOTNOTE_LINES`) --
   editorial apparatus, not translated text, matching this corpus's
   house convention (Falconer/Miller/Yonge-ND all drop footnotes whole).
3. Segment the remaining lines into the 20 roman-numeral chapters (I..XX,
   `_ROMAN_CHAPTERS`), asserting the sequence is exact, strict, and total
   -- any drift (missing/duplicate/out-of-order numeral) raises loudly.
4. Per chapter: strip the chapter's own leading numeral token, flatten
   internal whitespace, join into one paragraph-flattened string (matching
   this corpus's `{chapter, text}` JSON convention -- no embedded
   paragraph breaks, see `sources/yonge-nd/yonge.clean.json`).
5. Apply the OCR-proofing fix table (`_DEFECT_FIXES`, `_HYPHEN_REJOINS`,
   `_GREEK_FIXES`) -- every entry is a literal, corpus-unique substring
   substitution, hand-verified against the 1853 scan's own page images
   (archive.org `treatisescicero00ciceuoft`, all 19 pages 264-282 fetched
   and read directly -- see README's proofing-pass section for the error
   rate and the full defect table with page citations). Each substitution
   is asserted to match exactly once across the whole document; an
   unmatched or duplicated key raises loudly rather than silently
   under/over-applying (the Falconer Beta-Code-table / Rackham
   digit-fix-table discipline).
6. Greek restorations (`_GREEK_FIXES`, 4 terms: ἀξιώματα, θεωρήματα,
   ἐλάχιστος, ἀργὸς λόγος) are hand-verified against the same page images
   AND cross-checked against the PHI Latin spine's own Greek-in-Latin
   runs (`build/dist/de-fato/book-01.json` 1:1, 1:11, 1:22, 1:28 all carry
   the identical Greek terms in the Latin text itself) -- a double
   witness, not a guess.

## Concordance (`concordance.json`)

Built by direct philological comparison of every chapter's opening
sentence against the PHI Latin flat spine's 48 sections (`build/dist/
de-fato/book-01.json`, read only for this comparison -- if that build
artifact is absent, `_build_concordance` still emits the concordance from
the hand-verified table below, since the table itself IS the declared,
cited result of that comparison, not a runtime dependency on it. Rackham's
English was never consulted, per the brief.). Every one of the 20
mappings is content-anchored (a literal matching phrase was located in
both languages -- see README for the full anchor table); none are
interpolated. `start_section` is the section number ACTIVE (already
begun) at the point the English chapter opens, which is not always that
section's own first sentence (Yonge's chapter breaks don't always
coincide with Cicero's own section breaks) -- `section_position` records
which.

**PHI is licensed, local corpus text -- never committed, including as a
concordance anchor.** The Latin side of each anchor pair is stored ONLY
as `decision_key`-style fingerprint (`dk_lang.decision_key`'s own
convention, reused here independently: the first 16 hex characters of the
whitespace-normalized phrase's sha256 digest) plus a short, NON-VERBATIM
structural note (word count, whether it ends at a full stop or mid-clause,
whether it carries an embedded Greek term) -- never the literal Latin.
The English side of each pair IS committed verbatim: Yonge's 1853/1878
translation is the sanctioned public-domain text this whole extraction
exists to ship, so quoting it is exactly what the pipeline is for. See
`_anchor_hash` and `_self_check_concordance` below: the live verification
against the (gitignored, locally-built) Latin spine hashes candidate
word-bounded substrings of each declared section and compares HASHES only
-- the literal PHI text is read from the local build artifact at runtime
and never stored, printed, or committed.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

SRC_TXT = Path("../../build/yonge-fato/treatisesofcicer00ciceuoft_djvu.txt")
OUT = Path("../../sources/yonge-fato/yonge.clean.json")
CONCORDANCE_OUT = Path("../../sources/yonge-fato/concordance.json")
LATIN_SPINE = Path("../../build/dist/de-fato/book-01.json")

_EXPECTED_SHA256 = (
    "c269f19a3bad6d15e8f9b707e522b756a0237f6026b619afc6940683c7af8284"
)
_SRC_ITEM = "treatisesofcicer00ciceuoft"

_PREFACE_ANCHOR = "PREFACE   BY   THE   ORIGINAL   TRANSLATOR."
_START_ANCHOR = "[The  commencement  of  this  treatise  is  lost.]"
_END_ANCHOR = "[The  rest  of  this  treatise  is  lost.]"

_ROMAN_CHAPTERS = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
]
_CHAPTER_MARKER = re.compile(
    r"^(" + "|".join(_ROMAN_CHAPTERS[::-1]) + r")\.\s"
)  # longest-first alternation so "II."/"III." etc. don't false-match on "I."

_FOOTNOTE_LINES = {
    "1  From  jjBos.",
    "1  A  good  deal  of  the  original  is  lo^t  here.",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_apparatus(line: str) -> bool:
    """Page headers ('ON FATE. 265', '266 ON FATE.', OCR-garbled variants
    like 'OX FATE. Z6y') and printer's signature marks ('DE NAT. ETC. T',
    'T 2'): short, almost entirely uppercase/digit lines that never occur
    in this book's actual prose. Verified: exactly 20 lines in the sliced
    span match this, all confirmed apparatus by direct inspection of the
    1853 page images (no false positives, no misses)."""
    s = line.strip()
    if not s:
        return False
    lower = sum(1 for c in s if c.islower())
    return lower <= 1 and len(s) <= 20 and re.search(r"[0-9A-Z]", s)


# ---------------------------------------------------------------------
# Declared, hand-verified OCR fix tables. Every key was checked to occur
# EXACTLY ONCE in the whitespace-normalized, apparatus-and-footnote-
# stripped span before being hardcoded here (see README for the
# verification method and the page-image citation for each).
# ---------------------------------------------------------------------

# Hyphen line-wrap rejoins: (line-final fragment, next-line-first fragment)
# -> correct joined form. Default is to drop the hyphen (soft line-wrap);
# "dog- star," is the one case where the hyphen is a real compound-word
# hyphen and must be kept.
_HYPHEN_REJOINS = [
    ("Pos'do- nius,", "Posidonius,"),
    ("dog- star,", "dog-star,"),
    ("Afri- canus", "Africanus"),
    ("im- possible", "impossible"),
    ("Chry- sippus.", "Chrysippus."),
    ("cpm- pactly", "compactly"),
    ("highway- man", "highwayman"),
    ("Phi- loctetes", "Philoctetes"),
    ("Chrysip- pus", "Chrysippus"),
    ("pre-exist- ent", "pre-existent"),
]

# Dropped-hyphen line-wrap splits: this scan sometimes loses the hyphen
# glyph entirely at a line-wrap, leaving two bare word-fragments separated
# only by a space (no "-"). Found by a systematic dictionary-backed sweep
# of every line-final short fragment in the span (cross-checked against
# /usr/share/dict/words plus common-suffix stripping for inflected forms
# the dictionary lacks, e.g. "submitted"/"sentiments"); every entry below
# was hand-confirmed against the actual sentence context (several
# candidates the sweep also raised -- "many"+"ways", "For"+"how",
# "he."+"In", "be"+"known" -- were REJECTED as genuine two-word text, not
# splits, and are left untouched). Each key is a corpus-unique substring
# (verified via count()==1 against the flattened span); duplicate
# fragment-pairs ("pro"+"position" x2, "con"+"tinue" x2, "every"+"thing"
# x3, "what"+"ever" x2, "sub"+"mitted" x2) are disambiguated with wider
# surrounding context.
_DROPPED_HYPHEN_REJOINS = [
    ("con tinuous", "continuous"),
    ("philoso phical", "philosophical"),
    ("philoso phers", "philosophers"),
    ("sup posing", "supposing"),
    ("expres sion,", "expression,"),
    ("ob jection", "objection"),
    ("meta physical", "metaphysical"),
    ("con stitution", "constitution"),
    ("case nothing what ever would", "case nothing whatever would"),
    ("will be true ; and what ever will", "will be true ; and whatever will"),
    ("prin cipal", "principal"),
    ("par ticular", "particular"),
    ("lasci vious", "lascivious"),
    ("con firmed", "confirmed"),
    ("dis pute", "dispute"),
    ("if the first mem ber", "if the first member"),
    ("the conse quent is", "the consequent is"),
    ("excel lent", "excellent"),
    ("medi cine", "medicine"),
    ("not unavoidable ; and that every thing which", "not unavoidable ; and that everything which"),
    ("who maintain that every thing happens", "who maintain that everything happens"),
    ("says he, every thing happens", "says he, everything happens"),
    ("can not equally", "cannot equally"),
    ("al though we announce", "although we announce"),
    ("inex plicable", "inexplicable"),
    ("propo sition.", "proposition."),
    ("not the case that every pro position called", "not the case that every proposition called"),
    ("prove that every pro position must", "prove that every proposition must"),
    ("attrac tion", "attraction"),
    ("imagi nary", "imaginary"),
    ("happen ing", "happening"),
    ("phy sician", "physician"),
    ("idle ness,", "idleness,"),
    ("defi nitively", "definitively"),
    ("differ ence,", "difference,"),
    ("even tually", "eventually"),
    ("must happen are cer tain", "must happen are certain"),
    ("unembar rassed", "unembarrassed"),
    ("indiges tion", "indigestion"),
    ("the con sequence is", "the consequence is"),
    ("How ever, the", "However, the"),
    ("compulsion and neces sity.", "compulsion and necessity."),
    ("con trol,", "control,"),
    ("they con tinue their gyrations", "they continue their gyrations"),
    ("it will con tinue for", "it will continue for"),
    ("dis similarity", "dissimilarity"),
    ("disposi tions", "dispositions"),
    ("senti ments were free", "sentiments were free"),
    ("alterna tives,", "alternatives,"),
    ("dispu tants,", "disputants,"),
    ("instance, is not sub mitted to antecedent", "instance, is not submitted to antecedent"),
    ("the effect, are sub mitted to the empire", "the effect, are submitted to the empire"),
    ("true are neces sary,", "true are necessary,"),
    ("senti ments of", "sentiments of"),
    ("dis turbances,", "disturbances,"),
    ("the Chal deans to put up", "the Chaldeans to put up"),
    ("hap pened.", "happened."),
    ("sub sisting", "subsisting"),
    ("conse quences", "consequences"),
    ("pro duces", "produces"),
    ("pro positions", "propositions"),
    ("distin guishes", "distinguishes"),
    ("hap pens", "happens"),
    ("investiga tion,", "investigation,"),
    ("correspond ing", "corresponding"),
]

# Letter/word/punctuation-level OCR defects, each cited to its printed
# page (1853 scan, archive.org treatisescicero00ciceuoft) in the README.
_DEFECT_FIXES = [
    ("veiy much", "very much"),  # p265
    ("}rour choice", "your choice"),  # p265
    ("forget thut I", "forget that I"),  # p266
    ("your writing : so begin.1", "your writing; so begin."),  # p266 (colon->semicolon + drop footnote-marker digit)
    ("field of Mara ?", "field of Mars?"),  # p267
    ("in the sea \" Take", "in the sea.\" Take"),  # p269 (missing period before close-quote)
    ("is impossible. fiTou both", "is impossible. You both"),  # p269
    ("although Apolfo's oracle", "although Apollo's oracle"),  # p269
    ("the dog- star he", "the dog-star he"),  # p270 (stray space inside compound, not a line-wrap)
    ("thei-e is no more", "there is no more"),  # p270
    ("leads them oat of", "leads them out of"),  # p271
    ("This fact was oot without", "This fact was not without"),  # p272
    ("its proper natiire is", "its proper nature is"),  # p274
    ("Scipio shall take Xumantia,", "Scipio shall take Numantia,"),  # p275
    ("predicted GOO years", "predicted 600 years"),  # p275
    ("impossible to be maintained. I Nor need", "impossible to be maintained. Nor need"),  # p275 (stray glyph)
    ("as true. v/And therefore", "as true. And therefore"),  # p277
    ("they do not, in fa^t, agree", "they do not, in fact, agree"),  # p277
    ("murder, because he was Clyteinnestra's", "murder, because he was Clytemnestra's"),  # p277
    ("fall'n heneath the woodman's", "fall'n beneath the woodman's"),  # p278
    ("two contradictious are true", "two contradictions are true"),  # p279
    ("these two opinions Chrysippxis, as", "these two opinions Chrysippus, as"),  # p279
    ("Those wrho held the opposite", "Those who held the opposite"),  # p279
    ("from the t}rranny of necessity", "from the tyranny of necessity"),  # p279
    ("destruction of frea-will. But", "destruction of free-will. But"),  # p280
    ("hinder these efiects from happening", "hinder these effects from happening"),  # p281
    ("For even thmigh there", "For even though there"),  # p282
    ('shall beget CEdipus," then', 'shall beget Œdipus," then'),  # p276 (Œ ligature)
    ("that he will beget CEdipus. In", "that he will beget Œdipus. In"),  # p276
    ("predict in the case of OEdipus that", "predict in the case of Œdipus that"),  # p277
    ("do1?", "do?"),  # p267 (stray digit glued before a real question mark)
    ("ethics,1 the", "ethics, the"),  # p264 (drop footnote-marker digit; footnote text itself is dropped, see _FOOTNOTE_LINES)
]

# The "?" misread as a bare digit "1" (this scan's systematic defect --
# confirmed via the 1853 page images: every one of these is a genuine "?"
# in print). 15 instances, each a corpus-unique context string.
_QUESTION_MARK_FIXES = [
    ("give you pleasure 1 Do", "give you pleasure? Do"),
    ("fortune 1", "fortune?"),
    ("of another 1 or", "of another? or"),
    ("the calends 1", "the calends?"),
    ("does it proceed 1 I", "does it proceed? I"),
    ("gravity 1 For", "gravity? For"),
    ("happen 1 For", "happen? For"),
    ("in the sea 1 This", "in the sea? This"),
    ("are future 1 for", "are future? for"),
    ("series of causes 1 By", "series of causes? By"),
    ("past events 1 Because", "past events? Because"),
    ("isle of Lemnos 1 Afterwards", "isle of Lemnos? Afterwards"),
    ("why is it so 1 It", "why is it so? It"),
    ("that way 1 If", "that way? If"),
    ("say 1 — if", "say? — if"),
]

_GREEK_FIXES = [
    ("term axioms (a^ico/mra).", "term axioms (ἀξιώματα)."),  # p264: ἀξιώματα
    ("call theorems (^ecDpf/jMara).", "call theorems (θεωρήματα)."),  # p268: θεωρήματα
    ("Epicurus calls it eAc^ta-ros or", "Epicurus calls it ἐλάχιστος or"),  # p273: ἐλάχιστος
    ("some philosophers, apyos Aoyos, which", "some philosophers, ἀργὸς λόγος, which"),  # p275: ἀργὸς λόγος
]


# ---------------------------------------------------------------------
# Residual-garble safety net. The README claims (Greek restorations
# section) "No unrecognized Greek-looking garble remains -- every
# non-ASCII-suspect run in the span was accounted for" by `_GREEK_FIXES`
# above. That claim was hand-verified once; this is the machine-checked
# proof of it, run in `extract()` after every declared fix table --
# including `_GREEK_FIXES` -- has been applied to a chapter's text. It is
# bounded and heuristic, not exhaustive: it catches the two shapes this
# particular OCR pass's own garble takes (see `_GREEK_FIXES`'s own raw
# left-hand sides -- "a^ico/mra", "^ecDpf/jMara", "eAc^ta-ros" -- every one
# carries a caret or a mid-word slash, or an internal lowercase-then-
# uppercase letter transition no genuine 1853/1878 English word has), plus
# any non-ASCII character that is neither Greek script (the sanctioned,
# hand-verified restorations) nor one of the small set of non-Greek
# non-ASCII characters this corpus's clean output legitimately carries
# (the Œ/œ ligature from the Œdipus fix, the em dash). If this ever
# fires -- including against the real, currently-claimed-clean 20
# chapters -- STOP: it means the hand verification missed something, not
# that the detector is wrong.
_GARBLE_SYMBOL_RE = re.compile(r"[A-Za-z]*[\^/][A-Za-z]*")
_GARBLE_INTERNAL_CAP_RE = re.compile(r"[a-z]+[A-Z]")
_SANCTIONED_NON_GREEK_NONASCII = {"Œ", "œ", "—"}


def _is_greek_char(ch: str) -> bool:
    """Mirrors `dk_lang.is_greek_letter`'s test (name-prefix check), but
    tests any character, not just letters -- a Greek diacritic/breathing
    mark alone (rare, none expected here) would still need to pass this
    gate rather than being flagged as residue."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK")


def _looks_like_ocr_garble(token: str) -> bool:
    """True for a whitespace-delimited token matching this scan's own
    documented garble signature (see the module comment above) -- a caret
    or mid-word slash, or an internal lowercase-then-uppercase transition.
    Verified to fire on zero tokens across the current, hand-verified-clean
    20 chapters (see test_extract_yonge_fato.py)."""
    return bool(_GARBLE_SYMBOL_RE.search(token) or _GARBLE_INTERNAL_CAP_RE.search(token))


def _check_no_residual_garble(text: str) -> None:
    """Fails loud, naming the exact residue, if `text` (a chapter's fully
    fixed flattened string) still carries a garble-shaped token or an
    unaccounted-for non-ASCII character. See the module comment above this
    section for the full rationale; called from `extract()` immediately
    after `_GREEK_FIXES` is applied, once per chapter."""
    garbled = [tok for tok in text.split() if _looks_like_ocr_garble(tok)]
    if garbled:
        raise ValueError(f"residual OCR-garble-shaped token(s) in fixed text: {garbled!r}")
    bad_chars = sorted(
        {ch for ch in text if ord(ch) > 127 and ch not in _SANCTIONED_NON_GREEK_NONASCII and not _is_greek_char(ch)}
    )
    if bad_chars:
        raise ValueError(
            f"residual non-ASCII, non-Greek character(s) in fixed text: {bad_chars!r}"
        )


def _apply_fixes(text: str, table: list[tuple[str, str]]) -> tuple[str, int]:
    applied = 0
    for old, new in table:
        if not old:
            continue
        n = text.count(old)
        if n == 0:
            continue
        if n > 1:
            raise ValueError(f"fix key matched {n} times, expected <=1: {old!r}")
        text = text.replace(old, new)
        applied += 1
    return text, applied


def _load_source() -> list[str]:
    raw = SRC_TXT.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != _EXPECTED_SHA256:
        raise ValueError(
            f"{SRC_TXT} sha256 mismatch: expected {_EXPECTED_SHA256}, got {got}"
        )
    return raw.decode("utf-8").split("\n")


def _slice_span(lines: list[str]) -> list[str]:
    start_i = next(i for i, l in enumerate(lines) if l.strip() == _START_ANCHOR.strip())
    end_i = next(i for i, l in enumerate(lines) if l.strip() == _END_ANCHOR.strip())
    # Sanity: the preface anchor must exist and precede the span (excluded).
    preface_i = next(i for i, l in enumerate(lines) if l.strip() == _PREFACE_ANCHOR.strip())
    if not (preface_i < start_i < end_i):
        raise ValueError("anchor ordering assumption violated")
    return lines[start_i : end_i + 1]


def _strip_apparatus(
    span: list[str], expected_apparatus: int = 20, expected_footnotes: int | None = None
) -> list[str]:
    if expected_footnotes is None:
        expected_footnotes = len(_FOOTNOTE_LINES)
    kept = []
    dropped_apparatus = 0
    dropped_footnotes = 0
    for line in span:
        if _is_apparatus(line):
            dropped_apparatus += 1
            continue
        if line.strip() in _FOOTNOTE_LINES:
            dropped_footnotes += 1
            continue
        kept.append(line)
    if dropped_apparatus != expected_apparatus:
        raise ValueError(f"expected {expected_apparatus} apparatus lines, dropped {dropped_apparatus}")
    if dropped_footnotes != expected_footnotes:
        raise ValueError(f"expected {expected_footnotes} footnote lines, dropped {dropped_footnotes}")
    return kept


def _segment_chapters(
    lines: list[str], expected_romans: list[str] | None = None
) -> list[list[str]]:
    if expected_romans is None:
        expected_romans = _ROMAN_CHAPTERS
    marker_idx = [i for i, l in enumerate(lines) if _CHAPTER_MARKER.match(l.strip())]
    if len(marker_idx) != len(expected_romans):
        raise ValueError(f"expected {len(expected_romans)} chapter markers, found {len(marker_idx)}")
    found_romans = []
    for i in marker_idx:
        match = _CHAPTER_MARKER.match(lines[i].strip())
        found_romans.append(match.group(1))
    if found_romans != expected_romans:
        raise ValueError(f"chapter marker sequence mismatch: {found_romans}")

    segments = []
    for n, i in enumerate(marker_idx):
        seg_start = 0 if n == 0 else i  # chapter I's segment also absorbs the
        # preceding "[The commencement...]" bracket line (and the blank line
        # after it), since that segment starts at 0, not at marker_idx[0].
        seg_end = marker_idx[n + 1] if n + 1 < len(marker_idx) else len(lines)
        seg = list(lines[seg_start:seg_end])
        # Strip this chapter's own leading roman-numeral marker from its
        # marker line (which is always the LAST line of the segment for
        # chapter I -- since seg_start=0 -- and the FIRST line otherwise).
        marker_pos = i - seg_start
        stripped = _CHAPTER_MARKER.sub("", seg[marker_pos].strip(), count=1)
        seg[marker_pos] = stripped
        segments.append(seg)
    return segments


def _flatten(seg: list[str]) -> str:
    parts = [_norm(l) for l in seg]
    parts = [p for p in parts if p]
    return " ".join(parts)


def extract() -> list[dict]:
    lines = _load_source()
    span = _slice_span(lines)
    span = _strip_apparatus(span)
    segments = _segment_chapters(span)

    chapters = [_flatten(seg) for seg in segments]

    total_hyphen = 0
    total_dropped_hyphen = 0
    total_defect = 0
    total_qmark = 0
    total_greek = 0
    fixed_chapters = []
    for text in chapters:
        text, n1 = _apply_fixes(text, _HYPHEN_REJOINS)
        text, n1b = _apply_fixes(text, _DROPPED_HYPHEN_REJOINS)
        text, n2 = _apply_fixes(text, _DEFECT_FIXES)
        text, n3 = _apply_fixes(text, _QUESTION_MARK_FIXES)
        text, n4 = _apply_fixes(text, _GREEK_FIXES)
        _check_no_residual_garble(text)
        total_hyphen += n1
        total_dropped_hyphen += n1b
        total_defect += n2
        total_qmark += n3
        total_greek += n4
        fixed_chapters.append(text)

    if total_hyphen != len(_HYPHEN_REJOINS):
        raise ValueError(f"hyphen rejoins applied {total_hyphen}, expected {len(_HYPHEN_REJOINS)}")
    if total_dropped_hyphen != len(_DROPPED_HYPHEN_REJOINS):
        raise ValueError(
            f"dropped-hyphen rejoins applied {total_dropped_hyphen}, expected {len(_DROPPED_HYPHEN_REJOINS)}"
        )
    if total_defect != len(_DEFECT_FIXES):
        raise ValueError(f"letter/punctuation fixes applied {total_defect}, expected {len(_DEFECT_FIXES)}")
    if total_qmark != len(_QUESTION_MARK_FIXES):
        raise ValueError(f"question-mark fixes applied {total_qmark}, expected {len(_QUESTION_MARK_FIXES)}")
    if total_greek != len(_GREEK_FIXES):
        raise ValueError(f"Greek restorations applied {total_greek}, expected {len(_GREEK_FIXES)}")

    records = [
        {"chapter": n + 1, "text": text} for n, text in enumerate(fixed_chapters)
    ]
    return records


# ---------------------------------------------------------------------
# Concordance: hand-verified chapter -> Latin-section table (see module
# docstring and README for the full anchor citations). Each entry was
# built by locating chapter N's opening English sentence's exact Latin
# counterpart in build/dist/de-fato/book-01.json and recording which of
# the 48 sections contains it.
#
# PHI Latin is licensed corpus text -- never committed, including here.
# `anchor_lat_sha256_16` is NOT the literal Latin phrase: it is
# `_anchor_hash(phrase)`, the first 16 hex characters of the
# whitespace-normalized phrase's sha256 digest (dk_lang.decision_key's own
# convention, reused independently -- see module docstring). Every hash
# below was computed once, by hand, from the same hand-verified anchor
# phrases the original philological comparison produced; the phrases
# themselves are never written to this file or to concordance.json.
# `anchor_lat_note` is a short, NON-VERBATIM structural label (word count;
# whether the phrase ends at a full stop, "?", ";" or mid-clause; whether
# it carries an embedded Greek term) -- it exists only so a reviewer can
# tell entries apart without the Latin text in hand, and it must never
# quote the phrase. The English anchor stays verbatim: Yonge's translation
# is the sanctioned public-domain text this pipeline exists to ship.
# ---------------------------------------------------------------------
_CONCORDANCE = [
    # chapter, start_section, section_position, anchor_lat_sha256_16, anchor_lat_note, english anchor (short)
    (1, 1, "start", "511e2cad50c26f79", "8w, incl.-Greek-term, mid-clause", "THAT branch of philosophy which, because it relates to manners, the Greeks usually term ethics"),
    (2, 3, "start", "fa7fb458d0b7b749", "13w, mid-clause", "Since you have not, as I hope, abandoned your oratorical studies"),
    (3, 5, "start", "a70714829a1ea426", "7w, mid-clause", "in some of which, as in the case of Antipater the poet"),
    (4, 7, "start", "4e71549bf86d5e22", "13w, mid-clause", "let us, however, as we fairly may, dismiss Posidonius, without any offence to him, and turn our attention to the sophisms of Chrysippus"),
    (5, 9, "start", "e40f71e4b1f655c7", "13w, mid-clause", "he shows that he does not understand the true question, nor its principal difficulties"),
    (6, 11, "mid", "859fdf37f9341363", "9w, ends-'?'", "If you insist on the reality of divination, I once more ask, from what perceptions of art does it proceed?"),
    (7, 13, "start", "799470589a67eed7", "14w, mid-clause", "this consequence, however, is by no means agreeable to you, O Chrysippus, and this very point is your main dispute with Diodorus"),
    (8, 15, "start", "6970dfbb7288e0ba", "9w, mid-clause", "On this topic Chrysippus exerts all his ingenuity. He pretends that the Chaldeans are deceived"),
    (9, 17, "start", "0d82867eb35b4db8", "10w, incl.-Greek-term, mid-clause", "let us return to the question concerning possibility, so warmly contested by Diodorus"),
    (10, 20, "mid", "0c00b7b7e7a66f8b", "5w, ends-'.'", "This is all that we need say concerning possibility. Let us pass on to other matters."),
    (11, 23, "mid", "270917744d9b60bc", "13w, mid-clause", "Carneades argued more acutely when he taught that the Epicureans might defend their cause without this imaginary declination of atoms"),
    (12, 26, "end", "d64e799ad2661c6d", "16w, mid-clause", "The dispute then is at an end, since you must needs grant either that all things happen by fate, or that some effects may exist without external causes"),
    (13, 29, "mid", "bd5f9d0774d0a61f", "9w, mid-clause", "Very properly, therefore, is this argument called inactive"),
    (14, 31, "start", "486cf4eaa4767d0d", "13w, mid-clause", "Carneades, however, absolutely rejects this method of reasoning, and thinks that these conclusions are adopted too hastily"),
    (15, 33, "end", "e2f9df6491f057d9", "19w, mid-clause", "Wherefore if the Stoics, who maintain that everything happens by fate, are obliged in consistence with their principle to admit the truth of oracles of this kind"),
    (16, 36, "start", "514cc8ab35f6d432", "23w, mid-clause", "there is a difference, say they, between a cause without which an effect cannot happen, and a cause which necessarily produces an effect"),
    (17, 39, "start", "57bf162d6dfdb910", "10w, mid-clause", "It appears, indeed, to me, since the ancient philosophers are divided into two parties on the doctrine of fate"),
    (18, 41, "start", "5c71714e4df73be2", "16w, mid-clause", "Chrysippus, rejecting necessity, yet believing that nothing can happen without antecedent causes, distinguishes causes into two kinds"),
    (19, 43, "start", "ccfb6a9cebe5d0d6", "11w, mid-clause", "a man who pushes a cylinder gives it a principle of motion, but not immediately that of"),
    (20, 46, "start", "a35676a0f20da3a8", "16w, mid-clause", "It is according to these principles that we should examine the question concerning fate, and not rush with Epicurus to a fortuitous concourse of atoms"),
]


def _anchor_hash(phrase: str) -> str:
    """dk_lang.decision_key's own convention, reused independently here (no
    import coupling to that module -- same convention, different domain):
    the first 16 hex characters of the sha256 digest of the phrase after
    whitespace-normalization (collapsed internal whitespace, outer-
    trimmed). This is what `anchor_lat_sha256_16` values are -- never the
    literal phrase, which is not stored anywhere in this repo."""
    return hashlib.sha256(_norm(phrase).encode("utf-8")).hexdigest()[:16]


def _self_check_concordance() -> None:
    """If the Latin spine build artifact is present (it's gitignored, so
    may be absent in some environments), assert every declared anchor's
    HASH actually matches some word-bounded substring of its declared
    section -- a live check on top of the hand verification, not a
    substitute for it. This never reconstructs, stores, or prints the
    literal Latin anchor phrase: it hashes candidate substrings read live
    from the (uncommitted) build artifact and compares only the hashes."""
    if not LATIN_SPINE.exists():
        return
    spine = json.loads(LATIN_SPINE.read_text())
    by_id = {
        seg["id"]: _norm(" ".join(g["text"] for g in seg["greek"])).split(" ")
        for seg in spine["segments"]
    }
    # A hand-picked anchor's first/last word sometimes drops a punctuation
    # or quote mark attached to that word in the flat spine text (a
    # trailing comma the anchor omitted for readability, or a dialogue-
    # opening quote glyph glued to the anchor's first word) -- candidates
    # are hashed both as-is and with edge punctuation/quotes trimmed from
    # the outermost word(s), so this mirrors the pre-hash code's plain
    # substring check (which tolerated the same edge slack) without ever
    # needing the literal phrase.
    edge_punct = " ,.;:?!'‘’“”"
    for chapter, section, _pos, anchor_hash, _note, _en in _CONCORDANCE:
        key = f"1:{section}"
        if key not in by_id:
            raise ValueError(f"concordance chapter {chapter}: section {key} not in Latin spine")
        words = by_id[key]
        found = False
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                candidate = " ".join(words[i:j])
                variants = {candidate, candidate.strip(edge_punct)}
                if any(_anchor_hash(v) == anchor_hash for v in variants):
                    found = True
                    break
            if found:
                break
        if not found:
            raise ValueError(
                f"concordance chapter {chapter}: anchor hash {anchor_hash} not found in {key}"
            )


def build_concordance() -> dict:
    _self_check_concordance()
    starts = [c[1] for c in _CONCORDANCE]
    if starts[0] != 1:
        raise ValueError("chapter 1 must start at section 1")
    if any(b <= a for a, b in zip(starts, starts[1:])):
        raise ValueError(f"start_section must be strictly increasing: {starts}")
    if starts[-1] >= 48:
        raise ValueError("chapter XX must start before the final section 48")
    records = [
        {
            "chapter": chapter,
            "start_section": section,
            "exact": True,
            "section_position": pos,
            "anchor_lat_sha256_16": anchor_lat_hash,
            "anchor_lat_note": anchor_lat_note,
            "anchor_en": anchor_en,
        }
        for chapter, section, pos, anchor_lat_hash, anchor_lat_note, anchor_en in _CONCORDANCE
    ]
    return {
        "_comment": (
            "Chapter->section concordance for Cicero, De Fato (Yonge's "
            "chapter-keyed English translation -> the PHI flat Latin "
            "spine, sections 1-48). See sources/yonge-fato/README.md for "
            "the full methodology. Every start_section here is "
            "content-anchored (a literal matching phrase was located in "
            "both the English chapter's opening and a specific Latin "
            "section) -- none are interpolated. PHI Latin is licensed "
            "corpus text and is never committed: 'anchor_lat_sha256_16' is "
            "NOT the literal Latin phrase, it is the first 16 hex "
            "characters of the whitespace-normalized phrase's sha256 "
            "digest (dk_lang.decision_key's convention); 'anchor_lat_note' "
            "is a short, non-verbatim structural label (word count / "
            "ending punctuation / embedded-Greek-term flag), never a "
            "quote. 'anchor_en' is the sanctioned, verbatim public-domain "
            "English (Yonge, 1853/1878) this pipeline exists to ship. "
            "'exact': true for all 20 records means the value is a "
            "directly witnessed textual anchor, not a linear "
            "interpolation/extrapolation. 'section_position' records "
            "whether the anchor falls at the start, middle, or end of its "
            "Latin section (Yonge's chapter breaks don't always coincide "
            "with Cicero's own section breaks)."
        ),
        "records": records,
    }


def main() -> None:
    records = extract()
    if len(records) != 20:
        raise ValueError(f"expected 20 chapter records, got {len(records)}")
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} records to {OUT}")

    concordance = build_concordance()
    CONCORDANCE_OUT.write_text(
        json.dumps(concordance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote concordance ({len(concordance['records'])} records) to {CONCORDANCE_OUT}")


if __name__ == "__main__":
    main()
