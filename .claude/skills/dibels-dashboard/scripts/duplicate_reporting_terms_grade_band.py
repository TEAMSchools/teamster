"""Duplicate an existing `reporting__terms` grade-band's rows under new
`Grade Band` values, for years where every band tested on the same calendar.

SY25-26 (academic_year=2025) has PLIT rows carrying `Grade Band = "0,1,2"`
(K-2's pre-round accounting). Grades 3-8 need their own `Grade Band`-tagged
rows to build/validate the new 3-8 model, split into bands (typically `3,4`
and `5,6,7,8`) -- but SY25-26 had no grade-band-specific PM calendar, every
grade tested on the same dates. So the correct SY25-26 rows are exact
duplicates of the `0,1,2` rows, region by region, with only `Grade Band` (and
`Code`, see below) changed.

**Grade bands are region-specific.** Verified against SY25-26 enrollment:
Paterson had no grade 4 and no grade 8, so its bands are `3` and `5,6,7`, not
the `3,4` / `5,6,7,8` the other three regions use. Pass per-region overrides,
don't apply one region's band definition to all.

**Each band needs its own `code` prefix, not just a `Grade Band` tag.**
`dim_terms.term_key` hashes `(type, code, name, start_date, region,
school_id)` -- `grade_band` is NOT in that key. Duplicating a row with the
same `code` and only a different `grade_band` collides on `term_key` (a real
failure, caught via `unique_dim_terms_term_key`). `LIT` vs `PLIT` already
avoids this for K-2 by being different codes; give every new band its own
prefix the same way (e.g. `MLIT`/`MPLIT` for one band, `HLIT`/`HPLIT` for
another) rather than reusing `LIT`/`PLIT` untouched.

Usage:
    uv run --with google-api-python-client --with google-auth python3 \
        .claude/skills/dibels-dashboard/scripts/duplicate_reporting_terms_grade_band.py \
        --spreadsheet-id 1azcq9FsGDjYpvK7VBIHtGOsY8Yd-E5hFrxWuk5hFLH0 \
        --tab "Reporting Terms" \
        --academic-year 2025 \
        --source-grade-band "0,1,2" \
        --band "3,4:M" \
        --band "5,6,7,8:H" \
        --region-override "Paterson:3" \
        --region-override "Paterson:5,6,7" \
        --out out.tsv

`--band "3,4:M"` is GRADE_BAND:CODE_PREFIX -- the prefix is prepended to the
source row's existing `code` (`LIT1` -> `MLIT1`, `PLIT1` -> `MPLIT1`).
`--region-override "Paterson:3"` REPLACES Paterson's copy of the first band
with `3` (matched by position, not value; keeps that band's code prefix) --
pass one override per band, in the same order as `--band`, only for regions
that diverge.
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
