from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.config import Manifest


def _manifest(data: dict) -> Manifest:
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_stephanus_boundary_column_strips_trailing_line():
    # A section manifest with no bekker_range derives its span from the books;
    # a letter-scheme boundary token strips the editorial line ('357a1' -> '357a').
    m = _manifest({
        "citation": {"scheme": "stephanus"},
        "books": [
            {"n": 1, "start": "2a1", "end": "16d5"},
            {"n": 2, "start": "17a1", "end": "27d10"},
        ],
    })
    assert m.first_column == "2a"
    assert m.last_column == "27d"


def test_book_section_boundary_column_is_the_whole_dotted_token():
    # The regression gap 2 guards against: rstrip('0123456789') on "1.1" yields
    # the corrupt "1."; the dotted token has no line component and IS the column.
    m = _manifest({
        "citation": {"scheme": "book-section"},
        "books": [
            {"n": 1, "start": "1.1", "end": "1.28"},
            {"n": 12, "start": "12.1", "end": "12.36"},
        ],
    })
    assert m.first_column == "1.1"
    assert m.last_column == "12.36"


def test_book_section_book_for_column_partitions_by_book():
    m = _manifest({
        "citation": {"scheme": "book-section"},
        "books": [
            {"n": 1, "start": "1.1", "end": "1.28"},
            {"n": 2, "start": "2.1", "end": "2.17"},
        ],
    })
    assert m.book_for_column("1.9") == 1
    assert m.book_for_column("2.1") == 2
    assert m.book_for_column("3.1") is None


def test_duplicate_lettered_fragments_declaration_for_one_book_fails_loudly():
    # Round-2 Hole 3 (Sol): two citation.lettered_fragments entries for the
    # same book must not silently resolve to "whichever comes first" — that
    # hides a manifest-authoring bug (a stray duplicate block) behind
    # correct-looking behavior for whichever entry happens to win.
    m = _manifest({
        "work": {"id": "LIVES"},
        "citation": {
            "scheme": "book-section",
            "lettered_fragments": [
                {"book": 10, "found": ["120a"], "merge": {120: ["120a"]}},
                {"book": 10, "found": ["121a"], "merge": {121: ["121a"]}},
            ],
        },
        "books": [{"n": 10, "start": "10.120", "end": "10.121"}],
    })
    with pytest.raises(ValueError, match="duplicate"):
        m.lettered_fragments_for_book(10)
