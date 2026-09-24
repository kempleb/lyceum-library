"""Unit tests for dk_witness.split_witnesses.

Every fixture string below is REAL corpus apparatus text, copied verbatim
from the built dist JSON (a DK column's greek[] entries with role=='context',
space-joined the same way stage7_emit's wiring joins them before calling
split_witnesses) -- never invented Greek or Latin. dk_witness.py itself is
owner-verified against the whole corpus (see its module docstring); this
file pins the specific behaviors that verification exercised, as regression
tests, not a re-derivation of them.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import dk_witness


# Empedocles B17 (empedocles-fragments) -- the module docstring's own ground
# truth: four witnesses (Simplicius twice, Plutarch, Clement).
B17_TEXT = "SIMPL. Phys. 157, 25 ὁ δὲ Ἐ .... οὕτως ἐν τῶι πρώτωι τῶν Φυσικῶν παραδίδωσι ’δίπλ' ... ὁμοῖα’. 1. 2 SIMPL. Phys. 161, 14 τὰ εὐθὺς ἐν ἀρχῆι παρατεθέντα ‘τοτὲ ... εἶναι’. PLUT. Amat. 13 p. 756 D ἀλλ' ὅταν Ἐμπεδοκλέους ἀκούσηις λέγοντος, ὦ ἑταῖρε, ’καὶ ... τεθηπώς’, ταῦτ' οἴεσθαι χρὴ λέγεσθαι περὶ Ἔρωτος· οὐ γάρ ἐστιν ὁρατὸς ἀλλὰ δοξαστὸς ἡμῖν ὁ θεὸς ἐν τοῖς πάνυ παλαιοῖς. CLEM. Strom. V 15 [II 335, 22 St.] ὁ δὲ Ἐ. ἐν ταῖς ἀρχαῖς καὶ Φιλότητα συγκαταριθμεῖται συγκριτικήν τινα ἀγάπην νοῶν ’ἣν ... τεθηπώς’."

# Heraclitus B39 (heraclitus-fragments) -- a single real anchor ("DIOG."),
# so fewer than two witnesses -- must fail closed.
B39_TEXT = 'DIOG. I 88 .'

# Anaximander A20 (anaximander-testimonia) -- one real anchor ("PLIN.") plus
# two roman-numeral-lookalike tokens ("XXV.", "XXXI.", Thales'/Anaximander's
# own day-counts) that must NOT be mistaken for citation anchors.
A20_TEXT = 'PLIN. N. H. XVIII 213 occasum matutinum Vergiliarum Hesiodus .. tradidit fieri, cum aequinoctium autumni conficeretur, Thales XXV. die ab aequinoctio, Anaximander XXXI.'

# Protagoras B6 (protagoras-fragments) -- two real anchors, "CIC." among
# them: a roman-numeral-lookalike abbreviation that IS a genuine citation
# (Cicero), not a false positive to exclude.
B6_TEXT = 'CIC. Brut. 12, 46 scriptasque fuisse et paratas a Protagora rerum inlustrium disputationes, quae nunc communes appellantur loci. QUINTIL. III 1, 10 Abderites P., a quo decem milibus denariorum didicisse artem, quam edidit, [s. II 254, 21. 255, 12. 256, 11] dicitur. 1, 12 (84 A 10) horum primi communis locos tractasse dicuntur P., Gorgias, affectus Prodicus et Hippias et idem P. et Thrasymachus.'

# Heraclitus B12 (heraclitus-fragments) -- "ARIUS DID." -- "DID." (Arius
# Didymus) is the other evidenced roman-numeral-lookalike genuine anchor.
# Only one real anchor in this column, so it fails closed; used here only to
# confirm "DID." itself is recognized as an anchor.
B12_TEXT = 'ARIUS DID. ap. Eus. P. E. XV 20 (D. 471, 1) Ζήνων τὴν ψυχὴν λέγει αἰσθητικὴν , καθάπερ Ἡ.· βουλόμενος γὰρ ἐμφανίσαι, ὅτι αἱ ψυχαὶ ἀναθυμιώμεναι νοεραὶ ἀεὶ γίνονται, εἴκασεν αὐτὰς τοῖς ποταμοῖς λέγων οὕτως·'

# Democritus A21 (democritus-testimonia) -- four witnesses in one column,
# two of which land with no `source` key: CIC.'s witness is wholly Latin
# (no Greek boundary at all), and HORAT.'s witness is Latin prose running
# into Greek (2+ prose words on the label side) -- the two distinct
# fail-closed-per-witness paths the module docstring describes.
A21_TEXT = 'CIC. de orat. II 58, 235 atque illud primum quid sit ipse risus, quo pacto concitetur ... viderit Democritus. HORAT. Ep. II 1, 194 si foret in terris, rideret D. SOTION Stob. Flor. (III) 20, 53 τοῖς δὲ σοφοῖς ἀντὶ ὀργῆς Ἡρακλείτωι μὲν δάκρυα, Δημοκρίτωι δὲ γέλως ἐπήιει. IUVEN. 10, 33 perpetuo risu pulmonem agitare solebat D.; 47 tunc quoque materiam risus invenit ad omnis occursus hominum, cuius prudentia monstrat summos posse viros et magna exempla daturos vervecum in patria crassoque sub aëre nasci. SCHOL. z. d. St. Abderita nam fuit D., ubi stulti solent nasci.'

# Democritus B122 (democritus-fragments) -- two witnesses, each introduced
# by a CHAINED label ("ETYM. GEN." / "ANECD. BEKK. LEX. VI 374, 14"): every
# token in the chain is itself anchor-shaped, but the whole chain names ONE
# source, not one witness per token.
B122_TEXT = 'ETYM. GEN. ἀλαπάξαι: ἐκπορθῆσαι παρὰ τὴν λάπαθον τὴν βοτάνην ἥ ἐστι κενωτικὴ γαστρός. καὶ Δ. τοὺς βόθρους τοὺς παρὰ τῶν κυνηγετῶν γινομένους καλεῖ διὰ τὸ κεκενῶσθαι. ANECD. BEKK. LEX. VI 374, 14 ἀμέλει Δ. τοὺς βόθρους τοὺς πρὸς τῶν κυνηγῶν σκαπτομένους οἷς ὑπεράνω κόνις λεπτὴ ἐπιχεῖται καὶ φρύγανα ἐπιβάλλεται, ἵνα οἱ λαγωοὶ ἐμπίπτωσιν εἰς αὐτούς, φησὶ καλεῖσθαι.'


def test_b17_splits_into_exactly_the_four_known_witnesses():
    witnesses = dk_witness.split_witnesses(B17_TEXT)
    assert [w.get("source") for w in witnesses] == [
        "SIMPL. Phys. 157, 25",
        "1. 2 SIMPL. Phys. 161, 14",
        "PLUT. Amat. 13 p. 756 D",
        "CLEM. Strom. V 15 [II 335, 22 St.]",
    ]


def test_bare_marker_reattaches_to_the_following_citation_not_the_preceding_one():
    # DK's bare line-marker "1. 2" sits, in the raw text, right after the
    # first Simplicius quotation and right before the second -- it must
    # move onto the SECOND witness's own text, not trail the first's.
    witnesses = dk_witness.split_witnesses(B17_TEXT)
    assert not witnesses[0]["text"].rstrip().endswith("1. 2")
    assert witnesses[1]["source"] == "1. 2 SIMPL. Phys. 161, 14"


def test_fewer_than_two_anchors_returns_none():
    # A single real anchor ("DIOG.") -- fail closed, not a one-item list.
    assert dk_witness.split_witnesses(B39_TEXT) is None
    # No anchor at all.
    assert dk_witness.split_witnesses("οὐδὲν ἐνταῦθα") is None
    assert dk_witness.split_witnesses("") is None


def test_roman_numeral_lookalike_tokens_are_not_anchors_but_cic_and_did_are():
    # "XXV." and "XXXI." (Thales'/Anaximander's own day-counts, not
    # citations) must not inflate the anchor count -- only "PLIN." is real,
    # so this column has just one anchor and fails closed.
    starts = dk_witness._real_anchor_starts(A20_TEXT)
    assert len(starts) == 1
    assert A20_TEXT[starts[0]:].startswith("PLIN.")

    # "CIC." IS a genuine anchor despite being spelled entirely with roman-
    # numeral letters -- Protagoras B6 splits into its two real witnesses.
    witnesses = dk_witness.split_witnesses(B6_TEXT)
    assert witnesses is not None
    assert witnesses[0]["text"].startswith("CIC. Brut. 12, 46")
    assert witnesses[1]["text"].startswith("QUINTIL. III 1, 10")

    # "DID." (Arius Didymus) is the other evidenced exception -- recognized
    # as an anchor even though this column's single occurrence still fails
    # closed (only one real anchor overall).
    did_starts = dk_witness._real_anchor_starts(B12_TEXT)
    assert len(did_starts) == 1
    assert B12_TEXT[did_starts[0]:].startswith("DID.")
    assert dk_witness.split_witnesses(B12_TEXT) is None


def test_chained_label_yields_one_witness_not_one_per_token():
    # "ETYM. GEN." and "ANECD. BEKK. LEX. VI 374, 14" are each a chain of
    # anchor-shaped tokens naming ONE source -- two witnesses total, not
    # five.
    witnesses = dk_witness.split_witnesses(B122_TEXT)
    assert [w["source"] for w in witnesses] == [
        "ETYM. GEN.",
        "ANECD. BEKK. LEX. VI 374, 14",
    ]


def test_wholly_latin_and_prose_heavy_label_both_come_back_with_no_source():
    witnesses = dk_witness.split_witnesses(A21_TEXT)
    assert len(witnesses) == 4
    # CIC.'s witness is wholly Latin -- no Greek boundary at all.
    assert "source" not in witnesses[0]
    assert witnesses[0]["text"].startswith("CIC. de orat.")
    assert not any(dk_witness._is_greek_letter(ch) for ch in witnesses[0]["text"])
    # HORAT.'s witness runs Latin prose ("si foret in terris, rideret")
    # before its Greek arrives -- 2+ prose words on the label side, so it
    # fails closed the same way, just for a different reason.
    assert "source" not in witnesses[1]
    assert witnesses[1]["text"].startswith("HORAT. Ep. II 1, 194")
    assert any(dk_witness._is_greek_letter(ch) for ch in witnesses[1]["text"])
