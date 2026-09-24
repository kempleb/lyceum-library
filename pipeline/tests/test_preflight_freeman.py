"""Regression tests for the Freeman Ancilla wave's preflight gates --
kind/Greek-role cross-check (design note §1(b) gate (ii)) and the
structural well-formedness of the three optional manifest declarations
(freeman_concordance, display_order, abridged_columns)."""

from __future__ import annotations

from pathlib import Path

from reader_pipeline.preflight import (
    WorkManifest,
    _validate_freeman_kinds,
    _validate_freeman_manifest_declarations,
    _validate_freeman_paratext,
)


def _manifest(extra: dict | None = None) -> WorkManifest:
    data = {
        "work": {"id": "FIX", "author": "fixture"},
        "citation": {"scheme": "dk", "series": "B",
                     "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded", "B10": "note"}},
        "books": [{"n": 1, "start": "B1", "end": "B8"}],
    }
    data.update(extra or {})
    return WorkManifest(work_id="FIX", path=Path("FIX.yaml"), data=data)


def _seg(column: str, kind: str, roles: list[str]) -> dict:
    return {"column": column, "kind": kind,
            "greek": [{"role": r} for r in roles]}


def test_kind_role_gate_passes_when_consistent():
    loaded = {"book-01.json": {"segments": [
        _seg("B1", "verbatim", ["text", "context"]),
        _seg("B5", "title", ["context"]),
        _seg("B8", "embedded", ["context", "text"]),
        _seg("B10", "note", ["context"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert problems == []


def test_kind_role_gate_fatal_when_title_carries_text_without_override():
    # Residual 4 (round-2 fix): the title/note role-rule loosening is
    # SCOPED to columns with a validated citation.kind_overrides
    # adjudication, never global. B5 has no override declared in this
    # manifest, so the strict "title carries no role='text'" rule applies
    # and this is fatal.
    loaded = {"book-01.json": {"segments": [
        _seg("B5", "title", ["context", "text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B5" in p[2] for p in problems)


def test_kind_role_gate_allows_title_with_text_survival_when_overridden():
    # John's ruling on Protagoras B5 (2026-07-23, CANON.md): `title` is
    # extended to a "title-survivals-in-frame" case -- a title column MAY
    # carry a role='text' span (the quoted title word itself) without
    # being fatal, but ONLY when that specific column carries a validated
    # citation.kind_overrides adjudication (residual 4, round-2 fix) --
    # not as a blanket loosening of _FREEMAN_KIND_ROLE_RULE.
    m = _manifest({"citation": {
        "scheme": "dk", "series": "B",
        "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded", "B10": "note"},
        "kind_overrides": {"B5": {"kind": "title", "note": "title-survivals-in-frame"}},
    }})
    loaded = {"book-01.json": {"segments": [
        _seg("B5", "title", ["context", "text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert problems == []


def test_kind_role_gate_fatal_when_verbatim_carries_no_text():
    loaded = {"book-01.json": {"segments": [
        _seg("B1", "verbatim", ["context"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B1" in p[2] for p in problems)


def test_kind_role_gate_fatal_when_embedded_has_no_context():
    loaded = {"book-01.json": {"segments": [
        _seg("B8", "embedded", ["text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B8" in p[2] for p in problems)


def test_kind_role_gate_fatal_when_note_carries_text_without_override():
    # Residual 4 (round-2 fix): same scoping as the title case above --
    # B10 has no override declared in this manifest, so the strict
    # "note carries no role='text'" rule applies and this is fatal.
    loaded = {"book-01.json": {"segments": [
        _seg("B10", "note", ["context", "text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B10" in p[2] for p in problems)


def test_kind_role_gate_allows_note_with_bare_name_text_survival_when_overridden():
    # John's ruling on Protagoras B6 (2026-07-23, CANON.md): `note` MAY
    # carry a role='text' span (a bare proper name, "Euathlus", is not
    # the philosopher's own words) without being fatal, but ONLY when
    # that specific column carries a validated citation.kind_overrides
    # adjudication (residual 4, round-2 fix).
    m = _manifest({"citation": {
        "scheme": "dk", "series": "B",
        "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded", "B10": "note"},
        "kind_overrides": {"B10": {"kind": "note", "note": "bare proper name, not his words"}},
    }})
    loaded = {"book-01.json": {"segments": [
        _seg("B10", "note", ["context", "text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert problems == []


def test_kind_role_gate_fatal_when_note_carries_no_context():
    loaded = {"book-01.json": {"segments": [
        _seg("B10", "note", ["text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B10" in p[2] for p in problems)


def test_kind_role_gate_ignores_segments_without_kind():
    # B99 is not declared in citation.fragment_kinds at all (a genuine
    # alignment_allow_unmatched-style gap) -- a legitimate no-kind case.
    loaded = {"book-01.json": {"segments": [
        {"column": "B99", "greek": [{"role": "text"}]},
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert problems == []


def test_kind_role_gate_fatal_when_declared_column_has_no_emitted_kind():
    # finding 2: B1 IS declared in citation.fragment_kinds (Freeman covers
    # it) but the emitted segment carries no "kind" key at all -- a stage7
    # emission regression, fatal, not silently skipped.
    loaded = {"book-01.json": {"segments": [
        {"column": "B1", "greek": [{"role": "text"}]},
    ]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B1" in p[2] and "no \"kind\" key" in p[2] for p in problems)


def test_kind_role_gate_allows_omitted_column_to_carry_no_kind():
    # John's ruling 2026-07-23: an `omit`-declared column ships no Freeman
    # English at all, so the emitted segment carries no "kind" key -- this
    # is the CORRECT/expected shape, not the finding-2 emission regression.
    m = _manifest({"citation": {
        "scheme": "dk", "series": "B",
        "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded",
                            "B10": "note", "B9": "omit"},
        "kind_overrides": {"B9": {"kind": "omit", "reason": "no greek"}},
    }})
    loaded = {"book-01.json": {"segments": [
        {"column": "B9", "greek": [{"role": "context"}]},
    ]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert problems == []


def test_kind_role_gate_fatal_when_omitted_column_carries_a_kind():
    # The reverse regression: English was attached to a column John ruled
    # must ship none.
    m = _manifest({"citation": {
        "scheme": "dk", "series": "B",
        "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded",
                            "B10": "note", "B9": "omit"},
        "kind_overrides": {"B9": {"kind": "omit", "reason": "no greek"}},
    }})
    loaded = {"book-01.json": {"segments": [
        _seg("B9", "verbatim", ["text"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert any("B9" in p[2] and "omit" in p[2] for p in problems)


# --- manifest declaration well-formedness -----------------------------------

def test_freeman_concordance_absent_is_a_noop():
    problems: list = []
    _validate_freeman_manifest_declarations(_manifest(), problems, None)
    assert problems == []


def test_freeman_concordance_rejects_column_outside_fragment_kinds():
    m = _manifest({"freeman_concordance": {"B99": "B1000"}})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert any("B1000" in p[2] for p in problems)


def test_freeman_concordance_rejects_duplicate_targets():
    m = _manifest({"freeman_concordance": {"B99": "B1", "B98": "B1"}})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert any("more than one" in p[2] for p in problems)


def test_display_order_accepts_exact_permutation():
    m = _manifest({"display_order": ["B5", "B1", "B10", "B8"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert problems == []


def test_display_order_rejects_missing_column():
    m = _manifest({"display_order": ["B5", "B1", "B10"]})  # B8 missing
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert any("missing" in p[2] for p in problems)


def test_display_order_rejects_duplicate():
    m = _manifest({"display_order": ["B5", "B1", "B10", "B8", "B8"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert any("duplicated" in p[2] for p in problems)


def test_abridged_columns_rejects_unknown_column():
    m = _manifest({"abridged_columns": ["B1", "B999"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert any("B999" in p[2] for p in problems)


def test_abridged_columns_accepts_known_columns():
    m = _manifest({"abridged_columns": ["B1", "B8"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None)
    assert problems == []


# --- abridged_columns bidirectional reconciliation against dist data
# (finding 7) ------------------------------------------------------------

def _loaded_with_abridged(*columns: str) -> dict:
    return {"book-01.json": {"segments": [
        {"column": c, "abridged": True} for c in columns
    ]}}


def test_abridged_columns_declared_and_observed_agree():
    m = _manifest({"abridged_columns": ["B1"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None, _loaded_with_abridged("B1"))
    assert problems == []


def test_abridged_columns_undeclared_observed_is_fatal():
    m = _manifest()  # no abridged_columns declared at all
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None, _loaded_with_abridged("B1"))
    assert any("B1" in p[2] and "not declared" in p[2] for p in problems)


def test_abridged_columns_declared_unobserved_is_fatal():
    m = _manifest({"abridged_columns": ["B1"]})
    problems: list = []
    _validate_freeman_manifest_declarations(m, problems, None, _loaded_with_abridged())
    assert any("B1" in p[2] and "no abridged flag" in p[2] for p in problems)


# --- paratext.json content (finding 4; presence is a `required`-file-list
# check in _validate_work_data, not tested here) -----------------------

def _loaded_with_columns(paratext: list, *columns: str) -> dict:
    return {
        "paratext.json": paratext,
        "book-01.json": {"segments": [{"column": c} for c in columns]},
    }


def test_paratext_content_matches_declared_group_header_count():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforeColumn": "B5", "level": 2, "text": "x"}], "B1", "B5", "B8",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert problems == []


def test_paratext_content_count_mismatch_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = {"paratext.json": []}  # declared 1 header, emitted 0
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("stale emission" in p[2] for p in problems)


def test_paratext_content_must_be_a_list():
    m = _manifest()
    loaded = {"paratext.json": {"not": "a list"}}
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("must be a JSON list" in p[2] for p in problems)


# --- paratext.json per-entry shape (residual 2, round-2 fix) ---------------

def test_paratext_entry_extra_key_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforeColumn": "B5", "level": 2, "text": "x", "extra": "surprise"}],
        "B5",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("extra key(s)" in p[2] for p in problems)


def test_paratext_entry_missing_key_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns([{"beforeColumn": "B5", "level": 2}], "B5")
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("missing key(s)" in p[2] for p in problems)


def test_paratext_entry_unknown_before_column_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B999", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforeColumn": "B999", "level": 2, "text": "x"}], "B1",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("does not name a known spine column" in p[2] for p in problems)


def test_paratext_entry_bad_level_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 3, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforeColumn": "B5", "level": 3, "text": "x"}], "B5",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("is not 1 or 2" in p[2] for p in problems)


def test_paratext_entry_blank_text_is_fatal():
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "  ", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforeColumn": "B5", "level": 2, "text": "  "}], "B5",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert any("non-blank string" in p[2] for p in problems)


def test_paratext_malformed_entry_with_matching_count_is_still_fatal():
    # Residual 3: a same-length-but-malformed emission must not slip past
    # the count-only check -- count matches (1 declared, 1 emitted), but
    # the single entry's shape is wrong (a typo'd key instead of
    # `beforeColumn`).
    m = _manifest({"group_headers": [
        {"before_column": "B5", "level": 2, "text": "x", "sha256_16": "a"},
    ]})
    loaded = _loaded_with_columns(
        [{"beforColumn": "B5", "level": 2, "text": "x"}], "B5",
    )
    problems: list = []
    _validate_freeman_paratext(m, loaded, problems)
    assert not any("stale emission" in p[2] for p in problems)  # count DID match
    assert any("extra key(s)" in p[2] and "missing key(s)" in p[2] for p in problems)


# --- citation.whole_column_verbatim attestation ------------------------------
#
# The §1(b) verbatim rule ("at least one role='text' line") is an
# anti-fabrication check: no column may claim attested-verbatim status
# without positive evidence separating the author's own words from a
# quoting source's narrative. DK supplies that evidence CONTRASTIVELY,
# via <hi rend="letter-spacing"> -- so where an entry is nothing but the
# philosopher speaking from first word to last (Gorgias B11 Encomium of
# Helen, B11a Defence of Palamedes: whole continuous speeches, no quoting
# narrative anywhere in the div), the markup cannot exist at all. The
# attestation lets that evidence be ASSERTED in the manifest, per column,
# with a human-written justification -- never derived, never wholesale.

def _attested(decl) -> dict:
    return {"citation": {
        "scheme": "dk", "series": "B",
        "fragment_kinds": {"B1": "verbatim", "B5": "title", "B8": "embedded", "B10": "note"},
        "whole_column_verbatim": decl,
    }}


def test_whole_column_verbatim_absent_still_fails_an_all_context_verbatim():
    # Case 1: no attestation -> the gate holds, exactly as before, and the
    # message signposts the mechanism rather than dead-ending.
    loaded = {"book-01.json": {"segments": [_seg("B1", "verbatim", ["context"])]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert any("B1" in p[2] and "whole_column_verbatim" in p[2] for p in problems)


def test_whole_column_verbatim_without_a_justification_fails():
    # Case 2: attested but unjustified -> void. Both an empty string and a
    # missing key, and the underlying kind/role failure still stands.
    for decl in ({"B1": {"justification": "   "}}, {"B1": {}}, {"B1": None}):
        loaded = {"book-01.json": {"segments": [_seg("B1", "verbatim", ["context"])]}}
        problems: list = []
        _validate_freeman_kinds(WorkManifest(work_id="FIX", path=Path("FIX.yaml"),
                                             data={**_manifest().data, **_attested(decl)}),
                                loaded, problems)
        assert any("justification" in p[2] for p in problems), decl
        assert any("B1" in p[2] and "role='text'" in p[2] for p in problems), decl


def test_whole_column_verbatim_with_a_justification_passes():
    # Case 3: attested and justified -> the all-context verbatim column
    # passes, and nothing else is loosened.
    m = WorkManifest(work_id="FIX", path=Path("FIX.yaml"),
                     data={**_manifest().data,
                           **_attested({"B1": {"justification": "whole speech, no quoting frame"}})})
    loaded = {"book-01.json": {"segments": [
        _seg("B1", "verbatim", ["context", "context"]),
        _seg("B10", "note", ["context"]),
    ]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert problems == []


def test_whole_column_verbatim_leaves_a_genuine_text_column_alone():
    # Case 4: a column with real role='text' lines is unaffected -- it
    # passes without any attestation, and attesting it is itself flagged
    # stale (the mechanism must not accumulate on columns that never
    # needed it).
    loaded = {"book-01.json": {"segments": [_seg("B1", "verbatim", ["text", "context"])]}}
    problems: list = []
    _validate_freeman_kinds(_manifest(), loaded, problems)
    assert problems == []

    m = WorkManifest(work_id="FIX", path=Path("FIX.yaml"),
                     data={**_manifest().data,
                           **_attested({"B1": {"justification": "not needed here"}})})
    problems = []
    _validate_freeman_kinds(m, loaded, problems)
    assert any("stale declaration" in p[2] for p in problems)


def test_whole_column_verbatim_cannot_be_applied_wholesale():
    # The loophole the gate guards against: a work-wide/scheme-wide switch.
    # Every non-per-column shape is fatal AND grants nothing.
    for decl in (True, "all", ["B1"], "B1"):
        loaded = {"book-01.json": {"segments": [_seg("B1", "verbatim", ["context"])]}}
        problems: list = []
        _validate_freeman_kinds(WorkManifest(work_id="FIX", path=Path("FIX.yaml"),
                                             data={**_manifest().data, **_attested(decl)}),
                                loaded, problems)
        assert any("per-column object" in p[2] for p in problems), decl
        assert any("B1" in p[2] and "role='text'" in p[2] for p in problems), decl


def test_whole_column_verbatim_naming_an_unknown_column_is_stale():
    m = WorkManifest(work_id="FIX", path=Path("FIX.yaml"),
                     data={**_manifest().data,
                           **_attested({"B999": {"justification": "typo"}})})
    loaded = {"book-01.json": {"segments": [_seg("B1", "verbatim", ["text"])]}}
    problems: list = []
    _validate_freeman_kinds(m, loaded, problems)
    assert any("B999" in p[2] and "stale attestation" in p[2] for p in problems)
