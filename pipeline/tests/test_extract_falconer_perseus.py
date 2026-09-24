"""Regression tests for tools/extract_falconer_perseus.py -- the three
TEI-shape walkers (flat milestone-cursor / per-section-div / Miller-shape
per-book milestone-cursor). No network: these exercise the walkers on
minimal synthetic TEI fragments replicating the exact structures Perseus's
real phi0474.phi051/.phi052/.phi053 files use (see the module docstring for
full citations). A handful of tests also touch the pinned real XML files to
lock in corpus-level facts (Greek-term coverage, section counts).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import lxml.etree as ET
import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_falconer_perseus", _TOOLS / "extract_falconer_perseus.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_falconer_perseus"] = _mod
_spec.loader.exec_module(_mod)

_NS_DECL = 'xmlns="http://www.tei-c.org/ns/1.0"'


def _flat(inner: str) -> ET._Element:
    return ET.fromstring(f'<div {_NS_DECL} type="translation">{inner}</div>')


def _section_div(n: str, inner: str) -> ET._Element:
    return ET.fromstring(
        f'<div {_NS_DECL} type="textpart" subtype="section" n="{n}">{inner}</div>'
    )


def _book(n: str, inner: str) -> ET._Element:
    return ET.fromstring(
        f'<div {_NS_DECL} type="textpart" subtype="book" n="{n}">{inner}</div>'
    )


# --- shared _walk semantics (mirrors extract_miller_perseus.py's coverage) --

def test_flat_milestone_splits_across_paragraph_boundaries():
    root = _flat("""
        <head>Work title -- dropped, no section open yet</head>
        <p><milestone unit="section" n="1"/> First section opens here.</p>
        <p>Still first section, second paragraph.<milestone unit="section" n="2"/> Second section starts mid-paragraph.</p>
    """)
    ctx = _mod._Ctx()
    _mod._walk(root, ctx, milestone_units=("section",))
    assert _mod._clean(ctx.sections[1]) == "First section opens here. Still first section, second paragraph."
    assert _mod._clean(ctx.sections[2]) == "Second section starts mid-paragraph."


def test_chapter_milestone_ignored_in_flat_walk():
    ctx = _mod._Ctx()
    root = _flat("""
        <p><milestone unit="section" n="1"/><milestone unit="chapter" n="1"/> Text after a chapter milestone.</p>
    """)
    _mod._walk(root, ctx, milestone_units=("section",))
    assert _mod._clean(ctx.sections[1]) == "Text after a chapter milestone."


def test_note_and_bibl_both_dropped_whole():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(
        f'<p {_NS_DECL}>Before<note>a footnote, dropped</note> and '
        f'<cit><quote rend="blockquote">verse</quote><bibl>From Ennius, dropped too</bibl></cit>after.</p>'
    )
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        if _mod._local(child.tag) in _mod._DROPPED_WHOLE:
            _mod._append_after_dropped(ctx, child.tail)
        else:
            ctx.append(child.tail)
    ctx.append(el.text)
    text = _mod._clean(ctx.sections[1])
    assert "footnote" not in text
    assert "Ennius" not in text
    assert "verse" in text
    assert "after" in text


def test_duplicate_section_number_without_known_fix_raises():
    root = _flat("""
        <p><milestone unit="section" n="1"/> First.
        <milestone unit="section" n="2"/> Second.
        <milestone unit="section" n="2"/> Duplicate two -- no fix table entry for 2.</p>
    """)
    with pytest.raises(ValueError, match="duplicate unit='section' n=2"):
        _mod._walk(root, _mod._Ctx(), milestone_units=("section",))


def test_duplicate_35_corrected_to_36_via_hand_verified_fix():
    """Drives the real De Senectute bug: the SECOND unit=section n=35
    milestone is corrected to 36 via _DUPLICATE_MILESTONE_FIX, when
    duplicate_fix is passed explicitly (as only _extract_flat_milestone
    does)."""
    ctx = _mod._Ctx()
    root = _flat("""
        <p><milestone unit="section" n="35"/> First 35 (real).
        <milestone unit="section" n="35"/> Second 35, corrected to 36.
        <milestone unit="section" n="37"/> Real 37.</p>
    """)
    _mod._walk(root, ctx, milestone_units=("section",), duplicate_fix=_mod._DUPLICATE_MILESTONE_FIX)
    assert set(ctx.sections) == {35, 36, 37}
    assert _mod._clean(ctx.sections[36]) == "Second 35, corrected to 36."


def test_duplicate_35_still_fatal_without_duplicate_fix_passed():
    """MAJOR 1 regression: the {35: 36} repair is scoped to the De Senectute
    walker only -- a caller that does NOT pass duplicate_fix (every other
    walk in this corpus, including De Divinatione's per-book walk) must
    still fail loud on a duplicate n=35, exactly like any other duplicate."""
    root = _flat("""
        <p><milestone unit="section" n="35"/> First 35 (real).
        <milestone unit="section" n="35"/> Second 35 -- NOT corrected here.
        <milestone unit="section" n="37"/> Real 37.</p>
    """)
    with pytest.raises(ValueError, match="duplicate unit='section' n=35"):
        _mod._walk(root, _mod._Ctx(), milestone_units=("section",))


def test_duplicate_35_in_de_divinatione_shaped_walk_is_fatal():
    """MAJOR 1's required negative test: a synthetic duplicate n=35 inside a
    De-Divinatione-shaped (book div, per-book milestone walk) source must
    raise, since _extract_book_milestone never passes duplicate_fix -- the
    De Senectute repair does not leak into De Divinatione's walker."""
    book = _book("1", """
        <p><milestone unit="section" n="35"/> First 35.
        <milestone unit="section" n="35"/> Duplicate 35, De Divinatione shape.</p>
    """)
    with pytest.raises(ValueError, match="duplicate unit='section' n=35"):
        _mod._extract_book_milestone(book, expected_max=35, allow_missing=set())


def test_dropped_element_inserts_space_at_alphanumeric_boundary():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(f'<p {_NS_DECL}>word<note>x</note>word</p>')
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        _mod._append_after_dropped(ctx, child.tail)
    assert _mod._clean(ctx.sections[1]) == "word word"


def test_greek_foreign_decoded_from_beta_code():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(
        f'<p {_NS_DECL}>the Greeks call it <foreign xml:lang="greek">mantikh/</foreign>.</p>'
    )
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    assert _mod._clean(ctx.sections[1]) == "the Greeks call it μαντική."


def test_unrecognized_greek_foreign_fails_loud():
    el = ET.fromstring(f'<p {_NS_DECL}><foreign xml:lang="greek">bogus/term</foreign></p>')
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    with pytest.raises(ValueError, match="unexpected Beta-Code Greek"):
        for child in el:
            _mod._walk(child, ctx, milestone_units=("section",))


def test_grc_foreign_passes_through_as_unicode():
    """De Amicitia's alternate (already-Unicode) convention -- defensive
    pass-through path, verified corpus-wide to never fire on real data (see
    _assert_grc_all_in_notes) but must still behave correctly if it did."""
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(f'<p {_NS_DECL}>the term <foreign xml:lang="grc">φιλότης</foreign> means love.</p>')
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    assert _mod._clean(ctx.sections[1]) == "the term φιλότης means love."


def test_quote_and_q_both_wrapped_in_curly_quotes_alternating_by_depth():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(
        f'<p {_NS_DECL}>call it <quote>right,</quote> and also <q type="emph">wise</q>.</p>'
    )
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    assert _mod._clean(ctx.sections[1]) == "call it “right,” and also “wise”."


def test_blockquote_verse_and_type_blockquote_prose_are_distinct():
    """rend=blockquote (verse, <l> children) passes through with no marks;
    type=blockquote (no rend) with NO <l> children is treated as a REGULAR
    quote -- confirmed against the archive.org print (De Amicitia's Terence
    Eunuchus tag prints WITH quotation marks). Miller's _is_verse_quote
    (rend-only check) already gets this right unchanged."""
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(f"""<p {_NS_DECL}>
        <quote rend="blockquote"><l>Verse line one</l></quote>
        <quote type="blockquote">He says nay.</quote>
    </p>""")
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    text = _mod._clean(ctx.sections[1])
    assert "Verse line one" in text and "“Verse line one”" not in text
    assert "“He says nay.”" in text


def test_hi_emph_title_lat_foreign_all_plain_passthrough():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(f"""<p {_NS_DECL}>the <hi rend="italics">term</hi> called
        <foreign xml:lang="lat" rend="italic">amicitia</foreign> in his
        <title rend="italic">Cato the Elder</title> and <emph rend="italic">that</emph>.</p>""")
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    text = _mod._clean(ctx.sections[1])
    assert text == "the term called amicitia in his Cato the Elder and that."


def test_said_and_label_pass_through_as_running_text():
    ctx = _mod._Ctx()
    ctx.current = 1
    ctx.sections[1] = []
    el = ET.fromstring(
        f'<p {_NS_DECL}><said who="#X"><label>FANNIUS.</label> What you say is true.</said></p>'
    )
    ctx.append(el.text)
    for child in el:
        _mod._walk(child, ctx, milestone_units=("section",))
        ctx.append(child.tail)
    assert _mod._clean(ctx.sections[1]) == "FANNIUS. What you say is true."


# --- De Amicitia: per-section-div extraction --------------------------------

def test_section_divs_extracted_one_key_per_div_by_document_order():
    divs = [
        _section_div("1", '<p>First section.</p>'),
        _section_div("2", '<p rend="indent"><milestone unit="chapter" n="1"/>Second, with an ignored chapter milestone.</p>'),
    ]
    # Pad to satisfy the 1..104 completeness assert by monkeypatching range
    out = {}
    for expected_n, div in enumerate(divs, start=1):
        n = int(div.get("n"))
        assert n == expected_n
        ctx = _mod._Ctx()
        ctx.current = n
        ctx.sections[n] = []
        for child in div:
            _mod._walk(child, ctx, milestone_units=())
            ctx.append(child.tail)
        out[n] = _mod._clean(ctx.sections[n])
    assert out == {
        1: "First section.",
        2: "Second, with an ignored chapter milestone.",
    }


def test_section_divs_out_of_order_at_fails_loud():
    divs = [
        _section_div("2", '<p>Wrong order.</p>'),
    ]
    with pytest.raises(AssertionError, match="out of document order"):
        _mod._extract_section_divs(divs)


# --- De Divinatione: Miller-shape per-book milestone walk, + seciton typo --

def test_seciton_typo_treated_as_real_section_boundary():
    book = _book("2", """
        <p><milestone unit="section" n="127"/> One twenty-seven.
        <milestone unit="seciton" n="128"/> One twenty-eight, typo unit name.
        <milestone unit="section" n="129"/> One twenty-nine.</p>
    """)
    ctx = _mod._Ctx()
    _mod._walk(book, ctx, milestone_units=("section",), seciton_alias_n=128)
    assert set(ctx.sections) >= {127, 128, 129}
    assert _mod._clean(ctx.sections[128]) == "One twenty-eight, typo unit name."


def test_seciton_typo_with_wrong_n_is_fatal_even_with_alias_active():
    """MAJOR 2 negative test: seciton_alias_n=128 must not accept a
    'seciton' at any OTHER n -- only the one verified (book, n) pair."""
    book = _book("2", """
        <p><milestone unit="section" n="49"/> Forty-nine.
        <milestone unit="seciton" n="50"/> Misspelled fifty, NOT the verified 128.</p>
    """)
    with pytest.raises(ValueError, match="misspelled milestone unit='seciton' n=50"):
        _mod._walk(book, _mod._Ctx(), milestone_units=("section",), seciton_alias_n=128)


def test_seciton_typo_fatal_when_alias_not_active():
    """MAJOR 2 negative test: a caller that leaves seciton_alias_n unset
    (Book I's real call, or any other walk in this corpus) must fail loud
    on a 'seciton' milestone -- even at n=128 -- rather than silently
    accepting it as an unrecognized-and-ignored unit."""
    book = _book("1", """
        <p><milestone unit="section" n="127"/> One twenty-seven.
        <milestone unit="seciton" n="128"/> Typo in Book I -- not the verified alias.</p>
    """)
    with pytest.raises(ValueError, match="misspelled milestone unit='seciton' n=128"):
        _mod._walk(book, _mod._Ctx(), milestone_units=("section",))


def test_extract_book_milestone_seciton_alias_scoped_to_this_call():
    """End-to-end through _extract_book_milestone: passing seciton_alias_n
    accepts exactly that n; a book called WITHOUT it fails loud on any
    'seciton', matching how _extract_divinatione calls Book I vs Book II."""
    book2 = _book("2", """
        <p><milestone unit="section" n="1"/> One.
        <milestone unit="seciton" n="2"/> Two, typo alias.</p>
    """)
    out = _mod._extract_book_milestone(book2, expected_max=2, allow_missing=set(), seciton_alias_n=2)
    assert sorted(out) == [1, 2]

    book1 = _book("1", """
        <p><milestone unit="section" n="1"/> One.
        <milestone unit="seciton" n="2"/> Two, typo NOT aliased for this call.</p>
    """)
    with pytest.raises(ValueError, match="misspelled milestone unit='seciton'"):
        _mod._extract_book_milestone(book1, expected_max=2, allow_missing=set())


def test_book_milestone_declared_gap_allowed_explicitly():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> One.
        <milestone unit="section" n="2"/> Two.
        <milestone unit="section" n="4"/> Four -- three is a declared gap.</p>
    """)
    out = _mod._extract_book_milestone(book, expected_max=4, allow_missing={3})
    assert sorted(out) == [1, 2, 4]


def test_book_milestone_undeclared_gap_fails_loud():
    book = _book("1", """
        <p><milestone unit="section" n="1"/> One.
        <milestone unit="section" n="4"/> Four -- two AND three missing, undeclared.</p>
    """)
    with pytest.raises(AssertionError, match="expected 1..4"):
        _mod._extract_book_milestone(book, expected_max=4, allow_missing=set())


def test_clean_collapses_whitespace_and_tightens_punctuation():
    assert _mod._clean(["a  b\n\nc", "  ,", " d"]) == "a b c, d"


# --- corpus-level facts on the pinned real XML (skipped if not fetched) ----

_SEN = Path(__file__).resolve().parent.parent.parent / "sources/falconer-sen/phi0474.phi051.perseus-eng1.xml"
_AMIC = Path(__file__).resolve().parent.parent.parent / "sources/falconer-amic/phi0474.phi052.perseus-eng2.xml"
_DIV = Path(__file__).resolve().parent.parent.parent / "sources/falconer-div/phi0474.phi053.perseus-eng1.xml"

_requires_sources = pytest.mark.skipif(
    not (_SEN.exists() and _AMIC.exists() and _DIV.exists()),
    reason="pinned Falconer source XML not present",
)


@_requires_sources
def test_full_extraction_record_counts_and_determinism(tmp_path):
    import json as _json

    _mod._extract_senectute()
    _mod._extract_amicitia()
    _mod._extract_divinatione()

    sen = _json.loads(_mod.OUT_SEN.read_text(encoding="utf-8"))
    amic = _json.loads(_mod.OUT_AMIC.read_text(encoding="utf-8"))
    div = _json.loads(_mod.OUT_DIV.read_text(encoding="utf-8"))

    assert len(sen) == 85
    assert [r["section"] for r in sen] == list(range(1, 86))
    assert len(amic) == 104
    assert [r["section"] for r in amic] == list(range(1, 105))
    # 282 expected (132 + 150); De Divinatione's declared 1:25 gap (see
    # module docstring) makes this 281 -- a real, cross-verified, DECLARED
    # Perseus markup gap, not an extraction defect.
    assert len(div) == 281
    book1 = [r["section"] for r in div if r["book"] == 1]
    book2 = [r["section"] for r in div if r["book"] == 2]
    assert book1 == sorted(set(range(1, 133)) - {25})
    assert book2 == list(range(1, 151))

    for records in (sen, amic, div):
        for r in records:
            assert r["text"].strip(), f"empty record: {r}"

    # determinism: re-run, compare byte-for-byte
    first_sen = _mod.OUT_SEN.read_text(encoding="utf-8")
    first_amic = _mod.OUT_AMIC.read_text(encoding="utf-8")
    first_div = _mod.OUT_DIV.read_text(encoding="utf-8")
    _mod._extract_senectute()
    _mod._extract_amicitia()
    _mod._extract_divinatione()
    assert _mod.OUT_SEN.read_text(encoding="utf-8") == first_sen
    assert _mod.OUT_AMIC.read_text(encoding="utf-8") == first_amic
    assert _mod.OUT_DIV.read_text(encoding="utf-8") == first_div


@_requires_sources
def test_greek_terms_table_no_dead_entries_on_real_source():
    """Every _GREEK_TERMS entry must actually occur in the pinned De
    Divinatione XML's running body text (not only inside dropped notes)."""
    tree = ET.parse(str(_DIV))
    body = tree.getroot().find(".//t:text/t:body", _mod._NS)
    body_raws = []
    for el in body.iter():
        if _mod._local(el.tag) != "foreign" or el.get(_mod._XML_LANG) != "greek":
            continue
        if any(_mod._local(a.tag) == "note" for a in el.iterancestors()):
            continue
        body_raws.append((el.text or "").strip())
    assert len(body_raws) == 9, f"expected 9 body Greek strings in De Divinatione, got {len(body_raws)}"
    assert set(body_raws) == set(_mod._GREEK_TERMS.keys())


@_requires_sources
def test_grc_all_in_notes_guard_passes_on_real_source():
    _mod._assert_grc_all_in_notes(_AMIC)
