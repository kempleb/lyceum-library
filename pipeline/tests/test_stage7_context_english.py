"""stage7_emit's conditional spread for source-passage English (docs/
source-passage-english-scoping.md): a segment named in
build/stage1/context_english.json (stage1_context_english.run's resolved
output) emits it under `contextEnglish`; every other segment -- and every
work with no context_english at all -- emits no such key, byte-identical
to before this mechanism existed. Same conditional-spread posture as
test_section_paragraphs_emit.py's sections/title/paras coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline.stage7_emit import chapter_ranges, emit_books


def _spine():
    return {
        "work": "FIX",
        "segments": [
            {"id": "1:A1", "book": 1, "column": "A1",
             "lines": [{"n": 1, "text": "context text", "role": "context"}]},
            {"id": "1:A2", "book": 1, "column": "A2",
             "lines": [{"n": 1, "text": "other context text", "role": "context"}]},
        ],
    }


def _tokens_doc():
    return {
        "segments": [
            {"id": "1:A1", "lines": [{"n": 1, "tokens": []}]},
            {"id": "1:A2", "lines": [{"n": 1, "tokens": []}]},
        ],
    }


def test_context_english_key_present_only_on_the_segment_it_names(tmp_path):
    english = {"chunks": []}
    context_english = {
        "1:A1": [{
            "sourceAuthor": "Diogenes Laertius",
            "sourceWork": "Lives of Eminent Philosophers",
            "locus": "1.22-40", "status": "translated",
            "translationCredit": "Hicks, 1925", "text": "Resolved text.",
        }],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               out_dir, context_english=context_english)
    emitted = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["A1"]["contextEnglish"] == context_english["1:A1"]
    assert "contextEnglish" not in by_col["A2"]


def test_desert_span_carries_no_text_or_credit_key(tmp_path):
    english = {"chunks": []}
    context_english = {
        "1:A2": [{
            "sourceAuthor": "Sextus Empiricus", "sourceWork": "Adv. Math.",
            "locus": "VII 132", "status": "desert",
        }],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               out_dir, context_english=context_english)
    emitted = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    span = by_col["A2"]["contextEnglish"][0]
    assert "text" not in span
    assert "translationCredit" not in span


def test_alts_key_passes_through_unmodified(tmp_path):
    # Item 82: stage1_context_english.py may attach an `alts` array to a
    # span (Jowett per-passage translation picker). stage7_emit does not
    # know or care about this key -- it spreads the whole resolved span
    # dict verbatim, so `alts` must survive untouched, same posture as
    # every other key on the span.
    english = {"chunks": []}
    alts = [{
        "id": "jowett", "label": "Jowett",
        "translationCredit": (
            "Benjamin Jowett, The Dialogues of Plato, 3rd ed., Oxford, 1892"
        ),
        "sections": [{"locus": "447b", "text": "Jowett text."}],
    }]
    context_english = {
        "1:A1": [{
            "sourceAuthor": "Plato", "sourceWork": "Gorgias",
            "locus": "447b", "status": "translated",
            "translationCredit": "Lamb, 1925", "text": "Resolved text.",
            "alts": alts,
        }],
    }
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               out_dir, context_english=context_english)
    emitted = json.loads((out_dir / "book-01.json").read_text(encoding="utf-8"))
    by_col = {s["column"]: s for s in emitted["segments"]}
    assert by_col["A1"]["contextEnglish"][0]["alts"] == alts


def test_no_context_english_arg_emits_no_key_anywhere(tmp_path):
    english = {"chunks": []}
    out_dir = tmp_path / "dist"
    out_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), out_dir)
    raw = (out_dir / "book-01.json").read_text(encoding="utf-8")
    assert '"contextEnglish"' not in raw


def test_mechanism_absent_vs_present_but_undeclared_is_byte_identical(tmp_path):
    # Adversarial review, finding 4's byte-identity requirement: a work with
    # no context-english.json sidecar must emit output identical whether
    # stage7_emit's context_english mechanism is absent entirely (the
    # `context_english` kwarg omitted -- the pre-mechanism call shape every
    # other work still uses) or present but finds nothing to attach (an
    # explicit empty dict -- stage1_context_english.run() returning None
    # and stage7's own `context_english_path.exists()` check both collapse
    # to this same `{}` at call time; see stage7_emit.py's own comment at
    # the emit_books call site).
    english = {"chunks": []}

    absent_dir = tmp_path / "absent"
    absent_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []), absent_dir)

    present_dir = tmp_path / "present"
    present_dir.mkdir()
    emit_books(_spine(), _tokens_doc(), english, chapter_ranges(_spine(), []),
               present_dir, context_english={})

    absent_raw = (absent_dir / "book-01.json").read_text(encoding="utf-8")
    present_raw = (present_dir / "book-01.json").read_text(encoding="utf-8")
    assert absent_raw == present_raw
