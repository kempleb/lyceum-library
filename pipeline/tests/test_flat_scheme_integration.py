"""End-to-end integration of the flat `section` scheme (Epictetus' Enchiridion)
through the REAL stage entry points — the same functions `reader_pipeline all`
invokes: stage1_greek.run -> stage2_validate.run -> stage7_emit.run. (Round 1
of this test called inner helpers like emit_sections directly, which masked
stage7_emit.run's unconditional english_chunks.json load — Sol re-review
round 2.)

The manifest is Enchiridion's real shape: single-book, flat chapter-integer
bounds, and a REAL English primary (model "archive"; "none" is rejected at
preflight for this scheme — see test_scheme.py's flat-manifest guards). No
in-pass English builder exists for the flat scheme yet, so the test writes
stage1/english_chunks.json + alignment.json directly — exactly the
separate-pass contract the stephanus works already use (an English pass
supplies those artifacts after stage1, before stage6/stage7). Stages 3-6 are
not under test; their artifacts are supplied minimally so stage7_emit.run
exercises its full real path (turn/para flow, emit_books, sections, columns,
manifest emission).

Round 1 of this test failed before the round-1 fixes (preflight rejected the
flat book bounds; config._boundary_column, refs.column_prefix_key and stage2's
book partition all broke on bare-integer tokens) and this reworked version
must keep the whole `all`-shaped chain green.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_greek, stage2_validate, stage7_emit
from reader_pipeline.config import Manifest
from reader_pipeline.preflight import WorkManifest, _validate_manifest_schema

FLAT_TEI = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><p>Alpha one.</p></div>
<div type="Chapter" n="2"><div type="section" n="1"><p>Beta two.</p></div></div>
<div type="Chapter" n="3"><p>Gamma three.</p></div>
</body></text></TEI>"""

# The observed spine fingerprint stage2's section_spine baseline pins:
# columns "1", "2", "3" in reading order.
_SPINE_SHA = hashlib.sha256(b"1,2,3").hexdigest()

MANIFEST_DATA = {
    "work": {
        "id": "ENCH",
        "title": "Enchiridion",
        "author": "epictetus",
        "tlg_author": "0557",
        "tlg_work": "002",
        "greek_edition": "Fixture",
    },
    "citation": {"scheme": "section"},
    "english": {
        "primary": {"id": "fx", "name": "Fixture", "model": "archive", "file": "fx.md"},
    },
    "sources": {"tlg_dir_env": "TLG_DIR", "tlg_dir_default": "build"},
    "section_spine": {"count": 3, "sha256": _SPINE_SHA},
    # Exactly ONE book with bare chapter-integer bounds — the flat scheme is
    # bookless and preflight rejects any other book count.
    "books": [{"n": 1, "start": "1", "end": "3"}],
}

SEG_IDS = ["1:1", "1:2", "1:3"]
ENG_TEXTS = {
    "1:1": "Of things, some are in our power.",
    "1:2": "Remember that desire promises attainment.",
    "1:3": "Of each thing that entertains the mind, say what it is.",
}


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _stage_artifacts(build: Path) -> None:
    """The stage1-English / stage3-6 artifacts stage2+stage7 load. The English
    pair simulates the separate English pass (Enchiridion's real shape); the
    stage3-6 files are the minimal valid shapes of stages not under test."""
    # Separate-pass English: one chunk per flat column, 1:1 alignment.
    _write_json(build / "stage1" / "english_chunks.json", {
        "work": "ENCH",
        "translation": "Fixture",
        "chunks": [
            {"id": sid, "book": 1, "column": sid.split(":")[1],
             "text": ENG_TEXTS[sid], "notes": [], "markers": []}
            for sid in SEG_IDS
        ],
        "chapters": [],
    })
    _write_json(build / "stage1" / "alignment.json", {
        "pairs": [{"segment": sid, "english": sid} for sid in SEG_IDS],
        "english_only": [],
    })
    # stage3 tokens: one (empty) token line per segment's synthetic line 1.
    _write_json(build / "stage3" / "tokens.json", {
        "segments": [{"id": sid, "lines": [{"n": 1, "tokens": []}]}
                     for sid in SEG_IDS],
    })
    _write_json(build / "stage3" / "sigla_log.json", [])
    _write_json(build / "stage4" / "analyses.json", {})
    _write_json(build / "stage4" / "key_map.json", {})
    _write_json(build / "stage4" / "unmatched.json", [])
    _write_json(build / "stage4" / "summary.json", {})
    _write_json(build / "stage5" / "lemma_map.json", {})
    _write_json(build / "stage5" / "summary.json", {"lsj_entries_kept": 0})
    _write_json(build / "stage5" / "missing_lemmata.json", [])
    for name in ("lemma.json", "form.json", "english.json", "meta.json", "form_lemmata.json"):
        _write_json(build / "stage6" / name, {})


def test_flat_work_through_real_stage_entry_points(tmp_path, monkeypatch):
    build = tmp_path / "build"
    monkeypatch.setenv("CORPUS_VERSION", "fixture-test")

    # Redirect every stage module's build root at the tmp dir. Each module
    # binds `from .config import BUILD_DIR` to its own module global (and
    # stage1_greek derives EXPORT_DIR from it at import time), so each is
    # patched where it is used.
    monkeypatch.setattr(stage1_greek, "BUILD_DIR", build)
    monkeypatch.setattr(stage1_greek, "EXPORT_DIR", build / "export")
    monkeypatch.setattr(stage2_validate, "BUILD_DIR", build)
    monkeypatch.setattr(stage7_emit, "BUILD_DIR", build)

    manifest = Manifest(json.loads(json.dumps(MANIFEST_DATA)),
                        ROOT / "manifests" / "fake.yaml")

    # --- preflight: the real Enchiridion manifest shape passes schema -------
    wm = WorkManifest(work_id="ENCH", path=Path("ENCH.yaml"),
                      data=json.loads(json.dumps(MANIFEST_DATA)))
    problems: list = []
    _validate_manifest_schema(wm, problems)
    assert problems == [], f"preflight rejected the flat manifest: {problems}"
    assert manifest.first_column == "1"
    assert manifest.last_column == "3"

    # --- stage1 (real run): pre-staged export short-circuits Diogenes -------
    export_xml = stage1_greek.exported_xml_path(manifest)
    export_xml.parent.mkdir(parents=True, exist_ok=True)
    export_xml.write_text(FLAT_TEI, encoding="utf-8")
    spine_path = stage1_greek.run(manifest)
    spine = json.loads(spine_path.read_text(encoding="utf-8"))
    assert [s["id"] for s in spine["segments"]] == SEG_IDS
    assert [s["book"] for s in spine["segments"]] == [1, 1, 1]
    assert spine["unassigned_lines"] == []

    # --- English pass + stages 3-6 artifacts (see _stage_artifacts) ---------
    _stage_artifacts(build)

    # --- stage2 (real run): the full validation report must PASS ------------
    stage2_validate.run(manifest)
    report = json.loads(
        (build / "stage2" / "validation_report.json").read_text(encoding="utf-8"))
    assert report["ok"], {k: v for k, v in report["checks"].items() if not v.get("ok")}

    # --- stage7 (real run — the entry point `reader_pipeline all` calls, and
    # the one that loads english_chunks.json unconditionally) ----------------
    out_dir = stage7_emit.run(manifest)
    assert out_dir == build / "dist" / "ENCH"

    book = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    assert book["book"] == 1
    assert [s["id"] for s in book["segments"]] == SEG_IDS
    for seg in book["segments"]:
        assert seg["greek"][0]["text"]
        assert seg["english"]["text"] == ENG_TEXTS[seg["id"]]

    sections = json.loads((out_dir / "sections.json").read_text(encoding="utf-8"))
    assert list(sections.keys()) == ["1"]
    assert [e["column"] for e in sections["1"]] == ["1", "2", "3"]
    assert [e["page"] for e in sections["1"]] == [1, 2, 3]
    # Flat columns have no section letter: the key is OMITTED, never null
    # (SectionRef.letter in shared/lib/data.ts is an optional string).
    assert all("letter" not in e for e in sections["1"])

    chapters = json.loads((out_dir / "chapters.json").read_text(encoding="utf-8"))
    assert chapters == {}  # section-scheme works navigate by sections.json

    columns = json.loads((out_dir / "columns.json").read_text(encoding="utf-8"))
    assert set(columns.keys()) == {"1", "2", "3"}
    assert columns["2"] == [{"book": 1, "lo": 1, "hi": 1}]

    emitted = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert emitted["schema_version"] == "manifest.v1"
    assert emitted["id"] == "ENCH"
    assert emitted["author"] == "epictetus"
    assert emitted["title"] == "Enchiridion"
    assert emitted["language"] == "grc"
    assert emitted["route"] == "/epictetus/ENCH"
    assert emitted["citation"] == {
        "scheme": "section",
        "books": [{"n": 1, "start": "1", "end": "3"}],
    }
    assert emitted["editions"] == [{
        "language": "grc",
        "edition": "Fixture",
        "source": {"kind": "tlg", "author": "0557", "work": "002"},
        "license": {"status": "unverified"},
    }]
    assert emitted["translations"] == [{
        "id": "fx",
        "name": "Fixture",
        "slot": "primary",
        "default": True,
        "alignment": "archive",
        "license": {"status": "unverified"},
    }]
    assert emitted["apparatus"] == {
        "footnotes": False,
        "sidenotes": False,
        "paratext": False,
        "figures": False,
        "sections": True,
        "philosophers": False,
    }
    assert emitted["corpus_version"] == "fixture-test"
    assert emitted["work"]["id"] == "ENCH"
    assert emitted["books"] == [
        {"book": 1, "segments": 3, "first_column": "1", "last_column": "3"},
    ]
