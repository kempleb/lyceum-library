"""Stage 1 of docs/lined-source-plan.md: Discourses' `citation.lined_source`
opt-in — one Greek spine entry per Schenkl print `<l>` instead of one
flattened entry per chapter (see stage1_greek._lined_chapter_lines /
_apply_lined_wraps, and _parse_flat_book_section's `lined` branch) — plus
docs/lined-rollout-plan.md's wave-1 extension of the same treatment to the
flat `section` scheme's six works (Enchiridion + the five Epicurus works),
via `_parse_flat_chapter`'s own lined branch and `_lined_chapter_lines`'
`section_div_type=None` mode.

Fixture-level tests cover the four named ground-truth shapes from the plan's
§1.2/§1.3 evidence (intra-section wrap, section-straddling wrap, the two
angle-bracket unjoinable lines, and the never-observed chapter-final-hyphen
case, which must raise rather than splice). The real-corpus tests run the
actual TLG export through `parse_spine` and check I1/I2/I3/I5 plus the
work-wide census (9285 lines, 2393 joined) against an INDEPENDENT re-parse of
the export XML — not a trust of the code under test.

The "Wave 1" section below repeats the same discipline for the flat scheme:
fixture-level shapes for Enchiridion's section-straddling wrap, an Epicurus
intra-column wrap, Pythocles' retained `<l n="t">` greeting (Ruling 3), and a
column-final-hyphen fixture that must raise; then real-corpus census tests
for all six wave-1 works against docs/lined-rollout-plan.md's Ruling-4 table,
plus a structural check that Discourses' `parse_spine` output is unchanged.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_greek import (
    _apply_lined_wraps,
    _fold_hyphen_final_sigma,
    _lined_chapter_lines,
    _lined_section_div,
    _lined_source_declared,
    _parse_flat_book_section,
    _parse_flat_chapter,
    _rejoin_wrapped_hyphens,
    _warn_if_lined_source_has_no_wraps,
    exported_xml_path,
    parse_spine,
)

SCHEME = scheme_mod.get("book-section")
FLAT_SCHEME = scheme_mod.get("section")


def _manifest(lined: bool = True) -> Manifest:
    citation = {"scheme": "book-section"}
    if lined:
        citation["lined_source"] = True
        # R1a (wave 2): the default became None (column div is the leaf);
        # Discourses-topology fixtures declare the sub-div type explicitly,
        # exactly as manifests/discourses.yaml now does.
        citation["lined_section_div"] = "section"
    data = {
        "work": {"id": "discourses", "tlg_author": "0557", "tlg_work": "001",
                 "greek_edition": "Fixture"},
        "citation": citation,
        "books": [{"n": 1, "start": "1.1", "end": "1.30"}],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


# --- opt-in gating --------------------------------------------------------

def test_lined_source_declared_requires_the_manifest_key():
    assert _lined_source_declared(_manifest(lined=True)) is True
    assert _lined_source_declared(_manifest(lined=False)) is False
    assert _lined_source_declared(None) is False


# --- _lined_chapter_lines / _apply_lined_wraps: the named ground-truth shapes -----

def test_intra_section_wrap_matches_1_1_section_1():
    # docs/lined-source-plan.md §1.2: <l n="1">...αὐτὴν αὑ-</l> / <l n="2">τῆς
    # θεωρητικήν...</l>, both lines inside section 1 — the word is owned by
    # the line where it starts (Q1.3) and rendered whole (Q2), wrap = the
    # character count of "αὑ" (the fragment Schenkl printed before the
    # hyphen), matching the emitted-data spec's own worked example (§3).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑ-</l>
<l n="2">τῆς θεωρητικήν.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, headers = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert headings == [] and headers == []
    assert flat == [
        {"column": "1.1", "n": 1,
         "text": "Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑτῆς",
         "sec": 1, "joined": True, "wrap": 2, "wrapO": 43},
        {"column": "1.1", "n": 2, "text": "θεωρητικήν.", "sec": 1},
    ]


def test_section_straddling_wrap_lands_the_word_on_the_earlier_section():
    # §1.2's second shape: the wrap crosses INTO the next section
    # ("ἀποδο-" / "κιμαστικήν.", §1 l.2 -> §2 l.1). Q1.3 reverses the old
    # snap: the whole word is owned by, and its `sec` is, the FIRST half's
    # section (1), not 2. wrap is computed directly from the fragment
    # Schenkl actually printed before the hyphen ("ἀποδο", 5 characters) --
    # the plan's own I3 formula and Stage 4 slice contract
    # (`t.slice(0, wrap) + "-"` must reproduce what the source page shows)
    # both pin this to 5, not the "wrap: 6" figure that appears in the plan's
    # Stage 1 acceptance-criteria prose (docs/lined-source-plan.md:479) --
    # see this file's module docstring / the task report for the full
    # arithmetic check. 0 < 5 < len("ἀποδοκιμαστικήν.")=16 satisfies I3
    # either way.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑ-</l>
<l n="2">τῆς θεωρητικήν, οὐ τοίνυν οὐδὲ δοκιμαστικὴν ἢ ἀποδο-</l>
</div>
<div type="section" n="2">
<l n="1">κιμαστικήν. ἡ γραμματικὴ μέχρι.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert flat == [
        {"column": "1.1", "n": 1,
         "text": "Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑτῆς",
         "sec": 1, "joined": True, "wrap": 2, "wrapO": 43},
        {"column": "1.1", "n": 2,
         "text": "θεωρητικήν, οὐ τοίνυν οὐδὲ δοκιμαστικὴν ἢ ἀποδοκιμαστικήν.",
         "sec": 1, "joined": True, "wrap": 5, "wrapO": 42},
        {"column": "1.1", "n": 3, "text": "ἡ γραμματικὴ μέχρι.", "sec": 2},
    ]
    # I3 bounds against the actual joined token.
    last = flat[1]["text"].rsplit(" ", 1)[-1]
    assert last == "ἀποδοκιμαστικήν."
    assert 0 < flat[1]["wrap"] < len(last)
    assert flat[1]["text"][: flat[1]["text"].index(last) + flat[1]["wrap"]] + "-" == \
        "θεωρητικήν, οὐ τοίνυν οὐδὲ δοκιμαστικὴν ἢ ἀποδο-"


def test_no_sections_key_ever_emitted_for_a_lined_chapter():
    # I5: lined_source retires the `sections` standoff channel entirely --
    # _chapter_sections must never be called for a lined chapter, even when
    # the chapter nests 2+ sections (which would normally trigger it under
    # section_paragraphs).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><l n="1">Alpha.</l></div>
<div type="section" n="2"><l n="1">Beta.</l></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert all("sections" not in f for f in flat)
    assert [f["sec"] for f in flat] == [1, 2]


def test_interrupted_column_fragments_merge_with_continuous_n():
    # Lives shape (wave 2): one citable column arrives as TWO leaf divs
    # with the same @n (a section interrupted by a philosopher-heading
    # stub, or the lettered_fragments remap). Fragments must merge into
    # one column with `n` numbered continuously (I1), and the wrap pass
    # must run once over the ASSEMBLED column — a hyphen at the
    # interruption point is an ordinary in-column wrap, never a spurious
    # column-final one.
    data = {
        "work": {"id": "lives-fixture", "tlg_author": "0004",
                 "tlg_work": "001", "greek_edition": "Fixture"},
        "citation": {"scheme": "book-section", "lined_source": True},
        "books": [{"n": 1, "start": "1.1", "end": "1.9"}],
    }
    manifest = Manifest(data, ROOT / "manifests" / "fake.yaml")
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="5">
<l n="1">Τὸ πρῶτον μέρος τῆς το-</l>
</div>
<div type="chapter" n="5">
<l n="1">μῆς ἕπεται.</l>
<l n="2">Δεύτερος στίχος.</l>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, headers = _parse_flat_book_section(tree, SCHEME, manifest)
    assert headings == [] and headers == []
    assert [(e["column"], e["n"]) for e in flat] == [
        ("1.5", 1), ("1.5", 2), ("1.5", 3),
    ]
    # the interruption-point hyphen rejoined as an ordinary in-column wrap
    assert flat[0]["text"].endswith("τομῆς")
    assert flat[0]["joined"] is True and flat[0]["wrap"] == 2
    assert flat[1]["text"] == "ἕπεται."
    assert flat[2]["text"] == "Δεύτερος στίχος."


def test_two_real_unjoinable_angle_bracket_lines_stay_unjoined():
    # §1.3: the two corpus-wide exceptions whose continuation is an
    # editorial angle bracket, not a lowercase Greek letter -- must keep
    # their literal hyphen, carry no `joined`/`wrap`, and must NOT raise.
    # Real locations: 1.2 sec 3 l.1 "...ἀπάγξα-" -> "<σθαι οὐ>κ...", and
    # 2.5 sec 17 l.1 "...βάλ-" -> "<λ>ωμεν...".
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="2">
<div type="section" n="3">
<l n="1">μαθόντες ὅτι εὔλογόν ἐστιν. Τὸ δ' ἀπάγξα-</l>
<l n="2">&lt;σθαι οὐ&gt;κ ἔστιν ἀφόρητον;</l>
</div>
</div>
<div type="chapter" n="5">
<div type="section" n="17">
<l n="1">ἂν δὲ μετὰ ταραχῆς καὶ φόβου δεχώμεθα ἢ βάλ-</l>
<l n="2">&lt;λ&gt;ωμεν αὐτό.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    by_col = {f["column"]: f for f in flat if f["n"] == 1}
    assert by_col["1.2"]["text"].endswith("ἀπάγξα-")
    assert "joined" not in by_col["1.2"] and "wrap" not in by_col["1.2"]
    assert by_col["1.5"]["text"].endswith("βάλ-")
    assert "joined" not in by_col["1.5"] and "wrap" not in by_col["1.5"]
    cont1 = next(f for f in flat if f["column"] == "1.2" and f["n"] == 2)
    assert cont1["text"] == "<σθαι οὐ>κ ἔστιν ἀφόρητον;"
    cont2 = next(f for f in flat if f["column"] == "1.5" and f["n"] == 2)
    assert cont2["text"] == "<λ>ωμεν αὐτό."


def test_chapter_final_hyphen_wrap_candidate_raises_not_splices():
    # A wrap-candidate hyphen on the LAST <l> of a chapter has no successor
    # within the column to join with. §1.3's census found zero of these in
    # the real corpus, but the code must refuse loudly rather than silently
    # dropping the hyphen or reaching into the next chapter -- a wrap can
    # never cross a column boundary.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Τέλος τοῦ λόγου ἀτελὲς μέν, ἀλλ' ἀναγ-</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="chapter-final"):
        _parse_flat_book_section(tree, SCHEME, _manifest())


def test_apply_lined_wraps_raises_naming_the_column_directly():
    lines = [{"n": 1, "text": "λόγος ἀναγ-", "sec": 1}]
    with pytest.raises(ValueError, match=r"1\.9"):
        _apply_lined_wraps("1.9", lines)


def test_apply_lined_wraps_counts_wrap_from_the_words_first_greek_letter():
    # An opening curly quote glued to the wrapped word must not count into
    # `wrap` (17 real loci, e.g. 'λέγειν ‘Συμβήσε-' at tlg0557001.xml:1295):
    # the token's surface starts at the first Greek letter, and the reader
    # slices the token — wrap 8 would repaint Schenkl's Συμβήσε-/ταί split
    # as Συμβήσετ-/αί (verifier check-4 catch, 2026-08-29).
    lines = [
        {"n": 1, "text": "λέγειν ‘Συμβήσε-", "sec": 1},
        {"n": 2, "text": "ταί τινα κακά.", "sec": 1},
    ]
    _apply_lined_wraps("1.4", lines)
    assert lines[0]["joined"] is True
    assert lines[0]["wrap"] == len("Συμβήσε")
    assert lines[0]["text"] == "λέγειν ‘Συμβήσεταί"
    assert lines[1]["text"] == "τινα κακά."


def test_apply_lined_wraps_emits_wrapo_uniformly_on_an_ordinary_wrap():
    # docs/lined-source-plan.md §3's 2026-08-29 wrapO deviation: `wrapO` is
    # emitted on EVERY joined line, uniformly -- not only the em-dash glob
    # shape below. Here the wrapped word IS the line's last (and only)
    # token, so wrapO happens to equal the last token's own offset too.
    lines = [
        {"n": 1, "text": "Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑ-", "sec": 1},
        {"n": 2, "text": "τῆς θεωρητικήν.", "sec": 1},
    ]
    _apply_lined_wraps("1.1", lines)
    assert lines[0]["wrap"] == 2
    assert lines[0]["wrapO"] == len("Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν ")
    assert lines[0]["text"][lines[0]["wrapO"] :] == "αὑτῆς"


def test_apply_lined_wraps_em_dash_glob_wrapo_names_the_wrapped_token_not_the_last():
    # The real defect (epicurus-letter-to-herodotus §53/§69 -- the only two
    # corpus sites, caught by preflight on the first wave-1 full build): the
    # source glues an em dash straight onto the next word with NO space
    # ("σθαι—πολλὴν"), so whole-whitespace-token absorption (I4) pulls BOTH
    # words onto this line -- "πολλὴν" becomes the line's LAST token, not
    # the wrapped "σχηματίζεσθαι". `wrapO` must still point at the wrapped
    # word's own start, not wherever the absorbed line's last word landed
    # -- this is exactly why "wrapped token = last token" is false here and
    # wrapO must name the token explicitly (docs/lined-source-plan.md §3's
    # 2026-08-29 deviation note).
    lines = [
        {"n": 1, "text": "τῶν ὁμογενῶν σχηματίζε-", "sec": 53},
        {"n": 2, "text": "σθαι—πολλὴν γὰρ ῥεῖ.", "sec": 53},
    ]
    _apply_lined_wraps("53", lines)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "τῶν ὁμογενῶν σχηματίζεσθαι—πολλὴν"
    assert lines[0]["wrap"] == len("σχηματίζε")
    assert lines[0]["wrapO"] == len("τῶν ὁμογενῶν ")
    # The wrapped word is NOT the whole of the last whitespace-delimited
    # chunk of the absorbed text -- "πολλὴν" rides along glued to it.
    assert lines[0]["text"].rsplit(" ", 1)[-1] == "σχηματίζεσθαι—πολλὴν"
    assert lines[1]["text"] == "γὰρ ῥεῖ."


def test_apply_lined_wraps_keeps_an_opening_siglum_in_the_wrap_count():
    # Editorial sigla are PART of the token surface ("<ἀναισχυντία>"), so a
    # wrapped word opening with "<" counts the bracket into `wrap` — unlike
    # a glued quote, which tokenization strips (4 real loci, e.g. 2.9 §12
    # "τὸν ἀναίσχυντον <ἀναι-" / "σχυντία>, τὸν ἄπιστον").
    lines = [
        {"n": 1, "text": "τὸν ἀναίσχυντον <ἀναι-", "sec": 12},
        {"n": 2, "text": "σχυντία>, τὸν ἄπιστον", "sec": 12},
    ]
    _apply_lined_wraps("2.9", lines)
    assert lines[0]["joined"] is True
    assert lines[0]["wrap"] == len("<ἀναι")
    assert lines[0]["text"] == "τὸν ἀναίσχυντον <ἀναισχυντία>,"
    assert lines[1]["text"] == "τὸν ἄπιστον"


# --- sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29) -----
# Every Teubner/Schenkl print-line wrap-hyphen is preceded by the LINE-FINAL
# form of sigma (ς), a typographic convention -- even when the sigma sits in
# MEDIAL position once the word is rejoined ("προς-" / "ήκει" for the single
# word προσήκει). No Greek word contains a medial ς, so every rejoin site
# must fold that character back to the ordinary σ. `_fold_hyphen_final_sigma`
# is the one place this rule is written; these tests cover it directly, then
# both rejoin paths (lined `_apply_lined_wraps` and flattened
# `_rejoin_wrapped_hyphens`) that call it.

def test_fold_hyphen_final_sigma_converts_final_to_medial():
    assert _fold_hyphen_final_sigma("ς") == "σ"


def test_fold_hyphen_final_sigma_leaves_medial_sigma_unchanged():
    assert _fold_hyphen_final_sigma("σ") == "σ"


def test_fold_hyphen_final_sigma_leaves_other_letters_unchanged():
    for ch in ["α", "ν", "ρ", "ω", "π", "-"]:
        assert _fold_hyphen_final_sigma(ch) == ch


def test_apply_lined_wraps_folds_final_sigma_through_a_closing_siglum():
    lines = [
        {"n": 1, "text": "ἐν προ<ς>-", "sec": 11},
        {"n": 2, "text": "θέσει καὶ ἐποχῇ", "sec": 12},
    ]
    _apply_lined_wraps("1.4", lines)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "ἐν προ<σ>θέσει"
    assert lines[1]["text"] == "καὶ ἐποχῇ"


def test_apply_lined_wraps_folds_a_line_final_sigma_before_the_wrap_hyphen():
    # Minimal analog of the real corpus locus (enchiridion ch.31 §5): Schenkl
    # prints "...ὧν προς-" / "ήκει ἐπιμελεῖσθαι." -- the fold must convert the
    # ς the print convention put before the hyphen back to medial σ, giving
    # the real Greek word προσήκει, not the impossible "προςήκει".
    lines = [
        {"n": 1, "text": "δεῖ γινώσκειν ὧν προς-", "sec": 5},
        {"n": 2, "text": "ήκει ἐπιμελεῖσθαι.", "sec": 5},
    ]
    _apply_lined_wraps("31", lines)
    assert lines[0]["joined"] is True
    assert lines[0]["text"] == "δεῖ γινώσκειν ὧν προσήκει"
    assert lines[1]["text"] == "ἐπιμελεῖσθαι."
    # Stage 4's repaint contract (I3/Q2): slicing the stored token at
    # [wrapO, wrapO+wrap) recovers the fragment Schenkl printed on THIS line,
    # once a TRAILING σ in that slice is folded back to ς for display (the
    # reader's own `splitWrapLine`/`foldTrailingSigmaForDisplay` in
    # shared/lib/speakers.ts does exactly this).
    wrapO, wrap = lines[0]["wrapO"], lines[0]["wrap"]
    fragment = lines[0]["text"][wrapO : wrapO + wrap]
    assert fragment == "προσ"
    painted = (fragment[:-1] + "ς" if fragment.endswith("σ") else fragment) + "-"
    assert painted == "προς-"


def test_rejoin_wrapped_hyphens_folds_a_line_final_sigma_before_the_wrap_hyphen():
    # Same convention, in the FLATTENED (non-lined) rejoin path shared by
    # numeric_section/flat_numeric works and DK's own per-block call: a
    # literal "- " surviving inside one flattened chapter string (per this
    # function's own docstring) folds the same way.
    assert _rejoin_wrapped_hyphens("ὧν προς- ήκει ἐπιμελεῖσθαι.") == "ὧν προσήκει ἐπιμελεῖσθαι."


def test_rejoin_wrapped_hyphens_leaves_a_genuine_medial_sigma_alone():
    # A word that already has the correct medial σ before some OTHER "-"
    # that isn't a wrap-hyphen match at all (uppercase/punctuation
    # continuation) is never touched -- the fold only ever fires exactly
    # where a rejoin actually happens.
    assert _rejoin_wrapped_hyphens("προσήκει σοι.") == "προσήκει σοι."


def test_apply_lined_wraps_raises_on_a_chained_three_line_wrap():
    # A word spanning THREE print lines (the absorbed continuation itself
    # ends in a wrap hyphen). Zero exist in the corpus (plan §1.3 census);
    # silently absorbing would mangle the line and could hide a
    # chapter-final wrap behind a fully-absorbed last line — must refuse
    # (adversarial-review WARN, 2026-08-29).
    lines = [
        {"n": 1, "text": "τὸ πρᾶγμα ἀπο-", "sec": 1},
        {"n": 2, "text": "δο-", "sec": 1},
        {"n": 3, "text": "κιμαστικὸν λέγεται.", "sec": 1},
    ]
    with pytest.raises(ValueError, match="chained"):
        _apply_lined_wraps("2.7", lines)


# --- non-lined fixture: byte-identical to the pre-feature flatten -----------

def test_non_lined_fixture_work_is_byte_identical_to_the_flattened_shape():
    # A work whose manifest does NOT declare `lined_source` (every other
    # book-section work, e.g. Meditations) must take the old single-
    # flattened-line-per-chapter branch exactly as before -- gated
    # structurally, not by shape (the same chapter shape as the wrap tests
    # above, but manifest=None here).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑ-</l>
<l n="2">τῆς θεωρητικήν.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, headings, headers = _parse_flat_book_section(tree, SCHEME, None)
    assert headings == [] and headers == []
    assert flat == [
        {"column": "1.1", "n": 1,
         "text": "Τῶν ἄλλων δυνάμεων οὐδεμίαν εὑρήσετε αὐτὴν αὑτῆς θεωρητικήν."}
    ]
    assert "sec" not in flat[0] and "wrap" not in flat[0] and "joined" not in flat[0]


def test_manifest_declaring_lined_source_false_takes_the_old_branch_too():
    manifest = _manifest(lined=False)
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1"><l n="1">Alpha.</l></div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, manifest)
    assert flat == [{"column": "1.1", "n": 1, "text": "Alpha."}]


# --- parse_spine: sec/wrap survive the copied-key list ----------------------

def test_parse_spine_copies_sec_and_wrap_onto_segment_lines():
    # Same wrap pair as test_stage1_book_section.py's own hyphen-rejoin
    # regression ("ὃν οὔτ' ἀναγ-" / "κάσαι ἔστιν." -> "...ἀναγκάσαι ἔστιν."),
    # here checked end-to-end through parse_spine's copied-key list rather
    # than the flattened-chapter branch.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">ὃν οὔτ' ἀναγ-</l>
<l n="2">κάσαι ἔστιν.</l>
</div>
</div>
</div>
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
    lines = spine["segments"][0]["lines"]
    assert lines == [
        {"n": 1, "text": "ὃν οὔτ' ἀναγκάσαι", "sec": 1, "joined": True, "wrap": 4, "wrapO": 8},
        {"n": 2, "text": "ἔστιν.", "sec": 1},
    ]


# --- indent: paragraph-opening first-line inset (John's ruling 2026-08-29) --

def test_indent_captured_on_a_rend_indent_line():
    # docs/lined-source-plan.md addendum: <l rend="indent(1)"> is Schenkl's
    # own paragraph-opening first-line inset. Captured as `indent: 1` on
    # exactly that line; every other line in the same section carries no
    # `indent` key at all.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1" rend="indent(1)">Τῶν ἄλλων δυνάμεων.</l>
<l n="2">τῆς θεωρητικήν.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert flat == [
        {"column": "1.1", "n": 1, "text": "Τῶν ἄλλων δυνάμεων.", "sec": 1, "indent": 1},
        {"column": "1.1", "n": 2, "text": "τῆς θεωρητικήν.", "sec": 1},
    ]


def test_indent_levels_2_and_3_captured_for_quoted_inset_matter():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Ordinary line.</l>
<l n="2" rend="indent(2)">Quoted, level two.</l>
<l n="3" rend="indent(3)">Quoted, level three.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert "indent" not in flat[0]
    assert flat[1]["indent"] == 2
    assert flat[2]["indent"] == 3


def test_indent_not_tied_to_section_boundaries():
    # indent(N) marks a print-line inset wherever Schenkl set one -- it is
    # not derived from, and need not coincide with, a section's own first
    # line (a section can open with no indent, or carry an indented line
    # mid-section for inset/quoted matter).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1">Section-opening line, no indent.</l>
<l n="2" rend="indent(1)">A later line carries the inset.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    flat, _, _ = _parse_flat_book_section(tree, SCHEME, _manifest())
    assert "indent" not in flat[0]
    assert flat[1]["indent"] == 1


def test_indent_unrecognized_rend_value_raises():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1" rend="bogus">Alpha.</l>
</div>
</div>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="unrecognized"):
        _parse_flat_book_section(tree, SCHEME, _manifest())


def test_parse_spine_copies_indent_onto_segment_lines():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1">
<div type="section" n="1">
<l n="1" rend="indent(1)">Alpha.</l>
<l n="2">Beta.</l>
</div>
</div>
</div>
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
    lines = spine["segments"][0]["lines"]
    assert lines == [
        {"n": 1, "text": "Alpha.", "sec": 1, "indent": 1},
        {"n": 2, "text": "Beta.", "sec": 1},
    ]


def test_parse_spine_never_emits_indent_for_a_non_lined_work():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1"><div type="section" n="1"><p>Alpha.</p></div></div>
</div>
</body></text></TEI>"""
    )
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        path = Path(f.name)
    try:
        spine = parse_spine(path, _manifest(lined=False))
    finally:
        path.unlink()
    line = spine["segments"][0]["lines"][0]
    assert "indent" not in line


def test_parse_spine_never_emits_sec_or_wrap_for_a_non_lined_work():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Book" n="1">
<div type="chapter" n="1"><div type="section" n="1"><p>Alpha.</p></div></div>
</div>
</body></text></TEI>"""
    )
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        path = Path(f.name)
    try:
        spine = parse_spine(path, _manifest(lined=False))
    finally:
        path.unlink()
    line = spine["segments"][0]["lines"][0]
    assert "sec" not in line and "wrap" not in line


# ============================================================================
# Wave 1 (docs/lined-rollout-plan.md): the flat `section` scheme's
# `_parse_flat_chapter` lined branch. Fixtures use `<div type="Chapter">`
# (the scheme's default `page_div_type`, matching test_stage1_section.py's
# existing fixtures) — the five Epicurus works' own div-type override
# ("Section"/"Fragment", via citation.div_types.page) is orthogonal to the
# lined-branch logic under test here, which only cares about the CHAPTER
# div's children, not its own type name.
# ============================================================================

def _flat_manifest(lined_section_div: str | None = None, lined: bool = True) -> Manifest:
    citation = {"scheme": "section"}
    if lined:
        citation["lined_source"] = True
    if lined_section_div is not None:
        citation["lined_section_div"] = lined_section_div
    data = {
        "work": {"id": "wave1-fixture", "tlg_author": "0000", "tlg_work": "000",
                 "greek_edition": "Fixture"},
        "citation": citation,
        "books": [],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def test_lined_section_div_reads_the_manifest_key():
    assert _lined_section_div(_flat_manifest(lined_section_div="section")) == "section"
    assert _lined_section_div(_flat_manifest(lined_section_div=None)) is None
    assert _lined_section_div(None) is None


def test_epicurus_style_intra_column_wrap_is_rejoined_with_no_sec():
    # No lined_section_div: the column div (here "Chapter", standing in for
    # an Epicurus "Section"/"Fragment") IS the leaf -- _lined_chapter_lines
    # walks its own <l> children directly and stamps no `sec` at all
    # (Ruling 1c).
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="35">
<l n="1">Τοῖς μὴ δυναμένοις ἕκαστα τῶν περὶ φύσεως ἀναγε-</l>
<l n="2">γραμμένων ἡμῖν ἀκριβοῦν.</l>
</div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest())
    assert headings == []
    assert len(flat) == 2
    l1, l2 = flat
    assert l1["column"] == l2["column"] == "35"
    assert "sec" not in l1 and "sec" not in l2
    assert l1["n"] == 1 and l2["n"] == 2
    assert l1["joined"] is True
    assert l1["text"] == "Τοῖς μὴ δυναμένοις ἕκαστα τῶν περὶ φύσεως ἀναγεγραμμένων"
    assert l2["text"] == "ἡμῖν ἀκριβοῦν."
    # wrap = len("ἀναγε") -- the fragment Schenkl/Arrighetti printed on the
    # first line, before the hyphen.
    assert l1["wrap"] == len("ἀναγε")


def test_enchiridion_style_section_straddling_wrap_lands_on_the_earlier_section():
    # lined_section_div="section": the Chapter nests <div type="section">
    # sub-divisions (Enchiridion's own shape) and each emitted line carries
    # `sec` -- a wrap can straddle the section boundary (mirrors Discourses'
    # own section-straddling case) and the word still lands on the line
    # where it STARTS, per Q1.3/Ruling 1.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="5">
<div type="section" n="1"><l n="1">πρῶτον μὲν μηδὲν ἐπὶ τῇ ὁρμῇ ται-</l></div>
<div type="section" n="2"><l n="1">νιώδης εἶναι.</l></div>
</div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest(lined_section_div="section"))
    assert headings == []
    assert len(flat) == 2
    l1, l2 = flat
    assert l1["column"] == l2["column"] == "5"
    assert l1["sec"] == 1 and l2["sec"] == 2
    assert l1["joined"] is True
    assert l1["text"] == "πρῶτον μὲν μηδὲν ἐπὶ τῇ ὁρμῇ ταινιώδης"
    assert l2["text"] == "εἶναι."
    assert l1["wrap"] == len("ται")


def test_pythocles_style_l_n_t_greeting_retained_as_first_body_line():
    # Ruling 3: an <l n="t"> INSIDE a numbered column's own div (unlike a
    # dedicated top-level n="t" div, which _parse_flat_chapter drops via
    # citation.title_labels) is an ordinary body line -- never skipped, kept
    # as line 1, no `indent`. Removing it would delete real corpus text,
    # which I4 forbids.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="84">
<l n="t">Ἐπίκουρος Πυθοκλεῖ χαίρειν. </l>
<l n="1">τὴν περὶ τῶν μετεώρων μάθησιν...</l>
</div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest())
    assert headings == []
    assert len(flat) == 2
    greeting = flat[0]
    assert greeting["column"] == "84"
    assert greeting["n"] == 1
    assert greeting["text"] == "Ἐπίκουρος Πυθοκλεῖ χαίρειν."
    assert "indent" not in greeting
    assert "sec" not in greeting


def test_flat_scheme_column_final_hyphen_wrap_candidate_raises():
    # No successor line to join with within the column -- the real corpus
    # census found zero of these across all six wave-1 works (Rule 0's own
    # evidence: column-final wraps = 0 for all six, since the column IS the
    # leaf and a genuine column-final wrap would mean the print edition
    # split a word across two separate citable units). Must raise, never
    # silently drop the hyphen or splice across columns.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1">
<l n="1">τελευταῖον ῥῆ-</l>
</div>
<div type="Chapter" n="2">
<l n="1">Ἄλλο.</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match=r"1: .*no continuation"):
        _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest())


def test_flat_scheme_non_lined_fixture_byte_identical_to_the_flattened_shape():
    # Acceptance: a flat work WITHOUT lined_source is untouched -- same
    # single-flattened-entry-per-chapter shape _parse_flat_chapter has
    # always produced (see test_stage1_section.py, unaffected by this
    # change), byte-identical.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1">
<l n="1">Τοῖς μὴ δυναμένοις</l>
<l n="2">ἕκαστα ἀκριβοῦν.</l>
</div>
</body></text></TEI>"""
    )
    flat, headings = _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest(lined=False))
    assert headings == []
    assert flat == [{"column": "1", "n": 1, "text": "Τοῖς μὴ δυναμένοις ἕκαστα ἀκριβοῦν."}]
    assert "sec" not in flat[0] and "wrap" not in flat[0] and "joined" not in flat[0]


def test_warn_if_lined_source_has_no_wraps_prints_when_zero_joined(capsys):
    _warn_if_lined_source_has_no_wraps("some-work", [{"n": 1, "text": "a"}, {"n": 2, "text": "b"}])
    out = capsys.readouterr().out
    assert "stage1 WARNING: some-work: lined_source declared" in out


def test_warn_if_lined_source_has_no_wraps_silent_when_any_joined(capsys):
    _warn_if_lined_source_has_no_wraps(
        "some-work", [{"n": 1, "text": "a", "joined": True, "wrap": 1}, {"n": 2, "text": "b"}]
    )
    out = capsys.readouterr().out
    assert out == ""


def test_parse_flat_chapter_warns_when_a_lined_work_has_zero_wraps(capsys):
    # Rule 0's machine enforcement, exercised through the real call site --
    # a lined_source work whose whole emission joins nothing prints the
    # WARNING naming the work id, not a FATAL.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="Chapter" n="1"><l n="1">Alpha beta.</l></div>
<div type="Chapter" n="2"><l n="1">Gamma delta.</l></div>
</body></text></TEI>"""
    )
    _parse_flat_chapter(tree, FLAT_SCHEME, _flat_manifest())
    out = capsys.readouterr().out
    assert "stage1 WARNING: wave1-fixture: lined_source declared" in out


# ============================================================================
# Real-corpus integration: build/export/.../tlg0557001.xml through
# parse_spine, checked against an INDEPENDENT re-parse of the same XML (not
# a trust of the code under test). Skipped when the export isn't present
# (a from-scratch checkout with no Diogenes export cached).
# ============================================================================

DISCOURSES_MANIFEST_PATH = ROOT / "manifests" / "discourses.yaml"


def _real_manifest() -> Manifest:
    return Manifest.load(DISCOURSES_MANIFEST_PATH)


def _real_xml_path() -> Path:
    return exported_xml_path(_real_manifest())


requires_export = pytest.mark.skipif(
    not _real_xml_path().exists(),
    reason="Diogenes TLG export not present at build/export/... — run "
           "`uv run python -m reader_pipeline --work discourses stage1` once "
           "(or the full pipeline) to populate it before this test can run",
)


_SECTION_N_RE = re.compile(r"^(\d+)(?:,(\d+))?$")


def _independent_expected() -> dict[str, tuple[int, list[int]]]:
    """{column: (body <l> count, distinct TLG section @n in document order)}
    from a fresh, from-scratch walk of the export XML -- deliberately not
    calling any stage1_greek helper, so this is a real cross-check rather
    than the code under test grading its own homework."""
    tree = etree.parse(str(_real_xml_path()))
    root = tree.getroot()
    out: dict[str, tuple[int, list[int]]] = {}
    for book in root.iter("{*}div"):
        if book.get("type") != "Book":
            continue
        book_n = book.get("n")
        for chap in book:
            if chap.get("type") != "chapter":
                continue
            column = f"{book_n}.{chap.get('n')}"
            count = 0
            secs: list[int] = []
            for sec in chap:
                if etree.QName(sec).localname != "div" or sec.get("type") != "section":
                    continue
                n_raw = sec.get("n")
                if n_raw == "t":
                    continue
                m = _SECTION_N_RE.match(n_raw or "")
                secs.append(int(m.group(1)))
                count += len([l for l in sec if etree.QName(l).localname == "l"])
            out[column] = (count, secs)
    return out


@pytest.fixture(scope="module")
def real_spine():
    return parse_spine(_real_xml_path(), _real_manifest())


@requires_export
def test_real_corpus_global_line_and_joined_counts(real_spine):
    total_lines = sum(len(s["lines"]) for s in real_spine["segments"])
    joined = sum(1 for s in real_spine["segments"] for l in s["lines"] if l.get("joined"))
    assert total_lines == 9285
    # wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
    assert joined == 2393
    assert len(real_spine["segments"]) == 95


@requires_export
def test_real_corpus_i1_n_is_dense_1_to_len_per_segment(real_spine):
    for seg in real_spine["segments"]:
        assert [l["n"] for l in seg["lines"]] == list(range(1, len(seg["lines"]) + 1)), seg["column"]


@requires_export
def test_real_corpus_i2_sec_matches_an_independent_xml_walk(real_spine):
    expected = _independent_expected()
    for seg in real_spine["segments"]:
        exp_count, exp_secs = expected[seg["column"]]
        assert len(seg["lines"]) == exp_count, seg["column"]
        got_secs: list[int] = []
        for l in seg["lines"]:
            if not got_secs or got_secs[-1] != l["sec"]:
                got_secs.append(l["sec"])
        assert got_secs == exp_secs, seg["column"]
        secvals = [l["sec"] for l in seg["lines"]]
        assert secvals == sorted(secvals), seg["column"]  # non-decreasing


@requires_export
def test_real_corpus_i3_wrap_bounds_and_text_endswith_last_word(real_spine):
    checked = 0
    for seg in real_spine["segments"]:
        for l in seg["lines"]:
            if not l.get("joined"):
                assert "wrap" not in l
                continue
            checked += 1
            last = l["text"].rsplit(" ", 1)[-1]
            assert 0 < l["wrap"] < len(last), (seg["column"], l["n"])
            assert l["text"].endswith(last)
    # wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
    assert checked == 2393


@requires_export
def test_real_corpus_wrapo_present_uniformly_and_names_the_last_token_for_discourses(real_spine):
    # wrapO deviation (2026-08-29, docs/lined-source-plan.md §3): emitted
    # uniformly on every joined line (not only the em-dash glob shape,
    # which Discourses has zero of -- unlike the Epicurus wave-1 corpus,
    # docs/lined-rollout-plan.md's "no such em-dash glob in Discourses"
    # claim). For every one of Discourses' 2393 joined lines, `wrapO` must
    # point at the START of the line's own LAST whitespace-delimited word
    # -- i.e. "wrapped token = last token" stays true here; wrapO merely
    # makes that fact explicit rather than assumed, so this suite's
    # unmodified assertions above (I3 bounds against `last`) stay correct.
    checked = 0
    for seg in real_spine["segments"]:
        for l in seg["lines"]:
            if not l.get("joined"):
                assert "wrapO" not in l
                continue
            checked += 1
            assert isinstance(l["wrapO"], int) and l["wrapO"] >= 0
            last = l["text"].rsplit(" ", 1)[-1]
            # `last.endswith(...)` rather than `==`: a glued opening quote
            # (17 real loci, e.g. 'λέγειν ‘Συμβήσεταί' -- see
            # `_apply_lined_wraps`' own glued-quote skip) is part of the
            # whitespace-delimited `last` but NOT part of the wrapped
            # token's own surface, so `wrapO` correctly starts one
            # character later than `last` does. `wrapO` is still the
            # start of THIS line's own last real word either way.
            assert last.endswith(l["text"][l["wrapO"] :]), (seg["column"], l["n"])
    # wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
    assert checked == 2393


@requires_export
def test_real_corpus_i5_no_line_ever_carries_both_sec_and_sections(real_spine):
    for seg in real_spine["segments"]:
        for l in seg["lines"]:
            assert not ("sec" in l and "sections" in l)


@requires_export
def test_real_corpus_two_named_unjoinable_lines(real_spine):
    seg12 = next(s for s in real_spine["segments"] if s["column"] == "1.2")
    line = next(l for l in seg12["lines"] if l["sec"] == 3 and l["text"].endswith("-"))
    assert line["text"].endswith("ἀπάγξα-")
    assert "joined" not in line and "wrap" not in line

    seg25 = next(s for s in real_spine["segments"] if s["column"] == "2.5")
    line = next(l for l in seg25["lines"] if l["sec"] == 17 and l["text"].endswith("-"))
    assert line["text"].endswith("βάλ-")
    assert "joined" not in line and "wrap" not in line


@requires_export
def test_real_corpus_indent_totals(real_spine):
    # docs/lined-source-plan.md addendum (John's ruling 2026-08-29):
    # 390/53/4 indent(1)/(2)/(3) <l> work-wide, verified by an independent
    # probe of tlg0557001.xml (see this file's report / the plan addendum).
    from collections import Counter

    counts: Counter = Counter()
    for seg in real_spine["segments"]:
        for l in seg["lines"]:
            if "indent" in l:
                counts[l["indent"]] += 1
    assert counts == {1: 390, 2: 53, 3: 4}


@requires_export
def test_real_corpus_1_1_indent_spot_check(real_spine):
    # docs/lined-source-plan.md addendum: 1.1's opening indent(1) lines are
    # exactly its sections 1, 7, 10, 14, 18, 21, 26, 28 -- each section's
    # OWN first line (verified independently against the export XML).
    seg = next(s for s in real_spine["segments"] if s["column"] == "1.1")
    section_first_line: dict[int, dict] = {}
    for l in seg["lines"]:
        section_first_line.setdefault(l["sec"], l)
    indented_sections = {sec for sec, l in section_first_line.items() if l.get("indent") == 1}
    assert indented_sections == {1, 7, 10, 14, 18, 21, 26, 28}
    # And no OTHER line of 1.1 (mid-section) carries an indent at all.
    for l in seg["lines"]:
        if l is section_first_line[l["sec"]]:
            continue
        assert "indent" not in l


@requires_export
def test_real_corpus_i4_round_trip_reproduces_the_prechange_flatten(real_spine):
    # I4: joining a segment's line texts with single spaces -- SKIPPING any
    # line whose `text` is empty (a hyphen-wrapped word whose entire
    # continuation IS the whole of the next physical line leaves that line
    # with nothing of its own; it is still emitted as its own `n` entry, per
    # the positional next-line contract Stage 4's renderer relies on for
    # `wrap`, but it contributes no separating space of its own -- 18 such
    # lines exist in the real corpus) -- reproduces the PRE-CHANGE flattened
    # chapter text byte-for-byte MODULO SIGMA (sigma-fold correction,
    # docs/lined-source-plan.md §3, 2026-08-29 -- see below), with NO further
    # wrap-rejoin step needed: our emitted lines already carry every
    # hyphen-wrapped word whole, so `_rejoin_wrapped_hyphens` applied on top
    # is a verified no-op (the only two remaining literal hyphens are §1.3's
    # angle-bracket lines, whose continuation was never lowercase Greek and
    # which `_rejoin_wrapped_hyphens` itself therefore also leaves
    # untouched).
    from reader_pipeline.stage1_greek import _rejoin_wrapped_hyphens

    snapshot_dir = Path(
        "/private/tmp/claude-501/-Users-johnboyer-Developer-classical-philosophy-reader/"
        "459257c0-dd2c-4cf8-b980-ecb727e0a6d0/scratchpad/discourses-prechange"
    )
    if not snapshot_dir.exists():
        pytest.skip("pre-change discourses dist snapshot not present")
    pre: dict[str, str] = {}
    for f in sorted(snapshot_dir.glob("book-0*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for seg in doc["segments"]:
            pre[seg["column"]] = seg["greek"][0]["text"]

    # Sigma-fold amendment: this snapshot was captured BEFORE the sigma-wrap
    # fix landed, so it still carries the medial-ς orthographic bug at every
    # locus the fix corrects (Discourses: 30 loci in 24 distinct chapters,
    # some chapters carrying more than one -- verified by direct corpus
    # scan). A byte-exact comparison would demand reproducing that bug, which
    # defeats the point of fixing it -- fold both sides' ς to σ before
    # comparing (a pure single-character substitution, so it changes no
    # other content and cannot mask an unrelated divergence).
    def _fold_sigma(s: str) -> str:
        return s.replace("ς", "σ")

    checked = 0
    sigma_folded_segments = 0
    sigma_folded_loci = 0
    for seg in real_spine["segments"]:
        old = pre.get(seg["column"])
        assert old is not None, seg["column"]
        declared_r4c_join = {
            "1.4": ("προ<ς>- θέσει", "προ<σ>θέσει"),
            "3.10": ("πυρέ<ς>- σοντα", "πυρέ<σ>σοντα"),
        }.get(seg["column"])
        if declared_r4c_join:
            # wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
            before, after = declared_r4c_join
            assert old.count(before) == 1, seg["column"]
            old = old.replace(before, after)
        reconstructed = " ".join(l["text"] for l in seg["lines"] if l["text"])
        if reconstructed != old:
            assert _fold_sigma(reconstructed) == _fold_sigma(old), seg["column"]
            sigma_folded_segments += 1
            sigma_folded_loci += sum(
                1 for i, ch in enumerate(reconstructed)
                if ch == "σ" and i < len(old) and old[i] == "ς"
            )
        # Reapplying the wrap-rejoin on top is a no-op, as claimed above.
        assert _rejoin_wrapped_hyphens(reconstructed) == reconstructed
        checked += 1
    assert checked == 95
    assert sigma_folded_segments == 24
    assert sigma_folded_loci == 30


_MEDIAL_SIGMA_RE = re.compile(r"ς(?=\w)", re.UNICODE)


def _medial_sigma_loci(segments) -> list[str]:
    """Every `(column, n)` locus in `segments` whose emitted line `text`
    contains a ς immediately followed by a Greek letter -- the mechanical
    signature of the sigma-wrap defect (no Greek word contains a medial ς).
    `\\w` under `re.UNICODE` matches any Greek letter here since these lines
    are pure Greek plus editorial punctuation/digits, which never follow a
    genuine word-final ς with no separating space."""
    hits: list[str] = []
    for seg in segments:
        for l in seg["lines"]:
            if _MEDIAL_SIGMA_RE.search(l["text"]):
                hits.append(f"{seg['column']}.{l['n']}")
    return hits


@requires_export
def test_real_corpus_discourses_no_medial_sigma_survives_the_rejoin(real_spine):
    # Corpus-wide acceptance for the sigma-fold correction (docs/lined-
    # source-plan.md §3, 2026-08-29): direct scan of the current build/dist
    # (pre-fix) found exactly 30 sigma-wrap loci in Discourses -- every one
    # of them must be gone from the emitted spine.
    assert _medial_sigma_loci(real_spine["segments"]) == []


@requires_export
def test_real_corpus_discourses_parse_flat_book_section_unchanged():
    # Acceptance: "Discourses' parse_spine output unchanged (the default
    # parameter makes this structural; assert it anyway)." Stage 1 touched
    # neither _parse_flat_book_section's own body nor its
    # `_lined_chapter_lines(stripped)` call site (still zero-arg, so it
    # still gets `_lined_chapter_lines`'s default `section_div_type="section"`
    # -- the exact string this function hardcoded before this change).
    # Exercises the real call site directly against the real export, so this
    # is a structural check, not just an inference from the source diff.
    tree = etree.parse(str(_real_xml_path()))
    sch = scheme_mod.for_manifest(_real_manifest())
    flat, headings, headers = _parse_flat_book_section(tree.getroot(), sch, _real_manifest())
    total = len(flat)
    joined = sum(1 for l in flat if l.get("joined"))
    assert total == 9285
    # wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
    assert joined == 2393
    assert headers == []
    assert all("sections" not in l for l in flat)


# ============================================================================
# Wave 1 real-corpus census (docs/lined-rollout-plan.md Ruling 4's table):
# the six wave-1 works, each run through the real Diogenes export via
# `parse_spine`. `bodyLines`/`wraps`/`indent` are cross-checked against an
# INDEPENDENT walk of the export XML (`_independent_flat_census`), not a
# trust of the code under test; `columns` is exactly `len(segments)`.
# ============================================================================

WAVE1_CENSUS = {
    "enchiridion": {"columns": 53, "bodyLines": 598, "wraps": 132, "straddle": 8,
                     "indent": {1: 52, 2: 7}},
    "epicurus-letter-to-herodotus": {"columns": 49, "bodyLines": 522, "wraps": 130,
                                      "indent": {1: 28}},
    "epicurus-letter-to-pythocles": {"columns": 33, "bodyLines": 372, "wraps": 89,
                                      "indent": {1: 29}},
    "epicurus-letter-to-menoeceus": {"columns": 14, "bodyLines": 152, "wraps": 38,
                                      "indent": {1: 11, 2: 1}},
    "epicurus-kuriai-doxai": {"columns": 40, "bodyLines": 168, "wraps": 39,
                               "indent": {1: 40}},
    "epicurus-vatican-sayings": {"columns": 62, "bodyLines": 149, "wraps": 23,
                                  "indent": {1: 62}},
}


def _wave1_manifest(work_id: str) -> Manifest:
    return Manifest.load(ROOT / "manifests" / f"{work_id}.yaml")


def _wave1_xml_path(work_id: str) -> Path:
    return exported_xml_path(_wave1_manifest(work_id))


def _wave1_missing_exports() -> list[str]:
    return [w for w in WAVE1_CENSUS if not _wave1_xml_path(w).exists()]


requires_wave1_exports = pytest.mark.skipif(
    bool(_wave1_missing_exports()),
    reason=(
        "Diogenes TLG export not present for one or more wave-1 works "
        f"({_wave1_missing_exports()!r}) — run `uv run python -m "
        "reader_pipeline --work <w> stage1` for each to populate it before "
        "this test can run"
    ),
)


def _independent_flat_census(work_id: str) -> tuple[int, list[int]]:
    """(top-level column div count, distinct <l> counts per column) from a
    fresh, from-scratch walk of the export XML — deliberately not calling
    any stage1_greek helper. Mirrors _parse_flat_chapter's own topology
    rules (top-level page_div_type divs are columns; an @n=="t" div is a
    dropped title/greeting, never a column; every <l> directly or indirectly
    under a numbered column div, INCLUDING an <l n="t">, is a body line —
    Ruling 3) without sharing any code with it."""
    manifest = _wave1_manifest(work_id)
    sch = scheme_mod.for_manifest(manifest)
    root = etree.parse(str(_wave1_xml_path(work_id))).getroot()
    counts: list[int] = []
    for div in root.iter("{*}div"):
        if div.get("type") != sch.page_div_type:
            continue
        if div.get("n") == "t":
            continue
        counts.append(len([l for l in div.iter("{*}l")]))
    return len(counts), counts


@requires_wave1_exports
@pytest.mark.parametrize("work_id", sorted(WAVE1_CENSUS))
def test_wave1_real_corpus_census(work_id):
    expected = WAVE1_CENSUS[work_id]
    manifest = _wave1_manifest(work_id)
    spine = parse_spine(_wave1_xml_path(work_id), manifest)
    segs = spine["segments"]

    assert len(segs) == expected["columns"], work_id

    total_lines = sum(len(s["lines"]) for s in segs)
    joined = sum(1 for s in segs for l in s["lines"] if l.get("joined"))
    assert total_lines == expected["bodyLines"], work_id
    assert joined == expected["wraps"], work_id

    # I1: n is dense 1..len(lines) per segment.
    for s in segs:
        assert [l["n"] for l in s["lines"]] == list(range(1, len(s["lines"]) + 1)), (work_id, s["column"])

    # I3: wrap present iff joined; 0 < wrap < len(last token's surface).
    for s in segs:
        for l in s["lines"]:
            if not l.get("joined"):
                assert "wrap" not in l, (work_id, s["column"], l["n"])
                continue
            last = l["text"].rsplit(" ", 1)[-1]
            assert 0 < l["wrap"] < len(last), (work_id, s["column"], l["n"])
            assert l["text"].endswith(last)

    # I5: no line ever carries both sec and sections.
    for s in segs:
        for l in s["lines"]:
            assert not ("sec" in l and "sections" in l), (work_id, s["column"], l["n"])
            assert "sections" not in l, (work_id, s["column"], l["n"])

    # Ruling 1c/1d: sec is present on every line or on none, per segment.
    # Enchiridion (lined_section_div declared) carries sec on every line;
    # the five Epicurus works carry it on none.
    has_sec = _lined_section_div(manifest) is not None
    for s in segs:
        secs_present = [("sec" in l) for l in s["lines"]]
        assert all(secs_present) if has_sec else not any(secs_present), (work_id, s["column"])
        if has_sec:
            secvals = [l["sec"] for l in s["lines"]]
            assert secvals == sorted(secvals), (work_id, s["column"])  # non-decreasing

    # Indent totals.
    counts: dict[int, int] = {}
    for s in segs:
        for l in s["lines"]:
            if "indent" in l:
                counts[l["indent"]] = counts.get(l["indent"], 0) + 1
    assert counts == expected["indent"], work_id

    # Section-straddling wrap count (Enchiridion only): a joined line whose
    # `sec` differs from its immediate successor's.
    if "straddle" in expected:
        straddle = 0
        for s in segs:
            for i, l in enumerate(s["lines"]):
                if l.get("joined") and i + 1 < len(s["lines"]) and l["sec"] != s["lines"][i + 1]["sec"]:
                    straddle += 1
        assert straddle == expected["straddle"], work_id

    # Independent cross-check: per-column body-line counts (bare walk, no
    # shared code with _parse_flat_chapter/_lined_chapter_lines).
    indep_total, indep_counts = _independent_flat_census(work_id)
    assert indep_total == expected["columns"], work_id
    assert sum(indep_counts) == expected["bodyLines"], work_id
    assert sorted(indep_counts) == sorted(len(s["lines"]) for s in segs), work_id


@requires_wave1_exports
def test_wave1_pythocles_column_84_retains_the_l_n_t_greeting():
    # Ruling 3, real corpus: section 84's own <l n="t"> greeting is column
    # 84's first print line, n=1, no indent -- never skipped.
    manifest = _wave1_manifest("epicurus-letter-to-pythocles")
    spine = parse_spine(_wave1_xml_path("epicurus-letter-to-pythocles"), manifest)
    seg = next(s for s in spine["segments"] if s["column"] == "84")
    first = seg["lines"][0]
    assert first["n"] == 1
    assert first["text"] == "Ἐπίκουρος Πυθοκλεῖ χαίρειν."
    assert "indent" not in first
    assert "sec" not in first


@requires_wave1_exports
def test_wave1_herodotus_53_and_69_em_dash_glob_wraps_are_valid_and_named():
    # The real defect this report fixes: preflight's first wave-1 full build
    # FATALed on epicurus-letter-to-herodotus §53 and §69, the only two
    # corpus sites where a hyphen-wrapped word's continuation carries an em
    # dash GLUED to the next word ("…σχηματίζε-" / "σθαι—πολλὴν γὰρ…").
    # `_apply_lined_wraps`'s whole-whitespace-token absorption correctly
    # pulls "σθαι—πολλὴν" onto the wrapped line as one chunk (I4's byte-
    # perfect round-trip requires it), which makes "πολλὴν" the line's LAST
    # token -- `wrapO` names the wrapped token ("σχηματίζεσθαι") explicitly
    # instead, so `wrap` is validated against the RIGHT token's length (13,
    # not "πολλὴν"'s 6). Real values confirmed via `uv run python -m
    # reader_pipeline --work epicurus-letter-to-herodotus stage1`, 2026-08-29.
    manifest = _wave1_manifest("epicurus-letter-to-herodotus")
    spine = parse_spine(_wave1_xml_path("epicurus-letter-to-herodotus"), manifest)
    segs = {s["column"]: s for s in spine["segments"]}

    seg53 = segs["53"]
    glob53 = next(l for l in seg53["lines"] if l["n"] == 3)
    assert glob53["text"] == (
        "ἀέρα ὑπὸ τῆς προιεμένης φωνῆς ἢ καὶ τῶν ὁμογενῶν σχηματίζεσθαι—πολλὴν"
    )
    assert glob53["wrap"] == 9
    assert glob53["wrapO"] == 49
    assert glob53["text"][glob53["wrapO"] : glob53["wrapO"] + 13] == "σχηματίζεσθαι"
    assert 0 < glob53["wrap"] < 13  # against the WRAPPED token's length, not "πολλὴν"'s (6)
    # The wrapped word is not the last whitespace-delimited chunk of the
    # absorbed text -- "πολλὴν" rides along glued to it with no space.
    assert glob53["text"].rsplit(" ", 1)[-1] == "σχηματίζεσθαι—πολλὴν"

    seg69 = segs["69"]
    glob69 = next(l for l in seg69["lines"] if l["n"] == 4)
    assert glob69["text"] == (
        "τὴν ἑαυτοῦ φύσιν ἔχον ἀίδιον, οὐχ οἷον δὲ εἶναι συμπεφορημένον—ὥσπερ"
    )
    assert glob69["wrap"] == 9
    assert glob69["wrapO"] == 48
    assert glob69["text"][glob69["wrapO"] : glob69["wrapO"] + 14] == "συμπεφορημένον"
    assert 0 < glob69["wrap"] < 14
    assert glob69["text"].rsplit(" ", 1)[-1] == "συμπεφορημένον—ὥσπερ"

    # Every other joined line in these two columns is an ordinary
    # (non-glob) wrap -- confirms wrapO is emitted uniformly, not only on
    # the glob shape, and stays consistent with I3 everywhere.
    for seg in (seg53, seg69):
        for l in seg["lines"]:
            if not l.get("joined"):
                assert "wrap" not in l and "wrapO" not in l
                continue
            assert isinstance(l["wrapO"], int) and l["wrapO"] >= 0
            assert 0 < l["wrap"]


@requires_wave1_exports
@pytest.mark.parametrize("work_id", ["enchiridion", "epicurus-letter-to-pythocles"])
def test_wave1_no_medial_sigma_survives_the_rejoin(work_id):
    # Same corpus-wide acceptance as Discourses, for the two wave-1 works a
    # direct scan of the current build/dist (pre-fix) found sigma-wraps in:
    # enchiridion (2 loci) and epicurus-letter-to-pythocles (1 locus). The
    # other four wave-1 works (herodotus/menoeceus/kd/vatican) had zero.
    manifest = _wave1_manifest(work_id)
    spine = parse_spine(_wave1_xml_path(work_id), manifest)
    assert _medial_sigma_loci(spine["segments"]) == []


@requires_wave1_exports
def test_named_sigma_wrap_loci_corrected():
    # The three loci a cross-family Greek review named directly (report
    # instructions): enchiridion ch.31 §5 προσήκει, ch.33 §12-13
    # προσηκόντως, and epicurus-letter-to-pythocles §90 προσκρούσῃ. Each was
    # the wrongly-glued "προς<letter>" before this fix; confirm the emitted
    # spine now carries the real, medial-σ word.
    ench = parse_spine(_wave1_xml_path("enchiridion"), _wave1_manifest("enchiridion"))
    ench_segs = {s["column"]: s for s in ench["segments"]}
    ch31 = " ".join(l["text"] for l in ench_segs["31"]["lines"] if l["sec"] == 5)
    assert "προσήκει" in ch31
    assert "προςήκει" not in ch31
    ch33 = " ".join(l["text"] for l in ench_segs["33"]["lines"] if l["sec"] in (12, 13))
    assert "προσηκόντως" in ch33
    assert "προςηκόντως" not in ch33

    pyth = parse_spine(
        _wave1_xml_path("epicurus-letter-to-pythocles"),
        _wave1_manifest("epicurus-letter-to-pythocles"),
    )
    pyth_seg90 = next(s for s in pyth["segments"] if s["column"] == "90")
    text90 = " ".join(l["text"] for l in pyth_seg90["lines"])
    assert "προσκρούσῃ" in text90
    assert "προςκρούσῃ" not in text90
