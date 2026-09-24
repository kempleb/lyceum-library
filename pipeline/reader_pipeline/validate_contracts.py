"""Validate Lyceum's versioned JSON contracts.

Run from pipeline/ with::

    python -m reader_pipeline.validate_contracts --schemas ../schemas ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


SCHEMA_FILES = {
    "manifest": "manifest.v1.json",
    "snapshot": "snapshot.v1.json",
    "registry": "route-registry.v1.json",
}


def _pointer(parts: Iterable[Any]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded) if encoded else "/"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schemas(schema_dir: Path) -> dict[str, dict]:
    """Load every contract schema and check it against draft 2020-12."""
    schemas = {
        kind: load_json(schema_dir / filename)
        for kind, filename in SCHEMA_FILES.items()
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    return schemas


def validation_errors(
    instance: Any, schema: dict, *, registry: bool = False
) -> list[tuple[str, str]]:
    """Return JSON Pointer/message pairs for one instance."""
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [
        (_pointer(error.absolute_path), error.message)
        for error in validator.iter_errors(instance)
    ]
    if registry and isinstance(instance, dict):
        seen: dict[str, int] = {}
        routes = instance.get("routes")
        if isinstance(routes, list):
            for index, entry in enumerate(routes):
                if not isinstance(entry, dict) or not isinstance(entry.get("route"), str):
                    continue
                route = entry["route"]
                if route in seen:
                    errors.append((
                        f"/routes/{index}/route",
                        f"duplicate route {route!r}; first declared at /routes/{seen[route]}/route",
                    ))
                else:
                    seen[route] = index
    return sorted(errors)


def unverified_license_warnings(instance: Any) -> list[str]:
    """Find allowed, but not yet verified, manifest license records."""
    warnings = []
    if not isinstance(instance, dict):
        return warnings
    for collection in ("editions", "translations"):
        entries = instance.get(collection)
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            license_data = entry.get("license")
            if isinstance(license_data, dict) and license_data.get("status") == "unverified":
                warnings.append(f"/{collection}/{index}/license/status")
    return warnings


def _validate_file(path: Path, schema: dict, *, registry: bool = False) -> bool:
    try:
        instance = load_json(path)
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR {path} /: {error}")
        return False

    errors = validation_errors(instance, schema, registry=registry)
    for pointer, message in errors:
        print(f"ERROR {path} {pointer}: {message}")
    for pointer in unverified_license_warnings(instance):
        print(f"WARNING {path} {pointer}: license status is 'unverified'")
    if not errors:
        print(f"OK {path}")
    return not errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", type=Path, default=Path("../schemas"))
    parser.add_argument(
        "--manifest", type=Path, nargs="+", action="append", default=[], metavar="FILE"
    )
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--dist", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        schemas = load_schemas(args.schemas)
    except (OSError, json.JSONDecodeError, SchemaError) as error:
        print(f"ERROR {args.schemas} /: schema self-check failed: {error}")
        return 1

    manifests = [path for group in args.manifest for path in group]
    if args.dist:
        # A missing --dist directory must fail loudly: Path.glob on a missing
        # dir yields nothing, which would read as a clean (empty) run.
        if not args.dist.is_dir():
            print(f"ERROR {args.dist} /: --dist directory does not exist")
            return 1
        found = sorted(args.dist.glob("*/manifest.json"))
        if not found:
            print(f"ERROR {args.dist} /: --dist contains no */manifest.json")
            return 1
        manifests.extend(found)

    if not manifests and not args.snapshot and not args.registry:
        print("ERROR /: nothing to validate — pass --manifest, --snapshot, --registry, or --dist")
        return 1

    ok = True
    for path in manifests:
        ok = _validate_file(path, schemas["manifest"]) and ok
    if args.snapshot:
        ok = _validate_file(args.snapshot, schemas["snapshot"]) and ok
    if args.registry:
        ok = _validate_file(args.registry, schemas["registry"], registry=True) and ok
    print(f"checked: {len(manifests)} manifest(s)"
          f"{', snapshot' if args.snapshot else ''}"
          f"{', registry' if args.registry else ''}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
