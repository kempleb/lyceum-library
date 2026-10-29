from __future__ import annotations

import sys
from pathlib import Path

import pytest
from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))

from reader_pipeline import scheme as scheme_mod
from reader_pipeline import stage1_latin
from reader_pipeline.config import Manifest
from reader_pipeline.stage1_latin import (
    _assert_l_title_is_label_only,
    _derive_transposed_blocks,
    _parse_verse,
    _title_content_hash,
    _transposition_seam_note,
    parse_spine,
)

# PHI's verse export shape: lowercase "book" outer div (the same
# citation.div_types override De Officiis' book-section manifest uses),
# flat <l n="…"> children — no section level at all.
SCHEME = scheme_mod.for_manifest(
    {"citation": {"scheme": "verse-line", "div_types": {"page": "book"}}}
)


def _manifest(books: list[dict] | None = None, citation_extra: dict | None = None) -> Manifest:
    # Every fixture XML below is a single book, n="1" -- this default satisfies
    # the now-mandatory per-book citation.transpositions declaration (an
    # explicit empty list) for any test that doesn't care about transposition
    # behavior itself; a test that does passes its own via citation_extra
    # (which overrides this key outright via dict.update below).
    # `title_labels: []` similarly satisfies the now-mandatory (adversarial-
    # review Finding 2) declared-title-hash gate for any test whose fixture
    # carries no <l n="t"|"t2"> title line at all; a test that does declares
    # its own hash(es) via citation_extra.
    citation = {
        "scheme": "verse-line", "div_types": {"page": "book"},
        "transpositions": {"1": []}, "title_labels": [],
    }
    citation.update(citation_extra or {})
    data = {
        "work": {
            "id": "DRNFIX", "phi_author": "0550", "phi_work": "001",
            "latin_edition": "Fixture", "language": "lat", "no_english": True,
        },
        "citation": citation,
        "books": books or [],
    }
    return Manifest(data, ROOT / "manifests" / "fake.yaml")


def _tree(xml: str):
    return etree.fromstring(xml.encode("utf-8")).getroottree()


def _write_tmp_xml(tree) -> Path:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        f.write(etree.tostring(tree))
        return Path(f.name)


# --- l-level title-line assertion -------------------------------------------


def test_l_title_label_only_accepts_a_declared_hash():
    l_el = etree.fromstring(
        '<l xmlns="http://www.tei-c.org/ns/1.0" n="t">'
        '<label type="head">FICTA CARMINA</label></l>'
    )
    declared = [_title_content_hash("FICTA CARMINA")]
    _assert_l_title_is_label_only(l_el, "t", "1", declared, _manifest())  # no raise


def test_l_title_without_nested_label_fails_loudly():
    l_el = etree.fromstring(
        '<l xmlns="http://www.tei-c.org/ns/1.0" n="t">A bare title with no label wrapper</l>'
    )
    with pytest.raises(ValueError, match="no nested <label>"):
        _assert_l_title_is_label_only(l_el, "t", "1", [], _manifest())


def test_l_title_undeclared_content_fails_loudly():
    # A synthetic n="t"/"t2" line whose content hash is NOT declared in
    # citation.title_labels must never be silently dropped — the same
    # "may be substantive content" guard as book-section's title-div check,
    # one level down, now gated on the declared-hash mechanism rather than
    # a shape heuristic.
    l_el = etree.fromstring(
        '<l xmlns="http://www.tei-c.org/ns/1.0" n="t2">'
        '<label type="head">This reads like an ordinary sentence, not a heading.</label></l>'
    )
    with pytest.raises(ValueError, match="is not declared in citation.title_labels"):
        _assert_l_title_is_label_only(l_el, "t2", "1", [], _manifest())


def test_title_lines_are_dropped_end_to_end():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="t"><label type="head">FICTA CARMINA</label></l>
<l n="t2"><label type="head">LIBER FICTVS</label></l>
<l n="1">Fictum carmen prima linea nunc canitur.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={"title_labels": [
        {"sha256_16": _title_content_hash("FICTA CARMINA"), "note": "synthetic whole-work title line"},
        {"sha256_16": _title_content_hash("LIBER FICTVS"), "note": "synthetic per-book heading line"},
    ]})
    flat = _parse_verse(tree, SCHEME, manifest)
    assert [e["lineref"] for e in flat] == ["1"]
    assert flat[0]["column"] == "1.1"


# --- lacuna CONTENT classification (design delta over §3.2) ------------------


def test_asterisk_only_line_is_classified_lacuna():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="1a">* * *</l>
<l n="2">Tertia deinde linea sequitur ordine recto.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={"lacunae": {"1": ["1a"]}})
    flat = _parse_verse(tree, SCHEME, manifest)
    by_ref = {e["lineref"]: e for e in flat}
    assert by_ref["1a"]["role"] == "lacuna"
    assert by_ref["1a"]["text"] == ""  # no Latin tokens survive for a lacuna
    assert by_ref["1"]["role"] == "text"
    assert by_ref["2"]["role"] == "text"


def test_bracketed_real_text_with_lettered_suffix_is_not_a_lacuna():
    # The 3.672a counter-case: a lettered-suffix line whose content is a
    # genuine bracketed editorial insertion (real words), not an asterisk
    # gap — must classify as ordinary verse, not a lacuna, even though its
    # `n` LOOKS exactly like a lacuna token shape.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="672">Fictum carmen sextam et septuagesimam lineam profert.</l>
<l n="672a">[fictum et suppositum verbum hic interseritur]</l>
<l n="673">Nec ullum verum hic latet indicium.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={"lacunae": {"1": []}})
    flat = _parse_verse(tree, SCHEME, manifest)
    by_ref = {e["lineref"]: e for e in flat}
    assert by_ref["672a"]["role"] == "text"
    assert by_ref["672a"]["text"] == "[fictum et suppositum verbum hic interseritur]"


def test_range_token_is_always_a_lacuna():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="2-9">* * *</l>
<l n="10">Post lacunam decima linea sequitur.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={"lacunae": {"1": ["2-9"]}})
    flat = _parse_verse(tree, SCHEME, manifest)
    by_ref = {e["lineref"]: e for e in flat}
    assert by_ref["2-9"]["role"] == "lacuna"
    assert by_ref["2-9"]["column"] == "1.2-9"


def test_range_token_with_non_gap_content_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="2-9">Non est lacuna sed textus verus hic.</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="carries non-gap content"):
        _parse_verse(tree, SCHEME, _manifest(citation_extra={"lacunae": {"1": ["2-9"]}}))


# --- bidirectional lacuna declaration gate -----------------------------------


def test_undeclared_observed_lacuna_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="1a">* * *</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="undeclared \\(observed but not declared\\): \\['1a'\\]"):
        _parse_verse(tree, SCHEME, _manifest(citation_extra={"lacunae": {}}))


def test_stale_declared_lacuna_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="stale \\(declared but not observed\\): \\['1a'\\]"):
        _parse_verse(tree, SCHEME, _manifest(citation_extra={"lacunae": {"1": ["1a"]}}))


# --- hyphen-rejoin ban --------------------------------------------------------


def test_hyphen_ending_verse_line_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen inter-</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="hyphenated wrap"):
        _parse_verse(tree, SCHEME, _manifest())


# --- transposition derivation -------------------------------------------------


def test_derive_transposed_blocks_single_line_case():
    # Mirrors the real DRN book 1 shape ("14" reprinted after "15").
    doc = ["1", "2", "3", "5", "4", "6"]
    assert _derive_transposed_blocks(doc) == [{"start": "4", "end": "4", "before": "5"}]


def test_derive_transposed_blocks_multi_line_case():
    # Mirrors the real DRN shape of a contiguous multi-line block ("50..61"
    # reprinted after "135").
    doc = ["1", "2", "10", "5", "6", "7", "11"]
    assert _derive_transposed_blocks(doc) == [
        {"start": "5", "end": "7", "before": "10"},
    ]


def test_derive_transposed_blocks_handles_a_lettered_before_anchor():
    # Mirrors the real DRN book 6 shape ("48..91" reprinted after "95a").
    doc = ["93", "94", "95", "95a", "48", "49", "96"]
    assert _derive_transposed_blocks(doc) == [
        {"start": "48", "end": "49", "before": "95a"},
    ]


def test_derive_transposed_blocks_no_transposition_is_empty():
    assert _derive_transposed_blocks(["1", "2", "3", "4"]) == []


def test_transposition_declaration_mismatch_fails_loudly():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="3">Tertia linea nunc ante secundam ponitur.</l>
<l n="2">Secunda linea nunc post tertiam sequitur.</l>
<l n="4">Quarta deinde linea sequitur ordine recto.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={
        "lacunae": {"1": []},
        "transpositions": {"1": [{"start": "2", "end": "2", "before": "9"}]},  # wrong "before"
    })
    with pytest.raises(ValueError, match="transposition mismatch"):
        _parse_verse(tree, SCHEME, manifest)


def test_transposition_declaration_match_passes_and_attaches_seam_note():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="3">Tertia linea nunc ante secundam ponitur.</l>
<l n="2">Secunda linea nunc post tertiam sequitur.</l>
<l n="4">Quarta deinde linea sequitur ordine recto.</l>
</div>
</body></text></TEI>"""
    )
    manifest = _manifest(citation_extra={
        "lacunae": {"1": []},
        "transpositions": {"1": [{"start": "2", "end": "2", "before": "3"}]},
    })
    flat = _parse_verse(tree, SCHEME, manifest)
    by_ref = {e["lineref"]: e for e in flat}
    assert by_ref["2"]["seam_note"] == _transposition_seam_note("2", "2", "3")
    assert "seam_note" not in by_ref["1"]


def test_transposition_undeclared_manifest_fails_loudly():
    # Adversarial-review blocker: an absent citation.transpositions
    # manifest key used to skip the cross-check entirely (fail OPEN,
    # mirroring cross_section_rejoins' "absent means no-op" precedent).
    # A verse-line work's transposition declaration is now REQUIRED --
    # this proves omission of the whole key is a hard build error, not a
    # silent no-op.
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="3">Tertia linea nunc ante secundam ponitur.</l>
<l n="2">Secunda linea nunc post tertiam sequitur.</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="citation.transpositions is required"):
        _parse_verse(
            tree, SCHEME,
            _manifest(citation_extra={"lacunae": {"1": []}, "transpositions": None}),
        )


def test_transposition_missing_book_declaration_fails_loudly():
    # A citation.transpositions dict that omits ONE book's entry (rather
    # than the whole key) must fail just as loudly -- "every book in the
    # spine" means every book, not "every book that happens to be
    # declared."
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="1">Fictum carmen prima linea nunc canitur.</l>
</div>
</body></text></TEI>"""
    )
    with pytest.raises(ValueError, match="book 1 has no citation.transpositions"):
        _parse_verse(
            tree, SCHEME,
            _manifest(citation_extra={"lacunae": {"1": []}, "transpositions": {}}),
        )


# --- parse_spine dispatch: verse-line end to end ------------------------------


def test_parse_spine_dispatches_to_verse_and_preserves_document_order():
    tree = _tree(
        """<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div type="book" n="1">
<l n="t"><label type="head">FICTA CARMINA</label></l>
<l n="t2"><label type="head">LIBER FICTVS</label></l>
<l n="1">Fictum carmen prima linea nunc canitur.</l>
<l n="1a">* * *</l>
<l n="2">Tertia deinde linea sequitur ordine recto.</l>
</div>
</body></text></TEI>"""
    )
    path = _write_tmp_xml(tree)
    try:
        manifest = _manifest(
            books=[{"n": 1, "start": "1.1", "end": "1.2"}],
            citation_extra={
                "lacunae": {"1": ["1a"]},
                "title_labels": [
                    {"sha256_16": _title_content_hash("FICTA CARMINA"), "note": "synthetic whole-work title line"},
                    {"sha256_16": _title_content_hash("LIBER FICTVS"), "note": "synthetic per-book heading line"},
                ],
            },
        )
        spine = parse_spine(path, manifest)
    finally:
        path.unlink()

    assert [s["column"] for s in spine["segments"]] == ["1.1", "1.1a", "1.2"]
    assert [s["book"] for s in spine["segments"]] == [1, 1, 1]
    lacuna_seg = spine["segments"][1]
    assert lacuna_seg["lines"] == [{"n": 1, "text": "", "role": "lacuna"}]
    assert spine["edition"] == "Fixture"


# --- run_export: work.export_verse_mode picks -y, per-mode export dir -------


def _latin_export_manifest(verse):
    work = {"id": "OFFFIX", "phi_author": "0474", "phi_work": "055", "language": "lat"}
    if verse is not None:
        work["export_verse_mode"] = verse
    return Manifest(
        {
            "work": work,
            "citation": {"scheme": "book-section", "div_types": {"page": "book", "section": "section"}},
            "books": [{"n": 1, "start": "1.1", "end": "1.10"}],
            "sources": {"diogenes_server": "/Applications/Diogenes.app/Contents/server"},
        },
        ROOT / "manifests" / "fake.yaml",
    )


def _capture_latin_export(monkeypatch, tmp_path, writes=False):
    monkeypatch.setattr(stage1_latin, "EXPORT_DIR", tmp_path / "export")
    monkeypatch.setattr(stage1_latin, "RAW_EXPORT_DIR", tmp_path / "export-raw")
    monkeypatch.setattr(stage1_latin, "_diogenes_scratch_config_dir", lambda manifest: tmp_path / "cfg")
    calls: list = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, "cwd": kwargs.get("cwd")})
        if writes:
            outdir = Path(cmd[cmd.index("-o") + 1])
            for work in ("048", "055"):
                f = outdir / "Diogenes-Resources" / "xml" / "phi" / f"phi0474{work}.xml"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(f"{work} {'-y' in cmd}", encoding="utf-8")

    monkeypatch.setattr(stage1_latin.subprocess, "run", fake_run)
    return calls


@pytest.mark.parametrize("verse,mode_dir", [(True, "verse"), (False, "plain")])
def test_run_export_uses_stock_script_with_y_only_in_verse_mode(monkeypatch, tmp_path, verse, mode_dir):
    calls = _capture_latin_export(monkeypatch, tmp_path)
    # The fake export writes nothing, so run_export fails its own
    # post-export check; the command it built is what this test asserts on.
    with pytest.raises(FileNotFoundError):
        stage1_latin.run_export(_latin_export_manifest(verse))
    cmd = calls[0]["cmd"]
    assert cmd[:2] == ["perl", "xml-export.pl"]
    assert ("-y" in cmd) is verse
    assert cmd[cmd.index("-o") + 1] == str(tmp_path / "export-raw" / mode_dir)
    assert calls[0]["cwd"] == Path("/Applications/Diogenes.app/Contents/server")


def test_run_export_copies_only_this_work_and_reuses_the_author_export(monkeypatch, tmp_path):
    calls = _capture_latin_export(monkeypatch, tmp_path, writes=True)
    out = stage1_latin.run_export(_latin_export_manifest(True))
    assert out == tmp_path / "export" / "Diogenes-Resources" / "xml" / "phi" / "phi0474055.xml"
    assert out.read_text(encoding="utf-8") == "055 True"
    assert sorted(p.name for p in out.parent.iterdir()) == ["phi0474055.xml"]
    out.unlink()
    stage1_latin.run_export(_latin_export_manifest(True))
    assert len(calls) == 1  # the per-mode author export is reused


def test_run_export_requires_export_verse_mode(monkeypatch, tmp_path):
    calls = _capture_latin_export(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="export_verse_mode"):
        stage1_latin.run_export(_latin_export_manifest(None))
    assert calls == []
