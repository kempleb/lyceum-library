"""Preflight gates for the lined source data shape."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from reader_pipeline.preflight import (
    WorkManifest,
    _validate_lined_indent_max,
    _validate_lined_source,
    _validate_greek_sections,
)


SEGMENT = "1:1.1"
BOOK_FILE = "book-01.json"


def _manifest(*, lined: bool = True, indent_max: int | None = None) -> WorkManifest:
    data = {"citation": {"lined_source": True}} if lined else {}
    if indent_max is not None:
        data["citation"]["lined_indent_max"] = indent_max
    return WorkManifest(work_id="discourses", path=Path("discourses.yaml"), data=data)


def _clean_greek() -> list[dict]:
    return [
        {
            "n": 1,
            "text": "Τῶν ἄλλων",
            "tokens": [{"t": "Τῶν", "o": 0}, {"t": "ἄλλων", "o": 4}],
            "sec": 1,
        },
        {
            # Mirrors the real emitted shape (build/dist/discourses/book-01.json
            # seg 1:1.1 greek[1]): the last token's surface `t` is the bare word
            # -- the sentence-final period that Schenkl prints right after the
            # absorbed continuation fragment is NOT part of `t`, it's a
            # letterless TAIL in `text` after the token's own [o, o+len(t))
            # span. See I3's 2026-08-29 amendment in docs/lined-source-plan.md.
            "n": 2,
            "text": "λέξις ἀποδοκιμαστικήν.",
            "tokens": [
                {"t": "λέξις", "o": 0},
                {"t": "ἀποδοκιμαστικήν", "o": 6},
            ],
            "sec": 1,
            "joined": True,
            # 5, not the plan's old arithmetic slip of 6: "ἀποδο-" (5 chars)
            # / "κιμαστικήν" (10 chars) is the real split (matches the actual
            # corpus wrap for this word, and the Reader-side fixtures in
            # shared/__tests__/reader-prose-flow.test.ts and speakers.test.ts)
            # -- kept self-consistent so nobody copies a wrong worked example.
            "wrap": 5,
            # wrapO deviation (2026-08-29, docs/lined-source-plan.md §3):
            # the wrapped token's own offset -- here it happens to equal the
            # LAST token's `o` (no em-dash glob in this fixture), but I3
            # validates against the token AT this offset, not "the last
            # token", so the two are independent facts about the data.
            "wrapO": 6,
        },
        {
            "n": 3,
            "text": "ἡ γραμματική",
            "tokens": [{"t": "ἡ", "o": 0}, {"t": "γραμματική", "o": 2}],
            "sec": 2,
        },
    ]


def _clean_sectionless_greek() -> list[dict]:
    greek = deepcopy(_clean_greek())
    for line in greek:
        del line["sec"]
    greek[0]["indent"] = 1
    return greek


def _lined_problems(
    greek: list[dict],
    *,
    lined: bool = True,
    indent_max: int | None = None,
) -> list[tuple[str, str, str]]:
    problems: list[tuple[str, str, str]] = []
    manifest = _manifest(lined=lined, indent_max=indent_max)
    observations: list[tuple[int, str, str]] = []
    _validate_lined_source(
        manifest, BOOK_FILE, SEGMENT, greek, problems, observations
    )
    _validate_lined_indent_max(
        manifest, observations, [(BOOK_FILE, SEGMENT)], problems
    )
    return problems


def _assert_one_fatal(problems: list[tuple[str, str, str]], text: str) -> None:
    assert len(problems) == 1
    work, file_name, message = problems[0]
    assert work == "discourses"
    assert file_name == BOOK_FILE
    assert SEGMENT in message
    assert text in message


def test_validate_lined_source_accepts_a_clean_uniform_sec_segment():
    assert _lined_problems(_clean_greek()) == []


def test_validate_lined_source_accepts_a_clean_sectionless_segment():
    assert _lined_problems(_clean_sectionless_greek()) == []


def test_validate_lined_source_finds_duplicate_n_from_the_data_shape_guard():
    greek = _clean_sectionless_greek()
    greek[1]["n"] = 1

    _assert_one_fatal(_lined_problems(greek, lined=False), "`n` values")


def test_validate_lined_source_rejects_wrap_equal_to_token_length():
    greek = deepcopy(_clean_greek())
    greek[1]["wrap"] = len(greek[1]["tokens"][-1]["t"])

    _assert_one_fatal(_lined_problems(greek), "0 < wrap <")


def test_validate_lined_source_rejects_wrap_without_joined():
    greek = deepcopy(_clean_greek())
    del greek[1]["joined"]

    _assert_one_fatal(_lined_problems(greek), "requires `joined`")


def test_validate_lined_source_rejects_joined_alone_on_a_non_final_line():
    greek = deepcopy(_clean_greek())
    del greek[1]["wrap"]
    del greek[1]["wrapO"]

    _assert_one_fatal(_lined_problems(greek), "only on the segment's last line")


def test_validate_lined_source_accepts_joined_alone_on_the_segment_final_line():
    greek = deepcopy(_clean_greek())
    greek[-1]["joined"] = True

    assert _lined_problems(greek) == []


def test_validate_lined_source_accepts_a_letterless_punctuation_tail():
    # The default clean fixture already carries a `.` tail after the wrap
    # token; a trailing space-then-punctuation tail must also be accepted.
    greek = deepcopy(_clean_greek())
    greek[1]["text"] += " "

    assert _lined_problems(greek) == []


def test_validate_lined_source_rejects_a_wrap_tail_containing_a_letter():
    greek = deepcopy(_clean_greek())
    greek[1]["text"] += "x"

    _assert_one_fatal(_lined_problems(greek), "no letter characters")


def test_validate_lined_source_rejects_wrapped_token_text_mismatch_at_its_own_offset():
    # The token AT `wrapO` (here still the last token -- no em-dash glob in
    # this fixture) must actually match `text` at that offset. Corrupting
    # the token's own `t` (same length, so `wrap`'s own bound stays valid)
    # isolates this one reason.
    greek = deepcopy(_clean_greek())
    greek[1]["tokens"][-1]["t"] = "ξξξξξξξξξξξξξξξ"

    _assert_one_fatal(_lined_problems(greek), "at its own offset")


def test_validate_lined_source_rejects_wrap_without_wrapo():
    # `wrapO` is required iff `wrap`; dropping only `wrapO` must FATAL.
    greek = deepcopy(_clean_greek())
    del greek[1]["wrapO"]

    _assert_one_fatal(_lined_problems(greek), "`wrap` and `wrapO` must be present together")


def test_validate_lined_source_rejects_wrapo_pointing_at_no_token():
    # `wrapO` must match some token's own `o` -- a value that lands between
    # tokens (or past the end) is a defect, not a silent no-op.
    greek = deepcopy(_clean_greek())
    greek[1]["wrapO"] = 999

    _assert_one_fatal(_lined_problems(greek), "does not match any token's `o`")


def test_validate_lined_source_accepts_an_em_dash_glob_with_a_token_after_the_wrapped_one():
    # docs/lined-source-plan.md §3's 2026-08-29 wrapO deviation, the real
    # defect this preflight change fixes (epicurus-letter-to-herodotus §53/
    # §69): whole-whitespace-token absorption can glue MORE than the
    # wrapped word onto a joined line when the source glues an em dash
    # straight onto the next word with no space -- "σχηματίζεσθαι—πολλὴν"
    # absorbs "πολλὴν" as a second, LAST token. `wrapO` names the WRAPPED
    # token ("σχηματίζεσθαι", not "πολλὴν") explicitly, `wrap` validates
    # against ITS length (13), and -- because a token follows it -- the
    # letterless-tail rule does NOT apply (the glob legitimately contains a
    # following word, not stray punctuation).
    greek = [
        {
            "n": 1,
            "text": "τῶν ὁμογενῶν σχηματίζεσθαι—πολλὴν",
            "tokens": [
                {"t": "τῶν", "o": 0},
                {"t": "ὁμογενῶν", "o": 4},
                {"t": "σχηματίζεσθαι", "o": 13},
                {"t": "πολλὴν", "o": 27},
            ],
            "sec": 53,
            "joined": True,
            "wrap": 9,
            "wrapO": 13,
        },
        {"n": 2, "text": "γὰρ ῥεῖ.", "tokens": [{"t": "γὰρ", "o": 0}, {"t": "ῥεῖ", "o": 4}], "sec": 53},
    ]
    assert _lined_problems(greek) == []


def test_validate_lined_source_rejects_sec_going_backwards():
    greek = deepcopy(_clean_greek())
    greek[1]["sec"] = 2
    greek[2]["sec"] = 1

    _assert_one_fatal(_lined_problems(greek), "must not decrease")


def test_validate_lined_source_rejects_sec_present_on_only_some_lines():
    greek = deepcopy(_clean_greek())
    del greek[1]["sec"]

    _assert_one_fatal(_lined_problems(greek), "present on some lines but not others")


def test_validate_lined_source_rejects_sec_and_sections_without_a_second_report():
    greek = deepcopy(_clean_greek())
    greek[1]["sections"] = [{"n": 1, "o": 0}]
    problems = _lined_problems(greek)
    for line in greek:
        _validate_greek_sections(_manifest(), BOOK_FILE, SEGMENT, line, problems)

    _assert_one_fatal(problems, "carry both `sec` and a `sections` key")


# --- indent: paragraph-opening first-line inset (John's ruling 2026-08-29) --

def test_validate_lined_source_accepts_indent_1_through_20_without_a_declaration():
    for level in (1, 2, 3, 7, 16, 20):
        greek = deepcopy(_clean_greek())
        greek[0]["indent"] = level
        assert _lined_problems(greek) == []


def test_validate_lined_source_rejects_indent_0():
    greek = deepcopy(_clean_greek())
    greek[0]["indent"] = 0

    _assert_one_fatal(_lined_problems(greek), "not an integer 1..20")


def test_validate_lined_source_rejects_indent_21():
    greek = deepcopy(_clean_greek())
    greek[0]["indent"] = 21

    _assert_one_fatal(_lined_problems(greek), "not an integer 1..20")


def test_validate_lined_source_rejects_a_non_integer_indent():
    greek = deepcopy(_clean_greek())
    greek[0]["indent"] = "1"

    _assert_one_fatal(_lined_problems(greek), "not an integer 1..20")


def test_validate_lined_source_rejects_indent_above_declared_max():
    greek = deepcopy(_clean_greek())
    greek[0]["indent"] = 8

    _assert_one_fatal(_lined_problems(greek, indent_max=7), "exceeds citation.lined_indent_max=7")


def test_validate_lined_source_rejects_stale_high_declared_indent_max():
    greek = deepcopy(_clean_greek())
    greek[0]["indent"] = 6

    _assert_one_fatal(_lined_problems(greek, indent_max=7), "is stale-high")


def test_validate_greek_sections_still_checks_a_non_lined_sections_fixture():
    line = {
        "n": 1,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 3}],
    }
    problems: list[tuple[str, str, str]] = []

    _validate_greek_sections(_manifest(lined=False), BOOK_FILE, SEGMENT, line, problems)

    _assert_one_fatal(problems, "falls inside token span")
