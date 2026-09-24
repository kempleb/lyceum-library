"""Damaged-papyrus columns: surviving scraps around a lacuna get no `k` key.

John's ruling 2026-08-29 (REVIEW-CHECKLIST item 95, option b): in the three
manifest-declared `citation.dk_damaged_columns` columns (Protagoras A30,
Democritus A99a, Empedocles B142) a token loses its dictionary key — and so
its word popup — when it is a diacritic-free scrap of the papyrus
transcription: a single bare letter, a fragment glued to a lacuna dot run,
or an all-capitals damage run. Real words keep their keys, including the
correctly accentless enclitics (που, πως). Display text is untouched — the
rule changes only whether `k` is emitted.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage3_tokenize import tokenize


def _spine(text: str, column: str = "A30") -> dict:
    return {
        "work": "TST",
        "segments": [
            {
                "id": f"1:{column}",
                "book": 1,
                "column": column,
                "lines": [{"n": 1, "text": text}],
            },
        ],
    }


def _toks(
    text: str,
    column: str = "A30",
    declared: frozenset[str] | None = None,
) -> list[dict]:
    damaged_columns = frozenset({column}) if declared is None else declared
    tokens, _sigla, key_failures = tokenize(
        _spine(text, column), damaged_columns=damaged_columns
    )
    assert key_failures == []
    return tokens["segments"][0]["lines"][0]["tokens"]


def _key_by_surface(toks: list[dict]) -> dict[str, str | None]:
    return {t["t"]: t.get("k") for t in toks}


# The real A30 sentence (post 61a8691: the between-tails lacuna prints
# "ης....... ς"), the one damaged-transcription stretch in that column.
A30 = (
    "προκατα (?) τῶν η........ τοῖς κινδύνοις τωι ης....... ς "
    "καταλαμβάνοντα τα...... ἐπ]ήδα δὲ οὐκ ἐν τῶι πεδίωι."
)


def test_a30_damage_scraps_lose_their_keys():
    # `t` is the dot-trimmed surface (`_surface` trims edge punctuation; the
    # lacuna dots still display, via the line text outside the token span) —
    # the damage call itself is made on the RAW form, dots attached.
    keys = _key_by_surface(_toks(A30))
    # Single bare letters and dot-glued fragments: no key, so no popup.
    assert keys["η"] is None
    assert keys["ς"] is None
    assert keys["ης"] is None
    assert keys["τα"] is None


def test_a30_real_words_keep_their_keys():
    keys = _key_by_surface(_toks(A30))
    for surface in ("τῶν", "τοῖς", "κινδύνοις", "καταλαμβάνοντα", "δὲ", "πεδίωι"):
        assert keys[surface], surface
    # ἐπ]ήδα: dots touch the PREVIOUS token, not this one — recoverable, keyed.
    assert keys["ἐπ]ήδα"]
    # Bare lowercase multi-letter fragments with no dots stay keyed (their
    # popups are honest misses; the ruling scoped removal to the three
    # shapes above).
    assert keys["προκατα"]
    assert keys["τωι"]


def test_uppercase_damage_runs_lose_their_keys():
    # B142's raw papyrus transcription: all-capitals runs, single letters.
    keys = _key_by_surface(_toks("ΛΟΥΕ ΤΕΓΕΟΙΔΟΜΟΙΑΙΓ Φ Π", column="B142"))
    for surface in ("ΛΟΥΕ", "ΤΕΓΕΟΙΔΟΜΟΙΑΙΓ", "Φ", "Π"):
        assert keys[surface] is None, surface


def test_accentless_real_words_keep_keys_in_damaged_column():
    # A99a: που/πως are enclitics, correctly printed without accents; φασιν
    # and the stage1-cleaned damaged words are multi-letter lowercase — all
    # keep their keys.
    keys = _key_by_surface(_toks("που πως φασιν απολλιπομενης", column="A99a"))
    for surface in ("που", "πως", "φασιν", "απολλιπομενης"):
        assert keys[surface], surface


def test_single_letter_with_diacritic_keeps_key():
    # A real one-letter word always carries a mark (ἡ, ἤ, ὦ) — only the bare
    # letter is a damage scrap.
    keys = _key_by_surface(_toks("ἡ δ' ὡς"))
    assert keys["ἡ"]
    assert keys["δ'"]
    assert keys["ὡς"]


def test_undamaged_columns_are_untouched():
    # The same shapes outside a declared damaged column key exactly as before.
    keys = _key_by_surface(_toks("η ΛΟΥΕ τα", declared=frozenset()))
    assert keys["η"] == "h"
    assert keys["ΛΟΥΕ"] == "loue"
    assert keys["τα"] == "ta"
    # And a damaged-columns declaration for a DIFFERENT column changes nothing.
    keys = _key_by_surface(_toks("η ΛΟΥΕ τα", declared=frozenset({"B142"})))
    assert keys["η"] == "h"


def test_dropped_scraps_emit_no_key_failures():
    # The scraps skip the key attempt entirely — they are not key failures
    # (which are fatal for word tokens), and their `t`/`o` are unchanged.
    tokens, _sigla, key_failures = tokenize(
        _spine(A30), damaged_columns=frozenset({"A30"})
    )
    assert key_failures == []
    toks = tokens["segments"][0]["lines"][0]["tokens"]
    line = A30
    for t in toks:
        assert line[t["o"] : t["o"] + len(t["t"])] == t["t"]
