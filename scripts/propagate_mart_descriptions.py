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

import json
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


_PACKAGE_DISPLAY_NAMES: dict[str, str] = {
    "adp": "ADP",
    "amplify": "Amplify",
    "deanslist": "DeansList",
    "edplan": "EdPlan",
    "finalsite": "Finalsite",
    "iready": "iReady",
    "kippadb": "KIPPADB",
    "overgrad": "Overgrad",
    "pearson": "Pearson",
    "powerschool": "PowerSchool",
    "renlearn": "Renaissance",
    "titan": "Titan",
}


def _format_propagated_description(
    staging_desc: str,
    package: str,
    staging_model: str,
    staging_column: str,
) -> str:
    """Format a propagated description with source attribution."""
    display = _PACKAGE_DISPLAY_NAMES.get(package, package)
    return f"{staging_desc} Source: {display} {staging_model}.{staging_column}."


def _enrich_yaml_descriptions(
    doc: dict,
    lineage: dict[str, dict],
    source_mapping: dict[str, dict],
    staging_dict: dict[tuple[str, str], dict],
) -> int:
    """Enrich a YAML doc's column descriptions using lineage.

    Mutates doc in place. Returns the number of columns enriched.
    """
    enriched = 0
    for model in doc.get("models", []) or []:
        for col in model.get("columns", []) or []:
            col_name = col["name"]

            # Skip if description already exists
            existing = _flatten(col.get("description"))
            if existing:
                continue

            # Look up lineage
            lin = lineage.get(col_name)
            if not lin or lin["source_column"] is None:
                continue

            source_table = lin["source_table"]
            source_col = lin["source_column"]

            # Resolve source boundary
            mapping = source_mapping.get(source_table)
            if not mapping:
                continue

            package = mapping["package"]
            staging_model = mapping["table_name"]

            # Look up staging description
            staging = staging_dict.get((staging_model, source_col))
            if not staging or not staging["description"]:
                continue

            col["description"] = _format_propagated_description(
                staging["description"], package, staging_model, source_col
            )
            enriched += 1

            # Propagate PII flag
            if staging["contains_pii"]:
                col.setdefault("config", {}).setdefault("meta", {})["contains_pii"] = (
                    True
                )

    return enriched


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


KIPPTAF_PROJECT = Path("src/dbt/kipptaf")
MANIFEST_PATH = KIPPTAF_PROJECT / "target" / "manifest.json"
COMPILED_DIR = KIPPTAF_PROJECT / "target" / "compiled" / "kipptaf" / "models"

# Source-system package staging YAML directories
STAGING_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/amplify/models/dds/staging/properties"),
    Path("src/dbt/amplify/models/mclass/api/staging/properties"),
    Path("src/dbt/amplify/models/mclass/sftp/staging/properties"),
    Path("src/dbt/deanslist/models/staging/properties"),
    Path("src/dbt/edplan/models/staging/properties"),
    Path("src/dbt/finalsite/models/staging/properties"),
    Path("src/dbt/iready/models/staging/properties"),
    Path("src/dbt/overgrad/models/staging/properties"),
    Path("src/dbt/pearson/models/staging/properties"),
    Path("src/dbt/powerschool/models/sis/staging/properties"),
    Path("src/dbt/renlearn/models/staging/properties"),
    Path("src/dbt/titan/models/staging/properties"),
)

# Skip these directory patterns (staging already enriched, extracts/rpt out of scope)
_SKIP_PATTERNS: tuple[str, ...] = ("staging", "extracts", "rpt_")


def _discover_kipptaf_yaml_dirs() -> list[Path]:
    """Find all properties/ directories under kipptaf models, excluding staging/extracts/rpt."""
    base = KIPPTAF_PROJECT / "models"
    dirs: list[Path] = []
    for props_dir in sorted(base.rglob("properties")):
        if not props_dir.is_dir():
            continue
        rel = str(props_dir.relative_to(base))
        if any(skip in rel for skip in _SKIP_PATTERNS):
            continue
        dirs.append(props_dir)
    return dirs


def _find_compiled_sql(model_name: str) -> Path | None:
    """Find the compiled SQL file for a kipptaf model."""
    for sql_path in COMPILED_DIR.rglob(f"{model_name}.sql"):
        return sql_path
    return None


def main() -> None:
    # Load manifest
    if not MANIFEST_PATH.exists():
        msg = f"Manifest not found at {MANIFEST_PATH}. Run: uv run dbt compile --project-dir {KIPPTAF_PROJECT}"
        raise FileNotFoundError(msg)

    with MANIFEST_PATH.open() as fh:
        manifest = json.load(fh)

    # Build lookup dicts
    staging_dict = _build_staging_description_dict(
        [d for d in STAGING_YAML_DIRS if d.exists()]
    )
    source_mapping = _build_source_mapping(manifest)

    print(f"Loaded {len(staging_dict)} staging descriptions")
    print(f"Loaded {len(source_mapping)} source mappings")

    # Discover target YAML dirs
    target_dirs = _discover_kipptaf_yaml_dirs()
    print(f"Found {len(target_dirs)} target YAML directories")

    total_enriched = 0
    total_files = 0

    for props_dir in target_dirs:
        for yml_path in sorted(props_dir.glob("*.yml")):
            with yml_path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)

            if not doc or not doc.get("models"):
                continue

            # For each model in the YAML, extract lineage from compiled SQL
            file_enriched = 0
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                compiled_path = _find_compiled_sql(model_name)
                if not compiled_path:
                    continue

                sql = compiled_path.read_text(encoding="utf-8")
                lineage = _extract_column_lineage(sql)

                file_enriched += _enrich_yaml_descriptions(
                    doc, lineage, source_mapping, staging_dict
                )

            if file_enriched > 0:
                with yml_path.open("w", encoding="utf-8") as fh:
                    yaml.dump(
                        doc,
                        fh,
                        sort_keys=False,
                        default_flow_style=False,
                        width=88,
                        allow_unicode=True,
                    )
                total_enriched += file_enriched
                total_files += 1

    print(f"Enriched {total_enriched} columns across {total_files} files")


if __name__ == "__main__":
    main()
