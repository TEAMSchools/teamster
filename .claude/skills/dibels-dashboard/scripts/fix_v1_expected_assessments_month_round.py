"""Correct `Month/Round` on Benchmark rows of the "Expected Assessments V1" tab
so it matches each region's real calendar in `reporting__terms`.

WHY THIS EXISTS, AND WHY IT IS A THIRD SCRIPT
---------------------------------------------
The same drift was fixed once already, on the newer by-levels tab, by
`fix_expected_assessments_benchmark_month_round.py` (now superseded by
`backfill_expected_assessments_derived_columns.py`). Neither can be pointed at
V1: their column indices target the 17- and 18-column layouts respectively, and
V1 is 16 columns. Rather than add a layout flag to a superseded script, this one
targets V1 explicitly and says so in its name.

V1 still matters. It is the live source for the INTERNAL PM data model --
`sheet_range: src_google_sheets__dibels_expected_assessments` -- while the
by-levels range feeds aimline. Both carry the same Benchmark rows, so whichever
branch supplies Benchmark downstream must have correct values. Leaving V1 stale
forces Benchmark to be sourced from the by-levels branch, which means the
internal chain would draw its Benchmark rows from one sheet and its PM rows from
another. Fixing V1 removes that wrinkle entirely.

THE RULE
--------
The month a Benchmark round's `Start Date` falls in IS the correct
`Month/Round`. Look it up from `reporting__terms` keyed on
(academic_year, region, admin_season), from rows where `type = 'LIT'` and
`name` is BOY, MOY or EOY.

**Match on `name`, never on `code` alone.** A PM round can carry the same
`LIT1`/`LIT2`/`LIT3` code as a Benchmark window in years before grade-band
tagging existed; only `name` separates `BOY` from `BOY->MOY`. Matching on code
lets a PM round's date overwrite a real Benchmark date, which produced
implausibly large corrections the first time this fix was attempted on the other
tab.

WHAT DRIFTS
-----------
`Month/Round` is hand-written per row, so it was copied forward as a fixed label
per season -- August / January / May network-wide -- and never checked against
the calendar. That is wrong wherever a region's window does not fall in the
canonical month. Miami is the worst case (BOY opens in September, EOY in April),
but it is not the only one: Miami's AY2024 MOY starts 2024-12-09, so its correct
label is December, not January.

Rows whose (academic_year, region, admin_season) is absent from
`reporting__terms` are LEFT ALONE and reported as skipped -- there is nothing to
correct them against yet. PM rows are never touched.

Every non-Benchmark row passes through in its original position, so the output
is a full-tab replacement, not a patch.

Usage:
    uv run --with google-api-python-client --with google-auth \
        --with google-cloud-bigquery python3 \
        .claude/skills/dibels-dashboard/scripts/fix_v1_expected_assessments_month_round.py \
        --spreadsheet-id 15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs \
        --range src_google_sheets__dibels_expected_assessments \
        --out /tmp/v1_fixed.tsv

Then paste the output over the V1 tab and rebuild
`stg_google_sheets__dibels_expected_assessments` to confirm.
"""

import argparse

import google.auth
from google.cloud import bigquery
from googleapiclient.discovery import build

# V1 tab, 16 columns, 0-indexed. Header reads:
#   Academic Year, Region, Grade, Test Type, Discipline, Subject Area,
#   Measure Standard, Test Code, Admin Season, Month/Round, Illuminate Subject,
#   iReady Subject, PS Credit Type, Assessment Include, PM Goal Include,
#   PM Goal Criteria
ACADEMIC_YEAR_COL = 0
REGION_COL = 1
ADMIN_SEASON_COL = 8
MONTH_ROUND_COL = 9
EXPECTED_WIDTH = 16

BENCHMARK_SEASONS = {"BOY", "MOY", "EOY"}

TERMS_QUERY = """
select
    academic_year,
    region,
    name as admin_season,
    start_date,
from `teamster-332318`.kipptaf_google_sheets.stg_google_sheets__reporting__terms
where type = 'LIT' and name in ('BOY', 'MOY', 'EOY')
"""


def benchmark_month_lookup(client):
    """(academic_year, region, admin_season) -> month name of the start date."""
    out = {}
    for row in client.query(TERMS_QUERY).result():
        key = (str(row.academic_year), row.region, row.admin_season)
        out[key] = row.start_date.strftime("%B")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--range", required=True, dest="named_range")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds)
    grid = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=args.spreadsheet_id, range=args.named_range)
        .execute()
        .get("values", [])
    )
    if not grid:
        raise SystemExit(f"{args.named_range} returned no rows")

    header, rows = grid[0], grid[1:]
    if len(header) != EXPECTED_WIDTH:
        raise SystemExit(
            f"expected the {EXPECTED_WIDTH}-column V1 layout, got {len(header)}:"
            f" {header}. If the tab was widened, this script's column indices"
            " are wrong -- fix them before running."
        )

    lookup = benchmark_month_lookup(bigquery.Client(project="teamster-332318"))

    corrected = []
    changes = []
    skipped = set()
    for row in rows:
        row = list(row) + [""] * (EXPECTED_WIDTH - len(row))
        season = row[ADMIN_SEASON_COL].strip()
        if season not in BENCHMARK_SEASONS:
            corrected.append(row)
            continue

        key = (row[ACADEMIC_YEAR_COL].strip(), row[REGION_COL].strip(), season)
        want = lookup.get(key)
        if want is None:
            skipped.add(key)
            corrected.append(row)
            continue

        have = row[MONTH_ROUND_COL].strip()
        if have != want:
            changes.append((key, have, want))
            row[MONTH_ROUND_COL] = want
        corrected.append(row)

    with open(args.out, "w") as f:
        f.write("\t".join(header) + "\n")
        for row in corrected:
            f.write("\t".join(row) + "\n")

    print(f"rows written: {len(corrected)} (+ header) -> {args.out}")
    print(f"Benchmark rows corrected: {len(changes)}")
    by_key = {}
    for key, have, want in changes:
        by_key.setdefault((key, have, want), 0)
        by_key[(key, have, want)] += 1
    for (key, have, want), n in sorted(by_key.items(), key=lambda kv: str(kv[0])):
        year, region, season = key
        print(
            f"  {year} {region:9s} {season:3s}  {have or '<blank>'} -> {want}  ({n} rows)"
        )
    if skipped:
        print(f"skipped, no reporting__terms row yet: {len(skipped)} key(s)")
        for key in sorted(skipped):
            print(f"  {key[0]} {key[1]} {key[2]}")


if __name__ == "__main__":
    main()
