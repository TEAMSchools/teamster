"""Create the NJ SLEDS ungraded-worklist view and export one CSV per region.

Deliberately NOT gated on validate_submission.run_checks. The worklist is the
tool used to resolve the rows that make the gate fail (no usable grade in
either source, conflicting grades, or an out-of-domain grade) - gating this
script on the gate passing would be circular: it would only become available
once it was no longer needed. Run it regardless of the gate's state.

Every value is written as the string the view produced - no numeric
coercion - with None becoming an empty field, matching build_submission.py.

Usage:
    uv run --with google-cloud-bigquery python export_worklist.py OUTDIR
"""

import csv
import sys
from pathlib import Path

from google.cloud import bigquery
from submission_query import UNGRADED_WORKLIST_COLUMNS, UNGRADED_WORKLIST_SQL

PROJECT = "teamster-332318"
VIEW = "teamster-332318.cokafor.rpt_student_course_ungraded"
REGIONS = ("newark", "camden")


def create_view(client):
    client.query(f"create or replace view `{VIEW}` as {UNGRADED_WORKLIST_SQL}").result()
    print(f"view created: {VIEW}")


def export_region(client, region, outdir):
    """Query one region from the view and write its worklist CSV."""
    cols = ", ".join(f"`{c}`" for c in UNGRADED_WORKLIST_COLUMNS)
    # trunk-ignore(bandit/B608): region is drawn from the local REGIONS constant, not user input
    sql = f"select {cols} from `{VIEW}` where region = '{region}'"
    rows = list(client.query(sql).result())

    final_path = Path(outdir) / f"NJ_Student_Course_Ungraded_{region}.csv"
    with final_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(UNGRADED_WORKLIST_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    "" if row[c] is None else str(row[c])
                    for c in UNGRADED_WORKLIST_COLUMNS
                ]
            )
    print(f"  {region}: {len(rows)} rows -> {final_path}")
    return len(rows)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)

    client = bigquery.Client(project=PROJECT)

    create_view(client)

    total = 0
    for region in REGIONS:
        total += export_region(client, region, outdir)
    print(f"exported {total} rows across {len(REGIONS)} region(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
