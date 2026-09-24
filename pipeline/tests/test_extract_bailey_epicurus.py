"""Regression tests for tools/extract_bailey_epicurus.py.

No network and no dependence on the vendored OCR text being present for the
unit-level tests: these exercise the module's pure functions directly with
small synthetic inputs. The determinism test is the one exception -- it
requires the real vendored source file (sources/bailey-epicurus/
bailey-extant-remains-1926.djvu.txt) and is skipped if that file is absent.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# tools/ is not a package; load the module directly by path (same pattern as
# the sibling extract_*_wikisource.py test files).
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_bailey_epicurus", _TOOLS / "extract_bailey_epicurus.py")
m = importlib.util.module_from_spec(_spec)
sys.modules["extract_bailey_epicurus"] = m
_spec.loader.exec_module(m)


# --- decimal anchors (the three Letters) -------------------------------------

def test_decimal_anchor_accepts_exact_continuity():
    lines = [
        "35 For those who are unable, Herodotus, to work in detail",
        "36 exposition. Indeed it is necessary to go back",
    ]
    out, skipped, unassigned = m._extract_letter(lines, 35, 83)
    assert out["35"] == "For those who are unable, Herodotus, to work in detail"
    assert out["36"] == "exposition. Indeed it is necessary to go back"
    assert skipped == []
    assert unassigned == []


def test_decimal_anchor_jumps_over_genuinely_unmarked_sections():
    # Bailey's own edition does not print every DL section number in the
    # English column (verified: Letter to Herodotus sections 37-42 carry no
    # digit anywhere in the English OCR text) -- a gap must be recorded, not
    # silently merged away or guessed at.
    lines = [
        "35 For those who are unable to study in detail",
        "43. And the atoms move continuously for all time",
    ]
    out, skipped, unassigned = m._extract_letter(lines, 35, 83)
    assert set(out) == {"35", "43"}
    assert skipped == list(range(36, 43))


def test_decimal_anchor_does_not_split_on_bare_page_number():
    # A lone page-bottom marker ("37") must never be mistaken for a real
    # section anchor -- `_clean_or_none` drops it before it ever reaches
    # `_extract_letter`.
    lines = ["35 For those who are unable to study in detail", "37", "more text here"]
    out, _, _ = m._extract_letter(lines, 35, 83)
    assert list(out) == ["35"]
    assert "more text here" in out["35"]


# --- Grok gate finding: a decimal anchor printed literally mid-word ---------

def test_decimal_anchor_mid_word_boundary_resolved_to_word_edge():
    # Regression: Letter to Pythocles 107/108 (raw OCR lines 3993-4010).
    # Bailey's own page break, and so this walk's own section-107/108
    # boundary, falls inside one word: "...a process most fre-" / "108
    # quent in the atmosphere...". Left at the anchor's own printed
    # position, 107 would end mid-word and 108 would open mid-word;
    # the fix moves the break to the nearest WORD edge instead.
    lines = [
        "107 for they produce hail by causing coagulation, a process most fre-",
        "108 quent in the atmosphere. Or else, owing to the friction of clouds.",
    ]
    out, skipped, unassigned = m._extract_letter(lines, 107, 116)
    assert out["107"].endswith("a process most fre- quent")
    assert out["108"] == "in the atmosphere. Or else, owing to the friction of clouds."
    assert skipped == []
    assert unassigned == []


def test_decimal_anchor_mid_word_fix_does_not_fire_without_a_hyphen():
    # The narrow gate (previous fragment must already end in a hyphen)
    # must never fire on an ordinary anchor whose own content happens to
    # open with a lowercase word -- Bailey's own edition regularly opens
    # a section mid-sentence (see test_decimal_anchor_accepts_exact_
    # continuity's sibling case), and that must be left completely alone.
    lines = [
        "35 For those who are unable to study in detail",
        "36 exposition. Indeed it is necessary to go back",
    ]
    out, skipped, unassigned = m._extract_letter(lines, 35, 83)
    assert out["35"] == "For those who are unable to study in detail"
    assert out["36"] == "exposition. Indeed it is necessary to go back"
    assert unassigned == []


def test_decimal_anchor_mid_word_fix_requires_lowercase_completion():
    # A capitalized word right after the anchor (a genuine new sentence,
    # not a broken-word completion) must not be pulled into the previous
    # section just because that section happened to end in a hyphen.
    lines = [
        "50 a long line that ends with a genuine compound hyphen-",
        "51 Word starts a fresh sentence here for testing purposes",
    ]
    out, skipped, unassigned = m._extract_letter(lines, 50, 83)
    assert out["50"].endswith("hyphen-")
    assert out["51"] == "Word starts a fresh sentence here for testing purposes"


# --- Finding 1(a): isolated Greek-script garble must not sink an English line

def test_isolated_greek_garble_word_does_not_drop_english_line():
    # Regression: letter-to-herodotus:35, raw L554-555 -- a single stray
    # Greek-script OCR garble word at the end of an otherwise-English line
    # ("...epitome of the whole διρθεπι") used to condemn the WHOLE line
    # under `_has_greek`, losing real prose. The garble token is stripped,
    # the rest of the line survives.
    lines = [
        "35 For those who are unable to work in detail",
        "prepared at sufficient length an epitome of the whole διρθεπι",
        "system, that they may keep adequately in παπα̂ at least",
    ]
    out, _, _ = m._extract_letter(lines, 35, 83)
    assert "epitome of the whole" in out["35"]
    assert "keep adequately in" in out["35"]
    assert "διρθεπι" not in out["35"]


def test_greek_heavy_apparatus_line_still_dropped_outright():
    # A line where MOST of the content is Greek/apparatus noise (more than
    # 2 Greek tokens, or over 30% of the line) must still be dropped
    # entirely, never stripped-and-kept: recovering isolated garble must
    # not turn into a general licence to admit apparatus criticus.
    lines = [
        "35 For those who are unable to work in detail",
        "XXXII I cep Usener : σεβαστοεν τ σεβαστὸς a ey",
        "36 more genuine translated prose continues right here",
    ]
    out, _, _ = m._extract_letter(lines, 35, 83)
    assert "cep Usener" not in out["35"]
    assert "ey" not in out["35"].split()


# --- Finding 1(d): hyphen-break continuation below the word-ratio bar --------

def test_hyphen_break_completion_recovered_despite_low_word_ratio():
    # Regression: letter-to-herodotus:36 ends mid-word "incom-" because the
    # true continuation line, "prehensible in number.", has only one
    # common-word hit in three words (0.33 ratio, under the 0.34 bar) and
    # is rejected by `_looks_english` on its own.
    lines = [
        "36 differences of shape are not quite infinite, but only incom-",
        "prehensible in number.",
    ]
    out, _, _ = m._extract_letter(lines, 35, 83)
    assert out["36"] == (
        "differences of shape are not quite infinite, but only incom- "
        "prehensible in number."
    )


def test_hyphen_break_does_not_swallow_unrelated_apparatus_fragment():
    # Regression: Vatican Saying 27's own hyphenated "pain-" is followed,
    # in physical OCR page order, by an apparatus-criticus line (an editor
    # surname) before the real continuation "fully after completion"
    # arrives. A blanket "anything after a hyphen" rule would swallow the
    # apparatus fragment too; `_hyphen_continues` requires the candidate
    # line's own first letter to be lower-case (a genuine broken-word
    # continuation), which "Hartel" is not.
    section = [_stub(n) for n in range(1, 27)] + [
        "XXVII. In all other occupations the fruit comes pain-",
        "Hartel . V",
        "fully after completion, but in philosophy pleasure goes",
    ]
    out, skipped, corrections, _, _ = m._extract_roman(section, 40, set())
    assert out["27"] == (
        "In all other occupations the fruit comes pain- fully after "
        "completion, but in philosophy pleasure goes"
    )
    assert "Hartel" not in out["27"]


# --- Finding 1(c): short terminal-punctuated closes to a hanging sentence ----

def test_single_word_terminal_line_completes_hanging_sentence():
    # Regression: Vatican Saying 81's own text ends "...causes of" with no
    # terminal punctuation, and the actual close, "unlimited desire.", is a
    # single-word (+ period) line that `_looks_english` always rejects
    # (fewer than 2 words). Accepted here because the buffer is mid-
    # sentence and the line is a short terminal-punctuated close.
    lines = ([_stub(n) for n in range(1, 81)] + [
        "LXXXI. The disturbance of the soul cannot be ended nor true joy "
        "created by anything else that is associated with causes of",
        "unlimited desire.",
    ])
    out, skipped, _, _, _ = m._extract_roman(lines, 81, set())
    assert out["81"].endswith("unlimited desire.")


def test_short_terminal_line_not_accepted_when_previous_sentence_already_closed():
    # The sentence-close fallback must require the buffer to be genuinely
    # hanging: a short trailing line arriving right after a fragment that
    # ALREADY ended in terminal punctuation is not a completion and must
    # not be admitted just because it is short.
    lines = [_stub(n) for n in range(1, 3)] + [
        "III. A short doctrine that ends cleanly right here.",
        "Stray.",
    ]
    out, _, _, _, _ = m._extract_roman(lines, 40, set())
    assert out["3"] == "A short doctrine that ends cleanly right here."
    assert "Stray" not in out["3"]


# --- Finding 2(a): bracketed roman-numeral anchors ---------------------------

def test_bracketed_roman_numeral_anchor_is_recovered_with_brackets_kept():
    # Regression: Vatican Saying 10, raw L5842-5845 -- printed inside
    # Bailey's own square brackets to mark disputed authenticity. The
    # leading "[" before the numeral broke the anchor match entirely, so
    # Saying 10's text bled into whichever entry was still open (Saying
    # 9). The opening bracket is restored onto the saying's own text
    # (Bailey's brackets are editorially meaningful, not noise); the
    # closing bracket is already ordinary body text.
    lines = [_stub(n) for n in range(1, 9)] + [
        "IX. Necessity is an evil, but there is no necessity to live under it.",
        "[X. Remember that you are of mortal nature and have",
        "a limited time to live and have seen things that have been.]",
        "XI. For most men rest is stagnation and activity madness.",
    ]
    out, skipped, _, _, _ = m._extract_roman(lines, 81, set())
    assert out["10"].startswith("[Remember that you are of mortal nature")
    assert out["10"].endswith("that have been.]")
    assert "Remember" not in out["9"]
    assert skipped == []


def test_bracket_with_interior_space_before_numeral_is_recovered():
    # Vatican Saying 36's own bracket has a space between "[" and the
    # numeral ("[ XXXVI. Epicurus’ life...").
    lines = [_stub(n) for n in range(1, 36)] + [
        "[ XXXVI. Epicurus own life when compared to other men is a mere legend. }",
    ]
    out, _, _, _, _ = m._extract_roman(lines, 40, set())
    assert out["36"].startswith("[Epicurus own life")


# --- Finding 2(b) / (e): a lost anchor must not bleed into the PREVIOUS entry

def test_leading_a_confusable_for_dropped_leading_x():
    # Regression: Vatican Sayings 18, 31, 34 all show a leading "X" in a
    # multi-X roman numeral misreading as "A" ("AVIII" for "XVIII", "AXXI"
    # for "XXXI", "AXXIV" for "XXXIV"). Left unrecognised, the saying's
    # text bled into the previous entry instead of landing on its own key.
    lines = [_stub(n) for n in range(1, 17)] + [
        "XVII. It is not the young man who should be thought happy indeed",
        "AVIII. Remove sight, association and contact, and the passion ends",
        "XIX. Forgetting the good that has been he has become old this day",
    ]
    out, skipped, _, _, _ = m._extract_roman(lines, 81, set())
    assert out["18"] == "Remove sight, association and contact, and the passion ends"
    assert "Remove sight" not in out["17"]
    assert skipped == []


def test_dropped_trailing_i_recovers_saying_without_bleeding_into_neighbour():
    # Regression: Vatican Saying 23's own numeral prints as "XXII." (an
    # exact reading for a DIFFERENT, already-consumed saying, 22, which is
    # itself cross-reference-only) rather than "XXIII." -- a genuine
    # dropped trailing "I". Left unrecovered, Saying 23's text bled into
    # Saying 21's buffer instead of landing on its own key.
    lines = [_stub(n) for n in range(1, 21)] + [
        "XXI. We must not violate nature dear friend but obey her fully now",
        "XXII. All friendship is desirable in itself though it starts from need",
    ]
    out, skipped, corrections, _, _ = m._extract_roman(lines, 81, {22})
    assert out["21"] == (
        "We must not violate nature dear friend but obey her fully now"
    )
    assert out["23"] == (
        "All friendship is desirable in itself though it starts from need"
    )
    assert "friendship" not in out["21"]
    assert any("23" in c for c in corrections)


def test_dropped_trailing_double_i_recovered():
    # Regression: Vatican Saying 48's own numeral, "XLVIII", misreads as
    # "XLVI" (two trailing strokes gone, not one) -- distinct from the
    # single-dropped-I case above.
    lines = [_stub(n) for n in range(1, 47)] + [
        "XLVII. I have anticipated thee Fortune and entrenched myself well",
        "XLVI. We must try to make the end of the journey better than start",
    ]
    out, skipped, corrections, _, _ = m._extract_roman(lines, 81, set())
    assert out["48"] == (
        "We must try to make the end of the journey better than start"
    )
    assert skipped == []
    assert any("48" in c for c in corrections)


def test_exact_match_at_a_later_position_wins_over_fuzzy_match_at_an_earlier_one():
    # Regression: Vatican Saying 58's own numeral, "LVIII.", parses
    # EXACTLY for 58, but also satisfies the doubled-letter-removed repair
    # for 57 (an earlier, unrecovered position). A first-hit-wins forward
    # search misfiled Saying 58's text under key "57"; the exact match
    # anywhere in the window must be preferred over any fuzzy match.
    lines = [_stub(n) for n in range(1, 56)] + [
        "LVIII. We must release ourselves from the prison of affairs today",
    ]
    out, skipped, corrections, _, _ = m._extract_roman(lines, 81, set())
    assert out["58"] == "We must release ourselves from the prison of affairs today"
    assert "57" not in out


# --- Finding 2(c): the Vatican crossref scan must recognise Greek-mixed numerals

def test_crossref_scan_recovers_greek_mixed_damaged_numeral():
    # Regression: Vatican Saying 72's own crossref line mixes Greek-script
    # numeral lookalikes with a digit and a merged-doubled-I accent glyph
    # in the SAME token ("1ΧΧῚ]. = Κύριαι Δόξαι XIII"). The primary
    # ASCII-only crossref regex cannot match it at all; without the
    # fallback, Saying 72 was never in `known_skips`, and the next real
    # anchor (Saying 73's own numeral, "LXXIII.") was fuzzily misread as a
    # damaged "LXXII", misfiling 73's text under key "72".
    raw_lines = ["1ΧΧῚ]. = Κύριαι Δόξαι XIII"]
    crossrefs = m._scan_vs_crossrefs(raw_lines)
    assert crossrefs == {72: raw_lines[0]}


def test_crossref_scan_still_reads_ordinary_ascii_numerals_unchanged():
    raw_lines = ["VI. = Κύριαε Δόξαι XXXV."]
    assert m._scan_vs_crossrefs(raw_lines) == {6: raw_lines[0]}


def test_saying_73_lands_on_its_own_key_once_72_is_recognised_as_crossref():
    lines = [_stub(n) for n in range(1, 72)] + [
        "LXXIII. The occurrence of certain bodily pains assists us today",
    ]
    known_skips = {72}
    out, skipped, _, _, _ = m._extract_roman(lines, 81, known_skips)
    assert out["73"] == "The occurrence of certain bodily pains assists us today"
    assert "72" not in out
    assert skipped == []


# --- Finding 3: the merge cap is a hard invariant, cut at a sentence boundary

def test_merge_cap_never_exceeded_and_cuts_at_a_sentence_boundary():
    # Regression: the old cap check ran BEFORE appending a line, so a
    # merged run could still end up past 6,000 characters, mid-sentence.
    # A run of many short complete sentences, well past the cap, must be
    # cut back to the last full sentence at or before the cap -- never
    # mid-word -- with the remainder recorded as unassigned overflow, not
    # silently dropped or silently kept past the cap.
    sentence = "This is one short complete sentence about atoms and void. "
    long_run = sentence * 200  # well over 6,000 characters
    lines = ["35 " + long_run.strip()]
    out, skipped, unassigned = m._extract_letter(lines, 35, 83)
    assert len(out["35"]) <= m._MAX_MERGE_CHARS
    assert out["35"].endswith("void.")
    assert unassigned
    assert unassigned[0]["after_section"] == 35
    # nothing was fabricated: kept + overflow reconstitutes the run exactly
    assert (out["35"] + " " + unassigned[0]["text"]).strip() == long_run.strip()


def test_merge_cap_boundary_exact_length_untouched():
    text_at_cap = ("word " * (m._MAX_MERGE_CHARS // 5 - 2)).strip() + "."
    assert len(text_at_cap) <= m._MAX_MERGE_CHARS
    kept, overflow = m._cut_at_sentence_boundary(text_at_cap, m._MAX_MERGE_CHARS)
    assert kept == text_at_cap
    assert overflow == ""


def test_cut_at_sentence_boundary_never_invents_a_boundary():
    # A run with NO sentence-ending punctuation at all within the cap
    # becomes wholly unassigned rather than truncated at an arbitrary
    # character count.
    text = "word " * 2000  # no periods anywhere
    kept, overflow = m._cut_at_sentence_boundary(text, 100)
    assert kept == ""
    assert overflow == text


# --- Finding 5: an inline compound "N-M." anchor spans two numbers at once ---

def test_inline_compound_range_anchor_creates_its_own_key():
    # Regression: Vatican Collection 56-57 is printed under a single
    # inline "LVI-LVII." anchor (Bailey's own edition has no separate 56
    # or 57). The old single-anchor-only matcher couldn't recognise it at
    # all, so its text bled into Saying 55, and the next real anchor
    # (Saying 58's own "LVIII.") got fuzzily misread as a damaged Saying
    # 57 by the doubled-letter repair.
    lines = [_stub(n) for n in range(1, 55)] + [
        "LV. We must heal our misfortunes by the grateful recollection today",
        "LVI-LVII. The wise man is not more pained when being tortured himself",
        "than when seeing his friend tortured and his life is upset indeed.",
        "LVIII. We must release ourselves from the prison of affairs today",
    ]
    out, skipped, corrections, compounds, _ = m._extract_roman(lines, 81, set())
    assert out["55"] == "We must heal our misfortunes by the grateful recollection today"
    assert out["56-57"] == (
        "The wise man is not more pained when being tortured himself "
        "than when seeing his friend tortured and his life is upset indeed."
    )
    assert out["58"] == "We must release ourselves from the prison of affairs today"
    assert "57" not in out
    assert "56" not in out
    assert compounds == [{"key": "56-57", "covers": [56, 57]}]
    assert skipped == []


# --- Finding 4: trailing sections after the last matched anchor are gaps too

def test_compute_gaps_itemizes_trailing_run_after_last_anchor():
    # Regression: a walk that never resumes after its last anchor (no
    # LATER anchor ever appears to reveal, via a jump, that a stretch was
    # skipped) previously produced NO gap record at all for that trailing
    # run -- Herodotus 58-83, Pythocles 115-116, Menoeceus 124-135 all
    # vanished from `meta.json` this way even though none of them were
    # ever extracted.
    out = {"35": "...", "36": "...", "40": "..."}
    gaps = m._compute_gaps(35, 45, out)
    assert gaps == [37, 38, 39, 41, 42, 43, 44, 45]


def test_compute_gaps_excludes_crossref_and_compound_covered_numbers():
    out = {"1": "...", "56-57": "..."}
    gaps = m._compute_gaps(1, 6, out, compound_covers={56, 57}, exclude={2})
    assert gaps == [3, 4, 5, 6]


# --- roman-numeral anchors + homoglyph repair (KD, VS) -----------------------

def test_roman_anchor_exact_and_continuity():
    lines = ["I. The blessed and immortal nature knows no trouble",
              "II. Death is nothing to us for that which is dissolved"]
    out, skipped, corrections, compounds, unassigned = m._extract_roman(lines, 40, set())
    assert out["1"] == "The blessed and immortal nature knows no trouble"
    assert out["2"] == "Death is nothing to us for that which is dissolved"
    assert skipped == []
    assert corrections == []
    assert compounds == []
    assert unassigned == []


def test_roman_homoglyph_dropped_capital_i():
    # Attested defect: a doubled capital I misreads with the second I as
    # lower-case "f" ("If." for "II.").
    lines = ["I. The blessed and immortal nature knows no trouble",
              "If. Death is nothing to us for that which is dissolved"]
    out, _, corrections, _, _ = m._extract_roman(lines, 40, set())
    assert out["2"] == "Death is nothing to us for that which is dissolved"
    assert any("2" in c for c in corrections)


def test_roman_homoglyph_digit_for_i_and_u_for_double_i():
    # "111," for "III." (digits standing in for I) and "XXVUI" for
    # "XXVIII" (U standing in for a doubled I).
    lines = [
        "I. first doctrine text here for testing purposes",
        "II. second doctrine text here for testing purposes",
        "111, third doctrine text here for testing purposes",
        "IV. fourth doctrine text here for testing purposes",
    ]
    out, skipped, _, _, _ = m._extract_roman(lines, 40, set())
    assert out["3"] == "third doctrine text here for testing purposes"
    assert skipped == []


def _stub(n: int) -> str:
    return f"{m._int_to_roman(n)}. This is the doctrine that we must know well"


_ROMAN_1_TO_9 = [_stub(n) for n in range(1, 10)]


def test_roman_spurious_doubled_letter_recovered_only_when_long_enough():
    # "XXXVI" for "XXVI" (doctrine 26): a spurious extra X. The recovery
    # path is gated on the normalized token being >=5 characters so it can
    # never fire on short numerals (see the X/XI collision test below).
    lines = ([_stub(n) for n in range(1, 26)]
             + ["XXXVI. twenty sixth doctrine text here for testing purposes"])
    out, skipped, corrections, _, _ = m._extract_roman(lines, 40, set())
    assert out["26"] == "twenty sixth doctrine text here for testing purposes"
    assert skipped == []
    assert any("26" in c for c in corrections)


def test_roman_anchor_never_misfiles_a_real_neighbour_as_a_missing_number():
    # Regression: an earlier fuzzy edit-distance matcher accepted "XI." as a
    # damaged reading of a missing "X." (edit distance 1), which would
    # silently misfile doctrine 11's text as doctrine 10 and cascade every
    # doctrine after it off by one. Doctrine 10 must be left an honest gap;
    # doctrine 11's own text must land on key "11", not "10".
    lines = _ROMAN_1_TO_9 + [
        "XI. eleventh doctrine text here for testing purposes indeed",
    ]
    out, skipped, _, _, _ = m._extract_roman(lines, 40, set())
    assert "10" not in out
    assert skipped == [10]
    assert out["11"] == "eleventh doctrine text here for testing purposes indeed"


def test_leading_greek_lookalike_numeral_is_repaired():
    # The OCR sets some roman numerals using visually identical Greek
    # capitals (Chi for Latin X) -- left alone this drops the whole line
    # under the Greek-script filter, losing real English content.
    lines = _ROMAN_1_TO_9 + [
        "Χ. tenth doctrine text here for testing purposes indeed",
    ]
    out, skipped, _, _, _ = m._extract_roman(lines, 40, set())
    assert out["10"] == "tenth doctrine text here for testing purposes indeed"
    assert skipped == []


# --- Grok gate finding: digit "1" glued onto is/in/it/if (no space) ----------

def test_digit_letter_homoglyph_fixes_all_four_short_words():
    text = (
        "but 1s enticed by it, all friendship 1s desirable 1n itself, "
        "for 1t is not the case, 1f we are really to have a standard"
    )
    fixed = m._fix_digit_letter_homoglyphs(text)
    assert fixed == (
        "but is enticed by it, all friendship is desirable in itself, "
        "for it is not the case, if we are really to have a standard"
    )


def test_digit_letter_homoglyph_leaves_legitimate_digits_alone():
    # Must never fire on a real number: an ordinal ("1st"), a year
    # ("1926"), a bare section/page numeral ("108"), or the digit "1"
    # standing alone as its own token.
    text = "In 1926, on the 1st of the month, section 108 reads: 1 is the count."
    assert m._fix_digit_letter_homoglyphs(text) == text


# --- Vatican Collection cross-reference-only sayings -------------------------

def test_vs_crossref_scan_finds_evidence_and_skip_extraction_respects_it():
    raw_lines = [
        "I. = Κύριαι Δόξαι I.",
        "II. = Κύριαι Δόξαι II.",
        "*III. Πᾶσα ἀλγηδὼν εὐκαταφρόνητος",
    ]
    crossrefs = m._scan_vs_crossrefs(raw_lines)
    assert crossrefs == {
        1: "I. = Κύριαι Δόξαι I.",
        2: "II. = Κύριαι Δόξαι II.",
    }
    english_lines = ["III. All bodily suffering is negligible for that pain"]
    out, skipped, _, _, _ = m._extract_roman(english_lines, 81, set(crossrefs))
    assert out["3"] == "All bodily suffering is negligible for that pain"
    assert skipped == []  # 1 and 2 are known skips, never reported as gaps


def test_vs_crossref_tolerates_attested_vowel_typo():
    # "Κύριαε" for "Κύριαι" (an attested OCR vowel slip on this exact word).
    raw_lines = ["VI. = Κύριαε Δόξαι XXXV."]
    assert m._scan_vs_crossrefs(raw_lines) == {6: "VI. = Κύριαε Δόξαι XXXV."}


# --- determinism (requires the real vendored source) -------------------------

_REPO_ROOT = _TOOLS.parent.parent
_SRC_FILE = _REPO_ROOT / "sources/bailey-epicurus/bailey-extant-remains-1926.djvu.txt"


@pytest.mark.skipif(not _SRC_FILE.exists(), reason="vendored OCR source not present")
def test_end_to_end_is_deterministic():
    tool = _TOOLS / "extract_bailey_epicurus.py"
    outputs = [
        "bailey-letters.clean.json", "bailey-kd.clean.json",
        "bailey-vs.clean.json", "meta.json",
    ]
    src_dir = _SRC_FILE.parent
    # The tool resolves its own SRC/OUT paths relative to "../sources/...",
    # so it must be invoked with cwd = pipeline/ (this module's parent), the
    # same convention every sibling extract_*.py tool uses.
    runs = []
    for _ in range(2):
        subprocess.run([sys.executable, str(tool)], cwd=str(_TOOLS.parent),
                        check=True, capture_output=True)
        runs.append({name: (src_dir / name).read_bytes() for name in outputs})
    assert runs[0] == runs[1]


@pytest.mark.skipif(not _SRC_FILE.exists(), reason="vendored OCR source not present")
def test_end_to_end_spot_checks_and_invariants():
    """Re-verifies, against the real vendored source, the previously-
    passing spot checks (letter-to-herodotus:35, KD IV, VS 4) plus the
    machine-verifiable success criteria for this fix: no store entry over
    6,000 characters, VS 73 carries its own text while 72 (a genuine
    cross-reference) does not steal it, VS 10 is present with its
    brackets kept, VS 81 ends "unlimited desire.", and every part's meta
    gaps covers the full expected range."""
    tool = _TOOLS / "extract_bailey_epicurus.py"
    subprocess.run([sys.executable, str(tool)], cwd=str(_TOOLS.parent),
                    check=True, capture_output=True)
    src_dir = _SRC_FILE.parent
    import json
    letters = json.loads((src_dir / "bailey-letters.clean.json").read_text(encoding="utf-8"))
    kd = json.loads((src_dir / "bailey-kd.clean.json").read_text(encoding="utf-8"))
    vs = json.loads((src_dir / "bailey-vs.clean.json").read_text(encoding="utf-8"))
    meta = json.loads((src_dir / "meta.json").read_text(encoding="utf-8"))

    assert "who are unable" in letters["letter-to-herodotus:35"]
    assert kd["4"].startswith("Pain does not last continuously")
    assert vs["4"].startswith("All bodily suffering is negligible")

    for store in (letters, kd, vs):
        for key, text in store.items():
            assert len(text) <= m._MAX_MERGE_CHARS, key

    assert "72" not in vs
    assert vs["73"].startswith("The occurrence of certain bodily pains")
    assert vs["10"].startswith("[")
    assert vs["81"].endswith("unlimited desire.")

    # Grok gate, 2026-07-29: the 107/108 mid-word boundary is resolved --
    # neither entry ends nor opens mid-word.
    assert letters["letter-to-pythocles:107"].endswith("frequent")
    assert letters["letter-to-pythocles:108"].startswith("in the atmosphere")

    # Grok gate, 2026-07-29: a full re-sweep of the regenerated stores for
    # the digit/letter homoglyph pattern must return zero hits (legitimate
    # digits -- ordinals, years, section numerals -- are never matched by
    # `_DIGIT_LETTER_HOMOGLYPH` in the first place, so this is a genuine
    # zero, not an excluded count).
    for store in (letters, kd, vs):
        for key, text in store.items():
            assert not m._DIGIT_LETTER_HOMOGLYPH.search(text), (key, text)

    # Every hand-verified PATCHES.json entry applied cleanly.
    assert meta["patches_applied"] == 9

    for slug, part_meta in meta["letters"].items():
        lo, hi = part_meta["expected_range"]
        gap_numbers = {g["section"] for g in part_meta["gaps"]}
        covered = {int(k.split(":")[1]) for k in letters if k.startswith(slug + ":")}
        assert covered | gap_numbers == set(range(lo, hi + 1))
