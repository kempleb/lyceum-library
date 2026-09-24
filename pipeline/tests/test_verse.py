"""stage7_emit's conditional verse spread (item 5c): a chunk that carries a
validated `verse` field (see stage1_book_section_english.py's verse-sidecar
support) emits it under `english.verse` in book-NN.json; every other chunk —
and every no-verse work entirely — emits no `verse` key at all, byte-identical
to before this feature existed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage7_emit import chapter_ranges, emit_books


def _spine():
    return {
        "work": "DL",
        "segments": [
            {"id": "7:7.1", "book": 7, "column": "7.1",
             "lines": [{"n": 1, "text": "alpha"}]},
            {"id": "7:7.2", "book": 7, "column": "7.2",
             "lines": [{"n": 1, "text": "beta"}]},
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "7:7.1", "lines": [{"n": 1, "tokens": []}]},
            {"id": "7:7.2", "lines": [{"n": 1, "tokens": []}]},
        ],
    }


def test_verse_key_present_only_on_the_chunk_that_carries_it(tmp_path):
    english = {
        "chunks": [
            {"id": "7:7.1", "book": 7, "column": "7.1", "text": "One two.",
             "notes": [], "markers": [],
             "verse": [{"start": 0, "end": 8, "breaks": [3]}]},
            {"id": "7:7.2", "book": 7, "column": "7.2", "text": "No verse here.",
             "notes": [], "markers": []},
        ],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english,
               chapter_ranges(_spine(), []), out_dir)
    emitted = json.loads((out_dir / "book-07.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["7.1"]["english"]["verse"] == [{"start": 0, "end": 8, "breaks": [3]}]
    assert "verse" not in by_col["7.2"]["english"]


def test_no_verse_work_emits_no_verse_key_anywhere_in_the_json(tmp_path):
    english = {
        "chunks": [
            {"id": "7:7.1", "book": 7, "column": "7.1", "text": "One two.",
             "notes": [], "markers": []},
            {"id": "7:7.2", "book": 7, "column": "7.2", "text": "No verse here.",
             "notes": [], "markers": []},
        ],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english,
               chapter_ranges(_spine(), []), out_dir)
    raw = (out_dir / "book-07.json").read_text(encoding="utf-8")
    assert '"verse"' not in raw


def test_duplicate_line_n_pairs_tokens_positionally_not_by_n_key():
    # CLAUDE.md defect B doubled-merge finding (Lives 8.83/7.160 et al.): a
    # segment with two Greek lines sharing the same `n` (a "doubled section"
    # merge -- two source sections both flatten to a synthetic n=1 line) must
    # keep each line's OWN tokens. Before this fix, emit_books built an
    # `n`-keyed dict (`{l["n"]: l["tokens"] for l in tok_seg["lines"]}`),
    # which silently collapsed the duplicate key so BOTH emitted lines got
    # the second line's tokens -- a real desync (line 1's tokens don't even
    # occur as substrings of line 1's own text) that fails the preflight
    # token-walk gate.
    spine = {
        "work": "DL",
        "segments": [
            {"id": "8:8.83", "book": 8, "column": "8.83", "lines": [
                {"n": 1, "text": "Οὗτος πρῶτος."},
                {"n": 1, "text": "Ἀλκμαίων Κροτωνιάτης."},
            ]},
        ],
    }
    tokens_doc = {
        "segments": [
            {"id": "8:8.83", "lines": [
                {"n": 1, "tokens": [{"t": "Οὗτος", "o": 0, "k": "ou(=tos"}]},
                {"n": 1, "tokens": [{"t": "Ἀλκμαίων", "o": 0, "k": "a)lkmai/wn"}]},
            ]},
        ],
    }
    english = {"chunks": []}
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        emit_books(spine, tokens_doc, english, chapter_ranges(spine, []), out_dir)
        emitted = json.loads((out_dir / "book-08.json").read_text(encoding="utf-8"))
    lines = emitted["segments"][0]["greek"]
    assert lines[0]["tokens"] == [{"t": "Οὗτος", "o": 0, "k": "ou(=tos"}]
    assert lines[1]["tokens"] == [{"t": "Ἀλκμαίων", "o": 0, "k": "a)lkmai/wn"}]
