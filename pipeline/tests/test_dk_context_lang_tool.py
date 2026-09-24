from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "tools"))

from reader_pipeline import dk_lang, stage1_greek
from reader_pipeline.config import Manifest

import dk_context_lang  # noqa: E402
import migrate_dk_context_lang_keys as migrate  # noqa: E402

TEI_NS = "http://www.tei-c.org/ns/1.0"

FIXTURE_XML = f"""<TEI xmlns="{TEI_NS}"><text><body>
<div type="Fragment" n="1">
<p>PLUT. def. orac. 11 <hi rend="letter-spacing">logos legomenos</hi> oder vielmehr ARIST. Metaph.</p>
</div>
<div type="Fragment" n="2">
<p><hi rend="letter-spacing">ANOTHER logos</hi> vgl. B 1</p>
</div>
</body></text></TEI>"""
# Fixture is deliberately Latin-alphabet throughout (find_non_greek_runs
# only cares about Latin-vs-Greek script, not real Greek content) so the
# whole fixture doc is exercised without needing genuine Greek text.


def _manifest(work_id: str) -> Manifest:
    return Manifest(
        {
            "work": {"id": work_id, "author": "fixture", "language": "grc",
                      "tlg_author": "9999", "tlg_work": "001",
                      "greek_edition": "Fixture"},
            "citation": {"scheme": "dk", "series": "B"},
            "books": [{"n": 1, "start": "B1", "end": "B2"}],
        },
        ROOT / "manifests" / "fake.yaml",
    )


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """Redirects every path this tool/stage1 touches into tmp_path, and
    pre-places the fixture export XML exactly where run_export expects it
    so it short-circuits (file already exists) instead of shelling out to
    Diogenes -- the same hermetic-testing shape
    migrate_dk_context_lang_keys.py's own design assumes (cached export)."""
    export_dir = tmp_path / "export"
    build_dir = tmp_path / "build"
    sources_dir = tmp_path / "sources"
    monkeypatch.setattr(stage1_greek, "EXPORT_DIR", export_dir)
    monkeypatch.setattr(stage1_greek, "BUILD_DIR", build_dir)
    monkeypatch.setattr(stage1_greek, "SOURCES_DIR", sources_dir)

    xml_path = export_dir / "Diogenes-Resources" / "xml" / "tlg" / "tlg9999001.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(FIXTURE_XML, encoding="utf-8")

    manifest = _manifest("fixwork")
    return manifest, sources_dir, build_dir


def test_propose_writes_verbatim_flat_shape_to_build_scratch_only(wired):
    manifest, sources_dir, build_dir = wired
    path = dk_context_lang.propose(manifest)

    assert path == build_dir / "dk-proposals" / "fixwork.json"
    assert not (sources_dir / "fixwork").exists()  # nothing under sources/ yet

    proposal = json.loads(path.read_text(encoding="utf-8"))
    # dk_lang.propose_decisions' own flat shape: verbatim normalized text -> decision.
    # (Every non-Greek run needs a decision, including inside role='text'
    # blocks -- real corpus shape for an all-Latin fragment like Heraclitus
    # B4; this ASCII fixture's "Greek" spans are non-Greek script too, so
    # "logos legomenos"/"ANOTHER logos" -- the letter-spaced spans -- land
    # in the proposal exactly like a real Latin-fragment role='text' run would.)
    assert set(proposal) == {
        "PLUT. def. orac. 11", "logos legomenos", "oder vielmehr ARIST. Metaph",
        "ANOTHER logos", "vgl. B 1",
    }
    assert all(d in dk_lang.DECISIONS for d in proposal.values())
    # The German-prose run is heuristically flagged for a reviewer to confirm.
    assert proposal["oder vielmehr ARIST. Metaph"] == "strip-german"


def test_finalize_requires_a_prior_propose(wired):
    manifest, _sources_dir, _build_dir = wired
    with pytest.raises(FileNotFoundError, match="run --propose"):
        dk_context_lang.finalize(manifest)


def test_finalize_rejects_unrecognized_decision_value(wired):
    manifest, _sources_dir, build_dir = wired
    scratch = build_dir / "dk-proposals" / "fixwork.json"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text(json.dumps({"PLUT. def. orac. 11": "delete-it"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized decision"):
        dk_context_lang.finalize(manifest)


def test_finalize_writes_only_hash_keyed_notes_no_verbatim_text_under_sources(wired):
    manifest, sources_dir, _build_dir = wired
    dk_context_lang.propose(manifest)
    # A reviewer overrides the heuristic strip-german guess to keep-latin,
    # to prove finalize honors the REVIEWED value, not the heuristic one.
    scratch = dk_context_lang._scratch_path("fixwork")
    proposal = json.loads(scratch.read_text(encoding="utf-8"))
    proposal["oder vielmehr ARIST. Metaph"] = "keep-latin"
    scratch.write_text(json.dumps(proposal), encoding="utf-8")

    stats = dk_context_lang.finalize(manifest)
    assert stats == {"work_id": "fixwork", "entries": 5, "finalized": 5}
    assert not scratch.exists()  # scratch proposal cleaned up

    committed_path = sources_dir / "fixwork" / "dk-context-lang.json"
    raw = committed_path.read_text(encoding="utf-8")
    committed = json.loads(raw)
    assert len(committed) == 5
    for key, entry in committed.items():
        assert dk_lang._HASH_KEY_RE.match(key)  # 16-hex key, never literal text
        assert entry["decision"] in dk_lang.DECISIONS
        assert entry["note"] and entry["note"] != "pending"

    # No proposal key (the verbatim run text finalize started from) may
    # appear ANYWHERE in the finalized file -- not in a key, not in a note,
    # not by coincidence in any other field -- checked programmatically
    # against the whole raw serialized file, not one hardcoded entry's note.
    for proposal_key in proposal:
        assert proposal_key not in raw, (
            f"verbatim proposal text leaked into committed file: {proposal_key!r}"
        )

    # Honored the reviewer's override, not the raw heuristic guess.
    keep_latin_key = dk_lang.decision_key(dk_lang.normalize_run("oder vielmehr ARIST. Metaph"))
    assert committed[keep_latin_key]["decision"] == "keep-latin"

    # dk_lang.load_decisions (the real stage1 loader) accepts the file as-is.
    loaded = dk_lang.load_decisions(committed_path)
    assert loaded == committed


def test_finalize_is_idempotent_round_trip_via_load_decisions(wired):
    manifest, sources_dir, _build_dir = wired
    dk_context_lang.propose(manifest)
    dk_context_lang.finalize(manifest)
    committed_path = sources_dir / "fixwork" / "dk-context-lang.json"
    first = json.loads(committed_path.read_text(encoding="utf-8"))

    # Re-propose against the now-committed file: every run is already
    # decided, so the new scratch proposal reflects the COMMITTED
    # decisions exactly (not fresh heuristic guesses).
    path = dk_context_lang.propose(manifest)
    proposal = json.loads(path.read_text(encoding="utf-8"))
    assert proposal["oder vielmehr ARIST. Metaph"] == "strip-german"

    # Finalizing again with unchanged decisions is a no-op on content
    # (notes regenerate identically; keys/decisions unchanged).
    dk_context_lang.finalize(manifest)
    second = json.loads(committed_path.read_text(encoding="utf-8"))
    assert first == second


def test_stale_committed_entry_fails_loud_at_finalize(wired):
    # A committed decision whose run no longer occurs in a fresh export
    # (e.g. a manifest/export change) must surface as a hard error, not
    # silently vanish -- caught by stage1's own pre-existing
    # used-vs-declared staleness gate (fires from inside the real stage1
    # run `regenerate_notes` performs; `regenerate_notes`'s own "never
    # consulted" check is a second, redundant guard against a DIFFERENT
    # failure mode -- this tool mis-deriving a key -- that never gets a
    # chance to fire here because stage1's gate raises first).
    manifest, sources_dir, _build_dir = wired
    scratch_path = dk_context_lang.propose(manifest)
    proposal = json.loads(scratch_path.read_text(encoding="utf-8"))
    dk_context_lang.finalize(manifest)  # commits every real run cleanly first (deletes scratch)

    committed_path = sources_dir / "fixwork" / "dk-context-lang.json"
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    stale_key = dk_lang.decision_key(dk_lang.normalize_run("GHOST RUN NEVER SEEN"))
    committed[stale_key] = {"decision": "citation", "note": "hand-injected stale entry"}
    committed_path.write_text(json.dumps(committed), encoding="utf-8")
    prior_bytes = committed_path.read_bytes()

    # Re-supply the same reviewed proposal content by hand -- propose()
    # itself would now ALSO trip this same stale-entry gate against the
    # doctored committed file (its own permissive wrapper only silences
    # UNDECIDED runs, not a decided-but-never-used entry), so it can't be
    # used here to regenerate the scratch file.
    scratch_path.parent.mkdir(parents=True, exist_ok=True)
    scratch_path.write_text(json.dumps(proposal), encoding="utf-8")

    with pytest.raises(ValueError, match="stale entry"):
        dk_context_lang.finalize(manifest)

    # Atomic: a finalize that fails mid-regeneration leaves sources/ EXACTLY
    # as it was before the call -- never a half-written merged/pending file.
    assert committed_path.read_bytes() == prior_bytes


def test_finalize_failure_leaves_no_file_when_none_committed_before(wired):
    """Blocker 1(c)'s other half: when the work has NO committed decision
    file yet, a finalize that fails partway through (here: a proposal entry
    for a run that never actually occurs in the export, so stage1's own
    stale-entry gate -- fired from inside the real stage1 run
    regenerate_notes performs -- raises) must leave sources/ exactly as
    absent as it started -- not a newly-created, only-partially-finalized
    file."""
    manifest, sources_dir, _build_dir = wired
    scratch_path = dk_context_lang.propose(manifest)
    proposal = json.loads(scratch_path.read_text(encoding="utf-8"))
    proposal["A RUN THAT NEVER OCCURS IN THE FIXTURE"] = "citation"
    scratch_path.write_text(json.dumps(proposal), encoding="utf-8")

    committed_path = sources_dir / "fixwork" / "dk-context-lang.json"
    assert not committed_path.exists()  # first-ever finalize for this work

    with pytest.raises(ValueError, match="stale entry"):
        dk_context_lang.finalize(manifest)

    assert not committed_path.exists()  # atomic: nothing left behind on failure
    assert scratch_path.exists()  # scratch is only ever deleted on success


def test_regenerate_notes_via_migration_tool_path(wired, monkeypatch):
    """Nit (b): regenerate_notes is SHARED by dk_context_lang.py's
    --finalize (exercised throughout this file) and
    migrate_dk_context_lang_keys.py's own migrate_work (its
    `Manifest.for_work` / `regenerate_notes` call pair) -- prove that
    SECOND call site works end to end too, by running migrate_work itself
    against this fixture, not merely by calling regenerate_notes directly
    or only through finalize."""
    manifest, sources_dir, _build_dir = wired
    monkeypatch.setattr(migrate, "SOURCES_DIR", sources_dir)
    monkeypatch.setattr(Manifest, "for_work", classmethod(lambda cls, work, public=False: manifest))

    # Seed a v1-style file (literal run text as keys -- the shape
    # migrate_work exists to replace) directly, bypassing dk_context_lang.py
    # entirely, using the same runs the fixture export actually contains.
    v1 = {
        "PLUT. def. orac. 11": "citation",
        "logos legomenos": "keep-latin",
        "oder vielmehr ARIST. Metaph": "strip-german",
        "ANOTHER logos": "keep-latin",
        "vgl. B 1": "citation",
    }
    work_dir = sources_dir / "fixwork"
    work_dir.mkdir(parents=True, exist_ok=True)
    migrated_path = work_dir / "dk-context-lang.json"
    migrated_path.write_text(json.dumps(v1), encoding="utf-8")

    stats = migrate.migrate_work("fixwork")
    assert stats == {"work_id": "fixwork", "entries": 5}

    migrated = json.loads(migrated_path.read_text(encoding="utf-8"))
    assert len(migrated) == 5
    for key, entry in migrated.items():
        assert dk_lang._HASH_KEY_RE.match(key)  # 16-hex key, never literal text
        assert entry["decision"] in dk_lang.DECISIONS
        assert entry["note"] and entry["note"] != "pending"
    for text in v1:
        assert text not in migrated_path.read_text(encoding="utf-8")  # no verbatim text leaked

    # dk_lang.load_decisions (the real stage1 loader) accepts the result.
    assert dk_lang.load_decisions(migrated_path) == migrated


def test_propose_scratch_file_never_written_under_sources(wired):
    manifest, sources_dir, build_dir = wired
    dk_context_lang.propose(manifest)
    for p in sources_dir.rglob("*"):
        assert False, f"unexpected file under sources/: {p}"  # sources_dir must not even exist
    assert not sources_dir.exists()
