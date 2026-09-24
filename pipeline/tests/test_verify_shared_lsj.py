"""verify_shared_lsj.py — the shared-dictionary safety gate (LSJ/Greek,
Lewis & Short/Latin). Covers the FAIL-OPEN fix (Wave 2 Batch 1b review,
item 4): an unrecognized `work.language` used to fall back to "lsj"
(Greek's shard dir) via `SHARD_DIR.get(language, "lsj")`, silently checking
a mis-declared work's dictionary keys against the wrong dictionary instead
of failing the build. It must reject instead.
"""

from __future__ import annotations

import json
from pathlib import Path

from reader_pipeline import verify_shared_lsj


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_rejects_unknown_language(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(verify_shared_lsj, "BUILD_DIR", tmp_path)
    dist = tmp_path / "dist"
    _write(dist / "badwork" / "analyses.json", {
        "foo": [{"lemma": "foo", "gloss": "", "parse": "", "lsj": ["foo-key"]}],
    })
    _write(dist / "badwork" / "manifest.json", {"work": {"language": "xx"}})

    rc = verify_shared_lsj.main()

    assert rc == 1
    err = capsys.readouterr().err
    assert "UNRECOGNIZED language" in err
    assert "badwork" in err


def test_grc_default_language_still_resolves(tmp_path, monkeypatch):
    # Sanity check alongside the rejection test above: a work with NO
    # manifest.json (or none carrying work.language) still defaults to
    # 'grc' and resolves against the 'lsj' shard dir exactly as before --
    # the fix rejects UNRECOGNIZED languages, not the legitimate default.
    monkeypatch.setattr(verify_shared_lsj, "BUILD_DIR", tmp_path)
    dist = tmp_path / "dist"
    _write(dist / "goodwork" / "analyses.json", {
        "foo": [{"lemma": "foo", "gloss": "", "parse": "", "lsj": ["lo/gos"]}],
    })
    _write(dist / "lsj" / "l.json", {"lo/gos": {"key": "lo/gos", "head": "λόγος", "html": ""}})

    rc = verify_shared_lsj.main()

    assert rc == 0


def test_lat_language_resolves_against_ls_shard(tmp_path, monkeypatch):
    # A correctly-declared 'lat' work resolves against the SEPARATE 'ls'
    # (Lewis & Short) shard dir, never 'lsj' -- unaffected by the
    # unknown-language rejection above.
    monkeypatch.setattr(verify_shared_lsj, "BUILD_DIR", tmp_path)
    dist = tmp_path / "dist"
    _write(dist / "de-officiis" / "analyses.json", {
        "honestum": [{"lemma": "honestus", "gloss": "", "parse": "neut nom sg", "lsj": ["ho^nestus"]}],
    })
    _write(dist / "de-officiis" / "manifest.json", {"work": {"language": "lat"}})
    _write(dist / "ls" / "h.json", {"ho^nestus": {"key": "ho^nestus", "head": "honestus", "html": ""}})

    rc = verify_shared_lsj.main()

    assert rc == 0
