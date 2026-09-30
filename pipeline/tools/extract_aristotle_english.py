"""Vendor Bekker-column English from the sibling aristotle-reader public
build into sources/aristotle-english/aristotle-english.clean.json.

Reads ``$ARISTOTLE_DATA_DIR`` or ``../aristotle-reader/build/dist`` (relative
to this repo's root). Read-only. If that directory is absent, exits with an
error. Does not fall back to this repo's own ``build/dist`` mount: that mount
does not exist yet when source-passage English is resolved (docs/aristotle-
context-english-design.md, section C).

The public manifest is the one the sibling's public build loads
(``Manifest.for_work(work, public=True)``): ``manifests/<Abbr>-public.yaml``
when that file exists, otherwise ``manifests/<Abbr>.yaml`` for a work with no
public/private split. A ``-public.yaml`` always wins, so Metaphysics never
reads ``Meta.yaml`` (Tredennick) and Politics never reads ``Pol.yaml``
(Rackham).

The primary translation id must be the table's id. Where the yaml sets
``english.primary.id``, that is the id. A Perseus primary (Rhetoric, Nicomachean
Ethics) sets no ``english.primary``; the id is the sibling registry's
slot-``english`` translation (``shared/lib/works.ts``) whose name equals
``work.english_translation``. A secondary id is never taken as the primary.
A different id is fatal. This script does not substitute another translation.

A declared licence, when the manifest has one, must match the table. Any
``private: true`` flag is fatal. The built ``manifest.json``
``english_translation`` must equal the public manifest's
``work.english_translation``, so a dist emitted from a different manifest
cannot be vendored under this id.

No manifest in this table carries a machine-readable licence field (checked
2026-09-25). Silence plus no ``private`` flag is accepted as the table's
``public-domain-us``. Silence is also accepted as ``unverified``: De Anima
and Poetics make no public-domain claim (owner, 2026-09-22; vendored here
2026-09-25). A declared licence that differs is still fatal. The table never
marks those two ``public-domain-us``.

Four columns have no English object (Rhetoric 1:1378a and 2:1404a, Politics
5:1316a and 5:1316b). They are stored with empty text and their line numbers.
A blank line inside a text is fatal.

Scan-checked edits in ``sources/aristotle-english/corrections.json`` are
applied after the columns are built and before the store is written. Each
``find`` must occur exactly once in that key. A replacement that introduces
a blank line is fatal.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "sources" / "aristotle-english" / "aristotle-english.clean.json"
CORRECTIONS_PATH = REPO_ROOT / "sources" / "aristotle-english" / "corrections.json"

# abbr -> expected primary translation. Insertion order is the store's work
# order: Metaphysics, then the owner's 2026-09-25 table. Works are added
# here, never by reading whatever the sibling last built.
# De Anima and Poetics stay "unverified", never "public-domain-us".
_WORKS = {
    "Meta": {"translation_id": "ross", "licence": "public-domain-us"},
    "Phys": {"translation_id": "hardie", "licence": "public-domain-us"},
    "GC": {"translation_id": "joachim", "licence": "public-domain-us"},
    "Cael": {"translation_id": "stocks", "licence": "public-domain-us"},
    "Mete": {"translation_id": "webster", "licence": "public-domain-us"},
    "Rhet": {"translation_id": "freese", "licence": "public-domain-us"},
    "GA": {"translation_id": "platt", "licence": "public-domain-us"},
    "PA": {"translation_id": "ogle", "licence": "public-domain-us"},
    "Sens": {"translation_id": "beare", "licence": "public-domain-us"},
    "EN": {"translation_id": "rackham", "licence": "public-domain-us"},
    "Juv": {"translation_id": "ross", "licence": "public-domain-us"},
    "SE": {"translation_id": "pickard", "licence": "public-domain-us"},
    "HA": {"translation_id": "thompson", "licence": "public-domain-us"},
    "Top": {"translation_id": "pickard", "licence": "public-domain-us"},
    "Pol": {"translation_id": "jowett", "licence": "public-domain-us"},
    "Mirab": {"translation_id": "dowdall", "licence": "public-domain-us"},
    "Lin": {"translation_id": "joachim", "licence": "public-domain-us"},
    "DA": {"translation_id": "smith", "licence": "unverified"},
    "Poet": {"translation_id": "fyfe", "licence": "unverified"},
}

_KEY_RE = re.compile(r"^[A-Za-z]+:\d+:\d+[ab]$")


def _die(message: str) -> None:
    raise SystemExit(message)


def _data_dir() -> Path:
    env = os.environ.get("ARISTOTLE_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO_ROOT / ".." / "aristotle-reader" / "build" / "dist").resolve()


def _flagged_private(obj: object) -> bool:
    """True if any dict in obj sets ``private: true``. String values are not
    walked, so translation prose cannot trip the flag."""
    if isinstance(obj, dict):
        if obj.get("private") is True:
            return True
        return any(_flagged_private(v) for v in obj.values() if not isinstance(v, str))
    if isinstance(obj, list):
        return any(_flagged_private(v) for v in obj if not isinstance(v, str))
    return False


def _declared_licence(primary: dict) -> str | None:
    for key in ("licence", "license"):
        if key not in primary:
            continue
        val = primary[key]
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            status = val.get("status")
            if isinstance(status, str) and status.strip():
                return status.strip()
        _die(f"primary {key!r} is present but is not a licence status")
    return None


def _public_manifest_path(data_dir: Path, abbr: str) -> Path:
    """The manifest the sibling's public build would load for this work."""
    root = data_dir.parent.parent
    public = root / "manifests" / f"{abbr}-public.yaml"
    if public.is_file():
        return public
    plain = root / "manifests" / f"{abbr}.yaml"
    if plain.is_file():
        return plain
    _die(
        f"{abbr}: public manifest not found at {public} or {plain}. "
        f"This extractor does not fall back to this repo's build/dist."
    )


def _registry_english_primary(repo_root: Path, abbr: str) -> tuple[str, str]:
    """(id, name) of the sibling registry's slot-english translation.

    Used only when the public yaml has no ``english.primary`` (a Perseus
    primary). The name must still equal ``work.english_translation``; this
    does not pick a secondary.
    """
    path = repo_root / "shared" / "lib" / "works.ts"
    if not path.is_file():
        _die(f"{abbr}: no english.primary, and registry not found at {path}")
    text = path.read_text(encoding="utf-8")
    marks = list(re.finditer(r"^    id: '([A-Za-z0-9]+)',\s*$", text, re.M))
    block = None
    for i, mark in enumerate(marks):
        if mark.group(1) != abbr:
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[mark.start():end]
        break
    if block is None:
        _die(f"{abbr}: no work entry in {path}")
    found = re.findall(
        r"\{\s*id:\s*'([^']+)',\s*name:\s*'((?:\\'|[^'])*)',"
        r"\s*short:\s*'(?:\\'|[^'])*',\s*slot:\s*'english'\s*\}",
        block,
    )
    if len(found) != 1:
        _die(
            f"{abbr}: registry slot 'english' count is {len(found)} "
            f"(expected one primary); refusing to guess"
        )
    tid, name = found[0]
    return tid, name.replace("\\'", "'")


def _check_manifest(data_dir: Path, abbr: str, expected: dict) -> str:
    """Return the translation name the public build records. Fatal on
    id/licence mismatch or any private flag."""
    path = _public_manifest_path(data_dir, abbr)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        _die(f"{path}: manifest root must be an object")
    if _flagged_private(manifest):
        _die(f"{path}: private flag is set; refusing to vendor")
    work_block = manifest.get("work")
    if not isinstance(work_block, dict):
        _die(f"{path}: no work block")
    work_name = work_block.get("english_translation")
    if not isinstance(work_name, str) or not work_name.strip():
        _die(f"{path}: work.english_translation is missing")
    english = manifest.get("english")
    primary = english.get("primary") if isinstance(english, dict) else None
    if isinstance(primary, dict):
        found_id = primary.get("id")
        if found_id != expected["translation_id"]:
            _die(
                f"{path}: primary translation id {found_id!r} != expected "
                f"{expected['translation_id']!r}"
            )
        primary_name = primary.get("name")
        if isinstance(primary_name, str) and primary_name != work_name:
            print(
                f"{abbr}: note: english.primary.name {primary_name!r} != "
                f"work.english_translation {work_name!r}; id "
                f"{found_id!r} matches, vendoring the built columns"
            )
        licence_src = primary
    else:
        # Perseus primary: the yaml names the translation on the work block
        # and puts only secondaries under english.*. The id lives in the
        # public registry, matched by that same name.
        reg_id, reg_name = _registry_english_primary(path.parent.parent, abbr)
        if reg_name != work_name:
            _die(
                f"{path}: registry slot-english name {reg_name!r} != "
                f"work.english_translation {work_name!r}"
            )
        if reg_id != expected["translation_id"]:
            _die(
                f"{path}: registry primary id {reg_id!r} != expected "
                f"{expected['translation_id']!r}"
            )
        licence_src = {}
    declared = _declared_licence(licence_src)
    if declared is None:
        # See the module docstring. Silence is not a declared status.
        if expected["licence"] not in ("public-domain-us", "unverified"):
            _die(
                f"{path}: declares no licence status, and the table expects "
                f"{expected['licence']!r}"
            )
    elif declared != expected["licence"]:
        _die(
            f"{path}: licence {declared!r} != expected {expected['licence']!r}"
        )
    built_path = data_dir / abbr / "manifest.json"
    if not built_path.is_file():
        _die(f"{abbr}: built manifest not found at {built_path}")
    built = json.loads(built_path.read_text(encoding="utf-8"))
    if _flagged_private(built):
        _die(f"{built_path}: private flag is set; refusing to vendor")
    built_work = built.get("work") if isinstance(built, dict) else None
    if not isinstance(built_work, dict) or built_work.get("id") != abbr:
        _die(f"{built_path}: work.id is not {abbr!r}")
    built_name = built_work.get("english_translation")
    if built_name != work_name:
        _die(
            f"{built_path}: english_translation {built_name!r} != public "
            f"manifest work.english_translation {work_name!r} (dist was not "
            f"emitted from the public manifest)"
        )
    return work_name


def _load_work(data_dir: Path, abbr: str) -> dict:
    work_dir = data_dir / abbr
    files = sorted(work_dir.glob("book-*.json"), key=lambda p: int(p.stem.split("-", 1)[1]))
    if not files:
        _die(f"{abbr}: no book-NN.json under {work_dir}")
    store: dict = {}
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            _die(f"{path}: root must be an object")
        book = doc.get("book")
        if not isinstance(book, int) or isinstance(book, bool) or book < 1:
            _die(f"{path}: book must be a positive integer")
        segments = doc.get("segments")
        if not isinstance(segments, list) or not segments:
            _die(f"{path}: segments must be a non-empty list")
        for seg in segments:
            if not isinstance(seg, dict):
                _die(f"{path}: segment is not an object")
            if _flagged_private({k: v for k, v in seg.items() if k != "greek"}):
                _die(f"{path}: private flag is set on a segment; refusing to vendor")
            column = seg.get("column")
            if not isinstance(column, str):
                _die(f"{path}: segment column is missing")
            greek = seg.get("greek")
            if not isinstance(greek, list) or not greek:
                _die(f"{abbr}:{book}:{column}: greek line list is empty")
            lines = []
            for row in greek:
                if not isinstance(row, dict) or "n" not in row:
                    _die(f"{abbr}:{book}:{column}: a greek line has no n")
                n = row["n"]
                if not isinstance(n, int) or isinstance(n, bool):
                    _die(f"{abbr}:{book}:{column}: line number {n!r} is not an integer")
                lines.append(n)
            english = seg.get("english")
            if english is None:
                # Known empty columns (Rhetoric 1378a/1404a, Politics
                # 1316a/1316b) have Greek lines and no English object.
                text = ""
            elif not isinstance(english, dict):
                _die(f"{abbr}:{book}:{column}: english is not an object")
            else:
                text = english.get("text", "")
                if text is None:
                    text = ""
                if not isinstance(text, str):
                    _die(f"{abbr}:{book}:{column}: english text is not a string")
            key = f"{abbr}:{book}:{column}"
            if key in store:
                _die(f"duplicate store key {key}")
            store[key] = {"lines": lines, "text": text}
    return store


def _apply_corrections(store: dict, corrections: list) -> None:
    """Apply ``corrections.json`` to a built store, before it is written.

    Each entry's ``find`` must occur exactly once in that key's text. A
    replacement that introduces a blank line is fatal: column text is one
    paragraph, and a blank line would split it.
    """
    if not isinstance(corrections, list):
        _die("corrections must be a list")
    for i, entry in enumerate(corrections):
        if not isinstance(entry, dict):
            _die(f"correction {i}: entry is not an object")
        key = entry.get("key")
        find = entry.get("find")
        replace = entry.get("replace")
        where = f"correction {i}" if not isinstance(key, str) or not key else f"correction {key!r}"
        if not isinstance(key, str) or not key:
            _die(f"{where}: key is missing")
        if key not in store:
            _die(f"{where}: key is not in the store")
        if not isinstance(find, str) or find == "":
            _die(f"{where}: find is empty")
        if not isinstance(replace, str) or replace == "":
            _die(f"{where}: replace is empty")
        text = store[key]["text"]
        if not isinstance(text, str):
            _die(f"{where}: store text is not a string")
        count = text.count(find)
        if count != 1:
            _die(f"{where}: find occurs {count} times (expected exactly once)")
        new = text.replace(find, replace, 1)
        if new.count("\n\n") > text.count("\n\n"):
            _die(f"{where}: replacement introduces a blank line")
        store[key]["text"] = new


def _load_corrections() -> list:
    if not CORRECTIONS_PATH.is_file():
        _die(f"corrections file not found: {CORRECTIONS_PATH}")
    data = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        _die(f"{CORRECTIONS_PATH}: corrections must be a list")
    return data


def _check_store(store: dict) -> None:
    if not store:
        _die("store is empty")
    for key, entry in store.items():
        if not _KEY_RE.fullmatch(key):
            _die(f"bad key {key!r}")
        lines = entry["lines"]
        text = entry["text"]
        if not isinstance(lines, list) or not lines:
            _die(f"{key}: empty lines list")
        for n in lines:
            if not isinstance(n, int) or isinstance(n, bool):
                _die(f"{key}: line number {n!r} is not an integer")
        if not isinstance(text, str):
            _die(f"{key}: text is not a string")
        if "\n\n" in text:
            _die(f"{key}: text contains a blank line")


def main() -> None:
    data_dir = _data_dir()
    if not data_dir.is_dir():
        _die(
            f"Aristotle data dir not found: {data_dir}. "
            f"Set ARISTOTLE_DATA_DIR or build the sibling at "
            f"../aristotle-reader/build/dist. This extractor does not fall "
            f"back to this repo's build/dist."
        )
    store: dict = {}
    for abbr, expected in _WORKS.items():
        name = _check_manifest(data_dir, abbr, expected)
        work_store = _load_work(data_dir, abbr)
        store.update(work_store)
        print(f"{abbr}: {len(work_store)} columns ({name}, {expected['licence']})")
    _apply_corrections(store, _load_corrections())
    _check_store(store)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} -- {len(store)} keys")
    print(f"SHA-256 {digest}")


if __name__ == "__main__":
    main()
