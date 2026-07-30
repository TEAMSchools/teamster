"""Create the NJ SLEDS submission view and export one CSV per region.

Refuses to export if the validation gate reports any failure. Every value is
written as the string the view produced - no numeric coercion, so 3-decimal
credits and leading-zero CDS codes survive.

Usage:
    uv run --with google-cloud-bigquery python build_submission.py OUTDIR
"""

import csv
import sys
from pathlib import Path

from google.cloud import bigquery
from submission_query import SUBMISSION_COLUMNS, SUBMISSION_SQL
from validate_submission import run_checks

PROJECT = "teamster-332318"
VIEW = "teamster-332318.cokafor.rpt_student_course_submission"
REGIONS = ("newark", "camden")


def create_view(client):
    client.query(f"create or replace view `{VIEW}` as {SUBMISSION_SQL}").result()
    print(f"view created: {VIEW}")


def export_region(client, region, outdir):
    cols = ", ".join(f"`{c}`" for c in SUBMISSION_COLUMNS)
    # trunk-ignore(bandit/B608): region is drawn from the local REGIONS constant, not user input
    sql = f"select {cols} from `{VIEW}` where region = '{region}'"
    rows = list(client.query(sql).result())
    path = Path(outdir) / f"NJ_Student_Course_Submission_{region}.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(SUBMISSION_COLUMNS)
        for row in rows:
            writer.writerow(
                ["" if row[c] is None else str(row[c]) for c in SUBMISSION_COLUMNS]
            )
    print(f"  {region}: {len(rows)} rows -> {path}")
    return len(rows)


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
    total = sum(export_region(client, r, outdir) for r in REGIONS)
    print(f"exported {total} rows across {len(REGIONS)} region(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
