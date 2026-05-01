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
import dataclasses
import json
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MARTS_DIR = REPO_ROOT / "src/dbt/kipptaf/models/marts"
MANIFEST_PATH = REPO_ROOT / "src/dbt/kipptaf/target/manifest.json"
# When running from a worktree, the worktree's manifest is usually missing —
# fall back to the main repo's manifest.
MAIN_MANIFEST_PATH = Path("/workspaces/teamster/src/dbt/kipptaf/target/manifest.json")
OP_TOKEN_PATH = Path("/etc/secret-volume/.op-token")
# trunk-ignore(bandit/B105): 1Password reference, not a credential value
DAGSTER_TOKEN_OP_REF = "op://Data Team/Dagster Cloud Agent/credential"
REPORT_MD = REPO_ROOT / "docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.md"
REPORT_JSON = (
    REPO_ROOT / "docs/superpowers/specs/2026-05-01-mart-yaml-audit-report.json"
)


def _git_head_sha() -> str:
    # trunk-ignore(bandit/B603,bandit/B607): hardcoded git command, no user input
    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _load_yaml_models() -> dict[str, ParsedModel]:
    out: dict[str, ParsedModel] = {}
    for yml in MARTS_DIR.rglob("*.yml"):
        for parsed in parse_mart_yaml(yml):
            out[parsed.name] = parsed
    return out


def _candidate_keys_for_unprobed(
    bq_cols: dict[str, str],
) -> list[tuple[str, ...]]:
    return [(c,) for c in bq_cols if c.endswith("_key") or c.endswith("_id")]


def _default_manifest() -> Path:
    if MANIFEST_PATH.exists():
        return MANIFEST_PATH
    if MAIN_MANIFEST_PATH.exists():
        return MAIN_MANIFEST_PATH
    return MANIFEST_PATH


def main() -> None:
    description = (__doc__ or "").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_default_manifest(),
        help="path to dbt manifest.json (defaults to worktree, falls back to main repo)",
    )
    args = parser.parse_args()

    print(f"Loading manifest from {args.manifest}...")
    nodes = load_manifest(args.manifest)
    raw_manifest = json.loads(args.manifest.read_text())
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
                    for sub in [cols[:i] + cols[i + 1 :] for i in range(len(cols))]:
                        if sub:
                            oversubsets[sub] = grain_probe(bq, relation, list(sub))
        else:
            for cand in _candidate_keys_for_unprobed(
                bq_cols_by_table[(m.database, m.schema, m.alias)]
            ):
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

        severities = {t["severity"] for t in ym.uniqueness_tests}
        test_severity = (
            "warn" if "warn" in severities else "error" if severities else "—"
        )
        dagster_outcomes = {s.outcome for s in per_model_statuses.values()}
        dagster_status = (
            "FAILED"
            if "FAILED" in dagster_outcomes
            else "WARN"
            if "WARN" in dagster_outcomes
            else "PASSED"
            if "PASSED" in dagster_outcomes
            else "—"
        )
        timestamps = [s.timestamp for s in per_model_statuses.values() if s.timestamp]
        ts = max(timestamps) if timestamps else None

        any_broken = any(f.kind == "broken" for f in findings)
        any_suspect = any(f.kind == "suspect" for f in findings)
        bq_probe_outcome = (
            "dupes"
            if any_broken
            else "over-spec"
            if any_suspect
            else "unique"
            if probes
            else "—"
        )
        grain_status = (
            "broken"
            if any_broken
            else "suspect"
            if any_suspect
            else "warn-masked"
            if any(f.kind == "warn_masked" for f in findings)
            else "missing-test"
            if any(f.kind == "missing_test" for f in findings)
            else "pass"
        )

        node_config = raw_manifest["nodes"][m.unique_id]["config"]
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


# === YAML parsing ===


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

_TYPE_PARAM_RE = re.compile(r"\s*\([^)]*\)\s*$")

# BigQuery accepts legacy spellings as synonyms — collapse to the canonical
# standard SQL form so the audit doesn't flag them as drift.
# https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types
_TYPE_SYNONYMS = {
    "boolean": "bool",
    "integer": "int64",
    "int": "int64",
    "smallint": "int64",
    "tinyint": "int64",
    "byteint": "int64",
    "float": "float64",
    "decimal": "numeric",
    "bigdecimal": "bignumeric",
}


def normalize_type(t: str) -> str:
    base = _TYPE_PARAM_RE.sub("", t.strip()).lower()
    return _TYPE_SYNONYMS.get(base, base)


# === Manifest loader ===


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


class BQJob(Protocol):
    def result(self) -> Iterable[Any]: ...


class BQClient(Protocol):
    def query(self, query: str) -> BQJob: ...


def fetch_dataset_columns(
    client: BQClient, database: str, schema: str
) -> dict[str, dict[str, str]]:
    # trunk-ignore(bandit/B608): inputs are dbt manifest dataset names, not user input
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
        # trunk-ignore(bandit/B608): inputs are mart relation + column names from manifest
        f"select count(*) as n_rows, "
        f'count(distinct format("{fmt}", {cols})) as n_keys '
        f"from {relation}"
    )
    row = next(iter(client.query(sql).result()))
    return row.n_rows, row.n_keys


# === Upstream cast tracer ===

# === Dagster status fetcher ===


@dataclasses.dataclass(frozen=True)
class DagsterStatus:
    outcome: str  # PASSED | FAILED | WARN | NOT_RUN
    timestamp: float | None


_DAGSTER_QUERY = """
query AssetChecks($assetKey: AssetKeyInput!) {
  assetNodeOrError(assetKey: $assetKey) {
    ... on AssetNode {
      assetChecksOrError {
        ... on AssetChecks {
          checks {
            name
            executionForLatestMaterialization {
              evaluation { severity success timestamp }
            }
          }
        }
      }
    }
  }
}
"""


def asset_key_for_mart_node(node: ManifestNode) -> list[str]:
    # Asset key collapses the facts/dimensions/bridges subdir into just `marts`,
    # mirroring the staging/intermediate stripping pattern. See CLAUDE.md.
    return ["kipptaf", "marts", node.name]


def _dagster_graphql(query: str, variables: dict, token: str, deployment: str) -> dict:
    from gql import Client, gql
    from gql.transport.requests import RequestsHTTPTransport

    transport = RequestsHTTPTransport(
        url=f"https://kipptaf.dagster.cloud/{deployment}/graphql",
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
        node = resp.get("assetNodeOrError") or {}
        checks = (node.get("assetChecksOrError") or {}).get("checks", [])
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
            successful = execution["success"]
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
    if token:
        return token

    if not OP_TOKEN_PATH.exists():
        raise RuntimeError(
            f"DAGSTER_CLOUD_API_TOKEN unset and {OP_TOKEN_PATH} missing. "
            "Rebuild Codespace to re-provision the 1Password token."
        )
    op_token = OP_TOKEN_PATH.read_text().strip()
    # trunk-ignore(bandit/B105): sentinel value from postCreate.sh, not a credential
    if not op_token or op_token == "revoked-after-injection":
        raise RuntimeError(
            f"OP token in {OP_TOKEN_PATH} is empty or revoked. "
            "Rebuild Codespace to re-provision."
        )
    # trunk-ignore(bandit/B603,bandit/B607): hardcoded `op` invocation, no user input
    result = subprocess.run(
        ["op", "read", DAGSTER_TOKEN_OP_REF],
        capture_output=True,
        text=True,
        env={**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": op_token},
        check=True,
    )
    return result.stdout.strip()


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
        # trunk-ignore(bandit/B105): false positive on counter dict literals
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


if __name__ == "__main__":
    main()
