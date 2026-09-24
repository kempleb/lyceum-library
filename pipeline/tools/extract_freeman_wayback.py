"""One-off: fetch a chapter of Kathleen Freeman's *Ancilla to the
Pre-Socratic Philosophers* (Blackwell, 1948) from sacred-texts.com's
transcription (`sacred-texts.com/cla/app/appNN.htm`), reached via a
web.archive.org raw `id_` snapshot (sacred-texts itself 403s a plain
fetch — see docs/ancilla-source-assessment.md §1), and produce a clean,
DK-column-keyed JSON plus a group-header sidecar.

Method matches the assessment memo exactly: `GET
https://archive.org/wayback/available?url=sacred-texts.com/cla/app/<page>.htm`
for the latest snapshot timestamp, then the raw (unwrapped) page at
`http://web.archive.org/web/<ts>id_/https://www.sacred-texts.com/cla/app/<page>.htm`.
Politely sequential — one page at a time, a short delay between requests
(`_FETCH_DELAY_S`) — no concurrency.

## Output shape (design note docs/freeman-wave-design.md §1/§6)

`{"<Bn>": {"kind": "title"|"verbatim"|"embedded"|"note", "text": "..."}}` —
the clean JSON. A sidecar list `[{"before_column", "level", "text"}]`
records Freeman's own group-header paratext (subject/category labels with
no DK number of their own — "Doubtful titles...", "'On Mathematics'",
"(Titles)" — see the design note §1's two-level taxonomy) in reading
order, `before_column` naming the DK column token the header immediately
precedes.

## Freeman → DK column mapping

Freeman prints no literal "B" — chapter + Arabic-number-plus-letter is
synthesized into `B<n><letter?>` here (assessment §1, risk 2).

## Kind classification (design note §1(b))

A per-column MARKUP proposal, in order:
  1. Any small-caps `<span style="font-variant:small-caps">` present in the
     column's accumulated content → `embedded` (Freeman's `N. (SOURCE:
     'quote')` signature — a named ancient source's own sentence, quoted).
  2. Else, any ROMAN (non-italic) prose word present outside all `<i>`
     tags → `verbatim` (leading N., then Freeman's rendering of the
     philosopher's own surviving words; her OWN italic insertions may
     still appear inside the roman span, per her Foreword's stated
     convention — this classifier only asks whether ANY roman text
     exists, not whether ALL of it is roman).
  3. Else (the whole entry, once the leading "N." label is stripped, is
     wrapped in italics) — Freeman uses two distinct wholly-italic
     shapes that read identically at the markup level alone:
       (a) a BARE quoted title, `'Title.'` (single-quote first
           non-whitespace character) → `title`;
       (b) anything else (typically a parenthetical editorial narration,
           `(...)`) — ambiguous at the markup level alone between `note`
           ("no words survive", Freeman narrates in her own voice) and
           `embedded` (the ancient source's testimonium happens to
           preserve one attested word or short phrase, which Freeman
           folds into her own narration rather than block-quoting). This
           is the design note's cross-check case, and per the CLAUDE.md
           "no heuristic tie-break" rule (the Empedocles verse-heuristic
           ban) this classifier NEVER auto-resolves it -- and, per the
           phase-1 pilot's round-2 fix, ABSENCE of contrary evidence is
           not a resolution either: this shape is ALWAYS `conflict`,
           regardless of whether an already-built Greek DK spine's
           role='text' hint (`text_columns`, optional param) was even
           supplied, and regardless of whether the hint happens to AGREE
           with the conservative literal-markup reading. The hint's only
           legitimate job is to help a human DETECT disagreement faster
           when one exists; its absence, or its agreement, is evidence
           toward a ruling, never the ruling itself. `conflict` is NOT a
           legal Segment.kind; it is resolvable ONLY by an explicit,
           human-authored `citation.kind_overrides` declaration in the
           work's manifest (validated, each entry requires a `note`
           justifying the ruling) -- see stage1_freeman_english.py's
           `_resolve_kind_overrides`, which is where the actual build
           gate lives (this one-off tool has no independent override
           mechanism of its own; the ruling belongs in the manifest,
           once, not duplicated here). This holds even for a column
           where markup and Greek structure fully AGREE (e.g. Protagoras
           B7) -- an override is still required, recording the human
           ruling once rather than re-deriving it by heuristic on every
           run. CANON-logged judgment call (Protagoras B5/B6/B6a/B7,
           Wave "Freeman Ancilla" phase 1 pilot): RESOLVED by John's
           2026-07-23 ruling -- see
           manifests/protagoras-fragments.yaml's `citation.kind_overrides`.

Front matter (bio paragraph(s) before the first numbered fragment) is
dropped, unchanged from every prior extractor's convention. A page-break
marker paragraph (`<A NAME="page_N">`) is recognized and skipped without
affecting group-header/continuation state.

## Group-header vs. roman-continuation disambiguation (§1's L2 taxonomy)

An unnumbered, non-smallcaps paragraph is an L2 group header ONLY when it
carries the taxonomy's actual signature: wholly italic (no roman prose word
outside any `<i>`), a short label ("*Titles*", "*Spurious fragments*").
Otherwise -- ANY roman prose present -- it is a continuation of the entry
currently being accumulated (the same merge the smallcaps-continuation
branch already does), never paratext. Without this check a multi-paragraph
`verbatim` entry whose second `<p>` happens to carry no leading number would
misclassify as a header and silently drop real fragment text.

## Source-citation frame ranges (design note §3's `.eng-source-frame`)

For an `embedded`-kind entry classified via signal 1 (a smallcaps source
name present), the extractor also emits `frames`: `[[start, end)]` char
offsets into the STORED text marking Freeman's own parenthetic citation
lead-in (e.g. "(Porphyry: " in "(Porphyry: 'Few of the writings...')") --
the apparatus the reader's `.eng-source-frame` styles, as distinct from the
quoted words that follow. Computed from the first smallcaps span's own text:
`start` is the nearest preceding "(", `end` is the first quote character
(straight or curly) after the name. Absent when no quote character follows
(the parenthetical narrates in Freeman's own voice around the name with no
block quote to set apart) -- an implementation-level choice (the design note
does not specify an exact range format); see docs/freeman-wave-design.md §3
appendix note.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

from lxml import html as lxml_html

_FETCH_DELAY_S = 1.5
_UA = "Mozilla/5.0 (compatible; classical-philosophy-reader research fetch)"

_LEAD_NUM_RE = re.compile(r"^(\d+)([a-z]?)\.\s*")
_PAGE_MARKER_RE = re.compile(r"^p\.\s*\d+$")
# A parenthetical entry opening with a title announcement -- "(Title of
# book:", "(Title of work:", or bare "(Title:" -- immediately followed by
# the title text itself (see classify_kind's Leucippus B1 note). Anchored at
# the very start of the entry so an ordinary parenthetical remark, e.g.
# "(Some note about...)", never matches.
_TITLE_ANNOUNCEMENT_RE = re.compile(r"^\(Title(?: of (?:book|work))?:")

# Literal numbering typos in sacred-texts' transcription.
# The exact entry opening is part of each match so neither correction can
# silently rewrite another chapter or the later, genuine Democritus B308.
_SOURCE_NUMBER_CORRECTIONS = (
    (re.compile(r"^308\.\s+'Theogonia\.'"), "B301", re.compile(r"^308\.\s*")),
    (
        re.compile(r"^30S\.\s+\(Reference to Democritus as philosopher"),
        "B305",
        re.compile(r"^30S\.\s*"),
    ),
    (
        re.compile(r"^S\.\s+If it were not One,"),
        "B5",
        re.compile(r"^S\.\s*"),
    ),
    (
        re.compile(r"^S\.\s+They purify themselves by staining"),
        "B5",
        re.compile(r"^S\.\s*"),
    ),
    (
        re.compile(r"^S\.\s+Actually, Number has two distinct forms"),
        "B5",
        re.compile(r"^S\.\s*"),
    ),
    (
        re.compile(r"^S9\.\s+To drink beaker after beaker"),
        "B59",
        re.compile(r"^S9\.\s*"),
    ),
    (
        re.compile(r"^So\.\s+When you have listened, not to me but to the Law"),
        "B50",
        re.compile(r"^So\.\s*"),
    ),
    (
        re.compile(r"^83\.\s+\(On Pythagoras\)\. Original chief of wranglers"),
        "B81",
        re.compile(r"^83\.\s*"),
    ),
    (
        re.compile(r"^12 7\.\s+\(To the Egyptians\):"),
        "B127",
        re.compile(r"^12 7\.\s*"),
    ),
    (
        re.compile(r"^7, 8\.\s+For this \(view\) can never predominate"),
        "B7",
        re.compile(r"^7, 8\.\s*"),
    ),
    (
        re.compile(r"^77, 78\.\s+\(Trees\) retentive of their leaves"),
        "B77",
        re.compile(r"^77, 78\.\s*"),
    ),
)

# A third class of sacred-texts scan typo: a capital I or lowercase l
# standing in for the digit 1 somewhere in a leading Arabic-number label
# (Democritus B131 prints as ``13I.``). Unlike the two literal corrections
# above (each tied to a unique exact opening phrase), this class is
# detected generically -- but only ever ACCEPTED when the corrected number
# is the exact expected successor of the entry currently being
# accumulated. That successor check, not the letter shape, is what keeps a
# genuine roman numeral (``III.``) or a stray letter from ever being
# misread as a new DK entry: neither would coincidentally equal the next
# Arabic number in sequence.
_LEAD_NUM_TYPO_RE = re.compile(r"^([0-9Il]+)\.\s")
_I_L_TO_1 = str.maketrans({"I": "1", "l": "1"})


def _expected_next_column(cur_num: str | None) -> int | None:
    """The Arabic number expected to follow `cur_num` (a plain ``B<n>``
    column, no letter suffix), or None when there is nothing being
    accumulated or its column carries a letter suffix (e.g. ``B129a`` has
    no well-defined "next number" of its own)."""
    if cur_num is None:
        return None
    m = re.fullmatch(r"B(\d+)", cur_num)
    return int(m.group(1)) + 1 if m else None


def _typo_corrected_column(text: str, expected_next: int | None
                            ) -> tuple[str, re.Pattern[str]] | None:
    """Detects an I/l-for-1 scan typo in `text`'s leading Arabic-number
    label, returning the corrected column and its label-strip pattern only
    when the correction's numeric value equals `expected_next` exactly."""
    if expected_next is None:
        return None
    m = _LEAD_NUM_TYPO_RE.match(text)
    if not m:
        return None
    token = m.group(1)
    if token.isdigit():
        return None  # ordinary numbering -- not a typo case
    corrected = token.translate(_I_L_TO_1)
    if not corrected.isdigit() or int(corrected) != expected_next:
        return None
    return f"B{corrected}", re.compile(r"^" + re.escape(token) + r"\.\s*")


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def wayback_snapshot_url(page_url: str) -> str:
    """The latest wayback snapshot's raw `id_` URL for `page_url`
    (assessment §1's availability-API method)."""
    avail = json.loads(
        _fetch(f"https://archive.org/wayback/available?url={page_url}")
    )
    snap = avail.get("archived_snapshots", {}).get("closest")
    if not snap or not snap.get("available"):
        raise ValueError(f"no wayback snapshot available for {page_url}")
    ts = snap["timestamp"]
    return f"http://web.archive.org/web/{ts}id_/https://{page_url}"


def fetch_chapter_html(chapter_file: str) -> str:
    """`chapter_file` e.g. 'app75.htm'. Politely sequential: sleeps
    `_FETCH_DELAY_S` AFTER fetching so a caller looping over several
    chapters never bursts requests."""
    url = wayback_snapshot_url(f"sacred-texts.com/cla/app/{chapter_file}")
    html_bytes = _fetch(url)
    time.sleep(_FETCH_DELAY_S)
    return html_bytes.decode("utf-8", errors="replace")


def _has_smallcaps(el) -> bool:
    spans = el.xpath('.//span[contains(@style, "small-caps")]')
    logical_emphasis = {
        "it", "it is", "it is not", "it not to be", "not", "not to be"
    }
    return any(_plain_text(span).lower() not in logical_emphasis for span in spans)


_FOOTNOTE_CALL_HREF_RE = re.compile(r"^#fn_\d+$")
# Punctuation that, when it immediately follows a stripped footnote-call
# anchor (no intervening word), signals that any whitespace directly
# BEFORE the anchor -- ordinary space or a non-breaking space (nbsp
# transcribes as a literal space HTML entity, sacred-texts uses it before
# a footnote call) -- is layout glue, not real inter-word spacing, and
# should collapse to nothing (see `_strip_footnote_call_anchors`).
_FOOTNOTE_ADJACENT_PUNCT_RE = re.compile(r"^[.,;:!?]")
# A stripped anchor's tail starting with `.` or `,` followed by whitespace
# and a LOWERCASE letter: the run continues mid-sentence, so that leading
# punctuation is an orphan left by the footnote-call markup (the digit's
# own trailing punctuation in the source, e.g. `All Things<a>1</a>. were
# together`), not a real sentence break -- see `_strip_footnote_call_anchors`.
_ORPHANED_MID_SENTENCE_PUNCT_RE = re.compile(r"^[.,](\s+)(?=[a-z])")
_TRAILING_WS_RE = re.compile(r"[ \t\r\n\xa0]+$")
_TRAILING_SENTENCE_PUNCT_RE = re.compile(r"[.,;:!?][ \t\r\n\xa0]*$")
_LEGACY_C1_TRANSLATION = str.maketrans({
    "\u0091": "\u2018",  # Windows-1252 left single quotation mark
    "\u0092": "\u2019",  # Windows-1252 right single quotation mark
    "\u0097": "\u2014",  # Windows-1252 em dash
})
_TEXT_BOUNDARY_TAGS = {"br", "div", "p", "table", "td", "th", "tr"}


def _strip_footnote_call_anchors(el) -> None:
    """Remove `<a href="#fn_N">...</a>` footnote-call markers (the
    superscript digit sacred-texts prints to point at its own endnotes) in
    place. Footnotes are not extracted under current policy (module
    docstring has no footnote-kind Segment); left alone, the anchor's
    digit text node leaks into `itertext()` and lands mid-sentence in the
    stored prose (e.g. Xenophanes B1: "...his memory (and his endeavour)
    1 concerning virtue..."). The paired empty `<a name="fr_N">` return
    anchor carries no text and needs no stripping."""
    for a in el.xpath('.//a[@href]'):
        href = a.get("href", "")
        if _FOOTNOTE_CALL_HREF_RE.match(href):
            parent = a.getparent()
            prev = a.getprevious()
            # lxml's tail (the text AFTER a's closing tag, belonging to
            # the surrounding flow, not to `a` itself) would otherwise be
            # discarded along with the element -- splice it onto the
            # preceding sibling's tail, or the parent's own leading text
            # when `a` was the first child.
            if a.tail and _FOOTNOTE_ADJACENT_PUNCT_RE.match(a.tail):
                # Punctuation sits immediately after the removed call, no
                # intervening word -- any whitespace directly before the
                # call (the strip point) is layout glue, not real
                # inter-word spacing. Walk back through the paired empty
                # `fr_N` return anchor (and any other content-free
                # sibling) to the nearest place that actually holds text,
                # and collapse its trailing whitespace away.
                node = prev
                while node is not None and not node.tail:
                    node = node.getprevious()
                preceding_text = node.tail if node is not None else (parent.text or "")
                if (
                    _ORPHANED_MID_SENTENCE_PUNCT_RE.match(a.tail)
                    and not _TRAILING_SENTENCE_PUNCT_RE.search(preceding_text)
                ):
                    # The punctuation right after the call is not a real
                    # sentence break -- it's the tail of the footnote-call
                    # digit that got left behind when the digit itself was
                    # stripped, and the text keeps going lowercase right
                    # after it. Drop it (collapsing its trailing
                    # whitespace run to a single space so word spacing
                    # survives the splice below).
                    a.tail = _ORPHANED_MID_SENTENCE_PUNCT_RE.sub(" ", a.tail)
                if node is not None:
                    node.tail = _TRAILING_WS_RE.sub("", node.tail)
                else:
                    parent.text = _TRAILING_WS_RE.sub("", parent.text or "")
            if a.tail:
                if prev is not None:
                    prev.tail = (prev.tail or "") + a.tail
                else:
                    parent.text = (parent.text or "") + a.tail
            parent.remove(a)


def _plain_text(el) -> str:
    """Flattened text content, collapsed whitespace, HTML entities already
    resolved by lxml. Footnote-call anchors are stripped first (see
    `_strip_footnote_call_anchors`) so their superscript digit never
    reaches the stored prose."""
    _strip_footnote_call_anchors(el)
    pieces: list[str] = []

    def boundary() -> None:
        if pieces and not pieces[-1].endswith((" ", "\n", "\r", "\t")):
            pieces.append(" ")

    def collect(node) -> None:
        if node.text:
            pieces.append(node.text)
        for child in node:
            is_boundary = child.tag.lower() in _TEXT_BOUNDARY_TAGS
            if is_boundary:
                boundary()
            collect(child)
            if is_boundary:
                boundary()
            if child.tail:
                pieces.append(child.tail)

    collect(el)
    text = "".join(pieces).translate(_LEGACY_C1_TRANSLATION)
    return re.sub(r"\s+", " ", text).strip()


def _has_roman_word(el) -> bool:
    """True if any text node OUTSIDE every <i> ancestor contains a letter
    -- i.e. real roman prose exists, not just connective punctuation/
    parens/quotes belonging to an italic wrapper. `node.text` is inside
    `node` itself; `node.tail` (text after node's closing tag) belongs to
    `node`'s PARENT's context, not node's -- the two are checked against
    their own respective ancestor chains."""
    def under_italic(container) -> bool:
        while container is not None:
            if container.tag == "i":
                return True
            container = container.getparent()
        return False

    for node in el.iter():
        if node.text and re.search(r"[A-Za-z]", node.text) and not under_italic(node):
            return True
        if node.tail and re.search(r"[A-Za-z]", node.tail) and not under_italic(node.getparent()):
            return True
    return False


def _is_bare_smallcaps_label(p_el, full_text: str) -> bool:
    """True when `p_el`'s entire text content IS its small-caps span(s)
    (an L1 group header, e.g. "THE TETRALOGIES OF THRASYLLUS") rather
    than a small-caps NAME embedded in a larger citation/continuation
    structure (an `embedded`-kind continuation paragraph, e.g.
    "(Porphyry: '…')")."""
    sc_spans = p_el.xpath('.//span[contains(@style, "small-caps")]')
    if not sc_spans:
        return False
    sc_text = re.sub(r"\s+", " ", "".join(
        "".join(s.itertext()) for s in sc_spans
    )).strip()
    # Remove every small-caps span separately: Democritus' tetralogy
    # headings use two spans with roman numerals/connectives between them
    # ("TETRALOGIES III to VI: NATURAL SCIENCE"). Those connective words
    # are still header glue, while a source citation's remaining prose is
    # not.
    remainder = full_text
    for span in sc_spans:
        remainder = remainder.replace(_plain_text(span), "", 1)
    words = re.findall(r"[A-Za-z]+", remainder)
    return all(
        word.lower() in {"the", "and", "to", "etc"}
        or re.fullmatch(r"[IVXLCDM]+", word)
        for word in words
    )


def _smallcaps_header_level(text: str) -> int:
    # The wave design explicitly treats Freeman's Causes subject label as
    # an L2 label even though sacred-texts transcribes it in small caps.
    if text.casefold() == "unclassified writings on 'causes'":
        return 2
    return 1


def _is_page_marker(p_el) -> bool:
    names = p_el.xpath('.//a/@name | .//A/@NAME')
    if any(str(n).lower().startswith("page_") for n in names):
        return True
    text = _plain_text(p_el)
    return bool(_PAGE_MARKER_RE.match(text))


def _is_footnote_definition(p_el) -> bool:
    names = p_el.xpath('.//a/@name | .//A/@NAME')
    return any(str(name).lower().startswith("fn_") for name in names)


def classify_kind(html_fragment_els: list, text_columns: set[str] | None,
                   column: str) -> str:
    """`html_fragment_els` are the (possibly several, for a merged/
    continuation entry) lxml <p> elements making up one DK column's
    Freeman entry. See module docstring for the decision order. Returns
    one of `title`/`verbatim`/`embedded`/`note`/`conflict` -- `conflict`
    is NOT a legal Segment.kind; it marks a wholly-italic, non-title
    entry (typically a parenthetical, `(...)`) whose note-vs-embedded
    reading this classifier can never settle by markup alone, and can
    only be resolved by an explicit, human-authored
    `citation.kind_overrides` manifest declaration (see module
    docstring). When `text_columns` is supplied, a proposed `verbatim`
    without a live Greek role='text' line, or a proposed `title` with
    one, is likewise `conflict`: every markup/role disagreement stops for
    review (design note §1(b)). A missing hint is never treated as proof
    either way."""
    # The leading "N." (or "Na.") printed label sits in the FIRST
    # element's own lead text node, outside any <i> -- strip it before
    # scanning for roman prose, or the digit-adjacent letter suffix
    # ("8a.") would itself register as a false-positive roman word. This
    # mutates the element in place; harmless, since the caller's own text
    # extraction re-applies the identical (idempotent) strip.
    first = html_fragment_els[0]
    if first.text:
        first.text = _LEAD_NUM_RE.sub("", first.text, count=1)

    # Leucippus B1 is a title-survival-in-frame in mixed typography:
    # ``(Title of book:`` and Freeman's attribution are italic, while the
    # surviving title itself is roman. The generic roman-prose rule below
    # would call that `verbatim`, but the approved Protagoras B5 precedent
    # makes the semantic title reading explicit through a manifest
    # override. Keep this exact source shape as `conflict` so the extractor
    # never silently decides the title-vs-prose question itself. Generalized
    # (conservatively) beyond the literal "(Title of book:" wording to also
    # catch "(Title of work:" and bare "(Title:" -- still anchored at the
    # very start of the entry so an ordinary parenthetical remark can never
    # match.
    first_text = _plain_text(first)
    if _TITLE_ANNOUNCEMENT_RE.match(first_text):
        return "conflict"
    if re.match(r"^\(=\s*", first_text):
        return "conflict"

    if any(_has_smallcaps(el) for el in html_fragment_els):
        if text_columns is not None and column not in text_columns:
            return "conflict"
        return "embedded"
    if any(_has_roman_word(el) for el in html_fragment_els):
        if text_columns is not None and column not in text_columns:
            return "conflict"
        return "verbatim"
    # Wholly italic. Strip the leading "N." label from the FIRST element's
    # flattened text to see what character actually opens the entry.
    first_text = _plain_text(html_fragment_els[0])
    first_text = _LEAD_NUM_RE.sub("", first_text, count=1)
    if first_text[:1] in "'‘’":
        if text_columns is not None and column in text_columns:
            return "conflict"
        return "title"
    # Wholly italic, not a bare quoted title: the note/embedded
    # ambiguity (module docstring). ALWAYS `conflict` -- never
    # auto-resolved (CLAUDE.md rule 9 / design note §1's "no heuristic
    # tie-break"), and never resolved BY OMISSION either: a missing or
    # agreeing `text_columns` hint is not proof the ambiguity was
    # actually checked, only evidence toward a human ruling.
    return "conflict"


_QUOTE_CHARS = "'‘’"
_PARMENIDES_B8_OPENING = "There is only one other description of the way remaining"
_LEUCIPPUS_TERMS_LEAD = (
    "Certain terms of the Atomic Theory can probably be traced to "
    "Leucippus, e.g."
)


def _frame_range(text: str, source_name: str) -> tuple[int, int] | None:
    """The `.eng-source-frame` char range for an `embedded`-kind entry
    whose smallcaps span reads `source_name` (module docstring's
    "Source-citation frame ranges"): from the nearest preceding "(" up to
    (excluding) the first quote character after the name. None when no
    quote character follows (nothing to set the frame apart from)."""
    idx = text.find(source_name)
    if idx == -1:
        return None
    start = text.rfind("(", 0, idx)
    if start == -1:
        start = 0
    scan_from = idx + len(source_name)
    for i in range(scan_from, len(text)):
        if text[i] in _QUOTE_CHARS:
            return (start, i) if i > start else None
    return None


def _smallcaps_source_name(html_fragment_els: list) -> str | None:
    for el in html_fragment_els:
        spans = el.xpath('.//span[contains(@style, "small-caps")]')
        if spans:
            return _plain_text(spans[0])
    return None


def _source_column(text: str) -> tuple[str, re.Pattern[str]] | None:
    """Return the synthesized column and label-strip pattern for an entry.

    Most entries use Freeman's ordinary Arabic-number-plus-letter label.
    Exact transcription corrections above are handled first so the first
    (misprinted) Democritus 308 does not collide with the genuine B308
    later in the chapter, ``30S`` does not disappear into B304, and
    Melissus', Philolaus', and Critias' scan-typo ``S.``/``S9.`` labels
    are each restored to their own DK column (B5, B5, B59 respectively)
    rather than disappearing as an unnumbered continuation of the
    preceding entry.
    """
    for signature, column, strip_re in _SOURCE_NUMBER_CORRECTIONS:
        if signature.match(text):
            return column, strip_re
    m = _LEAD_NUM_RE.match(text)
    if not m:
        return None
    return f"B{m.group(1)}{m.group(2)}", _LEAD_NUM_RE


def _assert_no_footnote_artifact(column: str, els: list, text: str) -> None:
    """Belt-and-braces check for `_strip_footnote_call_anchors`, run once
    per flushed column. Any footnote-call anchor that did not match the
    exact removable ``#fn_N`` shape remains a structural artifact and is
    fatal: it is silent corruption of the philosopher's words, not a
    warning to log past. Validation is structural rather than a bare
    ``word 1 word`` text heuristic because Democritus' calendar contains
    many genuine inline numbers, including single-digit day counts."""
    for el in els:
        for a in el.xpath('.//a[@href]'):
            href = a.get("href", "")
            if href.startswith("#fn_"):
                raise ValueError(
                    f"column {column!r}: footnote-call anchor "
                    f"{href!r} survived text extraction"
                )


def _chapter_blocks(tree) -> list:
    """Return semantic chapter blocks in document order.

    Ordinary chapters are paragraph-based. Democritus B14 is the stress
    case: sacred-texts wraps its eight internally numbered calendar
    extracts in ``div style="margin-left: 32px"`` containers containing
    paragraphs and tables. Treat each such container as one continuation
    block and suppress its descendant paragraphs, or their internal
    ``1.``/``2.`` labels would be fabricated as DK B-columns.
    """
    blocks = []
    for el in tree.xpath("//p | //div[contains(@style, 'margin-left')]"):
        if el.xpath(
            "ancestor::div[contains(@style, 'margin-left')]"
        ):
            continue
        blocks.append(el)
    return blocks


def parse_chapter(html_doc: str, text_columns: set[str] | None = None
                   ) -> tuple[dict[str, dict], list[dict]]:
    """Returns (columns, group_headers).

    `columns`: {"<Bn>": {"kind": ..., "text": ..., "frames"?: [[start,
    end), ...]}}, in Freeman's own reading order (dict insertion order —
    Python 3.7+ preserves it, and every caller here treats it as
    significant per the design note's §3.7 display-order verification).
    `kind` may be `conflict` (not a legal Segment.kind) -- see
    `classify_kind`. `frames` is present only for an `embedded` entry
    where a source-citation lead-in was detected (module docstring's
    "Source-citation frame ranges").

    `group_headers`: [{"before_column", "level", "text"}], in reading
    order. `level` is 1 (whole-paragraph small-caps, no italics, no
    number) or 2 (wholly italic short label, no number) — design note
    §1's two-level taxonomy.

    `text_columns`: optional set of DK column tokens whose Greek role
    profile carries at least one role='text' line — see
    `classify_kind`'s wholly-italic-parenthetical tie-break. Omit for a
    markup-only, Greek-unaware first pass.
    """
    tree = lxml_html.fromstring(html_doc)
    blocks = _chapter_blocks(tree)

    columns: dict[str, dict] = {}
    group_headers: list[dict] = []
    started = False
    cur_num: str | None = None
    cur_els: list = []
    cur_strip_re: re.Pattern[str] | None = None
    pending_headers: list[dict] = []

    def flush():
        nonlocal cur_num, cur_els, cur_strip_re
        if cur_num is not None:
            if cur_num in columns:
                # A synthesized DK token repeating (Freeman printing the
                # same Arabic-number-plus-letter twice, or a synthesis
                # bug) is never silently overwritten -- fatal, the same
                # posture as every other duplicate-anchor gate in this
                # pipeline.
                raise ValueError(
                    f"duplicate synthesized DK column {cur_num!r} -- "
                    f"Freeman's chapter text prints this token more than "
                    f"once; the second occurrence is never silently "
                    f"merged or overwritten"
                )
            kind = classify_kind(cur_els, text_columns, cur_num)
            text = " ".join(_plain_text(el) for el in cur_els)
            # Strip the leading "N." label from the stored text (the DK
            # token itself, not the printed Arabic-number label, is the
            # citation identity from here on — matches every other
            # extractor's convention of not re-printing the citation
            # number inside the translated prose). `cur_strip_re`, set
            # when this entry started, is authoritative even for a
            # typo-corrected label ("13I.") that `_source_column` alone
            # would no longer recognize on re-derivation.
            strip_re = cur_strip_re or _LEAD_NUM_RE
            text = strip_re.sub("", text, count=1)
            _assert_no_footnote_artifact(cur_num, cur_els, text)
            record = {"kind": kind, "text": text}
            if kind == "embedded":
                source_name = _smallcaps_source_name(cur_els)
                frame = _frame_range(text, source_name) if source_name else None
                if frame:
                    record["frames"] = [list(frame)]
            columns[cur_num] = record
        cur_num, cur_els, cur_strip_re = None, [], None

    for p in blocks:
        if _is_page_marker(p) or _is_footnote_definition(p):
            continue
        text = _plain_text(p)
        if not text:
            continue
        # Democritus B14's indented calendar is internally numbered
        # (1–8), but all eight witnesses belong to the one DK column.
        # Its wrapper is structural continuation markup, never a new
        # fragment entry.
        if p.tag.lower() == "div" and "margin-left" in p.get("style", ""):
            if not _has_smallcaps(p) and not _has_roman_word(p):
                # A standalone margin-left div carrying no small-caps
                # source name and no roman prose is Freeman's own
                # paratext label, never fragment continuation -- the same
                # L2-header signature the ordinary wholly-italic <p>
                # branch below already recognizes. Two witness shapes:
                # a forward range label ("128-141. (Unusual words quoted
                # by grammarians)", B127/B128) and a bare end-of-section
                # marker ("(End of the Gnomae)", B115/B116) -- consistent
                # with the already-committed "(End of the Tetralogies of
                # Thrasyllus)" header, which is the identical shape in a
                # plain <p>. A div carrying small-caps or roman prose
                # (Democritus B14's calendar extracts) is still glued to
                # the entry being accumulated.
                pending_headers.append({"level": 2, "text": text})
                continue
            if cur_els:
                cur_els.append(p)
            continue
        source = _source_column(text) or _typo_corrected_column(
            text, _expected_next_column(cur_num)
        )
        if source:
            flush()
            started = True
            cur_num, cur_strip_re = source
            cur_els = [p]
            for h in pending_headers:
                h["before_column"] = cur_num
                group_headers.append(h)
            pending_headers = []
            continue
        if cur_num == "B7" and text.startswith(_PARMENIDES_B8_OPENING):
            # Freeman combines Parmenides 7 and 8 under one printed
            # ``7, 8.`` heading. The next paragraph begins B8's remaining
            # Way and is the source's clean semantic boundary.
            flush()
            cur_num = "B8"
            cur_strip_re = re.compile(r"(?!)")
            cur_els = [p]
            continue
        if not started:
            # A chapter may put a genuine L2 genre/section label before
            # its first numbered entry (Xenophanes: "Elegíacs"). Keep
            # that label pending for B1 while still dropping ordinary
            # roman-prose biography/front matter.
            if _is_bare_smallcaps_label(p, text):
                pending_headers.append({
                    "level": _smallcaps_header_level(text),
                    "text": text,
                })
            elif not _has_smallcaps(p) and not _has_roman_word(p):
                pending_headers.append({"level": 2, "text": text})
            continue
        if _is_bare_smallcaps_label(p, text):
            # L1 group header: the paragraph's ENTIRE content is the
            # small-caps span itself, nothing else (design note's
            # "THE TETRALOGIES OF THRASYLLUS" shape) -- distinguished
            # from a continuation paragraph (below), where the small-caps
            # source name is only PART of a larger citation structure
            # ("(Porphyry: '…')").
            pending_headers.append({
                "level": _smallcaps_header_level(text),
                "text": text,
            })
            continue
        if _has_smallcaps(p):
            # continuation of the entry currently being accumulated
            # (e.g. B2's second <p>, the Porphyry quote)
            if cur_els:
                cur_els.append(p)
            continue
        if not _has_roman_word(p):
            if text == _LEUCIPPUS_TERMS_LEAD and cur_els:
                # This is the prose lead-in to the following terminology
                # lists, not a structural label for B2. Keep the whole
                # unsupported dossier attached to B1a so its `omit`
                # disposition also withholds this editorial English.
                cur_els.append(p)
                continue
            # wholly italic, non-numbered, no small-caps -> an L2 group
            # header (the taxonomy's actual signature: a short label, e.g.
            # "'On Mathematics'", "(Titles)").
            pending_headers.append({"level": 2, "text": text})
            continue
        # Roman prose present, no small-caps, no number -- NOT a header:
        # a continuation paragraph of the entry currently being
        # accumulated (a multi-paragraph `verbatim` entry). Merging here
        # is what stops real fragment text from being misread as
        # paratext and silently dropped.
        if cur_els:
            cur_els.append(p)

    flush()
    return columns, group_headers


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chapter_file", help="e.g. app75.htm")
    ap.add_argument("out_prefix", help="e.g. sources/freeman-ancilla/protagoras")
    ap.add_argument("--text-columns-file", help=(
        "optional JSON file: a list of DK column tokens carrying at "
        "least one role='text' Greek line (from the already-built Greek "
        "spine), used only to DETECT wholly-italic-parenthetical "
        "note/embedded disagreement -- it never resolves it: that shape "
        "always classifies `conflict`, resolvable solely by a validated "
        "manifest citation.kind_overrides adjudication"))
    args = ap.parse_args()

    text_columns = None
    if args.text_columns_file:
        text_columns = set(json.loads(Path(args.text_columns_file).read_text()))

    html_doc = fetch_chapter_html(args.chapter_file)
    columns, group_headers = parse_chapter(html_doc, text_columns)

    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    (out_prefix.parent / f"{out_prefix.name}.clean.json").write_text(
        json.dumps(columns, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_prefix.parent / f"{out_prefix.name}.group_headers.json").write_text(
        json.dumps(group_headers, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(columns)} columns, {len(group_headers)} group headers -> "
          f"{out_prefix}.clean.json / {out_prefix}.group_headers.json")

    conflicted = sorted(c for c, r in columns.items() if r["kind"] == "conflict")
    if conflicted:
        # Fail loud, same posture the pipeline enforces at build time
        # (stage1_freeman_english._resolve_kind_overrides): the files
        # above are still written (a human needs to see them to write the
        # manifest ruling), but this run reports itself as stopped, not
        # successful.
        raise SystemExit(
            f"STOPPED: {len(conflicted)} column(s) have markup-ambiguous "
            f"kind (wholly-italic, non-title -- typically parenthetical, "
            f"no small-caps source) that cannot be auto-resolved: "
            f"{conflicted} -- a human must rule 'note' vs 'embedded' for "
            f"each (design note docs/freeman-wave-design.md §1(b)) and "
            f"declare a citation.kind_overrides entry (with a note) per "
            f"column in the work's manifest before this chapter is "
            f"usable, EVEN when the Greek spine's role='text' hint "
            f"agrees with the conservative literal-markup reading -- "
            f"absence of disagreement is not a resolution."
        )


if __name__ == "__main__":
    main()
