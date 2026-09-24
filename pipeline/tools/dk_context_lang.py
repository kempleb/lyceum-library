"""Propose -> finalize authoring flow for a dk work's dk-context-lang.json
decision file (Wave 1b design memo §4.3; dk_lang.py's module doc for the
hash-key format; migrate_dk_context_lang_keys.py for the one-shot v1->v2
migration this tool does NOT replace).

The problem this fixes (task #52): `dk_lang.propose_decisions` produces a
review-ready proposal, but only in the OLD flat `{verbatim_run_text:
decision}` shape -- fine for a human/agent to read, but that shape must
NEVER be the thing that lands in a commit (hard rule: corpus source text is
never committed). Before this tool there was no path from "here is a raw
heuristic proposal" to "here is a reviewed, hash-keyed, noted decision
file" for a work that doesn't have one yet -- `migrate_dk_context_lang_keys.py`
only ever re-keys an EXISTING v1 file; it has no way to author a NEW one.

Two steps, meant to be run from the repo root after `nvm use 22`:

  uv run --with pytest python pipeline/tools/dk_context_lang.py --propose WORK_ID

    Runs a REAL stage1 dk-fragment parse against the work's (uncommitted,
    exported) TLG XML, collecting every distinct non-Greek run the parser
    would need a decision for, classifying each with dk_lang.classify_run,
    and writing the VERBATIM proposal -- dk_lang.propose_decisions' own
    flat `{normalized_run_text: decision}` shape, unchanged -- to an
    UNCOMMITTED scratch file: build/dk-proposals/<work_id>.json. This is
    the ONLY place this tool ever writes verbatim run text to disk; build/
    is gitignored, and the file must never be copied into sources/. A
    human or reviewing agent edits the `decision` values in place
    (one of dk_lang.DECISIONS: "citation" / "keep-latin" / "strip-german")
    before finalizing.

    When the work already HAS a committed sources/<work_id>/dk-context-
    lang.json, its entries are pre-seeded into the proposal at their
    already-committed decision (recovered from the live export text,
    never from the decision file itself, which carries no text) --
    re-running --propose after adding new fragments surfaces the FULL
    reviewable set, with only genuinely new runs carrying a fresh
    heuristic guess.

  uv run --with pytest python pipeline/tools/dk_context_lang.py --finalize WORK_ID

    Reads the (reviewed) scratch proposal, converts every entry to the
    committed hash+note shape via dk_lang.decision_key (never the literal
    text), merges it into sources/<work_id>/dk-context-lang.json, then
    reuses migrate_dk_context_lang_keys.regenerate_notes -- the same real-
    stage1-run-with-recording-wrapper note-generation the v1->v2 migration
    used -- to both PROVE every finalized entry is genuinely consulted and
    derive its non-verbatim structural `note`. The scratch proposal file is
    deleted on success.

Both steps require the work's manifest to already parse cleanly except for
missing/undecided dk-context-lang.json entries -- this tool authors
decisions, it does not discover div/role structure (that's ordinary
manifest authoring against `python -m reader_pipeline stage1`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from reader_pipeline import dk_lang  # noqa: E402
from reader_pipeline import stage1_greek  # noqa: E402
from reader_pipeline.config import Manifest  # noqa: E402

import migrate_dk_context_lang_keys as migrate  # noqa: E402


def _scratch_path(work_id: str) -> Path:
    # stage1_greek.BUILD_DIR, read at CALL time (not imported by value) so
    # a test's `monkeypatch.setattr(stage1_greek, "BUILD_DIR", ...)`
    # redirects this too, exactly like it already redirects stage1's own
    # reads/writes -- one source of truth for "where build/ actually is."
    return stage1_greek.BUILD_DIR / "dk-proposals" / f"{work_id}.json"


def _decisions_path(work_id: str) -> Path:
    return stage1_greek.SOURCES_DIR / work_id / "dk-context-lang.json"


def collect_proposals(manifest: Manifest) -> dict[str, str]:
    """Every distinct non-Greek run `manifest`'s work contains, normalized
    text -> a decision: the work's own already-committed decision when one
    exists (recovered from the live export text via its hash, never stored
    verbatim anywhere), else `dk_lang.classify_run`'s heuristic guess.

    Runs the real stage1 dk-fragment parse (`stage1_greek.run`) with
    `dk_lang.apply_context_language` intercepted so it never raises on an
    undecided run (its normal fail-loud contract against the real
    committed-decisions path): any run with no decision yet is
    classified-and-accepted on the spot, in the SAME `decisions` dict
    object `_parse_fragments` threads through the whole document (loaded,
    unmodified, via the ordinary `_dk_load_context_lang` -- {} when the
    work has no committed file yet), so the whole document is walked in
    one pass with no scratch decisions pre-supplied and every entry the
    real committed-decisions path would eventually need gets surfaced."""
    proposals: dict[str, str] = {}
    real_apply = dk_lang.apply_context_language

    def _proposing_apply(text, decisions, *, where, used=None):
        for run in dk_lang.find_non_greek_runs(text):
            normalized = dk_lang.normalize_run(run)
            key = dk_lang.decision_key(normalized)
            if key not in decisions:
                decisions[key] = {"decision": dk_lang.classify_run(run), "note": "proposal"}
            proposals.setdefault(normalized, decisions[key]["decision"])
        return real_apply(text, decisions, where=where, used=used)

    dk_lang.apply_context_language = _proposing_apply
    try:
        stage1_greek.run(manifest)
    finally:
        dk_lang.apply_context_language = real_apply
    return proposals


def propose(manifest: Manifest) -> Path:
    proposals = collect_proposals(manifest)
    path = _scratch_path(manifest.work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(proposals, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def finalize(manifest: Manifest) -> dict:
    work_id = manifest.work_id
    scratch = _scratch_path(work_id)
    if not scratch.exists():
        raise FileNotFoundError(
            f"no proposal file at {scratch} -- run --propose {work_id} "
            f"first (and review its decisions) before finalizing"
        )
    proposal = json.loads(scratch.read_text(encoding="utf-8"))
    if not isinstance(proposal, dict):
        raise ValueError(f"{scratch}: root must be an object")
    bad = {t: d for t, d in proposal.items() if d not in dk_lang.DECISIONS}
    if bad:
        raise ValueError(
            f"{work_id}: unrecognized decision(s) in {scratch} (must be "
            f"one of {sorted(dk_lang.DECISIONS)}): {list(bad.items())[:5]}"
        )

    path = _decisions_path(work_id)
    # Byte-exact backup of whatever is currently committed (None when the
    # work has no decision file yet), captured BEFORE any write below, so
    # any failure during validation/regeneration can restore this work's
    # sources/ tree to EXACTLY its prior state rather than leaving it
    # mutated by a finalize that ultimately fails.
    prior_bytes = path.read_bytes() if path.exists() else None
    # A pre-existing committed file must round-trip through the SAME
    # loader stage1 itself uses -- a stale/malformed file (e.g. a
    # pre-migration literal-text-keyed file) fails loudly HERE, before
    # anything below mutates it, rather than surfacing as a confusing
    # downstream error mid-regeneration.
    existing: dict[str, dict[str, str]] = (
        dk_lang.load_decisions(path) if prior_bytes is not None else {}
    )

    # Every existing committed entry carries forward even if the reviewed
    # scratch proposal doesn't mention it (a genuinely stale committed
    # entry -- the run no longer occurs in a fresh export -- surfaces as a
    # hard "never consulted" error from regenerate_notes below, the same
    # fail-loud behavior the migration script already relies on, rather
    # than silently vanishing here).
    merged: dict[str, dict[str, str]] = dict(existing)
    key_for_text: dict[str, str] = {}
    for text, decision in proposal.items():
        key = dk_lang.decision_key(dk_lang.normalize_run(text))
        if key in key_for_text and key_for_text[key] != text:
            raise ValueError(
                f"{work_id}: hash collision between {key_for_text[key]!r} "
                f"and {text!r} -- both hash to {key}"
            )
        key_for_text[key] = text
        merged[key] = {"decision": decision, "note": "pending"}

    path.parent.mkdir(parents=True, exist_ok=True)

    def _write(data: dict) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    # Atomic from the caller's point of view: regenerate_notes needs the
    # CANDIDATE merged content on disk at the real committed path (the
    # only place stage1's own _dk_load_context_lang ever reads from -- see
    # its doc), so validation cannot happen purely off to the side. Every
    # write below is instead guarded by the backup captured above: on ANY
    # failure (including one raised deep inside the real stage1 run
    # regenerate_notes performs), the real path is restored to
    # prior_bytes exactly, or removed if it didn't exist before -- sources/
    # is never left holding unvalidated, only-partially-finalized content.
    try:
        _write(merged)
        migrate.regenerate_notes(manifest, merged)
        _write(merged)
    except BaseException:
        if prior_bytes is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(prior_bytes)
        raise
    scratch.unlink()
    return {"work_id": work_id, "entries": len(merged), "finalized": len(proposal)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--propose", metavar="WORK_ID", help="write an uncommitted, reviewable proposal")
    group.add_argument("--finalize", metavar="WORK_ID", help="commit a reviewed proposal as hash+note decisions")
    args = parser.parse_args(argv)

    if args.propose:
        manifest = Manifest.for_work(args.propose)
        path = propose(manifest)
        proposal = json.loads(path.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for d in proposal.values():
            counts[d] = counts.get(d, 0) + 1
        print(f"proposed {len(proposal)} run(s) for {args.propose} -> {path}")
        if counts:
            print("  " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"  review/edit {path}, then run --finalize {args.propose}")
        return 0

    manifest = Manifest.for_work(args.finalize)
    stats = finalize(manifest)
    print(
        f"finalized {args.finalize}: {stats['finalized']} run(s) merged, "
        f"{stats['entries']} total committed entries"
    )
    print(f"  wrote sources/{args.finalize}/dk-context-lang.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
