"""SUPERSEDED -- see `backfill_expected_assessments_derived_columns.py`, which
folds this fix in alongside `assessment_type` backfill. Kept for its docstring
(the boundary-rule writeup) and because it was already run once; don't run it
standalone against the current sheet -- its column indices target the
intermediate 17-column schema (`measure_standard_level` added,
`assessment_type` not yet), not the current 18-column layout.

Correct `month_round` on Benchmark rows in the "Expected Assessments" tab
so it matches each region's actual calendar in `reporting__terms`, instead of
a single fixed label copied network-wide.

Root cause this fixes: `month_round` for Benchmark rows (BOY/MOY/EOY) is
manually written per row and drifts from the actual calendar over time and
across regions -- confirmed on Miami specifically for AY2025/AY2026 (its BOY
starts in September, not the "August" every other region and every prior
year's Miami row carries; its EOY starts in April, not "May"), and the same
kind of drift shows up on older years too once checked against
`reporting__terms` directly. Nobody had checked month_round against
`reporting__terms`' actual dates before this.

The month a Benchmark round's `Start Date` in `reporting__terms` falls in
IS the correct `month_round` value. This script derives that lookup --
keyed on (academic_year, region, admin_season), sourced from the `LIT1`/
`LIT2`/`LIT3` rows in `reporting__terms` -- and applies it to every Benchmark
row on the "Expected Assessments" tab for every academic year present,
correcting any row whose `month_round` disagrees. Rows for an academic
year/region not yet in `reporting__terms` are left untouched and reported as
skipped -- there is nothing to correct them against yet.

**Disambiguating a Benchmark row from a PM round sharing the same code**:
before grade-band tagging existed, a PM round can carry the exact same
`LIT1`/`LIT2`/`LIT3` code as the real Benchmark row for that year, with no
`Grade Band` value to tell them apart either (e.g. AY2024 Camden `LIT1` has
one row named `BOY`, dated 2024-08-21, and another named `BOY->MOY`, dated
2024-09-30 -- same code, both grade-band-blank). Only the `Name` column
(exactly `BOY`/`MOY`/`EOY`, vs `BOY->MOY` etc for a PM round) disambiguates
them. Matching by code alone silently let a PM round's date overwrite the
true Benchmark date in the lookup for those years -- caught by comparing
which rows this script proposed changing against `reporting__terms` before
trusting the diff, not by inspection of the code alone.

PM rows are untouched entirely -- this script only touches
`admin_season in (BOY, MOY, EOY)`.

Usage:
    uv run --with google-api-python-client --with google-auth python3 \
        .claude/skills/dibels-dashboard/scripts/fix_expected_assessments_benchmark_month_round.py \
        --terms-spreadsheet-id 1azcq9FsGDjYpvK7VBIHtGOsY8Yd-E5hFrxWuk5hFLH0 \
        --terms-tab "Reporting Terms" \
        --ea-spreadsheet-id 15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs \
        --ea-tab "Expected Assessments" \
        --out out.tsv
"""

import argparse
import datetime

import google.auth
from googleapiclient.discovery import build

NUM_COLS = 17
AY_COL, REGION_COL, MSL_COL, ASEASON_COL, MROUND_COL = 0, 1, 6, 9, 10
BENCHMARK_CODE_TO_SEASON = {"LIT1": "BOY", "LIT2": "MOY", "LIT3": "EOY"}

T_TYPE, T_CODE, T_NAME, T_START, T_AY, T_REGION = 0, 1, 2, 3, 5, 10


def build_month_lookup(rows: list[list[str]]) -> dict[tuple[str, str, str], str]:
    lookup: dict[tuple[str, str, str], str] = {}
    for r in rows:
        if len(r) <= T_REGION:
            continue  # trailing blank cells (Grade Band, Lockbox Date) are dropped by the API
        if r[T_TYPE] != "LIT" or r[T_CODE] not in BENCHMARK_CODE_TO_SEASON:
            continue
        season = BENCHMARK_CODE_TO_SEASON[r[T_CODE]]
        if r[T_NAME] != season:
            # In years before grade-band tagging existed, a PM round can share the
            # same LIT1/LIT2/LIT3 code as the real Benchmark row (code alone does
            # not disambiguate) -- only the Name column ("BOY"/"MOY"/"EOY" exactly,
            # vs "BOY->MOY" etc for a PM round) tells them apart.
            continue
        month = datetime.date.fromisoformat(r[T_START]).strftime("%B")
        lookup[(r[T_AY], r[T_REGION], season)] = month
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms-spreadsheet-id", required=True)
    parser.add_argument("--terms-tab", required=True)
    parser.add_argument("--ea-spreadsheet-id", required=True)
    parser.add_argument("--ea-tab", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds)

    terms_res = (
        svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=args.terms_spreadsheet_id,
            range=f"'{args.terms_tab}'!A1:M20000",
        )
        .execute()
    )
    terms_rows = [r for r in terms_res.get("values", [])[1:] if r and r[0].strip()]
    month_lookup = build_month_lookup(terms_rows)

    ea_res = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=args.ea_spreadsheet_id, range=f"'{args.ea_tab}'!A1:R20000")
        .execute()
    )
    ea_rows = [r for r in ea_res.get("values", [])[1:] if r and r[0].strip()]

    out_rows = []
    corrected = 0
    skipped_no_lookup: set[tuple[str, str, str]] = set()
    for row in ea_rows:
        padded = list(row) + [""] * (NUM_COLS - len(row))
        season = padded[ASEASON_COL]
        if season in ("BOY", "MOY", "EOY"):
            key = (padded[AY_COL], padded[REGION_COL], season)
            correct_month = month_lookup.get(key)
            if correct_month is None:
                skipped_no_lookup.add(key)
            elif padded[MROUND_COL] != correct_month:
                padded[MROUND_COL] = correct_month
                corrected += 1
        out_rows.append(padded)

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(f"total rows written: {len(out_rows)} -> {args.out}")
    print(f"month_round corrected: {corrected}")
    if skipped_no_lookup:
        print(
            "\nBenchmark rows with no reporting_terms match (left as-is, nothing to "
            "correct against yet):"
        )
        for key in sorted(skipped_no_lookup):
            print(f"  {key}")


if __name__ == "__main__":
    main()
