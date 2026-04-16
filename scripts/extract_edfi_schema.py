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
