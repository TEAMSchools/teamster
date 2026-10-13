"""Write the live Goals tab, whole, as a pasteable TSV -- optionally with edits.

Goal changes are handed to the user as the entire tab, pasted over A1, never as a
list of cells to edit by hand. This reads the tab LIVE through the Sheets external
(ADC has Drive scope; the BigQuery MCP does not), not the staging model, which is
unpivoted to one row per metric and does not have the tab's shape.

Output is tab-separated because Google Sheets only splits a paste into columns on
tabs; comma-separated text lands entirely in column A. Blank cells stay blank --
staging's UNPIVOT drops nulls, so filling a blank (every PSAT pct_2_plus_attempts)
creates a goal that did not exist.

Usage:
    uv run python .claude/skills/carat-dashboard/scripts/dump_goals_tab.py \
        out.tsv [--set MATCH COLUMN=VALUE]...

MATCH is comma-separated column=value pairs; every row matching all of them gets
COLUMN set to VALUE. Example -- Official SAT 2+ attempts to 95%:

    --set test_type=Official,score_type=sat_total_score pct_2_plus_attempts=0.95

A --set that matches no row, or names an unknown column, aborts.
"""

import argparse
import csv
import sys

from google.cloud import bigquery

QUERY = (
    "select * from "
    "`teamster-332318.kipptaf_google_sheets.src_google_sheets__kippfwd__goals`"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--set", nargs=2, action="append", default=[])
    args = parser.parse_args()

    result = bigquery.Client(project="teamster-332318").query(QUERY).result()
    header = [field.name for field in result.schema]
    rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in result]

    for match, assignment in args.set:
        pairs = match.split(",") + [assignment]
        if any("=" not in pair for pair in pairs):
            sys.exit(f"--set {match} {assignment}: every part must be column=value")
        conditions = dict(pair.split("=", 1) for pair in match.split(","))
        column, value = assignment.split("=", 1)
        unknown = (set(conditions) | {column}) - set(header)
        if unknown:
            sys.exit(f"unknown column(s): {sorted(unknown)}")
        hits = [r for r in rows if all(r[k] == v for k, v in conditions.items())]
        if not hits:
            sys.exit(f"--set {match} matched no row")
        for r in hits:
            print(f"{match}: {column} {r[column] or '(blank)'} -> {value}")
            r[column] = value

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows([r[c] for c in header] for r in rows)

    print(f"wrote {len(rows)} rows x {len(header)} columns to {args.out}")


if __name__ == "__main__":
    main()
