"""Duplicate an existing `reporting__terms` grade-band's `LIT` rows under new
`Grade Band` values, for years where every band tested on the same calendar.

**`PLIT` is K-2-only in the target SY26-27 model — never duplicate it for
another band.** `PLIT` feeds the in-house, collective-average PM goal
calculation (school-day counting for the daily-growth-rate math), which only
K-2 keeps; grades 3-8 move to Amplify aimline, which supplies per-student
goals directly and has no use for `PLIT`. This script only ever reads and
writes `LIT`-coded rows (see the `PLIT%` exclusion below) — if a future band
genuinely needs `PLIT`, that is a K-2-band-only case, not something this
script should do generically.

SY25-26 (academic_year=2025) has `LIT` rows carrying `Grade Band = "0,1,2"`
alongside K-2's `PLIT` rows. Grades 3-8 need their own `Grade Band`-tagged
`LIT` rows to build/validate the new 3-8 model, split into bands (typically
`3,4` and `5,6,7,8`) -- but SY25-26 had no grade-band-specific PM calendar,
every grade tested on the same dates. So the correct SY25-26 rows are exact
duplicates of `0,1,2`'s `LIT` rows, region by region, with only `Grade Band`
changed.

**Grade bands are region-specific.** Verified against SY25-26 enrollment:
Paterson had no grade 4 and no grade 8, so its bands are `3` and `5,6,7`, not
the `3,4` / `5,6,7,8` the other three regions use. Pass per-region overrides,
don't apply one region's band definition to all.

**No `code` prefix is needed.** `dim_terms.term_key` now hashes `grade_band`
too (fixed on #3834 after this exact scenario broke
`unique_dim_terms_term_key` -- duplicating a row with the same `code` and
only a different `grade_band` used to collide on `term_key`). A `--band`
GRADE_BAND:CODE_PREFIX form is still accepted for the rare case a band needs
a genuinely different code, but leave the prefix empty (`"3,4:"`) unless
there's a real reason not to.

Usage:
    uv run --with google-api-python-client --with google-auth python3 \
        .claude/skills/dibels-dashboard/scripts/duplicate_reporting_terms_grade_band.py \
        --spreadsheet-id 1azcq9FsGDjYpvK7VBIHtGOsY8Yd-E5hFrxWuk5hFLH0 \
        --tab "Reporting Terms" \
        --academic-year 2025 \
        --source-grade-band "0,1,2" \
        --band "3,4:" \
        --band "5,6,7,8:" \
        --region-override "Paterson:3" \
        --region-override "Paterson:5,6,7" \
        --out out.tsv

`--region-override "Paterson:3"` REPLACES Paterson's copy of the first band
with `3` (matched by position, not value) -- pass one override per band, in
the same order as `--band`, only for regions that diverge.
"""

import argparse

import google.auth
from googleapiclient.discovery import build

TYPE_COL = 0
CODE_COL = 1
NAME_COL = 2
REGION_COL = 10
GRADE_BAND_COL = 11


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--tab", required=True)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--source-grade-band", required=True)
    parser.add_argument(
        "--band", action="append", required=True, help="GRADE_BAND:CODE_PREFIX"
    )
    parser.add_argument(
        "--region-override",
        action="append",
        default=[],
        help="REGION:GRADE_BAND, positionally matched to --band order for that region",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    bands = [b.split(":", 1) for b in args.band]

    overrides_by_region: dict[str, list[str]] = {}
    for spec in args.region_override:
        region, band = spec.split(":", 1)
        overrides_by_region.setdefault(region, []).append(band)

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    svc = build("sheets", "v4", credentials=creds)
    res = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=args.spreadsheet_id, range=f"'{args.tab}'!A1:M10000")
        .execute()
    )
    rows = res.get("values", [])[1:]  # drop header

    academic_year_col = 5
    source_rows = [
        r
        for r in rows
        if len(r) > GRADE_BAND_COL
        and r[GRADE_BAND_COL] == args.source_grade_band
        and r[academic_year_col] == args.academic_year
        and not r[CODE_COL].startswith("PLIT")
    ]

    if not source_rows:
        raise SystemExit(
            f"No rows found for academic_year={args.academic_year} "
            f"grade_band={args.source_grade_band} -- check the filters."
        )

    out_rows = []
    for position, (default_band, code_prefix) in enumerate(bands):
        for row in source_rows:
            region = row[REGION_COL]
            region_overrides = overrides_by_region.get(region, [])
            band = (
                region_overrides[position]
                if position < len(region_overrides)
                else default_band
            )
            new_row = list(row)
            new_row[GRADE_BAND_COL] = band
            new_row[CODE_COL] = code_prefix + new_row[CODE_COL]
            out_rows.append(new_row)

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(f"source rows matched ({args.source_grade_band}): {len(source_rows)}")
    print(f"total rows written: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
