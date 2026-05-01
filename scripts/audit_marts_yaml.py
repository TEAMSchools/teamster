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
