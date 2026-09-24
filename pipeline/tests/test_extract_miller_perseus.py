"""Regression tests for tools/extract_miller_perseus.py's TEI-milestone
walking. No network: these exercise `_walk`/`_extract_book` on minimal
synthetic TEI fragments replicating the exact structures Perseus's real
phi0474.phi055.perseus-eng1.xml uses (see the module docstring for full
citations to the real-file line numbers each case mirrors).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import lxml.etree as ET
import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_miller_perseus", _TOOLS / "extract_miller_perseus.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_miller_perseus"] = _mod
_spec.loader.exec_module(_mod)

_TEI_OPEN = '<div xmlns="http://www.tei-c.org/ns/1.0" type="textpart" subtype="book" n="{n}">'
_PINNED_XML = (
    Path(__file__).resolve().parent.parent.parent
    / "sources/miller-de-officiis/phi0474.phi055.perseus-eng1.xml"
)


def _book(n: str, inner: str) -> ET._Element:
    return ET.fromstring(_TEI_OPEN.format(n=n) + inner + "</div>")


def test_milestone_splits_across_paragraph_boundaries():
    # Mirrors 2.88/2.89: a "<p>" opens with one section's tail and a NEW
    # milestone fires mid-<p> (no <p> boundary aligns with a section
    # boundary), while a separate <p> also belongs to the earlier section.
    book = _book("1", """
        <head>Book I title -- dropped, no section open yet</head>
        <p><milestone unit="section" n="1"/> First section opens here.</p>
        <p>Still first section, a second paragraph.<milestone unit="section" n="2"/> Second section starts mid-paragraph.</p>
    """)
    out, last, _labels = _mod._extract_book(book, 1)
    assert out["1.1"] == "First section opens here. Still first section, a second paragraph."
    assert out["1.2"] == "Second section starts mid-paragraph."
    assert last == 2


def test_chapter_and_alternatesection_milestones_are_ignored():
    # Mirrors 1.15's real structure: a genuine "section" milestone opens the
    # section, then BOTH a "chapter" and (elsewhere, same section) an
    # "alternatesection" milestone appear inside it with no effect on the
    # open section -- their tail text stays attached to the real section.
    book = _book("1", """
        <p><milestone unit="section" n="1"/><milestone unit="chapter" n="1"/> Text after a chapter milestone.
        <milestone unit="alternatesection" n="1"/> Text after an alternatesection milestone.</p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == (
        "Text after a chapter milestone. Text after an alternatesection milestone."
    )


def test_note_dropped_whole_both_marg_and_untyped():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> Before<note type="marg">a running summary, dropped</note> and
        after<note>an untyped footnote, also dropped</note> the notes.</p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == "Before and after the notes."


def test_duplicate_section_number_within_book_raises():
    # Review blocker: setdefault() silently merged a repeated unit="section"
    # number (sequence 1,2,1). A second n=1 must fail loud.
    book = _book("1", """
        <p><milestone unit="section" n="1"/> First.
        <milestone unit="section" n="2"/> Second.
        <milestone unit="section" n="1"/> Duplicate one.</p>
    """)
    with pytest.raises(ValueError, match="duplicate unit=section n=1"):
        _mod._extract_book(book, 1)


def test_dropped_note_inserts_space_at_alphanumeric_boundary():
    # Review blocker: word<note>x</note>word must not silently emit wordword.
    book = _book("1", """
        <p><milestone unit="section" n="1"/>word<note>x</note>word</p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == "word word"


def test_greek_foreign_decoded_from_beta_code():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> for the Greeks call it
        <foreign xml:lang="greek">kato/rqwma,</foreign> while the ordinary duty
        they call <foreign xml:lang="greek">kaqh=kon.</foreign></p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == (
        "for the Greeks call it κατόρθωμα, while the ordinary duty they call καθῆκον."
    )


def test_greek_terms_table_all_eleven_distinct_and_no_dead_entries():
    """Every _GREEK_TERMS entry must occur in the pinned XML body (not only
    inside dropped notes), and every body Greek string must be in the table.
    Dead-entry protection: an unused table key fails the test. Also locks
    the corpus counts (13 body occurrences, 11 distinct)."""
    assert _PINNED_XML.exists(), f"missing pinned source {_PINNED_XML}"
    tree = ET.parse(str(_PINNED_XML))
    body = tree.getroot().find(".//t:text/t:body", _mod._NS)
    assert body is not None
    body_raws: list[str] = []
    for el in body.iter():
        if not isinstance(el.tag, str) or not el.tag.endswith("foreign"):
            continue
        if el.get(_mod._XML_LANG) != "greek":
            continue
        if any(
            isinstance(a.tag, str) and a.tag.endswith("note")
            for a in el.iterancestors()
        ):
            continue
        body_raws.append((el.text or "").strip())
    distinct = set(body_raws)
    assert len(body_raws) == 13, f"expected 13 body Greek strings, got {len(body_raws)}"
    assert len(distinct) == 11, f"expected 11 distinct body Greek strings, got {len(distinct)}"
    assert distinct == set(_mod._GREEK_TERMS.keys()), (
        f"body Greek set {distinct!r} != table keys {set(_mod._GREEK_TERMS.keys())!r}"
    )
    # All 11 distinct mappings present and decode to the pinned Unicode forms.
    assert len(_mod._GREEK_TERMS) == 11
    for raw, unicode_form in _mod._GREEK_TERMS.items():
        assert raw in distinct, f"dead _GREEK_TERMS entry never seen in body: {raw!r}"
        assert unicode_form, f"empty decode for {raw!r}"
    # Spot-check the full table (every mapping is a known Stoic term shape).
    assert _mod._GREEK_TERMS == {
        "kato/rqwma,": "κατόρθωμα,",
        "kaqh=kon.": "καθῆκον.",
        "pre/pon.": "πρέπον.",
        "o(rmh/,": "ὁρμή,",
        "ei)/rwn": "εἴρων",
        "eu)taci/a": "εὐταξία",
        "eu)kairi/a,": "εὐκαιρία,",
        "sofi/a;": "σοφία;",
        "fro/nhsis,": "φρόνησις,",
        "pa/qh": "πάθη",
        "o(rmai/": "ὁρμαί",
    }


def test_unrecognized_greek_foreign_fails_loud():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> An unknown term:
        <foreign xml:lang="greek">bogus/term</foreign></p>
    """)
    with pytest.raises(ValueError, match="unexpected Greek"):
        _mod._extract_book(book, 1)


def test_quote_wrapped_in_curly_quotes_alternating_by_depth():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> call it <quote>right,</quote> for
        the Greeks call it right.</p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == "call it “right,” for the Greeks call it right."


def test_blockquote_verse_passes_through_with_no_quote_marks():
    # Mirrors the Accius Thyestes/Atreus exchange (3.102): a <quote
    # rend="blockquote"> wrapping <sp>/<speaker>/<l> gets no curly marks of
    # its own (only the surrounding plain <quote> does), and speaker names
    # are kept as ordinary running text.
    book = _book("1", """
        <p><milestone unit="section" n="1"/> <quote>the lines of Accius:
        <quote rend="blockquote"><sp><speaker>Thyestes.</speaker>
        <l>'Hast thou broke thy faith?'</l></sp></quote> a wicked king.</quote></p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out["1.1"] == (
        "“the lines of Accius: Thyestes. 'Hast thou broke thy faith?' a wicked king.”"
    )


def test_book_numbered_by_document_order_not_at_attribute():
    # Mirrors the real Book III data bug: its own @n is "1", the same as
    # Book I's. _extract_book must never be handed the div's own @n as the
    # book index -- the CALLER (main()'s enumerate(books, start=1)) supplies
    # the document-order index instead. This test locks in that the div's
    # own (wrong) @n plays no role in the emitted key.
    mislabeled_book_three = _book("1", '<p><milestone unit="section" n="1"/> Book three text.</p>')
    out, _, _ = _mod._extract_book(mislabeled_book_three, 3)
    assert out == {"3.1": "Book three text."}


def test_main_enumerates_three_books_by_document_order_not_at_n():
    """Integration-style lock on main()'s book enumeration: findall in
    document order + enumerate(..., start=1), never book.get("n"). A
    refactor that used @n would collapse mislabeled Book III into book 1."""
    tei = """<?xml version="1.0"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <text><body>
        <div type="textpart" subtype="book" n="1">
          <p><milestone unit="section" n="1"/> Book one.</p>
        </div>
        <div type="textpart" subtype="book" n="2">
          <p><milestone unit="section" n="1"/> Book two.</p>
        </div>
        <div type="textpart" subtype="book" n="1">
          <p><milestone unit="section" n="1"/> Book three (mislabeled n=1).</p>
        </div>
      </body></text>
    </TEI>
    """
    root = ET.fromstring(tei.encode("utf-8"))
    body = root.find(".//t:text/t:body", _mod._NS)
    # Same query main() uses.
    books = body.findall('.//t:div[@subtype="book"]', _mod._NS)
    assert len(books) == 3
    out: dict[str, str] = {}
    for book_idx, book in enumerate(books, start=1):
        book_out, _, _ = _mod._extract_book(book, book_idx)
        out.update(book_out)
    assert out == {
        "1.1": "Book one.",
        "2.1": "Book two.",
        "3.1": "Book three (mislabeled n=1).",
    }
    # Contrast: using @n would clobber book 1 with book 3's text and never
    # emit a 3.x key -- the failure mode this test guards against.
    wrong: dict[str, str] = {}
    for book in books:
        book_out, _, _ = _mod._extract_book(book, int(book.get("n")))
        wrong.update(book_out)
    assert "3.1" not in wrong
    assert wrong["1.1"] == "Book three (mislabeled n=1)."


def test_non_contiguous_section_numbers_fail_loud():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> First.
        <milestone unit="section" n="3"/> Skips two.</p>
    """)
    with pytest.raises(AssertionError, match="non-contiguous"):
        _mod._extract_book(book, 1)


def test_text_before_first_milestone_is_dropped():
    book = _book("1", """
        <head>Book I: the title, before any section is open</head>
        <p><milestone unit="section" n="1"/> Real content.</p>
    """)
    out, _, _ = _mod._extract_book(book, 1)
    assert out == {"1.1": "Real content."}


def test_clean_collapses_whitespace_and_tightens_punctuation():
    assert _mod._clean(["a  b\n\nc", "  ,", " d"]) == "a b c, d"


def test_leading_chapter_roman_label_stripped_at_section_start():
    # Content audit: 2.44 opens "(XIII.) But, although…" — Miller's chapter
    # roman numeral living in the TEI body after the section milestone.
    book = _book("1", """
        <p><milestone unit="section" n="1"/> (XIII.) But, although the essence.</p>
    """)
    out, _, labels = _mod._extract_book(book, 1)
    assert out["1.1"] == "But, although the essence."
    assert "(XIII.)" not in out["1.1"]
    assert labels == ["1.1"]


def test_patch_3_38_lie_to_he_drives_real_patches_entry():
    """Drives the real PATCHES.json 3.38 entry (Perseus 'lie' → print 'he')."""
    patches = _mod._load_patches()
    p338 = [p for p in patches if p.get("chapter") == "3.38"]
    assert len(p338) == 1, f"expected exactly one 3.38 patch, got {p338!r}"
    old, new = p338[0]["replace"][0]
    assert old == "while lie himself"
    assert new == "while he himself"
    # Synthetic section text carrying the typo, shaped like the real 3.38.
    out = {
        "3.38": (
            "he became invisible to everyone, while lie himself saw everything; "
            "but as often as he turned it back"
        )
    }
    patched = _mod._apply_patches(out, patches)
    assert "while he himself" in patched["3.38"]
    assert "while lie himself" not in patched["3.38"]
    # Exact-once enforcement: a second apply must fail (old no longer present).
    with pytest.raises(ValueError, match="matched 0 times"):
        _mod._apply_patches(dict(patched), patches)
