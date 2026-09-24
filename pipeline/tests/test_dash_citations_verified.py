"""Check the citation stage's filled-in DK dashes against the TLG/PHI (John's
ruling, 2026-09-24: before an expanded dash citation goes live, check it
against the source text).

The stage runs over all 39 DK fragment/testimonia spines as a dry run (as
test_citation_dash_oracle.py does -- manifests untouched; only Heraclitus
fragments is opted in for real). Every dash it fills in becomes a reading for
pipeline/tools/verify_dash_citations.py, which looks for the passage DK
prints after the dash in the source author's own text. The test fails on any
MISMATCH, NOT-FOUND or NOT-CHECKED (item 1, 2026-09-24: a reading the check
could not even attempt does not ship on a guess either) that John's rulings
in sources/dk-citations/dash-adjudications.json do not cover (a source that
is in the TLG/PHI must be verified before it ships live) -- "covered" means
an adjudication entry exists for that exact printed head (work + segment +
head, matched exactly as the stage's own _same_head does). Readings the
machine cannot reach at all (NOT-IN-CORPUS, SCHEME-UNMAPPED) ship by a
separate ruling and never fail this test; CONFIRMED-PARTIAL and WEAK
(pipeline/tools/verify_dash_citations.py, defect 4) are lesser-confidence
confirmations and fail it only when another place in the text has as much
evidence (their "also", review item 8), unless ruled. Lexicon dashes ("s.v.
<headword>") are checked against the lexicon's entries (item 7). A direct
head whose author the stage inferred from an ambiguous abbreviation ("HEROD.
II 123" = Herodotus, flag author-inferred) is checked too, and a Herodotus
reading so inferred, direct or dash, must carry the literal verdict
CONFIRMED (item 3, tightened 2026-09-24: WEAK and CONFIRMED-PARTIAL are not
enough for an inferred author either) -- any other verdict fails it unless
ruled (Sol review finding 3). Coverage:
  - a reading or correction ruled for that head (John located it himself),
    or a pending ruling (reading: null) -- the stage then keeps the head
    verbatim, so it never reaches these results at all;
  - the "_as_printed" rule for Clement's Stromateis: DK's own section
    numbers stand, so a near miss in the same book is accepted.

Inputs are gitignored build data: build/dk-spines/, build/dk-dash-survey/
survey.json (for the passage each dash stands before), and the verifier's
Diogenes export cache build/dash-verify/cache/ (or the TLG/PHI corpus and
Diogenes, to make it). The test skips cleanly when they are absent (same
pattern as test_citation_dash_oracle.py's `requires_data`). Run this file
directly to print the verdict counts and every mismatch/not-found.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "pipeline" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_citation_dash_oracle as oracle  # noqa: E402
import verify_dash_citations as verifier  # noqa: E402
from reader_pipeline import stage1_citation_expansion as ce  # noqa: E402
from reader_pipeline.config import Manifest  # noqa: E402

CACHE = ROOT / "build" / "dash-verify" / "cache"
ADJUDICATIONS = ROOT / "sources" / "dk-citations" / "dash-adjudications.json"

requires_corpus = pytest.mark.skipif(
    not (oracle.SPINES.is_dir() and oracle.SURVEY.exists()
         and (CACHE.is_dir() or (verifier.CORPUS_ROOT.is_dir() and verifier.DIOGENES.is_dir()))),
    reason="build/dk-spines/, build/dk-dash-survey/survey.json and the verifier's TLG/PHI "
           "export cache (build/dash-verify/cache/) not present -- gitignored build data",
)


def _reading(dictionary, entry: dict) -> str:
    """The verifier's reading for a filled-in entry: the author's first
    dictionary variant, the work abbreviation (none for a DEFAULT work) and
    the locus, e.g. "STOB. III 13, 47", "CLEM. Strom. IV 50 (II 271, 3)".
    An entry with no author (Bekker's Anecdota Graeca) matches the
    dictionary entries whose canonical author is None."""
    for key, a in dictionary._authors.items():
        if a["canonical_author"] != entry.get("authorDisplay"):
            continue
        # Several work keys may carry the title ("AËT." DEFAULT and "de
        # plac."; "SEXT." DEFAULT and "adv. math."): take the first form the
        # verifier's parser for this source can read.
        # (No backslash inside the f-string: CI runs Python 3.9.)
        trailing_p = re.compile(r"\s*p\.$")
        readings = [
            f"{a['variants'][0]}{'' if wk == 'DEFAULT' else ' ' + trailing_p.sub('', wk)} "
            f"{entry['locus']}".strip()
            for wk, w in a["works"].items() if w["title"] == entry["work"]["title"]]
        spec = verifier.SOURCES.get(_source_name(entry))
        for r in readings:
            try:
                if spec is not None:
                    spec.parse(r)
                return r
            except verifier.NotInCorpus:
                return r
            except (verifier.Unmapped, IndexError, AttributeError):
                continue
        if readings:
            return readings[0]
    raise AssertionError(f"no dictionary author/work for {entry!r}")


def _source_name(entry: dict) -> str:
    """The verifier's source key: the author, or the work when the entry has
    none (Bekker's Anecdota Graeca, John's ruling 2026-09-24)."""
    return entry.get("authorDisplay") or entry["work"]["title"]


def stage_records(tmp_build: Path) -> list[dict]:
    """One verifier record per dash the stage fills in, paired with the
    survey record for the same head (the oracle's pairing)."""
    _, rows = oracle.oracle(tmp_build)
    dictionary = ce._load_dictionary()
    survey = defaultdict(list)
    for rec in json.loads(oracle.SURVEY.read_text(encoding="utf-8")):
        survey[(rec["work"], rec["segment"], rec["head"])].append(rec)
    out = []
    for row in rows:
        e = row.get("stage")
        if not e or e["resolution"] != "dash":
            continue
        rec = survey[(row["work"], row["column"], row["head"])].pop(0)
        out.append({
            "work": row["work"], "segment": row["column"], "head": row["head"],
            # The stage's OWN extracted head (its "verbatim" field) -- not
            # always the same string as the survey's "head" above, which is
            # only a lookup key into the spine text for cutting the passage.
            # A dash-adjudications.json ruling's "head" is matched against
            # THIS string inside _resolve_head, so _covered (defect 3) must
            # compare against it too, not the survey's shorter head.
            "stage_head": e["verbatim"],
            "classification": rec["classification"],
            "source_author": _source_name(e),
            "stage": _reading(dictionary, e),
            "flags": e["flags"],
        })
    return out + inferred_direct_records(tmp_build)


def inferred_direct_records(tmp_build: Path) -> list[dict]:
    """One verifier record per DIRECT head whose author the stage inferred
    from an ambiguous abbreviation ("HEROD. II 123" = Herodotus, Sol review
    finding 3) -- the dashes built on one already come through the survey
    pairing, flagged the same way. The passage is cut after the stage's own
    head."""
    dictionary = ce._load_dictionary()
    saved = ce.BUILD_DIR, ce._resolve_source
    ce.BUILD_DIR, ce._resolve_source = tmp_build, oracle._dry_run_resolve_source
    out = []
    try:
        for path in sorted(oracle.SPINES.glob("*.json")):
            manifest = Manifest({"work": {"id": path.stem}, "citation": {"expand_citations": True}},
                                Path(f"{path.stem}.yaml"))
            result = json.loads(ce.run(manifest, json.loads(path.read_text(encoding="utf-8")))
                                .read_text(encoding="utf-8"))
            for seg_id, runs in result.items():
                for e in (e for run in runs for e in run):
                    if e["resolution"] != "direct" or ce._INFERRED not in e["flags"]:
                        continue
                    out.append({
                        "work": path.stem, "segment": seg_id.split(":", 1)[1],
                        "head": e["verbatim"], "stage_head": e["verbatim"],
                        "classification": "", "source_author": _source_name(e),
                        "stage": _reading(dictionary, e), "flags": e["flags"],
                    })
    finally:
        ce.BUILD_DIR, ce._resolve_source = saved
    return out


def verify_stage(tmp_build: Path) -> list[dict]:
    records = stage_records(tmp_build)
    spines = verifier.load_spines(oracle.SPINES)
    results = verifier.run(records, "stage", {}, spines, verifier.Corpus(CACHE), set())
    # verifier.run() builds its own result dicts with a fixed key set (it
    # does not pass unknown input fields through), and never drops or
    # reorders records (classes=set() filters nothing) -- so re-attach each
    # record's stage_head and flags by position.
    for rec, res in zip(records, results):
        res["stage_head"] = rec["stage_head"]
        res["flags"] = rec["flags"]
    return results


# Sources whose author the stage may infer from an ambiguous abbreviation
# and that the TLG check must confirm (Sol review finding 3).
_MUST_CONFIRM = {"Herodotus"}


def _covered(result: dict, rulings: dict) -> str | None:
    """Why a MISMATCH or NOT-FOUND is covered by John's rulings, else None.
    "Covered" = an entry in dash-adjudications.json for that exact head --
    work + segment + the whole printed head, matched exactly as the stage's
    own _same_head does (defect 3: a ruling for "— —40" must never cover a
    different head, "— —400", that happens to land in the same segment)."""
    ruling = rulings.get(result["work"], {}).get(result["segment"])
    head = result.get("stage_head", result["head"])
    if ruling and ce._same_head(head, ruling.get("head", "")):
        return "ruled"
    if "CLEM Strom." in rulings.get("_as_printed", {}) and \
            result["source_author"] == "Clement of Alexandria":
        m = re.search(r"Strom\.\s+([IVX]+)\s", result["reading"])
        found = re.search(r"Stromata: book (\d+), section", result["found"])
        if m and found and verifier.roman_to_int(m.group(1)) == int(found.group(1)) \
                and "near miss" in result["note"]:
            return "as printed (Clement's Stromateis)"
    return None


def _competing(result: dict) -> list[str]:
    """Review item 8: the places in `also` with at least as many independent
    (disjoint-span) probes as the reading's own locus -- as much evidence
    elsewhere. Raw counts are not compared: overlapping probes are one
    stretch of the passage (Sol review finding 1)."""
    out = []
    for place in result.get("also", []):
        m = re.search(r"(\d+) independent\]", place)
        if m and int(m.group(1)) >= result.get("independent_at_locus", 0):
            out.append(place)
    return out


def _failures(results: list[dict], rulings: dict) -> list[str]:
    """What fails the gate: a MISMATCH, NOT-FOUND or NOT-CHECKED (item 1 --
    a reading the check could not even attempt does not ship on a guess
    either), or a WEAK or CONFIRMED-PARTIAL with a competing place
    (_competing), that John's rulings do not cover (_covered); and a
    Herodotus reading the stage inferred from "HEROD." that the check did
    not confirm outright (item 3 -- only the literal verdict CONFIRMED
    passes an inferred reading; WEAK and CONFIRMED-PARTIAL are lesser
    confidence and fail it too, same as NOT-IN-CORPUS, SCHEME-UNMAPPED and
    NOT-CHECKED, unless ruled)."""
    out = []
    for r in results:
        inferred = ce._INFERRED in r.get("flags", []) and r["source_author"] in _MUST_CONFIRM
        if r["verdict"] in ("MISMATCH", "NOT-FOUND"):
            why = f"the TLG/PHI has it at {r['found']} ({r['note']})"
        elif r["verdict"] == "NOT-CHECKED":
            why = f"the check could not run: {r['note']}"
        elif inferred and r["verdict"] != "CONFIRMED":
            why = f"an inferred author must be confirmed outright: {r['verdict']} ({r['note']})"
        elif r["verdict"] in ("WEAK", "CONFIRMED-PARTIAL") and _competing(r):
            why = (f"{r['verdict']} at {r['found']} ({r['independent_at_locus']} independent probes), "
                   f"as much evidence at {'; '.join(_competing(r))}")
        else:
            continue
        if _covered(r, rulings) is None:
            out.append(f"{r['work']} {r['segment']} {r['head']!r}: stage reads "
                       f"{r['reading']!r}, {why}")
    return out


# --- _covered: unit tests on synthetic rulings/results (no corpus needed) --

def test_covered_requires_the_exact_head_not_just_work_and_segment():
    # Defect 3: a ruling for one dash head in a segment must never cover a
    # DIFFERENT dash head that happens to land in the same segment -- match
    # work + segment + the whole printed head (normalised whitespace only),
    # exactly as the stage's own _same_head does.
    rulings = {"democritus-fragments": {"B177": {
        "head": "— —40",
        "reading": {"author": "STOB", "work": "DEFAULT", "locus": "II 15, 40"},
    }}}
    ruled = {"work": "democritus-fragments", "segment": "B177", "head": "— —40",
             "reading": "STOB. II 15, 40", "found": "elsewhere", "note": "",
             "source_author": "Stobaeus"}
    other_head = dict(ruled, head="— —400")
    assert _covered(ruled, rulings) == "ruled"
    assert _covered(other_head, rulings) is None


def test_covered_matches_the_head_with_whitespace_normalised_only():
    rulings = {"work": {"S1": {
        "head": "— —40 (D. 1)",
        "reading": {"author": "X", "work": "DEFAULT", "locus": "1"},
    }}}
    spaced = {"work": "work", "segment": "S1", "head": "—  —40  (D. 1)",
              "reading": "", "found": "", "note": "", "source_author": ""}
    assert _covered(spaced, rulings) == "ruled"


def test_covered_by_any_adjudication_entry_not_only_a_filled_in_reading():
    # Item 2's redefinition: "covered" = an entry exists for that exact head,
    # whatever its reading (a pending/null reading still counts -- the stage
    # keeps such a head verbatim, so it never reaches these results in
    # practice, but _covered must not itself require a truthy reading).
    rulings = {"parmenides-testimonia": {"A42": {
        "head": "—II 25, 3 (D. 356)",
        "reading": None,
        "pending": "awaiting-print-check",
    }}}
    result = {"work": "parmenides-testimonia", "segment": "A42",
              "head": "—II 25, 3 (D. 356)", "verdict": "NOT-FOUND",
              "reading": "AËT. II 25, 3", "found": "", "note": "0 of 2 probes found",
              "source_author": "Aëtius"}
    assert _covered(result, rulings) == "ruled"


def test_weak_or_partial_with_a_competing_location_fails_unless_ruled():
    # Review item 8: a WEAK or CONFIRMED-PARTIAL verdict passes only when no
    # other place in the text has as much evidence as the reading's own
    # locus ("also"), or when John has ruled on that exact head.
    base = {"work": "w", "segment": "S1", "head": "— —5", "reading": "STOB. I 1, 5",
            "found": "2037.001: book 1, chapter 1, section 5", "note": "",
            "source_author": "Stobaeus", "probes_at_locus": 2, "independent_at_locus": 2}
    weak_alone = dict(base, verdict="WEAK", also=[])
    weak_rival = dict(base, verdict="WEAK",
                      also=["2037.001 Anthologium: book 1, chapter 9, section 1 [3 probes, 3 independent]"])
    partial_tie = dict(base, verdict="CONFIRMED-PARTIAL",
                       also=["0094.003 Placita: aet-book 2, aet-chapter 4 [2 probes, 2 independent]"])
    partial_less = dict(base, verdict="CONFIRMED-PARTIAL", probes_at_locus=4, independent_at_locus=4,
                        also=["0094.003 Placita: aet-book 2, aet-chapter 4 [2 probes, 2 independent]"])
    assert _failures([weak_alone, partial_less], {}) == []
    assert len(_failures([weak_rival, partial_tie], {})) == 2
    ruled = {"w": {"S1": {"head": "— —5", "reading": None, "pending": "awaiting-print-check"}}}
    assert _failures([weak_rival], ruled) == []


def test_rival_is_weighed_by_independent_probes_not_raw_ones():
    # Sol review finding 1: four overlapping probes at the printed locus are
    # one stretch of the passage (1 independent), three disjoint probes
    # elsewhere are three. Comparing raw counts (4 >= 3) let the WEAK
    # reading pass; independent counts (1 < 3) make the rival compete, so
    # the gate fails unless the exact head is ruled.
    probes = [verifier.Probe("x" * 20, s) for s in (0, 5, 10, 15, 40, 60, 80)]
    at = (("book", "1"), ("chapter", "1"), ("section", "5"))
    other = (("book", "1"), ("chapter", "9"), ("section", "1"))
    hits = [verifier.Hit(i, "001", at) for i in range(4)] + \
           [verifier.Hit(i, "001", other) for i in (4, 5, 6)]
    works = {"001": verifier.WorkIndex("001", "Anthologium", "", [0], [()])}
    locus = verifier.Locus([("book", "1"), ("chapter", "1"), ("section", "5")], ["001"])
    res = verifier.evaluate([locus], hits, probes, works, "2037")
    assert res["verdict"] == "WEAK"
    assert res["probes_at_locus"] == 4 and res["independent_at_locus"] == 1
    assert res["also"] and "3 independent" in res["also"][0]
    result = dict(res, work="w", segment="S1", head="— —5", reading="STOB. I 1, 5",
                  source_author="Stobaeus")
    assert len(_failures([result], {})) == 1
    ruled = {"w": {"S1": {"head": "— —5", "reading": None, "pending": "awaiting-print-check"}}}
    assert _failures([result], ruled) == []


def test_an_inferred_herodotus_reading_must_be_confirmed():
    # Sol review finding 3, tightened 2026-09-24: "HEROD." read as Herodotus
    # is a rule of thumb (Herodian the historian is cited by book + chapter
    # too), so each such reading -- direct head or dash -- must carry the
    # LITERAL verdict CONFIRMED in the TLG Herodotus; WEAK and
    # CONFIRMED-PARTIAL are lesser confidence and fail too, unless the exact
    # head is ruled (item 1). A reading the verifier cannot check does not
    # pass by default, as a dash does.
    base = {"work": "w", "segment": "S1", "head": "HEROD. II 123", "reading": "HERODOT. II 123",
            "found": "", "note": "", "source_author": "Herodotus", "flags": ["author-inferred"],
            "probes_at_locus": 2, "independent_at_locus": 2, "also": []}
    ok = [dict(base, verdict="CONFIRMED")]
    bad = [dict(base, verdict=v) for v in
           ("WEAK", "CONFIRMED-PARTIAL", "SCHEME-UNMAPPED", "NOT-IN-CORPUS", "NOT-CHECKED")]
    rival = dict(base, verdict="WEAK", also=["0016.001 Historiae: book 2, section 9 [2 probes, 2 independent]"])
    assert _failures(ok, {}) == []
    assert len(_failures(bad + [rival], {})) == 6
    ruled = {"w": {"S1": {"head": "HEROD. II 123", "reading": None, "pending": "awaiting-print-check"}}}
    assert _failures(bad + [rival], ruled) == []
    # A dash the stage did not mark inferred keeps the dash rule.
    plain = dict(base, verdict="SCHEME-UNMAPPED", flags=["dash-e4"])
    assert _failures([plain], {}) == []


def test_not_checked_fails_the_gate_unless_ruled():
    # Item 1: a filled-in dash the verifier could not even attempt (e.g. an
    # incomplete citation) used to pass silently -- NOT-CHECKED is not one
    # of the verdicts that ships without a ruling (only NOT-IN-CORPUS and
    # SCHEME-UNMAPPED do, plus WEAK / CONFIRMED-PARTIAL with no rival).
    base = {"work": "w", "segment": "S1", "head": "— —5", "reading": "STOB. I 1",
            "found": "", "note": "reading is not a complete citation",
            "source_author": "Stobaeus", "flags": []}
    result = dict(base, verdict="NOT-CHECKED")
    assert len(_failures([result], {})) == 1
    ruled = {"w": {"S1": {"head": "— —5", "reading": None, "pending": "awaiting-print-check"}}}
    assert _failures([result], ruled) == []
    # NOT-IN-CORPUS and SCHEME-UNMAPPED still ship without a ruling.
    assert _failures([dict(base, verdict="NOT-IN-CORPUS")], {}) == []
    assert _failures([dict(base, verdict="SCHEME-UNMAPPED")], {}) == []


@requires_corpus
def test_every_inferred_herodotus_reading_is_checked(tmp_path):
    # Every "HEROD." the stage reads as Herodotus in the 39 works, direct
    # heads included, reaches the TLG check.
    results = verify_stage(tmp_path)
    got = {(r["work"], r["segment"]) for r in results
           if "author-inferred" in r["flags"] and r["source_author"] == "Herodotus"}
    assert {("pythagoras-testimonia", "1"), ("pythagoras-testimonia", "2"),
            ("thales-testimonia", "A6"), ("thales-testimonia", "A16")} <= got


@requires_corpus
def test_every_filled_in_dash_is_confirmed_or_ruled(tmp_path):
    results = verify_stage(tmp_path)
    rulings = json.loads(ADJUDICATIONS.read_text(encoding="utf-8"))
    counts = Counter(r["verdict"] for r in results)
    uncovered = _failures(results, rulings)
    lesser = [f"{r['verdict']} {r['work']} {r['segment']} {r['reading']!r} at {r['found']}"
              f"{' | also ' + '; '.join(r['also']) if r.get('also') else ''}"
              for r in results if r["verdict"] in ("WEAK", "CONFIRMED-PARTIAL")]
    assert not uncovered, (
        f"verdicts: {dict(counts)}\n" + "\n".join(uncovered)
        + "\n\nall WEAK / CONFIRMED-PARTIAL:\n" + "\n".join(lesser))
    assert results, "the stage filled in no dash at all"


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        results = verify_stage(Path(d))
    rulings = json.loads(ADJUDICATIONS.read_text(encoding="utf-8"))
    # Every verdict the run produced, always -- CONFIRMED-PARTIAL and WEAK
    # (defect 4) and NOT-IN-CORPUS / SCHEME-UNMAPPED stay visible even though
    # they fail the test only with a competing place (item 8).
    print(dict(Counter(r["verdict"] for r in results)), f"of {len(results)} filled-in dashes")
    for r in results:
        if r["verdict"] in ("MISMATCH", "NOT-FOUND"):
            why = _covered(r, rulings) or "NOT COVERED"
            print(f"{r['verdict']} {r['work']} {r['segment']} {r['head']!r}: {r['reading']} -> "
                  f"{r['found']} [{why}]")
    for r in results:
        if r["verdict"] in ("WEAK", "CONFIRMED-PARTIAL"):
            rival = _competing(r)
            why = "" if not rival else f" COMPETING {'; '.join(rival)} [{_covered(r, rulings) or 'NOT COVERED'}]"
            print(f"{r['verdict']:18} {r['work']} {r['segment']} {r['reading']} | {r['note']}{why}")
    if "-v" in sys.argv:
        for r in results:
            if r["verdict"] not in ("CONFIRMED", "MISMATCH", "NOT-FOUND", "WEAK", "CONFIRMED-PARTIAL"):
                print(f"{r['verdict']:18} {r['work']} {r['segment']} {r['reading']} | {r['note']}")
