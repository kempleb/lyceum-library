"""Schema and validator coverage for Lyceum's versioned contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from reader_pipeline.validate_contracts import (
    load_schemas,
    unverified_license_warnings,
    validation_errors,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = load_schemas(ROOT / "schemas")
SAMPLE_MANIFEST = ROOT / "fixtures" / "data" / "sample-work" / "manifest.json"
SNAPSHOT = ROOT / "fixtures" / "taxonomy.json"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_manifest_fixture_passes_and_unverified_is_only_a_warning():
    manifest = _json(SAMPLE_MANIFEST)
    assert validation_errors(manifest, SCHEMAS["manifest"]) == []
    assert unverified_license_warnings(manifest) == [
        "/editions/0/license/status"
    ]


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "id",
        "author",
        "title",
        "language",
        "route",
        "citation",
        "editions",
        "translations",
        "apparatus",
        "corpus_version",
    ],
)
def test_manifest_missing_each_required_field_fails(field):
    manifest = copy.deepcopy(_json(SAMPLE_MANIFEST))
    del manifest[field]
    errors = validation_errors(manifest, SCHEMAS["manifest"])
    assert errors
    assert any(f"'{field}' is a required property" in message for _, message in errors)


def test_registry_duplicate_routes_fail_even_when_schema_shape_is_valid():
    registry = {
        "schema_version": "route-registry.v1",
        "routes": [
            {"route": "/plato/republic", "corpus": "classical", "work": "republic"},
            {"route": "/plato/republic", "corpus": "other", "work": "republic-copy"},
        ],
    }
    errors = validation_errors(registry, SCHEMAS["registry"], registry=True)
    assert errors == [(
        "/routes/1/route",
        "duplicate route '/plato/republic'; first declared at /routes/0/route",
    )]


def test_snapshot_fixture_validates():
    assert validation_errors(_json(SNAPSHOT), SCHEMAS["snapshot"]) == []


def test_snapshot_missing_period_label_fails():
    snapshot = copy.deepcopy(_json(SNAPSHOT))
    del snapshot["taxonomy"]["period_label"]
    errors = validation_errors(snapshot, SCHEMAS["snapshot"])
    assert errors
    assert any("'period_label' is a required property" in message for _, message in errors)


def test_snapshot_wrong_type_period_label_fails():
    snapshot = copy.deepcopy(_json(SNAPSHOT))
    snapshot["taxonomy"]["period_label"] = ["not", "an", "object"]
    errors = validation_errors(snapshot, SCHEMAS["snapshot"])
    assert errors


def test_cli_dist_missing_directory_fails(capsys):
    from reader_pipeline.validate_contracts import main

    rc = main(["--schemas", str(ROOT / "schemas"), "--dist", str(ROOT / "no-such-dist")])
    assert rc == 1
    assert "--dist directory does not exist" in capsys.readouterr().out


def test_cli_dist_empty_directory_fails(tmp_path, capsys):
    from reader_pipeline.validate_contracts import main

    rc = main(["--schemas", str(ROOT / "schemas"), "--dist", str(tmp_path)])
    assert rc == 1
    assert "contains no */manifest.json" in capsys.readouterr().out


def test_cli_reports_checked_count(capsys):
    from reader_pipeline.validate_contracts import main

    rc = main([
        "--schemas", str(ROOT / "schemas"),
        "--manifest", str(SAMPLE_MANIFEST),
        "--snapshot", str(SNAPSHOT),
    ])
    assert rc == 0
    assert "checked: 1 manifest(s), snapshot" in capsys.readouterr().out
