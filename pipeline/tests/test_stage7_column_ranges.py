"""column_line_ranges (stage7_emit.py, columns.json): a dk verse fragment's
role='context' lines carry a non-citable NEGATIVE synthetic n
(stage1_greek._parse_fragments) that must never widen a column's citable
line-number range -- a citation jump / nearest-line snap must never be able
to land on a non-citable context block (Sol review nit (a)). But a column
whose lines are ALL negative (citation.unmarked_columns / prose_columns)
must still get an entry, falling back to its full line set, so a bare
citation to it still resolves (defect found 2026-09-12 by the
navigation-block cross-check)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage7_emit import column_line_ranges


def test_negative_context_line_n_excluded_from_column_range():
    spine = {
        "segments": [
            {"id": "1:B8", "book": 1, "column": "B8", "lines": [
                {"n": -1, "text": "context block", "role": "context"},
                {"n": 1, "text": "text line one", "role": "text"},
                {"n": 2, "text": "text line two", "role": "text"},
            ]},
        ],
    }
    out = column_line_ranges(spine)
    assert out == {"B8": [{"book": 1, "lo": 1, "hi": 2}]}


def test_all_context_column_still_gets_an_entry():
    # Regression test (defect found 2026-09-12 by the navigation-block
    # cross-check): a fragment declared in citation.unmarked_columns (all
    # context, no real citable verse at all -- e.g. Parmenides B22) has no
    # citable line, but the column itself is still real content. A bare
    # citation to it ("Parmenides B22") must still resolve to its book, so
    # it must not be dropped from columns.json entirely -- this used to
    # assert `out == {}`, which was the bug, not the spec.
    spine = {
        "segments": [
            {"id": "1:B22", "book": 1, "column": "B22", "lines": [
                {"n": -1, "text": "context only", "role": "context"},
            ]},
        ],
    }
    out = column_line_ranges(spine)
    assert out == {"B22": [{"book": 1, "lo": -1, "hi": -1}]}


def test_prose_columns_testimonium_still_gets_an_entry():
    # The Critias shape (citation.prose_columns): stage1_greek sets
    # cite_n=None unconditionally for a prose_columns block, exactly like a
    # context block, so every line in the segment carries a negative
    # synthetic n even though the block is a real, contentful testimonium
    # (Critias B31-B73 minus B43). Same fallback as the unmarked-columns
    # case above, multi-line this time.
    spine = {
        "segments": [
            {"id": "1:B31", "book": 1, "column": "B31", "lines": [
                {"n": -1, "text": "first testimonium block", "role": "text"},
                {"n": -2, "text": "second testimonium block", "role": "text"},
            ]},
        ],
    }
    out = column_line_ranges(spine)
    assert out == {"B31": [{"book": 1, "lo": -2, "hi": -1}]}


def test_ordinary_non_dk_scheme_range_unaffected():
    spine = {
        "segments": [
            {"id": "1:1097a", "book": 1, "column": "1097a", "lines": [
                {"n": 1, "text": "alpha"},
                {"n": 15, "text": "omega"},
            ]},
        ],
    }
    out = column_line_ranges(spine)
    assert out == {"1097a": [{"book": 1, "lo": 1, "hi": 15}]}
