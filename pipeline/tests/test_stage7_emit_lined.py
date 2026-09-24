"""stage7_emit's conditional spread for the lined-source Greek fields
(docs/lined-source-plan.md §3/Stage 2): `sec` present unconditionally
whenever the spine line carries it (every line of a lined chapter always
does); `wrap` and `wrapO` present iff `joined` is (I3; `wrapO` is the
2026-08-29 deviation naming the wrapped token's own offset explicitly, see
the plan's §3 note). Every other work's line carries none of these keys at
all -- byte-identical by construction. Same shape as
test_section_paragraphs_emit.py's coverage of `sections`/`title`/`paras`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage7_emit import chapter_ranges, emit_books


def _spine():
    return {
        "work": "DISC",
        "segments": [
            {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [
                {"n": 1, "text": "alpha beta", "sec": 1, "joined": True, "wrap": 2, "wrapO": 6, "indent": 1},
                {"n": 2, "text": "gamma", "sec": 1},
                {"n": 3, "text": "delta", "sec": 2},
            ]},
            {"id": "1:1.2", "book": 1, "column": "1.2", "lines": [
                {"n": 1, "text": "epsilon"}],
             },
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "1:1.1", "lines": [
                {"n": 1, "tokens": [{"t": "alpha", "o": 0}, {"t": "beta", "o": 6}]},
                {"n": 2, "tokens": [{"t": "gamma", "o": 0}]},
                {"n": 3, "tokens": [{"t": "delta", "o": 0}]},
            ]},
            {"id": "1:1.2", "lines": [{"n": 1, "tokens": [{"t": "epsilon", "o": 0}]}]},
        ],
    }


def _emit(tmp_path):
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), out_dir)
    return json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))


def test_sec_present_on_every_lined_line_unconditionally(tmp_path):
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    greek = by_col["1.1"]["greek"]
    assert [g["sec"] for g in greek] == [1, 1, 2]


def test_wrap_present_only_alongside_joined(tmp_path):
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    greek = by_col["1.1"]["greek"]
    assert greek[0]["joined"] is True and greek[0]["wrap"] == 2
    assert "wrap" not in greek[1]
    assert "joined" not in greek[1]
    assert "wrap" not in greek[2] and "joined" not in greek[2]


def test_wrapo_present_only_alongside_joined(tmp_path):
    # wrapO deviation (2026-08-29, docs/lined-source-plan.md §3): mirrors
    # `wrap`'s own conditional spread exactly.
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    greek = by_col["1.1"]["greek"]
    assert greek[0]["wrapO"] == 6
    assert "wrapO" not in greek[1]
    assert "wrapO" not in greek[2]


def test_non_lined_work_emits_neither_sec_nor_wrap_anywhere(tmp_path):
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    line = by_col["1.2"]["greek"][0]
    assert "sec" not in line and "wrap" not in line and "wrapO" not in line


def test_no_sec_or_wrap_key_appears_in_the_raw_json_for_an_entirely_non_lined_work(tmp_path):
    spine = {
        "work": "MED",
        "segments": [
            {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "alpha"}]},
        ],
    }
    tokens_doc = {"segments": [{"id": "1:1.1", "lines": [{"n": 1, "tokens": []}]}]}
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(spine, tokens_doc, english, chapter_ranges(spine, []), out_dir)
    raw = (out_dir / "book-01.json").read_text(encoding="utf-8")
    assert '"sec"' not in raw
    assert '"wrap"' not in raw
    assert '"wrapO"' not in raw


# --- indent: paragraph-opening first-line inset (John's ruling 2026-08-29) --

def test_indent_present_only_on_the_line_that_carries_it(tmp_path):
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    greek = by_col["1.1"]["greek"]
    assert greek[0]["indent"] == 1
    assert "indent" not in greek[1]
    assert "indent" not in greek[2]


def test_non_lined_work_emits_no_indent_anywhere(tmp_path):
    emitted = _emit(tmp_path)
    by_col = {s["column"]: s for s in emitted["segments"]}
    line = by_col["1.2"]["greek"][0]
    assert "indent" not in line


def test_no_indent_key_appears_in_the_raw_json_for_an_entirely_non_lined_work(tmp_path):
    spine = {
        "work": "MED",
        "segments": [
            {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "alpha"}]},
        ],
    }
    tokens_doc = {"segments": [{"id": "1:1.1", "lines": [{"n": 1, "tokens": []}]}]}
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(spine, tokens_doc, english, chapter_ranges(spine, []), out_dir)
    raw = (out_dir / "book-01.json").read_text(encoding="utf-8")
    assert '"indent"' not in raw
