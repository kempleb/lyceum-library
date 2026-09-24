"""Regression tests for stage1_citation_expansion.py (docs/citation-expansion-
wiring-design.md, PILOT slice): the ported prose-flow head-boundary rule on
real Heraclitus head shapes, direct dictionary lookup, verbatim passthrough for
dash / dash-misparse / unmappable-bracket heads, multi-source splitting at
explicit author tokens, the no-opt-in no-op (byte-identity), and the
author-known-but-work-unresolvable FATAL gate.

The real sources/dk-citations/citation-dictionary.json is used as-is (a build
input, not a fixture); only BUILD_DIR is redirected so run() never touches the
real build tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_citation_expansion as ce
from reader_pipeline.config import Manifest


@pytest.fixture(scope="module")
def dictionary():
    return ce._load_dictionary()


def _manifest(expand: bool, work_id="heraclitus-fragments") -> Manifest:
    data = {"work": {"id": work_id}}
    if expand:
        data["citation"] = {"expand_citations": True}
    return Manifest(data, Path("FIX.yaml"))


def _spine(*context_first_lines: str) -> dict:
    """One segment per head-line; each line is the first line of a context run."""
    return {"segments": [
        {"id": f"1:B{i}", "book": 1, "column": f"B{i}",
         "lines": [{"n": 1, "text": text, "role": "context"}]}
        for i, text in enumerate(context_first_lines, start=1)
    ]}


@pytest.fixture(autouse=True)
def _patch_build(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "BUILD_DIR", tmp_path / "build")


# --- Ported head-boundary rule ---------------------------------------------

def test_extract_head_only_line_no_greek_body():
    # B1: whole line is citation (isSourceHeadOnlyText branch).
    assert ce._extract_head("SEXT. adv. math. VII 132 (Vgl. A 4. 16. B 51)") == \
        "SEXT. adv. math. VII 132 (Vgl. A 4. 16. B 51)"


def test_extract_head_peels_prefix_before_first_lowercase_greek():
    # B6: head ends at the first lowercase-Greek token (ὁ).
    line = "ARISTOTELES Meteor. B 2. 355a 13 [vgl. 68 B 158] ὁ ἥλιος οὐ μόνον"
    assert ce._extract_head(line) == "ARISTOTELES Meteor. B 2. 355a 13 [vgl. 68 B 158]"


def test_extract_head_drops_greek_in_parenthetical():
    # B3: the trailing "(περὶ ...)" Greek parenthetical is body, not head.
    line = "AËT. II 21, 4 (D. 351, 20) (περὶ μεγέθους ἡλίου)"
    assert ce._extract_head(line) == "AËT. II 21, 4 (D. 351, 20)"


def test_extract_head_none_for_greek_initial_line():
    assert ce._extract_head("Ἡράκλειτος ὁ Ἐφέσιος φησι") is None


# --- Direct dictionary lookup ----------------------------------------------

def test_direct_lookup_author_work_locus(dictionary):
    entries = ce._resolve_head(dictionary, "SEXT. adv. math. VII 132", "w", "1:B1")
    assert entries == [{
        "verbatim": "SEXT. adv. math. VII 132",
        "resolution": "direct",
        "authorDisplay": "Sextus Empiricus",
        "work": {"title": "Adversus Mathematicos", "italic": True},
        "locus": "VII 132",
        "flags": [],
        "dashInherited": False,
    }]


def test_direct_lookup_falls_to_default_work(dictionary):
    # AËT. + no explicit work token -> DEFAULT (Placita); author flag carried.
    (e,) = ce._resolve_head(dictionary, "AËT. I 7, 5 (D. 299)", "w", "1:B3")
    assert e["resolution"] == "direct"
    assert e["authorDisplay"] == "Aëtius"
    assert e["work"] == {"title": "Placita", "italic": True}
    # The trailing "(D. NNN)" Diels-Doxographi page ref is apparatus, split
    # out of the locus into its own field (fix round finding 1) -- never
    # dropped, never folded into the lookup.
    assert e["locus"] == "I 7, 5"
    assert e["apparatus"] == "(D. 299)"
    assert "diels-doxographi" in e["flags"]


def test_direct_lookup_bracketed_pseudo_author(dictionary):
    (e,) = ce._resolve_head(dictionary, "[Arist.] de mundo 5. 396b 7", "w", "1:B10")
    assert e["authorDisplay"] == "pseudo-Aristotle"
    assert e["work"] == {"title": "De Mundo", "italic": True}
    assert e["locus"] == "5. 396b 7"
    assert "pseudo" in e["flags"]


def test_multi_source_splits_at_each_author(dictionary):
    # B5, post Grok-gate fixes: defect 6 strips the trailing split comma off
    # the first source's locus; defect 4 (case-fold + bare "c. Cels." key)
    # lets "c. CELS." resolve as a matched work, not a DEFAULT fall-through,
    # so it no longer sits in Origen's locus either.
    head = "ARISTOCRITUS Theosophia 68 (Buresch Klaros S. 118), ORIG. c. CELS. VII 62"
    entries = ce._resolve_head(dictionary, head, "w", "1:B5")
    assert [e["authorDisplay"] for e in entries] == ["Aristocritus", "Origen"]
    assert entries[0]["work"]["title"] == "Theosophia"
    assert entries[0]["locus"] == "68 (Buresch Klaros S. 118)"
    assert entries[1]["work"]["title"] == "Contra Celsum"
    assert entries[1]["locus"] == "VII 62"


# --- Verbatim passthrough (honest "as printed") ----------------------------

def test_single_dash_head_is_verbatim(dictionary):
    assert ce._resolve_head(dictionary, "—de sensu 5. 443a 23", "w", "1:B7") == [
        {"verbatim": "—de sensu 5. 443a 23", "resolution": "verbatim",
         "flags": ["dash-continuation"]}]


def test_double_dash_head_is_verbatim(dictionary):
    (e,) = ce._resolve_head(dictionary, "— —34 (p. 26, 6)", "w", "1:B15")
    assert e["resolution"] == "verbatim"
    assert e["flags"] == ["dash-continuation"]


def test_bracketed_unmappable_apparatus_is_verbatim(dictionary):
    (e,) = ce._resolve_head(dictionary, "[Stob. II 15, 33]", "w", "1:B99")
    assert e["resolution"] == "verbatim"
    assert e["flags"] == ["unmappable"]
    assert "authorDisplay" not in e


def test_non_citation_head_yields_no_entry(dictionary):
    # A leading token that matches no author / dash / misparse / bracket is not
    # a citation head (e.g. editorial prose) -> no fabricated entry.
    assert ce._resolve_head(dictionary, "Nach B 6 folgt", "w", "1:B1") == []


# --- Fatal gate: author known, work unresolvable, no DEFAULT ----------------

def test_author_known_but_no_work_and_no_default_is_fatal(dictionary):
    # MARC. is a dictionary author (Marcus Aurelius) whose only works are
    # ANTON./Anton. and which has no DEFAULT; a bare "MARC. IX 99" therefore
    # names no resolvable work -> fatal, never fabricated.
    with pytest.raises(ValueError, match="names no work"):
        ce._resolve_head(dictionary, "MARC. IX 99", "heraclitus-fragments", "1:B1")


def test_run_propagates_fatal(tmp_path):
    manifest = _manifest(expand=True)
    spine = _spine("MARC. IX 99")
    with pytest.raises(ValueError, match="names no work"):
        ce.run(manifest, spine)


# --- Opt-in gating / byte-identity -----------------------------------------

def test_no_opt_in_returns_none_and_writes_nothing(tmp_path):
    manifest = _manifest(expand=False)
    spine = _spine("SEXT. adv. math. VII 132")
    assert ce.run(manifest, spine) is None
    assert not (tmp_path / "build" / "stage1" / "citation_expansion.json").exists()


def test_run_emits_only_segments_with_heads(tmp_path):
    # Fix round finding 2: the emitted value is a list of RUNS (one list per
    # context run, document order), never a flattened list of entries.
    manifest = _manifest(expand=True)
    spine = _spine(
        "SEXT. adv. math. VII 132",           # 1:B1 direct
        "Ἡράκλειτος ὁ Ἐφέσιος φησι",           # 1:B2 no head -> absent
        "—de sensu 5. 443a 23",               # 1:B3 verbatim
    )
    out = ce.run(manifest, spine)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert set(result) == {"1:B1", "1:B3"}
    assert result["1:B1"] == [[{
        "verbatim": "SEXT. adv. math. VII 132",
        "resolution": "direct",
        "authorDisplay": "Sextus Empiricus",
        "work": {"title": "Adversus Mathematicos", "italic": True},
        "locus": "VII 132",
        "flags": [],
        "dashInherited": False,
    }]]
    assert result["1:B3"] == [[
        {"verbatim": "—de sensu 5. 443a 23", "resolution": "verbatim",
         "flags": ["dash-continuation"]},
    ]]


def test_run_keeps_distinct_runs_separate_b37(tmp_path):
    # DEFECT 2 regression: real Heraclitus B37 carries TWO separate context
    # runs in one column -- "COLUMELLA VIII 4..." (a Latin quote-intro head)
    # and, later in the same column, an unrelated "[vgl. B 13]," editorial
    # cross-reference. They must stay two run slots, never merged into one
    # flattened, semicolon-joined false attribution.
    manifest = _manifest(expand=True)
    spine = {"segments": [{
        "id": "1:B37", "book": 1, "column": "B37",
        "lines": [
            {"n": 1, "text": "COLUMELLA VIII 4 si modo credimus Ephesio Heracleto qui ait",
             "role": "context"},
            {"n": 2, "text": "igni omnia ista constare.", "role": "context"},
            {"n": -1, "text": "Nach B 6 folgt der Übergang.", "role": "text"},
            {"n": 3, "text": "[vgl. B 13],", "role": "context"},
        ],
    }]}
    out = ce.run(manifest, spine)
    result = json.loads(out.read_text(encoding="utf-8"))
    runs = result["1:B37"]
    assert len(runs) == 2
    assert runs[0][0]["authorDisplay"] == "Columella"
    assert runs[0][0]["resolution"] == "direct"
    assert runs[1] == [{"verbatim": "[vgl. B 13],", "resolution": "verbatim",
                         "flags": ["unmappable"]}]


# --- Grok content-gate fix round (2026-07-24): 12 locus-hygiene defects ----
# Real extracted heads from the Heraclitus pilot (see build/stage1/
# greek_spine.json first "context" lines for each column). Attribution was
# verified sound by the gate; every one of these is purely a locus (or, for
# defects 2/4, a work-match) boundary bug.


def test_defect1_porphyr_zu_homeric_questions_b102(dictionary):
    # PORPHYR.'s "zu <Greek Iliad book-letter> <n> [...]" citation form
    # (Quaestiones Homericae); the Greek letter is a traditional book numeral,
    # not prose -- kept verbatim in the locus (locus_includes_work).
    (e,) = ce._resolve_head(dictionary, "PORPHYR. zu Δ 4 [I 69, 6 Schr.]", "w", "1:B102")
    assert e["authorDisplay"] == "Porphyry"
    assert e["work"]["title"] == "Quaestiones Homericae"
    assert e["locus"] == "zu Δ 4 [I 69, 6 Schr.]"


def test_defect1_porphyr_zu_homeric_questions_b103(dictionary):
    (e,) = ce._resolve_head(dictionary, "PORPHYR. zu Ξ 200 [I 190 Schr.]", "w", "1:B103")
    assert e["authorDisplay"] == "Porphyry"
    assert e["work"]["title"] == "Quaestiones Homericae"
    assert e["locus"] == "zu Ξ 200 [I 190 Schr.]"


def test_defect2_arius_did_variant_b12(dictionary):
    # "ARIUS DID." must match as one author variant; "DID." was leaking into
    # the locus when only "ARIUS" matched.
    (e,) = ce._resolve_head(
        dictionary, "ARIUS DID. ap. Eus. P. E. XV 20 (D. 471, 1)", "w", "1:B12")
    assert e["authorDisplay"] == "Arius Didymus"
    assert e["locus"] == "ap. Eus. P. E. XV 20"
    assert e["apparatus"] == "(D. 471, 1)"


def test_defect3_catal_codd_astrol_graec_b139(dictionary):
    (e,) = ce._resolve_head(
        dictionary, "CATAL. CODD. ASTROL. GRAEC. IV 32 VII 106", "w", "1:B139")
    assert e["authorDisplay"] == "Catalogus Codicum Astrologorum"
    assert e["work"]["title"] == "Catalogus Codicum Astrologorum Graecorum"
    assert e["locus"] == "IV 32 VII 106"


def test_defect4_case_insensitive_work_abbrev_b5(dictionary):
    (e,) = ce._resolve_head(dictionary, "ORIG. c. CELS. VII 62", "w", "1:B5")
    assert e["authorDisplay"] == "Origen"
    assert e["work"]["title"] == "Contra Celsum"
    assert e["locus"] == "VII 62"


def test_defect5_work_key_trailing_p_not_consumed_b104(dictionary):
    # "in Alc. I p." must not swallow the printed "p." into the work marker.
    (e,) = ce._resolve_head(
        dictionary, "PROCL. in Alc. I p. 525, 21 (1864)", "w", "1:B104")
    assert e["work"]["title"] == "in Platonis Alcibiadem I"
    assert e["locus"] == "p. 525, 21 (1864)"


def test_defect5_work_key_trailing_p_not_consumed_b126a(dictionary):
    (e,) = ce._resolve_head(
        dictionary,
        "ANATOL. de decade p. 36 Heiberg (Annales d'histoire. Congres de Paris 1901. 5. section)",
        "w", "1:B126a")
    assert e["work"]["title"] == "De Decade"
    assert e["locus"] == "p. 36 Heiberg (Annales d'histoire. Congres de Paris 1901. 5. section)"


def test_defect6_multi_source_split_strips_trailing_comma_b5(dictionary):
    head = "ARISTOCRITUS Theosophia 68 (Buresch Klaros S. 118), ORIG. c. CELS. VII 62"
    entries = ce._resolve_head(dictionary, head, "w", "1:B5")
    assert entries[0]["authorDisplay"] == "Aristocritus"
    assert entries[0]["locus"] == "68 (Buresch Klaros S. 118)"


def test_defect7_capitalized_greek_abbrev_ends_locus_b50(dictionary):
    # "Ἡ." (short for Ἡράκλειτος) has no lowercase Greek of its own, so the
    # ported head-boundary rule doesn't stop before it; it's quoted-text
    # lead-in, not locus.
    (e,) = ce._resolve_head(
        dictionary, "HIPPOL. Refut. IX 9 Ἡ.", "w", "1:B50")
    assert e["authorDisplay"] == "Hippolytus"
    assert e["locus"] == "IX 9"


def test_defect8_latin_head_drops_quote_intro_b4(dictionary):
    (e,) = ce._resolve_head(
        dictionary, "ALBERTUS M. de veget. VI 401 p. 545 Meyer H. dixit quod", "w", "1:B4")
    assert e["authorDisplay"] == "Albertus Magnus"
    assert e["locus"] == "VI 401 p. 545 Meyer"


def test_defect8_latin_head_drops_quote_intro_b37(dictionary):
    (e,) = ce._resolve_head(
        dictionary, "COLUMELLA VIII 4 si modo credimus Ephesio Heracleto qui ait", "w", "1:B37")
    assert e["authorDisplay"] == "Columella"
    assert e["locus"] == "VIII 4"


def test_defect8_latin_head_keeps_only_citation_bracket_b67a(dictionary):
    head = (
        "HISDOSUS Scholasticus ad Chalcid. Plat. Tim. [cod. Paris. l. 8624 s. XII f. 2] "
        "ita vitalis calor a sole procedens omnibus quae vivunt vitam subministrat. cui "
        "sententiae Heraclitus adquiescens optimam similitudinem dat de aranea ad animam, "
        "de tela araneae ad corpus."
    )
    (e,) = ce._resolve_head(dictionary, head, "w", "1:B67a")
    assert e["authorDisplay"] == "Hisdosus Scholasticus"
    assert e["work"]["title"] == "in Chalcidii Timaeum (glossa)"
    assert e["locus"] == "[cod. Paris. l. 8624 s. XII f. 2]"
