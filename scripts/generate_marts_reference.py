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


def _constraint_target(constraint: Mapping[str, object]) -> str | None:
    """Return the target model name from a foreign_key constraint dict.

    Reads the ref-aware ``to:`` field (dbt 1.9+), which all marts use for both
    column-level and model-level foreign_key constraints.  Returns ``None`` when
    the field is absent or does not contain a ``ref('...')`` call.
    """
    raw = constraint.get("to") or ""
    return _extract_target(str(raw))


def parse_fk_edges(yaml_path: Path) -> list[FkEdge]:
    """Return one FkEdge per foreign_key constraint in the file.

    Captures both column-level constraints (``columns[].constraints[].type =
    foreign_key`` with a ``to: ref(...)`` value) and model-level constraints
    (``models[].constraints[].type = foreign_key`` with a ``to: ref(...)`` value
    and a ``columns:`` list) — both via the ref-aware ``to:`` field (dbt 1.9+).
    For model-level constraints, one edge is emitted per column name in the
    constraint's ``columns`` list.

    Column-level edges are emitted first (in column order), followed by
    model-level edges (in constraint order, then column order within each
    constraint).  Non-foreign-key constraints are ignored in both locations.
    """
    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    edges: list[FkEdge] = []
    for model in doc.get("models", []):
        source = model["name"]

        # Column-level FK constraints.
        for column in model.get("columns", []):
            for constraint in column.get("constraints", []):
                if constraint.get("type") != "foreign_key":
                    continue
                target = _constraint_target(constraint)
                if target is not None:
                    edges.append(FkEdge(source, column["name"], target))

        # Model-level FK constraints.
        for constraint in model.get("constraints", []):
            if constraint.get("type") != "foreign_key":
                continue
            target = _constraint_target(constraint)
            if target is None:
                continue
            for fk_col in constraint.get("columns", []):
                edges.append(FkEdge(source, str(fk_col), target))

    return edges


def collect_edges(marts_dir: Path) -> list[FkEdge]:
    """Parse FK edges from every facts/dimensions/bridges properties file."""
    edges: list[FkEdge] = []
    for subdir in ("facts", "dimensions", "bridges"):
        for path in sorted((marts_dir / subdir / "properties").glob("*.yml")):
            edges.extend(parse_fk_edges(path))
    return edges


def collect_fact_names(marts_dir: Path) -> list[str]:
    """Return the sorted list of fct_* model names from facts/properties."""
    names: list[str] = []
    for path in sorted((marts_dir / "facts" / "properties").glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        names.extend(
            model["name"]
            for model in doc.get("models", [])
            if model["name"].startswith("fct_")
        )
    return sorted(names)


def build_adjacency(edges: Iterable[FkEdge]) -> dict[str, list[FkEdge]]:
    """Group edges by source model into an adjacency map."""
    adjacency: dict[str, list[FkEdge]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source].append(edge)
    return adjacency


def snowflake_subgraph(
    adjacency: Mapping[str, list[FkEdge]], root: str
) -> list[FkEdge]:
    """BFS from root, collecting every reachable FK edge (full snowflake chain).

    Each target node is enqueued once; role-qualified parallel edges to the same
    target are all kept. Shared targets (a dim reached via two paths) are visited
    once; the visited set also guards against cycles. The marts design is acyclic
    by convention.
    """
    visited: set[str] = {root}
    queue: deque[str] = deque([root])
    collected: list[FkEdge] = []
    seen: set[tuple[str, str, str]] = set()
    while queue:
        node = queue.popleft()
        for edge in adjacency.get(node, []):
            key = (edge.source, edge.fk_column, edge.target)
            if key not in seen:
                seen.add(key)
                collected.append(edge)
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append(edge.target)
    return collected
