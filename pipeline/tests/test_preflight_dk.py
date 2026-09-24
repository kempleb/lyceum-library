from __future__ import annotations

import json
import sys
from pathlib import Path

from reader_pipeline import dk_lang
from reader_pipeline import preflight as preflight_mod
from reader_pipeline import scheme as scheme_mod
from reader_pipeline.preflight import (
    WorkManifest,
    _dk_expected_all_context_columns,
    _validate_books,
    _validate_columns,
    _validate_dk_work,
    _validate_manifest_schema,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))


def _decision_key(run_text: str) -> str:
    """Mirrors the real dk-context-lang.json key derivation (see
    dk_lang.decision_key's doc) -- used both to write fixture decision files
    below and to key `_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS` monkeypatches
    the same way the real committed dict is keyed."""
    return dk_lang.decision_key(dk_lang.normalize_run(run_text))


def _stage_decisions(tmp_path, monkeypatch, work_id: str, decisions: dict) -> None:
    """`decisions` is `{run_text: decision}`, test-readable -- converted here
    to the real committed hash-keyed shape (see `_decision_key`/dk_lang.
    decision_key) so the fixture file on disk matches what preflight
    actually loads in production."""
    src = tmp_path / "sources" / work_id
    src.mkdir(parents=True, exist_ok=True)
    hashed = {
        _decision_key(run): {"decision": decision, "note": "test"}
        for run, decision in decisions.items()
    }
    (src / "dk-context-lang.json").write_text(
        json.dumps(hashed, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(preflight_mod, "SOURCES_DIR", tmp_path / "sources")


SCHEME = scheme_mod.get("dk")


def _manifest_data(citation_extra: dict | None = None, with_english: bool = False) -> dict:
    citation = {"scheme": "dk", "series": "B"}
    citation.update(citation_extra or {})
    data = {
        "work": {"id": "HERFIX", "title": "Fixture", "author": "heraclitus",
                 "tlg_author": "9999", "tlg_work": "001", "greek_edition": "Fixture"},
        "citation": citation,
        "sources": {"tlg_dir_env": "TLG_DIR", "tlg_dir_default": "build"},
        "section_spine": {"count": 1, "sha256": "0" * 64},
        "books": [{"n": 1, "start": "B1", "end": "B1"}],
    }
    if with_english:
        data["english"] = {"primary": {"id": "fx", "name": "Fixture", "model": "archive", "file": "fx.json"}}
    return data


def _schema_problems(data: dict) -> list[str]:
    manifest = WorkManifest(work_id="HERFIX", path=Path("HERFIX.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    return [m for _work, _file, m in problems]


# --- manifest schema: dk's Greek-only / bookless carve-outs -----------------

def test_dk_manifest_may_omit_english_entirely():
    assert _schema_problems(_manifest_data()) == []


def test_dk_manifest_with_english_still_requires_well_formed_primary():
    data = _manifest_data()
    data["english"] = {}
    messages = _schema_problems(data)
    assert any("english.primary must be an object" in m for m in messages), messages


def test_dk_manifest_with_well_formed_english_passes():
    assert _schema_problems(_manifest_data(with_english=True)) == []


def test_dk_manifest_requires_series():
    data = _manifest_data()
    del data["citation"]["series"]
    messages = _schema_problems(data)
    assert any("citation.series must be" in m for m in messages), messages


def test_dk_manifest_no_series_rejects_explicit_empty_string_series():
    # citation.series: "" is NOT "series omitted" -- only a genuinely absent
    # (None) series satisfies citation.no_series's contract; an empty
    # string used to slip through this gate silently.
    data = _manifest_data({"no_series": True, "series": ""})
    messages = _schema_problems(data)
    assert any("citation.series must be omitted" in m for m in messages), messages


def test_dk_manifest_no_series_with_no_series_letter_passes():
    data = _manifest_data({"no_series": True})
    del data["citation"]["series"]
    data["books"] = [{"n": 1, "start": "1", "end": "1"}]
    assert _schema_problems(data) == []


def test_dk_manifest_rejects_multiple_books():
    data = _manifest_data()
    data["books"] = [{"n": 1, "start": "B1", "end": "B1"}, {"n": 2, "start": "B2", "end": "B2"}]
    messages = _schema_problems(data)
    assert any("bookless and must declare exactly one book" in m for m in messages), messages


def test_dk_manifest_rejects_non_dk_column_boundary_token():
    data = _manifest_data()
    data["books"] = [{"n": 1, "start": "4.23", "end": "4.24"}]
    messages = _schema_problems(data)
    assert any("dk (Diels-Kranz) column token" in m for m in messages), messages


def test_citation_lines_pre_check_rejects_non_dk_scheme():
    data = {"work": {"id": "X"}, "citation": {"scheme": "bekker", "lines": True}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("only meaningful for scheme 'dk'" in m for m in messages), messages


def test_citation_lines_pre_check_rejects_non_bool():
    data = {"work": {"id": "X"}, "citation": {"scheme": "dk", "series": "B", "lines": "yes"}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("citation.lines must be true or false" in m for m in messages), messages


def test_no_series_with_lines_is_a_collected_problem_not_an_uncaught_crash():
    # scheme.py's for_manifest raises ValueError for this exact, declared-
    # unimplemented combination -- individually each override is legal
    # (both are valid dk overrides on their own), so the earlier
    # citation.lines/citation.no_series pre-checks each pass and, without
    # this dedicated combination check, the raise would escape
    # _validate_manifest_schema uncaught, aborting every other manifest in
    # the same preflight run instead of landing as one collected Problem.
    data = {"work": {"id": "X"}, "citation": {"scheme": "dk", "no_series": True, "lines": True}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)  # must not raise
    messages = [m for _work, _file, m in problems]
    assert any("no_series with citation.lines is not implemented" in m for m in messages), messages


# --- _validate_dk_work: the dist-level gates --------------------------------

def _book(segments: list[dict]) -> dict:
    return {"book": 1, "segments": segments}


def _seg(column: str, greek: list[dict]) -> dict:
    return {"id": f"1:{column}", "book": 1, "column": column, "greek": greek}


def test_grammar_series_gate_flags_wrong_series_prefix():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data(),
    )
    loaded = {"book-01.json": _book([
        _seg("A1", [{"role": "text", "text": "λόγος", "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("does not start with the work's declared citation.series" in m for m in messages), messages


def test_zero_greek_token_gate_flags_undeclared_latin_fragment():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "text", "text": "verba", "tokens": [{"t": "verba", "o": 0}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("zero Greek tokens" in m for m in messages), messages


def test_zero_greek_token_gate_passes_when_declared_latin_fragment():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({"latin_fragments": ["B1"]}),
    )
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "text", "text": "verba", "tokens": [{"t": "verba", "o": 0}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_zero_greek_token_gate_skips_columns_with_no_role_text_at_all():
    # unmarked_columns' concern (memo gate 4), not this gate's -- a column
    # with no role='text' block whatsoever must not ALSO have to be
    # declared latin_fragments.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "λόγος", "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_stale_latin_fragments_declaration_is_flagged():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({"latin_fragments": ["B1"]}),
    )
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "text", "text": "λόγος", "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("stale declaration" in m for m in messages), messages


def test_german_stopword_scan_flags_a_survivor():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "und λόγος",
                      "tokens": [{"t": "und", "o": 0}, {"t": "λόγος", "o": 4, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword" in m for m in messages), messages


# --- unconditional-stopword exemption (Sol blocker S1, Empedocles B142/B101) -

def test_unconditional_stopword_conflict_fails_by_default(tmp_path, monkeypatch):
    # A `citation`-decided run containing an unconditional stopword ("über")
    # with NO matching entry in _DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS is
    # still fatal -- restoring a sacrificed citation decision does not, by
    # itself, get a free pass.
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"über das": "citation"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "über das λόγος",
                      "tokens": [{"t": "über", "o": 0}, {"t": "das", "o": 5},
                                  {"t": "λόγος", "o": 9, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword" in m for m in messages), messages


def test_unconditional_stopword_exact_exemption_passes(tmp_path, monkeypatch):
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"über das": "citation"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        "HERFIX": {_decision_key("über das"): frozenset({"über", "das"})},
    })
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "über das λόγος",
                      "tokens": [{"t": "über", "o": 0}, {"t": "das", "o": 5},
                                  {"t": "λόγος", "o": 9, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_unconditional_stopword_strip_german_cannot_satisfy_the_gate(tmp_path, monkeypatch):
    # The exact run text matches an exemption entry, but the decision is
    # `strip-german`, not `citation`/`keep-latin` -- the exemption's
    # contract requires a REVIEWED, KEPT decision, so deleting the run
    # (strip-german) can never "satisfy" the gate by coincidentally matching
    # the exemption's text. Simulated directly against emitted JSON
    # (independent of stage1, which should have stripped the run entirely
    # under a real strip-german decision).
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"über das": "strip-german"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        "HERFIX": {_decision_key("über das"): frozenset({"über", "das"})},
    })
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "über das λόγος",
                      "tokens": [{"t": "über", "o": 0}, {"t": "das", "o": 5},
                                  {"t": "λόγος", "o": 9, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword" in m for m in messages), messages


def test_unconditional_stopword_exemption_is_bound_to_exact_run_text(tmp_path, monkeypatch):
    # A DIFFERENT run's normalized text merely contains "über" but isn't the
    # exact declared exemption key -- still fatal, proving the exemption is
    # bound to exact run text, not just the word.
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"über allgemein gesagt": "citation"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        "HERFIX": {_decision_key("über das"): frozenset({"über", "das"})},  # different key
    })
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "über allgemein gesagt λόγος",
                      "tokens": [{"t": "über", "o": 0}, {"t": "λόγος", "o": 20, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword" in m for m in messages), messages


# --- unconditional-stopword exemption MECHANISM, synthetic only (re-review
# finding: the ORIGINAL versions of these tests exercised the real,
# committed `_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS["anaxagoras-testimonia"]`
# ("Hier."/Hieronymus, Wave 1b) and `[...]["antiphon-sophist-testimonia"]`
# ("der", A6, Wave 1c Sophists batch 2) entries DIRECTLY, not monkeypatched
# -- which required embedding the exact Pliny/Eusebius/Plutarch apparatus
# run text those hashes are keyed to, a hard-rule violation (corpus source
# text is never committed) this test file must not repeat. The REAL A6/
# Hieronymus entries are instead covered at the CORPUS level: the preflight
# gate `npm run build:public` runs as a hard build gate has the actual
# corpus and the actual dk-context-lang.json decisions, and validates the
# real hashes against real data there -- a typo or accidental deletion of
# either literal key in preflight.py's real dict fails THAT gate, not a
# local unit test. What belongs here instead is coverage of the MECHANISM
# itself: an invented work id and invented (never real) run text standing
# in for the real A6/Hieronymus shape, proving exact-run-hash match passes,
# a different run sharing the same stopword still fails, and a
# `strip-german` decision can never satisfy the exemption even when its
# hash matches. ----------------------------------------------------------

def _synth_exempt_manifest_data(work_id: str) -> dict:
    return {
        "work": {"id": work_id, "title": "Fixture", "author": "fixture-author",
                 "tlg_author": "9999", "tlg_work": "001", "greek_edition": "Fixture"},
        "citation": {"scheme": "dk", "series": "A"},
        "sources": {"tlg_dir_env": "TLG_DIR", "tlg_dir_default": "build"},
        "section_spine": {"count": 1, "sha256": "0" * 64},
        "books": [{"n": 1, "start": "A1", "end": "A1"}],
    }


def test_stopword_exemption_mechanism_exact_run_hash_passes(tmp_path, monkeypatch):
    # Invented stand-in for the real A6/Hieronymus shape: a non-Greek
    # `citation`-decided run carrying an unconditional German stopword,
    # exempted by its own exact sha256-prefix hash -- computed here the
    # same way the real committed dict (and the real decision file) is
    # keyed, via `_decision_key`/dk_lang.decision_key.
    work_id = "SYNTH-EXEMPT-FIX"
    run_text = "Zzq. Fixture Antiquarian Notice IX 42 [Zzyx der Fixturianus]"
    _stage_decisions(tmp_path, monkeypatch, work_id, {run_text: "citation"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        work_id: {_decision_key(run_text): frozenset({"der"})},
    })
    manifest = WorkManifest(work_id=work_id, path=Path("x.yaml"),
                            data=_synth_exempt_manifest_data(work_id))
    loaded = {"book-01.json": _book([
        _seg("A1", [{
            "role": "context", "text": f"λόγος {run_text} ἀλήθεια",
            "tokens": [{"t": "λόγος", "o": 0}, {"t": "ἀλήθεια", "o": 6 + len(run_text) + 1}],
        }]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_stopword_exemption_mechanism_different_run_same_stopword_fails(tmp_path, monkeypatch):
    # A different run merely sharing the same unconditional stopword
    # ("der") -- not the exact declared exemption key -- must still fail
    # loudly: the exemption dict is scoped to exact run text, same contract
    # the real A6/Hieronymus entries rely on.
    work_id = "SYNTH-EXEMPT-FIX"
    exempted_run = "Zzq. Fixture Antiquarian Notice IX 42 [Zzyx der Fixturianus]"
    other_run = "Zzq. Fixture Antiquarian Notice IX 99 [Zzyx der Otherus]"
    _stage_decisions(tmp_path, monkeypatch, work_id, {other_run: "citation"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        work_id: {_decision_key(exempted_run): frozenset({"der"})},
    })
    manifest = WorkManifest(work_id=work_id, path=Path("x.yaml"),
                            data=_synth_exempt_manifest_data(work_id))
    loaded = {"book-01.json": _book([
        _seg("A1", [{
            "role": "context", "text": f"λόγος {other_run} ἀλήθεια",
            "tokens": [{"t": "λόγος", "o": 0}, {"t": "ἀλήθεια", "o": 6 + len(other_run) + 1}],
        }]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword(s) ['der']" in m for m in messages), messages


def test_stopword_exemption_mechanism_strip_german_never_satisfies(tmp_path, monkeypatch):
    # The exact run text matches the exemption entry's hash, but the
    # decision is `strip-german`, not `citation`/`keep-latin` -- a
    # REVIEWED, KEPT decision is required, so a decision to delete the run
    # can never "satisfy" the gate merely by hashing to the right key.
    work_id = "SYNTH-EXEMPT-FIX"
    run_text = "Zzq. Fixture Antiquarian Notice IX 42 [Zzyx der Fixturianus]"
    _stage_decisions(tmp_path, monkeypatch, work_id, {run_text: "strip-german"})
    monkeypatch.setattr(preflight_mod, "_DK_UNCONDITIONAL_STOPWORD_EXEMPTIONS", {
        work_id: {_decision_key(run_text): frozenset({"der"})},
    })
    manifest = WorkManifest(work_id=work_id, path=Path("x.yaml"),
                            data=_synth_exempt_manifest_data(work_id))
    loaded = {"book-01.json": _book([
        _seg("A1", [{
            "role": "context", "text": f"λόγος {run_text} ἀλήθεια",
            "tokens": [{"t": "λόγος", "o": 0}, {"t": "ἀλήθεια", "o": 6 + len(run_text) + 1}],
        }]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("German stopword(s) ['der']" in m for m in messages), messages


def test_german_stopword_scan_allows_vgl_nach_covered_by_a_citation_decision(tmp_path, monkeypatch):
    # Scoped exemption (Sol review nit): "vgl."/"nach" pass ONLY when the
    # SPECIFIC non-Greek run they live in is decided `citation` in this
    # work's own decision file. A Greek word between them ("λόγος") splits
    # the text into two separate non-Greek runs, "vgl" and "nach".
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {
        "vgl": "citation",
        "nach": "citation",
    })
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "vgl. λόγος nach ἀλήθεια",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "λόγος", "o": 5, "k": "lo/gos"},
                                  {"t": "nach", "o": 11}, {"t": "ἀλήθεια", "o": 16}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_german_stopword_scan_flags_vgl_nach_with_no_decision_file_at_all(tmp_path, monkeypatch):
    # No decision file -> no run can ever be `citation`-decided -- a global,
    # unreviewed pass is exactly what this nit closes.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "vgl. λόγος nach ἀλήθεια",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "λόγος", "o": 5, "k": "lo/gos"},
                                  {"t": "nach", "o": 11}, {"t": "ἀλήθεια", "o": 16}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("'vgl'" in m for m in messages), messages
    assert any("'nach'" in m for m in messages), messages


def test_german_stopword_scan_allows_vgl_covered_by_a_keep_latin_decision(tmp_path, monkeypatch):
    # Real-corpus shape (Heraclitus B99/B106, Testimonia A13/A19): a run
    # decided `keep-latin` because it's PREDOMINANTLY a Latin bibliographic
    # citation with "vgl."/"Vgl." embedded as the connector between two
    # references -- both `citation` and `keep-latin` are reviewed, KEPT
    # decisions, so both qualify for the exemption.
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"vgl. de fort": "keep-latin"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "vgl. de fort λόγος",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "λόγος", "o": 13, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_german_stopword_scan_flags_vgl_decided_strip_german(tmp_path, monkeypatch):
    # The run IS decided -- just not a KEPT decision -- so the exemption
    # still does not apply: a `strip-german` decision surviving into
    # emitted text at all is exactly the leak this gate exists to catch
    # (stage1 should have removed it; this fixture simulates that failure
    # directly against the emitted JSON, independent of stage1 itself).
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"vgl": "strip-german"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "vgl. λόγος",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "λόγος", "o": 5, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("'vgl'" in m for m in messages), messages


def test_german_stopword_scan_allows_aus_des_covered_by_a_citation_decision(tmp_path, monkeypatch):
    # Sol review blocker S3 (Xenophanes A36/A9's real corpus shapes):
    # "aus" ("THEODORET. IV 5 aus Aëtios" -- "from Aëtios") and "des"
    # ("[Berthelot Collect. des Alchim. gr. I 2]" -- French "Collection des
    # Alchimistes grecs", not German at all) are citation-internal
    # connectors exactly like "bei" -- extending `_DK_BOUNDED_STOPWORDS` so
    # a REVIEWED `citation` decision exempts them too, instead of the
    # unconditional gate stripping the whole attribution as content loss.
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {
        "aus": "citation",
        "des": "citation",
    })
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "aus λόγος des ἀλήθεια",
                      "tokens": [{"t": "aus", "o": 0}, {"t": "λόγος", "o": 4, "k": "lo/gos"},
                                  {"t": "des", "o": 10}, {"t": "ἀλήθεια", "o": 14}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_german_stopword_scan_flags_aus_des_with_no_decision_file_at_all(tmp_path, monkeypatch):
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "aus λόγος des ἀλήθεια",
                      "tokens": [{"t": "aus", "o": 0}, {"t": "λόγος", "o": 4, "k": "lo/gos"},
                                  {"t": "des", "o": 10}, {"t": "ἀλήθεια", "o": 14}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("'aus'" in m for m in messages), messages
    assert any("'des'" in m for m in messages), messages


def test_german_stopword_scan_allows_richtig_covered_by_a_citation_decision(tmp_path, monkeypatch):
    # Grok review defect G3 (Xenophanes A9): EUSEB. Chron. "b) Ol. 59—61
    # [richtig Arm. 60,1 = 540]" -- "richtig" ("correct(ly)") functions as a
    # bare chronological-correction marker (Latin "recte"'s German
    # equivalent), exactly like vgl/nach/bei/aus/des -- a REVIEWED `citation`
    # decision exempts it too, instead of the word silently surviving
    # unchecked (it was never in `_DK_GERMAN_STOPWORDS` OR
    # `_DK_BOUNDED_STOPWORDS` at all before this fix).
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"richtig": "citation"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "richtig λόγος",
                      "tokens": [{"t": "richtig", "o": 0}, {"t": "λόγος", "o": 8, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_german_stopword_scan_flags_richtig_with_no_decision_file_at_all(tmp_path, monkeypatch):
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "richtig λόγος",
                      "tokens": [{"t": "richtig", "o": 0}, {"t": "λόγος", "o": 8, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("'richtig'" in m for m in messages), messages


def test_german_stopword_scan_allows_a_citation_run_reused_across_many_occurrences(tmp_path, monkeypatch):
    # ONE decision-file entry legitimately backs MANY occurrences in the
    # emitted work -- DK's own citation apparatus repeats verbatim across
    # divs (an earlier count-bounded version of this gate undercounted
    # exactly this real-corpus shape; this is the regression test for it).
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"vgl": "citation"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "context", "text": "vgl. λόγος",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "λόγος", "o": 5, "k": "lo/gos"}]}]),
        _seg("B2", [{"role": "context", "text": "vgl. ἀλήθεια",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "ἀλήθεια", "o": 5}]}]),
        _seg("B3", [{"role": "context", "text": "vgl. σοφία",
                      "tokens": [{"t": "vgl", "o": 0}, {"t": "σοφία", "o": 5}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_clean_work_produces_no_problems():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _seg("B1", [{"role": "text", "text": "λόγος", "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]}]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


# --- verse line gate (memo gate 6, Parmenides pilot) ------------------------

VERSE_SCHEME = scheme_mod.for_manifest({"citation": {"scheme": "dk", "lines": True}})


def _verse_seg(column: str, ns_roles: list[tuple[int, str]]) -> dict:
    return _seg(column, [
        {"role": role, "n": n, "text": "λόγος",
         "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]}
        for n, role in ns_roles
    ])


def test_verse_line_gate_accepts_clean_1_to_k_text_lines_with_negative_context():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(-1, "context"), (1, "text"), (2, "text"), (3, "text"), (-2, "context")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    assert problems == []


def test_verse_line_gate_flags_a_gap_in_text_line_numbers():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(1, "text"), (3, "text")]),  # 2 missing
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("not a clean 1..k sequence" in m for m in messages), messages


def test_verse_line_gate_flags_text_lines_not_restarting_at_1():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(2, "text"), (3, "text")]),  # starts at 2
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("not a clean 1..k sequence" in m for m in messages), messages


def test_verse_line_gate_flags_context_line_with_citable_n():
    # A context block whose n collides with the citable (non-negative) line
    # range would let a citation jump / nearest-line snap land on it.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(1, "text"), (2, "context")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("non-negative n" in m for m in messages), messages


def test_verse_line_gate_does_not_run_for_a_lineless_dk_work():
    # Heraclitus-shaped (lineless): synthetic position-index n's on context
    # blocks are 1-based by design and must NOT be flagged.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(1, "context"), (2, "text"), (3, "context")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_bounded_stopword_exemption_survives_a_div_map_label_prefix(tmp_path, monkeypatch):
    # Parmenides B7's real shape: a div_map merge block's synthetic
    # "[Label] " prefix precedes the decided run; without stripping the
    # prefix before re-deriving runs, the label's trailing "] " fuses with
    # the run into a combined string the decision file can't match (a false
    # positive against a correctly decided run).
    _stage_decisions(tmp_path, monkeypatch, "HERFIX", {"PLATO Soph. 237 A vgl. 258D": "citation"})
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "div_map": [
                                {"n": "7,8", "target": "B7", "role": "context",
                                 "position": "leading",
                                 "label": "Alternate source (Plato, Sophist)"},
                            ]}))
    loaded = {"book-01.json": _book([
        _seg("B7", [
            {"role": "context", "n": -1,
             "text": "[Alternate source (Plato, Sophist)] PLATO Soph. 237 A vgl. 258D λόγος",
             "tokens": [{"t": "λόγος", "o": 64, "k": "lo/gos"}]},
            {"role": "text", "n": 1, "text": "λόγος",
             "tokens": [{"t": "λόγος", "o": 0, "k": "lo/gos"}]},
        ]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    assert problems == []


def test_div_map_label_strip_only_matches_the_manifest_declared_label(tmp_path, monkeypatch):
    # Sol review nit (b): the strip must be an EXACT match against this
    # work's own declared citation.div_map labels, not a generic "any
    # leading [...]" regex -- a genuine DK apparatus bracket that ISN'T a
    # div_map label (e.g. a bracketed cross-reference) must NOT be stripped,
    # so a real undecided "vgl" inside it is still caught.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "div_map": [
                                {"n": "7,8", "target": "B7", "role": "context",
                                 "position": "leading", "label": "Alternate source"},
                            ]}))
    loaded = {"book-01.json": _book([
        _seg("B9", [
            # A DIFFERENT bracketed prefix ("[vgl. B 13]") that is NOT the
            # declared div_map label ("Alternate source") -- must survive
            # the strip and still trip the bounded-stopword gate.
            {"role": "text", "n": 1,
             "text": "[vgl. B 13] λόγος",
             "tokens": [{"t": "λόγος", "o": 12, "k": "lo/gos"}]},
        ]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("vgl" in m for m in messages), messages


# --- _dk_expected_all_context_columns: manifest-derived expected set -------
#
# The fix for the GPT-5.6-Sol-High confirm review blocker (2026-07-17):
# preflight independently derives the EXPECTED set of all-context (zero
# citable line) dk columns from the manifest's own declarations, rather than
# trusting an empty *emitted* line set as proof on its own. THE RULE (see
# the function's own doc comment for the full derivation): the expected
# all-context set is exactly `citation.unmarked_columns`, identically for a
# prose fragment work and a verse work (`citation.lines: true`) --
# `verse_text_lines` never implies an all-context column and is irrelevant
# to this derivation.

def test_expected_all_context_columns_is_unmarked_columns_for_prose():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"unmarked_columns": ["B33", "B52"]}))
    assert _dk_expected_all_context_columns(manifest, SCHEME) == {"B33", "B52"}


def test_expected_all_context_columns_is_unmarked_columns_for_verse():
    # Mirrors the real Parmenides shape: B22-B24 declared unmarked, B1-B20
    # declared in verse_text_lines -- the expected set ignores
    # verse_text_lines entirely and is exactly unmarked_columns.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({
                                "lines": True,
                                "verse_text_lines": {"B1": [1, 2, 3]},
                                "unmarked_columns": ["B22", "B23", "B24"],
                            }))
    assert _dk_expected_all_context_columns(manifest, VERSE_SCHEME) == {"B22", "B23", "B24"}


def test_expected_all_context_columns_empty_when_undeclared():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    assert _dk_expected_all_context_columns(manifest, SCHEME) == set()


def test_expected_all_context_columns_empty_for_non_fragment_scheme():
    bekker_scheme = scheme_mod.get("bekker")
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"unmarked_columns": ["B1"]}))
    assert _dk_expected_all_context_columns(manifest, bekker_scheme) == set()


# --- _validate_books / _validate_columns: the dist-level all-context cross-check ---

def test_validate_books_flags_a_verse_column_with_no_citable_lines_and_no_declaration():
    # THE DEFECT CLASS THIS FIX CLOSES: an emission-stage bug lost every
    # citable (role='text') line of B1 after stage1 -- only a negative
    # (context) n survives -- but B1 is NOT declared in unmarked_columns.
    # Before the fix, an empty recomputed line set was trusted on its own
    # and this passed silently as "legitimately all-context".
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([_verse_seg("B1", [(-1, "context")])])}
    problems: list = []
    _validate_books(manifest, loaded, problems, False, set(), VERSE_SCHEME, set())
    messages = [m for _w, _f, m in problems]
    assert any(
        "column B1 has zero citable (role='text') line(s)" in m
        and "not declared in citation.unmarked_columns" in m
        for m in messages
    ), messages


def test_validate_books_flags_a_stale_unmarked_columns_declaration():
    # The other direction of the same two-way-exact contract: B1 is declared
    # all-context, but the emitted data carries a real citable line -- a
    # stale declaration must be caught, not silently ignored.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "unmarked_columns": ["B1"]}))
    loaded = {"book-01.json": _book([_verse_seg("B1", [(1, "text")])])}
    problems: list = []
    _validate_books(manifest, loaded, problems, False, set(), VERSE_SCHEME, {"B1"})
    messages = [m for _w, _f, m in problems]
    assert any(
        "declared in citation.unmarked_columns" in m and "stale unmarked_columns declaration" in m
        for m in messages
    ), messages


def test_validate_books_accepts_a_genuinely_all_context_declared_column():
    # Positive case, the real Parmenides B22-B24 shape: declared unmarked,
    # only negative (context) n's in the emitted data -- no problem.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "unmarked_columns": ["B22"]}))
    loaded = {"book-01.json": _book([_verse_seg("B22", [(-1, "context"), (-2, "context")])])}
    problems: list = []
    _validate_books(manifest, loaded, problems, False, set(), VERSE_SCHEME, {"B22"})
    assert problems == []


def test_validate_books_all_context_cross_check_does_not_apply_to_prose():
    # Regression guard for the false-positive this fix's implementation
    # first produced against the live corpus (174 reports against
    # Heraclitus/Parmenides-testimonia): a lineless (prose) dk work's `n` is
    # a position index assigned to EVERY block regardless of role, so an
    # empty recomputed line set has no bearing on role='text' presence
    # there and must never be cross-checked against unmarked_columns via
    # this signal. Contrived n's below (a prose column would never actually
    # emit a negative n) isolate that the verse-only gate, not incidental
    # non-occurrence, is what suppresses this.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"), data=_manifest_data())
    loaded = {"book-01.json": _book([_verse_seg("B1", [(-1, "context")])])}
    problems: list = []
    _validate_books(manifest, loaded, problems, False, set(), SCHEME, set())
    messages = [m for _w, _f, m in problems]
    assert not any("citation.unmarked_columns" in m for m in messages), messages


def test_validate_columns_flags_missing_entry_for_undeclared_all_context_column():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    segments = {(1, "B1"): {"segment": {}, "lines": set(), "file": "book-01.json"}}
    problems: list = []
    _validate_columns(manifest, {}, segments, problems, VERSE_SCHEME, set())
    messages = [m for _w, _f, m in problems]
    assert any(
        "1:B1 has zero citable lines and no columns.json entry" in m
        and "not declared in citation.unmarked_columns" in m
        for m in messages
    ), messages


def test_validate_columns_flags_stale_declaration_when_entry_carries_lines():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "unmarked_columns": ["B1"]}))
    segments = {(1, "B1"): {"segment": {}, "lines": {1, 2}, "file": "book-01.json"}}
    columns = {"B1": [{"book": 1, "lo": 1, "hi": 2}]}
    problems: list = []
    _validate_columns(manifest, columns, segments, problems, VERSE_SCHEME, {"B1"})
    messages = [m for _w, _f, m in problems]
    assert any(
        "column B1 is declared in citation.unmarked_columns" in m
        and "stale unmarked_columns declaration" in m
        for m in messages
    ), messages


def test_validate_columns_accepts_a_genuinely_all_context_declared_column():
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True, "unmarked_columns": ["B22"]}))
    segments = {(1, "B22"): {"segment": {}, "lines": set(), "file": "book-01.json"}}
    problems: list = []
    _validate_columns(manifest, {}, segments, problems, VERSE_SCHEME, {"B22"})
    assert problems == []


# --- prose_columns mutual exclusion + exhaustive classification (Sol review
# blocker: "prose_columns is self-authorizing in the dist gate" -- a column
# declared prose_columns is, by stage1_greek's own construction, guaranteed
# to never carry a citable line number, so the ordinary dist-level cross-
# checks can never independently catch a wrong prose_columns declaration) --

def test_prose_columns_verse_text_lines_overlap_is_flagged():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({
            "lines": True,
            "prose_columns": ["B1"],
            "verse_text_lines": {"B1": [1]},
        }),
    )
    loaded = {"book-01.json": _book([_verse_seg("B1", [(-1, "context")])])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any(
        "citation.prose_columns declares" in m and "mutually exclusive" in m
        for m in messages
    ), messages


def test_prose_columns_no_overlap_with_verse_text_lines_is_not_flagged():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({
            "lines": True,
            "prose_columns": ["B1"],
            "verse_text_lines": {"B2": [1]},
        }),
    )
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(-1, "context")]),
        _verse_seg("B2", [(1, "text")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert not any("mutually exclusive" in m for m in messages), messages


def test_mixed_work_column_absent_from_every_declared_bucket_is_flagged():
    # A mixed work (non-empty prose_columns) with a THIRD column, B2, that
    # is in none of verse_text_lines/prose_columns/unmarked_columns -- the
    # exact loophole the old code left open: B2's dist shape (a clean
    # citable line) would pass every existing cross-check on its own, but a
    # mixed work must classify every column explicitly, not fall through to
    # the implicit mechanical-walk default.
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({"lines": True, "prose_columns": ["B1"]}),
    )
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(-1, "context")]),
        _verse_seg("B2", [(1, "text")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any(
        "mixed verse+prose work" in m and "['B2']" in m for m in messages
    ), messages


def test_mixed_work_every_column_declared_somewhere_is_not_flagged():
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({
            "lines": True,
            "prose_columns": ["B1"],
            "verse_text_lines": {"B2": [1]},
            "unmarked_columns": ["B3"],
        }),
    )
    loaded = {"book-01.json": _book([
        _verse_seg("B1", [(-1, "context")]),
        _verse_seg("B2", [(1, "text")]),
        _verse_seg("B3", [(-1, "context")]),
    ])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert not any("mixed verse+prose work" in m for m in messages), messages


def test_exhaustive_classification_contract_does_not_apply_to_a_non_mixed_verse_work():
    # No citation.prose_columns declared at all -- an ordinary verse work
    # (e.g. Parmenides) still legitimately relies on the implicit mechanical
    # -walk default for an undeclared column; this contract must not fire.
    manifest = WorkManifest(work_id="HERFIX", path=Path("x.yaml"),
                            data=_manifest_data({"lines": True}))
    loaded = {"book-01.json": _book([_verse_seg("B1", [(1, "text")])])}
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert not any("mixed verse+prose work" in m for m in messages), messages


def test_mixed_work_with_zero_observed_columns_is_flagged_not_vacuously_passed():
    # Re-review finding: `unclassified = seen_columns - declared_union` is
    # trivially the empty set whenever `seen_columns` itself is empty (e.g.
    # every book's dist doc is missing/malformed, or carries no `segments`
    # list at all) -- the OLD code read that as "nothing unclassified" and
    # passed silently, even though the exhaustive-classification contract
    # never actually checked anything against real dist output. A mixed
    # work (non-empty prose_columns) with NO observable columns at all must
    # be flagged in its own right.
    manifest = WorkManifest(
        work_id="HERFIX", path=Path("x.yaml"),
        data=_manifest_data({"lines": True, "prose_columns": ["B1"]}),
    )
    loaded: dict = {}  # no book-01.json at all -> seen_columns stays empty
    problems: list = []
    _validate_dk_work(manifest, loaded, problems, VERSE_SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any(
        "mixed verse+prose work" in m and "no observable columns" in m
        for m in messages
    ), messages
