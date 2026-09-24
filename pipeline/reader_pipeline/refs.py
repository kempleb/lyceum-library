"""Column/line reference utilities, shared across citation schemes.

A *column* is a citation-page token: a Bekker page+side like "1094a", a
Stephanus page+section like "17e", or a book-section book.section like "4.23"
(Marcus Aurelius) or "7.85" (Diogenes Laertius). A *ref* adds a line number,
e.g. "1094a15" or "17e3"; a book-section scheme has no user-facing line, so its
ref grammar is the same dotted token as its column.

Token parsing/sorting dispatches on the work's `Scheme`: passing no scheme (the
default) parses the shared letter grammar (a-e), which serves Bekker sides
(a/b) and Stephanus sections (a-e) identically — "17e" orders before "18a". A
numeric-section scheme (book-section) parses its own dotted grammar and orders
its section component numerically, so "4.9" < "4.10" rather than lexicographic
"4.10" < "4.9".

`column_range` enumerates a rectangular page x side range and is BEKKER-ONLY:
Stephanus/Busse/book-section spans are irregular (works start and end mid-page
and interior pages are not guaranteed to carry every letter), so their expected
column set comes from the observed spine, never from enumeration. Callers on
those schemes must not invoke it.
"""

from __future__ import annotations

import re

# Shared letter grammar (bekker a/b, stephanus a-e). Used when no scheme is
# passed; identical to what the bekker/busse/stephanus schemes carry, so the
# scheme-less default and those schemes parse byte-identically.
_COLUMN_RE = re.compile(r"^(\d+)([a-e])$")
_REF_RE = re.compile(r"^(\d+)([a-e])(\d+)$")
_COL_PREFIX_RE = re.compile(r"^(\d+)([a-e])")


def _verse_line_lineref_key(lineref: str) -> tuple[int, str]:
    """Sort key for a verse-line lineref component (the part after the book
    dot): a plain line reuses `scheme.verse_line_order_key` (int, suffix); a
    declared-lacuna RANGE token ("1094-1101") has no single citable
    position, so it sorts at its START line's key — the range is always
    encountered (in citation order) exactly where its first line would be,
    and no other token shares that start position (see
    docs/wave2-latin-design.md §3.2/§3.3)."""
    from . import scheme as scheme_mod

    if scheme_mod.verse_line_kind(lineref) == "range":
        lineref = lineref.split("-", 1)[0]
    return scheme_mod.verse_line_order_key(lineref)


def column_key(column: str, scheme=None) -> tuple:
    """Sort key for a column token.

    Default (scheme=None) parses the shared a-e grammar -> (page, letter). Pass
    a Scheme to parse its own column grammar; a numeric-section scheme yields
    (book, section) with an int section so "4.9" < "4.10". A flat-numeric
    scheme (`section`) yields (chapter, None) — its column_re has only one
    regex group, so chapters sort purely on the leading int ("2" < "10",
    never lexically); the `None` keeps the tuple 2-shaped for callers that
    unpack it alongside the other schemes (e.g. stage7_emit's emit_sections).
    A dk (Diels-Kranz) scheme yields (series, number, suffix) — series 'A'/
    'B' first (a work's spine only ever carries one, but the token itself
    always names it — see scheme.py's dk module doc), then the number as an
    int ("B9" < "B10", never lexical), then the suffix string with '' (no
    suffix) sorting before any letter ('' < 'a' < 'b' — Python string
    ordering already gives this for free), so B84 < B84a < B84b and
    B126 < B126a < B126b. A verse-line scheme (Lucretius' DRN) yields
    (book, number, suffix) — the SAME (number, suffix) shape as dk's tail,
    computed via `_verse_line_lineref_key` so "1.9" < "1.10" (numeric, never
    lexical) and a declared-lacuna range token sorts at its start line (see
    that helper's own doc comment).

    The flat grammar trims OUTER whitespace only (mirroring citation.ts's
    flat factory: " 5 " is accepted, "5 0" is rejected — internal whitespace
    is never collapsed into a different number)."""
    pattern = scheme.column_re if scheme is not None else _COLUMN_RE
    if scheme is not None and scheme.flat_numeric:
        column = column.strip()
    m = pattern.match(column)
    if not m:
        raise ValueError(f"not a column token: {column!r}")
    if scheme is not None and scheme.flat_numeric:
        return (int(m.group(1)), None)
    if scheme is not None and scheme.numeric_section:
        return (int(m.group(1)), int(m.group(2)))
    if scheme is not None and scheme.fragment_scheme:
        return (m.group(1), int(m.group(2)), m.group(3) or "")
    if scheme is not None and scheme.verse_line_scheme:
        num, suffix = _verse_line_lineref_key(m.group(2))
        return (int(m.group(1)), num, suffix)
    return (int(m.group(1)), m.group(2))


def ref_key(ref: str, scheme=None) -> tuple:
    """Sort key for a full ref like '1103a14' or '17e3' -> (page, letter, line).

    Pass a Scheme to parse its own ref grammar. A numeric-section scheme has no
    user-facing line component (its ref grammar IS its dotted column), so its
    key is the 2-tuple (book, section) — never mixed with a letter-scheme key.
    A flat-numeric scheme (`section`) likewise has no user-facing line; its key
    is the 2-tuple (chapter, None), same shape as column_key's (and the same
    outer-whitespace-only trim). A lineless dk scheme has no user-facing line
    either — its ref grammar IS its column grammar (3 groups: series, number,
    suffix) — so its key is column_key's 3-tuple; a VERSE dk work's ref
    grammar has a 4th group (the line), so its key is the 4-tuple (series,
    number, suffix, line)."""
    pattern = scheme.ref_re if scheme is not None else _REF_RE
    if scheme is not None and scheme.flat_numeric:
        ref = ref.strip()
    m = pattern.match(ref)
    if not m:
        raise ValueError(f"not a ref: {ref!r}")
    if scheme is not None and scheme.flat_numeric:
        return (int(m.group(1)), None)
    if scheme is not None and scheme.numeric_section:
        return (int(m.group(1)), int(m.group(2)))
    if scheme is not None and scheme.fragment_scheme:
        if scheme.lines_user_facing:
            return (m.group(1), int(m.group(2)), m.group(3) or "", int(m.group(4)))
        return (m.group(1), int(m.group(2)), m.group(3) or "")
    if scheme is not None and scheme.verse_line_scheme:
        # Lineless: ref grammar IS the column grammar (§3.1/§3.4) — same key
        # shape as column_key's verse-line branch.
        num, suffix = _verse_line_lineref_key(m.group(2))
        return (int(m.group(1)), num, suffix)
    return (int(m.group(1)), m.group(2), int(m.group(3)))


def line_key(column: str, line: int, scheme=None) -> tuple:
    """The column's sort key with a line number appended: (page, letter, line)
    for a letter scheme, (book, section, line) for a numeric-section scheme."""
    return (*column_key(column, scheme), line)


def column_prefix_key(token: str, scheme=None) -> tuple[int, str] | tuple[int, int] | tuple[int, None]:
    """The sort key of a token's leading column, ignoring any trailing line
    number.

    For a letter scheme, accepts either a bare column ('327a') or a full ref
    ('2a1'); both collapse to (page, letter). Section-scheme (stephanus) book
    assignment compares at this granularity because Plato's book boundaries
    fall on a section letter (page-initial, e.g. 357a) and the per-section line
    numbers are editorial — so a whole section belongs to exactly one book.
    This also lets a book table declare boundaries as either '357a' or '357a1'
    interchangeably.

    A numeric-section scheme (book-section) carries no user-facing line, so its
    dotted token IS the whole column ('4.23'); the prefix key is just the
    column key. Likewise a flat-numeric scheme (`section`): its bare-integer
    token ('5') IS the whole column. A dk scheme is bookless (its single
    declared book covers the whole spine, like `section`) — a bare column
    ('B30') IS the whole token for a lineless work, and a verse work's
    dotted ref ('B8.34') has its line component stripped first (the book
    boundary is never mid-fragment). A verse-line scheme (Lucretius) is
    bookless-per-LINE rather than per-work — its dotted 'book.lineref' token
    has no separate line component either (§3.1/§3.4), so, like
    numeric_section, the prefix key is just the column key."""
    if scheme is not None and (scheme.numeric_section or scheme.flat_numeric or scheme.verse_line_scheme):
        return column_key(token, scheme)
    if scheme is not None and scheme.fragment_scheme:
        base = token.split(".", 1)[0] if scheme.lines_user_facing else token
        return column_key(base, scheme)
    m = _COL_PREFIX_RE.match(token)
    if not m:
        raise ValueError(f"not a column-bearing token: {token!r}")
    return (int(m.group(1)), m.group(2))


def column_range(first: str, last: str, sides: tuple[str, ...] = ("a", "b")) -> list[str]:
    """All columns from `first` to `last` inclusive over `sides` (Bekker only).

    Enumerates the page x side rectangle. `sides` defaults to Bekker's a/b;
    it exists so the Bekker caller is explicit, NOT so other schemes can
    enumerate — Stephanus/Busse/book-section expected columns come from the
    observed spine.
    """
    fp, fs = column_key(first)
    lp, ls = column_key(last)
    out = []
    for page in range(fp, lp + 1):
        for side in sides:
            if (page, side) < (fp, fs) or (page, side) > (lp, ls):
                continue
            out.append(f"{page}{side}")
    return out
