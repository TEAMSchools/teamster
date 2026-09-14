"""Generate PM rows for the "Expected Assessments" tab, for any academic year.

Round/grade/measure data comes from `--rounds`, a TSV transcribed directly from
the confirmed T&L PM rounds doc for the year. Two behaviors differ by grade
band, confirmed with the user against real AY2025 data before writing this:

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
(`Both` -> both copies; `Well Below only` -> just the one).

`pm_goal_criteria` = `AND` for every row (confirmed with the user -- T&L
requires meeting all tested standards per round, network-wide, not a mix of
AND/OR).

`month_round` derives from each round's own start date -- no PD-day
complication here, that only affects Benchmark rows.

`--rounds` columns (tab-separated, one header row, one row per
region/round/grade; regions and grades in output order):

    region         `Newark`, `Paterson`, `Camden` or `Miami`
    round_number   1-based, in calendar order within the region
    season         `BOY->MOY` or `MOY->EOY`
    start_date     ISO `YYYY-MM-DD`
    end_date       ISO `YYYY-MM-DD` (carried for reference; unused downstream)
    grade          0-8, `0` = K
    measures       comma-separated measure codes, see MEASURE_MAP below
    cohort         `Both` or `Well Below`

Omit a (round, grade) pair entirely when the doc does not test it -- the K-2
scaffold below fills it back in with `pm_goal_include = false`, and 3-8 gets no
row at all.

`rounds/sy2627_expected_assessments.tsv` is the SY26-27 table. Next year: copy
it, edit the dates and grids, run.

Usage:
    uv run python3 \
        .claude/skills/dibels-dashboard/scripts/generate_pm_expected_assessments_rows.py \
        --academic-year 2026 \
        --rounds .claude/skills/dibels-dashboard/scripts/rounds/sy2627_expected_assessments.tsv \
        --out out.tsv
"""

import argparse
import csv
import datetime

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

K2_GRADES = {0, 1, 2}


def read_rounds(path: str) -> dict[str, list[tuple]]:
    """Read the round grid into {region: [(round_number, season, start, end,
    {grade: (measure_codes, cohort)})]}, preserving file order.

    Columns are documented in the module docstring.
    """
    regions: dict[str, list[tuple]] = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            region = r["region"]
            round_number = int(r["round_number"])
            rounds = regions.setdefault(region, [])
            if not rounds or rounds[-1][0] != round_number:
                rounds.append(
                    (round_number, r["season"], r["start_date"], r["end_date"], {})
                )
            rounds[-1][4][int(r["grade"])] = (r["measures"].split(","), r["cohort"])
    return regions


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
    academic_year: str,
    region: str,
    grade: int,
    round_number: int,
    season: str,
    start: str,
    pm_goal_include: str,
    measure_standard: str,
) -> list[str]:
    return [
        academic_year,
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
    # full benchmark-level names, matching the live sheet and
    # int_amplify__benchmark_student_summary.overall_aimline_composite_level --
    # the short forms will not join
    levels = (
        ["Below Benchmark", "Well Below Benchmark"]
        if cohort == BOTH
        else ["Well Below Benchmark"]
    )
    for level in levels:
        r = list(base)
        r[7] = level
        rows.append(r)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--academic-year",
        type=int,
        required=True,
        help="academic year, labelled by the FALL (SY26-27 is 2026)",
    )
    parser.add_argument("--rounds", required=True, help="round grid TSV, see docstring")
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
        help=(
            "Comma-separated regions to emit. Defaults to every region in the"
            " --rounds file, in file order. Use this to emit"
            " one region's rows without regenerating another's already-pasted"
            " output."
        ),
    )
    parser.add_argument(
        "--no-scaffold",
        action="store_true",
        help=(
            "no grade gets the pm_goal_include scaffold -- every grade follows"
            " the aimline pattern (rows only for rounds the doc lists, blank"
            " pm_goal_include). Use for the aimline model, which supplies goals"
            " per student and needs no trajectory continuity."
        ),
    )
    args = parser.parse_args()

    academic_year = str(args.academic_year)
    region_rounds = read_rounds(args.rounds)

    if args.no_scaffold:
        scaffold_grades: set[int] = set()
    elif args.single_rows:
        scaffold_grades = set(range(0, 9))
    else:
        scaffold_grades = K2_GRADES

    regions_arg = args.regions or ",".join(region_rounds)
    selected = [r.strip() for r in regions_arg.split(",") if r.strip()]
    unknown = [r for r in selected if r not in region_rounds]
    if unknown:
        raise SystemExit(f"unknown region(s): {', '.join(unknown)}")

    out_rows: list[list[str]] = []

    for region in selected:
        rounds = region_rounds[region]
        # -- grades 3-8: only rounds actually listed, pm_goal_include always blank --
        for round_number, season, start, _end, grades in rounds:
            for grade, (measure_codes, cohort) in grades.items():
                if grade in scaffold_grades:
                    continue
                for ms in measure_rows(measure_codes):
                    base = base_row(
                        academic_year,
                        region,
                        grade,
                        round_number,
                        season,
                        start,
                        "",
                        ms,
                    )
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
                                academic_year,
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
