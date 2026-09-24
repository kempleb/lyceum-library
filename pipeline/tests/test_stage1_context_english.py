"""Regression tests for stage1_context_english.py (docs/source-passage-
english-scoping.md's implementation): unknown-column / missing-field /
bad-status fatal gates, the Diogenes Laertius locus resolver (single
section and inclusive range), desert spans, the work-declares-nothing
no-op path, the (source_author, source_work) resolver registry (a
Hicks-shaped locus under the WRONG source_work must not resolve), locus
syntax validation, the empty-declaration fatal gate, and integration
coverage pinning the real pilot sidecars (sources/thales-testimonia,
sources/thales-fragments) against sources/hicks-dl/hicks-lives.clean.json,
hand-verified independently of this module's own code."""

from __future__ import annotations

import hashlib
import json
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


def _manifest(work_id="thales-testimonia") -> Manifest:
    return Manifest({"work": {"id": work_id}}, Path("FIX.yaml"))


def _write_hicks(tmp_path, sections: dict[str, str]) -> None:
    p = tmp_path / "hicks-dl" / "hicks-lives.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sections), encoding="utf-8")


def _write_declaration(tmp_path, work_id: str, declared: dict) -> None:
    p = tmp_path / work_id / "context-english.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(declared), encoding="utf-8")


@pytest.fixture(autouse=True)
def _patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", tmp_path)
    monkeypatch.setattr(sce, "BUILD_DIR", tmp_path / "build")
    return tmp_path


def test_no_declaration_file_is_a_no_op(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    assert sce.run(manifest, spine) is None


def test_unknown_column_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A2": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.22", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    with pytest.raises(ValueError, match="match no spine segment"):
        sce.run(manifest, spine)


def test_missing_required_field_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    with pytest.raises(ValueError, match="missing required field"):
        sce.run(manifest, spine)


def test_bad_status_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.22", "status": "lost"},
        ]},
    })
    with pytest.raises(ValueError, match="expected 'translated' or 'desert'"):
        sce.run(manifest, spine)


def test_translated_without_credit_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.22", "status": "translated"},
        ]},
    })
    with pytest.raises(ValueError, match="no non-empty translation_credit"):
        sce.run(manifest, spine)


def test_desert_with_credit_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Sextus Empiricus", "source_work": "Adv. Math.",
             "locus": "VII 132", "status": "desert",
             "translation_credit": "should not be here"},
        ]},
    })
    with pytest.raises(ValueError, match="has no translation to credit"):
        sce.run(manifest, spine)


def test_unsupported_source_author_translated_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Aristotle", "source_work": "Metaphysics",
             "locus": "983b6", "status": "translated",
             "translation_credit": "Ross, 1924"},
        ]},
    })
    with pytest.raises(ValueError, match="no locus resolver"):
        sce.run(manifest, spine)


def test_known_author_wrong_source_work_is_fatal(tmp_path):
    # Finding 1 (adversarial review): a resolver keyed by author ALONE would
    # let a Hicks-shaped locus resolve under a source_work the sidecar never
    # meant (e.g. "Metaphysics" instead of "Lives of Eminent Philosophers")
    # -- a false credit. Registered by the (author, work) PAIR, this must be
    # exactly as fatal as an unknown author, never a silent resolve.
    _write_hicks(tmp_path, {"1.22": "Section 22 text."})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius", "source_work": "Metaphysics",
             "locus": "1.22", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    with pytest.raises(ValueError, match="no locus resolver"):
        sce.run(manifest, spine)


@pytest.mark.parametrize("locus", ["1.+22-040", "1.22- 40", "1.22-", "-1.22", "1.a2"])
def test_malformed_locus_syntax_is_fatal(tmp_path, locus):
    # Finding 2: locus syntax must full-match before resolution -- Python's
    # int() tolerance (leading '+', embedded whitespace) must not let a
    # malformed locus slip through as if it were a well-formed range.
    _write_hicks(tmp_path, {"1.22": "Section 22.", "1.40": "Section 40."})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": locus, "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    with pytest.raises(ValueError, match="is not valid"):
        sce.run(manifest, spine)


def test_empty_declaration_is_fatal(tmp_path):
    # Finding 3: an empty top-level `{}` must not silently look like
    # intentional "no context English" coverage -- it reads as a truncated
    # sidecar and must be fatal.
    _write_declaration(tmp_path, "thales-testimonia", {})
    manifest = _manifest()
    spine = _spine(["A1"])
    with pytest.raises(ValueError, match="must not be empty"):
        sce.run(manifest, spine)


def test_unresolvable_locus_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.22": "Section 22 text."})
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    with pytest.raises(ValueError, match="not a key in"):
        sce.run(manifest, spine)


def test_resolves_single_section_locus(tmp_path):
    _write_hicks(tmp_path, {"1.23": "After engaging in politics..."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    span = resolved["1:B4"][0]
    assert span == {
        "sourceAuthor": "Diogenes Laertius",
        "sourceWork": "Lives of Eminent Philosophers",
        "locus": "1.23",
        "status": "translated",
        "translationCredit": "Hicks, 1925",
        "text": "After engaging in politics...",
    }


def test_resolves_range_locus_by_concatenating_sections_in_order(tmp_path):
    _write_hicks(tmp_path, {
        "1.22": "Section 22.", "1.23": "Section 23.", "1.24": "Section 24.",
    })
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.22-24", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert resolved["1:A1"][0]["text"] == "Section 22.\n\nSection 23.\n\nSection 24."
    # UX (adversarial review): a range locus's per-paragraph DL section
    # markers, one per resolved Hicks key, in order.
    assert resolved["1:A1"][0]["sectionLoci"] == ["1.22", "1.23", "1.24"]


def test_single_section_locus_carries_no_section_loci(tmp_path):
    # A single-section locus needs no per-paragraph marker -- the span's
    # own `locus` already names the one section, and its credit line
    # already shows it (Reader.svelte's `.context-english-credit`).
    _write_hicks(tmp_path, {"1.23": "Section 23 text."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert "sectionLoci" not in resolved["1:B4"][0]


def test_desert_span_carries_no_text_or_credit(tmp_path):
    manifest = _manifest()
    spine = _spine(["A3"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A3": {"context_spans": [
            {"source_author": "Scholiast on Plato", "source_work": "in Remp.",
             "locus": "600A", "status": "desert"},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert resolved["1:A3"][0] == {
        "sourceAuthor": "Scholiast on Plato",
        "sourceWork": "in Remp.",
        "locus": "600A",
        "status": "desert",
    }


# --- Integration: the REAL pilot sidecars against the REAL Hicks store ----
# (Finding 4, adversarial review). These read sources/thales-testimonia/
# context-english.json, sources/thales-fragments/context-english.json, and
# sources/hicks-dl/hicks-lives.clean.json directly off disk (bypassing the
# _patch_dirs autouse fixture's tmp_path redirection) so a real regression
# in either the pilot declarations or the vendored Hicks store itself would
# fail these tests. Expected values were computed independently of this
# module's own code (uv run python3, reading hicks-lives.clean.json
# directly) and hand-verified before being written here.

def _run_against_real_sources(work_id: str, columns: list[str]) -> dict:
    manifest = _manifest(work_id)
    spine = _spine(columns)
    out_path = sce.run(manifest, spine)
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_real_thales_testimonia_A1_declares_the_full_hicks_range(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources("thales-testimonia", ["A1", "A9"])
    span = resolved["1:A1"][0]
    # The declared locus is the literal range DK carries forward from Hicks
    # 1.22 through 1.40 -- 19 consecutive Loeb sections.
    assert span["locus"] == "1.22-40"
    assert span["sourceAuthor"] == "Diogenes Laertius"
    assert span["sourceWork"] == "Lives of Eminent Philosophers"
    assert span["status"] == "translated"
    assert span["translationCredit"] == "Hicks, 1925"
    assert span["sectionLoci"] == [f"1.{n}" for n in range(22, 41)]
    assert len(span["sectionLoci"]) == 19
    text = span["text"]
    assert text.startswith(
        "Herodotus, Duris, and Democritus are agreed that Thales was the "
        "son of Examyas and Cleobulina, and belonged to the Thelidae"
    )
    assert text.endswith(
        "Some make them meet at the Pan-Ionian festival, at Corinth, and "
        "at Delphi."
    )
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == (
        "14d593bc7fc2dd800667f31d2bf5f09402be165e54438227f3498dffc50cbcd6"
    )


# --- REVIEW-CHECKLIST item 83: source-passage excerpt emphasis -----------

def test_single_emphasis_substring_emits_verbatim(tmp_path):
    _write_hicks(tmp_path, {"1.23": "After engaging in politics he retired."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["engaging in politics"]},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert resolved["1:B4"][0] == {
        "sourceAuthor": "Diogenes Laertius",
        "sourceWork": "Lives of Eminent Philosophers",
        "locus": "1.23",
        "status": "translated",
        "translationCredit": "Hicks, 1925",
        "text": "After engaging in politics he retired.",
        "emphasis": ["engaging in politics"],
    }


def test_multiple_emphasis_substrings_in_text_order(tmp_path):
    _write_hicks(tmp_path, {"1.23": "First he did this, and then he did that."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["First he did this", "then he did that"]},
        ]},
    })
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    assert resolved["1:B4"][0]["emphasis"] == [
        "First he did this", "then he did that",
    ]


def test_span_without_emphasis_emits_byte_identically(tmp_path):
    _write_hicks(tmp_path, {"1.23": "Plain text, no emphasis declared."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    declared = {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925"},
        ]},
    }
    _write_declaration(tmp_path, "thales-fragments", declared)
    out_path = sce.run(manifest, spine)
    resolved = json.loads(out_path.read_text(encoding="utf-8"))
    span = resolved["1:B4"][0]
    assert "emphasis" not in span
    assert span == {
        "sourceAuthor": "Diogenes Laertius",
        "sourceWork": "Lives of Eminent Philosophers",
        "locus": "1.23",
        "status": "translated",
        "translationCredit": "Hicks, 1925",
        "text": "Plain text, no emphasis declared.",
    }


def test_empty_emphasis_string_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "Some resolved text here."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["   "]},
        ]},
    })
    with pytest.raises(ValueError, match="must be a non-empty string"):
        sce.run(manifest, spine)


def test_emphasis_substring_absent_from_text_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "Some resolved text here."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["not in the text anywhere"]},
        ]},
    })
    with pytest.raises(ValueError, match="does not occur in the resolved English text"):
        sce.run(manifest, spine)


def test_emphasis_substring_occurring_twice_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "he said this and he said this again."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["he said this"]},
        ]},
    })
    with pytest.raises(ValueError, match="occurs 2 times"):
        sce.run(manifest, spine)


def test_overlapping_emphasis_substrings_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "The quick brown fox jumps."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["quick brown", "brown fox"]},
        ]},
    })
    with pytest.raises(ValueError, match="overlap"):
        sce.run(manifest, spine)


def test_emphasis_substrings_out_of_text_order_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "First he did this, and then he did that."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["then he did that", "First he did this"]},
        ]},
    })
    with pytest.raises(ValueError, match="declared in the order they occur"):
        sce.run(manifest, spine)


def test_emphasis_on_desert_span_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A3"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A3": {"context_spans": [
            {"source_author": "Scholiast on Plato", "source_work": "in Remp.",
             "locus": "600A", "status": "desert",
             "emphasis": ["anything"]},
        ]},
    })
    with pytest.raises(ValueError, match="there is no resolved English text to emphasize"):
        sce.run(manifest, spine)


def test_empty_emphasis_list_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "Some resolved text here."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": []},
        ]},
    })
    with pytest.raises(ValueError, match="must be a non-empty list of strings"):
        sce.run(manifest, spine)


def test_real_thales_fragments_B4_declares_hicks_1_23(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    resolved = _run_against_real_sources("thales-fragments", ["B4"])
    span = resolved["1:B4"][0]
    assert span["locus"] == "1.23"
    assert span["sourceAuthor"] == "Diogenes Laertius"
    assert span["sourceWork"] == "Lives of Eminent Philosophers"
    assert span["status"] == "translated"
    assert span["translationCredit"] == "Hicks, 1925"
    assert "sectionLoci" not in span
    text = span["text"]
    assert text.startswith(
        "After engaging in politics he became a student of nature. "
        "According to some he left nothing in writing"
    )
    assert text.endswith(
        "It was this which gained for him the admiration of Xenophanes "
        "and Herodotus and the notice of Heraclitus and Democritus."
    )
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == (
        "6f32776c2170b50ed5d22a139e7529346742012ebdfe1eec9781b552f16fa806"
    )
