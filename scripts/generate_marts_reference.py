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
import sys
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = REPO_ROOT / "src/dbt/kipptaf/models/marts"
DEFAULT_OUTPUT = REPO_ROOT / "docs/reference/marts-data-models.md"

# Conformed dimensions: shared across many facts (the time / place / term
# backbone). Omitted from the diagrams to reduce clutter — they still appear in
# each fact's FK table.
CONFORMED_DIMS = frozenset({"dim_dates", "dim_locations", "dim_regions", "dim_terms"})

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
    raw = constraint.get("to", "")
    return _extract_target(str(raw))


def _warn_if_legacy_expression(constraint: Mapping[str, object], source: str) -> None:
    """Warn when a foreign_key constraint uses the legacy ``expression:`` form.

    The generator reads only the ref-aware ``to:`` field, so a constraint written
    with the legacy free-text ``expression: "ref('...')"`` form (instead of
    ``to: ref('...')``) is silently skipped — dropping the FK from the diagram.
    Surface it at generation time so the regression is caught, not lost.
    """
    expression = constraint.get("expression")
    if expression is not None:
        print(
            f"WARNING: {source}: foreign_key constraint uses legacy "
            f"'expression: {expression!r}' instead of 'to: ref(...)' — FK "
            "skipped. Migrate it to the to: form.",
            file=sys.stderr,
        )


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

    For table-materialized models, column-level ``relationships`` data tests
    provide FK edges for columns that lack a ``constraints: foreign_key`` entry.
    """
    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    edges: list[FkEdge] = []
    for model in doc.get("models", []):
        source = model["name"]
        constrained: set[str] = set()

        # Column-level FK constraints.
        for column in model.get("columns", []):
            for constraint in column.get("constraints", []):
                if constraint.get("type") != "foreign_key":
                    continue
                target = _constraint_target(constraint)
                if target is None:
                    _warn_if_legacy_expression(constraint, source)
                    continue
                edges.append(FkEdge(source, column["name"], target))
                constrained.add(column["name"])

        # Model-level FK constraints.
        for constraint in model.get("constraints", []):
            if constraint.get("type") != "foreign_key":
                continue
            target = _constraint_target(constraint)
            if target is None:
                _warn_if_legacy_expression(constraint, source)
                continue
            for fk_col in constraint.get("columns", []):
                edges.append(FkEdge(source, str(fk_col), target))
                constrained.add(str(fk_col))

        # Relationships-test fallback for table-materialized models.
        if (model.get("config") or {}).get("materialized") != "table":
            continue
        for column in model.get("columns", []):
            if column["name"] in constrained:
                continue
            for test in column.get("data_tests") or []:
                if not isinstance(test, Mapping):
                    continue
                params = test.get("relationships")
                if not isinstance(params, Mapping):
                    continue
                params = params.get("arguments", params)
                target = _extract_target(str(params.get("to", "")))
                if target is not None:
                    edges.append(FkEdge(source, column["name"], target))

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
    adjacency: Mapping[str, list[FkEdge]],
    root: str,
    exclude: frozenset[str] = frozenset(),
) -> list[FkEdge]:
    """BFS from root, collecting every reachable FK edge (full snowflake chain).

    Each target node is enqueued once; role-qualified parallel edges to the same
    target are all kept. Shared targets (a dim reached via two paths) are visited
    once; the visited set also guards against cycles. The marts design is acyclic
    by convention.

    Targets in ``exclude`` (conformed dimensions) are dropped entirely: their
    edges are skipped and the traversal does not chain through them.
    """
    visited: set[str] = {root}
    queue: deque[str] = deque([root])
    collected: list[FkEdge] = []
    seen: set[tuple[str, str, str]] = set()
    while queue:
        node = queue.popleft()
        for edge in adjacency.get(node, []):
            if edge.target in exclude:
                continue
            key = (edge.source, edge.fk_column, edge.target)
            if key not in seen:
                seen.add(key)
                collected.append(edge)
            if edge.target not in visited:
                visited.add(edge.target)
                queue.append(edge.target)
    return collected


BANNER = (
    "<!-- generated by scripts/generate_marts_reference.py; do not edit by hand -->"
)

INTRO = """\
The `kipptaf` marts are dimensional models (fact and dimension tables) consumed
by Cube and Tableau. They follow a **strict-chain snowflake** design: each fact
table holds foreign keys to its _direct_ parents only, and deeper context is
reached by chaining one dimension to its parent dimension
(`fct_student_attendance_daily` → `dim_student_enrollments` → `dim_students`).

Each section below shows one fact table and the snowflake chain reachable from
it, followed by the fact's own foreign keys. **Conformed dimensions —
`dim_dates`, `dim_terms`, `dim_locations`, and `dim_regions` — are omitted from
the diagrams** to reduce clutter (they are referenced throughout and would
otherwise appear in nearly every graph); each fact's foreign-key table below its
diagram still lists them.

> **Reading the diagrams.** Boxes are tables (`fct_*` facts, `dim_*`
> dimensions). An edge `child }o--|| parent : "fk_column"` reads "many rows of
> _child_ reference one row of _parent_ via _fk_column_." A fact with several
> edges to the same dimension (e.g. `submitter_staff_key` and
> `assignee_staff_key` both to `dim_staff`) is showing role-qualified foreign
> keys.
"""


def render_erdiagram(edges: list[FkEdge], root: str) -> str:
    lines = ["```mermaid", "erDiagram"]
    if edges:
        for edge in edges:
            lines.append(f'  {edge.source} }}o--|| {edge.target} : "{edge.fk_column}"')
    else:
        lines.append(f"  {root} {{")
        lines.append("  }")
    lines.append("```")
    return "\n".join(lines)


def render_fk_table(adjacency: Mapping[str, list[FkEdge]], root: str) -> str:
    direct = sorted(adjacency.get(root, []), key=lambda e: e.fk_column)
    lines = ["| FK column | References |", "| --- | --- |"]
    lines.extend(f"| `{edge.fk_column}` | `{edge.target}` |" for edge in direct)
    return "\n".join(lines)


def render_fact_section(adjacency: Mapping[str, list[FkEdge]], fact: str) -> str:
    sub = snowflake_subgraph(adjacency, fact, exclude=CONFORMED_DIMS)
    return "\n".join(
        [
            f"## {fact}",
            "",
            render_erdiagram(sub, fact),
            "",
            "### Foreign keys",
            "",
            render_fk_table(adjacency, fact),
        ]
    )


def render_page(adjacency: Mapping[str, list[FkEdge]], facts: list[str]) -> str:
    sections = [render_fact_section(adjacency, fact) for fact in facts]
    body = "\n\n".join(["# Marts data models", BANNER, INTRO.rstrip(), *sections])
    return body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marts-dir", type=Path, default=MARTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    edges = collect_edges(args.marts_dir)
    adjacency = build_adjacency(edges)
    facts = collect_fact_names(args.marts_dir)
    page = render_page(adjacency, facts)
    args.output.write_text(page, encoding="utf-8")
    print(f"wrote {len(facts)} fact sections to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
