"""Regression tests for tools/extract_burnet_wikisource.py's wikitext
parsing -- Herakleitos' `<section begin="DKn">` tag scan and Parmenides'
Burnet-numeral heading scan. No network: these exercise the module's
functions directly on minimal synthetic wikitext replicating the exact
structures found in the pinned Wikisource revisions (captured 2026-07-16,
see the module docstring) -- including the two real defects the module was
built to survive: the DK121 cross-page premature section-close, and fr. 6's
transposed-brace heading typo.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_burnet_wikisource", _TOOLS / "extract_burnet_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_burnet_wikisource"] = _mod
_spec.loader.exec_module(_mod)

ROOT = Path(__file__).resolve().parents[2]


# --- Herakleitos: DK-tag scan -----------------------------------------------

def test_dk_span_extraction_basic():
    text = (
        '<section begin="DK50" />{{fine|(1) It is wise to hearken. R.P. 40.}}'
        '<section end="DK50" />\n'
        '<section begin="DK1" />{{fine|(2) Though this Word is true. R. P. 32.}}'
        '<section end="DK1" />'
    )
    spans = _mod._extract_dk_spans(text)
    assert [name for name, _ in spans] == ["DK50", "DK1"]
    assert "It is wise to hearken" in spans[0][1]
    assert "Though this Word" in spans[1][1]


def test_dk_column_normalization_lowercases_suffix():
    # Real Wikisource tags are inconsistently cased (DK31A/DK31B alongside
    # lowercase DK49a/DK101a) -- the dk citation scheme's canonical suffix
    # is lowercase (docs/wave1b-presocratics-design.md SS2.1).
    assert _mod._normalize_dk_column("DK31A") == "B31a"
    assert _mod._normalize_dk_column("DK5B") == "B5b"
    assert _mod._normalize_dk_column("DK49a") == "B49a"
    assert _mod._normalize_dk_column("DK84B") == "B84b"
    assert _mod._normalize_dk_column("DK100") == "B100"


def test_dk_column_normalization_rejects_unmatched_shape():
    with pytest.raises(ValueError):
        _mod._normalize_dk_column("DKxx")


def test_dkxx_excluded_not_emitted_as_column(monkeypatch):
    # DKxx is Wikisource's own placeholder for "no genuine DK number" (see
    # module docstring) -- build_heraclitus must collect it separately and
    # never emit a "DKxx"/"Bxx" key.
    text = (
        '<section begin="DK50" />{{fine|(1) Real fragment.}}<section end="DK50" />\n'
        '<section begin="DKxx" />{{fine|(14) Excluded item.}}<section end="DKxx" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, excluded = _mod.build_heraclitus(patches=[])
    assert columns == {"B50": "Real fragment."}
    assert excluded == ["Excluded item."]


def test_merged_dk_column_duplicates_text(monkeypatch):
    text = (
        '<section begin="DK110111" />{{fine|(104) One translation, two DK numbers.}}'
        '<section end="DK110111" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_heraclitus(patches=[])
    assert columns == {
        "B110": "One translation, two DK numbers.",
        "B111": "One translation, two DK numbers.",
    }


def test_concat_merge_joins_split_tags_into_one_column(monkeypatch):
    # Real case: DK6 (the TLG export's edition) merged what an earlier
    # edition split as 5a/5b and 31a/31b -- Wikisource's tagging still
    # follows the split. _CONCAT_MERGE_COLUMNS concatenates each pair's
    # cleaned text (in tag order) under the single DK6 column.
    text = (
        '<section begin="DK5A" />{{fine|(1) First half.}}<section end="DK5A" />\n'
        '<section begin="DK5B" />{{fine|(2) Second half.}}<section end="DK5B" />\n'
        '<section begin="DK50" />{{fine|(3) An ordinary fragment.}}<section end="DK50" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_heraclitus(patches=[])
    assert columns == {
        "B5": "First half. Second half.",
        "B50": "An ordinary fragment.",
    }
    # The split halves are consumed by the merge, never emitted as their own
    # lettered columns.
    assert "B5a" not in columns and "B5b" not in columns


def test_concat_merge_fails_loud_on_missing_sibling_tag(monkeypatch):
    # Only one half of a declared pair is present -- Wikisource's tagging
    # must have changed; this must fail loudly, never silently emit a
    # half-translation under the merged column.
    text = '<section begin="DK5A" />{{fine|(1) First half only.}}<section end="DK5A" />'
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError):
        _mod.build_heraclitus(patches=[])


def test_concat_merge_fails_loud_on_a_duplicate_source_tag(monkeypatch):
    # A SECOND "DK5A" occurrence (a re-tagging slip, or a pinned-revision
    # bump that duplicated a span) used to silently OVERWRITE the first
    # half already captured in concat_parts, with no error at all -- nit
    # (d): duplicate DK5A/DK5B tags must fail loud, not overwrite.
    text = (
        '<section begin="DK5A" />{{fine|(1) First half.}}<section end="DK5A" />\n'
        '<section begin="DK5A" />{{fine|(1) A duplicate first half.}}<section end="DK5A" />\n'
        '<section begin="DK5B" />{{fine|(2) Second half.}}<section end="DK5B" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="duplicate Herakleitos tag"):
        _mod.build_heraclitus(patches=[])


def test_cross_reference_captured_verbatim_when_tagged():
    # No special-casing exists for cross-reference text -- if it were ever
    # tagged, the general mechanism captures it like any other content.
    text = '<section begin="DK99" />{{fine|(56) Same as 45.}}<section end="DK99" />'
    spans = _mod._extract_dk_spans(text)
    assert _mod._clean_heraclitus_fragment(spans[0][1]) == "Same as 45."


def test_untagged_cross_reference_not_extracted():
    # Real case (Ch. III, Bywater ordinal 56): a cross-reference note sits
    # BETWEEN two tagged fragments with no section tag of its own -- it must
    # never be fabricated into a fake column.
    text = (
        '<section begin="DK11" />{{fine|(55) Tagged fragment.}}<section end="DK11" />\n'
        '{{fine|(56) Same as 45.}}\n'
        '<section begin="DKxx" />{{fine|(57) Good and ill are one.}}<section end="DKxx" />'
    )
    spans = _mod._extract_dk_spans(text)
    assert [name for name, _ in spans] == ["DK11", "DKxx"]
    assert not any("Same as 45" in content for _, content in spans)


def test_ellipsis_template_renders_as_spaced_dots():
    text = '<section begin="DK43" />{{fine|(14) {{...}} bringing witnesses.}}<section end="DK43" />'
    spans = _mod._extract_dk_spans(text)
    assert _mod._clean_heraclitus_fragment(spans[0][1]) == ". . . bringing witnesses."


def test_footnote_ref_dropped():
    text = (
        '<section begin="DK1" />{{fine|(2) True<ref>a footnote, editorial apparatus'
        ' not the translation</ref> evermore.}}<section end="DK1" />'
    )
    spans = _mod._extract_dk_spans(text)
    cleaned = _mod._clean_heraclitus_fragment(spans[0][1])
    assert "footnote" not in cleaned
    assert cleaned == "True evermore."


def test_self_closing_ref_dropped():
    text = '<section begin="DK1" />{{fine|(2) True<ref name="x" /> evermore.}}<section end="DK1" />'
    spans = _mod._extract_dk_spans(text)
    assert _mod._clean_heraclitus_fragment(spans[0][1]) == "True evermore."


def test_ordinal_prefix_stripped():
    text = '<section begin="DK12" />{{fine|(41, 42) You cannot step twice.}}<section end="DK12" />'
    spans = _mod._extract_dk_spans(text)
    assert _mod._clean_heraclitus_fragment(spans[0][1]) == "You cannot step twice."


def test_multiple_fine_blocks_joined_with_space():
    # Real case: DK14 wraps two of Burnet's own numbered items (124, 125).
    text = (
        '<section begin="DK14" />{{fine|(124) Night-walkers.}}\n\n'
        '{{fine|(125) The mysteries.}}<section end="DK14" />'
    )
    spans = _mod._extract_dk_spans(text)
    cleaned = _mod._clean_heraclitus_fragment(spans[0][1])
    assert cleaned == "Night-walkers. (125) The mysteries."
    # only the SPAN's own leading ordinal is stripped -- the second item's
    # own numeral, mid-string, is left as Burnet printed it (matches the
    # real DK14 shipped text).


# --- raw/chunk patch mechanism ----------------------------------------------

def test_raw_patch_reconstructs_cross_page_fragment():
    # Replicates the real DK121 defect: a section closes prematurely,
    # mid-sentence, at a page boundary; the raw patch removes the premature
    # close so the general scan captures the whole two-page fragment.
    text = (
        '<section begin="DK121" />{{fine|(114) The Ephesians would do well,}}'
        ' <section end="DK121" />\n'
        '{{fine|saying more.}}\n<section end="DK121" />'
    )
    patches = [{
        "scope": "raw", "chapter": "heraclitus",
        "old": '(114) The Ephesians would do well,}} <section end="DK121" />',
        "new": '(114) The Ephesians would do well,}}',
    }]
    patched = _mod._apply_raw_patches(text, "heraclitus", patches)
    spans = _mod._extract_dk_spans(patched)
    assert len(spans) == 1
    cleaned = _mod._clean_heraclitus_fragment(spans[0][1])
    assert cleaned == "The Ephesians would do well, saying more."


def test_raw_patch_fails_loud_when_old_string_not_found():
    patches = [{"scope": "raw", "chapter": "heraclitus", "old": "not present anywhere", "new": "x"}]
    with pytest.raises(ValueError):
        _mod._apply_raw_patches("some text", "heraclitus", patches)


def test_raw_patch_fails_loud_when_old_string_matches_twice():
    patches = [{"scope": "raw", "chapter": "heraclitus", "old": "twice", "new": "x"}]
    with pytest.raises(ValueError):
        _mod._apply_raw_patches("twice twice", "heraclitus", patches)


def test_raw_patch_ignores_other_chapter():
    patches = [{"scope": "raw", "chapter": "parmenides", "old": "xyz", "new": "abc"}]
    # "xyz" is absent from this text, but the patch is scoped to a
    # different chapter, so it must not even be attempted.
    assert _mod._apply_raw_patches("hello world", "heraclitus", patches) == "hello world"


def test_raw_patch_b22_applies_the_real_wikisource_patches_entry():
    # End-to-end regression for the REAL WIKISOURCE-PATCHES.json B22 raw
    # patch (Grok review defect G2) -- unlike test_xenophanes_frag22_..._b22
    # below, which builds its synthetic fixture with the XenoFragB22 tags
    # ALREADY inserted (bypassing the raw-patch path entirely), this test
    # loads the actual patches file and drives the actual patch's "old"/"new"
    # text through _apply_raw_patches, so deleting or corrupting the real
    # B22 entry fails this test.
    patches = _mod._load_patches()
    b22_patches = [
        p for p in patches
        if p.get("scope") == "raw" and p.get("chapter") == "xenophanes"
    ]
    assert len(b22_patches) == 1, (
        "expected exactly one raw xenophanes patch (B22) in "
        "WIKISOURCE-PATCHES.json"
    )
    old = b22_patches[0]["old"]
    text = f"another poem (fr. 22 = 17 Karst.; R. P. 95 a):\n{old}\n"
    patched = _mod._apply_raw_patches(text, "xenophanes", patches)
    assert '<section begin="XenoFragB22" />' in patched
    assert '<section end="XenoFragB22" />' in patched
    # The wrapped span still contains the original, untouched text.
    assert old in patched


def test_raw_patch_fails_loud_on_double_apply():
    # The B22 patch's `new` value contains its `old` value as a substring
    # (wrapping it in section tags) -- applying it a second time must be
    # rejected as an idempotence violation, not silently nest the tags.
    patches = _mod._load_patches()
    b22_patches = [
        p for p in patches
        if p.get("scope") == "raw" and p.get("chapter") == "xenophanes"
    ]
    old = b22_patches[0]["old"]
    text = f"another poem (fr. 22 = 17 Karst.; R. P. 95 a):\n{old}\n"
    once = _mod._apply_raw_patches(text, "xenophanes", patches)
    with pytest.raises(ValueError, match="already applied"):
        _mod._apply_raw_patches(once, "xenophanes", patches)


def test_chunk_patch_applies_exactly_once_match():
    chunks = {"B50": "It is wise to hearcken, not to me."}
    patches = [{
        "scope": "chunk", "chapter": "heraclitus", "column": "B50",
        "replace": [["hearcken", "hearken"]],
    }]
    out = _mod._apply_chunk_patches(chunks, "heraclitus", patches)
    assert out["B50"] == "It is wise to hearken, not to me."


def test_chunk_patch_fails_loud_on_unknown_column():
    patches = [{"scope": "chunk", "chapter": "heraclitus", "column": "B999", "replace": [["a", "b"]]}]
    with pytest.raises(ValueError):
        _mod._apply_chunk_patches({"B50": "text"}, "heraclitus", patches)


def _real_chunk_patch(patches, chapter, column):
    matches = [
        p for p in patches
        if p.get("scope") == "chunk" and p.get("chapter") == chapter and p.get("column") == column
    ]
    assert len(matches) == 1, (
        f"expected exactly one chunk patch for {chapter}/{column} in "
        f"WIKISOURCE-PATCHES.json, found {len(matches)}"
    )
    return matches[0]


def test_chunk_patch_anaximander_b1_trims_burnet_frame_and_citation():
    # Grok content audit trim defect #1: the raw micro-pass extraction runs
    # past Burnet's own closing quotation mark into his connective frame
    # ("as he says in these somewhat poetical terms") and source citation
    # ("—Phys. Op. fr. 2 (R. P. 16)"). Drives the REAL WIKISOURCE-PATCHES.json
    # entry's own "old" text through _apply_chunk_patches, so deleting or
    # reverting that entry fails this test.
    patches = _mod._load_patches()
    patch = _real_chunk_patch(patches, "anaximander", "B1")
    old, new = patch["replace"][0]
    before = {
        "B1": 'And into that from which things take their rise they pass '
              'away once more, "as is meet; for they make reparation and '
              'satisfaction to one another for their injustice according '
              'to the ordering of time' + old
    }
    out = _mod._apply_chunk_patches(before, "anaximander", patches)
    assert out["B1"].endswith(
        'ordering of time," R. P. 16.'
    )
    assert "as he says in these somewhat poetical terms" not in out["B1"]
    assert "Phys." not in out["B1"]
    assert new in out["B1"]


def test_chunk_patch_anaximenes_b2_trims_source_citation():
    # Grok content audit trim defect #2: same shape as Anaximander B1 --
    # a trailing doxographical source citation ("—Aet. i. 3, 4 (R. P. 24)")
    # survives past Burnet's own closing quotation mark. Drives the REAL
    # WIKISOURCE-PATCHES.json entry.
    patches = _mod._load_patches()
    patch = _real_chunk_patch(patches, "anaximenes", "B2")
    old, new = patch["replace"][0]
    before = {
        "B2": '"Just as," he said, "our soul, being air, holds us '
              'together, so do breath and air encompass the whole world' + old
    }
    out = _mod._apply_chunk_patches(before, "anaximenes", patches)
    assert out["B2"].endswith('encompass the whole world." R. P. 24.')
    assert "Aet." not in out["B2"]
    assert new in out["B2"]


def test_chunk_patch_anaxagoras_b10_normalizes_footnote_residue():
    # Grok content audit trim defect #3: B10's citation ends "R. P. 155,
    # f, n. 1." -- the ", n. 1" is footnote-marker residue absent from
    # every other R. P. locator in this corpus (which use the bare
    # "R. P. NNN x." shape, e.g. this same file's B8: "R. P. 155 e.").
    # Drives the REAL WIKISOURCE-PATCHES.json entry.
    patches = _mod._load_patches()
    patch = _real_chunk_patch(patches, "anaxagoras", "B10")
    old, new = patch["replace"][0]
    before = {"B10": "How can hair come from what is not hair, or " + old}
    out = _mod._apply_chunk_patches(before, "anaxagoras", patches)
    assert out["B10"] == "How can hair come from what is not hair, or flesh? R. P. 155 f."
    assert "n. 1" not in out["B10"]
    assert new in out["B10"]


def test_committed_wave48_trimmed_fragments_end_clean():
    # Content-level regression pin against the REAL committed clean.json
    # files (not synthetic fixtures): if a future regeneration runs without
    # these WIKISOURCE-PATCHES.json chunk patches (patch reverted, deleted,
    # or the extractor's patch-application call removed), this must fail.
    def _load(name):
        return json.loads(
            (ROOT / "sources" / "burnet-egp" / name).read_text(encoding="utf-8")
        )

    anaximander = _load("burnet-anaximander.clean.json")
    assert anaximander["B1"].endswith('ordering of time," R. P. 16.')
    assert "as he says in these somewhat poetical terms" not in anaximander["B1"]
    assert "Phys." not in anaximander["B1"]

    anaximenes = _load("burnet-anaximenes.clean.json")
    assert anaximenes["B2"].endswith('encompass the whole world." R. P. 24.')
    assert "Aet." not in anaximenes["B2"]

    anaxagoras = _load("burnet-anaxagoras.clean.json")
    assert anaxagoras["B10"] == (
        "How can hair come from what is not hair, or flesh from what "
        "is not flesh? R. P. 155 f."
    )
    assert "n. 1" not in anaxagoras["B10"]


# --- Parmenides: heading-number scan ----------------------------------------

def _wrap_parm(body: str) -> str:
    return _mod._PARM_WRAPPER_BEGIN + body + _mod._PARM_WRAPPER_END


def test_parmenides_single_numeral_heading():
    text = _wrap_parm('{{c|{{fine|(2)}}}}\n{{fine|Look steadfastly.}}')
    frags = _mod._extract_parmenides_fragments(text)
    assert len(frags) == 1
    keys, raw = frags[0]
    assert keys == ("B2",)
    assert _mod._clean_parmenides_fragment(raw)[0] == "Look steadfastly."


def test_parmenides_combined_heading_duplicates_keys():
    text = _wrap_parm('{{c|{{fine|(4, 5)}}}}\n{{fine|Come now, I will tell thee.}}')
    frags = _mod._extract_parmenides_fragments(text)
    assert frags[0][0] == ("B4", "B5")


def test_parmenides_malformed_heading_brace_typo_still_parses():
    # Real defect (Page:.../188, fr. 6): "{{c|{{fine|(6}})}}}}" instead of
    # the well-formed "{{c|{{fine|(6)}}}}".
    text = _wrap_parm('{{c|{{fine|(6}})}}}}\n{{fine|It needs must be.}}')
    frags = _mod._extract_parmenides_fragments(text)
    assert len(frags) == 1
    keys, raw = frags[0]
    assert keys == ("B6",)
    assert _mod._clean_parmenides_fragment(raw)[0] == "It needs must be."


def test_parmenides_divider_heading_is_not_a_fragment_boundary():
    text = _wrap_parm(
        '{{c|{{fine|(1)}}}}\n{{fine|The car that bears me.}}\n\n'
        '{{c|{{sc|{{fine|The Way of Truth}}}}}}\n\n'
        '{{c|{{fine|(2)}}}}\n{{fine|Look steadfastly.}}'
    )
    frags = _mod._extract_parmenides_fragments(text)
    assert [keys for keys, _ in frags] == [("B1",), ("B2",)]
    text1 = _mod._clean_parmenides_fragment(frags[0][1])[0]
    assert "Way of Truth" not in text1


def test_parmenides_two_fragments_content_bounded_correctly():
    text = _wrap_parm(
        '{{c|{{fine|(2)}}}}\n{{fine|Fragment two text.}}\n\n'
        '{{c|{{fine|(3)}}}}\n{{fine|Fragment three text.}}'
    )
    frags = _mod._extract_parmenides_fragments(text)
    assert _mod._clean_parmenides_fragment(frags[0][1])[0] == "Fragment two text."
    assert _mod._clean_parmenides_fragment(frags[1][1])[0] == "Fragment three text."


# --- Parmenides: old-Diels-numeral -> DK6 remap for the 2-5 block ----------
#
# Burnet's own printed numerals for fr. 2, 3, and the combined "(4, 5)"
# heading follow Diels' EARLIER "Parmenides Lehrgedicht" (1897) numbering,
# not the DK6 (Diels-Kranz 6th ed., 1951) numbering the TLG spine uses --
# see the module docstring and sources/INVENTORY.md's Parmenides coverage
# note for the full content-match + Burnet-footnote evidence. Ground truth
# (verified against the real pinned Wikisource revisions and the DK6 Greek,
# 2026-07-17):
#   Burnet (2)    "Look steadfastly..."   = DK6 B4
#   Burnet (3)    "It is all one..."      = DK6 B5
#   Burnet (4, 5) "Come now... two ways   = DK6 B2 (+ B3, embedded: Burnet's
#                  ... same thing that      own footnote to this heading
#                  can be thought..."       calls the same-thought/being
#                                           line part of "fr. 4")


def test_build_parmenides_remaps_old_diels_numerals_to_dk6_columns(monkeypatch):
    text = _wrap_parm(
        '{{c|{{fine|(1)}}}}\n{{fine|Proem text.}}\n\n'
        '{{c|{{fine|(2)}}}}\n{{fine|Look steadfastly.}}\n\n'
        '{{c|{{fine|(3)}}}}\n{{fine|It is all one to me.}}\n\n'
        '{{c|{{fine|(4, 5)}}}}\n{{fine|Come now, the two ways.}}\n\n'
        '{{c|{{fine|(6}})}}}}\n{{fine|It needs must be.}}'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_parmenides(patches=[])
    assert columns == {
        "B1": "Proem text.",
        "B4": "Look steadfastly.",
        "B5": "It is all one to me.",
        "B2": "Come now, the two ways.",
        "B3": "Come now, the two ways.",
        "B6": "It needs must be.",
    }
    # The raw (identity) reading of Burnet's own numerals must NEVER survive
    # as a column of its own -- that would be exactly the B2-B5 content
    # mismatch this remap exists to fix.
    assert "B2" in columns and columns["B2"] != "Look steadfastly."


def test_build_parmenides_remap_fails_loud_when_expected_heading_missing(monkeypatch):
    # Wikisource's own printed numerals changing out from under the pinned
    # revisions (or a test fixture that forgets one) must fail loudly, never
    # silently skip the remap and ship an unremapped (wrong) column.
    text = _wrap_parm(
        '{{c|{{fine|(1)}}}}\n{{fine|Proem text.}}\n\n'
        '{{c|{{fine|(2)}}}}\n{{fine|Look steadfastly.}}'
        # (3) and (4, 5) deliberately missing.
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="_PARMENIDES_HEADING_REMAP"):
        _mod.build_parmenides(patches=[])


def test_parmenides_sidenote_markers_become_paras_with_correct_offsets():
    # Replicates the real B1 shape: a marker sitting mid-sentence, between
    # two fine blocks, with a space before it and none after.
    raw = (
        '{{fine|drawing my car,}} {{left sidenote|5}}{{fine|and maidens showed'
        ' the way.}}'
    )
    text, paras = _mod._clean_parmenides_fragment(raw)
    assert text == "drawing my car, and maidens showed the way."
    assert paras == [{"n": 5, "o": text.index("and maidens")}]


def test_parmenides_no_sidenote_markers_yields_empty_paras():
    text, paras = _mod._clean_parmenides_fragment('{{fine|Short fragment.}}')
    assert text == "Short fragment."
    assert paras == []


def test_parmenides_separator_and_nop_templates_stripped():
    raw = '{{fine|One clause.}} {{separator|8}} {{fine|Next clause.}} {{nop}}'
    text, _ = _mod._clean_parmenides_fragment(raw)
    assert "separator" not in text
    assert "nop" not in text
    assert text == "One clause. Next clause."


# --- Xenophanes: heading scan, numeral remap, listing-end boundary,
# XenoFragB (DK B8) re-attachment (Sol review blocker S4 / Grok review
# defect G1) -- previously ZERO dedicated tests for this extractor at all.

def _xeno_text(
    headings_body: str,
    *,
    frag8: str = "{{fine|Threescore years and seven.}}",
    frag22: str = "{{fine|This is the sort of thing we should say by the fireside.}}",
) -> str:
    """Minimal synthetic wikitext replicating the real Xenophanes shape:
    the chapter heading, a `XenoFragB`-wrapped cross-quote (DK B8), a
    `XenoFragB22`-wrapped cross-quote (DK B22, Grok review defect G2 --
    this module's OWN inserted tag, not Wikisource's), the numbered-heading
    listing body, and the listing's own `XenoFragC` end tag (see
    `_XENO_LISTING_END`'s doc -- without it the last heading's content
    cannot be bounded)."""
    return (
        "Xenophanes of Kolophon\n"
        f'<section begin="XenoFragB" />{frag8}<section end="XenoFragB" />\n'
        f'<section begin="XenoFragB22" />{frag22}<section end="XenoFragB22" />\n'
        f"{headings_body}"
        '<section end="XenoFragC" />'
    )


# (4)/(5) headings satisfy `build_xenophanes`'s own
# `_XENOPHANES_NUMERAL_REMAP` completeness check -- included in every
# `build_xenophanes`-level fixture below that isn't ITSELF testing that
# check, so the frag8/B8 hardening path (later in `build_xenophanes`) is
# actually reached.
_XENO_REMAP_HEADINGS = (
    '{{c|{{fine|(4)}}}}\n{{fine|Nor would a man mix wine.}}\n\n'
    '{{c|{{fine|(5)}}}}\n{{fine|Thou didst send the thigh-bone.}}\n\n'
)


def test_xenophanes_numeral_remap_4_to_b5_and_5_to_b6(monkeypatch):
    # Real defect class (module doc, `_XENOPHANES_NUMERAL_REMAP`): Burnet's
    # own printed numerals (4)/(5) predate DK6 by three decades and
    # translate DK6 B5/B6 respectively, not B4/B5.
    text = _xeno_text(
        '{{c|{{fine|(4)}}}}\n{{fine|Nor would a man mix wine.}}\n\n'
        '{{c|{{fine|(5)}}}}\n{{fine|Thou didst send the thigh-bone.}}\n\n'
        '{{c|{{fine|(7)}}}}\n{{fine|The dog fragment.}}\n'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns = _mod.build_xenophanes(patches=[])
    assert columns["B5"] == "Nor would a man mix wine."
    assert columns["B6"] == "Thou didst send the thigh-bone."
    assert columns["B7"] == "The dog fragment."
    # The RAW (unmapped) Burnet numerals must never survive as columns of
    # their own -- exactly the Parmenides B2-B5 defect class repeated here.
    assert "B4" not in columns


def test_xenophanes_frag22_reattached_as_b22(monkeypatch):
    # Grok review defect G2: Burnet DOES translate DK6 B22 ("This is the
    # sort of thing we should say by the fireside..."), embedded in the
    # biographical narrative like B8's own quotation but never wrapped in a
    # Wikisource `<section>` tag of its own -- re-attached via the SAME
    # discipline as B8, through a tag THIS module's own raw patch inserts
    # (WIKISOURCE-PATCHES.json). B22 must never sit in
    # `citation.alignment_allow_unmatched` once this column is emitted.
    text = _xeno_text(
        '{{c|{{fine|(4)}}}}\n{{fine|Nor would a man mix wine.}}\n\n'
        '{{c|{{fine|(5)}}}}\n{{fine|Thou didst send the thigh-bone.}}\n',
        frag22="{{fine|This is the sort of thing we should say by the fireside "
               "in the winter-time.}}",
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns = _mod.build_xenophanes(patches=[])
    assert columns["B22"] == (
        "This is the sort of thing we should say by the fireside in the "
        "winter-time."
    )


def test_xenophanes_numeral_remap_fails_loud_when_expected_heading_missing(monkeypatch):
    # (5) deliberately missing -- Wikisource's own numbering changing out
    # from under the pinned revisions (or a fixture that forgets one) must
    # fail loudly, never silently ship an unremapped B4.
    text = _xeno_text('{{c|{{fine|(4)}}}}\n{{fine|Nor would a man mix wine.}}\n')
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="_XENOPHANES_NUMERAL_REMAP"):
        _mod.build_xenophanes(patches=[])


def test_xenophanes_listing_end_bounds_last_heading_content():
    # Grok review defect G1 (real case: B38): the LAST heading in the
    # listing has no following heading to bound it against -- falling back
    # to "the rest of the fetched text" let Burnet's own post-listing
    # commentary (raw wiki markup included) bleed into it. Bounded instead
    # against `_XENO_LISTING_END` (the "XenoFragC" end tag).
    text = (
        "Xenophanes of Kolophon\n"
        '{{c|{{fine|(38)}}}}\n{{fine|If god had not made brown honey.}}'
        '<section end="XenoFragC" />\n'
        '58.{{right sidenote|The heavenly bodies.}} '
        "This trailing commentary must never leak into B38."
    )
    frags = _mod._extract_xenophanes_fragments(text)
    assert len(frags) == 1
    keys, raw = frags[0]
    assert keys == ("B38",)
    cleaned = _mod._clean_xenophanes_fragment(raw)
    assert cleaned == "If god had not made brown honey."
    assert "sidenote" not in cleaned
    assert "trailing commentary" not in cleaned.lower()


def test_xenophanes_missing_listing_end_tag_is_a_hard_error():
    text = (
        "Xenophanes of Kolophon\n"
        '{{c|{{fine|(1)}}}}\n{{fine|Fragment one.}}\n'
        # no <section end="XenoFragC" /> at all -- a stale/moved tag must
        # fail loudly, not silently fall back to "the rest of the text".
    )
    with pytest.raises(ValueError, match="XenoFragC"):
        _mod._extract_xenophanes_fragments(text)


def test_xenophanes_frag8_duplicate_tag_is_a_hard_error(monkeypatch):
    # Sol review blocker S4: a duplicated "XenoFragB" begin/end pair (a
    # re-tagging slip, or a pinned-revision bump that introduced a second
    # copy) must fail loudly, never silently re-attach against whichever
    # copy `.find()` happens to see first.
    text = (
        "Xenophanes of Kolophon\n"
        '<section begin="XenoFragB" />{{fine|First copy.}}<section end="XenoFragB" />\n'
        '<section begin="XenoFragB" />{{fine|Duplicate copy.}}<section end="XenoFragB" />\n'
        + _XENO_REMAP_HEADINGS
        + '{{c|{{fine|(1)}}}}\n{{fine|Fragment one.}}\n'
        '<section end="XenoFragC" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="XenoFragB"):
        _mod.build_xenophanes(patches=[])


def test_xenophanes_frag8_empty_content_is_a_hard_error(monkeypatch):
    text = (
        "Xenophanes of Kolophon\n"
        '<section begin="XenoFragB" /><section end="XenoFragB" />\n'
        + _XENO_REMAP_HEADINGS
        + '{{c|{{fine|(1)}}}}\n{{fine|Fragment one.}}\n'
        '<section end="XenoFragC" />'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="empty"):
        _mod.build_xenophanes(patches=[])


def test_xenophanes_frag8_residual_template_markup_is_a_hard_error(monkeypatch):
    # `_finish_plain_text` strips HTML-like `<...>` tags, never `{{...}}`
    # MediaWiki template invocations -- an unhandled template (unlike the
    # ellipsis/nop/separator templates `_strip_common_markup` DOES expand)
    # survives verbatim into the cleaned text. Real shape: a stray
    # "{{right sidenote|...}}" riding along outside the `{{fine|...}}`
    # block.
    text = _xeno_text(
        _XENO_REMAP_HEADINGS + '{{c|{{fine|(1)}}}}\n{{fine|Fragment one.}}\n',
        frag8="{{fine|Real content.}} {{right sidenote|stray}}",
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="wiki markup"):
        _mod.build_xenophanes(patches=[])


# --- Empedokles: numeral remap (S4, Sol blocker) ----------------------------
#
# `build_empedocles` requires EVERY `_EMPEDOCLES_HEADING_REMAP` key
# ((B4,), (B5,), (B77,B78)) and EVERY `_EMPEDOCLES_DROP` key ((B3,)) to
# actually be found in whatever wikitext it processes (its own
# `missing`/`missing_drop` checks) -- so every fixture below that calls the
# real `build_empedocles` includes ALL of headings (3), (4), (5), (77, 78)
# even when a given test only asserts on one piece of the result.

def _wrap_emped(body: str) -> str:
    return _mod._EMPED_WRAPPER_BEGIN + body + _mod._EMPED_WRAPPER_END


_EMPED_REQUIRED_HEADINGS = (
    '{{c|{{fine|(3)}}}}\n{{fine|to keep within thy dumb heart.}}\n\n'
    '{{c|{{fine|(4)}}}}\n{{fine|But, O ye gods, turn aside the madness of those men.}}\n\n'
    '{{c|{{fine|(5)}}}}\n{{fine|Low minds disbelieve their betters; '
    'to keep within thy dumb heart, understand.}}\n\n'
    '{{c|{{fine|(77, 78)}}}}\n{{fine|Evergreen trees couplet.}}'
)


def test_build_empedocles_3_dropped_as_content_subset_of_5_to_b4(monkeypatch):
    # Real Burnet defect: (3) translates only the TAIL clause of the SAME
    # passage (5) translates in full -- (3) is dropped outright (never any
    # column's content), and (5)'s own text already contains (3)'s clause
    # verbatim, i.e. nothing is lost -- content evidence, not just "(3) is
    # not a key".
    text = _wrap_emped(_EMPED_REQUIRED_HEADINGS)
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_empedocles(patches=[])
    assert columns == {
        "B3": "But, O ye gods, turn aside the madness of those men.",
        "B4": "Low minds disbelieve their betters; to keep within thy dumb "
              "heart, understand.",
        "B77": "Evergreen trees couplet.",
    }
    # (3)'s own standalone clause never appears as any column's WHOLE value
    # on its own...
    assert "to keep within thy dumb heart." not in columns.values()
    # ...but the SAME clause IS present, as a genuine substring, inside the
    # column (5) already supersedes it with (content evidence).
    assert "to keep within thy dumb heart" in columns["B4"]


def test_build_empedocles_4_to_b3_and_5_to_b4_exact_text(monkeypatch):
    text = _wrap_emped(_EMPED_REQUIRED_HEADINGS)
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_empedocles(patches=[])
    assert columns["B3"] == "But, O ye gods, turn aside the madness of those men."
    assert columns["B4"] == (
        "Low minds disbelieve their betters; to keep within thy dumb heart, "
        "understand."
    )


def test_build_empedocles_combined_77_78_heading_files_under_b77_only(monkeypatch):
    text = _wrap_emped(_EMPED_REQUIRED_HEADINGS)
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_empedocles(patches=[])
    assert columns["B77"] == "Evergreen trees couplet."
    assert "B78" not in columns


def test_build_empedocles_combined_heading_duplicates_under_both_keys(monkeypatch):
    # A DIFFERENT combined heading than 77-78 (which collapses onto B77
    # alone via compound_n_map) -- the general un-collapsed duplication
    # mechanism still duplicates identical text under both keys.
    text = _wrap_emped(
        _EMPED_REQUIRED_HEADINGS
        + '\n\n{{c|{{fine|(11, 12)}}}}\n{{fine|Shared couplet translation.}}'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_empedocles(patches=[])
    assert columns["B11"] == "Shared couplet translation."
    assert columns["B12"] == "Shared couplet translation."


def test_build_empedocles_purifications_title_stripped_from_b111(monkeypatch):
    text = _wrap_emped(
        _EMPED_REQUIRED_HEADINGS
        + '\n\n{{c|{{fine|(111)}}}}\n{{fine|Closing lines of the Physika.}}'
          '\n{{c|PURIFICATIONS}}\n\n'
          '{{c|{{fine|(112)}}}}\n{{fine|O friends, who dwell in the great city.}}'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, _ = _mod.build_empedocles(patches=[])
    assert "PURIFICATIONS" not in columns["B111"]
    assert columns["B111"] == "Closing lines of the Physika."
    assert columns["B112"] == "O friends, who dwell in the great city."


def test_build_empedocles_missing_remap_heading_fails_loud(monkeypatch):
    text = _wrap_emped('{{c|{{fine|(4)}}}}\n{{fine|Only one heading.}}')
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="_EMPEDOCLES_HEADING_REMAP"):
        _mod.build_empedocles(patches=[])


# --- extractor-wide invariant (Grok review defect G1): no emitted English
# value for ANY author THIS MODULE builds (Herakleitos/Parmenides/
# Xenophanes) may contain raw wiki template/link markup. Disk-based (not a
# synthetic fixture) -- it must fail against the REAL committed
# sources/burnet-egp/burnet-xenophanes.clean.json until that file is
# regenerated with the `_XENO_LISTING_END` boundary fix above. Scoped to
# `sources/burnet-egp/` specifically (this module's own output directory,
# `OUT_DIR`) -- NOT every `*.clean.json` in the repo: other extractors'
# outputs legitimately use bracket notation for unrelated purposes (e.g.
# the Long Meditations extractor's "[[Greek: aktines]]" transliteration
# gloss convention, which is not MediaWiki markup at all and is out of this
# module's -- and this fix round's -- scope).

def _iter_string_leaves(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_string_leaves(v)
    elif isinstance(value, list):
        for v in value:
            yield from _iter_string_leaves(v)


def test_no_wiki_template_markup_survives_in_any_clean_json():
    clean_json_paths = sorted(glob.glob(str(ROOT / "sources" / "burnet-egp" / "*.clean.json")))
    assert clean_json_paths, "expected at least one *.clean.json under sources/burnet-egp/"
    violations = []
    for path in clean_json_paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for text in _iter_string_leaves(data):
            if _mod._contains_wiki_markup(text):
                violations.append((path, text[:120]))
    assert violations == [], violations


# --- Task #48 (the Burnet English alignment wave): Zeno / Melissus /
# Anaxagoras (Ch. VIII / Ch. VI), plus the micro-pass (Anaximander B1,
# Anaximenes B2, Leucippus B2). No network: synthetic fixtures replicating
# the exact wikitext shapes found in the pinned revisions -- no verbatim
# Burnet/Diels text reproduced beyond a few generic words needed to exercise
# the parsing logic itself.

def test_committed_wave48_clean_json_key_sets():
    # Regression pin against the REAL committed files (not a synthetic
    # fixture) -- catches silent extractor drift changing a shipped key set
    # without a deliberate regeneration, same discipline as the wiki-markup
    # invariant sweep above.
    def _keys(name):
        return set(json.loads(
            (ROOT / "sources" / "burnet-egp" / name).read_text(encoding="utf-8")
        ).keys())

    assert _keys("burnet-zeno.clean.json") == {"B1", "B2", "B3"}
    assert _keys("burnet-melissus.clean.json") == {f"B{n}" for n in range(1, 11)}
    assert _keys("burnet-anaxagoras.clean.json") == (
        {f"B{n}" for n in range(1, 20)} | {"B21", "B21a", "B21b", "B22"}
    )
    assert _keys("burnet-anaximander.clean.json") == {"B1"}
    assert _keys("burnet-anaximenes.clean.json") == {"B2"}
    assert _keys("burnet-leucippus.clean.json") == {"B2"}


# --- Zeno (Ch. VIII): heading-numeral scan, hard-bounded to S:S160-S:S161 --

def _zeno_wrap(body: str) -> str:
    return _mod._ZENO_SECTION_START + "\n" + body + "\n" + _mod._ZENO_SECTION_END


def test_zeno_three_fragments_extracted_in_order():
    text = _zeno_wrap(
        '{{c|{{fine|(1)}}}}\n{{fine|If what is had no magnitude.}}\n\n'
        '{{c|{{fine|(2)}}}}\n{{fine|For if it were added.}}\n\n'
        '{{c|{{fine|(3)}}}}\n{{fine|If things are a many.}}'
    )
    frags = _mod._extract_zeno_fragments(text)
    assert [keys for keys, _ in frags] == [("B1",), ("B2",), ("B3",)]
    assert _mod._clean_xenophanes_fragment(frags[0][1]) == "If what is had no magnitude."


def test_zeno_missing_start_marker_is_hard_error():
    with pytest.raises(ValueError):
        _mod._extract_zeno_fragments("no S:S160 marker anywhere in this text")


def test_zeno_missing_end_marker_is_hard_error():
    text = _mod._ZENO_SECTION_START + "\nsome body with no S:S161 marker at all"
    with pytest.raises(ValueError):
        _mod._extract_zeno_fragments(text)


def test_zeno_section_163_paraphrase_excluded_by_the_160_161_bound():
    # MUST-FAIL coverage: S:S163 (Burnet's own PARAPHRASE of Aristotle's
    # motion testimonia -- stadium/Achilles/arrow/moving-rows -- never a
    # translation of any Zeno fragment, see the extractor's module doc)
    # sits, in the real chapter, strictly AFTER S:S161. Even a
    # correctly-shaped numbered heading placed there (as it would be
    # scanning "the rest of the text" instead of a hard-bounded span) must
    # never be picked up.
    text = (
        _zeno_wrap('{{c|{{fine|(1)}}}}\n{{fine|If what is had no magnitude.}}')
        + '\n163.{{right sidenote|Motion}} {{c|{{fine|(1)}}}}\n'
          '{{fine|You cannot cross a race-course.}}'
    )
    frags = _mod._extract_zeno_fragments(text)
    assert [keys for keys, _ in frags] == [("B1",)]
    assert not any(
        "race-course" in _mod._clean_xenophanes_fragment(raw) for _, raw in frags
    )


def test_zeno_section_163_inline_shape_cannot_produce_its_own_heading_match():
    # Structural defense in depth (per the module doc): S:S163's real shape
    # is an INLINE "{{fine|(N) ...}}" block with NO separate
    # "{{c|{{fine|(N)}}}}" heading of its own -- the heading-boundary scan
    # requires the literal "{{c|{{" heading-open sequence, so this shape can
    # never be mistaken for a fragment start, bound or no bound.
    text = _zeno_wrap(
        '{{c|{{fine|(1)}}}}\n{{fine|If what is had no magnitude.}}\n\n'
        '{{fine|(2) You cannot cross a race-course.}}'
    )
    frags = _mod._extract_zeno_fragments(text)
    assert not any(keys == ("B2",) for keys, _ in frags)


# --- Melissus / Anaxagoras: ordinal-fine inline scan, tag-bounded span -----

def test_extract_tag_bounded_span_basic():
    text = 'before<section begin="MelisFrag" />BODY<section end="MelisFrag" />after'
    assert _mod._extract_tag_bounded_span(
        text, '<section begin="MelisFrag" />', '<section end="MelisFrag" />', '"MelisFrag"'
    ) == "BODY"


def test_extract_tag_bounded_span_fails_loud_on_duplicate_begin():
    text = (
        '<section begin="MelisFrag" />A<section end="MelisFrag" />'
        '<section begin="MelisFrag" />B<section end="MelisFrag" />'
    )
    with pytest.raises(ValueError, match="MelisFrag"):
        _mod._extract_tag_bounded_span(
            text, '<section begin="MelisFrag" />', '<section end="MelisFrag" />', '"MelisFrag"'
        )


def test_extract_tag_bounded_span_fails_loud_when_end_precedes_begin():
    text = '<section end="MelisFrag" />BODY<section begin="MelisFrag" />'
    with pytest.raises(ValueError, match="before its own begin"):
        _mod._extract_tag_bounded_span(
            text, '<section begin="MelisFrag" />', '<section end="MelisFrag" />', '"MelisFrag"'
        )


def test_extract_ordinal_fine_fragments_basic_ordinals():
    span = '{{fine|(1) First.}}\n{{fine|(2) Second.}}'
    frags = _mod._extract_ordinal_fine_fragments(span)
    assert [o for o, _ in frags] == ["1", "2"]


def test_extract_ordinal_fine_fragments_normalizes_italicized_letter_suffix():
    # Real case: Melissus' own "(1''a'')" wiki-italicizes its letter suffix,
    # unlike its own plain "(6a)" two fragments later -- both spellings must
    # normalize to the same ordinal string.
    span = "{{fine|(1''a'') Restored.}}\n{{fine|(1) Real.}}\n{{fine|(6a) Inserted.}}"
    frags = _mod._extract_ordinal_fine_fragments(span)
    assert [o for o, _ in frags] == ["1a", "1", "6a"]


def test_extract_ordinal_fine_fragments_multi_block_continuation():
    # A fragment may continue across more than one {{fine|...}} block --
    # content between one ordinal-prefixed start and the next belongs to the
    # SAME fragment (real case: Anaxagoras (4), (12), (17)).
    span = '{{fine|(4) Opening.}}\n{{fine|Continuation, no ordinal.}}\n{{fine|(5) Next.}}'
    frags = _mod._extract_ordinal_fine_fragments(span)
    assert [o for o, _ in frags] == ["4", "5"]
    assert "Continuation" in dict(frags)["4"]


def test_extract_ordinal_fine_fragments_empty_span_is_hard_error():
    with pytest.raises(ValueError, match="no ordinal-prefixed"):
        _mod._extract_ordinal_fine_fragments("no fine blocks here at all")


def test_clean_ordinal_fine_fragment_strips_leading_ordinal():
    raw = "{{fine|(6a) Inserted text here.}}"
    assert _mod._clean_ordinal_fine_fragment(raw) == "Inserted text here."


def _eleatics_text(*, include_1a: bool = True, include_6a: bool = True) -> str:
    zeno_body = (
        _mod._ZENO_SECTION_START + "\n"
        '{{c|{{fine|(1)}}}}\n{{fine|If what is had no magnitude.}}\n\n'
        '{{c|{{fine|(2)}}}}\n{{fine|For if it were added.}}\n\n'
        '{{c|{{fine|(3)}}}}\n{{fine|If things are a many.}}\n'
        + _mod._ZENO_SECTION_END
    )
    ordinals = []
    if include_1a:
        ordinals.append('{{fine|(1a) Restored insertion.}}')
    ordinals.append('{{fine|(1) What was was ever.}}')
    ordinals.append('{{fine|(2) Since then it has not come into being.}}')
    if include_6a:
        ordinals.append('{{fine|(6a) Ventured insertion.}}')
    melissus_body = (
        '<section begin="MelisFrag" />' + "\n".join(ordinals) + '<section end="MelisFrag" />'
    )
    return zeno_body + "\n" + melissus_body


def test_build_eleatics_ch8_excludes_1a_and_6a_never_emitted_as_columns(monkeypatch):
    # MUST-FAIL coverage (leakage guard): (1a)/(6a) are Burnet's own
    # declared insertions with no DK number (see `_MELISSUS_EXCLUDED_
    # ORDINALS`) -- must never surface as "B1a"/"B6a" columns.
    text = _eleatics_text()
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    zeno, melissus, excluded = _mod.build_eleatics_ch8(patches=[])
    assert zeno == {
        "B1": "If what is had no magnitude.",
        "B2": "For if it were added.",
        "B3": "If things are a many.",
    }
    assert melissus == {
        "B1": "What was was ever.",
        "B2": "Since then it has not come into being.",
    }
    assert excluded == ["Restored insertion.", "Ventured insertion."]
    assert "B1a" not in melissus
    assert "B6a" not in melissus


def test_build_eleatics_ch8_fails_loud_when_declared_exclusion_missing(monkeypatch):
    text = _eleatics_text(include_1a=False)
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="_MELISSUS_EXCLUDED_ORDINALS"):
        _mod.build_eleatics_ch8(patches=[])


def _anaxagoras_text(*, include_20: bool = True) -> str:
    ordinals = [
        '{{fine|(1) All things were together.}}',
        '{{fine|(2) For air and aether.}}',
    ]
    if include_20:
        ordinals.append('{{fine|(20) Dogstar rises.}}')
    ordinals.append('{{fine|(21) From the weakness.}}')
    return '<section begin="AnaxFrag" />' + "\n".join(ordinals) + '<section end="AnaxFrag" />'


def test_build_anaxagoras_excludes_20_never_emitted_as_a_column(monkeypatch):
    text = _anaxagoras_text()
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    columns, excluded = _mod.build_anaxagoras(patches=[])
    assert columns == {
        "B1": "All things were together.",
        "B2": "For air and aether.",
        "B21": "From the weakness.",
    }
    assert excluded == ["Dogstar rises."]
    assert "B20" not in columns


def test_build_anaxagoras_fails_loud_when_declared_exclusion_missing(monkeypatch):
    text = _anaxagoras_text(include_20=False)
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: text)
    with pytest.raises(ValueError, match="_ANAXAGORAS_EXCLUDED_ORDINALS"):
        _mod.build_anaxagoras(patches=[])


# --- Micro-pass: hand-curated exact-anchor extraction ----------------------

def test_extract_micro_fine_block_matches_exactly_one():
    page = "Some prose. {{fine|And into that from which things take their rise.}} more prose."
    result = _mod._extract_micro_fine_block(page, "And into that from which", "test")
    assert result == "And into that from which things take their rise."


def test_extract_micro_fine_block_fails_loud_on_zero_matches():
    page = "{{fine|Unrelated content.}}"
    with pytest.raises(ValueError, match="matched 0"):
        _mod._extract_micro_fine_block(page, "not present anywhere", "test")


def test_extract_micro_fine_block_fails_loud_on_multiple_matches():
    page = "{{fine|Just as our soul is one.}} {{fine|Just as our soul is two.}}"
    with pytest.raises(ValueError, match="matched 2"):
        _mod._extract_micro_fine_block(page, "Just as our soul", "test")


def test_extract_micro_quoted_span_matches_exactly_one():
    page = ('Some prose "Naught happens for nothing," he said, "but everything '
            'of necessity." trailing.')
    result = _mod._extract_micro_quoted_span(
        page, '"Naught happens for nothing,"', 'of necessity."', "test"
    )
    assert result.startswith('"Naught happens for nothing,"')
    assert result.endswith('of necessity."')


def test_extract_micro_quoted_span_fails_loud_on_zero_matches():
    with pytest.raises(ValueError, match="matched 0"):
        _mod._extract_micro_quoted_span("nothing relevant here", "start phrase", "end phrase", "test")


def test_extract_micro_quoted_span_fails_loud_on_multiple_matches():
    page = (
        '"Naught happens for nothing," first passage ends with "of necessity." '
        '"Naught happens for nothing," second passage ends with "of necessity."'
    )
    with pytest.raises(ValueError, match="matched 2"):
        _mod._extract_micro_quoted_span(
            page, '"Naught happens for nothing,"', 'of necessity."', "test"
        )


def test_wave_48_builders_are_idempotent_on_pinned_fixtures(monkeypatch):
    chapter = _eleatics_text() + "\n" + _anaxagoras_text()
    micro_page = (
        "{{fine|And into that from which things take their rise, as is meet.}}\n"
        '{{fine|Just as," he said, "our soul, being air, holds us together.}}\n'
        '"Naught happens for nothing," he said, "but everything from a ground '
        'and of necessity."'
    )
    monkeypatch.setattr(_mod, "_fetch_chapter_wikitext", lambda revisions: chapter)
    monkeypatch.setattr(_mod, "_fetch_wikitext", lambda revid: micro_page)

    builders = (
        _mod.build_eleatics_ch8,
        _mod.build_anaxagoras,
        _mod.build_anaximander_micro,
        _mod.build_anaximenes_micro,
        _mod.build_leucippus_micro,
    )
    for builder in builders:
        first = builder(patches=[])
        second = builder(patches=[])
        assert json.dumps(first, ensure_ascii=False).encode("utf-8") == (
            json.dumps(second, ensure_ascii=False).encode("utf-8")
        )


def test_build_anaximander_micro_extracts_b1(monkeypatch):
    page = "prose {{fine|And into that from which things take their rise, as is meet.}} more"
    monkeypatch.setattr(_mod, "_fetch_wikitext", lambda revid: page)
    columns = _mod.build_anaximander_micro(patches=[])
    assert columns == {"B1": "And into that from which things take their rise, as is meet."}


def test_build_anaximenes_micro_extracts_b2(monkeypatch):
    page = '{{fine|Just as," he said, "our soul, being air, holds us together.}}'
    monkeypatch.setattr(_mod, "_fetch_wikitext", lambda revid: page)
    columns = _mod.build_anaximenes_micro(patches=[])
    assert columns == {"B2": 'Just as," he said, "our soul, being air, holds us together.'}


def test_build_leucippus_micro_extracts_b2(monkeypatch):
    page = ('prose. "Naught happens for nothing," he said, "but everything from a '
            'ground and of necessity." trailing.')
    monkeypatch.setattr(_mod, "_fetch_wikitext", lambda revid: page)
    columns = _mod.build_leucippus_micro(patches=[])
    assert columns == {
        "B2": '"Naught happens for nothing," he said, "but everything from a '
              'ground and of necessity."'
    }
