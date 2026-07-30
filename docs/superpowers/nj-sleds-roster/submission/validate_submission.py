"""Validation gate for the NJ SLEDS student course submission.

Exits non-zero if any handbook or parity rule fails. Prints aggregate counts
only - never row-level values, which are PII.
"""

import sys

from google.cloud import bigquery
from submission_query import ALPHA_GRADE_DOMAIN, SUBMISSION_COLUMNS, SUBMISSION_SQL

PROJECT = "teamster-332318"

BASE_TABLES = {
    "newark": "teamster-332318.cokafor.stg_student_extract_newark",
    "camden": "teamster-332318.cokafor.stg_student_extract_camden",
}

PASS_THROUGH_COLUMNS = [
    c for c in SUBMISSION_COLUMNS if c not in ("AlphaGradeEarned", "CreditsEarned")
]

# Per-cycle baseline, not a derivable truth: band composition legitimately
# shifts between extract pulls (enrollment, course, and span changes), and
# the band logic is exactly what this baseline cross-checks, so deriving it
# would be circular. Re-measure by hand whenever a new extract is loaded (see
# the README's re-baseline step). Measured from the 2026-07-29 extract.
BASELINE_BAND_ROWS = {
    ("newark", "HS"): 10695,
    ("newark", "MS"): 10746,
    ("newark", "OUT"): 11709,
    ("camden", "HS"): 3648,
    ("camden", "MS"): 3638,
    ("camden", "OUT"): 3057,
}


def _rows(client, sql):
    return list(client.query(sql).result())


def base_table_row_count(client, region):
    """Fresh row count of the region's extract base table.

    Shared by check_row_parity (the fan-out gate) and build_submission's
    export_region (the post-gate re-verification of what was actually
    written), so both compare against the same live number instead of two
    copies of similar SQL drifting apart.
    """
    table = BASE_TABLES[region]
    # trunk-ignore(bandit/B608): table is drawn from the local BASE_TABLES constant, not user input
    sql_text = f"select count(*) as n from `{table}`"
    return _rows(client, sql_text)[0].n


def check_row_parity(client, sql=SUBMISSION_SQL):
    """Every extract row appears exactly once, matching its base table.

    Compares against each base table's own count, queried fresh, rather than
    a frozen literal - so this stays a true fan-out guard across extract
    reloads instead of asserting a snapshot that goes stale next cycle.
    """
    failures = []
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select region, count(*) as n
    from ({sql})
    group by region
    """
    actual = {r.region: r.n for r in _rows(client, sql_text)}
    for region in BASE_TABLES:
        expected = base_table_row_count(client, region)
        got = actual.get(region, 0)
        if got != expected:
            failures.append(
                f"row parity {region}: view {got}, base table {expected} "
                "(join fanned out)"
            )
    return failures


def check_band_counts(client, sql=SUBMISSION_SQL):
    """Band classification matches the spec exactly."""
    failures = []
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select region, grade_band, count(*) as n
    from ({sql})
    group by region, grade_band
    """
    actual = {(r.region, r.grade_band): r.n for r in _rows(client, sql_text)}
    for key, expected in BASELINE_BAND_ROWS.items():
        got = actual.get(key, 0)
        if got != expected:
            failures.append(
                f"band count {key[0]}/{key[1]}: expected {expected}, got {got}"
            )
    return failures


# Per-cycle baseline, same caveat as BASELINE_BAND_ROWS above - re-measure by
# hand whenever a new extract is loaded. Measured from the 2026-07-29 extract.
BASELINE_STORED_COVERAGE = {
    ("newark", "HS"): 10675,
    ("newark", "MS"): 10682,
    ("camden", "HS"): 3616,
    ("camden", "MS"): 3633,
}


def check_stored_coverage(client, sql=SUBMISSION_SQL):
    """Stored Y1 grades cover the in-scope bands at the measured rate.

    Counts are a floor, not an equality: a re-pulled extract may match more
    rows. A drop signals a broken join.
    """
    failures = []
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select region, grade_band, countif(stored_letter is not null) as matched
    from ({sql})
    group by region, grade_band
    """
    actual = {(r.region, r.grade_band): r.matched for r in _rows(client, sql_text)}
    for key, floor in BASELINE_STORED_COVERAGE.items():
        got = actual.get(key, 0)
        if got < floor:
            failures.append(
                f"stored coverage {key[0]}/{key[1]}: expected at least "
                f"{floor}, got {got}"
            )
    return failures


def check_no_stored_conflicts(client, sql=SUBMISSION_SQL):
    """No student-section carries two different stored Y1 letters or credits."""
    failures = []
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select
        countif(n_stored_letters > 1) as letter_conflicts,
        countif(n_stored_credits > 1) as credit_conflicts
    from ({sql})
    """
    row = _rows(client, sql_text)[0]
    if row.letter_conflicts:
        failures.append(
            f"{row.letter_conflicts} row(s) have conflicting stored Y1 letter grades"
        )
    if row.credit_conflicts:
        failures.append(
            f"{row.credit_conflicts} row(s) have conflicting stored Y1 earned credits"
        )
    return failures


def check_no_live_conflicts(client, sql=SUBMISSION_SQL):
    """A conflicted live grade is never emitted as the resolved value.

    Live reporting terms legitimately disagree on tens of thousands of rows -
    several term types close on the same date. That is not an error, because
    on any row with a stored grade the live value is never consulted. The
    invariant that matters is narrower: when live terms disagree, the guard
    must null the value rather than pick one, so grade_source can never be
    'live' on a conflicted row.
    """
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select count(*) as n
    from ({sql})
    where n_live_letters > 1 and grade_source = 'live'
    """
    n = _rows(client, sql_text)[0].n
    if n:
        return [f"{n} row(s) emitted a conflicted live grade"]
    return []


def check_live_fills_only_gaps(client, sql=SUBMISSION_SQL):
    """Live grades never override a stored grade."""
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select count(*) as n
    from ({sql})
    where
        stored_letter is not null
        and live_letter is not null
        and stored_letter != live_letter
        and grade_source = 'live'
    """
    n = _rows(client, sql_text)[0].n
    if n:
        return [f"{n} row(s) took a live grade over a stored grade"]
    return []


def check_alpha_grade_domain(client, sql=SUBMISSION_SQL):
    """Every emitted letter grade is one of the 18 legal handbook values."""
    domain = ", ".join(f"'{g}'" for g in sorted(ALPHA_GRADE_DOMAIN))
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select count(*) as n
    from ({sql})
    where AlphaGradeEarned is not null
      and AlphaGradeEarned not in ({domain})
    """
    n = _rows(client, sql_text)[0].n
    if n:
        return [f"{n} row(s) carry an out-of-domain AlphaGradeEarned"]
    return []


def check_in_scope_rows_have_grades(client, sql=SUBMISSION_SQL):
    """No in-scope row is left without a letter grade."""
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select region, grade_band, count(*) as n
    from ({sql})
    where grade_band in ('HS', 'MS') and AlphaGradeEarned is null
    group by region, grade_band
    """
    return [
        f"{r.n} in-scope row(s) in {r.region}/{r.grade_band} have no grade"
        for r in _rows(client, sql_text)
    ]


def check_out_of_scope_rows_blank(client, sql=SUBMISSION_SQL):
    """Scope-boundary guard.

    OUT-band rows carry no grade and no credit. MS-band rows are in scope for
    AlphaGradeEarned only (see the spec's scope table) and must carry no
    CreditsEarned.
    """
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select
        countif(
            grade_band = 'OUT'
            and (AlphaGradeEarned is not null or CreditsEarned is not null)
        ) as out_of_scope_graded,
        countif(grade_band = 'MS' and CreditsEarned is not null) as ms_has_credit
    from ({sql})
    """
    r = _rows(client, sql_text)[0]
    failures = []
    if r.out_of_scope_graded:
        failures.append(
            f"{r.out_of_scope_graded} out-of-scope row(s) were given a grade or credit"
        )
    if r.ms_has_credit:
        failures.append(
            f"{r.ms_has_credit} MS-band row(s) were given a CreditsEarned value"
        )
    return failures


def check_credits_earned(client, sql=SUBMISSION_SQL):
    """CreditsEarned is present, 3-decimal, in range, and within available."""
    # trunk-ignore(bandit/B608): sql defaults to the local module constant, not user input
    sql_text = f"""
    select
        countif(grade_band = 'HS' and CreditsEarned is null) as missing,
        countif(
            CreditsEarned is not null
            and not regexp_contains(CreditsEarned, r'^[0-9]+\\.[0-9]{{3}}$')
        ) as malformed,
        countif(
            CreditsEarned is not null
            and safe_cast(CreditsEarned as float64) not between 0.0 and 35.0
        ) as out_of_range,
        countif(
            CreditsEarned is not null
            and safe_cast(CreditsEarned as float64)
                > safe_cast(nullif(AvailableCredit, '') as float64)
        ) as over_available
    from ({sql})
    """
    r = _rows(client, sql_text)[0]
    failures = []
    if r.missing:
        failures.append(f"{r.missing} HS row(s) missing CreditsEarned")
    if r.malformed:
        failures.append(f"{r.malformed} row(s) CreditsEarned not 3-decimal formatted")
    if r.out_of_range:
        failures.append(f"{r.out_of_range} row(s) CreditsEarned outside 0.000-35.000")
    if r.over_available:
        failures.append(
            f"{r.over_available} row(s) CreditsEarned exceeds AvailableCredit"
        )
    return failures


def check_pass_through_columns_unchanged(client, sql=SUBMISSION_SQL):
    """The 23 non-written columns are byte-identical to the base tables.

    This is the load-bearing narrowing constraint of the whole exception to
    source-fix-only: only AlphaGradeEarned and CreditsEarned may ever differ
    from the native extract. EXCEPT DISTINCT in both directions catches drift
    either way - a view row with a pass-through value not found in any base
    row, or a base row whose pass-through values are missing from the view.
    """
    cols = ", ".join(f"`{c}`" for c in PASS_THROUGH_COLUMNS)
    tables = BASE_TABLES.values()
    # trunk-ignore(bandit/B608): cols/tables draw from local module constants, not user input
    base_union = " union all ".join(f"select {cols} from `{t}`" for t in tables)
    # trunk-ignore(bandit/B608): cols/table draw from local module constants, not user input
    view_extra_sql = f"""
    select count(*) as n
    from (
        select {cols} from ({sql})
        except distinct
        ({base_union})
    )
    """
    # trunk-ignore(bandit/B608): cols/table draw from local module constants, not user input
    base_extra_sql = f"""
    select count(*) as n
    from (
        ({base_union})
        except distinct
        select {cols} from ({sql})
    )
    """
    failures = []
    view_extra = _rows(client, view_extra_sql)[0].n
    if view_extra:
        failures.append(
            f"{view_extra} view row(s) have a pass-through column combination "
            "not found in either base table"
        )
    base_extra = _rows(client, base_extra_sql)[0].n
    if base_extra:
        failures.append(
            f"{base_extra} base-table row(s) have a pass-through column "
            "combination missing from the view"
        )
    return failures


CHECKS = [
    check_row_parity,
    check_band_counts,
    check_stored_coverage,
    check_no_stored_conflicts,
    check_no_live_conflicts,
    check_live_fills_only_gaps,
    check_alpha_grade_domain,
    check_in_scope_rows_have_grades,
    check_out_of_scope_rows_blank,
    check_credits_earned,
    check_pass_through_columns_unchanged,
]


def run_checks(client):
    failures = []
    for check in CHECKS:
        failures.extend(check(client))
    return failures


def self_test(client):
    """Prove the real checks fire on injected defects. Mutates SQL in memory.

    Each block calls the ACTUAL check function against the mutated SQL, so
    widening a check's domain or weakening its predicate makes this
    self-test fail. A self-test that re-implements the check's own predicate
    would keep passing with the check's logic gutted, which is worse than no
    self-test at all - it manufactures false confidence.

    This does not prove every check still runs as part of the gate: it calls
    two check functions directly by name, so it covers 2 of the 11 check
    groups in CHECKS.
    """
    failures = []

    # An out-of-domain grade must be caught by check_alpha_grade_domain.
    bad_domain = SUBMISSION_SQL.replace(
        "candidate_letter,\n                cast(null as string)",
        "'F*',\n                cast(null as string)",
    )
    if bad_domain == SUBMISSION_SQL:
        failures.append("self-test could not inject a bad grade domain")
    elif not check_alpha_grade_domain(client, sql=bad_domain):
        failures.append("check_alpha_grade_domain missed an 'F*' grade")

    # A 1-decimal credit must be caught by check_credits_earned.
    bad_format = SUBMISSION_SQL.replace("format('%.3f'", "format('%.1f'")
    if bad_format == SUBMISSION_SQL:
        failures.append("self-test could not inject a bad credit format")
    elif not any(
        "3-decimal" in f for f in check_credits_earned(client, sql=bad_format)
    ):
        failures.append("check_credits_earned missed a 1-decimal credit")

    return failures


def main():
    client = bigquery.Client(project=PROJECT)
    if "--self-test" in sys.argv:
        failures = self_test(client)
        if failures:
            print(f"SELF-TEST FAILED ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
            return 1
        print("SELF-TEST PASSED")
        return 0
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
