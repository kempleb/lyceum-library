"""Regression tests for pipeline/tools/extract_jowett_stephanus.py.

These tests use a synthetic mini `plato-dist` tree so the extractor logic is
verified without depending on the real sister-repo build output.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "pipeline" / "tools"
SPEC = importlib.util.spec_from_file_location(
    "extract_jowett_stephanus", TOOLS / "extract_jowett_stephanus.py"
)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules["extract_jowett_stephanus"] = MOD
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def _turn(column: str, reference: str | None, jowett: str | None) -> dict:
    turn = {"g": {"c": column}}
    if reference is not None:
        turn["e"] = reference
    if jowett is None:
        return turn
    turn["alt"] = {"jowett": {"e": jowett}}
    return turn


def _book(*turns: dict) -> dict:
    return {"turnFlow": {"turns": list(turns)}}


def _write_book(path: Path, *turns: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_book(*turns)), encoding="utf-8")


def _build_fixture_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "plato-dist"
    _write_book(
        dist / "Gorgias" / "book-01.json",
        _turn("453a", "  first ref  ", "  First alt  "),
        _turn("453a", "second ref", "Second alt"),
        _turn("453b", "third ref", "Third alt"),
        _turn("453b", "fourth ref", None),
        _turn("453c", "   ", "Ghost alt"),
        _turn("453c", None, None),
        _turn("453d", None, "Lead-in"),
        _turn("453d", "main ref", "  Main alt  "),
    )
    _write_book(
        dist / "Gorgias" / "book-02.json",
        _turn("454a", "fifth ref", "Fifth alt"),
    )
    _write_book(
        dist / "Meno" / "book-01.json",
        _turn("70a", "meno ref", "Meno alt"),
    )
    _write_book(
        dist / "Unmapped Work" / "book-01.json",
        _turn("1a", "ignored ref", "ignored alt"),
    )
    return dist


def test_extract_jowett_stephanus_cli(tmp_path):
    plato_dist = _build_fixture_dist(tmp_path)
    out_dir = tmp_path / "out"

    MOD.main(["--plato-dist", str(plato_dist), "--out", str(out_dir)])

    clean_path = out_dir / "jowett-stephanus.clean.json"
    meta_path = out_dir / "meta.json"
    clean = json.loads(clean_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert list(clean) == sorted(clean)
    assert clean == {
        "gorgias:453a": "First alt Second alt",
        "gorgias:453d": "Lead-in Main alt",
        "gorgias:454a": "Fifth alt",
        "meno:70a": "Meno alt",
    }

    assert meta["source_repo_path"] == str(plato_dist.resolve())
    assert meta["source_store_path"].endswith("sources/perseus-plato/plato-stephanus.clean.json")
    assert meta["unmapped_works"] == ["Unmapped Work"]
    assert meta["generation_parameters"]["coverage_rule"].startswith("covered only when")

    work_list = meta["work_list"]
    assert [item["work"] for item in work_list] == ["Gorgias", "Meno"]
    gorgias = work_list[0]
    meno = work_list[1]
    assert gorgias["slug"] == "gorgias"
    assert gorgias["covered_columns"] == 3
    assert gorgias["omitted_columns"] == 2
    assert gorgias["partial_omitted"] == 1
    assert gorgias["all_null_omitted"] == 1
    assert gorgias["book_files"] == ["book-01.json", "book-02.json"]
    assert meno["slug"] == "meno"
    assert meno["covered_columns"] == 1
    assert meno["omitted_columns"] == 0
    assert meno["partial_omitted"] == 0
    assert meno["all_null_omitted"] == 0


def test_deterministic_two_runs_are_byte_identical(tmp_path):
    plato_dist = _build_fixture_dist(tmp_path)
    out_dir = tmp_path / "out"

    MOD.main(["--plato-dist", str(plato_dist), "--out", str(out_dir)])
    first_clean = (out_dir / "jowett-stephanus.clean.json").read_bytes()
    first_meta = (out_dir / "meta.json").read_bytes()

    MOD.main(["--plato-dist", str(plato_dist), "--out", str(out_dir)])
    assert (out_dir / "jowett-stephanus.clean.json").read_bytes() == first_clean
    assert (out_dir / "meta.json").read_bytes() == first_meta


def test_all_null_columns_are_omitted(tmp_path):
    plato_dist = tmp_path / "plato-dist"
    _write_book(
        plato_dist / "Gorgias" / "book-01.json",
        _turn("453c", None, None),
        _turn("453c", "   ", "Ghost alt"),
    )

    out_dir = tmp_path / "out"
    MOD.main(["--plato-dist", str(plato_dist), "--out", str(out_dir)])
    clean = json.loads((out_dir / "jowett-stephanus.clean.json").read_text(encoding="utf-8"))
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))

    assert clean == {}
    assert meta["work_list"] == [
        {
            "work": "Gorgias",
            "slug": "gorgias",
            "book_files": ["book-01.json"],
            "covered_columns": 0,
            "omitted_columns": 1,
            "partial_omitted": 0,
            "all_null_omitted": 1,
        }
    ]



def test_dialogue_mapping_keys_are_directory_names():
    # plato-reader work directories have no spaces ("HippiasMajor"); a spaced
    # key can never match and silently drops an aligned dialogue.
    for name in MOD._PLATO_DIALOGUES:
        assert " " not in name, f"mapping key {name!r} cannot match a work directory"
    assert "HippiasMajor" in MOD._PLATO_DIALOGUES
    assert "HippiasMinor" in MOD._PLATO_DIALOGUES
