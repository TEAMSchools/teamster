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


def _extract_table_name(relation: str) -> str:
    """Extract the bare table name from a fully qualified BigQuery relation.

    '`teamster-332318`.`zz_cbini_kipptaf_powerschool`.`stg_powerschool__students`'
    → 'stg_powerschool__students'
    """
    parts = relation.replace("`", "").split(".")
    return parts[-1] if parts else relation


def _build_compiled_sql_cache(
    compiled_dir: Path,
) -> tuple[dict[str, Path], dict[str, list[str]]]:
    """Build caches of compiled SQL paths and their referenced tables.

    Returns (path_cache, tables_cache) where:
    - path_cache: {model_name: Path}
    - tables_cache: {model_name: [referenced_table_names]}
    """
    path_cache: dict[str, Path] = {}
    for sql_path in compiled_dir.rglob("*.sql"):
        path_cache[sql_path.stem] = sql_path

    tables_cache: dict[str, list[str]] = {}
    for model_name, sql_path in path_cache.items():
        sql = sql_path.read_text(encoding="utf-8")
        tables_cache[model_name] = _extract_referenced_tables(sql)

    return path_cache, tables_cache


def _resolve_column_to_staging(
    col_name: str,
    referenced_tables: list[str],
    staging_dict: dict[tuple[str, str], dict],
    tables_cache: dict[str, list[str]],
    visited: set[str] | None = None,
) -> tuple[str, str, str] | None:
    """Resolve a column name to a staging model by walking referenced tables.

    Assumes union_relations and deduplicate are column-passthrough — their
    output columns match their inputs. Recursively follows intermediate
    models until a staging description is found.

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

        # Direct match in staging dict
        if (table_name, col_name) in staging_dict:
            return (table_name, col_name, _infer_package(table_name))

        # Not staging — try to follow through this table's pre-parsed refs
        upstream_tables = tables_cache.get(table_name)
        if upstream_tables is None:
            continue

        result = _resolve_column_to_staging(
            col_name, upstream_tables, staging_dict, tables_cache, visited
        )
        if result is not None:
            return result

    return None


def _enrich_yaml_descriptions(
    doc: dict,
    referenced_tables: list[str],
    source_mapping: dict[str, dict],
    staging_dict: dict[tuple[str, str], dict],
    tables_cache: dict[str, list[str]] | None = None,
) -> int:
    """Enrich a YAML doc's column descriptions from staging sources.

    Overwrites existing descriptions when a staging source is traceable.
    Assumes union_relations and deduplicate are column-passthrough.
    Mutates doc in place. Returns the number of columns enriched.
    """
    enriched = 0
    for model in doc.get("models", []) or []:
        for col in model.get("columns", []) or []:
            col_name = col["name"]

            if tables_cache is not None:
                resolved = _resolve_column_to_staging(
                    col_name, referenced_tables, staging_dict, tables_cache
                )
            else:
                # Non-recursive path (for tests with simple fixtures)
                resolved = None
                for table in referenced_tables:
                    table_name = _extract_table_name(table)
                    mapping = source_mapping.get(table)
                    if mapping and (mapping["table_name"], col_name) in staging_dict:
                        resolved = (
                            mapping["table_name"],
                            col_name,
                            mapping["package"],
                        )
                        break
                    if (table_name, col_name) in staging_dict:
                        resolved = (table_name, col_name, _infer_package(table_name))
                        break

            if resolved is None:
                continue

            staging_model, staging_col, package = resolved
            staging = staging_dict[(staging_model, staging_col)]

            col["description"] = _format_propagated_description(
                staging["description"], package, staging_model, staging_col
            )
            enriched += 1

            # Propagate PII flag
            if staging["contains_pii"]:
                col.setdefault("config", {}).setdefault("meta", {})["contains_pii"] = (
                    True
                )

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

    # Build compiled SQL cache
    path_cache, tables_cache = _build_compiled_sql_cache(COMPILED_DIR)
    print(f"Cached {len(path_cache)} compiled SQL files")

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

            # For each model in the YAML, extract referenced tables from compiled SQL
            file_enriched = 0
            for model in doc.get("models", []) or []:
                model_name = model["name"]
                model_tables = tables_cache.get(model_name)
                if model_tables is None:
                    continue

                file_enriched += _enrich_yaml_descriptions(
                    doc,
                    model_tables,
                    source_mapping,
                    staging_dict,
                    tables_cache,
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
