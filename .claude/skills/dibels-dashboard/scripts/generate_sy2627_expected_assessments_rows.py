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

# Miami, T&L SY27 doc, Miami tab. Three shapes rather than 11 literals, because
# the doc really is this regular -- only round 1 and the season change differ:
#
#   round 1        grade 1 gets NWF alone (the doc splits "G1" from "G2-3")
#   rounds 2-5     grades 1-3 get NWF + ORF
#   rounds 6-11    NWF drops from grades 1-3, and Maze is added to 4-8
#
# Cohorts alternate strictly by round: odd rounds test Below + Well Below, even
# rounds Well Below only. Unlike NJ, this applies to K-2 as well as 3-8, which
# is why the K-2 scaffold branch reads the round's cohort (see k2_cohort).
MIAMI_ROUND_1 = {
    0: ["PSF", "NWF"],
    1: ["NWF"],
    2: ["NWF", "ORF"],
    3: ["NWF", "ORF"],
    4: ["ORF"],
    5: ["ORF"],
    6: ["ORF"],
    7: ["ORF"],
    8: ["ORF"],
}
MIAMI_EARLY = {
    0: ["PSF", "NWF"],
    1: ["NWF", "ORF"],
    2: ["NWF", "ORF"],
    3: ["NWF", "ORF"],
    4: ["ORF"],
    5: ["ORF"],
    6: ["ORF"],
    7: ["ORF"],
    8: ["ORF"],
}
MIAMI_LATE = {
    0: ["PSF", "NWF"],
    1: ["ORF"],
    2: ["ORF"],
    3: ["ORF"],
    4: ["ORF", "MAZE"],
    5: ["ORF", "MAZE"],
    6: ["ORF", "MAZE"],
    7: ["ORF", "MAZE"],
    8: ["ORF", "MAZE"],
}

# (round_number, start, end, measures-by-grade). The MOY Benchmark window
# (1/5 - 1/22) falls between rounds 5 and 6, so 1-5 are BOY->MOY and 6-11 are
# MOY->EOY.
MIAMI_SCHEDULE = [
    (1, "2026-10-05", "2026-10-09", MIAMI_ROUND_1),
    (2, "2026-10-26", "2026-11-06", MIAMI_EARLY),
    (3, "2026-11-09", "2026-11-13", MIAMI_EARLY),
    (4, "2026-11-30", "2026-12-04", MIAMI_EARLY),
    (5, "2026-12-14", "2026-12-18", MIAMI_EARLY),
    (6, "2027-02-01", "2027-02-05", MIAMI_LATE),
    (7, "2027-02-15", "2027-02-19", MIAMI_LATE),
    (8, "2027-03-01", "2027-03-05", MIAMI_LATE),
    (9, "2027-03-15", "2027-03-19", MIAMI_LATE),
    (10, "2027-04-05", "2027-04-09", MIAMI_LATE),
    (11, "2027-04-19", "2027-04-23", MIAMI_LATE),
]

MIAMI_SEASON_SPLIT = 5

MIAMI_ROUNDS = [
    (
        round_number,
        "BOY->MOY" if round_number <= MIAMI_SEASON_SPLIT else "MOY->EOY",
        start,
        end,
        {
            grade: (measures, BOTH if round_number % 2 == 1 else WBB)
            for grade, measures in by_grade.items()
        },
    )
    for round_number, start, end, by_grade in MIAMI_SCHEDULE
]

REGION_ROUNDS = {
    "Newark": NEWARK_PATERSON_ROUNDS,
    "Paterson": NEWARK_PATERSON_ROUNDS,
    "Camden": CAMDEN_ROUNDS,
    "Miami": MIAMI_ROUNDS,
}

K2_GRADES = {0, 1, 2}


def k2_cohort(grades: dict, grade: int) -> str:
    """Cohort for a K-2 scaffold row.

    NJ K-2 is `Both` in every round, but Miami alternates by round (odd rounds
    test Below + Well Below, even rounds Well Below only), so this cannot be
    hardcoded. When the grade is absent from the round entirely -- a
    scaffold-fill row that exists only for goal-trajectory continuity -- borrow
    the cohort from another K-2 grade in the same round rather than a
    round-level cohort: NJ rounds are NOT uniform across bands (round 1 is
    `Both` for K-2 and `Well Below` for 3-8).
    """
    entry = grades.get(grade)
    if entry:
        return entry[1]
    for sibling in sorted(K2_GRADES):
        if sibling in grades:
            return grades[sibling][1]
    return BOTH


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


def emit(
    rows: list[list[str]], base: list[str], cohort: str, single: bool = False
) -> None:
    """Append the cohort copies of a row, or one cohort-free row.

    The round data carries ONE measure list per grade/round plus a cohort tag,
    never per-cohort measure lists -- so single-row mode is just dropping the
    tag, not choosing between cohorts.
    """
    if single:
        rows.append(list(base))
        return
    levels = ["Below", "Well Below"] if cohort == BOTH else ["Well Below"]
    for level in levels:
        r = list(base)
        r[7] = level
        rows.append(r)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--single-rows",
        action="store_true",
        help=(
            "Emit the old 16-column shape for the Expected Assessments tab: one"
            " row per grade/round/measure with no assessment_type or"
            " measure_standard_level, and the goal scaffold applied to every"
            " grade. Use this for the internal-only fallback, where 3-8 needs"
            " the same trajectory scaffold K-2 gets."
        ),
    )
    parser.add_argument(
        "--regions",
        default=",".join(REGION_ROUNDS),
        help=(
            "Comma-separated regions to emit. Defaults to all. Use this to emit"
            " one region's rows without regenerating another's already-pasted"
            " output."
        ),
    )
    args = parser.parse_args()

    scaffold_grades = set(range(0, 9)) if args.single_rows else K2_GRADES

    selected = [r.strip() for r in args.regions.split(",") if r.strip()]
    unknown = [r for r in selected if r not in REGION_ROUNDS]
    if unknown:
        raise SystemExit(f"unknown region(s): {', '.join(unknown)}")

    out_rows: list[list[str]] = []

    for region in selected:
        rounds = REGION_ROUNDS[region]
        # -- grades 3-8: only rounds actually listed, pm_goal_include always blank --
        for round_number, season, start, _end, grades in rounds:
            for grade, (measure_codes, cohort) in grades.items():
                if grade in scaffold_grades:
                    continue
                for ms in measure_rows(measure_codes):
                    base = base_row(region, grade, round_number, season, start, "", ms)
                    emit(out_rows, base, cohort, args.single_rows)

        # -- grades K-2: scaffold every round per season for any measure tested
        # at least once that season; pm_goal_include=false on untested rounds --
        seasons: dict[str, list[tuple]] = {}
        for round_number, season, start, end, grades in rounds:
            seasons.setdefault(season, []).append((round_number, start, end, grades))

        for season, season_rounds in seasons.items():
            for grade in scaffold_grades:
                tested_measures: set[str] = set()
                for _round_number, _start, _end, grades in season_rounds:
                    if grade in grades:
                        tested_measures.update(grades[grade][0])

                for measure_code in sorted(tested_measures):
                    for ms in MEASURE_MAP[measure_code]:
                        for round_number, start, _end, grades in season_rounds:
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
                            emit(
                                out_rows,
                                base,
                                k2_cohort(grades, grade),
                                args.single_rows,
                            )

    with open(args.out, "w") as f:
        for row in out_rows:
            # the old tab has neither assessment_type (derived) nor
            # measure_standard_level; dropping 6 and 7 leaves its 16-column order
            out = (
                [v for i, v in enumerate(row) if i not in (6, 7)]
                if args.single_rows
                else row
            )
            f.write("\t".join(out) + "\n")

    print(f"rows written: {len(out_rows)} -> {args.out}")


if __name__ == "__main__":
    main()
