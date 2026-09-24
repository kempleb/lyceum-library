"""One-shot migration: sources/*/dk-context-lang.json v1 (keyed by each
run's own LITERAL text -- a hard-rule violation, corpus source text
committed to the repo) -> v2 (keyed by `dk_lang.decision_key`, a hash of the
same normalized text, with a short NON-VERBATIM human-readable `note`; see
dk_lang.py's module doc for the full key-format contract).

Every decision VERDICT is preserved exactly -- only the key changes, from
literal text to a hash of that text, and each entry gains a `note` derived
from WHERE the run occurs in the export (a structural location label like
"B30, citation apparatus", never the run's own source text).

For each work this script:
  1. Loads the old (v1) file and computes each entry's new hash key,
     aborting loudly on any hash collision (two distinct old entries
     hashing to the same key -- astronomically unlikely at 64 bits, but
     checked rather than assumed).
  2. Writes the v2 file (hash keys, placeholder notes).
  3. Runs the REAL stage1 Greek parse for the work (reads the migrated file
     right back via the ordinary dk_lang.load_decisions/apply_context_language
     path) with a thin recording wrapper around apply_context_language, which
     both proves every migrated entry is genuinely still consulted (stage1's
     own stale-decision check is fatal, exactly as before migration) and
     captures each hash's occurrence location(s) for the note.
  4. Rewrites the v2 file with real notes.

Idempotent: re-running against an already-migrated (v2) file is a no-op up
to key stability (hash keys survive re-derivation unchanged) -- but is not
attempted/tested here since the migration is intended to run exactly once.

Usage (from the repo root, after `nvm use 22`; pipeline runs directly on
system Python via uv):

    uv run --with pytest python pipeline/tools/migrate_dk_context_lang_keys.py

Requires the Diogenes export XML for every dk author to already be cached
under build/export/Diogenes-Resources/xml/tlg/ (true for this repo's
current corpus -- see docs/tlg-phi-export.md) or TLG_DIR/Diogenes.app
reachable to export on demand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from reader_pipeline import dk_lang  # noqa: E402
from reader_pipeline import stage1_greek  # noqa: E402
from reader_pipeline.config import Manifest, SOURCES_DIR  # noqa: E402

_CATEGORY = {
    "citation": "citation apparatus",
    "keep-latin": "kept Latin quotation",
    "strip-german": "stripped German commentary",
}


def _short_loc(work_id: str, where: str) -> str:
    """`where` (e.g. "heraclitus-fragments B30" or "heraclitus-fragments div
    n='7,8' (div_map -> B7)") with the redundant leading work-id dropped --
    this is a structural location label synthesized by stage1_greek/dk_lang,
    never source text, so it is safe to use verbatim in a committed note."""
    prefix = f"{work_id} "
    return where[len(prefix):] if where.startswith(prefix) else where


def regenerate_notes(manifest: Manifest, decisions: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Regenerate every entry's `note` in `decisions` (already the shape
    written to sources/<work_id>/dk-context-lang.json by the caller) FROM
    SCRATCH, by running a REAL stage1 parse for `manifest`'s work with a
    recording `apply_context_language` wrapper -- both PROVES every entry
    is genuinely still consulted (stage1's own undecided-run/stale-entry
    checks are unconditionally fatal, unchanged) and captures each hash's
    occurrence location(s), which become the (non-verbatim, structural)
    note text. Mutates and returns `decisions` in place. Shared by
    `migrate_work` (below) and `pipeline/tools/dk_context_lang.py`'s
    `--finalize` step -- the note-generation approach the Wave 1b hash
    migration introduced, factored out so a NEW work's decision file gets
    the identical treatment a migrated one already got, not a
    reimplementation."""
    work_id = manifest.work_id
    occurrences: dict[str, list[str]] = {}
    real_apply = dk_lang.apply_context_language

    def _recording_apply(text, decisions_arg, *, where, used=None):
        local_used: set[str] = set()
        result = real_apply(text, decisions_arg, where=where, used=local_used)
        for h in local_used:
            occurrences.setdefault(h, []).append(where)
        if used is not None:
            used.update(local_used)
        return result

    dk_lang.apply_context_language = _recording_apply
    try:
        stage1_greek.run(manifest)
    finally:
        dk_lang.apply_context_language = real_apply

    missing = sorted(set(decisions) - set(occurrences))
    if missing:
        raise ValueError(
            f"{work_id}: {len(missing)} hash(es) never consulted by "
            f"stage1 -- a migration/finalize bug, not a real stale entry "
            f"(stage1 would have already raised on that): {missing[:5]}"
        )

    for h, wheres in occurrences.items():
        decision = decisions[h]["decision"]
        category = _CATEGORY.get(decision, decision)
        loc = _short_loc(work_id, wheres[0])
        extra = f" (+{len(wheres) - 1} more)" if len(wheres) > 1 else ""
        decisions[h]["note"] = f"{loc}, {category}{extra}"

    return decisions


def migrate_work(work_id: str) -> dict:
    """Migrate one work's dk-context-lang.json in place. Returns a small
    stats dict. Raises if the migrated file doesn't round-trip cleanly
    through a real stage1 run (an undecided run or a stale entry -- either
    would mean this script mis-derived a key)."""
    path = SOURCES_DIR / work_id / "dk-context-lang.json"
    old = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(old, dict):
        raise ValueError(f"{path}: root must be an object")

    key_for_text: dict[str, str] = {}
    for text, decision in old.items():
        if decision not in dk_lang.DECISIONS:
            raise ValueError(f"{work_id}: unrecognized decision {decision!r} for {text!r}")
        key = dk_lang.decision_key(dk_lang.normalize_run(text))
        if key in key_for_text and key_for_text[key] != text:
            raise ValueError(
                f"{work_id}: hash collision between {key_for_text[key]!r} and "
                f"{text!r} -- both hash to {key}"
            )
        key_for_text[key] = text

    migrated: dict[str, dict[str, str]] = {
        dk_lang.decision_key(dk_lang.normalize_run(text)): {"decision": decision, "note": "pending"}
        for text, decision in old.items()
    }
    if len(migrated) != len(old):
        raise ValueError(f"{work_id}: entry count changed during migration ({len(old)} -> {len(migrated)})")

    def _write(data: dict) -> None:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    _write(migrated)

    # Real stage1 run against the JUST-WRITTEN v2 file: proves it round-
    # trips (same decisions consulted for the same runs stage1 would have
    # seen against the v1 file -- stage1's own undecided-run/stale-entry
    # checks are unconditionally fatal, exactly as before this migration)
    # and records WHERE each hash occurs, for the note.
    manifest = Manifest.for_work(work_id)
    regenerate_notes(manifest, migrated)

    _write(migrated)
    return {"work_id": work_id, "entries": len(migrated)}


def main(argv: list[str]) -> int:
    only = set(argv) or None
    paths = sorted(SOURCES_DIR.glob("*/dk-context-lang.json"))
    stats = []
    for p in paths:
        work_id = p.parent.name
        if only and work_id not in only:
            continue
        print(f"migrating {work_id} ...", flush=True)
        stats.append(migrate_work(work_id))

    print()
    total = 0
    for s in stats:
        print(f"  {s['work_id']}: {s['entries']} entries")
        total += s["entries"]
    print(f"\n{len(stats)} file(s) migrated, {total} entries total.")

    # Belt-and-braces: every committed key across every file must now be a
    # 16-hex-char hash -- no verbatim (long or non-ASCII) key survives.
    bad: list[tuple[Path, str]] = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        for k in data:
            if len(k) != 16 or not all(c in "0123456789abcdef" for c in k):
                bad.append((p, k))
    if bad:
        print(f"\nBAD KEYS remain in {len(bad)} place(s):")
        for p, k in bad[:10]:
            print(f"  {p}: {k!r}")
        return 1
    print("OK: zero non-hash keys remain across every dk-context-lang.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
