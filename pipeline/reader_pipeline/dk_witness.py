"""DK (Diels-Kranz) apparatus witness split.

A DK column's apparatus/context text often quotes SEVERAL ancient sources
one after another -- Empedocles B17's apparatus alone strings together four
(Simplicius twice, Plutarch, Clement) -- but the pipeline has always
flattened the whole thing into one undifferentiated blob (a single
role='context' block). 265 columns corpus-wide carry 2+ witnesses that way;
Parmenides B7 carries eight. This module splits that blob into an ordered
list of witnesses -- {source, text} -- for the reader to render as separate
rows instead of one wall of prose.

NO LINE SPANS. An earlier draft also derived, per witness, WHICH verse lines
that witness attests, from DK's own bare line-markers ("1. 2") and his
incipit/explicit quotations. Measured against the real corpus that yields
only ~70 spans across 399 multi-line columns -- there are just SIX bare
markers corpus-wide, and half the quotations cannot be pinned because DK's
incipit recurs (Empedocles B17 repeats its own opening verbatim at line 16,
so "delta-iota-pi-lambda'" opens both line 1 and line 16) or quotes a variant
reading that matches no line at all (Clement's variant for B17's line 21).
John ruled 2026-08-05: not worth it, drop them. Recorded here because the
tempting rescue is a trap -- anchoring on the UNIQUE explicit and taking the
nearest preceding incipit gives B17's Simplicius lines 16-35 when the truth
is 1-35, i.e. it is right sometimes and silently wrong otherwise.

Ground truth (Empedocles B17, `build/export/.../tlg1342004.xml` div n="17",
emitted at app/dist/data/empedocles-fragments/book-01.json column B17): the
context block's text --

    SIMPL. Phys. 157, 25 ... 'δίπλ' ... ὁμοῖα'. 1. 2 SIMPL. Phys. 161, 14
    ... 'τοτὲ ... εἶναι'. PLUT. Amat. 13 p. 756 D ... 'καὶ ... τεθηπώς',
    ... CLEM. Strom. V 15 [II 335, 22 St.] ... 'ἣν ... τεθηπώς'.

-- is four witnesses (SIMPL. 157,25 / SIMPL. 161,14 / PLUT. Amat. 13 / CLEM.
Strom. V 15).

Two traps this module works around, both verified directly against the
export rather than assumed:

  * `<hi rend="letter-spacing">` CANNOT be used to find the quotations. In
    these apparatus blocks the milestones are mis-nested -- B17's print-line
    1 closes a run that was never opened, line 2 opens two -- the same
    defective-milestone class as Anaxagoras A92. So this works on flattened
    text.
  * Witnesses run ACROSS the div's print lines, and words are hyphen-split
    at line ends ("Ἐμπε-" / "δοκλέους" at B17's lines 4/5). The caller must
    hand this function text that has already been through the existing
    hyphen-rejoin, not raw per-line text.
"""

from __future__ import annotations

import re
import unicodedata


# Duplicated (not imported) rather than shared with dk_lang.is_greek_letter /
# stage1_greek._is_greek_letter / stage3_tokenize._is_greek_letter -- same
# reasoning as those three's own matching docstrings: no other coupling
# between this module and any of them.
def _is_greek_letter(ch: str) -> bool:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return False
    return name.startswith("GREEK") and unicodedata.category(ch).startswith("L")


# A witness's own citation: an uppercase Latin-alphabet abbreviation of 3+
# characters followed by a literal period (SIMPL. PLUT. CLEM. ARISTOT.
# DIOG. SEXT. STOB. SCHOL. ...).
_ANCHOR_RE = re.compile(r"\b([A-Z]{3,})\.")

# Two verified real citation abbreviations that happen to be spelled
# entirely with roman-numeral letters (I V X L C D M) -- CIC. (Cicero, the
# single most common Latin citation in this corpus) and DID. (Arius
# Didymus, Heraclitus B12 / Xenophanes A24). A full-corpus sweep of every
# other all-those-letters token found in a DK context block (XXV. XXXI.
# III. VII. VIII. XII. XIII. CLXX. IICCCCLXXXIIII. XDCCC.) is, in every
# case checked, a genuine roman numeral used as a page/day/year NUMBER
# inside a witness's own quoted Latin (e.g. Anaximander A20's "Thales
# XXV. die ab aequinoctio"), never a citation -- so those are excluded from
# anchor status, and these two evidenced exceptions are kept, matching this
# codebase's own narrow-exception convention (stage1_greek's
# dk_damaged_columns / export_artifact_chars) rather than a generic guess.
_ROMAN_LOOKALIKE_ANCHORS = {"CIC", "DID"}


def _is_roman_numeral(token: str) -> bool:
    return set(token) <= set("IVXLCDM") and token not in _ROMAN_LOOKALIKE_ANCHORS


# A bare ALL-CAPS continuation token (with or without its own period) --
# the shape DK's own compound citation labels take ("AMMON. SCHOL. HOMER.";
# a chain of scholiast names, all anchors in their own right but naming ONE
# source). Used only to test the GAP between two consecutive raw anchor
# matches: a gap made of nothing but whitespace and/or tokens matching this
# is the same citation continuing, not a new witness.
_BARE_CAPS_TOKEN_RE = re.compile(r"^[A-Z]{2,}\.?$")


def _is_chain_continuation_gap(gap: str) -> bool:
    """True when `gap` -- the text strictly between two consecutive raw
    anchor matches -- is nothing but whitespace and/or bare all-caps
    continuation tokens, so the second anchor is part of the FIRST
    anchor's own citation label, not a new witness starting. Any lowercase
    letter, digit, or other content (e.g. a whole Latin quotation between
    two real citations, "CIC. ... Democritus. HORAT. ...") means real
    material sits between them, so the second anchor is genuine."""
    return all(_BARE_CAPS_TOKEN_RE.match(tok) for tok in gap.split())


def _real_anchor_starts(text: str) -> list[int]:
    """Start offsets of every ANCHOR in `text` that begins a genuinely new
    witness -- i.e. every raw anchor match, minus roman-numeral false
    positives, minus anchors that are chained continuations of the anchor
    immediately before them (see `_is_chain_continuation_gap`)."""
    starts: list[int] = []
    prev_end: int | None = None
    for m in _ANCHOR_RE.finditer(text):
        if _is_roman_numeral(m.group(1)):
            continue
        if prev_end is None or not _is_chain_continuation_gap(text[prev_end:m.start()]):
            start = m.start()
            # DK brackets a pseudonymous attribution -- "[ARISTOT.] de
            # Melisso", "[PLUT.] Vit. X orat.", "[GEMIN.]", "[THEOPHR.]".
            # The bracket is part of the citation (it is what marks the work
            # as Ps.-Aristotle), so the witness begins AT it: starting at the
            # letter would strand "[" on the previous witness and label this
            # one "ARISTOT.]" -- a different scholarly claim.
            if start > 0 and text[start - 1] == "[":
                start -= 1
            starts.append(start)
        prev_end = m.end()
    return starts


# DK's own bare line-marker (Empedocles B17's "1. 2" = "lines 1 and 2"):
# two or more period-separated integers, immediately preceding a citation
# with only whitespace between. Requires AT LEAST two numbers -- the only
# evidenced shape -- so an ordinary trailing single digit (which could be
# almost anything) is never misread as a marker. DK's own bibliographic
# page/line references in this corpus are always comma- or space-separated
# ("Phys. 157, 25"), never period-separated, so this shape does not collide
# with them.
#
# Spans were dropped (see module doc), but this is still needed: the marker
# belongs to the citation AFTER it, so without reattribution it would trail
# on the PREVIOUS witness's text as a stray "1. 2".
_MARKER_RE = re.compile(r"(?<!\d)(\d+(?:\s*\.\s*\d+)+)\.?\s*$")

# A lowercase Latin word of 4+ letters NOT followed by a period, i.e. running
# prose rather than a reference abbreviation ("de", "nat.", "simpl.",
# "medic." are all abbreviated; "opinio", "nativos", "intervallis" are not).
_PROSE_WORD_RE = re.compile(r"\b([a-z]{4,})\b(?!\.)")

# How many such words make a candidate label prose rather than a citation.
# Measured against all 485 labelled witnesses in the corpus: 429 labels
# contain ZERO prose words, 46 contain exactly one, NONE contain two, and
# the 10 that contain three or more are every one of them the Latin-prose
# defect this guards (Cicero, Columella, Censorinus, Macrobius, Gellius,
# Horace). The empty bucket at two is the natural separator, so this is a
# measured boundary rather than a chosen cutoff.
#
# Deliberately NOT a length cutoff: the longest genuine label in the corpus
# is 122 chars ("PAPYR. LONDIN. 121 c. 5b v. 168 [Kenyon Greek Pap. in the
# Br. Mus. ...]"), longer than several of the defects, so length cannot
# separate them and would truncate a real reference.
_MAX_LABEL_PROSE_WORDS = 2


def split_witnesses(text: str) -> list[dict] | None:
    """Split one DK context block into its ordered ancient witnesses.

    Returns None -- FAIL CLOSED, caller emits the column exactly as before,
    unchanged -- when fewer than two witnesses are found. A column that does
    not split cleanly must not be split at all.

    Text before the first citation is kept as a leading witness with no
    `source` key (John's ruling: do not drop it), rendered with no
    small-caps label. A bare line-marker immediately preceding a citation
    (only whitespace between) is reattributed to THAT citation -- moved out
    of the previous witness's trailing text into this witness's own leading
    text -- before the source/text split below.

    The source/text boundary is the first Greek letter: a citation label is
    Latin-alphabet and its testimony is Greek, so the first Greek character
    is where the label ends.

    A WHOLLY-LATIN witness has no such boundary -- a Latin source quoting
    Democritus in Latin (Democritus B300 alone carries five: Vitruvius,
    Pliny twice, Columella, Petronius) would put its entire paragraph on the
    label side and leave the body empty, rendering a whole page of Pliny as
    a small-caps citation label. Splitting label from reference inside Latin
    is guesswork -- the reference tail varies ("PLIN. N. H. XXIV 160",
    "PETRON. 88, 2", "GAL. de simpl. medic. X, 1 (XII 250 K.)") and the body
    can begin with a capital ("...160 Democriticerte..."). So these fail
    closed the same way the split itself does: no `source` key at all, the
    whole segment as text, rendered unlabelled exactly as apparatus reads
    today -- just in its own row. Being un-labelled is honest; being
    mislabelled is not.
    """
    starts = _real_anchor_starts(text)
    if len(starts) < 2:
        return None

    # Segment i spans [lo[i], hi[i]). DK's bare line-marker sits at the TAIL
    # of one segment but belongs to the citation AFTER it, so where a tail
    # carries one, that segment ends at the marker and the next one begins
    # there. Done purely on offsets -- the text is never rewritten, which is
    # what lets a caller slice tokens by [start, end).
    bounds = [0] + starts + [len(text)]
    lo = list(bounds[:-1])
    hi = list(bounds[1:])
    for i in range(len(lo) - 1):
        m = _MARKER_RE.search(text[lo[i] : hi[i]])
        if m:
            hi[i] = lo[i] + m.start()
            lo[i + 1] = lo[i] + m.start()

    witnesses: list[dict] = []
    for i, (a, b) in enumerate(zip(lo, hi)):
        raw = text[a:b]
        stripped = raw.strip()
        if not stripped:
            continue
        start = a + (len(raw) - len(raw.lstrip()))

        def entry(s: str, off: int, source: str | None = None) -> dict:
            w = {"text": s, "start": off, "end": off + len(s)}
            return {"source": source, **w} if source else w

        # The lead-in run before the first citation carries no label.
        if i == 0:
            witnesses.append(entry(stripped, start))
            continue

        rel = next((j for j, ch in enumerate(stripped) if _is_greek_letter(ch)), None)
        # Fail closed PER WITNESS: a wholly-Latin witness (no Greek at all)
        # and a mostly-Latin one whose Greek arrives late both put running
        # prose on the label side, so neither gets a label -- see docstring.
        if rel is None:
            witnesses.append(entry(stripped, start))
            continue
        source = stripped[:rel].strip()
        if len(_PROSE_WORD_RE.findall(source)) >= _MAX_LABEL_PROSE_WORDS:
            witnesses.append(entry(stripped, start))
            continue

        # Back the boundary up over sigla attached to that first Greek word.
        # A token can BEGIN at an editorial bracket or quote ("[θε]ὸν",
        # "<τὴν", "’τῶν"), so cutting at the first Greek LETTER would split
        # the word's own token across the label/body line and drop it from
        # the body -- five real tokens corpus-wide, each a Greek word a
        # reader would expect to be able to click.
        while rel > 0 and stripped[rel - 1] in "[<(‘’‹«":
            rel -= 1
        source = stripped[:rel].strip()

        tail = stripped[rel:]
        body_off = start + rel + (len(tail) - len(tail.lstrip()))
        witnesses.append(entry(tail.strip(), body_off, source))
    return witnesses
