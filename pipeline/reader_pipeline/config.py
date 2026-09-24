"""Manifest loading and path resolution.

Repo layout assumed:
    plato-reader/            <- repo root
      manifests/ne.yaml
      sources/               <- committable sources (Perseus TEI)
      build/                 <- pipeline output, gitignored
      pipeline/              <- this package
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from . import scheme as scheme_mod
from .refs import line_key

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = REPO_ROOT / "build"
SOURCES_DIR = REPO_ROOT / "sources"


class Manifest:
    def __init__(self, data: dict, path: Path):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: Path | None = None) -> "Manifest":
        path = path or REPO_ROOT / "manifests" / "EN.yaml"
        with open(path, encoding="utf-8") as f:
            return cls(yaml.safe_load(f), path)

    @classmethod
    def for_work(cls, work: str, public: bool = False) -> "Manifest":
        """Load the manifest for a work slug, e.g. 'EN' or 'DA'.

        Public builds use manifests/<work>-public.yaml when it exists, falling
        back to the normal manifest for works with no private translations.
        """
        manifests_dir = REPO_ROOT / "manifests"
        if public:
            public_path = manifests_dir / f"{work}-public.yaml"
            if public_path.exists():
                return cls.load(public_path)
        return cls.load(manifests_dir / f"{work}.yaml")

    @property
    def work_id(self) -> str:
        return self.data["work"]["id"]

    @property
    def author(self) -> str:
        """Author slug (e.g. 'aristotle', 'plato'), required by every manifest."""
        return self.data["work"]["author"]

    @property
    def language(self) -> str:
        """Work's source language: 'grc' (default) or 'lat'. Only 'grc' is
        actually wired up end-to-end today; 'lat' is accepted here so
        stage4/stage5 can parameterize on it, but Latin support itself is
        Wave 2 work (see stage4_morphology / stage5_lsj)."""
        return self.data["work"].get("language", "grc")

    @property
    def lexicon(self) -> bool:
        """Whether this work's tokens are keyed against a lexicon at all
        (Wave 2 §4.2's no-lexicon-first posture: a work may legitimately
        ship with tokens that carry `t` but no `k` — declared
        `work.lexicon: false`, first used by Cicero's De Officiis, Batch
        1a). Defaults to True: every pre-Wave-2 manifest has no `lexicon`
        key at all and must keep keying tokens exactly as before."""
        return bool(self.data["work"].get("lexicon", True))

    @property
    def first_column(self) -> str:
        span = self.data.get("bekker_range")
        if span:
            return span["first_column"]
        return self._boundary_column(self.books[0]["start"])

    @property
    def last_column(self) -> str:
        span = self.data.get("bekker_range")
        if span:
            return span["last_column"]
        return self._boundary_column(self.books[-1]["end"])

    def _boundary_column(self, token: str) -> str:
        """The bare column of a book-boundary token. A letter scheme strips the
        trailing editorial line ('357a1' -> '357a', '1094a2' -> '1094a'); a
        numeric-section scheme's dotted token ('1.1') has no line component and
        already IS the whole column, so stripping trailing digits would corrupt
        it to '1.' — return it unchanged. A flat-numeric scheme's bare-integer
        token ('53') is ALL digits, so the strip would corrupt it to '' —
        likewise return it unchanged. A dk column ('B30', 'B84a') ends in a
        DIGIT (or a letter suffix) that is part of the token itself, never an
        editorial line — stripping trailing digits would corrupt "B30" to "B"
        — likewise return it unchanged. A verse-line dotted token ('1.101',
        '3.47a') is the same shape as a dk column for this purpose (its
        lineref is the whole column, not an editorial line to strip)."""
        sch = scheme_mod.for_manifest(self)
        if sch.numeric_section or sch.flat_numeric or sch.fragment_scheme or sch.verse_line_scheme:
            return token
        return token.rstrip("0123456789")

    @property
    def books(self) -> list[dict]:
        return self.data["books"]

    def tlg_dir(self) -> Path:
        src = self.data["sources"]
        env = os.environ.get(src["tlg_dir_env"])
        if env:
            return Path(env)
        return (REPO_ROOT / src["tlg_dir_default"]).resolve()

    def phi_dir(self) -> Path:
        """PHI (Latin) corpus location, mirroring `tlg_dir()` exactly: an
        env var override (`sources.phi_dir_env`, e.g. "PHI_DIR") wins, else
        a manifest-declared default path relative to REPO_ROOT
        (`sources.phi_dir_default`) — see docs/tlg-phi-export.md's Wave 2
        PHI section (EMPIRICAL UPDATE 2026-07-17: the `phi_dir`-keyed
        Diogenes prefs line is what's actually load-bearing for the export
        itself, written by stage1_latin.run_export; this accessor is what
        supplies that value from the manifest/env, exactly as `tlg_dir()`
        supplies the TLG line)."""
        src = self.data["sources"]
        env = os.environ.get(src["phi_dir_env"])
        if env:
            return Path(env)
        return (REPO_ROOT / src["phi_dir_default"]).resolve()

    def diogenes_server(self) -> Path:
        return Path(self.data["sources"]["diogenes_server"])

    def diogenes_data(self) -> Path:
        return Path(self.data["sources"]["diogenes_data"])

    def perseus_eng(self) -> Path:
        # Vendored Perseus eng TEI for this work: an explicit work.english_source
        # name, else derived from the TLG work number. Falls back to the legacy
        # sources.perseus_eng path (NE-only download location).
        name = self.data["work"].get("english_source")
        if not name:
            name = f"tlg0086.tlg{self.data['work']['tlg_work']}.perseus-eng2.xml"
        vendored = SOURCES_DIR / name
        if vendored.exists():
            return vendored
        legacy = (self.data.get("sources") or {}).get("perseus_eng")
        return Path(legacy) if legacy else vendored

    def book_for_line(self, column: str, line: int) -> int | None:
        """Book number containing Bekker position (column, line), or None
        if the position falls in an inter-book numbering gap."""
        pos = line_key(column, line)
        for b in self.books:
            m_start = _ref_to_key(b["start"])
            m_end = _ref_to_key(b["end"])
            if m_start <= pos <= m_end:
                return b["n"]
        return None

    def lettered_fragments_for_book(self, book_n: str | int) -> dict | None:
        """Manifest-declared lettered-fragment remap table for one book
        (citation.lettered_fragments — see manifests/lives.yaml and
        stage1_greek._resolve_lettered_fragments), or None if this book has
        no declaration. A list entry looks like:
            {book: 10, found: ["120a", "121b", "120b", "121a"],
             merge: {120: ["120a", "121b", "120b"], 121: ["121a"]}}

        Raises loudly if more than one entry declares the same book — a
        silent first-match would hide a manifest-authoring duplicate behind
        whichever entry happens to come first (Sol round-2 review, Hole 3).
        """
        matches = [
            entry
            for entry in (self.data.get("citation") or {}).get("lettered_fragments", [])
            if str(entry["book"]) == str(book_n)
        ]
        if len(matches) > 1:
            raise ValueError(
                f"{self.work_id}: {len(matches)} duplicate "
                f"citation.lettered_fragments declarations for book "
                f"{book_n!r} — each book may be declared at most once"
            )
        return matches[0] if matches else None

    def lettered_fragment_books(self) -> list[str]:
        """Every book_n declared in citation.lettered_fragments (as a
        string), in manifest order. Used by stage1_greek to check for stale
        declarations — a declared book whose encountered lettered-@n set
        turns out empty once the document is scanned."""
        return [
            str(entry["book"])
            for entry in (self.data.get("citation") or {}).get("lettered_fragments", [])
        ]

    def book_for_column(self, column: str) -> int | None:
        """Book number whose declared range contains a column token, compared
        at (page, letter) granularity, or None if it falls outside every book.

        For section schemes (stephanus): book boundaries fall page-initial on a
        section letter, so a whole section (page+letter column) belongs to one
        book and the editorial per-section line numbers are irrelevant to the
        assignment. Book start/end may be given as bare columns ('357a') or full
        refs ('357a1'); only the (page, letter) prefix is compared."""
        from .refs import column_prefix_key

        sch = scheme_mod.for_manifest(self)
        pos = column_prefix_key(column, sch)
        for b in self.books:
            if column_prefix_key(b["start"], sch) <= pos <= column_prefix_key(b["end"], sch):
                return b["n"]
        return None


def _ref_to_key(ref: str):
    from .refs import ref_key

    return ref_key(ref)
