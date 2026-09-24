"""Build sources/dk-citations/doxographi-pages.json: which author each page of
Diels's Doxographi Graeci belongs to, as the DK heads that print a page show
it.

A DK dash head may print a "(D. NNN)" page, and rule E lets that page point
the dash back to an earlier source (stage1_citation_expansion.py). The page
may select an author only when the page is shown to be his (review finding 2,
2026-09-24). This tool reads every EXPLICIT head (one that names its author,
not a dash) in the 39 DK spines and records, per printed page, the dictionary
author keys printed with it. The stage owns a page for an author when the
nearest printed pages at or below and at or above it are his alone.

    uv run python pipeline/tools/build_doxographi_pages.py [--spines build/dk-spines]

The output holds page numbers and dictionary author keys only, no corpus text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipeline"))

from reader_pipeline import stage1_citation_expansion as ce  # noqa: E402

OUT = REPO / "sources" / "dk-citations" / "doxographi-pages.json"
_PAGE = re.compile(r"\(D\.\s*(\d+)")


def build(spines: Path) -> dict:
    dictionary = ce._load_dictionary()
    pages: dict[int, set[str]] = {}
    for f in sorted(spines.glob("*.json")):
        spine = json.loads(f.read_text(encoding="utf-8"))
        for seg in spine["segments"]:
            for head, _, _, _ in ce._segment_context(seg):
                if not head:
                    continue
                h = ce._nfc(head).strip()
                if ce._DASH_PREFIX.match(h):
                    continue
                tokens = re.findall(r"\S+", h)
                starts = ce._split_sources(dictionary, tokens, 0)
                for idx, (start, _, key) in enumerate(starts):
                    end = starts[idx + 1][0] if idx + 1 < len(starts) else len(tokens)
                    for m in _PAGE.finditer(" ".join(tokens[start:end])):
                        pages.setdefault(int(m.group(1)), set()).add(key)
    return {
        "_about": "Pages of Diels, Doxographi Graeci (1879) printed in explicit DK heads, "
                  "with the dictionary author keys printed with each. Built by "
                  "pipeline/tools/build_doxographi_pages.py from build/dk-spines; do not "
                  "hand-edit. The citation stage lets a dash's (D. NNN) page select an "
                  "author only when the nearest printed pages around it are his alone.",
        "pages": {str(p): sorted(keys) for p, keys in sorted(pages.items())},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spines", type=Path, default=REPO / "build" / "dk-spines")
    a = ap.parse_args(argv)
    table = build(a.spines)
    rows = ",\n".join(f"  {json.dumps(p)}: {json.dumps(k)}" for p, k in table["pages"].items())
    OUT.write_text(f'{{\n "_about": {json.dumps(table["_about"], ensure_ascii=False)},\n'
                   f' "pages": {{\n{rows}\n }}\n}}\n', encoding="utf-8")
    print(f"{len(table['pages'])} pages -> {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
