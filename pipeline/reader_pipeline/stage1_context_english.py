"""Stage 1c: source-passage English for a DK context run (docs/source-
passage-english-scoping.md — Phase C's mechanism sketch, phase 1 of the
phased plan: Diogenes Laertius). DRAFT pending John's approval of the
reader-facing credit copy (see shared/components/Reader.svelte's
`.context-english` block and the strings quoted there).

A DK fragment/testimonia work MAY declare `sources/<work>/context-english.json`
-- a hand-authored, per-work sidecar keyed by SEGMENT id (the spine's own
"<book>:<column>" token, e.g. "1:A1"), one entry per column carrying a
`context_spans` list. Each span names the SOURCE author/work a `role:
"context"` Greek run quotes from (or is quoted BY), keyed at the
carried-forward-source-run granularity the census established (docs/
source-passage-english-scoping.md, Phase A) -- not per raw context line.

This is a LOCUS POINTER, never a pasted duplicate: a `status: "translated"`
span names a `source_author` this module knows how to resolve (Diogenes
Laertius -> the vendored Hicks Loeb store already used for the `lives`
work's own English -- see stage1_book_section_english.py and
sources/hicks-dl/hicks-lives.clean.json; Plato -> the Stephanus store;
Aristotle -> the Bekker-column store) plus a `locus` string resolved
against that store at BUILD TIME, so the emitted text can never drift from
the vendored JSON. A translated Aristotle span must also carry `emphasis`:
the build keeps only the sentences that hold those words and writes "…" at
each cut (docs/aristotle-context-english-design.md, B.4 as amended in H).
A `status: "desert"` span carries no text at all --
an honest "no PD English exists for this passage" state the reader renders
as its own notice, not a silent fallback.

A work with no context-english.json file at all is completely unaffected --
`run` returns None and stage7_emit attaches no `contextEnglish` key to any
segment (byte-identical output to before this module existed).

## Fatal gates (this module IS the preflight for this sidecar; there is no
separate DIST-level cross-check yet -- see docs/source-passage-english-
scoping.md's implementation section for why that is a phase-2 item)

- The declaration file must not be empty -- `{}` is fatal (an honest "no
  sidecar" state is the file not existing at all; a present-but-empty file
  reads as a truncated write and must not silently pass as "no coverage
  declared").
- The declaration's top-level keys must all match a real spine segment id
  (`f"{book}:{column}"`) -- an unknown column is fatal.
- Every span must carry `source_author`, `source_work`, `locus`, `status`
  (status must be "translated" or "desert") -- a missing/bad field is fatal.
- A "translated" span must carry a non-empty `translation_credit` and its
  `(source_author, source_work)` PAIR must be one this module has a
  resolver registered for -- registered by the exact pair, not by author
  alone, so a declaration that names the right author but the wrong work
  (e.g. "Diogenes Laertius" + "Metaphysics") can never resolve against the
  wrong store. The `locus` must full-match that resolver's syntax and then
  resolve against its store (a locus naming a section the store doesn't
  carry is fatal -- never a silent partial/empty result).
- A "desert" span must NOT carry `translation_credit` (nothing to credit).
- A span MAY carry `head`: the exact printed text of the citation heading it
  translates (a heading's `text`, e.g. "—22, 2 (D. 352)"), emitted as
  `headText`. The reader binds the span to that heading instead of matching
  by author and work in document order -- needed where a column has several
  headings from one source and English for only some of them. The text must
  occur in one of the column's Greek lines, or the build fails.

## Trimming to what DK quotes (owner rulings, 2026-09-27)

"Trim to what DK quotes": the English beside a source passage starts at the
sentence that translates DK's first quoted words and ends at the sentence
that translates DK's last. A translated span MAY carry `trim`, an object with
any of:

- `start`: exact English text the kept passage begins with;
- `end`: exact English text the kept passage ends with;
- `omit`: a list of `[from, to]` pairs, each dropping the stretch that begins
  with `from` and ends with `to` (a stretch DK leaves out in the middle).

Each anchor must occur exactly once in the English it applies to (0 or 2+ is
fatal), must not contain a blank line, and the anchors must come in order
(start, omits, end) with kept text on both sides of every omit. Each cut is
marked "…" exactly as the Aristotle sentence-keep marks its cuts: at the head
of the kept text, at its tail, and at the head of the text that resumes after
an omit. A paragraph left empty drops out with its section locus. For
Aristotle the anchors are found in the English after the emphasis
sentence-keep (trimming applies on top of it). Emphasis must survive the trim
(each bold substring still exactly once), or the build fails.

A span that offers alternate translations (Jowett) and carries `trim` must
also carry `alt_trims`: `{"<alt id>": <trim object> | "keep" | "drop"}` --
a trim object in the same shape, "keep" (checked; nothing to cut), or "drop"
(that translation does not render DK's words, so it is not offered). Naming an
alternate the span does not offer is fatal.

Jowett's store is aligned by speaker turn, so his rendering of DK's words can
sit under a neighbouring Stephanus key. A Plato span MAY carry `alt_loci`:
`{"jowett": "<locus>"}`, a Plato locus (single or range) that replaces the
span's own loci for Jowett only; every key it names must hold Jowett text, or
the build fails. The alternate is still labelled with the span's own locus and
trimmed by `alt_trims` like any other.

Where the Perseus TEI drops words the printed Loeb has, sources/perseus-plato/
corrections.json restores them when the Plato store loads (see
_apply_plato_corrections); a missing anchor is fatal.

Galen (On the Natural Faculties, Brock's Loeb, 1916) resolves "<book>.<chapter>"
against sources/brock-galen/, which holds only the chapters DK cites.

Aëtius (Placita, in Goodwin's revision of the pseudo-Plutarch translation "by
several hands", Plutarch's Morals vol. III, Boston 1874) resolves a Diels
"<book>.<chapter>" locus against sources/goodwin-placita/, which holds only
the chapters DK's matched passages need. The store keeps Goodwin's own chapter
numbers; they are Diels's except that Book V chapters 23 and 24 are swapped.

Plutarch's Moralia resolves a Stephanus locus ("929b", "683d-683f"), by the
essay title DK's head expansion gives, against sources/loeb-moralia/ (the
Loeb, 1927-1959) where a usable Loeb volume covers the essay, and against
sources/goodwin-morals/ (Goodwin's revision, Plutarch's Morals, Boston 1874)
for the rest; Plutarch's Lives (Perrin's Loeb, 1914-1920) resolve a chapter
locus ("16", "26-28") against sources/perrin-lives/. Each store holds only
the chapters the placed spans need.

Harpocration (Lexicon in Decem Oratores, the English of Harpokration On Line,
CC BY 4.0) resolves "s.v. <headword>" against sources/harpokration-online/,
which holds only the entries DK's matched passages need.

Section division: only Diogenes Laertius keeps one paragraph per section
(sectionLoci), because those sections match DK's own "(N)" markers. Plato and
Aristotle English is one continuous passage: a Stephanus or Bekker range is
joined with a space and emits no sectionLoci, and a Jowett alternate is one
section under the span's own locus (owner ruling, 2026-09-27).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import BUILD_DIR, SOURCES_DIR, Manifest


def _load_hicks() -> dict[str, str]:
    # SOURCES_DIR read at call time (not bound to a module-level constant at
    # import time) so tests can monkeypatch it, same posture as every other
    # stage1 module's SOURCES_DIR-relative lookups.
    path = SOURCES_DIR / "hicks-dl" / "hicks-lives.clean.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_plato() -> dict[str, str]:
    # Same call-time SOURCES_DIR read as _load_hicks -- see that function's
    # comment. One flat store shared by all 18 vendored dialogues (docs/
    # plato-locus-resolver-design.md SS2.4), keyed "<slug>:<page><letter>".
    path = SOURCES_DIR / "perseus-plato" / "plato-stephanus.clean.json"
    return _apply_plato_corrections(json.loads(path.read_text(encoding="utf-8")))


def _apply_plato_corrections(store: dict[str, str]) -> dict[str, str]:
    """Restores words the Perseus TEI drops, from the printed Loeb page:
    sources/perseus-plato/corrections.json, a list of {key, before, insert,
    source}. `insert` goes into store[key] just before `before`, which must
    occur there exactly once (fatal otherwise, as is a key the store lacks).
    No file, no corrections."""
    path = SOURCES_DIR / "perseus-plato" / "corrections.json"
    if not path.exists():
        return store
    for fix in json.loads(path.read_text(encoding="utf-8")):
        key, before = fix["key"], fix["before"]
        text = store.get(key)
        if text is None:
            raise ValueError(
                f"perseus-plato/corrections.json names {key!r}, which is not "
                f"in plato-stephanus.clean.json"
            )
        if text.count(before) != 1:
            raise ValueError(
                f"perseus-plato/corrections.json: anchor {before!r} occurs "
                f"{text.count(before)} times in {key!r} -- expected once"
            )
        at = text.index(before)
        store[key] = text[:at] + fix["insert"] + text[at:]
    return store


# Per-passage translation picker (REVIEW-CHECKLIST item 82): a second, ALT
# store of the same flat "<slug>:<page><letter>" shape, Jowett's public-
# domain 1892 translation, used only to offer the reader a second English
# rendering of a Plato quote alongside the primary (Fowler/Lamb/Bury) text
# already resolved above. This store is optional at the file-system level --
# unlike plato-stephanus.clean.json, whose absence is never tolerated once a
# span names Plato, a missing jowett-stephanus.clean.json simply means "no
# alts available yet" (it is generated by a separate, independent pipeline
# step) and is never fatal.
_JOWETT_CREDIT = "Benjamin Jowett, The Dialogues of Plato, 3rd ed., Oxford, 1892"


def _load_jowett() -> dict[str, str] | None:
    path = SOURCES_DIR / "jowett-plato" / "jowett-stephanus.clean.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# A locus must full-match this shape before any resolver sees it -- an
# inclusive int() conversion (Python tolerates leading '+'/whitespace) would
# otherwise let syntax like "1.+22-040" or "1.22- 40" slip through as if it
# were a well-formed "<book>.<section>"/"<book>.<start>-<end>" locus.
_LOCUS_RE = re.compile(r"^\d+\.\d+(?:-\d+)?$")


def _resolve_diogenes_laertius(locus: str) -> tuple[str, list[str] | None]:
    """`locus` is a Hicks-store key ("1.23") or an inclusive section RANGE
    within one book ("1.22-40") -- the shape a single carried-forward DL
    citation run takes when DK quotes several consecutive Loeb sections
    (see docs/source-passage-english-scoping.md's granularity note). A range
    concatenates each resolved section's Hicks text, in order, separated by
    a blank line (Hicks' own section boundaries read as paragraph breaks);
    any missing section is fatal, not silently skipped. Returns
    `(text, section_loci)`: `section_loci` is the ordered list of resolved
    Hicks keys, one per paragraph in `text`, for a range locus (so the
    reader can mark each paragraph with its own DL section number); `None`
    for a single-section locus (the span's own `locus` already names it)."""
    if not _LOCUS_RE.fullmatch(locus):
        raise ValueError(
            f"Diogenes Laertius locus {locus!r} is not valid -- expected "
            f"'<book>.<section>' or '<book>.<start>-<end>'"
        )
    hicks = _load_hicks()
    if "-" in locus:
        book_s, rng = locus.split(".", 1)
        start_s, end_s = rng.split("-", 1)
        start, end = int(start_s), int(end_s)  # _LOCUS_RE guarantees plain digits
        if end < start:
            raise ValueError(
                f"Diogenes Laertius locus {locus!r}: end section {end} is "
                f"before start section {start}"
            )
        parts = []
        keys = []
        for n in range(start, end + 1):
            key = f"{book_s}.{n}"
            if key not in hicks:
                raise ValueError(
                    f"Diogenes Laertius locus {locus!r} resolves to Hicks "
                    f"section {key!r}, which is not in "
                    f"sources/hicks-dl/hicks-lives.clean.json"
                )
            parts.append(hicks[key])
            keys.append(key)
        return "\n\n".join(parts), keys
    if locus not in hicks:
        raise ValueError(
            f"Diogenes Laertius locus {locus!r} is not a key in "
            f"sources/hicks-dl/hicks-lives.clean.json"
        )
    return hicks[locus], None


# A Plato locus is a single Stephanus "<page><letter>" token ("315c") or an
# inclusive range within one dialogue ("315c-315e") -- never a dialogue name
# (that lives in source_work, resolved by the registry pair below, not
# repeated in the locus) and never an open-ended "ff." (docs/plato-locus-
# resolver-design.md SS3(b): the hand-authoring human pins an explicit end;
# this regex has no way to match an unbounded range, so "ff." simply fails
# to full-match and is rejected like any other malformed locus).
_PLATO_LOCUS_RE = re.compile(r"^\d+[a-e](?:-\d+[a-e])?$")

# Dialogue title, as a context-english.json sidecar names it in source_work
# -> (plato-stephanus.clean.json store slug, translation credit). All 18
# dialogues DK's testimonia/fragments columns cite (docs/plato-locus-
# resolver-design.md SS1's census) -- deliberately not all 36 Platonic
# dialogues; vendoring a 19th later is a one-line table edit plus one file
# copy, per that memo's SS2.4.
_PLATO_DIALOGUES = {
    "Apology": ("apology", "Fowler, 1914"),
    "Charmides": ("charmides", "Lamb, 1927"),
    "Cratylus": ("cratylus", "Fowler, 1926"),
    "Euthydemus": ("euthydemus", "Lamb, 1924"),
    "Gorgias": ("gorgias", "Lamb, 1925"),
    "Hippias Major": ("hippias-major", "Fowler, 1926"),
    "Hippias Minor": ("hippias-minor", "Fowler, 1926"),
    "Laches": ("laches", "Lamb, 1924"),
    "Lysis": ("lysis", "Lamb, 1925"),
    "Meno": ("meno", "Lamb, 1924"),
    "Phaedo": ("phaedo", "Fowler, 1914"),
    "Phaedrus": ("phaedrus", "Fowler, 1914"),
    "Philebus": ("philebus", "Fowler, 1925"),
    "Protagoras": ("protagoras", "Lamb, 1924"),
    "Sophist": ("sophist", "Fowler, 1921"),
    "Symposium": ("symposium", "Lamb, 1925"),
    "Theaetetus": ("theaetetus", "Fowler, 1921"),
    "Timaeus": ("timaeus", "Bury, 1929"),
    # Vendored 2026-07-28 for wired-column candidates (Laws, Republic,
    # Parmenides) and Jowett turn-alignment coverage (Crito, Euthyphro, Ion)
    # -- see sources/perseus-plato/README.md for each dialogue's PD basis.
    "Crito": ("crito", "Fowler, 1914"),
    "Euthyphro": ("euthyphro", "Fowler, 1914"),
    "Ion": ("ion", "Lamb, 1925"),
    "Laws": ("laws", "Bury, 1926"),
    "Parmenides": ("parmenides", "Fowler, 1926"),
    # Republic's store covers the whole dialogue. Perseus's TEI is a 1935-37
    # printing of both Loeb volumes (vol. 1 possibly following Shorey's 1937
    # revision), so NEITHER volume is claimed PD-by-date; the whole text rests
    # on the project owner's explicit pre-1940 ruling, 2026-07-28. See
    # sources/perseus-plato/README.md for the exact wording.
    "Republic": ("republic", "Shorey, 1930-1937 (per owner's pre-1940 ruling, 2026-07-28)"),
}


def _resolve_plato(slug: str):
    """Returns a resolver closure for one dialogue's `slug`, matching
    `_resolve_diogenes_laertius`'s `(text, section_loci)` contract. A range
    expands by INDEX into the store's own key order for this dialogue, never
    by arithmetic on Stephanus numbers (docs/plato-locus-resolver-design.md
    SS5's range-expansion note) -- page letter-counts vary, so "does page
    316 have an 'e'?" is answered by the store, not computed."""

    def resolver(locus: str) -> tuple[str, list[str] | None]:
        if not _PLATO_LOCUS_RE.fullmatch(locus):
            raise ValueError(
                f"Plato locus {locus!r} is not valid -- expected "
                f"'<page><letter>' or '<page><letter>-<page><letter>' "
                f"(an open-ended 'ff.' is never accepted -- a human must "
                f"pin an explicit end)"
            )
        store = _load_plato()
        prefix = f"{slug}:"
        # Document order, not sorted order: preserved from the store JSON's
        # own key order (json.loads keeps insertion order), which IS the
        # dialogue's reading order -- the only order a range may expand by.
        keys = [k[len(prefix):] for k in store if k.startswith(prefix)]
        if "-" in locus:
            start, end = locus.split("-", 1)
            if start not in keys:
                raise ValueError(
                    f"Plato locus {locus!r} resolves to {slug}:{start}, "
                    f"which is not in "
                    f"sources/perseus-plato/plato-stephanus.clean.json"
                )
            if end not in keys:
                raise ValueError(
                    f"Plato locus {locus!r} resolves to {slug}:{end}, "
                    f"which is not in "
                    f"sources/perseus-plato/plato-stephanus.clean.json"
                )
            start_i, end_i = keys.index(start), keys.index(end)
            if end_i < start_i:
                raise ValueError(
                    f"Plato locus {locus!r}: end {end!r} comes before "
                    f"start {start!r} in {slug}'s store order"
                )
            span = keys[start_i : end_i + 1]
            parts = [store[f"{prefix}{k}"] for k in span]
            return "\n\n".join(parts), span
        if locus not in keys:
            raise ValueError(
                f"Plato locus {locus!r} is not a key in "
                f"sources/perseus-plato/plato-stephanus.clean.json for "
                f"{slug!r}"
            )
        return store[f"{prefix}{locus}"], None

    return resolver


def _load_aristotle() -> dict:
    # Same call-time SOURCES_DIR read as _load_hicks. One flat store, keyed
    # "<Abbr>:<book>:<column>", each value {"lines": [int, ...], "text": str}.
    # docs/aristotle-context-english-design.md section C.
    path = SOURCES_DIR / "aristotle-english" / "aristotle-english.clean.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_aristotle_alternates() -> dict:
    path = SOURCES_DIR / "aristotle-english" / "alternates.json"
    if not path.exists():
        raise ValueError("Aristotle alternates file is missing: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


# A Bekker locus names a column and a line, or a range with both ends written
# out in full. No abbreviated end ("983b6-33"), no spaces, no "ff.", no bare
# column. The work lives in source_work, not in the locus.
_ARISTOTLE_LOCUS_RE = re.compile(
    r"^(\d{1,4}[ab])(\d{1,2})(?:-(\d{1,4}[ab])(\d{1,2}))?$"
)


def _resolve_aristotle_alternate(span: dict) -> tuple[str, None]:
    """A span naming `translation` takes its English from a whole passage in
    alternates.json (hand-vendored, not Bekker-line-aligned), for a clause
    the default translation leaves out. Exactly one passage must contain the
    locus; the id's work and credit must match the span's."""
    locus = span["locus"]
    match = _ARISTOTLE_LOCUS_RE.fullmatch(locus)
    if match is None:
        raise ValueError(
            f"Aristotle locus {locus!r} is not valid -- expected "
            f"'<column><line>' or '<column><line>-<column><line>' "
            f"(no abbreviated end, no spaces, no 'ff.')"
        )
    alternates = _load_aristotle_alternates()
    translation = span["translation"]
    if translation not in alternates:
        raise ValueError(f"Aristotle translation {translation!r} is not in alternates.json")
    entry = alternates[translation]
    if entry["work"] != span["source_work"]:
        raise ValueError(
            f"Aristotle translation {translation!r} is for {entry['work']!r}, "
            f"not {span['source_work']!r}"
        )
    if span["translation_credit"] != entry["credit"]:
        raise ValueError(
            f"Aristotle translation {translation!r} credit does not match "
            f"{entry['credit']!r}"
        )

    def position(column: str, line: str) -> tuple[int, str, int]:
        return int(column[:-1]), column[-1], int(line)

    start = position(match.group(1), match.group(2))
    end = position(match.group(3), match.group(4)) if match.group(3) else start
    found = []
    for passage_locus, passage_text in entry["passages"].items():
        passage = _ARISTOTLE_LOCUS_RE.fullmatch(passage_locus)
        if passage is None:
            raise ValueError(f"Aristotle alternate passage {passage_locus!r} is not valid")
        passage_start = position(passage.group(1), passage.group(2))
        passage_end = (
            position(passage.group(3), passage.group(4))
            if passage.group(3) else passage_start
        )
        if passage_start <= start and end <= passage_end:
            found.append(passage_text)
    if len(found) != 1:
        raise ValueError(
            f"Aristotle locus {locus!r} is in {len(found)} passages "
            f"for translation {translation!r} -- expected one"
        )
    return found[0], None


# Closing quote or bracket that may sit on a sentence-ending . ? !
_SENTENCE_CLOSING = "\"'”’)]"
# A following opening quote, or a "(" opening a numbered point such as
# "(6) Again…", starts the next sentence (B.4 step 5).
_SENTENCE_OPENING = "\"“‘'("
# Abbreviations and a single capital initial ("W.") do not end a sentence.
_SENTENCE_ABBREV_RE = re.compile(r"(?i)(?:^|[^A-Za-z])(?:e\.g|i\.e|cf|viz)$")
_SENTENCE_INITIAL_RE = re.compile(r"(?:^|[^A-Za-z])[A-Z]$")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """[start, end) of each sentence. A sentence ends at . ? or ! plus any
    closing quote or bracket, when whitespace and then a capital or an
    opening quote follow. Not after e.g. / i.e. / cf. / viz. / a single
    capital initial. Semicolons do not end sentences. The whitespace between
    sentences is in neither span."""
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] in ".!?":
            k = i + 1
            while k < n and text[k] in _SENTENCE_CLOSING:
                k += 1
            if k < n and text[k].isspace():
                m = k
                while m < n and text[m].isspace():
                    m += 1
                if m < n and (text[m].isupper() or text[m] in _SENTENCE_OPENING):
                    before = text[:i]
                    if (
                        _SENTENCE_ABBREV_RE.search(before) is None
                        and _SENTENCE_INITIAL_RE.search(before) is None
                    ):
                        spans.append((start, k))
                        start = m
                        i = m
                        continue
        i += 1
    spans.append((start, n))
    return spans


def _span_containing(spans: list[tuple[int, int]], pos: int) -> tuple[int, int]:
    for start, end in spans:
        if start <= pos < end:
            return start, end
    for start, end in spans:
        if pos < start:
            return start, end
    return spans[-1]


def _trim_to_emphasis(
    text: str, emphasis: list[str], section_loci: list[str] | None
) -> tuple[str, list[str] | None]:
    """Keep the sentence holding the first bold run through the sentence
    holding the last. No extra sentence on either side. "…" at each cut.
    A paragraph left empty drops out, and so does its sectionLoci entry.
    One remaining paragraph emits no sectionLoci."""
    spans = _sentence_spans(text)
    first = text.index(emphasis[0])
    last_end = text.index(emphasis[-1]) + len(emphasis[-1])
    keep_start, _ = _span_containing(spans, first)
    _, keep_end = _span_containing(spans, last_end - 1)
    paragraphs: list[tuple[int, int]] = []
    pos = 0
    parts = text.split("\n\n")
    for idx, part in enumerate(parts):
        paragraphs.append((pos, pos + len(part)))
        pos += len(part)
        if idx != len(parts) - 1:
            pos += 2
    kept: list[str] = []
    kept_loci: list[str] = []
    for idx, (p0, p1) in enumerate(paragraphs):
        lo = p0 if p0 > keep_start else keep_start
        hi = p1 if p1 < keep_end else keep_end
        if lo >= hi:
            continue
        piece = text[lo:hi]
        if not piece.strip():
            continue
        kept.append(piece)
        if section_loci is not None:
            kept_loci.append(section_loci[idx])
    if not kept:
        raise ValueError("emphasis trim left no text")
    if text[:keep_start].strip():
        kept[0] = "…" + kept[0]
    if text[keep_end:].strip():
        kept[-1] = kept[-1] + "…"
    trimmed = "\n\n".join(kept)
    if len(kept) == 1:
        return trimmed, None
    return trimmed, kept_loci


def _resolve_aristotle(abbr: str):
    """Resolver for one work's store abbreviation. Same (text, section_loci)
    contract as _resolve_plato. A range expands by store order, then by
    position in `lines` -- never by arithmetic on Bekker numbers, which is
    wrong for a column split across a book and for the 1029b transposition.
    Returns the columns the locus touches plus one neighbouring segment on
    each side (empty neighbours skipped). section_loci are column tokens
    ("983b"), never line loci."""

    def _column(key: str) -> str:
        return key.rsplit(":", 1)[1]

    def resolver(locus: str) -> tuple[str, list[str] | None]:
        match = _ARISTOTLE_LOCUS_RE.fullmatch(locus)
        if match is None:
            raise ValueError(
                f"Aristotle locus {locus!r} is not valid -- expected "
                f"'<column><line>' or '<column><line>-<column><line>' "
                f"(no abbreviated end, no spaces, no 'ff.')"
            )
        start_col = match.group(1)
        start_line = int(match.group(2))
        end_col = match.group(3)
        end_line = int(match.group(4)) if match.group(4) is not None else None
        store = _load_aristotle()
        prefix = abbr + ":"
        items = [(k, store[k]) for k in store if k.startswith(prefix)]

        def find(col: str, line: int) -> int:
            found = None
            saw_column = False
            for idx, (key, entry) in enumerate(items):
                if _column(key) != col:
                    continue
                saw_column = True
                lines = entry["lines"]
                if line in lines:
                    if found is not None:
                        raise ValueError(
                            f"Aristotle locus {locus!r}: line {line} is in "
                            f"more than one {col} segment"
                        )
                    found = idx
            if found is not None:
                return found
            if not saw_column:
                raise ValueError(
                    f"Aristotle locus {locus!r}: column {col!r} is not in "
                    f"the store"
                )
            raise ValueError(
                f"Aristotle locus {locus!r}: line {line} is not in column {col!r}"
            )

        start_i = find(start_col, start_line)
        if end_col is None:
            end_i = start_i
            end_line_here = start_line
        else:
            end_i = find(end_col, end_line)
            end_line_here = end_line
        if end_i < start_i or (
            end_i == start_i
            and items[start_i][1]["lines"].index(end_line_here)
            < items[start_i][1]["lines"].index(start_line)
        ):
            raise ValueError(
                f"Aristotle locus {locus!r}: end comes before start in "
                f"store order"
            )
        span_n = end_i - start_i + 1
        if span_n > 3:
            raise ValueError(
                f"Aristotle locus {locus!r}: range spans {span_n} segments, "
                f"more than 3"
            )
        for idx in range(start_i, end_i + 1):
            if not str(items[idx][1].get("text", "")).strip():
                raise ValueError(
                    f"Aristotle locus {locus!r}: empty English in "
                    f"{items[idx][0]} inside the range"
                )
        lo = start_i
        hi = end_i
        if lo > 0 and str(items[lo - 1][1].get("text", "")).strip():
            lo -= 1
        if hi + 1 < len(items) and str(items[hi + 1][1].get("text", "")).strip():
            hi += 1
        chosen = items[lo : hi + 1]
        parts = [entry["text"] for _, entry in chosen]
        if len(parts) == 1:
            return parts[0], None
        cols = [_column(key) for key, _ in chosen]
        return "\n\n".join(parts), cols

    return resolver


# Site title -> (store abbr, credit). Credit strings are the owner's
# 2026-09-25 table. Pair-keyed, like Plato: ("Aristotle", "Problemata")
# has no entry.
_ARISTOTLE_WORKS = {
    "Metaphysics": ("Meta", "Ross, 1928"),
    "Physics": ("Phys", "Hardie and Gaye, 1930"),
    "On Generation and Corruption": ("GC", "Joachim, 1922"),
    "On the Heavens": ("Cael", "Stocks, 1922"),
    "Meteorology": ("Mete", "Webster, 1923"),
    "Rhetoric": ("Rhet", "Freese, 1926"),
    "Generation of Animals": ("GA", "Platt, 1910"),
    "Parts of Animals": ("PA", "Ogle, 1912"),
    "Sense and Sensibilia": ("Sens", "Beare, 1908"),
    "Nicomachean Ethics": ("EN", "Rackham, 1926"),
    "On Youth, Old Age, Life and Death, and Respiration": ("Juv", "G. R. T. Ross, 1908"),
    "Sophistical Refutations": ("SE", "Pickard-Cambridge, 1928"),
    "History of Animals": ("HA", "Thompson, 1910"),
    "Topics": ("Top", "Pickard-Cambridge, 1928"),
    "Politics": ("Pol", "Jowett, 1885"),
    "De Mirabilibus Auscultationibus": ("Mirab", "Dowdall, 1909"),
    "De Lineis Insecabilibus": ("Lin", "Joachim, 1908"),
    "De Anima": ("DA", "Smith, 1931"),
    "Poetics": ("Poet", "Fyfe, 1932"),
}

# DK treats these three as doubtful. The same resolver, store, and credit
# are also registered under "pseudo-Aristotle" (owner ruling H.3). No other
# work gets that author.
_PSEUDO_ARISTOTLE_TITLES = (
    "De Mirabilibus Auscultationibus",
    "De Lineis Insecabilibus",
    "History of Animals",
)
# These works have no store and take English only from alternates.json.
_ALTERNATES_ONLY_PSEUDO_ARISTOTLE_TITLES = ("Problemata",)


def _resolve_alternates_only(title: str):
    def resolver(_locus: str) -> tuple[str, None]:
        raise ValueError(
            f"{title} has no stored translation -- the span must name a "
            f"'translation' from alternates.json"
        )

    return resolver

# Trim applies only to these pairs, so Diogenes Laertius and Plato output
# stays byte-identical (docs/aristotle-context-english-design.md H.1).
_TRIM_TO_EMPHASIS = {("Aristotle", title) for title in _ARISTOTLE_WORKS}
_TRIM_TO_EMPHASIS.update(
    ("pseudo-Aristotle", title) for title in _PSEUDO_ARISTOTLE_TITLES
)
_TRIM_TO_EMPHASIS.update(
    ("pseudo-Aristotle", title)
    for title in _ALTERNATES_ONLY_PSEUDO_ARISTOTLE_TITLES
)


# (source_author, source_work) -> resolver, phase 1 (DL) + phase 2 (Plato) --
# docs/source-passage-english-scoping.md's phased plan item 1, and docs/
# plato-locus-resolver-design.md. Registered by the exact PAIR, not by
# author alone: a "translated" span naming an author this module knows but a
# work it doesn't (or a pair it has never seen) is fatal (see
# `_resolve_span`) -- never resolved against the wrong author's store.
# Later phases add their own entries here as their own mechanism work
# lands, never a fallback.
_RESOLVERS = {
    ("Diogenes Laertius", "Lives of Eminent Philosophers"): _resolve_diogenes_laertius,
    **{
        ("Plato", title): _resolve_plato(slug)
        for title, (slug, _credit) in _PLATO_DIALOGUES.items()
    },
}
_RESOLVERS.update({
    ("Aristotle", title): _resolve_aristotle(abbr)
    for title, (abbr, _credit) in _ARISTOTLE_WORKS.items()
})
_RESOLVERS.update({
    ("pseudo-Aristotle", title): _RESOLVERS[("Aristotle", title)]
    for title in _PSEUDO_ARISTOTLE_TITLES
})
_RESOLVERS.update({
    ("pseudo-Aristotle", title): _resolve_alternates_only(title)
    for title in _ALTERNATES_ONLY_PSEUDO_ARISTOTLE_TITLES
})


def _resolve_galen(locus: str) -> tuple[str, None]:
    """Galen, On the Natural Faculties, in Brock's Loeb translation (1916):
    sources/brock-galen/brock-natural-faculties.clean.json, keyed
    "<book>.<chapter>" ("2.8"). Only the chapters DK cites are vendored; a
    chapter holds Brock's paragraphs separated by blank lines, so a span
    trims it to DK's words. One chapter per locus, no ranges."""
    if not re.fullmatch(r"\d+\.\d+", locus):
        raise ValueError(
            f"Galen locus {locus!r} is not valid -- expected '<book>.<chapter>'"
        )
    path = SOURCES_DIR / "brock-galen" / "brock-natural-faculties.clean.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    if locus not in store:
        raise ValueError(
            f"Galen locus {locus!r} is not a key in "
            f"sources/brock-galen/brock-natural-faculties.clean.json"
        )
    return store[locus], None


_RESOLVERS[("Galen", "On the Natural Faculties")] = _resolve_galen

# Goodwin prints Diels's Book V chapters 23 (Heraclitus and the Stoics on
# maturity) and 24 (sleep and death) in the reverse order. A span's locus is
# always Diels's (DK's heads cite Diels); the store is keyed by Goodwin's.
_GOODWIN_CHAPTER = {"5.23": "5.24", "5.24": "5.23"}


def _resolve_aetius(locus: str) -> tuple[str, None]:
    """Aëtius, Placita (pseudo-Plutarch's epitome), in Goodwin's 1874 English:
    sources/goodwin-placita/goodwin-placita.clean.json, keyed
    "<book>.<chapter>" in Goodwin's numbering. `locus` is Diels's
    "<book>.<chapter>" ("2.21"); only V 23 and V 24 differ (see
    _GOODWIN_CHAPTER). A chapter holds Goodwin's paragraphs separated by
    blank lines, so a span trims it to DK's words. One chapter per locus."""
    if not re.fullmatch(r"\d+\.\d+", locus):
        raise ValueError(
            f"Aëtius locus {locus!r} is not valid -- expected '<book>.<chapter>'"
        )
    key = _GOODWIN_CHAPTER.get(locus, locus)
    path = SOURCES_DIR / "goodwin-placita" / "goodwin-placita.clean.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    if key not in store:
        raise ValueError(
            f"Aëtius locus {locus!r} (Goodwin's chapter {key!r}) is not a key "
            f"in sources/goodwin-placita/goodwin-placita.clean.json"
        )
    return store[key], None


_RESOLVERS[("Aëtius", "Placita")] = _resolve_aetius

# Plutarch's Moralia in Goodwin's revision of the translation "by several
# hands" (Plutarch's Morals, 5 vols, Boston 1874): the essays DK quotes, by
# the title DK's head expansion gives them. Only the chapters the placed spans
# need are vendored. Each chapter carries the Stephanus range it covers
# (sources/goodwin-morals/README.md says how the ranges were found).
_GOODWIN_MORALIA = (
    "Adversus Colotem", "Amatorius", "An Seni Respublica Gerenda Sit",
    "Animine an Corporis Affectiones Sint Peiores", "Coniugalia Praecepta",
    "Consolatio ad Apollonium", "De Adulatore et Amico", "De Amore Prolis",
    "De Animae Procreatione in Timaeo", "De Cohibenda Ira",
    "De Communibus Notitiis adversus Stoicos", "De Curiositate",
    "De Defectu Oraculorum", "De E apud Delphos", "De Esu Carnium", "De Exilio",
    "De Facie in Orbe Lunae", "De Fortuna", "De Garrulitate", "De Genio Socratis",
    "De Gloria Atheniensium", "De Iside et Osiride", "De Liberis Educandis",
    "De Primo Frigido", "De Profectibus in Virtute", "De Pythiae Oraculis",
    "De Recta Ratione Audiendi", "De Sollertia Animalium", "De Superstitione",
    "De Tranquillitate Animi", "De Tuenda Sanitate Praecepta",
    "De Virtute Morali", "De Vitioso Pudore", "Praecepta Gerendae Reipublicae",
    "Quaestiones Convivales", "Quaestiones Naturales", "Quaestiones Platonicae",
    "Quomodo Adulescens Poetas Audire Debeat",
    "Regum et Imperatorum Apophthegmata", "Septem Sapientium Convivium",
)
# DK prints these under "[PLUT.]": the head expansion's author is
# "pseudo-Plutarch".
_GOODWIN_PSEUDO_MORALIA = ("Vitae Decem Oratorum",)

_STEPHANUS_RE = re.compile(r"(\d{1,4})([a-f])")
_STEPHANUS_LOCUS_RE = re.compile(r"(\d{1,4}[a-f])(?:-(\d{1,4}[a-f]))?")


def _stephanus_key(ref: str) -> tuple[int, str]:
    m = _STEPHANUS_RE.fullmatch(ref)
    return int(m.group(1)), m.group(2)


def _resolve_moralia(store: str, title: str):
    """Plutarch, `title`, from the Moralia store sources/<store>/<store>.
    clean.json (goodwin-morals or loeb-moralia), `{essay: {chapter: {"steph",
    "text"}}}`. `locus` is a Stephanus page and letter ("929b") or a range of
    them ("683d-683f"); the resolved text is every vendored chapter whose
    Stephanus range meets the locus, in order, separated by blank lines, so
    a span trims it to DK's words. A locus that meets no vendored chapter is
    fatal."""
    where = f"sources/{store}/{store}.clean.json"

    def resolve(locus: str) -> tuple[str, None]:
        m = _STEPHANUS_LOCUS_RE.fullmatch(locus)
        if not m:
            raise ValueError(
                f"Plutarch locus {locus!r} is not valid -- expected a Stephanus "
                f"page and letter ('929b') or a range ('683d-683f')"
            )
        lo = _stephanus_key(m.group(1))
        hi = _stephanus_key(m.group(2)) if m.group(2) else lo
        if hi < lo:
            raise ValueError(f"Plutarch locus {locus!r} runs backwards")
        path = SOURCES_DIR / store / f"{store}.clean.json"
        chapters = json.loads(path.read_text(encoding="utf-8")).get(title)
        if not chapters:
            raise ValueError(f"Plutarch work {title!r} is not in {where}")
        texts = []
        for chapter in chapters.values():
            first, last = (_stephanus_key(r) for r in chapter["steph"].split("-"))
            if first <= hi and last >= lo:
                texts.append(chapter["text"])
        if not texts:
            raise ValueError(
                f"Plutarch locus {locus!r} meets no chapter of {title!r} in {where}"
            )
        return "\n\n".join(texts), None
    return resolve


# The Loeb Moralia (1927-1959), where a usable volume covers the essay:
# vols. I-II by date, III-VII, X and XII on no renewal found (owner ruling,
# 2026-09-29, review item 118). Its English replaces Goodwin's for these
# essays; Goodwin's chapters of them stay in his store, unread. Each Loeb
# chapter carries the Stephanus range of the same chapter in Goodwin's store
# (sources/loeb-moralia/README.md).
_LOEB_MORALIA = (
    "An Seni Respublica Gerenda Sit",
    "Animine an Corporis Affectiones Sint Peiores", "Coniugalia Praecepta",
    "Consolatio ad Apollonium", "De Adulatore et Amico", "De Amore Prolis",
    "De Cohibenda Ira", "De Curiositate", "De Defectu Oraculorum",
    "De E apud Delphos", "De Esu Carnium", "De Exilio", "De Facie in Orbe Lunae",
    "De Fortuna", "De Garrulitate", "De Genio Socratis", "De Gloria Atheniensium",
    "De Iside et Osiride", "De Liberis Educandis", "De Primo Frigido",
    "De Profectibus in Virtute", "De Pythiae Oraculis", "De Recta Ratione Audiendi",
    "De Sollertia Animalium", "De Superstitione", "De Tranquillitate Animi",
    "De Tuenda Sanitate Praecepta", "De Virtute Morali", "De Vitioso Pudore",
    "Praecepta Gerendae Reipublicae", "Quomodo Adulescens Poetas Audire Debeat",
    "Regum et Imperatorum Apophthegmata", "Septem Sapientium Convivium",
)
_LOEB_PSEUDO_MORALIA = ("Vitae Decem Oratorum",)

_RESOLVERS.update({
    (author, title): _resolve_moralia(
        "loeb-moralia" if title in loeb else "goodwin-morals", title
    )
    for author, titles, loeb in (
        ("Plutarch", _GOODWIN_MORALIA, _LOEB_MORALIA),
        ("pseudo-Plutarch", _GOODWIN_PSEUDO_MORALIA, _LOEB_PSEUDO_MORALIA),
    )
    for title in titles
})

# Plutarch's Lives in Bernadotte Perrin's Loeb translation (1914-1920), by
# the Latin title DK's head expansion gives them. The credit year is the
# volume's (sources/perrin-lives/README.md).
_PERRIN_LIVES = (
    "Alcibiades", "Antonius", "Camillus", "Cimon", "Coriolanus", "Lycurgus",
    "Lysander", "Nicias", "Numa", "Pericles", "Solon",
)


def _resolve_perrin_life(title: str):
    """Plutarch, Life of `title`, in Perrin's Loeb: sources/perrin-lives/
    perrin-lives.clean.json, `{life: {chapter: text}}`. `locus` is a chapter
    ("16") or a range of chapters ("26-28"); every chapter in it must be
    vendored (fatal otherwise). Chapters are separated by blank lines."""
    def resolve(locus: str) -> tuple[str, None]:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", locus)
        if not m:
            raise ValueError(
                f"Plutarch locus {locus!r} is not valid -- expected a chapter "
                f"('16') or a range of chapters ('26-28')"
            )
        first = int(m.group(1))
        last = int(m.group(2)) if m.group(2) else first
        if last < first:
            raise ValueError(f"Plutarch locus {locus!r} runs backwards")
        path = SOURCES_DIR / "perrin-lives" / "perrin-lives.clean.json"
        chapters = json.loads(path.read_text(encoding="utf-8")).get(title, {})
        missing = [str(c) for c in range(first, last + 1) if str(c) not in chapters]
        if missing:
            raise ValueError(
                f"Plutarch locus {locus!r}: {title} chapter(s) {missing} not in "
                f"sources/perrin-lives/perrin-lives.clean.json"
            )
        return "\n\n".join(chapters[str(c)] for c in range(first, last + 1)), None
    return resolve


_RESOLVERS.update({
    ("Plutarch", title): _resolve_perrin_life(title) for title in _PERRIN_LIVES
})

_HARPOCRATION_LOCUS_RE = re.compile(r"^s\.v\. (\S(?:.*\S)?)$")


def _resolve_harpocration(locus: str) -> tuple[str, None]:
    """Harpocration, Lexicon in Decem Oratores, in the English of Harpokration
    On Line (CC BY 4.0): sources/harpokration-online/harpokration-online.clean.json.
    `locus` is "s.v. <headword>" in DK's spelling; `entries` is keyed by the
    headword as HOL spells it, and `dk_spellings` maps a DK spelling that
    differs to HOL's. Only the entries DK's matched passages need are
    vendored; a span trims an entry to DK's words."""
    match = _HARPOCRATION_LOCUS_RE.fullmatch(locus)
    if match is None:
        raise ValueError(
            f"Harpocration locus {locus!r} is not valid -- expected "
            f"'s.v. <headword>'"
        )
    path = SOURCES_DIR / "harpokration-online" / "harpokration-online.clean.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    headword = match.group(1)
    key = store["dk_spellings"].get(headword, headword)
    if key not in store["entries"]:
        raise ValueError(
            f"Harpocration locus {locus!r} is not an entry in "
            f"sources/harpokration-online/harpokration-online.clean.json"
        )
    return store["entries"][key], None


_RESOLVERS[("Harpocration", "Lexicon in Decem Oratores")] = _resolve_harpocration


def _jowett_alts(
    source_author: str,
    source_work: str,
    locus: str,
    section_loci: list[str] | None,
    alt_locus: str | None = None,
) -> dict | None:
    """Builds the `alts` entry for Jowett's translation of a Plato span, or
    `None` when there is nothing to offer -- no Jowett store on disk (not
    generated yet), an unregistered dialogue, or a store with no entry for
    any of this span's loci. `section_loci` is the span's per-locus list (a
    range); a single-locus span passes `None` and this function falls back
    to `[locus]`. The texts found are joined with a space into ONE section
    under the span's own locus: Plato English carries no Stephanus division
    (owner ruling, 2026-09-27). Loci with no Jowett text add nothing (the
    store is turn-aligned, so a long speech sits under its first locus).

    `alt_locus` (the span's `alt_loci["jowett"]`) replaces the span's loci
    for Jowett only: his store is aligned by speaker turn, so his rendering
    of DK's words can sit under a neighbouring Stephanus key. It is a Plato
    locus, expanded by the Perseus store's order like the span's own, and
    every key it names must carry Jowett text (fatal otherwise)."""
    if source_author != "Plato":
        return None
    dialogue = _PLATO_DIALOGUES.get(source_work)
    if dialogue is None:
        return None
    slug, _credit = dialogue
    jowett = _load_jowett()
    if alt_locus is not None:
        if jowett is None:
            raise ValueError(
                f"alt_loci names Jowett locus {alt_locus!r}, but "
                f"sources/jowett-plato/jowett-stephanus.clean.json is missing"
            )
        _text, keys = _resolve_plato(slug)(alt_locus)
        keys = keys or [alt_locus]
        missing = [
            k for k in keys
            if not (isinstance(jowett.get(f"{slug}:{k}"), str)
                    and jowett[f"{slug}:{k}"].strip())
        ]
        if missing:
            raise ValueError(
                f"alt_loci Jowett locus {alt_locus!r}: no Jowett text for "
                f"{slug}:{', '.join(missing)}"
            )
        texts = [jowett[f"{slug}:{k}"] for k in keys]
    else:
        if jowett is None:
            return None
        loci = section_loci if section_loci else [locus]
        texts = []
        for loc in loci:
            value = jowett.get(f"{slug}:{loc}")
            if isinstance(value, str) and value.strip():
                texts.append(value)
    if not texts:
        return None
    return {
        "id": "jowett",
        "label": "Jowett",
        "translationCredit": _JOWETT_CREDIT,
        "sections": [{"locus": locus, "text": " ".join(texts)}],
    }


# Only these sources keep one paragraph per section: Diogenes Laertius's
# sections match DK's own "(N)" markers. Every other source's range is one
# continuous passage (owner ruling, 2026-09-27).
_SECTIONED_PAIRS = {("Diogenes Laertius", "Lives of Eminent Philosophers")}

_TRIM_KEYS = ("start", "end", "omit")


def _find_anchor(text: str, anchor, what: str) -> int:
    if not isinstance(anchor, str) or not anchor.strip():
        raise ValueError(f"trim {what} must be a non-empty string")
    if "\n\n" in anchor:
        raise ValueError(
            f"trim {what} {anchor!r} contains a blank line (crosses a paragraph)"
        )
    count = text.count(anchor)
    if count == 0:
        raise ValueError(
            f"trim {what} {anchor!r} does not occur in the resolved English "
            f"text -- authoring drift against the store"
        )
    if count > 1:
        raise ValueError(
            f"trim {what} {anchor!r} occurs {count} times in the resolved "
            f"English text -- ambiguous anchor"
        )
    return text.index(anchor)


def _apply_trim(
    text: str, section_loci: list[str] | None, trim
) -> tuple[str, list[str] | None]:
    """Keeps `text` from the `start` anchor to the end of the `end` anchor,
    less each `omit` stretch, writing "…" at every cut (see the module
    docstring). Paragraphs ("\\n\\n") left empty drop out, and so do their
    `section_loci` entries. Returns the kept loci in full (the caller decides
    whether one paragraph still carries sectionLoci)."""
    if not isinstance(trim, dict) or not trim:
        raise ValueError("trim must be a non-empty object")
    unknown = sorted(set(trim) - set(_TRIM_KEYS))
    if unknown:
        raise ValueError(f"trim has unknown key(s) {unknown}")
    start = _find_anchor(text, trim["start"], "start") if "start" in trim else 0
    if "end" in trim:
        end = _find_anchor(text, trim["end"], "end") + len(trim["end"])
    else:
        end = len(text)
    if end <= start:
        raise ValueError("trim end comes before trim start")
    omit = trim.get("omit", [])
    if not isinstance(omit, list) or ("omit" in trim and not omit):
        raise ValueError("trim omit must be a non-empty list of [from, to] pairs")
    cuts = []
    for pair in omit:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"trim omit entry {pair!r} must be a [from, to] pair")
        lo = _find_anchor(text, pair[0], "omit from")
        to_at = _find_anchor(text, pair[1], "omit to")
        if to_at < lo:
            raise ValueError(f"trim omit {pair!r}: 'to' comes before 'from'")
        hi = to_at + len(pair[1])
        if not text[start:lo].strip() or not text[hi:end].strip():
            raise ValueError(
                f"trim omit {pair!r} must leave kept text on both sides "
                f"(use start/end to cut at the edges)"
            )
        cuts.append((lo, hi))
    cuts.sort()
    for (_, hi1), (lo2, _) in zip(cuts, cuts[1:]):
        if lo2 < hi1:
            raise ValueError("trim omit stretches overlap")
    # Kept intervals, each flagged when a cut precedes it.
    intervals = []
    pos, mark = start, bool(text[:start].strip())
    for lo, hi in cuts:
        intervals.append([pos, lo, mark])
        pos, mark = hi, True
    intervals.append([pos, end, mark])
    paragraphs: list[tuple[int, int]] = []
    p = 0
    for part in text.split("\n\n"):
        paragraphs.append((p, p + len(part)))
        p += len(part) + 2
    kept: list[str] = []
    kept_loci: list[str] = []
    for idx, (p0, p1) in enumerate(paragraphs):
        pieces = []
        for interval in intervals:
            a, b, pending = interval
            piece = text[max(a, p0):min(b, p1)].strip()
            if not piece:
                continue
            if pending:
                piece = "…" + piece
                interval[2] = False
            pieces.append(piece)
        if pieces:
            kept.append(" ".join(pieces))
            if section_loci is not None:
                kept_loci.append(section_loci[idx])
    if not kept:
        raise ValueError("trim left no text")
    if text[end:].strip():
        kept[-1] = kept[-1] + "…"
    return "\n\n".join(kept), (kept_loci if section_loci is not None else None)


def _trim_alts(span: dict, alts: list[dict]) -> list[dict]:
    """Applies the span's `alt_trims` to its alternate translations (each one
    section of text). A trimmed span must say what happens to every
    alternate it offers."""
    offered = [alt["id"] for alt in alts]
    alt_trims = span.get("alt_trims")
    if alt_trims is None:
        if "trim" in span and offered:
            raise ValueError(
                f"span is trimmed but has no alt_trims for its alternate "
                f"translation(s) {offered} -- every translation offered must "
                f"be trimmed (or marked 'keep' or 'drop')"
            )
        return alts
    if not isinstance(alt_trims, dict) or not alt_trims:
        raise ValueError("alt_trims must be a non-empty object")
    unknown = sorted(set(alt_trims) - set(offered))
    if unknown:
        raise ValueError(
            f"alt_trims names {unknown}, which this span does not offer"
        )
    if "trim" in span:
        missing = [a for a in offered if a not in alt_trims]
        if missing:
            raise ValueError(f"span is trimmed but alt_trims omits {missing}")
    out = []
    for alt in alts:
        rule = alt_trims.get(alt["id"], "keep")
        if rule == "drop":
            continue
        if rule == "keep":
            out.append(alt)
            continue
        if not isinstance(rule, dict):
            raise ValueError(
                f"alt_trims[{alt['id']!r}] must be a trim object, 'keep' or 'drop'"
            )
        (section,) = alt["sections"]
        try:
            text, _ = _apply_trim(section["text"], None, rule)
        except ValueError as exc:
            raise ValueError(f"alt_trims[{alt['id']!r}]: {exc}") from exc
        out.append({**alt, "sections": [{"locus": section["locus"], "text": text}]})
    return out


_REQUIRED_SPAN_FIELDS = ("source_author", "source_work", "locus", "status")


def _validate_emphasis(
    manifest: Manifest, seg_id: str, emphasis: list, text: str
) -> list[str]:
    """Validates a `translated` span's hand-authored `emphasis` list (REVIEW-
    CHECKLIST item 83: source-passage excerpt emphasis) against `text`, the
    already-resolved primary English -- the bold ranges an editor marks as
    the words that actually translate the DK Greek excerpt, distinct from
    the surrounding Stephanus/Hicks context that is not bolded. Each
    substring must occur EXACTLY ONCE in `text` (0 = authoring drift against
    the store, fatal; 2+ = ambiguous anchor, fatal), the substrings must not
    overlap, and they must appear in the same order as `emphasis` declares
    them. Validation runs only against the PRIMARY text -- independent of
    `alts`, which this function never sees."""
    if not isinstance(emphasis, list) or not emphasis:
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] emphasis "
            f"must be a non-empty list of strings"
        )
    occurrences = []
    for sub in emphasis:
        if not isinstance(sub, str) or not sub.strip():
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"emphasis entry {sub!r} must be a non-empty string"
            )
        # A blank line inside one emphasis string crosses a paragraph.
        if "\n\n" in sub:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"emphasis substring contains a blank line "
                f"(crosses a paragraph)"
            )
        count = text.count(sub)
        if count == 0:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"emphasis substring {sub!r} does not occur in the "
                f"resolved English text -- authoring drift against the store"
            )
        if count > 1:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"emphasis substring {sub!r} occurs {count} times in the "
                f"resolved English text -- ambiguous anchor"
            )
        start = text.index(sub)
        occurrences.append((start, start + len(sub), sub))
    by_position = sorted(occurrences, key=lambda t: t[0])
    for (_, end1, sub1), (start2, _, sub2) in zip(by_position, by_position[1:]):
        if start2 < end1:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"emphasis substrings {sub1!r} and {sub2!r} overlap"
            )
    if [sub for _, _, sub in by_position] != list(emphasis):
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] emphasis "
            f"substrings must be declared in the order they occur in the "
            f"resolved English text"
        )
    return list(emphasis)


def _resolve_span(manifest: Manifest, seg_id: str, span: dict) -> dict:
    missing = [f for f in _REQUIRED_SPAN_FIELDS if not span.get(f)]
    if missing:
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] span is "
            f"missing required field(s) {missing}"
        )
    status = span["status"]
    if status not in ("translated", "desert"):
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] span has "
            f"status {status!r} -- expected 'translated' or 'desert'"
        )
    # Emitted keys are camelCase (shared/lib/data.ts ContextEnglishSpan),
    # matching the rest of this pipeline's emitted-JSON convention, even
    # though the hand-authored declaration file uses snake_case (matching
    # docs/source-passage-english-scoping.md's Phase C sketch).
    out = {
        "sourceAuthor": span["source_author"],
        "sourceWork": span["source_work"],
        "locus": span["locus"],
        "status": status,
    }
    if "head" in span:
        head = span["head"]
        if not isinstance(head, str) or not head.strip():
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] head "
                f"must be a non-empty string (the citation heading's exact "
                f"printed text)"
            )
        out["headText"] = head
    if status == "desert":
        if "translation" in span:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
                f"status 'desert' but names a translation -- a desert span "
                f"names no translation"
            )
        if span.get("translation_credit"):
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
                f"status 'desert' but carries a translation_credit -- a "
                f"desert span has no translation to credit"
            )
        if span.get("emphasis") is not None:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
                f"status 'desert' but declares 'emphasis' -- there is no "
                f"resolved English text to emphasize"
            )
        if "trim" in span or "alt_trims" in span or "alt_loci" in span:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
                f"status 'desert' but declares a trim or alt_loci -- there is "
                f"no English to trim"
            )
        return out
    # status == "translated"
    credit = span.get("translation_credit")
    if not isinstance(credit, str) or not credit.strip():
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
            f"status 'translated' but has no non-empty translation_credit"
        )
    pair = (span["source_author"], span["source_work"])
    if "translation" in span:
        translation = span["translation"]
        if not isinstance(translation, str) or not translation.strip():
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"translation must be a non-empty string"
            )
        if pair not in _TRIM_TO_EMPHASIS:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                f"translation is only allowed on Aristotle or "
                f"pseudo-Aristotle spans"
            )
    resolver = _RESOLVERS.get((span["source_author"], span["source_work"]))
    if resolver is None:
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}] names "
            f"source ({span['source_author']!r}, {span['source_work']!r}) "
            f"with status 'translated', but this module has no locus "
            f"resolver registered for that (source_author, source_work) "
            f"pair yet -- add one (or declare the span 'desert' if no PD "
            f"English exists)"
        )
    try:
        if "translation" in span:
            text, section_loci = _resolve_aristotle_alternate(span)
        else:
            text, section_loci = resolver(span["locus"])
    except ValueError as exc:
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}]: {exc}"
        ) from exc
    out["translationCredit"] = credit
    # Alternates are built from the full per-locus list, before any
    # flattening or trimming of the primary text.
    full_loci = section_loci
    if pair not in _SECTIONED_PAIRS and section_loci:
        # One continuous passage: no Stephanus or Bekker division.
        text = " ".join(text.split("\n\n"))
        section_loci = None
    out["text"] = text
    # Per-paragraph section markers. Only a multi-paragraph resolve carries
    # this -- one entry per paragraph in `text`, in order. Set BEFORE
    # emphasis so Diogenes Laertius and Plato keep their existing key order.
    if section_loci:
        out["sectionLoci"] = section_loci
    emphasis = None
    if pair in _TRIM_TO_EMPHASIS:
        # Emphasis is what defines the window (B.4). Validate the item-83
        # rules against the full resolved text, then trim.
        emphasis = span.get("emphasis")
        if not isinstance(emphasis, list) or not emphasis:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] is "
                f"status 'translated' for an Aristotle span but has no "
                f"emphasis -- emphasis defines the window"
            )
        emphasis = _validate_emphasis(manifest, seg_id, emphasis, text)
        text, section_loci = _trim_to_emphasis(text, emphasis, section_loci)
        out["text"] = text
        if section_loci:
            out["sectionLoci"] = section_loci
        else:
            out.pop("sectionLoci", None)
    elif span.get("emphasis") is not None:
        emphasis = _validate_emphasis(manifest, seg_id, span["emphasis"], text)
    if "trim" in span:
        # Trim to what DK quotes (owner ruling, 2026-09-27), on top of the
        # Aristotle sentence-keep.
        try:
            text, kept_loci = _apply_trim(text, section_loci, span["trim"])
        except ValueError as exc:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}]: {exc}"
            ) from exc
        out["text"] = text
        if kept_loci and len(kept_loci) > 1:
            out["sectionLoci"] = kept_loci
        else:
            out.pop("sectionLoci", None)
        if emphasis is not None:
            # Every bold run must survive the trim intact.
            emphasis = _validate_emphasis(manifest, seg_id, emphasis, text)
    if emphasis is not None:
        out["emphasis"] = emphasis
    alt_locus = _alt_locus(manifest, seg_id, span)
    try:
        alts = _jowett_alts(
            span["source_author"], span["source_work"], span["locus"], full_loci,
            alt_locus,
        )
        alts_out = _trim_alts(span, [alts] if alts else [])
    except ValueError as exc:
        raise ValueError(
            f"{manifest.work_id}: context-english.json[{seg_id!r}]: {exc}"
        ) from exc
    if alts_out:
        out["alts"] = alts_out
    return out


def _alt_locus(manifest: Manifest, seg_id: str, span: dict) -> str | None:
    """The span's `alt_loci`: `{"jowett": "<Plato locus>"}`, Plato spans
    only (see `_jowett_alts`)."""
    if "alt_loci" not in span:
        return None
    alt_loci = span["alt_loci"]
    where = f"{manifest.work_id}: context-english.json[{seg_id!r}]"
    if span["source_author"] != "Plato":
        raise ValueError(f"{where}: alt_loci is only allowed on Plato spans")
    if not isinstance(alt_loci, dict) or set(alt_loci) != {"jowett"}:
        raise ValueError(
            f"{where}: alt_loci must be {{\"jowett\": \"<locus>\"}} -- "
            f"got {alt_loci!r}"
        )
    return alt_loci["jowett"]


def run(manifest: Manifest, spine: dict) -> Path | None:
    src_path = SOURCES_DIR / manifest.work_id / "context-english.json"
    if not src_path.exists():
        return None
    declared = json.loads(src_path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict):
        raise ValueError(f"{manifest.work_id}: context-english.json must be an object")
    if not declared:
        raise ValueError(
            f"{manifest.work_id}: context-english.json must not be empty -- "
            f"an empty '{{}}' declares no coverage and reads as a truncated "
            f"file, not intentional 'no context English' (delete the file "
            f"instead if the work truly has none)"
        )
    segments = {seg["id"]: seg for seg in spine["segments"]}
    unknown = sorted(set(declared) - set(segments))
    if unknown:
        raise ValueError(
            f"{manifest.work_id}: context-english.json names column(s) "
            f"that match no spine segment: {unknown}"
        )
    resolved: dict[str, list[dict]] = {}
    for seg_id, entry in declared.items():
        spans = (entry or {}).get("context_spans")
        if not isinstance(spans, list) or not spans:
            raise ValueError(
                f"{manifest.work_id}: context-english.json[{seg_id!r}] must "
                f"carry a non-empty 'context_spans' list"
            )
        resolved[seg_id] = [_resolve_span(manifest, seg_id, s) for s in spans]
        # A span's `head` names the citation heading it translates; it must
        # be printed in this column's Greek (one line: a heading never
        # crosses a line).
        lines = [line.get("text", "") for line in segments[seg_id].get("lines", [])]
        for span in resolved[seg_id]:
            head = span.get("headText")
            if head is not None and not any(head in text for text in lines):
                raise ValueError(
                    f"{manifest.work_id}: context-english.json[{seg_id!r}] "
                    f"head {head!r} does not occur in the column's Greek"
                )
    out_path = BUILD_DIR / "stage1" / "context_english.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return out_path
