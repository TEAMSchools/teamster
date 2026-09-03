"""Generate SY26-27 Miami `LIT`/`PLIT` rows for `reporting__terms`.

Miami's counterpart to `generate_sy2627_k2_lit_plit_rows.py`. Kept separate
rather than folded into that script because Miami differs in three ways that
would each need a branch there, and that script's NJ output is already verified
and pasted -- not worth the regression risk:

1. **Calendar source.** NJ resolves in-session days through
   `stg_powerschool__schools.schoolcity`, which is NULL for every Miami row
   (Miami is Focus, and `int_students__schools`'s Focus branch does not carry
   it). Miami reads `int_focus__calendar_day` joined to `int_focus__schools`,
   restricted to the five ACTIVE schools via `max_syear is null` -- the two
   closed schools (Liberty, Sunrise) still carry a wider untrimmed AY2026
   calendar (212 days vs 182) that would move every boundary.
2. **Three grade bands in one pass.** The NJ script emits only the K-2 band.
   Per the user's decision, Miami keeps its AY2025 band scheme -- `0,1,2`
   carrying `LIT`+`PLIT`, and `3,4` / `5,6,7,8` carrying `LIT` only (`PLIT` is
   K-2-only; grades 3-8 take Amplify's aimline goals). Note this deliberately
   does NOT mirror the T&L doc's own K / 1-3 / 4-5 / 6-8 groupings, whose `1-3`
   band would straddle the K-2 / 3-8 boundary. Every Miami round shares
   identical dates across all bands, so the band split only matters for `PLIT`.
3. **`PLIT1.start`.** NJ copies the season's `BOY` Benchmark start date, which
   works only because NJ's `BOY` window opens on roughly the first day of
   school. Miami's `BOY` Benchmark sits a month into the year (`2026-09-08`),
   so that shortcut would put `PLIT1` a month late. Per the skill's Miami
   operating policy, derive it from the first in-session day of the academic
   year instead -- which is what AY2025 approximates (`PLIT1` started
   `2025-08-12` against a first in-session day of `2025-08-11`).

Round dates are transcribed from the T&L doc
`12ZDlAJY_IgSS4yElBAFWouJ6_M8982j1Fb1B93-INjU`, "SY27 - DIBELS PM Rounds - All
Regions", Miami tab -- never derived or rolled forward. Confirmed as the AY2026
doc by its Benchmark windows matching `reporting__terms` exactly (BOY 9/8-9/25,
MOY 1/5-1/22, EOY 4/26-5/14). Remember the Academics team labels academic years
by the SPRING, so "SY27" is `academic_year = 2026`.

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
        .claude/skills/dibels-dashboard/scripts/generate_sy2627_miami_lit_plit_rows.py \
        --out out.tsv
"""

import argparse
import datetime

from google.cloud import bigquery

REGION = "Miami"
ACADEMIC_YEAR = "2026"
FISCAL_YEAR = "2027"
PS_YEAR_ID = "36"

# Grade bands, and whether each carries PLIT rows. PLIT is K-2-only.
BANDS = [("0,1,2", True), ("3,4", False), ("5,6,7,8", False)]

# (round_number, start, end) -- T&L SY27 doc, Miami tab.
ROUNDS = [
    (1, "2026-10-05", "2026-10-09"),
    (2, "2026-10-26", "2026-11-06"),
    (3, "2026-11-09", "2026-11-13"),
    (4, "2026-11-30", "2026-12-04"),
    (5, "2026-12-14", "2026-12-18"),
    (6, "2027-02-01", "2027-02-05"),
    (7, "2027-02-15", "2027-02-19"),
    (8, "2027-03-01", "2027-03-05"),
    (9, "2027-03-15", "2027-03-19"),
    (10, "2027-04-05", "2027-04-09"),
    (11, "2027-04-19", "2027-04-23"),
]

# The MOY Benchmark window (1/5 - 1/22) falls between PM #5 and PM #6, so
# rounds 1-5 are BOY->MOY and rounds 6-11 are MOY->EOY.
SEASON_SPLIT = 5


def d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def fetch_in_session_dates(client: bigquery.Client) -> set[datetime.date]:
    query = """
        select distinct cd.school_date
        from `teamster-332318.kipptaf_focus.int_focus__calendar_day` as cd
        inner join `teamster-332318.kipptaf_focus.int_focus__schools` as f
            on cd.schoolid = f.id
        inner join
            `teamster-332318.kipptaf_google_sheets.stg_google_sheets__people__locations` as loc
            on f.school_number = loc.focus_school_id
        where f.max_syear is null and cd.academic_year = 2026
    """
    return {row.school_date for row in client.query(query).result()}


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


def row(code: str, season: str, start: str, end: str, grade_band: str) -> list[str]:
    return [
        "LIT",
        code,
        season,
        start,
        end,
        ACADEMIC_YEAR,
        FISCAL_YEAR,
        PS_YEAR_ID,
        "",
        "",
        REGION,
        grade_band,
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    client = bigquery.Client(project="teamster-332318")
    in_session = fetch_in_session_dates(client)
    first_day = min(in_session)

    plit: dict[int, tuple[str, str]] = {}
    skipped: list[int] = []
    prev_round_end: datetime.date | None = None
    for round_number, r_start, r_end in ROUNDS:
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

    out_rows = []
    for grade_band, carries_plit in BANDS:
        for round_number, r_start, r_end in ROUNDS:
            season = "BOY->MOY" if round_number <= SEASON_SPLIT else "MOY->EOY"
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

    print(f"first in-session day AY2026: {first_day}")
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
