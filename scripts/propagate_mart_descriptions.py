# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0", "ruamel.yaml>=0.18", "sqlglot>=28.0"]
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


def _get_ryaml():
    """Lazy-load ruamel.yaml for round-trip YAML editing.

    ruamel.yaml is declared in the PEP 723 script dependencies and
    available when running via ``uv run``.  Tests that import this
    module via ``importlib`` don't need it — they never call ``main()``.
    """
    # trunk-ignore-begin(pyright/reportMissingImports): PEP 723 dep
    from ruamel.yaml import YAML

    # trunk-ignore-end(pyright/reportMissingImports)

    ry = YAML()
    ry.preserve_quotes = True
    ry.width = 88
    ry.indent(mapping=2, sequence=4, offset=2)
    return ry


_WS_RE = re.compile(r"\s+")


def _flatten(text: str | None) -> str:
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


def _infer_column_role(description: str) -> str:
    """Infer primary_key or foreign_key from a column description.

    PowerSchool data dictionary descriptions explicitly label columns as
    'Primary key' or 'Foreign key'.
    """
    lower = description.lower()
    if "primary key" in lower:
        return "primary_key"
    if "foreign key" in lower:
        return "foreign_key"
    return ""


def _build_staging_description_dict(
    yaml_dirs: list[Path],
) -> dict[tuple[str, str], dict]:
    """Build {(model_name, column_name): {description, contains_pii, column_role}}.

    Skips columns with empty or absent descriptions.
    Infers column_role (primary_key/foreign_key) from description text.
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
                        "column_role": _infer_column_role(desc),
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


def _extract_referenced_tables(sql: str) -> list[str]:
    """Extract bare table names from all physical table references in compiled SQL.

    Parses the SQL with sqlglot and finds all Table nodes, returning
    their unqualified names. Assumes union_relations and deduplicate
    are column-passthrough — their output columns match their inputs.
    """
    try:
        stmts = sqlglot.parse(sql, read="bigquery")
    except Exception:
        return []

    tables: list[str] = []
    for stmt in stmts:
        if stmt is None:
            continue
        for table in stmt.find_all(exp.Table):
            name = table.name
            if name:
                tables.append(name)
    return tables


def _resolve_star(
    select: exp.Expression, ctes: dict[str, exp.Expression]
) -> exp.Expression:
    """If select is ``SELECT * FROM cte``, resolve into the CTE's select."""
    if not isinstance(select, exp.Select):
        return select
    exprs = select.expressions
    if len(exprs) == 1 and isinstance(exprs[0], exp.Star):
        from_clause = select.find(exp.From)
        if from_clause:
            table = from_clause.this
            if isinstance(table, exp.Table) and table.name in ctes:
                return _resolve_star(ctes[table.name], ctes)
    return select


def _resolve_table_aliases(
    select: exp.Expression,
) -> dict[str, str]:
    """Map table aliases to their actual table names.

    ``FROM stg_powerschool__students AS se`` → ``{'se': 'stg_powerschool__students'}``
    """
    result: dict[str, str] = {}
    for table in select.find_all(exp.Table):
        if table.alias:
            result[table.alias] = table.name
        else:
            result[table.name] = table.name
    return result


def _extract_alias_map(sql: str) -> dict[str, tuple[str, str]]:
    """Extract column alias mappings from compiled SQL.

    Returns {output_alias: (source_table, source_column)} for simple
    renames like ``se.dob AS birth_date``. Tracks which table/CTE the
    source column comes from to avoid cross-contamination. Skips
    computed expressions.
    """
    try:
        stmts = sqlglot.parse(sql, read="bigquery")
    except Exception:
        return {}

    if not stmts or stmts[0] is None:
        return {}

    stmt = stmts[0]

    ctes: dict[str, exp.Expression] = {}
    for cte in stmt.find_all(exp.CTE):
        ctes[cte.alias] = cte.this

    resolved = _resolve_star(stmt, ctes)
    if not isinstance(resolved, exp.Select):
        return {}

    table_aliases = _resolve_table_aliases(resolved)

    def _unwrap_column(node: exp.Expression) -> exp.Column | None:
        """Unwrap a Column from transparent wrappers (CAST, etc.)."""
        if isinstance(node, exp.Column):
            return node
        if isinstance(node, exp.Cast):
            return _unwrap_column(node.this)
        return None

    result: dict[str, tuple[str, str]] = {}
    for expression in resolved.expressions:
        if not isinstance(expression, exp.Alias):
            continue
        alias = expression.alias
        col = _unwrap_column(expression.this)
        if col is None:
            continue
        source_col = col.name
        table_qual = col.table or ""
        source_table = table_aliases.get(table_qual, table_qual)
        if alias != source_col:
            result[alias] = (source_table, source_col)
    return result


_STAGING_SLUG_MAP: dict[str, str] = {
    "adp_workforce_now": "adp",
    "adp_workforce_manager": "adp",
    "adp_payroll": "adp",
}


def _infer_package(model_name: str) -> str | None:
    """Infer the source package from a model name.

    'stg_powerschool__students' → 'powerschool'
    'base_powerschool__student_enrollments' → 'powerschool'
    'int_adp_workforce_now__workers' → 'adp'
    'dim_students' → None (no clear package)
    """
    for prefix in ("base_", "int_", "stg_"):
        if model_name.startswith(prefix):
            remainder = model_name[len(prefix) :]
            slug = remainder.split("__", 1)[0]
            return _STAGING_SLUG_MAP.get(slug, slug)
    return None


def _build_staging_index(
    staging_dict: dict[tuple[str, str], dict],
) -> dict[str, list[tuple[str, str]]]:
    """Build {column_name: [(staging_model, column_name), ...]} index.

    Used for package-wide fallback searches.
    """
    index: dict[str, list[tuple[str, str]]] = {}
    for model_col in staging_dict:
        col = model_col[1]
        index.setdefault(col, []).append(model_col)
    return index


def _summarize_expression(node: exp.Expression) -> str:
    """Generate a plain-text description of a SQL expression.

    Returns a concise summary suitable for a dbt column description.
    """
    # CAST → transparent, handled by alias map
    if isinstance(node, exp.Cast):
        return ""

    # CASE → categorical mapping
    if isinstance(node, exp.Case):
        source_cols = sorted({c.name for c in node.find_all(exp.Column)})
        if source_cols:
            return f"Categorical mapping of {', '.join(source_cols)}."
        return "Categorical mapping."

    # IS NULL / IS NOT NULL boolean check
    if isinstance(node, exp.Not) and node.find(exp.Is):
        inner_cols = [c.name for c in node.find_all(exp.Column)]
        if inner_cols:
            return f"True when {inner_cols[0]} is not null."
        return "Null check."

    if isinstance(node, exp.Is):
        inner_cols = [c.name for c in node.find_all(exp.Column)]
        if inner_cols:
            return f"True when {inner_cols[0]} is null."
        return "Null check."

    # Window function
    if isinstance(node, exp.Window):
        func = node.this
        func_name = type(func).__name__.upper()
        inner_cols = [c.name for c in func.find_all(exp.Column)]
        col_str = ", ".join(inner_cols) if inner_cols else "value"

        parts: list[str] = [f"{func_name} of {col_str}"]

        partition_by = node.args.get("partition_by")
        if partition_by:
            part_cols = [c.name for c in partition_by if isinstance(c, exp.Column)]
            if part_cols:
                parts.append(f"partitioned by {', '.join(part_cols)}")

        order = node.args.get("order")
        if order:
            order_cols = [c.name for c in order.find_all(exp.Column)]
            if order_cols:
                parts.append(f"ordered by {', '.join(order_cols)}")

        return " ".join(parts) + "."

    # COALESCE
    if isinstance(node, exp.Coalesce):
        inner_cols = [c.name for c in node.find_all(exp.Column)]
        if inner_cols:
            return f"First non-null of {', '.join(inner_cols)}."
        return "Coalesce expression."

    # IF
    if isinstance(node, exp.If):
        source_cols = sorted({c.name for c in node.find_all(exp.Column)})
        if source_cols:
            return f"Conditional on {', '.join(source_cols)}."
        return "Conditional expression."

    # Hash / MD5 / surrogate key
    if isinstance(node, exp.Func) and node.sql_name() in ("MD5", "TO_HEX", "SHA256"):
        return "Surrogate key."
    # Nested TO_HEX(MD5(...))
    if isinstance(node, exp.Anonymous) and node.name.upper() == "TO_HEX":
        return "Surrogate key."
    hex_funcs = list(node.find_all(exp.Anonymous))
    if any(f.name.upper() == "TO_HEX" for f in hex_funcs):
        return "Surrogate key."

    # Fallback: list source columns
    source_cols = sorted({c.name for c in node.find_all(exp.Column)})
    if source_cols:
        return f"Derived from {', '.join(source_cols)}."
    return "Computed expression."


def _extract_expression_map(sql: str) -> dict[str, tuple[str, list[str]]]:
    """Extract computed column expression summaries from compiled SQL.

    Returns {output_alias: (plain_text_summary, [source_column_names])}
    for non-simple columns (CASE, window functions, etc.). Simple column
    references, passthroughs, and CASTs are excluded (handled by alias map).
    """
    try:
        stmts = sqlglot.parse(sql, read="bigquery")
    except Exception:
        return {}

    if not stmts or stmts[0] is None:
        return {}

    stmt = stmts[0]
    ctes: dict[str, exp.Expression] = {}
    for cte in stmt.find_all(exp.CTE):
        ctes[cte.alias] = cte.this

    resolved = _resolve_star(stmt, ctes)
    if not isinstance(resolved, exp.Select):
        return {}

    result: dict[str, tuple[str, list[str]]] = {}
    for expression in resolved.expressions:
        if isinstance(expression, exp.Alias):
            inner = expression.this
            # Skip simple columns and CASTs (handled by alias map)
            if isinstance(inner, exp.Column):
                continue
            if isinstance(inner, exp.Cast):
                continue
            summary = _summarize_expression(inner)
            if not summary:
                continue
            source_cols = sorted({c.name for c in inner.find_all(exp.Column)})
            result[expression.alias] = (summary, source_cols)

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


def _set_provenance(
    col: dict,
    package: str,
    staging_model: str,
    staging_column: str,
) -> None:
    """Set structured provenance meta attributes on a column."""
    display = _PACKAGE_DISPLAY_NAMES.get(package, package)
    meta = col.setdefault("config", {}).setdefault("meta", {})
    meta["source_system"] = display
    meta["source_model"] = staging_model
    meta["source_column"] = staging_column


def _extract_table_name(relation: str) -> str:
    """Extract the bare table name from a fully qualified BigQuery relation.

    '`teamster-332318`.`zz_cbini_kipptaf_powerschool`.`stg_powerschool__students`'
    → 'stg_powerschool__students'
    """
    parts = relation.replace("`", "").split(".")
    return parts[-1] if parts else relation


class _CompiledCache:
    """Pre-parsed compiled SQL cache: table references, alias maps, and expression summaries."""

    def __init__(self, compiled_dir: Path) -> None:
        self.tables: dict[str, list[str]] = {}
        self.aliases: dict[str, dict[str, tuple[str, str]]] = {}
        self.expressions: dict[str, dict[str, tuple[str, list[str]]]] = {}
        self.parse_failures: list[str] = []

        for sql_path in compiled_dir.rglob("*.sql"):
            model_name = sql_path.stem
            sql = sql_path.read_text(encoding="utf-8")
            tables = _extract_referenced_tables(sql)
            aliases = _extract_alias_map(sql)
            expressions = _extract_expression_map(sql)
            if not tables and not aliases and not expressions:
                self.parse_failures.append(model_name)
            self.tables[model_name] = tables
            self.aliases[model_name] = aliases
            self.expressions[model_name] = expressions


def _resolve_column_to_staging(
    col_name: str,
    referenced_tables: list[str],
    staging_dict: dict[tuple[str, str], dict],
    cache: _CompiledCache,
    staging_index: dict[str, list[tuple[str, str]]],
    visited: set[str] | None = None,
) -> tuple[str, str, str] | None:
    """Resolve a column name to a staging model by walking referenced tables.

    At each intermediate model, checks the alias map to follow renames
    (e.g., ``dob AS birth_date`` in model A means when tracing
    ``birth_date`` through A, we continue looking for ``dob`` upstream).

    Returns (staging_model, staging_column, package) or None.
    """
    if visited is None:
        visited = set()

    for table in referenced_tables:
        table_name = _extract_table_name(table)

        # Prevent infinite loops
        trace_key = f"{table_name}.{col_name}"
        if trace_key in visited:
            continue
        visited.add(trace_key)

        # Direct passthrough match in staging
        if (table_name, col_name) in staging_dict:
            return (table_name, col_name, _infer_package(table_name) or table_name)

        # Not staging — check this model's alias map for renames
        upstream_tables = cache.tables.get(table_name)
        if upstream_tables is None:
            continue

        alias_map = cache.aliases.get(table_name, {})
        alias_entry = alias_map.get(col_name)

        if alias_entry is not None:
            # Column is renamed — follow into the specific source table
            alias_table, alias_col = alias_entry
            if alias_table:
                # Scoped: only look in the table the alias came from
                result = _resolve_column_to_staging(
                    alias_col,
                    [alias_table],
                    staging_dict,
                    cache,
                    staging_index,
                    visited,
                )
            else:
                # No table qualifier — search all upstream tables
                result = _resolve_column_to_staging(
                    alias_col,
                    upstream_tables,
                    staging_dict,
                    cache,
                    staging_index,
                    visited,
                )
        else:
            # Column passes through unchanged
            result = _resolve_column_to_staging(
                col_name,
                upstream_tables,
                staging_dict,
                cache,
                staging_index,
                visited,
            )
        if result is not None:
            return result

    # Staging index fallback — the column name exists in staging but the
    # recursive walk couldn't reach it (cross-project boundary). Prefer
    # packages seen during the walk.
    candidates = staging_index.get(col_name, [])
    if candidates:
        walked_pkgs = {
            _infer_package(_extract_table_name(t)) for t in referenced_tables
        }
        walked_pkgs.discard(None)
        for stg_model, stg_col in candidates:
            stg_pkg = _infer_package(stg_model)
            if stg_pkg and stg_pkg in walked_pkgs:
                return (stg_model, stg_col, stg_pkg)

    return None


def _enrich_yaml_descriptions(
    doc: dict,
    model_name: str,
    source_mapping: dict[str, dict],
    staging_dict: dict[tuple[str, str], dict],
    cache: _CompiledCache | None = None,
    staging_index: dict[str, list[tuple[str, str]]] | None = None,
) -> int:
    """Enrich a YAML doc's column descriptions from staging sources.

    Three-phase resolution per column:
    1. Passthrough — column name matches a staging column in referenced tables
    2. Alias trace — column is an alias for a staging column (e.g., dob AS birth_date)
    3. Package fallback — search all staging in the inferred package

    Overwrites existing descriptions when a staging source is traceable.
    Mutates doc in place. Returns the number of columns enriched.
    """
    referenced_tables = cache.tables.get(model_name, []) if cache else []
    alias_map = cache.aliases.get(model_name, {}) if cache else {}

    enriched = 0
    for model in doc.get("models", []) or []:
        for col in model.get("columns", []) or []:
            col_name = col["name"]
            resolved = None

            if cache is not None and staging_index is not None:
                # Phase 1: passthrough match via recursive table walk
                resolved = _resolve_column_to_staging(
                    col_name,
                    referenced_tables,
                    staging_dict,
                    cache,
                    staging_index,
                )

                # Phase 2: alias trace — check if col_name is an alias
                if resolved is None and col_name in alias_map:
                    alias_table, alias_col = alias_map[col_name]
                    if alias_table:
                        resolved = _resolve_column_to_staging(
                            alias_col,
                            [alias_table],
                            staging_dict,
                            cache,
                            staging_index,
                        )
                    else:
                        resolved = _resolve_column_to_staging(
                            alias_col,
                            referenced_tables,
                            staging_dict,
                            cache,
                            staging_index,
                        )

                # Phase 3: package-wide fallback
                if resolved is None:
                    # Infer preferred packages from the reference chain
                    # (scan 2 levels deep to find source packages)
                    ref_pkgs: set[str] = set()
                    for t in referenced_tables:
                        tn = _extract_table_name(t)
                        p = _infer_package(tn)
                        if p:
                            ref_pkgs.add(p)
                        for t2 in cache.tables.get(tn, []):
                            p2 = _infer_package(_extract_table_name(t2))
                            if p2:
                                ref_pkgs.add(p2)
                    pkg = _infer_package(model_name)

                    alias_entry = alias_map.get(col_name)
                    alias_col_name = alias_entry[1] if alias_entry else ""
                    for lookup_col in [col_name, alias_col_name]:
                        if not lookup_col:
                            continue
                        candidates = staging_index.get(lookup_col, [])
                        # Prefer candidates from the model's package or
                        # its reference chain's packages
                        for stg_model, stg_col in candidates:
                            stg_pkg = _infer_package(stg_model)
                            if pkg and stg_pkg == pkg:
                                resolved = (stg_model, stg_col, stg_pkg)
                                break
                            if stg_pkg in ref_pkgs:
                                resolved = (stg_model, stg_col, stg_pkg)
                                break
                        if resolved:
                            break
            else:
                # Non-recursive path (for tests): use source_mapping keys
                for _relation, mapping in source_mapping.items():
                    if (mapping["table_name"], col_name) in staging_dict:
                        resolved = (
                            mapping["table_name"],
                            col_name,
                            mapping["package"],
                        )
                        break

            if resolved is not None:
                staging_model, staging_col, package = resolved
                staging = staging_dict[(staging_model, staging_col)]

                # Carry staging description as-is
                col["description"] = staging["description"]
                enriched += 1

                # Structured provenance
                _set_provenance(
                    col, package or staging_model, staging_model, staging_col
                )

                # Propagate PII flag and column role
                if staging["contains_pii"]:
                    col["config"]["meta"]["contains_pii"] = True
                if staging.get("column_role"):
                    col["config"]["meta"]["column_role"] = staging["column_role"]
                continue

            # Phase 4: computed column description from SQL expression
            if cache is not None and staging_index is not None:
                expr_map = cache.expressions.get(model_name, {})
                expr_entry = expr_map.get(col_name)
                if expr_entry:
                    summary, source_cols = expr_entry

                    # Try to find upstream description for source columns
                    upstream_desc = ""
                    for src_col in source_cols:
                        upstream = _resolve_column_to_staging(
                            src_col,
                            referenced_tables,
                            staging_dict,
                            cache,
                            staging_index,
                        )
                        if upstream:
                            stg = staging_dict[(upstream[0], upstream[1])]
                            upstream_desc = stg["description"]
                            break

                    if upstream_desc:
                        col["description"] = f"{upstream_desc} {summary}"
                    else:
                        col["description"] = summary
                    enriched += 1
                    continue

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


def main() -> None:
    ryaml = _get_ryaml()

    # Load manifest
    if not MANIFEST_PATH.exists():
        msg = f"Manifest not found at {MANIFEST_PATH}. Run: uv run dbt compile --project-dir {KIPPTAF_PROJECT}"
        raise FileNotFoundError(msg)

    with MANIFEST_PATH.open(encoding="utf-8") as fh:
        manifest = json.load(fh)

    # Build lookup dicts
    staging_dict = _build_staging_description_dict(
        [d for d in STAGING_YAML_DIRS if d.exists()]
    )
    source_mapping = _build_source_mapping(manifest)

    print(f"Loaded {len(staging_dict)} staging descriptions")
    print(f"Loaded {len(source_mapping)} source mappings")

    # Build caches
    cache = _CompiledCache(COMPILED_DIR)
    staging_index = _build_staging_index(staging_dict)
    print(
        f"Cached {len(cache.tables)} compiled SQL files, {len(cache.aliases)} alias maps"
    )
    if cache.parse_failures:
        print(
            f"Warning: {len(cache.parse_failures)} models returned no parsed data: "
            f"{', '.join(cache.parse_failures[:10])}"
            f"{'...' if len(cache.parse_failures) > 10 else ''}"
        )

    # Discover target YAML dirs
    target_dirs = _discover_kipptaf_yaml_dirs()
    print(f"Found {len(target_dirs)} target YAML directories")

    total_enriched = 0
    total_files = 0

    for props_dir in target_dirs:
        for yml_path in sorted(props_dir.glob("*.yml")):
            with yml_path.open(encoding="utf-8") as fh:
                doc = ryaml.load(fh)

            if not doc or not doc.get("models"):
                continue

            file_enriched = 0
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                if model_name not in cache.tables:
                    continue

                file_enriched += _enrich_yaml_descriptions(
                    doc,
                    model_name,
                    source_mapping,
                    staging_dict,
                    cache,
                    staging_index,
                )

            if file_enriched > 0:
                with yml_path.open("w", encoding="utf-8") as fh:
                    ryaml.dump(doc, fh)
                total_enriched += file_enriched
                total_files += 1

    print(f"Enriched {total_enriched} columns across {total_files} files")


if __name__ == "__main__":
    main()
