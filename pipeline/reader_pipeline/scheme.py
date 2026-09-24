"""Citation-scheme contract.

A *citation scheme* is the reference system a work is cited by: Bekker pages for
Aristotle (``1094a15``), Busse/CAG pages for Porphyry's Isagoge (``1.5``), or
Stephanus pages for Plato (``2a``). Each scheme differs in

  * how the export nests its structural divs (a flat page div, or a page div
    containing section divs whose letter composes the citation token),
  * the grammar of a *column* token and a full *ref* (column + line),
  * whether line numbers are shown to the reader,
  * how the validator establishes the *expected* column set — enumerate a
    rectangular page x side range (Bekker), or trust the observed spine
    (Busse, Stephanus, whose page/section spans are irregular and per-work).

Every scheme-conditional in the pipeline dispatches on the `Scheme` returned by
`for_manifest()` / `get()` instead of scattering ``== "busse"`` string tests.

Column-token composition:
  * bekker       — the page div already carries the full column ("16a"); no
                   sections. compose_column("16a") -> "16a".
  * busse        — the page div carries a bare page number ("1"); we
                   synthesise a single a-side column. compose_column("1") ->
                   "1a".
  * stephanus    — a page div ("2") nests section divs ("a".."e"); the column
                   is their composition. compose_column("2", "a") -> "2a".
  * book-section — a book div ("4") nests section divs ("23"); the column is
                   their dotted composition. compose_column("4", "23") ->
                   "4.23" (Marcus Aurelius "4.23", Diogenes Laertius "7.85").
                   Unlike stephanus, no columns.json-style lookup is needed to
                   recover the book from a column: the book number IS the
                   column's dotted prefix.
  * section      — a bookless prose scheme (Epictetus' Enchiridion): the page
                   div ("5") IS the column, like bekker, but nests a
                   non-citable <div type="section"> that stage1 flattens into
                   the chapter text (see _parse_flat_chapter). No book
                   wrapper at all — every column belongs to the work's single
                   declared book. compose_column("5") -> "5".
  * verse-line   — a book div ("1") nests <l> line divs whose own @n is
                   either a plain line number with an optional single
                   lowercase suffix ("101", "47a") or, for a declared
                   editorial lacuna, a range ("1094-1101"); the column is
                   their dotted composition, compose_column("1", "101") ->
                   "1.101" (Lucretius' DRN, Wave 2 Batch 2 — design memo
                   docs/wave2-latin-design.md §3.1-3.4). Like book-section,
                   no columns.json-style lookup is needed to recover the
                   book from a column: the book number IS the column's
                   dotted prefix.
  * letter       — a letter div ("47") nests section divs ("3"); the column
                   is their dotted composition, compose_column("47", "3") ->
                   "47.3" (Seneca's Epistulae Morales, Wave 2 Batch 3 —
                   design memo docs/wave2-seneca-design.md §A). Byte-
                   identical grammar to book-section, reused wholesale
                   (`page_div_type="letter"` is the only difference that
                   matters here); the letter IS the book axis (124 letters,
                   124 declared books), the book number IS the column's
                   dotted prefix, exactly as book-section's own book axis.

One further scheme name (ennead) is a registered but unimplemented
`stub=True` entry: present in the registry so a manifest naming it is
recognized (not silently treated as bekker), but every entry point that
would act on its columns (`compose_column`, and preflight manifest
validation) rejects it loudly instead of guessing at an unbuilt grammar.

  * dk           — Diels-Kranz fragment/testimonium numbering (the
                   Presocratics, Wave 1b): a citable "column" is a series
                   letter (A testimonia / B fragments) + number + optional
                   lowercase suffix ("B30", "B84a"), never a page>section
                   composition — its export shape is one flat div PER
                   citable unit (`page_div_type="Fragment"`, no nested
                   section div), so it is parsed by its own dedicated stage1
                   walker (`_parse_fragments`), never by `compose_column`
                   (whose 2-argument page/section signature has no series
                   or suffix slot to begin with — seeschema `fragment_scheme`
                   below and `compose_column`'s dk branch, which raises
                   NotImplementedError for exactly this reason). Bookless
                   (`books: 1`, like `section`); `has_sections=True` (the
                   ordered fragment list is the outline nav, exactly
                   `section`'s per-chapter role); lineless by default
                   (`lines_user_facing=False` — DK fragments are cited by
                   column alone, "B30") with a per-work `citation.lines`
                   override (see `for_manifest`) for a verse work (Parmenides)
                   whose fragments carry real, per-fragment-restarting line
                   numbers cited "B8.34". A chapter DK prints with NO series
                   letter at all (Pythagoras, DK 14 — cited "DK 14, 7", never
                   "14 A7") opts out of the series letter entirely via a
                   per-work `citation.no_series` override (see `for_manifest`
                   below): the column is just number+suffix ("7", "6a"), not
                   composable with `citation.lines` (unevidenced combination).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Scheme:
    name: str
    # TEI @type of the page-level div in the Diogenes export.
    page_div_type: str
    # TEI @type of the nested section div whose letter joins the page number to
    # form a column token, or None when the page div IS the column (bekker) or a
    # whole synthetic column (busse).
    section_div_type: str | None
    # Ordered valid section letters; used for display and to order columns that
    # share a page. Bekker's two "sides" (a/b) play the same structural role.
    section_letters: tuple[str, ...]
    # Whether line numbers within a column are meaningful citation targets shown
    # to the reader. Stephanus cites page+letter only; lines are editorial.
    lines_user_facing: bool
    # How stage2 decides the expected column set: "range" enumerates a
    # page x side rectangle (Bekker only); "observed" trusts the spine's own
    # columns (irregular per-work spans; page numbers not globally unique).
    validation_mode: str
    # Sides column_range enumerates, or None when range enumeration is
    # unsupported (a scheme whose columns must never be enumerated rectangularly).
    range_sides: tuple[str, ...] | None
    # Human name of the citation column, for gutters / reports.
    display_label: str
    # Full column-token regex (no line) and full ref regex (column + line).
    column_re: re.Pattern
    ref_re: re.Pattern
    # Separator compose_column's shared page>section branch joins page and
    # section with: stephanus's "2"+"a" -> "2a" has none; book-section's
    # "4"+"23" -> "4.23" joins with ".". Bekker/busse compose via their own
    # dedicated branches below and ignore this field. Dispatching on this
    # field (rather than adding another `if self.name == ...` string check)
    # is the "dispatch on the Scheme object" design intent noted above.
    column_separator: str = ""
    # True for a scheme name that is registered but not yet implemented (dk,
    # verse-line, ennead) — see module docstring.
    stub: bool = False
    # Whether a column token nests a section division AND the reader shows a
    # per-chapter/section outline (sections.json) in place of chapters.json —
    # mirrors citation.ts's CitationScheme.hasSections. Left None (the
    # default) this is DERIVED from `section_div_type` in __post_init__
    # (True whenever a section div is nested, as for stephanus/book-section);
    # a scheme may instead pass it explicitly to override that derivation —
    # `section` (Epictetus' Enchiridion) has no section_div_type at all (its
    # sub-sections are flattened chapter-internal text, not a separate
    # citable column) but still wants the per-chapter sections.json outline,
    # so its registry entry passes has_sections=True directly.
    has_sections: bool | None = None

    def __post_init__(self) -> None:
        if self.has_sections is None:
            object.__setattr__(self, "has_sections", self.section_div_type is not None)

    @property
    def bekker_native(self) -> bool:
        """True only for the genuine Bekker scheme; other schemes carry
        synthetic/irregular column tokens that skip Bekker-specific checks."""
        return self.name == "bekker"

    @property
    def flat_numeric(self) -> bool:
        """True only for the flat `section` scheme (Epictetus' Enchiridion):
        its column token is a single bare integer with no letter/section axis
        and no book wrapper at all. This is the discriminator stage1_greek.py
        dispatches its own flat-prose parser on, and refs.py's
        column_key/ref_key special-case it — its column_re has only one
        regex group, so there is no second component to unpack."""
        return self.name == "section"

    @property
    def numeric_section(self) -> bool:
        """True when the section axis is open-ended integers (book-section's
        '4.23') rather than a fixed letter axis (bekker a/b, stephanus a-e).

        This is the discriminator refs.py dispatches on: a numeric-section
        token's section component sorts as an int ('4.9' < '4.10'), while a
        letter-axis section sorts by its position in `section_letters`. Every
        letter scheme lists its letters; book-section deliberately carries an
        empty `section_letters` because that field's ordering semantics do not
        apply to it (see its registry entry). `section` also carries an empty
        `section_letters` (no letter axis either) but is excluded here — it is
        a flat bookless token, not a dotted book.section one; `flat_numeric`
        above is its own discriminator. `dk` likewise carries an empty
        `section_letters` (its series letter is not an ordering axis the way
        stephanus' a-e is) but is excluded here too — its own discriminator
        is `fragment_scheme` below."""
        return (
            self.has_sections and not self.section_letters
            and not self.flat_numeric and not self.fragment_scheme
        )

    @property
    def verse_line_scheme(self) -> bool:
        """True only for `verse-line` (Lucretius' DRN, Wave 2 Batch 2): its
        column is a (book, lineref) pair whose lineref carries its own
        richer grammar (an optional suffix letter, or a range form for a
        declared lacuna) rather than book-section's plain section integer —
        excluded from `numeric_section` above precisely because of that
        richer grammar (see that property's own doc comment). This is the
        discriminator refs.py's column_key/ref_key/column_prefix_key,
        stage1_latin's verse walker, stage2_validate's structural checks,
        stage7_emit's citation-order sort, and preflight's book-schema/
        dist-level gates all dispatch on, the same way `fragment_scheme`
        lets those same call sites recognize dk."""
        return self.name == "verse-line"

    @property
    def letter_scheme(self) -> bool:
        """True only for `letter` (Seneca's Epistulae Morales, Wave 2 Batch
        3 — docs/wave2-seneca-design.md §A): its column grammar, dotted
        composition, and book-recovery are byte-identical to book-section's
        (also true of `numeric_section`, which derives True for this scheme
        the same way it does for book-section — see that property's own
        doc). This is the discriminator stage1_latin's `parse_spine`
        dispatches its `_parse_letters` walker on (page="letter", the letter
        IS the book axis, unlike book-section's chapter-as-page), the same
        way `verse_line_scheme` lets stage1 recognize Lucretius' DRN."""
        return self.name == "letter"

    @property
    def fragment_scheme(self) -> bool:
        """True only for `dk` (Diels-Kranz): its column is a (series, number,
        suffix) triple, its export shape is one flat div per citable
        fragment/testimonium (no nested section div), and it is bookless
        like `section` — but it is its own scheme, not a variant of
        `flat_numeric`, because its column grammar carries a series letter
        `compose_column` has no parameter for. Stage1 dispatches its own
        `_parse_fragments` walker on this predicate; refs.py's column/ref
        key functions and preflight's book-boundary validation dispatch on
        it the same way `flat_numeric`/`numeric_section` do."""
        return self.name == "dk"

    def compose_column(self, page_n: str, section_n: str | None = None) -> str:
        """The column token for a page div (and, for section schemes, the
        current section letter)."""
        if self.stub:
            raise NotImplementedError(f"scheme {self.name!r} is registered but not implemented")
        if self.fragment_scheme:
            # dk's column is (series, number, suffix) — composed directly by
            # _parse_fragments from a div's own @n plus the work's declared
            # series, never through this page/section-shaped signature.
            raise NotImplementedError(
                "scheme 'dk' composes its column (series+number+suffix) in "
                "stage1_greek._parse_fragments, not via compose_column"
            )
        if self.name in ("bekker", "section"):
            return page_n
        if self.name == "busse":
            return f"{page_n}a"
        # stephanus, book-section (and any future page>section scheme)
        return f"{page_n}{self.column_separator}{section_n}"


# Shared line-bearing column grammar. Bekker sides are a/b; Stephanus letters
# a-e. refs.py parses the same range, so a single a-e regex serves both.
_COLUMN_RE = re.compile(r"^(\d+)([a-e])$")
_REF_RE = re.compile(r"^(\d+)([a-e])(\d+)$")

# book-section's dotted grammar: book.section (Marcus "4.23", DL "7.85"). No
# [a-e] letter axis at all — refs.py's column_key/ref_key/column_range are
# hardcoded to the shared a-e grammar above and do NOT parse this token; see
# the module docstring and the deferred-to-Wave-1a note this WP reports.
# No user-facing line component exists for this scheme (see
# `lines_user_facing` below), so the same regex serves as both column and ref.
_DOTTED_COLUMN_RE = re.compile(r"^(\d+)\.(\d+)$")

# verse-line's grammar (Lucretius' DRN, continuous verse with a book axis —
# design memo docs/wave2-latin-design.md §3.1-3.2): the citable unit is
# book.line; book is the page axis (book-section's book level, reused), and
# the line — the column-token grammar within a book — is a bare number with
# an optional single lowercase suffix letter (the observed "47a" insertions),
# no leading-zero normalization (same rationale as dk's _DK_COLUMN_RE below:
# PHI has none, so a literal digit run is preserved rather than defensively
# stripped — see the "047" case in test_scheme.py and this grammar's parity
# with citation.ts's identical VERSE_LINE_RE).
_VERSE_LINE_RE = re.compile(r"^([0-9]+)([a-z]?)$")
# A lacuna range token (§3.2): valid ONLY as a spine-internal token for an
# editor-marked gap div (n="1094-1101"), never general citation input a
# reader types — the acceptance-against-a-declared-lacuna policy is a LATER
# gate (preflight), out of scope for this scheme-grammar layer, which only
# parses and classifies it (see verse_line_kind below).
_VERSE_LINE_RANGE_RE = re.compile(r"^([0-9]+)([a-z]?)-([0-9]+)([a-z]?)$")
# The full dotted column: book '.' lineref, where lineref is either form
# above — mirrors _DOTTED_COLUMN_RE's shape but with a richer second
# component. Lineless (lines_user_facing=False — the line IS the column,
# §3.1/§3.4), so the same regex serves as both column and ref, same as
# book-section/section.
_VERSE_LINE_COLUMN_RE = re.compile(r"^([0-9]+)\.([0-9]+[a-z]?(?:-[0-9]+[a-z]?)?)$")


def verse_line_kind(lineref: str) -> str:
    """Classify a verse-line lineref (the part after the book dot, e.g. the
    "101" in "1.101" or "1094-1101" in "1.1094-1101") as "line" or "range" —
    mirrors citation.ts's `isVerseLineRange`. Raises ValueError if neither
    grammar matches."""
    if _VERSE_LINE_RANGE_RE.match(lineref):
        return "range"
    if _VERSE_LINE_RE.match(lineref):
        return "line"
    raise ValueError(f"not a verse-line lineref: {lineref!r}")


def verse_line_order_key(lineref: str) -> tuple[int, str]:
    """Sort key for a single (non-range) verse-line lineref: (int(number),
    suffix), so 47 < 47a < 48 and 99 < 100 (numeric, never lexicographic) —
    reuses dk's proven '' < 'a' < 'b' ordering (design memo §3.1). Exported
    for the later emit-time citation-order sort (§3.3); mirrors
    citation.ts's `verseLineOrderKey` exactly. Raises ValueError for a range
    token (no single sort position — see verse_line_kind) or a malformed
    one."""
    m = _VERSE_LINE_RE.match(lineref)
    if not m:
        raise ValueError(f"not a verse-line token: {lineref!r}")
    return (int(m.group(1)), m.group(2) or "")


# `section`'s flat grammar: a bare chapter integer (Epictetus' Enchiridion
# "5"). No letter axis and no dotted book prefix at all, so the same regex
# serves as both column and ref (this scheme has no user-facing line either —
# see `lines_user_facing` below). Explicit [0-9] rather than \d: Python's \d
# matches Unicode digits ("٥"), which citation.ts's JS \d does not — the two
# registries must agree on the grammar exactly (see the TS/Python parity
# tests), and a chapter number is ASCII by construction.
#
# The optional `-[0-9]+` tail (Epicurus' Vatican Sayings, Wave 3): the
# Arrighetti/TLG export carries exactly one div whose own @n is a compound
# "56-57" (a single manuscript-continuous saying spanning two traditional
# numbers, verified against the export — not a range-gap marker; see
# scheme.py module doc's dk `expected_gaps` for the unrelated concept that
# name might suggest). It is one whole, atomic column token, never split;
# `column_key`/`column_prefix_key` sort it on its leading number only
# (group 1), which is safe here because no separate "56" or "57" div exists
# in this work's spine to collide with.
_FLAT_COLUMN_RE = re.compile(r"^([0-9]+)(?:-[0-9]+)?$")

# dk's column grammar (Diels-Kranz): a series letter (A testimonia / B
# fragments, canonical uppercase), a number (no leading-zero normalization —
# the TLG export has none), and an optional single lowercase suffix letter
# (covers every observed case: 1a, 3a, 3b, 14a, 49a, 67a, 84a, 84b, 101a,
# 125a, 126a, 126b, 40a, 43a, 44a, 46a, 46b, 15a — verified against the
# Heraclitus/Parmenides groundwork reports). No line component: dk is
# lineless by default (a fragment is cited "B30", not "B30.1"); a verse
# work's manifest opts a real line component in via `citation.lines` (see
# for_manifest below), which is the ONLY thing that changes ref_re/
# lines_user_facing — the column grammar itself never changes.
#
# Case-parity contract with citation.ts's matching `DK_COLUMN_RE` (identical
# pattern): STRICT on both sides, always — this side has no equivalent of
# citation.ts's separate, deliberately wider `DK_INPUT_COLUMN_RE`/
# `DK_INPUT_REF_RE` (case-insensitive input, canonicalized), because those
# exist ONLY at the TypeScript citation-jump UI layer (a reader hand-typing
# "b30"). Every manifest/emitted column this side ever parses is already
# canonical — there is no "jump layer" in the pipeline for this grammar to
# be lenient about. See citation.ts's DK_INPUT_COLUMN_RE doc comment for the
# full contract statement.
_DK_COLUMN_RE = re.compile(r"^([AB])([0-9]+)([a-z]?)$")
# A verse dk work's ref grammar: column + dot + line ("B8.34" — the
# scholarly convention for fragment.line, not book-section's colon; see
# citation.ts's matching dk formatCitation doc comment). Line is an
# unadorned integer; per-fragment line numbering restarts at 1 (Parmenides).
_DK_VERSE_REF_RE = re.compile(r"^([AB])([0-9]+)([a-z]?)\.([0-9]+)$")

# A regex that can never match, for a stub scheme's column/ref fields — its
# grammar isn't designed yet, so nothing should ever successfully parse
# against it (compose_column raises before either field would be consulted).
_NEVER_RE = re.compile(r"(?!)")

# A no-series dk work's column grammar (Pythagoras, DK ch. 14 — see
# `citation.no_series` in `for_manifest` below): DK prints this chapter's
# testimonia with NO A/B series letter at all (cited "DK 14, 7", never
# "14 A7") — a real, verified DK6/export characteristic (confirmed against
# tlg0632006.xml: every div's own @n is a bare number+optional-suffix, and
# the work's <sourceDesc> itself carries no series letter either), not an
# extraction gap. The leading `()` keeps the SAME 3-group shape as
# `_DK_COLUMN_RE` (group 1 always matches empty) so every consumer that
# unpacks (series, number, suffix) — refs.py's column_key/ref_key,
# stage1_greek's div-@n composition — works unchanged with series == "".
# "Case-parity contract with citation.ts's matching `DK_NO_SERIES_COLUMN_RE`"
# is deliberately narrow: it covers ONLY strictness (uppercase-series/
# lowercase-suffix canonicalization — see `_DK_COLUMN_RE`'s own case-parity
# comment above, which this one inherits), never capture-GROUP SHAPE. The
# two sides genuinely differ there, on purpose: this regex is 3 groups (the
# always-empty placeholder above); citation.ts's `DK_NO_SERIES_COLUMN_RE` is
# 2 groups (`/^([0-9]+)([a-z]?)$/`, no placeholder) because its consumers
# (parseColumnToken's `canonicalNoSeriesColumn`) never unpack a 3-tuple the
# way this side's refs.py/stage1_greek consumers do — there is no shared
# "(series, number, suffix)" unpacking contract on the TS side to keep a
# placeholder group in sync with. See citation.test.ts's capture-shape note
# test for the asserted (Python 3 / TS 2) group counts.
_DK_NO_SERIES_COLUMN_RE = re.compile(r"^()([0-9]+)([a-z]?)$")


def _stub_scheme(name: str, display_label: str) -> Scheme:
    """A registered-but-unimplemented scheme (see module docstring): present
    in SCHEMES so `get()` recognizes the name instead of a caller mistaking
    an unknown name for one, but every field is a placeholder and `stub=True`
    makes `compose_column` (and preflight manifest validation) reject it."""
    return Scheme(
        name=name,
        page_div_type="",
        section_div_type=None,
        section_letters=(),
        lines_user_facing=False,
        validation_mode="observed",
        range_sides=None,
        display_label=display_label,
        column_re=_NEVER_RE,
        ref_re=_NEVER_RE,
        stub=True,
    )


SCHEMES: dict[str, Scheme] = {
    "bekker": Scheme(
        name="bekker",
        page_div_type="Bekker-page",
        section_div_type=None,
        section_letters=("a", "b"),
        lines_user_facing=True,
        validation_mode="range",
        range_sides=("a", "b"),
        display_label="Bekker page",
        column_re=_COLUMN_RE,
        ref_re=_REF_RE,
    ),
    "busse": Scheme(
        name="busse",
        page_div_type="page",
        section_div_type=None,
        section_letters=("a",),
        lines_user_facing=True,
        validation_mode="observed",
        range_sides=None,
        display_label="CAG page",
        column_re=_COLUMN_RE,
        ref_re=_REF_RE,
    ),
    "stephanus": Scheme(
        name="stephanus",
        page_div_type="Stephanus-page",
        section_div_type="section",
        section_letters=("a", "b", "c", "d", "e"),
        lines_user_facing=False,
        validation_mode="observed",
        range_sides=None,
        display_label="Stephanus page",
        column_re=_COLUMN_RE,
        ref_re=_REF_RE,
    ),
    "book-section": Scheme(
        name="book-section",
        # Verified against build/export/.../tlg0562001.xml (Marcus Aurelius,
        # Farquharson TEI, Wave 1a-D): div[@type="Book"][@n=1..12] nests
        # div[@type="chapter"][@n] — the citation-bearing unit (the "23" in
        # "4.23"). The XML also nests a THIRD level, div[@type="section"],
        # inside each chapter (usually one, up to 10 for 1.16); that level is
        # NOT a Scheme concept — stage1_greek flattens it into the chapter's
        # text, it is never a separate citable column.
        page_div_type="Book",
        section_div_type="chapter",
        # Sections are open-ended integers ("4.23"), not a fixed a-e letter
        # axis — this field's letter-ordering semantics don't apply here.
        section_letters=(),
        lines_user_facing=False,
        validation_mode="observed",
        range_sides=None,
        display_label="Book.section citation",
        column_re=_DOTTED_COLUMN_RE,
        ref_re=_DOTTED_COLUMN_RE,
        column_separator=".",
    ),
    "section": Scheme(
        name="section",
        # Verified against the Diogenes export of the Enchiridion: chapter
        # divs sit at the top level (no Book wrapper) as
        # div[@type="Chapter"][@n] — capitalized "Chapter", unlike
        # book-section's lowercase "chapter". A nested div[@type="section"]
        # (the chapter's un-cited sub-paragraph breaks) is not a Scheme
        # concept — stage1_greek's _parse_flat_chapter flattens it into the
        # chapter text, exactly as book-section's chapter flatten does.
        page_div_type="Chapter",
        section_div_type=None,
        section_letters=(),
        lines_user_facing=False,
        validation_mode="observed",
        range_sides=None,
        display_label="Chapter citation",
        column_re=_FLAT_COLUMN_RE,
        ref_re=_FLAT_COLUMN_RE,
        # Overrides the has_sections default (section_div_type is None here,
        # which would derive False) — this scheme still wants the
        # per-chapter sections.json outline. See the field's doc comment.
        has_sections=True,
    ),
    "dk": Scheme(
        name="dk",
        # Verified against the Heraclitus export (build/export/.../
        # tlg0626001.xml, tlg0626002.xml): a citable unit is one flat
        # div[@type="Fragment"][@n="30"] — no nested section div at all,
        # unlike every page>section scheme above.
        page_div_type="Fragment",
        section_div_type=None,
        section_letters=(),
        lines_user_facing=False,
        validation_mode="observed",  # DK numbering has real gaps (B84/B109)
        range_sides=None,
        display_label="Diels-Kranz citation",
        column_re=_DK_COLUMN_RE,
        ref_re=_DK_COLUMN_RE,  # lineless by default; a verse work overrides both
        # The ordered fragment list IS the outline nav (mirrors `section`'s
        # override — see that entry's comment and citation.ts's hasSections).
        has_sections=True,
    ),
    "verse-line": Scheme(
        name="verse-line",
        # Provisional: named to match the design memo's stated shape
        # (docs/wave2-latin-design.md §6 — "<div type='book'>/<l n>" walk,
        # identical shape to book-section's own book/chapter walk) but NOT
        # YET re-verified against the real Lucretius PHI export the way
        # book-section's "Book"/"chapter" pair was (see that entry's own
        # comment above) — this task is the scheme-GRAMMAR layer only (no
        # stage1 wiring; that lands with the Wave 2 Batch 2 recon). A
        # `citation.div_types` override (the same seam book-section already
        # uses for PHI's lowercased "book") is available if the real export
        # needs a different pair.
        page_div_type="book",
        section_div_type="l",
        section_letters=(),
        lines_user_facing=False,     # the line IS the column -- no sub-line axis
        validation_mode="observed",  # non-monotonic order (transpositions, §3.3)
        range_sides=None,
        display_label="Verse/line citation",
        column_re=_VERSE_LINE_COLUMN_RE,
        ref_re=_VERSE_LINE_COLUMN_RE,  # lineless: ref grammar IS the column grammar
        column_separator=".",
        # Overrides the has_sections default (section_div_type is not None
        # here, which would derive True) -- a verse-line book runs to
        # ~1000+ lines; unlike book-section's tens-of-chapters-per-book
        # outline, a per-line sections.json outline nav would be unusable.
        # Same override shape as `section`'s (has_sections=True override)
        # and dk's, just the other direction.
        has_sections=False,
    ),
    "ennead": _stub_scheme("ennead", "Ennead citation"),
    "letter": Scheme(
        name="letter",
        # Verified against phi1017015.xml (Seneca's Epistulae Morales,
        # docs/wave2-seneca-design.md §A): a flat div[@type="letter"][@n]
        # (letter 1..124, the page axis) nests div[@type="section"][@n] (the
        # column) — structurally book-section's own book/chapter shape with
        # page_div_type="letter", not a new grammar (design note §A: "reuses
        # that grammar wholesale rather than inventing one"). The dotted
        # column token ("47.3") composes via the shared page>section branch
        # in compose_column below; book_for_column recovers the letter (124
        # of them) from the column's dotted prefix exactly as book-section
        # recovers a book, unchanged.
        page_div_type="letter",
        section_div_type="section",
        # Open-ended integer section axis (numeric_section derives True
        # below, mirroring book-section) -- no fixed letter axis.
        section_letters=(),
        lines_user_facing=False,
        validation_mode="observed",
        range_sides=None,
        display_label="Letter.section citation",
        column_re=_DOTTED_COLUMN_RE,
        ref_re=_DOTTED_COLUMN_RE,
        column_separator=".",
    ),
}


def get(name: str | None) -> Scheme:
    """The Scheme for a citation-scheme name; None/"" default to bekker."""
    return SCHEMES[name or "bekker"]


# Recognized keys under a manifest's `citation.div_types` override block (see
# for_manifest below). The nested section div's @type was the only override
# needed through Wave 1b — Diogenes Laertius' book-section export nests
# div[@type="section"] siblings directly under its Book divs, not "chapter"
# like Marcus Aurelius' Meditations (the book-section scheme's registered
# default, scheme.py:246). Wave 2 Batch 1a (Cicero, PHI) added `page`: PHI's
# book-section export lowercases the outer div's own @type (`<div
# type="book">`, verified against phi0474055.xml), unlike every TLG
# book-section export's capitalized `<div type="Book">` — a real per-corpus
# (not per-work) convention difference, not a one-off. A key outside this set
# is a manifest-authoring mistake and must be rejected loudly rather than
# silently ignored — see preflight.py's pre-check, which runs this same set
# BEFORE calling for_manifest so the rejection lands as a collected Problem
# (not an uncaught exception that aborts validating every other manifest,
# mirroring the existing scheme-name/stub pre-checks there).
DIV_TYPE_OVERRIDE_KEYS = {"page", "section"}


def for_manifest(manifest) -> Scheme:
    """The Scheme a manifest declares under `citation.scheme` (default bekker),
    with any `citation.div_types` override applied.

    Accepts anything with a `.data` dict (Manifest) or a plain dict.

    `citation.div_types.section` overrides the scheme's `section_div_type`
    (e.g. book-section's registered "chapter") for a work whose TEI export
    nests a differently-named section div under the same page_div_type —
    Diogenes Laertius nests div[@type="section"], not "chapter".
    `citation.div_types.page` overrides the scheme's `page_div_type` (e.g.
    book-section's registered "Book") for a work whose TEI export names the
    outer div differently — PHI's Latin book-section exports use lowercase
    "book". Absent either override, the scheme's registered constant is used
    unchanged. An unknown key raises loudly (see DIV_TYPE_OVERRIDE_KEYS);
    callers that have already validated the manifest (preflight) pre-check
    the key set themselves so this never raises mid-run for them."""
    data = getattr(manifest, "data", manifest)
    citation = (data.get("citation") or {}) if isinstance(data, dict) else {}
    name = citation.get("scheme")
    sch = get(name)
    div_types = citation.get("div_types")
    if div_types:
        if not isinstance(div_types, dict):
            raise ValueError("citation.div_types must be an object")
        unknown = set(div_types) - DIV_TYPE_OVERRIDE_KEYS
        if unknown:
            raise ValueError(
                f"citation.div_types has unknown override key(s) {sorted(unknown)}; "
                f"only {sorted(DIV_TYPE_OVERRIDE_KEYS)} is recognized"
            )
        page_override = div_types.get("page")
        if page_override is not None:
            if not isinstance(page_override, str) or not page_override:
                raise ValueError("citation.div_types.page must be a non-empty string")
            sch = replace(sch, page_div_type=page_override)
        section_override = div_types.get("section")
        if section_override is not None:
            if not isinstance(section_override, str) or not section_override:
                raise ValueError("citation.div_types.section must be a non-empty string")
            sch = replace(sch, section_div_type=section_override)
    lines_override = citation.get("lines")
    if lines_override is not None:
        if not sch.fragment_scheme:
            raise ValueError(
                f"citation.lines is only meaningful for scheme 'dk', not {sch.name!r}"
            )
        if lines_override is True:
            # A verse dk work (Parmenides): fragments carry real, citable
            # per-fragment-restarting line numbers ("B8.34") — the ONLY
            # per-work override seam this scheme has (mirrors book-section/
            # DL's div_types override above); the column grammar itself is
            # unchanged. See scheme.py module docstring's dk entry and
            # citation.ts's matching `hasUserFacingLines` composition.
            sch = replace(sch, lines_user_facing=True, ref_re=_DK_VERSE_REF_RE)
        elif lines_override is not False:
            raise ValueError("citation.lines must be true or false")
    no_series_override = citation.get("no_series")
    if no_series_override is not None:
        if not sch.fragment_scheme:
            raise ValueError(
                f"citation.no_series is only meaningful for scheme 'dk', not {sch.name!r}"
            )
        if no_series_override is True:
            # A DK chapter printed WITHOUT a series letter (Pythagoras, DK
            # 14 — see module docstring's `dk` entry and the
            # `_DK_NO_SERIES_COLUMN_RE` comment above). Not composable with
            # `citation.lines` — no chapter needing both has been observed,
            # and silently picking a 4-group grammar for an unevidenced
            # combination would guess at a shape this scheme hasn't proven.
            if sch.lines_user_facing:
                raise ValueError(
                    "citation.no_series with citation.lines is not implemented"
                )
            sch = replace(sch, column_re=_DK_NO_SERIES_COLUMN_RE, ref_re=_DK_NO_SERIES_COLUMN_RE)
        elif no_series_override is not False:
            raise ValueError("citation.no_series must be true or false")
    return sch
