#!/usr/bin/env python3
# Generator for the DK source-citation expansion dictionary.
# Encodes philological decisions; emits citation-dictionary.json and coverage stats.
import json, sys, unicodedata
from collections import defaultdict
def nfc(s): return unicodedata.normalize("NFC", s)

import os
SELF_DIR = os.path.dirname(os.path.abspath(__file__))
CENSUS = json.load(open(os.path.join(SELF_DIR, "citation-heads-census.json")))["census"]

# ---------------------------------------------------------------------------
# Locus-template controlled vocabulary (documented in the memo).
#   bekker              Aristotle & CAG commentators on Bekker pages: "A 3. 984a 11"
#   stephanus           Plato: Stephanus page+col: "183 E" / "p. 76 C"
#   moralia             Plutarch Moralia: chapter + Stephanus page: "4 p. 1108 F"
#   vita                Biographies/Lives: chapter number: "16"
#   book-chapter-section Roman book . arabic chapter . arabic section: "I 7, 5"
#   book-para           Roman book + arabic paragraph/section: "II 6" / "VII 90"
#   book-page-col       Roman book + page-number + column letter: "V 220 B"
#   book-page           Roman book + editor page ("p."): "I p. 61"
#   page-line           editor page, line (+ editor name): "164, 22" / "65, 11 Friedl."
#   book-page-line      Roman book + page + line: "II 180 Sudh."
#   section             bare arabic section/fragment number: "11" / "59"
#   book-section        Roman book + arabic section (no page): "VIII 19"
#   chapter-page        chapter + editor page: "c. 251 p. 284, 10 Wrob."
#   opaque              varied/irregular locus; render verbatim as printed
# ---------------------------------------------------------------------------

# Suffix / apparatus conventions (orthogonal, documented in memo):
#   flag "diels-doxographi"  : "(D. NNN)" -> Diels, Doxographi Graeci p. NNN (kept in parens)
#   flag "editor-page-bracket": "[II 438, 9 St.]" etc. -> apparatus, preserved verbatim, unexpanded

def w(title, tmpl, notes=None, ital=True, locus_includes_work=False, **extra):
    # extra (2026-09-24): `column_letters` (a page may carry Stephanus-style
    # column letters though the template is opaque), `volume_by_part`
    # ([[part, first page, last page, volume], ...]: the stage prints the
    # volume before the locus), `locus_prefix` (printed before the locus: the
    # lexicon a head names only in its author slot).
    e = {"title": title, "title_italic": ital, "locus_template": tmpl}
    if notes: e["notes"] = notes
    if locus_includes_work: e["locus_includes_work"] = True
    e.update(extra)
    return e

# Shorthand Aristotle works (shared by ARISTOT / ARIST / [ARISTOT] via reference)
ARIST_WORKS = {
    "DEFAULT": w("(unspecified Aristotelian work)", "bekker", "Bare ARISTOT. + Bekker locus; work named in printed head where present.", ital=False),
    "Metaph.": w("Metaphysica", "bekker"),
    "Phys.": w("Physica", "bekker"),
    "Rhet.": w("Rhetorica", "bekker"),
    "de caelo": w("De Caelo", "bekker"),
    "de gen. et corr.": w("De Generatione et Corruptione", "bekker"),
    "de anima": w("De Anima", "bekker"),
    "Meteorol.": w("Meteorologica", "bekker"),
    "de gen. anim.": w("De Generatione Animalium", "bekker"),
    "Poet.": w("Poetica", "bekker"),
    "Meteor.": w("Meteorologica", "bekker"),
    "Soph. el.": w("De Sophisticis Elenchis", "bekker"),
    "Eth. Nic.": w("Ethica Nicomachea", "bekker"),
    "de gen. animal.": w("De Generatione Animalium", "bekker"),
    "de gener. anim.": w("De Generatione Animalium", "bekker"),
    "de partt. anim.": w("De Partibus Animalium", "bekker"),
    "de resp.": w("De Respiratione", "bekker"),
    "de sens.": w("De Sensu", "bekker"),
    "de sensu": w("De Sensu", "bekker"),
    "Pol.": w("Politica", "bekker"),
    "Polit.": w("Politica", "bekker", "R3 dash-continuation work-override token (census: '—Polit. A 13. 1260a 27')."),
    "Top.": w("Topica", "bekker"),
    "de gener. et corr.": w("De Generatione et Corruptione", "bekker"),
    "de part. anim.": w("De Partibus Animalium", "bekker"),
    "de partt. animal.": w("De Partibus Animalium", "bekker"),
    "de respir.": w("De Respiratione", "bekker"),
    "Metaphys.": w("Metaphysica", "bekker"),
    "de gener. et corr.": w("De Generatione et Corruptione", "bekker"),
    "Eth.": w("Ethica", "bekker"),
}

PLATO_WORKS = {
    "DEFAULT": w("(unspecified Platonic dialogue)", "stephanus", "Work named in head; Stephanus page follows.", ital=False),
    "Theaet.": w("Theaetetus", "stephanus"),
    "Meno": w("Meno", "stephanus"),
    "Apol.": w("Apologia", "stephanus"),
    "Cratyl.": w("Cratylus", "stephanus"),
    "Crat.": w("Cratylus", "stephanus"),
    "Phaedo": w("Phaedo", "stephanus"),
    "Phaedr.": w("Phaedrus", "stephanus"),
    "PHAEDR.": w("Phaedrus", "stephanus", "R3 dash-continuation work-override token (census: '—PHAEDR. 261 D')."),
    "Protag.": w("Protagoras", "stephanus"),
    "Prot.": w("Protagoras", "stephanus", "R3 dash-continuation work-override token (census: '—Prot. 333 D')."),
    "Soph.": w("Sophista", "stephanus"),
    "Sophist.": w("Sophista", "stephanus"),
    "Gorg.": w("Gorgias", "stephanus"),
    "Euthyd.": w("Euthydemus", "stephanus"),
    "Charm.": w("Charmides", "stephanus"),
    "Leg.": w("Leges", "stephanus"),
    "Parm.": w("Parmenides", "stephanus"),
    "Symp.": w("Symposium", "stephanus"),
    "Tim.": w("Timaeus", "stephanus"),
    "Hip": w("Hippias (Maior/Minor)", "stephanus", "Truncated census artifact; kept for census-key stability. Real printed tokens carry the full keys below."),
    "Hipp. maior": w("Hippias Maior", "stephanus", "Printed head 'PLATO Hipp. maior 289 A' (Heraclitus B82) — pilot gap fix 2026-07-24."),
    "Hipp. mai.": w("Hippias Maior", "stephanus"),
    "Hipp. minor": w("Hippias Minor", "stephanus"),
    "Hipp. min.": w("Hippias Minor", "stephanus"),
    "de rep.": w("Respublica", "stephanus"),
    # 2026-09-24 (content review): R3 dash titles DK prints that had no key.
    "Phileb.": w("Philebus", "stephanus", "Gorgias A26 '—Phileb. 58A'; Philebus, St. II 11A-67B."),
    "Lach.": w("Laches", "stephanus", "Prodicus A17 '—Lach. 197 B'; Laches, St. II 178A-201C."),
    "Charmid.": w("Charmides", "stephanus", "Prodicus A18 '—Charmid. 163 A B'; Charmides, St. II 153A-176D."),
    "Hipp min.": w("Hippias Minor", "stephanus",
                   "Hippias A10 '—Hipp min. 364c' (DK prints no period after 'Hipp'); Hippias Minor, St. I 363A-376C."),
}

PLUT_WORKS = {
    # Lives (vita template) and Moralia (moralia template). DEFAULT keeps work from head.
    "DEFAULT": w("(unspecified work of Plutarch)", "opaque", "Work named in printed head.", ital=False,
                 column_letters=True),
    "Quaest. conv.": w("Quaestiones Convivales", "moralia"),
    "Quaest. conviv.": w("Quaestiones Convivales", "moralia"),
    "Quaest. conv..": w("Quaestiones Convivales", "moralia"),
    "adv. Colot.": w("Adversus Colotem", "moralia"),
    "adv. Col.": w("Adversus Colotem", "moralia"),
    "Pericl.": w("Pericles", "vita"),
    "Quaest. nat.": w("Quaestiones Naturales", "moralia"),
    "de esu carn.": w("De Esu Carnium", "moralia"),
    "Cim.": w("Cimon", "vita"),
    "de Pyth. or.": w("De Pythiae Oraculis", "moralia"),
    "de curios.": w("De Curiositate", "moralia"),
    "de fac. in orb. lun.": w("De Facie in Orbe Lunae", "moralia"),
    "de fac. lun.": w("De Facie in Orbe Lunae", "moralia"),
    "de fort.": w("De Fortuna", "moralia"),
    "de prim. frig.": w("De Primo Frigido", "moralia"),
    "Alcib.": w("Alcibiades", "vita"),
    "Amat.": w("Amatorius", "moralia"),
    "Anton.": w("Antonius", "vita"),
    "Camill.": w("Camillus", "vita"),
    "Coriol.": w("Coriolanus", "vita"),
    "Lyc.": w("Lycurgus", "vita"),
    "Lys.": w("Lysander", "vita"),
    "Nic.": w("Nicias", "vita"),
    "Num.": w("Numa", "vita"),
    "Quaest. Platon.": w("Quaestiones Platonicae", "moralia"),
    "Quaest. phys.": w("Quaestiones Naturales", "moralia", "'Quaest. phys.' = Quaestiones Naturales."),
    "Sympos.": w("Quaestiones Convivales", "moralia", "'Sympos.' = Symposiaca / Quaestiones Convivales."),
    "c. princip. philos. esse diss.": w("Maxime cum principibus philosopho esse disserendum", "moralia", "Diels short title 'contra principem philosophum esse disserentem'; census locus (p. 777 c) falls in Stephanus 776A-779C, i.e. this work, not Ad Principem Ineruditum (779D-782F)."),
    "de amic. mult.": w("De Amicorum Multitudine", "moralia"),
    "de amic. multit.": w("De Amicorum Multitudine", "moralia"),
    "de coh. ira": w("De Cohibenda Ira", "moralia"),
    "de def. or.": w("De Defectu Oraculorum", "moralia"),
    "de defectu orac.": w("De Defectu Oraculorum", "moralia"),
    "de exil.": w("De Exilio", "moralia"),
    "de fac. in orbe lun.": w("De Facie in Orbe Lunae", "moralia"),
    "de garr.": w("De Garrulitate", "moralia"),
    "de puer. ed.": w("De Liberis Educandis", "moralia"),
    "de sanit.": w("De Tuenda Sanitate Praecepta", "moralia"),
    "de tranq. an.": w("De Tranquillitate Animi", "moralia"),
    "de tranqu. an.": w("De Tranquillitate Animi", "moralia"),
    "de virt. mor.": w("De Virtute Morali", "moralia"),
    "de vit. pud.": w("De Vitioso Pudore", "moralia"),
    # R3 dash-continuation work-override tokens (author inherited as Plutarch,
    # work is the explicit token per the memo's R3 rule) confirmed in the census.
    "de E": w("De E apud Delphos", "moralia"),
    "de superst.": w("De Superstitione", "moralia"),
    "de adul. et am.": w("De Adulatore et Amico", "moralia"),
    "de amore prol.": w("De Amore Prolis", "moralia"),
    "de aud.": w("De Recta Ratione Audiendi", "moralia"),
    "de audiendo": w("De Recta Ratione Audiendi", "moralia"),
    "de commun. not.": w("De Communibus Notitiis adversus Stoicos", "moralia"),
    "de commun. notit.": w("De Communibus Notitiis adversus Stoicos", "moralia"),
    "de lat. viv.": w("De Latenter Vivendo", "moralia"),
    "de mul. virt. p.": w("De Mulierum Virtutibus", "moralia"),
    "de music.": w("De Musica", "moralia"),
    "de prof. in virt.": w("De Profectibus in Virtute", "moralia"),
    "de sanit. praec.": w("De Tuenda Sanitate Praecepta", "moralia"),
    "de sollert. anim.": w("De Sollertia Animalium", "moralia"),
    # 2026-09-24 (content review): R3 dash titles DK prints that had no key.
    # Stephanus ranges and work numbers from the TLG Plutarch (0007) titles.
    "cons. ad Apoll.": w("Consolatio ad Apollonium", "moralia",
                         "Heraclitus B88 '—cons. ad Apoll. 10 p. 106 E'; Mor. 101F-122A (TLG "
                         "0007.076, which marks it spurious; DK does not bracket it, so it "
                         "stays under Plutarch as printed)."),
    "an seni resp.": w("An Seni Respublica Gerenda Sit", "moralia",
                       "Heraclitus B97 '—an seni resp. 7 p. 787C'; Mor. 783B-797F (TLG 0007.117)."),
    "fac. lun.": w("De Facie in Orbe Lunae", "moralia",
                   "Heraclitus B98 '—fac. lun. 28 p. 943 E' (DK drops the 'de'); Mor. "
                   "920B-945E (TLG 0007.126)."),
    "aqu. et ign. comp.": w("Aquane an Ignis Sit Utilior", "moralia",
                            "Heraclitus B99 '—aqu. et ign. comp. 7 p. 957 A'; Mor. 955D-958E "
                            "(TLG 0007.128, marked spurious there; DK does not bracket it). B99 "
                            "itself stays as printed pending John's print check "
                            "(dash-adjudications.json)."),
    "Qu. Plat.": w("Quaestiones Platonicae", "moralia",
                   "Heraclitus B100 '—Qu. Plat. 8, 4 p. 1007 D'; Mor. 999C-1011E (TLG 0007.133)."),
    "Reip. ger. praec.": w("Praecepta Gerendae Reipublicae", "moralia",
                           "Democritus B153 '—Reip. ger. praec. 28 p. 821 A'; Mor. 798A-825F "
                           "(TLG 0007.118)."),
    "de glor. Ath.": w("De Gloria Atheniensium", "moralia",
                       "Gorgias B23 '—de glor. Ath. 5 p. 348c'; Mor. 345C-351B (TLG 0007.088)."),
    "fragm. de libid. et aegr.": w("De Libidine et Aegritudine", "section",
                                   "Democritus B159 '—fragm. de libid. et aegr. 2': the fragment "
                                   "'Utrum animae an corporis sit libido et aegritudo' (Moralia fr., "
                                   "TLG 0007.143), cited by section."),
}

# ---------------------------------------------------------------------------
# CANON: normalized-key -> entry. `variants` MUST list the exact census strings.
# ---------------------------------------------------------------------------
CANON = {}

def add(key, canonical, variants, works, flags=None):
    CANON[key] = {
        "canonical_author": canonical,
        "variants": variants,
        "works": works,
        "flags": flags or [],
    }

# --- Doxographers / high-frequency ---
add("AET", "Aëtius", ["AËT.", "AËt."],
    {"DEFAULT": w("Placita", "book-chapter-section",
       "Bare AËT. + Roman-book locus = Placita (Diels' reconstruction from ps.-Plut. + Stobaeus). '(D. NNN)' = Diels, Doxographi Graeci page."),
     "de plac.": w("Placita", "book-chapter-section", "'de placitis' = Placita.")},
    flags=["diels-doxographi"])

add("DIOG_LAERT", "Diogenes Laertius", ["DIOG.", "Diog.", "DIOGENES LAERTIUS"],
    {"DEFAULT": w("Vitae Philosophorum", "book-para",
       "Bare DIOG. + Roman-book locus = Vitae Philosophorum (bk in Roman, chapter/section in arabic). Distinct from DIOGENES of Oinoanda (fragments).")},
    flags=[])

add("SIMPL", "Simplicius", ["SIMPL.", "SIMPLIC."],
    {"Phys.": w("in Aristotelis Physica", "page-line", "Diels CAG page,line; commentary title Latinized 'in Physica'."),
     "de caelo": w("in Aristotelis De Caelo", "page-line", "Heiberg CAG page,line."),
     "de cael.": w("in Aristotelis De Caelo", "page-line"),
     "de cael. p.": w("in Aristotelis De Caelo", "page-line"),
     "de caelo p.": w("in Aristotelis De Caelo", "page-line"),
     "DEFAULT": w("(commentary on Aristotle)", "page-line", ital=False)},
    flags=["title-is-commentary"])

add("CLEM", "Clement of Alexandria", ["CLEM."],
    {"Strom.": w("Stromata", "book-chapter-section", "Book (Roman) + chapter/section; '[II 438, 9 St.]' = Staehlin edition page/line (apparatus, preserved verbatim)."),
     "Str.": w("Stromata", "book-chapter-section"),
     "Protr.": w("Protrepticus", "section"),
     "Paed.": w("Paedagogus", "book-chapter-section"),
     "Paedag.": w("Paedagogus", "book-chapter-section"),
     "DEFAULT": w("Stromata", "book-chapter-section", "Bare CLEM. AL. in census is Stromata.")},
    flags=["editor-page-bracket"])

add("ATHEN", "Athenaeus", ["ATHEN."],
    {"DEFAULT": w("Deipnosophistae", "book-page-col", "Roman book + Casaubon page-number + column letter (e.g. 'V 220 B')."),
     "epit.": w("Deipnosophistae (Epitome)", "book-page-col")},
    flags=[])

add("STOB", "Stobaeus", ["STOB.", "STOBAEUS"],
    {"DEFAULT": w("Anthologium", "book-chapter-section",
       "Bare STOB. + Roman book = Anthologium (Eclogae bks I-II + Florilegium bks III-IV in Wachsmuth-Hense). '[vgl. ...]' = editorial cross-ref."),
     "Ecl.": w("Eclogae (Anthologii libri I-II)", "book-chapter-section", "Wachsmuth page in brackets."),
     "Flor.": w("Florilegium (Anthologii libri III-IV)", "book-chapter-section", "Hense.")},
    flags=[])

add("SEXT", "Sextus Empiricus", ["SEXT.", "SEXT. EMP.", "SEXTUS"],
    {"DEFAULT": w("Adversus Mathematicos", "book-para",
       "Bare SEXT. + Roman book = Adversus Mathematicos (books VII-XI = adv. dogmaticos). All census bare heads are book VII (unambiguous: Pyrrh. Hyp. has only 3 books). Pyrrhoneae Hypotyposes cited only with explicit 'Pyrrh. hyp.'."),
     "adv. math.": w("Adversus Mathematicos", "book-para")},
    flags=[])

add("CIC", "Cicero", ["CIC.", "CICERO"],
    {"DEFAULT": w("(work of Cicero)", "opaque", "Work named in head; loci are book+section, render as printed.", ital=False),
     "de orat.": w("De Oratore", "book-para"),
     "de fin.": w("De Finibus", "book-para"),
     "Ac.": w("Academica", "book-para"),
     "Acad.": w("Academica", "book-para"),
     "Tusc.": w("Tusculanae Disputationes", "book-para"),
     "de div.": w("De Divinatione", "book-para"),
     "de divin.": w("De Divinatione", "book-para"),
     # 2026-09-24: the former key "de div. i" swallowed the book numeral
     # (matching is case-folded, so it also took "de div. I 20, 39" and
     # printed "20, 39"); removed, the book stays in the locus.
     "Brut.": w("Brutus", "section"),
     "Cato": w("Cato Maior de Senectute", "section"),
     "Epist.": w("Epistulae ad Familiares", "opaque"),
     "Orat.": w("Orator", "section"),
     "de fato": w("De Fato", "book-para"),
     "de nat. deor.": w("De Natura Deorum", "book-para"),
     "de nat. d.": w("De Natura Deorum", "book-para",
                     "Anaximenes A10 '—de nat. d. I 10, 26' (after CIC. Acad.); Cic. N.D. 1.26."),
     "ad Qu.": w("Epistulae ad Quintum Fratrem", "opaque")},
    flags=[])

add("PROCL", "Proclus", ["PROCL."],
    {"in Eucl.": w("in Primum Euclidis Elementorum Librum", "page-line", "Friedlein page,line."),
     "in Eucl. p.": w("in Primum Euclidis Elementorum Librum", "page-line"),
     "in Tim. I": w("in Platonis Timaeum (vol. I)", "page-line", "Diehl vol/page,line."),
     "in Tim. II": w("in Platonis Timaeum (vol. II)", "page-line"),
     "in Tim. III": w("in Platonis Timaeum (vol. III)", "page-line"),
     "in Parm.": w("in Platonis Parmenidem", "page-line",
                   "Cousin col./page. 2026-09-24: replaces the key 'in Parm. I p.', which "
                   "swallowed the book I ('PROCL. in Parm. I p. 708, 16', Parmenides B5; "
                   "'—in Parm. I p. 665, 17', A18); the book now stays in the locus."),
     "in Parm. p.": w("in Platonis Parmenidem", "page-line"),
     "in Rep. II": w("in Platonis Rem Publicam (vol. II)", "page-line", "Kroll."),
     "in remp. II": w("in Platonis Rem Publicam (vol. II)", "page-line"),
     "in Alc. I p.": w("in Platonis Alcibiadem I", "page-line"),
     "in Crat.": w("in Platonis Cratylum", "page-line", "Pasquali section/page."),
     "ad Eucl.": w("in Primum Euclidis Elementorum Librum", "page-line"),
     "DEFAULT": w("(commentary of Proclus)", "page-line", ital=False)},
    flags=["title-is-commentary"])

add("HIPPOL", "Hippolytus", ["HIPPOL.", "HIPPOLYT.", "Hipp."],
    {"Ref.": w("Refutatio Omnium Haeresium", "book-chapter-section", "Also '(D. NNN, W. NNN)' = Diels DG / Wendland pages."),
     "Refut.": w("Refutatio Omnium Haeresium", "book-chapter-section"),
     "DEFAULT": w("Refutatio Omnium Haeresium", "book-chapter-section", "Bare HIPPOL. + '(D. ..., W. ...)' = Refutatio.")},
    flags=["diels-doxographi"])
# 2026-09-24: Democritus B32 prints a second source after Clement, "Hipp.
# Ref. VIII 14 (p. 234, 5 W.)" -- Hippolytus, Refutatio VIII 14 (Wendland's
# GCS page 234). "Hipp." is also Plato's Hippias (a dash-misparse token), so
# it names Hippolytus only when one of his titles follows it.
CANON["HIPPOL"]["variants_need_work"] = ["Hipp."]
# 'HIPP.' is shared between Hippolytus and Hippocrates; author is fixed by the work.
add("HIPP_SHARED", "Hippolytus / Hippocrates (shared abbrev.)", ["HIPP."],
    {"Ref.": w("Refutatio Omnium Haeresium", "book-chapter-section", "Author = Hippolytus."),
     "de nat. hom.": w("De Natura Hominis", "section", "Author = Hippocrates (Hippocratic corpus).")},
    flags=["ambiguous-abbrev", "author-varies-by-work"])

add("PHILOSTR", "Philostratus", ["PHILOSTR.", "PHILOSTRAT."],
    {"DEFAULT": w("(work of Philostratus)", "opaque", "'V. Apoll.' = Vita Apollonii (book + chapter + Kayser page,line).", ital=False),
     "Ep.": w("Epistulae", "opaque")},
    flags=[])

add("PORPHYR", "Porphyry", ["PORPHYR.", "PORPH."],
    {"DEFAULT": w("(work of Porphyry)", "opaque", "'V. Pyth.' = Vita Pythagorae (section).", ital=False),
     "de abst.": w("De Abstinentia", "book-para"),
     "de antro nymph.": w("De Antro Nympharum", "section"),
     "Quaest. hom.": w("Quaestiones Homericae", "page-line"),
     "zu": w("Quaestiones Homericae", "page-line",
             "'zu <Greek book-letter> <n> [...]' Homeric-Questions citation form "
             "(B102 'zu Δ 4 [...]', B103 'zu Ξ 200 [...]'); the Greek capitals are "
             "traditional Iliad book numerals (Δ=4, Ξ=14), not editorial Greek prose. "
             "The token-aligned matcher can't express 'zu' as a work marker that gets "
             "dropped from the locus (it's the only token identifying the work here, "
             "and it must stay in the printed locus too), so locus_includes_work keeps "
             "the whole matched span -- 'zu ...' -- verbatim as printed (pilot gap fix "
             "2026-07-24, Grok gate defect 1).",
             locus_includes_work=True),
     "in Ptolem. Harm. p.": w("in Ptolemaei Harmonica", "page-line"),
     "in Ptol.": w("in Ptolemaei Harmonica", "page-line"),
     "de Styge a": w("De Styge", "opaque", "'ap. Stob.' = apud Stobaeum; secondary transmission.")},
    flags=[])

add("GALEN", "Galen", ["GALEN.", "GAL."],
    {"DEFAULT": w("(work of Galen)", "opaque", "Loci give Kühn volume/page '[XII 248 K.]' and/or CMG/Helmreich; render as printed.", ital=False),
     "de elem.": w("De Elementis ex Hippocrate", "opaque"),
     "de meth. med.": w("De Methodo Medendi", "opaque"),
     "de plac. Hipp. et Plat.": w("De Placitis Hippocratis et Platonis", "opaque"),
     "de simpl. med.": w("De Simplicium Medicamentorum Temperamentis", "opaque"),
     "de simpl. medic.": w("De Simplicium Medicamentorum Temperamentis", "opaque"),
     "de virt. physic.": w("De Naturalibus Facultatibus", "opaque"),
     "de dign. puls.": w("De Dignoscendis Pulsibus", "opaque"),
     "in Epid. III": w("in Hippocratis Epidemiarum librum III", "opaque"),
     "in Epid. VI": w("in Hippocratis Epidemiarum librum VI", "opaque"),
     "ad Hippocr.": w("in Hippocratis (Epidemias)", "opaque"),
     "in Hipp. de hum.": w("in Hippocratis De Humoribus", "opaque"),
     "in Hipp. nat. hom.": w("in Hippocratis De Natura Hominis", "opaque"),
     "in Hip": w("in Hippocratis (opus)", "opaque", "Truncated head 'in Hipp. ...'; work completed from printed line.")},
    flags=[])

add("AEL", "Aelian", ["AEL.", "AELIAN."],
    {"DEFAULT": w("(work of Aelian)", "opaque", "'V. H.' = Varia Historia (book + chapter); 'N. H.'/'H. N.' = De Natura Animalium.", ital=False),
     "H. N.": w("De Natura Animalium", "book-section"),
     "N. H.": w("De Natura Animalium", "book-section"),
     "Nat. an": w("De Natura Animalium", "book-section"),
     "V. H.": w("Varia Historia", "book-section",
                "2026-09-24: 'AEL. V. H. VIII 19' (Anaxagoras A24) etc. = Varia Historia, "
                "book + chapter; before this key the DEFAULT printed 'V. H.' in the locus.")},
    flags=[])

# --- Lexicographers / reference (title = the work itself; bare heads) ---
add("SUID", "Suda", ["SUID.", "SUIDAS"],
    {"DEFAULT": w("Lexicon (Suda)", "opaque", "Cited by lemma (s.v.); no numeric locus in bare heads.")},
    flags=["cited-by-lemma"])
add("HARPOCR", "Harpocration", ["HARPOCR.", "HARPOCRAT."],
    {"DEFAULT": w("Lexicon in Decem Oratores", "opaque", "Cited by lemma (s.v.).")},
    flags=["cited-by-lemma"])
add("HESYCH", "Hesychius", ["HESYCH."],
    {"DEFAULT": w("Lexicon", "opaque", "Cited by lemma (s.v.).")}, flags=["cited-by-lemma"])
add("PHOT", "Photius", ["PHOT.", "PHOTIUS"],
    {"DEFAULT": w("Lexicon", "opaque", "Also Bibliotheca ('Bibl. cod. NNN') where the head names it.")},
    flags=["cited-by-lemma"])
# Herodian's works as DK names them (Grok content review item 6, 2026-09-24:
# the head stopped at the Greek title, so every one printed an empty locus).
# Titles: house convention (John's ruling (b), 2026-09-24) puts work titles
# in Latin, so Περὶ μονήρους λέξεως and Περὶ διχρόνων render as *De Dictione
# Singulari* and *De Dichronis* -- the TLG canon (TLG0087.IDT) gives no Latin
# title for either, but "De prosodia catholica" and "Schematismi Homerici"
# do carry one there and stay as the TLG gives them. John has since reopened
# Greek vs. Latin titles as an editorial question (see README); these two
# stay Latin until he rules. The locus is whatever DK prints after the
# title, as printed (`locus_as_printed`): a page and line, or a "bei
# <author> ..." note naming the text that preserves the passage, which the
# stage keeps as apparatus.
_HDN = dict(locus_as_printed=True)
add("HEROD_GRAMM", "Herodian (grammarian)", ["HERODIAN.", "HERODIAN"],
    {"DEFAULT": w("(grammatical work)", "opaque", "Aelius Herodianus, grammarian. Distinct from Herodotus (HERODOT.).", ital=False),
     "π. μον. λέξ.": w("De Dictione Singulari", "opaque",
                       "Xenophanes B37, B38; Critias B41 ('HEROD. π. μον. λέξ. p. 40, 14').", **_HDN),
     "π. μον. λέξεως": w("De Dictione Singulari", "opaque", "Xenophanes B42.", **_HDN),
     "π. διχρ.": w("De Dichronis", "opaque",
                   "Xenophanes B10, B36; Cramer, Anecdota Oxoniensia III.", **_HDN),
     "π. καθολ. προσ.": w("De Prosodia Catholica", "opaque",
                          "Democritus B127-128, preserved by Eustathius and Theognostus; "
                          "Lentz's volume, page and line in the bracket ('[I 355, 19 L.]').", **_HDN),
     "schematismi Hom.": w("Schematismi Homerici", "opaque",
                           "Empedocles B51, from the Darmstadt codex in Sturz's Etymologicum "
                           "Gudianum p. 745.", **_HDN)},
    flags=[])
# 2026-09-24: DK's "HEROD." is Herodotus in Pythagoras 1-2 ("HEROD. II 123",
# "—IV 95": Hdt. 2.123, 4.95), Thales A6/A16 (Hdt. 1.75, 2.20) and
# Anaxagoras A91 (Hdt. 2.22), but Herodian in Critias B41 ("HEROD. π. μον.
# λέξ. p. 40, 14", Herodian's Περὶ μονήρους λέξεως). It is therefore no
# author's variant; the stage decides from the evidence (meta
# `ambiguous_variants`) and keeps the head as printed when there is none.
AMBIGUOUS_VARIANTS = {
    "HEROD.": {
        "book-chapter": "HERODOT",   # a book numeral + chapter follows (Historiae)
        "greek-title": "HEROD_GRAMM",  # a Greek "π. ..." title follows (Herodian's works)
    },
}

# --- Aristotle (real) ---
add("ARISTOT", "Aristotle", ["ARISTOT.", "ARIST.", "ARISTOTELES"], dict(ARIST_WORKS), flags=[])

# --- Plato (real) ---
add("PLATO", "Plato", ["PLATO", "PLAT."], dict(PLATO_WORKS), flags=[])

# --- Plutarch (real) ---
add("PLUT", "Plutarch", ["PLUT.", "PLUTARCH", "PLUTARCH."], dict(PLUT_WORKS),
    flags=["lives-vs-moralia"])

# --- Theophrastus ---
add("THEOPHR", "Theophrastus", ["THEOPHR.", "THEOPHRAST."],
    {"DEFAULT": w("(work of Theophrastus)", "opaque", ital=False),
     "de sens.": w("De Sensibus", "section", "'(D. NNN)' = Diels DG page (Theophr. is a main doxographic source)."),
     "de sensu": w("De Sensibus", "section"),
     "de caus. pl.": w("De Causis Plantarum", "book-chapter-section"),
     "de caus. plant.": w("De Causis Plantarum", "book-chapter-section"),
     "d. c. pl.": w("De Causis Plantarum", "book-chapter-section",
                    "2026-09-24: Democritus A131 'THEOPHR. d. c. pl. VI 2, 3' = De causis "
                    "plantarum VI 2, 3 (as A129 'de caus. plant. VI 1, 6')."),
     "H. plant.": w("Historia Plantarum", "book-chapter-section"),
     "Metaphys.": w("Metaphysica", "opaque"),
     "de igne": w("De Igne", "section")},
    flags=["diels-doxographi"])

# --- Commentators & philosophers (CAG page-line) ---
add("ALEX", "Alexander of Aphrodisias", ["ALEX."],
    {"DEFAULT": w("(commentary of Alexander)", "page-line", ital=False),
     "Metaph.": w("in Aristotelis Metaphysica", "page-line"),
     "in Metaphys. A": w("in Aristotelis Metaphysica", "page-line"),
     "de mixt.": w("De Mixtione", "page-line", "Bruns Suppl. Arist."),
     "Quaest. II": w("Quaestiones (lib. II)", "page-line", "Bruns.")},
    flags=["title-is-commentary"])
add("PHILOP", "John Philoponus", ["PHILOP.", "PHILOPON."],
    {"DEFAULT": w("(commentary of Philoponus)", "page-line", ital=False),
     "de anima": w("in Aristotelis De Anima", "page-line", "Hayduck CAG."),
     "de anima p.": w("in Aristotelis De Anima", "page-line"),
     "de gen. et corr.": w("in Aristotelis De Generatione et Corruptione", "page-line", "Vitelli.")},
    flags=["title-is-commentary"])
add("THEMIST", "Themistius", ["THEMIST."],
    {"DEFAULT": w("(work of Themistius)", "opaque", "'Or.' = Orationes (oration + page).", ital=False),
     "Or.": w("Orationes", "opaque")},
    flags=[])
add("OLYMPIOD", "Olympiodorus", ["OLYMPIOD.", "OLYMP.", "OLYMPIODOR."],
    {"DEFAULT": w("(commentary of Olympiodorus)", "page-line", ital=False),
     "in Meteor.": w("in Aristotelis Meteora", "page-line"),
     "in Plat. Phileb.": w("in Platonis Philebum", "page-line"),
     "de arte sacra lapidis philosophorum c.": w("De Arte Sacra", "opaque")},
    flags=["title-is-commentary"])
add("AMMON", "Ammonius", ["AMMON."],
    {"de interpr.": w("in Aristotelis De Interpretatione", "page-line", "Busse CAG."),
     "de interpr. p.": w("in Aristotelis De Interpretatione", "page-line"),
     "DEFAULT": w("(commentary of Ammonius)", "page-line", ital=False)},
    flags=["title-is-commentary"])
add("EUDEM", "Eudemus of Rhodes", ["EUDEM."],
    {"Eth.": w("Ethica (Eudemia)", "bekker", "Eudemian Ethics traditionally transmitted in the Aristotelian corpus."),
     "Phys.": w("Physica (fragmenta)", "opaque", "Fr. numbers; witness usually Simplicius.")},
    flags=[])
add("DAVID", "David (Elias)", ["DAVID"],
    {"Prol.": w("Prolegomena Philosophiae", "page-line", "Busse CAG.")}, flags=[])

# --- Neoplatonists / misc philosophers ---
add("IAMBL", "Iamblichus", ["IAMBL.", "IAMBLICH.", "IAMBLICHUS"],
    {"DEFAULT": w("(work of Iamblichus)", "opaque", "'V. P.'/'V. Pyth.' = De Vita Pythagorica (section).", ital=False),
     "de myst.": w("De Mysteriis", "book-para"),
     "de anima": w("De Anima", "opaque",
                   "Heraclitus B70 '—de anima [Stob. Ecl. II 1, 16]' (after IAMBL. de myst.): "
                   "Iamblichus' De anima, preserved only in Stobaeus' Eclogae, which DK's "
                   "bracket locates."),
     "in Nicom. p.": w("in Nicomachi Arithmeticam", "page-line"),
     "in Nic. p.": w("in Nicomachi Arithmeticam", "page-line")},
    flags=[])
add("PLOTIN", "Plotinus", ["PLOTIN."],
    {"Enn.": w("Enneades", "book-chapter-section", "Ennead + treatise + chapter.")}, flags=[])
add("NUMEN", "Numenius", ["NUMEN."],
    {"DEFAULT": w("Fragmenta", "section", "Cited by fragment number + editor.", ital=False)}, flags=[])
add("PSELL", "Michael Psellus", ["PSELL."],
    {"DEFAULT": w("(work of Psellus)", "opaque", ital=False),
     "de lap.": w("De Lapidum Virtutibus", "section")},
    flags=[])
add("HIEROCL", "Hierocles", ["HIEROCL."],
    {"ad c.": w("in Aureum Carmen (Commentarius)", "opaque", "'ad c. aur.' = in Aurea Carmina Pythagorae.")},
    flags=[])
add("HERMIAS", "Hermias (Irrisio)", ["HERM.", "HERMIAS"],
    {"Irris.": w("Irrisio Gentilium Philosophorum", "section", "'(D. NNN)' = Diels DG page.")},
    flags=["diels-doxographi"])
add("SYNCELL", "George Syncellus", ["SYNCELL."],
    {"DEFAULT": w("Ecloga Chronographica", "opaque")}, flags=[])
add("HISDOSUS", "Hisdosus Scholasticus", ["HISDOSUS", "HISDOSUS Scholasticus"],
    {"DEFAULT": w("in Chalcidii Timaeum (glossa)", "opaque"),
     "ad Chalcid. Plat. Tim.": w("in Chalcidii Timaeum (glossa)", "opaque",
        "Full printed work-reference span (B67a); author variant extended to 'HISDOSUS "
        "Scholasticus' so this frame isn't left dangling at the front of the locus "
        "(pilot gap fix 2026-07-24, Grok gate defect 8).")},
    flags=["obscure"])
add("PSEUDORIB", "pseudo-Oribasius", ["PSEUDORIBASIUS"],
    {"DEFAULT": w("in Aphorismos Hippocratis", "opaque")}, flags=["obscure"])

# --- Christian / doxographic authors ---
add("EUSEB", "Eusebius", ["EUSEB.", "EUS."],
    {"DEFAULT": w("(work of Eusebius)", "opaque", "'P. E.' = Praeparatio Evangelica (book+chapter+section); 'Chron.' = Chronica.", ital=False),
     "Chron.": w("Chronica", "opaque")},
    flags=[])
add("CLEM_note", "Clement of Alexandria", [], {}, flags=[])  # placeholder removed below
del CANON["CLEM_note"]
add("EPIPHAN", "Epiphanius", ["EPIPHAN."],
    {"adv. haer.": w("Adversus Haereses (Panarion)", "book-chapter-section", "'(D. NNN)' = Diels DG page.")},
    flags=["diels-doxographi"])
add("THEODORET", "Theodoret", ["THEODORET."],
    {"DEFAULT": w("Graecarum Affectionum Curatio", "book-section", "'aus Aëtios (D. NNN)' = drawn from Aëtius, Diels DG page.")},
    flags=["diels-doxographi"])
add("TERTULL", "Tertullian", ["TERTULL.", "TERT."],
    {"DEFAULT": w("(work of Tertullian)", "opaque", ital=False),
     "Apolog.": w("Apologeticum", "section"),
     "Apologetic.": w("Apologeticum", "section"),
     "de anima": w("De Anima", "section"),
     "de anim.": w("De Anima", "section"),
     "de anima c.": w("De Anima", "section")},
    flags=[])
add("LACTANT", "Lactantius", ["LACTANT."],
    {"DEFAULT": w("Divinae Institutiones", "book-chapter-section", "'Inst. div.' = Divinae Institutiones.")},
    flags=[])
add("AUGUSTIN", "Augustine", ["AUGUSTIN."],
    {"DEFAULT": w("De Civitate Dei", "book-para", "'C. D.' = De Civitate Dei.")}, flags=[])
add("IRENAEUS", "Irenaeus", ["IRENAEUS"],
    {"DEFAULT": w("Adversus Haereses", "book-chapter-section", "'(D. NNN)' = Diels DG page.")},
    flags=["diels-doxographi"])
add("ATHANASIUS", "Athanasius (rhetor)", ["ATHANASIUS"],
    {"DEFAULT": w("(Prolegomena to Hermogenes)", "opaque", ital=False)}, flags=["obscure"])
add("ORIG", "Origen", ["ORIG."],
    {"c. Cels. IV": w("Contra Celsum (lib. IV)", "book-para"),
     "c. Cels. VI": w("Contra Celsum (lib. VI)", "book-para"),
     "c. Cels.": w("Contra Celsum", "book-para",
        "Bare 'c. Cels.' (no book number, e.g. B5 'ORIG. c. CELS. VII 62') -- matching it "
        "(case-insensitively, Grok gate defect 4) keeps it out of the locus."),
     "DEFAULT": w("Contra Celsum", "book-para", "'c. Cels.' = Contra Celsum.")},
    flags=[])
add("TATIAN", "Tatian", ["TATIAN."],
    {"DEFAULT": w("Oratio ad Graecos", "opaque")}, flags=[])
add("ATHENAG", "Athenagoras", ["ATHENAG."],
    {"DEFAULT": w("Legatio pro Christianis", "opaque")}, flags=[])
add("CYRILL", "Cyril of Alexandria", ["CYRILL."],
    {"c. Jul. I p.": w("Contra Iulianum (lib. I)", "opaque")}, flags=[])

# --- Latin authors ---
add("PLIN", "Pliny the Elder", ["PLIN.", "PLINIUS"],
    {"DEFAULT": w("Naturalis Historia", "book-para", "'N. H.'/'N. HIST.' = Naturalis Historia (book + section)."),
     "N. H.": w("Naturalis Historia", "book-para")},
    flags=[])
add("LUCRET", "Lucretius", ["LUCRET.", "LUCR."],
    {"DEFAULT": w("De Rerum Natura", "book-section", "Book + line.")}, flags=[])
add("SENECA", "Seneca", ["SENEC.", "SENECA", "SEN."],
    {"DEFAULT": w("(work of Seneca)", "opaque", "'Nat. quaest.'/'Nat. qu.' = Naturales Quaestiones; 'Ep./Epist.' = Epistulae Morales.", ital=False),
     "Controv.": w("Controversiae", "opaque", "This is Seneca the Elder."),
     "Ep.": w("Epistulae Morales", "section"),
     "Epist.": w("Epistulae Morales", "section")},
    flags=["elder-vs-younger"])
add("CENSOR", "Censorinus", ["CENSOR.", "CENSORIN."],
    {"DEFAULT": w("De Die Natali", "book-chapter-section", "Chapter + section; '(D. NNN)' = Diels DG page.")},
    flags=["diels-doxographi"])
add("COLUM", "Columella", ["COLUM.", "COLUMELLA"],
    {"DEFAULT": w("De Re Rustica", "book-chapter-section")}, flags=[])
add("VITRUV", "Vitruvius", ["VITRUV.", "VITR."],
    {"DEFAULT": w("De Architectura", "book-chapter-section")}, flags=[])
add("GELL", "Aulus Gellius", ["GELL.", "GELLIUS"],
    {"DEFAULT": w("Noctes Atticae", "book-chapter-section")}, flags=[])
add("VAL_MAX", "Valerius Maximus", ["VAL. MAX."],
    {"DEFAULT": w("Facta et Dicta Memorabilia", "book-chapter-section")}, flags=[])
add("MACROB", "Macrobius", ["MACROB."],
    {"DEFAULT": w("(work of Macrobius)", "opaque", "'S. Sc.'/'in S. Scip.' = Commentarii in Somnium Scipionis.", ital=False),
     "in S. Scip. I": w("Commentarii in Somnium Scipionis (lib. I)", "book-chapter-section")},
    flags=[])
add("AMMIAN", "Ammianus Marcellinus", ["AMMIAN.", "AMMIAN. MARCELL."],
    {"DEFAULT": w("Res Gestae", "book-chapter-section")}, flags=[])
# "APULEIUS" in full: Thales A19 (content review item 7).
add("APUL", "Apuleius", ["APUL.", "APULEIUS"],
    {"Florida": w("Florida", "section"),
     "Flor.": w("Florida", "section",
                "2026-09-24: Protagoras A4 'APUL. Flor. 18' = Apuleius, Florida 18 (the "
                "Protagoras-Euathlus story); A4 was fatal without this key.")},
    flags=[])
add("VARRO", "Varro", ["VARRO"],
    {"DEFAULT": w("(work of Varro)", "opaque", "'Sat.' = Saturae Menippeae.", ital=False)},
    flags=["obscure"])
add("QUINTIL", "Quintilian", ["QUINTIL.", "QUINT."],
    {"DEFAULT": w("Institutio Oratoria", "book-chapter-section", "'Inst.' = Institutio Oratoria."),
     "Inst.": w("Institutio Oratoria", "book-chapter-section")},
    flags=[])
add("PRISC", "Priscian", ["PRISC."],
    {"DEFAULT": w("Institutiones Grammaticae", "book-para")}, flags=[])
add("CHALCID", "Calcidius", ["CHALCID."],
    {"DEFAULT": w("in Platonis Timaeum", "chapter-page")}, flags=["title-is-commentary"])
add("ALBERT", "Albertus Magnus", ["ALBERT. Magn.", "ALBERTUS M.", "ALBERTUS MAGNUS"],
    {"DEFAULT": w("(work of Albertus Magnus)", "opaque", ital=False),
     "de lapid.": w("De Mineralibus", "book-chapter-section", "Jammy edition ref in brackets."),
     "de veget.": w("De Vegetabilibus", "book-para"),
     "Ethica": w("Ethica", "book-chapter-section")},
    flags=["medieval"])
add("MALL", "Mallius Theodorus", ["MALL.", "MALLIUS"],
    {"DEFAULT": w("De Metris", "book-page-line", "Keil Gramm. Lat.")}, flags=["obscure"])

# --- Historians / geographers ---
add("STRABO", "Strabo", ["STRABO", "STRAB."],
    {"DEFAULT": w("Geographica", "book-page", "Roman book + Casaubon page ('p.').")}, flags=[])
add("DIOD", "Diodorus Siculus", ["DIOD.", "DIODOR."],
    {"DEFAULT": w("Bibliotheca Historica", "book-chapter-section")}, flags=[])
add("HERODOT", "Herodotus", ["HERODOT."],
    {"DEFAULT": w("Historiae", "book-section", "Book + chapter. NB distinct from Herodian(us).")},
    flags=[])
add("POLYB", "Polybius", ["POLYB."],
    {"DEFAULT": w("Historiae", "book-section")}, flags=[])
add("PAUS", "Pausanias", ["PAUS."],
    {"DEFAULT": w("Graeciae Descriptio", "book-chapter-section")}, flags=[])
add("MARM_PAR", "Marmor Parium", ["MARM. PAR."],
    {"DEFAULT": w("Marmor Parium", "opaque", "Epoch number; FGrHist 239.")}, flags=[])
add("MARCELL", "Marcellinus", ["MARCELL."],
    {"DEFAULT": w("Vita Thucydidis", "section", "'V. Thuc.' = Vita Thucydidis.")}, flags=[])

# --- Orators / poets / dramatists (Greek) ---
add("ISOCR", "Isocrates", ["ISOCR."],
    {"DEFAULT": w("(oration of Isocrates)", "section", ital=False),
     "Bus.": w("Busiris", "section")},
    flags=[])
add("ANDOC", "Andocides", ["ANDOC."],
    {"DEFAULT": w("(oration of Andocides)", "book-section", ital=False)}, flags=[])
add("LYCURG", "Lycurgus", ["LYCURG."],
    {"Leocr.": w("in Leocratem", "section")}, flags=[])
add("ARISTOPH", "Aristophanes", ["ARISTOPH."],
    {"DEFAULT": w("(comedy of Aristophanes)", "section", ital=False),
     "Aves": w("Aves", "section"),
     "Nub.": w("Nubes", "section"),
     "Vesp.": w("Vespae", "section", "Gorgias A5a '—Vesp. 420' (after ARISTOPH. Aves 1694); Wasps, by line."),
     "Tagenistae": w("Tagenistae", "opaque",
                     "Prodicus A5 '—Tagenistae fr. 490 K.' (after ARISTOPH. Nub. 360): the lost "
                     "comedy Tagenistae (Fryers), cited by Kock's fragment number (CAF I).")},
    flags=[])
add("MENANDER", "Menander (rhetor)", ["MENANDER"],
    {"DEFAULT": w("(rhetorical treatise)", "book-chapter-section", "Menander Rhetor, Peri epideiktikon.", ital=False)},
    flags=["ambiguous-abbrev"])

# --- Xenophon ---
add("XENOPH", "Xenophon", ["XENOPH.", "XEN."],
    {"DEFAULT": w("(work of Xenophon)", "opaque", ital=False),
     "Mem.": w("Memorabilia", "book-chapter-section"),
     "Memor.": w("Memorabilia", "book-chapter-section"),
     "Memorab.": w("Memorabilia", "book-chapter-section"),
     "Symp.": w("Symposium", "book-section"),
     "An.": w("Anabasis", "book-chapter-section"),
     "Hell.": w("Hellenica", "book-chapter-section")},
    flags=[])

# --- Rhetoricians / grammarians / lexica ---
add("POLL", "Julius Pollux", ["POLL.", "POLLUX"],
    {"DEFAULT": w("Onomasticon", "book-section")}, flags=[])
add("MOERIS", "Moeris", ["MOERIS"],
    {"DEFAULT": w("Lexicon Atticum", "page-line", "Bekker page.")}, flags=[])
add("PHRYNICH", "Phrynichus", ["PHRYNICH."],
    {"DEFAULT": w("Praeparatio Sophistica", "opaque"),
     # 2026-09-24: Critias A20 "PHRYNICH. Praepar. sophist. [Phot. Bibl. 158
     # p. 101b 4 Bekk.]" -- DK prints no page/number of his own after the
     # title abbreviation, only the bracket naming where Photius preserves
     # the passage; that bracket is apparatus, kept as printed
     # (`editor_apparatus`, reusing the gnomologia mechanism), and the locus
     # is then empty (no page/number to print).
     "Praepar. sophist.": w("Praeparatio Sophistica", "opaque", editor_apparatus=True)},
    flags=[])
add("EROTIAN", "Erotianus", ["EROTIAN."],
    {"DEFAULT": w("Vocum Hippocraticarum Collectio", "page-line")}, flags=[])
add("HERMOG", "Hermogenes", ["HERMOG.", "HERMOGENES"],
    {"de id.": w("De Ideis", "opaque"),
     "de ideis": w("De Ideis", "opaque")},
    flags=[])
add("SOPAT", "Sopater", ["SOPAT."],
    {"Rhet.": w("(Prolegomena in Aristidem / Rhetorica)", "opaque", "Walz Rhet. Gr.", ital=False)}, flags=["obscure"])
add("ARISTID", "Aelius Aristides", ["ARISTID."],
    {"DEFAULT": w("Ars Rhetorica", "book-section")}, flags=[])
add("LIBAN", "Libanius", ["LIBAN."],
    {"Or.": w("Orationes", "opaque", "Foerster vol/page.")}, flags=[])
add("HIMER", "Himerius", ["HIMER."],
    {"DEFAULT": w("(oration of Himerius)", "opaque", ital=False),
     "Ecl.": w("Eclogae", "book-section")},
    flags=[])
add("MAXIM_TYR", "Maximus of Tyre", ["MAXIM."],
    {"TYR.": w("Dissertationes", "book-page", "'MAXIM. TYR.' = Maximus of Tyre, Dissertationes.")},
    flags=[])
add("THEMIST_note", "x", [], {}); del CANON["THEMIST_note"]
add("DIO_CHRYS", "Dio Chrysostom", ["DIO", "DIO CHRYSOST."],
    {"DEFAULT": w("Orationes", "section", "Oration + section; von Arnim vol/page in brackets.")}, flags=[])
add("LUCIAN", "Lucian", ["LUCIAN.", "LUC."],
    {"DEFAULT": w("(work of Lucian)", "opaque", "'V. hist.' = Verae Historiae.", ital=False),
     "de lapsu in sal.": w("Pro Lapsu inter Salutandum", "section")},
    flags=[])
add("HERACLIT_ALL", "Heraclitus (allegorista)", ["HERACLIT."],
    {"DEFAULT": w("Allegoriae Homericae", "section", "Heraclitus the Homeric allegorist ('Alleg. Hom.'); NOT the philosopher Heraclitus."),
     "Alleg.": w("Allegoriae Homericae", "section")},
    flags=["not-the-philosopher"])
add("CORNUTUS", "Cornutus", ["CORNUTUS"],
    {"Epidrom.": w("Epidrome (Theologiae Graecae Compendium)", "section")}, flags=[])
add("IULIAN", "Julian (imp.)", ["IULIAN."],
    {"Ep.": w("Epistulae", "opaque")}, flags=[])
add("ARTEMID", "Artemidorus", ["ARTEMID."],
    {"DEFAULT": w("Oneirocritica", "book-page-line")}, flags=[])
add("PHILOSTR_note","x",[],{}); del CANON["PHILOSTR_note"]

# --- Peripatetic doxography / mathematics / astronomy ---
add("ACHILL", "Achilles Tatius (astronomus)", ["ACHILL. Is", "ACHILL. Is.", "ACHILL. IS."],
    {"DEFAULT": w("Isagoge in Arati Phaenomena", "chapter-page",
       "'Is./Isag.' = Isagoge; census token often truncated ('ag. ...'). Maass page,line.")},
    flags=["truncated-token"])
add("THEO_SMYRN", "Theon of Smyrna", ["THEO"],
    {"DEFAULT": w("Expositio Rerum Mathematicarum", "page-line", "'Theo Smyrn.' = Theon of Smyrna; Hiller page."),
     "Smyrn.": w("Expositio Rerum Mathematicarum", "page-line"),
     "SMYRN.": w("Expositio Rerum Mathematicarum", "page-line")},
    flags=[])
add("NICOM", "Nicomachus of Gerasa", ["NICOM."],
    {"Arithm.": w("Introductio Arithmetica", "book-page-line")}, flags=[])
add("THEOL_ARITHM", "Theologumena Arithmeticae", ["THEOL. Arithm.", "THEOLOG."],
    {"DEFAULT": w("Theologumena Arithmeticae", "page-line", "de Falco page. Anonymous compilation.")},
    flags=[])
add("ANATOL", "Anatolius", ["ANATOL."],
    {"de decade p.": w("De Decade", "page-line", "Heiberg.")}, flags=[])
add("AGATHEM", "Agathemerus", ["AGATHEM.", "AGATHEMER."],
    {"DEFAULT": w("Geographiae Informatio", "book-section")}, flags=[])
add("EUDOX", "Eudoxus", ["EUDOX."],
    {"DEFAULT": w("Ars Astronomica", "opaque", "Papyrus (Blass); fragmentary.")}, flags=["fragmentary"])
add("HEPHAEST", "Hephaestion", ["HEPHAEST."],
    {"DEFAULT": w("Enchiridion de Metris", "page-line", ital=True),
     "Ench.": w("Enchiridion de Metris", "page-line")},
    flags=[])
add("PTOLEM", "Ptolemy", ["PTOLEM."],
    {"DEFAULT": w("(work of Ptolemy)", "opaque", "'Apparit.' = Phaseis (De Apparitionibus).", ital=False)}, flags=[])
add("DERCYLL", "Dercyllides", ["DERCYLLIDES"],
    {"DEFAULT": w("(apud Theonem astr.)", "page-line", "Cited via Theon.", ital=False)}, flags=["obscure"])
add("NICAND", "Nicander", ["NICAND."],
    {"Alex.": w("Alexipharmaca", "section")}, flags=[])

# --- Medical ---
add("HIPPOCR", "Hippocrates (corpus)", ["HIPPOCR."],
    {"DEFAULT": w("(Hippocratic treatise)", "opaque", "Littré vol/page '[VI 34 L.]'.", ital=False),
     "de arte": w("De Arte", "section"),
     "de prisc. med.": w("De Prisca Medicina (De Vetere Medicina)", "section")},
    flags=[])
add("SORAN", "Soranus", ["SORAN.", "SORANUS"],
    {"Gynaec.": w("Gynaecia", "book-page-line", "Ilberg.")}, flags=[])
add("RUFUS", "Rufus of Ephesus", ["RUFUS"],
    {"DEFAULT": w("De Nominatione Partium Hominis", "page-line", "Daremberg.")}, flags=[])
add("APOLLON_CIT", "Apollonius of Citium", ["APOLLON. Cit."],
    {"in Hipp. p.": w("in Hippocratis De Articulis", "page-line")}, flags=[])
add("PALAEPHAT", "Palaephatus", ["PALAEPHAT."],
    {"de incredib. p.": w("De Incredibilibus", "page-line", "Festa.")}, flags=[])
add("CAELIUS", "Caelius Aurelianus", ["CAELIUS", "CAELIUS AUREL."],
    {"Morb. chron.": w("De Morbis Chronicis", "opaque",
        "2026-09-24: Empedocles A98 'CAELIUS AUREL. Morb. chron. I 5 p. 25 Sich.' = Caelius "
        "Aurelianus, De morbis chronicis (Tardae passiones) I 5, page 25 of Sichard's "
        "edition (Basel 1529). Replaces the census key 'AURE' (the truncated 'AUREL.'), "
        "which matched no printed head and made A98 fatal.")},
    flags=[])

# --- Apollonius Dyscolus / grammatical ---
add("APOLL_DYSC", "Apollonius Dyscolus", ["APOLL. DYSC.", "APOLLON."],
    {"de pron. p.": w("De Pronominibus", "page-line", "Schneider."),
     "de pronom. p.": w("De Pronominibus", "page-line")},
    flags=[])
add("HERODIAN_note","x",[],{}); del CANON["HERODIAN_note"]

# --- Anthology / gnomologia / anecdota (edition-based) ---
# A gnomologium is a collection, not an author (Grok content review item 4,
# 2026-09-24: "Gnomologium, Gnomologium Parisinum" printed the name twice):
# like Bekker's Anecdota it has no author (canonical None) and renders as the
# collection's title; the locus is DK's codex and saying number ("743 n.
# 312"), the editor or edition DK names is apparatus, as printed
# (`editor_apparatus`: "ed. Sternbach", "Sternb.", "[Ac. Cracov. XX 152]").
_GNOM = dict(editor_apparatus=True)
add("GNOMOL", None, ["GNOMOL.", "GNOM."],
    {"DEFAULT": w("(Gnomologium)", "opaque", "Named by manuscript/collection (Vaticanum, Vindobonense, Parisinum, Monacense); edition ref in brackets.", ital=False, **_GNOM),
     "VATIC.": w("Gnomologium Vaticanum", "opaque", **_GNOM),
     "VINDOB.": w("Gnomologium Vindobonense", "opaque", **_GNOM),
     "PARIS.": w("Gnomologium Parisinum", "opaque",
                 "2026-09-24: Empedocles A20 'GNOM. PARIS. n. 153 [Ac. Cracov. XX 152]' and "
                 "Heraclitus B131 '—Paris. ed. Sternbach n. 209' = L. Sternbach's Gnomologium "
                 "Parisinum ineditum (Rozprawy Akademii Umiejętności, Kraków, XX, 1893).", **_GNOM),
     "Monac. lat.": w("Gnomologium Monacense Latinum", "opaque",
                 "2026-09-24: Heraclitus B130 'GNOMOL. Monac. lat. I 19 (Caecil. Balb. Wölfflin "
                 "...)' = the Latin Munich gnomologium printed by Wölfflin with Caecilius Balbus, "
                 "De nugis philosophorum (Basel 1855).", **_GNOM)},
    flags=["edition-keyed"])
# Bekker's Anecdota Graeca -- John's ruling, 2026-09-24: "AN. BEKK. Lex. VI p.
# 418, 6" renders as the work *Anecdota Graeca* with NO author, locus "I, Lex.
# VI p. 418, 6" (volume, lexicon, page, line). canonical_author None = no
# author printed.
# The volume (volume_by_part; Sol review finding 2): Bekker's three volumes
# each start at p. 1 (I Berlin 1814, II 1816, III 1821), so a page alone
# never names one. A volume numeral DK prints ("ANECD. Bekk. I 337, 13",
# Empedocles B47) is the volume. Otherwise only a part known to lie in vol.
# I, with its page inside that part, gives vol. I -- the Lexica Segueriana
# of Coislin. 345 fill vol. I: the TLG's canon (DOCCAN2) gives "Anecdota
# Graeca, vol. 1, Bekker, Berlin 1814" for 4289.001-004, pp. 75-116 (the
# Antiatticista), 117-180, 181-194, 195-318 (Lex. V); Lex. VI, the Synagoge
# (Συναγωγὴ λέξεων χρησίμων), pp. 319-476, closes the volume (DK's own "I
# 337, 13 [Συναγωγὴ λέξεων χρησ.]"). DK cites only the Antiatticista and
# Lex. VI, so only they are listed; any other head stays as printed,
# flagged edition-volume-unknown.
_SYNAGOGE = [["Lex. VI", 319, 476, "I"]]
add("ANECD_BEKK", None, ["ANECD. BEKK.", "ANECD. Bekk.", "AN. BEKK."],
    {"DEFAULT": w("Anecdota Graeca", "page-line",
        "Bekker, Anecdota Graeca; DK names the volume itself here ('I 337, 13').",
        volume_by_part=[]),
     "Lex.": w("Anecdota Graeca", "page-line",
        "'Lex. VI p. 470, 25' = Bekker's sixth lexicon (the Synagoge), vol. I.",
        locus_includes_work=True, volume_by_part=_SYNAGOGE),
     "Antiattic.": w("Anecdota Graeca", "page-line",
        "'Antiattic. 114, 28' = the Antiatticista, vol. I pp. 75-116.",
        locus_includes_work=True, volume_by_part=[["Antiattic.", 75, 116, "I"]])},
    flags=["edition-keyed", "not-single-author"])
# The Antiatticista named in the author slot ("ANTIATT. Bekk. An. 78, 20",
# "ANTIATT. BEKK. p. 94, 1"): the same edition; DK's own "Antiatt." goes
# before the page so the lexicon is not lost ('An.' = Anecdota, dropped).
_ANTIATT = [["Antiatt.", 75, 116, "I"]]
add("ANTIATT_BEKK", None, ["ANTIATT. BEKK.", "ANTIATT. Bekk."],
    {"DEFAULT": w("Anecdota Graeca", "page-line", "Antiatticista, vol. I pp. 75-116.",
        locus_prefix="Antiatt.", volume_by_part=_ANTIATT),
     "An.": w("Anecdota Graeca", "page-line", "'An.' = Anecdota: Antiatticista, vol. I pp. 75-116.",
        locus_prefix="Antiatt.", volume_by_part=_ANTIATT)},
    flags=["edition-keyed", "not-single-author"])
add("ANECD_PAR", "Anecdota Parisina", ["ANECD. PAR."],
    {"DEFAULT": w("Anecdota Graeca Parisiensia", "page-line", "Cramer.")}, flags=["edition-keyed"])
add("LESBON", "Lesbonax", ["LESBON."],
    {"DEFAULT": w("De Figuris", "page-line", "Valckenaer.")}, flags=["obscure"])

# --- Etymologica ---
add("ETYM", "Etymologicum", ["ETYM."],
    {"DEFAULT": w("(Etymologicum)", "opaque", "Family of lexica cited by name: Genuinum, Magnum, Gudianum, Orionis. Cited by lemma (s.v.).", ital=False),
     "GEN.": w("Etymologicum Genuinum", "opaque"),
     "GENUIN.": w("Etymologicum Genuinum", "opaque"),
     "ORION.": w("Orionis Etymologicum", "opaque")},
    flags=["cited-by-lemma", "edition-keyed"])

# --- Scholia (title = 'Scholia in <author>') ---
def schol(target):
    return {"DEFAULT": w("Scholia in " + target, "opaque",
        "Scholia cited by the passage of " + target + " they gloss (+ editor page).", ital=False)}
add("SCHOL_HOM", "Scholia in Homerum", ["SCHOL. HOM.", "SCHOL. HOM. BT", "SCHOL. BLT", "SCHOL. A", "SCHOL. ABT", "AMMON. SCHOL. HOMER."], schol("Homerum"), flags=["scholia"])
add("SCHOL_DIONYS", "Scholia in Dionysium Thracem", ["SCHOL. DIONYS."], {"THRAC.": w("Scholia in Dionysium Thracem", "page-line", "Hilgard.", ital=False)}, flags=["scholia"])
add("SCHOL_APOLL", "Scholia in Apollonium Rhodium", ["SCHOL. APOLL."], schol("Apollonium Rhodium"), flags=["scholia"])
add("SCHOL_ARISTOPH", "Scholia in Aristophanem", ["SCHOL. ARISTOPH.", "SCHOL. ARIST."], schol("Aristophanem"), flags=["scholia"])
add("SCHOL_ARAT", "Scholia in Aratum", ["SCHOL. ARAT."], schol("Aratum"), flags=["scholia"])
add("SCHOL_PIND", "Scholia in Pindarum", ["SCHOL. PIND."], schol("Pindarum"), flags=["scholia"])
CANON["SCHOL_PIND"]["works"]["Nem."] = w(
    "Scholia in Pindarum", "opaque",
    "2026-09-24: Hippias B15 '—Nem. 7, 53' (after 'SCHOL. PIND. Pyth. 4, 288') = scholia "
    "on Pindar's Nemean 7 (Drachmann, Scholia vetera III). The ode stays in the locus as "
    "printed, like 'Pyth.' under the DEFAULT.", ital=False, locus_includes_work=True)
add("SCHOL_NIC", "Scholia in Nicandrum", ["SCHOL. NICANDR.", "SCHOL. Nic."], schol("Nicandrum"), flags=["scholia"])
add("SCHOL_EUR", "Scholia in Euripidem", ["SCHOL. EUR.", "SCHOL. EURIP."], schol("Euripidem"), flags=["scholia"])
add("SCHOL_AESCHIN", "Scholia in Aeschinem", ["SCHOL. AESCHIN."], schol("Aeschinem"), flags=["scholia"])
add("SCHOL_EPICTET", "Scholia in Epictetum", ["SCHOL. EPICTET."], schol("Epictetum"), flags=["scholia"])
add("SCHOL_HIPPOCR", "Scholia in Hippocratem", ["SCHOL. HIPPOCR."], schol("Hippocratem"), flags=["scholia"])
add("SCHOL_GREGOR", "Scholia in Gregorium", ["SCHOL. IN GREGOR."], schol("Gregorium Nazianzenum"), flags=["scholia"])
add("SCHOL_PLAT", "Scholia in Platonem", ["SCHOL. PLATONIS"], schol("Platonem"), flags=["scholia"])
add("SCHOL_BARE", "Scholia", ["SCHOL."],
    {"DEFAULT": w("Scholia", "opaque", "Bare 'SCHOL.' + target named in head (in Apoll. Rhod., in Euclid., ad Dionys.).", ital=False),
     "ad DIONYS.": w("Scholia in Dionysium Thracem", "page-line"),
     "in APOLL. RHOD.": w("Scholia in Apollonium Rhodium", "opaque"),
     "in Euclid. X": w("Scholia in Euclidem", "opaque")},
    flags=["scholia"])
add("GREGOR", "Gregory of Corinth", ["GREGOR."],
    {"DEFAULT": w("(ad Hermogenem)", "opaque", ital=False)}, flags=["obscure"])
add("VITA_EUR", "Vita Euripidis", ["VITA"],
    {"EURIPID.": w("Vita Euripidis", "page-line", "'VITA EURIPID.' = anonymous Life of Euripides.", ital=False)},
    flags=["anonymous"])

# --- Tzetzes / Byzantine ---
add("TZETZ", "John Tzetzes", ["TZETZ.", "TZETZES"],
    {"DEFAULT": w("(work of Tzetzes)", "opaque", ital=False),
     "Alleg.": w("Allegoriae Iliadis", "opaque"),
     "ad Dion.": w("Scholia in Dionysium Periegetam", "opaque", "'ad Dion. Perieg.'"),
     "ad Aristoph.": w("Scholia in Aristophanem", "opaque"),
     "Schol. z. Hesiod": w("Scholia in Hesiodum", "opaque",
                           "2026-09-24: Democritus B5 'TZETZES Schol. z. Hesiod (Gaisford Poet. "
                           "gr. min. III 58)' = Tzetzes' scholia on Hesiod as printed in "
                           "Gaisford, Poetae minores Graeci III (scholia ad Hesiodum). DK names "
                           "no poem, so neither does the title.", ital=False)},
    flags=[])
add("PLANUD", "Maximus Planudes", ["PLANUD."],
    {"ad Hermog.": w("in Hermogenem", "opaque", "Walz Rhet. Gr."),
     "in Hermog. Rhet. V": w("in Hermogenem", "opaque")},
    flags=[])
add("EUSTATH", "Eustathius", ["EUSTATH."],
    {"DEFAULT": w("Commentarii ad Homerum", "opaque", "'ad Il./ad Od.'; census tokens truncated ('ad.', 'Zu ').", ital=False),
     "Zu": w("Commentarii ad Homerum", "opaque")},
    flags=["truncated-token"])
add("PSEUDODIONYS", "pseudo-Dionysius (rhetor)", ["PSEUDODIONYS."],
    {"DEFAULT": w("Ars Rhetorica", "opaque")}, flags=["pseudo"])
# Grok content review item 5 (2026-09-24): DK's "CEBREN." (Anaxagoras A10,
# "CEBREN. I 165, 18 Bekk.") is Georgius Cedrenus, Compendium historiarum,
# cited by volume, page and line of Bekker's Bonn edition (CSHB, 1838-39) --
# not Bekker's Anecdota, as this entry had it.
add("CEBREN", "Georgius Cedrenus", ["CEBREN."],
    {"DEFAULT": w("Compendium Historiarum", "book-page-line",
                  "Volume + page + line of Bekker's Bonn edition ('I 165, 18 Bekk.').")},
    flags=[])
add("HERMIPPUS", "Hermippus (astrol.)", ["HERMIPPUS"],
    {"DEFAULT": w("De Astrologia", "book-chapter-section", "Byzantine dialogue; Kroll-Viereck.")}, flags=["obscure"])
# A gnomological collection too (item 4): no author; "CORPUS PARISINUM
# PROFANUM [Cod. Paris. gr. 1168 nach Elter]: 166" (Democritus B302) printed
# "PARISINUM PROFANUM" again in its locus.
add("CORPUS_PAR", None, ["CORPUS"],
    {"DEFAULT": w("Corpus Parisinum Profanum", "section", "Anonymous gnomological corpus.", **_GNOM),
     "PARISINUM PROFANUM": w("Corpus Parisinum Profanum", "section", "Anonymous gnomological corpus.", **_GNOM)},
    flags=["anonymous"])

# --- Dionysius of Halicarnassus ---
add("DIONYS_HAL", "Dionysius of Halicarnassus", ["DIONYS.", "DIONYSIUS"],
    {"DEFAULT": w("(work of Dionysius of Halicarnassus)", "opaque", "NB bare 'DIONYS.' can also be Dionysius of Alexandria (apud Eus.) — disambiguate from head context.", ital=False),
     "Lys.": w("De Lysia", "section"),
     "de comp. verb.": w("De Compositione Verborum", "section")},
    flags=["ambiguous-abbrev"])

# --- Demetrius ---
add("DEMETR", "Demetrius", ["DEMETR."],
    {"de poem.": w("De Poematis", "opaque", "Philodemus' work / Herculanean; Demetrius Laco. Flagged: attribution uncertain.")},
    flags=["uncertain"])

# --- Philo / Philodemus (distinct!) ---
add("PHILO", "Philo of Alexandria", ["PHILO"],
    {"DEFAULT": w("(work of Philo)", "opaque", ital=False),
     "de prov.": w("De Providentia", "book-para"),
     "de provid.": w("De Providentia", "book-para")},
    flags=[])
add("PHILODEM", "Philodemus", ["PHILODEM.", "PHILOD."],
    {"DEFAULT": w("(work of Philodemus)", "opaque", "Herculanean papyri; Voll. Herc. / editor.", ital=False),
     "Rhet.": w("Rhetorica", "book-page-line", "Sudhaus vol/page + fr."),
     "de ira": w("De Ira", "page-line", "Gomperz."),
     "de morte": w("De Morte", "page-line", "Mekler."),
     "de piet. p.": w("De Pietate", "page-line", "Gomperz."),
     "de piet. c.": w("De Pietate", "page-line"),
     "de music.": w("De Musica", "opaque",
                    "Democritus B144 '—de music. Δ 31 p. 108, 29 Kemke' (after PHILODEM. de ira): "
                    "Philodemus, De musica IV, Kemke's edition (1884).")},
    flags=[])

# --- Marcus Aurelius ---
add("MARC_ANT", "Marcus Aurelius", ["MARC."],
    {"ANTON.": w("Ad Se Ipsum (Meditationes)", "book-section", "'MARC. ANTON.' = Marcus Antoninus."),
     "Anton.": w("Ad Se Ipsum (Meditationes)", "book-section")},
    flags=[])

# --- Ioannes Lydus ---
add("IOANN_LYD", "John Lydus", ["IOANN. LYD.", "JOH."],
    {"de mens.": w("De Mensibus", "book-chapter-section"),
     "DEFAULT": w("De Mensibus", "book-chapter-section", "'JOH. LYDUS de mens.' = John Lydus, De Mensibus.")},
    flags=[])

# --- Josephus ---
add("IOSEPH", "Josephus", ["IOSEPH."],
    {"c. Ap. I": w("Contra Apionem (lib. I)", "section"),
     "c. Ap. II": w("Contra Apionem (lib. II)", "section")},
    flags=[])

# --- Arius Didymus / Stobaeus-source ---
add("ARIUS", "Arius Didymus", ["ARIUS", "ARIUS DID."],
    {"DEFAULT": w("Epitome (Physica)", "opaque", "'ARIUS DID. ap. Eus. P. E.'; '(D. NNN)' = Diels DG page.")},
    flags=["diels-doxographi"])

# --- Numenius etc. handled. Nicomachus of Gerasa handled. ---

# --- Aristocritus / Theosophia ---
add("ARISTOCRITUS", "Aristocritus", ["ARISTOCRITUS"],
    {"Theos.": w("Theosophia", "section"),
     "Theosophia": w("Theosophia", "section")},
    flags=["obscure"])

# --- Apollodorus ---
add("APOLLODOR", "Apollodorus", ["APOLLODOR.", "APOLLODOROS"],
    {"DEFAULT": w("(Chronica / FGrHist 244)", "opaque", "Apollodorus of Athens, chronographer.", ital=False)},
    flags=[])

# --- Diogenes of Oinoanda / Apollonia distinct from Laertius ---
add("DIOGENES_OIN", "Diogenes of Oenoanda", ["DIOGENES"],
    {"DEFAULT": w("Fragmenta (Inscriptio)", "opaque",
       "'DIOGENES v. Oinoanda' = Diogenes of Oinoanda (Epicurean inscription); NOT Diog. Laertius.", ital=False),
     "LAERTIUS": w("Vitae Philosophorum", "book-para",
       "Census splits 'DIOGENES LAERTIUS' as author='DIOGENES', work='LAERTIUS'; author here is Diogenes Laertius (= DIOG_LAERT), not Oinoanda.")},
    flags=["ambiguous-name"])

# --- Named individuals cited once (real authors) ---
add("ALCIDAMAS", "Alcidamas", ["ALCIDAMAS"],
    {"DEFAULT": w("(apud Aristotelem)", "opaque", "Cited via Arist. Rhet.", ital=False)}, flags=[])
add("ARISTOCLES", "Aristocles", ["ARISTOCLES"],
    {"DEFAULT": w("(fragmenta)", "opaque", ital=False)}, flags=["obscure"])
add("MELAMPUS", "Melampus", ["MELAMPUS"],
    {"DEFAULT": w("(divinatory treatise)", "opaque", ital=False)}, flags=["obscure"])
add("MENON", "Menon (Anonymus Londinensis)", ["MENON"],
    {"DEFAULT": w("Anonymus Londinensis (Iatrica)", "opaque",
       "The medical doxography (P. Lond. 137) associated with Menon, pupil of Aristotle.")},
    flags=[])
add("SUETONIUS", "Suetonius", ["SUETONIUS"],
    {"DEFAULT": w("(fragmenta)", "opaque", "Miller Mélanges.", ital=False)}, flags=[])

# --- Codices / papyri (edition/shelfmark-keyed, not authors) ---
add("COD_PARIS", "Codex Parisinus", ["COD. PARIS."],
    {"DEFAULT": w("(manuscript source)", "opaque", "MS shelfmark, not an author.", ital=False)}, flags=["ms-shelfmark"])
add("COD_MONAC", "Codex Monacensis", ["COD. MONAC."],
    {"DEFAULT": w("(manuscript source)", "opaque", ital=False)}, flags=["ms-shelfmark"])
add("PAP", "Papyrus", ["PAP.", "PAPYR.", "OXYRH.", "HIBEH", "VOLL."],
    {"DEFAULT": w("(papyrus source)", "opaque",
       "Papyrus collections: Oxyrhynchus, Hibeh, Herculanean (Voll. Herc.), London, Petropolitanus, magical. Edition/number-keyed.", ital=False)},
    flags=["edition-keyed", "not-single-author"])
add("CATAL_ASTROL", "Catalogus Codicum Astrologorum", ["CATAL."],
    {"DEFAULT": w("Catalogus Codicum Astrologorum Graecorum", "opaque", ital=False),
     "CODD. ASTROL. GRAEC.": w("Catalogus Codicum Astrologorum Graecorum", "opaque", ital=False,
        notes="Full printed continuation of the abbreviation (B139 'CATAL. CODD. ASTROL. GRAEC. IV 32 "
              "VII 106'); matching it keeps it out of the locus (pilot gap fix 2026-07-24, Grok gate "
              "defect 3).")},
    flags=["edition-keyed"])
add("EXC", "Excerpta", ["EXC."],
    {"DEFAULT": w("(Excerpta)", "opaque", "'EXC. ASTRON.' = astronomical excerpts; 'EXC. VINDOB.' = Excerpta Vindobonensia.", ital=False),
     "VINDOB.": w("Excerpta Vindobonensia", "opaque")},
    flags=["edition-keyed"])
add("EPIGR", "Epigrammata (Anthologia)", ["EPIGR."],
    {"DEFAULT": w("(epigram)", "opaque", "Kaibel Epigrammata Graeca.", ital=False)}, flags=["edition-keyed"])
add("MASALA", "Messahala (Masha'allah)", ["MASALA"],
    {"DEFAULT": w("(astrological codex)", "opaque", ital=False)}, flags=["obscure", "ms-shelfmark"])
add("HYPOTH", "Hypothesis", ["HYPOTH."],
    {"SOPH.": w("Hypothesis (Sophoclis)", "opaque", "Argument prefixed to a play.", ital=False)},
    flags=["anonymous"])

# --- Pseudonymous / bracketed authors ---
add("PS_ARISTOT", "pseudo-Aristotle", ["[ARISTOT.]", "[ARIST.]", "[Arist.]"],
    {"DEFAULT": w("(pseudo-Aristotelian work)", "bekker", "Bracket = spurious/dubious attribution.", ital=False),
     "Probl.": w("Problemata", "bekker"),
     "de MXG": w("De Melisso Xenophane Gorgia", "bekker"),
     "de mundo": w("De Mundo", "bekker"),
     "Mirab.": w("De Mirabilibus Auscultationibus", "bekker"),
     "de lin. insec.": w("De Lineis Insecabilibus", "bekker"),
     "de lin. insecab. p.": w("De Lineis Insecabilibus", "bekker"),
     "hist. anim.": w("Historia Animalium", "bekker", "Bk 9/10 regarded spurious.")},
    flags=["pseudo"])
add("PS_PLUT", "pseudo-Plutarch", ["[PLUT.]", "[PLUTARCH.]", "[Plut.]"],
    {"DEFAULT": w("(pseudo-Plutarchean work)", "opaque", ital=False),
     "Strom.": w("Stromateis", "section", "ps.-Plut. Stromateis, a Diels doxographic source; '(D. NNN)' = Diels DG page."),
     "Vit.": w("Vitae Decem Oratorum", "opaque", "'Vit. X orat.' = Vitae Decem Oratorum.")},
    flags=["pseudo", "diels-doxographi"])
add("PS_GALEN", "pseudo-Galen", ["[GALEN.]", "[GALEN]"],
    {"DEFAULT": w("Historia Philosopha", "section",
       "ps.-Galen Historia Philosopha, a Diels doxographic source; '(D. NNN)' = Diels DG page."),
     "d. defin. med.": w("Definitiones Medicae", "opaque", "'[GALEN]. d. defin. med.' = pseudo-Galen, Definitiones Medicae (Kühn vol/page); distinct from the bare Historia Philosopha DEFAULT.")},
    flags=["pseudo", "diels-doxographi"])
add("PS_PLATO", "pseudo-Plato", ["[PLATO]"],
    {"Alcib.": w("Alcibiades (I/II)", "stephanus", "Spurious/disputed."),
     "Axiochos": w("Axiochus", "stephanus"),
     "Eryxias": w("Eryxias", "stephanus")},
    flags=["pseudo"])
add("PS_ARIST_note","x",[],{}); del CANON["PS_ARIST_note"]
add("PS_LUCIAN", "pseudo-Lucian", ["[LUC.]", "[LUCIAN.]"],
    {"Macrob.": w("Macrobii", "section", "'Macrob.' = Macrobii (Long-livers)."),
     "Macrob": w("Macrobii", "section",
                 "2026-09-24: Gorgias A13 prints '[LUC.] Macrob 23' with no period = "
                 "[Lucian], Macrobii 23 (Gorgias lived 108 years); A13 was fatal without "
                 "this key.")},
    flags=["pseudo"])
add("PS_GEMIN", "pseudo-Geminus", ["[GEMIN.]"],
    {"Isag.": w("Isagoge (Elementa Astronomiae)", "page-line", "Manitius.")},
    flags=["pseudo"])
add("PS_DEMOSTH", "pseudo-Demosthenes", ["[DEMOSTH.]"],
    {"DEFAULT": w("(spurious oration in the Demosthenic corpus)", "book-section", ital=False)},
    flags=["pseudo"])
add("PS_SYNES", "pseudo-Synesius", ["[SYNES.]"],
    {"ad Dioscorum": w("Ad Dioscorum (alchemical)", "opaque")},
    flags=["pseudo"])
add("PS_SUID", "Suda", ["[SUID.]"],
    {"DEFAULT": w("Lexicon (Suda)", "opaque", "Bracketed = editorial supplement.")},
    flags=["cited-by-lemma"])

# --- Democrates (gnomological pseudo-Democritus) ---
add("DEMOKRAT", "Democrates", ["DEMOKRAT.", "DEMOKRATES"],
    {"DEFAULT": w("Sententiae (Gnomae Democratis)", "section",
       "The gnomological 'Golden Sayings' collection under Democrates' name (DK 68 B, the Democrates maxims). Cited by saying number.")},
    flags=["pseudonymous-collection"])

# --- Anonymus Londinensis (as its own head) ---
add("ANON_LOND", "Anonymus Londinensis", ["ANON. LONDIN."],
    {"DEFAULT": w("Iatrica (Anonymus Londinensis)", "opaque",
       "Medical doxography, P. Lond. 137; cited by column,line.", ital=False)},
    flags=["anonymous"])
add("ANON_PLAT_THEAET", "Anonymus in Platonis Theaetetum", ["ANONYM. IN PLAT."],
    {"Theaet.": w("Commentarium in Platonis Theaetetum", "page-line",
       "Berlin papyrus (Anon. commentator on the Theaetetus).", ital=False)},
    flags=["anonymous"])
add("ANON_BYZANT", "Anonymus Byzantinus", ["ANONYM. BYZANT."],
    {"DEFAULT": w("(Isagoge in Aratum)", "opaque", "ed. Treu; astronomical.", ital=False)},
    flags=["anonymous", "obscure"])
add("ANON_ROHDEI", "Anonymus Rohdei", ["ANON. ROHDEI"],
    {"DEFAULT": w("(fragment, Rohde Kl. Schr.)", "opaque", ital=False)},
    flags=["obscure"])
add("SCHOL_BASIL", "Scholia in Basilium", ["SCHOL. BASILII"],
    {"DEFAULT": w("Scholia in Basilium", "opaque", "ed. Pasquali.", ital=False)},
    flags=["scholia"])

# NICOMACHUS full spelling (Gerasenus, via Porph./Iamb. witnesses)
CANON["NICOM"]["variants"].append("NICOMACHUS")
CANON["NICOM"]["works"]["Porph."] = w("(apud Porphyrium/Iamblichum, Vita Pythagorae)", "opaque",
    "Nicomachus cited through Porphyry's and Iamblichus' Lives of Pythagoras.", ital=False)

# ---------------------------------------------------------------------------
# DASH continuation (not a lexical author; resolved by the walk-back rules).
# ---------------------------------------------------------------------------
DASH_KEY = "—"

# Census tokens that are dash-continuation MIS-PARSES: the parser put a work-title
# fragment (or a Latin verse/prose word) into the author field. Author is inherited
# from the preceding column by the walk-back rules; these are NOT real authors.
DASH_MISPARSE = {
    # Plato dialogues appearing as "author" after a stripped dash:
    "Hipp.", "Hipp", "Meno", "Charmid.", "Euthyd.", "Lach.", "Phileb.", "Sympos.",
    # Plutarch Moralia fragments:
    "Qu.", "Reip.",
    # Aristophanes / Pindar / misc dramatic titles:
    "Vesp.", "Tagenistae", "Nem.",
    # Eusebius / lexica / gnomologia fragments:
    "Chron.", "Lex.", "Paris.", "Vatic.",
    # Latin verse/prose continuation words mis-taken as authors:
    "Ionium", "Italiae", "Democriti", "Democritus",
}

# Genuinely unmappable "author" tokens = apparatus / edition / cross-ref artifacts,
# NOT citation heads. Flagged, never expanded.
UNMAPPABLE = set()
for r in CENSUS:
    a = r["author_abbrev"]
    if a.startswith("[Stob.") or a.startswith("[STOB."):
        UNMAPPABLE.add(a)           # bracketed Stobaeus source-locations (Democritus maxims)
UNMAPPABLE |= {
    "Arnim",                                   # editor surname, not an author
    "[PLG II 269 B., ALG I 78 D.]",            # poetic-corpus edition ref
    "[s. 82 A 7. 85 A 2]", "[s. 84 A 20]",     # internal DK cross-refs
    "[d. Rhamn., d. caed. Her. 27]",           # cross-ref note
    "[fr. 4 P. Lang Bonn 1911 S. 53ff.]",      # edition/fragment ref
    "[Alternate source (Plato, Sophist, and related witnesses)]",  # census placeholder artifact
    "[Thrasymachos]",                          # bracketed section label, no locus
    "[Scholion]",                              # bare label
    "[s. II 254, 21. 255, 12. 256, 11]",       # internal DK page cross-ref
}

# --- Build variant -> key resolver and detect unmatched census authors ---
resolver = {}
for key, e in CANON.items():
    for v in e["variants"]:
        vv = nfc(v)
        if vv in resolver:
            print("DUP VARIANT:", v, "->", resolver[vv], "and", key, file=sys.stderr)
        resolver[vv] = key
DASH_MISPARSE = {nfc(x) for x in DASH_MISPARSE}
UNMAPPABLE = {nfc(x) for x in UNMAPPABLE}
NEED_WORK = {nfc(v) for e in CANON.values() for v in e.get("variants_need_work", [])}
for v in AMBIGUOUS_VARIANTS:
    if nfc(v) in resolver:
        print("AMBIGUOUS VARIANT ALSO AN AUTHOR VARIANT:", v, file=sys.stderr)

census_authors = {}
for r in CENSUS:
    census_authors[r["author_abbrev"]] = census_authors.get(r["author_abbrev"], 0) + r["occurrences"]

matched_occ = 0
dash_occ = 0
misparse_occ = 0
unmappable_occ = 0
unmatched = {}
for a0, occ in census_authors.items():
    a = nfc(a0)
    if a == DASH_KEY:
        dash_occ += occ
    elif a in NEED_WORK and a in DASH_MISPARSE:
        misparse_occ += occ  # "Hipp." alone: Plato's Hippias after a lost dash
    elif a in resolver or a in AMBIGUOUS_VARIANTS:
        matched_occ += occ
    elif a in DASH_MISPARSE:
        misparse_occ += occ
    elif a in UNMAPPABLE:
        unmappable_occ += occ
    else:
        unmatched[a] = occ

total = sum(census_authors.values())
print("TOTAL occ:", total)
print("matched (dictionary authors):", matched_occ)
print("dash continuation:", dash_occ)
print("dash misparse tokens:", misparse_occ)
print("unmappable artifacts:", unmappable_occ)
print("UNMATCHED count:", len(unmatched), "occ:", sum(unmatched.values()))
for a, occ in sorted(unmatched.items(), key=lambda kv: -kv[1]):
    print("   UNMATCHED", repr(a), occ)

# --- Work-level: which (author,work) pairs fall through to DEFAULT? ---
print("\n=== work fall-through to DEFAULT (matched authors, explicit work not named) ===")
fall = []
named_work_occ = 0
default_work_occ = 0
for r in CENSUS:
    a = nfc(r["author_abbrev"])
    key = resolver.get(a)
    if a in AMBIGUOUS_VARIANTS:
        named_work_occ += r["occurrences"]  # the author (and so the work) comes from the evidence
        continue
    if not key or (a in NEED_WORK and a in DASH_MISPARSE):
        continue
    works = CANON[key]["works"]
    wk = r["work_abbrev"]
    if wk is not None and nfc(wk) in {nfc(k) for k in works}:
        named_work_occ += r["occurrences"]
    elif wk is None:
        # bare author -> DEFAULT expected. If the author has no DEFAULT work at all,
        # the occurrence isn't silently dropped from the coverage stats: it falls to
        # the same generic/opaque bucket as an explicit-but-unmatched work token
        # (e.g. HYPOTH.'s one census record, where the splitter folded the printed
        # work name into the locus field instead of work_abbrev).
        if "DEFAULT" in works:
            named_work_occ += r["occurrences"]
        else:
            default_work_occ += r["occurrences"]
    else:
        default_work_occ += r["occurrences"]
        fall.append((key, wk, r["occurrences"]))
for key, wk, occ in sorted(fall, key=lambda t: (-t[2], t[0])):
    print(f"   {occ:>3}  {key}  ::  {wk}")
print("named-work occ:", named_work_occ, " default/opaque-work occ:", default_work_occ)

# ---------------------------------------------------------------------------
# EMIT citation-dictionary.json
# ---------------------------------------------------------------------------
OUT = {
    "meta": {
        "purpose": "Deterministic expansion of DK source-citation heads into Hackett-style "
                   "English/Latinized citations, and author/work resolution for Greek dash-continuation heads.",
        "conventions": {
            "author_names": "Latinized nominative unless commonly anglicized in English scholarship (John's ruling, 2026-07-24): Aristotle, Plutarch, Clement of Alexandria, Stobaeus; Aëtius, Simplicius unchanged.",
            "work_titles": "Latin, rendered italic where title_italic=true (marked structurally, not with embedded markup). "
                           "title_italic=false marks placeholder/descriptive DEFAULT titles that are not real work titles.",
            "locus_templates": {
                "bekker": "Aristotle & CAG commentators: book-letter + chapter + Bekker number (A 3. 984a 11).",
                "stephanus": "Plato: Stephanus page + column (183 E, p. 76 C).",
                "moralia": "Plutarch Moralia: chapter + Stephanus page (4 p. 1108 F).",
                "vita": "Lives/biographies: chapter number (16).",
                "book-chapter-section": "Roman book . arabic chapter . arabic section (I 7, 5).",
                "book-para": "Roman book + arabic paragraph/section (II 6, VII 90).",
                "book-page-col": "Roman book + page-number + column letter (V 220 B).",
                "book-page": "Roman book + editor page 'p.' (I p. 61).",
                "page-line": "editor page, line (+editor name) (164, 22; 65, 11 Friedl.).",
                "book-page-line": "Roman book + page + line (II 180 Sudh.).",
                "section": "bare arabic section/fragment number (11, 59).",
                "book-section": "Roman book + arabic section, no page (VIII 19).",
                "chapter-page": "chapter + editor page (c. 251 p. 284, 10 Wrob.).",
                "opaque": "irregular/compound locus; render verbatim as printed."
            },
            "flags": {
                "diels-doxographi": "head may carry '(D. NNN)' = Diels, Doxographi Graeci p. NNN; keep in parentheses, do not silently drop.",
                "editor-page-bracket": "head may carry '[II 438, 9 St.]' etc. = editor page/line (Staehlin, Wachsmuth...); apparatus, preserve verbatim, do not expand.",
                "cited-by-lemma": "no numeric locus; cited by headword (s.v.).",
                "title-is-commentary": "title is a commentary 'in <Aristotelem/Platonem>'; locus is the commentary page, not the base text.",
                "pseudo": "bracketed/spurious attribution ([ARISTOT.] -> pseudo-Aristotle).",
                "ambiguous-abbrev": "abbrev shared by >1 author; disambiguate from work or head context. "
                                    "An abbreviation in `ambiguous_variants` is no author's variant: the stage picks "
                                    "the author from what follows it, else keeps the head as printed with this flag.",
                "author-inferred": "(set by the stage) the author was picked from an ambiguous abbreviation by what "
                                   "follows it; on the head and every dash built on it. A Herodotus reading so "
                                   "picked must be confirmed in the TLG (tests/test_dash_citations_verified.py).",
                "edition-volume-unknown": "a work with `volume_by_part` whose head prints no volume and names "
                                          "no listed part with its page inside that part: the head stays as printed.",
                "edition-keyed / ms-shelfmark / scholia / anonymous / obscure / truncated-token": "see per-entry notes."
            },
            "multi_source_heads": "A head naming several witnesses (e.g. 'PLUT. adv. Col. 10 p. 1111 F. AËT. I 30, 1 (D. 326, 10)') "
                                  "is split at each new explicit author token and each source expanded independently, joined by semicolons in render."
        },
        "coverage": {
            "total_parseable_heads": total,
            "mapped_to_dictionary_author": matched_occ,
            "dash_continuation_resolved_by_rules": dash_occ,
            "dash_misparse_tokens_resolved_by_rules": misparse_occ,
            "unmappable_apparatus_artifacts": unmappable_occ,
            "named_work_occ": named_work_occ,
            "generic_or_opaque_work_occ": default_work_occ,
            "pct_heads_covered_incl_dash": round(100.0 * (matched_occ + dash_occ + misparse_occ) / total, 1),
            "pct_heads_covered_dictionary_only": round(100.0 * matched_occ / total, 1)
        },
        "dash_misparse_tokens": sorted(DASH_MISPARSE),
        "ambiguous_variants": AMBIGUOUS_VARIANTS,
        "ambiguous_variants_rules": {
            "book-chapter": "a Roman book numeral and a number follow the abbreviation in the head",
            "greek-title": "nothing follows it in the head, and the text after the head opens with a "
                           "Greek title abbreviation in 'π.' (Περὶ ...)"},
        "work_fields": {
            "column_letters": "true: the locus may end in Stephanus/Casaubon column letters ('1113 AB') "
                              "although the template is not stephanus / moralia / bekker / book-page-col",
            "volume_by_part": "[[part, first page, last page, volume], ...]: an edition in volumes that "
                              "each start at p. 1. A volume numeral the head prints wins; else a locus "
                              "opening with a listed part whose page lies in it gets that volume, printed "
                              "first ('I, Lex. VI p. 418, 6'); else the head stays as printed",
            "locus_prefix": "printed before the locus (the lexicon a head names in its author slot)",
            "locus_as_printed": "true: the locus is everything the head prints after the title, untrimmed; "
                                "a 'bei <author> ...' note (the text that preserves the passage) is apparatus "
                                "and the locus is then empty",
            "editor_apparatus": "true: the locus is only the numbers (codex, saying, book); the editor or "
                                "edition DK names with it ('ed. Sternbach', 'Sternb.', a bracket) is apparatus, "
                                "as printed",
            "variants_need_work (author level)": "these variants name the author only when one of his "
                                                 "titles follows them"},
        "unmappable_artifacts": sorted(UNMAPPABLE),
        "notes": "Entries keyed by normalized (NFC) author abbreviation. 'variants' lists exact census spellings folded into the key. "
                 "'—' (dash) is NOT an author entry: it is resolved by the dash-continuation rules in the companion memo."
    },
    "authors": CANON
}
json.dump(OUT, open(os.path.join(SELF_DIR, "citation-dictionary.json"), "w"),
          ensure_ascii=False, indent=2)
print("\nWROTE citation-dictionary.json  (authors:", len(CANON), ")")
