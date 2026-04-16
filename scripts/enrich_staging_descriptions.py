# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Enrich dbt staging YAML files with descriptions and PII flags.

Reads JSON mapping file(s) produced by extract_pdf_dictionary.py and writes
description and config.meta.contains_pii to staging YAML properties files.

Usage:
    uv run scripts/enrich_staging_descriptions.py <json_path> [<json_path> ...]

Design reference:
    docs/superpowers/specs/2026-04-16-data-dictionary-enrichment-design.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

import yaml

# All directories that may contain staging YAML files
STAGING_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/powerschool/models/sis/staging/properties"),
    Path("src/dbt/kipptaf/models/powerschool/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_now/sftp/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/workforce_manager/staging/properties"),
    Path("src/dbt/kipptaf/models/adp/payroll/staging/properties"),
)


def enrich_yaml_data(
    doc: dict,
    mapping_entries: list[dict],
    return_stats: bool = False,
) -> dict | tuple[dict, dict[str, int]]:
    """Enrich a YAML document with descriptions and PII flags.

    Args:
        doc: Parsed YAML document (from yaml.safe_load).
        mapping_entries: List of mapping entry dicts from JSON.
        return_stats: If True, return (doc, stats) tuple.

    Returns:
        Enriched YAML document dict, or (doc, stats) if return_stats=True.

    Behavior:
        - description: added only if absent or empty.
        - config.meta.contains_pii: written only when true (absence = not PII).
        - Columns with no mapping entry are not modified.
    """
    # Build lookup: (model, column) -> entry
    lookup: dict[tuple[str, str], dict] = {}
    for entry in mapping_entries:
        key = (entry["model"], entry["column"])
        lookup[key] = entry

    stats = {"enriched": 0, "skipped": 0, "total": 0}

    for model in doc.get("models", []) or []:
        model_name = model["name"]
        for column in model.get("columns", []) or []:
            stats["total"] += 1
            col_name = column["name"]
            key = (model_name, col_name)
            if key not in lookup:
                continue

            entry = lookup[key]

            # Description: add only if absent or empty
            existing_desc = column.get("description", "")
            if existing_desc and str(existing_desc).strip():
                stats["skipped"] += 1
            else:
                column["description"] = entry["description"]
                stats["enriched"] += 1

            # PII flag: write only when true (absence = not PII)
            if entry["contains_pii"]:
                config = column.setdefault("config", {})
                meta = config.setdefault("meta", {})
                meta["contains_pii"] = True

    if return_stats:
        return doc, stats
    return doc


def find_yaml_file(model_name: str) -> Path | None:
    """Find the YAML properties file for a given staging model name.

    Searches all known staging YAML directories for a file named
    <model_name>.yml.
    """
    for directory in STAGING_YAML_DIRS:
        if not directory.exists():
            continue
        candidate = directory / f"{model_name}.yml"
        if candidate.exists():
            return candidate
    return None


def write_yaml(doc: dict, fh: TextIO) -> None:
    """Write YAML document preserving key order."""
    yaml.dump(
        doc,
        fh,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: uv run scripts/enrich_staging_descriptions.py "
            "<json_path> [<json_path> ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load all mapping files (single pass)
    all_entries: list[dict] = []
    table_descriptions: dict[str, str] = {}
    for json_path in sys.argv[1:]:
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        all_entries.extend(data.get("entries", []))
        table_descriptions.update(data.get("table_descriptions", {}))
        print(f"Loaded {len(data.get('entries', []))} entries from {json_path}")

    # Group entries by model
    entries_by_model: dict[str, list[dict]] = {}
    for entry in all_entries:
        model = entry["model"]
        entries_by_model.setdefault(model, []).append(entry)

    # Process each model
    total_enriched = 0
    total_skipped = 0
    total_columns = 0
    files_modified = 0

    for model_name in sorted(entries_by_model):
        yaml_path = find_yaml_file(model_name)
        if yaml_path is None:
            print(f"  SKIP {model_name}: YAML file not found")
            continue

        with yaml_path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)

        if not doc:
            print(f"  SKIP {model_name}: empty YAML")
            continue

        # Enrich model-level description from table_descriptions
        model_desc_added = False
        if model_name in table_descriptions:
            for model in doc.get("models", []) or []:
                if model["name"] == model_name:
                    existing = model.get("description", "")
                    if not existing or not str(existing).strip():
                        # Rebuild dict with description before columns
                        new_model = {
                            "name": model["name"],
                            "description": table_descriptions[model_name],
                        }
                        new_model.update(
                            {k: v for k, v in model.items() if k != "name"}
                        )
                        model.clear()
                        model.update(new_model)
                        model_desc_added = True

        result, stats = enrich_yaml_data(
            doc, entries_by_model[model_name], return_stats=True
        )

        if stats["enriched"] > 0 or model_desc_added:
            with yaml_path.open("w", encoding="utf-8") as fh:
                write_yaml(result, fh)
            files_modified += 1

        total_enriched += stats["enriched"]
        total_skipped += stats["skipped"]
        total_columns += stats["total"]

        print(
            f"  {model_name}: "
            f"{stats['enriched']} enriched, "
            f"{stats['skipped']} skipped (existing), "
            f"{stats['total']} total"
        )

    print("\nSummary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Columns enriched: {total_enriched}")
    print(f"  Columns skipped (existing desc): {total_skipped}")
    print(f"  Total columns processed: {total_columns}")


if __name__ == "__main__":
    main()
