from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.preflight import (
    WorkManifest,
    _no_english_allowed,
    _validate_verse_line_work,
)

SCHEME = scheme_mod.for_manifest({"citation": {"scheme": "verse-line", "div_types": {"page": "book"}}})


def _manifest_data(citation_extra: dict | None = None) -> dict:
    citation = {"scheme": "verse-line", "div_types": {"page": "book"}}
    citation.update(citation_extra or {})
    return {
        "work": {
            "id": "DRNFIX", "title": "Fixture", "author": "lucretius",
            "phi_author": "0550", "phi_work": "001", "latin_edition": "Fixture",
            "language": "lat", "no_english": True,
        },
        "citation": citation,
        "books": [{"n": 1, "start": "1.1", "end": "1.4"}],
    }


def _book(segments: list[dict]) -> dict:
    return {"book": 1, "segments": segments}


def _line(text: str, role: str | None = None, tokens: list | None = None) -> dict:
    line = {"n": 1, "text": text, "tokens": tokens if tokens is not None else (
        [] if role == "lacuna" else [{"t": text.split()[0] if text.split() else text, "o": 0}]
    )}
    if role:
        line["role"] = role
    return line


def _seg(column: str, text: str, role: str | None = None, tokens: list | None = None) -> dict:
    return {"id": f"1:{column}", "book": 1, "column": column,
            "greek": [_line(text, role, tokens)]}


def _fingerprint(columns: list[str]) -> dict:
    return {
        "count": len(columns),
        "sha256": hashlib.sha256(",".join(columns).encode("utf-8")).hexdigest(),
    }


COLUMNS = ["1.1", "1.2", "1.3", "1.4"]


def _clean_book():
    return _book([
        _seg("1.1", "Fictum unum"),
        _seg("1.2", "Fictum duo"),
        _seg("1.3", "", role="lacuna"),
        _seg("1.4", "Fictum quattuor"),
    ])


def test_no_english_allowed_for_a_declared_verse_line_work():
    # scheme.numeric_section is False for verse-line (see scheme.py's own
    # doc comment) -- _no_english_allowed must still permit it via the
    # verse_line_scheme branch, mirroring De Officiis' Batch-1a staging.
    assert _no_english_allowed({"no_english": True}, SCHEME) is True
    assert _no_english_allowed({"no_english": False}, SCHEME) is False


def test_clean_book_with_matching_fingerprint_passes():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3"]}, "fingerprint": _fingerprint(COLUMNS)}),
    )
    loaded = {"book-01.json": _clean_book()}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    assert problems == []


def test_post_sort_monotonicity_gate_flags_an_out_of_order_column():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3"]}, "fingerprint": _fingerprint(["1.1", "1.3", "1.2", "1.4"])}),
    )
    loaded = {"book-01.json": _book([
        _seg("1.1", "Fictum unum"),
        _seg("1.3", "", role="lacuna"),
        _seg("1.2", "Fictum duo"),  # out of citation order after 1.3
        _seg("1.4", "Fictum quattuor"),
    ])}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("post-sort monotonicity gate" in m for m in messages), messages


def test_lacuna_declared_but_not_emitted_fails_loudly():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3", "9"]}, "fingerprint": _fingerprint(COLUMNS)}),
    )
    loaded = {"book-01.json": _clean_book()}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("stale (declared but not emitted): ['9']" in m for m in messages), messages


def test_lacuna_emitted_but_not_declared_fails_loudly():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": []}, "fingerprint": _fingerprint(COLUMNS)}),
    )
    loaded = {"book-01.json": _clean_book()}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("undeclared (emitted but not in citation.lacunae): ['3']" in m for m in messages), messages


def test_lacuna_segment_with_tokens_fails_loudly():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3"]}, "fingerprint": _fingerprint(COLUMNS)}),
    )
    loaded = {"book-01.json": _book([
        _seg("1.1", "Fictum unum"),
        _seg("1.2", "Fictum duo"),
        _seg("1.3", "", role="lacuna", tokens=[{"t": "stray", "o": 0}]),
        _seg("1.4", "Fictum quattuor"),
    ])}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("a lacuna must have zero Latin tokens" in m for m in messages), messages


def test_fingerprint_mismatch_fails_loudly():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3"]}, "fingerprint": {"count": 999, "sha256": "0" * 64}}),
    )
    loaded = {"book-01.json": _clean_book()}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("citation.fingerprint mismatch" in m for m in messages), messages


def test_missing_fingerprint_fails_loudly():
    manifest = WorkManifest(
        work_id="DRNFIX", path=Path("x.yaml"),
        data=_manifest_data({"lacunae": {"1": ["3"]}}),
    )
    loaded = {"book-01.json": _clean_book()}
    problems: list = []
    _validate_verse_line_work(manifest, loaded, problems, SCHEME)
    messages = [m for _w, _f, m in problems]
    assert any("citation.fingerprint must be an object" in m for m in messages), messages
