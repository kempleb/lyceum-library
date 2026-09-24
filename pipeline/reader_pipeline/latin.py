"""Latin key derivation and search fold (Wave 2 Batch 0).

Companion to beta.py's Greek key derivation, for PHI Latin surface tokens.
See docs/wave2-latin-design.md §4 (the design memo this module implements).

Key differences from Greek:
  - No transliteration. PHI's Latin text is already plain Latin with the
    classical u/v convention applied at the source, so the lookup/display
    key IS the lowercased surface form (NFC-normalized) -- not a re-encoding
    into some other alphabet, and no i/j or u/v REWRITE of the key (that
    normalization is a SEARCH-fold affordance only -- see fold() below).
  - No lexicon assumed. A Latin key may legitimately resolve to nothing in
    latin-analyses.txt -- Wave 2's declared no-lexicon-first posture (memo
    §4.2). Unlike Greek's to_beta_key, to_latin_key never raises: it cannot
    fail to produce a key, only fail to find one in the analyses table
    later (stage4's job, not this module's).
  - Enclitic split offers ADDITIONAL lookup variants, never a destructive
    edit of the key: -que/-ne/-ve are stripped as a FALLBACK candidate,
    tried only after the whole form itself. Morpheus (via latin-analyses.txt)
    already resolves most enclitics on its own; the split exists for the
    ~10% of forms it misses (memo §4.1's stated failure mode). A word that
    is itself a lemma ending in one of those letters (e.g. "quisque") still
    resolves correctly because the whole form is tried first.
  - Search folding (fold()) unifies u/v and i/j into single classes so a
    search for "uita" finds "vita" and "coniunx" finds "conjunx" regardless
    of the edition's spelling convention -- a MATCHING affordance only; the
    displayed text and the lemma-page key keep the source spelling.
"""

from __future__ import annotations

import re
import unicodedata

# Enclitic suffixes offered as ADDITIONAL lookup variants -- never destructive
# of the base key (memo §4.1). Checked longest-first is unnecessary since they
# share no overlapping tails, but the order here is just declaration order.
_ENCLITICS = ("que", "ne", "ve")

# A split host shorter than this is not offered as a variant -- guards against
# reducing very short tokens (already rare after tokenization) to a 0-1
# character "host" that could never be a real lookup candidate anyway.
_MIN_HOST_LEN = 2

# Minimal explicit stoplist: common, high-frequency Latin words that happen to
# END in one of the enclitic suffixes above but whose stripped "host" is not
# the word's own stem -- splitting would offer a real-but-WRONG word as a
# variant (e.g. "atque" -/-> "at": both are genuine Latin words, but "atque"
# is not "at" + "-que"). The design memo (§4.1) leaves this list open
# ("a word genuinely ending in those letters ... must not be force-split");
# this repo resolves that by suppressing the split candidate entirely for
# these words, rather than trying to enumerate every legitimate word ending
# in -que/-ne/-ve (e.g. "quisque", "utrumne" un-stoplisted below need no
# special-casing at all: the whole form is always tried FIRST in
# lookup_variants, so they resolve correctly as long as they are themselves
# in latin-analyses.txt; the stoplist only suppresses a noisy/misleading
# FALLBACK variant for words common enough that a wrong split is worse than
# no split). Extend this list if a future analyses-table audit finds another
# common false enclitic producing a misleading fallback hit.
_FALSE_ENCLITIC_STOPLIST = frozenset({
    "atque", "neque", "itaque", "absque", "denique", "undique",
    "utique", "quoque", "namque", "plerumque", "ubique",
})


def to_latin_key(surface: str) -> str:
    """Base lookup/display key for a Latin surface token: NFC-normalized,
    lowercased. No transliteration, no u/v or i/j rewrite -- PHI already
    applies the classical u/v convention in the source text, so this key IS
    the lowercased surface, not a re-encoding (memo §4.1). Unlike
    beta.to_beta_key, this never raises: any non-empty input produces a
    non-empty key.

    Hyphenated-token policy: a token that itself contains an interior hyphen
    (an editorial mark, e.g. the "utrum-ne" shape occasionally used to flag
    an enclitic boundary) gets NO special handling here -- the hyphen is not
    stripped, so it stays in the key verbatim (stage3's tokenizer only
    edge-trims ordinary punctuation, never interior characters, for Latin --
    see stage3_tokenize.py's `_clean`/`_surface`). `lookup_variants` below
    may then offer an enclitic-split variant that itself carries a dangling
    trailing hyphen (e.g. "utrum-" from "utrum-ne"); that variant simply
    fails to match anything in latin-analyses.txt like any other miss --
    stage4 falls back gracefully (an unmatched-token entry, not a crash).
    No hyphen-aware splitting is implemented; this is a documented
    degradation, not a bug."""
    return unicodedata.normalize("NFC", surface).lower()


def enclitic_variants(key: str) -> list[str]:
    """Additional lookup-variant hosts for `key` with a possible enclitic
    suffix stripped (-que/-ne/-ve) -- NEVER mutates `key` itself, only offers
    extra fallback candidates a caller may also try (memo §4.1). A key in
    `_FALSE_ENCLITIC_STOPLIST` yields no variants (see module docstring)."""
    if key in _FALSE_ENCLITIC_STOPLIST:
        return []
    variants = []
    for suf in _ENCLITICS:
        if key.endswith(suf) and len(key) - len(suf) >= _MIN_HOST_LEN:
            variants.append(key[: -len(suf)])
    return variants


def _capitalized_key(key: str) -> str:
    """latin-analyses.txt's own capitalization convention for proper names:
    title case, first letter only ("Cicero", "Panaetio", "Athenis") --
    distinct from Greek's '*'-prefixed capital-key namespace (capital_key
    in beta.py); Latin's analyses table just capitalizes the ordinary key."""
    return key[:1].upper() + key[1:] if key else key


def lookup_variants(key: str, capitalized: bool = False) -> list[str]:
    """Candidate latin-analyses.txt keys to try, in order: the whole form
    FIRST (so a genuine lemma ending in -que/-ne/-ve, e.g. "quisque",
    resolves before any split is considered), then the enclitic-split
    variant(s) as a fallback (memo §4.1), then -- only when the SURFACE
    token was itself capitalized -- each of those same candidates'
    capitalized form.

    Case-fold fix (Wave 2 Batch 1b review, item 2; Grok-flagged, 617/930
    occurrences): latin-analyses.txt keys proper names CAPITALIZED (Cicero,
    Panaetio, Athenis, ...), but to_latin_key always lowercases (memo §4.1
    -- the key IS the lowercased surface), so every proper-name lookup
    missed until this fallback. Gated on `capitalized` (not tried
    unconditionally) and tried LAST, mirroring beta.lookup_variants'
    capital-key fallback ordering: an ordinary word that merely happens to
    start a sentence still resolves via its lowercase key above (it has
    one -- ordinary words are never capital-keyed in the table), so this
    never risks preferring a wrong capitalized homograph over a right
    lowercase one. Praenomina abbreviations (M., C., L., Q., P., ...) are
    genuinely absent from the table under ANY casing and still miss
    gracefully -- this fixes case-fold misses, not true gaps."""
    variants = [key]
    for v in enclitic_variants(key):
        if v not in variants:
            variants.append(v)
    if capitalized:
        for v in list(variants):
            cap = _capitalized_key(v)
            if cap not in variants:
                variants.append(cap)
    return variants


# Search-fold: keep only base Latin letters + apostrophe, mirroring stage6's
# Greek fold_lemma (which keeps only [a-z']) -- applied AFTER NFD decomposition
# and the u/v and i/j unification below, so any residual non-letter character
# (combining diacritics included) is dropped too.
_FOLD_STRIP = re.compile(r"[^a-z']")

# Ligatures that PHI/reprint sources occasionally use in place of the two-letter
# spelling (a scanned/OCR'd edition, or a source that hasn't normalized to the
# classical digraph) -- expanded BEFORE NFD decomposition because neither has a
# Unicode canonical decomposition to its component letters (NFD/NFKD both leave
# "æ"/"œ" as a single codepoint), so decomposition alone would not recover them.
_LIGATURES = {"æ": "ae", "œ": "oe"}


def fold(key: str) -> str:
    """Search-fold form of a Latin key: lowercase, with u/v unified to 'u'
    and i/j unified to 'i' -- so "uita" folds the same as "vita", and
    "coniunx" folds the same as "conjunx" (memo §4.1). This is a matching
    affordance only: to_latin_key (the displayed/lemma-page key) is
    untouched by this.

    NFD-decomposes BEFORE stripping non-base-letter characters, so a
    macron/breve-carrying vowel (e.g. "mālus", "ă") folds to its BASE letter
    ("malus") rather than being deleted outright (which would have wrongly
    produced "mlus") -- NFD splits the precomposed letter into base + a
    combining mark, and the combining mark (not in [a-z']) is what the strip
    regex removes. The æ/œ ligatures are expanded to their two-letter
    spelling first, since Unicode NFD does not decompose them (see
    _LIGATURES above)."""
    folded = key.lower()
    for ligature, expansion in _LIGATURES.items():
        folded = folded.replace(ligature, expansion)
    folded = unicodedata.normalize("NFD", folded)
    folded = folded.replace("v", "u").replace("j", "i")
    return _FOLD_STRIP.sub("", folded)
