"""Oracle check for DK dash citations (rule E, John 2026-09-24): run the
citation-expansion stage over all 39 DK fragment/testimonia spines (as if
every work opted in -- a dry run; manifests are not touched) and compare each
dash head's result with the hand survey of all 613 dash heads.

Every dash head lands in one of four bins:
  agree      the stage fills it in exactly as the survey reads it;
  verbatim   the stage leaves it as printed, flagged (acceptable);
  missing    the stage has no head there (a dash inside a passage);
  disagree   the stage fills in a DIFFERENT citation -- each one must be in
             EXPLAINED below, with the reason, or the test fails.

Both inputs are gitignored build data: build/dk-spines/<work>.json (the 39
stage1 spines) and build/dk-dash-survey/survey.json (the survey). The test
skips cleanly when either is absent (same pattern as
test_stage1_lined_source.py's `requires_export`). Run this file directly
(`uv run python tests/test_citation_dash_oracle.py`) to print the report.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_citation_expansion as ce  # noqa: E402
from reader_pipeline.config import Manifest  # noqa: E402

SPINES = ROOT / "build" / "dk-spines"
SURVEY = ROOT / "build" / "dk-dash-survey" / "survey.json"

requires_data = pytest.mark.skipif(
    not (SPINES.is_dir() and SURVEY.exists()),
    reason="build/dk-spines/ and build/dk-dash-survey/survey.json not present "
           "(gitignored build data) -- copy them in to run the dash oracle",
)

# (work, column, head) -> why the stage's filled-in citation differs from
# the survey's reading. The survey was made under the dash-COUNT hypothesis
# before rule E; where the two part, rule E is the ruling.
_ADJUDICATED = "John's adjudication (sources/dk-citations/dash-adjudications.json): the TLG text puts it here; DK's line omits the chapter"
_AFTER_B256 = "follows John's reading of B256 (IV 2, 14); the survey itself expected IV 2, 15-17 if B256 is IV 2"
_HIDDEN_CHAPTER = "John's adjudication: located in the TLG Stobaeus; DK's line hides the chapter change"
_MISPRINT = "John's ruling: a DK misprint, printed corrected with a note (the TLG has it at the corrected locus)"
_BEKKER_VOLUME = ("John's ruling (2026-09-24): Bekker's Anecdota prints its volume first ('I, Lex. VI p. ...'), "
                  "which the survey's reading does not; same page and line")
EXPLAINED: dict[tuple[str, str, str], str] = {
    ("antiphon-sophist-fragments", "B107", "—V 441"): _MISPRINT,
    ("democritus-fragments", "B226", "— —47"): _HIDDEN_CHAPTER,
    ("democritus-fragments", "B245", "— —53"): _HIDDEN_CHAPTER,
    ("democritus-fragments", "B285", "— —65"): _HIDDEN_CHAPTER,
    ("heraclitus-fragments", "B80", "— —VI 42 (II 111, 11 Koetschau)"):
        "same citation: the work title Contra Celsum (lib. VI) carries the book, so the locus is 42 "
        "(review finding 4), the same shape as the direct head ORIG. c. Cels. VI 12",
    ("thales-testimonia", "A17b", "—II 27, 5 (D. 358)"): _MISPRINT,
    ("antiphon-sophist-fragments", "B60", "—II 31, 39 p. 208, 13 W."):
        "same citation: the stage keeps Wachsmuth's initial 'W.' as printed",
    ("antiphon-sophist-fragments", "B17", "— —p. 472, 14"): _BEKKER_VOLUME,
    ("antiphon-sophist-fragments", "B83", "—Lex. VI p. 345, 26"): _BEKKER_VOLUME,
    ("antiphon-sophist-fragments", "B84", "—p. 367, 31"):
        _BEKKER_VOLUME + "; and rule E step 5 keeps 'Lex. VI' from the citation above (the survey's "
        "one-dash-one-level reading dropped it); the Lexica of Bekker's Anecdota I are paged through "
        "the volume, so both find the same page",
    ("antiphon-sophist-fragments", "B85", "—p. 418, 6"): "as B84",
    ("antiphon-sophist-fragments", "B86", "—p. 419, 18"): "as B84",
    ("prodicus-testimonia", "A5", "—Tagenistae fr. 490 K."):
        "same citation: the stage keeps Kock's initial 'K.' as printed",
    ("antiphon-sophist-fragments", "B93b", "—p. 87, 25 R."):
        "rule E step 5 keeps the section letter A of 'PHOT. A p. 66, 4' (Reitzenstein's alpha section); "
        "the survey's one-dash reading dropped it; the page locates it either way",
    ("critias-fragments", "B61", "— —152. 153"):
        "the stage keeps both sections DK prints; the survey kept only the first",
    ("critias-fragments", "B70", "— —196. 197"): "as B61",
    ("democritus-fragments", "B177", "— —40"): _ADJUDICATED,
    ("democritus-fragments", "B217", "— —30"): _ADJUDICATED,
    ("democritus-fragments", "B256", "— —14"): _ADJUDICATED,
    ("democritus-fragments", "B257", "— —15"): _AFTER_B256,
    ("democritus-fragments", "B258", "— —16"): _AFTER_B256,
    ("democritus-fragments", "B259", "— —17"): _AFTER_B256,
    ("democritus-fragments", "B292", "— —19"): _ADJUDICATED,
    ("democritus-fragments", "B128", "—π. καθολ. προσ. bei Theogn. p. 79 [I 355, 19 L.]"):
        "same citation: 'bei Theogn. p. 79 [I 355, 19 L.]' names the text that preserves Herodian's "
        "De prosodia catholica, so the stage prints it as apparatus after the title, with no locus "
        "of its own (content review item 6)",
    ("gorgias-fragments", "B16", "— —1406b 4"):
        "rule E step 5 keeps book and chapter (Γ 3) and replaces the Bekker page and line; "
        "1406b 4 does lie in Rhet. Γ 3",
    ("heraclitus-fragments", "B79", "— —"):
        "same citation: the dictionary keys Origen's Contra Celsum by book ('c. Cels. VI' = Contra "
        "Celsum (lib. VI)), so the locus is 12, exactly as the direct head above it prints",
}


# --- Normalizing a citation to compare -------------------------------------

_LOOKALIKE = str.maketrans("ΑΒΓΔΕΖΗΙΚΜΝΟΡΤΥΧ", "ABΓDEZHIKMNOPTYX")


def _locus_key(locus: str) -> tuple[str, ...]:
    """The locus as a sequence of numbers, numerals and letters: bracket
    groups, editor names, markers ("p.", "n.", "t.") and punctuation dropped;
    Greek capitals that look like Latin ones unified (the data prints
    Latin "B"/"D" for Greek book letters)."""
    s = re.sub(r"\([^()]*\)|\[[^\[\]]*\]", " ", locus)
    out = []
    for tok in s.split():
        core = tok.strip(".,;:").translate(_LOOKALIKE)
        core = re.sub(r"(?<=\d)ff?$", "", core)  # "1ff." = "1 ff."
        if re.fullmatch(r"\*?\d+[a-zA-Z]{0,3}", core) or re.fullmatch(r"[IVXLC]+|[A-ZΑ-Ω]", core):
            m = re.fullmatch(r"(\d+)([A-F])", core)
            out.extend([m.group(1), m.group(2)] if m else [core])
        elif core.startswith("s.v") or core == "s":
            out.append("s.v.")
    return tuple(out)


def _survey_reading(dictionary, reading: str):
    """(author key, work title or None, locus key) of a survey reading like
    "SIMPLIC. Phys. 155, 30" or "HARPOCR. s.v. [headword]"."""
    toks = reading.replace("(?)", "").split()
    m = dictionary.match_author(toks, 0)
    if m is None or m[1] == ce._AMBIGUOUS:
        return None, None, _locus_key(reading)
    span, key = m
    rest = toks[span:]
    if rest and rest[0].startswith("(") and rest[0].endswith(")"):
        rest = [rest[0][1:-1]] + rest[1:]
    w = dictionary.match_work(key, rest, 0)
    works = dictionary.author_entry(key)["works"]
    if w is not None:
        span_w = w[0]
        if ce._ROMAN_NUMERAL.match(rest[span_w - 1].strip(".,")):
            span_w -= 1  # a work key that swallows the book ("de div. I")
        title, rest = works[w[1]]["title"], rest[span_w:]
    elif rest and not ce._LOCUS_START.match(rest[0]) and not rest[0].startswith("s."):
        title = None  # a work the dictionary does not name
    else:
        title = works.get("DEFAULT", {}).get("title")
    return key, title, _locus_key(" ".join(rest))


def _stage_dash_entries(result: dict) -> dict[tuple[str, str], list[dict]]:
    """Per (column), the stage's dash entries in document order."""
    out: dict[str, list[dict]] = {}
    for seg_id, runs in result.items():
        col = seg_id.split(":", 1)[1]
        for run in runs:
            for e in run:
                if ce._DASH_PREFIX.match(e["verbatim"]) or "dash-misparse" in e["flags"]:
                    out.setdefault(col, []).append(e)
    return out


FATALS: list[str] = []


def _dry_run_resolve_source(*args, **kwargs):
    """The fatal gate (author known, no work, no DEFAULT) guards opted-in
    works; in this dry run over works that have not opted in it would stop
    at the first dictionary gap, so it is recorded and the head passes
    through verbatim instead (and its author still resets the chain)."""
    try:
        return _REAL_RESOLVE_SOURCE(*args, **kwargs)
    except ValueError as err:
        FATALS.append(str(err).split(" -- ")[0])
        tokens, start, end = args[3], args[4], args[5]
        return ce._verbatim(" ".join(tokens[start:end]), ["oracle-fatal"]), None


_REAL_RESOLVE_SOURCE = ce._resolve_source


def oracle(tmp_build: Path) -> tuple[Counter, list[dict]]:
    saved = ce.BUILD_DIR, ce._resolve_source
    ce.BUILD_DIR, ce._resolve_source = tmp_build, _dry_run_resolve_source
    try:
        return _oracle()
    finally:
        ce.BUILD_DIR, ce._resolve_source = saved


def _oracle() -> tuple[Counter, list[dict]]:
    FATALS.clear()
    dictionary = ce._load_dictionary()
    survey = json.loads(SURVEY.read_text(encoding="utf-8"))
    by_work: dict[str, list[dict]] = {}
    for rec in survey:
        by_work.setdefault(rec["work"], []).append(rec)
    bins: Counter = Counter()
    rows: list[dict] = []
    for work, recs in sorted(by_work.items()):
        spine = json.loads((SPINES / f"{work}.json").read_text(encoding="utf-8"))
        manifest = Manifest({"work": {"id": work}, "citation": {"expand_citations": True}},
                            Path(f"{work}.yaml"))
        result = json.loads(ce.run(manifest, spine).read_text(encoding="utf-8"))
        stage = _stage_dash_entries(result)
        taken: Counter = Counter()
        for rec in recs:
            col = rec["segment"]
            row = {"work": work, "column": col, "head": rec["head"], "reading": rec["resolved"]}
            if rec["position"] == "in-passage":
                row["bin"] = "missing"
            else:
                entries = stage.get(col, [])
                if taken[col] >= len(entries):
                    row["bin"] = "missing"
                else:
                    e = entries[taken[col]]
                    taken[col] += 1
                    row["stage"] = e
                    if e["resolution"] == "verbatim":
                        row["bin"] = "verbatim"
                    else:
                        key, title, locus = _survey_reading(dictionary, rec["resolved"])
                        author = dictionary.author_entry(key)["canonical_author"] if key else None
                        stage_locus = _locus_key(e["locus"])
                        same_locus = stage_locus == locus or (
                            locus[-1:] == ("s.v.",) and stage_locus[:1] == ("s.v.",)
                            and "[headword]" in rec["resolved"]) or (
                            locus == ("s.v.",) and stage_locus[:1] == ("s.v.",))
                        same = (e.get("authorDisplay") == author and same_locus
                                and (title is None or e["work"]["title"] == title))
                        row["bin"] = "agree" if same else "disagree"
            bins[row["bin"]] += 1
            rows.append(row)
    return bins, rows


def _fmt(e: dict) -> str:
    author = f"{e['authorDisplay']}, " if e.get("authorDisplay") else ""
    return f"{author}{e['work']['title']} {e['locus']}"


@pytest.mark.skipif(not SPINES.is_dir(), reason="build/dk-spines/ not present (gitignored build data)")
def test_all_39_works_opt_in_without_a_fatal_error(tmp_path, monkeypatch):
    # The goal for switching expansion on everywhere: the stage, with its
    # real fatal gate (no dry-run wrapper), runs over every DK
    # fragment/testimonia spine as if each work had opted in.
    monkeypatch.setattr(ce, "BUILD_DIR", tmp_path)
    spines = sorted(SPINES.glob("*.json"))
    assert len(spines) == 39
    fatal = []
    for path in spines:
        manifest = Manifest({"work": {"id": path.stem}, "citation": {"expand_citations": True}},
                            Path(f"{path.stem}.yaml"))
        try:
            ce.run(manifest, json.loads(path.read_text(encoding="utf-8")))
        except ValueError as err:
            fatal.append(str(err)[:200])
    assert not fatal, "\n".join(fatal)


@requires_data
def test_every_dash_disagreement_is_explained(tmp_path):
    bins, rows = oracle(tmp_path)
    unexplained = [
        f"{r['work']} {r['column']} {r['head']!r}: stage {_fmt(r['stage'])!r} vs survey {r['reading']!r}"
        for r in rows
        if r["bin"] == "disagree" and (r["work"], r["column"], r["head"]) not in EXPLAINED
    ]
    assert not unexplained, "\n".join(unexplained)
    assert sum(bins.values()) == 613


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        bins, rows = oracle(Path(d))
    print(dict(bins))
    for r in rows:
        if r["bin"] == "disagree":
            why = EXPLAINED.get((r["work"], r["column"], r["head"]), "UNEXPLAINED")
            print(f"DISAGREE {r['work']} {r['column']} {r['head']!r}\n   stage  {_fmt(r['stage'])}\n"
                  f"   survey {r['reading']}\n   why    {why}")
    if "-v" in sys.argv:
        for r in rows:
            if r["bin"] in ("verbatim", "missing"):
                flags = r["stage"]["flags"] if "stage" in r else []
                print(f"{r['bin'].upper():8} {r['work']} {r['column']} {r['head']!r} {flags} | survey {r['reading']}")
