"""Stage 1 (Latin): PHI spine producer for all three Latin schemes this
module covers — book-section prose (Wave 2 Batch 1a — Cicero's *De
Officiis*, the pilot), verse-line continuous verse (Wave 2 Batch 2 —
Lucretius' *De Rerum Natura*; see `_parse_verse`/`_parse_spine_verse` below),
and flat bookless `section` prose (Wave 2 Batch 3 round 2 — Cicero's Cato
Maior, Laelius, De Fato, Lucullus, Paradoxa Stoicorum; see
`_parse_flat_section` below) — each a sibling path within this module
rather than a separate file — smallest faithful change, book-section's
`_line_text`/`_is_latin_letter`/`_check_sourcedesc`/
`_rejoin_wrapped_hyphens` helpers are reused as-is by both siblings.

Book-section: NO Beta Code decode (PHI text is plain Latin already). ~70%
generic reuse of stage1_greek.py's book-section SHAPE (export
-> per-book/per-section flatten -> segment grouping), re-implemented here
rather than imported: every other stage1_*.py module is self-contained with
no cross-imports of stage1_greek's private helpers (that module's own
comments document this as deliberate — "the two stages have no other
coupling"), and PHI's export carries two real structural differences from
every TLG book-section export that make straight reuse impossible anyway
(see `_parse_book_section` below):
  1. PHI's outer div lowercases its own @type (`<div type="book">`, not
     "Book") — handled via `citation.div_types.page`, a new scheme.py
     override (Wave 2 Batch 1a; DL's existing `div_types.section` override
     is the precedent).
  2. PHI's book-section export carries a whole-work title division
     (`<div type="book" n="t">`) AND a per-book title heading
     (`<div type="section" n="t">`, a short all-caps per-book heading label) —
     neither has a TLG book-section analogue, so both are dropped as
     non-citable front matter (verified against phi0474055.xml: exactly one
     "book t" and exactly one "section t" per real book, never a citable
     content collision). Each dropped title div's content is verified against
     a per-manifest declared hash (see `citation.title_labels` / the
     `_load_declared_title_labels` mechanism below) rather than quoted here —
     this repo's hard rule is that corpus source text is never committed (see
     dk_lang.py's identically-reasoned hash-key convention).

`_check_sourcedesc` IS imported from stage1_greek — it is genuinely
corpus-agnostic (operates on `tree`'s <sourceDesc> text only) and its own
docstring anticipates this reuse ("a differently-shaped sourceDesc ... a PHI
Latin work ... needs no special-casing").
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from lxml import etree

from . import lined
from . import scheme as scheme_mod
from .config import BUILD_DIR, REPO_ROOT, Manifest
from .lined import LinedAlphabet, _fold_hyphen_final_sigma
from .stage1_greek import _check_sourcedesc

EXPORT_DIR = BUILD_DIR / "export"


def exported_xml_path(manifest: Manifest) -> Path:
    w = manifest.data["work"]
    return (
        EXPORT_DIR
        / "Diogenes-Resources"
        / "xml"
        / "phi"
        / f"phi{w['phi_author']}{w['phi_work']}.xml"
    )


def _diogenes_scratch_config_dir(manifest: Manifest) -> Path:
    """Bootstrap (or reuse) a `Diogenes_Config_Dir` prefs directory under
    `build/` (gitignored, regenerated per clone) carrying a `phi_dir` line —
    the mechanism docs/tlg-phi-export.md's PHI section documents as the one
    actually load-bearing for resolving the corpus location (Diogenes'
    `Base.pm` reads its corpus paths from this prefs file only; a `TLG_DIR`/
    `PHI_DIR` env var passed directly to the subprocess is NOT read by the
    installed 4.5 Diogenes.app at all — verified empirically against the
    real app during Batch 1a's PHI export). De Officiis is prose, so no
    `-y`/`-Y` verse-mode flag or patched export script is needed here — the
    STOCK `/Applications/Diogenes.app/Contents/server/xml-export.pl`
    correctly auto-detects prose vs. verse per work (confirmed: its own
    export log prints "(prose)" for De Officiis). Lucretius (Batch 2, verse)
    will need the patched script's `-y` flag; this function only sets up
    what prose export needs."""
    cfg_dir = BUILD_DIR / "diogenes-scratch"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    prefs = cfg_dir / "diogenes.prefs"
    prefs.write_text(f'phi_dir "{manifest.phi_dir()}"\n', encoding="utf-8")
    return cfg_dir


_PATCH_FILE = REPO_ROOT / "docs" / "diogenes-xml-export-y.patch"


def _patched_export_script(manifest: Manifest) -> Path:
    """Bootstrap (or reuse) a scratch copy of Diogenes' `xml-export.pl` with
    `docs/diogenes-xml-export-y.patch` applied — the `-y`/`-Y` verse-mode
    flags the installed 4.5 build's stock script lacks (docs/tlg-phi-
    export.md's TLG recipe, step 1: "Copy ... to a writable scratch
    location and apply docs/diogenes-xml-export-y.patch"). The stock
    `/Applications/Diogenes.app` install is never modified in place — this
    always derives a fresh scratch copy from the tracked patch file rather
    than hardcoding a path to a pre-built patched script (the one at
    build/phi-test/scratch-script/ is untracked, throwaway scratch — not a
    dependency). Mirrors `_diogenes_scratch_config_dir`'s bootstrap-or-reuse
    shape under `build/` (gitignored, regenerated per clone).

    Needed for verse-line Latin works (Lucretius, Batch 2): unlike De
    Officiis (book-section, prose), a verse-line PHI export must run in
    strict verse mode (`-y`) rather than trust the stock script's prose/
    verse auto-detect heuristic, which is unverified against PHI works.
    `tei_all.rnc` is copied alongside the script (same doc step) since the
    patched script validates against it from its own directory."""
    scratch_dir = BUILD_DIR / "diogenes-scratch"
    script = scratch_dir / "xml-export-local-y.pl"
    if script.exists():
        return script
    scratch_dir.mkdir(parents=True, exist_ok=True)
    stock_server = manifest.diogenes_server()
    shutil.copy(stock_server / "xml-export.pl", script)
    result = subprocess.run(
        ["patch", str(script), str(_PATCH_FILE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        script.unlink(missing_ok=True)
        raise RuntimeError(
            f"applying {_PATCH_FILE} to a scratch copy of xml-export.pl "
            f"failed (exit {result.returncode}): {result.stdout}{result.stderr}"
        )
    shutil.copy(stock_server / "tei_all.rnc", scratch_dir / "tei_all.rnc")
    return script


def run_export(manifest: Manifest) -> Path:
    """Run Diogenes xml-export.pl for a PHI author (-c phi) unless already
    done. Exports every work of the declared author in one invocation (the
    same one-invocation-per-author shape as stage1_greek.run_export) — the
    caller only reads the one file it needs (`exported_xml_path`).

    Prose (book-section) works run the STOCK script with no verse flag —
    its own prose/verse auto-detect heuristic is confirmed correct for De
    Officiis (Batch 1a; see `_diogenes_scratch_config_dir`'s doc comment).
    A verse-line work instead dispatches through `_patched_export_script`'s
    scratch copy with `-y` forced (docs/tlg-phi-export.md: "Use -y for
    verse works ... omit it for prose") — the two `-I` includes mirror
    that doc's own worked TLG command exactly (Diogenes' own modules, then
    its CPAN dependencies), and `cwd` moves to the patched script's own
    scratch directory so it finds its `tei_all.rnc` neighbor."""
    out = exported_xml_path(manifest)
    if out.exists():
        return out
    w = manifest.data["work"]
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    cfg_dir = _diogenes_scratch_config_dir(manifest)
    sch = scheme_mod.for_manifest(manifest)
    env = {"Diogenes_Config_Dir": str(cfg_dir), "PATH": "/usr/bin:/bin"}
    if sch.verse_line_scheme:
        script = _patched_export_script(manifest)
        stock_server = manifest.diogenes_server()
        cmd = [
            "perl",
            "-I", str(stock_server),
            "-I", str(stock_server.parent / "dependencies" / "CPAN"),
            str(script),
            "-c", "phi",
            "-n", w["phi_author"],
            "-y",
            "-o", str(EXPORT_DIR),
        ]
        cwd = script.parent
    else:
        cmd = [
            "perl",
            "xml-export.pl",
            "-c", "phi",
            "-n", w["phi_author"],
            "-o", str(EXPORT_DIR),
        ]
        cwd = manifest.diogenes_server()
    subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    if not out.exists():
        raise FileNotFoundError(f"export ran but {out} is missing")
    return out


def _line_text(el: etree._Element) -> str:
    """Flatten a div's full text content (itertext(), whitespace-collapsed)
    — the Latin analogue of stage1_greek._line_text with no strip_bars/
    extra_strip_chars params (PHI's export carries no "|" edition-line-break
    convention; unlike TLG's verse-mode export, De Officiis is plain <p>
    prose with no <l> lines at all — confirmed zero <l> elements in
    phi0474055.xml)."""
    text = "".join(el.itertext())
    return re.sub(r"\s+", " ", text).strip()


def _is_latin_letter(ch: str) -> bool:
    """Mirrors stage3_tokenize.py's identically-named helper (duplicated
    rather than imported — same precedent as stage1_greek.py's own
    `_is_greek_letter` duplication: the two stages have no other coupling)."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("LATIN") and unicodedata.category(ch).startswith("L")


LATIN_LINED = LinedAlphabet(
    is_letter=_is_latin_letter,
    # Points at the same sigma-fold lined.py's wrap machinery now applies
    # universally to both alphabets (2026-08-30 cross-script wrap fix) --
    # identity on ordinary Latin text (no final ς to fold), so this changes
    # no existing Latin behavior; it matters only for a Greek fragment
    # wrapped inside a Latin work (e.g. de-finibus "σκοτει-" / "νός"). This
    # field itself is no longer read by the wrap machinery (which calls
    # `_fold_hyphen_final_sigma` directly) -- kept in sync for construction-
    # site clarity, see LinedAlphabet's own comment in lined.py.
    fold_wrap_final=_fold_hyphen_final_sigma,
    name="latin",
    # PHI's leading apostrophe (`'honestum`, a quotation opener glued onto
    # the next word with no space) is deliberately NOT in stage3_tokenize's
    # Latin surface-trim set, so _surface() keeps it in the token's `t` --
    # see stage3_tokenize._to_latin_lookup_key's docstring. lined.py's
    # fragment-start advance must land ON it, not skip past it into the
    # letter run. All four apostrophe codepoints stage3 recognizes
    # (_APOSTROPHES: ' ’ ᾽ ʼ) glue the same way on the
    # leading edge (Grok gate probe, 2026-08-30); any OTHER leading char
    # stage3 would keep is unattested in PHI Latin, and preflight's
    # wrapO-token check catches a mismatch loudly.
    frag_start_glued_chars="'’᾽ʼ",
)


def _rejoin_wrapped_hyphens(text: str) -> str:
    """Rejoin PHI print-line hyphenation that survives as a literal "- "
    WITHIN a single section's flattened, whitespace-collapsed text — the
    Latin analogue of stage1_greek._rejoin_wrapped_hyphens (identical
    algorithm, gated on Latin letters instead of Greek; duplicated per that
    function's own "no other coupling" precedent, and no offset-mapping
    variant is needed here since De Officiis does not opt into a
    `_chapter_sections`-style standoff channel).

    A hyphen directly preceded by a Latin letter and, after a run of spaces,
    directly followed by a LOWERCASE Latin letter rejoins (so "Nor- banum",
    capitalized only because it is a proper name split across the wrap,
    still rejoins: the check is on the letter AFTER the wrap, not before).

    Content-verification correction (Grok content-defect finding, Wave 2
    Batch 1a): an earlier version of this docstring claimed De Officiis'
    real corpus-wide print-line wraps (the "animan- tium" family) were
    handled HERE — they are not. Every one of the 7 genuine wraps in the
    real export (phi0474055.xml) turns out to straddle a SECTION boundary
    (the hyphenated half ends one `<div type="section">`'s flattened text,
    the continuation opens the very next section's) — this function only
    ever sees one section's own text at a time, so it cannot see (let alone
    rejoin) either half of a cross-section wrap; verified empirically
    against the real export, this function rejoins ZERO occurrences
    corpus-wide today. The cross-section case is handled separately by
    `_rejoin_cross_section_hyphens` below, which operates on the flat
    section list (so it CAN see both halves). This function remains a
    correct, defensive intra-section handler for the shape it actually
    covers (a wrap that happens not to cross a section boundary) — kept
    per Karpathy rule 3 (surgical: not removing working, tested code that
    is simply not exercised by this particular export), covered by its own
    existing direct/synthetic unit tests."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and i > 0 and _is_latin_letter(text[i - 1]):
            j = i + 1
            while j < n and text[j] == " ":
                j += 1
            if j > i + 1 and j < n and _is_latin_letter(text[j]) and text[j].islower():
                i = j
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _rejoin_cross_section_hyphens(
    flat: list[dict], manifest: Manifest, *, same_book_required: bool = True
) -> int:
    """Rejoin a PHI print-line hyphen wrap that straddles a SECTION boundary
    — the case `_rejoin_wrapped_hyphens` above cannot see (it only ever
    reads one section's own flattened text). Hyphen-owner-wins: the complete
    word joins the section where it BEGINS (its trailing "-" is replaced by
    the continuation letters), and those same letters are removed from the
    head of the following section's text, exactly mirroring the "role
    boundary" ownership rule elsewhere in this pipeline (a token belongs to
    the citable unit it starts in, never split across one).

    Detection mirrors `_rejoin_wrapped_hyphens`'s own shape check exactly
    (a hyphen directly preceded by a Latin letter; the following section's
    text begins with a LOWERCASE Latin letter), applied across the flat,
    document-ordered `(column, text)` pair instead of within one string —
    and, when `same_book_required` (the default, used by book-section),
    additionally requires both sections to share the same book (a hyphen
    wrap has never been observed, and is not expected, to straddle a book
    boundary; PHI's own book/section export makes that shape impossible to
    produce honestly anyway). `same_book_required=False` is the flat
    `section`-scheme caller's mode (Wave 2 Batch 3 round 2 —
    `_parse_flat_section`): that scheme has no book axis at all (every
    column belongs to the work's single declared book), and a flat
    column's bare token has no "." to split on the way a dotted
    book-section column does — the boundary check simply does not apply,
    so every adjacent pair is eligible.

    Verified against the real export (phi0474055.xml, De Officiis): exactly
    7 genuine cross-section wraps corpus-wide — 1.97/98 ("animan-"/"tium"
    -> "animantium"), 1.146/147 ("quo-"/"rum" -> "quorum"), 2.9/10
    ("vi-"/"tae" -> "vitae"), 2.49/50 ("Nor-"/"banum" -> "Norbanum"),
    2.72/73 ("neces-"/"saria" -> "necessaria"), 3.27/28 ("ve-"/"rum" ->
    "verum"), 3.61/62 ("se-"/"mel" -> "semel") — an exhaustive corpus-wide
    scan for this shape found no others. Mutates `flat` in place (the
    caller's list of dicts, so downstream `text` values are already
    corrected); returns the number of rejoins performed, which the caller
    cross-checks against the manifest's declared
    `citation.cross_section_rejoins` (a re-export drift tripwire — a future
    PHI re-export producing a different count must fail loudly, not
    silently rejoin a different, unreviewed set of words)."""
    n = 0
    for i in range(len(flat) - 1):
        cur, nxt = flat[i], flat[i + 1]
        if same_book_required and cur["column"].split(".", 1)[0] != nxt["column"].split(".", 1)[0]:
            continue  # never straddle a book boundary
        text = cur["text"]
        if len(text) < 2 or text[-1] != "-" or not _is_latin_letter(text[-2]):
            continue
        nxt_text = nxt["text"]
        if not nxt_text or not _is_latin_letter(nxt_text[0]) or not nxt_text[0].islower():
            continue
        word, _sep, rest = nxt_text.partition(" ")
        cur["text"] = text[:-1] + word
        nxt["text"] = rest
        n += 1
    return n


# Declared-hash guard for a dropped n="t" title div (module docstring point
# 2 / `_parse_book_section` below; adversarial-review Finding 2, replacing an
# earlier shape-heuristic guard — see git history for that version and its
# own rationale). A blind `n == "t"` match with no content check would
# silently swallow a genuine citable section if some future/other PHI
# export ever reused "t" for something else, or if a title div ever grew
# stray sibling content — a SHAPE heuristic (short, all-caps) narrows that
# risk but a plausible short all-caps sentence could still be silently
# dropped. So the guard is instead a DECLARED expectation: each Latin
# manifest lists every title div it expects to drop as
# `citation.title_labels`, a list of `{sha256_16, note}` entries (the
# dk_lang.py hash-key convention — this repo's hard rule is that corpus
# source text is never committed, so the manifest declares a hash of each
# label's exact flattened text, plus a short NON-VERBATIM human note, never
# the label itself). `_load_declared_title_labels` loads and validates that
# list; `_check_title_drop` asserts a candidate's content hash is declared
# (an undeclared drop is FATAL — never silently dropped) with only a
# generous shape cap (`_TITLE_LABEL_SHAPE_CAP`) left as defense-in-depth;
# `_finalize_title_drops` asserts the observed drops match the declaration
# exactly (both directions — a stale declared entry never observed, or a
# count mismatch, both fail loudly). The POSITION each candidate is checked
# at is unchanged from the original shape-heuristic guard (book n="t" /
# section n="t" nested in a non-title book, for this scheme; the flat and
# verse-line schemes' own analogous positions below) — only the content
# check changed.
_HASH_KEY_RE = re.compile(r"^[0-9a-f]{16}$")
_TITLE_LABEL_SHAPE_CAP = 200


def _title_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_declared_title_labels(manifest: Manifest) -> list[str]:
    """The manifest's declared `citation.title_labels` as a list of content
    hashes (order-independent, duplicates preserved — the same exact label
    text can legitimately recur, e.g. De Rerum Natura's whole-work title
    line repeats verbatim in every book, so this is a MULTISET, not a set).
    REQUIRED for every work this module's parsers walk — mirrors `citation.
    transpositions`' "required, explicit empty list is fine" precedent
    (verse-line): a work whose export genuinely drops no title divs
    declares `title_labels: []`, but omitting the key entirely is a
    fail-open hazard, not a supported bootstrapping state."""
    raw = (manifest.data.get("citation") or {}).get("title_labels")
    if raw is None:
        raise ValueError(
            f"{manifest.work_id}: citation.title_labels is required — "
            f"declare a list of {{sha256_16, note}} entries, one per title "
            f"div this work's parser expects to drop (an explicit empty "
            f"list is fine once verified this export drops none)"
        )
    if not isinstance(raw, list):
        raise ValueError(f"{manifest.work_id}: citation.title_labels must be a list")
    hashes: list[str] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or set(entry) != {"sha256_16", "note"}:
            raise ValueError(
                f"{manifest.work_id}: citation.title_labels[{i}] must be an "
                f"object with exactly the keys sha256_16 and note"
            )
        h = entry["sha256_16"]
        if not isinstance(h, str) or not _HASH_KEY_RE.match(h):
            raise ValueError(
                f"{manifest.work_id}: citation.title_labels[{i}].sha256_16 "
                f"must be a 16-hex-character sha256 prefix, not {h!r}"
            )
        note = entry["note"]
        if not isinstance(note, str) or not note:
            raise ValueError(
                f"{manifest.work_id}: citation.title_labels[{i}].note must "
                f"be a non-empty (non-verbatim) string"
            )
        hashes.append(h)
    return hashes


def _check_title_drop(text: str, context: str, declared: list[str], manifest: Manifest) -> str:
    """FATAL unless `text`'s content hash is declared in `citation.
    title_labels`. `_TITLE_LABEL_SHAPE_CAP` is a minimal shape sanity check
    kept purely as defense-in-depth (an empty or absurdly long div was never
    a plausible title label to begin with, independent of the hash check);
    it is not the primary guard — the declared hash is. Returns the content
    hash on success, for the caller to accumulate and cross-check via
    `_finalize_title_drops`."""
    if not text or len(text) > _TITLE_LABEL_SHAPE_CAP:
        raise ValueError(
            f"{manifest.work_id}: {context} n=\"t\" div fails the "
            f"defense-in-depth shape cap (empty, or over "
            f"{_TITLE_LABEL_SHAPE_CAP} chars) — refusing to silently drop "
            f"what may be substantive content"
        )
    h = _title_content_hash(text)
    if h not in declared:
        raise ValueError(
            f"{manifest.work_id}: {context} n=\"t\" div's content hash "
            f"{h!r} is not declared in citation.title_labels — an "
            f"undeclared title-drop candidate is fatal; verify the content "
            f"by hand and, if it genuinely is a bare title label, add its "
            f"{{sha256_16, note}} entry to the manifest"
        )
    return h


def _finalize_title_drops(observed: list[str], declared: list[str], manifest: Manifest, kind: str) -> None:
    """Cross-checks the full multiset of hashes actually dropped during a
    parse against `citation.title_labels`' declared multiset — bidirectional,
    mirroring `citation.lacunae`'s own bidirectional check in `_parse_verse`:
    a count mismatch (declaring more or fewer drops than actually happened)
    and a stale declared hash (declared but never observed — a re-export
    dropped or reworded a heading) both fail loudly rather than silently
    passing."""
    observed_counts = Counter(observed)
    declared_counts = Counter(declared)
    if len(observed) != len(declared):
        raise ValueError(
            f"{manifest.work_id}: {kind} title-label count mismatch — "
            f"observed {len(observed)} dropped title div(s) but citation."
            f"title_labels declares {len(declared)}"
        )
    if observed_counts != declared_counts:
        stale = sorted((declared_counts - observed_counts).elements())
        unexpected = sorted((observed_counts - declared_counts).elements())
        raise ValueError(
            f"{manifest.work_id}: {kind} citation.title_labels mismatch — "
            f"stale declaration(s) (declared but never observed): "
            f"{stale or 'none'}; unexpected drop(s) (observed but not "
            f"declared): {unexpected or 'none'}"
        )


# `citation.source_book` (Wave 2 Seneca essays — docs/wave2-seneca-design.md
# §E.3): a single-book essay (De Providentia = Dialogi book 1, De Constantia
# Sapientis = Dialogi book 2) is one PHI *book* out of a 12-book file
# (phi1017012.xml holds the whole Dialogi), but the essay's OWN citation is
# 2-level (chapter.section) — book-section's page axis is remapped onto the
# PHI *chapter* level (`citation.div_types.page: "chapter"`) rather than the
# literal outer `<div type="book">`, which is instead scoped down to exactly
# one declared book via this key. `_resolve_source_book` finds that one
# `<div type="book" n=source_book>` (the literal PHI structural type — a
# corpus-wide constant, independent of any per-work `div_types.page`
# override, which for an essay names the CHAPTER div, not this outer one)
# and returns it as the scope root `_parse_book_section` walks instead of
# the whole tree. Since lxml's `.iter()` on that single element only ever
# visits ITS OWN descendants, every other Dialogi book's content is
# structurally unreachable from the scoped walk — "other books' content
# leaking" (the design note's fail-loud item) is therefore a walk-scoping
# bug, not a content filter, and is exercised by a dedicated regression test
# rather than a runtime cross-check. A declared `source_book` absent from
# the export, or matching more than one `<div type="book">` (should never
# happen — book `@n` is unique per PHI's own convention, but never assumed),
# is fatal via the match-count check below.
def _resolve_source_book(tree, manifest: Manifest):
    """None when `citation.source_book` is not declared (every pre-Seneca
    Latin book-section manifest — the legacy whole-tree walk is unchanged).
    Otherwise the single `<div type="book">` element named by the declared
    token, to scope `_parse_book_section`'s walk to."""
    source_book = (manifest.data.get("citation") or {}).get("source_book")
    if source_book is None:
        return None
    if not isinstance(source_book, str) or not source_book:
        raise ValueError(f"{manifest.work_id}: citation.source_book must be a non-empty string")
    matches = [d for d in tree.iter("{*}div") if d.get("type") == "book" and d.get("n") == source_book]
    if len(matches) != 1:
        raise ValueError(
            f"{manifest.work_id}: citation.source_book {source_book!r} must "
            f"match exactly one <div type=\"book\"> in the export, found "
            f"{len(matches)}"
        )
    return matches[0]


def _parse_book_section(tree, sch, manifest: Manifest) -> list[dict]:
    """Flat (column, n=1, text) list for PHI's book-section prose export.

    `<div type="book" n="1..3">` (page_div_type, overridden via
    `citation.div_types.page: "book"` — PHI lowercases this @type, unlike
    every TLG book-section export's capitalized "Book") directly nests
    `<div type="section" n="...">` (section_div_type, overridden via
    `citation.div_types.section: "section"`, the same DL precedent) — no
    intermediate "chapter" level at all, unlike Meditations' book>chapter>
    section nesting. Each section div IS the citable column
    ("book.section", e.g. De Officiis 1.7); its own itertext() flatten
    (there is no further nesting to strip — confirmed the export's only div
    @types are "book" and "section") becomes the segment's one synthetic
    line, exactly like stage1_greek's chapter flatten.

    A single-book essay (`citation.source_book` declared — see
    `_resolve_source_book` above) instead maps PHI *chapter* divs onto this
    same page axis (`citation.div_types.page: "chapter"`) scoped to one
    declared Dialogi book: the walk below iterates `page_div_type` divs
    within that scope root rather than the whole tree, so what this
    docstring calls "book_n" is the essay's PHI *chapter* token. The
    mechanism is otherwise unchanged — same title-drop gate (an essay's
    per-book chapter `n="t"` heading is the "book" title-drop branch below),
    same digit-or-"t" token check, same column composition.

    Two non-citable divs, both dropped rather than emitted (verified against
    the real export: `<div type="book" n="t">` occurs exactly once — the
    whole-work title — and each real book's first section is
    `<div type="section" n="t">` — a per-book heading label): a section
    n="t" is dropped BEFORE composing a column (a "t.1"-shaped column would
    not even match book-section's `_DOTTED_COLUMN_RE`, which requires digits
    on both sides), and an entire book n="t" is skipped up front so its own
    nested section n="1" (the title text's own container) is never visited
    at all. Both drops are gated on the manifest's declared
    `citation.title_labels` (see `_check_title_drop`/`_finalize_title_drops`
    above) — the exact content, not just the shape, must be a match a human
    reviewer signed off on. An unrecognized non-digit, non-"t" page/section
    @n is a loud ValueError — this export shape has no other special
    numbering convention (no DL-style lettered fragments, no dk-style stubs)
    to account for; a page token failing this check is the design note's
    "undeclared chapter tokens" fail-loud item for the essays."""
    citation = manifest.data.get("citation") or {}
    lined_source = citation.get("lined_source") is True
    if lined_source and "cross_section_rejoins" in citation:
        raise ValueError(
            f"{manifest.work_id}: citation.lined_source and "
            f"citation.cross_section_rejoins cannot both be declared"
        )
    lined_section_div = citation.get("lined_section_div")
    declared_cross_column_wraps = citation.get("lined_cross_column_wraps") \
        if "lined_cross_column_wraps" in citation else None
    declared_titles = _load_declared_title_labels(manifest)
    observed_titles: list[str] = []
    flat: list[dict] = []
    scope_root = _resolve_source_book(tree, manifest)
    walk_root = scope_root if scope_root is not None else tree
    for book_div in walk_root.iter("{*}div"):
        if book_div.get("type") != sch.page_div_type:
            continue
        book_n = book_div.get("n")
        if book_n == "t":
            observed_titles.append(_check_title_drop(_line_text(book_div), "book", declared_titles, manifest))
            continue
        if scope_root is not None and not (isinstance(book_n, str) and book_n.isdigit()):
            # "undeclared chapter tokens" (design note §E.3's fail-loud
            # item): scoped ONLY to the source_book essay path — every
            # pre-existing book-section work (De Officiis et al.) never
            # declared this check and keeps its exact prior behavior
            # (surgical/blast-radius discipline; the section-level
            # equivalent below is, and always was, unconditional).
            raise ValueError(
                f"{manifest.work_id}: unrecognized PHI {sch.page_div_type} "
                f"n={book_n!r} — expected a plain digit string or the "
                f"title marker 't'"
            )
        for sec_div in book_div.iter("{*}div"):
            if sec_div.get("type") != sch.section_div_type:
                continue
            n = sec_div.get("n")
            if n == "t":
                observed_titles.append(
                    _check_title_drop(_line_text(sec_div), f"book {book_n!r} section", declared_titles, manifest)
                )
                continue
            if not (isinstance(n, str) and n.isdigit()):
                raise ValueError(
                    f"{manifest.work_id}: unrecognized PHI section n={n!r} "
                    f"in book {book_n!r} — expected a plain digit string or "
                    f"the book/section title marker 't'"
                )
            column = sch.compose_column(book_n, n)
            if lined_source:
                section_lines = lined._lined_chapter_lines(
                    sec_div,
                    lined_section_div,
                    alphabet=LATIN_LINED,
                    column=column,
                )
                if section_lines:
                    lined._apply_lined_wraps(
                        column,
                        section_lines,
                        alphabet=LATIN_LINED,
                        defer_column_final=declared_cross_column_wraps is not None,
                    )
                    flat.extend({"column": column, **line} for line in section_lines)
                continue
            text = _rejoin_wrapped_hyphens(_line_text(sec_div))
            if text:
                flat.append({"column": column, "n": 1, "text": text})

    _finalize_title_drops(observed_titles, declared_titles, manifest, "book-section")

    # Cross-section print-line hyphen wraps (Grok content-defect fix — see
    # `_rejoin_cross_section_hyphens`'s own doc): must run AFTER the whole
    # flat list is built (it needs to see consecutive sections' text
    # together), so it cannot be folded into the per-section loop above.
    # An essay scoped via `source_book` (§E.5 of the design note) runs with
    # `same_book_required=False`: its "book" axis is really the chapter, and
    # a print-line wrap can legitimately straddle a chapter seam (there is
    # only ever one real Dialogi book in scope, so this can never reach
    # across an actual book boundary either way).
    if lined_source:
        if declared_cross_column_wraps is not None:
            if not isinstance(declared_cross_column_wraps, int):
                raise ValueError(
                    f"{manifest.work_id}: citation.lined_cross_column_wraps must "
                    f"be an integer, got {declared_cross_column_wraps!r}"
                )
            actual = lined._apply_lined_cross_column_wraps(
                flat, alphabet=LATIN_LINED
            )
            if actual != declared_cross_column_wraps:
                raise ValueError(
                    f"{manifest.work_id}: citation.lined_cross_column_wraps mismatch: "
                    f"declared {declared_cross_column_wraps}, observed {actual}"
                )
    else:
        n_rejoins = _rejoin_cross_section_hyphens(flat, manifest, same_book_required=(scope_root is None))
        _check_cross_section_rejoin_count(n_rejoins, manifest)
    return flat


def _check_cross_section_rejoin_count(n_rejoins: int, manifest: Manifest) -> None:
    """Shared re-export-drift tripwire for `citation.cross_section_rejoins`
    (declared count of `_rejoin_cross_section_hyphens` hits) — factored out
    so both `_parse_book_section` and `_parse_flat_section` (Wave 2 Batch 3
    round 2) share one check rather than duplicating it. Absence of the
    declaration is a no-op (mirrors `expected_sourcedesc`'s own
    absence-means-no-op precedent)."""
    expected_rejoins = (manifest.data.get("citation") or {}).get("cross_section_rejoins")
    if expected_rejoins is None:
        return
    if not isinstance(expected_rejoins, int):
        raise ValueError(
            f"{manifest.work_id}: citation.cross_section_rejoins must "
            f"be an integer"
        )
    if n_rejoins != expected_rejoins:
        raise ValueError(
            f"{manifest.work_id}: expected {expected_rejoins} "
            f"cross-section hyphen rejoin(s) (citation."
            f"cross_section_rejoins) but this export produced "
            f"{n_rejoins} — a re-export text change; verify the new "
            f"wraps by hand before updating the declared count"
        )


# --------------------------------------------------------------------------
# `letter` scheme (Wave 2 Seneca — Epistulae Morales, PHI 1017/015; design
# note docs/wave2-seneca-design.md §A-D): a sibling path within this module,
# reusing book-section's page>section grammar wholesale with the page axis
# relabeled "letter" (§A) — `<div type="letter" n="t|1..124|fr">` nests
# `<div type="section" n="sa|t|1..N">`. Three deltas over plain book-section,
# all declared and fail-loud (never silent):
#   * §B: each real letter's `<section n="sa">` salutation folds onto that
#     letter's section "1" as a leading `role="salutation"` line, gated on
#     `citation.salutation_role: true` — never its own citable column.
#   * §C: the pre-letter-1 `letter n="t"` shell is taken WHOLE, never via the
#     naive "drop section n='t'" rule (its own nested `section n="1"` is the
#     book-1 heading label, never letter 1's real section 1 — the design
#     note's explicit warning that rule would miss this one), plus 17
#     embedded `section n="t"` per-Liber headings inside real letters — both
#     verified via the same declared-hash `citation.title_labels` gate
#     book-section uses (`_check_title_drop`/`_finalize_title_drops`), 18
#     entries total. REVIEW-CHECKLIST item 5 (John's ruling): once verified,
#     the label text is RESTORED as a leading `role="heading"` line on that
#     letter's own section 1 (ahead of any `role="salutation"` line) rather
#     than discarded — never its own citable column, exactly like the
#     salutation fold in §B just above.
#   * §D: `letter n="fr"` (the post-124 Gellius appendix) is excluded via
#     `citation.exclude_letters`, the `exclude_sections` bidirectional
#     tripwire pattern (`_check_exclude_sections`) lifted to the page axis
#     (`_check_exclude_letters` below) — never descended into, so its own
#     internal `n="t"` heading is never reached or hash-checked.


def _check_exclude_letters(declared: set[str], observed_tokens: list[str], manifest: Manifest) -> None:
    """Cross-check `citation.exclude_letters` (§D: the Gellius `fr`
    appendix after Ep. 124) against what `_parse_letters` actually observed
    and excluded — the letter-axis analogue of `_check_exclude_sections`
    above (same bidirectional shape: a separate function per that
    function's own precedent of one check per axis/scheme, so each error
    message names its own manifest key rather than a shared parametrized
    one). Every declared token must have been observed EXACTLY ONCE (a
    re-export that drops, renumbers, or duplicates a declared exclusion
    fails loudly — a stale or now-ambiguous declaration, not silently kept
    or silently double-dropped) and every excluded token must have been
    declared (the walker only ever adds to `observed_tokens` when the
    token is already in `declared`, so this is a defensive invariant, not a
    reachable path today)."""
    counts = Counter(observed_tokens)
    stale = sorted(tok for tok in declared if counts.get(tok, 0) == 0)
    if stale:
        raise ValueError(
            f"{manifest.work_id}: citation.exclude_letters declares "
            f"{stale} but the export does not contain that letter token "
            f"exactly once — stale declaration; a re-export dropped or "
            f"renumbered it, fix the manifest rather than keeping a dead "
            f"entry"
        )
    duplicated = sorted(tok for tok in declared if counts.get(tok, 0) > 1)
    if duplicated:
        raise ValueError(
            f"{manifest.work_id}: citation.exclude_letters token(s) "
            f"{duplicated} occur more than once in the export — expected "
            f"each declared exclusion exactly once"
        )


def _parse_letters(tree, sch, manifest: Manifest) -> list[dict]:
    """Flat (column, n, text[, role]) list for PHI's Epistulae Morales
    export — see the module-doc block just above this function for the
    three declared deltas over plain book-section (salutation fold, title
    drops, fr exclusion) this walker implements.

    Section-token dispatch within a real letter (n=1..124, i.e. not "t" and
    not declared-excluded):
      * "sa" — captured, not yet emitted (attached to section "1" below).
        At most one per letter; a second is a loud ValueError.
      * "t" — an embedded per-Liber heading, verified exactly like
        book-section's per-book heading (context says "letter", not
        "book") and then captured for restoration onto section "1" below —
        never its own citable column.
      * a plain digit — an ordinary citable column. When it is "1", any
        captured heading (the letter-"t" shell for letter 1, or this
        letter's own embedded section "t") is emitted FIRST as a leading
        `n=1, role="heading"` line sharing that column (REVIEW-CHECKLIST
        item 5, John's ruling — restored rather than discarded). When
        `citation.salutation_role` is also set, the captured salutation (if
        non-empty) is emitted next as its own `n=1, role="salutation"` line
        sharing that same column, and section 1's own text follows as
        `n=2` (or `n=1` if there is no salutation to precede it) — every
        entry sharing one column/segment (never a separate citable unit),
        matching stage7's existing per-line `role` passthrough (dk's
        `context` role precedent). Every other digit section is a single
        `n=1` line, unchanged from book-section.
      * anything else is a loud ValueError.

    `citation.salutation_role` gates two bidirectional invariants, checked
    per real letter: a section "1" with no preceding "sa" is fatal (a
    missing salutation), and a "sa" with no section "1" to attach to is
    fatal (an empty or malformed letter) — "exactly one sa per real letter"
    per the design note, asserted only over letters 1-124 (fr has no sa and
    is never descended into).

    Salutation attachment is a POST-PASS over a `body` list built exactly
    like book-section's own flat list (one entry per real section, never
    split) — never spliced in during the walk itself. This matters for
    `_rejoin_cross_section_hyphens`, which assumes ADJACENT flat entries are
    adjacent SECTIONS: were a salutation line spliced in immediately ahead
    of every letter's section 1, it would sit between one letter's last
    section and the next letter's section 1 in the flat list, silently
    defeating detection of a hyphen wrap that straddles that boundary. The
    rejoin therefore runs on `body` alone; salutation lines are spliced onto
    the (already-rejoined) section-1 entries afterward, purely additively."""
    declared_titles = _load_declared_title_labels(manifest)
    observed_titles: list[str] = []
    raw_exclude_letters = (manifest.data.get("citation") or {}).get("exclude_letters") or []
    # A duplicate entry in the manifest's OWN declaration (an authoring
    # slip, e.g. "fr" listed twice) must fail loud naming the duplicate --
    # `set(...)` below silently collapses it otherwise, which would hide
    # the mistake rather than surfacing it (this is a check on the
    # declaration itself, distinct from `_check_exclude_letters` below,
    # which cross-checks the declaration against what the EXPORT contains).
    _dup_exclude_letters = sorted(
        tok for tok, count in Counter(raw_exclude_letters).items() if count > 1
    )
    if _dup_exclude_letters:
        raise ValueError(
            f"{manifest.work_id}: citation.exclude_letters declares "
            f"duplicate token(s) {_dup_exclude_letters} — each exclusion "
            f"must be declared exactly once"
        )
    declared_exclude = set(raw_exclude_letters)
    excluded_tokens: list[str] = []
    # Schema-validated as a real boolean, not merely truthy: `bool(...)` on
    # a raw YAML value would accept the STRING "false" (a plausible
    # authoring slip -- an accidentally-quoted manifest value) as True,
    # since any non-empty string is truthy in Python. `salutation_role`
    # gates a whole structural mechanism (every real letter must carry
    # exactly one "sa" div, checked below), so a silently-wrong flag value
    # must fail loud naming the offending value, not be coerced.
    raw_salutation_role = (manifest.data.get("citation") or {}).get("salutation_role", False)
    if not isinstance(raw_salutation_role, bool):
        raise ValueError(
            f"{manifest.work_id}: citation.salutation_role must be a real "
            f"boolean (true/false), got {raw_salutation_role!r} "
            f"({type(raw_salutation_role).__name__})"
        )
    salutation_role = raw_salutation_role

    body: list[dict] = []
    pending_salutations: dict[str, str] = {}
    # §C restore: a captured heading's verbatim (hash-verified) text, keyed
    # by the letter it precedes — the letter-"t" shell keys onto letter "1"
    # (it always immediately precedes it), an embedded section "t" keys onto
    # its own letter. Folded onto that letter's section "1" below, exactly
    # like `pending_salutations` above.
    pending_headings: dict[str, str] = {}

    for letter_div in tree.iter("{*}div"):
        if letter_div.get("type") != sch.page_div_type:
            continue
        letter_n = letter_div.get("n")

        if letter_n == "t":
            # The COMPLETE direct-child shape, not just the section-typed
            # divs among it: `letter_div.iterchildren("{*}div")` filtered by
            # type (the old check) silently ignores any other direct child
            # -- a rogue non-section div (a stray "note" type) or a non-div
            # element entirely (a `<p>` sibling) -- so a shell carrying
            # extra content would pass with that extra content silently
            # discarded. Every direct child, of whatever tag, is asserted
            # here; anything beyond exactly one section-typed div is fatal.
            shell_children = list(letter_div.iterchildren())
            shell_tags = [
                etree.QName(c).localname if isinstance(c.tag, str) else "<comment/PI>"
                for c in shell_children
            ]
            if (
                len(shell_children) != 1
                or shell_tags[0] != "div"
                or shell_children[0].get("type") != sch.section_div_type
            ):
                raise ValueError(
                    f"{manifest.work_id}: letter \"t\" shell has "
                    f"{len(shell_children)} direct child element(s) "
                    f"{list(zip(shell_tags, (c.get('type') for c in shell_children)))!r}, "
                    f"expected exactly one div of type {sch.section_div_type!r} "
                    f"and nothing else"
                )
            shell_text = _line_text(shell_children[0])
            observed_titles.append(
                _check_title_drop(shell_text, 'letter "t" shell', declared_titles, manifest)
            )
            # The shell always immediately precedes letter 1 — restore its
            # verified text as letter 1's heading (§C restore).
            pending_headings["1"] = shell_text
            continue

        if letter_n in declared_exclude:
            excluded_tokens.append(letter_n)
            continue

        if not (isinstance(letter_n, str) and letter_n.isdigit()):
            raise ValueError(
                f"{manifest.work_id}: unrecognized PHI letter n={letter_n!r} "
                f"— expected a plain digit string, the title marker 't', or "
                f"a token declared in citation.exclude_letters"
            )

        saw_salutation = False
        saw_section_1 = False
        for sec_div in letter_div.iter("{*}div"):
            if sec_div.get("type") != sch.section_div_type:
                continue
            n = sec_div.get("n")
            if n == "sa" and salutation_role:
                if saw_salutation:
                    raise ValueError(
                        f"{manifest.work_id}: letter {letter_n!r} has more "
                        f"than one section n=\"sa\" salutation"
                    )
                saw_salutation = True
                sal_text = _rejoin_wrapped_hyphens(_line_text(sec_div))
                if not sal_text:
                    # A silently-empty salutation used to just skip the
                    # `pending_salutations` write while `saw_salutation`
                    # stayed True -- passing the "has exactly one sa" check
                    # below while attaching nothing, so the letter's
                    # section 1 silently lost its salutation line. Fatal
                    # instead: a real "sa" div must carry text.
                    raise ValueError(
                        f"{manifest.work_id}: letter {letter_n!r} section "
                        f"n=\"sa\" salutation is empty — a real salutation "
                        f"div must carry text"
                    )
                pending_salutations[letter_n] = sal_text
                continue
            if n == "t":
                sec_text = _line_text(sec_div)
                observed_titles.append(
                    _check_title_drop(sec_text, f"letter {letter_n!r} section", declared_titles, manifest)
                )
                # Restore onto this same letter's section "1" (§C restore).
                pending_headings[letter_n] = sec_text
                continue
            if not (isinstance(n, str) and n.isdigit()):
                # Reachable for n="sa" too when `citation.salutation_role`
                # is not set (the flag gates the whole mechanism -- an
                # undeclared "sa" is just an ordinary unrecognized token,
                # never silently dropped).
                raise ValueError(
                    f"{manifest.work_id}: unrecognized PHI section n={n!r} "
                    f"in letter {letter_n!r} — expected a plain digit "
                    f"string, the salutation marker 'sa', or the title "
                    f"marker 't'"
                )
            if n == "1":
                saw_section_1 = True
            column = sch.compose_column(letter_n, n)
            text = _rejoin_wrapped_hyphens(_line_text(sec_div))
            if text:
                body.append({"column": column, "n": 1, "text": text, "_section_n": n, "_letter_n": letter_n})

        if salutation_role:
            if not saw_salutation:
                raise ValueError(
                    f"{manifest.work_id}: letter {letter_n!r} has no "
                    f"section n=\"sa\" salutation — every real "
                    f"(non-excluded) letter must carry exactly one"
                )
            if not saw_section_1:
                raise ValueError(
                    f"{manifest.work_id}: letter {letter_n!r} has a "
                    f"section n=\"sa\" salutation but no section \"1\" to "
                    f"attach it to"
                )

    _finalize_title_drops(observed_titles, declared_titles, manifest, "letter")
    _check_exclude_letters(declared_exclude, excluded_tokens, manifest)

    n_rejoins = _rejoin_cross_section_hyphens(body, manifest, same_book_required=True)
    _check_cross_section_rejoin_count(n_rejoins, manifest)

    flat: list[dict] = []
    for entry in body:
        letter_n, section_n = entry["_letter_n"], entry["_section_n"]
        is_section_1 = section_n == "1"
        heading_text = pending_headings.get(letter_n) if is_section_1 else None
        salutation_text = pending_salutations.get(letter_n) if is_section_1 else None
        # §C restore: a heading (when present) leads, ahead of any
        # salutation — every heading-bearing letter is also
        # salutation-bearing (headings only ever precede a real letter), so
        # in practice this is always heading, then salutation, then text.
        if heading_text:
            flat.append({"column": entry["column"], "n": 1, "text": heading_text, "role": "heading"})
        if salutation_text:
            flat.append({"column": entry["column"], "n": 1, "text": salutation_text, "role": "salutation"})
            flat.append({"column": entry["column"], "n": 2, "text": entry["text"]})
        else:
            flat.append({"column": entry["column"], "n": 1, "text": entry["text"]})
    return flat


# --------------------------------------------------------------------------
# Flat `section` scheme (Wave 2 Batch 3 round 2 — Cicero's Cato Maior, De
# Amicitia (Laelius), De Fato, Lucullus, Paradoxa Stoicorum; design note
# docs/wave2-batch3c-design.md §B.0): a sibling path within this module,
# same shape as the verse-line path below — a bookless PHI export whose
# citable div (`sch.page_div_type`, "section" after the `citation.
# div_types.page` override the manifest already declares for book-section)
# sits either directly at the top level (Cato Maior/Laelius/De Fato/
# Lucullus: no wrapper at all, verified against their real exports — the
# document's only div @type is "section") or nested one level inside a
# non-citable grouping div DECLARED by the manifest's `citation.flat_wrapper`
# (Paradoxa Stoicorum: each `<div type="paradox" n="pr|1..6">` wraps its own
# run of numbered `<div type="section">` children; the paradox axis is
# presentation only, per the design note, dropped here by never reading its
# @n at all — every column still comes straight off compose_column(section_n)).
#
# Depth scoping (adversarial-review Finding 3, replacing an earlier
# unconstrained any-depth walk that collected a section div wherever it sat
# in the tree — see git history for that version): `_collect_flat_section_
# candidates` below only accepts a section div that is a direct child of
# `<body>`, or — only when the manifest declares `citation.flat_wrapper:
# {div_type, n_tokens}` — a direct child of a declared-wrapper div (itself a
# direct child of `<body>`, whose own @n is in the declared token set). A
# section div anywhere else (double-nested, inside an undeclared wrapper
# type, or inside a wrapper carrying an undeclared @n) is FATAL: the total
# count of `sch.page_div_type` divs anywhere in the tree is cross-checked
# against the count found at these declared positions, so an escapee can
# neither be silently skipped nor silently swept in. Duplicate composed
# columns are likewise FATAL, checked before the cross-section hyphen-rejoin
# / fingerprint step below.
#
# Two title-drop shapes, both gated on the manifest's declared
# `citation.title_labels` multiset (`_check_title_drop`/
# `_finalize_title_drops`, shared with the book-section scheme above — not a
# separate character-class guard):
#   * a bare `n="t"` section div at a declared position — the whole-work
#     title for Cato Maior/Laelius/De Fato/Lucullus, and Paradoxa's own
#     per-paradox headings (one per paradox 1-6; each embeds a short Greek
#     quotation alongside its Latin label — mixed-script content a
#     Latin-only shape guard would have to special-case, but the
#     hash-declared mechanism does not care about script at all);
#   * Paradoxa's WHOLE-WORK title wrapper: `<div type="paradox" n="t">`
#     nests a numbered `<div type="section">` that would otherwise collide
#     with the real section of the same number living inside the sibling
#     `<div type="paradox" n="pr">` (the proem) — dropped by checking its
#     immediate (declared) wrapper's own `n="t"` (a no-op for every other
#     work in this batch, which declare no `citation.flat_wrapper` at all).


def _flat_wrapper_config(manifest: Manifest) -> tuple[str | None, set[str] | None]:
    """The manifest's declared `citation.flat_wrapper` (Finding 3's
    depth-scoping declaration) as `(div_type, n_tokens)`, or `(None, None)`
    for a work with no wrapper at all (Cato Maior/Laelius/De Fato/Lucullus —
    a bare top-level section spine). `n_tokens` is the allowed set of the
    wrapper div's own @n values (Paradoxa: the title wrapper "t", the proem
    "pr", and the six numbered paradoxes "1".."6") — a wrapper div at a
    declared position but carrying an UNDECLARED @n is fatal, never silently
    walked into or silently skipped."""
    raw = (manifest.data.get("citation") or {}).get("flat_wrapper")
    if raw is None:
        return None, None
    if not isinstance(raw, dict) or set(raw) != {"div_type", "n_tokens"}:
        raise ValueError(
            f"{manifest.work_id}: citation.flat_wrapper must be an object "
            f"with exactly the keys div_type and n_tokens"
        )
    div_type = raw["div_type"]
    n_tokens = raw["n_tokens"]
    if not isinstance(div_type, str) or not div_type:
        raise ValueError(f"{manifest.work_id}: citation.flat_wrapper.div_type must be a non-empty string")
    if not isinstance(n_tokens, list) or not n_tokens or not all(isinstance(t, str) and t for t in n_tokens):
        raise ValueError(
            f"{manifest.work_id}: citation.flat_wrapper.n_tokens must be a "
            f"non-empty list of non-empty strings"
        )
    return div_type, set(n_tokens)


def _collect_flat_section_candidates(tree, sch, manifest: Manifest) -> list[tuple]:
    """Every citable section div at a DECLARED position (Finding 3): a
    direct child of `<body>`, or a direct child of a declared `citation.
    flat_wrapper` div that itself sits directly under `<body>` with a
    declared @n. Returns `(sec_div, wrapper_div_or_None)` pairs in document
    order (the same relative order an any-depth `tree.iter` walk would have
    visited them in, since both `<body>`'s own children and each wrapper's
    own children are walked in their natural document order).

    Cross-checks the total count of `sch.page_div_type` divs ANYWHERE in the
    tree against the number found at these declared positions — a section
    div outside them (double-nested, an undeclared wrapper type, or an
    undeclared wrapper @n) is FATAL rather than silently skipped or silently
    included."""
    body = tree.find(".//{*}body")
    if body is None:
        raise ValueError(f"{manifest.work_id}: export has no <body>")
    wrapper_div_type, wrapper_n_tokens = _flat_wrapper_config(manifest)

    candidates: list[tuple] = []
    # `.iterchildren("{*}div")` (not a bare `for child in body`) — a spine
    # section or its wrapper must be an actual <div> element, not merely any
    # element carrying a matching @type. Without this tag check, a non-div
    # element (e.g. a stray milestone) carrying the declared wrapper's @type
    # would be treated as a legitimate wrapper and its section-div children
    # swept in as spine, without ever being rejected: the div children
    # themselves still count toward `total_anywhere` below (that count comes
    # from `tree.iter("{*}div")`, tag-scoped independently of ancestry), so
    # nothing would have caught the mismatch. Requiring the tag here instead
    # means such a section div is simply never collected as a candidate, so
    # it now correctly trips the total-count cross-check as an escapee.
    for child in body.iterchildren("{*}div"):
        ctype = child.get("type")
        if ctype == sch.page_div_type:
            candidates.append((child, None))
        elif wrapper_div_type is not None and ctype == wrapper_div_type:
            wn = child.get("n")
            if wn not in wrapper_n_tokens:
                raise ValueError(
                    f"{manifest.work_id}: {wrapper_div_type} div with "
                    f"undeclared n={wn!r} — expected one of citation."
                    f"flat_wrapper.n_tokens {sorted(wrapper_n_tokens)}"
                )
            for grandchild in child.iterchildren("{*}div"):
                if grandchild.get("type") == sch.page_div_type:
                    candidates.append((grandchild, child))

    total_anywhere = sum(1 for d in tree.iter("{*}div") if d.get("type") == sch.page_div_type)
    if total_anywhere != len(candidates):
        raise ValueError(
            f"{manifest.work_id}: found {total_anywhere} div(s) of type "
            f"{sch.page_div_type!r} in the export but only {len(candidates)} "
            f"sit at a declared position (a direct child of <body>, or of a "
            f"declared citation.flat_wrapper div) — an undeclared or nested "
            f"section div is fatal, never silently skipped or silently "
            f"included"
        )
    return candidates


def _check_exclude_sections(declared: set[str], observed_tokens: list[str], manifest: Manifest) -> None:
    """Cross-check `citation.exclude_sections` (De Fato's fr/fr1/fr2/fr3/fr5
    tail — design note-adjacent filter, Wave 2 Batch 3 round 2) against what
    `_parse_flat_section` actually observed and excluded: every declared
    token must have been observed EXACTLY ONCE (a re-export that drops,
    renumbers, or duplicates a declared exclusion fails loudly — a stale or
    now-ambiguous declaration, not silently kept or silently double-dropped)
    and every excluded token must have been declared (the walker only ever
    adds to `observed_tokens` when the token is already in `declared`, so
    this is a defensive invariant, not a reachable path today)."""
    counts = Counter(observed_tokens)
    stale = sorted(tok for tok in declared if counts.get(tok, 0) == 0)
    if stale:
        raise ValueError(
            f"{manifest.work_id}: citation.exclude_sections declares "
            f"{stale} but the export does not contain that section token "
            f"exactly once — stale declaration; a re-export dropped or "
            f"renumbered it, fix the manifest rather than keeping a dead "
            f"entry"
        )
    duplicated = sorted(tok for tok in declared if counts.get(tok, 0) > 1)
    if duplicated:
        raise ValueError(
            f"{manifest.work_id}: citation.exclude_sections token(s) "
            f"{duplicated} occur more than once in the export — expected "
            f"each declared exclusion exactly once"
        )


def _parse_flat_section(tree, sch, manifest: Manifest) -> list[dict]:
    """Flat (column, n=1, text) list for PHI's flat, bookless `section`-
    scheme export — see the module-doc block just above this function for
    the declared depth-scoping (Finding 3) and title-drop (Finding 2)
    mechanisms, and `_collect_flat_section_candidates` for the position
    enumeration itself.

    A non-digit, non-"t" section `n` is a loud ValueError UNLESS it is
    declared in the manifest's `citation.exclude_sections` (De Fato's
    fragment tail: "fr", "fr1", "fr2", "fr3", "fr5") — see
    `_check_exclude_sections`, called once after the walk with every
    excluded token actually observed. A duplicate composed column is a loud
    ValueError, checked as each column is composed — before the
    cross-section hyphen-rejoin / fingerprint step below ever sees it.

    Reuses `_line_text`/`_rejoin_wrapped_hyphens` unchanged (book-section
    precedent) and `_rejoin_cross_section_hyphens` with
    `same_book_required=False` (this scheme has no book axis at all — see
    that function's own doc comment for why the boundary check doesn't
    apply here), cross-checked the same way via
    `_check_cross_section_rejoin_count`."""
    declared_titles = _load_declared_title_labels(manifest)
    observed_titles: list[str] = []
    flat: list[dict] = []
    seen_columns: set[str] = set()
    excluded_tokens: list[str] = []
    declared_exclude = set((manifest.data.get("citation") or {}).get("exclude_sections") or [])

    for sec_div, wrapper in _collect_flat_section_candidates(tree, sch, manifest):
        n = sec_div.get("n")

        # Title-wrapper drop (Paradoxa only — see module-doc block above):
        # the section's own declared-position wrapper carries n="t".
        if wrapper is not None and wrapper.get("n") == "t":
            observed_titles.append(
                _check_title_drop(
                    _line_text(sec_div), f'{wrapper.get("type")} n="t" wrapper', declared_titles, manifest
                )
            )
            continue

        if n == "t":
            context = f'{wrapper.get("type")} {wrapper.get("n")!r} section' if wrapper is not None else "section"
            observed_titles.append(_check_title_drop(_line_text(sec_div), context, declared_titles, manifest))
            continue
        if not (isinstance(n, str) and n.isdigit()):
            if n in declared_exclude:
                excluded_tokens.append(n)
                continue
            raise ValueError(
                f"{manifest.work_id}: unrecognized PHI section n={n!r} — "
                f"expected a plain digit string, the title marker 't', or "
                f"a token declared in citation.exclude_sections"
            )
        column = sch.compose_column(n)
        if column in seen_columns:
            raise ValueError(
                f"{manifest.work_id}: duplicate section column {column!r} "
                f"in the flat spine — refusing to silently fingerprint "
                f"colliding columns"
            )
        seen_columns.add(column)
        text = _rejoin_wrapped_hyphens(_line_text(sec_div))
        if text:
            flat.append({"column": column, "n": 1, "text": text})

    _finalize_title_drops(observed_titles, declared_titles, manifest, "flat-section")
    _check_exclude_sections(declared_exclude, excluded_tokens, manifest)

    n_rejoins = _rejoin_cross_section_hyphens(flat, manifest, same_book_required=False)
    _check_cross_section_rejoin_count(n_rejoins, manifest)
    return flat


# --------------------------------------------------------------------------
# Verse (Wave 2 Batch 2 — Lucretius' DRN, `verse-line` scheme): a sibling
# path within this module rather than a separate stage1_latin_verse.py file
# (smallest faithful change — book-section's helpers above, `_line_text`/
# `_check_sourcedesc`/`_is_latin_letter`, are reused as-is; only the div walk
# and per-line classification differ). PHI's DRN export nests flat
# `<l n="…">` line divs directly under `<div type="book" n="1..6">` — no
# section level at all, unlike book-section's book>section nesting (see
# scheme.py's verse-line module-doc entry). Two title lines per book
# (`<l n="t">`/`<l n="t2">`, each wrapping a nested `<label>`) are dropped as
# non-citable front matter, exactly like book-section's dropped `n="t"`
# divs — verified against the real export (phi0550001.xml): every book
# opens with exactly this pair (the work's own title line, and a per-book
# heading line), the same two-line shape as book-section's dropped
# whole-work-title/per-book-title divs, one level down at <l> instead of
# <div>. Gated on the manifest's declared `citation.title_labels` multiset
# (`_check_title_drop`/`_finalize_title_drops`, shared with the
# book-section/flat-section schemes above), accumulated across ALL six
# books and cross-checked once at the very end of `_parse_verse` below —
# unlike book-section/flat-section, this scheme's declared list spans the
# whole work rather than resetting per book (the title line's own text
# repeats verbatim across books, e.g. the work's title line, so the same
# hash legitimately recurs multiple times in the declaration).


def _assert_l_title_is_label_only(l_el: etree._Element, n: str, book_n: str, declared: list[str], manifest: Manifest) -> str:
    """The l-level analogue of `_check_title_drop` above: a dropped
    `n="t"`/`n="t2"` verse line must nest a `<label>` child (never a bare
    title with no element wrapper) — a structural shape check kept as-is —
    and its flattened text's content hash must be declared in `citation.
    title_labels`, exactly like the book-section/flat-section title-drop
    gate. Returns the content hash on success, for the caller to accumulate
    and cross-check via `_finalize_title_drops`."""
    if l_el.find("{*}label") is None:
        raise ValueError(
            f"{manifest.work_id}: book {book_n!r} <l n={n!r}> title line "
            f"has no nested <label> child — refusing to silently drop what "
            f"may be substantive content"
        )
    return _check_title_drop(_line_text(l_el), f"book {book_n!r} <l n={n!r}> title line", declared, manifest)


# Editor-marked lacuna content ("* * *", asterisks with any interleaved
# whitespace) — the CONTENT signal `verse-line`'s lacuna role is assigned
# by (design delta over the wave2-latin-design.md §3.2 memo, adjudicated by
# the orchestrator): a line whose flattened text is ONLY this shape is a
# lacuna regardless of whether its own `n` is an ordinary lettered-suffix
# token ("860a") or the one PHI range token ("1094-1101") — NOT by token
# shape alone, since a genuine bracketed editorial insertion with real text
# (3.672a) also carries a lettered suffix but is ordinary verse. An empty
# string never matches (`+` requires >=1 char), so a line with no text at
# all is a data bug, not silently treated as a lacuna.
_LACUNA_TEXT_RE = re.compile(r"^[*\s]+$")


def _verse_lineref_order_key(lineref: str) -> tuple[int, str]:
    """Sort key for a document-order transposition scan: a plain lineref via
    `scheme_mod.verse_line_order_key`; the one PHI range token
    ("1094-1101") has no single citable position, so it sorts at its START
    line — mirrors refs.py's identically-reasoned `_verse_line_lineref_key`
    (duplicated rather than imported: this module has no other dependency
    on refs.py, and it is a two-line helper)."""
    if scheme_mod.verse_line_kind(lineref) == "range":
        lineref = lineref.split("-", 1)[0]
    return scheme_mod.verse_line_order_key(lineref)


def _derive_transposed_blocks(doc_linerefs: list[str]) -> list[dict]:
    """Mechanically derive the transposed blocks from a book's DOCUMENT-order
    lineref sequence (design memo §3.3's "editors reprint transposed blocks
    under their original line numbers, so document order != citation
    order"): a maximal run of consecutive document-order entries whose
    citation-order key is LESS than the running maximum already seen is a
    block transmitted out of numeric sequence — it is printed here, in the
    manuscript's transmitted position, immediately after the higher-numbered
    line that is its "before" anchor. The running maximum does not advance
    across a block (the block's own keys are, by construction, all below
    it), so line numbering resumes correctly once the block ends.

    Each entry is `{"start": lineref, "end": lineref, "before": lineref}` —
    `start`/`end` bound the (possibly single-line) block in DOCUMENT order
    (which is also numeric order within the block, since the run is
    required to stay strictly ascending), `before` is the document-order
    predecessor the block is transmitted after. Verified against the real
    DRN export: reproduces every worked example in the recon brief exactly
    (book 1's "14" after "15" and "50..61" after "135"; book 6's "48..91"
    after "95a"; book 4's 12-block count)."""
    blocks: list[dict] = []
    running_max_key: tuple[int, str] | None = None
    running_max_ref: str | None = None
    i, n = 0, len(doc_linerefs)
    while i < n:
        ref = doc_linerefs[i]
        key = _verse_lineref_order_key(ref)
        if running_max_key is not None and key < running_max_key:
            start = ref
            before = running_max_ref
            j = i
            cur_key = key
            while j + 1 < n:
                nxt = doc_linerefs[j + 1]
                nkey = _verse_lineref_order_key(nxt)
                if nkey < running_max_key and nkey > cur_key:
                    j += 1
                    cur_key = nkey
                    continue
                break
            blocks.append({"start": start, "end": doc_linerefs[j], "before": before})
            i = j + 1
            continue
        running_max_key = key
        running_max_ref = ref
        i += 1
    return blocks


def _transposition_seam_note(start: str, end: str, before: str) -> str:
    """The auto-generated seam note for one transposed block (design memo
    §3.3: "a small inline note at the seam ... records the fact"). ONE
    place the wording lives so it can be retuned later without hunting call
    sites — exact wording is provisional pending John's review (per the
    orchestrator's lacuna/transposition design delta), the way the memo's
    own example note text is flagged provisional."""
    span = start if start == end else f"{start}–{end}"
    plural = "" if start == end else "s"
    return f"Line{plural} {span} transmitted after line {before} in this edition."


def _parse_verse(tree, sch, manifest: Manifest) -> list[dict]:
    """Flat (book, lineref, column, text, role[, seam_note]) list for PHI's
    verse-line export, in DOCUMENT order (never re-sorted here — the
    citation-order sort is emit-time, stage7_emit's job, per design memo
    §3.3: "never key lookup or anchors off file position" until the very
    last, presentation-only step).

    Two fail-loud gates run per book, mirroring the cross_section_rejoins
    re-export-drift tripwire De Officiis' book-section parser already
    established:
      * lacuna declaration (bidirectional): every line/range token this
        walk classifies `role="lacuna"` (by CONTENT, not token shape — see
        `_LACUNA_TEXT_RE`'s doc comment) must be declared in the manifest's
        `citation.lacunae[book]`, and every declared token must actually be
        observed — a re-export that drops, adds, or misclassifies a lacuna
        fails loudly instead of silently drifting.
      * transposition declaration: REQUIRED (adversarial-review blocker —
        an absent `citation.transpositions` used to fail OPEN, skipping
        the cross-check entirely). Every book in the spine must carry an
        entry in the manifest's `citation.transpositions` — an explicit
        empty list is fine once verified to have no transposed blocks,
        but omission (of the whole key, or of one book's entry) is now a
        hard build error, not a silent no-op. Where a book does declare
        one, the block list `_derive_transposed_blocks` computes from
        that book's document order must match it exactly."""
    declared_lacunae: dict[str, set[str]] = {
        str(k): set(v) for k, v in ((manifest.data.get("citation") or {}).get("lacunae") or {}).items()
    }
    declared_transpositions = (manifest.data.get("citation") or {}).get("transpositions")
    if declared_transpositions is None:
        raise ValueError(
            f"{manifest.work_id}: citation.transpositions is required for a "
            f"verse-line work — declare a per-book list (an explicit empty "
            f"list is fine once verified to have no transposed blocks) for "
            f"every book in the spine; omission is a fail-open hazard, not "
            f"a supported bootstrapping state"
        )
    declared_titles = _load_declared_title_labels(manifest)
    observed_titles: list[str] = []

    flat: list[dict] = []
    for book_div in tree.iter("{*}div"):
        if book_div.get("type") != sch.page_div_type:
            continue
        book_n = book_div.get("n")
        if not (isinstance(book_n, str) and book_n.isdigit()):
            raise ValueError(
                f"{manifest.work_id}: unrecognized PHI verse book n={book_n!r} "
                f"— expected a plain digit string"
            )
        book = int(book_n)
        doc_linerefs: list[str] = []
        found_lacunae: set[str] = set()
        book_entries: list[dict] = []
        for l_el in book_div.iter("{*}l"):
            n = l_el.get("n")
            if n in ("t", "t2"):
                observed_titles.append(_assert_l_title_is_label_only(l_el, n, book_n, declared_titles, manifest))
                continue
            kind = scheme_mod.verse_line_kind(n)  # fails loudly on a malformed n
            text = _line_text(l_el)
            if text and len(text) >= 2 and text[-1] == "-" and _is_latin_letter(text[-2]):
                raise ValueError(
                    f"{manifest.work_id}: book {book_n} line {n!r} ends in "
                    f"an apparent hyphenated wrap ({text!r}) — verse-line "
                    f"has no hyphen-rejoin path; a wrap would be a new "
                    f"phenomenon in this export, investigate before adding "
                    f"one rather than silently emitting the truncated line"
                )
            is_gap_content = bool(_LACUNA_TEXT_RE.match(text))
            if kind == "range":
                if not is_gap_content:
                    raise ValueError(
                        f"{manifest.work_id}: book {book_n} range token "
                        f"{n!r} carries non-gap content ({text!r}) — every "
                        f"range-form PHI token observed so far is an "
                        f"editorial lacuna marker; investigate before "
                        f"treating this one as ordinary verse"
                    )
                role = "lacuna"
            else:
                role = "lacuna" if is_gap_content else "text"
            if role == "lacuna":
                found_lacunae.add(n)
            doc_linerefs.append(n)
            entry = {
                "book": book,
                "lineref": n,
                "column": sch.compose_column(book_n, n),
                "text": "" if role == "lacuna" else text,
                "role": role,
            }
            flat.append(entry)
            book_entries.append(entry)

        declared = declared_lacunae.get(book_n, set())
        undeclared = found_lacunae - declared
        stale = declared - found_lacunae
        if undeclared or stale:
            raise ValueError(
                f"{manifest.work_id}: book {book_n} lacuna declaration "
                f"mismatch against citation.lacunae — undeclared (observed "
                f"but not declared): {sorted(undeclared) or 'none'}; stale "
                f"(declared but not observed): {sorted(stale) or 'none'}"
            )

        observed_blocks = _derive_transposed_blocks(doc_linerefs)
        if book_n not in declared_transpositions:
            raise ValueError(
                f"{manifest.work_id}: book {book_n} has no citation."
                f"transpositions declaration — every book in the spine "
                f"must declare one (an explicit empty list is fine once "
                f"verified to have no transposed blocks; omission is not)"
            )
        declared_blocks = declared_transpositions[book_n]
        if declared_blocks != observed_blocks:
            raise ValueError(
                f"{manifest.work_id}: book {book_n} transposition "
                f"mismatch against citation.transpositions — observed "
                f"{observed_blocks!r} but manifest declares "
                f"{declared_blocks!r}"
            )
        seam_by_start = {
            b["start"]: _transposition_seam_note(b["start"], b["end"], b["before"])
            for b in observed_blocks
        }
        for entry in book_entries:
            note = seam_by_start.get(entry["lineref"])
            if note:
                entry["seam_note"] = note

    _finalize_title_drops(observed_titles, declared_titles, manifest, "verse-line")
    return flat


def _parse_spine_verse(xml_path: Path, manifest: Manifest, sch) -> dict:
    """`parse_spine`'s verse-line counterpart: each citable `<l>` becomes its
    own segment (mirrors book-section's one-segment-per-section shape, with
    a single synthetic line entry `n=1`, since the column — not a
    within-column line — IS the citable unit here too, `lines_user_facing:
    False`). Segments are emitted in DOCUMENT order (stage7_emit sorts them
    into citation order at emit time — see that module's doc comment)."""
    tree = etree.parse(str(xml_path))
    _check_sourcedesc(tree, manifest, xml_path)
    flat = _parse_verse(tree, sch, manifest)

    segments: list[dict] = []
    for entry in flat:
        line: dict = {"n": 1, "text": entry["text"]}
        if entry["role"] == "lacuna":
            line["role"] = "lacuna"
        if "seam_note" in entry:
            line["seam_note"] = entry["seam_note"]
        segments.append(
            {
                "id": f"{entry['book']}:{entry['column']}",
                "book": entry["book"],
                "column": entry["column"],
                "lines": [line],
            }
        )

    return {
        "work": manifest.work_id,
        "edition": manifest.data["work"]["latin_edition"],
        "segments": segments,
        "headings": [],
        "unassigned_lines": [],
    }


def parse_spine(xml_path: Path, manifest: Manifest) -> dict:
    sch = scheme_mod.for_manifest(manifest)
    if sch.verse_line_scheme:
        return _parse_spine_verse(xml_path, manifest, sch)
    tree = etree.parse(str(xml_path))
    _check_sourcedesc(tree, manifest, xml_path)
    # Flat `section` scheme (Wave 2 Batch 3 round 2 — Cato Maior/Laelius/De
    # Fato/Lucullus/Paradoxa): bookless, so every column is assigned to the
    # work's single declared book (1) directly, with no manifest book-table
    # lookup at all — mirrors stage1_greek.parse_spine's identically-reasoned
    # flat_numeric branch (a bare-integer column carries no book-boundary
    # grammar for `manifest.book_for_column` to parse).
    #
    # `letter` (Wave 2 Seneca — Epistulae Morales, design note §A/G): a
    # book-section-shaped dotted scheme like the default branch below (a
    # 124-entry manifest book table, one per letter, drives the ordinary
    # `book_for_column` lookup — no flat_numeric special-case needed), but
    # dispatches to `_parse_letters` for the salutation-fold/title-drop/
    # fr-exclusion deltas §B-D describe.
    if sch.letter_scheme:
        flat = _parse_letters(tree, sch, manifest)
    elif sch.flat_numeric:
        flat = _parse_flat_section(tree, sch, manifest)
    else:
        flat = _parse_book_section(tree, sch, manifest)

    segments: list[dict] = []
    seg_by_key: dict[tuple, dict] = {}
    unassigned: list[dict] = []
    for line in flat:
        book = 1 if sch.flat_numeric else manifest.book_for_column(line["column"])
        if book is None:
            unassigned.append(line)
            continue
        key = (book, line["column"])
        seg = seg_by_key.get(key)
        if seg is None:
            seg = {
                "id": f"{book}:{line['column']}",
                "book": book,
                "column": line["column"],
                "lines": [],
            }
            seg_by_key[key] = seg
            segments.append(seg)
        # `role` (letter's salutation fold, §B) passes through only when
        # present — every pre-existing book-section/flat-section caller's
        # `line` dict carries no "role" key at all, so this stays
        # byte-identical for them (the same additive-passthrough shape
        # stage7_emit.py already uses for dk's context role and verse-line's
        # seam_note).
        seg["lines"].append({
            "n": line["n"],
            "text": line["text"],
            **({"role": role} if (role := line.get("role")) else {}),
            **({"joined": True} if line.get("joined") else {}),
            **({"wrap": line["wrap"]} if "wrap" in line else {}),
            **({"wrapO": line["wrapO"]} if "wrapO" in line else {}),
            **({"indent": line["indent"]} if "indent" in line else {}),
        })

    return {
        "work": manifest.work_id,
        "edition": manifest.data["work"]["latin_edition"],
        "segments": segments,
        "headings": [],
        "unassigned_lines": unassigned,
    }


def run(manifest: Manifest) -> Path:
    xml_path = run_export(manifest)
    spine = parse_spine(xml_path, manifest)
    out = BUILD_DIR / "stage1" / "latin_spine.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spine, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
