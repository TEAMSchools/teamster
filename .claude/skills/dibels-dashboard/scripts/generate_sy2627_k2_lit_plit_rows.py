"""Generate SY26-27 K-2 `LIT`/`PLIT` rows for `reporting__terms`, NJ regions
only (Camden, Newark, Paterson) -- Miami excluded, see module docstring below.

`LIT` round dates are transcribed directly from the confirmed T&L PM rounds
doc ("SY27 - DIBELS PM Rounds - All Regions") -- hardcoded in ROUNDS below,
one list per region since Newark/Paterson share a grid and Camden has its
own. Benchmark BOY/MOY/EOY rows for AY2026 already exist in
`reporting__terms` (added by an earlier rollover pass this session) and are
not touched here.

`PLIT` dates are DERIVED, not transcribed, using the boundary rule verified
against real AY2025 `reporting__terms` data (see the `dibels-dashboard`
skill, "PLIT boundary rule" -- matched 7 real boundaries exactly across
Camden, Newark and Paterson before this script was written):

    PLITn.start = first IN-SESSION day strictly after the previous round's
                  end_date (round n-1, or the season's own Benchmark start
                  for PLIT1)
    PLITn.end   = last IN-SESSION day strictly before round n's start_date

This holds cleanly WITHIN a season. Crossing from BOY->MOY into MOY->EOY
(the first PLIT of the second season) is an open question -- last year's
real data shows a 1-day overlap there (the new season's PLIT1 starts one
calendar day before the old season's last round officially ends) that was
never explained and is NOT replicated here. This script applies the same
clean rule at the season boundary too (day after the last BOY->MOY round
ends). If that turns out wrong, only the one row per region needs
correcting once the real reason for last year's overlap is known.

PD days are deliberately NOT excluded from the boundary calculation.
Checked against last year's real numbers first: the frozen PM goals sheet
does NOT reliably exclude PD days either (Camden round 2's frozen
`pm_round_days` matched a naive PD-day-inclusive count exactly), so
building PD-day awareness in here would make this MORE correct than
precedent, not consistent with it. Revisit if that's ever explicitly
decided otherwise.

Miami is excluded entirely -- its PLIT structure is different (windows
spanning entire breaks) and unverified; it needs its own pass.

Usage:
    uv run --with google-cloud-bigquery python3 \
        .claude/skills/dibels-dashboard/scripts/generate_sy2627_k2_lit_plit_rows.py \
        --out out.tsv
"""

import argparse
import datetime

from google.cloud import bigquery

ACADEMIC_YEAR = "2026"
FISCAL_YEAR = "2027"
GRADE_BAND = "0,1,2"
PS_YEAR_ID = "36"

# (region, [(round_number, start, end), ...])
ROUNDS = {
    "Newark": [
        (1, "2026-09-28", "2026-10-02"),
        (2, "2026-10-19", "2026-10-23"),
        (3, "2026-11-16", "2026-11-20"),
        (4, "2026-12-14", "2026-12-18"),
        (5, "2027-02-01", "2027-02-05"),
        (6, "2027-02-22", "2027-02-26"),
        (7, "2027-03-15", "2027-03-19"),
        (8, "2027-05-03", "2027-05-07"),
    ],
    "Paterson": [
        (1, "2026-09-28", "2026-10-02"),
        (2, "2026-10-19", "2026-10-23"),
        (3, "2026-11-16", "2026-11-20"),
        (4, "2026-12-14", "2026-12-18"),
        (5, "2027-02-01", "2027-02-05"),
        (6, "2027-02-22", "2027-02-26"),
        (7, "2027-03-15", "2027-03-19"),
        (8, "2027-05-03", "2027-05-07"),
    ],
    "Camden": [
        (1, "2026-09-28", "2026-10-02"),
        (2, "2026-10-26", "2026-10-30"),
        (3, "2026-11-16", "2026-11-20"),
        (4, "2027-03-01", "2027-03-05"),
        (5, "2027-04-05", "2027-04-09"),
        (6, "2027-05-03", "2027-05-07"),
    ],
}

# Season boundary per region: the round_number after which BOY->MOY ends and
# MOY->EOY begins. Newark/Paterson: 4 BOY->MOY + 4 MOY->EOY. Camden: 3 + 3.
SEASON_SPLIT = {"Newark": 4, "Paterson": 4, "Camden": 3}

# Season1's own Benchmark BOY start date (PLIT1.start anchor), from the
# AY2026 LIT1/BOY rows already in reporting_terms.
BOY_START = {"Newark": "2026-08-19", "Paterson": "2026-08-19", "Camden": "2026-08-13"}


def d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def fetch_in_session_dates(client: bigquery.Client, region: str) -> set[datetime.date]:
    query = """
        select distinct c.date_value
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__calendar_day` c
        inner join `teamster-332318.kipptaf_powerschool.stg_powerschool__schools` s
            on c.schoolid = s.school_number and c._dbt_source_project = s._dbt_source_project
        where s.schoolcity = @region and c.insession = 1
          and c.date_value between '2026-07-01' and '2027-07-01'
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("region", "STRING", region)]
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
    args = parser.parse_args()

    client = bigquery.Client(project="teamster-332318")

    out_rows = []
    for region, rounds in ROUNDS.items():
        in_session = fetch_in_session_dates(client, region)
        season1_len = SEASON_SPLIT[region]
        prev_round_end: datetime.date | None = None

        for round_number, r_start, r_end in rounds:
            season = "BOY->MOY" if round_number <= season1_len else "MOY->EOY"

            if prev_round_end is None:
                plit_start = d(
                    BOY_START[region]
                )  # PLIT1 starts ON the BOY Benchmark start
            else:
                plit_start = first_in_session_after(in_session, prev_round_end)
            plit_end = last_in_session_before(in_session, d(r_start))

            out_rows.append(
                [
                    "LIT",
                    f"PLIT{round_number}",
                    season,
                    plit_start.isoformat(),
                    plit_end.isoformat(),
                    ACADEMIC_YEAR,
                    FISCAL_YEAR,
                    PS_YEAR_ID,
                    "",
                    "",
                    region,
                    GRADE_BAND,
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
                    ACADEMIC_YEAR,
                    FISCAL_YEAR,
                    PS_YEAR_ID,
                    "",
                    "",
                    region,
                    GRADE_BAND,
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
