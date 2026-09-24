"""WP6: work.author / work.language — manifest accessors, preflight schema
validation, and stage4/stage5 dictionary-path parameterization.

Uses synthetic manifest data in the style of tests/fixtures/preflight/*/manifests/
(a minimal Bekker-scheme work dict) rather than a real corpus manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reader_pipeline.config import Manifest
from reader_pipeline import stage3_tokenize, stage4_morphology, stage5_lsj, stage6_search
from reader_pipeline.preflight import WorkManifest, _validate_manifest_schema


def _sources() -> dict:
    return {
        "tlg_dir_env": "TLG_DIR",
        "tlg_dir_default": "../TLG Files/TLG",
        "diogenes_server": "/Applications/Diogenes.app/Contents/server",
        "diogenes_data": "/Applications/Diogenes.app/Contents/dependencies/data",
    }


def _bekker_manifest_data(work_overrides: dict | None = None) -> dict:
    work = {
        "id": "VAL",
        "title": "Valid Fixture",
        "author": "aristotle",
        "tlg_author": "0086",
        "tlg_work": "999",
        "greek_edition": "Fixture Greek",
        "english_translation": "Fixture English",
    }
    work.update(work_overrides or {})
    return {
        "work": work,
        "bekker_range": {"first_column": "1094a", "last_column": "1094a"},
        "chapters": {"source": "explicit", "list": [{"n": 1, "bekker": "1094a1"}]},
        "english": {
            "primary": {
                "id": "fixture",
                "name": "Fixture English",
                "model": "archive",
                "dir": "fixture",
                "books": 1,
                "chapter_marker": "number",
            }
        },
        "books": [{"n": 1, "start": "1094a1", "end": "1094a2"}],
        "sources": _sources(),
    }


def _schema_problems(data: dict) -> list[str]:
    manifest = WorkManifest(work_id=data["work"]["id"], path=Path("VAL.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    return [message for _work, _file, message in problems]


# --- Manifest accessors (config.py) -----------------------------------------


def test_manifest_exposes_author():
    m = Manifest(_bekker_manifest_data(), Path("VAL.yaml"))
    assert m.author == "aristotle"


def test_manifest_language_defaults_to_grc():
    m = Manifest(_bekker_manifest_data(), Path("VAL.yaml"))
    assert m.language == "grc"


def test_manifest_language_honors_explicit_value():
    m = Manifest(_bekker_manifest_data({"language": "lat"}), Path("VAL.yaml"))
    assert m.language == "lat"


def test_manifest_lexicon_defaults_to_true():
    m = Manifest(_bekker_manifest_data(), Path("VAL.yaml"))
    assert m.lexicon is True


def test_manifest_lexicon_honors_explicit_false():
    m = Manifest(_bekker_manifest_data({"lexicon": False}), Path("VAL.yaml"))
    assert m.lexicon is False


# --- preflight schema validation --------------------------------------------


def test_preflight_schema_accepts_manifest_with_author_and_language():
    # Wave 2 Batch 1a: a `language: lat` work's source-identity keys are
    # PHI's (phi_author/phi_work/latin_edition), not TLG's — see
    # preflight._validate_manifest_schema's language-dispatched work_keys.
    # The base fixture's tlg_* fields stay present too (harmless extras);
    # only the phi_* fields are actually required for this to pass clean.
    data = _bekker_manifest_data({
        "language": "lat",
        "phi_author": "0474",
        "phi_work": "055",
        "latin_edition": "Fixture Latin",
    })
    assert _schema_problems(data) == []


def test_preflight_schema_rejects_missing_author():
    data = _bekker_manifest_data()
    del data["work"]["author"]
    problems = _schema_problems(data)
    assert any("work.author must be a non-empty string" in p for p in problems)


def test_preflight_schema_rejects_unknown_language():
    data = _bekker_manifest_data({"language": "fra"})
    problems = _schema_problems(data)
    assert any("work.language must be 'grc' or 'lat'" in p for p in problems)


def test_preflight_schema_omitted_language_is_fine():
    data = _bekker_manifest_data()
    assert "language" not in data["work"]
    assert _schema_problems(data) == []


# --- Blocker 1(a): work.lexicon must not fail open for a grc work (Sol) -----


def test_preflight_schema_rejects_lexicon_false_on_grc_work():
    data = _bekker_manifest_data({"lexicon": False})
    problems = _schema_problems(data)
    assert any(
        "work.lexicon: false is not permitted for a grc-language work" in p
        for p in problems
    ), problems


def test_preflight_schema_accepts_lexicon_false_on_lat_work():
    data = _bekker_manifest_data({
        "language": "lat", "lexicon": False,
        "phi_author": "0474", "phi_work": "055", "latin_edition": "Fixture Latin",
    })
    assert _schema_problems(data) == []


def test_preflight_schema_lexicon_true_is_fine_on_grc_work():
    data = _bekker_manifest_data({"lexicon": True})
    assert _schema_problems(data) == []


# --- stage4/stage5 dictionary/morphology source-path parameterization ------


def _language_manifest(language: str) -> Manifest:
    return Manifest(_bekker_manifest_data({"language": language}), Path("VAL.yaml"))


def test_stage5_grc_dictionary_path_unchanged():
    path = stage5_lsj._dictionary_path(_language_manifest("grc"))
    assert path.name == "grc.lsj.xml"


def test_stage5_lat_dictionary_path_wired():
    # Wave 2 Batch 1b wires stage5's Latin dictionary path (Lewis & Short,
    # docs/wave2-latin-design.md §6) -- this replaces the earlier
    # NotImplementedError expectation, which locked in the pre-Batch-1b stub
    # behavior (Karpathy rule 5: wrong tests get replaced, not appeased).
    path = stage5_lsj._dictionary_path(_language_manifest("lat"))
    assert path.name == "lat.ls.perseus-eng1.xml"


def test_stage5_base_key_strips_diogenes_latin_homonym_hash():
    # Real-data finding (Wave 2 Batch 1b): stage4's Latin lemma field carries
    # Diogenes' OWN homonym marker as "qui#1", "edo#1" -- confirmed 10.79% of
    # ALL latin-analyses.txt lemma groups (common words: "qui", "edo",
    # "is#1"/"is#2"), a DIFFERENT convention from Lewis & Short's own
    # trailing-digit key ("qui1", "e^do1"). Without stripping '#',
    # base_key("qui#1") left a dangling "qui#" that could never match L&S's
    # base_index (keyed off base_key("qui1") == "qui"), silently failing the
    # base-match fallback for ~11% of Latin lemmata -- caught by exercising
    # the real Diogenes data, not by unit tests alone (Karpathy rule 5).
    assert stage5_lsj.base_key("qui#1") == stage5_lsj.base_key("qui1") == "qui"
    assert stage5_lsj.fold_key("edo#1") == stage5_lsj.fold_key("edo1") == "edo"


def test_stage5_shard_dir_per_language():
    # LSJ (Greek) and Lewis & Short (Latin) are kept in separate shard
    # directories -- separate key spaces, per app/src/components/LemmaPage
    # .astro's `dictShardDir` (the convention stage5/stage7/preflight all
    # key off of, see stage5_lsj.SHARD_DIR's docstring).
    assert stage5_lsj.SHARD_DIR == {"grc": "lsj", "lat": "ls"}


def test_stage5_lat_run_shards_lewis_short_entries(tmp_path, monkeypatch):
    # Mirrors the Greek stage5 shape (div/key streaming, exact/base-match
    # fallback, letter sharding) against a synthetic Lewis & Short fragment
    # in the REAL div1/key TEI shape, confirmed against the live Diogenes
    # file (docs/wave2-latin-design.md §6): <div1 key="..."> instead of
    # LSJ's <div2 key="...">, plus L&S-only tags (itype/gen/sense/...).
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    analyses = {
        "honestum": [
            {"lemma_id": 1, "form": "honestum", "lemma": "honestus", "gloss": "", "parse": "neut nom sg"},
        ],
        "virtutem": [
            {"lemma_id": 2, "form": "virtutem", "lemma": "virtus", "gloss": "", "parse": "fem acc sg"},
        ],
        "qui": [
            # The real Diogenes homonym-marker shape ("qui#1" — see
            # test_stage5_base_key_strips_diogenes_latin_homonym_hash),
            # exercised end-to-end here against L&S's OWN "qui1" key
            # convention.
            {"lemma_id": 3, "form": "qui", "lemma": "qui#1", "gloss": "", "parse": "masc nom sg"},
        ],
    }
    (tmp_path / "stage4" / "analyses.json").write_text(json.dumps(analyses))

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    # "honestus" is an exact-key match; "vi^rtu_s1" (macron marks + a
    # homonym digit, the real L&S key convention) exercises the
    # digit/macron-stripped base-match fallback for lemma "virtus"; "qui1"
    # exercises the '#'-stripped base-match fallback for lemma "qui#1". The
    # fourth entry ("abacus") is never requested, so it must NOT be kept --
    # proving the wanted-only extraction, not just that parsing works.
    ls_xml = (
        '<div1 id="crossAbacus1" orig_id="n0" key="a^ba^cu^s1" n="I" opt="n">'
        '<head extent="full" lang="la" opt="n">abacus</head> '
        '<gen opt="n">m.</gen>'
        '</div1>\n'
        '<div1 id="crossHonestus" orig_id="n1" key="honestus" n="I" opt="n">'
        '<head extent="full" lang="la" opt="n">honestus</head> '
        '<itype opt="n">adj.</itype> '
        '<sense id="n1.0" n="I" level="1" opt="n">honorable, <i>honestus</i></sense>'
        '</div1>\n'
        '<div1 id="crossVirtus" orig_id="n2" key="vi^rtu_s1" n="I" opt="n">'
        '<head extent="full" lang="la" opt="n">virtus</head> '
        '<gen opt="n">f.</gen> '
        '<sense id="n2.0" n="I" level="1" opt="n">manliness, virtue</sense>'
        '</div1>\n'
        '<div1 id="crossQui1" orig_id="n3" key="qui1" n="I" opt="n">'
        '<head extent="full" lang="la" opt="n">qui</head> '
        '<pos opt="n">pron.</pos> '
        '<sense id="n3.0" n="I" level="1" opt="n">who, which</sense>'
        '</div1>\n'
    )
    (diogenes_dir / "lat.ls.perseus-eng1.xml").write_text(ls_xml, encoding="utf-8")

    data = _bekker_manifest_data({
        "language": "lat", "id": "TSTLAT",
        "phi_author": "0474", "phi_work": "055", "latin_edition": "Fixture Latin",
    })
    data["sources"] = _sources()
    data["sources"]["diogenes_data"] = str(diogenes_dir)
    manifest = Manifest(data, Path("TSTLAT.yaml"))

    out_dir = stage5_lsj.run(manifest)
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary["lemmata_needed"] == 3
    assert summary["lsj_entries_kept"] == 3
    assert summary["lemmata_without_entry"] == 0

    lemma_map = json.loads((out_dir / "lemma_map.json").read_text())
    assert lemma_map["honestus"] == ["honestus"]
    assert lemma_map["virtus"] == ["vi^rtu_s1"]  # base-match fallback
    assert lemma_map["qui#1"] == ["qui1"]  # '#'-stripped base-match fallback

    # Sharded under 'ls' (Latin), not 'lsj' (Greek) -- SHARD_DIR.
    h_shard = json.loads((out_dir / "ls" / "h.json").read_text())
    assert h_shard["honestus"]["head"] == "honestus"
    assert "lsj-itype" in h_shard["honestus"]["html"]  # L&S-only tag mapped
    assert "honorable" in h_shard["honestus"]["html"]

    v_shard = json.loads((out_dir / "ls" / "v.json").read_text())
    assert v_shard["vi^rtu_s1"]["head"] == "virtus"

    q_shard = json.loads((out_dir / "ls" / "q.json").read_text())
    assert q_shard["qui1"]["head"] == "qui"

    # The unrequested "abacus" entry must not be kept anywhere.
    assert "abacus" not in json.dumps(h_shard) and "abacus" not in json.dumps(v_shard)
    assert not (out_dir / "ls" / "a.json").exists()


def test_stage5_shard_letter_skips_capital_and_star_like_the_readers_do():
    # Real-build finding (surfaced by the case-fold fix, item 2): the OLD
    # `ch.isalpha()` accepted an uppercase first letter, sharding a
    # capitalized L&S proper-name key ("Py_tha^go^ras") under 'P' -- but
    # every reader (preflight._lsj_shard, data.ts's lsjShard, LemmaPage
    # .astro's lsjShardLetter) skips non-[a-z] characters and looks under
    # 'y'. This pins parity with those three.
    assert stage5_lsj.shard_letter("Py_tha^go^ras") == "y"
    assert stage5_lsj.shard_letter("*a)rxh/") == "a"  # Greek: unaffected, '*' skipped
    assert stage5_lsj.shard_letter("honestus") == "h"
    assert stage5_lsj.shard_letter("123") == "_"


def test_stage5_lat_filters_homonym_fanout(tmp_path, monkeypatch):
    # Wave 2 Batch 1b review finding (highest severity, both content-review
    # gates): base/fold matching attaches EVERY L&S entry sharing a
    # digit/'#'-stripped stem, even when Diogenes' own lemma ('edo#1', not
    # '#2'/'#3') already picked a specific homograph -- "est" was showing
    # edo1 "to eat" (correct) PLUS edo2 "to publish" and edo3 "a glutton"
    # (both wrong), and "sum1" plus its own cross-reference stubs sum2/sum3.
    # This fixture mirrors the REAL Diogenes/L&S data for all four review
    # examples (verified against the live files at /Applications/Diogenes
    # .app/.../lat.ls.perseus-eng1.xml and latin-analyses.txt before writing
    # this test): "est" -> edo#1 + sum#1, "oris" -> os#1, "quod" -> qui#1 +
    # qui#2. Governing principle: THE READER MUST NEVER BE SHOWN A WRONG
    # GLOSS AS IF CERTAIN -- each assertion below is either a correctly
    # narrowed single match, or an explicit multi-entry group (never a
    # wrong entry silently included, never a right one silently dropped
    # down to zero).
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    analyses = {
        "est": [
            # "fut imperat act 3rd sg" (NOT "pres ind act 3rd sg") is the
            # REAL representative parse `_lemma_parse_hints` picks up for
            # "edo#1" from a real full-corpus de-officiis build -- a
            # deliberate regression lock: the first cut of
            # `_analysis_pos_class`'s verb-hint regex ("ind|subj|imp|..")
            # matched neither "imperat" (mood spelled differently) nor a
            # tense-only parse, so it classified this as 'unknown' and
            # skipped POS filtering entirely, leaving edo3 (a noun) in the
            # "est" result on the real corpus even though this exact
            # fixture (with the friendlier "pres ind act 3rd sg" guess)
            # passed. See _VERB_PARSE_RE's docstring for the full story.
            {"lemma_id": 1, "form": "est", "lemma": "edo#1", "gloss": "", "parse": "fut imperat act 3rd sg"},
            {"lemma_id": 2, "form": "est", "lemma": "sum#1", "gloss": "", "parse": "imperf ind act 3rd pl"},
        ],
        "oris": [
            {"lemma_id": 3, "form": "oris", "lemma": "os#1", "gloss": "", "parse": "neut gen sg"},
        ],
        "quod": [
            {"lemma_id": 4, "form": "quod", "lemma": "qui#1", "gloss": "", "parse": "neut nom/acc sg"},
            {"lemma_id": 5, "form": "quod", "lemma": "qui#2", "gloss": "", "parse": "neut nom/acc sg"},
        ],
    }
    (tmp_path / "stage4" / "analyses.json").write_text(json.dumps(analyses))

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    filler = "Long enough sense prose to clear the cross-reference-stub length heuristic. " * 3
    ls_xml = (
        # edo1 "to eat" -- verb, no <pos> tag (itype's trailing conjugation
        # digit is the only signal, exactly like the real entry).
        '<div1 id="crosse^do1" key="e^do1" n="1" opt="n">'
        '<head extent="full" lang="la" opt="n">edo</head>, '
        '<itype opt="n">ēdi, ēsum, 3</itype> '
        f'<sense id="n1.0" n="I" level="1" opt="n">to eat. {filler}</sense>'
        '</div1>\n'
        # edo2 "to publish" -- verb, explicit <pos> (also like the real entry).
        '<div1 id="crosse_do2" key="e_do2" n="2" opt="n">'
        '<head extent="full" lang="la" opt="n">edo</head>, '
        '<itype opt="n">dīdi, dītum, 3</itype>, <pos opt="n">v. a.</pos> '
        f'<sense id="n2.0" n="I" level="1" opt="n">to give out. {filler}</sense>'
        '</div1>\n'
        # edo3 "a glutton" -- NOUN (gen="m."). Must be POS-filtered out for
        # a verb-parsed "est", regardless of how short its entry is.
        '<div1 id="crosse^do3" key="e^do3" n="3" opt="n">'
        '<head extent="full" lang="la" opt="n">edo</head>, <itype opt="n">ōnis</itype>, '
        '<gen opt="n">m.</gen> <sense id="n3.0" n="I" level="1" opt="n">a glutton.</sense>'
        '</div1>\n'
        # sum1 "to be" -- verb, real full entry.
        '<div1 id="crosssum1" key="sum1" n="1" opt="n">'
        '<head extent="full" lang="la" opt="n">sum</head>, <itype opt="n">fūi, esse</itype>, '
        f'<pos opt="n">v. n.</pos> <sense id="n4.0" n="I" level="1" opt="n">to be, exist. {filler}</sense>'
        '</div1>\n'
        # sum2 -- a pure cross-reference stub, no <sense> at all (exactly
        # the real entry's shape: "sum = eum ... v. is.").
        '<div1 id="crosssum2" key="sum2" n="2" opt="n">'
        '<head extent="full" lang="la" opt="n">sum</head> = eum, v. is.'
        '</div1>\n'
        # sum3 -- a trivial one-sense cross-reference stub (the real
        # entry's shape: "in composition, for sub before m; v. sub").
        '<div1 id="crosssum3" key="sum3" n="3" opt="n">'
        '<head extent="full" lang="la" opt="n">sum</head> <itype opt="n">in composition</itype>, '
        'for sub before m; v. sub <sense id="n5.0" n="I" level="1" opt="n">fin.</sense>'
        '</div1>\n'
        # os1 "the mouth" -- neut noun. Same POS/gender as os2, so nothing
        # here can derive which one "oris" means -- both must survive as an
        # explicit ambiguity (memo: "o_s1 not o^s2 if derivable, else
        # labeled" -- not derivable here).
        '<div1 id="crosso_s1" key="o_s1" n="1" opt="n">'
        '<head extent="full" lang="la" opt="n">os</head>, <itype opt="n">ōris</itype>, '
        f'<gen opt="n">n.</gen> <sense id="n6.0" n="I" level="1" opt="n">the mouth. {filler}</sense>'
        '</div1>\n'
        # os2 "a bone" -- neut noun (same class as os1, deliberately).
        '<div1 id="crosso^s2" key="o^s2" n="2" opt="n">'
        '<head extent="full" lang="la" opt="n">os</head>, <itype opt="n">ossis</itype>, '
        f'<gen opt="n">n.</gen> <sense id="n7.0" n="I" level="1" opt="n">a bone. {filler}</sense>'
        '</div1>\n'
        # qui1 "who, which" (relative/interrogative pronoun) -- no <pos>/
        # <gen> at all, exactly like the real entry (itype is the paradigm
        # "quae, quod", not a POS marker this classifier reads).
        '<div1 id="crossQui1" key="qui1" n="1" opt="n">'
        '<head extent="full" lang="la" opt="n">qui</head>, <itype opt="n">quae, quod</itype> '
        f'<sense id="n8.0" n="I" level="1" opt="n">who, which. {filler}</sense>'
        '</div1>\n'
        # qui_2 "how" (interrogative/relative adverb) -- also no <pos>/
        # <gen>/<itype> this classifier reads (the real entry's "adv.
        # interrog." descriptor is inline italic text, not a <pos> tag).
        '<div1 id="crossqui_2" key="qui_2" n="2" opt="n">'
        '<head extent="full" lang="la" opt="n">qui</head>, <i>adv. interrog.</i> '
        f'<sense id="n9.0" n="I" level="1" opt="n">in what manner, how. {filler}</sense>'
        '</div1>\n'
    )
    (diogenes_dir / "lat.ls.perseus-eng1.xml").write_text(ls_xml, encoding="utf-8")

    data = _bekker_manifest_data({
        "language": "lat", "id": "TSTHOMONYM",
        "phi_author": "0474", "phi_work": "056", "latin_edition": "Fixture Latin",
    })
    data["sources"] = _sources()
    data["sources"]["diogenes_data"] = str(diogenes_dir)
    manifest = Manifest(data, Path("TSTHOMONYM.yaml"))

    out_dir = stage5_lsj.run(manifest)
    lemma_map = json.loads((out_dir / "lemma_map.json").read_text())
    missing = json.loads((out_dir / "missing_lemmata.json").read_text())
    assert missing == []

    # est -> edo#1: edo3 (noun) correctly POS-filtered out; edo1/edo2 (both
    # verbs) are a genuine residual ambiguity our own numbering can't
    # resolve further (Diogenes' '#1' doesn't map onto L&S's digit) --
    # explicit ambiguity is the correct, honest outcome here.
    assert sorted(lemma_map["edo#1"]) == sorted(["e^do1", "e_do2"])
    assert "e^do3" not in lemma_map["edo#1"]

    # est -> sum#1: sum2/sum3 are cross-reference stubs, correctly dropped
    # -- cleanly narrows to the single real entry.
    assert lemma_map["sum#1"] == ["sum1"]

    # oris -> os#1: os1 (mouth) and os2 (bone) are both real, substantial,
    # same-POS/same-gender entries -- nothing here can derive which one
    # "oris" means, so both survive as an explicit ambiguity (never a
    # silent, possibly-wrong pick of one).
    assert sorted(lemma_map["os#1"]) == sorted(["o_s1", "o^s2"])

    # quod -> qui#1 AND qui#2: both Diogenes lemmas legitimately match BOTH
    # L&S homographs (qui1 the pronoun, qui_2 the adverb) -- confirms no
    # naive #N -> L&S-digit map was invented (that would have produced
    # qui#1 -> qui1 only, silently dropping qui_2 as a valid answer for
    # BOTH Diogenes lemmas).
    assert sorted(lemma_map["qui#1"]) == sorted(["qui1", "qui_2"])
    assert sorted(lemma_map["qui#2"]) == sorted(["qui1", "qui_2"])


def test_stage5_analysis_pos_class_covers_real_corpus_verb_vocabulary():
    # Locks in the FULL verb-hint vocabulary confirmed against a real
    # corpus build's stage4/analyses.json parse tokens -- see
    # _VERB_PARSE_RE's docstring for the "fut imperat act 3rd sg" story.
    assert stage5_lsj._analysis_pos_class("pres ind act 3rd sg") == "verb"
    assert stage5_lsj._analysis_pos_class("fut imperat act 3rd sg") == "verb"  # "imperat", not "imp"
    assert stage5_lsj._analysis_pos_class("imperf act 3rd sg") == "verb"  # mood OMITTED entirely
    assert stage5_lsj._analysis_pos_class("pres part act masc nom sg") == "verb"  # participle
    assert stage5_lsj._analysis_pos_class("perf pass 3rd pl") == "verb"
    assert stage5_lsj._analysis_pos_class("neut nom/acc sg") == "nominal"
    assert stage5_lsj._analysis_pos_class("masc/fem abl pl") == "nominal"
    assert stage5_lsj._analysis_pos_class("indeclform (conj)") == "particle"
    assert stage5_lsj._analysis_pos_class("") == "unknown"


def test_stage5_grc_hash_in_lemma_fails_loud(tmp_path, monkeypatch):
    # The Greek '#'-absence gate (Wave 2 Batch 1b review finding, item 1): a
    # loud runtime assertion, not a comment -- '#' is Diogenes' Latin-only
    # homonym marker, and Greek's own base/fold strip (_BASE_STRIP,
    # _FOLD_STRIP) silently corrupts a real Greek lemma/key if this ever
    # drifts.
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    analyses = {
        "logos": [
            {"lemma_id": 1, "form": "logos", "lemma": "lo/gos#1", "gloss": "word", "parse": "noun"},
        ],
    }
    (tmp_path / "stage4" / "analyses.json").write_text(json.dumps(analyses))
    manifest = Manifest(_bekker_manifest_data({"id": "TSTHASH"}), Path("TSTHASH.yaml"))
    with pytest.raises(ValueError, match="#"):
        stage5_lsj.run(manifest)


def test_stage5_grc_hash_in_dictionary_key_fails_loud(tmp_path, monkeypatch):
    # Mirror of the lemma-side gate above, on the dictionary side: a
    # grc.lsj.xml key carrying '#' must also fail loud, not silently
    # corrupt the base/fold strip.
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    analyses = {
        "logos": [
            {"lemma_id": 1, "form": "logos", "lemma": "lo/gos", "gloss": "word", "parse": "noun"},
        ],
    }
    (tmp_path / "stage4" / "analyses.json").write_text(json.dumps(analyses))

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    (diogenes_dir / "grc.lsj.xml").write_text(
        '<div2 id="x" key="lo/gos#1" n="1" opt="n">'
        '<head extent="full" lang="greek" opt="n">λόγος</head>'
        '<sense id="n1.0" n="I" level="1" opt="n">word</sense></div2>\n',
        encoding="utf-8",
    )
    data = _bekker_manifest_data({"id": "TSTHASH2"})
    data["sources"] = _sources()
    data["sources"]["diogenes_data"] = str(diogenes_dir)
    manifest = Manifest(data, Path("TSTHASH2.yaml"))
    with pytest.raises(ValueError, match="#"):
        stage5_lsj.run(manifest)


def test_stage4_grc_analyses_path_unchanged():
    path = stage4_morphology._analyses_path(_language_manifest("grc"))
    assert path.name == "greek-analyses.txt"


def test_stage4_lat_analyses_path_wired():
    # Wave 2 Batch 0 wires stage4's Latin path (docs/wave2-latin-design.md
    # §6) — this replaces the earlier NotImplementedError expectation, which
    # locked in the pre-Batch-0 stub behavior (Karpathy rule 5: wrong tests
    # get replaced, not appeased).
    path = stage4_morphology._analyses_path(_language_manifest("lat"))
    assert path.name == "latin-analyses.txt"


# --- stage3.run() wired posture for 'lat' (Batch 1a) ------------------------


def test_stage3_lat_run_wired(tmp_path, monkeypatch):
    # Wave 2 Batch 1a wires stage1_latin.py + stage3's "lat" entry in
    # _SPINE_FILENAMES (Cicero's De Officiis, the first real PHI work) --
    # this replaces the earlier NotImplementedError expectation, which
    # locked in the pre-Batch-1a stub behavior (Karpathy rule 5: wrong tests
    # get replaced, not appeased).
    monkeypatch.setattr(stage3_tokenize, "BUILD_DIR", tmp_path)
    (tmp_path / "stage1").mkdir()
    spine = {
        "work": "TSTLAT",
        "segments": [
            {
                "id": "1:1.1", "book": 1, "column": "1.1",
                "lines": [{"n": 1, "text": "Quamquam te, Marce fili"}],
            }
        ],
    }
    (tmp_path / "stage1" / "latin_spine.json").write_text(json.dumps(spine))

    out = stage3_tokenize.run(_language_manifest("lat"))
    tokens_doc = json.loads(out.read_text(encoding="utf-8"))
    tokens = tokens_doc["segments"][0]["lines"][0]["tokens"]
    assert [t["t"] for t in tokens] == ["Quamquam", "te", "Marce", "fili"]
    assert tokens[0]["k"] == "quamquam"  # lexicon defaults on (memo §4.2)


def test_stage3_lat_run_lexicon_false_omits_keys(tmp_path, monkeypatch):
    # The no-lexicon-first posture (memo §4.2, `work.lexicon: false`):
    # tokens carry `t` but no `k` at all, regardless of language.
    monkeypatch.setattr(stage3_tokenize, "BUILD_DIR", tmp_path)
    (tmp_path / "stage1").mkdir()
    spine = {
        "work": "TSTLAT",
        "segments": [
            {
                "id": "1:1.1", "book": 1, "column": "1.1",
                "lines": [{"n": 1, "text": "Quamquam te"}],
            }
        ],
    }
    (tmp_path / "stage1" / "latin_spine.json").write_text(json.dumps(spine))

    manifest = _language_manifest("lat")
    manifest.data["work"]["lexicon"] = False
    out = stage3_tokenize.run(manifest)
    tokens_doc = json.loads(out.read_text(encoding="utf-8"))
    tokens = tokens_doc["segments"][0]["lines"][0]["tokens"]
    assert [t["t"] for t in tokens] == ["Quamquam", "te"]
    assert all("k" not in t for t in tokens)


# --- stage6 fold() fail-loud posture for an unrecognized language ----------


def test_stage6_fold_rejects_unknown_language():
    with pytest.raises(ValueError, match="unsupported language"):
        stage6_search.fold("logos", "xyz")


def test_stage6_fold_dispatches_grc_and_lat():
    assert stage6_search.fold("lo/gos", "grc") == "logos"
    assert stage6_search.fold("uita", "lat") == "uita"
    assert stage6_search.fold("vita", "lat") == "uita"


# --- stage4 integration: whole-form-first vs enclitic-host resolution -----


def test_stage4_lat_resolution_prefers_whole_form_over_enclitic_split(tmp_path, monkeypatch):
    """Integration test (not just a `lookup_variants` unit check) for the
    actual resolution loop in stage4_morphology.run(): a token whose FULL
    surface form is itself a real analyses-table entry (e.g. "quisque", a
    lemma in its own right) must resolve to that whole-form key, never to
    the enclitic-split fallback ("quis"), even though both keys are present
    in the table — whole-form-first order (latin.py's lookup_variants,
    memo §4.1) must actually be honored end-to-end by run(), not merely
    declared correctly by lookup_variants in isolation. A token with NO
    whole-form entry of its own ("virumque") must still fall back to its
    split host ("virum") and resolve, rather than landing in unmatched.json.
    """
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    tokens_doc = {
        "segments": [
            {
                "column": "1.1",
                "lines": [
                    {
                        "n": 1,
                        "tokens": [
                            {"t": "quisque", "k": "quisque"},
                            {"t": "virumque", "k": "virumque"},
                        ],
                    }
                ],
            }
        ]
    }
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps(tokens_doc))

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    (diogenes_dir / "latin-analyses.txt").write_text(
        # "quisque" AND "quis" both have their own entries -- if the split
        # were tried first (or preferred), "quisque" would wrongly resolve
        # to "quis"'s analysis instead of its own.
        "quisque\t{1 9 quisque,quisque\tanyone/anything\tnom sg}\n"
        "quis\t{2 9 quis,quis\twho/what\tnom sg}\n"
        # "virumque" has no entry of its own -- only its split host "virum"
        # does, so resolution must fall back to the split to match at all.
        "virum\t{3 9 virum,vir\tman\tacc sg}\n"
    )

    data = _bekker_manifest_data({"language": "lat", "id": "TSTLAT"})
    data["sources"]["diogenes_data"] = str(diogenes_dir)
    manifest = Manifest(data, Path("TSTLAT.yaml"))

    stage4_morphology.run(manifest)

    key_map = json.loads((tmp_path / "stage4" / "key_map.json").read_text())
    assert key_map["quisque"] == "quisque"  # whole form wins, not "quis"
    assert key_map["virumque"] == "virum"   # falls back to the split host


# --- Blocker 1(b): lexicon:true fail-loud on zero keyed tokens/lemmata (Sol) -


def _empty_tokens_doc() -> dict:
    # Every token is non-lexical (no `k`) — the shape a lexicon-on work
    # would carry if stage3's lexical gate silently produced no keys.
    return {"segments": [{"column": "1.1", "lines": [{"n": 1, "tokens": [{"t": "***"}]}]}]}


def test_stage4_lexicon_true_zero_keyed_tokens_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps(_empty_tokens_doc()))

    data = _bekker_manifest_data({"language": "lat", "id": "TSTLAT", "lexicon": True})
    manifest = Manifest(data, Path("TSTLAT.yaml"))

    with pytest.raises(ValueError, match="zero keyed tokens"):
        stage4_morphology.run(manifest)


def test_stage4_lexicon_false_zero_keyed_tokens_is_the_legitimate_no_op(tmp_path, monkeypatch):
    # The exact same empty-artifact shape as above, but declared
    # `lexicon: false` — must NOT raise (this is what a real no-lexicon
    # work's stage3 output legitimately looks like).
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps(_empty_tokens_doc()))

    data = _bekker_manifest_data({"language": "lat", "id": "TSTLAT", "lexicon": False})
    manifest = Manifest(data, Path("TSTLAT.yaml"))

    out = stage4_morphology.run(manifest)
    summary = json.loads((tmp_path / "stage4" / "summary.json").read_text())
    assert summary["token_match_rate"] is None
    assert json.loads(out.read_text()) == {}


def test_stage5_lexicon_true_zero_lemmata_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    (tmp_path / "stage4" / "analyses.json").write_text("{}")

    data = _bekker_manifest_data({"language": "grc", "lexicon": True})
    manifest = Manifest(data, Path("VAL.yaml"))

    with pytest.raises(ValueError, match="zero lemmata"):
        stage5_lsj.run(manifest)


def test_stage5_lexicon_false_zero_lemmata_is_the_legitimate_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(stage5_lsj, "BUILD_DIR", tmp_path)
    (tmp_path / "stage4").mkdir()
    (tmp_path / "stage4" / "analyses.json").write_text("{}")

    data = _bekker_manifest_data({
        "language": "lat", "lexicon": False,
        "phi_author": "0474", "phi_work": "055", "latin_edition": "Fixture Latin",
    })
    manifest = Manifest(data, Path("VAL.yaml"))

    out_dir = stage5_lsj.run(manifest)
    summary = json.loads((out_dir / "summary.json").read_text())
    assert summary == {
        "lemmata_needed": 0, "lsj_entries_kept": 0,
        "shards": 0, "lemmata_without_entry": 0,
    }
