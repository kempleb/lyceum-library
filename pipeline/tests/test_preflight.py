from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from reader_pipeline.preflight import (
    WorkManifest,
    _check_token_walk,
    _collect_token_keys,
    _validate_english_paras,
    _validate_form_lemmata_shape,
    _validate_greek_sections,
    _validate_lsj_keys,
    _validate_manifest_schema,
    _validate_mounted_form_lemmata,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "pipeline" / "tests" / "fixtures" / "preflight"
# Self-contained schema-only manifest fixtures (tests/fixtures/preflight/manifests/),
# not the repo-root manifests/ dir (which this repo does not populate/commit).
MANIFESTS = FIXTURES / "manifests"


def _load_manifest(name: str) -> dict:
    return yaml.safe_load((MANIFESTS / name).read_text(encoding="utf-8"))


def _schema_problems(data: dict, name: str = "Euthyphro.yaml") -> list[str]:
    manifest = WorkManifest(work_id=data["work"]["id"], path=MANIFESTS / name, data=data)
    problems: list = []
    _validate_manifest_schema(manifest, problems)
    return [message for _work, _file, message in problems]


def _run_preflight(name: str) -> subprocess.CompletedProcess[str]:
    fixture = FIXTURES / name
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "reader_pipeline.preflight",
            str(fixture / "data"),
            str(fixture / "manifests"),
        ],
        cwd=ROOT / "pipeline",
        text=True,
        capture_output=True,
        check=False,
    )


def test_preflight_valid_fixture_passes():
    result = _run_preflight("valid")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "preflight ok:" in result.stdout


def test_preflight_broken_fixture_reports_bekker_order_and_dangling_reference():
    result = _run_preflight("broken")

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "Greek Bekker lines are out of order" in output
    assert "chapter '1' has dangling Bekker anchor 1094a5" in output


# --- search/form_lemmata.json shape (Sol re-review #2, 2026-09-23) -----------

def test_validate_form_lemmata_shape_accepts_the_real_contract():
    problems: list = []
    _validate_form_lemmata_shape(
        "TST", "search/form_lemmata.json", {"pasa": ["pas"], "ambig": ["bar", "foo"]}, problems
    )
    assert problems == []


def test_validate_form_lemmata_shape_rejects_non_object():
    problems: list = []
    _validate_form_lemmata_shape("TST", "search/form_lemmata.json", ["pasa"], problems)
    assert any("must be an object" in p for _w, _f, p in problems)


def test_validate_form_lemmata_shape_rejects_empty_value_array():
    problems: list = []
    _validate_form_lemmata_shape("TST", "search/form_lemmata.json", {"pasa": []}, problems)
    assert any("must be a non-empty array" in p for _w, _f, p in problems)


def test_validate_form_lemmata_shape_rejects_non_string_values():
    problems: list = []
    _validate_form_lemmata_shape("TST", "search/form_lemmata.json", {"pasa": [1]}, problems)
    assert any("must be an array of strings" in p for _w, _f, p in problems)


def test_validate_form_lemmata_shape_rejects_unsorted_values():
    problems: list = []
    _validate_form_lemmata_shape("TST", "search/form_lemmata.json", {"ambig": ["foo", "bar"]}, problems)
    assert any("must be sorted" in p for _w, _f, p in problems)


def test_validate_form_lemmata_shape_rejects_key_equal_to_one_of_its_own_values():
    problems: list = []
    _validate_form_lemmata_shape("TST", "search/form_lemmata.json", {"pas": ["pas"]}, problems)
    assert any("must not include its own key" in p for _w, _f, p in problems)


def test_validate_mounted_form_lemmata_skips_native_work_dirs(tmp_path):
    # A directory whose name IS a native work id is _validate_work_data's
    # job (the required-file check), never this scan's -- even with a
    # malformed file, the mounted scan must not double-report it.
    work_dir = tmp_path / "VAL" / "search"
    work_dir.mkdir(parents=True)
    (work_dir / "form_lemmata.json").write_text(json.dumps({"pasa": []}), encoding="utf-8")
    problems: list = []
    _validate_mounted_form_lemmata(tmp_path, {"VAL"}, problems)
    assert problems == []


def test_validate_mounted_form_lemmata_is_a_noop_when_the_file_is_absent(tmp_path):
    (tmp_path / "MOUNTED").mkdir()
    problems: list = []
    _validate_mounted_form_lemmata(tmp_path, set(), problems)
    assert problems == []


def test_validate_mounted_form_lemmata_flags_a_present_but_malformed_file(tmp_path):
    work_dir = tmp_path / "MOUNTED" / "search"
    work_dir.mkdir(parents=True)
    (work_dir / "form_lemmata.json").write_text(json.dumps({"pasa": []}), encoding="utf-8")
    problems: list = []
    _validate_mounted_form_lemmata(tmp_path, set(), problems)
    assert any("must be a non-empty array" in p for _w, _f, p in problems)


def test_preflight_valid_fixture_fails_when_native_form_lemmata_is_missing():
    # End-to-end counterpart: stage7_emit.py writes search/form_lemmata.json
    # unconditionally for every native work, so its absence at dist level is
    # an emission regression this gate must catch, not a graceful skip.
    path = FIXTURES / "valid" / "data" / "VAL" / "search" / "form_lemmata.json"
    original = path.read_text(encoding="utf-8")
    try:
        path.unlink()
        result = _run_preflight("valid")
        assert result.returncode != 0
        assert "search/form_lemmata.json: emitted JSON file is missing" in (result.stdout + result.stderr)
    finally:
        path.write_text(original, encoding="utf-8")


def test_preflight_valid_fixture_fails_when_a_mounted_work_carries_a_malformed_form_lemmata():
    # The "valid" fixture's manifests/ only declares VAL, so a second work
    # directory dropped into its data/ with no matching manifest is exactly
    # the mounted-corpus shape this preflight run cannot otherwise see.
    mounted_dir = FIXTURES / "valid" / "data" / "MOUNTED"
    try:
        (mounted_dir / "search").mkdir(parents=True)
        # An entry whose key is among its own values -- unambiguously invalid.
        (mounted_dir / "search" / "form_lemmata.json").write_text(
            json.dumps({"pas": ["pas"]}), encoding="utf-8"
        )
        result = _run_preflight("valid")
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "MOUNTED: search/form_lemmata.json" in output
        assert "must not include its own key" in output
    finally:
        shutil.rmtree(mounted_dir, ignore_errors=True)


def test_preflight_schema_accepts_real_stephanus_manifests():
    # A section-scheme manifest carries no bekker_range/chapters and no
    # work.english_translation; it must pass the scheme-dispatched schema.
    assert _schema_problems(_load_manifest("Euthyphro.yaml")) == []
    assert _schema_problems(_load_manifest("Republic.yaml"), "Republic.yaml") == []


def test_preflight_schema_rejects_bad_section_token_and_missing_spine():
    data = _load_manifest("Euthyphro.yaml")
    data["books"][0]["start"] = "2z9"  # not a page+section token
    del data["section_spine"]  # the observed-spine fingerprint is required
    problems = _schema_problems(data)
    assert any("books[0].start must be a Stephanus section token" in p for p in problems)
    assert any("section_spine must be an object" in p for p in problems)


# --- book-section scheme (Marcus Aurelius-style "4.23" dotted tokens) ---------

def _load_book_section_manifest() -> dict:
    path = FIXTURES / "book_section" / "manifests" / "MED.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_preflight_token_walk_broken_fixture_is_fatal_end_to_end():
    # Integration counterpart to the _check_token_walk unit tests below: runs
    # the exact historical defect (interior siglum `<ν>` stripped from `t`
    # while `text` keeps it) through the REAL call site in _validate_books,
    # not just the isolated function. If that call site is ever deleted (the
    # scenario the Sol review warned about -- reverting the gate leaves the
    # whole suite green), this is the test that would catch it, since the
    # unit tests below call `_check_token_walk` directly and would not.
    result = _run_preflight("token_walk_broken")

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "fail the sequential text.find(t, ptr) walk" in output
    assert "ὁμολογεῖν" in output


def test_preflight_book_section_fixture_passes():
    # End-to-end round-trip: a valid book-section manifest AND its emitted data
    # (dotted columns in book-NN.json / columns.json) validate cleanly.
    result = _run_preflight("book_section")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "preflight ok:" in result.stdout


def test_preflight_book_section_schema_accepts_dotted_book_boundaries():
    assert _schema_problems(_load_book_section_manifest(), "MED.yaml") == []


def test_preflight_accepts_a_valid_div_types_section_override():
    # citation.div_types.section (Diogenes Laertius' TEI nests
    # div[@type="section"], not book-section's registered "chapter" default —
    # see scheme.py's for_manifest) is a recognized, schema-valid override.
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = {"section": "section"}
    assert _schema_problems(data, "MED.yaml") == []


def test_preflight_rejects_an_unknown_div_types_override_key():
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = {"bogus": "section"}
    problems = _schema_problems(data, "MED.yaml")
    assert any("citation.div_types" in p and "unknown" in p for p in problems), problems


def test_preflight_rejects_a_non_object_div_types():
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = "section"
    problems = _schema_problems(data, "MED.yaml")
    assert any("citation.div_types must be an object" in p for p in problems), problems


# --- Blocker 3: citation.div_types override VALUES must be validated (Sol) ---


def test_preflight_rejects_an_empty_string_div_types_value():
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = {"page": ""}
    problems = _schema_problems(data, "MED.yaml")
    assert any("citation.div_types.page must be a non-empty string" in p for p in problems), problems


def test_preflight_rejects_a_non_string_div_types_value():
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = {"section": 5}
    problems = _schema_problems(data, "MED.yaml")
    assert any("citation.div_types.section must be a non-empty string" in p for p in problems), problems


def test_preflight_accepts_div_types_with_both_page_and_section_set():
    # De Officiis' real shape (PHI lowercases both the outer "book" div and
    # nests "section" directly) — both overrides declared together must
    # still pass clean.
    data = _load_book_section_manifest()
    data["citation"]["div_types"] = {"page": "book", "section": "section"}
    assert _schema_problems(data, "MED.yaml") == []


# --- Blocker 2: english omission on book-section gated by the manifest's --
# --- OWN declaration, not scheme shape alone (Sol) -------------------------


def test_preflight_meditations_shaped_manifest_missing_english_fails():
    # A Meditations-shaped (book-section, no work.no_english declaration)
    # manifest that is simply missing its `english` block — a genuine
    # extraction bug — must FAIL, not silently pass because book-section
    # (numeric_section) scheme shape alone used to grant the relaxation.
    data = _load_book_section_manifest()
    del data["english"]
    problems = _schema_problems(data, "MED.yaml")
    assert any("english" in p and "must be an object" in p for p in problems), problems


def test_preflight_book_section_manifest_declaring_no_english_passes():
    # De Officiis' actual shape: the manifest's OWN `work.no_english: true`
    # declaration is what legitimizes the omission.
    data = _load_book_section_manifest()
    del data["english"]
    data["work"]["no_english"] = True
    assert _schema_problems(data, "MED.yaml") == []


def test_preflight_rejects_non_bool_no_english():
    data = _load_book_section_manifest()
    data["work"]["no_english"] = "yes"
    problems = _schema_problems(data, "MED.yaml")
    assert any("work.no_english must be a boolean" in p for p in problems), problems


def test_preflight_no_english_true_with_english_present_still_requires_well_formed_primary():
    # Declaring no_english: true does not exempt a manifest that ALSO
    # declares `english` from the normal english.primary schema checks —
    # the relaxation only ever applies when `english` is actually absent.
    data = _load_book_section_manifest()
    data["work"]["no_english"] = True
    data["english"] = {}
    problems = _schema_problems(data, "MED.yaml")
    assert any("english.primary must be an object" in p for p in problems), problems


def test_preflight_rejects_no_english_true_together_with_english_block():
    # MAJOR 3 (verse-line English gate-hardening, adversarial review): a
    # manifest declaring BOTH work.no_english: true AND an english: block is
    # self-contradictory -- must fail schema validation naming both keys, not
    # silently pass and let stage1's verse-line dispatch (__main__.py)
    # resolve the ambiguity by dispatching on "english" presence alone.
    data = _load_book_section_manifest()
    assert "english" in data  # MED.yaml's baseline shape carries english
    data["work"]["no_english"] = True
    problems = _schema_problems(data, "MED.yaml")
    assert any(
        "no_english" in p and "english" in p and "mutually exclusive" in p
        for p in problems
    ), problems


# --- flat `section`-scheme no_english relaxation (Wave 2 Batch 3 round 2, --
# --- extending _no_english_allowed from book-section/verse-line only) ------


def _load_flat_latin_manifest() -> dict:
    return _load_manifest("FlatLatin.yaml")


def test_preflight_flat_section_manifest_declaring_no_english_passes():
    # Cato Maior/Laelius/De Fato/Lucullus/Paradoxa's actual shape: a flat
    # `section`-scheme work may now also omit `english` when its OWN
    # manifest declares `work.no_english: true` — previously only
    # book-section/verse-line had this relaxation; Enchiridion (the only
    # prior flat work) always carried real English, so this path was never
    # exercised for flat_numeric before.
    data = _load_flat_latin_manifest()
    assert "english" not in data
    assert _schema_problems(data, "FlatLatin.yaml") == []


def test_preflight_flat_section_manifest_missing_english_without_declaration_fails():
    # Without work.no_english: true, an absent `english` block on a flat
    # work is still a genuine extraction bug (mirrors Meditations' own
    # book-section-shaped test above) — scheme shape alone must not grant
    # the relaxation.
    data = _load_flat_latin_manifest()
    del data["work"]["no_english"]
    problems = _schema_problems(data, "FlatLatin.yaml")
    assert any("english" in p and "must be an object" in p for p in problems), problems


def test_preflight_book_section_schema_rejects_lexicographic_and_bad_tokens():
    data = _load_book_section_manifest()
    # "1.10" then "1.9": lexicographically "1.10" < "1.9", so a string-sort bug
    # would silently accept this reversed range. Numeric comparison (10 > 9)
    # must flag it — this is the regression guard for the dotted sort key.
    data["books"] = [
        {"n": 1, "start": "1.10", "end": "1.9"},
        {"n": 2, "start": "2a", "end": "2.5"},  # "2a" is a letter token, not dotted
    ]
    problems = _schema_problems(data, "MED.yaml")
    assert any("books[0] start must not be after end" in p for p in problems)
    assert any("books[1].start must be a book.section token" in p for p in problems)


# --- chapter_concordance on the book-section (numeric_section) scheme, De ---
# --- Finibus phase 3: widened from flat_numeric-only (De Fato) -------------


def test_preflight_book_section_accepts_chapter_concordance_model():
    # De Finibus' actual shape: a book-section (numeric_section) manifest
    # whose english.primary.model is "chapter_concordance" (Yonge's
    # chapter-span translation, stage1_chapter_concordance_english.py) --
    # previously only the flat 'section' scheme (De Fato) passed this gate;
    # __main__.py's numeric_section dispatch already runs this builder, so
    # preflight must accept it too instead of flagging a false positive.
    data = _load_book_section_manifest()
    data["english"]["primary"]["model"] = "chapter_concordance"
    data["english"]["primary"]["concordance"] = "fixture/med-concordance.json"
    assert _schema_problems(data, "MED.yaml") == []


def test_preflight_book_section_chapter_concordance_still_requires_concordance_file():
    # The dedicated concordance-file gate (below the scheme-scoping check
    # above) still applies on book-section exactly as it already does on
    # flat_numeric -- a manifest that sets the model but forgets the second
    # source file must still fail loudly, not just at a raw KeyError deep in
    # stage1.
    data = _load_book_section_manifest()
    data["english"]["primary"]["model"] = "chapter_concordance"
    problems = _schema_problems(data, "MED.yaml")
    assert any(
        "english.primary.concordance must be a non-empty string" in p for p in problems
    ), problems


# --- _collect_token_keys: explicit token schema (gap: structurally invalid tokens) ---

def _token_problems(token: dict) -> list[str]:
    manifest = WorkManifest(work_id="TST", path=MANIFESTS / "Euthyphro.yaml", data={})
    problems: list = []
    _collect_token_keys(manifest, "file.json", "seg1", {"tokens": [token]}, set(), problems)
    return [message for _work, _file, message in problems]


def test_collect_token_keys_rejects_an_empty_token_object():
    # {} has neither `t` nor `o`. The old required-k rule (a token with no
    # `k` is assumed non-lexical and valid) let this slip through silently,
    # since a non-lexical token legitimately has no `k` either — both must
    # now be flagged as their own distinct problems.
    problems = _token_problems({})
    assert any("token.t must be a non-empty string" in p for p in problems), problems
    assert any("token.o must be a non-negative integer" in p for p in problems), problems


def test_collect_token_keys_rejects_a_token_missing_o():
    problems = _token_problems({"t": "λόγος"})
    assert problems == ["seg1: token.o must be a non-negative integer"]


def test_collect_token_keys_rejects_a_token_missing_t():
    problems = _token_problems({"o": 0})
    assert problems == ["seg1: token.t must be a non-empty string"]


def test_collect_token_keys_still_rejects_an_empty_k():
    # Regression guard: the explicit-schema fix must not weaken this
    # pre-existing check — a present-but-empty `k` is still invalid.
    problems = _token_problems({"t": "λόγος", "o": 0, "k": ""})
    assert problems == ["seg1: token.k must be a non-empty string"]


def test_collect_token_keys_accepts_a_well_formed_non_lexical_token():
    # A genuinely non-lexical token (no `k` at all, e.g. inline apparatus)
    # with valid `t`/`o` must still pass with no problems.
    assert _token_problems({"t": "Zeller", "o": 6}) == []


def test_collect_token_keys_rejects_a_whitespace_only_t():
    # FINDING 3 (must-fail-first): {"t": " ", "o": 0} passed the old rule
    # (`not isinstance(t, str) or not t`) because a whitespace-only string is
    # still truthy in Python — it slipped through as if it were a real
    # token. It must be rejected with its own distinct message, not folded
    # into the empty-string case.
    problems = _token_problems({"t": " ", "o": 0})
    assert problems == ["seg1: token.t must not be whitespace-only"]


def test_collect_token_keys_rejects_a_tab_and_newline_only_t():
    # Any whitespace-only `t`, not just a single space, must be rejected.
    problems = _token_problems({"t": "\t\n", "o": 0})
    assert problems == ["seg1: token.t must not be whitespace-only"]


# --- _check_token_walk: FATAL gate mirroring shared/lib/speakers.ts's render-time walk ---
#
# This is the sole enforcement for the token/text surface contract (stage3_tokenize.py's
# module docstring, CLAUDE.md defect B): `t` must be a literal, in-order-findable
# substring of `text`, and `o` must point at that same span. A GPT-5.6-Sol-High
# adversarial review flagged this gate as having zero test coverage — reverting it
# would leave the whole suite green. These tests pin it down.


def test_check_token_walk_reports_a_leapfrog_cascade_not_just_one_failure():
    # Mirrors the renderer's non-advancing-pointer-on-miss behavior (see the
    # function's own docstring): a single corrupted token (`t` matches far AHEAD
    # of its true position) advances `ptr` past several genuinely-earlier tokens,
    # so each of THEM fails to find too, since a failed find leaves `ptr`
    # unchanged rather than resyncing. One bad token therefore cascades into
    # multiple walk failures, not one -- exactly the >15,000-char leapfrog
    # measured in the Discourses build.
    text = "one two three four five"
    line = {
        "text": text,
        "tokens": [
            {"t": "four", "o": 14},  # corrupted: matches the 4th word, not the 1st
            {"t": "two", "o": 4},  # true position (index 4) is now BEHIND ptr=18
            {"t": "three", "o": 8},  # true position (index 8) is also behind ptr=18
            {"t": "four", "o": 14},  # already consumed above; also behind ptr=18
            {"t": "five", "o": 19},  # still ahead of ptr=18 -- this one recovers
        ],
    }
    wf, om = _check_token_walk("1094a", 1, line)

    assert len(wf) == 3
    assert "two" in wf[0]
    assert "three" in wf[1]
    assert "four" in wf[2]
    assert om == []


def test_check_token_walk_flags_a_wrong_offset_on_an_otherwise_findable_token():
    # The token IS findable (walk succeeds), but its `o` does not point at its
    # own `t` -- the offset check must fire independently of the walk check.
    line = {
        "text": "alpha beta",
        "tokens": [
            {"t": "alpha", "o": 0},
            {"t": "beta", "o": 0},  # wrong: "beta" is actually at offset 6
        ],
    }
    wf, om = _check_token_walk("1094a", 2, line)

    assert wf == []
    assert len(om) == 1
    assert "beta" in om[0] and "o=0" in om[0]


def test_check_token_walk_fatal_on_interior_siglum_stripped_from_t():
    # The exact historical defect (CLAUDE.md defect B / stage3_tokenize.py's
    # docstring): the source line keeps the Schenkl supplement's `<`/`>` marks
    # INSIDE the word (`ὁμολογεῖ<ν>`), but a broken emitter strips them from
    # `t` (`ὁμολογεῖν`) while `text` still has them -- so `t` is no longer a
    # literal substring of `text` and the walk must fail.
    line = {
        "text": "ζητοῦμεν εἰ ὁμολογεῖ<ν> ἔοικε",
        "tokens": [
            {"t": "ζητοῦμεν", "o": 0},
            {"t": "εἰ", "o": 9},
            {"t": "ὁμολογεῖν", "o": 12},  # BROKEN: should be "ὁμολογεῖ<ν>"
            {"t": "ἔοικε", "o": 24},
        ],
    }
    wf, om = _check_token_walk("1094a", 3, line)

    assert len(wf) == 1
    assert "ὁμολογεῖν" in wf[0]


def test_check_token_walk_passes_edge_punctuation_and_a_kept_interior_siglum():
    # Positive control: edge punctuation (curly quotes, comma) glued to a word
    # that ALSO carries a kept-verbatim interior siglum, with exact offsets --
    # this is the well-formed shape stage3_tokenize.py actually emits, and the
    # gate must pass it cleanly (no walk failures, no offset mismatches).
    text = "“ὁμολογεῖ<ν>,” φησίν."
    line = {
        "text": text,
        "tokens": [
            {"t": "“ὁμολογεῖ<ν>,”", "o": 0},
            {"t": "φησίν.", "o": 15},
        ],
    }
    wf, om = _check_token_walk("1094a", 4, line)

    assert wf == []
    assert om == []


# --- _validate_greek_sections / _validate_english_paras: FATAL gate for the
# section-paragraphing channels (Discourses/Enchiridion's `sections`/`paras`
# -- see stage1_greek._chapter_sections and stage1_book_section_english.py's
# paras sidecar). A GPT-5.6-Sol-High adversarial review found no preflight
# coverage for these channels at all: a bad offset (landing inside a Greek
# token's span -- exactly the shape Reader.svelte's splitGreekSections was
# fixed to render safely, never to receive from bad data) or descending
# `paras` offsets would reach the build with no gate. These tests pin the
# new gate down, both at the unit level (direct calls, like _check_token_walk
# above) and end-to-end through the real _validate_books call site.

def _manifest(work_id: str = "VAL") -> WorkManifest:
    return WorkManifest(work_id=work_id, path=Path("fake.yaml"), data={})


def test_validate_greek_sections_passes_a_boundary_at_a_token_start_and_in_a_gap():
    # Positive control: one offset sits exactly at a token's own start (0),
    # the other in the inter-token gap (the space) -- both legal per the
    # fixed renderer's char-offset-direct split.
    line = {
        "n": 1,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 6}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems)
    assert problems == []


def test_validate_greek_sections_fatal_on_offset_inside_a_token_span():
    # The exact render-safety violation: o=3 lands strictly inside "ἀγαθός"
    # ([0,6)) -- rendering a paragraph break there would split a clickable
    # Greek word.
    line = {
        "n": 2,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 3}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems)
    assert len(problems) == 1
    assert "falls inside token span" in problems[0][2]
    assert "o=3" in problems[0][2]


def test_validate_greek_sections_fatal_on_non_ascending_offsets():
    line = {
        "n": 3,
        "text": "ἀγαθός λόγος καλόν",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}, {"t": "καλόν", "o": 13}],
        "sections": [{"n": 1, "o": 7}, {"n": 2, "o": 0}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems)
    assert any("not strictly ascending" in p[2] for p in problems)


def test_validate_greek_sections_fatal_on_out_of_bounds_offset():
    line = {"n": 4, "text": "ἀγαθός", "tokens": [{"t": "ἀγαθός", "o": 0}], "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 99}]}
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems)
    assert any("out of bounds" in p[2] for p in problems)


def test_validate_greek_sections_fatal_on_nonzero_first_offset():
    # GPT-5.6-Sol-High confirm review (2026-07-16): splitGreekSections
    # (shared/lib/speakers.ts) slices line.text starting at sections[0].o,
    # not from 0 -- a nonzero first offset would silently drop the text
    # before it at render time. o=6 sits in the inter-token gap (the space
    # after "ἀγαθός"), so this isolates the new rule from the existing
    # inside-a-token-span rule.
    line = {
        "n": 5,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 6}, {"n": 2, "o": 7}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems)
    assert any("sections[0].o must be 0" in p[2] for p in problems)
    assert not any("falls inside token span" in p[2] for p in problems)


def test_validate_greek_sections_fatal_when_line_also_carries_a_speaker_event():
    # GPT-5.6-Sol-High confirm review (2026-07-16): splitGreekSections does
    # not re-bucket Segment.speakers across the pieces it produces, so this
    # combination must never ship. speaker_lines mirrors what the real call
    # site derives from segment["speakers"][*]["line"].
    line = {
        "n": 2,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 7}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems, {2})
    assert any("carries both a `sections` channel and a speaker-turn event" in p[2] for p in problems)


def test_validate_greek_sections_speaker_lines_elsewhere_in_segment_is_not_flagged():
    # Positive control: speaker_lines is non-empty but does not include THIS
    # line's n -- must not be a false positive.
    line = {
        "n": 2,
        "text": "ἀγαθός λόγος",
        "tokens": [{"t": "ἀγαθός", "o": 0}, {"t": "λόγος", "o": 7}],
        "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 7}],
    }
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", line, problems, {7})
    assert problems == []


def test_validate_greek_sections_absent_key_is_a_silent_no_op():
    # Every work that never opts in (the overwhelming majority) carries no
    # `sections` key at all -- must not be flagged.
    problems: list = []
    _validate_greek_sections(_manifest(), "book-01.json", "1:1094a", {"n": 1, "text": "x", "tokens": []}, problems)
    assert problems == []


def test_validate_english_paras_passes_ascending_in_bounds_offsets():
    english = {"text": "Good. Fine speech.", "paras": [{"n": 1, "o": 0}, {"n": 2, "o": 6}]}
    problems: list = []
    _validate_english_paras(_manifest(), "book-01.json", "1:1094a", english, problems)
    assert problems == []


def test_validate_english_paras_fatal_on_descending_offsets():
    english = {"text": "Good. Fine speech.", "paras": [{"n": 2, "o": 5}, {"n": 1, "o": 2}]}
    problems: list = []
    _validate_english_paras(_manifest(), "book-01.json", "1:1094a", english, problems)
    assert any("not strictly ascending" in p[2] for p in problems)


def test_validate_english_paras_absent_key_is_a_silent_no_op():
    problems: list = []
    _validate_english_paras(_manifest(), "book-01.json", "1:1094a", {"text": "x"}, problems)
    assert problems == []


def test_preflight_sections_broken_fixture_is_fatal_end_to_end():
    # Integration counterpart to the unit tests above: runs a bad Greek
    # `sections` offset (inside a token span) AND descending English `paras`
    # offsets through the REAL call site in _validate_books /
    # _validate_english_bekker, not just the isolated functions -- so a
    # deleted call site (not just a deleted function) would still be caught.
    result = _run_preflight("sections_broken")

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "falls inside token span" in output
    assert "english.paras offsets not strictly ascending" in output


def test_preflight_sections_broken_fixture_fatal_on_nonzero_first_offset_end_to_end():
    # Integration counterpart to test_validate_greek_sections_fatal_on_nonzero_first_offset:
    # runs through the real _validate_books call site. Reuses the
    # sections_broken fixture's greek line 2 ("ἀγαθός λόγος"), replacing its
    # sections with a first offset in the inter-token gap (o=6, not inside
    # any token) so only the new rule fires, not the sibling inside-a-token
    # -span rule already covered above.
    fixture = FIXTURES / "sections_broken"
    book_path = fixture / "data" / "VAL" / "book-01.json"
    original = book_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(original)
        doc["segments"][0]["greek"][1]["sections"] = [{"n": 1, "o": 6}, {"n": 2, "o": 7}]
        book_path.write_text(json.dumps(doc), encoding="utf-8")
        result = _run_preflight("sections_broken")
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "sections[0].o must be 0" in output
        assert "falls inside token span" not in output
    finally:
        book_path.write_text(original, encoding="utf-8")


def test_preflight_sections_broken_fixture_fatal_on_sections_with_speakers_end_to_end():
    # Integration counterpart to
    # test_validate_greek_sections_fatal_when_line_also_carries_a_speaker_event:
    # adds a segment["speakers"] event on the same line (n=2) that already
    # carries the fixture's `sections` channel.
    fixture = FIXTURES / "sections_broken"
    book_path = fixture / "data" / "VAL" / "book-01.json"
    original = book_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(original)
        doc["segments"][0]["speakers"] = [{"line": 2, "offset": 0, "label": "Α."}]
        book_path.write_text(json.dumps(doc), encoding="utf-8")
        result = _run_preflight("sections_broken")
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "carries both a `sections` channel and a speaker-turn event" in output
    finally:
        book_path.write_text(original, encoding="utf-8")


def test_preflight_book_section_fixture_with_valid_sections_and_paras_passes():
    # The real rebuilt corpus proof, at fixture scale: a book-section work
    # whose Greek line carries a well-formed `sections` channel and whose
    # English chunk carries a well-formed `paras` channel validates cleanly
    # end-to-end (mirrors test_preflight_book_section_fixture_passes). A
    # brand-new segment is appended (rather than mutating the existing
    # single-word lines, too short to host a legal two-entry `sections`
    # array) so this is independent of the fixture's other content.
    fixture = FIXTURES / "book_section"
    book_path = fixture / "data" / "MED" / "book-01.json"
    columns_path = fixture / "data" / "MED" / "columns.json"
    book_original = book_path.read_text(encoding="utf-8")
    columns_original = columns_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(book_original)
        doc["segments"].append({
            "id": "1:1.3",
            "column": "1.3",
            "greek": [{
                "n": 1,
                "text": "ἀγαθός λόγος",
                "tokens": [{"t": "ἀγαθός", "o": 0, "k": "a)gaqo/s"}, {"t": "λόγος", "o": 7, "k": "lo/gos"}],
                "sections": [{"n": 1, "o": 0}, {"n": 2, "o": 6}],
            }],
            "english": {
                "text": "Good. Fine speech.",
                "notes": [],
                "markers": [],
                "paras": [{"n": 2, "o": 6}],
            },
        })
        book_path.write_text(json.dumps(doc), encoding="utf-8")
        columns = json.loads(columns_original)
        columns["1.3"] = [{"book": 1, "lo": 1, "hi": 1}]
        columns_path.write_text(json.dumps(columns), encoding="utf-8")
        result = _run_preflight("book_section")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "preflight ok:" in result.stdout
    finally:
        book_path.write_text(book_original, encoding="utf-8")
        columns_path.write_text(columns_original, encoding="utf-8")


def test_validate_lsj_keys_rejects_unknown_language(tmp_path):
    # FAIL-OPEN fix (Wave 2 Batch 1b review, item 4): `_validate_lsj_keys`
    # used to fall back an unrecognized `work.language` to "lsj" (Greek's
    # shard dir) via `SHARD_DIR.get(language, "lsj")`, silently checking a
    # mis-declared work's dictionary keys against the wrong dictionary
    # instead of failing. It must reject instead.
    manifest = WorkManifest(work_id="TST", path=Path("fake.yaml"), data={"work": {"language": "xx"}})
    problems: list = []
    _validate_lsj_keys(manifest, tmp_path, {"some-key"}, problems)
    assert problems, "an unrecognized language must be flagged as a preflight problem"
    assert any("unrecognized language" in message for _work, _file, message in problems)


def test_validate_lsj_keys_grc_default_still_works(tmp_path):
    # Sanity check alongside the rejection test above: the DEFAULT ('grc',
    # when work.language is absent) must still resolve to the 'lsj' shard
    # dir exactly as before -- the fix rejects UNRECOGNIZED languages, not
    # the legitimate default.
    (tmp_path / "lsj").mkdir()
    (tmp_path / "lsj" / "l.json").write_text(json.dumps({"lo/gos": {"key": "lo/gos", "head": "λόγος", "html": ""}}))
    manifest = WorkManifest(work_id="TST", path=Path("fake.yaml"), data={"work": {}})
    problems: list = []
    _validate_lsj_keys(manifest, tmp_path, {"lo/gos"}, problems)
    assert problems == []
