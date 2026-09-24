"""Regression tests for tools/build_hicks_epicurus_letters.py -- the direct
re-key of hicks-lives.clean.json's Book X 10.<n> entries into this corpus's
flat-scheme "<letter-id>:<n>" column tokens for the three Epicurus letters.

No network. Two kinds of test here:
  * unit tests against a small synthetic `lives` dict (monkeypatched via
    `_load_lives`), covering the missing-key and boundary-assertion failure
    paths without touching the real store;
  * a real-source test (skipped if sources/hicks-dl/hicks-lives.clean.json
    is absent) that runs the actual build and checks counts, the "who are
    unable to study" acceptance string, and determinism.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "build_hicks_epicurus_letters", _TOOLS / "build_hicks_epicurus_letters.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["build_hicks_epicurus_letters"] = m
_spec.loader.exec_module(m)

_LIVES_PATH = Path(__file__).resolve().parent.parent.parent / "sources/hicks-dl/hicks-lives.clean.json"
_requires_source = pytest.mark.skipif(
    not _LIVES_PATH.exists(), reason="sources/hicks-dl/hicks-lives.clean.json not present",
)


def _synthetic_lives() -> dict[str, str]:
    lives = {}
    lives["10.35"] = "“For those who are unable to study carefully, here is the epitome.”"
    for n in range(36, 83):
        lives[f"10.{n}"] = f"Herodotus section {n}."
    lives["10.83"] = (
        "The letter's real last sentence. Such is his epistle on Physics. "
        "Next comes the “epistle on Celestial Phenomena.” "
        "“Epicurus to Pythocles, greeting.”"
    )
    lives["10.84"] = "“In your letter to me, Pythocles, you ask...”"
    for n in range(85, 116):
        lives[f"10.{n}"] = f"Pythocles section {n}."
    lives["10.116"] = "The letter's clean final sentence, no trailing matter."
    lives["10.122"] = "“Let no one be slow to seek wisdom when he is young.”"
    for n in range(123, 135):
        lives[f"10.{n}"] = f"Menoeceus section {n}."
    lives["10.135"] = (
        "The letter's real last sentence. Such are his views on life and "
        "conduct; and he has discoursed upon them at greater length elsewhere."
    )
    return lives


def test_build_produces_expected_key_counts(monkeypatch):
    monkeypatch.setattr(m, "_load_lives", _synthetic_lives)
    letters, meta = m.build()
    assert len(letters) == 49 + 33 + 14
    assert letters["letter-to-herodotus:35"].startswith("“For those who are unable")
    assert letters["letter-to-pythocles:84"].startswith("“In your letter to me")
    assert letters["letter-to-menoeceus:122"].startswith("“Let no one be slow")
    assert meta["letters"]["letter-to-herodotus"]["count"] == 49
    assert meta["letters"]["letter-to-pythocles"]["count"] == 33
    assert meta["letters"]["letter-to-menoeceus"]["count"] == 14


def test_boundary_matter_recorded_only_where_it_exists(monkeypatch):
    monkeypatch.setattr(m, "_load_lives", _synthetic_lives)
    _, meta = m.build()
    hdt = meta["letters"]["letter-to-herodotus"]["boundary_matter"]
    assert hdt["kept_verbatim"] is True
    assert "Epicurus to Pythocles, greeting" in hdt["trailing_non_letter_text"]

    pyth = meta["letters"]["letter-to-pythocles"]["boundary_matter"]
    assert pyth["kept_verbatim"] is False
    assert pyth["trailing_non_letter_text"] is None

    men = meta["letters"]["letter-to-menoeceus"]["boundary_matter"]
    assert men["kept_verbatim"] is True
    assert "discoursed upon them at greater length" in men["trailing_non_letter_text"]


def test_missing_expected_section_fails_loud(monkeypatch):
    lives = _synthetic_lives()
    del lives["10.50"]
    monkeypatch.setattr(m, "_load_lives", lambda: lives)
    with pytest.raises(SystemExit, match="10.50"):
        m.build()


def test_empty_expected_section_fails_loud(monkeypatch):
    lives = _synthetic_lives()
    lives["10.50"] = "   "
    monkeypatch.setattr(m, "_load_lives", lambda: lives)
    with pytest.raises(SystemExit, match="10.50"):
        m.build()


def test_boundary_opening_assertion_fires_on_drift(monkeypatch):
    lives = _synthetic_lives()
    lives["10.35"] = "Some other opening text entirely."
    monkeypatch.setattr(m, "_load_lives", lambda: lives)
    with pytest.raises(AssertionError, match="expected 10.35 to open with"):
        m.build()


def test_boundary_trailing_assertion_fires_on_drift(monkeypatch):
    lives = _synthetic_lives()
    lives["10.83"] = "“For those who are unable to study carefully.” No trailing matter at all."
    monkeypatch.setattr(m, "_load_lives", lambda: lives)
    with pytest.raises(AssertionError, match="expected 10.83 to end with"):
        m.build()


@_requires_source
def test_real_source_counts_and_who_are_unable_string():
    letters, meta = m.build()
    assert len(letters) == 96
    assert "who are unable to study" in letters["letter-to-herodotus:35"]
    assert set(meta["letters"]) == {
        "letter-to-herodotus", "letter-to-pythocles", "letter-to-menoeceus",
    }


@_requires_source
def test_real_source_build_is_deterministic():
    letters1, meta1 = m.build()
    letters2, meta2 = m.build()
    assert json.dumps(letters1, sort_keys=True) == json.dumps(letters2, sort_keys=True)
    assert json.dumps(meta1, sort_keys=True) == json.dumps(meta2, sort_keys=True)
