"""Regression tests for tools/extract_gummere_wikisource.py -- the rendered-
HTML walker plus the post-adversarial-review hardening added after a
GPT-5.6-Sol review: cache envelope/completeness validation, the fail-loud
pass-through allowlist, the Letter-41 merge exact-once assertion, and the
declared per-letter/per-page integrity manifest. No network: these exercise
the module's functions directly on minimal synthetic HTML/report structures
replicating the exact shapes found in the pinned Wikisource responses (see
the module docstring).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import lxml.html
import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_gummere_wikisource", _TOOLS / "extract_gummere_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_gummere_wikisource"] = _mod
_spec.loader.exec_module(_mod)


# --- rendered-HTML envelope/completeness validation (BLOCKER) --------------

_GOOD_TAIL = '<!-- Saved in parser cache with key enwikisource:pcache and timestamp 20260701 -->\n'
_GOOD_HTML = (
    '<div class="mw-parser-output"><div class="prp-pages-output" lang="en">'
    '<p>Some prose.</p></div></div>\n' + _GOOD_TAIL
)


def test_validate_rendered_html_accepts_complete_response():
    _mod._validate_rendered_html(1, _GOOD_HTML, "cache")  # must not raise


def test_validate_rendered_html_rejects_empty():
    with pytest.raises(ValueError, match="empty HTML"):
        _mod._validate_rendered_html(1, "   ", "fetch")


def test_validate_rendered_html_rejects_missing_terminal_anchor():
    truncated = _GOOD_HTML.split(_GOOD_TAIL)[0][:40]  # cut mid-prose, no anchor
    with pytest.raises(ValueError, match="Saved in parser cache"):
        _mod._validate_rendered_html(2, truncated, "cache")


def test_validate_rendered_html_rejects_wrong_content_div_count():
    no_content_div = '<div class="mw-parser-output"><p>orphan prose</p></div>\n' + _GOOD_TAIL
    with pytest.raises(ValueError, match="prp-pages-output divs, expected exactly 1"):
        _mod._validate_rendered_html(3, no_content_div, "fetch")


def test_validate_rendered_html_rejects_unparseable_markup():
    # lxml.html.fromstring is lenient, but an empty document (no elements at
    # all) still has zero prp-pages-output divs -- covered by the count
    # check above. This test locks in that a non-HTML string is rejected via
    # the same "wrong div count" path rather than being silently accepted.
    bogus = "just plain text, no markup at all\n" + _GOOD_TAIL
    with pytest.raises(ValueError, match="prp-pages-output"):
        _mod._validate_rendered_html(4, bogus, "cache")


# --- atomic cache writes ----------------------------------------------------

def test_atomic_write_leaves_no_tmp_file_and_correct_content(tmp_path):
    target = tmp_path / "12345.html"
    _mod._atomic_write(target, "hello world")
    assert target.read_text(encoding="utf-8") == "hello world"
    leftovers = list(tmp_path.glob("*.tmp-*"))
    assert leftovers == []


def test_fetch_rejects_truncated_cache_without_hitting_network(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "CACHE_DIR", tmp_path)
    cache_path = tmp_path / "999.html"
    cache_path.write_text(_GOOD_HTML[:30], encoding="utf-8")  # truncated, no anchor
    with pytest.raises(ValueError, match="truncated or malformed"):
        _mod._fetch(1, 999)


# --- fail-loud pass-through allowlist (MAJOR 2) -----------------------------

def _ctx_open_section(n=1):
    ctx = _mod._Ctx()
    ctx.current = n
    ctx.sections[n] = []
    return ctx


def test_allowlisted_paragraph_passes_through():
    ctx = _ctx_open_section()
    el = lxml.html.fromstring('<p>Ordinary prose.</p>')
    _mod._walk(el, ctx, 1, {})
    assert _mod._clean(ctx.sections[1]) == "Ordinary prose."


def test_unknown_element_class_is_fatal():
    ctx = _ctx_open_section()
    el = lxml.html.fromstring(
        '<div class="wst-maintenance-banner">Please do not remove this notice.</div>'
    )
    with pytest.raises(ValueError, match="unrecognized element"):
        _mod._walk(el, ctx, 1, {})


def test_unknown_bare_div_is_fatal():
    """A bare, classless <div> (never seen in the real corpus, where every
    pass-through div carries one of the allowlisted class sets) must also
    be rejected -- the allowlist is keyed on the FULL class set, not just
    the tag name."""
    ctx = _ctx_open_section()
    el = lxml.html.fromstring('<div>surprise structural element</div>')
    with pytest.raises(ValueError, match="unrecognized element"):
        _mod._walk(el, ctx, 1, {})


# --- data-page-quality capture (MAJOR 2) ------------------------------------

def _pagenum_span(page_name, quality, marker_id="3"):
    return lxml.html.fromstring(
        f'<span class="pagenum ws-pagenum" id="{marker_id}" '
        f'data-page-name="{page_name}" data-page-quality="{quality}"></span>'
    )


def test_pagenum_span_records_quality_and_occurrence_count():
    report = {}
    ctx = _mod._Ctx()
    _mod._walk(_pagenum_span("Page:X/1", "3"), ctx, 1, report)
    _mod._walk(_pagenum_span("Page:X/1", "3"), ctx, 1, report)  # shared boundary page
    assert report["page_quality"] == {"Page:X/1": "3"}
    assert report["page_occurrences"] == {"Page:X/1": 2}


def test_pagenum_span_quality_mismatch_across_transclusions_is_fatal():
    report = {}
    ctx = _mod._Ctx()
    _mod._walk(_pagenum_span("Page:X/1", "3"), ctx, 1, report)
    with pytest.raises(ValueError, match="data-page-quality changed"):
        _mod._walk(_pagenum_span("Page:X/1", "2"), ctx, 2, report)


def test_pagenum_span_missing_attributes_is_fatal():
    el = lxml.html.fromstring('<span class="pagenum ws-pagenum" id="3"></span>')
    with pytest.raises(ValueError, match="missing data-page-name"):
        _mod._walk(el, _mod._Ctx(), 1, {})


# --- Letter 41 merge exact-once assertion (MAJOR 1) -------------------------

def _report_with_merges(merges, marker_seq_41):
    return {"merges": merges, "marker_sequence": {41: marker_seq_41}}


def test_merge_invariant_passes_for_the_real_declared_shape():
    report = _report_with_merges([(41, 9, 8)], list(range(1, 10)))
    _mod._assert_merge_invariant(report)  # must not raise


def test_merge_invariant_fatal_when_marker_removed_entirely():
    report = _report_with_merges([], list(range(1, 9)))  # marker 9 never seen
    with pytest.raises(ValueError, match=r"observed 0 time\(s\)"):
        _mod._assert_merge_invariant(report)


def test_merge_invariant_fatal_when_marker_duplicated():
    report = _report_with_merges([(41, 9, 8), (41, 9, 8)], list(range(1, 9)) + [9, 9])
    with pytest.raises(ValueError, match=r"observed 2 time\(s\)"):
        _mod._assert_merge_invariant(report)


def test_merge_invariant_fatal_when_folded_into_wrong_section():
    report = _report_with_merges([(41, 9, 7)], list(range(1, 8)) + [9])
    with pytest.raises(ValueError, match="expected section 8"):
        _mod._assert_merge_invariant(report)


def test_merge_invariant_fatal_when_marker_not_final_or_not_adjacent():
    # Sequence ends with an extra marker after 9 -- 9 is not the FINAL marker.
    report = _report_with_merges([(41, 9, 8)], list(range(1, 10)) + [10])
    with pytest.raises(ValueError, match="must be the FINAL raw marker"):
        _mod._assert_merge_invariant(report)


def test_merge_invariant_fatal_on_undeclared_merge():
    report = _report_with_merges([(41, 9, 8), (7, 3, 2)], list(range(1, 10)))
    with pytest.raises(ValueError, match="no matching _MERGE_TAIL declaration"):
        _mod._assert_merge_invariant(report)


# --- salutation corpus-wide invariant (MINOR 1) + post-patch ordering (MINOR 2) --
#
# BLOCKER fix (Sol re-verification, 2026-07-21): these fixtures used to
# import the real `_SALUTATION` module constant and quote its verbatim
# Gummere opening-phrase text directly -- real English prose from the
# corpus, contradicting this file's own "no network / synthetic fixtures"
# framing (see module docstring). `_SALUTATION` is monkeypatched to an
# INVENTED sentence for every test below, and every fixture record is
# invented prose sharing no wording with the real corpus (verified: no
# 4-word run shared with sources/gummere-epistulae/gummere.clean.json).

_FAKE_SALUTATION = "Salve, this invented greeting exists only for this test."


def _records(overrides=None):
    recs = [
        {"book": 1, "section": 1, "text": _FAKE_SALUTATION + " An invented continuation follows here."},
        {"book": 1, "section": 2, "text": "Invented placeholder prose for the first letter's second part."},
        {"book": 2, "section": 1, "text": "Invented placeholder prose for a second, unrelated letter."},
    ]
    if overrides:
        for i, o in overrides.items():
            recs[i] = o
    return recs


def test_salutation_invariant_passes_at_correct_position(monkeypatch):
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    _mod._assert_salutation_invariant(_records())  # must not raise


def test_salutation_invariant_fatal_when_absent(monkeypatch):
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({0: {"book": 1, "section": 1, "text": "No salutation here at all."}})
    with pytest.raises(ValueError, match="found 0"):
        _mod._assert_salutation_invariant(recs)


def test_salutation_invariant_fatal_when_found_in_another_letters_body(monkeypatch):
    """MINOR 1's own regression: a salutation-like sentence surfacing in
    some OTHER letter's body prose (not just Letter 1's front matter) must
    be caught -- this is exactly what the old front-div-only check missed."""
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({2: {"book": 2, "section": 1, "text": _FAKE_SALUTATION + " stray invented text"}})
    with pytest.raises(ValueError, match="found 2"):
        _mod._assert_salutation_invariant(recs)


def test_salutation_invariant_fatal_when_duplicated_within_one_record(monkeypatch):
    """MINOR fix (Sol re-verification, 2026-07-21): the invariant now
    counts total OCCURRENCES (`str.count`, summed), not the number of
    records CONTAINING the phrase -- a single record quoting the
    salutation twice used to still pass (`len(hits) == 1`)."""
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({0: {"book": 1, "section": 1,
                          "text": _FAKE_SALUTATION + " " + _FAKE_SALUTATION}})
    with pytest.raises(ValueError, match="found 2"):
        _mod._assert_salutation_invariant(recs)


def test_salutation_invariant_fatal_when_not_at_start_of_letter1_section1(monkeypatch):
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({0: {"book": 1, "section": 1, "text": "An invented lead-in. " + _FAKE_SALUTATION}})
    with pytest.raises(ValueError, match="not at the start"):
        _mod._assert_salutation_invariant(recs)


def test_final_text_invariants_catch_empty_text_introduced_after_patches(monkeypatch):
    """MINOR 2: a patch that empties out a record must be caught by the
    POST-patch invariant pass, not solely by the earlier pre-patch
    per-letter check."""
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({1: {"book": 1, "section": 2, "text": "   "}})
    with pytest.raises(ValueError, match="empty text after patches"):
        _mod._assert_final_text_invariants(recs)


def test_final_text_invariants_catch_residual_markup_introduced_after_patches(monkeypatch):
    monkeypatch.setattr(_mod, "_SALUTATION", _FAKE_SALUTATION)
    recs = _records({1: {"book": 1, "section": 2, "text": "prose with <b>markup</b>"}})
    with pytest.raises(ValueError, match="un-stripped"):
        _mod._assert_final_text_invariants(recs)


# --- declared integrity manifest (BLOCKER c) --------------------------------

def test_load_integrity_fatal_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "does-not-exist.json")
    with pytest.raises(ValueError, match="not found"):
        _mod._load_integrity()


def test_write_then_validate_integrity_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    html_sha = {1: "a" * 64, 2: "b" * 64}
    pages = {"Page:X/1": "3", "Page:X/2": "4"}
    _mod._write_integrity_baseline(html_sha, pages)
    _mod._validate_integrity(html_sha, pages)  # must not raise

    declared = json.loads(_mod.GUMMERE_INTEGRITY.read_text(encoding="utf-8"))
    assert declared["letter_html_sha256"] == {"1": "a" * 64, "2": "b" * 64}
    assert declared["page_quality"] == pages


def test_validate_integrity_fatal_on_missing_declared_letter(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64}, {})
    with pytest.raises(ValueError, match="missing declared HTML hash"):
        _mod._validate_integrity({1: "a" * 64, 2: "b" * 64}, {})


def test_validate_integrity_fatal_on_undeclared_extra_letter(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64, 2: "b" * 64}, {})
    with pytest.raises(ValueError, match="never observed"):
        _mod._validate_integrity({1: "a" * 64}, {})


def test_validate_integrity_fatal_on_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64}, {})
    with pytest.raises(ValueError, match="does not match declared"):
        _mod._validate_integrity({1: "c" * 64}, {})


def test_validate_integrity_fatal_on_page_quality_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64}, {"Page:X/1": "3"})
    with pytest.raises(ValueError, match="does not match declared"):
        _mod._validate_integrity({1: "a" * 64}, {"Page:X/1": "2"})


def test_validate_integrity_fatal_on_missing_declared_page(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64}, {"Page:X/1": "3"})
    with pytest.raises(ValueError, match="missing declared page-quality"):
        _mod._validate_integrity({1: "a" * 64}, {"Page:X/1": "3", "Page:X/2": "3"})


def test_validate_integrity_fatal_on_undeclared_extra_page(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "GUMMERE_INTEGRITY", tmp_path / "gummere.integrity.json")
    _mod._write_integrity_baseline({1: "a" * 64}, {"Page:X/1": "3", "Page:X/2": "3"})
    with pytest.raises(ValueError, match="never transcluded"):
        _mod._validate_integrity({1: "a" * 64}, {"Page:X/1": "3"})


# --- docstring/README facts locked in against the real pinned cache --------

_CACHE = Path(__file__).resolve().parent.parent.parent / "build/gummere-wikisource-cache"
_requires_cache = pytest.mark.skipif(not _CACHE.is_dir(), reason="local Wikisource fetch cache not present")


@_requires_cache
def test_real_corpus_still_byte_identical_and_integrity_verified(monkeypatch, tmp_path):
    """End-to-end regression against the real, pinned, already-fetched
    cache: build() must reproduce the exact committed gummere.clean.json
    and the existing gummere.integrity.json must still validate."""
    real_clean = _mod.OUT_CLEAN.read_text(encoding="utf-8")
    records, report = _mod.build()
    produced = json.dumps(records, ensure_ascii=False, indent=1) + "\n"
    assert produced == real_clean
    assert report["n_records"] == 2139
    assert report["n_letters"] == 124
    assert report["n_page_transclusions"] == 780
    assert report["n_distinct_pages"] == 688
    assert report.get("merges") == [(41, 9, 8)]
