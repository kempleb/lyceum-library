"""Versioned fields emitted with each work manifest."""

from __future__ import annotations

from pathlib import Path

import pytest

from reader_pipeline.config import Manifest
from reader_pipeline.stage7_emit import _manifest_v1_fields


def test_manifest_v1_fields_include_fallback_licenses_and_emitted_apparatus(
    tmp_path, monkeypatch
):
    out_dir = tmp_path / "dist" / "fixture-work"
    out_dir.mkdir(parents=True)
    (out_dir / "sections.json").write_text("{}", encoding="utf-8")
    (out_dir / "figures.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("CORPUS_VERSION", raising=False)

    manifest = Manifest(
        {
            "work": {
                "id": "fixture-work",
                "slug": "fixture-route",
                "title": "Fixture Work",
                "author": "fixture-author",
                "language": "grc",
                "tlg_author": "9999",
                "tlg_work": "001",
                "greek_edition": "Fixture Greek Edition",
            },
            # The app's shortened slugs live in the registry block (the real
            # corpus shape — 44 works); registry.slug must win over work.slug.
            "registry": {"slug": "fixture-registry-route"},
            "citation": {"scheme": "book-section"},
            "bekker_range": {"first_column": "1.1", "last_column": "2.4"},
            "books": [
                {"n": 1, "start": "1.1", "end": "1.4"},
                {"n": 2, "start": "2.1", "end": "2.4"},
            ],
            "english": {
                "primary": {
                    "id": "fixture-primary",
                    "name": "Fixture Primary",
                    "model": "archive",
                },
                "overlays": [{
                    "id": "fixture-overlay",
                    "name": "Fixture Overlay",
                    "model": "manual",
                }],
            },
        },
        Path("fixture-work.yaml"),
    )

    fields = _manifest_v1_fields(manifest, out_dir)

    assert fields["schema_version"] == "manifest.v1"
    assert fields["id"] == "fixture-work"
    assert fields["author"] == "fixture-author"
    assert fields["title"] == "Fixture Work"
    assert fields["language"] == "grc"
    assert fields["route"] == "/fixture-author/fixture-registry-route"
    assert fields["citation"] == {
        "scheme": "book-section",
        "books": [
            {"n": 1, "start": "1.1", "end": "1.4"},
            {"n": 2, "start": "2.1", "end": "2.4"},
        ],
        "bekker_range": {"first_column": "1.1", "last_column": "2.4"},
    }
    assert fields["editions"] == [{
        "language": "grc",
        "edition": "Fixture Greek Edition",
        "source": {"kind": "tlg", "author": "9999", "work": "001"},
        "license": {"status": "unverified"},
    }]
    assert fields["translations"] == [
        {
            "id": "fixture-primary",
            "name": "Fixture Primary",
            "slot": "primary",
            "default": True,
            "alignment": "archive",
            "license": {"status": "unverified"},
        },
        {
            "id": "fixture-overlay",
            "name": "Fixture Overlay",
            "slot": "overlay",
            "default": False,
            "alignment": "manual",
            "license": {"status": "unverified"},
        },
    ]
    assert fields["apparatus"] == {
        "footnotes": False,
        "sidenotes": False,
        "paratext": False,
        "figures": True,
        "sections": True,
        "philosophers": False,
    }
    assert fields["corpus_version"] == "dev"


def test_manifest_v1_corpus_version_comes_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CORPUS_VERSION", "abc1234-2026-08-27")
    manifest = Manifest(
        {
            "work": {
                "id": "latin-fixture",
                "title": "Latin Fixture",
                "author": "fixture-author",
                "language": "lat",
                "phi_author": "9999",
                "phi_work": "002",
                "latin_edition": "Fixture Latin Edition",
            },
            "citation": {"scheme": "section"},
            "books": [{"n": 1, "start": "1", "end": "2"}],
        },
        Path("latin-fixture.yaml"),
    )

    fields = _manifest_v1_fields(manifest, tmp_path)

    assert fields["route"] == "/fixture-author/latin-fixture"
    assert fields["editions"][0]["source"]["kind"] == "phi"
    assert fields["translations"] == []
    assert fields["corpus_version"] == "abc1234-2026-08-27"
    # No registry block on this manifest -- presentation is omitted entirely,
    # never emitted as null/empty.
    assert "presentation" not in fields


def _minimal_manifest(work_extra, path="fixture-work.yaml", **extra_top):
    return Manifest(
        {
            "work": {
                "id": "fixture-work",
                "title": "Fixture Work",
                "author": "fixture-author",
                "language": "grc",
                "tlg_author": "9999",
                "tlg_work": "001",
                "greek_edition": "Fixture Greek Edition",
                **work_extra,
            },
            "citation": {"scheme": "dk"},
            "books": [{"n": 1, "start": "B1", "end": "B31"}],
            **extra_top,
        },
        Path(path),
    )


def test_manifest_v1_presentation_field_emits_registry_block_verbatim_and_strips_route(
    tmp_path,
):
    registry_block = {
        "id": "fixture-work",
        "slug": "fixture-slug",
        "title": "Fixture Work",
        "abbr": "Fix.",
        "workType": "fragments",
        "bookLabels": ["1"],
        "blurb": "A fixture blurb.",
        # Route ownership is registry-side per P1 -- this key should never
        # exist in practice, but stage7 must strip it defensively if it did.
        "route": "/fixture-author/should-be-stripped",
    }
    manifest = _minimal_manifest({}, registry=registry_block)

    fields = _manifest_v1_fields(manifest, tmp_path)

    assert "presentation" in fields
    assert "route" not in fields["presentation"]
    expected = {k: v for k, v in registry_block.items() if k != "route"}
    assert fields["presentation"] == expected
    # Verbatim means unmutated -- the source dict is untouched by the strip.
    assert registry_block["route"] == "/fixture-author/should-be-stripped"


def test_manifest_v1_translations_include_gorgias_shaped_column_sources_and_summary_overlay(
    tmp_path,
):
    """Mirrors manifests/gorgias-fragments.yaml's `english:` shape (Sol review
    finding 4): a primary translation, a per-column `column_sources` override
    for one fragment, and a `summary_overlay` scoped to two columns."""
    manifest = _minimal_manifest(
        {},
        english={
            "primary": {
                "id": "freeman",
                "name": "Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Blackwell, 1948)",
                "model": "freeman",
                "file": "freeman-ancilla/freeman-gorgias.clean.json",
            },
            "column_sources": [
                {
                    "column": "B11",
                    "file": "parnassos-gorgias/gatt-helen.clean.json",
                    "heading": "Encomium of Helen",
                    "credit": {
                        "translator": "Jurgen R. Gatt",
                        "source": (
                            "Gorgias/Gorgias: The Sicilian Orator and the "
                            "Platonic Dialogue, ed. S. Montgomery Ewegen and "
                            "Coleen P. Zoller (Parnassos Press — Fonte Aretusa)"
                        ),
                        "year": 2022,
                        "licence": {
                            "name": "CC BY-NC-ND 4.0",
                            "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
                        },
                    },
                },
            ],
            "summary_overlay": {"id": "freeman-summary", "columns": ["B11", "B11a"]},
        },
    )

    fields = _manifest_v1_fields(manifest, tmp_path)

    assert fields["translations"] == [
        {
            "id": "freeman",
            "name": "Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Blackwell, 1948)",
            "slot": "primary",
            "default": True,
            "alignment": "freeman",
            "license": {"status": "unverified"},
        },
        {
            "id": "freeman-summary",
            "name": "Kathleen Freeman, Ancilla to the Pre-Socratic Philosophers (Blackwell, 1948) — summary",
            "slot": "overlay",
            "kind": "summary",
            "default": False,
            "columns": ["B11", "B11a"],
            "license": {"status": "unverified"},
        },
        {
            "id": "gatt-helen",
            "name": (
                "Jurgen R. Gatt, in Gorgias/Gorgias: The Sicilian Orator and "
                "the Platonic Dialogue, ed. S. Montgomery Ewegen and Coleen "
                "P. Zoller (Parnassos Press — Fonte Aretusa)"
            ),
            "slot": "column",
            "default": False,
            "columns": ["B11"],
            "heading": "Encomium of Helen",
            "license": {
                "status": "licensed",
                "rationale": (
                    "Jurgen R. Gatt, tr., Gorgias/Gorgias: The Sicilian "
                    "Orator and the Platonic Dialogue, ed. S. Montgomery "
                    "Ewegen and Coleen P. Zoller (Parnassos Press — Fonte "
                    "Aretusa), 2022 (CC BY-NC-ND 4.0)"
                ),
                "source_url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
            },
        },
    ]


def _cc_column_source_manifest(licence_extra):
    """A column_sources entry whose credit.licence carries `status: cc`
    (John's ruling, 2026-09-22: CC translations must show their CC
    abbreviation, not the generic "Licensed" bucket)."""
    return _minimal_manifest(
        {},
        english={
            "column_sources": [
                {
                    "column": "B11",
                    "file": "parnassos-gorgias/gatt-helen.clean.json",
                    "credit": {
                        "translator": "Jurgen R. Gatt",
                        "licence": {"status": "cc", **licence_extra},
                    },
                },
            ],
        },
    )


def test_manifest_v1_column_source_cc_status_emits_cc_license_with_name_and_url(tmp_path):
    manifest = _cc_column_source_manifest(
        {
            "name": "CC BY-NC-ND 4.0",
            "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
        }
    )

    fields = _manifest_v1_fields(manifest, tmp_path)

    assert fields["translations"][0]["license"] == {
        "status": "cc",
        "name": "CC BY-NC-ND 4.0",
        "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
        "rationale": "Jurgen R. Gatt, tr.",
    }


def test_manifest_v1_column_source_cc_status_without_name_raises(tmp_path):
    manifest = _cc_column_source_manifest({})

    with pytest.raises(ValueError, match="cc"):
        _manifest_v1_fields(manifest, tmp_path)


def test_manifest_v1_column_source_no_licence_status_still_synthesises_licensed(tmp_path):
    """Regression pin: a `credit.licence` with a `name` but no `status` key
    at all keeps today's behaviour exactly -- synthesised `status: licensed`."""
    manifest = _minimal_manifest(
        {},
        english={
            "column_sources": [
                {
                    "column": "B11",
                    "file": "parnassos-gorgias/gatt-helen.clean.json",
                    "credit": {
                        "translator": "Jurgen R. Gatt",
                        "licence": {"name": "CC BY-NC-ND 4.0"},
                    },
                },
            ],
        },
    )

    fields = _manifest_v1_fields(manifest, tmp_path)

    assert fields["translations"][0]["license"] == {
        "status": "licensed",
        "rationale": "Jurgen R. Gatt, tr. (CC BY-NC-ND 4.0)",
    }
