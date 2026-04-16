# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Extract Ed-Fi Unified Data Model attribute names and descriptions.

Fetches the Ed-Fi Resource API OpenAPI spec from GitHub, extracts
(entity, attribute, description) triples, and writes a vendored CSV.

Output: docs/superpowers/specs/edfi-v6.1.0-attributes.csv

Usage:
    uv run scripts/extract_edfi_schema.py

Design reference:
    docs/superpowers/specs/2026-04-16-edfi-profiling-and-description-propagation-design.md
"""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path
from typing import TextIO

import yaml

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    return _CAMEL_RE.sub("_", name).lower()


def _extract_attributes(spec: dict) -> list[dict[str, str]]:
    """Extract (entity, attribute, description) triples from an OpenAPI spec."""
    rows: list[dict[str, str]] = []
    schemas = spec.get("components", {}).get("schemas", {})
    for entity_name, schema in schemas.items():
        properties = schema.get("properties", {})
        for attr_name, attr_def in properties.items():
            rows.append(
                {
                    "entity": entity_name,
                    "attribute_camel": attr_name,
                    "attribute_snake": _camel_to_snake(attr_name),
                    "description": attr_def.get("description", ""),
                }
            )
    return rows


EDFI_REPO = "Ed-Fi-Alliance-OSS/Ed-Fi-Data-Standard"
EDFI_TAG = "v6.1.0"
EDFI_SPEC_PATH = "Schemas/JSON/Ed-Fi-Resource-API-Specification.yaml"

CSV_FIELDS: tuple[str, ...] = (
    "entity",
    "attribute_camel",
    "attribute_snake",
    "description",
)

OUTPUT_CSV = Path("docs/superpowers/specs/edfi-v6.1.0-attributes.csv")


def _write_csv(rows: list[dict[str, str]], fh: TextIO) -> None:
    """Write attribute rows to CSV."""
    writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def _fetch_spec() -> dict:
    """Fetch the Ed-Fi OpenAPI spec from GitHub."""
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{EDFI_REPO}/contents/{EDFI_SPEC_PATH}",
            "--header",
            "Accept: application/vnd.github.raw+json",
            "--method",
            "GET",
            "-F",
            f"ref={EDFI_TAG}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return yaml.safe_load(result.stdout)


def main() -> None:
    spec = _fetch_spec()
    rows = _extract_attributes(spec)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        _write_csv(rows, fh)

    print(f"Wrote {len(rows)} attributes to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
