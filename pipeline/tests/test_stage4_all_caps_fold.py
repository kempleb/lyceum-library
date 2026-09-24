"""Greek all-caps morphology fallback regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from reader_pipeline import stage4_morphology, stage7_emit
from reader_pipeline.config import Manifest


def test_all_caps_tokens_collect_all_accented_source_matches(tmp_path, monkeypatch):
    """Absent bare keys fall back to every matching accented Morpheus key."""
    monkeypatch.setattr(stage4_morphology, "BUILD_DIR", tmp_path)
    (tmp_path / "stage3").mkdir()
    (tmp_path / "stage3" / "tokens.json").write_text(json.dumps({
        "segments": [{"column": "B3", "lines": [{"n": 1, "tokens": [
            {"t": "ΑΡΧΩΝ", "k": "arxwn"},
            {"t": "ΠΕΡΙ", "k": "peri"},
        ]}]}],
    }))
    diogenes = tmp_path / "diogenes"
    diogenes.mkdir()
    (diogenes / "greek-analyses.txt").write_text(
        "*)/arxwn\t{4 9 *)/arxwn\t \tmasc nom/voc sg}\n"
        "a)rxw=n\t{1 9 a)rxw=n,a)rxh/\trule\tgen pl}\n"
        "a)/rxwn\t{2 9 a)/rxwn,a)/rxwn\truler\tnom sg}\n"
        # The source table can repeat a key; it must not create duplicate
        # cards in the all-caps group.
        "a)/rxwn\t{2 9 a)/rxwn,a)/rxwn\truler\tnom sg}\n"
        "a(/rxwn\t{2 9 a)/rxwn,a)/rxwn\truler\tnom sg}\n"
        "peri/\t{3 9 peri/,peri/\tabout\tpreposition}\n"
        "pe/ri\t{3 9 peri/,peri/\tabout\tpreposition}\n"
    )
    manifest = Manifest({
        "work": {"id": "CAPS", "author": "test", "language": "grc"},
        "books": [{"n": 1, "start": "B1", "end": "B9"}],
        "sources": {"diogenes_data": str(diogenes)},
    }, Path("CAPS.yaml"))

    stage4_morphology.run(manifest)

    analyses = json.loads((tmp_path / "stage4" / "analyses.json").read_text())
    key_map = json.loads((tmp_path / "stage4" / "key_map.json").read_text())
    assert key_map["arxwn"] == "arxwn"
    assert {a["lemma"] for a in analyses["arxwn"]} == {
        "*)/arxwn",
        "a)rxh/",
        "a)/rxwn",
    }
    assert len(analyses["arxwn"]) == 3
    assert all(a["foldedAccent"] is True for a in analyses["arxwn"])
    assert key_map["peri"] == "peri"
    assert len(analyses["peri"]) == 1
    assert analyses["peri"][0]["foldedAccent"] is True

    monkeypatch.setattr(stage7_emit, "BUILD_DIR", tmp_path)
    (tmp_path / "stage5").mkdir()
    (tmp_path / "stage5" / "lemma_map.json").write_text(json.dumps({
        "a)rxh/": ["a)rxh/"],
        "a)/rxwn": ["a)/rxwn"],
    }))
    emitted_dir = tmp_path / "dist"
    emitted_dir.mkdir()
    stage7_emit.emit_analyses(emitted_dir)
    emitted = json.loads((emitted_dir / "analyses.json").read_text())
    assert len(emitted["arxwn"]) == 3
    assert all(a["foldedAccent"] is True for a in emitted["arxwn"])
    assert any(a["lemma"] == "*)/arxwn" for a in emitted["arxwn"])
    assert emitted["peri"][0]["foldedAccent"] is True
