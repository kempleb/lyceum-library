from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_greek import _parse_flat_chapter, _rejoin_wrapped_hyphens, parse_spine

SCHEME = scheme_mod.get("section")


def _manifest() -> Manifest:
    # Bookless: no "books" boundary table at all — parse_spine's flat_numeric
    # branch assigns every column to book 1 directly, without consulting it.
    return Manifest(
        {
            "work": {"id": "ENCH", "tlg_author": "0557", "tlg_work": "001",
                     "greek_edition": "Fixture"},
            "citation": {"scheme": "section"},
            "books": [],
        },
        ROOT / "manifests" / "fake.yaml",
    )


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


# --- _parse_flat_chapter: XML-shape fidelity ---------------------------------

def test_flattens_a_bookless_chapter_with_no_nested_section():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1">
<p>Alpha beta gamma.</p>
</div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, SCHEME)
    assert headings == []
    assert flat == [{"column": "1", "n": 1, "text": "Alpha beta gamma."}]


def test_nested_sections_flatten_into_the_chapter_not_split_into_columns():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="5">
<div type="section" n="1"><p>First.</p></div>
<div type="section" n="2"><p>Second.</p></div>
</div>
</body></text></TEI>"""
    )
    flat, _ = _parse_flat_chapter(tree, SCHEME)
    assert len(flat) == 1
    assert flat[0]["column"] == "5"
    assert flat[0]["text"] == "First. Second."


def test_print_line_hyphen_wrap_is_rejoined_inside_the_flattened_chapter():
    # CLAUDE.md defect A: the Enchiridion (flat_numeric scheme) shows the
    # same literal "- " print-line-wrap artifact as Discourses (43/53
    # columns measured) for the same reason -- this scheme is also excluded
    # from the cross-line rejoin in parse_spine() (see the numeric_section /
    # flat_numeric guard there), since a chapter here is also flattened to
    # one synthetic line by _line_text() rather than kept as separate lines.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1">
<p>αἰ-</p>
<p>σχύνῃ τὰ σαυτοῦ.</p>
</div>
</body></text></TEI>"""
    )
    flat, _ = _parse_flat_chapter(tree, SCHEME)
    assert flat == [{"column": "1", "n": 1, "text": "αἰσχύνῃ τὰ σαυτοῦ."}]


def test_three_chapters_get_correct_bare_integer_columns_in_document_order():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><p>One.</p></div>
<div type="Chapter" n="2"><p>Two.</p></div>
<div type="Chapter" n="10"><p>Ten.</p></div>
</body></text></TEI>"""
    )
    flat, _ = _parse_flat_chapter(tree, SCHEME)
    assert [f["column"] for f in flat] == ["1", "2", "10"]
    assert [f["text"] for f in flat] == ["One.", "Two.", "Ten."]


def test_chapter_div_inside_a_wrapper_div_raises_loudly():
    # Sol re-review round 2: a Chapter nested in a front-matter/misc wrapper
    # div is NOT a real top-level column, and silently parsing it would emit
    # a phantom chapter. Under the flat scheme ANY div ancestor of a Chapter
    # div is a loud error naming the file and scheme, same style as the
    # Book-div guard.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="frontmatter"><div type="Chapter" n="1"><p>Wrapped.</p></div></div>
<div type="Chapter" n="2"><p>Two.</p></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match=r"nested.*section"):
        _parse_flat_chapter(tree, SCHEME, xml_path=Path("ench.xml"))
    with pytest.raises(ValueError, match="ench.xml"):
        _parse_flat_chapter(tree, SCHEME, xml_path=Path("ench.xml"))


def test_chapter_div_inside_another_chapter_raises_loudly():
    # Same guard: a Chapter nested inside a Chapter is also a topology the
    # flat scheme does not describe — error, never a silent skip or a
    # phantom column.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><p>Outer.</p>
<div type="Chapter" n="99"><p>Inner.</p></div></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="nested"):
        _parse_flat_chapter(tree, SCHEME)


def test_book_div_under_flat_scheme_raises_loudly_instead_of_misparsing():
    # A <div type="Book"> means the export is NOT the flat bookless shape this
    # scheme declares — silently hardcoding book=1 would misassign every
    # chapter, so the parse must abort naming the file and the scheme.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="Chapter" n="1"><p>One.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match=r'div\[@type="Book"\].*section'):
        _parse_flat_chapter(tree, SCHEME, xml_path=Path("ench.xml"))
    with pytest.raises(ValueError, match="ench.xml"):
        _parse_flat_chapter(tree, SCHEME, xml_path=Path("ench.xml"))


# --- top-level n="t" div: Epicurus' title/greeting drop (Wave 3) -------------
# TLG's export for Epicurus' Letters/Vatican Sayings carries an extra
# top-level div, n="t", holding either a bare collection title (Kuriai
# Doxai, Vatican Sayings) or a letter's own opening salutation (Ep.
# Herodotum, Ep. Menoeceum) — see manifests/epicurus-*.yaml and
# stage1_greek.py's `_load_flat_title_declarations`.

def _manifest_with_title_labels(*entries) -> Manifest:
    return Manifest(
        {
            "work": {"id": "EPIC", "tlg_author": "0537", "tlg_work": "010",
                     "greek_edition": "Fixture"},
            "citation": {
                "scheme": "section",
                "title_labels": [
                    {"sha256_16": h, "note": n} for h, n in entries
                ],
            },
            "books": [],
        },
        ROOT / "manifests" / "fake.yaml",
    )


def _hash16(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def test_declared_title_div_is_dropped_not_emitted_as_a_column():
    greeting = "Ἐπίκουρος Ἡροδότῳ χαίρειν."
    manifest = _manifest_with_title_labels((_hash16(greeting), "greeting"))
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="t"><l n="t">{greeting}</l></div>
<div type="Chapter" n="35"><p>Τοῖς μὴ δυναμένοις.</p></div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, SCHEME, manifest)
    assert [f["column"] for f in flat] == ["35"]
    assert flat[0]["text"] == "Τοῖς μὴ δυναμένοις."
    assert headings == []


def test_undeclared_title_div_raises_loudly_instead_of_silently_dropping():
    manifest = _manifest_with_title_labels()  # nothing declared
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="t"><l n="t">ΚΥΡΙΑΙ ΔΟΞΑΙ</l></div>
<div type="Chapter" n="1"><p>One.</p></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match='undeclared top-level n="t"'):
        _parse_flat_chapter(tree, SCHEME, manifest)


def test_declared_title_hash_must_match_the_actual_text_not_just_be_present():
    # A wrong/stale hash (declared for different text) must not silently
    # authorize dropping whatever text actually sits in the n="t" div.
    manifest = _manifest_with_title_labels((_hash16("some other text"), "stale"))
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="t"><l n="t">ΚΥΡΙΑΙ ΔΟΞΑΙ</l></div>
<div type="Chapter" n="1"><p>One.</p></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match='undeclared top-level n="t"'):
        _parse_flat_chapter(tree, SCHEME, manifest)


# --- parse_spine dispatch: bookless, single book -----------------------------

def test_parse_spine_dispatches_section_scheme_and_assigns_a_single_book():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><p>One.</p></div>
<div type="Chapter" n="2"><p>Two.</p></div>
<div type="Chapter" n="3"><p>Three.</p></div>
</body></text></TEI>"""
    )
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        path = Path(f.name)
    try:
        spine = parse_spine(path, _manifest())
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1", "2", "3"]
    assert [s["book"] for s in spine["segments"]] == [1, 1, 1]  # bookless -> all book 1
    # No line-wrap hyphen rejoin for this scheme's synthetic per-chapter line.
    assert all("joined" not in s["lines"][0] for s in spine["segments"])
    assert spine["unassigned_lines"] == []


# --- _rejoin_wrapped_hyphens: unit coverage of the precision requirements ----

def test_rejoin_wrapped_hyphens_joins_greek_letter_hyphen_space_lowercase_greek():
    assert _rejoin_wrapped_hyphens("ἀναγ- κάσαι ἔστιν") == "ἀναγκάσαι ἔστιν"


def test_rejoin_wrapped_hyphens_joins_across_multiple_spaces():
    # _line_text collapses whitespace runs to one space before this function
    # ever runs, but the function itself must not assume exactly one space.
    assert _rejoin_wrapped_hyphens("ἀναγ-  κάσαι") == "ἀναγκάσαι"


def test_rejoin_wrapped_hyphens_never_touches_the_em_dash():
    # U+2014 EM DASH glues Discourses' dialogue turns together (" — ") and
    # must survive untouched -- it is a different codepoint from the ASCII
    # hyphen-minus U+002D wrap artifact, never a wrap candidate.
    text = "τίς οὖν θέλει ζῆν ἁμαρτάνων; — Οὐδείς."
    assert _rejoin_wrapped_hyphens(text) == text


def test_rejoin_wrapped_hyphens_leaves_uppercase_after_the_gap_untouched():
    # An uppercase letter after the gap does not match the print-line-wrap
    # shape (a wrapped word continues in lowercase) -- left alone rather than
    # silently joined into a garbled token.
    text = "λόγος- Ἀγαθός"
    assert _rejoin_wrapped_hyphens(text) == text


def test_rejoin_wrapped_hyphens_leaves_punctuation_after_the_gap_untouched():
    text = "λόγος- (ἀγαθός)"
    assert _rejoin_wrapped_hyphens(text) == text


def test_rejoin_wrapped_hyphens_leaves_a_non_greek_preceding_char_untouched():
    # A hyphen not immediately preceded by a Greek letter (e.g. a Latin
    # apparatus citation like "Zeller-Nestle") is not a print-line wrap.
    assert _rejoin_wrapped_hyphens("Zeller- Nestle λόγος") == "Zeller- Nestle λόγος"


def test_rejoin_wrapped_hyphens_leaves_a_glued_hyphen_with_no_gap_untouched():
    # No whitespace between the hyphen and the next letter at all: not the
    # documented wrap shape (always "- ", hyphen then a run of spaces).
    assert _rejoin_wrapped_hyphens("ὁμο-δέ") == "ὁμο-δέ"
