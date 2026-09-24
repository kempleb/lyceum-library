"""Shared lined-source machinery for stage-1 text producers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Callable

from lxml import etree


@dataclass(frozen=True)
class LinedAlphabet:
    # `is_letter` and `fold_wrap_final` are kept per-alphabet (rather than
    # removed) for construction-site clarity and any future per-work use,
    # but the wrap machinery below (`_is_wrap_candidate`, `_apply_lined_
    # wraps`, `_apply_lined_cross_column_wraps`) no longer calls either --
    # it uses the fixed script-union `_is_wrap_letter` and the universal
    # `_fold_hyphen_final_sigma` instead (2026-08-30 cross-script wrap fix,
    # see `_is_wrap_letter`'s own comment below).
    is_letter: Callable[[str], bool]
    fold_wrap_final: Callable[[str], str]
    name: str
    # Characters that, when glued directly onto a wrapped word's own start,
    # are part of that word's TOKEN SURFACE for this alphabet -- so the
    # fragment-start advance below (`_apply_lined_wraps`) must land ON one
    # of these, never skip past it. Mirrors stage3_tokenize.py's `_surface()`
    # edge-trim: a character in stage3's `_PUNCT` is stripped from `t` (skip
    # it here too, unchanged Greek behavior -- the glued-curly-quote fix),
    # a character NOT in `_PUNCT` survives into `t` (stop here). Greek's
    # glued line-start punctuation (a curly opening quote, U+2018) IS in
    # `_PUNCT`; Latin's leading ASCII apostrophe (`'honestum`, PHI's
    # quotation-opener convention) is deliberately NOT, per stage3_tokenize.
    # `_to_latin_lookup_key`'s docstring. See `pipeline/tests/
    # test_stage3_latin.py::test_latin_leading_ascii_apostrophe_stripped_
    # from_key_not_surface`.
    frag_start_glued_chars: str = ""


def _line_text(el: etree._Element) -> str:
    """Flatten an element's text, collapsing whitespace."""
    text = "".join(el.itertext())
    return re.sub(r"\s+", " ", text).strip()


_SECTION_N_RE = re.compile(r"^(\d+)(?:,(\d+))?$")

# A paragraph-opening print-line's rend attribute in the Discourses export:
# Schenkl's own first-line indent, `indent(1)` for an ordinary paragraph
# open, deeper `indent(2)`/`indent(3)` for quoted/inset matter (390/53/4
# work-wide -- John's ruling 2026-08-29: render the inset, "as long as it
# doesn't screw up the lines"). Any OTHER `rend` value on an `<l>` is
# unrecognized and must fail loudly rather than silently drop the signal.
_LINE_INDENT_RE = re.compile(r"^indent\((\d+)\)$")

# The one non-whitespace HARD token boundary in stage3_tokenize.py's own
# tokenizing regex (`r"[^\s—]+"`, stage3_tokenize.py ~:261): an em dash
# splits two raw token matches apart even with NO surrounding whitespace
# ("Em-dashes glue clauses together with no spaces; they are separators, not
# part of any token" -- that function's own comment). `_word_start` below
# must mirror this exact boundary set, not just whitespace, or its back-walk
# overshoots straight through a glued em dash (see
# test_section_paragraphs_hyphen_crossing_snap_stops_at_glued_em_dash).
# Duplicated as a single-character literal rather than imported -- same call
# as `_is_greek_letter`'s docstring above: the two stages have no other
# coupling, and importing stage3_tokenize here for one character is not
# worth introducing it.
_STAGE3_HARD_SEPARATORS = "—"


# --- Cross-script wrap letter test (2026-08-30) -----------------------------
# A print-line wrap's letters do not always belong to the WORK's own
# language: an editor's citation glued into a Greek work sets the editor's
# name in Latin (Lives 1.67, "(Her-" / "cher 637)."), and a Latin philosophical
# work quotes a Greek technical term whole (De Finibus 1.15 "σκοτει-" / "νός",
# 3.35 "πά-" / "θη", 3.52 "προηγ-" / "μένον"; De Officiis 1.8 "κατ-" /
# "όρθωμα"; the Tusculans 1.37 "νεκυο-" / "μαντεῖα", 4.21 "κατηγο-" /
# "ρήματα" -- 7 loci corpus-wide, matching the 4.5 export's own rejoin of all
# seven as whole words). The wrap machinery below must recognize a wrap or
# continuation letter of EITHER script, not just the alphabet the calling
# work is nominally keyed to -- so its letter test is a fixed script-UNION,
# never `alphabet.is_letter`.
#
# Duplicated (not imported) from stage1_greek._is_greek_letter and
# stage1_latin._is_latin_letter: `lined.py` is imported BY both of those
# modules (see GREEK_LINED/LATIN_LINED below), so importing either back INTO
# lined.py would cycle. Same "no other coupling" precedent as those
# functions' own docstrings.
def _is_greek_letter_for_wrap(ch: str) -> bool:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK") and unicodedata.category(ch).startswith("L")


def _is_latin_letter_for_wrap(ch: str) -> bool:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("LATIN") and unicodedata.category(ch).startswith("L")


def _is_wrap_letter(ch: str) -> bool:
    """Script-union letter test for the wrap machinery (see comment above):
    True for a Greek OR a Latin letter, regardless of which alphabet the
    calling work is nominally keyed to."""
    return _is_greek_letter_for_wrap(ch) or _is_latin_letter_for_wrap(ch)


# Greek print-house convention: a word broken across a print line is always
# typeset with the LINE-FINAL form of sigma (ς) immediately before the wrap
# hyphen, even when that sigma sits in MEDIAL position once the word is
# rejoined -- Schenkl prints "προς-" / "ήκει" for the one word προσήκει,
# never the medial "προσ-". A closing editorial siglum can sit between that
# sigma and the wrap hyphen (for example, "προ<ς>-"). Look back through a
# trailing run of `>`/`]` and fold the exposed ς to σ. The substitution is
# length-preserving, and every other fragment -- including any fragment with
# no final ς, which covers ordinary Latin -- is returned unchanged. Applied
# universally in the wrap join step below (both alphabets), not gated on
# which alphabet the calling work is nominally keyed to: a Greek fragment
# embedded in a Latin work (see the cross-script comment above) needs the
# same fold, and the identity behavior on pure Latin text means this is a
# no-op for ordinary Latin wraps.
def _fold_hyphen_final_sigma(fragment: str) -> str:
    return re.sub(r"ς(?=[>\]]*$)", "σ", fragment)


def _word_start(text: str, pos: int, *, alphabet: LinedAlphabet) -> int:
    """The char index where the SURFACE word containing `text[pos]` began,
    scanning backward from `pos` while the preceding character is not a
    stage3_tokenize.py token boundary -- whitespace or `_STAGE3_HARD_
    SEPARATORS` (currently just the em dash), not just alphabetic and not
    just whitespace. Used by `_chapter_sections` to SNAP a section boundary
    whose remapped offset lands mid-word (a print-line hyphen wrap
    straddling the section boundary) back to the start of that straddling
    word -- the same word stage3's own tokenizer would delimit, so the
    snapped section boundary never disagrees with where a token actually
    starts.

    Grok-4.5 content verification (2026-07-16) found the original
    alphabetic-only walk undershoots whenever the straddling word carries an
    attached non-letter with no intervening space: an opening curly quote
    glued directly onto the wrap's first letter (Discourses 1.9 sec 30,
    2.10 sec 13, 3.8 sec 4 -- `'Sigma...` snaps to the Sigma, stranding the
    quote on the PRIOR section) or an editorial siglum embedded inside the
    wrap word itself (1.23 sec 7: `ana<sigma>trephesthai` snaps to the
    `t` after `>`, stranding `ana<sigma>` on the prior section). Both are
    the same shape: the character immediately before the alpha-run boundary
    is non-alpha but ALSO non-whitespace, i.e. still part of the same
    surface word (no space separates them) -- so the correct snap target is
    the whitespace boundary, not the alphabetic-run boundary. This also
    matches the token contract elsewhere in this pipeline: a token's
    surface form `t` is the literal substring, siglum/punctuation included,
    never just its alphabetic core.

    A GPT-5.6-Sol-High confirm review (2026-07-16) then found the
    whitespace-only walk OVERSHOOTS in the opposite direction: a glued em
    dash ("λόγος—ἀποδο-", no spaces at all) is not whitespace either, so the
    old walk sailed straight through it and back into the PRECEDING clause,
    dragging "λόγος—" into the new section along with the straddling word.
    Stopping the walk at either boundary class fixes both directions at
    once."""
    while pos > 0 and not text[pos - 1].isspace() and text[pos - 1] not in _STAGE3_HARD_SEPARATORS:
        pos -= 1
    return pos


def _is_wrap_candidate(text: str, *, alphabet: LinedAlphabet) -> bool:
    """Whether ``text`` ends in a guarded print-line wrap hyphen.

    The letter test is the script-union `_is_wrap_letter`, not `alphabet.
    is_letter` -- a wrapped word's own script does not always match the
    work's nominal alphabet (see the cross-script comment above
    `_is_wrap_letter`). `alphabet` is kept as a parameter only to thread
    through to `_word_start` below, unchanged."""
    if not text.endswith("-") or len(text) <= 1:
        return False
    if _is_wrap_letter(text[-2]):
        return True
    if text[-2] not in ">]":
        return False
    start = _word_start(text, len(text) - 1, alphabet=alphabet)
    return any(_is_wrap_letter(ch) for ch in text[start:-1])


def _lined_chapter_lines(
    stripped_chap_div,
    section_div_type: str | None = None,
    *,
    alphabet: LinedAlphabet,
    column: str | None = None,
) -> list[dict]:
    """Per-Schenkl-print-line `[{"n", "text", "sec"?, "indent"?}]` for a
    lined chapter/column div.

    `section_div_type` selects the walk (docs/lined-rollout-plan.md
    Ruling 1a):
      - a string (`"section"` for Discourses): walk
        `stripped_chap_div`'s direct
        <div type=section_div_type> children in document order and, within
        each, its <l> children in document order (title stub already
        excluded by `_strip_title_section` before this is called, mirroring
        `_parse_flat_book_section`'s non-lined path). Every emitted entry
        carries `sec`, the enclosing section's own TLG number.
      - `None` (`_parse_flat_chapter`'s lined branch — the five wave-1 flat
        `section`-scheme works whose column div IS the citable/leaf unit,
        Ruling 1c): walk `stripped_chap_div`'s own <l> children directly, in
        document order, and stamp NO `sec` at all — there is no sub-column
        granularity below the column to record; the column number is
        already the segment id and already printed in the block header. An
        `<l n="t">` here is an ordinary body line, never skipped (Ruling 3 —
        e.g. Pythocles' greeting lives inside its own numbered section, not
        a dropped title div; skipping it would remove text from the corpus,
        which invariant I4 forbids).

    `n` is a per-chapter/column running ordinal, 1..N — NOT the TLG <l> @n,
    which restarts inside every section (docs/lined-source-plan.md Q1.1).
    `sec` (string mode only) is the enclosing section's own TLG number;
    Schenkl's one merged "25,26" (Discourses 2.13) is recorded under its
    first number, matching `_chapter_sections`. Text is `_line_text(l)`, not
    yet hyphen-rejoined — `_apply_lined_wraps` below does that pass
    separately, since a wrap can straddle a section boundary (Q1.3) while
    this function's job is purely the section -> line (or column -> line)
    walk.

    `indent` (John's ruling 2026-08-29) is the `<l>`'s own `@rend="indent(N)"`
    level, present only when that attribute is set — a paragraph's
    first-line inset that Schenkl prints and Diogenes shows. A visual inset
    only: it never touches `text`, tokens, `sec`, or the wrap/join channel.
    An `<l>` with some OTHER `@rend` value is unrecognized and fails loudly
    rather than silently dropping the signal."""
    out: list[dict] = []
    n = 0
    if section_div_type is None:
        for l in stripped_chap_div.iter("{*}l"):
            text = _line_text(l)
            if not text:
                continue
            n += 1
            entry = {"n": n, "text": text}
            rend = l.get("rend")
            if rend:
                im = _LINE_INDENT_RE.match(rend)
                if not im:
                    raise ValueError(
                        f"unrecognized <l> @rend={rend!r} (line n={n})"
                    )
                entry["indent"] = int(im.group(1))
            out.append(entry)
        return out
    matching_divs = [
        child
        for child in stripped_chap_div
        if etree.QName(child).localname == "div"
        and child.get("type") == section_div_type
    ]
    if not matching_divs and next(stripped_chap_div.iter("{*}l"), None) is not None:
        column_name = column or stripped_chap_div.get("n") or "<unknown>"
        column_div_type = stripped_chap_div.get("type") or "<unknown>"
        raise ValueError(
            f"{column_name}: column div type {column_div_type!r} contains "
            f"descendant <l> elements but no child divs of configured type "
            f"{section_div_type!r}"
        )
    for sec_div in matching_divs:
        n_raw = sec_div.get("n")
        if n_raw == "t":
            continue
        m = _SECTION_N_RE.match(n_raw or "")
        if not m:
            raise ValueError(f"unrecognized TLG section @n={n_raw!r}")
        sec = int(m.group(1))
        for l in sec_div.iter("{*}l"):
            text = _line_text(l)
            if not text:
                continue
            n += 1
            entry = {"n": n, "text": text, "sec": sec}
            rend = l.get("rend")
            if rend:
                im = _LINE_INDENT_RE.match(rend)
                if not im:
                    raise ValueError(
                        f"unrecognized <l> @rend={rend!r} (section {sec}, "
                        f"line n={n})"
                    )
                entry["indent"] = int(im.group(1))
            out.append(entry)
    return out


def _apply_lined_wraps(
    column: str,
    lines: list[dict],
    *,
    alphabet: LinedAlphabet,
    defer_column_final: bool = False,
) -> None:
    """In-place print-line hyphen rejoin across one chapter's `lines`
    (Q1.3/Q2 of docs/lined-source-plan.md): a line ending in an ASCII hyphen
    directly preceded by a Greek letter, whose immediate successor's text
    begins with a LOWERCASE Greek letter, absorbs that successor's first
    whitespace-delimited word — the successor's `text` loses that word — and
    the first line is marked `joined: True`, `wrap: <int>` (the character
    count of the fragment Schenkl printed on THIS line, of the eventual
    joined word — I3). Same match shape as `_rejoin_wrapped_hyphens` (see its
    docstring), applied across `<l>` boundaries instead of within one
    flattened string.

    Deliberately NOT the plain `text.endswith("-")` check parse_spine's own
    cross-line loop uses for bekker/stephanus (no Greek-letter guard at all):
    this work's ground truth (§1.3) carries two lines (1.2 §3 l.1, 2.5 §17
    l.1) whose continuation is an editorial angle bracket, not a Greek
    letter, and those must stay unjoined with their literal hyphen intact
    rather than erroring or splicing.

    A wrap-candidate hyphen on the chapter's LAST line has no successor to
    join with — the corpus-wide census (§1.3) found zero such chapter-final
    wraps in the real export, so this is a defect signal (a stray candidate
    at a column boundary) rather than a case to handle: raises ValueError
    naming the column, never silently drops the hyphen or splices across
    chapters."""
    for i, line in enumerate(lines):
        text = line["text"]
        if not _is_wrap_candidate(text, alphabet=alphabet):
            continue
        if i + 1 >= len(lines):
            if defer_column_final:
                continue
            raise ValueError(
                f"{column}: chapter-final print-line hyphen wrap (line "
                f"n={line['n']!r}) has no continuation — a wrap can never "
                f"cross a column boundary"
            )
        nxt = lines[i + 1]
        # Continuation-side letter test is the script-union (see
        # `_is_wrap_letter`'s cross-script comment above) -- a Latin
        # continuation ("cher") wrapped inside a Greek work, or a Greek one
        # inside a Latin work, must still be accepted here.
        if not (nxt["text"] and _is_wrap_letter(nxt["text"][0]) and nxt["text"][0].islower()):
            continue
        frag_start = _word_start(text, len(text) - 1, alphabet=alphabet)
        # `wrap` counts characters of the TOKEN's surface printed on this
        # line (I3: the reader slices the token's `t`), but `_word_start`
        # walks back to whitespace — an opening quote glued to the word
        # (`λέγειν ‘Συμβήσε-`, 17 real loci) would count into the fragment
        # and put the repainted split one character off (Συμβήσετ-/αί for
        # Schenkl's Συμβήσε-/ταί; verifier check-4 catch, 2026-08-29).
        # Advance to where tokenization will start the token: quotes and
        # other word-external punctuation are excluded from the token
        # surface, but Schenkl's editorial sigla are PART of it (verified:
        # the emitted token for 2.9 §12's supplement is "<ἀναισχυντία>",
        # brackets included; 4 wrapped words in the corpus open with "<").
        # So skip glued non-letters EXCEPT an opening siglum, and EXCEPT a
        # character this alphabet's own surface keeps (`frag_start_glued_
        # chars` -- Latin's leading ASCII apostrophe, `'moriatur`: stage3's
        # `_surface()` does not edge-trim it, so the fragment starts ON it,
        # not past it. Greek's set is empty; its glued curly quote IS
        # stripped by `_surface()`, so it is still skipped here unchanged.
        while (
            frag_start < len(text) - 1
            and not _is_wrap_letter(text[frag_start])
            and text[frag_start] not in "<["
            and text[frag_start] not in alphabet.frag_start_glued_chars
        ):
            frag_start += 1
        wrap = len(text) - 1 - frag_start
        head, _, rest = nxt["text"].partition(" ")
        if _is_wrap_candidate(head, alphabet=alphabet):
            # A word chained across THREE print lines: the absorbed
            # continuation itself ends in a wrap hyphen. The corpus census
            # (plan §1.3) found zero of these; silently absorbing would leave
            # this line ending in a literal mid-word hyphen, skip the next
            # join (the emptied successor no longer ends in "-"), and could
            # even hide a chapter-final wrap behind a fully-absorbed last
            # line (adversarial-review WARN, 2026-08-29). Refuse loudly.
            raise ValueError(
                f"{column}: chained print-line hyphen wrap (line "
                f"n={line['n']!r} absorbs a continuation that itself ends "
                f"in a wrap hyphen) — unsupported by the lined emission"
            )
        # Fold the whole pre-hyphen fragment before gluing on the
        # continuation. The sigma fold is applied universally (both
        # alphabets, see `_fold_hyphen_final_sigma`'s own comment) rather
        # than via `alphabet.fold_wrap_final` -- it needs to look through
        # trailing closing sigla and must preserve the fragment's length.
        fragment = text[:-1]
        fragment = _fold_hyphen_final_sigma(fragment)
        line["text"] = fragment + head
        line["joined"] = True
        line["wrap"] = wrap
        # The character offset, in this line's FINAL (post-absorb) `text`, of
        # the wrapped word's own start -- named explicitly rather than
        # inferred as "the last token" because absorption takes the WHOLE
        # whitespace-delimited continuation fragment (I4), which can glue
        # more than the wrapped word onto this line when the source prints an
        # em dash with no space before the next word (e.g. epicurus-letter-
        # to-herodotus §53/§69: "…σχηματίζε-" / "σθαι—πολλὴν…" absorbs
        # "σθαι—πολλὴν" whole, so "πολλὴν" becomes the line's LAST token, not
        # the wrapped one). `frag_start` is unchanged by the absorb step
        # above (it only appends to the end of `text[:-1]`), so it is already
        # the correct offset into the final joined text. Emitted uniformly on
        # every joined line, not only this glob case -- see docs/lined-
        # source-plan.md §3's 2026-08-29 wrapO deviation note.
        line["wrapO"] = frag_start
        nxt["text"] = rest


def _apply_lined_cross_column_wraps(
    flat: list[dict], *, alphabet: LinedAlphabet
) -> int:
    """Rejoin declared print wraps across adjacent column boundaries.

    The word belongs to the column where it starts. Unlike an in-column
    wrap, a cross-column join records only ``joined``: the print split is
    not repainted across two segments.
    """
    joined = 0
    for i in range(len(flat) - 1):
        cur, nxt = flat[i], flat[i + 1]
        if cur["column"] == nxt["column"]:
            continue
        text = cur["text"]
        if not _is_wrap_candidate(text, alphabet=alphabet):
            continue
        nxt_text = nxt["text"]
        # Continuation-side letter test is the script-union, same as
        # `_apply_lined_wraps` above (see `_is_wrap_letter`'s cross-script
        # comment).
        if not (
            nxt_text
            and _is_wrap_letter(nxt_text[0])
            and nxt_text[0].islower()
        ):
            continue
        head, _, rest = nxt_text.partition(" ")
        if _is_wrap_candidate(head, alphabet=alphabet):
            raise ValueError(
                f"{cur['column']}: chained print-line hyphen wrap (line "
                f"n={cur['n']!r} absorbs a continuation that itself ends "
                f"in a wrap hyphen) — unsupported by the lined emission"
            )
        fragment = text[:-1]
        fragment = _fold_hyphen_final_sigma(fragment)
        cur["text"] = fragment + head
        cur["joined"] = True
        cur.pop("wrap", None)
        cur.pop("wrapO", None)
        # `nxt` (the receiving line) can ALSO carry its own, unrelated
        # in-column `wrap`/`wrapO` -- set earlier by `_apply_lined_wraps`
        # for a print-line hyphen further down THIS SAME line, wrapping into
        # the column's second line. That `wrapO` was computed against
        # `nxt`'s ORIGINAL text; stripping `head` (plus the separating
        # space) off the front shifts every later offset left by the same
        # amount, so `wrapO` must be rebased or it points at the wrong
        # character (silently, since it can still land inside the string) --
        # or past the end (loudly, since preflight's "matches a token's `o`"
        # check catches it). `wrap` itself (a length, not an offset) is
        # unaffected. Evidence: lives 2:2.42, wrap=6 wrapO=52 pre-rebase,
        # the wrapped token actually at o=44 -- exactly the 8-char head
        # `_apply_lined_cross_column_wraps` stripped off this line's front.
        stripped_len = len(nxt_text) - len(rest)
        if "wrapO" in nxt:
            rebased_wrap_o = nxt["wrapO"] - stripped_len
            # 0 is a LEGAL rebased offset: a two-word receiving line
            # (carried word-tail + its own wrapped word) leaves the wrapped
            # token as the first token of the remaining text (Grok gate
            # finding, 2026-08-30). Only a NEGATIVE rebase — a wrap start
            # that lived inside the stripped head — is impossible.
            if rebased_wrap_o < 0:
                raise ValueError(
                    f"{nxt['column']}: cross-column head-strip of "
                    f"{stripped_len} char(s) rebases line n={nxt['n']!r}'s "
                    f"own wrapO={nxt['wrapO']!r} to {rebased_wrap_o!r} "
                    f"(< 0) — its in-column wrap start cannot sit inside "
                    f"the head absorbed into the prior column"
                )
            nxt["wrapO"] = rebased_wrap_o
        nxt["text"] = rest
        joined += 1

    for i, line in enumerate(flat):
        if not _is_wrap_candidate(line["text"], alphabet=alphabet):
            continue
        is_column_final = i + 1 >= len(flat) or flat[i + 1]["column"] != line["column"]
        if is_column_final:
            raise ValueError(
                f"{line['column']}: column-final print-line hyphen wrap "
                f"(line n={line['n']!r}) survived the cross-column pass"
            )
    return joined


def _warn_if_lined_source_has_no_wraps(
    work_id: str, flat_lines: list[dict], *, alphabet: LinedAlphabet
) -> None:
    """Rule 0's machine enforcement (docs/lined-rollout-plan.md): after
    `_apply_lined_wraps` has run over a whole `lined_source` work, if it
    marked zero lines `joined`, the export may not be a lined PROSE edition
    at all — a genuine verse `<l>` stream (a metrical line never splits a
    word mid-line) would also show zero wraps, which is exactly the shape
    `lined_source` must never be turned on for. A WARNING, not a FATAL: a
    genuinely short prose work could legitimately wrap nothing by chance
    (Rule 0's stated limit — absence of wraps is weak evidence; presence is
    strong evidence)."""
    if not any(line.get("joined") for line in flat_lines):
        print(
            f"  stage1 WARNING: {work_id}: lined_source declared but the "
            f"export contains no print-line hyphen wraps — verify this is "
            f"a lined prose edition, not verse"
        )
