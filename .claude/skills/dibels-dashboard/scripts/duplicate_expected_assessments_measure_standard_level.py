"""Regenerate the full "Expected Assessments" tab data, splitting SY2025-26 PM
rows across the new `measure_standard_level` cohort dimension (Below / Well
Below).

Every 2025 PM row on this tab today has no cohort split -- one row per
measure_standard tested for a region/grade/round. Per the T&L PM rounds doc
(SY27 - KIPP NJ - DIBELS PM Rounds + Goals), every PM round lists "Below &
Well-below" together with no differentiation -- both cohorts are tested on
the identical measures on the identical rounds. So for 2025, the correct fix
is mechanical: each existing PM row becomes two rows, identical in every
column except `measure_standard_level` ("Below" then "Well Below" right
after it), in place of the original single row.

Every other row -- other academic years, and Benchmark rows (BOY/MOY/EOY)
for ANY year including 2025 -- passes through byte-for-byte unchanged, in
its original position. Benchmark rows are excluded from the split because
Benchmark tests all students regardless of cohort.

Walking the whole tab in original order (rather than filtering to just the
2025 PM rows) sidesteps a real problem: those rows are not a contiguous
block in the sheet (a ~376-row span of other rows sits in the middle of
their range), so a partial-output paste-over would land on the wrong rows.
Regenerating the entire tab keeps every row's context and lets it be pasted
as one contiguous block starting at row 2.

Usage:
    uv run --with google-api-python-client --with google-auth python3 \
        .claude/skills/dibels-dashboard/scripts/duplicate_expected_assessments_measure_standard_level.py \
        --spreadsheet-id 15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs \
        --tab "Expected Assessments" \
        --academic-year 2025 \
        --out out.tsv
"""

import argparse

import google.auth
from googleapiclient.discovery import build

NUM_COLS = 17
ACADEMIC_YEAR_COL = 0
MEASURE_STANDARD_LEVEL_COL = 6
ADMIN_SEASON_COL = 9
BENCHMARK_SEASONS = {"BOY", "MOY", "EOY"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--tab", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds)
    res = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=args.spreadsheet_id, range=f"'{args.tab}'!A1:R20000")
        .execute()
    )
    rows = res.get("values", [])[1:]  # drop header

    out_rows = []
    split_count = 0
    passthrough_count = 0
    for row in rows:
        if not row or not row[0].strip():
            continue  # phantom blank sheet row past the real data

        padded = list(row) + [""] * (NUM_COLS - len(row))
        is_target_year = padded[ACADEMIC_YEAR_COL].strip() == args.academic_year
        is_pm_row = padded[ADMIN_SEASON_COL] not in BENCHMARK_SEASONS
        already_split = padded[MEASURE_STANDARD_LEVEL_COL].strip() != ""

        if is_target_year and is_pm_row and not already_split:
            below = list(padded)
            below[MEASURE_STANDARD_LEVEL_COL] = "Below"
            well_below = list(padded)
            well_below[MEASURE_STANDARD_LEVEL_COL] = "Well Below"
            out_rows.append(below)
            out_rows.append(well_below)
            split_count += 1
        else:
            out_rows.append(padded)
            passthrough_count += 1

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(
        f"PM rows split into Below/Well Below (academic_year={args.academic_year}): {split_count}"
    )
    print(f"rows passed through unchanged: {passthrough_count}")
    print(f"total output rows: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
