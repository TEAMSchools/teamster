# dbt Extract YML Auto-Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically generate and sync dbt YML property files for extract
models — on save (existing models) and at commit time (new models) — eliminating
manual YML maintenance for the `extracts/` layer.

**Architecture:** Two components: (1) a Python file watcher (VS Code background
task) that syncs existing YML files when SQL is saved, querying BigQuery for
data_types; (2) a Trunk pre-commit action that blocks commits missing complete
YMLs and provides a generator script. Shared SQL parsing and BQ query logic
lives in a common module.

**Tech Stack:** Python 3.13 (via `uv run`), watchdog (file system events),
PyYAML, google-cloud-bigquery, Trunk custom actions, bash

**Spec:** [approved plan](../../.claude/plans/dazzling-fluttering-goblet.md)

---

## File Map

| File                                           | Action          | Task |
| ---------------------------------------------- | --------------- | ---- |
| `.vscode/scripts/shared/__init__.py`           | Create          | 1    |
| `.vscode/scripts/shared/dbt_yml_utils.py`      | Create          | 1    |
| `tests/test_dbt_yml_utils.py`                  | Create          | 1    |
| `.vscode/scripts/dbt-extracts-yml-sync.py`     | Create          | 2    |
| `.vscode/scripts/dbt-extracts-yml-generate.py` | Create          | 3    |
| `.vscode/scripts/dbt-extracts-yml-check.sh`    | Create          | 4    |
| `.trunk/trunk.yaml`                            | Modify (manual) | 4    |
| `.vscode/tasks.json`                           | Modify          | 5    |
| `.vscode/CLAUDE.md`                            | Modify          | 6    |
| `src/dbt/CLAUDE.md`                            | Modify          | 6    |

**Manual application pattern:** `.trunk/trunk.yaml` is protected by hooks. Draft
the change and present as a complete replacement block for the user to apply
manually.

---

### Task 1: Shared utilities — SQL parser + BQ schema resolver

**Files:**

- Create: `.vscode/scripts/shared/dbt_yml_utils.py`
- Create: `tests/test_dbt_yml_utils.py`

This module contains all reusable logic: Jinja stripping, SQL column extraction,
BigQuery schema resolution, YML path computation, and YML sync logic.

#### Schema resolution

Given a SQL file path like
`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__foo.sql`:

1. Extract project name from path: `kipptaf`
2. Read `src/dbt/<project>/dbt_project.yml` for `+schema` config
3. Walk the directory hierarchy to find the most specific `+schema` override
4. Combine: dev → `zz_<GITHUB_USER>_<project>_<schema>`, prod →
   `<project>_<schema>`
5. Default to prod schema for BQ queries (the materialized table lives there)

Known schema mappings from `dbt_project.yml`:

| Project    | Path                | Schema suffix | BQ dataset (prod)     |
| ---------- | ------------------- | ------------- | --------------------- |
| kipptaf    | `extracts/`         | `extracts`    | `kipptaf_extracts`    |
| kipptaf    | `extracts/tableau/` | `tableau`     | `kipptaf_tableau`     |
| kippnewark | `extracts/`         | `extracts`    | `kippnewark_extracts` |
| kippcamden | `extracts/`         | `extracts`    | `kippcamden_extracts` |
| kippmiami  | `extracts/`         | `extracts`    | `kippmiami_extracts`  |

- [ ] **Step 1: Write failing tests for `strip_jinja()`**

```python
# tests/test_dbt_yml_utils.py
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".vscode" / "scripts"))
from shared.dbt_yml_utils import strip_jinja


class TestStripJinja:
    def test_removes_jinja_comments(self):
        sql = "select col {#- this is a comment #} from t"
        assert strip_jinja(sql) == "select col  from t"

    def test_replaces_jinja_expressions_with_placeholder(self):
        sql = "from {{ ref('stg_foo') }} as f"
        result = strip_jinja(sql)
        assert "ref" not in result
        assert "__JINJA__" in result

    def test_removes_jinja_blocks(self):
        sql = "{% if true %}select col{% endif %}"
        result = strip_jinja(sql)
        assert "{%" not in result

    def test_removes_sql_line_comments(self):
        sql = "select col -- this is a comment\nfrom t"
        assert "comment" not in strip_jinja(sql)

    def test_removes_sql_block_comments(self):
        sql = "select /* block */ col from t"
        assert "block" not in strip_jinja(sql)

    def test_preserves_sql_structure(self):
        sql = "select\n    col_a,\n    col_b,\nfrom {{ ref('foo') }}"
        result = strip_jinja(sql)
        assert "col_a" in result
        assert "col_b" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbt_yml_utils.py::TestStripJinja -v
```

Expected: `ModuleNotFoundError` — module doesn't exist yet.

- [ ] **Step 3: Implement `strip_jinja()`**

```python
# .vscode/scripts/shared/dbt_yml_utils.py
"""Shared utilities for dbt extract YML auto-generation."""

from __future__ import annotations

import re
from pathlib import Path

# --- Jinja/SQL stripping ---

_JINJA_COMMENT = re.compile(r"\{#-?[\s\S]*?-?#\}")
_JINJA_EXPR = re.compile(r"\{\{[\s\S]*?\}\}")
_JINJA_BLOCK = re.compile(r"\{%[\s\S]*?%\}")
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")


def strip_jinja(sql: str) -> str:
    """Remove Jinja and SQL comments, replace Jinja expressions with placeholder."""
    sql = _JINJA_COMMENT.sub("", sql)
    sql = _JINJA_EXPR.sub("__JINJA__", sql)
    sql = _JINJA_BLOCK.sub("", sql)
    sql = _SQL_LINE_COMMENT.sub("", sql)
    sql = _SQL_BLOCK_COMMENT.sub("", sql)
    return sql
```

Also create `__init__.py`:

```python
# .vscode/scripts/shared/__init__.py
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_dbt_yml_utils.py::TestStripJinja -v
```

Expected: all PASS.

- [ ] **Step 5: Write failing tests for `find_first_select()` and
      `parse_select_columns()`**

```python
# tests/test_dbt_yml_utils.py (append)
from shared.dbt_yml_utils import find_first_select, parse_select_columns


class TestFindFirstSelect:
    def test_simple_select(self):
        sql = "select col_a, col_b, from t"
        result = find_first_select(strip_jinja(sql))
        assert "col_a" in result
        assert "col_b" in result

    def test_cte_returns_final_select(self):
        sql = "with cte as (select x from y) select col_a, col_b, from cte"
        result = find_first_select(strip_jinja(sql))
        assert "col_a" in result

    def test_union_all_returns_first_select(self):
        sql = "select col_a, col_b, from t1 union all select col_a, col_b, from t2"
        result = find_first_select(strip_jinja(sql))
        # Should return the body of the FIRST select
        assert "t1" not in result  # FROM is excluded
        assert "col_a" in result

    def test_subquery_not_confused_with_top_level(self):
        sql = "select (select max(x) from y) as mx, col_b, from t"
        result = find_first_select(strip_jinja(sql))
        assert "mx" in result or "col_b" in result

    def test_select_distinct(self):
        sql = "select distinct col_a, col_b, from t"
        result = find_first_select(strip_jinja(sql))
        assert "col_a" in result
        assert "distinct" not in result.lower().split(",")[0].strip()


class TestParseSelectColumns:
    def test_simple_columns(self):
        body = "col_a, col_b, col_c,"
        assert parse_select_columns(body) == ["col_a", "col_b", "col_c"]

    def test_aliased_columns(self):
        body = "x as col_a, y as col_b,"
        assert parse_select_columns(body) == ["col_a", "col_b"]

    def test_qualified_columns(self):
        body = "t.col_a, t.col_b,"
        assert parse_select_columns(body) == ["col_a", "col_b"]

    def test_function_with_alias(self):
        body = "concat(a, b) as full_name, upper(c) as upper_c,"
        assert parse_select_columns(body) == ["full_name", "upper_c"]

    def test_backtick_quoted(self):
        body = "null as `last year final`, null as `Q1 pct`,"
        assert parse_select_columns(body) == ["last year final", "Q1 pct"]

    def test_null_literal_with_alias(self):
        body = "null as pm1, 'Benchmark' as score_type,"
        assert parse_select_columns(body) == ["pm1", "score_type"]

    def test_window_function_with_alias(self):
        body = "max(x) over (partition by y) as max_x,"
        assert parse_select_columns(body) == ["max_x"]

    def test_jinja_placeholder_with_alias(self):
        body = "__JINJA__ as ref_col, col_b,"
        assert parse_select_columns(body) == ["ref_col", "col_b"]

    def test_star_expression_filtered(self):
        body = "*, col_b,"
        assert parse_select_columns(body) == ["col_b"]

    def test_no_trailing_comma(self):
        body = "col_a, col_b"
        assert parse_select_columns(body) == ["col_a", "col_b"]
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v -k "FindFirstSelect or ParseSelectColumns"
```

Expected: `ImportError` — functions not defined.

- [ ] **Step 7: Implement `find_first_select()` and `parse_select_columns()`**

```python
# .vscode/scripts/shared/dbt_yml_utils.py (append)

def find_first_select(sql: str) -> str:
    """Find the column body of the first top-level SELECT (between SELECT and FROM).

    For UNION ALL queries, returns the first SELECT's column body.
    Skips SELECTs inside CTEs and subqueries using parenthesis depth tracking.

    Strategy: find all top-level SELECT positions (depth 0, not inside parens),
    then take the first one. CTEs are handled naturally because CTE body SELECTs
    are inside parentheses (depth > 0).
    """
    cleaned = sql.strip()

    # Find the first top-level SELECT (at paren depth 0)
    # CTE bodies are inside parens, so their SELECTs are at depth > 0
    depth = 0
    select_pos = None
    pos = 0

    # Handle DISTINCT keyword after SELECT
    while pos < len(cleaned):
        ch = cleaned[pos]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            rest = cleaned[pos:]
            rest_lower = rest.lower()
            if rest_lower.startswith("select") and (
                pos == 0 or not cleaned[pos - 1].isalnum()
            ):
                after = pos + 6
                if after >= len(cleaned) or not cleaned[after].isalnum():
                    # Skip DISTINCT if present
                    body_start = after
                    remaining = cleaned[body_start:].lstrip()
                    if remaining.lower().startswith("distinct"):
                        body_start = cleaned.index("distinct", body_start) + 8
                        if body_start < len(cleaned) and not cleaned[body_start].isalnum():
                            pass  # body_start is correct
                    select_pos = body_start
                    break
        pos += 1

    if select_pos is None:
        msg = "No top-level SELECT found"
        raise ValueError(msg)

    # Now find FROM at the same depth
    depth = 0
    pos = select_pos
    while pos < len(cleaned):
        ch = cleaned[pos]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            rest = cleaned[pos:].lower()
            if rest.startswith("from") and (
                pos == 0 or not cleaned[pos - 1].isalnum()
            ):
                after = pos + 4
                if after >= len(cleaned) or not cleaned[after].isalnum():
                    return cleaned[select_pos:pos].strip()
        pos += 1

    msg = "No FROM found after SELECT"
    raise ValueError(msg)


def parse_select_columns(body: str) -> list[str]:
    """Extract column names from a SELECT body (text between SELECT and FROM).

    Returns column names in order. Handles aliases, qualified names, functions,
    backtick-quoted identifiers, and trailing commas.
    """
    # Split on commas at depth 0
    columns: list[str] = []
    depth = 0
    current: list[str] = []

    for ch in body:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            expr = "".join(current).strip()
            if expr:
                columns.append(expr)
            current = []
        else:
            current.append(ch)

    # Handle last expression (may not have trailing comma)
    last = "".join(current).strip()
    if last:
        columns.append(last)

    # Extract name from each column expression
    names: list[str] = []
    for expr in columns:
        name = _extract_column_name(expr)
        if name and name != "*":
            names.append(name)
    return names


def _extract_column_name(expr: str) -> str | None:
    """Extract the column name/alias from a single SELECT expression."""
    expr = expr.strip()
    if not expr:
        return None

    # Check for AS keyword (case-insensitive, word boundary)
    as_match = re.search(r"\bAS\s+", expr, re.IGNORECASE)
    if as_match:
        alias = expr[as_match.end():].strip()
        return alias.strip("`")

    # No alias — take the last token
    # Remove parenthesized expressions for token extraction
    tokens = expr.split()
    last_token = tokens[-1] if tokens else expr
    # Handle qualified names: table.col -> col
    if "." in last_token:
        last_token = last_token.rsplit(".", 1)[-1]
    return last_token.strip("`")
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v
```

Expected: all PASS.

- [ ] **Step 9: Write failing tests for `find_yml_path()` and
      `resolve_schema()`**

```python
# tests/test_dbt_yml_utils.py (append)
from shared.dbt_yml_utils import find_yml_path, resolve_schema


class TestFindYmlPath:
    def test_standard_path(self):
        sql = Path("src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql")
        expected = Path(
            "src/dbt/kipptaf/models/extracts/clever/properties/rpt_clever__enrollments.yml"
        )
        assert find_yml_path(sql) == expected

    def test_nested_subdirectory(self):
        sql = Path("src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__foo.sql")
        expected = Path(
            "src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__foo.yml"
        )
        assert find_yml_path(sql) == expected


class TestResolveSchema:
    def test_kipptaf_extracts(self):
        sql = Path("src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql")
        assert resolve_schema(sql) == "kipptaf_extracts"

    def test_kipptaf_tableau(self):
        sql = Path("src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__foo.sql")
        assert resolve_schema(sql) == "kipptaf_tableau"

    def test_school_project_extracts(self):
        sql = Path("src/dbt/kippnewark/models/extracts/powerschool/rpt_ps__foo.sql")
        assert resolve_schema(sql) == "kippnewark_extracts"
```

- [ ] **Step 10: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v -k "FindYmlPath or ResolveSchema"
```

Expected: `ImportError`.

- [ ] **Step 11: Implement `find_yml_path()` and `resolve_schema()`**

```python
# .vscode/scripts/shared/dbt_yml_utils.py (append)
import yaml


def find_yml_path(sql_path: Path) -> Path:
    """Compute the YML property file path for a given SQL model file."""
    return sql_path.parent / "properties" / sql_path.with_suffix(".yml").name


def resolve_schema(sql_path: Path, repo_root: Path | None = None) -> str:
    """Resolve the BigQuery dataset name for an extract model.

    Reads dbt_project.yml to find the +schema config for the model's directory.
    Returns the prod schema: <project>_<schema_suffix>.
    """
    if repo_root is None:
        repo_root = Path("/workspaces/teamster")

    parts = sql_path.parts
    # Find project name: part after "dbt" in path
    dbt_idx = parts.index("dbt")
    project_name = parts[dbt_idx + 1]

    # Read dbt_project.yml
    project_yml = repo_root / "src" / "dbt" / project_name / "dbt_project.yml"
    with project_yml.open() as f:
        config = yaml.safe_load(f)

    # Walk the models config hierarchy to find most specific +schema
    models_config = config.get("models", {}).get(project_name, {})

    # Build the relative path from models/ to the SQL file's directory
    models_idx = parts.index("models")
    dir_parts = parts[models_idx + 1 : -1]  # e.g., ("extracts", "tableau")

    schema_suffix = "extracts"  # default for extracts
    current = models_config
    for part in dir_parts:
        if part == "properties":
            break
        current = current.get(part, {})
        if "+schema" in current:
            schema_suffix = current["+schema"]

    return f"{project_name}_{schema_suffix}"
```

- [ ] **Step 12: Run tests to verify they pass**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v
```

Expected: all PASS.

- [ ] **Step 13: Write failing tests for `query_column_types()`**

```python
# tests/test_dbt_yml_utils.py (append)
from unittest.mock import MagicMock, patch
from shared.dbt_yml_utils import query_column_types


class TestQueryColumnTypes:
    @patch("shared.dbt_yml_utils.bigquery.Client")
    def test_returns_type_mapping(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.query.return_value = [
            MagicMock(column_name="col_a", data_type="STRING"),
            MagicMock(column_name="col_b", data_type="INT64"),
        ]
        result = query_column_types("my_model", "kipptaf_extracts")
        assert result == {"col_a": "string", "col_b": "int64"}

    @patch("shared.dbt_yml_utils.bigquery.Client")
    def test_returns_empty_on_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.query.side_effect = Exception("table not found")
        result = query_column_types("missing_model", "kipptaf_extracts")
        assert result == {}
```

- [ ] **Step 14: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbt_yml_utils.py::TestQueryColumnTypes -v
```

Expected: `ImportError`.

- [ ] **Step 15: Implement `query_column_types()`**

```python
# .vscode/scripts/shared/dbt_yml_utils.py (append)
from google.cloud import bigquery


_BQ_PROJECT = "teamster-332318"


def query_column_types(
    model_name: str,
    dataset: str,
    project: str = _BQ_PROJECT,
) -> dict[str, str]:
    """Query BigQuery INFORMATION_SCHEMA.COLUMNS for column data types.

    Returns {column_name: data_type} mapping. Returns empty dict on error
    (e.g., model not yet materialized).
    """
    try:
        client = bigquery.Client(project=project)
        sql = (
            f"SELECT column_name, data_type "
            f"FROM `{project}`.{dataset}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE table_name = '{model_name}' "
            f"ORDER BY ordinal_position"
        )
        rows = client.query(sql)
        return {row.column_name: row.data_type.lower() for row in rows}
    except Exception:
        return {}
```

- [ ] **Step 16: Run tests to verify they pass**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v
```

Expected: all PASS.

- [ ] **Step 17: Write failing tests for `sync_yml()`**

```python
# tests/test_dbt_yml_utils.py (append)
from shared.dbt_yml_utils import sync_yml


class TestSyncYml:
    def test_adds_new_columns(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "columns": [
                {"name": "col_a", "data_type": "string"},
            ]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a", "col_b"],
            bq_types={"col_a": "string", "col_b": "int64"},
        )
        data = yaml.safe_load(yml_path.read_text())
        cols = data["models"][0]["columns"]
        assert len(cols) == 2
        assert cols[1] == {"name": "col_b", "data_type": "int64"}

    def test_removes_deleted_columns(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "columns": [
                {"name": "col_a", "data_type": "string"},
                {"name": "col_b", "data_type": "int64"},
            ]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a"],
            bq_types={"col_a": "string"},
        )
        data = yaml.safe_load(yml_path.read_text())
        cols = data["models"][0]["columns"]
        assert len(cols) == 1
        assert cols[0]["name"] == "col_a"

    def test_preserves_existing_metadata(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "columns": [
                {
                    "name": "col_a",
                    "data_type": "string",
                    "description": "important col",
                    "data_tests": [{"unique": {"config": {"store_failures": True}}}],
                },
            ]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a"],
            bq_types={"col_a": "string"},
        )
        data = yaml.safe_load(yml_path.read_text())
        col = data["models"][0]["columns"][0]
        assert col["description"] == "important col"
        assert "data_tests" in col

    def test_column_order_matches_sql(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "columns": [
                {"name": "col_b", "data_type": "int64"},
                {"name": "col_a", "data_type": "string"},
            ]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a", "col_b"],
            bq_types={"col_a": "string", "col_b": "int64"},
        )
        data = yaml.safe_load(yml_path.read_text())
        cols = data["models"][0]["columns"]
        assert cols[0]["name"] == "col_a"
        assert cols[1]["name"] == "col_b"

    def test_updates_data_type(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "columns": [
                {"name": "col_a", "data_type": "string"},
            ]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a"],
            bq_types={"col_a": "int64"},
        )
        data = yaml.safe_load(yml_path.read_text())
        assert data["models"][0]["columns"][0]["data_type"] == "int64"

    def test_preserves_model_level_keys(self, tmp_path):
        yml_path = tmp_path / "model.yml"
        yml_path.write_text(yaml.dump({
            "models": [{"name": "m", "config": {"contract": {"enforced": True}},
                "data_tests": [{"dbt_utils.unique_combination_of_columns": {}}],
                "columns": [{"name": "col_a", "data_type": "string"}]}]
        }))
        sync_yml(
            yml_path=yml_path,
            sql_columns=["col_a"],
            bq_types={"col_a": "string"},
        )
        data = yaml.safe_load(yml_path.read_text())
        model = data["models"][0]
        assert "config" in model
        assert "data_tests" in model
```

- [ ] **Step 18: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v -k "CreateYml or SyncYml"
```

Expected: `ImportError`.

- [ ] **Step 19: Implement `sync_yml()`**

```python
# .vscode/scripts/shared/dbt_yml_utils.py (append)


def sync_yml(
    yml_path: Path,
    sql_columns: list[str],
    bq_types: dict[str, str],
) -> None:
    """Sync YML columns with SQL columns. Column order matches sql_columns order.

    - Adds new columns (with data_type from bq_types)
    - Removes columns not in sql_columns
    - Updates data_type if changed
    - Preserves existing metadata (description, data_tests, etc.)
    - Preserves model-level keys (config, data_tests, etc.)
    """
    data = yaml.safe_load(yml_path.read_text())
    model = data["models"][0]

    # Build lookup of existing columns by name
    existing: dict[str, dict] = {}
    for col in model.get("columns", []):
        existing[col["name"]] = col

    # Build new columns list in SQL order
    new_columns: list[dict] = []
    for col_name in sql_columns:
        if col_name in existing:
            col = existing[col_name]
            # Update data_type if BQ has a different one
            if col_name in bq_types:
                col["data_type"] = bq_types[col_name]
            new_columns.append(col)
        else:
            col = {"name": col_name}
            if col_name in bq_types:
                col["data_type"] = bq_types[col_name]
            new_columns.append(col)

    model["columns"] = new_columns
    yml_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )
```

- [ ] **Step 20: Run all tests to verify they pass**

```bash
uv run pytest tests/test_dbt_yml_utils.py -v
```

Expected: all PASS.

- [ ] **Step 21: Integration test against real SQL files**

```python
# tests/test_dbt_yml_utils.py (append)


class TestIntegrationRealFiles:
    """Test column extraction against actual SQL files in the repo."""

    def _extract(self, sql_path: str) -> list[str]:
        path = Path("/workspaces/teamster") / sql_path
        sql = path.read_text()
        body = find_first_select(strip_jinja(sql))
        return parse_select_columns(body)

    def test_clever_enrollments_union_all(self):
        cols = self._extract(
            "src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql"
        )
        assert cols == ["school_id", "section_id", "student_id"]

    def test_resolve_schema_kipptaf_tableau(self):
        sql_path = Path(
            "src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__assessment_entry_audit.sql"
        )
        assert resolve_schema(sql_path) == "kipptaf_tableau"

    def test_resolve_schema_kipptaf_extracts(self):
        sql_path = Path(
            "src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql"
        )
        assert resolve_schema(sql_path) == "kipptaf_extracts"
```

- [ ] **Step 22: Run integration tests**

```bash
uv run pytest tests/test_dbt_yml_utils.py::TestIntegrationRealFiles -v
```

Expected: all PASS.

- [ ] **Step 23: Commit**

```bash
git add tests/test_dbt_yml_utils.py .vscode/scripts/shared/dbt_yml_utils.py .vscode/scripts/shared/__init__.py
git commit -m "feat: add shared dbt YML utilities — SQL parser, schema resolver, YML sync"
```

---

### Task 2: File watcher — VS Code background task

**Files:**

- Create: `.vscode/scripts/dbt-extracts-yml-sync.py`

This script runs as a background VS Code task, watching for SQL file saves in
extracts directories and syncing the matching YML.

- [ ] **Step 1: Write the file watcher script**

```python
# .vscode/scripts/dbt-extracts-yml-sync.py
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Watch dbt extract SQL files and sync matching YML property files on save."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

# Add shared module to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared.dbt_yml_utils import (
    find_first_select,
    find_yml_path,
    parse_select_columns,
    query_column_types,
    resolve_schema,
    strip_jinja,
    sync_yml,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [yml-sync] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path("/workspaces/teamster")
DEBOUNCE_SECONDS = 1.0


class ExtractsSqlHandler(PatternMatchingEventHandler):
    """Handle SQL file changes in extracts directories."""

    def __init__(self) -> None:
        super().__init__(patterns=["*.sql"], ignore_directories=True)
        self._last_trigger: dict[str, float] = {}

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent) -> None:
        sql_path = Path(event.src_path)

        # Debounce
        now = time.monotonic()
        last = self._last_trigger.get(str(sql_path), 0)
        if now - last < DEBOUNCE_SECONDS:
            return
        self._last_trigger[str(sql_path)] = now

        yml_path = find_yml_path(sql_path)
        if not yml_path.exists():
            log.info("No YML for %s (new file — will be handled at commit time)", sql_path.name)
            return

        try:
            sql = sql_path.read_text()
            body = find_first_select(strip_jinja(sql))
            columns = parse_select_columns(body)

            if not columns:
                log.warning("No columns extracted from %s — skipping", sql_path.name)
                return

            schema = resolve_schema(
                sql_path.relative_to(REPO_ROOT), repo_root=REPO_ROOT
            )
            model_name = sql_path.stem
            bq_types = query_column_types(model_name, schema)

            sync_yml(yml_path=yml_path, sql_columns=columns, bq_types=bq_types)
            log.info("Synced %s (%d columns)", yml_path.name, len(columns))
        except Exception:
            log.exception("Error syncing %s", sql_path.name)


def main() -> None:
    observer = Observer()
    handler = ExtractsSqlHandler()

    watched = 0
    for extracts_dir in REPO_ROOT.glob("src/dbt/*/models/extracts"):
        observer.schedule(handler, str(extracts_dir), recursive=True)
        watched += 1
        log.info("Watching %s", extracts_dir.relative_to(REPO_ROOT))

    if watched == 0:
        log.warning("No extracts directories found")
        return

    observer.start()
    log.info("dbt extracts YML sync ready (%d directories)", watched)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test the watcher manually**

```bash
# Start the watcher in the background
uv run .vscode/scripts/dbt-extracts-yml-sync.py &
WATCHER_PID=$!

# Wait for it to initialize
sleep 2

# Touch an existing SQL file to trigger sync
touch src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql

# Wait for sync
sleep 3

# Check the log output, then kill the watcher
kill $WATCHER_PID
```

Expected: log shows "Synced rpt_clever\_\_enrollments.yml (3 columns)".

- [ ] **Step 3: Commit**

```bash
git add .vscode/scripts/dbt-extracts-yml-sync.py
git commit -m "feat: add dbt extracts YML file watcher script"
```

---

### Task 3: YML generator script

**Files:**

- Create: `.vscode/scripts/dbt-extracts-yml-generate.py`

Standalone script to generate a complete YML for a new extract model. Used by
the pre-commit hook's instructions and can be run manually.

- [ ] **Step 1: Write the generator script**

```python
# .vscode/scripts/dbt-extracts-yml-generate.py
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""Generate a complete dbt YML property file for an extract model.

Usage:
    uv run .vscode/scripts/dbt-extracts-yml-generate.py <sql_file_path>
    uv run .vscode/scripts/dbt-extracts-yml-generate.py --defer <sql_file_path> [--defer-until=next|--defer-for=N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared.dbt_yml_utils import (
    find_first_select,
    find_yml_path,
    parse_select_columns,
    query_column_types,
    resolve_schema,
    strip_jinja,
)

REPO_ROOT = Path("/workspaces/teamster")
DEFERRALS_FILE = REPO_ROOT / ".vscode" / ".yml-sync-deferrals.json"


def generate_yml(sql_path: Path) -> Path:
    """Generate a complete YML property file for the given SQL model."""
    sql = sql_path.read_text()
    body = find_first_select(strip_jinja(sql))
    columns = parse_select_columns(body)

    rel_path = sql_path.relative_to(REPO_ROOT)
    schema = resolve_schema(rel_path, repo_root=REPO_ROOT)
    model_name = sql_path.stem
    bq_types = query_column_types(model_name, schema)

    # Build column list in SQL SELECT order
    col_entries: list[dict] = []
    for col_name in columns:
        entry: dict = {"name": col_name}
        if col_name in bq_types:
            entry["data_type"] = bq_types[col_name]
        col_entries.append(entry)

    data = {
        "models": [
            {
                "name": model_name,
                "config": {"contract": {"enforced": True}},
                "description": "TODO: set the correct unique key columns in data_tests below",
                "data_tests": [
                    {
                        "dbt_utils.unique_combination_of_columns": {
                            "arguments": {
                                "combination_of_columns": columns[:2],
                            },
                            "config": {"store_failures": True},
                        }
                    }
                ],
                "columns": col_entries,
            }
        ]
    }

    yml_path = find_yml_path(sql_path)
    yml_path.parent.mkdir(parents=True, exist_ok=True)
    yml_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )
    return yml_path


def load_deferrals() -> dict:
    if DEFERRALS_FILE.exists():
        return json.loads(DEFERRALS_FILE.read_text())
    return {}


def save_deferrals(deferrals: dict) -> None:
    DEFERRALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEFERRALS_FILE.write_text(json.dumps(deferrals, indent=2))


def defer_model(model_name: str, until: str = "next", count: int = 1) -> None:
    """Defer the YML check for a model."""
    deferrals = load_deferrals()
    if until == "next":
        deferrals[model_name] = {"type": "next", "remaining": 1}
    else:
        deferrals[model_name] = {"type": "count", "remaining": count}
    save_deferrals(deferrals)
    print(f"Deferred YML check for '{model_name}' ({until}, {count} commits)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dbt extract YML")
    parser.add_argument("sql_path", type=Path, help="Path to the SQL file")
    parser.add_argument("--defer", action="store_true", help="Defer the check")
    parser.add_argument("--defer-until", default="next", help="next (default)")
    parser.add_argument("--defer-for", type=int, default=1, help="Number of commits")
    args = parser.parse_args()

    sql_path = args.sql_path.resolve()
    model_name = sql_path.stem

    if args.defer:
        if args.defer_for > 1:
            defer_model(model_name, until="count", count=args.defer_for)
        else:
            defer_model(model_name, until=args.defer_until)
        return

    yml_path = generate_yml(sql_path)
    print(f"Generated: {yml_path}")
    print("TODO: Review the file and set the correct unique key columns in data_tests.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the generator manually**

```bash
# Test against an existing model (will overwrite — use a model you can reset)
uv run .vscode/scripts/dbt-extracts-yml-generate.py \
    src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql
```

Expected: generates YML with 3 columns, data_types from BQ, uniqueness test
stub, and a `description: "TODO: set the correct unique key columns..."`
reminder. Verify with `cat`.

- [ ] **Step 3: Test deferral**

```bash
uv run .vscode/scripts/dbt-extracts-yml-generate.py --defer --defer-for=3 \
    src/dbt/kipptaf/models/extracts/clever/rpt_clever__enrollments.sql
cat .vscode/.yml-sync-deferrals.json
```

Expected: JSON file with deferral entry.

- [ ] **Step 4: Reset the test file and commit**

```bash
git checkout -- src/dbt/kipptaf/models/extracts/clever/properties/rpt_clever__enrollments.yml
rm -f .vscode/.yml-sync-deferrals.json
git add .vscode/scripts/dbt-extracts-yml-generate.py
git commit -m "feat: add dbt extract YML generator script with deferral support"
```

---

### Task 4: Pre-commit hook — Trunk custom action

**Files:**

- Create: `.vscode/scripts/dbt-extracts-yml-check.sh`
- Modify (manual): `.trunk/trunk.yaml`

The pre-commit check runs as a Trunk action. It blocks commits with incomplete
extract YMLs and prints downstream impact reminders.

- [ ] **Step 1: Write the pre-commit check script**

```bash
#!/usr/bin/env bash
# .vscode/scripts/dbt-extracts-yml-check.sh
# Pre-commit check: ensures staged extract SQL files have complete YML property files.
# Called by trunk-action as a git pre-commit hook.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
DEFERRALS_FILE="${REPO_ROOT}/.vscode/.yml-sync-deferrals.json"

# Get staged files
staged_files=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)
if [[ -z "${staged_files}" ]]; then
	exit 0
fi

blocked=()
reminders=()

for file in ${staged_files}; do
	# Only check extract SQL files
	# trunk-ignore(shellcheck/SC2254): glob pattern intentional
	case "${file}" in
	src/dbt/*/models/extracts/*.sql | src/dbt/*/models/extracts/**/*.sql) ;;
	*) continue ;;
	esac

	model_name=$(basename "${file}" .sql)
	dir=$(dirname "${file}")
	yml_file="${dir}/properties/${model_name}.yml"

	# Check if this model is deferred
	if [[ -f "${DEFERRALS_FILE}" ]]; then
		remaining=$(uv run python -c "
import json, sys
d = json.load(open('${DEFERRALS_FILE}'))
m = d.get('${model_name}', {})
r = m.get('remaining', 0)
if r > 0:
    m['remaining'] = r - 1
    d['${model_name}'] = m
    json.dump(d, open('${DEFERRALS_FILE}', 'w'), indent=2)
print(r)
" 2>/dev/null || echo 0)
		if [[ "${remaining}" -gt 0 ]]; then
			continue
		fi
	fi

	# Check if this is a new file (added, not modified)
	diff_filter=$(git diff --cached --diff-filter=A --name-only -- "${file}" 2>/dev/null || true)

	if [[ -n "${diff_filter}" ]]; then
		# New file — must have a complete YML (with data_type + uniqueness test)
		if [[ ! -f "${REPO_ROOT}/${yml_file}" ]]; then
			blocked+=("${model_name}:${file}")
		else
			# YML exists but was created outside the generator — check completeness
			# Only block if the YML is also staged (i.e., newly created alongside the SQL)
			yml_staged=$(git diff --cached --name-only -- "${yml_file}" 2>/dev/null || true)
			if [[ -n "${yml_staged}" ]]; then
				has_data_type=$(grep -c "data_type:" "${REPO_ROOT}/${yml_file}" 2>/dev/null || echo 0)
				has_test=$(grep -c -E "(unique:|unique_combination_of_columns)" "${REPO_ROOT}/${yml_file}" 2>/dev/null || echo 0)
				if [[ "${has_data_type}" -eq 0 ]] || [[ "${has_test}" -eq 0 ]]; then
					blocked+=("${model_name}:${file}")
				fi
			fi
		fi
	else
		# Modified file — print downstream reminder
		reminders+=("${model_name}")
	fi
done

# Print reminders (non-blocking)
for model in "${reminders[@]+"${reminders[@]}"}"; do
	echo "💡 Friendly reminder: check downstream models for impact based on your"
	echo "   changes to '${model}'. Build the current model + downstream with:"
	echo "     dbt build --select ${model}+"
	echo ""
done

# Block if any models need YMLs
if [[ ${#blocked[@]} -gt 0 ]]; then
	echo "❌ The following extract models need complete YML property files:"
	echo ""
	for entry in "${blocked[@]}"; do
		model="${entry%%:*}"
		file="${entry#*:}"
		echo "  ${model}"
		echo "    Generate: uv run .vscode/scripts/dbt-extracts-yml-generate.py ${file}"
		echo "    Defer:    uv run .vscode/scripts/dbt-extracts-yml-generate.py --defer ${file}"
		echo "              Options: --defer-until=next | --defer-for=<N>"
		echo ""
	done
	echo "Generate the YML files, stage them, and commit again."
	exit 1
fi
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x .vscode/scripts/dbt-extracts-yml-check.sh
```

- [ ] **Step 3: Present trunk.yaml changes for manual application**

The user must manually add the custom action to `.trunk/trunk.yaml`. Add under
`actions:`:

```yaml
actions:
  definitions:
    - id: dbt-extract-yml-check
      display_name: dbt Extract YML Check
      description:
        Ensures staged extract SQL files have complete YML property files
      run: bash .vscode/scripts/dbt-extracts-yml-check.sh
      triggers:
        - git_hooks: [pre-commit]
  enabled:
    - dbt-extract-yml-check
    - trunk-announce
    - trunk-check-pre-push
    - trunk-fmt-pre-commit
    - trunk-upgrade-available
```

Insert `definitions:` before `enabled:` (currently line 82). Add
`dbt-extract-yml-check` to the `enabled` list.

- [ ] **Step 4: Test the pre-commit hook**

```bash
# Create a dummy SQL file
mkdir -p src/dbt/kipptaf/models/extracts/test_hook
cat > src/dbt/kipptaf/models/extracts/test_hook/rpt_test__hook_check.sql << 'EOF'
select
    1 as col_a,
    'hello' as col_b,
from {{ ref("stg_foo") }}
EOF

# Stage and attempt to commit
git add src/dbt/kipptaf/models/extracts/test_hook/rpt_test__hook_check.sql
git commit -m "test: verify pre-commit hook blocks"
```

Expected: commit blocked with message about missing YML.

- [ ] **Step 5: Clean up test file and commit the hook script**

```bash
git rm --cached src/dbt/kipptaf/models/extracts/test_hook/rpt_test__hook_check.sql
rm -rf src/dbt/kipptaf/models/extracts/test_hook
git add .vscode/scripts/dbt-extracts-yml-check.sh
git commit -m "feat: add pre-commit hook for dbt extract YML completeness"
```

---

### Task 5: VS Code task registration

**Files:**

- Modify: `.vscode/tasks.json`

- [ ] **Step 1: Add the background watcher task to tasks.json**

Add this entry to the `tasks` array in `.vscode/tasks.json` (after the existing
"dbt: Build Init" task, before the closing `]`):

```json
{
  "label": "dbt: Extracts YML Sync",
  "type": "shell",
  "command": "source \"${HOME}/.local/bin/env\" && uv run .vscode/scripts/dbt-extracts-yml-sync.py",
  "runOptions": {
    "runOn": "folderOpen"
  },
  "isBackground": true,
  "presentation": {
    "reveal": "never",
    "panel": "dedicated",
    "close": true
  },
  "problemMatcher": []
}
```

- [ ] **Step 2: Commit**

```bash
git add .vscode/tasks.json
git commit -m "feat: register dbt extracts YML sync as auto-start VS Code task"
```

---

### Task 6: Documentation updates

**Files:**

- Modify: `.vscode/CLAUDE.md`
- Modify: `src/dbt/CLAUDE.md`

- [ ] **Step 1: Update `.vscode/CLAUDE.md`**

Add a new section after the existing "Claude Auth" section:

```markdown
## dbt Extracts YML Sync

Background task that auto-syncs YML property files when extract SQL files are
saved. Watches `src/dbt/*/models/extracts/**/*.sql`.

- **Requires** `"task.allowAutomaticTasks": "on"` in VS Code User Settings (same
  requirement as "Setup: Post-Build Init")
- On save: parses the first SELECT, queries BigQuery for data_types, syncs the
  matching `properties/<model>.yml`
- Only acts on files that already have a YML — new files are handled by the
  pre-commit hook
- Generator script:
  `uv run .vscode/scripts/dbt-extracts-yml-generate.py <sql_path>`
- Pre-commit hook (via Trunk) blocks commits with incomplete extract YMLs
```

- [ ] **Step 2: Update `src/dbt/CLAUDE.md`**

Add a note under the "Per-layer requirements" section, after the `rpt_`,
`dim_*`, `fct_*` requirements:

```markdown
**Extract YML auto-generation**: YML property files for `models/extracts/` are
auto-synced on save (columns, data_types, column order). New extract models
trigger a pre-commit check — run the generator script to create a complete YML
before committing:

    uv run .vscode/scripts/dbt-extracts-yml-generate.py <sql_file_path>

The generator creates the YML with `contract: enforced: true`, all columns with
`data_type` from BigQuery, and a `dbt_utils.unique_combination_of_columns` stub.
Review and set the correct unique key columns before merging.
```

- [ ] **Step 3: Add `.vscode/.yml-sync-deferrals.json` to `.gitignore`**

This file is local state and should not be committed:

```bash
echo ".vscode/.yml-sync-deferrals.json" >> .gitignore
```

- [ ] **Step 4: Commit**

```bash
git add .vscode/CLAUDE.md src/dbt/CLAUDE.md .gitignore
git commit -m "docs: document dbt extract YML auto-generation workflow"
```
