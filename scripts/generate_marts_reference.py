# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///

"""Generate the marts data-model reference page.

Parses foreign-key constraints from the kipptaf marts properties YAML, builds a
directed FK graph, traverses the full snowflake chain per fact table, and emits
a single markdown page with a Mermaid ER diagram and an FK table per fact.

No dbt build or warehouse access required.

Usage:
    uv run scripts/generate_marts_reference.py

Design reference:
    docs/superpowers/specs/2026-06-04-marts-data-models-reference-design.md
"""

from __future__ import annotations

import argparse
import dataclasses
import re
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = REPO_ROOT / "src/dbt/kipptaf/models/marts"
DEFAULT_OUTPUT = REPO_ROOT / "docs/reference/marts-data-models.md"

_REF_RE = re.compile(r"ref\(\s*['\"]([a-z0-9_]+)['\"]\s*\)")


@dataclasses.dataclass(frozen=True)
class FkEdge:
    """A foreign-key edge from a model's column to a target model."""

    source: str
    fk_column: str
    target: str


def _extract_target(to_value: str) -> str | None:
    match = _REF_RE.search(to_value)
    return match.group(1) if match else None


def parse_fk_edges(yaml_path: Path) -> list[FkEdge]:
    """Return one FkEdge per column-level foreign_key constraint in the file."""
    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    edges: list[FkEdge] = []
    for model in doc.get("models", []):
        source = model["name"]
        for column in model.get("columns", []):
            for constraint in column.get("constraints", []):
                if constraint.get("type") != "foreign_key":
                    continue
                target = _extract_target(str(constraint.get("to", "")))
                if target is not None:
                    edges.append(FkEdge(source, column["name"], target))
    return edges
