from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline import stage7_emit
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_greek import (
    _chapter_sections,
    _parse_flat_book_section,
    _rejoin_wrapped_hyphens,
    _rejoin_wrapped_hyphens_mapped,
    _strip_title_section,
    parse_spine,
)

SCHEME = scheme_mod.get("book-section")


def _manifest(
    books: list[dict],
    div_types: dict | None = None,
    philosophers: dict | None = None,
    lettered_fragments: list[dict] | None = None,
    section_paragraphs: bool = False,
) -> Manifest:
    citation = {"scheme": "book-section"}
    if div_types is not None:
        citation["div_types"] = div_types
    if lettered_fragments is not None:
        citation["lettered_fragments"] = lettered_fragments
    if section_paragraphs:
        citation["section_paragraphs"] = True
    data = {
        "work": {"id": "MED", "tlg_author": "0562", "tlg_work": "001",
                 "greek_edition": "Fixture"},
        "citation": citation,
        "books": books,
    }
    if philosophers is not None:
        data["philosophers"] = philosophers
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


# --- _parse_flat_book_section: XML-shape fidelity -----------------------------

def test_flattens_a_single_section_chapter_to_one_synthetic_line():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<p rend="indent(1)">Alpha beta gamma.</p>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, _ = _parse_flat_book_section(tree, SCHEME)
    assert headings == []
    assert flat == [{"column": "1.1", "n": 1, "text": "Alpha beta gamma."}]


def test_multiple_sections_in_one_chapter_flatten_together_not_split():
    # Verified anomaly: chapter 1.16 nests up to 10 <section> divs; none of
    # them is a separate citable column — they all join the one "1.16" line.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="16">
<div type="section" n="1"><p>First.</p></div>
<div type="section" n="2"><p>Second.</p></div>
<div type="section" n="3"><p>Third.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert len(flat) == 1
    assert flat[0]["column"] == "1.16"
    assert flat[0]["text"] == "First. Second. Third."


def test_pb_and_space_milestones_contribute_no_text():
    # Verified anomalies: 124 bare <pb/> markers and <space quantity="N"/>
    # inline-verse indents — neither carries its own text (no `.text`, only
    # a `.tail` that already flows through itertext()), so both disappear
    # for free without special-case stripping code.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="4">
<div type="chapter" n="9">
<div type="section" n="1">
<p>Before <pb/>after. <space quantity="5"/>Verse line.</p>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert flat[0]["text"] == "Before after. Verse line."


def test_manuscript_colophon_head_label_preserved_as_leading_text():
    # Verified anomaly: 2.1 and 3.1 open with an extra
    # <p><label type="head">...</label></p> manuscript colophon. No heading
    # precedent applies to this scheme (unlike the <l n="t"> title-line ->
    # `headings` convention the line-bearing parsers use), so the fallback
    # is to keep it as the chapter's leading text unit, verbatim.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="2">
<div type="chapter" n="1">
<div type="section" n="1">
<p><label type="head" rend="indent(5)">Τὰ ἐν Κουάδοις πρὸς τῷ Γρανούᾳ αʹ</label></p>
<p rend="indent(1)">Ἕωθεν προλέγειν ἑαυτῷ.</p>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, _ = _parse_flat_book_section(tree, SCHEME)
    assert headings == []
    assert flat[0]["column"] == "2.1"
    assert flat[0]["text"] == "Τὰ ἐν Κουάδοις πρὸς τῷ Γρανούᾳ αʹ Ἕωθεν προλέγειν ἑαυτῷ."


def test_editorial_brackets_and_crux_marks_pass_through_unchanged():
    # Editorial ‹angle›/[square] brackets and cruces (†) are ordinary
    # character data to this flatten — preserved, matching how the other
    # schemes' stage1 parsers leave them for stage3 to strip/log as sigla.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="6">
<div type="section" n="1">
<p>Kept [ἀγαθόν] and &lt;δέ&gt; and a † crux.</p>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert flat[0]["text"] == "Kept [ἀγαθόν] and <δέ> and a † crux."


def test_print_line_hyphen_wrap_is_rejoined_inside_the_flattened_chapter():
    # CLAUDE.md defect A: TLG print-line hyphenation (Discourses/Meditations
    # source XML wraps a word across <l> lines mid-chapter) survives as a
    # literal "- " when the whole chapter flattens to one synthetic line —
    # the cross-line rejoin in parse_spine() is explicitly skipped for this
    # scheme (see the guard just above it), since it operates on separate
    # per-line dicts this scheme's parser never produces. Must-fail-first:
    # before the fix, flat[0]["text"] contained the literal "ἀναγ- κάσαι".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="4">
<div type="chapter" n="1">
<div type="section" n="1">
<p>ὃν οὔτ' ἀναγ-</p>
<p>κάσαι ἔστιν.</p>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert flat[0]["text"] == "ὃν οὔτ' ἀναγκάσαι ἔστιν."


def test_discourses_n_t_title_section_is_excluded_from_the_chapter_body():
    # Regression: Epictetus' Discourses (also book-section) tags a chapter's
    # Greek title as <div type="section" n="t">, mirroring the <l n="t">
    # title-line convention the line-bearing parsers route to `headings`.
    # Unlike an ordinary numbered sub-section, it must NOT leak into the
    # chapter body text.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="t"><p>Περὶ τοῦ ἐφ' ἡμῖν.</p></div>
<div type="section" n="1"><p>Τῶν ὄντων τὰ μέν ἐστιν ἐφ' ἡμῖν.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, _ = _parse_flat_book_section(tree, SCHEME)
    assert headings == []
    assert flat == [{"column": "1.1", "n": 1, "text": "Τῶν ὄντων τὰ μέν ἐστιν ἐφ' ἡμῖν."}]


def test_strip_title_section_preserves_the_removed_divs_tail_text():
    # Regression (Sol-High review, 2026-07-16): removing the n="t" title div
    # must not delete its .tail — real body text sitting between the title
    # div's close tag and the next sibling belongs to the chapter.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1"><div type="section" n="t"><p>Title.</p></div>Tail body text. <div type="section" n="1"><p>Section body.</p></div></div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert flat == [{"column": "1.1", "n": 1,
                     "text": "Tail body text. Section body."}]


def test_strip_title_section_preserves_tail_when_title_is_first_child():
    # Same regression, first-child shape: the removed div's tail must attach
    # to the parent's text, not vanish.
    xml = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="2"><div type="section" n="t"><p>T.</p></div>Kept tail.</div>
</div>
</body></text></TEI>"""
    tree = _tree(xml)
    flat, _, _ = _parse_flat_book_section(tree, SCHEME)
    assert flat == [{"column": "1.2", "n": 1, "text": "Kept tail."}]


def test_strip_title_section_leaves_a_chapter_with_no_title_untouched():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>No title here.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    chap_div = next(d for d in tree.iter("{*}div") if d.get("type") == "chapter")
    assert _strip_title_section(chap_div) is chap_div  # no copy needed


# --- parse_spine dispatch: book-section end to end -----------------------------

def test_parse_spine_dispatches_book_section_and_assigns_books():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1"><div type="section" n="1"><p>One.</p></div></div>
<div type="chapter" n="2"><div type="section" n="1"><p>Two.</p></div></div>
</div>
<div type="Book" n="2">
<div type="chapter" n="1"><div type="section" n="1"><p>Three.</p></div></div>
</div>
</body></text></TEI>"""
    )
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        path = Path(f.name)
    try:
        manifest = _manifest([
            {"n": 1, "start": "1.1", "end": "1.2"},
            {"n": 2, "start": "2.1", "end": "2.1"},
        ])
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1.1", "1.2", "2.1"]
    assert [s["book"] for s in spine["segments"]] == [1, 1, 2]
    # No line-wrap hyphen rejoin for this scheme — see stage1_greek's guard.
    assert all("joined" not in s["lines"][0] for s in spine["segments"])
    assert spine["unassigned_lines"] == []
    # Meditations carries no philosopher-heading stubs — the key must be
    # entirely absent (zero-diff for every non-Diogenes-Laertius work), not
    # present-but-empty.
    assert "philosopher_headers" not in spine


def _write_tmp_xml(tree) -> Path:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        return Path(f.name)


# --- citation.div_types.section override (Diogenes Laertius) -----------------

def test_div_types_override_defaults_to_the_scheme_constant():
    sch = scheme_mod.for_manifest({"citation": {"scheme": "book-section"}})
    assert sch.section_div_type == "chapter"


def test_div_types_override_swaps_the_nested_section_div_type():
    sch = scheme_mod.for_manifest(
        {"citation": {"scheme": "book-section", "div_types": {"section": "section"}}}
    )
    assert sch.section_div_type == "section"
    assert sch.page_div_type == "Book"          # every other field untouched
    assert sch.has_sections                     # not re-derived to False


def test_div_types_override_rejects_unknown_keys():
    with pytest.raises(ValueError, match="unknown"):
        scheme_mod.for_manifest(
            {"citation": {"scheme": "book-section", "div_types": {"bogus": "x"}}}
        )


def test_dl_shaped_tei_parses_under_the_div_type_override():
    # DL's TEI is div[@type="Book"] -> flat div[@type="section"] siblings
    # (NOT "chapter" like Meditations) — with the override applied,
    # _parse_flat_book_section must dispatch on the overridden section div
    # type exactly as it does on the default "chapter" for Meditations.
    dl_sch = scheme_mod.for_manifest(
        {"citation": {"scheme": "book-section", "div_types": {"section": "section"}}}
    )
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="7">
<div type="section" n="1"><p>Ζήνων.</p></div>
<div type="section" n="2"><p>Δεύτερον.</p></div>
</div>
</body></text></TEI>"""
    )
    flat, headings, headers = _parse_flat_book_section(tree, dl_sch)
    assert headings == []
    assert headers == []
    assert flat == [
        {"column": "7.1", "n": 1, "text": "Ζήνων."},
        {"column": "7.2", "n": 1, "text": "Δεύτερον."},
    ]


def test_meditations_shaped_manifest_is_unaffected_by_the_override_feature():
    # No citation.div_types at all — Meditations' existing manifests parse
    # exactly as before, dispatching on the registered "chapter" default.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1"><div type="section" n="1"><p>Alpha.</p></div></div>
</div>
</body></text></TEI>"""
    )
    flat, headings, headers = _parse_flat_book_section(tree, SCHEME)
    assert headings == []
    assert headers == []
    assert flat == [{"column": "1.1", "n": 1, "text": "Alpha."}]


# --- t-stub philosopher headers (Diogenes Laertius) ---------------------------

DL_SCHEME = scheme_mod.for_manifest(
    {"citation": {"scheme": "book-section", "div_types": {"section": "section"}}}
)


def test_t_stub_sections_are_excluded_from_flat_and_collected_as_headers():
    # A stub div (@n="t18-47") must NOT become a phantom column like
    # "2.t18-47" — it is the philosopher-heading marker for sections 18-47,
    # collected into `headers` instead, with the ordinary numbered sections
    # around it parsing normally. Collection requires the manifest to opt in
    # via a `philosophers` block (Sol Major 2 review round, 2026-07-16).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="t1-15"><p>Θαλῆς.</p></div>
<div type="section" n="1"><p>First life section.</p></div>
<div type="section" n="15"><p>Last life section.</p></div>
<div type="section" n="t16-44"><p>Σόλων.</p></div>
<div type="section" n="16"><p>Solon's first section.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.16"}],
                         div_types={"section": "section"},
                         philosophers={"names_file": "fake.json"})
    flat, headings, headers = _parse_flat_book_section(tree, DL_SCHEME, manifest)
    assert headings == []
    assert [f["column"] for f in flat] == ["1.1", "1.15", "1.16"]
    assert headers == [
        {"book": 1, "start_section": 1, "end_section": 15, "greek_name": "Θαλῆς."},
        {"book": 1, "start_section": 16, "end_section": 44, "greek_name": "Σόλων."},
    ]


def test_t_stub_headers_flow_through_parse_spine_no_phantom_columns():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="2">
<div type="section" n="t18-47"><p>Ἀναξίμανδρος.</p></div>
<div type="section" n="18"><p>Body text.</p></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _manifest(
            [{"n": 2, "start": "2.18", "end": "2.18"}],
            div_types={"section": "section"},
            philosophers={"names_file": "fake.json"},
        )
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()
    assert [s["column"] for s in spine["segments"]] == ["2.18"]  # no "2.t18-47"
    assert spine["philosopher_headers"] == [
        {"book": 2, "start_section": 18, "end_section": 47, "greek_name": "Ἀναξίμανδρος."},
    ]


def test_t_stub_without_philosophers_block_fails_loudly():
    # Sol Major 2: a t-prefixed @n in a work whose manifest does NOT declare
    # a `philosophers` block must be a loud parse error, never a silent drop
    # into an unused headers list. Covers both no-manifest-at-all and a
    # manifest with no `philosophers` key.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="t1-15"><p>Θαλῆς.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="philosophers"):
        _parse_flat_book_section(tree, DL_SCHEME, None)

    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.15"}],
                         div_types={"section": "section"})  # no philosophers=
    with pytest.raises(ValueError, match="philosophers"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_t_stub_zero_start_rejected():
    # Malformed stub content: @n="t0" means start=end=0, which is not a
    # valid 1-indexed section — loud ValueError, not a bogus header.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="t0"><p>Bogus.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.1"}],
                         div_types={"section": "section"},
                         philosophers={"names_file": "fake.json"})
    with pytest.raises(ValueError, match="malformed"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_t_stub_end_before_start_rejected():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="t5-3"><p>Bogus.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.5"}],
                         div_types={"section": "section"},
                         philosophers={"names_file": "fake.json"})
    with pytest.raises(ValueError, match="malformed"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


# --- lettered-fragment remap (Diogenes Laertius book 10) ----------------------

def test_lettered_fragments_declared_and_matching_remaps_to_merged_sections():
    # Sol Major 1: with a manifest declaration whose `found` list matches the
    # document order of the encountered lettered @n exactly, the remap
    # applies — 120a/121b/120b all resolve onto "10.120", 121a onto "10.121".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
<div type="section" n="121b"><p>Beta.</p></div>
<div type="section" n="120b"><p>Gamma.</p></div>
<div type="section" n="121a"><p>Delta.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.121"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a", "121b", "120b", "121a"],
            "merge": {120: ["120a", "121b", "120b"], 121: ["121a"]},
        }],
    )
    flat, headings, headers = _parse_flat_book_section(tree, DL_SCHEME, manifest)
    assert headings == [] and headers == []
    assert [f["column"] for f in flat] == ["10.120", "10.120", "10.120", "10.121"]
    assert [f["text"] for f in flat] == ["Alpha.", "Beta.", "Gamma.", "Delta."]


def test_lettered_fragment_without_manifest_declaration_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([{"n": 10, "start": "10.120", "end": "10.120"}],
                         div_types={"section": "section"})  # no lettered_fragments=
    with pytest.raises(ValueError, match="lettered-fragment"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_lettered_fragment_declared_but_subset_encountered_fails_loudly():
    # Declaration expects all four fragments; the export only carries three
    # — missing/extra vs. the declaration is a loud failure, not a silent
    # partial remap.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
<div type="section" n="121b"><p>Beta.</p></div>
<div type="section" n="120b"><p>Gamma.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.121"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a", "121b", "120b", "121a"],
            "merge": {120: ["120a", "121b", "120b"], 121: ["121a"]},
        }],
    )
    with pytest.raises(ValueError, match="does not match"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_lettered_fragment_declared_but_reordered_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
<div type="section" n="120b"><p>Gamma.</p></div>
<div type="section" n="121b"><p>Beta.</p></div>
<div type="section" n="121a"><p>Delta.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.121"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a", "121b", "120b", "121a"],
            "merge": {120: ["120a", "121b", "120b"], 121: ["121a"]},
        }],
    )
    with pytest.raises(ValueError, match="does not match"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_declared_lettered_fragments_book_with_none_encountered_fails_loudly():
    # Round-2 Hole 1 (Sol): manifest declares book 10 found=["120a"] but the
    # document's book 10 carries only a plain n="120" section — no lettered
    # @n at all. Before the fix, _resolve_lettered_fragments only iterates
    # BOOKS THAT WERE ENCOUNTERED with lettered n's, so a stale declaration
    # for a book with zero lettered n's in the document silently no-ops.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120"><p>Plain.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.120"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a"],
            "merge": {120: ["120a"]},
        }],
    )
    with pytest.raises(ValueError, match="stale"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_malformed_t_prefixed_n_fails_loudly_regardless_of_philosophers_opt_in():
    # Round-2 Hole 2 (Sol): an @n beginning with "t" that does NOT match the
    # strict tSTART(-END) stub regex (e.g. "t5-" or "tbad") must fail loudly
    # rather than falling through to ordinary column composition (which would
    # emit a phantom column like "1.t5-"). This must fire even when the
    # manifest HAS opted into philosophers — malformed-ness, not opt-in
    # status, is what makes it an error.
    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.1"}],
                         div_types={"section": "section"},
                         philosophers={"names_file": "fake.json"})
    for bad_n in ("t5-", "tbad"):
        tree = _tree(
            f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="{bad_n}"><p>Bogus.</p></div>
</div>
</body></text></TEI>"""
        )
        with pytest.raises(ValueError, match="unrecognized"):
            _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_malformed_t_prefixed_n_fails_loudly_without_philosophers_opt_in_too():
    # Same malformed value, but the manifest has NOT opted into philosophers
    # at all — still a loud "unrecognized" error, not the "no philosophers
    # block" message (that's for WELL-FORMED stubs only).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="tbad"><p>Bogus.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.1"}],
                         div_types={"section": "section"})  # no philosophers=
    with pytest.raises(ValueError, match="unrecognized"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_duplicate_value_in_found_list_fails_loudly_as_manifest_authoring_error():
    # Round-2 Hole 4 (Sol): a duplicate value inside a book's declared
    # `found` list (or inside a single `merge` component list) is a
    # manifest-authoring error, independent of what the document contains —
    # it must be caught at declaration-validation time, before the
    # found-vs-document-order comparison. Previously it fell through to
    # `resolved[(book_n, n)] = resolved_n`, silently overwriting the same
    # mapping twice.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.121"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a", "120a", "121a"],
            "merge": {120: ["120a", "120a"], 121: ["121a"]},
        }],
    )
    with pytest.raises(ValueError, match="duplicate"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_duplicate_value_within_a_merge_list_fails_loudly_too():
    # Same authoring error, but `found` itself has no duplicates — only one
    # `merge` value list repeats a component.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="10">
<div type="section" n="120a"><p>Alpha.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(
        [{"n": 10, "start": "10.120", "end": "10.121"}],
        div_types={"section": "section"},
        lettered_fragments=[{
            "book": 10,
            "found": ["120a", "121a"],
            "merge": {120: ["120a", "120a"], 121: ["121a"]},
        }],
    )
    with pytest.raises(ValueError, match="duplicate"):
        _parse_flat_book_section(tree, DL_SCHEME, manifest)


def test_works_without_t_stubs_omit_philosopher_headers_key_entirely():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="section" n="1"><p>No stubs here.</p></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _manifest([{"n": 1, "start": "1.1", "end": "1.1"}],
                             div_types={"section": "section"})
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()
    assert "philosopher_headers" not in spine


# --- doubled-column merge (regression) ----------------------------------------

def test_two_divs_sharing_book_and_number_merge_into_one_doubled_column():
    # parse_spine's segment grouping is keyed (book, column) (stage1_greek.py
    # ~435-449), not one segment per div — two divs sharing the same (book, n)
    # (a doubled/split citation unit) must concatenate into ONE spine segment,
    # preserving document order.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="2">
<div type="chapter" n="125"><div type="section" n="1"><p>First half.</p></div></div>
<div type="chapter" n="125"><div type="section" n="1"><p>Second half.</p></div></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _manifest([{"n": 2, "start": "2.125", "end": "2.125"}])
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()
    assert [s["column"] for s in spine["segments"]] == ["2.125"]
    assert len(spine["segments"]) == 1
    assert spine["segments"][0]["lines"] == [
        {"n": 1, "text": "First half."},
        {"n": 1, "text": "Second half."},
    ]


# --- philosophers.json emission (stage7_emit.emit_philosophers) --------------

def _dl_manifest(philosophers: dict | None = None) -> Manifest:
    data = {
        "work": {"id": "DL", "tlg_author": "0004", "tlg_work": "001",
                 "greek_edition": "Fixture"},
        "citation": {"scheme": "book-section", "div_types": {"section": "section"}},
        "books": [{"n": 1, "start": "1.1", "end": "1.44"}],
    }
    if philosophers is not None:
        data["philosophers"] = philosophers
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_emit_philosophers_returns_none_and_writes_nothing_without_headers(tmp_path):
    spine = {"segments": [], "headings": [], "unassigned_lines": []}
    result = stage7_emit.emit_philosophers(spine, _dl_manifest(), tmp_path)
    assert result is None
    assert not (tmp_path / "philosophers.json").exists()


def test_emit_philosophers_falls_back_to_greek_name_with_no_names_file(tmp_path):
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 15, "greek_name": "Θαλῆς."},
            {"book": 1, "start_section": 16, "end_section": 44, "greek_name": "Σόλων."},
        ],
    }
    out = stage7_emit.emit_philosophers(spine, _dl_manifest(), tmp_path)
    written = json.loads((tmp_path / "philosophers.json").read_text(encoding="utf-8"))
    assert written == out
    assert written == {
        "1": [
            {"startSection": 1, "endSection": 15, "greekName": "Θαλῆς.",
             "name": "Θαλῆς.", "id": "1:1.1"},
            {"startSection": 16, "endSection": 44, "greekName": "Σόλων.",
             "name": "Σόλων.", "id": "1:1.16"},
        ],
    }


def test_emit_philosophers_matches_english_names_by_order_within_book(tmp_path, monkeypatch):
    # Exact-match happy path: every name's start_section equals a header's
    # start_section, so start_section-equality matching (Grok M1/M2 review
    # round, 2026-07-16) produces the same result the old by-position
    # matching did here.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([
            {"book": 1, "start_section": 1, "name": "Thales"},
            {"book": 1, "start_section": 16, "name": "Solon"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 15, "greek_name": "Θαλῆς."},
            {"book": 1, "start_section": 16, "end_section": 44, "greek_name": "Σόλων."},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert [e["name"] for e in out["1"]] == ["Thales", "Solon"]


def test_emit_philosophers_extra_leading_name_matches_by_start_section_not_position(
    tmp_path, monkeypatch, capsys,
):
    # Grok M1/M2 regression, book-1-shaped: the real lives-names.json carries
    # a leading "Prologue" entry at start_section 1 with NO corresponding
    # Greek-derived header (the TEI's first header, Thales, starts at 1.22).
    # Under the old BY-POSITION matching this shifted every subsequent name
    # one slot late, mislabeling Thales's header as "Prologue". Matching by
    # start_section equality must label Thales correctly and log the
    # unmatched "Prologue" name as unused rather than silently consuming it.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([
            {"book": 1, "start_section": 1, "name": "Prologue"},
            {"book": 1, "start_section": 22, "name": "THALES"},
            {"book": 1, "start_section": 45, "name": "SOLON"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 22, "end_section": 44, "greek_name": "ΘΑΛΗΣ"},
            {"book": 1, "start_section": 45, "end_section": 67, "greek_name": "ΣΟΛΩΝ"},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert [e["name"] for e in out["1"]] == ["THALES", "SOLON"]
    captured = capsys.readouterr().out
    assert "WARNING" in captured
    assert "Prologue" in captured and "unused" in captured


def test_emit_philosophers_duplicate_start_section_matches_in_document_order(
    tmp_path, monkeypatch,
):
    # Grok M1/M2 regression, book-2-shaped: two headers share the same
    # start_section (Cebes/Menedemus both at 2.125, the doubled Bekker
    # section) and the names file carries two names at that same
    # start_section too — they must match in document order (first name to
    # first header, second to second), not collide or cross-match.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([
            {"book": 2, "start_section": 125, "name": "CEBES"},
            {"book": 2, "start_section": 125, "name": "MENEDEMUS"},
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 2, "start_section": 125, "end_section": 125, "greek_name": "ΚΕΒΗΣ"},
            {"book": 2, "start_section": 125, "end_section": 144, "greek_name": "ΜΕΝΕΔΗΜΟΣ"},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert [e["name"] for e in out["2"]] == ["CEBES", "MENEDEMUS"]


def test_emit_philosophers_logs_a_count_mismatch_and_falls_back_for_the_rest(
    tmp_path, monkeypatch, capsys,
):
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([{"book": 1, "start_section": 1, "name": "Thales"}]),  # only 1 of 2
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 15, "greek_name": "Θαλῆς."},
            {"book": 1, "start_section": 16, "end_section": 44, "greek_name": "Σόλων."},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert [e["name"] for e in out["1"]] == ["Thales", "Σόλων."]  # 2nd falls back
    assert "WARNING" in capsys.readouterr().out


def test_emit_philosophers_warns_on_a_names_file_with_zero_entries_for_a_book(
    tmp_path, monkeypatch, capsys,
):
    # A names file that's present but has NO entries at all for book 1 (which
    # DOES have Greek headers) used to slip past the `if names and ...`
    # mismatch check silently, since an empty list is falsy — every header
    # fell back to its Greek name with no warning at all.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(json.dumps([]), encoding="utf-8")
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 44, "greek_name": "Θαλῆς."},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert [e["name"] for e in out["1"]] == ["Θαλῆς."]  # falls back, as before
    assert "WARNING" in capsys.readouterr().out


def test_emit_philosophers_warns_on_names_file_entries_for_a_headerless_book(
    tmp_path, monkeypatch, capsys,
):
    # A names file with entries for book 2, which has NO Greek-derived
    # headers at all, used to be silently ignored: the emission loop only
    # ever visits headers_by_book, so book 2 is never touched and no warning
    # fires — headers stay authoritative (no emission change), but the
    # mismatch must still be logged loudly.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([{"book": 2, "start_section": 1, "name": "Ghost"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 44, "greek_name": "Θαλῆς."},
        ],
    }
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert set(out) == {"1"}  # book 2 never emitted — headers are authoritative
    assert "WARNING" in capsys.readouterr().out


def test_emit_philosophers_warns_on_names_file_with_no_headers_at_all(
    tmp_path, monkeypatch, capsys,
):
    # Sol counterexample: names_file configured but the spine has ZERO
    # philosopher headers — the early return skipped every warning, so the
    # whole file was silently unused.
    src = tmp_path / "sources"
    src.mkdir()
    (src / "dl-names.json").write_text(
        json.dumps([{"book": 1, "start_section": 1, "name": "Ghost"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(stage7_emit, "SOURCES_DIR", src)
    spine = {"segments": [], "headings": [], "unassigned_lines": []}
    manifest = _dl_manifest({"names_file": "dl-names.json"})
    out = stage7_emit.emit_philosophers(spine, manifest, tmp_path)
    assert out is None
    captured = capsys.readouterr().out
    assert "WARNING" in captured and "unused" in captured


def test_emit_philosophers_no_names_file_never_warns(tmp_path, capsys):
    # The ordinary book-section case (no names_file configured at all) must
    # stay silent — this is not the "zero entries" asymmetry, it's simply
    # the feature being unused.
    spine = {
        "segments": [], "headings": [], "unassigned_lines": [],
        "philosopher_headers": [
            {"book": 1, "start_section": 1, "end_section": 44, "greek_name": "Θαλῆς."},
        ],
    }
    stage7_emit.emit_philosophers(spine, _dl_manifest(), tmp_path)
    assert "WARNING" not in capsys.readouterr().out


# --- Discourses section-paragraph standoff channel (citation.section_paragraphs) --

def test_section_paragraphs_not_emitted_without_manifest_opt_in():
    # Meditations-shaped: multiple sections in one chapter, but no opt-in —
    # must stay byte-identical to the pre-feature emission (no "sections" key).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>First.</p></div>
<div type="section" n="2"><p>Second.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=False))
    assert flat == [{"column": "1.1", "n": 1, "text": "First. Second."}]
    assert "sections" not in flat[0]


def test_section_paragraphs_omitted_when_manifest_has_no_citation_opt_in_key_at_all():
    # manifest=None (most direct-call fixtures) must not crash and must not
    # emit sections either.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>First.</p></div>
<div type="section" n="2"><p>Second.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, None)
    assert "sections" not in flat[0]


def test_section_paragraphs_opt_in_records_offsets():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="t"><p>Title, excluded.</p></div>
<div type="section" n="1"><p>First bit.</p></div>
<div type="section" n="2"><p>Second bit.</p></div>
<div type="section" n="3"><p>Third bit.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    assert flat[0]["text"] == "First bit. Second bit. Third bit."
    assert flat[0]["sections"] == [
        {"n": 1, "o": 0},
        {"n": 2, "o": 11},
        {"n": 3, "o": 23},
    ]
    for s in flat[0]["sections"]:
        assert flat[0]["text"][s["o"]:s["o"] + 1] != " "


def test_section_paragraphs_omitted_when_chapter_has_only_one_section():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>Only one.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    assert flat[0]["text"] == "Only one."
    assert "sections" not in flat[0]


def test_section_paragraphs_malformed_n_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>First.</p></div>
<div type="section" n="bad"><p>Second.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="unrecognized TLG section"):
        _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))


def test_section_paragraphs_compound_n_resolves_to_first_number():
    # Discourses 2.13's Schenkl-merged n="25,26" — the one compound section @n
    # in the whole work.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="2">
<div type="chapter" n="13">
<div type="section" n="24"><p>Twenty-four.</p></div>
<div type="section" n="25,26"><p>Merged.</p></div>
<div type="section" n="27"><p>Twenty-seven.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    ns = [s["n"] for s in flat[0]["sections"]]
    assert ns == [24, 25, 27]


def test_section_paragraphs_never_change_the_chapter_text_itself():
    # CRITICAL INVARIANT: opting in only ADDS a "sections" key; the chapter's
    # own `text` (and therefore every downstream Greek token) is untouched.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>Alpha be-</p></div>
<div type="section" n="2"><p>ta gamma.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat_off, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=False))
    flat_on, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    assert flat_off[0]["text"] == flat_on[0]["text"]


def test_section_paragraphs_hyphen_crossing_boundary_is_snapped_not_dropped():
    # A print-line hyphen wraps straight across the section-2 boundary (real
    # Greek text — the rejoin rule only fires on actual Greek letters, see
    # _is_greek_letter): after the whole-text rejoin, section 2's raw offset
    # would land mid-word ("κιμαστικήν"). Ground-truth adjudication against
    # the real Discourses TLG XML (all 618 corpus-wide instances of this
    # shape) found every one is a genuine Schenkl print-line straddle, never
    # an offset-remap bug — so the boundary is never dropped: it SNAPS back
    # to the start of the straddling word ("ἀποδοκιμαστικήν"), which becomes
    # section 2's opening word, matching how a Loeb marginal number sits at
    # the wrapped line.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>ἡ γραμματικὴ ἀποδο-</p></div>
<div type="section" n="2"><p>κιμαστικήν ἐστιν.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    text = flat[0]["text"]
    assert text == "ἡ γραμματικὴ ἀποδοκιμαστικήν ἐστιν."
    assert flat[0]["sections"] == [
        {"n": 1, "o": 0},
        {"n": 2, "o": text.index("ἀποδοκιμαστικήν")},
    ]


def test_section_paragraphs_hyphen_crossing_snaps_only_the_affected_boundary():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>ἡ γραμματικὴ ἀποδο-</p></div>
<div type="section" n="2"><p>κιμαστικήν ἐστιν.</p></div>
<div type="section" n="3"><p>Δεύτερον τοῦτο.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    text = flat[0]["text"]
    assert text == "ἡ γραμματικὴ ἀποδοκιμαστικήν ἐστιν. Δεύτερον τοῦτο."
    ns = [s["n"] for s in flat[0]["sections"]]
    assert ns == [1, 2, 3]  # no boundary is ever dropped
    assert flat[0]["sections"][1]["o"] == text.index("ἀποδοκιμαστικήν")  # snapped
    assert flat[0]["sections"][2]["o"] == text.index("Δεύτερον")  # untouched
    for s in flat[0]["sections"]:
        o = s["o"]
        assert not (o > 0 and text[o - 1].isalpha() and text[o].isalpha())


def test_section_paragraphs_hyphen_crossing_snaps_past_attached_leading_quote():
    # Grok-4.5 content verification (2026-07-16), 4/618 real Discourses
    # boundaries: the straddling wrap word can carry an attached opening
    # quote right at its own start, with NO space between the quote and the
    # wrap's first letter (e.g. a direct quotation whose first word happens
    # to be the one Schenkl's print line wrapped -- Discourses 1.9 sec 30,
    # 2.10 sec 13, 3.8 sec 4). `_word_start`'s old alphabetic-only walk
    # stopped AT the quote (not past it), stranding it as the trailing
    # character of the PRIOR section. Must-fail-first: before the
    # whitespace-based `_word_start` fix, `sections[1]["o"]` pointed at
    # "ἀποδοκιμαστικήν" (past the quote), not at "‘ἀποδοκιμαστικήν".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>ἡ γραμματικὴ ‘ἀποδο-</p></div>
<div type="section" n="2"><p>κιμαστικήν ἐστιν.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    text = flat[0]["text"]
    assert text == "ἡ γραμματικὴ ‘ἀποδοκιμαστικήν ἐστιν."
    assert flat[0]["sections"] == [
        {"n": 1, "o": 0},
        {"n": 2, "o": text.index("‘ἀποδοκιμαστικήν")},
    ]


def test_section_paragraphs_hyphen_crossing_snaps_past_interior_siglum():
    # Grok-4.5 content verification (2026-07-16): Discourses 1.23 sec 7 --
    # an editorial siglum (<ς>) embedded INSIDE the straddling word, not at
    # its edge. The old alphabetic-only walk stopped right after the `>`,
    # stranding "ἀνα<ς>" as the trailing content of the PRIOR section
    # (leaving only "τρέφεσθαι" opening the new one). The whole surface
    # word "ἀνα<ς>τρέφεσθαι" must open the new section instead.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>ἡ γραμματικὴ ἀνα&lt;ς&gt;τρέφ-</p></div>
<div type="section" n="2"><p>εσθαι δεῖ.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    text = flat[0]["text"]
    assert text == "ἡ γραμματικὴ ἀνα<ς>τρέφεσθαι δεῖ."
    assert flat[0]["sections"] == [
        {"n": 1, "o": 0},
        {"n": 2, "o": text.index("ἀνα<ς>τρέφεσθαι")},
    ]


def test_section_paragraphs_hyphen_crossing_snap_stops_at_glued_em_dash():
    # GPT-5.6-Sol-High confirm review (2026-07-16): a clause glued to the next
    # by an em dash with NO space ("λόγος—ἀποδο-"). Theoretical shape — a
    # corpus-wide old-vs-new diff found zero live instances in Schenkl — kept
    # as defensive hardening. `_word_start`'s whitespace-only back-walk does
    # not stop at the em dash (it is not whitespace), so it overshoots straight
    # through it and back to the start of "λόγος", dragging "λόγος—" into
    # section 2 along with the straddling wrap word. stage3_tokenize.py's own
    # tokenizing regex (`r"[^\s—]+"`, ~:261) treats an em dash as a hard
    # token boundary EVEN WHEN GLUED to a word with no surrounding space --
    # that is the boundary class `_word_start` must mirror. The correct snap
    # target is unchanged from the plain case (test_..._boundary_is_snapped_
    # not_dropped above): the start of "ἀποδοκιμαστικήν", NOT "λόγος—ἀποδο-
    # κιμαστικήν".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><p>ἡ γραμματικὴ λόγος—ἀποδο-</p></div>
<div type="section" n="2"><p>κιμαστικήν ἐστιν.</p></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest([], section_paragraphs=True))
    text = flat[0]["text"]
    assert text == "ἡ γραμματικὴ λόγος—ἀποδοκιμαστικήν ἐστιν."
    assert flat[0]["sections"] == [
        {"n": 1, "o": 0},
        {"n": 2, "o": text.index("ἀποδοκιμαστικήν")},
    ]


# --- _rejoin_wrapped_hyphens_mapped -------------------------------------------

def test_rejoin_mapped_matches_unmapped_text_output():
    text = "ἀγαθὸς λόγος ἀποδο- κιμαστικήν. τέλος."
    plain = _rejoin_wrapped_hyphens(text)
    mapped_text, _ = _rejoin_wrapped_hyphens_mapped(text)
    assert plain == mapped_text


def test_rejoin_mapped_offset_after_wrap_lands_mid_word():
    text = "ἀποδο- κιμαστικήν"
    new_text, old_to_new = _rejoin_wrapped_hyphens_mapped(text)
    assert new_text == "ἀποδοκιμαστικήν"
    boundary_offset = text.index(" κιμαστικήν") + 1  # pre-rejoin "section start"
    mapped = old_to_new[boundary_offset]
    assert new_text[mapped - 1].isalpha() and new_text[mapped].isalpha()


def test_rejoin_mapped_offset_unaffected_by_distant_rejoin():
    text = "πρῶτον. ἀποδο- κιμαστικήν. δεύτερον."
    new_text, old_to_new = _rejoin_wrapped_hyphens_mapped(text)
    boundary_offset = text.index(" δεύτερον") + 1
    mapped = old_to_new[boundary_offset]
    assert new_text[mapped:mapped + 9] == "δεύτερον."
    assert new_text[mapped - 1] == " "


def test_rejoin_mapped_end_of_text_offset():
    text = "ἀγαθός."
    new_text, old_to_new = _rejoin_wrapped_hyphens_mapped(text)
    assert old_to_new[len(text)] == len(new_text)


def test_rejoin_mapped_sigma_fold_is_an_in_place_substitution_offsets_unaffected():
    # Sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29): the
    # character folded (ς->σ) is the same character position that would
    # otherwise have been appended unchanged -- a pure in-place substitution,
    # never a length change -- so `_chapter_sections`' own remap of
    # pre-rejoin TLG-section-start offsets onto the rejoined text (I2) is
    # unaffected by this fix. Same shape as
    # test_rejoin_mapped_offset_unaffected_by_distant_rejoin above, but with
    # a sigma-wrap: the fold does not shift where "δεύτερον." lands.
    text = "ὧν προς- ήκει ἐπιμελεῖσθαι. δεύτερον."
    new_text, old_to_new = _rejoin_wrapped_hyphens_mapped(text)
    assert new_text == "ὧν προσήκει ἐπιμελεῖσθαι. δεύτερον."
    boundary_offset = text.index(" δεύτερον") + 1
    mapped = old_to_new[boundary_offset]
    assert new_text[mapped:mapped + 9] == "δεύτερον."
    assert new_text[mapped - 1] == " "
    assert old_to_new[len(text)] == len(new_text)
