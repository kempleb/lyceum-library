from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_greek
from reader_pipeline.config import Manifest


def test_run_export_passes_home_to_diogenes(monkeypatch, tmp_path):
    # Diogenes' Base.pm get_user_config_dir dies ("Could not find user
    # profile dir!", exit 25) when HOME is unset; a fresh checkout with an
    # empty build/export hit this at the first TLG work.
    monkeypatch.setattr(stage1_greek, "EXPORT_DIR", tmp_path / "export")
    monkeypatch.setattr(stage1_greek, "RAW_EXPORT_DIR", tmp_path / "export-raw")
    monkeypatch.setenv("HOME", "/Users/someone")

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env")

    monkeypatch.setattr(stage1_greek.subprocess, "run", fake_run)

    manifest = Manifest(
        {
            "work": {"id": "FIX", "tlg_author": "0713", "tlg_work": "001",
                     "export_verse_mode": False},
            "sources": {
                "diogenes_server": "/Applications/Diogenes.app/Contents/server",
                "tlg_dir_env": "TLG_DIR",
                "tlg_dir_default": "../TLG Files/TLG",
            },
        },
        ROOT / "manifests" / "fake.yaml",
    )

    # The fake export writes nothing, so run_export fails its own
    # post-export check; the env it built is what this test asserts on.
    with pytest.raises(FileNotFoundError):
        stage1_greek.run_export(manifest)

    assert captured["env"]["HOME"] == "/Users/someone"


@pytest.mark.parametrize("verse,mode_dir", [(True, "verse"), (False, "plain")])
def test_run_export_passes_y_only_in_verse_mode(monkeypatch, tmp_path, verse, mode_dir):
    # Empedocles' Fragmenta need -y and his Testimonia must not have it, so
    # each mode exports the whole author into its own directory and only
    # this work's file is copied into EXPORT_DIR.
    monkeypatch.setattr(stage1_greek, "EXPORT_DIR", tmp_path / "export")
    monkeypatch.setattr(stage1_greek, "RAW_EXPORT_DIR", tmp_path / "export-raw")
    calls: list = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        outdir = Path(cmd[cmd.index("-o") + 1])
        for work in ("003", "004"):
            f = outdir / "Diogenes-Resources" / "xml" / "tlg" / f"tlg1342{work}.xml"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f"{work} {'-y' in cmd}", encoding="utf-8")

    monkeypatch.setattr(stage1_greek.subprocess, "run", fake_run)
    manifest = Manifest(
        {
            "work": {"id": "FIX", "tlg_author": "1342", "tlg_work": "004",
                     "export_verse_mode": verse},
            "sources": {
                "diogenes_server": "/Applications/Diogenes.app/Contents/server",
                "tlg_dir_env": "TLG_DIR",
                "tlg_dir_default": "../TLG Files/TLG",
            },
        },
        ROOT / "manifests" / "fake.yaml",
    )

    out = stage1_greek.run_export(manifest)

    assert ("-y" in calls[0]) is verse
    assert calls[0][calls[0].index("-o") + 1] == str(tmp_path / "export-raw" / mode_dir)
    assert out.read_text(encoding="utf-8") == f"004 {verse}"
    assert sorted(p.name for p in out.parent.iterdir()) == ["tlg1342004.xml"]


def test_run_export_requires_export_verse_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(stage1_greek, "EXPORT_DIR", tmp_path / "export")
    manifest = Manifest(
        {"work": {"id": "FIX", "tlg_author": "1342", "tlg_work": "004"},
         "sources": {"diogenes_server": "/x"}},
        ROOT / "manifests" / "fake.yaml",
    )
    with pytest.raises(ValueError, match="export_verse_mode"):
        stage1_greek.run_export(manifest)
