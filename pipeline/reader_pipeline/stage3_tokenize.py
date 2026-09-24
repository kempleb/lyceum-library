"""Stage 3: tokenize the Greek spine.

Splits each line on whitespace and emits, per token, two independent views:

  * `t` (surface): the LITERAL substring of the line's `text` the token
    occupies — only ordinary punctuation (`_PUNCT`) is trimmed from its
    edges; editorial sigla (`_SIGLA`: †*<>[]⎪⟦⟧⌜⌞⌝⌟) are NEVER removed, at
    either edge or inside. This is a hard contract: the reader's
    `lineRenderParts` (shared/lib/speakers.ts) walks each line with
    `text.indexOf(tok.t, ptr)` in strict token order, so `t` must always be
    findable as a contiguous run inside `text`. Deleting an interior mark
    (e.g. the Schenkl supplement `ὁμολογεῖ<ν>`, whose `<`/`>` sit BETWEEN two
    letters of one word) breaks that contiguity and desyncs every later
    token's offset walk for the rest of the line (measured: a >15,000-char
    leapfrog in the Discourses build) — this was CLAUDE.md defect B.
  * `k` (Beta Code lookup key): derived from the fully CLEANED form (all
    punctuation and sigla stripped, `_clean()` below) exactly as before —
    the lexicon key is unaffected by the `t`/surface contract above.

`o` is the exact character offset of `t` within the line's `text`
(`text[o:o+len(t)] == t` always holds), not the offset of the raw
whitespace-delimited match (which could include leading punctuation the
surface trim removes).

A token's `k` is present only when the token is LEXICAL — a token that
contains no Greek letters at all (inline Latin-script scholarly apparatus:
"FGrH", editor names, bare numerals like "35") is NON-LEXICAL by definition
and is emitted with no `k` field, never an empty string. A token that DOES
contain Greek letters but still fails to produce a key is a real bug (an
unhandled character/mark reaching to_beta_key), not an expected non-lexical
token, so it fails loudly instead of being silently demoted — see the
ValueError raised at the end of tokenize() below.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from .beta import to_beta_key
from .config import BUILD_DIR, Manifest
from .latin import to_latin_key

# Stripped silently from token edges: ordinary punctuation. The pipe `|` marks
# verse-line divisions inside quoted hexameter (e.g. the Empedocles fragments in
# Metaphysics) — a metrical separator, not part of any word. ‘ (U+2018) opens a
# quotation (e.g. the poets quoted in the Politics); its mate ’ (U+2019) is left
# out of this set because it doubles as the elision apostrophe, which the
# surface form keeps; a ’ that instead CLOSES a quotation is peeled below.
# « » (U+00AB/U+00BB) wrap quoted verse in the TLG (e.g. the Empedocles fragments
# in On Generation and Corruption) — edge punctuation, stripped silently.
# „ “ (U+201E/U+201C) are German-style low-opening/high-closing curly quotes
# (Epictetus Discourses 2.17/2.21's „εἰς ... λύχνους“,
# „ἥξει ... εἰδώς“); unlike ’ (U+2019) neither one doubles as the
# elision apostrophe, so both are always edge punctuation and safe to strip
# unconditionally like « » above. The hyphen-minus - (U+002D) edges a
# meta-linguistic morpheme the TLG cites as a word part (Cratylus 405d's
# "ὁμο-" / "ἀ-", naming the prefixes); it is not part of any lookup form,
# so strip it from the token edge. The colon : (U+003A) is a
# scholiast's lemma/gloss separator (Heraclitus A14a's scholion on
# Nicander, glossing a quoted word with a following explanation --
# never part of a Greek lookup form), edge punctuation, safe to strip
# unconditionally like the marks above (first attested in this corpus
# by the Wave 1b DK pilot; no prior work needed it).
# A bare ASCII ? (U+003F) marks an editor's textual uncertainty
# directly appended to a word with no space (Heraclitus B12's fourth block, "ἀναθυμιῶνται(?)" -- "the exhalations(?)", Diels' own doubt about the
# reading) -- edge punctuation, distinct from the Greek question mark
# (U+037E, already handled via NFD decomposition below), safe to strip
# unconditionally.
_PUNCT = ".,·;—()|\"‘«»„“-:?" + "·;"  # real Greek ano teleia + Greek question mark -- distinct codepoints
# from the look-alike ASCII . and ; just above; the TLG export uses
# these Greek-specific forms, which NFD-decompose to the ASCII ones
# (so both must be listed here, since _clean() strips the RAW token
# before to_beta_key's own NFD normalize runs)

# Stripped but logged: editorial sigla found by the stage 2 inventory.
# ⎪ (U+23AA) is the column divider the TLG uses inside Aristotle's inline tables
# (e.g. the De Int 22a modal-opposition square); strip it so the cells tokenize.
# ⟦ ⟧ (U+27E6/U+27E7) are the double brackets marking editorially secluded text
# (e.g. the deleted passages in De Generatione Animalium); treat like [ ].
# ⌜ ⌞ ⌝ ⌟ (U+231C/231E/231D/231F) are the half/corner brackets the TLG uses to
# mark editorial supplements and transpositions (e.g. in the Eudemian Ethics);
# strip like the other seclusion brackets so the bracketed words tokenize.
# NOTE: the keraia (U+0374 GREEK NUMERAL SIGN, ʹ) is deliberately NOT in
# this set -- see _KERAIA below. It used to live here and be stripped as an
# "editorial mark" BEFORE classification, so a numeral like "αʹ" reached
# to_beta_key as bare "α" and wrongly keyed as the word alpha (Sol review
# finding, 2026-07-16). It must be recognized as part of the numeral before
# any stripping happens, and it stays in the token's surface text -- it is
# the numeral's own orthography, not editorial apparatus.
# ( ) join the set here (Wave 1b Parmenides pilot, first attested INTERIOR
# use in this corpus): DK6's own supplement notation marks an editorially
# resolved/supplied letter INSIDE a word with parentheses, e.g. B8's
# "ἔστ(ι)", "ὄνομ(α)", "ἄγους(α)" -- the same semantic category as the
# angle-bracket supplement "ὁμολογεῖ<ν>" documented above, just DK's own
# bracket convention for it. ( ) were already in `_PUNCT` for the
# established EDGE-only case (Heraclitus B12's "ἀναθυμιῶνται(?)", an
# uncertainty annotation stripped entirely, display included) -- that
# behavior is unchanged (edge-stripping in `_surface()` still keys off
# `_PUNCT` membership alone), but an INTERIOR paren, like every other siglum
# here, was previously left in the cleaned lookup key with no transliteration
# (a `to_beta_key` hard failure -- key_failures.json). Adding them to
# `_SIGLA` fixes the key (interior sigla are stripped from `k`). INTERIOR
# parens stay visible in surface `t` like `<>`, but a TRAILING `)` is still
# edge-trimmed by `_surface()` because `()` are also in `_PUNCT` (unlike
# pure `_SIGLA` marks such as `<>`).
#
# ⸏ (U+2E0F PARAGRAPHOS, first attested in this corpus, Wave 1c Sophists
# batch 2: Antiphon 87 B44, the damaged POxy 1364 "On Truth" papyrus):
# marks the location of a genuine ancient marginal paragraphos stroke in
# the papyrus, printed by Diels glued directly onto the adjacent Greek
# word with no separating space -- both leading-edge and INTERIOR
# (mid-word, where a hyphen-wrap rejoin pulled the two halves together).
# A real papyrological siglum, the same
# semantic category as `<>`/`()`/`[]` above (editorial/scribal apparatus
# marking a real manuscript feature, not part of the word) -- corpus-wide,
# not manifest-scoped, on the same reasoning already established for `()`:
# any future DK papyrus fragment quoted with its own paragraphoi needs the
# same handling, not a one-off `export_artifact_chars` (that mechanism is
# for accidental encoding glitches specific to one work, e.g. Empedocles'
# obol sign -- a genuine, recurring papyrological convention belongs here
# instead, exactly like `()`'s own precedent above).
#
# ⸓ (U+2E13 DOTTED OBELOS) and Ͻ (U+03FD GREEK CAPITAL REVERSED LUNATE
# SIGMA SYMBOL, used here as a critical siglum, not a letter -- Antiphon
# B44/B54) join the same set for the same reason: genuine ancient/editorial
# critical marks the export glues directly onto an adjacent Greek word.
#
# ⌊⌋ (U+230A/U+230B LEFT/RIGHT FLOOR, Wave 2 Batch 1a: Cicero's De Officiis,
# Atzert's Teubner text) mark an editorially-flagged passage, always
# DOUBLED (⌊⌊...⌋⌋) and glued directly onto the adjacent word with no space
# (verified corpus-wide against phi0474055.xml: 42 pairs, e.g.
# "⌊⌊etiamne", "furioso?⌋⌋") -- the same recurring-editorial-siglum shape as
# the paragraphos/dotted-obelos precedent above, not a one-off
# `export_artifact_chars` glitch, so it joins the corpus-wide set rather
# than a manifest-scoped one.
#
# → ← (U+2192/U+2190 RIGHTWARDS/LEFTWARDS ARROW, John's dashboard ruling
# 2026-07-24 reversing the earlier `export_artifact_chars` strip): Zeno
# testimonia A28's `<seg type="Diagram">` (Alexander of Aphrodisias' figure
# for the Stadium paradox, via Simplicius) glues these directly onto the
# adjacent row-label run with no separating space -- "ΒΒΒΒ→" (the B-row
# moving right, Δ→Ε) and "←ΓΓΓΓ" (the Γ-row moving left, Ε→Δ), confirmed
# against the export XML and the diagram's own verbal legend ("Β ὄγκοι
# κινούμενοι ἀπὸ τοῦ Δ ἐπὶ τὸ Ε" / "Γ ... ἀπὸ τοῦ Ε ἐπὶ τὸ Δ"). Originally
# treated as a one-off `export_artifact_chars` glitch and stripped
# entirely; re-classified as genuine DK6 print content (John: "if there
# were arrows, put them in") -- same recurring-editorial-siglum shape as
# the paragraphos/dotted-obelos/floor-bracket precedents above, so it
# joins the corpus-wide `_SIGLA` set (kept verbatim in surface `t`,
# stripped from the lexicon key `k`) rather than staying manifest-scoped.
_SIGLA = "†*<>()[]⎪⟦⟧⌜⌞⌝⌟⸏⸓Ͻ⌊⌋→←"

_LANGUAGE_PUNCT = {
    "grc": (_PUNCT, _PUNCT),
    # PHI's restored exclamation marks are sentence punctuation in Latin:
    # excluded from lookup keys AND edge-trimmed from surfaces, exactly as
    # `.` is (R7.1: no Latin Token.t contains `!`). Greek keeps `!` out of
    # both sets — three shipped works carry literal editorial `(!)` marks.
    "lat": (_PUNCT + "!", _PUNCT + "!"),
}


_APOSTROPHES = "'’᾽ʼ"  # ', ’, ᾽ (koronis), ʼ


def _is_greek_letter(ch: str) -> bool:
    """True when ch is a Greek LETTER of any accentuation (so an apostrophe
    sitting after it is an elision mark, not a closing quotation mark).

    The letter-category guard matters: U+037E GREEK QUESTION MARK and U+0387
    GREEK ANO TELEIA are named "GREEK …" but are punctuation (category Po), and
    they are exactly the marks that sit between a quoted word and its closing ’
    (λέγεις;’, οἶδα·’) — treating them as letters would wrongly keep the quote."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK") and unicodedata.category(ch).startswith("L")


def _contains_greek(token: str) -> bool:
    """True when token has at least one Greek letter — the line between a
    LEXICAL token (should key, and must fail loudly if it does not) and a
    NON-LEXICAL one (inline Latin-script apparatus/numerals; no Greek at
    all, so no key is expected and none is emitted)."""
    return any(_is_greek_letter(ch) for ch in token)


def _is_latin_letter(ch: str) -> bool:
    """True when ch is a Latin-script LETTER of any accentuation — the
    Latin-language analogue of `_is_greek_letter` above, gating which tokens
    are LEXICAL for a work whose manifest declares `language: lat`."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("LATIN") and unicodedata.category(ch).startswith("L")


def _contains_latin(token: str) -> bool:
    """True when token has at least one Latin letter — the Latin-language
    analogue of `_contains_greek` above: the line between a LEXICAL token
    (gets a `k` key) and a NON-LEXICAL one (bare numerals, non-Latin-script
    apparatus; no key is expected or emitted)."""
    return any(_is_latin_letter(ch) for ch in token)


# Greek alphabetic-numeral signals: Diogenes Laertius cites sums (e.g. a
# philosopher's estate in the Lives) using Greek LETTERS as digits rather
# than Arabic numerals — 'ιϛ' is iota(10) + stigma(6) = 16; '͵δοε' is the
# lower numeral sign U+0375 (a thousands multiplier) followed by more
# letter-digits. These are real Greek letters by Unicode category, but they
# are numerals, not words, and can never have a Morpheus/LSJ entry — exactly
# like a bare Arabic-numeral token ("35"), so a token containing any of these
# signals is non-lexical even though it "contains Greek".
#   ͵ (U+0375) lower numeral sign (thousands multiplier prefix)
#   Ϛϛ (U+03DA/03DB) stigma — numeral 6
#   Ϙϙ Ϟϟ (U+03D8/03D9, U+03DE/03DF) archaic/classical koppa — numeral 90
#   Ϡϡ (U+03E0/03E1) sampi — numeral 900
#
# ʹ (U+0374 GREEK NUMERAL SIGN, the "keraia") and its modifier-letter
# lookalike ʹ (U+02B9 MODIFIER LETTER PRIME, occasionally substituted for it in
# some digitizations -- zero occurrences in this corpus as of the 2026-07-16
# audit, but treated identically since both mark the same thing) is the
# TRAILING mark on a Greek alphabetic numeral (Lives' catalogue-of-works
# lists cite book counts this way: "αʹ" = "1", "ρξεʹ" = "165"; Meditations'
# manuscript colophon "Γρανούᾳ αʹ"; Discourses' chapter heading "ιβʹ. Περὶ προσοχὴς" = "12. On
# attention"). It has no Beta Code transliteration of its own, so a
# keraia-suffixed numeral is non-lexical like the other alphabetic-numeral
# forms above -- but unlike them, the keraia stays in the token's surface
# text `t` (it is not editorial punctuation), only `k` is omitted.
_KERAIA = 'ʹʹ'

_GREEK_NUMERAL_SIGNALS = "͵ϚϛϘϙϞϟϠϡ" + _KERAIA

# Full alphabetic-numeral grammar: a real numeral token (checked against the
# lives build — every no-`k` token containing Greek letters there is one of
# 'ιϛ', 'ϛ', '͵βυκ', '͵βψμ', '͵βων', '͵δοε', '͵δσλθ') is an OPTIONAL leading
# lower numeral sign (a thousands multiplier, only ever a prefix) followed by
# one or more numeral-value letters and nothing else. The value letters are
# the plain (unaccented) lowercase/uppercase Greek alphabet plus digamma
# (archaic numeral 6, alongside stigma) — never the FINAL sigma 'ς', which
# the Milesian system never uses (200 is medial 'σ' even token-final), so a
# token ending 'ς' is never mistaken for a numeral. A trailing _KERAIA
# character is stripped from the body before this check (see
# _is_greek_numeral below) rather than being listed here — it is not a
# value letter, just the numeral's own closing mark.
_NUMERAL_LETTERS = (
    "αβγδεζηθικλμνξοπρστυφχψω"
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
    "ϝϜ"
    "ϚϛϘϙϞϟϠϡ"
)

# Attic ACROPHONIC numerals: a wholly separate, non-alphabetic notation
# system (Unicode "Ancient Greek Numbers" block, U+10140-U+1018F) that an
# inscription can quote verbatim mixed in with the ordinary Milesian
# alphabetic-numeral letters above — Anaxagoras testimonia A4a's Marmor
# Parium quotation "ἔτη Η𐅄ΔΔΓΙΙΙΙ" (179) and A11's "ἔτη 𐅄ΔΔΔΔ" (90): Η/Δ/Γ/Ι
# there are the SAME plain Greek majuscules `_NUMERAL_LETTERS` already
# recognizes, glued (no separating space) onto U+10144 GREEK ACROPHONIC
# ATTIC FIFTY. Every character in this block carries Unicode general
# category Nl or No ("letter number"/"other number"), never "L*", so
# `_is_greek_letter` (which requires category "L*") already excludes it —
# `_contains_greek` needs no change. But `_is_greek_numeral`'s own
# value-letter check must recognize it too, or a mixed acrophonic+
# alphabetic token like "Η𐅄ΔΔΓΙΙΙΙ" is neither a numeral (an unrecognized
# character in the body) nor a real word (`to_beta_key` cannot
# transliterate an acrophonic numeral either way) — it would hard-fail as
# a key_failure instead of being recognized as the non-lexical numeral it
# is. The character itself must stay in the token/display text (it is
# genuine ancient inscription content, not an export artifact) — only the
# `k` lookup key is omitted, exactly like every other numeral shape here.
_ANCIENT_GREEK_NUMBERS_LO = 0x10140
_ANCIENT_GREEK_NUMBERS_HI = 0x1018F


def _is_ancient_greek_number_char(ch: str) -> bool:
    return _ANCIENT_GREEK_NUMBERS_LO <= ord(ch) <= _ANCIENT_GREEK_NUMBERS_HI


def _is_greek_numeral(token: str) -> bool:
    """True when the ENTIRE token — not just some character within it — is
    Greek alphabetic-numeral (Milesian) or acrophonic (Attic) numeral
    notation rather than a lexical word. A token that merely CONTAINS a
    numeral signal (e.g. malformed "ϛλόγος") is not a numeral and must
    return False here, so the caller fails it loudly as a real word instead
    of silently demoting it.

    A trailing _KERAIA character (see above) is stripped from the body
    before the value-letter check, so a numeral like "α" with a keraia
    suffix appended is recognized the same way "ιϛ" is. A bare keraia with
    nothing before it (no leading numeral-value letters, and not even a
    lower-numeral-sign prefix) leaves an empty body and correctly returns
    False here — that is not a real numeral, so it falls through to the
    ordinary key-failure path instead of being silently demoted."""
    if not token or not any(
        ch in _GREEK_NUMERAL_SIGNALS or _is_ancient_greek_number_char(ch)
        for ch in token
    ):
        return False
    body = token[1:] if token[0] == "͵" else token
    if body and body[-1] in _KERAIA:
        body = body[:-1]
    return bool(body) and "͵" not in body and all(
        ch in _NUMERAL_LETTERS or _is_ancient_greek_number_char(ch) for ch in body
    )


# Damaged-papyrus columns (manifest `citation.dk_damaged_columns`: Protagoras
# A30, Democritus A99a, Empedocles B142 — the three columns printing a papyrus
# transcription with lacuna dots). The letters surviving around a lacuna would
# otherwise key like words and open the dictionary popup on junk — mostly
# honest misses, but a bare "η" fold-matched 13 readings and B142's uppercase
# run "ΛΟΥΕ" resolved to λούω "wash". John's ruling 2026-08-29
# (REVIEW-CHECKLIST item 95, option b): inside these columns ONLY, a token
# loses its `k` (and so its popup — Reader renders an unkeyed token as plain
# text) when it is a DIACRITIC-FREE scrap: a single bare letter (a real
# one-letter word — ἡ, ἤ, ὦ — always carries a mark), a fragment glued to a
# lacuna dot run of 2+ periods (a single trailing period is ordinary sentence
# punctuation), or an all-capitals damage run. Everything else keeps its key,
# deliberately including the correctly accentless enclitics (που, πως), the
# recoverable τωι/φασιν, and dotless lowercase fragments like προκατα (their
# popups are honest "No analysis found" misses). Display `t`/`o` are never
# touched — this gates key emission only, and skips the key ATTEMPT (these
# are not key failures).
_DK_LACUNA_DOT_EDGE_RE = re.compile(r"^\.\.|\.\.$")


def _is_dk_damage_fragment(raw: str, token: str) -> bool:
    """True when `token` (the cleaned form; `raw` is the whitespace-split
    original, dots still attached) is a surviving scrap of a damaged papyrus
    transcription rather than a word — see the block comment above."""
    nfd = unicodedata.normalize("NFD", token)
    if any(unicodedata.combining(ch) for ch in nfd):
        return False
    letters = [ch for ch in token if _is_greek_letter(ch)]
    if not letters:
        return False
    if len(token) == 1:
        return True
    if all(ch.isupper() for ch in letters):
        return True
    return bool(_DK_LACUNA_DOT_EDGE_RE.search(raw))


def _clean(raw: str, punctuation: str) -> tuple[str, bool]:
    """Strip punctuation/sigla from both edges; keep a trailing elision
    apostrophe. Returns (token, had_sigla)."""
    had_sigla = any(ch in _SIGLA for ch in raw)
    strip = punctuation + _SIGLA
    token = raw.strip(strip)
    # Inner sigla (rare: † within a corrupt word, <> around a supplement
    # inside a word) are removed too; the surface form keeps only letters
    # and apostrophes.
    token = "".join(ch for ch in token if ch not in _SIGLA)
    # ’ (U+2019) survives the edge strip because it doubles as the elision
    # apostrophe (δ’, κατ’). When it instead closes a quotation the TLG wraps
    # around a quoted word (the Apology's Homer lines, the Timaeus' oracle) or a
    # meta-linguistic citation, it trails the word's own punctuation — ,’ .’ ;’ —
    # so a comma or stop stays trapped against the word and cannot transliterate.
    # A closing quote is an apostrophe NOT sitting directly after a Greek letter
    # (an elision apostrophe always follows the letter it elides); peel it and
    # re-strip the punctuation it exposed, looping until the edge is a real word.
    while token and token[-1] in _APOSTROPHES and not (
        len(token) >= 2 and _is_greek_letter(token[-2])
    ):
        token = token[:-1].strip(strip)
    return token, had_sigla


def _preceded_by_greek_letter(s: str, idx: int) -> bool:
    """True when the nearest character before position `idx` in `s` that is
    NOT an editorial sigil is a Greek letter. Mirrors the letter `_clean()`'s
    trailing-apostrophe loop sees at this point (its `token` has already had
    interior sigla removed by then), so a sigil sitting between a letter and
    a trailing apostrophe doesn't change the elision-vs-closing-quote call."""
    j = idx - 1
    while j >= 0 and s[j] in _SIGLA:
        j -= 1
    return j >= 0 and _is_greek_letter(s[j])


def _surface(raw: str, punctuation: str) -> tuple[str, int]:
    """The literal surface span of `raw` for `t`: only `_PUNCT` (ordinary
    punctuation) is trimmed from the edges; `_SIGLA` (editorial marks) are
    left in place everywhere, so the result is always a plain contiguous
    substring of `raw` (and, since `raw` itself is `text[m.start():m.end()]`
    for some regex match, of the line's `text`). Returns
    `(surface_text, start_offset_within_raw)`.

    The trailing-apostrophe peel mirrors `_clean()`'s closing-quote heuristic
    (an apostrophe not preceded by a Greek letter closes a quotation rather
    than eliding a vowel, so it — and any punctuation it exposes — is
    trimmed too), but looks past sigla via `_preceded_by_greek_letter` rather
    than removing them, since removal is exactly what this function must
    not do."""
    start, end = 0, len(raw)
    while start < end and raw[start] in punctuation:
        start += 1
    while end > start and raw[end - 1] in punctuation:
        end -= 1
    while (
        end > start
        and raw[end - 1] in _APOSTROPHES
        and not _preceded_by_greek_letter(raw, end - 1)
    ):
        end -= 1
        while end > start and raw[end - 1] in punctuation:
            end -= 1
    return raw[start:end], start


def _is_no_op_numeral(_token: str) -> bool:
    """Latin has no documented numeral-notation hazard analogous to Greek's
    alphabetic/acrophonic numerals (memo §0/§4): Roman numerals are ordinary
    Latin letters and, like any other unmatched form, simply miss the
    analyses table under the no-lexicon posture (memo §4.2) — that is a
    stage4 lookup-miss concern, not a stage3 lexical-gating one. Always
    False, so a Latin token that fails to key (unreachable today — see
    latin.to_latin_key's docstring) is never silently swallowed."""
    return False


def _to_latin_lookup_key(token: str) -> str:
    """Latin key derivation only: edge-strip ASCII apostrophes, then
    `to_latin_key`.

    Shared `_clean` / `_PUNCT` deliberately leave `'` alone: on the Greek
    path the same codepoint is in `_APOSTROPHES` and is kept when it follows
    a Greek letter (elision: δ’, κατ’), and `_PUNCT` also omits the curly
    close-quote mates that double as elision marks. PHI Latin, by contrast,
    glues a leading ASCII `'` onto quoted words (`'honestum`) as a
    quotation opener — not part of the lemma — so a future latin-analyses
    lookup would miss if the key kept it. Only edge `'` is stripped
    (``str.strip("'")``); an interior apostrophe is preserved. Surface `t`
    is independent (`_surface`) and is not touched here. Greek dispatch
    still calls `to_beta_key` directly — this helper is Latin-path-only.

    Cross-referenced by `lined.py`'s `LATIN_LINED.frag_start_glued_chars`
    (`stage1_latin.py`): since `'` survives edge-stripping into surface `t`
    here, the lined-source fragment-start advance must land ON a leading
    `'`, not skip past it — the same fact this docstring states, read from
    the other side."""
    return to_latin_key(token.strip("'"))


# language -> (key_fn, contains_letter_fn, is_numeral_fn, key_fn_name, label)
_LANGUAGE_DISPATCH = {
    "grc": (to_beta_key, _contains_greek, _is_greek_numeral, "to_beta_key", "Greek"),
    "lat": (
        _to_latin_lookup_key,
        _contains_latin,
        _is_no_op_numeral,
        "to_latin_key",
        "Latin",
    ),
}


def tokenize(
    spine: dict,
    language: str = "grc",
    lexicon: bool = True,
    damaged_columns: frozenset[str] = frozenset(),
) -> tuple[dict, list[dict], list[dict]]:
    """`lexicon=False` (Wave 2 §4.2's no-lexicon-first posture — a work-level
    switch, `work.lexicon: false`, first used by Cicero's De Officiis, Batch
    1a) skips key derivation ENTIRELY: every token gets `t`/`o` only, never a
    `k`, regardless of language or letter content. This is deliberately not
    "attempt to key, then discard the result" — a no-lexicon work has no
    `latin-analyses.txt`/LSJ lookup coming later in the pipeline for these
    keys to ever resolve against, so computing and emitting them would be
    dead data. When `lexicon=True` on Latin, keys go through
    `_to_latin_lookup_key` (edge-strips ASCII `'` quotation glue before
    `to_latin_key`); with `lexicon=False` that path is never entered, so
    de-officiis-style builds emit the same `t`/`o`-only tokens as before."""
    if language not in _LANGUAGE_DISPATCH:
        raise ValueError(f"unsupported language: {language!r}")
    key_fn, contains_letter, is_numeral, key_fn_name, lang_label = _LANGUAGE_DISPATCH[language]
    clean_punctuation, surface_punctuation = _LANGUAGE_PUNCT[language]

    segments_out = []
    sigla_log: list[dict] = []
    key_failures: list[dict] = []
    for seg in spine["segments"]:
        col_damaged = seg["column"] in damaged_columns
        lines_out = []
        for line in seg["lines"]:
            ref = f"{seg['column']}{line['n']}"
            text = line["text"]
            tokens = []
            # Em-dashes glue clauses together with no spaces; they are
            # separators, not part of any token.
            for m in re.finditer(r"[^\s—]+", text):
                raw = m.group(0)
                token, had_sigla = _clean(raw, clean_punctuation)
                if had_sigla:
                    sigla_log.append({"ref": ref, "raw": raw, "kept": token})
                if not token:
                    continue
                surface, surface_start = _surface(raw, surface_punctuation)
                entry = {"t": surface, "o": m.start() + surface_start}
                # Only attempt to key a token that contains at least one
                # letter of this work's language — a token with none (bare
                # numerals, inline apparatus in the OTHER script) is
                # NON-LEXICAL by definition and gets no `k`, never a key_fn
                # attempt (which, for Greek, would fail anyway; for Latin,
                # to_latin_key never fails, so the gate must be explicit).
                # `lexicon=False` short-circuits this whole attempt (see the
                # function docstring) — no work declaring it is skipped here.
                # A damage scrap in a `dk_damaged_columns` column skips the
                # attempt too (see `_is_dk_damage_fragment`'s block comment;
                # item 95 ruling) — deliberately not a key failure.
                if lexicon and contains_letter(token) and not (
                    col_damaged and _is_dk_damage_fragment(raw, token)
                ):
                    try:
                        key = key_fn(token)
                    except ValueError as err:
                        key, error = None, str(err)
                    else:
                        error = None if key else f"{key_fn_name} produced an empty key"
                    if error is None:
                        entry["k"] = key
                    elif not is_numeral(token):
                        # A WORD token that cannot key is a bug (an
                        # unhandled character/mark reaching key_fn) —
                        # collect it here and fail loudly below rather than
                        # silently demoting a real word to non-lexical.
                        key_failures.append({"ref": ref, "token": token, "error": error})
                    # else: a recognized numeral notation that failed to key
                    # (Greek alphabetic/acrophonic numerals) — omit `k`;
                    # this is expected, not a failure.
                # else: non-lexical — no letters of this language at all
                # (inline other-script apparatus, editor names, bare
                # numerals) — omit `k` entirely; this is expected.
                tokens.append(entry)
            lines_out.append({"n": line["n"], "tokens": tokens})
        segments_out.append(
            {"id": seg["id"], "book": seg["book"], "column": seg["column"], "lines": lines_out}
        )
    if key_failures:
        raise ValueError(
            f"{len(key_failures)} {lang_label} token(s) failed to produce a "
            f"lookup key (this indicates an unhandled character/mark in "
            f"{key_fn_name}, not an expected non-lexical token): "
            + "; ".join(
                f"{f['ref']} {f['token']!r} ({f['error']})" for f in key_failures[:10]
            )
            + (" ..." if len(key_failures) > 10 else "")
        )
    return (
        {"work": spine["work"], "segments": segments_out},
        sigla_log,
        key_failures,
    )


# stage1 spine producer per work.language, keyed by the filename each
# producer writes under build/stage1/. 'grc' -> stage1_greek.py;
# 'lat' -> stage1_latin.py (Wave 2 Batch 1a — Cicero's De Officiis, the
# first real PHI work). stage2_validate.py and stage7_emit.py read this same
# mapping (imported, not re-declared) so all three stages agree on where a
# given language's spine lives.
_SPINE_FILENAMES = {"grc": "greek_spine.json", "lat": "latin_spine.json"}


def run(manifest: Manifest) -> Path:
    language = manifest.language
    spine_file = _SPINE_FILENAMES.get(language)
    if spine_file is None:
        raise NotImplementedError(
            f"stage3 has no stage1 spine producer wired for "
            f"work.language={language!r} yet"
        )
    spine = json.loads(
        (BUILD_DIR / "stage1" / spine_file).read_text(encoding="utf-8")
    )
    # Same manifest read as stage1's damage-regex gate: only a column
    # explicitly whitelisted in `citation.dk_damaged_columns` gets the
    # damage-scrap key omission (see `_is_dk_damage_fragment`).
    damaged_columns = frozenset(
        (manifest.data.get("citation") or {}).get("dk_damaged_columns", []) or []
    )
    tokens, sigla_log, key_failures = tokenize(
        spine, language, manifest.lexicon, damaged_columns
    )
    out_dir = BUILD_DIR / "stage3"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "tokens.json"
    out.write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")
    (out_dir / "sigla_log.json").write_text(
        json.dumps(sigla_log, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "key_failures.json").write_text(
        json.dumps(key_failures, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out
