"""Helpers of pipeline/tools/verify_dash_citations.py, on invented text only
(no TLG/PHI content: the Greek below is made-up word salad)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline" / "tools"))

import verify_dash_citations as v  # noqa: E402

TEI_NS = "http://www.tei-c.org/ns/1.0"


# --- normalisation --------------------------------------------------------

def test_norm_greek_drops_accents_breathings_and_punctuation():
    assert v.norm_greek("Ἄλφος, βῆτος· γάμμας.") == "αλφοσβητοσγαμμασ"


def test_norm_greek_iota_subscript_meets_adscript():
    # TLG prints the subscript, DK the adscript: both become a plain iota.
    assert v.norm_greek("τῷ κάλῳ") == v.norm_greek("τῶι κάλωι") == "τωικαλωι"


def test_norm_greek_elision_mark_vanishes():
    assert v.norm_greek("δ' ἔλαφον") == v.norm_greek("δ᾽ ἔλαφον") == "δελαφον"


def test_norm_latin_merges_u_v_and_i_j():
    assert v.norm_latin("Iuvat vIVAM, jam!") == "iuuatuiuamiam"


def test_make_probes_overlap_and_short_text():
    probes = v.make_probes("abcdefghijklmnopqrstuvwxyz", length=10, step=8)
    assert probes == ["abcdefghij", "ijklmnopqr", "qrstuvwxyz"]
    assert v.make_probes("abcdefghi", length=20) == ["abcdefghi"]
    assert v.make_probes("abc", length=20) == []


def test_word_probes_keep_long_distinct_words():
    assert v.word_probes("νέος εὐδαίμων μέν εὐδαίμων", "grc") == \
        ["ευδαιμων"]


# --- numbers and loci -----------------------------------------------------

def test_numerals():
    assert v.roman_to_int("XIV") == 14 and v.roman_to_int("IX") == 9
    assert v.roman_to_int("Q") is None
    assert v.greek_numeral("κβʹ") == 22
    assert v.greek_numeral("ιϛʹ") == 16


def test_same_value_allows_a_letter_suffix_on_one_side():
    assert v.same_value("48a", "48")[0]
    assert v.same_value("7c", "7c") == (True, "")
    assert not v.same_value("7c", "7d")[0]
    assert not v.same_value("49", "48")[0]


def test_letter_near_and_next_page():
    assert v.letter_near("b", "C") and not v.letter_near("a", "c")
    assert v.next_page("409a") == "409b"
    assert v.next_page("409b") == "410a"
    assert v.next_page("155") == "156"


def test_match_locus_levels_line_tolerance_and_page_run_on():
    stob = v.Locus([("book", "3"), ("chapter", "12"), ("section", "13")],
                   ["001"])
    path = (("Book", "3"), ("chapter", "12"), ("section", "13"),
            ("line", "4"))
    assert v.match_locus("001", path, stob)[0]
    assert not v.match_locus("002", path, stob)[0]
    assert not v.match_locus(
        "001", (("Book", "3"), ("chapter", "13"), ("section", "13")), stob)[0]
    cag = v.Locus([("page", "155"), ("line", "30")], ["004"], fine="line")
    assert v.match_locus("004", (("page", "155"), ("line", "32")), cag)[0]
    assert not v.match_locus("004", (("page", "155"), ("line", "34")), cag)[0]
    ok, note, adjacent = v.match_locus("004", (("page", "156"), ("line", "1")), cag)
    assert ok and "runs on" in note and adjacent


def test_match_locus_adjacent_flag_defect4(tmp_path):
    # Defect 4: the +/- adjacency allowance still matches, but a caller must
    # be able to tell an exact hit from one that only matched nearby.
    cag = v.Locus([("page", "155"), ("line", "30")], ["004"], fine="line")
    ok, _, adjacent = v.match_locus("004", (("page", "155"), ("line", "30")), cag)
    assert ok and not adjacent  # exact line -- not adjacent
    ok, _, adjacent = v.match_locus("004", (("page", "155"), ("line", "31")), cag)
    assert ok and adjacent  # within LINE_TOL but not exact
    stephanus = v.Locus([("page", "447"), ("section", "c")], ["023"], fine="letter")
    ok, _, adjacent = v.match_locus("023", (("page", "447"), ("section", "c")), stephanus)
    assert ok and not adjacent  # exact letter -- not adjacent
    ok, _, adjacent = v.match_locus("023", (("page", "447"), ("section", "b")), stephanus)
    assert ok and adjacent  # neighbouring letter


# --- reading parsers ------------------------------------------------------

def test_parse_stobaeus_forms():
    [a, b] = v.p_stobaeus("STOB. III 29, 63. 83a")
    assert a.levels == [("book", "3"), ("chapter", "29"), ("section", "63")]
    assert b.levels[-1] == ("section", "83a")
    [c] = v.p_stobaeus("STOB. II 31, 39 p. 208, 13")
    assert c.levels == [("book", "2"), ("chapter", "31"), ("section", "39")]
    [d] = v.p_stobaeus("STOB. Flor. I 176")  # Meineke chapter I = W-H III 1
    assert d.levels == [("book", "3"), ("chapter", "1"), ("section", "176")]
    # DK's own printed forms, as the citation stage keeps them.
    [e] = v.p_stobaeus("STOB. II (Ecl. eth.) 7, 3i")
    assert e.levels == [("book", "2"), ("chapter", "7"), ("section", "3i")]
    [f] = v.p_stobaeus("STOB. Flor. III t. 1, 27 Hense")  # Hense's vol. III, title 1
    assert f.levels == [("book", "3"), ("chapter", "1"), ("section", "27")]


def test_parse_other_schemes():
    [a] = v.p_aristotle("ARISTOT. de anima Α 2. 404b 1")
    assert a.levels == [("bekker-page", "404b"), ("line", "1")]
    locs = v.p_plutarch("PLUT. Quaest. conv. I 1, 5 p. 614D E")
    assert [lc.levels[-1][1] for lc in locs] == ["D", "E"]
    [c] = v.p_clement("CLEM. Strom. V 105 (II 396, 10)")
    assert c.levels == [("book", "5"), ("section", "105")] and c.works == ["004"]
    [p] = v.p_plato("PLATO Gorg. 447 C")
    assert p.works == ["023"] and p.levels[-1] == ("section", "c")


def test_mismatch_needs_more_than_a_confirmation():
    assert v.needed(2) == 1 and v.needed(10) == 2
    assert v.mismatch_needed(10) == 3 and v.mismatch_needed(80) == 5


# --- passages and the search, end to end on a made-up text ----------------

def test_passage_for_stops_at_next_head_and_next_locus():
    seg = "—3, 1 ἄλφα βῆτα. 4, 2 γάμμα δέλτα. —5, 1 ἔψιλον"
    heads = ["—3, 1", "—5, 1"]
    assert v.passage_for(seg, "—3, 1", heads).strip() == "ἄλφα βῆτα."
    assert v.passage_for(seg, "—5, 1", heads).strip() == "ἔψιλον"


FAKE = f"""<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt>
<title>Florilegium fictum</title></titleStmt></fileDesc></teiHeader>
<text><body>
<div type="Book" n="1"><div type="chapter" n="1">
<div type="section" n="1"><l n="1">θαλασσία χελιδὼν ὑφαίνει νεφέλαις </l>
<l n="2">ῥοδίζουσι νότοις ἀλώπεκα.</l></div>
<div type="section" n="2"><l n="1">πορφύρεος κροκόεσσα χαλκόπτερος </l>
<l n="2">ῥοδοδάκτυλος κυανέοις πετάλοις σκιάζει.</l></div>
</div></div></body></text></TEI>"""


def _index(tmp_path):
    f = tmp_path / "tlg9999001.xml"
    f.write_text(FAKE, encoding="utf-8")
    return {"001": v.index_xml(f, "grc")}


def test_index_and_evaluate_confirm_and_mismatch(tmp_path):
    works = _index(tmp_path)
    passage = "πορφύρεος κροκόεσσα χαλκόπτερος ῥοδοδάκτυλος"
    probes = v.make_probes(v.norm_greek(passage))
    hits = v.find_hits(probes, works)
    right = v.Locus([("book", "1"), ("chapter", "1"), ("section", "2")],
                    ["001"])
    wrong = v.Locus([("book", "1"), ("chapter", "1"), ("section", "1")],
                    ["001"])
    res = v.evaluate([right], hits, probes, works, "9999")
    assert res["verdict"] == "CONFIRMED"
    res = v.evaluate([wrong], hits, probes, works, "9999")
    assert res["verdict"] == "MISMATCH" and "section 2" in res["found"]
    assert "near miss" in res["note"]
    other_probes = v.make_probes(v.norm_greek("μελανόπτερος ξανθὸς "
                                               "ἀκρωτήριον"))
    none = v.find_hits(other_probes, works)
    assert v.evaluate([right], none, other_probes, works, "9999")["verdict"] == \
        "NOT-FOUND"


def _fake_index(work: str, title: str = "Fake Text") -> v.WorkIndex:
    return v.WorkIndex(work=work, title=title, letters="", starts=[0], paths=[()])


def test_evaluate_confirmed_partial_when_locus_checked_is_set():
    # Defect 4: a Locus that names which levels the source's own text lets
    # you check (e.g. Aëtius book+chapter, never section) confirms as
    # CONFIRMED-PARTIAL, with `checked` naming those levels -- never a plain
    # CONFIRMED, even with plenty of matching (full-length) probes.
    works = {"003": _fake_index("003", "Placita philosophorum")}
    lc = v.Locus([("aet-book", "1"), ("aet-chapter", "5")], ["003"],
                 label="I 5 (section 9 unchecked)",
                 checked=["aet-book", "aet-chapter"])
    probes = ["a" * v.PROBE_LEN, "b" * v.PROBE_LEN]  # two full-length probes
    hits = [v.Hit(0, "003", (("aet-book", "1"), ("aet-chapter", "5"))),
            v.Hit(1, "003", (("aet-book", "1"), ("aet-chapter", "5")))]
    res = v.evaluate([lc], hits, probes, works, "0094")
    assert res["verdict"] == "CONFIRMED-PARTIAL"
    assert res["checked"] == ["aet-book", "aet-chapter"]


def test_evaluate_weak_on_a_single_short_probe_confirmation():
    # A single probe shorter than PROBE_LEN (20) confirming is not enough
    # evidence for CONFIRMED -- it becomes WEAK, even though `needed()`
    # alone (which counts probes, not their length) would have allowed it.
    works = {"001": _fake_index("001")}
    lc = v.Locus([("book", "1")], ["001"])
    short_probe = "αβγδεφγηιαβγ"  # 12 letters -- shorter than PROBE_LEN
    hits = [v.Hit(0, "001", (("book", "1"),))]
    res = v.evaluate([lc], hits, [short_probe], works, "0001")
    assert res["verdict"] == "WEAK"
    # Two independent probes at the same (short) length is enough, though.
    hits2 = [v.Hit(0, "001", (("book", "1"),)), v.Hit(1, "001", (("book", "1"),))]
    res2 = v.evaluate([lc], hits2, [short_probe, short_probe], works, "0001")
    assert res2["verdict"] == "CONFIRMED"


def test_evaluate_confirmed_on_a_single_full_length_probe():
    # A single probe at the full PROBE_LEN is enough evidence on its own.
    works = {"001": _fake_index("001")}
    lc = v.Locus([("book", "1")], ["001"])
    long_probe = "a" * v.PROBE_LEN
    hits = [v.Hit(0, "001", (("book", "1"),))]
    res = v.evaluate([lc], hits, [long_probe], works, "0001")
    assert res["verdict"] == "CONFIRMED"


# --- overlapping probes (review item 9) -------------------------------------

def test_evaluate_overlapping_probes_are_one_piece_of_evidence():
    # Two probes that share letters are one stretch of the passage: they
    # must not reach the two-probe CONFIRMED threshold on their own.
    import string
    works = {"001": _fake_index("001")}
    lc = v.Locus([("book", "1")], ["001"])
    probes = v.make_probes(string.ascii_letters[:45])  # starts 0, 5, ... 25
    assert len(probes) == 6
    overlapping = [v.Hit(0, "001", (("book", "1"),)), v.Hit(1, "001", (("book", "1"),))]
    res = v.evaluate([lc], overlapping, probes, works, "0001")
    assert res["verdict"] == "WEAK"
    apart = [v.Hit(0, "001", (("book", "1"),)), v.Hit(4, "001", (("book", "1"),))]
    assert v.evaluate([lc], apart, probes, works, "0001")["verdict"] == "CONFIRMED"


# --- lexicon headwords (item 7) ---------------------------------------------

LEXICON = f"""<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt>
<title>Lexicon fictum</title></titleStmt></fileDesc></teiHeader>
<text><body><div type="Alphabetic-letter" n="alpha">
<div type="entry" n="1"><l n="1"><hi rend="letter-spacing">Ἀβάκλης:</hi> ὄνομα πλαστόν.</l></div>
<div type="entry" n="2"><l n="1">[<hi rend="letter-spacing">μελαίνης χελιδόνος πύργου</hi>· ὄργανόν τι.</l></div>
<div type="entry" n="3"><l n="1"><seg type="lemma" rend="bold">Ἄδρυφος</seg> (fr. 1)· φυτόν.</l></div>
</div></body></text></TEI>"""

LEXICON_PAGES = f"""<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt>
<title>Lexicon paginatum</title></titleStmt></fileDesc></teiHeader>
<text><body><div type="Page" n="1">
<l n="1">Αβρυλος: ὄνομα ξένον. τινὲς δὲ λέγουσι: οὐδέν. </l></div>
<div type="Page" n="2">
<l n="1">βρύον ἁλιπλάγκτου: ἕτερον. </l>
<l n="2" rend="indent(1)">Ἀγρύπνη: ἡ νύξ. </l>
</div></body></text></TEI>"""


def test_lexicon_lemmas_from_entries_and_from_indented_lines(tmp_path):
    f = tmp_path / "tlg9998001.xml"
    f.write_text(LEXICON, encoding="utf-8")
    assert [lemma for lemma, _ in v.extract_lemmas(f)] == \
        ["Ἀβάκλης", "μελαίνης χελιδόνος πύργου", "Ἄδρυφος"]
    g = tmp_path / "tlg9998002.xml"
    g.write_text(LEXICON_PAGES, encoding="utf-8")
    # Page 2 line 1 runs on from page 1; only the first line and indented
    # lines open an entry.
    got = v.extract_lemmas(g)
    assert [lemma for lemma, _ in got] == ["Αβρυλος", "Ἀγρύπνη"]
    assert got[1][1] == "Page 2, line 2"


def test_check_headword_verdicts(tmp_path):
    f = tmp_path / "tlg9998001.xml"
    f.write_text(LEXICON, encoding="utf-8")
    index = v.LemmaIndex({"001": v.extract_lemmas(f)}, "9998")
    # Accents, breathings and case do not matter.
    assert index.check("ἀβακλής")["verdict"] == "CONFIRMED"
    assert index.check("ΑΔΡΥΦΟΣ")["verdict"] == "CONFIRMED"
    # The headword opens a longer entry (or the other way round): WEAK.
    weak = index.check("μελαίνης χελιδόνος")
    assert weak["verdict"] == "WEAK" and weak["found"] == "9998.001: entry 2 (alpha)"
    assert index.check("ζαβλάκης")["verdict"] == "NOT-FOUND"


def test_lexicon_sources_are_checked_by_headword():
    for name, author in (("Harpocration", "1389"), ("Hesychius", "4085"),
                         ("Suda", "9010"), ("Etymologicum", "4097")):
        spec = v.SOURCES[name]
        assert spec.author == author and spec.lexicon, name
