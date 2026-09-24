"""stage6_search.py's form_lemmata.json (John, 2026-09-23 ruling): the
search page's default Lemma mode must accept a word AS PRINTED, not just its
headword. lemma.json is keyed by folded headword only, so typing a printed
inflected form (e.g. Πᾶσα, headword πᾶς) finds nothing today. This file adds
a per-work surface-fold -> headword-fold(s) map the client unions into its
lemma.json lookup (shared/lib/search.ts) -- see its own tests for the
client-side half.

Three cases, mirroring the module docstring's stated contract exactly:
  - a surface form that differs from its headword IS in the map (pasa -> pas)
  - a surface form that EQUALS its headword is OMITTED (texnh: no entry)
  - an ambiguous form (multiple analyses, different lemmata) lists every
    headword, sorted (ambig -> [bar, foo])
"""

from __future__ import annotations

import json
from pathlib import Path

from reader_pipeline import stage6_search
from reader_pipeline.config import Manifest


def _manifest(language: str = "grc") -> Manifest:
    data = {"work": {"id": "TST6", "author": "fixture"}}
    if language != "grc":
        data["work"]["language"] = language
    return Manifest(data, Path("TST6.yaml"))


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _seed(build: Path) -> None:
    # tokens.json: two segments.
    #   s1: "pasa" (surface, differs from its headword "pas") + "texnh"
    #       (surface == its own headword "texnh").
    #   s2: "ambig" — one token whose stored key carries TWO analyses with
    #       different lemmata ("foo", "bar") — an ambiguous surface form.
    _write_json(build / "stage3" / "tokens.json", {
        "segments": [
            {
                "id": "s1", "book": 1, "column": "1094a",
                "lines": [{"n": 1, "tokens": [
                    {"t": "Pasa", "k": "pasa"},
                    {"t": "texnh", "k": "texnh"},
                ]}],
            },
            {
                "id": "s2", "book": 1, "column": "1094b",
                "lines": [{"n": 1, "tokens": [
                    {"t": "ambig", "k": "ambig"},
                ]}],
            },
        ],
    })
    _write_json(build / "stage4" / "key_map.json", {
        "pasa": "pasa", "texnh": "texnh", "ambig": "ambig",
    })
    _write_json(build / "stage4" / "analyses.json", {
        "pasa": [{"lemma": "pas"}],
        "texnh": [{"lemma": "texnh"}],
        "ambig": [{"lemma": "foo"}, {"lemma": "bar"}],
    })


def test_form_lemmata_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(stage6_search, "BUILD_DIR", tmp_path)
    _seed(tmp_path)

    out_dir = stage6_search.run(_manifest())
    form_lemmata = json.loads((out_dir / "form_lemmata.json").read_text(encoding="utf-8"))

    # A surface form ≠ its headword maps to it.
    assert form_lemmata["pasa"] == ["pas"]
    # A surface form == its headword is omitted entirely.
    assert "texnh" not in form_lemmata
    # An ambiguous form lists every headword it could analyze to, sorted.
    assert form_lemmata["ambig"] == ["bar", "foo"]
    # Nothing else sneaks in.
    assert set(form_lemmata) == {"pasa", "ambig"}


def test_form_lemmata_feeds_lemma_json_correctly(tmp_path, monkeypatch):
    """Sanity check that the map's headwords are genuinely lemma.json keys
    (so the client's union-in step actually has postings to union)."""
    monkeypatch.setattr(stage6_search, "BUILD_DIR", tmp_path)
    _seed(tmp_path)

    out_dir = stage6_search.run(_manifest())
    lemma_idx = json.loads((out_dir / "lemma.json").read_text(encoding="utf-8"))
    form_lemmata = json.loads((out_dir / "form_lemmata.json").read_text(encoding="utf-8"))

    for headwords in form_lemmata.values():
        for h in headwords:
            assert h in lemma_idx, f"{h!r} missing from lemma.json"

    assert lemma_idx["pas"] == [[0, 0]]
    assert lemma_idx["foo"] == [[1, 0]]
    assert lemma_idx["bar"] == [[1, 0]]


def test_summary_reports_form_lemmata_count(tmp_path, monkeypatch):
    monkeypatch.setattr(stage6_search, "BUILD_DIR", tmp_path)
    _seed(tmp_path)

    stage6_search.run(_manifest())
    summary = json.loads((tmp_path / "stage6" / "summary.json").read_text())
    assert summary["form_lemmata"] == 2
