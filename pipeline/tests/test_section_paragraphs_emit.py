"""stage7_emit's conditional spread for the Discourses section-paragraph
channels (John's ruling 2026-07-16): a Greek line carrying `sections` (see
stage1_greek._chapter_sections) emits it under `greek[i].sections`; an
English chunk carrying `title`/`paras` (see stage1_book_section_english.py's
titles/paras sidecars) emits them under `english.title`/`english.paras`.
Every other line/chunk — and every work that never opts in at all — emits
none of these keys, byte-identical to before this feature existed. Same
conditional-spread shape as test_verse.py's verse coverage.
"""

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
            {"id": "4:4.1", "book": 4, "column": "4.1",
             "lines": [{"n": 1, "text": "alpha beta", "sections": [
                 {"n": 1, "o": 0}, {"n": 2, "o": 6},
             ]}]},
            {"id": "4:4.2", "book": 4, "column": "4.2",
             "lines": [{"n": 1, "text": "gamma"}]},
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "4:4.1", "lines": [{"n": 1, "tokens": []}]},
            {"id": "4:4.2", "lines": [{"n": 1, "tokens": []}]},
        ],
    }


def test_greek_sections_key_present_only_on_the_line_that_carries_it(tmp_path):
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english,
               chapter_ranges(_spine(), []), out_dir)
    emitted = json.loads((out_dir / "book-04.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["4.1"]["greek"][0]["sections"] == [
        {"n": 1, "o": 0}, {"n": 2, "o": 6},
    ]
    assert "sections" not in by_col["4.2"]["greek"][0]


def test_english_title_and_paras_present_only_on_the_chunk_that_carries_them(tmp_path):
    english = {
        "chunks": [
            {"id": "4:4.1", "book": 4, "column": "4.1", "text": "Alpha beta.",
             "notes": [], "markers": [], "title": "Of freedom",
             "paras": [{"n": 2, "o": 6}]},
            {"id": "4:4.2", "book": 4, "column": "4.2", "text": "Gamma.",
             "notes": [], "markers": []},
        ],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english,
               chapter_ranges(_spine(), []), out_dir)
    emitted = json.loads((out_dir / "book-04.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["4.1"]["english"]["title"] == "Of freedom"
    assert by_col["4.1"]["english"]["paras"] == [{"n": 2, "o": 6}]
    assert "title" not in by_col["4.2"]["english"]
    assert "paras" not in by_col["4.2"]["english"]


def test_no_section_paragraph_work_emits_none_of_these_keys_anywhere(tmp_path):
    spine = {
        "work": "MED",
        "segments": [
            {"id": "4:4.1", "book": 4, "column": "4.1", "lines": [{"n": 1, "text": "alpha"}]},
        ],
    }
    tokens_doc = {"segments": [{"id": "4:4.1", "lines": [{"n": 1, "tokens": []}]}]}
    english = {
        "chunks": [
            {"id": "4:4.1", "book": 4, "column": "4.1", "text": "Alpha.",
             "notes": [], "markers": []},
        ],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(spine, tokens_doc, english, chapter_ranges(spine, []), out_dir)
    raw = (out_dir / "book-04.json").read_text(encoding="utf-8")
    assert '"sections"' not in raw
    assert '"title"' not in raw
    assert '"paras"' not in raw
