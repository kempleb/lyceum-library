from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.latin import (
    enclitic_variants,
    fold,
    lookup_variants,
    to_latin_key,
)


def test_to_latin_key_lowercases_and_nfc_normalizes():
    assert to_latin_key("Virtus") == "virtus"
    assert to_latin_key("HOMO") == "homo"
    # A precomposed and a decomposed form of the same accented letter (not
    # expected in PHI's plain Latin, but the key derivation must not choke
    # on or diverge for either encoding) fold to the same NFC key.
    precomposed = "é"  # é
    decomposed = "é"  # e + combining acute
    assert to_latin_key(precomposed) == to_latin_key(decomposed)


def test_to_latin_key_never_raises_and_is_never_empty_for_nonempty_input():
    # Unlike beta.to_beta_key, to_latin_key has no restricted character set --
    # it cannot fail to produce A key, only fail to find one in the analyses
    # table later (a stage4 concern, not this module's).
    for token in ("virtus", "XII", "35", "quisque", "Aeneas"):
        key = to_latin_key(token)
        assert key
        assert key == key.lower()


def test_enclitic_variants_offers_split_host_as_fallback_only():
    # memo example: "arma virumque" -> "virum" is offered as a variant.
    assert enclitic_variants("virumque") == ["virum"]
    assert enclitic_variants("populusque") == ["populus"]


def test_enclitic_variants_covers_ne_and_ve_suffixes():
    assert enclitic_variants("possitne") == ["possit"]
    assert enclitic_variants("sive") == ["si"]


def test_enclitic_variants_does_not_split_false_enclictics():
    # "atque"/"neque" are their own words, not host + "-que"/"-ne" -- the
    # stoplist suppresses the misleading split entirely.
    assert enclitic_variants("atque") == []
    assert enclitic_variants("neque") == []
    assert enclitic_variants("itaque") == []
    assert enclitic_variants("denique") == []


def test_enclitic_variants_never_mutates_the_key_and_respects_min_host_len():
    # A key with no enclitic suffix, or too short a host, yields no variants
    # -- enclitic_variants only ever ADDS candidates, never changes `key`.
    assert enclitic_variants("verbum") == []
    # "ve" suffix on a 3-char word leaves a 1-char host -- below _MIN_HOST_LEN.
    assert enclitic_variants("ave") == []


def test_lookup_variants_tries_whole_form_first():
    # "quisque" is itself a lemma (memo's own example) -- the whole form must
    # be the FIRST candidate so a caller's whole-form-first analyses lookup
    # resolves it correctly before ever considering the "quis" split.
    assert lookup_variants("quisque") == ["quisque", "quis"]
    assert lookup_variants("virumque") == ["virumque", "virum"]
    assert lookup_variants("atque") == ["atque"]


def test_lookup_variants_not_capitalized_never_offers_the_capital_form():
    # Default (capitalized=False, and every pre-existing call site above)
    # is unaffected by the case-fold fix -- no capital-key candidate is
    # ever offered unless the caller says the surface token was itself
    # capitalized.
    assert lookup_variants("cicero") == ["cicero"]


def test_lookup_variants_capitalized_offers_the_capital_form_last():
    # Case-fold fix (Wave 2 Batch 1b review, item 2): latin-analyses.txt
    # keys proper names CAPITALIZED ("Cicero", "Panaetio", "Athenis" are
    # the table's REAL keys -- confirmed against the live Diogenes file;
    # there is no lowercase "cicero" entry at all) -- to_latin_key always
    # lowercases, so the plain form alone would miss every one of them.
    # Tried LAST (after the whole form and any enclitic split), mirroring
    # beta.lookup_variants' capital-key fallback ordering.
    assert lookup_variants("cicero", capitalized=True) == ["cicero", "Cicero"]
    assert lookup_variants("panaetio", capitalized=True) == ["panaetio", "Panaetio"]
    assert lookup_variants("athenis", capitalized=True) == ["athenis", "Athenis"]


def test_lookup_variants_capitalized_also_capitalizes_the_enclitic_split():
    # The capitalized fallback applies to EVERY candidate already collected
    # (whole form + enclitic splits), not just the whole form.
    assert lookup_variants("ciceroque", capitalized=True) == [
        "ciceroque", "cicero", "Ciceroque", "Cicero",
    ]


def test_fold_unifies_u_v_and_venus_uenus_equivalence():
    assert fold("venus") == fold("uenus")
    assert fold("vita") == fold("uita")


def test_fold_unifies_i_j_and_coniunx_conjunx_equivalence():
    assert fold("coniunx") == fold("conjunx")


def test_fold_is_lowercase_and_letters_only():
    assert fold("Virtus!") == fold("virtus")
    assert fold("VIRTUS") == "uirtus"


def test_fold_strips_macron_to_base_letter_not_to_nothing():
    # Regression: an earlier version of fold() stripped non-[a-z'] characters
    # BEFORE decomposing, so a macron-carrying vowel (a single precomposed
    # codepoint, not in [a-z']) was deleted whole rather than reduced to its
    # base letter -- "mālus" wrongly folded to "mlus" instead of "malus".
    assert fold("mālus") == "malus"  # mālus = mālus (a + macron, precomposed)


def test_fold_strips_breve_to_base_letter():
    assert fold("mălus") == "malus"  # mălus = mălus (a + breve, precomposed)


def test_fold_expands_ae_ligature():
    # "æ" has no Unicode canonical decomposition to "a"+"e" -- NFD alone
    # would leave it untouched (and the strip regex would then delete it
    # outright), so fold() must expand it explicitly before decomposing.
    assert fold("cælum") == fold("caelum")  # cælum == caelum
    assert fold("cælum") == "caelum"


def test_fold_expands_oe_ligature():
    assert fold("fœdus") == fold("foedus")  # fœdus == foedus


def test_stoplist_suppresses_split_for_all_eleven_entries():
    # The full _FALSE_ENCLITIC_STOPLIST (memo §4.1) -- every listed word must
    # yield no enclitic-split variant, not just the first few checked above.
    for word in (
        "atque", "neque", "itaque", "absque", "denique", "undique",
        "utique", "quoque", "namque", "plerumque", "ubique",
    ):
        assert enclitic_variants(word) == [], word


def test_hyphenated_token_key_keeps_the_hyphen():
    # Policy (documented on to_latin_key): an interior editorial hyphen (the
    # "utrum-ne" shape) is not stripped or specially handled -- it stays in
    # the key verbatim.
    assert to_latin_key("utrum-ne") == "utrum-ne"


def test_hyphenated_token_lookup_variants_does_not_crash():
    # lookup_variants may offer a variant with a dangling trailing hyphen
    # (the enclitic-split candidate for a hyphenated host) -- that variant
    # simply won't be found in the analyses table later; this is a graceful
    # degradation (an ordinary unmatched-token miss in stage4), never an
    # exception. Behavior test only -- no new splitting mechanism.
    variants = lookup_variants("utrum-ne")
    assert variants[0] == "utrum-ne"  # whole form tried first, unchanged
    assert all(isinstance(v, str) for v in variants)
