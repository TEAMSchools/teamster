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

import yaml


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
        - config.meta.contains_pii: always written (authoritative).
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

            # PII flag: always write (authoritative)
            config = column.setdefault("config", {})
            meta = config.setdefault("meta", {})
            meta["contains_pii"] = entry["contains_pii"]

    if return_stats:
        return doc, stats
    return doc


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
