"""stage1_dk_fills (John's ruling, 2026-09-29): a DK "FIRST ... LAST" whose
full text DK prints elsewhere is filled with the words between, located by
the Greek-free sources/dk-abbreviations/fills.json. The Greek below is
invented (letter names), never corpus text."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_dk_fills as F
from reader_pipeline.stage7_emit import chapter_ranges, emit_books

VERSE = {"citation": {"lines": True}}
PROSE = {"citation": {}}

# A fragment of three verse lines, and a source passage quoting it as
# "ἄλφα ... ζῆτα" -- the "..." sits at offset 30 of the context line.
CONTEXT = "ΠΗΓΗ 1, 2 ὡς λέγει ὁ ποιητής ‘ἄλφα ... ζῆτα’ καὶ τὰ λοιπά."
TEXT_LINES = [
    {"n": 1, "text": "ἄλφα βῆτα, γάμμα", "role": "text"},
    {"n": 2, "text": "δέλτα ἒ ψιλόν,", "role": "text"},
    {"n": 3, "text": "ζῆτα ἦτα θῆτα.", "role": "text"},
]
AT = CONTEXT.index("...")


def _source_lines():
    return [{"n": -1, "text": CONTEXT, "role": "context"}] + TEXT_LINES


def _loc(**target):
    t = {"work": "fix-fragments", "column": "B1", "role": "text",
         "from": 1, "after": 0, "to": 3, "before": 0}
    t.update(target)
    return {"work": "fix-fragments", "column": "B1", "role": "context", "n": -1,
            "at": AT, "left": 1, "right": 1, "target": t}


def test_verse_fill_is_the_words_between_joined_by_slashes():
    li, fill = F.resolve(_loc(), _source_lines(), _source_lines(), VERSE)
    assert li == 0
    assert fill == {"start": AT, "end": AT + 3, "text": "βῆτα, γάμμα / δέλτα ἒ ψιλόν,",
                    "kind": "verse", "abbrev": "ἄλφα ... ζῆτα"}
    assert CONTEXT[fill["start"]:fill["end"]] == "..."


def test_prose_fill_within_one_line_uses_the_stored_anchors():
    # "ἄλφα" recurs; the anchors, not a search, decide which one.
    target = [{"n": 1, "text": "ἄλφα βῆτα, γάμμα ἄλφα δέλτα ἒ καὶ ζῆτα.", "role": "text"}]
    source = [{"n": -1, "text": "ὁ δὲ λέγει ‘ἄλφα ... ζῆτα’.", "role": "context"}]
    loc = {"work": "w", "column": "B2", "role": "context", "n": -1, "at": source[0]["text"].index("..."),
           "left": 1, "right": 1,
           "target": {"work": "w", "column": "B2", "role": "text", "from": 1, "after": 0, "to": 1, "before": 7}}
    _, fill = F.resolve(loc, source, target, PROSE)
    assert fill["text"] == "βῆτα, γάμμα ἄλφα δέλτα ἒ καὶ"
    assert fill["kind"] == "prose"


def test_matching_ignores_accents_elision_says_word_and_a_cut_word():
    # Printed "ἐστὶ" matches the target's "ἐστι"; the inserted "φησίν" is
    # not a printed word; "γ." is a word cut short.
    target = [{"n": 1, "text": "ἄλφα βῆτα γάμμα ἐστι δέλτα καὶ ζῆτα", "role": "text"}]
    source = [{"n": -1, "text": "‘ἄλφα βῆτα γ. ἐστὶ, φησίν, ... ζῆτα’", "role": "context"}]
    loc = {"work": "w", "column": "B3", "role": "context", "n": -1, "at": source[0]["text"].index("..."),
           "left": 5, "right": 1,
           "target": {"work": "w", "column": "B3", "role": "text", "from": 1, "after": 3, "to": 1, "before": 6}}
    _, fill = F.resolve(loc, source, target, PROSE)
    assert fill["text"] == "δέλτα καὶ"
    assert fill["abbrev"] == "ἄλφα βῆτα γ. ἐστὶ, φησίν, ... ζῆτα"
    assert F._printed("γ. x", ("γ", 0, 1)) == ("γ", "prefix")
    assert F._same(F._printed("γ. x", ("γ", 0, 1)), F.norm("γάμμα"))
    assert F._same(F.norm("ἀλλ'"), F.norm("ἀλλά"))


def test_first_run_may_start_on_an_earlier_line():
    source = [{"n": 3, "text": "‘ἄλφα βῆτα", "role": "text"}, {"n": 4, "text": "γάμμα ... ζῆτα’", "role": "text"}]
    loc = {"work": "w", "column": "B4", "role": "text", "n": 4, "at": 6, "left": 3, "right": 1,
           "target": {"work": "w", "column": "B1", "role": "text", "from": 1, "after": 2, "to": 3, "before": 0}}
    _, fill = F.resolve(loc, source, TEXT_LINES, VERSE)
    assert fill["abbrev"] == "ἄλφα βῆτα γάμμα ... ζῆτα"
    assert fill["text"] == "δέλτα ἒ ψιλόν,"


@pytest.mark.parametrize("change, message", [
    ({"at": AT + 1}, "no '...' at offset"),
    ({"n": -2}, "0 lines with n=-2"),
    ({"target": {"work": "fix-fragments", "column": "B1", "role": "text",
                 "from": 1, "after": 1, "to": 3, "before": 0}}, "no longer match"),
    ({"target": {"work": "fix-fragments", "column": "B1", "role": "text",
                 "from": 1, "after": 0, "to": 9, "before": 0}}, "0 lines with n=9"),
    ({"target": {"work": "fix-fragments", "column": "B1", "role": "text",
                 "from": 1, "after": 0, "to": 3, "before": 7}}, "out of range"),
])
def test_a_locator_that_no_longer_matches_fails_loudly(change, message):
    loc = dict(_loc(), **change)
    with pytest.raises(F.DkFillError, match=re.escape(message)):
        F.resolve(loc, _source_lines(), _source_lines(), VERSE)


def test_a_prose_target_over_several_lines_is_refused():
    with pytest.raises(F.DkFillError, match="prose target must be one line"):
        F.resolve(_loc(), _source_lines(), _source_lines(), PROSE)


def test_kind_follows_the_target():
    assert F.fill_kind(VERSE, {"role": "text", "column": "B1"}, 1) == "verse"
    assert F.fill_kind({"citation": {"lines": True, "prose_columns": ["B1"]}},
                       {"role": "text", "column": "B1"}, 1) == "prose"
    assert F.fill_kind(PROSE, {"role": "context", "column": "A1"}, 2) == "verse"
    assert F.fill_kind(PROSE, {"role": "context", "column": "A1"}, 1) == "prose"


class _M:
    def __init__(self, work, data):
        self.work_id, self.data = work, data


def test_build_reads_another_works_column_for_a_cross_work_target():
    testimonia = {"segments": [{"id": "1:A1", "column": "A1",
                                "lines": [{"n": -1, "text": CONTEXT, "role": "context"}]}]}
    fragments = {"segments": [{"id": "1:B1", "column": "B1", "lines": TEXT_LINES}]}
    loc = dict(_loc(), work="fix-testimonia", column="A1")
    asked = []

    def spine_for(work):
        asked.append(work)
        return fragments, VERSE

    out = F.build(_M("fix-testimonia", PROSE), testimonia, [loc], spine_for)
    assert asked == ["fix-fragments"]
    assert out == {"1:A1": {"0": [{"start": AT, "end": AT + 3, "text": "βῆτα, γάμμα / δέλτα ἒ ψιλόν,",
                                   "kind": "verse", "abbrev": "ἄλφα ... ζῆτα"}]}}
    assert F.build(_M("other-work", PROSE), testimonia, [loc], spine_for) == {}


def test_stage7_attaches_fills_to_their_line_only(tmp_path):
    spine = {"work": "FIX", "segments": [
        {"id": "1:B1", "book": 1, "column": "B1", "lines": _source_lines()}]}
    tokens_doc = {"segments": [{"id": "1:B1", "lines": [{"n": ln["n"], "tokens": []} for ln in _source_lines()]}]}
    fill = {"start": AT, "end": AT + 3, "text": "x", "kind": "verse", "abbrev": "a ... b"}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(spine, tokens_doc, {"chunks": []}, chapter_ranges(spine, []), out_dir,
               dk_fills={"1:B1": {"0": [fill]}})
    greek = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))["segments"][0]["greek"]
    assert greek[0]["fills"] == [fill]
    assert greek[0]["text"] == CONTEXT
    assert all("fills" not in g for g in greek[1:])
    with pytest.raises(ValueError, match="no longer spans"):
        emit_books(spine, tokens_doc, {"chunks": []}, chapter_ranges(spine, []), out_dir,
                   dk_fills={"1:B1": {"1": [fill]}})


def test_locator_file_is_greek_free_and_well_formed():
    doc = json.loads(F.LOCATORS_PATH.read_text(encoding="utf-8"))
    assert not re.search("[Ͱ-Ͽἀ-῿]", F.LOCATORS_PATH.read_text(encoding="utf-8"))
    fills = doc["fills"]
    assert len(fills) == 178
    keys = {"survey", "work", "column", "role", "n", "at", "left", "right", "target"}
    tkeys = {"work", "column", "role", "from", "after", "to", "before"}
    for loc in fills:
        assert set(loc) == keys and set(loc["target"]) == tkeys
        assert loc["left"] >= 1 and loc["right"] >= 1
        assert (ROOT / "manifests" / f"{loc['work']}.yaml").exists()
        assert (ROOT / "manifests" / f"{loc['target']['work']}.yaml").exists()
    places = [(loc["work"], loc["column"], loc["n"], loc["role"], loc["at"]) for loc in fills]
    assert len(set(places)) == len(places)
