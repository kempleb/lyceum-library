from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage2_validate import validate
from reader_pipeline.stage3_tokenize import tokenize


def _spine_with_lines(*lines: str) -> dict:
    """A single-segment spine wrapping the given raw line texts, for tests
    that only care about tokenize()'s per-token key logic."""
    return {
        "work": "TST",
        "segments": [
            {
                "id": "1:1094a",
                "book": 1,
                "column": "1094a",
                "lines": [{"n": i + 1, "text": text} for i, text in enumerate(lines)],
            },
        ],
    }


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TinyManifest:
    first_column = "1094a"
    last_column = "1094b"
    books = [{"n": 1, "start": "1094a1", "end": "1094b2"}]
    data = {
        "work": {"id": "TST"},
        "bekker_range": {"first_column": first_column, "last_column": last_column},
        "books": books,
        "proper_names": [],
    }


def _tiny_spine():
    return {
        "work": "TST",
        "segments": [
            {
                "id": "1:1094a",
                "book": 1,
                "column": "1094a",
                "lines": [
                    {"n": 1, "text": "Ἀγαθός ἐστι."},
                    {"n": 2, "text": "τῷ λόγος"},
                ],
            },
            {
                "id": "1:1094b",
                "book": 1,
                "column": "1094b",
                "lines": [
                    {"n": 1, "text": "κατ’ ἀρετήν"},
                    {"n": 2, "text": "†λόγος†—ἀγαθός"},
                ],
            },
        ],
    }


def _tiny_english():
    return {
        "chunks": [
            {
                "id": "1:1094a",
                "column": "1094a",
                "text": "The good is something in speech.",
            },
            {
                "id": "1:1094b",
                "column": "1094b",
                "text": "According to virtue, speech is good.",
            },
        ]
    }


def _tiny_alignment():
    return {
        "pairs": [
            {"segment": "1:1094a", "english": "1:1094a"},
            {"segment": "1:1094b", "english": "1:1094b"},
        ],
        "english_only": [],
    }


def test_tokenize_records_offsets_boundaries_sigla_and_is_idempotent():
    tokens, sigla_log, key_failures = tokenize(_tiny_spine())

    assert key_failures == []
    assert tokens["segments"][0]["lines"][0]["tokens"] == [
        {"t": "Ἀγαθός", "o": 0, "k": "a)gaqo/s"},
        {"t": "ἐστι", "o": 7, "k": "e)sti"},
    ]
    assert tokens["segments"][0]["lines"][1]["tokens"] == [
        {"t": "τῷ", "o": 0, "k": "tw=|"},
        {"t": "λόγος", "o": 3, "k": "lo/gos"},
    ]
    # The daggers are editorial sigla, not ordinary punctuation: `t` keeps
    # them verbatim (the surface contract — see stage3_tokenize.py's module
    # docstring) even though the lexicon key `k` is still derived from the
    # fully-cleaned "λόγος" form.
    assert tokens["segments"][1]["lines"][1]["tokens"] == [
        {"t": "†λόγος†", "o": 0, "k": "lo/gos"},
        {"t": "ἀγαθός", "o": 8, "k": "a)gaqo/s"},
    ]
    assert sigla_log == [{"ref": "1094b2", "raw": "†λόγος†", "kept": "λόγος"}]
    assert tokenize(_tiny_spine()) == (tokens, sigla_log, key_failures)


def test_tokenize_keeps_an_interior_siglum_verbatim_in_t_but_keys_the_cleaned_form():
    # The Schenkl supplement case named in this module's own docstring (and
    # CLAUDE.md defect B): the `<`/`>` sit BETWEEN two letters of one word
    # (ὁμολογεῖ<ν>), not at the word's edges like the `test_tokenize_records_
    # offsets_boundaries_sigla_and_is_idempotent` dagger case above. `t` must
    # keep the siglum verbatim (so it stays a literal substring of `text` for
    # the preflight token-walk gate / the reader's render-time walk), while
    # `k` is still derived from the fully-cleaned "ὁμολογεῖν" form.
    spine = _spine_with_lines("ζητοῦμεν εἰ ὁμολογεῖ<ν> ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"},
        {"t": "εἰ", "o": 9, "k": "ei)"},
        {"t": "ὁμολογεῖ<ν>", "o": 12, "k": "o(mologei=n"},
        {"t": "ἔοικε", "o": 24, "k": "e)/oike"},
    ]
    assert sigla_log == [{"ref": "1094a1", "raw": "ὁμολογεῖ<ν>", "kept": "ὁμολογεῖν"}]
    assert key_failures == []


def test_tokenize_keeps_an_interior_paren_siglum_verbatim_in_t_but_keys_the_cleaned_form():
    # The parenthesis analogue of the angle-bracket case above (`_SIGLA`'s
    # '()' widening, stage3_tokenize.py, Wave 1b Parmenides pilot): a DK6
    # editorial supplement can also be typeset with parentheses INSIDE a
    # word ("γ(ί)νεται"-shaped -- here "ὁμολογεῖ(ν)τος", so the closing paren
    # is followed by more of the word, truly interior rather than sitting at
    # the token's trailing edge -- see below). `t` must keep the siglum
    # verbatim (a literal substring of `text`, for the preflight token-walk
    # gate / the reader's render-time walk), while `k` is still derived from
    # the fully-cleaned "ὁμολογεῖντος" form -- exactly the same contract as
    # the angle-bracket case.
    #
    # NOTE this is deliberately NOT the same shape as `()` at a token's very
    # END (e.g. the real DK examples in stage3_tokenize.py's module comment,
    # "ἔστ(ι)"/"ὄνομ(α)"/"ἄγους(α)"): unlike `<>`, `()` is ALSO a member of
    # `_PUNCT` (the established edge-only case, "ἀναθυμιῶνται(?)"), so
    # `_surface()`'s edge-trim still strips a TRAILING `)` even when it's an
    # editorial supplement mark, not just ordinary punctuation -- confirmed
    # empirically: `tokenize` on "ἔστ(ι)" alone yields `t == "ἔστ(ι"` (closing
    # paren dropped), not the fully-bracketed form the module comment's
    # phrasing ("exactly like <>") might suggest. That asymmetry is a
    # pre-existing behavior this test does not exercise or fix -- flagged
    # for a follow-up, not addressed here (out of this task's scope).
    spine = _spine_with_lines("ζητοῦμεν εἰ ὁμολογεῖ(ν)τος ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"},
        {"t": "εἰ", "o": 9, "k": "ei)"},
        {"t": "ὁμολογεῖ(ν)τος", "o": 12, "k": "o(mologei=ntos"},
        {"t": "ἔοικε", "o": 27, "k": "e)/oike"},
    ]
    assert sigla_log == [{"ref": "1094a1", "raw": "ὁμολογεῖ(ν)τος", "kept": "ὁμολογεῖντος"}]
    assert key_failures == []


def test_tokenize_keeps_paragraphos_siglum_verbatim_in_t_but_keys_the_cleaned_form():
    # ⸏ (U+2E0F PARAGRAPHOS, Wave 1c Sophists batch 2, Antiphon 87 B44's
    # damaged POxy 1364 papyrus): a genuine ancient marginal siglum the
    # export glues directly onto the adjacent Greek word with no separating
    # space, both at a word's leading edge and INTERIOR (mid-word, where a
    # hyphen-wrap rejoin pulled the two halves together) -- same `_SIGLA`
    # contract as `<>`/`()` above: kept verbatim in the surface `t`,
    # stripped from the lexicon key `k`. Synthetic fixture word, interior
    # placement.
    spine = _spine_with_lines("ζητοῦμεν εἰ λό⸏γος ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"},
        {"t": "εἰ", "o": 9, "k": "ei)"},
        {"t": "λό⸏γος", "o": 12, "k": "lo/gos"},
        {"t": "ἔοικε", "o": 19, "k": "e)/oike"},
    ]
    assert sigla_log == [{"ref": "1094a1", "raw": "λό⸏γος", "kept": "λόγος"}]
    assert key_failures == []


def test_tokenize_keeps_dotted_obelos_siglum_verbatim_in_t_but_keys_the_cleaned_form():
    # ⸓ (U+2E13 DOTTED OBELOS, Wave 1c Sophists batch 2, Antiphon 87 B44/B54):
    # a genuine editorial critical mark the export glues directly onto the
    # adjacent Greek word with no separating space -- same `_SIGLA` contract
    # as `⸏`/`<>`/`()` above: kept verbatim in the surface `t`, stripped from
    # the lexicon key `k`. Synthetic fixture word, interior placement.
    spine = _spine_with_lines("ζητοῦμεν εἰ λό⸓γος ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"},
        {"t": "εἰ", "o": 9, "k": "ei)"},
        {"t": "λό⸓γος", "o": 12, "k": "lo/gos"},
        {"t": "ἔοικε", "o": 19, "k": "e)/oike"},
    ]
    assert sigla_log == [{"ref": "1094a1", "raw": "λό⸓γος", "kept": "λόγος"}]
    assert key_failures == []


def test_tokenize_keeps_stadium_diagram_arrows_verbatim_in_t_but_keys_the_cleaned_form():
    # → ← (U+2192/U+2190, John's dashboard ruling 2026-07-24): Zeno
    # testimonia A28's Stadium-paradox diagram glues these onto the row
    # labels at the WORD EDGE with no separating space -- "ΒΒΒΒ→" (trailing)
    # and "←ΓΓΓΓ" (leading) -- unlike the interior paragraphos/dotted-obelos
    # fixtures above. Same `_SIGLA` contract: kept verbatim in the surface
    # `t`, stripped from the lexicon key `k`.
    spine = _spine_with_lines("ΑΑΑΑ ΒΒΒΒ→ Ε ←ΓΓΓΓ")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ΑΑΑΑ", "o": 0, "k": "aaaa"},
        {"t": "ΒΒΒΒ→", "o": 5, "k": "bbbb"},
        {"t": "Ε", "o": 11, "k": "e"},
        {"t": "←ΓΓΓΓ", "o": 13, "k": "gggg"},
    ]
    assert sigla_log == [
        {"ref": "1094a1", "raw": "ΒΒΒΒ→", "kept": "ΒΒΒΒ"},
        {"ref": "1094a1", "raw": "←ΓΓΓΓ", "kept": "ΓΓΓΓ"},
    ]
    assert key_failures == []


def test_tokenize_preserves_modifier_letter_prime_in_t_and_strips_it_from_k():
    # ʹ (U+02B9 MODIFIER LETTER PRIME): lookalike of the keraia (U+0374) that
    # some digitizations substitute for it. `_KERAIA` treats both identically
    # as the trailing mark on a Greek alphabetic numeral: preserved in the
    # surface `t` (it is numeral orthography, not editorial punctuation) and
    # stripped from the lookup path (numeral is non-lexical — no `k` field).
    # Synthetic fixture, same `_spine_with_lines` shape as the dotted-obelos
    # sigla test above.
    spine = _spine_with_lines("ζητοῦμεν εἰ αʹ ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[0] == {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"}
    assert toks[1] == {"t": "εἰ", "o": 9, "k": "ei)"}
    assert toks[2]["t"] == "αʹ"  # U+02B9 preserved in surface text
    assert "k" not in toks[2]  # stripped from lookup: non-lexical numeral
    assert toks[3] == {"t": "ἔοικε", "o": 15, "k": "e)/oike"}
    assert sigla_log == []
    assert key_failures == []


def test_tokenize_keeps_reversed_lunate_sigma_siglum_verbatim_in_t_but_keys_the_cleaned_form():
    # Ͻ (U+03FD GREEK CAPITAL REVERSED LUNATE SIGMA SYMBOL, Wave 1c Sophists
    # batch 2, Antiphon 87 B44/B54): used in this corpus as a critical
    # siglum, not a letter -- despite its Unicode name starting "GREEK", it
    # is category symbol, not letter (the same "named GREEK but not a
    # letter" trap `_is_greek_letter`'s own doc comment already warns about
    # for U+037E/U+0387). Same `_SIGLA` contract: kept verbatim in `t`,
    # stripped from `k`. Synthetic fixture word, interior placement.
    spine = _spine_with_lines("ζητοῦμεν εἰ λόϽγος ἔοικε")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "ζητοῦμεν", "o": 0, "k": "zhtou=men"},
        {"t": "εἰ", "o": 9, "k": "ei)"},
        {"t": "λόϽγος", "o": 12, "k": "lo/gos"},
        {"t": "ἔοικε", "o": 19, "k": "e)/oike"},
    ]
    assert sigla_log == [{"ref": "1094a1", "raw": "λόϽγος", "kept": "λόγος"}]
    assert key_failures == []


def test_tokenize_omits_k_for_non_lexical_apparatus_tokens_but_keys_the_greek():
    # Inline Latin-script scholarly apparatus (editor name, bare numeral) has
    # no Greek letters at all, so it is NON-LEXICAL: no `k` field at all, not
    # an empty string — while the neighboring Greek word still keys normally.
    spine = _spine_with_lines("λόγος Zeller 35")
    tokens, sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "λόγος", "o": 0, "k": "lo/gos"},
        {"t": "Zeller", "o": 6},
        {"t": "35", "o": 13},
    ]
    assert "k" not in toks[1]
    assert "k" not in toks[2]
    assert key_failures == []


def test_tokenize_strips_the_real_greek_ano_teleia_and_question_mark():
    # U+0387 GREEK ANO TELEIA and U+037E GREEK QUESTION MARK are the actual
    # codepoints the TLG export uses for these marks — they LOOK like the
    # ASCII middle dot/semicolon and NFD-decompose to them, but are distinct
    # characters. A trailing one glued onto a real word (as the TLG always
    # writes them, no preceding space) must still strip cleanly so the word
    # keys — this is what Lives 1.18's "τρία·" (Diogenes Laertius on
    # the three parts of philosophy) and "ἐρωτᾷς;" need.
    spine = _spine_with_lines("τρία· ἐρωτᾷς;")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks == [
        {"t": "τρία", "o": 0, "k": "tri/a"},
        {"t": "ἐρωτᾷς", "o": 6, "k": "e)rwta=|s"},
    ]
    assert key_failures == []


def test_tokenize_omits_k_for_greek_alphabetic_numerals():
    # Diogenes Laertius cites sums using Greek LETTERS as digits (e.g. a
    # philosopher's estate) rather than Arabic numerals: 'ιϛ' is iota(10) +
    # stigma(6) = 16; '͵δοε' is the lower numeral sign U+0375 (a thousands
    # multiplier) plus more letter-digits. These contain real Greek letters
    # by Unicode category but are numerals, never lexical words, so they
    # must be non-lexical (no `k`, no loud failure) exactly like a bare
    # Arabic-numeral token — not mistaken for a genuinely broken Greek word.
    spine = _spine_with_lines("ἀγαθός ιϛ ϛ ͵δοε")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[0] == {"t": "ἀγαθός", "o": 0, "k": "a)gaqo/s"}
    for tok in toks[1:]:
        assert "k" not in tok
    assert [t["t"] for t in toks[1:]] == ["ιϛ", "ϛ", "͵δοε"]
    assert key_failures == []


def test_tokenize_strips_glued_curly_quotes_and_keys_the_greek_word():
    # German-style curly quotes „ " (U+201E/U+201C) glue directly onto a Greek
    # word at the edges in the Discourses TEI (e.g. Epictetus 2.17's
    # "„εἰς ... λύχνους“"). They must be stripped like « » so the Greek keys
    # correctly, rather than surviving into to_beta_key and either raising or
    # (pre-fix) being silently dropped to non-lexical.
    spine = _spine_with_lines("„λόγος“ ἀγαθός")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    # „ “ are ordinary punctuation (_PUNCT), not editorial sigla, so they are
    # trimmed from `t` as before -- but `o` now points at the exact surface
    # start (index 1, past the opening „), not the raw match start (index 0),
    # per the offset-exactness contract.
    assert toks == [
        {"t": "λόγος", "o": 1, "k": "lo/gos"},
        {"t": "ἀγαθός", "o": 8, "k": "a)gaqo/s"},
    ]
    assert key_failures == []


def test_tokenize_fails_loudly_when_a_greek_token_cannot_key():
    # A token that DOES contain a Greek letter but still fails to transliterate
    # is a real bug (an unhandled character/mark reaching to_beta_key) — it
    # must never be silently demoted to non-lexical. Simulate an unhandled
    # combining mark (U+0330 COMBINING TILDE BELOW — not something beta.py's
    # _MARKS table understands) glued onto a Greek base letter.
    spine = _spine_with_lines("λο̰γος")
    with pytest.raises(ValueError, match="Greek token"):
        tokenize(spine)


def test_tokenize_fails_loudly_on_malformed_tokens_merely_containing_a_numeral_signal():
    # _is_greek_numeral must require the ENTIRE token to be alphabetic-numeral
    # notation, not just contain a numeral-signal character somewhere inside
    # it. Before the fix, any token with a stigma/koppa/sampi/lower-numeral-
    # sign character ANYWHERE was silently demoted to non-lexical, no matter
    # what else the token contained — so malformed Greek like a stigma glued
    # onto a real word, at either edge, or a stigma plus an unhandled
    # combining mark, was silently swallowed instead of failing loudly like
    # any other unhandled character reaching to_beta_key.
    for bad_token in ("ϛλόγος", "λόγοςϛ", "ϛ̰"):
        with pytest.raises(ValueError, match="Greek token"):
            tokenize(_spine_with_lines(bad_token))


def test_tokenize_still_omits_k_for_a_genuine_corpus_numeral_after_the_stricter_grammar():
    # The stricter full-token grammar must not regress the real numerals it
    # was designed around (drawn from the Diogenes Laertius lives build):
    # 'ιϛ' (10+6=16), 'ϛ' (6 alone), and '͵δοε' (a lower-numeral-sign-prefixed
    # thousands token) must still demote to non-lexical with no `k` and no
    # key failure.
    spine = _spine_with_lines("ἀγαθός ιϛ ϛ ͵δοε")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[0] == {"t": "ἀγαθός", "o": 0, "k": "a)gaqo/s"}
    for tok in toks[1:]:
        assert "k" not in tok
    assert [t["t"] for t in toks[1:]] == ["ιϛ", "ϛ", "͵δοε"]
    assert key_failures == []


def test_tokenize_fails_loudly_on_mixed_latin_apparatus_glued_to_a_greek_word():
    # Explicit regression test (requested in review): inline Latin-script
    # apparatus glued directly onto a Greek word with no space, e.g. an "FGrH"
    # citation abutting a real word, has no numeral signal at all and must
    # still fail loudly — a naive "grammar" fix must not treat any Greek-plus-
    # Latin mixture as non-lexical apparatus.
    with pytest.raises(ValueError, match="Greek token"):
        tokenize(_spine_with_lines("FGrHἀλλά"))


def test_tokenize_demotes_keraia_suffixed_numeral_with_keraia_intact_in_t():
    # FINDING 1 (must-fail-first): a token like "αʹ" ("book 1", from
    # the Lives catalogue-of-works lists, e.g. book 5's Aristotle/Theophrastus
    # bibliography) used to have its keraia stripped by the edge-sigla cleaner
    # BEFORE numeral classification -- it reached to_beta_key as bare "α"
    # and wrongly keyed as the word alpha (k="a"), with the keraia dropped
    # from the displayed text too. Now: the keraia is classified as part of
    # the numeral before any stripping, so the token demotes to non-lexical
    # (no `k`) with the keraia PRESERVED in the surface text `t`.
    spine = _spine_with_lines("λόγος αʹ")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[0] == {"t": "λόγος", "o": 0, "k": "lo/gos"}
    numeral_tok = toks[1]
    assert numeral_tok["t"] == "αʹ"  # keraia intact in the surface text
    assert "k" not in numeral_tok  # non-lexical: no lexicon lookup key
    assert key_failures == []


def test_tokenize_demotes_multi_digit_keraia_numerals_from_the_lives_catalogue():
    # Same grammar, longer numeral bodies drawn from the actual Lives build
    # (Book 5's bibliography lists cite counts like "ρξεʹ" = 165,
    # "κδʹ" = 24).
    spine = _spine_with_lines("θέσεις ρξεʹ, κδʹ,")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert [t["t"] for t in toks] == ["θέσεις", "ρξεʹ", "κδʹ"]
    assert "k" in toks[0]
    for tok in toks[1:]:
        assert "k" not in tok
    assert key_failures == []


def test_tokenize_omits_k_for_attic_acrophonic_numerals_and_keeps_them_in_t():
    # Must-fail-first (Anaxagoras testimonia A4a/A11, Marmor Parium
    # chronological entries quoted verbatim): U+10144 GREEK ACROPHONIC ATTIC
    # FIFTY is glued directly onto ordinary Milesian alphabetic-numeral
    # letters with no separating space -- "Η𐅄ΔΔΓΙΙΙΙ" (179) and "𐅄ΔΔΔΔ" (90).
    # Before the fix, U+10144 had no numeral-signal recognition at all: the
    # token contained real Greek letters (Η/Δ/Γ/Ι) so _contains_greek was
    # True, but _is_greek_numeral was False (no Milesian signal character),
    # and to_beta_key cannot transliterate U+10144 either -- so the token
    # was wrongly routed to the hard key_failures path instead of being
    # recognized as the non-lexical numeral it is. The acrophonic character
    # must be PRESERVED in the displayed surface text `t` (genuine ancient
    # inscription content, not export noise), with no `k` lookup key.
    spine = _spine_with_lines("ἔτη Η𐅄ΔΔΓΙΙΙΙ ἔτη 𐅄ΔΔΔΔ")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert [t["t"] for t in toks] == ["ἔτη", "Η𐅄ΔΔΓΙΙΙΙ", "ἔτη", "𐅄ΔΔΔΔ"]
    assert "k" in toks[0] and "k" in toks[2]  # "ἔτη" keys normally, twice
    assert "k" not in toks[1]  # "Η𐅄ΔΔΓΙΙΙΙ" (179): non-lexical, no key
    assert "k" not in toks[3]  # "𐅄ΔΔΔΔ" (90): non-lexical, no key
    assert key_failures == []


def test_tokenize_fails_loudly_on_malformed_token_merely_containing_an_acrophonic_char():
    # Mirrors test_tokenize_fails_loudly_on_malformed_tokens_merely_
    # containing_a_numeral_signal for the acrophonic block: an acrophonic
    # numeral character glued onto an unhandled combining mark must still
    # fail loudly, not be silently swallowed just because SOME character in
    # the token is an acrophonic numeral signal.
    with pytest.raises(ValueError, match="Greek token"):
        tokenize(_spine_with_lines("𐅄λο̰γος"))


def test_tokenize_treats_lone_numeral_sign_as_explicitly_non_lexical():
    # FINDING 2: a lone lower numeral sign "͵" (U+0375, the thousands-
    # multiplier prefix used alone with nothing following it) has no Greek
    # LETTERS at all -- unicodedata categorizes it as a symbol, not a letter --
    # so it already demoted silently via the no-Greek-letters path before this
    # change. Lock that behavior explicitly: non-lexical, no `k`, no error.
    spine = _spine_with_lines("λόγος ͵")
    tokens, _sigla_log, key_failures = tokenize(spine)
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    assert toks[1]["t"] == "͵"
    assert "k" not in toks[1]
    assert key_failures == []

def test_validate_reports_clean_tiny_fixture_and_is_idempotent():
    report = validate(TinyManifest(), _tiny_spine(), _tiny_english(), _tiny_alignment())

    assert report["ok"] is True
    assert report["checks"]["columns"] == {
        "expected": 2,
        "found": 2,
        "missing": [],
        "extra": [],
        "monotonic": True,
        "ok": True,
    }
    assert report["checks"]["line_gaps"]["unexpected"] == []
    assert report["checks"]["alignment"]["unexpected_unmatched"] == []
    assert report["checks"]["alignment"]["unexpected_english_only"] == []
    assert report["checks"]["sigla"]["characters"] == [
        {
            "char": "†",
            "name": "DAGGER",
            "count": 2,
            "samples": [
                {"ref": "1094b2", "text": "†λόγος†—ἀγαθός"},
                {"ref": "1094b2", "text": "†λόγος†—ἀγαθός"},
            ],
        }
    ]
    assert validate(TinyManifest(), _tiny_spine(), _tiny_english(), _tiny_alignment()) == report


class OmitOverrideManifest(TinyManifest):
    """Same fixture as TinyManifest, but 1094b carries a `kind: "omit"`
    citation.kind_overrides disposition (Freeman-English-withheld-by-
    editorial-ruling, design note §1(b)) -- the same declaration
    stage1_freeman_english.py's `_resolve_kind_overrides` already
    enforces, not a parallel hand-maintained allowance list."""
    data = {
        **TinyManifest.data,
        "citation": {
            "kind_overrides": {
                "1094b": {"kind": "omit", "reason": "no Greek role='text' span"},
            },
        },
    }


def _tiny_alignment_1094b_unmatched():
    return {
        "pairs": [
            {"segment": "1:1094a", "english": "1:1094a"},
            {"segment": "1:1094b", "english": None},
        ],
        "english_only": [],
    }


def _tiny_english_1094a_only():
    return {
        "chunks": [
            {
                "id": "1:1094a",
                "column": "1094a",
                "text": "The good is something in speech.",
            },
        ]
    }


class SummarySuppressedManifest(TinyManifest):
    """Same fixture as TinyManifest, but 1094b is named in
    `english.summary_suppressed` (John's ruling 2026-07-29: a Freeman précis
    already covered by a translated context-english span ships no English
    chunk at all) -- the same declaration stage1_freeman_english.py's
    `build_english` already enforces, not a parallel hand-maintained
    allowance list."""
    data = {
        **TinyManifest.data,
        "english": {"summary_suppressed": ["1094b"]},
    }


def test_validate_alignment_ok_when_unmatched_column_is_summary_suppressed():
    # Regression: stage2's alignment gate must accept a column as
    # legitimately unmatched when the manifest's english.summary_suppressed
    # names it -- the SAME declaration stage1_freeman_english.py uses to
    # decide no English chunk ships for it (John's ruling 2026-07-29).
    report = validate(
        SummarySuppressedManifest(), _tiny_spine(),
        _tiny_english_1094a_only(), _tiny_alignment_1094b_unmatched(),
    )
    assert report["checks"]["alignment"]["unexpected_unmatched"] == []
    assert report["checks"]["alignment"]["allowed_unmatched"] == ["1:1094b"]
    assert report["checks"]["alignment"]["ok"] is True


def test_validate_alignment_ok_when_unmatched_column_is_omit_declared():
    # Regression: stage2's alignment gate must accept a column as
    # legitimately unmatched when the manifest's citation.kind_overrides
    # declares it `kind: "omit"` -- the SAME declaration stage1 uses to
    # decide no English chunk ships for it (John's ruling 2026-07-23).
    report = validate(
        OmitOverrideManifest(), _tiny_spine(),
        _tiny_english_1094a_only(), _tiny_alignment_1094b_unmatched(),
    )
    assert report["checks"]["alignment"]["unexpected_unmatched"] == []
    assert report["checks"]["alignment"]["allowed_unmatched"] == ["1:1094b"]
    assert report["checks"]["alignment"]["ok"] is True


def test_validate_alignment_still_fails_when_unmatched_column_is_not_omit_declared():
    # The other direction: an unmatched column that is NEITHER omit-declared
    # NOR covered by alignment_allow_unmatched must still fail -- the omit
    # allowance must not become a blanket pass for every unexplained gap.
    report = validate(
        TinyManifest(), _tiny_spine(),
        _tiny_english_1094a_only(), _tiny_alignment_1094b_unmatched(),
    )
    assert report["checks"]["alignment"]["unexpected_unmatched"] == ["1:1094b"]
    assert report["checks"]["alignment"]["ok"] is False


def test_deterministic_stage2_stage3_smoke_matches_golden_fixture():
    tokens, sigla_log, key_failures = tokenize(_tiny_spine())
    report = validate(TinyManifest(), _tiny_spine(), _tiny_english(), _tiny_alignment())
    smoke = {
        "tokens": tokens,
        "sigla_log": sigla_log,
        "key_failures": key_failures,
        "validation": {
            "ok": report["ok"],
            "columns": report["checks"]["columns"],
            "line_gaps": report["checks"]["line_gaps"],
            "alignment": report["checks"]["alignment"],
            "sigla": report["checks"]["sigla"],
        },
    }

    expected = json.loads(
        (FIXTURES / "deterministic_stage2_stage3_golden.json").read_text(encoding="utf-8")
    )
    assert smoke == expected


# --- book-section scheme (gap 4): dotted columns validate under "observed" ----

def _book_section_spine():
    # Columns in document order; "1.10" must sort AFTER "1.2" (numeric, not
    # lexicographic), which a working dotted key guarantees.
    return {
        "work": "MED",
        "segments": [
            {"id": "1:1.1", "book": 1, "column": "1.1",
             "lines": [{"n": 1, "text": "ἀγαθός"}]},
            {"id": "1:1.2", "book": 1, "column": "1.2",
             "lines": [{"n": 1, "text": "λόγος"}]},
            {"id": "1:1.10", "book": 1, "column": "1.10",
             "lines": [{"n": 1, "text": "ἀρετή"}]},
        ],
    }


def _book_section_manifest():
    cols = ["1.1", "1.2", "1.10"]
    sha = hashlib.sha256(",".join(cols).encode("utf-8")).hexdigest()

    class M:
        first_column = "1.1"
        last_column = "1.10"
        books = [{"n": 1, "start": "1.1", "end": "1.10"}]
        data = {
            "work": {"id": "MED"},
            "citation": {"scheme": "book-section"},
            "books": books,
            "section_spine": {"count": len(cols), "sha256": sha},
            "proper_names": [],
        }

    return M()


def _ratio_spine_and_english(outlier_ratio):
    """A healthy cluster of book-section chapters (English ~1.3x the Greek) plus
    one chapter forced to `outlier_ratio`. Greek is 100 chars/chapter; English
    length is set to hit the target ratio."""
    segs, chunks = [], []
    ratios = [1.30, 1.25, 1.35, 1.28, 1.32, 1.27, 1.33, 1.29, 1.31, 1.26, outlier_ratio]
    for i, ratio in enumerate(ratios, 1):
        col = f"1.{i}"
        sid = f"1:{col}"
        segs.append({"id": sid, "book": 1, "column": col,
                     "lines": [{"n": 1, "text": "α" * 100}]})
        chunks.append({"id": sid, "column": col, "text": "e" * round(100 * ratio)})
    spine = {"work": "MED", "segments": segs}
    english = {"chunks": chunks}
    alignment = {"pairs": [{"segment": s["id"], "english": s["id"]} for s in segs],
                 "english_only": []}
    return spine, english, alignment


def _ratio_gate_manifest(gate):
    cols = [f"1.{i}" for i in range(1, 12)]
    sha = hashlib.sha256(",".join(cols).encode("utf-8")).hexdigest()

    class M:
        first_column = "1.1"
        last_column = "1.11"
        books = [{"n": 1, "start": "1.1", "end": "1.11"}]
        data = {
            "work": {"id": "MED"},
            "citation": {"scheme": "book-section"},
            "books": books,
            "section_spine": {"count": len(cols), "sha256": sha},
            "proper_names": [],
        }
        if gate is not None:
            data["length_ratio_gate"] = gate

    return M()


def test_length_ratio_gate_fails_on_synthetic_outlier():
    # A catastrophically short chapter (ratio 0.15 vs a ~1.3 healthy centre) must
    # FAIL the enforced gate, named by its column.
    spine, english, alignment = _ratio_spine_and_english(outlier_ratio=0.15)
    report = validate(_ratio_gate_manifest({"max_robust_z": 5.0}),
                      spine, english, alignment)
    lr = report["checks"]["length_ratio"]
    assert lr["enforced"] is True
    assert lr["ok"] is False
    assert [f["column"] for f in lr["failures"]] == ["1.11"]
    assert report["ok"] is False


def test_length_ratio_gate_passes_when_outlier_is_exempted():
    # The same outlier, listed in `exempt`, is dropped from the stats and the
    # test — the gate passes honestly (the rest of the distribution is healthy).
    spine, english, alignment = _ratio_spine_and_english(outlier_ratio=0.15)
    report = validate(_ratio_gate_manifest({"max_robust_z": 5.0, "exempt": ["1.11"]}),
                      spine, english, alignment)
    lr = report["checks"]["length_ratio"]
    assert lr["ok"] is True
    assert lr["failures"] == []


def test_length_ratio_check_informational_without_manifest_optin():
    # No `length_ratio_gate` in the manifest → the same outlier is reported but
    # never fails the build (unvetted works are not broken silently).
    spine, english, alignment = _ratio_spine_and_english(outlier_ratio=0.15)
    report = validate(_ratio_gate_manifest(None), spine, english, alignment)
    lr = report["checks"]["length_ratio"]
    assert lr["enforced"] is False
    assert lr["ok"] is True
    assert any(o["column"] == "1.11" for o in lr["outliers"])


# --- dk (fragment) scheme: section_spine mismatch must not crash (bug repro) --

def _dk_spine():
    return {
        "work": "DK",
        "segments": [
            {"id": "1:B1", "book": 1, "column": "B1",
             "lines": [{"n": 1, "text": "ἀγαθός"}]},
            {"id": "1:B2", "book": 1, "column": "B2",
             "lines": [{"n": 1, "text": "λόγος"}]},
            {"id": "1:B4", "book": 1, "column": "B4",
             "lines": [{"n": 1, "text": "ἀρετή"}]},
        ],
    }


def _dk_manifest_with_stale_baseline():
    # Baseline deliberately does NOT match the observed spine (as if stage2 ran
    # against build/stage1 output left over from a different work), forcing
    # the section_spine "not count_ok" diagnostic path.
    class M:
        first_column = "B1"
        last_column = "B4"
        books = [{"n": 1, "start": "B1", "end": "B4"}]
        data = {
            "work": {"id": "DK"},
            "citation": {"scheme": "dk", "series": "B"},
            "books": books,
            "section_spine": {"count": 99, "sha256": "0" * 64},
            "proper_names": [],
        }

    return M()


def test_validate_dk_scheme_section_spine_mismatch_does_not_crash():
    # Regression test for an UnboundLocalError on `letter_ix`: the dk
    # (fragment) scheme has no letter axis, so `letter_ix` is never built, but
    # the section_spine diagnostic path referenced it unconditionally whenever
    # a baseline mismatch needed pinpointing. It must report a clean FAIL, not
    # raise.
    report = validate(
        _dk_manifest_with_stale_baseline(), _dk_spine(),
        {"chunks": []}, {"pairs": [], "english_only": []},
    )

    assert report["ok"] is False
    spine_check = report["checks"]["section_spine"]
    assert spine_check["ok"] is False
    assert spine_check["count_match"] is False
    # B4 follows B2 with B3 undeclared-missing -> a real same-series gap the
    # diagnostic should be able to name without crashing.
    assert spine_check["first_diverging_token"] is not None


def test_validate_book_section_scheme_orders_dotted_columns_numerically():
    report = validate(
        _book_section_manifest(), _book_section_spine(),
        {"chunks": []}, {"pairs": [], "english_only": []},
    )

    assert report["ok"] is True
    cols = report["checks"]["columns"]
    assert cols["found"] == 3
    assert cols["missing"] == [] and cols["extra"] == []
    assert cols["monotonic"] is True  # (1,1) < (1,2) < (1,10), numerically
    # observed scheme establishes the spine as its own expected column set
    assert report["checks"]["section_order"]["strictly_increasing"] is True
    assert report["checks"]["section_spine"]["ok"] is True
    assert report["checks"]["book_partition"]["ok"] is True
    assert report["checks"]["book_partition"]["sections_outside_any_book"] == []
