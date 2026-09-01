"""Backfill the new `assessment_type` column on the "Expected Assessments"
tab for every row, all years, and correct `month_round` on Benchmark rows
against `reporting__terms`' actual dates while regenerating.

`assessment_type` replaces the `if(admin_season in ('BOY', 'MOY', 'EOY'),
'Benchmark', 'PM')` derivation that used to live in
`stg_google_sheets__dibels_expected_assessments.sql` -- the value is now
authored on the sheet directly instead of inferred downstream. This script
fills it using that exact same rule, so every existing row keeps the value
it already had implicitly; a future row with no assessment_type set is
simply missing data, not a rule to reverse-engineer.

`month_round` correction is the fix from
`fix_expected_assessments_benchmark_month_round.py`, folded in here so this
produces one complete, current TSV rather than two that need to be merged
by hand. See that script's docstring for why month_round drifts and how the
Benchmark-vs-PM-round disambiguation (by `Name`, not code) matters when
building the reporting_terms lookup.

Column layout as of the assessment_type column add (index 6, after
subject_area):
    0 academic_year, 1 region, 2 grade, 3 test_type, 4 discipline,
    5 subject_area, 6 assessment_type, 7 measure_standard_level,
    8 measure_standard, 9 test_code, 10 admin_season, 11 month_round,
    12 illuminate_subject, 13 iready_subject, 14 ps_credit_type,
    15 assessment_include, 16 pm_goal_include, 17 pm_goal_criteria

Usage:
    uv run --with google-api-python-client --with google-auth python3 \
        .claude/skills/dibels-dashboard/scripts/backfill_expected_assessments_derived_columns.py \
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

NUM_COLS = 18
AY_COL, REGION_COL, ATYPE_COL, ASEASON_COL, MROUND_COL = 0, 1, 6, 10, 11
BENCHMARK_SEASONS = {"BOY", "MOY", "EOY"}
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
            continue  # a PM round can share the same code; Name disambiguates
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
        .get(spreadsheetId=args.ea_spreadsheet_id, range=f"'{args.ea_tab}'!A1:S20000")
        .execute()
    )
    ea_rows = [r for r in ea_res.get("values", [])[1:] if r and r[0].strip()]

    out_rows = []
    atype_filled = 0
    month_corrected = 0
    skipped_no_lookup: set[tuple[str, str, str]] = set()
    for row in ea_rows:
        padded = list(row) + [""] * (NUM_COLS - len(row))
        season = padded[ASEASON_COL]
        assessment_type = "Benchmark" if season in BENCHMARK_SEASONS else "PM"
        if padded[ATYPE_COL] != assessment_type:
            padded[ATYPE_COL] = assessment_type
            atype_filled += 1

        if season in BENCHMARK_SEASONS:
            key = (padded[AY_COL], padded[REGION_COL], season)
            correct_month = month_lookup.get(key)
            if correct_month is None:
                skipped_no_lookup.add(key)
            elif padded[MROUND_COL] != correct_month:
                padded[MROUND_COL] = correct_month
                month_corrected += 1

        out_rows.append(padded)

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(f"total rows written: {len(out_rows)} -> {args.out}")
    print(f"assessment_type filled/changed: {atype_filled}")
    print(f"month_round corrected: {month_corrected}")
    if skipped_no_lookup:
        print(
            "\nBenchmark rows with no reporting_terms match (month_round left as-is):"
        )
        for key in sorted(skipped_no_lookup):
            print(f"  {key}")


if __name__ == "__main__":
    main()
