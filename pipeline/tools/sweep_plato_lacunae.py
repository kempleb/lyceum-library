"""One-off investigation script (not part of the pipeline): sweep the 18
vendored Perseus Plato dialogues in sources/perseus-plato/ for signs of the
same defect class found at Cratylus 391b-c -- a Stephanus milestone whose
run of text is suspiciously short, or a missing letter-milestone within an
otherwise-populated page.

Two independent signals, both cheap and machine-checkable:

1. **Short entries.** Any `{slug}:{locus}` -> text entry under a low word-
   count threshold. A normal Stephanus letter-span runs several dozen words
   of English; anything under ~8 words is suspicious (it usually means the
   milestone fired but almost no text followed before the next one -- exactly
   the shape of the Cratylus 391c entry, whose stored text is the tail half
   of a sentence).
2. **Skipped letters.** For each dialogue, group keys by Stephanus page
   number and check the letter sequence run a-e (or however far that page
   goes) has no gaps -- e.g. page has a, b, d but no c.

Run: `cd pipeline && python3 tools/sweep_plato_lacunae.py`
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

STORE = Path(__file__).resolve().parent.parent.parent / "sources" / "perseus-plato" / "plato-stephanus.clean.json"

_KEY_RE = re.compile(r"^([a-z-]+):(\d+)([a-e])$")

SHORT_WORD_THRESHOLD = 8


def main() -> None:
    store: dict[str, str] = json.loads(STORE.read_text(encoding="utf-8"))

    by_dialogue: dict[str, dict[tuple[int, str], str]] = defaultdict(dict)
    for key, text in store.items():
        m = _KEY_RE.match(key)
        if not m:
            print(f"UNPARSEABLE KEY: {key!r}")
            continue
        slug, page, letter = m.group(1), int(m.group(2)), m.group(3)
        by_dialogue[slug][(page, letter)] = text

    short_entries: list[tuple[str, int]] = []
    gap_entries: list[str] = []

    for slug, locus_map in sorted(by_dialogue.items()):
        # -- signal 1: short entries --
        for (page, letter), text in locus_map.items():
            wc = len(text.split())
            if wc < SHORT_WORD_THRESHOLD:
                short_entries.append((f"{slug}:{page}{letter}", wc))

        # -- signal 2: skipped letters within a page's populated range --
        pages = defaultdict(set)
        for (page, letter) in locus_map:
            pages[page].add(letter)
        for page, letters in sorted(pages.items()):
            present = sorted(letters)
            lo, hi = present[0], present[-1]
            full_range = [c for c in "abcde" if lo <= c <= hi]
            missing = [c for c in full_range if c not in letters]
            if missing:
                gap_entries.append(f"{slug}:{page} missing letter(s) {missing} (has {present})")

    print(f"Total keys: {len(store)}")
    print(f"Dialogues: {len(by_dialogue)}")
    print()
    print(f"=== Short entries (< {SHORT_WORD_THRESHOLD} words): {len(short_entries)} ===")
    for key, wc in sorted(short_entries, key=lambda x: x[1]):
        print(f"  {key}: {wc} words -- {store[key.split(':', 1)[0] + ':' + key.split(':', 1)[1]]!r}")
    print()
    print(f"=== Skipped-letter gaps within a page: {len(gap_entries)} ===")
    for line in gap_entries:
        print(f"  {line}")
    print()
    print("=== Key counts per dialogue ===")
    for slug, locus_map in sorted(by_dialogue.items()):
        pages = sorted({p for p, _ in locus_map})
        print(f"  {slug}: {len(locus_map)} keys, pages {pages[0]}-{pages[-1]}")


if __name__ == "__main__":
    main()
