"""NIT (Wave 2 Batch 1a): align/reference.py + align/glossing.py used to
hardcode "greek_spine.json" unconditionally — unexercised for Latin so far
only because no Latin work has an `english` block yet (align/ is English-
alignment tooling), not because it was actually correct. Both now dispatch
the spine filename per work.language, mirroring stage2_validate.py/
stage7_emit.py's existing `_SPINE_FILENAMES` dispatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pipeline"))

from reader_pipeline import config
from reader_pipeline.align import glossing, reference


class _FakeManifest:
    def __init__(self, language: str):
        self.language = language


def test_reference_spine_filename_defaults_to_grc_with_no_work_id():
    assert reference._spine_filename(None) == "greek_spine.json"


def test_reference_spine_filename_dispatches_on_work_language(monkeypatch):
    monkeypatch.setattr(
        config.Manifest, "for_work", classmethod(lambda cls, work, public=False: _FakeManifest("lat"))
    )
    assert reference._spine_filename("de-officiis") == "latin_spine.json"


def test_reference_spine_filename_grc_work(monkeypatch):
    monkeypatch.setattr(
        config.Manifest, "for_work", classmethod(lambda cls, work, public=False: _FakeManifest("grc"))
    )
    assert reference._spine_filename("EN") == "greek_spine.json"


def test_glossing_spine_filename_defaults_to_grc_with_no_work_id():
    assert glossing._spine_filename(None) == "greek_spine.json"


def test_glossing_spine_filename_dispatches_on_work_language(monkeypatch):
    monkeypatch.setattr(
        config.Manifest, "for_work", classmethod(lambda cls, work, public=False: _FakeManifest("lat"))
    )
    assert glossing._spine_filename("de-officiis") == "latin_spine.json"
