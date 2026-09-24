from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.beta import capital_key, lookup_variants, to_beta_key


def test_to_beta_key_keeps_accents_breathings_iota_subscript_and_final_sigma():
    assert to_beta_key("ἀγαθός") == "a)gaqo/s"
    assert capital_key(to_beta_key("Ἀγαθός")) == "*)agaqo/s"
    assert to_beta_key("τῷ") == "tw=|"
    assert to_beta_key("λόγος") == "lo/gos"


def test_to_beta_key_normalizes_grave_and_elision_apostrophe():
    assert to_beta_key("ἄνθρωπός") == "a)/nqrwpos"
    assert to_beta_key("κατ’") == "kat'"


def test_to_beta_key_normalizes_every_apostrophe_variant_to_ascii():
    # John, 2026-09-23 ruling item 3: the client's search fold
    # (shared/lib/search.ts's greekFold) must agree with THIS key fold on one
    # canonical apostrophe -- real corpus text renders elision with all four
    # marks _APOSTROPHES lists (straight, curly, koronis, modifier-letter),
    # and to_beta_key is where that normalization to ASCII "'" already
    # happens, upstream of stage6_search.py's fold_lemma. This test locks
    # that contract so a future _APOSTROPHES edit can't silently diverge from
    # the client's copy of the same set.
    assert to_beta_key("κατ'") == "kat'"   # U+0027 straight apostrophe
    assert to_beta_key("κατ’") == "kat'"   # U+2019 right single quotation mark
    assert to_beta_key("κατ᾽") == "kat'"   # U+1FBD koronis
    assert to_beta_key("κατʼ") == "kat'"   # U+02BC modifier letter apostrophe


def test_lookup_variants_expands_diaeresis_and_capital_lookup_keys():
    assert lookup_variants("pro+i/ento", capitalized=True) == [
        "pro+i/ento",
        "proi/ento",
        "pro(i/ento",
        "pro)i/ento",
        "*pro+i/ento",
        "*proi/ento",
        "*pro(i/ento",
        "*pro)i/ento",
    ]


def test_lookup_variants_preserves_homograph_digits_in_existing_keys():
    assert capital_key("tis1") == "*tis1"
    assert lookup_variants("tis1", capitalized=True) == ["tis1", "*tis1"]


def test_to_beta_key_rejects_digits_in_surface_tokens():
    with pytest.raises(ValueError, match="cannot transliterate"):
        to_beta_key("τις1")


def test_to_beta_key_drops_combining_dot_below():
    # U+0323 marks a papyrologically doubtful letter (Epictetus Discourses
    # 1.18's ἐ̣, ν̣, ἀ̣λ̣λ̣ω̣σ̣) — it has no Beta Code transliteration and no
    # bearing on the word's identity, so it must be dropped like macron/breve,
    # not raise. Before this fix to_beta_key raised ValueError here.
    assert to_beta_key("ἐ" + "̣") == to_beta_key("ἐ")
    assert to_beta_key("ν" + "̣") == to_beta_key("ν")
    assert to_beta_key("ἀ̣λ̣λ̣ω̣σ̣") == to_beta_key("ἀλλωσ")


def test_to_beta_key_drops_combining_dot_above():
    # U+0307: the SAME papyrologically-doubtful-letter mark as dot-below
    # above, just the alternate placement Diogenes' export uses on some
    # damaged-papyrus letters (Wave 1c Sophists batch 2, Antiphon 87 B44,
    # the POxy 1364 papyrus). Dropped identically. Synthetic fixture forms.
    assert to_beta_key("δ" + "̇") == to_beta_key("δ")
    assert to_beta_key("λ̇ο̇γ̇") == to_beta_key("λογ")
