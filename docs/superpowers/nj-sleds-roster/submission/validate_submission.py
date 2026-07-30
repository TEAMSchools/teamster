"""Validation gate for the NJ SLEDS student course submission.

Exits non-zero if any handbook or parity rule fails. Prints aggregate counts
only - never row-level values, which are PII.
"""

import sys

from google.cloud import bigquery
from submission_query import SUBMISSION_SQL

PROJECT = "teamster-332318"

EXPECTED_EXTRACT_ROWS = {"newark": 33150, "camden": 10343}
EXPECTED_BAND_ROWS = {
    ("newark", "HS"): 10695,
    ("newark", "MS"): 10746,
    ("newark", "OUT"): 11709,
    ("camden", "HS"): 3648,
    ("camden", "MS"): 3857,
    ("camden", "OUT"): 2838,
}


def _rows(client, sql):
    return list(client.query(sql).result())


def check_row_parity(client):
    """Every extract row appears exactly once. No fan-out, no loss."""
    failures = []
    # trunk-ignore(bandit/B608): SUBMISSION_SQL is a local module constant, not user input
    sql = f"""
    select region, count(*) as n
    from ({SUBMISSION_SQL})
    group by region
    """
    actual = {r.region: r.n for r in _rows(client, sql)}
    for region, expected in EXPECTED_EXTRACT_ROWS.items():
        got = actual.get(region, 0)
        if got != expected:
            failures.append(f"row parity {region}: expected {expected}, got {got}")
    return failures


def check_band_counts(client):
    """Band classification matches the spec exactly."""
    failures = []
    # trunk-ignore(bandit/B608): SUBMISSION_SQL is a local module constant, not user input
    sql = f"""
    select region, grade_band, count(*) as n
    from ({SUBMISSION_SQL})
    group by region, grade_band
    """
    actual = {(r.region, r.grade_band): r.n for r in _rows(client, sql)}
    for key, expected in EXPECTED_BAND_ROWS.items():
        got = actual.get(key, 0)
        if got != expected:
            failures.append(
                f"band count {key[0]}/{key[1]}: expected {expected}, got {got}"
            )
    return failures


CHECKS = [check_row_parity, check_band_counts]


def run_checks(client):
    failures = []
    for check in CHECKS:
        failures.extend(check(client))
    return failures


def main():
    client = bigquery.Client(project=PROJECT)
    failures = run_checks(client)
    if failures:
        print(f"FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASSED ({len(CHECKS)} check group(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
