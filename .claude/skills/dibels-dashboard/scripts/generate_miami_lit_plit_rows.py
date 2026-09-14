"""Generate Miami `LIT`/`PLIT` rows for `reporting__terms`, for any academic year.

Miami's counterpart to `generate_nj_lit_plit_rows.py`. Kept separate rather than
folded into that script because Miami differs in three ways that would each need
a branch there, and that script's NJ output is already verified and pasted --
not worth the regression risk:

1. **Calendar source.** NJ resolves in-session days through
   `stg_powerschool__schools.schoolcity`, which is NULL for every Miami row
   (Miami is Focus, and `int_students__schools`'s Focus branch does not carry
   it). Miami reads `int_focus__calendar_day` joined to `int_focus__schools`,
   restricted to the ACTIVE schools via `max_syear is null` -- closed schools
   (Liberty, Sunrise) still carry a wider untrimmed calendar (212 days vs 182 in
   AY2026) that would move every boundary.
2. **Three grade bands in one pass.** The NJ script emits only the K-2 band.
   Per the user's decision, Miami keeps its AY2025 band scheme -- `0,1,2`
   carrying `LIT`+`PLIT`, and `3,4` / `5,6,7,8` carrying `LIT` only (`PLIT` is
   K-2-only; grades 3-8 take Amplify's aimline goals). Note this deliberately
   does NOT mirror the T&L doc's own K / 1-3 / 4-5 / 6-8 groupings, whose `1-3`
   band would straddle the K-2 / 3-8 boundary. Every Miami round shares
   identical dates across all bands, so the band split only matters for `PLIT`.
3. **`PLIT1.start`.** NJ copies the season's `BOY` Benchmark start date, which
   works only because NJ's `BOY` window opens on roughly the first day of
   school. Miami's `BOY` Benchmark sits a month into the year (`2026-09-08` in
   SY26-27), so that shortcut would put `PLIT1` a month late. Per the skill's
   Miami operating policy, derive it from the first in-session day of the
   academic year instead -- which is what AY2025 approximates (`PLIT1` started
   `2025-08-12` against a first in-session day of `2025-08-11`).

Round dates come from `--rounds`, a TSV transcribed from the T&L PM rounds doc's
Miami tab -- never derived or rolled forward. Confirm the doc is the right year
by checking its Benchmark windows against `reporting__terms` (SY26-27: BOY
9/8-9/25, MOY 1/5-1/22, EOY 4/26-5/14). Remember the Academics team labels
academic years by the SPRING, so "SY27" is `--academic-year 2026`.

`--rounds` columns (tab-separated, one header row):

    round_number   1-based, in calendar order
    season         `BOY->MOY` or `MOY->EOY` -- the MOY Benchmark window falls
                   between two rounds; everything at or before it is BOY->MOY
    start_date     ISO `YYYY-MM-DD`
    end_date       ISO `YYYY-MM-DD`

`rounds/sy2627_miami.tsv` is the SY26-27 table. Next year: copy it, edit the
dates, run.

`PLIT` boundaries are DERIVED with the same rule verified against real AY2025
data for NJ and Miami both (see the `dibels-dashboard` skill, "PLIT boundary
rule"):

    PLITn.start = first IN-SESSION day strictly after round n-1's end_date
                  (or, for PLIT1, the first in-session day of the year)
    PLITn.end   = last IN-SESSION day strictly before round n's start_date

The season boundary uses that same clean rule. Miami's AY2025 data confirms it
there exactly (`PLIT4` started the day after `LIT3` ended), unlike NJ, whose
AY2025 `PLIT5` shows an unexplained 1-day overlap.

Usage:
    uv run --with google-cloud-bigquery python3 \
        .claude/skills/dibels-dashboard/scripts/generate_miami_lit_plit_rows.py \
        --academic-year 2026 \
        --rounds .claude/skills/dibels-dashboard/scripts/rounds/sy2627_miami.tsv \
        --out out.tsv
"""

import argparse
import csv
import datetime

from google.cloud import bigquery

REGION = "Miami"

# Grade bands, and whether each carries PLIT rows.
# The doc groups Miami K / 1-3 / 4-5 / 6-8. Every Miami round shares the same
# dates across bands, so the split only decides which grades a PLIT row
# covers -- and the internal method now covers K-8, so every band carries it.
BANDS = [("0", True), ("1,2,3", True), ("4,5", True), ("6,7,8", True)]


def d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def read_rounds(path: str) -> list[tuple[int, str, str, str]]:
    with open(path, newline="") as f:
        return [
            (int(r["round_number"]), r["season"], r["start_date"], r["end_date"])
            for r in csv.DictReader(f, delimiter="\t")
        ]


def fetch_in_session_dates(
    client: bigquery.Client, academic_year: int
) -> set[datetime.date]:
    query = """
        select distinct cd.school_date
        from `teamster-332318.kipptaf_focus.int_focus__calendar_day` as cd
        inner join `teamster-332318.kipptaf_focus.int_focus__schools` as f
            on cd.schoolid = f.id
        inner join
            `teamster-332318.kipptaf_google_sheets.stg_google_sheets__people__locations` as loc
            on f.school_number = loc.focus_school_id
        where f.max_syear is null and cd.academic_year = @academic_year
    """
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("academic_year", "INT64", academic_year)
            ]
        ),
    )
    return {row.school_date for row in job.result()}


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
    args = parser.parse_args()

    academic_year = str(args.academic_year)
    fiscal_year = str(args.academic_year + 1)
    # PowerSchool yearid convention: AY2026 (SY26-27) is 36.
    ps_year_id = str(args.academic_year - 1990)

    rounds = read_rounds(args.rounds)

    client = bigquery.Client(project="teamster-332318")
    in_session = fetch_in_session_dates(client, args.academic_year)
    first_day = min(in_session)

    plit: dict[int, tuple[str, str]] = {}
    skipped: list[int] = []
    prev_round_end: datetime.date | None = None
    for round_number, _season, r_start, r_end in rounds:
        if prev_round_end is None:
            plit_start = first_day
        else:
            plit_start = first_in_session_after(in_session, prev_round_end)
        plit_end = last_in_session_before(in_session, d(r_start))
        # A round can legitimately have NO pre-round window. When T&L extends a
        # round to butt up against the next one -- SY26-27 PM #2 runs 10/26 to
        # 11/06 and PM #3 starts 11/09 -- there are no school days left between
        # them, so the derived start lands after the derived end. Skip the row
        # rather than emit an inverted range: the days are not lost, they now sit
        # inside the previous round's LIT window, and pm_round_days maps LITn and
        # PLITn to the same round anyway. Nothing downstream filters on PLIT.
        if plit_start > plit_end:
            skipped.append(round_number)
        else:
            plit[round_number] = (plit_start.isoformat(), plit_end.isoformat())
        prev_round_end = d(r_end)

    def row(code: str, season: str, start: str, end: str, grade_band: str) -> list[str]:
        return [
            "LIT",
            code,
            season,
            start,
            end,
            academic_year,
            fiscal_year,
            ps_year_id,
            "",
            "",
            REGION,
            grade_band,
            "",
        ]

    out_rows = []
    for grade_band, carries_plit in BANDS:
        for round_number, season, r_start, r_end in rounds:
            if carries_plit and round_number in plit:
                p_start, p_end = plit[round_number]
                out_rows.append(
                    row(f"PLIT{round_number}", season, p_start, p_end, grade_band)
                )
            out_rows.append(
                row(f"LIT{round_number}", season, r_start, r_end, grade_band)
            )

    with open(args.out, "w") as f:
        for out_row in out_rows:
            f.write("\t".join(out_row) + "\n")

    print(f"first in-session day AY{academic_year}: {first_day}")
    print("derived PLIT windows:")
    for round_number, (p_start, p_end) in plit.items():
        print(f"  PLIT{round_number:<2} {p_start} -> {p_end}")
    if skipped:
        print(
            "PLIT skipped, no school days between rounds: "
            + ", ".join(f"PLIT{n}" for n in skipped)
        )
    print(f"rows written: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
