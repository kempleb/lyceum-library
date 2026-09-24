from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import dk_lang
from reader_pipeline import scheme as scheme_mod
from reader_pipeline import stage1_greek
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_greek import (
    _check_sourcedesc, _dk_normalize_quote_marks, _dk_role_blocks, _line_text,
    _parse_fragments, parse_spine,
)

SCHEME = scheme_mod.get("dk")

TEI_NS = "http://www.tei-c.org/ns/1.0"


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


def _manifest(citation_extra: dict | None = None, work_id: str = "FIXWORK") -> Manifest:
    citation = {"scheme": "dk", "series": "B"}
    citation.update(citation_extra or {})
    return Manifest(
        {
            "work": {"id": work_id, "tlg_author": "9999", "tlg_work": "001",
                     "greek_edition": "Fixture"},
            "citation": citation,
            "books": [{"n": 1, "start": "B1", "end": "B2"}],
        },
        ROOT / "manifests" / "fake.yaml",
    )


# A fake sources/<work_id>/dk-context-lang.json is never written for these
# fixtures (SOURCES_DIR / work_id won't exist), so _dk_load_context_lang
# returns {} — every non-Greek run in these fixtures must therefore be pure
# Greek, or the test explicitly supplies a decisions dict by calling
# apply_context_language paths indirectly. Kept deliberately simple: no
# non-Greek content in the fixture Greek below (dk_lang.py has its own
# dedicated test suite for the language-decision mechanism).


# --- role-block walking: the letter-spacing / small / italic distinction ---

def test_letter_spacing_is_role_text_everything_else_is_context():
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>ΞΞΞ. <hi rend="letter-spacing">λόγος ἐστίν</hi>. ΨΨΨ.</p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(False, "ΞΞΞ. "), (True, "λόγος ἐστίν"), (False, ". ΨΨΨ.")]


def test_nested_italic_inside_letter_spacing_stays_role_text():
    # Mirrors Heraclitus B4's real shape: a Latin quotation typeset in
    # italics WITHIN the letter-spaced (role='text') span must not flip
    # back to context just because italic is context-flavored elsewhere.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>ΞΞΞ <hi rend="letter-spacing">ante <hi rend="italic">verba</hi> post</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert all(is_text for is_text, _ in runs[1:])  # everything after the intro is role='text'


def test_context_nested_inside_letter_spacing_via_interleaving_still_flips_back():
    # small/italic nested WITHIN a letter-spacing span never resets it to
    # context (see the module doc's B4 rationale) -- but a SIBLING small
    # block after the letter-spacing span closes correctly reverts.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p><hi rend="letter-spacing">ΑΑΑ</hi> ΒΒΒ <hi rend="small">ΓΓΓ</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(True, "ΑΑΑ"), (False, " ΒΒΒ "), (False, "ΓΓΓ")]


def test_self_closing_letter_spacing_milestone_applies_to_its_own_tail():
    # The verified Diogenes export quirk (Heraclitus B32/B41/B43/B84a): an
    # EMPTY <hi rend="letter-spacing"/> milestone's effect applies to the
    # rest of the paragraph, not to a (nonexistent) subtree.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>ΞΞΞ <hi rend="letter-spacing"/>λόγος ἐστίν.</p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(False, "ΞΞΞ "), (True, "λόγος ἐστίν.")]


def test_milestone_with_later_scoped_sibling_in_same_parent_is_a_noop():
    # Anaxagoras A92 (the only instance of this shape found in a full-corpus
    # sweep -- Heraclitus B32/B41/B43/B84a and testimonium A19, Anaxagoras
    # fragments B15/B16, and every verse-fragment milestone in Empedocles/
    # Parmenides/Xenophanes are each the LAST letter-spacing-family <hi>
    # within their own immediate parent, so "extends to end of node" is
    # exactly the real quotation there): a self-closing milestone NESTED
    # inside a wrapping <hi rend="small"> whose own remaining content later
    # holds a SECOND, genuinely-scoped <hi rend="letter-spacing"> sibling is
    # not a real quotation-opening milestone -- treating it as one would
    # swallow Theophrastus' own third-person narrative (everything between
    # the milestone and the real, short marked phrase) as if it were
    # Anaxagoras' own words. Must-fail-first: before the fix, this asserted
    # `[(False, "NNN "), (True, "AAA BBB "), (True, "GGG"), (True, " DDD")]`
    # -- the milestone's tail ran unbounded through the scoped span and out
    # the other side, since the scoped call's own state return value is
    # discarded but the ENCLOSING frame's `state` had already flipped True.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p><hi rend="small">NNN <hi rend="letter-spacing"/>AAA BBB <hi rend="letter-spacing">GGG</hi> DDD</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert runs == [
        (False, "NNN "), (False, "AAA BBB "), (True, "GGG"), (False, " DDD"),
    ]


def test_milestone_with_no_later_sibling_still_extends_to_end_of_its_parent():
    # Same shape as the previous test (milestone nested inside a wrapping
    # <hi>), but with NO later letter-spacing sibling -- mirrors the real,
    # verified Anaxagoras fragments B15/B16 shape (a milestone that is the
    # ONLY letter-spacing element in its immediate parent, and correctly
    # marks its whole remaining tail). Confirms the A92 fix is scoped to
    # "a later sibling exists," not "any nested milestone."
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p><hi rend="small"><hi rend="letter-spacing"/>AAA BBB CCC</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, _end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(True, "AAA BBB CCC")]


# --- `_dk_role_blocks`' returned `end_state` (Sol review blocker, div_concat
# ambient threading): a caller threading ambient state across multiple calls
# must use the walker's own returned end state, never infer it from the last
# EMITTED run's state -- the two disagree in exactly the two shapes below. ---

def test_role_blocks_end_state_a_part_ending_inside_scoped_span_with_no_tail():
    # A part/line ending INSIDE a SCOPED (non-milestone) letter-spacing span
    # with no tail after it: the last emitted run is (True, "λόγος"), but a
    # scoped <hi>'s state change never escapes its own subtree -- the walk's
    # real ending ambient state is False (unchanged), not True. Before the
    # fix, a caller inferring ambient from `runs[-1][0]` would wrongly carry
    # role='text' into whatever comes next.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>ΞΞΞ <hi rend="letter-spacing">λόγος</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(False, "ΞΞΞ "), (True, "λόγος")]
    assert end_state is False  # scoped span's True never escapes its subtree
    assert runs[-1][0] is True  # ... which is exactly what the buggy inference read


def test_role_blocks_end_state_an_empty_terminal_milestone_with_no_following_text():
    # An empty self-closing milestone as the LAST child, with no tail at all
    # (nothing follows it in the document): `emit` never fires for it (no
    # text to emit), so `runs` gains no new entry -- but the milestone still
    # flips the walk's own `state` for whatever the CALLER threads next.
    # Before the fix, a caller inferring ambient from `runs[-1][0]` would
    # miss this entirely (either using a stale prior run's state, or IndexError
    # on an empty `runs` list) and wrongly keep role='context'.
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>ΞΞΞ <hi rend="letter-spacing"/></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    runs, end_state = _dk_role_blocks(p, "fixture")
    assert runs == [(False, "ΞΞΞ ")]
    assert end_state is True  # the milestone fired; nothing followed it to emit


def test_unrecognized_rend_value_is_a_hard_error():
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p><hi rend="bold">λόγος</hi></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    with pytest.raises(ValueError, match="unrecognized"):
        _dk_role_blocks(p, "fixture")


def test_verse_l_element_is_not_yet_implemented():
    xml = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p><l n="1">λόγος</l></p>
</div>
</body></text></TEI>"""
    p = _tree(xml).find(f".//{{{TEI_NS}}}p")
    with pytest.raises(NotImplementedError, match="verse line"):
        _dk_role_blocks(p, "fixture")


# --- _parse_fragments: div walking, column composition, gates --------------

def _fragmenta_xml(*divs: str) -> str:
    body = "\n".join(divs)
    return f"""<TEI xmlns="{TEI_NS}"><text><body>{body}</body></text></TEI>"""


def test_title_div_is_stripped_never_a_column():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="tit,1-99"><p><label type="head">ΤΙΤΛΟΣ</label></p></div>',
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    flat, headings = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    cols = {e["column"] for e in flat}
    assert cols == {"B1"}


def test_column_composed_from_series_plus_bare_div_n():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="30"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="84a"><p><hi rend="letter-spacing">ἐστίν</hi></p></div>',
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert {e["column"] for e in flat} == {"B30", "B84a"}


def test_lettered_dk_columns_coexist_with_their_own_base_number():
    # Anaxagoras testimonia's real shape: A4/A4a and A20/A20a are each
    # INDEPENDENTLY-EXISTING divs (not one div holding both) -- unlike
    # test_column_composed_from_series_plus_bare_div_n's B84a above (which
    # has no corresponding bare "B84" div at all), a lettered div's presence
    # must compose as its own distinct column alongside its base number's
    # SEPARATE div, never merging or colliding with it.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="4"><p><hi rend="letter-spacing">ΑΑΑ</hi></p></div>',
        '<div type="Fragment" n="4a"><p><hi rend="letter-spacing">ΒΒΒ</hi></p></div>',
        '<div type="Fragment" n="20"><p><hi rend="letter-spacing">ΓΓΓ</hi></p></div>',
        '<div type="Fragment" n="20a"><p><hi rend="letter-spacing">ΔΔΔ</hi></p></div>',
    )
    m = _manifest({"series": "A"})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert {e["column"] for e in flat} == {"A4", "A4a", "A20", "A20a"}
    assert [e["text"] for e in flat if e["column"] == "A4"] == ["ΑΑΑ"]
    assert [e["text"] for e in flat if e["column"] == "A4a"] == ["ΒΒΒ"]


def test_lettered_dk_columns_three_way_split_coexist_with_base_number():
    # Anaxagoras fragments' real shape: B21, B21a, B21b are three genuinely
    # distinct divs (three separate DK sub-entries sharing one base number),
    # not a base plus a single lettered variant.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="21"><p><hi rend="letter-spacing">ΑΑΑ</hi></p></div>',
        '<div type="Fragment" n="21a"><p><hi rend="letter-spacing">ΒΒΒ</hi></p></div>',
        '<div type="Fragment" n="21b"><p><hi rend="letter-spacing">ΓΓΓ</hi></p></div>',
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert {e["column"] for e in flat} == {"B21", "B21a", "B21b"}
    assert [e["text"] for e in flat if e["column"] == "B21"] == ["ΑΑΑ"]
    assert [e["text"] for e in flat if e["column"] == "B21a"] == ["ΒΒΒ"]
    assert [e["text"] for e in flat if e["column"] == "B21b"] == ["ΓΓΓ"]


def test_series_a_for_testimonia():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"series": "A"})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert flat[0]["column"] == "A1"


def test_missing_series_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest()
    del m.data["citation"]["series"]
    with pytest.raises(ValueError, match="citation.series"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_no_series_with_explicit_empty_string_series_is_a_hard_error():
    # citation.series: "" is NOT "series omitted" -- only a genuinely absent
    # (None) series satisfies citation.no_series's contract. Mirrors
    # preflight.py's own pre-check of the same hole.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"no_series": True, "series": ""})
    with pytest.raises(ValueError, match="citation.series must be omitted"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_unrecognized_div_n_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="7,8"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    with pytest.raises(ValueError, match="unrecognized dk fragment"):
        _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")


def test_div_map_merges_leading_context_into_target_column():
    # Mirrors Parmenides' n="7,8" -> B7 leading merge: the alternate-source
    # div appears BEFORE its target's own div in the export, and its content
    # renders as a labeled context block ahead of B7's own text.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="7,8"><p>ΑΑΑ ΒΒΒ</p></div>',
        '<div type="Fragment" n="7"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B7", "role": "context", "position": "leading", "label": "Alt"},
    ]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    cols = {e["column"] for e in flat}
    assert cols == {"B7"}
    assert flat[0]["role"] == "context"
    assert flat[0]["text"] == "[Alt] ΑΑΑ ΒΒΒ"
    assert flat[1]["role"] == "text"
    assert flat[1]["text"] == "λόγος"


def test_div_map_merges_trailing_context_into_target_column():
    # Mirrors Parmenides' n="8schol" -> B8 trailing merge: the scholion div
    # appears AFTER its target's own div and renders after B8's own text.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="8"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="8schol"><p>ΓΓΓ ΔΔΔ</p></div>',
    )
    m = _manifest({"div_map": [
        {"n": "8schol", "target": "B8", "role": "context", "position": "trailing", "label": "Schol"},
    ]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert flat[0]["role"] == "text"
    assert flat[0]["text"] == "λόγος"
    assert flat[1]["role"] == "context"
    assert flat[1]["text"] == "[Schol] ΓΓΓ ΔΔΔ"


def test_div_map_entry_requires_context_role():
    xml = _fragmenta_xml('<div type="Fragment" n="7,8"><p>ΑΑΑ</p></div>')
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B7", "role": "text", "position": "leading", "label": "Alt"},
    ]})
    with pytest.raises(ValueError, match="role="):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_map_entry_requires_position():
    xml = _fragmenta_xml('<div type="Fragment" n="7,8"><p>ΑΑΑ</p></div>')
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B7", "role": "context", "label": "Alt"},
    ]})
    with pytest.raises(ValueError, match="position"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_map_stale_declaration_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="7"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B7", "role": "context", "position": "leading", "label": "Alt"},
    ]})
    with pytest.raises(ValueError, match="no such div was found"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_map_duplicate_source_n_is_a_hard_error():
    # Two declarations for the SAME source div @n (a manifest-authoring
    # copy-paste slip) must never silently overwrite -- the first entry's
    # target/position/label would vanish with no error otherwise (Sol
    # review blocker 3).
    xml = _fragmenta_xml(
        '<div type="Fragment" n="7,8"><p>ΑΑΑ</p></div>',
        '<div type="Fragment" n="7"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="9"><p><hi rend="letter-spacing">ἐστίν</hi></p></div>',
    )
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B7", "role": "context", "position": "leading", "label": "Alt"},
        {"n": "7,8", "target": "B9", "role": "context", "position": "trailing", "label": "Alt2"},
    ]})
    with pytest.raises(ValueError, match="more than once"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_map_unconsumed_target_is_a_hard_error():
    # Declares a merge onto B9, but no div n="9" exists in this export --
    # the merge's text would otherwise silently vanish.
    xml = _fragmenta_xml('<div type="Fragment" n="7,8"><p>ΑΑΑ</p></div>')
    m = _manifest({"div_map": [
        {"n": "7,8", "target": "B9", "role": "context", "position": "leading", "label": "Alt"},
    ]})
    with pytest.raises(ValueError, match="ever processed as an ordinary fragment"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- div_concat (Xenophanes A28: no separate plain "28" div at all) --------

def test_div_concat_composes_target_from_ordered_parts_no_own_div():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="27"><p>ζζζ</p></div>',
        '<div type="Fragment" n="28,977a"><p>ααα</p></div>',
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
        '<div type="Fragment" n="29"><p>υυυ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
        "unmarked_columns": ["A27", "A28", "A29"],
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    cols = [e["column"] for e in flat]
    # A28 lands between A27 and A29 -- the document position of its FIRST
    # declared part, not appended at the end.
    assert cols == ["A27", "A28", "A28", "A29"]
    assert [e["text"] for e in flat if e["column"] == "A28"] == ["ααα", "βββ"]


def test_div_concat_order_matches_document_order_is_fine():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="28,977a"><p>ααα</p></div>',
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
        "unmarked_columns": ["A28"],
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert [e["text"] for e in flat] == ["ααα", "βββ"]


def test_div_concat_order_mismatched_against_document_order_is_a_hard_error():
    # Sol review blocker S2: the declared order is a PINNED EXPECTATION, not
    # a reordering device -- a re-export that shuffled the parts (the
    # document here has b before a, but the manifest still declares a/b)
    # must fail loudly rather than silently composing the column in the
    # stale declared order.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
        '<div type="Fragment" n="28,977a"><p>ααα</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
        "unmarked_columns": ["A28"],
    })
    with pytest.raises(ValueError, match="document order"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_requires_at_least_two_parts():
    m = _manifest({"series": "A", "div_concat": {"A28": ["28,977a"]}})
    xml = _fragmenta_xml('<div type="Fragment" n="28,977a"><p>AAA</p></div>')
    with pytest.raises(ValueError, match="at least two"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_missing_part_is_a_hard_error():
    xml = _fragmenta_xml('<div type="Fragment" n="28,977a"><p>AAA</p></div>')
    m = _manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
    })
    with pytest.raises(ValueError, match="no such div was found"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_source_collides_with_div_map_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="28,977a"><p>AAA</p></div>',
        '<div type="Fragment" n="28,977b"><p>BBB</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_map": [{"n": "28,977a", "target": "A9", "role": "context",
                      "position": "leading", "label": "X"}],
        "div_concat": {"A28": ["28,977a", "28,977b"]},
    })
    with pytest.raises(ValueError, match="at most one merge mechanism"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_duplicate_source_across_targets_is_a_hard_error():
    m = _manifest({
        "series": "A",
        "div_concat": {
            "A28": ["28,977a", "28,977b"],
            "A30": ["28,977a", "30,x"],
        },
    })
    xml = _fragmenta_xml('<div type="Fragment" n="28,977a"><p>AAA</p></div>')
    with pytest.raises(ValueError, match="more than once"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_and_verse_work_is_not_implemented():
    m, sch = _verse_manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
    })
    xml = _fragmenta_xml('<div type="Fragment" n="1"><l n="1">ααα</l></div>')
    with pytest.raises(NotImplementedError, match="prose-only"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_div_concat_output_column_collides_with_a_plain_div_is_a_hard_error():
    # Sol review blocker S1a: `seen_ns` tracks SOURCE div @n's, not output
    # COLUMN names -- a re-export that adds a genuine plain div n="28"
    # alongside the "28,977a"/"28,977b" parts that already compose column
    # "A28" must be FATAL, not a silently accepted second "A28" entry (the
    # plain div's @n and the concat parts' @n's are all distinct strings, so
    # nothing about `seen_ns` alone would ever catch this).
    xml = _fragmenta_xml(
        '<div type="Fragment" n="28,977a"><p>ααα</p></div>',
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
        '<div type="Fragment" n="28"><p>γγγ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A28": ["28,977a", "28,977b"]},
        "unmarked_columns": ["A28"],
    })
    with pytest.raises(ValueError, match="already established"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- div_concat: a plain base div AS the target's own first member ---------
# (Melissus A5, Wave 1b/1c: unlike Xenophanes A28's original div_concat case
# -- no separate plain "5" div at all -- Melissus' div "5" DOES exist, but
# carries only the citation header, no fragment content of its own; declared
# as div_concat's own first ordered member (rather than left to collide as
# an independent plain div, per the previous test) so it folds into A5 in
# document order alongside its seven "5,97Xa/b" continuation parts.)


def test_div_concat_first_member_is_a_plain_base_div_with_no_content_of_its_own():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="4"><p>δδδ</p></div>',
        '<div type="Fragment" n="5"><p>ηδη</p></div>',
        '<div type="Fragment" n="5,974a"><p>ααα</p></div>',
        '<div type="Fragment" n="5,974b"><p>βββ</p></div>',
        '<div type="Fragment" n="6"><p>ζζζ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A5": ["5", "5,974a", "5,974b"]},
        "unmarked_columns": ["A4", "A5", "A6"],
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    cols = [e["column"] for e in flat]
    # A5 lands between A4 and A6 -- the document position of its first
    # declared part ("5" itself), not appended at the end.
    assert cols == ["A4", "A5", "A5", "A5", "A6"]
    assert [e["text"] for e in flat if e["column"] == "A5"] == [
        "ηδη", "ααα", "βββ",
    ]


def test_div_concat_plain_base_div_first_member_missing_is_a_hard_error():
    # The bare "5" div (the citation-header-only base div) was never
    # exported at all -- e.g. a re-export folded its heading text into the
    # first continuation part. The Pass-1.5 pre-scan (missing_concat_parts)
    # must catch this exactly like any other missing part, not silently
    # compose A5 from just the two continuation divs.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="5,974a"><p>ααα</p></div>',
        '<div type="Fragment" n="5,974b"><p>βββ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A5": ["5", "5,974a", "5,974b"]},
    })
    with pytest.raises(ValueError, match="no such div was found"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_plain_base_div_first_member_renamed_is_a_hard_error():
    # A re-export renumbered the bare base div (e.g. "5" -> "5,973") without
    # updating the manifest -- the declared "5" no longer matches any div in
    # the export (a distinct div "5,973" exists instead, but under a name
    # the manifest never declared), so this must fail exactly like the
    # never-existed case above, not silently drop the renamed div's content.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="5,973"><p>ARISTOT. q. f. de Melisso...</p></div>',
        '<div type="Fragment" n="5,974a"><p>ααα</p></div>',
        '<div type="Fragment" n="5,974b"><p>βββ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_concat": {"A5": ["5", "5,974a", "5,974b"]},
    })
    with pytest.raises(ValueError, match="no such div was found"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- compound_n_map (Empedocles "77,78"/"148,149,150": ONE div with a DK
# joint-numbered heading, no mechanical per-number split) -----------------

def test_compound_n_map_files_div_content_under_the_target_plain_column():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="76"><p>ζζζ</p></div>',
        '<div type="Fragment" n="77,78"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="79"><p>υυυ</p></div>',
    )
    m = _manifest({
        "compound_n_map": {"77,78": "77"},
        "unmarked_columns": ["B76", "B79"],
        "expected_gaps": ["B78"],
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    cols = [e["column"] for e in flat]
    assert cols == ["B76", "B77", "B79"]
    assert [e["text"] for e in flat if e["column"] == "B77"] == ["λόγος"]


def test_compound_n_map_target_must_match_plain_column_grammar():
    m = _manifest({"compound_n_map": {"77,78": "not-a-number"}})
    xml = _fragmenta_xml('<div type="Fragment" n="77,78"><p>ααα</p></div>')
    with pytest.raises(ValueError, match="plain number"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_compound_n_map_stale_declaration_is_a_hard_error():
    m = _manifest({
        "compound_n_map": {"77,78": "77"}, "unmarked_columns": ["B1"],
        "expected_gaps": ["B78"],
    })
    xml = _fragmenta_xml('<div type="Fragment" n="1"><p>ζζζ</p></div>')
    with pytest.raises(ValueError, match="no such div was found"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- compound_n_map collision matrix (Sol review blocker S2) ---------------

def test_compound_n_map_source_colliding_with_div_map_source_is_a_hard_error():
    m = _manifest({
        "compound_n_map": {"77,78": "77"},
        "div_map": [{"n": "77,78", "target": "B76", "role": "context",
                     "position": "leading", "label": "Alt"}],
        "expected_gaps": ["B78"],
    })
    xml = _fragmenta_xml('<div type="Fragment" n="77,78"><p>ααα</p></div>')
    with pytest.raises(ValueError, match="at most one merge mechanism"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_compound_n_map_source_colliding_with_div_concat_source_is_a_hard_error():
    m = _manifest({
        "compound_n_map": {"77,78": "77"},
        "div_concat": {"B50": ["77,78", "51"]},
        "expected_gaps": ["B78"],
    })
    xml = _fragmenta_xml(
        '<div type="Fragment" n="77,78"><p>ααα</p></div>',
        '<div type="Fragment" n="51"><p>βββ</p></div>',
    )
    with pytest.raises(ValueError, match="at most one merge mechanism"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_compound_n_map_target_must_equal_first_heading_component():
    m = _manifest({
        "compound_n_map": {"77,78": "78"},
        "expected_gaps": ["B77"],
    })
    xml = _fragmenta_xml('<div type="Fragment" n="77,78"><p>ααα</p></div>')
    with pytest.raises(ValueError, match="first heading component"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_compound_n_map_trailing_component_must_be_in_expected_gaps():
    m = _manifest({"compound_n_map": {"77,78": "77"}})  # no expected_gaps entry
    xml = _fragmenta_xml('<div type="Fragment" n="77,78"><p>ααα</p></div>')
    with pytest.raises(ValueError, match="citation.expected_gaps"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_compound_n_map_target_colliding_with_div_concat_target_is_a_hard_error():
    m = _manifest({
        "compound_n_map": {"77,78": "77"},
        "div_concat": {"B77": ["50", "51"]},
        "expected_gaps": ["B78"],
    })
    xml = _fragmenta_xml(
        '<div type="Fragment" n="50"><p>ααα</p></div>',
        '<div type="Fragment" n="51"><p>βββ</p></div>',
        '<div type="Fragment" n="77,78"><p>γγγ</p></div>',
    )
    with pytest.raises(ValueError, match="collide with citation.div_concat"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_map_target_colliding_with_div_concat_target_is_a_hard_error():
    # Sol review blocker S1b: div_map's contract requires a REAL,
    # independently-existing target column -- a div_concat column (composed
    # from parts with no div of its own) can never be one, so declaring the
    # SAME name as both a div_map target and a div_concat target must be
    # rejected at manifest-parsing time.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="9"><p>δδδ</p></div>',
        '<div type="Fragment" n="28,977a"><p>ααα</p></div>',
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_map": [
            {"n": "9", "target": "A28", "role": "context",
             "position": "leading", "label": "X"},
        ],
        "div_concat": {"A28": ["28,977a", "28,977b"]},
    })
    with pytest.raises(ValueError, match="also declares it as a merge target"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_div_concat_member_colliding_with_div_map_target_is_a_hard_error():
    # Sol review blocker S1c: a div_concat MEMBER (source n) must not also
    # be a declared div_map TARGET -- a div may be declared in at most one
    # merge mechanism, on either side of it (the source-side collision is
    # already covered by test_div_concat_source_collides_with_div_map_is_a_
    # hard_error above; this is the target-side mirror).
    xml = _fragmenta_xml(
        '<div type="Fragment" n="9"><p>δδδ</p></div>',
        '<div type="Fragment" n="28,977b"><p>βββ</p></div>',
    )
    m = _manifest({
        "series": "A",
        "div_map": [
            {"n": "9", "target": "28,977a", "role": "context",
             "position": "leading", "label": "X"},
        ],
        "div_concat": {"A28": ["28,977a", "28,977b"]},
    })
    with pytest.raises(ValueError, match="also a citation.div_map target"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- verse fragments (Parmenides pilot: citation.lines: true) --------------


def _verse_manifest(citation_extra: dict | None = None, work_id: str = "FIXWORK"):
    extra = {"lines": True}
    extra.update(citation_extra or {})
    m = _manifest(extra, work_id)
    return m, scheme_mod.for_manifest(m)


def test_verse_declared_text_lines_get_sequential_citable_n():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<l n="1">ΞΞΞ ΨΨΨ</l>'
        '<l n="2">αα ββ</l>'
        '<l n="3">γγ δδ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": [2, 3]},
        "verse_text_line_counts": {"B1": 2},
    })
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    text_lines = [e for e in flat if e["role"] == "text"]
    ctx_lines = [e for e in flat if e["role"] == "context"]
    assert [(e["n"], e["text"]) for e in text_lines] == [(1, "αα ββ"), (2, "γγ δδ")]
    assert ctx_lines[0]["text"] == "ΞΞΞ ΨΨΨ"
    assert ctx_lines[0]["n"] < 0  # non-citable, distinct number space


def test_verse_declared_empty_text_lines_suppresses_real_letter_spacing():
    # Sol review blocker S5 (nit): a direct regression test for the
    # explicit-empty-override shape (`col: []`, paired
    # `verse_text_line_counts[col]: 0`) -- real corpus shape: Xenophanes'
    # B4/B19/B21/B21a/B39/B40/B41 (seven columns) each carry GENUINE
    # `<hi rend="letter-spacing">` markup embedded in a source's own
    # narrative sentence, positively suppressed via an explicit `[]` rather
    # than left to the mechanical per-line walk (which would otherwise
    # wrongly promote the WHOLE containing line, narrative and all, to
    # role='text'). No test exercised this shape at all before this fix --
    # every existing verse_text_lines test used a non-empty list.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<l n="1">ΞΞΞ <hi rend="letter-spacing">λόγος</hi> ΨΨΨ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": []},
        "verse_text_line_counts": {"B1": 0},
        "unmarked_columns": ["B1"],
    })
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert all(e["role"] == "context" for e in flat)
    assert "λόγος" in " ".join(e["text"] for e in flat)


def test_verse_mechanical_role_persists_across_line_boundary():
    # A self-closing letter-spacing milestone opening at the START of one
    # <l> must carry its role into the NEXT <l> too (mirrors Parmenides
    # B21's real "ψευ-" / "δοφανῆ" hyphenated word-wrap, one line further
    # out for clarity here): line 1 is pure context, line 2's milestone
    # flips role for the rest of ITS content, and line 3 -- with no <hi> of
    # its own at all -- still inherits role='text' from that milestone.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="21">'
        '<l n="1">ΞΞΞ</l>'
        '<l n="2"><hi rend="letter-spacing"/>ψευ-</l>'
        '<l n="3">δοφανῆ</l>'
        "</div>",
    )
    m, sch = _verse_manifest()
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("context", "ΞΞΞ"),
        ("text", "ψευ-"),
        ("text", "δοφανῆ"),
    ]


def test_verse_context_flush_rejoins_wrapped_hyphens():
    # Xenophanes B4/B12/B21/B39 shape: ordinary verse-column path (not
    # prose_columns) flushes consecutive non-text <l> lines into one
    # role='context' block. TLG print-line hyphenation survives inside that
    # flush as "Δη- μοδίκη"; the flat-chapter and prose_columns paths already
    # call `_rejoin_wrapped_hyphens` -- this path must too.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="4">'
        '<l n="1">εἴτε Δη- μοδίκη ἡ Κυμαία</l>'
        '<l n="2"><hi rend="letter-spacing">λόγος</hi></l>'
        "</div>",
    )
    m, sch = _verse_manifest()
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    ctx = [e for e in flat if e["role"] == "context"]
    assert len(ctx) == 1
    assert "Δημοδίκη" in ctx[0]["text"]
    assert "Δη- μοδίκη" not in ctx[0]["text"]


def test_verse_text_lines_stale_declaration_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><l n="1">'
        '<hi rend="letter-spacing">λόγος</hi></l></div>'
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B2": [1]},
        "verse_text_line_counts": {"B2": 1},
    }, work_id="FIXWORK")
    with pytest.raises(ValueError, match="verse_text_lines declares"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_verse_text_lines_partial_declaration_is_a_hard_error():
    # The worst silent-failure class (Sol review blocker 1): the div has 5
    # real verse lines, but the declaration only covers a clean 1..k PREFIX
    # of them (a truncated/copy-paste-incomplete edit) -- every declared
    # value is real and unique, so nothing about it looks wrong on its own,
    # and without the independently-declared count the remaining real verse
    # (lines 4-5) would silently demote to muted context. The mismatched
    # verse_text_line_counts entry is what catches it.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<l n="1">ΞΞΞ</l>'
        '<l n="2">αα</l>'
        '<l n="3">ββ</l>'
        '<l n="4">γγ</l>'
        '<l n="5">δδ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": [2, 3]},  # should have been [2, 3, 4, 5]
        "verse_text_line_counts": {"B1": 4},  # the true, independently-known count
    })
    with pytest.raises(ValueError, match="declares 2 line.*declares 4"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_verse_text_lines_declared_value_not_in_div_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<l n="1">ΞΞΞ</l>'
        '<l n="2">αα</l>'
        "</div>",
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": [2, 5]},  # "5" does not exist in this div
        "verse_text_line_counts": {"B1": 2},
    })
    with pytest.raises(ValueError, match="do not exist as a raw"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_verse_text_lines_duplicate_declared_value_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<l n="1">ΞΞΞ</l>'
        '<l n="2">αα</l>'
        '<l n="3">ββ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": [2, 2, 3]},
        "verse_text_line_counts": {"B1": 3},
    })
    with pytest.raises(ValueError, match="duplicate entries"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_verse_text_line_counts_missing_entry_is_a_hard_error():
    m, sch = _verse_manifest({"verse_text_lines": {"B1": [2, 3]}})
    with pytest.raises(ValueError, match="has no matching entry"):
        _parse_fragments(_tree(_fragmenta_xml(
            '<div type="Fragment" n="1"><l n="1">x</l></div>',
        )), sch, m, "fixture")


def test_verse_text_line_counts_stale_entry_is_a_hard_error():
    m, sch = _verse_manifest({
        "verse_text_lines": {"B1": [2, 3]},
        "verse_text_line_counts": {"B1": 2, "B2": 1},
    })
    with pytest.raises(ValueError, match="declares no such column"):
        _parse_fragments(_tree(_fragmenta_xml(
            '<div type="Fragment" n="1"><l n="1">x</l></div>',
        )), sch, m, "fixture")


def test_verse_text_lines_requires_citation_lines_true():
    xml = _fragmenta_xml('<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>')
    m = _manifest({"verse_text_lines": {"B1": [1]}})
    with pytest.raises(ValueError, match="only meaningful for a verse dk work"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


# --- citation.prose_columns (Wave 1c Sophists batch 2, Critias Fragmenta: a
# `citation.lines: true` work whose export line-splits EVERY div uniformly,
# including columns whose real content is testimonial prose, not verse) ----

def test_prose_columns_merges_lines_and_rejoins_hyphen_no_cite_n():
    # Two consecutive raw <l> lines, mid-word print-line hyphenation on the
    # first (a synthetic prose word split "λό-" / "γος") -- must rejoin
    # into one word, with a real reconstructed space at the OTHER
    # (non-hyphenated) line boundary, and land as ONE merged text block
    # carrying no citable verse-line number (unlike an ordinary verse
    # column's per-line `cite_n`).
    xml = _fragmenta_xml(
        '<div type="Fragment" n="32">'
        '<l n="1"><hi rend="letter-spacing">ἐστὶ δὲ ὁ λό-</hi></l>'
        '<l n="2"><hi rend="letter-spacing">γος ἀγαθός.</hi></l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B32"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert len(flat) == 1
    entry = flat[0]
    assert entry["role"] == "text"
    assert entry["text"] == "ἐστὶ δὲ ὁ λόγος ἀγαθός."
    assert entry["n"] < 0  # non-citable, same number space as verse context


def test_prose_columns_context_and_text_both_merge_role_by_role():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="32">'
        '<l n="1">ΞΞΞ ΨΨΨ</l>'
        '<l n="2"><hi rend="letter-spacing">λόγος ἐστὶν</hi></l>'
        '<l n="3"><hi rend="letter-spacing">ἀγαθός.</hi></l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B32"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("context", "ΞΞΞ ΨΨΨ"),
        ("text", "λόγος ἐστὶν ἀγαθός."),
    ]


def test_prose_columns_mixed_role_single_line_splits_at_run_granularity():
    # Critias B31/B53/B60 shape (content-verification finding, Wave 1c
    # Sophists batch 2): a citation/apparatus header immediately followed by
    # a letter-spaced quotation, both on the SAME raw <l> -- must NOT
    # collapse to a single role='text' line (the old per-line "is_text = any
    # run in it came out True" bug); the context/text split within the line
    # must survive into the merged prose blocks.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="31">'
        '<l n="1">ΝΝΝ <hi rend="letter-spacing">λόγος ἐστίν</hi> ΨΨΨ ΩΩΩ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B31"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("context", "ΝΝΝ"),
        ("text", "λόγος ἐστίν"),
        ("context", "ΨΨΨ ΩΩΩ"),
    ]
    assert all(e["n"] < 0 for e in flat)  # prose_columns: never a citable cite_n


def test_prose_columns_mixed_role_line_ambient_carries_from_prior_line():
    # A milestone opened near the END of line 1 (no closing tag before the
    # line ends) must carry role='text' into line 2's own leading run, using
    # `_dk_role_blocks`' returned end_state (not the old `runs[-1][0]`
    # inference) -- exactly the div_concat bug class, now proven for the
    # prose_columns run-granularity path too.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="31">'
        '<l n="1">ΝΝΝ <hi rend="letter-spacing"/>ἐστὶ</l>'
        '<l n="2">λόγος.</l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B31"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("context", "ΝΝΝ"),
        ("text", "ἐστὶ λόγος."),
    ]


def test_prose_columns_hyphen_wrap_at_role_boundary_text_then_context():
    # Residual blocker (re-review of the uncommitted Sophists batch 2 tree):
    # a mid-word print-line hyphen-wrap ("λό-" / "γος") landing EXACTLY at a
    # role transition -- here a scoped letter-spacing span closes right at
    # the hyphen, so line 1's own run is role='text' ("λό-") and line 2's
    # continuation is plain role='context' ("γος ἀγαθός."). Not yet observed
    # in this corpus's own six built works (checked directly against the
    # actual export), but a real, evidenced export shape in principle (a
    # milestone can open or close at any character), so it is handled
    # deterministically rather than left to silently split the word: a word
    # is never split across role blocks, and the hyphen-owner's role
    # (here, 'text') wins for the whole word. "ἀγαθός." -- everything AFTER
    # the continuation word -- keeps its own original role ('context'), in
    # its own block, unaffected.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="32">'
        '<l n="1"><hi rend="letter-spacing">λό-</hi></l>'
        '<l n="2">γος ἀγαθός.</l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B32"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("text", "λόγος"),
        ("context", "ἀγαθός."),
    ]
    assert all(e["n"] < 0 for e in flat)


def test_prose_columns_hyphen_wrap_at_role_boundary_context_then_text():
    # Mirror of the above with the roles reversed: the hyphenated fragment
    # ("λό-") is role='context', and the continuation ("γος ἐστίν") opens a
    # NEW letter-spacing span -- the hyphen-owner's role ('context') still
    # wins for the whole reassembled word, and the rest of the following
    # block ("ἐστίν") keeps its own role='text' in its own block.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="33">'
        '<l n="1">ΝΝΝ λό-</l>'
        '<l n="2"><hi rend="letter-spacing">γος ἐστίν</hi> ΨΨΨ</l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B33"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("context", "ΝΝΝ λόγος"),
        ("text", "ἐστίν"),
        ("context", "ΨΨΨ"),
    ]
    assert all(e["n"] < 0 for e in flat)


def test_prose_columns_hyphen_wrap_at_role_boundary_folds_a_line_final_sigma():
    # Sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29): the
    # real corpus locus this covers is empedocles-fragments B29's own
    # "...τὰ βελτίονα, προς-" / "δοκᾶι δὲ..." (a wrap-hyphen landing exactly
    # at a role transition, the shape `_dk_rejoin_hyphen_across_role_blocks`
    # exists to handle). No Greek word contains a medial ς, so the rejoined
    # word must be "προσδοκᾶι", never the line-final "προςδοκᾶι" Schenkl's
    # print convention would otherwise leave glued in place.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="29">'
        '<l n="1"><hi rend="letter-spacing">προς-</hi></l>'
        '<l n="2">δοκᾶι δὲ καὶ θεούς.</l>'
        "</div>",
    )
    m, sch = _verse_manifest({"prose_columns": ["B29"]})
    flat, _ = _parse_fragments(_tree(xml), sch, m, "fixture")
    assert [(e["role"], e["text"]) for e in flat] == [
        ("text", "προσδοκᾶι"),
        ("context", "δὲ καὶ θεούς."),
    ]


def test_prose_columns_requires_citation_lines_true():
    xml = _fragmenta_xml('<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>')
    m = _manifest({"prose_columns": ["B1"]})
    with pytest.raises(ValueError, match="only meaningful for a verse dk work"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_prose_columns_and_verse_text_lines_are_mutually_exclusive():
    xml = _fragmenta_xml('<div type="Fragment" n="1"><l n="1">λόγος</l></div>')
    m, sch = _verse_manifest({
        "prose_columns": ["B1"],
        "verse_text_lines": {"B1": [1]},
        "verse_text_line_counts": {"B1": 1},
    })
    with pytest.raises(ValueError, match="mutually exclusive"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


def test_prose_columns_stale_declaration_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><l n="1">'
        '<hi rend="letter-spacing">λόγος</hi></l></div>',
    )
    m, sch = _verse_manifest({"prose_columns": ["B1", "B2"]})
    with pytest.raises(ValueError, match="no such column was ever emitted"):
        _parse_fragments(_tree(xml), sch, m, "fixture")


# --- div_concat ambient role threading (Wave 1c Sophists batch 2, Antiphon
# 87 B44: the div_concat prose path used to reset ambient role state to
# False at the start of EVERY source div's own <p>, silently muting every
# part after the one holding a milestone) --------------------------------

def test_div_concat_ambient_role_threads_across_parts():
    # A self-closing letter-spacing milestone opening near the end of the
    # FIRST part (no closing <hi> anywhere in that part) must carry
    # role='text' into the SECOND part too -- the same contract the verse
    # walker's own ambient threading already guarantees across <l> line
    # boundaries (see test_verse_mechanical_role_persists_across_line_
    # boundary above), now proven for div_concat's multi-<p> composition.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="44,A,col1">'
        '<p>ΞΞΞ <hi rend="letter-spacing"/>πρωτον</p>'
        "</div>",
        '<div type="Fragment" n="44,A,col2">'
        "<p>δευτερον</p>"
        "</div>",
    )
    m = _manifest({
        "series": "B",
        "div_concat": {"B44": ["44,A,col1", "44,A,col2"]},
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    b44 = [(e["role"], e["text"]) for e in flat if e["column"] == "B44"]
    # "δευτερον" (col2's own <p>, no <hi> of its own at all) must still
    # inherit role='text' from col1's trailing milestone -- the bug this
    # test guards was col2 silently resetting to role='context' instead.
    # Each source div's <p> still contributes its own flat entry (no
    # cross-<p> block merging), but BOTH now carry role='text'.
    assert b44 == [("context", "ΞΞΞ"), ("text", "πρωτον"), ("text", "δευτερον")]


def test_div_concat_ambient_does_not_leak_out_of_a_scoped_span_with_no_tail():
    # Edge shape (a) (Sol review blocker): part 1 ends INSIDE a SCOPED
    # (non-milestone) letter-spacing span with no tail after it -- the
    # scoped span's role='text' must NOT escape into part 2, since it never
    # escapes its own subtree in the first place. Before the fix (ambient
    # inferred from `runs[-1][0]` instead of `_dk_role_blocks`' own returned
    # end_state), part 2 wrongly inherited role='text'.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="44,A,col1">'
        '<p>ΞΞΞ <hi rend="letter-spacing">πρωτον</hi></p>'
        "</div>",
        '<div type="Fragment" n="44,A,col2">'
        "<p>δευτερον</p>"
        "</div>",
    )
    m = _manifest({
        "series": "B",
        "div_concat": {"B44": ["44,A,col1", "44,A,col2"]},
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    b44 = [(e["role"], e["text"]) for e in flat if e["column"] == "B44"]
    assert b44 == [("context", "ΞΞΞ"), ("text", "πρωτον"), ("context", "δευτερον")]


def test_div_concat_ambient_carries_across_an_empty_terminal_milestone():
    # Edge shape (b) (Sol review blocker): part 1 ends with an empty
    # self-closing milestone and NO following text at all -- no run is ever
    # emitted for it, so `runs[-1][0]` (the buggy inference) would read the
    # PRIOR run's state (False) instead of the milestone's own effect. Part
    # 2 must still inherit role='text'.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="44,A,col1">'
        '<p>ΞΞΞ <hi rend="letter-spacing"/></p>'
        "</div>",
        '<div type="Fragment" n="44,A,col2">'
        "<p>δευτερον</p>"
        "</div>",
    )
    m = _manifest({
        "series": "B",
        "div_concat": {"B44": ["44,A,col1", "44,A,col2"]},
    })
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    b44 = [(e["role"], e["text"]) for e in flat if e["column"] == "B44"]
    assert b44 == [("context", "ΞΞΞ"), ("text", "δευτερον")]


def test_duplicate_div_n_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">ἐστίν</hi></p></div>',
    )
    with pytest.raises(ValueError, match="appears more than once"):
        _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")


def test_role_coverage_gate_rejects_context_only_fragment():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="small">ΞΞΞ ΩΩΩ ΨΨΨ</hi></p></div>',
    )
    with pytest.raises(ValueError, match="no role='text' block"):
        _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")


def test_role_coverage_gate_honors_declared_unmarked_columns():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="small">ΞΞΞ ΩΩΩ ΨΨΨ</hi></p></div>',
    )
    m = _manifest({"unmarked_columns": ["B1"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert flat[0]["role"] == "context"


def test_prose_p_context_rejoins_wrapped_hyphens():
    # Ordinary prose-<p> branch (non-verse dk): a citation-head context run
    # can carry the same TLG print-line hyphen shape ("Δη- μοδίκη") that the
    # flat-chapter path already rejoins. prose_columns already calls
    # `_rejoin_wrapped_hyphens` on each merged block; this path must too.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<p>εἴτε Δη- μοδίκη ἡ Κυμαία <hi rend="letter-spacing">λόγος</hi></p>'
        "</div>",
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    ctx = [e for e in flat if e["role"] == "context"]
    assert len(ctx) == 1
    assert "Δημοδίκη" in ctx[0]["text"]
    assert "Δη- μοδίκη" not in ctx[0]["text"]


def test_stale_unmarked_columns_declaration_is_a_hard_error():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"unmarked_columns": ["B99"]})
    with pytest.raises(ValueError, match="stale"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_unmarked_columns_declaration_with_an_actual_text_run_is_a_hard_error():
    # The other direction of the same two-way-exact contract: a column
    # declared unmarked that DOES carry a role='text' letter-spacing run
    # (a re-export that now marks it normally, or a manifest typo) must fail
    # loudly too, not silently keep the column's block mis-tagged 'context'.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"unmarked_columns": ["B1"]})
    with pytest.raises(ValueError, match="DOES carry a role='text'"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_expected_gaps_present_in_export_is_a_hard_error():
    # Declaring B2 a gap while the export still carries it must fail loudly
    # (a re-export that RESTORED a declared-deleted column, e.g. B84/B109).
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
        '<div type="Fragment" n="2"><p><hi rend="letter-spacing">ἐστίν</hi></p></div>',
    )
    m = _manifest({"expected_gaps": ["B2"]})
    with pytest.raises(ValueError, match="expected_gaps declares"):
        _parse_fragments(_tree(xml), SCHEME, m, "fixture")


def test_expected_gap_genuinely_absent_is_silently_fine():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    m = _manifest({"expected_gaps": ["B2"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    assert {e["column"] for e in flat} == {"B1"}


def test_multi_block_fragment_gets_sequential_synthetic_n_and_role_per_block():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p>ΞΞΞ <hi rend="letter-spacing">λόγος</hi> ΨΨΨ</p></div>',
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert [(e["n"], e["role"], e["text"]) for e in flat] == [
        (1, "context", "ΞΞΞ"),
        (2, "text", "λόγος"),
        (3, "context", "ΨΨΨ"),
    ]


def test_multiple_p_elements_in_one_div_all_contribute_blocks():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1">'
        '<p><hi rend="letter-spacing">λόγος</hi></p>'
        '<p><hi rend="letter-spacing">ἐστίν</hi></p>'
        "</div>",
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert [e["text"] for e in flat] == ["λόγος", "ἐστίν"]


# --- dk-context-lang.json decision-file staleness (nit c) ------------------

def _stage_decisions(tmp_path, monkeypatch, work_id: str, decisions: dict) -> None:
    """`decisions` is `{run_text: decision}`, test-readable -- converted here
    to the real committed hash-keyed shape (`{dk_lang.decision_key(run):
    {"decision", "note"}}`, see dk_lang.decision_key's doc) so the fixture
    file on disk matches what stage1 actually loads in production."""
    src = tmp_path / "sources" / work_id
    src.mkdir(parents=True, exist_ok=True)
    hashed = {
        dk_lang.decision_key(dk_lang.normalize_run(run)): {"decision": decision, "note": "test"}
        for run, decision in decisions.items()
    }
    (src / "dk-context-lang.json").write_text(
        json.dumps(hashed, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(stage1_greek, "SOURCES_DIR", tmp_path / "sources")


def test_stale_decision_file_entry_is_a_hard_error(tmp_path, monkeypatch):
    # "ZZZ nichtvorhanden" never occurs anywhere in this export -- a stale
    # decision (re-export changed the text, or an authoring slip) must fail
    # loudly rather than sitting unreviewably dead in the decision file.
    _stage_decisions(tmp_path, monkeypatch, "FIXWORK", {
        "XYZ": "citation",
        "ZZZ nichtvorhanden": "strip-german",
    })
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi> XYZ</p></div>',
    )
    with pytest.raises(ValueError, match="stale"):
        _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")


def test_every_decision_actually_consulted_is_not_stale(tmp_path, monkeypatch):
    _stage_decisions(tmp_path, monkeypatch, "FIXWORK", {"XYZ": "citation"})
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi> XYZ</p></div>',
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert any("XYZ" in e["text"] for e in flat)


def test_headings_is_always_empty_for_dk():
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>',
    )
    _flat, headings = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    assert headings == []


# --- _line_text: verified export artifact stripping (Empedocles B109a) -----

def test_line_text_strips_declared_extra_chars_glued_to_a_word():
    # U+1017C GREEK OBOL SIGN glued directly onto "ὁρῶντα" with no space --
    # a confirmed Diogenes/TLG export artifact (Empedocles B109a), not part
    # of the word and not something stage3_tokenize.py's Beta Code
    # transliteration can handle. Sol blocker S3: scoped to an explicit
    # `extra_strip_chars` argument (this work's manifest-declared
    # `citation.export_artifact_chars`) rather than an unconditional
    # module-level constant applied to every work.
    xml = f"""<l xmlns="{TEI_NS}">ἐπὶ τὸν ὁρῶντα\U0001017c. περὶ μὲν</l>"""
    el = etree.fromstring(xml.encode("utf-8"))
    assert _line_text(el, extra_strip_chars="\U0001017c") == "ἐπὶ τὸν ὁρῶντα. περὶ μὲν"


def test_line_text_does_not_strip_undeclared_chars():
    # Zero-diff default: a work that does NOT declare this exact character
    # in citation.export_artifact_chars must see it survive untouched.
    xml = f"""<l xmlns="{TEI_NS}">ἐπὶ τὸν ὁρῶντα\U0001017c. περὶ μὲν</l>"""
    el = etree.fromstring(xml.encode("utf-8"))
    assert _line_text(el) == "ἐπὶ τὸν ὁρῶντα\U0001017c. περὶ μὲν"


def test_parse_fragments_strips_export_artifact_chars_in_prose_divs():
    # Wave 1b Zeno/Melissus/Anaxagoras batch: `citation.export_artifact_chars`
    # (Empedocles B109a's mechanism) was wired only into the verse path
    # (`_dk_walk_verse_div` via `_line_text`'s `extra_strip_chars`) -- a
    # PROSE dk work's own div-walking loop (the `else` branch below the
    # `if is_verse:` block) never consulted it at all, so a prose testimonium
    # carrying the identical glued-artifact shape (Zeno A28's embedded
    # diagram direction arrows glued onto "ΒΒΒΒ"/"ΓΓΓΓ" with no separating
    # space) hit stage3_tokenize's Beta Code transliteration hard error
    # instead of stripping cleanly like the verse case. Repro: a prose
    # (non-`lines`) dk manifest declaring the arrow as an artifact char must
    # see it stripped from a plain context block's text.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">ΒΒΒΒ→ καὶ Α</hi></p></div>',
    )
    m = _manifest({"export_artifact_chars": ["→"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    texts = [e["text"] for e in flat if e["column"] == "B1"]
    assert any("→" not in t for t in texts)
    assert not any("→" in t for t in texts)


def test_parse_fragments_strips_the_leftwards_arrow_export_artifact_too():
    # Companion to the rightwards-arrow test above: the real Zeno testimonia
    # manifest declares BOTH U+2192 (→) and U+2190 (←) -- Simplicius'
    # Stadium-paradox diagram (A28) marks the two rows of moving blocks with
    # direction arrows pointing opposite ways. Only "→" had direct test
    # coverage; this exercises "←" through the same prose path with both
    # characters declared together, mirroring the real manifest exactly.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p><hi rend="letter-spacing">ΒΒΒΒ→ καὶ ΓΓΓΓ← Α</hi></p></div>',
    )
    m = _manifest({"export_artifact_chars": ["→", "←"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    texts = [e["text"] for e in flat if e["column"] == "B1"]
    assert not any("→" in t or "←" in t for t in texts)


def test_dk_merge_blocks_inserts_space_at_digit_to_greek_glue():
    # Empedocles A20a: a citation number's tail run into a sibling <hi>'s
    # text with no source whitespace at all must not glue into one
    # un-tokenizable run.
    from reader_pipeline.stage1_greek import _dk_merge_blocks
    runs = [(False, "...1208b 11"), (False, "φασὶ δὲ")]
    blocks = _dk_merge_blocks(runs)
    assert blocks == [{"role": "context", "text": "...1208b 11 φασὶ δὲ"}]


def test_dk_merge_blocks_does_not_insert_space_mid_greek_word():
    from reader_pipeline.stage1_greek import _dk_merge_blocks
    runs = [(True, "μέγα"), (True, "λοπρεπής")]
    blocks = _dk_merge_blocks(runs)
    assert blocks == [{"role": "text", "text": "μέγαλοπρεπής"}]


def test_dk_merge_blocks_inserts_space_at_digit_paren_to_greek_glue():
    # Anaxagoras A92 (Wave 1c, exposed by the milestone-vs-scoped fix --
    # see test_milestone_with_later_scoped_sibling_in_same_parent_is_a_noop
    # above): Diels' own in-text section number "(29)" (Theophrastus'
    # apparatus convention) glues directly onto the following quoted Greek
    # with no source whitespace at all -- "...τὸν ψόφον. (29)ἅπασαν...".
    # Before the fix, the closing ")" between the digit and the Greek
    # defeated the single-character digit check (Empedocles A20a's plain
    # digit-glue precedent), so the two blocks merged into one un-
    # tokenizable run ("(29)ἅπασαν" -> tokenize's "29ἅπασαν", a hard
    # to_beta_key failure on the bare "2").
    from reader_pipeline.stage1_greek import _dk_merge_blocks
    runs = [(False, "...τὸν ψόφον. (29)"), (False, "ἅπασαν δ' αἴσθησιν")]
    blocks = _dk_merge_blocks(runs)
    assert blocks == [
        {"role": "context", "text": "...τὸν ψόφον. (29) ἅπασαν δ' αἴσθησιν"},
    ]


def test_dk_merge_blocks_does_not_insert_space_at_letter_to_greek_glue():
    # Sol blocker S3: only a DIGIT-to-Greek glue is evidenced (Empedocles
    # A20a) -- an ASCII LETTER directly touching Greek with no space has no
    # corpus evidence behind it and must be left alone as a possibly
    # deliberately glued token, not "fixed" on the strength of a different
    # shape's evidence.
    from reader_pipeline.stage1_greek import _dk_merge_blocks
    runs = [(False, "abc"), (False, "τι")]
    blocks = _dk_merge_blocks(runs)
    assert blocks == [{"role": "context", "text": "abcτι"}]


# --- Sol blocker S3: manifest-scoped `dk_damaged_columns` / _dk_clean_line_
# text (Empedocles B142's papyrus-transcription cleanups) ------------------

def test_dk_clean_line_text_skips_damage_cleanup_outside_declared_columns():
    from reader_pipeline.stage1_greek import _dk_clean_line_text
    xml = f"""<l xmlns="{TEI_NS}">λόγοιο.Ὦ φίλοι ΤΕΓΕ.......</l>"""
    el = etree.fromstring(xml.encode("utf-8"))
    # damaged=False (the default): neither the inline-wrap rejoin nor the
    # damage-period strip fires -- a period legitimately touching an
    # uppercase Greek letter (a real, if rare, possible shape) survives.
    assert _dk_clean_line_text(el) == "λόγοιο.Ὦ φίλοι ΤΕΓΕ......."


def test_dk_clean_line_text_applies_damage_cleanup_inside_declared_columns():
    from reader_pipeline.stage1_greek import _dk_clean_line_text
    xml = f"""<l xmlns="{TEI_NS}">ΤΕΓΕΟΙΔΟΜΟΙΑΙΓ.......ΤΕΠ̣.ΟΑΙ</l>"""
    el = etree.fromstring(xml.encode("utf-8"))
    assert _dk_clean_line_text(el, damaged=True) == "ΤΕΓΕΟΙΔΟΜΟΙΑΙΓΤΕΠΟΑΙ"


def test_parse_fragments_scopes_damage_cleanup_to_declared_columns():
    # End-to-end: B142's div (declared in dk_damaged_columns) gets the
    # damage-period strip; a different verse column with the SAME
    # coincidental shape (undeclared) does not.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="142">'
        '<l n="1"><hi rend="letter-spacing">ΤΕΓΕ.......ΟΙ</hi></l>'
        '</div>',
        '<div type="Fragment" n="143">'
        '<l n="1"><hi rend="letter-spacing">ΤΕΓΕ.......ΟΙ</hi></l>'
        '</div>',
    )
    m = _manifest({
        "lines": True,
        "verse_text_lines": {"B142": ["1"], "B143": ["1"]},
        "verse_text_line_counts": {"B142": 1, "B143": 1},
        "dk_damaged_columns": ["B142"],
    })
    verse_scheme = scheme_mod.for_manifest(m)
    flat, _ = _parse_fragments(_tree(xml), verse_scheme, m, "fixture")
    by_col = {e["column"]: e["text"] for e in flat}
    assert by_col["B142"] == "ΤΕΓΕΟΙ"
    assert by_col["B143"] == "ΤΕΓΕ.......ΟΙ"


# --- Sol blocker: _DK_DAMAGE_PERIOD_LOWER_RE over-fired on ordinary sentence
# periods (Democritus A99a, a damaged Hibeh papyrus, Diogenes export
# tlg1304001.xml col. 2) -- the original version reused B142's uppercase-
# scoped "either side" alternation, which deletes ANY period with a
# lowercase Greek letter on just ONE side, so an ordinary sentence period
# followed by whitespace + "§" or an uppercase proper name was corrupted
# right along with the genuine intra-word lacuna dots. Verified against the
# real source: "...τῶν ὁμοφύλων. § ὅτι..." emitted "...τῶν ὁμοφύλων § ὅτι...",
# "...τῆς γῆς. § τούτωι..." emitted "...τῆς γῆς § τούτωι...". Fixed by
# requiring BOTH a lowercase Greek lookbehind AND lookahead together (a
# period run only matches when Greek immediately touches it on both sides,
# with no intervening whitespace) -- the actual lacuna shape.

def test_dk_damage_period_lower_re_preserves_sentence_period_before_section_mark():
    # Must-fail-first (a): on the pre-fix alternation regex, the period
    # here is deleted because "ν" (lowercase) sits immediately before it --
    # even though "§" (via a space) sits after, not another Greek letter.
    from reader_pipeline.stage1_greek import _DK_DAMAGE_PERIOD_LOWER_RE
    text = "συνενεχθέντων τῶν ὁμοφύλων. § ὅτι"
    assert _DK_DAMAGE_PERIOD_LOWER_RE.sub("", text) == text


def test_dk_damage_period_lower_re_preserves_sentence_period_before_uppercase_name():
    # Same bug, the OTHER real-div instance: "τῆς γῆς. Δη>μόκριτος" -- the
    # period sits between lowercase "ς" and (across a space) the capitalized
    # start of "Δημόκριτος". Must survive; it is not a lacuna dot.
    from reader_pipeline.stage1_greek import _DK_DAMAGE_PERIOD_LOWER_RE
    text = "εἶναι τῆς γῆς. Δημόκριτος δὲ"
    assert _DK_DAMAGE_PERIOD_LOWER_RE.sub("", text) == text


def test_dk_damage_period_lower_re_removes_intra_word_lacuna_dots():
    # Must-fail-first (b), the positive case this regex exists for: the
    # real papyrus lacuna shape -- one or more periods glued with NO
    # whitespace between two lowercase Greek letters inside a word.
    from reader_pipeline.stage1_greek import _DK_DAMAGE_PERIOD_LOWER_RE
    text = "σηπεδόνος απο.λ.λιπομενης απ.δ..πεσθαι φησὶν"
    assert (
        _DK_DAMAGE_PERIOD_LOWER_RE.sub("", text)
        == "σηπεδόνος απολλιπομενης απδπεσθαι φησὶν"
    )


def test_parse_fragments_prose_path_scopes_lower_damage_cleanup_to_declared_columns():
    # Must-fail-first (c): the prose-path lowercase regex must never fire
    # for a column not in this work's manifest-declared
    # `citation.dk_damaged_columns` -- mirrors
    # test_parse_fragments_scopes_damage_cleanup_to_declared_columns above
    # (B142's verse/uppercase case) for the A99a prose/lowercase case.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="99a">'
        '<p><hi rend="letter-spacing">απο.λ.λιπομενης</hi></p>'
        '</div>',
        '<div type="Fragment" n="99b">'
        '<p><hi rend="letter-spacing">απο.λ.λιπομενης</hi></p>'
        '</div>',
    )
    m = _manifest({"series": "A", "dk_damaged_columns": ["A99a"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    by_col = {e["column"]: e["text"] for e in flat}
    assert by_col["A99a"] == "απολλιπομενης"
    assert by_col["A99b"] == "απο.λ.λιπομενης"


def test_parse_fragments_prose_path_preserves_sentence_periods_and_removes_lacuna_dots_together():
    # End-to-end reproduction of Democritus A99a's actual div (Diogenes
    # export tlg1304001.xml col. 2, verified against the real source text):
    # genuine intra-word lacuna dots and ordinary sentence-final periods
    # before "§" occur in the SAME damaged column and must be told apart
    # correctly in a single pass.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="99a"><p><hi rend="letter-spacing">'
        "σηπεδόνος απο.λ.λιπομενης απ.δ..πεσθαι φησὶν ἐν τῶι ὑγρῶι τὰ ὅμοια, "
        "καὶ οὕτως γενέσθαι θάλατταν συνενεχθέντων τῶν ὁμοφύλων. § ὅτι δὲ "
        "ἐκ τῶν ὁμογενῶν θάλαττα, γίνεσθαι τῆς γῆς. § τούτωι μὲν οὖν"
        "</hi></p></div>",
    )
    m = _manifest({"series": "A", "dk_damaged_columns": ["A99a"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    text = next(e["text"] for e in flat if e["column"] == "A99a")
    assert "απολλιπομενης" in text
    assert "απδπεσθαι" in text
    assert "ὁμοφύλων. §" in text
    assert "γῆς. §" in text


# --- ς exclusion (Protagoras A30, Opus ruling 2026-08-29): [α-ω] numerically
# includes ς (U+03C2), so the lookbehind fired on a word-FINAL sigma -- but ς
# ends a word by definition, so a dot run after it is a lacuna BETWEEN two
# surviving word tails, never intra-word letter damage. The real A30 div
# (tlg1635001.xml, Oxyrh. Pap. II col. XII) carries "ης.......ς", which the
# old regex fused into the impossible "ηςς". The ruling: keep the dots (like
# the same sentence's other lacunae "η........ τοῖς", "τα...... ἐπ]ήδα") and
# open the trailing boundary with a space so stage3 can tokenize (interior
# dots are fatal there; edge dots strip before keying).

def test_dk_damage_period_lower_re_does_not_fire_after_final_sigma():
    # Must-fail-first: the old lookbehind [α-ω] matched ς and emitted "ηςς".
    from reader_pipeline.stage1_greek import _DK_DAMAGE_PERIOD_LOWER_RE
    text = "τωι ης.......ς καταλαμβάνοντα"
    assert _DK_DAMAGE_PERIOD_LOWER_RE.sub("", text) == text


def test_dk_damage_period_lower_re_still_strips_dots_before_final_sigma():
    # The LOOKAHEAD keeps ς on purpose: dots before a word-final sigma are
    # ordinary intra-word letter damage, the A99a case the regex exists for.
    from reader_pipeline.stage1_greek import _DK_DAMAGE_PERIOD_LOWER_RE
    assert _DK_DAMAGE_PERIOD_LOWER_RE.sub("", "τα..ς") == "τας"


def test_dk_damage_period_after_final_sigma_re_opens_token_boundary():
    from reader_pipeline.stage1_greek import (
        _DK_DAMAGE_PERIOD_AFTER_FINAL_SIGMA_RE,
    )
    text = "τωι ης.......ς καταλαμβάνοντα"
    assert (
        _DK_DAMAGE_PERIOD_AFTER_FINAL_SIGMA_RE.sub(r"\1 ", text)
        == "τωι ης....... ς καταλαμβάνοντα"
    )
    # A sentence period after ς with whitespace before the next word is NOT
    # this shape -- the lookahead requires a glued lowercase letter.
    text = "εἶναι τῆς γῆς. § τούτωι τῆς γῆς. Δημόκριτος"
    assert _DK_DAMAGE_PERIOD_AFTER_FINAL_SIGMA_RE.sub(r"\1 ", text) == text


def test_parse_fragments_prose_path_removes_combining_dot_before_period_regexes():
    # Sol catch (must-fail-first on the pre-reorder code): a combining dot
    # below (U+0323) glued between a letter and a lacuna run blinds both
    # period regexes' lookbehinds; removing it AFTER them re-created the
    # glued interior-dot shape stage3 hard-fails on. Removal now runs first
    # (as the verse path always did), so the ς rule still opens the boundary
    # and the intra-word strip still fires through a marked letter.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="30"><p><hi rend="letter-spacing">'
        "τωι ης̣.......ς καταλαμβάνοντα απο.λ̣.λιπομενης"
        "</hi></p></div>",
    )
    m = _manifest({"series": "A", "dk_damaged_columns": ["A30"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    text = next(e["text"] for e in flat if e["column"] == "A30")
    assert "ης....... ς καταλαμβάνοντα" in text
    assert "απολλιπομενης" in text
    assert "̣" not in text


def test_parse_fragments_prose_path_preserves_final_sigma_lacuna_with_dots():
    # End-to-end on the real Protagoras A30 shape: the between-tails lacuna
    # keeps its dots and gains a token boundary; the same line's other dot
    # runs (already whitespace-bounded on one side) pass through untouched.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="30"><p><hi rend="letter-spacing">'
        "τῶν η........ τοῖς κινδύνοις τωι ης.......ς καταλαμβάνοντα "
        "τα...... ἐπ]ήδα δὲ οὐκ"
        "</hi></p></div>",
    )
    m = _manifest({"series": "A", "dk_damaged_columns": ["A30"]})
    flat, _ = _parse_fragments(_tree(xml), SCHEME, m, "fixture")
    text = next(e["text"] for e in flat if e["column"] == "A30")
    assert "ης....... ς καταλαμβάνοντα" in text
    assert "ηςς" not in text
    assert "η........ τοῖς" in text
    assert "τα...... ἐπ]ήδα" in text


# --- _check_sourcedesc: FATAL author/edition-drift gate (Wave 1c Sol nit) --
# A wrong-author or wrong-edition re-export (e.g. a stale TLG_DIR pointing
# at a different numbered file -- Stoic Zeno TLG0635 exported in place of
# Zeno of Elea TLG0595) must fail loudly at parse time, not silently parse
# as if it were the declared work's own corpus.

def _sourcedesc_tree(sourcedesc_text: str):
    xml = f"""<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><sourceDesc>
<p>
  {sourcedesc_text}
</p>
</sourceDesc></fileDesc></teiHeader><text><body>
<div type="Fragment" n="1"><p><hi rend="letter-spacing">λόγος</hi></p></div>
</body></text></TEI>"""
    return _tree(xml)


def _manifest_with_expected_sourcedesc(expected: str | None) -> Manifest:
    work = {"id": "FIXWORK", "tlg_author": "9999", "tlg_work": "001",
            "greek_edition": "Fixture"}
    if expected is not None:
        work["expected_sourcedesc"] = expected
    return Manifest(
        {
            "work": work,
            "citation": {"scheme": "dk", "series": "B"},
            "books": [{"n": 1, "start": "B1", "end": "B2"}],
        },
        ROOT / "manifests" / "fake.yaml",
    )


def test_check_sourcedesc_passes_when_declared_substring_is_present():
    tree = _sourcedesc_tree(
        'Anaxagoras Phil., Testimonia (0713: 001) "Die Fragmente der '
        'Vorsokratiker, vol. 2, 6th edn.", Ed. Diels, H., Kranz, W. '
        "Berlin: Weidmann, 1952, Repr. 1966."
    )
    m = _manifest_with_expected_sourcedesc(
        'Anaxagoras Phil., Testimonia (0713: 001) "Die Fragmente der '
        "Vorsokratiker, vol. 2"
    )
    _check_sourcedesc(tree, m, "fixture")  # must not raise


def test_check_sourcedesc_fails_loudly_on_wrong_author():
    # Simulates the real-world failure mode the gate exists to catch: a
    # stale TLG_DIR export of a DIFFERENT author entirely (Stoic Zeno
    # TLG0635 in place of Zeno of Elea TLG0595, or any other author swap).
    tree = _sourcedesc_tree(
        'Zeno Stoic. Phil., Fragmenta (0635: 001) "Stoicorum Veterum '
        'Fragmenta, vol. 1", Ed. von Arnim, H. Leipzig: Teubner, 1905.'
    )
    m = _manifest_with_expected_sourcedesc(
        'Zeno Phil., Testimonia (0595: 001) "Die Fragmente der '
        "Vorsokratiker, vol. 1"
    )
    with pytest.raises(ValueError, match="expected_sourcedesc"):
        _check_sourcedesc(tree, m, "fixture")


def test_check_sourcedesc_fails_loudly_on_wrong_volume():
    # Same author/work, but a DIFFERENT DK volume than declared -- e.g. a
    # re-export that accidentally pulled vol. 1 content for a vol. 2 work.
    tree = _sourcedesc_tree(
        'Anaxagoras Phil., Testimonia (0713: 001) "Die Fragmente der '
        'Vorsokratiker, vol. 1, 6th edn.", Ed. Diels, H., Kranz, W. '
        "Berlin: Weidmann, 1951, Repr. 1966."
    )
    m = _manifest_with_expected_sourcedesc(
        'Anaxagoras Phil., Testimonia (0713: 001) "Die Fragmente der '
        "Vorsokratiker, vol. 2"
    )
    with pytest.raises(ValueError, match="expected_sourcedesc"):
        _check_sourcedesc(tree, m, "fixture")


def test_check_sourcedesc_is_a_noop_when_not_declared():
    # A work that hasn't been backfilled with work.expected_sourcedesc yet
    # skips the check entirely -- optional, not retroactively required.
    tree = _sourcedesc_tree("anything at all, not even a real sourceDesc shape")
    m = _manifest_with_expected_sourcedesc(None)
    _check_sourcedesc(tree, m, "fixture")  # must not raise


def test_check_sourcedesc_matches_across_source_whitespace_wrapping():
    # The real export wraps <sourceDesc><p> content across indented lines
    # (see build/export/.../tlg0713001.xml) -- the check must collapse that
    # incidental whitespace, not require it to match verbatim.
    tree = _sourcedesc_tree(
        "Anaxagoras Phil.,\n  Testimonia (0713: 001)\n  \"Die Fragmente "
        'der\n  Vorsokratiker, vol. 2, 6th edn.", Ed. Diels, H.'
    )
    m = _manifest_with_expected_sourcedesc(
        'Anaxagoras Phil., Testimonia (0713: 001) "Die Fragmente der '
        "Vorsokratiker, vol. 2"
    )
    _check_sourcedesc(tree, m, "fixture")  # must not raise


# --- quote-mark polarity fix (_dk_normalize_quote_marks) --------------------
#
# Owner ruling 2026-08-05 ("we fix it and make damn sure every instance is
# correct"): the raw TLG export frequently OPENS a Greek quotation with
# U+2019 RIGHT SINGLE QUOTATION MARK instead of U+2018 LEFT SINGLE
# QUOTATION MARK. These tests exercise the standalone helper directly
# (simplest, most precise way to pin down its pairing/fail-closed/safety
# behavior) plus one end-to-end wiring check through `_parse_fragments`.

def test_even_count_column_normalizes_alternately():
    # The dominant defect shape (measured against the live corpus): a pair
    # that opens with U+2019 (wrong) and closes with U+2018 (wrong) gets
    # rewritten to open U+2018 / close U+2019 (right).
    flat = [{"column": "B1", "n": 1, "text": "ΞΞΞ ’λόγος‘ ΨΨΨ"}]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == "ΞΞΞ ‘λόγος’ ΨΨΨ"


def test_odd_count_column_is_left_byte_identical():
    # FAIL CLOSED (owner ruling): an odd total mark count can't be paired
    # at all -- guessing which single mark is the stray would invent a
    # reading the source doesn't support. Left completely untouched, not
    # partially "fixed".
    original = "ΞΞΞ ’λόγος ΨΨΨ ‘ἐστίν ΩΩΩ ’τέλος"
    flat = [{"column": "B2", "n": 1, "text": original}]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == original


def test_elision_apostrophe_is_never_touched():
    # SAFETY (the critical fact): Greek elision uses U+0027 APOSTROPHE, a
    # completely different code point from either curly quote -- it must
    # survive byte-identical even on a line that ALSO carries a genuine,
    # correctable quote-mark pair right next to it.
    original = "δ' ’λόγος‘ καθ' αὑτόν"
    flat = [{"column": "B3", "n": 1, "text": original}]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == "δ' ‘λόγος’ καθ' αὑτόν"


def test_quotation_spanning_two_lines_pairs_across_the_boundary():
    # Quotations span lines -- pairing walks a WHOLE column's entries in
    # document order, never per-entry.
    flat = [
        {"column": "B4", "n": 1, "text": "ΞΞΞ ’λόγος"},
        {"column": "B4", "n": 2, "text": "ἐστίν‘ ΨΨΨ"},
    ]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == "ΞΞΞ ‘λόγος"
    assert flat[1]["text"] == "ἐστίν’ ΨΨΨ"


def test_already_correct_pair_is_unchanged():
    original = "ΞΞΞ ‘λόγος’ ΨΨΨ"
    flat = [{"column": "B5", "n": 1, "text": original}]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == original


def test_multiple_pairs_in_one_column_all_alternate():
    # Two ALREADY-adjacent same-facing pairs ("’’", "‘‘" -- fact 2's other
    # observed shapes) still resolve to a clean alternating sequence across
    # the whole column, not just within one naively-adjacent pair.
    flat = [{"column": "B6", "n": 1, "text": "’ΑΑΑ’ ΞΞΞ ‘ΒΒΒ‘"}]
    _dk_normalize_quote_marks(flat)
    assert flat[0]["text"] == "‘ΑΑΑ’ ΞΞΞ ‘ΒΒΒ’"


def test_normalization_is_wired_into_parse_fragments():
    # End-to-end check: _parse_fragments' own returned flat entries come
    # out already normalized -- not just the standalone helper in
    # isolation.
    xml = _fragmenta_xml(
        '<div type="Fragment" n="1"><p>’λόγος‘ '
        '<hi rend="letter-spacing">ἐστίν</hi></p></div>',
    )
    flat, _ = _parse_fragments(_tree(xml), SCHEME, _manifest(), "fixture")
    ctx = [e for e in flat if e["role"] == "context"][0]
    assert ctx["text"] == "‘λόγος’"


# --- sigma-fold correction, real corpus (docs/lined-source-plan.md §3, ------
# 2026-08-29) -----------------------------------------------------------

_EMPEDOCLES_FRAGMENTS_MANIFEST_PATH = (
    ROOT / "manifests" / "empedocles-fragments.yaml"
)
requires_empedocles_export = pytest.mark.skipif(
    not _EMPEDOCLES_FRAGMENTS_MANIFEST_PATH.exists()
    or not stage1_greek.exported_xml_path(
        Manifest.load(_EMPEDOCLES_FRAGMENTS_MANIFEST_PATH)
    ).exists(),
    reason="Diogenes TLG export not present for empedocles-fragments -- run "
           "`uv run python -m reader_pipeline --work empedocles-fragments "
           "stage1` once to populate it before this test can run",
)


@requires_empedocles_export
def test_real_corpus_empedocles_b122_no_medial_sigma_survives_the_rejoin():
    # The DK-work real locus (B122, Plut. de tranq. an. 15 p. 474 B): Schenkl-
    # style print sets "...τὰ βελτίονα, προς-" / "δοκᾶι δὲ..." across a
    # letter-spacing role-block boundary -- `_dk_rejoin_hyphen_across_role_
    # blocks` is the site that must fold the line-final ς back to medial σ
    # here, since it removes the hyphen before `_rejoin_wrapped_hyphens` ever
    # sees the block. No Greek word contains a medial ς.
    manifest = Manifest.load(_EMPEDOCLES_FRAGMENTS_MANIFEST_PATH)
    spine = parse_spine(stage1_greek.exported_xml_path(manifest), manifest)
    texts = [l["text"] for seg in spine["segments"] for l in seg["lines"]]
    assert any("προσδοκᾶι" in t for t in texts)
    assert not any("προςδοκᾶι" in t for t in texts)
    for t in texts:
        for i, ch in enumerate(t):
            if ch != "ς" or i + 1 >= len(t):
                continue
            nxt = t[i + 1]
            assert not (stage1_greek._is_greek_letter(nxt) and nxt.islower()), (t, i)
