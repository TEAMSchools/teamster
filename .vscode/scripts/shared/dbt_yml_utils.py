from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from google.cloud import bigquery

# ---------------------------------------------------------------------------
# Jinja stripping
# ---------------------------------------------------------------------------

_JINJA_PATTERNS = [
    (re.compile(r"\{#-?[\s\S]*?-?#\}"), ""),  # comments
    (re.compile(r"\{\{[\s\S]*?\}\}"), "__JINJA__"),  # expressions
    (re.compile(r"\{%[\s\S]*?%\}"), ""),  # blocks
    (re.compile(r"--[^\n]*"), ""),  # SQL line comments
    (re.compile(r"/\*[\s\S]*?\*/"), ""),  # SQL block comments
]


def strip_jinja(sql: str) -> str:
    """Remove Jinja templating and SQL comments from SQL text."""
    for pattern, replacement in _JINJA_PATTERNS:
        sql = pattern.sub(replacement, sql)
    return sql


# ---------------------------------------------------------------------------
# SELECT parsing
# ---------------------------------------------------------------------------


def find_first_select(sql: str) -> str:
    """Return the column body (between SELECT and FROM) of the first top-level SELECT.

    Top-level means depth 0 (not inside parentheses). CTE body SELECTs are at
    depth > 0, so they are naturally skipped. For UNION ALL the first SELECT is
    returned. Raises ValueError if no suitable SELECT or FROM is found.
    """
    text = sql
    n = len(text)

    # Find first top-level SELECT keyword
    select_start = None
    depth = 0
    i = 0
    while i < n:
        ch = text[i]
        if ch == "(":
            depth += 1
            i += 1
        elif ch == ")":
            depth -= 1
            i += 1
        elif depth == 0 and text[i : i + 6].upper() == "SELECT":
            # Make sure it's a word boundary (not e.g. SELECTS)
            after = text[i + 6] if i + 6 < n else " "
            if not after.isalnum() and after != "_":
                select_start = i + 6
                break
            else:
                i += 1
        else:
            i += 1

    if select_start is None:
        raise ValueError("No top-level SELECT found in SQL")

    # Strip optional DISTINCT
    body_start = select_start
    rest = text[body_start:].lstrip()
    if rest[:8].upper() == "DISTINCT":
        after_distinct = rest[8] if len(rest) > 8 else " "
        if not after_distinct.isalnum() and after_distinct != "_":
            stripped_offset = len(text[body_start:]) - len(rest)
            body_start += stripped_offset + 8

    # Find the matching top-level FROM
    depth = 0
    j = body_start
    from_pos = None
    while j < n:
        ch = text[j]
        if ch == "(":
            depth += 1
            j += 1
        elif ch == ")":
            depth -= 1
            j += 1
        elif depth == 0 and text[j : j + 4].upper() == "FROM":
            after = text[j + 4] if j + 4 < n else " "
            if not after.isalnum() and after != "_":
                from_pos = j
                break
            else:
                j += 1
        else:
            j += 1

    if from_pos is None:
        raise ValueError("No top-level FROM found after SELECT")

    return text[body_start:from_pos]


def _extract_column_name(expr: str) -> str | None:
    """Extract column name or alias from a single SELECT expression."""
    expr = expr.strip()
    if not expr:
        return None

    # Look for AS alias — search from right to handle nested function calls
    # We need to find a top-level AS keyword
    depth = 0
    tokens = []
    i = 0
    n = len(expr)
    current = []

    while i < n:
        ch = expr[i]
        if ch in "([":
            depth += 1
            current.append(ch)
            i += 1
        elif ch in ")]":
            depth -= 1
            current.append(ch)
            i += 1
        elif depth == 0 and expr[i : i + 3].upper() == " AS":
            after = expr[i + 3] if i + 3 < n else " "
            if after in (" ", "\n", "\t", "`"):
                tokens.append("".join(current).strip())
                current = []
                i += 3  # skip " AS"
                continue
            else:
                current.append(ch)
                i += 1
        else:
            current.append(ch)
            i += 1

    tokens.append("".join(current).strip())

    if len(tokens) >= 2:
        # Last token is the alias
        alias = tokens[-1].strip().strip("`").strip()
        return alias if alias else None

    # No AS — use last token (handle qualified: table.col → col)
    last = tokens[-1].strip()
    # Remove backtick quoting
    last = last.strip("`")
    # Handle qualified reference
    if "." in last:
        last = last.split(".")[-1].strip("`")
    # Take last word as fallback (handles function calls without alias — rare)
    words = re.split(r"\s+", last)
    result = words[-1].strip().strip("`") if words else None
    return result if result else None


def parse_select_columns(body: str) -> list[str]:
    """Split SELECT body on top-level commas and extract column names."""
    # Split on commas at depth 0
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))

    columns: list[str] = []
    for part in parts:
        name = _extract_column_name(part)
        if name and name != "*":
            columns.append(name)
    return columns


# ---------------------------------------------------------------------------
# YML path
# ---------------------------------------------------------------------------


def find_yml_path(sql_path: Path) -> Path:
    """Return the properties YML path for a SQL model file."""
    return sql_path.parent / "properties" / sql_path.with_suffix(".yml").name


# ---------------------------------------------------------------------------
# Schema resolution
# ---------------------------------------------------------------------------

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[4]
# .vscode/scripts/shared/dbt_yml_utils.py → 4 levels up = repo root


def resolve_schema(sql_path: Path, repo_root: Path | None = None) -> str:
    """Resolve the production BigQuery dataset name for a dbt SQL model.

    Reads the dbt_project.yml for the project that owns the sql_path and walks
    the +schema config hierarchy to find the most-specific schema suffix.

    Returns the prod schema: ``<project>_<schema_suffix>``.
    """
    if repo_root is None:
        repo_root = _DEFAULT_REPO_ROOT

    # Determine which dbt project owns this file
    dbt_src = repo_root / "src" / "dbt"
    try:
        rel = sql_path.relative_to(dbt_src)
    except ValueError:
        raise ValueError(f"{sql_path} is not under {dbt_src}")

    project_name = rel.parts[0]
    dbt_project_yml = dbt_src / project_name / "dbt_project.yml"

    with dbt_project_yml.open() as f:
        project_config = yaml.safe_load(f)

    models_config = project_config.get("models", {})

    # The model path relative to models/ directory
    models_dir = dbt_src / project_name / "models"
    try:
        model_rel = sql_path.relative_to(models_dir)
    except ValueError:
        # sql_path may not be under models/ (e.g. synthetic test paths)
        # Fall back: try using parts after project_name/models
        parts = rel.parts[2:]  # skip project_name/models
        model_rel = Path(*parts) if parts else Path(sql_path.name)

    # Walk the config hierarchy: project → dir1 → dir2 → ...
    # Start from the project-level config
    project_node = models_config.get(project_name, {})
    path_parts = list(model_rel.parts[:-1])  # directories, not the filename

    schema_suffix = _walk_schema(project_node, path_parts)
    if schema_suffix is None:
        schema_suffix = "extracts"

    return f"{project_name}_{schema_suffix}"


def _walk_schema(node: dict, parts: list[str]) -> str | None:
    """Recursively walk the dbt_project.yml models config to find +schema.

    Returns the most-specific +schema value, or None if not found.
    """
    # Collect schemas as we descend, most-specific wins
    schema = node.get("+schema")
    current_schema = schema

    remaining = list(parts)
    current_node = node

    for part in remaining:
        if part in current_node:
            current_node = current_node[part]
            sub_schema = current_node.get("+schema")
            if sub_schema is not None:
                current_schema = sub_schema
        else:
            break

    return current_schema


# ---------------------------------------------------------------------------
# BigQuery schema query
# ---------------------------------------------------------------------------


def query_column_types(
    model_name: str,
    dataset: str,
    project: str = "teamster-332318",
) -> dict[str, str]:
    """Query BigQuery INFORMATION_SCHEMA.COLUMNS for column data types.

    Returns {column_name: data_type} with lowercase values.
    Returns empty dict on any error.
    """
    # Validate identifiers to prevent injection via f-string interpolation
    if not re.fullmatch(r"[\w-]+", dataset):
        return {}
    if not re.fullmatch(r"[\w-]+", project):
        return {}

    try:
        client = bigquery.Client(project=project)
        query = (
            f"SELECT column_name, data_type "
            f"FROM `{project}`.{dataset}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = @table_name "
            f"ORDER BY ordinal_position"
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("table_name", "STRING", model_name)
            ]
        )
        result = client.query(query, job_config=job_config).result()
        return {row.column_name: row.data_type.lower() for row in result}
    except Exception as exc:
        print(
            f"[dbt_yml_utils] BQ query failed for {model_name}: {exc}",
            file=sys.stderr,
        )
        return {}


# ---------------------------------------------------------------------------
# YML sync
# ---------------------------------------------------------------------------


def sync_yml(
    yml_path: Path,
    sql_columns: list[str],
    bq_types: dict[str, str],
) -> None:
    """Sync a dbt properties YML file with the SQL column list.

    - Column order matches sql_columns order.
    - New columns are added with data_type from bq_types (empty string if unknown).
    - Deleted columns are removed.
    - Existing data_type is updated if bq_types has a different value.
    - Existing metadata (description, data_tests) is preserved.
    - Model-level keys (config, data_tests) are preserved.
    """
    yml_path = Path(yml_path)

    # Load existing YML or create skeleton
    if yml_path.exists():
        with yml_path.open() as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    if "models" not in data:
        model_name = yml_path.stem
        data["models"] = [{"name": model_name, "columns": []}]

    models = data["models"]
    if len(models) > 1:
        print(
            f"[dbt_yml_utils] Warning: {yml_path} contains {len(models)} models,"
            " only syncing first",
            file=sys.stderr,
        )

    model = models[0]
    if "columns" not in model:
        model["columns"] = []

    # Index existing columns by name for fast lookup
    existing: dict[str, dict] = {col["name"]: col for col in model["columns"]}

    # Build new column list in SQL order
    new_columns: list[dict] = []
    for col_name in sql_columns:
        if col_name in existing:
            col = dict(existing[col_name])
        else:
            col = {"name": col_name}

        # Update data_type if we have BQ info
        if col_name in bq_types:
            col["data_type"] = bq_types[col_name]

        new_columns.append(col)

    model["columns"] = new_columns

    # Write back
    yml_path.parent.mkdir(parents=True, exist_ok=True)
    with yml_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
