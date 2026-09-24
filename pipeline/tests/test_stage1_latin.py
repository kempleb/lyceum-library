from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_latin import (
    _check_title_drop,
    _finalize_title_drops,
    _load_declared_title_labels,
    _parse_book_section,
    _parse_flat_section,
    _parse_letters,
    _rejoin_cross_section_hyphens,
    _rejoin_wrapped_hyphens,
    _resolve_source_book,
    _title_content_hash,
    parse_spine,
)

# PHI's book-section export shape: lowercase "book" (not TLG's "Book"),
# section divs nested directly (no intermediate "chapter" level) — the
# citation.div_types override this work declares.
SCHEME = scheme_mod.for_manifest(
    {"citation": {"scheme": "book-section", "div_types": {"page": "book", "section": "section"}}}
)


def _manifest(books: list[dict], citation_extra: dict | None = None) -> Manifest:
    # `title_labels: []` satisfies the now-mandatory (adversarial-review
    # Finding 2) declared-title-hash gate for any test whose fixture carries
    # no n="t" title div at all; a test that does declares its own hash(es)
    # via citation_extra.
    citation = {
        "scheme": "book-section", "div_types": {"page": "book", "section": "section"},
        "title_labels": [],
    }
    citation.update(citation_extra or {})
    data = {
        "work": {
            "id": "OFF", "phi_author": "0474", "phi_work": "055",
            "latin_edition": "Fixture", "language": "lat",
        },
        "citation": citation,
        "books": books,
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _title_declaration(text: str, note: str = "synthetic title label") -> dict:
    return {"sha256_16": _title_content_hash(text), "note": note}


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


def _write_tmp_xml(tree) -> Path:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        return Path(f.name)


# --- citation.div_types.page override (PHI's lowercase "book") --------------


def test_page_div_type_override_swaps_the_outer_div_type():
    sch = scheme_mod.for_manifest(
        {"citation": {"scheme": "book-section", "div_types": {"page": "book"}}}
    )
    assert sch.page_div_type == "book"
    assert sch.section_div_type == "chapter"  # untouched


def test_page_div_type_override_rejects_unknown_keys_unchanged():
    with pytest.raises(ValueError, match="unknown"):
        scheme_mod.for_manifest(
            {"citation": {"scheme": "book-section", "div_types": {"page": "book", "bogus": "x"}}}
        )


# --- _parse_book_section: PHI XML-shape fidelity -----------------------------


def test_flattens_a_single_section_to_one_synthetic_line():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="1"><p>Fictum tibi, Synthipater nate.</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_book_section(tree, SCHEME, _manifest([]))
    assert flat == [{"column": "1.1", "n": 1, "text": "Fictum tibi, Synthipater nate."}]


def test_whole_work_title_book_is_dropped():
    # A whole-work title division (always <div type="book" n="t">) must
    # never become a phantom "t.1" column — book-section's dotted grammar
    # has no letter axis to accept it anyway. Fixture text is wholly
    # synthetic (Finding 1): its content hash is declared in
    # citation.title_labels, mirroring how a real manifest declares its
    # own verified title-div hash.
    title = "TITULUS SYNTHETICUS OPERIS"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="t">
<div type="section" n="1"><p>{title}</p></div>
</div>
<div type="book" n="1">
<div type="section" n="1"><p>Real content.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([], {"title_labels": [_title_declaration(title)]})
    flat = _parse_book_section(tree, SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "Real content."}]


def test_per_book_title_section_is_dropped():
    # Each real book's own heading is <div type="section" n="t">, a sibling
    # of the ordinary numbered sections — dropped, not collected as a
    # heading (mirrors Discourses' n="t" title-section exclusion, one level
    # up in this export shape). Fixture text is wholly synthetic.
    title = "CAPUT SYNTHETICUM PRIMUM"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="t"><p>{title}</p></div>
<div type="section" n="1"><p>First section.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([], {"title_labels": [_title_declaration(title)]})
    flat = _parse_book_section(tree, SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "First section."}]


def test_unrecognized_section_n_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="bad"><p>Bogus.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="unrecognized PHI section"):
        _parse_book_section(tree, SCHEME, _manifest([]))


def test_print_line_hyphen_wrap_is_rejoined():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="1"><p>fictan- tium synthera omnis</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_book_section(tree, SCHEME, _manifest([]))
    assert flat[0]["text"] == "fictantium synthera omnis"


def test_rejoin_wrapped_hyphens_direct():
    assert _rejoin_wrapped_hyphens("vi- tae") == "vitae"
    assert _rejoin_wrapped_hyphens("Nor- banum") == "Norbanum"
    # An edition hyphen NOT followed by a lowercase letter (e.g. a genuine
    # trailing dash) is left untouched.
    assert _rejoin_wrapped_hyphens("res- Publica") == "res- Publica"


def test_pb_milestones_contribute_no_text():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="1"><p>Before <pb/>after.</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_book_section(tree, SCHEME, _manifest([]))
    assert flat[0]["text"] == "Before after."


# --- parse_spine dispatch: book-section end to end ---------------------------


def test_parse_spine_dispatches_and_assigns_books():
    # No work.expected_sourcedesc declared -- _check_sourcedesc no-ops (see
    # its own docstring), so no <teiHeader>/<sourceDesc> is needed here.
    whole_title = "TITULUS SYNTHETICUS"
    book1_title = "CAPUT SYNTHETICUM UNUM"
    book2_title = "CAPUT SYNTHETICUM DUO"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="t"><div type="section" n="1"><p>{whole_title}</p></div></div>
<div type="book" n="1">
<div type="section" n="t"><p>{book1_title}</p></div>
<div type="section" n="1"><p>One.</p></div>
<div type="section" n="2"><p>Two.</p></div>
</div>
<div type="book" n="2">
<div type="section" n="t"><p>{book2_title}</p></div>
<div type="section" n="1"><p>Three.</p></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _manifest(
            [
                {"n": 1, "start": "1.1", "end": "1.2"},
                {"n": 2, "start": "2.1", "end": "2.1"},
            ],
            {
                "title_labels": [
                    _title_declaration(whole_title),
                    _title_declaration(book1_title),
                    _title_declaration(book2_title),
                ]
            },
        )
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1.1", "1.2", "2.1"]
    assert [s["book"] for s in spine["segments"]] == [1, 1, 2]
    assert spine["unassigned_lines"] == []
    assert spine["edition"] == "Fixture"
    assert spine["headings"] == []


# --- Adversarial-review Finding 2: declared-hash title-drop gate ------------


def test_load_declared_title_labels_missing_key_is_fatal():
    data = {
        "work": {"id": "OFF", "phi_author": "0474", "phi_work": "055", "latin_edition": "Fixture", "language": "lat"},
        "citation": {"scheme": "book-section", "div_types": {"page": "book", "section": "section"}},
        "books": [],
    }
    manifest = Manifest(data, ROOT / "manifests" / "fake.yaml")
    with pytest.raises(ValueError, match="citation.title_labels is required"):
        _load_declared_title_labels(manifest)


def test_load_declared_title_labels_accepts_an_explicit_empty_list():
    manifest = _manifest([], {"title_labels": []})
    assert _load_declared_title_labels(manifest) == []


def test_load_declared_title_labels_rejects_a_bad_hash_shape():
    manifest = _manifest([], {"title_labels": [{"sha256_16": "not-hex", "note": "x"}]})
    with pytest.raises(ValueError, match="sha256_16"):
        _load_declared_title_labels(manifest)


def test_check_title_drop_accepts_a_declared_hash():
    text = "TITULUS SYNTHETICUS UNUS"
    h = _title_content_hash(text)
    manifest = _manifest([])
    assert _check_title_drop(text, "book", [h], manifest) == h


def test_check_title_drop_rejects_undeclared_content():
    manifest = _manifest([])
    with pytest.raises(ValueError, match="is not declared in citation.title_labels"):
        _check_title_drop("TITULUS NON DECLARATUS", "book", [], manifest)


def test_check_title_drop_rejects_empty_text():
    manifest = _manifest([])
    with pytest.raises(ValueError, match="shape cap"):
        _check_title_drop("", "book", [], manifest)


def test_check_title_drop_rejects_over_200_chars_even_when_declared():
    # The shape cap is defense-in-depth, independent of the declared-hash
    # check — an absurdly long div was never a plausible title label,
    # regardless of whether its hash happens to be declared.
    label = "A" * 201
    h = _title_content_hash(label)
    manifest = _manifest([])
    with pytest.raises(ValueError, match="shape cap"):
        _check_title_drop(label, "book", [h], manifest)


def test_check_title_drop_accepts_200_chars_exactly():
    label = "A" * 200
    h = _title_content_hash(label)
    manifest = _manifest([])
    assert _check_title_drop(label, "book", [h], manifest) == h


def test_finalize_title_drops_accepts_a_matching_multiset():
    manifest = _manifest([])
    _finalize_title_drops(["aaa", "bbb"], ["bbb", "aaa"], manifest, "book-section")  # no raise


def test_finalize_title_drops_count_mismatch_is_fatal():
    manifest = _manifest([])
    with pytest.raises(ValueError, match="count mismatch"):
        _finalize_title_drops(["aaa"], ["aaa", "bbb"], manifest, "book-section")


def test_finalize_title_drops_stale_declaration_is_fatal():
    manifest = _manifest([])
    with pytest.raises(ValueError, match="stale declaration"):
        _finalize_title_drops(["aaa", "ccc"], ["aaa", "bbb"], manifest, "book-section")


def test_whole_work_title_book_undeclared_content_fails_loudly():
    # A n="t" book div whose content hash is not declared in citation.
    # title_labels must never be silently dropped — the exact hole an
    # undeclared drop candidate represents, whether or not the content
    # happens to look like a plausible heading.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="t">
<div type="section" n="1"><p>TEXTUS NON DECLARATUS</p></div>
</div>
<div type="book" n="1">
<div type="section" n="1"><p>Real content.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="is not declared in citation.title_labels"):
        _parse_book_section(tree, SCHEME, _manifest([]))


def test_per_book_title_section_undeclared_content_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="t"><p>TEXTUS NON DECLARATUS</p></div>
<div type="section" n="1"><p>First section.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="is not declared in citation.title_labels"):
        _parse_book_section(tree, SCHEME, _manifest([]))


def test_book_section_title_count_mismatch_fails_loudly():
    # citation.title_labels declares an extra entry never observed by the
    # walk -- a stale/miscounted declaration is fatal, not silently ignored.
    title = "TITULUS SYNTHETICUS OPERIS"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="t">
<div type="section" n="1"><p>{title}</p></div>
</div>
<div type="book" n="1">
<div type="section" n="1"><p>Real content.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([], {
        "title_labels": [_title_declaration(title), _title_declaration("NUMQUAM VISUM")]
    })
    with pytest.raises(ValueError, match="count mismatch"):
        _parse_book_section(tree, SCHEME, manifest)


# --- Grok content defect: cross-section print-line hyphen wraps --------------


def test_rejoin_cross_section_hyphens_rejoins_a_straddling_wrap():
    flat = [
        {"column": "1.97", "n": 1, "text": "...syntheticaque fictan-"},
        {"column": "1.98", "n": 1, "text": "tium fictarum. Ficquare..."},
    ]
    n = _rejoin_cross_section_hyphens(flat, _manifest([]))
    assert n == 1
    assert flat[0]["text"] == "...syntheticaque fictantium"
    assert flat[1]["text"] == "fictarum. Ficquare..."


def test_rejoin_cross_section_hyphens_leaves_non_hyphen_sections_untouched():
    flat = [
        {"column": "1.1", "n": 1, "text": "Fictum tibi, Synthipater nate."},
        {"column": "1.2", "n": 1, "text": "Annum iam ficticium synthum."},
    ]
    n = _rejoin_cross_section_hyphens(flat, _manifest([]))
    assert n == 0
    assert flat[0]["text"] == "Fictum tibi, Synthipater nate."
    assert flat[1]["text"] == "Annum iam ficticium synthum."


def test_rejoin_cross_section_hyphens_does_not_cross_a_book_boundary():
    # A hyphen at the very end of the last section of book 1 must not reach
    # into book 2's first section — never observed in the real corpus, and
    # this pipeline never wants to guess at it.
    flat = [
        {"column": "1.161", "n": 1, "text": "...ultimum ver-"},
        {"column": "2.1", "n": 1, "text": "bum novi libri."},
    ]
    n = _rejoin_cross_section_hyphens(flat, _manifest([]))
    assert n == 0
    assert flat[0]["text"] == "...ultimum ver-"
    assert flat[1]["text"] == "bum novi libri."


def test_parse_book_section_end_to_end_rejoins_cross_section_hyphen():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="97"><p>syntheticaque fictan-</p></div>
<div type="section" n="98"><p>tium fictarum.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([], {"cross_section_rejoins": 1})
    flat = _parse_book_section(tree, SCHEME, manifest)
    assert flat == [
        {"column": "1.97", "n": 1, "text": "syntheticaque fictantium"},
        {"column": "1.98", "n": 1, "text": "fictarum."},
    ]


def test_parse_book_section_cross_section_rejoin_count_mismatch_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="97"><p>syntheticaque fictan-</p></div>
<div type="section" n="98"><p>tium fictarum.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest([], {"cross_section_rejoins": 7})  # actual is 1
    with pytest.raises(ValueError, match="expected 7 cross-section hyphen"):
        _parse_book_section(tree, SCHEME, manifest)


def test_parse_book_section_no_declared_cross_section_rejoins_skips_count_check():
    # Undeclared citation.cross_section_rejoins means "no-op" (mirrors
    # expected_sourcedesc's own absent-means-no-op precedent) — the rejoin
    # still happens mechanically, just without a count assertion.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="section" n="97"><p>syntheticaque fictan-</p></div>
<div type="section" n="98"><p>tium fictarum.</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_book_section(tree, SCHEME, _manifest([]))
    assert flat[0]["text"] == "syntheticaque fictantium"


# --- Pipeline Change B: flat `section`-scheme Latin walker (Wave 2 Batch 3 --
# --- round 2 — Cato Maior/Laelius/De Fato/Lucullus top-level; Paradoxa     --
# --- paradox-wrapped) — adversarial-review Findings 2 & 3 ------------------

FLAT_SCHEME = scheme_mod.for_manifest({"citation": {"scheme": "section", "div_types": {"page": "section"}}})


def _flat_manifest(citation_extra: dict | None = None) -> Manifest:
    citation = {"scheme": "section", "div_types": {"page": "section"}, "title_labels": []}
    citation.update(citation_extra or {})
    data = {
        "work": {
            "id": "LUC", "phi_author": "0474", "phi_work": "046",
            "latin_edition": "Fixture", "language": "lat",
        },
        "citation": citation,
        "books": [{"n": 1, "start": "1", "end": "999"}],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_parse_flat_section_top_level_no_wrapper():
    # Cato Maior/Laelius/De Fato/Lucullus shape: bare <div type="section">
    # siblings at the top level, no wrapper div at all.
    title = "TITULUS SYNTHETICUS UNUS."
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="t"><p>{title}</p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="2"><p>Secunda sectio.</p></div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"title_labels": [_title_declaration(title)]})
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [
        {"column": "1", "n": 1, "text": "Prima sectio."},
        {"column": "2", "n": 1, "text": "Secunda sectio."},
    ]


def test_parse_flat_section_paradox_wrapped_title_wrapper_is_dropped():
    # Paradoxa shape: a whole-work title division wraps a numbered section
    # that would otherwise collide with the real section of the same
    # number inside a sibling (non-title) wrapper div.
    wrapper_title = "SYNTHETICA PRAEFATIO AD LECTOREM."
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="paradox" n="t">
<div type="section" n="1"><p>{wrapper_title}</p></div>
</div>
<div type="paradox" n="pr">
<div type="section" n="1"><p>Prima sectio realis.</p></div>
<div type="section" n="2"><p>Secunda sectio realis.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({
        "flat_wrapper": {"div_type": "paradox", "n_tokens": ["t", "pr"]},
        "title_labels": [_title_declaration(wrapper_title)],
    })
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [
        {"column": "1", "n": 1, "text": "Prima sectio realis."},
        {"column": "2", "n": 1, "text": "Secunda sectio realis."},
    ]


def test_parse_flat_section_per_paradox_title_with_mixed_script_is_dropped():
    # Paradoxa's real per-paradox headings embed a Greek thesis quotation
    # alongside a Latin ordinal label — mixed-script content the declared-
    # hash mechanism does not care about at all (unlike a Latin-only shape
    # guard). Fixture uses WHOLLY INVENTED Latin-shaped and Greek-shaped
    # words (Finding 1) — no real corpus text, Greek or Latin.
    mixed_title = "SYNTHETICON I. Ξενοπλαστον τυχοπλαστον."
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="paradox" n="1">
<div type="section" n="t"><p>{mixed_title}</p></div>
<div type="section" n="6"><p>Sectio realis sex.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({
        "flat_wrapper": {"div_type": "paradox", "n_tokens": ["1"]},
        "title_labels": [_title_declaration(mixed_title)],
    })
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [{"column": "6", "n": 1, "text": "Sectio realis sex."}]


def test_parse_flat_section_unrecognized_non_digit_n_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="bogus"><p>Nescioquid.</p></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="unrecognized PHI section"):
        _parse_flat_section(tree, FLAT_SCHEME, _flat_manifest())


def test_parse_flat_section_exclude_sections_happy_path():
    # De Fato's fr/fr1/fr2/fr3/fr5 tail: declared tokens are silently
    # dropped rather than raising.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="fr"><p>Fragmentum unum.</p></div>
<div type="section" n="fr1"><p>Fragmentum duo.</p></div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"exclude_sections": ["fr", "fr1"]})
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [{"column": "1", "n": 1, "text": "Prima sectio."}]


def test_parse_flat_section_stale_exclusion_fails_loudly():
    # A declared exclusion that the export no longer contains (a re-export
    # dropped or renumbered it) must fail loudly, not silently pass.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="fr"><p>Fragmentum unum.</p></div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"exclude_sections": ["fr", "fr1"]})  # fr1 never observed
    with pytest.raises(ValueError, match="stale declaration"):
        _parse_flat_section(tree, FLAT_SCHEME, manifest)


def test_parse_flat_section_undeclared_non_digit_token_fails_loudly():
    # A non-digit, non-"t" token NOT declared in exclude_sections is the
    # ordinary fail-loud path, unchanged.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="fr"><p>Fragmentum unum.</p></div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"exclude_sections": ["fr1"]})  # "fr" not declared
    with pytest.raises(ValueError, match="unrecognized PHI section"):
        _parse_flat_section(tree, FLAT_SCHEME, manifest)


def test_parse_flat_section_cross_section_hyphen_rejoin_no_book_boundary_check():
    # Flat scheme has no book axis at all: same_book_required=False means
    # every adjacent pair is eligible (unlike book-section, whose bare
    # column has no "." to split on here anyway).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>syntheticaque fictan-</p></div>
<div type="section" n="2"><p>tium fictarum.</p></div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"cross_section_rejoins": 1})
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [
        {"column": "1", "n": 1, "text": "syntheticaque fictantium"},
        {"column": "2", "n": 1, "text": "fictarum."},
    ]


def test_parse_spine_dispatches_flat_section_scheme():
    title = "SYNTHETICVS TITVLVS."
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="t"><p>{title}</p></div>
<div type="section" n="1"><p>One.</p></div>
<div type="section" n="2"><p>Two.</p></div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _flat_manifest({"title_labels": [_title_declaration(title)]})
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1", "2"]
    assert [s["book"] for s in spine["segments"]] == [1, 1]
    assert spine["unassigned_lines"] == []


# --- Adversarial-review Finding 3: flat-walker depth scoping -----------------


def test_flat_section_nested_rogue_section_div_is_fatal():
    # A section div nested inside an UNDECLARED wrapper (no citation.
    # flat_wrapper at all) must never be silently swept in or silently
    # skipped -- the total section-div count no longer matches the count
    # found at declared positions.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="rogue" n="x">
<div type="section" n="2"><p>Sectio abscondita.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="declared position"):
        _parse_flat_section(tree, FLAT_SCHEME, _flat_manifest())


def test_flat_section_wrapper_type_on_non_div_element_does_not_admit_its_children():
    # citation.flat_wrapper matches by @type value alone; a non-<div> element
    # (e.g. a stray milestone) carrying the declared wrapper's @type must not
    # be treated as a legitimate wrapper -- its nested section div is then an
    # escapee at an undeclared position, caught by the same total-count
    # cross-check the sibling rogue-wrapper test above exercises.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio realis.</p></div>
<milestone type="paradox" n="pr">
<div type="section" n="2"><p>Sectio abscondita.</p></div>
</milestone>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"flat_wrapper": {"div_type": "paradox", "n_tokens": ["pr"]}})
    with pytest.raises(ValueError, match="declared position"):
        _parse_flat_section(tree, FLAT_SCHEME, manifest)


def test_flat_section_duplicate_column_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="section" n="1"><p>Prima sectio.</p></div>
<div type="section" n="1"><p>Sectio iterata.</p></div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="duplicate section column"):
        _parse_flat_section(tree, FLAT_SCHEME, _flat_manifest())


def test_flat_section_undeclared_wrapper_n_is_fatal():
    # A wrapper div type IS declared (citation.flat_wrapper), but this
    # particular wrapper's own @n was not included in its declared
    # n_tokens set -- fatal, never silently walked into or silently skipped.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="paradox" n="pr">
<div type="section" n="1"><p>Prima sectio realis.</p></div>
</div>
<div type="paradox" n="99">
<div type="section" n="2"><p>Sectio non declarata.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"flat_wrapper": {"div_type": "paradox", "n_tokens": ["pr"]}})
    with pytest.raises(ValueError, match="undeclared n="):
        _parse_flat_section(tree, FLAT_SCHEME, manifest)


def test_flat_section_declared_wrapper_happy_path():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="paradox" n="pr">
<div type="section" n="1"><p>Prima sectio realis.</p></div>
<div type="section" n="2"><p>Secunda sectio realis.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _flat_manifest({"flat_wrapper": {"div_type": "paradox", "n_tokens": ["pr"]}})
    flat = _parse_flat_section(tree, FLAT_SCHEME, manifest)
    assert flat == [
        {"column": "1", "n": 1, "text": "Prima sectio realis."},
        {"column": "2", "n": 1, "text": "Secunda sectio realis."},
    ]


# --- `citation.source_book` (Wave 2 Seneca essays, docs/wave2-seneca-       -
# --- design.md §E.3): scope a book-section walk to a single declared PHI   -
# --- <div type="book"> out of a multi-book file, chapter->page/section->   -
# --- column, per _resolve_source_book's own doc comment. ------------------

# Essay shape: citation.div_types.page="chapter" (unlike De Officiis' own
# page="book" override) -- book-section's page axis is the PHI *chapter*
# level, scoped down to one declared Dialogi book via source_book.
ESSAY_SCHEME = scheme_mod.for_manifest(
    {"citation": {"scheme": "book-section", "div_types": {"page": "chapter", "section": "section"}}}
)


def _essay_manifest(citation_extra: dict | None = None) -> Manifest:
    citation = {
        "scheme": "book-section", "div_types": {"page": "chapter", "section": "section"},
        "title_labels": [],
    }
    citation.update(citation_extra or {})
    data = {
        "work": {
            "id": "PROV", "phi_author": "1017", "phi_work": "012",
            "latin_edition": "Fixture", "language": "lat",
        },
        "citation": citation,
        "books": [],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


# A 2-book fixture (mirrors phi1017012.xml's shape: multiple <div type="book">
# siblings, each nesting <div type="chapter"> -> <div type="section">) used
# by every source_book test below. Book "1" and book "2" deliberately reuse
# the SAME chapter/section numbering (chapter 1, section 1) so a leak would
# be caught by content, not merely by an unexpected extra column.
_TWO_BOOK_XML = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="chapter" n="1"><div type="section" n="1"><p>Liber unus, caput unum.</p></div></div>
</div>
<div type="book" n="2">
<div type="chapter" n="1"><div type="section" n="1"><p>Liber duo, caput unum.</p></div></div>
</div>
</body></text></TEI>"""


def test_resolve_source_book_absent_declaration_is_a_noop():
    tree = _tree(_TWO_BOOK_XML)
    assert _resolve_source_book(tree, _essay_manifest()) is None


def test_resolve_source_book_absent_from_export_is_fatal():
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": "9"})
    with pytest.raises(ValueError, match="must match exactly one"):
        _resolve_source_book(tree, manifest)


def test_resolve_source_book_returns_the_declared_book_element():
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": "2"})
    scoped = _resolve_source_book(tree, manifest)
    assert scoped.get("type") == "book"
    assert scoped.get("n") == "2"


def test_source_book_scoping_extracts_only_the_declared_book():
    # Declared-book extraction: book 1's own chapter/section content, and
    # only that content, is emitted -- book 2's identically-numbered
    # chapter/section is never visited (see _resolve_source_book's own doc
    # comment: a scoped .iter() cannot structurally reach a sibling book).
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": "1"})
    flat = _parse_book_section(tree, ESSAY_SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "Liber unus, caput unum."}]


def test_source_book_scoping_rejects_leaked_content():
    # Leak-rejection regression: were the scoping to (incorrectly) walk the
    # whole tree instead of the declared book's own subtree, book 2's
    # identically-numbered chapter 1 / section 1 would collide with book 1's
    # -- this fixture exists specifically to catch that regression by content
    # (book 2's distinct sentence must never appear when source_book="1").
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": "1"})
    flat = _parse_book_section(tree, ESSAY_SCHEME, manifest)
    texts = [seg["text"] for seg in flat]
    assert "Liber duo, caput unum." not in texts


def test_source_book_scoping_second_book():
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": "2"})
    flat = _parse_book_section(tree, ESSAY_SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "Liber duo, caput unum."}]


def test_source_book_must_be_a_non_empty_string():
    tree = _tree(_TWO_BOOK_XML)
    manifest = _essay_manifest({"source_book": 1})  # int, not str
    with pytest.raises(ValueError, match="non-empty string"):
        _resolve_source_book(tree, manifest)


def test_source_book_scoping_drops_the_chapter_title_heading():
    # E.3: each essay's per-book chapter n="t" heading is title-dropped by
    # the existing page_n == "t" branch -- "page" is now the chapter.
    title = "CAPUT SYNTHETICUM TITULI"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="chapter" n="t"><div type="section" n="1"><p>{title}</p></div></div>
<div type="chapter" n="1"><div type="section" n="1"><p>Prima sectio.</p></div></div>
</div>
</body></text></TEI>"""
    )
    manifest = _essay_manifest({"source_book": "1", "title_labels": [_title_declaration(title)]})
    flat = _parse_book_section(tree, ESSAY_SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "Prima sectio."}]


def test_source_book_scoping_undeclared_chapter_token_is_fatal():
    # "undeclared chapter tokens" (design note's fail-loud item): a chapter
    # @n that is neither a plain digit string nor the title marker "t".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="chapter" n="bogus"><div type="section" n="1"><p>Nescioquid.</p></div></div>
</div>
</body></text></TEI>"""
    )
    manifest = _essay_manifest({"source_book": "1"})
    with pytest.raises(ValueError, match="unrecognized PHI chapter"):
        _parse_book_section(tree, ESSAY_SCHEME, manifest)


def test_source_book_scoping_rejoins_a_chapter_seam_hyphen():
    # E.5: essays run the cross-section hyphen rejoin with
    # same_book_required=False -- a print-line wrap can legitimately
    # straddle a chapter seam (the essay's "book" axis is really the
    # chapter).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="chapter" n="1"><div type="section" n="6"><p>fictan-</p></div></div>
<div type="chapter" n="2"><div type="section" n="1"><p>tium synthera.</p></div></div>
</div>
</body></text></TEI>"""
    )
    manifest = _essay_manifest({"source_book": "1", "cross_section_rejoins": 1})
    flat = _parse_book_section(tree, ESSAY_SCHEME, manifest)
    assert flat == [
        {"column": "1.6", "n": 1, "text": "fictantium"},
        {"column": "2.1", "n": 1, "text": "synthera."},
    ]


def test_source_book_scoping_end_to_end_via_parse_spine():
    title = "CAPUT SYNTHETICUM TITULI"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<div type="chapter" n="t"><div type="section" n="1"><p>{title}</p></div></div>
<div type="chapter" n="1"><div type="section" n="1"><p>One.</p></div></div>
<div type="chapter" n="2"><div type="section" n="1"><p>Two.</p></div></div>
</div>
<div type="book" n="2">
<div type="chapter" n="1"><div type="section" n="1"><p>Should never appear.</p></div></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _essay_manifest({
            "source_book": "1",
            "title_labels": [_title_declaration(title)],
        })
        manifest.data["books"] = [{"n": 1, "start": "1.1", "end": "2.1"}]
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1.1", "2.1"]
    assert all("never appear" not in "".join(l["text"] for l in s["lines"]) for s in spine["segments"])


# --- `letter` scheme (Wave 2 Seneca -- Epistulae Morales, PHI 1017/015;    -
# --- design note docs/wave2-seneca-design.md SS A-D): salutation fold,     -
# --- letter "t" shell skip (incl. the naive-section-rule trap case),      -
# --- embedded section "t" declared drops, exclude_letters bidirectional. --

LETTER_SCHEME = scheme_mod.for_manifest({"citation": {"scheme": "letter"}})


def _letter_manifest(citation_extra: dict | None = None) -> Manifest:
    citation = {
        "scheme": "letter",
        "title_labels": [],
        "salutation_role": True,
        "exclude_letters": [],
    }
    citation.update(citation_extra or {})
    data = {
        "work": {
            "id": "EP", "phi_author": "1017", "phi_work": "015",
            "latin_edition": "Fixture", "language": "lat",
        },
        "citation": citation,
        "books": [],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_letters_salutation_attaches_as_a_leading_role_line_on_section_1():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>SYNTHIPATER SODALI SVO SALVTEM.</p></div>
<div type="section" n="1"><p>Prima sectio epistulae.</p></div>
<div type="section" n="2"><p>Secunda sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_letters(tree, LETTER_SCHEME, _letter_manifest())
    assert flat == [
        {"column": "1.1", "n": 1, "text": "SYNTHIPATER SODALI SVO SALVTEM.", "role": "salutation"},
        {"column": "1.1", "n": 2, "text": "Prima sectio epistulae."},
        {"column": "1.2", "n": 1, "text": "Secunda sectio."},
    ]


def test_letters_missing_salutation_before_section_1_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="1"><p>Prima sectio epistulae.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="has no section n=\"sa\""):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_duplicate_salutation_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Prima salutatio.</p></div>
<div type="section" n="sa"><p>Altera salutatio.</p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="more than one section"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_salutation_with_no_section_1_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio orphana.</p></div>
<div type="section" n="2"><p>Non prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="no section \"1\" to attach"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_no_salutation_role_flag_leaves_sa_unattached_and_fatal():
    # Without citation.salutation_role, an "sa" section is just an
    # unrecognized non-digit token -- the flag gates the whole mechanism,
    # it does not silently no-op into "drop sa".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"salutation_role": False})
    with pytest.raises(ValueError, match="unrecognized PHI section"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_salutation_role_string_false_is_fatal_not_truthy():
    # A YAML authoring slip -- "false" quoted as a string -- must fail
    # loud, not silently coerce via bool("false") == True.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"salutation_role": "false"})
    with pytest.raises(ValueError, match="must be a real boolean"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_salutation_role_non_bool_truthy_value_is_fatal():
    # Same schema-validation gate, a different non-bool shape (an int).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"salutation_role": 1})
    with pytest.raises(ValueError, match="must be a real boolean"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_empty_salutation_div_is_fatal_not_silently_dropped():
    # An "sa" div with no text used to silently skip the
    # pending_salutations write while still counting as "seen" -- passing
    # the "has exactly one sa" check while attaching nothing to section 1.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p></p></div>
<div type="section" n="1"><p>Prima sectio.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="salutation is empty"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_t_shell_is_skipped_as_a_whole_page_not_via_the_naive_section_rule():
    # SS C.1's explicit trap: the pre-letter-1 shell's own book-1 heading
    # label lives at <section n="1"> INSIDE <letter n="t">, not at
    # <section n="t"> -- a naive "drop section n='t'" rule would never fire
    # on it (there is no section n="t" here at all) and it would leak in as
    # a phantom "t.1" column. The real walker must skip the whole letter
    # n="t" page up front instead -- and restore its text (REVIEW-CHECKLIST
    # item 5) as a leading role="heading" line on letter 1's own section 1,
    # ahead of the role="salutation" line.
    heading = "LIBER PRIMVS SYNTHETICVS"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="t">
<div type="section" n="1"><p>{heading}</p></div>
</div>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"title_labels": [_title_declaration(heading)]})
    flat = _parse_letters(tree, LETTER_SCHEME, manifest)
    # No phantom "t.1" column -- the shell's own text now leads letter 1's
    # section 1, heading before salutation before the real text.
    assert [f["column"] for f in flat] == ["1.1", "1.1", "1.1"]
    assert flat[0] == {"column": "1.1", "n": 1, "text": heading, "role": "heading"}
    assert flat[1] == {"column": "1.1", "n": 1, "text": "Salutatio.", "role": "salutation"}
    assert flat[2] == {"column": "1.1", "n": 2, "text": "Prima epistula."}


def test_letters_t_shell_undeclared_heading_content_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="t">
<div type="section" n="1"><p>Titulus non declaratus.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="not declared"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_t_shell_with_wrong_nested_section_count_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="t">
<div type="section" n="1"><p>Unum.</p></div>
<div type="section" n="2"><p>Duo.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="direct child element"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_t_shell_with_rogue_sibling_div_is_fatal():
    # A shell carrying its one real section div PLUS an extra sibling (a
    # stray "note"-typed div) must fail loud, not silently discard the
    # extra content -- the old check only counted section-typed direct
    # children, so this rogue sibling would have passed unnoticed.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="t">
<div type="section" n="1"><p>Titulus.</p></div>
<div type="note"><p>Nota spuria.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="direct child element"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_t_shell_with_rogue_non_div_sibling_is_fatal():
    # A non-div direct child (a bare <p>) alongside the one real section
    # div must ALSO fail loud -- the old check filtered on "{*}div" before
    # counting, so a non-div sibling was invisible to it entirely.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="t">
<div type="section" n="1"><p>Titulus.</p></div>
<p>Textus vagus.</p>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="direct child element"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_embedded_section_t_heading_is_declared_and_restored():
    # SS C.2: one of the 17 embedded per-Liber headings, inside a real
    # letter, alongside its salutation/section-1 -- both mechanisms
    # (title_labels verification for the heading, salutation_role for "sa")
    # coexist. Restored (REVIEW-CHECKLIST item 5) as a leading
    # role="heading" line, ahead of role="salutation", ahead of the real
    # section-1 text -- never its own citable column.
    heading = "LIBER SECVNDVS SYNTHETICVS"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="13">
<div type="section" n="t"><p>{heading}</p></div>
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Tertia decima epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"title_labels": [_title_declaration(heading)]})
    flat = _parse_letters(tree, LETTER_SCHEME, manifest)
    assert [f["column"] for f in flat] == ["13.1", "13.1", "13.1"]
    assert flat[0] == {"column": "13.1", "n": 1, "text": heading, "role": "heading"}
    assert flat[1] == {"column": "13.1", "n": 1, "text": "Salutatio.", "role": "salutation"}
    assert flat[2] == {"column": "13.1", "n": 2, "text": "Tertia decima epistula."}


def test_letters_without_a_heading_emit_no_heading_line():
    # A letter that carries no preceding "t" (neither a shell nor an
    # embedded section) -- e.g. Seneca's real letter 2, or any letter
    # sitting inside the manuscript-tradition gap at Books XII/XIII/XVIII
    # (John's ruling: left silent, no editorial note, and the pipeline
    # already only emits what the export declares -- this asserts ABSENCE
    # only, nothing more) -- must emit no role="heading" line at all.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
<div type="letter" n="2">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Secunda epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    flat = _parse_letters(tree, LETTER_SCHEME, _letter_manifest())
    assert all(f.get("role") != "heading" for f in flat)
    assert [f["column"] for f in flat] == ["1.1", "1.1", "2.1", "2.1"]


def test_letters_embedded_section_t_undeclared_content_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="13">
<div type="section" n="t"><p>Titulus non declaratus.</p></div>
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="not declared"):
        _parse_letters(tree, LETTER_SCHEME, _letter_manifest())


def test_letters_title_label_count_mismatch_fails_loudly():
    # 18 total drops expected (shell + 17 embedded) -- a declared multiset
    # that does not match what was actually observed is fatal, mirroring
    # book-section's _finalize_title_drops bidirectional check.
    heading = "LIBER SECVNDVS SYNTHETICVS"
    other_heading = "NVMQVAM VISVS TITVLVS"
    tree = _tree(
        f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="13">
<div type="section" n="t"><p>{heading}</p></div>
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest(
        {"title_labels": [_title_declaration(heading), _title_declaration(other_heading)]}
    )
    with pytest.raises(ValueError, match="title-label count mismatch"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_exclude_letters_fr_is_skipped_wholesale_and_never_descended():
    # SS D: letter n="fr" is excluded before any of its own sections
    # (including its own internal n="t" heading, per the design note) are
    # ever visited -- an undeclared title inside "fr" must NOT trip the
    # title-drop gate, proving it is genuinely never descended into.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
<div type="letter" n="fr">
<div type="section" n="t"><p>Titulus numquam declaratus, numquam visus.</p></div>
<div type="section" n="1"><p>Fragmentum Gellianum.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"exclude_letters": ["fr"]})
    flat = _parse_letters(tree, LETTER_SCHEME, manifest)
    assert [f["column"] for f in flat] == ["1.1", "1.1"]
    assert all("Gellianum" not in f["text"] for f in flat)


def test_letters_exclude_letters_stale_declaration_is_fatal():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    # "fr" declared but the export never contains it -- a re-export drift
    # tripwire, same bidirectional shape as exclude_sections.
    manifest = _letter_manifest({"exclude_letters": ["fr"]})
    with pytest.raises(ValueError, match="stale declaration"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_exclude_letters_duplicate_declaration_is_fatal():
    # A duplicate in the MANIFEST'S OWN declaration ("fr" listed twice) --
    # distinct from test_letters_exclude_letters_stale_declaration_is_fatal,
    # which is about the declaration vs. the export. `set(...)` alone would
    # silently collapse this typo; it must fail loud instead, naming the
    # duplicate, before the export is even walked.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
<div type="letter" n="fr">
<div type="section" n="1"><p>Fragmentum Gellianum.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"exclude_letters": ["fr", "fr"]})
    with pytest.raises(ValueError, match="duplicate token"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_undeclared_exclusion_fails_as_ordinary_unrecognized_token():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
<div type="letter" n="fr">
<div type="section" n="1"><p>Fragmentum.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"exclude_letters": []})  # "fr" not declared
    with pytest.raises(ValueError, match="unrecognized PHI letter"):
        _parse_letters(tree, LETTER_SCHEME, manifest)


def test_letters_cross_section_rejoin_declared_count_checked():
    # Within one letter only -- same_book_required=True (the letter IS the
    # "book" for this scheme, exactly like book-section) never rejoins
    # across a LETTER boundary, only across a section boundary within one.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
<div type="section" n="2"><p>fictan-</p></div>
<div type="section" n="3"><p>tium synthera.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"cross_section_rejoins": 1})
    flat = _parse_letters(tree, LETTER_SCHEME, manifest)
    texts = {f["column"]: f["text"] for f in flat}
    assert texts["1.2"] == "fictantium"
    assert texts["1.3"] == "synthera."


def test_letters_cross_section_rejoin_never_crosses_a_letter_boundary():
    # The letter-boundary analogue of _parse_book_section's own
    # never-crosses-a-book-boundary test: a hyphen wrap that happens to
    # straddle two letters is left untouched (same_book_required=True), a
    # re-export-drift tripwire on citation.cross_section_rejoins would
    # catch a genuine such wrap appearing in the real export.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>fictan-</p></div>
</div>
<div type="letter" n="2">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>tium synthera.</p></div>
</div>
</body></text></TEI>"""
    )
    manifest = _letter_manifest({"cross_section_rejoins": 0})
    flat = _parse_letters(tree, LETTER_SCHEME, manifest)
    texts = {f["column"]: f["text"] for f in flat if "role" not in f}
    assert texts["1.1"] == "fictan-"
    assert texts["2.1"] == "tium synthera."


def test_parse_spine_dispatches_letter_scheme_end_to_end():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="letter" n="1">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Prima epistula.</p></div>
</div>
<div type="letter" n="2">
<div type="section" n="sa"><p>Salutatio.</p></div>
<div type="section" n="1"><p>Secunda epistula.</p></div>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _letter_manifest()
        manifest.data["books"] = [
            {"n": 1, "start": "1.1", "end": "1.1"},
            {"n": 2, "start": "2.1", "end": "2.1"},
        ]
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1.1", "2.1"]
    assert [s["book"] for s in spine["segments"]] == [1, 2]
    first_seg = spine["segments"][0]
    assert [l["n"] for l in first_seg["lines"]] == [1, 2]
    assert first_seg["lines"][0]["role"] == "salutation"
    assert "role" not in first_seg["lines"][1]
    assert spine["unassigned_lines"] == []
