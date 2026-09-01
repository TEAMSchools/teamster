"""Generate SY26-27 PM rows for the "Expected Assessments" tab, NJ regions
only (Camden, Newark, Paterson) -- Miami excluded, see the dibels-dashboard
skill.

Round/grade/measure data below is transcribed directly from the confirmed
T&L PM rounds doc ("SY27 - DIBELS PM Rounds - All Regions"). Two behaviors
differ by grade band, confirmed with the user against real AY2025 data
before writing this:

**Grades 3-8** (aimline): one row per (grade, round, measure) ONLY for
rounds where the doc actually lists that grade+measure. `pm_goal_include`
is always NULL -- aimline supplies the goal directly, this field no longer
gates anything for these grades.

**Grades K-2** (in-house collective-average calc, matches the PLIT-is-K-2-
only pattern): for every measure tested AT LEAST ONCE in a season for a
grade, a row exists for EVERY round of that season -- rounds where the
measure isn't in that round's tested set still get a row, with
`pm_goal_include = false` (goal calculated for trajectory continuity, not
displayed downstream). Rounds where it IS tested get `pm_goal_include =
null`. Verified against real data: Camden/Newark/Paterson AY2025 grade 0
PSF, BOY->MOY -- rounds 1-3 have `pm_goal_include = null`,
`assessment_include = null`; round 4 (PSF not tested that round) STILL has
a row, `assessment_include = null`, `pm_goal_include = false`.

Every row is duplicated into `measure_standard_level` = `Below` and
`Well Below`, per the cohort column each round/grade specifies in the doc
(`Both` -> both copies; `Well Below only` -> just the one). K-2 is always
`Both` for all three regions, every round, per the doc.

`pm_goal_criteria` = `AND` for every row this year (confirmed with the
user -- T&L requires meeting all tested standards per round, network-wide,
not a mix of AND/OR).

`month_round` derives from each round's own start date -- no PD-day
complication here, that only affects Benchmark rows (see
fix_expected_assessments_benchmark_month_round.py).

Usage:
    uv run python3 \
        .claude/skills/dibels-dashboard/scripts/generate_sy2627_expected_assessments_rows.py \
        --out out.tsv
"""

import argparse
import datetime

ACADEMIC_YEAR = "2026"
GRADE_LEVEL_TEXT = {
    0: "K",
    1: "1",
    2: "2",
    3: "3",
    4: "4",
    5: "5",
    6: "6",
    7: "7",
    8: "8",
}

MEASURE_MAP = {
    "PSF": ["PSF_Phonological Awareness_Phonemic Awareness (PSF)"],
    "NWF": [
        "NWF_Nonsense Word Fluency_Letter Sounds (NWF-CLS)",
        "NWF_Nonsense Word Fluency_Decoding (NWF-WRC)",
    ],
    "ORF": [
        "ORF_Oral Reading Fluency_Reading Fluency (ORF)",
        "ORF_Oral Reading Fluency_Reading Accuracy (ORF-Accu)",
    ],
    "MAZE": ["Comprehension_Comprehension_Reading Comprehension (Maze)"],
    "WRF": ["WRF_Word Reading Fluency_Word Reading (WRF)"],
}

BOTH = "Both"
WBB = "Well Below"

# region -> [ (round_number, season, start, end, {grade: (measure_codes, cohort)}) ]
NEWARK_PATERSON_ROUNDS = [
    (
        1,
        "BOY->MOY",
        "2026-09-28",
        "2026-10-02",
        {
            0: (["PSF"], BOTH),
            1: (["PSF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], WBB),
            4: (["ORF"], WBB),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        2,
        "BOY->MOY",
        "2026-10-19",
        "2026-10-23",
        {
            0: (["PSF"], BOTH),
            1: (["PSF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF", "MAZE"], BOTH),
            4: (["ORF", "MAZE"], BOTH),
            5: (["ORF", "MAZE"], BOTH),
            6: (["ORF", "MAZE"], BOTH),
            7: (["ORF", "MAZE"], BOTH),
            8: (["ORF", "MAZE"], BOTH),
        },
    ),
    (
        3,
        "BOY->MOY",
        "2026-11-16",
        "2026-11-20",
        {
            0: (["PSF"], BOTH),
            1: (["PSF", "NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], WBB),
            4: (["ORF"], WBB),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        4,
        "BOY->MOY",
        "2026-12-14",
        "2026-12-18",
        {
            0: (["NWF"], BOTH),
            1: (["NWF"], BOTH),
            2: (["NWF", "ORF"], BOTH),
            3: (["NWF", "ORF"], BOTH),
            4: (["ORF"], BOTH),
            5: (["ORF"], BOTH),
            6: (["ORF"], BOTH),
            7: (["ORF"], BOTH),
            8: (["ORF"], BOTH),
        },
    ),
    (
        5,
        "MOY->EOY",
        "2027-02-01",
        "2027-02-05",
        {
            0: (["NWF"], BOTH),
            1: (["NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], WBB),
            4: (["ORF"], WBB),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        6,
        "MOY->EOY",
        "2027-02-22",
        "2027-02-26",
        {
            0: (["NWF"], BOTH),
            1: (["NWF", "ORF"], BOTH),
            2: (["NWF", "ORF"], BOTH),
            3: (["NWF", "ORF", "MAZE"], BOTH),
            4: (["ORF", "MAZE"], BOTH),
            5: (["ORF", "MAZE"], BOTH),
            6: (["ORF", "MAZE"], BOTH),
            7: (["ORF", "MAZE"], BOTH),
            8: (["ORF", "MAZE"], BOTH),
        },
    ),
    (
        7,
        "MOY->EOY",
        "2027-03-15",
        "2027-03-19",
        {
            0: (["NWF", "WRF"], BOTH),
            1: (["NWF", "ORF"], BOTH),
            2: (["NWF", "ORF"], BOTH),
            3: (["NWF", "ORF"], BOTH),
            4: (["ORF"], BOTH),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        8,
        "MOY->EOY",
        "2027-05-03",
        "2027-05-07",
        {
            0: (["NWF", "WRF"], BOTH),
            1: (["ORF"], BOTH),
            2: (["ORF"], BOTH),
            # 3-8 not tested (test prep) -- omitted entirely
        },
    ),
]

CAMDEN_ROUNDS = [
    (
        1,
        "BOY->MOY",
        "2026-09-28",
        "2026-10-02",
        {
            0: (["PSF"], BOTH),
            1: (["PSF", "NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], BOTH),
            4: (["ORF"], BOTH),
            5: (["ORF"], BOTH),
            6: (["ORF"], BOTH),
            7: (["ORF"], BOTH),
            8: (["ORF"], BOTH),
        },
    ),
    (
        2,
        "BOY->MOY",
        "2026-10-26",
        "2026-10-30",
        {
            0: (["PSF"], BOTH),
            1: (["PSF", "NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], WBB),
            4: (["ORF"], WBB),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        3,
        "BOY->MOY",
        "2026-11-16",
        "2026-11-20",
        {
            0: (["PSF"], BOTH),
            1: (["PSF", "NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["NWF", "ORF"], BOTH),
            4: (["ORF"], BOTH),
            5: (["ORF"], BOTH),
            6: (["ORF"], BOTH),
            7: (["ORF"], BOTH),
            8: (["ORF"], BOTH),
        },
    ),
    (
        4,
        "MOY->EOY",
        "2027-03-01",
        "2027-03-05",
        {
            0: (["NWF"], BOTH),
            1: (["NWF"], BOTH),
            2: (["NWF"], BOTH),
            3: (["ORF"], WBB),
            4: (["ORF"], WBB),
            5: (["ORF"], WBB),
            6: (["ORF"], WBB),
            7: (["ORF"], WBB),
            8: (["ORF"], WBB),
        },
    ),
    (
        5,
        "MOY->EOY",
        "2027-04-05",
        "2027-04-09",
        {
            0: (["NWF"], BOTH),
            1: (["NWF", "ORF"], BOTH),
            2: (["NWF", "ORF"], BOTH),
            3: (["ORF"], BOTH),
            4: (["ORF"], BOTH),
            5: (["ORF"], BOTH),
            6: (["ORF"], BOTH),
            7: (["ORF"], BOTH),
            8: (["ORF"], BOTH),
        },
    ),
    (
        6,
        "MOY->EOY",
        "2027-05-03",
        "2027-05-07",
        {
            0: (["NWF"], BOTH),
            1: (["NWF", "ORF"], BOTH),
            2: (["NWF", "ORF"], BOTH),
            # 3-8 not tested (test prep) -- omitted entirely
        },
    ),
]

REGION_ROUNDS = {
    "Newark": NEWARK_PATERSON_ROUNDS,
    "Paterson": NEWARK_PATERSON_ROUNDS,
    "Camden": CAMDEN_ROUNDS,
}

K2_GRADES = {0, 1, 2}


def month_of(date_str: str) -> str:
    return datetime.date.fromisoformat(date_str).strftime("%B")


def measure_rows(measure_codes: list[str]) -> list[str]:
    out = []
    for code in measure_codes:
        out.extend(MEASURE_MAP[code])
    return out


def base_row(
    region: str,
    grade: int,
    round_number: int,
    season: str,
    start: str,
    pm_goal_include: str,
    measure_standard: str,
) -> list[str]:
    return [
        ACADEMIC_YEAR,
        region,
        str(grade),
        "Official",
        "ELA",
        "Reading",
        "PM",
        "",  # measure_standard_level filled by caller
        measure_standard,
        f"LIT{round_number}",
        season,
        month_of(start),
        "Text Study",
        "Reading",
        "ENG",
        "",  # assessment_include
        pm_goal_include,
        "AND",
    ]


def emit(rows: list[list[str]], base: list[str], cohort: str) -> None:
    levels = ["Below", "Well Below"] if cohort == BOTH else ["Well Below"]
    for level in levels:
        r = list(base)
        r[7] = level
        rows.append(r)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_rows: list[list[str]] = []

    for region, rounds in REGION_ROUNDS.items():
        # -- grades 3-8: only rounds actually listed, pm_goal_include always blank --
        for round_number, season, start, end, grades in rounds:
            for grade, (measure_codes, cohort) in grades.items():
                if grade in K2_GRADES:
                    continue
                for ms in measure_rows(measure_codes):
                    base = base_row(region, grade, round_number, season, start, "", ms)
                    emit(out_rows, base, cohort)

        # -- grades K-2: scaffold every round per season for any measure tested
        # at least once that season; pm_goal_include=false on untested rounds --
        seasons: dict[str, list[tuple]] = {}
        for round_number, season, start, end, grades in rounds:
            seasons.setdefault(season, []).append((round_number, start, end, grades))

        for season, season_rounds in seasons.items():
            for grade in K2_GRADES:
                tested_measures: set[str] = set()
                for round_number, start, end, grades in season_rounds:
                    if grade in grades:
                        tested_measures.update(grades[grade][0])

                for measure_code in sorted(tested_measures):
                    for ms in MEASURE_MAP[measure_code]:
                        for round_number, start, end, grades in season_rounds:
                            grade_entry = grades.get(grade)
                            if grade_entry and measure_code in grade_entry[0]:
                                pm_goal_include = ""
                            else:
                                pm_goal_include = "false"
                            base = base_row(
                                region,
                                grade,
                                round_number,
                                season,
                                start,
                                pm_goal_include,
                                ms,
                            )
                            emit(out_rows, base, BOTH)

    with open(args.out, "w") as f:
        for row in out_rows:
            f.write("\t".join(row) + "\n")

    print(f"rows written: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
