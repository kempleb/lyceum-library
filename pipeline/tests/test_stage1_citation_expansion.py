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
    # cross-reference. They must stay two run slots, never merged into one
    # flattened, semicolon-joined false attribution.
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
    assert _cite(result["1:B23"][0][0]) == ("dash", "Suda", "Lexicon (Suda)", "s.v. μακάρων νήσοισιν")


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
    # Real Empedocles A44 -> A45: an ARISTOT. inside A44's passage stands
    # between the Aëtius head and "—I 26, 1"; nothing in the dash decides
    # between them, so it stays as printed.
    result = _run({"segments": [
        _seg("1:A44", "AËT. I 24, 2 Ἐ. καὶ Ἀναξαγόρας. ARISTOT. de cael. Γ 7. 305b 1 Ἐ. φησιν"),
        _seg("1:A45", "—I 26, 1 Ἐ. φύσιν εἱμαρμένης"),
    ]}, work_id="empedocles-testimonia")
    assert _verbatim_flags(result["1:A45"][0][0]) == ["dash-unresolved", "dash-antecedent-uncertain"]


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
        _seg("1:A2", "ACHILL. Isag. 4 p. 34, 20 M."),
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


def test_rule_e_memo_excluded_dash_work_stays_verbatim():
    result = _run(_spine("THEOPHR. Metaphys. 15 p. 7a 10 Usen.", "—de vertig. 9"))
    assert _verbatim_flags(result["1:B2"][0][0]) == ["dash-unresolved", "dash-work-excluded"]


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


def test_finding_b_same_author_other_work_in_passage_is_the_antecedent():
    # Synthetic: the ARISTOT. Metaph. named inside the passage is the last
    # source named, so the book-letter dash is Metaphysics, not Physics.
    result = _run({"segments": [
        _seg("1:A1", "ARISTOT. Phys. Γ 4. 203a 33 ὅσοι μὲν στοιχεῖα φασιν. ARISTOT. Metaph. Α 4. 985b 4 Λεύκιππος"),
        _seg("1:A2", "— —Ζ 13. 1039a 9 δυνατὸν δὲ λέγει"),
        _seg("1:A3", "— —14. 1039a 30"),
    ]}, work_id="democritus-testimonia")
    assert _cite(result["1:A2"][0][0]) == ("dash", "Aristotle", "Metaphysica", "Ζ 13. 1039a 9")
    assert _cite(result["1:A3"][0][0]) == ("dash", "Aristotle", "Metaphysica", "Ζ 14. 1039a 30")


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
    ce._scan_passage(ce._load_dictionary(), chain, "tradunt. Dagegen HEROD. II 22 ἡ γὰρ τετάρτη")
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
        "CIC. de div. i 50, 112 ab Anaximandro physico": "i 50, 112",          # Anaximander A5a
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
    # ("ecl." = Eclogae) still falls through to DEFAULT, unchanged -- the new
    # explicit key only matches the two-token "Praepar. sophist." span.
    (e,) = ce._resolve_head(dictionary, "PHRYNICH. ecl. 312 Lob.", "hippias-fragments", "1:B10")
    assert _cite(e) == ("direct", "Phrynichus", "Praeparatio Sophistica", "ecl. 312 Lob.")
