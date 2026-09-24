"""One-off: extract C. R. Haines' 1916 Loeb Meditations translation from the
raw archive.org OCR text (sources/haines-meditations/thecommuningswit00marcuoft_djvu.txt
— see sources/INVENTORY.md) into a clean {book}.{chapter}: text JSON map,
keyed exactly like the Greek book-section spine's dotted column tokens.

This is a bilingual facing-page Loeb edition: the OCR text interleaves
English-page and Greek-page content in physical page-scan order, and the
Greek-page OCR is garbage (the engine transliterated Greek into nonsense
Latin-alphabet strings — INVENTORY.md's line-level estimate: ~36% of raw
lines). The extraction is driven by the ONE positional signal that does
survive the flat OCR — the running head at the top of every printed page:

* PAGE SIDE (see `_BOOK_HEAD` / `_GREEK_HEAD`). Every English recto page is
  headed "BOOK <n>"; every Greek verso page is headed "MARCUS AURELIUS", and a
  book-opening Greek page "BIBAION <numeral>". `extract` tracks which side the
  running head last put it on and captures prose ONLY on English pages —
  Greek-page noise is skipped wholesale, not filtered per line. A chapter cut
  by a Greek page resumes into the SAME buffer when the next "BOOK <n>" head
  reopens the English side (this recovers continuations the earlier per-line
  English-ness filter used to truncate, e.g. 2.14, 10.17, 12.36).

* CHAPTER MARKERS (see `_match_chapter`). A section opens with an Arabic
  numeral + period ("23. ..."); acceptance requires numeric continuity
  (next == current + 1). A marker whose digit reads current+1 but whose
  content is too OCR-mangled to open a sentence ("34. 4 man..." for "A man")
  is treated as a boundary that FLUSHES the previous chapter and logs an
  unrecovered gap, rather than letting the corrupt text bleed forward.

* FOOTNOTE ZONE. On an English page a chapter's body is bounded below by the
  page's footnotes, found structurally: a "N "/symbol trigger, a bare
  page-number, a spaced ellipsis, or a wide-gap/overflow rule (see `_ELLIPSIS`
  and the trim logic in `extract`). The one layout that resists every
  structural rule — a footnote spliced into the body across a page break on a
  double-spaced page — is caught by `_APPARATUS`, a classical-citation content
  signal verified to fire on zero clean chapters.

Output is post-processed for OCR line-wrap hyphens (`_dehyphenate`) and margin
marks (`_MARGIN_MARK`). Verified at content level against the Greek: no chapter
carries a running head, Greek transliteration, or footnote apparatus, and the
English/Greek length-ratio distribution has no unexplained outliers (stage2's
length_ratio gate enforces this on rebuild).

Known coverage gaps (see manifests/meditations.yaml, sources/INVENTORY.md):
5.37 (both translations merge it into 5.36) and 11.31/11.34/12.15 (Haines
markers OCR-corrupted beyond recovery; Long covers all three).

A corpus-wide, deterministic rule (`_strip_comma_footnote_marks`, run right
after dehyphenation) collapses the ",!"/",?" footnote-superscript OCR
signature (a reference mark glued straight onto its comma with no space) back
to a plain comma -- see that function's docstring for the cross-scan evidence
that this is always OCR noise, never real punctuation.

A handful of residual per-chapter splices (a stray footnote/apparatus
fragment, small-caps proper-name garble, or in one case page-bottom OCR
noise, that no general heuristic above catches without risking regressions
elsewhere) are closed by hand-verified surgical corrections in
`PATCHES.json` (see `_apply_patches`, applied last, after the comma-mark
rule) rather than by further extraction rules -- see sources/INVENTORY.md's
patch-policy note for the count and rationale.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SRC = Path("../sources/haines-meditations/thecommuningswit00marcuoft_djvu.txt")
OUT = Path("../sources/haines-meditations/haines.clean.json")
PATCHES = Path("../sources/haines-meditations/PATCHES.json")

# The English pages of this Loeb carry the book name ("BOOK II") as their
# running head; the facing Greek verso pages carry "MARCUS AURELIUS" instead.
# That pairing is the one reliable page-side signal left in the flat OCR, and
# it is what `extract` uses to know which physical page a line sits on (see the
# module docstring). Both heads pick up occasional leading OCR margin noise
# ("/ BOOK II", "' BOOK IV", "“MARCUS AURELIUS"), so both patterns tolerate a
# short run of leading non-letters; `_GREEK_HEAD` additionally forbids any
# OTHER letters on the line so a body sentence merely mentioning the emperor
# can never be mistaken for a page head.
_BOOK_HEAD = re.compile(r"^[^A-Za-z0-9]{0,3}\s*BOOK\s+([IVXLil][IVXLil.\- ]*)$")
# A Greek verso page's running head is "MARCUS AURELIUS"; the Greek page that
# OPENS a book instead carries the Greek book title "BIBAION <numeral>"
# (ΒΙΒΛΙΟΝ, the Λ mis-OCR'd to A) — without matching that too, the whole
# book-opening Greek page leaks into the previous book's last chapter. `BIBA[IO]+N`
# matches "BIBAION"/"BIBAON" but never "BIBLIOGRAPHY".
_GREEK_HEAD = re.compile(r"^[^A-Za-z]*(?:MARCUS\s+AURELIUS|BIBA[IO]+N\b).*$")
# A leading margin-mark ("_", "|", "§", "*", ...) and a comma-for-period are
# both attested OCR artifacts on an otherwise-genuine marker (e.g. "_ 4, From
# my GranpraTuer's..." for "4. From my Grandfather's...", "| 6. How many...");
# the numeric-continuity check at the call site is what actually guards
# against a false match (a coincidentally digit-shaped Greek-page OCR
# fragment), not the leading punctuation.
_SECTION_HEAD = re.compile(r"^[^0-9A-Za-z]{0,2}\s*(\d{1,2})[.,][^0-9A-Za-z]{0,2}\s*(\S.*)$")
# Fallback for a marker whose digit(s) themselves got OCR'd as a lookalike
# letter (seen: "I3." for "13." — 1 -> I). Tried only when the strict digit
# match above fails to find a numeral equal to chapter + 1; the character
# class is deliberately small (well-attested digit/letter OCR confusions
# only) and the caller still requires an EXACT chapter + 1 match, so this
# never loosens acceptance — it only widens which glyphs can spell a digit.
# The terminal-punctuation gap (between "[.,]" and the content) allows a
# short run of non-alnum filler too — an OCR'd footnote-reference glyph is
# sometimes fused straight onto the period with no space ("61.*Enter...").
_SECTION_HEAD_FUZZY = re.compile(r"^[^0-9A-Za-z]{0,2}\s*([0-9IOSBGZlosbgz]{1,2})[.,][^0-9A-Za-z]{0,2}\s*(\S.*)$")
_FUZZY_DIGIT = {"I": "1", "l": "1", "O": "0", "o": "0", "S": "5", "s": "5",
                "B": "8", "b": "6", "G": "6", "g": "9", "Z": "2", "z": "2"}


def _defuzz(numeral: str) -> str:
    return "".join(_FUZZY_DIGIT.get(ch, ch) for ch in numeral)
# A footnote/apparatus line opens with its reference mark then a space: a digit,
# or one of the OCR's superscript-symbol stand-ins. Besides the typographic
# marks (* ® § † ‡ °), the scan also renders footnote bullets as "#", ">" and
# "»" (e.g. the three notes under 7.49, the apparatus line the corrupt 11.31
# marker degraded into) — all likewise never open a line of Marcus' body prose.
_FOOTNOTE_TRIGGER = re.compile(r"^(?:\d{1,3}|[*®§†‡#>»°])\s+\S")
_STOP_MARKER = "THE SPEECHES OF MARCUS"

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50}


def _roman_to_int(raw: str) -> int | None:
    """Best-effort Roman numeral value, tolerant of the OCR's I/l confusion
    on II/III ("Il" -> II, "Ill" -> III, "Vil" -> VII, "XIl" -> XII): the OCR
    reliably confuses lowercase l for uppercase I, so normalise l -> I before
    parsing. Returns None for anything that isn't a clean I/V/X/L run."""
    s = raw.strip().rstrip(". -").upper().replace("L", "I")
    if not s or any(ch not in _ROMAN_VALUES for ch in s):
        return None
    total = prev = 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


# A generous common-English-word set: function words + the register this
# translation's prose actually uses. Not a dictionary — a discriminator
# against OCR'd-Greek noise, which rarely produces real hits even by chance
# (Greek word shapes don't line up with English function words).
_ENGLISH_WORDS = set("""
the of and to in a is that it as for with not but he his this which be are
from at by on or an was were have has had their them they what who when
where how all one would will can if so no do does did been being than then
also such own yet upon i my me we us our you your she her him himself
itself myself thyself thou thee thy shalt art dost doth hath nor
nothing something everything anyone every each other another same these
those there here now still yet even more most much many few little
good bad true false right wrong good evil man men mind soul nature reason
god gods universe life death time thing things world according according
whole part parts within without because since while until unless before
after above below between among according toward towards through
according man's men's thy own thou hast shall must ought may might could
should would say says said think thinks thought thoughts do done doing
give given gives take taken takes come came comes go goes going make makes
made keep keeps kept let lets know knows known see sees seen find finds
found live lives lived act acts acted look looks looked call calls called
work works worked leave leaves left mean means meant seem seems seemed
whether either neither always never often sometimes soon once again
therefore thus indeed perhaps truly rather quite very too only just
about above across after against along among around
""".split())


def _looks_english(line: str) -> bool:
    words = re.findall(r"[A-Za-z']+", line)
    if len(words) < 2:
        return False
    hits = sum(1 for w in words if w.lower() in _ENGLISH_WORDS)
    return hits >= 2 or hits / len(words) >= 0.34


# A leading quote mark, or a stray OCR'd footnote-reference digit run (e.g.
# "34. 4 man while fondly kissing..." — the marker "34." is itself genuine,
# but a footnote superscript got OCR'd as a bare "4 " glued onto the start of
# its own content) both precede real prose harmlessly and are skipped before
# judging whether the content opens a capitalized sentence.
_LEAD_NOISE = re.compile(r"^(?:[\'\"‘’“”]|\d{1,2}\s+)+")


def _opens_sentence(content: str) -> bool:
    """True if `content` (the text right after a candidate marker's
    punctuation) starts, after any leading quote/footnote-digit noise, with a
    capital letter — every genuine chapter opening in this translation is a
    full capitalized sentence. Rejects the false positives a bare digit/
    footnote fragment produces (e.g. a footnote's own "7.e. conditionally..."
    cross-reference, whose content opens lowercase) without needing to tell a
    footnote's English prose apart from a chapter's by word content alone —
    both are equally "English"."""
    s = _LEAD_NOISE.sub("", content)
    for ch in s:
        if ch.isalpha():
            return ch.isupper()
        if ch.isdigit():
            return False
    return False


# Footnote-reference marks glued onto the end of the word they annotate, no
# space in front (a real footnote never opens a fresh word) — plain digits,
# OCR'd superscript digits, and the handful of symbol glyphs seen standing in
# for a superscript mark ("him.°", "Rusticus,3"). The lookbehind keeps this
# from ever touching a digit/symbol that starts its own token.
_STRIP_MARKS = re.compile(r"(?<=[A-Za-z.,;:!?'’])[0-9§®°*†‡¹²³⁴⁵⁶⁷⁸⁹]{1,3}(?=\s|$)")


# OCR margin/gutter artefacts ("|", "{", "}", "_") that the scan drops into the
# running prose (e.g. "{ | the one he is now living", "fall upon | the same
# altar", "says the _ Sage", a stray "_" splitting a line-wrap "Philo- _sophy");
# never legitimate characters in this English text, so removed and the resulting
# double space collapsed (which also lets the later dehyphenation re-join the
# wrap the "_" had blocked).
_MARGIN_MARK = re.compile(r"\s*[|{}_]+\s*")


def _clean_prose(line: str) -> str:
    # Strip stray OCR'd superscript footnote-reference marks that land inside
    # the running prose (e.g. "Verus,!" -> "Verus,"), not the real word text,
    # and drop OCR margin marks.
    line = _STRIP_MARKS.sub("", line)
    line = _MARGIN_MARK.sub(" ", line)
    return line.strip()


# A backstop against facing-Greek-page transliteration noise leaking into an
# English chapter when a "MARCUS AURELIUS" head is itself too OCR-mangled to be
# recognised (so `extract`'s page-side tracking wrongly still believes it is on
# an English page). The engine transliterated Greek into Latin-alphabet
# nonsense that keeps the Greek word's internal capitals ("aTroKeKopmpevny",
# "TovTOD", "KaTa"); genuine English prose almost never has a lower-then-upper
# transition inside a word. Two such tokens (or any surviving Greek-script
# character) marks the line as Greek-page noise.
_INTERNAL_CAP = re.compile(r"[a-z][A-Z]")


def _looks_greek(line: str) -> bool:
    if any("Ͱ" <= c <= "Ͽ" or "ἀ" <= c <= "῿" for c in line):
        return True
    tokens = re.findall(r"[A-Za-z]+", line)
    return sum(1 for t in tokens if _INTERNAL_CAP.search(t)) >= 2


# The footnote zone sits at the bottom of an English page. Its start is found
# structurally rather than by whitespace (the scan's line spacing is not
# uniform — some pages are single-spaced, some double-spaced, so a blank-line
# count cannot tell a chapter break from a body/footnote break). Anchors:
#   * a "N " / symbol footnote trigger,
#   * a bare page-number line (the page's very bottom),
#   * a spaced ellipsis (". . .") — only ever quoted footnote/apparatus
#     material in this edition, never Marcus' body prose (verified whole-scan),
#     so it flags a footnote that abuts the body with no blank at all (e.g. the
#     Casaubon gloss under 9.13).
# A footnote that has OVERFLOWED from a previous page prints ABOVE the trigger
# with no digit of its own; it is recovered by the overflow trim in `extract`
# (a block captured since the last blank that runs straight into a trigger is
# footnote, not body).
_ELLIPSIS = re.compile(r"\.\s\.\s\.")
_PAGE_NUMBER = re.compile(r"^\d{1,4}$")
# A last-resort content signal for a footnote spliced into the body across a
# page break on a DOUBLE-spaced page — the one layout the blank-gap rules above
# cannot separate (footnote and body wraps are both 2-blank set off, and the
# body resumes on the next page). Marcus' body prose never carries a
# classical-citation reference ("Apol. ii. 8", "Cass. viii. 5", "§ 2"): an
# abbreviation + roman-numeral + number, or a section-sign + number. Verified to
# fire on ZERO of the clean chapters, only on apparatus, so it is safe to treat
# a matching line as a footnote trigger. (A bare trailing "§" reference mark
# without a number is NOT matched — that is stripped as OCR furniture, not a
# citation.)
#
# Three more apparatus shapes join the citation-locator one above (all
# likewise verified to fire on zero clean chapters — see extract_haines
# defect audit): Gataker/Casaubon/Lofft are this Loeb's own editorial
# apparatus, and "the Scholiast" is how it cites an ancient commentator —
# Marcus' own prose never names a translator/editor; "cp." ("compare") is
# this edition's stock cross-reference abbreviation, never Marcus' or
# Haines' own diction; and bare third-person "Marcus" is the editor's-voice
# tell — the book IS Marcus addressing himself in the first/second person,
# so he never names himself. Together these catch a footnote whose overflow
# text (from a page-spanning note, or one glued straight onto the body with
# no blank at all) carries no classical-citation locator of its own.
_APPARATUS = re.compile(
    r"\b[A-Z][a-z]{1,7}\.\s+[ivxlc]{1,6}\.\s*\d|§\s*\d"
    r"|\b(?:Gataker|Casaubon|Lofft|Scholiast)\b"
    r"|\bcp\.\s"
    r"|\bMarcus\b"
)
# End-of-sentence punctuation, used to tell a page's line-spacing regime apart
# (see `extract`): a 2+ blank gap after a line that ENDS a sentence is a
# body/footnote break on a single-spaced page; the same gap after a line that
# breaks mid-sentence is just a wrap on a double-spaced page.
_SENTENCE_FINAL = tuple(".!?\"')”’")


# --- OCR line-wrap dehyphenation ---------------------------------------------
# The scan breaks a word across a line with a trailing hyphen ("dis-\nposition"),
# which the line join renders as "dis- position". These must be re-joined, but a
# genuine hyphenated compound ("World-City", "self-control") must keep its
# hyphen. Rule, applied to every "LEFT- RIGHT" (hyphen glued to LEFT, then a
# space, then RIGHT), both alphabetic:
#   1. RIGHT capitalised            -> keep hyphen  ("World- City" -> "World-City")
#   2. LEFT+RIGHT is a real word    -> dehyphenate  ("dis- position" -> "disposition",
#      (attested elsewhere unhyphenated  "with- out" -> "without", "know- ledge"
#       in this same corpus)             -> "knowledge")
#   3. LEFT and RIGHT both real words -> keep hyphen (a true compound whose
#      but LEFT+RIGHT is not         joined form is not itself a word:
#                                     "self- control" -> "self-control")
#   4. otherwise                    -> dehyphenate  (a bare word fragment)
# The "real word" test is the corpus's own vocabulary (tokens seen standalone,
# unhyphenated), so the rule is deterministic from the input alone — no external
# dictionary — and self-tunes to Haines' register and spelling.
_HYPHEN_WRAP = re.compile(r"([A-Za-z]+)-\s+([A-Za-z]+)")


def _build_vocab(chapters: dict[str, str]) -> set[str]:
    # Only whitespace tokens with no hyphen count: a still-hyphenated wrap
    # ("tyrann-ical") must NOT seed its own fragments ("tyrann", "ical") into
    # the vocabulary, or the real-word tests below would wrongly judge the
    # fragment a word and keep the very hyphen we mean to remove.
    vocab: set[str] = set()
    for text in chapters.values():
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


# `_STRIP_MARKS` only catches a footnote-reference mark GLUED onto the word it
# annotates (no space). The scan sometimes prints the same mark as its own
# detached token, a lone symbol or 1-2 digit number surrounded by whitespace
# ("amiss ? §", "thy share ? 4"); at the very end of a chapter this is pure OCR
# furniture (there is no next word for it to attach to) and safe to strip
# outright. Deliberately narrow: only the known superscript-stand-in symbols
# and bare digits — NOT "!" or "?", which are genuine terminal punctuation
# throughout this text (Marcus' own exclamations: "what a world of slavery !",
# with the OCR's usual stray space before punctuation) and must never be eaten.
_TRAILING_MARK = re.compile(r"\s+(?:[°§¡®†‡*]|[0-9]{1,2})$")

# A dangling, unmatched close-paren at the very end of a chapter (e.g. 4.21's
# "...from the Causal.” us)") is OCR noise from the footnote-zone trigger
# that follows — real prose never ends on an unbalanced ")". Gated on the
# whole chapter having no matching "(" at all, so a genuine parenthetical
# close is never touched.
_DANGLING_CLOSE_PAREN = re.compile(r"\s+[a-z]{1,6}\)$")

# The footnote-reference full stop that should have been glued to the body's
# own closing punctuation (as `_STRIP_MARKS` handles for a digit/symbol mark)
# instead survives as its own detached "." token when the OCR splits it onto
# a stray trailing space — leaving a doubled terminal stop ("...his lot. .").
# Collapses to the genuine sentence-final punctuation already present.
_DOUBLED_STOP = re.compile(r"([.!?])\s+\.$")


def _strip_trailing_mark(text: str) -> str:
    while True:
        stripped = _TRAILING_MARK.sub("", text)
        if stripped == text:
            break
        text = stripped
    if text.count("(") < text.count(")"):
        text = _DANGLING_CLOSE_PAREN.sub("", text).rstrip()
    text = _DOUBLED_STOP.sub(r"\1", text)
    return text


# A footnote superscript OCR'd as "!" or "?" glued straight onto the comma it
# follows, with no space ("Verus,!", "Nature,?") -- a comma is mid-clause
# punctuation, never followed by real terminal punctuation, so a "," then
# immediately "!"/"?" is never genuine English (confirmed corpus-wide: 90
# sites, none of which read as a real exclamation/question at the comma).
# Cross-checked against two independent digitizations of the same 1916
# edition (communingswithhi00marc, communingswithh00haingoog -- see
# sources/INVENTORY.md): the SAME site renders as a different footnote-mark
# glyph in each scan (",^", ",'", a raised digit) rather than a real "!"/"?",
# confirming the mark is OCR noise, not print. Deliberately narrow to the
# exact ",[!?]" adjacency -- a real "!"/"?" preceded by anything other than
# "," (e.g. "what a world of slavery !") is untouched, and other glued marks
# (a curly quote, ">", "°", etc.) are not this pattern and are left to
# PATCHES.json.
_COMMA_FOOTNOTE_MARK = re.compile(r",[!?]")


def _strip_comma_footnote_marks(text: str) -> str:
    return _COMMA_FOOTNOTE_MARK.sub(",", text)


# A single marker occasionally survives OCR too corrupted for even the fuzzy
# digit-lookalike/dropped-leading-"1" recovery to recognise (e.g. "» Fes ans
# 3 and nithin me..." for what should open with "31."), which would strand
# the strict cur+1 walk forever on the rest of the book if nothing more were
# done — every later, perfectly legible marker would keep failing the "== cur
# + 1" test too, having no way to know "31" was ever skipped. A bounded
# forward-jump recovery breaks that: if the very next chapter's marker is
# unrecoverable but the one after resolves cleanly, accept it and record the
# skip rather than losing the rest of the book. Small ceiling (a Meditations
# book's chapters run to 75; a >5 jump is far more likely a coincidental
# digit-shaped fragment than five consecutive unrecoverable markers).
_MAX_JUMP = 5


def _match_chapter(line: str, chapter: int) -> tuple[re.Match | None, int | None]:
    """(match, new_chapter) opening the next chapter, or (None, None).

    Tiered by confidence/specificity, most permissive last:
      1. strict Arabic digits, == chapter + 1 (the overwhelming common case).
      2. digit-lookalike-letter / dropped-leading-"1" fuzzy match,
         == chapter + 1 (a corrupted but still cur+1 marker).
      3. strict Arabic digits only (never the letter-lookalike class, which
         is far likelier to coincidentally fire on ordinary prose/footnote
         text), on a line that ALSO passes `_looks_english` — a facing Greek
         page's own section numeral (Greek letter, e.g. theta = 9) is
         sometimes OCR'd into a plain, coincidentally-shaped Arabic digit
         ("9." was seen for a Greek theta), which would otherwise jump the
         walk onto the wrong page's numbering — for chapter + 2 ..
         chapter + _MAX_JUMP. A bounded forward jump, tried ONLY once tiers
         1-2 both fail, to recover from a single marker too corrupted for
         either to locate."""
    want = str(chapter + 1)
    m = _SECTION_HEAD.match(line)
    if m and m.group(1) == want and _opens_sentence(m.group(2)):
        return m, chapter + 1
    fm = _SECTION_HEAD_FUZZY.match(line)
    # The letter-lookalike class (tier 2) is wide enough that a Greek-page
    # transliteration fragment can coincidentally open "<lookalike-letter>."
    # (seen: Greek "s." — stigma/epsilon mis-OCR'd — defuzzing to "5" and
    # colliding with a real chapter 5): gate tier 2 on _looks_english too, not
    # just the capitalization check, exactly as tier 3 already is.
    if fm and _opens_sentence(fm.group(2)) and _looks_english(fm.group(2)):
        digits = _defuzz(fm.group(1))
        if digits == want or (chapter + 1 >= 10 and "1" + digits == want):
            return fm, chapter + 1
    if m and _opens_sentence(m.group(2)) and _looks_english(m.group(2)):
        for target in range(chapter + 2, chapter + 1 + _MAX_JUMP):
            if m.group(1) == str(target):
                return m, target
    return None, None


def extract(text: str) -> dict[str, str]:
    """Walk the flat OCR one line at a time, tracking which physical page side
    the line sits on. English recto pages ("BOOK II" running head) carry the
    translation; Greek verso pages ("MARCUS AURELIUS" head) carry only the
    facing Greek and its apparatus and are skipped wholesale — this, not a
    per-line English-ness guess, is what keeps transliterated-Greek noise out.

    On an English page, prose is captured verbatim (page-side already excludes
    the Greek), and a chapter's body is bounded below by the page's footnote
    zone, detected structurally (see `_ELLIPSIS`): a "N " / symbol footnote
    trigger, a bare page-number line, or a spaced ellipsis. A footnote that has
    overflowed from a previous page prints above the trigger with no digit of
    its own — the block captured since the last blank line that runs straight
    into such a trigger is trimmed back off the buffer as footnote, not body. A
    chapter interrupted by a Greek page resumes cleanly on the next English
    page, because the running head reopens capture into the SAME buffer."""
    lines = text.split("\n")
    out: dict[str, str] = {}
    skipped: list[str] = []
    book = 0
    chapter = 0
    buf: list[str] = []
    page = None            # "english" | "greek" | None (front matter)
    footnote_mode = False
    block_start = 0          # buf index where the current blank-separated block began
    block_opened_gap = 0       # how many blank lines opened the current block?
    page_had_body = False      # was any body captured earlier on this physical page?
    overflow_eligible = False  # was there body ABOVE the current block on this page?
    page_double_spaced = False  # does this page wrap body across 2-blank gaps?
    blanks = 0                 # consecutive blank OCR lines just seen

    def flush():
        if book and chapter and buf:
            joined = " ".join(buf).strip()
            if joined:
                out[f"{book}.{chapter}"] = joined

    for raw in lines:
        line = raw.strip()
        if _STOP_MARKER in line:
            break
        if not line:
            blanks += 1
            continue
        run_blanks, blanks = blanks, 0

        m = _BOOK_HEAD.match(line)
        if m:
            n = _roman_to_int(m.group(1))
            if n == book + 1:
                flush()
                book, chapter, buf = n, 0, []
            # n == book is a running head; a new physical English page either
            # way, so reopen capture (footnotes belong to the page they sit on)
            # and forget the previous page's body — the first block on this page
            # is top-of-page body, not a footnote overflow.
            page, footnote_mode, page_had_body = "english", False, False
            page_double_spaced, block_start = False, len(buf)
            continue
        if _GREEK_HEAD.match(line):
            page = "greek"
            continue
        if book == 0 or page != "english":
            continue  # front matter, or a facing Greek page — never body text

        m, target = _match_chapter(line, chapter)
        if target is not None:
            flush()
            if target > chapter + 1:
                skipped.extend(f"{book}.{c}" for c in range(chapter + 1, target))
            chapter = target
            buf = [_clean_prose(_LEAD_NOISE.sub("", m.group(2)))]
            footnote_mode, block_start, block_opened_gap = False, 0, 0
            page_had_body = True  # a chapter body now sits above later blocks
            continue
        # A corrupted-opening marker: the strict digit reads chapter + 1 but its
        # content does not open a capitalised sentence (the opening word is
        # OCR-mangled, e.g. "34. 4 man..." for "34. A man..."). It is a real
        # chapter boundary whose own text is too corrupt to trust — flush the
        # previous chapter and log this one as an unrecovered gap, skipping its
        # body until the next legible marker, rather than letting the corrupt
        # text bleed onto the previous chapter (which had over-run 11.33/11.30).
        bm = _SECTION_HEAD.match(line)
        if bm and bm.group(1) == str(chapter + 1) and not _opens_sentence(bm.group(2)):
            flush()
            chapter += 1
            skipped.append(f"{book}.{chapter}")
            buf, footnote_mode = [], True
            continue
        if footnote_mode or chapter == 0:
            continue
        overflow_anchor = bool(_FOOTNOTE_TRIGGER.match(line) or _PAGE_NUMBER.match(line))
        if overflow_anchor or _ELLIPSIS.search(line):
            # Footnote-zone anchor. Trim off the current block as a marker-less
            # footnote overflow ONLY when ALL of these hold, each ruling out a
            # look-alike that must be kept:
            #   * block_opened_gap >= 2 — the block is set off from the body above
            #     it by a WIDE gap (a footnote boundary), not the 1-blank gap that
            #     merely continues a chapter's body onto its next line (4.19).
            #   * run_blanks <= 1 — the numbered footnote / page-number that ends
            #     the zone sits right below it (an overflow runs INTO the zone);
            #     a double-spaced page keeps its body 2 blanks clear, so its body
            #     is never caught (4.24, 6.50).
            #   * overflow_eligible — there is body ABOVE it on this page, so a
            #     chapter's own tail continuation (first block on a fresh page —
            #     12.36) is safe.
            #   * the block ENDS a sentence — a footnote is a complete sentence
            #     ("...3,000 drachmas."), whereas body that runs onto the next
            #     page breaks off mid-sentence.
            # A spaced ellipsis is the footnote line itself, so it never trims.
            if overflow_anchor and block_opened_gap >= 2 and run_blanks <= 1 \
                    and overflow_eligible \
                    and buf and buf[-1].rstrip().endswith(_SENTENCE_FINAL):
                del buf[block_start:]
            footnote_mode = True
            continue
        if _APPARATUS.search(line):
            # A classical citation — footnote apparatus, never body. When this
            # line was reached WITHIN a block set off from the body by a wide gap
            # (run_blanks == 0, block_opened_gap >= 2), that whole block is the
            # footnote (its earlier lines carried no citation of their own, e.g.
            # 3.1) — drop it. When the citation OPENS a new block (run_blanks > 0,
            # e.g. 8.6's "in Apol. ii. 8 ..."), nothing of it is buffered yet, so
            # just enter footnote mode; the body above stays put.
            if run_blanks == 0 and block_opened_gap >= 2 and overflow_eligible:
                del buf[block_start:]
            footnote_mode = True
            continue
        if _looks_greek(line):
            continue  # backstop: an OCR-mangled Greek head that page-side missed
        if run_blanks >= 2 and page_had_body and not page_double_spaced:
            if buf and buf[-1].rstrip().endswith(_SENTENCE_FINAL):
                # sentence-final line + wide gap on a page that has NOT been seen
                # wrapping body across such gaps => the footnote zone (e.g. the
                # marker-less Latin note set off under 11.33).
                footnote_mode = True
                continue
            # a wide gap after a mid-sentence line is a body wrap: this page
            # double-spaces, so later wide gaps here are body too, not footnotes.
            page_double_spaced = True
        if run_blanks:
            block_start, block_opened_gap = len(buf), run_blanks
            overflow_eligible = page_had_body
        buf.append(_clean_prose(line))
        page_had_body = True
    flush()
    if skipped:
        print(f"  unrecoverable chapter marker(s), OCR too corrupted to "
              f"locate: {', '.join(skipped)}")
    return out


# --- hand-verified per-chapter patches ---------------------------------------
# A small residue of splices (see sources/INVENTORY.md's patch-policy note)
# resist every general signal above without risking regressions on chapters
# that already extract clean, so they are closed the same way the sibling
# repos close their own last-mile residuals: hand-verified, per-chapter,
# exact-string corrections, committed alongside their evidence in
# PATCHES.json rather than folded into the heuristics. Applied LAST, after
# dehyphenation, so each patch's old-text is exactly what a human reviewer
# would see in the finished chapter.
#
# Patches are claims about the extraction output ("this exact string is
# here"), so a patch that no longer finds its target text — because the
# extraction heuristics changed, or the patch was mistyped — must fail the
# build loudly rather than silently no-op and let a corrected-looking but
# actually-still-broken chapter through.
def _load_patches() -> list[dict]:
    if not PATCHES.exists():
        return []
    return json.loads(PATCHES.read_text(encoding="utf-8"))


def _apply_patches(out: dict[str, str], patches: list[dict]) -> dict[str, str]:
    for p in patches:
        chapter = p["chapter"]
        if chapter not in out:
            raise ValueError(f"PATCHES.json: chapter {chapter!r} not found in extraction output")
        text = out[chapter]
        for old in p.get("remove", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: chapter {chapter} 'remove' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, "")
        for old, new in p.get("replace", []):
            if text.count(old) != 1:
                raise ValueError(
                    f"PATCHES.json: chapter {chapter} 'replace' text matched "
                    f"{text.count(old)} times (expected exactly 1): {old!r}"
                )
            text = text.replace(old, new)
        out[chapter] = text.strip()
    return out


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    out = extract(text)
    vocab = _build_vocab(out)
    out = {k: _strip_trailing_mark(_dehyphenate(v, vocab)) for k, v in out.items()}
    out = {k: _strip_comma_footnote_marks(v) for k, v in out.items()}
    patches = _load_patches()
    out = _apply_patches(out, patches)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {OUT} — {len(out)} chapters"
          + (f" ({len(patches)} hand-verified patch(es) applied)" if patches else ""))


if __name__ == "__main__":
    main()
