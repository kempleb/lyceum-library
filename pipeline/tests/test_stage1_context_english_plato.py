"""Regression tests for stage1_context_english.py's Plato locus resolver
(docs/plato-locus-resolver-design.md, Phase 1 + Phase 2): the single-letter
and multi-letter-range cases, discontinuous loci in one column (two spans),
`ff.` rejection, a missing locus/endpoint refusing rather than guessing, a
reversed range, an unregistered dialogue, and integration coverage pinning
the real hand-authored sidecars against the real vendored Perseus store
(Phase 1's three Hippias columns, plus Phase 3's hand-authored loci across
all six works that cite Plato)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import stage1_context_english as sce
from reader_pipeline.config import Manifest, SOURCES_DIR as REAL_SOURCES_DIR


def _spine(columns: list[str]) -> dict:
    return {"work": "FIX", "segments": [
        {"id": f"1:{c}", "book": 1, "column": c, "lines": []} for c in columns
    ]}


def _manifest(work_id="hippias-testimonia") -> Manifest:
    return Manifest({"work": {"id": work_id}}, Path("FIX.yaml"))


def _write_plato_store(tmp_path, entries: dict[str, str]) -> None:
    p = tmp_path / "perseus-plato" / "plato-stephanus.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries), encoding="utf-8")


def _write_jowett_store(tmp_path, entries: dict[str, str]) -> None:
    p = tmp_path / "jowett-plato" / "jowett-stephanus.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries), encoding="utf-8")


def _write_declaration(tmp_path, work_id: str, declared: dict) -> None:
    p = tmp_path / work_id / "context-english.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(declared), encoding="utf-8")


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", tmp_path)
    monkeypatch.setattr(sce, "BUILD_DIR", tmp_path / "build")
    return tmp_path


def _plato_span(work: str, locus: str, credit: str = "Fowler, 1926") -> dict:
    return {
        "source_author": "Plato", "source_work": work, "locus": locus,
        "status": "translated", "translation_credit": credit,
    }


def test_resolves_single_letter_locus(tmp_path):
    _write_plato_store(tmp_path, {
        "hippias-major:281a": "Hippias, beautiful and wise...",
    })
    manifest = _manifest()
    spine = _spine(["A6"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A6": {"context_spans": [_plato_span("Hippias Major", "281a")]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    span = resolved["1:A6"][0]
    assert span["text"] == "Hippias, beautiful and wise..."
    assert span["sourceAuthor"] == "Plato"
    assert span["sourceWork"] == "Hippias Major"
    assert "sectionLoci" not in span


def test_resolves_multi_letter_range_across_a_page_boundary(tmp_path):
    # docs/plato-locus-resolver-design.md's own page-crossing example: a
    # range need not stay on one Stephanus page.
    _write_plato_store(tmp_path, {
        "hippias-minor:363c": "for he has told us...",
        "hippias-minor:363d": "which I prepared for exhibition...",
        "hippias-minor:364a": "You are in a state of blessedness...",
    })
    manifest = _manifest()
    spine = _spine(["A8"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A8": {"context_spans": [_plato_span("Hippias Minor", "363c-364a")]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    span = resolved["1:A8"][0]
    assert span["text"] == (
        "for he has told us...\n\nwhich I prepared for exhibition...\n\n"
        "You are in a state of blessedness..."
    )
    # Bare Stephanus tokens, never the dialogue-slug-prefixed store key
    # (docs/plato-locus-resolver-design.md SS5: "Keep it that way --
    # '315c-315e', not 'protagoras.315c-315e'").
    assert span["sectionLoci"] == ["363c", "363d", "364a"]


def test_discontinuous_loci_in_one_column_are_two_spans(tmp_path):
    # docs/plato-locus-resolver-design.md SS3(c): a column citing two
    # separate Plato passages takes two context_spans, each independently
    # resolved and credited.
    _write_plato_store(tmp_path, {
        "gorgias:453a": "First locus text.",
        "gorgias:455a": "Second locus text.",
    })
    manifest = _manifest()
    spine = _spine(["A28"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A28": {"context_spans": [
            _plato_span("Gorgias", "453a", "Lamb, 1925"),
            _plato_span("Gorgias", "455a", "Lamb, 1925"),
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert [s["text"] for s in resolved["1:A28"]] == [
        "First locus text.", "Second locus text.",
    ]


@pytest.mark.parametrize("locus", ["315c ff.", "315cff", "315c-", "-315c", "315", "315f", "ff."])
def test_ff_and_other_malformed_loci_are_rejected(tmp_path, locus):
    # docs/plato-locus-resolver-design.md SS0/SS3(b): "ff." is rejected
    # outright -- no open-ended ranges, a human pins the end -- and this is
    # just the locus-syntax gate, not a special case: the regex has no way
    # to match an unbounded range at all.
    _write_plato_store(tmp_path, {"protagoras:315c": "text"})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [_plato_span("Protagoras", locus, "Lamb, 1924")]},
    })
    with pytest.raises(ValueError, match="is not valid"):
        sce.run(manifest, spine)


def test_missing_locus_key_is_fatal_not_silent(tmp_path):
    _write_plato_store(tmp_path, {"protagoras:315c": "text"})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [_plato_span("Protagoras", "315d", "Lamb, 1924")]},
    })
    with pytest.raises(ValueError, match="not a key in"):
        sce.run(manifest, spine)


def test_range_with_missing_end_endpoint_is_fatal(tmp_path):
    _write_plato_store(tmp_path, {"protagoras:315c": "text"})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [_plato_span("Protagoras", "315c-315e", "Lamb, 1924")]},
    })
    with pytest.raises(ValueError, match="not in"):
        sce.run(manifest, spine)


def test_reversed_range_is_fatal(tmp_path):
    _write_plato_store(tmp_path, {
        "protagoras:315c": "c text", "protagoras:315d": "d text",
    })
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [_plato_span("Protagoras", "315d-315c", "Lamb, 1924")]},
    })
    with pytest.raises(ValueError, match="comes before"):
        sce.run(manifest, spine)


def test_unregistered_dialogue_is_fatal_like_an_unknown_author(tmp_path):
    # Statesman is deliberately not vendored (docs/plato-locus-resolver-
    # design.md SS4: the registry is pair-keyed, so "Plato" + a dialogue
    # this module has no resolver for is fatal, never a fallback resolve).
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [_plato_span("Statesman", "257a", "Fowler, 1925")]},
    })
    with pytest.raises(ValueError, match="no locus resolver"):
        sce.run(manifest, spine)


# --- Integration: the REAL Hippias-testimonia sidecar against the REAL -----
# vendored Perseus store (docs/plato-locus-resolver-design.md's Phase 1
# three columns). Bypasses the _patch_dirs autouse fixture's tmp_path
# redirection to read sources/hippias-testimonia/context-english.json and
# sources/perseus-plato/plato-stephanus.clean.json directly off disk, so a
# real regression in either the hand-authored sidecar or the vendored store
# would fail these tests.

def _run_against_real_sources(work_id: str) -> dict:
    # Columns are derived from the real sidecar's own keys rather than
    # hardcoded, so hand-authoring a new column (Phase 3 adds 34 of them
    # across six works) can never fail these tests for the wrong reason --
    # `run` is fatal on a declared column the spine doesn't carry.
    declared = json.loads(
        (REAL_SOURCES_DIR / work_id / "context-english.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = _manifest(work_id)
    spine = _spine([seg_id.split(":", 1)[1] for seg_id in declared])
    out_path = sce.run(manifest, spine)
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_real_hippias_testimonia_A4_resolves_apology_19e(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources("hippias-testimonia")
    span = resolved["1:A4"][0]
    assert span["sourceWork"] == "Apology"
    assert span["locus"] == "19e"
    assert "sectionLoci" not in span
    assert span["text"].startswith(
        "people and that I make money by it, that is not true either."
    )
    assert "Gorgias of Leontini and Prodicus of Ceos and Hippias of Elis" in span["text"]


def test_real_hippias_testimonia_A6_resolves_hippias_major_281a(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources("hippias-testimonia")
    span = resolved["1:A6"][0]
    assert span["sourceWork"] == "Hippias Major"
    assert span["locus"] == "281a"
    assert "sectionLoci" not in span
    assert span["text"].startswith(
        "Soc. Hippias, beautiful and wise, what a long time it is since you "
        "have put in at the port of Athens!"
    )


def test_real_hippias_testimonia_A8_resolves_hippias_minor_363c_to_364a(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources("hippias-testimonia")
    span = resolved["1:A8"][0]
    assert span["sourceWork"] == "Hippias Minor"
    assert span["locus"] == "363c-364a"
    assert span["sectionLoci"] == ["363c", "363d", "364a"]
    assert "Naturally, Socrates, I am in this state" in span["text"]
    assert span["text"].endswith(
        "Your reputation will be a monument of wisdom for the city of Elis "
        "and your parents."
    )


# --- Integration: every hand-authored Plato locus in the repo -------------
# Phase 3 authored 34 more columns across six works. These pin the whole
# set, so a bad edit to any sidecar -- or a regression in the vendored
# store -- fails here rather than at build time.

PLATO_SIDECAR_WORKS = [
    "hippias-testimonia", "prodicus-testimonia", "gorgias-testimonia",
    "critias-testimonia", "protagoras-testimonia", "philolaus-testimonia",
]


@pytest.mark.parametrize("work_id", PLATO_SIDECAR_WORKS)
def test_every_authored_plato_locus_resolves_to_real_text(work_id, monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources(work_id)
    plato = [
        (seg_id, s)
        for seg_id, spans in resolved.items()
        for s in spans
        if s["sourceAuthor"] == "Plato"
    ]
    assert plato, f"{work_id} declares no Plato span"
    for seg_id, span in plato:
        assert span["text"].strip(), f"{work_id} {seg_id} {span['locus']} empty"
        assert span["translationCredit"]
        # A range must mark each letter it emitted; a single letter must not
        # (docs/plato-locus-resolver-design.md SS3(a)).
        if "-" in span["locus"]:
            assert span["sectionLoci"][0] == span["locus"].split("-")[0]
            assert span["sectionLoci"][-1] == span["locus"].split("-")[1]
        else:
            assert "sectionLoci" not in span


def test_critias_A3_carries_timaeus_three_discontinuous_loci(monkeypatch):
    # DK prints "Tim. 20 A ... 20 D ... 21 A" -- three separate excerpts in
    # one column, authored as three spans rather than one 20a-21b sweep.
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    spans = _run_against_real_sources("critias-testimonia")["1:A3"]
    assert [s["locus"] for s in spans] == ["20a", "20d-20e", "21a-21b"]
    assert "he is no novice in any of the subjects" in spans[0]["text"]
    assert spans[1]["text"].startswith("Critias here mentioned to us a story")
    assert "close upon ninety years of age" in spans[2]["text"]


def test_prodicus_A2_pins_the_end_of_DKs_open_ended_ff(monkeypatch):
    # DK cites "Protag. 315 C D ff."; the quoted Greek ends at the first
    # clause of 316a, so the hand-authored locus pins 315c-316a rather than
    # leaving the range open (the resolver refuses "ff." by design).
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    span = _run_against_real_sources("prodicus-testimonia")["1:A2"][0]
    assert span["locus"] == "315c-316a"
    assert span["sectionLoci"] == ["315c", "315d", "315e", "316a"]
    assert "Tantalus also did I there behold" in span["text"]
    assert span["text"].rstrip().endswith(
        "So, when we had entered, after some more little delays over certain "
        "points we had to examine, we went up to Protagoras,"
    )


# --- Item 82: per-passage translation picker -- Jowett `alts` -------------
# sources/jowett-plato/jowett-stephanus.clean.json is an OPTIONAL second
# store (same flat "slug:locus" shape as plato-stephanus.clean.json),
# generated by a separate pipeline step. Its absence must mean "no alts",
# never an error; its presence adds an `alts` array to a span only when at
# least one of the span's loci has a Jowett hit.

def test_missing_jowett_store_emits_no_alts_byte_identical(tmp_path, monkeypatch):
    _write_plato_store(tmp_path, {"hippias-major:281a": "Primary text."})
    manifest = _manifest()
    spine = _spine(["A6"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A6": {"context_spans": [_plato_span("Hippias Major", "281a")]},
    })
    # Run once with no jowett store on disk at all.
    out_path = sce.run(manifest, spine)
    without_store = out_path.read_text(encoding="utf-8")
    resolved = json.loads(without_store)
    assert "alts" not in resolved["1:A6"][0]

    # Baseline: the same run with the alts branch stubbed out entirely --
    # equivalent to the code before the feature existed. Output must be
    # byte-identical, proving the branch adds nothing when the store is
    # absent.
    monkeypatch.setattr(sce, "_jowett_alts", lambda *args, **kwargs: None)
    out_path2 = sce.run(manifest, spine)
    assert out_path2.read_text(encoding="utf-8") == without_store


def test_blank_or_null_jowett_values_are_gaps_not_hits(tmp_path):
    # An empty string, whitespace, or JSON null in the store must count as
    # "no Jowett for this locus" -- never ship as text, never keep alts alive.
    _write_plato_store(tmp_path, {"hippias-major:281a": "Primary text."})
    _write_jowett_store(tmp_path, {
        "hippias-major:281a": "",
        "hippias-minor:363c": None,
        "hippias-major:282a": "   ",
    })
    manifest = _manifest()
    spine = _spine(["A6"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A6": {"context_spans": [_plato_span("Hippias Major", "281a")]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert "alts" not in resolved["1:A6"][0]


def test_full_jowett_coverage_all_sections_carry_text(tmp_path):
    _write_plato_store(tmp_path, {
        "hippias-minor:363c": "Primary c.",
        "hippias-minor:363d": "Primary d.",
        "hippias-minor:364a": "Primary a.",
    })
    _write_jowett_store(tmp_path, {
        "hippias-minor:363c": "Jowett c.",
        "hippias-minor:363d": "Jowett d.",
        "hippias-minor:364a": "Jowett a.",
    })
    manifest = _manifest()
    spine = _spine(["A8"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A8": {"context_spans": [_plato_span("Hippias Minor", "363c-364a")]},
    })
    out_path = sce.run(manifest, spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A8"][0]
    assert span["alts"] == [{
        "id": "jowett",
        "label": "Jowett",
        "translationCredit": (
            "Benjamin Jowett, The Dialogues of Plato, 3rd ed., Oxford, 1892"
        ),
        "sections": [
            {"locus": "363c", "text": "Jowett c."},
            {"locus": "363d", "text": "Jowett d."},
            {"locus": "364a", "text": "Jowett a."},
        ],
    }]


def test_partial_jowett_coverage_gap_sections_omit_text_key(tmp_path):
    _write_plato_store(tmp_path, {
        "hippias-minor:363c": "Primary c.",
        "hippias-minor:363d": "Primary d.",
        "hippias-minor:364a": "Primary a.",
    })
    _write_jowett_store(tmp_path, {
        "hippias-minor:363c": "Jowett c.",
        # 363d has no Jowett entry at all.
        "hippias-minor:364a": "Jowett a.",
    })
    manifest = _manifest()
    spine = _spine(["A8"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A8": {"context_spans": [_plato_span("Hippias Minor", "363c-364a")]},
    })
    out_path = sce.run(manifest, spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A8"][0]
    sections = span["alts"][0]["sections"]
    assert [s["locus"] for s in sections] == ["363c", "363d", "364a"]
    assert sections[0]["text"] == "Jowett c."
    assert "text" not in sections[1]
    assert sections[2]["text"] == "Jowett a."


def test_zero_jowett_coverage_omits_alts_key_entirely(tmp_path):
    _write_plato_store(tmp_path, {"hippias-major:281a": "Primary text."})
    _write_jowett_store(tmp_path, {"gorgias:453a": "Unrelated entry."})
    manifest = _manifest()
    spine = _spine(["A6"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A6": {"context_spans": [_plato_span("Hippias Major", "281a")]},
    })
    out_path = sce.run(manifest, spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A6"][0]
    assert "alts" not in span


def test_jowett_multi_locus_ordering_matches_section_loci(tmp_path):
    # Deliberately write the Jowett store with keys in a DIFFERENT order
    # than the span's own loci, and confirm `sections` still follows
    # sectionLoci order, not store insertion order.
    _write_plato_store(tmp_path, {
        "hippias-minor:363c": "Primary c.",
        "hippias-minor:363d": "Primary d.",
        "hippias-minor:364a": "Primary a.",
    })
    _write_jowett_store(tmp_path, {
        "hippias-minor:364a": "Jowett a.",
        "hippias-minor:363c": "Jowett c.",
        "hippias-minor:363d": "Jowett d.",
    })
    manifest = _manifest()
    spine = _spine(["A8"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A8": {"context_spans": [_plato_span("Hippias Minor", "363c-364a")]},
    })
    out_path = sce.run(manifest, spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A8"][0]
    assert span["sectionLoci"] == ["363c", "363d", "364a"]
    assert [s["locus"] for s in span["alts"][0]["sections"]] == [
        "363c", "363d", "364a",
    ]


# --- Six dialogues vendored 2026-07-28 (Laws, Republic, Parmenides, Crito, -
# Euthyphro, Ion): registry entries resolve against the REAL vendored store,
# using the resolver directly (no hand-authored sidecar names these
# dialogues yet, so _run_against_real_sources's declared-column approach
# doesn't apply here).

@pytest.mark.parametrize("work,slug,locus,starts_with", [
    ("Crito", "crito", "43a", "Socrates. Why have you come at this time, Crito?"),
    ("Euthyphro", "euthyphro", "2a", "Euthyphro. What strange thing has happened, Socrates,"),
    ("Ion", "ion", "530a", "Soc. Welcome, Ion."),
    ("Laws", "laws", "889b", "Ath. I will explain it more clearly."),
    ("Parmenides", "parmenides", "127a", "Thereupon we started, and we found Antiphon at home,"),
    ("Republic", "republic", "327a", "I went down yesterday to the Peiraeus"),
])
def test_new_dialogue_locus_resolves_against_real_store(
    monkeypatch, work, slug, locus, starts_with
):
    # No hand-authored sidecar names these six dialogues yet, so this reads
    # the resolver directly off the registry rather than going through a
    # declaration file (matching how this module's low-level tests exercise
    # `_PLATO_DIALOGUES`/`_resolve_plato` elsewhere).
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    registered_slug, credit = sce._PLATO_DIALOGUES[work]
    assert registered_slug == slug
    assert credit
    resolver = sce._resolve_plato(registered_slug)
    text, _section_loci = resolver(locus)
    assert text.startswith(starts_with)


def test_republic_books_6_to_10_resolve(monkeypatch):
    # Shorey's Republic vol. 2 (Books 6-10, Stephanus 484-621) was published
    # 1935 -- not US public domain by date -- but the project owner ruled a
    # pre-1940 line for this vendoring, 2026-07-28 ("No. Pre 1940. Do it.").
    # `600a` (Book 10) must now resolve like any other locus in the store.
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolver = sce._resolve_plato("republic")
    text, _section_loci = resolver("600a")
    assert text.strip()


def test_republic_covers_all_ten_books(monkeypatch):
    # Book 5 ends at Stephanus page 480; Book 6 begins at 484 (first page of
    # the 1935 volume); Book 10 runs to 621. Pin the full span so a future
    # re-extraction can't silently regress back to the Books 1-5 cutoff.
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    store = sce._load_plato()
    republic_pages = sorted(
        int(re.match(r"^\d+", k[len("republic:"):]).group())
        for k in store
        if k.startswith("republic:")
    )
    assert 327 in republic_pages
    assert 480 in republic_pages
    assert 484 in republic_pages
    assert max(republic_pages) >= 621


# --- Store integrity: every key in both flat stores is well-formed --------

def test_plato_store_keys_are_all_well_formed(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    store = sce._load_plato()
    assert store, "plato-stephanus.clean.json must not be empty"
    key_re = re.compile(r"^[a-z][a-z-]*:\d+[a-e]$")
    for key, text in store.items():
        assert key_re.fullmatch(key), f"malformed store key {key!r}"
        assert isinstance(text, str) and text.strip(), f"{key!r}: empty text"
    for expected_slug in (
        "crito", "euthyphro", "ion", "laws", "parmenides", "republic",
    ):
        assert any(k.startswith(f"{expected_slug}:") for k in store), (
            f"{expected_slug!r} has no entries in plato-stephanus.clean.json"
        )


def test_jowett_store_keys_are_all_well_formed(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    jowett = sce._load_jowett()
    assert jowett, "jowett-stephanus.clean.json must not be empty"
    key_re = re.compile(r"^[a-z][a-z-]*:\d+[a-e]$")
    for key, text in jowett.items():
        assert key_re.fullmatch(key), f"malformed jowett key {key!r}"
        if text is not None:
            assert isinstance(text, str)
    for expected_slug in ("crito", "euthyphro", "ion"):
        assert any(k.startswith(f"{expected_slug}:") for k in jowett), (
            f"{expected_slug!r} has no Jowett-aligned entries"
        )
    # Laws, Republic, Parmenides are not turn-aligned to Jowett in
    # plato-reader's build (deferred there); nothing to assert PRESENT, but
    # confirm the extractor didn't fabricate entries for them either.
    for undeferred_slug in ("laws", "republic", "parmenides"):
        assert not any(k.startswith(f"{undeferred_slug}:") for k in jowett), (
            f"{undeferred_slug!r} unexpectedly has Jowett entries -- "
            "plato-reader has no turn alignment for it"
        )


def test_jowett_single_locus_span_still_produces_one_section(tmp_path):
    _write_plato_store(tmp_path, {"hippias-major:281a": "Primary text."})
    _write_jowett_store(tmp_path, {"hippias-major:281a": "Jowett text."})
    manifest = _manifest()
    spine = _spine(["A6"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A6": {"context_spans": [_plato_span("Hippias Major", "281a")]},
    })
    out_path = sce.run(manifest, spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A6"][0]
    assert span["alts"] == [{
        "id": "jowett",
        "label": "Jowett",
        "translationCredit": (
            "Benjamin Jowett, The Dialogues of Plato, 3rd ed., Oxford, 1892"
        ),
        "sections": [{"locus": "281a", "text": "Jowett text."}],
    }]
