"""Loud key-set reconciliation for chapter-keyed English sources (Sol review
round 3, MAJOR 1): stage1_flat_english and stage1_book_section_english used to
iterate SPINE segments and look keys up in the source JSON, so a mis-keyed or
extra source key was silently ignored and a missing SECONDARY key silently
vanished from ross_chunks.json (stage2's alignment check only covers the
primary). Both builders must now reconcile the source key sets against the
spine column set for BOTH slots: unknown/extra keys are a loud error naming
them; missing keys are a loud error unless the manifest declares them —
primary gaps via the existing `alignment_allow_unmatched`, secondary gaps via
the new symmetric `alignment_allow_unmatched_secondary` (both keyed by
segment id, "5:5.37", as meditations.yaml's Haines gaps already are).

Also under test: __main__._stage1's scheme dispatch for the flat and
book-section schemes — each must reach its dedicated English pass and RETURN,
never falling through to the has_sections branch (which deletes the english
scratch for any non-perseus_stephanus primary — the round-1 defect that left
the flat scheme with no English at all).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_book_section_english, stage1_flat_english
from reader_pipeline.config import Manifest


# --- fixtures ----------------------------------------------------------------

FLAT_SPINE = {
    "work": "ENCH",
    "segments": [
        {"id": "1:1", "book": 1, "column": "1", "lines": [{"n": 1, "text": "α"}]},
        {"id": "1:2", "book": 1, "column": "2", "lines": [{"n": 1, "text": "β"}]},
        {"id": "1:3", "book": 1, "column": "3", "lines": [{"n": 1, "text": "γ"}]},
    ],
    "unassigned_lines": [],
}

BS_SPINE = {
    "work": "MED",
    "segments": [
        {"id": "1:1.1", "book": 1, "column": "1.1", "lines": [{"n": 1, "text": "α"}]},
        {"id": "1:1.2", "book": 1, "column": "1.2", "lines": [{"n": 1, "text": "β"}]},
        {"id": "2:2.1", "book": 2, "column": "2.1", "lines": [{"n": 1, "text": "γ"}]},
    ],
    "unassigned_lines": [],
}


def _flat_manifest(extra: dict | None = None) -> Manifest:
    data = {
        "work": {"id": "ENCH", "title": "Ench", "author": "epictetus",
                 "tlg_author": "0557", "tlg_work": "002", "greek_edition": "Fx"},
        "citation": {"scheme": "section"},
        "english": {
            "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                        "file": "fx/primary.json"},
            "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                          "file": "fx/secondary.json"},
        },
        "books": [{"n": 1, "start": "1", "end": "3"}],
    }
    data.update(extra or {})
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _bs_manifest(extra: dict | None = None) -> Manifest:
    data = {
        "work": {"id": "MED", "title": "Med", "author": "marcus-aurelius",
                 "tlg_author": "0562", "tlg_work": "001", "greek_edition": "Fx"},
        "citation": {"scheme": "book-section"},
        "english": {
            "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                        "file": "fx/primary.json"},
            "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                          "file": "fx/secondary.json"},
        },
        "books": [{"n": 1, "start": "1.1", "end": "1.2"},
                  {"n": 2, "start": "2.1", "end": "2.1"}],
    }
    data.update(extra or {})
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _stage_sources(module, tmp_path, monkeypatch, primary: dict, secondary: dict):
    """Point the module under test's SOURCES_DIR/BUILD_DIR at tmp and write
    the two clean chapter-keyed source JSONs."""
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True, exist_ok=True)
    (src / "fx" / "primary.json").write_text(
        json.dumps(primary, ensure_ascii=False), encoding="utf-8")
    (src / "fx" / "secondary.json").write_text(
        json.dumps(secondary, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "SOURCES_DIR", src)
    monkeypatch.setattr(module, "BUILD_DIR", tmp_path / "build")


# --- flat `section` scheme (stage1_flat_english) ------------------------------

FLAT_PRIMARY = {"1": "One.", "2": "Two.", "3": "Three."}
FLAT_SECONDARY = {"1": "Uno.", "2": "Due.", "3": "Tre."}


def test_flat_happy_path_builds_chunks_and_overlay(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, FLAT_SECONDARY)
    eng_path, align_path = stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["id"] for c in english["chunks"]] == ["1:1", "1:2", "1:3"]
    assert english["chunks"][2]["text"] == "Three."
    alignment = json.loads(align_path.read_text(encoding="utf-8"))
    assert all(p["english"] == p["segment"] for p in alignment["pairs"])
    ross = json.loads(
        (tmp_path / "build" / "stage1" / "ross_chunks.json").read_text(encoding="utf-8"))
    assert set(ross) == {"1:1", "1:2", "1:3"}
    assert ross["1:2"] == [{"chapter": "2", "text": "Due.", "cont": False, "bekker": []}]


def test_flat_extra_primary_key_fails_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   {**FLAT_PRIMARY, "4": "Phantom."}, FLAT_SECONDARY)
    with pytest.raises(ValueError, match=r"primary.*4"):
        stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)


def test_flat_extra_secondary_key_fails_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, {**FLAT_SECONDARY, "9": "Phantom."})
    with pytest.raises(ValueError, match=r"secondary.*9"):
        stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)


def test_flat_missing_primary_key_fails_loud_unless_allowed(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   {"1": "One.", "3": "Three."}, FLAT_SECONDARY)
    with pytest.raises(ValueError, match=r"primary.*2"):
        stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)
    # Declared via the existing primary allowance (segment-id form) it passes,
    # and the gap chapter is simply omitted from the chunks.
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   {"1": "One.", "3": "Three."}, FLAT_SECONDARY)
    manifest = _flat_manifest({"alignment_allow_unmatched": ["1:2"]})
    eng_path, _ = stage1_flat_english.run(manifest, FLAT_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["id"] for c in english["chunks"]] == ["1:1", "1:3"]


def test_flat_missing_secondary_key_fails_loud(tmp_path, monkeypatch):
    # THE silent-loss hole: a secondary gap used to vanish from
    # ross_chunks.json with no check anywhere (stage2 only covers primary).
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, {"1": "Uno.", "3": "Tre."})
    with pytest.raises(ValueError, match=r"secondary.*2"):
        stage1_flat_english.run(_flat_manifest(), FLAT_SPINE)


def test_flat_allowed_secondary_gap_passes(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, {"1": "Uno.", "3": "Tre."})
    manifest = _flat_manifest({"alignment_allow_unmatched_secondary": ["1:2"]})
    stage1_flat_english.run(manifest, FLAT_SPINE)
    ross = json.loads(
        (tmp_path / "build" / "stage1" / "ross_chunks.json").read_text(encoding="utf-8"))
    assert set(ross) == {"1:1", "1:3"}


def test_flat_wrong_book_allowance_rejected(tmp_path, monkeypatch):
    # allowances must resolve against exact spine segment ids — a bare-column
    # match let "999:2" mask a genuinely missing secondary chapter
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, {"1": "Uno.", "3": "Tre."})
    manifest = _flat_manifest({"alignment_allow_unmatched_secondary": ["999:2"]})
    with pytest.raises(ValueError, match="not in the Greek spine"):
        stage1_flat_english.run(manifest, FLAT_SPINE)


def test_flat_stale_allowance_for_an_actually_matched_key_is_a_hard_error(tmp_path, monkeypatch):
    # Two-way exact (Sol review blocker): an allowance entry for a segment
    # the source DOES cover is a stale declaration, not a silent no-op —
    # every primary key is present here, so "1:2" is unreviewably stale.
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, FLAT_SECONDARY)
    manifest = _flat_manifest({"alignment_allow_unmatched": ["1:2"]})
    with pytest.raises(ValueError, match=r"ARE matched"):
        stage1_flat_english.run(manifest, FLAT_SPINE)


def test_flat_stale_secondary_allowance_for_an_actually_matched_key_is_a_hard_error(tmp_path, monkeypatch):
    _stage_sources(stage1_flat_english, tmp_path, monkeypatch,
                   FLAT_PRIMARY, FLAT_SECONDARY)
    manifest = _flat_manifest({"alignment_allow_unmatched_secondary": ["1:2"]})
    with pytest.raises(ValueError, match=r"ARE matched"):
        stage1_flat_english.run(manifest, FLAT_SPINE)


# --- book-section scheme (stage1_book_section_english) — the same hole, and
# --- Discourses ships Long through this module -------------------------------

BS_PRIMARY = {"1.1": "One-one.", "1.2": "One-two.", "2.1": "Two-one."}
BS_SECONDARY = {"1.1": "Uno.", "1.2": "Due.", "2.1": "Tre."}


def test_book_section_happy_path(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    eng_path, _ = stage1_book_section_english.run(_bs_manifest(), BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["column"] for c in english["chunks"]] == ["1.1", "1.2", "2.1"]
    ross = json.loads(
        (tmp_path / "build" / "stage1" / "ross_chunks.json").read_text(encoding="utf-8"))
    assert set(ross) == {"1:1.1", "1:1.2", "2:2.1"}


def test_book_section_extra_primary_key_fails_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   {**BS_PRIMARY, "3.1": "Phantom."}, BS_SECONDARY)
    with pytest.raises(ValueError, match=r"primary.*3\.1"):
        stage1_book_section_english.run(_bs_manifest(), BS_SPINE)


def test_book_section_missing_secondary_key_fails_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, {"1.1": "Uno.", "2.1": "Tre."})
    with pytest.raises(ValueError, match=r"secondary.*1\.2"):
        stage1_book_section_english.run(_bs_manifest(), BS_SPINE)


def test_book_section_allowed_gaps_pass(tmp_path, monkeypatch):
    # Meditations' real shape: Haines (primary) misses a chapter declared in
    # alignment_allow_unmatched; Long (secondary) misses one declared in
    # alignment_allow_unmatched_secondary.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   {"1.1": "One-one.", "2.1": "Two-one."},
                   {"1.1": "Uno.", "1.2": "Due."})
    manifest = _bs_manifest({
        "alignment_allow_unmatched": ["1:1.2"],
        "alignment_allow_unmatched_secondary": ["2:2.1"],
    })
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert [c["column"] for c in english["chunks"]] == ["1.1", "2.1"]
    ross = json.loads(
        (tmp_path / "build" / "stage1" / "ross_chunks.json").read_text(encoding="utf-8"))
    assert set(ross) == {"1:1.1", "1:1.2"}


# --- __main__._stage1 dispatch: flat + book-section reach their dedicated
# --- English pass and return (never the has_sections deletion branch) ---------

def _dispatch_stage1(monkeypatch, tmp_path, manifest, spine, english_module_name):
    """Run __main__._stage1 with stage1_greek and the named English module
    faked out; returns (called-flag dict, build dir)."""
    import importlib

    main_mod = importlib.import_module("reader_pipeline.__main__")
    stage1_greek = importlib.import_module("reader_pipeline.stage1_greek")
    english_mod = importlib.import_module(f"reader_pipeline.{english_module_name}")

    build = tmp_path / "build"
    (build / "stage1").mkdir(parents=True)
    spine_path = build / "stage1" / "greek_spine.json"
    spine_path.write_text(json.dumps(spine, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(main_mod, "BUILD_DIR", build)
    monkeypatch.setattr(stage1_greek, "run", lambda m: spine_path)

    called: dict[str, bool] = {}

    def fake_run(m, sp):
        called["dedicated_pass"] = True
        eng = build / "stage1" / "english_chunks.json"
        eng.write_text(json.dumps(
            {"work": m.work_id, "translation": "Fx", "chunks": []},
            ensure_ascii=False), encoding="utf-8")
        align = build / "stage1" / "alignment.json"
        align.write_text(json.dumps(
            {"pairs": [], "english_only": []}, ensure_ascii=False), encoding="utf-8")
        return eng, align

    monkeypatch.setattr(english_mod, "run", fake_run)
    main_mod._stage1(manifest)
    return called, build


def test_stage1_dispatch_flat_scheme_reaches_dedicated_pass(tmp_path, monkeypatch):
    called, build = _dispatch_stage1(
        monkeypatch, tmp_path, _flat_manifest(), FLAT_SPINE, "stage1_flat_english")
    assert called.get("dedicated_pass"), (
        "flat scheme never reached stage1_flat_english.run — dispatch fell through")
    # The has_sections branch would have deleted the english scratch.
    assert (build / "stage1" / "english_chunks.json").exists()
    assert (build / "stage1" / "alignment.json").exists()


def test_stage1_dispatch_book_section_reaches_dedicated_pass(tmp_path, monkeypatch):
    called, build = _dispatch_stage1(
        monkeypatch, tmp_path, _bs_manifest(), BS_SPINE, "stage1_book_section_english")
    assert called.get("dedicated_pass"), (
        "book-section never reached stage1_book_section_english.run")
    assert (build / "stage1" / "english_chunks.json").exists()


# --- verse standoff sidecar (book-section, Diogenes Laertius' quoted verse) ---

def _stage_verse_sidecar(tmp_path, monkeypatch, sidecar: dict) -> None:
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True, exist_ok=True)
    (src / "fx" / "verse.json").write_text(
        json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(stage1_book_section_english, "SOURCES_DIR", src)


def test_verse_sidecar_attaches_validated_ranges_to_matching_chunks(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        # "One-one." is 8 chars; range [0, 8) covers the whole chunk, one
        # break strictly inside at offset 3 ("One" | "-one.").
        "1.1": [{"start": 0, "end": 8, "breaks": [3]}],
    })
    manifest = _bs_manifest({"english": {
        "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                    "file": "fx/primary.json", "verse_sidecar": "fx/verse.json"},
        "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                      "file": "fx/secondary.json"},
    }})
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["verse"] == [{"start": 0, "end": 8, "breaks": [3]}]
    # No sidecar entry for these columns — no `verse` key at all (never an
    # empty list), matching stage7_emit's conditional-spread convention.
    assert "verse" not in by_column["1.2"]
    assert "verse" not in by_column["2.1"]


def test_verse_sidecar_absent_leaves_every_chunk_verse_free(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    eng_path, _ = stage1_book_section_english.run(_bs_manifest(), BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert all("verse" not in c for c in english["chunks"])


def test_verse_sidecar_rejects_out_of_bounds_range(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 0, "end": 999, "breaks": []}],  # "One-one." is 8 chars
    })
    manifest = _bs_manifest({"english": {
        "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                    "file": "fx/primary.json", "verse_sidecar": "fx/verse.json"},
        "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                      "file": "fx/secondary.json"},
    }})
    with pytest.raises(ValueError, match=r"1\.1.*out of bounds"):
        stage1_book_section_english.run(manifest, BS_SPINE)


def test_verse_sidecar_rejects_a_break_on_the_range_boundary(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 0, "end": 8, "breaks": [8]}],  # not STRICTLY inside
    })
    manifest = _bs_manifest({"english": {
        "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                    "file": "fx/primary.json", "verse_sidecar": "fx/verse.json"},
        "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                      "file": "fx/secondary.json"},
    }})
    with pytest.raises(ValueError, match=r"1\.1.*not strictly inside"):
        stage1_book_section_english.run(manifest, BS_SPINE)


# --- verse standoff sidecar: overlapping/nested ranges (Sol review round —
# --- these used to pass bounds validation and silently corrupt rendering:
# --- Reader.svelte's groupVerse resets its `lines` accumulator on a second
# --- verseStart, discarding the first range's already-collected text) -------

def _verse_manifest():
    return _bs_manifest({"english": {
        "primary": {"id": "p", "name": "Primary Fx", "model": "archive",
                    "file": "fx/primary.json", "verse_sidecar": "fx/verse.json"},
        "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                      "file": "fx/secondary.json"},
    }})


def test_verse_sidecar_rejects_overlapping_ranges(tmp_path, monkeypatch):
    # "One-one." is 8 chars. [0,6) and [3,8) overlap without either nesting
    # the other. Direct repro against the UNPATCHED _validated_verse_ranges
    # confirmed this pair was silently ACCEPTED before this fix (both ranges
    # pass the per-range bounds/break check independently; nothing compared
    # them against each other) — see this task's brief for the repro output.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 0, "end": 6, "breaks": []},
                {"start": 3, "end": 8, "breaks": []}],
    })
    with pytest.raises(ValueError, match=r"1\.1.*overlap"):
        stage1_book_section_english.run(_verse_manifest(), BS_SPINE)


def test_verse_sidecar_rejects_nested_ranges(tmp_path, monkeypatch):
    # [0,8) fully contains [2,4) — also unaccepted before this fix, for the
    # same reason as the overlapping case above.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 0, "end": 8, "breaks": []},
                {"start": 2, "end": 4, "breaks": []}],
    })
    with pytest.raises(ValueError, match=r"1\.1.*overlap"):
        stage1_book_section_english.run(_verse_manifest(), BS_SPINE)


def test_verse_sidecar_accepts_adjacent_ranges(tmp_path, monkeypatch):
    # Legitimate: the next range's start equals the previous range's end —
    # abutting, not overlapping.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 0, "end": 4, "breaks": []},
                {"start": 4, "end": 8, "breaks": []}],
    })
    eng_path, _ = stage1_book_section_english.run(_verse_manifest(), BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["verse"] == [
        {"start": 0, "end": 4, "breaks": []},
        {"start": 4, "end": 8, "breaks": []},
    ]


def test_verse_sidecar_does_not_require_sorted_input(tmp_path, monkeypatch):
    # Non-overlapping ranges given out of start order still pass, and are
    # preserved in their given (input) order — sortedness is only used
    # internally for the overlap check, not imposed on the output.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_verse_sidecar(tmp_path, monkeypatch, {
        "1.1": [{"start": 4, "end": 8, "breaks": []},
                {"start": 0, "end": 4, "breaks": []}],
    })
    eng_path, _ = stage1_book_section_english.run(_verse_manifest(), BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["verse"] == [
        {"start": 4, "end": 8, "breaks": []},
        {"start": 0, "end": 4, "breaks": []},
    ]


# --- title + paras sidecars (book-section, Discourses only) ------------------

# A spine whose Greek carries stage1_greek's `sections` standoff channel on
# column "1.1" (the shape _parse_flat_book_section emits when
# citation.section_paragraphs opts in) — used to validate paras' "subset of
# the Greek channel's numbers" rule.
BS_SPINE_WITH_SECTIONS = {
    "work": "DISC",
    "segments": [
        {"id": "1:1.1", "book": 1, "column": "1.1",
         "lines": [{"n": 1, "text": "One-one.", "sections": [
             {"n": 1, "o": 0}, {"n": 2, "o": 4},
         ]}]},
        {"id": "1:1.2", "book": 1, "column": "1.2", "lines": [{"n": 1, "text": "One-two."}]},
        {"id": "2:2.1", "book": 2, "column": "2.1", "lines": [{"n": 1, "text": "Two-one."}]},
    ],
    "unassigned_lines": [],
}


def _stage_titles_paras(tmp_path, monkeypatch, titles: dict | None, paras: dict | None) -> None:
    src = tmp_path / "sources"
    (src / "fx").mkdir(parents=True, exist_ok=True)
    if titles is not None:
        (src / "fx" / "titles.json").write_text(
            json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    if paras is not None:
        (src / "fx" / "paras.json").write_text(
            json.dumps(paras, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(stage1_book_section_english, "SOURCES_DIR", src)


def _titles_paras_manifest(titles_sidecar: str | None = None, paras_sidecar: str | None = None):
    primary = {"id": "p", "name": "Primary Fx", "model": "archive", "file": "fx/primary.json"}
    if titles_sidecar:
        primary["titles_sidecar"] = titles_sidecar
    if paras_sidecar:
        primary["paras_sidecar"] = paras_sidecar
    return _bs_manifest({"english": {
        "primary": primary,
        "secondary": {"id": "s", "name": "Secondary Fx", "model": "archive",
                      "file": "fx/secondary.json"},
    }})


def test_titles_sidecar_attaches_title_to_matching_chunk_only(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_titles_paras(tmp_path, monkeypatch, {"1.1": "Of freedom"}, None)
    manifest = _titles_paras_manifest(titles_sidecar="fx/titles.json")
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["title"] == "Of freedom"
    assert "title" not in by_column["1.2"]
    assert "title" not in by_column["2.1"]


def test_titles_sidecar_absent_leaves_every_chunk_title_free(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    manifest = _titles_paras_manifest()
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    assert all("title" not in c for c in english["chunks"])


def test_paras_sidecar_attaches_validated_offsets_subset_of_greek_sections(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    # "One-one." is 8 chars; n=2 is a real member of the Greek sections
    # channel for column 1.1 (see BS_SPINE_WITH_SECTIONS).
    _stage_titles_paras(tmp_path, monkeypatch, None, {"1.1": [{"n": 2, "o": 4}]})
    manifest = _titles_paras_manifest(paras_sidecar="fx/paras.json")
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE_WITH_SECTIONS)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["paras"] == [{"n": 2, "o": 4}]
    assert "paras" not in by_column["1.2"]
    assert "paras" not in by_column["2.1"]


def test_paras_sidecar_out_of_bounds_offset_fails_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_titles_paras(tmp_path, monkeypatch, None, {"1.1": [{"n": 2, "o": 999}]})
    manifest = _titles_paras_manifest(paras_sidecar="fx/paras.json")
    with pytest.raises(ValueError, match=r"1\.1.*out of bounds"):
        stage1_book_section_english.run(manifest, BS_SPINE_WITH_SECTIONS)


def test_paras_sidecar_non_ascending_offsets_fail_loud(tmp_path, monkeypatch):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_titles_paras(tmp_path, monkeypatch, None, {
        "1.1": [{"n": 2, "o": 4}, {"n": 3, "o": 4}],
    })
    manifest = _titles_paras_manifest(paras_sidecar="fx/paras.json")
    with pytest.raises(ValueError, match=r"1\.1.*not strictly ascending"):
        stage1_book_section_english.run(manifest, BS_SPINE_WITH_SECTIONS)


def test_paras_sidecar_number_not_in_greek_sections_is_dropped_and_warned(tmp_path, monkeypatch, capsys):
    # n=99 is not a member of the Greek sections channel for 1.1 (only 1, 2
    # are) — dropped and reported (a printed WARNING), never a silent
    # absorb and never a hard build failure over an isolated coincidence.
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_titles_paras(tmp_path, monkeypatch, None, {"1.1": [{"n": 99, "o": 4}]})
    manifest = _titles_paras_manifest(paras_sidecar="fx/paras.json")
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE_WITH_SECTIONS)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert "paras" not in by_column["1.1"]
    assert "WARNING" in capsys.readouterr().out


def test_paras_sidecar_partial_drop_keeps_the_valid_entries(tmp_path, monkeypatch, capsys):
    _stage_sources(stage1_book_section_english, tmp_path, monkeypatch,
                   BS_PRIMARY, BS_SECONDARY)
    _stage_titles_paras(tmp_path, monkeypatch, None, {
        "1.1": [{"n": 2, "o": 4}, {"n": 99, "o": 6}],
    })
    manifest = _titles_paras_manifest(paras_sidecar="fx/paras.json")
    eng_path, _ = stage1_book_section_english.run(manifest, BS_SPINE_WITH_SECTIONS)
    english = json.loads(eng_path.read_text(encoding="utf-8"))
    by_column = {c["column"]: c for c in english["chunks"]}
    assert by_column["1.1"]["paras"] == [{"n": 2, "o": 4}]
    assert "WARNING" in capsys.readouterr().out
