from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_latin import _parse_book_section, parse_spine


SCHEME = scheme_mod.for_manifest(
    {
        "citation": {
            "scheme": "book-section",
            "div_types": {"page": "book", "section": "section"},
        }
    }
)


def _manifest(citation_extra: dict | None = None) -> Manifest:
    citation = {
        "scheme": "book-section",
        "div_types": {"page": "book", "section": "section"},
        "title_labels": [],
    }
    citation.update(citation_extra or {})
    return Manifest(
        {
            "work": {
                "id": "OFF",
                "phi_author": "0474",
                "phi_work": "055",
                "latin_edition": "Fixture",
                "language": "lat",
            },
            "citation": citation,
            "books": [{"n": 1, "start": "1.1", "end": "1.1"}],
        },
        ROOT / "manifests" / "fake.yaml",
    )


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


def _write_xml(tmp_path: Path, xml: str) -> Path:
    path = tmp_path / "fixture.xml"
    path.write_text(xml, encoding="utf-8")
    return path


def test_lined_latin_leaf_column_emits_wrap_and_indent(tmp_path):
    path = _write_xml(
        tmp_path,
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="1">
<l n="1">Esse quis-</l>
<l n="2">quam restat.</l>
<l n="3" rend="indent(2)">Linea incisa.</l>
</div>
</div>
</body></text></TEI>""",
    )

    spine = parse_spine(path, _manifest({"lined_source": True}))

    assert spine["segments"] == [
        {
            "id": "1:1.1",
            "book": 1,
            "column": "1.1",
            "lines": [
                {
                    "n": 1,
                    "text": "Esse quisquam",
                    "joined": True,
                    "wrap": 4,
                    "wrapO": 5,
                },
                {"n": 2, "text": "restat."},
                {"n": 3, "text": "Linea incisa.", "indent": 2},
            ],
        }
    ]
    # Latin's identity fold leaves the line-final s in "quis-" unchanged.
    assert spine["segments"][0]["lines"][0]["text"].startswith("Esse quisq")


def test_non_lined_latin_spine_keeps_head_shape_byte_for_byte(tmp_path):
    path = _write_xml(
        tmp_path,
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="1"><p>Esse quis- quam restat.</p></div>
</div>
</body></text></TEI>""",
    )

    actual = json.dumps(
        parse_spine(path, _manifest()), ensure_ascii=False, indent=1
    ).encode("utf-8")
    expected = json.dumps(
        {
            "work": "OFF",
            "edition": "Fixture",
            "segments": [
                {
                    "id": "1:1.1",
                    "book": 1,
                    "column": "1.1",
                    "lines": [{"n": 1, "text": "Esse quisquam restat."}],
                }
            ],
            "headings": [],
            "unassigned_lines": [],
        },
        ensure_ascii=False,
        indent=1,
    ).encode("utf-8")

    assert actual == expected
    assert not any(
        key in actual.decode("utf-8")
        for key in ('"joined"', '"wrap"', '"wrapO"', '"indent"')
    )


def test_lined_source_with_cross_section_rejoins_is_fatal():
    tree = _tree("<TEI xmlns='http://www.tei-c.org/ns/1.0'/>")
    manifest = _manifest(
        {"lined_source": True, "cross_section_rejoins": 0}
    )

    with pytest.raises(
        ValueError,
        match=r"OFF: citation\.lined_source and citation\.cross_section_rejoins",
    ):
        _parse_book_section(tree, SCHEME, manifest)
