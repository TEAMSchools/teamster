# /// script
# requires-python = ">=3.13"
# dependencies = ["pypdf>=4.0", "pyyaml>=6.0"]
# ///

"""Extract column descriptions from source-system PDF data dictionaries.

Reads a PDF data dictionary (PowerSchool or ADP), extracts field descriptions,
matches them to staging YAML column names, and outputs a JSON mapping file.

Output: .claude/scratch/<source>_dictionary.json

Usage:
    uv run scripts/extract_pdf_dictionary.py <pdf_path> <source_system>

    source_system: "powerschool" or "adp"

Design reference:
    docs/superpowers/specs/2026-04-16-data-dictionary-enrichment-design.md
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
