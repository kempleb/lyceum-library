"""Regression tests for tools/extract_freeman_wayback.py's HTML parsing --
column synthesis, front-matter/page-marker skipping, group-header vs.
continuation-paragraph disambiguation, and the four-way kind classifier
(including the wholly-italic-parenthetical note/embedded tie-break). No
network: exercises `parse_chapter`/`classify_kind` directly on minimal
synthetic HTML replicating sacred-texts.com's actual markup shapes (see
the module docstring; verified against the real Protagoras/DK80 chapter,
`sources/freeman-ancilla/freeman-protagoras.clean.json`)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_freeman_wayback", _TOOLS / "extract_freeman_wayback.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_freeman_wayback"] = _mod
_spec.loader.exec_module(_mod)


def _wrap(body: str) -> str:
    return f"<HTML><BODY>{body}</BODY></HTML>"


# --- front matter / page markers -------------------------------------------

def test_front_matter_before_first_number_is_dropped():
    html = _wrap(
        "<p>Someone of Somewhere: fifth century B.C.</p>"
        "<p>He wrote a book. Various titles are mentioned.</p>"
        "<p>1. Plain surviving words here.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B1"]
    assert headers == []


def test_page_marker_paragraph_is_skipped_not_a_header():
    html = _wrap(
        "<p>1. Plain roman words.</p>"
        '<p><A NAME="page_126"><FONT SIZE=1 COLOR=GREEN>p. 126</FONT></A></p>'
        "<p>2. More plain roman words.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B1", "B2"]
    assert headers == []


def test_footnote_call_anchor_digit_is_not_emitted_into_entry_text():
    html = _wrap(
        "<p>1. Words before "
        '<a name="fr_6"></a><a href="#fn_6"><font size="1">1</font></a> '
        "words after.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["text"] == "Words before words after."


def test_surviving_footnote_anchor_shape_is_fatal():
    html = _wrap(
        "<p>1. Words before "
        '<a href="#fn_74-extra"><font size="1">2</font></a> words after.</p>'
    )
    with pytest.raises(ValueError, match="footnote-call anchor"):
        _mod.parse_chapter(html)


def test_footnote_call_nbsp_before_punctuation_is_collapsed():
    # Anaxagoras B1's actual sacred-texts shape: a non-breaking space sits
    # between the last word and the footnote-call anchor, which is itself
    # immediately followed by punctuation (no intervening word). Stripping
    # only the anchor's digit (the existing behaviour) leaves that nbsp
    # behind, and it later collapses to a single stray space before the
    # period ("All Things . were"). The paired empty `fr_N` return anchor
    # sits between the nbsp and the footnote-call anchor, exactly as in
    # the real page -- the fix must look through it.
    #
    # The anchor's tail here is ". were together." -- punctuation followed
    # by whitespace and a LOWERCASE word, i.e. the anchor sat mid-sentence
    # and the period is an orphan left behind by the footnote-call markup,
    # not a real sentence break (this is the live B1 defect shape: "All
    # Things. were together."). It must be dropped, not spliced in.
    html = _wrap(
        "<p>1. All Things "
        '<a name="fr_75"></a><a href="#fn_70"><font size="1">1</font></a>'
        ". were together.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["text"] == "All Things were together."


def test_footnote_call_genuine_sentence_break_after_anchor_is_preserved():
    # Conservative guard for the fix above: when the word AFTER the
    # anchor's punctuation is capitalized, the punctuation is a real
    # sentence break (the footnote call sat at the very end of a
    # sentence, not mid-sentence) and must be kept -- a wrong rule here
    # would eat real periods.
    html = _wrap(
        "<p>1. All Things were together"
        '<a name="fr_75"></a><a href="#fn_70"><font size="1">1</font></a>'
        ". Nothing was distinct.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["text"] == "All Things were together. Nothing was distinct."


def test_footnote_call_ordinary_word_spacing_is_untouched():
    # Conservative guard: when a word (not punctuation) follows the
    # footnote-call anchor, normal inter-word spacing must be preserved.
    html = _wrap(
        "<p>1. Words before "
        '<a name="fr_6"></a><a href="#fn_6"><font size="1">1</font></a> '
        "words after.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["text"] == "Words before words after."


def test_footnote_definitions_after_last_entry_are_not_appended():
    html = _wrap(
        '<p>1. Final words.<a href="#fn_1"><font size="1">1</font></a></p>'
        "<h3>Footnotes</h3>"
        '<p><a name="fn_1"></a><a href="chapter.htm#fr_1">1:1</a> '
        "Editorial footnote.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["text"] == "Final words."


def test_genuine_inline_numbers_do_not_trigger_footnote_leak_validation():
    html = _wrap(
        "<p>5. He wrote the book 730 years after Troy.</p>"
        "<p>6. The wind remains for 7 days.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B5"]["text"] == "He wrote the book 730 years after Troy."
    assert cols["B6"]["text"] == "The wind remains for 7 days."


def test_legacy_windows_punctuation_is_normalized():
    cols, _ = _mod.parse_chapter(
        _wrap(
            "<p>1. \u0091Democritus\u0092 view\u0097not the "
            "source\u0092s.\u0092</p>"
        )
    )
    assert cols["B1"]["text"] == "‘Democritus’ view—not the source’s.’"


# --- numbering / lettering --------------------------------------------------

def test_lettered_fragment_tokens_synthesized():
    html = _wrap(
        "<p>1. First.</p>"
        "<p>1a. First-a.</p>"
        "<p>2. Second.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B1", "B1a", "B2"]


# --- group header vs. continuation-paragraph disambiguation ----------------

def test_smallcaps_continuation_merges_into_previous_column():
    html = _wrap(
        "<p>2. (From 'On Being').</p>"
        '<p>(<span style="font-variant:small-caps;">Porphyry</span>: '
        "'<i>a quoted sentence</i>').</p>"
        "<p>3. Next entry.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B2", "B3"]
    assert headers == []
    assert "Porphyry" in cols["B2"]["text"]
    assert cols["B2"]["kind"] == "embedded"


def test_smallcaps_embedded_reading_without_greek_text_role_is_conflict():
    html = _wrap(
        '<p>298. (<span style="font-variant:small-caps;">Suidas</span>: '
        "Democritus uses the word for 'one's own').</p>"
    )
    cols, _ = _mod.parse_chapter(html, text_columns=set())
    assert cols["B298"]["kind"] == "conflict"


def test_wholly_italic_no_smallcaps_paragraph_is_a_group_header():
    html = _wrap(
        "<p>5. Some entry.</p>"
        "<p>'<i>On Mathematics</i>'</p>"
        "<p>6. Next entry.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B5", "B6"]
    assert headers == [
        {"level": 2, "text": "'On Mathematics'", "before_column": "B6"}
    ]


def test_leading_group_header_attaches_to_first_column():
    # Xenophanes begins with the italic genre label "Elegíacs" before B1;
    # unlike Protagoras, its first declared paratext therefore precedes
    # the parser's first numbered entry.
    html = _wrap(
        "<p>Author biography in roman prose.</p>"
        "<p><i>Elegíacs</i></p>"
        "<p>1. First surviving words.</p>"
    )
    _, headers = _mod.parse_chapter(html)
    assert headers == [
        {"level": 2, "text": "Elegíacs", "before_column": "B1"}
    ]


def test_multiple_headers_before_one_column_all_attach_to_it():
    html = _wrap(
        "<p>1. Some entry.</p>"
        "<p>(<i>Doubtful titles</i>)</p>"
        "<p>'<i>Titles</i>'</p>"
        "<p>2. Next entry.</p>"
    )
    _, headers = _mod.parse_chapter(html)
    assert [h["text"] for h in headers] == ["(Doubtful titles)", "'Titles'"]
    assert all(h["before_column"] == "B2" for h in headers)


def test_level_1_header_is_whole_paragraph_smallcaps_no_italics():
    html = _wrap(
        "<p>1. Some entry.</p>"
        '<p><span style="font-variant:small-caps;">THE TETRALOGIES</span></p>'
        "<p>2. Next entry.</p>"
    )
    _, headers = _mod.parse_chapter(html)
    assert headers[0]["level"] == 1


def test_level_1_header_accepts_roman_numeral_connector_markup():
    html = _wrap(
        '<p><span style="font-variant:small-caps;">Tetralogies</span> '
        'III to VI: <span style="font-variant:small-caps;">Natural Science</span>, '
        "etc.</p>"
        "<p>1. First entry.</p>"
    )
    _, headers = _mod.parse_chapter(html)
    assert headers == [{
        "level": 1,
        "text": "Tetralogies III to VI: Natural Science, etc.",
        "before_column": "B1",
    }]


def test_democritus_causes_smallcaps_label_is_designated_level_2():
    html = _wrap(
        '<p><span style="font-variant:small-caps;">'
        "unclassified writings on 'causes'</span></p>"
        "<p>11b. First title.</p>"
    )
    _, headers = _mod.parse_chapter(html)
    assert headers == [{
        "level": 2,
        "text": "unclassified writings on 'causes'",
        "before_column": "B11b",
    }]


def test_indented_internally_numbered_div_stays_in_one_column():
    html = _wrap(
        "<p>14. (<i>Calendar extracts</i>).</p>"
        '<div style="margin-left: 32px">1. First witness.'
        "<p>2. Second witness.</p>"
        "<table><tr><td>3rd.</td><td>Rain.</td></tr></table></div>"
        "<p>14a. Next real column.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B14", "B14a"]
    assert "1. First witness." in cols["B14"]["text"]
    assert "2. Second witness." in cols["B14"]["text"]
    assert "3rd. Rain." in cols["B14"]["text"]


def test_smallcaps_margin_left_div_stays_glued_not_header():
    """A margin-left div carrying a small-caps source name (Democritus
    B14's calendar-witness shape) is still continuation text, never a
    header, even standing on its own between two ordinary entries."""
    html = _wrap(
        "<p>1. First entry.</p>"
        '<div style="margin-left: 32px">'
        '(<span style="font-variant:small-caps;">Source</span>: a note).'
        "</div>"
        "<p>2. Second entry.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B1", "B2"]
    assert headers == []
    assert "Source" in cols["B1"]["text"]


def test_range_label_margin_left_div_becomes_l2_header():
    """Democritus B127/B128: a standalone margin-left div printing a
    forward range label (``N-M. (...)``) is Freeman's own paratext, not
    B127's continuation -- it becomes a new L2 group header before B(N)."""
    html = _wrap(
        "<p>127. Words for 127.</p>"
        '<div style="margin-left: 32px">128-141. '
        "(<i>Unusual words quoted by grammarians</i>)</div>"
        "<p>128. Words for 128.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B127", "B128"]
    assert cols["B127"]["text"] == "Words for 127."
    assert headers == [{
        "level": 2,
        "text": "128-141. (Unusual words quoted by grammarians)",
        "before_column": "B128",
    }]


def test_end_marker_margin_left_div_becomes_l2_header():
    """Democritus B115/B116: a standalone margin-left div printing a bare
    end-of-section marker (``(End of the Gnomae)``) is the same L2-header
    shape as the already-committed "(End of the Tetralogies of
    Thrasyllus)" -- paratext, not B115's continuation."""
    html = _wrap(
        "<p>115. Words for 115.</p>"
        '<div style="margin-left: 32px">(<i>End of the Gnomae</i>)</div>'
        "<p>116. Words for 116.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B115", "B116"]
    assert headers == [{
        "level": 2,
        "text": "(End of the Gnomae)",
        "before_column": "B116",
    }]


def test_democritus_transcription_number_typos_are_exactly_corrected():
    html = _wrap(
        "<p>308. '<i>Theogonia</i>.'</p>"
        "<p>30S. (<i>Reference to Democritus as philosopher in Qifti</i>).</p>"
        "<p>308. (<i>Epigram attributed to Democritus</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B301", "B305", "B308"]


def test_melissus_b5_transcription_number_typo_is_exactly_corrected():
    html = _wrap(
        "<p>4. Nothing with a beginning and end is infinite.</p>"
        "<p>S. If it were not One, it will form a boundary in relation "
        "to something else.</p>"
        "<p>6. If it were infinite, it would be One.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B4", "B5", "B6"]
    assert cols["B5"]["text"].startswith("If it were not One")


def test_philolaus_b5_transcription_number_typo_is_exactly_corrected():
    """app39.htm prints Philolaus B5's leading ``5.`` as ``S.`` -- the
    identical sacred-texts scan typo already fixed for Melissus. Left
    uncorrected, B5's English glues onto B4 and B5 silently disappears."""
    html = _wrap(
        "<p>4. Actually, everything that can be known has a Number; for "
        "it is impossible to grasp anything with the mind or to "
        "recognise it without this (<i>Number</i>).</p>"
        "<p>S. Actually, Number has two distinct forms, odd and even, "
        "and a third compounded of both, the even-odd; each of these "
        "two forms has many aspects, which each separate object "
        "demonstrates in itself.</p>"
        "<p>6. This is how it is with Nature and Harmony.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B4", "B5", "B6"]
    assert "Number has two distinct forms" in cols["B5"]["text"]
    assert "Number has two distinct forms" not in cols["B4"]["text"]


def test_critias_b59_transcription_number_typo_is_exactly_corrected():
    """app83.htm prints Critias B59's leading ``59.`` as ``S9.`` -- the
    same class of typo. Left uncorrected, B59's English glues onto B58
    and B59 silently disappears."""
    html = _wrap(
        "<p>58. Two-drachma men.</p>"
        "<p>S9. To drink beaker after beaker.</p>"
        "<p>60. Purchase of fish.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B58", "B59", "B60"]
    assert "To drink beaker after beaker" in cols["B59"]["text"]
    assert "To drink beaker after beaker" not in cols["B58"]["text"]


def test_i_for_1_typo_corrected_only_as_exact_successor():
    """Democritus B131: sacred-texts prints ``13I.`` (capital I for the
    digit 1). Accepted as B131 only because 131 is the exact expected
    successor of B130."""
    html = _wrap(
        "<p>130. Circular bands.</p>"
        "<p>13I. Untrodden (<i>unevenly compounded</i>).</p>"
        "<p>132. Equilateral.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B130", "B131", "B132"]
    assert cols["B130"]["text"] == "Circular bands."
    assert cols["B131"]["text"] == "Untrodden (unevenly compounded)."


def test_heraclitus_exact_numbering_typos_are_corrected():
    """The sacred-texts Heraclitus transcription has three distinct label
    corruptions.  Each correction is tied to the exact entry opening so a
    similar-looking label in another chapter cannot be silently rewritten."""
    html = _wrap(
        "<p>49a. In the same river.</p>"
        "<p>So. When you have listened, not to me but to the Law.</p>"
        "<p>4. Happiness does not lie in bodily pleasures.</p>"
        "<p>S. They purify themselves by staining themselves with blood.</p>"
        "<p>6. The sun is new each day.</p>"
        "<p>80. One should know that war is general.</p>"
        "<p>83. (<i>On Pythagoras</i>). Original chief of wranglers.</p>"
        "<p>82. The most handsome ape is ugly.</p>"
        "<p>83. The wisest man will appear an ape.</p>"
        "<p>126b. One thing increases in one way.</p>"
        "<p>12 7. (<i>To the Egyptians</i>): a saying.</p>"
        "<p>128. They pray to statues.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == [
        "B49a", "B50", "B4", "B5", "B6", "B80", "B81", "B82", "B83",
        "B126b", "B127", "B128"
    ]


def test_parmenides_combined_7_8_heading_splits_at_semantic_paragraph():
    """Freeman prints Parmenides 7 and 8 under one ``7, 8.`` heading, but
    the next paragraph begins B8's remaining Way.  Preserve the two DK
    columns without duplicating either translation."""
    html = _wrap(
        "<p>6. The preceding fragment.</p>"
        "<p>7, 8. For this (<i>view</i>) can never predominate.</p>"
        "<p>There is only one other description of the way remaining.</p>"
        "<p>Nor is Being divisible.</p>"
        "<p>9. Everything is full equally of Light and Night.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B6", "B7", "B8", "B9"]
    assert cols["B7"]["text"] == "For this (view) can never predominate."
    assert cols["B8"]["text"] == (
        "There is only one other description of the way remaining. "
        "Nor is Being divisible."
    )


def test_empedocles_compound_77_78_heading_attaches_to_b77():
    html = _wrap(
        "<p>76. Previous fragment.</p>"
        "<p>77, 78. (<i>Trees</i>) retentive of their leaves flourish all year.</p>"
        "<p>79. Thus eggs are borne.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B76", "B77", "B79"]
    assert cols["B77"]["text"] == (
        "(Trees) retentive of their leaves flourish all year."
    )


def test_parenthetic_bare_cross_reference_is_conflict():
    """A cross-reference is apparatus, not automatically a translation,
    even when a proper name outside italics makes the typography look like
    roman verbatim prose (Parmenides B25)."""
    html = _wrap("<p>25. (= Empedocles, <i>Frg</i>. 28).</p>")
    cols, _ = _mod.parse_chapter(html, text_columns={"B25"})
    assert cols["B25"]["kind"] == "conflict"


def test_roman_numeral_label_is_not_misread_as_a_typo_entry():
    """A genuine roman numeral (or stray letter) heading a paragraph is
    never mistaken for a numbering typo -- its I/l-corrected value does
    not equal the expected successor, so it stays a continuation of the
    entry being accumulated, never a fabricated new column."""
    html = _wrap(
        "<p>1. First words.</p>"
        "<p>III. Some unrelated roman numeral text.</p>"
        "<p>2. Second column.</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert list(cols) == ["B1", "B2"]
    assert "III. Some unrelated roman numeral text." in cols["B1"]["text"]


# --- kind classification ----------------------------------------------------

def test_kind_verbatim_roman_prose_after_italic_title_frame():
    html = _wrap("<p>1. (<i>From 'Truth'</i>). Of all things the measure is Man.</p>")
    cols, _ = _mod.parse_chapter(html)
    assert cols["B1"]["kind"] == "verbatim"


def test_kind_verbatim_pure_roman_no_italics():
    html = _wrap("<p>10. Art without practice is nothing.</p>")
    cols, _ = _mod.parse_chapter(html)
    assert cols["B10"]["kind"] == "verbatim"


def test_kind_embedded_smallcaps_source_plus_quote():
    html = _wrap(
        '<p>8. (<span style="font-variant:small-caps;">Plato</span>, '
        "Sophist 232D: '<i>a quoted view</i>').</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B8"]["kind"] == "embedded"


def test_logical_smallcaps_emphasis_is_not_a_source_name():
    """Parmenides B2/B8 set forms of ``it is`` and ``not to be`` in small
    caps for emphasis.  They remain Freeman's direct verse translation,
    not a named-source frame."""
    html = _wrap(
        '<p>2. The one that <span style="font-variant:small-caps;">'
        "it is</span>, and the other that "
        '<span style="font-variant:small-caps;">it is not</span>.</p>'
    )
    cols, _ = _mod.parse_chapter(html, text_columns={"B2"})
    assert cols["B2"]["kind"] == "verbatim"


def test_kind_title_bare_quoted_title_under_titles_header():
    html = _wrap("<p>8a. '<i>On Constitution</i>.'</p>")
    cols, _ = _mod.parse_chapter(html)
    assert cols["B8a"]["kind"] == "title"


def test_kind_title_not_confused_by_lettered_label_containing_a_letter():
    # Regression: "8a." itself contains the roman letter 'a' outside the
    # <i> -- the lead-label strip must happen before the roman-prose scan,
    # or every lettered entry misclassifies as verbatim.
    html = _wrap("<p>8h. '<i>On the Underworld</i>.'</p>")
    cols, _ = _mod.parse_chapter(html)
    assert cols["B8h"]["kind"] == "title"


def test_kind_conflict_wholly_italic_parenthetical_no_text_columns_given():
    # Round-2 fix (residual 1): a missing `text_columns` hint means no
    # cross-check was even attempted -- that is NOT grounds to fall back
    # to the conservative `note` reading. Ambiguity ALWAYS yields
    # `conflict`, hint or no hint.
    html = _wrap(
        "<p>7. (<i>Protagoras used to say the tangent touches the circle "
        "along a line</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B7"]["kind"] == "conflict"


def test_kind_conflict_wholly_italic_parenthetical_even_when_text_columns_agree():
    # Round-2 fix (residual 1): the Greek spine ALSO carries no role='text'
    # for this column (not in text_columns) -- no disagreement was
    # detected. But absence of disagreement is not a resolution: the
    # shape is still markup-ambiguous, so it is still `conflict`, resolvable
    # only by an explicit, human-authored citation.kind_overrides
    # declaration (e.g. Protagoras B7's own override, "markup-unambiguous
    # per Grok print audit").
    html = _wrap(
        "<p>7. (<i>Protagoras used to say the tangent touches the circle "
        "along a line</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html, text_columns=set())
    assert cols["B7"]["kind"] == "conflict"


def test_kind_conflict_wholly_italic_parenthetical_when_greek_disagrees():
    # Freeman's own markup reads as pure narration (paren-first, wholly
    # italic, no small-caps) -- the conservative literal-markup default
    # would be `note`, but that default is never trusted on its own
    # (round-2 fix, residual 1): the extractor STOPS (`conflict`) whether
    # a hint is absent, agrees, or -- as demonstrated here -- disagrees,
    # rather than auto-resolving any of the three cases (CLAUDE.md rule 9
    # / design note §1(b)'s "no heuristic tie-break" -- resolvable only
    # by an explicit, human-authored citation.kind_overrides declaration
    # in the manifest, see stage1_freeman_english.py).
    html = _wrap(
        "<p>5. (<i>Title: 'Contradictory Arguments'. Plato plagiarised "
        "from this</i>).</p>"
    )
    cols_no_hint, _ = _mod.parse_chapter(html)
    assert cols_no_hint["B5"]["kind"] == "conflict"
    cols_hint, _ = _mod.parse_chapter(html, text_columns={"B5"})
    assert cols_hint["B5"]["kind"] == "conflict"


def test_kind_conflict_mixed_typography_title_uses_b5_precedent():
    html = _wrap(
        "<p>1. (<i>Title of book:</i> The Great World-Order, "
        "<i>here attributed to Democritus</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html, text_columns={"B1"})
    assert cols["B1"]["kind"] == "conflict"


def test_kind_conflict_mixed_typography_title_of_work_variant():
    # Finding 2 (round-2 adversarial fix): the "(Title of book:" prefix
    # generalizes to "(Title of work:" -- same title-survival-in-frame
    # shape, different Freeman wording.
    html = _wrap(
        "<p>1. (<i>Title of work:</i> The Lesser World-Order, "
        "<i>attributed to Leucippus</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html, text_columns={"B1"})
    assert cols["B1"]["kind"] == "conflict"


def test_kind_conflict_mixed_typography_bare_title_variant():
    # Finding 2: bare "(Title:" (no "of book"/"of work") also generalizes.
    html = _wrap(
        "<p>1. (<i>Title:</i> On Nature, "
        "<i>attributed to this author</i>).</p>"
    )
    cols, _ = _mod.parse_chapter(html, text_columns={"B1"})
    assert cols["B1"]["kind"] == "conflict"


def test_kind_ordinary_parenthetical_not_caught_by_title_generalization():
    # Finding 2: the generalized title-announcement pattern must stay
    # conservative -- an ordinary parenthetical remark that merely starts
    # with "(" and contains no title announcement is unaffected, and falls
    # through to the normal wholly-italic conflict rule as before.
    html = _wrap("<p>1. (<i>Some note about the source</i>).</p>")
    cols, _ = _mod.parse_chapter(html, text_columns=set())
    assert cols["B1"]["kind"] == "conflict"


def test_kind_conflict_verbatim_markup_when_greek_has_no_text_role():
    # Xenophanes B21/B21a/B39/B41: Freeman sets a translated lexical
    # survival in roman type, but the live Greek spine cannot isolate the
    # headword from its source's surrounding sentence at whole-line role
    # granularity. The design record requires EVERY markup/role
    # disagreement to classify conflict; it must never auto-promote the
    # source sentence to the philosopher's words.
    html = _wrap("<p>21. (<i>Of Simonides</i>). Skinflint.</p>")
    cols, _ = _mod.parse_chapter(html, text_columns=set())
    assert cols["B21"]["kind"] == "conflict"


# --- duplicate synthesized DK keys -------------------------------------------

def test_duplicate_synthesized_dk_column_is_fatal():
    html = _wrap(
        "<p>1. First occurrence.</p>"
        "<p>2. Something else.</p>"
        "<p>1. A second, later paragraph that also prints '1.' -- never "
        "silently merged or overwritten.</p>"
    )
    with pytest.raises(ValueError, match="duplicate synthesized DK column"):
        _mod.parse_chapter(html)


# --- L2 header vs. roman-continuation disambiguation (finding 10) ----------

def test_roman_continuation_paragraph_is_not_a_group_header():
    # A second <p> with real roman prose, no small-caps, no leading number
    # -- a continuation of the entry being accumulated (a multi-paragraph
    # `verbatim` entry), NOT paratext. Regression: an earlier version of
    # the classifier treated ANY unnumbered non-smallcaps paragraph as an
    # L2 header, which would have silently dropped this text.
    html = _wrap(
        "<p>1. Of all things the measure is Man.</p>"
        "<p>And of the things that are not, that they are not.</p>"
        "<p>2. Next entry.</p>"
    )
    cols, headers = _mod.parse_chapter(html)
    assert list(cols) == ["B1", "B2"]
    assert headers == []
    assert "things that are not" in cols["B1"]["text"]
    assert cols["B1"]["kind"] == "verbatim"


# --- source-citation frame ranges (finding 13) ------------------------------

def test_embedded_entry_carries_frame_range():
    html = _wrap(
        '<p>8. (<span style="font-variant:small-caps;">Plato</span>, '
        "Sophist 232D: '<i>a quoted view</i>').</p>"
    )
    cols, _ = _mod.parse_chapter(html)
    assert cols["B8"]["kind"] == "embedded"
    start, end = cols["B8"]["frames"][0]
    text = cols["B8"]["text"]
    assert text[start:end] == "(Plato, Sophist 232D: "


def test_full_protagoras_chapter_matches_committed_clean_json():
    """End-to-end fidelity check against the real, reviewed extraction --
    catches any future edit to the parser silently drifting from the
    committed sources/freeman-ancilla/freeman-protagoras.clean.json.

    B11/B12 are NOT pre-removed before comparing (finding 9, phase-1
    adversarial fix round): the raw HTML genuinely contains them (Freeman
    prints two further numbered entries beyond the DK80B spine's last
    column), and they are dropped downstream by stage1_freeman_english's
    key-set reconciliation gate (an English orphan -- see
    test_stage1_freeman_english.py's true-orphan-path tests), not by this
    parser. Asserting the extraction/commit DIFF is EXACTLY the intended
    orphan set (rather than blindly popping them first) means a future
    regression that silently drops or adds any OTHER column still fails
    this test."""
    import json

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / "app75.htm"
    if not fixture.exists():
        pytest.skip("app75.htm fixture not present")
    committed = json.loads(
        (root / "sources" / "freeman-ancilla" / "freeman-protagoras.clean.json")
        .read_text(encoding="utf-8")
    )
    text_columns = {"B1", "B2", "B3", "B4", "B5", "B6", "B6a", "B6b", "B8", "B9", "B10"}
    cols, _ = _mod.parse_chapter(fixture.read_text(encoding="utf-8"), text_columns)
    extra = set(cols) - set(committed)
    missing = set(committed) - set(cols)
    assert extra == {"B11", "B12"}, f"unexpected extraction drift (extra): {extra}"
    assert missing == set(), f"unexpected extraction drift (missing): {missing}"
    # sacred-texts' own transcription of the Porphyry quote inside B2 has a
    # transcription typo ("fit any rate") the committed clean JSON corrects
    # to "At any rate" (archive.org OCR-scan-confirmed) -- README.md's
    # "Mechanical fix (1)". A documented, verified exception, not parser
    # drift, so B2 is compared after applying the same known fix; every
    # other column is compared byte-for-byte (finding 15).
    _MECHANICAL_FIXES = {"B2": ("fit any rate", "At any rate")}
    for col in committed:
        assert cols[col]["kind"] == committed[col]["kind"], col
        text = cols[col]["text"]
        if col in _MECHANICAL_FIXES:
            bad, good = _MECHANICAL_FIXES[col]
            text = text.replace(bad, good)
        assert text == committed[col]["text"], col
        assert cols[col].get("frames") == committed[col].get("frames"), col


def test_full_xenophanes_chapter_matches_committed_extraction():
    """Phase 1b fidelity lock: the reviewed app18 HTML fixture re-extracts
    to the checked-in clean JSON and both genre headers byte-for-byte."""
    import json

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / "app18.htm"
    committed = json.loads(
        (root / "sources" / "freeman-ancilla" / "freeman-xenophanes.clean.json")
        .read_text(encoding="utf-8")
    )
    committed_headers = json.loads(
        (root / "sources" / "freeman-ancilla"
         / "freeman-xenophanes.group_headers.json")
        .read_text(encoding="utf-8")
    )
    text_columns = {
        "B1", "B2", "B3", "B5", "B6", "B7", "B8", "B9", "B10",
        "B11", "B12", "B14", "B15", "B16", "B17", "B18", "B20",
        "B22", "B23", "B24", "B25", "B26", "B27", "B28", "B29",
        "B30", "B31", "B32", "B33", "B34", "B35", "B36", "B37",
        "B38",
    }
    cols, headers = _mod.parse_chapter(
        fixture.read_text(encoding="utf-8"), text_columns
    )
    assert cols == committed
    assert headers == committed_headers


# Independent expected column ORDER per work (finding 1, round-2 adversarial
# fix): a literal, hand-reviewed sequence, never derived from `parse_chapter`'s
# own output or from the committed JSON it is checked against. Plain dict
# equality (`cols == committed`, below) does not care about key order, so a
# regression that silently reordered or dropped-and-re-added a column while
# keeping the same set of keys and values would pass unnoticed without this.
_BATCH_1_SPINES = {
    "anaximander": ["B1", "B2", "B3", "B4", "B5"],
    "anaximenes": ["B1", "B2", "B2a", "B3"],
    "zeno": ["B1", "B2", "B3", "B4"],
    "melissus": [f"B{i}" for i in range(1, 12)],
    "leucippus": ["B1", "B1a", "B2"],
}

# One hand-quoted, distinctive literal phrase per work -- taken straight from
# the witness text, not from the extractor's or the committed JSON's output --
# so a bug that blanks, truncates, or corrupts an entry's text while leaving
# its `kind` and dict-equality intact is still caught (finding 1).
_BATCH_1_REPRESENTATIVE_TEXT = {
    "anaximander": ("B4", "Nozzle of the bellows."),
    "anaximenes": ("B2", "As our soul, being air, holds us together"),
    "zeno": ("B4", "the place in which it is"),
    "melissus": ("B8", "contact with the finger"),
    "leucippus": ("B2", "everything happens out of reason and by necessity"),
}

# Independent header expectations (finding 1): anaximenes' "(Spurious)" L2
# header sits before B3, melissus' "Spurious" L2 header sits before B11.
_BATCH_1_HEADER_EXPECTATION = {
    "anaximenes": {"level": 2, "text": "(Spurious)", "before_column": "B3"},
    "melissus": {"level": 2, "text": "Spurious", "before_column": "B11"},
}


@pytest.mark.parametrize(
    ("chapter_file", "work", "text_columns", "english_orphans"),
    [
        ("app14.htm", "anaximander", {"B1", "B2", "B3", "B4", "B5"}, set()),
        ("app15.htm", "anaximenes", {"B1", "B2", "B2a", "B3"}, set()),
        ("app24.htm", "zeno", {"B1", "B2", "B3", "B4"}, set()),
        (
            "app25.htm", "melissus",
            {f"B{i}" for i in range(1, 12)}, {"B12"},
        ),
        ("app62.htm", "leucippus", {"B1", "B2"}, set()),
    ],
)
def test_burnet_flip_batch_1_matches_committed_extractions(
    chapter_file, work, text_columns, english_orphans
):
    """The five reviewed sacred-texts fixtures re-extract byte-for-byte.

    Melissus B12 is the one declared English orphan: it is present in the
    source fixture but has no DK30B spine column and is therefore excluded
    from the committed clean JSON.
    """
    import json

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / chapter_file
    source_dir = root / "sources" / "freeman-ancilla"
    committed = json.loads(
        (source_dir / f"freeman-{work}.clean.json").read_text(encoding="utf-8")
    )
    committed_headers = json.loads(
        (source_dir / f"freeman-{work}.group_headers.json")
        .read_text(encoding="utf-8")
    )
    cols, headers = _mod.parse_chapter(
        fixture.read_text(encoding="utf-8"), text_columns
    )
    assert set(cols) - set(committed) == english_orphans
    assert set(committed) - set(cols) == set()

    # Independent literal order/content checks (finding 1): asserted against
    # hand-authored expectations above, BEFORE the dict-equality check below
    # that (being order-insensitive and comparing only to the committed JSON)
    # cannot catch reordering or a fixture/JSON pair that drifted together.
    expected_order = _BATCH_1_SPINES[work] + sorted(english_orphans)
    assert list(cols) == expected_order
    rep_col, rep_phrase = _BATCH_1_REPRESENTATIVE_TEXT[work]
    assert rep_phrase in cols[rep_col]["text"]
    if work in _BATCH_1_HEADER_EXPECTATION:
        assert _BATCH_1_HEADER_EXPECTATION[work] in headers

    for orphan in english_orphans:
        cols.pop(orphan)
    assert cols == committed
    assert headers == committed_headers


# Independent expected column sequence for the app63.htm fixture (Freeman's
# OWN raw labels, "B16c" not yet remapped to DK's "B15c") -- a literal,
# reviewed fixture, NOT derived from `parse_chapter`'s own output (finding
# 3, round 2 adversarial fix). Deriving `text_targets` below from the
# parser's own first-pass keys would be self-referential: a parser bug that
# drops or misorders a column could never be caught by a "spine" built from
# that same buggy output. 386 Greek-spine columns (in DK order, B16c at its
# printed position between B15b and B16) + the 5 English-only orphans below.
_DEMOCRITUS_RAW_SPINE = [
    'B0a', 'B0b', 'B0c', 'B1', 'B1a', 'B1b', 'B2', 'B2a', 'B2b', 'B2c', 'B3',
    'B4', 'B4a', 'B4b', 'B4c', 'B5', 'B5a', 'B5b', 'B5c', 'B5d', 'B5e',
    'B5f', 'B5g', 'B5h', 'B5i', 'B6', 'B7', 'B8', 'B8a', 'B8b', 'B9', 'B10',
    'B10a', 'B10b', 'B11', 'B11a', 'B11b', 'B11c', 'B11d', 'B11e', 'B11f',
    'B11g', 'B11h', 'B11i', 'B11k', 'B11l', 'B11m', 'B11n', 'B11o', 'B11p',
    'B11q', 'B11r', 'B12', 'B13', 'B14', 'B14a', 'B14b', 'B14c', 'B15',
    'B15a', 'B15b', 'B16c', 'B16', 'B16a', 'B17', 'B18', 'B18a', 'B18b',
    'B19', 'B20', 'B20a', 'B21', 'B22', 'B23', 'B24', 'B25', 'B25a', 'B25b',
    'B26', 'B26a', 'B26b', 'B26c', 'B26d', 'B26e', 'B26f', 'B27', 'B27a',
    'B28', 'B28a', 'B28b', 'B28c', 'B29', 'B29a', 'B30', 'B31', 'B32', 'B33',
    'B34', 'B35', 'B36', 'B37', 'B38', 'B39', 'B40', 'B41', 'B42', 'B43',
    'B44', 'B45', 'B46', 'B47', 'B48', 'B49', 'B50', 'B51', 'B52', 'B53',
    'B53a', 'B54', 'B55', 'B56', 'B57', 'B58', 'B59', 'B60', 'B61', 'B62',
    'B63', 'B64', 'B65', 'B66', 'B67', 'B68', 'B69', 'B70', 'B71', 'B72',
    'B73', 'B74', 'B75', 'B76', 'B77', 'B78', 'B79', 'B80', 'B81', 'B82',
    'B83', 'B84', 'B85', 'B86', 'B87', 'B88', 'B89', 'B90', 'B91', 'B92',
    'B93', 'B94', 'B95', 'B96', 'B97', 'B98', 'B99', 'B100', 'B101', 'B102',
    'B103', 'B104', 'B105', 'B106', 'B107', 'B107a', 'B108', 'B109', 'B110',
    'B111', 'B112', 'B113', 'B114', 'B115', 'B116', 'B117', 'B118', 'B119',
    'B120', 'B121', 'B122', 'B122a', 'B123', 'B124', 'B125', 'B126', 'B127',
    'B128', 'B129', 'B129a', 'B130', 'B131', 'B132', 'B133', 'B134', 'B135',
    'B136', 'B137', 'B138', 'B139', 'B139a', 'B140', 'B141', 'B142', 'B143',
    'B144', 'B144a', 'B145', 'B146', 'B147', 'B148', 'B149', 'B150', 'B151',
    'B152', 'B153', 'B154', 'B155', 'B155a', 'B156', 'B157', 'B158', 'B159',
    'B160', 'B161', 'B162', 'B163', 'B164', 'B165', 'B166', 'B167', 'B168',
    'B169', 'B170', 'B171', 'B172', 'B173', 'B174', 'B175', 'B176', 'B177',
    'B178', 'B179', 'B180', 'B181', 'B182', 'B183', 'B184', 'B185', 'B186',
    'B187', 'B188', 'B189', 'B190', 'B191', 'B192', 'B193', 'B194', 'B195',
    'B196', 'B197', 'B198', 'B199', 'B200', 'B201', 'B202', 'B203', 'B204',
    'B205', 'B206', 'B207', 'B208', 'B209', 'B210', 'B211', 'B212', 'B213',
    'B214', 'B215', 'B216', 'B217', 'B218', 'B219', 'B220', 'B221', 'B222',
    'B223', 'B224', 'B225', 'B226', 'B227', 'B228', 'B229', 'B230', 'B231',
    'B232', 'B233', 'B234', 'B235', 'B236', 'B237', 'B238', 'B239', 'B240',
    'B241', 'B242', 'B243', 'B244', 'B245', 'B246', 'B247', 'B248', 'B249',
    'B250', 'B251', 'B252', 'B253', 'B254', 'B255', 'B256', 'B257', 'B258',
    'B259', 'B260', 'B261', 'B262', 'B263', 'B264', 'B265', 'B266', 'B267',
    'B268', 'B269', 'B270', 'B271', 'B272', 'B273', 'B274', 'B275', 'B276',
    'B277', 'B278', 'B279', 'B280', 'B281', 'B282', 'B283', 'B284', 'B285',
    'B286', 'B287', 'B288', 'B289', 'B290', 'B291', 'B292', 'B293', 'B294',
    'B295', 'B296', 'B297', 'B298', 'B298a', 'B298b', 'B299', 'B299a',
    'B299b', 'B299c', 'B299d', 'B299e', 'B299f', 'B299g', 'B299h', 'B300',
    'B301', 'B302', 'B302a', 'B303', 'B304', 'B305', 'B306', 'B307', 'B308',
    'B309',
]


def test_full_democritus_chapter_matches_committed_extraction():
    """Phase 2 stress lock: tables/indented B14 material, compound L1
    headers, source-number corrections, edition reconciliation, and the
    deliberately open conflicts all remain explicit."""
    import json
    import yaml

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / "app63.htm"
    committed = json.loads(
        (root / "sources" / "freeman-ancilla" / "freeman-democritus.clean.json")
        .read_text(encoding="utf-8")
    )
    committed_headers = json.loads(
        (root / "sources" / "freeman-ancilla"
         / "freeman-democritus.group_headers.json")
        .read_text(encoding="utf-8")
    )
    manifest = yaml.safe_load(
        (root / "manifests" / "democritus-fragments.yaml").read_text()
    )
    orphans = {"B25a", "B25b", "B301", "B303", "B305"}
    # Independent of the parser's own output (finding 3): `spine` and
    # `text_targets` come from the literal `_DEMOCRITUS_RAW_SPINE` fixture
    # above, never from a first pass of `parse_chapter` on this same fixture.
    spine = ["B15c" if c == "B16c" else c for c in _DEMOCRITUS_RAW_SPINE]
    spine = [c for c in spine if c not in orphans]
    text_targets = set(spine) - set(manifest["citation"]["unmarked_columns"])
    text_columns = {
        c for c in _DEMOCRITUS_RAW_SPINE
        if ("B15c" if c == "B16c" else c) in text_targets
    }
    cols, headers = _mod.parse_chapter(
        fixture.read_text(encoding="utf-8"), text_columns
    )
    # Finding 4: assert the RAW extraction (before the 5 English-only
    # orphans are filtered out) is complete and non-empty for every orphan,
    # so a regression that silently drops or blanks an orphan is caught
    # here rather than being masked by the filter below.
    assert len(cols) == 391  # 386 DK-spine columns (as B16c) + 5 orphans
    assert set(cols) == set(_DEMOCRITUS_RAW_SPINE)
    for orphan in orphans:
        assert cols[orphan]["text"].strip() != "", orphan

    cols = {c: rec for c, rec in cols.items() if c not in orphans}
    headers = [
        {**h, "before_column": "B15c"}
        if h["before_column"] == "B16c" else h
        for h in headers
    ]

    assert cols == committed
    assert headers == committed_headers
    assert len(cols) == 386  # full 386/386 Freeman coverage; B131 no longer a gap
    assert len(headers) == 21  # +2: B127/B128's range label, B115/B116's end marker


# --- Burnet-flip batch 2: full-fixture fidelity (Heraclitus, Parmenides,
# Empedocles, Anaxagoras) --------------------------------------------------
#
# The synthetic snippet tests above (e.g.
# test_heraclitus_exact_numbering_typos_are_corrected,
# test_parmenides_combined_7_8_heading_splits_at_semantic_paragraph,
# test_empedocles_compound_77_78_heading_attaches_to_b77) exercise isolated
# parsing rules on minimal HTML. They do not catch a regression that only
# shows up against the real, reviewed sacred-texts chapters. These four
# tests bring batch 2 up to the batch-1/Democritus fidelity standard: a
# hand-authored, independent raw column order (never derived from running
# parse_chapter on this same fixture) verified before the order-blind
# dict-equality check, a hand-quoted literal phrase per work (verified
# against the fixture, not copied from the committed JSON), and the
# declared orphan/compound exceptions.

# Independent RAW extraction order per work -- literal DK reading order
# (including the English-only orphan columns, in their natural printed
# position, NOT appended at the end): heraclitus 144 retained + B109
# (deleted-by-DK6 cross-reference, between B108/B110); parmenides 26, no
# orphans; empedocles 161 retained + B149/B150 (absorbed into compound
# B148 by a later stage, not by parse_chapter) + B154b (no DK6 column);
# anaxagoras 23 retained + B20/B23 (English-only Doubtful/Spurious
# entries, B23 last).
_BATCH_2_RAW_SPINES = {
    "heraclitus": [
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21',
        'B22', 'B23', 'B24', 'B25', 'B26', 'B27', 'B28', 'B29', 'B30', 'B31',
        'B32', 'B33', 'B34', 'B35', 'B36', 'B37', 'B38', 'B39', 'B40', 'B41',
        'B42', 'B43', 'B44', 'B45', 'B46', 'B47', 'B48', 'B49', 'B49a', 'B50',
        'B51', 'B52', 'B53', 'B54', 'B55', 'B56', 'B57', 'B58', 'B59', 'B60',
        'B61', 'B62', 'B63', 'B64', 'B65', 'B66', 'B67', 'B68', 'B69', 'B70',
        'B71', 'B72', 'B73', 'B74', 'B75', 'B76', 'B77', 'B78', 'B79', 'B80',
        'B81', 'B82', 'B83', 'B84a', 'B84b', 'B85', 'B86', 'B87', 'B88',
        'B89', 'B90', 'B91', 'B92', 'B93', 'B94', 'B95', 'B96', 'B97', 'B98',
        'B99', 'B100', 'B101', 'B101a', 'B102', 'B103', 'B104', 'B105',
        'B106', 'B107', 'B108', 'B109', 'B110', 'B111', 'B112', 'B113',
        'B114', 'B115', 'B116', 'B117', 'B118', 'B119', 'B120', 'B121',
        'B122', 'B123', 'B124', 'B125', 'B125a', 'B126', 'B126a', 'B126b',
        'B127', 'B128', 'B129', 'B130', 'B131', 'B132', 'B133', 'B134',
        'B135', 'B136', 'B137', 'B138', 'B139',
    ],
    "parmenides": [
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B15a', 'B16', 'B17', 'B18', 'B19',
        'B20', 'B21', 'B22', 'B23', 'B24', 'B25',
    ],
    "empedocles": [
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21',
        'B22', 'B23', 'B24', 'B25', 'B26', 'B27', 'B27a', 'B28', 'B29', 'B30',
        'B31', 'B32', 'B33', 'B34', 'B35', 'B36', 'B37', 'B38', 'B39', 'B40',
        'B41', 'B42', 'B43', 'B44', 'B45', 'B46', 'B47', 'B48', 'B49', 'B50',
        'B51', 'B52', 'B53', 'B54', 'B55', 'B56', 'B57', 'B58', 'B59', 'B60',
        'B61', 'B62', 'B63', 'B64', 'B65', 'B66', 'B67', 'B68', 'B69', 'B70',
        'B71', 'B72', 'B73', 'B74', 'B75', 'B76', 'B77', 'B79', 'B80', 'B81',
        'B82', 'B83', 'B84', 'B85', 'B86', 'B87', 'B88', 'B89', 'B90', 'B91',
        'B92', 'B93', 'B94', 'B95', 'B96', 'B97', 'B98', 'B99', 'B100',
        'B101', 'B102', 'B103', 'B104', 'B105', 'B106', 'B107', 'B108',
        'B109', 'B109a', 'B110', 'B111', 'B112', 'B113', 'B114', 'B115',
        'B116', 'B117', 'B118', 'B119', 'B120', 'B121', 'B122', 'B123',
        'B124', 'B125', 'B126', 'B127', 'B128', 'B129', 'B130', 'B131',
        'B132', 'B133', 'B134', 'B135', 'B136', 'B137', 'B138', 'B139',
        'B140', 'B141', 'B142', 'B143', 'B144', 'B145', 'B146', 'B147',
        'B148', 'B149', 'B150', 'B151', 'B152', 'B153', 'B153a', 'B154',
        'B154a', 'B154b', 'B154c', 'B155', 'B156', 'B157', 'B158', 'B159',
    ],
    "anaxagoras": [
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21',
        'B21a', 'B21b', 'B22', 'B23',
    ],
}

# The `text_columns` hint per work: the DK spine tokens whose Greek role
# profile carries a marked role='text' line (module docstring's
# classify_kind contract) -- the full retained spine minus each
# manifest's own declared `unmarked_columns` and `latin_fragments`
# (heraclitus: minus B4/B37/B130 Latin-only and the 17-entry
# unmarked_columns list, B138/B139 included since they too are unmarked;
# parmenides: minus B18 Latin-only; empedocles: minus B94 Latin-only and
# its unmarked_columns list; anaxagoras: no exclusions, all verbatim).
# Independent of `_BATCH_2_RAW_SPINES` and never derived from a first pass
# of parse_chapter.
_BATCH_2_TEXT_COLUMNS = {
    "heraclitus": {
        'B1', 'B2', 'B3', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11', 'B12',
        'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22',
        'B23', 'B24', 'B25', 'B26', 'B27', 'B28', 'B29', 'B30', 'B31', 'B32',
        'B34', 'B35', 'B36', 'B38', 'B39', 'B40', 'B41', 'B42', 'B43', 'B44',
        'B45', 'B46', 'B47', 'B48', 'B49', 'B49a', 'B50', 'B51', 'B56', 'B57',
        'B58', 'B59', 'B62', 'B63', 'B64', 'B65', 'B66', 'B67', 'B70', 'B71',
        'B73', 'B74', 'B75', 'B77', 'B78', 'B79', 'B80', 'B81', 'B84a',
        'B84b', 'B85', 'B86', 'B87', 'B88', 'B89', 'B90', 'B91', 'B92', 'B93',
        'B94', 'B95', 'B96', 'B97', 'B98', 'B99', 'B100', 'B101', 'B101a',
        'B102', 'B103', 'B104', 'B105', 'B106', 'B107', 'B108', 'B110',
        'B111', 'B112', 'B113', 'B114', 'B115', 'B116', 'B117', 'B118',
        'B119', 'B120', 'B121', 'B122', 'B123', 'B124', 'B125', 'B125a',
        'B126', 'B126a', 'B127', 'B128', 'B129', 'B131', 'B132', 'B133',
        'B134', 'B135', 'B137',
    },
    "parmenides": {
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B15a', 'B16', 'B17', 'B19', 'B20', 'B21',
        'B25',
    },
    "empedocles": {
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B8', 'B9', 'B10', 'B11', 'B12',
        'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B20', 'B21', 'B22',
        'B23', 'B24', 'B25', 'B26', 'B27', 'B27a', 'B28', 'B29', 'B30', 'B31',
        'B32', 'B33', 'B34', 'B35', 'B36', 'B37', 'B38', 'B39', 'B40', 'B41',
        'B42', 'B43', 'B44', 'B45', 'B46', 'B47', 'B48', 'B49', 'B50', 'B51',
        'B52', 'B53', 'B54', 'B55', 'B56', 'B57', 'B59', 'B60', 'B61', 'B62',
        'B63', 'B64', 'B65', 'B66', 'B67', 'B68', 'B69', 'B70', 'B71', 'B72',
        'B73', 'B74', 'B75', 'B76', 'B77', 'B79', 'B80', 'B81', 'B82', 'B83',
        'B84', 'B85', 'B86', 'B87', 'B88', 'B89', 'B90', 'B91', 'B93', 'B95',
        'B96', 'B98', 'B99', 'B100', 'B101', 'B102', 'B103', 'B104', 'B105',
        'B106', 'B107', 'B108', 'B109', 'B109a', 'B110', 'B111', 'B112',
        'B113', 'B114', 'B115', 'B116', 'B117', 'B118', 'B119', 'B120',
        'B121', 'B122', 'B123', 'B124', 'B125', 'B126', 'B127', 'B128',
        'B129', 'B130', 'B131', 'B132', 'B133', 'B134', 'B135', 'B136',
        'B137', 'B138', 'B139', 'B140', 'B141', 'B142', 'B143', 'B144',
        'B145', 'B146', 'B147', 'B148', 'B149', 'B150', 'B151', 'B153',
        'B154', 'B154a', 'B154c', 'B155', 'B156', 'B157',
    },
    "anaxagoras": {
        'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11',
        'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18', 'B19', 'B21', 'B21a',
        'B21b', 'B22',
    },
}

# One hand-quoted, distinctive literal phrase per work, verified against
# the raw fixture HTML directly (not the committed JSON). Heraclitus B81
# doubles as the exact-numbering-remap regression check (README: "the
# first printed B83->B81"): the fixture's SECOND paragraph literally
# labeled "83." is the one that must land on B81, immediately after the
# genuinely-labeled "82.".
_BATCH_2_REPRESENTATIVE_TEXT = {
    "heraclitus": ("B81", "Original chief of wranglers"),
    "parmenides": ("B2", "you must accept my word"),
    "empedocles": ("B17", "single One out of Many"),
    "anaxagoras": ("B12", "self-ruling"),
}

# Final (post-drop) group_header expectations, matching each committed
# freeman-<work>.group_headers.json exactly.
_BATCH_2_HEADER_EXPECTATION = {
    "heraclitus": [
        {"level": 2, "text": "Doubtful and spurious fragments",
         "before_column": "B126a"},
    ],
    "parmenides": [
        {"level": 2, "text": "Doubtful", "before_column": "B20"},
        {"level": 2, "text": "Spurious", "before_column": "B21"},
    ],
    "empedocles": [
        {"level": 2, "text": "Doubtful fragments", "before_column": "B154"},
        {"level": 2, "text": "Spurious fragments", "before_column": "B155"},
    ],
    # Anaxagoras' only raw header ("Spurious", before B23) is dropped along
    # with its orphan column B23 -- README: "is likewise absent from the
    # sidecar."
    "anaxagoras": [],
}


@pytest.mark.parametrize(
    ("chapter_file", "work", "english_orphans"),
    [
        ("app19.htm", "heraclitus", {"B109"}),
        ("app23.htm", "parmenides", set()),
        ("app26.htm", "empedocles", {"B149", "B150", "B154b"}),
        ("app54.htm", "anaxagoras", {"B20", "B23"}),
    ],
)
def test_burnet_flip_batch_2_matches_committed_extractions(
    chapter_file, work, english_orphans
):
    """The four reviewed batch-2 sacred-texts fixtures re-extract
    byte-for-byte, at the same fidelity standard as batch 1/Democritus.

    Heraclitus B109 and anaxagoras B20/B23 are declared English-only
    orphans (bare cross-reference or beyond-the-DK-spine entries).
    Empedocles B149/B150/B154b are also orphans from parse_chapter's own
    point of view: B149 and B150 are absorbed into compound B148 by a
    LATER pipeline stage (compound_n_map, not this parser -- unlike the
    genuine single "77, 78." printed heading that already yields just
    B77 unaided), and B154b has no DK6 column at all.
    """
    import json

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / chapter_file
    source_dir = root / "sources" / "freeman-ancilla"
    committed = json.loads(
        (source_dir / f"freeman-{work}.clean.json").read_text(encoding="utf-8")
    )
    committed_headers = json.loads(
        (source_dir / f"freeman-{work}.group_headers.json")
        .read_text(encoding="utf-8")
    )
    cols, headers = _mod.parse_chapter(
        fixture.read_text(encoding="utf-8"), _BATCH_2_TEXT_COLUMNS[work]
    )

    # Independent literal order/content checks (batch-1/finding-1
    # precedent), BEFORE the order-blind dict-equality check below.
    assert list(cols) == _BATCH_2_RAW_SPINES[work]
    rep_col, rep_phrase = _BATCH_2_REPRESENTATIVE_TEXT[work]
    assert rep_phrase in cols[rep_col]["text"]

    if work == "empedocles":
        # Reproduce the compound_n_map concatenation explicitly (module
        # docstring's "148,149,150" note) rather than silently matching
        # it by popping the absorbed columns unexamined.
        cols["B148"]["text"] = " ".join(
            [cols["B148"]["text"], cols["B149"]["text"], cols["B150"]["text"]]
        )

    assert set(cols) - set(committed) == english_orphans
    assert set(committed) - set(cols) == set()
    for orphan in english_orphans:
        cols.pop(orphan)
    assert cols == committed

    if work == "anaxagoras":
        headers = [
            h for h in headers if h["before_column"] not in english_orphans
        ]
    assert headers == _BATCH_2_HEADER_EXPECTATION[work]
    assert headers == committed_headers

# --- Freeman Ancilla phase 3: Thales, Philolaus, Gorgias, Prodicus,
# Hippias, Antiphon the Sophist, Critias (docs/phase3-sourcing-queue.md) --

_PHASE_3_TEXT_COLUMNS = {
    "thales": {"B1", "B3"},
    "philolaus": {
        "B1", "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B19",
        "B2", "B20", "B20a", "B21", "B22", "B23", "B3", "B4", "B5", "B6",
        "B7", "B8", "B9",
    },
    "gorgias": {
        "B10", "B12", "B13", "B15", "B16", "B17", "B2", "B20", "B21", "B22",
        "B23", "B24", "B26", "B27", "B3", "B4", "B5", "B5a", "B5b", "B6",
        "B7", "B8",
    },
    "prodicus": {"B1", "B4", "B6", "B7"},
    "hippias": {"B10", "B12", "B17", "B2", "B3", "B4", "B6", "B9"},
    "antiphon-sophist": {
        "B1", "B10", "B100", "B101", "B102", "B103", "B104", "B105", "B106",
        "B106a", "B107", "B108", "B109", "B11", "B110", "B111", "B112",
        "B113", "B114", "B115", "B116", "B117", "B12", "B14", "B15", "B16",
        "B17", "B18", "B19", "B2", "B20", "B21", "B22", "B23", "B24",
        "B24a", "B25", "B29", "B3", "B30", "B31", "B32", "B33", "B34",
        "B35", "B36", "B37", "B38", "B39", "B4", "B40", "B41", "B42",
        "B43", "B44", "B44a", "B45", "B46", "B47", "B48", "B49", "B5",
        "B50", "B51", "B52", "B53", "B53a", "B54", "B55", "B56", "B57",
        "B58", "B59", "B6", "B60", "B61", "B63", "B64", "B65", "B66",
        "B67", "B67a", "B68", "B69", "B7", "B70", "B71", "B72", "B73",
        "B74", "B75", "B76", "B77", "B78", "B8", "B82", "B83", "B84",
        "B85", "B86", "B87", "B88", "B89", "B9", "B90", "B91", "B92",
        "B93", "B93a", "B93b", "B94", "B95", "B96", "B97", "B98", "B99",
    },
    "critias": {
        "B1", "B10", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19",
        "B2", "B20", "B21", "B22", "B23", "B25", "B26", "B27", "B28", "B29",
        "B31", "B32", "B33", "B34", "B35", "B36", "B37", "B38", "B39", "B4",
        "B40", "B41", "B41a", "B42", "B44", "B46", "B48", "B49", "B5",
        "B51", "B53", "B54", "B55", "B56", "B57", "B58", "B59", "B6",
        "B60", "B61", "B62", "B63", "B64", "B65", "B66", "B67", "B68",
        "B69", "B7", "B70", "B71", "B72", "B73", "B75", "B8", "B9",
    },
}

# Freeman's own English-only orphan entries (no corresponding DK column),
# dropped from the committed clean JSON -- see each work's own manifest
# header note (Gorgias B28/Hippias B7 match declared `expected_gaps`;
# Critias' five entries are the three declared `expected_gaps` plus two
# further Oxyrhynchus-papyrus additions with no DK6 column at all).
_PHASE_3_ORPHANS = {
    "thales": set(),
    "philolaus": set(),
    "gorgias": {"B28"},
    "prodicus": set(),
    "hippias": {"B7"},
    "antiphon-sophist": set(),
    "critias": {"B11", "B12a", "B15a", "B24", "B74"},
}

# One hand-quoted, distinctive literal phrase per work, taken straight from
# the witness text (batch-1/finding-1 precedent) -- catches a bug that
# blanks or corrupts an entry while leaving dict-equality against the
# committed JSON intact only by coincidence.
_PHASE_3_REPRESENTATIVE_TEXT = {
    "thales": ("B3", "much-discussed four substances"),
    "philolaus": ("B1", "fitted together from the Non-Limited"),
    "gorgias": ("B2", "wrote a treatise 'On Nature'"),
    "prodicus": ("B6", "on the borderline between the philosopher and the statesman"),
    "hippias": ("B6", "Orpheus"),
    "antiphon-sophist": ("B29", "showers and contrary winds"),
    "critias": ("B1", "Anacreon, whom Teos gave to Greece"),
}


@pytest.mark.parametrize(
    ("chapter_file", "work"),
    [
        ("app13.htm", "thales"),
        ("app39.htm", "philolaus"),
        ("app77.htm", "gorgias"),
        ("app79.htm", "prodicus"),
        ("app81.htm", "hippias"),
        ("app82.htm", "antiphon-sophist"),
        ("app83.htm", "critias"),
    ],
)
def test_freeman_phase_3_matches_committed_extractions(chapter_file, work):
    """Phase 3 fidelity lock (docs/phase3-sourcing-queue.md): Thales,
    Philolaus, Gorgias, Prodicus, Hippias, Antiphon the Sophist, and
    Critias each re-extract from their reviewed sacred-texts fixture to
    the checked-in clean JSON and group-header sidecar, modulo the
    declared English-only orphans and (Hippias only) the documented
    page-break-split hand-fix (hippias-fragments.yaml's "EXTRACTION FIX"
    note)."""
    import json

    root = Path(__file__).resolve().parents[2]
    fixture = root / "pipeline" / "tests" / "fixtures" / "freeman" / chapter_file
    source_dir = root / "sources" / "freeman-ancilla"
    committed = json.loads(
        (source_dir / f"freeman-{work}.clean.json").read_text(encoding="utf-8")
    )
    committed_headers = json.loads(
        (source_dir / f"freeman-{work}.group_headers.json")
        .read_text(encoding="utf-8")
    )
    cols, headers = _mod.parse_chapter(
        fixture.read_text(encoding="utf-8"), _PHASE_3_TEXT_COLUMNS[work]
    )

    rep_col, rep_phrase = _PHASE_3_REPRESENTATIVE_TEXT[work]
    assert rep_phrase in cols[rep_col]["text"]

    orphans = _PHASE_3_ORPHANS[work]
    extra = set(cols) - set(committed)
    missing = set(committed) - set(cols)
    assert extra == orphans, f"unexpected extraction drift (extra): {extra - orphans}"
    assert missing == set(), f"unexpected extraction drift (missing): {missing}"
    for orphan in orphans:
        cols.pop(orphan)

    if work == "hippias":
        # B16's entry is split by sacred-texts across a page break into
        # two wholly-italic paragraphs; the extractor (correctly, per its
        # own documented L2-header taxonomy) reads the second half as a
        # bare group-header paratext label rather than a continuation.
        # The committed clean JSON merges it back onto B16 by hand;
        # reproduce that merge explicitly here rather than silently
        # matching it.
        continuation = next(
            h for h in headers
            if h["before_column"] == "B17" and h["text"].startswith("Envious people")
        )
        cols["B16"]["text"] = cols["B16"]["text"] + " " + continuation["text"]
        headers = [h for h in headers if h is not continuation]

    if work == "gorgias":
        # Freeman's "Doubtful" label originally precedes her own B28
        # English-only orphan (dropped above); it genuinely introduces
        # the B29-B31 "doubtful" maxims that follow, so the manifest
        # reattaches it to B29 rather than dropping it.
        headers = [
            {**h, "before_column": "B29"} if h["before_column"] == "B28" else h
            for h in headers
        ]

    if work == "critias":
        # Three per-fragment labels ("From 'Tennês'"/"'Rhadamanthys'"/
        # "'Peirithôus'") describe ONLY the dropped Oxyrhynchus-orphan
        # entries immediately following them and are withheld along with
        # that content; "Spurious or uncertain" (originally before the
        # dropped B74 gap) genuinely introduces the real B75 column that
        # follows and is reattached instead of dropped.
        headers = [
            h for h in headers
            if h["before_column"] not in {"B11", "B12a", "B15a"}
        ]
        headers = [
            {**h, "before_column": "B75"} if h["before_column"] == "B74" else h
            for h in headers
        ]

    for col in committed:
        assert cols[col]["kind"] == committed[col]["kind"], col
        assert cols[col]["text"] == committed[col]["text"], col
    assert headers == committed_headers
