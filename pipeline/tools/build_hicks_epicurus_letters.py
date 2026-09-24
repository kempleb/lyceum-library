"""Derive R. D. Hicks's 1925 Loeb translation of Epicurus' three letters (as
transcribed by Diogenes Laertius, Book X) from the already-built
`sources/hicks-dl/hicks-lives.clean.json` (see
pipeline/tools/extract_hicks_dl_perseus.py, which builds that store from the
pinned Perseus TEI). No re-parsing of the source XML: this is a pure re-key
of an existing, already-verified store, one letter's own {book}.{section}
range sliced out and renamed to this corpus's flat-scheme column tokens
("<letter-id>:<section>").

## The three ranges (Diogenes Laertius Book X's own running section count)

  * letter-to-herodotus: 10.35-10.83 (49 sections)
  * letter-to-pythocles: 10.84-10.116 (33 sections)
  * letter-to-menoeceus: 10.122-10.135 (14 sections)

These match manifests/epicurus-letter-to-*.yaml's own declared `books[]`
ranges exactly -- verified against those manifests directly, not assumed.

## Boundary-matter check (verified against the actual Hicks/Perseus text,
## not assumed -- CAVEAT the brief flagged explicitly)

Each letter's FIRST section (10.35, 10.84, 10.122) opens directly on
Epicurus' own words, in Hicks' own quotation marks -- no leading Diogenes
narrative. This holds for all three: Perseus/Hicks carries the salutation
("Epicurus to Herodotus/Pythocles/Menoeceus, greeting") as either a separate
title div before the letter (Herodotus, Menoeceus -- dropped by the Greek
spine's own `title_labels` declaration, an unrelated channel) or folded into
the END of the PRECEDING section on the Hicks/English side (Pythocles' and
Menoeceus' greetings both land at the tail of 10.83 and 10.121
respectively -- see below) -- never at the head of the section this script
treats as the letter's own first key.

The picture is NOT symmetric at the closing end, and this script does NOT
silently trim either case:

  * 10.83 (letter-to-herodotus's LAST section) ends with Diogenes' own
    resumptive narrative running directly into the NEXT letter's
    salutation, all inside this one section's text: '...Such is his
    epistle on Physics. Next comes the "epistle on Celestial Phenomena."
    "Epicurus to Pythocles, greeting."' None of that trailing matter is
    Epicurus' own letter -- it is Diogenes' connective tissue plus the next
    letter's greeting (which is why 10.84 itself opens clean, with no
    greeting repeated).
  * 10.135 (letter-to-menoeceus's LAST section) ends with Diogenes'
    resumptive summary: '...Such are his views on life and conduct; and he
    has discoursed upon them at greater length elsewhere.'
  * 10.116 (letter-to-pythocles's LAST section) carries NO trailing
    Diogenes matter -- it ends cleanly on the letter's own last sentence.
    (Diogenes' connective sentence introducing the Letter to Menoeceus
    instead opens 10.117, entirely outside this letter's declared range.)

Per the brief's own explicitly-sanctioned "simplest honest option": this
script keeps 10.83 and 10.135 VERBATIM, trailing matter and all -- the
section IS Diogenes' own section, and guessing at a trim boundary risks
silently cutting real Epicurus text. The exact trailing strings are
recorded below (`_BOUNDARY_TRAILING_MATTER`) and asserted present at
generation time (so a future re-extraction of hicks-lives.clean.json that
changes this text fails loud rather than silently drifting the documented
decision), and are also written into the meta.json's `boundary_matter`
field for any downstream consumer that wants to strip them later.
"""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path("../sources/hicks-dl/hicks-lives.clean.json")
OUT_LETTERS = Path("../sources/hicks-dl/hicks-epicurus-letters.clean.json")
OUT_META = Path("../sources/hicks-dl/hicks-epicurus-letters.meta.json")

# (letter id, DL Book X start section, DL Book X end section)
_LETTERS: list[tuple[str, int, int]] = [
    ("letter-to-herodotus", 35, 83),
    ("letter-to-pythocles", 84, 116),
    ("letter-to-menoeceus", 122, 135),
]

# Verified opening substring for each letter's first key (guards against a
# silent re-extraction drift introducing leading Diogenes narrative).
_BOUNDARY_OPENING = {
    "letter-to-herodotus": "“For those who are unable to study",
    "letter-to-pythocles": "“In your letter to me",
    "letter-to-menoeceus": "“Let no one be slow to seek wisdom",
}

# Verified trailing substring for each letter's LAST key -- present only
# where boundary non-letter matter genuinely exists (see module docstring).
# letter-to-pythocles's 10.116 carries no such matter and has no entry here.
_BOUNDARY_TRAILING_MATTER = {
    "letter-to-herodotus": (
        "Such is his epistle on Physics. Next comes the “epistle on "
        "Celestial Phenomena.” “Epicurus to Pythocles, greeting.”"
    ),
    "letter-to-menoeceus": (
        "Such are his views on life and conduct; and he has discoursed "
        "upon them at greater length elsewhere."
    ),
}


def _load_lives() -> dict[str, str]:
    return json.loads(SRC.read_text(encoding="utf-8"))


def build() -> tuple[dict[str, str], dict]:
    lives = _load_lives()
    letters: dict[str, str] = {}
    letters_meta: dict[str, dict] = {}

    for letter_id, start, end in _LETTERS:
        missing = []
        for n in range(start, end + 1):
            src_key = f"10.{n}"
            text = lives.get(src_key, "").strip()
            if not text:
                missing.append(src_key)
                continue
            letters[f"{letter_id}:{n}"] = text
        if missing:
            raise SystemExit(
                f"{letter_id}: hicks-lives.clean.json is missing/empty for "
                f"{len(missing)} expected DL Book X section(s): {missing}"
            )

        first_text = letters[f"{letter_id}:{start}"]
        opening = _BOUNDARY_OPENING[letter_id]
        assert first_text.startswith(opening), (
            f"{letter_id}: expected 10.{start} to open with {opening!r}, "
            f"got {first_text[:60]!r} -- boundary-matter decision above no "
            f"longer holds against the actual source text"
        )

        last_text = letters[f"{letter_id}:{end}"]
        trailing = _BOUNDARY_TRAILING_MATTER.get(letter_id)
        if trailing is not None:
            assert last_text.endswith(trailing), (
                f"{letter_id}: expected 10.{end} to end with {trailing!r}, "
                f"got ...{last_text[-80:]!r} -- boundary-matter decision "
                f"above no longer holds against the actual source text"
            )

        letters_meta[letter_id] = {
            "range": [start, end],
            "count": end - start + 1,
            "boundary_matter": {
                "leading_non_letter_text": None,
                "trailing_non_letter_text": trailing,
                "kept_verbatim": trailing is not None,
            },
        }

    meta = {
        "witness": "sources/hicks-dl/hicks-lives.clean.json "
                   "(pipeline/tools/extract_hicks_dl_perseus.py)",
        "source_file": "hicks-lives.clean.json",
        "generation": {
            "tool": "pipeline/tools/build_hicks_epicurus_letters.py",
            "method": "Direct re-key of hicks-lives.clean.json's Book X "
                      "10.<n> entries into this corpus's flat-scheme "
                      "'<letter-id>:<n>' column tokens -- no re-parsing, no "
                      "rewriting of the translated text itself.",
        },
        "known_limitations": [
            "10.83 (letter-to-herodotus's last section) and 10.135 "
            "(letter-to-menoeceus's last section) each carry Diogenes "
            "Laertius' own connective/resumptive narrative trailing the "
            "letter's actual last sentence, kept verbatim rather than "
            "trimmed -- see the module docstring's 'Boundary-matter check' "
            "for the verified evidence and the exact trailing strings.",
        ],
        "letters": letters_meta,
    }
    return letters, meta


def main() -> None:
    letters, meta = build()
    OUT_LETTERS.write_text(
        json.dumps(letters, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    OUT_META.write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_LETTERS} -- {len(letters)} sections across {len(_LETTERS)} letters")
    print(f"wrote {OUT_META}")


if __name__ == "__main__":
    main()
