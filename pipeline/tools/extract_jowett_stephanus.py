"""Extract Benjamin Jowett's aligned Plato translation into a flat
Stephanus-keyed JSON store.

Input: plato-reader build output with one JSON per book at
`<PLATO_DIST>/<WorkName>/book-*.json`. Each book file contains a `turnFlow`
with `turns`; each turn carries a Stephanus column in `g.c`, a reference text
in `e`, and an optional aligned Jowett turn text in `alt.jowett.e`.

Output:
- `sources/jowett-plato/jowett-stephanus.clean.json`
- `sources/jowett-plato/meta.json`

Only works whose title maps to a slug already present in
`sources/perseus-plato/plato-stephanus.clean.json` are included.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_STORE = REPO_ROOT / "sources" / "perseus-plato" / "plato-stephanus.clean.json"
OUT_NAME = "jowett-stephanus.clean.json"
META_NAME = "meta.json"

_PLATO_DIALOGUES = {
    "Apology": "apology",
    "Charmides": "charmides",
    "Cratylus": "cratylus",
    "Euthydemus": "euthydemus",
    "Gorgias": "gorgias",
    "HippiasMajor": "hippias-major",
    "HippiasMinor": "hippias-minor",
    "Laches": "laches",
    "Lysis": "lysis",
    "Meno": "meno",
    "Phaedo": "phaedo",
    "Phaedrus": "phaedrus",
    "Philebus": "philebus",
    "Protagoras": "protagoras",
    "Sophist": "sophist",
    "Symposium": "symposium",
    "Theaetetus": "theaetetus",
    "Timaeus": "timaeus",
    # Added 2026-07-28 alongside the six new primary-store dialogues. Only
    # these three (of the six) have Jowett turns aligned in plato-reader's
    # build/dist -- Laws, Republic, and Parmenides are plato-reader's own
    # deferred set (narrated/monologue or granularity-mismatched works; see
    # its sources/INVENTORY.md) and carry no `alt.jowett` data at all, so
    # they simply won't appear in `unmapped_works`' complement -- there is
    # nothing to map.
    "Crito": "crito",
    "Euthyphro": "euthyphro",
    "Ion": "ion",
}


def _load_allowed_slugs() -> set[str]:
    data = json.loads(SOURCE_STORE.read_text(encoding="utf-8"))
    return {key.split(":", 1)[0] for key in data}


def _strip_or_empty(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _jowett_text(turn: dict) -> str:
    alt = turn.get("alt")
    if not isinstance(alt, dict):
        return ""
    jowett = alt.get("jowett")
    if not isinstance(jowett, dict):
        return ""
    return _strip_or_empty(jowett.get("e"))


def _reference_text(turn: dict) -> str:
    return _strip_or_empty(turn.get("e"))


def _load_turns(book_path: Path) -> list[dict]:
    data = json.loads(book_path.read_text(encoding="utf-8"))
    turn_flow = data.get("turnFlow")
    if not isinstance(turn_flow, dict):
        raise ValueError(f"{book_path}: missing turnFlow object")
    turns = turn_flow.get("turns")
    if not isinstance(turns, list):
        raise ValueError(f"{book_path}: missing turnFlow.turns list")
    return turns


def _extract_work(work_dir: Path, slug: str) -> tuple[dict[str, str], dict]:
    store: dict[str, str] = {}
    columns: dict[str, list[dict[str, str]]] = {}
    book_files = sorted(p for p in work_dir.glob("book-*.json") if p.is_file())
    for book_path in book_files:
        for turn in _load_turns(book_path):
            if not isinstance(turn, dict):
                continue
            g = turn.get("g")
            if not isinstance(g, dict):
                continue
            locus = g.get("c")
            if not isinstance(locus, str) or not locus:
                continue
            columns.setdefault(locus, []).append(
                {
                    "reference": _reference_text(turn),
                    "jowett": _jowett_text(turn),
                }
            )

    covered = 0
    partial_omitted = 0
    all_null_omitted = 0
    for locus, turns in columns.items():
        has_reference = any(turn["reference"] for turn in turns)
        text_parts = [turn["jowett"] for turn in turns if turn["jowett"]]
        if not has_reference:
            all_null_omitted += 1
            continue
        if any(turn["reference"] and not turn["jowett"] for turn in turns):
            partial_omitted += 1
            continue
        store[f"{slug}:{locus}"] = " ".join(text_parts)
        covered += 1

    stats = {
        "work": work_dir.name,
        "slug": slug,
        "book_files": [p.name for p in book_files],
        "covered_columns": covered,
        "omitted_columns": partial_omitted + all_null_omitted,
        "partial_omitted": partial_omitted,
        "all_null_omitted": all_null_omitted,
    }
    return store, stats


def build_artifacts(plato_dist: Path, out_dir: Path) -> tuple[dict[str, str], dict]:
    allowed_slugs = _load_allowed_slugs()
    clean: dict[str, str] = {}
    work_list: list[dict] = []
    unmapped_works: list[str] = []

    for work_dir in sorted(p for p in plato_dist.iterdir() if p.is_dir()):
        if not any(work_dir.glob("book-*.json")):
            continue  # not a work directory (lexica, reports, indices)
        slug = _PLATO_DIALOGUES.get(work_dir.name)
        if slug is None or slug not in allowed_slugs:
            unmapped_works.append(work_dir.name)
            continue
        work_store, stats = _extract_work(work_dir, slug)
        clean.update(work_store)
        work_list.append(stats)

    meta = {
        "source_repo_path": str(plato_dist.resolve()),
        "source_store_path": str(SOURCE_STORE),
        "work_list": sorted(work_list, key=lambda item: item["work"]),
        "unmapped_works": sorted(unmapped_works),
        "generation_parameters": {
            "input_book_glob": "book-*.json",
            "turn_text_path": "turnFlow.turns[*].alt.jowett.e",
            "reference_text_path": "turnFlow.turns[*].e",
            "coverage_rule": (
                "covered only when every non-empty reference turn in a column "
                "also has a non-empty Jowett turn; empty-reference turns do "
                "not count toward coverage but still contribute text to a "
                "covered column; columns with no non-empty reference turns "
                "are omitted entirely (all_null_omitted)"
            ),
            "column_separator": " ",
            "output_sort_keys": True,
            "ensure_ascii": False,
            "indent": 2,
            "trailing_newline": True,
        },
    }
    return clean, meta


def write_outputs(clean: dict[str, str], meta: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_path = out_dir / OUT_NAME
    meta_path = out_dir / META_NAME
    clean_path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return clean_path, meta_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plato-dist", required=True, help="Path to plato-reader build output")
    parser.add_argument("--out", required=True, help="Output directory for jowett-plato artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plato_dist = Path(args.plato_dist)
    out_dir = Path(args.out)
    clean, meta = build_artifacts(plato_dist, out_dir)
    write_outputs(clean, meta, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
