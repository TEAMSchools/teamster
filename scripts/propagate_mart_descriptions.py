# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0", "sqlglot>=28.0"]
# ///

"""Propagate staging descriptions into intermediate and mart YAML.

Traces column lineage from compiled SQL using sqlglot, resolves
cross-project source boundaries via the kipptaf manifest, and writes
staging descriptions into downstream YAML properties files.

Prerequisites:
    uv run dbt compile --project-dir src/dbt/kipptaf

Usage:
    uv run scripts/propagate_mart_descriptions.py

Design reference:
    docs/superpowers/specs/2026-04-16-edfi-profiling-and-description-propagation-design.md
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

_WS_RE = re.compile(r"\s+")


def _flatten(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def _build_staging_description_dict(
    yaml_dirs: list[Path],
) -> dict[tuple[str, str], dict]:
    """Build {(model_name, column_name): {description, contains_pii}} from staging YAMLs.

    Skips columns with empty or absent descriptions.
    """
    result: dict[tuple[str, str], dict] = {}
    for directory in yaml_dirs:
        for yml_path in sorted(directory.glob("*.yml")):
            with yml_path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
            if not doc:
                continue
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                for col in model.get("columns", []) or []:
                    desc = _flatten(col.get("description"))
                    if not desc:
                        continue
                    pii = (
                        col.get("config", {}).get("meta", {}).get("contains_pii", False)
                    )
                    result[(model_name, col["name"])] = {
                        "description": desc,
                        "contains_pii": bool(pii),
                    }
    return result


_REGION_PREFIXES: tuple[str, ...] = (
    "kippnewark_",
    "kippcamden_",
    "kippmiami_",
    "kipppaterson_",
)


def _strip_region_prefix(source_name: str) -> str:
    """Strip regional project prefix to get the package name.

    'kippnewark_powerschool' -> 'powerschool'
    'kippadb' -> 'kippadb' (no prefix)
    """
    for prefix in _REGION_PREFIXES:
        if source_name.startswith(prefix):
            return source_name[len(prefix) :]
    return source_name


def _extract_column_lineage(sql: str) -> dict[str, dict]:
    """Extract column lineage from compiled BigQuery SQL.

    Takes compiled SQL (all Jinja resolved) and returns a mapping of output
    column aliases to their source information::

        {
            "birth_date": {
                "source_table": "`teamster-332318`.`kippnewark_powerschool`.`stg_powerschool__students`",
                "source_column": "dob",
            },
            "student_name": {"source_table": "...", "source_column": "lastfirst"},
            "ethnicity_label": {"source_table": "...", "source_column": None},
        }

    For simple renames (``dob AS birth_date``), traces back to the source table
    and column.  For passthroughs (``student_number`` with no alias), traces
    back to the source table.  For computed expressions (CASE, COALESCE, etc.),
    sets ``source_column`` to ``None``.
    """
    stmt = sqlglot.parse(sql, read="bigquery")[0]

    # Collect CTEs: {name: Select node}
    ctes: dict[str, exp.Select] = {}
    with_clause = stmt.find(exp.With)
    if with_clause:
        for cte in with_clause.expressions:
            ctes[cte.alias] = cte.this

    def _resolve_physical_table(select_node: exp.Select) -> str | None:
        """Walk FROM clauses through CTEs until a physical table is found."""
        from_clause = select_node.find(exp.From)
        if from_clause is None:
            return None
        table = from_clause.this
        if not isinstance(table, exp.Table):
            return None
        table_name = table.name
        if table_name in ctes:
            return _resolve_physical_table(ctes[table_name])
        return table.sql(dialect="bigquery")

    def _resolve_select(select_node: exp.Select) -> exp.Select:
        """If select is ``SELECT * FROM cte``, resolve into the CTE's select."""
        if len(select_node.expressions) == 1 and isinstance(
            select_node.expressions[0], exp.Star
        ):
            from_clause = select_node.find(exp.From)
            if from_clause is not None:
                table = from_clause.this
                if isinstance(table, exp.Table) and table.name in ctes:
                    return _resolve_select(ctes[table.name])
        return select_node

    def _is_simple_column(node: exp.Expression) -> bool:
        """Check if a node is a simple column reference (no computation)."""
        return isinstance(node, exp.Column)

    def _trace_column_through_ctes(
        col_name: str, current_select: exp.Select
    ) -> tuple[str | None, str | None]:
        """Trace a column name back through CTEs to find physical table and column.

        Returns (source_table, source_column).
        """
        from_clause = current_select.find(exp.From)
        if from_clause is None:
            return None, col_name

        table = from_clause.this
        if not isinstance(table, exp.Table):
            return None, col_name

        table_name = table.name

        # If FROM references a CTE, look inside that CTE
        if table_name in ctes:
            cte_select = ctes[table_name]

            # If the CTE is SELECT *, recurse into its source
            if len(cte_select.expressions) == 1 and isinstance(
                cte_select.expressions[0], exp.Star
            ):
                return _trace_column_through_ctes(col_name, cte_select)

            # Look for the column in the CTE's expressions
            for cte_expr in cte_select.expressions:
                if isinstance(cte_expr, exp.Alias):
                    alias_name = cte_expr.alias
                    if alias_name == col_name:
                        # Found it — if the inner expression is a simple column,
                        # trace further; otherwise it's computed
                        if _is_simple_column(cte_expr.this):
                            inner_col = cte_expr.this.name
                            return _trace_column_through_ctes(inner_col, cte_select)
                        return _resolve_physical_table(cte_select), None
                elif isinstance(cte_expr, exp.Column):
                    if cte_expr.name == col_name:
                        return _trace_column_through_ctes(col_name, cte_select)

            # Column not found explicitly — might come from a SELECT *
            return _resolve_physical_table(cte_select), col_name

        # Physical table — we've reached the bottom
        physical = table.sql(dialect="bigquery")
        return physical, col_name

    # Resolve the outermost SELECT (handles SELECT * FROM cte)
    resolved = _resolve_select(stmt)
    result: dict[str, dict] = {}

    for expression in resolved.expressions:
        if isinstance(expression, exp.Star):
            # Can't resolve individual columns from a bare star at the leaf
            continue

        if isinstance(expression, exp.Alias):
            alias_name = expression.alias
            inner = expression.this

            if _is_simple_column(inner):
                source_table, source_column = _trace_column_through_ctes(
                    inner.name, resolved
                )
                result[alias_name] = {
                    "source_table": source_table,
                    "source_column": source_column,
                }
            else:
                # Computed expression
                result[alias_name] = {
                    "source_table": _resolve_physical_table(resolved),
                    "source_column": None,
                }

        elif isinstance(expression, exp.Column):
            col_name = expression.name
            source_table, source_column = _trace_column_through_ctes(col_name, resolved)
            result[col_name] = {
                "source_table": source_table,
                "source_column": source_column,
            }

    return result


def _build_source_mapping(manifest: dict) -> dict[str, dict]:
    """Build {relation_name: {source_name, table_name, package}} from manifest sources."""
    result: dict[str, dict] = {}
    for source in manifest.get("sources", {}).values():
        relation = source.get("relation_name", "")
        if not relation:
            continue
        source_name = source["source_name"]
        result[relation] = {
            "source_name": source_name,
            "table_name": source["name"],
            "package": _strip_region_prefix(source_name),
        }
    return result
