from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage5_lsj import (
    demote_band_first_sense,
    demote_roman_first_subsense,
    entry_html,
    lift_demoted_siblings,
)

# χείρ-shaped: an unnumbered first sense whose deepest child is a demoted
# "II." run -- the defect review item 99 fixes (8,091 LSJ entries).
XEIR_BEFORE = [
    (1, ""),
    (3, "2."),
    (3, "3."),
    (2, "II."),
    (3, "1."),
    (2, "III."),
]
XEIR_AFTER = [
    (1, ""),
    (2, "2."),
    (2, "3."),
    (1, "II."),
    (2, "1."),
    (1, "III."),
]

# ἁγνός-shaped: the unnumbered opening is a genuine preamble -- the romans
# below it are already correctly nested and must not move.
AGNOS = [
    (1, ""),
    (2, "I."),
    (2, "II."),
]


def test_xeir_shaped_entry_is_lifted():
    assert lift_demoted_siblings(XEIR_BEFORE) == XEIR_AFTER


def test_agnos_shaped_preamble_is_unchanged():
    assert lift_demoted_siblings(AGNOS) == AGNOS


def test_first_sense_numbered_i_is_unchanged():
    senses = [(1, "I."), (2, "II."), (2, "III.")]
    assert lift_demoted_siblings(senses) == senses


def test_single_sense_entry_is_unchanged():
    senses = [(1, "")]
    assert lift_demoted_siblings(senses) == senses


# ἀναβαίνω-shaped: the run stops at the next sense at or above the opener's
# own level -- a later, independently-numbered "B." band (and everything
# nested under it) is copied through unchanged, not lifted.
def test_run_stops_before_later_band():
    senses = [(1, ""), (2, "II"), (3, "1"), (2, "III"), (1, "B"), (2, "1")]
    expected = [(1, ""), (1, "II"), (2, "1"), (1, "III"), (1, "B"), (2, "1")]
    assert lift_demoted_siblings(senses) == expected


def test_second_sense_numbered_arabic_with_dot_is_unchanged():
    senses = [(1, ""), (2, "2.")]
    assert lift_demoted_siblings(senses) == senses


def test_second_sense_numbered_one_with_dot_is_unchanged():
    senses = [(1, ""), (2, "1.")]
    assert lift_demoted_siblings(senses) == senses


def test_second_sense_numbered_iii_is_unchanged():
    senses = [(1, ""), (2, "III")]
    assert lift_demoted_siblings(senses) == senses


def test_second_sense_numbered_letter_is_unchanged():
    senses = [(1, ""), (2, "A")]
    assert lift_demoted_siblings(senses) == senses


def test_whitespace_only_opener_with_padded_ii_is_lifted():
    senses = [(1, " "), (2, "II ")]
    expected = [(1, " "), (1, "II ")]
    assert lift_demoted_siblings(senses) == expected


def _sense(level: str, n: str) -> str:
    n_attr = f' n="{n}"' if n else ' n=""'
    return f'<sense level="{level}"{n_attr}>body</sense>'


def test_to_html_stamps_lifted_data_level():
    xml = "<div2 key=\"xei/r\">" + "".join(
        _sense(str(level), n.rstrip(".")) for level, n in XEIR_BEFORE
    ) + "</div2>"
    entry_el = etree.fromstring(xml)
    html = entry_html(entry_el)
    got = [int(m) for m in re.findall(r'data-level="(\d+)"', html)]
    assert got == [level for level, _n in XEIR_AFTER]


def test_div1_entry_is_not_lifted():
    # Lewis & Short's <div1> shape -- entry_html only lifts LSJ's <div2>.
    senses = [(1, ""), (2, "II")]
    xml = "<div1 key=\"amo\">" + "".join(
        _sense(str(level), n) for level, n in senses
    ) + "</div1>"
    entry_el = etree.fromstring(xml)
    html = entry_html(entry_el)
    got = [int(m) for m in re.findall(r'data-level="(\d+)"', html)]
    assert got == [level for level, _n in senses]


# ---------------------------------------------------------------------------
# demote_band_first_sense -- review item 99, second shape: a letter band's
# own unnumbered first sense left at the band's level (reading as a second
# band) instead of demoted to join the roman run beneath it.

# arari/skw-shaped: "A. ... join together ... II. fit together ... III. ...
# IV. ... B. ..." -- Perseus gives A. and the unnumbered "join together" the
# same level, so the run reads as a rival band instead of A's own division I.
ARARISKO_BEFORE = [
    (1, "A."),
    (1, ""),
    (2, "II."),
    (2, "III."),
    (2, "IV."),
    (1, "B."),
    (2, "1."),
]
ARARISKO_AFTER = [
    (1, "A."),
    (2, ""),
    (2, "II."),
    (2, "III."),
    (2, "IV."),
    (1, "B."),
    (2, "1."),
]


def test_band_opener_demoted_to_join_roman_run():
    assert demote_band_first_sense(ARARISKO_BEFORE) == ARARISKO_AFTER


def test_band_preamble_followed_by_i_is_unchanged():
    # The band's unnumbered opener is a genuine preamble (already nested
    # correctly) when what follows it one level down is "I.", not "II." --
    # same guard as lift_demoted_siblings, same reason.
    senses = [(1, "A."), (1, ""), (2, "I."), (2, "II."), (1, "B.")]
    assert demote_band_first_sense(senses) == senses


def test_unnumbered_sense_not_after_a_letter_is_unchanged():
    # The same shape, but the same-level predecessor is roman ("II."), not
    # a letter address -- not a band opener, so it must not move.
    senses = [(1, "II."), (1, ""), (2, "II."), (2, "III.")]
    assert demote_band_first_sense(senses) == senses


# ---------------------------------------------------------------------------
# demote_roman_first_subsense -- review item 99, third shape: a division's
# first sub-sense, demoted to the division's own level, whose printed "1."
# also arrives as the OCR-confusable "I.".

# spouda/zw-shaped: division "II." whose own first sub-sense misreads "I."
# for "1." and sits at II.'s level instead of one below it.
SPOUDAZO_BEFORE = [
    (1, "II."),
    (1, "I."),
    (2, "2."),
]
SPOUDAZO_AFTER = [
    (1, "II."),
    # Relabeled undotted, matching Perseus's own n="1" (no trailing period
    # in the source attribute; entry_html supplies it on render).
    (2, "1"),
    (2, "2."),
]


def test_roman_first_subsense_demoted_and_relabeled():
    assert demote_roman_first_subsense(SPOUDAZO_BEFORE) == SPOUDAZO_AFTER


def test_i_without_preceding_roman_sibling_is_unchanged():
    # phre/n-shaped: "I. midriff ... 2. heart ... 3. mind ... 4. will" is an
    # ordinary division with sub-senses, already correctly nested -- no
    # roman sibling precedes "I." at its own level, so it must not move.
    senses = [(1, "A."), (1, "I."), (2, "2."), (2, "3.")]
    assert demote_roman_first_subsense(senses) == senses


def test_i_after_non_roman_sibling_is_unchanged():
    # The predecessor at "I."'s own level exists but is a letter address,
    # not a roman numeral -- the roman series isn't "already open", so the
    # guard must hold.
    senses = [(1, "A."), (1, "I."), (2, "2.")]
    assert demote_roman_first_subsense(senses) == senses


def test_run_not_opening_on_2_is_unchanged():
    # The demoted-looking "I." is followed by a run that does not open on
    # "2." -- not the sub-sense-numbering artifact, so it must not move.
    senses = [(1, "II."), (1, "I."), (2, "II.")]
    assert demote_roman_first_subsense(senses) == senses


def test_restarted_roman_series_is_unchanged():
    # w(s-shaped (Grok review, 2026-09-24): band B. first lists its divisions
    # I.-IV. as a summary, then restarts I., II., ... to treat each in full.
    # The restarted "I." follows "IV." and is followed by "II." -- a new
    # roman series, not a misread "1.", so it must not move. (The artifact
    # "I." sits inside a series: the next roman sibling continues from the
    # one before it, as in spouda/zw "I. intr. ... II. trans.".)
    senses = [
        (1, "B."),
        (2, "I."), (2, "II."), (2, "III."), (2, "IV."),
        (2, "I."), (3, "2."),
        (2, "II."), (3, "2."),
    ]
    assert demote_roman_first_subsense(senses) == senses


def test_artifact_i_inside_a_continuing_series_still_moves():
    # prin/e)pitugxa/nw-shaped: the roman sibling after the artifact "I."
    # continues the series from the one before it (I. -> II., II. -> III.).
    senses = [(2, "I."), (2, "I."), (3, "2."), (2, "II.")]
    assert demote_roman_first_subsense(senses) == [(2, "I."), (3, "1"), (3, "2."), (2, "II.")]
    senses = [(1, "II."), (1, "I."), (2, "2."), (1, "III.")]
    assert demote_roman_first_subsense(senses) == [(1, "II."), (2, "1"), (2, "2."), (1, "III.")]


def test_band_opener_demotion_reflected_in_entry_html():
    # ararisko-shaped entry run through the full stage5 pipeline: the band
    # fix demotes the opener, and each <sense>'s data-level/text reflect it.
    xml = "<div2 key=\"a)rari/skw\">" + "".join(
        _sense(str(level), n.rstrip(".")) for level, n in ARARISKO_BEFORE
    ) + "</div2>"
    entry_el = etree.fromstring(xml)
    html = entry_html(entry_el)
    got = [int(m) for m in re.findall(r'data-level="(\d+)"', html)]
    assert got == [level for level, _n in ARARISKO_AFTER]


def test_roman_relabel_reflected_in_entry_html():
    # spoudazo-shaped entry: the mis-glyphed "I." must show up in the HTML
    # as "1.", not just move level.
    xml = "<div2 key=\"spouda/zw\">" + "".join(
        _sense(str(level), n.rstrip(".")) for level, n in SPOUDAZO_BEFORE
    ) + "</div2>"
    entry_el = etree.fromstring(xml)
    html = entry_html(entry_el)
    got_levels = [int(m) for m in re.findall(r'data-level="(\d+)"', html)]
    assert got_levels == [level for level, _n in SPOUDAZO_AFTER]
    got_numerals = re.findall(r'lsj-sense-n">([^<]+)\.</b>', html)
    assert got_numerals == ["II", "1", "2"]
