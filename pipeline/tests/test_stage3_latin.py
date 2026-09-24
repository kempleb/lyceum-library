from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage3_tokenize import tokenize


def _latin_spine(*lines: str) -> dict:
    """A single-segment spine wrapping the given raw Latin line texts,
    mirroring test_stage2_stage3.py's `_spine_with_lines` for Greek."""
    return {
        "work": "TST-LAT",
        "segments": [
            {
                "id": "1:1.1",
                "book": 1,
                "column": "1.1",
                "lines": [{"n": i + 1, "text": text} for i, text in enumerate(lines)],
            },
        ],
    }


def test_latin_tokens_get_lowercased_keys():
    spine = _latin_spine("Officium honestumque colimus.")
    tokens, sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []
    words = tokens["segments"][0]["lines"][0]["tokens"]
    keyed = {t["t"]: t["k"] for t in words if "k" in t}
    assert keyed["Officium"] == "officium"
    assert keyed["colimus"] == "colimus"
    # "honestumque" keeps its own literal key -- enclitic splitting is a
    # stage4 lookup-variant concern, not a stage3 key-derivation one.
    assert keyed["honestumque"] == "honestumque"


def test_latin_surface_text_is_untouched_by_lowercasing():
    # `t` (surface) preserves the original casing/orthography; only `k`
    # (the lookup key) is lowercased -- same t/k split as Greek. Trailing
    # ordinary punctuation ("." in _PUNCT) is still edge-trimmed from both.
    spine = _latin_spine("Cicero scribit.")
    tokens, _sigla_log, _key_failures = tokenize(spine, "lat")
    words = tokens["segments"][0]["lines"][0]["tokens"]
    assert [t["t"] for t in words] == ["Cicero", "scribit"]
    assert [t["k"] for t in words] == ["cicero", "scribit"]


def test_latin_bare_numeral_token_gets_no_key():
    # A bare Arabic numeral has no Latin letters -- non-lexical, like a bare
    # numeral in a Greek work.
    spine = _latin_spine("liber 35 incipit")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []
    by_surface = {t["t"]: t for t in tokens["segments"][0]["lines"][0]["tokens"]}
    assert "k" not in by_surface["35"]
    assert by_surface["liber"]["k"] == "liber"


def test_latin_never_raises_key_failures():
    # to_latin_key cannot fail (no restricted character set), so a Latin
    # work's key_failures list is always empty -- unlike Greek's to_beta_key,
    # which fails loudly on unhandled marks.
    spine = _latin_spine("Quisque suum agit; utrum-ne id sciat?")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []


def test_tokenize_rejects_unknown_language():
    with pytest.raises(ValueError, match="unsupported language"):
        tokenize(_latin_spine("nihil"), "xyz")


def test_greek_default_language_unchanged():
    # tokenize(spine) with no language argument still defaults to Greek --
    # the existing call sites across the test suite and stage3.run() rely on
    # this default staying 'grc'.
    spine = {
        "work": "TST",
        "segments": [
            {
                "id": "1:1094a",
                "book": 1,
                "column": "1094a",
                "lines": [{"n": 1, "text": "λόγος"}],
            },
        ],
    }
    tokens, _sigla_log, key_failures = tokenize(spine)
    assert key_failures == []
    assert tokens["segments"][0]["lines"][0]["tokens"][0]["k"] == "lo/gos"


def test_exclamation_edge_punctuation_is_latin_only():
    greek_tokens, _sigla_log, greek_failures = tokenize(_latin_spine("(!)"), "grc")
    assert greek_failures == []
    assert greek_tokens["segments"][0]["lines"][0]["tokens"] == [{"t": "!", "o": 1}]

    latin_tokens, _sigla_log, latin_failures = tokenize(_latin_spine("viam! (!)"), "lat")
    assert latin_failures == []
    words = latin_tokens["segments"][0]["lines"][0]["tokens"]
    # `!` is edge-trimmed from the Latin surface exactly as `.` is (R7.1:
    # no Latin Token.t contains `!`).
    assert words == [{"t": "viam", "o": 0, "k": "viam"}]
    assert all("!" not in token.get("k", "") for token in words)


def test_latin_leading_ascii_apostrophe_stripped_from_key_not_surface():
    # PHI Latin glues a leading ASCII `'` onto quoted words ('honestum).
    # Surface `t` must keep it (substring contract); the lookup key must not.
    spine = _latin_spine("'honestum est")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []
    words = tokens["segments"][0]["lines"][0]["tokens"]
    quoted = next(t for t in words if t["t"].endswith("honestum"))
    assert quoted["t"] == "'honestum"
    assert quoted["k"] == "honestum"


def test_latin_trailing_ascii_apostrophe_stripped_from_key():
    # Symmetric edge case: trailing ASCII `'` is not part of the lemma key.
    # (Shared `_surface` may already peel a trailing non-elision apostrophe
    # from `t`; the key path must be clean either way.)
    spine = _latin_spine("honestum' est")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []
    words = tokens["segments"][0]["lines"][0]["tokens"]
    # Whatever surface shape remains, the keyed form of the honestum token
    # is the bare lemma — never with a trailing apostrophe in `k`.
    honestum_toks = [t for t in words if "honestum" in t["t"]]
    assert len(honestum_toks) == 1
    assert honestum_toks[0]["k"] == "honestum"
    assert not honestum_toks[0]["k"].endswith("'")


def test_latin_interior_ascii_apostrophe_preserved_in_key():
    # Edge-only strip: a genuinely interior `'` must survive into `k`.
    spine = _latin_spine("mel'iora")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat")
    assert key_failures == []
    tok = tokens["segments"][0]["lines"][0]["tokens"][0]
    assert tok["t"] == "mel'iora"
    assert tok["k"] == "mel'iora"


def test_latin_lexicon_false_emits_no_keys_even_with_leading_apostrophe():
    # de-officiis posture: lexicon:false skips key derivation entirely, so
    # the Latin apostrophe edge-strip is pre-positioning only — no `k`
    # fields, surface still carries the quote glue.
    spine = _latin_spine("'honestum est")
    tokens, _sigla_log, key_failures = tokenize(spine, "lat", lexicon=False)
    assert key_failures == []
    words = tokens["segments"][0]["lines"][0]["tokens"]
    assert all("k" not in t for t in words)
    assert words[0]["t"] == "'honestum"


def test_greek_u02b9_keraia_lookalike_unchanged_by_latin_apostrophe_fix():
    # Regression guard: Greek path must stay byte-identical for U+02B9
    # (MODIFIER LETTER PRIME / keraia lookalike). Canonical coverage lives
    # in test_stage2_stage3.test_tokenize_preserves_modifier_letter_prime_...;
    # this re-asserts the contract next to the Latin apostrophe tests so a
    # Latin-only strip cannot bleed into Greek key derivation.
    spine = {
        "work": "TST",
        "segments": [
            {
                "id": "1:1094a",
                "book": 1,
                "column": "1094a",
                "lines": [{"n": 1, "text": "ζητοῦμεν εἰ αʹ ἔοικε"}],
            },
        ],
    }
    tokens, sigla_log, key_failures = tokenize(spine)  # default language=grc
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[0] == {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"}
    assert toks[1] == {"t": "εἰ", "o": 9, "k": "ei)"}
    assert toks[2]["t"] == "αʹ"
    assert "k" not in toks[2]
    assert toks[3] == {"t": "ἔοικε", "o": 15, "k": "e)/oike"}
    assert sigla_log == []
    assert key_failures == []
