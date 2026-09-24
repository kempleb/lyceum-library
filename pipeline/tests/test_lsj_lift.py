from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage5_lsj import entry_html, lift_demoted_siblings

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
