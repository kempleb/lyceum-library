"""Stage 1a: TLG Greek spine via Diogenes verse-mode export.

Parses the verse-mode TEI (Bekker-page divs containing <l n="..."> lines),
rejoins words hyphenated across lines onto the first line, assigns each line
to a book from the manifest table, and emits spine segments keyed
(book, column) so book-straddling columns split into per-book segments.
"""

from __future__ import annotations

import copy
from functools import partial
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from lxml import etree

from . import dk_lang
from . import scheme as scheme_mod
from .config import BUILD_DIR, SOURCES_DIR, Manifest
from .lined import (
    LinedAlphabet,
    _LINE_INDENT_RE,
    _SECTION_N_RE,
    _apply_lined_cross_column_wraps as _apply_lined_cross_column_wraps_impl,
    _apply_lined_wraps as _apply_lined_wraps_impl,
    _fold_hyphen_final_sigma,
    _lined_chapter_lines as _lined_chapter_lines_impl,
    _warn_if_lined_source_has_no_wraps as _warn_if_lined_source_has_no_wraps_impl,
    _word_start as _word_start_impl,
)

EXPORT_DIR = BUILD_DIR / "export"


def exported_xml_path(manifest: Manifest) -> Path:
    w = manifest.data["work"]
    return (
        EXPORT_DIR
        / "Diogenes-Resources"
        / "xml"
        / "tlg"
        / f"tlg{w['tlg_author']}{w['tlg_work']}.xml"
    )


def run_export(manifest: Manifest) -> Path:
    """Run Diogenes xml-export.pl in verse mode (-y) unless already done."""
    out = exported_xml_path(manifest)
    if out.exists():
        return out
    w = manifest.data["work"]
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "perl",
            "xml-export.pl",
            "-c", "tlg",
            "-n", w["tlg_author"],
            "-y",
            "-o", str(EXPORT_DIR),
        ],
        cwd=manifest.diogenes_server(),
        env={"TLG_DIR": str(manifest.tlg_dir()), "PATH": "/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )
    if not out.exists():
        raise FileNotFoundError(f"export ran but {out} is missing")
    return out


def _line_text(el: etree._Element, strip_bars: bool = False, extra_strip_chars: str = "") -> str:
    """Flatten an <l>, dropping heading labels, collapsing whitespace.

    `strip_bars` removes literal "|" edition line-break markers, which some
    exports (e.g. De Mundo's) print inside a plain <l> — mid-word (καλοῦν|ται)
    or between words (μέσον | μὲν); the bar is never part of a Greek word.
    It must stay FALSE on compound-numbered lines (n="8,9"), where "|" is the
    delimiter _expand_compound splits on to map the physical line onto its two
    Bekker numbers — stripping it there would destroy the split.

    `extra_strip_chars` (Sol blocker S3, replacing an earlier unconditional
    module-level constant that used to fire for every scheme/work in the
    whole pipeline): every character in this string is dropped outright,
    same as a bar. Defaults to "" (no-op) for every ordinary call site —
    only `_dk_clean_line_text` passes a manifest-declared value (this
    work's own `citation.export_artifact_chars`), so a confirmed export
    artifact verified against exactly one work's exactly one character
    (e.g. Empedocles' U+1017C GREEK OBOL SIGN glued onto "ὁρῶντα" in
    B109a, div n="109a" line 3, "ἐπὶ τὸν ὁρῶντα𐅼.") is scoped to that
    work + character, not silently applied corpus-wide to every other
    work's every line on the strength of one div's evidence."""
    text = "".join(el.itertext())
    if strip_bars:
        text = text.replace("|", "")
    for ch in extra_strip_chars:
        text = text.replace(ch, "")
    return re.sub(r"\s+", " ", text).strip()


def _is_greek_letter(ch: str) -> bool:
    """True when `ch` is a Greek LETTER of any accentuation. Mirrors
    stage3_tokenize.py's identically-named helper (duplicated rather than
    imported: the two stages have no other coupling, and this is a ~5-line
    pure function)."""
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK") and unicodedata.category(ch).startswith("L")


# `_fold_hyphen_final_sigma` itself now lives in lined.py (2026-08-30
# cross-script wrap fix -- see that module's own comment): the wrap
# machinery applies it universally to both alphabets, not just Greek's own.
# Re-imported above (not redefined here) for this module's OTHER, non-lined-
# machinery call sites below (~line 190, ~1550, ~2875 -- the DK-block-merge
# and flat-hyphen-join paths, which are not part of the lined machinery and
# stay Greek-only by their own explicit `_is_greek_letter` guards).

GREEK_LINED = LinedAlphabet(
    is_letter=_is_greek_letter,
    fold_wrap_final=_fold_hyphen_final_sigma,
    name="greek",
    # Empty: Greek's own glued line-start punctuation (a curly opening
    # quote, U+2018) IS stripped by stage3_tokenize._surface()'s _PUNCT
    # edge-trim, so lined.py's fragment-start advance keeps skipping past
    # it, unchanged (the 17-locus Discourses quote fix this depends on).
    frag_start_glued_chars="",
)

# Keep the old Greek-module names for test and caller compatibility. Stage-1
# production call sites below still pass the policy explicitly.
_lined_chapter_lines = partial(_lined_chapter_lines_impl, alphabet=GREEK_LINED)
_apply_lined_wraps = partial(_apply_lined_wraps_impl, alphabet=GREEK_LINED)
_apply_lined_cross_column_wraps = partial(
    _apply_lined_cross_column_wraps_impl, alphabet=GREEK_LINED
)
_warn_if_lined_source_has_no_wraps = partial(
    _warn_if_lined_source_has_no_wraps_impl, alphabet=GREEK_LINED
)
_word_start = partial(_word_start_impl, alphabet=GREEK_LINED)


def _rejoin_wrapped_hyphens_mapped(text: str) -> tuple[str, list[int]]:
    """Same rejoin rule as `_rejoin_wrapped_hyphens` (see its docstring for
    the exact match shape), but also returns `old_to_new`: a length
    len(text)+1 list where old_to_new[i] is the char index in the returned
    text that source index i maps onto. A character consumed by the rejoin
    (the hyphen itself, or an absorbed run of spaces) maps to the join
    point — the index immediately following the word fragment it used to
    separate. old_to_new[len(text)] is always len(new_text), so an offset
    sitting at the very end of `text` maps cleanly too.

    Used by `_chapter_sections` to remap pre-rejoin TLG-section-start
    offsets onto the chapter's final (post-rejoin) text -- see that
    function's docstring for why some remapped offsets land mid-word (a
    print-line hyphen wrap straddling a section boundary) and must be
    dropped rather than rendered as a paragraph break."""
    out: list[str] = []
    old_to_new: list[int] = [0] * (len(text) + 1)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and i > 0 and _is_greek_letter(text[i - 1]):
            j = i + 1
            while j < n and text[j] == " ":
                j += 1
            if j > i + 1 and j < n and _is_greek_letter(text[j]) and text[j].islower():
                # Fold the whole pre-hyphen fragment in place. The fold is
                # length-preserving, so `old_to_new` needs no adjustment.
                if out:
                    out = list(_fold_hyphen_final_sigma("".join(out)))
                for k in range(i, j):
                    old_to_new[k] = len(out)
                i = j
                continue
        old_to_new[i] = len(out)
        out.append(ch)
        i += 1
    old_to_new[n] = len(out)
    return "".join(out), old_to_new


def _rejoin_wrapped_hyphens(text: str) -> str:
    """Rejoin TLG print-line hyphenation that survives as a literal
    "- " inside a chapter-flattened text (numeric_section / flat_numeric
    schemes flatten a whole chapter's <l> lines in one `_line_text()` shot,
    so the per-line cross-line hyphen rejoin below in parse_spine() never
    sees these lines to stitch — CLAUDE.md defect A). `text` is assumed
    already whitespace-collapsed by `_line_text` (every run of whitespace is
    exactly one U+0020 space), so only that single-space shape needs
    handling here.

    Only the ASCII hyphen-minus U+002D is a wrap candidate (verified against
    the actual corpus data) — U+2014 EM DASH, which glues Discourses'
    dialogue turns together (" — "), is a different codepoint and is never
    touched. A candidate hyphen must be directly preceded by a Greek letter
    and, after the run of spaces, directly followed by a LOWERCASE Greek
    letter — the unambiguous shape of a word broken across a print line. A
    hyphen followed by an uppercase letter or by punctuation does not match
    that shape (it could be a deliberate morpheme-boundary citation, as
    stage3_tokenize.py's _PUNCT comment documents for a different corpus) and
    is left untouched, not silently joined."""
    return _rejoin_wrapped_hyphens_mapped(text)[0]


def _chapter_sections(stripped_chap_div, final_text: str) -> tuple[list[dict], list[dict]]:
    """Per-TLG-section standoff offsets `[{n, o}]` into a chapter's flattened,
    hyphen-rejoined `final_text` (the exact string emitted as the chapter's
    one synthetic Greek line) — John's ruling 2026-07-16: Schenkl's Greek
    sub-chapter section divisions are the default paragraphing wherever TLG
    carries them. Shared by Discourses (book-section scheme, title div
    already excluded by `_strip_title_section` before this is called) and
    Enchiridion (flat `section` scheme, no title div at all — see
    `_parse_flat_chapter`).

    Walks `stripped_chap_div`'s direct <div type="section" n="N"> children in
    document order.
    Each section's own `_line_text` output, joined with a single space, is
    verified — corpus-wide, all 95 chapters — to reproduce
    `_line_text(stripped_chap_div)` byte-for-byte, so the pre-rejoin offset
    of each section's start is well-defined. Those offsets are then remapped
    through `_rejoin_wrapped_hyphens_mapped`'s old_to_new table onto
    `final_text` (the SAME rejoin already applied to produce it).

    Schenkl's print-line wraps do not respect TLG's section numbering: a
    hyphenated word can straddle a section boundary. Ground-truth adjudication
    against the real Discourses TLG XML (2026-07-16, all 618 corpus-wide
    occurrences, spread across all 4 books, individually inspected) found
    EVERY one is a genuine print-line straddle -- the preceding section's
    last physical <l> ends in Schenkl's wrap hyphen and the next section's
    first physical <l> opens with the bare continuation -- never an
    offset-remap bug (independently confirmed: the remap's old_to_new table
    was also verified correct for all 2015 non-straddling boundaries in the
    same run, via an offset-independent check that the mapped position's
    following characters equal the section's own first source word). The
    ~23.5% corpus-wide rate is fully explained by the base rate: ~25.8% of
    ALL physical lines in Schenkl's narrow Teubner column end in a wrap
    hyphen, and a section boundary's position is uncorrelated with line-wrap
    position, so roughly one boundary in four coincidentally lands on one.

    The whole-text rejoin fuses such a boundary's start directly onto the end
    of the PRECEDING section's last word, so the remapped offset lands
    mid-word. Rendering a paragraph break there would split a Greek token
    (forbidden — see Reader.svelte's splitGreekSections), so any offset that
    remaps mid-word is SNAPPED BACK (via `_word_start`) to the start of the
    straddling word rather than dropped: that word becomes the opening word
    of the NEW section's paragraph — matching how a Loeb marginal number
    sits at the wrapped line. No boundary is ever dropped. Returns
    `(kept, snapped)`: `kept` carries every section's boundary, in order;
    `snapped` is the subset of `kept` whose offset was adjusted this way (a
    strict subset also present, already snapped, in `kept`) — for the
    pipeline run's report only.

    One further anomaly, resolved here rather than reported: Discourses
    2.13 has Schenkl's single merged section n="25,26" (one printed section
    covering two Loeb-numbered sections) — the only non-integer section @n
    in the whole work. Recorded under its first number (25); English's
    every-5th-section marker scheme (see stage1_book_section_english.py's
    paras sidecar) happens to anchor at 25 too, so this does not break the
    English/Greek subset validation."""
    pre_entries: list[tuple[int, int]] = []
    cum = ""
    for child in stripped_chap_div:
        if etree.QName(child).localname != "div" or child.get("type") != "section":
            continue
        n_raw = child.get("n")
        if n_raw == "t":
            continue
        m = _SECTION_N_RE.match(n_raw or "")
        if not m:
            raise ValueError(f"unrecognized TLG section @n={n_raw!r}")
        n = int(m.group(1))
        t = _line_text(child)
        if not t:
            continue
        o = len(cum) + (1 if cum else 0)
        cum = f"{cum} {t}" if cum else t
        pre_entries.append((n, o))
    if len(pre_entries) < 2:
        return [], []
    rejoined, old_to_new = _rejoin_wrapped_hyphens_mapped(cum)
    if rejoined != final_text:
        raise ValueError(
            "TLG section-offset flatten does not match the chapter's own "
            "hyphen-rejoined text -- per-section concatenation drifted "
            "from _line_text(stripped_chap_div)"
        )
    kept: list[dict] = []
    snapped: list[dict] = []
    prev_o, prev_n = -1, -1
    for n, o in pre_entries:
        no = old_to_new[o]
        midword = (
            0 < no < len(final_text)
            and final_text[no - 1].isalpha() and final_text[no].isalpha()
        )
        if midword:
            no = _word_start(final_text, no, alphabet=GREEK_LINED)
        if no <= prev_o or n <= prev_n:
            raise ValueError(
                f"non-ascending TLG section offsets: n={n} o={no} "
                f"after prior n={prev_n} o={prev_o}"
            )
        entry = {"n": n, "o": no}
        kept.append(entry)
        if midword:
            snapped.append(entry)
        prev_o, prev_n = no, n
    return kept, snapped


def _lined_source_declared(manifest) -> bool:
    """Whether this work's manifest opts into per-print-line Greek emission
    (`citation.lined_source`, Discourses only — docs/lined-source-plan.md)
    instead of `_parse_flat_book_section`'s default one-flat-entry-per-
    chapter flatten. Mutually exclusive in practice with `section_paragraphs`
    (the `sections` standoff channel `lined_source` replaces for the one work
    that ever carried it, per that plan's Q4) — a lined chapter never calls
    `_chapter_sections` and never emits a `sections` key (I5)."""
    return bool(manifest is not None and manifest.data.get("citation", {}).get("lined_source"))


def _lined_section_div(manifest) -> str | None:
    """`citation.lined_section_div` is the R1a tri-state switch from
    docs/lined-wave2-plan.md: absent (`None`) means the column div is the leaf,
    while Discourses declares `"section"` so `_lined_chapter_lines` walks the
    nested section divs and stamps their @n onto each line as `sec`. A dedicated
    key rather than a reuse of `citation.div_types.section`
    on purpose — the latter mutates the shared `Scheme` dataclass, read by
    several other call sites, whereas this key's blast radius is one
    function."""
    return (
        manifest.data.get("citation", {}).get("lined_section_div")
        if manifest is not None else None
    )


def _lined_cross_column_wraps_declared(manifest) -> int | None:
    """The declared cross-column rejoin count, or ``None`` when absent."""
    if manifest is None:
        return None
    citation = manifest.data.get("citation", {})
    if "lined_cross_column_wraps" not in citation:
        return None
    return citation["lined_cross_column_wraps"]


def _apply_declared_lined_cross_column_wraps(
    flat: list[dict], manifest, declared: int | None
) -> None:
    if declared is None:
        return
    actual = _apply_lined_cross_column_wraps(flat, alphabet=GREEK_LINED)
    work_id = manifest.work_id if manifest is not None else "<unknown>"
    if actual != declared:
        raise ValueError(
            f"{work_id}: citation.lined_cross_column_wraps mismatch: "
            f"declared {declared}, actual {actual}"
        )



_COMPOUND_N = re.compile(r"^\d+(?:\s*,\s*\d+)+$")


def _line_no(n: str | None) -> int | None:
    """The Bekker line number of a plain-numeral <l n="…">, or None otherwise
    (a heading label or a compound range, both handled by the caller)."""
    if n and n.isdigit():
        return int(n)
    return None


def _expand_compound(items: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """Reconstruct true Bekker lines from a run of compound-numbered physical
    lines. In a few places Ross's OCT prints one physical line that straddles
    two Bekker lines, tagging it with both numbers (n="8,9") and an in-line `|`
    at the internal break (seen only at APo 99b8-14). For each physical line we
    rejoin a word the break splits (καθόλου πρῶ|τον → πρῶτον, kept whole on the
    earlier line, as with hyphenation), then split the remainder at word-boundary
    `|`s and map the pieces onto the line's Bekker numbers. Pieces that share a
    Bekker number across adjacent physical lines are concatenated, so every
    Bekker line is recovered exactly once and in order."""
    by_line: dict[int, list[str]] = {}
    order: list[int] = []
    for n_str, raw in items:
        nums = [int(x) for x in n_str.split(",")]
        text = re.sub(r"(?<=\S)\|(?=\S)", "", raw)      # rejoin mid-word break
        pieces = re.split(r"\s*\|\s*", text)            # split word-boundary breaks
        for i, piece in enumerate(pieces):
            piece = piece.strip()
            if not piece:
                continue
            num = nums[i] if i < len(nums) else nums[-1]
            if num not in by_line:
                by_line[num] = []
                order.append(num)
            by_line[num].append(piece)
    return [(num, re.sub(r"\s+", " ", " ".join(by_line[num])).strip())
            for num in order]


# A verified DK export quirk (Empedocles B142, a damaged Herculaneum
# papyrus, PHerc. 1012): Diels' own apparatus prose wraps a word across a
# PRINT-LINE boundary INSIDE a single raw <l> element (not across two <l>s,
# which _rejoin_wrapped_hyphens already handles elsewhere) -- e.g.
# "νομέ-|(5)νου" (hyphen, edition line-break bar, a parenthetical Diels-line
# number, then the word's continuation) and "οἰ-κτρῆς" (bare mid-word
# hyphen, no bar). Neither the DK verse walker's per-line reading nor
# stage3_tokenize.py's Beta Code transliteration has anywhere else to
# absorb this -- DK deliberately skips the cross-<l> hyphen rejoin (see
# parse_spine's own comment: adjacent flat[] entries can belong to
# different fragments), so a WITHIN-one-<l> wrap like this is a genuinely
# new shape.
#
# Rejoins a hyphen, optionally followed by a bracketed Diels-line number
# annotation like "(5)" (removed whole -- it is Diels' own print-line
# number, not part of any word, and stage3_tokenize.py has no mechanism to
# drop a bare digit the way it drops bracket sigla), then zero or more
# supplement brackets left dangling by the SAME wrap ("[" / "<", e.g.
# "λέ-|[γ]ε[ται]", "οἰ->κτ<ρ>ῆς" once entity-decoded) up to the eventual
# Greek letter that resumes the wrapped word -- mirroring
# _rejoin_wrapped_hyphens' word-wrap logic at the single-line scope this
# case actually needs. The skipped BRACKET characters (not the digit
# group, which is deleted outright) are left in place -- stage3_tokenize.py's
# `_SIGLA` already strips "()[]<>" from a token's interior.
_DK_INLINE_WRAP_RE = re.compile(
    r"-(?:\(\d+\))?(?=[\(\)\[\]<>]*[\u0370-\u03ff\u1f00-\u1fff])"
)

# Same B142 papyrus (PHerc. 1012, lines 5-6 of its div): the RAW, damaged
# transcription -- printed by Diels alongside his own clean reconstruction
# (which is what this work's manifest declares as the real citable text,
# see empedocles-fragments.yaml's B142 comment) -- marks uncertain letters
# with a combining dot-below (U+0323, e.g. "Τ̣") and illegible stretches
# with runs of bare periods ("......."), neither a real accent nor real
# punctuation. The combining mark is always safe to drop outright (it never
# appears anywhere else in this corpus). A period is only dropped when it
# sits with NO space against an UPPERCASE Greek letter on either side --
# the papyrus-placeholder shape (normal Greek prose is lowercase-and-
# accented; an uppercase run only ever occurs in exactly this kind of
# damage transcription) -- so a genuine Latin citation abbreviation like
# "p. 92" elsewhere in the SAME context text (space before the digits, not
# touching a Greek letter at all) is never touched.
_DK_COMBINING_DOT_BELOW = "\u0323"
_DK_DAMAGE_PERIOD_RE = re.compile(r"(?<=[\u0391-\u03a9])\.+|\.+(?=[\u0391-\u03a9])")

# Democritus A99a (Testimonia, a damaged Hibeh papyrus -- Grenfell-Hunt col.
# 2 -- quoted in Diogenes' PROSE context apparatus, not a verse <l>): the
# SAME lacuna-period damage convention as B142 above, but with the periods
# glued to LOWERCASE Greek ("απο.λ.λιπομενης", "απ.δ..πεσθαι") instead of an
# uppercase run -- this div's damaged span sits inside ordinary lowercase
# prose narrative, so the uppercase-only heuristic behind
# `_DK_DAMAGE_PERIOD_RE` (deliberately scoped that way for B142, see
# `_dk_clean_line_text`'s doc) does not fire. A SEPARATE, lowercase-scoped
# regex, applied only in the PROSE block path below and only for a column
# in this work's manifest-declared `citation.dk_damaged_columns` -- never
# touching the verse path or `_DK_DAMAGE_PERIOD_RE` itself, so B142's
# already-verified behavior is unchanged.
#
# GPT-5.6-Sol-High review blocker: the ORIGINAL version of this regex used
# the same "either side" alternation as `_DK_DAMAGE_PERIOD_RE` above
# (lookbehind-only OR lookahead-only) -- correct for B142's uppercase-run
# shape, where a period never legitimately sits next to an uppercase run
# any other way, but WRONG here, because A99a's damaged column is ordinary
# lowercase prose: an alternation fires on an ordinary SENTENCE period that
# merely has a lowercase Greek letter on ONE side and whitespace/§/an
# uppercase proper name on the other (verified corruption against the real
# div: source "...τῆς γῆς. Δη>μόκριτος..." emitted "...τῆς γῆς Δημόκριτος...",
# "...τῶν ὁμοφύλων. § ὅτι..." emitted "...τῶν ὁμοφύλων § ὅτι...", and
# "...γίνεσθαι τῆς γῆς. § τούτωι..." emitted "...γίνεσθαι τῆς γῆς § τούτωι...").
# The genuine lacuna shape in this div is always a period (or period run)
# with NO intervening whitespace on EITHER side -- glued INSIDE a word
# between two lowercase Greek letters, e.g. "απο.λ.λιπομενης", "απ.δ..πεσθαι"
# -- so the regex below requires BOTH the lookbehind AND the lookahead
# together (not an alternation): a period run only matches when a lowercase
# Greek letter immediately precedes AND immediately follows it. Whitespace,
# "§", an uppercase letter, or end-of-string on either side breaks the match,
# which is exactly what distinguishes an ordinary sentence-final period from
# a lacuna dot in this shape.
#
# The LOOKBEHIND excludes ς (U+03C2, which the naive range [α-ω] numerically
# includes): ς is word-FINAL by definition, so a dot run after it can never
# be intra-word letter damage -- it is a lacuna BETWEEN two surviving word
# tails, and stripping it fuses them into impossible Greek (Protagoras A30,
# Oxyrh. Pap. II col. XII: "ης.......ς" emitted "ηςς"; Opus ruling
# 2026-08-29). [α-ρσ-ω] is exactly [α-ω] minus ς, which sits between ρ and
# σ in the block. The LOOKAHEAD keeps ς: dots before a word-final ς can be
# ordinary intra-word damage ("τα..ς"), the case this regex exists for.
_DK_DAMAGE_PERIOD_LOWER_RE = re.compile(r"(?<=[α-ρσ-ω])\.+(?=[α-ω])")

# The companion for that excluded shape (same Opus ruling): a lacuna dot run
# glued between a word-final ς and a following lowercase letter keeps its
# dots (they are DK's own marker for the lost stretch, and the neighbouring
# lacunae in the same A30 sentence -- "η........ τοῖς", "τα...... ἐπ]ήδα" --
# all display theirs), but gains a space AFTER the run so the surviving tail
# becomes its own token: stage3 hard-fails on a token with INTERIOR dots,
# while edge dots strip cleanly before keying ("ης.......ς" is fatal;
# "ης....... ς" keys as hs + s). The space asserts no word division DK does
# not: word-initial ς is impossible, so the detached "ς" reads as exactly
# what it is, the surviving end of an unrecoverable word.
_DK_DAMAGE_PERIOD_AFTER_FINAL_SIGMA_RE = re.compile(r"(?<=ς)(\.+)(?=[α-ω])")


def _dk_clean_line_text(
    l_el: etree._Element, *, extra_strip_chars: str = "", damaged: bool = False,
) -> str:
    """`_line_text(l_el, strip_bars=True, extra_strip_chars=extra_strip_chars)`
    (the "|" edition line-break bar is never part of a DK verse line's own
    word; `extra_strip_chars` is this work's manifest-declared
    `citation.export_artifact_chars`, see `_line_text`'s own doc), plus --
    only when `damaged` is True (this column is in this work's manifest-
    declared `citation.dk_damaged_columns`, e.g. Empedocles B142) -- the two
    targeted B142-driven papyrus-transcription cleanups above (Sol blocker
    S3: both regexes were verified against exactly one div and, before this
    fix, applied unconditionally to every DK verse column of every DK verse
    work -- a length-based tightening of the damage-period regex was
    considered and rejected, since the real B142 div carries damage-period
    runs of both a single bare "." and a seven-period run, so no minimum
    length can separate damage from a hypothetical legitimate case without
    also losing the genuine single-period one; scoped instead by this
    manifest-declared column whitelist). `damaged` defaults to False: a
    column not explicitly whitelisted gets neither regex applied at all."""
    text = _line_text(l_el, strip_bars=True, extra_strip_chars=extra_strip_chars)
    if not damaged:
        return text
    text = _DK_INLINE_WRAP_RE.sub("", text)
    text = text.replace(_DK_COMBINING_DOT_BELOW, "")
    return _DK_DAMAGE_PERIOD_RE.sub("", text)



_SPEAKER_SENTINEL = "\x00"


def _line_with_speakers(el: etree._Element) -> tuple[str, list[dict]]:
    """Flatten an <l> for a section (Stephanus) work, EXCLUDING inline speaker
    labels from the token stream and returning where each turn begins.

    A `<label type="speaker">` marks the start of a speech; its text (e.g. "ΕΥΘ."
    or the Parmenides dialectic dash "—") must never enter the Greek token stream.
    We drop each such label but record a marker `{offset, label}` whose offset is
    the char position in the returned (whitespace-collapsed) line text where the
    following speech begins. A single physical line may carry several turns
    (Parmenides), so markers is a list in document order."""
    parts: list[str] = [el.text or ""]
    labels: list[str] = []
    for child in el:
        tag = etree.QName(child).localname if isinstance(child.tag, str) else ""
        if tag == "label" and child.get("type") == "speaker":
            labels.append((child.text or "").strip())
            parts.append(_SPEAKER_SENTINEL)
        else:
            # Non-speaker inline content (a <pb/> carries none; a head label on a
            # title line contributes its text) stays in the stream.
            parts.append("".join(child.itertext()))
        parts.append(child.tail or "")
    collapsed = re.sub(r"\s+", " ", "".join(parts)).strip()
    out: list[str] = []
    markers: list[dict] = []
    li = 0
    i = 0
    while i < len(collapsed):
        ch = collapsed[i]
        if ch == _SPEAKER_SENTINEL:
            i += 1
            if i < len(collapsed) and collapsed[i] == " ":
                i += 1  # absorb the single space after the label
            if out and out[-1] != " ":
                out.append(" ")
            markers.append({"offset": len("".join(out)), "label": labels[li]})
            li += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out), markers


def _parse_flat_bekker(tree, sch) -> tuple[list[dict], list[dict]]:
    """Flat (column, line_no, text) list for a flat page-div scheme (bekker,
    busse): the page div carries the whole column and holds <l> lines directly,
    with the Aristotle compound-line (<l n="8,9">) handling. Byte-identical to
    the original single-scheme parser."""
    flat: list[dict] = []
    headings: list[dict] = []
    for div in tree.iter("{*}div"):
        if div.get("type") != sch.page_div_type:
            continue
        column = sch.compose_column(div.get("n"))
        compound: list[tuple[str, str]] = []  # run of compound-numbered lines

        def flush():
            for line_no, text in _expand_compound(compound):
                flat.append({"column": column, "n": line_no, "text": text})
            compound.clear()

        for l in div.iter("{*}l"):
            n = l.get("n")
            if n and not n.isdigit() and _COMPOUND_N.match(n):
                compound.append((n, _line_text(l)))
                continue
            if compound:
                flush()
            line_no = _line_no(n)
            if line_no is None:
                headings.append({"column": column, "text": _line_text(l, strip_bars=True)})
                continue
            flat.append({"column": column, "n": line_no, "text": _line_text(l, strip_bars=True)})
        if compound:
            flush()
    return flat, headings


def _parse_flat_stephanus(tree, sch) -> tuple[list[dict], list[dict]]:
    """Flat (column, line_no, text, speakers) list for a section scheme
    (stephanus): each Stephanus-page div nests section divs; the column token is
    page+section and line numbers restart per section. Inline speaker labels are
    lifted out as per-line markers; title/heading lines (n="t") route to
    headings; stray <pb/> milestones are ignored (they carry no text)."""
    flat: list[dict] = []
    headings: list[dict] = []
    for page_div in tree.iter("{*}div"):
        if page_div.get("type") != sch.page_div_type:
            continue
        page_n = page_div.get("n")
        for sec_div in page_div.iter("{*}div"):
            if sec_div.get("type") != sch.section_div_type:
                continue
            column = sch.compose_column(page_n, sec_div.get("n"))
            for l in sec_div.iter("{*}l"):
                line_no = _line_no(l.get("n"))
                if line_no is None:
                    headings.append(
                        {"column": column, "text": _line_text(l, strip_bars=True)}
                    )
                    continue
                text, speakers = _line_with_speakers(l)
                entry = {"column": column, "n": line_no, "text": text}
                if speakers:
                    entry["speakers"] = speakers
                flat.append(entry)
    return flat, headings


# Diogenes Laertius' book-section export (section_div_type overridden to
# "section" per-manifest — see scheme.py's citation.div_types) intersperses
# philosopher-heading stub divs among its ordinary numbered section divs:
# @n="t18-47" marks the Greek display-name heading for the philosopher whose
# life spans sections 18-47 of that book. A bare numbered section (@n="85")
# is the ordinary citable case; this pattern only ever matches the stub form.
#
# A second stub shape, @n="t105" (no dash), marks a life confined to a
# single section — start == end == 105. Confirmed against the export itself
# (not guessed): every one of the 10 corpus-wide occurrences sits directly
# between two ordinary numbered-section runs whose boundary is exactly that
# one number, and one instance (book 2's "t125" immediately followed by
# "t125-144") lines up exactly with the already-documented doubled Bekker
# section 2.125 (Cebes's one-section life at t125, then Menedemus's life
# starting at the same shared column) — i.e. the abbreviated single-number
# form is how the export spells "start == end", not a different marker.
#
# This stub syntax is DL-specific, not a property of the book-section scheme
# itself — any other book-section work (Meditations, Discourses, Enchiridion)
# has no reason to carry a "t"-prefixed section @n at all. Collecting it into
# the headers channel is therefore gated on the work's manifest opting in
# (declaring a `philosophers` block, the same key emit_philosophers already
# reads — see _philosophers_declared below); for a work that has NOT opted
# in, a t-prefixed @n is a loud parse error rather than silently vanishing
# into an unused headers list (Sol Major 2 review round, 2026-07-16).
_TSTUB_N_RE = re.compile(r"^t(\d+)(?:-(\d+))?$")


def _philosophers_declared(manifest) -> bool:
    """Whether this work's manifest opts into philosopher-heading stub
    collection — presence of a `philosophers:` block (lives.yaml's
    `philosophers.names_file` is the concrete case emit_philosophers reads),
    regardless of its contents. `manifest` may be None (most direct-call
    test fixtures don't need one), which counts as not opted in."""
    return manifest is not None and manifest.data.get("philosophers") is not None


# Diogenes Laertius Book 10 (Epicurus) carries a well-known manuscript leaf
# transposition in the doxographical epitome just before the Letter to
# Menoeceus: the TLG export's own <div type="section"> run for what every
# translation reads as plain sections 120-121 is actually FOUR lettered
# fragments in manuscript document order — n="120a", "121b", "120b", "121a"
# — not two plain-numbered divs (confirmed: this is the ONLY place in the
# whole corpus these letter-suffixed section @n values appear). See
# manifests/lives.yaml's `citation.lettered_fragments` for the full
# philological rationale (Hicks's 1925 Loeb, following Bignone's
# transposition) and the declared found/merge table.
#
# The remap below is deliberately NOT hardcoded to book 10 in code: it is
# manifest-declared (any book-section work can, in principle, carry a
# similar seam) and validated before use. `_LETTERED_FRAGMENT_N_RE` detects
# the general SHAPE of a lettered fragment (digits + one lowercase letter);
# `_resolve_lettered_fragments` pre-scans the whole document, groups
# encountered lettered @n by book, and for each book that has any:
#   * requires a `citation.lettered_fragments` entry for that exact book —
#     an undeclared lettered @n is a loud ValueError, never a silent
#     misparse or a phantom column like "10.120a";
#   * requires the encountered set to match the declared `found` list
#     EXACTLY — same members, same document order — so a missing, extra, or
#     reordered fragment is also a loud ValueError naming the work, book,
#     and found-vs-declared mismatch, rather than being silently accepted.
# Only once both checks pass does the declared `merge` table become the
# (book, lettered-n) -> plain-section-n map the second pass composes columns
# from.
_LETTERED_FRAGMENT_N_RE = re.compile(r"^(\d+)([a-z])$")


def _validate_lettered_fragments_declaration(work_id: str, book_n: str, decl: dict) -> None:
    """Manifest-authoring validation for one citation.lettered_fragments
    entry, run BEFORE any comparison against the document's encountered
    lettered-@n set: a duplicate value inside `found`, or inside any single
    `merge` component list, can never be satisfied by any document — it is
    an error in the declaration itself, so it must fail loudly here rather
    than surfacing later as a confusing found-vs-declared mismatch, or
    silently overwriting the same (book, n) -> resolved_n mapping twice
    (Sol round-2 review, Hole 4)."""
    found = [str(x) for x in decl["found"]]
    if len(found) != len(set(found)):
        dupes = sorted({x for x in found if found.count(x) > 1})
        raise ValueError(
            f"{work_id}: book {book_n!r} citation.lettered_fragments "
            f"`found` list has duplicate entries {dupes!r} — each lettered "
            f"fragment may be declared at most once"
        )
    for resolved_n, components in decl["merge"].items():
        comps = [str(x) for x in components]
        if len(comps) != len(set(comps)):
            dupes = sorted({x for x in comps if comps.count(x) > 1})
            raise ValueError(
                f"{work_id}: book {book_n!r} citation.lettered_fragments "
                f"`merge` entry {resolved_n!r} has duplicate components "
                f"{dupes!r} — each lettered fragment may map to its "
                f"resolved section only once"
            )


def _resolve_lettered_fragments(tree, sch, manifest) -> dict[tuple[str, str], str]:
    encountered: dict[str, list[str]] = {}
    for book_div in tree.iter("{*}div"):
        if book_div.get("type") != sch.page_div_type:
            continue
        book_n = book_div.get("n")
        for chap_div in book_div.iter("{*}div"):
            if chap_div.get("type") != sch.section_div_type:
                continue
            n = chap_div.get("n")
            if _TSTUB_N_RE.match(n or ""):
                continue
            if _LETTERED_FRAGMENT_N_RE.match(n or ""):
                encountered.setdefault(book_n, []).append(n)

    work_id = manifest.work_id if manifest is not None else "<unknown>"

    # Validate every DECLARED book's table (not just encountered ones) up
    # front: a manifest-authoring duplicate inside `found`/`merge` fails
    # regardless of the document's contents (Hole 4), and a declared book
    # with NO encountered lettered @n at all — the document only ever
    # carries the plain form, e.g. n="120" instead of "120a" — is a stale
    # declaration that must fail loudly rather than silently no-opping,
    # which is what happened before when the loop below only ever visited
    # books that WERE encountered (Sol round-2 review, Hole 1).
    if manifest is not None:
        for book_n in manifest.lettered_fragment_books():
            decl = manifest.lettered_fragments_for_book(book_n)
            _validate_lettered_fragments_declaration(work_id, book_n, decl)
            if not encountered.get(book_n):
                raise ValueError(
                    f"{work_id}: stale lettered_fragments declaration: "
                    f"book {book_n!r} declares {decl['found']!r} but the "
                    f"document carries none"
                )

    resolved: dict[tuple[str, str], str] = {}
    for book_n, found in encountered.items():
        decl = manifest.lettered_fragments_for_book(book_n) if manifest is not None else None
        if decl is None:
            raise ValueError(
                f"{work_id}: lettered-fragment section n(s) {found!r} found "
                f"in book {book_n!r} but this work's manifest has no "
                f"citation.lettered_fragments entry for that book — a "
                f"lettered @n can only be remapped onto a plain section "
                f"number when the manifest declares the exact expected "
                f"fragment table for that book"
            )
        declared_found = [str(x) for x in decl["found"]]
        if found != declared_found:
            raise ValueError(
                f"{work_id}: book {book_n!r} lettered-fragment set does not "
                f"match the manifest's citation.lettered_fragments "
                f"declaration — found {found!r} (in document order), "
                f"declared {declared_found!r}"
            )
        merge = {str(k): [str(x) for x in v] for k, v in decl["merge"].items()}
        merge_components = [n for components in merge.values() for n in components]
        if sorted(merge_components) != sorted(declared_found):
            raise ValueError(
                f"{work_id}: book {book_n!r} citation.lettered_fragments "
                f"declaration is inconsistent — `merge` components "
                f"{sorted(merge_components)!r} do not match `found` "
                f"{sorted(declared_found)!r}"
            )
        for resolved_n, components in merge.items():
            for n in components:
                resolved[(book_n, n)] = resolved_n

    return resolved


def _parse_flat_book_section(tree, sch, manifest=None) -> tuple[list[dict], list[dict], list[dict]]:
    """Flat (column, line_no, text) list for a book-section prose scheme
    (Marcus Aurelius): <div type="Book" n="4"> nests <div type="chapter"
    n="23"> -> column "4.23" — the citable unit. A chapter usually nests a
    single <div type="section"> (up to 10, e.g. 1.16), which is NOT a
    separate citable column; its <p> paragraphs are flattened straight into
    the chapter as one synthetic line (n=1; this scheme has no user-facing
    line component — lines_user_facing is False).

    Flattening the whole chapter div's itertext() in one shot (via the same
    `_line_text` used elsewhere) also handles every documented anomaly for
    free, since none of them carries text of its own that would need special
    stripping: bare <pb/> milestones and <space quantity="N"/> indent markers
    contribute nothing (no .text, only a tail that already flows through);
    editorial [square] brackets and the `&lt;angle&gt;`-entity brackets and
    crux marks (†) are ordinary character data. The 2.1/3.1 manuscript
    colophons (<p><label type="head">Τὰ ἐν Κουάδοις...</label></p>, "Τὰ ἐν
    Καρνούντῳ") have no dedicated heading precedent in this scheme (unlike
    the <l n="t"> title-line -> `headings` convention the line-bearing
    parsers below use), so they fall out of this same flatten as the chapter
    text's leading text unit, preserved verbatim — the fallback the brief
    calls for when no heading precedent applies.

    One further exception: Epictetus' Discourses (also book-section) tags a
    chapter's Greek title as <div type="section" n="t">, mirroring the
    <l n="t"> title-line convention — it must not leak into the chapter body,
    so it is excluded from the flatten (see _strip_title_section) rather than
    being folded in like an ordinary sub-section.

    A third case (Diogenes Laertius, section_div_type overridden to
    "section"): a section div whose @n is a "tSTART-END" stub is a
    philosopher-heading marker, not a citable column at all — composing a
    column from it would flatten into a phantom column like "2.t18-47".
    Instead of joining `flat`, it is collected into the returned `headers`
    list as {book, start_section, end_section, greek_name}, where
    `greek_name` is the stub div's own flattened text (the philosopher's
    Greek display name). Collection is gated on `manifest` opting in (see
    `_philosophers_declared`) and the stub's bounds are validated (start >=
    1, end >= start) — both loud ValueError on failure, never a silent drop
    or a bogus header (Sol Major 2 review round, 2026-07-16).

    `manifest` also supplies the citation.lettered_fragments declaration
    (see `_resolve_lettered_fragments`) needed to remap DL book 10's
    manuscript-order lettered fragments onto plain section numbers; it may
    be None when the document carries no lettered fragments at all (most
    direct-call test fixtures).

    `manifest.data["citation"]["section_paragraphs"]` (opt-in, Discourses
    only) additionally attaches each chapter's `_chapter_sections` standoff
    channel as a `sections` key on its `flat` entry. Gated explicitly rather
    than by shape: Meditations' chapter divs nest the SAME kind of numbered
    section divs (up to ~10 per chapter) but John's ruling scopes the new
    paragraphing channel to Discourses only — see CANON.md / the Wave
    report for the rationale (Meditations' sub-chapter sections are not a
    meaningful citation granularity the way Discourses' Loeb-numbered
    sections are).

    `manifest.data["citation"]["lined_source"]` (opt-in, Discourses only —
    docs/lined-source-plan.md) replaces the single-flattened-line emission
    with one `flat` entry per Schenkl print `<l>` (`_lined_chapter_lines` +
    `_apply_lined_wraps`), and skips `_chapter_sections`/`section_paragraphs`
    entirely for that chapter — see those two helpers' own docstrings."""
    flat: list[dict] = []
    headings: list[dict] = []
    headers: list[dict] = []
    lettered = _resolve_lettered_fragments(tree, sch, manifest)
    emit_sections = bool(
        manifest is not None and manifest.data.get("citation", {}).get("section_paragraphs")
    )
    lined = _lined_source_declared(manifest)
    lined_section_div = _lined_section_div(manifest)
    declared_cross_column_wraps = _lined_cross_column_wraps_declared(manifest)
    # Lined emission collects per-column line lists BEFORE wrap application,
    # because one citable column can arrive as multiple leaf divs: a section
    # interrupted by a philosopher-heading stub (Lives 2.125, 7.160, 7.166,
    # 8.83, 8.84), or the declared lettered_fragments remap (Lives 10.120 =
    # 120a+121b+120b). Fragments renumber `n` continuously on merge (I1) and
    # the wrap pass runs ONCE over the assembled column, so a hypothetical
    # wrap at an interruption point is an ordinary in-column wrap, not a
    # spurious column-final one.
    lined_pending: dict[str, list[dict]] = {}
    for book_div in tree.iter("{*}div"):
        if book_div.get("type") != sch.page_div_type:
            continue
        book_n = book_div.get("n")
        for chap_div in book_div.iter("{*}div"):
            if chap_div.get("type") != sch.section_div_type:
                continue
            n = chap_div.get("n")
            m = _TSTUB_N_RE.match(n or "")
            if n and n.startswith("t") and not m:
                # Any @n beginning with "t" that is NOT a well-formed
                # tSTART(-END) stub is unrecognized, regardless of whether
                # this work's manifest opts into philosophers — malformed-
                # ness is what makes it an error, not opt-in status. Without
                # this guard a value like "t5-" or "tbad" falls through to
                # ordinary column composition below and is silently emitted
                # as a phantom column (Sol round-2 review, Hole 2).
                work_id = manifest.work_id if manifest is not None else "<unknown>"
                raise ValueError(
                    f"{work_id}: unrecognized t-prefixed section n={n!r} in "
                    f"book {book_n!r} — a well-formed philosopher-heading "
                    f"stub matches tSTART or tSTART-END; this value matches "
                    f"neither, so it cannot be a stub and must not fall "
                    f"through to ordinary column composition"
                )
            if m:
                if not _philosophers_declared(manifest):
                    work_id = manifest.work_id if manifest is not None else "<unknown>"
                    raise ValueError(
                        f"{work_id}: philosopher-heading stub section "
                        f"n={n!r} found in book {book_n!r}, but this work's "
                        f"manifest does not declare a `philosophers` block "
                        f"— a t-prefixed @n is only ever a header stub for "
                        f"a work that opts in; otherwise it is an "
                        f"unrecognized section n, which must fail loudly "
                        f"rather than silently dropping out of the "
                        f"citable spine"
                    )
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else start
                if start < 1 or end < start:
                    work_id = manifest.work_id if manifest is not None else "<unknown>"
                    raise ValueError(
                        f"{work_id}: malformed philosopher-heading stub "
                        f"n={n!r} in book {book_n!r} — start={start}, "
                        f"end={end} (start must be >= 1 and end >= start)"
                    )
                headers.append({
                    "book": int(book_n),
                    "start_section": start,
                    "end_section": end,
                    "greek_name": _line_text(chap_div),
                })
                continue
            resolved_n = lettered.get((book_n, n), n)
            column = sch.compose_column(book_n, resolved_n)
            stripped = _strip_title_section(chap_div)
            if lined:
                chap_lines = _lined_chapter_lines(
                    stripped,
                    lined_section_div,
                    alphabet=GREEK_LINED,
                    column=column,
                )
                if column in lined_pending:
                    base = len(lined_pending[column])
                    for i, cl in enumerate(chap_lines):
                        cl["n"] = base + i + 1
                    lined_pending[column].extend(chap_lines)
                else:
                    lined_pending[column] = chap_lines
                continue
            text = _rejoin_wrapped_hyphens(_line_text(stripped))
            if text:
                entry = {"column": column, "n": 1, "text": text}
                if emit_sections:
                    kept, _snapped = _chapter_sections(stripped, text)
                    if len(kept) >= 2:
                        entry["sections"] = kept
                flat.append(entry)
            else:
                headings.append({"column": column, "text": ""})
    if lined:
        for column, chap_lines in lined_pending.items():
            if chap_lines:
                _apply_lined_wraps(
                    column,
                    chap_lines,
                    alphabet=GREEK_LINED,
                    defer_column_final=declared_cross_column_wraps is not None,
                )
                flat.extend({"column": column, **cl} for cl in chap_lines)
            else:
                headings.append({"column": column, "text": ""})
        _apply_declared_lined_cross_column_wraps(
            flat, manifest, declared_cross_column_wraps
        )
    return flat, headings, headers


def _strip_title_section(chap_div: etree._Element) -> etree._Element:
    """`chap_div`, or (only if it nests one) a deep copy with any
    <div type="section" n="t"> removed — the chapter's Greek title (Discourses
    n="t" fix), which must not leak into the body text `_line_text`'s
    itertext() would otherwise flatten it into.

    Removal preserves the title div's .tail (the standard lxml removal dance:
    reattach it to the previous sibling's tail, or the parent's text when the
    div is the first child) — that tail is real body text sitting between the
    title's close tag and the next sibling, not part of the title."""
    titles = [
        d for d in chap_div.iter("{*}div")
        if d is not chap_div and d.get("type") == "section" and d.get("n") == "t"
    ]
    if not titles:
        return chap_div
    clone = copy.deepcopy(chap_div)
    for d in list(clone.iter("{*}div")):
        if d.get("type") == "section" and d.get("n") == "t":
            parent = d.getparent()
            tail = d.tail or ""
            if tail:
                prev = d.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or "") + tail
                else:
                    parent.text = (parent.text or "") + tail
            parent.remove(d)
    return clone


def _flat_title_content_hash(text: str) -> str:
    """Mirrors stage1_latin.py's `_title_content_hash` (same hash, same
    truncation) — kept as its own copy rather than a cross-module import
    since the two stages have no other coupling and the drop/merge
    declarations below are Greek-flat-scheme-specific (see
    `_load_flat_title_declarations`)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_flat_title_declarations(manifest) -> dict[str, str]:
    """A flat-scheme manifest's declared top-level `n="t"` divs (Epicurus'
    Letters/Vatican Sayings, Wave 3), keyed by `_flat_title_content_hash`
    (never a positional/shape heuristic — Sol re-review round 2's whole
    point for this parser): `citation.title_labels` ({sha256_16, note}[]).

    TLG's export carries an `n="t"` div for two different reasons, both
    dropped outright here (mirroring stage1_latin.py's PHI title-drop
    convention — same field name/shape, independently loaded since Latin's
    loader enforces a stricter 2-key-only shape this module does not need
    to share):

      * a bare work/collection title (Kuriai Doxai's "ΚΥΡΙΑΙ ΔΟΞΑΙ",
        Vatican Sayings' "ΕΠΙΚΟΥΡΟΥ ΠΡΟΣΦΩΝΗΣΙΣ") — carries no citable
        content of its own;
      * a letter's own opening salutation (Ep. Herodotum's "Ἐπίκουρος
        Ἡροδότῳ χαίρειν.", Ep. Menoeceum's "Ἐπίκουρος Μενοικεῖ χαίρειν."),
        exported as its own div immediately before the first numbered
        section rather than inline within it (contrast Ep. Pythoclem,
        where the identical greeting formula is an `<l n="t">` INSIDE
        section 84's own div and needs no special handling at all —
        confirmed against the export). Every scholarly edition (Bailey,
        Hicks) prints this salutation as an unnumbered rubric ABOVE the
        first numbered section, never as part of its text — dropping it
        here matches that convention, so section 35/122 read exactly as
        every printed edition cites them, opening with their own first
        substantive sentence rather than the salutation.

    An undeclared `n="t"` div is a LOUD error (raised at the call site),
    never a silent drop — a future re-export's differently-shaped title
    div must be reviewed and classified, not guessed at."""
    citation = (manifest.data.get("citation") or {}) if manifest is not None else {}
    out: dict[str, str] = {}
    for entry in citation.get("title_labels") or []:
        out[entry["sha256_16"]] = entry.get("note", "")
    return out


def _parse_flat_chapter(tree, sch, manifest=None, xml_path=None) -> tuple[list[dict], list[dict]]:
    """Flat (column, line_no, text) list for a flat, bookless prose scheme
    (Epictetus' Enchiridion, citation.scheme: "section"): <div type="Chapter"
    n="5"> sits at the TOP LEVEL — no Book wrapper — and IS the citable
    column (compose_column("5") -> "5"). A nested <div type="section"> (the
    chapter's un-cited sub-paragraph breaks) is not a separate citable
    column; it flattens straight into the chapter as one synthetic line
    (n=1; this scheme has no user-facing line component), exactly like
    _parse_flat_book_section's chapter flatten.

    Two guards against a mis-declared export — both LOUD errors, never a
    silent skip or misparse (Sol re-review round 2):
      * any <div type="Book"> in the document: this scheme is bookless by
        definition (the caller assigns every column to the single declared
        book), so a Book wrapper means the work is NOT flat and silently
        parsing it would misassign every chapter to book 1;
      * a Chapter div with ANY div ancestor (another Chapter, a front-matter
        wrapper, anything): the flat scheme describes chapters at the top
        level only, so a wrapped Chapter is a topology this scheme does not
        describe — treating it as a real column would emit a phantom
        chapter, and skipping it would silently drop text.

    `manifest.data["citation"]["section_paragraphs"]` (opt-in; per John's
    ruling 2026-07-16 that Greek sub-chapter divisions are the default
    paragraphing wherever TLG carries them — mirrors Discourses'
    book-section opt-in, see `_parse_flat_book_section`'s docstring)
    additionally attaches each chapter's `_chapter_sections` standoff channel
    as a `sections` key on its `flat` entry. A chapter with no chapter-title
    stub (confirmed against the export: zero occurrences in this scheme) so
    `_chapter_sections` runs directly against `chap_div` — no
    `_strip_title_section` pre-pass needed.

    `manifest.data["citation"]["lined_source"]` (opt-in, wave 1 —
    docs/lined-rollout-plan.md Ruling 1) replaces the single-flattened-line
    emission with one `flat` entry per Schenkl print `<l>`
    (`_lined_chapter_lines` + `_apply_lined_wraps`), mutually exclusive with
    `section_paragraphs` by construction (the lined branch `continue`s before
    the `section_paragraphs` code below can run). `citation.lined_section_div`
    (Enchiridion only) selects `_lined_chapter_lines`' string-walk mode,
    stamping `sec` from the chapter's own nested `<div type=…>` sub-division;
    absent, the five Epicurus works walk `<l>` directly under the column div
    and stamp no `sec` at all — see `_lined_section_div`'s and
    `_lined_chapter_lines`' own docstrings.

    A top-level `n="t"` div (Epicurus, Wave 3 — see
    `_load_flat_title_declarations`) is not itself a citable chapter and is
    dropped outright (a bare collection title, or a letter's own opening
    greeting — see that function's doc comment for why both drop). Which
    divs may be dropped is a manifest-declared hash gate, never inferred
    from position alone. Contrast Ep. Pythocles, whose IDENTICAL greeting
    formula is exported as an `<l n="t">` INSIDE its numbered section's own
    div rather than as a dedicated top-level div — that line needs no
    declaration and no dropping; it flattens into (or, lined, becomes a line
    of) that section automatically (Ruling 3)."""
    for el in tree.iter("{*}div"):
        if el.get("type") == "Book":
            raise ValueError(
                f"{xml_path or '<xml>'}: found div[@type=\"Book\"] under flat "
                f"scheme {sch.name!r} — this scheme is bookless; a Book "
                f"wrapper means the export does not match the declared "
                f"citation scheme"
            )

    flat: list[dict] = []
    headings: list[dict] = []
    emit_sections = bool(
        manifest is not None and manifest.data.get("citation", {}).get("section_paragraphs")
    )
    lined = _lined_source_declared(manifest)
    lined_section_div = _lined_section_div(manifest)
    declared_cross_column_wraps = _lined_cross_column_wraps_declared(manifest)
    declared_titles = _load_flat_title_declarations(manifest)
    for chap_div in tree.iter("{*}div"):
        if chap_div.get("type") != sch.page_div_type:
            continue
        wrapper = next(iter(chap_div.iterancestors("{*}div")), None)
        if wrapper is not None:
            raise ValueError(
                f"{xml_path or '<xml>'}: div[@type=\"{sch.page_div_type}\"]"
                f"[@n=\"{chap_div.get('n')}\"] is nested inside "
                f"div[@type=\"{wrapper.get('type')}\"] under flat scheme "
                f"{sch.name!r} — chapters must be top-level; a wrapped "
                f"export does not match the declared citation scheme"
            )
        if chap_div.get("n") == "t":
            title_text = _rejoin_wrapped_hyphens(_line_text(chap_div))
            h = _flat_title_content_hash(title_text)
            if h in declared_titles:
                continue
            raise ValueError(
                f"{xml_path or '<xml>'}: undeclared top-level n=\"t\" div "
                f"(sha256_16={h!r}, text={title_text!r}) under flat scheme "
                f"{sch.name!r} — declare it in citation.title_labels before "
                f"this can build"
            )
        column = sch.compose_column(chap_div.get("n"))
        if lined:
            chap_lines = _lined_chapter_lines(
                chap_div,
                lined_section_div,
                alphabet=GREEK_LINED,
                column=column,
            )
            if chap_lines:
                _apply_lined_wraps(
                    column,
                    chap_lines,
                    alphabet=GREEK_LINED,
                    defer_column_final=declared_cross_column_wraps is not None,
                )
                flat.extend({"column": column, **cl} for cl in chap_lines)
            else:
                headings.append({"column": column, "text": ""})
            continue
        text = _rejoin_wrapped_hyphens(_line_text(chap_div))
        if text:
            entry = {"column": column, "n": 1, "text": text}
            if emit_sections:
                kept, _snapped = _chapter_sections(chap_div, text)
                if len(kept) >= 2:
                    entry["sections"] = kept
            flat.append(entry)
        else:
            headings.append({"column": column, "text": ""})
    if lined:
        _apply_declared_lined_cross_column_wraps(
            flat, manifest, declared_cross_column_wraps
        )
        _warn_if_lined_source_has_no_wraps(
            manifest.work_id if manifest is not None else "<unknown>",
            flat,
            alphabet=GREEK_LINED,
        )
    return flat, headings


# ── DK (Diels-Kranz) fragment/testimonium parser ────────────────────────────
#
# Diels-Kranz's export shape is fundamentally different from every other
# scheme this pipeline parses: each citable unit (a fragment or testimonium)
# is its OWN flat div[@type="Fragment"][@n="30"] -- no nested section div.
# A prose work's div holds <p> children (Heraclitus, both Parmenides
# Testimonia and Fragmenta's few genuinely-prose testimony-style columns);
# a verse work's div (`citation.lines: true`, Parmenides Fragmenta) holds
# <l n> lines DIRECTLY under the div, no <p> wrapper at all -- see
# `_dk_walk_verse_div` below. Distinguishing the philosopher's own quoted
# words (role 'text', <hi rend="letter-spacing">) from the ancient source's
# narrative and Diels/Kranz's own German commentary (role 'context',
# rend="small"/"italic"/... -- structurally indistinguishable from each
# other in the export, see dk_lang.py's module doc) is the entire
# philological content of this parser; flattening it with the other
# parsers' single itertext() call would destroy that distinction (Wave 1b
# design memo §4).
#
# Verse role determination (Parmenides pilot finding, not anticipated by the
# design memo): unlike Heraclitus, where <hi rend="letter-spacing"> reliably
# brackets the ENTIRE citable quotation, most Parmenides verse fragments
# carry NO letter-spacing around their real multi-line poetry at all --
# letter-spacing there marks only short, elliptical PREVIEW quotations
# embedded in the apparatus (e.g. "'ἡ μὲν ... φράσαις'"), immediately
# followed by the full, unmarked verse continuation with no further
# typographic signal. Diels' own indentation attributes (rend="indent(1/2)")
# are cosmetic (present on both apparatus and verse lines alike) and cannot
# mechanically resolve the boundary either. This is the same "heuristic
# can't resolve it, philology must" situation dk_lang.py already formalizes
# for German-stripping -- so verse role, for the columns where the
# mechanical <hi>-walk gets it wrong, is a manifest-declared,
# philologically-reviewed override (`citation.verse_text_lines`; see
# `_dk_walk_verse_div`), not a heuristic. CANON-log-worthy: see the Wave 1b
# Parmenides integration report.

# A title div's @n ("tit,1-126") -- stripped entirely, following the
# _strip_title_section precedent, but matched narrowly (must start with
# "tit") so a genuinely malformed fragment @n can never silently vanish as
# "a title".
_DK_TITLE_N_RE = re.compile(r"^tit\b")

# An ordinary fragment/testimonium div's @n: digits + an optional single
# lowercase suffix letter (mirrors the dk column grammar's own number+suffix
# shape, scheme.py's _DK_COLUMN_RE -- the series letter is NOT part of the
# div's own @n; it is supplied by the work's declared citation.series).
_DK_PLAIN_N_RE = re.compile(r"^([0-9]+)([a-z]?)$")

# <hi rend="..."> values actually observed in the Heraclitus export
# (verified against build/export/.../tlg0626001.xml, tlg0626002.xml -- see
# the Wave 1b groundwork). Any OTHER rend value is a hard parse error (the
# first stage1 code to inspect `rend` at all -- a new typographic category
# in a later DK author must not silently mis-classify). "letter-spacing" is
# the ONLY role-determining value (Heraclitus B's own quoted words, or a
# testimonium's directly-quoted primary source); every other recognized
# value is typographic only (small/italic commentary-or-narrative framing,
# a combined "small italic", numeral overline notation, and a "superscript"
# footnote/folio marker -- including the literal, verified-against-the-
# export corrupted spelling " uper cript", a Diogenes/DDP export artifact,
# not a transcription typo introduced here) and never changes the ambient
# role on its own.
_DK_TEXT_RENDS = {"letter-spacing"}
_DK_RECOGNIZED_RENDS = _DK_TEXT_RENDS | {
    "small", "italic", "small italic", "overline", "small superscript",
    " uper cript",
}


def _dk_role_blocks(
    p_el, xml_path, initial_state: bool = False,
) -> tuple[list[tuple[bool, str]], bool]:
    """Walk one <p>'s content, returning `(runs, end_state)` -- `runs` is
    [(is_text, text)] in document order (`is_text` True for a span inside
    (at any depth under) a <hi rend="letter-spacing">, False otherwise (the
    default/ambient state for everything else, including plain unmarked
    prose -- see dk_lang.py's module doc and the memo's §4.2)); `end_state`
    is the ambient role in force AFTER this whole node has been walked --
    see the "end_state, not the last run" note below. A role FLIPS back to
    False the moment a letter-spacing span closes, and flips True again on
    the next one, so context->quote->context interleaving within one
    sentence (attested in the export, e.g. a "small" narrative wrapping a
    nested letter-spacing quotation) round-trips exactly. A non-role-
    determining <hi> (italic, overline, ...) never changes the ambient
    state -- critically, B4's entirely-Latin fragment nests
    <hi rend="italic"> INSIDE <hi rend="letter-spacing">, and that italic
    span must stay role='text' (it is Diels' own typographic choice for the
    Latin quotation, not a context interruption); the "own rend contains
    letter-spacing, else inherit ambient" rule handles this without a B4
    special case.

    `initial_state` seeds the ambient role the walk STARTS at (default False
    /context, prose's only caller). The verse walker (`_dk_walk_verse_div`)
    calls this once per <l> line of a fragment div and threads `end_state`
    (NOT the last element of `runs` -- see below) into the next line's
    `initial_state` -- so a milestone that fires near a line's end (e.g.
    Parmenides B21's self-closing letter-spacing right before a hyphenated
    word-wrap) correctly carries its role across the line boundary, exactly
    as it already carries across a <hi> boundary within one <p>.

    `end_state` vs. `runs[-1][0]` (Sol review blocker, div_concat ambient
    threading, Wave 1c Sophists batch 2): a caller threading ambient state
    across MULTIPLE calls (the verse walker across <l> lines, div_concat's
    own per-<p>-part loop below) must use this returned `end_state`, never
    infer it from the state of the last EMITTED run -- those two disagree in
    at least two real shapes: (a) a part/line ending inside a SCOPED
    <hi rend="letter-spacing"> with no tail (the last run's own state is
    True from inside that scoped subtree, but a scoped <hi>'s state change
    never escapes its own subtree -- the walk's real ending ambient state is
    whatever it was before the scoped span opened); (b) an EMPTY terminal
    milestone with no following text (`emit` never fires -- `runs` gains no
    new entry at all -- yet the milestone still flips the walk's own `state`
    for whatever comes next, in the NEXT part/line). `end_state` is `walk`'s
    own return value, which already accounts for both correctly; `runs`
    exists only to report what was actually emitted.

    Raises on any unrecognized rend value, and on a verse <l> encountered as
    a nested CHILD (never observed -- <l> elements don't nest). Calling this
    function WITH an <l> itself as the root (`p_el`) is legal and is exactly
    how the verse walker uses it, one call per line -- only a NESTED <l>
    child is rejected, by the `elif tag == "l"` branch below.

    A verified Diogenes export quirk (confirmed against the export -- e.g.
    Heraclitus B32, B41, B43, B84a): a fragment's letter-spaced quotation is
    sometimes marked by a self-closing MILESTONE `<hi rend="letter-spacing"
    />` with no content of its own, immediately followed by the actual
    quoted text as the empty element's TAIL -- not by the ordinary wrapping
    `<hi rend="letter-spacing">quote</hi>` shape. `walk` distinguishes the
    two: an ORDINARY (non-empty) `<hi>` is a SCOPED wrapper (its role
    change applies only to its own subtree, exactly like every other nested
    case above); an EMPTY self-closing `<hi>` is a MILESTONE (like a `<pb/>`
    page break) -- its role change applies to the rest of the CURRENT
    node's remaining content (starting with its own tail), not to a
    subtree it doesn't have -- UNLESS a LATER `<hi rend="letter-spacing">`
    -family sibling (scoped or itself a milestone) follows within that same
    immediate parent, verified below.

    A second, rarer export quirk (Anaxagoras A92, Theophrastus de sens.
    27-37 quoted inside one all-enclosing `<hi rend="small">` -- the only
    instance in the whole corpus swept for this shape, Wave 1b/1c
    verification): a self-closing milestone whose immediate parent goes on
    to hold a SECOND, genuinely-scoped `<hi rend="letter-spacing">` sibling
    later in its own content is not a real quotation-opening milestone --
    "extends to the rest of the current node" would swallow ~1,400 chars of
    Theophrastus' own third-person doxographical narrative (including his
    own "(30)"/"(37)" section numbers) as if they were Anaxagoras' own
    words, when the source's only genuine marked phrase there is the later
    sibling's own short, cleanly-scoped span ("τῆς λεπτῆς ἀέρος"). Every
    OTHER self-closing milestone actually observed in the corpus (Heraclitus
    B32/B41/B43/B84a and testimonium A19, Anaxagoras fragments B15/B16,
    Empedocles/Parmenides/Xenophanes verse) is the LAST `<hi
    rend="letter-spacing">`-family element within its own immediate
    parent -- its "extends to the end" span is exactly and only the real
    quotation, because nothing else marked follows it there. So: a
    milestone with a later same-parent letter-spacing sibling is treated as
    a no-op (an orphaned/duplicate export artifact, not a role change) --
    its own tail is emitted at whatever state already applied, and the
    later sibling's own (independently-correct) scoped marking is
    untouched. A milestone with no such later sibling keeps the original,
    verified "extends to the rest of the current node" behavior."""
    runs: list[tuple[bool, str]] = []

    def emit(state: bool, text: str | None) -> None:
        if text:
            runs.append((state, text))

    def walk(node, state: bool) -> bool:
        """Processes `node`'s text and children at ambient `state`, applying
        any milestone role changes found among its DIRECT children, and
        returns the (possibly milestone-updated) resulting state -- the
        caller's own state is otherwise unaffected (an ordinary scoped
        <hi>'s state change never escapes its own subtree)."""
        emit(state, node.text)
        children = list(node)
        for idx, child in enumerate(children):
            tag = etree.QName(child).localname if isinstance(child.tag, str) else ""
            if tag == "hi":
                rend = child.get("rend", "")
                if rend not in _DK_RECOGNIZED_RENDS:
                    raise ValueError(
                        f"{xml_path}: unrecognized <hi rend={rend!r}> inside "
                        f"a dk fragment div -- add it to _DK_RECOGNIZED_RENDS "
                        f"(and _DK_TEXT_RENDS if it marks the philosopher's "
                        f"own words) only after confirming what it means"
                    )
                new_state = state or (rend in _DK_TEXT_RENDS)
                is_milestone = child.text is None and len(child) == 0
                if is_milestone and rend in _DK_TEXT_RENDS and any(
                    etree.QName(sib).localname == "hi"
                    and sib.get("rend", "") in _DK_TEXT_RENDS
                    for sib in children[idx + 1:]
                ):
                    pass  # orphaned/duplicate milestone (A92 shape): no-op
                elif is_milestone:
                    state = new_state  # milestone: persists going forward
                else:
                    walk(child, new_state)  # scoped: subtree only
                emit(state, child.tail)
            elif tag == "l":
                raise NotImplementedError(
                    f"{xml_path}: <l> (verse line) inside a dk fragment div "
                    f"-- this parser handles prose only; a verse dk work "
                    f"(citation.lines: true) needs the verse-line walker "
                    f"the Wave 1b memo scopes to the Parmenides pilot"
                )
            else:
                # <space> (a bare indent marker) and any other tag (e.g. a
                # stray <pb/>) carry no role-changing effect of their own;
                # descend defensively (in case one unexpectedly nests real
                # content) at the unchanged ambient state.
                walk(child, state)
                emit(state, child.tail)
        return state

    end_state = walk(p_el, initial_state)
    return runs, end_state


# A verified DK export quirk (Empedocles A20a, Testimonia): a citation
# apparatus number ("...1208b 11") sits directly against the OPENING of the
# next sibling <hi> with no source whitespace at all ("11<hi
# rend=\"small\">φασὶ..."). Both sides are role='context' (small isn't
# role-determining), so _dk_merge_blocks' plain `+=` concatenation below
# glues them into one un-tokenizable run ("11φασὶ") -- so a synthetic space
# is inserted at exactly this script-boundary shape, and nowhere else, when
# merging.
#
# Sol blocker S3: the ONLY evidenced real shape is a citation-apparatus
# NUMBER glued to Greek (a page/section digit, never a letter) -- the
# earlier `.isalnum()` check also matched an ASCII LETTER touching Greek,
# which has no corpus evidence behind it and could legitimately be some
# other deliberately-glued token this codebase hasn't seen yet. Tightened
# to `.isdigit()` only: the evidenced shape, nothing broader.
#
# Anaxagoras A92 (Wave 1c, exposed by the milestone-vs-scoped fix above --
# see _dk_role_blocks' module doc): the SAME digit-then-Greek glue, but with
# a single closing parenthesis sitting between the digit and the Greek --
# "...τὸν ψόφον. (29)ἅπασαν..." (Theophrastus' own in-text section number,
# Diels' apparatus convention "(NN)", glued directly onto the following
# quotation with no source whitespace at all). `)` is not itself
# role-determining or digit-shaped, so the plain single-character check
# above misses it; one trailing `)` is stripped from `prev` before the
# digit check so "(29)" still counts as ending in "9" -- still the
# evidenced shape (a citation-apparatus number), just with its own closing
# paren riding along, nothing broader.
def _dk_needs_merge_space(prev: str, next_text: str) -> bool:
    prev_end = prev[-2:-1] if prev[-1:] == ")" else prev[-1:]
    next_start = next_text[:1]
    return (
        bool(prev_end) and prev_end.isascii() and prev_end.isdigit()
        and bool(next_start) and _is_greek_letter(next_start)
    )


def _dk_merge_blocks(runs: list[tuple[bool, str]]) -> list[dict]:
    """Collapse [(is_text, text)] runs into role-tagged blocks (§4.2):
    consecutive same-role runs merge into one block; whitespace is
    collapsed within a block the same way `_line_text` collapses it
    elsewhere. Empty (whitespace-only) blocks are dropped."""
    blocks: list[dict] = []
    for is_text, text in runs:
        role = "text" if is_text else "context"
        if blocks and blocks[-1]["role"] == role:
            prev = blocks[-1]["text"]
            if prev and text and _dk_needs_merge_space(prev, text):
                prev += " "
            blocks[-1]["text"] = prev + text
        else:
            blocks.append({"role": role, "text": text})
    out = []
    for b in blocks:
        collapsed = re.sub(r"\s+", " ", b["text"]).strip()
        if collapsed:
            out.append({"role": b["role"], "text": collapsed})
    return out


def _dk_rejoin_hyphen_across_role_blocks(blocks: list[dict]) -> list[dict]:
    """A TLG print-line hyphen-wrap (the same shape `_rejoin_wrapped_hyphens`
    fixes -- Greek letter, "-", then a lowercase Greek letter after the
    line-wrap's lost word-space) can straddle a `_dk_merge_blocks` role
    boundary: a letter-spacing milestone can open (or close) exactly at the
    wrap point, e.g. a context-role block ending "...λό-" immediately
    followed by a text-role block starting "γος...". `_rejoin_wrapped_hyphens`
    is applied PER BLOCK (see the `_dk_walk_verse_div_prose_runs` caller
    above), so it can never see both halves of such a word at once -- left
    alone, the word would render split across two blocks, one half wrongly
    muted or wrongly promoted.

    CONSTRAINT (deterministic, documented once here rather than at each call
    site): a word is never split across role blocks. When a block ends in an
    unambiguous wrap-hyphen (a Greek letter, then "-", nothing after -- by
    the time `_dk_merge_blocks` has collapsed/stripped each block, any
    original space between the hyphen and the continuation is already gone
    from both sides) and the immediately following block starts with a
    lowercase Greek letter, only the CONTINUATION WORD (the following
    block's text up to its first remaining space, if any) is pulled across
    into the hyphenated word's own block, and the merged span takes the
    HYPHEN-OWNER's role -- the role of the block holding the word's first
    half wins, not the role of the block holding its second half. Any text
    in the following block AFTER that first word keeps that block's own
    original role, in its own block, unaffected.

    Must run on `_dk_merge_blocks`' own output (already-collapsed
    {"role", "text"} blocks), before `_rejoin_wrapped_hyphens` is applied to
    each resulting block's text -- an intra-block hyphen-wrap (no role
    change at the wrap point) is left entirely to that later, per-block
    call, unaffected by this pass."""
    out: list[dict] = []
    for b in blocks:
        text = b["text"]
        prev = out[-1] if out else None
        if (
            prev is not None
            and prev["text"][-1:] == "-"
            and len(prev["text"]) >= 2
            and _is_greek_letter(prev["text"][-2])
            and text
            and _is_greek_letter(text[0])
            and text[0].islower()
        ):
            sp = text.find(" ")
            word, rest = (text, "") if sp == -1 else (text[:sp], text[sp + 1:])
            # Fold the whole pre-hyphen fragment before gluing on the
            # continuation. The join guards above remain unchanged.
            prev_fragment = prev["text"][:-1]
            prev_fragment = _fold_hyphen_final_sigma(prev_fragment)
            prev["text"] = prev_fragment + word
            if rest:
                out.append({"role": b["role"], "text": rest})
            continue
        out.append(dict(b))
    return out


def _dk_load_context_lang(manifest: Manifest) -> dict[str, dict[str, str]]:
    """This work's committed German/Latin/citation decision file (Wave 1b
    memo §4.3) -- `sources/<work_id>/dk-context-lang.json`, keyed by a HASH
    of each non-Greek run's own normalized text (see
    dk_lang.decision_key/normalize_run -- corpus source text is never
    committed, so the literal run text is never the key). Missing entirely
    is legal only when the work carries no non-Greek runs at all (never
    observed in practice); stage1 fails loudly the first time a run with no
    matching entry is actually encountered (see
    dk_lang.apply_context_language), not here."""
    path = SOURCES_DIR / manifest.work_id / "dk-context-lang.json"
    if not path.exists():
        return {}
    return dk_lang.load_decisions(path)


def _dk_walk_verse_div(
    div_el, xml_path, override_lines: set[str] | None,
    *, extra_strip_chars: str = "", damaged: bool = False,
) -> list[dict]:
    """One entry per `<l n>` DIRECT child of a verse dk fragment div (no `<p>`
    wrapper at all in a verse work's export -- see this section's module
    doc): `[{"raw_n": str, "is_text": bool, "text": str}, ...]` in document
    order.

    `extra_strip_chars`/`damaged` are this fragment's column-scoped
    `_dk_clean_line_text` inputs (Sol blocker S3) -- passed through
    unchanged, only consulted on the `override_lines is not None` path
    below (the only caller of `_dk_clean_line_text`).

    `override_lines`, when not None, is this column's manifest-declared
    `citation.verse_text_lines` set (raw `<l n>` values that are role='text')
    -- authoritative: a line's role is simply "raw_n in override_lines", and
    its text is the line's own plain flattened content (`_line_text`), no
    further <hi> role-splitting. This is the common case for Parmenides
    Fragmenta (see the module doc's "Verse role determination" note) --
    Diels' letter-spacing does not reliably bracket a multi-line verse
    quotation, only short apparatus previews, so the real text/context
    boundary needs a philologically-reviewed declaration.

    When None (a column with no override -- either a genuinely clean
    letter-spacing-bracketed column, e.g. B15a/B21, or a Latin fragment like
    B18 where role precision doesn't affect anything user-facing), role is
    the mechanical `_dk_role_blocks` walk, called once per line with the
    AMBIENT STATE THREADED ACROSS LINES (a milestone opened near one line's
    end -- e.g. a hyphenated word-wrap -- must carry its role into the next
    line, exactly as it already carries across a <hi> boundary within one
    <p>): a line's role is "any run in it came out True", and its text is
    the concatenation of ALL its runs (both roles) -- sub-line role
    granularity is not preserved for verse (a citable unit is a whole <l>),
    a deliberate simplification accepted for the columns using this path
    (see the Wave 1b Parmenides report for the specific, low-stakes cases
    this affects: B18, B21)."""
    out: list[dict] = []
    ambient = False
    for l_el in div_el.findall("{*}l"):
        raw_n = l_el.get("n") or ""
        if override_lines is not None:
            is_text = raw_n in override_lines
            text = _dk_clean_line_text(
                l_el, extra_strip_chars=extra_strip_chars, damaged=damaged,
            )
        else:
            runs, ambient = _dk_role_blocks(l_el, xml_path, initial_state=ambient)
            is_text = any(is_text_run for is_text_run, _ in runs)
            text = re.sub(r"\s+", " ", "".join(t for _, t in runs)).strip()
        if text:
            out.append({"raw_n": raw_n, "is_text": is_text, "text": text})
    return out


def _dk_walk_verse_div_prose_runs(div_el, xml_path) -> list[tuple[bool, str]]:
    """Like `_dk_walk_verse_div` with `override_lines=None` (the mechanical
    `_dk_role_blocks` walk, ambient state threaded across <l> lines), but for
    a `citation.prose_columns` column ONLY: preserves ROLE-RUN granularity
    instead of collapsing every `<l>` line to a single "any run in it came
    out True" verdict. A verse-shaped div whose content is genuinely
    testimonial prose can carry a MIXED-ROLE line -- a citation/apparatus
    header immediately followed by a letter-spaced quotation, all inside one
    raw `<l>` (Critias B31/B53/B60, confirmed by direct reading, Wave 1c
    Sophists batch 2) -- collapsing such a line to one role would wrongly
    promote the whole line's text (or wrongly mute the whole line's
    quotation), losing exactly the context/text split `_dk_role_blocks`
    already resolves correctly at sub-line granularity for ordinary <p>
    prose.

    Returns `[(is_text, text), ...]` runs in document order, ready for
    `_dk_merge_blocks` exactly like an ordinary <p>'s own runs. A synthetic
    single space is inserted between the LAST run of one <l> and the FIRST
    run of the next (reconstructing the real word-space a raw line's own
    right-stripped text already lost at its line-wrap boundary -- mirrors
    `_dk_walk_verse_div`'s own per-line join, before `_rejoin_wrapped_hyphens`
    removes it again at a genuine mid-word hyphen-wrap); WITHIN one line,
    runs concatenate exactly as `_dk_role_blocks` produced them (contiguous
    source text, no boundary lost). Ambient role state threads across lines
    via `_dk_role_blocks`' own returned `end_state` (see its doc comment for
    why this differs from the last emitted run's state)."""
    combined: list[tuple[bool, str]] = []
    ambient = False
    for l_el in div_el.findall("{*}l"):
        runs, ambient = _dk_role_blocks(l_el, xml_path, initial_state=ambient)
        if runs and combined:
            is_text_run, t = runs[0]
            runs[0] = (is_text_run, " " + t)
        combined.extend(runs)
    return combined


# Quote-mark polarity fix (owner ruling, 2026-08-05 -- "we fix it and make
# damn sure every instance is correct"): the raw TLG export frequently
# OPENS a Greek quotation with U+2019 RIGHT SINGLE QUOTATION MARK instead
# of U+2018 LEFT SINGLE QUOTATION MARK -- a verified UPSTREAM export
# defect (present already in the raw export XML), which our pipeline was
# until now faithfully passing through unexamined. This is a deliberate
# correction, not a parse fix.
#
# SAFETY (the one fact that matters most here): Greek ELISION in this
# corpus uses U+0027 APOSTROPHE (δ', ἀλλ', παρ', κατ', καθ', τ', οὐδ', ...)
# -- a completely different code point from either curly quote. U+2018/
# U+2019 are ALWAYS quotation marks here, NEVER elision. This pass
# touches ONLY U+2018 and U+2019 and must NEVER be extended to U+0027 --
# doing so would corrupt Greek words, not fix punctuation.
#
# A quotation can SPAN LINES (DK's apparatus narrative wraps a quoted
# sentence across several raw <l>/<p> lines/blocks), so marks must be
# collected and paired across a WHOLE COLUMN's blocks in document order,
# never per-block.
#
# Runs BEFORE `dk_lang.apply_context_language` (the German/Latin apparatus
# decision-file lookup), not after: a handful of this corpus's already-
# reviewed non-Greek runs happen to have a quote mark sitting right at
# their edge (e.g. "...Vgl. EURIP. fr. 944" immediately preceded by a
# quotation's closing mark) -- `dk_lang.find_non_greek_runs` includes that
# adjacent mark in the run it hashes, so the run's `decision_key` would
# differ depending on which side of the fix it's computed from. Running
# the fix FIRST means exactly one text -- the final, corrected text -- is
# ever hashed against `dk-context-lang.json`, corpus-wide, with no
# separate reconciliation needed between stage1's own decision lookups and
# preflight's independent re-derivation from the emitted dist (which can
# only ever see the final, corrected text). The handful of decision-file
# entries whose hash covered such a boundary were re-keyed once, by hand,
# against the corrected text at the same time this fix shipped (same
# review verdict -- `citation`/`keep-latin` -- just re-hashed).
#
# FAIL CLOSED (owner ruling): a column with an ODD total mark count can't
# be paired at all -- guessing which single mark is the stray would
# invent a reading the source doesn't support. Such a column is left
# COMPLETELY untouched (not partially fixed). preflight's own independent
# dist-level scan (`_validate_dk_work`) re-derives the same odd/even split
# straight from the emitted JSON and requires every odd (unbalanced)
# column to be declared BY NAME in `citation.dk_unbalanced_quote_columns`,
# so an unfixable column stays visible for review rather than silently
# dropped.
#
# Substitution is length-preserving (both marks are exactly one code
# point), so no line/offset structure changes -- this can run as a pure
# in-place text rewrite with no knock-on effect on token spans computed
# from this text later (stage3_tokenize.py).
_DK_QUOTE_OPEN = "‘"   # LEFT SINGLE QUOTATION MARK
_DK_QUOTE_CLOSE = "’"  # RIGHT SINGLE QUOTATION MARK
_DK_QUOTE_CHARS = _DK_QUOTE_OPEN + _DK_QUOTE_CLOSE


def _dk_normalize_quote_marks(blocks: list[dict]) -> None:
    """Mutates `blocks` (ONE column's block list, already fully assembled
    in document order -- including any div_map leading/trailing merge, see
    `_parse_fragments`' own call site) IN PLACE: rewrites its U+2018/
    U+2019 occurrences alternately -- 1st, 3rd, 5th... -> U+2018 (opening);
    2nd, 4th, 6th... -> U+2019 (closing). A column whose total mark count
    is ODD (or zero) is left completely untouched -- see the module
    comment above for why."""
    positions: list[tuple[int, int]] = []
    for idx, b in enumerate(blocks):
        for pos, ch in enumerate(b["text"]):
            if ch in _DK_QUOTE_CHARS:
                positions.append((idx, pos))
    if not positions or len(positions) % 2 != 0:
        return  # fail closed: zero or an odd count -- leave as-is

    by_block: dict[int, list[tuple[int, str]]] = {}
    for i, (idx, pos) in enumerate(positions):
        new_ch = _DK_QUOTE_OPEN if i % 2 == 0 else _DK_QUOTE_CLOSE
        by_block.setdefault(idx, []).append((pos, new_ch))
    for idx, repls in by_block.items():
        chars = list(blocks[idx]["text"])
        for pos, new_ch in repls:
            chars[pos] = new_ch
        blocks[idx]["text"] = "".join(chars)


def _parse_fragments(tree, sch, manifest: Manifest, xml_path=None) -> tuple[list[dict], list[dict]]:
    """Flat (column, n, text, role) list for a dk (Diels-Kranz) fragment or
    testimonium collection: each div[@type="Fragment"][@n] IS one citable
    column (composed from the work's declared `citation.series` + the div's
    own @n -- never through Scheme.compose_column, whose page/section
    signature has no series slot; see scheme.py's dk module doc).

    Lineless (default, Heraclitus + both Testimonia works): one fragment =
    one segment; every role-tagged block inside becomes one `flat` entry
    sharing that fragment's column, with a synthetic 1-based `n` (a
    display-suppressed position index, never a citable target).

    Verse (`sch.lines_user_facing`, Parmenides Fragmenta): a fragment div's
    `<l n>` children are walked directly (no `<p>` wrapper -- see
    `_dk_walk_verse_div`). Each role='text' line becomes its OWN flat entry
    with a REAL citable `n` -- 1-based, restarting per fragment, counting
    ONLY text lines (so a fragment whose real verse is preceded by testimonial
    apparatus, e.g. Parmenides B11, cites its poem's own first line "B11.1",
    not the div's raw TLG line 3). Consecutive role='context' lines merge
    into one block each, with a non-citable NEGATIVE synthetic `n` (distinct
    number space from any real citable line, so a citation jump/nearest-line
    snap can never land on one) -- mirrors `_dk_merge_blocks`' prose
    merge-adjacent-same-role behavior, at line rather than free-form-run
    granularity.

    Manifest `citation.series` ('A' or 'B') is required, UNLESS
    `citation.no_series: true` (a DK chapter printed with no series letter
    at all, e.g. Pythagoras DK 14 — see scheme.py's module doc), in which
    case `citation.series` must be omitted and the column carries no letter
    prefix. `citation.
    expected_gaps` (DK's own declared deletions, e.g. Heraclitus B84/B109)
    is checked here as a defensive spine assertion -- a re-export that
    RESTORES a declared-absent column is caught immediately rather than
    silently accepted; the authoritative completeness check is the
    `fragment_spine` count+sha256 fingerprint, verified in stage2 the same
    way `section_spine` already is.

    Div accounting (memo gate 3): every div in the source is consumed
    EXACTLY once -- as a citable column, a declared title div
    (`_DK_TITLE_N_RE`), a declared `citation.div_map` merge (Parmenides'
    irregular alternate-source/scholion divs, e.g. n="7,8" -> B7 leading
    context, n="8schol" -> B8 trailing context -- see the merge-collection
    pass below), or a declared `citation.div_concat` part (Xenophanes A28:
    DK's own testimonium is FIVE export divs with no separate plain "28"
    div at all -- div_map's leading/trailing shape merges an extra div
    around a real, independently-existing target column, which this case
    doesn't have, so div_concat instead declares an ORDERED list of source
    divs that together compose a column with no div of its own; see the
    Pass 1.5/Pass 2 handling below). Any other @n shape is a hard parse
    error.

    Role coverage (memo gate 4): every fragment must carry at least one
    role='text' block -- a context-only "fragment" is an extraction
    failure -- UNLESS its column is declared in the manifest's
    `citation.unmarked_columns`. This is a real, verified DK6/export
    characteristic, not a parser gap: a meaningful share of Heraclitus divs
    (both A-testimonia and, more surprisingly, B-fragments -- e.g. the
    famous B53 "war is father of all") carry NO letter-spacing markup at
    all -- the source's own typography does not always distinguish the
    citable words from their surrounding narrative (sometimes because a
    "— —" continuation entry's citation is implied from an earlier div and
    the whole remaining text IS the quotation with nothing to contrast
    against; sometimes because a paraphrase absorbs the attested word into
    its own sentence with nothing macroscopically quotable). Forcing a
    role='text' block onto that content would fabricate a typographic
    distinction the source itself does not draw; declaring the column
    instead is the honest, reviewable record of what the export actually
    contains (a CANON-log-worthy finding — see the Wave 1b report). Zero-
    Greek-token fragments (an all-Latin fragment like Heraclitus B4) are
    legal but must be declared in the manifest's `citation.latin_fragments`
    -- checked at preflight (post-tokenization), not here."""
    no_series = (manifest.data.get("citation") or {}).get("no_series", False)
    series = (manifest.data.get("citation") or {}).get("series")
    if no_series:
        # A DK chapter printed with no series letter (Pythagoras, DK 14 —
        # see scheme.py's `citation.no_series` doc). `series` composes
        # directly into the column token below (`f"{series}{n}"`), so ""
        # naturally yields a bare number+suffix column with no code change
        # to that composition. An explicit `citation.series: ""` does NOT
        # satisfy "series omitted" -- it must be genuinely absent (`None`),
        # same hole/fix as preflight.py's mirrored pre-check.
        if series is not None:
            raise ValueError(
                f"{manifest.work_id}: citation.series must be omitted "
                f"when citation.no_series is true"
            )
        series = ""
    elif series not in ("A", "B"):
        raise ValueError(
            f"{manifest.work_id}: citation.series must be 'A' or 'B' for a dk work"
        )
    is_verse = sch.lines_user_facing

    # Sol blocker S3 -- both scoped to THIS work's own manifest declaration,
    # never a global module-level constant (see `_line_text`'s and
    # `_dk_clean_line_text`'s own docs for the full rationale): a confirmed
    # export artifact character (e.g. Empedocles' U+1017C GREEK OBOL SIGN,
    # B109a) and the set of columns whose raw papyrus-damage transcription
    # needs the inline-wrap/damage-period cleanup (e.g. Empedocles B142) are
    # each verified against exactly one work's exactly one case and must not
    # silently apply corpus-wide on that strength alone.
    export_artifact_chars = "".join(
        (manifest.data.get("citation") or {}).get("export_artifact_chars", []) or []
    )
    dk_damaged_columns = set(
        (manifest.data.get("citation") or {}).get("dk_damaged_columns", []) or []
    )

    # `citation.prose_columns` (Wave 1c Sophists batch 2, Critias Fragmenta
    # finding, not anticipated by any prior DK wave): a verse work
    # (`citation.lines: true`) whose Diogenes export line-splits EVERY div
    # uniformly, including columns whose actual content is testimonial
    # PROSE, not the philosopher's own metrical verse -- confirmed by direct
    # reading (mid-word print-line hyphen wraps -- a prose word split
    # across two raw <l> lines with a literal trailing hyphen -- the same
    # hallmark that already distinguishes forced prose-chopping from real
    # verse elsewhere in this corpus; see docs/tlg-phi-export.md). Diogenes' own is_work_verse heuristic decides
    # verse/prose at WHOLE-WORK granularity, not per-div, so a single TLG
    # work mixing genuine verse (elegies, tragedy) with genuine prose
    # (Critias' own prose Constitution of the Spartans, his Homilies,
    # Pollux's lexicographic citations of his prose vocabulary) has no
    # export-level way to separate the two -- every div holds raw <l n>
    # lines regardless of genre. Declaring a column here does NOT change
    # how its raw lines are read (still `div.findall("l")`, still the
    # mechanical per-line `_dk_role_blocks` walk, ambient state threaded
    # across lines exactly like the ordinary verse mechanical path -- proven
    # reliable for prose testimonia throughout every OTHER dk work in this
    # corpus) -- it changes how the resulting (is_text, text) runs are
    # ASSEMBLED into blocks: merged via `_dk_merge_blocks` (adjacent
    # same-role lines collapse into one flowing paragraph, exactly like an
    # ordinary <p>-based prose column) instead of the verse path's per-line
    # `cite_n` citation numbering. Citing a prose testimonium's marked
    # quotation as if it were "line 3 of a poem" would be a genuine
    # citation-scheme error (DK does not cite Critias' prose fragments by
    # verse line) -- `cite_n` is always None here, matching every other
    # prose dk column in the corpus. A declared prose_columns entry may NOT
    # also carry a `verse_text_lines` override (the two mechanisms are
    # mutually exclusive -- an override declares raw <l n> role directly,
    # which only means something on the verse-citation path).
    prose_columns = set(
        (manifest.data.get("citation") or {}).get("prose_columns", []) or []
    )
    if prose_columns and not is_verse:
        raise ValueError(
            f"{manifest.work_id}: citation.prose_columns is only "
            f"meaningful for a verse dk work (citation.lines: true) -- an "
            f"ordinary prose work's columns are already prose by default"
        )

    # Read once, up front -- needed both by compound_n_map's trailing-
    # component check below (S2) and by the end-of-function re-appearance
    # check (`unexpected_present`) further down. Moved from its old
    # near-the-`return` position so compound_n_map validation can consult
    # it; the later check reuses this same variable rather than re-reading.
    expected_gaps = set(
        (manifest.data.get("citation") or {}).get("expected_gaps", [])
    )

    div_map_raw = (manifest.data.get("citation") or {}).get("div_map", [])
    div_map: dict[str, dict] = {}
    merge_targets_by_position: dict[tuple[str, str], str] = {}
    for e in div_map_raw:
        entry_n = str(e.get("n"))
        target = e.get("target")
        role = e.get("role")
        position = e.get("position")
        label = e.get("label")
        if role != "context":
            raise ValueError(
                f"{manifest.work_id}: citation.div_map entry n={entry_n!r} "
                f"has role={role!r} -- only 'context' is implemented (every "
                f"declared Parmenides merge is a context block: an "
                f"alternate-source witness or a scholion, never the "
                f"philosopher's own citable text)"
            )
        if position not in ("leading", "trailing"):
            raise ValueError(
                f"{manifest.work_id}: citation.div_map entry n={entry_n!r} "
                f"must declare position: leading|trailing (which side of "
                f"the target column's own content this merge renders on)"
            )
        if not target or not label:
            raise ValueError(
                f"{manifest.work_id}: citation.div_map entry n={entry_n!r} "
                f"must declare both target and label"
            )
        key = (target, position)
        if key in merge_targets_by_position:
            raise ValueError(
                f"{manifest.work_id}: citation.div_map declares two "
                f"{position!r} merges for target {target!r} -- at most one "
                f"per side"
            )
        merge_targets_by_position[key] = entry_n
        if entry_n in div_map:
            # A manifest-authoring duplicate (Sol review blocker): two
            # citation.div_map entries for the SAME source div @n would
            # otherwise silently overwrite -- the first entry's target/
            # position/label vanish with no error, exactly the kind of
            # invisible-loss bug the div-accounting gates elsewhere in this
            # function exist to prevent (mirrors the lettered_fragments
            # duplicate-declaration check).
            raise ValueError(
                f"{manifest.work_id}: citation.div_map declares n={entry_n!r} "
                f"more than once -- each source div may be declared at most "
                f"once"
            )
        div_map[entry_n] = e

    # div_map's declared TARGET column names (e.g. "B7") -- used below to
    # reject any citation.div_concat overlap with them (Sol review blocker
    # S1b/S1c): div_map's contract is that `target` names a REAL,
    # independently-existing column (a div_map merge attaches an EXTRA div
    # around it); a div_concat target has no div of its own at all, so the
    # two mechanisms' targets/members must never collide.
    div_map_targets: set[str] = {e["target"] for e in div_map.values()}

    # `citation.div_concat`: target column -> ORDERED list of source div
    # @n's that together compose it -- a mechanism distinct from div_map
    # (Xenophanes A28, Wave 1b Xenophanes finding, not anticipated by the
    # design memo): DK's own testimonium A28 is not one export div but FIVE,
    # split at the quoted Ps.-Aristotle "De Melisso Xenophane Gorgia"
    # treatise's own Bekker-page boundaries (977a/977b/978a/978b/979a), with
    # NO separate plain "28" div at all -- div_map's leading/trailing shape
    # always merges an EXTRA div around a real, independently-existing
    # target column, which this case doesn't have. Declared, ordered,
    # two-way-exact; prose only (no verse dk work has needed it). The
    # target's role/unmarked-column status is determined normally from its
    # (here: absent) letter-spacing, exactly like any ordinary column.
    div_concat_raw = (manifest.data.get("citation") or {}).get("div_concat", {}) or {}
    if div_concat_raw and is_verse:
        raise NotImplementedError(
            f"{manifest.work_id}: citation.div_concat is a prose-only "
            f"mechanism (no verse dk work has needed it yet)"
        )
    div_concat_source_to_target: dict[str, str] = {}
    div_concat_order: dict[str, list[str]] = {}
    for target, source_ns in div_concat_raw.items():
        if not isinstance(source_ns, list) or len(source_ns) < 2:
            raise ValueError(
                f"{manifest.work_id}: citation.div_concat[{target!r}] must "
                f"declare a list of at least two source div @n's"
            )
        # Sol review blocker S1b: a div_concat TARGET must not also be a
        # declared div_map TARGET -- div_map's contract requires a real,
        # independently-existing column to merge onto, which a div_concat
        # column (composed with no div of its own) can never be.
        if target in div_map_targets:
            raise ValueError(
                f"{manifest.work_id}: citation.div_concat declares target "
                f"{target!r}, but citation.div_map also declares it as a "
                f"merge target -- div_map's contract requires a real, "
                f"independently-existing target, which a div_concat output "
                f"column (no div of its own) can never be"
            )
        ordered = [str(n) for n in source_ns]
        div_concat_order[target] = ordered
        for n in ordered:
            if n in div_map:
                raise ValueError(
                    f"{manifest.work_id}: citation.div_concat declares "
                    f"n={n!r}, but it is also a citation.div_map source -- "
                    f"a div may be declared in at most one merge mechanism"
                )
            # Sol review blocker S1c: a div_concat MEMBER must not also be a
            # declared div_map TARGET (the reverse of the source check just
            # above) -- a div may be declared in at most one merge
            # mechanism, on either side of it.
            if n in div_map_targets:
                raise ValueError(
                    f"{manifest.work_id}: citation.div_concat declares "
                    f"n={n!r}, but it is also a citation.div_map target -- "
                    f"a div may be declared in at most one merge mechanism"
                )
            if n in div_concat_source_to_target:
                raise ValueError(
                    f"{manifest.work_id}: citation.div_concat declares "
                    f"n={n!r} more than once (targets "
                    f"{div_concat_source_to_target[n]!r} and {target!r}) -- "
                    f"each source div may be declared at most once"
                )
            div_concat_source_to_target[n] = target

    # `citation.compound_n_map`: raw div @n (a comma-joined DK compound,
    # e.g. Empedocles "77,78") -> the PLAIN number[+suffix] that div's
    # content is filed under (e.g. "77") -- a mechanism distinct from both
    # div_map (an EXTRA div merged as context around a real target) and
    # div_concat (MULTIPLE divs composing ONE column with no div of its
    # own). Here there is exactly ONE div, and DK's own print edition gives
    # it a JOINT heading spanning two or three consecutive numbers (verified
    # against the export: Empedocles B "77,78" and "148,149,150" each carry
    # ONE continuous apparatus discussing/quoting content DK numbers under a
    # combined heading, not several independently-quotable sub-entries with
    # a mechanical split point) -- modern concordances (e.g. Wright's
    # edition) likewise treat each as one grouped citation. The div's full
    # content (apparatus + all its letter-spaced quotations) ships under the
    # FIRST number's column; the other number(s) in the joint heading are
    # declared in `citation.expected_gaps` (no column of their own -- a
    # reader citing, e.g., "B78" specifically gets the standard unknown-
    # citation error, same posture as any other DK numbering quirk). Wave 1b
    # Empedocles finding, CANON-log-worthy, flagged for a citation-grammar
    # follow-up if John wants "B78"/"B149"/"B150" separately addressable.
    compound_n_map_raw = (
        (manifest.data.get("citation") or {}).get("compound_n_map", {}) or {}
    )
    compound_n_map: dict[str, str] = {}
    for raw_n, target_n in compound_n_map_raw.items():
        raw_n = str(raw_n)
        target_n = str(target_n)
        if not _DK_PLAIN_N_RE.match(target_n):
            raise ValueError(
                f"{manifest.work_id}: citation.compound_n_map[{raw_n!r}] "
                f"target {target_n!r} does not match the plain "
                f"number[+suffix] column grammar"
            )
        # Sol review blocker S2 (compound_n_map collision matrix) -- four
        # checks, all purely declarative (derivable from the manifest's own
        # declared dicts, no document walk needed), mirroring the
        # div_map/div_concat mutual-exclusion and target-collision checks
        # elsewhere in this function:
        #
        # (1) A compound source div must not also be declared as a div_map
        # source or a div_concat source -- "a div may be declared in at most
        # one merge mechanism" (same contract div_map/div_concat already
        # enforce against each other).
        if raw_n in div_map:
            raise ValueError(
                f"{manifest.work_id}: citation.compound_n_map declares "
                f"n={raw_n!r}, but it is also a citation.div_map source -- "
                f"a div may be declared in at most one merge mechanism"
            )
        if raw_n in div_concat_source_to_target:
            raise ValueError(
                f"{manifest.work_id}: citation.compound_n_map declares "
                f"n={raw_n!r}, but it is also a citation.div_concat source "
                f"-- a div may be declared in at most one merge mechanism"
            )
        # (2) The declared target must equal the div's own FIRST joint-
        # heading component -- compound_n_map files a div's content under
        # its first number by construction (see the module comment above);
        # a target that doesn't match that first component is either a typo
        # or files the content under the wrong column.
        components = [c.strip() for c in raw_n.split(",")]
        first_component = components[0] if components else None
        if first_component != target_n:
            raise ValueError(
                f"{manifest.work_id}: citation.compound_n_map[{raw_n!r}] "
                f"target {target_n!r} does not match the div's own first "
                f"heading component {first_component!r} -- a compound "
                f"div's content is always filed under its FIRST "
                f"joint-heading number"
            )
        # (3) Every trailing component (the joint-heading numbers AFTER the
        # first, which get no column of their own) must be explicitly
        # acknowledged in citation.expected_gaps -- an undeclared trailing
        # number would otherwise vanish from the spine with no record that
        # its absence is expected.
        for trailing in components[1:]:
            gap_column = f"{series}{trailing}"
            if gap_column not in expected_gaps:
                raise ValueError(
                    f"{manifest.work_id}: citation.compound_n_map[{raw_n!r}] "
                    f"trailing component {trailing!r} composes column "
                    f"{gap_column!r}, which has no column of its own and "
                    f"must be declared in citation.expected_gaps -- an "
                    f"undeclared trailing component would silently vanish "
                    f"from the spine with no record of why"
                )
        compound_n_map[raw_n] = target_n

    # (4) A compound_n_map TARGET must not collide with a div_concat TARGET
    # -- both mechanisms compose a column with no div of its own already
    # anchored under a name, so two different sources claiming the same
    # output column would silently overwrite one another downstream.
    compound_target_columns = {f"{series}{t}" for t in compound_n_map.values()}
    compound_concat_target_overlap = compound_target_columns & set(div_concat_order)
    if compound_concat_target_overlap:
        raise ValueError(
            f"{manifest.work_id}: citation.compound_n_map target(s) "
            f"{sorted(compound_concat_target_overlap)} collide with "
            f"citation.div_concat declared target(s) -- a div may compose "
            f"at most one output column via at most one mechanism"
        )

    unmarked_columns = set(
        (manifest.data.get("citation") or {}).get("unmarked_columns", [])
    )
    verse_text_lines_raw = (
        (manifest.data.get("citation") or {}).get("verse_text_lines", {}) or {}
    )
    if verse_text_lines_raw and not is_verse:
        raise ValueError(
            f"{manifest.work_id}: citation.verse_text_lines is only "
            f"meaningful for a verse dk work (citation.lines: true)"
        )
    verse_text_line_counts_raw = (
        (manifest.data.get("citation") or {}).get("verse_text_line_counts", {}) or {}
    )
    if verse_text_line_counts_raw and not is_verse:
        raise ValueError(
            f"{manifest.work_id}: citation.verse_text_line_counts is only "
            f"meaningful for a verse dk work (citation.lines: true)"
        )
    prose_verse_override_overlap = prose_columns & set(verse_text_lines_raw)
    if prose_verse_override_overlap:
        raise ValueError(
            f"{manifest.work_id}: citation.prose_columns declares "
            f"{sorted(prose_verse_override_overlap)}, but citation."
            f"verse_text_lines also declares (an) override for the same "
            f"column(s) -- the two mechanisms are mutually exclusive (a "
            f"prose column always uses the mechanical letter-spacing walk, "
            f"never a verse line-role override)"
        )

    # Manifest-authoring validation (Sol review blocker 1): a PARTIAL
    # verse_text_lines declaration for a column -- a clean 1..k subset of
    # REAL, EXISTING <l n> values that still passes the verse gate while the
    # rest of that fragment's real verse silently demotes to muted context
    # -- is the worst silent-failure class this scheme has: nothing about a
    # too-short declared set looks wrong on its own. Two checks here mirror
    # the two-way-exact discipline every other declared list in this
    # function already uses (lettered_fragments' found-vs-declared, div_map's
    # stale checks):
    #   1. no duplicate value within one column's own declared list (would
    #      otherwise silently collapse into the same set entry, one fewer
    #      real declaration than the author intended, with no error);
    #   2. `verse_text_line_counts` is a REQUIRED, independently-declared
    #      redundant count for every (and only every) column
    #      verse_text_lines declares -- so a future edit that trims or
    #      copy-paste-truncates part of a column's line list without ALSO
    #      updating its paired count fails loudly here, instead of quietly
    #      demoting the dropped lines to context. (Existence -- every
    #      declared value is actually a raw <l n> in that fragment's own
    #      div -- is checked per-div below, once the document is walked;
    #      that catches a wrong-but-plausible value a count mismatch alone
    #      wouldn't.)
    declared_line_cols = set(verse_text_lines_raw)
    declared_count_cols = set(verse_text_line_counts_raw)
    extra_counts = declared_count_cols - declared_line_cols
    if extra_counts:
        raise ValueError(
            f"{manifest.work_id}: citation.verse_text_line_counts declares "
            f"{sorted(extra_counts)}, but citation.verse_text_lines declares "
            f"no such column -- a stale declaration must be removed"
        )
    missing_counts = declared_line_cols - declared_count_cols
    if missing_counts:
        raise ValueError(
            f"{manifest.work_id}: citation.verse_text_lines declares "
            f"{sorted(missing_counts)}, but citation.verse_text_line_counts "
            f"has no matching entry -- every declared column's resulting "
            f"text-line count must be independently declared too, so a "
            f"future partial edit to the line list is caught rather than "
            f"silently accepted"
        )
    for col, ns in verse_text_lines_raw.items():
        raw_list = [str(x) for x in ns]
        if len(raw_list) != len(set(raw_list)):
            dupes = sorted({x for x in raw_list if raw_list.count(x) > 1})
            raise ValueError(
                f"{manifest.work_id}: citation.verse_text_lines[{col!r}] has "
                f"duplicate entries {dupes!r} -- each declared line may "
                f"appear at most once"
            )
        expected_count = verse_text_line_counts_raw[col]
        if len(raw_list) != expected_count:
            raise ValueError(
                f"{manifest.work_id}: citation.verse_text_lines[{col!r}] "
                f"declares {len(raw_list)} line(s) but "
                f"citation.verse_text_line_counts[{col!r}] declares "
                f"{expected_count} -- a partial or stale line-list edit "
                f"must be reconciled with its independently-declared "
                f"count, not silently accepted"
            )

    verse_text_lines: dict[str, set[str]] = {
        col: {str(x) for x in ns} for col, ns in verse_text_lines_raw.items()
    }
    verse_text_lines_used: set[str] = set()

    decisions = _dk_load_context_lang(manifest)
    used_decisions: set[str] = set()

    flat: list[dict] = []
    seen_ns: set[str] = set()
    # target_column -> {"leading"|"trailing": {"label": str, "text": str}}
    # (text already German-stripped -- see the merge-collection pass below;
    # the ordinary-column loop that consumes these must NOT re-run
    # apply_context_language over already-stripped text).
    merges: dict[str, dict[str, dict]] = {}

    # Pass 1: collect every declared div_map merge FIRST, over the whole
    # document, before any ordinary column is parsed. A single combined pass
    # would only ever see a merge div that happens to precede its target in
    # document order (Parmenides' own case is split both ways: "7,8" precedes
    # its target B7, but "8schol" FOLLOWS its target B8) -- `position`
    # (leading/trailing) is a declared RENDERING side, independent of the
    # export's own document order, so merge collection must not depend on it
    # either.
    for div in tree.iter("{*}div"):
        if div.get("type") != sch.page_div_type:
            continue
        n = div.get("n") or ""
        if n not in div_map:
            continue
        if n in seen_ns:
            raise ValueError(
                f"{xml_path or manifest.work_id}: div @n={n!r} appears "
                f"more than once -- every div must be consumed exactly once"
            )
        seen_ns.add(n)
        entry = div_map[n]
        target, position, label = entry["target"], entry["position"], entry["label"]
        raw_text = _line_text(div)
        stripped = dk_lang.apply_context_language(
            raw_text, decisions,
            where=f"{manifest.work_id} div n={n!r} (div_map -> {target})",
            used=used_decisions,
        )
        merges.setdefault(target, {})[position] = {"label": label, "text": stripped}

    # Pass 1.5: pre-scan every declared div_concat source div's <p> children,
    # over the whole document, before Pass 2 walks it in order. Unlike
    # div_map's leading/trailing shape, a concat target has no
    # independently-existing "real" div of its own to anchor Pass 2's
    # per-div loop -- ALL of a target's parts must be in hand before the
    # FIRST of them (in document order) is reached and the synthetic column
    # emitted there (see Pass 2 below).
    div_concat_parts: dict[str, list] = {}  # source n -> that div's <p> children
    div_concat_actual_order: dict[str, list[str]] = {}  # target -> n's, DOCUMENT order
    for div in tree.iter("{*}div"):
        if div.get("type") != sch.page_div_type:
            continue
        n = div.get("n") or ""
        if n not in div_concat_source_to_target:
            continue
        if n in div_concat_parts:
            raise ValueError(
                f"{xml_path or manifest.work_id}: div @n={n!r} appears "
                f"more than once -- every div must be consumed exactly once"
            )
        div_concat_parts[n] = list(div.findall("{*}p"))
        div_concat_actual_order.setdefault(div_concat_source_to_target[n], []).append(n)
    missing_concat_parts = set(div_concat_source_to_target) - set(div_concat_parts)
    if missing_concat_parts:
        raise ValueError(
            f"{manifest.work_id}: citation.div_concat declares source "
            f"div(s) {sorted(missing_concat_parts)}, but no such div was "
            f"found in the export -- a stale declaration (re-export "
            f"changed the page split) must be removed, not left to "
            f"silently no-op"
        )

    # Sol review blocker S2: the declared order is not a reordering device --
    # it must MATCH the export's own document order exactly. Without this, a
    # re-export that shuffled a target's parts (page-split churn) would
    # silently compose the column in the STALE declared order instead of the
    # new document order, reordering the resulting text with no error at
    # all. Checked here, once every part's document position is known; the
    # declaration then serves purely as a pinned, reviewable expectation.
    for target, declared in div_concat_order.items():
        actual = div_concat_actual_order.get(target, [])
        if actual != declared:
            raise ValueError(
                f"{manifest.work_id}: citation.div_concat[{target!r}] "
                f"declares order {declared!r}, but the export's own "
                f"document order is {actual!r} -- a re-export that "
                f"reordered these parts must update the manifest to match "
                f"(the declaration pins an expectation, it never reorders "
                f"the composed text)"
            )

    # Sol review blocker S1a: `seen_ns` (above) tracks SOURCE div @n's, not
    # output COLUMN names -- it cannot catch a re-export that adds a plain
    # div whose @n happens to equal a div_concat TARGET column (e.g. a real
    # n="28" div appearing alongside the "28,977a".."28,979a" parts that
    # already compose column "A28"): the plain div's @n ("28") and the
    # concat parts' @n's ("28,977a" etc.) are all distinct strings, so
    # `seen_ns` sees no collision at all, and the plain div would silently
    # become a SECOND "A28" entry in `flat` instead of failing loudly.
    # `seen_columns` closes that gap by tracking the column namespace
    # itself, independent of which mechanism established it.
    seen_columns: set[str] = set()

    # Pass 2: ordinary columns (div_map source divs already consumed above
    # are skipped here via `n in div_map`, never double-processed;
    # div_concat source divs are folded into their target column the moment
    # the FIRST declared part is reached, in document order).
    for div in tree.iter("{*}div"):
        if div.get("type") != sch.page_div_type:
            continue
        n = div.get("n") or ""

        p_elements: list | None = None
        if n in div_concat_source_to_target:
            target = div_concat_source_to_target[n]
            order = div_concat_order[target]
            if n != order[0]:
                continue  # a later part of `target` -- folded in below
            for part_n in order:
                if part_n in seen_ns:
                    raise ValueError(
                        f"{xml_path or manifest.work_id}: div @n={part_n!r} "
                        f"appears more than once -- every div must be "
                        f"consumed exactly once"
                    )
                seen_ns.add(part_n)
            column = target
            p_elements = [p for part_n in order for p in div_concat_parts[part_n]]
        elif _DK_TITLE_N_RE.match(n):
            continue  # the work's Greek title div -- stripped, never a column

        elif n in div_map:
            continue  # consumed in pass 1

        else:
            # A declared citation.compound_n_map entry (e.g. "77,78" -> "77")
            # resolves to its target's plain number[+suffix] BEFORE the
            # grammar check below, so the div's own joint-headed content is
            # filed under that plain column exactly like any ordinary div —
            # no other code path in this function needs to know the
            # difference (see the compound_n_map module comment above).
            effective_n = compound_n_map.get(n, n)
            m = _DK_PLAIN_N_RE.match(effective_n)
            if not m:
                raise ValueError(
                    f"{xml_path or manifest.work_id}: unrecognized dk "
                    f"fragment @n={n!r} -- matches neither the title "
                    f"pattern, a declared citation.div_map/div_concat/"
                    f"compound_n_map entry, nor the plain number[+suffix] "
                    f"column grammar"
                )
            if n in seen_ns:
                raise ValueError(
                    f"{xml_path or manifest.work_id}: div @n={n!r} appears "
                    f"more than once -- every div must be consumed exactly "
                    f"once"
                )
            seen_ns.add(n)
            column = f"{series}{effective_n}"

        # Sol review blocker S1a: FATAL, not a silent second column -- see
        # the `seen_columns` declaration above.
        if column in seen_columns:
            raise ValueError(
                f"{xml_path or manifest.work_id}: div @n={n!r} composes "
                f"output column {column!r}, but that column was already "
                f"established by another div -- every output column must "
                f"be established exactly once (a re-export may have added "
                f"a plain div whose @n now collides with a "
                f"citation.div_concat target)"
            )
        seen_columns.add(column)

        # Each entry: {"role", "text", "cite_n" (int|None), "pre_stripped"
        # (bool -- a div_map merge's text was already German-stripped at
        # collection time above; re-running apply_context_language on it a
        # second time would misinterpret this block's own synthetic
        # "[Label] " prefix's balanced brackets as part of the ORIGINAL
        # export text and, worse, re-derive `used_decisions` off already-
        # substituted text -- harmless in practice since the strip is
        # idempotent, but skipped outright for clarity).
        blocks: list[dict] = []

        lead = merges.get(column, {}).get("leading")
        if lead:
            blocks.append({
                "role": "context", "cite_n": None, "pre_stripped": True,
                "text": f"[{lead['label']}] {lead['text']}",
            })

        if is_verse and column in prose_columns:
            # citation.prose_columns (see its own declaration comment
            # above): this column's div holds raw <l n> lines like every
            # other div in a verse work, but its content is testimonial
            # PROSE, not the philosopher's own metrical verse. Read the
            # lines via the SAME mechanical per-line `_dk_role_blocks` walk
            # the ordinary verse mechanical path uses (ambient state
            # threaded across lines via `_dk_role_blocks`' own returned
            # `end_state`, ¬override) -- proven reliable for prose
            # testimonia throughout the rest of this corpus -- then
            # assemble the resulting (is_text, text) RUNS with
            # `_dk_merge_blocks`, exactly like an ordinary <p>-based prose
            # column: adjacent same-role runs collapse into one flowing
            # paragraph, and `cite_n` is always None (no verse-line
            # citation number; DK does not cite these fragments by line).
            #
            # RUN granularity, not LINE granularity (Critias B31/B53/B60
            # content-verification finding, Wave 1c Sophists batch 2): a
            # single raw <l> can itself mix roles -- a citation/apparatus
            # header immediately followed by a letter-spaced quotation (and
            # sometimes a further short context tail) all on one physical
            # line. Collapsing a line to one `is_text = any(...)` verdict
            # (the ordinary verse-citation path's own simplification, fine
            # there because a citable unit is a whole poem line either way)
            # would wrongly promote the ENTIRE mixed line to role='text'
            # here, where there is no such citable-unit excuse -- so this
            # path keeps each `_dk_role_blocks` run separate instead of
            # flattening per line.
            prose_runs = _dk_walk_verse_div_prose_runs(div, xml_path or manifest.work_id)
            # `_dk_merge_blocks` already collapses internal whitespace and
            # merges adjacent same-role runs (including the digit-glued-to-
            # Greek `_dk_needs_merge_space` fixup); `_rejoin_wrapped_hyphens`
            # -- the SAME helper already used corpus-wide for a flattened
            # chapter's hyphen-wrapped print lines -- then removes exactly
            # the "hyphen + space(s) + lowercase Greek letter" shape a
            # genuine mid-word line-wrap leaves (the synthetic single space
            # `_dk_walk_verse_div_prose_runs` inserts at each <l> boundary
            # to reconstruct the line-wrap's lost word-space), doing nothing
            # to any other boundary. `_dk_rejoin_hyphen_across_role_blocks`
            # runs FIRST, mending a wrap-hyphen that lands exactly at a role
            # transition (see its own doc comment for why a per-block
            # `_rejoin_wrapped_hyphens` call alone can never see both halves
            # of such a word) -- not observed in this corpus's own six built
            # works as of this fix, but a real, evidenced export shape
            # (Sol re-review), so handled deterministically rather than left
            # to silently split a word.
            for b in _dk_rejoin_hyphen_across_role_blocks(_dk_merge_blocks(prose_runs)):
                text = _rejoin_wrapped_hyphens(b["text"])
                if text:
                    blocks.append({"role": b["role"], "cite_n": None,
                                    "pre_stripped": False, "text": text})
        elif is_verse:
            override = verse_text_lines.get(column)
            if override is not None:
                verse_text_lines_used.add(column)
                # Existence half of the two-way-exact contract (Sol review
                # blocker 1): every declared line value must be a REAL raw
                # <l n> in THIS fragment's own div -- an independent
                # fingerprint of the source, computed fresh here rather than
                # trusted from the manifest. A declared value with no
                # matching raw line (a typo, or a value left over from a
                # prior re-export's numbering) would otherwise just never
                # match in `_dk_walk_verse_div` below, silently doing
                # nothing instead of failing loudly.
                raw_line_ns = {l_el.get("n") or "" for l_el in div.findall("{*}l")}
                missing = sorted(override - raw_line_ns)
                if missing:
                    raise ValueError(
                        f"{manifest.work_id}: citation.verse_text_lines"
                        f"[{column!r}] declares line(s) {missing} that do "
                        f"not exist as a raw <l n> in this fragment's div "
                        f"-- a typo or a stale value from a prior export "
                        f"must be fixed, not silently ignored"
                    )
            verse_lines = _dk_walk_verse_div(
                div, xml_path or manifest.work_id, override,
                extra_strip_chars=export_artifact_chars,
                damaged=column in dk_damaged_columns,
            )
            text_i = 0
            ctx_buf: list[str] = []

            def _flush_ctx() -> None:
                nonlocal ctx_buf
                if ctx_buf:
                    joined = _rejoin_wrapped_hyphens(
                        re.sub(r"\s+", " ", " ".join(ctx_buf)).strip()
                    )
                    if joined:
                        blocks.append({"role": "context", "cite_n": None,
                                        "pre_stripped": False, "text": joined})
                    ctx_buf = []

            for vl in verse_lines:
                if vl["is_text"]:
                    _flush_ctx()
                    text_i += 1
                    blocks.append({"role": "text", "cite_n": text_i,
                                    "pre_stripped": False, "text": vl["text"]})
                else:
                    ctx_buf.append(vl["text"])
            _flush_ctx()
        else:
            # `p_elements` is set only for a div_concat target column (its
            # content spans multiple source divs, declared order); every
            # ordinary column falls back to its own single div's children.
            #
            # Ambient role state THREADS ACROSS `p_elements` (Wave 1c
            # Sophists batch 2, Antiphon 87 B44 finding): a div_concat
            # column is, by its own contract, one unbroken passage split
            # only at the source's own page/column boundaries (verified
            # content-continuous at declaration time, e.g. Xenophanes A28's
            # own comment) -- a self-closing letter-spacing milestone near
            # the end of one part must carry its role into the NEXT part,
            # exactly as it already carries across a <hi> boundary within
            # one <p>, or across an <l> line boundary in the verse walker
            # (`_dk_walk_verse_div`'s own `ambient` variable). B44's own
            # papyrus text (POxy 1364) is entirely Antiphon's own words
            # after one milestone opens near the top of its first part; the
            # OLD per-<p> `initial_state=False` reset silently muted 10 of
            # its 11 parts back to role='context' the moment each new part
            # began -- confirmed wrong by content, not merely suspected.
            # An ORDINARY (non-concat) column's own multiple <p> siblings
            # keep the pre-existing, unthreaded behavior -- unrelated
            # working code, out of this fix's scope.
            #
            # Threaded via `_dk_role_blocks`' own returned `end_state`, NOT
            # `runs[-1][0]` (Sol review blocker -- see `_dk_role_blocks`' own
            # doc comment for the two shapes this gets wrong: a part ending
            # inside a scoped, tail-less letter-spacing span, and an empty
            # terminal milestone with no following text).
            ambient = False
            for p in (p_elements if p_elements is not None else div.findall("{*}p")):
                runs, end_state = _dk_role_blocks(
                    p, xml_path or manifest.work_id,
                    initial_state=(ambient if p_elements is not None else False),
                )
                if p_elements is not None:
                    ambient = end_state
                for b in _dk_merge_blocks(runs):
                    text = _rejoin_wrapped_hyphens(b["text"])
                    # Same manifest-declared `citation.export_artifact_chars`
                    # the verse path (`_dk_walk_verse_div` above) already
                    # honours -- prose divs can carry the identical shape (a
                    # non-lexical mark glued onto a Greek run with no
                    # separating space, e.g. Zeno A28's embedded diagram
                    # direction arrows on "ΒΒΒΒ"/"ΓΓΓΓ") and stage3_tokenize's
                    # Beta Code transliteration handles it no differently
                    # than the verse case. Scoped identically: only fires
                    # for a work that declares it.
                    for ch in export_artifact_chars:
                        text = text.replace(ch, "")
                    # Democritus A99a (dk_damaged_columns, prose): the
                    # lowercase-Greek-scoped damage-period cleanup (see
                    # `_DK_DAMAGE_PERIOD_LOWER_RE`'s own doc) -- opt-in per
                    # column, never touches any work that doesn't declare it.
                    if column in dk_damaged_columns:
                        # U+0323 removal must run FIRST (Sol catch on the ς
                        # fix; the verse path `_dk_clean_line_text` already
                        # orders it this way): a dot-below glued between a
                        # letter and a lacuna run ("ης̣...ς") blinds
                        # both lookbehinds, and removing it afterwards
                        # re-creates the glued interior-dot shape stage3
                        # hard-fails on.
                        text = text.replace(_DK_COMBINING_DOT_BELOW, "")
                        text = _DK_DAMAGE_PERIOD_LOWER_RE.sub("", text)
                        text = _DK_DAMAGE_PERIOD_AFTER_FINAL_SIGMA_RE.sub(
                            r"\1 ", text
                        )
                    blocks.append({"role": b["role"], "cite_n": None,
                                    "pre_stripped": False, "text": text})

        trail = merges.get(column, {}).get("trailing")
        if trail:
            blocks.append({
                "role": "context", "cite_n": None, "pre_stripped": True,
                "text": f"[{trail['label']}] {trail['text']}",
            })

        has_text_block = any(b["role"] == "text" for b in blocks)
        if not has_text_block and column not in unmarked_columns:
            raise ValueError(
                f"{manifest.work_id}: fragment {column} carries no "
                f"role='text' block -- a context-only \"fragment\" is an "
                f"extraction failure (memo gate 4), unless declared in "
                f"citation.unmarked_columns"
            )
        if has_text_block and column in unmarked_columns:
            # The other direction of the same two-way-exact contract (Sol
            # review blocker): citation.unmarked_columns must equal the
            # OBSERVED unmarked-column set exactly, mirroring
            # lettered_fragments' found-vs-declared precedent above. A
            # declared-unmarked column that actually carries a
            # role='text' block is a stale declaration (a re-export that
            # now marks the fragment normally, or a manifest typo) --
            # left undetected, it would silently mis-tag that block's
            # role downstream from what the export actually shows.
            raise ValueError(
                f"{manifest.work_id}: citation.unmarked_columns declares "
                f"{column!r}, but this export DOES carry a role='text' "
                f"letter-spacing run for it -- a stale declaration must "
                f"be removed from the manifest, not left to silently "
                f"no-op"
            )

        # Quote-mark polarity fix: runs over this column's now-fully-
        # assembled `blocks` (leading merge + main content + trailing
        # merge), BEFORE the decision-language lookup below -- see
        # `_dk_normalize_quote_marks`'s own module doc for why this must
        # come first, not last. A `pre_stripped` (div_map merge) block's
        # own decision-matching already ran, earlier, against its ORIGINAL
        # text (Pass 1 above) -- unaffected by this call either way, since
        # it never re-runs `apply_context_language` below.
        _dk_normalize_quote_marks(blocks)

        ctx_i = 0
        for i, b in enumerate(blocks, start=1):
            stripped = b["text"] if b["pre_stripped"] else dk_lang.apply_context_language(
                b["text"], decisions, where=f"{manifest.work_id} {column}",
                used=used_decisions,
            )
            if not stripped:
                continue  # a block that was ENTIRELY a strip-german run
            if not is_verse:
                out_n = i  # unchanged lineless behavior: position index, all roles
            elif b["cite_n"] is not None:
                out_n = b["cite_n"]  # real citable verse-line number
            else:
                ctx_i -= 1
                out_n = ctx_i  # non-citable, distinct number space (negative)
            flat.append({"column": column, "n": out_n, "text": stripped, "role": b["role"]})

    stale_decisions = sorted(set(decisions) - used_decisions)
    if stale_decisions:
        # The committed file carries no run text (see dk_lang's key-format
        # doc), so a hash alone is useless to a reviewer here -- report each
        # stale hash alongside its own (non-verbatim) `note`, the only
        # human-readable trace of what it was for that survives in committed
        # code.
        stale_report = [
            f"{h} ({decisions[h].get('note', '?')!r})" for h in stale_decisions[:5]
        ]
        raise ValueError(
            f"{manifest.work_id}: dk-context-lang.json declares "
            f"{len(stale_decisions)} decision(s) for a run that no longer "
            f"occurs in this export -- a stale entry (re-export changed the "
            f"text, or a manifest-authoring slip) must be removed, not left "
            f"to silently no-op: {stale_report}"
            + (" ..." if len(stale_decisions) > 5 else "")
        )

    emitted_columns = {e["column"] for e in flat}

    stale_unmarked = unmarked_columns - emitted_columns
    if stale_unmarked:
        raise ValueError(
            f"{manifest.work_id}: citation.unmarked_columns declares "
            f"{sorted(stale_unmarked)}, but no such column was emitted -- "
            f"a stale declaration (renumbering, or the export now marks "
            f"the fragment normally) must be removed from the manifest, "
            f"not left to silently no-op"
        )

    stale_div_map = set(div_map) - seen_ns
    if stale_div_map:
        raise ValueError(
            f"{manifest.work_id}: citation.div_map declares n="
            f"{sorted(stale_div_map)}, but no such div was found in the "
            f"export -- a stale declaration (renumbering, or a re-export "
            f"change) must be removed from the manifest, not left to "
            f"silently no-op"
        )

    stale_compound_n_map = set(compound_n_map) - seen_ns
    if stale_compound_n_map:
        raise ValueError(
            f"{manifest.work_id}: citation.compound_n_map declares n="
            f"{sorted(stale_compound_n_map)}, but no such div was found in "
            f"the export -- a stale declaration (renumbering, or a "
            f"re-export change) must be removed from the manifest, not "
            f"left to silently no-op"
        )

    stale_div_concat = set(div_concat_source_to_target) - seen_ns
    if stale_div_concat:
        raise ValueError(
            f"{manifest.work_id}: citation.div_concat declares n="
            f"{sorted(stale_div_concat)}, but no such div was consumed -- "
            f"a stale declaration (renumbering, or a re-export change) "
            f"must be removed from the manifest, not left to silently "
            f"no-op"
        )

    stale_prose_columns = prose_columns - emitted_columns
    if stale_prose_columns:
        raise ValueError(
            f"{manifest.work_id}: citation.prose_columns declares "
            f"{sorted(stale_prose_columns)}, but no such column was ever "
            f"emitted -- a stale declaration (renumbering, or a re-export "
            f"change) must be removed from the manifest, not left to "
            f"silently no-op"
        )

    unconsumed_div_concat_targets = set(div_concat_order) - emitted_columns
    if unconsumed_div_concat_targets:
        raise ValueError(
            f"{manifest.work_id}: citation.div_concat declares target(s) "
            f"{sorted(unconsumed_div_concat_targets)}, but no such column "
            f"was ever emitted -- every declared target's first part must "
            f"actually be found in the export"
        )

    unconsumed_merges = set(merges) - emitted_columns
    if unconsumed_merges:
        raise ValueError(
            f"{manifest.work_id}: citation.div_map declares merge target(s) "
            f"{sorted(unconsumed_merges)}, but no such column was ever "
            f"processed as an ordinary fragment -- every div_map target "
            f"must itself be a real, emitted column"
        )

    stale_verse_text_lines = set(verse_text_lines) - verse_text_lines_used
    if stale_verse_text_lines:
        raise ValueError(
            f"{manifest.work_id}: citation.verse_text_lines declares "
            f"{sorted(stale_verse_text_lines)}, but no such column was "
            f"processed as an ordinary verse fragment -- a stale "
            f"declaration must be removed from the manifest, not left to "
            f"silently no-op"
        )

    unexpected_present = expected_gaps & emitted_columns
    if unexpected_present:
        raise ValueError(
            f"{manifest.work_id}: citation.expected_gaps declares "
            f"{sorted(unexpected_present)} as absent, but the export "
            f"carries them -- a re-export may have restored a div DK/TLG "
            f"previously omitted; update the manifest, don't silently "
            f"accept the drift"
        )

    return flat, []


def _check_sourcedesc(tree, manifest: Manifest, xml_path) -> None:
    """FATAL gate (Wave 1c Sol nit): the export XML's own <teiHeader>
    <sourceDesc> text must CONTAIN this work's manifest-declared
    `work.expected_sourcedesc` substring -- an author-name + edition
    fragment in the exact wording Diogenes' own export prints (e.g.
    "Anaxagoras Phil." + "Die Fragmente der Vorsokratiker, vol. 2",
    verified against the export at manifest-authoring time). Catches a
    wrong-author or wrong-edition re-export at the earliest possible
    point: a stale TLG_DIR pointing at a DIFFERENT author's numbered file
    (e.g. TLG0635 Stoic Zeno re-exported in place of TLG0595 Zeno of
    Elea -- both plausibly named "Zeno" in a casual export run) would
    otherwise silently parse as if it were the declared philosopher's own
    corpus; every div/column mechanism downstream has no way to know the
    text is simply the wrong work. Declared per-work (not hardcoded here)
    so a differently-shaped sourceDesc (a different scheme, a PHI Latin
    work, ...) needs no special-casing.

    Optional: a work with no `work.expected_sourcedesc` declared skips
    this check entirely -- not every work has been backfilled with it."""
    expected = manifest.data.get("work", {}).get("expected_sourcedesc")
    if not expected:
        return
    nodes = tree.findall(".//{*}sourceDesc")
    actual = " ".join(
        re.sub(r"\s+", " ", "".join(node.itertext())).strip() for node in nodes
    )
    if expected not in actual:
        raise ValueError(
            f"{xml_path or manifest.work_id}: export XML's <sourceDesc> "
            f"does not contain the manifest-declared work.expected_sourcedesc "
            f"{expected!r} -- got {actual!r}. A wrong-author or wrong-edition "
            f"re-export (e.g. a stale TLG_DIR pointing at a different "
            f"numbered file) must fail loudly here, not silently parse as if "
            f"it were the declared work's own corpus."
        )


def parse_spine(xml_path: Path, manifest: Manifest) -> dict:
    tree = etree.parse(str(xml_path))
    _check_sourcedesc(tree, manifest, xml_path)
    # The citation scheme selects the export shape and column-token grammar:
    #   - bekker       : <div type="Bekker-page" n="16a"> holds <l> directly.
    #   - busse        : <div type="page" n="1"> -> synthetic a-side column
    #                    "1a" (Porphyry's Isagoge; reader relabels the gutter).
    #   - stephanus    : <div type="Stephanus-page" n="2"> nests
    #                    <div type="section" n="a"> -> column "2a"; lines
    #                    restart per section; inline
    #                    <label type="speaker"> turn markers.
    #   - book-section : <div type="Book" n="4"> nests <div type="chapter"
    #                    n="23"> -> column "4.23"; no <l> lines at all (plain
    #                    <p> prose), so the whole chapter flattens to one
    #                    synthetic line (see _parse_flat_book_section).
    #   - section      : <div type="Chapter" n="5"> at the TOP LEVEL (no Book
    #                    wrapper) -> column "5"; a nested <div type="section">
    #                    flattens into the chapter the same way (see
    #                    _parse_flat_chapter). Bookless — every column is
    #                    assigned to the work's single declared book below.
    sch = scheme_mod.for_manifest(manifest)
    # philosopher_headers is only ever populated by the book-section branch
    # (Diogenes Laertius' "t18-47" philosopher-heading stubs — see
    # _parse_flat_book_section); every other scheme leaves it empty, and the
    # returned spine dict omits the key entirely in that case (see below).
    philosopher_headers: list[dict] = []
    if sch.flat_numeric:
        flat, headings = _parse_flat_chapter(tree, sch, manifest, xml_path)
    elif sch.numeric_section:
        flat, headings, philosopher_headers = _parse_flat_book_section(tree, sch, manifest)
    elif sch.fragment_scheme:
        # dk (Diels-Kranz) — checked BEFORE the has_sections branch below,
        # since dk also sets has_sections=True (the fragment list is the
        # outline nav) but its export shape (one flat div per citable
        # fragment, no nested section div) has nothing in common with
        # stephanus' page>section nesting.
        flat, headings = _parse_fragments(tree, sch, manifest, xml_path)
    elif sch.has_sections:
        flat, headings = _parse_flat_stephanus(tree, sch)
    else:
        flat, headings = _parse_flat_bekker(tree, sch)

    # Rejoin hyphenated words: a line ending in "-" takes the first
    # whitespace-delimited token of the next line (which may sit in the next
    # section or page). Consuming that token off the FRONT of the next line
    # shifts any speaker markers on it left by the removed prefix length.
    # Book-section's synthetic per-chapter line is not a physical print-line
    # wrap artifact (no editions hyphenate across chapters), so this rejoin
    # would only ever misfire by splicing one chapter's trailing "-" onto the
    # next chapter's opening word; skip it for that scheme entirely. `section`
    # (Epictetus' Enchiridion) is the same synthetic-per-chapter-line shape.
    # dk's role-tagged blocks are likewise not physical print-line wraps —
    # excluded for the same reason, PLUS adjacent flat[] entries can belong
    # to two DIFFERENT fragments (no book/column boundary check here), so
    # splicing across that boundary would corrupt an unrelated fragment.
    for i, line in enumerate([] if (sch.numeric_section or sch.flat_numeric or sch.fragment_scheme) else flat):
        if not line["text"].endswith("-"):
            continue
        if i + 1 >= len(flat) or not flat[i + 1]["text"]:
            raise ValueError(
                f"hyphenated line with no continuation: {line['column']}{line['n']}"
            )
        nxt = flat[i + 1]
        head, _, rest = nxt["text"].partition(" ")
        # No Greek-letter guard on this loop's JOIN (see the comment above),
        # but the sigma FOLD keeps the same guard the other three sites have
        # (Sol review WARN, 2026-08-29): fold a line-end ς only when the
        # absorbed continuation begins with a Greek letter — a ς before an
        # apostrophe/bracket continuation is genuinely word-final and must
        # stay ς. Zero corpus occurrences today; this is a tripwire-grade
        # guard, not a behavior change.
        fragment = line["text"][:-1]
        if fragment and head and _is_greek_letter(head[0]):
            fragment = _fold_hyphen_final_sigma(fragment)
        line["text"] = fragment + head
        line["joined"] = True
        removed = len(nxt["text"]) - len(rest)
        nxt["text"] = rest
        for m in nxt.get("speakers", []):
            m["offset"] = max(0, m["offset"] - removed)

    # Group into per-(book, column) segments, preserving document order.
    segments: list[dict] = []
    seg_by_key: dict[tuple, dict] = {}
    unassigned: list[dict] = []
    for line in flat:
        # Section schemes (stephanus) assign a whole section to one book by its
        # (page, letter) column — boundaries are page-initial and the per-section
        # line numbers are editorial. Line-bearing schemes (bekker) split a
        # book-straddling column by line number. `section` is bookless — every
        # column belongs to the work's single declared book (1), with no
        # manifest book-table lookup at all (its column token, a bare integer,
        # carries no book-boundary grammar for book_for_column to parse).
        if sch.flat_numeric or sch.fragment_scheme:
            # Bookless (dk mirrors `section`'s single-declared-book shape —
            # see scheme.py's dk module doc): no manifest book-table lookup
            # at all, since a dk column ("B30") carries no book-boundary
            # grammar for book_for_column to parse.
            book = 1
        elif sch.has_sections:
            book = manifest.book_for_column(line["column"])
        else:
            book = manifest.book_for_line(line["column"], line["n"])
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
        entry = {"n": line["n"], "text": line["text"]}
        if line.get("joined"):
            entry["joined"] = True
        if "sec" in line:
            entry["sec"] = line["sec"]
        if "wrap" in line:
            entry["wrap"] = line["wrap"]
        if "wrapO" in line:
            entry["wrapO"] = line["wrapO"]
        if "indent" in line:
            entry["indent"] = line["indent"]
        if line.get("sections"):
            entry["sections"] = line["sections"]
        if line.get("role"):
            entry["role"] = line["role"]
        seg["lines"].append(entry)
        # Speaker turn events for this line, keyed by line number within the
        # segment (column). Emitted per-segment so the reader can render the
        # speaker at the char offset where the turn's speech begins.
        for m in line.get("speakers", []):
            seg.setdefault("speakers", []).append(
                {"line": line["n"], "offset": m["offset"], "label": m["label"]}
            )

    return {
        "work": manifest.work_id,
        "edition": manifest.data["work"]["greek_edition"],
        "segments": segments,
        "headings": headings,
        "unassigned_lines": unassigned,
        # Present only for a work whose Greek TEI carries philosopher-heading
        # stubs (Diogenes Laertius); every other work omits the key entirely
        # (stage7_emit's emit_philosophers treats absence/emptiness as "emit
        # nothing" — zero-diff for every work that isn't Diogenes Laertius).
        **({"philosopher_headers": philosopher_headers} if philosopher_headers else {}),
    }


def run(manifest: Manifest) -> Path:
    xml_path = run_export(manifest)
    spine = parse_spine(xml_path, manifest)
    out = BUILD_DIR / "stage1" / "greek_spine.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spine, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
