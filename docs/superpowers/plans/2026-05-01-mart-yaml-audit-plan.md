# Mart YAML Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/audit_marts_yaml.py`, run it across
`src/dbt/kipptaf/models/marts/`, and commit the resulting audit report. Triage
and fix passes are out of scope for this plan — they happen after the report
exists.

**Architecture:** Single-file Python script (PEP 723 inline metadata, following
`scripts/gen_column_naming_audit_inventory.py` pattern). Reads mart YAMLs and
`target/manifest.json`, queries BigQuery via the `google-cloud-bigquery` client,
fetches Dagster asset-check status via the dbt-cloud-mcp / dagster-plus-mcp
Python clients, emits markdown + JSON reports under `docs/superpowers/specs/`.
Fail-hard on infrastructure errors; flag (don't abort) on findings.

**Tech Stack:** Python ≥3.13, `pyyaml`, `google-cloud-bigquery`, dbt manifest
JSON, Dagster GraphQL via `gql`. All deps declared in PEP 723 `# /// script`
block.

**Spec:**
[docs/superpowers/specs/2026-05-01-mart-yaml-audit-design.md](../specs/2026-05-01-mart-yaml-audit-design.md)

---

## File structure

| File                                                            | Purpose                                                                                  |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `scripts/audit_marts_yaml.py`                                   | The audit script (single file, ~600 LOC est.)                                            |
| `tests/scripts/test_audit_marts_yaml.py`                        | Unit tests for parse, normalize, bucketing, report rendering                             |
| `tests/scripts/fixtures/`                                       | Test fixtures: sample YAMLs, sample manifest.json subset, sample INFORMATION_SCHEMA rows |
| `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md`   | Run output (committed)                                                                   |
| `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json` | Run output (committed)                                                                   |
| `scripts/CLAUDE.md`                                             | One row added to the script catalog                                                      |

The script is divided into clear sections (one per concern) within the single
file:

```text
audit_marts_yaml.py
├─ PEP 723 metadata + module docstring
├─ Constants (paths, type-normalization map)
├─ YAML parsing (extract data_type, uniqueness tests, severity)
├─ Type normalization (BQ-form ↔ YAML-form)
├─ Manifest loader (mart model list, parent_map traversal)
├─ Upstream cast tracer (regex over compiled SQL)
├─ BigQuery introspection (INFORMATION_SCHEMA + grain probes)
├─ Dagster status fetcher (asset-check executions)
├─ Bucketing (Pass / Suspect / Broken / Warn-masked / Status-mismatch / Type-drift)
├─ Report rendering (markdown + JSON)
└─ CLI / main()
```

Each section has its own `# === SECTION ===` divider comment so the file stays
navigable.

---

## Task 1: Script skeleton + dependencies

**Files:**

- Create: `scripts/audit_marts_yaml.py`
- Create: `tests/scripts/__init__.py` (if not present)
- Create: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Create the script with PEP 723 header and a no-op main()**

```python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "pyyaml>=6.0",
#   "google-cloud-bigquery>=3.25",
#   "gql[requests]>=3.5",
# ]
# ///

"""Audit mart YAMLs against BigQuery and Dagster.

Two audits in one pass over `src/dbt/kipptaf/models/marts/**/*.yml`:

- Type drift: YAML `data_type` vs BigQuery `INFORMATION_SCHEMA.COLUMNS`.
- Grain / uniqueness test correctness: declared `unique` /
  `dbt_utils.unique_combination_of_columns` tests confirmed against the
  materialized table; over-specified tests and missing tests surfaced.

Outputs `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.{md,json}`.

Fail-hard on infrastructure errors (BQ / Dagster / parse). Findings
(failing tests, drift, mismatches) are flagged, never aborted.

Usage:
    uv run scripts/audit_marts_yaml.py

Design reference:
    docs/superpowers/specs/2026-05-01-mart-yaml-audit-design.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = REPO_ROOT / "src/dbt/kipptaf/models/marts"
MANIFEST_PATH = REPO_ROOT / "src/dbt/kipptaf/target/manifest.json"
REPORT_MD = REPO_ROOT / "docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md"
REPORT_JSON = REPO_ROOT / "docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json"


def main() -> None:
    description = (__doc__ or "").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.parse_args()
    raise NotImplementedError("audit not wired up yet")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs and exits with the expected error**

Run: `uv run scripts/audit_marts_yaml.py` Expected: exits non-zero with
`NotImplementedError: audit not wired up yet`.

- [ ] **Step 3: Commit**

```bash
git add scripts/audit_marts_yaml.py
git commit -m "feat: bootstrap mart YAML audit script (#3678)"
```

---

## Task 2: YAML parser

Extracts per-model: declared `data_type` per column, declared uniqueness test
columns (`unique` and `dbt_utils.unique_combination_of_columns`), declared
`severity` per uniqueness test, and the YAML file path.

The parser handles two test placements:

- single-column `unique` listed under a column's `data_tests:` block
- model-level `dbt_utils.unique_combination_of_columns` listed under the model's
  `data_tests:` block, with `arguments.combination_of_columns: [...]`

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Create / modify: `tests/scripts/test_audit_marts_yaml.py`
- Create: `tests/scripts/fixtures/sample_mart.yml`

- [ ] **Step 1: Write the failing test**

`tests/scripts/fixtures/sample_mart.yml`:

```yaml
models:
  - name: fct_sample
    description: Sample fact for unit testing.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_id
              - academic_year
          config:
            severity: warn
    columns:
      - name: surrogate_key
        data_type: string
        data_tests:
          - unique
          - not_null
      - name: student_id
        data_type: int64
      - name: academic_year
        data_type: int64
      - name: created_timestamp
        data_type: timestamp
```

`tests/scripts/test_audit_marts_yaml.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_marts_yaml import ParsedModel, parse_mart_yaml

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_mart_yaml_extracts_columns_and_tests() -> None:
    parsed = parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")

    assert isinstance(parsed, list)
    assert len(parsed) == 1
    model = parsed[0]
    assert isinstance(model, ParsedModel)
    assert model.name == "fct_sample"
    assert model.column_data_types == {
        "surrogate_key": "string",
        "student_id": "int64",
        "academic_year": "int64",
        "created_timestamp": "timestamp",
    }
    assert model.uniqueness_tests == [
        {"columns": ["surrogate_key"], "severity": "error", "kind": "unique"},
        {
            "columns": ["student_id", "academic_year"],
            "severity": "warn",
            "kind": "unique_combination_of_columns",
        },
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_parse_mart_yaml_extracts_columns_and_tests -v`
Expected: FAIL with ImportError (`ParsedModel`, `parse_mart_yaml` not defined).

- [ ] **Step 3: Implement the parser**

Append to `scripts/audit_marts_yaml.py` (in a `# === YAML parsing ===` section):

```python
import dataclasses
from typing import Any

import yaml


@dataclasses.dataclass(frozen=True)
class ParsedModel:
    name: str
    yaml_path: Path
    column_data_types: dict[str, str]
    uniqueness_tests: list[dict[str, Any]]


def _extract_unique_tests_from_column(
    col_name: str, data_tests: list[Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for test in data_tests:
        if test == "unique":
            out.append({"columns": [col_name], "severity": "error", "kind": "unique"})
        elif isinstance(test, dict) and "unique" in test:
            cfg = test["unique"].get("config", {})
            out.append(
                {
                    "columns": [col_name],
                    "severity": cfg.get("severity", "error"),
                    "kind": "unique",
                }
            )
    return out


def _extract_unique_combination_test(test: Any) -> dict[str, Any] | None:
    if not isinstance(test, dict):
        return None
    key = next(iter(test.keys()))
    if not key.endswith("unique_combination_of_columns"):
        return None
    body = test[key] or {}
    args = body.get("arguments", {})
    cols = args.get("combination_of_columns", [])
    cfg = body.get("config", {})
    return {
        "columns": list(cols),
        "severity": cfg.get("severity", "error"),
        "kind": "unique_combination_of_columns",
    }


def parse_mart_yaml(path: Path) -> list[ParsedModel]:
    raw = yaml.safe_load(path.read_text())
    out: list[ParsedModel] = []
    for model in raw.get("models", []):
        column_types: dict[str, str] = {}
        uniqueness: list[dict[str, Any]] = []

        for col in model.get("columns") or []:
            if "data_type" in col:
                column_types[col["name"]] = col["data_type"]
            for t in _extract_unique_tests_from_column(
                col["name"], col.get("data_tests") or []
            ):
                uniqueness.append(t)

        for t in model.get("data_tests") or []:
            extracted = _extract_unique_combination_test(t)
            if extracted is not None:
                uniqueness.append(extracted)

        out.append(
            ParsedModel(
                name=model["name"],
                yaml_path=path,
                column_data_types=column_types,
                uniqueness_tests=uniqueness,
            )
        )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_parse_mart_yaml_extracts_columns_and_tests -v`
Expected: PASS.

- [ ] **Step 5: Add a second fixture covering a multi-model file and
      column-level severity override**

Append to `sample_mart.yml`:

```yaml
- name: dim_sample
  columns:
    - name: dim_key
      data_type: string
      data_tests:
        - unique:
            config:
              severity: warn
```

Add test:

```python
def test_parse_mart_yaml_handles_multi_model_and_column_severity() -> None:
    parsed = parse_mart_yaml(FIXTURE_DIR / "sample_mart.yml")
    assert [m.name for m in parsed] == ["fct_sample", "dim_sample"]
    dim = parsed[1]
    assert dim.uniqueness_tests == [
        {"columns": ["dim_key"], "severity": "warn", "kind": "unique"},
    ]
```

Run: `uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/
git commit -m "feat: parse mart YAMLs for data_type, uniqueness tests, severity"
```

---

## Task 3: Type normalization

Normalize a type string for comparison: lowercase, strip parameterization
(`STRING(255)` → `string`, `NUMERIC(10,2)` → `numeric`). Used both ways — YAML
side and BQ side go through the same normalizer.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.audit_marts_yaml import normalize_type


def test_normalize_type_strips_params_and_lowercases() -> None:
    assert normalize_type("STRING") == "string"
    assert normalize_type("string") == "string"
    assert normalize_type("STRING(255)") == "string"
    assert normalize_type("NUMERIC(10,2)") == "numeric"
    assert normalize_type("BIGNUMERIC(38, 9)") == "bignumeric"
    assert normalize_type("DATETIME") == "datetime"
    assert normalize_type("TIMESTAMP") == "timestamp"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_normalize_type_strips_params_and_lowercases -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Type normalization ===`
section):

```python
import re

_TYPE_PARAM_RE = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_type(t: str) -> str:
    return _TYPE_PARAM_RE.sub("", t.strip()).lower()
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_normalize_type_strips_params_and_lowercases -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: add type normalization helper"
```

---

## Task 4: Manifest loader

Load `src/dbt/kipptaf/target/manifest.json`, extract mart models
(resource_type=model, file path under `models/marts/`), and provide a
parent-traversal helper that walks up `parent_map` to find ancestor models
touching a column. Compiled SQL is stored on each manifest node — we'll use it
in Task 6 for the cast trace.

The loader is fail-hard: if `manifest.json` is missing or unparseable, raise.
Engineers must run `uv run dbt parse --project-dir src/dbt/kipptaf` first.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`
- Create: `tests/scripts/fixtures/sample_manifest.json`

- [ ] **Step 1: Build a minimal manifest fixture**

`tests/scripts/fixtures/sample_manifest.json`:

```json
{
  "nodes": {
    "model.kipptaf.fct_sample": {
      "name": "fct_sample",
      "resource_type": "model",
      "package_name": "kipptaf",
      "original_file_path": "models/marts/facts/fct_sample.sql",
      "relation_name": "`teamster-332318`.`kipptaf`.`fct_sample`",
      "schema": "kipptaf",
      "database": "teamster-332318",
      "alias": "fct_sample",
      "depends_on": { "nodes": ["model.kipptaf.int_sample"] },
      "compiled_code": "select student_id, cast(created as datetime) as created_timestamp from {{ ref('int_sample') }}"
    },
    "model.kipptaf.int_sample": {
      "name": "int_sample",
      "resource_type": "model",
      "package_name": "kipptaf",
      "original_file_path": "models/people/int_sample.sql",
      "relation_name": "`teamster-332318`.`kipptaf`.`int_sample`",
      "schema": "kipptaf",
      "database": "teamster-332318",
      "alias": "int_sample",
      "depends_on": { "nodes": ["model.kipptaf.stg_sample"] },
      "compiled_code": "select student_id, created from {{ ref('stg_sample') }}"
    },
    "model.kipptaf.stg_sample": {
      "name": "stg_sample",
      "resource_type": "model",
      "package_name": "kipptaf",
      "original_file_path": "models/people/staging/stg_sample.sql",
      "relation_name": "`teamster-332318`.`kipptaf_people`.`stg_sample`",
      "schema": "kipptaf_people",
      "database": "teamster-332318",
      "alias": "stg_sample",
      "depends_on": { "nodes": [] },
      "compiled_code": "select student_id, cast(created as datetime) as created from src"
    },
    "model.kipptaf.dim_other": {
      "name": "dim_other",
      "resource_type": "model",
      "package_name": "kipptaf",
      "original_file_path": "models/people/intermediate/int_other.sql",
      "relation_name": "`teamster-332318`.`kipptaf`.`dim_other`",
      "schema": "kipptaf",
      "database": "teamster-332318",
      "alias": "dim_other",
      "depends_on": { "nodes": [] },
      "compiled_code": "select 1"
    }
  },
  "parent_map": {
    "model.kipptaf.fct_sample": ["model.kipptaf.int_sample"],
    "model.kipptaf.int_sample": ["model.kipptaf.stg_sample"],
    "model.kipptaf.stg_sample": [],
    "model.kipptaf.dim_other": []
  }
}
```

- [ ] **Step 2: Write the failing tests**

```python
from scripts.audit_marts_yaml import ManifestNode, load_manifest, mart_models


def test_load_manifest_returns_indexed_nodes() -> None:
    nodes = load_manifest(FIXTURE_DIR / "sample_manifest.json")
    assert "model.kipptaf.fct_sample" in nodes
    assert isinstance(nodes["model.kipptaf.fct_sample"], ManifestNode)
    assert nodes["model.kipptaf.fct_sample"].relation_name == "`teamster-332318`.`kipptaf`.`fct_sample`"


def test_mart_models_filters_to_marts_dir() -> None:
    nodes = load_manifest(FIXTURE_DIR / "sample_manifest.json")
    marts = mart_models(nodes)
    assert [n.name for n in marts] == ["fct_sample"]


def test_load_manifest_raises_when_missing() -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        load_manifest(FIXTURE_DIR / "does_not_exist.json")
```

- [ ] **Step 3: Run tests to verify failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k load_manifest`
Expected: FAIL with ImportError.

- [ ] **Step 4: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Manifest loader ===`
section):

```python
import json


@dataclasses.dataclass(frozen=True)
class ManifestNode:
    unique_id: str
    name: str
    resource_type: str
    original_file_path: str
    relation_name: str
    database: str
    schema: str
    alias: str
    depends_on: list[str]
    compiled_code: str | None


def load_manifest(path: Path) -> dict[str, ManifestNode]:
    if not path.exists():
        raise FileNotFoundError(
            f"manifest not found: {path}. "
            "Run `uv run dbt parse --project-dir src/dbt/kipptaf` first."
        )
    raw = json.loads(path.read_text())
    out: dict[str, ManifestNode] = {}
    for unique_id, node in raw.get("nodes", {}).items():
        out[unique_id] = ManifestNode(
            unique_id=unique_id,
            name=node["name"],
            resource_type=node["resource_type"],
            original_file_path=node["original_file_path"],
            relation_name=node.get("relation_name") or "",
            database=node.get("database") or "",
            schema=node.get("schema") or "",
            alias=node.get("alias") or node["name"],
            depends_on=node.get("depends_on", {}).get("nodes", []),
            compiled_code=node.get("compiled_code"),
        )
    return out


def mart_models(nodes: dict[str, ManifestNode]) -> list[ManifestNode]:
    return [
        n
        for n in nodes.values()
        if n.resource_type == "model"
        and n.original_file_path.startswith("models/marts/")
    ]
```

- [ ] **Step 5: Run tests to verify pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k load_manifest`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/
git commit -m "feat: load dbt manifest, filter to mart models"
```

---

## Task 5: BigQuery introspection

Two responsibilities:

1. **Per-dataset INFORMATION_SCHEMA cache** — for each unique
   `(database, schema)` pair across mart relations, query
   `INFORMATION_SCHEMA.COLUMNS` once. Returns
   `{(database, schema, table): {column_name: data_type}}`.
2. **Grain probe** — given a relation and a list of key columns, run
   `select count(*) as rows, count(distinct format("%T|%T|...", c1, c2, ...)) as keys from <relation>`
   and return `(rows, keys)`. NULL-safe per CLAUDE.md (`format("%T|...")`, never
   `concat()`).

This task uses the live `google-cloud-bigquery` client. Tests mock the client.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import MagicMock

from scripts.audit_marts_yaml import (
    BQClient,
    fetch_dataset_columns,
    grain_probe,
)


def _mock_bq_client(rows: list[dict]) -> MagicMock:
    client = MagicMock(spec=BQClient)
    job = MagicMock()
    job.result.return_value = [MagicMock(**r) for r in rows]
    client.query.return_value = job
    return client


def test_fetch_dataset_columns_groups_by_table() -> None:
    client = _mock_bq_client([
        {"table_name": "fct_sample", "column_name": "student_id", "data_type": "INT64"},
        {"table_name": "fct_sample", "column_name": "created_timestamp", "data_type": "DATETIME"},
        {"table_name": "dim_other", "column_name": "key", "data_type": "STRING"},
    ])
    result = fetch_dataset_columns(client, "teamster-332318", "kipptaf")
    assert result == {
        "fct_sample": {"student_id": "INT64", "created_timestamp": "DATETIME"},
        "dim_other": {"key": "STRING"},
    }


def test_grain_probe_returns_rows_and_distinct_keys() -> None:
    client = _mock_bq_client([{"rows": 100, "keys": 95}])
    rows, keys = grain_probe(
        client,
        "`teamster-332318`.`kipptaf`.`fct_sample`",
        ["student_id", "academic_year"],
    )
    assert (rows, keys) == (100, 95)
    sql = client.query.call_args[0][0]
    assert 'format("%T|%T", `student_id`, `academic_year`)' in sql
```

- [ ] **Step 2: Run tests to verify failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k 'fetch_dataset or grain_probe'`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === BigQuery introspection ===`
section):

```python
from typing import Protocol


class BQClient(Protocol):
    def query(self, sql: str): ...


def fetch_dataset_columns(
    client: BQClient, database: str, schema: str
) -> dict[str, dict[str, str]]:
    sql = f"""
    select table_name, column_name, data_type
    from `{database}`.`{schema}`.INFORMATION_SCHEMA.COLUMNS
    order by table_name, ordinal_position
    """
    out: dict[str, dict[str, str]] = {}
    for row in client.query(sql).result():
        out.setdefault(row.table_name, {})[row.column_name] = row.data_type
    return out


def grain_probe(
    client: BQClient, relation: str, key_columns: list[str]
) -> tuple[int, int]:
    fmt = "|".join(["%T"] * len(key_columns))
    cols = ", ".join(f"`{c}`" for c in key_columns)
    sql = (
        f'select count(*) as rows, '
        f'count(distinct format("{fmt}", {cols})) as keys '
        f"from {relation}"
    )
    row = next(iter(client.query(sql).result()))
    return row.rows, row.keys
```

- [ ] **Step 4: Run tests to verify pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k 'fetch_dataset or grain_probe'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: BigQuery dataset introspection + grain probe"
```

---

## Task 6: Upstream cast tracer

Given a column name, the mart's manifest node, and the manifest map: walk
`parent_map` recursively and record every `cast(<col> as <type>)` or
`safe_cast(<col> as <type>)` expression that touches this column on the way from
source to mart. Returns an ordered list of `(model_name, cast_expression)`
tuples — outermost (closest to mart) first.

The trace is informational. It does not need to perfectly track column renames;
the regex match is on the column name as it appears in the mart, and the trace
stops at the first ancestor where that name doesn't appear in the compiled SQL.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.audit_marts_yaml import trace_column_casts


def test_trace_column_casts_walks_parent_map() -> None:
    nodes = load_manifest(FIXTURE_DIR / "sample_manifest.json")
    casts = trace_column_casts(
        column="created_timestamp",
        from_node="model.kipptaf.fct_sample",
        nodes=nodes,
    )
    # The mart casts `created` to datetime aliasing as created_timestamp;
    # int_sample passes it through; stg_sample casts the source to datetime.
    assert ("fct_sample", "cast(created as datetime) as created_timestamp") in casts
```

- [ ] **Step 2: Run test, expect failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_trace_column_casts_walks_parent_map -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Upstream cast tracer ===`
section):

```python
_CAST_RE = re.compile(
    r"\b(?:safe_cast|cast)\s*\([^()]*?\)(?:\s+as\s+[\w_]+)?",
    re.IGNORECASE,
)


def trace_column_casts(
    column: str, from_node: str, nodes: dict[str, ManifestNode]
) -> list[tuple[str, str]]:
    """Walk parent_map recording cast(...) expressions touching `column`.

    Returns (model_name, cast_expression) pairs, mart-first.
    Stops descending when an ancestor's compiled SQL no longer mentions
    the column name verbatim.
    """
    out: list[tuple[str, str]] = []
    visited: set[str] = set()

    def walk(unique_id: str) -> None:
        if unique_id in visited:
            return
        visited.add(unique_id)
        node = nodes.get(unique_id)
        if node is None or not node.compiled_code:
            return
        if column not in node.compiled_code:
            return
        for match in _CAST_RE.finditer(node.compiled_code):
            expr = match.group(0)
            if column in expr:
                out.append((node.name, expr))
        for parent_id in node.depends_on:
            walk(parent_id)

    walk(from_node)
    return out
```

- [ ] **Step 4: Run test, expect pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_trace_column_casts_walks_parent_map -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: trace upstream cast expressions for a column"
```

---

## Task 7: Dagster asset-check status fetcher

Fetches current asset-check status for each mart's uniqueness test. Two
implementation options — pick **(a) GraphQL via gql** for simplicity:

- (a) Query Dagster Cloud GraphQL directly. Token is in the env
  (`DAGSTER_CLOUD_API_TOKEN` is set when running locally via the dagster-mcp
  launch flow; for the audit, the script reads it from the environment after the
  user has sourced it).
- (b) Use the dagster-plus-mcp Python package — but it's MCP-server-shaped,
  awkward to call from a script.

The fetcher takes a list of mart asset-keys (derived from
`kipptaf/<dir>/<model_name>` per the asset-key rule in CLAUDE.md — directories
`staging`/`intermediate` are stripped, but mart subdirs
`dimensions`/`facts`/`bridges` ARE part of the key). It returns
`{asset_key: {check_name: (status, timestamp)}}`.

If `DAGSTER_CLOUD_API_TOKEN` is unset → fail-hard with a clear error.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing test (mocking the gql transport)**

```python
from unittest.mock import patch

from scripts.audit_marts_yaml import (
    DagsterStatus,
    asset_key_for_mart_node,
    fetch_dagster_check_status,
)


def test_asset_key_includes_mart_subdir() -> None:
    nodes = load_manifest(FIXTURE_DIR / "sample_manifest.json")
    fct = nodes["model.kipptaf.fct_sample"]
    assert asset_key_for_mart_node(fct) == ["kipptaf", "facts", "fct_sample"]


def test_fetch_dagster_check_status_parses_response() -> None:
    fake_response = {
        "assetChecksOrError": {
            "checks": [
                {
                    "name": "unique_fct_sample_surrogate_key",
                    "executionForLatestMaterialization": {
                        "evaluation": {
                            "severity": "ERROR",
                            "successful": True,
                            "timestamp": 1714521240.0,
                        }
                    },
                }
            ]
        }
    }
    with patch("scripts.audit_marts_yaml._dagster_graphql") as gql:
        gql.return_value = fake_response
        result = fetch_dagster_check_status(
            asset_keys=[["kipptaf", "facts", "fct_sample"]],
            token="fake",
            deployment="prod",
        )
    assert result == {
        ("kipptaf", "facts", "fct_sample"): {
            "unique_fct_sample_surrogate_key": DagsterStatus(
                outcome="PASSED", timestamp=1714521240.0
            )
        }
    }
```

- [ ] **Step 2: Run tests, expect failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k dagster`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Dagster status fetcher ===`
section):

```python
import os


@dataclasses.dataclass(frozen=True)
class DagsterStatus:
    outcome: str  # PASSED | FAILED | WARN | NOT_RUN
    timestamp: float | None


_DAGSTER_QUERY = """
query AssetChecks($assetKey: AssetKeyInput!) {
  assetChecksOrError(assetKey: $assetKey) {
    ... on AssetChecks {
      checks {
        name
        executionForLatestMaterialization {
          evaluation { severity successful timestamp }
        }
      }
    }
  }
}
"""


def asset_key_for_mart_node(node: ManifestNode) -> list[str]:
    parts = Path(node.original_file_path).parts
    # parts: ('models', 'marts', 'facts'|'dimensions'|'bridges', '<file>.sql')
    subdir = parts[2]
    return ["kipptaf", subdir, node.name]


def _dagster_graphql(query: str, variables: dict, token: str, deployment: str) -> dict:
    from gql import Client, gql
    from gql.transport.requests import RequestsHTTPTransport

    transport = RequestsHTTPTransport(
        url=f"https://teamschools.dagster.cloud/{deployment}/graphql",
        headers={"Dagster-Cloud-Api-Token": token},
        timeout=30,
    )
    with Client(transport=transport) as session:
        return session.execute(gql(query), variable_values=variables)


def fetch_dagster_check_status(
    asset_keys: list[list[str]], token: str, deployment: str = "prod"
) -> dict[tuple[str, ...], dict[str, DagsterStatus]]:
    out: dict[tuple[str, ...], dict[str, DagsterStatus]] = {}
    for key in asset_keys:
        resp = _dagster_graphql(
            _DAGSTER_QUERY,
            {"assetKey": {"path": key}},
            token=token,
            deployment=deployment,
        )
        checks = resp.get("assetChecksOrError", {}).get("checks", [])
        per_check: dict[str, DagsterStatus] = {}
        for check in checks:
            execution = (check.get("executionForLatestMaterialization") or {}).get(
                "evaluation"
            )
            if execution is None:
                per_check[check["name"]] = DagsterStatus(outcome="NOT_RUN", timestamp=None)
                continue
            successful = execution["successful"]
            severity = execution["severity"]
            if successful:
                outcome = "PASSED"
            elif severity == "WARN":
                outcome = "WARN"
            else:
                outcome = "FAILED"
            per_check[check["name"]] = DagsterStatus(
                outcome=outcome, timestamp=execution["timestamp"]
            )
        out[tuple(key)] = per_check
    return out


def require_dagster_token() -> str:
    token = os.environ.get("DAGSTER_CLOUD_API_TOKEN")
    if not token:
        raise RuntimeError(
            "DAGSTER_CLOUD_API_TOKEN is not set. Source it via "
            "`op read 'op://...' > /tmp/dgst && export DAGSTER_CLOUD_API_TOKEN=$(cat /tmp/dgst)` "
            "or run from a terminal where the dagster-mcp-launch flow has set it."
        )
    return token
```

- [ ] **Step 4: Run tests, expect pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k dagster`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: fetch Dagster asset-check status for mart uniqueness tests"
```

---

## Task 8: Bucketing logic

Combines all signals into per-model `Finding` records:

- type-drift findings (one per mismatched column)
- grain findings: pass / suspect / broken / warn-masked
- status-mismatch findings (Dagster vs BQ probe disagree)
- missing-test findings (no uniqueness test declared on a mart)

The bucketer is pure — takes parsed YAML, BQ types, BQ probe results, Dagster
statuses; returns `list[Finding]`.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.audit_marts_yaml import Finding, bucket_model


def test_bucket_model_clean_pass() -> None:
    yaml_model = ParsedModel(
        name="fct_clean",
        yaml_path=Path("/tmp/fct_clean.yml"),
        column_data_types={"k": "string"},
        uniqueness_tests=[
            {"columns": ["k"], "severity": "error", "kind": "unique"}
        ],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"k": "STRING"},
        probe_results={("k",): (100, 100)},
        oversubset_results={},
        dagster_statuses={"unique_fct_clean_k": DagsterStatus("PASSED", 1.0)},
        upstream_traces={},
    )
    assert findings == []


def test_bucket_model_flags_type_drift() -> None:
    yaml_model = ParsedModel(
        name="fct_x",
        yaml_path=Path("/tmp/fct_x.yml"),
        column_data_types={"created_timestamp": "timestamp"},
        uniqueness_tests=[],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"created_timestamp": "DATETIME"},
        probe_results={},
        oversubset_results={},
        dagster_statuses={},
        upstream_traces={"created_timestamp": [("stg_x", "cast(created as datetime)")]},
    )
    drift = [f for f in findings if f.kind == "type_drift"]
    assert len(drift) == 1
    assert drift[0].column == "created_timestamp"
    assert drift[0].yaml_type == "timestamp"
    assert drift[0].bq_type == "datetime"


def test_bucket_model_flags_warn_masked_uniqueness() -> None:
    yaml_model = ParsedModel(
        name="fct_w",
        yaml_path=Path("/tmp/fct_w.yml"),
        column_data_types={"k": "string"},
        uniqueness_tests=[
            {"columns": ["k"], "severity": "warn", "kind": "unique"}
        ],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"k": "STRING"},
        probe_results={("k",): (100, 100)},
        oversubset_results={},
        dagster_statuses={},
        upstream_traces={},
    )
    assert any(f.kind == "warn_masked" for f in findings)


def test_bucket_model_flags_broken_when_probe_finds_dupes() -> None:
    yaml_model = ParsedModel(
        name="fct_b",
        yaml_path=Path("/tmp/fct_b.yml"),
        column_data_types={"k": "string"},
        uniqueness_tests=[
            {"columns": ["k"], "severity": "error", "kind": "unique"}
        ],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"k": "STRING"},
        probe_results={("k",): (100, 90)},  # 10 dupes
        oversubset_results={},
        dagster_statuses={"unique_fct_b_k": DagsterStatus("PASSED", 1.0)},
        upstream_traces={},
    )
    kinds = [f.kind for f in findings]
    assert "broken" in kinds
    assert "status_mismatch" in kinds  # Dagster says pass, probe says dupes


def test_bucket_model_flags_missing_uniqueness_test() -> None:
    yaml_model = ParsedModel(
        name="fct_m",
        yaml_path=Path("/tmp/fct_m.yml"),
        column_data_types={"k": "string"},
        uniqueness_tests=[],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"k": "STRING"},
        probe_results={},
        oversubset_results={},
        dagster_statuses={},
        upstream_traces={},
    )
    assert any(f.kind == "missing_test" for f in findings)


def test_bucket_model_flags_over_specified() -> None:
    yaml_model = ParsedModel(
        name="fct_o",
        yaml_path=Path("/tmp/fct_o.yml"),
        column_data_types={"a": "string", "b": "string"},
        uniqueness_tests=[
            {"columns": ["a", "b"], "severity": "error", "kind": "unique_combination_of_columns"}
        ],
    )
    findings = bucket_model(
        yaml_model=yaml_model,
        bq_columns={"a": "STRING", "b": "STRING"},
        probe_results={("a", "b"): (100, 100)},
        oversubset_results={("a",): (100, 100)},  # `a` alone is also unique
        dagster_statuses={},
        upstream_traces={},
    )
    assert any(f.kind == "suspect" and "over-specified" in f.detail for f in findings)
```

- [ ] **Step 2: Run tests, expect failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k bucket_model`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Bucketing ===` section):

```python
@dataclasses.dataclass(frozen=True)
class Finding:
    model: str
    kind: str  # type_drift|broken|suspect|warn_masked|status_mismatch|missing_test
    column: str | None
    yaml_type: str | None
    bq_type: str | None
    detail: str
    upstream_trace: list[tuple[str, str]] | None = None


def bucket_model(
    *,
    yaml_model: ParsedModel,
    bq_columns: dict[str, str],
    probe_results: dict[tuple[str, ...], tuple[int, int]],
    oversubset_results: dict[tuple[str, ...], tuple[int, int]],
    dagster_statuses: dict[str, DagsterStatus],
    upstream_traces: dict[str, list[tuple[str, str]]],
) -> list[Finding]:
    findings: list[Finding] = []

    # Type drift
    for col, yaml_type in yaml_model.column_data_types.items():
        bq_type = bq_columns.get(col)
        if bq_type is None:
            findings.append(
                Finding(
                    model=yaml_model.name,
                    kind="type_drift",
                    column=col,
                    yaml_type=yaml_type,
                    bq_type=None,
                    detail="column declared in YAML missing from BQ",
                )
            )
            continue
        if normalize_type(yaml_type) != normalize_type(bq_type):
            findings.append(
                Finding(
                    model=yaml_model.name,
                    kind="type_drift",
                    column=col,
                    yaml_type=normalize_type(yaml_type),
                    bq_type=normalize_type(bq_type),
                    detail=f"YAML `{yaml_type}` vs BQ `{bq_type}`",
                    upstream_trace=upstream_traces.get(col),
                )
            )

    # Missing uniqueness test
    if not yaml_model.uniqueness_tests:
        findings.append(
            Finding(
                model=yaml_model.name,
                kind="missing_test",
                column=None,
                yaml_type=None,
                bq_type=None,
                detail="model has no unique / unique_combination_of_columns test",
            )
        )

    # Per-test grain analysis
    for test in yaml_model.uniqueness_tests:
        cols = tuple(test["columns"])
        severity = test["severity"]

        # Warn-masked is its own finding regardless of probe outcome
        if severity == "warn":
            findings.append(
                Finding(
                    model=yaml_model.name,
                    kind="warn_masked",
                    column=None,
                    yaml_type=None,
                    bq_type=None,
                    detail=f"uniqueness test on {cols} is severity=warn",
                )
            )

        probe = probe_results.get(cols)
        if probe is None:
            continue
        rows, keys = probe
        probe_unique = rows == keys

        if not probe_unique:
            findings.append(
                Finding(
                    model=yaml_model.name,
                    kind="broken",
                    column=None,
                    yaml_type=None,
                    bq_type=None,
                    detail=f"BQ probe found {rows - keys} dup rows on {cols}",
                )
            )

        # Status mismatch: Dagster says PASSED but probe found dupes (or vice versa)
        relevant_statuses = [
            s for name, s in dagster_statuses.items() if yaml_model.name in name
        ]
        if relevant_statuses and probe is not None:
            outcomes = {s.outcome for s in relevant_statuses}
            if probe_unique and "FAILED" in outcomes:
                findings.append(
                    Finding(
                        model=yaml_model.name,
                        kind="status_mismatch",
                        column=None,
                        yaml_type=None,
                        bq_type=None,
                        detail="probe unique, Dagster FAILED",
                    )
                )
            if not probe_unique and "PASSED" in outcomes:
                findings.append(
                    Finding(
                        model=yaml_model.name,
                        kind="status_mismatch",
                        column=None,
                        yaml_type=None,
                        bq_type=None,
                        detail="probe found dupes, Dagster PASSED",
                    )
                )

        # Over-specified: a smaller subset is also unique
        if probe_unique and len(cols) > 1:
            for sub_cols, (sub_rows, sub_keys) in oversubset_results.items():
                if (
                    set(sub_cols) < set(cols)
                    and sub_rows == sub_keys
                    and sub_rows > 0
                ):
                    findings.append(
                        Finding(
                            model=yaml_model.name,
                            kind="suspect",
                            column=None,
                            yaml_type=None,
                            bq_type=None,
                            detail=(
                                f"declared {cols} unique, but {sub_cols} is also "
                                "unique → test over-specified"
                            ),
                        )
                    )
                    break

    return findings
```

- [ ] **Step 4: Run tests, expect pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v -k bucket_model`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: bucket findings into type_drift / broken / suspect / warn_masked / status_mismatch / missing_test"
```

---

## Task 9: Report renderer

Renders the populated finding set into the markdown + JSON formats specified in
the design doc. Pure function: takes the per-model record dict; returns
`(md_text, json_text)`.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`
- Modify: `tests/scripts/test_audit_marts_yaml.py`

- [ ] **Step 1: Write the failing test**

```python
from scripts.audit_marts_yaml import ModelReport, render_report


def test_render_report_emits_md_and_json() -> None:
    model_reports = [
        ModelReport(
            model="fct_y",
            materialization="table",
            contract="enforced",
            test_severity="error",
            dagster_status="PASSED",
            dagster_status_timestamp=1714521240.0,
            bq_probe_outcome="unique",
            grain_status="suspect",
            findings=[
                Finding(
                    model="fct_y",
                    kind="type_drift",
                    column="created_timestamp",
                    yaml_type="timestamp",
                    bq_type="datetime",
                    detail="YAML `timestamp` vs BQ `DATETIME`",
                    upstream_trace=[("stg_y", "cast(created as datetime)")],
                ),
                Finding(
                    model="fct_y",
                    kind="suspect",
                    column=None,
                    yaml_type=None,
                    bq_type=None,
                    detail="declared (student_id, year), but (student_id,) is also unique",
                ),
            ],
        ),
    ]
    md, js = render_report(model_reports, run_sha="abc1234")
    assert "# Mart YAML Audit Report" in md
    assert "fct_y" in md
    assert "abc1234" in md
    assert "Type drift: 1" in md
    parsed = json.loads(js)
    assert parsed["run_sha"] == "abc1234"
    assert len(parsed["models"]) == 1
    assert parsed["models"][0]["model"] == "fct_y"
```

- [ ] **Step 2: Run test, expect failure**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_render_report_emits_md_and_json -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `scripts/audit_marts_yaml.py` (in a `# === Report rendering ===`
section):

```python
@dataclasses.dataclass(frozen=True)
class ModelReport:
    model: str
    materialization: str
    contract: str
    test_severity: str
    dagster_status: str
    dagster_status_timestamp: float | None
    bq_probe_outcome: str
    grain_status: str
    findings: list[Finding]


def _summary_counts(reports: list[ModelReport]) -> dict[str, int]:
    counts = {
        "Pass": 0,
        "Suspect": 0,
        "Broken": 0,
        "Warn-masked": 0,
        "Status-mismatch": 0,
        "Type drift": 0,
        "Missing-test": 0,
    }
    for r in reports:
        if r.grain_status == "pass" and not r.findings:
            counts["Pass"] += 1
        for f in r.findings:
            if f.kind == "type_drift":
                counts["Type drift"] += 1
            elif f.kind == "broken":
                counts["Broken"] += 1
            elif f.kind == "suspect":
                counts["Suspect"] += 1
            elif f.kind == "warn_masked":
                counts["Warn-masked"] += 1
            elif f.kind == "status_mismatch":
                counts["Status-mismatch"] += 1
            elif f.kind == "missing_test":
                counts["Missing-test"] += 1
    return counts


def render_report(
    reports: list[ModelReport], run_sha: str
) -> tuple[str, str]:
    counts = _summary_counts(reports)
    summary_line = (
        f"Run: {run_sha} | Models scanned: {len(reports)} | "
        + " | ".join(f"{k}: {v}" for k, v in counts.items())
    )

    lines: list[str] = [
        "# Mart YAML Audit Report — 2026-05-01",
        "",
        summary_line,
        "",
        "## Summary table",
        "",
        "| Model | Materialization | Contract | Type drift | Grain status | "
        "Test severity | Dagster status | BQ probe | Difficulty | Disposition | Issue |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(reports, key=lambda x: x.model):
        type_drift_count = sum(1 for f in r.findings if f.kind == "type_drift")
        lines.append(
            f"| {r.model} | {r.materialization} | {r.contract} | "
            f"{type_drift_count} | {r.grain_status} | {r.test_severity} | "
            f"{r.dagster_status} | {r.bq_probe_outcome} | TBD | TBD | — |"
        )
    lines.extend(["", "## Per-model details", ""])
    for r in sorted(reports, key=lambda x: x.model):
        lines.append(f"### {r.model}")
        lines.append("")
        lines.append(f"- Test severity: {r.test_severity}")
        lines.append(
            f"- Dagster current status: {r.dagster_status} "
            f"({r.dagster_status_timestamp})"
        )
        lines.append(f"- BQ probe: {r.bq_probe_outcome}")
        lines.append(f"- Grain status: {r.grain_status}")
        if r.findings:
            lines.append("- Findings:")
            for f in r.findings:
                lines.append(f"  - **{f.kind}**: {f.detail}")
                if f.upstream_trace:
                    for model, expr in f.upstream_trace:
                        lines.append(f"    - upstream `{model}`: `{expr}`")
        lines.append("- Difficulty: TBD")
        lines.append("- Disposition: TBD")
        lines.append("")

    md = "\n".join(lines)

    js = json.dumps(
        {
            "run_sha": run_sha,
            "summary": counts,
            "models": [dataclasses.asdict(r) for r in reports],
        },
        indent=2,
        default=str,
    )
    return md, js
```

- [ ] **Step 4: Run test, expect pass**

Run:
`uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py::test_render_report_emits_md_and_json -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_marts_yaml.py tests/scripts/test_audit_marts_yaml.py
git commit -m "feat: render audit report as markdown + JSON"
```

---

## Task 10: Wire end-to-end in main()

Replace the `NotImplementedError` stub with the full audit pipeline:

1. Load manifest. Fail-hard if missing.
2. Build mart-model list. For each, parse its YAML.
3. Group mart relations by `(database, schema)`. For each group, fetch
   `INFORMATION_SCHEMA.COLUMNS`. Fail-hard on BQ error.
4. For each model with declared uniqueness tests, run grain probes (declared +
   smaller-subset). For models with no uniqueness test, run candidate probes on
   plausible single-column keys (any column whose name ends in `_key` or `_id`).
   Fail-hard on BQ error.
5. Compute asset keys, fetch Dagster statuses. Fail-hard on Dagster API error.
6. For each type-drift column, run the upstream cast tracer.
7. Build `ModelReport` per model from all signals (delegate to `bucket_model`).
8. Render report. Write `.md` and `.json`.
9. Print a one-line summary to stdout.

**Files:**

- Modify: `scripts/audit_marts_yaml.py`

- [ ] **Step 1: Implement the orchestration**

Replace the placeholder `main()` with:

```python
import subprocess
from collections import defaultdict


def _git_head_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _load_yaml_models() -> dict[str, ParsedModel]:
    out: dict[str, ParsedModel] = {}
    for yml in MARTS_DIR.rglob("*.yml"):
        for parsed in parse_mart_yaml(yml):
            out[parsed.name] = parsed
    return out


def _candidate_keys_for_unprobed(model: ManifestNode, bq_cols: dict[str, str]) -> list[tuple[str, ...]]:
    return [(c,) for c in bq_cols if c.endswith("_key") or c.endswith("_id")]


def main() -> None:
    description = (__doc__ or "").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.parse_args()

    print(f"Loading manifest from {MANIFEST_PATH}...")
    nodes = load_manifest(MANIFEST_PATH)
    marts = mart_models(nodes)
    print(f"  found {len(marts)} mart models")

    print(f"Loading YAMLs from {MARTS_DIR}...")
    yamls = _load_yaml_models()
    missing_yaml = [m.name for m in marts if m.name not in yamls]
    if missing_yaml:
        raise RuntimeError(f"mart manifest nodes missing YAML: {missing_yaml}")

    print("Initializing BigQuery client...")
    from google.cloud import bigquery
    bq = bigquery.Client()

    by_dataset: dict[tuple[str, str], list[ManifestNode]] = defaultdict(list)
    for m in marts:
        by_dataset[(m.database, m.schema)].append(m)

    print(f"Fetching INFORMATION_SCHEMA for {len(by_dataset)} dataset(s)...")
    bq_cols_by_table: dict[tuple[str, str, str], dict[str, str]] = {}
    for (db, schema), models_in_ds in by_dataset.items():
        cols = fetch_dataset_columns(bq, db, schema)
        for m in models_in_ds:
            if m.alias not in cols:
                raise RuntimeError(
                    f"mart {m.name} not materialized in {db}.{schema}.{m.alias} — "
                    "run `uv run dbt build --project-dir src/dbt/kipptaf --target prod` first"
                )
            bq_cols_by_table[(db, schema, m.alias)] = cols[m.alias]

    print("Running grain probes...")
    probe_results_by_model: dict[str, dict[tuple[str, ...], tuple[int, int]]] = {}
    oversubset_results_by_model: dict[str, dict[tuple[str, ...], tuple[int, int]]] = {}
    for m in marts:
        ym = yamls[m.name]
        relation = m.relation_name
        probes: dict[tuple[str, ...], tuple[int, int]] = {}
        oversubsets: dict[tuple[str, ...], tuple[int, int]] = {}

        if ym.uniqueness_tests:
            for test in ym.uniqueness_tests:
                cols = tuple(test["columns"])
                probes[cols] = grain_probe(bq, relation, list(cols))
                if len(cols) > 1:
                    for sub in [cols[:i] + cols[i+1:] for i in range(len(cols))]:
                        if sub:
                            oversubsets[sub] = grain_probe(bq, relation, list(sub))
        else:
            for cand in _candidate_keys_for_unprobed(m, bq_cols_by_table[(m.database, m.schema, m.alias)]):
                probes[cand] = grain_probe(bq, relation, list(cand))

        probe_results_by_model[m.name] = probes
        oversubset_results_by_model[m.name] = oversubsets

    print("Fetching Dagster asset-check statuses...")
    token = require_dagster_token()
    asset_keys = [asset_key_for_mart_node(m) for m in marts]
    statuses = fetch_dagster_check_status(asset_keys, token=token)

    print("Tracing upstream casts for type drifts...")
    upstream_traces_by_model: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for m in marts:
        ym = yamls[m.name]
        bq_cols = bq_cols_by_table[(m.database, m.schema, m.alias)]
        traces: dict[str, list[tuple[str, str]]] = {}
        for col, yt in ym.column_data_types.items():
            bt = bq_cols.get(col)
            if bt and normalize_type(yt) != normalize_type(bt):
                traces[col] = trace_column_casts(col, m.unique_id, nodes)
        upstream_traces_by_model[m.name] = traces

    print("Bucketing findings...")
    model_reports: list[ModelReport] = []
    for m in marts:
        ym = yamls[m.name]
        bq_cols = bq_cols_by_table[(m.database, m.schema, m.alias)]
        probes = probe_results_by_model[m.name]
        oversubsets = oversubset_results_by_model[m.name]
        per_model_statuses = statuses.get(tuple(asset_key_for_mart_node(m)), {})
        traces = upstream_traces_by_model[m.name]

        findings = bucket_model(
            yaml_model=ym,
            bq_columns=bq_cols,
            probe_results=probes,
            oversubset_results=oversubsets,
            dagster_statuses=per_model_statuses,
            upstream_traces=traces,
        )

        # Roll up into a ModelReport
        severities = {t["severity"] for t in ym.uniqueness_tests}
        test_severity = (
            "warn" if "warn" in severities else "error" if severities else "—"
        )
        dagster_outcomes = {s.outcome for s in per_model_statuses.values()}
        dagster_status = (
            "FAILED" if "FAILED" in dagster_outcomes
            else "WARN" if "WARN" in dagster_outcomes
            else "PASSED" if "PASSED" in dagster_outcomes
            else "—"
        )
        timestamps = [s.timestamp for s in per_model_statuses.values() if s.timestamp]
        ts = max(timestamps) if timestamps else None

        any_broken = any(f.kind == "broken" for f in findings)
        any_suspect = any(f.kind == "suspect" for f in findings)
        bq_probe_outcome = (
            "dupes" if any_broken
            else "over-spec" if any_suspect
            else "unique" if probes
            else "—"
        )
        grain_status = (
            "broken" if any_broken
            else "suspect" if any_suspect
            else "warn-masked" if any(f.kind == "warn_masked" for f in findings)
            else "missing-test" if any(f.kind == "missing_test" for f in findings)
            else "pass"
        )

        # Materialization + contract come from manifest.json `config`. We
        # don't carry those on ManifestNode yet — read directly:
        node_config = json.loads(MANIFEST_PATH.read_text())["nodes"][m.unique_id]["config"]
        materialization = node_config.get("materialized", "view")
        contract_enforced = node_config.get("contract", {}).get("enforced", False)

        model_reports.append(
            ModelReport(
                model=m.name,
                materialization=materialization,
                contract="enforced" if contract_enforced else "none",
                test_severity=test_severity,
                dagster_status=dagster_status,
                dagster_status_timestamp=ts,
                bq_probe_outcome=bq_probe_outcome,
                grain_status=grain_status,
                findings=findings,
            )
        )

    print(f"Rendering report to {REPORT_MD}...")
    md, js = render_report(model_reports, run_sha=_git_head_sha())
    REPORT_MD.write_text(md)
    REPORT_JSON.write_text(js)

    counts = _summary_counts(model_reports)
    print("Done. " + " | ".join(f"{k}: {v}" for k, v in counts.items()))
```

- [ ] **Step 2: Run unit tests, confirm still passing**

Run: `uv run --with pytest pytest tests/scripts/test_audit_marts_yaml.py -v`
Expected: all PASS (the orchestration is integration-only — no new unit tests
required).

- [ ] **Step 3: Commit**

```bash
git add scripts/audit_marts_yaml.py
git commit -m "feat: wire mart YAML audit end-to-end in main()"
```

---

## Task 11: Update script catalog

**Files:**

- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Add a row to the script catalog**

Insert under the existing table (alphabetical position — between `dbt-yaml.py`
and `enrich_staging_descriptions.py`):

```text
| `audit_marts_yaml.py`                         | Audit mart YAMLs against BigQuery + Dagster (#3678)                                         |
```

- [ ] **Step 2: Commit**

```bash
git add scripts/CLAUDE.md
git commit -m "docs: register audit_marts_yaml.py in scripts catalog"
```

---

## Task 12: First real run + report commit

This is the integration moment. The script runs against live BigQuery and
Dagster. If anything fails-hard, fix the underlying issue and re-run from
scratch — do not commit a partial report.

**Files:**

- Create (via script):
  `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md`
- Create (via script):
  `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json`

- [ ] **Step 1: Parse the manifest in prod target**

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --target prod
```

Expected: `target/manifest.json` written, no errors.

- [ ] **Step 2: Source the Dagster Cloud token**

```bash
export DAGSTER_CLOUD_API_TOKEN=$(op read 'op://Engineering/dagster-cloud-api-token-codespaces/credential')
```

(Adjust the `op://` path if your 1Password layout differs — it's whatever the
user already uses.)

- [ ] **Step 3: Run the audit**

```bash
uv run scripts/audit_marts_yaml.py
```

Expected output ends with:
`Done. Pass: N | Suspect: M | Broken: K | Warn-masked: W | Status-mismatch: S | Type drift: D | Missing-test: T`.

If any fail-hard error fires:

- BQ unreachable → check ADC:
  `gcloud auth application-default print-access-token`
- Manifest missing column → re-run `dbt parse` and check `target/manifest.json`
- Mart not materialized → run
  `uv run dbt build --project-dir src/dbt/kipptaf --target prod --select <model>+`
- Dagster API failure → check the GraphQL URL host (deployment slug) matches
  your account

- [ ] **Step 4: Verify the report files**

```bash
ls -la docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.{md,json}
head -30 docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md
```

Expected: both files present, summary line at top of `.md` matches the stdout
summary.

- [ ] **Step 5: Spot-check a known case**

`fct_job_candidate_applications` was the trigger model for this audit (#3643
Task 18). Verify it appears in the report. With the YAML already corrected
inline by Task 18, expect zero type-drift findings on that model now — but the
grain probe should still execute.

```bash
grep -A 15 "^### fct_job_candidate_applications" docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md
```

- [ ] **Step 6: Commit the report**

```bash
git add docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json
git commit -m "chore: initial mart YAML audit report (#3678)"
```

- [ ] **Step 7: Push and open the PR (audit-only)**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
git push
```

Stop here. Do **not** open the PR yet — Task 13 covers triage, which precedes PR
creation.

---

## Task 13: Triage gate (manual; this plan stops here)

This task is a checkpoint, not an implementation step. The fix pass that follows
depends on what's in the report and can't be planned in advance.

- [ ] **Step 1: Present the report to the user**

State counts. Surface any high-signal findings (failing Dagster tests, status
mismatches, broken grains).

- [ ] **Step 2: Manual triage pass**

For each finding row in the report, fill in `Difficulty` (trivial / moderate /
hard, plus one-line rationale) and `Disposition` (fix-in-this-pr / defer). Use
the `## Per-model details` section to walk findings; update the
`## Summary table`'s columns accordingly.

This step is a conversation with the user, not a script. The output is a
hand-edited report file.

- [ ] **Step 3: Commit triaged report**

```bash
git add docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md
git commit -m "chore: triage mart YAML audit findings (#3678)"
```

- [ ] **Step 4: Write a fix-pass plan**

Use the writing-plans skill again. The fix-pass plan enumerates one task per
`fix-in-this-pr` finding and one task per defer cluster (which produces a
follow-up issue).

The fix-pass plan's terminal state: PR opened with audit + fixes + linked
issues.

---

## Acceptance for this plan

- `scripts/audit_marts_yaml.py` exists, has unit-test coverage for all pure
  functions, runs end-to-end without error against the live environment.
- `docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md` and `.json` are
  committed and contain a populated finding set.
- A fix-pass plan exists (written after triage) that picks up where this plan
  ends.
