from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.preflight import WorkManifest, _validate_manifest_schema


def test_default_and_named_lookup():
    assert scheme_mod.get(None).name == "bekker"
    assert scheme_mod.get("").name == "bekker"
    assert scheme_mod.get("busse").name == "busse"
    assert scheme_mod.get("stephanus").name == "stephanus"


def test_for_manifest_reads_citation_scheme():
    assert scheme_mod.for_manifest({}).name == "bekker"
    assert scheme_mod.for_manifest({"citation": {"scheme": "stephanus"}}).name == "stephanus"

    class M:
        data = {"citation": {"scheme": "busse"}}

    assert scheme_mod.for_manifest(M()).name == "busse"


def test_bekker_capabilities():
    s = scheme_mod.get("bekker")
    assert s.page_div_type == "Bekker-page"
    assert not s.has_sections
    assert s.bekker_native
    assert s.lines_user_facing
    assert s.validation_mode == "range"
    assert s.range_sides == ("a", "b")
    assert s.compose_column("16a") == "16a"


def test_busse_capabilities_synthesize_a_side_column():
    s = scheme_mod.get("busse")
    assert s.page_div_type == "page"
    assert not s.has_sections
    assert not s.bekker_native
    assert s.validation_mode == "observed"
    assert s.range_sides is None
    assert s.compose_column("1") == "1a"


def test_stephanus_capabilities_compose_page_plus_section():
    s = scheme_mod.get("stephanus")
    assert s.page_div_type == "Stephanus-page"
    assert s.section_div_type == "section"
    assert s.has_sections
    assert not s.bekker_native
    assert not s.lines_user_facing          # Plato cited to the section, not line
    assert s.validation_mode == "observed"
    assert s.range_sides is None            # never enumerate a rectangular range
    assert s.section_letters == ("a", "b", "c", "d", "e")
    assert s.compose_column("2", "a") == "2a"
    assert s.compose_column("17", "e") == "17e"


def test_unknown_scheme_raises():
    with pytest.raises(KeyError):
        scheme_mod.get("nonesuch")


def test_book_section_capabilities_compose_dotted_column():
    s = scheme_mod.get("book-section")
    assert s.name == "book-section"
    assert s.has_sections
    assert not s.bekker_native
    assert not s.stub
    assert not s.lines_user_facing            # no user-facing line numbers
    assert s.validation_mode == "observed"     # no [a-e] range logic
    assert s.range_sides is None
    assert s.compose_column("4", "23") == "4.23"   # Marcus Aurelius
    assert s.compose_column("7", "85") == "7.85"   # Diogenes Laertius


def test_book_section_div_types_verified_against_tlg0562001():
    # Wave 1a-D: verified against the real Meditations export
    # (build/export/.../tlg0562001.xml) — div[@type="Book"][@n=1..12] nests
    # div[@type="chapter"][@n], the citation-bearing unit (the "23" in
    # "4.23"). No longer the unverified "book"/"section" placeholders.
    s = scheme_mod.get("book-section")
    assert s.page_div_type == "Book"
    assert s.section_div_type == "chapter"


# --- Blocker 3: citation.div_types override VALUES must be validated (Sol) --


def test_div_types_page_override_rejects_empty_string():
    with pytest.raises(ValueError, match="citation.div_types.page must be a non-empty string"):
        scheme_mod.for_manifest({"citation": {"scheme": "book-section", "div_types": {"page": ""}}})


def test_div_types_section_override_rejects_non_string():
    with pytest.raises(ValueError, match="citation.div_types.section must be a non-empty string"):
        scheme_mod.for_manifest(
            {"citation": {"scheme": "book-section", "div_types": {"section": 5}}}
        )


def test_div_types_page_and_section_both_set_is_valid():
    sch = scheme_mod.for_manifest(
        {"citation": {"scheme": "book-section", "div_types": {"page": "book", "section": "section"}}}
    )
    assert sch.page_div_type == "book"
    assert sch.section_div_type == "section"


def test_book_section_column_and_ref_regex_match_dotted_tokens():
    s = scheme_mod.get("book-section")
    assert s.column_re.match("4.23")
    assert s.column_re.match("7.85")
    assert not s.column_re.match("4.23.5")
    assert not s.column_re.match("4a")      # letter grammar, not dotted
    assert not s.column_re.match("4.")
    assert not s.column_re.match(".23")
    # No user-facing line component: ref grammar is the same dotted shape.
    assert s.ref_re.match("4.23")
    assert not s.ref_re.match("4.23.5")


def test_section_capabilities_flat_bookless_chapter_grammar():
    # Epictetus' Enchiridion: bookless flat scheme, has_sections overridden
    # to True (per-chapter sections.json outline) even though there is no
    # section_div_type — its "sections" are flattened chapter-internal text,
    # not a separate citable column.
    s = scheme_mod.get("section")
    assert s.name == "section"
    assert s.page_div_type == "Chapter"          # capitalized, per the Diogenes export
    assert s.section_div_type is None
    assert s.has_sections                          # explicit override, not derived
    assert not s.numeric_section                   # flat, not book-section's dotted grammar
    assert s.flat_numeric
    assert not s.bekker_native
    assert not s.stub
    assert not s.lines_user_facing
    assert s.validation_mode == "observed"
    assert s.range_sides is None
    assert s.compose_column("5") == "5"
    assert s.compose_column("10") == "10"


def test_section_column_and_ref_regex_match_bare_integers():
    s = scheme_mod.get("section")
    assert s.column_re.match("5")
    assert s.column_re.match("10")
    assert not s.column_re.match("1.5")   # dotted book-section grammar
    assert not s.column_re.match("5a")    # letter grammar
    assert not s.column_re.match("5.")
    assert not s.column_re.match("")
    # No user-facing line component: ref grammar is the same bare-integer shape.
    assert s.ref_re.match("5")
    assert not s.ref_re.match("5.1")


def test_section_column_accepts_the_one_epicurus_compound_token():
    # Epicurus' Vatican Sayings (TLG 0537:014) carries exactly one div whose
    # own @n is a compound "56-57" — one atomic saying spanning two
    # traditional numbers, not a range-gap marker (see
    # manifests/epicurus-vatican-sayings.yaml). Still rejects a malformed
    # token ("5-", "-5", "5-5-5").
    from reader_pipeline.refs import column_key

    s = scheme_mod.get("section")
    assert s.column_re.match("56-57")
    assert column_key("56-57", s) == (56, None)
    assert not s.column_re.match("5-")
    assert not s.column_re.match("-5")
    assert not s.column_re.match("5-5-5")


def test_has_sections_is_derived_by_default_but_overridable():
    # Every existing scheme still derives has_sections from section_div_type
    # (the pre-existing behavior, now via __post_init__ instead of a
    # property) — only `section` passes the override explicitly.
    assert not scheme_mod.get("bekker").has_sections
    assert not scheme_mod.get("busse").has_sections
    assert scheme_mod.get("stephanus").has_sections
    assert scheme_mod.get("book-section").has_sections
    assert scheme_mod.get("section").has_sections


@pytest.mark.parametrize("name", ["ennead"])
def test_stub_schemes_are_registered_but_marked_unusable(name):
    s = scheme_mod.get(name)
    assert s.name == name
    assert s.stub


@pytest.mark.parametrize("name", ["ennead"])
def test_stub_scheme_compose_column_fails_loudly(name):
    with pytest.raises(NotImplementedError):
        scheme_mod.get(name).compose_column("1")


def test_dk_capabilities_fragment_scheme_bookless_lineless_by_default():
    s = scheme_mod.get("dk")
    assert s.name == "dk"
    assert not s.stub
    assert s.page_div_type == "Fragment"
    assert s.section_div_type is None
    assert s.has_sections                       # ordered fragment list is the outline nav
    assert s.fragment_scheme
    assert not s.numeric_section
    assert not s.flat_numeric
    assert not s.bekker_native
    assert not s.lines_user_facing               # lineless by default (Heraclitus)
    assert s.validation_mode == "observed"        # real gaps (B84/B109) — never range-enumerated
    assert s.range_sides is None


def test_dk_compose_column_fails_loudly_not_page_section_shaped():
    # dk's column is (series, number, suffix) — composed in
    # stage1_greek._parse_fragments, never through compose_column's
    # page/section-only signature.
    with pytest.raises(NotImplementedError):
        scheme_mod.get("dk").compose_column("30")


def test_dk_column_and_ref_regex_match_series_number_suffix():
    s = scheme_mod.get("dk")
    for tok in ["B1", "B30", "B84a", "B126b", "A5", "A1a", "B15a"]:
        assert s.column_re.match(tok), tok
        assert s.ref_re.match(tok), tok    # lineless: ref grammar IS the column grammar
    for bad in ["C1", "b1", "B", "B1A", "30", "B1.5"]:
        assert not s.column_re.match(bad), bad


def test_dk_citation_lines_override_enables_verse_ref_grammar():
    sch = scheme_mod.for_manifest({"citation": {"scheme": "dk", "lines": True}})
    assert sch.lines_user_facing
    assert sch.ref_re.match("B8.34")
    assert not sch.column_re.match("B8.34")  # column grammar itself is unchanged
    assert sch.column_re.match("B8")


def test_dk_citation_lines_false_is_a_no_op():
    sch = scheme_mod.for_manifest({"citation": {"scheme": "dk", "lines": False}})
    assert not sch.lines_user_facing


def test_dk_citation_lines_rejects_non_bool():
    with pytest.raises(ValueError, match="true or false"):
        scheme_mod.for_manifest({"citation": {"scheme": "dk", "lines": "yes"}})


def test_citation_lines_rejects_non_dk_scheme():
    with pytest.raises(ValueError, match="only meaningful for scheme 'dk'"):
        scheme_mod.for_manifest({"citation": {"scheme": "bekker", "lines": True}})


# --- citation.no_series (Pythagoras, DK 14 — no series letter at all) -------


def test_dk_citation_no_series_override_swaps_column_grammar():
    sch = scheme_mod.for_manifest({"citation": {"scheme": "dk", "no_series": True}})
    assert sch.column_re.match("7")
    assert sch.column_re.match("6a")
    assert not sch.column_re.match("B7")   # series-letter form now REJECTED
    assert not sch.column_re.match("A7")
    assert sch.ref_re.match("7")           # lineless: ref grammar IS the column grammar


def test_dk_citation_no_series_false_is_a_no_op():
    sch = scheme_mod.for_manifest({"citation": {"scheme": "dk", "no_series": False}})
    assert sch.column_re.match("B30")
    assert not sch.column_re.match("30")


def test_dk_citation_no_series_rejects_non_bool():
    with pytest.raises(ValueError, match="true or false"):
        scheme_mod.for_manifest({"citation": {"scheme": "dk", "no_series": "yes"}})


def test_citation_no_series_rejects_non_dk_scheme():
    with pytest.raises(ValueError, match="only meaningful for scheme 'dk'"):
        scheme_mod.for_manifest({"citation": {"scheme": "bekker", "no_series": True}})


def test_dk_citation_no_series_with_lines_not_implemented():
    with pytest.raises(ValueError, match="not implemented"):
        scheme_mod.for_manifest(
            {"citation": {"scheme": "dk", "no_series": True, "lines": True}}
        )


def test_dk_no_series_column_re_capture_shape_note():
    # Documents (rather than merely asserting parity of) a deliberate
    # Python/TS asymmetry -- see `_DK_NO_SERIES_COLUMN_RE`'s own comment.
    # This side's regex keeps 3 capture groups (an always-empty leading
    # placeholder + number + suffix) to match `_DK_COLUMN_RE`'s
    # (series, number, suffix) shape, since refs.py/stage1_greek consumers
    # unpack that 3-tuple unconditionally of no_series. citation.ts's
    # matching `DK_NO_SERIES_COLUMN_RE` is only 2 groups (no placeholder)
    # -- its sole consumer never unpacks a 3-tuple. The "case-parity
    # contract" the two sides' comments cross-reference is about
    # canonicalization strictness only, never capture-group count -- if
    # this count ever changes on either side, update BOTH comments, not
    # just the regex.
    sch = scheme_mod.for_manifest({"citation": {"scheme": "dk", "no_series": True}})
    m = sch.column_re.match("7a")
    assert m is not None
    assert m.groups() == ("", "7", "a")


# --- verse-line (Lucretius' DRN -- continuous verse with a book axis;
# design memo docs/wave2-latin-design.md §3.1-3.4) -------------------------

VERSE_LINE = scheme_mod.get("verse-line")


def test_verse_line_capabilities_compose_dotted_column():
    s = VERSE_LINE
    assert s.name == "verse-line"
    assert not s.stub
    assert not s.has_sections            # a per-line outline nav would be unusable
    assert not s.bekker_native
    assert not s.lines_user_facing       # the line IS the column, no sub-line axis
    assert not s.numeric_section         # richer grammar than book-section's plain int
    assert not s.fragment_scheme
    assert not s.flat_numeric
    assert s.validation_mode == "observed"   # non-monotonic order (transpositions, §3.3)
    assert s.range_sides is None
    assert s.column_separator == "."
    assert s.compose_column("1", "101") == "1.101"
    assert s.compose_column("3", "47a") == "3.47a"
    assert s.compose_column("1", "1094-1101") == "1.1094-1101"  # a declared lacuna token


def test_verse_line_column_and_ref_regex_match_dotted_tokens():
    s = VERSE_LINE
    for tok in ["1.101", "3.47a", "1.1094-1101", "12.1", "1.99", "1.100"]:
        assert s.column_re.match(tok), tok
        assert s.ref_re.match(tok), tok   # lineless: ref grammar IS the column grammar


@pytest.mark.parametrize("value", [
    "47ab",     # two suffix letters
    "a47",      # letter before number (and not dotted at all)
    "4.7.1",    # extra dotted component
    "",
    "4.",
    ".23",
    "4a",       # not dotted at all -- bekker-style letter grammar
    "1.47-",    # dangling range dash
    "1.-47",
])
def test_verse_line_rejects_malformed_tokens(value):
    assert not VERSE_LINE.column_re.match(value)


def test_verse_line_leading_zero_is_accepted_and_preserved_literally_not_stripped():
    # DECISION (design memo §3.1: "no leading-zero normalization; PHI has
    # none"): mirrors dk's identical grammar note (`_DK_COLUMN_RE`'s own
    # comment, "no leading-zero normalization ... TLG has none") -- there,
    # `[0-9]+` is permissive (a leading zero is never defensively stripped)
    # because real TLG/PHI data is never observed to carry one, not because
    # a stray one must be rejected. The same reading applies here: the
    # regex does not special-case a leading zero, so a "047"-shaped token
    # structurally matches and its digits are preserved AS-IS in the
    # captured group (never renormalized to "47") -- see citation.test.ts's
    # matching case for the TS-side parity assertion.
    m = VERSE_LINE.column_re.match("1.047")
    assert m is not None
    assert m.group(2) == "047"                       # literal digits preserved, not stripped
    assert scheme_mod.verse_line_order_key("047") == (47, "")  # but sorts as int 47


def test_verse_line_order_key_sorts_numeric_with_suffix_after_bare():
    # 47 < 47a < 48; 99 < 100 (numeric, never lexicographic) -- reuses dk's
    # proven '' < 'a' < 'b' ordering (design memo §3.1).
    linerefs = ["100", "99", "48", "47a", "47"]
    assert sorted(linerefs, key=scheme_mod.verse_line_order_key) == [
        "47", "47a", "48", "99", "100",
    ]


def test_verse_line_order_key_ignores_book_context_entirely():
    # The key is derived from a lineref ALONE -- a caller applies it per-book
    # (the design memo's §3.3 citation-order sort is explicitly within a
    # book), so the same lineref sorts identically regardless of which book
    # it came from; there is no book component here to ignore.
    assert scheme_mod.verse_line_order_key("47a") == scheme_mod.verse_line_order_key("47a")
    assert scheme_mod.verse_line_order_key("47") < scheme_mod.verse_line_order_key("47a")


def test_verse_line_order_key_rejects_a_range_token():
    with pytest.raises(ValueError, match="not a verse-line token"):
        scheme_mod.verse_line_order_key("1094-1101")


def test_verse_line_kind_classifies_line_vs_range():
    assert scheme_mod.verse_line_kind("101") == "line"
    assert scheme_mod.verse_line_kind("47a") == "line"
    assert scheme_mod.verse_line_kind("1094-1101") == "range"
    assert scheme_mod.verse_line_kind("1094a-1101b") == "range"


def test_verse_line_kind_rejects_malformed_lineref():
    with pytest.raises(ValueError, match="not a verse-line lineref"):
        scheme_mod.verse_line_kind("47ab")


# TS/Python grammar parity: the SAME case list as citation.test.ts's
# "grammar parity with scheme.py" block for verse-line.
@pytest.mark.parametrize("tok", ["1.101", "3.47a", "1.1094-1101", "12.1", "1.1094a-1101b"])
def test_verse_line_grammar_parity_with_citation_ts_valid(tok):
    assert VERSE_LINE.column_re.match(tok), tok


@pytest.mark.parametrize("tok", ["47ab", "a47", "4.7.1", "", "4a", "1.47-", "1.-47", "1."])
def test_verse_line_grammar_parity_with_citation_ts_malformed(tok):
    assert not VERSE_LINE.column_re.match(tok), tok


# --- letter (Seneca's Epistulae Morales, Wave 2 Batch 3 -- design memo
# docs/wave2-seneca-design.md §A): a book-section-shaped dotted scheme,
# grammar reused wholesale (no new regex) -- letter = page axis, section =
# column, "47.3". --------------------------------------------------------

LETTER = scheme_mod.get("letter")


def test_letter_capabilities_compose_dotted_column():
    s = LETTER
    assert s.name == "letter"
    assert not s.stub
    assert s.has_sections                # mirrors book-section, unlike verse-line
    assert not s.bekker_native
    assert not s.lines_user_facing        # no user-facing line component
    assert s.numeric_section              # open-ended integer section axis
    assert s.letter_scheme
    assert not s.verse_line_scheme
    assert not s.fragment_scheme
    assert not s.flat_numeric
    assert s.validation_mode == "observed"
    assert s.range_sides is None
    assert s.column_separator == "."
    assert s.compose_column("47", "3") == "47.3"
    assert s.compose_column("124", "1") == "124.1"


def test_letter_div_types_verified_against_phi1017015():
    # Verified against the untracked PHI export (design memo §A rationale):
    # div[@type="letter"][@n=1..124|t|fr] nests div[@type="section"][@n].
    s = LETTER
    assert s.page_div_type == "letter"
    assert s.section_div_type == "section"


def test_letter_column_and_ref_regex_match_dotted_tokens():
    s = LETTER
    assert s.column_re.match("47.3")
    assert s.column_re.match("124.1")
    assert not s.column_re.match("47.3.5")
    assert not s.column_re.match("47a")     # letter grammar, not dotted -- no such axis here
    assert not s.column_re.match("47.")
    assert not s.column_re.match(".3")
    assert not s.column_re.match("3")       # bare column -- no letter-less form (design memo §A.3)
    # No user-facing line component: ref grammar is the same dotted shape.
    assert s.ref_re.match("47.3")
    assert not s.ref_re.match("47.3.5")


def test_letter_has_sections_derives_true_like_book_section():
    assert scheme_mod.get("letter").has_sections


# TS/Python grammar parity: the SAME case list as citation.test.ts's
# "grammar parity with scheme.py" block for letter.
@pytest.mark.parametrize("tok", ["47.3", "124.1", "1.1", "7.85"])
def test_letter_grammar_parity_with_citation_ts_valid(tok):
    assert LETTER.column_re.match(tok), tok


@pytest.mark.parametrize("tok", ["47.3.5", "47.", ".3", "47a", "3", "", "a.3"])
def test_letter_grammar_parity_with_citation_ts_malformed(tok):
    assert not LETTER.column_re.match(tok), tok


def _flat_manifest_data(model: str = "archive", books: list | None = None) -> dict:
    return {
        "work": {"id": "ENCH", "title": "Enchiridion", "author": "epictetus",
                 "tlg_author": "0557", "tlg_work": "002",
                 "greek_edition": "Fixture"},
        "citation": {"scheme": "section"},
        "english": {"primary": {"id": "fx", "name": "Fixture", "model": model,
                                "file": "fx.md"}},
        "sources": {"tlg_dir_env": "TLG_DIR", "tlg_dir_default": "build"},
        "section_spine": {"count": 3, "sha256": "0" * 64},
        "books": books if books is not None else [{"n": 1, "start": "1", "end": "3"}],
    }


def _flat_preflight_problems(data: dict) -> list[str]:
    manifest = WorkManifest(work_id="ENCH", path=Path("ENCH.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    return [m for _work, _file, m in problems]


def test_preflight_rejects_flat_manifest_with_model_none():
    # CONSTRAIN LOUDLY (Sol re-review round 2): the all-stages pipeline
    # deletes the english scratch for a has_sections work whose primary.model
    # is not perseus_stephanus, and stage6/stage7 load english_chunks.json
    # unconditionally — a pre-existing platform behavior. A flat work with
    # model "none" therefore cannot complete `reader_pipeline all`; preflight
    # must say so instead of letting it break silently at stage6.
    messages = _flat_preflight_problems(_flat_manifest_data(model="none"))
    assert any("unsupported" in m and "none" in m for m in messages), messages


def test_preflight_rejects_flat_manifest_with_multiple_books():
    # stage1 assigns every flat column to the single book 1 — a multi-book
    # flat manifest would silently collapse all its books into one. Rejected
    # at preflight instead.
    messages = _flat_preflight_problems(_flat_manifest_data(books=[
        {"n": 1, "start": "1", "end": "3"},
        {"n": 2, "start": "4", "end": "6"},
    ]))
    assert any("exactly one book" in m for m in messages), messages


def test_preflight_rejects_flat_manifest_with_zero_books():
    messages = _flat_preflight_problems(_flat_manifest_data(books=[]))
    assert any("exactly one book" in m for m in messages), messages


def test_preflight_rejects_flat_manifest_with_wrong_book_number():
    # stage1 hardcodes flat segments to book 1; a manifest declaring n: 2
    # would silently disagree with the emitted book-01 files.
    messages = _flat_preflight_problems(_flat_manifest_data(books=[
        {"n": 2, "start": "1", "end": "3"},
    ]))
    assert any("must be n: 1" in m for m in messages), messages


def test_preflight_flat_manifest_with_non_dict_book_entry_does_not_crash():
    # a malformed entry like books: [1] must get the shared validator's
    # "must be an object" diagnostic, not an AttributeError from the n:1 guard
    messages = _flat_preflight_problems(_flat_manifest_data(books=[1]))
    assert messages, messages
    assert not any("must be n: 1" in m for m in messages), messages


def test_preflight_accepts_single_book_flat_manifest_with_real_model():
    assert _flat_preflight_problems(_flat_manifest_data()) == []


def test_preflight_rejects_stub_scheme():
    # `ennead` — verse-line was un-stubbed (Wave 2 Batch 2's scheme-grammar
    # task); this now covers the OTHER still-stub schemes' preflight guard,
    # unchanged by that un-stubbing (see test_preflight_rejects_stub_letter_scheme
    # below for the second one).
    data = {"work": {"id": "X"}, "citation": {"scheme": "ennead"}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("ennead" in m and "not implemented" in m for m in messages)


def test_letter_scheme_is_no_longer_stub_rejected_by_preflight():
    # `letter` was un-stubbed (Wave 2 Batch 3's Seneca scheme-grammar task,
    # docs/wave2-seneca-design.md §A) -- the preflight stub pre-check
    # (line ~156) must fall through to the ordinary schema checks instead of
    # short-circuiting with "not implemented", the same transition
    # verse-line made in an earlier wave. A minimal manifest still collects
    # OTHER schema problems (missing work/english/sources fields) -- this
    # only asserts the stub message specifically is gone.
    data = {"work": {"id": "X"}, "citation": {"scheme": "letter"}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert not any("not implemented" in m for m in messages), messages
    assert messages  # still a schema-incomplete manifest, just not stub-rejected


def test_preflight_rejects_unknown_scheme_cleanly():
    data = {"work": {"id": "X"}, "citation": {"scheme": "nonesuch"}}
    manifest = WorkManifest(work_id="X", path=Path("X.yaml"), data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    messages = [m for _work, _file, m in problems]
    assert any("nonesuch" in m and "not a recognized scheme" in m for m in messages)
