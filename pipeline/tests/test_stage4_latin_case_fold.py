"""stage4_morphology's Latin lookup — the case-fold fix (Wave 2 Batch 1b
review, item 2, Grok-flagged: 617/930 occurrences). latin-analyses.txt keys
proper names CAPITALIZED (Cicero, Panaetio, Athenis — confirmed against the
live Diogenes file; there is no lowercase entry for any of them), but
to_latin_key always lowercases the surface token, so a proper-name lookup
missed until `_lookup_variants` was wired to also try the capitalized form
(see test_latin.py for the unit-level coverage of `latin.lookup_variants`
itself; this file is the stage4 end-to-end proof against a realistic
tokens.json + latin-analyses.txt pair).
"""

from __future__ import annotations

import json
from pathlib import Path

from reader_pipeline.config import Manifest
from reader_pipeline import stage4_morphology


def _tokens_doc(tokens: list[dict]) -> dict:
    return {
        "segments": [{
            "column": "1.1",
            "lines": [{"n": 1, "tokens": tokens}],
        }],
    }


def _manifest(diogenes_dir: Path) -> Manifest:
    data = {
        "work": {
            "id": "TSTCASEFOLD", "title": "Fixture", "author": "cicero",
            "language": "lat", "phi_author": "0474", "phi_work": "055",
            "latin_edition": "Fixture Latin", "english_translation": "Fixture English",
        },
        "sources": {
            "tlg_dir_env": "TLG_DIR",
            "tlg_dir_default": "../TLG Files/TLG",
            "diogenes_server": "/Applications/Diogenes.app/Contents/server",
            "diogenes_data": str(diogenes_dir),
        },
    }
    return Manifest(data, Path("TSTCASEFOLD.yaml"))


def test_capitalized_proper_name_resolves(tmp_path, monkeypatch):
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    # "cicero" is the lowercased stage3 KEY (to_latin_key always lowercases,
    # memo §4.1) for a surface token that was actually printed "Cicero".
    doc = _tokens_doc([{"t": "Cicero", "o": 0, "k": "cicero"}])
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps(doc), encoding="utf-8")

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    # The REAL Diogenes shape: only the capitalized key exists, exactly
    # like the live latin-analyses.txt (confirmed: grep finds "Cicero" but
    # no "cicero" at all).
    (diogenes_dir / "latin-analyses.txt").write_text(
        "Cicero\t{12902964 9 Cicero_,Cicero\t \tmasc nom/voc sg}\n",
        encoding="utf-8",
    )

    out = stage4_morphology.run(_manifest(diogenes_dir))
    analyses = json.loads(out.read_text(encoding="utf-8"))
    unmatched = json.loads((tmp_path / "stage4" / "unmatched.json").read_text())
    key_map = json.loads((tmp_path / "stage4" / "key_map.json").read_text())

    assert unmatched == []
    assert key_map["cicero"] == "Cicero"
    assert analyses["Cicero"][0]["lemma"] == "Cicero"


def test_genuinely_absent_praenomen_abbreviation_still_misses_gracefully(tmp_path, monkeypatch):
    # Praenomina abbreviations (M., C., L., Q., P., ...) are genuinely
    # absent from latin-analyses.txt under ANY casing -- the case-fold fix
    # does not (and should not) manufacture a match for these; they must
    # still land in unmatched.json exactly as before.
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    doc = _tokens_doc([{"t": "M.", "o": 0, "k": "m."}])
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps(doc), encoding="utf-8")

    diogenes_dir = tmp_path / "diogenes"
    diogenes_dir.mkdir()
    # A realistic file that has OTHER entries but genuinely nothing for
    # "m."/"M." under either casing.
    (diogenes_dir / "latin-analyses.txt").write_text(
        "Cicero\t{12902964 9 Cicero_,Cicero\t \tmasc nom/voc sg}\n",
        encoding="utf-8",
    )

    out = stage4_morphology.run(_manifest(diogenes_dir))
    analyses = json.loads(out.read_text(encoding="utf-8"))
    unmatched = json.loads((tmp_path / "stage4" / "unmatched.json").read_text())

    assert analyses == {}
    assert len(unmatched) == 1
    assert unmatched[0]["key"] == "m."
    assert unmatched[0]["surface"] == "M."
