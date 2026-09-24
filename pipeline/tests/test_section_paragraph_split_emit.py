"""stage7_emit's conditional spread for the section-paragraph-split override
(item 85's Melissus B7/B8 addendum): a segment whose column is named in the
manifest's `citation.section_paragraph_columns` list emits
`"sectionParagraphSplit": true` at the chunk level; every other segment --
and every work with no such declaration at all -- emits no such key,
byte-identical to before this mechanism existed. Same conditional-spread
posture as test_whole_column_verbatim_emit.py's sibling mechanism (item 65),
but a bare list, not a per-column justified object -- this flag asserts
nothing about authorial voice, only that both sides should paragraph-break
at the same inline "(N)" markers."""

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
            {"id": "1:B7", "book": 1, "column": "B7",
             "lines": [
                 {"n": 1, "text": "Simplicius says. (1)", "role": "context"},
                 {"n": 2, "text": "Melissus speaking. (2) more.", "role": "text"},
                 {"n": 3, "text": ".", "role": "context"},
             ]},
            {"id": "1:B9", "book": 1, "column": "B9",
             "lines": [{"n": 1, "text": "ordinary column", "role": "context"}]},
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "1:B7", "lines": [{"n": 1, "tokens": []}, {"n": 2, "tokens": []}, {"n": 3, "tokens": []}]},
            {"id": "1:B9", "lines": [{"n": 1, "tokens": []}]},
        ],
    }


def test_declared_column_carries_the_flag_on_both_greek_and_english_sides(tmp_path):
    english = {
        "chunks": [
            {"id": "1:B7", "text": "(1) Simplicius says. (2) Melissus speaking more.",
             "notes": [], "markers": []},
            {"id": "1:B9", "text": "Ordinary text.", "notes": [], "markers": []},
        ],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               out_dir, section_paragraph_columns={"B7"})
    emitted = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["B7"]["sectionParagraphSplit"] is True
    assert "sectionParagraphSplit" not in by_col["B9"]
    # One flag per chunk covers the whole segment, not a nested key.
    assert "sectionParagraphSplit" not in by_col["B7"]["english"]
    assert not any("sectionParagraphSplit" in line for line in by_col["B7"]["greek"])


def test_undeclared_column_is_byte_identical_to_no_declaration_at_all(tmp_path):
    english = {
        "chunks": [
            {"id": "1:B7", "text": "(1) Simplicius says. (2) Melissus speaking more.",
             "notes": [], "markers": []},
            {"id": "1:B9", "text": "Ordinary text.", "notes": [], "markers": []},
        ],
    }
    with_dir = tmp_path / "with"
    with_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               with_dir, section_paragraph_columns={"B7"})

    without_dir = tmp_path / "without"
    without_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), without_dir)

    with_raw = json.loads((with_dir / "book-01.json").read_text(encoding="utf-8"))
    without_raw = json.loads((without_dir / "book-01.json").read_text(encoding="utf-8"))
    with_by_col = {s["column"]: s for s in with_raw["segments"]}
    without_by_col = {s["column"]: s for s in without_raw["segments"]}
    b7_with = dict(with_by_col["B7"])
    del b7_with["sectionParagraphSplit"]
    assert b7_with == without_by_col["B7"]
    assert with_by_col["B9"] == without_by_col["B9"]
    assert "sectionParagraphSplit" not in without_by_col["B7"]
    assert "sectionParagraphSplit" not in without_by_col["B9"]


def test_no_key_anywhere_when_the_mechanism_is_absent(tmp_path):
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), out_dir)
    raw = (out_dir / "book-01.json").read_text(encoding="utf-8")
    assert '"sectionParagraphSplit"' not in raw


def test_mechanism_absent_vs_present_but_empty_is_byte_identical(tmp_path):
    english = {"chunks": []}

    absent_dir = tmp_path / "absent"
    absent_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), absent_dir)

    present_dir = tmp_path / "present"
    present_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               present_dir, section_paragraph_columns=set())

    absent_raw = (absent_dir / "book-01.json").read_text(encoding="utf-8")
    present_raw = (present_dir / "book-01.json").read_text(encoding="utf-8")
    assert absent_raw == present_raw
