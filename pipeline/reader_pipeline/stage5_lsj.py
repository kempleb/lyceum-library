"""Stage 5: dictionary entries for corpus-occurring lemmata only.

Greek: streams grc.lsj.xml (110MB, 116,728 <div2 key="..."> entries), keeping
just the entries whose key matches a lemma in the Stage 4 analyses (exact
match first, then digit/macron-stripped base match, which also picks up all
homonyms a)1, a)2, ...). Latin (Wave 2 Batch 1b): streams
lat.ls.perseus-eng1.xml (Lewis & Short, ~78MB, 51,669 <div1 key="..."> entries)
the same way -- the TEI shape is the same family (div/head/orth/gen/sense/
cit/bibl/author), just a different enclosing div name and a handful of
Latin-only tags (itype/pos/usg/case/mood/number/lbl); see _DIV_TAG/_TAG_MAP.
Entry bodies are converted from Perseus TEI to compact HTML and sharded by
initial letter, into a per-language shard directory (SHARD_DIR).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from html import escape
from pathlib import Path

from lxml import etree

from .config import BUILD_DIR, Manifest

# Master dictionary source file per work.language, resolved under
# manifest.diogenes_data(). 'grc' is LSJ; 'lat' is Lewis & Short (Wave 2
# Batch 1b). The 'lat' filename is the REAL Diogenes filename
# (lat.ls.perseus-eng1.xml, confirmed against docs/wave2-latin-design.md §6 —
# an earlier placeholder "lat.ls.xml" here was a silent-wrong-file landmine
# that would have passed a naive build once stage5 grows Latin support).
_DICTIONARY_FILENAMES = {"grc": "grc.lsj.xml", "lat": "lat.ls.perseus-eng1.xml"}

# Both dictionaries are a flat stream of per-lemma div fragments (no root
# element), but Perseus TEI names the element differently per dictionary:
# LSJ uses <div2 key="...">, Lewis & Short uses <div1 key="...">. Everything
# else about the streaming/shard/match approach is shared (see run() below).
_DIV_TAG = {"grc": "div2", "lat": "div1"}

# Shard directory name under build/stage5/ and build/dist/, per language —
# kept SEPARATE (not merged into one 'lsj' dir) because the two dictionaries
# are keyed in different, potentially-colliding key spaces (LSJ's Beta Code
# vs L&S's plain-Latin-plus-macron-marks) — app/src/components/LemmaPage.astro
# already made this call for the /lemma/<lang> route (`dictShardDir`), so
# stage5/stage7 mirror it rather than introducing a second convention.
SHARD_DIR = {"grc": "lsj", "lat": "ls"}


def _dictionary_path(manifest: Manifest) -> Path:
    language = manifest.language
    if language not in _DICTIONARY_FILENAMES:
        raise ValueError(f"unsupported work.language: {language!r}")
    return manifest.diogenes_data() / _DICTIONARY_FILENAMES[language]


# Letter-class spans keep the CSS in charge of presentation. Shared across
# both dictionaries -- LSJ (div2) and Lewis & Short (div1) use an overlapping
# TEI tag family (head/orth/gen/i/foreign/quote/cit/bibl/author/sense are
# identical in shape between the two, verified against real L&S entries
# below); the L&S-only rows (itype, pos, usg, case, mood, number, lbl) cover
# tags LSJ's entries don't use. Any tag not in this map (L&S's rare cb/pb/
# ref/figure/sup/hi) falls through to _to_html's generic `else` branch
# (a plain `lsj-<tag>` span) rather than raising -- new/rare TEI tags degrade
# to unstyled text, they don't break the build.
_TAG_MAP = {
    "head": ("b", "lsj-head"),
    "orth": ("b", "lsj-orth"),
    "gen": ("span", "lsj-gen"),
    "etym": ("span", "lsj-etym"),
    "i": ("i", None),
    "tr": ("span", "lsj-tr"),
    "foreign": ("span", "lsj-greek"),
    "quote": ("span", "lsj-quote"),
    "cit": ("span", "lsj-cit"),
    "bibl": ("span", "lsj-bibl"),
    "author": ("span", "lsj-author"),
    "title": ("i", "lsj-title"),
    "sense": ("div", "lsj-sense"),
    # Lewis & Short only (Wave 2 Batch 1b) -- morphology/usage labels that
    # LSJ's entries don't carry.
    "itype": ("i", "lsj-itype"),
    "pos": ("span", "lsj-pos"),
    "usg": ("span", "lsj-usg"),
    "case": ("span", "lsj-case"),
    "mood": ("span", "lsj-mood"),
    "number": ("span", "lsj-number"),
    "lbl": ("span", "lsj-lbl"),
}

# '#' (added Wave 2 Batch 1b): stage4's Latin lemma field carries Diogenes'
# OWN homonym marker as "qui#1", "edo#1" (confirmed: 10.79% of all
# latin-analyses.txt lemma groups, not a rare corner -- e.g. "qui", "edo",
# "is#1"/"is#2" are common words) -- a DIFFERENT convention from Lewis &
# Short's own trailing-digit homonym key ("qui1", "e^do1", "e^do2"). Without
# stripping '#' here, base_key("qui#1") left a dangling "qui#" that could
# never match L&S's base_index (keyed off base_key("qui1") == "qui"), so
# ~11% of Latin lemma lookups would silently fail the base-match fallback.
# '#' never appears in Greek data (grc.lsj.xml, greek-analyses.txt both
# confirmed clean), so this is safe to add to the shared strip sets.
_BASE_STRIP = re.compile(r"[0-9_^\-#]")
_FOLD_STRIP = re.compile(r"[0-9_^\-/=\\|+#]")
_CONNECTIVE = re.compile(r"^[\s,;]*(?:(?:or|and)[\s,;]*)?$", re.IGNORECASE)
_DANGLING_CONNECTIVE = re.compile(r"(?:\s*[,;]\s*)?\b(?:or|and)\s*$", re.IGNORECASE)
_DANGLING_ARTICLE = re.compile(r"\b(?:an?|the)$", re.IGNORECASE)


def base_key(key: str) -> str:
    return _BASE_STRIP.sub("", key)


def fold_key(key: str) -> str:
    """Accent/diaeresis/macron/hyphen-insensitive form; breathings kept."""
    return _FOLD_STRIP.sub("", key)


def lemma_candidates(lemma: str) -> list[tuple[str, str]]:
    """Ranked (index, value) lookups for a lemma against LSJ keys.

    Fallbacks cover Morpheus lemmatizations LSJ heads differently:
    adverbs in -ws live under the adjective (a)kribw=s -> a)kribh/s),
    verbal adjectives in -teos are headed as -teon, and synthetic
    compounds carry hyphens and extra accents (a)nti/-bla/ptw).
    """
    cands = [("exact", lemma), ("base", base_key(lemma))]
    fold = fold_key(lemma)
    cands.append(("fold", fold))
    if fold.endswith("ws"):
        cands.append(("fold", fold[:-2] + "hs"))
    if fold.endswith("teos"):
        cands.append(("fold", fold[:-4] + "teon"))
    return cands


def shard_letter(key: str) -> str:
    """Mirrors the THREE consumer-side implementations exactly (skip '*',
    first ASCII a-z, else '_'): preflight.py's `_lsj_shard`,
    shared/lib/data.ts's `lsjShard`, and LemmaPage.astro's
    `lsjShardLetter`. Bug this replaces (surfaced by the Wave 2 Batch 1b
    case-fold fix, item 2 -- the FIRST thing that made a capitalized L&S
    proper-name key like "Py_tha^go^ras" actually get matched/sharded):
    the old `ch.isalpha()` accepted an UPPERCASE first letter too, sharding
    "Py_tha^go^ras" under 'P' while every reader (the three consumers
    above) looks for it under 'y' (skipping the capital, matching only
    a-z) -- every capitalized L&S key was written to a shard file no
    reader would ever check, silently failing preflight's shared-shard
    coverage gate. Harmless for Greek (Beta Code's capital marker is '*',
    never a literal uppercase ASCII letter, so isalpha() and this were
    always equivalent there)."""
    for ch in key:
        if ch == "*":
            continue
        if "a" <= ch <= "z":
            return ch
    return "_"


def lift_demoted_siblings(
    senses: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Fix Perseus TEI's demoted print-siblings (review item 99).

    Ported from Grammata's proven fix for the same Perseus LSJ data --
    scripts/wordtool/t8rows.py's `lift_demoted_siblings` (measured there at
    8,091 demoted entries against 209 preamble entries on these shards).

    Perseus marks an LSJ entry's implicit, unnumbered first sense `level="1"`
    and the print divisions II., III., IV.… that follow it `level="2"`, so
    anything that indents by level draws II. onward as children of the first
    sense instead of as its siblings. In print they are one flat series
    (χείρ: I unnumbered, with sub-senses 2., 3.; then II, III, IV… as
    siblings of I) -- so lift the demoted run back up by one level, children
    riding along with it.

    `senses` is an entry's ordered list of (level, n) pairs, one per <sense>
    (n is the printed numeral, e.g. "II." or "II", or "" for an unnumbered
    sense). Returns a new list with the fix applied, or `senses` itself
    unchanged when the entry doesn't match.

    Trigger: the first sense is unnumbered. The "run" is every sense after
    it up to (but not including) the next sense whose level is <= the
    opener's own level -- that boundary sense and everything after it belong
    to a later, independently-numbered band and are copied through
    unchanged (an entry like ἀναβαίνω with a later "B." band keeps B and
    everything nested under it). The run lifts only when its shallowest
    level is exactly one deeper than the opener's AND the first sense at
    that shallowest level is numbered "II" (or "II."). Guard: if that
    position is numbered "I" instead, the unnumbered opening is a genuine
    preamble -- the general sense the print states before it divides I.,
    II., III. (ἁγνός: "pure, chaste, holy" then I., II., III., already
    correctly nested) -- and must NOT change. Action: every sense in the run
    has its level reduced by one, never below 1.
    """
    if len(senses) < 2:
        return senses
    l0, n0 = senses[0]
    if n0.strip():
        return senses
    stop = next((j for j in range(1, len(senses)) if senses[j][0] <= l0), len(senses))
    run = range(1, stop)
    if not len(run) or min(senses[j][0] for j in run) != l0 + 1:
        return senses
    first = next(j for j in run if senses[j][0] == l0 + 1)
    if (senses[first][1] or "").strip().rstrip(".") != "II":
        return senses
    lifted = [senses[0]]
    for j in run:
        lvl, n = senses[j]
        lifted.append((max(lvl - 1, 1), n))
    lifted.extend(senses[stop:])
    return lifted


_LETTER_ADDR = re.compile(r"^[A-Z]$")
_ROMAN = re.compile(r"^[IVX]+$")


def _is_letter_addr(n: str) -> bool:
    """True for a print letter-band address (A, B, C...) -- never I, V, X,
    which read as roman numerals rather than letters. Adapted from
    Grammata's `is_letter_addr` (scripts/wordtool/t8rows.py)."""
    return bool(_LETTER_ADDR.match(n)) and n not in ("I", "V", "X")


def demote_band_first_sense(
    senses: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Fix Perseus TEI's demoted division run under a print letter band
    (review item 99, second shape).

    Ported from Grammata's `demote_band_first_sense`
    (scripts/wordtool/t8rows.py, 2026-08-31) -- the mirror image of
    `lift_demoted_siblings` above. There, the demoted run sits under an
    entry-opening unnumbered sense and gets lifted up to join it. Here
    the same demotion happens under a letter band's own unnumbered first
    sense (A., B., ...), and the fix is the opposite move: demote that
    first sense down one level, INTO the run, rather than lift the run
    out to meet it.

    ἀραρίσκω prints "A. ... join together ... II. fit together ... III.
    fit, equip ... IV. make fitting ... B. ...". Perseus gives A and the
    unnumbered "join together" the same level, so "join together" reads
    as a second band and II-IV nest under it instead of beside it.
    Demoting "join together" to join its roman siblings restores the
    print's single band with one division series.

    Same trigger as the lift, checked at every unnumbered sense in the
    entry (not just the first): the run one level down must open on "II"
    (or "II."). Here the unnumbered sense is additionally required to sit
    immediately after a same-level print letter address (A, B, C...,
    never I, V, X) -- that is what marks it as a band's own opener rather
    than some other unnumbered sense, and is why this rule can't just
    reuse the lift's opener-only check. Grammata measured 3 Greek entries
    against this shape: ἀραρίσκω, ἐρύω, φύω; none in Latin.
    """
    out = list(senses)
    for i in range(1, len(out)):
        lvl, n = out[i]
        if n.strip():
            continue
        prev = None
        for j in range(i - 1, -1, -1):
            if out[j][0] < lvl:
                break
            if out[j][0] == lvl:
                prev = out[j]
                break
        if prev is None or not _is_letter_addr((prev[1] or "").strip().rstrip(".")):
            continue
        stop = next((j for j in range(i + 1, len(out)) if out[j][0] <= lvl), len(out))
        run = range(i + 1, stop)
        if not len(run) or min(out[j][0] for j in run) != lvl + 1:
            continue
        first = next(j for j in run if out[j][0] == lvl + 1)
        if (out[first][1] or "").strip().rstrip(".") != "II":
            continue
        out[i] = (lvl + 1, n)
    return out


def demote_roman_first_subsense(
    senses: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Fix Perseus TEI's roman "I" where the print means arabic "1."
    (review item 99, third shape -- an OCR misread, not a mis-nesting).

    Ported from Grammata's `demote_roman_first_subsense`
    (scripts/wordtool/t8rows.py, 2026-08-31). A division's first
    sub-sense sits at the DIVISION's own level instead of one below it --
    the same demotion `lift_demoted_siblings` and `demote_band_first_sense`
    fix -- and where that sub-sense opens an arabic run, its "1." also
    arrives transcribed as a capital "I": the two are one glyph apart in
    the printed face, an OCR read rather than something Liddell and Scott
    wrote.

    σπουδάζω proves it inside one entry: "II. trans." has children 1.,
    2., while "I. intr." has children I., 2., 3., 4. -- same position,
    same entry, two different glyphs for it.

    Three conditions, all required, because "I." followed by "2." is
    ordinary LSJ everywhere else -- φρήν is "I. midriff ... 2. heart ...
    3. mind ... 4. will", a division with sub-senses that must not be
    renumbered. What marks the artifact: the sense itself is numbered
    "I" (not unnumbered); a roman sibling already stands before it at the
    same level, so this cannot be another division opening a fresh
    series; and the run beneath it opens on the print's own "2." The
    sense then takes the level AND numeral ("1", matching Perseus's
    undotted `n` attribute -- entry_html supplies the period) that run
    belongs at. Grammata measured 3 entries against this shape, two in Greek
    (ἐπιτυγχάνω, σπουδάζω) and one in Latin (exspiro, Lewis & Short) --
    out of scope here, LSJ only.
    """
    out = list(senses)
    for i in range(1, len(out)):
        lvl, n = out[i]
        if (n or "").strip().rstrip(".") != "I":
            continue
        prev = None
        for j in range(i - 1, -1, -1):
            if out[j][0] < lvl:
                break
            if out[j][0] == lvl:
                prev = (out[j][1] or "").strip().rstrip(".")
                break
        if not prev or not _ROMAN.match(prev):
            continue
        stop = next((j for j in range(i + 1, len(out)) if out[j][0] <= lvl), len(out))
        run = range(i + 1, stop)
        if not len(run):
            continue
        deep = min(out[j][0] for j in run)
        first = next(j for j in run if out[j][0] == deep)
        if (out[first][1] or "").strip().rstrip(".") != "2":
            continue
        # A fourth condition, from our own data (w(s, Grok review
        # 2026-09-24): the artifact "I." sits INSIDE a roman series, so
        # the next roman sibling, if any, continues from the one before it
        # (I. -> II., II. -> III.). ὡς B. lists "I.-IV." as a summary and
        # then restarts "I." to treat each in full; that "I." is followed
        # by "II.", not "V.", and must not move.
        nxt = out[stop][1] if stop < len(out) and out[stop][0] == lvl else ""
        nxt = (nxt or "").strip().rstrip(".")
        if _ROMAN.match(nxt) and _roman_value(nxt) != _roman_value(prev) + 1:
            continue
        out[i] = (deep, "1")
    return out


def _roman_value(numeral: str) -> int:
    values = {"I": 1, "V": 5, "X": 10}
    total = 0
    for k, ch in enumerate(numeral):
        v = values[ch]
        total += -v if k + 1 < len(numeral) and values[numeral[k + 1]] > v else v
    return total


def _lift_entry_sense_levels(entry_el) -> None:
    """Apply the three demoted-sense fixes above to one LSJ entry's
    <sense> children in place, correcting each one's `level` (and, for
    `demote_roman_first_subsense`, `n`) attribute before HTML emission.
    LSJ-only (see entry_html's call site: <div2> is LSJ, Lewis & Short's
    <div1> is untouched). <sense> elements are flat direct children of the
    entry div, each carrying its own level/n -- confirmed against χείρ and
    ἁγνός (no nested <sense> in the TEI).

    Order: `lift_demoted_siblings` first (an entry-opening demotion), then
    `demote_band_first_sense` (a band-opening demotion, which reads levels
    the lift may have already corrected), then `demote_roman_first_subsense`
    (an independent OCR misread) last -- it is the only one of the three
    that changes a sense's numeral rather than only its level, so applying
    it last keeps the other two rules' level-only bookkeeping simple."""
    sense_els = entry_el.findall("sense")
    senses = [(int(el.get("level") or "1"), el.get("n") or "") for el in sense_els]
    fixed = lift_demoted_siblings(senses)
    fixed = demote_band_first_sense(fixed)
    fixed = demote_roman_first_subsense(fixed)
    if fixed == senses:
        return
    for el, (level, n), (_orig_level, orig_n) in zip(sense_els, fixed, senses):
        el.set("level", str(level))
        if n != orig_n:
            el.set("n", n)


def _to_html(el) -> str:
    tag = el.tag if isinstance(el.tag, str) else None
    parts = []
    if tag == "sense":
        level = el.get("level") or "1"
        n = el.get("n") or ""
        parts.append(f'<div class="lsj-sense" data-level="{escape(level)}">')
        if n:
            parts.append(f'<b class="lsj-sense-n">{escape(n)}.</b> ')
        body_open = True
    elif tag in _TAG_MAP:
        html_tag, cls = _TAG_MAP[tag]
        cls_attr = f' class="{cls}"' if cls else ""
        parts.append(f"<{html_tag}{cls_attr}>")
        body_open = True
    elif tag is None:
        body_open = False
    else:
        parts.append(f'<span class="lsj-{escape(tag)}">')
        body_open = True
    if tag is not None and el.text:
        parts.append(escape(el.text))
    for child in el:
        parts.append(_to_html(child))
    if body_open:
        if tag == "sense":
            parts.append("</div>")
        else:
            html_tag = _TAG_MAP.get(tag, ("span", None))[0]
            parts.append(f"</{html_tag}>")
    if el.tail:
        parts.append(escape(el.tail))
    return "".join(parts)


def entry_html(entry_el) -> str:
    if entry_el.tag == "div2":
        _lift_entry_sense_levels(entry_el)
    parts = []
    if entry_el.text:
        parts.append(escape(entry_el.text))
    for child in entry_el:
        parts.append(_to_html(child))
    return "".join(parts).strip()


def _strip_edge_punctuation(value: str) -> str:
    while value and (
        value[0].isspace() or unicodedata.category(value[0]).startswith("P")
    ):
        value = value[1:]
    while value and (
        value[-1].isspace() or unicodedata.category(value[-1]).startswith("P")
    ):
        value = value[:-1]
    return value


def derive_short_def(entry_el) -> str:
    """Derive a compact definition from an LSJ entry's leading italic run."""
    sense = next((el for el in entry_el.iter() if el.tag == "sense"), None)
    body = sense if sense is not None else entry_el
    children = list(body)
    first_i = next((i for i, child in enumerate(children) if child.tag == "i"), None)
    if first_i is None:
        return ""

    parts = ["".join(children[first_i].itertext())]
    previous = children[first_i]
    for child in children[first_i + 1 :]:
        if child.tag != "i" or not _CONNECTIVE.fullmatch(previous.tail or ""):
            break
        parts.extend((previous.tail or "", "".join(child.itertext())))
        previous = child

    short_def = " ".join("".join(parts).split())
    short_def = _strip_edge_punctuation(short_def)
    short_def = _DANGLING_CONNECTIVE.sub("", short_def)
    short_def = _strip_edge_punctuation(short_def)
    # Adjectives in -ikos/-ios are glossed "of or belonging to a <Greek noun>",
    # and the noun is untranslated Greek outside the italic run: the derivation
    # would end on a stranded article. Give up rather than ship broken English.
    if _DANGLING_ARTICLE.search(short_def):
        return ""
    # A definition this long is one continuous italic clause (technical terms
    # like kefalaiwth/s), never a joined run — cutting it would reintroduce the
    # truncation this function exists to repair, so keep the shipped gloss.
    if len(short_def) > 100:
        return ""
    return short_def


def needed_lemmata(analyses: dict) -> set[str]:
    lemmata = set()
    for groups in analyses.values():
        for g in groups:
            if g["lemma"]:
                lemmata.add(g["lemma"])
    return lemmata


def _lemma_parse_hints(analyses: dict) -> dict[str, str]:
    """First-seen stage4 `parse` string per lemma (Latin homonym-filter
    input, Wave 2 Batch 1b — see `_filter_homonym_candidates` below). A
    Diogenes lemma always names one specific headword, so any ONE token's
    parse for that lemma is representative of its part of speech."""
    hints: dict[str, str] = {}
    for groups in analyses.values():
        for g in groups:
            lemma = g.get("lemma")
            if lemma and lemma not in hints:
                hints[lemma] = g.get("parse") or ""
    return hints


# ── Latin homonym fan-out filtering (Wave 2 Batch 1b review finding) ───────
# Governing principle: THE READER MUST NEVER BE SHOWN A WRONG GLOSS AS IF
# CERTAIN — either correctly filtered, or explicitly modeled as ambiguous.
#
# The bug: base_key()/fold_key() strip BOTH Diogenes' own '#N' homonym
# marker AND Lewis & Short's own trailing-digit homonym marker down to the
# same bare stem ("est" -> lemma "edo#1" -> base "edo" -> EVERY L&S entry
# based "edo": e^do1 "to eat" [correct], e_do2 "to publish", e^do3 "a
# glutton, noun" [both wrong]). Diogenes' '#N' does NOT correspond to L&S's
# own digit (confirmed: "qui#1"/"qui#2" both legitimately match BOTH
# "qui1" and "qui_2" — see docs/wave2-latin-design.md), so a naive #N ->
# digit map is never built; instead:
#
#   (a) filter what's DERIVABLE — an L&S candidate's own grammatical
#       markers (<pos>, <gen>, <itype>) give a coarse POS class; the
#       corpus analysis's own `parse` string (stage4) gives the same coarse
#       class for the token actually being looked up. A candidate whose
#       class contradicts the token's is wrong and is dropped (edo3, a
#       NOUN, can never be what a VERB-parsed "est" means). Pure
#       cross-reference stub entries (L&S's "sum2 = eum ... v. is.", no
#       real sense content) are dropped too, whenever a substantive
#       candidate survives.
#   (b) whatever's left after (a) with MORE than one candidate is a real
#       residual ambiguity nothing here can resolve further (e.g. qui1 vs
#       qui_2 for "quod" — both legitimate, same POS class, no signal left
#       to prefer one) — kept as-is; the reader-facing layers (WordPopup,
#       LemmaPage) are responsible for rendering an explicit "N dictionary
#       entries match this headword" group rather than picking one
#       silently.
#
# Entirely a Latin-path concern: Greek's `_BASE_STRIP`/`_FOLD_STRIP' never
# see a '#' (enforced by the loud gate in `run()` below), so a Greek
# base/fold match is never actually a homonym fan-out in the first place —
# `ambiguous_pos`/`ambiguous_stub` stay empty on that path and nothing here
# executes.

_VERB_PARSE_RE = re.compile(
    r"\b(ind|subj|imperat|inf|part|gerundive|supine|"
    r"pres|imperf|fut|perf|plup|futperf|act|pass)\b"
)
_CASE_PARSE_RE = re.compile(r"\b(nom|gen|dat|abl|voc|acc)\b")


def _analysis_pos_class(parse: str) -> str:
    """Coarse POS class from a stage4 Latin `parse` string: 'pres ind act
    3rd sg' -> verb, 'neut gen sg' -> nominal (noun/adj/pron alike -- L&S
    doesn't need finer here), 'indeclform (conj)' -> particle. 'unknown'
    when the parse string doesn't say (never filters on it).

    The verb vocabulary is the FULL set confirmed against a real corpus
    build's stage4/analyses.json parse tokens (Wave 2 Batch 1b real-build
    finding, post-fix verification): the initial mood-only guess
    ("ind|subj|imp|inf|part|ger|sup") missed real forms whose mood is
    spelled differently ("imperat", not "imp") or omitted entirely when a
    tense+voice pair alone implies indicative ("imperf act 3rd sg" is a
    genuine, observed parse with no mood token at all) -- either miss left
    `_analysis_pos_class` returning 'unknown' for a real verb token, which
    (correctly, per this module's never-drop-to-zero design) skips POS
    filtering rather than filtering wrongly, but under-delivered the fix:
    "est" -> edo#1 kept edo3 (a NOUN) unfiltered because its own occurrence
    happened to parse "fut imperat act 3rd sg", not the "pres ind act 3rd
    sg" this regex was checked against in isolation. Tense/voice tokens are
    included alongside mood/nonfinite ones for exactly that reason -- every
    one of them is verb-only vocabulary; nominal words carry case, never
    tense or voice."""
    p = (parse or "").lower()
    if _VERB_PARSE_RE.search(p):
        return "verb"
    if _CASE_PARSE_RE.search(p):
        return "nominal"
    if "indeclform" in p:
        return "particle"
    return "unknown"


_VERB_ITYPE_RE = re.compile(r",\s*[1-4]$")
_NOMINAL_POS = {
    "adj.", "pron.", "p. a.", "dem. pron.", "rel. pron.", "indef. pron.",
    "num. adj.", "interrog. pron.", "poss. pron.",
}
_PARTICLE_POS = {"adv.", "conj.", "prep.", "interj."}


def _entry_pos_class(entry_el) -> str:
    """Coarse POS class from an L&S entry's OWN markers (<pos>, <gen>,
    <itype>) -- the mirror of `_analysis_pos_class` above. 'unknown' when
    none of them say (never filters a candidate out)."""
    pos = (entry_el.findtext("pos") or "").strip().lower()
    if pos.startswith("v."):
        return "verb"
    if pos in _PARTICLE_POS:
        return "particle"
    if pos in _NOMINAL_POS:
        return "nominal"
    gen = (entry_el.findtext("gen") or "").strip()
    if gen:
        return "nominal"  # <gen> (m./f./n./comm.) only ever marks a noun
    itype = (entry_el.findtext("itype") or "").strip().lower()
    if itype in ("esse", "fŭi, esse") or _VERB_ITYPE_RE.search(itype):
        return "verb"  # principal-parts pattern, e.g. "ēdi, ēsum, 3"
    if itype.startswith("indecl"):
        return "particle"
    return "unknown"


_STUB_HTML_LEN = 200  # below this, an entry with no substantive sense content


def _is_crossref_stub(entry_el, html: str) -> bool:
    """A pure cross-reference redirect (L&S's "sum2 = eum ... v. is.", or
    the barely-longer "sum3 in composition, for sub before m; v. sub") --
    detectable by shape: no <sense> at all, or a real-but-trivial one and
    very little content overall. Guarded at the call site by `if
    non_stub:`, so this can never discard the LAST surviving candidate --
    it only prunes a stub when a substantive alternative remains."""
    if entry_el.find("sense") is None:
        return True
    return len(html) < _STUB_HTML_LEN


def _filter_homonym_candidates(
    candidates: list[str],
    parse: str,
    pos_of: dict[str, str],
    stubs: set[str],
) -> list[str]:
    """Tier (a) of the homonym fan-out fix (see the module note above):
    narrow a multi-candidate L&S match using whatever's derivable. Never
    returns an empty list from a non-empty input -- a filter step that
    would drop every remaining candidate is skipped instead, so genuine
    residual ambiguity (tier (b)) is always what's left to render."""
    analysis_class = _analysis_pos_class(parse)
    if analysis_class != "unknown":
        pos_matched = [
            k for k in candidates
            if pos_of.get(k, "unknown") in (analysis_class, "unknown")
        ]
        if pos_matched:
            candidates = pos_matched
    if len(candidates) > 1:
        non_stub = [k for k in candidates if k not in stubs]
        if non_stub:
            candidates = non_stub
    return candidates


def run(manifest: Manifest) -> Path:
    language = manifest.language
    shard_dir_name = SHARD_DIR[language]
    analyses = json.loads(
        (BUILD_DIR / "stage4" / "analyses.json").read_text(encoding="utf-8")
    )
    lemmata = needed_lemmata(analyses)
    if language == "grc":
        # '#' is Diogenes' Latin-only homonym marker (edo#1, qui#2, ...) --
        # never present in Greek's own lemma vocabulary (confirmed against
        # greek-analyses.txt; see _BASE_STRIP's docstring). A loud gate, not
        # a comment: if this ever fires, `_BASE_STRIP`/`_FOLD_STRIP` would
        # silently mis-strip a real Greek character and the base/fold
        # fallback match would be corrupted for that lemma.
        hashed = sorted(l for l in lemmata if "#" in l)
        if hashed:
            raise ValueError(
                f"{manifest.work_id}: {len(hashed)} Greek lemma(s) contain "
                f"'#' (e.g. {hashed[:5]}) -- '#' is Diogenes' Latin-only "
                f"homonym marker; Greek data was assumed clean of it and "
                f"no longer is (see stage5_lsj._BASE_STRIP's docstring)"
            )

    out_dir = BUILD_DIR / "stage5"
    (out_dir / shard_dir_name).mkdir(parents=True, exist_ok=True)
    # This dir is a PER-WORK artifact, but nothing used to empty it: letters
    # this work doesn't touch kept whatever the previously built work left
    # behind, and stage7's _merge_shared_lsj globs *.json — so stale shards
    # from before a build leaked into build/dist in whatever order history
    # happened to leave them (byte-nondeterminism across otherwise identical
    # builds). The dir's contents must be exactly this work's output.
    for stale in (out_dir / shard_dir_name).glob("*.json"):
        stale.unlink()
    if not lemmata:
        # Blocker 1 fix (Sol): a LEXICON-ON work (`manifest.lexicon` — the
        # default) with zero resolved lemmata is NOT the same shape as a
        # declared no-lexicon work — stage4 now guarantees (see its own
        # Blocker 1 fix) that a lexicon-on work with real keyed tokens never
        # silently produces an empty analyses.json for THAT reason, but
        # stage4's own lookup can still legitimately resolve zero of them
        # (e.g. a wrong/missing analyses filename — the exact
        # `_DICTIONARY_FILENAMES` landmine this module's own history already
        # hit once). Failing loudly here, rather than falling through to the
        # same trivial empty-artifact shape, is what actually catches that:
        # a genuine no-lexicon work must declare `work.lexicon: false`.
        if manifest.lexicon:
            raise ValueError(
                f"{manifest.work_id}: work.lexicon is true but stage4 "
                f"resolved zero lemmata — either stage4's analyses lookup "
                f"failed for every keyed token (e.g. a wrong/missing "
                f"analyses file) or something upstream silently dropped "
                f"every key; a genuine no-lexicon work must declare "
                f"work.lexicon: false instead of producing this empty "
                f"artifact shape"
            )
        # A no-lexicon work (`work.lexicon: false`, Wave 2 §4.2) has no token
        # carrying `k`, so stage4's analyses.json is legitimately `{}` and
        # there is nothing to look up here. Skip the dictionary scan entirely
        # and emit the same trivial-but-valid shard-less output stage7
        # already expects from a work with genuinely zero dictionary hits.
        (out_dir / "lemma_map.json").write_text("{}", encoding="utf-8")
        (out_dir / "short_defs.json").write_text("{}", encoding="utf-8")
        (out_dir / "missing_lemmata.json").write_text("[]", encoding="utf-8")
        summary = {
            "lemmata_needed": 0, "lsj_entries_kept": 0,
            "shards": 0, "lemmata_without_entry": 0,
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
        return out_dir

    # The master dictionary file is not one XML document (no root element); it
    # is a stream of <div1>/<div2> fragments (per-language element name, see
    # _DIV_TAG), so it is scanned line-wise.
    lsj_path = _dictionary_path(manifest)
    div_tag = _DIV_TAG[language]
    div_open = f"<{div_tag} "
    div_close = f"</{div_tag}>"
    key_re = re.compile(rf'<{div_tag} [^>]*key="([^"]*)"')

    # Pass 1: every dictionary key, plus base/fold indexes for fallback matching.
    all_keys: set[str] = set()
    base_index: dict[str, list[str]] = defaultdict(list)
    fold_index: dict[str, list[str]] = defaultdict(list)
    with open(lsj_path, encoding="utf-8") as f:
        for line in f:
            if div_open not in line:
                continue
            m = key_re.search(line)
            if not m:
                continue
            key = m.group(1)
            all_keys.add(key)
            base_index[base_key(key)].append(key)
            fold_index[fold_key(key)].append(key)

    if language == "grc":
        # See the lemmata-side gate above -- same invariant, the dictionary
        # side. Both must hold for the base/fold strip to be trustworthy.
        hashed_keys = sorted(k for k in all_keys if "#" in k)
        if hashed_keys:
            raise ValueError(
                f"{manifest.work_id}: {len(hashed_keys)} Greek LSJ key(s) "
                f"contain '#' (e.g. {hashed_keys[:5]}) -- '#' is Diogenes' "
                f"Latin-only homonym marker; grc.lsj.xml was assumed clean "
                f"of it and no longer is (see stage5_lsj._BASE_STRIP's "
                f"docstring)"
            )

    # Wave 2 Batch 1b homonym fan-out fix, tier (a) input: classify every
    # candidate key that's part of an AMBIGUOUS base/fold group (a small
    # minority of the dictionary) by its own POS markers, via one extra
    # targeted scan of the same file (see the module note above
    # `_filter_homonym_candidates`). Greek is untouched -- `candidate_keys`
    # stays empty and this whole block is a no-op on that path.
    ambiguous_pos: dict[str, str] = {}
    ambiguous_stub: set[str] = set()
    parse_hint: dict[str, str] = {}
    if language == "lat":
        parse_hint = _lemma_parse_hints(analyses)
        candidate_keys: set[str] = set()
        for keys in base_index.values():
            if len(keys) > 1:
                candidate_keys.update(keys)
        for keys in fold_index.values():
            if len(keys) > 1:
                candidate_keys.update(keys)
        if candidate_keys:
            buf2: list[str] = []
            want2 = False
            key2 = ""
            with open(lsj_path, encoding="utf-8") as f:
                for line in f:
                    if div_open in line:
                        m = key_re.search(line)
                        key2 = m.group(1) if m else ""
                        want2 = key2 in candidate_keys
                        buf2 = []
                    if want2:
                        buf2.append(line)
                        if div_close in line:
                            fragment = "".join(buf2)
                            start = fragment.index(div_open)
                            end = fragment.rindex(div_close) + len(div_close)
                            entry_el = etree.fromstring(fragment[start:end])
                            html2 = entry_html(entry_el)
                            ambiguous_pos[key2] = _entry_pos_class(entry_el)
                            if _is_crossref_stub(entry_el, html2):
                                ambiguous_stub.add(key2)
                            want2 = False

    # Match lemmata to LSJ keys by the ranked candidate list.
    lemma_map: dict[str, list[str]] = {}
    missing: list[str] = []
    for lemma in sorted(lemmata):
        matched: list[str] | None = None
        for kind, value in lemma_candidates(lemma):
            if kind == "exact" and value in all_keys:
                matched = [value]
            elif kind == "base" and base_index.get(value):
                matched = sorted(base_index[value])
            elif kind == "fold" and fold_index.get(value):
                matched = sorted(fold_index[value])
            if matched:
                break
        if matched and len(matched) > 1 and language == "lat":
            matched = _filter_homonym_candidates(
                matched, parse_hint.get(lemma, ""), ambiguous_pos, ambiguous_stub,
            )
        if matched:
            lemma_map[lemma] = matched
        else:
            missing.append(lemma)
    wanted = {k for keys in lemma_map.values() for k in keys}

    # Pass 2: extract and convert just the wanted entries.
    shards: dict[str, dict] = defaultdict(dict)
    short_defs: dict[str, str] = {}
    n_kept = 0
    buf: list[str] = []
    want = False
    key = ""
    with open(lsj_path, encoding="utf-8") as f:
        for line in f:
            if div_open in line:
                m = key_re.search(line)
                key = m.group(1) if m else ""
                want = key in wanted
                buf = []
            if want:
                buf.append(line)
                if div_close in line:
                    fragment = "".join(buf)
                    start = fragment.index(div_open)
                    end = fragment.rindex(div_close) + len(div_close)
                    entry_el = etree.fromstring(fragment[start:end])
                    head = entry_el.findtext("head") or key
                    shards[shard_letter(key)][key] = {
                        "key": key,
                        "head": head,
                        "html": entry_html(entry_el),
                    }
                    if language == "grc":
                        # Greek only, and not merely out of caution: every
                        # Latin parse entry ships with an EMPTY gloss (0 of
                        # 231,938 across the 14 Latin works, measured
                        # 2026-07-26), so there is no truncated gloss to
                        # extend there — stage7 would skip them all anyway.
                        # Deriving them would cost a full Lewis & Short scan
                        # per work for nothing, on a heuristic calibrated to
                        # LSJ's italic convention (L&S also opens senses with
                        # grammatical labels in <i>, "<i>gen. sing.</i>").
                        short_def = derive_short_def(entry_el)
                        if short_def:
                            short_defs[key] = short_def
                    n_kept += 1
                    want = False

    # out_dir/shard_dir_name already created above, before the zero-lemmata
    # early return. Shard dir is 'lsj' for Greek (unchanged dist layout),
    # 'ls' for Latin (see SHARD_DIR).
    # sort_keys on every shard writer (here, stage7's _merge_shared_lsj,
    # lsj_topup, lsj-merge.mjs): shard bytes are then a pure function of
    # shard CONTENT, never of work build order or leftover state, so
    # byte-identity across builds is a usable regression contract.
    for letter, entries in sorted(shards.items()):
        (out_dir / shard_dir_name / f"{letter}.json").write_text(
            json.dumps(entries, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    (out_dir / "lemma_map.json").write_text(
        json.dumps(lemma_map, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "short_defs.json").write_text(
        json.dumps(short_defs, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "missing_lemmata.json").write_text(
        json.dumps(missing, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    summary = {
        "lemmata_needed": len(lemmata),
        "lsj_entries_kept": n_kept,
        "short_defs": len(short_defs),
        "shards": len(shards),
        "lemmata_without_entry": len(missing),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return out_dir
