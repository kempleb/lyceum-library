"""Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 4; Stage sequence 2).

Regenerates LSJ dictionary entries for keys that are referenced ONLY by a
mounted corpus's works (e.g. aristotle) and by no classical work -- using
THIS repo's stage5_lsj renderer (entry_html, shard_letter) directly against
the local Diogenes grc.lsj.xml, never trusting whatever HTML a mounted
corpus's own (possibly older) pre-built shards happen to carry
(mount-corpus.mjs's lsj-merge.mjs already gives immediate, cruder coverage
for those at mount time; this supersedes it -- see lsj-merge.mjs's own
docstring, "moots their flagged-inconsistent shards").

"Aristotle-only" (or, generically, "mounted-only") is defined structurally,
not by provenance/timing: a key is a regen candidate iff it is referenced by
some mounted work's analyses.json AND is not referenced by ANY work outside
the mounted set (a genuinely classical key, even one a mounted work happens
to reference too, is never touched -- "classical entries never overwritten",
Settled decision 4). The mounted-work id set is read from every
build/dist/.mounts/*.json file mount-corpus.mjs writes; if none exist (the
mount never ran, or no-op'd for a missing source), this is a clean no-op.

Unlike stage5_lsj.run(), which matches raw LEMMATA to LSJ keys via
lemma_candidates()'s fuzzy base/fold fallback chain, this module does an
EXACT-KEY lookup only: every analyses.json entry (mounted or classical
alike) already carries its own resolved `lsj: [...]` key list (mounted
corpora resolve their own keys the same way classical's stage4/stage5 do --
docs/p3-probe.md's key-path diff found analyses.json byte-shape identical
across both corpora), so there is no lemma-to-key matching left to redo
here, only key-to-entry rendering.

Run: uv run python -m reader_pipeline.lsj_topup
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from lxml import etree

from .config import BUILD_DIR
from .stage5_lsj import SHARD_DIR, _DICTIONARY_FILENAMES, _DIV_TAG, entry_html, shard_letter

# Every manifests/*.yaml source declares the same diogenes_data path; kept as
# one literal here (not re-parsed from YAML, to avoid a manifests/ dependency
# in a stage that runs across the whole corpus, not per-work) with an env
# override for machines where Diogenes lives elsewhere.
DEFAULT_DIOGENES_DATA = "/Applications/Diogenes.app/Contents/dependencies/data"


def diogenes_data_dir() -> Path:
    return Path(os.environ.get("DIOGENES_DATA", DEFAULT_DIOGENES_DATA))


def _mounted_work_ids(dist: Path) -> set[str]:
    mounts_dir = dist / ".mounts"
    if not mounts_dir.is_dir():
        return set()
    ids: set[str] = set()
    for f in sorted(mounts_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        ids.update(data.get("works") or [])
    return ids


def _referenced_keys(analyses_path: Path) -> set[str]:
    analyses = json.loads(analyses_path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for parses in analyses.values():
        for parse in parses:
            keys.update(parse.get("lsj", []))
    return keys


def _missing_from_shards(
    dist: Path, keys: set[str], language: dict[str, str]
) -> set[str]:
    """Keys from `keys` that are NOT present as an entry in their shard file
    under build/dist/<SHARD_DIR[language]>/<shard_letter(key)>.json --
    read-only, used by --check-only. Groups by (language, letter) so each
    shard file is read at most once, regardless of how many keys land in it.
    Missing shard directories/files simply mean every key routed there is
    missing (an entry can't be present in a shard that was never written)."""
    by_shard: dict[tuple[str, str], list[str]] = {}
    for k in keys:
        lang = language.get(k, "grc")
        by_shard.setdefault((lang, shard_letter(k)), []).append(k)

    missing: set[str] = set()
    shard_cache: dict[Path, dict | None] = {}
    for (lang, letter), shard_keys in by_shard.items():
        shard_dir = SHARD_DIR.get(lang)
        if shard_dir is None:
            # No shard directory defined for this language at all (would be
            # an unsupported-language regen, which a real run rejects) --
            # such a key cannot be present anywhere, so it counts missing.
            missing.update(shard_keys)
            continue
        shard_path = dist / shard_dir / f"{letter}.json"
        if shard_path not in shard_cache:
            shard = (
                json.loads(shard_path.read_text(encoding="utf-8"))
                if shard_path.exists()
                else {}
            )
            if not isinstance(shard, dict):
                print(
                    f"lsj_topup: shard {shard_path} root is not an object.",
                    file=sys.stderr,
                )
                shard_cache[shard_path] = None
            else:
                shard_cache[shard_path] = shard
        shard = shard_cache[shard_path]
        if shard is None:
            missing.update(shard_keys)
            continue
        for k in shard_keys:
            if k not in shard:
                missing.add(k)
    return missing


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Compute regen_keys as usual, then exit 0 if every one of them "
            "is already present in the emitted build/dist/lsj shards, else 1 "
            "(naming the count and first 10 still missing) -- never opens "
            "grc.lsj.xml. Used by build-public.mjs --from-dist to fail a "
            "release build that was not fully topped up before publish, on "
            "a machine with no Diogenes install."
        ),
    )
    args = parser.parse_args(argv if argv is not None else [])

    dist = BUILD_DIR / "dist"
    shard_dirs = set(SHARD_DIR.values())

    mounted_ids = _mounted_work_ids(dist)
    if not mounted_ids:
        print("lsj_topup: no mounted corpus found under build/dist/.mounts -- no-op.")
        return 0

    analyses_files = sorted(
        p for p in dist.glob("*/analyses.json") if p.parent.name not in shard_dirs
    )
    if not analyses_files:
        print("lsj_topup: no <work>/analyses.json found under build/dist", file=sys.stderr)
        return 1

    mounted_keys: set[str] = set()
    classical_keys: set[str] = set()
    mounted_language: dict[str, str] = {}  # key -> language, from the FIRST mounted work seen
    for af in analyses_files:
        work = af.parent.name
        keys = _referenced_keys(af)
        if work in mounted_ids:
            mounted_keys.update(keys)
            manifest_path = af.parent / "manifest.json"
            language = "grc"
            if manifest_path.exists():
                language = json.loads(manifest_path.read_text(encoding="utf-8")).get(
                    "language", "grc"
                )
            for key in keys:
                mounted_language.setdefault(key, language)
        else:
            classical_keys.update(keys)

    regen_keys = mounted_keys - classical_keys
    print(
        f"lsj_topup: {len(mounted_keys)} key(s) referenced by mounted work(s), "
        f"{len(mounted_keys & classical_keys)} already classical-covered, "
        f"{len(regen_keys)} to regenerate."
    )

    if not regen_keys:
        print("lsj_topup: nothing to regenerate.")
        return 0

    if args.check_only:
        # "Topped up" means present in the shard, not freshly regenerated --
        # a key that was already in build/dist/lsj/<letter>.json (topped up
        # by an earlier full build, or already classical-covered elsewhere)
        # counts, even though it is structurally back in regen_keys every
        # time the aristotle mount is present (mounted_keys - classical_keys
        # never empties out just because a prior run filled the shards).
        # Content is never compared here (overwrite semantics are unchanged
        # for a real run); presence alone is the invariant.
        missing = sorted(_missing_from_shards(dist, regen_keys, mounted_language))
        if not missing:
            print(
                f"lsj_topup: --check-only: all {len(regen_keys)} regen key(s) already "
                f"present in build/dist/{SHARD_DIR['grc']} shards -- release is topped up."
            )
            return 0
        sample = missing[:10]
        print(
            f"lsj_topup: --check-only: {len(missing)} of {len(regen_keys)} regen key(s) "
            f"missing from the shards (e.g. {sample}) -- this release was not fully "
            f"topped up before publish.",
            file=sys.stderr,
        )
        return 1

    # Only 'grc' is supported today (the mounted aristotle corpus is
    # entirely Greek); a mounted Latin key would need lat.ls.perseus-eng1.xml
    # streamed the same way, which no corpus mounted so far exercises.
    languages = {mounted_language.get(k, "grc") for k in regen_keys}
    unsupported = languages - {"grc"}
    if unsupported:
        raise ValueError(
            f"lsj_topup: regeneration requested for unsupported language(s) "
            f"{sorted(unsupported)} -- only grc is implemented"
        )

    dictionary_path = diogenes_data_dir() / _DICTIONARY_FILENAMES["grc"]
    if not dictionary_path.exists():
        print(
            f"lsj_topup: STOP -- grc.lsj.xml not found at {dictionary_path} "
            f"(set DIOGENES_DATA to override).",
            file=sys.stderr,
        )
        return 1

    div_tag = _DIV_TAG["grc"]
    div_open = f"<{div_tag} "
    div_close = f"</{div_tag}>"
    key_re = re.compile(rf'<{div_tag} [^>]*key="([^"]*)"')

    found: dict[str, dict] = {}
    buf: list[str] = []
    want = False
    key = ""
    with open(dictionary_path, encoding="utf-8") as f:
        for line in f:
            if div_open in line:
                m = key_re.search(line)
                key = m.group(1) if m else ""
                want = key in regen_keys
                buf = []
            if want:
                buf.append(line)
                if div_close in line:
                    fragment = "".join(buf)
                    start = fragment.index(div_open)
                    end = fragment.rindex(div_close) + len(div_close)
                    entry_el = etree.fromstring(fragment[start:end])
                    head = entry_el.findtext("head") or key
                    found[key] = {"key": key, "head": head, "html": entry_html(entry_el)}
                    want = False

    still_missing = sorted(regen_keys - found.keys())
    if still_missing:
        print(
            f"lsj_topup: {len(still_missing)} regen key(s) not found in "
            f"grc.lsj.xml (e.g. {still_missing[:8]}) -- left unresolved.",
        )

    shard_dir = dist / SHARD_DIR["grc"]
    shard_dir.mkdir(parents=True, exist_ok=True)
    by_shard: dict[str, list[str]] = {}
    for k in found:
        by_shard.setdefault(shard_letter(k), []).append(k)

    regenerated = 0
    for letter, keys in sorted(by_shard.items()):
        shard_path = shard_dir / f"{letter}.json"
        shard = (
            json.loads(shard_path.read_text(encoding="utf-8")) if shard_path.exists() else {}
        )
        for k in keys:
            shard[k] = found[k]
            regenerated += 1
        # sort_keys: see stage5_lsj.run's shard writer — shard bytes must
        # depend on content only, not on merge/regeneration order.
        shard_path.write_text(
            json.dumps(shard, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

    print(f"lsj_topup: regenerated {regenerated} key(s) across {len(by_shard)} shard(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
