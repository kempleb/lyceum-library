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
    # lexicon a head names only in its author slot); see meta.work_fields.
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
    # 2026-09-26 (page-structure check): two title spellings DK prints that had no key.
    "de part. an.": w("De Partibus Animalium", "bekker",
                      "Empedocles A78 'ARISTOT. de part. an. Α 1. 642a 17' = PA I 1, 642a17 "
                      "(fell to the unspecified-work default)."),
    "d. gen. et corr.": w("De Generatione et Corruptione", "bekker",
                          "Empedocles A42, a title continuing ARISTOT. inside the passage: "
                          "'d. gen. et corr. B 7. 334a 5' = GC II 7, 334a5."),
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
     "d. orat.": w("De Oratore", "book-para",
                   "Anaxagoras A15 'CIC. d. orat. III 138' = De or. 3.138 (Pericles taught by Anaxagoras); "
                   "the head was cut after 'd.' (2026-09-26)."),
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
     "Ep.": w("Epistulae", "opaque"),
     # 2026-09-27: Critias A1, A21, Protagoras A2, Antiphon A6 "V. soph. I 16";
     # Democritus A9 "Vit. sophist. 10 p. 13, 1 Kayser". Match is case-folded,
     # so "V. Soph." (Antiphon B44a, Critias B50, Hippias A2, Prodicus A1a) too.
     "V. soph.": w("Vitae Sophistarum", "opaque", "Book + chapter (+ section), or Kayser page."),
     "Vit. sophist.": w("Vitae Sophistarum", "opaque")},
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
add("HESYCH", "Hesychius", ["HESYCH.", "HES."],
    {"DEFAULT": w("Lexicon", "opaque", "Cited by lemma (s.v.). "
                  "2026-09-27: 'HES.' (Antiphon B43, mid-line after HARPOCR.'s own "
                  "'ἄβιος' entry, printing a second lemma 'ἄβιος' of his own) is DK's "
                  "short form of 'HESYCH.', not a separate abbreviation.")},
    flags=["cited-by-lemma"])
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
# 2026-09-26: bare "DIOGENES" is Diogenes Laertius when a book numeral and a
# section follow (Parmenides A1 "DIOGENES IX 21—23.", Xenophanes A2 "DIOGENES
# IX 21": D.L. 9.21-23, Ξενοφάνους δὲ διήκουσε Παρμενίδης ...); DK names
# Diogenes of Oenoanda in full ("DIOGENES v. Oinoanda", Democritus A50),
# which is his own variant below.
AMBIGUOUS_VARIANTS = {
    "DIOGENES": {
        "book-chapter": "DIOG_LAERT",  # a book numeral + section follows (Vitae Philosophorum)
    },
    "HEROD.": {
        "book-chapter": "HERODOT",   # a book numeral + chapter follows (Historiae)
        "greek-title": "HEROD_GRAMM",  # a Greek "π. ..." title follows (Herodian's works)
    },
}

# --- Aristotle (real) ---
# "ARISTOT," (comma for the period) is a slip in the source: Empedocles A78
# "ARISTOT, de anima Α 4. 408a 13" stands before De anima I 4, 408a13-23
# (ὁμοίως δὲ ἄτοπον καὶ <τὸ> τὸν λόγον τῆς μίξεως εἶναι τὴν ψυχήν ...), in DK's
# usual head form; it is the only "ARISTOT," in the 39 works (2026-09-26).
add("ARISTOT", "Aristotle", ["ARISTOT.", "ARIST.", "ARISTOTELES", "ARISTOT,"], dict(ARIST_WORKS), flags=[])

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
     # Not "in Metaphys. A": the key took Aristotle's book letter out of the
     # locus (Parmenides A7 "A 3. 984b 3 p. 31, 7 Hayd.", 2026-09-29).
     "in Metaphys.": w("in Aristotelis Metaphysica", "page-line"),
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
     "in Nic. p.": w("in Nicomachi Arithmeticam", "page-line"),
     # 2026-09-27: Leucippus A5, Pythagoras 7, 16, 17 "IAMBL. V. P. 104".
     "V. P.": w("De Vita Pythagorica", "section")},
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
# 2026-09-27: Empedocles A19 "SCHOL. IAMBLICH. V. P. p. 198 Nauck", a scholion on
# Iamblichus' De Vita Pythagorica at Nauck's page (St. Petersburg 1884); was split
# into a bare "SCHOL." and a separate Iamblichus head.
add("SCHOL_IAMBL", "Scholia in Iamblichum", ["SCHOL. IAMBLICH."], schol("Iamblichum"), flags=["scholia"])
CANON["SCHOL_IAMBL"]["works"]["V. P."] = w("De Vita Pythagorica", "opaque", "Nauck's page.")
add("SCHOL_BARE", "Scholia", ["SCHOL."],
    {"DEFAULT": w("Scholia", "opaque", "Bare 'SCHOL.' + target named in head (in Apoll. Rhod., in Euclid., ad Dionys.).", ital=False),
     "ad DIONYS.": w("Scholia in Dionysium Thracem", "page-line"),
     "in APOLL. RHOD.": w("Scholia in Apollonium Rhodium", "opaque"),
     "in Euclid. X": w("Scholia in Euclidem", "opaque")},
    flags=["scholia"])
add("GREGOR", "Gregory of Corinth", ["GREGOR. CORINTH.", "GREGOR."],
    {"DEFAULT": w("(ad Hermogenem)", "opaque", ital=False),
     # 2026-09-29: DK prints the title (Critias B16 "GREGOR. CORINTH. Zu
     # HERMOG. Β 445, 7 Rabe"), as "Zu Hesiod. Opp." is Proclus' in Hesiodum.
     "Zu HERMOG.": w("in Hermogenem", "opaque", "Critias B16; his commentary on Hermogenes.")},
    flags=["obscure"])
add("VITA_EUR", "Vita Euripidis", ["VITA"],
    {"EURIPID.": w("Vita Euripidis", "page-line", "'VITA EURIPID.' = anonymous Life of Euripides.", ital=False)},
    flags=["anonymous"])
add("ZOSIM", "Zosimus", ["ZOSIM."],
    {"DEFAULT": w("(work of Zosimus)", "opaque", ital=False),
     "V. Isocr.": w("Vita Isocratis", "page-line",
                    "2026-09-27: Hippias A3 'ZOSIM. V. Isocr. p. 253, 4 Westerm.', mid-line "
                    "after HARPOCR.'s own sentence, printing its own quotation of the same "
                    "family detail ('γυναῖκα δ' ἠγάγετο Πλαθάνην ...'). Zosimus (of Ascalon/"
                    "Gaza)'s Life of Isocrates, Westermann's Βιογράφοι (Vitarum Scriptorum "
                    "Graecorum Reliquiae, 1845) page, line.")},
    flags=[])

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
     "d. Lys.": w("De Lysia", "section",
                  "Gorgias A4 'vgl. DIONYS. d. Lys. 3' = Lys. 3 (Gorgias' style); the head was cut "
                  "after 'd.' (2026-09-26)."),
     "de comp. verb.": w("De Compositione Verborum", "section")},
    flags=["ambiguous-abbrev"])

# --- Demetrius ---
# 2026-09-26: DK's two DEMETR. heads name two Demetrii. With a title it is
# Demetrius Laco's De poematis (Democritus B298a); with a bare section number
# it is the De elocutione (Περὶ ἑρμηνείας) under Demetrius' name, cited by
# section: Heraclitus A4 "DEMETR. 192" = Eloc. 192 (Heraclitus' obscurity for
# want of connectives, after Eloc. 191 on clarity). "uncertain" now sits on
# De poematis alone, so B298a keeps its flags.
add("DEMETR", "Demetrius", ["DEMETR."],
    {"DEFAULT": w("De Elocutione", "section",
                  "Bare DEMETR. + section number = De elocutione (On Style); Heraclitus A4 'DEMETR. 192'."),
     "de poem.": w("De Poematis", "opaque", "Philodemus' work / Herculanean; Demetrius Laco. Flagged: attribution uncertain.",
                   flags=["uncertain"])},
    flags=[])

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
    {"DEFAULT": w("(Chronica / FGrHist 244)", "opaque", "Apollodorus of Athens, chronographer.", ital=False),
     # Grok content-check item 15, 2026-09-27: DK prints the Greek title
     # ("Περὶ θεῶν", Empedocles B41), distinct from the Chronica the bare
     # DEFAULT names; kept Greek, as printed (no Latin title on record). The
     # "bei Macrob. Sat. I 17, 46" note is the text that preserves it, same
     # apparatus convention as Dionysius of Alexandria's "bei Eus."
     "Περὶ θεῶν": w("Περὶ θεῶν", "opaque",
                    "Empedocles B41 'APOLLODOROS Περὶ θεῶν bei Macrob. Sat. I 17, 46'.",
                    ital=False, locus_as_printed=True)},
    flags=[])

# --- Diogenes of Oinoanda / Apollonia distinct from Laertius ---
add("DIOGENES_OIN", "Diogenes of Oenoanda", ["DIOGENES v. Oinoanda"],
    {"DEFAULT": w("Fragmenta (Inscriptio)", "opaque",
       "'DIOGENES v. Oinoanda' = Diogenes of Oinoanda (Epicurean inscription); NOT Diog. Laertius.", ital=False),
     "LAERTIUS": w("Vitae Philosophorum", "book-para",
       "Census splits 'DIOGENES LAERTIUS' as author='DIOGENES', work='LAERTIUS'; author here is Diogenes Laertius (= DIOG_LAERT), not Oinoanda.")},
    flags=["ambiguous-name"])

# --- Named individuals cited once (real authors) ---
add("ALCIDAMAS", "Alcidamas", ["ALCIDAMAS"],
    {"DEFAULT": w("(apud Aristotelem)", "opaque", "Cited via Arist. Rhet.", ital=False)}, flags=[])
add("ARISTOCLES", "Aristocles", ["ARISTOCLES"],
    {"DEFAULT": w("(fragmenta)", "opaque", ital=False),
     # Grok content-check item 43, 2026-09-27: DK prints the Greek title
     # ("Περὶ φιλοσοφίας η" -- Book Eta -- [EUS. XIV 17, 1]", Xenophanes A49);
     # no Latin title is on record for it, so the title stays Greek, as
     # printed, rather than invented (John's "don't invent Latin" rule). The
     # rest of the head is the locus, as printed.
     "Περὶ φιλοσοφίας": w("Περὶ φιλοσοφίας", "opaque",
                          "Xenophanes A49 'ARISTOCLES Περὶ φιλοσοφίας η [EUS. XIV 17, 1]'.",
                          ital=False, locus_as_printed=True)},
    flags=["obscure"])
add("MELAMPUS", "Melampus", ["MELAMPUS"],
    {"DEFAULT": w("(divinatory treatise)", "opaque", ital=False),
     # Grok content-check item 3, 2026-09-27: DK prints the Greek title
     # ("Περὶ παλμῶν", Antiphon B81a); kept Greek, as printed, same rule as
     # Aristocles and Apollodorus below.
     "Περὶ παλμῶν": w("Περὶ παλμῶν", "opaque",
                      "Antiphon B81a 'MELAMPUS Περὶ παλμῶν 18. 19 [Diels Beitr. z. Zuckungsl. I, "
                      "Abh. d. Berl. Ak. 1907]'.", ital=False, locus_as_printed=True)},
    flags=["obscure"])
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
# Excerpta and epigrams are collections, not authors (as the gnomologia and
# papyri): no author, the collection is the title (2026-09-29; had printed
# "Excerpta, (Excerpta) ASTRON. ..." and "Excerpta, Excerpta Vindobonensia").
add("EXC", None, ["EXC."],
    {"DEFAULT": w("(Excerpta)", "opaque", "'EXC. ASTRON.' = astronomical excerpts; 'EXC. VINDOB.' = Excerpta Vindobonensia.", ital=False),
     "ASTRON.": w("Excerpta Astronomica", "opaque",
        "Anaxagoras A87 'EXC. ASTRON. cod. Vatic. 381 [ed. Maass Aratea p. 143]': astronomical "
        "excerpts in cod. Vat. gr. 381, printed by E. Maass, Aratea (1892) p. 143."),
     "VINDOB.": w("Excerpta Vindobonensia", "opaque")},
    flags=["edition-keyed"])
add("EPIGR", None, ["EPIGR."],
    {"DEFAULT": w("Epigrammata Graeca", "opaque",
        "Gorgias A8 'EPIGR. 875a p. 534 Kaibel': G. Kaibel, Epigrammata Graeca ex lapidibus "
        "conlecta (Berlin 1878), no. 875a, p. 534 (was the placeholder '(epigram)').")},
    flags=["edition-keyed"])
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

# 2026-09-27: the reader printed "SUID:" bare (Heraclitus A1a opens its line
# with it, a colon for the period); DK quotes the entry, so the stage gives the
# headword after the colon as the locus (s.v.).
CANON["SUID"]["variants"].append("SUID:")

# 2026-09-27: title or author words the matched key left at the start of the
# locus ("Galen, De Elementis ex Hippocrate sec. Hipp. I 4").
CANON["GALEN"]["works"]["de elem. sec. Hipp."] = w("De Elementis ex Hippocrate", "opaque",
    "Democritus A49, Heraclitus A5: 'sec. Hipp.' (secundum Hippocratem) is the title's.")
CANON["GALEN"]["works"]["ad Hippocr. Epid. VI"] = w("in Hippocratis Epidemiarum librum VI", "opaque",
    "Empedocles B67 'ad Hippocr. Epid. VI 48 [XVII A p. 1002 K]', as 'in Epid. VI'.")
CANON["PS_GALEN"]["works"]["Hist. philos."] = w("Historia Philosopha", "section", "Leucippus A5.")
CANON["PS_GALEN"]["works"]["Hist. phil."] = w("Historia Philosopha", "section", "Xenophanes A35.")
CANON["ARISTID"]["works"]["Ars rhet."] = w("Ars Rhetorica", "opaque", "Critias B46.")
CANON["PSEUDODIONYS"]["works"]["Ars rhet."] = w("Ars Rhetorica", "opaque", "Critias B49.")
CANON["EUDOX"]["works"]["Ars astron."] = w("Ars Astronomica", "opaque", "Democritus B14; 'coll.' (column) + Blass page, as printed.",
                                          locus_as_printed=True)
CANON["HERACLIT_ALL"]["works"]["Alleg. Hom."] = w("Allegoriae Homericae", "opaque", "Xenophanes B31.")
CANON["HIEROCL"]["works"]["ad c. aur."] = w("in Aureum Carmen (Commentarius)", "opaque", "Empedocles B121, B158.")
CANON["LACTANT"]["works"]["Inst. div."] = w("Divinae Institutiones", "book-chapter-section", "Democritus A70, Empedocles A24.")
CANON["MENON"]["works"]["Anonymi Londin."] = w("Anonymus Londinensis (Iatrica)", "opaque",
    "Philolaus A27, A28; the bracket (Suppl. Arist. III 1) stays in the locus.")
CANON["PHOT"]["works"]["Bibl."] = w("Bibliotheca", "opaque",
    "Parmenides A4 'PHOT. Bibl. c. 249 p. 439a 36': codex + Bekker page; was given the Lexicon's title.")
CANON["PHOT"]["works"]["Lex."] = w("Lexicon", "opaque", "Democritus B144a 'PHOTIUS Lex. A S. 106, 23 Reitzenst.'.")
CANON["PHRYNICH"]["works"]["ecl."] = w("Ecloga", "section",
    "Hippias B10 'PHRYNICH. ecl. 312 Lob.': Lobeck's Phrynichi Eclogae (1820); was given the Praeparatio's title.")
CANON["SEXT"]["works"]["Pyrrh. h."] = w("Pyrrhoniae Hypotyposes", "book-para",
    "Democritus A134, Protagoras A14; was given Adversus Mathematicos.")
CANON["SEXT"]["works"]["Pyrrh. hypot."] = w("Pyrrhoniae Hypotyposes", "book-para", "Anaxagoras A97.")
CANON["TZETZ"]["works"]["ad Dion. Perieg."] = w("Scholia in Dionysium Periegetam", "opaque", "Xenophanes B41.")
CANON["SCHOL_APOLL"]["works"]["Rhod."] = w("Scholia in Apollonium Rhodium", "opaque",
    "Democritus B14 'RHOD. B 1098', A99 'Rhod. IV 269f. Wendel'.", ital=False)
CANON["SCHOL_BARE"]["works"]["ad DIONYS. Thrac."] = w("Scholia in Dionysium Thracem", "page-line", "Empedocles A25.")
CANON["THEOL_ARITHM"]["variants"].append("THEOLOG. Arithm.")  # Philolaus A12
CANON["CLEM"]["variants"].append("CLEM. AL.")  # Pythagoras 8
CANON["IOANN_LYD"]["variants"].append("JOH. LYDUS")  # Heraclitus A19
CANON["MALL"]["variants"] += ["MALL. THEODOR.", "MALLIUS THEODOR."]  # Critias B3, Democritus B16
CANON["MALL"]["works"]["de metr."] = w("De Metris", "opaque", "Keil, Grammatici Latini VI page, line.")
CANON["RUFUS"]["variants"].append("RUFUS Ephes.")  # Empedocles B70
CANON["RUFUS"]["works"]["d. nom. part. hom."] = w("De Nominatione Partium Hominis", "opaque", "Daremberg page.")

# 2026-09-27: Galen heads left as "(work of Galen)" or cut short, from a hand
# check of all 30 (titles as the dictionary's other commentaries on Hippocrates).
CANON["GALEN"]["works"].update({
    "de usu partt.": w("De Usu Partium", "opaque", "Democritus B34."),
    "comment. in Hippocr. de offic.": w("in Hippocratis De Officina Medici", "opaque", "Critias B39."),
    "in Hipp. de med. off.": w("in Hippocratis De Officina Medici", "opaque", "Antiphon B1, B2."),
    "in Hipp. d. nat. h.": w("in Hippocratis De Natura Hominis", "opaque", "Anaximenes A22."),
    "in Hipp. de nat. h.": w("in Hippocratis De Natura Hominis", "opaque", "Empedocles A43."),
    "in Hippocr. d. nat. hom.": w("in Hippocratis De Natura Hominis", "opaque", "Xenophanes A36."),
    "d. natur. facult.": w("De Naturalibus Facultatibus", "opaque", "Anaxagoras A104, as 'de virt. physic.'."),
    "Meth. med.": w("De Methodo Medendi", "opaque", "Empedocles A3."),
    "de medic. empir.": w("De Medicina Empirica", "opaque",
        "Democritus B125: Schöne's Greek fragment (Berl. Sitz. Ber. 1901), as printed.", locus_as_printed=True),
})
# Empedocles A78 opens "A o ET. V 22, 1 (D. 434)": the export's garble of AËT.
CANON["AET"]["variants"].append("A o ET.")

# "GAL. Hist. phil. 3 (D. 599)" (Anaxagoras A7) is the pseudo-Galen Historia.
CANON["PS_GALEN"]["variants"].append("GAL.")
CANON["PS_GALEN"]["variants_need_work"] = ["GAL."]

# 2026-09-27, second round (Grok sample check and the "(work of ...)" list):
# titles DK prints that fell to an author's placeholder title, and authors a
# column opens with that the dictionary did not know.
#
# "HIPP." names Hippolytus before his Refutatio and Hippocrates before a
# Hippocratic title (Democritus B11 "HIPP. de arte 11", Melissus A6 "HIPP. de
# nat. hom."); HIPP_SHARED stays only for a title neither has.
CANON["HIPPOL"]["variants"].append("HIPP.")
CANON["HIPPOL"]["variants_need_work"].append("HIPP.")
CANON["HIPPOCR"]["variants"].append("HIPP.")
CANON["HIPPOCR"]["variants_need_work"] = ["HIPP."]
CANON["HIPPOCR"]["works"].update({
    "de nat. hom.": w("De Natura Hominis", "section", "Melissus A6 'HIPP. de nat. hom. 1 [VI 34 L.]'."),
    "de nat. inf.": w("De Natura Pueri", "section",
        "Democritus A151 'HIPPOCR. de nat. inf. 31 (VII 540 L.)': Littré VII, the chapter on mules "
        "(Περὶ φύσιος παιδίου, De natura pueri)."),
})
# Papyri: the collection is the title and no author is printed (as Bekker's
# Anecdota, John's ruling 2026-09-24): "Herculaneum Papyrus 1788". The bare
# "PAP." / "PAPYR." entry stays for a collection DK does not name.
add("PAP_HERC", None, ["PAP. HERC.", "PAP. HERCUL.", "VOLL. HERC."],
    {"DEFAULT": w("Herculaneum Papyrus", "opaque",
        "Pythagoras 13, Leucippus B1a (P. Herc. 1788); Empedocles B142 'VOLL. HERC. N. 1012' "
        "(Volumina Herculanensia).", ital=False)}, flags=["edition-keyed"])
add("PAP_OXY", None, ["OXYRH.", "OXYRH. PAP.", "PAP. OXYRH."],
    {"DEFAULT": w("Oxyrhynchus Papyrus", "opaque",
        "Antiphon B44 'OXYRH. PAP. XI n. 1364', Empedocles B109a 'PAP. OXYRH. 1609 XIII 94', "
        "Xenophanes B21a 'OXYRH. 1087, 40'.", ital=False)}, flags=["edition-keyed"])
add("PAP_HIBEH", None, ["HIBEH PAPYR."],
    {"DEFAULT": w("Hibeh Papyrus", "opaque", "Democritus A99a.", ital=False)}, flags=["edition-keyed"])
add("PAP_LOND", None, ["PAPYR. LONDIN."],
    {"DEFAULT": w("London Papyrus", "opaque", "Democritus B300 20: P. Lond. 121 (PGM VII).", ital=False)},
    flags=["edition-keyed"])
add("PAP_LUGD", None, ["PAPYR. MAGIC. LUGD."],
    {"DEFAULT": w("Leiden Magical Papyrus", "opaque", "Democritus B300 21: P. Lugd. Bat. J 384 (PGM XII).",
        ital=False)}, flags=["edition-keyed"])
add("PAP_PETROP", None, ["PAPYR. PETROPOL."],
    {"DEFAULT": w("St Petersburg Papyrus", "opaque", "Hippias B19 (Jernstedt).", ital=False)},
    flags=["edition-keyed"])
for v in ("OXYRH.", "HIBEH"):
    CANON["PAP"]["variants"].remove(v)
# Authors a column opens with (they got no head).
CANON["ACHILL"]["variants"].append("ACHILL. Isag.")  # Anaxagoras A79, Leucippus B1, Xenophanes B28
add("LYSIAS", "Lysias", ["LYS."],
    {"DEFAULT": w("Orationes", "opaque", "Critias A11 'LYS. 12, 43': speech + section.")}, flags=[])
add("DIONYS_ALEX", "Dionysius of Alexandria", ["DIONYSIOS,", "DIONYS."],
    {"DEFAULT": w("De Natura", "opaque",
        "Democritus B118 'DIONYSIOS, bei Eus. P. E. XIV 27, 4', A43 'DIONYS. bei Eus. P. E. XIV 23, "
        "2. 3': the bishop's De natura, which Eusebius quotes (P. E. XIV 23-27); the 'bei' note is "
        "apparatus, as Herodian's.", locus_as_printed=True),
     "bei Eus. P. E.": w("De Natura", "opaque", locus_as_printed=True, locus_includes_work=True)}, flags=[])
CANON["DIONYS_ALEX"]["variants_need_work"] = ["DIONYS."]
CANON["PS_GALEN"]["variants"].append("[GALEN].")  # Democritus B124 "[GALEN]. d. defin. med."
add("VIT_HOMERI", None, ["VIT. HOMERI"],
    {"Rom.": w("Vita Homeri Romana", "opaque", "Hippias B18 'VIT. HOMERI Rom. p. 30, 27 Wil.'.")}, flags=[])
add("CLAUD_MAM", "Claudianus Mamertus", ["CLAUD. MAM."],
    {"DEFAULT": w("De Statu Animae", "opaque", "Philolaus B22 'CLAUD. MAM. II 3 p. 105, 5 Engelbr.'.")}, flags=[])
add("BOETH", "Boethius", ["BOËTHIUS"],
    {"Inst. mus.": w("De Institutione Musica", "opaque", "Philolaus A26 'BOËTHIUS Inst. mus. III 5 p. 276, 15 Friedl.'.")},
    flags=[])
# Titles that fell to "(work of ...)" / "(unspecified ...)".
CANON["PLUT"]["works"].update({
    "Sol.": w("Solon", "vita", "Thales A8, A11."),
    "Alex. fort.": w("De Alexandri Magni Fortuna aut Virtute", "moralia", "Pythagoras 18."),
    "Coni. praec.": w("Coniugalia Praecepta", "moralia", "Gorgias B8a."),
    "Conv. VII sap.": w("Septem Sapientium Convivium", "moralia", "Thales A21."),
    "Quaest. Rom.": w("Quaestiones Romanae", "moralia", "Empedocles A60."),
    "Reg. apophth.": w("Regum et Imperatorum Apophthegmata", "moralia", "Xenophanes A11."),
    "Symp.": w("Quaestiones Convivales", "moralia", "Anaximander A30, as 'Sympos.'."),
    "d. fac. in orb. lun.": w("De Facie in Orbe Lunae", "moralia", "Democritus A89a."),
    "d. prim. frig.": w("De Primo Frigido", "moralia", "Empedocles A69."),
    "def. orac.": w("De Defectu Oraculorum", "moralia", "Heraclitus A19."),
    "Animine an corp. aff.": w("Animine an Corporis Affectiones Sint Peiores", "moralia", "Democritus B149."),
    "de Isid.": w("De Iside et Osiride", "moralia", "Empedocles B115."),
    "de Is. et Os.": w("De Iside et Osiride", "moralia", "Empedocles B18, A3."),
    "de Is. et Osir.": w("De Iside et Osiride", "moralia", "Philolaus A14."),
    "quom. ad. poet. aud.": w("Quomodo Adulescens Poetas Audire Debeat", "moralia", "Empedocles A25."),
    "quomodo adul. poet. aud. deb.": w("Quomodo Adulescens Poetas Audire Debeat", "moralia", "Parmenides A15."),
    "aud. poet.": w("Quomodo Adulescens Poetas Audire Debeat", "moralia", "Xenophanes B34."),
    "de an. procr.": w("De Animae Procreatione in Timaeo", "moralia", "Empedocles A45."),
    "de genio Socr.": w("De Genio Socratis", "moralia", "Philolaus A4a."),
})
CANON["PS_PLUT"]["works"].update({
    "Cons. ad Apoll.": w("Consolatio ad Apollonium", "moralia", "Protagoras B9 '[PLUT.] Cons. ad Apoll.'."),
    "Stromat.": w("Stromateis", "opaque", "Empedocles A30 '[PLUT.] Stromat. ap. Eus. P. E. I 8, 10'."),
})
CANON["PS_PLUT"]["works"]["V. X orat."] = w("Vitae Decem Oratorum", "moralia", "Critias A16 '[Plut.] V. X orat. 1, 1 p. 832 DE'.")
CANON["PS_ARISTOT"]["works"].update({
    "de plantis": w("De Plantis", "bekker", "Anaxagoras A117."),
    "de plant.": w("De Plantis", "bekker", "Empedocles A70."),
    "de spiritu": w("De Spiritu", "bekker", "Empedocles A78."),
    "de Melisso Xenophane Gorgia": w("De Melisso Xenophane Gorgia", "opaque", "Xenophanes A28, the title in full."),
})
CANON["PHILOSTR"]["works"].update({
    "V. S.": w("Vitae Sophistarum", "opaque", "Gorgias A1, A1a, A24, B5b."),
    "V. Apoll.": w("Vita Apollonii", "opaque", "Anaxagoras A6, Democritus A19, Empedocles A14."),
    "V. Apoll. Tyan.": w("Vita Apollonii", "opaque", "Zeno A9."),
    "V. Ap.": w("Vita Apollonii", "opaque", "Empedocles A18."),
})
CANON["SENECA"]["works"].update({
    "Nat. qu.": w("Naturales Quaestiones", "opaque", "Also 'Nat. Qu.' (the match ignores case)."),
    "Nat. quaest.": w("Naturales Quaestiones", "opaque", "Also 'Nat. Quaest.'."),
})
CANON["PORPHYR"]["works"].update({
    "V. P.": w("Vita Pythagorae", "section", "Pythagoras 8, 13, 16."),
    "V. Pyth.": w("Vita Pythagorae", "section", "Pythagoras 8a, 9; Empedocles B129."),
    "de Styge": w("De Styge", "opaque", "Empedocles B105 'de Styge ap. Stob. Ecl. I 49, 53'."),
})
CANON["IAMBL"]["works"].update({
    "V. Pyth.": w("De Vita Pythagorica", "section", "Empedocles A15, B135; Parmenides A4."),
    "V. Pythag.": w("De Vita Pythagorica", "section", "Thales A11."),
    "Protr.": w("Protrepticus", "section", "Anaxagoras A48."),
    "Ep.": w("Epistulae", "opaque", "Antiphon B44a 'IAMBL. Ep. Περὶ ὁμονοίας [Stob. II 33, 15]'."),
    "in Nicom.": w("in Nicomachi Arithmeticam", "page-line", "Philolaus A24 'in Nicom. 118, 23 Pist.'."),
})
CANON["CIC"]["works"].update({
    "d. n. deor.": w("De Natura Deorum", "book-chapter-section", "Prodicus B5."),
    "d. nat. d.": w("De Natura Deorum", "book-chapter-section", "Anaximander A17."),
    "d. deor. n.": w("De Natura Deorum", "book-chapter-section", "Thales A23."),
    "de deor. nat.": w("De Natura Deorum", "book-chapter-section", "Democritus A74."),
    "de rp.": w("De Re Publica", "opaque", "Empedocles B135."),
    "de oratore": w("De Oratore", "book-chapter-section", "Empedocles A25."),
    "de inv.": w("De Inventione", "opaque", "Gorgias A26."),
})
CANON["PHILODEM"]["works"].update({
    "de poëm.": w("De Poematis", "opaque", "Antiphon B93."),
    "de adulat.": w("De Adulatione", "opaque", "Democritus B153."),
    "schol. Zenon. de lib. dic.": w("De Libertate Dicendi", "opaque",
        "Democritus A34: from Zeno's lectures (ἐκ τῶν Ζήνωνος σχολῶν); the locus ('VH1 V 2 fr. 20') "
        "as printed.", locus_as_printed=True),
    "de piet.": w("De Pietate", "opaque", "Democritus A75."),
    "de pietate": w("De Pietate", "opaque", "Empedocles A33."),
})
CANON["MACROB"]["works"].update({
    "S. Sc.": w("Commentarii in Somnium Scipionis", "book-chapter-section", "Parmenides A45."),
    "S. Scip.": w("Commentarii in Somnium Scipionis", "book-chapter-section", "Heraclitus A15, Philolaus A23, Xenophanes A50."),
    "Sat.": w("Saturnalia", "book-chapter-section", "Empedocles B90."),
})
CANON["AEL"]["works"].update({
    "Var. hist.": w("Varia Historia", "book-section", "Anaxagoras A21."),
    "Nat. anim.": w("De Natura Animalium", "book-section", "Empedocles B61."),
    "Hist. an.": w("De Natura Animalium", "book-section", "Empedocles A66 'AELIAN. Hist. an. IX 64'."),
})
# "AEL. PROMOT." (Democritus B300 10) is Aelius Promotus the physician, not
# Aelian; DK prints no title ("c. 26 [nach Marc. 295]").
add("AEL_PROMOT", "Aelius Promotus", ["AEL. PROMOT."],
    {"DEFAULT": w("(work of Aelius Promotus)", "opaque", "Chapter after cod. Marc. 295; no title printed.",
        ital=False)}, flags=[])
CANON["PHILO"]["works"].update({
    "d. opif.": w("De Opificio Mundi", "opaque", "Philolaus B20."),
    "quod omn. prob. lib.": w("Quod Omnis Probus Liber Sit", "opaque", "Zeno A18."),
    "de aetern. mundi": w("De Aeternitate Mundi", "opaque", "Empedocles B12."),
})
add("PHILO_BYBL", "Philo of Byblos", ["PHILO BYBL."],
    {"DEFAULT": w("Historia Phoenicia", "opaque",
        "Democritus B300 16 'PHILO BYBL. b. Eus. P. E. I 10, 53': the Phoenician History, which "
        "Eusebius quotes (P. E. I 9-10); the locus is Eusebius', as printed.", locus_as_printed=True)}, flags=[])
CANON["DIONYS_HAL"]["works"].update({
    "Halic. Isocr.": w("De Isocrate", "section", "Prodicus A7 'DIONYS. Halic. Isocr. 1'."),
    "Isae.": w("De Isaeo", "section", "Gorgias A32."),
})
CANON["EUSTATH"]["works"]["Z. DIONYS. Per."] = w("Commentarii in Dionysium Periegetam", "section",
    "Hippias B8 'EUSTATH. Z. DIONYS. Per. 270': on the verse of Dionysius Periegetes (was split into "
    "two heads, the second read as Dionysius of Halicarnassus).", ital=False)
CANON["EUSEB"]["works"]["P. E."] = w("Praeparatio Evangelica", "book-chapter-section",
    "Anaximander A4, Empedocles A8, Protagoras B4.")
CANON["VARRO"]["works"].update({
    "de r. rust.": w("De Re Rustica", "book-chapter-section", "Democritus B26f."),
    "Sat.": w("Saturae Menippeae", "opaque", "Democritus A161 'VARRO Sat. Cycnus'."),
    "Eumenid. sat.": w("Saturae Menippeae (Eumenides)", "opaque", "Empedocles A72."),
})
CANON["PSELL"]["works"].update({
    "d. omnif. doctr.": w("De Omnifaria Doctrina", "section", "Anaxagoras A101a."),
    "de lapid.": w("De Lapidum Virtutibus", "opaque", "Empedocles A89."),
})
CANON["THEOPHR"]["works"].update({
    "d. ign.": w("De Igne", "section", "Democritus A73."),
    "fr.": w("Fragmenta", "opaque", "Democritus A155b 'THEOPHRAST. fr. 171, 12 W.' (Wimmer)."),
})
CANON["TERTULL"]["works"].update({
    "ad nat.": w("Ad Nationes", "book-section", "Democritus A74."),
    "de an.": w("De Anima", "section", "Democritus A160."),
})
CANON["TZETZ"]["works"].update({
    "Chil.": w("Chiliades", "opaque", "Leucippus A5."),
    "Exeg. Iliad.": w("Exegesis in Iliadem", "opaque", "Empedocles A66."),
})
CANON["THEMIST"]["works"]["Phys."] = w("in Aristotelis Physica Paraphrasis", "page-line", "Antiphon B13.")
CANON["LUCIAN"]["works"]["V. hist."] = w("Verae Historiae", "book-section", "Antiphon A7.")
CANON["PTOLEM"]["works"]["Apparit."] = w("Phaseis", "opaque",
    "Democritus B14 'PTOLEM. Apparit. epileg. ebenda p. 275, 1': the epilogue of the Phaseis "
    "(Φάσεις ἀπλανῶν ἀστέρων), Heiberg's page, as printed.", locus_as_printed=True)
CANON["ALEX"]["works"].update({
    "Top.": w("in Aristotelis Topica", "page-line", "Democritus A117."),
    "in meteor.": w("in Aristotelis Meteorologica", "page-line", "Anaxagoras A90."),
    "zu Arist. Meteor.": w("in Aristotelis Meteorologica", "page-line", "Democritus A92."),
    "de fato": w("De Fato", "opaque", "Anaxagoras A66."),
    "de sensu": w("in Aristotelis De Sensu", "page-line", "Leucippus A29."),
    "in Metaph. z. d. St.": w("in Aristotelis Metaphysica", "page-line", "Leucippus A6."),
    "q. f. problem.": w("Problemata", "opaque", "Empedocles B101: 'q. f.' (quae fertur), the Problemata under his name."),
})
CANON["PHILOP"]["works"].update({
    "Phys.": w("in Aristotelis Physica", "page-line", "Xenophanes A29, Zeno A21."),
    "in Phys.": w("in Aristotelis Physica", "page-line", "Parmenides A21."),
    "de an. prooem.": w("in Aristotelis De Anima", "page-line", "Critias A23: the preface, CAG page."),
})
CANON["OLYMPIOD"]["works"].update({
    "IN PLAT. Gorg.": w("in Platonis Gorgiam", "opaque", "Gorgias A10, B2."),
    "in Plat. Phileb.2": w("in Platonis Philebum", "opaque",
        "Democritus B142: the export fuses a note figure to the title ('Phileb.2')."),
    "de arte sacra": w("De Arte Sacra", "opaque", "Melissus A13."),
    "de arte sacr.": w("De Arte Sacra", "opaque", "Xenophanes A36."),
})
CANON["PROCL"]["works"].update({
    "Vit. Hom.": w("Vita Homeri", "opaque", "Gorgias B25 (Chrestomathia)."),
    "Zu Hesiod. Opp.": w("in Hesiodi Opera et Dies", "section", "Xenophanes A22."),
})
CANON["SIMPL"]["works"]["Cat."] = w("in Aristotelis Categorias", "page-line", "Heraclitus A22.")
CANON["ARISTOT"]["works"].update({
    "Hist. anim.": w("Historia Animalium", "bekker", "Democritus B126."),
    "q. f. de Melisso Xenophane Gorgia": w("De Melisso Xenophane Gorgia", "opaque",
        "Melissus A5: 'q. f.' (quae fertur), the treatise under Aristotle's name."),
})
CANON["PLATO"]["works"]["Hipp. m."] = w("Hippias Maior", "stephanus", "Anaxagoras A13.")
CANON["LACTANT"]["works"]["de opif."] = w("De Opificio Dei", "book-chapter-section",
    "Parmenides A54 'LACTANT. de opif. 12, 12' (was given the Institutiones).")
CANON["LACTANT"]["works"]["de opif. dei"] = w("De Opificio Dei", "book-chapter-section", "Empedocles A51.")
CANON["ORIG"]["works"]["c. Celsum"] = w("Contra Celsum", "book-para",
    "Empedocles B137 'ORIG. c. Celsum v 49' (the title fell into the locus).")
CANON["IAMBL"]["variants"].append("Iambl.")  # Pythagoras 13 "Μουσεῖον. Iambl. V. P. 170", 14 "Vgl. Iambl. V. P. 260"

# 2026-09-27, third round (Grok check; the second round's leftovers).
# The letter's title and Stobaeus' place are the locus, as printed: "IAMBL.
# Ep. Περὶ ὁμονοίας [Stob. II 33, 15]" (Antiphon B44a).
CANON["IAMBL"]["works"]["Ep."]["locus_as_printed"] = True
# Spanheim's page and columns, as printed: "IULIAN. Ep. 201 B.—C." (Democritus A20).
CANON["IULIAN"]["works"]["Ep."]["locus_as_printed"] = True
# Xenophanes B45 "SCHOL. HIPPOCR. ad Epid. I 13, 3 [Nachmanson, Erotian. p. 102,
# 19]": a scholion on Epidemics I 13, 3, at Nachmanson's Erotian page (as
# SCHOL. IAMBLICH. V. P.: the title is the commented work's).
CANON["SCHOL_HIPPOCR"]["works"]["ad Epid."] = w("Epidemiae", "opaque", "Xenophanes B45.")
# Democritus B307 "PSEUDORIBASIUS in Aphorism. Hippocr. ed. Io. Guinterius
# Andernacus Paris. 1533f. 5 v": the edition and its leaf are the locus.
CANON["PSEUDORIB"]["works"]["in Aphorism. Hippocr."] = w("in Aphorismos Hippocratis", "opaque", "Democritus B307.")
# Parmenides B1 "28—32 SIMPL. d. cael. 557, 20".
CANON["SIMPL"]["works"]["d. cael."] = w("in Aristotelis De Caelo", "page-line", "Parmenides B1.")
# Parmenides B7 "50—61 SIbmPL. Phys. 38, 28": the export's garble of SIMPL.
# "Simpl." in mixed case opens a source after a sentence (Anaximander A17
# "κόσμον. Simpl. Phys. 1121, 5", Democritus A165) only before a title;
# elsewhere it is a note inside a citation ("EUDEM. bei Simpl. Phys. 143, 4").
CANON["SIMPL"]["variants"] += ["SIbmPL.", "Simpl."]
CANON["SIMPL"]["variants_need_work"] = ["Simpl."]
# Empedocles A83 "ORIBASIUS aus Athenaios III 78, 13 [Diokles fr. 175 Wellm.]":
# the Collectiones Medicae, Bussemaker-Daremberg vol. III page 78, line 13, a
# passage Oribasius took from Athenaeus of Attalia; the "aus" note stays in the
# locus as printed, as Dionysius' "bei Eus." (German in the English: John's call).
add("ORIBAS", "Oribasius", ["ORIBASIUS"],
    {"DEFAULT": w("Collectiones Medicae", "opaque", "Empedocles A83."),
     "aus Athenaios": w("Collectiones Medicae", "opaque", "Empedocles A83.",
        locus_as_printed=True, locus_includes_work=True)}, flags=[])

# 2026-09-28 (Grok check of 150 heads): heads whose English was empty because
# the dictionary lacked the work, each read from its own column.
# Dash titles memo §5 had left out until someone read the columns (now
# stage1's _DASH_WORK_EXCLUDED is empty): each follows a head of that author.
CANON["GALEN"]["works"]["de differ. puls."] = w("De Differentia Pulsuum", "opaque",
    "Democritus B126 '—de differ. puls. I 25 [VIII 551 K]' after 'GALEN. de medic. empir.' (Kühn VIII 551).")
CANON["PHILO"]["works"]["de vita contempl."] = w("De Vita Contemplativa", "opaque",
    "Democritus A15 '—de vita contempl. p. 473 M. (VI 49 C.—W.)' after 'PHILO de prov.' (Mangey's page, "
    "Cohn-Wendland's volume).")
CANON["THEOPHR"]["works"].update({
    "de odor.": w("De Odoribus", "section", "Democritus A133 '—de odor. 64' after THEOPHR. d. c. pl."),
    "de vertig.": w("De Vertigine", "section", "Heraclitus B125 '—de vertig. 9' after 'THEOPHR. Metaphys.'."),
})
CANON["PROCL"]["works"]["in Hes. Opp."] = w("in Hesiodi Opera et Dies", "section",
    "Gorgias B26 '—in Hes. Opp. 758' after 'PROCL. Vit. Hom.' (the title of 'Zu Hesiod. Opp.').")
# Titles printed with an author the dictionary had, not yet keys.
CANON["HIEROCL"]["works"]["in Pyth. c. aur."] = w("in Aureum Carmen (Commentarius)", "opaque",
    "Democritus B142 'HIEROCL. in Pyth. c. aur. 25' (as 'ad c. aur.').")
CANON["APUL"]["works"]["Apol."] = w("Apologia", "section", "Democritus B300 12 'APUL. Apol. 27'.")
CANON["CAELIUS"]["works"]["Acut. morb."] = w("De Morbis Acutis", "opaque",
    "Democritus A28 'CAELIUS AUREL. Acut. morb. II 37' (Celerum Passionum), beside his 'Morb. chron.'.")
# DK prints no title: the work is the author's only one cited in DK.
CANON["MARC_ANT"]["works"]["DEFAULT"] = w("Ad Se Ipsum (Meditationes)", "book-section",
    "Heraclitus B76 'MARC. IV 46' (the passage B71 cites as 'MARC. ANTON. IV 46').")
CANON["ANATOL"]["works"]["DEFAULT"] = w("De Decade", "page-line",
    "Parmenides A44 'ANATOL. p. 30 Heib.' (Heiberg's pages, as 'de decade p. 35 Heiberg', Philolaus B20).")
# "EUDEM. bei Simpl. Phys. 143, 4" (Parmenides B7): Eudemus as Simplicius
# quotes him; DK prints no title, so none is given -- the "bei" note alone,
# as printed ("Eudemus of Rhodes, bei Simpl. Phys. 143, 4").
CANON["EUDEM"]["works"]["bei Simpl. Phys."] = w("", "opaque", "Parmenides B7.",
    locus_as_printed=True, locus_includes_work=True)
# "APOLLON. mir. 6" (Pythagoras 7) is Apollonius the paradoxographer, not
# Apollonius Dyscolus, whose "APOLLON. de pronom." shares the spelling: the
# variant names him only before his title (as pseudo-Galen's "GAL.").
add("APOLLON_PARADOX", "Apollonius Paradoxographus", ["APOLLON."],
    {"mir.": w("Historiae Mirabiles", "section", "Pythagoras 7 'APOLLON. mir. 6'.")}, flags=[])
CANON["APOLLON_PARADOX"]["variants_need_work"] = ["APOLLON."]

# 2026-09-29, second round: John's rulings of the same day.
# (1) Bekker's Anecdota Graeca keeps its title with no author, and "Bekk."
# follows the locus as apparatus, as the gnomologia print "Sternb." Lex. VI
# is the part DK names even where it prints only "VI" (Antiphon B19 "AN.
# BEKK. VI 403, 5": Bekker has three volumes, so VI is no volume) or "LEX."
# in capitals (Democritus B122); the text of both is in the TLG Synagoge
# (4289.005), whose edition gives no Bekker page.
for _key in ("ANECD_BEKK", "ANTIATT_BEKK"):
    for _work in CANON[_key]["works"].values():
        _work["edition_note"] = "Bekk."
CANON["ANECD_BEKK"]["works"]["DEFAULT"]["volume_by_part"] = [["Lex. VI", 319, 476, "I", ["VI"]]]
# (2) Where DK prints no title, the title the TLG confirms: the passage DK
# quotes found in that work at that place.
# "z. d. St." (zu der Stelle), "dazu", "ad h. c." (on this passage), and
# Democritus A68's bare "SIMPL. p. 330, 14" after "Vgl. zu 196b 14": the
# commentator's work on the Aristotle or Plato passage cited above. Each
# checked in the TLG: Simplicius in Phys. (4013.004) 460 (Anaxagoras A45),
# 1318-19 (Democritus A58), 330 (A68), 138 (Zeno A22); in de caelo
# (4013.001) 119 (Anaxagoras A73), 511 (A88), 583 (Leucippus A16); in de
# anima (4013.005) 202 (Empedocles B108); Alexander in Meteor. (0732.008)
# 67 (Anaximander A27), 37 (Democritus A91); in de sensu (0732.007) 23
# (Empedocles B84); in Top. (0732.006) 181 (Prodicus A19); Philoponus in de
# anima (4015.008) 83 (Democritus A101), 486 (Empedocles B108); in GC
# (4015.006) 160 (Empedocles A87); Olympiodorus in Gorg. (4019.005) 4, 9
# (Gorgias A27; the TLG has Westerink's lectures, not Jahn's pages).
CANON["SIMPL"]["works"]["de anima"] = w("in Aristotelis De Anima", "page-line",
    "Empedocles B108 'SIMPL. z. d. St. 202, 30' on De anima 427a 24; TLG 4013.005, CAG XI "
    "(the TLG marks it '[Sp.?]', perhaps Priscian of Lydia; DK gives it to Simplicius).")
_ON_PASSAGE = {
    "SIMPL": ({"ARISTOT:Physica": "Phys.", "ARISTOT:De Caelo": "de caelo", "ARISTOT:De Anima": "de anima"},
              ["z. d. St.", "dazu"]),
    "ALEX": ({"ARISTOT:Meteorologica": "in meteor.", "ARISTOT:De Sensu": "de sensu",
              "ARISTOT:Topica": "Top."}, ["z. d. St."]),
    "PHILOP": ({"ARISTOT:De Anima": "de anima",
                "ARISTOT:De Generatione et Corruptione": "de gen. et corr."}, ["z. d. St.", "ad h. c."]),
    "OLYMPIOD": ({"PLATO:Gorgias": "IN PLAT. Gorg."}, ["z. d. St."]),
}
for _key, (_table, _markers) in _ON_PASSAGE.items():
    _default = CANON[_key]["works"]["DEFAULT"]
    for _marker in _markers:
        CANON[_key]["works"][_marker] = w(_default["title"], "page-line", ital=False,
            locus_includes_work=True, on_passage_above=_table)
CANON["SIMPL"]["works"]["DEFAULT"]["on_passage_above"] = _ON_PASSAGE["SIMPL"][0]
# Titles found by page: Galen's Kühn page (Democritus A46 "GALEN. VIII 931 K.":
# TLG 0057.060, Kühn VIII 931) and CMG page (Melissus A6 "GAL. CMG V 9, 1, 17,
# 16": TLG 0057.085, Kühn XV 29), Aristotle's Bekker page (Xenophanes A13
# "ARIST. B 26. 1400b 5": TLG 0086.038, 1400b). Each key is the place as
# printed and stays in the locus.
CANON["GALEN"]["works"]["VIII 931"] = w("De Dignoscendis Pulsibus", "opaque",
    "Democritus A46; TLG 0057.060, Kühn VIII 931.", locus_includes_work=True)
CANON["GALEN"]["works"]["CMG V 9, 1,"] = w("in Hippocratis De Natura Hominis", "opaque",
    "Melissus A6 'GAL. CMG V 9, 1, 17, 16'; TLG 0057.085, Kühn XV 29.", locus_includes_work=True)
CANON["ARISTOT"]["works"]["B 26. 1400b"] = w("Rhetorica", "bekker",
    "Xenophanes A13 'ARIST. B 26. 1400b 5'; TLG 0086.038, Bekker 1400b.", locus_includes_work=True)
# The quoting text names the work: Diogenes Laertius VIII 58 (TLG 0004.001)
# "Ἀπολλόδωρος ἐν Χρονικοῖς (FGrH 244 F 33)" (Gorgias A10); Theon of Smyrna
# p. 198 Hiller (TLG 1724.001) says Dercyllides wrote it "ἐν τῷ περὶ τοῦ
# ἀτράκτου καὶ τῶν σφονδύλων τῶν ἐν τῇ Πολιτείᾳ παρὰ Πλάτωνι λεγομένων"
# (Thales A17). Greek titles with no Latin one on record stay Greek.
CANON["APOLLODOR"]["works"]["DEFAULT"] = w("Chronica", "opaque",
    "Gorgias A10; D.L. VIII 58 names the Chronica (FGrHist 244 F 33).")
_DERCYLL_TITLE = "Περὶ τοῦ ἀτράκτου καὶ τῶν σφονδύλων τῶν ἐν τῇ Πολιτείᾳ παρὰ Πλάτωνι λεγομένων"
CANON["DERCYLL"]["works"]["DEFAULT"] = w(_DERCYLL_TITLE, "opaque",
    "Thales A17; Theon names the book at p. 198 Hiller.", ital=False)
# Theon's place, as printed (the DEFAULT locus stopped at "astr.").
CANON["DERCYLL"]["works"]["ap. Theon."] = w(_DERCYLL_TITLE, "opaque",
    "Thales A17 'DERCYLLIDES ap. Theon. astr. 198, 14 H.'.", ital=False,
    locus_as_printed=True, locus_includes_work=True)
# In the TLG under their own author: Suetonius (1760.001, section 4;
# Parmenides B24), the anonymous prolegomena to Aratus in cod. Paris. suppl.
# gr. 607A, which Treu printed (4161.006, section 14 = Maass's Isag. II 14;
# Parmenides A40), Athanasius' prolegomena to Hermogenes (4238.001, Rabe p.
# 180; Gorgias B5a, "Alexandr." his city), Sopater's Διαίρεσις ζητημάτων
# (2031.001, Walz VIII 23; Gorgias B31), Menander Rhetor's first treatise
# (2586.001, Spengel pp. 333 and 337; Empedocles A23, "I" = treatise I).
CANON["SUETONIUS"]["works"]["DEFAULT"] = w("Περὶ βλασφημιῶν καὶ πόθεν ἑκάστη", "opaque",
    "Parmenides B24 'SUETONIUS (Miller Mél. 417)'; TLG 1760.001, section 4.", ital=False)
CANON["ANON_BYZANT"]["works"]["DEFAULT"] = w("Prolegomena in Aratum", "opaque",
    "Parmenides A40; TLG 4161.006 (e cod. Paris. suppl. gr. 607A), section 14.")
CANON["ATHANASIUS"]["variants"].insert(0, "ATHANASIUS Alexandr.")
CANON["ATHANASIUS"]["works"]["DEFAULT"] = w("Prolegomena in Hermogenis Librum περὶ στάσεων", "opaque",
    "Gorgias B5a 'ATHANASIUS Alexandr. Rhet. Gr. XIV, 180, 9 Rabe'; TLG 4238.001, Rabe p. 180.")
CANON["SOPAT"]["works"]["Rhet."] = w("Διαίρεσις ζητημάτων", "opaque",
    "Gorgias B31 'SOPAT. Rhet. gr. VIII 23 W.'; TLG 2031.001, Walz VIII p. 23 (Rhetores Graeci, "
    "kept in the locus).", ital=False, locus_includes_work=True)
CANON["MENANDER"]["works"]["DEFAULT"] = w("Διαίρεσις τῶν ἐπιδεικτικῶν", "book-chapter-section",
    "Empedocles A23 'MENANDER I 2, 2', 'Ebenda 5, 2'; TLG 2586.001, Spengel pp. 333, 337.", ital=False)
# (3) A number that names the work: the TLG work list (Isocrates 0010.019
# Antidosis = orat. 15, 0010.009 Helenae encomium = orat. 10; Andocides
# 0027.001 De mysteriis = orat. 1; [Demosthenes] 0014.058 In Theocrinem =
# orat. 58), each passage found there. The number stays in the locus;
# `numbered`: after a head of the author, numbers opening with it name the
# work too (Gorgias B1 "ISOCR. 10, 3 ... 15, 268", the Antidosis, TLG 268).
_NUM = dict(locus_includes_work=True, numbered=True)
CANON["ISOCR"]["works"].update({
    "XV": w("Antidosis", "section", "Anaxagoras A15 'ISOCR. XV 235'.", **_NUM),
    "15,": w("Antidosis", "section", "Gorgias A18 'ISOCR. 15, 155f.', Gorgias B1 '15, 268'.", **_NUM),
    "10,": w("Helenae Encomium", "section", "Gorgias B1 'ISOCR. 10, 3'.", **_NUM),
})
CANON["ANDOC"]["works"]["I"] = w("De Mysteriis", "section", "Critias A5 'ANDOC. I 47'.", **_NUM)
CANON["PS_DEMOSTH"]["works"]["58,"] = w("In Theocrinem", "section", "Critias A6 '[DEMOSTH.] 58, 67'.", **_NUM)
# Thales A11a "HIMER. 30 Cod. Neap.": the TLG (Colonna, 2051.001) has the
# passage in oration 28, Εἰς Ἀθήναιον κόμητα; its oration 30 is another speech,
# so DK's number (another numbering; DK cites the Naples codex after
# Schenkl) gives no title. The
# collection is named, DK's number kept.
CANON["HIMER"]["works"]["DEFAULT"] = w("Declamationes et Orationes", "opaque",
    "Thales A11a; TLG 2051.001, Colonna's oration 28.")
# (4) Protagoras B2 "PORPHYR. ἀπὸ τοῦ α τῆς Φιλολόγου ἀκροάσεως b. Eus. P. E.
# X 3, 25": Eusebius heads P. E. X 3 (TLG 2018.001) "ἀπὸ τοῦ πρώτου τῆς
# Φιλολόγου ἀκροάσεως". Greek, in the nominative (no Latin title on
# record); book I before the locus; Eusebius' place is apparatus.
CANON["PORPHYR"]["works"]["ἀπὸ τοῦ α τῆς Φιλολόγου ἀκροάσεως"] = w("Φιλόλογος ἀκρόασις", "opaque",
    "Protagoras B2; Eusebius, P. E. X 3 (TLG 2018.001) quotes book I.", ital=False,
    locus_as_printed=True, locus_prefix="I")

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
        if v in e.get("variants_need_work", []) and vv in resolver:
            continue  # names this author only before his titles ("GAL. Hist. phil.")
        if vv in resolver and v not in CANON[resolver[vv]].get("variants_need_work", []):
            print("DUP VARIANT:", v, "->", resolver[vv], "and", key, file=sys.stderr)
        resolver[vv] = key  # a plain variant outranks one that needs a title ("HIPP.")
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

# 2026-09-27, fifth round (John's review: title-abbreviation leftovers +
# Suda/author redundancy):
#
# The DEFAULT title is already Pliny's/Gellius's own work, so a printed
# title-abbreviation spelling that has no key falls through to DEFAULT with
# its words stuck at the front of the locus: "PLIN. H. n. XXXIV 21" ->
# "Naturalis Historia H. n. XXXIV 21" (heraclitus-testimonia A3a); "PLIN. N.
# HIST. II 14" -> "Naturalis Historia N. HIST. II 14" (democritus-testimonia
# A76) -- the DEFAULT note already claimed 'N. H.'/'N. HIST.' both work, but
# only 'N. H.' was a key. "GELLIUS N. A. III 11" (xenophanes-fragments B13)
# is the same gap for Noctes Atticae. Each spelling gets its own key to the
# same title/template so the abbreviation is consumed, not left in the locus.
CANON["PLIN"]["works"]["N. HIST."] = w("Naturalis Historia", "book-para")
CANON["PLIN"]["works"]["H. N."] = w("Naturalis Historia", "book-para",
    "Heraclitus A3a 'PLIN. H. n. XXXIV 21' (lower-case 'n.'; match_work casefolds).")
CANON["GELL"]["works"]["N. A."] = w("Noctes Atticae", "book-chapter-section",
    "Xenophanes B13 'GELLIUS N. A. III 11'.")

# The Suda is cited by its own name, not by a person's -- "Suda" is already
# the title, so a separate work title only repeats it ("Suda, Lexicon
# (Suda)"). Hesychius and Harpocration, whose lexica are real titled works
# distinct from their names, keep a title ("Hesychius, Lexicon"); the Suda's
# own scholarly citation form has none: "Suda, s.v. <word>". `bare_title`
# (stage1_citation_expansion._entry) supplies "Lexicon" only when a head
# carries no locus at all (a bare "SUID."/"SUIDAS"), so that case still reads
# "Suda, Lexicon" instead of a dangling "Suda,".
CANON["SUID"]["works"]["DEFAULT"] = w("", "opaque",
    "The Suda is cited by its own name, not an author's; title left empty so "
    "the printed form is 'Suda, s.v. <word>', matching how Hesychius/"
    "Harpocration cite their (real, separately-named) lexica. `bare_title` "
    "covers the headword-less heads (italic, as Hesychius' 'Lexicon' is).",
    bare_title="Lexicon")
CANON["PS_SUID"]["works"]["DEFAULT"] = w("", "opaque",
    "Bracketed = editorial supplement; same non-repeating title as SUID.",
    bare_title="Lexicon")

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
            "volume_by_part": "[[part, first page, last page, volume, [other printed forms]?], ...]: an "
                              "edition in volumes that each start at p. 1. A locus opening with a listed "
                              "part (in any case, or one of its other printed forms) whose page lies in it "
                              "gets that volume, printed first, with the part as listed ('I, Lex. VI p. "
                              "418, 6'); else a volume numeral the head prints; else the head stays as printed",
            "numbered": "true: the key is a number that names the work (an orator's speech, 'ISOCR. "
                        "XV 235'); numbers after a dash that open with it name the work too",
            "edition_note": "printed after the locus as apparatus: the editor whose pages the locus "
                            "gives ('Bekk.' for Bekker's Anecdota Graeca, John's ruling 2026-09-29)",
            "on_passage_above": "{'<author key>:<title>': work key}: DK's 'z. d. St.' (zu der Stelle, on "
                                "this passage) names the commentator's work on the passage cited above; the "
                                "stage takes the first head above that is no commentary and, when its work is "
                                "listed, prints that commentary's title, the marker left out of the locus. "
                                "Nothing listed: the head keeps its placeholder, marker and all",
            "locus_prefix": "printed before the locus (the lexicon a head names in its author slot)",
            "locus_as_printed": "true: the locus is everything the head prints after the title, untrimmed; "
                                "a 'bei <author> ...' note (the text that preserves the passage) is apparatus "
                                "and the locus is then empty",
            "editor_apparatus": "true: the locus is only the numbers (codex, saying, book); the editor or "
                                "edition DK names with it ('ed. Sternbach', 'Sternb.', a bracket) is apparatus, "
                                "as printed",
            "bare_title": "the title to print instead when the head resolves to no locus at all (a bare "
                          "abbreviation with nothing after it): lets `title` stay empty for a work cited by "
                          "its own name, not an author's (the Suda), without leaving a dangling 'Author,' "
                          "when there is no locus to follow it",
            "flags": "per-work flags, added after the author's (DEMETR. 'de poem.': 'uncertain')",
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
