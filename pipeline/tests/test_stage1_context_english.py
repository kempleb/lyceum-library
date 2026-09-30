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
    # Aristotle/Metaphysics is registered. This pins a pair that still has
    # no resolver, which must stay fatal in the same way.
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Sextus Empiricus",
             "source_work": "Against the Logicians",
             "locus": "VII 132", "status": "translated",
             "translation_credit": "Bury, 1935"},
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


def _head_spine(line_text: str) -> dict:
    spine = _spine(["A12"])
    spine["segments"][0]["lines"] = [{"n": 1, "text": line_text}]
    return spine


def _head_declaration(tmp_path, head) -> None:
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A12": {"context_spans": [
            {"source_author": "Aëtius", "source_work": "Placita",
             "locus": "2.22", "status": "desert", "head": head},
        ]},
    })


def test_head_is_emitted_as_head_text(tmp_path):
    _head_declaration(tmp_path, "—22, 2 (D. 352)")
    spine = _head_spine("λόγος. —II 20, 16 (D. 351) λόγος. —22, 2 (D. 352) λόγος.")
    resolved = json.loads(sce.run(_manifest(), spine).read_text(encoding="utf-8"))
    assert resolved["1:A12"][0]["headText"] == "—22, 2 (D. 352)"


def test_head_not_printed_in_the_column_is_fatal(tmp_path):
    _head_declaration(tmp_path, "—24, 3 (D. 354)")
    spine = _head_spine("λόγος. —22, 2 (D. 352) λόγος.")
    with pytest.raises(ValueError, match="does not occur in the column's Greek"):
        sce.run(_manifest(), spine)


@pytest.mark.parametrize("head", ["", "  ", 3])
def test_head_must_be_a_non_empty_string(tmp_path, head):
    _head_declaration(tmp_path, head)
    with pytest.raises(ValueError, match="head must be a non-empty string"):
        sce.run(_manifest(), _head_spine("λόγος."))


# --- Integration: the REAL pilot sidecars against the REAL Hicks store ----
# (Finding 4, adversarial review). These read sources/thales-testimonia/
# context-english.json, sources/thales-fragments/context-english.json, and
# sources/hicks-dl/hicks-lives.clean.json directly off disk (bypassing the
# _patch_dirs autouse fixture's tmp_path redirection) so a real regression
# in either the pilot declarations or the vendored Hicks store itself would
# fail these tests. Expected values were computed independently of this
# module's own code (uv run python3, reading hicks-lives.clean.json
# directly) and hand-verified before being written here.

def _real_spine(declared: dict, columns: list[str] | None = None) -> dict:
    """A spine for a real sidecar. The Greek is not in the repository: each
    column gets one stand-in line printing the headings its spans name, so
    the `head` check passes."""
    spine = _spine(columns or [key.split(":", 1)[1] for key in declared])
    for seg in spine["segments"]:
        heads = [s["head"] for s in declared.get(seg["id"], {}).get("context_spans", [])
                 if "head" in s]
        seg["lines"] = [{"n": 1, "text": " ".join(heads)}]
    return spine


def _run_against_real_sources(work_id: str, columns: list[str]) -> dict:
    manifest = _manifest(work_id)
    declared = json.loads(
        (sce.SOURCES_DIR / work_id / "context-english.json").read_text(encoding="utf-8")
    )
    spine = _real_spine(declared, columns)
    out_path = sce.run(manifest, spine)
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_real_thales_testimonia_A1_declares_the_full_hicks_range(monkeypatch):
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    # Spine columns come from the sidecar itself. A later column (an Aristotle
    # span, authored separately) must not make this A1 pin fail the
    # unknown-column gate.
    declared = json.loads(
        (REAL_SOURCES_DIR / "thales-testimonia" / "context-english.json").read_text(
            encoding="utf-8"
        )
    )
    columns = [key.split(":", 1)[1] for key in declared]
    resolved = _run_against_real_sources("thales-testimonia", columns)
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
    # Trimmed to what DK quotes (owner ruling, 2026-09-27): DK's 1.40 stops
    # at Chilon, so the English stops there too, with "…" at the cut.
    assert text.endswith("though admitting that it was appropriated by Chilon.…")
    assert "Some make them meet at the Pan-Ionian festival" not in text
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == (
        "2907b9c9f28a12f7f635b2b450eb2108b56d32d7e2d2ceacb36f285456f3ee01"
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
    # Trimmed to the one sentence DK quotes (owner ruling, 2026-09-27).
    assert span["text"] == (
        "…But according to others he wrote nothing but two treatises, one On "
        "the Solstice and one On the Equinox, regarding all other matters as "
        "incognizable.…"
    )
    assert hashlib.sha256(span["text"].encode("utf-8")).hexdigest() == (
        "6a4fffcd15551983b7ead2d22a238424fbf3fdf0139a21ed8b5e5b975cf561cd"
    )


# --- Aristotle Bekker resolver and emphasis trim (docs/aristotle-context-
# english-design.md D and B.4, as amended in H: the sentences that hold the
# bold, and no sentence beyond them). Invented columns and invented English
# only. Geometry is asserted on the resolver's pre-trim window.


def _write_aristotle(tmp_path, segments: dict) -> None:
    p = tmp_path / "aristotle-english" / "aristotle-english.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(segments), encoding="utf-8")


def _write_plato(tmp_path, sections: dict) -> None:
    p = tmp_path / "perseus-plato" / "plato-stephanus.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sections), encoding="utf-8")


def _col(lines: list, text: str) -> dict:
    return {"lines": lines, "text": text}


def _window_store() -> dict:
    return {
        "Meta:1:10a": _col([1, 2], "Alpha one. Alpha two."),
        "Meta:1:10b": _col([1, 2, 5], "Beta one. Beta two."),
        "Meta:1:11a": _col([1, 2], "Gamma one. Gamma two."),
        "Meta:1:11b": _col([1], "Delta one."),
        "Meta:1:12a": _col([1], "Epsilon one."),
    }


def _resolve_meta(locus: str):
    return sce._resolve_aristotle("Meta")(locus)


def _aristotle_declaration(locus: str, emphasis) -> dict:
    span = {
        "source_author": "Aristotle",
        "source_work": "Metaphysics",
        "locus": locus,
        "status": "translated",
        "translation_credit": "Ross, 1924",
    }
    if emphasis is not None:
        span["emphasis"] = emphasis
    return {"1:A1": {"context_spans": [span]}}


def _write_aristotle_alternates(tmp_path, passages=None, work="Metaphysics",
                                credit="M'Mahon, 1857") -> None:
    if passages is None:
        passages = {
            "986a22-986b2": "First sentence. The missing clause appears here. Last sentence."
        }
    path = tmp_path / "aristotle-english" / "alternates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "mmahon": {"work": work, "credit": credit, "passages": passages}
    }), encoding="utf-8")


def _alternate_span(locus="986a29", **changes) -> dict:
    span = _aristotle_declaration(locus, ["missing clause"])["1:A1"]["context_spans"][0]
    span.update({"translation": "mmahon", "translation_credit": "M'Mahon, 1857"})
    span.update(changes)
    return span


def _run_alternate(tmp_path, span: dict) -> dict:
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [span]}
    })
    path = sce.run(_manifest(), _spine(["A1"]))
    return json.loads(path.read_text(encoding="utf-8"))["1:A1"][0]


def test_aristotle_alternate_resolves_and_trims_without_bekker_store(tmp_path):
    _write_aristotle_alternates(tmp_path)
    span = _run_alternate(tmp_path, _alternate_span())
    assert span["text"] == "…The missing clause appears here.…"
    assert span["emphasis"] == ["missing clause"]
    assert span["translationCredit"] == "M'Mahon, 1857"
    assert list(span) == ["sourceAuthor", "sourceWork", "locus", "status",
                          "translationCredit", "text", "emphasis"]
    assert "sectionLoci" not in span
    assert "translation" not in span
    assert "alts" not in span
    assert not (tmp_path / "aristotle-english" / "aristotle-english.clean.json").exists()


def test_aristotle_alternate_range_inside_passage_resolves(tmp_path):
    _write_aristotle_alternates(tmp_path)
    span = _run_alternate(tmp_path, _alternate_span("986a27-986a34"))
    assert span["text"] == "…The missing clause appears here.…"


@pytest.mark.parametrize("locus", ["914b9-915a19", "915a4"])
def test_pseudo_aristotle_problemata_alternate_resolves_and_trims(tmp_path, locus):
    path = tmp_path / "aristotle-english" / "alternates.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "forster-1927": {
            "work": "Problemata",
            "credit": "Forster, 1927",
            "passages": {
                "914b9-915a19": "First sentence. The middle thought appears here. Last sentence."
            },
        },
    }), encoding="utf-8")
    span = _run_alternate(tmp_path, _alternate_span(
        locus, source_author="pseudo-Aristotle", source_work="Problemata",
        translation="forster-1927", translation_credit="Forster, 1927",
        emphasis=["middle thought"],
    ))
    assert span["text"] == "…The middle thought appears here.…"
    assert span["emphasis"] == ["middle thought"]
    assert span["translationCredit"] == "Forster, 1927"
    assert "sectionLoci" not in span
    assert not (tmp_path / "aristotle-english" / "aristotle-english.clean.json").exists()


def test_pseudo_aristotle_problemata_without_translation_is_fatal(tmp_path):
    span = _alternate_span(
        "914b9-915a19", source_author="pseudo-Aristotle",
        source_work="Problemata", translation_credit="Forster, 1927",
    )
    span.pop("translation")
    with pytest.raises(ValueError, match="no stored translation"):
        _run_alternate(tmp_path, span)


def test_aristotle_problemata_with_translation_is_fatal(tmp_path):
    assert ("Aristotle", "Problemata") not in sce._RESOLVERS
    with pytest.raises(ValueError, match="only allowed"):
        _run_alternate(tmp_path, _alternate_span(
            "914b9-915a19", source_work="Problemata",
            translation="forster-1927", translation_credit="Forster, 1927",
        ))


@pytest.mark.parametrize("translation", [None, "", "  ", 42])
def test_aristotle_alternate_translation_id_must_be_nonempty_string(tmp_path, translation):
    with pytest.raises(ValueError, match="context-english.json\\['1:A1'\\].*non-empty string"):
        _run_alternate(tmp_path, _alternate_span(translation=translation))


def test_aristotle_alternate_only_allowed_on_aristotle_pair(tmp_path):
    with pytest.raises(ValueError, match="context-english.json\\['1:A1'\\].*only allowed"):
        _run_alternate(tmp_path, _alternate_span(
            source_author="Diogenes Laertius", source_work="Lives of Eminent Philosophers"
        ))


def test_aristotle_alternate_unknown_id_is_fatal(tmp_path):
    _write_aristotle_alternates(tmp_path)
    with pytest.raises(ValueError, match="not in alternates.json"):
        _run_alternate(tmp_path, _alternate_span(translation="unknown"))


def test_aristotle_alternate_missing_file_is_fatal(tmp_path):
    with pytest.raises(ValueError, match="alternates file is missing"):
        _run_alternate(tmp_path, _alternate_span())


def test_aristotle_alternate_wrong_work_is_fatal(tmp_path):
    _write_aristotle_alternates(tmp_path, work="Physics")
    with pytest.raises(ValueError, match="is for 'Physics', not 'Metaphysics'"):
        _run_alternate(tmp_path, _alternate_span())


def test_aristotle_alternate_wrong_credit_is_fatal(tmp_path):
    _write_aristotle_alternates(tmp_path)
    with pytest.raises(ValueError, match="credit does not match"):
        _run_alternate(tmp_path, _alternate_span(translation_credit="Ross, 1928"))


def test_aristotle_alternate_bad_locus_is_fatal(tmp_path):
    _write_aristotle_alternates(tmp_path)
    with pytest.raises(ValueError, match="Aristotle locus .* is not valid"):
        _run_alternate(tmp_path, _alternate_span("986a29-34"))


@pytest.mark.parametrize("passages, expected", [
    ({"986a22-986a28": "Too short."}, "in 0 passages"),
    ({"986a22-986b2": "First.", "986a25-986a34": "Second."}, "in 2 passages"),
])
def test_aristotle_alternate_requires_one_containing_passage(tmp_path, passages, expected):
    _write_aristotle_alternates(tmp_path, passages=passages)
    with pytest.raises(ValueError, match=expected):
        _run_alternate(tmp_path, _alternate_span())


def test_aristotle_alternate_on_desert_is_fatal(tmp_path):
    span = _alternate_span(status="desert")
    span.pop("translation_credit")
    with pytest.raises(ValueError, match="desert span names no translation"):
        _run_alternate(tmp_path, span)


def test_aristotle_single_line_includes_neighbours(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    text, loci = _resolve_meta("10b5")
    assert loci == ["10a", "10b", "11a"]
    assert text == "Alpha one. Alpha two.\n\nBeta one. Beta two.\n\nGamma one. Gamma two."
    assert all(not loc[-1].isdigit() for loc in loci)


def test_aristotle_same_column_range_includes_neighbours(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    text, loci = _resolve_meta("10b1-10b5")
    assert loci == ["10a", "10b", "11a"]
    assert "Beta one. Beta two." in text


def test_aristotle_cross_column_range_includes_neighbours(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    _text, loci = _resolve_meta("10b1-11a1")
    assert loci == ["10a", "10b", "11a", "11b"]
    assert all(not loc[-1].isdigit() for loc in loci)


def test_aristotle_three_segment_range_is_allowed_and_four_is_fatal(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    _text, loci = _resolve_meta("10a1-11a1")
    assert loci == ["10a", "10b", "11a", "11b"]
    with pytest.raises(ValueError, match="more than 3"):
        _resolve_meta("10a1-11b1")


def test_aristotle_book_split_column_picks_the_half_that_holds_the_line(tmp_path):
    _write_aristotle(tmp_path, {
        "Meta:3:10a": _col([1], "Before split."),
        "Meta:3:10b": _col([1, 2], "Book three half."),
        "Meta:4:10b": _col([20, 30], "Book four half."),
        "Meta:4:11a": _col([1], "After split."),
    })
    text, loci = _resolve_meta("10b30")
    assert loci == ["10b", "10b", "11a"]
    assert text == "Book three half.\n\nBook four half.\n\nAfter split."
    assert "Before split." not in text


def test_aristotle_transposed_line_order_follows_position_in_lines(tmp_path):
    _write_aristotle(tmp_path, {
        "Meta:1:10b": _col([3, 4, 5, 1, 2, 6], "Beta one. Beta two."),
    })
    text, loci = _resolve_meta("10b4-10b1")
    assert loci is None
    assert text == "Beta one. Beta two."
    with pytest.raises(ValueError, match="before"):
        _resolve_meta("10b1-10b4")


def test_aristotle_missing_column_is_fatal(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    with pytest.raises(ValueError, match="not in the store"):
        _resolve_meta("99a1")


def test_aristotle_missing_line_is_fatal(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    with pytest.raises(ValueError, match="not in column"):
        _resolve_meta("10a9")


def test_aristotle_reversed_range_is_fatal(tmp_path):
    _write_aristotle(tmp_path, _window_store())
    with pytest.raises(ValueError, match="before"):
        _resolve_meta("11a1-10a1")


def test_aristotle_empty_segment_inside_range_is_fatal(tmp_path):
    store = _window_store()
    store["Meta:1:10b"] = _col([1, 2, 5], "   ")
    _write_aristotle(tmp_path, store)
    with pytest.raises(ValueError, match="empty English"):
        _resolve_meta("10a1-11a1")


def test_aristotle_empty_neighbour_is_skipped(tmp_path):
    store = _window_store()
    store["Meta:1:10a"] = _col([1, 2], "")
    _write_aristotle(tmp_path, store)
    text, loci = _resolve_meta("10b1")
    assert loci == ["10b", "11a"]
    assert text == "Beta one. Beta two.\n\nGamma one. Gamma two."


@pytest.mark.parametrize("locus", ["10a", "10 a 5", "10a5ff", "10a5-6", "10a5-"])
def test_aristotle_bad_locus_syntax_is_fatal(tmp_path, locus):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", _aristotle_declaration(locus, ["unused"]))
    with pytest.raises(ValueError, match="is not valid"):
        sce.run(manifest, spine)


def test_aristotle_problemata_translated_is_fatal(tmp_path):
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Aristotle", "source_work": "Problemata",
             "locus": "10a1", "status": "translated",
             "translation_credit": "Ross, 1924"},
        ]},
    })
    with pytest.raises(ValueError, match="no locus resolver"):
        sce.run(manifest, spine)


def test_aristotle_translated_without_emphasis_is_fatal(tmp_path):
    _write_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Beta two."),
    })
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", _aristotle_declaration("10a1", None))
    with pytest.raises(ValueError, match="no emphasis"):
        sce.run(manifest, spine)


def _run_aristotle(tmp_path, store: dict, locus: str, emphasis: list) -> dict:
    _write_aristotle(tmp_path, store)
    manifest = _manifest()
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "thales-testimonia", _aristotle_declaration(locus, emphasis))
    out_path = sce.run(manifest, spine)
    return json.loads(out_path.read_text(encoding="utf-8"))["1:A1"][0]


def test_aristotle_trim_keeps_only_the_bold_sentence(tmp_path):
    # H.1 supersedes the earlier "one sentence either side". One sentence,
    # text on both sides: that sentence, with an ellipsis at each cut.
    span = _run_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Beta two. Gamma three."),
    }, "10a1", ["Beta two"])
    assert span["text"] == "…Beta two.…"
    assert "sectionLoci" not in span


def test_aristotle_trim_omits_leading_ellipsis_when_bold_starts_the_text(tmp_path):
    span = _run_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Beta two. Gamma three."),
    }, "10a1", ["Alpha one"])
    assert span["text"] == "Alpha one.…"
    assert not span["text"].startswith("…")


def test_aristotle_range_is_one_passage_without_section_division(tmp_path):
    # Owner ruling, 2026-09-27: no Bekker division; a range spanning columns
    # is one continuous passage (joined with a space), with no sectionLoci.
    span = _run_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Alpha two."),
        "Meta:1:10b": _col([1], "Beta one. Beta two."),
        "Meta:1:11a": _col([1], "Gamma one. Gamma two."),
    }, "10b1", ["Beta two", "Gamma one"])
    assert span["text"] == "…Beta two. Gamma one.…"
    assert "sectionLoci" not in span
    assert "Alpha" not in span["text"]


def test_aristotle_trim_drops_section_loci_when_one_paragraph_remains(tmp_path):
    span = _run_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Alpha two."),
        "Meta:1:10b": _col([1], "Beta one. Beta two."),
        "Meta:1:11a": _col([1], "Gamma one. Gamma two."),
    }, "10b1", ["Beta two"])
    assert span["text"] == "…Beta two.…"
    assert "sectionLoci" not in span


def test_aristotle_sentence_rule(tmp_path):
    cases = [
        ("See e.g. This point holds. Done next.", ["This point"],
         "See e.g. This point holds.…"),
        ("See cf. This note holds. Done next.", ["This note"],
         "See cf. This note holds.…"),
        ("Consult W. D. Ross later today. Stop here.", ["Ross"],
         "Consult W. D. Ross later today.…"),
        ('He stopped. "Go on now." Further words.', ["Go on"],
         '…"Go on now."…'),
        ("Alpha one; beta two. Gamma three.", ["beta two"],
         "Alpha one; beta two.…"),
        # A numbered point opening with "(" starts a new sentence.
        ("Alpha one. (6) Beta two here.", ["Alpha"], "Alpha one.…"),
    ]
    for text, emphasis, expected in cases:
        span = _run_aristotle(tmp_path, {
            "Meta:1:10a": _col([1], text),
        }, "10a1", emphasis)
        assert span["text"] == expected
    # Likewise when the "(" point opens the next column's paragraph: the
    # previous column's last sentence is not pulled in.
    span = _run_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one."),
        "Meta:1:10b": _col([1], "(2) Beta two here."),
    }, "10b1", ["Beta"])
    assert span["text"] == "…(2) Beta two here."


def test_emphasis_containing_a_blank_line_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.23": "Alpha one.\n\nBeta two."})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["Alpha one.\n\nBeta two"]},
        ]},
    })
    with pytest.raises(ValueError, match="blank line"):
        sce.run(manifest, spine)


def test_diogenes_and_plato_spans_are_not_trimmed(tmp_path):
    prose = "Alpha one. Beta two. Gamma three."
    _write_hicks(tmp_path, {"1.23": prose})
    manifest = _manifest("thales-fragments")
    spine = _spine(["B4"])
    _write_declaration(tmp_path, "thales-fragments", {
        "1:B4": {"context_spans": [
            {"source_author": "Diogenes Laertius",
             "source_work": "Lives of Eminent Philosophers",
             "locus": "1.23", "status": "translated",
             "translation_credit": "Hicks, 1925",
             "emphasis": ["Beta two"]},
        ]},
    })
    out_path = sce.run(manifest, spine)
    dl = json.loads(out_path.read_text(encoding="utf-8"))["1:B4"][0]
    assert dl["text"] == prose
    assert "…" not in dl["text"]

    _write_plato(tmp_path, {"apology:10a": prose})
    manifest = _manifest("hippias-testimonia")
    spine = _spine(["A1"])
    _write_declaration(tmp_path, "hippias-testimonia", {
        "1:A1": {"context_spans": [
            {"source_author": "Plato", "source_work": "Apology",
             "locus": "10a", "status": "translated",
             "translation_credit": "Fowler, 1914",
             "emphasis": ["Beta two"]},
        ]},
    })
    out_path = sce.run(manifest, spine)
    plato = json.loads(out_path.read_text(encoding="utf-8"))["1:A1"][0]
    assert plato["text"] == prose
    assert "…" not in plato["text"]
    assert "sectionLoci" not in plato


def test_committed_aristotle_store_covers_registered_works(tmp_path):
    path = REAL_SOURCES_DIR / "aristotle-english" / "aristotle-english.clean.json"
    store = json.loads(path.read_text(encoding="utf-8"))
    assert store
    key_re = re.compile(r"^[A-Za-z]+:\d+:\d+[ab]$")
    abbrs = {abbr for abbr, _credit in sce._ARISTOTLE_WORKS.values()}
    present = set()
    for key, entry in store.items():
        assert key_re.fullmatch(key)
        assert "\n\n" not in entry["text"]
        assert entry["lines"]
        assert all(isinstance(n, int) and not isinstance(n, bool) for n in entry["lines"])
        present.add(key.split(":", 1)[0])
    assert present == abbrs


def test_pseudo_aristotle_pairs_resolve_and_no_others(tmp_path):
    # Invented columns. The three doubtful works share the Aristotle
    # resolver and store; Problemata uses alternates only.
    pseudo = {
        work for author, work in sce._RESOLVERS if author == "pseudo-Aristotle"
    }
    assert pseudo == (set(sce._PSEUDO_ARISTOTLE_TITLES)
                      | set(sce._ALTERNATES_ONLY_PSEUDO_ARISTOTLE_TITLES))
    assert {
        work for author, work in sce._TRIM_TO_EMPHASIS if author == "pseudo-Aristotle"
    } == pseudo
    _write_aristotle(tmp_path, {
        "Mirab:1:10a": _col([1], "Marvel one. Marvel two."),
        "Lin:1:10a": _col([1], "Line one. Line two."),
        "HA:1:10a": _col([1], "Animal one. Animal two."),
    })
    expect = {
        "De Mirabilibus Auscultationibus": ("Mirab", "Dowdall, 1909", "Marvel one. Marvel two."),
        "De Lineis Insecabilibus": ("Lin", "Joachim, 1908", "Line one. Line two."),
        "History of Animals": ("HA", "Thompson, 1910", "Animal one. Animal two."),
    }
    for title, (abbr, credit, text) in expect.items():
        assert sce._ARISTOTLE_WORKS[title] == (abbr, credit)
        pseudo_res = sce._RESOLVERS[("pseudo-Aristotle", title)]
        arist_res = sce._RESOLVERS[("Aristotle", title)]
        assert pseudo_res is arist_res
        got, loci = pseudo_res("10a1")
        assert got == text
        assert loci is None


def test_extractor_table_marks_de_anima_and_poetics_unverified():
    # Smith's De Anima and Fyfe's Poetics are unverified, never
    # public-domain-us. Every other row is the public-domain primary.
    import importlib.util
    tools = Path(__file__).resolve().parent.parent / "tools"
    spec = importlib.util.spec_from_file_location(
        "extract_aristotle_english", tools / "extract_aristotle_english.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._WORKS == {
        "Meta": {"translation_id": "ross", "licence": "public-domain-us"},
        "Phys": {"translation_id": "hardie", "licence": "public-domain-us"},
        "GC": {"translation_id": "joachim", "licence": "public-domain-us"},
        "Cael": {"translation_id": "stocks", "licence": "public-domain-us"},
        "Mete": {"translation_id": "webster", "licence": "public-domain-us"},
        "Rhet": {"translation_id": "freese", "licence": "public-domain-us"},
        "GA": {"translation_id": "platt", "licence": "public-domain-us"},
        "PA": {"translation_id": "ogle", "licence": "public-domain-us"},
        "Sens": {"translation_id": "beare", "licence": "public-domain-us"},
        "EN": {"translation_id": "rackham", "licence": "public-domain-us"},
        "Juv": {"translation_id": "ross", "licence": "public-domain-us"},
        "SE": {"translation_id": "pickard", "licence": "public-domain-us"},
        "HA": {"translation_id": "thompson", "licence": "public-domain-us"},
        "Top": {"translation_id": "pickard", "licence": "public-domain-us"},
        "Pol": {"translation_id": "jowett", "licence": "public-domain-us"},
        "Mirab": {"translation_id": "dowdall", "licence": "public-domain-us"},
        "Lin": {"translation_id": "joachim", "licence": "public-domain-us"},
        "DA": {"translation_id": "smith", "licence": "unverified"},
        "Poet": {"translation_id": "fyfe", "licence": "unverified"},
    }
    for abbr in ("DA", "Poet"):
        assert mod._WORKS[abbr]["licence"] == "unverified"
        assert mod._WORKS[abbr]["licence"] != "public-domain-us"


def _load_aristotle_extractor():
    import importlib.util
    tools = Path(__file__).resolve().parent.parent / "tools"
    spec = importlib.util.spec_from_file_location(
        "extract_aristotle_english", tools / "extract_aristotle_english.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_corrections_match_the_store():
    # The committed list is well-formed, and each replacement is present in
    # the committed column it names. Invented-text behaviour of the apply
    # step is test_extractor_correction_step_on_invented_text.
    path = REAL_SOURCES_DIR / "aristotle-english" / "corrections.json"
    store_path = REAL_SOURCES_DIR / "aristotle-english" / "aristotle-english.clean.json"
    corrections = json.loads(path.read_text(encoding="utf-8"))
    store = json.loads(store_path.read_text(encoding="utf-8"))
    key_re = re.compile(r"^[A-Za-z]+:\d+:\d+[ab]$")
    assert isinstance(corrections, list) and corrections
    for entry in corrections:
        assert set(entry) >= {"key", "find", "replace", "source"}
        assert key_re.fullmatch(entry["key"])
        assert isinstance(entry["find"], str) and entry["find"]
        assert isinstance(entry["replace"], str) and entry["replace"]
        assert isinstance(entry["source"], str) and entry["source"].strip()
        assert entry["replace"] in store[entry["key"]]["text"]


def test_extractor_correction_step_on_invented_text():
    mod = _load_aristotle_extractor()
    store = {"Fix:1:10a": {"lines": [1], "text": "Alpha one. Beta two."}}
    mod._apply_corrections(store, [{
        "key": "Fix:1:10a",
        "find": "Beta two",
        "replace": "Beta two now",
        "source": "invented",
    }])
    assert store["Fix:1:10a"]["text"] == "Alpha one. Beta two now."
    # A second pass must not find the old words.
    with pytest.raises(SystemExit, match="occurs 0 times"):
        mod._apply_corrections(store, [{
            "key": "Fix:1:10a",
            "find": "Beta two.",
            "replace": "Beta two now.",
        }])
    doubled = {"Fix:1:10a": {"lines": [1], "text": "Beta here. Beta there."}}
    with pytest.raises(SystemExit, match="occurs 2 times"):
        mod._apply_corrections(doubled, [{
            "key": "Fix:1:10a",
            "find": "Beta",
            "replace": "Gamma",
        }])
    missing = {"Fix:1:10a": {"lines": [1], "text": "Alpha only."}}
    with pytest.raises(SystemExit, match="not in the store"):
        mod._apply_corrections(missing, [{
            "key": "Fix:1:10b",
            "find": "Alpha",
            "replace": "Beta",
        }])
    blank = {"Fix:1:10a": {"lines": [1], "text": "Alpha one. Beta two."}}
    with pytest.raises(SystemExit, match="blank line"):
        mod._apply_corrections(blank, [{
            "key": "Fix:1:10a",
            "find": "one. Beta",
            "replace": "one.\n\nBeta",
        }])


# --- Trim to what DK quotes (owner ruling, 2026-09-27): sidecar `trim` ----
# (`start`, `end`, `omit`) and `alt_trims`. Invented text only, except the
# Heraclitus A6 pin against the real sidecar and stores.


def _dl_span(locus: str, **extra) -> dict:
    span = {
        "source_author": "Diogenes Laertius",
        "source_work": "Lives of Eminent Philosophers",
        "locus": locus, "status": "translated",
        "translation_credit": "Hicks, 1925",
    }
    span.update(extra)
    return span


def _run_one(tmp_path, span: dict, work_id="thales-testimonia") -> dict:
    _write_declaration(tmp_path, work_id, {"1:A1": {"context_spans": [span]}})
    out_path = sce.run(_manifest(work_id), _spine(["A1"]))
    return json.loads(out_path.read_text(encoding="utf-8"))["1:A1"][0]


def _three_sections(tmp_path) -> None:
    _write_hicks(tmp_path, {
        "1.1": "Lead in. Alpha one. Alpha two.",
        "1.2": "Beta one. Beta two.",
        "1.3": "Gamma one. Gamma two. Tail out.",
    })


def test_trim_cuts_start_end_and_middle_with_an_ellipsis_at_each_cut(tmp_path):
    _three_sections(tmp_path)
    span = _run_one(tmp_path, _dl_span("1.1-3", trim={
        "start": "Alpha one.",
        "end": "Gamma two.",
        "omit": [["Alpha two.", "Beta one."]],
    }))
    assert span["text"] == "…Alpha one.\n\n…Beta two.\n\nGamma one. Gamma two.…"
    assert span["sectionLoci"] == ["1.1", "1.2", "1.3"]


def test_trim_omit_inside_one_paragraph_joins_with_one_ellipsis(tmp_path):
    _write_hicks(tmp_path, {"1.1": "Alpha one. Alpha two. Alpha three."})
    span = _run_one(tmp_path, _dl_span("1.1", trim={
        "omit": [["Alpha two.", "Alpha two."]],
    }))
    assert span["text"] == "Alpha one. …Alpha three."
    assert "sectionLoci" not in span


def test_trim_drops_an_emptied_paragraph_and_its_section_locus(tmp_path):
    _three_sections(tmp_path)
    span = _run_one(tmp_path, _dl_span("1.1-3", trim={
        "omit": [["Alpha two.", "Beta two."]],
    }))
    assert span["text"] == "Lead in. Alpha one.\n\n…Gamma one. Gamma two. Tail out."
    assert span["sectionLoci"] == ["1.1", "1.3"]


def test_trim_to_one_paragraph_emits_no_section_loci(tmp_path):
    _three_sections(tmp_path)
    span = _run_one(tmp_path, _dl_span("1.1-3", trim={
        "start": "Beta one.", "end": "Beta two.",
    }))
    assert span["text"] == "…Beta one. Beta two.…"
    assert "sectionLoci" not in span


def test_span_without_trim_is_unchanged(tmp_path):
    _three_sections(tmp_path)
    span = _run_one(tmp_path, _dl_span("1.1-3"))
    assert span["text"] == (
        "Lead in. Alpha one. Alpha two.\n\nBeta one. Beta two.\n\n"
        "Gamma one. Gamma two. Tail out."
    )
    assert "…" not in span["text"]


@pytest.mark.parametrize("trim, message", [
    ({"start": "Absent words."}, "trim start 'Absent words.' does not occur"),
    ({"end": "Absent words."}, "trim end 'Absent words.' does not occur"),
    ({"omit": [["Absent", "Beta two."]]}, "trim omit from 'Absent' does not occur"),
    ({"omit": [["Alpha two.", "Absent"]]}, "trim omit to 'Absent' does not occur"),
    ({"start": "one."}, "occurs 3 times"),
    ({"start": "Gamma one.", "end": "Alpha one."}, "end comes before trim start"),
    ({"omit": [["Beta one.", "Alpha two."]]}, "'to' comes before 'from'"),
    ({"omit": [["Lead in.", "Alpha one."]]}, "kept text on both sides"),
    ({"omit": [["Alpha two.", "Beta two."], ["Beta one.", "Gamma one."]]}, "overlap"),
    ({"stop": "Beta two."}, "unknown key"),
    ({}, "non-empty object"),
    ({"start": "Alpha one.\n\nBeta"}, "blank line"),
])
def test_bad_or_missing_trim_anchor_is_fatal(tmp_path, trim, message):
    _three_sections(tmp_path)
    with pytest.raises(ValueError, match=re.escape(message)):
        _run_one(tmp_path, _dl_span("1.1-3", trim=trim))


def test_trim_on_desert_span_is_fatal(tmp_path):
    span = {
        "source_author": "Diogenes Laertius",
        "source_work": "Lives of Eminent Philosophers",
        "locus": "1.1", "status": "desert", "trim": {"start": "Alpha"},
    }
    with pytest.raises(ValueError, match="desert.*trim"):
        _run_one(tmp_path, span)


def test_trim_that_cuts_an_emphasis_run_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.1": "Alpha one. Alpha two. Alpha three."})
    with pytest.raises(ValueError, match="does not occur"):
        _run_one(tmp_path, _dl_span(
            "1.1", emphasis=["Alpha two."], trim={"start": "Alpha three."}
        ))


def test_trim_applies_on_top_of_the_aristotle_sentence_keep(tmp_path):
    _write_aristotle(tmp_path, {
        "Meta:1:10a": _col([1], "Alpha one. Beta two. Gamma three. Delta four. Omega."),
    })
    declared = _aristotle_declaration("10a1", ["Beta two", "Delta four"])
    declared["1:A1"]["context_spans"][0]["trim"] = {
        "omit": [["Gamma three.", "Gamma three."]],
    }
    _write_declaration(tmp_path, "thales-testimonia", declared)
    out_path = sce.run(_manifest(), _spine(["A1"]))
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A1"][0]
    # One "…" per cut: the sentence-keep's at each edge, the trim's in the middle.
    assert span["text"] == "…Beta two. …Delta four.…"
    assert span["emphasis"] == ["Beta two", "Delta four"]


def _write_jowett(tmp_path, entries: dict) -> None:
    p = tmp_path / "jowett-plato" / "jowett-stephanus.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries), encoding="utf-8")


def _plato_trimmed_span(**extra) -> dict:
    span = {
        "source_author": "Plato", "source_work": "Cratylus",
        "locus": "402a-402b", "status": "translated",
        "translation_credit": "Fowler, 1926",
        "trim": {"start": "Fowler two.", "end": "Fowler three."},
    }
    span.update(extra)
    return span


def _cratylus_stores(tmp_path) -> None:
    _write_plato(tmp_path, {
        "cratylus:402a": "Fowler one. Fowler two.",
        "cratylus:402b": "Fowler three. Fowler four.",
    })
    _write_jowett(tmp_path, {
        "cratylus:402a": "Jowett one. Jowett two.",
        "cratylus:402b": "Jowett three. Jowett four.",
    })


def test_alternate_translation_is_trimmed_too(tmp_path):
    _cratylus_stores(tmp_path)
    span = _run_one(tmp_path, _plato_trimmed_span(alt_trims={"jowett": {
        "start": "Jowett two.", "end": "Jowett four.",
        "omit": [["Jowett three.", "Jowett three."]],
    }}), work_id="heraclitus-testimonia")
    assert span["text"] == "…Fowler two. Fowler three.…"
    assert "sectionLoci" not in span
    assert span["alts"][0]["sections"] == [
        {"locus": "402a-402b", "text": "…Jowett two. …Jowett four."},
    ]


def test_trimmed_span_must_say_how_to_trim_its_alternate(tmp_path):
    _cratylus_stores(tmp_path)
    with pytest.raises(ValueError, match="no alt_trims"):
        _run_one(tmp_path, _plato_trimmed_span(), work_id="heraclitus-testimonia")


def test_alternate_can_be_kept_or_dropped(tmp_path):
    _cratylus_stores(tmp_path)
    kept = _run_one(tmp_path, _plato_trimmed_span(alt_trims={"jowett": "keep"}),
                    work_id="heraclitus-testimonia")
    assert kept["alts"][0]["sections"][0]["text"] == (
        "Jowett one. Jowett two. Jowett three. Jowett four."
    )
    dropped = _run_one(tmp_path, _plato_trimmed_span(alt_trims={"jowett": "drop"}),
                       work_id="heraclitus-testimonia")
    assert "alts" not in dropped


def test_alt_trims_for_an_alternate_not_offered_is_fatal(tmp_path):
    _write_plato(tmp_path, {"cratylus:402a": "Fowler one. Fowler two."})
    span = _plato_trimmed_span(locus="402a", trim={"start": "Fowler two."},
                               alt_trims={"jowett": "keep"})
    with pytest.raises(ValueError, match="does not offer"):
        _run_one(tmp_path, span, work_id="heraclitus-testimonia")


def test_missing_alternate_anchor_is_fatal(tmp_path):
    _cratylus_stores(tmp_path)
    span = _plato_trimmed_span(alt_trims={"jowett": {"start": "Absent."}})
    with pytest.raises(ValueError, match=r"alt_trims\['jowett'\].*does not occur"):
        _run_one(tmp_path, span, work_id="heraclitus-testimonia")


def test_real_heraclitus_A6_starts_at_heracleitus_says_in_both_translations(monkeypatch):
    # The owner's case (2026-09-27): DK quotes from "λέγει που Ἡράκλειτος" to
    # "οὐκ ἂν ἐμβαίης"; the English now starts and stops there too.
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    declared = json.loads(
        (REAL_SOURCES_DIR / "heraclitus-testimonia" / "context-english.json")
        .read_text(encoding="utf-8")
    )
    spine = _real_spine(declared)
    out_path = sce.run(_manifest("heraclitus-testimonia"), spine)
    span = json.loads(out_path.read_text(encoding="utf-8"))["1:A6"][0]
    assert span["text"].startswith("…Heracleitus says, you know,")
    assert span["text"].endswith("you cannot step twice into the same stream.…")
    assert "It sounds absurd" not in span["text"]
    (jowett,) = span["alts"]
    (section,) = jowett["sections"]
    assert section["locus"] == "402a"
    assert section["text"].startswith("…Heracleitus is supposed to say")
    assert section["text"].endswith("you cannot go into the same water twice.…")


# --- Jowett from a neighbouring key (owner ruling, 2026-09-27): `alt_loci` --
# Jowett's store is aligned by speaker turn, so his rendering of DK's words
# can sit under the Stephanus key before the span's own.


def _gorgias_turn_stores(tmp_path) -> None:
    _write_plato(tmp_path, {
        "gorgias:452e": "Lamb one. Lamb two.",
        "gorgias:453a": "Lamb three. Lamb four.",
    })
    _write_jowett(tmp_path, {
        "gorgias:452e": "Jowett one. Jowett two. Jowett three.",
        "gorgias:453a": "Jowett four.",
    })


def _gorgias_span(**extra) -> dict:
    span = {
        "source_author": "Plato", "source_work": "Gorgias", "locus": "453a",
        "status": "translated", "translation_credit": "Lamb, 1925",
        "trim": {"start": "Lamb four."},
    }
    span.update(extra)
    return span


def test_jowett_alternate_drawn_from_the_neighbouring_key(tmp_path):
    _gorgias_turn_stores(tmp_path)
    span = _run_one(tmp_path, _gorgias_span(
        alt_loci={"jowett": "452e"},
        alt_trims={"jowett": {"start": "Jowett two.", "end": "Jowett three."}},
    ), work_id="gorgias-testimonia")
    assert span["text"] == "…Lamb four."
    (alt,) = span["alts"]
    # The words come from 452e; the section keeps the span's own locus.
    assert alt["sections"] == [{"locus": "453a", "text": "…Jowett two. Jowett three."}]


def test_jowett_alt_locus_range_expands_by_store_order(tmp_path):
    _gorgias_turn_stores(tmp_path)
    span = _run_one(tmp_path, _gorgias_span(
        alt_loci={"jowett": "452e-453a"},
        alt_trims={"jowett": {"start": "Jowett three.", "end": "Jowett four."}},
    ), work_id="gorgias-testimonia")
    assert span["alts"][0]["sections"][0]["text"] == "…Jowett three. Jowett four."


def test_without_alt_loci_the_span_locus_still_picks_jowett(tmp_path):
    _gorgias_turn_stores(tmp_path)
    span = _run_one(tmp_path, _gorgias_span(alt_trims={"jowett": "keep"}),
                    work_id="gorgias-testimonia")
    assert span["alts"][0]["sections"][0]["text"] == "Jowett four."


@pytest.mark.parametrize("jowett, alt_locus, message", [
    ({"gorgias:453a": "Jowett four."}, "452e", "no Jowett text for gorgias:452e"),
    ({"gorgias:452e": "  ", "gorgias:453a": "Jowett four."}, "452e",
     "no Jowett text for gorgias:452e"),
    ({"gorgias:452e": "Jowett one."}, "452e-453a", "no Jowett text for gorgias:453a"),
    ({"gorgias:452e": "Jowett one."}, "452d", "not a key"),
    ({"gorgias:452e": "Jowett one."}, "452e ff.", "not valid"),
])
def test_bad_alt_locus_is_fatal(tmp_path, jowett, alt_locus, message):
    _write_plato(tmp_path, {"gorgias:452e": "Lamb one.", "gorgias:453a": "Lamb three. Lamb four."})
    _write_jowett(tmp_path, jowett)
    with pytest.raises(ValueError, match=re.escape(message)):
        _run_one(tmp_path, _gorgias_span(alt_loci={"jowett": alt_locus},
                                         alt_trims={"jowett": "keep"}),
                 work_id="gorgias-testimonia")


def test_alt_locus_without_a_jowett_store_is_fatal(tmp_path):
    _write_plato(tmp_path, {"gorgias:452e": "Lamb one.", "gorgias:453a": "Lamb three. Lamb four."})
    with pytest.raises(ValueError, match="jowett-stephanus.clean.json is missing"):
        _run_one(tmp_path, _gorgias_span(alt_loci={"jowett": "452e"}),
                 work_id="gorgias-testimonia")


@pytest.mark.parametrize("alt_loci", [{"bury": "452e"}, {}, "452e", {"jowett": "452e", "x": "1a"}])
def test_malformed_alt_loci_is_fatal(tmp_path, alt_loci):
    _gorgias_turn_stores(tmp_path)
    with pytest.raises(ValueError, match="alt_loci must be"):
        _run_one(tmp_path, _gorgias_span(alt_loci=alt_loci), work_id="gorgias-testimonia")


def test_alt_loci_on_a_non_plato_span_is_fatal(tmp_path):
    _write_hicks(tmp_path, {"1.1": "Alpha one."})
    with pytest.raises(ValueError, match="only allowed on Plato spans"):
        _run_one(tmp_path, _dl_span("1.1", alt_loci={"jowett": "452e"}))


def test_alt_loci_on_a_desert_span_is_fatal(tmp_path):
    span = {
        "source_author": "Plato", "source_work": "Gorgias", "locus": "453a",
        "status": "desert", "alt_loci": {"jowett": "452e"},
    }
    with pytest.raises(ValueError, match="desert.*alt_loci"):
        _run_one(tmp_path, span, work_id="gorgias-testimonia")


def _run_real(monkeypatch, work_id: str) -> dict:
    monkeypatch.setattr(sce, "SOURCES_DIR", REAL_SOURCES_DIR)
    monkeypatch.setattr(sce, "BUILD_DIR", REAL_SOURCES_DIR.parent / "pipeline" / "build" / "_test_tmp")
    declared = json.loads(
        (REAL_SOURCES_DIR / work_id / "context-english.json").read_text(encoding="utf-8")
    )
    out_path = sce.run(_manifest(work_id), _real_spine(declared))
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_real_gorgias_A28_takes_jowett_from_452e(monkeypatch):
    # The owner's case: Jowett was dropped at 453a because his rendering of
    # DK's clause sits under 452e in his turn-aligned store.
    (span, _) = _run_real(monkeypatch, "gorgias-testimonia")["1:A28"]
    assert span["locus"] == "453a"
    (jowett,) = span["alts"]
    assert jowett["sections"] == [{"locus": "453a", "text": (
        "…and you mean to say, if I am not mistaken, that rhetoric is the "
        "artificer of persuasion, having this and no other business, and that "
        "this is her crown and end.…"
    )}]


# --- Galen, Brock's Loeb (1916): sources/brock-galen/ ----------------------


def _write_galen(tmp_path, chapters: dict) -> None:
    p = tmp_path / "brock-galen" / "brock-natural-faculties.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(chapters), encoding="utf-8")


def _galen_span(locus: str, **extra) -> dict:
    span = {
        "source_author": "Galen", "source_work": "On the Natural Faculties",
        "locus": locus, "status": "translated", "translation_credit": "Brock, 1916",
    }
    span.update(extra)
    return span


def test_galen_chapter_is_trimmed_within_one_paragraph(tmp_path):
    _write_galen(tmp_path, {"2.8": "Para one.\n\nAlpha. Beta. Gamma.\n\nPara three."})
    span = _run_one(tmp_path, _galen_span("2.8", trim={"start": "Beta.", "end": "Beta."}))
    assert span["text"] == "…Beta.…"
    assert "sectionLoci" not in span


@pytest.mark.parametrize("locus, message", [
    ("2.10", "not a key"), ("II 8", "not valid"), ("2.8-9", "not valid"),
])
def test_bad_galen_locus_is_fatal(tmp_path, locus, message):
    _write_galen(tmp_path, {"2.8": "Alpha."})
    with pytest.raises(ValueError, match=message):
        _run_one(tmp_path, _galen_span(locus))


def test_real_galen_resolves_anaxagoras_A104_and_prodicus_B4(monkeypatch):
    (a104,) = _run_real(monkeypatch, "anaxagoras-testimonia")["1:A104"]
    assert (a104["sourceAuthor"], a104["sourceWork"], a104["locus"]) == (
        "Galen", "On the Natural Faculties", "2.8")
    assert a104["translationCredit"] == "Brock, 1916"
    assert a104["text"] == (
        "…For, if it was right to raise this problem, why should we not make "
        "investigations concerning the blood as well—whether it takes its "
        "origin in the body, or is distributed through the food as is "
        "maintained by those who postulate homœmeries?…"
    )
    (b4,) = _run_real(monkeypatch, "prodicus-fragments")["1:B4"]
    assert b4["locus"] == "2.9"
    assert b4["text"].startswith("…Prodicus also, when in his book “On the Nature of Man”")
    assert b4["text"].endswith("anything else than cold and moist.…")
    assert "\n\n" not in b4["text"]


def test_committed_galen_store_matches_its_checksum():
    folder = REAL_SOURCES_DIR / "brock-galen"
    digest, name = (folder / "SHA256SUMS").read_text(encoding="utf-8").split()
    assert name == "brock-natural-faculties.clean.json"
    assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    store = json.loads((folder / name).read_text(encoding="utf-8"))
    assert sorted(store) == ["2.8", "2.9"]


# --- Aëtius, Goodwin's Placita (1874): sources/goodwin-placita/ -------------


def _write_goodwin(tmp_path, chapters: dict) -> None:
    p = tmp_path / "goodwin-placita" / "goodwin-placita.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(chapters), encoding="utf-8")


def _aetius_span(locus: str, **extra) -> dict:
    span = {
        "source_author": "Aëtius", "source_work": "Placita",
        "locus": locus, "status": "translated", "translation_credit": "Goodwin, 1874",
    }
    span.update(extra)
    return span


def test_aetius_locus_is_diels_numbering_with_book_v_23_and_24_swapped(tmp_path):
    # Store keys are Goodwin's chapters; loci are Diels's.
    _write_goodwin(tmp_path, {
        "2.21": "Sun size.", "5.23": "Goodwin V 23.", "5.24": "Goodwin V 24.",
    })
    assert _run_one(tmp_path, _aetius_span("2.21"))["text"] == "Sun size."
    assert _run_one(tmp_path, _aetius_span("5.23"))["text"] == "Goodwin V 24."
    assert _run_one(tmp_path, _aetius_span("5.24"))["text"] == "Goodwin V 23."


@pytest.mark.parametrize("locus, message", [
    ("2.9", "not a key"), ("II 21", "not valid"), ("2.21-22", "not valid"),
    ("2.21, 4", "not valid"),
])
def test_bad_aetius_locus_is_fatal(tmp_path, locus, message):
    _write_goodwin(tmp_path, {"2.21": "Alpha."})
    with pytest.raises(ValueError, match=message):
        _run_one(tmp_path, _aetius_span(locus))


def test_aetius_trim_anchor_missing_from_the_chapter_is_fatal(tmp_path):
    _write_goodwin(tmp_path, {"2.21": "Alpha. Beta. Gamma."})
    with pytest.raises(ValueError, match="does not occur"):
        _run_one(tmp_path, _aetius_span("2.21", trim={"start": "Delta.", "end": "Gamma."}))


def test_real_aetius_heraclitus_B3_and_the_book_v_swap(monkeypatch):
    (b3,) = _run_real(monkeypatch, "heraclitus-fragments")["1:B3"]
    assert (b3["sourceAuthor"], b3["sourceWork"], b3["locus"]) == (
        "Aëtius", "Placita", "2.21")
    assert b3["translationCredit"] == "Goodwin, 1874"
    assert b3["text"] == "…Heraclitus, that it is no broader than a man’s foot.…"
    assert b3["emphasis"] == ["no broader than a man’s foot"]
    # DK's V 24, 2 (sleep and death) is Goodwin's chapter XXIII ...
    (a85,) = _run_real(monkeypatch, "empedocles-testimonia")["1:A85"]
    assert a85["locus"] == "5.24"
    assert a85["text"] == (
        "…Empedocles, that a moderate cooling of the blood causeth sleep, but "
        "a total remotion of heat from blood causeth death.…"
    )
    # ... and DK's V 23 (maturity) is Goodwin's chapter XXIV.
    (a18,) = _run_real(monkeypatch, "heraclitus-testimonia")["1:A18"]
    assert a18["locus"] == "5.23"
    assert a18["text"].startswith("Heraclitus and the Stoics say, that men begin")
    assert a18["text"].endswith("the seminal serum is emitted.…")


def test_committed_goodwin_store_matches_its_checksum():
    folder = REAL_SOURCES_DIR / "goodwin-placita"
    digest, name = (folder / "SHA256SUMS").read_text(encoding="utf-8").split()
    assert name == "goodwin-placita.clean.json"
    assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    store = json.loads((folder / name).read_text(encoding="utf-8"))
    assert len(store) == 77
    assert store["5.23"].startswith("Alcmaeon says, that sleep is caused")
    assert store["5.24"].startswith("Heraclitus and the Stoics say")


# --- Plutarch: the Moralia (Goodwin 1874, Loeb 1927-1959), Perrin's Lives ----


def _write_morals(tmp_path, essays: dict, store="goodwin-morals") -> None:
    p = tmp_path / store / f"{store}.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(essays), encoding="utf-8")


def _write_lives(tmp_path, lives: dict) -> None:
    p = tmp_path / "perrin-lives" / "perrin-lives.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(lives), encoding="utf-8")


def _plutarch_span(work: str, locus: str, credit="Goodwin, 1874",
                   author="Plutarch", **extra) -> dict:
    span = {
        "source_author": author, "source_work": work, "locus": locus,
        "status": "translated", "translation_credit": credit,
    }
    span.update(extra)
    return span


# Synthetic chapters (the Stephanus ranges are made up) of an essay Goodwin
# still serves, and of one the Loeb serves.
_ESSAY = {"Quaestiones Naturales": {
    "2": {"steph": "97e-98b", "text": "Two."},
    "3": {"steph": "98b-98f", "text": "Three a.\n\nThree b."},
    "4": {"steph": "98f-99b", "text": "Four."},
}}
_LOEB_ESSAY = {"De Fortuna": _ESSAY["Quaestiones Naturales"]}


@pytest.mark.parametrize("locus, text", [
    ("98c", "Three a.\n\nThree b."),                    # inside one chapter
    ("98b", "Two.\n\nThree a.\n\nThree b."),            # a letter two chapters share
    ("98e-99a", "Three a.\n\nThree b.\n\nFour."),      # a range across chapters
])
def test_moralia_resolves_every_chapter_the_stephanus_locus_meets(tmp_path, locus, text):
    _write_morals(tmp_path, _ESSAY)
    _write_morals(tmp_path, _LOEB_ESSAY, store="loeb-moralia")
    assert _run_one(tmp_path, _plutarch_span("Quaestiones Naturales", locus))["text"] == text
    span = _run_one(tmp_path, _plutarch_span("De Fortuna", locus, credit="Babbitt, 1928"))
    assert span["text"] == text


@pytest.mark.parametrize("locus, message", [
    ("98", "not valid"), ("98g", "not valid"), ("3", "not valid"),
    ("98c-98", "not valid"), ("98f-98c", "runs backwards"),
    ("100a", "meets no chapter"),
])
def test_bad_moralia_locus_is_fatal(tmp_path, locus, message):
    _write_morals(tmp_path, _ESSAY)
    with pytest.raises(ValueError, match=message):
        _run_one(tmp_path, _plutarch_span("Quaestiones Naturales", locus))


def test_moralia_essay_missing_from_its_store_is_fatal(tmp_path):
    _write_morals(tmp_path, _ESSAY)
    with pytest.raises(ValueError, match=r"'Amatorius' is not in sources/goodwin-morals/"):
        _run_one(tmp_path, _plutarch_span("Amatorius", "756e"))
    # A Loeb essay reads only the Loeb store, even where Goodwin's has it.
    _write_morals(tmp_path, {**_ESSAY, **_LOEB_ESSAY})
    _write_morals(tmp_path, {}, store="loeb-moralia")
    with pytest.raises(ValueError, match=r"'De Fortuna' is not in sources/loeb-moralia/"):
        _run_one(tmp_path, _plutarch_span("De Fortuna", "98c", credit="Babbitt, 1928"))


def test_moralia_trim_anchor_missing_from_the_chapters_is_fatal(tmp_path):
    _write_morals(tmp_path, _ESSAY)
    with pytest.raises(ValueError, match="does not occur"):
        _run_one(tmp_path, _plutarch_span("Quaestiones Naturales", "98c", trim={"start": "Five."}))


def test_perrin_life_resolves_a_chapter_or_a_range(tmp_path):
    _write_lives(tmp_path, {"Pericles": {"26": "Twenty-six.", "27": "Twenty-seven.", "28": "Twenty-eight."}})
    span = _run_one(tmp_path, _plutarch_span("Pericles", "27", credit="Perrin, 1916"))
    assert span["text"] == "Twenty-seven."
    span = _run_one(tmp_path, _plutarch_span("Pericles", "26-28", credit="Perrin, 1916"))
    assert span["text"] == "Twenty-six.\n\nTwenty-seven.\n\nTwenty-eight."
    assert "sectionLoci" not in span


@pytest.mark.parametrize("locus, message", [
    ("16", "not in"), ("26-29", r"\['29'\] not in"), ("28-26", "runs backwards"),
    ("26.2", "not valid"), ("xxvi", "not valid"),
])
def test_bad_perrin_life_locus_is_fatal(tmp_path, locus, message):
    _write_lives(tmp_path, {"Pericles": {"26": "A.", "27": "B.", "28": "C."}})
    with pytest.raises(ValueError, match=message):
        _run_one(tmp_path, _plutarch_span("Pericles", locus, credit="Perrin, 1916"))


def test_perrin_trim_anchor_missing_from_the_chapter_is_fatal(tmp_path):
    _write_lives(tmp_path, {"Solon": {"2": "Thales traded."}})
    with pytest.raises(ValueError, match="does not occur"):
        _run_one(tmp_path, _plutarch_span("Solon", "2", credit="Perrin, 1914",
                                          trim={"end": "sold oil."}))


def test_plutarch_pairs_are_registered_by_dk_author_and_title():
    # The head expansion's author decides the pair: the Lives of the Ten
    # Orators is "[PLUT.]", so only pseudo-Plutarch resolves it.
    assert ("pseudo-Plutarch", "Vitae Decem Oratorum") in sce._RESOLVERS
    assert ("Plutarch", "Vitae Decem Oratorum") not in sce._RESOLVERS
    assert ("Plutarch", "Quaestiones Convivales") in sce._RESOLVERS
    assert ("Plutarch", "Pericles") in sce._RESOLVERS
    assert ("Plutarch", "Stromateis") not in sce._RESOLVERS
    assert ("pseudo-Plutarch", "Stromateis") not in sce._RESOLVERS


def test_every_loeb_essay_is_registered_and_goodwin_keeps_the_rest():
    # A Loeb title missing from Goodwin's list would silently not register.
    assert set(sce._LOEB_MORALIA) <= set(sce._GOODWIN_MORALIA)
    assert set(sce._LOEB_PSEUDO_MORALIA) <= set(sce._GOODWIN_PSEUDO_MORALIA)
    goodwin_only = set(sce._GOODWIN_MORALIA) - set(sce._LOEB_MORALIA)
    assert goodwin_only == {
        "Adversus Colotem", "Amatorius", "De Animae Procreatione in Timaeo",
        "De Communibus Notitiis adversus Stoicos", "Quaestiones Convivales",
        "Quaestiones Naturales", "Quaestiones Platonicae",
    }


def test_real_plutarch_moralia_heraclitus_B93_de_pythiae_oraculis_404d(monkeypatch):
    spans = _run_real(monkeypatch, "heraclitus-fragments")["1:B93"]
    (span,) = [s for s in spans if s["sourceAuthor"] == "Plutarch"]
    assert (span["sourceWork"], span["locus"], span["translationCredit"]) == (
        "De Pythiae Oraculis", "404d", "Babbitt, 1936")
    assert span["text"] == (
        "…the Lord whose prophetic shrine is at Delphi neither tells nor "
        "conceals, but indicates.…"
    )
    assert span["emphasis"] == [
        "the Lord whose prophetic shrine is at Delphi neither tells nor conceals, but indicates"
    ]


def test_real_plutarch_moralia_goodwin_still_serves_the_essays_no_usable_loeb_covers(monkeypatch):
    (span,) = [s for s in _run_real(monkeypatch, "heraclitus-fragments")["1:B101"]
               if s["sourceAuthor"] == "Plutarch"]
    assert (span["sourceWork"], span["translationCredit"]) == ("Adversus Colotem", "Goodwin, 1874")


@pytest.mark.parametrize("work, seg, essay, credit, start, end", [
    # Vols. I-II (public domain by date)
    ("democritus-fragments", "1:B145", "De Liberis Educandis", "Babbitt, 1927",
     "…for, according to Democritus, “A word is a deed’s shadow.”", "shadow.”…"),
    ("gorgias-fragments", "1:B8a", "Coniugalia Praecepta", "Babbitt, 1928",
     "When the orator Gorgias read to the Greeks at Olympia", "on the wife’s part towards the girl.…"),
    # Vols. III-VII, X, XII (no renewal found)
    ("xenophanes-testimonia", "1:A11", "Regum et Imperatorum Apophthegmata", "Babbitt, 1931",
     "…In answer to Xenophanes of Colophon", "although he is dead.”…"),
    ("gorgias-fragments", "1:B23", "De Gloria Atheniensium", "Babbitt, 1936",
     "…But tragedy blossomed forth", "the delights of language.…"),
    ("democritus-fragments", "1:B149", "Animine an Corporis Affectiones Sint Peiores",
     "Helmbold, 1939", "…Shall we, then, say in our own case", "causes to gush forth”?…"),
    ("heraclitus-fragments", "1:B94", "De Exilio", "De Lacy and Einarson, 1959",
     "…for “the Sun will not transgress his bounds,” says Heracleitus;",
     "ministers of Justice, will find him out.”"),
    ("philolaus-testimonia", "1:A4a", "De Genio Socratis", "De Lacy and Einarson, 1959",
     "…After the Pythagorean societies throughout the different cities",
     "prevail over Cylon’s party,…"),
    ("antiphon-sophist-testimonia", "1:A6", "Vitae Decem Oratorum", "Fowler, 1936",
     "…And he is said to have written tragedies", "the book On Poets by Glaucus of Rhegium.…"),
    ("anaximenes-fragments", "1:B1", "De Primo Frigido", "Helmbold, 1957",
     "…Or are we, as old Anaximenes maintained", "that is propelled forward and makes contact."),
    ("heraclitus-fragments", "1:B98", "De Facie in Orbe Lunae", "Cherniss, 1957",
     "…“Souls employ the sense of smell in Hades.”", "in Hades.”"),
])
def test_real_plutarch_moralia_loeb_placements(monkeypatch, work, seg, essay, credit, start, end):
    """The Loeb English replaces Goodwin's wherever a usable Loeb volume
    covers the essay (owner ruling 2026-09-29, review item 118), credited to
    the volume's translator and year."""
    (span,) = [s for s in _run_real(monkeypatch, work)[seg]
               if s["sourceWork"] == essay]
    assert span["translationCredit"] == credit
    assert span["text"].startswith(start)
    assert span["text"].endswith(end)


def test_real_plutarch_moralia_loeb_cuts_and_corrections(monkeypatch):
    """DK's gaps are cut from the Loeb English, and the Perseus slips are
    corrected to the printed page (sources/loeb-moralia/README.md)."""
    def only(work, seg, essay):
        (span,) = [s for s in _run_real(monkeypatch, work)[seg] if s["sourceWork"] == essay]
        return span

    b42 = only("empedocles-fragments", "1:B42", "De Facie in Orbe Lunae")
    assert "not upon ⟨an⟩other star. …There remains then the theory of Empedocles" in b42["text"]
    assert "Posidonius" not in b42["text"] and "missiles" not in b42["text"]
    assert b42["emphasis"] == [
        "His beams she put to flight",
        "From heaven above as far as to the earth, Whereof such breadth as had the "
        "bright-eyed moon She cast in shade",
    ]
    b147 = only("democritus-fragments", "1:B147", "De Tuenda Sanitate Praecepta")
    assert "“swine in their wild excitement over bedding,” as Democritus put it" in b147["text"]
    assert "Zeuxippus" not in b147["text"]
    b92 = only("heraclitus-fragments", "1:B92", "De Pythiae Oraculis")
    assert b92["text"].startswith("…Do you not see, …what grace the songs of Sappho have")
    assert "unembellished" in b92["text"]
    b18 = only("anaxagoras-fragments", "1:B18", "De Facie in Orbe Lunae")
    assert "this very proposition of Anaxagoras’s that ‘the sun imparts" in b18["text"]
    b122 = only("empedocles-fragments", "1:B122", "De Tranquillitate Animi")
    assert "far-seeing Heliopê" in b122["text"] and "Thoösa" in b122["text"]


def test_real_plutarch_english_covers_only_what_dk_quotes(monkeypatch):
    """Lead-ins and tails Plutarch adds around DK's words stay out of the
    shown English (owner rulings, 2026-09-29); Perrin's printer's errors are
    corrected; Natural Questions 39 opens with Goodwin's question title.
    Empedocles B144 is in the Loeb (Helmbold, 1939) since the same day."""
    def only(work, seg):
        (span,) = [s for s in _run_real(monkeypatch, work)[seg] if s["sourceAuthor"] == "Plutarch"]
        return span["text"]

    assert only("heraclitus-fragments", "1:B85").startswith("…\u201cWith anger it is hard")
    assert only("heraclitus-fragments", "1:B86").startswith("…But most of the Deity")
    assert only("gorgias-fragments", "1:B20").startswith("…Gorgias the Leontine says")
    assert only("empedocles-fragments", "1:B144").startswith(
        "…I have been wont to regard as great and divine that saying of Empedocles")
    assert only("heraclitus-fragments", "1:B101") == "…I have been seeking myself.…"
    assert only("empedocles-fragments", "1:B76").endswith("above their bodies bear;…")
    assert only("empedocles-fragments", "1:B80").startswith("This discourse we liked")
    assert only("empedocles-fragments", "1:B94").startswith(
        "How cometh it that water, seeming white aloft, showeth to be black in the bottom?"
        "\n\nIs it because")


def test_real_plutarch_life_melissus_A3_pericles_26_to_28(monkeypatch):
    (span,) = _run_real(monkeypatch, "melissus-testimonia")["1:A3"]
    assert (span["sourceWork"], span["locus"], span["translationCredit"]) == (
        "Pericles", "26-28", "Perrin, 1916")
    text = span["text"]
    assert text.startswith("…For no sooner had he sailed off than Melissus, the son of Ithagenes,")
    assert "…To these brand-marks, they say, the verse of Aristophanes" in text
    assert "“For oh! how lettered is the folk of the Samians!”" in text
    assert "samaena is a ship of war" not in text      # omitted, as DK omits it
    assert "Periphoretus" not in text
    assert text.endswith("neither by Thucydides, nor Ephorus, nor Aristotle.…")
    assert "sectionLoci" not in span


def test_real_plutarch_spans_bind_to_their_named_heads(monkeypatch):
    # Thales A11 prints two Plutarch heads; each span names its own.
    spans = _run_real(monkeypatch, "thales-testimonia")["1:A11"]
    by_head = {s["headText"]: s for s in spans if s["sourceAuthor"] == "Plutarch"}
    assert by_head["PLUT. Sol. 2"]["locus"] == "2"
    assert by_head["PLUT. Sol. 2"]["translationCredit"] == "Perrin, 1914"
    assert by_head["de Is. et Osir. 34"]["locus"] == "364c-364d"
    assert by_head["de Is. et Osir. 34"]["translationCredit"] == "Babbitt, 1936"
    assert by_head["de Is. et Osir. 34"]["text"].startswith(
        "…They think also that Homer, like Thales, had gained his knowledge")


@pytest.mark.parametrize("folder, name", [
    ("goodwin-morals", "goodwin-morals.clean.json"),
    ("loeb-moralia", "loeb-moralia.clean.json"),
    ("perrin-lives", "perrin-lives.clean.json"),
])
def test_committed_plutarch_stores_match_their_checksums(folder, name):
    digest, listed = (REAL_SOURCES_DIR / folder / "SHA256SUMS").read_text(encoding="utf-8").split()
    assert listed == name
    assert hashlib.sha256((REAL_SOURCES_DIR / folder / name).read_bytes()).hexdigest() == digest


def test_committed_goodwin_morals_store_is_registered_and_well_formed():
    store = json.loads((REAL_SOURCES_DIR / "goodwin-morals" / "goodwin-morals.clean.json")
                       .read_text(encoding="utf-8"))
    assert set(store) == set(sce._GOODWIN_MORALIA) | set(sce._GOODWIN_PSEUDO_MORALIA)
    for essay, chapters in store.items():
        for chapter in chapters.values():
            first, last = chapter["steph"].split("-")
            assert sce._stephanus_key(first) <= sce._stephanus_key(last), (essay, chapter["steph"])
            assert chapter["text"].strip() and "  " not in chapter["text"]
    # Perseus's speaker labels are not in the 1874 print (it numbers the
    # paragraphs instead); they were removed.
    assert "ZEUXIPPUS" not in json.dumps(store) and "AUTOB." not in json.dumps(store)
    lives = json.loads((REAL_SOURCES_DIR / "perrin-lives" / "perrin-lives.clean.json")
                       .read_text(encoding="utf-8"))
    assert set(lives) == set(sce._PERRIN_LIVES)


def test_committed_loeb_moralia_store_is_registered_and_well_formed():
    store = json.loads((REAL_SOURCES_DIR / "loeb-moralia" / "loeb-moralia.clean.json")
                       .read_text(encoding="utf-8"))
    assert set(store) == set(sce._LOEB_MORALIA) | set(sce._LOEB_PSEUDO_MORALIA)
    goodwin = json.loads((REAL_SOURCES_DIR / "goodwin-morals" / "goodwin-morals.clean.json")
                         .read_text(encoding="utf-8"))
    for essay, chapters in store.items():
        for number, chapter in chapters.items():
            # Each Loeb chapter carries the range of Goodwin's same chapter.
            assert chapter["steph"] == goodwin[essay][number]["steph"], (essay, number)
            text = chapter["text"]
            assert text.strip() == text and "  " not in text, (essay, number)
    dump = json.dumps(store, ensure_ascii=False)
    # Perseus markup and slips the store corrects (README table).
    for slip in ("twTo", "Demolitus", "Anaxagorass", "unembellislied", "xv.2.p", "[", "]",
                 "swine m their", "Heraeleitus", "strugglingagainst"):
        assert slip not in dump, slip
    assert sum(len(chapters) for chapters in store.values()) == 57


# --- A new Plato span end to end (2026-09-27): Zeno A13, Phaedrus 261d ------


def test_real_zeno_A13_phaedrus_261d_in_both_translations(monkeypatch):
    (span,) = _run_real(monkeypatch, "zeno-testimonia")["1:A13"]
    assert (span["sourceWork"], span["locus"], span["translationCredit"]) == (
        "Phaedrus", "261d", "Fowler, 1914")
    assert span["text"] == (
        "…Do we not know that the Eleatic Palamedes (Zeno) has such an art of "
        "speaking that the same things appear to his hearers to be alike and "
        "unlike, one and many, stationary and in motion?…"
    )
    assert span["emphasis"] == [span["text"].strip("…")]
    (jowett,) = span["alts"]
    assert jowett["sections"] == [{"locus": "261d", "text": (
        "…Have we not heard of the Eleatic Palamedes (Zeno), who has an art of "
        "speaking by which he makes the same things appear to his hearers like "
        "and unlike, one and many, at rest and in motion?…"
    )}]


# --- Harpocration, Harpokration On Line (CC BY 4.0): sources/harpokration-online/


def _write_hol(tmp_path, entries: dict, dk_spellings: dict | None = None) -> None:
    p = tmp_path / "harpokration-online" / "harpokration-online.clean.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"entries": entries, "dk_spellings": dk_spellings or {}}),
                 encoding="utf-8")


def _harpocration_span(locus: str, **extra) -> dict:
    span = {
        "source_author": "Harpocration", "source_work": "Lexicon in Decem Oratores",
        "locus": locus, "status": "translated",
        "translation_credit": "Harpokration On Line (CC BY 4.0)",
    }
    span.update(extra)
    return span


def test_harpocration_resolves_by_headword_and_by_dk_spelling(tmp_path):
    _write_hol(tmp_path, {"ἄοπτα": "Aopta: unseen.", "σκιάποδες": "Skiapodes: shadow."},
               {"Σκιάποδες": "σκιάποδες"})
    assert _run_one(tmp_path, _harpocration_span("s.v. ἄοπτα"))["text"] == "Aopta: unseen."
    assert _run_one(tmp_path, _harpocration_span("s.v. Σκιάποδες"))["text"] == "Skiapodes: shadow."


@pytest.mark.parametrize("locus, message", [
    ("s.v. ἀπαθῆ", "not an entry"), ("ἄοπτα", "not valid"), ("s.v.  ἄοπτα", "not valid"),
    ("s.v. ", "not valid"),
])
def test_bad_or_missing_harpocration_entry_is_fatal(tmp_path, locus, message):
    _write_hol(tmp_path, {"ἄοπτα": "Aopta: unseen."})
    with pytest.raises(ValueError, match=message):
        _run_one(tmp_path, _harpocration_span(locus))


def test_real_harpocration_antiphon_B14_trimmed_to_dk_and_B15_elision(monkeypatch):
    spans = _run_real(monkeypatch, "antiphon-sophist-fragments")
    (b14,) = spans["1:B14"]
    assert (b14["sourceAuthor"], b14["sourceWork"], b14["locus"]) == (
        "Harpocration", "Lexicon in Decem Oratores", "s.v. διάθεσις")
    assert b14["translationCredit"] == "Harpokration On Line (CC BY 4.0)"
    assert b14["text"] == (
        "Diathesis (disposition): …For they say the word ‘to dispose’ for "
        "‘to arrange.’ Antiphon in On Truth 1 (says), “stripped of a starting "
        "point, it would have disposed even many good things badly.”…"
    )
    # DK elides τοῦ ξύλου inside the quotation; so does the English.
    (b15,) = spans["1:B15"]
    assert "“and the decay …should become alive,”" in b15["text"]
    # Critias B35: DK's Λυκιουργεῖς resolves through HOL's lower-case key.
    (b35,) = _run_real(monkeypatch, "critias-fragments")["1:B35"]
    assert b35["text"].startswith("Lykiourgeis: …But the grammatikos")


def test_committed_harpokration_store_matches_its_checksum():
    folder = REAL_SOURCES_DIR / "harpokration-online"
    digest, name = (folder / "SHA256SUMS").read_text(encoding="utf-8").split()
    assert name == "harpokration-online.clean.json"
    assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    store = json.loads((folder / name).read_text(encoding="utf-8"))
    assert len(store["entries"]) == 31
    assert all(v in store["entries"] for v in store["dk_spellings"].values())
