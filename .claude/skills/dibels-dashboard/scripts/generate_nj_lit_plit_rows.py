"""Generate NJ `LIT`/`PLIT` rows for `reporting__terms` (Camden, Newark,
Paterson) for any academic year -- Miami excluded, see module docstring below.

`LIT` round dates come from `--rounds`, a TSV transcribed directly from the
confirmed T&L PM rounds doc for the year -- never derived or rolled forward.
Benchmark BOY/MOY/EOY rows are added by a separate rollover pass and are not
touched here.

`--rounds` columns (tab-separated, one header row, regions in output order):

    region         `Newark`, `Paterson` or `Camden`
    round_number   1-based, in calendar order within the region
    season         `BOY->MOY` or `MOY->EOY`
    start_date     ISO `YYYY-MM-DD`
    end_date       ISO `YYYY-MM-DD`
    plit1_start    required on the region's round 1 row, blank elsewhere: the
                   region's own BOY Benchmark start date, which PLIT1 starts ON
                   (see below). Take it from the year's `LIT1`/`BOY` rows
                   already in `reporting__terms`.

The TSV is transcribed fresh each year and not committed. First rows of the
SY26-27 table, for the shape:

    region	round_number	season	start_date	end_date	plit1_start
    Newark	1	BOY->MOY	2026-09-28	2026-10-02	2026-08-19
    Newark	2	BOY->MOY	2026-10-19	2026-10-23

`PLIT` dates are DERIVED, not transcribed, using the boundary rule verified
against real AY2025 `reporting__terms` data (see the `dibels-dashboard` skill,
"PLIT boundary rule" -- matched 7 real boundaries exactly across Camden, Newark
and Paterson before this script was written):

    PLITn.start = first IN-SESSION day strictly after the previous round's
                  end_date (round n-1, or the season's own Benchmark start
                  for PLIT1)
    PLITn.end   = last IN-SESSION day strictly before round n's start_date

This holds cleanly WITHIN a season. Crossing from BOY->MOY into MOY->EOY
(the first PLIT of the second season) is an open question -- AY2025's real
data shows a 1-day overlap there (the new season's PLIT1 starts one
calendar day before the old season's last round officially ends) that was
never explained and is NOT replicated here. This script applies the same
clean rule at the season boundary too (day after the last BOY->MOY round
ends). If that turns out wrong, only the one row per region needs
correcting once the real reason for that overlap is known.

PD days are deliberately NOT excluded from the boundary calculation.
Checked against AY2025's real numbers first: the frozen PM goals sheet
does NOT reliably exclude PD days either (Camden round 2's frozen
`pm_round_days` matched a naive PD-day-inclusive count exactly), so
building PD-day awareness in here would make this MORE correct than
precedent, not consistent with it. Revisit if that's ever explicitly
decided otherwise.

Miami is excluded entirely -- its PLIT structure is different (windows
spanning entire breaks) and unverified; it has its own script,
`generate_miami_lit_plit_rows.py`.

Usage:
    uv run --with google-cloud-bigquery python3 \
        .claude/skills/dibels-dashboard/scripts/generate_nj_lit_plit_rows.py \
        --academic-year 2026 \
        --rounds sy2627_nj.tsv \
        --out out.tsv
"""

import argparse
import csv
import datetime

from google.cloud import bigquery

DEFAULT_BANDS = ["0,1,2", "3,4", "5,6,7,8"]


def d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def read_rounds(
    path: str,
) -> tuple[dict[str, list[tuple[int, str, str, str]]], dict[str, str]]:
    """Return {region: [(round_number, season, start, end)]}, {region: plit1_start}."""
    rounds: dict[str, list[tuple[int, str, str, str]]] = {}
    plit1_start: dict[str, str] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            region = r["region"]
            round_number = int(r["round_number"])
            rounds.setdefault(region, []).append(
                (round_number, r["season"], r["start_date"], r["end_date"])
            )
            if round_number == 1:
                plit1_start[region] = r["plit1_start"]
    missing = [r for r in rounds if not plit1_start.get(r)]
    if missing:
        raise SystemExit(f"plit1_start missing on round 1 for: {', '.join(missing)}")
    return rounds, plit1_start


def fetch_in_session_dates(
    client: bigquery.Client, region: str, academic_year: int
) -> set[datetime.date]:
    # int_students__calendar_day, NOT stg_powerschool__calendar_day: Miami is
    # Focus-only from AY2026, and the frozen PowerSchool archive still serves a
    # rolled-forward Miami calendar with phantom in-session days (23 in Jul 2026,
    # 7 on Aug 3-11 before Focus's real Aug 12 start, 18 on Jun 4-29 after its
    # real Jun 3 end). Those would move PLIT boundaries. Verified day-for-day
    # identical to the PowerSchool path for all three NJ regions in both SY25-26
    # and SY26-27, so NJ output is unchanged.
    query = """
        select distinct c.date_value
        from `teamster-332318.kipptaf_students.int_students__calendar_day` c
        inner join `teamster-332318.kipptaf_powerschool.stg_powerschool__schools` s
            on c.schoolid = s.school_number and c._dbt_source_project = s._dbt_source_project
        where s.schoolcity = @region and c.insession = 1
          and c.date_value between @year_start and @year_end
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("region", "STRING", region),
                bigquery.ScalarQueryParameter(
                    "year_start", "DATE", datetime.date(academic_year, 7, 1)
                ),
                bigquery.ScalarQueryParameter(
                    "year_end", "DATE", datetime.date(academic_year + 1, 7, 1)
                ),
            ]
        ),
    )
    return {row.date_value for row in job.result()}


def first_in_session_after(
    dates: set[datetime.date], after: datetime.date
) -> datetime.date:
    candidates = sorted(x for x in dates if x > after)
    if not candidates:
        raise ValueError(f"No in-session day found after {after}")
    return candidates[0]


def last_in_session_before(
    dates: set[datetime.date], before: datetime.date
) -> datetime.date:
    candidates = sorted((x for x in dates if x < before), reverse=True)
    if not candidates:
        raise ValueError(f"No in-session day found before {before}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--academic-year",
        type=int,
        required=True,
        help="academic year, labelled by the FALL (SY26-27 is 2026)",
    )
    parser.add_argument(
        "--rounds", required=True, help="round-dates TSV, see docstring"
    )
    parser.add_argument(
        "--band",
        action="append",
        help=(
            "grade band to emit, repeatable. Defaults to every K-8 band."
            " PLIT is emitted for each -- the internal method counts school days"
            " against it and now covers K-8, so every band needs it."
        ),
    )
    args = parser.parse_args()
    bands = args.band or DEFAULT_BANDS

    academic_year = str(args.academic_year)
    fiscal_year = str(args.academic_year + 1)
    # PowerSchool yearid convention: AY2026 (SY26-27) is 36.
    ps_year_id = str(args.academic_year - 1990)

    all_rounds, plit1_start = read_rounds(args.rounds)

    client = bigquery.Client(project="teamster-332318")

    out_rows = []
    for region, rounds in all_rounds.items():
        in_session = fetch_in_session_dates(client, region, args.academic_year)
        prev_round_end: datetime.date | None = None

        for round_number, season, r_start, r_end in rounds:
            if prev_round_end is None:
                plit_start = d(
                    plit1_start[region]
                )  # PLIT1 starts ON the BOY Benchmark start
            else:
                plit_start = first_in_session_after(in_session, prev_round_end)
            plit_end = last_in_session_before(in_session, d(r_start))

            for grade_band in bands:
                out_rows.append(
                    [
                        "LIT",
                        f"PLIT{round_number}",
                        season,
                        plit_start.isoformat(),
                        plit_end.isoformat(),
                        academic_year,
                        fiscal_year,
                        ps_year_id,
                        "",
                        "",
                        region,
                        grade_band,
                        "",
                    ]
                )
                out_rows.append(
                    [
                        "LIT",
                        f"LIT{round_number}",
                        season,
                        r_start,
                        r_end,
                        academic_year,
                        fiscal_year,
                        ps_year_id,
                        "",
                        "",
                        region,
                        grade_band,
                        "",
                    ]
                )
            prev_round_end = d(r_end)

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(f"rows written: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
