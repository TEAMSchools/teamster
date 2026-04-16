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


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
