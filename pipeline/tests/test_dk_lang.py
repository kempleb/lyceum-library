from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import dk_lang


def _decisions(pairs: dict[str, str]) -> dict[str, dict[str, str]]:
    """Test helper mirroring the migration script: `{run_text: decision}` ->
    the committed hash-keyed shape `{hash: {"decision", "note"}}` (see
    dk_lang.decision_key's doc). Keeps the tests below readable (assert
    against plain run text) while exercising the real, hashed lookup path."""
    return {
        dk_lang.decision_key(dk_lang.normalize_run(run)): {"decision": decision, "note": "test"}
        for run, decision in pairs.items()
    }


def test_decision_key_is_a_16_hex_char_hash():
    key = dk_lang.decision_key(dk_lang.normalize_run("vgl. B 12"))
    assert len(key) == 16
    assert all(c in "0123456789abcdef" for c in key)
    # Deterministic and content-addressed: the same normalized text always
    # hashes to the same key, a different one to a (near-certainly) different key.
    assert key == dk_lang.decision_key(dk_lang.normalize_run("vgl. B 12"))
    assert key != dk_lang.decision_key(dk_lang.normalize_run("vgl. B 13"))


def test_find_non_greek_runs_splits_at_greek_letter_boundaries():
    text = "PLUT. def. orac. 11 οἱ μὲν λέγοντες [vgl. B 12]"
    runs = dk_lang.find_non_greek_runs(text)
    assert runs == ["PLUT. def. orac. 11", "[vgl. B 12]"]


def test_find_non_greek_runs_drops_pure_punctuation_and_short_runs():
    # A lone bracket or single digit carries no language signal.
    text = "λόγος] 5 ἀλήθεια"
    assert dk_lang.find_non_greek_runs(text) == []


def test_find_non_greek_runs_trims_connective_punctuation():
    text = "λόγος, ARIST. Metaph. λόγος"
    assert dk_lang.find_non_greek_runs(text) == ["ARIST. Metaph"]


def test_normalize_run_collapses_internal_whitespace():
    assert dk_lang.normalize_run("  vgl.\n B 12  ") == "vgl. B 12"


def test_classify_run_citation_shape_all_caps_and_numerals():
    assert dk_lang.classify_run("AËT. I 3, 11 (D. 283)") == "citation"
    assert dk_lang.classify_run("[B 40]") == "citation"


def test_classify_run_all_caps_citation_with_lowercase_title_words():
    # A citation abbreviation's own lowercase Latin title words ("de anima")
    # must not be mistaken for genuine prose -- the case check is against
    # the ORIGINAL word casing, not a lowered copy (see the regression this
    # guards: an earlier version of this heuristic lowercased before
    # counting "lowercase words", which made every all-caps abbreviation
    # look like prose).
    assert dk_lang.classify_run("ARIST. de anima A 2. 405a 24") == "citation"


def test_classify_run_latin_prose_scores_keep_latin():
    run = ("CHALCID. c. 251 p. 284, 10 Wrob. H. vero consentientibus Stoicis "
           "rationem nostram cum divina ratione conectit")
    assert dk_lang.classify_run(run) == "keep-latin"


def test_classify_run_german_prose_scores_strip_german():
    # Two or more genuine German words (not a single bare apparatus
    # particle -- see the heuristic-limitation test below) tips the
    # citation-shape check's <=1-lowercase-word threshold.
    assert dk_lang.classify_run("oder vielmehr") == "strip-german"


def test_classify_run_isolated_single_german_word_is_a_heuristic_limitation():
    # A single bare German word -- whether apparatus shorthand ("vgl" — see
    # test_classify_run_bare_apparatus_particle_is_citation_not_strip
    # above, correctly kept) or genuine prose reduced to one word ("und"
    # joining two Suda headwords; "wie" opening a short parenthetical aside)
    # -- reads identically under this heuristic's <=1-lowercase-word
    # threshold: 'citation', not 'strip-german'. This is a REAL, documented
    # heuristic limitation, not a silent gap: both committed decision files
    # override these SPECIFIC runs to 'strip-german' by hand (see the Wave
    # 1b implementation report's flagged-ambiguous item) -- the heuristic is
    # a labor-saving proposal only, never authoritative (module doc).
    assert dk_lang.classify_run("und") == "citation"
    assert dk_lang.classify_run("(wie Diogenes 64 A 20)") == "citation"


def test_classify_run_bare_apparatus_particle_is_citation_not_strip():
    # A single bare bibliographic-shorthand word ("vgl." "cf.") reads as
    # citation-shaped (at most one lowercase word, at most one German hit),
    # matching this corpus's own dk-context-lang.json decision for exactly
    # these tokens (see the Wave 1b implementation report's flagged-
    # ambiguous item).
    assert dk_lang.classify_run("HIPPOL. IX 9 (nach B 50)") == "citation"


def test_propose_decisions_dedups_by_normalized_run():
    runs = ["[B 40]", "[B 40]", " [B 40] "]
    proposal = dk_lang.propose_decisions(runs)
    assert proposal == {"[B 40]": "citation"}


def test_load_decisions_rejects_unrecognized_value(tmp_path):
    key = dk_lang.decision_key(dk_lang.normalize_run("[B 40]"))
    path = tmp_path / "dk-context-lang.json"
    path.write_text(
        json.dumps({key: {"decision": "delete-it", "note": "test"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        dk_lang.load_decisions(path)


def test_load_decisions_rejects_non_object_root(tmp_path):
    path = tmp_path / "dk-context-lang.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        dk_lang.load_decisions(path)


def test_load_decisions_rejects_literal_text_key_not_a_hash(tmp_path):
    # A stale pre-migration file (or an authoring slip) keyed by the run's
    # own literal text -- exactly the committed-corpus-text shape this
    # format change exists to forbid -- must fail loudly, not silently
    # never match anything downstream.
    path = tmp_path / "dk-context-lang.json"
    path.write_text('{"[B 40]": {"decision": "citation", "note": "test"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="hex-char decision hash"):
        dk_lang.load_decisions(path)


def test_load_decisions_rejects_missing_note(tmp_path):
    key = dk_lang.decision_key(dk_lang.normalize_run("[B 40]"))
    path = tmp_path / "dk-context-lang.json"
    path.write_text(json.dumps({key: {"decision": "citation"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="must be an object"):
        dk_lang.load_decisions(path)


def test_load_decisions_accepts_well_formed_hash_keyed_file(tmp_path):
    key = dk_lang.decision_key(dk_lang.normalize_run("[B 40]"))
    path = tmp_path / "dk-context-lang.json"
    path.write_text(
        json.dumps({key: {"decision": "citation", "note": "bracketed cross-ref"}}),
        encoding="utf-8",
    )
    assert dk_lang.load_decisions(path) == {
        key: {"decision": "citation", "note": "bracketed cross-ref"}
    }


def test_apply_context_language_strips_strip_german_runs():
    text = "SEXT. VII 133 οἱ μὲν vgl. λέγοντες oder vielmehr ἀλήθεια"
    decisions = _decisions({"SEXT. VII 133": "citation", "vgl": "citation", "oder vielmehr": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    assert "oder vielmehr" not in out
    assert "SEXT. VII 133" in out
    assert "vgl" in out


def test_apply_context_language_raises_on_undecided_run():
    text = "PLUT. def. orac. λόγος"
    with pytest.raises(ValueError, match="no dk-context-lang.json decision"):
        dk_lang.apply_context_language(text, {}, where="A1")


def test_apply_context_language_collapses_whitespace_after_stripping():
    text = "λόγος oder vielmehr ἀλήθεια"
    decisions = _decisions({"oder vielmehr": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    assert out == "λόγος ἀλήθεια"


def test_apply_context_language_is_a_no_op_when_nothing_needs_deciding():
    text = "λόγος ἀλήθεια"
    assert dk_lang.apply_context_language(text, {}, where="test") == text


def test_apply_context_language_removes_bracket_orphaned_by_strip():
    # Real shape: Heraclitus B58 "κακόν [näml. ἕν ἐστιν]." -- the run
    # extraction splits "[näml. ... ]" into two non-Greek runs because the
    # Greek gloss "ἕν ἐστιν" sits inside the brackets. The opening bracket
    # rides along with the German word ("[näml" -- brackets aren't in the
    # " ,.;:" trim charset) and gets removed with it; left unfixed, the
    # closing "]" is stranded with no partner.
    text = "κακόν [näml. ἕν ἐστιν]."
    decisions = _decisions({"[näml": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    assert "[" not in out
    assert "]" not in out
    assert out == "κακόν . ἕν ἐστιν."


def test_apply_context_language_leaves_ambiguous_block_bracket_alone(capsys):
    # Sol review blocker repro: the prior unbounded, per-run partner search
    # assumed any unmatched "]" found by scanning forward from the stripped
    # run's edge belonged to that run. Here the block itself is already
    # unbalanced BEFORE the strip -- two "["s ("[λέξις", the ancient
    # source's own, and "[oder vielmehr", the German aside) and only one
    # "]" -- so the trailing "]" is at least as plausibly the ancient
    # source's own "[λέξις ... ]" closing bracket as it is the stripped
    # run's partner. The safe, correct answer for a block this ambiguous is
    # to delete nothing beyond the trimmed run itself: the prior code
    # deleted the "]" anyway ("ἀρχή [λέξις μέση τέλος", leaving the
    # ancient "[λέξις" permanently dangling with no partner at all); the
    # fixed behaviour leaves "[λέξις ... μέση]" intact.
    text = "ἀρχή [λέξις [oder vielmehr μέση] τέλος"
    decisions = _decisions({"[oder vielmehr": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="B58-repro")
    assert out == "ἀρχή [λέξις μέση] τέλος"
    assert out.count("[") == 1
    assert out.count("]") == 1
    warnings = [line for line in capsys.readouterr().out.splitlines() if "WARNING" in line]
    assert any("B58-repro" in w for w in warnings)


def test_apply_context_language_removes_introducing_colon_orphaned_by_strip():
    # Real shape: Heraclitus B118 "... ἀρίστη oder vielmehr: αὔη ..." -- the
    # trailing colon is trimmed off the run string itself (":" is in the
    # " ,.;:" trim charset), so the literal replace of "oder vielmehr" never
    # touches it; left unfixed, the colon survives alone, introducing
    # nothing.
    text = "ξηρὴ ψυχή oder vielmehr: αὔη ψυχή"
    decisions = _decisions({"oder vielmehr": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    assert ":" not in out
    assert out == "ξηρὴ ψυχή αὔη ψυχή"


def test_apply_context_language_keeps_outer_comma_after_self_delimited_aside():
    # Real shape: Heraclitus A15 "ψυχήν (wie Diogenes 64 A 20), εἴπερ τὴν"
    # -- the strip-german run is a SELF-CONTAINED parenthetical (opens and
    # closes with its own matching delimiter), so the comma trailing it is
    # the OUTER Greek clause's own punctuation ("ψυχήν, ... εἴπερ ..."), not
    # something the run itself introduced -- it must survive.
    text = "ψυχήν (wie Diogenes 64 A 20), εἴπερ τὴν"
    decisions = _decisions({"(wie Diogenes 64 A 20)": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    # The comma survives (pre-existing "stray space before comma" cosmetics
    # are untouched -- out of this fix's scope, unrelated to orphaning).
    assert out == "ψυχήν , εἴπερ τὴν"


def test_apply_context_language_removes_paren_orphaned_by_strip():
    # Grok review defect G4 (real shape: Xenophanes B41 "κανών (über
    # σιρός) σιλλογράφος" -- a lexicographer's headword-gloss aside): the
    # run extraction splits "(über ... )" into two non-Greek runs because
    # the Greek headword "σιρός" sits inside the parens, exactly the
    # square-bracket "[näml. ... ]" shape above but with "("/")". Before
    # this fix, the orphan-recovery mechanism only tracked "["/"]" --
    # "(über" was removed with its opening paren, but the matching ")"
    # two Greek words later was never found, so it survived orphaned:
    # "κανών σιρός) σιλλογράφος".
    text = "κανών (über σιρός) σιλλογράφος"
    decisions = _decisions({"(über": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="B41-repro")
    assert "(" not in out
    assert ")" not in out
    assert out == "κανών σιρός σιλλογράφος"


def test_apply_context_language_leaves_ambiguous_block_paren_alone(capsys):
    # The paren mirror of the square-bracket ambiguity guard above: the
    # block's own "("/")" structure is already unbalanced BEFORE the strip
    # (two "("s, one ")") -- there is no principled partner to delete, so
    # nothing beyond the trimmed run itself is touched.
    text = "ἀρχή (λέξις (über μέση) τέλος"
    decisions = _decisions({"(über": "strip-german"})
    out = dk_lang.apply_context_language(text, decisions, where="paren-ambig-repro")
    assert out == "ἀρχή (λέξις μέση) τέλος"
    assert out.count("(") == 1
    assert out.count(")") == 1
    warnings = [line for line in capsys.readouterr().out.splitlines() if "WARNING" in line]
    assert any("paren-ambig-repro" in w for w in warnings)


def test_apply_context_language_never_touches_a_balanced_bracket():
    # Conservative guard: a bracketed citation run that is NOT split by
    # embedded Greek (both bracket members inside the same run, as in
    # "[vgl. B 12]") must be left completely alone when it is a 'citation'
    # decision -- nothing here is "orphaned by a strip".
    text = "λόγος [vgl. B 12] ἀλήθεια"
    decisions = _decisions({"[vgl. B 12]": "citation"})
    out = dk_lang.apply_context_language(text, decisions, where="test")
    assert out == text
