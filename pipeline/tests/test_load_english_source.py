"""stage1_common.load_english_source: the list-of-records English source
shape (extract_falconer_perseus.py's convention -- [{"section": n, "text":
...}] for a flat scheme, [{"book": n, "section": n, "text": ...}] for
book-section) alongside the pre-existing dict-keyed shape every other
extractor (Miller, Oldfather, ...) produces. Both must normalize to the
same column-token-keyed dict stage1_flat_english/stage1_book_section_english's
`_load_prose` and `validate_english_source` consume -- this is what let
Falconer's De Senectute/De Amicitia/De Divinatione wiring reuse the existing
direct-lookup builders unchanged (see manifests/cato-maior-de-senectute.yaml,
manifests/laelius-de-amicitia.yaml, manifests/de-divinatione.yaml)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage1_common import load_english_source
from reader_pipeline import stage1_book_section_english, stage1_flat_english
from reader_pipeline.config import Manifest


# --- load_english_source: shape normalization ---------------------------

def test_dict_shape_flat_passthrough(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps({"1": "One.", "2": "Two."}), encoding="utf-8")
    assert load_english_source(p) == {"1": "One.", "2": "Two."}


def test_dict_shape_book_section_passthrough(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps({"1.1": "One-one.", "2.1": "Two-one."}), encoding="utf-8")
    assert load_english_source(p) == {"1.1": "One-one.", "2.1": "Two-one."}


def test_list_of_records_flat_shape_normalizes_to_bare_section_keys(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"section": 1, "text": "One."},
        {"section": 2, "text": "Two."},
    ]), encoding="utf-8")
    assert load_english_source(p) == {"1": "One.", "2": "Two."}


def test_list_of_records_book_section_shape_normalizes_to_dotted_keys(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"book": 1, "section": 1, "text": "One-one."},
        {"book": 2, "section": 150, "text": "Two-one-fifty."},
    ]), encoding="utf-8")
    assert load_english_source(p) == {"1.1": "One-one.", "2.150": "Two-one-fifty."}


def test_list_of_records_declared_gap_is_simply_absent(tmp_path):
    # De Divinatione's real shape: Falconer's own extractor leaves 1:25
    # absent from the list rather than fabricating a splice point (see
    # manifests/de-divinatione.yaml's alignment_allow_unmatched: ["1:1.25"]).
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"book": 1, "section": 24, "text": "Twenty-four."},
        {"book": 1, "section": 26, "text": "Twenty-six."},
    ]), encoding="utf-8")
    data = load_english_source(p)
    assert "1.25" not in data
    assert data == {"1.24": "Twenty-four.", "1.26": "Twenty-six."}


# --- load_english_source: MAJOR 3 schema validation (list-of-records only,
# matching the dict shape's own no-op passthrough for anything it doesn't
# itself consume) ------------------------------------------------------------

def test_list_shape_string_section_rejected(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"section": "1", "text": "One."}]), encoding="utf-8")
    with pytest.raises(ValueError, match="non-integer 'section'"):
        load_english_source(p)


def test_list_shape_string_book_rejected(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"book": "1", "section": 1, "text": "One."}]), encoding="utf-8")
    with pytest.raises(ValueError, match="non-integer 'book'"):
        load_english_source(p)


def test_list_shape_bool_section_rejected(tmp_path):
    # bool is an int subclass in Python -- True/False must not silently
    # become key "True"/"False" (or worse, "1"/"0").
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"section": True, "text": "One."}]), encoding="utf-8")
    with pytest.raises(ValueError, match="non-integer 'section'"):
        load_english_source(p)


def test_list_shape_bool_book_rejected(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"book": False, "section": 1, "text": "One."}]), encoding="utf-8")
    with pytest.raises(ValueError, match="non-integer 'book'"):
        load_english_source(p)


def test_list_shape_empty_text_rejected(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"section": 1, "text": ""}]), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid 'text'"):
        load_english_source(p)


def test_list_shape_non_string_text_rejected(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([{"section": 1, "text": None}]), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid 'text'"):
        load_english_source(p)


def test_list_shape_duplicate_normalized_key_raises_with_both_indices(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"book": 1, "section": 1, "text": "First copy."},
        {"book": 1, "section": 2, "text": "Unrelated."},
        {"book": 1, "section": 1, "text": "Second copy -- would silently overwrite."},
    ]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"records 0 and 2 both normalize to key '1\.1'"):
        load_english_source(p)


def test_list_shape_flat_scheme_duplicate_bare_key_raises(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"section": 1, "text": "First."},
        {"section": 1, "text": "Duplicate."},
    ]), encoding="utf-8")
    with pytest.raises(ValueError, match=r"records 0 and 1 both normalize to key '1'"):
        load_english_source(p)


def test_list_shape_unknown_extra_key_tolerated(tmp_path):
    # extract_rackham_fin.py's real records carry a "chapter" key
    # alongside book/section/text -- unrecognized keys must not fail the
    # build, matching the dict shape's leniency toward anything it doesn't
    # itself consume.
    p = tmp_path / "src.json"
    p.write_text(json.dumps([
        {"book": 1, "section": 1, "chapter": "I", "text": "Text."},
    ]), encoding="utf-8")
    assert load_english_source(p) == {"1.1": "Text."}


# --- end-to-end: stage1_flat_english / stage1_book_section_english accept
# --- the list-of-records shape exactly like the dict shape ----------------

FLAT_SPINE = {
    "work": "SEN",
    "segments": [
        {"id": "1:1", "book": 1, "column": "1", "lines": [{"n": 1, "text": "a"}]},
        {"id": "1:2", "book": 1, "column": "2", "lines": [{"n": 1, "text": "b"}]},
    ],
    "unassigned_lines": [],
}

BS_SPINE = {
    "work": "DIV",
    "segments": [
        {"id": "1:1.24", "book": 1, "column": "1.24", "lines": [{"n": 1, "text": "a"}]},
        {"id": "1:1.25", "book": 1, "column": "1.25", "lines": [{"n": 1, "text": "b"}]},
        {"id": "1:1.26", "book": 1, "column": "1.26", "lines": [{"n": 1, "text": "c"}]},
    ],
    "unassigned_lines": [],
}


def _flat_manifest(extra: dict | None = None) -> Manifest:
    data = {
        "work": {"id": "SEN", "title": "Sen", "author": "cicero",
                 "phi_author": "0474", "phi_work": "051", "latin_edition": "Fx"},
        "citation": {"scheme": "section"},
        "english": {"primary": {"id": "falconer", "name": "Falconer Fx",
                                 "model": "archive", "file": "fx/falconer.clean.json"}},
        "books": [{"n": 1, "start": "1", "end": "2"}],
    }
    data.update(extra or {})
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _bs_manifest(extra: dict | None = None) -> Manifest:
    data = {
        "work": {"id": "DIV", "title": "Div", "author": "cicero",
                 "phi_author": "0474", "phi_work": "053", "latin_edition": "Fx"},
        "citation": {"scheme": "book-section"},
        "english": {"primary": {"id": "falconer", "name": "Falconer Fx",
                                 "model": "archive", "file": "fx/falconer.clean.json"}},
        "books": [{"n": 1, "start": "1.24", "end": "1.26"}],
    }
    data.update(extra or {})
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_flat_english_run_accepts_list_of_records_source(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True)
    (src / "fx" / "falconer.clean.json").write_text(json.dumps([
        {"section": 1, "text": "One."},
        {"section": 2, "text": "Two."},
    ]), encoding="utf-8")
    monkeypatch.setattr(stage1_flat_english, "SOURCES_DIR", src)
    monkeypatch.setattr(stage1_flat_english, "BUILD_DIR", tmp_path / "build")
    eng_path, _ = stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["id"] for c in english["chunks"]] == ["1:1", "1:2"]
    assert english["chunks"][1]["text"] == "Two."


def test_book_section_english_run_accepts_list_of_records_source_with_declared_gap(
    tmp_path, monkeypatch,
):
    # Mirrors De Divinatione's real shape: 1:25 absent from the source list,
    # declared via alignment_allow_unmatched rather than silently dropped.
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True)
    (src / "fx" / "falconer.clean.json").write_text(json.dumps([
        {"book": 1, "section": 24, "text": "Twenty-four."},
        {"book": 1, "section": 26, "text": "Twenty-six."},
    ]), encoding="utf-8")
    monkeypatch.setattr(stage1_book_section_english, "SOURCES_DIR", src)
    monkeypatch.setattr(stage1_book_section_english, "BUILD_DIR", tmp_path / "build")
    manifest = _bs_manifest({"alignment_allow_unmatched": ["1:1.25"]})
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["column"] for c in english["chunks"]] == ["1.24", "1.26"]


def test_book_section_english_run_list_shape_undeclared_gap_fails_loud(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True)
    (src / "fx" / "falconer.clean.json").write_text(json.dumps([
        {"book": 1, "section": 24, "text": "Twenty-four."},
        {"book": 1, "section": 26, "text": "Twenty-six."},
    ]), encoding="utf-8")
    monkeypatch.setattr(stage1_book_section_english, "SOURCES_DIR", src)
    monkeypatch.setattr(stage1_book_section_english, "BUILD_DIR", tmp_path / "build")
    with pytest.raises(ValueError, match=r"primary.*1\.25"):
        stage1_book_section_english.run(_bs_manifest(), BS_SPINE)
