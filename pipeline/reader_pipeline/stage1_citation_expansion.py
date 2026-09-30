"""Stage 1d: DK source-citation expansion (docs/citation-expansion-wiring-
design.md phases 1-3: DIRECT dictionary lookups, then dash citations by
John's rule E of 2026-09-24, which replaced the memo's R1-R4 -- see "Dash
citations: rule E" below).

A DK fragment/testimonia work MAY opt in by declaring
`citation.expand_citations: true` in its manifest (pilot work:
heraclitus-fragments). For a declared work this module re-extracts each
column's source-citation head(s) from the spine's context runs, resolves the
explicit heads against sources/dk-citations/citation-dictionary.json, and emits
an `expandedCitation` LIST OF RUNS per segment -- one inner list per distinct
context run, document order, never flattened (fix round finding 2: two
separate runs, e.g. Heraclitus B37's "COLUMELLA VIII 4..." and its later,
unrelated "[vgl. B 13],", must never merge into one false attribution). A
work that does NOT declare the flag is completely unaffected -- `run` returns
None and stage7_emit attaches no `expandedCitation` key to any segment
(byte-identical output).

## Head-boundary rule (ported from shared/lib/prose-flow.ts)

The pipeline is Python; the head|body boundary lives in TypeScript. This module
ports the MINIMAL rule John ruled on (item 24, Critias B31, 2026-07-24) --
faithfully, from these prose-flow.ts sources:
  - isLowercaseGreekChar / hasLowercaseGreek : prose-flow.ts:60-74
  - isAllCapsGreekToken                      : prose-flow.ts:84-95
  - isLatinOrNumeralToken / isPurePunctToken : prose-flow.ts:97-105
  - isHeadMaterialToken                      : prose-flow.ts:111-117
  - isSourceHeadOnlyText                     : prose-flow.ts:126-138
  - headPrefixLenInMixedToken                : prose-flow.ts:147-169
  - peelSourceHeadPrefix                     : prose-flow.ts:202-255
Rule (verbatim from prose-flow.ts:190-200): head material is (a) all-caps Greek
title words, (b) Latin-script tokens, (c) numerals / roman numerals / section
markers and punctuation between them; the head ends at the first token that
contains lowercase Greek (intra-token split when a Latin/numeral piece fuses to
the body without a space); the head must contain at least one Latin letter or
numeral -- bare all-caps Greek is not a head; quote-marks/brackets at the seam
attach to the body.

## Resolution

A head is split at each explicit author-variant token outside brackets (the
memo's `multi_source_heads` convention), so one column can carry several
sources; each source is one `expandedCitation` list entry. For each source:
  - a leading author-variant match resolves author+work+locus directly
    (resolution "direct");
  - a leading dash (em / en dash), or a dash-misparse token whose dash was
    lost, is resolved by rule E (resolution "dash", `dashInherited`, flag
    dash-e2 ... dash-e5, or `adjudicated` from John's table), or stays
    verbatim flagged `dash-unresolved` plus the reason;
  - an unmappable apparatus artifact / bracketed non-author passes through
    verbatim (resolution "verbatim") -- honest "as printed", never a
    fabricated author. A bracketed DK cross-reference alone is no head.

## Fatal gate (this module IS the preflight for its sidecar)

(An unresolvable dash is honest verbatim, never fatal -- design §5. The
dash adjudication table is fatal when it no longer matches the text.)

A head whose leading token matches a dictionary author variant but whose work
cannot be resolved (no explicit work token matched AND the author has no
DEFAULT work) is FATAL -- the dictionary knows the author, so a silent drop
would hide a real coverage hole rather than fabricate or pass through. A head
whose leading token matches nothing (author, dash, misparse, unmappable,
bracket) is treated as "not a citation head" (e.g. a run whose first line is
editorial prose) and produces no entry -- counted and reported, never emitted.
"""

from __future__ import annotations

import bisect
import copy
import json
import re
import unicodedata
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest

# --- Ported head-boundary primitives (prose-flow.ts, cited above) ----------

_GREEK_LETTER = re.compile(r"[Ͱ-Ͽἀ-῿]")
# Quotes / brackets at the head|body seam attach to the body (prose-flow.ts:52-54).
_BODY_BOUNDARY_PUNCT = set("'\"’”‘“«»()[]{}")


def _is_greek(ch: str) -> bool:
    return bool(_GREEK_LETTER.match(ch))


def _is_lower_greek(ch: str) -> bool:  # prose-flow.ts:64-67
    return _is_greek(ch) and ch != ch.upper()


def _has_lower_greek(s: str) -> bool:  # prose-flow.ts:69-74
    return any(_is_lower_greek(ch) for ch in s)


def _has_latin_or_numeral(s: str) -> bool:  # prose-flow.ts:76-78
    return bool(re.search(r"[A-Za-z0-9]", s))


def _is_all_caps_greek_token(token: str) -> bool:  # prose-flow.ts:84-95
    saw_greek = False
    for ch in token:
        if _is_lower_greek(ch):
            return False
        if _is_greek(ch):
            saw_greek = True
            continue
        if re.match(r"[A-Za-z]", ch):
            return False
    return saw_greek


def _is_latin_or_numeral_token(token: str) -> bool:  # prose-flow.ts:98-101
    if _GREEK_LETTER.search(token):
        return False
    return _has_latin_or_numeral(token)


def _is_pure_punct_token(token: str) -> bool:  # prose-flow.ts:103-105
    return not _GREEK_LETTER.search(token) and not re.search(r"[A-Za-z0-9]", token)


def _is_head_material_token(token: str) -> bool:  # prose-flow.ts:111-117
    if _has_lower_greek(token):
        return False
    if _is_all_caps_greek_token(token):
        return True
    if _is_latin_or_numeral_token(token):
        return True
    if _is_pure_punct_token(token):
        return True
    return False


def _is_source_head_only_text(text: str) -> bool:  # prose-flow.ts:126-138
    t = text.strip()
    if not t:
        return False
    if _has_lower_greek(t):
        return False
    tokens = re.findall(r"\S+", t)
    if not tokens:
        return False
    saw_latin_or_num = False
    for tok in tokens:
        if not _is_head_material_token(tok):
            return False
        if _has_latin_or_numeral(tok):
            saw_latin_or_num = True
    return saw_latin_or_num


def _head_prefix_len_in_mixed_token(token: str) -> int:  # prose-flow.ts:147-169
    first_lower = -1
    for i, ch in enumerate(token):
        if _is_lower_greek(ch):
            first_lower = i
            break
    if first_lower < 0:
        return len(token)
    body_start = first_lower
    while body_start > 0 and token[body_start - 1] in _BODY_BOUNDARY_PUNCT:
        body_start -= 1
    if body_start == 0:
        return 0
    prefix = token[:body_start]
    if not _has_latin_or_numeral(prefix):
        return 0
    if _has_lower_greek(prefix):
        return 0
    return body_start


def _peel_source_head_prefix(text: str) -> str | None:  # prose-flow.ts:202-255
    """Return the source-citation head prefix of a mixed context string, or
    None when there is no peelable head. (This port needs only the head string,
    not the body rest that prose-flow's renderer also returns.)"""
    tokens = [(m.group(0), m.start()) for m in re.finditer(r"\S+", text)]
    if not tokens:
        return None
    saw_latin_or_num = False
    rest_offset = -1
    for tok, start in tokens:
        if not _has_lower_greek(tok):
            if not _is_head_material_token(tok):
                rest_offset = start
                break
            if _has_latin_or_numeral(tok):
                saw_latin_or_num = True
            continue
        head_len = _head_prefix_len_in_mixed_token(tok)
        if head_len > 0:
            prefix = tok[:head_len]
            if _has_latin_or_numeral(prefix):
                saw_latin_or_num = True
            rest_offset = start + head_len
        else:
            rest_offset = start
        break
    if rest_offset < 0:
        return None  # entire run is head-shaped -> caller uses head-only path
    head = text[:rest_offset].strip()
    if not head or not saw_latin_or_num or not _has_latin_or_numeral(head):
        return None
    if not text[rest_offset:].strip():
        return None
    return head


def _extract_head(line_text: str) -> str | None:
    """The source-citation head at the start of a context-run's first line: a
    peelable prefix (mixed head+Greek body), or the whole line when it is
    head-only (all citation, no Greek body -- prose-flow's isSourceHeadOnlyText
    branch, prose-flow.ts:559 / buildProseFlow)."""
    peeled = _peel_source_head_prefix(line_text)
    if peeled is not None:
        return peeled
    if _is_source_head_only_text(line_text):
        return line_text.strip()
    return None


# --- Dictionary lookup -----------------------------------------------------


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _casefold_tuple(s: str) -> tuple[str, ...]:
    return tuple(t.casefold() for t in _nfc(s).split())


# The "author key" of an ambiguous abbreviation that nothing decides (DK's
# "HEROD.": Herodotus or Herodian) -- never a dictionary key.
_AMBIGUOUS = "?ambiguous"


class _Dictionary:
    """Direct-lookup index over citation-dictionary.json: author-variant and
    per-author work-abbrev token sequences (longest-match), plus the meta
    dash-misparse and unmappable-artifact token sets.

    Work-abbreviation matching is case-folded (Grok gate defect 4: 'c. CELS.'
    must match the dict's 'Cels.' forms) -- the stored work-key tuples and the
    query tokens are both casefolded for comparison; the surrounding pipeline
    always renders from the ORIGINAL-case tokens (verbatim / locus text), so
    casefolding here only affects whether a match fires, never the emitted
    text. Author-variant matching stays case-SENSITIVE: casefolding it turned
    up genuine ambiguity (a locus-internal reference like 'ap. Eus. P. E.'
    would casefold-match Eusebius's 'EUS.' variant and Calcidius's 'Chalcid.'/
    Plato's 'Plat.' would casefold-match mid-sentence in a Latin quotation),
    which the author position never needs -- the census's exact-case variant
    spellings already disambiguate it."""

    def __init__(self, raw: dict):
        self._authors = raw["authors"]
        self.doxographi_pages: list[tuple[int, frozenset[str]]] = []
        meta = raw.get("meta", {})
        self._misparse = {_nfc(t) for t in meta.get("dash_misparse_tokens", [])}
        self._unmappable = {_nfc(t) for t in meta.get("unmappable_artifacts", [])}
        # variant token-tuple -> author key (longest first). A variant in the
        # author's `variants_need_work` names him only when one of his titles
        # follows ("Hipp. Ref." = Hippolytus; "Hipp. maior" = Plato's Hippias
        # after a lost dash). A variant in meta `ambiguous_variants` is no
        # author's: match_author decides it from what follows (_AMBIGUOUS
        # when nothing decides it).
        self._variants: list[tuple[tuple[str, ...], str, bool]] = []
        for key, entry in self._authors.items():
            need_work = {_nfc(v) for v in entry.get("variants_need_work", [])}
            for v in entry["variants"]:
                self._variants.append((tuple(_nfc(v).split()), key, _nfc(v) in need_work))
        self._ambiguous = {tuple(_nfc(v).split()): rules
                           for v, rules in meta.get("ambiguous_variants", {}).items()}
        for seq in self._ambiguous:
            self._variants.append((seq, _AMBIGUOUS, False))
        # A variant that needs a title is tried before the same spelling
        # without one ("GAL." + "Hist. phil." is pseudo-Galen, else Galen).
        self._variants.sort(key=lambda t: (-len(t[0]), not t[2]))
        # per-author: work token-tuple -> work key (longest first, no DEFAULT)
        self._works: dict[str, list[tuple[tuple[str, ...], str]]] = {}
        for key, entry in self._authors.items():
            ws = [
                (_casefold_tuple(wk), wk)
                for wk in entry["works"]
                if wk != "DEFAULT"
            ]
            ws.sort(key=lambda t: -len(t[0]))
            self._works[key] = ws

    def match_author(self, tokens: list[str], i: int, after: str = "") -> tuple[int, str] | None:
        """Longest author-variant match in `tokens` starting at index i;
        returns (token_span, author_key) or None. The key is _AMBIGUOUS for
        an ambiguous abbreviation nothing decides; `after` is the text that
        follows the head (Critias B41 "HEROD." + "π. μον. λέξ. ...")."""
        for seq, key, need_work in self._variants:
            n = len(seq)
            if tuple(tokens[i:i + n]) != seq:
                continue
            if key == _AMBIGUOUS:
                return n, self._disambiguate(self._ambiguous[seq], tokens[i + n:], after)
            if need_work and self.match_work(key, tokens, i + n) is None:
                continue
            return n, key
        return None

    @staticmethod
    def _disambiguate(rules: dict, rest: list[str], after: str) -> str:
        """The author an ambiguous abbreviation names, from what follows it
        (citation-dictionary.json meta `ambiguous_variants_rules`): a book
        numeral + a number ("HEROD. II 123": Herodotus), or a Greek title in
        "π." ("HEROD. π. μον. λέξ.": Herodian); else _AMBIGUOUS."""
        nxt = rest if rest else after.split()
        if "book-chapter" in rules and len(rest) >= 2 \
                and _ROMAN_NUMERAL.match(rest[0].rstrip(".,;")) and re.match(r"^\d", rest[1]):
            return rules["book-chapter"]
        if "greek-title" in rules and nxt and nxt[0] == "π.":
            return rules["greek-title"]
        return _AMBIGUOUS

    def is_ambiguous(self, tokens: list[str]) -> bool:
        """Is this author span an ambiguous abbreviation (meta
        `ambiguous_variants`) that match_author assigned from what follows?"""
        return tuple(tokens) in self._ambiguous

    def match_work(self, key: str, tokens: list[str], i: int) -> tuple[int, str] | None:
        for seq, wk in self._works[key]:
            n = len(seq)
            cand = tuple(t.casefold() for t in tokens[i:i + n])
            if cand == seq:
                # A work-abbreviation key ending in the printed "p." (page)
                # marker doesn't consume it: "p." belongs to the printed
                # locus that follows, not the work marker (Grok gate defect
                # 5, e.g. 'in Alc. I p.' / 'de decade p.') -- span the match
                # one token short so "p." remains the first locus token. Only
                # a key printing the lower-case page marker: Iamblichus' "V.
                # P." is his title (De Vita Pythagorica), not a page.
                span = n - 1 if seq and wk.split()[-1] == "p." else n
                return span, wk
        return None

    def author_entry(self, key: str) -> dict:
        return self._authors[key]

    def is_misparse(self, token: str) -> bool:
        return _nfc(token) in self._misparse

    def is_unmappable(self, head: str, token: str) -> bool:
        return _nfc(head) in self._unmappable or _nfc(token) in self._unmappable


def _load_dictionary() -> _Dictionary:
    # SOURCES_DIR read at call time so tests can monkeypatch it (same posture
    # as every other stage1 module).
    path = SOURCES_DIR / "dk-citations" / "citation-dictionary.json"
    dictionary = _Dictionary(json.loads(path.read_text(encoding="utf-8")))
    pages_path = SOURCES_DIR / "dk-citations" / "doxographi-pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))["pages"] if pages_path.exists() else {}
    # Sorted (page, author keys) -- see _doxographi_owner.
    dictionary.doxographi_pages = sorted((int(p), frozenset(keys)) for p, keys in pages.items())
    return dictionary


def _verbatim(text: str, flags: list[str]) -> dict:
    return {"verbatim": text.strip(), "resolution": "verbatim", "flags": flags}


# --- Locus boundary (Grok content-gate defects 6, 7, 8) --------------------
#
# A resolved source's `locus` is the printed apparatus text after author+work
# are peeled off. Two shapes leak non-locus text into it if left unchecked:
#   7. A bare capitalized Greek abbreviation (e.g. "Ἡ.", short for
#      Ἡράκλειτος) has no lowercase Greek of its own, so the ported
#      prose-flow head-boundary rule (which only watches for lowercase
#      Greek) treats it as head material and it slides into the locus.
#   8. An all-Latin apparatus head (a Latin author quoting/glossing
#      Heraclitus in Latin) has no Greek at all to signal the body
#      boundary, so the ENTIRE Latin sentence -- quote-intro and all --
#      reads as "head-only" text and the whole thing lands in the locus.
# _truncate_locus stops the locus at the first Greek-script token or the
# first genuine lowercase Latin prose word, while letting Roman numerals,
# Bekker page/column numbers (355a, 396b), short lowercase apparatus
# abbreviations (p., c., ap.), capitalized editor names, and bracketed /
# parenthesized apparatus groups (which may contain lowercase text, e.g. an
# editor's French annotation) all continue it unconditionally.
_SHORT_LOWER_ABBREV = re.compile(r"^[a-z]{1,3}\.$")  # p. / c. / ap.
_ROMAN_NUMERAL = re.compile(r"^[IVXLCDM]+$")
_BEKKER_NUMERAL = re.compile(r"^\*?\d+(?:[a-zA-Z]|[a-f]{2}|ff)?[.,;:]?$")  # 132 / 396b / 525, / 95C / *48. / 1ff. / 14: / 2ab
_SINGLE_CAP_ABBREV = re.compile(r"^[A-Z]\.,?$")  # H. / P. / E. -- ambiguous alone
# A genuine page/number token a 2-3 letter Stephanus/Bekker column cluster
# ("1113 AB") may directly follow -- unlike _BEKKER_NUMERAL, this excludes
# the "ff" suffix on purpose: "after 'ff.' ... it ends the locus" (defect 1).
_PAGE_NUMBER = re.compile(r"^\*?\d+[a-zA-Z]?[.,;]?$")
# A range of numbers joined by a dash ("1—17." / "21—23." / "5-7,"): locus
# by the same rules as one number, trailing period and all ("DIOG. IX
# 1—17." keeps "IX 1—17.", as "DIOG. II 3." keeps "II 3.").
_NUMBER_RANGE = re.compile(r"^\*?\d+[a-zA-Z]?[—–-]\d+[a-zA-Z]?[.,;]?$")
_LOWER_PROSE_WORD = re.compile(r"^[a-z]{2,}[.,;:]?$")  # dixit / si / subministrat. / ait:
# A bare capital letter with no period: an Aristotle book letter ("B 2. 355a
# 13", "K 5. 1176a 7", "Θ 2. 1155b 4") or a Stephanus / page column letter
# ("289 A", "p. 178 F"). Greek only as plain capitals (no breathing), and
# only when a number follows -- "Ἡ." / "Δ." (the quoted philosopher's name,
# period-marked) still end the locus.
_LATIN_LETTER = re.compile(r"^[A-Z](?:[—–-][A-Z])?[,;]?$")  # "A", "A—C"
_GREEK_BOOK_LETTER = re.compile(r"^[Α-Ωα-ω]$")  # Iliad upper case, Odyssey lower ("μ 62")

# The "(D. NNN)" / "(D. NNN, W. NN)" Diels-Doxographi-Graeci page ref (memo
# ruling 4), plus any bracket groups DK prints immediately after it -- real
# heads carry a trailing annotation marker there ("HIPPOLYT. Refut. I 13
# (D. 565, W. 16) (1)", "THEOPHRAST. de sensu 1ff. (D. 499ff.) (1)"), which
# is apparatus too and must not stay embedded in the locus. NOT end-anchored:
# anchoring it stranded the whole ref in the locus whenever anything followed.
# The match still starts only at the exact "(D." shape, so no other
# parenthetical _truncate_locus lets through (editor names, edition years, a
# "(Vgl. ...)" cross-reference) is ever pulled out; the run stops at the first
# thing that is not a bracket group.
_DOXOGRAPHI_APPARATUS = re.compile(
    # Also the chapter title first, the page inside its parenthesis:
    # Empedocles A88 "AËT. IV 14, 1 (περὶ κατοπτρικῶν ἐμφάσεων. D. 405)".
    r"\((?:(?:περὶ|διὰ τί|πῶς|τίς|τί|εἰ|ποῦ|πόσ)\s[^()]*?\.\s+)?D\.[^()]*(?:\)(?:\s*(?:\([^()]*\)|\[[^\[\]]*\]))*|$)"
)  # also an unclosed "(D. 341;" where the head was cut at the Greek


def _is_locus_stop_word(token: str) -> bool:
    """A genuine lowercase running Latin word (item 8's body signal) -- never
    the 1-3 letter apparatus abbreviations ('p.', 'c.', 'ap.')."""
    return bool(_LOWER_PROSE_WORD.match(token)) and not _SHORT_LOWER_ABBREV.match(token)


def _opens_sentence(word: str, nxt: str | None) -> bool:
    """A capitalized word, not an abbreviation, followed by running Latin:
    the first word of a sentence ("Milesius ex ...")."""
    core = word.rstrip(",;")
    return nxt is not None and len(core) >= 2 and core[:1].isupper() and core[1:].islower() \
        and core.isalpha() and _is_locus_stop_word(nxt) and not nxt.endswith(".")


def _numbers_follow(tokens: list[str]) -> bool:
    """An edition siglum is locus when its own numbers follow it ("CMG V 9,
    1"): the next token is a number, or a Roman numeral before one."""
    if not tokens:
        return False
    if re.match(r"^\*?\d", tokens[0]):
        return True
    return bool(_ROMAN_NUMERAL.match(tokens[0].rstrip(".,;"))) and len(tokens) > 1 \
        and bool(re.match(r"^\d", tokens[1]))


def _abbrevs_then_numbers(tokens: list[str]) -> bool:
    """Numbers follow, after any lowercase abbreviations ("cor. 3")."""
    j = 0
    while j < len(tokens) and re.fullmatch(r"[a-z]+\.", tokens[j]):
        j += 1
    return _numbers_follow(tokens[j:])


def _garbled_article(tokens: list[str], i: int) -> bool:
    """The export's "3o" for the Greek article before the philosopher's
    initial and the quotation: Melissus A4 "SIMPL. Phys. 70, 16 3o M. καὶ
    ..." (ὁ Μ.). Not "VI 3o [II 445, 16 St.]" (Empedocles B111, a garbled
    30), which no initial and Greek (or the end of the head) follow."""
    return bool(re.fullmatch(r"\d+o", tokens[i]) and i + 1 < len(tokens)
                and _SINGLE_CAP_ABBREV.match(tokens[i + 1])
                and (i + 2 == len(tokens) or _has_lower_greek(tokens[i + 2])))


def _truncate_locus(tokens: list[str], columns: bool = False) -> list[str]:
    return _truncate_locus_ex(tokens, columns)[0]


# Citation schemes whose pages carry column letters (Stephanus: Plato and
# Plutarch's Moralia; Bekker: Aristotle; Casaubon: Athenaeus). A work of
# another scheme may say so itself (citation-dictionary.json work field
# `column_letters`).
_COLUMN_SCHEMES = {"stephanus", "moralia", "bekker", "book-page-col"}


def _column_letters(dictionary: "_Dictionary", key: str, wk: str) -> bool:
    """Review item 10: may a 2-3 letter cluster ("1113 AB") end this work's
    locus? Only where its citation scheme has column letters -- "LUCR. V 621
    DE SOLE" ends at "V 621"."""
    work = dictionary.author_entry(key)["works"][wk]
    return bool(work.get("column_letters", work.get("locus_template") in _COLUMN_SCHEMES))


def _truncate_locus_ex(tokens: list[str], columns: bool = False,
                       head: bool = False) -> tuple[list[str], list[str]]:
    """The locus tokens, and -- when a firm end cut the locus short -- the
    tokens after that end (else []). Firm ends (review finding c): a closed
    group followed by a period ("(oben I 113, 18). II 46 ..." -- what follows
    is a second citation), a "vgl." cross-reference, and a capitalized word
    followed by running prose ("(D. 191) Anaxagorae enim ..."). `columns`:
    the source's scheme has column letters (_column_letters). `head`: the
    printed extent of a head (_head_extent), not the locus the reader
    expands, which also runs through a section word before its number ("I
    praef. 32", "V. soph. I 15, 2"), DK's "z. d. St.", and column letters
    after a page ("p. 832 DE"), and stops at a name in a list ("74
    Parmenides, X., minus ...")."""
    out: list[str] = []
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if tok.startswith("(") or tok.startswith("["):
            close = ")" if tok.startswith("(") else "]"
            j = i
            while j < n and close not in tokens[j]:
                j += 1
            if j >= n:  # unclosed group -> keep the rest verbatim, stop
                out.extend(tokens[i:])
                break
            out.extend(tokens[i:j + 1])
            if tokens[j].endswith(close + "."):
                out[-1] = out[-1][:-1]
                return out, tokens[j + 1:]
            i = j + 1
            continue
        if tok.casefold().rstrip(".") == "vgl":
            break
        nxt = tokens[i + 1] if i + 1 < n else None
        if tok in ("a", "b") and out and out[-1][:1].isdigit() and nxt is not None and nxt[:1].isdigit():
            out.append(tok); i += 1; continue  # Bekker column set apart: "1009 b 25"
        if tok in ("r", "v") and out and re.fullmatch(r"\d+", out[-1]):
            out.append(tok); i += 1; continue  # a leaf's side: "1533f. 5 v" (Democritus B307)
        if _garbled_article(tokens, i):
            break
        if _GREEK_BOOK_LETTER.match(tok) and nxt is not None and nxt[:1].isdigit():
            out.append(tok); i += 1; continue
        if not head and columns and out and _PAGE_NUMBER.match(out[-1]) and re.fullmatch(r"[A-Fa-f][,;]?", tok):
            # A column letter after the page, in either case and whatever
            # follows: "ATHEN. IV 157 c Εὐξίθεος", "X 413 F nach 21 C 2" (the
            # head's printed extent already runs through it).
            out.append(tok); i += 1; continue
        if out and re.fullmatch(r"\d+,?|[IVXLC]+", out[-1]) and re.fullmatch(r"[a-f]", tok) \
                and (nxt is None or nxt[:1] in "[(" or nxt == "p." or nxt[:1].isdigit()):
            # A section's letter: Stobaeus "I 10, 11 b p. 121 W.", "I 21, 7 a
            # [p. 187, 14 Wachsm.]"; Seneca's book "IV a 2, 17".
            out.append(tok); i += 1; continue
        if _LATIN_LETTER.match(tok) and not (nxt is not None and _is_locus_stop_word(nxt)):
            out.append(tok); i += 1; continue
        if _GREEK_LETTER.search(tok):
            break
        if tok == "a." and nxt == "O.":  # "a. O.": am angegebenen Ort (_same_place_above)
            out += [tok, nxt]; i += 2; continue
        if _SHORT_LOWER_ABBREV.match(tok):
            out.append(tok); i += 1; continue
        if head and re.fullmatch(r"[a-z]{4,}\.", tok) and _abbrevs_then_numbers(tokens[i + 1:]):
            # A section word before its number: "I praef. 32", "I prooem.
            # cor. 3", "V. soph. I 15, 2".
            out.append(tok); i += 1; continue
        core = tok.rstrip(".,;")
        if core and _ROMAN_NUMERAL.match(core) and not _SINGLE_CAP_ABBREV.match(tok):
            # "D." / "L." / "M." / "X." with a period is an initial, below.
            out.append(tok); i += 1; continue
        if not out and re.fullmatch(r"[ivx]{1,4}", tok) and nxt is not None and nxt[:1].isdigit():
            # A book numeral the spine prints in lower case, opening the
            # locus before a number: "CIC. de div. i 50, 112" (Anaximander A5a).
            out.append(tok); i += 1; continue
        if _NUMBER_RANGE.match(tok):
            out.append(tok); i += 1
            if tok.endswith(".") and nxt is not None and re.fullmatch(r"\(\d+\)", nxt):
                break  # DK's section marker opens the passage: "IX 1—17. (1)"
            continue
        if _BEKKER_NUMERAL.match(tok):
            out.append(tok); i += 1; continue
        if _SINGLE_CAP_ABBREV.match(tok):
            # Ambiguous alone: a title-abbreviation letter ("P. E." =
            # Praeparatio Evangelica) vs. an author-name initial introducing
            # the Latin quotation ("H. dixit quod" = "Heraclitus said
            # that..."). One-token lookahead: it continues the locus unless
            # the very next token is itself prose, or a capitalized word that
            # opens a Latin sentence (Anaximander A30 "CENSORIN. 4, 7 A.
            # Milesius videri sibi": A[naximander] Milesius).
            if nxt is not None and (_is_locus_stop_word(nxt)
                                    or _opens_sentence(nxt, tokens[i + 2] if i + 2 < n else None)):
                break
            if out and _SINGLE_CAP_ABBREV.match(out[-1]) and nxt is not None and _has_lower_greek(nxt):
                break  # after the editor's initial, the philosopher's: "37 H. Z. ὁ Ἐλεάτης"
            out.append(tok); i += 1; continue
        if head and tok == "St." and out and out[-1] == "d.":
            out.append(tok); i += 1; continue  # "z. d. St.": zu der Stelle, on the passage
        if re.fullmatch(r"[A-Z][a-z]*\.(?:[—–-][A-Z][a-z]*\.)+,?", tok) and any(re.search(r"\d", t) for t in out):
            # Two editors after the place, joined by a dash: "II 277, 10
            # Us.—Rad." (Usener-Radermacher; Critias B49, Grok head check
            # 2026-09-28).
            out.append(tok); i += 1; continue
        if len(core) >= 2 and core[:1].isupper() and core.isalpha():
            if core.isupper() and re.fullmatch(r"[A-F]{2,3}", core):
                # Stephanus/Bekker column-letter cluster ("1113 AB") -- counts
                # only when it directly follows a page/number token already
                # in the locus; after "ff." or any other word it ends the
                # locus instead of falling through to the capitalized-word
                # rule below (defect 1: "LUCR. V 621ff. DE SOLE" must not
                # keep "DE" just because a digit appeared earlier in the
                # locus -- only the immediately preceding token counts), and
                # only in a scheme that has column letters (review item 10:
                # "LUCR. V 621 DE SOLE").
                if (columns or (head and len(out) >= 2 and out[-2] == "p.")) and out \
                        and (_PAGE_NUMBER.match(out[-1]) or _NUMBER_RANGE.match(out[-1])):
                    out.append(tok); i += 1; continue
                break
            if head and tok.endswith(",") and not tok.endswith(".,"):
                break  # a name in a list, not an editor: "74 Parmenides, X., minus ..."
            if not tok.endswith(".") and nxt in ("V.", "v.") and i + 2 < n \
                    and re.fullmatch(r"[A-Z][a-z]*\.", tokens[i + 2]):
                break  # the philosopher, "von" his city: "25, 2 Diogenes V. Ap." (Leucippus A3)
            j = i
            while j < n and re.fullmatch(r"[A-Z][a-z]+", tokens[j]):
                j += 1
            if j > i and j < n and (tokens[j] in ("...", "…") or (
                    re.fullmatch(r"[A-Z]\.,", tokens[j]) and j + 1 < n and re.fullmatch(r"[a-z]+,?", tokens[j + 1]))):
                # Names before DK's ellipsis or an initial and running Latin
                # open the quotation, not an editor: "51 Plato ... in Politia",
                # "II, 1, 33 Otho Iunius ... edidit", "III 1, 10 Abderites P.,
                # a quo".
                break
            if core.isupper() and any(re.search(r"\d", t) for t in out) \
                    and not _numbers_follow(tokens[i + 1:]):
                break  # a heading after the locus: "V 621ff. DEMOCRITI DE SOLE"
            if nxt is not None and core[1:].islower() and not tok.endswith(".") \
                    and _is_locus_stop_word(nxt) and not nxt.endswith("."):
                break  # a Latin sentence's first word, not an editor
            if tok.endswith(".") and len(core) <= 2 and _opens_sentence(nxt or "", tokens[i + 2] if i + 2 < n else None):
                break  # the quoted philosopher's initial: "Helm Th. Milesius ex ..."
            if tok.endswith(".") and len(core) == 2 and nxt is not None and _is_locus_stop_word(nxt) \
                    and not nxt.endswith("."):
                break  # the same initial before running Latin: "Friedl. Ph. vero Pythagoricus"
            out.append(tok); i += 1; continue  # capitalized editor name
        break
    return out, []


# Another page of the same work to compare, printed bare right before the
# quotation begins (Parmenides B7 "PLATO Soph. 237 A vgl. 258D"): apparatus,
# not a further locus -- _head_extent already let the head run through it
# (_COMPARE_PAGE), so it is always the last thing in the printed locus.
# Also another place with its book and its edition page, after a dash:
# Heraclitus B29 "— — —60 (II 366, 11) vgl. IV 50 (II 271, 17)" (Clement).
_LOCUS_COMPARE_TAIL = re.compile(r"\s+vgl\.\s+(?:[IVX]+\s+)?\d+(?:\s?[A-F])?(?:\s+\([^()]*\))?$"
                                 # DK's bare "nach B 14" (_NACH_FRAGMENT), 2026-09-29.
                                 r"|\s+nach\s+(?:\d+\s+)?[ABC]\s?\d+[a-z]?(?:,\s*\d+)?(?=:?$)")


def _locus_fields(locus_tokens: list[str], truncate: bool, is_last: bool,
                  columns: bool = False) -> tuple[str, str | None]:
    """The printed locus after author+work, and any "(D. NNN)" apparatus
    pulled out of it."""
    compare = None
    if truncate:
        # Grok content-check item 27, 2026-09-27: the "vgl. 258D" compare
        # note the head already carries was dropped instead of becoming
        # apparatus.
        match = _LOCUS_COMPARE_TAIL.search(" ".join(locus_tokens))
        if match:
            compare = match.group(0).strip()
        locus_tokens = _truncate_locus(locus_tokens, columns)
    locus = " ".join(locus_tokens)
    if locus.endswith(":"):
        locus = locus[:-1]  # "GELL. XVII 21, 14: iuxta ...", the colon before the quotation
    book = re.match(r"[ivx]{1,4}(?=\s+\d)", locus)
    if book:
        # A book numeral the export prints in lower case reads as the
        # numeral: Empedocles A72 "AËT. v 19, 5" is Aëtius V 19, 5.
        locus = book.group().upper() + locus[book.end():]
    if not is_last and locus.endswith(","):
        # Multi-source split: the comma that separated this source from the
        # next in the printed head belongs to the head, not this source's
        # locus (Grok gate defect 6).
        locus = locus[:-1]
    apparatus = None
    m = _DOXOGRAPHI_APPARATUS.search(locus)
    if m:
        # "(D. NNN)" Doxographi Graeci page ref rides along the locus but is
        # never expanded (memo rulings 4/5, "Apparatus is never expanded") --
        # pull it into its own field so the renderer can print it, and drop
        # it from `locus`, per fix round finding 1.
        apparatus = m.group(0)
        locus = re.sub(r"\s+", " ", locus[:m.start()] + " " + locus[m.end():]).strip()
    if compare:
        apparatus = compare if not apparatus else f"{apparatus} {compare}"
    return locus, apparatus


def _split_editor(locus: str) -> tuple[str, str | None]:
    """A work with `editor_apparatus` (a gnomologium): the locus keeps only
    its numbers -- codex, saying, book, "n." / "p." before a number -- and the
    editor or edition printed with them ("ed. Sternbach", "Sternb.", a
    bracket group) becomes apparatus, as printed, in printed order:
    "ed. Sternbach n. 209" -> ("n. 209", "ed. Sternbach")."""
    toks = locus.split()
    kept: list[str] = []
    app: list[str] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok[:1] in "([":
            close = ")" if tok[0] == "(" else "]"
            j = i
            while j < len(toks) - 1 and close not in toks[j]:
                j += 1
            group = toks[i:j + 1]
            group[-1] = group[-1].rstrip(":")  # "[... nach Elter]: 166"
            app.extend(group)
            i = j + 1
            continue
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        core = tok.rstrip(".,;:")
        if re.match(r"^\*?\d", tok) or _ROMAN_NUMERAL.match(core) \
                or (tok in ("n.", "p.") and re.match(r"^\d", nxt)):
            kept.append(tok)
        else:
            app.append(tok)
        i += 1
    return " ".join(kept).rstrip(","), (" ".join(app) or None)


def _entry(
    verbatim: str, resolution: str, author: dict, work: dict,
    locus: str, apparatus: str | None, extra_flags: list[str],
) -> dict:
    if work.get("editor_apparatus"):
        locus, editor = _split_editor(locus)
        apparatus = " ".join(filter(None, [editor, apparatus])) or None
    if work.get("edition_note"):
        # The editor whose pages the locus gives, after it: Bekker's Anecdota
        # Graeca "I 337, 13 Bekk." (John's ruling, 2026-09-29).
        apparatus = " ".join(filter(None, [work["edition_note"], apparatus]))
    # `bare_title` (a work cited by its own name, not an author's -- the
    # Suda): the empty `title` prints nothing ("Suda, s.v. word"), but a head
    # with no locus at all falls back to it instead of a dangling "Suda,".
    title = work["title"]
    if not title and not locus and work.get("bare_title"):
        title = work["bare_title"]
    result = {
        "verbatim": verbatim,
        "resolution": resolution,
        "authorDisplay": author["canonical_author"],
        "work": {"title": title, "italic": bool(work["title_italic"])},
        "locus": locus,
        "flags": list(author.get("flags", [])) + list(work.get("flags", [])) + extra_flags,
        "dashInherited": resolution == "dash",
    }
    if author["canonical_author"] is None:
        # An edition with no author (Bekker's Anecdota Graeca, John's ruling
        # 2026-09-24): the reader prints the work first.
        del result["authorDisplay"]
    if apparatus:
        result["apparatus"] = apparatus
    return result


def _work_and_locus(
    dictionary: _Dictionary, key: str, author_span: int, tokens: list[str],
    start: int, end: int, is_last: bool,
) -> tuple[str | None, str, str | None]:
    """(work key, locus, apparatus) for one source span tokens[start:end]
    whose author matched `key`; work key None when no work token matches and
    the author has no DEFAULT."""
    entry = dictionary.author_entry(key)
    work_start = start + author_span
    matched = dictionary.match_work(key, tokens, work_start)
    if matched is not None:
        wspan, wk = matched
        includes = bool(entry["works"][wk].get("locus_includes_work"))
        if entry["works"][wk].get("locus_as_printed"):
            # With locus_includes_work the matched words stay printed: "bei
            # Eus. P. E. XIV 27, 4" (Dionysius of Alexandria) names the text
            # that preserves him, apparatus as _as_printed reads it.
            locus, apparatus = _as_printed(tokens[(work_start if includes else work_start + wspan):end], is_last)
            return wk, _edition_locus(entry["works"][wk], locus), apparatus
        locus_tokens = tokens[work_start:end] if includes else tokens[work_start + wspan:end]
        locus, apparatus = _locus_fields(locus_tokens, not includes, is_last,
                                         _column_letters(dictionary, key, wk))
        return wk, _edition_locus(entry["works"][wk], locus), apparatus
    if "DEFAULT" in entry["works"]:
        locus, apparatus = _locus_fields(tokens[work_start:end], True, is_last,
                                         _column_letters(dictionary, key, "DEFAULT"))
        return "DEFAULT", _edition_locus(entry["works"]["DEFAULT"], locus), apparatus
    return None, "", None


# A note naming the text that preserves the passage ("bei Theogn. p. 79 [I
# 355, 19 L.]": Herodian quoted in Theognostus): apparatus, not the locus.
_PRESERVED_IN = {"bei", "b."}  # "b. Eus. P. E. X 3, 25" (Protagoras B2)


def _as_printed(tokens: list[str], is_last: bool) -> tuple[str, str | None]:
    """(locus, apparatus) for a work with `locus_as_printed` (Herodian's,
    content review item 6): everything printed after the title, untrimmed;
    a "bei <author>" note is apparatus, and the locus is then empty."""
    text = " ".join(tokens)
    if not is_last and text.endswith(","):
        text = text[:-1]
    if tokens and tokens[0].casefold() in _PRESERVED_IN:
        return "", text
    return text, None


def _edition_locus(work: dict, locus: str | None) -> str | None:
    """The locus with what the work entry prints before it: its
    `locus_prefix` (the lexicon a head names in its author slot, "Antiatt.")
    and the volume its `volume_by_part` gives it ("I, Lex. VI p. 418, 6":
    Bekker's Anecdota Graeca, John's ruling 2026-09-24). The volumes each
    start at p. 1, so a page alone names none (Sol review finding 2): a
    volume numeral the head prints wins ("II p. 337, 13"); else the locus
    must open with a listed part whose page lies inside it. None otherwise
    -- the head then stays as printed, never guessed. A locus that already
    opens with its volume (a dash built on one) is checked, not prefixed
    again."""
    table = work.get("volume_by_part")
    prefix = work.get("locus_prefix")
    if locus is None or (table is None and not prefix):
        return locus
    built = re.match(r"^([IVX]+),\s+", locus)  # "I, Lex. VI p. 472, 14"
    body = locus[built.end():] if built else locus
    if prefix and not built and not body.startswith(prefix):
        body = f"{prefix} {body}".strip()  # a locus_as_printed work may print none of its own
    if table is None:
        return body
    # A listed part, in any case or another printed form, is printed as
    # listed: "LEX. VI 374, 14" and "VI 403, 5" are Lex. VI (Democritus
    # B122, Antiphon B19; John's ruling, 2026-09-29) -- Bekker has three
    # volumes, so "VI" is no volume.
    for part, lo, hi, vol, *other in table:
        for printed in [part] + (other[0] if other else []):
            m = re.match(re.escape(printed) + r"(?![A-Za-z])", body, re.IGNORECASE)
            page = m and (re.match(r"\s*(?:p\.\s*)?(\d+)", body[m.end():]))
            if page and lo <= int(page.group(1)) <= hi and (not built or built.group(1) == vol):
                return f"{vol}, {part}{body[m.end():]}"
    if not built and re.match(r"^[IVX]+\s+(?=\d|p\.)", body):
        return body  # "I 337, 13", "II p. 337, 13": printed by DK
    return None


def _resolve_source(
    dictionary: _Dictionary,
    key: str,
    author_span: int,
    tokens: list[str],
    start: int,
    end: int,
    work_id: str,
    seg_id: str,
    is_last: bool,
) -> tuple[dict, str]:
    """Resolve one source span tokens[start:end] whose author matched `key`
    over `author_span` tokens; returns (entry, work key). Fatal when the
    author is known but no work resolves and the author has no DEFAULT (never
    fabricate)."""
    entry = dictionary.author_entry(key)
    wk, locus, apparatus = _work_and_locus(dictionary, key, author_span, tokens, start, end, is_last)
    if wk is None:
        raise ValueError(
            f"{work_id}: citation head in segment {seg_id!r} resolves to author "
            f"{entry['canonical_author']!r} (dictionary key {key}), but names no "
            f"work this author has -- tokens {tokens[start + author_span:end]!r} match no "
            f"work abbreviation and {key} has no DEFAULT work (never fabricate a "
            f"title; add the work to the dictionary or flag the head)"
        )
    if locus is None:  # _edition_locus: no volume for this page
        return _verbatim(" ".join(tokens[start:end]), ["edition-volume-unknown"]), wk
    return _entry(" ".join(tokens[start:end]), "direct", entry, entry["works"][wk],
                  locus, apparatus, []), wk


# A word that makes the author abbreviation after it part of the title it
# is in, not a new source: Critias B16 "GREGOR. CORINTH. Zu HERMOG." (on
# Hermogenes), "SCHOL. ad DIONYS.", "EUSTATH. Z. DIONYS." (review finding d).
_TITLE_CONNECTORS = {"zu", "z.", "ad", "in", "bei", "apud", "ap."}


def _is_new_source_at(tokens: list[str], i: int) -> bool:
    """An author variant at tokens[i] (i > 0) starts a new source unless the
    word before it ties it into the current title: a connector, or an
    all-caps title word ("OXYRH. PAP.", "HIBEH PAPYR.", "OLYMP. IN PLAT.").
    A citation that ended on a number, a closing bracket or a comma /
    semicolon, or a Latin sentence that ended in a period, is followed by a
    new source. A mixed-case abbreviation ("Hipp.", "Diog.") could also be a
    word of the running Latin, so it starts a new source only after a
    period, a semicolon, a closing bracket or a number (item 6, Democritus
    B32 "— —94 (I 214, 9 St.) Hipp. Ref. VIII 14")."""
    prev = tokens[i - 1]
    if any(c.islower() for c in tokens[i]):
        return bool(re.search(r"[\d)\]]", prev) or prev.endswith((".", ";")))
    if re.search(r"[\d)\]]", prev) or prev.endswith((",", ";")):
        return True
    if prev.casefold() in _TITLE_CONNECTORS:
        return False
    if not any(c.islower() for c in prev):
        # A single column letter after a page ("p. 1111 F. AËT.") ends a
        # citation; any other all-caps word is part of a title.
        return bool(re.fullmatch(r"[A-Z]\.?", prev) and i >= 2 and re.search(r"\d", tokens[i - 2]))
    return True


def _split_sources(dictionary: _Dictionary, tokens: list[str], i: int,
                   after: str = "") -> list[tuple[int, int, str]]:
    """(start, author_span, author_key) of each explicit author-variant token
    at or after index i (the memo's multi_source_heads convention). An author
    named inside a bracket or parenthesis ("[vgl. ATHEN. XIII 610 B]") is a
    cross-reference within the source, never a new source; nor is one that a
    title connector ties to the source before it (_is_new_source_at).
    `after` is the text after the head (see _Dictionary.match_author)."""
    starts: list[tuple[int, int, str]] = []
    depth = 0
    first = i
    while i < len(tokens):
        m = dictionary.match_author(tokens, i, after) if depth == 0 else None
        if m is not None and i > first and not _is_new_source_at(tokens, i):
            m = None
        if m is not None:
            starts.append((i, m[0], m[1]))
            span = m[0]
        else:
            span = 1
        for tok in tokens[i:i + span]:
            depth = max(0, depth + tok.count("[") + tok.count("(") - tok.count("]") - tok.count(")"))
        i += span
    return starts


# --- Dash citations: rule E (John, 2026-09-24) ------------------------------
#
# DK's dash stands for "the source above"; the survey of all 613 dash heads
# in the 39 fragment/testimonia works showed the NUMBER of dashes is not a
# reliable guide to how much it stands for. Rule E reads what follows the
# dashes instead:
#   1. The source is the last author named, walking back in document order
#      through the work, across columns (each run() is one work, so nothing
#      carries between works). Exception: when what follows cannot belong to
#      that author -- a work title the dictionary does not give him, or a
#      "(D. NNN)" Doxographi page -- take the nearest earlier source that
#      fits, which may be one named inside a passage (Heraclitus A11,
#      Empedocles A93).
#   2. Nothing follows: the same place as the citation above. In a lexicon
#      (Harpocration, Hesychius, Suda, Etymologicum), a dash plus a word is
#      s.v. that headword.
#   3. A work title follows: same author, that work, the locus as printed.
#   4. A book numeral follows (Roman, or a book letter): same author and
#      work, the locus as printed.
#   5. Only numbers follow: keep the citation above and replace the same
#      number of trailing parts, like for like ("— —210" after STOB. III 1,
#      91 = III 1, 210; "—2, 36" after that = III 2, 36).
# Where rule E cannot produce a complete, certain citation the head stays
# verbatim, flagged `dash-unresolved` plus the reason -- never invented.
# Certainty guards beyond the rule's own wording, each tested:
#   - a source named inside a passage by ANOTHER author than the last head
#     leaves a dash with nothing but numbers (or nothing) undecidable: the
#     print does not say which one it repeats (Empedocles A44 -> A45 vs
#     Heraclitus A10 -> A11), so it stays verbatim unless a title or a
#     "(D.)" page decides;
#   - the title walk-back stops at the last explicit head: an older source
#     reached only because the dictionary lacks the title would be a guess;
#   - an all-caps author the dictionary does not know still resets the chain
#     (a following dash stays verbatim), and stops the "(D.)" walk-back;
#   - an undashed continuation locus inside a passage ("... 8, 10 (D. 395)")
#     moves the chain like a dash would, so the next dash builds on it;
#   - a "(D. NNN)" page picks an author only when the explicit heads show
#     the page is his (_doxographi_owner), else `doxographi-owner-unknown`;
#   - numbers opening with two places ("152. 153") stay verbatim when they
#     could replace one number or two (_level_uncertain);
#   - a book numeral under a work title that carries its book ("Contra
#     Celsum (lib. VI)") is dropped when it is that book, and leaves the
#     dash verbatim when it is another.
# Rulings John made from the TLG check override rule E per head
# (dash-adjudications.json: readings, misprint corrections with a note,
# heads awaiting his check of the print).
# A filled-in dash emits resolution "dash" with the same fields as a direct
# entry (the reader renders the two identically, John's ruling); its flags
# name the step (dash-e2 ... dash-e5).

_LEXICON_FLAG = "cited-by-lemma"
# An author read from an ambiguous abbreviation by a rule of thumb ("HEROD."
# + book + chapter = Herodotus; Herodian the historian is cited the same
# way): on the head and on every dash built on it, so the TLG check
# (tests/test_dash_citations_verified.py) can require each one confirmed.
_INFERRED = "author-inferred"

# Memo §5: "dash-work tokens deliberately left out of the R3 lookup" --
# attribution unconfirmable from the census, so never resolved here. All
# five ("de vertig.", "de odor.", "de vita contempl. p.", "de differ. puls.",
# "in Hes. Opp.") were read in their columns on 2026-09-28 and are now
# dictionary keys under the author whose head each follows; add a title
# here only when its column cannot decide it.
_DASH_WORK_EXCLUDED: list[tuple[str, ...]] = []
_DASH_PREFIX = re.compile(r"^(?:[—–]\s*)+")
_ATTACHED_DASH = re.compile(r"^[—–]+[A-Za-z0-9]")
# First token after the dashes that is a locus, not a work title: a number,
# a Roman numeral, a bare or period-marked capital letter (book / column
# letter), a page / number marker, a parenthesized or asterisked number.
_LOCUS_START = re.compile(r"^(\d|\(\d|\*\d|[IVXLCDM]+[.,;]?$|[A-ZΑ-Ω][.,;]?$|p\.$|n\.$)")
# Diels' own doubt about a dash's printed numeral or reading ("(?)", or a
# bare "?") -- never expanded on a guess (stage3_tokenize.py has the same
# convention for a doubtful word, e.g. Heraclitus B12's "ἀναθυμιῶνται(?)").
_LOCUS_DOUBT_MARK = re.compile(r"\?")


class _Source:
    """One source the chain has seen: dictionary author key (None = not an
    author the dictionary knows, or not decidable), work key (None =
    unknown), locus without its apparatus (None = unknown). `origin` is
    "head" or "passage"; `foreign` marks an explicit all-caps author the
    dictionary does not know."""

    def __init__(self, author: str | None, work: str | None, locus: str | None,
                 origin: str = "head", foreign: bool = False,
                 like: "_Source | None" = None, inferred: bool | None = None) -> None:
        self.author, self.work, self.locus = author, work, locus
        self.origin, self.foreign = origin, foreign
        # The author was read from an ambiguous abbreviation (_INFERRED);
        # a source continuing `like` in the same work inherits it.
        same = like is not None and (like.author, like.work) == (author, work)
        self.inferred = inferred if inferred is not None else (same and like.inferred)
        # What is still known when the locus is not: the work abbreviation
        # printed at the front of a DEFAULT work's locus ("V. H. " in AEL. V.
        # H. X 13; "" when none, None when unknown) and the kinds of the
        # locus's parts -- carried over from `like`, the source this one
        # continues in the same work.
        if locus is not None:
            parts = _locus_parts(locus)
            self.prefix: str | None = _locus_prefix(locus)
            self.shape: list[str] | None = [p.kind for p in parts] if parts is not None else None
        elif like is not None and (like.author, like.work) == (author, work):
            self.prefix, self.shape = like.prefix, like.shape
        else:
            self.prefix, self.shape = None, None
        # A citation that prints only the text preserving the passage, as
        # apparatus with no locus of its own ("DIONYSIOS, bei Eus. P. E. XIV
        # 27, 4"): that place, for a dash that replaces its numbers.
        self.preserved: str | None = None


class _Chain:
    """Every source named so far in one work, document order."""

    def __init__(self) -> None:
        self.sources: list[_Source] = []
        self.head_start = 0  # index of the last explicit head's first source

    def push_head(self, sources: list[_Source]) -> None:
        self.head_start = len(self.sources)
        self.sources.extend(sources)

    def last_head_author(self) -> str | None:
        for src in reversed(self.sources):
            if src.origin == "head":
                return src.author
        return None


# --- Locus parts (rule E step 5) --------------------------------------------
#
# A locus is read as typed parts: B book (Roman numeral or book letter), N
# number (with a letter suffix, "ff.", or an asterisk; a "p."/"n."/"c."/"t."
# marker before it stays part of it), K Bekker page+column ("355a", "1009
# b"), C column letter(s) ("A", "D E"). "63. 83a" after a comma is one part
# (two places at one level). Bracket groups and trailing editor names are not
# parts. Step 5 keeps the text before the replaced parts and appends the
# dash's own printed locus.


class _Part:
    def __init__(self, kind: str, start: int, end: int, num_start: int | None = None,
                 multi: bool = False) -> None:
        self.kind, self.start, self.end = kind, start, end
        # Where the number itself starts, after a "p." / "n." marker.
        self.num_start = start if num_start is None else num_start
        # Two places joined by a period ("152. 153"): one part, by DK's
        # usage, but on its own it does not show which level it stands at.
        self.multi = multi


_NUM = re.compile(r"^\*?\d+[a-z]{0,2}(?:ff?)?$")
_NUM_WITH_COLUMN = re.compile(r"^(\d+)([A-F])$")
_NUM_MARKERS = {"p", "c", "n", "t", "fr", "ol", "cap"}


def _locus_parts(locus: str) -> list[_Part] | None:
    """The typed parts of a locus, or None when numbers follow something this
    reader does not understand, or the levels are ambiguous -- so that a
    replacement can never land on the wrong level."""
    toks = [(m.group(0), m.start()) for m in re.finditer(r"\S+", locus)]
    parts: list[_Part] = []
    i, depth = 0, 0
    while i < len(toks):
        tok, s = toks[i]
        opens = tok.count("(") + tok.count("[")
        closes = tok.count(")") + tok.count("]")
        if depth > 0 or tok[:1] in "([":
            depth = max(0, depth + opens - closes)
            i += 1
            continue
        core = tok.rstrip(",;.:")
        nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
        nxt_num = bool(re.match(r"^\*?\d", nxt))
        if core in _NUM_MARKERS and tok.endswith(".") and nxt_num:
            n_tok, n_s = toks[i + 1]
            parts.append(_Part("N", s, n_s + len(n_tok.rstrip(",;.:")), n_s))
            i += 2
            continue
        if core in ("ff", "f") and parts:
            parts[-1].end = s + len(tok.rstrip(",;:"))
            i += 1
            continue
        after_number = bool(parts) and parts[-1].kind in ("N", "C")
        if re.fullmatch(r"[A-F][—–-][A-F]", core) and after_number:
            parts.append(_Part("C", s, s + 3))  # a column range, "337 A—C"
            i += 1
            continue
        if len(core) == 1 and "A" <= core <= "F" and after_number:
            if parts[-1].kind == "C":
                parts[-1].end = s + 1
            else:
                parts.append(_Part("C", s, s + 1))
            i += 1
            continue
        if re.fullmatch(r"[IVXLC]{2,}", core) or (
                len(core) == 1 and core.isupper() and core.isalpha()
                and (nxt_num or nxt == "p.")):
            parts.append(_Part("B", s, s + len(core)))
            i += 1
            continue
        if len(core) == 1 and "A" <= core <= "F":
            parts.append(_Part("C", s, s + 1))
            i += 1
            continue
        if re.fullmatch(r"\d+[ab]", core) and nxt_num:
            parts.append(_Part("K", s, s + len(core)))
            i += 1
            continue
        if re.fullmatch(r"\d+", core) and nxt in ("a", "b") and i + 2 < len(toks) \
                and re.match(r"^\d", toks[i + 2][0]):
            parts.append(_Part("K", s, toks[i + 1][1] + 1))
            i += 2
            continue
        m = _NUM_WITH_COLUMN.match(core)
        if m:
            parts.append(_Part("N", s, s + len(m.group(1))))
            parts.append(_Part("C", s + len(m.group(1)), s + len(core)))
            i += 1
            continue
        if _NUM.match(core):
            parts.append(_Part("N", s, s + len(core)))
            i += 1
            continue
        if not parts and not re.search(r"\d", tok):
            i += 1  # a work abbreviation printed before the locus ("V. H.")
            continue
        # Anything else ends the parts: fine when only editor names and
        # apparatus follow, unreliable when more numbers do.
        tail = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", "", locus[s:])
        if re.search(r"\d", tail):
            return None
        break
    # "29, 63. 83a" / "33, 24. 25": two places at the last level are one
    # part. Right after a book ("VI 152. 153", "II 1. 2") the period may
    # join two places (Pollux: book, section) or two levels (a misprinted
    # "II 1, 2"): undecidable, so unreliable.
    merged: list[_Part] = []
    for p in parts:
        if merged and p.kind == "N" and merged[-1].kind == "N" and merged[-1].num_start == merged[-1].start \
                and p.num_start == p.start and locus[merged[-1].end:p.start].strip() == ".":
            if len(merged) >= 2 and merged[-2].kind == "B" \
                    and not locus[merged[-2].end:merged[-1].start].strip():
                return None
            merged[-1] = _Part("N", merged[-1].start, p.end, multi=True)
        else:
            merged.append(p)
    return merged


def _locus_prefix(locus: str) -> str:
    """The text before a locus's first number or book numeral: a work
    abbreviation the dictionary does not list ("V. H. " in AEL. V. H. X 13)."""
    toks = [(m.group(0), m.start()) for m in re.finditer(r"\S+", locus)]
    for i, (tok, s) in enumerate(toks):
        core = tok.strip(".,;:()[]")
        nxt = toks[i + 1][0] if i + 1 < len(toks) else ""
        if re.search(r"\d", tok) or re.fullmatch(r"[IVXLC]{2,}", core) or tok == "p." or (
                len(core) == 1 and core.isupper() and re.match(r"^\*?\d", nxt)):
            return locus[:s]
    return ""


def _same_place(locus: str) -> str:
    """Step 2: the citation above without its own trailing apparatus."""
    parts = _locus_parts(locus)
    return locus[:parts[-1].end] if parts else locus


def _level_uncertain(base: str, new: str) -> bool:
    """Review finding 1: a dash that opens with two places ("152. 153") and
    prints no higher level of its own could replace the last number of the
    citation above ("VI 151, 2" -> "VI 151, 152. 153") or the last two
    ("VI 152. 153"). Only when the part before the replaced one is not a
    number ("VI 38": a book) can it stand at one level alone."""
    base_parts, new_parts = _locus_parts(base), _locus_parts(new)
    if not base_parts or not new_parts or not new_parts[0].multi:
        return False
    k = len(new_parts)
    return len(base_parts) > k and base_parts[-k - 1].kind == "N"


def _replace_trailing(base: str, new: str) -> str | None:
    """Step 5: `base` with as many trailing parts as `new` has replaced by
    `new`, like for like; None when the parts do not line up. A "p." / "n."
    marker on the first replaced part stays when the new number has none
    ("— —313" after "743 n. 312" = 743 n. 313) -- but not a "p." page, which
    after other numbers is an edition's own count ("II 31, 39 p. 208, 13 W.":
    "— —31, 40" must not become "p. 31, 40")."""
    base_parts, new_parts = _locus_parts(base), _locus_parts(new)
    if not base_parts or not new_parts or len(new_parts) > len(base_parts):
        return None
    k = len(new_parts)
    if [p.kind for p in base_parts[-k:]] != [p.kind for p in new_parts]:
        return None
    first = base_parts[-k]
    if new_parts[0].num_start == new_parts[0].start and first.num_start != first.start:
        if base[first.start:first.num_start].startswith("p."):
            return None  # a page ("p. 208, 13 W.") is another count than the citation's own
        return _book_comma(base[:first.num_start] + new)
    return _book_comma(base[:first.start] + new)


def _book_comma(locus: str) -> str:
    """A filled-in locus prints its book numeral without the comma DK's
    citation above had: "28, 1" after "I, 27, 1 (D. 322)" is "I 28, 1"
    (Heraclitus A8)."""
    return re.sub(r"^([IVXLC]+),(?=\s+\d)", r"\1", locus)


# --- Dash resolution -------------------------------------------------------


_TITLE_BOOK = re.compile(r"\((?:lib|vol)\. ([IVXLC]+)\)|librum ([IVXLC]+)")


def _title_book(dictionary: _Dictionary, key: str, wk: str) -> str | None:
    """The book (or volume) numeral a work title carries: "VI" for Contra
    Celsum (lib. VI), the dictionary's "c. Cels. VI"."""
    m = _TITLE_BOOK.search(dictionary.author_entry(key)["works"].get(wk, {}).get("title", ""))
    return (m.group(1) or m.group(2)) if m else None


def _is_lexicon(dictionary: _Dictionary, key: str) -> bool:
    return _LEXICON_FLAG in dictionary.author_entry(key).get("flags", [])


def _headword(text: str) -> str | None:
    """The lexicon headword a dash stands before: up to the first ':' or '·',
    one to three Greek words ("ἔμβιος: Ἀ.", "μακάρων νήσοισιν: ...", or a
    headword printed alone on the next line)."""
    t = re.sub(r"^[Ss]\.\s*[Vv]\.\s*", "", text.strip())
    m = re.match(r"^([^:·]+?)\s*[:·]", t)
    words = (m.group(1) if m else t).split()
    if not 1 <= len(words) <= 3 or not all(_GREEK_LETTER.search(w) for w in words):
        return None
    if any("..." in w or "…" in w for w in words):
        return None
    return " ".join(words).strip(".,;")


def _match_title(dictionary: _Dictionary, key: str, tokens: list[str]) -> tuple[int, str] | None:
    """A work of `key` at the start of `tokens`; "(Flor.)" in parentheses
    counts as "Flor."."""
    m = dictionary.match_work(key, tokens, 0)
    if m is None and tokens and tokens[0].startswith("(") and tokens[0].endswith(")"):
        m = dictionary.match_work(key, [tokens[0][1:-1]] + tokens[1:], 0)
    return m


def _numbered_work_above(dictionary: _Dictionary, chain: _Chain, tokens: list[str]) -> bool:
    """The numbers after a dash open with a number that names a work of an
    author the run above names (`numbered`, John's ruling 2026-09-29): Gorgias
    B1 "ISOCR. 10, 3 ... 15, 268" -- oration 15, the Antidosis, not the
    Helena's section 15."""
    for src in chain.sources[chain.head_start:]:
        m = _match_title(dictionary, src.author, tokens) if src.author else None
        if m is not None and dictionary.author_entry(src.author)["works"][m[1]].get("numbered"):
            return True
    return False


def _resolve_dash(
    dictionary: _Dictionary,
    chain: _Chain,
    verbatim: str,
    tokens: list[str],
    lemma: str,
    is_last: bool,
    extra_flags: list[str],
) -> tuple[dict, _Source]:
    """Resolve one dash source whose printed text after the dashes is
    `tokens` (rule E); returns the entry and the source the chain moves to.
    `lemma` is the text the dash stands before (a lexicon headword)."""

    def unresolved(why: str | None, author: str | None = None, work: str | None = None):
        flags = extra_flags + ["dash-unresolved"] + ([why] if why else [])
        return _verbatim(verbatim, flags), _Source(author, work, None, like=ante)

    ante: _Source | None = None
    basis: _Source | None = None  # the source the dash builds on

    def filled(key: str, wk: str, locus: str, apparatus: str | None, step: str):
        entry = dictionary.author_entry(key)
        locus = _edition_locus(entry["works"][wk], locus)
        if locus is None:  # the page left the volume the citation above is in
            return unresolved("edition-volume-unknown", key, wk)
        inferred = bool(basis and basis.inferred)
        e = _entry(verbatim, "dash", entry, entry["works"][wk], locus, apparatus,
                   extra_flags + [step] + ([_INFERRED] if inferred else []))
        return e, _Source(key, wk, locus, inferred=inferred)

    if not chain.sources:
        return unresolved(None)
    text = " ".join(tokens)
    if _LOCUS_DOUBT_MARK.search(text):
        # Diels' own doubt about the printed numeral ("(?)", or another
        # editorial doubt mark) -- never expanded on a guess; stays verbatim,
        # flagged locus-doubtful, and the chain treats it as unplaced.
        return _verbatim(verbatim, extra_flags + ["locus-doubtful"]), \
            _Source(None, None, None, like=ante)
    page = _doxographi_page(text)

    # What follows the dashes.
    if not tokens:
        kind = "nothing"
    elif not re.search(r"[A-Za-z0-9Ͱ-Ͽἀ-῿]", text):
        kind = "punct"
    elif tokens[0].casefold() in ("s.", "s.v.") and (tokens[0].casefold() == "s.v." or (
            len(tokens) > 1 and tokens[1].casefold() == "v.")):
        kind = "sv"
    elif not _LOCUS_START.match(tokens[0]) or _numbered_work_above(dictionary, chain, tokens):
        kind = "title"
    else:
        kind = "locus"

    if kind == "title":  # step 3 (and step 1's title exception)
        folded = [t.casefold() for t in tokens]
        if any(tuple(folded[:len(seq)]) == seq for seq in _DASH_WORK_EXCLUDED):
            return unresolved("dash-work-excluded")
        for src in reversed(chain.sources[chain.head_start:]):
            m = _match_title(dictionary, src.author, tokens) if src.author else None
            if m is not None:
                break
        else:
            return unresolved("dash-work-not-in-dictionary")
        key, (wspan, wk) = src.author, m
        ante = src if src.work == wk else None
        basis = src
        work = dictionary.author_entry(key)["works"][wk]
        includes = bool(work.get("locus_includes_work"))
        columns = _column_letters(dictionary, key, wk)
        locus_tokens = tokens if includes else tokens[wspan:]
        if work.get("locus_as_printed"):
            locus, apparatus = _as_printed(locus_tokens, is_last)
        else:
            rest = _truncate_locus_ex(locus_tokens, columns)[1]
            if not includes and rest and _has_locus(rest):
                return unresolved("dash-locus-unclear", key, wk)
            locus, apparatus = _locus_fields(locus_tokens, not includes, is_last, columns)
            if _lost_numbers(locus_tokens, locus, apparatus):
                return unresolved("dash-locus-unclear", key, wk)
        if not re.search(r"\d", locus + (apparatus or "")):
            return unresolved("dash-no-number", key, wk)  # "—Zu" cut at "μ 62 p. 1713"
        owner = _doxographi_owner(dictionary, page) if page is not None else None
        if owner is not None and owner != key:
            return unresolved("dash-doxographi-mismatch")
        return filled(key, wk, locus, apparatus, "dash-e3")

    # Steps 2, 4, 5: whose citation the dash repeats.
    if page is not None:  # step 1's "(D. NNN)" exception
        owner = _doxographi_owner(dictionary, page)
        if owner is None:
            return unresolved("doxographi-owner-unknown")
        for ante in reversed(chain.sources):
            if ante.foreign:
                return unresolved("dash-doxographi-mismatch")
            if ante.author == owner:
                break
        else:
            return unresolved("dash-doxographi-mismatch")
    else:
        ante = chain.sources[-1]
        head_src = next((s for s in reversed(chain.sources) if s.origin == "head"), None)
        if ante.origin == "passage" and (ante.author != chain.last_head_author() or (
                kind == "locus" and head_src is not None and ante.work != head_src.work)):
            # Another author's source, or for a place (not a lexicon's dash)
            # another work of his, named in the passage since the heading
            # (Zeno A25 "Top. Θ 8. 160b 7" after the Physics): which one the
            # dash repeats is not printed, unless only one fits it.
            ante = _only_fitting_book(chain, tokens) if kind == "locus" else None
            if ante is None:
                return unresolved("dash-antecedent-uncertain")
    if ante.author is None or ante.work is None:
        return unresolved("dash-antecedent-unresolved")
    key, wk = ante.author, ante.work
    basis = ante

    if kind in ("nothing", "sv") and _is_lexicon(dictionary, key):  # step 2, lexicon
        word = _headword(lemma)
        if word is None:
            return unresolved("dash-headword-unclear", key, wk)
        return filled(key, wk, f"s.v. {word}", None, "dash-e2")
    if kind == "nothing":  # step 2
        if ante.locus is None:
            return unresolved("dash-antecedent-unresolved", key, wk)
        return filled(key, wk, _same_place(ante.locus), None, "dash-e2")
    if kind in ("punct", "sv"):
        return unresolved("dash-no-number", key, wk)

    if len(tokens) == 1 and re.fullmatch(r"\(\d+\)", tokens[0]):
        # A section number in parentheses, alone: Democritus B119 "— —(5)"
        # after B118's "... XIV 27, 4" is section 5 (step 5).
        tokens = [tokens[0][1:-1]]
    columns = _column_letters(dictionary, key, wk)
    locus_tokens, rest = _truncate_locus_ex(tokens, columns)
    if rest and _has_locus(rest):
        return unresolved("dash-locus-unclear", key, wk)
    locus, apparatus = _locus_fields(tokens, True, is_last, columns)
    if _lost_numbers(tokens, locus, apparatus):
        return unresolved("dash-locus-unclear", key, wk)
    parts = _locus_parts(locus)
    if not parts:
        return unresolved("dash-locus-unparsed", key, wk)
    if parts[0].kind == "B":  # step 4
        title_book = _title_book(dictionary, key, wk)
        if title_book is not None:
            # Review finding 4: the work title already carries the book
            # ("Contra Celsum (lib. VI)"); print it once, as the direct head
            # does, and never under another book's title.
            if locus[parts[0].start:parts[0].end] != title_book:
                return unresolved("dash-book-not-in-title", key, wk)
            locus = locus[parts[0].end:].strip()
            if not re.search(r"\d", locus):
                return unresolved("dash-no-number", key, wk)
            return filled(key, wk, locus, apparatus, "dash-e4")
        if wk == "DEFAULT":
            if ante.prefix is None:
                return unresolved("dash-antecedent-unresolved", key, wk)
            if re.search(r"[A-Za-z]", ante.prefix):
                locus = ante.prefix + locus
        return filled(key, wk, locus, apparatus, "dash-e4")
    if ante.locus == "" and ante.preserved and not apparatus:
        # Step 5 on the place of the text that preserves the passage:
        # Democritus B119 "— —(5)" after B118 "DIONYSIOS, bei Eus. P. E. XIV
        # 27, 4" is "bei Eus. P. E. XIV 27, 5".
        replaced = _replace_trailing(ante.preserved, locus)
        if replaced is None:
            return unresolved("dash-locus-mismatch", key, wk)
        entry, src = filled(key, wk, "", replaced, "dash-e5")
        src.preserved = replaced
        return entry, src
    if ante.locus is None:  # step 5
        # Only the shape of the citation above is known: a dash that
        # replaces every part of it is still complete ("—20." after "—.").
        if ante.prefix is None or ante.shape != [p.kind for p in parts]:
            return unresolved("dash-antecedent-unresolved", key, wk)
        return filled(key, wk, ante.prefix + locus, apparatus, "dash-e5")
    if _level_uncertain(ante.locus, locus):
        return unresolved("dash-level-uncertain", key, wk)
    replaced = _replace_trailing(ante.locus, locus)
    if replaced is None:
        return unresolved("dash-locus-mismatch", key, wk)
    return filled(key, wk, replaced, apparatus, "dash-e5")


def _only_fitting_book(chain: _Chain, tokens: list[str]) -> "_Source | None":
    """Rule E step 4 when a source named in the passage stands between the
    dash and the heading above it: a dash that opens with a book numeral
    prints a whole place, and it repeats the one source since that heading
    whose place has the same parts -- Democritus A152 "— —XII 17" (book,
    number) after A151's "— —XII 16" (Aelian) and the passage's Hippocrates
    ("31"), pseudo-Aristotle ("10, 14. 892a 38") and Aristotle ("Β 8. 747a
    29"). None when no source or more than one fits."""
    parts = _locus_parts(" ".join(_truncate_locus(tokens)))
    if not parts or parts[0].kind != "B":
        return None
    shape = [p.kind for p in parts]
    fits = [s for s in chain.sources[chain.head_start:]
            if s.author and s.work and s.locus is not None and s.shape == shape]
    if len({(s.author, s.work) for s in fits}) != 1:
        return None
    return fits[-1]


# Diels, Doxographi Graeci (1879). Pages before 267 are the prolegomena,
# which discuss Cicero, Censorinus and others (Democritus A138 "CIC. de div.
# II 58, 120" -> "— —I 3, 5 (D. 224)" is still Cicero), so such a page
# decides nothing. Any later page selects an author only when the heads DK
# prints with a page show it is his (review finding 2): the page table
# (sources/dk-citations/doxographi-pages.json, built by
# pipeline/tools/build_doxographi_pages.py from the explicit heads) owns a
# page for an author when the nearest printed pages at or below and at or
# above it are his alone.
_PROLEGOMENA_END = 267


def _doxographi_page(text: str) -> int | None:
    """The "(D. NNN)" page a dash prints, when it can point away from the
    last author named (not a prolegomena page)."""
    m = re.search(r"\(D\.\s*(\d+)", text)
    if m is None or int(m.group(1)) < _PROLEGOMENA_END:
        return None
    return int(m.group(1))


def _doxographi_owner(dictionary: _Dictionary, page: int) -> str | None:
    """The author key the page table shows owning `page`, else None."""
    pages = dictionary.doxographi_pages
    i = bisect.bisect_left(pages, (page,))
    above = pages[i] if i < len(pages) else None
    below = above if above is not None and above[0] == page else (pages[i - 1] if i > 0 else None)
    if below is None or above is None or len(below[1]) != 1 or below[1] != above[1]:
        return None
    return next(iter(below[1]))


def _lost_numbers(tokens: list[str], locus: str, apparatus: str | None) -> bool:
    """The printed citation has numbers but the locus boundary kept none of
    them ("—Zu μ 62 p. 1713" stops at the Greek μ): not a complete locus."""
    return bool(re.search(r"\d", " ".join(tokens))) and not re.search(
        r"\d", locus + (apparatus or ""))


def _has_locus(tokens: list[str]) -> bool:
    """Numbers or a book numeral before any Greek: a second citation."""
    for tok in tokens:
        if _has_lower_greek(tok):
            return False
        core = tok.strip(".,;:()[]")
        if core[:1].isdigit() or (core and _ROMAN_NUMERAL.match(core)):
            return True
    return False


# --- Adjudicated dash heads -------------------------------------------------


def _load_adjudications() -> dict:
    """John's rulings on dash heads (sources/dk-citations/dash-adjudications.
    json): {work: {column: ruling}}. A ruling's "head" is the whole printed
    dash head it rules on, matched exactly (whitespace aside). Two kinds:
      - a reading (no "type"): "reading" is {"author", "work", "locus",
        "apparatus"?} as citation-dictionary.json keys, or null while the
        ruling is pending (the head stays verbatim, flagged by "pending",
        default "awaiting-adjudication");
      - a correction ("type": "correction"): DK misprinted the locus;
        "printed" is the misprint as it stands in the head, "reading" the
        corrected citation, "readerNote" the note the reader shows after it;
      - a note ("type": "note"): the head, dash or direct, resolves as it
        would, and "readerNote" is shown after it.
    "note" records the ruling for the table's readers, never shown."""
    path = SOURCES_DIR / "dk-citations" / "dash-adjudications.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


# Flags that only a ruling puts on an entry: run() counts a ruling used by them.
_RULING_FLAGS = {"adjudicated", "corrected", "annotated", "awaiting-adjudication", "awaiting-print-check"}


def _same_head(printed: str, ruled: str) -> bool:
    """Review finding 3: a ruling applies to its whole printed head only --
    with or without the quotation's Greek initial after it, which the heads
    of citationHeads leave to the passage (Thales A17b "—II 27, 5 (D. 358)
    Θ.", _cut_greek_initial)."""
    def norm(text: str) -> str:
        return re.sub(r"\s+[Ͱ-Ͽἀ-῿]\.,?$", "", " ".join(_nfc(text).split()))
    return norm(printed) == norm(ruled)


def _adjudicated(
    dictionary: _Dictionary, chain: _Chain, ruling: dict, verbatim: str,
    work_id: str, seg_id: str,
) -> tuple[dict, _Source]:
    reading = ruling.get("reading")
    ante = chain.sources[-1] if chain.sources else None
    if reading is None:
        return (_verbatim(verbatim, [ruling.get("pending", "awaiting-adjudication")]),
                _Source(ante.author if ante else None, ante.work if ante else None, None, like=ante))
    key, wk = reading["author"], reading["work"]
    correction = ruling.get("type") == "correction"

    def moved(why: str) -> ValueError:
        return ValueError(
            f"{work_id}: the adjudication for {seg_id!r} ({verbatim!r}) {why} -- the source "
            f"data moved; re-check the adjudication table")

    if correction:
        # A misprint correction names its author and work itself, so it
        # stands where the chain above is lost (Antiphon B107), but never
        # against a chain that names another source.
        if ruling["printed"] not in verbatim:
            raise moved(f"corrects the printed {ruling['printed']!r}, which the head no longer prints")
        if ante is not None and ante.author is not None and (ante.author, ante.work) != (key, wk):
            raise moved(f"reads it as {key} {wk}, but the citation above it is now "
                        f"{(ante.author, ante.work)}")
    elif not any((s.author, s.work) == (key, wk) for s in chain.sources[chain.head_start:]):
        # A reading names a source the run above names: the last one, or
        # another of the run's sources where it names two (Antiphon B19's
        # Harpocration and Bekker's Anecdota: John's TLG lookup of 2026-09-27
        # says which lexicon each dash after it repeats).
        raise moved(f"reads it as {key} {wk}, but the citation above it is now "
                    f"{(ante.author, ante.work) if ante else None}")
    entry = dictionary.author_entry(key)
    e = _entry(verbatim, "dash", entry, entry["works"][wk], reading["locus"],
               reading.get("apparatus"), ["corrected" if correction else "adjudicated"])
    if correction:
        e["note"] = ruling["readerNote"]
    return e, _Source(key, wk, reading["locus"])


# --- Heads ------------------------------------------------------------------

_DK_CROSS_REFERENCE = re.compile(r"""
    \[\s*
    (?:
        (?:(?:vgl\.?|s\.|cf\.)\s*)?
        (?:(?:[1-9]|[1-8][0-9]|90)\s+)?
        [ABCΑΒΓ]\s*\d+\s*[a-z]?(?:\s*[—–-]\s*\d+\s*[a-z]?)?
        (?:\s*(?:[,.;]|u\.|und)\s*(?:(?:vgl\.?|s\.|cf\.)\s*)?
           (?:[ABCΑΒΓ]\s*)?\d+\s*[a-z]?(?:\s*[—–-]\s*\d+\s*[a-z]?)?)*
        (?:\s+[IVXLC]+\s+\d+\s*,\s*\d+)?
        (?:\s+Ende)?
      | (?:vgl\.?|s\.|cf\.)\s*\d+\s*,\s*\d+
    )
    \s*\]
    (?:[\s.,;:!?…·"'’”»)]|\(\d+\))*
""", re.VERBOSE)


def _foreign_author_head(tokens: list[str]) -> bool:
    """An all-caps author name the dictionary does not know ("ACHILL.",
    "LYS.", "APULEIUS"): not a Roman numeral, at least two capitals."""
    t = tokens[0].rstrip(".,:;")
    return bool(re.fullmatch(r"[A-ZÄËÏÖÜ]{2,}", t)) and not _ROMAN_NUMERAL.match(t)


def _same_place_above(dictionary: _Dictionary, chain: _Chain, key: str,
                      entry: dict, wk: str) -> tuple[dict, str]:
    """A locus DK prints as "a. O." (am angegebenen Ort, at the place
    cited) is the place of the last source of the same author, in his work
    there unless the head names another: Critias B40 "GAL. a. O." after
    B39's "GAL. comment. in Hippocr. de offic. I 1". Left as printed when
    no such place is known."""
    if entry["resolution"] != "direct" or entry["locus"] != "a. O.":
        return entry, wk
    above = next((s for s in reversed(chain.sources) if s.author == key), None)
    if above is None or above.work is None or above.locus is None or wk not in ("DEFAULT", above.work):
        return entry, wk
    author = dictionary.author_entry(key)
    same = _entry(entry["verbatim"], "direct", author, author["works"][above.work],
                  above.locus, None, ["same-place"])
    return same, above.work


def _commented_passage_above(dictionary: _Dictionary, chain: _Chain, key: str,
                             entry: dict, wk: str) -> tuple[dict, str]:
    """A commentator's head that names no title, DK's "z. d. St." (zu der
    Stelle, on this passage), "dazu" or "ad h. c." or a bare page after
    another's: his commentary on the passage cited above (John's ruling,
    2026-09-29). The first head above that is no commentary decides, when
    the work's `on_passage_above` lists its author and title; the marker
    then leaves the locus. Anything else stays as resolved."""
    table = dictionary.author_entry(key)["works"].get(wk, {}).get("on_passage_above")
    if entry["resolution"] != "direct" or not table:
        return entry, wk
    above = None
    for src in reversed(chain.sources):
        # A heading later in a line counts as a passage source; both count.
        if src.author is not None and "title-is-commentary" in dictionary.author_entry(src.author)["flags"]:
            continue  # Empedocles B108: Simplicius' "z. d. St." after Philoponus' is on the same passage
        above = src
        break
    if above is None or above.author is None or above.work is None:
        return entry, wk
    title = dictionary.author_entry(above.author)["works"][above.work]["title"]
    target = table.get(f"{above.author}:{title}")
    if target is None:
        return entry, wk
    locus = entry["locus"]
    if wk != "DEFAULT":
        marker = r"\s*".join(re.escape(t) for t in wk.split())
        locus = re.sub(r"^" + marker + r"\s*", "", locus, flags=re.IGNORECASE)
    author = dictionary.author_entry(key)
    return _entry(entry["verbatim"], "direct", author, author["works"][target], locus,
                  entry.get("apparatus"), ["commented-passage-above"]), target


# A locus that is nothing but DK's lexicon marker "s. v."/"S. V." (sub
# voce): the head-extraction rule cut the headword after it, still to come.
_SV_BARE_LOCUS = re.compile(r"[Ss]\.\s*[Vv]\.")

# A lexicon head DK gives no locus at all (a bare abbreviation like "HES."
# mid-line, or a column's own bare "HARPOCR."), immediately followed on the
# same printed line by its own entry -- one word, then ":"/"·" -- with no "s.
# v." marker at all (Antiphon B43 "HES. ἄβιος : πλούσιος ...", the headword
# right after HARPOCR.'s own "ἄβιος" entry for the same word; John/GPT-6-Sol
# review, 2026-09-27).
_LEMMA_COLON_WORD = re.compile(r"\s*[A-Za-zͰ-Ͽἀ-῿]+\s*[:·]")

# A display line that is nothing but one bare word: a lexicon headword DK
# prints alone on its own line, split from the ":"/"·" that introduces its
# entry, which the digitized text lands on a LATER line still (Antiphon
# B43's "ἄβιος" is one display line, its "': πλούσιος ...'" the next).
_BARE_WORD_LINE = re.compile(r"[A-Za-zͰ-Ͽἀ-῿]+")

# A headword DK quotes as the entry's first word with no ":"/"·" after it:
# before a period ("SUID. Καλλίμαχος. Πίναξ ...", Democritus A32), DK's
# ellipsis ("ETYM. GENUIN. γλαύξ ... ἔστι", A157) or a bracketed reference
# ("SUID. Δημόκριτος [A 2; II 85, 2]", A31); or the name a Suda life opens
# with, its father's name after it ("SUIDAS Ἀναξιμένης Εὐρυστράτου",
# Anaximenes A2). Never DK's one-letter initial for the philosopher ("SUID.
# Ἀ....", "HARPOCR. Ἀ. σοφιστὴς"). Grok head check, 2026-09-28.
_LEMMA_WORD = re.compile(r"\s*([Ͱ-Ͽἀ-῿]{2,})(?:\.(?!\.)|\s+(?:\.\.\.|…|\[))")
_LEMMA_NAME = re.compile(r"\s*([Ͱ-Ͽἀ-῿]{2,})\s+[Ͱ-Ͽἀ-῿]")


def _entry_headword(lemma: str) -> str | None:
    """The headword a lexicon head with no locus quotes first (_LEMMA_COLON_WORD,
    _LEMMA_WORD, _LEMMA_NAME), or None."""
    if _LEMMA_COLON_WORD.match(lemma):
        return re.match(r"\s*([A-Za-zͰ-Ͽἀ-῿]+)", lemma).group(1)
    word = _LEMMA_WORD.match(lemma)
    if word:
        return word.group(1)
    name = _LEMMA_NAME.match(lemma)
    if name and name.group(1)[0].isupper() and name.group(1)[1:].islower():
        return name.group(1)
    return None


def _lemma_lookahead(lines: list[dict], li: int) -> str:
    """The lemma right after the head on line `li` when its own line has
    nothing left (`resolve_located_segments`'s "rest"): normally just the
    next display line, but one further line too when that next line is
    nothing but a bare headword (`_BARE_WORD_LINE`) with no ':'/'·' of its
    own -- so `_resolve_head`'s lexicon-headword completion can see the
    colon that confirms it, even though DK's own line split put it out of
    reach (2026-09-27)."""
    if li + 1 >= len(lines):
        return ""
    lemma = _nfc(lines[li + 1].get("text", ""))
    if li + 2 < len(lines) and _BARE_WORD_LINE.fullmatch(lemma.strip()):
        lemma += " " + _nfc(lines[li + 2].get("text", ""))
    return lemma


def _resolve_head(
    dictionary: _Dictionary, head: str, work_id: str, seg_id: str,
    chain: _Chain | None = None, lemma: str = "", ruling: dict | None = None,
) -> list[dict]:
    """Resolve one extracted head into >=1 expandedCitation entries, updating
    the chain. Returns [] when the head is not a citation head (leading token
    matches nothing). With no `chain`, the head is resolved as if nothing
    preceded it. `ruling` is an adjudication for this column's dash head."""
    if chain is None:
        chain = _Chain()
    h = _nfc(head).strip()
    dash = _DASH_PREFIX.match(h)
    misparse = False
    if dash is None:
        tokens = re.findall(r"\S+", h)
        if not tokens:
            return []
        if dictionary.match_author(tokens, 0, lemma) is None:
            # Not a resolvable author at the head start. A dash-misparse token
            # (a work title or Latin word whose dash the census lost) goes
            # through the dash logic and is never looked up as an author;
            # honest verbatim for unmappable / bracketed heads other than DK
            # cross-references; anything else
            # is "not a citation head" -> no entry, though an all-caps name
            # the dictionary lacks still names the source.
            if dictionary.is_misparse(tokens[0]):
                misparse = True
            elif _DK_CROSS_REFERENCE.fullmatch(h):
                return []
            elif dictionary.is_unmappable(h, tokens[0]) or tokens[0].startswith("["):
                return [_verbatim(head, ["unmappable"])]
            else:
                if _foreign_author_head(tokens):
                    chain.push_head([_Source(None, None, None, foreign=True)])
                return []
    if dash is not None or misparse:
        prefix = h[:dash.end()] if dash else ""
        tokens = re.findall(r"\S+", h[dash.end():] if dash else h)
        # Later explicit authors in the same head split off as their own
        # sources; the first token after the dash is never an author.
        later = _split_sources(dictionary, tokens, 1, lemma)
        end = later[0][0] if later else len(tokens)
        verbatim = (prefix + " ".join(tokens[:end])).strip()
        if ruling is not None and _same_head(verbatim, ruling["head"]) and ruling.get("type") == "note":
            # The reading stands; the ruling only adds the reader's note
            # (Gorgias B26 keeps DK's 758 and gives the modern line numbers;
            # John's ruling, 2026-09-29).
            entry, src = _resolve_dash(dictionary, chain, verbatim, tokens[:end], lemma,
                                       not later, ["dash-misparse"] if misparse else [])
            entry["note"] = ruling["readerNote"]
            entry["flags"].append("annotated")
        elif ruling is not None and _same_head(verbatim, ruling["head"]):
            entry, src = _adjudicated(dictionary, chain, ruling, verbatim, work_id, seg_id)
        else:
            entry, src = _resolve_dash(dictionary, chain, verbatim, tokens[:end], lemma,
                                       not later, ["dash-misparse"] if misparse else [])
        chain.sources.append(src)
        entries = [entry]
    else:
        later = _split_sources(dictionary, tokens, 0, lemma)
        entries = []
    head_sources: list[_Source] = []
    for idx, (start, span, key) in enumerate(later):
        is_last = idx + 1 >= len(later)
        end = len(tokens) if is_last else later[idx + 1][0]
        if key == _AMBIGUOUS:
            # "HEROD." with neither a book + chapter nor a Herodian title
            # after it: as printed; like an author the dictionary does not
            # know, it names a source a later dash cannot build on.
            entries.append(_verbatim(" ".join(tokens[start:end]), ["ambiguous-abbrev"]))
            head_sources.append(_Source(None, None, None, foreign=True))
            continue
        entry, wk = _resolve_source(dictionary, key, span, tokens, start, end, work_id, seg_id, is_last)
        entry, wk = _same_place_above(dictionary, chain, key, entry, wk)
        entry, wk = _commented_passage_above(dictionary, chain, key, entry, wk)
        locus = entry.get("locus") or ""
        # A bracket group alone is a note, not a place: "HARPOCR. [vgl. PHOT.
        # A Reitzenst. 37, 18]" (Antiphon B22) names its headword too.
        note = locus if re.fullmatch(r"\[[^\[\]]*\]", locus) else None
        placeless = not locus or note is not None
        colon_head = placeless and tokens[end - 1].endswith(":")
        bare_sv = bool(_SV_BARE_LOCUS.fullmatch(locus))
        headword = _entry_headword(lemma) if placeless and not colon_head else None
        if is_last and entry["resolution"] == "direct" and (colon_head or bare_sv or headword) \
                and _is_lexicon(dictionary, key):
            # "SUID: Ἡράκλειτος ...": DK quotes the entry; its headword is
            # the first word after the colon (Heraclitus A1a). "SUID. s. v.
            # ἀγχιβατεῖν ...": the head-extraction rule ends a head at the
            # first lowercase Greek, so a lexicon's own headword right after
            # a bare "s. v."/"S. V." is cut from the head and left in
            # `lemma`, the text that follows it on the same printed line
            # (Heraclitus B122; GPT-6-Sol review, 2026-09-27). A bare head
            # with no locus AND no "s. v." marker at all, mid-line right
            # before its own "word :" entry, reads the same way (Antiphon
            # B43's "HES.", 2026-09-27).
            word = headword or (re.match(r"\s*([A-Za-zͰ-Ͽἀ-῿]+)", lemma) or [None, None])[1]
            if word:
                entry["locus"] = f"s.v. {word}"
                if note:
                    entry["apparatus"] = " ".join(filter(None, [note, entry.get("apparatus")]))
                # _entry() picked the empty-locus fallback title (`bare_title`,
                # e.g. the Suda's own "Lexicon") before this locus existed; a
                # real locus found here means it no longer applies.
                work = dictionary.author_entry(key)["works"][wk]
                if work.get("bare_title") and entry["work"]["title"] == work["bare_title"]:
                    entry["work"]["title"] = work["title"]
        inferred = dictionary.is_ambiguous(tokens[start:start + span])
        if inferred:
            entry["flags"].append(_INFERRED)
        entries.append(entry)
        head_sources.append(_Source(key, wk, entry.get("locus"), inferred=inferred))
        apparatus = entry.get("apparatus") or ""
        if entry.get("locus") == "" and apparatus.split()[:1] and apparatus.split()[0].casefold() in _PRESERVED_IN:
            head_sources[-1].preserved = apparatus
    if head_sources:
        chain.push_head(head_sources)
    if (dash is None and not misparse and entries and ruling is not None
            and ruling.get("type") == "note" and _same_head(h, ruling["head"])):
        # A note ruling on a direct head: the reading stands, the reader's
        # note follows it (Thales A11a keeps DK's 30, Himerius, with a note
        # naming Colonna's oration 28; John's ruling, 2026-09-29).
        entries[-1]["note"] = ruling["readerNote"]
        entries[-1]["flags"].append("annotated")
    return entries


# --- Sources printed inside a passage --------------------------------------

_CONTINUATION_TOKEN = re.compile(r"^(?:[IVXLC]+|\d+[a-z]?)[.,;]?$")


def _scan_passage(dictionary: _Dictionary, chain: _Chain, text: str) -> None:
    """Rule E step 1 counts every source named, including those DK prints
    INSIDE a passage after its head. Nothing here is emitted; the chain
    learns (a) each all-caps author variant outside brackets (mixed-case ones
    like "Plat." also occur as words in Latin quotations), (b) each dash
    fused to a locus or title ("—22, 2 (D. 352)"), resolved by rule E, and
    (c) each undashed continuation locus -- numbers before a "(D. NNN)" page,
    or an "N, N" pair opening a sentence -- which moves the last source on
    like a dash. A bare "—" is punctuation in the Greek."""
    tokens = re.findall(r"\S+", _nfc(text))
    depth = 0
    floor = 0  # tokens before this belong to a source already read
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        span = 1
        if depth == 0:
            m = dictionary.match_author(tokens, i)
            if m is not None and not any(c.islower() for c in "".join(tokens[i:i + m[0]])) \
                    and (i == 0 or _is_new_source_at(tokens, i)):
                if i and tokens[i - 1].casefold() == "dagegen":
                    # "Dagegen HARPOCR. ..." (by contrast): a comparison DK
                    # adds to the passage, not the next source (Antiphon B99,
                    # before B100's "—II 123" in Pollux).
                    span = max(1, len(_cite_tokens(tokens, i)))
                else:
                    span = _passage_citation(dictionary, chain, tokens, i)
                floor = i + span
            elif _ATTACHED_DASH.match(tok) or (
                    tok in ("—", "–") and i + 1 < len(tokens) and _ATTACHED_DASH.match(tokens[i + 1])):
                span = _passage_dash(dictionary, chain, tokens, i)
                floor = i + span
            elif tok.startswith("(D.") or (
                    re.match(r"^\d+[a-z]?,$", tok) and i + 1 < len(tokens)
                    and re.match(r"^\d+[a-z]?[.,;·]?$", tokens[i + 1])
                    and (i == floor or tokens[i - 1].endswith((".", "·", ";")))):
                span = _passage_continuation(dictionary, chain, tokens, i, floor)
                floor = i + span
        for t in tokens[i:i + span]:
            depth = max(0, depth + t.count("[") + t.count("(") - t.count("]") - t.count(")"))
        i += span


def _cite_tokens(tokens: list[str], i: int) -> list[str]:
    head = _extract_head(" ".join(tokens[i:]))
    return re.findall(r"\S+", head) if head else tokens[i:i + 1]


def _passage_citation(dictionary: _Dictionary, chain: _Chain, tokens: list[str], i: int) -> int:
    cite = _cite_tokens(tokens, i)
    starts = _split_sources(dictionary, cite, 0)
    for idx, (start, span, key) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(cite)
        if key == _AMBIGUOUS:
            chain.sources.append(_Source(None, None, None, "passage", foreign=True))
            continue
        wk, locus, _ = _work_and_locus(dictionary, key, span, cite, start, end, idx + 1 >= len(starts))
        chain.sources.append(_Source(key, wk, locus if wk else None, "passage",
                                     inferred=dictionary.is_ambiguous(cite[start:start + span])))
    return max(1, len(cite))


def _passage_dash(dictionary: _Dictionary, chain: _Chain, tokens: list[str], i: int) -> int:
    cite = _cite_tokens(tokens, i)
    joined = " ".join(cite)
    dash = _DASH_PREFIX.match(joined)
    rest_full = re.findall(r"\S+", joined[dash.end():]) if dash else cite
    later = _split_sources(dictionary, rest_full, 1)
    rest = rest_full[:later[0][0]] if later else rest_full
    _, src = _resolve_dash(dictionary, chain, joined, rest, "", True, [])
    src.origin = "passage"
    chain.sources.append(src)
    # A later author in the same citation is left for the scanner to read.
    return max(1, len(cite) - (len(rest_full) - len(rest)))


def _passage_continuation(
    dictionary: _Dictionary, chain: _Chain, tokens: list[str], i: int, floor: int,
) -> int:
    """An undashed locus that continues the last source: the locus tokens
    ending before a "(D." at i (or starting with the "N, N" pair at i), plus
    a following "(D. ...)" group."""
    if tokens[i].startswith("(D."):
        j = i
        while j > floor and _CONTINUATION_TOKEN.match(tokens[j - 1]):
            j -= 1
        locus = tokens[j:i]
        k = i
    else:
        locus = []
        k = i
        while k < len(tokens) and _CONTINUATION_TOKEN.match(tokens[k]):
            locus.append(tokens[k])
            k += 1
    if k < len(tokens) and tokens[k].startswith("(D."):
        close = k
        while close < len(tokens) and ")" not in tokens[close]:
            close += 1
        group = tokens[k:close + 1]
        k = close + 1
    else:
        group = []
    if not chain.sources:
        return max(1, k - i)
    if not locus:
        last = chain.sources[-1]
        chain.sources.append(_Source(last.author, last.work, None, "passage", like=last))
        return max(1, k - i)
    _, src = _resolve_dash(dictionary, chain, " ".join(locus + group), locus + group, "", True, [])
    src.origin = "passage"
    chain.sources.append(src)
    return max(1, k - i)


# --- Head extraction per segment --------------------------------------------


def _dash_head(text: str) -> str:
    """The head of a line that opens with a dash but has no head by the
    prose-flow rule: the dashes alone ("—", "— —" before a headword or the
    fragment itself), or the dashes plus a Greek work title and the Latin
    citation after it (Democritus B128 "—π. καθολ. προσ. bei Theogn. p. 79
    [I 355, 19 L.]")."""
    dash = _DASH_PREFIX.match(text)
    rest = text[dash.end():]
    tokens = re.findall(r"\S+", rest)
    if tokens and all(_is_pure_punct_token(t) for t in tokens):
        return text.strip()  # "—." (Democritus B53a): the number is missing
    n = 0
    while n < len(tokens) and n < 4 and _has_lower_greek(tokens[n]):
        n += 1
    if 0 < n < len(tokens) and re.search(r"[A-Za-z]", tokens[n]) and not _GREEK_LETTER.search(tokens[n]):
        after = _extract_head(" ".join(tokens[n:]))
        if after:
            return (text[:dash.end()] + " ".join(tokens[:n]) + " " + after).strip()
    return text[:dash.end()].strip()


def _herodian_locus_start(tok: str) -> bool:
    """Whether `tok`, the token right after a Herodian Greek title's words,
    can open the locus that follows it: a number, "p.", a bracket, or "bei"
    (the German note that preserves who quotes Herodian, "bei Eustath. ...").
    Anything else -- an author abbreviation like "PLUT.", or a Greek word --
    ends the head with no locus (2026-09-24 tightening: `_is_head_material_
    token` alone wrongly let a following source's own head, "τὸ PLUT. de
    aud. ...", read as Herodian's locus)."""
    return tok == "bei" or bool(re.match(r"\d|[([]|p\.$", tok))


def _greek_title_tail(rest: str) -> int:
    """How much of `rest`, the text after a head, still belongs to it when
    it opens with a Greek title in "π." (Περὶ ...): the prose-flow rule
    ends the head at the first lowercase Greek, so "HERODIAN. π. μον. λέξ.
    p. 41, 5" would stop at "HERODIAN." (content review item 6). The title
    is up to four Greek words; the locus after it is head material up to the
    Greek text, where a lone Greek letter before a number is a Homer book
    ("zu ξ 428"). With no locus, only the period-marked title words count
    ("π. μον. λέξ. τὸ δὲ"). Returns the length of that stretch, else 0."""
    toks = [(m.group(0), m.end()) for m in re.finditer(r"\S+", rest)]
    if not toks or toks[0][0] != "π.":
        return 0
    n = 1
    while n < len(toks) and n < 4 and _has_lower_greek(toks[n][0]):
        n += 1
    if n >= len(toks) or not _herodian_locus_start(toks[n][0]):
        n = 1
        while n < len(toks) and n < 4 and _has_lower_greek(toks[n][0]) and toks[n][0].endswith("."):
            n += 1
        return toks[n - 1][1]
    end = toks[n - 1][1]
    i = n
    while i < len(toks):
        tok = toks[i][0]
        book = len(tok) == 1 and _is_greek(tok) and i + 1 < len(toks) and toks[i + 1][0][:1].isdigit()
        if not (_is_head_material_token(tok) or book):
            break
        end = toks[i][1]
        i += 1
    return end


def _greek_book_title_tail(rest: str) -> int:
    """How much of `rest`, the text after a head, still belongs to it when
    it opens with a book's Greek title in full, "Περὶ ..." (up to four
    words), and a place follows the title -- a number, a bracket, or a "bei"
    note: Antiphon B44a "IAMBL. Ep. Περὶ ὁμονοίας [Stob. II 33, 15] ἡ
    ὁμόνοια ...", the letter and Stobaeus' place. The title, then the head
    material after it up to the Greek text; 0 when no place follows (the
    Greek is then the quotation)."""
    toks = [(m.group(0), m.end()) for m in re.finditer(r"\S+", rest)]
    if not toks or toks[0][0] != "Περὶ":
        return 0
    n = 1
    while n < len(toks) and n < 4 and _GREEK_LETTER.search(toks[n][0]) and not re.search(r"[\[\]()]", toks[n][0]):
        n += 1
    if n >= len(toks) or not _herodian_locus_start(toks[n][0]):
        return 0
    end = toks[n - 1][1]
    depth = 0
    for tok, tok_end in toks[n:]:
        if not depth and (not _is_head_material_token(tok) or re.fullmatch(r"\(\d+\)", tok)):
            break  # the quotation, or DK's section label that opens it ("(18)")
        depth = max(0, depth + tok.count("(") + tok.count("[") - tok.count(")") - tok.count("]"))
        end = tok_end
    return end


# "ἀπὸ τοῦ α τῆς Φιλολόγου ἀκροάσεως b. Eus. P. E. X 3, 25" (Protagoras B2):
# DK names the book and the work in Greek, then where the passage is kept.
_GREEK_BOOK_OF_TITLE = re.compile(r"\s*ἀπὸ τοῦ [α-ω] τῆς(?: [Ͱ-Ͽἀ-῿]+){1,3}(?=\s+(?:b\.|bei)\s)")


def _greek_book_of_title_tail(rest: str) -> int:
    """How much of `rest`, the text after a head, still belongs to it when
    it opens with "ἀπὸ τοῦ <book> τῆς <title>" and a "b."/"bei" note: the
    phrase, then the head material of the note up to the Greek text. 0
    otherwise (2026-09-29)."""
    m = _GREEK_BOOK_OF_TITLE.match(rest)
    if not m:
        return 0
    end = m.end()
    for tok in re.finditer(r"\S+", rest[m.end():]):
        if not _is_head_material_token(tok.group()):
            break
        end = m.end() + tok.end()
    return end


def _homer_book_tail(rest: str) -> int:
    """How much of `rest`, the text after a head, still belongs to it when
    it opens with an Odyssey book letter, lower-case Greek, before a number:
    "EUSTATH. Zu θ 376 p. 1601, 25 καὶ ...", "—Zu μ 62 p. 1713 ἄλλοι ..."
    (the prose-flow rule ends the head at the letter). The letter, then the
    head material after it up to the Greek text; 0 otherwise."""
    toks = [(m.group(0), m.end()) for m in re.finditer(r"\S+", rest)]
    if len(toks) < 2 or not re.fullmatch(r"[α-ω]", toks[0][0]) or not toks[1][0][:1].isdigit():
        return 0
    end = toks[0][1]
    for tok, tok_end in toks[1:]:
        if not _is_head_material_token(tok):
            break
        end = tok_end
    return end


def _segment_context(seg: dict) -> list[tuple[str | None, str, str, bool]]:
    """(head, passage, lemma, scan) for each line that can carry a head or a
    passage, document order. A head is (a) the source-citation head at the
    start of a maximal context run (DK prints the apparatus citation there),
    or the dashes that open such a run with no Latin head after them; (b) a
    dash-opened head on a later line of a context run ("—*48." in Democritus
    B82); (c) a dash line the spine marks as text (Heraclitus B42 "— —τόν τε
    Ὅμηρον"). The Reader counts run starts by the same three rules
    (Reader.svelte runStartLines). The passage is the rest of a context line,
    scanned for sources named inside it (`scan`); `lemma` is the text a
    lexicon dash stands before -- the rest of its line, else the next line."""
    pieces: list[tuple[str | None, str, str, bool]] = []
    prev_role = None
    lines = seg.get("lines", [])
    for idx, line in enumerate(lines):
        role = line.get("role")
        text = _nfc(line.get("text", "")).strip()
        dash = _DASH_PREFIX.match(text)
        head = None
        if role == "context":
            if prev_role != "context":
                head = _extract_head(text) or (_dash_head(text) if dash else None)
                if head and not dash and text.startswith(head):
                    head = text[:len(head) + _greek_title_tail(text[len(head):])].strip()
                if head and text.startswith(head):
                    head = text[:len(head) + _homer_book_tail(text[len(head):])].strip()
            elif dash:
                head = _extract_head(text)
        elif role == "text" and dash:
            head = _extract_head(text) or _dash_head(text)
        if role == "context" or head:
            rest = text[len(head):] if head and text.startswith(head) else ("" if head else text)
            lemma = rest
            if head and not rest.strip() and idx + 1 < len(lines):
                lemma = _nfc(lines[idx + 1].get("text", ""))
            pieces.append((head, rest, lemma, role == "context"))
        prev_role = role
    return pieces


def _segment_heads(seg: dict) -> list[str]:
    """The source-citation heads of a segment, document order."""
    return [head for head, _, _, _ in _segment_context(seg) if head]


# Exact source locations. Offsets count UTF-16 code units, as String.slice and
# token offsets do in the reader. lineIndex disambiguates repeated printed n.
def _utf16_offset(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


# "ebenda" (German: in the same place) -- the source cited just before, at
# the locus printed after it (Empedocles B98 "EBEND. 331, 3" = SIMPL. Phys.
# 331, 3). "vgl." (compare) introduces a cross-reference.
_EBEND = {"ebend.", "ebenda", "ebenda."}
_VGL = {"vgl.", "vgl"}


def _ebend_span(words: list[str], i: int) -> int:
    """The tokens at words[i] that print an "ebenda" head: "EBEND." /
    "Ebend." (1; lower case only after a sentence, not after an abbreviation:
    "PTOLEM. Apparit. epileg. ebenda p. 275, 1" is one citation), or an
    all-caps author abbreviation before it, "AR. ebend." (2, Thales A22). 0
    when there is none, or when no locus follows it."""
    n = 0
    if words[i].casefold() in _EBEND and (
            words[i][0].isupper() or i == 0 or not re.fullmatch(r"[a-z]+\.", words[i - 1])):
        n = 1
    elif i + 1 < len(words) and re.fullmatch(r"[A-ZÄËÏÖÜ]{2,}\.", words[i]) \
            and words[i + 1].casefold() in _EBEND:
        n = 2
    return n if n and i + n < len(words) and _LOCUS_START.match(words[i + n]) else 0


def _dash_names_place(dictionary: _Dictionary, rest: list[str], authors: list[str | None]) -> bool:
    """Whether the words after a dash name a place, as a continuation head
    must: an author, a locus (numbers, a book numeral or letter, "p."),
    "ebenda", or a title the dictionary gives one of `authors` (the sources
    the dash can continue). A dash before Greek or Latin prose, or before
    nothing, is punctuation: a change of speaker in a quoted dialogue
    (Philolaus B15 "συγγεγονότες; —Οὐδέν γε σαφές"), or DK's "— Vgl."."""
    if not rest:
        return False
    if dictionary.match_author(rest, 0) or _LOCUS_START.match(rest[0]) or _ebend_span(rest, 0):
        return True
    return any(_match_title(dictionary, a, rest) for a in authors if a and a != _AMBIGUOUS)


def _close_groups(head: str, tail: str) -> str:
    """A bracket or parenthesis opened inside a head closes inside it, even
    around ";" or Greek words: "AËT. III 15, 4 (D. 379; περὶ σεισμῶν γῆς)"
    (Anaxagoras A89), "ACHILL. IS. 24 [p. 55, 24 M; περὶ τοῦ γαλαξίου]"
    (Democritus A91). That is an apparatus group, one that prints Latin or a
    number before any Greek; any other group opens the quotation itself and
    ends the head: "DIODOR. I 39 (... τοῖς μεγίστοις ὄρεσι ...)" (Democritus
    A99). Unchanged when the group does not close in `tail`."""
    opened: list[int] = []
    for pos, ch in enumerate(head):
        if ch in "([":
            opened.append(pos)
        elif ch in ")]" and opened:
            opened.pop()
    if not opened:
        return head
    if not re.match(r"[^Ͱ-Ͽἀ-῿]*?[A-Za-z0-9]", head[opened[0] + 1:]):
        return head[:opened[0]].rstrip()
    depth = len(opened)
    for pos in range(len(head), len(tail)):
        ch = tail[pos]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
            if not depth:
                return tail[:pos + 1]
    return head


def _head_extent(dictionary: _Dictionary, tail: str) -> str:
    """The printed head at the start of `tail` (text from a citation start
    to the next one), or "" when there is none."""
    numbers = _NUMBER_CONTINUATION.match(tail)
    if numbers:
        return numbers.group()  # "28, 1 (D. 358)", not the "Ἀ.," after it
    head = _extract_head(tail) or (_dash_head(tail) if tail.startswith("—") else "")
    if not head:
        return ""
    head = tail[:len(head) + _greek_title_tail(tail[len(head):])].rstrip()
    head = tail[:len(head) + _homer_book_tail(tail[len(head):])].rstrip()
    head = tail[:len(head) + _greek_book_title_tail(tail[len(head):])].rstrip()
    head = tail[:len(head) + _greek_book_of_title_tail(tail[len(head):])].rstrip()
    # A Greek word the head cut in two belongs to the passage, with a dash
    # fused to it: "PLAT. Phaedr. 269 E—Κινδυνεύει" (a change of speaker).
    word = re.search(r"[—–]?[Ͱ-Ͽἀ-῿]+$", head)
    if word and len(head) < len(tail) and _is_greek(tail[len(head)]):
        head = head[:word.start()].rstrip()
    head = _close_groups(_cut_greek_initial(head), tail)
    # An editor's initial then the philosopher's before the Greek: "STOB.
    # Flor. (III) t. 7, 37 H. Z. ὁ Ἐλεάτης" (Zeno A20).
    second = re.search(r"(?<=\d\s[A-Z]\.)\s+[A-Z]\.$", head)  # not "SUID. S. V."
    if second and _has_lower_greek(tail[len(head):len(head) + 4]):
        head = head[:second.start()]
    # A place in the same source after a sentence end is its own head:
    # Democritus A90 "AËT. II 25, 9 (D. 356) s. 59 A 77. 30, 3 (D. 361; ...)".
    for later in re.finditer(r"(?<=[.·;])\s+(?=" + _NUMBER_CONTINUATION.pattern + ")", head):
        before = head[:later.start()].split()
        # Not the head's own locus: "CENSOR. 6, 1 (D. 190;)", "... AËT. II 1, 3".
        if re.search(r"\d", head[:later.start()]) and not dictionary.match_author([_nfc(w) for w in before[-1:]], 0):
            head = head[:later.start()]
            break
    # Section labels belong to the passage, not its citation.
    for mark in re.finditer(r"\s+\(\d+\)(?=\s|$)", head):
        if re.search(r"[.··;:]$", head[:mark.start()].rstrip()):
            head = head[:mark.start()].rstrip()
            break
    # Verse numbers marking which lines of the fragment a further witness
    # attests stand between the two citations, belonging to neither
    # (Empedocles B12 "[ARISTOT.] de MXG 2, 6 p. 975b 1. 1. 2 PHILO de
    # aetern. mundi ...": "1. 2" numbers the verses PHILO's citation attests,
    # not a continuation of ps.-Aristotle's own page; Grok content-check
    # item 11, 2026-09-27). Only after the locus already reached a firm,
    # period-closed end, and only a short run of numbers restarting at 1.
    verse = re.search(r"(?<=[.\u00b7;])\s+(?:1(?:\.\s*[2-9])+)\.?\s*$", head)
    if verse:
        head = head[:verse.start()]
    # The old Greek-only peel swallowed Latin quotations. Use the
    # resolver's work/locus grammar to find their printed boundary.
    matches = list(re.finditer(r"\S+", head))
    words = [_nfc(m.group()) for m in matches]
    sources = _split_sources(dictionary, words, 0) if words else []
    ebend = _ebend_span(words, 0) if words else 0
    count = 0
    firm = False  # the locus came to a firm end with a place after it
    for idx, (source_start, span, key) in enumerate(sources):
        # Each source's locus, not only the last one's: a Latin quotation
        # may stand between two ("SEN. Nat. qu. IV a 2, 17 A. ait ...
        # Dagegen HEROD. II 22", Anaxagoras A91).
        stop = sources[idx + 1][0] if idx + 1 < len(sources) else len(words)
        if key == _AMBIGUOUS:
            count = 0
            continue
        work = dictionary.match_work(key, words, source_start + span)
        prefix = source_start + span + (work[0] if work else 0)
        wk = work[1] if work else "DEFAULT"
        entry = dictionary.author_entry(key)["works"].get(wk, {})
        if not work:
            number = _first_number(words, prefix, stop)
            prefix = prefix if number is None else number
        count = 0
        if not entry.get("locus_as_printed") and not entry.get("locus_includes_work"):
            locus, rest = _truncate_locus_ex(words[prefix:stop], _column_letters(dictionary, key, wk) if entry else False, True)
            count = prefix + len(locus)
            firm = bool(count < stop and rest and re.match(r"\d", words[count]))
            if count < stop and (_ends_locus(words[count]) or firm):
                break  # firm: a closed group and a period, then a place ("CENSORIN. 5, 4 [s. 24 A 13]. 6, 6 ex ...")
    if not sources and ebend:
        count = ebend + len(_truncate_locus_ex(words[ebend:], head=True)[0])
    elif not sources and words:
        # A dash or a title with no author (the source above): its locus
        # from the first number, "—6, 2 sunt qui ..." (Anaxagoras A109),
        # "de divin. I 38, 80 negat enim ...".
        bare = [_DASH_PREFIX.sub("", w) for w in words]
        number = _first_number(bare, 0, len(bare))
        if number is not None:
            count = number + len(_truncate_locus_ex(bare[number:], head=True)[0])
    if count and count < len(matches) and (_ends_locus(words[count], bool(sources or ebend)) or firm):
        head = _close_groups(head[:matches[count - 1].end()].rstrip(), tail)
    # Aëtius' chapter title in its own parenthesis after the Diels page is
    # the citation's, as it is inside it ("(D. 387; εἰ σῶμα ἡ ψυχὴ ...)"):
    # Philolaus A21 "—III 13, 1. 2. (D. 378) (περὶ κινήσεως γῆς)". Not a
    # supplement to the quotation (Heraclitus A12 "(D. 354) (γίνεσθαι τὴν
    # ἔκλειψιν)").
    chapter = _CHAPTER_TITLE.match(tail[len(head):])
    if chapter and re.search(r"\(D\.[^()]*\)$", head):
        head = tail[:len(head) + chapter.end()]
    # Another page of the same work to compare, before the quotation, is
    # the citation's: Parmenides B7 "PLATO Soph. 237 A vgl. 258D Π. δὲ ...".
    compare = _COMPARE_PAGE.match(tail[len(head):])
    if compare and re.search(r"\d\s?[A-Fa-f]?$", head):
        head = tail[:len(head) + compare.end()]
    # A chapter's Greek title between the chapter and its Bekker place is
    # the citation's, with the place after it: Anaxagoras A84 "ARISTOT.
    # Meteorol. Β 9 (περὶ ἀστραπῆς καὶ βροντῆς) 369b 14 [nach 31 A 63]" had
    # stopped at "Β 9" (Grok check of round 7, 2026-09-29).
    chapter = _CHAPTER_TITLE.match(tail[len(head):])
    if chapter and re.match(r"\s+\d", tail[len(head) + chapter.end():]):
        place = _head_extent(dictionary, tail[:len(head)] + tail[len(head) + chapter.end():])
        if len(place) > len(head):
            head = tail[:len(place) + chapter.end()]
    # The same title right after the place, before the quotation, is the
    # citation's too: Critias B4 "HEPHAEST. 2, 3 (περὶ συνεκφωνήσεως)",
    # Democritus A77 "... p. 734F (διὰ τί τοῖς φθινοπωρινοῖς ...)", and
    # Empedocles A88 "AËT. IV 14, 1 (περὶ κατοπτρικῶν ἐμφάσεων. D. 405)"
    # with the Diels page inside it (2026-09-29).
    chapter = _CHAPTER_TITLE.match(tail[len(head):])
    if chapter and re.search(r"\d[A-Fa-f]?$", head) and not re.match(r"\s+\d", tail[len(head) + chapter.end():]):
        head = tail[:len(head) + chapter.end()]
    # DK's note that the passage follows another fragment in the same source,
    # printed bare after the place: "CLEM. Str. v 110 [II 400, 1 St.] nach B
    # 14" (Xenophanes B15), as "[nach 28 B 16]" and "(nach B 50)" are.
    nach = _NACH_FRAGMENT.match(tail[len(head):])
    if nach and re.search(r"[\d\])]\s?[A-Fa-f]?$", head):
        head = tail[:len(head) + nach.end()]
    return _cut_unclosed(head)


_COMPARE_PAGE = re.compile(r"\s+vgl\.\s+\d+(?:\s?[A-F])?(?=\s+[Ͱ-Ͽἀ-῿])")
# "nach B 14", "nach 67 A 8", "nach 21 C 2:" -- a DK number, then the end of
# the line, the Greek, or a quotation mark.
_NACH_FRAGMENT = re.compile(r"\s+nach\s+(?:\d+\s+)?[ABC]\s?\d+[a-z]?(?:,\s*\d+)?:?(?=\s*$|\s+[Ͱ-Ͽἀ-῿‘'])")


_CHAPTER_TITLE = re.compile(r"\s*\((?:περὶ|διὰ τί|πῶς|τίς|τί|εἰ|ποῦ|πόσ)\s[^()]*\)")


def _first_number(words: list[str], start: int, stop: int) -> int | None:
    """The first number or book numeral outside brackets in words[start:
    stop]: "APOLLODOR. [F GrHist. 244F 33, s. oben I 278, 28]" has none of
    its own."""
    depth = 0
    for j in range(start, stop):
        if not depth and re.match(r"^(?:\d|[IVXLC]+[.,]?$)", words[j]):
            return j
        depth = max(0, depth + words[j].count("(") + words[j].count("[")
                    - words[j].count(")") - words[j].count("]"))
    return None


def _ends_locus(word: str, vgl: bool = True) -> bool:
    """A word after a locus that opens the quoted text: a Latin word, a
    Latin initial ("CENSORIN. 4, 7 A. Milesius ...": A[naximander]; "6, 1
    E., quem ..."), one in quotation marks ("90, 32 ‘Democritus’ inquit"),
    one after a stray semicolon ("15, 3 ;X. Colophonius"), or DK's
    ellipsis ("I 4, 4 ... propter"). Not a book numeral, which starts
    another place ("—IX 18 (oben I 113, 18). II 46"), nor, after a dash
    (`vgl` false), DK's "vgl.", whose comparison belongs to the citation
    ("— — —60 (II 366, 11) vgl. IV 50")."""
    if re.fullmatch(r"[IVXLC]+[,;]?|[IVXLC]{2,}\.", word) or (not vgl and word.casefold().startswith("vgl")):
        return False
    if re.fullmatch(r"\d+o", word):
        return True  # the export's "3o" for the article (_garbled_article)
    return bool(re.match(r"[‘'\"“«;:]?(?:[A-Za-z]{2}|[A-Z]\.,?$)|\.\.\.|…", word))


def _cut_unclosed(head: str) -> str:
    """A bracket, parenthesis or angle bracket still open at the end of a
    head does not close before the quoted text begins (or never closes in
    the column): the head ends before it, and the opener stays in the
    passage as printed (Anaxagoras B7 "SIMPLIC. de caelo 608, 23 (nach ...",
    its closer lines later after the Greek; Anaximenes A17 "AËT. III 3, 2
    (D. 368," with none; Heraclitus A17 "... (D. 392) <Ἡ. ...>", an editor's
    supplement to the quotation)."""
    opened: list[int] = []
    for pos, ch in enumerate(head):
        if ch in "([<":
            opened.append(pos)
        elif ch in ")]>" and opened:
            opened.pop()
    return head[:opened[0]].rstrip() if opened else head


def _cut_greek_initial(head: str) -> str:
    """A philosopher's Greek initial ("Ἡ.", "Ἀ.", "Δ.") outside brackets
    opens the quotation: the head ends before it, with whatever follows
    ("—29, 3 Ἡ. ...", "AËT. II 13, 7 (D. 342) Ἀ. [sc. τὰ ἄστρα εἶναι]"). A
    Greek book letter before a number stays."""
    depth = 0
    for m in re.finditer(r"\S+", head):
        tok = m.group()
        if depth == 0 and m.start() > 0 and re.fullmatch(r"[Ͱ-Ͽἀ-῿]\.,?", tok) and tok[0] != tok[0].lower() \
                and not re.match(r"\s*\d", head[m.end():]):
            return head[:m.start()].rstrip()
        depth = max(0, depth + tok.count("(") + tok.count("[") - tok.count(")") - tok.count("]"))
    return head


def _vgl_pointer(dictionary: _Dictionary, text: str, start: int, continues: bool) -> bool:
    """A citation DK introduces with "vgl." (compare) is a heading only when
    its own text follows it (Gorgias A4 "vgl. DIONYS. d. Lys. 3 δηλοῖ ...").
    Followed by another citation, or by nothing (`continues`: more lines of
    the column follow), it only points elsewhere: Empedocles B98 "vgl. AËT.
    v 22 [A 78 I 299, 5]. EBEND. 331, 3 ..."."""
    head = _head_extent(dictionary, text[start:])
    rest = text[start + len(head):]
    if not re.search(r"[^\W_]", rest):
        return not continues
    words = [_nfc(w) for w in rest.lstrip(" .,;:·").split()]
    return bool(words and (dictionary.match_author(words, 0) or _ebend_span(words, 0)))


# Numbers then a Diels Doxographi page, "4, 3 (D. 331)": a place in the
# source cited above (_citation_positions).
_NUMBERS = (r"(?:ib\.\s+(?:[IVX]+,?\s*)?\d+[a-z]?(?:,\s*\d+[a-z]?)?|[IVX]+,?\s*\d+[a-z]?(?:,\s*\d+[a-z]?)?"
            r"|\d+[a-z]?,\s*\d+[a-z]?)(?:\.\s*\d+[a-z]?)*")
# The Diels page, in parentheses or (Xenophanes A43 "II 28, 1 [D. 358]")
# brackets; without one, the numbers must stand before the philosopher's
# Greek initial (Heraclitus A8 "28, 1 Ἡ. οὐσίαν ...") or a DK cross-reference
# (Empedocles A90 "9, 6 [28 A 47].").
_DIELS_PAGE = r"\s*(?:\(D\.\s*\d+[^()]*\)|\[D\.\s*\d+[^\[\]]*\])"
_NUMBER_CONTINUATION = re.compile(
    _NUMBERS + r"(?:" + _DIELS_PAGE + r"|(?=\s+[Ͱ-Ͽἀ-῿]\.,?\s)|(?=\s*\[\d+\s*[AB]\s*\d+[a-z]?\]))")
# "4, 3", "II 13, 10", "V 28", "I, 27, 1", "29, 6. 7", "23, 1(D.", "ib. 8" (ibidem)
# A head that is such a place, as printed.
_NUMBER_HEAD = re.compile(_NUMBERS + r"(?:" + _DIELS_PAGE + r")?$")


def _list_boundary(dictionary: _Dictionary, words: list[str], i: int, before: str) -> bool:
    """DK lists a second source straight after the first one's locus, with
    no sentence end between them: "SEXT. adv. math. VII 49. 110 PLUT. aud.
    poet. 2 p. 17 E" (Xenophanes B34), "DIOG. IX 36 CIC. Tusc. v 36, 104"
    (Democritus B116), "... (Buresch Klaros S. 118), ORIG. c. CELS. VII 62"
    (Heraclitus B5). A capitalised author abbreviation the dictionary knows,
    after a number, a column letter after a number ("267A", "17 E"), or a
    closed bracket and a comma, starts a head of its own. Not a lower-case
    one ("EUDEM. bei Simpl. Phys. 143, 4" is one citation)."""
    if sum(ch.isupper() for ch in words[i]) < 2 or not dictionary.match_author(words, i):
        return False
    return bool(re.search(r"(?:\d[A-Fa-f]?|\d\s[A-Fa-f]|[\])],)$", before))


def _citation_positions(dictionary: _Dictionary, text: str,
                        author: str | None = None, chain: _Chain | None = None,
                        run_start: bool = False, continues: bool = False) -> tuple[list[int], str | None]:
    """Strict sentence-boundary authors, dashes, "ebenda" heads, and
    same-column work ditto.

    Work-only heads use match_work, just as the dash resolver does. Protect
    the author and its own work tokens so "ARIST. de caelo" stays one head,
    after a dash too ("—ARIST. de caelo Α 10. 279b 12", Heraclitus A10). A
    dash is a head only where it names a place (_dash_names_place), except
    at the start of a line that opens a run (`run_start`), where DK's dash
    alone repeats the source above (Heraclitus B42 "— —τόν τε Ὅμηρον").
    A citation after "vgl." that only points elsewhere is none
    (_vgl_pointer; `continues`: more lines of the column follow `text`).
    """
    tokens = list(re.finditer(r"\S+", text))
    words = [_nfc(m.group()) for m in tokens]
    starts = []
    depth = 0
    cursor = 0
    protected = 0
    # An opener that never closes on the line encloses nothing (Anaximenes
    # A17 "AËT. III 3, 2 (D. 368, ..." then "... 4, 1 (D. 370)").
    unclosed: list[int] = []
    for pos, ch in enumerate(text):
        if ch in "([":
            unclosed.append(pos)
        elif ch in ")]" and unclosed:
            unclosed.pop()
    for i, token in enumerate(tokens):
        start = token.start()
        for pos in range(cursor, start):
            ch = text[pos]
            if ch in "([" and pos not in unclosed:
                depth += 1
            elif ch in ")]":
                depth = max(0, depth - 1)
        cursor = start
        before = text[:start].rstrip()
        boundary = not before or bool(re.search(r"[.··;;:\]\)][\]\)\}’”»\"']*$", before)) \
            or _list_boundary(dictionary, words, i, before)
        if depth or not boundary or start < protected:
            continue
        direct = dictionary.match_author(words, i)
        work = dictionary.match_work(author, words, i) if author and author != _AMBIGUOUS else None
        vgl = i > 0 and words[i - 1].casefold() in _VGL
        if direct is not None:
            if vgl and _vgl_pointer(dictionary, text, start, continues):
                continue
            span, author = direct
            own_work = dictionary.match_work(author, words, i + span) if author != _AMBIGUOUS else None
            protected = tokens[min(len(tokens) - 1, i + span + (own_work[0] if own_work else 0) - 1)].end()
        elif text[start:].startswith("—"):
            rest_text = _DASH_PREFIX.sub("", text[start:])
            offset = len(text) - len(rest_text)
            rest_tokens = list(re.finditer(r"\S+", rest_text))
            rest = [_nfc(m.group()) for m in rest_tokens]
            if not (start == 0 and run_start):
                authors = [author] + ([s.author for s in chain.sources[chain.head_start:]] if chain else [])
                if not _dash_names_place(dictionary, rest, authors):
                    continue
            direct_after_dash = dictionary.match_author(rest, 0) if rest else None
            if direct_after_dash:
                span, author = direct_after_dash
                own_work = dictionary.match_work(author, rest, span) if author != _AMBIGUOUS else None
                protected = offset + rest_tokens[min(len(rest_tokens), span + (own_work[0] if own_work else 0)) - 1].end()
            elif author is None and chain is not None:
                probe = copy.deepcopy(chain)
                candidate = _extract_head(text[start:]) or _dash_head(text[start:])
                _resolve_head(dictionary, candidate, "location-probe", "", probe)
                if probe.sources:
                    author = probe.sources[-1].author
        elif _ebend_span(words, i):
            protected = tokens[i + _ebend_span(words, i) - 1].end()
        elif _NUMBER_CONTINUATION.match(text[start:]) \
                and (re.search(r"\[?D\.", _NUMBER_CONTINUATION.match(text[start:]).group())
                     or (i and _has_lower_greek(words[i - 1]))) \
                and (author and author != _AMBIGUOUS or (start == 0 and run_start and chain is not None)
                     or (i and dictionary.match_author(words[i - 1:i], 0))) \
                and not (starts and start < starts[-1] + len(_head_extent(dictionary, text[starts[-1]:]))):
            if i and dictionary.match_author(words[i - 1:i], 0):
                # The author printed just before, with no sentence end
                # before him (Anaximander A17 "ὡς δοκεῖ AËT. I 7, 12 (D. 302)").
                if starts and tokens[i - 1].start() < starts[-1] + len(_head_extent(dictionary, text[starts[-1]:])):
                    continue
                starts.append(tokens[i - 1].start())
                author = dictionary.match_author(words[i - 1:i], 0)[1]
                protected = start + _NUMBER_CONTINUATION.match(text[start:]).end()
                continue
            if not author:
                # Opening a column, DK's dash left out (Anaximenes A14 "II 13,
                # 10 (D. 342)" after A13's Aëtius): the source it repeats.
                probe = copy.deepcopy(chain)
                _resolve_head(dictionary, "—" + _NUMBER_CONTINUATION.match(text).group(), "location-probe", "", probe)
                if not (probe.sources and probe.sources[-1].author):
                    continue
                author = probe.sources[-1].author
            # A new place in the source above, by numbers alone, with its
            # Diels page (Heraclitus A10 "AËT. II 1. 2 (D. 327) ... κόσμον.
            # 4, 3 (D. 331) Ἡ. ..."): rule E, a dash DK did not print. Not
            # the locus of the head it follows ("CENSOR. 6, 1 (D. 190;)").
            protected = start + _NUMBER_CONTINUATION.match(text[start:]).end()
        elif work is not None:
            if starts and not re.search(r"\d", text[starts[-1]:start]):
                continue  # still the citation above: "EUDEM. bei Simpl. Phys. 143, 4"
            if vgl and _vgl_pointer(dictionary, text, start, continues):
                continue
            protected = tokens[i + work[0] - 1].end()
        else:
            continue
        starts.append(start)
    return starts, author


def citation_starts(dictionary: _Dictionary, text: str) -> list[int]:
    return _citation_positions(dictionary, text)[0]


def _run_start(lines: list[dict], li: int) -> bool:
    """Does line li open a run, where a dash alone is DK's ditto head: a
    text line, or the first line of a context run (as _segment_context)."""
    role = lines[li].get("role")
    return role == "text" or (role == "context" and (li == 0 or lines[li - 1].get("role") != "context"))


def located_heads(dictionary: _Dictionary, lines: list[dict], chain: _Chain | None = None) -> list[dict]:
    """Extract exact, non-overlapping head ranges without normalizing the text."""
    result = []
    preceding_author = None
    for li, line in enumerate(lines):
        text = line.get("text", "")
        starts, preceding_author = _citation_positions(dictionary, text, preceding_author, chain,
                                                       _run_start(lines, li), li + 1 < len(lines))
        leads = [_vgl_lead(text, start, starts[i - 1] if i else None) for i, start in enumerate(starts)]
        for i, start in enumerate(starts):
            limit = leads[i + 1] if i + 1 < len(starts) else len(text)
            head = _head_extent(dictionary, text[start:limit])
            if not head:
                continue
            end = start + len(head)
            result.append({"lineIndex": li, "line": line["n"],
                           "start": _utf16_offset(text[:leads[i]]),
                           "end": _utf16_offset(text[:end]), "text": text[leads[i]:end]})
    return result


def _vgl_lead(text: str, start: int, previous: int | None) -> int:
    """Where the head at `start` begins when DK introduces it with "vgl."
    (compare) and its own text follows (_vgl_pointer): at the "vgl.", which
    is part of the heading, not a last word left on the passage above it
    (Anaxagoras A47 "... ἄτοπα. Vgl. ARISTOT. Metaph. ..."). The heading
    also takes up to two words before the "vgl." back to the end of the
    sentence or the start of the line: DK's dash, or the word or line the
    note is on (Protagoras A11 "— Vgl. EUSTATH.", Leucippus A7 "Zu ἁφή vgl.
    PHILOPON.", Parmenides B7 "42 vgl. SIMPL."). A "vgl." can also introduce
    a short cross-reference clause of its own before the citation, "zu
    196b 14" (German "on", a Bekker page and line): the whole note is the
    heading's (Democritus A68 "... τύχης. Vgl. zu 196b 14 SIMPL. p. 330,
    14", Grok content-check item 9, 2026-09-27). `previous`: the start of
    the head before it on the line, which it never reaches."""
    floor = 0 if previous is None else previous
    words = list(re.finditer(r"\S+", text[floor:start]))
    if not words:
        return start
    k = len(words) - 1
    if k >= 3 and words[k - 2].group().casefold() == "zu" \
            and words[k - 3].group().casefold() in _VGL \
            and re.fullmatch(r"\d+[a-z]?", words[k - 1].group()) \
            and re.fullmatch(r"\d+[a-z]?", words[k].group()):
        return floor + words[k - 3].start()
    if words[k].group().casefold() not in _VGL:
        return start
    first = k
    while first > max(0, k - 2) and not re.search(r"[.·;:!?]$", words[first - 1].group()):
        first -= 1
    if first < k and not (re.search(r"[.·;:!?]$", words[first - 1].group()) if first
                          else previous is None):
        first = k
    return floor + words[first].start()


# A heading _vgl_lead began before its citation: the words up to "vgl.",
# and its own cross-reference clause if it has one ("zu 196b 14").
_VGL_LEAD = re.compile(r"^(?:\S+\s+){0,2}?(?i:vgl)\.\s+(?:zu\s+\d+[a-z]?\s+\d+[a-z]?\s+)?")


# A citation DK prints in a passage that the dictionary does not read, a
# capitalized name with a number after it ("Menander Rhet. I 2, 2").
_UNREAD_CITATION = re.compile(r"(?<![\w.])[A-Z][A-Za-z]+\.?(?:\s+[A-Za-z]+\.)*\s+(?:[IVXLC]+|\d+)(?=[\s,.;]|$)")


def _unread_citation(passage: str) -> bool:
    """Whether `passage` cites a source of its own outside brackets, which
    an "ebenda" after it could mean (Parmenides A20 "Menander Rhet. I 2, 2
    ... Ebend. I 5, 2"). A "vgl." pointer up to its first number (Empedocles
    B98 "vgl. AËT. v 22 [A 78 ...]") is a cross-reference, not a source."""
    text = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", " ", passage)
    text = re.sub(r"(?i)\bvgl\.(?:\s+\S+)*?\s+\S*\d\S*", " ", text)
    return bool(_UNREAD_CITATION.search(text))


def _resolve_ebend(dictionary: _Dictionary, words: list[str], span: int,
                   source: _Source | None, between: str) -> tuple[list[dict], _Source]:
    """An "ebenda" head (_ebend_span): the author and work of the heading
    before it in the same column, at the locus printed after it, filled in
    as rule E fills a dash (steps 4-5). Stays as printed, flagged
    `ebend-unresolved`, when that source is unknown, when the passage since
    it cites another source (_unread_citation), or when an author printed
    before "ebend." is not his ("AR. ebend." after ARIST., Thales A22)."""
    printed = " ".join(words)
    if source is None or source.author is None or source.work is None or _unread_citation(between) \
            or (span == 2 and not any(v.startswith(words[0].rstrip("."))
                                      for v in dictionary.author_entry(source.author)["variants"])):
        return [_verbatim(printed, ["ebend", "ebend-unresolved"])], _Source(None, None, None, "passage")
    named = copy.copy(source)
    named.origin = "head"  # the heading it repeats, even one inside a passage
    chain = _Chain()
    chain.push_head([named])
    entry, resolved = _resolve_dash(dictionary, chain, printed, words[span:], "", True, ["ebend"])
    return [entry], resolved


def _number_continuation(dictionary: _Dictionary, chain: _Chain, before: int,
                         printed: str, ante: "_Source | None") -> list[dict] | None:
    """A number continuation ("4, 3 (D. 331)") rule E could not place,
    when the source above prints a book the numbers leave out ("II 1. 2"
    for II 1, 2, Heraclitus A10; "II 25, 9 s. 59 A 77.", Democritus A90):
    that book, with the numbers for chapter and section, in a book,
    chapter, section work whose Diels page is the same author's. None
    otherwise. `ante`: the source the last heading in the column named (not
    a passage's, Anaximenes A17 "(D. 368, ..."). Replaces the unresolved
    source the attempt left in the chain; `before` is the chain's length
    before it."""
    page = _doxographi_page(printed)
    if ante is None or ante.author is None or ante.work is None or ante.locus is None \
            or page is None or _doxographi_owner(dictionary, page) != ante.author:
        return None
    work = dictionary.author_entry(ante.author)["works"][ante.work]
    book = re.match(r"([IVX]+)\s+\d", ante.locus)
    if work.get("locus_template") != "book-chapter-section" or book is None:
        return None
    locus, apparatus = _locus_fields(f"{book.group(1)} {printed}".split(), True, True)
    entry = _entry(printed, "dash", dictionary.author_entry(ante.author), work, locus, apparatus,
                   ["dash-e5", "number-continuation"])
    chain.sources[before:] = [_Source(ante.author, ante.work, locus)]
    return [entry]


def _record_forms(dictionary: _Dictionary, forms: dict, printed: str) -> None:
    """Remember how a head prints its author and work abbreviations, for
    _dash_display: forms[(author, work)] = (author as printed, work as
    printed or None), forms[author] = the author as printed."""
    words = re.findall(r"\S+", _nfc(printed))
    for start, span, key in _split_sources(dictionary, words, 0):
        if key == _AMBIGUOUS:
            continue
        work = dictionary.match_work(key, words, start + span)
        author = " ".join(words[start:start + span])
        forms[key] = author
        forms[(key, work[1] if work else "DEFAULT")] = (
            author, " ".join(words[start + span:start + span + work[0]]) if work else None)


def _dash_display(dictionary: _Dictionary, forms: dict, head: dict, first: bool,
                  src: "_Source | None") -> str:
    """What the Greek-side heading of a dash head reads (John, 2026-09-27:
    each testimony or fragment starts with the full citation). The first
    head of a column, a dash that names no author, reads as the full
    citation in DK's abbreviations: the author (and an inherited work) as
    the head it continues prints them, then the resolved locus (A12 "—II 20,
    16 (D. 351)" -> "AËT. II 20, 16 (D. 351)"); a dash whose reading waits
    on John's check of the print keeps its printed locus (A11). Any other
    dash head, or one whose source is not known, reads without the dash."""
    stripped = _DASH_PREFIX.sub("", head["text"])
    entries = head["expanded"]
    if not first or src is None or src.author is None or src.work is None or len(entries) != 1:
        return stripped
    entry = entries[0]
    author_entry = dictionary.author_entry(src.author)
    own = dictionary.match_work(src.author, re.findall(r"\S+", _nfc(stripped)), 0)
    if entry["resolution"] == "dash":
        apparatus = entry.get("apparatus") or ""
        note = author_entry["works"][src.work].get("edition_note")
        if note and apparatus.startswith(note):
            # The English's "Bekk." after the locus; DK's own "AN. BEKK."
            # already names him on this side.
            apparatus = apparatus[len(note):].strip()
        body = " ".join(filter(None, [entry.get("locus"), apparatus]))
    elif {"awaiting-print-check", "awaiting-adjudication"} & set(entry["flags"]) \
            and (own or re.match(r"[IVX]+\s+\d", stripped)):
        body = stripped  # a whole printed locus ("II 13, 8"), not "37" short of its book
    else:
        return stripped
    printed = forms.get((src.author, src.work))
    author = printed[0] if printed else forms.get(src.author, author_entry["variants"][0])
    work_entry = author_entry["works"][src.work]
    if work_entry.get("locus_includes_work") or work_entry.get("volume_by_part") \
            or work_entry.get("locus_prefix") or (own and entry["resolution"] != "dash"):
        work = None  # the locus prints it
    elif own:
        work = " ".join(re.findall(r"\S+", stripped)[:own[0]])
    elif src.work == "DEFAULT":
        work = None
    else:
        work = printed[1] if printed and printed[1] else src.work
    return " ".join(filter(None, [author, work, body]))


def _same_place_display(dictionary: _Dictionary, forms: dict, head: dict, src: "_Source") -> str:
    """The Greek-side heading of a first head that prints DK's "a. O." (the
    place cited above, _same_place_above): the head with the place itself,
    and the work as the head above printed it when this one names none --
    Antiphon B2 "GAL. in Hipp. de med. off. a. O." -> "GAL. in Hipp. de med.
    off. XVIII B 656 K.", Critias B40 "GAL. a. O." -> "GAL. comment. in
    Hippocr. de offic. I 1"."""
    printed = re.sub(r"\s*a\.\s*O\.\s*$", "", head["text"])
    words = re.findall(r"\S+", _nfc(printed))
    direct = dictionary.match_author(words, 0)
    own = direct and dictionary.match_work(src.author, words, direct[0])
    work = None if own else (forms.get((src.author, src.work)) or (None, None))[1]
    return " ".join(filter(None, [printed, work, head["expanded"][0]["locus"]]))


def resolve_located_segments(dictionary: _Dictionary, segments: list[dict],
                             work_id: str, rulings: dict) -> dict:
    """Resolve in print order; passage scans retain rule E's chain evidence."""
    chain = _Chain()
    result = {}
    forms: dict = {}  # how the work's heads print each source (_record_forms)
    for seg in segments:
        lines = seg.get("lines", seg.get("greek", []))
        heads = located_heads(dictionary, lines, chain)
        column = seg.get("column") or seg["id"].split(":", 1)[-1]
        by_line = {}
        preceding_author = None
        column_source = None  # the source the last heading in this column named
        between = ""  # the passage since that heading
        for head in heads:
            by_line.setdefault(head["lineIndex"], []).append(head)
        for li, line in enumerate(lines):
            text = line.get("text", "")
            # Work in UTF-16 only at the boundary; Python scans code points.
            raw = text.encode("utf-16-le")
            cursor = 0
            for head in by_line.get(li, []):
                # A heading DK introduces with "vgl." resolves from its
                # citation; its words up to the "vgl." read as passage, as
                # before the heading took them (_vgl_lead).
                lead = _VGL_LEAD.match(head["text"])
                printed = head["text"][lead.end():] if lead else head["text"]
                start = head["start"] + (_utf16_offset(lead.group()) if lead else 0)
                passage = raw[cursor * 2:start * 2].decode("utf-16-le")
                _scan_passage(dictionary, chain, passage)
                between += " " + passage
                rest = raw[head["end"] * 2:].decode("utf-16-le")
                # NFC as the heads are: the export prints the Greek colon as
                # U+0387, which NFC folds to the "·" the lemma rules match
                # (Antiphon B55 "PHOT. ἵνα· ὅπου", 2026-09-28).
                lemma = _nfc(rest) or _lemma_lookahead(lines, li)
                previous_head_start = chain.head_start
                source_count = len(chain.sources)
                old_run_head = start == 0 and (
                    printed.startswith(("—", "–")) or
                    (line.get("role") == "context" and
                     (li == 0 or lines[li - 1].get("role") != "context")))
                undashed = _DASH_PREFIX.sub("", printed)
                words = re.findall(r"\S+", _nfc(printed))
                direct = dictionary.match_author(words, 0)
                explicit_after_dash = dictionary.match_author(re.findall(r"\S+", _nfc(undashed)), 0) if undashed != printed else None
                if explicit_after_dash:
                    direct = explicit_after_dash
                if direct:
                    preceding_author = direct[1]
                ebend = _ebend_span(words, 0)
                numbers = not direct and bool(_NUMBER_HEAD.match(printed))
                continuation = not direct and not ebend and not numbers and not printed.startswith(("—", "–"))
                resolution_chain = chain
                if continuation and preceding_author and preceding_author != _AMBIGUOUS:
                    # Explicitly the preceding heading's author in THIS column;
                    # incidental source mentions in the passage cannot steal it.
                    resolution_chain = _Chain()
                    resolution_chain.push_head([_Source(preceding_author, None, None)])
                if ebend:
                    head["expanded"], ebend_source = _resolve_ebend(dictionary, words, ebend, column_source, between)
                    if ebend_source.author is not None:
                        # An ebenda left as printed names no source a later
                        # dash could build on or be kept from.
                        chain.sources.append(ebend_source)
                else:
                    try:
                        if numbers:  # read "II1, 6", "23, 1(D. 352)" as spaced
                            spaced = re.sub(r"(\d)\(", r"\1 (", re.sub(r"^([IVX]+,?)(\d)", r"\1 \2", printed))
                            spaced = re.sub(r"^ib\.\s+", "", spaced)  # "ib. 8 (D. 329)": ibidem, the source above
                        head["expanded"] = _resolve_head(dictionary, "—" + (spaced if numbers else printed) if continuation or numbers else (undashed if explicit_after_dash else printed), work_id,
                                                          seg["id"], resolution_chain, lemma, rulings.get(column))
                        if numbers and {"dash-antecedent-uncertain", "doxographi-owner-unknown"} \
                                & set(head["expanded"][0]["flags"]) \
                                and column_source is not None and column_source.author:
                            # Undashed numbers right after a source this
                            # column names in its text continue that source,
                            # the last one named, though a dash heads the
                            # column with another author and the table
                            # gives the Diels page no owner (Protagoras A23
                            # "CIC. de nat. deor. I 24, 63 ... 12, 29 (D.
                            # 535)"). The page then decides nothing and is
                            # printed as apparatus.
                            named = copy.copy(column_source)
                            named.origin = "head"
                            retry = _Chain()
                            retry.push_head([named])
                            page = re.search(r"\s*\(D\.[^()]*\)$", spaced)
                            core = spaced[:page.start()] if page and "doxographi-owner-unknown" \
                                in head["expanded"][0]["flags"] else spaced
                            entries = _resolve_head(dictionary, "—" + core, work_id, seg["id"], retry, lemma)
                            if entries and entries[0]["resolution"] != "verbatim":
                                if core != spaced:
                                    entries[0]["apparatus"] = page.group().strip()
                                head["expanded"] = entries
                                chain.sources[source_count:] = retry.sources[1:]
                        if numbers and head["expanded"][0]["resolution"] == "verbatim":
                            head["expanded"] = _number_continuation(
                                dictionary, chain, source_count, spaced, column_source) or head["expanded"]
                        if explicit_after_dash or numbers:
                            for entry in head["expanded"]:
                                entry["verbatim"] = printed
                        if continuation:
                            for entry in head["expanded"]:
                                entry["verbatim"] = printed
                                entry["flags"].append("work-continuation")
                            chain.sources.extend(resolution_chain.sources[1:])
                    except ValueError as error:
                        # Newly visible mid-line sources may lack dictionary work
                        # coverage. Keep their heading and flag it, never guess a
                        # work or let a later dash inherit an unrelated source.
                        if "but names no work" not in str(error):
                            raise
                        head["expanded"] = [_verbatim(head["text"], ["work-unresolved"])]
                        chain.push_head([_Source(None, None, None, foreign=True)])
                if lead:
                    for entry in head["expanded"]:
                        entry["verbatim"] = head["text"]
                if direct and not ebend:
                    _record_forms(dictionary, forms, undashed if explicit_after_dash else printed)
                src = chain.sources[-1] if len(chain.sources) > source_count else None
                if head["text"].startswith(("—", "–")):
                    head["display"] = _dash_display(dictionary, forms, head, head is heads[0] and not direct, src)
                    for entry in head["expanded"]:
                        if entry["resolution"] == "verbatim":
                            entry["verbatim"] = head["display"]  # no dash on the English side either
                elif numbers and head is heads[0]:
                    display = _dash_display(dictionary, forms, head, True, src)
                    if display != head["text"]:
                        head["display"] = display
                elif head is heads[0] and src is not None and len(head["expanded"]) == 1 \
                        and "same-place" in head["expanded"][0]["flags"]:
                    head["display"] = _same_place_display(dictionary, forms, head, src)
                if chain.sources and chain.sources[-1].author:
                    preceding_author = chain.sources[-1].author
                if ebend:
                    column_source = ebend_source
                elif len(chain.sources) > source_count:
                    column_source = chain.sources[-1]
                between = ""
                if not old_run_head:
                    # Structural headings do not change rule E's distinction
                    # between a run head and a source named within its passage.
                    chain.head_start = previous_head_start
                    for source in chain.sources[source_count:]:
                        source.origin = "passage"
                cursor = head["end"]
            passage = raw[cursor * 2:].decode("utf-16-le")
            _scan_passage(dictionary, chain, passage)
            between += " " + passage
        result[seg["id"]] = heads
    return result


def run(manifest: Manifest, spine: dict) -> Path | None:
    if not manifest.data.get("citation", {}).get("expand_citations"):
        return None
    dictionary = _load_dictionary()
    rulings = _load_adjudications().get(manifest.work_id, {})
    # One list PER SEGMENT, each element being one head's own entry list
    # (fix round finding 2) -- never flattened. Two distinct runs (e.g.
    # Heraclitus B37's "COLUMELLA VIII 4..." and its later, unrelated
    # "[vgl. B 13],") stay two separate lines; a run's own multi-source split
    # (one head naming several witnesses) still joins as one line, exactly as
    # DK printed it. A head that is not itself a resolvable citation
    # (editorial prose head-only text) contributes an EMPTY list in its slot,
    # never dropped from the sequence: the reader's per-block placement counts
    # heads positionally by the same rule (_segment_context), so a dropped
    # slot would misalign every later run in the segment.
    resolved: dict[str, list[list[dict]]] = {}
    counts = {"direct": 0, "dash": 0, "verbatim": 0}
    n_skipped = 0
    used_rulings: set[str] = set()
    # One chain per work, carried across its columns in document order.
    chain = _Chain()
    for seg in spine["segments"]:
        seg_id = seg["id"]
        column = seg.get("column") or seg_id.split(":", 1)[-1]
        runs: list[list[dict]] = []
        any_entries = False
        for head, passage, lemma, scan in _segment_context(seg):
            if head:
                head_entries = _resolve_head(dictionary, head, manifest.work_id, seg_id,
                                             chain, lemma, rulings.get(column))
                if any(_RULING_FLAGS & set(e["flags"]) for e in head_entries):
                    used_rulings.add(column)
                if not head_entries:
                    n_skipped += 1
                else:
                    any_entries = True
                runs.append(head_entries)
            if scan:
                _scan_passage(dictionary, chain, passage)
        if any_entries:
            resolved[seg_id] = runs
            for e in (e for run in runs for e in run):
                counts[e["resolution"]] += 1
    columns = {seg.get("column") or seg["id"].split(":", 1)[-1] for seg in spine["segments"]}
    unused = (set(rulings) & columns) - used_rulings
    if unused:
        raise ValueError(
            f"{manifest.work_id}: dash adjudications for {sorted(unused)} match no dash "
            f"head in their column -- the source data moved; re-check the adjudication table")
    print(
        f"  citation_expansion: columns={len(resolved)} direct={counts['direct']} "
        f"dash={counts['dash']} verbatim={counts['verbatim']} non-head-runs={n_skipped}"
    )
    out_path = BUILD_DIR / "stage1" / "citation_expansion.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    locations = resolve_located_segments(dictionary, spine["segments"], manifest.work_id, rulings)
    (out_path.parent / "citation_heads.json").write_text(
        json.dumps(locations, ensure_ascii=False, indent=1), encoding="utf-8")
    return out_path
