"""stage7_emit's conditional spread for the whole-column verbatim override
(REVIEW-CHECKLIST item 65, John's ruling 2026-07-28): a segment whose column
is named in the manifest's `citation.whole_column_verbatim` attestation (see
preflight._whole_column_verbatim_columns) emits `"wholeColumnVerbatim": true`
at the chunk level; every other segment -- and every work with no such
attestation at all -- emits no such key, byte-identical to before this
mechanism existed. Same conditional-spread posture as the `credit` splice
(stage7_emit.py, per-column translation credit) and
test_stage7_context_english.py's coverage of a sibling mechanism."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage7_emit import chapter_ranges, emit_books


def _spine():
    return {
        "work": "FIX",
        "segments": [
            {"id": "1:B11", "book": 1, "column": "B11",
             "lines": [{"n": 1, "text": "Gorgias speaking entire", "role": "context"}]},
            {"id": "1:B12", "book": 1, "column": "B12",
             "lines": [{"n": 1, "text": "ordinary column", "role": "context"}]},
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "1:B11", "lines": [{"n": 1, "tokens": []}]},
            {"id": "1:B12", "lines": [{"n": 1, "tokens": []}]},
        ],
    }


def test_attested_column_carries_the_flag_on_both_greek_and_english_sides(tmp_path):
    english = {
        "chunks": [
            {"id": "1:B11", "text": "Helen text.", "notes": [], "markers": []},
            {"id": "1:B12", "text": "Ordinary text.", "notes": [], "markers": []},
        ],
    }
    whole_column_verbatim = {
        "B11": {"justification": "DK prints this div as continuous Gorgias."},
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               out_dir, whole_column_verbatim=whole_column_verbatim)
    emitted = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["B11"]["wholeColumnVerbatim"] is True
    # One flag per chunk covers the whole segment -- both its Greek and its
    # English -- not a separate key nested under "greek" or "english".
    assert "wholeColumnVerbatim" not in by_col["B11"]["english"]
    assert not any("wholeColumnVerbatim" in line for line in by_col["B11"]["greek"])


def test_unattested_column_is_byte_identical_to_no_attestation_at_all(tmp_path):
    english = {
        "chunks": [
            {"id": "1:B11", "text": "Helen text.", "notes": [], "markers": []},
            {"id": "1:B12", "text": "Ordinary text.", "notes": [], "markers": []},
        ],
    }
    whole_column_verbatim = {
        "B11": {"justification": "DK prints this div as continuous Gorgias."},
    }

    with_attestation_dir = tmp_path / "with"
    with_attestation_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               with_attestation_dir, whole_column_verbatim=whole_column_verbatim)

    no_attestation_dir = tmp_path / "without"
    no_attestation_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               no_attestation_dir)

    with_raw = json.loads((with_attestation_dir / "book-01.json").read_text(encoding="utf-8"))
    without_raw = json.loads((no_attestation_dir / "book-01.json").read_text(encoding="utf-8"))
    with_by_col = {s["column"]: s for s in with_raw["segments"]}
    without_by_col = {s["column"]: s for s in without_raw["segments"]}
    # B11 (attested) differs by exactly the one key.
    b11_with = dict(with_by_col["B11"])
    del b11_with["wholeColumnVerbatim"]
    assert b11_with == without_by_col["B11"]
    # B12 (unattested) is untouched either way.
    assert with_by_col["B12"] == without_by_col["B12"]
    assert "wholeColumnVerbatim" not in without_by_col["B11"]
    assert "wholeColumnVerbatim" not in without_by_col["B12"]


def test_no_key_anywhere_when_the_mechanism_is_absent(tmp_path):
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), out_dir)
    raw = (out_dir / "book-01.json").read_text(encoding="utf-8")
    assert '"wholeColumnVerbatim"' not in raw


def test_mechanism_absent_vs_present_but_empty_is_byte_identical(tmp_path):
    english = {"chunks": []}

    absent_dir = tmp_path / "absent"
    absent_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), absent_dir)

    present_dir = tmp_path / "present"
    present_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               present_dir, whole_column_verbatim={})

    absent_raw = (absent_dir / "book-01.json").read_text(encoding="utf-8")
    present_raw = (present_dir / "book-01.json").read_text(encoding="utf-8")
    assert absent_raw == present_raw
