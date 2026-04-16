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


def _extract_alias_map(sql: str) -> dict[str, str]:
    """Extract column alias mappings from compiled SQL.

    Returns {output_alias: source_column} for simple renames like
    ``dob AS birth_date``. Only traces through CTE chains; skips
    computed expressions.
    """
    try:
        stmts = sqlglot.parse(sql, read="bigquery")
    except Exception:
        return {}

    if not stmts or stmts[0] is None:
        return {}

    stmt = stmts[0]

    # Collect CTEs
    ctes: dict[str, exp.Expression] = {}
    for cte in stmt.find_all(exp.CTE):
        ctes[cte.alias] = cte.this

    # Find the outermost select — resolve SELECT * FROM cte
    def _resolve_star(select: exp.Expression) -> exp.Expression:
        if not isinstance(select, exp.Select):
            return select
        exprs = select.expressions
        if len(exprs) == 1 and isinstance(exprs[0], exp.Star):
            from_clause = select.find(exp.From)
            if from_clause:
                table = from_clause.this
                if isinstance(table, exp.Table) and table.name in ctes:
                    return _resolve_star(ctes[table.name])
        return select

    resolved = _resolve_star(stmt)
    if not isinstance(resolved, exp.Select):
        return {}

    result: dict[str, str] = {}
    for expression in resolved.expressions:
        if isinstance(expression, exp.Alias) and isinstance(
            expression.this, exp.Column
        ):
            alias = expression.alias
            source_col = expression.this.name
            if alias != source_col:
                result[alias] = source_col
    return result


def _infer_package_from_model(model_name: str) -> str | None:
    """Infer the source package from a kipptaf model name.

    'base_powerschool__student_enrollments' → 'powerschool'
    'int_deanslist__incidents' → 'deanslist'
    'dim_students' → None (no clear package)
    """
    for prefix in ("base_", "int_", "stg_"):
        if model_name.startswith(prefix):
            remainder = model_name[len(prefix) :]
            package_slug = remainder.split("__", 1)[0]
            return package_slug
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
    """Pre-parsed compiled SQL cache: table references and alias maps."""

    def __init__(self, compiled_dir: Path) -> None:
        self.tables: dict[str, list[str]] = {}
        self.aliases: dict[str, dict[str, str]] = {}

        for sql_path in compiled_dir.rglob("*.sql"):
            model_name = sql_path.stem
            sql = sql_path.read_text(encoding="utf-8")
            self.tables[model_name] = _extract_referenced_tables(sql)
            self.aliases[model_name] = _extract_alias_map(sql)


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
            return (table_name, col_name, _infer_package(table_name))

        # Not staging — check this model's alias map for renames
        upstream_tables = cache.tables.get(table_name)
        if upstream_tables is None:
            continue

        alias_map = cache.aliases.get(table_name, {})
        # If this model renames col_name, follow the alias upstream
        upstream_col = alias_map.get(col_name, col_name)

        result = _resolve_column_to_staging(
            upstream_col, upstream_tables, staging_dict, cache, staging_index, visited
        )
        if result is not None:
            return result

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
                    source_col = alias_map[col_name]
                    resolved = _resolve_column_to_staging(
                        source_col,
                        referenced_tables,
                        staging_dict,
                        cache,
                        staging_index,
                    )

                # Phase 3: package-wide fallback
                if resolved is None:
                    pkg = _infer_package_from_model(model_name)
                    for lookup_col in [col_name, alias_map.get(col_name, "")]:
                        if not lookup_col:
                            continue
                        candidates = staging_index.get(lookup_col, [])
                        for stg_model, stg_col in candidates:
                            stg_pkg = _infer_package(stg_model)
                            if pkg is None or stg_pkg == pkg:
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

            if resolved is None:
                continue

            staging_model, staging_col, package = resolved
            staging = staging_dict[(staging_model, staging_col)]

            # Carry staging description as-is
            col["description"] = staging["description"]
            enriched += 1

            # Structured provenance
            _set_provenance(col, package, staging_model, staging_col)

            # Propagate PII flag
            if staging["contains_pii"]:
                col["config"]["meta"]["contains_pii"] = True

    return enriched


def _infer_package(staging_model: str) -> str:
    """Infer the package name from a staging model name.

    'stg_powerschool__students' → 'powerschool'
    'stg_adp_workforce_now__workers' → 'adp'
    """
    if not staging_model.startswith("stg_"):
        return staging_model
    # Strip 'stg_' prefix and take the first segment before '__'
    remainder = staging_model[4:]
    parts = remainder.split("__", 1)
    slug = parts[0] if parts else remainder
    # Map known multi-word slugs to package names
    _SLUG_MAP = {
        "adp_workforce_now": "adp",
        "adp_workforce_manager": "adp",
        "adp_payroll": "adp",
    }
    if slug in _SLUG_MAP:
        return _SLUG_MAP[slug]
    return slug


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

    with MANIFEST_PATH.open() as fh:
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
