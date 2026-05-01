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
REPORT_JSON = (
    REPO_ROOT / "docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json"
)


def main() -> None:
    description = (__doc__ or "").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.parse_args()
    raise NotImplementedError("audit not wired up yet")


if __name__ == "__main__":
    main()


# === YAML parsing ===

import dataclasses
from typing import Any, Protocol

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


# === Type normalization ===

import re

_TYPE_PARAM_RE = re.compile(r"\s*\([^)]*\)\s*$")


def normalize_type(t: str) -> str:
    return _TYPE_PARAM_RE.sub("", t.strip()).lower()


# === Manifest loader ===

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


# === BigQuery introspection ===


from collections.abc import Iterable


class BQJob(Protocol):
    def result(self) -> Iterable[Any]: ...


class BQClient(Protocol):
    def query(self, sql: str) -> BQJob: ...


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
        f"select count(*) as rows, "
        f'count(distinct format("{fmt}", {cols})) as keys '
        f"from {relation}"
    )
    row = next(iter(client.query(sql).result()))
    return row.rows, row.keys


# === Upstream cast tracer ===

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
