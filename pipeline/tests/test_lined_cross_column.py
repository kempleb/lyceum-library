from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.config import Manifest
from reader_pipeline.lined import (
    LinedAlphabet,
    _apply_lined_cross_column_wraps,
    _apply_lined_wraps,
)
from reader_pipeline.stage1_greek import GREEK_LINED, _parse_flat_chapter
from reader_pipeline.stage1_latin import LATIN_LINED as REAL_LATIN_LINED
from reader_pipeline.stage3_tokenize import tokenize


LATIN_LINED = LinedAlphabet(
    is_letter=lambda ch: ch.isascii() and ch.isalpha(),
    fold_wrap_final=lambda ch: ch,
    name="latin",
)


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


def _flat_manifest(declared: int) -> Manifest:
    return Manifest(
        {
            "work": {
                "id": "cross-column-fixture",
                "tlg_author": "0000",
                "tlg_work": "000",
                "greek_edition": "Fixture",
            },
            "citation": {
                "scheme": "section",
                "lined_source": True,
                "lined_cross_column_wraps": declared,
                "title_labels": [],
            },
            "books": [{"n": 1, "start": "1", "end": "2"}],
        },
        ROOT / "manifests" / "fake.yaml",
    )


def test_cross_column_wrap_is_owned_by_first_column_and_tokens_match_text():
    flat = [
        {"column": "1.1", "n": 1, "text": "haec conten-"},
        {"column": "1.2", "n": 1, "text": "tionibus restant"},
    ]

    assert _apply_lined_cross_column_wraps(flat, alphabet=LATIN_LINED) == 1
    assert flat == [
        {"column": "1.1", "n": 1, "text": "haec contentionibus", "joined": True},
        {"column": "1.2", "n": 1, "text": "restant"},
    ]
    assert "wrap" not in flat[0] and "wrapO" not in flat[0]

    spine = {
        "work": "fixture",
        "segments": [
            {
                "id": f"1:{line['column']}",
                "book": 1,
                "column": line["column"],
                "lines": [line],
            }
            for line in flat
        ],
    }
    tokens_doc, _, _ = tokenize(spine, language="lat", lexicon=False)
    token_texts = [
        [token["t"] for token in segment["lines"][0]["tokens"]]
        for segment in tokens_doc["segments"]
    ]
    assert token_texts == [["haec", "contentionibus"], ["restant"]]


def test_greek_cross_column_wrap_folds_final_sigma_to_medial_sigma():
    flat = [
        {"column": "1.1", "n": 1, "text": "προς-"},
        {"column": "1.2", "n": 1, "text": "ήκει καλῶς"},
    ]

    assert _apply_lined_cross_column_wraps(flat, alphabet=GREEK_LINED) == 1
    assert flat[0]["text"] == "προσήκει"
    assert flat[1]["text"] == "καλῶς"


def test_declared_cross_column_wrap_count_mismatch_raises():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><l n="1">haec ἀναγ-</l></div>
<div type="Chapter" n="2"><l n="1">καία ἐστίν</l></div>
</body></text></TEI>"""
    )

    with pytest.raises(
        ValueError,
        match=r"cross-column-fixture.*declared 2, actual 1",
    ):
        _parse_flat_chapter(tree, scheme_mod.get("section"), _flat_manifest(2))


def test_cross_column_pass_rejects_a_surviving_wrap_candidate():
    flat = [
        {"column": "1.1", "n": 1, "text": "verbum-"},
        {"column": "1.2", "n": 1, "text": "Restat"},
    ]

    with pytest.raises(ValueError, match=r"1\.1.*survived"):
        _apply_lined_cross_column_wraps(flat, alphabet=LATIN_LINED)


def test_deferred_chained_cross_column_wrap_still_raises():
    flat = [
        {"column": "1.1", "n": 1, "text": "con-"},
        {"column": "1.2", "n": 1, "text": "ten-"},
        {"column": "1.2", "n": 2, "text": "dit"},
    ]

    with pytest.raises(ValueError, match="chained"):
        _apply_lined_cross_column_wraps(flat, alphabet=LATIN_LINED)


def test_work_final_wrap_still_raises_after_deferral():
    lines = [{"column": "1.1", "n": 1, "text": "verbum-"}]
    _apply_lined_wraps(
        "1.1", lines, alphabet=LATIN_LINED, defer_column_final=True
    )

    with pytest.raises(ValueError, match=r"1\.1.*survived"):
        _apply_lined_cross_column_wraps(lines, alphabet=LATIN_LINED)


def test_closing_siglum_before_hyphen_joins():
    lines = [
        {"n": 1, "text": "haec con<ten>-"},
        {"n": 2, "text": "tionibus restant"},
    ]

    _apply_lined_wraps("1.1", lines, alphabet=LATIN_LINED)
    assert lines[0]["text"] == "haec con<ten>tionibus"
    assert lines[0]["joined"] is True
    assert lines[1]["text"] == "restant"


def test_opening_siglum_continuation_does_not_join():
    lines = [
        {"n": 1, "text": "verbum prae-"},
        {"n": 2, "text": "<tendebat> neque"},
    ]

    _apply_lined_wraps("1.1", lines, alphabet=LATIN_LINED)
    assert lines == [
        {"n": 1, "text": "verbum prae-"},
        {"n": 2, "text": "<tendebat> neque"},
    ]


# --- Class A: Latin leading-apostrophe fragment start (wave-2 preflight
# wrapO defect, 126-locus census) ------------------------------------------
# PHI Latin glues a leading ASCII `'` onto a quoted word with no space
# ('moriatur, a quotation opener) and stage3_tokenize._surface() does NOT
# edge-strip it (deliberately -- see _to_latin_lookup_key's docstring), so
# the token's own surface `t` starts ON the apostrophe. The lined fragment-
# start advance must land there too, not skip past it into the letter run,
# or `wrap`/`wrapO` are computed one character short and preflight's "wrapO
# does not match any token's `o`" FATAL fires (evidence: tusculan-
# disputations 5:5.56, "'moriatur'?" wrap=5 wrapO=33 pre-fix vs. the real
# token `'moriatur` at o=32).

def test_latin_apostrophe_glued_wrapped_word_counts_wrap_from_the_apostrophe():
    lines = [
        {"n": 1, "text": "non semel respondit, sed saepe: 'moria-"},
        {"n": 2, "text": "tur'?"},
    ]
    _apply_lined_wraps("5.56", lines, alphabet=REAL_LATIN_LINED)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "non semel respondit, sed saepe: 'moriatur'?"
    # The fragment starts ON the apostrophe, not the 'm' after it.
    assert lines[0]["wrapO"] == len("non semel respondit, sed saepe: ")
    assert lines[0]["wrap"] == len("'moria")
    assert lines[0]["text"][lines[0]["wrapO"] :].startswith("'moriatur")


def test_greek_glued_curly_quote_still_skipped_not_landed_on():
    # The Greek analogue MUST stay unchanged (Discourses' 17-locus quote
    # fix depends on it): a glued CURLY quote is stripped by _surface(), so
    # the fragment start still skips past it, unlike Latin's ASCII '.
    lines = [
        {"n": 1, "text": "λέγειν ‘Συμβήσε-", "sec": 1},
        {"n": 2, "text": "ταί τινα κακά.", "sec": 1},
    ]
    _apply_lined_wraps("1.4", lines, alphabet=GREEK_LINED)
    assert lines[0]["joined"] is True
    assert lines[0]["wrap"] == len("Συμβήσε")
    assert lines[0]["text"][lines[0]["wrapO"] :].startswith("Συμβήσε")


# --- Class B: a cross-column receiving line's OWN in-column wrapO must be
# rebased when its head is stripped for the cross-column absorption --------
# The receiving line (a column's first line) can independently end in its
# own wrap hyphen further down, already processed by `_apply_lined_wraps`
# and carrying `wrap`/`wrapO` BEFORE the cross-column pass strips N
# characters off its front. `wrapO` is an offset into `text` and must move
# left by N with it; `wrap` (a length) does not change. Evidence: lives
# 2:2.42, "Εὐβουλίδης μὲν γὰρ ἑκατόν φησιν ὁμολογῆσαι· θορυβησάντων"
# emitted wrap=6 wrapO=52 pre-fix, but the wrapped token θορυβησάντων sits
# at o=44 -- exactly the 8-char head ("Εὐβουλίδης ") absorbed from the
# prior column.

def test_cross_column_absorption_rebases_the_receiving_lines_own_wrapo():
    # Column 1.1's last line donates "δης" to column 1.2's first line
    # ("Εὐβουλί-" / "δης …"); that first line separately ends its OWN
    # in-column wrap further down ("θορυβησάν-" / "των"), already resolved
    # by `_apply_lined_wraps` before the cross-column pass runs.
    receiving_lines = [
        {
            "column": "1.2", "n": 1,
            "text": "δης μὲν γὰρ ἑκατόν φησιν ὁμολογῆσαι· θορυβησάν-",
        },
        {"column": "1.2", "n": 2, "text": "των πάντες."},
    ]
    _apply_lined_wraps("1.2", receiving_lines, alphabet=GREEK_LINED)
    pre_rebase_wrapo = receiving_lines[0]["wrapO"]
    assert receiving_lines[0]["text"] == (
        "δης μὲν γὰρ ἑκατόν φησιν ὁμολογῆσαι· θορυβησάντων"
    )

    flat = [
        {"column": "1.1", "n": 5, "text": "εἶπεν Εὐβουλί-"},
        receiving_lines[0],
    ]
    joined = _apply_lined_cross_column_wraps(flat, alphabet=GREEK_LINED)
    assert joined == 1
    assert flat[0]["text"] == "εἶπεν Εὐβουλίδης"
    assert flat[0]["joined"] is True
    assert "wrap" not in flat[0] and "wrapO" not in flat[0]

    receiving = flat[1]
    stripped = len("δης ")
    assert receiving["wrapO"] == pre_rebase_wrapo - stripped
    assert receiving["text"] == "μὲν γὰρ ἑκατόν φησιν ὁμολογῆσαι· θορυβησάντων"
    assert receiving["text"][receiving["wrapO"] :].startswith("θορυβησάντων")


def test_cross_column_rebase_to_zero_is_legal():
    # A two-word receiving line -- carried word-tail + its own wrapped word
    # -- rebases its wrapO to exactly 0: the wrapped token becomes the
    # FIRST token of the remaining text. 0 is a legal start-of-line offset,
    # not corruption (Grok gate finding, 2026-08-30).
    receiving_line = {
        "column": "1.2", "n": 1, "text": "ab restant",
        "joined": True, "wrap": 3, "wrapO": 3,
    }
    flat = [
        {"column": "1.1", "n": 5, "text": "verbum-"},
        receiving_line,
    ]
    _apply_lined_cross_column_wraps(flat, alphabet=REAL_LATIN_LINED)
    assert receiving_line["text"] == "restant"
    assert receiving_line["wrapO"] == 0
    assert receiving_line["wrap"] == 3


def test_cross_column_rebase_raising_when_wrapo_would_go_negative():
    # A wrapO that sits INSIDE the absorbed head is impossible -- raise
    # loudly rather than emit a negative offset.
    receiving_line = {
        "column": "1.2", "n": 1, "text": "ab restant",
        "joined": True, "wrap": 3, "wrapO": 1,
    }
    flat = [
        {"column": "1.1", "n": 5, "text": "verbum-"},
        receiving_line,
    ]
    with pytest.raises(ValueError, match=r"1\.2.*wrapO"):
        _apply_lined_cross_column_wraps(flat, alphabet=REAL_LATIN_LINED)


def test_cross_column_rebase_composes_with_apostrophe_glued_wrap():
    # Class A + class B on one line: the receiving line carries a
    # quote-glued in-column wrap ('moriatur at offset 16); the cross-column
    # pass strips the 9-char head and the wrapO must still land on the
    # apostrophe (Tusculans 5.56 shape meeting the lives 2.42 shape).
    receiving_line = {
        "column": "1.2", "n": 1, "text": "tionibus saepe: 'moriatur'?",
        "joined": True, "wrap": 6, "wrapO": 16,
    }
    flat = [
        {"column": "1.1", "n": 5, "text": "con-"},
        receiving_line,
    ]
    _apply_lined_cross_column_wraps(flat, alphabet=REAL_LATIN_LINED)
    assert receiving_line["text"] == "saepe: 'moriatur'?"
    assert receiving_line["wrapO"] == 7
    assert receiving_line["text"][7:].startswith("'moriatur")
    assert receiving_line["wrap"] == 6


# --- Class C: cross-script wraps (2026-08-30) -------------------------------
# A wrapped word's own script does not always match the WORK's nominal
# alphabet: an editor's citation name set in Latin glued into a Greek work
# (Lives 1.67, "(Her-" / "cher 637)."), or a Greek technical term quoted
# whole inside a Latin work (De Finibus 1.15 "σκοτει-" / "νός" et al.) -- 7
# loci corpus-wide, matching the 4.5 export's own rejoin of all seven as
# whole words. The wrap machinery's letter test is now a fixed script-union
# (`_is_wrap_letter`), not `alphabet.is_letter`, so it recognizes either
# script's letters regardless of which alphabet the calling work passes.

def test_greek_word_wrapped_inside_latin_fixture_lands_wrapo_on_greek_letters():
    # De Finibus 1.15: "σκοτεινός" (a Greek technical term Cicero quotes
    # whole) wraps across a print line inside a Latin-keyed work exactly as
    # an ordinary Latin word would.
    lines = [
        {"n": 7, "text": "ut Heraclitus, cognomento qui σκοτει-"},
        {"n": 8, "text": "νός perhibetur, quia de natura"},
    ]
    _apply_lined_wraps("1.15", lines, alphabet=REAL_LATIN_LINED)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "ut Heraclitus, cognomento qui σκοτεινός"
    assert lines[1]["text"] == "perhibetur, quia de natura"
    # wrap/wrapO land ON the Greek letters, not skipped over as non-letters
    # of the work's own (Latin) alphabet.
    assert lines[0]["text"][lines[0]["wrapO"] :] == "σκοτεινός"
    assert lines[0]["wrap"] == len("σκοτει")


def test_latin_word_wrapped_inside_greek_fixture_rejoins():
    # Lives 1.67: an editor's citation name set in Latin ("Hercher 637")
    # glued into a Greek work wraps across a print line too.
    lines = [
        {
            "n": 4,
            "text": "ἀξιώσας, νῦν ἐπανελθὼν ἀρεσκοίμην οἷς σὺ πράσσεις (Her-",
        },
        {"n": 5, "text": "cher 637)."},
    ]
    _apply_lined_wraps("1.67", lines, alphabet=GREEK_LINED)
    assert lines[0]["joined"] is True
    assert lines[0]["text"].endswith("(Hercher")
    assert lines[1]["text"] == "637)."
    assert lines[0]["text"][lines[0]["wrapO"] :] == "Hercher"
    assert lines[0]["wrap"] == len("Her")


def test_greek_sigma_fold_applies_when_wrapped_inside_latin_fixture():
    # The fold that turns a line-final ς into medial σ
    # (`_fold_hyphen_final_sigma`, Greek print-house convention) is now
    # applied universally by the wrap machinery, not gated on the work's
    # own alphabet -- a Greek word wrapped inside a LATIN-keyed work must
    # fold exactly the way it would inside a Greek-keyed one (mirrors
    # `test_greek_cross_column_wrap_folds_final_sigma_to_medial_sigma`
    # above, embedded in a Latin fixture instead).
    lines = [
        {"n": 1, "text": "ut ait ille προς-"},
        {"n": 2, "text": "ήκει bene"},
    ]
    _apply_lined_wraps("1.1", lines, alphabet=REAL_LATIN_LINED)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "ut ait ille προσήκει"
    assert lines[1]["text"] == "bene"
