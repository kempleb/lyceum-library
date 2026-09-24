"""One-off: extract Cyril Bailey's 1926 Clarendon translation of Epicurus
("Epicurus: The Extant Remains") from the raw archive.org OCR text
(sources/bailey-epicurus/bailey-extant-remains-1926.djvu.txt -- see
sources/INVENTORY.md) into three clean per-part English stores: the three
Letters (to Herodotus, to Pythocles, to Menoeceus), the Principal Doctrines
(Kyriai Doxai), and the Vatican Collection (Sententiae Vaticanae).

## The source: a bilingual facing-page edition, OCR'd flat

Like the Haines Meditations (see extract_haines.py, whose architecture this
script follows), this is a facing-page bilingual edition read by a flat OCR
pass in physical page order: Greek text (with its own apparatus criticus)
and English translation interleave, and roughly 44% of the raw lines are
Greek. Unlike Haines, though, this OCR run preserved the Greek in real
Greek-script Unicode rather than transliterating it into Latin-alphabet
noise -- so a per-line "does this line contain a Greek-script character"
test (`_has_greek`) is a highly reliable, cheap discriminator that drops
essentially all Greek prose AND the mixed Greek/Latin critical apparatus (a
sweep of the Letter to Herodotus confirms apparatus lines almost always cite
at least one Greek word, so they carry a Greek character too).

## What's left after the Greek-line filter

Running heads and page furniture, which this OCR renders as an ALL-CAPS
line ("EPICURUS TO HERODOTUS", "I. TO HERODOTUS 21", "PRINCIPAL DOCTRINES",
"IV. PRINCIPAL DOCTRINES 99", "V. FRAGMENTS 111") -- genuine translated
prose is never rendered in all caps, so `_is_heading_line` (all alphabetic
characters upper-case, >=3 of them) drops these regardless of the exact
wording or of the numeral-prefix corruption OCR inflicts on them (roman
numerals and page numbers misread every which way: "1. FO HERODOTUS 49.",
"Il. TO PYTHOCLES 6", "I], TO. PYTHOCLES 69" -- none of that variation
matters once the test is "is this whole line shouting").

The remaining page furniture is page-bottom stray numbers (bare digit
lines, sometimes with a lone OCR'd punctuation mark: "37 ", "46\" ") and the
literal word "Scholia" heading a block of Greek scholiast notes (itself
Greek and so already dropped, but its own heading is plain Latin script) --
both dropped structurally (`_is_bare_marker`, `_is_scholia_heading`) because
neither carries the >=2-real-word content a translated sentence always does.
A handful of surviving Latin-script apparatus fragments (sigla lists,
lone editor surnames such as "Cronert") are caught the same way Haines'
sibling apparatus fragments are: `_looks_english`, a common-word-ratio test.

## Known, disclosed limitation: the marginal synopsis column

Bailey's printed page carries a third, narrow marginal column of short
topic labels ("Introduction:", "Methods of procedure,", "The nature of
void,"...) beside the main translation. The flat OCR interleaves this
column's fragments into the SAME physical line as the main prose members
next to it, mid-sentence, with no distinguishing case or punctuation signal
(both columns are ordinary English prose fragments) -- unlike the Greek/
English split, there is no per-line signal available in the bare OCR text
that discriminates "which of these words belongs to the main translation".
This script makes NO attempt to strip these fragments: doing so without a
reliable signal would risk deleting real translated words, which is worse
than leaving a disclosed, sparse contamination in place. Coverage is
otherwise faithful to the OCR; this limitation is recorded in meta.json
verbatim so nobody mistakes silence for cleanliness.

## Anchors: DL section numbers (Letters) and roman numerals (KD, VS)

The three Letters carry Diogenes Laertius' own section numbers (Herodotus
35-83, Pythocles 84-116, Menoeceus 122-135) as a leading digit run at the
very start of an English OCR line (`_DECIMAL_ANCHOR`); Bailey's own section
breaks do not always land on an English sentence boundary (the Usener/DL
segmentation is a citation scheme, not a grammatical one), so unlike Haines'
_opens_sentence gate this script only requires strict decimal continuity
(current + 1) plus a bounded forward-jump recovery for a single
unrecoverably corrupted marker (`_MAX_JUMP`, same rationale as Haines).

The Principal Doctrines (I-XL) and Vatican Collection (I-LXXXI) instead
carry roman numerals. This OCR's dominant roman-numeral defect is a dropped
"I" (a doubled capital I misreading as one wider glyph, or as "f"/"l"): "If."
for "II.", "XXII." for what is structurally the Vatican Collection's XXIII.
`_match_roman` accepts a marker one below the expected value as a corrected
read (logging the correction) precisely because of this attested pattern,
never further -- a marker two or more below expected is left unrecovered.

## The Vatican Collection's cross-reference-only sayings

A number of Vatican Collection sayings are not independent text at all: the
manuscript itself just cross-references a Principal Doctrine ("VI. = Kupiai
Δόξαι XXXV." -- "VI. = Principal Doctrine XXXV"). These lines are Greek
script and so vanish under the Greek-line filter along with everything
else; **left alone, that would silently turn a real editorial fact (there
is no independent English here) into an ordinary, unremarked-upon gap**.
`_scan_vs_crossrefs` runs a SEPARATE pass over the raw (pre-filter) lines
restricted to the Vatican Collection's line range specifically to find
these cross-reference lines and record them, with the raw OCR line as
evidence, as an explicit skip -- never a guess at what the missing English
might say. Confirmed instances: 1, 2, 3, 5, 6, 8, 13, 20, 22, 49, 50, 72.

## 2026-07-29 fixes (Grok verification-gate findings)

A verification pass found five defect classes and they are now fixed, each
with its own regression test in `test_extract_bailey_epicurus.py`:
(1) an isolated Greek-script garble word no longer condemns an otherwise-
English line (`_strip_greek_tokens`, gated on the Greek being a small
minority of the line so genuine apparatus/Greek prose is still dropped
outright); a hyphen-break continuation and a short terminal-punctuated
sentence-close are now accepted even when they fail the ordinary common-
word-ratio bar (`_accept_line`, `_hyphen_continues`,
`_looks_like_sentence_close`); a leading bracket before a roman-numeral
anchor (Bailey's own doubtful-attribution marks, Vatican Sayings 10/30/36)
and a leading "A" standing in for a dropped "X" (Sayings 18/31/34) are both
recognised; a dropped trailing "I" stroke or two (Sayings 23, 43, 48) is
repaired without an edit-distance test. (2) bracketed numerals keep
Bailey's brackets in the extracted text; a forward-jump repair now prefers
an EXACT match anywhere in its window over a fuzzy one at an earlier
position, so a numeral that reads correctly for a later saying is never
shadowed by an earlier one it merely resembles once a repair is applied
(Saying 58 no longer misfiles as 57); the Vatican crossref scan gained a
narrow fallback for Saying 72's own Greek-mixed damaged numeral, so Saying
73 lands on its own key instead of being swallowed by a phantom "72".
(0) [second gate, same date] a decimal section anchor whose own printed
position falls literally inside a hyphenated word (Letter to Pythocles
107/108: "...a process most fre-" / "108 quent in the atmosphere...") is
now resolved to the nearest WORD edge rather than left mid-word
(`_resolve_anchor_mid_word`); a digit/letter homoglyph ("1" for "i",
glued onto "s"/"n"/"t"/"f" with no space -- "1s", "1n", "1t", "1f") is
now corrected everywhere via a conservative, word-boundary-gated general
rule (`_fix_digit_letter_homoglyphs`, 56 occurrences confirmed by a full
sweep) rather than dozens of one-off patches; a further ~13 non-
generalizable OCR defects (stray page numbers and marginal-column
fragments glued onto real words with no space, an isolated "3" for "i",
two isolated "!" for "l", one "Tue" for "The") are corrected via
PATCHES.json entries, each carrying its own raw-OCR line evidence.
(3) the 6,000-character merge cap is now a hard invariant enforced AT
FLUSH TIME by cutting to the last full sentence at or before the cap
(`_cut_at_sentence_boundary`) -- never mid-word -- with genuine overflow
recorded honestly as `unassigned` text in `meta.json`, never silently kept
past the cap or silently dropped. (4) `meta.json`'s `gaps` now come from
`_compute_gaps`, itemizing every expected-but-absent number in the full
range -- including a trailing run after the walk's last anchor, which
previously produced no gap record at all (Herodotus 58-83, Pythocles
115-116, Menoeceus 124-135). (5) a rare inline compound anchor spanning
two numbers at once ("LVI-LVII.", Vatican Collection 56-57, which Bailey
prints with no separate saying at either number) is now recognised
(`_match_roman_range`) and stored under its own compound key, "56-57",
recorded in `meta.json`'s `vs.compound_sayings`.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SRC = Path("../sources/bailey-epicurus/bailey-extant-remains-1926.djvu.txt")
OUT_LETTERS = Path("../sources/bailey-epicurus/bailey-letters.clean.json")
OUT_KD = Path("../sources/bailey-epicurus/bailey-kd.clean.json")
OUT_VS = Path("../sources/bailey-epicurus/bailey-vs.clean.json")
OUT_META = Path("../sources/bailey-epicurus/meta.json")
PATCHES = Path("../sources/bailey-epicurus/PATCHES.json")

_EXPECTED_SHA256 = "50924207cdee3361c00aabd8d4fdfb443e022e912958e2f1f43ab2c4aebbd55f"

_WITNESS_URL = (
    "https://archive.org/details/EpicurusTheExtantRemainsBaileyOxford1926_201309"
)


def _verify_source() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"missing {SRC} -- fetch the tesseract text layer of {_WITNESS_URL} "
            "and place it there before running."
        )
    actual = hashlib.sha256(SRC.read_bytes()).hexdigest()
    if actual != _EXPECTED_SHA256:
        raise SystemExit(
            f"SHA-256 mismatch for {SRC}: expected {_EXPECTED_SHA256}, got {actual} "
            "-- the vendored copy must not have changed; re-verify before proceeding."
        )


# --- script / noise classification -------------------------------------------

def _has_greek(line: str) -> bool:
    return any("Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿" for c in line)


# A single isolated Greek-script OCR garble word inside an otherwise
# English line (the marginal-synopsis column and stray misreads both
# produce this: "prepared at sufficient Iength an epitome of the whole
# διρθεπι" -- letter-to-herodotus:35) must not sink the real English
# prose sharing its physical OCR line the way a genuinely Greek or
# Greek/Latin-apparatus line should. Stripping every Greek-script TOKEN
# (never a partial word -- OCR never splits a token mid-word against
# whitespace) and re-testing what remains against `_looks_english` is the
# fix -- but ONLY when the Greek is genuinely isolated (at most 2 tokens,
# at most 30% of the line): apparatus criticus lines routinely mix several
# Greek citation words into otherwise-Latin editorial noise ("XXXII I cep
# Usener : σεβαστοεν τ
# σεβαστὸς (λόγος) a ey"),
# and stripping FOUR Greek tokens out of eleven can still coincidentally
# leave two short common words ("I", "a") behind, clearing the same bar a
# genuine one-word garble does. Gating the strip itself on how much of the
# line was Greek keeps that apparatus noise correctly rejected outright
# (as it always was) while still recovering the narrow, evidenced case.
def _strip_greek_tokens(line: str) -> str | None:
    tokens = line.split()
    greek_tokens = [t for t in tokens if _has_greek(t)]
    if not greek_tokens:
        return line
    if len(greek_tokens) > 2 or len(greek_tokens) / len(tokens) > 0.3:
        return None
    return " ".join(t for t in tokens if not _has_greek(t))


# The OCR occasionally sets a roman numeral's letters using their visually
# IDENTICAL Greek-script capitals -- capital Chi (Χ) for Latin X being the
# case actually attested (Principal Doctrine X's own opening line: "Χ. If
# the things that produce..."). Left alone this would drop an otherwise
# perfectly good English line under `_has_greek` (one Greek-script
# character is enough to condemn the whole line), silently losing both the
# anchor and its content. Only a short leading run (roman-numeral length)
# of these specific lookalikes, immediately before "." or "," and a space,
# is corrected -- never a Greek character anywhere else in the line, which
# is always genuine Greek text or apparatus.
_LEADING_GREEK_NUMERAL = re.compile(r"^([ΙΧΥ]{1,4})([.,]\s+\S.*)$")
_GREEK_TO_LATIN_NUMERAL = {"Ι": "I", "Χ": "X", "Υ": "U"}


def _fix_leading_greek_numeral(line: str) -> str:
    m = _LEADING_GREEK_NUMERAL.match(line)
    if not m:
        return line
    fixed = "".join(_GREEK_TO_LATIN_NUMERAL[c] for c in m.group(1))
    return fixed + m.group(2)


# A running head or part-title, this OCR's one reliably-preserved typographic
# signal: printed in small caps / all caps, never how Bailey's own English
# prose is set. Requires at least 3 upper-case letters so a bare 1-2 letter
# roman numeral ("VI") is never caught by this rule alone.
def _is_heading_line(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


_BARE_MARKER = re.compile(r"^[0-9]{1,4}[.,\"'°*]{0,2}$")
_SCHOLIA = re.compile(r"(?i)^scholia\.?$")


def _is_bare_marker(line: str) -> bool:
    return bool(_BARE_MARKER.match(line)) or bool(_SCHOLIA.match(line))


# A generous common-English-word set (same role as extract_haines.py's own
# list: not a dictionary, a discriminator against Latin-script apparatus
# noise -- editor surnames, sigla lists -- which rarely produces two hits).
_ENGLISH_WORDS = set("""
the of and to in a is that it as for with not but he his this which be are
from at by on or an was were have has had their them they what who when
where how all one would will can if so no do does did been being than then
also such own yet upon i my me we us our you your she her him himself
itself myself nor nothing something everyone every each other another same
these those there here now still even more most much many few little good
bad true false right wrong man men mind soul nature reason god gods universe
life death time thing things world whole part parts within without because
since while until unless before after above below between among toward
through say says said think thinks thought do done doing give given gives
take taken takes come came comes go goes going make makes made keep keeps
kept let lets know knows known see sees seen find finds found live lives
lived act acts acted look looks looked call calls called work works worked
leave leaves left mean means meant seem seems seemed whether either neither
always never often sometimes soon once again therefore thus indeed perhaps
truly rather quite very too only just about across against along around
must may might could should would nature's pleasure pain sense senses
sensation sensations body bodies atom atoms void motion shape size
""".split())


def _looks_english(line: str) -> bool:
    words = re.findall(r"[A-Za-z']+", line)
    if len(words) < 2:
        return False
    hits = sum(1 for w in words if w.lower() in _ENGLISH_WORDS)
    return hits >= 2 or hits / len(words) >= 0.34


def _clean_or_none(line: str) -> str | None:
    """Structural-noise classification: Greek-script garble words are
    stripped (see `_strip_greek_tokens`) rather than condemning the whole
    line outright; the running-head/bare-marker checks then run on
    whatever's left. Returns None for a line that can never carry real
    translated prose (empty, all-Greek, a running head, page furniture);
    otherwise the cleaned text, still subject to `_accept_line`'s content
    bar in the caller."""
    if not line.strip():
        return None
    cleaned = _strip_greek_tokens(line) if _has_greek(line) else line.strip()
    if cleaned is None:
        return None
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if _is_heading_line(cleaned):
        return None
    if _is_bare_marker(cleaned):
        return None
    return cleaned


def _sentence_open(buf: list[str]) -> bool:
    """True if the last buffered fragment does NOT already end a
    sentence -- i.e. the entry is mid-sentence and genuinely expects a
    continuation, as opposed to having just closed cleanly."""
    if not buf:
        return False
    tail = buf[-1].rstrip()
    return bool(tail) and tail[-1] not in ".!?”\""


_SHORT_SENTENCE_CLOSE = re.compile(r"^[A-Za-z][A-Za-z' ]*[.!?]$")


def _looks_like_sentence_close(line: str) -> bool:
    """A short (1-3 word) line consisting of nothing but a terminal-
    punctuated close ("content.", "unlimited desire."). `_looks_english`
    alone routinely rejects these (too few words to clear its common-word
    ratio) -- this is a narrower, blunter shape test used only as a
    fallback, and only when the buffer is already open on a hanging
    sentence (see `_accept_line`), never a general substitute."""
    words = re.findall(r"[A-Za-z']+", line)
    if not (1 <= len(words) <= 3):
        return False
    return bool(_SHORT_SENTENCE_CLOSE.match(line.strip()))


def _hyphen_continues(buf: list[str], cleaned: str) -> bool:
    """True only when `cleaned` is the PLAUSIBLE completion of a word
    broken across an OCR line-wrap ("incom-" / "prehensible in
    number."), never a blanket "anything after a hyphen" pass: the flat
    OCR often places an apparatus-criticus block between a hyphenated
    line-wrap and its true continuation (Vatican Saying 27's own
    hyphenated "pain-" is followed, in physical page order, by an
    apparatus line before "fully after completion" ever arrives) --
    "Hartel . V" (an editor surname) is not a real completion and must
    not be swallowed just because the previous fragment happened to end
    in a hyphen. A genuine continuation always resumes the broken word
    in LOWER case (a hyphenated proper noun would be the rare
    exception, not attested here); an apparatus fragment beginning with
    a capitalized editor surname or numeral does not."""
    if not (buf and buf[-1].rstrip().endswith("-")):
        return False
    first_alpha = re.match(r"[A-Za-z]", cleaned.lstrip())
    return bool(first_alpha) and first_alpha.group(0).islower()


def _accept_line(cleaned: str, buf: list[str], entry_open: bool) -> bool:
    """Whether `cleaned` becomes body text for the currently open entry:
    the ordinary `_looks_english` bar, or -- only once an entry is
    already open, since neither fallback below is a fresh classification
    decision -- one of two narrow, evidence-driven exceptions
    `_looks_english` always fails on its own: (1) a plausible hyphen-break
    completion (see `_hyphen_continues`); (2) the previous fragment is
    itself mid-sentence and this line is a short terminal-punctuated
    close (see `_looks_like_sentence_close`)."""
    if _looks_english(cleaned):
        return True
    if not entry_open:
        return False
    if _hyphen_continues(buf, cleaned):
        return True
    if _sentence_open(buf) and _looks_like_sentence_close(cleaned):
        return True
    return False


# --- OCR line-wrap dehyphenation (same rule as extract_haines.py) -----------

_HYPHEN_WRAP = re.compile(r"([A-Za-z]+)-\s+([A-Za-z]+)")


def _build_vocab(texts: list[str]) -> set[str]:
    vocab: set[str] = set()
    for text in texts:
        for tok in text.split():
            if "-" in tok:
                continue
            word = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", tok)
            if len(word) >= 2 and word.isalpha():
                vocab.add(word.lower())
    return vocab


def _dehyphenate(text: str, vocab: set[str]) -> str:
    def repl(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        merged = left + right
        if right[:1].isupper():
            return f"{left}-{right}"
        if merged.lower() in vocab:
            return merged
        if left.lower() in vocab and right.lower() in vocab:
            return f"{left}-{right}"
        return merged
    return _HYPHEN_WRAP.sub(repl, text)


# A single OCR confusable -- the digit "1" standing in for a lowercase "i"
# -- recurs at volume across all three stores (56 occurrences confirmed by a
# full sweep, 2026-07-29 Grok verification gate) in exactly one shape: the
# glyph glued directly onto the three trailing letters of one of the four
# short English words that begin with "i" ("is", "in", "it", "if"), with no
# space of its own ("1s enticed", "1n itself", "1t is not", "1f we are").
# Handling this as 56 individual PATCHES entries would bury the one real
# defect (a single misread glyph) under volume; a general rule is the more
# honest fix, but only because this exact shape is safe to generalize:
# `\b1(s|n|t|f)\b` requires the digit to be its OWN token bounded by word
# edges on both sides, so it can never fire inside a genuine number --
# ordinals ("1st"), years ("1926"), section numerals ("108") and page
# numbers all have further digits or letters immediately after the "1"
# and so never reach a word boundary at that position. Confirmed against
# the regenerated stores: zero false positives, and no legitimate digit
# usage anywhere in the corpus takes this exact shape.
_DIGIT_LETTER_HOMOGLYPH = re.compile(r"\b1(s|n|t|f)\b")
_DIGIT_LETTER_HOMOGLYPH_FIX = {"s": "is", "n": "in", "t": "it", "f": "if"}


def _fix_digit_letter_homoglyphs(text: str) -> str:
    return _DIGIT_LETTER_HOMOGLYPH.sub(
        lambda m: _DIGIT_LETTER_HOMOGLYPH_FIX[m.group(1)], text)


# --- decimal anchors (the three Letters) -------------------------------------

# Unlike Haines' Meditations chapters, Bailey's DL section numbers are NOT
# printed at every Usener/von der Muehll break in the English translation --
# where several consecutive Greek sections fall inside one continuous
# English sentence/paragraph, Bailey's own edition prints no intervening
# number at all (confirmed: sections 37-42 of the Letter to Herodotus carry
# no digit token anywhere in the English OCR text, on any line, while the
# Greek page prints all six -- this is the source's own convention, not an
# OCR failure, so a wide jump tolerance is required to resync past a long
# run of genuinely-unmarked sections without losing the rest of the letter).
_MAX_JUMP = 20
_DECIMAL_ANCHOR = re.compile(r"^(\d{1,3})[.,]?\s+(\S.*)$")

# A run of genuinely-unmarked sections (see above) is honestly merged into
# the last section actually anchored -- but only up to a point. Past this
# many characters with no further anchor in sight, the OCR's numbering has
# broken down badly enough that attributing yet more text to the last KNOWN
# number would be actively misleading (observed: without this cap, a single
# stretch with no anchor from Herodotus section 57 onward absorbed the
# LAST 26 sections of the whole letter -- 22,000 characters -- under the
# key "57", which is far worse than an honest gap). Once the cap is hit,
# further lines are treated the same as an unrecoverable stretch: left out
# of the store entirely rather than glued onto a number they may not even
# belong to. The threshold is generous (comfortably above the largest
# legitimately-merged run actually observed, ~4,100 characters for a
# several-section merge in the Letter to Pythocles) so it never truncates
# an ordinary multi-section merge, only a runaway one.
_MAX_MERGE_CHARS = 6000

# A generous circuit breaker on ACCUMULATION only (never on the cap
# itself, which `_cut_at_sentence_boundary` now enforces exactly at flush
# time) -- keeps a genuinely pathological, still-unanchored run from
# growing without bound while the walk looks for its next real anchor.
_MAX_ACCUMULATE_CHARS = _MAX_MERGE_CHARS * 4

_SENTENCE_END = re.compile(r'[.!?][\'"’”)\]]*(?=\s|$)')


def _cut_at_sentence_boundary(text: str, limit: int) -> tuple[str, str]:
    """(kept, overflow): `kept` never exceeds `limit` characters and
    always ends at a genuine sentence boundary -- never mid-word or
    mid-clause. The old cap check ran BEFORE appending a line, so a merged
    entry could still end up past 6,000 characters, mid-sentence
    (letter-to-herodotus:57, letter-to-menoeceus:123); enforcing the cap
    by WHERE the cut falls, rather than by raw character count, fixes
    both at once. Whatever doesn't fit is never fabricated a boundary --
    it is returned as `overflow` for the caller to record honestly as
    unassigned text instead of silently keeping (or silently dropping)
    it."""
    if len(text) <= limit:
        return text, ""
    cut = 0
    for m in _SENTENCE_END.finditer(text):
        if m.end() > limit:
            break
        cut = m.end()
    if cut == 0:
        return "", text
    return text[:cut].strip(), text[cut:].strip()


def _match_decimal(line: str, current: int, hi: int) -> tuple[int | None, str | None]:
    """(new_current, content) opening the next section, or (None, None)."""
    m = _DECIMAL_ANCHOR.match(line)
    if not m:
        return None, None
    n = int(m.group(1))
    if n == current + 1:
        return n, m.group(2)
    if current + 1 < n <= min(current + _MAX_JUMP, hi):
        return n, m.group(2)
    return None, None


# Bailey's own printed section number for the Letter to Pythocles' section
# 108 sits literally INSIDE one word -- the page break that carries it falls
# between "fre-" (the hyphenated line-wrap opening "a process most fre-",
# ending section 107's own page) and "quent" (raw OCR lines 3993-4010:
# "...a process most fre-" / "108 quent in the atmosphere..."). Anchoring
# section 108 exactly where the walk finds its digit, as every other anchor
# is, would leave 107 ending mid-word and 108 opening mid-word -- so the
# section break is instead resolved to the nearest WORD edge: the
# completion fragment ("quent") joins the still-open previous section, and
# only what remains after it opens the new one. Gated narrowly (the
# previous fragment must already end in a hyphen, and the anchor's own
# content must open with a lowercase word-continuation) so this can only
# ever recover this exact shape of defect, never redraw an ordinary anchor.
def _resolve_anchor_mid_word(buf: list[str], content: str) -> tuple[str | None, str]:
    """(completion, remaining_content): if the previous fragment ends in a
    hyphen and `content` opens with a lowercase word-completion, that
    completion is returned to be appended to the PREVIOUS section's buffer
    and `remaining_content` is what the new section actually opens with.
    Otherwise (None, content) -- the anchor's own position is left alone."""
    if not (buf and buf[-1].rstrip().endswith("-")):
        return None, content
    parts = content.split(None, 1)
    if not parts or not (parts[0].isalpha() and parts[0].islower()):
        return None, content
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _extract_letter(
    lines: list[str], lo: int, hi: int
) -> tuple[dict[str, str], list[int], list[dict]]:
    out: dict[str, str] = {}
    skipped: list[int] = []
    unassigned: list[dict] = []
    current = lo - 1
    buf: list[str] = []

    def flush():
        nonlocal buf
        if current >= lo and buf:
            joined = " ".join(buf).strip()
            if joined:
                kept, overflow = _cut_at_sentence_boundary(joined, _MAX_MERGE_CHARS)
                if kept:
                    out[str(current)] = kept
                if overflow:
                    unassigned.append({"after_section": current, "text": overflow})
        buf = []

    for raw in lines:
        line = raw.strip()
        cleaned = _clean_or_none(line)
        if cleaned is None:
            continue
        if not _accept_line(cleaned, buf, current >= lo):
            continue
        line = cleaned
        n, content = _match_decimal(line, current, hi)
        if n is not None:
            completion, content = _resolve_anchor_mid_word(buf, content)
            if completion is not None:
                buf.append(completion)
            flush()
            if n > current + 1:
                skipped.extend(range(current + 1, n))
            current = n
            buf = [content] if content else []
            continue
        if current >= lo and sum(len(b) for b in buf) < _MAX_ACCUMULATE_CHARS:
            buf.append(line)
    flush()
    return out, skipped, unassigned


# --- roman-numeral anchors (Principal Doctrines, Vatican Collection) ---------

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50}
# A permissive parse (fuzzed confusables -> their likely roman letter, then
# read off directly) used only for the Vatican Collection cross-reference
# scan below, where the numeral is single-use evidence text, not a walk
# anchor -- a parse failure there just means that one cross-reference isn't
# recognised, not a false anchor, so strictness is less important here than
# in `_match_roman`.
# "A" is also attested standing in for a leading "X" that OCR fails to
# render distinctly (Vatican Sayings 18, 31, 34 all show it: "AVIII" for
# "XVIII", "AXXI" for "XXXI", "AXXIV" for "XXXIV" -- in every case the
# FIRST of a run of leading X's misreads as "A", never any other
# position). Gated the same way every other confusable is: acceptance
# still requires exact continuity in `_match_roman`, so widening which
# glyphs can SPELL a numeral never loosens the numeric check itself.
_ROMAN_FUZZ = {"H": "X", "T": "I", "E": "I", "F": "I", "1": "I", "U": "II", "A": "X"}


def _roman_to_int(raw: str) -> int | None:
    """A permissive read of `raw` as a roman numeral, tried two ways: first
    literally (after the fuzz substitutions above), and -- only if that
    reading does not round-trip back to its own canonical spelling, i.e.
    it wasn't a well-formed numeral to begin with -- with a trailing "L"
    reinterpreted as a misread "I" (attested: "IIL." for "III.", which
    literally parses as the well-formed-looking but WRONG value 48 unless
    this fallback fires). Returns None if neither reading is well-formed."""
    def parse(s: str) -> int | None:
        if not s or any(ch not in _ROMAN_VALUES for ch in s):
            return None
        total = prev = 0
        for ch in reversed(s):
            v = _ROMAN_VALUES[ch]
            total += -v if v < prev else v
            prev = max(prev, v)
        return total

    s = "".join(_ROMAN_FUZZ.get(ch, ch) for ch in raw.upper())
    n = parse(s)
    if n is not None and _int_to_roman(n) == s:
        return n
    if s.endswith("L") and len(s) > 1:
        alt = s[:-1] + "I"
        n_alt = parse(alt)
        if n_alt is not None and _int_to_roman(n_alt) == alt:
            return n_alt
    return n


# The dominant defect this OCR inflicts on a roman numeral is a dropped
# capital I (two adjacent I's misreading as one glyph, or as "f"/"l"/"1"):
# "If." for "II.", "IIL." for "III.", "HLIX." for "XLIX.", "VITE" for "VIII."
# The character class below is deliberately generous (numeral-shaped
# letters plus the specific confusables attested above) -- acceptance is
# still gated on continuity in `_match_roman`, so a widened class here only
# widens which glyphs can SPELL a numeral, never loosens the numeric check.
# A doctrine/saying opening a fresh printed page carries that page's own
# running page-number glued onto the SAME OCR line as the numeral that
# follows it ("141 VII. Some men wished...", "142 IX. If every pleasure...")
# -- an optional leading page-number run (plus a stray OCR dash/tilde/quote,
# e.g. "~ If. Death is nothing...") is tolerated ahead of the numeral itself.
# The token itself is captured widely (any run of the roman letters plus the
# OCR's attested confusable stand-ins for them -- U/H/T/E/F/B/S/1 -- rather
# than parsed strictly): this OCR's roman-numeral damage is too varied to
# enumerate as fixed substitutions (e.g. "XXVUI" for "XXVIII", "XXI1X" for
# "XXIX", "HLIX" for "XLIX") -- see `_match_roman`, which instead checks the
# token (after normalization) against the numeral the walk already EXPECTS
# next, trusting sequence position over a fragile character parse alone.
# The very first character must be from the strict upper-case numeral/
# confusable set (so an ordinary lower-case English word, e.g. "is the
# removal...", can never open a match); a doubled capital I inside the
# numeral is however attested dropping to lower case ("If." for "II."), so
# trailing characters also accept lower-case "f"/"l".
# A doubtful/spurious-attribution saying is printed by Bailey inside its
# own square brackets (Vatican Sayings 10, 30, 36) -- the OPENING bracket
# sits immediately before the numeral itself ("[X. Remember...", "[
# XXXVI. Epicurus’ life..."), which the noise-prefix class below did not
# tolerate, so the anchor line failed to match at all and its text bled
# into whichever entry was still open. Captured separately (group 1) so
# `_match_roman` can restore it onto the front of the saying's own text
# -- Bailey's brackets are editorially meaningful (they mark the saying's
# disputed authenticity) and are kept, never silently dropped, per the
# same brief that keeps the closing bracket (already just ordinary body
# text, needing no special handling) in place.
_ROMAN_TOKEN = re.compile(
    r"^(?:\d{1,4}\s+)?(\[)?[~\-–—'\"“”]{0,2}\s*\*?"
    r"([IVXLUHTEFBS1A][IVXLUHTEFBS1flA]{0,7})[.,\]]?\s+(\S.*)$"
)

# A rare compound saying printed under a single inline "N-M." anchor
# spanning two numbers at once (Vatican Collection 56-57, "LVI-LVII. The
# wise man is not more pained..." -- Bailey's own edition prints no
# separate 56 or 57; Arrighetti's numbering agrees there is no
# independent saying at either number). Tried before the ordinary single-
# anchor matcher; an inline range that doesn't exactly match the two
# positions the walk expects next simply falls through to it unchanged.
_ROMAN_RANGE_TOKEN = re.compile(
    r"^(?:\d{1,4}\s+)?[~\-–—'\"“”]{0,2}\s*\*?"
    r"([IVXLUHTEFBS1A][IVXLUHTEFBS1flA]{0,7})-([IVXLUHTEFBS1A][IVXLUHTEFBS1flA]{0,7})"
    r"[.,\]]?\s+(\S.*)$"
)


def _int_to_roman(n: int) -> str:
    out = []
    for value, sym in ((50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"),
                       (4, "IV"), (1, "I")):
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _normalize_roman(token: str) -> str:
    """Best-guess reading of `token` as a roman numeral: each attested
    confusable glyph (see `_ROMAN_FUZZ`) replaced by the letter it stands in
    for. Not a validated parse (the result may not even be a well-formed
    numeral) -- only ever used as a fuzzy-comparison input, never trusted on
    its own."""
    return "".join(_ROMAN_FUZZ.get(ch, ch) for ch in token.upper())


def _matches_with_one_doubled_letter_removed(normalized: str, expected: str) -> bool:
    """A second, separate attested defect: a doubled X or I glyph prints as
    THREE strokes instead of two ("XXXVI" for "XXVI", i.e. Principal
    Doctrine 26's own numeral gaining a spurious extra X). Recovering this
    by trying "delete any one character" would be unsafe at short lengths
    (see `_match_roman`'s docstring on the X/XI collision); gated here on
    the normalized token being at least 5 characters, comfortably longer
    than any single-digit-range numeral (X, XI, XII, ... all <=4 chars),
    so this repair path can never fire on the short numerals where a
    missing-neighbour collision is possible."""
    if len(normalized) < 5:
        return False
    for i, ch in enumerate(normalized):
        if ch in ("X", "I") and normalized[:i] + normalized[i + 1:] == expected:
            return True
    return False


def _matches_with_dropped_trailing_is(normalized: str, expected: str) -> bool:
    """A THIRD attested defect, distinct from both the doubled-letter-
    INSERTED case above and the ordinary single-merged-glyph case the
    trailing lower-case f/l tolerance in `_ROMAN_TOKEN` already recovers:
    here one or two trailing "I" strokes are dropped ENTIRELY, with no
    fuzz-mappable stand-in glyph left behind at all (Vatican Saying 43's
    own numeral "XLIII" misreads as "XLII"; Saying 48's own numeral
    "XLVIII" misreads as "XLVI", losing two strokes). Gated on the
    EXPECTED numeral being reconstructed EXACTLY by appending one or two
    literal "I"s to the damaged reading -- never a general edit-distance
    test -- so, like its sibling above, it can only ever recover this
    specific tail-collapse, not any other numeral discrepancy."""
    if normalized == expected:
        return False
    return any(normalized + "I" * dropped == expected for dropped in (1, 2))


def _match_roman(
    line: str, current: int, hi: int, known_skips: set[int]
) -> tuple[int | None, str | None, str | None]:
    """(new_current, content, correction_note) opening the next item, or
    (None, None, None). `known_skips` are item numbers already established
    (via `_scan_vs_crossrefs`) to have no independent English text; the
    walk's expectation jumps straight over them.

    Acceptance requires an EXACT match between the normalized token (see
    `_normalize_roman`) and the roman numeral for the target position --
    NOT a fuzzy/edit-distance "close enough" test. Adjacent roman numerals
    are often only one character apart ("X" vs "XI", "XI" vs "XII"), so a
    numeral one position further along the sequence would routinely pass
    any edit-distance-1 tolerance too: with a missing doctrine 10, its
    neighbour "XI." (doctrine 11) is edit-distance 1 from the EXPECTED "X"
    and would be silently misfiled as 10 -- cascading every doctrine after
    it off by one. Exact-after-normalization avoids that: it recovers
    genuine character-for-character OCR damage ("111" -> "III", "XXVUI" ->
    "XXVIII") without ever accepting a numerically different, merely
    similar-looking, neighbour."""
    m = _ROMAN_TOKEN.match(line)
    if not m:
        return None, None, None
    bracket, token, content = m.group(1), m.group(2), m.group(3)
    if bracket:
        content = "[" + content
    want = current + 1
    while want in known_skips and want <= hi:
        want += 1
    normalized = _normalize_roman(token)
    want_roman = _int_to_roman(want)
    if normalized == want_roman:
        note = None if token.upper() == normalized else \
            f"numeral {token!r} read as {normalized!r} (OCR damage)"
        return want, content, note
    if _matches_with_one_doubled_letter_removed(normalized, want_roman):
        note = f"numeral {token!r} read as {want_roman!r} (spurious doubled letter)"
        return want, content, note
    if _matches_with_dropped_trailing_is(normalized, want_roman):
        note = f"numeral {token!r} read as {want_roman!r} (dropped trailing stroke(s))"
        return want, content, note
    # Try each subsequent (non-skip) target within the jump ceiling, in case
    # the walk missed one or more markers entirely. An EXACT match anywhere
    # in the window is checked FIRST, across the whole window, before any
    # fuzzy repair is considered at all: a numeral that reads perfectly, with
    # no damage whatsoever, for some LATER position must never be shadowed by
    # an EARLIER position it merely happens to resemble once a repair
    # heuristic is applied (observed: Vatican Saying 58's own numeral
    # "LVIII." parses exactly as 58, but ALSO satisfies the doubled-letter-
    # removed repair for 57 -- the real defect was two unrecognised anchors
    # before it, not damage to this numeral; a first-hit-wins single pass
    # misfiled 58's text under 57).
    window = []
    n = want + 1
    while n <= hi and len(window) < _MAX_JUMP:
        if n not in known_skips:
            window.append(n)
        n += 1
    for n in window:
        if normalized == _int_to_roman(n):
            note = f"numeral {token!r} read as {_int_to_roman(n)!r} (OCR damage, forward jump over {n - want} unrecovered marker(s))"
            return n, content, note
    for n in window:
        n_roman = _int_to_roman(n)
        if _matches_with_one_doubled_letter_removed(normalized, n_roman):
            note = f"numeral {token!r} read as {n_roman!r} (OCR damage, forward jump over {n - want} unrecovered marker(s), spurious doubled letter)"
            return n, content, note
        if _matches_with_dropped_trailing_is(normalized, n_roman):
            note = f"numeral {token!r} read as {n_roman!r} (OCR damage, forward jump over {n - want} unrecovered marker(s), dropped trailing stroke(s))"
            return n, content, note
    return None, None, None


def _match_roman_range(
    line: str, current: int, hi: int, known_skips: set[int]
) -> tuple[int | None, int | None, str | None, str | None]:
    """(n1, n2, content, note) opening a compound saying under a single
    inline "N-M." anchor, or (None, None, None, None). See
    `_ROMAN_RANGE_TOKEN`. Requires an EXACT match for BOTH numbers against
    the two positions the walk already expects next -- no fuzzy repair,
    since this compound form is rare and narrowly evidenced; anything that
    isn't this exact pattern simply falls through to `_match_roman`
    unchanged."""
    m = _ROMAN_RANGE_TOKEN.match(line)
    if not m:
        return None, None, None, None
    tok1, tok2, content = m.group(1), m.group(2), m.group(3)
    want1 = current + 1
    while want1 in known_skips and want1 <= hi:
        want1 += 1
    want2 = want1 + 1
    while want2 in known_skips and want2 <= hi:
        want2 += 1
    if (_normalize_roman(tok1) == _int_to_roman(want1)
            and _normalize_roman(tok2) == _int_to_roman(want2)):
        return want1, want2, content, None
    return None, None, None, None


def _extract_roman(
    lines: list[str], hi: int, known_skips: set[int]
) -> tuple[dict[str, str], list[int], list[str], list[dict], list[dict]]:
    out: dict[str, str] = {}
    skipped: list[int] = []
    corrections: list[str] = []
    compounds: list[dict] = []
    unassigned: list[dict] = []
    current = 0
    buf: list[str] = []
    pending_key: str | None = None

    def flush():
        nonlocal buf
        if current >= 1 and buf:
            joined = " ".join(buf).strip()
            if joined:
                kept, overflow = _cut_at_sentence_boundary(joined, _MAX_MERGE_CHARS)
                key = pending_key if pending_key is not None else str(current)
                if kept:
                    out[key] = kept
                if overflow:
                    unassigned.append({"after_item": current, "text": overflow})
        buf = []

    for raw in lines:
        line = _fix_leading_greek_numeral(raw.strip())
        cleaned = _clean_or_none(line)
        if cleaned is None:
            continue
        if not _accept_line(cleaned, buf, current >= 1):
            continue
        line = cleaned

        n1, n2, content, note = _match_roman_range(line, current, hi, known_skips)
        if n1 is not None:
            flush()
            if n1 > current + 1:
                skipped.extend(c for c in range(current + 1, n1) if c not in known_skips)
            current = n2
            pending_key = f"{n1}-{n2}"
            compounds.append({"key": pending_key, "covers": [n1, n2]})
            buf = [content]
            if note:
                corrections.append(note)
            continue

        n, content, note = _match_roman(line, current, hi, known_skips)
        if n is not None:
            flush()
            if n > current + 1:
                skipped.extend(c for c in range(current + 1, n) if c not in known_skips)
            current = n
            pending_key = None
            buf = [content]
            if note:
                corrections.append(f"{n}: {note}")
            continue

        if current >= 1 and sum(len(b) for b in buf) < _MAX_ACCUMULATE_CHARS:
            buf.append(line)
    flush()
    return out, skipped, corrections, compounds, unassigned


# --- Vatican Collection cross-reference-only sayings -------------------------

# "Κύρι[αά]ι?" tolerates the vowel-ending OCR damage attested on this exact
# word ("Κύριαι" misread "Κύριαε") without loosening the much more
# distinctive "Δόξαι" that follows.
_VS_CROSSREF = re.compile(r"^\*?([IVXLUHTEFBS1]{1,8})[.,\]]?\s*=\s*Κύρι\S*\s*Δόξαι")

# Saying 72's own crossref line is damaged badly enough that Greek-script
# numeral lookalikes and the "two strokes merge into one glyph" defect
# (attested throughout this OCR, here rendered with a Greek diacritic
# instead of a bare Latin stand-in) land in the SAME token as ordinary
# confusables: "1ΧΧῚ]. = Κύριαι Δόξαι XIII" -- "1" standing for "L",
# Greek capital Chi twice for "X", and a single accented Greek capital
# iota for a MERGED doubled "I". Tried only as a fallback when the
# primary regex above doesn't match, so it can never change how any of
# the other confirmed crossrefs are read; without it, this crossref was
# never recognised, `known_skips` never contained 72, and the next real
# anchor ("LXXIII.", Saying 73's own numeral) got fuzzily misread as a
# damaged "LXXII" instead -- misfiling Saying 73's text under key "72"
# and leaving 73 an honest-looking but false gap.
# U+1FDA (GREEK CAPITAL LETTER IOTA WITH VARIA) is the specific accented
# glyph actually attested standing in for a merged doubled "I" here --
# named by codepoint, not typed literally, so no transcription/font
# ambiguity can silently break the match.
_MERGED_II_IOTA = "\u1fda"
_VS_CROSSREF_FALLBACK_FUZZ = {
    "\u0399": "I",  # Greek capital iota
    "\u03a7": "X",  # Greek capital chi
    "\u03a5": "U",  # Greek capital upsilon
    "1": "L",
    _MERGED_II_IOTA: "II",
}
_VS_CROSSREF_FALLBACK = re.compile(
    "^\\*?([IVXLUHTEFBS1\u0399\u03a7\u03a5" + _MERGED_II_IOTA + "]{1,8})"
    r"[.,\]]{0,2}\s*=\s*\u039a\u03cd\u03c1\u03b9\S*\s*\u0394\u03cc\u03be\u03b1\u03b9"
)


def _scan_vs_crossrefs(raw_lines: list[str]) -> dict[int, str]:
    """A separate pass over the RAW (pre Greek-filter) lines: a Vatican
    Collection saying that is nothing but a cross-reference to a Principal
    Doctrine is itself a Greek-script line and vanishes under `_has_greek`
    with everything else -- which would silently turn a genuine "no
    independent English here" fact into an ordinary, unremarked gap. Returns
    {item number: raw OCR line} evidence for every such cross-reference
    found."""
    found: dict[int, str] = {}
    for raw in raw_lines:
        line = raw.strip()
        m = _VS_CROSSREF.match(line)
        if m:
            n = _roman_to_int(m.group(1))
            if n is not None:
                found[n] = line
            continue
        m = _VS_CROSSREF_FALLBACK.match(line)
        if m:
            mapped = "".join(_VS_CROSSREF_FALLBACK_FUZZ.get(ch, ch) for ch in m.group(1))
            n = _roman_to_int(mapped)
            if n is not None:
                found[n] = line
    return found


# --- part boundaries ----------------------------------------------------------

_HERODOTUS_START = re.compile(r"EPICURUS TO HERODOTUS")
_PYTHOCLES_START = re.compile(r"EPICURUS TO PYTHOCLES")
_MENOECEUS_START = re.compile(r"EPICURUS TO MENOECEUS")
_KD_START = re.compile(r"^PRINCIPAL DOCTRINES\s*$")
_VS_START = re.compile(r"VATICAN COLLECTION")
_VS_END = re.compile(r"CERTORUM LIBRORUM")


def _slice(lines: list[str], start_pat: re.Pattern, end_pat: re.Pattern,
           after: int = 0) -> list[str]:
    start = end = None
    for i, raw in enumerate(lines):
        if i < after:
            continue
        if start is None and start_pat.search(raw):
            start = i + 1
            continue
        if start is not None and end_pat.search(raw):
            end = i
            break
    if start is None:
        raise SystemExit(f"start pattern not found: {start_pat.pattern!r}")
    return lines[start:end if end is not None else len(lines)]


LETTER_SPECS = {
    "letter-to-herodotus": (_HERODOTUS_START, _PYTHOCLES_START, 35, 83),
    "letter-to-pythocles": (_PYTHOCLES_START, _MENOECEUS_START, 84, 116),
    "letter-to-menoeceus": (_MENOECEUS_START, _KD_START, 122, 135),
}


# --- hand-verified patches (same contract as extract_haines.py) -------------

def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_patches(stores: dict[str, dict[str, str]], patches: list[dict]) -> None:
    for p in patches:
        store, key = p["store"], p["key"]
        if store not in stores or key not in stores[store]:
            raise ValueError(f"PATCHES.json: {store}:{key} not found in extraction output")
        text = stores[store][key]
        for old in p.get("remove", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: {store}:{key} 'remove' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, "")
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: {store}:{key} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        stores[store][key] = text.strip()


def _compute_gaps(
    lo: int, hi: int, out: dict[str, str],
    compound_covers: set[int] = frozenset(), exclude: set[int] = frozenset(),
) -> list[int]:
    """Every expected number in [lo, hi] with no text of its own -- whether
    or not the walk's own jump-detection ever recorded a skip for it.
    Relying solely on that internal `skipped` list silently missed a
    TRAILING run after the last anchor the walk ever found (it only
    records a skip when a LATER anchor resumes and reveals the gap by
    jumping over it -- a stretch that never resumes leaves no such
    record): Herodotus 58-83, Pythocles 115-116, and Menoeceus 124-135
    all vanished from `gaps` this way even though none of them were ever
    extracted. `compound_covers` (numbers folded into a compound saying's
    own key, e.g. Vatican 56 and 57 under "56-57") and `exclude`
    (cross-reference-only sayings, which are not gaps at all) are not
    gaps either."""
    covered = {int(k) for k in out if k.isdigit()}
    covered |= set(compound_covers)
    return sorted(n for n in range(lo, hi + 1) if n not in covered and n not in exclude)


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                     encoding="utf-8")


def main() -> None:
    _verify_source()
    text = SRC.read_text(encoding="utf-8")
    raw_lines = text.split("\n")

    # -- Letters --
    letters: dict[str, str] = {}
    letters_meta: dict[str, dict] = {}
    for slug, (start_pat, end_pat, lo, hi) in LETTER_SPECS.items():
        section = _slice(raw_lines, start_pat, end_pat)
        out, skipped, unassigned = _extract_letter(section, lo, hi)
        expected = hi - lo + 1
        for n, txt in out.items():
            letters[f"{slug}:{n}"] = txt
        letters_meta[slug] = {
            "expected_range": [lo, hi],
            "expected_count": expected,
            "extracted_count": len(out),
            "gaps": [
                {"section": n, "reason": "OCR marker not found or too corrupted to recover"}
                for n in _compute_gaps(lo, hi, out)
            ],
            "unassigned": unassigned,
        }

    # -- Principal Doctrines (I-XL, no known cross-reference-only items) --
    kd_section = _slice(raw_lines, _KD_START, _VS_START)
    kd, kd_skipped, kd_corrections, kd_compounds, kd_unassigned = _extract_roman(
        kd_section, 40, set())
    kd_meta = {
        "expected_range": [1, 40],
        "expected_count": 40,
        "extracted_count": len(kd),
        "gaps": [
            {"doctrine": n, "reason": "OCR marker not found or too corrupted to recover"}
            for n in _compute_gaps(1, 40, kd)
        ],
        "numeral_corrections": kd_corrections,
        "unassigned": kd_unassigned,
    }

    # -- Vatican Collection (I-LXXXI, with cross-reference-only skips) --
    vs_section = _slice(raw_lines, _VS_START, _VS_END)
    # The cross-reference scan itself must look WIDER than `vs_section`: the
    # Greek-script heading ("SENTENTIAE VATICANAE") that opens this part
    # sits on a Greek (verso) page, physically BEFORE the English (recto)
    # "VATICAN COLLECTION" heading `_VS_START` anchors on -- and Bailey's
    # English column skips a cross-reference-only saying's number entirely
    # (no "I. = ..." line of its own on the English side), so the earliest
    # cross-references (sayings 1, 2, 3, 5, 6, 8, 13) live only in that
    # Greek lead-in, before `vs_section` even begins. Scanning from the
    # Principal Doctrines onward (still bounded by `_VS_END`) catches those
    # too without risking a false hit -- nothing in the Principal Doctrines
    # themselves matches "<numeral> = Κύριαι Δόξαι <numeral>".
    vs_crossref_scan = _slice(raw_lines, _KD_START, _VS_END)
    vs_crossrefs = _scan_vs_crossrefs(vs_crossref_scan)
    vs, vs_gaps, vs_corrections, vs_compounds, vs_unassigned = _extract_roman(
        vs_section, 81, set(vs_crossrefs))
    vs_compound_covers = {n for c in vs_compounds for n in c["covers"]}
    vs_meta = {
        "expected_range": [1, 81],
        "expected_count": 81,
        "extracted_count": len(vs),
        "cross_reference_only": [
            {"saying": n, "evidence": line}
            for n, line in sorted(vs_crossrefs.items())
        ],
        "compound_sayings": vs_compounds,
        "gaps": [
            {"saying": n, "reason": "OCR marker not found or too corrupted to recover"}
            for n in _compute_gaps(1, 81, vs, vs_compound_covers, set(vs_crossrefs))
        ],
        "numeral_corrections": vs_corrections,
        "unassigned": vs_unassigned,
    }

    # -- dehyphenate (corpus-wide vocab across all three stores) --
    vocab = _build_vocab(list(letters.values()) + list(kd.values()) + list(vs.values()))
    letters = {k: _dehyphenate(v, vocab) for k, v in letters.items()}
    kd = {k: _dehyphenate(v, vocab) for k, v in kd.items()}
    vs = {k: _dehyphenate(v, vocab) for k, v in vs.items()}

    # -- digit/letter homoglyph repair (corpus-wide, see _fix_digit_letter_homoglyphs) --
    letters = {k: _fix_digit_letter_homoglyphs(v) for k, v in letters.items()}
    kd = {k: _fix_digit_letter_homoglyphs(v) for k, v in kd.items()}
    vs = {k: _fix_digit_letter_homoglyphs(v) for k, v in vs.items()}

    stores = {"letters": letters, "kd": kd, "vs": vs}
    patches = _load_patches()
    _apply_patches(stores, patches)

    _write(OUT_LETTERS, stores["letters"])
    _write(OUT_KD, stores["kd"])
    _write(OUT_VS, stores["vs"])
    _write(OUT_META, {
        "witness": _WITNESS_URL,
        "source_file": "bailey-extant-remains-1926.djvu.txt",
        "source_sha256": _EXPECTED_SHA256,
        "generation": {
            "tool": "pipeline/tools/extract_bailey_epicurus.py",
            "method": "Greek-Unicode line filter + all-caps running-head filter "
                      "+ decimal/roman section-number anchor walk; deterministic "
                      "from the vendored OCR text alone.",
        },
        "known_limitations": [
            "Bailey's printed page carries a narrow marginal synopsis column "
            "(short topic labels) beside the main translation; the flat OCR "
            "interleaves fragments of that column into the same line as the "
            "main prose, mid-sentence, with no reliable per-line signal to "
            "separate them. This script does not attempt to strip them: a "
            "sparse residue of marginal-gloss word fragments may appear "
            "inline in the extracted text. Not fixed by patches (too diffuse "
            "to enumerate); disclosed here rather than silently left unclean.",
        ],
        "letters": letters_meta,
        "kd": kd_meta,
        "vs": vs_meta,
        "patches_applied": len(patches),
    })

    print(f"letters: {len(letters)} sections -> {OUT_LETTERS}")
    print(f"kd: {len(kd)}/40 doctrines -> {OUT_KD}")
    print(f"vs: {len(vs)}/81 sayings ({len(vs_crossrefs)} cross-reference-only) -> {OUT_VS}")
    print(f"wrote {OUT_META}")


if __name__ == "__main__":
    main()
