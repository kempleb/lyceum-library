"""Regression tests for stage1_citation_expansion.py (docs/citation-expansion-
wiring-design.md phases 1-3): the ported prose-flow head-boundary rule on
real Heraclitus head shapes, direct dictionary lookup, verbatim passthrough for
unmappable-bracket heads, multi-source splitting at explicit author tokens, the
no-opt-in no-op (byte-identity), the author-known-but-work-unresolvable FATAL
gate, and dash citations under rule E (John, 2026-09-24) with their honest
verbatim fallbacks.

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
    line = "ARISTOTELES Meteor. B 2. 355a 13 [vgl. 68 B 158] ὁ λύχνος οὐ πάντως"
    assert ce._extract_head(line) == "ARISTOTELES Meteor. B 2. 355a 13 [vgl. 68 B 158]"


def test_extract_head_drops_greek_in_parenthetical():
    # B3: the trailing "(περὶ ...)" Greek parenthetical is body, not head.
    line = "AËT. II 21, 4 (D. 351, 20) (περὶ σχήματος ἄστρου)"
    assert ce._extract_head(line) == "AËT. II 21, 4 (D. 351, 20)"


def test_extract_head_none_for_greek_initial_line():
    assert ce._extract_head("Νικόστρατος ὁ Κορίνθιος φησι") is None


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

def test_single_dash_head_alone_is_verbatim_unresolved(dictionary):
    # No walk-back state passed = nothing precedes it: no antecedent.
    assert ce._resolve_head(dictionary, "—de sensu 5. 443a 23", "w", "1:B7") == [
        {"verbatim": "—de sensu 5. 443a 23", "resolution": "verbatim",
         "flags": ["dash-unresolved"]}]


def test_double_dash_head_alone_is_verbatim_unresolved(dictionary):
    (e,) = ce._resolve_head(dictionary, "— —34 (p. 26, 6)", "w", "1:B15")
    assert e["resolution"] == "verbatim"
    assert e["flags"] == ["dash-unresolved"]


def test_bracketed_unmappable_apparatus_is_verbatim(dictionary):
    (e,) = ce._resolve_head(dictionary, "[Stob. II 15, 33]", "w", "1:B99")
    assert e["resolution"] == "verbatim"
    assert e["flags"] == ["unmappable"]
    assert "authorDisplay" not in e


@pytest.mark.parametrize("head", [
    "[B 40].", "[B 41].", "[B 42]. (2)", "[B 43]", "[B 44].",
    "[B 121].", "[B 45].", "[B 1],", '[B 116]".’',
    "[vgl. 22 B 31].", "[B 125]", "[A 10]", "[B 298a]",
    "[B 1. 2]", "[B 40, 41]", "[B 40 u. 41]", "[B 40 und 41]",
    "[cf. 90 C 7]", "[s. B 2]", "[vgl B 9]", "[B 6a]·", "[B 6 b]",
    "[B 78—81]", "[B 1—44]", "[B 1–44]", "[B 1-44]",
    "[B 17, 17—20].", "[B 17, 7. 8].",
    "[Β 1, 28—30].", "[Β 8, 4].", "[Α 1]", "[Γ 7]",
    "[B 99; vgl. A 93]:", "[B 99; s. A 93]", "[B 99; cf. A 93]",
    "[B 4 Ende]).", "[B 11 II 37, 12].", "[B 12 II 39, 6]",
    "[vgl. 166, 15].", "[31 B 39];",
])
def test_dk_cross_reference_is_not_a_citation(dictionary, head):
    assert ce._resolve_head(dictionary, head, "w", "1:A1") == []


@pytest.mark.parametrize("head", [
    "[Stob. III 13, 46].",
    "[B 13] ceteraque generis eiusdem …",
    "[B 6]. ac primum diesin …",
    "[s. II 254, 21. 255, 12. 256, 11] dicitur. …",
    "[31 B 39]; p. 522, 7 Heib.",
    "[ohne", "[sc.", "[Thrasymachos]",
    "[PLG II 269 B., ALG I 78 D.]",
    "[d. Rhamn., d. caed. Her. 27]",
    "[fr. 4 P. Lang Bonn 1911 S. 53ff.],",
])
def test_bracketed_source_or_text_stays_verbatim(dictionary, head):
    assert ce._resolve_head(dictionary, head, "w", "1:A1") == [
        {"verbatim": head, "resolution": "verbatim", "flags": ["unmappable"]}]


def test_bracketed_latin_passage_stays_verbatim(dictionary):
    head = "[s. II 254, 21. 255, 12. 256, 11] dicitur. …"
    assert ce._resolve_head(dictionary, head, "protagoras-fragments", "1:B6") == [
        {"verbatim": head, "resolution": "verbatim", "flags": ["unmappable"]}]


def test_non_citation_head_yields_no_entry(dictionary):
    # A leading token that matches no author / dash / misparse / bracket is not
    # a citation head (e.g. editorial prose) -> no fabricated entry.
    assert ce._resolve_head(dictionary, "Nach B 6 folgt", "w", "1:B1") == []


# --- Fatal gate: author known, work unresolvable, no DEFAULT ----------------

def test_author_known_but_no_work_and_no_default_is_fatal(dictionary):
    # EUDEM. is a dictionary author (Eudemus of Rhodes) whose only works are
    # Eth./Phys./"bei Simpl. Phys." and which has no DEFAULT; a bare "EUDEM.
    # IX 99" therefore names no resolvable work -> fatal, never fabricated.
    # (MARC. was the example until 2026-09-28, when Heraclitus B76's "MARC.
    # IV 46" gave Marcus Aurelius a DEFAULT.)
    with pytest.raises(ValueError, match="names no work"):
        ce._resolve_head(dictionary, "EUDEM. IX 99", "heraclitus-fragments", "1:B1")


def test_run_propagates_fatal(tmp_path):
    manifest = _manifest(expand=True)
    spine = _spine("EUDEM. IX 99")
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
        "Νικόστρατος ὁ Κορίνθιος φησι",           # 1:B2 no head -> absent
        "—de sensu 5. 443a 23",               # 1:B3 R3, Sextus has no de sensu
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
         "flags": ["dash-unresolved", "dash-work-not-in-dictionary"]},
    ]]


def test_run_keeps_distinct_runs_separate_b37(tmp_path):
    # DEFECT 2 regression: real Heraclitus B37 carries TWO separate context
    # runs in one column -- "COLUMELLA VIII 4..." (a Latin quote-intro head)
    # and, later in the same column, an unrelated "[vgl. B 13]," editorial
    # cross-reference. They stay in two run slots; the cross-reference has
    # no citation entry.
    manifest = _manifest(expand=True)
    spine = {"segments": [{
        "id": "1:B37", "book": 1, "column": "B37",
        "lines": [
            {"n": 1, "text": "COLUMELLA VIII 4 si vero credimus Empedocli Agrigentino qui dixit",
             "role": "context"},
            {"n": 2, "text": "aqua cuncta haec pendere.", "role": "context"},
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
    assert runs[1] == []


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
        dictionary, "COLUMELLA VIII 4 si vero credimus Empedocli Agrigentino qui dixit", "w", "1:B37")
    assert e["authorDisplay"] == "Columella"
    assert e["locus"] == "VIII 4"


def test_defect8_latin_head_keeps_only_citation_bracket_b67a(dictionary):
    head = (
        "HISDOSUS Scholasticus ad Chalcid. Plat. Tim. [cod. Paris. l. 8624 s. XII f. 2] "
        "ita naturalis vapor a luna oriens cunctis quae crescunt robur ministrat. huic "
        "opinioni Empedocles consentiens pulchram imaginem sumit de igne ad mentem, "
        "de flamma ignis ad membra."
    )
    (e,) = ce._resolve_head(dictionary, head, "w", "1:B67a")
    assert e["authorDisplay"] == "Hisdosus Scholasticus"
    assert e["work"]["title"] == "in Chalcidii Timaeum (glossa)"
    assert e["locus"] == "[cod. Paris. l. 8624 s. XII f. 2]"


# --- Title-abbreviation leftovers + Suda/author redundancy (2026-09-27, ----
# fifth round: John's review) -------------------------------------------------

@pytest.mark.parametrize("head,locus", [
    # Heraclitus A3a: DK prints the title abbreviation lower-case ("H. n.");
    # it fell through to DEFAULT unconsumed and sat at the front of the locus.
    ("PLIN. H. n. XXXIV 21", "XXXIV 21"),
    # Democritus A76: the DEFAULT note already claimed 'N. HIST.' worked as
    # well as 'N. H.', but only 'N. H.' was ever a key.
    ("PLIN. N. HIST. II 14", "II 14"),
    # The already-working spelling stays working.
    ("PLIN. N. H. II 149 f.", "II 149 f."),
])
def test_pliny_title_abbreviation_is_consumed_not_left_in_locus(dictionary, head, locus):
    (e,) = ce._resolve_head(dictionary, head, "w", "1:B1")
    assert e["authorDisplay"] == "Pliny the Elder"
    assert e["work"]["title"] == "Naturalis Historia"
    assert e["locus"] == locus


def test_gellius_title_abbreviation_is_consumed_not_left_in_locus(dictionary):
    # Xenophanes B13: "N. A." (Noctes Atticae) is DK's own abbreviation, not
    # a locus token.
    (e,) = ce._resolve_head(dictionary, "GELLIUS N. A. III 11", "w", "1:B13")
    assert e["authorDisplay"] == "Aulus Gellius"
    assert e["work"]["title"] == "Noctes Atticae"
    assert e["locus"] == "III 11"


def test_suda_title_does_not_repeat_the_author(dictionary):
    # Heraclitus B122's printed line is "SUID. s. v. ἀγχιβατεῖν ἀμφισβατεῖν·"
    # (role "context"): the head-extraction rule ends a head at the first
    # lowercase Greek, so "SUID. s. v." is all the head itself carries, but
    # the headword right after it belongs to the citation, not the passage
    # (GPT-6-Sol review, 2026-09-27 -- the earlier version of this test
    # dropped the headword from its input and so never exercised the
    # completion; fixed here to the real printed line via `_located`, which
    # runs head-extraction the way the pipeline does). The Suda is cited by
    # its own name, not a person's: a separate work title only repeated it
    # ("Suda, Lexicon (Suda)"). With a real locus the title is empty, so the
    # printed form is "Suda, s.v. ἀγχιβατεῖν" -- unlike Hesychius/
    # Harpocration, whose lexica are real titled works distinct from their
    # names and so keep one.
    (h,) = _located(dictionary, ("context", "SUID. s. v. ἀγχιβατεῖν ἀμφισβατεῖν·"))
    e = h["expanded"][0]
    assert e["authorDisplay"] == "Suda"
    assert e["work"]["title"] == ""
    assert e["locus"] == "s.v. ἀγχιβατεῖν"


def test_suda_bare_head_falls_back_to_a_title_not_a_dangling_comma(dictionary):
    # A bare "SUID."/"SUIDAS" with nothing after it has no locus to follow an
    # empty title, so it falls back to "Lexicon" (as Hesychius' own lexicon
    # is titled) rather than rendering as a dangling "Suda,".
    for head in ("SUID.", "SUIDAS"):
        (e,) = ce._resolve_head(dictionary, head, "w", "1:B10")
        assert e["authorDisplay"] == "Suda"
        assert e["work"] == {"title": "Lexicon", "italic": True}
        assert e["locus"] == ""


# --- Dash citations: rule E (John, 2026-09-24) ------------------------------
# Read what follows the dashes, never how many there are:
#   1. the source is the last author named, walking back in document order
#      through the work (across columns); a work title that author did not
#      write, or a "(D. NNN)" Doxographi page, sends the walk to the nearest
#      earlier source that fits -- which may be one named inside a passage;
#   2. nothing follows: the same place as the citation above (a lexicon: s.v.
#      the headword that follows);
#   3. a work title follows: same author, that work, the locus as printed;
#   4. a book numeral (Roman or book letter) follows: same author and work,
#      the locus as printed;
#   5. only numbers follow: keep the citation above and replace the same
#      number of trailing parts, like for like.
# Where rule E cannot give a complete, certain citation the head stays
# verbatim with a flag. Every example below is a real DK head (survey of all
# 613 dash heads, 2026-09-24) unless marked synthetic.


def _run(spine, work_id="heraclitus-fragments") -> dict:
    out = ce.run(_manifest(expand=True, work_id=work_id), spine)
    return json.loads(out.read_text(encoding="utf-8"))


def _seg(seg_id: str, *lines) -> dict:
    """A segment; a plain string is a context line, a (role, text) pair sets
    the role."""
    out = []
    for i, line in enumerate(lines, 1):
        role, text = line if isinstance(line, tuple) else ("context", line)
        out.append({"n": i, "text": text, "role": role})
    return {"id": seg_id, "book": 1, "column": seg_id.split(":")[1], "lines": out}


def _cite(entry: dict) -> tuple:
    return (entry["resolution"], entry["authorDisplay"], entry["work"]["title"], entry["locus"])


def _verbatim_flags(entry: dict) -> list[str]:
    assert entry["resolution"] == "verbatim", entry
    assert "authorDisplay" not in entry
    return entry["flags"]


def test_rule_e_diogenes_heraclitus_b39_to_b45():
    # Steps 2 and 5 on Diogenes IX: "— —φαίνεσθαι δὴ" repeats IX 1; "— —2"
    # replaces the last part of IX 1 (= IX 2), whatever the dash count says.
    # B42 and B44 are dash lines the spine marks as text: they are heads too.
    result = _run({"segments": [
        _seg("1:B39", "DIOG. I 88", ("text", "ἐν Θήβαις Κρίτων ἐγένετο"), "."),
        _seg("1:B40", "—IX 1 [s. A 1 I 140, 2, vgl. ATHEN. XIII 610 B]",
             ("text", "πολυπειρίη νοῦν ἔχειν οὐ παιδεύει"), "."),
        _seg("1:B41", "— —φαίνεσθαι δὴ", ("text", "πᾶν τόδε κρυπτόν")),
        _seg("1:B42", ("text", "— —ὅνπερ καὶ Μίδην"), "ἔλεγεν", ("text", "ἱκανὸν ἐκ τῶν θρόνων"),
             "ὡσαύτως [vgl. A 22 B 56]."),
        _seg("1:B43", "— —2", ("text", "λύπην δεῖ παύειν")),
        _seg("1:B44", ("text", "— —πείθεσθαι δεῖ τὸν ἄρχοντα"), "."),
        _seg("1:B45", "— —7", ("text", "σώματος πέρατα ζητῶν"), "."),
    ]})
    dl = ("dash", "Diogenes Laertius", "Vitae Philosophorum")
    (b40,) = result["1:B40"][0]
    assert _cite(b40) == dl + ("IX 1 [s. A 1 I 140, 2, vgl. ATHEN. XIII 610 B]",)
    assert _cite(result["1:B41"][0][0]) == dl + ("IX 1",)
    assert result["1:B41"][0][0]["verbatim"] == "— —"
    assert _cite(result["1:B42"][0][0]) == dl + ("IX 1",)
    assert _cite(result["1:B43"][0][0]) == dl + ("IX 2",)
    assert _cite(result["1:B44"][0][0]) == dl + ("IX 2",)
    assert _cite(result["1:B45"][0][0]) == dl + ("IX 7",)
    assert result["1:B45"][0][0]["dashInherited"] is True


def test_rule_e_text_line_head_gets_its_own_run_slot():
    # B42's head is on a text-role line; the context run after it has no
    # head, so it contributes nothing -- one slot, the dash head's.
    result = _run({"segments": [
        _seg("1:B40", "DIOG. IX 1"),
        _seg("1:B42", ("text", "— —ὅνπερ καὶ Μίδην"), "ἔλεγεν", ("text", "ἱκανόν"), "ὡσαύτως."),
    ]})
    assert len(result["1:B42"]) == 1


def test_rule_e_plutarch_heraclitus_b92_to_b95():
    result = _run({"segments": [
        _seg("1:B92", "PLUT. de Pyth. or. 6 p. 397 A Οὐχ ὁρᾶις"),
        _seg("1:B93", "— —21 p. 404 D", ("text", "ὁ ἄναξ")),
        _seg("1:B94", "—de exil. 11 p. 604 A", ("text", "Ἥλιος γὰρ")),
        _seg("1:B95", "—Sympos. III pr. 1 p. 644 F", ("text", "ἀμαθίην γὰρ")),
    ]})
    assert _cite(result["1:B93"][0][0]) == ("dash", "Plutarch", "De Pythiae Oraculis", "21 p. 404 D")
    assert _cite(result["1:B94"][0][0]) == ("dash", "Plutarch", "De Exilio", "11 p. 604 A")
    assert _cite(result["1:B95"][0][0]) == \
        ("dash", "Plutarch", "Quaestiones Convivales", "III pr. 1 p. 644 F")


def test_rule_e_simplicius_anaxagoras_b7_to_b9():
    # Step 3 then step 5: "—Phys." is Simplicius on the Physics, NOT de caelo,
    # and "— —35, 13" replaces both parts of 175, 11.
    result = _run({"segments": [
        _seg("1:B7", "SIMPLIC. de caelo 608, 23 (nach"),
        _seg("1:B8", "—Phys. 175, 11 λέγοντος τοῦ Θεοδώρου"),
        _seg("1:B9", "— —35, 13 θεώρησον δὲ ὅσα"),
    ]}, work_id="anaxagoras-fragments")
    assert _cite(result["1:B8"][0][0]) == ("dash", "Simplicius", "in Aristotelis Physica", "175, 11")
    assert _cite(result["1:B9"][0][0]) == ("dash", "Simplicius", "in Aristotelis Physica", "35, 13")


def test_rule_e_pollux_critias_b53_to_b58():
    result = _run({"segments": [
        _seg("1:B53", "POLL. II 58", ("text", "διοπτεύειν"), "Κ. καὶ Ἀντιφῶν [87 B 6]."),
        _seg("1:B54", "— —122 παρὰ δὲ Κ—ίαι καὶ", ("text", "λογεὺς"), "ὁ κῆρυξ."),
        _seg("1:B55", "— —148", ("text", "ταχύχειρ"), "ὥσπερ Κ."),
        _seg("1:B56", "—III 116 καὶ ὥσπερ Κ.", ("text", "ῥυπαρία"), "."),
        _seg("1:B57", "—IV 64 Κ—ίαι τὰς περὶ σκάφος γραφάς"),
        _seg("1:B58", "— —165 παρὰ Κ—ίαι", ("text", "διδραχμιαῖοι"), "."),
    ]}, work_id="critias-fragments")
    loci = {s: result[s][0][0]["locus"] for s in ("1:B54", "1:B56", "1:B57", "1:B58")}
    assert loci == {"1:B54": "II 122", "1:B56": "III 116",
                    "1:B57": "IV 64", "1:B58": "IV 165"}
    assert {result[s][0][0]["authorDisplay"] for s in loci} == {"Julius Pollux"}
    # Rule E reads B55 as II 148, but the TLG has the gloss at II 149: John
    # checks the print first (2026-09-24), so it stays as printed until then.
    assert _verbatim_flags(result["1:B55"][0][0]) == ["awaiting-print-check"]


def test_rule_e_aetius_leucippus_a25_to_a31():
    # A30's passage carries an undashed Aëtius continuation "8, 10 (D. 395)";
    # A31's "— —14, 2" keeps book IV from it.
    result = _run({"segments": [
        _seg("1:A25", "AËT. III 3, 10 (D. 369) Λ. ὕδατος ἀπολειφθέντος"),
        _seg("1:A26", "— —10, 4 (D. 377) Λ. τυμπανοειδῆ."),
        _seg("1:A27", "— —12, 1 (D. 377) Λ. διαφυγεῖν τὸν ἀέρα"),
        _seg("1:A28", "ARISTOT. de anima Α 2. 404a 1 Λεύκιππος δὲ ὕδωρ τι"),
        _seg("1:A29", "AËT. IV 13, 1 (D. 403) Λ., Δημόκριτος"),
        _seg("1:A30", "—IV 8, 5 (D. 394) Λ., Δημόκριτος τινὰς νοήσεις εἶναι τοῦ πνεύματος. "
                      "8, 10 (D. 395) Λ., Δημόκριτος"),
        _seg("1:A31", "— —14, 2 (D. 405) Λ., Δημόκριτος, Ἐπίκουρος"),
    ]}, work_id="leucippus-testimonia")
    got = {s: (result[s][0][0]["locus"], result[s][0][0]["apparatus"])
           for s in ("1:A26", "1:A27", "1:A30", "1:A31")}
    assert got == {"1:A26": ("III 10, 4", "(D. 377)"), "1:A27": ("III 12, 1", "(D. 377)"),
                   "1:A30": ("IV 8, 5", "(D. 394)"), "1:A31": ("IV 14, 2", "(D. 405)")}
    assert {result[s][0][0]["authorDisplay"] for s in got} == {"Aëtius"}


def test_rule_e_stobaeus_democritus_b190_to_b193():
    result = _run({"segments": [
        _seg("1:B190", "STOB. III 1, 91 Δ—ου.", ("text", "φαύλων ἔργων"), "."),
        _seg("1:B191", "— —210 Δ—ου.", ("text", "ἀνθρώποισι γὰρ"), "."),
        _seg("1:B192", "—2, 36 Δ—ου.", ("text", "ἔστι ῥάιδιον"), "."),
        _seg("1:B193", "—3, 43 Δ—ου.", ("text", "φρονήσιος ἔργον"), "."),
    ]}, work_id="democritus-fragments")
    assert [result[s][0][0]["locus"] for s in ("1:B191", "1:B192", "1:B193")] == \
        ["III 1, 210", "III 2, 36", "III 3, 43"]
    assert result["1:B191"][0][0]["work"]["title"] == "Anthologium"


def test_rule_e_step5_counts_parts_not_dashes():
    # Real Heraclitus B21 -> B35: three dashes or two, "—10" after "IV 4" is
    # IV 10 and "— —141" after "V 116" is V 141 (Strom. V: Staehlin II 421).
    result = _run({"segments": [
        _seg("1:B21", "CLEM. Strom. III 21 (II 205, 7) οὐδὲ γὰρ Ἡ."),
        _seg("1:B22", "— —IV 4 (II 249, 23)"),
        _seg("1:B23", "— — —10 (II 252, 25)"),
        _seg("1:B28", "— —V 9 (II 331, 20)"),
        _seg("1:B29", "— — —60 (II 366, 11) vgl. IV 50 (II 271, 17)"),
        _seg("1:B32", "— — —116 (II 404, 1)"),
        _seg("1:B33", "— — —τρόπος καὶ δόξα πείθεσθαι νέων."),
        _seg("1:B35", "— —141 (II 421, 4)"),
    ]})
    loci = [result[s][0][0]["locus"] for s in ("1:B23", "1:B29", "1:B32", "1:B33", "1:B35")]
    assert loci == ["IV 10 (II 252, 25)", "V 60 (II 366, 11)", "V 116 (II 404, 1)", "V 116",
                    "V 141 (II 421, 4)"]
    assert {result[s][0][0]["work"]["title"] for s in ("1:B23", "1:B35")} == {"Stromata"}


def test_rule_e_step5_like_for_like_column_letter():
    # Real Heraclitus B82 -> B83: "— —B" replaces the column letter of 289 A.
    result = _run({"segments": [
        _seg("1:B82", "PLATO Hipp. maior 289 A λεόντων ὁ γενναιότατος"),
        _seg("1:B83", "— —B δαιμόνων ὁ εὐγενέστατος"),
    ]})
    assert _cite(result["1:B83"][0][0]) == ("dash", "Plato", "Hippias Maior", "289 B")


def test_rule_e_step5_mismatched_parts_stay_verbatim():
    # Synthetic: a Bekker line number cannot replace a Stephanus column.
    result = _run({"segments": [
        _seg("1:B1", "PLATO Hipp. maior 289 A"),
        _seg("1:B2", "— —355a 13"),
    ]})
    assert _verbatim_flags(result["1:B2"][0][0]) == ["dash-unresolved", "dash-locus-mismatch"]


def test_rule_e_doubtful_locus_stays_verbatim():
    # Synthetic: a dash whose printed locus carries an editorial doubt mark
    # ("(?)", Diels' own uncertainty about the numeral) is not expanded on a
    # guess -- it stays verbatim, flagged locus-doubtful, not dash-e5.
    result = _run({"segments": [
        _seg("1:B1", "STOB. I 1, 4"),
        _seg("1:B2", "— —5 (?)"),
    ]}, work_id="democritus-fragments")
    assert _verbatim_flags(result["1:B2"][0][0]) == ["locus-doubtful"]


def test_rule_e_step4_book_numeral_keeps_author_and_work():
    # Real Heraclitus B108 -> B116 -> B119 (Stobaeus Florilegium).
    result = _run({"segments": [
        _seg("1:B108", "STOB. Flor. I 174 Hense Ἡρακλείτου."),
        _seg("1:B110", "— —176"),
        _seg("1:B116", "— —V 6"),
        _seg("1:B117", "— —7"),
        _seg("1:B119", "— —IV 40, 23 Ἡ. εἶπεν ὅτι"),
    ]})
    flor = "Florilegium (Anthologii libri III-IV)"
    assert [(result[s][0][0]["work"]["title"], result[s][0][0]["locus"])
            for s in ("1:B110", "1:B116", "1:B117", "1:B119")] == \
        [(flor, "I 176"), (flor, "V 6"), (flor, "V 7"), (flor, "IV 40, 23")]


def test_rule_e_lexicon_dash_is_s_v_the_headword():
    # Real Antiphon B4 -> B5 -> B15 (Harpocration) and Parmenides B22 -> B23
    # (Suda, "—S. V." printed): a dash plus a word is s.v. that headword.
    result = _run({"segments": [
        _seg("1:B4", "HARPOCR.", ("text", "ἄοπτα:"), "μᾶλλον ἢ φανερά"),
        _seg("1:B5", "—", ("text", "ἀπαθῆ"), "· μᾶλλον ἢ ὅσα μὴ καλῶς εἰρημένα ῥήματα ἀτελῆ Ἀ."),
        _seg("1:B15", "—ἔμβιος: Ἀ.", ("text", "Ἀληθείας α·")),
    ]}, work_id="antiphon-sophist-fragments")
    b5 = result["1:B5"][0][0]
    assert _cite(b5) == ("dash", "Harpocration", "Lexicon in Decem Oratores", "s.v. ἀπαθῆ")
    assert b5["verbatim"] == "—"
    assert result["1:B15"][0][0]["locus"] == "s.v. ἔμβιος"
    result = _run({"segments": [
        _seg("1:B22", "SUIDAS s. v. ὡς: σφόδρα. Ἐμπεδοκλεῖ"),
        _seg("1:B23", "—S. V. μακάρων νήσοισιν: τειχός τι τῶν ἐν Ἀργείαι Μυκηνῶν"),
    ]}, work_id="parmenides-fragments")
    # The Suda is cited by its own name, not an author's: no separate title
    # repeats "Suda" (2026-09-27 fifth round; contrast Harpocration above,
    # whose lexicon has a real title distinct from his name).
    assert _cite(result["1:B23"][0][0]) == ("dash", "Suda", "", "s.v. μακάρων νήσοισιν")


def test_rule_e_non_lexicon_bare_dash_is_the_same_place():
    # Real Heraclitus B51 -> B52 (Hippolytus): the Greek after the dash is the
    # fragment, not a headword.
    result = _run({"segments": [
        _seg("1:B51", "HIPPOL. IX 9 (nach B 50)"),
        _seg("1:B52", "— —χρόνος νέος ὑπάρχει γελῶν, τρέχων· πατρὸς ὁ θρόνος."),
    ]})
    (e,) = result["1:B52"][0]
    assert (e["resolution"], e["authorDisplay"], e["locus"]) == ("dash", "Hippolytus", "IX 9")


def test_rule_e_doxographi_page_walks_back_to_aetius():
    # Real Parmenides A39 -> A40 -> A40a -> A41: the "(D. 345)" page cannot
    # belong to the Anonymus Byzantinus of A40, so the dash repeats the
    # Aëtius above it; A41 still does after a DIOG. inside A40a's passage.
    result = _run({"segments": [
        _seg("1:A38", "AËT. II 11, 4 (D. 340) Π."),
        _seg("1:A39", "—II 13, 8 (D. 342) Π. καὶ Ἡράκλειτος"),
        _seg("1:A40", "ANONYM. BYZANT. ed. Treu p. 52, 19 [Isag. in Arat. II 14 p. 318, 15 Maass] καὶ τῶν"),
        _seg("1:A40a", "—II 15, 4 (D. 345) Π. δεύτερον δὲ κρίνει", ("text", "αἰθέρα"),
             "καλεῖ [Β 10,5]. DIOG. VIII 14 (Pythagoras) δεύτερόν τε Φωσφόρον"),
        _seg("1:A41", "—II 20, 8 (D. 349) Π. καὶ Μητρόδωρος"),
    ]}, work_id="parmenides-testimonia")
    for seg, locus in (("1:A40a", "II 15, 4"), ("1:A41", "II 20, 8")):
        (e,) = result[seg][0]
        assert (e["resolution"], e["authorDisplay"], e["locus"]) == ("dash", "Aëtius", locus)


def test_rule_e_passage_source_is_the_antecedent_when_the_head_cannot_fit():
    # Real Empedocles A92 -> A93: the head above is PLATO; the "(D. 406)" page
    # points to the AËT. named inside A92's passage.
    result = _run({"segments": [
        _seg("1:A92", "PLATO Meno p. 76 C Θέλεις οὖν μοι περὶ σχήματος διαλέγεσθαι; "
                      "AËT. I 15, 3 (D. 313) Ἐ. σχῆμα ὑπάρχειν"),
        _seg("1:A93", "—IV 16, 1 (D. 406) Ἐ. τὴν ὄψιν συμβαίνειν"),
        _seg("1:A94", "—IV 17, 2 (D. 407) Ἐ. ταῖς αἰσθήσεσιν"),
    ]}, work_id="empedocles-testimonia")
    assert _cite(result["1:A93"][0][0]) == ("dash", "Aëtius", "Placita", "IV 16, 1")
    assert _cite(result["1:A94"][0][0]) == ("dash", "Aëtius", "Placita", "IV 17, 2")


def test_rule_e_other_author_in_passage_makes_a_plain_dash_uncertain():
    # Real Heraclitus B95 -> B96 shape, synthetic loci: a source by another
    # author inside the passage, and a dash of numbers only, which either
    # could continue: it stays as printed.
    result = _run({"segments": [
        _seg("1:A44", "AËT. I 24, 2 Ἐ. καὶ Ἀναξαγόρας. STOB. I 10, 12 Ἐ. φησιν"),
        _seg("1:A45", "—26, 1 Ἐ. φύσιν εἱμαρμένης"),
    ]}, work_id="empedocles-testimonia")
    assert _verbatim_flags(result["1:A45"][0][0]) == ["dash-unresolved", "dash-antecedent-uncertain"]


def test_rule_e_a_book_numeral_only_one_source_above_fits_decides():
    # Replaces the old pin of Empedocles A45 as undecidable (2026-09-27,
    # item 8): "—I 26, 1" prints a whole place, book, chapter, section, and
    # only the Aëtius head above has such places -- the ARISTOT. in A44's
    # passage prints "Γ 7. 305b 1". Real Democritus A151 -> A152: "— —XII 17"
    # is Aelian's, not the Hippocrates or Aristotle named in A151's text.
    result = _run({"segments": [
        _seg("1:A44", "AËT. I 24, 2 Ἐ. καὶ Ἀναξαγόρας. ARISTOT. de cael. Γ 7. 305b 1 Ἐ. φησιν"),
        _seg("1:A45", "—I 26, 1 Ἐ. φύσιν εἱμαρμένης"),
    ]}, work_id="empedocles-testimonia")
    assert _cite(result["1:A45"][0][0]) == ("dash", "Aëtius", "Placita", "I 26, 1")
    result = _run({"segments": [
        _seg("1:A150", "AEL. H. N. XII 16 λέγει Δ."),
        _seg("1:A151", "— —XII 16 λέγει Δ. πολύγονα.",
             "ὁμοίως. HIPPOCR. de nat. inf. 31 (VII 540 L.) ὅτι δέ. [ARISTOT.] Probl. 10, 14. 892a 38 διὰ τί."
             " ARISTOT. de gen. anim. Β 8. 747a 29 Δ. μὲν οὖν"),
        _seg("1:A152", "— —XII 17 ἐν τοῖς νοτίοις"),
    ]}, work_id="democritus-testimonia")
    assert _cite(result["1:A152"][0][0]) == ("dash", "Aelian", "De Natura Animalium", "XII 17")


def test_rule_e_title_decides_among_the_sources_named_since_the_last_head():
    # Real Gorgias A25 -> A26 (printed "—Phileb. 58A"): CIC. is the last
    # author named, but "Phileb."/"Gorg." are Plato's; A26 here is a
    # synthetic "—Gorg." (the dictionary has listed "Phileb." only since
    # 2026-09-24; see test_item3_plato_titles).
    result = _run({"segments": [
        _seg("1:A25", "PLATO Phaedr. p. 267A CIC. Brut. 12, 47"),
        _seg("1:A26", "—Gorg. 447C"),
        _seg("1:A27", "—Phileb. 58A"),
    ]}, work_id="gorgias-testimonia")
    assert _cite(result["1:A26"][0][0]) == ("dash", "Plato", "Gorgias", "447C")
    assert _cite(result["1:A27"][0][0]) == ("dash", "Plato", "Philebus", "58A")


def test_rule_e_unknown_author_resets_the_chain():
    # An all-caps author the dictionary does not know still names the
    # source: a following dash must not reach past it.
    result = _run({"segments": [
        _seg("1:A1", "DIOG. I 88"),
        _seg("1:A2", "CHRON. PASCH. 317, 5"),  # "ACHILL. Isag." is known since 2026-09-27
        _seg("1:A3", "—IX 1"),
    ]})
    assert _verbatim_flags(result["1:A3"][0][0]) == ["dash-unresolved", "dash-antecedent-unresolved"]


def test_rule_e_dash_with_no_antecedent_is_verbatim():
    result = _run(_spine("—de sensu 5. 443a 23"))
    assert result["1:B1"] == [[{
        "verbatim": "—de sensu 5. 443a 23", "resolution": "verbatim",
        "flags": ["dash-unresolved"]}]]


def test_rule_e_walk_never_crosses_into_another_work():
    _run(_spine("PLUT. Coriol. 22"))
    result = _run(_spine("—de E 8 p. 388 E"))
    assert result["1:B1"][0][0]["resolution"] == "verbatim"


def test_rule_e_memo_excluded_dash_work_now_resolves():
    # Memo §5 left five dash titles out until their columns were read; each
    # follows a head of its author (2026-09-28): Heraclitus B125.
    result = _run(_spine("THEOPHR. Metaphys. 15 p. 7a 10 Usen.", "—de vertig. 9"))
    assert _cite(result["1:B2"][0][0]) == ("dash", "Theophrastus", "De Vertigine", "9")


def test_rule_e_dash_misparse_title_resolves_under_the_last_author():
    # Real gorgias-testimonia A21: "Meno 95C" whose dash was lost.
    result = _run(_spine("PLATO Gorg. 449 A", "Meno 95C", "Ionium fulvis inundat aequor ab antris"))
    (e,) = result["1:B2"][0]
    assert _cite(e) == ("dash", "Plato", "Meno", "95C")
    assert "dash-misparse" in e["flags"]
    assert _verbatim_flags(result["1:B3"][0][0]) == \
        ["dash-misparse", "dash-unresolved", "dash-work-not-in-dictionary"]


def test_rule_e_filled_in_dash_carries_the_same_fields_as_a_direct_entry():
    result = _run(_spine("SIMPL. Phys. 155, 30", "—164, 20"))
    (e,) = result["1:B2"][0]
    assert e == {
        "verbatim": "—164, 20",
        "resolution": "dash",
        "authorDisplay": "Simplicius",
        "work": {"title": "in Aristotelis Physica", "italic": True},
        "locus": "164, 20",
        "flags": ["title-is-commentary", "dash-e5"],
        "dashInherited": True,
    }


def test_rule_e_mid_segment_dash_line_is_a_head():
    # Real Democritus B82: "—*48." opens a second numbered item inside the
    # column, on a context line that continues the run.
    result = _run({"segments": [
        _seg("1:B81", "DEMOKRATES 46."),
        _seg("1:B82", "—47.", ("text", "ἀνοήμονες"), ".", "—*48. εὐδαίμων, ὃς τέχνην καὶ λόγον ἔχει·"),
    ]}, work_id="democritus-fragments")
    runs = result["1:B82"]
    assert [r[0]["locus"] for r in runs] == ["47.", "*48."]


def test_rule_e_dash_with_only_a_period_stays_verbatim():
    # Real Democritus B53a "—.": the number is not printed.
    result = _run({"segments": [
        _seg("1:B53", "DEMOKRATES 19.", ("text", "πολλοὶ λόγον"), "."),
        _seg("1:B53a", "—.", ("text", "πολλοὶ δρῶντες"), "[Stob. II 15, 33]."),
    ]}, work_id="democritus-fragments")
    assert _verbatim_flags(result["1:B53a"][0][0]) == ["dash-unresolved", "dash-no-number"]


# --- Code-review findings on 70b655e (a-d) ---------------------------------

def test_finding_a_numbers_after_a_book_letter_keep_the_book():
    # "—3. 355b 2" after Meteor. B 2. 355a 13 is B 3. 355b 2, never "3. 355b 2";
    # a Greek book letter is a level too (synthetic follow-ons).
    result = _run(_spine("ARISTOTELES Meteor. B 2. 355a 13", "—3. 355b 2",
                         "ARISTOT. de anima Α 2. 404a 25", "— —3. 406b 15"))
    assert _cite(result["1:B2"][0][0]) == ("dash", "Aristotle", "Meteorologica", "B 3. 355b 2")
    assert _cite(result["1:B4"][0][0]) == ("dash", "Aristotle", "De Anima", "Α 3. 406b 15")


def test_finding_b_same_author_other_work_in_passage_is_uncertain(dictionary):
    # Replaces finding b's synthetic pin (the work named in the passage is
    # the antecedent), 2026-09-27: real Zeno A25 -> A26 names Aristotle's
    # Topica inside A25 ("Top. Θ 8. 160b 7"), and A26's "— —Ζ 9. 239b 14"
    # is the Physics of A25's heading (239b is a Physics page). Another work
    # of the same author named in the passage makes a place dash as
    # uncertain as another author does, unless only one fits it.
    _, a25, a26 = _columns(dictionary,
        [("context", "ARISTOT. Phys. Δ 3. 210b 22 ὃ δὲ Ζ. ἠπόρει")],
        [("context", "— —Ζ 9. 239b 9 τέτταρες. ἀπείροις. Top. Θ 8. 160b 7 πολλοὺς γὰρ λόγους")],
        [("context", "— —Ζ 9. 239b 14 δεύτερος δ' ὁ καλούμενος")])
    assert _cite(a25[0]["expanded"][0]) == ("dash", "Aristotle", "Physica", "Ζ 9. 239b 9")
    assert _cite(a25[1]["expanded"][0])[2] == "Topica"
    assert _verbatim_flags(a26[0]["expanded"][0]) == ["dash-unresolved", "dash-antecedent-uncertain"]


def test_finding_c_locus_has_a_firm_end():
    # Real Anaxagoras A108 -> A110: Latin prose after the Doxographi page is
    # not locus. Real Xenophanes A18 -> A19: a second locus after a closed
    # group is not silently folded in -- the head stays as printed.
    result = _run({"segments": [
        _seg("1:A108", "CENSOR. 6, 1 (D. 190;) A. pulmo unde omnia sunt vita."),
        _seg("1:A109", "—6, 2 sunt qui frigidum spiritum abesse contendant"),
        _seg("1:A110", "—6, 3 (D. 191) Empedocli enim aliisque nonnullis per venas sanguis"),
    ]}, work_id="anaxagoras-testimonia")
    (e,) = result["1:A110"][0]
    assert (e["locus"], e["apparatus"]) == ("6, 3", "(D. 191)")
    assert result["1:A109"][0][0]["locus"] == "6, 2"
    result = _run({"segments": [
        _seg("1:A18", "DIOG. IX 22 καὶ ἐκεῖνος μέν"),
        _seg("1:A19", "—IX 18 (oben I 113, 18). II 46 (vgl. I 103, 10) ἀποθανόντι δὲ"),
    ]}, work_id="xenophanes-testimonia")
    assert _verbatim_flags(result["1:A19"][0][0]) == ["dash-unresolved", "dash-locus-unclear"]


def test_finding_d_author_inside_a_title_is_not_a_second_source(dictionary):
    # Real Critias B16: HERMOG. is part of Gregory's title ("on Hermogenes").
    entries = ce._resolve_head(
        dictionary, "GREGOR. CORINTH. Zu HERMOG. Β 445, 7 Rabe", "critias-fragments", "1:B16")
    assert len(entries) == 1
    assert entries[0]["authorDisplay"] == "Gregory of Corinth"
    assert "445, 7" in entries[0]["locus"]


# --- Adjudicated dash heads (John, 2026-09-24) ------------------------------

def test_adjudicated_heads_are_resolved_from_the_table():
    # Real Democritus B175 -> B178: DK's "— —40" omits the chapter; John's
    # reading from the TLG Stobaeus is II 15, 40, and B178 builds on it.
    result = _run({"segments": [
        _seg("1:B175", "STOBAEUS II 9, 4"),
        _seg("1:B176", "— —5"),
        _seg("1:B177", "— —40 Δ—ου.", ("text", "ἄνθρωπος"), "."),
        _seg("1:B178", "— —31, 56 Δ—ου."),
    ]}, work_id="democritus-fragments")
    (e,) = result["1:B177"][0]
    assert _cite(e) == ("dash", "Stobaeus", "Anthologium", "II 15, 40")
    assert "adjudicated" in e["flags"]
    assert result["1:B178"][0][0]["locus"] == "II 31, 56"


def test_adjudicated_clement_keeps_the_staehlin_page_as_apparatus():
    result = _run({"segments": [
        _seg("1:B31", "CLEM. Paed. I 6 (I 93, 15 Stähl.)"),
        _seg("1:B32", "— —94 (I 214, 9 St.) Hipp. Ref. VIII 14 (p. 234, 5 W.). STOB. III 6, 28."),
    ]}, work_id="democritus-fragments")
    first = result["1:B32"][0][0]
    assert (first["authorDisplay"], first["work"]["title"], first["locus"], first["apparatus"]) == \
        ("Clement of Alexandria", "Paedagogus", "II 94", "(I 214, 9 St.)")
    assert result["1:B32"][0][-1]["authorDisplay"] == "Stobaeus"


def test_pending_adjudication_stays_verbatim(monkeypatch):
    monkeypatch.setattr(ce, "_load_adjudications", lambda: {
        "democritus-fragments": {"B177": {"head": "— —40", "reading": None}}})
    result = _run({"segments": [
        _seg("1:B176", "STOBAEUS II 9, 5"),
        _seg("1:B177", "— —40 Δ—ου."),
        _seg("1:B179", "— —57"),
    ]}, work_id="democritus-fragments")
    assert _verbatim_flags(result["1:B177"][0][0]) == ["awaiting-adjudication"]
    # The chapter is unknown until John rules, so a number-only dash after it
    # cannot be filled in either.
    assert result["1:B179"][0][0]["resolution"] == "verbatim"


def test_adjudication_that_no_longer_matches_is_fatal(monkeypatch):
    monkeypatch.setattr(ce, "_load_adjudications", lambda: {
        "democritus-fragments": {"B177": {"head": "— —40", "reading": {
            "author": "CLEM", "work": "Paed.", "locus": "II 15, 40", "note": "x"}}}})
    with pytest.raises(ValueError, match="adjudicat"):
        _run({"segments": [_seg("1:B176", "STOBAEUS II 9, 5"), _seg("1:B177", "— —40")]},
             work_id="democritus-fragments")


def test_locus_keeps_book_and_column_letters(dictionary):
    # Real Heraclitus B6 / B13 / B82 and Anaxagoras A28: the pilot dropped
    # these letters (and with them B6's whole locus).
    cases = {
        "ARISTOTELES Meteor. B 2. 355a 13 [vgl. 68 B 158]": "B 2. 355a 13 [vgl. 68 B 158]",
        "ATHEN. V p. 178 F": "V p. 178 F",
        "PLATO Hipp. maior 289 A": "289 A",
        "ARISTOT. Metaph. Γ 5. 1009 b 25 [nach 28 B 16]": "Γ 5. 1009 b 25 [nach 28 B 16]",
        "PLATO Meno 95C": "95C",
    }
    for head, locus in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert e["locus"] == locus, head


# --- Review round (GPT-6 Sol, 2026-09-24) -----------------------------------

def test_review_1_two_places_after_two_numbered_levels_stay_verbatim():
    # Synthetic, from the review: after "VI 151, 2", "152. 153" may be two
    # sections replacing "151, 2" or two places replacing "2" -- the print
    # does not say which; never the mixed-level "VI 151, 152. 153".
    result = _run({"segments": [
        _seg("1:B60", "POLL. VI 151, 2"),
        _seg("1:B61", "— —152. 153 τινὲς μὲν οὖν"),
    ]}, work_id="critias-fragments")
    assert _verbatim_flags(result["1:B61"][0][0]) == ["dash-unresolved", "dash-level-uncertain"]


def test_review_1_real_democritus_b284_two_places_after_chapter_and_section():
    # Real Democritus B283 -> B284: "24. 25" after IV 33, 23 has the same two
    # readings (sections 24 and 25 of chapter 33, or chapter 24 section 25).
    result = _run({"segments": [
        _seg("1:B282", "STOB. IV 31, 120"),
        _seg("1:B283", "—33, 23"),
        _seg("1:B284", "— —24. 25"),
    ]}, work_id="democritus-fragments")
    assert result["1:B283"][0][0]["locus"] == "IV 33, 23"
    assert "dash-level-uncertain" in _verbatim_flags(result["1:B284"][0][0])


def test_review_1_two_places_resolve_where_only_one_level_can_take_them():
    # Real Critias B59 -> B61: after VI 38 the section is the only number, so
    # "152. 153" can only be two sections. Real Democritus B240: the dash
    # prints its own chapter, which fixes the level of "63. 83a".
    result = _run({"segments": [
        _seg("1:B59", "POLL. VI 31"),
        _seg("1:B60", "— —38 Κ. γὰρ ὅμως"),
        _seg("1:B61", "— —152. 153 τινὲς μὲν οὖν"),
    ]}, work_id="critias-fragments")
    assert result["1:B61"][0][0]["locus"] == "VI 152. 153"
    result = _run({"segments": [
        _seg("1:B239", "STOB. III 28, 13"),
        _seg("1:B240", "—29, 63. 83a (III p. LXXIX H.)"),
    ]}, work_id="democritus-fragments")
    assert result["1:B240"][0][0]["locus"] == "III 29, 63. 83a (III p. LXXIX H.)"


def test_review_2_doxographi_page_selects_only_the_author_it_belongs_to():
    # Synthetic, from the review: page 565 of Diels's Doxographi is printed
    # with Hippolytus's own heads, never with Theophrastus's, so the dash
    # repeats Hippolytus although Theophrastus was named last.
    result = _run({"segments": [
        _seg("1:A1", "HIPPOL. Refut. I 13 (D. 565)"),
        _seg("1:A2", "THEOPHR. de sensu 1ff. (D. 499)"),
        _seg("1:A3", "—I 14 (D. 565)"),
    ]}, work_id="democritus-testimonia")
    (e,) = result["1:A3"][0]
    assert (e["resolution"], e["authorDisplay"], e["locus"]) == ("dash", "Hippolytus", "I 14")


def test_review_2_doxographi_page_no_head_shows_the_owner_of_stays_verbatim():
    # Page 600 falls between Epiphanius (590) and Pseudo-Galen (601) in the
    # heads DK prints with a page: nothing shows whose page it is.
    result = _run({"segments": [
        _seg("1:A1", "HIPPOL. Refut. I 13 (D. 565)"),
        _seg("1:A3", "—I 14 (D. 600)"),
    ]}, work_id="democritus-testimonia")
    assert _verbatim_flags(result["1:A3"][0][0]) == ["dash-unresolved", "doxographi-owner-unknown"]


def test_review_2_page_table_matches_the_heads_in_the_spines():
    # The committed page table is derived from the spines; skip without them.
    spines = ROOT / "build" / "dk-spines"
    if not spines.is_dir():
        pytest.skip("build/dk-spines/ not present (gitignored build data)")
    sys.path.insert(0, str(ROOT / "pipeline" / "tools"))
    import build_doxographi_pages as b
    committed = json.loads((ROOT / "sources" / "dk-citations" / "doxographi-pages.json")
                           .read_text(encoding="utf-8"))
    assert b.build(spines)["pages"] == committed["pages"]


def test_review_3_adjudication_must_match_the_whole_printed_head(monkeypatch):
    # "— —40" ruled; the text now prints "— —400": the ruling no longer
    # matches its line, which is fatal (never apply it by prefix).
    monkeypatch.setattr(ce, "_load_adjudications", lambda: {
        "democritus-fragments": {"B177": {"head": "— —40", "reading": {
            "author": "STOB", "work": "DEFAULT", "locus": "II 15, 40"}, "note": "x"}}})
    with pytest.raises(ValueError, match="adjudicat"):
        _run({"segments": [_seg("1:B176", "STOBAEUS II 9, 5"), _seg("1:B177", "— —400")]},
             work_id="democritus-fragments")


def test_review_4_book_the_title_carries_is_not_printed_twice():
    # Real Heraclitus B78 -> B80: the dictionary's "c. Cels. VI" is Contra
    # Celsum (lib. VI), so "— —VI 42" is that work, locus 42 -- the same
    # shape as the direct head above it.
    result = _run({"segments": [
        _seg("1:B78", "ORIG. c. Cels. VI 12 (II 82, 23 Koetschau)", ("text", "ἦθος γὰρ")),
        _seg("1:B79", ("text", "— —γυνὴ σοφὴ εἶπεν"), "."),
        _seg("1:B80", "— —VI 42 (II 111, 11 Koetschau)", ("text", "γινώσκειν δὲ δεῖ"), "."),
    ]})
    assert _cite(result["1:B78"][0][0]) == \
        ("direct", "Origen", "Contra Celsum (lib. VI)", "12 (II 82, 23 Koetschau)")
    assert _cite(result["1:B80"][0][0]) == \
        ("dash", "Origen", "Contra Celsum (lib. VI)", "42 (II 111, 11 Koetschau)")


def test_review_4_other_book_than_the_title_carries_stays_verbatim():
    # Synthetic: a dash naming book VIII under Contra Celsum (lib. VI).
    result = _run({"segments": [
        _seg("1:B78", "ORIG. c. Cels. VI 12 (II 82, 23 Koetschau)"),
        _seg("1:B80", "— —VIII 42"),
    ]})
    assert _verbatim_flags(result["1:B80"][0][0]) == ["dash-unresolved", "dash-book-not-in-title"]


def test_review_5_locus_ends_before_an_all_caps_heading(dictionary):
    # Real Democritus A88: DK's heading after Lucretius's line number is not
    # locus. An edition siglum followed by numbers is (real Empedocles A34).
    (e,) = ce._resolve_head(dictionary, "LUCR. V 621ff. DEMOCRITI DE SOLE", "w", "s")
    assert e["locus"] == "V 621ff."
    (e,) = ce._resolve_head(
        dictionary, "GALEN. in Hipp. nat. hom. XV 32 K. CMG V 9, 1 p. 19, 7", "w", "s")
    assert e["locus"] == "XV 32 K. CMG V 9, 1 p. 19, 7"
    # Column letters set together stay (real Empedocles B9).
    (e,) = ce._resolve_head(dictionary, "PLUT. adv. Col. 11 p. 1113 AB", "w", "s")
    assert e["locus"] == "11 p. 1113 AB"


# --- Independent-reviewer round: defect 1 -----------------------------------
# The Stephanus/Bekker column-letter exemption (a 2-3 letter A-F cluster,
# "1113 AB") must count only when it directly follows a page/number token
# already in the locus -- not merely when *some* digit appeared earlier in
# the locus. test_review_5 above shows the real Democritus A88 head is
# already fine because "DEMOCRITI" (9 letters, not an A-F{2,3} shape) trips
# the ordinary heading break first. Drop DEMOCRITI and the bug surfaces: "DE"
# (D, E both A-F) is itself shaped like a column cluster, so the old rule let
# it through on the strength of the "621ff." digits earlier in the locus,
# even though "DE" does not directly follow a page/number ("621ff." ends in
# "ff.", which explicitly does not count -- see _PAGE_NUMBER).


def test_defect1_column_letters_require_a_directly_preceding_page_number(dictionary):
    (e,) = ce._resolve_head(dictionary, "LUCR. V 621ff. DE SOLE", "w", "s")
    assert e["locus"] == "V 621ff."


def test_defect1_column_letters_still_count_right_after_a_page_number(dictionary):
    (e,) = ce._resolve_head(dictionary, "PLUT. de Pyth. or. 1113 AB", "w", "s")
    assert e["locus"] == "1113 AB"


# --- John's rulings of 2026-09-24 (TLG check) --------------------------------

def test_ruling_a_stobaeus_chapters_from_the_tlg_and_the_dashes_after_them():
    result = _run({"segments": [
        _seg("1:B224", "STOB. III 10, 68"),
        _seg("1:B225", "—12, 13"),
        _seg("1:B226", "— —47"),
        _seg("1:B227", "—16, 17"),
        _seg("1:B244", "STOB. III 31, 7"),
        _seg("1:B245", "— —53"),
        _seg("1:B246", "—40, 6"),
        _seg("1:B283", "STOB. IV 33, 23"),
        _seg("1:B285", "— —65"),
        _seg("1:B285a", "— —66"),  # synthetic: a dash after a ruling builds on it
        _seg("1:B286", "—39, 17"),
    ]}, work_id="democritus-fragments")
    got = {s: (result[s][0][0]["locus"], "adjudicated" in result[s][0][0]["flags"])
           for s in ("1:B225", "1:B226", "1:B227", "1:B245", "1:B246", "1:B285",
                     "1:B285a", "1:B286")}
    assert got == {
        "1:B225": ("III 12, 13", False), "1:B226": ("III 13, 47", True),
        "1:B227": ("III 16, 17", False), "1:B245": ("III 38, 53", True),
        "1:B246": ("III 40, 6", False), "1:B285": ("IV 34, 65", True),
        "1:B285a": ("IV 34, 66", False), "1:B286": ("IV 39, 17", False),
    }


def test_ruling_b_misprint_is_corrected_with_a_note():
    # Real Antiphon B106 -> B108 (Pollux): DK prints "V 441"; the TLG has the
    # gloss at V 141. The dash after it builds on the corrected reading.
    result = _run({"segments": [
        _seg("1:B106", "POLL. IV 167"),
        _seg("1:B107", "—V 441 καὶ τὸ ὄνομα ἀλήθεια"),
        _seg("1:B108", "—VI 163 Ἀ."),
    ]}, work_id="antiphon-sophist-fragments")
    (e,) = result["1:B107"][0]
    assert _cite(e) == ("dash", "Julius Pollux", "Onomasticon", "V 141")
    assert e["note"] == "DK prints “V 441”."
    assert "corrected" in e["flags"]
    assert result["1:B108"][0][0]["locus"] == "VI 163"


def test_ruling_b_correction_stands_when_the_chain_above_is_unresolved():
    # Real Antiphon: the dashes before B107 stay as printed (the chain was
    # lost at B100), yet John's reading of B107 names author and work.
    result = _run({"segments": [
        _seg("1:B106", "—IV 167"),
        _seg("1:B107", "—V 441 καὶ τὸ ὄνομα ἀλήθεια"),
    ]}, work_id="antiphon-sophist-fragments")
    assert result["1:B106"][0][0]["resolution"] == "verbatim"
    assert result["1:B107"][0][0]["locus"] == "V 141"


def test_ruling_b_aetius_misprint_keeps_the_doxographi_page():
    result = _run({"segments": [
        _seg("1:A17a", "AËT. II 13, 1 (D. 341) Θ. ὑγρὰ δέ"),
        _seg("1:A17b", "—II 27, 5 (D. 358) Θ. δεύτερος εἶπεν"),
    ]}, work_id="thales-testimonia")
    (e,) = result["1:A17b"][0]
    assert (e["authorDisplay"], e["locus"], e["apparatus"], e["note"]) == \
        ("Aëtius", "II 28, 5", "(D. 358)", "DK prints “II 27, 5”.")


def test_ruling_b_correction_whose_printed_form_is_not_in_its_head_is_fatal(monkeypatch):
    monkeypatch.setattr(ce, "_load_adjudications", lambda: {
        "antiphon-sophist-fragments": {"B107": {
            "head": "—V 441", "type": "correction", "printed": "V 442",
            "reading": {"author": "POLL", "work": "DEFAULT", "locus": "V 141"},
            "readerNote": "DK prints “V 442”.", "note": "x"}}})
    with pytest.raises(ValueError, match="adjudicat"):
        _run({"segments": [_seg("1:B106", "POLL. IV 167"), _seg("1:B107", "—V 441")]},
             work_id="antiphon-sophist-fragments")


def test_ruling_c_plutarch_b99_awaits_the_print_check():
    result = _run({"segments": [
        _seg("1:B97", "PLUT. de Is. 76 p. 382 A"),
        _seg("1:B99", "—aqu. et ign. comp. 7 p. 957 A; vgl. de fort. 3. p. 98 C",
             ("text", "εἰ μὴ νέφος ἦν")),
    ]})
    assert _verbatim_flags(result["1:B99"][0][0]) == ["awaiting-print-check"]


def test_ruling_d_clement_stromateis_keeps_dks_section_numbers():
    # Real Heraclitus B21 -> B26: the TLG's Stromateis numbers these sections
    # one or two apart; John keeps DK's own numbers, so nothing is corrected.
    result = _run({"segments": [
        _seg("1:B21", "CLEM. Strom. III 21 (II 205, 7)"),
        _seg("1:B22", "— —IV 4 (II 249, 23)"),
        _seg("1:B25", "— — —50 (II 271, 3)"),
        _seg("1:B26", "— — —143 (II 310, 21)"),
    ]})
    for seg, locus in (("1:B25", "IV 50 (II 271, 3)"), ("1:B26", "IV 143 (II 310, 21)")):
        (e,) = result[seg][0]
        assert (e["authorDisplay"], e["locus"]) == ("Clement of Alexandria", locus)
        assert "note" not in e and "corrected" not in e["flags"]


# --- Lexicon dashes placed by TLG lookup (John, 2026-09-27, option 3) --------

def _lexicon_cites(result: dict, *segs: str) -> dict:
    return {s: (_cite(result[s][0][0]), "adjudicated" in result[s][0][0]["flags"]) for s in segs}


def test_lexicon_dash_after_a_head_naming_two_lexica_is_placed_from_the_tlg():
    # Real Antiphon B19 -> B21 and B68 -> B71: the run above names two
    # lexica (Harpocration, then Bekker's Anecdota or the Etymologicum
    # Genuinum mid-passage), so rule E cannot say which one the dash repeats.
    # The TLG Harpocration has each headword with DK's gloss.
    h = ("dash", "Harpocration", "Lexicon in Decem Oratores")
    result = _run({"segments": [
        _seg("1:B19", "HARPOCR.", ("text", "ἀνήκει"), ": παρ' Ἀ—τι",
             "α ἀντὶ τοῦ ἁπλοῦ ἥκει. AN. BEKK. VI 403, 5 Ἀ. μὲν ἀντὶ τοῦ καθήκει."),
        _seg("1:B20", "—", ("text", "ἐπαλλάξεις"), ": ἀντὶ τοῦ συναλλαγὰς Ἀ."),
        _seg("1:B21", "—", ("text", "ὀριγνηθῆναι"), ": ἀντὶ τοῦ ἐπιθυμῆσαι Ἀ."),
        _seg("1:B67", "HARPOCR.", ("text", "ἀθεώρητος"), ": ἀντὶ τοῦ ἀθέατος."),
        _seg("1:B68", "—", ("text", "αὐλιζόμενοι"), ": ἀντὶ τοῦ κοιμώμενοι Α."),
        _seg("1:B69", "—", "βαλβίς· Ἀ. Περὶ ὁμονοίας", "· ἡ ἀρχή. ETYM. GEN. βαλβίς: ... καὶ",
             ("text", "βαλβῖσιν"), "ἀντὶ τοῦ ταῖς ἀρχαῖς."),
        _seg("1:B70", "—", ("text", "εὐηνιώτατα"), "· Ἀ. ἐν"),
        _seg("1:B71", "—", "φηλώματα: Ἀ. ἐν τῶι Περὶ ὁμονοίας", "ἐξαπάτας."),
    ]}, work_id="antiphon-sophist-fragments")
    assert _lexicon_cites(result, "1:B20", "1:B21", "1:B70", "1:B71") == {
        "1:B20": (h + ("s.v. ἐπαλλάξεις",), True),
        "1:B21": (h + ("s.v. ὀριγνηθῆναι",), True),
        "1:B70": (h + ("s.v. εὐηνιώτατα",), True),
        "1:B71": (h + ("s.v. φηλώματα",), True),
    }
    # B69: John's ruling of 2026-09-27, DK's printed headword (Harpocration's
    # entry is headed Βαλβῖσιν); it replaced the pending print check.
    assert _lexicon_cites(result, "1:B69") == {"1:B69": (h + ("s.v. βαλβίς",), True)}


def test_ruling_hesychius_b132_reads_lattes_headword():
    # Real Democritus B131 -> B132: John, 2026-09-27, Latte's headword
    # ἀσκαληνές (TLG Hesychius α 7691, the gloss ἰσόπλευρον, παρὰ
    # Δημοκρίτῳ), not DK's ἀσκαληρές; it replaced the pending print check.
    result = _run({"segments": [
        _seg("1:B131", "HESYCH.", ("text", "ἀπάτητον"), ": τὸ ἀνωμάλως συγκείμενον παρὰ Δ—ωι."),
        _seg("1:B132", "—", ("text", "ἀσκαληρές"), ": ἰσόπλευρον παρὰ Δ—ωι."),
    ]}, work_id="democritus-fragments")
    assert _lexicon_cites(result, "1:B132") == {
        "1:B132": (("dash", "Hesychius", "Lexicon", "s.v. ἀσκαληνές"), True)}


def test_lexicon_dash_after_the_etymologicum_and_bekker_is_placed_by_elimination():
    # Real Democritus B122 -> B123: the TLG Synagoge (Bekker's Lex. VI) has
    # neither headword; the Genuinum's descendants carry both with
    # Democritus' name.
    e = ("dash", "Etymologicum", "Etymologicum Genuinum")
    result = _run({"segments": [
        _seg("1:B122", "ETYM. GEN. ἀλαπάξαι: ἐκπορθῆσαι.", ("text", "λαπάθους"),
             "καλεῖ. ANECD. BEKK. LEX. VI 374, 14 ἀμέλει Δ."),
        _seg("1:B122a", "—", ("text", "γυνή"), ": ... ἤ, ὡς Δ.,", ("text", "γονή")),
        _seg("1:B123", "—", ("text", "δείκελον"), ": παρὰ δὲ Δημοκρίτωι."),
    ]}, work_id="democritus-fragments")
    assert _lexicon_cites(result, "1:B122a", "1:B123") == {
        "1:B122a": (e + ("s.v. γυνή",), True),
        "1:B123": (e + ("s.v. δείκελον",), True),
    }


def test_lexicon_dash_before_an_ano_teleia_is_placed_from_the_tlg():
    # Real Antiphon B23 and B46: DK prints the Greek ano teleia after the
    # headword; the TLG Harpocration has both entries.
    result = _run({"segments": [
        _seg("1:B22", "HARPOCR. [vgl. PHOT. A Reitzenst. 37, 18]", "ἀειεστώ· Ἀ."),
        _seg("1:B23", "—", "διάστασις· Ἀ. Ἀληθείας β.", "ἀντὶ τοῦ διακοσμήσεως τῶν ὅλων."),
        _seg("1:B45", "HARPOCRAT.", "Σκιάποδες: Ἀ. ἐν τῶι Περὶ ὁμονοίας"),
        _seg("1:B46", "—", "Μακροκέφαλοι· Ἀ. ἐν τῶι Περὶ ὁμονοίας", ". ἔθνος."),
    ]}, work_id="antiphon-sophist-fragments")
    assert [_cite(result[s][0][0])[3] for s in ("1:B23", "1:B46")] == \
        ["s.v. διάστασις", "s.v. Μακροκέφαλοι"]


def test_pollux_run_continues_past_a_dagegen_comparison():
    # Real Antiphon B99 -> B105 (item 13, 2026-09-27; replaces the pin of
    # B100-B104 as a lost chain): "Dagegen HARPOCR." inside B99 compares
    # Harpocration's gloss, it is not the next source, so B100-B104 are
    # Pollux; B105 keeps John's TLG reading, the same IV 9.
    result = _run({"segments": [
        _seg("1:B97", "POLL. II 109"),
        _seg("1:B99", "— —Ἀ. δὲ", ("text", "ἀπαρτιλογία"), "ὥσπερ. Dagegen HARPOCR. ἀπαρτιλογία."),
        _seg("1:B100", "—II 123 κακολόγος"),
        _seg("1:B104", "—IV 9 ἀνεπιστημοσύνη."),
        _seg("1:B105", "— —", ("text", "δοκησίσοφος"), ", ὡς Ἀ. ἔφη."),
    ]}, work_id="antiphon-sophist-fragments")
    p = ("dash", "Julius Pollux", "Onomasticon")
    assert _cite(result["1:B100"][0][0]) == p + ("II 123",)
    assert _cite(result["1:B104"][0][0]) == p + ("IV 9",)
    assert _lexicon_cites(result, "1:B105") == {"1:B105": (p + ("IV 9",), True)}
    chain = ce._Chain()
    ce._scan_passage(ce._load_dictionary(), chain, "ὥσπερ. Dagegen HARPOCR. ἀπαρτιλογία.")
    assert chain.sources == []


def test_lexicon_ruling_naming_neither_source_of_the_run_is_fatal(monkeypatch):
    monkeypatch.setattr(ce, "_load_adjudications", lambda: {
        "antiphon-sophist-fragments": {"B20": {"head": "—", "reading": {
            "author": "HESYCH", "work": "DEFAULT", "locus": "s.v. ἐπαλλάξεις"}, "note": "x"}}})
    with pytest.raises(ValueError, match="adjudicat"):
        _run({"segments": [
            _seg("1:B19", "HARPOCR.", ("text", "ἀνήκει"), "α ἥκει. AN. BEKK. VI 403, 5 Ἀ."),
            _seg("1:B20", "—", ("text", "ἐπαλλάξεις"), ": ἀντὶ τοῦ Ἀ."),
        ]}, work_id="antiphon-sophist-fragments")


# --- Dictionary / parsing defects (TLG check + content review, 2026-09-24) --
# Every head below is printed in the 39 DK spines unless marked synthetic.


def _no_author(entry: dict) -> tuple:
    assert "authorDisplay" not in entry, entry
    return (entry["resolution"], entry["work"]["title"], entry["locus"])


def test_item1_bekker_anecdota_has_no_author_and_prints_the_volume(dictionary):
    # John's ruling, 2026-09-24: "AN. BEKK. Lex. VI p. 418, 6" is *Anecdota
    # Graeca* I, Lex. VI p. 418, 6 -- no author; Bekker's vol. I (1814) holds
    # the Lexica Segueriana, pp. 1-476.
    cases = {
        "AN. BEKK. Lex. VI p. 470, 25": "I, Lex. VI p. 470, 25",       # Antiphon B16
        "ANECD. BEKK. Antiattic. 114, 28": "I, Antiattic. 114, 28",    # Antiphon B82
        "ANTIATT. Bekk. An. 78, 20": "I, Antiatt. 78, 20",             # Antiphon B72
        "ANTIATT. BEKK. p. 94, 1": "I, Antiatt. p. 94, 1",             # Critias B13
        "ANECD. Bekk. I 337, 13": "I 337, 13",                         # Empedocles B47 prints the volume
    }
    for head, locus in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _no_author(e) == ("direct", "Anecdota Graeca", locus), head
        assert e["work"]["italic"] is True


def test_item1_bekker_anecdota_dashes_keep_the_volume():
    # Real Antiphon B16/B17 and B82-B86.
    result = _run({"segments": [
        _seg("1:B16", "AN. BEKK. Lex. VI p. 470, 25"),
        _seg("1:B17", "— —p. 472, 14"),
        _seg("1:B82", "ANECD. BEKK. Antiattic. 114, 28"),
        _seg("1:B83", "—Lex. VI p. 345, 26"),
        _seg("1:B84", "—p. 367, 31"),
        _seg("1:B85", "—p. 418, 6"),
    ]}, work_id="antiphon-sophist-fragments")
    got = {s: _no_author(result[s][0][0]) for s in ("1:B17", "1:B83", "1:B84", "1:B85")}
    assert got == {
        "1:B17": ("dash", "Anecdota Graeca", "I, Lex. VI p. 472, 14"),
        "1:B83": ("dash", "Anecdota Graeca", "I, Lex. VI p. 345, 26"),
        "1:B84": ("dash", "Anecdota Graeca", "I, Lex. VI p. 367, 31"),
        "1:B85": ("dash", "Anecdota Graeca", "I, Lex. VI p. 418, 6"),
    }


def test_item1_bekker_anecdota_page_outside_a_known_part_stays_verbatim(dictionary):
    # Sol review finding 2b: Bekker's vols. II (1816) and III (1821) start
    # again at p. 1, so a page alone never names the volume. Only a part
    # known to lie in vol. I -- the Antiatticista (pp. 75-116), Lex. VI, the
    # Synagoge (pp. 319-476) -- with its page inside that part's pages gives
    # vol. I; anything else stays as printed, flagged. All synthetic.
    for head in ("AN. BEKK. Lex. VI p. 501, 3",      # past the Synagoge
                 "AN. BEKK. Lex. VI p. 200, 3",      # before it
                 "ANECD. BEKK. p. 123, 4",           # no part named
                 "ANECD. Bekk. 337, 13",             # no part, no volume
                 "AN. BEKK. Lex. V p. 200, 1",       # a part DK never cites
                 "ANTIATT. BEKK. p. 130, 1",         # past the Antiatticista
                 "ANECD. BEKK. Antiattic. 60, 2"):   # before it
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert e["resolution"] == "verbatim", head
        assert "edition-volume-unknown" in e["flags"], head
    result = _run({"segments": [
        _seg("1:B16", "AN. BEKK. Lex. VI p. 470, 25"),
        _seg("1:B17", "—p. 520, 1"),  # synthetic: the dash leaves the Synagoge
    ]}, work_id="antiphon-sophist-fragments")
    assert "edition-volume-unknown" in _verbatim_flags(result["1:B17"][0][0])


def test_item1_bekker_anecdota_printed_volume_wins(dictionary):
    # Sol review finding 2a: a volume numeral DK prints in the head is the
    # volume -- never overruled by the page, never printed twice. Real
    # Empedocles B47 ("I 337, 13"); the others synthetic.
    cases = {
        "ANECD. Bekk. I 337, 13": "I 337, 13",
        "ANECD. Bekk. II p. 337, 13": "II p. 337, 13",
        "ANECD. Bekk. II 337, 13": "II 337, 13",
        "ANECD. BEKK. III p. 1450, 2": "III p. 1450, 2",
    }
    for head, locus in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _no_author(e) == ("direct", "Anecdota Graeca", locus), head
    result = _run({"segments": [
        _seg("1:B1", "ANECD. Bekk. II p. 337, 13"),
        _seg("1:B2", "— —15"),  # synthetic dash on a printed volume
    ]}, work_id="w")
    assert _no_author(result["1:B2"][0][0]) == ("dash", "Anecdota Graeca", "II p. 337, 15")


def test_item2_herod_with_book_and_chapter_is_herodotus():
    # Real Pythagoras 1-2 and Thales A6: book numeral + chapter = Herodotus.
    result = _run({"segments": [
        _seg("1:1", "HEROD. II 123 ἄλλοι δὲ φασι τοῦτον τὸν νόμον"),
        _seg("1:2", "—IV 95 καθὼς δὲ σὺ γινώσκεις"),
    ]}, work_id="pythagoras-testimonia")
    (e1,) = result["1:1"][0]
    (e2,) = result["1:2"][0]
    assert _cite(e1) == ("direct", "Herodotus", "Historiae", "II 123")
    assert _cite(e2) == ("dash", "Herodotus", "Historiae", "IV 95")
    assert "ambiguous-abbrev" not in e1["flags"] + e2["flags"]


def test_herod_readings_are_marked_inferred_direct_and_dash():
    # Sol review finding 3: "HEROD." + book + chapter is read as Herodotus
    # by a rule of thumb (Herodian the historian is cited the same way), so
    # every such reading -- the head and each dash built on it -- carries
    # "author-inferred" for the TLG check. Real Pythagoras 1-2, Thales A4-A6.
    result = _run({"segments": [
        _seg("1:1", "HEROD. II 123 ἄλλοι δὲ φασι τοῦτον τὸν νόμον"),
        _seg("1:2", "—IV 95 καθὼς δὲ σὺ γινώσκεις"),
        _seg("1:3", "— —96 ὡς δὲ"),  # synthetic: a dash on the dash
        _seg("1:A4", "HERODOT. I 170 ὠφέλιμος δὲ καὶ"),
        _seg("1:A5", "—I 74 ὁμονοοῦσι δέ σφι"),
    ]}, work_id="pythagoras-testimonia")
    for s in ("1:1", "1:2", "1:3"):
        (e,) = result[s][0]
        assert e["authorDisplay"] == "Herodotus", s
        assert "author-inferred" in e["flags"], s
    for s in ("1:A4", "1:A5"):  # HERODOT. is Herodotus by name
        assert "author-inferred" not in result[s][0][0]["flags"], s


def test_item2_herod_before_a_herodian_title_is_herodian():
    # Real Critias B41: the Greek title after the head is Herodian's
    # Περὶ μονήρους λέξεως.
    result = _run({"segments": [
        _seg("1:B41", "HEROD. π. μον. λέξ. p. 40, 14 τὸ μὲν παρὰ Νικάνδρωι ἐπὶ"),
    ]}, work_id="critias-fragments")
    (e,) = result["1:B41"][0]
    assert (e["resolution"], e["authorDisplay"]) == ("direct", "Herodian (grammarian)")


def _app(entry: dict) -> tuple:
    return _cite(entry) + (entry.get("apparatus"),)


def test_herodian_greek_title_is_the_work_and_what_follows_is_the_locus():
    # Grok content review item 6: the head used to stop at the Greek title
    # ("π." is lowercase Greek), so every Herodian head rendered an empty
    # locus. The title is now part of the head: the work is the title, the
    # locus whatever DK prints after it; a "bei <author>" note (the text
    # that preserves Herodian) is apparatus, as printed. Every Herodian head
    # in the 39 works; the last one synthetic.
    #
    # House convention (John's ruling (b), 2026-09-24): work titles render in
    # Latin, so Περὶ μονήρους λέξεως / Περὶ διχρόνων -> *De Dictione
    # Singulari* / *De Dichronis* (the TLG gives neither a Latin title; "De
    # Prosodia Catholica" and "Schematismi Homerici" already have one and are
    # unaffected).
    result = _run({"segments": [
        _seg("1:X10", "HERODIAN π. διχρ. p. 296, 6 [Cr. An. Ox. III]"),                # Xenophanes B10
        _seg("1:X36", "HERODIAN. π. διχρ. 296, 9"),                                    # B36
        _seg("1:X37", "HERODIAN. π. μον. λέξ. 30, 30"),                                # B37
        _seg("1:X38", "HERODIAN. π. μον. λέξ. p. 41, 5"),                              # B38
        _seg("1:X42", "HERODIAN. π. μον. λέξεως 7, 11 καὶ πρὸς Ἐμπεδοκλεῖ ἐν βίῳ Φυσικῶν·"),  # B42
        _seg("1:C41", "HEROD. π. μον. λέξ. p. 40, 14 τὸ μὲν παρὰ Νικάνδρωι ἐπὶ"),           # Critias B41
        _seg("1:D127", "HERODIAN. π. καθολ. προσ. bei Eustath. zu ξ 428 p. 1766 [II 445, 9 L.] καὶ Δ.",
             ("text", "γελῶντες ἄνθρωποι χαίρουσι"), "."),                              # Democritus B127
        _seg("1:D128", "—π. καθολ. προσ. bei Theogn. p. 79 [I 355, 19 L.] εἰς ἣν θηλυκόν"),  # B128
        _seg("1:E51", "HERODIAN. schematismi Hom. cod. Darmstadini in Sturzii Et. Gud. p. 745 "
                      "[ad Et. M. p. 111, 10] ἀκίχητα· οἱ δὲ κρυπτά"),                 # Empedocles B51
        _seg("1:S1", "HERODIAN. π. μον. λέξ. τὸ δὲ"),                                  # synthetic: no locus
    ]}, work_id="w")
    h = ("Herodian (grammarian)",)
    got = {s: _app(result[s][0][0])[1:] for s in result}
    assert got == {
        "1:X10": h + ("De Dichronis", "p. 296, 6 [Cr. An. Ox. III]", None),
        "1:X36": h + ("De Dichronis", "296, 9", None),
        "1:X37": h + ("De Dictione Singulari", "30, 30", None),
        "1:X38": h + ("De Dictione Singulari", "p. 41, 5", None),
        "1:X42": h + ("De Dictione Singulari", "7, 11", None),
        "1:C41": h + ("De Dictione Singulari", "p. 40, 14", None),
        "1:D127": h + ("De Prosodia Catholica", "", "bei Eustath. zu ξ 428 p. 1766 [II 445, 9 L.]"),
        "1:D128": h + ("De Prosodia Catholica", "", "bei Theogn. p. 79 [I 355, 19 L.]"),
        "1:E51": h + ("Schematismi Homerici",
                      "cod. Darmstadini in Sturzii Et. Gud. p. 745 [ad Et. M. p. 111, 10]", None),
        "1:S1": h + ("De Dictione Singulari", "", None),
    }
    assert result["1:D128"][0][0]["resolution"] == "dash"
    assert result["1:C41"][0][0]["verbatim"] == "HEROD. π. μον. λέξ. p. 40, 14"


def test_item2_herod_without_evidence_stays_verbatim(dictionary):
    # Synthetic: neither a book + chapter nor a Herodian title follows.
    (e,) = ce._resolve_head(dictionary, "HEROD. fr. 3", "w", "s")
    assert _verbatim_flags(e) == ["ambiguous-abbrev"]


def test_item2_herod_in_a_passage_is_herodotus():
    # Real Anaxagoras A91 "Dagegen HEROD. II 22": the chain learns Herodotus.
    chain = ce._Chain()
    # (Anaxagoras A91 prints "Dagegen" before it, a comparison since
    # 2026-09-27: test_pollux_run_continues_past_a_dagegen_comparison.)
    ce._scan_passage(ce._load_dictionary(), chain, "tradunt. HEROD. II 22 ἡ γὰρ τετάρτη")
    assert (chain.sources[-1].author, chain.sources[-1].locus) == ("HERODOT", "II 22")


def test_item3_plutarch_titles():
    result = _run({"segments": [
        _seg("1:B85", "PLUT. Coriol. 22"),
        _seg("1:B88", "—cons. ad Apoll. 10 p. 106 E"),
        _seg("1:B97", "—an seni resp. 7 p. 787C"),
        _seg("1:B98", "—fac. lun. 28 p. 943 E"),
        _seg("1:B100", "—Qu. Plat. 8, 4 p. 1007 D ..."),
        _seg("1:B153", "—Reip. ger. praec. 28 p. 821 A"),
        _seg("1:B159", "—fragm. de libid. et aegr. 2"),
        _seg("1:B23", "—de glor. Ath. 5 p. 348c"),
    ]})
    got = {s: _cite(result[s][0][0])[2:] for s in
           ("1:B88", "1:B97", "1:B98", "1:B100", "1:B153", "1:B159", "1:B23")}
    assert got == {
        "1:B88": ("Consolatio ad Apollonium", "10 p. 106 E"),
        "1:B97": ("An Seni Respublica Gerenda Sit", "7 p. 787C"),
        "1:B98": ("De Facie in Orbe Lunae", "28 p. 943 E"),
        "1:B100": ("Quaestiones Platonicae", "8, 4 p. 1007 D"),
        "1:B153": ("Praecepta Gerendae Reipublicae", "28 p. 821 A"),
        "1:B159": ("De Libidine et Aegritudine", "2"),
        "1:B23": ("De Gloria Atheniensium", "5 p. 348c"),
    }
    assert all(result[s][0][0]["authorDisplay"] == "Plutarch" for s in got)


def test_item3_plutarch_aqua_an_ignis_has_a_title(dictionary):
    # (Heraclitus B99 itself still awaits John's print check: see
    # test_ruling_c_plutarch_b99_awaits_the_print_check.)
    (e,) = ce._resolve_head(dictionary, "PLUT. aqu. et ign. comp. 7 p. 957 A", "w", "s")
    assert _cite(e) == ("direct", "Plutarch", "Aquane an Ignis Sit Utilior", "7 p. 957 A")


def test_item3_plato_titles():
    result = _run({"segments": [
        _seg("1:A14", "PLATO Prot. 340 A"),
        _seg("1:A17", "—Lach. 197 B"),
        _seg("1:A18", "—Charmid. 163 A B"),
        _seg("1:A26", "—Phileb. 58A"),
        _seg("1:A8", "PLATO Hipp. min. 363c"),
        _seg("1:A10", "—Hipp min. 364c"),
    ]}, work_id="prodicus-testimonia")
    got = {s: _cite(result[s][0][0])[1:] for s in ("1:A17", "1:A18", "1:A26", "1:A10")}
    assert got == {
        "1:A17": ("Plato", "Laches", "197 B"),
        "1:A18": ("Plato", "Charmides", "163 A B"),
        "1:A26": ("Plato", "Philebus", "58A"),
        "1:A10": ("Plato", "Hippias Minor", "364c"),
    }


def test_item3_other_titles():
    def one(*heads):
        segs = [_seg(f"1:X{i}", h) for i, h in enumerate(heads)]
        result = _run({"segments": segs}, work_id="w")
        return _cite(result[f"1:X{len(heads) - 1}"][0][-1])[1:]
    assert one("CIC. Acad. II 37, 118", "—de nat. d. I 10, 26 post A. ignem numen constituit") == \
        ("Cicero", "De Natura Deorum", "I 10, 26")
    assert one("IAMBL. de myst. I 11", "—de anima [Stob. Ecl. II 1, 16]") == \
        ("Iamblichus", "De Anima", "[Stob. Ecl. II 1, 16]")
    assert one("ARISTOPH. Aves 1694", "—Vesp. 420") == ("Aristophanes", "Vespae", "420")
    assert one("ARISTOPH. Nub. 360", "—Tagenistae fr. 490 K.") == \
        ("Aristophanes", "Tagenistae", "fr. 490 K.")
    assert one("SCHOL. PIND. Pyth. 4, 288", "—Nem. 7, 53") == \
        ("Scholia in Pindarum", "Scholia in Pindarum", "Nem. 7, 53")
    assert one("PHILODEM. de ira 28, 17 G.", "—de music. Δ 31 p. 108, 29 Kemke Δ.") == \
        ("Philodemus", "De Musica", "Δ 31 p. 108, 29 Kemke")
    assert one("THEOPHR. d. c. pl. VI 2, 3", "— —VI 7, 2") == \
        ("Theophrastus", "De Causis Plantarum", "VI 7, 2")


def test_item3_direct_titles(dictionary):
    cases = {
        "THEOPHR. d. c. pl. VI 2, 3": ("Theophrastus", "De Causis Plantarum", "VI 2, 3"),
        "AEL. V. H. VIII 19": ("Aelian", "Varia Historia", "VIII 19"),
        "AELIAN. V. H. XII 32": ("Aelian", "Varia Historia", "XII 32"),
        "TZETZES Schol. z. Hesiod (Gaisford Poet. gr. min. III 58)":
            ("John Tzetzes", "Scholia in Hesiodum", "(Gaisford Poet. gr. min. III 58)"),
    }
    for head, want in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _cite(e)[1:] == want, head


def _gnom(entry: dict) -> tuple:
    return _no_author(entry) + (entry.get("apparatus"),)


def test_gnomologia_have_no_author_and_keep_the_editor_as_apparatus(dictionary):
    # Grok content review item 4: a gnomologium is a collection, not an
    # author ("Gnomologium, Gnomologium Parisinum" printed its name twice).
    # Like Bekker's Anecdota it renders with no author; the locus is DK's
    # codex and saying number, the editor and edition DK names are apparatus,
    # as printed. Every gnomologium head in the 39 works.
    cases = {
        "GNOMOL. VINDOB. 50 p. 14 Wachsm.":                      # Antiphon A9
            ("direct", "Gnomologium Vindobonense", "50 p. 14", "Wachsm."),
        "GNOM. PARIS. n. 153 [Ac. Cracov. XX 152]":              # Empedocles A20
            ("direct", "Gnomologium Parisinum", "n. 153", "[Ac. Cracov. XX 152]"),
        "GNOMOL. VATIC. 743 n. 166 [ed. Sternbach Wien. Stud. X 36]":  # Gorgias B29
            ("direct", "Gnomologium Vaticanum", "743 n. 166", "[ed. Sternbach Wien. Stud. X 36]"),
        "GNOMOL. Monac. lat. I 19 (Caecil. Balb. Wölfflin p. u,)":  # Heraclitus B130
            ("direct", "Gnomologium Monacense Latinum", "I 19", "(Caecil. Balb. Wölfflin p. u,)"),
        "CORPUS PARISINUM PROFANUM [Cod. Paris. gr. 1168 nach Elter]: 166":  # Democritus B302
            ("direct", "Corpus Parisinum Profanum", "166", "[Cod. Paris. gr. 1168 nach Elter]"),
    }
    for head, want in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _gnom(e) == want, head
        assert e["work"]["italic"] is True, head
    result = _run({"segments": [                                  # Heraclitus B130-B135
        _seg("1:B130", "GNOMOL. Monac. lat. I 19 (Caecil. Balb. Wölfflin p. u,)"),
        _seg("1:B131", "—Paris. ed. Sternbach n. 209 ὁ γὰρ δὴ Ἡ. ἔλεγε"),
        _seg("1:B132", "—Vatic. 743 n. 312 Sternb."),
        _seg("1:B133", "— —313"),
    ]})
    assert _gnom(result["1:B131"][0][0]) == ("dash", "Gnomologium Parisinum", "n. 209", "ed. Sternbach")
    assert _gnom(result["1:B132"][0][0]) == ("dash", "Gnomologium Vaticanum", "743 n. 312", "Sternb.")
    assert _gnom(result["1:B133"][0][0]) == ("dash", "Gnomologium Vaticanum", "743 n. 313", None)
    result = _run({"segments": [                                  # Gorgias B29-B30
        _seg("1:B29", "GNOMOL. VATIC. 743 n. 166 [ed. Sternbach Wien. Stud. X 36] Γ. ὁ σοφός"),
        _seg("1:B30", "—n. 167 [a. O. 37] Γ. ὁ"),
    ]}, work_id="gorgias-fragments")
    assert _gnom(result["1:B30"][0][0]) == ("dash", "Gnomologium Vaticanum", "743 n. 167", "[a. O. 37]")


def test_cebren_is_cedrenus_not_bekkers_anecdota(dictionary):
    # Grok content review item 5: Anaxagoras A10 "CEBREN. I 165, 18 Bekk."
    # is Georgius Cedrenus, Compendium historiarum, cited by the page and
    # line of Bekker's edition (Bonn 1838-39, vol. I) -- not the Anecdota.
    (e,) = ce._resolve_head(dictionary, "CEBREN. I 165, 18 Bekk. καὶ δή, ὡς Πέρσαι", "w", "s")
    assert _cite(e) == ("direct", "Georgius Cedrenus", "Compendium Historiarum", "I 165, 18 Bekk.")
    assert e["work"]["italic"] is True


def test_apuleius_in_full_is_apuleius(dictionary):
    # Grok content review item 7: Thales A19 prints the name in full. The
    # locus ends at the editor: "Th." opens the Latin epithet that follows.
    (e,) = ce._resolve_head(
        dictionary, "APULEIUS Flor. 18 p. 37, 10 Helm Th. Prienensis ex decem illis prudentiae "
        "numeratis viris merito primus", "thales-testimonia", "1:A19")
    assert _cite(e) == ("direct", "Apuleius", "Florida", "18 p. 37, 10 Helm")


def test_item4_book_numeral_is_not_part_of_the_work_key(dictionary):
    cases = {
        "CIC. de div. I 20, 39 somnia, de quibus disputans": "I 20, 39",       # Antiphon B79
        "CIC. de div. i 50, 112 ab Anaximandro physico": "I 50, 112",          # Anaximander A5a (read as I)
        "PROCL. in Parm. I p. 708, 16 (nach B 8, 25)": "I p. 708, 16 (nach B 8, 25)",  # Parmenides B5
        "PROCL. in Parm. p. 694, 23 [zu Plat. p. 127 D]": "p. 694, 23 [zu Plat. p. 127 D]",
    }
    for head, locus in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert e["locus"] == locus, head
    result = _run({"segments": [
        _seg("1:A17", "PROCL. in Tim. I 345, 12 Diehl"),
        _seg("1:A18", "—in Parm. I p. 665, 17"),  # real Parmenides A18
    ]}, work_id="parmenides-testimonia")
    assert _cite(result["1:A18"][0][0]) == ("dash", "Proclus", "in Platonis Parmenidem", "I p. 665, 17")


def test_item5_heads_that_were_fatal(dictionary):
    (e,) = ce._resolve_head(
        dictionary, "CAELIUS AUREL. Morb. chron. I 5 p. 25 Sich. (furor) Anaxagoram secuti "
        "aliud dicunt ex mentis vitio nasci", "empedocles-testimonia", "1:A98")
    assert _cite(e) == ("direct", "Caelius Aurelianus", "De Morbis Chronicis", "I 5 p. 25 Sich. (furor)")
    entries = ce._resolve_head(
        dictionary, "PLIN. N. H. VII 156 compertum est Zenonem Eleatem nonaginta et duos vixisse. "
        "[LUC.] Macrob 23", "gorgias-testimonia", "1:A13")
    assert _cite(entries[-1]) == ("direct", "pseudo-Lucian", "Macrobii", "23")
    entries = ce._resolve_head(
        dictionary, "EUSEB. Chron. Hier. Euripides ... [444—41]. APUL. Flor. 18 P. qui philosophus "
        "erat valde peritus", "protagoras-testimonia", "1:A4")
    assert _cite(entries[-1]) == ("direct", "Apuleius", "Florida", "18")


def test_item6_mixed_case_author_after_a_boundary_starts_a_new_source():
    # Real Democritus B32: after Clement, DK names Hippolytus as a second
    # source. John's B32 reading still applies to the Clement part.
    result = _run({"segments": [
        _seg("1:B31", "CLEM. Paed. I 6 (I 93, 15 Stähl.)"),
        _seg("1:B32", "— —94 (I 214, 9 St.) Hipp. Ref. VIII 14 (p. 234, 5 W.)."),
    ]}, work_id="democritus-fragments")
    clem, hipp = result["1:B32"][0]
    assert (clem["authorDisplay"], clem["locus"], clem["apparatus"]) == \
        ("Clement of Alexandria", "II 94", "(I 214, 9 St.)")
    assert "adjudicated" in clem["flags"]
    assert _cite(hipp) == ("direct", "Hippolytus", "Refutatio Omnium Haeresium", "VIII 14 (p. 234, 5 W.)")


def test_item6_hipp_without_a_hippolytus_title_is_not_hippolytus():
    # Synthetic: a dash-lost "Hipp." after PLATO is still Plato's Hippias.
    result = _run({"segments": [
        _seg("1:A8", "PLATO Hipp. min. 363c"),
        _seg("1:A9", "Hipp. maior 286 A"),
    ]}, work_id="hippias-testimonia")
    assert _cite(result["1:A9"][0][0])[1:] == ("Plato", "Hippias Maior", "286 A")


def test_item10_column_letters_only_where_the_scheme_has_them(dictionary):
    cases = {
        "LUCR. V 621 DE SOLE": "V 621",                       # Lucretius: book + line
        "PLUT. adv. Col. 11 p. 1113 AB": "11 p. 1113 AB",     # Moralia: Stephanus page
        "ATHEN. XIII 610 BC": "XIII 610 BC",                  # synthetic, Casaubon page
        "ATHEN. V p. 178 F": "V p. 178 F",
        "ARISTOTELES Meteor. B 2. 355a 13": "B 2. 355a 13",
        "PLATO Hipp. maior 282D E": "282D E",
    }
    for head, locus in cases.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert e["locus"] == locus, head


# --- Two-fix round, 2026-09-24 (Herodian titles Latin; Critias A20 bracket) -

def test_critias_a20_phrynich_bracket_is_apparatus_not_a_truncated_locus(dictionary):
    # Real Critias A20 (critias-testimonia): "PHRYNICH. Praepar. sophist.
    # [Phot. Bibl. 158 p. 101b 4 Bekk.]" used to match only the DEFAULT work,
    # which let the generic locus-truncation rule cut the locus after
    # "Praepar." and silently drop "sophist." and the whole bracket. The
    # work abbreviation "Praepar. sophist." is now matched explicitly as
    # *Praeparatio Sophistica*; DK prints no page/number of his own, so the
    # locus is empty and the bracket -- naming where Photius preserves the
    # passage -- is apparatus, kept as printed (brackets and all).
    (e,) = ce._resolve_head(
        dictionary, "PHRYNICH. Praepar. sophist. [Phot. Bibl. 158 p. 101b 4 Bekk.]",
        "critias-testimonia", "1:A20")
    assert _cite(e) == ("direct", "Phrynichus", "Praeparatio Sophistica", "")
    assert e["apparatus"] == "[Phot. Bibl. 158 p. 101b 4 Bekk.]"


def test_herodian_title_locus_may_not_swallow_a_following_source():
    # Synthetic: a Herodian title's up-to-four-word greek-word count could
    # reach a stray Greek word ("τὸ") that is not part of the title, and the
    # old `_is_head_material_token` check then let the NEXT source's own
    # head ("PLUT. de aud. ...") read as Herodian's locus. After a Herodian
    # title, the locus may open only with a number, "p.", a bracket, or a
    # "bei ..." note (_herodian_locus_start); anything else, including a
    # Greek word, ends the head with no locus -- never "τὸ". The Plutarch
    # text after it is not turned into its own head here (no new split
    # invented): it stays passage text, scanned but not emitted.
    result = _run({"segments": [
        _seg("1:B1", "HERODIAN. π. μον. λέξ. τὸ PLUT. de aud. 7 p. 41 A"),
    ]}, work_id="w")
    (e,) = result["1:B1"][0]
    assert _cite(e) == ("direct", "Herodian (grammarian)", "De Dictione Singulari", "")


def test_herodian_real_heads_still_render_as_before(dictionary):
    # The six real Herodian heads (Xenophanes B10, B36, B37, B38, B42;
    # Critias B41) plus Democritus B127/B128 (dash) and Empedocles B51 are
    # unaffected by the item-6 tightening -- unchanged from
    # test_herodian_greek_title_is_the_work_and_what_follows_is_the_locus.
    result = _run({"segments": [
        _seg("1:X10", "HERODIAN π. διχρ. p. 296, 6 [Cr. An. Ox. III]"),
        _seg("1:X36", "HERODIAN. π. διχρ. 296, 9"),
        _seg("1:X37", "HERODIAN. π. μον. λέξ. 30, 30"),
        _seg("1:X38", "HERODIAN. π. μον. λέξ. p. 41, 5"),
        _seg("1:X42", "HERODIAN. π. μον. λέξεως 7, 11 καὶ πρὸς Ἐμπεδοκλεῖ ἐν βίῳ Φυσικῶν·"),
        _seg("1:C41", "HEROD. π. μον. λέξ. p. 40, 14 τὸ μὲν παρὰ Νικάνδρωι ἐπὶ"),
        _seg("1:D127", "HERODIAN. π. καθολ. προσ. bei Eustath. zu ξ 428 p. 1766 [II 445, 9 L.] καὶ Δ.",
             ("text", "γελῶντες ἄνθρωποι χαίρουσι"), "."),
        _seg("1:D128", "—π. καθολ. προσ. bei Theogn. p. 79 [I 355, 19 L.] εἰς ἣν θηλυκόν"),
        _seg("1:E51", "HERODIAN. schematismi Hom. cod. Darmstadini in Sturzii Et. Gud. p. 745 "
                      "[ad Et. M. p. 111, 10] ἀκίχητα· οἱ δὲ κρυπτά"),
    ]}, work_id="w")
    h = ("Herodian (grammarian)",)
    got = {s: _app(result[s][0][0])[1:] for s in result}
    assert got == {
        "1:X10": h + ("De Dichronis", "p. 296, 6 [Cr. An. Ox. III]", None),
        "1:X36": h + ("De Dichronis", "296, 9", None),
        "1:X37": h + ("De Dictione Singulari", "30, 30", None),
        "1:X38": h + ("De Dictione Singulari", "p. 41, 5", None),
        "1:X42": h + ("De Dictione Singulari", "7, 11", None),
        "1:C41": h + ("De Dictione Singulari", "p. 40, 14", None),
        "1:D127": h + ("De Prosodia Catholica", "", "bei Eustath. zu ξ 428 p. 1766 [II 445, 9 L.]"),
        "1:D128": h + ("De Prosodia Catholica", "", "bei Theogn. p. 79 [I 355, 19 L.]"),
        "1:E51": h + ("Schematismi Homerici",
                      "cod. Darmstadini in Sturzii Et. Gud. p. 745 [ad Et. M. p. 111, 10]", None),
    }
    assert result["1:D128"][0][0]["resolution"] == "dash"


def test_phrynich_other_work_is_unaffected_by_the_praepar_sophist_key(dictionary):
    # Real Hippias B10 (hippias-fragments): a different Phrynichus work
    # ("ecl." = Eclogae) is his Ecloga, not the Praeparatio the DEFAULT
    # names (replaced 2026-09-27: this test had locked in that title).
    (e,) = ce._resolve_head(dictionary, "PHRYNICH. ecl. 312 Lob.", "hippias-fragments", "1:B10")
    assert _cite(e) == ("direct", "Phrynichus", "Ecloga", "312 Lob.")

# Synthetic source strings: no licensed corpus excerpts in these tests.
def test_located_every_source_and_pointer_only(dictionary):
    lines = [
        {"n": -1, "text": "ARIST. Metaph. A 3. 984a 7 [s. c. 18, 7 I 109, 5].", "role": "context"},
        {"n": -1, "text": "SIMPL. Phys. 23, 33 λόγος. AËT. I 3, 11 (D. 283) λόγος. GAL. de elem. sec. Hipp. I 4 (I 443 K. 23, 1 Helmr.) λόγος.", "role": "context"},
    ]
    heads = ce.located_heads(dictionary, lines)
    assert len(heads) == 4
    assert [h['lineIndex'] for h in heads] == [0, 1, 1, 1]
    assert heads[0]['text'] == lines[0]['text']
    assert heads[2]['text'] == 'AËT. I 3, 11 (D. 283)'
    for h in heads:
        assert lines[h['lineIndex']]['text'][h['start']:h['end']] == h['text']


def test_located_a4_shape(dictionary):
    text = 'ARIST. Rhet. Γ 5. 1407b 11 λόγος. DEMETR. 192 λόγος. DIOG. II 22 λόγος.'
    heads = ce.located_heads(dictionary, [{'n': 1, 'text': text}])
    assert [h['text'] for h in heads] == ['ARIST. Rhet. Γ 5. 1407b 11', 'DEMETR. 192', 'DIOG. II 22']


@pytest.mark.parametrize('text', [
    'XIV p. 645', '[B 40].', '(D. 283)',
    'λόγος ARIST. Metaph. A 3', 'λόγος, ARIST. Metaph. A 3',
    'λόγος [vgl. ARIST. Metaph. A 3].', 'de caelo Γ 3. 302a 28 λόγος.',
])
def test_location_negatives(dictionary, text):
    assert ce.located_heads(dictionary, [{'n': 1, 'text': text}]) == []


@pytest.mark.parametrize('boundary', ['. ', '· ', '; ', ': ', '] ', ') ', '.”) '])
def test_location_sentence_boundaries(dictionary, boundary):
    text = 'λόγος' + boundary + 'DIOG. II 22 λόγος.'
    assert len(ce.located_heads(dictionary, [{'n': 1, 'text': text}])) == 1


def test_location_work_continuation_same_column(dictionary):
    seg = {'id': '1:A43', 'lines': [
        {'n': 1, 'role': 'context', 'text': 'ARIST. Metaph. A 3. 984a 11 λόγος. de caelo Γ 3. 302a 28 λόγος.'},
        {'n': 2, 'role': 'context', 'text': 'de gen. et corr. I 1. 314a 1 λόγος.'},
    ]}
    result = ce.resolve_located_segments(dictionary, [seg], 'fixture', {})['1:A43']
    assert len(result) == 3
    assert result[0]['text'] == 'ARIST. Metaph. A 3. 984a 11'
    assert result[1]['expanded'][0]['authorDisplay'] == 'Aristotle'
    assert result[1]['expanded'][0]['work']['title'] == 'De Caelo'
    assert result[1]['expanded'][0]['verbatim'] == result[1]['text']
    assert 'work-continuation' in result[1]['expanded'][0]['flags']
    assert not ce.located_heads(dictionary, [seg['lines'][1]])


def test_location_dash_sections_latin_and_utf16(dictionary):
    lines = [{'n': 1, 'text': 'DIOG. IX 1—17. (1) λόγος. — —22 λόγος.'},
             {'n': 2, 'text': 'COLUMELLA VIII 4 si vero credimus.'},
             {'n': 3, 'text': '𐀀. DIOG. II 22 λόγος.'}]
    heads = ce.located_heads(dictionary, lines)
    assert [h['text'] for h in heads] == ['DIOG. IX 1—17.', '— —22', 'COLUMELLA VIII 4', 'DIOG. II 22']
    assert heads[-1]['start'] == 4


def test_run_emits_location_sidecar_and_legacy_unchanged(tmp_path):
    path = ce.run(_manifest(True), _spine('DIOG. IX 1 λόγος. DIOG. II 22 λόγος.'))
    heads = json.loads((path.parent / 'citation_heads.json').read_text())['1:B1']
    assert len(heads) == 2
    assert heads[1]['expanded'][0]['authorDisplay'] == 'Diogenes Laertius'
    assert isinstance(json.loads(path.read_text())['1:B1'], list)


# --- Page-structure check gaps (2026-09-26) ----------------------------------
# Printed heads as DK has them; the passages are placeholders.

@pytest.mark.parametrize("head,expected", [
    # Parmenides A1, Xenophanes A2: a book numeral + section = Diogenes Laertius.
    ("DIOGENES IX 21", ("direct", "Diogenes Laertius", "Vitae Philosophorum", "IX 21")),
    # Democritus A50: DK names Oenoanda in full.
    ("DIOGENES v. Oinoanda fr. 33c. 2 [p. 41 William Lpz. 1907]",
     ("direct", "Diogenes of Oenoanda", "Fragmenta (Inscriptio)", "fr. 33c. 2 [p. 41 William Lpz. 1907]")),
    # Thales A1: the full name, unaffected.
    ("DIOGENES LAERTIUS I 22", ("direct", "Diogenes Laertius", "Vitae Philosophorum", "I 22")),
])
def test_bare_diogenes_by_what_follows(dictionary, head, expected):
    (e,) = ce._resolve_head(dictionary, head, "w", "s")
    assert _cite(e) == expected
    assert ("author-inferred" in e["flags"]) == (head == "DIOGENES IX 21")


def test_bare_diogenes_with_nothing_deciding_stays_as_printed(dictionary):
    (e,) = ce._resolve_head(dictionary, "DIOGENES fr. 3", "w", "s")
    assert _verbatim_flags(e) == ["ambiguous-abbrev"]


def test_demetrius_bare_section_is_de_elocutione(dictionary):
    # Heraclitus A4 "DEMETR. 192" (was fatal, then kept verbatim as
    # work-unresolved); Democritus B298a's De poematis keeps its flag.
    (e,) = ce._resolve_head(dictionary, "DEMETR. 192", "w", "s")
    assert _cite(e) == ("direct", "Demetrius", "De Elocutione", "192")
    assert e["flags"] == []
    (p,) = ce._resolve_head(dictionary, "DEMETR. de poem. B 20", "w", "s")
    assert _cite(p) == ("direct", "Demetrius", "De Poematis", "B 20")
    assert p["flags"] == ["uncertain"]


def test_aristotle_title_spellings_and_comma_head(dictionary):
    seg = {"id": "1:A78", "lines": [{"n": 1, "role": "context", "text":
           "AËT. V 22, 1 (D. 434) λόγος. ARISTOT. de part. an. Α 1. 642a 17 λόγος. "
           "ARISTOT, de anima Α 4. 408a 13 λόγος. d. gen. et corr. B 7. 334a 5 λόγος."}]}
    heads = ce.resolve_located_segments(dictionary, [seg], "fixture", {})["1:A78"]
    assert [h["text"] for h in heads] == [
        "AËT. V 22, 1 (D. 434)", "ARISTOT. de part. an. Α 1. 642a 17",
        "ARISTOT, de anima Α 4. 408a 13", "d. gen. et corr. B 7. 334a 5"]
    assert [_cite(h["expanded"][0])[1:] for h in heads[1:]] == [
        ("Aristotle", "De Partibus Animalium", "Α 1. 642a 17"),
        ("Aristotle", "De Anima", "Α 4. 408a 13"),
        ("Aristotle", "De Generatione et Corruptione", "B 7. 334a 5")]
    assert "work-continuation" in heads[3]["expanded"][0]["flags"]


# --- Number ranges in the locus (2026-09-26) ---------------------------------
# A range printed with a dash ("1—17.") was cut off, leaving the book alone.

@pytest.mark.parametrize("head,locus,apparatus", [
    ("DIOG. IX 1—17.", "IX 1—17.", None),          # Heraclitus A1
    ("DIOG. II 1—2.", "II 1—2.", None),            # Anaximander A1
    ("DIOGENES IX 21—23.", "IX 21—23.", None),     # Parmenides A1
    ("HIPPOL. Ref. I 6, 1—7 (D.559 W. 10).", "I 6, 1—7", "(D.559 W. 10)"),  # Anaximander A11
    ("SEXT. VII 122-124", "VII 122-124", None),
    # A single number ending in "." is unchanged.
    ("DIOG. II 22.", "II 22.", None),
    ("LUCR. V 621.", "V 621.", None),
])
def test_number_range_stays_whole(dictionary, head, locus, apparatus):
    (e,) = ce._resolve_head(dictionary, head, "w", "s")
    assert e["resolution"] == "direct"
    assert e["locus"] == locus
    assert e.get("apparatus") == apparatus


@pytest.mark.parametrize("head,locus", [
    ("DIOG. IX 1—17. (1)", "IX 1—17."),
    ("DIOGENES LAERTIUS I 22—44. (22)", "I 22—44."),
])
def test_number_range_never_takes_the_section_marker(dictionary, head, locus):
    (e,) = ce._resolve_head(dictionary, head, "w", "s")
    assert e["locus"] == locus


def test_number_range_located_head_before_section_and_greek(dictionary):
    seg = {"id": "1:A1", "lines": [{"n": 1, "role": "context",
           "text": "DIOG. IX 1—17. (1) Ἡράκλειτος Βλόσωνος."}]}
    (h,) = ce.resolve_located_segments(dictionary, [seg], "fixture", {})["1:A1"]
    assert h["text"] == "DIOG. IX 1—17."
    assert h["expanded"][0]["locus"] == "IX 1—17."


# --- Head detection: the five patterns of the Grok check (2026-09-26) -------
# Printed heads as DK has them; the passages are short placeholders.

def _located(dictionary, *lines):
    """The located heads of one column; each line is (role, text)."""
    seg = {"id": "1:X", "lines": [{"n": i + 1, "role": role, "text": text}
                                  for i, (role, text) in enumerate(lines)]}
    return ce.resolve_located_segments(dictionary, [seg], "fixture", {})["1:X"]


def _texts(heads):
    return [h["text"] for h in heads]


# 1. A change of speaker in a quoted dialogue is no continuation head: a dash
# is one only where a locus, an author or a title follows it.
@pytest.mark.parametrize("text,heads", [
    # Philolaus B15
    ("PLAT. Phaedo 61 D τί δέ, ὦ Κέβης; λόγος συγγεγονότες; —Οὐδέν γε σαφές, ὦ Σώκρατες. "
     "—Ἀλλὰ μὴν λόγος.", ["PLAT. Phaedo 61 D"]),
    # Empedocles A92
    ("PLATO Meno p. 76 C λόγος ἀκολουθήσαις; —Βούλομαι· πῶς γὰρ οὔ; —Οὐκοῦν λόγος.",
     ["PLATO Meno p. 76 C"]),
    # Anaxagoras A15: the dash is fused to the first Greek word.
    ("PLAT. Phaedr. 269 E—Κινδυνεύει, ὦ ἄριστε, λόγος.", ["PLAT. Phaedr. 269 E"]),
    # Protagoras A11: a dash before Latin prose; the source after "Vgl." has
    # its own text, so it is a head, and takes DK's "— Vgl." with it.
    ("ATHEN. V 218 B λόγος. — Vgl. EUSTATH. Od. 1547, 53 ἐμφαίνειν λόγος.",
     ["ATHEN. V 218 B", "— Vgl. EUSTATH. Od. 1547, 53"]),
])
def test_speaker_dash_is_no_head(dictionary, text, heads):
    assert _texts(_located(dictionary, ("context", text))) == heads


def test_speaker_dash_across_lines_is_no_head(dictionary):
    # Philolaus B6: a dash at a line end before Greek; Gorgias A5a: a dash
    # opening a line inside a context run, before a Greek verse.
    assert _texts(_located(dictionary, ("context", "STOB. I 21, 7d λόγος"),
                           ("text", "λόγος κατέχεσθαι. —"), ("context", "ἁρμονίας δὲ λόγος"))) == \
        ["STOB. I 21, 7d"]
    assert _texts(_located(dictionary, ("context", "ARISTOPH. Vesp. 420"),
                           ("context", "Ἡράκλεις λόγος;"),
                           ("context", "—οἷς γ' ἀπώλεσαν λόγος."))) == ["ARISTOPH. Vesp. 420"]


def test_continuation_dashes_stay_heads(dictionary):
    # Heraclitus B42: DK's dash alone repeats the source above where it opens
    # a line; Heraclitus A12: a dash before numbers mid-line; Gorgias A5a: a
    # dash before a title of the author above.
    heads = _located(dictionary, ("context", "DIOG. IX 1 λόγος."), ("text", "— —τόν τε Ὅμηρον λόγος"))
    assert _texts(heads) == ["DIOG. IX 1", "— —"]
    assert _texts(_located(dictionary, ("context",
                  "AËT. II 22, 1 (D. 351) λόγος. —24, 3 (D. 354) λόγος."))) == \
        ["AËT. II 22, 1 (D. 351)", "—24, 3 (D. 354)"]
    heads = _located(dictionary, ("context", "ARISTOPH. Nub. 360 λόγος"), ("context", "λόγος."),
                     ("context", "—Vesp. 420"), ("context", "λόγος."))
    assert _texts(heads) == ["ARISTOPH. Nub. 360", "—Vesp. 420"]
    assert _cite(heads[1]["expanded"][0])[1:3] == ("Aristophanes", "Vespae")


def test_speaker_dash_in_a_paragraph_is_no_citation(dictionary):
    # The structure gate's paragraph scan uses the same rule.
    assert ce.citation_starts(dictionary, "λόγος; —Οὐδέν γε σαφές. —Ἀλλὰ μὴν λόγος.") == []


# 2. A continuation dash's head runs through the locus it introduces.
@pytest.mark.parametrize("lines,head", [
    # Hippias A11
    ([("context", "—Hipp. mai. 285 B ἐπαινοῦσι λόγος")], "—Hipp. mai. 285 B"),
    # Philolaus B6, with the passage on the same line and on the next
    ([("context", "— —7d [p. 188, 14,] περὶ δὲ λόγος")], "— —7d [p. 188, 14,]"),
    ([("context", "— —7d [p. 188, 14,]"), ("text", "περὶ δὲ λόγος")], "— —7d [p. 188, 14,]"),
])
def test_dash_head_runs_through_its_locus(dictionary, lines, head):
    assert _texts(_located(dictionary, *lines)) == [head]


def test_dash_before_an_author_keeps_his_title(dictionary):
    # Heraclitus A10 "—ARIST. de caelo ...": no second head at the title.
    heads = _located(dictionary, ("context",
                     "SIMPL. Phys. 23, 33 λόγος [31 B 17]. —ARIST. de caelo Α 10. 279b 12 γενόμενον λόγος."))
    assert _texts(heads) == ["SIMPL. Phys. 23, 33", "—ARIST. de caelo Α 10. 279b 12"]
    assert _cite(heads[1]["expanded"][0]) == ("direct", "Aristotle", "De Caelo", "Α 10. 279b 12")


# 3. A group opened inside a head closes inside it.
@pytest.mark.parametrize("text,head,locus,apparatus", [
    # Anaxagoras A89
    ("AËT. III 15, 4 (D. 379; περὶ σεισμῶν γῆς) Ἀ. ἀέρος λόγος.",
     "AËT. III 15, 4 (D. 379; περὶ σεισμῶν γῆς)", "III 15, 4", "(D. 379; περὶ σεισμῶν γῆς)"),
    # Democritus A91
    ("ACHILL. IS. 24 [p. 55, 24 M; περὶ τοῦ γαλαξίου] ἄλλοι δὲ λόγος.",
     "ACHILL. IS. 24 [p. 55, 24 M; περὶ τοῦ γαλαξίου]", "24 [p. 55, 24 M; περὶ τοῦ γαλαξίου]", None),
    # Gorgias A10: the head was cut inside the bracket.
    ("APOLLODOR. [F GrHist. 244F 33, s. oben I 278, 28] ἐννέα λόγος.",
     "APOLLODOR. [F GrHist. 244F 33, s. oben I 278, 28]", None, None),
])
def test_group_closes_inside_the_head(dictionary, text, head, locus, apparatus):
    (h,) = _located(dictionary, ("context", text))
    assert h["text"] == head
    if locus is not None:
        assert h["expanded"][0]["locus"] == locus
        assert h["expanded"][0].get("apparatus") == apparatus


def test_group_that_opens_the_quotation_ends_the_head(dictionary):
    # Democritus A99: the parenthesis holds the quoted text itself.
    (h,) = _located(dictionary, ("context", "DIODOR. I 39 (... τοῖς μεγίστοις ὄρεσι λόγος)."))
    assert h["text"] == "DIODOR. I 39"


# 4. The locus ends where the quotation begins, and not before.
@pytest.mark.parametrize("text,head,locus", [
    # Anaximander A30: A[naximander] Milesius opens the Latin quotation.
    ("CENSORIN. 4, 7 A. Milesius videri sibi ex aqua terraque.", "CENSORIN. 4, 7", "4, 7"),
    # Gorgias A26, Protagoras A20: the same with G[orgias], P[rotagoras].
    ("CIC. de inv. 5, 2 G. Leontinus, antiquissimus fere rhetor.", "CIC. de inv. 5, 2", None),
    ("SEN. Ep. 88, 43 P. ait de omni re disputari posse.", "SEN. Ep. 88, 43", "88, 43"),
    # Gorgias A4, Anaxagoras A15: "d." (de) before the title.
    ("DIONYS. d. Lys. 3 δηλοῖ δὲ λόγος.", "DIONYS. d. Lys. 3", "3"),
    ("CIC. d. orat. III 138 Periclem non declamator aliquis.", "CIC. d. orat. III 138", "III 138"),
])
def test_locus_extent(dictionary, text, head, locus):
    (h,) = _located(dictionary, ("context", text))
    assert h["text"] == head
    if locus is not None:
        assert h["expanded"][0]["locus"] == locus


@pytest.mark.parametrize("text,head", [
    # A Greek initial opens the quotation, with what follows it.
    ("AËT. II 13, 7 (D. 342) Ἀ. [sc. τὰ ἄστρα εἶναι] λόγος.", "AËT. II 13, 7 (D. 342)"),
    ("—29, 3 Ἡ. ... (ἐκλείπειν λόγος)", "—29, 3"),
    # A section word, "z. d. St.", "bei <author>": still the citation.
    ("PHILOSTR. V. soph. I 15, 2 πιθανώτατος λόγος.", "PHILOSTR. V. soph. I 15, 2"),
    ("COLUMELLA de r. rust. I praef. 32 accedit huc quod.", "COLUMELLA de r. rust. I praef. 32"),
    ("SCHOL. z. d. St. Abderita nam fuit D.", "SCHOL. z. d. St."),
    ("EUDEM. bei Simpl. Phys. 143, 4 ὥστε λόγος.", "EUDEM. bei Simpl. Phys. 143, 4"),
    ("CLEM. AL. Strom. I 62 [II 39, 17 St.] Πυθαγόρας λόγος.", "CLEM. AL. Strom. I 62 [II 39, 17 St.]"),
    # A name in a Latin list is not an editor.
    ("CICERO Acad. prior. II 23, 74 Parmenides, X., minus bonis versibus.",
     "CICERO Acad. prior. II 23, 74"),
])
def test_head_extent_quotation_boundary(dictionary, text, head):
    assert _texts(_located(dictionary, ("context", text))) == [head]


# 5. "vgl." + a citation is a head only when its own text follows; "ebenda"
# is a continuation head of the source above in the column.
def test_vgl_pointer_and_ebenda(dictionary):
    # Empedocles B98
    heads = _located(dictionary, ("context",
                     "SIMPL. Phys. 32, 3 λόγος ‘ἡ δὲ ... σαρκός’ vgl. AËT. v 22 [A 78 I 299, 5]. "
                     "EBEND. 331, 3 καὶ τὰ μόρια λόγος."))
    assert _texts(heads) == ["SIMPL. Phys. 32, 3", "EBEND. 331, 3"]
    e = heads[1]["expanded"][0]
    # The head above, not the Aëtius the pointer names.
    assert _cite(e) == ("dash", "Simplicius", heads[0]["expanded"][0]["work"]["title"], "331, 3")
    assert "ebend" in e["flags"] and e["verbatim"] == "EBEND. 331, 3"


def test_vgl_with_its_own_text_is_a_head(dictionary):
    # Gorgias A4: Dionysius's own text follows.
    heads = _located(dictionary, ("context", "DIOD. XII 53, 1 λόγος. vgl. DIONYS. d. Lys. 3 δηλοῖ λόγος."))
    assert _texts(heads) == ["DIOD. XII 53, 1", "vgl. DIONYS. d. Lys. 3"]
    # The heading's "vgl." is DK's; the citation resolves as before.
    assert _cite(heads[1]["expanded"][0]) == ("direct", "Dionysius of Halicarnassus", "De Lysia", "3")
    assert heads[1]["expanded"][0]["verbatim"] == "vgl. DIONYS. d. Lys. 3"


@pytest.mark.parametrize("text,paragraph", [
    # Empedocles A44: a pointer ends the column.
    ("ARISTOT. Metaph. A 3. 984a 11 λόγος. Vgl. ARISTOT. de cael. Γ 5.",
     "λόγος. Vgl. ARISTOT. de cael. Γ 5."),
    # Thales A22: another citation follows the pointer at once.
    ("ARIST. de anima A 5. 411 a 7 λόγος. Vgl. PLATO Legg. X 899 B. AR. ebend. A 2. 405a 19 ἔοικε λόγος.",
     "λόγος. Vgl. PLATO Legg. X 899 B."),
])
def test_vgl_pointer_is_no_head(dictionary, text, paragraph):
    texts = _texts(_located(dictionary, ("context", text)))
    assert not any(t.startswith(("ARISTOT. de cael.", "PLATO")) for t in texts)
    # The structure gate's paragraph scan agrees.
    assert ce.citation_starts(dictionary, paragraph) == []


def test_ebenda_after_an_author_abbreviation(dictionary):
    # Thales A22 "AR. ebend.": Aristotle, De anima, as the head above.
    heads = _located(dictionary, ("context",
                     "ARIST. de anima A 5. 411 a 7 λόγος. Vgl. PLATO Legg. X 899 B. AR. ebend. A 2. 405a 19 ἔοικε λόγος."))
    assert _texts(heads) == ["ARIST. de anima A 5. 411 a 7", "AR. ebend. A 2. 405a 19"]
    assert _cite(heads[1]["expanded"][0]) == ("dash", "Aristotle", "De Anima", "A 2. 405a 19")


def test_ebenda_steps(dictionary):
    # Xenophanes A26 (a number after a book), Parmenides A34 ("p."), and an
    # "ebenda" inside a citation (Democritus B14, "epileg. ebenda p. 275, 1")
    # that is no head of its own.
    heads = _located(dictionary, ("context", "PHILO de provid. II 39 non ita tamen. Ebend. 42 at quare."))
    assert _texts(heads) == ["PHILO de provid. II 39", "Ebend. 42"]
    assert heads[1]["expanded"][0]["locus"] == "II 42"
    heads = _located(dictionary, ("context", "SIMPL. Phys. 39, 10 λόγος. Ebend. p. 25, 15 καὶ λόγος."))
    assert heads[1]["expanded"][0]["locus"] == "p. 25, 15"
    assert len(_located(dictionary, ("context", "PTOLEM. Apparit. epileg. ebenda p. 275, 1"))) == 1


def test_ebenda_after_an_unread_citation_stays_as_printed(dictionary):
    # Parmenides A20: "Menander Rhet. I 2, 2" stands between the head above
    # and the "Ebend.", which may mean either.
    heads = _located(dictionary, ("context",
                     "SIMPL. Phys. 146, 29 λόγος; Menander Rhet. I 2, 2 φυσικοὶ λόγος [vgl. 31 A 23]. "
                     "Ebend. I 5, 2 εἰσὶν δὲ λόγος."))
    assert _texts(heads) == ["SIMPL. Phys. 146, 29", "Ebend. I 5, 2"]
    assert _verbatim_flags(heads[1]["expanded"][0]) == ["ebend", "ebend-unresolved"]


# 2026-09-27 fixes. 1. "SCHOL. <AUTHOR>." is one source, a scholion on that
# author (Empedocles A19), not a bare "SCHOL." and a separate author head.
def test_scholion_on_iamblichus_is_one_head(dictionary):
    heads = _located(dictionary, ("context",
                     "ARISTOT. Soph. el. 33 p. 183b 31 λόγος. SCHOL. IAMBLICH. V. P. p. 198 Nauck λόγος."))
    assert _texts(heads) == ["ARISTOT. Soph. el. 33 p. 183b 31", "SCHOL. IAMBLICH. V. P. p. 198 Nauck"]
    (e,) = heads[1]["expanded"]
    assert _cite(e) == ("direct", "Scholia in Iamblichum", "De Vita Pythagorica", "p. 198 Nauck")
    assert e["work"]["italic"] and "scholia" in e["flags"]


# 2. Titles that expanded to "(work of ...)".
@pytest.mark.parametrize("head,author,title,locus", [
    # Critias A1, A21, Protagoras A2, Antiphon A6; the match is case-folded.
    ("PHILOSTR. V. soph. I 16", "Philostratus", "Vitae Sophistarum", "I 16"),
    ("PHILOSTR. V. Soph. I 15, 4", "Philostratus", "Vitae Sophistarum", "I 15, 4"),
    # Democritus A9
    ("PHILOSTR. Vit. sophist. 10 p. 13, 1 Kayser", "Philostratus", "Vitae Sophistarum", "10 p. 13, 1 Kayser"),
    # Leucippus A5: "P." is his title, not a page marker.
    ("IAMBL. V. P. 104", "Iamblichus", "De Vita Pythagorica", "104"),
    # A key ending in the page marker "p." still leaves it in the locus.
    ("IAMBL. in Nicom. p. 118, 23", "Iamblichus", "in Nicomachi Arithmeticam", "p. 118, 23"),
])
def test_philostratus_and_iamblichus_titles(dictionary, head, author, title, locus):
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)
    assert e["work"]["italic"]


# 3. A bracket or parenthesis that does not close before the quoted text
# ends the head before it; the opener stays in the passage.
@pytest.mark.parametrize("lines,head,locus", [
    # Anaxagoras B7: the parenthesis closes on a later line, after Greek.
    ((("context", "SIMPLIC. de caelo 608, 23 (nach"), ("text", "λόγος [B 4]). λόγος.")),
     "SIMPLIC. de caelo 608, 23", "608, 23"),
    # Anaximenes A17, Anaxagoras A42, Pythagoras 13: it never closes.
    ((("context", "AËT. III 3, 2 (D. 368, Ἀναξιμένης λόγος (περὶ λόγου) λόγος."),),
     "AËT. III 3, 2", "III 3, 2"),
    ((("context", "HIPPOL. Refut. I 8, 1 ff. [D. 561, W. 13; (1) λόγος [λόγος] λόγος."),),
     "HIPPOL. Refut. I 8, 1 ff.", "I 8, 1 ff."),
    ((("context", "PAP. HERC. 1788 (Coll. alt. VIII fr. 4; Crönert S. 147 <λόγος> λόγος."),),
     "PAP. HERC. 1788", None),
])
def test_unclosed_group_is_left_out_of_the_head(dictionary, lines, head, locus):
    (h,) = _located(dictionary, *lines)
    assert h["text"] == head
    if locus is not None:
        assert h["expanded"][0]["locus"] == locus
        assert "apparatus" not in h["expanded"][0]


# 4. A heading DK introduces with "vgl." takes it (and a dash, or the word
# or line the note is on) so no passage ends in a bare "Vgl.".
@pytest.mark.parametrize("lines,head,cite", [
    # Anaxagoras A47
    ((("context", "ARISTOT. Phys. A 4. 187a 20 λόγος. Vgl. ARISTOT. Metaph. A 4. 985a 18 λόγος."),),
     "Vgl. ARISTOT. Metaph. A 4. 985a 18", ("direct", "Aristotle", "Metaphysica", "A 4. 985a 18")),
    # Democritus B117: "Vgl." opens the line.
    ((("text", "λόγος."), ("context", "Vgl. CIC. Ac. pr. II 10, 32 naturam accusa.")),
     "Vgl. CIC. Ac. pr. II 10, 32", ("direct", "Cicero", "Academica", "pr. II 10, 32")),
    # Leucippus A7, Parmenides B7
    ((("context", "ARISTOT. Phys. A 4. 187a 20 λόγος φησι. Zu ἁφή vgl. PHILOPON. de gen. et corr. p. 158, 26 οὐ λόγος."),),
     "Zu ἁφή vgl. PHILOPON. de gen. et corr. p. 158, 26", None),
    ((("context", "ARISTOT. Phys. A 4. 187a 20 λόγος. 42 vgl. SIMPL. Phys. 147, 13 εἴπερ λόγος."),),
     "42 vgl. SIMPL. Phys. 147, 13", ("direct", "Simplicius", "in Aristotelis Physica", "147, 13")),
])
def test_vgl_heading_takes_its_vgl(dictionary, lines, head, cite):
    heads = _located(dictionary, *lines)
    assert heads[-1]["text"] == head
    assert heads[-1]["expanded"][0]["verbatim"] == head
    if cite is not None:
        assert _cite(heads[-1]["expanded"][0]) == cite
    for h in heads:
        before = lines[h["lineIndex"]][1][:h["start"]].rstrip()
        assert not before.casefold().endswith("vgl.")


def test_vgl_after_a_head_moves_to_the_next(dictionary):
    # Heraclitus B99: the "vgl." belongs to the second source, not the first.
    heads = _located(dictionary, ("context", "PLUT. de fort. 2 λόγος. aqu. et ign. comp. 7 p. 957 A; vgl. de fort. 3. p. 98 C"),
                     ("text", "λόγος"))
    assert _texts(heads)[-2:] == ["aqu. et ign. comp. 7 p. 957 A;", "vgl. de fort. 3. p. 98 C"]


# 6. A lexicon DK cites with a colon quotes its entry: the headword after the
# colon is the locus (Heraclitus A1a "SUID: Ἡράκλειτος ...").
def test_lexicon_with_a_colon_is_cited_by_its_headword(dictionary):
    (h,) = _located(dictionary, ("context", "SUID: Ἡράκλειτος Βλόσωνος λόγος."))
    assert h["text"] == "SUID:"
    # The Suda is cited by its own name, not an author's: no separate title
    # repeats "Suda" (2026-09-27 fifth round).
    assert _cite(h["expanded"][0]) == ("direct", "Suda", "", "s.v. Ἡράκλειτος")
    # A head whose entry prints only the philosopher's initial names no
    # headword; with no locus at all, the bare head falls back to a title
    # ("Lexicon", as Hesychius' and Harpocration's own lexica are titled)
    # instead of a dangling comma. (Until 2026-09-28 the example was a Suda
    # life, "SUID. Ἡράκλειτος Βλόσωνος", whose name is its headword.)
    (h,) = _located(dictionary, ("context", "SUIDAS Ἀ. Πραξιάδου Μιλήσιος φιλόσοφος."))
    assert h["expanded"][0]["locus"] == ""
    assert h["expanded"][0]["work"]["title"] == "Lexicon"


def test_unclosed_angle_bracket_is_left_out_of_the_head(dictionary):
    # Heraclitus A17: "<" opens the editor's supplement to the quotation.
    (h,) = _located(dictionary, ("context", "AËT. IV 7, 2 (D. 392) <Ἡ. λόγος> λόγος."))
    assert h["text"] == "AËT. IV 7, 2 (D. 392)"


# 10. Title words the matched key left at the start of the locus.
@pytest.mark.parametrize("head,author,title,locus", [
    ("GAL. de elem. sec. Hipp. I 4 (I 443 K. 23, 1 Helmr.)", "Galen", "De Elementis ex Hippocrate",
     "I 4 (I 443 K. 23, 1 Helmr.)"),
    ("GALEN. ad Hippocr. Epid. VI 48 [XVII A p. 1002 K].", "Galen", "in Hippocratis Epidemiarum librum VI",
     "48 [XVII A p. 1002 K]"),
    ("[GALEN.] Hist. philos. 3", "pseudo-Galen", "Historia Philosopha", "3"),
    ("ARISTID. Ars rhet. II 15 Schm.", "Aelius Aristides", "Ars Rhetorica", "II 15 Schm."),
    ("EUDOX. Ars astron. coll. 22, 21 [p. 25 Blass]", "Eudoxus", "Ars Astronomica", "coll. 22, 21 [p. 25 Blass]"),
    ("HERACLIT. Alleg. Hom. c. 44", "Heraclitus (allegorista)", "Allegoriae Homericae", "c. 44"),
    ("HIEROCL. ad c. aur. 24", "Hierocles", "in Aureum Carmen (Commentarius)", "24"),
    ("LACTANT. Inst. Div. I 2", "Lactantius", "Divinae Institutiones", "I 2"),
    ("PHOT. Bibl. c. 249 p. 439a 36", "Photius", "Bibliotheca", "c. 249 p. 439a 36"),
    ("SEXT. Pyrrh. h. II 63", "Sextus Empiricus", "Pyrrhoniae Hypotyposes", "II 63"),
    ("THEOLOG. Arithm. p. 74, 10", "Theologumena Arithmeticae", "Theologumena Arithmeticae", "p. 74, 10"),
    ("SCHOL. APOLL. RHOD. B 1098", "Scholia in Apollonium Rhodium", "Scholia in Apollonium Rhodium", "B 1098"),
    ("SCHOL. ad DIONYS. Thrac. p. 168, 8 Hilgard", "Scholia", "Scholia in Dionysium Thracem", "p. 168, 8 Hilgard"),
    # Author words: "CLEM. AL.", "JOH. LYDUS", "MALL. THEODOR.", "RUFUS Ephes.".
    ("CLEM. AL. Strom. I 62 [II 39, 17 St.]", "Clement of Alexandria", "Stromata", "I 62 [II 39, 17 St.]"),
    ("JOH. LYDUS de mens. III 14", "John Lydus", "De Mensibus", "III 14"),
    ("MALL. THEODOR. de metr. VI 589, 20", "Mallius Theodorus", "De Metris", "VI 589, 20"),
    ("RUFUS Ephes. d. nom. part. hom. 229p. 166, 11 Daremb.", "Rufus of Ephesus",
     "De Nominatione Partium Hominis", "229p. 166, 11 Daremb."),
])
def test_locus_starts_after_the_title(dictionary, head, author, title, locus):
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)


def _columns(dictionary, *columns, rulings=None):
    """The located heads of consecutive columns; each column is a list of
    (role, text) lines, named X1, X2, ..."""
    segs = [{"id": f"1:X{c + 1}", "column": f"X{c + 1}",
             "lines": [{"n": i + 1, "role": role, "text": text} for i, (role, text) in enumerate(lines)]}
            for c, lines in enumerate(columns)]
    result = ce.resolve_located_segments(dictionary, segs, "fixture", rulings or {})
    return [result[s["id"]] for s in segs]


# 11. A place in the source above printed by numbers and its Diels page is a
# head of its own (rule E, a dash DK did not print).
def test_number_continuation_is_a_head(dictionary):
    # Heraclitus A10 (with its "II 1. 2" for II 1, 2), A12-style numbers.
    (heads,) = _columns(dictionary, [("context",
        "AËT. II 1. 2 (D. 327) λόγος κόσμον. 4, 3 (D. 331) λόγος. 11, 4 (D. 340) λόγος.")])
    assert _texts(heads) == ["AËT. II 1. 2 (D. 327)", "4, 3 (D. 331)", "11, 4 (D. 340)"]
    assert _cite(heads[1]["expanded"][0]) == ("dash", "Aëtius", "Placita", "II 4, 3")
    assert heads[1]["expanded"][0]["apparatus"] == "(D. 331)"
    assert heads[1]["expanded"][0]["verbatim"] == "4, 3 (D. 331)"
    assert _cite(heads[2]["expanded"][0]) == ("dash", "Aëtius", "Placita", "II 11, 4")
    assert "display" not in heads[1]


@pytest.mark.parametrize("text,heads", [
    # The head's own locus is no continuation (Anaxagoras A108).
    ("CENSOR. 6, 1 (D. 190;) λόγος.", ["CENSOR. 6, 1 (D. 190;)"]),
    # An author printed mid-sentence before them (Anaximander A17).
    ("SIMPL. Phys. 24, 13 λόγος ὡς δοκεῖ AËT. I 7, 12 (D. 302) λόγος.",
     ["SIMPL. Phys. 24, 13", "AËT. I 7, 12 (D. 302)"]),
    # A second place fused to the head above (Democritus A90), missing spaces
    # (Anaximenes A15, Melissus A9).
    ("AËT. II 25, 9 (D. 356) s. 59 A 77. 30, 3 (D. 361) λόγος.",
     ["AËT. II 25, 9 (D. 356) s. 59 A 77.", "30, 3 (D. 361)"]),
    ("AËT. II 22, 1 (D. 352) λόγος. 23, 1(D. 352) λόγος.", ["AËT. II 22, 1 (D. 352)", "23, 1(D. 352)"]),
])
def test_number_continuation_extent(dictionary, text, heads):
    (located,) = _columns(dictionary, [("context", text)])
    assert _texts(located) == heads


def test_number_continuation_opening_a_column(dictionary):
    # Anaximenes A14: the column opens "II 13, 10 (D. 342)" after A13's
    # Aëtius, DK's dash left out; it reads as the full citation.
    _, heads = _columns(dictionary, [("context", "AËT. II 11, 1 (D. 339) λόγος.")],
                        [("context", "II 13, 10 (D. 342) λόγος. 14, 3 (D. 344) λόγος.")])
    assert _texts(heads) == ["II 13, 10 (D. 342)", "14, 3 (D. 344)"]
    assert _cite(heads[1]["expanded"][0]) == ("dash", "Aëtius", "Placita", "II 14, 3")
    assert heads[0]["display"] == "AËT. II 13, 10 (D. 342)"


# 12-13. Each testimony or fragment starts with the full citation: the
# heading's `display`, and no dash on the English side.
def test_dash_heads_display_the_full_citation(dictionary):
    _, heads = _columns(dictionary, [("context", "AËT. II 13, 8 (D. 342) λόγος.")],
                        [("context", "—II 20, 16 (D. 351) λόγος."), ("context", "—22, 2 (D. 352) λόγος.")])
    assert [h["display"] for h in heads] == ["AËT. II 20, 16 (D. 351)", "22, 2 (D. 352)"]
    assert heads[0]["text"] == "—II 20, 16 (D. 351)"  # printed text and offsets unchanged


def test_dash_display_uses_the_adjudicated_reading(dictionary):
    # Democritus B32: John's reading puts the dash in Paed. II.
    ruling = {"head": "— —94 (I 214, 9 St.)", "reading": {
        "author": "CLEM", "work": "Paed.", "locus": "II 94", "apparatus": "(I 214, 9 St.)"}}
    _, heads = _columns(dictionary, [("context", "CLEM. Paed. I 6 λόγος.")],
                        [("context", "— —94 (I 214, 9 St.) λόγος.")], rulings={"X2": ruling})
    assert heads[0]["display"] == "CLEM. Paed. II 94 (I 214, 9 St.)"


def test_dash_waiting_on_the_print_keeps_its_locus_without_the_dash(dictionary):
    # Heraclitus A11: the reading waits on John's check of the print.
    ruling = {"head": "—II 13, 8 (D. 342)", "reading": None, "pending": "awaiting-print-check"}
    _, heads = _columns(dictionary, [("context", "AËT. II 1, 2 (D. 327) λόγος.")],
                        [("context", "—II 13, 8 (D. 342) λόγος.")], rulings={"X2": ruling})
    (e,) = heads[0]["expanded"]
    assert heads[0]["display"] == e["verbatim"] == "AËT. II 13, 8 (D. 342)"
    assert e["resolution"] == "verbatim" and e["flags"] == ["awaiting-print-check"]


def test_unresolved_dash_prints_no_dash(dictionary):
    # A dash with no source above it: the heading and the English side
    # print what follows the dash, and nothing when nothing does.
    (heads,) = _columns(dictionary, [("context", "—IV 9 λόγος.")])
    assert heads[0]["display"] == heads[0]["expanded"][0]["verbatim"] == "IV 9"
    (heads,) = _columns(dictionary, [("context", "— —"), ("text", "λόγος")])
    assert heads[0]["display"] == heads[0]["expanded"][0]["verbatim"] == ""


def test_full_citation_head_gets_no_display(dictionary):
    (heads,) = _columns(dictionary, [("context", "AËT. II 13, 8 (D. 342) λόγος.")])
    assert "display" not in heads[0]


# 14. Galen, from a hand check of all 30 heads.
@pytest.mark.parametrize("head,author,title,locus", [
    ("GAL. de usu partt. III 10 (III 241 K., I 177, 10 Helmr.)", "Galen", "De Usu Partium",
     "III 10 (III 241 K., I 177, 10 Helmr.)"),
    ("GAL. comment. in Hippocr. de offic. I 1", "Galen", "in Hippocratis De Officina Medici", "I 1"),
    ("GAL. in Hipp. de med. off. XVIII B 656 K.", "Galen", "in Hippocratis De Officina Medici", "XVIII B 656 K."),
    ("GALEN. in Hipp. d. nat. h. XV 25 K.", "Galen", "in Hippocratis De Natura Hominis", "XV 25 K."),
    ("GAL. Hist. phil. 3 (D. 599)", "pseudo-Galen", "Historia Philosopha", "3"),
    # No title printed: John's ruling of 2026-09-29 fills the one the TLG
    # confirms (Democritus A46; 0057.060, Kühn VIII 931).
    ("GALEN. VIII 931 K.", "Galen", "De Dignoscendis Pulsibus", "VIII 931 K."),
])
def test_galen_titles(dictionary, head, author, title, locus):
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)


def test_galen_a_o_is_the_place_cited_above(dictionary):
    # Critias B39-B40, Antiphon B1-B2: "a. O." (am angegebenen Ort).
    _, heads = _columns(dictionary, [("context", "GAL. comment. in Hippocr. de offic. I 1 λόγος.")],
                        [("context", "GAL. a. O. καὶ λόγος.")])
    assert _texts(heads) == ["GAL. a. O."]
    assert _cite(heads[0]["expanded"][0]) == ("direct", "Galen", "in Hippocratis De Officina Medici", "I 1")
    _, heads = _columns(dictionary, [("context", "GAL. in Hipp. de med. off. XVIII B 656 K. λόγος.")],
                        [("context", "GAL. in Hipp. de med. off. a. O. καί· λόγος.")])
    assert _texts(heads) == ["GAL. in Hipp. de med. off. a. O."]
    assert heads[0]["expanded"][0]["locus"] == "XVIII B 656 K."


# --- Second round of 2026-09-27 (Grok sample check, "(work of ...)" list) ----

def test_round2_hipp_names_hippocrates_before_a_hippocratic_title(dictionary):
    # Democritus B11 "Vgl. HIPP. de arte 11"; Empedocles B29 "HIPP. Ref."
    for head, cite in {
        "HIPP. de arte 11": ("direct", "Hippocrates (corpus)", "De Arte", "11"),
        "HIPP. de nat. hom. 1 [VI 34 L.]": ("direct", "Hippocrates (corpus)", "De Natura Hominis", "1 [VI 34 L.]"),
        "HIPP. Ref. VII 29 (p. 212 W.)": ("direct", "Hippolytus", "Refutatio Omnium Haeresium", "VII 29 (p. 212 W.)"),
    }.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _cite(e) == cite, head


def test_round2_column_and_section_letters_stay_in_the_locus(dictionary):
    for head, locus in {
        "ATHEN. IV 157 c": "IV 157 c",                              # Philolaus B14
        "ATHEN. X 413 F nach 21 C 2:": "X 413 F",                   # Xenophanes B2
        "PLUT. de Isid. 361 c": "361 c",                            # Empedocles B115
        "STOB. Ecl. I 21, 7 a [p. 187, 14 Wachsm.]": "I 21, 7 a [p. 187, 14 Wachsm.]",  # Philolaus B2
        "AËT. v 19, 5 (D. 430)": "V 19, 5",                         # Empedocles A72, read as V
    }.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert e["locus"] == locus, head


def test_round2_papyri_print_the_collection_without_an_author(dictionary):
    (e,) = ce._resolve_head(dictionary, "PAP. HERC. 1788", "w", "s")  # Pythagoras 13
    assert "authorDisplay" not in e and (e["work"]["title"], e["locus"]) == ("Herculaneum Papyrus", "1788")
    (e,) = ce._resolve_head(dictionary, "OXYRH. PAP. XI n. 1364.", "w", "s")  # Antiphon B44
    assert (e["work"]["title"], e["locus"]) == ("Oxyrhynchus Papyrus", "XI n. 1364.")


def test_round2_titles_that_fell_to_placeholders(dictionary):
    for head, (author, title) in {
        "PLUT. Sol. 12": ("Plutarch", "Solon"),
        "PHILOSTR. V. S. I 9, 1ff.": ("Philostratus", "Vitae Sophistarum"),
        "SENEC. Nat. Qu. II 18": ("Seneca", "Naturales Quaestiones"),
        "PORPHYR. V. P. 9": ("Porphyry", "Vita Pythagorae"),
        "IAMBL. V. Pythag. 12": ("Iamblichus", "De Vita Pythagorica"),
        "LACTANT. de opif. 12, 12": ("Lactantius", "De Opificio Dei"),
        "PLAT. Hipp. m. 283 A": ("Plato", "Hippias Maior"),
        "GALEN. d. natur. facult. II 8": ("Galen", "De Naturalibus Facultatibus"),
        "EUSTATH. Z. DIONYS. Per. 270": ("Eustathius", "Commentarii in Dionysium Periegetam"),
        "DIONYS. bei Eus. P. E. XIV 23, 2. 3": ("Dionysius of Alexandria", "De Natura"),
    }.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert (e["authorDisplay"], e["work"]["title"]) == (author, title), head


def test_round2_authors_a_column_opens_with(dictionary):
    for line, text in {
        "ACHILL. Isag. 1, 13 p. 40, 26 M. τοὺς ἀστέρας": "ACHILL. Isag. 1, 13 p. 40, 26 M.",
        "LYS. 12, 43 ἐπειδὴ δὲ": "LYS. 12, 43",
        "[GALEN]. d. defin. med. 439 [XIX 449 K.] ἐκκρίνεται": "[GALEN]. d. defin. med. 439 [XIX 449 K.]",
        "VIT. HOMERI Rom. p. 30, 27 Wil. Ἱ. δ' αὖ": "VIT. HOMERI Rom. p. 30, 27 Wil.",
        "CLAUD. MAM. II 3 p. 105, 5 Engelbr. Pythagorae igitur, quia": "CLAUD. MAM. II 3 p. 105, 5 Engelbr.",
        "BOËTHIUS Inst. mus. III 5 p. 276, 15 Friedl. Ph. vero Pythagoricus": "BOËTHIUS Inst. mus. III 5 p. 276, 15 Friedl.",
    }.items():
        (h,) = _located(dictionary, ("context", line))
        assert h["text"] == text and h["expanded"][0]["resolution"] == "direct", line


def test_round2_heads_end_before_the_quotation(dictionary):
    for line, text in {
        # Anaxagoras A109, A91; Leucippus A11, A8; Democritus A92; Zeno A20.
        "—6, 2 sunt qui aetherium calorem inesse arbitrentur": "—6, 2",
        "SEN. Nat. qu. IV a 2, 17 A. ait ex Aethiopiae. Dagegen HEROD. II 22": "SEN. Nat. qu. IV a 2, 17",
        "CIC. Acad. pr. II 37, 118 (D. 119) L. plenum et inane.": "CIC. Acad. pr. II 37, 118 (D. 119)",
        "SEN. Nat. quaest. VII 3, 2 D. quoque, subtilissimus": "SEN. Nat. quaest. VII 3, 2",
        "QUINTIL. III 1, 10 Abderites P., a quo decem": "QUINTIL. III 1, 10",
        "TERTULL. de an. 51 Plato ... in Politia tamen": "TERTULL. de an. 51",
        "STOB. Flor. (III) t. 7, 37 H. Z. ὁ Ἐλεάτης": "STOB. Flor. (III) t. 7, 37 H.",
        "ALBERTUS M. de veget. VI 401 p. 545 Meyer H. dixit quod": "ALBERTUS M. de veget. VI 401 p. 545 Meyer",
    }.items():
        heads = _located(dictionary, ("context", line))
        assert heads[0]["text"] == text, line


def test_round2_greek_initial_with_a_comma_ends_the_head(dictionary):
    (h,) = _located(dictionary, ("context", "AËT. II 16, 1 (D. 345) Ἀ., Δημόκριτος"))  # Anaxagoras A78
    assert h["text"] == "AËT. II 16, 1 (D. 345)"


def test_round2_ibidem_and_pageless_places_in_aetius(dictionary):
    # Anaximander A17 "ib. 8 (D. 329)"; Heraclitus A8 "28, 1 Ἡ."; Empedocles
    # A90 "9, 6 [28 A 47]."; Xenophanes A43 "II 28, 1 [D. 358]".
    (heads,) = _columns(dictionary, [("context",
        "AËT. II 1, 3 (D. 327) Ἀ. ἀπείρους. ib. 8 (D. 329) τῶν ἀπείρους. 28, 1 Ἡ. οὐσίαν."
        " 9, 6 [28 A 47]. II 28, 1 [D. 358] Ἀναξίμανδρος.")])
    assert [(h["text"], h["expanded"][0]["locus"]) for h in heads] == [
        ("AËT. II 1, 3 (D. 327)", "II 1, 3"), ("ib. 8 (D. 329)", "II 1, 8"),
        ("28, 1", "II 28, 1"), ("9, 6", "II 9, 6"), ("II 28, 1 [D. 358]", "II 28, 1 [D. 358]")]


def test_round2_numbers_after_an_unknown_author_are_no_head(dictionary):
    # Democritus A4 "CHRON. PASCH. 317, 5 Δ." and Empedocles A97 "vgl.
    # Theodor. V 22 Ἐ.": numbers without a Diels page after an abbreviation.
    (heads,) = _columns(dictionary, [("context",
        "AËT. IV 5, 1 (D. 391) Ἱπποκράτης. CHRON. PASCH. 317, 5 Δ. τελευτᾶι. vgl. Theodor. V 22 Ἐ. κτλ.")])
    assert _texts(heads) == ["AËT. IV 5, 1 (D. 391)"]


def test_round2_aetius_chapter_title_is_in_the_head(dictionary):
    (h,) = _located(dictionary, ("context", "AËT. II 20, 15 (D. 351) (περὶ οὐσίας ἡλίου) Ἀ. πῦρ"))  # Antiphon B26
    assert h["text"] == "AËT. II 20, 15 (D. 351) (περὶ οὐσίας ἡλίου)"
    (h,) = _located(dictionary, ("context", "AËT. II 24, 3 (D. 354) (γίνεσθαι τὴν ἔκλειψιν) κατὰ"))  # Heraclitus A12
    assert h["text"] == "AËT. II 24, 3 (D. 354)"


def test_round2_odyssey_book_letter_is_in_the_head(dictionary):
    # Democritus B24 -> B25: "—Zu μ 62 p. 1713" after "EUSTATH. Zu ο 376 p. 1784".
    b24, b25 = _columns(dictionary,
        [("context", "EUSTATH. Zu ο 376 p. 1784 ἰστέον δὲ")],
        [("context", "—Zu μ 62 p. 1713 ἄλλοι δὲ Δία")])
    assert b24[0]["text"] == "EUSTATH. Zu ο 376 p. 1784"
    assert b25[0]["text"] == "—Zu μ 62 p. 1713"
    assert _cite(b25[0]["expanded"][0]) == ("dash", "Eustathius", "Commentarii ad Homerum", "μ 62 p. 1713")
    assert b25[0]["display"] == "EUSTATH. Zu μ 62 p. 1713"


def test_round2_same_place_first_head_shows_the_place(dictionary):
    # Critias B39 -> B40 "GAL. a. O."; Antiphon B1 -> B2.
    b39, b40 = _columns(dictionary,
        [("context", "GAL. comment. in Hippocr. de offic. I 1 λόγος")],
        [("context", "GAL. a. O. καὶ ἐν")])
    assert b40[0]["display"] == "GAL. comment. in Hippocr. de offic. I 1"
    b1, b2 = _columns(dictionary,
        [("context", "GAL. in Hipp. de med. off. XVIII B 656 K. ὥσπερ")],
        [("context", "GAL. in Hipp. de med. off. a. O. καί·")])
    assert b2[0]["display"] == "GAL. in Hipp. de med. off. XVIII B 656 K."


def test_round2_numbers_after_a_source_named_in_the_column_continue_it(dictionary):
    # Protagoras A23: a Plato dash heads the column; "12, 29 (D. 535)"
    # (a page the table gives no owner) continues the Cicero printed before it.
    (heads,) = _columns(dictionary, [("context", "PLATO Theaet. 162 D ὦ γενναῖοι ἐξαιρῶ."
        " CIC. de nat. deor. I 24, 63 Abderites quidem est exterminatus. 12, 29 (D. 535) nec vero P.")])
    e = heads[-1]["expanded"][0]
    assert (heads[-1]["text"], _cite(e), e["apparatus"]) == (
        "12, 29 (D. 535)", ("dash", "Cicero", "De Natura Deorum", "I 12, 29"), "(D. 535)")


def test_round2_a_ruling_matches_its_head_without_the_greek_initial(dictionary):
    # Thales A17b: the ruling's head prints "Θ.", the located head leaves it
    # to the passage; the correction still applies.
    rulings = {"X2": {"head": "—II 27, 5 (D. 358) Θ.", "type": "correction", "printed": "II 27, 5",
                      "reading": {"author": "AET", "work": "DEFAULT", "locus": "II 28, 5", "apparatus": "(D. 358)"},
                      "readerNote": "DK prints “II 27, 5”.", "note": "x"}}
    _, x2 = _columns(dictionary, [("context", "AËT. II 24, 1 (D. 353) Θ. πρῶτος")],
                     [("context", "—II 27, 5 (D. 358) Θ. πρῶτος")], rulings=rulings)
    assert x2[0]["text"] == "—II 27, 5 (D. 358)"
    assert x2[0]["expanded"][0]["locus"] == "II 28, 5" and "corrected" in x2[0]["expanded"][0]["flags"]


# --- 2026-09-27, third round (Grok check; the second round's leftovers) ----

@pytest.mark.parametrize("line,texts", [
    # Xenophanes B34, Democritus B116, Gorgias A25, Heraclitus B5: DK lists
    # a second source straight after the first one's locus.
    ("SEXT. adv. math. VII 49. 110 PLUT. aud. poet. 2 p. 17 E καὶ τὸ μὲν",
     ["SEXT. adv. math. VII 49. 110", "PLUT. aud. poet. 2 p. 17 E"]),
    ("DIOG. IX 36 CIC. Tusc. v 36, 104 intellegendum est igitur",
     ["DIOG. IX 36", "CIC. Tusc. v 36, 104"]),
    ("PLATO Phaedr. p. 267A CIC. Brut. 12, 47 communes loci",
     ["PLATO Phaedr. p. 267A", "CIC. Brut. 12, 47"]),
    ("ARISTOCRITUS Theosophia 68 (Buresch Klaros S. 118), ORIG. c. CELS. VII 62",
     ["ARISTOCRITUS Theosophia 68 (Buresch Klaros S. 118),", "ORIG. c. CELS. VII 62"]),
    # Parmenides B1, B7: a verse range before the source.
    ("1—30 SEXT. VII 111ff. ὁ δὲ γνώριμος", ["SEXT. VII 111ff."]),
    # "bei Simpl." is a note inside the citation, not a second source.
    ("EUDEM. bei Simpl. Phys. 143, 4 ὥστε οὐδὲ", ["EUDEM. bei Simpl. Phys. 143, 4"]),
])
def test_round3_a_second_source_after_a_locus_is_its_own_head(dictionary, line, texts):
    assert _texts(_located(dictionary, ("context", line))) == texts


def test_round3_a_listed_source_resolves_alone(dictionary):
    heads = _located(dictionary, ("context", "SEXT. adv. math. VII 49. 110 PLUT. aud. poet. 2 p. 17 E καὶ"))
    assert [_cite(h["expanded"][0]) for h in heads] == [
        ("direct", "Sextus Empiricus", "Adversus Mathematicos", "VII 49. 110"),
        ("direct", "Plutarch", "Quomodo Adulescens Poetas Audire Debeat", "2 p. 17 E")]
    assert all(len(h["expanded"]) == 1 for h in heads)


def test_round3_a_letter_title_and_its_place_are_in_the_head(dictionary):
    # Antiphon B44a: the letter's Greek title and Stobaeus' place.
    heads = _located(dictionary, ("context",
        "οἰκηθείη. IAMBL. Ep. Περὶ ὁμονοίας [Stob. II 33, 15] ἡ ὁμόνοια, καθάπερ"))
    assert _texts(heads) == ["IAMBL. Ep. Περὶ ὁμονοίας [Stob. II 33, 15]"]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Iamblichus", "Epistulae", "Περὶ ὁμονοίας [Stob. II 33, 15]")
    # A Greek title with no place after it is the quotation's.
    (h,) = _located(dictionary, ("context", "IAMBL. Ep. Περὶ ὁμονοίας ἡ ὁμόνοια"))
    assert h["text"] == "IAMBL. Ep."
    # DK's section label after the place opens the passage (Antiphon B81a).
    (h,) = _located(dictionary, ("context", "MELAMPUS Περὶ παλμῶν 18. 19 [Diels Beitr.] (18) ἐὰν"))
    assert h["text"] == "MELAMPUS Περὶ παλμῶν 18. 19 [Diels Beitr.]"


def test_round3_parmenides_b7_physics_heads(dictionary):
    # Each "Phys." is its printed author's (the export's "SIbmPL." is SIMPL.),
    # not Eudemus', whose citation stands before them.
    heads = _located(dictionary, ("context",
        "8, 1—52 SIMPL. Phys. 144, 29 [nach 28 A 21] ὡς ... EUDEM. bei Simpl. Phys. 143, 4 ὥστε ..."
        " 44 ARIST. Phys. Γ 6. 207a 15 οὐ γὰρ ... 50—61 SIbmPL. Phys. 38, 28 καὶ ..."
        " 50—59 SIMPL. Phys. 30, 13 μετελθὼν ..."))
    assert [(h["text"], _cite(h["expanded"][0])[1:3]) for h in heads if h["expanded"][0]["resolution"] != "verbatim"] == [
        ("SIMPL. Phys. 144, 29 [nach 28 A 21]", ("Simplicius", "in Aristotelis Physica")),
        ("EUDEM. bei Simpl. Phys. 143, 4", ("Eudemus of Rhodes", "")),
        ("ARIST. Phys. Γ 6. 207a 15", ("Aristotle", "Physica")),
        ("SIbmPL. Phys. 38, 28", ("Simplicius", "in Aristotelis Physica")),
        ("SIMPL. Phys. 30, 13", ("Simplicius", "in Aristotelis Physica"))]


def test_round3_a_filled_in_locus_drops_the_book_comma(dictionary):
    # Heraclitus A8 "I, 27, 1 (D. 322) Ἡ. ... 28, 1 Ἡ. ..."
    (heads,) = _columns(dictionary, [("context",
        "AËT. I 7. 22 (D. 303) Ἡ. τὸ περιοδικὸν. I, 27, 1 (D. 322) Ἡ. πάντα. 28, 1 Ἡ. οὐσίαν.")])
    assert [(h["text"], h["expanded"][0]["locus"]) for h in heads][1:] == [
        ("I, 27, 1 (D. 322)", "I, 27, 1"), ("28, 1", "I 28, 1")]
    assert ce._replace_trailing("I, 27, 1", "28, 1") == "I 28, 1"


def test_round3_heads_end_before_the_quotation(dictionary):
    for line, (text, locus) in {
        # Leucippus A3 (Diogenes of Apollonia), Melissus A4 (the export's "3o
        # M." for ὁ Μ.), Democritus B307 (a leaf's side, then Latin).
        "SIMPL. Phys. 25, 2 Diogenes V. Ap. τὰ μὲν πλεῖστα": ("SIMPL. Phys. 25, 2", "25, 2"),
        "SIMPL. Phys. 70, 16 3o M. καὶ τὴν ἐπιγραφὴν": ("SIMPL. Phys. 70, 16", "70, 16"),
        "PSEUDORIBASIUS in Aphorism. Hippocr. ed. Io. Guinterius Andernacus Paris. 1533f. 5 v deinde dicimus quod":
            ("PSEUDORIBASIUS in Aphorism. Hippocr. ed. Io. Guinterius Andernacus Paris. 1533f. 5 v",
             "ed. Io. Guinterius Andernacus Paris. 1533f. 5 v"),
    }.items():
        heads = _located(dictionary, ("context", line))
        assert (heads[0]["text"], heads[0]["expanded"][0]["locus"]) == (text, locus), line
    # A garbled 30 before a bracket stays in the locus (Empedocles B111).
    (e,) = ce._resolve_head(dictionary, "CLEM. Strom. VI 3o [II 445, 16 St.]", "w", "s")
    assert e["locus"] == "VI 3o [II 445, 16 St.]"


def test_round3_loci_that_were_cut_short(dictionary):
    for head, cite in {
        "IULIAN. Ep. 201 B.—C.": ("direct", "Julian (imp.)", "Epistulae", "201 B.—C."),  # Democritus A20
        "SCHOL. HIPPOCR. ad Epid. I 13, 3 [Nachmanson, Erotian. p. 102, 19]":            # Xenophanes B45
            ("direct", "Scholia in Hippocratem", "Epidemiae", "I 13, 3 [Nachmanson, Erotian. p. 102, 19]"),
        "STOB. Ecl. I 15, 2ab [I 144, 20 W.]":                                           # Empedocles B28
            ("direct", "Stobaeus", "Eclogae (Anthologii libri I-II)", "I 15, 2ab [I 144, 20 W.]"),
        "SIMPL. d. cael. 557, 20": ("direct", "Simplicius", "in Aristotelis De Caelo", "557, 20"),  # Parmenides B1
    }.items():
        (e,) = ce._resolve_head(dictionary, head, "w", "s")
        assert _cite(e) == cite, head


def test_round3_mixed_case_simplicius_opens_a_source_before_a_title(dictionary):
    # Anaximander A17 "κόσμον. Simpl. Phys. 1121, 5 οἱ μὲν"
    heads = _located(dictionary, ("context",
        "AËT. II 1, 3 (D. 327) Ἀ. φθαρτὸν τὸν κόσμον. Simpl. Phys. 1121, 5 οἱ μὲν γὰρ"))
    assert _texts(heads) == ["AËT. II 1, 3 (D. 327)", "Simpl. Phys. 1121, 5"]
    assert _cite(heads[1]["expanded"][0]) == ("direct", "Simplicius", "in Aristotelis Physica", "1121, 5")


def test_round3_dash_with_a_section_number_after_a_preserving_text(dictionary):
    # Democritus B118 -> B119 "— —(5)": Eusebius' next section.
    _, b119 = _columns(dictionary,
        [("context", "DIONYSIOS, bei Eus. P. E. XIV 27, 4 ὁ γοῦν")],
        [("context", "— —(5)"), ("text", "ἄνθρωποι τύχης εἴδωλον")])
    e = b119[0]["expanded"][0]
    assert (e["resolution"], e["authorDisplay"], e["locus"], e["apparatus"]) == (
        "dash", "Dionysius of Alexandria", "", "bei Eus. P. E. XIV 27, 5")
    assert b119[0]["display"] == "DIONYSIOS, bei Eus. P. E. XIV 27, 5"


def test_round3_oribasius_is_a_source(dictionary):
    # Empedocles A83: "... δεούσης. ORIBASIUS aus Athenaios III 78, 13 [...]"
    heads = _located(dictionary, ("context",
        "AËT. V 21, 1 (D. 433) Ἐ. ἀπὸ πεντηκοστῆς μιᾶς δεούσης. ORIBASIUS aus Athenaios III 78, 13"
        " [Diokles fr. 175 Wellm.] περὶ δὲ τὰς"))
    assert _texts(heads)[1] == "ORIBASIUS aus Athenaios III 78, 13 [Diokles fr. 175 Wellm.]"
    e = heads[1]["expanded"][0]
    assert (e["authorDisplay"], e["work"]["title"]) == ("Oribasius", "Collectiones Medicae")


def test_round3_compare_page_of_the_same_work_is_in_the_head(dictionary):
    # Parmenides B7 "7, 1—2 PLATO Soph. 237 A vgl. 258D Π. δὲ ὁ μέγας"
    heads = _located(dictionary, ("context", "7, 1—2 PLATO Soph. 237 A vgl. 258D Π. δὲ ὁ μέγας"))
    assert _texts(heads) == ["PLATO Soph. 237 A vgl. 258D"]
    assert heads[0]["expanded"][0]["locus"] == "237 A"


# --- Grok content-review of round 3 (2026-09-27) ----------------------------

def test_round4_greek_titles_with_no_latin_on_record_stay_greek(dictionary):
    # Antiphon B81a, Empedocles B41, Xenophanes A49 (items 3, 15, 43): DK
    # prints a Greek title for a work with no Latin title on record -- the
    # English keeps it as printed rather than a placeholder, never inventing
    # a Latin one.
    (h,) = _located(dictionary, ("context",
        "τύχης. MELAMPUS Περὶ παλμῶν 18. 19 [Diels Beitr. z. Zuckungsl. I, Abh. d. Berl. Ak. 1907] ὀφθαλμὸς"))
    assert _cite(h["expanded"][0]) == (
        "direct", "Melampus", "Περὶ παλμῶν",
        "18. 19 [Diels Beitr. z. Zuckungsl. I, Abh. d. Berl. Ak. 1907]")
    (h,) = _located(dictionary, ("context", "APOLLODOROS Περὶ θεῶν bei Macrob. Sat. I 17, 46 τοῦτο"))
    e = h["expanded"][0]
    assert (e["authorDisplay"], e["work"]["title"], e["locus"], e["apparatus"]) == (
        "Apollodorus", "Περὶ θεῶν", "", "bei Macrob. Sat. I 17, 46")
    (h,) = _located(dictionary, ("context", "ARISTOCLES Περὶ φιλοσοφίας η [EUS. XIV 17, 1] οἴονται"))
    assert _cite(h["expanded"][0]) == (
        "direct", "Aristocles", "Περὶ φιλοσοφίας", "η [EUS. XIV 17, 1]")


def test_round4_vgl_zu_locus_is_in_the_head(dictionary):
    # Democritus A68 (item 9): the cross-reference clause "Vgl. zu 196b 14"
    # (Aristotle's own passage Simplicius comments on) is Simplicius' head,
    # not left dangling on the passage above it; the English still drops the
    # "Vgl." lead, as it does with every other one.
    heads = _located(dictionary, ("context", "τύχης. Vgl. zu 196b 14 SIMPL. p. 330, 14 τὸ δὲ"))
    assert _texts(heads) == ["Vgl. zu 196b 14 SIMPL. p. 330, 14"]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Simplicius", "(commentary on Aristotle)", "p. 330, 14")


def test_round4_verse_numbers_before_a_second_source_are_no_ones_locus(dictionary):
    # Empedocles B12 (item 11): "1. 2" numbers the verses PHILO's own
    # citation attests, not a continuation of ps.-Aristotle's page.
    heads = _located(dictionary, ("context",
        "[ARISTOT.] de MXG 2, 6 p. 975b 1. 1. 2 PHILO de aetern. mundi 2 p. 3, 5 Cum. ὥσπερ"))
    assert _texts(heads) == [
        "[ARISTOT.] de MXG 2, 6 p. 975b 1.",
        "PHILO de aetern. mundi 2 p. 3, 5 Cum."]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "pseudo-Aristotle", "De Melisso Xenophane Gorgia", "2, 6 p. 975b 1.")
    assert _cite(heads[1]["expanded"][0]) == (
        "direct", "Philo of Alexandria", "De Aeternitate Mundi", "2 p. 3, 5 Cum.")


def test_round4_compare_page_apparatus_is_kept(dictionary):
    # Parmenides B7 (item 27): the head's own "vgl. 258D" (already part of
    # the head since round 3) is apparatus, not dropped from the English.
    heads = _located(dictionary, ("context", "7, 1—2 PLATO Soph. 237 A vgl. 258D Π. δὲ ὁ μέγας"))
    e = heads[0]["expanded"][0]
    assert (e["locus"], e["apparatus"]) == ("237 A", "vgl. 258D")


def test_round5_zosim_mid_line_after_harpocration(dictionary):
    # Hippias A3: DK's "ZOSIM. V. Isocr. p. 253, 4 Westerm." sits mid-line,
    # right after HARPOCR.'s own sentence -- before the dictionary knew
    # "ZOSIM.", this fell to Harpocration's head instead of getting its own
    # (2026-09-27).
    heads = _located(dictionary, ("context",
        "ἐνομίζετο δὲ Ἰσοκράτους. ZOSIM. V. Isocr. p. 253, 4 Westerm. γυναῖκα δ' ἠγάγετο"))
    assert _texts(heads) == ["ZOSIM. V. Isocr. p. 253, 4 Westerm."]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Zosimus", "Vita Isocratis", "p. 253, 4 Westerm.")


def test_round5_hes_mid_line_is_hesychius_short_form(dictionary):
    # Antiphon B43: DK's "HES." -- Hesychius' short form, distinct from his
    # usual "HESYCH." -- sits mid-line after HARPOCR.'s own lemma entry for
    # the same headword; before this it fell to Harpocration's head
    # (2026-09-27). Its own headword "ἄβιος" prints alone on the next
    # display line, split from the ":" that introduces its gloss, which
    # lands on a THIRD line still ("HES." / "ἄβιος" / ": πλούσιος ...") --
    # the lemma-completion path (as SUID's/HARPOCR's own "s.v." heads use)
    # reads across that split to the real printed "s.v. ἄβιος".
    heads = _located(dictionary,
        ("context", "τὴν πολύξυλον. HES."),
        ("text", "ἄβιος"),
        ("context", ": πλούσιος ὡς Ἀ. ἐν Ἀληθείαι."))
    assert _texts(heads) == ["HES."]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Hesychius", "Lexicon", "s.v. ἄβιος")


def test_round5_suid_same_line_headword_wins_over_lookahead(dictionary):
    # Antiphon B115: "SUID. ἀπόκριναι: ... καὶ" / "ἀπόκρισις" / "ἡ ἀπολογία.
    # ...". Unlike B43's "HES.", SUID's own headword "ἀπόκριναι" is right
    # there on the SAME printed line as the head, before its ":" -- the
    # display line after it ("ἀπόκρισις", itself a bare word DK's own text
    # happens to print next) is a different word entirely, inside the
    # gloss, not the entry's headword. A same-line "word :" must always win
    # over the next-line lookahead built for B43; independent-check catch,
    # 2026-09-27.
    heads = _located(dictionary,
        ("context", "SUID. ἀπόκριναι: ... καὶ"),
        ("text", "ἀπόκρισις"),
        ("context", "ἡ ἀπολογία. οὕτως Λυσίας [fr. 305 O. A. II 214a 23] καὶ Ἀ."))
    assert _texts(heads) == ["SUID."]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Suda", "", "s.v. ἀπόκριναι")


# --- 2026-09-28: Grok check of 150 heads -------------------------------------

def test_round6_lexicon_headword_after_the_greek_colon_u0387(dictionary):
    # Antiphon B55: the export prints the colon after a headword as U+0387,
    # which NFC folds to the "·" the lemma rule reads; the text after a head
    # was matched un-normalized, so "PHOT. ἵνα· ὅπου" named no headword.
    heads = _located(dictionary, ("context", "PHOT. ἵνα· ὅπου. Ἀ."))
    assert _texts(heads) == ["PHOT."]
    assert _cite(heads[0]["expanded"][0]) == ("direct", "Photius", "Lexicon", "s.v. ἵνα")


@pytest.mark.parametrize("line,headword", [
    ("SUID. Καλλίμαχος. Πίναξ τῶν Δημοκρίτου γλωσσῶν.", "Καλλίμαχος"),  # Democritus A32
    ("ETYM. GENUIN. γλαύξ ... ἔστι γὰρ ὀξυωπέστατον τὸ ζῶιον.", "γλαύξ"),  # Democritus A157
    ("SUID. Δημόκριτος [A 2; II 85, 2]. γνήσια δὲ αὐτοῦ.", "Δημόκριτος"),  # Democritus A31
    ("SUIDAS Ἀναξιμένης Εὐρυστράτου Μιλήσιος φιλόσοφος.", "Ἀναξιμένης"),  # Anaximenes A2
    ("HARPOCR. Ἀφαρεύς. οὗτος Ἱππίου μὲν ἦν υἱός.", "Ἀφαρεύς"),  # Hippias A3
])
def test_round6_lexicon_entry_names_its_headword(dictionary, line, headword):
    (h,) = _located(dictionary, ("context", line))
    assert h["expanded"][0]["locus"] == f"s.v. {headword}"


@pytest.mark.parametrize("line", [
    "HARPOCR. Ἀ. σοφιστὴς Ἡγησιβούλου υἱὸς.",  # Anaxagoras A2: DK's initial, not the headword
    "SUID. Ἀ.... διάπυρον, τουτέστι πύρινον λίθον.",  # Anaxagoras A3
])
def test_round6_lexicon_initial_is_no_headword(dictionary, line):
    (h,) = _located(dictionary, ("context", line))
    assert h["expanded"][0]["locus"] == ""


def test_round6_lexicon_bracket_note_keeps_the_headword(dictionary):
    # Antiphon B22: the bracketed note is apparatus; the headword is on the
    # next line.
    heads = _located(dictionary, ("context", "HARPOCR. [vgl. PHOT. A Reitzenst. 37, 18]"),
                     ("text", "ἀειεστώ· Ἀ. ἐν Ἀληθείας δευτέρωι"))
    (e,) = heads[0]["expanded"]
    assert _cite(e) == ("direct", "Harpocration", "Lexicon in Decem Oratores", "s.v. ἀειεστώ")
    assert e["apparatus"] == "[vgl. PHOT. A Reitzenst. 37, 18]"


def test_round6_dash_compare_place_with_book_and_page_is_apparatus(dictionary):
    # Heraclitus B29: "vgl. IV 50 (II 271, 17)" was dropped from the English
    # and the heading.
    (_, heads) = _columns(dictionary, [("context", "CLEM. Strom. V 59 (II 366, 1) λόγος.")],
                          [("context", "— — —60 (II 366, 11) vgl. IV 50 (II 271, 17)"), ("text", "λόγος")])
    (e,) = heads[0]["expanded"]
    assert (e["locus"], e["apparatus"]) == ("V 60 (II 366, 11)", "vgl. IV 50 (II 271, 17)")
    assert heads[0]["display"] == "CLEM. Strom. V 60 (II 366, 11) vgl. IV 50 (II 271, 17)"


def test_round6_two_editors_joined_by_a_dash_end_the_head(dictionary):
    # Critias B49: Usener-Radermacher's edition, printed "Us.—Rad.".
    heads = _located(dictionary, ("context",
        "PSEUDODIONYS. Ars rhet. 6 II 277, 10 Us.—Rad. ἀνθρώπωι γὰρ γενομένωι"))
    assert _texts(heads) == ["PSEUDODIONYS. Ars rhet. 6 II 277, 10 Us.—Rad."]
    assert heads[0]["expanded"][0]["locus"] == "6 II 277, 10 Us.—Rad."


@pytest.mark.parametrize("above,dash,author,title,locus", [
    ("GALEN. de medic. empir. fr. ed. H. Schöne [Berl. Sitz. Ber. 1901] 1259, 8",
     "—de differ. puls. I 25 [VIII 551 K]", "Galen", "De Differentia Pulsuum", "I 25 [VIII 551 K]"),
    ("PHILO de prov. II 13 p. 52 Aucher.", "—de vita contempl. p. 473 M. (VI 49 C.—W.)",
     "Philo of Alexandria", "De Vita Contemplativa", "p. 473 M. (VI 49 C.—W.)"),
    ("THEOPHR. d. c. pl. VI 7, 2", "—de odor. 64", "Theophrastus", "De Odoribus", "64"),
    ("PROCL. Vit. Hom. p. 26, 14 Wil.", "—in Hes. Opp. 758", "Proclus", "in Hesiodi Opera et Dies", "758"),
])
def test_round6_formerly_excluded_dash_titles_resolve(dictionary, above, dash, author, title, locus):
    (_, heads) = _columns(dictionary, [("context", above + " λόγος.")], [("context", dash), ("text", "λόγος")])
    assert _cite(heads[0]["expanded"][0]) == ("dash", author, title, locus)


@pytest.mark.parametrize("head,author,title,locus", [
    ("HIEROCL. in Pyth. c. aur. 25", "Hierocles", "in Aureum Carmen (Commentarius)", "25"),
    ("APUL. Apol. 27", "Apuleius", "Apologia", "27"),
    ("CAELIUS AUREL. Acut. morb. II 37", "Caelius Aurelianus", "De Morbis Acutis", "II 37"),
    ("MARC. IV 46", "Marcus Aurelius", "Ad Se Ipsum (Meditationes)", "IV 46"),
    ("ANATOL. p. 30 Heib.", "Anatolius", "De Decade", "p. 30 Heib."),
    ("APOLLON. mir. 6", "Apollonius Paradoxographus", "Historiae Mirabiles", "6"),
    # The same spelling before Dyscolus' title stays his.
    ("APOLLON. de pronom. p. 65, 15 Schneid.", "Apollonius Dyscolus", "De Pronominibus", "p. 65, 15 Schneid."),
])
def test_round6_work_unresolved_heads_resolve(dictionary, head, author, title, locus):
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)


def test_round6_eudemus_bei_simplicius_prints_no_title(dictionary):
    # Parmenides B7: DK prints no title for Eudemus, only where Simplicius
    # quotes him.
    (e,) = ce._resolve_head(dictionary, "EUDEM. bei Simpl. Phys. 143, 4", "fixture", "1:X")
    assert _cite(e) == ("direct", "Eudemus of Rhodes", "", "")
    assert e["apparatus"] == "bei Simpl. Phys. 143, 4"


# --- 2026-09-29: Grok check of round 7 ---------------------------------------

def test_round7_alexander_metaphysics_keeps_the_book_letter(dictionary):
    # Parmenides A7: the work key swallowed Aristotle's book letter "A".
    (e,) = ce._resolve_head(dictionary, "ALEX. in Metaphys. A 3. 984b 3 p. 31, 7 Hayd.", "fixture", "1:X")
    assert _cite(e) == ("direct", "Alexander of Aphrodisias", "in Aristotelis Metaphysica",
                        "A 3. 984b 3 p. 31, 7 Hayd.")


def test_round7_greek_chapter_title_before_the_bekker_place_stays_in_the_head(dictionary):
    # Anaxagoras A84: the head stopped at the chapter title, losing the
    # Bekker page and the cross-reference.
    heads = _located(dictionary, ("context",
        "ARISTOT. Meteorol. Β 9 (περὶ ἀστραπῆς καὶ βροντῆς) 369b 14 [nach 31 A 63] Ἀ. δὲ τοῦ ἄνωθεν"),
        ("text", "αἰθέρος"))
    assert _texts(heads) == ["ARISTOT. Meteorol. Β 9 (περὶ ἀστραπῆς καὶ βροντῆς) 369b 14 [nach 31 A 63]"]
    assert _cite(heads[0]["expanded"][0]) == (
        "direct", "Aristotle", "Meteorologica", "Β 9 (περὶ ἀστραπῆς καὶ βροντῆς) 369b 14 [nach 31 A 63]")


def test_round7_collections_print_their_title_without_an_author(dictionary):
    # Anaxagoras A87: astronomical excerpts in cod. Vat. gr. 381, printed by
    # Maass (Aratea p. 143); was "Excerpta, (Excerpta) ASTRON. ...".
    (e,) = ce._resolve_head(dictionary, "EXC. ASTRON. cod. Vatic. 381 [ed. Maass Aratea p. 143]", "fixture", "1:X")
    assert "authorDisplay" not in e
    assert (e["work"]["title"], e["locus"]) == ("Excerpta Astronomica", "cod. Vatic. 381 [ed. Maass Aratea p. 143]")
    # Antiphon B64: the same collection entry, no longer "Excerpta, Excerpta Vindobonensia".
    (e,) = ce._resolve_head(dictionary, "EXC. VINDOB. 44 [Stob. IV 293, 17 Meineke; vgl. H. Schenk] Floril.", "fixture", "1:X")
    assert "authorDisplay" not in e and e["work"]["title"] == "Excerpta Vindobonensia"
    # Gorgias A8: Kaibel's Epigrammata Graeca, not "(epigram)".
    (e,) = ce._resolve_head(dictionary, "EPIGR. 875a p. 534 Kaibel", "fixture", "1:X")
    assert "authorDisplay" not in e
    assert (e["work"]["title"], e["work"]["italic"], e["locus"]) == ("Epigrammata Graeca", True, "875a p. 534 Kaibel")


@pytest.mark.parametrize("line,head,locus,nach", [
    # Xenophanes B15, B14: the note on the line's end.
    ("CLEM. Str. v 110 [II 400, 1 St.] nach B 14", "CLEM. Str. v 110 [II 400, 1 St.] nach B 14",
     "V 110 [II 400, 1 St.]", "nach B 14"),
    ("CLEM. Str. V 109 [II 399, 19 St.] nach B 23", "CLEM. Str. V 109 [II 399, 19 St.] nach B 23",
     "V 109 [II 399, 19 St.]", "nach B 23"),
    # Democritus A38: before the Greek.
    ("SIMPL. Phys. 28, 15 nach 67 A 8 παραπλησίως δὲ καὶ ὁ ἑταῖρος αὐτοῦ Δ.", "SIMPL. Phys. 28, 15 nach 67 A 8",
     "28, 15", "nach 67 A 8"),
    # Empedocles B36: before Stobaeus' own words, in quotation marks.
    ("STOB. Ecl. I 10, 11 [p. 121, 14 W.] nach B 6 ‘τῶν ... Νεῖκος’.", "STOB. Ecl. I 10, 11 [p. 121, 14 W.] nach B 6",
     "I 10, 11 [p. 121, 14 W.]", "nach B 6"),
    # Xenophanes B2: already in the head, dropped from the English.
    ("ATHEN. X 413 F nach 21 C 2: ταῦτ' εἴληφεν ὁ Εὐριπίδης", "ATHEN. X 413 F nach 21 C 2:",
     "X 413 F", "nach 21 C 2"),
])
def test_round7_unbracketed_nach_reference_is_the_heads(dictionary, line, head, locus, nach):
    # DK's "nach B 14" (after B 14 in the same source) stays in the head and
    # the English, as "[nach 28 B 16]" and "(nach B 50)" already do.
    heads = _located(dictionary, ("context", line), ("text", "λόγος"))
    assert _texts(heads) == [head]
    (e,) = heads[0]["expanded"]
    assert (e["locus"], e.get("apparatus")) == (locus, nach)


def test_round7_gregory_of_corinth_on_hermogenes(dictionary):
    # Critias B16: DK prints the title, "Zu HERMOG."; the author's second
    # word and the title had fallen into the locus under a placeholder.
    (e,) = ce._resolve_head(dictionary, "GREGOR. CORINTH. Zu HERMOG. Β 445, 7 Rabe", "fixture", "1:X")
    assert _cite(e) == ("direct", "Gregory of Corinth", "in Hermogenem", "Β 445, 7 Rabe")


# --- 2026-09-29, second round: John's rulings -------------------------------

@pytest.mark.parametrize("head,locus", [
    ("AN. BEKK. Lex. VI p. 470, 25", "I, Lex. VI p. 470, 25"),        # Antiphon B16
    ("ANECD. BEKK. Antiattic. 114, 28", "I, Antiattic. 114, 28"),     # Antiphon B82
    ("ANTIATT. Bekk. An. 78, 20", "I, Antiatt. 78, 20"),              # Antiphon B72
    ("ANTIATT. BEKK. p. 94, 1", "I, Antiatt. p. 94, 1"),              # Critias B13
    ("ANECD. Bekk. I 337, 13", "I 337, 13"),                          # Empedocles B47
    # Antiphon B19: "VI" is Bekker's Lex. VI (in vol. I), not a volume;
    # it had printed "Anecdota Graeca VI 403, 5".
    ("AN. BEKK. VI 403, 5", "I, Lex. VI 403, 5"),
    # Democritus B122: the lexicon in capitals had left the head as printed.
    ("ANECD. BEKK. LEX. VI 374, 14", "I, Lex. VI 374, 14"),
])
def test_ruling1_anecdota_prints_bekker_after_the_locus(dictionary, head, locus):
    # John, 2026-09-29: the title stays Anecdota Graeca with no author, and
    # "Bekk." follows the locus as apparatus, as the gnomologia print "Sternb.".
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _no_author(e) == ("direct", "Anecdota Graeca", locus)
    assert e["apparatus"] == "Bekk."


def test_ruling1_anecdota_dashes_print_bekker_too():
    # Real Antiphon B16/B17 and B82-B86.
    result = _run({"segments": [
        _seg("1:B16", "AN. BEKK. Lex. VI p. 470, 25"),
        _seg("1:B17", "— —p. 472, 14"),
        _seg("1:B82", "ANECD. BEKK. Antiattic. 114, 28"),
        _seg("1:B83", "—Lex. VI p. 345, 26"),
        _seg("1:B84", "—p. 367, 31"),
    ]}, work_id="antiphon-sophist-fragments")
    for s in ("1:B17", "1:B83", "1:B84"):
        assert result[s][0][0].get("apparatus") == "Bekk.", s


@pytest.mark.parametrize("line,author,title,locus", [
    # Anaxagoras A45, A73; Democritus A58; Leucippus A16
    ("ARISTOT. Phys. Γ 4. 203a 19 λόγος. SIMPL. Z. d. St. 460, 4 ἐπειδὴ λόγος.",
     "Simplicius", "in Aristotelis Physica", "460, 4"),
    ("ARISTOT. de caelo Α 3. 270b 24 λόγος. SIMPL. z. d. St. 119, 2 αἰτιᾶται λόγος.",
     "Simplicius", "in Aristotelis De Caelo", "119, 2"),
    # Zeno A22: "dazu"; the English had lost the page.
    ("ARISTOT. Phys. A 3. 187a 1 λόγος. SIMPL. dazu 138, 3 τὸν δὲ λόγος.",
     "Simplicius", "in Aristotelis Physica", "138, 3"),
    # Democritus A68: "Vgl. zu 196b 14", no "z. d. St."
    ("ARISTOT. Phys. Β 4. 195b 36 λόγος. Vgl. zu 196b 14 SIMPL. p. 330, 14 τὸ δὲ λόγος.",
     "Simplicius", "in Aristotelis Physica", "p. 330, 14"),
    # Anaximander A27, Democritus A91; Empedocles B84; Prodicus A19
    ("ARIST. Meteor. B 1. 353b 6 λόγος. ALEX. z. d. St. 67, 3 οἱ μὲν λόγος.",
     "Alexander of Aphrodisias", "in Aristotelis Meteorologica", "67, 3"),
    ("ARISTOT. de sens. 2 p. 437b 23 λόγος. ALEX. Z. d. St. p. 23, 8 Wendl. καὶ λόγος.",
     "Alexander of Aphrodisias", "in Aristotelis De Sensu", "p. 23, 8 Wendl."),
    ("ARISTOT. Top. B 6. 112b 22 λόγος. ALEX. Z. d. St. 181, 2 Π. δὲ λόγος.",
     "Alexander of Aphrodisias", "in Aristotelis Topica", "181, 2"),
    # Democritus A101; Empedocles A87 ("ad h. c."; the English had lost the page)
    ("ARISTOT. de anima Α 2. 404a 27 λόγος. PHILOP. z. d. St. p. 83, 27 ἀσώματον λόγος.",
     "John Philoponus", "in Aristotelis De Anima", "p. 83, 27"),
    ("ARISTOT. de gen. et corr. Α 8. 324b 26 λόγος. PHILOP. ad h. c. p. 160, 3 Vitelli ἀναγκαῖον λόγος.",
     "John Philoponus", "in Aristotelis De Generatione et Corruptione", "p. 160, 3 Vitelli"),
    # Gorgias A27: Olympiodorus on Plato
    ("PLATO Gorg. 450B λόγος. OLYMPIOD. Z. d. St. p. 131 Jahn [Jahns Archiv Suppl. 14, 131] οἱ λόγος.",
     "Olympiodorus", "in Platonis Gorgiam", "p. 131 Jahn [Jahns Archiv Suppl. 14, 131]"),
])
def test_ruling2_commentary_on_the_passage_above_names_the_commentary(dictionary, line, author, title, locus):
    # John, 2026-09-29: "z. d. St." (on this passage) names the commentator's
    # work on the passage cited above; each checked in the TLG.
    heads = _located(dictionary, ("context", line))
    assert _cite(heads[-1]["expanded"][0]) == ("direct", author, title, locus)


def test_ruling2_two_commentaries_on_one_passage(dictionary):
    # Empedocles B108: Philoponus, then Simplicius, both on De anima 427a 24.
    heads = _located(dictionary, ("context", "ARISTOT. Metaph. Γ 5. 1009b 18 λόγος. "
        "de anima Γ 3. 427 a 24 λόγος. PHILOP. Z. d. St. 486, 13 ὁ γὰρ λόγος. "
        "SIMPL. z. d. St. 202, 30 καὶ λόγος."))
    assert [_cite(h["expanded"][0])[2] for h in heads[-2:]] == [
        "in Aristotelis De Anima", "in Aristotelis De Anima"]


def test_ruling2_commentary_with_no_passage_above_keeps_its_placeholder(dictionary):
    # Synthetic: no title is invented when nothing above names the passage.
    (e,) = ce._resolve_head(dictionary, "SIMPL. z. d. St. 119, 2", "fixture", "1:X")
    assert _cite(e) == ("direct", "Simplicius", "(commentary on Aristotle)", "z. d. St. 119, 2")


@pytest.mark.parametrize("head,author,title,locus", [
    # Democritus A46: TLG 0057.060, Kühn VIII 931.
    ("GALEN. VIII 931 K.", "Galen", "De Dignoscendis Pulsibus", "VIII 931 K."),
    # Melissus A6: TLG 0057.085, Kühn XV 29.
    ("GAL. CMG V 9, 1, 17, 16", "Galen", "in Hippocratis De Natura Hominis", "CMG V 9, 1, 17, 16"),
    # Xenophanes A13: TLG 0086.038, Bekker 1400b.
    ("ARIST. B 26. 1400b 5", "Aristotle", "Rhetorica", "B 26. 1400b 5"),
    # Gorgias A10: Diogenes Laertius VIII 58 names the work ("ἐν Χρονικοῖς").
    ("APOLLODOR. [F GrHist. 244F 33, s. oben I 278, 28]", "Apollodorus", "Chronica",
     "[F GrHist. 244F 33, s. oben I 278, 28]"),
    # Parmenides B24: TLG 1760.001, section 4.
    ("SUETONIUS (Miller Mél. 417)", "Suetonius", "Περὶ βλασφημιῶν καὶ πόθεν ἑκάστη", "(Miller Mél. 417)"),
    # Parmenides A40: TLG 4161.006 (cod. Paris. suppl. gr. 607A), section 14.
    ("ANONYM. BYZANT. ed. Treu p. 52, 19 [Isag. in Arat. II 14 p. 318, 15 Maass]", "Anonymus Byzantinus",
     "Prolegomena in Aratum", "ed. Treu p. 52, 19 [Isag. in Arat. II 14 p. 318, 15 Maass]"),
    # Gorgias B5a: TLG 4238.001, Rabe (Rhet. Gr. XIV) p. 180.
    ("ATHANASIUS Alexandr. Rhet. Gr. XIV, 180, 9 Rabe", "Athanasius (rhetor)",
     "Prolegomena in Hermogenis Librum περὶ στάσεων", "Rhet. Gr. XIV, 180, 9 Rabe"),
    # Gorgias B31: TLG 2031.001, Walz VIII p. 23.
    ("SOPAT. Rhet. gr. VIII 23 W.", "Sopater", "Διαίρεσις ζητημάτων", "Rhet. gr. VIII 23 W."),
    # Empedocles A23: TLG 2586.001, Spengel p. 333.
    ("MENANDER I 2, 2", "Menander (rhetor)", "Διαίρεσις τῶν ἐπιδεικτικῶν", "I 2, 2"),
    # Thales A17: Theon names the work at p. 198 Hiller (TLG 1724.001).
    ("DERCYLLIDES ap. Theon. astr. 198, 14 H.", "Dercyllides",
     "Περὶ τοῦ ἀτράκτου καὶ τῶν σφονδύλων τῶν ἐν τῇ Πολιτείᾳ παρὰ Πλάτωνι λεγομένων",
     "ap. Theon. astr. 198, 14 H."),
])
def test_ruling2_titles_found_in_the_tlg(dictionary, head, author, title, locus):
    # John, 2026-09-29: where DK prints no title, the title the TLG confirms.
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)


def test_ruling2_menander_ebenda_keeps_the_title(dictionary):
    # Empedocles A23: "Ebenda 5, 2" after "MENANDER I 2, 2" (TLG Spengel p. 337).
    heads = _located(dictionary, ("context",
        "MENANDER I 2, 2 φυσικοὶ λόγος. Ebenda 5, 2 εἰσὶν δὲ λόγος."))
    assert [_cite(h["expanded"][0])[2:] for h in heads] == [
        ("Διαίρεσις τῶν ἐπιδεικτικῶν", "I 2, 2"), ("Διαίρεσις τῶν ἐπιδεικτικῶν", "I 5, 2")]


@pytest.mark.parametrize("head,author,title,locus", [
    ("ISOCR. XV 235", "Isocrates", "Antidosis", "XV 235"),                  # Anaxagoras A15
    ("ISOCR. 10, 3", "Isocrates", "Helenae Encomium", "10, 3"),             # Gorgias B1
    ("ISOCR. 15, 155f.", "Isocrates", "Antidosis", "15, 155f."),            # Gorgias A18
    ("ANDOC. I 47", "Andocides", "De Mysteriis", "I 47"),                   # Critias A5
    ("[DEMOSTH.] 58, 67", "pseudo-Demosthenes", "In Theocrinem", "58, 67"), # Critias A6
    # Thales A11a: the TLG (Colonna) has the passage in oration 28, not 30;
    # DK's number follows another numbering, so only the collection is named.
    ("HIMER. 30 Cod. Neap. [Schenkl Herm. 46, 1911, 420]", "Himerius", "Declamationes et Orationes",
     "30 Cod. Neap. [Schenkl Herm. 46, 1911, 420]"),
])
def test_ruling3_a_number_that_names_the_work(dictionary, head, author, title, locus):
    # John, 2026-09-29: the standard title from the number, checked in the TLG.
    (e,) = ce._resolve_head(dictionary, head, "fixture", "1:X")
    assert _cite(e) == ("direct", author, title, locus)


def test_ruling4_porphyry_philologos_akroasis(dictionary):
    # Protagoras B2: DK names the work in Greek after the author, as Eusebius
    # heads P. E. X 3 (TLG 2018.001) "ἀπὸ τοῦ πρώτου τῆς Φιλολόγου ἀκροάσεως".
    heads = _located(dictionary, ("context",
        "PORPHYR. ἀπὸ τοῦ α τῆς Φιλολόγου ἀκροάσεως b. Eus. P. E. X 3, 25 σπάνια δὲ τὰ λόγος."))
    assert _texts(heads) == ["PORPHYR. ἀπὸ τοῦ α τῆς Φιλολόγου ἀκροάσεως b. Eus. P. E. X 3, 25"]
    (e,) = heads[0]["expanded"]
    assert _cite(e) == ("direct", "Porphyry", "Φιλόλογος ἀκρόασις", "I")
    assert e["apparatus"] == "b. Eus. P. E. X 3, 25"


def test_ruling5_proclus_hesiod_line_gets_a_reader_note(dictionary):
    # Gorgias B26: DK's 758 stays; a note gives the modern line numbers.
    rulings = ce._load_adjudications()["gorgias-fragments"]
    (_, heads) = _columns(dictionary, [("context", "PROCL. Vit. Hom. p. 26, 14 Wil. λόγος.")],
                          [("context", "—in Hes. Opp. 758"), ("text", "λόγος")],
                          rulings={"X2": rulings["B26"]})
    (e,) = heads[0]["expanded"]
    assert _cite(e) == ("dash", "Proclus", "in Hesiodi Opera et Dies", "758")
    assert "760–764" in e["note"] and "Gaisford" in e["note"]


@pytest.mark.parametrize("line,head,locus,apparatus", [
    # Empedocles A88: the chapter title with its Diels page inside it.
    ("AËT. IV 14, 1 (περὶ κατοπτρικῶν ἐμφάσεων. D. 405) Ἐ. κατ' ἀπορροίας λόγος.",
     "AËT. IV 14, 1 (περὶ κατοπτρικῶν ἐμφάσεων. D. 405)", "IV 14, 1", "(περὶ κατοπτρικῶν ἐμφάσεων. D. 405)"),
    # Critias B4: the chapter title after the place.
    ("HEPHAEST. 2, 3 (περὶ συνεκφωνήσεως) ἢ δύο βραχεῖαι λόγος.",
     "HEPHAEST. 2, 3 (περὶ συνεκφωνήσεως)", "2, 3 (περὶ συνεκφωνήσεως)", None),
    # Democritus A77: a "διὰ τί" question as the chapter title.
    ("PLUT. Quaest. conv. VIII 10, 2 p. 734F (διὰ τί τοῖς φθινοπωρινοῖς ἐνυπνίοις ἥκιστα πιστεύομεν) "
     "ὁ δὲ Φαβωρῖνος λόγος.",
     "PLUT. Quaest. conv. VIII 10, 2 p. 734F (διὰ τί τοῖς φθινοπωρινοῖς ἐνυπνίοις ἥκιστα πιστεύομεν)",
     "VIII 10, 2 p. 734F (διὰ τί τοῖς φθινοπωρινοῖς ἐνυπνίοις ἥκιστα πιστεύομεν)", None),
])
def test_defect_chapter_title_after_the_place_is_the_heads(dictionary, line, head, locus, apparatus):
    heads = _located(dictionary, ("context", line))
    assert _texts(heads) == [head]
    (e,) = heads[0]["expanded"]
    assert (e["locus"], e.get("apparatus")) == (locus, apparatus)


def test_defect_supplement_after_the_diels_page_stays_out(dictionary):
    # Heraclitus A12: "(γίνεσθαι τὴν ἔκλειψιν)" supplements the quotation.
    heads = _located(dictionary, ("context", "AËT. II 24, 3 (D. 354) (γίνεσθαι τὴν ἔκλειψιν) λόγος."))
    assert _texts(heads) == ["AËT. II 24, 3 (D. 354)"]


def test_ruling5_note_ruling_counts_as_used_in_run():
    # The real table: run() fails on a ruling that matched no head.
    result = _run({"segments": [
        _seg("1:B25", "PROCL. Vit. Hom. p. 26, 14 Wil."),
        _seg("1:B26", "—in Hes. Opp. 758", ("text", "λόγος")),
    ]}, work_id="gorgias-fragments")
    (e,) = result["1:B26"][0]
    assert _cite(e)[3] == "758" and "annotated" in e["flags"] and e["note"]


def test_ruling_note_on_a_direct_head_keeps_the_reading(dictionary):
    # A note ruling applies to a direct head too: the reading stands, the
    # ruling adds its reader's note (Thales A11a keeps DK's 30).
    line = "HIMER. 30 Cod. Neap. [Schenkl Herm. 46, 1911, 420] λόγος."
    (plain,) = _columns(dictionary, [("context", line)])
    ruling = {"head": "HIMER. 30 Cod. Neap. [Schenkl Herm. 46, 1911, 420]", "type": "note",
              "readerNote": "A note.", "note": "x"}
    (heads,) = _columns(dictionary, [("context", line)], rulings={"X1": ruling})
    (before,), (after,) = plain[0]["expanded"], heads[0]["expanded"]
    assert "note" not in before and "annotated" not in before["flags"]
    assert after["note"] == "A note." and after["flags"] == before["flags"] + ["annotated"]
    assert {k: v for k, v in after.items() if k not in ("note", "flags")} == \
        {k: v for k, v in before.items() if k != "flags"}
    # A head the ruling does not name is left alone.
    (other,) = _columns(dictionary, [("context", line)],
                        rulings={"X1": dict(ruling, head="HIMER. 31 Cod. Neap.")})
    assert other[0]["expanded"] == plain[0]["expanded"]


def test_ruling_thales_a11a_himerius_note_is_in_the_table_and_used():
    rulings = ce._load_adjudications()["thales-testimonia"]
    assert rulings["A11a"]["type"] == "note" and "oration 28" in rulings["A11a"]["readerNote"]
    # run() fails on a ruling that matched no head, so this proves it is used.
    result = _run({"segments": [
        _seg("1:A11a", "HIMER. 30 Cod. Neap. [Schenkl Herm. 46, 1911, 420] λόγος."),
    ]}, work_id="thales-testimonia")
    (e,) = result["1:A11a"][0]
    assert e["locus"].startswith("30 ") and "annotated" in e["flags"] and "oration 28" in e["note"]


def test_ruling3_second_isocrates_speech_in_the_same_passage(dictionary):
    # Gorgias B1: DK's "15, 268" inside the passage is Isocrates' speech 15,
    # the Antidosis (TLG 0010.019 section 268), not the Helena's section 15.
    heads = _located(dictionary, ("context",
        "ISOCR. 10, 3 πῶς γὰρ ἂν λόγος ἀποφαίνειν. 15, 268 τοὺς λόγους λόγος."))
    assert _texts(heads) == ["ISOCR. 10, 3", "15, 268"]
    assert _cite(heads[1]["expanded"][0])[2:] == ("Antidosis", "15, 268")


def test_ruling1_greek_heading_of_an_anecdota_dash_does_not_repeat_bekker(dictionary):
    # Antiphon B17: the Greek side reads in DK's abbreviations, which name him.
    (_, heads) = _columns(dictionary, [("context", "AN. BEKK. Lex. VI p. 470, 25")],
                          [("context", "— —p. 472, 14"), ("text", "λόγος")])
    assert heads[0]["display"] == "AN. BEKK. I, Lex. VI p. 472, 14"
    assert heads[0]["expanded"][0]["apparatus"] == "Bekk."
