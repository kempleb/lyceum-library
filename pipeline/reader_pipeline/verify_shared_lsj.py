"""Safety gate for the shared (de-duplicated) dictionaries — LSJ (Greek) and
Lewis & Short (Latin, Wave 2 Batch 1b).

After the per-work emit (stage 7) merges every work's dictionary shards into
the corpus-wide build/dist/<shard_dir>/<letter>.json (shard_dir is 'lsj' for
Greek, 'ls' for Latin — stage5_lsj.SHARD_DIR), this checks the property the
reader relies on: EVERY dictionary key referenced by EVERY work's
analyses.json resolves in ITS LANGUAGE's shared shards. If any key is
missing, a word popup would silently show no dictionary entry — so this
exits non-zero and names the gaps, and the deploy must not proceed.

Each work's language (and therefore which shard_dir its keys must resolve
against) is read from its own build/dist/<work>/manifest.json (`work.language`,
Greek default) — the two dictionaries are entirely separate key spaces (LSJ's
Beta Code vs L&S's plain-Latin-plus-macron-marks), so a Latin work's keys are
never checked against the Greek shards or vice versa.

The letter-bucketing here mirrors the FRONT-END rule (shared/lib/data.ts
`lsjShard`: skip a leading '*' capital marker, take the first ASCII [a-z], else
'_'), because that is the rule the reader uses to pick which shard file to fetch.

Run: uv run python -m reader_pipeline.verify_shared_lsj
"""

from __future__ import annotations

import json
import sys

from .config import BUILD_DIR
from .stage5_lsj import SHARD_DIR


def front_end_shard(key: str) -> str:
    """Replicate shared/lib/data.ts `lsjShard` exactly."""
    for ch in key:
        if ch == "*":
            continue
        if "a" <= ch <= "z":
            return ch
    return "_"


def main() -> int:
    dist = BUILD_DIR / "dist"
    shard_dirs = set(SHARD_DIR.values())  # {'lsj', 'ls'}
    shared_dirs = {name: dist / name for name in shard_dirs}

    # Load each shared shard once, per shard_dir. A shard_dir that doesn't
    # exist at all (e.g. a partial/filtered build that never processed a
    # work of that language) behaves exactly like a shard_dir with zero
    # shards: every lookup against it legitimately misses. Only a build that
    # actually REFERENCES a key of that language and can't find it fails.
    shard_cache: dict[tuple[str, str], dict] = {}

    def shard_for(shard_dir_name: str, letter: str) -> dict:
        cache_key = (shard_dir_name, letter)
        if cache_key not in shard_cache:
            f = shared_dirs[shard_dir_name] / f"{letter}.json"
            shard_cache[cache_key] = (
                json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            )
        return shard_cache[cache_key]

    analyses_files = sorted(
        p for p in dist.glob("*/analyses.json") if p.parent.name not in shard_dirs
    )
    if not analyses_files:
        print("FAIL: no <work>/analyses.json found under build/dist", file=sys.stderr)
        return 1

    total_keys = 0
    languages_seen: set[str] = set()
    missing: dict[str, set[str]] = {}  # work -> missing keys
    bad_language: dict[str, str] = {}  # work -> unrecognized language value
    for af in analyses_files:
        work = af.parent.name
        manifest_path = af.parent / "manifest.json"
        language = "grc"
        if manifest_path.exists():
            language = json.loads(manifest_path.read_text(encoding="utf-8")) \
                .get("work", {}).get("language", "grc")
        # FAIL-OPEN fix (Wave 2 Batch 1b review, item 4): an unrecognized
        # language used to fall back to "lsj" (Greek's shard dir) via
        # `.get(language, "lsj")` — a work whose manifest carries a typo'd
        # or otherwise unknown language would have its keys silently
        # checked against the WRONG dictionary's shards instead of failing.
        # Reject instead of guessing.
        if language not in SHARD_DIR:
            bad_language[work] = language
            continue
        shard_dir_name = SHARD_DIR[language]
        analyses = json.loads(af.read_text(encoding="utf-8"))
        seen: set[str] = set()
        for parses in analyses.values():
            for parse in parses:
                for key in parse.get("lsj", []):
                    if key in seen:
                        continue
                    seen.add(key)
                    total_keys += 1
                    languages_seen.add(language)
                    if key not in shard_for(shard_dir_name, front_end_shard(key)):
                        missing.setdefault(work, set()).add(key)

    for name, shared in shared_dirs.items():
        if not shared.is_dir():
            print(f"Shared {name}: (dir not built in this run)")
            continue
        n_entries = sum(len(shard_for(name, f.stem)) for f in shared.glob("*.json"))
        print(
            f"Shared {name}: {n_entries} entries across "
            f"{len(list(shared.glob('*.json')))} shards."
        )
    print(f"Checked {total_keys} referenced keys across {len(analyses_files)} works "
          f"(languages: {', '.join(sorted(languages_seen)) or 'none'}).")
    ok = True
    if bad_language:
        for work, language in sorted(bad_language.items()):
            print(f"  UNRECOGNIZED language {language!r} — {work}: not in "
                  f"{sorted(SHARD_DIR)}, none of its keys were checked", file=sys.stderr)
        print(f"FAIL: {len(bad_language)} work(s) declare an unrecognized "
              f"work.language — see stage5_lsj.SHARD_DIR.", file=sys.stderr)
        ok = False
    if missing:
        for work, keys in sorted(missing.items()):
            sample = ", ".join(sorted(keys)[:8])
            print(f"  MISSING in shared dictionary — {work}: {len(keys)} keys (e.g. {sample})",
                  file=sys.stderr)
        print(f"FAIL: {sum(len(k) for k in missing.values())} referenced dictionary "
              f"keys are not in the shared dictionaries.", file=sys.stderr)
        ok = False
    if not ok:
        return 1

    print("OK: every referenced dictionary key resolves in its shared dictionary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
