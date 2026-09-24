r"""One-off: extract the Perseus canonical-greekLit English translations of
the Plato dialogues DK's testimonia/fragments columns cite (the original 18)
plus six more vendored 2026-07-28 for wired-column candidates and Jowett
turn-alignment coverage (Laws, Parmenides, Crito, Euthyphro, Ion, Republic --
Republic in full as of 2026-07-28, see "Republic" below), into a single flat
`{slug}:{stephanus-locus}` -> text JSON store -- see
docs/plato-locus-resolver-design.md and sources/INVENTORY.md ("Plato"
section) for full source-verification detail.

Source: PerseusDL/canonical-greekLit, data/tlg0059/tlg<NNN>/
tlg0059.tlg<NNN>.perseus-eng2.xml, vendored (not re-fetched) from the sibling
plato-reader repo's already-verified, already-patched local copies -- see
sources/perseus-plato/SHA256SUMS (generated against those files) and that
repo's own sources/perseus-eng/PATCHES.md for the four hand-repaired missing
milestones (Symposium 181b, Protagoras 332c, Hippias Major 302d, Ion 539d --
only the first three are in this project's original 18-dialogue set) already
baked into the copies here.

## LICENSING RULE: every entry in this table must be US public domain by
publication date -- pre-1931 as of 2026 (CLAUDE.md), EXCEPT Republic vol. 2
(Books 6-10, Shorey, 1935), vendored under the project owner's explicit
pre-1940 ruling, 2026-07-28 -- see "Republic" below and
sources/perseus-plato/README.md.

## Structure (docs/plato-locus-resolver-design.md SS2.1; confirmed directly
against the vendored XML)

Each dialogue is one flat sequence of page-level
`<div type="textpart" subtype="section" resp="perseus" n="<page>">` divs (one
per Stephanus PAGE), each containing an inline `<milestone unit="section"
n="<page><letter>"/>` cursor at every Stephanus LETTER boundary -- i.e. the
`n` token IS already the full locus ("281a", not "281" + "a" needing
concatenation). Republic and Laws additionally nest these page-level divs one
level under `<div type="textpart" subtype="book" n="<book>">` -- confirmed by
direct inspection 2026-07-28 that this nesting is transparent to `_walk`
below (it recurses through every element regardless of div type/subtype, and
only opens a locus at a `milestone` element), so no walker change was needed
to support them.

Two confirmed irregularities the walker must handle:

- **Attribute order is not stable.** Most files write
  `n="..." unit="section" resp="Stephanus"`; Protagoras (022) writes
  `unit="section" n="..."` with no `resp` at all. Attributes are read by
  name, never by position, and `resp` is never relied on.
- **One non-numeric milestone.** Theaetetus carries a single
  `<milestone unit="section" n="imbedded dialogue"/>` -- a structural
  marker, not a locus. Any `n` not matching `^\d+[a-e]$` is ignored as a
  boundary (the running text simply continues under whichever real locus is
  already open).

`<note>` (Loeb editorial footnotes) and `<bibl>` (inline reference tags) are
dropped whole, tail text preserved; everything else (including `<quote>`)
passes through as ordinary running prose, per the design memo's extractor-
gotchas list.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import lxml.etree as ET

SRC_DIR = Path("../sources/perseus-plato")
OUT_STORE = SRC_DIR / "plato-stephanus.clean.json"

_TEI_NS = "http://www.tei-c.org/ns/1.0"
_NS = {"t": _TEI_NS}

# TLG work number -> (store slug, expected SHA-256 of the vendored file, per
# sources/perseus-plato/SHA256SUMS).
_DIALOGUES = {
    "002": ("apology", "0f4c12045fc3d26a69d1120cf8eff04b64bedd401291f292f91bba593439e679"),
    "004": ("phaedo", "09af4aadfe9ebc3c0d9778818ab2b055c972639936ec078badeb6709c6563d83"),
    "005": ("cratylus", "1425489e475cd79e7fbad43730461965b61a8db90271e6720364d8e90b9625b8"),
    "006": ("theaetetus", "c672069ec54efbe9e1835db522498387b1e6edc5f0c32302b79e078071cf8b56"),
    "007": ("sophist", "3cb5b0a3832778b9725395af24436f8a1a1c854355f7d7424dea93344feab1f5"),
    "010": ("philebus", "688c1f37ab3778ec1aa1319b46b98f3b4cf88b8cb4cc4afa4f3c5d79d731d547"),
    "011": ("symposium", "eb9ec5a5337f9d13e985c26aa044ef4ae08f07186f63ba91ab6b19f0526b3cb9"),
    "012": ("phaedrus", "36bf8be9f1c0cb3d61e5b41de00e8902732a9347921288ec9c708eb63824f499"),
    "018": ("charmides", "3b69d80e7ef2153119e6d4079b9836eecc9ba720401b69dde5fdd812c7c75421"),
    "019": ("laches", "ca6fd7818ad1e525ec0488cb9edd6c01c9e9b118742bacd403eda99c9d3e0749"),
    "020": ("lysis", "ae373dd5bf0a90b74ce245dccb2161de0194694b774eb0e03af13581103b67d7"),
    "021": ("euthydemus", "4bd2706bf67d5412103c5b6cd7f59a275fea8d998a886d75e20f5685f8ee7aa4"),
    "022": ("protagoras", "d1ab2c63408018a09f375314be5d5a0ba5db0eff582f341e8aa2c9aa91540ffe"),
    "023": ("gorgias", "eba5cb89d8a8dfac300a1a7d444808531711ad1472a76865f96ea00523940759"),
    "024": ("meno", "4076910e19611982035326947f22b778de8df6be7ab41b80f346437415d7282a"),
    "025": ("hippias-major", "266ef2ca9010b955854985dac979b81ffc4bfbe3e58b56461d1e91dc8f0a4135"),
    "026": ("hippias-minor", "d79c9c538f6eaaa53708520f2db1105fc05f847fcb0981f3b80a1da8d549df5a"),
    "031": ("timaeus", "cabe59ce4805f468899a8a2c36645a69f1eccf34d39f6c2570aea9fddfc7ffa2"),
    # Vendored 2026-07-28 for wired-column candidates (Laws, Parmenides) and
    # ~500 Jowett-aligned turns (Crito, Euthyphro, Ion) -- see
    # sources/perseus-plato/README.md for each dialogue's PD basis.
    "001": ("euthyphro", "3d3e1b93f43467ab7b3798c54384bac4d0c1bfdfc265e786192295f51455e5a5"),
    "003": ("crito", "52351887351233ca662ef780f152be3a011a7bd32284086f52554c205b88e129"),
    "009": ("parmenides", "a2274d0fd8303f033b5a87a033400e7c07491010e00fc9eed82d370493ea8934"),
    "027": ("ion", "39b23266f322cc3fdaadf48097296baf56f6888f7b7c4d060a67a2f5ea9b43d6"),
    "034": ("laws", "5a0c359699ea967ee86b84ac7e5891dbdb7f3ad62c17049d8571e775dcf278a2"),
    # Republic (030): Perseus's single vendored file is Shorey's two-volume
    # Loeb translation; the TEI dates its printing 1935-37, and vol. 1
    # (Books 1-5, first published 1930, revised 1937) may follow the
    # revision, so NEITHER volume is claimed public domain by date. Both are
    # vendored under the project owner's explicit pre-1940 ruling,
    # 2026-07-28 (see sources/perseus-plato/README.md). Both volumes
    # are in this single file and extracted together, in full, like any other
    # dialogue -- no page filter.
    "030": ("republic", "36826064d30be3b40d20b820f4904ed170d375e41dd3f450cbe4eb733054766d"),
}

_LOCUS_RE = re.compile(r"^\d+[a-e]$")

# Same rationale as extract_hicks_dl_perseus.py's identical set: characters
# never legitimately preceded by a space in English typography, so a pending
# separator space left by a dropped <note>/<bibl>'s surrounding whitespace is
# DROPPED rather than materialized right before one of these.
_NO_LEADING_SPACE = frozenset(",;:.")


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


class _Builder:
    """Incrementally collapses whitespace while building flattened text --
    same shape as extract_hicks_dl_perseus.py's `_Builder`, minus verse-range
    tracking (no verse sidecar needed here; see module docstring)."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._length = 0
        self._pending_space = False

    def append(self, raw: str | None) -> None:
        if not raw:
            return
        out: list[str] = []
        pending = self._pending_space
        for ch in raw:
            if ch.isspace():
                if self._length > 0 or out:
                    pending = True
            else:
                if pending and ch not in _NO_LEADING_SPACE:
                    out.append(" ")
                pending = False
                out.append(ch)
        if out:
            s = "".join(out)
            self._parts.append(s)
            self._length += len(s)
        self._pending_space = pending

    def text(self) -> str:
        return "".join(self._parts)


class _Cursor:
    """Tracks which locus key is currently open while walking one dialogue's
    flat page-div sequence, and the ordered `{slug}:{locus}` -> text store
    accumulated so far."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.store: dict[str, str] = {}
        self._current_key: str | None = None
        self._buf: _Builder | None = None

    def _flush(self) -> None:
        if self._current_key is not None and self._buf is not None:
            text = self._buf.text().strip()
            if text:
                self.store[self._current_key] = text

    def open_locus(self, n: str) -> None:
        self._flush()
        self._current_key = f"{self.slug}:{n}"
        self._buf = _Builder()

    def append(self, raw: str | None) -> None:
        if self._buf is not None:
            self._buf.append(raw)

    def finish(self) -> None:
        self._flush()


_DROPPED_WHOLE = ("note", "bibl")


def _walk(el: ET._Element, cursor: _Cursor) -> None:
    tag = _local(el.tag)
    if tag in _DROPPED_WHOLE:
        return  # editorial apparatus only -- tail text still handled by caller
    if tag == "milestone" and el.get("unit") == "section":
        n = el.get("n")
        if n and _LOCUS_RE.fullmatch(n):
            cursor.open_locus(n)
        return
    cursor.append(el.text)
    for child in el:
        _walk(child, cursor)
        cursor.append(child.tail)


def _verify_source(path: Path, expected_sha256: str) -> None:
    if not path.exists():
        raise SystemExit(
            f"missing {path} -- vendor it from "
            "~/Developer/plato-reader/sources/perseus-eng/ (read-only there) "
            "before running."
        )
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, got "
            f"{actual} -- the vendored copy must not have changed; "
            "re-verify against sources/perseus-plato/SHA256SUMS before proceeding."
        )


def extract_dialogue(path: Path, slug: str) -> dict[str, str]:
    tree = ET.parse(str(path))
    body = tree.getroot().find(".//t:text/t:body", _NS)
    root_div = body.find('t:div[@type="translation"]', _NS)
    cursor = _Cursor(slug)
    cursor.append(root_div.text)
    for child in root_div:
        _walk(child, cursor)
        cursor.append(child.tail)
    cursor.finish()
    return cursor.store


def main() -> None:
    store: dict[str, str] = {}
    for tlg_n, (slug, expected_sha256) in _DIALOGUES.items():
        path = SRC_DIR / f"tlg0059.tlg{tlg_n}.perseus-eng2.xml"
        _verify_source(path, expected_sha256)
        dialogue_map = extract_dialogue(path, slug)
        assert dialogue_map, f"{slug}: extracted zero sections"
        for key, text in dialogue_map.items():
            assert text.strip(), f"{key}: empty extracted text"
        store.update(dialogue_map)
        print(f"{slug}: {len(dialogue_map)} sections")

    OUT_STORE.write_text(
        json.dumps(store, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_STORE} -- {len(store)} keys total")


if __name__ == "__main__":
    main()
