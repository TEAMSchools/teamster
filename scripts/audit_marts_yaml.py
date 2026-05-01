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

# === Dagster status fetcher ===

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
                per_check[check["name"]] = DagsterStatus(
                    outcome="NOT_RUN", timestamp=None
                )
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


# === Upstream cast tracer ===

_CAST_RE = re.compile(
    r"\b(?:safe_cast|cast)\s*\([^()]*?\)(?:\s+as\s+[\w_]+)?",
    re.IGNORECASE,
)


# === Bucketing ===


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
                if set(sub_cols) < set(cols) and sub_rows == sub_keys and sub_rows > 0:
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


# === Report rendering ===


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


def render_report(reports: list[ModelReport], run_sha: str) -> tuple[str, str]:
    counts = _summary_counts(reports)
    summary_line = f"Run: {run_sha} | Models scanned: {len(reports)} | " + " | ".join(
        f"{k}: {v}" for k, v in counts.items()
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
