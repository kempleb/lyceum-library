"""Regression tests for stage1_freeman_english.py: key-set reconciliation,
fragment_kinds staleness, group_headers staleness (content + self-
consistent hash), and the emitted chunk/paratext shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_freeman_english as sfe
from reader_pipeline.config import Manifest
from reader_pipeline.stage7_emit import emit_books


def _spine(columns: list[str], markers: dict[str, int] | None = None) -> dict:
    """`markers` (column -> count) gives that column a single Greek line
    printing "(1) (2) ... (N)" -- the DK section markers _greek_section_count
    reads to cross-check an english.column_sources file's own section count
    (finding 3, Sol review). A column absent from `markers` keeps the old
    empty-lines shape (no column_sources test ever touches it)."""
    markers = markers or {}
    return {"work": "FIX", "segments": [
        {"id": f"1:{c}", "book": 1, "column": c,
         "lines": [{"n": 1, "text": " ".join(f"({i})" for i in range(1, markers[c] + 1))}]
         if c in markers else []}
        for c in columns
    ]}


def _clean(tmp_path, records: dict) -> str:
    rel = "freeman-ancilla/fixture.clean.json"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records), encoding="utf-8")
    return rel


def _headers_file(tmp_path, headers: list) -> str:
    rel = "freeman-ancilla/fixture.group_headers.json"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(headers), encoding="utf-8")
    return rel


def _manifest(tmp_path, clean_rel, headers_rel=None, fragment_kinds=None,
              group_headers_decl=None, allow_unmatched=None,
              summary_suppressed=None, summary_labels=None) -> Manifest:
    data = {
        "work": {"id": "FIX"},
        "citation": {"scheme": "dk", "series": "B",
                     "fragment_kinds": fragment_kinds or {}},
        "english": {"primary": {
            "id": "freeman", "name": "Fixture Freeman", "model": "freeman",
            "file": clean_rel,
            **({"group_headers_file": headers_rel} if headers_rel else {}),
        }},
    }
    if group_headers_decl is not None:
        data["group_headers"] = group_headers_decl
    if allow_unmatched is not None:
        data["alignment_allow_unmatched"] = allow_unmatched
    if summary_suppressed is not None:
        data["english"]["summary_suppressed"] = summary_suppressed
    if summary_labels is not None:
        data["english"]["summary_labels"] = summary_labels
    return Manifest(data, Path("FIX.yaml"))


def _context_english_file(tmp_path, work_id: str, decl: dict) -> None:
    p = tmp_path / work_id / "context-english.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(decl), encoding="utf-8")


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sfe, "SOURCES_DIR", tmp_path)
    build_dir = tmp_path / "build"
    monkeypatch.setattr(sfe, "BUILD_DIR", build_dir)
    yield


def test_key_set_mismatch_extra_key_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"},
                                   "B99": {"kind": "verbatim", "text": "y"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "verbatim"})
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="matching no spine column"):
        sfe.run(manifest, spine)


def test_key_set_missing_column_without_allowance_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "verbatim"})
    spine = _spine(["B1", "B2"])
    with pytest.raises(ValueError, match="missing"):
        sfe.run(manifest, spine)


def test_key_set_missing_column_with_declared_allowance_passes(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"},
                          allow_unmatched=["1:B2"], group_headers_decl=[])
    spine = _spine(["B1", "B2"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert [c["column"] for c in english["chunks"]] == ["B1"]


# --- true orphan path (finding 9) -------------------------------------------

def test_orphan_column_not_in_spine_is_fatal_without_concordance(tmp_path):
    """The REAL Protagoras shape (B11/B12 beyond the spine's last column) --
    an orphan present in the clean JSON is routed through reconciliation
    itself, not pre-stripped by the test, and fails loudly (never silently
    dropped)."""
    clean_rel = _clean(tmp_path, {
        "B10": {"kind": "verbatim", "text": "x"},
        "B11": {"kind": "verbatim", "text": "Education does not take root."},
        "B12": {"kind": "verbatim", "text": "A Graeco-Syrian maxim."},
    })
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B10": "verbatim"})
    spine = _spine(["B10"])
    with pytest.raises(ValueError, match="matching no spine column") as exc:
        sfe.run(manifest, spine)
    assert "B11" in str(exc.value) and "B12" in str(exc.value)


def test_differently_keyed_legitimate_column_fails_loudly_without_concordance(tmp_path):
    """A Diels-5/Kranz-6 drift case (design note §2): Freeman's own printed
    number ("B2") does not match the real DK column ("B3") for this
    (synthetic) work. Undeclared, this must fail loudly on BOTH sides (an
    orphan key AND a missing spine column) -- never silently aligned by
    position."""
    clean_rel = _clean(tmp_path, {"B2": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B2": "verbatim"})
    spine = _spine(["B3"])
    with pytest.raises(ValueError, match="matching no spine column"):
        sfe.run(manifest, spine)


# --- freeman_concordance remap BEFORE key-set reconciliation (finding 5) ---

def test_freeman_concordance_remaps_before_key_set_reconciliation(tmp_path):
    """Same drift as above, but declared via freeman_concordance -- the
    remap must apply BEFORE _validate_key_set ever runs, so the (remapped)
    clean JSON reconciles cleanly against the spine."""
    clean_rel = _clean(tmp_path, {"B2": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B3": "verbatim"}, group_headers_decl=[])
    manifest.data["freeman_concordance"] = {"B2": "B3"}
    spine = _spine(["B3"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert [c["column"] for c in english["chunks"]] == ["B3"]
    assert english["chunks"][0]["text"] == "x"


def test_freeman_concordance_stale_key_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "verbatim"})
    manifest.data["freeman_concordance"] = {"B2": "B3"}  # B2 not in clean JSON
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="not present in the clean JSON"):
        sfe.run(manifest, spine)


def test_freeman_concordance_preserves_renamed_key_position():
    """finding 3, round 2: a naive pop+reassign remap silently relocates
    the renamed key to the END of the dict (Python dicts append on
    reinsertion) -- Freeman's own B16c/B15c drift is printed exactly
    where DK's B15c belongs, so the remap must keep it there."""
    clean = {"B15b": {"kind": "verbatim", "text": "a"},
              "B16c": {"kind": "verbatim", "text": "b"},
              "B16": {"kind": "verbatim", "text": "c"}}
    manifest = _manifest(Path("."), "unused", fragment_kinds={})
    manifest.data["freeman_concordance"] = {"B16c": "B15c"}
    remapped = sfe._apply_freeman_concordance(manifest, clean)
    assert list(remapped) == ["B15b", "B15c", "B16"]


# --- key-SEQUENCE reconciliation (finding 3, round 2 adversarial fix) -------
# `_validate_key_set` only reconciles column SETS -- a transposed pair of
# Freeman entries would still pass it while the reader (which renders in
# Greek spine order) silently shows the wrong English text next to each
# Greek column.

def test_key_sequence_matches_spine_order_passes(tmp_path):
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "one"},
        "B2": {"kind": "verbatim", "text": "two"},
        "B3": {"kind": "verbatim", "text": "three"},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "verbatim",
                                          "B3": "verbatim"},
                          group_headers_decl=[])
    spine = _spine(["B1", "B2", "B3"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert [c["column"] for c in english["chunks"]] == ["B1", "B2", "B3"]


def test_key_sequence_transposed_pair_is_fatal(tmp_path):
    """A swapped pair (B2/B3 transposed relative to the Greek spine) must
    stop the build -- set-only reconciliation would silently pass this and
    the reader would render B2's English text against the B3 Greek column."""
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "one"},
        "B3": {"kind": "verbatim", "text": "three"},
        "B2": {"kind": "verbatim", "text": "two"},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "verbatim",
                                          "B3": "verbatim"})
    spine = _spine(["B1", "B2", "B3"])
    with pytest.raises(ValueError, match="column order does not match the Greek spine"):
        sfe.run(manifest, spine)


def test_key_sequence_declared_display_order_permits_deviation(tmp_path):
    """A genuine Freeman-diverges-from-spine case is legal ONLY when the
    manifest declares `display_order` naming the actual Freeman sequence."""
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "one"},
        "B3": {"kind": "verbatim", "text": "three"},
        "B2": {"kind": "verbatim", "text": "two"},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "verbatim",
                                          "B3": "verbatim"},
                          group_headers_decl=[])
    manifest.data["display_order"] = ["B1", "B3", "B2"]
    spine = _spine(["B1", "B2", "B3"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert [c["column"] for c in english["chunks"]] == ["B1", "B2", "B3"]


def test_key_sequence_display_order_itself_wrong_is_fatal(tmp_path):
    """A declared display_order that does NOT match the actual Freeman
    sequence is a stale/mistaken declaration, not a free pass."""
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "one"},
        "B2": {"kind": "verbatim", "text": "two"},
        "B3": {"kind": "verbatim", "text": "three"},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "verbatim",
                                          "B3": "verbatim"})
    manifest.data["display_order"] = ["B1", "B3", "B2"]  # doesn't match clean JSON order
    spine = _spine(["B1", "B2", "B3"])
    with pytest.raises(ValueError, match="does not match the declared display_order"):
        sfe.run(manifest, spine)


# --- kind_overrides resolution (finding 1) ----------------------------------

def test_kind_overrides_resolves_a_conflicted_column(tmp_path):
    clean_rel = _clean(tmp_path, {"B5": {"kind": "conflict", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B5": "title"}, group_headers_decl=[])
    manifest.data["citation"]["kind_overrides"] = {
        "B5": {"kind": "title", "note": "John's ruling 7/23: title survival."}
    }
    spine = _spine(["B5"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert english["chunks"][0]["kind"] == "title"


def test_kind_overrides_unresolved_conflict_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B5": {"kind": "conflict", "text": "x"},
                                   "B6": {"kind": "conflict", "text": "y"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B5": "title", "B6": "note"})
    # B6 deliberately left unresolved -- a still-unresolved conflict must
    # still stop the build.
    manifest.data["citation"]["kind_overrides"] = {
        "B5": {"kind": "title", "note": "John's ruling 7/23: title survival."}
    }
    spine = _spine(["B5", "B6"])
    with pytest.raises(ValueError, match="remain unresolved") as exc:
        sfe.run(manifest, spine)
    assert "B6" in str(exc.value) and "B5" not in str(exc.value)


def test_kind_overrides_target_must_be_conflicted(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "verbatim"})
    manifest.data["citation"]["kind_overrides"] = {
        "B1": {"kind": "title", "note": "not actually conflicted"}
    }
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="NOT conflicted"):
        sfe.run(manifest, spine)


def test_kind_overrides_requires_a_note(tmp_path):
    clean_rel = _clean(tmp_path, {"B5": {"kind": "conflict", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B5": "title"})
    manifest.data["citation"]["kind_overrides"] = {"B5": {"kind": "title", "note": "  "}}
    spine = _spine(["B5"])
    with pytest.raises(ValueError, match="non-empty 'note'"):
        sfe.run(manifest, spine)


# --- `omit` disposition (John's ruling 2026-07-23) --------------------------

def test_kind_overrides_omit_resolves_the_stop(tmp_path):
    """`omit` releases the hard stop like any other override, but is not a
    legal Segment.kind -- it must not itself require a `note`, only a
    `reason`."""
    clean_rel = _clean(tmp_path, {"B304": {"kind": "conflict", "text": "I alone know."}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B304": "omit"}, group_headers_decl=[])
    manifest.data["citation"]["kind_overrides"] = {
        "B304": {"kind": "omit", "reason": "known mistranslation of ἓν μόνον οἶδα"}
    }
    spine = _spine(["B304"])
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert english["chunks"] == []


def test_kind_overrides_omit_requires_a_reason(tmp_path):
    clean_rel = _clean(tmp_path, {"B304": {"kind": "conflict", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B304": "omit"})
    manifest.data["citation"]["kind_overrides"] = {"B304": {"kind": "omit", "reason": "  "}}
    spine = _spine(["B304"])
    with pytest.raises(ValueError, match="non-empty 'reason'"):
        sfe.run(manifest, spine)


def test_kind_overrides_omit_without_reason_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B304": {"kind": "conflict", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B304": "omit"})
    manifest.data["citation"]["kind_overrides"] = {"B304": {"kind": "omit"}}
    spine = _spine(["B304"])
    with pytest.raises(ValueError, match="non-empty 'reason'"):
        sfe.run(manifest, spine)


def test_omitted_column_emits_no_english_alongside_others(tmp_path):
    """An `omit`-resolved column carries no chunk at all, while an ordinary
    column alongside it still ships normally."""
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "one"},
        "B304": {"kind": "conflict", "text": "I alone know."},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B304": "omit"},
                          group_headers_decl=[])
    manifest.data["citation"]["kind_overrides"] = {
        "B304": {"kind": "omit", "reason": "known mistranslation"}
    }
    spine = _spine(["B1", "B304"])
    eng_path, align_path = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text())
    assert [c["column"] for c in english["chunks"]] == ["B1"]
    alignment = json.loads(align_path.read_text())
    pairs = {p["segment"]: p["english"] for p in alignment["pairs"]}
    assert pairs["1:B304"] is None
    assert pairs["1:B1"] == "1:B1"


def test_kind_overrides_text_from_ports_english_between_columns(tmp_path):
    """DK's own double-numbering (Democritus B44/B225): B44's own text is
    a bare cross-reference stub, but its ruling carries the identical
    maxim's English by pointing `text_from` at the column that already
    carries it -- and that source column keeps its own text unaffected."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "verbatim", "text": "One should tell the truth, not speak at length."},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "verbatim"},
                          group_headers_decl=[])
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "DK double-numbering of B225's maxim",
                "text_from": "B225"}
    }
    spine = _spine(["B44", "B225"])
    eng_path, _ = sfe.run(manifest, spine)
    chunks = {c["column"]: c["text"] for c in json.loads(eng_path.read_text())["chunks"]}
    assert chunks["B44"] == "One should tell the truth, not speak at length."
    assert chunks["B225"] == "One should tell the truth, not speak at length."


def test_kind_overrides_text_from_unknown_column_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B44": {"kind": "conflict", "text": "= 225."}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B44": "verbatim"})
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"}
    }
    spine = _spine(["B44"])
    with pytest.raises(ValueError, match="text_from names column"):
        sfe.run(manifest, spine)


# --- text_from cycle detection (finding 1, phase-2 adversarial round) ------

def test_kind_overrides_text_from_two_column_cycle_is_fatal(tmp_path):
    """A -> B, B -> A: undetected, this would silently resolve each column
    from the OTHER's original clean text (a swap), never raising at all."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "conflict", "text": "= 44."},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "verbatim"})
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"},
        "B225": {"kind": "verbatim", "note": "y", "text_from": "B44"},
    }
    spine = _spine(["B44", "B225"])
    with pytest.raises(ValueError, match="cycle"):
        sfe.run(manifest, spine)


# --- text_from source disposition (finding 2, phase-2 adversarial round) ---

def test_kind_overrides_text_from_omitted_source_is_fatal(tmp_path):
    """A text_from source that itself resolves to `omit` must never have
    its (withheld) English quietly ported onto another column."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "conflict", "text": "no greek for this either"},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "omit"})
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"},
        "B225": {"kind": "omit", "reason": "no greek"},
    }
    spine = _spine(["B44", "B225"])
    with pytest.raises(ValueError, match="resolved disposition is 'omit'"):
        sfe.run(manifest, spine)


def test_kind_overrides_text_from_unresolved_conflict_source_is_fatal(tmp_path):
    """A text_from source left as an unresolved conflict (no override
    declared for it at all) must stop the build, not silently port its raw
    clean text onto the target."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "conflict", "text": "raw stub"},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "note"})
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"},
    }
    spine = _spine(["B44", "B225"])
    with pytest.raises(ValueError, match="remain unresolved"):
        sfe.run(manifest, spine)


# --- text_from cross-kind porting (finding 3, phase-2 adversarial round) ---

def test_kind_overrides_text_from_cross_kind_mismatch_is_fatal(tmp_path):
    """A verbatim target may not pull text from a note-kind source -- no
    exception mechanism."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "note", "text": "an editorial aside"},
    })
    manifest = _manifest(tmp_path, clean_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "note"})
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"},
    }
    spine = _spine(["B44", "B225"])
    with pytest.raises(ValueError, match="SAME kind"):
        sfe.run(manifest, spine)


def test_kind_overrides_text_from_matching_kind_passes(tmp_path):
    """Sanity: B44 <- B225 (both verbatim) must still work."""
    clean_rel = _clean(tmp_path, {
        "B44": {"kind": "conflict", "text": "= 225."},
        "B225": {"kind": "verbatim", "text": "One should tell the truth."},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B44": "verbatim", "B225": "verbatim"},
                          group_headers_decl=[])
    manifest.data["citation"]["kind_overrides"] = {
        "B44": {"kind": "verbatim", "note": "x", "text_from": "B225"},
    }
    spine = _spine(["B44", "B225"])
    eng_path, _ = sfe.run(manifest, spine)
    chunks = {c["column"]: c["text"] for c in json.loads(eng_path.read_text())["chunks"]}
    assert chunks["B44"] == "One should tell the truth."
    assert chunks["B225"] == "One should tell the truth."


def test_fragment_kinds_missing_declaration_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={})
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="does not match"):
        sfe.run(manifest, spine)


def test_fragment_kinds_stale_value_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "title"})
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="stale"):
        sfe.run(manifest, spine)


def test_group_headers_file_absent_is_fatal(tmp_path):
    """finding 3: group_headers_file is REQUIRED for the freeman model,
    even for a work with no headers at all -- an explicit empty-list
    sidecar, not a silently defaulted one."""
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    manifest = _manifest(tmp_path, clean_rel, fragment_kinds={"B1": "verbatim"})
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="group_headers_file is required"):
        sfe.run(manifest, spine)


def test_group_headers_level_must_be_1_or_2(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers = [{"level": 3, "text": "Label", "before_column": "B1"}]
    headers_rel = _headers_file(tmp_path, headers)
    import hashlib
    h = hashlib.sha256("Label".encode()).hexdigest()[:16]
    declared = [{"before_column": "B1", "level": 3, "text": "Label", "sha256_16": h}]
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=declared)
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="is not 1 or 2"):
        sfe.run(manifest, spine)


def test_group_headers_before_column_must_be_a_real_spine_column(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers = [{"level": 2, "text": "Label", "before_column": "B99"}]
    headers_rel = _headers_file(tmp_path, headers)
    import hashlib
    h = hashlib.sha256("Label".encode()).hexdigest()[:16]
    declared = [{"before_column": "B99", "level": 2, "text": "Label", "sha256_16": h}]
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=declared)
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="names no column"):
        sfe.run(manifest, spine)


def test_group_headers_matching_declaration_passes_and_writes_paratext(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"},
                                   "B2": {"kind": "note", "text": "y"}})
    headers = [{"level": 2, "text": "'On Mathematics'", "before_column": "B2"}]
    headers_rel = _headers_file(tmp_path, headers)
    import hashlib
    h = hashlib.sha256("'On Mathematics'".encode()).hexdigest()[:16]
    declared = [{"before_column": "B2", "level": 2, "text": "'On Mathematics'",
                 "sha256_16": h}]
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "note"},
                          group_headers_decl=declared)
    spine = _spine(["B1", "B2"])
    sfe.run(manifest, spine)
    paratext = json.loads((sfe.BUILD_DIR / "stage1" / "paratext.json").read_text())
    assert paratext == [{"beforeColumn": "B2", "level": 2, "text": "'On Mathematics'"}]


def test_group_headers_stale_hash_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers = [{"level": 2, "text": "Label", "before_column": "B1"}]
    headers_rel = _headers_file(tmp_path, headers)
    declared = [{"before_column": "B1", "level": 2, "text": "Label",
                 "sha256_16": "0" * 16}]
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"},
                          group_headers_decl=declared)
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="sha256_16"):
        sfe.run(manifest, spine)


def test_group_headers_count_mismatch_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [{"level": 2, "text": "Label", "before_column": "B1"}])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=[])
    spine = _spine(["B1"])
    with pytest.raises(ValueError, match="count mismatch"):
        sfe.run(manifest, spine)


def test_emitted_chunk_carries_kind(tmp_path):
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "x"},
        "B2": {"kind": "embedded", "text": "y", "frames": [[0, 2]]},
        "B3": {"kind": "title", "text": "'Title.'", "abridged": True},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(
        tmp_path, clean_rel, headers_rel,
        fragment_kinds={"B1": "verbatim", "B2": "embedded", "B3": "title"},
        group_headers_decl=[],
    )
    spine = _spine(["B1", "B2", "B3"])
    eng_path, _ = sfe.run(manifest, spine)
    chunks = {c["column"]: c for c in json.loads(eng_path.read_text())["chunks"]}
    assert chunks["B1"]["kind"] == "verbatim"
    assert "frames" not in chunks["B1"]
    assert "abridged" not in chunks["B1"]
    assert chunks["B2"]["kind"] == "embedded"
    assert chunks["B2"]["frames"] == [[0, 2]]
    assert chunks["B3"]["kind"] == "title"
    assert chunks["B3"]["abridged"] is True


def test_secondary_archive_emits_fragment_keyed_ross_overlay(tmp_path):
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "Freeman one."},
        "B2": {"kind": "verbatim", "text": "Freeman two."},
    })
    headers_rel = _headers_file(tmp_path, [])
    secondary_rel = "burnet-egp/fixture.json"
    secondary_path = tmp_path / secondary_rel
    secondary_path.parent.mkdir(parents=True, exist_ok=True)
    secondary_path.write_text(json.dumps({"B1": "Burnet one."}), encoding="utf-8")
    manifest = _manifest(
        tmp_path, clean_rel, headers_rel,
        fragment_kinds={"B1": "verbatim", "B2": "verbatim"},
        group_headers_decl=[],
    )
    manifest.data["english"]["secondary"] = {
        "id": "burnet", "name": "Fixture Burnet", "model": "archive",
        "file": secondary_rel,
    }
    manifest.data["alignment_allow_unmatched_secondary"] = ["1:B2"]

    sfe.run(manifest, _spine(["B1", "B2"]))

    ross = json.loads(
        (sfe.BUILD_DIR / "stage1" / "ross_chunks.json").read_text(encoding="utf-8")
    )
    assert ross == {
        "1:B1": [{
            "chapter": "B1", "text": "Burnet one.",
            "cont": False, "bekker": [],
        }]
    }


def test_democritus_sixteen_conflicts_resolved_by_johns_2026_07_23_ruling():
    """The sixteen precedent-less conflicts flagged by the phase-2 pilot
    are now all resolved by manifest `kind_overrides` (John's ruling
    2026-07-23): fourteen `omit` (no Democritean Greek for her English to
    face, a known mistranslation, or a deferred dossier), B44 `verbatim`
    (DK's own B44/B225 double-numbering, English ported via `text_from`),
    and B298a `embedded` (the maxim survives verbatim inside the
    Demetrius papyrus quotation)."""
    manifest = Manifest.load(ROOT / "manifests" / "democritus-fragments.yaml")
    clean = json.loads(
        (ROOT / "sources" / "freeman-ancilla"
         / "freeman-democritus.clean.json").read_text(encoding="utf-8")
    )
    remapped = sfe._apply_freeman_concordance(manifest, clean)
    resolved = sfe._resolve_kind_overrides(manifest, remapped)
    omitted = (
        "B15", "B19", "B23", "B25", "B27", "B27a", "B36",
        "B298", "B300", "B302a", "B304", "B306", "B307", "B309",
    )
    for column in omitted:
        assert resolved[column]["kind"] == "omit", column
    assert resolved["B44"]["kind"] == "verbatim"
    assert resolved["B44"]["text"] == resolved["B225"]["text"]
    assert resolved["B298a"]["kind"] == "embedded"
    assert not any(rec.get("kind") == "conflict" for rec in resolved.values())


# ── english.column_sources: a per-column English from a DIFFERENT
# translation than english.primary, with its own per-passage credit
# (John's ruling 2026-07-28 — Gorgias B11/B11a carry the Parnassos Press
# translations, since Freeman's own entries there are her summaries).

def _column_source_file(tmp_path, name, sections) -> str:
    rel = f"parnassos-fixture/{name}.clean.json"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        [{"section": i + 1, "text": t} for i, t in enumerate(sections)]
    ), encoding="utf-8")
    return rel


_FIXTURE_CREDIT = {
    "translator": "A. Translator",
    "source": "Fixture Edition (Fixture Press)",
    "year": 2022,
    "licence": {"name": "CC BY-NC-ND 4.0",
                "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/"},
}


def _column_source_manifest(tmp_path, sections=("First bit.", "Second bit."),
                            credit=None, column="B2"):
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "Freeman one."},
        "B2": {"kind": "verbatim", "text": "Freeman's own summary of B2."},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "verbatim"},
                          group_headers_decl=[])
    manifest.data["english"]["column_sources"] = [{
        "column": column,
        "file": _column_source_file(tmp_path, "speech", list(sections)),
        "credit": _FIXTURE_CREDIT if credit is None else credit,
    }]
    return manifest


def test_column_source_replaces_the_primary_text_and_carries_its_credit(tmp_path):
    manifest = _column_source_manifest(tmp_path)
    sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))

    english = json.loads(
        (sfe.BUILD_DIR / "stage1" / "english_chunks.json").read_text(encoding="utf-8")
    )
    chunks = {c["column"]: c for c in english["chunks"]}
    # The primary translation's own column is untouched, credit-free.
    assert chunks["B1"]["text"] == "Freeman one."
    assert "credit" not in chunks["B1"]
    # The sourced column ships the OTHER translation's text — the primary's
    # own text for it is gone, not kept alongside — with its sections
    # numbered inline exactly as the Greek prints them.
    assert chunks["B2"]["text"] == "(1) First bit. (2) Second bit."
    assert "summary" not in chunks["B2"]["text"]
    assert chunks["B2"]["kind"] == "verbatim"
    assert chunks["B2"]["credit"] == _FIXTURE_CREDIT
    # The work-level credit still names the primary translation.
    assert english["translation"] == "Fixture Freeman"


def test_no_column_sources_declared_emits_byte_identical_chunks(tmp_path):
    """The regression that matters: a work declaring no `column_sources`
    must emit exactly what it emitted before the mechanism existed —
    including no `credit` key anywhere."""
    clean_rel = _clean(tmp_path, {
        "B1": {"kind": "verbatim", "text": "One."},
        "B2": {"kind": "embedded", "text": "(Simplicius: 'Two.')",
               "frames": [[0, 12]]},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim", "B2": "embedded"},
                          group_headers_decl=[])
    spine = _spine(["B1", "B2"])

    assert sfe._load_column_sources(manifest, spine, {}) == {}
    built = sfe.build_english(manifest, spine, json.loads(
        (tmp_path / clean_rel).read_text(encoding="utf-8")))
    assert built == {
        "work": "FIX", "source": "freeman-ancilla",
        "translation": "Fixture Freeman",
        "chunks": [
            {"id": "1:B1", "book": 1, "column": "B1", "text": "One.",
             "notes": [], "markers": [], "kind": "verbatim"},
            {"id": "1:B2", "book": 1, "column": "B2",
             "text": "(Simplicius: 'Two.')", "notes": [], "markers": [],
             "kind": "embedded", "frames": [[0, 12]]},
        ],
    }


def test_column_source_on_an_omitted_column_is_fatal(tmp_path):
    manifest = _column_source_manifest(tmp_path)
    clean = {"B1": {"kind": "verbatim", "text": "x"},
             "B2": {"kind": "omit", "text": "y"}}
    with pytest.raises(ValueError, match='resolved kind is "omit"'):
        sfe._load_column_sources(manifest, _spine(["B1", "B2"]), clean)


def test_column_source_naming_a_column_off_the_spine_is_fatal(tmp_path):
    manifest = _column_source_manifest(tmp_path, column="B99")
    with pytest.raises(ValueError, match="not in this work's Greek spine"):
        sfe.run(manifest, _spine(["B1", "B2"]))


def test_column_source_with_a_gap_in_its_section_sequence_is_fatal(tmp_path):
    manifest = _column_source_manifest(tmp_path)
    rel = manifest.data["english"]["column_sources"][0]["file"]
    (tmp_path / rel).write_text(json.dumps(
        [{"section": 1, "text": "a"}, {"section": 3, "text": "b"}]
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="contiguously from 1"):
        sfe.run(manifest, _spine(["B1", "B2"]))


def test_column_source_without_a_credit_is_fatal(tmp_path):
    manifest = _column_source_manifest(tmp_path, credit=None)
    del manifest.data["english"]["column_sources"][0]["credit"]
    with pytest.raises(ValueError, match="credit is required"):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_credit_with_a_comma_but_no_ed_marker_is_fatal(tmp_path):
    """Sol review, commit b69eae5, finding 2: splitCreditSource's first-comma
    fallback (Reader.svelte) can truncate a genuine "Title, Subtitle" that
    names no editors. The convention is enforced at build time instead: a
    comma-bearing source must mark its editors with ", ed."."""
    manifest = _column_source_manifest(tmp_path, credit={
        **_FIXTURE_CREDIT, "source": "Fixture Edition, Subtitle (Fixture Press)",
    })
    with pytest.raises(ValueError, match="has a comma but no ', ed.'"):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_credit_source_with_ed_marker_passes(tmp_path):
    """The real Gorgias B11/B11a credit shape (manifests/gorgias-fragments.yaml):
    a title, ", ed." editors, and a publisher parenthetical -- must build."""
    manifest = _column_source_manifest(tmp_path, credit={
        **_FIXTURE_CREDIT,
        "source": (
            "Gorgias/Gorgias: The Sicilian Orator and the Platonic Dialogue, "
            "ed. S. Montgomery Ewegen and Coleen P. Zoller "
            "(Parnassos Press — Fonte Aretusa)"
        ),
    })
    sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))
    english = json.loads(
        (sfe.BUILD_DIR / "stage1" / "english_chunks.json").read_text(encoding="utf-8")
    )
    chunks = {c["column"]: c for c in english["chunks"]}
    assert chunks["B2"]["credit"]["source"] == (
        "Gorgias/Gorgias: The Sicilian Orator and the Platonic Dialogue, "
        "ed. S. Montgomery Ewegen and Coleen P. Zoller "
        "(Parnassos Press — Fonte Aretusa)"
    )


def test_column_source_credit_source_with_no_comma_at_all_passes(tmp_path):
    """A bare source with no comma is unambiguously a title -- covered by
    the fixture credit itself (`Fixture Edition (Fixture Press)`, no
    comma)."""
    manifest = _column_source_manifest(tmp_path)  # _FIXTURE_CREDIT, no comma
    sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_licence_needs_both_a_name_and_a_url(tmp_path):
    manifest = _column_source_manifest(tmp_path, credit={
        **_FIXTURE_CREDIT, "licence": {"name": "CC BY-NC-ND 4.0"},
    })
    with pytest.raises(ValueError, match=r"licence\.url"):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_section_count_mismatched_against_greek_is_fatal(tmp_path):
    """Finding 3 (Sol review): the per-record contiguous-from-1 check alone
    never caught a source file missing its LAST section (or carrying one
    past the Greek's own last marker) -- either would still pass that loop
    and ship silently against the wrong Greek text. The Greek spine here
    prints THREE section markers for B2; the fixture source file only
    supplies two."""
    manifest = _column_source_manifest(tmp_path)  # 2-record source (sections 1-2)
    with pytest.raises(
        ValueError,
        match=r"has 2 section\(s\), but the Greek spine for column 'B2' prints 3",
    ):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 3}))


def test_column_source_with_an_extra_section_past_the_greek_is_fatal(tmp_path):
    """Finding 3's other direction: a source file carrying MORE sections
    than the Greek prints is just as much a misalignment as one missing its
    last section, and must fail the same way."""
    manifest = _column_source_manifest(
        tmp_path, sections=("First bit.", "Second bit.", "Third bit.")
    )
    with pytest.raises(
        ValueError,
        match=r"has 3 section\(s\), but the Greek spine for column 'B2' prints 2",
    ):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_heading_is_prepended_as_a_leading_unmarked_line(tmp_path):
    """item 85 review (2026-07-28): a declared `heading` (the speech's own
    standard English title) leads the chunk's text, ahead of "(1)", with no
    marker of its own -- Reader.svelte's DK inline-marker split peels it off
    as its own leading, unmarked paragraph, matching the Greek div's own
    title line."""
    manifest = _column_source_manifest(tmp_path)
    manifest.data["english"]["column_sources"][0]["heading"] = "A Fixture Speech"
    sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))

    english = json.loads(
        (sfe.BUILD_DIR / "stage1" / "english_chunks.json").read_text(encoding="utf-8")
    )
    chunks = {c["column"]: c for c in english["chunks"]}
    assert chunks["B2"]["text"] == "A Fixture Speech (1) First bit. (2) Second bit."


def test_column_source_without_a_heading_omits_it_byte_identically(tmp_path):
    """Regression: `heading` is optional -- a column_sources entry declaring
    none emits exactly the pre-heading text, unchanged."""
    manifest = _column_source_manifest(tmp_path)
    assert "heading" not in manifest.data["english"]["column_sources"][0]
    sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))

    english = json.loads(
        (sfe.BUILD_DIR / "stage1" / "english_chunks.json").read_text(encoding="utf-8")
    )
    chunks = {c["column"]: c for c in english["chunks"]}
    assert chunks["B2"]["text"] == "(1) First bit. (2) Second bit."


def test_column_source_blank_heading_is_fatal(tmp_path):
    manifest = _column_source_manifest(tmp_path)
    manifest.data["english"]["column_sources"][0]["heading"] = "   "
    with pytest.raises(ValueError, match=r"heading.*non-empty string"):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


def test_column_source_heading_with_parenthesized_number_is_fatal(tmp_path):
    """Finding 5 (Sol review): a heading containing "(N)" would be
    indistinguishable, once joined onto the body text, from a genuine DK
    section marker sitting one word early — fatal, same posture as every
    other malformed-shape check in this loader."""
    manifest = _column_source_manifest(tmp_path)
    manifest.data["english"]["column_sources"][0]["heading"] = "Speech (2) Redux"
    with pytest.raises(ValueError, match=r"heading.*must not contain a parenthesized number"):
        sfe.run(manifest, _spine(["B1", "B2"], markers={"B2": 2}))


# Fix round (Sol adversarial review on commit 7287b10, finding 3): the
# previous version of this test read `marker_counts` straight off the
# vendored English files and used THAT SAME number to build the synthetic
# Greek spine's "(N)" markers -- so the cross-check
# `len(records) == greek_count` inside `_load_column_sources` was
# tautological by construction: the Greek side could never disagree with the
# English side, because both were derived from one number. Pinning the
# expected counts as literal constants, independent of either file, makes
# both sides real assertions again -- a drift in the vendored file's record
# count OR a regression in `_greek_section_count`'s own parsing now fails.
_HELEN_SECTIONS = 21
_PALAMEDES_SECTIONS = 37


def test_gorgias_b11_ships_parnassos_not_freemans_summary():
    """The first consumer, wired end to end from the real manifest and the
    real vendored source files: B11/B11a carry the Parnassos translations,
    each credited, and Freeman's own summary text for those columns is
    gone."""
    manifest = Manifest.load(ROOT / "manifests" / "gorgias-fragments.yaml")
    clean = json.loads(
        (ROOT / "sources" / "freeman-ancilla"
         / "freeman-gorgias.clean.json").read_text(encoding="utf-8")
    )
    resolved = sfe._resolve_kind_overrides(manifest, clean)
    assert resolved["B11"]["kind"] == "verbatim"
    assert resolved["B11a"]["kind"] == "verbatim"

    # The vendored English record count must match the pinned constant --
    # this is the "English side" half of finding 3's cross-check.
    parnassos_dir = ROOT / "sources" / "parnassos-gorgias"
    helen_records = json.loads((parnassos_dir / "gatt-helen.clean.json")
                               .read_text(encoding="utf-8"))
    palamedes_records = json.loads((parnassos_dir / "gazis-palamedes.clean.json")
                                    .read_text(encoding="utf-8"))
    assert len(helen_records) == _HELEN_SECTIONS
    assert len(palamedes_records) == _PALAMEDES_SECTIONS

    # A synthetic Greek spine built from the PINNED constants (not from the
    # files above) -- so `_greek_section_count` is exercised against a
    # number it had no part in producing.
    marker_counts = {"B11": _HELEN_SECTIONS, "B11a": _PALAMEDES_SECTIONS}
    spine = {"work": "gorgias-fragments", "segments": [
        {"id": f"1:{c}", "book": 1, "column": c,
         "lines": [{"n": 1, "text": " ".join(
             f"({i})" for i in range(1, marker_counts[c] + 1)
         )}] if c in marker_counts else []}
        for c in resolved
    ]}
    assert sfe._greek_section_count(spine, "B11") == _HELEN_SECTIONS
    assert sfe._greek_section_count(spine, "B11a") == _PALAMEDES_SECTIONS
    # The real sources/ tree, not the tmp_path fixture one.
    sources = ROOT / "sources"
    original = sfe.SOURCES_DIR
    sfe.SOURCES_DIR = sources
    try:
        column_sources = sfe._load_column_sources(manifest, spine, resolved)
        built = sfe.build_english(manifest, spine, resolved, column_sources)
    finally:
        sfe.SOURCES_DIR = original

    chunks = {c["column"]: c for c in built["chunks"]}
    # item 85 review (2026-07-28): the speech's own standard English title
    # leads the chunk, as an unmarked line ahead of "(1)" -- see the
    # `heading` field on manifests/gorgias-fragments.yaml's column_sources.
    assert chunks["B11"]["text"].startswith("Encomium of Helen (1) ")
    assert chunks["B11"]["text"] != resolved["B11"]["text"]
    assert resolved["B11"]["text"] not in chunks["B11"]["text"]
    assert chunks["B11"]["credit"]["translator"] == "Jurgen R. Gatt"
    assert chunks["B11"]["credit"]["licence"]["name"] == "CC BY-NC-ND 4.0"
    assert "(21) " in chunks["B11"]["text"]
    assert chunks["B11a"]["text"].startswith("Defence of Palamedes (1) ")
    assert chunks["B11a"]["credit"]["translator"].startswith("George Alexander Gazis")
    assert "(37) " in chunks["B11a"]["text"]


# ── english.summary_overlay: Freeman's own DISPLACED summary text for one
# or more column_sources columns, offered back as a sparse further overlay
# (John's ruling 2026-07-28, item 84).

def test_summary_overlay_emits_only_the_named_columns(tmp_path):
    clean = {
        "B1": {"kind": "verbatim", "text": "Freeman one."},
        "B2": {"kind": "verbatim", "text": "Freeman's summary of B2."},
        "B3": {"kind": "verbatim", "text": "Freeman's summary of B3."},
    }
    spine = _spine(["B1", "B2", "B3"])
    out = sfe.build_summary_overlay(spine, clean, ["B2", "B3"])
    assert set(out) == {"1:B2", "1:B3"}
    assert out["1:B2"] == [{
        "chapter": "B2", "text": "Freeman's summary of B2.",
        "cont": False, "bekker": [],
    }]
    assert out["1:B3"][0]["text"] == "Freeman's summary of B3."


def test_summary_overlay_skips_a_named_column_with_no_text(tmp_path):
    clean = {"B1": {"kind": "verbatim", "text": "Freeman one."},
             "B2": {"kind": "verbatim", "text": "   "}}
    spine = _spine(["B1", "B2"])
    out = sfe.build_summary_overlay(spine, clean, ["B1", "B2"])
    assert set(out) == {"1:B1"}


def test_summary_overlay_config_absent_returns_none(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=[])
    assert sfe._load_summary_overlay_cfg(manifest, _spine(["B1"])) is None


def test_summary_overlay_naming_a_column_off_the_spine_is_fatal(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=[])
    manifest.data["english"]["summary_overlay"] = {"id": "freeman-summary", "columns": ["B9"]}
    with pytest.raises(ValueError, match="not in this work's Greek spine"):
        sfe._load_summary_overlay_cfg(manifest, _spine(["B1"]))


def test_summary_overlay_requires_columns_list(tmp_path):
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "x"}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=[])
    manifest.data["english"]["summary_overlay"] = {"id": "freeman-summary"}
    with pytest.raises(ValueError, match="non-empty 'columns'"):
        sfe._load_summary_overlay_cfg(manifest, _spine(["B1"]))


def test_no_summary_overlay_declared_writes_empty_overlays_file(tmp_path):
    """Regression: a work declaring no `summary_overlay` (every DK/Freeman
    work but Gorgias) still gets overlays.json ALWAYS (re)written, empty --
    so a prior work's leftover overlays.json (build/stage1/ is one shared
    directory) can never leak through onto this one's emitted data."""
    clean_rel = _clean(tmp_path, {"B1": {"kind": "verbatim", "text": "Freeman one."}})
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(tmp_path, clean_rel, headers_rel,
                          fragment_kinds={"B1": "verbatim"}, group_headers_decl=[])
    # Simulate a prior work's leftover overlays.json in the shared build dir.
    stale_dir = sfe.BUILD_DIR / "stage1"
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "overlays.json").write_text(
        json.dumps({"stale-id": {"1:B1": [{"chapter": "B1", "text": "stale",
                                            "cont": False, "bekker": []}]}}),
        encoding="utf-8",
    )
    sfe.run(manifest, _spine(["B1"]))
    overlays = json.loads((sfe.BUILD_DIR / "stage1" / "overlays.json").read_text(encoding="utf-8"))
    assert overlays == {}


def test_gorgias_summary_overlay_carries_freemans_original_b11_b11a_text():
    """Wired end to end from the real manifest and the real vendored
    source files: the summary overlay carries Freeman's OWN (displaced)
    B11/B11a text, sparse -- no other column carries an entry."""
    manifest = Manifest.load(ROOT / "manifests" / "gorgias-fragments.yaml")
    clean = json.loads(
        (ROOT / "sources" / "freeman-ancilla"
         / "freeman-gorgias.clean.json").read_text(encoding="utf-8")
    )
    resolved = sfe._resolve_kind_overrides(manifest, clean)
    marker_counts = {"B11": _HELEN_SECTIONS, "B11a": _PALAMEDES_SECTIONS}
    spine = {"work": "gorgias-fragments", "segments": [
        {"id": f"1:{c}", "book": 1, "column": c,
         "lines": [{"n": 1, "text": " ".join(
             f"({i})" for i in range(1, marker_counts[c] + 1)
         )}] if c in marker_counts else []}
        for c in resolved
    ]}
    cfg = sfe._load_summary_overlay_cfg(manifest, spine)
    assert cfg is not None
    overlay_id, columns = cfg
    assert overlay_id == "freeman-summary"
    assert set(columns) == {"B11", "B11a"}
    overlay = sfe.build_summary_overlay(spine, resolved, columns)
    assert set(overlay) == {"1:B11", "1:B11a"}
    # Freeman's own summary text -- NOT the Parnassos text column_sources
    # ships as the default -- and starts as her printed summary label says.
    assert overlay["1:B11"][0]["text"] == clean["B11"]["text"]
    assert overlay["1:B11"][0]["text"].startswith("('Encomium on Helen': summary)")
    assert overlay["1:B11a"][0]["text"] == clean["B11a"]["text"]
    assert overlay["1:B11a"][0]["text"].startswith("(The 'Defence of Palam")
    # Sparse: no other column (e.g. B12, the column right after Palamedes)
    # carries an overlay entry at all.
    assert "1:B12" not in overlay


# --- John's ruling 2026-07-29: summary_suppressed / summary_labels ---------
#
# Regression tests reproducing the corpus-wide census's own edge cases
# (Democritus B10a/B14) alongside the ordinary happy paths, per CLAUDE.md's
# "write a test that reproduces it before fixing" discipline.


def test_wholly_parenthetical_gorgias_b4_shape():
    assert sfe._wholly_parenthetical(
        "(Plato in the 'Meno', 76A sqq.: colour is an effluence from "
        "objects, fitting the passages of the eyes)."
    )


def test_wholly_parenthetical_rejects_leading_tag_with_trailing_prose():
    # Democritus B10a: "(Title): '...' (?)" -- the FIRST paren closes after
    # "(Title)", long before the entry ends; the naive startswith('(')/
    # endswith(')') check would wrongly call this wholly parenthetical.
    assert not sfe._wholly_parenthetical(
        "(Title): 'On Images' or 'On Foresight'. (?)"
    )


def test_wholly_parenthetical_rejects_group_header_with_trailing_prose():
    # Democritus B14: "(Remains of Astronomical Calendar). 1. (Vitruvius). ..."
    # -- same shape, a leading parenthetical label followed by real content.
    assert not sfe._wholly_parenthetical(
        "(Remains of Astronomical Calendar). 1. (Vitruvius). Following the "
        "discoveries of the natural philosophers (Thales, Anaxagoras)."
    )


def test_wholly_parenthetical_rejects_non_parenthetical_text():
    assert not sfe._wholly_parenthetical("Fire goes out through the pores.")


def _b4_fixture(tmp_path, summary_suppressed=None, summary_labels=None):
    clean_rel = _clean(tmp_path, {
        "B3": {"kind": "embedded", "text": "Nothing exists."},
        "B4": {"kind": "embedded",
               "text": "(Plato in the 'Meno': colour is an effluence)."},
    })
    headers_rel = _headers_file(tmp_path, [])
    manifest = _manifest(
        tmp_path, clean_rel, headers_rel,
        fragment_kinds={"B3": "embedded", "B4": "embedded"},
        group_headers_decl=[],
        summary_suppressed=summary_suppressed,
        summary_labels=summary_labels,
    )
    spine = _spine(["B3", "B4"])
    return manifest, spine


def test_summary_suppressed_happy_path_omits_the_chunk(tmp_path):
    manifest, spine = _b4_fixture(tmp_path, summary_suppressed=["B4"])
    _context_english_file(tmp_path, "FIX", {
        "1:B4": {"context_spans": [
            {"source_author": "Plato", "source_work": "Meno",
             "locus": "76a", "status": "translated",
             "translation_credit": "Lamb, 1924"},
        ]},
    })
    covered = sfe._load_context_translated_columns(manifest, spine)
    assert covered == {"B4"}
    resolved = sfe._resolve_kind_overrides(manifest, sfe._load_clean(
        manifest.data["english"]["primary"]
    ))
    sfe._validate_summary_dispositions(manifest, resolved, covered, ["B4"], [])
    english = sfe.build_english(manifest, spine, resolved,
                                summary_suppressed={"B4"})
    columns = {c["column"] for c in english["chunks"]}
    assert columns == {"B3"}


def test_summary_suppressed_requires_wholly_parenthetical_entry(tmp_path):
    clean_rel = _clean(tmp_path, {
        "B4": {"kind": "embedded", "text": "Not parenthetical at all."},
    })
    manifest = _manifest(
        tmp_path, clean_rel, _headers_file(tmp_path, []),
        fragment_kinds={"B4": "embedded"}, group_headers_decl=[],
        summary_suppressed=["B4"],
    )
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    with pytest.raises(ValueError, match="NOT wholly parenthetical"):
        sfe._validate_summary_dispositions(manifest, resolved, {"B4"}, ["B4"], [])


def test_summary_suppressed_requires_translated_coverage(tmp_path):
    manifest, spine = _b4_fixture(tmp_path, summary_suppressed=["B4"])
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    with pytest.raises(ValueError, match="no `status: \"translated\"` span"):
        sfe._validate_summary_dispositions(manifest, resolved, set(), ["B4"], [])


def test_summary_labels_happy_path_flags_the_chunk(tmp_path):
    manifest, spine = _b4_fixture(tmp_path, summary_labels=["B4"])
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    sfe._validate_summary_dispositions(manifest, resolved, set(), [], ["B4"])
    english = sfe.build_english(manifest, spine, resolved,
                                summary_labels={"B4"})
    by_col = {c["column"]: c for c in english["chunks"]}
    assert by_col["B4"]["summary"] is True
    assert "summary" not in by_col["B3"]


def test_summary_labels_rejects_a_covered_column(tmp_path):
    manifest, spine = _b4_fixture(tmp_path, summary_labels=["B4"])
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    with pytest.raises(ValueError, match="SUPPRESSES a covered précis"):
        sfe._validate_summary_dispositions(manifest, resolved, {"B4"}, [], ["B4"])


def test_summary_dispositions_column_in_both_lists_is_fatal(tmp_path):
    manifest, spine = _b4_fixture(tmp_path)
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    with pytest.raises(ValueError, match="declared in BOTH"):
        sfe._validate_summary_dispositions(
            manifest, resolved, {"B4"}, ["B4"], ["B4"]
        )


def test_summary_suppressed_unknown_column_is_fatal(tmp_path):
    manifest, spine = _b4_fixture(tmp_path)
    resolved = sfe._resolve_kind_overrides(
        manifest, sfe._load_clean(manifest.data["english"]["primary"])
    )
    with pytest.raises(ValueError, match="does not cover"):
        sfe._validate_summary_dispositions(
            manifest, resolved, set(), ["B999"], []
        )


def test_gorgias_b4_end_to_end_via_run(tmp_path, monkeypatch):
    """Integration check against the REAL gorgias-fragments manifest/sources
    (not a fixture): B4 is declared english.summary_suppressed there, and
    ships with no Freeman English chunk at all in the actual built output."""
    manifest = Manifest.load(ROOT / "manifests" / "gorgias-fragments.yaml")
    monkeypatch.setattr(sfe, "SOURCES_DIR", ROOT / "sources")
    build_dir = tmp_path / "build"
    monkeypatch.setattr(sfe, "BUILD_DIR", build_dir)
    clean = json.loads(
        (ROOT / "sources" / "freeman-ancilla"
         / "freeman-gorgias.clean.json").read_text(encoding="utf-8")
    )
    resolved = sfe._resolve_kind_overrides(manifest, clean)
    marker_counts = {"B11": _HELEN_SECTIONS, "B11a": _PALAMEDES_SECTIONS}
    spine = {"work": "gorgias-fragments", "segments": [
        {"id": f"1:{c}", "book": 1, "column": c,
         "lines": [{"n": 1, "text": " ".join(
             f"({i})" for i in range(1, marker_counts[c] + 1)
         )}] if c in marker_counts else []}
        for c in resolved
    ]}
    eng_path, _ = sfe.run(manifest, spine)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_col = {c["column"]: c for c in english["chunks"]}
    assert "B4" not in by_col
    assert by_col["B2"]["summary"] is True
    assert by_col["B9"]["summary"] is True
    assert by_col["B13"]["summary"] is True
    assert "summary" not in by_col["B3"]

    tokens_doc = {"segments": [
        {"id": seg["id"], "lines": [
            {"n": line["n"], "tokens": []} for line in seg["lines"]
        ]}
        for seg in spine["segments"]
    ]}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(
        spine, tokens_doc, english, {}, out_dir,
        is_freeman=True,
        fragment_kinds=manifest.data["citation"]["fragment_kinds"],
    )
    emitted = json.loads(
        (out_dir / "book-01.json").read_text(encoding="utf-8")
    )
    emitted_by_col = {s["column"]: s for s in emitted["segments"]}
    assert emitted_by_col["B2"]["english"]["summary"] is True
    assert emitted_by_col["B9"]["english"]["summary"] is True
    assert emitted_by_col["B13"]["english"]["summary"] is True
    assert emitted_by_col["B4"]["english"] is None
