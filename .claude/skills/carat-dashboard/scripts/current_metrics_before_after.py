"""Compare the _current view's metrics before and after a score load.

Runs the compiled SQL of rpt_tableau__college_assessment_dashboard_current twice:
once as it stands, and once with int_assessments__all_college_assessments read
AS OF a timestamp, so the only thing that differs is which scores existed. Goals,
thresholds and the enrollment roster are read as of now in both runs, so a change
in the output is caused by the load and nothing else.

Both references to the scores table carry the same timestamp, which BigQuery
requires. Time travel reaches back 7 days only.

Percent met matches the published dashboard: one row per grade for
total scores only, filtered to currently enrolled (enroll_status = 0),
non-IEP-exempt students, then met_min_score_int = 1 over all of them, testers or
not -- verified against the Landing Page's bar counts. Shown
beside expected_metric_pct_goal. Counts only -- no student rows leave the
warehouse.

Usage (compile the model first):
    uv run dbt compile --select rpt_tableau__college_assessment_dashboard_current \
        --project-dir src/dbt/kipptaf --target prod
    uv run python .claude/skills/carat-dashboard/scripts/current_metrics_before_after.py \
        "2026-10-20 14:10:00 America/New_York" [--by-school]
"""

import argparse
import pathlib

from google.cloud import bigquery

COMPILED = pathlib.Path(
    "src/dbt/kipptaf/target/compiled/kipptaf/models/extracts/tableau/"
    "rpt_tableau__college_assessment_dashboard_current.sql"
)
SCORES = (
    "`teamster-332318`.`kipptaf_assessments`.`int_assessments__all_college_assessments`"
)


def metrics_sql(view_sql: str, by_school: bool) -> str:
    school = "school," if by_school else ""
    # trunk-ignore(bandit/B608): view_sql is the repo's own compiled model; as_of is a query parameter
    return f"""
with v as ({view_sql})
select
    expected_test_type,
    expected_scope,
    expected_metric_label,
    grade_level,
    {school}
    count(*) as students_with_score,
    round(100 * avg(met_min_score_int), 1) as pct_met,
    round(100 * any_value(expected_metric_pct_goal), 1) as pct_goal,
from v
where
    enroll_status = 0
    and grad_iep_exempt_status_overall != 'Yes'
    and expected_aligned_subject_area = 'Total'
group by expected_test_type, expected_scope, expected_metric_label, grade_level {"," if by_school else ""} {school.rstrip(",")}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "as_of", help="the paste time, e.g. '2026-10-20 14:10:00 America/New_York'"
    )
    parser.add_argument("--by-school", action="store_true")
    args = parser.parse_args()

    view_sql = COMPILED.read_text()
    if view_sql.count(SCORES) != 2:
        raise SystemExit(
            f"expected 2 references to the scores table, found {view_sql.count(SCORES)}"
        )
    before_sql = view_sql.replace(
        SCORES, f"{SCORES} for system_time as of timestamp(@as_of)"
    )

    client = bigquery.Client(project="teamster-332318")
    runs = {}
    for label, sql in (("before", before_sql), ("now", view_sql)):
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("as_of", "STRING", args.as_of)
            ]
        )
        for row in client.query(
            metrics_sql(sql, args.by_school), job_config=config
        ).result():
            key = tuple(
                v
                for k, v in row.items()
                if k not in ("students_with_score", "pct_met", "pct_goal")
            )
            runs.setdefault(key, {})[label] = row

    print(
        "test_type | scope | metric | grade"
        + (" | school" if args.by_school else "")
        + " | before % (n) | now % (n) | change | goal %"
    )
    for key in sorted(runs, key=lambda k: tuple(str(x) for x in k)):
        b, n = runs[key].get("before"), runs[key].get("now")
        if n is None or n["students_with_score"] == 0:
            continue
        b_pct = b["pct_met"] if b else None
        b_n = b["students_with_score"] if b else 0
        if b_pct is None or n["pct_met"] is None:
            change = "-"
        else:
            change = f"{n['pct_met'] - b_pct:+.1f}"
        cells = [str(x) for x in key] + [
            f"{b_pct} ({b_n})",
            f"{n['pct_met']} ({n['students_with_score']})",
            change,
            str(n["pct_goal"]),
        ]
        print(" | ".join(cells))


if __name__ == "__main__":
    main()
