"""Create the NJ SLEDS submission view and export one CSV per region.

Refuses to export if the validation gate reports any failure. Every value is
written as the string the view produced - no numeric coercion, so 3-decimal
credits and leading-zero CDS codes survive.

Each region is staged under a temporary filename and only renamed to its
final name once every region has exported successfully. This keeps a
mid-run failure from leaving a freshly written file for one region sitting
next to a stale file (from a previous run) for another, indistinguishable by
name.

Usage:
    uv run --with google-cloud-bigquery python build_submission.py OUTDIR
"""

import csv
import sys
from pathlib import Path

from google.cloud import bigquery
from submission_query import REGIONS_IN_SCOPE as REGIONS
from submission_query import (
    SUBMISSION_COLUMNS,
    SUBMISSION_SQL,
)
from validate_submission import base_table_row_count, run_checks

PROJECT = "teamster-332318"
VIEW = "teamster-332318.cokafor.rpt_student_course_submission"


def create_view(client):
    client.query(f"create or replace view `{VIEW}` as {SUBMISSION_SQL}").result()
    print(f"view created: {VIEW}")


def export_region(client, region, outdir):
    """Query one region from the view and stage its CSV under a temp name.

    Verifies the exported row count against the region's base table before
    writing anything: the view's non-extract inputs
    (stg_powerschool__students / storedgrades / pgfinalgrades) are
    dbt-managed and refresh daily, so a row landing in the window between the
    gate run and this export could fan the join out and silently write more
    rows than the extract has. Returns (final_path, temp_path, row_count) so
    the caller can rename every region's staged file only once all regions
    have succeeded.
    """
    cols = ", ".join(f"`{c}`" for c in SUBMISSION_COLUMNS)
    # trunk-ignore(bandit/B608): region is drawn from the local REGIONS constant, not user input
    sql = f"select {cols} from `{VIEW}` where region = '{region}'"
    rows = list(client.query(sql).result())

    expected = base_table_row_count(client, region)
    if len(rows) != expected:
        raise RuntimeError(
            f"export row-count mismatch for {region}: exported {len(rows)} "
            f"row(s), base table has {expected} row(s) (join fanned out "
            "since the gate ran)"
        )

    final_path = Path(outdir) / f"NJ_Student_Course_Submission_{region}.csv"
    temp_path = final_path.with_name(final_path.name + ".tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(SUBMISSION_COLUMNS)
        for row in rows:
            writer.writerow(
                ["" if row[c] is None else str(row[c]) for c in SUBMISSION_COLUMNS]
            )
    print(f"  {region}: {len(rows)} rows -> {temp_path} (staged)")
    return final_path, temp_path, len(rows)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)

    client = bigquery.Client(project=PROJECT)

    print("running validation gate...")
    failures = run_checks(client)
    if failures:
        print(f"GATE FAILED ({len(failures)} issue(s)) - refusing to export:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("gate passed")

    create_view(client)

    staged = []
    try:
        for region in REGIONS:
            staged.append(export_region(client, region, outdir))
    except RuntimeError as e:
        print(f"EXPORT ABORTED: {e}")
        for _, temp_path, _ in staged:
            temp_path.unlink(missing_ok=True)
        return 1

    for final_path, temp_path, _ in staged:
        temp_path.rename(final_path)
    total = sum(count for _, _, count in staged)
    print(f"exported {total} rows across {len(REGIONS)} region(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
